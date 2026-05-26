"""QPB Test Harness — acceptance grader (Phase 2).

Evaluates an acceptance case's `expected` list against the
normalized run-fact object (SCHEMA.md §5) per the §4 closed
assertion vocabulary and the §4.3 F-notes.

Architecture per design §C / §B:
  * Grader reads ONLY the normalized fact object (never raw CLI
    output) AND the case's `axes` (for `provenance_runner_matches`).
  * Per-assertion pass/fail with EVIDENCE (the fact value + the
    expected value + the comparator), so grading.json carries the
    reasoning, not just a verdict.
  * `reviewed:false` on auto-grade — human review sets it later.

THE F-NOTES (LOCKED at SCHEMA.md §4.3):

1. **`verdict_state` ⊥ `gate_result` are INDEPENDENT axes — do
   NOT cross-couple.** A `CLEANUP` gate may pair with either
   `solid` or `shallow` verdict; `verdict_state=failed` does NOT
   imply `gate_result=FAIL`. The grader treats them
   independently — they're TWO assertions that happen to
   describe two facets of the same run.

2. **`no_false_pass` / `no_false_fail` are INTERNAL-CONSISTENCY
   (tool-correctness) checks, NOT expectation-matching** (which
   would be redundant with asserting `gate_result`):
   - `no_false_pass` = the gate never reports `PASS`/`CLEANUP`
     while substantive (non-record-keeping) FAILs exist.
   - `no_false_fail` = the gate never reports `FAIL` on a run
     with zero substantive FAILs.
   These pin the GATE's own correctness, not the run's outcome
   — the grader doesn't have substantive-fail count from facts
   directly (facts is presentation-layer), so the check uses
   gate_result + the live-behavior cleanup_gaps fact + the
   absence-of-FAIL-narration-in-verdict heuristic.

3. **`BLOCKED` (AUP/usage-policy stop) is graded `N/A`**, never
   MISSED. Security grader-only — acceptance has no BLOCKED
   outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from bin.harness.schema import (
    AcceptanceAssertion,
    Attribution,
    Case,
    CaseType,
    Comparator,
    ExpectedAssertion,
    GateResult,
    ProvenanceBugcountVsGate,
    RunAxes,
    RunFacts,
    Runner,
    VerdictState,
)


class GraderError(RuntimeError):
    """Grader misconfiguration (e.g. acceptance grader invoked on
    a security_eval case)."""


@dataclass
class AssertionResult:
    """Per-assertion grading record. Goes into
    ``grading.json.assertions[]``."""
    assertion: str
    comparator: str           # "==" | "!=" | "in"
    expected: Any
    observed: Any
    passed: bool
    detail: str = ""          # human-readable explanation

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class AcceptanceGrading:
    """Top-level grading record per SCHEMA.md §7 grading.json
    shape. Acceptance-only; security uses ``SecurityGrading``."""
    case_id: str
    run_id: str
    case_type: str = CaseType.ACCEPTANCE.value
    # Counts derived from `assertions`.
    n_total: int = 0
    n_passed: int = 0
    n_failed: int = 0
    verdict: str = "PENDING"  # "ALL_PASSED" | "FAILED" | "PENDING"
    assertions: "list[AssertionResult]" = field(default_factory=list)
    reviewed: bool = False
    human_verdict: "str | None" = None

    def to_json(self) -> dict:
        return {
            "case_id": self.case_id,
            "run_id": self.run_id,
            "case_type": self.case_type,
            "n_total": self.n_total,
            "n_passed": self.n_passed,
            "n_failed": self.n_failed,
            "verdict": self.verdict,
            "assertions": [a.to_json() for a in self.assertions],
            "reviewed": self.reviewed,
            "human_verdict": self.human_verdict,
        }


# ---------------------------------------------------------------------------
# Fact lookup — translate an AcceptanceAssertion name → fact value.
# ---------------------------------------------------------------------------


# Maps SCHEMA.md §4.1 assertion names to a fact-extractor callable
# that takes ``(facts, axes)`` and returns the assertion's observed
# value (in the closed-domain shape matching its `value`).
_FACT_EXTRACTORS: "dict[str, Any]" = {}


def _register(assertion: str):
    def deco(fn):
        _FACT_EXTRACTORS[assertion] = fn
        return fn
    return deco


@_register(AcceptanceAssertion.GATE_RESULT.value)
def _ext_gate_result(facts: RunFacts, axes: RunAxes) -> str:
    """SCHEMA.md §4.1: enum PASS|CLEANUP|FAIL. The grader
    compares enum-value strings, not enum members, so the
    `expected` list in JSON can stay declarative."""
    return facts.gate.gate_result.value


@_register(AcceptanceAssertion.VERDICT_STATE.value)
def _ext_verdict_state(facts: RunFacts, axes: RunAxes) -> str:
    """SCHEMA.md §4.1: enum solid|shallow|failed.

    F-note 1: INDEPENDENT of gate_result. The grader treats this
    as its own axis — does NOT cross-couple to gate_result."""
    return facts.verdict.verdict_state.value


@_register(AcceptanceAssertion.ATTRIBUTION.value)
def _ext_attribution(facts: RunFacts, axes: RunAxes) -> str:
    return facts.verdict.attribution.value


@_register(AcceptanceAssertion.RECOMMENDS_STRONGER_MODEL.value)
def _ext_recommends_stronger(facts: RunFacts, axes: RunAxes) -> bool:
    """SCHEMA.md §4.1: bool (true ONLY when attribution=weak_model
    — but the grader doesn't enforce that here; it just reads the
    fact. The 090v code is what guarantees the gating; the
    grader's job is to PIN that contract by comparing both
    assertions independently)."""
    return facts.verdict.recommends_stronger_model


@_register(AcceptanceAssertion.PHASE0_STATUS_OK.value)
def _ext_phase0_status_ok(facts: RunFacts, axes: RunAxes) -> bool:
    return facts.phase0.status == "ok"


@_register(AcceptanceAssertion.PHASE0_FIRST_PROBE.value)
def _ext_phase0_first_probe(facts: RunFacts, axes: RunAxes) -> bool:
    return facts.phase0.first_probe_ok


@_register(AcceptanceAssertion.BANNER_RENDERED.value)
def _ext_banner_rendered(facts: RunFacts, axes: RunAxes) -> bool:
    return facts.install.banner_rendered


@_register(AcceptanceAssertion.GITIGNORE_REMEDIATION_FOLLOWED.value)
def _ext_gitignore_followed(facts: RunFacts, axes: RunAxes) -> bool:
    return facts.install.gitignore_remediation_followed


@_register(AcceptanceAssertion.PROVENANCE_RUNNER_MATCHES.value)
def _ext_provenance_runner_matches(facts: RunFacts,
                                     axes: RunAxes) -> bool:
    """SCHEMA.md §4.1: bool — `provenance.detected_runner ==
    axes.runner`. The Runner enum values are "claude" /
    "copilot" / "codex" / "cursor"; the gate emits "claude-code"
    (with the "-code" suffix) for CLAUDECODE. Tolerate that
    mapping here so a case with `axes.runner=claude` matches
    `detected_runner=claude-code`. Other runners pass through
    by exact value match."""
    detected = facts.provenance.detected_runner
    axis = axes.runner.value
    # Tolerate the "claude" / "claude-code" mapping (the gate's
    # _RUNNER_ENV_MARKERS emits "claude-code"; the Runner enum
    # value is "claude").
    if axis == "claude" and detected.startswith("claude-code"):
        return True
    # Multi-marker honest report ("+"-joined) — the axis is one
    # of them.
    if "+" in detected:
        parts = set(detected.split("+"))
        # "claude-code" stands in for "claude"
        return (axis in parts
                or (axis == "claude" and "claude-code" in parts))
    return detected == axis


@_register(AcceptanceAssertion.PROVENANCE_MODEL_LABELED_SELFREPORT.value)
def _ext_provenance_model_labeled(facts: RunFacts,
                                    axes: RunAxes) -> bool:
    """SCHEMA.md §4.1: bool — `provenance.selfreport_model_label
    present+labeled`. The fact carries None when the run-metadata
    `model` field was absent / non-string — i.e. the gate
    correctly emitted "Model: not recorded". Otherwise, the
    label is present (and 090w guarantees the
    "self-reported — not verified" disclaimer renders alongside)."""
    return facts.provenance.selfreport_model_label is not None


@_register(AcceptanceAssertion.PROVENANCE_BUGCOUNT_VS_GATE.value)
def _ext_provenance_bugcount_vs_gate(facts: RunFacts,
                                       axes: RunAxes) -> str:
    """SCHEMA.md §4.1: enum match|expect_mismatch. Maps the
    boolean `provenance_mismatch` to the enum value."""
    if facts.provenance.provenance_mismatch:
        return ProvenanceBugcountVsGate.EXPECT_MISMATCH.value
    return ProvenanceBugcountVsGate.MATCH.value


@_register(AcceptanceAssertion.NO_FALSE_PASS.value)
def _ext_no_false_pass(facts: RunFacts, axes: RunAxes) -> bool:
    """F-note 2: internal-consistency. The gate never reports
    PASS/CLEANUP while substantive (non-record-keeping) FAILs
    exist.

    v1.5.7 097 (DE-CIRCULARIZED): uses the
    ``substantive_fail_count`` independently parsed by
    ``facts.py`` from the gate's ``Total:`` line, NOT inferred
    from the gate's own routing. Pre-097 this check was
    circular — it asked "did the gate route to PASS while
    substantive fails exist" by reading the gate's own
    PASS/CLEANUP routing, so a buggy gate that falsely PASSed
    couldn't be caught (the contradiction shape was checked
    against verdict_state, a different axis). The 097 fix:

      no_false_pass = NOT (substantive_fail_count > 0
                           AND gate_result ∈ {PASS, CLEANUP})

    This catches a gate that REPORTS substantive fails on its
    ``Total:`` line yet routes to PASS — the genuine tool-
    correctness bug.
    """
    if facts.gate.substantive_fail_count > 0:
        if facts.gate.gate_result in (GateResult.PASS,
                                        GateResult.CLEANUP):
            return False
    return True


@_register(AcceptanceAssertion.NO_FALSE_FAIL.value)
def _ext_no_false_fail(facts: RunFacts, axes: RunAxes) -> bool:
    """F-note 2 sibling: the gate never reports FAIL on a run
    with zero substantive FAILs.

    v1.5.7 097 (DE-CIRCULARIZED): uses the
    ``substantive_fail_count`` independently parsed by
    ``facts.py``. Pre-097 this checked verdict_state agreement,
    which is a different axis (F-note 1 — verdict_state ⊥
    gate_result independence). The 097 fix:

      no_false_fail = NOT (gate_result == FAIL
                           AND substantive_fail_count == 0)

    A FAIL gate with zero substantive fails is a tool-
    correctness bug regardless of verdict_state.
    """
    if facts.gate.gate_result == GateResult.FAIL:
        if facts.gate.substantive_fail_count == 0:
            return False
    return True


@_register(AcceptanceAssertion.BUGS_UNVERIFIED_MESSAGE_PRESENT.value)
def _ext_bugs_unverified(facts: RunFacts, axes: RunAxes) -> bool:
    return facts.verdict.bugs_unverified_present


# ---------------------------------------------------------------------------
# Comparator application
# ---------------------------------------------------------------------------


def _apply_comparator(observed: Any, comparator: Comparator,
                       expected: Any) -> bool:
    """Apply the §4.3-note-3 closed-comparator vocabulary. The
    `in` comparator interprets `expected` as a collection (per
    SCHEMA.md §4 — used e.g. for
    `{assertion: "gate_result", comparator: "in",
     value: ["PASS", "CLEANUP"]}`).
    """
    if comparator == Comparator.EQ:
        return observed == expected
    if comparator == Comparator.NE:
        return observed != expected
    if comparator == Comparator.IN:
        try:
            return observed in expected
        except TypeError:
            return False
    raise GraderError(f"unknown comparator {comparator!r}")


# ---------------------------------------------------------------------------
# Top-level grader entry
# ---------------------------------------------------------------------------


def grade_assertion(entry: ExpectedAssertion, facts: RunFacts,
                     axes: RunAxes) -> AssertionResult:
    """Grade ONE acceptance assertion against the run facts."""
    extractor = _FACT_EXTRACTORS.get(entry.assertion)
    if extractor is None:
        # Unknown assertion — return a failing result naming the
        # gap. (The schema parser accepts assertion names as
        # free strings to remain forward-compatible with v1.6.x
        # E1 expansion; this is where the grader catches names
        # not yet in the §4 vocabulary.)
        return AssertionResult(
            assertion=entry.assertion,
            comparator=entry.comparator.value,
            expected=entry.value,
            observed=None,
            passed=False,
            detail=(
                f"assertion {entry.assertion!r} not in the §4 "
                f"closed vocabulary; grader has no fact extractor"
            ),
        )
    observed = extractor(facts, axes)
    passed = _apply_comparator(observed, entry.comparator, entry.value)
    detail = (
        f"{entry.assertion} = {observed!r} "
        f"(expected {entry.comparator.value} {entry.value!r}) — "
        f"{'PASS' if passed else 'FAIL'}"
    )
    return AssertionResult(
        assertion=entry.assertion,
        comparator=entry.comparator.value,
        expected=entry.value,
        observed=observed,
        passed=passed,
        detail=detail,
    )


def grade_acceptance(case: Case, facts: RunFacts, axes: RunAxes,
                      run_id: str) -> AcceptanceGrading:
    """Grade an acceptance case's `expected` list against the
    run's normalized facts. Returns ``AcceptanceGrading`` ready
    to be serialized to ``grading.json``.

    Per design §B / SCHEMA.md: grading is automatic + non-
    blocking; the result carries `reviewed=False` for later
    human override.
    """
    if case.type != CaseType.ACCEPTANCE:
        raise GraderError(
            f"grade_acceptance called on non-acceptance case "
            f"{case.id} (type={case.type.value}); use "
            f"grade_security for security_eval cases"
        )
    if case.expected is None:
        raise GraderError(
            f"acceptance case {case.id} has no `expected` list "
            f"to grade"
        )
    grading = AcceptanceGrading(
        case_id=case.id, run_id=run_id,
    )
    for entry in case.expected:
        grading.assertions.append(
            grade_assertion(entry, facts, axes),
        )
    grading.n_total = len(grading.assertions)
    grading.n_passed = sum(1 for a in grading.assertions if a.passed)
    grading.n_failed = grading.n_total - grading.n_passed
    if grading.n_failed == 0:
        grading.verdict = "ALL_PASSED"
    else:
        grading.verdict = "FAILED"
    return grading


__all__ = [
    "GraderError",
    "AssertionResult",
    "AcceptanceGrading",
    "grade_assertion",
    "grade_acceptance",
]
