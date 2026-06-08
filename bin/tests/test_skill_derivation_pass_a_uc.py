"""Tests for Phase 3b A.1 — Pass A UC derivation.

Covers section_kind classification (sections.py), execution-mode
keyword matching, the dual-stream record routing in run_pass_a, and
the UC prompt template's correct selection.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, List

from bin.skill_derivation import pass_a, protocol, sections
from bin.skill_derivation.runners import RunnerResult


# ---------------------------------------------------------------------------
# section_kind classification
# ---------------------------------------------------------------------------


class SectionKindClassificationTests(unittest.TestCase):
    def test_meta_section_classified_meta(self) -> None:
        kind = sections.classify_section_kind("Why This Exists", "meta-allowlist")
        self.assertEqual(kind, "meta")

    def test_meta_wins_over_execution_mode_keyword(self) -> None:
        # If a heading both is in META_SECTION_ALLOWLIST AND contains
        # an execution-mode keyword, meta wins (skip_reason set).
        kind = sections.classify_section_kind(
            "Phase 1 Overview", "meta-allowlist"  # contrived; meta-allowlist beats kw
        )
        self.assertEqual(kind, "meta")

    def test_phase_section_classified_execution_mode(self) -> None:
        kind = sections.classify_section_kind("Phase 1: Explore the Codebase", None)
        self.assertEqual(kind, "execution-mode")

    def test_recheck_section_classified_execution_mode(self) -> None:
        kind = sections.classify_section_kind("Recheck Mode — Verify Bug Fixes", None)
        self.assertEqual(kind, "execution-mode")

    def test_how_to_use_classified_execution_mode(self) -> None:
        kind = sections.classify_section_kind("How to Use", None)
        self.assertEqual(kind, "execution-mode")

    def test_case_insensitive_keyword_match(self) -> None:
        # The brief A.1 matching rule: case-insensitive substring.
        # The canonical keyword is "how to use"; heading "HOW TO USE"
        # should still match.
        self.assertTrue(sections.is_execution_mode_heading("HOW TO USE"))
        self.assertTrue(sections.is_execution_mode_heading("How to Use"))
        self.assertTrue(sections.is_execution_mode_heading("hOw tO uSe"))

    def test_operational_section_default(self) -> None:
        kind = sections.classify_section_kind("Cross-Record Invariants", None)
        self.assertEqual(kind, "operational")

    def test_body_text_does_not_trigger(self) -> None:
        # is_execution_mode_heading is heading-only by contract; body
        # mentions of "iteration" should NOT trigger when the caller
        # passes only the heading.
        self.assertFalse(
            sections.is_execution_mode_heading("Cross-Record Invariants")
        )

    def test_qpb_skill_md_execution_mode_count_in_target_range(self) -> None:
        """Brief A.1 pre-flight verification: 8-12 sections fire UC
        derivation under the chosen keyword list (Haiku target = 10 ± 20%).
        """
        # v1.5.8 instruction 208: SKILL.md moved into the plugin skill folder.
        skill_path = (
            Path(__file__).resolve().parents[2]
            / "skills" / "quality-playbook" / "SKILL.md"
        )
        if not skill_path.is_file():
            self.skipTest("QPB SKILL.md not at expected location")
        secs = sections.enumerate_sections(
            skill_path, repo_root=skill_path.parent
        )
        em_sections = [
            s for s in secs
            if s.section_kind == "execution-mode"
        ]
        self.assertGreaterEqual(
            len(em_sections),
            8,
            f"Expected 8-12 execution-mode sections; got {len(em_sections)}: "
            + ", ".join(s.heading for s in em_sections),
        )
        # Upper bound check is informational; phase numbering ranges
        # may legitimately produce slightly more matches than 12.
        self.assertLessEqual(
            len(em_sections),
            18,
            f"Execution-mode count significantly exceeds Haiku target: "
            f"{len(em_sections)} sections — tune EXECUTION_MODE_KEYWORDS "
            "before the live run.",
        )


# ---------------------------------------------------------------------------
# enumerate_sections sets section_kind in the JSON output
# ---------------------------------------------------------------------------


SKILL_FIXTURE_WITH_PHASES = """\
# Doc

