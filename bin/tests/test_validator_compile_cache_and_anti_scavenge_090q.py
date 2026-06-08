"""v1.5.7 instruction 090q: Phase 0 validator must not false-fail
on a compile-cache write + entry-sequence anti-scavenge guard.

Motivation: 2026-05-24 Ory Keto run3 (Codex / gpt-5.5, uvx channel
install) failed Phase 0 on a freshly, cleanly installed skill, then
the agent's recovery contaminated the run. Two distinct issues:

1. ``bin/qpb_validate.py``'s ``py_compile.compile(str(p),
   doraise=True)`` install-closure parse check wrote a ``.pyc`` into
   the install dir's ``__pycache__``. Codex's restricted sandbox
   denied that write, the validator returned a "py_compile filesystem
   error" → ``status != ok``. The install itself was fine (53 files
   copied, 5/5 smoke checks passed) — the false-fail was entirely a
   cache-write side effect.

2. Instead of HALTing on the Phase-0 failure, Codex searched the
   filesystem for other QPB checkouts (``qpb-bootstrap-v157``,
   ``httpx-1.5.7``, a full source tree), ran ``--force`` reinstalls
   from each, and finally drove a Mode-B ``run_playbook.py --codex``
   run from ``../qpb-bootstrap-v157/`` — abandoning the channel-
   installed skill entirely. The run then tested neither the channel
   install nor the v1.5.7 artifact.

Test surfaces:

  Task A (``_static_parse_ok`` benign-cache-write):
    * test_unwritable_compile_cache_returns_ok — mock
      ``py_compile.compile`` to raise ``PermissionError`` (the run3
      shape); assert the validator returns ``(True, ...)`` with the
      benign-detail string. Mutation bite: revert the benign OSError
      branch in ``_static_parse_ok`` (return ``(False, ...)`` again)
      → this test FAILs.
    * test_oserror_returns_ok_with_benign_detail — same mock, but
      using ``OSError`` (the broader parent type ``py_compile``
      raises on filesystem failures); assert the same benign return.
    * test_syntax_error_still_fails — write a bundled ``.py`` with a
      genuine syntax error, run ``_static_parse_ok`` against it,
      assert ``(False, "py_compile parse failed: …")``. This is the
      load-bearing "don't mask real defects" pin — without it, the
      benign-OSError handling could be a free pass for unparseable
      bundled files.
    * test_valid_py_file_returns_ok — sanity check on the happy path.

  Task B (anti-scavenge entry-sequence guard):
    * test_agents_md_carries_anti_scavenge_guard — AGENTS.md Mode-A
      entry sequence carries the "HALT on Phase-0 you can't resolve;
      never scavenge foreign QPB checkouts / never --force-reinstall
      from a foreign source / never fall back to a different
      run_playbook.py" directive. Mutation bite: drop the directive
      → this test FAILs.
    * test_agents_md_anti_scavenge_cites_run3_motivation — the
      directive references the 2026-05-24 Ory Keto run3 specifics
      so a future reader understands which adopter failure mode
      drove the rule.

  Scope guard:
    * test_skill_md_not_touched_by_090q — SKILL.md must not contain
      the 090q anchors (Halt Condition 2 + the 30K BPE ceiling).
"""
from __future__ import annotations

import os
import py_compile
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from bin import qpb_validate  # noqa: E402


