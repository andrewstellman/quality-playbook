"""v1.5.7 091 — schema (de)serialization round-trip tests.

Pins the SCHEMA.md §1 case shape + §2 run-invocation shape + §5
fact-object shape against ``bin/harness/schema.py``. A case that
loses or mutates a field on round-trip would fail these tests
before any grader-facing damage occurred.

These tests are part of the SEGREGATED harness functionality
suite per ``QPB_Test_Harness_1.5.7_Implementation_Plan.md`` §4 —
they cover harness internals, NOT skill-release behaviour. The
bundle-safety tests (which ARE in the release gate) live in
``bin/tests/test_publish_safety_090c.py``.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from bin.harness import schema as S


REPO_ROOT = Path(__file__).resolve().parents[3]
CASES_JSON = REPO_ROOT / "repos" / "security-test-cases" / "cases.json"


class CasesJsonLoadTests(unittest.TestCase):
    """The shipped ``cases.json`` parses cleanly — 10 security_eval
    + 1 acceptance per 091.

    NOTE: ``repos/security-test-cases/cases.json`` lives in the
    Cowork-editable data lane and is gitignored at the top level
    (`.gitignore:25: repos/`). On a fresh clone where the file is
    absent, these tests skip-clean — the schema parser is still
    fully covered by the synthetic-case tests below
    (``ExpectedAssertionShapeTests`` / ``CaseJsonRoundTripTests``)
    which don't depend on a disk artifact.
    """

    def setUp(self) -> None:
        if not CASES_JSON.is_file():
            self.skipTest(
                f"{CASES_JSON} absent — Cowork-managed lane "
                f"(gitignored). Schema parser still covered by "
                f"synthetic-case tests below."
            )

    def test_cases_file_parses(self) -> None:
        cases = S.load_cases_file(CASES_JSON)
        # 091 added the type field to the existing 10 security_eval
        # cases + a single ACC-001 smoke. 092 replaced ACC-001 with
        # the full Tier 0-3 acceptance set (ACC-A solid / ACC-B
        # weak_model / ACC-C honest / ACC-D shallow). Total: 14.
        self.assertEqual(len(cases), 14, [c.id for c in cases])

    def test_existing_ten_are_security_eval(self) -> None:
        cases = S.load_cases_file(CASES_JSON)
        sec = [c for c in cases if c.type == S.CaseType.SECURITY_EVAL]
        self.assertEqual(len(sec), 10)
        # Each carries an answer_key and NO expected list.
        for c in sec:
            self.assertIsNotNone(c.answer_key, c.id)
            self.assertIsNone(c.expected, c.id)
            self.assertEqual(c.inputs.prep, S.PrepPolicy.SECURITY)

    def test_acceptance_set_complete(self) -> None:
        """v1.5.7 092: the first acceptance case set is ACC-A /
        ACC-B / ACC-C / ACC-D, one per Tier 2 run-target shape."""
        cases = S.load_cases_file(CASES_JSON)
        acc = [c for c in cases if c.type == S.CaseType.ACCEPTANCE]
        ids = sorted(c.id for c in acc)
        self.assertEqual(ids, ["ACC-A", "ACC-B", "ACC-C", "ACC-D"])
        for a in acc:
            self.assertEqual(a.inputs.prep, S.PrepPolicy.ACCEPTANCE)
            self.assertIsNone(a.answer_key)
            self.assertIsNotNone(a.expected)
            self.assertGreater(len(a.expected), 0)
            # Every expected entry parses to the closed §F vocabulary.
            for e in a.expected:
                self.assertIsInstance(e, S.ExpectedAssertion)
                self.assertIn(e.comparator, list(S.Comparator))


class ExpectedAssertionShapeTests(unittest.TestCase):
    """SCHEMA.md §4: each expected entry is
    ``{assertion, comparator, value}``."""

    def test_well_formed_expected_entry_parses(self) -> None:
        raw = {
            "id": "ACC-X", "type": "acceptance",
            "title": "t",
            "inputs": {"repo_url": "u", "prep": "acceptance"},
            "expected": [
                {"assertion": "verdict_state",
                 "comparator": "==", "value": "shallow"},
            ],
        }
        c = S.parse_case(raw)
        self.assertEqual(len(c.expected), 1)
        self.assertEqual(c.expected[0].assertion, "verdict_state")
        self.assertEqual(c.expected[0].comparator, S.Comparator.EQ)
        self.assertEqual(c.expected[0].value, "shallow")

    def test_missing_assertion_raises(self) -> None:
        raw = {
            "id": "ACC-X", "type": "acceptance",
            "title": "t",
            "inputs": {"repo_url": "u", "prep": "acceptance"},
            "expected": [{"comparator": "==", "value": "shallow"}],
        }
        with self.assertRaises(S.SchemaError) as ctx:
            S.parse_case(raw)
        self.assertIn("assertion", str(ctx.exception))

    def test_bad_comparator_raises(self) -> None:
        raw = {
            "id": "ACC-X", "type": "acceptance",
            "title": "t",
            "inputs": {"repo_url": "u", "prep": "acceptance"},
            "expected": [{"assertion": "verdict_state",
                          "comparator": "<<", "value": "shallow"}],
        }
        with self.assertRaises(S.SchemaError) as ctx:
            S.parse_case(raw)
        self.assertIn("comparator", str(ctx.exception))

    def test_acceptance_with_answer_key_rejected(self) -> None:
        """SCHEMA.md §1: acceptance cases MUST NOT carry an
        answer_key. The loader enforces this so a half-converted
        case can't sneak through."""
        raw = {
            "id": "ACC-X", "type": "acceptance",
            "title": "t",
            "inputs": {"repo_url": "u", "prep": "acceptance"},
            "expected": [],
            "answer_key": {"cwe": "CWE-22", "vulnerable_parent": "x",
                           "file": "f", "symbol": "s",
                           "behavior": "b"},
        }
        with self.assertRaises(S.SchemaError) as ctx:
            S.parse_case(raw)
        self.assertIn("acceptance", str(ctx.exception).lower())

    def test_security_with_expected_rejected(self) -> None:
        """And vice-versa: a security_eval case MUST NOT carry
        an expected list."""
        raw = {
            "id": "SEC-X", "type": "security_eval",
            "inputs": {"repo_url": "u", "prep": "security"},
            "answer_key": {"cwe": "CWE-22", "vulnerable_parent": "x",
                           "file": "f", "symbol": "s",
                           "behavior": "b"},
            "expected": [],
        }
        with self.assertRaises(S.SchemaError) as ctx:
            S.parse_case(raw)
        self.assertIn("expected", str(ctx.exception).lower())


