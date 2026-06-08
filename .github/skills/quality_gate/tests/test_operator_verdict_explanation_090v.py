"""v1.5.7 instruction 090v — gate operator-facing verdict-explanation
layer (the v1.5.7 slice of the v1.6.x verdict-explanation track).

Motivated by the 2026-05-23/24/25 Mode-A channel-install run-series
(OpenFGA / Keto / NATS). Canonical examples:

  * Keto run5 (gpt-5.3-codex via Copilot, copilot channel) — the
    weak-model-artifact fixture: 6 all-trivial test functions
    (090s FAIL) + 3 claimed-GREEN-without-running TDD receipts
    (090p overclaim) → `Total: 25 FAIL → GATE FAILED`. Correct
    verdict-layer output: ❌ GATE FAILED + the weak-model
    attribution ("re-run with a stronger reasoning model").
  * NATS run2 (gpt-5.2/low, npm channel) — the shallow-pass
    fixture: a zero-bug, no-op-test PASS that is correct-by-
    semantics but unreadable. Correct output: ⚠️ GATE PASSED —
    but this run looks shallow.

The layer is purely additive — printed AFTER the load-bearing
``total_line`` / ``result_line`` lines. It NEVER changes
``exit_code`` / pass-fail semantics.

Spec: ``docs/design/QPB_v1.6.x_Verdict_Explanation_Proposal.md``
(the 1.5.7 slice — framework + high-frequency content; v1.6.x
expansion E1–E6 explicitly out of scope).

Test surfaces:

  LeadVerdictLineTests — three states (✅ solid / ⚠️ shallow / ❌
    failed) for clean / zero-bug / failing runs.
  ThreeBucketAttributionTests — the load-bearing classification
    test, with the mutation bite for the hard rule (a setup-
    failure-red run must NOT get the stronger-model line).
  LoadBearingPreservationTests — total_line + result_line +
    exit_code are byte-identical / numerically unchanged after
    the 090v layer is in place; the standalone 090s `NOTE:` is
    folded into the new block (not duplicated).
  BenignWarnDemotionTests — allowlisted legacy-manifest WARNs
    collapse into an "operational notices" summary; non-
    allowlisted WARNs stay prominent.
  GenericFallbackTests — an uncovered FAIL code still gets a
    clear generic narration.
  UnitClassifierTests — direct tests of the substring
    classifier helpers.
  ScopeGuardTests — SKILL.md / phase prompts untouched.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
from test_quality_gate import (  # noqa: E402
    minimal_zero_bug_tree,
    add_one_bug,
    quality_gate,
    FixtureBase,
)


_RUN4_EMPTY_GO_TEST = """\
package quality

import "testing"

func TestFunctionalBaseline(t *testing.T) {
}
"""

# A real Python functional test with an actual assertion — used so
# the 090s `no test functions found` / `all-trivial` checks PASS,
# isolating each test's intended shallow / failing / clean signal.
_REAL_PY_FUNCTIONAL_TEST = """\
import unittest

class FunctionalTests(unittest.TestCase):
    def test_thing(self):
        result = 1 + 1
        self.assertEqual(result, 2)
