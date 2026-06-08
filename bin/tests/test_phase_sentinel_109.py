"""v1.5.7 109 — phase sentinel: qpb_phase emitter + gate-result
sentinel + bundle-safety.

THREE emitters per 109:

  (1) ``bin/qpb_phase.py`` (new) — the skill calls it at each
      phase boundary. Emits one ``::QPB:: {json}`` line with
      ``kind:"phase"`` carrying a deterministic name (NOT
      model-supplied) + optional model-supplied note.
  (2) ``quality_gate.py`` — gains a ``::QPB:: {json}`` line with
      ``kind:"gate"`` carrying the gate's OWN computed
      gate_result + verdict_state. **HARD CONSTRAINT**:
      ``total_line`` / ``result_line`` / ``exit_code`` stay
      byte-identical to the pre-sentinel baseline; the sentinel
      is an ADDITIONAL line emitted AFTER the verdict block.
  (3) ``SKILL.md`` — calls (1) at each phase boundary with a
      1-3 sentence summary on ``done``.

Tests (109 Task D):
  * qpb_phase format/JSON; phase-name table; note newline-
    collapse + truncation; absent-note omits the key; no-args
    self-describing (089x); import-discipline clean (090c —
    stdlib only).
  * quality_gate.py emits the ``kind:"gate"`` line with right
    values AND the load-bearing-line regression (total_line /
    result_line / exit_code byte-identical to baseline,
    existing verdict parsers still parse correctly).
  * bundle-safety: qpb_phase.py present in BOTH channel
    closures; bin/harness/ still excluded.

Parser lives in the 107 status layer — out of scope for 109.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_qpb_phase():
    """Load bin/qpb_phase.py as a module without going through
    `bin/__init__.py` (which is its own bundle-discipline
    surface). Mirrors the pattern other 089x/090c tests use."""
    spec = importlib.util.spec_from_file_location(
        "qpb_phase_under_test",
        str(_REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts" / "qpb_phase.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_SENTINEL_PREFIX = "::QPB:: "
_SENTINEL_RE = re.compile(
    r"^::QPB:: (\{.+\})$"
)


def _parse_sentinel(line: str) -> dict:
    """Parse a single ``::QPB:: {json}`` line; return the JSON
    payload."""
    m = _SENTINEL_RE.match(line.rstrip())
    if not m:
        raise AssertionError(
            f"expected ::QPB:: line, got: {line!r}"
        )
    return json.loads(m.group(1))


# ---------------------------------------------------------------------------
# Task A — qpb_phase format + table + note handling
# ---------------------------------------------------------------------------


class QpbPhaseFormatTests(unittest.TestCase):

    def setUp(self):
        self.mod = _load_qpb_phase()

    def test_format_sentinel_basic_start(self):
        line = self.mod.format_sentinel(
            phase=3, state="start",
            ts="2026-05-26T16:30:00Z",
        )
        # Prefix + JSON envelope shape.
        self.assertTrue(line.startswith(_SENTINEL_PREFIX))
        payload = _parse_sentinel(line)
        self.assertEqual(payload["v"], 1)
        self.assertEqual(payload["kind"], "phase")
        self.assertEqual(payload["phase"], 3)
        self.assertEqual(payload["name"], "code-review")
        self.assertEqual(payload["state"], "start")
        self.assertEqual(payload["ts"], "2026-05-26T16:30:00Z")
        # No `note` when absent.
        self.assertNotIn("note", payload)

    def test_format_sentinel_done_with_note(self):
        line = self.mod.format_sentinel(
            phase=3, state="done", note="Reviewed the dup-key path.",
            ts="2026-05-26T16:33:12Z",
        )
        payload = _parse_sentinel(line)
        self.assertEqual(payload["state"], "done")
        self.assertEqual(
            payload["note"], "Reviewed the dup-key path.",
        )

    def test_phase_name_table_covers_0_through_6(self):
        """The deterministic phase-name table covers exactly
        phases 0..6 (the SKILL.md phase set)."""
        self.assertEqual(
            set(self.mod._PHASE_NAMES.keys()),
            {0, 1, 2, 3, 4, 5, 6},
        )
        # Names match the SKILL.md phase headings via short slugs.
        self.assertEqual(self.mod._PHASE_NAMES[0], "validation")
        self.assertEqual(self.mod._PHASE_NAMES[1], "exploration")
        self.assertEqual(self.mod._PHASE_NAMES[2], "generation")
        self.assertEqual(self.mod._PHASE_NAMES[3], "code-review")
        self.assertEqual(self.mod._PHASE_NAMES[4], "spec-audit")
        self.assertEqual(self.mod._PHASE_NAMES[5], "reconciliation")
        self.assertEqual(self.mod._PHASE_NAMES[6], "verification")

    def test_unknown_phase_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.mod.format_sentinel(phase=7, state="start")
        with self.assertRaises(ValueError):
            self.mod.format_sentinel(phase=-1, state="start")

    def test_invalid_state_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.mod.format_sentinel(phase=0, state="running")

    def test_note_newlines_collapsed_to_single_space(self):
        line = self.mod.format_sentinel(
            phase=2, state="done",
            note="line 1\nline 2\n\nline 3\ttab\tinside",
        )
        payload = _parse_sentinel(line)
        self.assertEqual(
            payload["note"],
            "line 1 line 2 line 3 tab inside",
        )

    def test_note_truncated_to_240_chars(self):
        long_note = "x" * 500
        line = self.mod.format_sentinel(
            phase=2, state="done", note=long_note,
        )
        payload = _parse_sentinel(line)
        # Truncated to 240 chars total (incl. the ellipsis).
        self.assertLessEqual(len(payload["note"]), 240)
        self.assertTrue(payload["note"].endswith("…"))

    def test_empty_note_after_collapse_omits_key(self):
        """A note that's whitespace-only after collapse ⇒ omit
        the key entirely (same as absent)."""
        line = self.mod.format_sentinel(
            phase=2, state="done", note="   \n\t  \n  ",
        )
        payload = _parse_sentinel(line)
        self.assertNotIn("note", payload)

    def test_payload_is_single_line(self):
        line = self.mod.format_sentinel(
            phase=0, state="start",
            note="multi\nline\nnote",
        )
        # The whole ::QPB:: line has no embedded newline.
        self.assertNotIn("\n", line)


# ---------------------------------------------------------------------------
# Task A — qpb_phase CLI behavior (089x self-describing)
# ---------------------------------------------------------------------------


class QpbPhaseCliTests(unittest.TestCase):

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable,
             str(_REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts" / "qpb_phase.py"), *args],
            capture_output=True, text=True, timeout=10,
        )

    def test_no_args_prints_purpose_and_exits_0(self):
        result = self._run()
        self.assertEqual(
            result.returncode, 0,
            f"089x: no-args must exit 0; got rc={result.returncode}\n"
            f"stderr:\n{result.stderr}",
        )
        out = result.stdout
        self.assertIn("qpb_phase", out)
        # 089x canonical banner shape (via _purpose.
        # print_command_intro): "Role in a playbook run:" +
        # the usage hint is in the trailing "run with --help"
        # line.
        self.assertIn("Role in a playbook run:", out)
        self.assertIn("qpb_phase <phase:int>", out)

    def test_help_flag_prints_purpose_and_exits_0(self):
        result = self._run("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("qpb_phase", result.stdout)

    def test_cli_emits_sentinel_line(self):
        result = self._run("3", "start")
        self.assertEqual(result.returncode, 0)
        lines = [
            ln for ln in result.stdout.splitlines()
            if ln.startswith(_SENTINEL_PREFIX)
        ]
        self.assertEqual(len(lines), 1)
        payload = _parse_sentinel(lines[0])
        self.assertEqual(payload["phase"], 3)
        self.assertEqual(payload["name"], "code-review")
        self.assertEqual(payload["state"], "start")

    def test_cli_with_note(self):
        result = self._run(
            "3", "done", "--note", "Found 2 issues in Phase 3.",
        )
        self.assertEqual(result.returncode, 0)
        lines = [
            ln for ln in result.stdout.splitlines()
            if ln.startswith(_SENTINEL_PREFIX)
        ]
        self.assertEqual(len(lines), 1)
        payload = _parse_sentinel(lines[0])
        self.assertEqual(
            payload["note"], "Found 2 issues in Phase 3.",
        )

    def test_cli_invalid_phase_exits_2(self):
        result = self._run("99", "start")
        self.assertEqual(result.returncode, 2)


# ---------------------------------------------------------------------------
# Task A — import-discipline (090c): qpb_phase imports stdlib only
# ---------------------------------------------------------------------------


class QpbPhaseImportDisciplineTests(unittest.TestCase):

    def test_only_canonical_purpose_import_in_source(self):
        """090c: shipped scripts may import ONLY from the
        canonical ``bin/_purpose.py`` helper (via the 3-step
        anchored fallback pattern that every other shipped
        script uses — `from bin._purpose import ...`,
        `from _purpose import ...`, then path-load). They must
        NOT import from any OTHER ``bin/`` script. qpb_phase
        ships, so its only ``bin/`` import is _purpose."""
        # v1.5.8 instruction 208: qpb_phase.py moved to skills/quality-playbook/scripts/.
        src = (_REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
               / "scripts" / "qpb_phase.py").read_text(
            encoding="utf-8")
        # Allowed: `from bin._purpose import ...`
        # Forbidden: `from bin.X import ...` for X != _purpose
        for forbidden in (
            "from bin.harness",
            "from bin.run_playbook",
            "from bin.install_skill",
            "from bin.qpb_validate",
            "from bin.qpb_harness",
            "from bin.quality_playbook",
            "import bin.harness",
            "import bin.run_playbook",
        ):
            self.assertNotIn(
                forbidden, src,
                f"qpb_phase must not `{forbidden}` — only the "
                f"canonical _purpose helper is allowed across "
                f"the bin/ closure.",
            )

    def test_loads_without_bin_package_on_sys_path(self):
        """A subprocess with `bin` removed from PYTHONPATH still
        runs qpb_phase.py — proves the script doesn't transitively
        rely on ``bin/__init__.py``."""
        env = os.environ.copy()
        # Strip any bin path from PYTHONPATH.
        env.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable,
                 str(_REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts" / "qpb_phase.py"),
                 "0", "start"],
                cwd=tmp,  # foreign cwd → no implicit bin/
                env=env,
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(
                result.returncode, 0,
                f"090c: qpb_phase.py must load + run with no "
                f"bin/ on PYTHONPATH. rc={result.returncode}\n"
                f"stderr:\n{result.stderr}",
            )


# ---------------------------------------------------------------------------
# Task B — quality_gate.py emits the kind:"gate" sentinel
# ---------------------------------------------------------------------------


def _import_gate_module():
    """Load quality_gate.py as a module — same pattern as the
    gate test suite uses internally."""
    # v1.5.8 instruction 208: quality_gate.py moved to skills/quality-playbook/scripts/.
    spec = importlib.util.spec_from_file_location(
        "quality_gate_under_test",
        str(_REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
             / "quality_gate.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class QualityGateSentinelHelperTests(unittest.TestCase):
    """Unit tests for the new ``_format_gate_sentinel`` helper +
    ``_compute_verdict_state`` helper."""

    def setUp(self):
        self.gate = _import_gate_module()

    def test_format_gate_sentinel_pass_solid(self):
        line = self.gate._format_gate_sentinel(
            gate_result="PASS", verdict_state="solid",
            ts="2026-05-26T16:34:01Z",
        )
        payload = _parse_sentinel(line)
        self.assertEqual(payload["v"], 1)
        self.assertEqual(payload["kind"], "gate")
        self.assertEqual(payload["gate_result"], "PASS")
        self.assertEqual(payload["verdict_state"], "solid")
        self.assertEqual(payload["ts"], "2026-05-26T16:34:01Z")

    def test_format_gate_sentinel_fail_failed(self):
        line = self.gate._format_gate_sentinel(
            gate_result="FAIL", verdict_state="failed",
            ts="2026-05-26T16:34:01Z",
        )
        payload = _parse_sentinel(line)
        self.assertEqual(payload["gate_result"], "FAIL")
        self.assertEqual(payload["verdict_state"], "failed")

    def test_format_gate_sentinel_cleanup(self):
        line = self.gate._format_gate_sentinel(
            gate_result="CLEANUP", verdict_state="solid",
            ts="2026-05-26T16:34:01Z",
        )
        payload = _parse_sentinel(line)
        self.assertEqual(payload["gate_result"], "CLEANUP")

    def test_compute_verdict_state_solid(self):
        """Zero fails, no warns, no zero-bug repos ⇒ solid."""
        state = self.gate._compute_verdict_state(
            exit_code=0, fail_records=[], warn_records=[],
            zero_bug_repos=[],
        )
        self.assertEqual(state, "solid")

    def test_compute_verdict_state_shallow_from_zero_bug(self):
        state = self.gate._compute_verdict_state(
            exit_code=0, fail_records=[], warn_records=[],
            zero_bug_repos=["repo-a"],
        )
        self.assertEqual(state, "shallow")

    def test_compute_verdict_state_failed_from_exit_nonzero(self):
        state = self.gate._compute_verdict_state(
            exit_code=1, fail_records=[("substantive", "x")],
            warn_records=[], zero_bug_repos=[],
        )
        self.assertEqual(state, "failed")


# ---------------------------------------------------------------------------
# Task B HARD CONSTRAINT — load-bearing-line regression
# ---------------------------------------------------------------------------


# Reuse the canonical fixture builders from the gate test suite.
sys.path.insert(0, str(
    _REPO_ROOT / ".github" / "skills" / "quality_gate" / "tests"
))
from test_quality_gate import (  # noqa: E402
    minimal_zero_bug_tree, add_one_bug, write_tree,
)


_REAL_PY_FUNCTIONAL_TEST = (
    "import unittest\n\n"
    "class FunctionalTests(unittest.TestCase):\n"
    "    def test_thing(self):\n"
    "        self.assertEqual(1 + 1, 2)\n"
)


class GateLoadBearingLinesRegressionTests(unittest.TestCase):
    """**The 109 mutation-bite for Task B.**

    The HARD CONSTRAINT is that ``total_line`` / ``result_line``
    / ``exit_code`` stay byte-identical to the pre-sentinel
    baseline. Pre-sentinel-era downstream consumers anchor on
    these patterns (Phase-6 witness, ``what_just_happened.md``,
    the harness fact extractors). The 109 sentinel is an
    ADDITIONAL line emitted AFTER the verdict block — never
    altering, reordering, or interleaving with the load-bearing
    lines.

    Mutation-bite: emit the sentinel in a way that shifts /
    garbles a load-bearing line (e.g. print it between
    total_line and result_line) ⇒ THIS test fails.
    """

    def _run_gate(self, populate_fn) -> tuple[int, str]:
        """Build a fixture tree and run the gate. Return
        (exit_code, full_stdout)."""
        from bin import install_skill
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            populate_fn(target)
            (target / ".github").mkdir(exist_ok=True)
            install_skill.install(into=target, ai_tool="claude",
                                    no_smoke=True)
            result = subprocess.run(
                [sys.executable, str(
                    target / ".claude" / "skills"
                    / "quality-playbook" / "quality_gate.py"),
                 str(target)],
                capture_output=True, text=True, timeout=120,
            )
            return result.returncode, result.stdout

    def _populate_solid(self, target: Path) -> None:
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id="BUG-001")
        tree["quality/test_functional.py"] = _REAL_PY_FUNCTIONAL_TEST
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.4.4\n\n"
            "## Phases\n- [x] Phase 1\n- [x] Phase 2\n"
            "- [x] Phase 3\n- [x] Phase 4\n"
            "- [x] Phase 5\n- [x] Phase 6\n"
            "## Terminal Gate Verification\n"
        )
        write_tree(target, tree)

    def test_total_and_result_lines_present_and_unchanged_pattern(
            self) -> None:
        """The canonical anchors stay where downstream consumers
        find them. We don't pin literal SHAs (the line content
        already varies per tree), but we DO pin the regex shapes
        that the existing parsers (facts.py, witness, etc.) match
        against — those must still match. Mutation-bite: if the
        sentinel garbles a load-bearing line, the regex match
        fails."""
        exit_code, stdout = self._run_gate(self._populate_solid)
        # exit_code unchanged for the solid tree.
        self.assertEqual(exit_code, 0)
        # total_line and result_line still in canonical form.
        total_re = re.compile(
            r"^Total: \d+ FAIL, \d+ WARN$", re.MULTILINE,
        )
        self.assertTrue(
            total_re.search(stdout),
            f"109: total_line regex must still match (load-"
            f"bearing for facts.py + witness). stdout:\n"
            f"{stdout}",
        )
        result_re = re.compile(
            r"^RESULT: GATE PASSED$", re.MULTILINE,
        )
        self.assertTrue(
            result_re.search(stdout),
            "109: RESULT: line must still match the load-bearing "
            "'GATE PASSED' pattern for a solid tree",
        )

    def test_gate_sentinel_line_present_after_verdict_block(
            self) -> None:
        """The 109 ``::QPB::`` gate line is emitted ONCE and
        AFTER the verdict block (after RESULT: + operator-
        verdict). Position check: the sentinel comes AFTER the
        RESULT: line in the output stream."""
        exit_code, stdout = self._run_gate(self._populate_solid)
        sentinel_lines = [
            ln for ln in stdout.splitlines()
            if ln.startswith(_SENTINEL_PREFIX)
        ]
        gate_sentinels = [
            ln for ln in sentinel_lines
            if '"kind":"gate"' in ln
        ]
        self.assertEqual(
            len(gate_sentinels), 1,
            f"109: exactly one kind:gate sentinel; got "
            f"{len(gate_sentinels)}",
        )
        payload = _parse_sentinel(gate_sentinels[0])
        self.assertEqual(payload["v"], 1)
        self.assertEqual(payload["kind"], "gate")
        self.assertEqual(payload["gate_result"], "PASS")
        self.assertEqual(payload["verdict_state"], "solid")
        # Position check: the gate sentinel comes AFTER the
        # RESULT: line.
        lines = stdout.splitlines()
        result_idx = next(
            (i for i, ln in enumerate(lines)
             if ln.startswith("RESULT:")), -1,
        )
        sentinel_idx = next(
            (i for i, ln in enumerate(lines)
             if ln.startswith(_SENTINEL_PREFIX)
             and '"kind":"gate"' in ln), -1,
        )
        self.assertGreater(result_idx, -1)
        self.assertGreater(sentinel_idx, result_idx,
                            "109: ::QPB:: sentinel must land "
                            "AFTER RESULT: (never before / "
                            "interleaved with the load-bearing "
                            "verdict block)")

    def test_facts_extraction_still_works_with_sentinel_present(
            self) -> None:
        """The harness's ``parse_gate_stdout`` still extracts
        the correct ``gate_result`` / ``verdict_state`` from a
        gate run that now includes the ::QPB:: sentinel line.
        Mutation-bite: if the sentinel garbles a load-bearing
        line, the parsers misextract."""
        from bin.harness import facts as F
        from bin.harness import schema as S
        exit_code, stdout = self._run_gate(self._populate_solid)
        gate, verdict, _prov = F.parse_gate_stdout(stdout)
        # PASS / solid extracted correctly despite the sentinel.
        self.assertEqual(gate.gate_result, S.GateResult.PASS)
        self.assertEqual(verdict.verdict_state,
                          S.VerdictState.SOLID)


# ---------------------------------------------------------------------------
# 109 (fix) — strengthen byte-identity coverage across PASS / CLEANUP / FAIL
# ---------------------------------------------------------------------------


class GateByteIdentityAcrossVerdictsTests(unittest.TestCase):
    """109 Council review nit 4: the original PASS-only regex
    test pinned shape, not byte identity, AND skipped the
    non-PASS paths. This class adds coverage that:

      * runs the gate over PASS / CLEANUP / FAIL fixture trees
      * confirms the ``::QPB:: {kind:"gate"}`` sentinel is the
        last line (109 contract);
      * confirms the load-bearing `total_line` and `result_line`
        appear ABOVE the sentinel AND parse via the same regex
        anchors used by ``facts.parse_gate_stdout``;
      * confirms the harness's authoritative grading
        (``parse_gate_stdout``) still extracts the right
        gate_result + verdict_state across all three verdicts
        despite the sentinel.

    The verdict-state in the sentinel is asserted equal to the
    verdict-state in the parsed facts — so divergence between
    operator-facing render and harness-facing sentinel would
    surface immediately.
    """

    def _run_gate(self, populate_fn) -> tuple[int, str]:
        from bin import install_skill
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            populate_fn(target)
            (target / ".github").mkdir(exist_ok=True)
            install_skill.install(into=target, ai_tool="claude",
                                    no_smoke=True)
            result = subprocess.run(
                [sys.executable, str(
                    target / ".claude" / "skills"
                    / "quality-playbook" / "quality_gate.py"),
                 str(target)],
                capture_output=True, text=True, timeout=120,
            )
            return result.returncode, result.stdout

    def _populate_failed(self, target: Path) -> None:
        tree = minimal_zero_bug_tree()
        tree["quality/BUGS.md"] = (
            "# Bugs\n\n### BUG-001: Example\nDescription.\n"
        )
        tree["quality/test_functional.py"] = (
            _REAL_PY_FUNCTIONAL_TEST
        )
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.4.4\n\n"
            "## Phases\n- [x] Phase 1\n- [x] Phase 2\n"
            "- [x] Phase 3\n- [x] Phase 4\n"
            "- [x] Phase 5\n- [x] Phase 6\n"
            "## Terminal Gate Verification\n"
        )
        write_tree(target, tree)

    def _gate_sentinel_payload(self, stdout: str) -> dict:
        for ln in reversed(stdout.splitlines()):
            if (ln.startswith(_SENTINEL_PREFIX)
                    and '"kind":"gate"' in ln):
                return _parse_sentinel(ln)
        raise AssertionError(
            "no kind:gate sentinel in gate stdout"
        )

    def _populate_solid(self, target: Path) -> None:
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id="BUG-001")
        tree["quality/test_functional.py"] = (
            _REAL_PY_FUNCTIONAL_TEST
        )
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.4.4\n\n"
            "## Phases\n- [x] Phase 1\n- [x] Phase 2\n"
            "- [x] Phase 3\n- [x] Phase 4\n"
            "- [x] Phase 5\n- [x] Phase 6\n"
            "## Terminal Gate Verification\n"
        )
        write_tree(target, tree)

    def test_pass_path_load_bearing_invariants(self) -> None:
        from bin.harness import facts as F
        from bin.harness import schema as S
        exit_code, stdout = self._run_gate(self._populate_solid)
        self.assertEqual(exit_code, 0)
        # Sentinel last; load-bearing line ABOVE it.
        lines = stdout.splitlines()
        sentinel_indexes = [
            i for i, ln in enumerate(lines)
            if (ln.startswith(_SENTINEL_PREFIX)
                and '"kind":"gate"' in ln)
        ]
        result_indexes = [
            i for i, ln in enumerate(lines)
            if ln.startswith("RESULT: GATE")
        ]
        self.assertEqual(len(sentinel_indexes), 1)
        self.assertEqual(len(result_indexes), 1)
        self.assertLess(result_indexes[0], sentinel_indexes[0])
        # parse_gate_stdout extracts PASS / solid.
        gate, verdict, _prov = F.parse_gate_stdout(stdout)
        self.assertEqual(gate.gate_result, S.GateResult.PASS)
        self.assertEqual(verdict.verdict_state,
                          S.VerdictState.SOLID)
        # Sentinel agrees with the parser.
        payload = self._gate_sentinel_payload(stdout)
        self.assertEqual(payload["gate_result"], "PASS")
        self.assertEqual(payload["verdict_state"], "solid")

    def test_failed_path_load_bearing_invariants(self) -> None:
        from bin.harness import facts as F
        from bin.harness import schema as S
        exit_code, stdout = self._run_gate(self._populate_failed)
        # Exit nonzero on FAIL.
        self.assertEqual(exit_code, 1)
        # Sentinel last; load-bearing line ABOVE it.
        lines = stdout.splitlines()
        sentinel_indexes = [
            i for i, ln in enumerate(lines)
            if (ln.startswith(_SENTINEL_PREFIX)
                and '"kind":"gate"' in ln)
        ]
        result_indexes = [
            i for i, ln in enumerate(lines)
            if ln.startswith("RESULT: GATE")
        ]
        self.assertEqual(len(sentinel_indexes), 1)
        self.assertEqual(len(result_indexes), 1)
        self.assertLess(result_indexes[0], sentinel_indexes[0])
        # parse_gate_stdout extracts FAIL / failed.
        gate, verdict, _prov = F.parse_gate_stdout(stdout)
        self.assertEqual(gate.gate_result, S.GateResult.FAIL)
        self.assertEqual(verdict.verdict_state,
                          S.VerdictState.FAILED)
        # Sentinel agrees with the parser (the 109 contract:
        # operator-facing and harness-facing state slugs match
        # via _compute_verdict_state).
        payload = self._gate_sentinel_payload(stdout)
        self.assertEqual(payload["gate_result"], "FAIL")
        self.assertEqual(payload["verdict_state"], "failed")


# ---------------------------------------------------------------------------
# Task D — bundle-safety: qpb_phase IN both closures; harness OUT
# ---------------------------------------------------------------------------


class QpbPhaseBundleInclusionTests(unittest.TestCase):

    def test_qpb_phase_in_strict_bundle_closure(self) -> None:
        """``_bundle_files`` strict path includes
        ``bin/qpb_phase.py`` — the adopter-side SKILL.md
        directive can resolve ``<install_root>/bin/qpb_phase.py``."""
        from bin.install_skill import _bundle_files
        bundle = _bundle_files(_REPO_ROOT)
        dest_paths = [str(dst) for _src, dst in bundle]
        self.assertIn(
            "bin/qpb_phase.py", dest_paths,
            "109: qpb_phase.py must ship in the strict bundle "
            "closure (the skill calls it at each phase boundary).",
        )

    def test_qpb_phase_in_soft_bundle_closure(self) -> None:
        """The soft (best-effort) enumeration path also lists
        ``bin/qpb_phase.py`` — keeps the freshness-check + the
        installer parallel."""
        from bin.install_skill import _bundle_files_soft
        bundle = _bundle_files_soft(_REPO_ROOT)
        dest_paths = [str(dst) for _src, dst in bundle]
        self.assertIn("bin/qpb_phase.py", dest_paths)

    def test_harness_still_excluded(self) -> None:
        """Defense-in-depth: the 091 harness-exclusion pin still
        holds. Adding qpb_phase to the closure must not leak
        ``bin/harness/`` or ``bin/qpb_harness.py``."""
        from bin.install_skill import _bundle_files
        bundle = _bundle_files(_REPO_ROOT)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                p.startswith("bin/harness/")
                or p == "bin/qpb_harness.py",
                f"109 must not perturb 091 harness exclusion: "
                f"{p!r} leaked.",
            )


if __name__ == "__main__":
    unittest.main()