class CaseJsonRoundTripTests(unittest.TestCase):
    """``parse_case(case_to_json(c))`` recovers identical
    enum-typed fields. Optional ``None`` fields are dropped from
    JSON; the recovered case matches on the populated ones."""

    def test_acceptance_case_round_trip(self) -> None:
        original = S.Case(
            id="ACC-X", type=S.CaseType.ACCEPTANCE, title="t",
            inputs=S.CaseInputs(
                repo_url="u", prep=S.PrepPolicy.ACCEPTANCE,
                target_ref="main",
                reference_docs_source="gather",
            ),
            expected=[
                S.ExpectedAssertion(
                    assertion="verdict_state",
                    comparator=S.Comparator.EQ,
                    value="solid",
                ),
            ],
        )
        as_json = S.case_to_json(original)
        recovered = S.parse_case(as_json)
        self.assertEqual(recovered.id, original.id)
        self.assertEqual(recovered.type, original.type)
        self.assertEqual(recovered.title, original.title)
        self.assertEqual(recovered.inputs.repo_url,
                         original.inputs.repo_url)
        self.assertEqual(recovered.inputs.prep, original.inputs.prep)
        self.assertEqual(recovered.expected[0].assertion,
                         original.expected[0].assertion)
        self.assertEqual(recovered.expected[0].comparator,
                         original.expected[0].comparator)
        self.assertEqual(recovered.expected[0].value,
                         original.expected[0].value)