## Why This Exists

Meta. No REQs.

## Phase 1: Explore

Operational + execution mode. Phase 1 produces EXPLORATION.md with
at least 8 findings.

## Cross-Cutting Invariants

Pure operational. Every record MUST have a `tier` field.

## Recheck Mode — Verify Bug Fixes

Re-runs the gate against fixes. The recheck mode is operational.
"""


class EnumerationSectionKindTests(unittest.TestCase):
    def test_section_kind_populated_in_enumerate_sections(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "SKILL.md").write_text(
                SKILL_FIXTURE_WITH_PHASES, encoding="utf-8"
            )
            secs = sections.enumerate_sections(
                tmp / "SKILL.md", repo_root=tmp
            )
            kinds = {s.heading: s.section_kind for s in secs}
            self.assertEqual(kinds["Why This Exists"], "meta")
            self.assertEqual(kinds["Phase 1: Explore"], "execution-mode")
            self.assertEqual(kinds["Cross-Cutting Invariants"], "operational")
            self.assertEqual(
                kinds["Recheck Mode — Verify Bug Fixes"], "execution-mode"
            )

    def test_sections_json_emits_section_kind(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "SKILL.md").write_text(
                SKILL_FIXTURE_WITH_PHASES, encoding="utf-8"
            )
            secs = sections.enumerate_sections(
                tmp / "SKILL.md", repo_root=tmp
            )
            out = tmp / "pass_a_sections.json"
            sections.write_sections_json(secs, out)
            payload = json.loads(out.read_text())
            self.assertEqual(payload["schema_version"], "1.1")
            for s in payload["sections"]:
                self.assertIn("section_kind", s)
                self.assertIn(
                    s["section_kind"],
                    ("operational", "execution-mode", "meta"),
                )


# ---------------------------------------------------------------------------
# Pass A driver dual-stream routing
# ---------------------------------------------------------------------------


@dataclass
class MockRunner:
    response_for: Callable[[str], str]
    elapsed_ms: int = 30_000
    call_log: List[str] = field(default_factory=list)

    def run(self, prompt: str) -> RunnerResult:
        self.call_log.append(prompt)
        return RunnerResult(
            stdout=self.response_for(prompt),
            stderr="",
            elapsed_ms=self.elapsed_ms,
            returncode=0,
        )


def _setup_dual_stream_fixture(tmp: Path) -> dict:
    skill_text = """\
# Doc

## Cross-Cutting Invariants

Operational only. No execution mode.

## Phase 1: Explore

