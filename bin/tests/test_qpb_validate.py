"""v1.5.7 instruction 077 (addendum r3 §3.1 / acceptance #1) —
general Phase 0 validator behavior.

Pins the §3.1 behavior contract: run-nonce + on-disk witness, the
nonce stamped on every emitted line, structured exit codes
(0 ok / 1 remediable / 2 blocked), and the detection findings
(install_absent / install_partial / install_wrong_ai_tool /
validator_invoked_from_clone / multiple_ai_tool_markers).

Environment checks (Python-version / cli-on-PATH / bash) are
host-dependent, so the exit-code / closure subtests patch
check_environment to isolate the behavior under test from CI host
state — a deliberate unit-test isolation, not a behavior change.
(v1.5.7 089y: the prior `tiktoken` / `yaml` `python_pkg` checks
were dropped — the shipped runtime is stdlib-only; adopters need
no third-party Python packages.)
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bin import qpb_validate as v

_QPB_ROOT = Path(__file__).resolve().parents[2]
_VALIDATOR = _QPB_ROOT / "bin" / "qpb_validate.py"
_INSTALLER = _QPB_ROOT / "bin" / "install_skill.py"

_NONCE_RE = re.compile(r"\bnonce=([0-9a-f]{32})\b")


def _run_main(argv):
    """Call v.main(argv) in-process, capturing (exit_code, stdout)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = v.main(argv)
    return rc, buf.getvalue()


def _install(target: Path) -> None:
    subprocess.run(
        [sys.executable, str(_INSTALLER), "--into", str(target),
         "--ai-tool", "claude"],
        check=True, capture_output=True)


class ValidatorNonceWitnessTests(unittest.TestCase):

    def test_validator_emits_nonce_and_writes_disk_file(self) -> None:
        """A .qpb_validation_<ts>_<nonce>.txt witness is written under
        <target>/quality/ and its nonce matches the emitted nonce.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-077 —
        BITE EXECUTED during instruction-077 development:
          Mutation: comment out `witness.write_text(body, ...)` in
          bin/qpb_validate.py:_write_witness.
          Observed failure (purged __pycache__ first):
            AssertionError: no .qpb_validation_* witness file under
            <target>/quality/
          Restoration: write_text restored; test PASS again.
        """
        with TemporaryDirectory() as td:
            target = Path(td).resolve()
            (target / ".claude").mkdir()
            rc, out = _run_main([str(target)])
            m = _NONCE_RE.search(out)
            self.assertIsNotNone(m, f"no nonce in output:\n{out}")
            nonce = m.group(1)
            qdir = target / "quality"
            hits = list(qdir.glob(f".qpb_validation_*_{nonce}.txt"))
            self.assertEqual(
                len(hits), 1,
                f"expected exactly one witness for nonce {nonce}; "
                f"found {hits} (dir={list(qdir.iterdir())})")
            body = hits[0].read_text(encoding="utf-8")
            self.assertIn(f"nonce={nonce}", body)
            self.assertIn("target=", body)

    def test_validator_event_lines_carry_nonce(self) -> None:
        """Every emitted event line carries nonce=<that-run-nonce>."""
        with TemporaryDirectory() as td:
            target = Path(td).resolve()
            (target / ".claude").mkdir()
            _, out = _run_main([str(target)])
        lines = [ln for ln in out.splitlines() if ln.strip()]
        self.assertTrue(lines)
        nonces = set()
        for ln in lines:
            self.assertTrue(
                ln.startswith("event="),
                f"non-event line emitted: {ln!r}")
            m = _NONCE_RE.search(ln)
            self.assertIsNotNone(m, f"line missing nonce: {ln!r}")
            nonces.add(m.group(1))
        self.assertEqual(len(nonces), 1,
                         f"inconsistent nonces across lines: {nonces}")