class StaticParseOkCompileCacheBenign090qTests(unittest.TestCase):
    """Task A: _static_parse_ok must treat compile-cache write
    failures (filesystem/permission OSErrors) as benign — the
    source still parsed; cache-write failure is not an install
    defect. PyCompileError / SyntaxError remain fatal."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._tmpdir = Path(self._tmp.name)
        # A trivially-parseable Python file the validator can target.
        self._valid_py = self._tmpdir / "valid.py"
        self._valid_py.write_text(
            "def f(x): return x + 1\n", encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_valid_py_file_returns_ok(self) -> None:
        """Happy path — a parseable file returns (True, None) or
        (True, benign detail). Sanity check before the mocked-OSError
        cases below."""
        ok, detail = qpb_validate._static_parse_ok(self._valid_py)
        self.assertTrue(
            ok, f"valid file unexpectedly failed: {detail}",
        )

    def test_does_not_use_py_compile(self) -> None:
        """v1.5.7 090q Task A regression anchor — the run3 root
        cause: ``py_compile.compile`` writes a ``.pyc`` into the
        install dir's ``__pycache__``, and Codex's restricted
        sandbox denied that write → false Phase-0 failure. The fix
        switches to the builtin ``compile()`` which does pure
        parse + bytecode generation in memory (no I/O).

        ``cfile=os.devnull`` is NOT a workaround — ``py_compile``
        raises ``FileExistsError`` ("``/dev/null`` is a non-regular
        file and will be changed into a regular one if import
        writes a byte-compiled file to it") on POSIX before doing
        the parse, so devnull-routing both fails to bypass the I/O
        AND silently masks SyntaxErrors. The only correct fix is
        to STOP USING ``py_compile`` for this parse check.

        Mutation bite: re-introduce ``py_compile.compile`` (with or
        without the broken ``cfile=os.devnull``) → this test FAILs
        because ``py_compile.compile`` is called. A failing test
        here means the run3 sandbox-write false-fail can recur.
        """
        with mock.patch(
            "bin.qpb_validate.py_compile.compile",
            side_effect=AssertionError(
                "_static_parse_ok must not call py_compile.compile "
                "(v1.5.7 090q — use the builtin compile() instead "
                "so the parse check does no disk I/O at all).",
            ),
        ) as m:
            ok, detail = qpb_validate._static_parse_ok(self._valid_py)
        self.assertEqual(
            m.call_count, 0,
            f"v1.5.7 090q: _static_parse_ok called py_compile."
            f"compile {m.call_count} time(s) — it MUST NOT. Use the "
            f"builtin compile(source, filename, 'exec') instead so "
            f"the parse check does no disk I/O (the run3 false-fail "
            f"was a py_compile cache write into a sandbox-denied "
            f"install dir).",
        )
        # And the valid file should still pass via the builtin path.
        self.assertTrue(ok, f"valid file unexpectedly failed: {detail}")

    def test_syntax_error_still_fails(self) -> None:
        """The load-bearing 'don't mask real defects' pin. A genuine
        SyntaxError must STILL fail — that's a real bundled-file
        defect. The 090q rewrite (builtin compile()) makes parse
        errors trivial to catch and impossible to mask: there's no
        I/O step that could swallow them.

        Mutation bite: change the SyntaxError branch to also return
        (True, ...) → this test FAILs.
        """
        bad_py = self._tmpdir / "bad.py"
        bad_py.write_text(
            "def f(x:\n  return x + 1\n",  # syntactically invalid
            encoding="utf-8",
        )
        ok, detail = qpb_validate._static_parse_ok(bad_py)
        self.assertFalse(
            ok,
            f"v1.5.7 090q: a genuine SyntaxError in a bundled file "
            f"must STILL fail — the builtin-compile() rewrite must "
            f"NOT mask real parse defects.",
        )
        self.assertIn("py_compile parse failed", detail)

    def test_oserror_on_source_read_is_benign(self) -> None:
        """An OSError on the source-read step (exotic FUSE mount,
        torn read, etc.) is treated as benign — the canonical
        readability check (`_readable_file`) runs upstream in
        `_check_install_closure`, so this OSError catch is a
        safety net for unusual filesystem failure modes, not the
        primary unreadable-file signal.

        Mutation bite: drop the OSError catch in _static_parse_ok
        → an exotic-FS read failure would re-trigger a Phase-0
        false-fail. This test FAILs.
        """
        with mock.patch.object(
            Path, "read_bytes",
            side_effect=OSError("exotic filesystem read failure"),
        ):
            ok, detail = qpb_validate._static_parse_ok(self._valid_py)
        self.assertTrue(
            ok,
            f"v1.5.7 090q: an OSError on the source-read step must "
            f"be BENIGN (it's not a parse defect; the canonical "
            f"readability check runs upstream). Got ok={ok}, "
            f"detail={detail!r}.",
        )
        self.assertIn("benign", detail)
        self.assertIn("090q", detail)


class AntiScavengeGuard090qTests(unittest.TestCase):
    """Task B: AGENTS.md's Mode-A entry sequence must instruct the
    agent to HALT on a Phase-0 failure it cannot resolve, and
    explicitly forbid scavenging foreign QPB checkouts / foreign-
    source --force-reinstalls / falling back to a different
    run_playbook.py."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.agents_text = (
            _REPO_ROOT / "AGENTS.md"
        ).read_text(encoding="utf-8")

    def test_agents_md_carries_anti_scavenge_guard(self) -> None:
        """Mutation bite: drop the 'HALT and report' / 'never
        scavenge' directive from AGENTS.md → this test FAILs."""
        self.assertIn(
            "v1.5.7 090q — anti-scavenge guard",
            self.agents_text,
            "AGENTS.md must carry the 090q anti-scavenge guard "
            "anchor.",
        )
        # The directive must explicitly require HALT + report.
        self.assertIn(
            "HALT the run and report the validator's findings",
            self.agents_text,
        )
        # And explicitly forbid each of the three scavenging
        # behaviors observed in the run3 contamination:
        self.assertIn(
            "other QPB checkouts / source trees",
            self.agents_text,
        )
        self.assertIn(
            "`--force` reinstalls from a foreign source",
            self.agents_text,
        )
        self.assertIn(
            "different `run_playbook.py`",
            self.agents_text,
        )

    def test_agents_md_anti_scavenge_cites_run3_motivation(
            self) -> None:
        """The directive must cite the 2026-05-24 Ory Keto run3
        specifics so a future reader understands which adopter
        failure mode drove the rule."""
        self.assertIn(
            "2026-05-24 Ory Keto run3", self.agents_text,
        )
        # The directive must name the specific foreign trees Codex
        # scavenged so future readers can pattern-match the trap.
        self.assertIn("qpb-bootstrap-v157", self.agents_text)
        # And it must close with the bumper-sticker rule.
        self.assertIn(
            "A failed Phase 0 is a signal to report, not a license to scavenge",
            self.agents_text,
        )


class ScopeGuard090qTests(unittest.TestCase):
    """Halt Condition 2 + 30K ceiling pin: SKILL.md must NOT carry
    the 090q anchors. The contract lives in `bin/qpb_validate.py`
    (Task A) and `AGENTS.md` (Task B), not in SKILL.md."""

    def test_skill_md_not_touched_by_090q(self) -> None:
        text = (_REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "v1.5.7 090q", text,
            "SKILL.md contains a 090q anchor — 090q's halt "
            "condition + the 32K BPE ceiling say 'don't touch "
            "SKILL.md'. Keep the contract in qpb_validate.py + "
            "AGENTS.md.",
        )


if __name__ == "__main__":
    unittest.main()