Execution mode + operational claims. Phase 1 produces
EXPLORATION.md with at least 8 findings.
"""
    skill_path = tmp / "SKILL.md"
    skill_path.write_text(skill_text, encoding="utf-8")
    enumerated = sections.enumerate_sections(skill_path, repo_root=tmp)
    sections_path = tmp / "phase3" / "pass_a_sections.json"
    sections.write_sections_json(enumerated, sections_path)
    return {
        "skill_path": skill_path,
        "sections_path": sections_path,
        "drafts_path": tmp / "phase3" / "pass_a_drafts.jsonl",
        "uc_drafts_path": tmp / "phase3" / "pass_a_use_case_drafts.jsonl",
        "progress_path": tmp / "phase3" / "pass_a_progress.json",
        "pass_spec_path": tmp / "PHASE3B_BRIEF.md",
        "document_root": tmp,
    }


class DualStreamRoutingTests(unittest.TestCase):
    def _operational_response(self, prompt: str) -> str:
        # Cross-Cutting Invariants section -> REQ-only response.
        import re
        m = re.search(r"Section index in this run: `(\d+)`", prompt)
        section_idx = int(m.group(1))
        return json.dumps({
            "draft_idx": 0,
            "section_idx": section_idx,
            "title": "Every record has tier",
            "description": "x",
            "acceptance_criteria": "y",
            "proposed_source_ref": "Cross-Cutting Invariants section",
        })

    def _execution_mode_response(self, prompt: str) -> str:
        # Phase 1 section -> mixed REQ + UC response.
        import re
        m = re.search(r"Section index in this run: `(\d+)`", prompt)
        section_idx = int(m.group(1))
        return (
            json.dumps({
                "draft_idx": 1,
                "section_idx": section_idx,
                "title": "Phase 1 produces 8 findings",
                "description": "x",
                "acceptance_criteria": "y",
                "proposed_source_ref": "Phase 1 section",
            })
            + "\n"
            + json.dumps({
                "uc_draft_idx": 0,
                "section_idx": section_idx,
                "title": "Operator runs Phase 1",
                "actors": ["operator"],
                "steps": ["invoke phase 1", "review EXPLORATION.md"],
                "trigger": "operator chooses to begin a new run",
                "acceptance": "EXPLORATION.md exists with >=8 findings",
                "proposed_source_ref": "Phase 1 section",
            })
        )

    def test_uc_records_route_to_uc_drafts_jsonl(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            paths = _setup_dual_stream_fixture(tmp)
            paths["pass_spec_path"].write_text("stub spec", encoding="utf-8")

            req_template = (
                Path(__file__).resolve().parents[1]
                / "skill_derivation"
                / "prompts"
                / "pass_a_section.md"
            )
            uc_template = (
                Path(__file__).resolve().parents[1]
                / "skill_derivation"
                / "prompts"
                / "pass_a_uc_section.md"
            )

            config = pass_a.PassAConfig(
                drafts_path=paths["drafts_path"],
                progress_path=paths["progress_path"],
                sections_path=paths["sections_path"],
                pass_spec_path=paths["pass_spec_path"],
                document_root=paths["document_root"],
                uc_drafts_path=paths["uc_drafts_path"],
                req_template_path=req_template,
                uc_template_path=uc_template,
            )

            def dispatch(prompt: str) -> str:
                # Pick the response based on which template was rendered.
                if "execution-mode" in prompt or "TWO record kinds" in prompt:
                    return self._execution_mode_response(prompt)
                return self._operational_response(prompt)

            runner = MockRunner(response_for=dispatch)
            pass_a.run_pass_a(config, runner, req_template)

            req_recs = [
                json.loads(line)
                for line in paths["drafts_path"].read_text().splitlines()
                if line.strip()
            ]
            uc_recs = [
                json.loads(line)
                for line in paths["uc_drafts_path"].read_text().splitlines()
                if line.strip()
            ]
            # REQ stream has both REQ records + the operational and
            # execution-mode REQs (2 total).
            req_only = [r for r in req_recs if "draft_idx" in r]
            self.assertEqual(len(req_only), 2)
            # UC stream has 1 UC record.
            self.assertEqual(len(uc_recs), 1)
            self.assertIn("uc_draft_idx", uc_recs[0])
            self.assertEqual(uc_recs[0]["title"], "Operator runs Phase 1")

    def test_operational_only_section_emits_no_uc_records(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            paths = _setup_dual_stream_fixture(tmp)
            paths["pass_spec_path"].write_text("stub spec", encoding="utf-8")

            req_template = (
                Path(__file__).resolve().parents[1]
                / "skill_derivation"
                / "prompts"
                / "pass_a_section.md"
            )
            uc_template = (
                Path(__file__).resolve().parents[1]
                / "skill_derivation"
                / "prompts"
                / "pass_a_uc_section.md"
            )

            config = pass_a.PassAConfig(
                drafts_path=paths["drafts_path"],
                progress_path=paths["progress_path"],
                sections_path=paths["sections_path"],
                pass_spec_path=paths["pass_spec_path"],
                document_root=paths["document_root"],
                uc_drafts_path=paths["uc_drafts_path"],
                req_template_path=req_template,
                uc_template_path=uc_template,
            )

            # Override: even on Phase 1 section, return REQ-only.
            def operational_only(prompt: str) -> str:
                return self._operational_response(prompt)

            runner = MockRunner(response_for=operational_only)
            pass_a.run_pass_a(config, runner, req_template)

            uc_recs = (
                paths["uc_drafts_path"].read_text().splitlines()
                if paths["uc_drafts_path"].is_file()
                else []
            )
            uc_with_idx = [
                json.loads(line) for line in uc_recs if line.strip()
            ]
            self.assertEqual(len(uc_with_idx), 0)


if __name__ == "__main__":
    unittest.main()
