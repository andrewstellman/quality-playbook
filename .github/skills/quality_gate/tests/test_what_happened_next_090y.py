"""v1.5.7 instruction 090y — verdict block "What happened" +
"What to do next" newcomer-orientation sections.

Motivated by the 2026-05-25 Keto run6 (Copilot/gpt-5.3-codex):
the gate FAILED and an operator reading the output could see
THAT it failed but had no idea what happened or what to do next.
090y adds two plain-English sections at the END of every run's
verdict block, written for someone who downloaded QPB, ran it,
and has no idea what they're looking at.

THE HARD RULE (per spec): the "stronger reasoning model" next-
step appears ONLY for the ``weak_model`` attribution. An honest
coverage/artifact fail (no attribution — the Keto run6 shape)
must NOT tell the user to swap models. Pinned by
test_honest_fail_does_not_recommend_stronger_model with its
mutation bite.

Test surfaces:

  WhatHappenedSectionTests — header present + state-correct
    summary for ✅ solid / ⚠️ shallow / ❌ failed / CLEANUP.
  WhatToDoNextAttributionTests — branching correct on
    attribution: weak_model → stronger-model; incomplete_
    verification → finish-verification; env_failure → fix-env-
    DO-NOT-swap-models; **honest ❌ (no attribution) → fix-the-
    flagged-issues WITHOUT stronger-model line (THE HARD RULE)**.
  NewcomerPhrasingTests — core terms ("gate" / "phases") are
    introduced in plain words.
  LoadBearingPreservationTests — total_line + result_line
    byte-identical, exit_code unchanged with both new sections
    present.
  EveryRunCarriesBothSectionsTests — both sections appear on
    PASS, CLEANUP, and FAIL.
  ScopeGuardTests — SKILL.md / phase prompts untouched.
"""
from __future__ import annotations

import re
import sys
import unittest
from io import StringIO
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
from test_quality_gate import (  # noqa: E402
    minimal_zero_bug_tree,
    add_one_bug,
    quality_gate,
    FixtureBase,
)


_REAL_PY_FUNCTIONAL_TEST = """\
import unittest

class FunctionalTests(unittest.TestCase):
    def test_thing(self):
        self.assertEqual(1 + 1, 2)
"""


def _one_bug_clean_tree() -> dict:
    """A clean ALL-PASS one-bug tree — drives the ✅ solid path."""
    tree = minimal_zero_bug_tree()
    add_one_bug(tree, bug_id="BUG-001")
    tree["quality/test_functional.py"] = _REAL_PY_FUNCTIONAL_TEST
    tree["quality/PROGRESS.md"] = (
        "# Progress\n\nSkill version: 1.4.4\n\n"
        "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
        "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
        "## Terminal Gate Verification\n"
    )
    return tree


def _zero_bug_tree() -> dict:
    """A minimal zero-bug ALL-PASS tree — drives the ⚠️ shallow
    path via _ZERO_BUG_REPOS."""
    tree = minimal_zero_bug_tree()
    tree["quality/test_functional.py"] = _REAL_PY_FUNCTIONAL_TEST
    tree["quality/PROGRESS.md"] = (
        "# Progress\n\nSkill version: 1.4.4\n\n"
        "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
        "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
        "## Terminal Gate Verification\n"
    )
    return tree


def _emit_verdict(*, fail_records, exit_code,
                    warn_records=None, zero_bug_repos=None,
                    run_provenance=None):
    """Helper: invoke _emit_operator_verdict with the given
    state and capture stdout for assertion."""
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        quality_gate._emit_operator_verdict(
            fail_records=fail_records,
            warn_records=warn_records or [],
            zero_bug_repos=zero_bug_repos or [],
            exit_code=exit_code,
            run_provenance=run_provenance,
        )
        return sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout


# ---------------------------------------------------------------------------
# Both sections render on every verdict state.
# ---------------------------------------------------------------------------


class EveryRunCarriesBothSectionsTests(unittest.TestCase):

    def test_solid_pass_carries_both_sections(self) -> None:
        captured = _emit_verdict(fail_records=[], exit_code=0)
        self.assertIn("── What happened ──", captured)
        self.assertIn("── What to do next ──", captured)

    def test_shallow_pass_carries_both_sections(self) -> None:
        captured = _emit_verdict(
            fail_records=[],
            exit_code=0,
            zero_bug_repos=["testproj"],
        )
        self.assertIn("── What happened ──", captured)
        self.assertIn("── What to do next ──", captured)

    def test_failed_run_carries_both_sections(self) -> None:
        captured = _emit_verdict(
            fail_records=[("substantive",
                            "some failure")],
            exit_code=1,
        )
        self.assertIn("── What happened ──", captured)
        self.assertIn("── What to do next ──", captured)

    def test_cleanup_pass_carries_both_sections(self) -> None:
        """CLEANUP path: only record-keeping fails — exit 0 +
        gate result PASSED WITH CLEANUP NEEDED."""
        captured = _emit_verdict(
            fail_records=[("record_keeping",
                            "BUG-NNN record gap")],
            exit_code=0,
        )
        self.assertIn("── What happened ──", captured)
        self.assertIn("── What to do next ──", captured)


