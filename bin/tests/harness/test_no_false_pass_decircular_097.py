"""v1.5.7 097 Task A — de-circularized no_false_pass / no_false_fail
mutation-bite tests.

Pre-097, the grader's `no_false_pass` / `no_false_fail` checks
inferred "substantive fails exist" from the gate's own
PASS/CLEANUP routing — circular. A buggy gate that wrongly
routed substantive-fail runs to PASS could never be caught.

097 fix:
  * ``GateFacts.substantive_fail_count`` + ``record_keeping_fail_
    count`` parsed INDEPENDENTLY from the gate's ``Total:`` line.
  * ``no_false_pass = NOT (substantive_fail_count > 0 AND
    gate_result ∈ {PASS, CLEANUP})``
  * ``no_false_fail = NOT (gate_result == FAIL AND
    substantive_fail_count == 0)``

This file is the **explicit mutation-bite suite** for the
de-circularization — separate from the broader grader tests in
test_grade_acceptance.py so the bite-evidence is concentrated.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import unittest

from bin.harness import facts as F
from bin.harness import grade_acceptance as G
from bin.harness import schema as S


def _mk_facts(*, gate_result: S.GateResult,
              substantive_fail_count: int,
              record_keeping_fail_count: int = 0,
              verdict_state: S.VerdictState = S.VerdictState.SOLID,
              ) -> S.RunFacts:
    return S.RunFacts(
        phase0=S.Phase0Facts(status="ok", probe_attempts=1,
                               first_probe_ok=True),
        verdict=S.VerdictFacts(
            verdict_state=verdict_state,
            attribution=S.Attribution.NONE,
            recommends_stronger_model=False,
            bugs_unverified_present=False,
        ),
        provenance=S.ProvenanceFacts(
            detected_runner="claude-code",
            selfreport_model_label="opus",
            gate_bug_count=0, reported_bug_count=None,
            provenance_mismatch=False,
        ),
        gate=S.GateFacts(
            gate_total="(synthetic)",
            gate_result=gate_result,
            cleanup_gaps=0,
            substantive_fail_count=substantive_fail_count,
            record_keeping_fail_count=record_keeping_fail_count,
        ),
        install=S.InstallSurfaceFacts(
            banner_rendered=True,
            gitignore_remediation_followed=True,
        ),
        run_meta=S.RunMetaFacts(
            blocked=False, stop_reason=None, exit_code=0,
            timings={}, raw_receipt="stream.ndjson",
        ),
    )


def _mk_axes() -> S.RunAxes:
    return S.RunAxes(
        runner=S.Runner.CLAUDE, mode=S.Mode.A,
        install_channel=S.InstallChannel.CLONE,
        model="opus",
    )


class NoFalsePassDeCircularizedTests(unittest.TestCase):

    def test_FALSE_PASS_DETECTED_via_substantive_count(self) -> None:
        """v1.5.7 097 MUTATION BITE: a gate that REPORTS
        substantive_fail_count>0 on its Total: line yet
        routes to PASS is a tool-correctness bug — and
        no_false_pass MUST return False.

        Mutation bite: revert _ext_no_false_pass to the
        pre-097 (verdict_state-based) check → this test FAILs
        because the false-PASS is no longer surfaced from the
        substantive count alone.
        """
        facts = _mk_facts(
            gate_result=S.GateResult.PASS,
            substantive_fail_count=3,
            verdict_state=S.VerdictState.SOLID,  # verdict
                                                  # agrees with
                                                  # the buggy
                                                  # PASS — but
                                                  # the count
                                                  # gives it
                                                  # away.
        )
        self.assertFalse(
            G._ext_no_false_pass(facts, _mk_axes()),
            "v1.5.7 097: substantive_fail_count=3 + gate_result=PASS "
            "MUST yield no_false_pass=False — the gate's own count "
            "contradicts its routing, independent of verdict_state.",
        )

    def test_FALSE_CLEANUP_PASS_DETECTED(self) -> None:
        """Same defect via the CLEANUP route: gate says
        CLEANUP (which exits 0) but the substantive count is
        non-zero. The 089c three-state contract says CLEANUP
        only routes when substantive==0, so this is a tool-
        correctness contradiction."""
        facts = _mk_facts(
            gate_result=S.GateResult.CLEANUP,
            substantive_fail_count=1,
            record_keeping_fail_count=2,
        )
        self.assertFalse(
            G._ext_no_false_pass(facts, _mk_axes()),
        )

    def test_genuine_PASS_with_zero_counts_returns_True(self) -> None:
        """Don't-over-fire pin: a genuine PASS (no substantive
        fails) returns True."""
        facts = _mk_facts(
            gate_result=S.GateResult.PASS,
            substantive_fail_count=0,
        )
        self.assertTrue(G._ext_no_false_pass(facts, _mk_axes()))

    def test_FAIL_gate_returns_True(self) -> None:
        """no_false_pass only fires for PASS/CLEANUP gates —
        a FAIL gate is internally consistent w.r.t. no_false_pass
        by construction."""
        facts = _mk_facts(
            gate_result=S.GateResult.FAIL,
            substantive_fail_count=5,
            verdict_state=S.VerdictState.FAILED,
        )
        self.assertTrue(G._ext_no_false_pass(facts, _mk_axes()))


class NoFalseFailDeCircularizedTests(unittest.TestCase):

    def test_FALSE_FAIL_DETECTED_via_substantive_count(self) -> None:
        """v1.5.7 097 MUTATION BITE: a gate that routes to FAIL
        with substantive_fail_count==0 is a tool-correctness bug.
        no_false_fail MUST return False, independent of
        verdict_state.

        Mutation bite: revert to the pre-097 (verdict_state
        agreement) check → this test FAILs because verdict_state
        agrees with FAIL and the old logic returns True.
        """
        facts = _mk_facts(
            gate_result=S.GateResult.FAIL,
            substantive_fail_count=0,
            record_keeping_fail_count=0,
            verdict_state=S.VerdictState.FAILED,  # verdict
                                                    # agrees
                                                    # with the
                                                    # buggy FAIL.
        )
        self.assertFalse(
            G._ext_no_false_fail(facts, _mk_axes()),
            "v1.5.7 097: substantive_fail_count=0 + gate_result=FAIL "
            "MUST yield no_false_fail=False.",
        )

    def test_genuine_FAIL_with_substantive_count_returns_True(
            self) -> None:
        facts = _mk_facts(
            gate_result=S.GateResult.FAIL,
            substantive_fail_count=2,
            verdict_state=S.VerdictState.FAILED,
        )
        self.assertTrue(G._ext_no_false_fail(facts, _mk_axes()))

    def test_PASS_gate_returns_True(self) -> None:
        """no_false_fail only fires for FAIL gates."""
        facts = _mk_facts(
            gate_result=S.GateResult.PASS,
            substantive_fail_count=0,
        )
        self.assertTrue(G._ext_no_false_fail(facts, _mk_axes()))


class ParserPopulatesCountsTests(unittest.TestCase):
    """Pin that the 097 parsing actually fills the new fields
    from the gate's `Total:` line. Without this the rest of 097
    is dead code."""

    _CANONICAL_FAILED_STDOUT = """\