class ValidatorExitCodeTests(unittest.TestCase):

    def test_validator_exit_codes(self) -> None:
        """ok=0, remediable=1, blocked=2 (§3.1 step 8).

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-077 —
        BITE EXECUTED during instruction-077 development:
          Mutation: in bin/qpb_validate.py:main(), change the
          findings==0 branch `return 0` to `return 1`.
          Observed failure (purged __pycache__ first):
            FAIL: test_validator_exit_codes
            AssertionError: 1 != 0 : event=invocation_context
            nonce=<hex> location=clone root=<clone>
            witness=.qpb_validation_<ts>_<hex>.txt … status=ok …
            (the ok subcase: rc was 1, expected 0)
          Restoration: `return 0` restored; test PASS again.
        """
        # ok = 0 — full install + clean (patched) environment.
        with TemporaryDirectory() as td:
            target = Path(td).resolve()
            (target / ".claude").mkdir()
            _install(target)
            (target / ".gitignore").write_text("quality/\n")
            (target / "reference_docs" / "cite").mkdir(parents=True)
            with mock.patch.object(v, "check_environment",
                                   return_value=([], [])):
                rc, out = _run_main([str(target)])
            self.assertEqual(rc, 0, out)
            self.assertIn("status=ok", out)

        # remediable = 1 — no install, clean (patched) environment.
        with TemporaryDirectory() as td:
            target = Path(td).resolve()
            (target / ".claude").mkdir()
            (target / ".gitignore").write_text("quality/\n")
            (target / "reference_docs" / "cite").mkdir(parents=True)
            with mock.patch.object(v, "check_environment",
                                   return_value=([], [])):
                rc, out = _run_main([str(target)])
            self.assertEqual(rc, 1, out)
            self.assertIn("status=remediable", out)

        # blocked = 2 — multiple AI-tool markers, no --ai-tool.
        with TemporaryDirectory() as td:
            target = Path(td).resolve()
            (target / ".claude").mkdir()
            (target / ".cursor").mkdir()
            rc, out = _run_main([str(target)])
            self.assertEqual(rc, 2, out)
            self.assertIn("status=blocked", out)


