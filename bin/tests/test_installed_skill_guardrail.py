"""v1.5.7 instruction 054 (A-10b): the installed-skill SHA guardrail.

`validate_no_source_edits` is git-based and SILENTLY passes when the
target is not a git repo — the common `setup_repos.sh` benchmark
case — so an agent that edits an installed skill file mid-run is not
caught. The gson opus-4.6 Mode-A run (2026-05-16) is the live
witness: the agent edited
`target/.claude/skills/quality-playbook/quality_gate.py:1003`
mid-run and no abort fired.

The additive guardrail: `run_state_lib.snapshot_installed_skill_shas`
hashes the installed skill tree; `_capture_installed_skill_baseline`
writes the run-start snapshot to
`quality/.installed_skill_baseline.json`; `_finalize_iteration`
re-snapshots at every phase/iteration boundary and folds any drift
into the existing `source_edit_violations` abort path (zero schema
impact). These tests drive `_finalize_iteration` directly on
synthetic targets — it degrades gracefully when no real
`quality_gate.py` gate is present (the "gate not found" branch) and
still reaches the guardrail block, so the wired behavior is
exercised end-to-end without standing up a full gate subprocess.
"""

from __future__ import annotations

import contextlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bin import run_playbook as rp
from bin import run_state_lib
from bin.run_state_lib import (
    diff_installed_skill_shas,
    snapshot_installed_skill_shas,
)

_BASELINE_REL = "quality/.installed_skill_baseline.json"


@contextlib.contextmanager
def _install_skill_unimportable():
    """Make `bin.install_skill` (and bare `install_skill`)
    unimportable for the duration — the instruction-053 technique:
    `sys.modules[name] = None` is insufficient on its own because
    `from bin import install_skill` resolves via the `install_skill`
    attribute already bound on the `bin` package object, so we also
    delattr+restore that attribute.

    This simulates a real `setup_repos.sh`-DEPLOYED target where
    `install_skill.py` is NOT in the bundled bin/ closure (per
    `install_skill._bundle_files`). The unittest process otherwise
    runs from the QPB source clone where the import always succeeds —
    that was the false confidence codex flagged in the 054 review.
    """
    import bin as _bin_pkg

    had_attr = hasattr(_bin_pkg, "install_skill")
    saved_attr = getattr(_bin_pkg, "install_skill", None)
    if had_attr:
        delattr(_bin_pkg, "install_skill")
    try:
        with mock.patch.dict(
            sys.modules,
            {"bin.install_skill": None, "install_skill": None},
        ):
            yield
    finally:
        if had_attr:
            setattr(_bin_pkg, "install_skill", saved_attr)