# ---------------------------------------------------------------------------
# "What happened" — state-correct summary.
# ---------------------------------------------------------------------------


class WhatHappenedSectionTests(unittest.TestCase):

    def test_solid_summary(self) -> None:
        captured = _emit_verdict(fail_records=[], exit_code=0)
        # The summary line for ✅ solid carries "passed cleanly".
        self.assertIn("passed cleanly", captured)

    def test_solid_summary_with_bug_count(self) -> None:
        """Solid + verified bugs → enriched summary with the
        gate-counted issue count."""
        captured = _emit_verdict(
            fail_records=[], exit_code=0,
            run_provenance=[{
                "repo": "x", "runner_detected": "claude-code",
                "model_self_reported": "opus",
                "bug_count_gate": 3,
                "bug_count_self_reported": 3,
                "provenance_mismatch": False,
            }],
        )
        self.assertIn("verified 3 issues", captured)

    def test_shallow_summary_names_why(self) -> None:
        captured = _emit_verdict(
            fail_records=[], exit_code=0,
            zero_bug_repos=["testproj"],
        )
        # "What happened" shallow line: "didn't dig deep" + a
        # reason (zero bugs).
        self.assertIn("didn't dig deep", captured)
        self.assertIn("found no issues", captured)

    def test_failed_summary_keto_run6_shape(self) -> None:
        """Keto run6 motivating fixture: ❌ failed with no
        attribution → the plain-English reason names "quality
        issues that need fixing", NOT model-blame."""
        captured = _emit_verdict(
            fail_records=[
                ("substantive",
                 "PROGRESS.md missing Terminal Gate section"),
            ],
            exit_code=1,
        )
        self.assertIn("did not pass the checkpoint", captured)
        self.assertIn("quality issues", captured)

    def test_failed_summary_weak_model(self) -> None:
        """Weak-model attribution → "cut corners" wording."""
        captured = _emit_verdict(
            fail_records=[
                ("substantive",
                 "quality/test_functional.go: ALL 1 test "
                 "function(s) are trivial / no-assertion "
                 "stubs"),
            ],
            exit_code=1,
        )
        self.assertIn("cut corners", captured)

    def test_failed_summary_bugs_unverified(self) -> None:
        """incomplete_verification attribution → "found issues
        but didn't verify them" wording."""
        captured = _emit_verdict(
            fail_records=[
                ("substantive",
                 "tdd-results.json missing (3 bugs require it)"),
            ],
            exit_code=1,
        )
        self.assertIn(
            "found issues but didn't verify them",
            captured,
        )

    def test_cleanup_summary_reads_as_pass_not_fail(self) -> None:
        """CLEANUP path: instruction 090y Task A — must read as
        a pass, not a fail. 'It passed, with some bookkeeping
        gaps to tidy up'."""
        captured = _emit_verdict(
            fail_records=[("record_keeping", "rk gap")],
            exit_code=0,
        )
        # NOT "did not pass" — the cleanup must read as pass.
        self.assertNotIn("did not pass", captured)
        # And carries the bookkeeping framing.
        self.assertIn("bookkeeping gaps", captured)
        self.assertIn("passed the checkpoint", captured)


# ---------------------------------------------------------------------------
# "What to do next" — THE HARD RULE: attribution branching.
# ---------------------------------------------------------------------------