class ValidatorFindingTests(unittest.TestCase):

    def test_validator_detects_install_absent(self) -> None:
        with TemporaryDirectory() as td:
            target = Path(td).resolve()
            (target / ".claude").mkdir()
            with mock.patch.object(v, "check_environment",
                                   return_value=([], [])):
                rc, out = _run_main([str(target)])
        self.assertEqual(rc, 1, out)
        self.assertIn("finding=install_absent", out)
        self.assertIn("status=remediable", out)

    def test_validator_detects_install_partial(self) -> None:
        with TemporaryDirectory() as td:
            target = Path(td).resolve()
            (target / ".claude").mkdir()
            _install(target)
            victim = (target / ".claude" / "skills" / "quality-playbook"
                      / "references" / "verification.md")
            self.assertTrue(victim.is_file(), "fixture install incomplete")
            victim.unlink()
            with mock.patch.object(v, "check_environment",
                                   return_value=([], [])):
                rc, out = _run_main([str(target)])
        self.assertEqual(rc, 1, out)
        self.assertIn("finding=install_partial", out)
        self.assertIn("references/verification.md", out)

    def test_validator_detects_wrong_ai_tool(self) -> None:
        with TemporaryDirectory() as td:
            target = Path(td).resolve()
            (target / ".cursor").mkdir()
            subprocess.run(
                [sys.executable, str(_INSTALLER), "--into", str(target),
                 "--ai-tool", "cursor"], check=True, capture_output=True)
            with mock.patch.object(v, "check_environment",
                                   return_value=([], [])):
                rc, out = _run_main([str(target), "--ai-tool", "claude"])
        self.assertIn("finding=install_wrong_ai_tool", out)

    def test_validator_multiple_markers_blocks(self) -> None:
        with TemporaryDirectory() as td:
            target = Path(td).resolve()
            (target / ".claude").mkdir()
            (target / ".cursor").mkdir()
            rc, out = _run_main([str(target)])
        self.assertEqual(rc, 2, out)
        self.assertIn("finding=multiple_ai_tool_markers", out)
        self.assertIn("status=blocked", out)

    def test_validator_clone_vs_installed_invocation(self) -> None:
        """Run from inside the QPB clone with no target arg ->
        finding=validator_invoked_from_clone, exit 2.

        v1.5.7 089x: bare no-args now prints the purpose banner +
        exits 0 (the universal no-args-safety invariant — every
        bin/*.py is self-describing on no-args). To trigger the
        clone-abort code path we now pass a non-target flag
        (``--ai-tool claude``) so argparse falls through to the
        clone-target-resolution check while still leaving
        ``args.target == None``."""
        proc = subprocess.run(
            [sys.executable, str(_VALIDATOR), "--ai-tool", "claude"],
            cwd=str(_QPB_ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("finding=validator_invoked_from_clone", proc.stdout)
        self.assertIn("status=blocked", proc.stdout)


class DetectInvocationContextTests(unittest.TestCase):
    """Instruction 077b F1 — detect_invocation_context() must return
    'installed' for a bundled tree (was always 'ambiguous' pre-077b
    because the closure bundles bin/SKILL.md/phase_prompts/references
    so the old _CLONE_MARKERS could never discriminate), 'clone' via a
    bundle-absent marker, and 'ambiguous' only as a true fallback."""

    def test_detect_invocation_context_returns_installed_for_bundled_tree(self):
        """The exact case HALT_077 reproduced: a fully-bundled
        <marker>/skills/quality-playbook/ tree must classify as
        'installed', not 'ambiguous'.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-077b —
        BITE EXECUTED during instruction-077b development:
          Mutation: in bin/qpb_validate.py:detect_invocation_context()
          change the installed-ancestor `return "installed", anc` to
          `break` (disabling step 1 — the pre-077b behavior).
          Observed failure (purged __pycache__ first):
            FAIL: test_detect_invocation_context_returns_installed_for_bundled_tree
            AssertionError: 'ambiguous' != 'installed' : bundled tree
            must classify as installed (the exact HALT_077 case)
          Restoration: `return "installed", anc` restored; PASS again.
        """
        with TemporaryDirectory() as td:
            qp = (Path(td) / ".claude" / "skills" / "quality-playbook")
            (qp / "bin").mkdir(parents=True)
            (qp / "phase_prompts").mkdir()
            (qp / "references").mkdir()
            (qp / "SKILL.md").write_text("meta:\n  version: 1.5.7\n")
            fake = qp / "bin" / "qpb_validate.py"
            fake.write_text("# bundled copy\n")
            ctx, root = v.detect_invocation_context(fake)
            self.assertEqual(
                ctx, "installed",
                "bundled tree must classify as installed (the exact "
                "HALT_077 case)")
            self.assertEqual(root.name, "quality-playbook")
            self.assertEqual(root, qp.resolve())

    def test_detect_invocation_context_returns_clone_for_clone_root(self):
        """A clone-shaped tree (bundle-absent marker present, no
        installed ancestor) classifies as 'clone'."""
        for marker in ("setup_repos.sh", ".git", "docs/design",
                       "ai_context"):
            with self.subTest(marker=marker), TemporaryDirectory() as td:
                clone = Path(td) / "QPBclone"
                (clone / "bin").mkdir(parents=True)
                (clone / "SKILL.md").write_text("x")
                mk = clone / marker
                if "/" in marker or marker in ("docs/design",):
                    mk.mkdir(parents=True)
                elif marker in (".git", "ai_context"):
                    mk.mkdir()
                else:
                    mk.write_text("#!/bin/bash\n")
                fake = clone / "bin" / "qpb_validate.py"
                fake.write_text("x")
                ctx, root = v.detect_invocation_context(fake)
                self.assertEqual(ctx, "clone")
                self.assertEqual(root, clone.resolve())

    def test_detect_invocation_context_ambiguous_is_true_fallback(self):
        """No installed ancestor AND no clone-only marker -> the
        'ambiguous' fallback (no longer the always-fired branch)."""
        with TemporaryDirectory() as td:
            bare = Path(td) / "x"
            (bare / "bin").mkdir(parents=True)
            (bare / "SKILL.md").write_text("x")  # bundled-looking, but
            (bare / "phase_prompts").mkdir()      # NOT a clone marker
            fake = bare / "bin" / "qpb_validate.py"
            fake.write_text("x")
            ctx, _ = v.detect_invocation_context(fake)
            self.assertEqual(ctx, "ambiguous")


if __name__ == "__main__":
    unittest.main()
