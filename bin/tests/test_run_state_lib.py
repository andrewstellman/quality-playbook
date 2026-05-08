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


def _canonical_phase1_exploration_md() -> str:
    """Return a minimal EXPLORATION.md that satisfies all 13 SKILL.md
    Phase 2 entry-gate checks (used by tests below to construct
    fixtures and to mutate single sections for per-check rejection
    tests)."""
    findings: list[str] = []
    # 8 numbered findings, each with 2+ file:line citations
    # (satisfies checks 9 + 10).
    for i in range(1, 9):
        findings.append(
            f"{i}. `bin/run_playbook.py:{1500 + i * 10}-{1500 + i * 10 + 5}` "
            f"diverges from `bin/run_state_lib.py:{1660 + i}-{1670 + i}` on "
            f"behavior X. Multi-location trace across both modules.\n"
        )
    findings_section = "## Open Exploration Findings\n\n" + "\n".join(findings)

    risks_section = (
        "## Quality Risks\n\n"
        "1. **Highest risk** — risk one. `bin/run_playbook.py:100`.\n\n"
        "2. **Second risk** — risk two. `bin/run_playbook.py:200`.\n"
    )

    # Pattern Applicability Matrix: 3 FULL rows (lower bound of 3-4
    # inclusive), 2 SKIP rows.
    matrix_section = (
        "## Pattern Applicability Matrix\n\n"
        "| Pattern | Decision (`FULL` / `SKIP`) | Target | Why |\n"
        "|---|---|---|---|\n"
        "| Fallback Parity | `FULL` | bin/ | Reason |\n"
        "| Cross-Implementation | `FULL` | bin/ | Reason |\n"
        "| API Surface | `FULL` | bin/ | Reason |\n"
        "| Dispatch Returns | `SKIP` | CLI | Reason |\n"
        "| Spec Parsing | `SKIP` | parsers | Reason |\n"
    )

    # 3 Pattern Deep Dive sections; 2 of them cite ≥2 distinct
    # identifiers OR ≥2 distinct file:line refs (multi-function).
    deep_dives = (
        "## Pattern Deep Dive — Fallback Parity\n\n"
        "- Cites `docs_present` and `_evaluate_documentation_state` "
        "across `bin/run_playbook.py:1560-1575` and "
        "`bin/run_playbook.py:1661-1669`.\n"
        "\n"
        "## Pattern Deep Dive — Cross-Implementation\n\n"
        "- Cites `validate_phase_artifacts` and `check_phase_gate` "
        "across `bin/run_state_lib.py:158-200` and "
        "`bin/run_playbook.py:830-840`.\n"
        "\n"
        "## Pattern Deep Dive — API Surface\n\n"
        "- Cites `_reference_docs_plaintext` and `formal_docs_guard_banner` "
        "across `bin/run_playbook.py:1583-1595` and "
        "`bin/run_playbook.py:1598-1621`.\n"
    )

    candidate_section = (
        "## Candidate Bugs for Phase 2\n\n"
        "1. **HIGH — first bug**\n"
        "   - Stage: open exploration\n"
        "   - Evidence: `bin/run_playbook.py:1560-1575`.\n"
        "\n"
        "2. **HIGH — second bug**\n"
        "   - Stage: open exploration + Fallback Parity\n"
        "   - Evidence: `bin/reference_docs_ingest.py:90-94`.\n"
        "\n"
        "3. **MEDIUM — third bug**\n"
        "   - Stage: quality risks\n"
        "   - Evidence: `bin/run_state_lib.py:171-198`.\n"
    )

    gate_section = (
        "## Gate Self-Check\n\n"
        "All 13 SKILL.md:1257-1273 checks satisfied.\n"
    )

    # Filler to clear 120 lines.
    filler = "\n".join(f"<!-- filler {i} -->" for i in range(60)) + "\n"

    return (
        "# Exploration\n\n"
        + findings_section + "\n"
        + risks_section + "\n"
        + matrix_section + "\n"
        + deep_dives + "\n"
        + candidate_section + "\n"
        + gate_section + "\n"
        + filler
    )