===========================================
Total: 5 FAIL (3 substantive, 2 record-keeping), 1 WARN
RESULT: GATE FAILED — 3 substantive issue(s) must be fixed

─── Operator Verdict ──────────────────────
❌ GATE FAILED

Why it failed:
  • [missing_artifact] (5 FAILs)
    A required artifact is missing.

── Run provenance ──
  Runner:  claude-code (detected from environment)
  Model:   opus (self-reported by the agent — not verified)
  Bugs:    0 found (gate-counted)
───────────────────────────────────────────
"""

    _CANONICAL_CLEANUP_STDOUT = """\
===========================================
Total: 2 CLEANUP, 0 WARN
RESULT: GATE PASSED WITH CLEANUP NEEDED — 2 audit record-keeping gap(s)

─── Operator Verdict ──────────────────────
⚠️ GATE PASSED — but this run looks shallow

Result: it passed the checkpoint, with some bookkeeping gaps.

── Run provenance ──
  Runner:  claude-code (detected from environment)
  Model:   opus (self-reported by the agent — not verified)
  Bugs:    1 found (gate-counted)
───────────────────────────────────────────
"""

    _CANONICAL_CLEAN_PASS_STDOUT = """\
===========================================
Total: 0 FAIL, 2 WARN
RESULT: GATE PASSED

─── Operator Verdict ──────────────────────
✅ GATE PASSED — this run looks solid

── Run provenance ──
  Runner:  claude-code (detected from environment)
  Model:   opus (self-reported by the agent — not verified)
  Bugs:    1 found (gate-counted)
───────────────────────────────────────────
"""

    def test_failed_total_line_populates_both_counts(self) -> None:
        gate, _v, _p = F.parse_gate_stdout(
            self._CANONICAL_FAILED_STDOUT,
        )
        self.assertEqual(gate.substantive_fail_count, 3)
        self.assertEqual(gate.record_keeping_fail_count, 2)
        self.assertEqual(gate.gate_result, S.GateResult.FAIL)

    def test_cleanup_total_line_populates_record_keeping_count(
            self) -> None:
        """CLEANUP path: substantive==0 by 089c construction;
        record_keeping == cleanup_gaps."""
        gate, _v, _p = F.parse_gate_stdout(
            self._CANONICAL_CLEANUP_STDOUT,
        )
        self.assertEqual(gate.substantive_fail_count, 0)
        self.assertEqual(gate.record_keeping_fail_count, 2)
        self.assertEqual(gate.cleanup_gaps, 2)
        self.assertEqual(gate.gate_result, S.GateResult.CLEANUP)

    def test_clean_pass_total_line_both_counts_zero(self) -> None:
        gate, _v, _p = F.parse_gate_stdout(
            self._CANONICAL_CLEAN_PASS_STDOUT,
        )
        self.assertEqual(gate.substantive_fail_count, 0)
        self.assertEqual(gate.record_keeping_fail_count, 0)
        self.assertEqual(gate.gate_result, S.GateResult.PASS)


if __name__ == "__main__":
    unittest.main()
