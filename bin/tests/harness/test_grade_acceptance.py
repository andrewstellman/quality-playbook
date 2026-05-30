"""v1.5.7 092 — acceptance grader tests.

Covers ``bin/harness/grade_acceptance.py``:

  PerAssertionGradingTests — every §4.1 assertion grades against
    a fixture fact-object. Each test pins one assertion's
    extractor + comparator combination.
  ComparatorBehaviourTests — ==/!=/in semantics.
  IndependenceTests — F-note 1: `verdict_state` ⊥ `gate_result`
    are independent axes; the grader does NOT cross-couple. A
    `CLEANUP` gate paired with either `solid` or `shallow`
    verdict grades each independently. **Mutation-bite present.**
  InternalConsistencyTests — F-note 2: `no_false_pass` /
    `no_false_fail` are tool-correctness checks, NOT
    expectation-matching. The grader returns True iff the gate's
    verdict-line agrees with its own three-state routing.
    **Mutation-bite present** (false PASS detected).
  ProvenanceTests — `provenance_runner_matches` tolerates the
    `claude`/`claude-code` mapping (the gate's _RUNNER_ENV_
    MARKERS emit `claude-code` for the `claude` axis);
    `provenance_bugcount_vs_gate` maps boolean
    `provenance_mismatch` → match/expect_mismatch enum.
  TopLevelGraderTests — `grade_acceptance` produces an
    `AcceptanceGrading` with n_total / n_passed / verdict;
    rejects security_eval cases; rejects acceptance with no
    `expected` list.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import unittest

from bin.harness import grade_acceptance as G
from bin.harness import schema as S


def _mk_facts(**overrides) -> S.RunFacts:
    """Synthesize a RunFacts with defaults overridable per test.

    Defaults: a solid PASS with no shallow signal, claude-code
    detected, no provenance mismatch."""
    defaults = dict(
        phase0=S.Phase0Facts(status="ok", probe_attempts=1,
                               first_probe_ok=True),
        verdict=S.VerdictFacts(
            verdict_state=S.VerdictState.SOLID,
            attribution=S.Attribution.NONE,
            recommends_stronger_model=False,
            bugs_unverified_present=False,
        ),
        provenance=S.ProvenanceFacts(
            detected_runner="claude-code",
            selfreport_model_label="opus",
            gate_bug_count=1,
            reported_bug_count=1,
            provenance_mismatch=False,
        ),
        gate=S.GateFacts(
            gate_total="Total: 0 FAIL, 0 WARN",
            gate_result=S.GateResult.PASS,
            cleanup_gaps=0,
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
    # Allow nested overrides via dot-keys like "verdict.attribution".
    for k, v in overrides.items():
        if "." in k:
            outer, inner = k.split(".", 1)
            obj = defaults[outer]
            setattr(obj, inner, v)
        else:
            defaults[k] = v
    return S.RunFacts(**defaults)


def _mk_axes(runner: S.Runner = S.Runner.CLAUDE,
             channel: S.InstallChannel = S.InstallChannel.CLONE,
             model: str = "opus") -> S.RunAxes:
    return S.RunAxes(
        runner=runner, mode=S.Mode.A,
        install_channel=channel, model=model,
    )


def _expected(assertion: str, comparator: S.Comparator,
              value) -> S.ExpectedAssertion:
    return S.ExpectedAssertion(
        assertion=assertion, comparator=comparator, value=value,
    )


# ---------------------------------------------------------------------------
# Per-assertion grading
# ---------------------------------------------------------------------------


class PerAssertionGradingTests(unittest.TestCase):

    def test_gate_result_pass(self) -> None:
        facts = _mk_facts()
        result = G.grade_assertion(
            _expected("gate_result", S.Comparator.EQ, "PASS"),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.observed, "PASS")

    def test_gate_result_in_list(self) -> None:
        """SCHEMA.md §4 `in` comparator for the
        `gate_result ∈ ["PASS", "CLEANUP"]` shape used by ACC-001
        (smoke acceptance case that tolerates either pass shape)."""
        facts = _mk_facts(
            **{"gate.gate_result": S.GateResult.CLEANUP},
        )
        result = G.grade_assertion(
            _expected("gate_result", S.Comparator.IN,
                       ["PASS", "CLEANUP"]),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.observed, "CLEANUP")

    def test_verdict_state_solid(self) -> None:
        facts = _mk_facts()
        result = G.grade_assertion(
            _expected("verdict_state", S.Comparator.EQ, "solid"),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)

    def test_attribution_weak_model(self) -> None:
        facts = _mk_facts(
            **{"verdict.attribution": S.Attribution.WEAK_MODEL},
        )
        result = G.grade_assertion(
            _expected("attribution", S.Comparator.EQ, "weak_model"),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)

    def test_recommends_stronger_model_true(self) -> None:
        facts = _mk_facts(
            **{"verdict.recommends_stronger_model": True},
        )
        result = G.grade_assertion(
            _expected("recommends_stronger_model",
                       S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)

    def test_phase0_status_ok(self) -> None:
        facts = _mk_facts()
        result = G.grade_assertion(
            _expected("phase0_status_ok", S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.observed, True)

    def test_phase0_status_remediable_fails(self) -> None:
        facts = _mk_facts(**{"phase0.status": "remediable"})
        result = G.grade_assertion(
            _expected("phase0_status_ok", S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.observed, False)

    def test_phase0_first_probe(self) -> None:
        facts = _mk_facts()
        result = G.grade_assertion(
            _expected("phase0_first_probe", S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)

    def test_banner_rendered(self) -> None:
        facts = _mk_facts()
        self.assertTrue(G.grade_assertion(
            _expected("banner_rendered", S.Comparator.EQ, True),
            facts, _mk_axes(),
        ).passed)

    def test_gitignore_remediation_followed(self) -> None:
        facts = _mk_facts()
        self.assertTrue(G.grade_assertion(
            _expected("gitignore_remediation_followed",
                       S.Comparator.EQ, True),
            facts, _mk_axes(),
        ).passed)

    def test_bugs_unverified_message_present(self) -> None:
        facts = _mk_facts(
            **{"verdict.bugs_unverified_present": True},
        )
        result = G.grade_assertion(
            _expected("bugs_unverified_message_present",
                       S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)

    def test_unknown_assertion_fails_explicitly(self) -> None:
        """An assertion name not in §4 returns a failing
        AssertionResult with a clear gap-naming detail (the
        schema parser is forward-tolerant; the grader is where
        unknown names surface)."""
        facts = _mk_facts()
        result = G.grade_assertion(
            _expected("v16x_assertion_that_doesnt_exist_yet",
                       S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertFalse(result.passed)
        self.assertIn("not in the §4 closed vocabulary",
                      result.detail)


# ---------------------------------------------------------------------------
# Comparators
# ---------------------------------------------------------------------------


class ComparatorBehaviourTests(unittest.TestCase):

    def test_eq_true(self) -> None:
        self.assertTrue(G._apply_comparator(
            "PASS", S.Comparator.EQ, "PASS",
        ))

    def test_eq_false(self) -> None:
        self.assertFalse(G._apply_comparator(
            "FAIL", S.Comparator.EQ, "PASS",
        ))

    def test_ne_true(self) -> None:
        self.assertTrue(G._apply_comparator(
            "FAIL", S.Comparator.NE, "PASS",
        ))

    def test_in_list(self) -> None:
        self.assertTrue(G._apply_comparator(
            "CLEANUP", S.Comparator.IN, ["PASS", "CLEANUP"],
        ))
        self.assertFalse(G._apply_comparator(
            "FAIL", S.Comparator.IN, ["PASS", "CLEANUP"],
        ))


# ---------------------------------------------------------------------------
# F-note 1: verdict_state ⊥ gate_result independence
# ---------------------------------------------------------------------------


class IndependenceTests(unittest.TestCase):
    """F-note 1 (LOCKED): the grader treats `verdict_state` and
    `gate_result` as INDEPENDENT axes — does NOT cross-couple
    them."""

    def test_cleanup_with_solid_verdict_grades_both_independently(
            self) -> None:
        """A CLEANUP gate paired with a `solid` verdict — both
        assertions are evaluated separately. (A CLEANUP gate
        can legitimately pair with either solid or shallow per
        §4.3 note 1.)"""
        facts = _mk_facts(
            **{"gate.gate_result": S.GateResult.CLEANUP,
                "gate.cleanup_gaps": 2,
                "verdict.verdict_state": S.VerdictState.SOLID},
        )
        gate_assertion = _expected(
            "gate_result", S.Comparator.EQ, "CLEANUP",
        )
        verdict_assertion = _expected(
            "verdict_state", S.Comparator.EQ, "solid",
        )
        gr = G.grade_assertion(gate_assertion, facts, _mk_axes())
        vr = G.grade_assertion(verdict_assertion, facts, _mk_axes())
        self.assertTrue(gr.passed)
        self.assertTrue(vr.passed)

    def test_cleanup_with_shallow_verdict_grades_both_independently(
            self) -> None:
        facts = _mk_facts(
            **{"gate.gate_result": S.GateResult.CLEANUP,
                "gate.cleanup_gaps": 2,
                "verdict.verdict_state": S.VerdictState.SHALLOW},
        )
        gr = G.grade_assertion(
            _expected("gate_result", S.Comparator.EQ, "CLEANUP"),
            facts, _mk_axes(),
        )
        vr = G.grade_assertion(
            _expected("verdict_state", S.Comparator.EQ, "shallow"),
            facts, _mk_axes(),
        )
        self.assertTrue(gr.passed)
        self.assertTrue(vr.passed)

    def test_grader_does_NOT_cross_couple_states(self) -> None:
        """v1.5.7 092 F-note 1 MUTATION BITE: if a future
        refactor made `verdict_state` extraction inherit from
        `gate_result` (e.g. "if gate_result is FAIL, force
        verdict_state to failed"), the case below would
        catch the cross-coupling.

        Fixture: `gate_result=PASS` + `verdict_state=failed`
        (impossible per the gate's own three-state routing, but
        synthesizable in fact-fixture form). The grader must
        report `verdict_state=failed` HONESTLY — not "corrected"
        to "solid" because gate_result said PASS.
        """
        facts = _mk_facts(
            **{"gate.gate_result": S.GateResult.PASS,
                "verdict.verdict_state": S.VerdictState.FAILED},
        )
        vr = G.grade_assertion(
            _expected("verdict_state", S.Comparator.EQ, "failed"),
            facts, _mk_axes(),
        )
        # Reported honestly — passes the failed-verdict assertion.
        self.assertTrue(
            vr.passed,
            "v1.5.7 092 F-note 1: the grader MUST NOT cross-"
            "couple verdict_state to gate_result. A "
            "verdict_state=failed fact must grade as 'failed' "
            "regardless of gate_result.",
        )
        # And gate_result is independently observed.
        gr = G.grade_assertion(
            _expected("gate_result", S.Comparator.EQ, "PASS"),
            facts, _mk_axes(),
        )
        self.assertTrue(gr.passed)


# ---------------------------------------------------------------------------
# F-note 2: no_false_pass / no_false_fail are internal-consistency
# ---------------------------------------------------------------------------


class InternalConsistencyTests(unittest.TestCase):
    """F-note 2 (LOCKED): `no_false_pass` / `no_false_fail` are
    TOOL-CORRECTNESS checks, NOT expectation-matching."""

    def test_no_false_pass_consistent(self) -> None:
        """PASS gate + verdict_state=solid → consistent → True."""
        facts = _mk_facts()
        result = G.grade_assertion(
            _expected("no_false_pass", S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.observed, True)

    def test_no_false_pass_FALSE_PASS_DETECTED(self) -> None:
        """v1.5.7 097 (de-circularized) MUTATION BITE: the gate
        reports PASS while its own `Total:` line says
        substantive fails exist → that's a tool-correctness
        bug, and `no_false_pass=False` surfaces it.

        Fixture: PASS routing + ``substantive_fail_count=2``.
        Pre-097 this was checked against verdict_state (which is
        independent per F-note 1 — circular logic). Post-097 the
        check uses the count independently parsed from the gate's
        ``Total:`` line.

        Mutation bite: revert to the count-free (circular)
        check → this test FAILs (the false-PASS contradiction
        is no longer surfaced because the old check looked at
        verdict_state instead of the count).
        """
        facts = _mk_facts(
            **{"gate.gate_result": S.GateResult.PASS,
                "gate.substantive_fail_count": 2},
        )
        result = G.grade_assertion(
            _expected("no_false_pass", S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertFalse(
            result.passed,
            "v1.5.7 097: PASS gate + substantive_fail_count > 0 "
            "is a tool-correctness contradiction; "
            "no_false_pass MUST be False (independent count, "
            "not gate's own routing).",
        )
        self.assertEqual(result.observed, False)

    def test_no_false_fail_consistent_on_fail(self) -> None:
        """FAIL gate with substantive_fail_count > 0 →
        consistent → no_false_fail=True. (v1.5.7 097
        de-circularized: uses the count, not verdict_state.)"""
        facts = _mk_facts(
            **{"gate.gate_result": S.GateResult.FAIL,
                "gate.substantive_fail_count": 3,
                "verdict.verdict_state": S.VerdictState.FAILED},
        )
        result = G.grade_assertion(
            _expected("no_false_fail", S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)

    def test_no_false_fail_FALSE_FAIL_DETECTED(self) -> None:
        """v1.5.7 097 (de-circularized) MUTATION BITE: the gate
        reports FAIL with `substantive_fail_count=0` →
        `no_false_fail=False`. Uses the independent count, not
        a verdict_state agreement check."""
        facts = _mk_facts(
            **{"gate.gate_result": S.GateResult.FAIL,
                "gate.substantive_fail_count": 0},
        )
        result = G.grade_assertion(
            _expected("no_false_fail", S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertFalse(result.passed)

    def test_no_false_pass_on_FAIL_gate_returns_True(self) -> None:
        """The `no_false_pass` check ONLY fires when the gate is
        PASS/CLEANUP. A FAIL gate is internally consistent w.r.t.
        no_false_pass by construction (it's not falsely passing
        — it's failing)."""
        facts = _mk_facts(
            **{"gate.gate_result": S.GateResult.FAIL,
                "verdict.verdict_state": S.VerdictState.FAILED},
        )
        result = G.grade_assertion(
            _expected("no_false_pass", S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)


# ---------------------------------------------------------------------------
# Provenance assertions
# ---------------------------------------------------------------------------


class ProvenanceTests(unittest.TestCase):

    def test_provenance_runner_matches_claude_vs_claude_code(
            self) -> None:
        """The gate emits `claude-code` (with the suffix) for the
        CLAUDECODE env marker; the Runner enum value is `claude`.
        The grader tolerates this mapping."""
        facts = _mk_facts(
            **{"provenance.detected_runner": "claude-code"},
        )
        result = G.grade_assertion(
            _expected("provenance_runner_matches",
                       S.Comparator.EQ, True),
            facts, _mk_axes(runner=S.Runner.CLAUDE),
        )
        self.assertTrue(result.passed)

    def test_provenance_runner_matches_codex_exact(self) -> None:
        facts = _mk_facts(
            **{"provenance.detected_runner": "codex"},
        )
        result = G.grade_assertion(
            _expected("provenance_runner_matches",
                       S.Comparator.EQ, True),
            facts, _mk_axes(runner=S.Runner.CODEX),
        )
        self.assertTrue(result.passed)

    def test_provenance_runner_matches_mismatch_fails(self) -> None:
        facts = _mk_facts(
            **{"provenance.detected_runner": "codex"},
        )
        result = G.grade_assertion(
            _expected("provenance_runner_matches",
                       S.Comparator.EQ, True),
            facts, _mk_axes(runner=S.Runner.CLAUDE),
        )
        self.assertFalse(result.passed)

    def test_provenance_runner_matches_multi_marker(self) -> None:
        """"+"-joined honest report when multiple env vars set
        — the axis runner is one of them."""
        facts = _mk_facts(
            **{"provenance.detected_runner": "codex+claude-code"},
        )
        result = G.grade_assertion(
            _expected("provenance_runner_matches",
                       S.Comparator.EQ, True),
            facts, _mk_axes(runner=S.Runner.CLAUDE),
        )
        self.assertTrue(result.passed)

    def test_provenance_model_labeled_selfreport_present(self) -> None:
        facts = _mk_facts()  # default has selfreport_model_label="opus"
        result = G.grade_assertion(
            _expected("provenance_model_labeled_selfreport",
                       S.Comparator.EQ, True),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)

    def test_provenance_model_labeled_when_self_report_absent_but_plan_known_returns_true(
            self) -> None:
        # v1.5.7 162 contract change: the agent didn't self-report
        # but the plan knows the model (axes.model="opus"). Pre-162:
        # False (stream-side check failed). Post-162: True (outcome
        # OK — harness invoked the planned model). The 2026-05-30
        # 13:43:22Z run-05 (express copilot/gpt-5.4) was this case
        # in production.
        facts = _mk_facts(
            **{"provenance.selfreport_model_label": None},
        )
        result = G.grade_assertion(
            _expected("provenance_model_labeled_selfreport",
                       S.Comparator.EQ, True),
            facts, _mk_axes(),  # default model="opus"
        )
        self.assertTrue(result.passed)

    def test_provenance_model_labeled_when_self_report_contradicts_plan_returns_false(
            self) -> None:
        # 162: the real contradiction case. Plan asked for "opus"
        # but the agent self-reported "gpt-3.5-turbo". The OUTCOME
        # assertion is False (model invoked ≠ self-reported).
        facts = _mk_facts(
            **{"provenance.selfreport_model_label": "gpt-3.5-turbo"},
        )
        result = G.grade_assertion(
            _expected("provenance_model_labeled_selfreport",
                       S.Comparator.EQ, True),
            facts, _mk_axes(model="opus"),
        )
        # Mutation-bite target: dropping the `if selfreport is
        # None: return True` branch makes the absent-but-plan-known
        # test fail; dropping the final `return selfreport ==
        # planned` makes this contradiction test fail.
        self.assertFalse(result.passed)

    def test_provenance_model_labeled_when_self_report_matches_plan_returns_true(
            self) -> None:
        # Happy path: agent self-reported "opus", plan asked for
        # "opus", they match.
        facts = _mk_facts(
            **{"provenance.selfreport_model_label": "opus"},
        )
        result = G.grade_assertion(
            _expected("provenance_model_labeled_selfreport",
                       S.Comparator.EQ, True),
            facts, _mk_axes(model="opus"),
        )
        self.assertTrue(result.passed)

    def test_provenance_model_labeled_mismatch_true_on_contradiction(
            self) -> None:
        # 162: complementary `_mismatch` assertion is the real
        # contradiction signal. When self-report ≠ planned, mismatch
        # is True (and operators can grade on this as a quality bug).
        facts = _mk_facts(
            **{"provenance.selfreport_model_label": "gpt-3.5-turbo"},
        )
        result = G.grade_assertion(
            _expected(
                "provenance_model_labeled_selfreport_mismatch",
                S.Comparator.EQ, True),
            facts, _mk_axes(model="opus"),
        )
        self.assertTrue(result.passed)

    def test_provenance_model_labeled_mismatch_false_when_self_report_absent(
            self) -> None:
        # No contradiction possible when agent didn't self-report.
        facts = _mk_facts(
            **{"provenance.selfreport_model_label": None},
        )
        result = G.grade_assertion(
            _expected(
                "provenance_model_labeled_selfreport_mismatch",
                S.Comparator.EQ, False),
            facts, _mk_axes(model="opus"),
        )
        self.assertTrue(result.passed)

    def test_provenance_model_labeled_mismatch_false_when_self_report_matches(
            self) -> None:
        # No mismatch when agent's self-report matches the plan.
        facts = _mk_facts(
            **{"provenance.selfreport_model_label": "opus"},
        )
        result = G.grade_assertion(
            _expected(
                "provenance_model_labeled_selfreport_mismatch",
                S.Comparator.EQ, False),
            facts, _mk_axes(model="opus"),
        )
        self.assertTrue(result.passed)

    def test_provenance_bugcount_match(self) -> None:
        facts = _mk_facts()  # provenance_mismatch=False
        result = G.grade_assertion(
            _expected("provenance_bugcount_vs_gate",
                       S.Comparator.EQ, "match"),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)

    def test_provenance_bugcount_expect_mismatch(self) -> None:
        """NATS run2 shape: gate 3 vs reported 0 → `expect_mismatch`."""
        facts = _mk_facts(
            **{"provenance.provenance_mismatch": True},
        )
        result = G.grade_assertion(
            _expected("provenance_bugcount_vs_gate",
                       S.Comparator.EQ, "expect_mismatch"),
            facts, _mk_axes(),
        )
        self.assertTrue(result.passed)


# ---------------------------------------------------------------------------
# Top-level grader entry
# ---------------------------------------------------------------------------


class TopLevelGraderTests(unittest.TestCase):

    def _mk_acceptance_case(self, expected_list) -> S.Case:
        return S.Case(
            id="ACC-T", type=S.CaseType.ACCEPTANCE, title="t",
            inputs=S.CaseInputs(
                repo_url="u", prep=S.PrepPolicy.ACCEPTANCE,
            ),
            expected=expected_list,
        )

    def test_all_passed(self) -> None:
        case = self._mk_acceptance_case([
            _expected("gate_result", S.Comparator.EQ, "PASS"),
            _expected("verdict_state", S.Comparator.EQ, "solid"),
            _expected("banner_rendered", S.Comparator.EQ, True),
        ])
        grading = G.grade_acceptance(
            case, _mk_facts(), _mk_axes(), run_id="rid",
        )
        self.assertEqual(grading.n_total, 3)
        self.assertEqual(grading.n_passed, 3)
        self.assertEqual(grading.n_failed, 0)
        self.assertEqual(grading.verdict, "ALL_PASSED")
        self.assertFalse(grading.reviewed)

    def test_mixed_pass_fail(self) -> None:
        case = self._mk_acceptance_case([
            _expected("gate_result", S.Comparator.EQ, "PASS"),
            _expected("verdict_state", S.Comparator.EQ, "shallow"),
        ])
        grading = G.grade_acceptance(
            case, _mk_facts(), _mk_axes(), run_id="rid",
        )
        self.assertEqual(grading.n_passed, 1)
        self.assertEqual(grading.n_failed, 1)
        self.assertEqual(grading.verdict, "FAILED")

    def test_rejects_security_eval_case(self) -> None:
        case = S.Case(
            id="SEC-T", type=S.CaseType.SECURITY_EVAL,
            title="t",
            inputs=S.CaseInputs(
                repo_url="u", prep=S.PrepPolicy.SECURITY,
            ),
            answer_key=S.AnswerKey(
                cwe="CWE-22", vulnerable_parent="x",
                file="f", symbol="s", behavior="b",
            ),
        )
        with self.assertRaises(G.GraderError) as ctx:
            G.grade_acceptance(
                case, _mk_facts(), _mk_axes(), run_id="rid",
            )
        self.assertIn("non-acceptance", str(ctx.exception))

    def test_grading_json_serializes(self) -> None:
        case = self._mk_acceptance_case([
            _expected("gate_result", S.Comparator.EQ, "PASS"),
        ])
        grading = G.grade_acceptance(
            case, _mk_facts(), _mk_axes(), run_id="rid",
        )
        import json
        # Round-trip the JSON shape.
        as_json = grading.to_json()
        json.dumps(as_json)  # raises if not JSON-serializable
        self.assertEqual(as_json["case_id"], "ACC-T")
        self.assertEqual(as_json["case_type"], "acceptance")
        self.assertEqual(as_json["verdict"], "ALL_PASSED")
        self.assertFalse(as_json["reviewed"])
        self.assertEqual(len(as_json["assertions"]), 1)


if __name__ == "__main__":
    unittest.main()