class WhatToDoNextAttributionTests(unittest.TestCase):

    def test_weak_model_gets_stronger_model_advice(self) -> None:
        """❌ weak_model → "re-run with a stronger reasoning
        model" — the only ❌ path that surfaces this advice."""
        captured = _emit_verdict(
            fail_records=[
                ("substantive",
                 "quality/test_functional.go: ALL 1 test "
                 "function(s) are trivial / no-assertion "
                 "stubs"),
            ],
            exit_code=1,
        )
        # Both sections present.
        self.assertIn("── What to do next ──", captured)
        # The stronger-model advice fires.
        self.assertIn("stronger reasoning model", captured)
        self.assertIn("cut corners", captured)

    def test_incomplete_verification_gets_finish_verification_advice(
            self) -> None:
        """❌ incomplete_verification → "re-run to complete the
        test step, or treat them as candidates to check by
        hand"."""
        captured = _emit_verdict(
            fail_records=[
                ("substantive",
                 "tdd-results.json missing (3 bugs require it)"),
            ],
            exit_code=1,
        )
        self.assertIn("complete the test step", captured)
        self.assertIn("check by hand", captured)
        # And the stronger-model advice MUST NOT appear here —
        # bugs_unverified is an incomplete run, not cut-corners.
        # (This was the load-bearing 090x HARD RULE; 090y must
        # preserve it.)
        # The "What to do next" section in 090y must not say to
        # swap models; the previous 090v section also does not
        # (because attribution=incomplete_verification routes
        # through bugs_unverified, not weak_model). Verified by
        # the bugs-unverified test suite already.

    def test_env_failure_DOES_NOT_recommend_stronger_model(
            self) -> None:
        """Pure environment failure → fix the environment, NEVER
        swap models. Pinned by both the 090v hard rule AND
        re-pinned here for the 090y newcomer-advice surface."""
        captured = _emit_verdict(
            fail_records=[
                ("substantive",
                 "BUG-001.red.log: tagged RED but body is a "
                 "setup/dependency/build/collection failure"),
            ],
            exit_code=1,
        )
        # The What-to-do-next env-failure path tells the user
        # explicitly NOT to swap models.
        self.assertIn("Do NOT swap models", captured)
        # And the "stronger reasoning model" advice does NOT
        # appear in the What-to-do-next section. (The 090v
        # Attribution: env section earlier in the block ALSO
        # avoids it — defense in depth.)
        # We can't simply assert "stronger reasoning model" is
        # absent (the 090v attribution section might still say
        # "model is not the problem"), so we narrow to the
        # what-to-do-next region.
        what_to_do = captured.split("── What to do next ──", 1)[1]
        self.assertNotIn("stronger reasoning model", what_to_do)

    def test_honest_fail_does_not_recommend_stronger_model(
            self) -> None:
        """**THE HARD RULE** (instruction 090y Task B "Branch
        correctly"): an honest coverage/artifact fail — no
        weak_model attribution, no env failure, no
        bugs_unverified — must surface "fix the flagged issues
        and re-run" WITHOUT the stronger-model line.

        This is the 2026-05-25 Keto run6 motivating shape: the
        gate FAILED on legitimate coverage/artifact gaps, and
        telling the operator to swap models would be actively
        wrong advice.

        Mutation bite: route the honest-fail path into the
        weak-model branch → the stronger-model line wrongly
        appears → this test FAILs.
        """
        captured = _emit_verdict(
            fail_records=[
                ("substantive",
                 "PROGRESS.md missing Terminal Gate section"),
                ("substantive",
                 "quality/COMPLETENESS_REPORT.md missing"),
            ],
            exit_code=1,
        )
        # Both sections present.
        self.assertIn("── What to do next ──", captured)
        # Per-section narrowing: in the "What to do next" region
        # specifically, the stronger-model line MUST NOT appear.
        what_to_do = captured.split("── What to do next ──", 1)[1]
        self.assertNotIn(
            "stronger reasoning model", what_to_do,
            "v1.5.7 090y HARD RULE: an honest coverage/artifact "
            "fail (no weak_model attribution) MUST NOT tell the "
            "user to swap models. The 2026-05-25 Keto run6 "
            "shape — telling that operator to use a stronger "
            "model would be actively-wrong advice. Got the "
            f"what-to-do section:\n{what_to_do}",
        )
        # The fix-the-flagged-issues line IS present.
        self.assertIn("flagged", what_to_do)
        self.assertIn("re-run", what_to_do)

    def test_honest_fail_with_found_bugs_points_at_bugs_md(
            self) -> None:
        """Instruction 090y: "if real bugs were found, 'the
        issues it did find are in quality/BUGS.md.'"""
        captured = _emit_verdict(
            fail_records=[
                ("substantive",
                 "PROGRESS.md missing Terminal Gate section"),
            ],
            exit_code=1,
            run_provenance=[{
                "repo": "x", "runner_detected": "claude-code",
                "model_self_reported": "opus",
                "bug_count_gate": 2,
                "bug_count_self_reported": None,
                "provenance_mismatch": False,
            }],
        )
        what_to_do = captured.split("── What to do next ──", 1)[1]
        self.assertIn("quality/BUGS.md", what_to_do)

    def test_solid_pass_points_at_bugs_and_patches(self) -> None:
        captured = _emit_verdict(fail_records=[], exit_code=0)
        what_to_do = captured.split("── What to do next ──", 1)[1]
        self.assertIn("quality/BUGS.md", what_to_do)
        self.assertIn("quality/patches/", what_to_do)
        self.assertIn("quality/results/", what_to_do)

    def test_shallow_pass_points_at_exploration_and_bugs(
            self) -> None:
        captured = _emit_verdict(
            fail_records=[],
            exit_code=0,
            zero_bug_repos=["testproj"],
        )
        what_to_do = captured.split("── What to do next ──", 1)[1]
        self.assertIn("quality/EXPLORATION.md", what_to_do)
        self.assertIn("quality/BUGS.md", what_to_do)
        # Shallow path "consider stronger model" — note this is
        # advisory ("consider"), not the directive ❌ weak_model
        # gets.
        self.assertIn("stronger reasoning model", what_to_do)
        self.assertIn("Consider", what_to_do)

    def test_cleanup_pass_points_at_why_it_failed(self) -> None:
        captured = _emit_verdict(
            fail_records=[("record_keeping", "rk gap")],
            exit_code=0,
        )
        what_to_do = captured.split("── What to do next ──", 1)[1]
        self.assertIn("Mostly good", what_to_do)
        self.assertIn("Why it failed", what_to_do)
        # CLEANUP must not say to swap models either.
        self.assertNotIn("stronger reasoning model", what_to_do)