def _marker_target(root: Path) -> Path:
    """install_skill.py layout: QPB skill tree under
    .claude/skills/quality-playbook/ (the gson reproduction layout)."""
    (root / "quality").mkdir(parents=True, exist_ok=True)
    skill = root / ".claude" / "skills" / "quality-playbook"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "quality_gate.py").write_text(
        "# installed gate v1\n", encoding="utf-8"
    )
    (skill / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    return root


def _flat_setup_repos_target(root: Path) -> Path:
    """setup_repos.sh flat layout: .github/skills/SKILL.md + the
    bundled bin/ closure at the target root."""
    (root / "quality").mkdir(parents=True, exist_ok=True)
    gh = root / ".github" / "skills"
    gh.mkdir(parents=True, exist_ok=True)
    (gh / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "quality_playbook.py").write_text(
        "# bundled closure v1\n", encoding="utf-8"
    )
    return root


class InstalledSkillGuardrailTests(unittest.TestCase):

    def test_installed_skill_sha_baseline_captured_at_run_start(self) -> None:
        """_capture_installed_skill_baseline writes the run-start
        snapshot; the baseline contains the installed file's SHA."""
        with TemporaryDirectory() as t:
            root = _marker_target(Path(t))
            log = root / "pb.log"
            log.write_text("", encoding="utf-8")
            rp._capture_installed_skill_baseline(root, log)
            baseline_path = root / _BASELINE_REL
            self.assertTrue(baseline_path.is_file())
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            self.assertIn(
                ".claude/skills/quality-playbook/quality_gate.py", baseline
            )
            self.assertEqual(
                baseline,
                snapshot_installed_skill_shas(root),
                "baseline must equal a fresh snapshot of the unmutated "
                "install tree",
            )

    def test_installed_skill_mutation_aborts_at_phase_boundary(self) -> None:
        """Capture baseline → mutate an installed skill file → invoke
        the phase-boundary verifier (_finalize_iteration); the run
        aborts and the changed path is recorded.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-054
        A-10b:
          Mutation: in bin/run_playbook.py:_finalize_iteration,
          comment out / neutralize the installed-skill guardrail
          block (the
          `from bin.run_state_lib import snapshot_installed_skill_shas,
          diff_installed_skill_shas` … `source_edit_violations =
          list(...) + [...]` block co-located with the
          validate_no_source_edits block).
          Expected failure: THIS test fails — `_finalize_iteration`
          returns "completed"/gate-status instead of "aborted"
          (no abort fires) and the gate log lacks the
          "installed-skill guardrail" section, so
          `assertEqual(status, "aborted")` fails.
          Restoration: re-enable the block; passes.
          Bite executed during instruction-054 development;
          PASS→FAIL→PASS confirmed (__pycache__ purged between
          mutate and restore).
        """
        with TemporaryDirectory() as t:
            root = _marker_target(Path(t))
            log = root / "pb.log"
            log.write_text("", encoding="utf-8")
            rp._capture_installed_skill_baseline(root, log)

            skill_file = (
                root / ".claude" / "skills" / "quality-playbook"
                / "quality_gate.py"
            )
            skill_file.write_text("# MUTATED mid-run\n", encoding="utf-8")

            status = rp._finalize_iteration(
                root, label="post-phase-6", log_file=log
            )
            self.assertEqual(status, "aborted")
            gate_log = root / "quality" / "results" / "quality-gate.log"
            self.assertTrue(gate_log.is_file())
            gate_log_text = gate_log.read_text(encoding="utf-8")
            self.assertIn("installed-skill guardrail", gate_log_text)
            self.assertIn(
                ".claude/skills/quality-playbook/quality_gate.py",
                gate_log_text,
            )

    def test_non_git_target_guardrail_still_works(self) -> None:
        """The synthetic target has NO .git dir (simulates a
        setup_repos.sh install). git-based validate_no_source_edits
        would silently pass; the SHA guardrail still catches the
        mutation and aborts."""
        with TemporaryDirectory() as t:
            root = _marker_target(Path(t))
            self.assertFalse((root / ".git").exists())
            log = root / "pb.log"
            log.write_text("", encoding="utf-8")
            rp._capture_installed_skill_baseline(root, log)
            (
                root / ".claude" / "skills" / "quality-playbook"
                / "SKILL.md"
            ).write_text("# tampered\n", encoding="utf-8")
            status = rp._finalize_iteration(
                root, label="post-singlepass", log_file=log
            )
            self.assertEqual(status, "aborted")

    def test_setup_repos_layout_guardrail(self) -> None:
        """Flat setup_repos.sh layout (.github/skills/SKILL.md + root
        bin/): mutating target/bin/quality_playbook.py is caught —
        EVEN WHEN `bin.install_skill` is unimportable.

        This test runs with `bin.install_skill` made unimportable to
        simulate the deployed `setup_repos.sh` target where
        `install_skill.py` is NOT in the bundled bin/ closure. The
        snapshot must succeed via the hardcoded
        `_FLAT_LAYOUT_BUNDLED_BIN_FILES` closure list without falling
        back to an empty bin/ snapshot (the v1.5.7 instruction-055 F1
        fix; the gap codex flagged in the 054 review).

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-055
        F1:
          Mutation: revert run_state_lib.snapshot_installed_skill_shas'
          flat-layout branch to enumerate bin/ via
          `from bin import install_skill;
          install_skill._bundle_files(target)` instead of the
          hardcoded `_FLAT_LAYOUT_BUNDLED_BIN_FILES` list.
          Expected failure: with install_skill unimportable (this
          test's context), the flat snapshot omits target/bin/*.py,
          so `assertIn("bin/quality_playbook.py", baseline)` fails
          (and the subsequent abort/diff assertions would too) —
          the mid-run bin/ mutation evades the guardrail, exactly
          the deployed-reality blind spot.
          Restoration: re-apply the hardcoded-closure flat branch;
          passes.
          Bite executed during instruction-055 development;
          PASS→FAIL→PASS confirmed (__pycache__ purged between
          mutate and restore).
        """
        with TemporaryDirectory() as t, _install_skill_unimportable():
            root = _flat_setup_repos_target(Path(t))
            log = root / "pb.log"
            log.write_text("", encoding="utf-8")
            rp._capture_installed_skill_baseline(root, log)
            baseline = json.loads(
                (root / _BASELINE_REL).read_text(encoding="utf-8")
            )
            # The flat footprint covers .github/skills/ wholesale +
            # the hardcoded bundled bin/ closure (no install_skill).
            self.assertIn(".github/skills/SKILL.md", baseline)
            self.assertIn("bin/quality_playbook.py", baseline)

            (root / "bin" / "quality_playbook.py").write_text(
                "# closure TAMPERED\n", encoding="utf-8"
            )
            status = rp._finalize_iteration(
                root, label="post-singlepass", log_file=log
            )
            self.assertEqual(status, "aborted")
            self.assertEqual(
                diff_installed_skill_shas(
                    baseline, snapshot_installed_skill_shas(root)
                ),
                ["bin/quality_playbook.py"],
            )

    def test_flat_layout_closure_matches_bundle_manifest(self) -> None:
        """Pin `_FLAT_LAYOUT_BUNDLED_BIN_FILES` against the canonical
        `install_skill._bundle_files()` bin/ dest basenames so a
        future bundle change that adds/removes a bin/ closure module
        without updating the hardcoded constant fails the suite
        (drift guard for the instruction-055 F1 hardcoded list).

        This test runs from the QPB clone (install_skill IS
        importable here) — that is correct: the pin must read the
        canonical source. The DEPLOYED-reality behavior is covered
        by test_setup_repos_layout_guardrail (install_skill
        poisoned)."""
        from bin import install_skill

        qpb_root = Path(__file__).resolve().parents[2]
        bundled_bin = {
            Path(dest).name
            for _src, dest in install_skill._bundle_files(qpb_root)
            if Path(dest).parent.as_posix() == "bin"
        }
        self.assertEqual(
            bundled_bin,
            set(run_state_lib._FLAT_LAYOUT_BUNDLED_BIN_FILES),
            "run_state_lib._FLAT_LAYOUT_BUNDLED_BIN_FILES drifted from "
            "install_skill._bundle_files()'s bin/ closure; update the "
            "hardcoded constant to match.",
        )

    def test_run_one_iterations_captures_baseline_at_run_start(self) -> None:
        """v1.5.7 instruction 055 F2: the STANDALONE --iterations
        dispatch (run_one_iterations WITHOUT phases_already_ran)
        captures the installed-skill baseline at run-start — the
        bypass codex flagged in the 054 review (run_one_phased /
        run_one_singlepass already captured; the standalone path did
        not, so _finalize_iteration's SHA check no-op'd for
        standalone `--iterations` runs).

        The capture is placed BEFORE the no-EXPLORATION.md early
        return, so a target without quality/EXPLORATION.md SKIPs
        (rc=1) yet still proves the baseline was written at run-start;
        a subsequent installed-skill mutation + _finalize_iteration
        proves the standalone-captured baseline is usable by the
        guardrail.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-055
        F2:
          Mutation: comment out / remove the
          `_capture_installed_skill_baseline(repo_dir, log_file)`
          call added to run_one_iterations' standalone (non
          phases_already_ran) branch in bin/run_playbook.py.
          Expected failure: THIS test fails at
          `assertTrue(baseline_path.is_file())` — the standalone
          dispatch never writes quality/.installed_skill_baseline.json,
          so the SHA guardrail has no baseline and the later abort
          assertion would also fail (the standalone blind spot).
          Restoration: re-add the call; passes.
          Bite executed during instruction-055 development;
          PASS→FAIL→PASS confirmed (__pycache__ purged between
          mutate and restore).
        """
        with TemporaryDirectory() as t:
            root = _marker_target(Path(t))  # no quality/EXPLORATION.md
            args = rp.parse_args(
                [str(root), "--model", "sonnet", "--strategy", "gap"]
            )
            # Standalone dispatch (phases_already_ran defaults False).
            rc = rp.run_one_iterations(
                root, ["gap"], args, "20260516T000000Z"
            )
            self.assertEqual(rc, 1)  # SKIP: no quality/EXPLORATION.md
            baseline_path = root / _BASELINE_REL
            self.assertTrue(
                baseline_path.is_file(),
                "standalone run_one_iterations must capture the "
                "installed-skill baseline at run-start (before the "
                "no-EXPLORATION.md SKIP)",
            )
            baseline = json.loads(
                baseline_path.read_text(encoding="utf-8")
            )
            self.assertIn(
                ".claude/skills/quality-playbook/quality_gate.py",
                baseline,
            )

            # The standalone-captured baseline is usable: a mid-run
            # mutation is caught at the _finalize_iteration boundary.
            log = root / "pb.log"
            log.write_text("", encoding="utf-8")
            (
                root / ".claude" / "skills" / "quality-playbook"
                / "quality_gate.py"
            ).write_text("# MUTATED\n", encoding="utf-8")
            status = rp._finalize_iteration(
                root, label="post-gap", log_file=log
            )
            self.assertEqual(status, "aborted")


if __name__ == "__main__":
    unittest.main()