class InvocationJsonRoundTripTests(unittest.TestCase):
    """SCHEMA.md §3: registry channels carry an ``@<version>``
    suffix in JSON. The parser splits it into
    ``(InstallChannel, install_version)``; serialization
    re-attaches it."""

    def test_clone_channel_round_trip(self) -> None:
        inv = S.RunInvocation(
            run_id="20260525T140000Z",
            case_id="ACC-001",
            axes=S.RunAxes(
                runner=S.Runner.CLAUDE,
                mode=S.Mode.A,
                install_channel=S.InstallChannel.CLONE,
                install_version=None,
                model="opus",
                thinking="high",
            ),
            qpb_version="1.5.7",
            target_sha="abc123",
            cli_command="claude --print ...",
            cwd="/tmp/t",
            env_snapshot={"CLAUDECODE": "1"},
            started_at="2026-05-25T14:00:00Z",
            ended_at="2026-05-25T14:10:00Z",
            exit_code=0,
            terminal_state=S.TerminalState.COMPLETED,
        )
        raw = S.run_invocation_to_json(inv)
        # No '@' suffix when channel is non-registry.
        self.assertEqual(raw["axes"]["install_channel"], "clone")
        recovered = S.parse_run_invocation(raw)
        self.assertEqual(recovered.axes.install_channel,
                         S.InstallChannel.CLONE)
        self.assertIsNone(recovered.axes.install_version)
        self.assertEqual(recovered.terminal_state,
                         S.TerminalState.COMPLETED)

    def test_registry_channel_at_suffix_round_trip(self) -> None:
        """``pip-registry@1.5.7`` in JSON ↔ ``(PIP_REGISTRY,
        install_version='1.5.7')`` in the dataclass."""
        inv = S.RunInvocation(
            run_id="20260525T140000Z",
            case_id="ACC-001",
            axes=S.RunAxes(
                runner=S.Runner.CLAUDE,
                mode=S.Mode.A,
                install_channel=S.InstallChannel.PIP_REGISTRY,
                install_version="1.5.7",
                model="opus",
            ),
            qpb_version="1.5.7",
            target_sha="abc",
            cli_command="x",
            cwd="/t",
            env_snapshot={},
            started_at="x", ended_at="y",
            exit_code=0,
            terminal_state=S.TerminalState.COMPLETED,
        )
        raw = S.run_invocation_to_json(inv)
        self.assertEqual(raw["axes"]["install_channel"],
                         "pip-registry@1.5.7")
        # Round-trip via the raw JSON string (the at-suffix is
        # the SCHEMA.md §3 canonical wire form).
        recovered = S.parse_run_invocation(raw)
        self.assertEqual(recovered.axes.install_channel,
                         S.InstallChannel.PIP_REGISTRY)
        self.assertEqual(recovered.axes.install_version, "1.5.7")


class GateResultMappingTests(unittest.TestCase):
    """SCHEMA.md §5 raw → enum mapping (longest-match-first to
    avoid CLEANUP collapsing into PASS)."""

    def test_gate_passed_cleanup_needed_maps_to_cleanup(self) -> None:
        gr = S.gate_result_from_raw(
            "GATE PASSED WITH CLEANUP NEEDED — 2 audit gap(s)",
        )
        self.assertEqual(gr, S.GateResult.CLEANUP)

    def test_gate_passed_maps_to_pass(self) -> None:
        self.assertEqual(
            S.gate_result_from_raw("GATE PASSED"),
            S.GateResult.PASS,
        )

    def test_gate_failed_maps_to_fail(self) -> None:
        self.assertEqual(
            S.gate_result_from_raw(
                "GATE FAILED — 3 substantive issue(s) must be fixed",
            ),
            S.GateResult.FAIL,
        )


class RunFactsRoundTripTests(unittest.TestCase):
    """The fact object serializes + parses without loss."""

    def _sample(self) -> S.RunFacts:
        return S.RunFacts(
            phase0=S.Phase0Facts(status="ok", probe_attempts=1,
                                   first_probe_ok=True),
            verdict=S.VerdictFacts(
                verdict_state=S.VerdictState.SHALLOW,
                attribution=S.Attribution.NONE,
                recommends_stronger_model=False,
                bugs_unverified_present=False,
            ),
            provenance=S.ProvenanceFacts(
                detected_runner="claude-code",
                selfreport_model_label="opus",
                gate_bug_count=0,
                reported_bug_count=None,
                provenance_mismatch=False,
            ),
            gate=S.GateFacts(
                gate_total="Total: 0 FAIL, 3 WARN",
                gate_result=S.GateResult.PASS,
                cleanup_gaps=0,
            ),
            install=S.InstallSurfaceFacts(
                banner_rendered=True,
                gitignore_remediation_followed=False,
            ),
            run_meta=S.RunMetaFacts(
                blocked=False,
                stop_reason=None,
                exit_code=0,
                timings={"prep_s": 4.2, "run_s": 600},
                raw_receipt="stream.ndjson",
            ),
        )

    def test_round_trip(self) -> None:
        facts = self._sample()
        raw = S.run_facts_to_json(facts)
        recovered = S.parse_run_facts(raw)
        # Enums recover as enum members.
        self.assertEqual(recovered.verdict.verdict_state,
                         S.VerdictState.SHALLOW)
        self.assertEqual(recovered.verdict.attribution,
                         S.Attribution.NONE)
        self.assertEqual(recovered.gate.gate_result,
                         S.GateResult.PASS)
        # Numeric + bool fields preserved.
        self.assertEqual(recovered.phase0.probe_attempts, 1)
        self.assertTrue(recovered.phase0.first_probe_ok)
        self.assertEqual(recovered.run_meta.timings["run_s"], 600)


if __name__ == "__main__":
    unittest.main()