# ---------------------------------------------------------------------------
# Newcomer phrasing — core terms introduced in plain words.
# ---------------------------------------------------------------------------


class NewcomerPhrasingTests(unittest.TestCase):

    def test_gate_introduced_plainly(self) -> None:
        """"The gate is the final quality checkpoint…" —
        introducing the term, not just using it."""
        captured = _emit_verdict(fail_records=[], exit_code=0)
        self.assertIn(
            "The gate is the final quality checkpoint",
            captured,
        )

    def test_phases_introduced_plainly(self) -> None:
        captured = _emit_verdict(fail_records=[], exit_code=0)
        self.assertIn("six phases", captured)
        # Plain enumeration of what each phase does, not
        # jargon-only names.
        self.assertIn("exploring", captured)
        self.assertIn("verifying findings", captured)


# ---------------------------------------------------------------------------
# Load-bearing preservation — total_line + result_line +
# exit_code unchanged with the new sections present.
# ---------------------------------------------------------------------------


class LoadBearingPreservationTests(FixtureBase):

    def test_total_line_byte_identical(self) -> None:
        self.write(_one_bug_clean_tree())
        stdout, _code = self.gate()
        self.assertRegex(
            stdout,
            re.compile(r"^Total: \d+ FAIL, \d+ WARN$",
                       re.MULTILINE),
        )

    def test_result_line_byte_identical_on_pass(self) -> None:
        self.write(_one_bug_clean_tree())
        stdout, code = self.gate()
        self.assertEqual(code, 0)
        self.assertRegex(
            stdout,
            re.compile(r"^RESULT: GATE PASSED$", re.MULTILINE),
        )

    def test_exit_code_unchanged_with_new_sections(self) -> None:
        """The 090y additions are presentation-only — the gate's
        pass/fail semantics are unchanged."""
        self.write(_one_bug_clean_tree())
        _stdout, code = self.gate()
        self.assertEqual(code, 0)

    def test_full_gate_run_carries_both_new_sections(self) -> None:
        """End-to-end: a full-gate run on a clean tree emits the
        "── What happened ──" + "── What to do next ──"
        headers."""
        self.write(_one_bug_clean_tree())
        stdout, _code = self.gate()
        self.assertIn("── What happened ──", stdout)
        self.assertIn("── What to do next ──", stdout)


# ---------------------------------------------------------------------------
# Scope guards.
# ---------------------------------------------------------------------------


class ScopeGuard090yTests(unittest.TestCase):

    def test_skill_md_not_touched_by_090y(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        text = (repo_root / "skills" / "quality-playbook" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "090y", text,
            "SKILL.md must not carry 090y anchors — gate output only.",
        )

    def test_phase_prompts_not_touched_by_090y(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        phase_dir = repo_root / "phase_prompts"
        for phase_file in sorted(phase_dir.glob("phase*.md")):
            text = phase_file.read_text(encoding="utf-8")
            self.assertNotIn(
                "090y", text,
                f"{phase_file.name} must not carry 090y anchors.",
            )


if __name__ == "__main__":
    unittest.main()