"""


def _zero_bug_tree() -> dict:
    """A minimal zero-bug ALL-PASS tree (no 090s WARN, no FAIL,
    no overclaim, no setup failure). The functional test carries
    a real assertion so only the zero-bug signal fires — drives
    the ⚠️ shallow lead via ``_ZERO_BUG_REPOS`` alone."""
    tree = minimal_zero_bug_tree()
    tree["quality/test_functional.py"] = _REAL_PY_FUNCTIONAL_TEST
    tree["quality/PROGRESS.md"] = (
        "# Progress\n\nSkill version: 1.4.4\n\n"
        "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
        "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
        "## Terminal Gate Verification\n"
    )
    return tree


def _one_bug_clean_tree() -> dict:
    """A clean ALL-PASS tree with one confirmed bug — the ✅ solid
    path. Replaces the default 090s-WARNing test_functional.py
    with one that has a real assertion."""
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


def _hollow_run4_tree() -> dict:
    """A zero-bug tree with the run4 hollow Go functional test in
    place — triggers 090s FAIL → ❌ GATE FAILED with the weak-
    model attribution + stronger-model line. Follows the same
    Go-language switch the 090s tests use (replace main.py with
    main.go so the language detector picks Go, drop the .py
    functional test, add the Go one + Go regression test pair)."""
    tree = _zero_bug_tree()
    # Swap to Go language detection.
    tree["main.go"] = "package main\nfunc main() {}\n"
    tree.pop("main.py", None)
    # Replace functional test with the run4 empty Go shape.
    tree.pop("quality/test_functional.py", None)
    tree["quality/test_functional.go"] = _RUN4_EMPTY_GO_TEST
    # Go regression test pair so the test-file-extension check
    # doesn't fire on a language mismatch.
    tree["quality/test_regression.go"] = "package quality\n"
    tree["quality/test_regression_test.go"] = "package quality\n"
    return tree


# ---------------------------------------------------------------------------
# Lead verdict line — ✅ solid / ⚠️ shallow / ❌ failed.
# ---------------------------------------------------------------------------


class LeadVerdictLineTests(FixtureBase):

    def test_clean_one_bug_run_renders_solid_lead(self) -> None:
        """A confirmed-bug PASS with no hollow tells renders the
        ✅ solid lead line.

        Mutation bite: invert the shallow-pass condition (treat all
        passes as shallow) → the ✅ lead disappears, this test FAILs.
        """
        self.write(_one_bug_clean_tree())
        stdout, code = self.gate()
        self.assertEqual(code, 0, stdout)
        self.assertIn("✅ GATE PASSED — this run looks solid", stdout)
        self.assertNotIn("⚠️ GATE PASSED — but this run looks shallow",
                         stdout)
        self.assertNotIn("❌ GATE FAILED", stdout)

    def test_zero_bug_run_renders_shallow_lead(self) -> None:
        """A zero-bug PASS renders the ⚠️ shallow lead line.

        Mutation bite: drop ``_ZERO_BUG_REPOS`` from the
        ``is_shallow_pass`` condition → the lead drops to ✅ on
        the canonical shallow shape, this test FAILs.
        """
        self.write(_zero_bug_tree())
        stdout, code = self.gate()
        self.assertEqual(code, 0, stdout)
        self.assertIn(
            "⚠️ GATE PASSED — but this run looks shallow", stdout,
            f"v1.5.7 090v: a zero-bug PASS must render the ⚠️ "
            f"shallow lead. Got stdout:\n{stdout}",
        )
        self.assertNotIn("✅ GATE PASSED — this run looks solid",
                         stdout)
        self.assertNotIn("❌ GATE FAILED", stdout)

    def test_failing_run_renders_failed_lead(self) -> None:
        """A run with any FAIL renders the ❌ failed lead line.

        Mutation bite: invert the exit_code check → the ❌ lead
        disappears on a FAIL, this test FAILs.
        """
        self.write(_hollow_run4_tree())
        stdout, code = self.gate()
        self.assertNotEqual(code, 0, stdout)
        self.assertIn("❌ GATE FAILED", stdout)
        self.assertNotIn("✅ GATE PASSED", stdout)
        self.assertNotIn("⚠️ GATE PASSED", stdout)


# ---------------------------------------------------------------------------
# Three-bucket attribution — the load-bearing hard rule.
# ---------------------------------------------------------------------------


class ThreeBucketAttributionTests(FixtureBase):

    def test_hollow_run_gets_weak_model_with_stronger_model_recommendation(
            self) -> None:
        """The run4 hollow shape (090s FAIL) renders the weak-model
        attribution AND the 'try a stronger reasoning model'
        recommendation.

        This is the Keto-run5 fixture from the spec: the gate must
        turn the 25-FAIL wall into the plain-English
        'cut corners — re-run with a stronger reasoning model'
        sentence.

        Mutation bite: route the 090s FAIL into the environment
        bucket → the stronger-model line disappears, this test
        FAILs.
        """
        self.write(_hollow_run4_tree())
        stdout, code = self.gate()
        self.assertNotEqual(code, 0)
        self.assertIn("Attribution: weak-model artifact", stdout)
        self.assertIn("cut corners", stdout)
        self.assertIn(
            "stronger reasoning model", stdout,
            "v1.5.7 090v: a hollow-tell FAIL must surface the "
            "'try a stronger reasoning model' recommendation in "
            "the weak-model bucket.",
        )

    def test_setup_failure_red_does_NOT_get_stronger_model_recommendation(
            self) -> None:
        """The 090p setup-failure-RED shape renders the environment
        attribution WITHOUT the stronger-model line.

        **THE HARD RULE** (per spec §1.5.7 "Bucket precedence"): the
        'try a stronger reasoning model' recommendation is gated
        specifically on a weak-model/fabrication signal. A pure
        environment-failure run (setup-failure reds only, no
        fabrication signal) gets the environment message and
        NEVER the stronger-model line. Mis-attribution gives
        actively harmful advice (telling the operator to swap
        models when their build broke).

        Mutation bite: drop the env-failure gate on the
        stronger-model line (e.g. emit it unconditionally on any
        FAIL) → this test FAILs because the stronger-model line
        wrongly appears on a pure setup-failure run.
        """
        # Directly exercise the layer with a synthetic setup-
        # failure FAIL record so the test doesn't depend on the
        # full 090p check-emit pipeline (which requires a real
        # red-phase log fixture). We pass the FAIL message
        # verbatim — _classify_fail substring-matches it.
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            quality_gate._emit_operator_verdict(
                fail_records=[(
                    "substantive",
                    "BUG-001.red.log: tagged RED but body is a "
                    "setup/dependency/build/collection failure",
                )],
                warn_records=[],
                zero_bug_repos=[],
                exit_code=1,
            )
            captured = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        # The environment bucket must fire.
        self.assertIn("Attribution: environment / setup problem",
                      captured)
        # And the stronger-model line MUST NOT appear (the load-
        # bearing hard rule).
        self.assertNotIn(
            "stronger reasoning model", captured,
            "v1.5.7 090v HARD RULE: a pure environment-failure "
            "run must NEVER surface the 'try a stronger "
            "reasoning model' recommendation — that mis-"
            "attribution gives actively harmful advice. "
            f"Captured:\n{captured}",
        )
        # And the weak-model bucket MUST NOT fire.
        self.assertNotIn(
            "Attribution: weak-model artifact", captured,
            "v1.5.7 090v: a setup-failure-only run must NOT "
            "trigger the weak-model bucket.",
        )

    def test_clean_run_gets_neither_bucket_message(self) -> None:
        """A clean pass with no shallow signal renders neither
        the weak-model nor the environment-failure bucket.

        Mutation bite: ungate the env-failure attribution print
        (always emit) → this test FAILs because the env message
        appears on a clean run.
        """
        self.write(_one_bug_clean_tree())
        stdout, _code = self.gate()
        self.assertNotIn("Attribution: weak-model artifact", stdout)
        self.assertNotIn("Attribution: environment / setup problem",
                         stdout)
        # And the "real PASS" residual line fires instead.
        self.assertIn("verdict reads as a real PASS", stdout)

    def test_mixed_hollow_and_setup_failure_gets_BOTH_buckets(
            self) -> None:
        """Buckets are not mutually exclusive — a run that carries
        BOTH a hollow tell AND a setup-failure red fires BOTH
        attribution messages. The stronger-model recommendation
        still rides on the weak-model bucket only.
        """
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            quality_gate._emit_operator_verdict(
                fail_records=[
                    ("substantive",
                     "quality/test_functional.go: ALL 1 test "
                     "function(s) are trivial / no-assertion "
                     "stubs"),
                    ("substantive",
                     "BUG-002.red.log: tagged RED but body is a "
                     "setup/dependency/build/collection failure"),
                ],
                warn_records=[],
                zero_bug_repos=[],
                exit_code=1,
            )
            captured = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn("Attribution: weak-model artifact", captured)
        self.assertIn("Attribution: environment / setup problem",
                      captured)
        self.assertIn("stronger reasoning model", captured)


# ---------------------------------------------------------------------------
# Load-bearing preservation — total_line + result_line + exit_code.
# ---------------------------------------------------------------------------


class LoadBearingPreservationTests(FixtureBase):
    """The downstream contract (phase6 witness, what_just_happened
    state templates) parses ``total_line`` and ``result_line``
    byte-for-byte. The 090v layer is additive — it MUST NOT
    reformat them or change exit_code."""

    def test_total_line_format_unchanged(self) -> None:
        """The ``Total: N FAIL, M WARN`` line (and its three-state
        variants per 089c) appears byte-identical in stdout.

        Mutation bite: reformat result_line / total_line → the
        regex below + downstream phase6-witness parser break;
        this test FAILs.
        """
        self.write(_zero_bug_tree())
        stdout, _code = self.gate()
        # Scan stdout line-by-line for the canonical Total: form.
        # Use re.MULTILINE so ^...$ anchors per line.
        self.assertRegex(
            stdout, re.compile(r"^Total: \d+ FAIL, \d+ WARN$", re.MULTILINE),
        )

    def test_result_line_byte_identical_on_pass(self) -> None:
        """``RESULT: GATE PASSED`` is the load-bearing PASS line."""
        self.write(_one_bug_clean_tree())
        stdout, code = self.gate()
        self.assertEqual(code, 0)
        self.assertRegex(
            stdout, re.compile(r"^RESULT: GATE PASSED$", re.MULTILINE),
        )

    def test_result_line_byte_identical_on_fail(self) -> None:
        """``RESULT: GATE FAILED — N substantive issue(s) must be
        fixed`` is the load-bearing FAIL line (089c three-state
        verdict)."""
        self.write(_hollow_run4_tree())
        stdout, code = self.gate()
        self.assertNotEqual(code, 0)
        self.assertRegex(
            stdout,
            re.compile(
                r"^RESULT: GATE FAILED — \d+ substantive "
                r"issue\(s\) must be fixed$",
                re.MULTILINE,
            ),
        )

    def test_exit_code_unchanged_on_pass(self) -> None:
        """A clean PASS exits 0 — 090v does not change pass/fail
        semantics."""
        self.write(_one_bug_clean_tree())
        _stdout, code = self.gate()
        self.assertEqual(code, 0)

    def test_exit_code_unchanged_on_zero_bug_pass(self) -> None:
        """A zero-bug PASS still exits 0 — the ⚠️ shallow lead is
        informational, not semantic."""
        self.write(_zero_bug_tree())
        _stdout, code = self.gate()
        self.assertEqual(code, 0)

    def test_exit_code_unchanged_on_fail(self) -> None:
        """A run with FAILs still exits non-zero."""
        self.write(_hollow_run4_tree())
        _stdout, code = self.gate()
        self.assertNotEqual(code, 0)

    def test_090s_zero_bug_message_folded_not_duplicated(self) -> None:
        """The 090s standalone ``NOTE: N repo(s) ... found ZERO
        confirmed bugs`` line is FOLDED into the 090v block, not
        duplicated. The 090s framing tokens (``ZERO confirmed
        bugs``, ``hollow / shallow run``, ``Ory Keto run4``,
        ``090s``) still appear — they moved to the new block.

        Mutation bite: re-introduce the standalone ``NOTE:`` print
        AND leave the 090v narration in place → the ``ZERO
        confirmed bugs`` substring appears TWICE; this test FAILs.
        """
        self.write(_zero_bug_tree())
        stdout, code = self.gate()
        self.assertEqual(code, 0)
        # Each 090s framing token appears exactly ONCE in the
        # final stdout — the message has moved, not multiplied.
        self.assertEqual(
            stdout.count("ZERO confirmed bugs"), 1,
            f"v1.5.7 090v: the 090s 'ZERO confirmed bugs' tag "
            f"must appear exactly once (folded into the verdict "
            f"block, not duplicated). Got:\n{stdout}",
        )
        self.assertEqual(
            stdout.count("hollow / shallow run"), 1,
            "v1.5.7 090v: 'hollow / shallow run' must appear once.",
        )
        self.assertEqual(
            stdout.count("2026-05-25 Ory Keto run4"), 1,
            "v1.5.7 090v: the Ory Keto run4 motivation citation "
            "must appear once.",
        )
        # The standalone "NOTE:" prefix (pre-090v shape) must
        # NOT appear — the message lives inside the new block now.
        self.assertNotIn(
            "NOTE: 1 repo", stdout,
            "v1.5.7 090v: the standalone 090s NOTE: prefix is "
            "subsumed by the operator-verdict block.",
        )


# ---------------------------------------------------------------------------
# Benign-WARN demotion — conservative curated allowlist.
# ---------------------------------------------------------------------------


class BenignWarnDemotionTests(unittest.TestCase):
    """Direct tests of ``_is_benign_warn`` and the demotion in
    ``_emit_operator_verdict``. The gate-fixture path doesn't
    easily reproduce the legacy-manifest WARN, so we test the
    helper + the layer directly."""

    def test_allowlist_substrings_are_recognised_as_benign(
            self) -> None:
        """Each curated allowlist substring is treated as benign."""
        benign_samples = [
            "DIVERGENCE: intended backward-compat path (089 F9 KEEP)",
            "bugs_manifest.json: legacy manifest detected; treating "
            "absent BUG.divergence_type as 'code-spec'",
            "verify.sh contains triage probe assertions (pre-W4 "
            "back-compat)",
            "Cannot detect skill version from SKILL.md",
        ]
        for sample in benign_samples:
            self.assertTrue(
                quality_gate._is_benign_warn(sample),
                f"v1.5.7 090v: allowlist must recognise {sample!r}",
            )

    def test_non_allowlisted_warn_stays_prominent(self) -> None:
        """A WARN that doesn't match the curated allowlist is NOT
        demoted. Conservative direction (per spec §1.5.7 Task D):
        never hide a WARN that might matter.

        Mutation bite: widen ``_is_benign_warn`` to a permissive
        regex that catches the sample below → this test FAILs.
        """
        samples = [
            "No ### BUG-NNN headings found in BUGS.md",
            "test_functional.go: no test functions found",
            "0 fix patches (fix patches are optional but strongly "
            "encouraged)",
        ]
        for sample in samples:
            self.assertFalse(
                quality_gate._is_benign_warn(sample),
                f"v1.5.7 090v: unknown WARN {sample!r} must NOT "
                f"be demoted — conservative allowlist.",
            )

    def test_layer_demotes_benign_collapses_into_summary(self) -> None:
        """Two benign WARNs collapse into the
        ``(N operational notices — safe to ignore)`` summary."""
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            quality_gate._emit_operator_verdict(
                fail_records=[],
                warn_records=[
                    "intended backward-compat path (089 F9 KEEP)",
                    "legacy manifest detected (schemas.md §3.10)",
                ],
                zero_bug_repos=[],
                exit_code=0,
            )
            captured = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn(
            "(2 operational notices — safe to ignore", captured,
            f"v1.5.7 090v: two allowlisted benign WARNs must "
            f"collapse into the operational-notices summary. "
            f"Got:\n{captured}",
        )

    def test_layer_keeps_non_benign_warn_prominent(self) -> None:
        """A non-allowlisted WARN appears in the ``actionable WARNs
        above — review:`` section with its excerpt."""
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            quality_gate._emit_operator_verdict(
                fail_records=[],
                warn_records=[
                    "test_functional.go: no test functions found",
                ],
                zero_bug_repos=[],
                exit_code=0,
            )
            captured = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn(
            "actionable WARN", captured,
            f"v1.5.7 090v: a non-benign WARN must surface in the "
            f"actionable summary. Got:\n{captured}",
        )
        self.assertIn("no test functions found", captured)
        # And it must NOT be folded into the operational-notices
        # collapse.
        self.assertNotIn("operational notice", captured)


# ---------------------------------------------------------------------------
# Generic fallback — uncovered FAIL codes still get a narration.
# ---------------------------------------------------------------------------


class GenericFallbackTests(unittest.TestCase):

    def test_uncovered_fail_gets_generic_narration(self) -> None:
        """A FAIL whose message doesn't match any curated category
        renders the generic 'This check failed: ...' fallback so
        no FAIL goes un-narrated.

        Mutation bite: drop the generic-fallback branch → an
        uncovered FAIL prints no narration; this test FAILs.
        """
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            quality_gate._emit_operator_verdict(
                fail_records=[(
                    "substantive",
                    "PROGRESS.md: some new unfamiliar check failed",
                )],
                warn_records=[],
                zero_bug_repos=[],
                exit_code=1,
            )
            captured = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn("Why it failed:", captured)
        self.assertIn("This check failed:", captured)
        # The generic narration cites the v1.6.x expansion as
        # where the curated message will land — so the operator
        # knows the gap is tracked.
        self.assertIn("v1.6.x", captured)


# ---------------------------------------------------------------------------
# Direct unit tests of the classifier helpers.
# ---------------------------------------------------------------------------


class UnitClassifierTests(unittest.TestCase):

    def test_classify_fail_recognises_090s_noop(self) -> None:
        """The 090s `trivial / no-assertion stubs` signature
        classifies as ``_FAIL_NOOP_FUNCTIONAL``."""
        result = quality_gate._classify_fail(
            "quality/test_functional.go: ALL 1 test function(s) "
            "are trivial / no-assertion stubs (the 2026-05-25 "
            "Ory Keto run4 hollow shape)."
        )
        self.assertEqual(result, quality_gate._FAIL_NOOP_FUNCTIONAL)

    def test_classify_fail_recognises_090p_overclaim(self) -> None:
        """The 090p `body admits non-execution` signature
        classifies as ``_FAIL_TDD_OVERCLAIM``."""
        result = quality_gate._classify_fail(
            "BUG-001.red.log tagged RED but body admits non-"
            "execution (\"by inspection\")."
        )
        self.assertEqual(result, quality_gate._FAIL_TDD_OVERCLAIM)

    def test_classify_fail_recognises_090p_setup_failure(self) -> None:
        """The 090p `setup/dependency/build/collection failure`
        signature classifies as ``_FAIL_SETUP_FAILURE_RED``."""
        result = quality_gate._classify_fail(
            "BUG-001.red.log: tagged RED but body is a "
            "setup/dependency/build/collection failure"
        )
        self.assertEqual(result, quality_gate._FAIL_SETUP_FAILURE_RED)

    def test_classify_fail_generic_fallback(self) -> None:
        """An unknown FAIL message routes to ``_FAIL_GENERIC``."""
        result = quality_gate._classify_fail(
            "PROGRESS.md: unfamiliar check failed"
        )
        self.assertEqual(result, quality_gate._FAIL_GENERIC)

    def test_has_weak_model_signal_fires_on_overclaim(self) -> None:
        """The hard-rule classifier fires on a 090p overclaim
        FAIL — drives the stronger-model recommendation."""
        self.assertTrue(quality_gate._has_weak_model_signal(
            fail_records=[(
                "substantive",
                "BUG-001 tagged RED but body admits non-execution",
            )],
            zero_bug_repos=[],
            warn_records=[],
        ))

    def test_has_weak_model_signal_does_NOT_fire_on_setup_failure_alone(
            self) -> None:
        """The hard-rule classifier does NOT fire on a pure setup-
        failure run — drives the env-message-only path that
        AVOIDS the stronger-model recommendation."""
        self.assertFalse(quality_gate._has_weak_model_signal(
            fail_records=[(
                "substantive",
                "BUG-001.red.log: tagged RED but body is a "
                "setup/dependency/build/collection failure",
            )],
            zero_bug_repos=[],
            warn_records=[],
        ))


# ---------------------------------------------------------------------------
# Scope guard — SKILL.md / phase prompts untouched.
# ---------------------------------------------------------------------------


class ScopeGuard090vTests(unittest.TestCase):

    def test_skill_md_not_touched_by_090v(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        text = (repo_root / "skills" / "quality-playbook" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "090v", text,
            "SKILL.md must not carry 090v anchors — 090v is gate "
            "output, not skill prose. 32K BPE ceiling untouched.",
        )

    def test_phase_prompts_not_touched_by_090v(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        phase_dir = repo_root / "phase_prompts"
        for phase_file in sorted(phase_dir.glob("phase*.md")):
            text = phase_file.read_text(encoding="utf-8")
            self.assertNotIn(
                "090v", text,
                f"{phase_file.name} must not carry 090v anchors — "
                f"090v is gate output, not phase prose.",
            )


if __name__ == "__main__":
    unittest.main()