def _write_canonical_phase1_fixture(quality: Path, *,
                                    skip_progress: bool = False) -> None:
    """Write the minimal-canonical EXPLORATION.md + PROGRESS.md to
    ``quality`` so all 13 phase-1 checks pass."""
    quality.mkdir(parents=True, exist_ok=True)
    (quality / "EXPLORATION.md").write_text(
        _canonical_phase1_exploration_md(), encoding="utf-8",
    )
    if not skip_progress:
        (quality / "PROGRESS.md").write_text(
            "# Quality Playbook Progress\n\n"
            "## Phase tracker\n\n"
            "- [x] Phase 1 - Explore\n"
            "- [ ] Phase 2 - Generate\n",
            encoding="utf-8",
        )


class ValidatePhaseArtifactsTests(unittest.TestCase):
    def test_validate_phase_artifacts_phase1_missing_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("EXPLORATION.md", reason)

    def test_validate_phase_artifacts_phase1_canonical_passes(self) -> None:
        """v1.5.6 BUG-005 (codex bootstrap): the canonical-minimal
        EXPLORATION.md + PROGRESS.md fixture (built to satisfy all 13
        SKILL.md:1257-1273 checks) must pass."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertTrue(ok, msg=reason)
            self.assertEqual(reason, "")

    def test_validate_phase_artifacts_phase1_actual_qpb_exploration_passes(self) -> None:
        """Calibration sanity: the actual QPB-self-bootstrap
        EXPLORATION.md from the 2026-05-08 codex run must pass.
        If this fails, the validator is too strict OR the canonical
        artifact has drifted (which would itself be a finding)."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        canonical_quality = repo_root / "quality"
        if not (canonical_quality / "EXPLORATION.md").is_file():
            self.skipTest(
                f"canonical {canonical_quality}/EXPLORATION.md not present "
                "in this checkout — skipping calibration test"
            )
        ok, reason = lib.validate_phase_artifacts(canonical_quality, 1)
        self.assertTrue(
            ok,
            f"Validator rejected the canonical EXPLORATION.md from the "
            f"codex bootstrap run: {reason!r}",
        )

    def test_phase1_validator_rejects_too_short(self) -> None:
        """Check 1: <120 lines fails."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "EXPLORATION.md").write_text(
                "## Finding 1\nshort\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("≥120", reason)

    def test_phase1_validator_rejects_missing_open_exploration_findings(self) -> None:
        """Check 2: missing ## Open Exploration Findings."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            text = text.replace("## Open Exploration Findings", "## Random Other")
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("Open Exploration Findings", reason)

    def test_phase1_validator_rejects_missing_quality_risks(self) -> None:
        """Check 3: missing ## Quality Risks."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            text = text.replace("## Quality Risks", "## Risks Renamed")
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("Quality Risks", reason)

    def test_phase1_validator_rejects_missing_pattern_applicability_matrix(self) -> None:
        """Check 4: missing ## Pattern Applicability Matrix."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            text = text.replace(
                "## Pattern Applicability Matrix", "## Patterns Considered"
            )
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("Pattern Applicability Matrix", reason)

    def test_phase1_validator_rejects_under_3_pattern_deep_dives(self) -> None:
        """Check 5: <3 ## Pattern Deep Dive — sections fails."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            # Drop two of the three deep dives.
            text = text.replace("## Pattern Deep Dive — Cross-Implementation", "## Removed-A")
            text = text.replace("## Pattern Deep Dive — API Surface", "## Removed-B")
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("pattern deep dives", reason)

    def test_phase1_validator_rejects_missing_candidate_bugs(self) -> None:
        """Check 6: missing ## Candidate Bugs for Phase 2."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            text = text.replace(
                "## Candidate Bugs for Phase 2", "## Bugs Renamed"
            )
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("Candidate Bugs for Phase 2", reason)

    def test_phase1_validator_rejects_missing_gate_self_check(self) -> None:
        """Check 7: missing ## Gate Self-Check."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            text = text.replace("## Gate Self-Check", "## Gate Renamed")
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("Gate Self-Check", reason)

    def test_phase1_validator_rejects_progress_md_unmarked(self) -> None:
        """Check 8: PROGRESS.md missing the [x] Phase 1 mark."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            (quality / "PROGRESS.md").write_text(
                "# Quality Playbook Progress\n\n"
                "## Phase tracker\n\n"
                "- [ ] Phase 1 - Explore\n",
                encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("PROGRESS.md", reason)
            self.assertIn("Phase 1", reason)

    def test_phase1_validator_rejects_under_8_findings(self) -> None:
        """Check 9: <8 numbered findings with file:line citations."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            # Strip the numbered findings block; replace with 4 entries.
            findings = "\n".join(
                f"{i}. `bin/run_playbook.py:{100 + i}-{105 + i}` and "
                f"`bin/run_state_lib.py:{200 + i}-{205 + i}` finding {i}.\n"
                for i in range(1, 5)
            )
            new_block = "## Open Exploration Findings\n\n" + findings + "\n"
            old_block_start = text.index("## Open Exploration Findings")
            old_block_end = text.index("## Quality Risks")
            text = text[:old_block_start] + new_block + text[old_block_end:]
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("≥8", reason)

    def test_phase1_validator_rejects_under_3_multilocation_findings(self) -> None:
        """Check 10: <3 findings citing ≥2 distinct file:line locations."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            # 8 findings but only 1 cites multiple locations.
            findings_lines = [
                "1. `bin/run_playbook.py:100-105` and `bin/run_state_lib.py:200-205` "
                "multi-location finding 1.\n"
            ]
            for i in range(2, 9):
                findings_lines.append(
                    f"{i}. `bin/run_playbook.py:{200 + i}-{205 + i}` "
                    f"single-location finding {i}.\n"
                )
            new_block = (
                "## Open Exploration Findings\n\n" + "\n".join(findings_lines) + "\n"
            )
            old_block_start = text.index("## Open Exploration Findings")
            old_block_end = text.index("## Quality Risks")
            text = text[:old_block_start] + new_block + text[old_block_end:]
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("multi-location", reason)

    def test_phase1_validator_rejects_full_count_below_3(self) -> None:
        """Check 11 lower bound: <3 FULL rows in matrix."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            # Replace 2 FULL rows with SKIP, leaving only 1 FULL.
            text = text.replace(
                "| Cross-Implementation | `FULL` | bin/ | Reason |",
                "| Cross-Implementation | `SKIP` | bin/ | Reason |", 1,
            )
            text = text.replace(
                "| API Surface | `FULL` | bin/ | Reason |",
                "| API Surface | `SKIP` | bin/ | Reason |", 1,
            )
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("FULL count", reason)
            self.assertIn("too low", reason)

    def test_phase1_validator_rejects_full_count_above_4(self) -> None:
        """Check 11 upper bound: >4 FULL rows in matrix."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            # Convert both SKIP rows to FULL → 5 FULL total.
            text = text.replace(
                "| Dispatch Returns | `SKIP` | CLI | Reason |",
                "| Dispatch Returns | `FULL` | CLI | Reason |", 1,
            )
            text = text.replace(
                "| Spec Parsing | `SKIP` | parsers | Reason |",
                "| Spec Parsing | `FULL` | parsers | Reason |", 1,
            )
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("FULL count", reason)
            self.assertIn("too high", reason)

    def test_phase1_validator_rejects_under_2_multifunction_deep_dives(self) -> None:
        """Check 12: <2 multi-function pattern deep dives."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            # Replace the deep-dive block with 3 single-function sections.
            old_dives_start = text.index("## Pattern Deep Dive — Fallback Parity")
            old_dives_end = text.index("## Candidate Bugs for Phase 2")
            new_dives = (
                "## Pattern Deep Dive — Fallback Parity\n\n"
                "- Single function `docs_present` only.\n\n"
                "## Pattern Deep Dive — Cross-Implementation\n\n"
                "- Single function `check_phase_gate` only.\n\n"
                "## Pattern Deep Dive — API Surface\n\n"
                "- Single function `_reference_docs_plaintext` only.\n\n"
            )
            text = text[:old_dives_start] + new_dives + text[old_dives_end:]
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("multi-function pattern deep dives", reason)

    def test_phase1_validator_rejects_candidate_bugs_missing_deep_dive_source(self) -> None:
        """Check 13b: Candidate Bugs all from exploration/risks, none from
        pattern deep dive."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            old_block_start = text.index("## Candidate Bugs for Phase 2")
            old_block_end = text.index("## Gate Self-Check")
            new_block = (
                "## Candidate Bugs for Phase 2\n\n"
                "1. **HIGH — first**\n"
                "   - Stage: open exploration\n\n"
                "2. **HIGH — second**\n"
                "   - Stage: open exploration\n\n"
                "3. **MEDIUM — third**\n"
                "   - Stage: quality risks\n\n"
            )
            text = text[:old_block_start] + new_block + text[old_block_end:]
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("candidate bugs source mix", reason)

    def test_phase1_validator_rejects_candidate_bugs_missing_exploration_source(self) -> None:
        """Check 13a: Candidate Bugs all from pattern deep dive, none from
        exploration/risks."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            _write_canonical_phase1_fixture(quality)
            text = (quality / "EXPLORATION.md").read_text(encoding="utf-8")
            old_block_start = text.index("## Candidate Bugs for Phase 2")
            old_block_end = text.index("## Gate Self-Check")
            new_block = (
                "## Candidate Bugs for Phase 2\n\n"
                "1. **HIGH — first**\n"
                "   - Stage: API Surface Consistency\n\n"
                "2. **HIGH — second**\n"
                "   - Stage: Fallback Parity\n\n"
                "3. **MEDIUM — third**\n"
                "   - Stage: Cross-Implementation\n\n"
            )
            text = text[:old_block_start] + new_block + text[old_block_end:]
            (quality / "EXPLORATION.md").write_text(text, encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("candidate bugs source mix", reason)

    def test_phase1_validator_aggregates_multiple_failures(self) -> None:
        """Multiple failures must aggregate into a multi-line message
        rather than short-circuiting on the first."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "EXPLORATION.md").write_text(
                "# Exploration\n\n"
                "## Unrelated heading\n"
                + "\n".join(f"line {i}" for i in range(150)),
                encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            # At least 3 distinct failure messages should be present
            # (missing headings, no findings, no matrix, etc.).
            self.assertGreaterEqual(
                len([line for line in reason.splitlines() if line.startswith("Phase 1 gate:")]),
                3,
                f"expected ≥3 aggregated 'Phase 1 gate:' failure lines, "
                f"got: {reason!r}",
            )

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

            # Stage all nine fixed-name Generate-contract artifacts +
            # the two JSON manifests (071 BUG-003 expansion) as
            # non-empty files.
            for name in (
                "REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md",
                "COVERAGE_MATRIX.md", "COMPLETENESS_REPORT.md",
                "RUN_CODE_REVIEW.md", "RUN_INTEGRATION_TESTS.md",
                "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
            ):
                (quality / name).write_text("body\n", encoding="utf-8")
            (quality / "requirements_manifest.json").write_text(
                "[]\n", encoding="utf-8",
            )
            (quality / "use_cases_manifest.json").write_text(
                "[]\n", encoding="utf-8",
            )

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
            (quality / "requirements_manifest.json").write_text("[]\n", encoding="utf-8")
            (quality / "use_cases_manifest.json").write_text("[]\n", encoding="utf-8")
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
            # Both file types but no triage_probes.sh → fails (071 BUG-005).
            (quality / "spec_audits" / "2026-05-06-triage.md").write_text(
                "# triage\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertFalse(ok)
            self.assertIn("triage_probes.sh", reason)
            # Add the probes file → fails on missing semantic-check (071 BUG-005).
            (quality / "spec_audits" / "triage_probes.sh").write_text(
                "#!/bin/sh\nexit 0\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertFalse(ok)
            self.assertIn("citation_semantic_check.json", reason)
            # Add the semantic-check artifact → passes.
            (quality / "citation_semantic_check.json").write_text(
                "{}\n", encoding="utf-8",
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
            # Two arbitrarily-named files + 071 BUG-005 artifacts (probes
            # + semantic-check) → passes (fallback path preserved).
            (quality / "spec_audits" / "report-b.md").write_text(
                "# b\n", encoding="utf-8",
            )
            (quality / "spec_audits" / "triage_probes.sh").write_text(
                "#!/bin/sh\nexit 0\n", encoding="utf-8",
            )
            (quality / "citation_semantic_check.json").write_text(
                "{}\n", encoding="utf-8",
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


class Phase2_5ValidatorExpansionTests(unittest.TestCase):
    """v1.5.6 fix-up 071 BUG-003/004/005/006: phase 2-5 validators
    expanded to enforce SKILL.md's full artifact contract at the
    phase boundary, extending instruction 066's pattern from Phase 1.
    Pre-fix the validators tolerated incomplete artifact sets and
    deferred the failure to the Phase 6 final gate — recreating the
    v1.5.4 'phase reported complete with shallow output' UX failure
    mode the validator system was added to close.
    """

    def _stage_phase2_artifacts(self, quality: Path, *, include_manifests: bool = True) -> None:
        for name in (
            "REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md",
            "COVERAGE_MATRIX.md", "COMPLETENESS_REPORT.md",
            "RUN_CODE_REVIEW.md", "RUN_INTEGRATION_TESTS.md",
            "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
        ):
            (quality / name).write_text("body\n", encoding="utf-8")
        (quality / "test_functional.py").write_text("def t(): pass\n", encoding="utf-8")
        if include_manifests:
            (quality / "requirements_manifest.json").write_text("[]\n", encoding="utf-8")
            (quality / "use_cases_manifest.json").write_text("[]\n", encoding="utf-8")

    # --- BUG-003: Phase 2 manifest enforcement ----------------------

    def test_phase2_validator_rejects_missing_requirements_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            self._stage_phase2_artifacts(quality, include_manifests=False)
            (quality / "use_cases_manifest.json").write_text("[]\n", encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 2)
            self.assertFalse(ok)
            self.assertIn("requirements_manifest.json", reason)

    def test_phase2_validator_rejects_missing_use_cases_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            self._stage_phase2_artifacts(quality, include_manifests=False)
            (quality / "requirements_manifest.json").write_text("[]\n", encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 2)
            self.assertFalse(ok)
            self.assertIn("use_cases_manifest.json", reason)

    def test_phase2_validator_rejects_empty_requirements_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            self._stage_phase2_artifacts(quality, include_manifests=False)
            (quality / "requirements_manifest.json").write_text("", encoding="utf-8")
            (quality / "use_cases_manifest.json").write_text("[]\n", encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 2)
            self.assertFalse(ok)
            self.assertIn("requirements_manifest.json", reason)
            self.assertIn("empty", reason)

    # --- BUG-004: Phase 3 per-bug regression-test patches -----------

    def _stage_phase3_artifacts(self, quality: Path, *, bug_ids: list[str], patches_for: list[str]) -> None:
        (quality / "code_reviews").mkdir(parents=True)
        (quality / "code_reviews" / "review.md").write_text("# review\n", encoding="utf-8")
        bugs_md = "# Bugs\n\n" + "\n".join(
            f"### BUG-{bid}: Sample\n**Severity**: HIGH\n" for bid in bug_ids
        ) + "\n"
        (quality / "BUGS.md").write_text(bugs_md, encoding="utf-8")
        patches = quality / "patches"
        patches.mkdir(parents=True)
        for bid in patches_for:
            (patches / f"BUG-{bid}-regression-test.patch").write_text(
                "diff --git a/x b/x\n--- a/x\n+++ b/x\n", encoding="utf-8",
            )

    def test_phase3_validator_requires_one_patch_per_bug(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            # 3 BUG entries, only 2 patches (BUG-002 missing).
            self._stage_phase3_artifacts(
                quality, bug_ids=["001", "002", "003"], patches_for=["001", "003"]
            )
            ok, reason = lib.validate_phase_artifacts(quality, 3)
            self.assertFalse(ok)
            self.assertIn("BUG-002", reason)
            self.assertIn("regression-test", reason)

    def test_phase3_validator_passes_with_full_patch_coverage(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            self._stage_phase3_artifacts(
                quality, bug_ids=["001", "002", "003"],
                patches_for=["001", "002", "003"],
            )
            ok, reason = lib.validate_phase_artifacts(quality, 3)
            self.assertTrue(ok, msg=reason)

    def test_phase3_validator_handles_titled_and_bare_bug_headings(self) -> None:
        """Regex matches archive_lib._BUG_HEADING_PATTERN — titled
        AND bare forms recognized."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "code_reviews").mkdir(parents=True)
            (quality / "code_reviews" / "r.md").write_text("# r\n", encoding="utf-8")
            (quality / "BUGS.md").write_text(
                "### BUG-001\n### BUG-002: Titled\n### BUG-001-fix-2: Suffix\n",
                encoding="utf-8",
            )
            (quality / "patches").mkdir()
            for bid in ("001", "002", "001-fix-2"):
                (quality / "patches" / f"BUG-{bid}-regression-test.patch").write_text(
                    "diff\n", encoding="utf-8",
                )
            ok, reason = lib.validate_phase_artifacts(quality, 3)
            self.assertTrue(ok, msg=reason)

    # --- BUG-005: Phase 4 triage probes + semantic check ------------

    def _stage_phase4_artifacts(
        self, quality: Path, *,
        include_probes: bool = True,
        include_semantic: bool = True,
    ) -> None:
        spec_audits = quality / "spec_audits"
        spec_audits.mkdir(parents=True)
        (spec_audits / "2026-05-08-triage.md").write_text("# triage\n", encoding="utf-8")
        (spec_audits / "2026-05-08-auditor-1.md").write_text("# a\n", encoding="utf-8")
        if include_probes:
            (spec_audits / "triage_probes.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        if include_semantic:
            (quality / "citation_semantic_check.json").write_text("{}\n", encoding="utf-8")

    def test_phase4_validator_rejects_missing_triage_probes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            self._stage_phase4_artifacts(quality, include_probes=False)
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertFalse(ok)
            self.assertIn("triage_probes.sh", reason)

    def test_phase4_validator_rejects_missing_citation_semantic_check(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            self._stage_phase4_artifacts(quality, include_semantic=False)
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertFalse(ok)
            self.assertIn("citation_semantic_check.json", reason)

    def test_phase4_validator_accepts_empty_citation_semantic_check(self) -> None:
        """An empty {} JSON should pass the presence check —
        Tier-3-only runs produce empty-but-valid semantic-check
        artifacts. Content validation belongs to the final gate."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            self._stage_phase4_artifacts(quality, include_semantic=False)
            (quality / "citation_semantic_check.json").write_text(
                "{}\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertTrue(ok, msg=reason)

    def test_phase4_validator_preserves_naming_convention_flexibility(self) -> None:
        """Backward-compat — the existing triage-or-auditor-or-fallback
        pattern still works alongside the new BUG-005 requirements."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            spec_audits = quality / "spec_audits"
            spec_audits.mkdir()
            # Arbitrary names (no triage/auditor in name) — fallback pattern.
            (spec_audits / "report-a.md").write_text("# a\n", encoding="utf-8")
            (spec_audits / "report-b.md").write_text("# b\n", encoding="utf-8")
            (spec_audits / "triage_probes.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (quality / "citation_semantic_check.json").write_text("{}\n", encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertTrue(
                ok,
                msg=f"backward-compat fallback (≥2 .md files when neither "
                    f"naming convention is used) must still pass when the "
                    f"new BUG-005 artifacts are present. reason={reason!r}",
            )

    # --- BUG-006: Phase 5 green logs for fix-bearing bugs -----------

    def _stage_phase5_artifacts(
        self, quality: Path, *, bug_ids: list[str],
        with_red: list[str], with_green: list[str],
        with_fix_patch: list[str],
    ) -> None:
        (quality / "BUGS.md").write_text(
            "\n".join(f"### BUG-{bid}: Sample\n" for bid in bug_ids),
            encoding="utf-8",
        )
        (quality / "results").mkdir(parents=True)
        (quality / "results" / "tdd-results.json").write_text(
            '{"results":[]}\n', encoding="utf-8",
        )
        (quality / "writeups").mkdir(parents=True)
        (quality / "patches").mkdir(parents=True)
        for bid in bug_ids:
            (quality / "writeups" / f"BUG-{bid}.md").write_text("# w\n", encoding="utf-8")
        for bid in with_red:
            (quality / "results" / f"BUG-{bid}.red.log").write_text("RED\n", encoding="utf-8")
        for bid in with_green:
            (quality / "results" / f"BUG-{bid}.green.log").write_text("GREEN\n", encoding="utf-8")
        for bid in with_fix_patch:
            (quality / "patches" / f"BUG-{bid}-fix.patch").write_text("diff\n", encoding="utf-8")

    def test_phase5_validator_requires_green_log_for_fix_bearing_bug(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            # BUG-001: red + fix patch but no green log → fail.
            self._stage_phase5_artifacts(
                quality, bug_ids=["001"],
                with_red=["001"], with_green=[],
                with_fix_patch=["001"],
            )
            ok, reason = lib.validate_phase_artifacts(quality, 5)
            self.assertFalse(ok)
            self.assertIn("BUG-001", reason)
            self.assertIn("green", reason.lower())

    def test_phase5_validator_skips_green_check_for_red_only_bug(self) -> None:
        """Code-review-only bug (no fix patch) — red-only is acceptable."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            self._stage_phase5_artifacts(
                quality, bug_ids=["002"],
                with_red=["002"], with_green=[],
                with_fix_patch=[],  # no fix patch → no green required
            )
            ok, reason = lib.validate_phase_artifacts(quality, 5)
            self.assertTrue(ok, msg=reason)

    def test_phase5_validator_passes_with_full_red_green_coverage(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            self._stage_phase5_artifacts(
                quality, bug_ids=["001", "002"],
                with_red=["001", "002"],
                with_green=["001", "002"],
                with_fix_patch=["001", "002"],
            )
            ok, reason = lib.validate_phase_artifacts(quality, 5)
            self.assertTrue(ok, msg=reason)

    # --- Calibration sanity check (mandatory per spec) --------------

    def test_phase_2_5_validators_accept_canonical_bootstrap_evidence(self) -> None:
        """The new validators MUST accept the canonical 2026-05-08
        codex bootstrap evidence at quality/previous_runs/20260508-codex-bootstrap/.
        If any phase rejects, the validator is too strict (or the
        canonical evidence has drifted, which would itself be a
        finding). Required calibration sanity per instruction 071."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        canonical = repo_root / "quality" / "previous_runs" / "20260508-codex-bootstrap"
        if not canonical.is_dir():
            self.skipTest(
                f"canonical bootstrap evidence absent: {canonical} "
                "— skipping calibration test"
            )
        for phase in (2, 3, 4, 5):
            with self.subTest(phase=phase):
                ok, reason = lib.validate_phase_artifacts(canonical, phase)
                self.assertTrue(
                    ok,
                    f"validator rejected canonical bootstrap evidence for "
                    f"phase {phase}: {reason!r}",
                )


class EmptyEventTypesWhitelistTests(unittest.TestCase):
    """v1.5.6 fix-up 067 C-4: pre-fix the whitelist check at
    bin/run_state_lib.py:902 had ``and declared_types`` as a guard,
    silently SKIPPING the check when ``_index.event_types`` was an
    empty list. The comment said "every subsequent event will fail
    invariant 4" — the code violated that contract. Council 2026-05-08
    (gpt-5.4 panelist A) flagged. Fix dropped ``and declared_types``;
    these tests pin the new behavior."""

    def test_empty_event_types_fails_every_event(self) -> None:
        with TemporaryDirectory() as temp_dir:
            jsonl_path = Path(temp_dir) / "run_state.jsonl"
            lines = [
                # _index with empty event_types — structurally broken
                # but should not silently bless every subsequent event.
                '{"event":"_index","ts":"2026-05-08T12:00:00Z","schema_version":"1.5.6","event_types":[],"benchmark":"x","lever_state":"baseline","started_at":"2026-05-08T12:00:00Z"}',
                '{"event":"phase_start","ts":"2026-05-08T12:00:01Z","phase":1}',
                '{"event":"phase_end","ts":"2026-05-08T12:00:02Z","phase":1,"key_counts":{"findings_total":0,"patterns_walked":0},"artifacts_produced":[]}',
            ]
            jsonl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            ok, violations = lib.validate_run_state_file(jsonl_path)
            self.assertFalse(ok, msg=str(violations))
            # Both non-_index events must trip the whitelist check.
            joined = "\n".join(violations)
            self.assertIn("phase_start", joined)
            self.assertIn("phase_end", joined)
            self.assertIn("not declared in _index.event_types", joined)

    def test_populated_event_types_still_passes_listed_events(self) -> None:
        """Regression check: the fix must not break the normal case."""
        with TemporaryDirectory() as temp_dir:
            jsonl_path = Path(temp_dir) / "run_state.jsonl"
            lines = [
                '{"event":"_index","ts":"2026-05-08T12:00:00Z","schema_version":"1.5.6","event_types":["_index","phase_start","phase_end"],"benchmark":"x","lever_state":"baseline","started_at":"2026-05-08T12:00:00Z"}',
                '{"event":"phase_start","ts":"2026-05-08T12:00:01Z","phase":1}',
                '{"event":"phase_end","ts":"2026-05-08T12:00:02Z","phase":1,"key_counts":{"findings_total":0,"patterns_walked":0},"artifacts_produced":[]}',
            ]
            jsonl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            ok, violations = lib.validate_run_state_file(jsonl_path)
            # No whitelist violations (other invariants might still
            # fail — that's not what this test is pinning).
            joined = "\n".join(violations)
            self.assertNotIn("not declared in _index.event_types", joined)


if __name__ == "__main__":
    unittest.main()
