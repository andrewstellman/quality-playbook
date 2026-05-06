"""Unit tests for ``bin/run_state_lib.py``.

Covers the surface specified in the v1.5.5 schema doc
(`references/run_state_schema.md`): event reading and parsing,
in-progress phase detection, per-phase artifact cross-validation,
file-level format invariants, PROGRESS.md rendering, and the
append-event guard. Each test stages its fixtures inside a
``TemporaryDirectory`` to keep the test suite hermetic.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import run_state_lib as lib


# Default event-type whitelist used by fixture files. Wide enough that
# tests don't have to thread it through individually.
_DEFAULT_EVENT_TYPES = [
    "_index",
    "run_start",
    "phase_start",
    "phase_end",
    "pattern_walked",
    "pass_started",
    "pass_ended",
    "finding_logged",
    "artifact_written",
    "gate_check",
    "error",
    "run_end",
]


def _index_line(event_types: list[str] | None = None) -> dict:
    return {
        "event": "_index",
        "ts": "2026-05-15T14:00:00Z",
        "schema_version": "1.5.5",
        "event_types": event_types or _DEFAULT_EVENT_TYPES,
        "benchmark": "chi-1.5.1",
        "lever_state": "post-pattern7",
        "started_at": "2026-05-15T14:00:00Z",
    }


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for ev in events:
            handle.write(json.dumps(ev) + "\n")


class ReadEventsTests(unittest.TestCase):
    def test_read_events_empty_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run_state.jsonl"
            path.write_text("", encoding="utf-8")
            self.assertEqual(lib.read_events(path), [])

    def test_read_events_well_formed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run_state.jsonl"
            events = [
                _index_line(),
                {
                    "event": "run_start",
                    "ts": "2026-05-15T14:00:01Z",
                    "runner": "claude",
                    "playbook_version": "1.5.5",
                    "target_path": "repos/archive/chi-1.5.1",
                },
                {
                    "event": "phase_start",
                    "ts": "2026-05-15T14:00:02Z",
                    "phase": 1,
                },
                {
                    "event": "artifact_written",
                    "ts": "2026-05-15T14:10:00Z",
                    "relative_path": "quality/EXPLORATION.md",
                    "byte_size": 12034,
                },
                {
                    "event": "phase_end",
                    "ts": "2026-05-15T14:10:01Z",
                    "phase": 1,
                    "key_counts": {"findings_total": 12, "patterns_walked": 7},
                    "artifacts_produced": ["quality/EXPLORATION.md"],
                },
            ]
            _write_jsonl(path, events)
            parsed = lib.read_events(path)
            self.assertEqual(len(parsed), 5)
            self.assertEqual(parsed[0].event, "_index")
            self.assertEqual(parsed[0].fields["schema_version"], "1.5.5")
            self.assertEqual(parsed[2].event, "phase_start")
            self.assertEqual(parsed[2].fields["phase"], 1)
            # Required ts/event fields should be split out, not also
            # duplicated into Event.fields.
            self.assertNotIn("ts", parsed[0].fields)
            self.assertNotIn("event", parsed[0].fields)

    def test_read_events_malformed_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run_state.jsonl"
            path.write_text(
                json.dumps(_index_line()) + "\n"
                + "{ this is not valid json\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as ctx:
                lib.read_events(path)
            self.assertIn("line 2", str(ctx.exception))


class LastInProgressPhaseTests(unittest.TestCase):
    def _events_for_phases(self, *, completed: list[int],
                           in_progress: list[int]) -> list[lib.Event]:
        events: list[lib.Event] = []
        for phase in completed:
            events.append(lib.Event(
                ts=f"2026-05-15T14:00:0{phase}Z",
                event="phase_start",
                fields={"phase": phase},
            ))
            events.append(lib.Event(
                ts=f"2026-05-15T14:00:0{phase}Z",
                event="phase_end",
                fields={"phase": phase, "key_counts": {}},
            ))
        for phase in in_progress:
            events.append(lib.Event(
                ts=f"2026-05-15T14:00:0{phase}Z",
                event="phase_start",
                fields={"phase": phase},
            ))
        return events

    def test_last_in_progress_phase_none_when_complete(self) -> None:
        events = self._events_for_phases(
            completed=[1, 2, 3, 4, 5, 6], in_progress=[],
        )
        self.assertIsNone(lib.last_in_progress_phase(events))

    def test_last_in_progress_phase_finds_phase4(self) -> None:
        events = self._events_for_phases(
            completed=[1, 2, 3], in_progress=[4],
        )
        self.assertEqual(lib.last_in_progress_phase(events), 4)

    def test_last_in_progress_phase_none_on_empty(self) -> None:
        self.assertIsNone(lib.last_in_progress_phase([]))


class ValidatePhaseArtifactsTests(unittest.TestCase):
    def test_validate_phase_artifacts_phase1_missing_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("EXPLORATION.md", reason)

    def test_validate_phase_artifacts_phase1_present(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            # v1.5.6 BUG-005: Phase 1 validator now requires ≥120 lines
            # (aligned with Phase 2 startup gate); pad with ≥120 lines.
            body_lines = ["filler line " + str(i) for i in range(150)]
            content = (
                "# Exploration\n\n"
                "## Finding 1: something interesting\n\n"
                + "\n".join(body_lines)
                + "\n"
            )
            (quality / "EXPLORATION.md").write_text(
                content, encoding="utf-8"
            )
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertTrue(ok, msg=reason)
            self.assertEqual(reason, "")

    def test_validate_phase_artifacts_phase1_open_exploration_findings_heading(self) -> None:
        """v1.5.6 BUG-004: the SKILL.md-prescribed exact heading
        ``## Open Exploration Findings`` (SKILL.md:1133, 1209, 1260)
        was rejected by the pre-fix regex. After the fix it must be
        accepted."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            body_lines = ["finding entry " + str(i) for i in range(150)]
            content = (
                "# Exploration\n\n"
                "## Open Exploration Findings\n\n"
                + "\n".join(body_lines)
                + "\n"
            )
            (quality / "EXPLORATION.md").write_text(
                content, encoding="utf-8"
            )
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertTrue(
                ok,
                msg=f"BUG-004 regression: '## Open Exploration Findings' "
                f"rejected as invalid Phase 1 finding section. reason={reason!r}",
            )

    def test_validate_phase_artifacts_phase1_too_short(self) -> None:
        """v1.5.6 BUG-005: short EXPLORATION.md fails on the 120-line
        threshold (was 200-byte pre-fix). The reason string must
        mention the line-count threshold so operators can fix it."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "EXPLORATION.md").write_text(
                "## Finding 1\nshort\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("120", reason)
            self.assertIn("lines", reason)

    def test_validate_phase_artifacts_phase1_threshold_matches_phase2_gate(self) -> None:
        """v1.5.6 BUG-005: Phase 1 validator and Phase 2 startup gate
        share a single threshold (120 lines). A 119-line EXPLORATION.md
        with a finding section must FAIL the Phase 1 validator (so it
        cannot pass Phase 1 and then immediately fail Phase 2 startup)
        — and a 120-line EXPLORATION.md must PASS."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            # Build a 119-line EXPLORATION.md with a valid finding heading.
            body_119 = ["## Finding 1\n"] + ["x\n"] * 117 + ["x"]
            self.assertEqual(len("".join(body_119).splitlines()), 119)
            (quality / "EXPLORATION.md").write_text(
                "".join(body_119), encoding="utf-8"
            )
            ok_119, reason_119 = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(
                ok_119,
                "Phase 1 validator must reject a 119-line "
                "EXPLORATION.md; Phase 2 startup gate would also "
                "reject it. (BUG-005 alignment.)"
            )

            # 120-line file passes.
            body_120 = ["## Finding 1\n"] + ["x\n"] * 118 + ["x"]
            self.assertEqual(len("".join(body_120).splitlines()), 120)
            (quality / "EXPLORATION.md").write_text(
                "".join(body_120), encoding="utf-8"
            )
            ok_120, reason_120 = lib.validate_phase_artifacts(quality, 1)
            self.assertTrue(
                ok_120,
                f"Phase 1 validator must accept a 120-line "
                f"EXPLORATION.md (matches Phase 2 startup gate). "
                f"reason={reason_120!r}"
            )

    def test_validate_phase_artifacts_phase1_no_finding_section(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            # ≥120 lines but no finding section — must fail on the
            # heading-regex check, not the line-count check.
            body_lines = ["filler line " + str(i) for i in range(150)]
            (quality / "EXPLORATION.md").write_text(
                "\n".join(body_lines) + "\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("finding section", reason)

    def test_validate_phase_artifacts_phase2_generate_contract(self) -> None:
        """v1.5.6 BUG-014 (Conclusion C): Phase 2 validator must check
        the shipped Generate contract — REQUIREMENTS.md, QUALITY.md,
        CONTRACTS.md, COVERAGE_MATRIX.md, COMPLETENESS_REPORT.md,
        RUN_CODE_REVIEW.md, RUN_INTEGRATION_TESTS.md, RUN_SPEC_AUDIT.md,
        RUN_TDD_TESTS.md, plus one test_functional.<ext> file. The
        pre-fix validator checked the v1.5.5-design triage artifacts
        (EXPLORATION_MERGED.md, triage.md) which were never adopted
        in the shipped SKILL.md."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)

            # Empty quality_dir — must fail with the first missing artifact.
            ok, reason = lib.validate_phase_artifacts(quality, 2)
            self.assertFalse(ok)
            self.assertIn("REQUIREMENTS.md", reason)

            # Stage all nine fixed-name Generate-contract artifacts as
            # non-empty files.
            for name in (
                "REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md",
                "COVERAGE_MATRIX.md", "COMPLETENESS_REPORT.md",
                "RUN_CODE_REVIEW.md", "RUN_INTEGRATION_TESTS.md",
                "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
            ):
                (quality / name).write_text("body\n", encoding="utf-8")

            # Still missing test_functional.<ext> — must fail.
            ok, reason = lib.validate_phase_artifacts(quality, 2)
            self.assertFalse(ok)
            self.assertIn("test_functional", reason)

            # Add a Python test_functional file — passes.
            (quality / "test_functional.py").write_text(
                "def test_x(): pass\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 2)
            self.assertTrue(ok, msg=reason)

    def test_validate_phase_artifacts_phase2_rejects_empty_artifact(self) -> None:
        """An empty artifact (zero bytes) must fail with an 'empty'
        diagnostic so operators know the file exists but has no
        content."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            for name in (
                "REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md",
                "COVERAGE_MATRIX.md", "COMPLETENESS_REPORT.md",
                "RUN_CODE_REVIEW.md", "RUN_INTEGRATION_TESTS.md",
                "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
            ):
                (quality / name).write_text("body\n", encoding="utf-8")
            # CONTRACTS.md exists but is empty.
            (quality / "CONTRACTS.md").write_text("", encoding="utf-8")
            (quality / "test_functional.py").write_text(
                "def test_x(): pass\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 2)
            self.assertFalse(ok)
            self.assertIn("CONTRACTS.md", reason)
            self.assertIn("empty", reason)

    def test_validate_phase_artifacts_phase2_accepts_polyglot_test_functional(self) -> None:
        """A target with multiple test_functional.* files (e.g. a
        polyglot repo with .py + .go) passes as long as at least one
        is non-empty. The contract is "one functional-test file
        exists per project"; the validator is permissive about
        multiple."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            for name in (
                "REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md",
                "COVERAGE_MATRIX.md", "COMPLETENESS_REPORT.md",
                "RUN_CODE_REVIEW.md", "RUN_INTEGRATION_TESTS.md",
                "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
            ):
                (quality / name).write_text("body\n", encoding="utf-8")
            # Empty .py file but a non-empty .go file — still passes
            # because the validator's contract is "at least one
            # non-empty test_functional.*".
            (quality / "test_functional.py").write_text("", encoding="utf-8")
            (quality / "test_functional.go").write_text(
                "func TestX(t *testing.T) {}\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 2)
            self.assertTrue(ok, msg=reason)

    # v1.5.6 cluster B: Phase 3 = Code Review per shipped pipeline.
    # Required artifacts: quality/code_reviews/ has ≥1 review file.
    # Conditional: if BUGS.md has confirmed bugs, every confirmed bug
    # has a regression-test patch under quality/patches/. The
    # pre-cluster-B Phase 3 check (RUN_CODE_REVIEW.md alone) was the
    # v1.5.5 design's Phase 2-side mapping; that file is actually a
    # Phase 2 Generate output (the protocol document), not a Phase 3
    # review result.

    def test_validate_phase_artifacts_phase3_requires_code_reviews_dir(self) -> None:
        """Phase 3 must produce at least one review file under
        quality/code_reviews/."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            ok, reason = lib.validate_phase_artifacts(quality, 3)
            self.assertFalse(ok)
            self.assertIn("code_reviews", reason)
            (quality / "code_reviews").mkdir()
            ok, reason = lib.validate_phase_artifacts(quality, 3)
            self.assertFalse(ok)
            self.assertIn("no review files", reason)
            (quality / "code_reviews" / "2026-05-06-review.md").write_text(
                "# Review\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 3)
            self.assertTrue(ok, msg=reason)

    def test_validate_phase_artifacts_phase3_conditional_regression_patches(self) -> None:
        """If BUGS.md has confirmed BUG entries, Phase 3 also requires
        regression-test patches under quality/patches/. With no BUGS.md
        or empty BUGS.md, the patch check is skipped."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "code_reviews").mkdir()
            (quality / "code_reviews" / "review.md").write_text(
                "# r\n", encoding="utf-8",
            )
            # No BUGS.md → passes (no bugs to track).
            ok, _ = lib.validate_phase_artifacts(quality, 3)
            self.assertTrue(ok)
            # BUGS.md with no entries → still passes.
            (quality / "BUGS.md").write_text(
                "# BUGS\n\nNo bugs yet.\n", encoding="utf-8",
            )
            ok, _ = lib.validate_phase_artifacts(quality, 3)
            self.assertTrue(ok)
            # BUGS.md with a confirmed bug + no patches/ → fails.
            (quality / "BUGS.md").write_text(
                "# BUGS\n\n### BUG-001: example\n\nbody\n",
                encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 3)
            self.assertFalse(ok)
            self.assertIn("patches", reason)
            # patches/ exists but no regression-test patch → fails.
            (quality / "patches").mkdir()
            ok, reason = lib.validate_phase_artifacts(quality, 3)
            self.assertFalse(ok)
            self.assertIn("regression-test", reason)
            # Regression-test patch present → passes.
            (quality / "patches" / "BUG-001-regression-test.patch").write_text(
                "diff --git ...\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 3)
            self.assertTrue(ok, msg=reason)

    def test_validate_phase_artifacts_phase4_spec_audit_contract(self) -> None:
        """Phase 4 = Spec Audit. quality/spec_audits/ must contain at
        least one triage file AND at least one auditor file (per the
        orchestrator_protocol.md naming convention). Pre-cluster-B
        this branch checked REQUIREMENTS.md + COVERAGE_MATRIX.md —
        those are Phase 2 Generate outputs, not Phase 4 outputs."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertFalse(ok)
            self.assertIn("spec_audits", reason)
            (quality / "spec_audits").mkdir()
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertFalse(ok)
            self.assertIn("no .md files", reason)
            # Only auditor file → fails (triage missing).
            (quality / "spec_audits" / "2026-05-06-auditor-1.md").write_text(
                "# auditor\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertFalse(ok)
            self.assertIn("triage", reason)
            # Both file types → passes.
            (quality / "spec_audits" / "2026-05-06-triage.md").write_text(
                "# triage\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertTrue(ok, msg=reason)

    def test_validate_phase_artifacts_phase4_fallback_two_files_when_no_naming_convention(self) -> None:
        """When the spec_audits/ files don't use the canonical
        triage/auditor naming, the validator falls back to a weaker
        '≥2 files' check + a hint to use the canonical names. This
        keeps backward-compat with older bootstrap runs."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "spec_audits").mkdir()
            # One arbitrarily-named file → fails.
            (quality / "spec_audits" / "report-a.md").write_text(
                "# a\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertFalse(ok)
            self.assertIn("fewer than 2", reason)
            self.assertIn("naming convention", reason)
            # Two arbitrarily-named files → passes (fallback).
            (quality / "spec_audits" / "report-b.md").write_text(
                "# b\n", encoding="utf-8",
            )
            ok, _ = lib.validate_phase_artifacts(quality, 4)
            self.assertTrue(ok)

    def test_validate_phase_artifacts_phase5_no_bugs_passes(self) -> None:
        """Phase 5 = Reconciliation, conditional on confirmed bugs.
        With no BUGS.md or empty BUGS.md, the validator passes (the
        contract says "if bugs were confirmed, then ...")."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            # No BUGS.md → passes.
            ok, _ = lib.validate_phase_artifacts(quality, 5)
            self.assertTrue(ok)
            # BUGS.md with no entries → passes.
            (quality / "BUGS.md").write_text(
                "# BUGS\n\nNo bugs yet.\n", encoding="utf-8",
            )
            ok, _ = lib.validate_phase_artifacts(quality, 5)
            self.assertTrue(ok)

    def test_validate_phase_artifacts_phase5_requires_writeups_and_red_logs(self) -> None:
        """When BUGS.md has confirmed bugs, Phase 5 requires
        tdd-results.json AND a writeup AND a red-phase log per bug."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "BUGS.md").write_text(
                "# BUGS\n\n### BUG-001: example\n\nbody\n"
                "### BUG-002: another\n\nbody\n",
                encoding="utf-8",
            )
            # No tdd-results.json → fails.
            ok, reason = lib.validate_phase_artifacts(quality, 5)
            self.assertFalse(ok)
            self.assertIn("tdd-results.json", reason)
            (quality / "results").mkdir()
            (quality / "results" / "tdd-results.json").write_text(
                '{"bugs":[]}\n', encoding="utf-8",
            )
            # Missing writeup → fails.
            ok, reason = lib.validate_phase_artifacts(quality, 5)
            self.assertFalse(ok)
            self.assertIn("writeup", reason)
            self.assertIn("BUG-001", reason)
            (quality / "writeups").mkdir()
            (quality / "writeups" / "BUG-001.md").write_text(
                "# w1\n", encoding="utf-8",
            )
            (quality / "writeups" / "BUG-002.md").write_text(
                "# w2\n", encoding="utf-8",
            )
            # Missing red-phase log → fails.
            ok, reason = lib.validate_phase_artifacts(quality, 5)
            self.assertFalse(ok)
            self.assertIn("red", reason)
            self.assertIn("BUG-001", reason)
            (quality / "results" / "BUG-001.red.log").write_text(
                "RED\n", encoding="utf-8",
            )
            (quality / "results" / "BUG-002.red.log").write_text(
                "RED\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 5)
            self.assertTrue(ok, msg=reason)

    def test_phase_names_dict_matches_shipped_pipeline(self) -> None:
        """v1.5.6 cluster B: pin the phase_names dict in
        write_progress_md against the shipped pipeline labels documented
        in references/orchestrator_protocol.md and SKILL.md
        (1=Explore / 2=Generate / 3=Code Review / 4=Spec Audit /
        5=Reconciliation / 6=Verify). A future drift back to the
        v1.5.5 design's Triage-model labels (the BUG-014 / BUG-009
        regression shape) trips this test."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            events = [
                lib.Event(
                    ts="2026-05-15T14:32:01Z",
                    event="_index",
                    fields={
                        "started_at": "2026-05-15T14:32:01Z",
                        "benchmark": "fake-bench",
                        "lever_state": "baseline",
                    },
                ),
            ]
            # Render with no current phase so every phase shows as
            # `- [ ] Phase N — <name>` for label parity check.
            lib.write_progress_md(quality, events, current_phase=None)
            text = (quality / "PROGRESS.md").read_text(encoding="utf-8")
            for n, name in (
                (1, "Explore"),
                (2, "Generate"),
                (3, "Code Review"),
                (4, "Spec Audit"),
                (5, "Reconciliation"),
                (6, "Verify"),
            ):
                self.assertIn(
                    f"- [ ] Phase {n} — {name}", text,
                    f"PROGRESS.md missing shipped-pipeline label for "
                    f"phase {n}: expected {name!r}. The phase_names "
                    f"dict in bin/run_state_lib.write_progress_md must "
                    f"match the shipped pipeline documented in "
                    f"references/orchestrator_protocol.md.",
                )
            # Forbid the v1.5.5 design's Triage-model labels — drift
            # back to those is the BUG-009/014/019 regression shape.
            for stale in (
                "Phase 2 — Triage",
                "Phase 3 — Investigation",
                "Phase 4 — Skill-derivation",
                "Phase 6 — Release readiness",
            ):
                self.assertNotIn(
                    stale, text,
                    f"PROGRESS.md contains stale v1.5.5-design label "
                    f"{stale!r} — phase_names dict drifted back to the "
                    f"never-shipped Triage-model mapping.",
                )

    def test_validate_phase_artifacts_phase6_verify_contract(self) -> None:
        """Phase 6 = Verify. Required: quality-gate.log non-empty AND
        PROGRESS.md contains a 'Terminal Gate Verification' section.
        Pre-cluster-B this branch required BUGS.md + INDEX.md, which
        was the v1.5.5 design's mapping (BUGS.md is a Phase 3
        output; INDEX.md was never adopted in the shipped contract)."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            ok, reason = lib.validate_phase_artifacts(quality, 6)
            self.assertFalse(ok)
            self.assertIn("quality-gate.log", reason)
            (quality / "results").mkdir()
            (quality / "results" / "quality-gate.log").write_text(
                "", encoding="utf-8"
            )
            ok, reason = lib.validate_phase_artifacts(quality, 6)
            self.assertFalse(ok)
            self.assertIn("empty", reason)
            (quality / "results" / "quality-gate.log").write_text(
                "GATE PASSED\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 6)
            self.assertFalse(ok)
            self.assertIn("PROGRESS.md", reason)
            (quality / "PROGRESS.md").write_text(
                "# Progress\n\n[x] Phase 6 done\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 6)
            self.assertFalse(ok)
            self.assertIn("Terminal Gate Verification", reason)
            (quality / "PROGRESS.md").write_text(
                "# Progress\n\n## Terminal Gate Verification\n\nPASSED\n",
                encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 6)
            self.assertTrue(ok, msg=reason)


class ValidateRunStateFileTests(unittest.TestCase):
    def test_validate_run_state_file_index_not_first(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run_state.jsonl"
            events = [
                {
                    "event": "run_start",
                    "ts": "2026-05-15T14:00:01Z",
                    "runner": "claude",
                },
                _index_line(),
            ]
            _write_jsonl(path, events)
            ok, violations = lib.validate_run_state_file(path)
            self.assertFalse(ok)
            self.assertTrue(
                any("first event must be '_index'" in v for v in violations),
                msg=violations,
            )

    def test_validate_run_state_file_well_formed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run_state.jsonl"
            events = [
                _index_line(),
                {
                    "event": "run_start",
                    "ts": "2026-05-15T14:00:01Z",
                    "runner": "claude",
                },
                {
                    "event": "phase_start",
                    "ts": "2026-05-15T14:00:02Z",
                    "phase": 1,
                },
                {
                    "event": "phase_end",
                    "ts": "2026-05-15T14:10:00Z",
                    "phase": 1,
                    "key_counts": {"findings_total": 3},
                },
            ]
            _write_jsonl(path, events)
            ok, violations = lib.validate_run_state_file(path)
            self.assertTrue(ok, msg=violations)
            self.assertEqual(violations, [])

    def test_validate_run_state_file_duplicate_phase_start(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run_state.jsonl"
            events = [
                _index_line(),
                {
                    "event": "phase_start",
                    "ts": "2026-05-15T14:00:01Z",
                    "phase": 1,
                },
                {
                    "event": "phase_start",
                    "ts": "2026-05-15T14:00:02Z",
                    "phase": 1,
                },
            ]
            _write_jsonl(path, events)
            ok, violations = lib.validate_run_state_file(path)
            self.assertFalse(ok)
            self.assertTrue(
                any("duplicate phase_start" in v for v in violations),
                msg=violations,
            )

    def test_validate_run_state_file_unknown_event_type(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run_state.jsonl"
            events = [
                _index_line(event_types=["_index", "phase_start"]),
                {
                    "event": "phase_start",
                    "ts": "2026-05-15T14:00:01Z",
                    "phase": 1,
                },
                {
                    "event": "mystery_event",
                    "ts": "2026-05-15T14:00:02Z",
                },
            ]
            _write_jsonl(path, events)
            ok, violations = lib.validate_run_state_file(path)
            self.assertFalse(ok)
            self.assertTrue(
                any("mystery_event" in v for v in violations),
                msg=violations,
            )


class WriteProgressMdTests(unittest.TestCase):
    def test_write_progress_md_renders_correctly(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            events = [
                lib.Event(
                    ts="2026-05-15T14:32:01Z",
                    event="_index",
                    fields={
                        "schema_version": "1.5.5",
                        "event_types": _DEFAULT_EVENT_TYPES,
                        "benchmark": "chi-1.5.1",
                        "lever_state": "post-pattern7",
                        "started_at": "2026-05-15T14:32:01Z",
                    },
                ),
                lib.Event(
                    ts="2026-05-15T14:32:02Z",
                    event="run_start",
                    fields={
                        "runner": "claude",
                        "playbook_version": "1.5.5",
                        "target_path": "repos/archive/chi-1.5.1",
                    },
                ),
                lib.Event(
                    ts="2026-05-15T14:32:03Z",
                    event="phase_start",
                    fields={"phase": 1},
                ),
                lib.Event(
                    ts="2026-05-15T14:42:11Z",
                    event="phase_end",
                    fields={
                        "phase": 1,
                        "key_counts": {
                            "findings_total": 12,
                            "patterns_walked": 7,
                        },
                        "duration_seconds": 610,
                    },
                ),
                lib.Event(
                    ts="2026-05-15T14:42:12Z",
                    event="artifact_written",
                    fields={
                        "relative_path": "quality/EXPLORATION.md",
                        "byte_size": 12034,
                    },
                ),
                lib.Event(
                    ts="2026-05-15T14:58:31Z",
                    event="phase_start",
                    fields={"phase": 5},
                ),
            ]
            lib.write_progress_md(quality, events, current_phase=5)
            text = (quality / "PROGRESS.md").read_text(encoding="utf-8")
            self.assertIn("# QPB Run Progress", text)
            self.assertIn("**Started:** 2026-05-15T14:32:01Z", text)
            self.assertIn("**Benchmark:** chi-1.5.1", text)
            self.assertIn("**Runner:** claude", text)
            self.assertIn("**Playbook version:** 1.5.5", text)
            # v1.5.6 cluster B: phase_names matches shipped pipeline
            # (Explore / Generate / Code Review / Spec Audit /
            # Reconciliation / Verify) — pre-cluster-B labels were
            # the v1.5.5 design's never-shipped Triage-model names.
            self.assertIn("- [x] Phase 1 — Explore", text)
            self.assertIn("findings_total=12", text)
            self.assertIn("patterns_walked=7", text)
            self.assertIn(
                "- [ ] Phase 5 — Reconciliation "
                "*(in progress, started 2026-05-15T14:58:31Z)*",
                text,
            )
            self.assertIn("- [ ] Phase 6 — Verify", text)
            self.assertIn("## Recent events (last 10)", text)
            self.assertIn("## Artifacts produced", text)
            self.assertIn("quality/EXPLORATION.md (12,034 bytes)", text)


class AppendEventTests(unittest.TestCase):
    def test_append_event_writes_single_line(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run_state.jsonl"
            lib.append_event(
                path,
                {
                    "event": "phase_start",
                    "ts": "2026-05-15T14:00:01Z",
                    "phase": 1,
                },
            )
            lib.append_event(
                path,
                {
                    "event": "phase_end",
                    "ts": "2026-05-15T14:10:00Z",
                    "phase": 1,
                },
            )
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["event"], "phase_start")
            self.assertEqual(json.loads(lines[1])["event"], "phase_end")

    def test_append_event_missing_ts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run_state.jsonl"
            with self.assertRaises(ValueError) as ctx:
                lib.append_event(path, {"event": "phase_start", "phase": 1})
            self.assertIn("'ts'", str(ctx.exception))

    def test_append_event_missing_event(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run_state.jsonl"
            with self.assertRaises(ValueError):
                lib.append_event(path, {"ts": "2026-05-15T14:00:00Z"})


class ValidateNoSourceEditsTests(unittest.TestCase):
    """v1.5.5 Item B: ``validate_no_source_edits`` is the run-end
    post-condition that catches Phase 5 going off-rails and editing
    files outside ``quality/``.

    Tests stage a real git repo in a tempdir so the helper's
    ``git status --porcelain`` shell-out runs against actual git
    plumbing rather than a mock — the bug class this guards against
    surfaced precisely because mocking the repo state lets a buggy
    parser pass tests that real ``git status`` output would fail.
    """

    def _init_repo(self, root: Path) -> None:
        """Create a tiny git repo with a quality/ tree and a few
        source-tree files committed."""
        import subprocess

        def run(*args: str) -> None:
            subprocess.run(
                ["git", *args],
                cwd=str(root),
                check=True,
                capture_output=True,
                text=True,
            )

        run("init", "-q")
        run("config", "user.email", "test@example.com")
        run("config", "user.name", "Test")
        run("config", "commit.gpgsign", "false")
        (root / "src").mkdir()
        (root / "quality").mkdir()
        (root / "src" / "code.py").write_text("print('hi')\n", encoding="utf-8")
        (root / "README.md").write_text("# Test repo\n", encoding="utf-8")
        (root / "quality" / "BUGS.md").write_text(
            "# Bugs\n", encoding="utf-8"
        )
        run("add", ".")
        run("commit", "-q", "-m", "initial")

    def test_clean_repo_returns_true(self) -> None:
        """A repo with no modifications is trivially clean."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_repo(root)
            ok, violations = lib.validate_no_source_edits(root)
            self.assertTrue(ok)
            self.assertEqual(violations, [])

    def test_quality_only_modifications_are_allowed(self) -> None:
        """The clean case — only files inside quality/ are dirty."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_repo(root)
            (root / "quality" / "BUGS.md").write_text(
                "# Bugs\n## BUG-001\n", encoding="utf-8"
            )
            (root / "quality" / "patches").mkdir()
            (root / "quality" / "patches" / "BUG-001-fix.patch").write_text(
                "--- a/x\n+++ b/x\n", encoding="utf-8"
            )
            ok, violations = lib.validate_no_source_edits(root)
            self.assertTrue(ok, f"unexpected violations: {violations}")
            self.assertEqual(violations, [])

    def test_source_file_modification_is_a_violation(self) -> None:
        """The defect case — Phase 5 mutated a source file."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_repo(root)
            (root / "src" / "code.py").write_text(
                "print('phase 5 went off the rails')\n", encoding="utf-8"
            )
            ok, violations = lib.validate_no_source_edits(root)
            self.assertFalse(ok)
            self.assertEqual(violations, ["src/code.py"])

    def test_untracked_source_file_is_a_violation(self) -> None:
        """An untracked file outside quality/ also flags — Phase 5
        producing a stray ``patch.rej`` at the repo root counts."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_repo(root)
            (root / "patch.rej").write_text("conflict\n", encoding="utf-8")
            ok, violations = lib.validate_no_source_edits(root)
            self.assertFalse(ok)
            self.assertEqual(violations, ["patch.rej"])

    def test_untracked_quality_file_is_allowed(self) -> None:
        """Untracked files INSIDE quality/ are normal Phase 5 output."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_repo(root)
            (root / "quality" / "REQUIREMENTS.md").write_text(
                "# REQs\n", encoding="utf-8"
            )
            ok, violations = lib.validate_no_source_edits(root)
            self.assertTrue(ok, f"unexpected violations: {violations}")

    def test_mixed_dirty_state_lists_only_violations(self) -> None:
        """Quality changes + source changes: only the source paths get
        flagged, with quality changes silently allowed."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_repo(root)
            (root / "quality" / "BUGS.md").write_text(
                "# Bugs\n## BUG-001\n", encoding="utf-8"
            )
            (root / "src" / "code.py").write_text(
                "edited\n", encoding="utf-8"
            )
            (root / "README.md").write_text(
                "# Edited\n", encoding="utf-8"
            )
            ok, violations = lib.validate_no_source_edits(root)
            self.assertFalse(ok)
            self.assertEqual(sorted(violations), ["README.md", "src/code.py"])

    def test_rename_into_quality_is_allowed(self) -> None:
        """A rename whose destination is in quality/ should be allowed
        even though the source path is outside quality/. Tests the
        ``-z`` rename-pair handling."""
        import subprocess

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_repo(root)
            # Stage a rename that takes a file FROM the source tree
            # INTO quality/. Use git mv so the rename is actually
            # detected (git status -z reports rename pairs only when
            # the operation is structurally a rename).
            subprocess.run(
                ["git", "mv", "README.md", "quality/README.md"],
                cwd=str(root),
                check=True,
                capture_output=True,
                text=True,
            )
            ok, violations = lib.validate_no_source_edits(root)
            self.assertTrue(
                ok,
                f"rename into quality/ should be allowed; got {violations}",
            )

    def test_rename_out_of_quality_is_a_violation(self) -> None:
        """Conversely, a rename whose destination is OUTSIDE quality/
        is a violation — the destination is what matters."""
        import subprocess

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_repo(root)
            subprocess.run(
                ["git", "mv", "quality/BUGS.md", "BUGS_at_root.md"],
                cwd=str(root),
                check=True,
                capture_output=True,
                text=True,
            )
            ok, violations = lib.validate_no_source_edits(root)
            self.assertFalse(ok)
            self.assertIn("BUGS_at_root.md", violations)

    def test_non_git_directory_returns_clean(self) -> None:
        """If target_dir isn't a git repo, there's no source tree to
        protect — return clean rather than crashing the run."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "anything.py").write_text("ok\n", encoding="utf-8")
            ok, violations = lib.validate_no_source_edits(root)
            self.assertTrue(ok)
            self.assertEqual(violations, [])

    def test_missing_target_dir_raises(self) -> None:
        """A non-existent target_dir is a programming error, not a
        runtime condition — surface it loudly."""
        with self.assertRaises(FileNotFoundError):
            lib.validate_no_source_edits(Path("/no/such/dir/qpb-test"))

    def test_custom_allowed_prefix_extends_allowlist(self) -> None:
        """Operators can pass extra allowed prefixes (e.g. a scratch
        dir). Files under those prefixes are not violations.

        Note: ``git status --porcelain`` reports an untracked directory
        as ``scratch/`` (not the individual files), so the violation
        path matches the directory entry git emits."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_repo(root)
            (root / "scratch").mkdir()
            (root / "scratch" / "experiment.txt").write_text(
                "ok\n", encoding="utf-8"
            )
            # Default allowlist flags it.
            ok, violations = lib.validate_no_source_edits(root)
            self.assertFalse(ok)
            self.assertIn("scratch/", violations)
            # Extended allowlist allows it.
            ok, violations = lib.validate_no_source_edits(
                root, allowed_prefixes=("quality/", "scratch/")
            )
            self.assertTrue(ok, f"unexpected violations: {violations}")

    def test_prefix_without_trailing_slash_is_normalized(self) -> None:
        """Convenience — a prefix passed without a trailing slash is
        treated as if it had one. ``quality`` matches ``quality/foo``
        but not ``quality_other/foo``."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_repo(root)
            (root / "quality_other").mkdir()
            (root / "quality_other" / "f.txt").write_text("x\n", encoding="utf-8")
            ok, violations = lib.validate_no_source_edits(
                root, allowed_prefixes=("quality",)
            )
            self.assertFalse(ok)
            # Untracked directory is emitted as 'quality_other/' by git.
            self.assertIn("quality_other/", violations)


if __name__ == "__main__":
    unittest.main()
