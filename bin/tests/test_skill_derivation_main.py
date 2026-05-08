"""Tests for bin/skill_derivation/__main__.py — CLI entry point.

Covers:
  - Argument parsing (the moved TestSkillDerivationMainArgs class).
  - End-to-end --pass all orchestration (Round 5 ND-1): runs A -> B
    -> C -> D in sequence with the B4 upstream-status gate enforced
    at each transition. Uses a small synthetic SKILL.md fixture and a
    deterministic MockRunner so the test does not depend on a live
    LLM. Verifies all four progress files reach status="complete"
    and the per-pass artifacts land at the expected paths.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, List
from unittest import mock

from bin.skill_derivation import __main__ as main_mod
from bin.skill_derivation import protocol
from bin.skill_derivation.runners import RunnerResult


# ---------------------------------------------------------------------------
# Argument parsing -- moved from .github/skills/quality_gate/tests/
# test_quality_gate.py:2678 per Round 5 ND-1. The bin/skill_derivation
# CLI tests structurally belong in the bin test suite; the gate suite
# tests gate behavior, not CLI plumbing.
# ---------------------------------------------------------------------------


class TestSkillDerivationMainArgs(unittest.TestCase):
    """Phase 3b commit 9: __main__.py argument parsing."""

    def test_imports_cleanly(self) -> None:
        # Smoke test: the module imports without side effects.
        from bin.skill_derivation import __main__ as main_mod_local
        self.assertTrue(callable(main_mod_local._main))

    def test_pass_choice_default_is_all(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example"])
        self.assertEqual(args.pass_choice, "all")
        self.assertTrue(args.resume)
        self.assertEqual(args.runner, "claude")
        self.assertEqual(args.pace_seconds, 0)

    def test_no_resume_flag(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example", "--no-resume"])
        self.assertFalse(args.resume)

    def test_pass_choice_individual(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        for choice in ("A", "B", "C", "D"):
            args = _parse_args(["/tmp/example", "--pass", choice])
            self.assertEqual(args.pass_choice, choice)

    def test_runner_copilot(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example", "--runner", "copilot"])
        self.assertEqual(args.runner, "copilot")

    def test_runner_codex(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example", "--runner", "codex"])
        self.assertEqual(args.runner, "codex")

    def test_runner_codex_with_model(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args([
            "/tmp/example", "--runner", "codex", "--model", "gpt-5-codex",
        ])
        self.assertEqual(args.runner, "codex")
        self.assertEqual(args.model, "gpt-5-codex")

    def test_runner_cursor(self) -> None:
        """v1.5.4 F-1: cursor is a recognized --runner choice."""
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example", "--runner", "cursor"])
        self.assertEqual(args.runner, "cursor")

    def test_runner_cursor_with_model(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args([
            "/tmp/example", "--runner", "cursor", "--model", "sonnet-4",
        ])
        self.assertEqual(args.runner, "cursor")
        self.assertEqual(args.model, "sonnet-4")

    def test_pace_seconds_int(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example", "--pace-seconds", "30"])
        self.assertEqual(args.pace_seconds, 30)

    def test_phase_default_is_3(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example"])
        self.assertEqual(args.phase, 3)

    def test_phase_4_accepted(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example", "--phase", "4"])
        self.assertEqual(args.phase, 4)

    def test_part_default_is_all(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example"])
        self.assertEqual(args.part, "all")

    def test_part_individual(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        for choice in ("a1", "a2", "a3", "b", "c", "d", "all"):
            args = _parse_args(["/tmp/example", "--part", choice])
            self.assertEqual(args.part, choice)

    def test_model_default_is_none(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example"])
        self.assertIsNone(args.model)

    def test_model_passthrough(self) -> None:
        from bin.skill_derivation.__main__ import _parse_args
        args = _parse_args(["/tmp/example", "--model", "opus"])
        self.assertEqual(args.model, "opus")


class MakeRunnerModelOverrideTests(unittest.TestCase):
    """Phase 5 Stage 0: make_runner accepts a model override that
    propagates to the constructed runner."""

    def test_make_runner_claude_default_model(self) -> None:
        from bin.skill_derivation.runners import make_runner, ClaudeRunner
        r = make_runner("claude")
        self.assertIsInstance(r, ClaudeRunner)
        self.assertEqual(r.model, "sonnet")

    def test_make_runner_claude_override_model(self) -> None:
        from bin.skill_derivation.runners import make_runner, ClaudeRunner
        r = make_runner("claude", model="opus")
        self.assertIsInstance(r, ClaudeRunner)
        self.assertEqual(r.model, "opus")

    def test_make_runner_copilot_default_model(self) -> None:
        from bin.skill_derivation.runners import make_runner, CopilotRunner
        r = make_runner("copilot")
        self.assertIsInstance(r, CopilotRunner)
        self.assertEqual(r.model, "claude-sonnet-4.6")

    def test_make_runner_copilot_override_model(self) -> None:
        from bin.skill_derivation.runners import make_runner, CopilotRunner
        r = make_runner("copilot", model="claude-opus-4.6")
        self.assertIsInstance(r, CopilotRunner)
        self.assertEqual(r.model, "claude-opus-4.6")

    def test_make_runner_codex_default_model_is_empty(self) -> None:
        """Codex's default model is empty — codex picks from
        ~/.codex/config.toml when no -m flag is passed."""
        from bin.skill_derivation.runners import make_runner, CodexRunner
        r = make_runner("codex")
        self.assertIsInstance(r, CodexRunner)
        self.assertEqual(r.model, "")

    def test_make_runner_codex_override_model(self) -> None:
        from bin.skill_derivation.runners import make_runner, CodexRunner
        r = make_runner("codex", model="gpt-5-codex")
        self.assertIsInstance(r, CodexRunner)
        self.assertEqual(r.model, "gpt-5-codex")

    def test_make_runner_cursor_default_model_is_empty(self) -> None:
        """v1.5.4 F-1: cursor's default model is empty — cursor picks
        from its account/config when no --model flag is passed (mirrors
        the codex convention)."""
        from bin.skill_derivation.runners import make_runner, CursorRunner
        r = make_runner("cursor")
        self.assertIsInstance(r, CursorRunner)
        self.assertEqual(r.model, "")

    def test_make_runner_cursor_override_model(self) -> None:
        from bin.skill_derivation.runners import make_runner, CursorRunner
        r = make_runner("cursor", model="sonnet-4")
        self.assertIsInstance(r, CursorRunner)
        self.assertEqual(r.model, "sonnet-4")

    def test_make_runner_unknown_lists_codex_in_error(self) -> None:
        from bin.skill_derivation.runners import make_runner
        with self.assertRaises(ValueError) as cm:
            make_runner("nonsense")
        self.assertIn("codex", str(cm.exception))

    def test_make_runner_unknown_lists_cursor_in_error(self) -> None:
        """v1.5.4 F-1: cursor must appear in the error message so an
        operator who typos the runner name sees all four options."""
        from bin.skill_derivation.runners import make_runner
        with self.assertRaises(ValueError) as cm:
            make_runner("nonsense")
        self.assertIn("cursor", str(cm.exception))


class CodexRunnerArgvTests(unittest.TestCase):
    """Verify CodexRunner builds the correct argv and passes the
    prompt on stdin (codex-cli 0.125+ reads stdin when no positional
    prompt is given)."""

    def test_argv_with_default_empty_model_omits_dash_m(self) -> None:
        from bin.skill_derivation.runners import CodexRunner
        from unittest import mock
        runner = CodexRunner()
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                stdout="HELLO", stderr="", returncode=0,
            )
            runner.run("Say HELLO")
            argv = mock_run.call_args.args[0]
            kwargs = mock_run.call_args.kwargs
            self.assertEqual(argv, ["codex", "exec", "--full-auto"])
            self.assertEqual(kwargs.get("input"), "Say HELLO")

    def test_argv_with_explicit_model_includes_dash_m(self) -> None:
        from bin.skill_derivation.runners import CodexRunner
        from unittest import mock
        runner = CodexRunner(model="gpt-5-codex")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                stdout="ok", stderr="", returncode=0,
            )
            runner.run("test")
            argv = mock_run.call_args.args[0]
            self.assertEqual(
                argv,
                ["codex", "exec", "--full-auto", "-m", "gpt-5-codex"],
            )


class CursorRunnerArgvTests(unittest.TestCase):
    """v1.5.4 F-1: verify CursorRunner builds the correct argv and
    passes the prompt on stdin (cursor-cli 3.1+ accepts stdin in
    `--print` mode; verified 2026-04-30)."""

    def test_argv_with_default_empty_model_omits_model_flag(self) -> None:
        from bin.skill_derivation.runners import CursorRunner
        from unittest import mock
        runner = CursorRunner()
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                stdout="HELLO", stderr="", returncode=0,
            )
            runner.run("Say HELLO")
            argv = mock_run.call_args.args[0]
            kwargs = mock_run.call_args.kwargs
            self.assertEqual(argv, ["cursor", "agent", "--print", "--force"])
            self.assertEqual(kwargs.get("input"), "Say HELLO")
            # Post-bootstrap regression pin: cursor 3.1.10 does NOT
            # honor `-` as a stdin sentinel (treats it as the literal
            # prompt). The argv must NOT carry a trailing `-`.
            self.assertNotIn("-", argv[-1:])

    def test_argv_with_explicit_model_includes_model_flag(self) -> None:
        from bin.skill_derivation.runners import CursorRunner
        from unittest import mock
        runner = CursorRunner(model="sonnet-4")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                stdout="ok", stderr="", returncode=0,
            )
            runner.run("test")
            argv = mock_run.call_args.args[0]
            self.assertEqual(
                argv,
                ["cursor", "agent", "--print", "--force", "--model", "sonnet-4"],
            )
            self.assertNotIn("-", argv[-1:])


class Phase4DispatcherSmokeTests(unittest.TestCase):
    """Phase 5 Stage 0: --phase 4 routes to the Phase 4 dispatcher.
    These smoke tests exercise the routing surface without requiring
    full Phase 4 module behavior; they verify _run_phase4 is reached
    with the right target_dir + part values."""

    def test_phase4_part_a1_runs_against_minimal_phase3_artifacts(self) -> None:
        """A.1 only needs pass_c_formal.jsonl + pass_c_formal_use_cases.jsonl
        + pass_a_sections.json. Construct a minimal phase3/ tree and
        verify --phase 4 --part a1 produces an empty
        pass_e_internal_divergences.jsonl without errors."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            p3 = tmp / "quality" / "phase3"
            p3.mkdir(parents=True)
            (p3 / "pass_c_formal.jsonl").write_text("", encoding="utf-8")
            (p3 / "pass_c_formal_use_cases.jsonl").write_text("", encoding="utf-8")
            (p3 / "pass_a_sections.json").write_text(
                json.dumps({"sections": []}), encoding="utf-8"
            )
            rc = main_mod._main([
                str(tmp), "--phase", "4", "--part", "a1",
            ])
            self.assertEqual(rc, 0)
            output = (p3 / "pass_e_internal_divergences.jsonl").read_text(
                encoding="utf-8"
            )
            self.assertEqual(output, "")  # zero records on empty input

    def test_phase4_part_c_emits_info_line_only(self) -> None:
        """Part 'c' (gate enforcement) is accepted by argparse but
        runs via quality_gate.py, not this CLI. The dispatcher emits
        an info line and exits 0 without touching disk."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "quality" / "phase3").mkdir(parents=True)
            rc = main_mod._main([
                str(tmp), "--phase", "4", "--part", "c",
            ])
            self.assertEqual(rc, 0)


# ---------------------------------------------------------------------------
# End-to-end --pass all integration test (Round 5 ND-1).
# ---------------------------------------------------------------------------


@dataclass
class _MockRunner:
    """Deterministic LLM runner for Pass A. Returns one REQ draft per
    call with the section_idx parsed out of the rendered prompt.
    elapsed_ms is set above the Pass A throughput tripwire floor.
    """

    elapsed_ms: int = 30_000
    call_log: List[str] = field(default_factory=list)

    def run(self, prompt: str) -> RunnerResult:
        import re
        self.call_log.append(prompt)
        match = re.search(r"Section index in this run: `(\d+)`", prompt)
        if match is None:
            section_idx = 0
        else:
            section_idx = int(match.group(1))
        # Single REQ per section keeps the fixture predictable.
        record = {
            "draft_idx": 0,
            "section_idx": section_idx,
            "title": f"REQ from section {section_idx}",
            "description": "stub description",
            "acceptance_criteria": "stub acceptance criteria",
            "proposed_source_ref": f"section_idx={section_idx}",
        }
        return RunnerResult(
            stdout=json.dumps(record) + "\n",
            stderr="",
            elapsed_ms=self.elapsed_ms,
            returncode=0,
        )


def _build_synthetic_fixture(root: Path) -> None:
    """Build a small Skill-shaped fixture (SKILL.md + role map)
    suitable for an end-to-end --pass all run. No reference files; the
    integration test focuses on orchestration, not reference-file
    iteration coverage (which has its own targeted tests).

    v1.5.4 Part 1: emits the new exploration_role_map.json artifact
    (a single skill-prose entry covering SKILL.md) instead of the
    retired project_type.json."""
    skill_text = """\
# Synthetic Skill

## Why This Exists

Meta prose -- intentionally allowlisted so Pass A skips it.

## Phase 1: Explore

Operational prose. The orchestrator MUST exit non-zero on missing
SKILL.md. Phase 1 produces EXPLORATION.md with at least 8 findings.

## Phase 2: Plan

Operational prose. The plan must enumerate all phases.

## Phase 3: Build

Operational prose. The build must run all unit tests.
"""
    (root / "SKILL.md").write_text(skill_text, encoding="utf-8")

    quality = root / "quality"
    quality.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "timestamp_start": "2026-04-27T00:00:00Z",
        # v1.5.4 Phase 3.6.1: provenance + summary required.
        "provenance": "git-ls-files",
        "files": [
            {
                "path": "SKILL.md",
                "role": "skill-prose",
                "size_bytes": len(skill_text.encode("utf-8")),
                "rationale": "synthetic fixture skill prose",
            },
        ],
        "breakdown": {
            "files_by_role": {"skill-prose": 1},
            "size_by_role": {"skill-prose": len(skill_text.encode("utf-8"))},
            "percentages": {
                "skill_share": 1.0,
                "code_share": 0.0,
                "tool_share": 0.0,
                "other_share": 0.0,
            },
        },
    }
    payload["summary"] = {
        "file_count": 1,
        "role_breakdown": {"skill-prose": 1},
        "percentages": dict(payload["breakdown"]["percentages"]),
        "provenance": "git-ls-files",
    }
    (quality / "exploration_role_map.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


class PassAllIntegrationTests(unittest.TestCase):
    """Round 5 ND-1: --pass all orchestration body has end-to-end
    coverage. Verifies A -> B -> C -> D run in sequence with B4 gate
    enforced at each transition, all four progress files reach
    status='complete', and the expected artifact set lands."""

    def test_pass_all_runs_a_b_c_d_in_order_with_b4_gate(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _build_synthetic_fixture(tmp)

            mock_runner = _MockRunner()

            # Patch make_runner so --pass all uses MockRunner instead
            # of firing real `claude --print` subprocesses. Pass-spec
            # path defaults to a real file in the brief dir; override
            # with a stub so render_recovery_preamble has something
            # readable on the integration host.
            spec_stub = tmp / "PASS_SPEC_STUB.md"
            spec_stub.write_text("integration test stub", encoding="utf-8")

            with mock.patch.object(
                main_mod, "make_runner", return_value=mock_runner
            ):
                rc = main_mod._main([
                    str(tmp),
                    "--pass", "all",
                    "--runner", "claude",
                    "--pass-spec-path", str(spec_stub),
                ])

            self.assertEqual(rc, 0)

            p3 = tmp / "quality" / "phase3"

            # All four progress files exist and are complete.
            for pass_name in ("a", "b", "c", "d"):
                progress_path = p3 / f"pass_{pass_name}_progress.json"
                self.assertTrue(
                    progress_path.is_file(),
                    f"pass_{pass_name}_progress.json missing",
                )
                state = protocol.read_progress(progress_path)
                self.assertIsNotNone(
                    state, f"pass_{pass_name} progress unreadable"
                )
                self.assertEqual(
                    state.status, "complete",
                    f"pass_{pass_name} did not complete: status={state.status}",
                )

            # Per-pass artifacts at expected paths.
            self.assertTrue((p3 / "pass_a_sections.json").is_file())
            self.assertTrue((p3 / "pass_a_drafts.jsonl").is_file())
            self.assertTrue((p3 / "pass_b_citations.jsonl").is_file())
            self.assertTrue((p3 / "pass_c_formal.jsonl").is_file())
            self.assertTrue((p3 / "pass_d_audit.json").is_file())
            self.assertTrue((p3 / "pass_d_section_coverage.json").is_file())
            self.assertTrue((p3 / "pass_d_council_inbox.json").is_file())

            # Pass A produced records for every non-meta section.
            drafts = [
                json.loads(line)
                for line in (p3 / "pass_a_drafts.jsonl").read_text().splitlines()
                if line.strip()
            ]
            self.assertGreater(len(drafts), 0)
            # The "Why This Exists" meta section is allowlisted; it
            # contributes a skip marker rather than a draft REQ.
            skipped = [d for d in drafts if d.get("skipped")]
            self.assertEqual(
                len(skipped), 1,
                "expected exactly one meta-skip marker for "
                "'Why This Exists'",
            )

            # Pass B emitted one citation record per Pass A draft
            # (including skip markers, which pass through with
            # citation_status='skipped').
            citations = [
                json.loads(line)
                for line in (p3 / "pass_b_citations.jsonl").read_text().splitlines()
                if line.strip()
            ]
            self.assertEqual(len(citations), len(drafts))

            # Pass C emitted formal REQs (verified or council-review).
            formals = [
                json.loads(line)
                for line in (p3 / "pass_c_formal.jsonl").read_text().splitlines()
                if line.strip()
            ]
            self.assertGreater(len(formals), 0)
            # Schemas.md invariant #21: every record populates
            # source_type and never carries the reserved
            # "execution-observation" value.
            for r in formals:
                self.assertIn("source_type", r)
                self.assertNotEqual(r["source_type"], "execution-observation")
                if r["source_type"] == "skill-section":
                    ss = r.get("skill_section")
                    self.assertIsNotNone(ss)
                    self.assertIsInstance(ss, str)
                    self.assertNotEqual(ss.strip(), "")

            # Pass D produced an audit + council inbox.
            audit = json.loads((p3 / "pass_d_audit.json").read_text())
            self.assertIn("promoted", audit)
            self.assertIn("rejected", audit)
            self.assertIn("demoted_to_tier_5", audit)
            inbox = json.loads((p3 / "pass_d_council_inbox.json").read_text())
            self.assertEqual(inbox["schema_version"], "1.0")
            self.assertIsInstance(inbox["items"], list)

    def test_pass_b_refuses_when_pass_a_incomplete(self) -> None:
        """Round 5 ND-1: --pass B run on a fixture whose Pass A never
        completed must fail with UpstreamIncompleteError. This pins
        the B4 gate behavior at the CLI orchestration boundary."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _build_synthetic_fixture(tmp)
            p3 = tmp / "quality" / "phase3"
            p3.mkdir(parents=True, exist_ok=True)
            # Pass A progress with status="running" -> Pass B refuses.
            protocol.write_progress_atomic(
                p3 / "pass_a_progress.json",
                protocol.ProgressState(
                    pass_="A", unit="section", cursor=2, total=10,
                    status="running", last_updated="2026-04-27T00:00:00Z",
                ),
            )
            (p3 / "pass_a_drafts.jsonl").write_text("", encoding="utf-8")

            with self.assertRaises(protocol.UpstreamIncompleteError) as cm:
                main_mod._main([str(tmp), "--pass", "B", "--runner", "claude"])
            self.assertIn("Pass B refused to start", str(cm.exception))

    def test_pass_c_refuses_when_pass_b_incomplete(self) -> None:
        """B4 gate at the C-of-A->B->C->D transition."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _build_synthetic_fixture(tmp)
            p3 = tmp / "quality" / "phase3"
            p3.mkdir(parents=True, exist_ok=True)
            # Pass A complete, Pass B not.
            protocol.write_progress_atomic(
                p3 / "pass_a_progress.json",
                protocol.ProgressState(
                    pass_="A", unit="section", cursor=4, total=4,
                    status="complete", last_updated="2026-04-27T00:00:00Z",
                ),
            )
            protocol.write_progress_atomic(
                p3 / "pass_b_progress.json",
                protocol.ProgressState(
                    pass_="B", unit="draft", cursor=2, total=4,
                    status="running", last_updated="2026-04-27T00:00:00Z",
                ),
            )
            (p3 / "pass_b_citations.jsonl").write_text("", encoding="utf-8")

            with self.assertRaises(protocol.UpstreamIncompleteError) as cm:
                main_mod._main([str(tmp), "--pass", "C", "--runner", "claude"])
            self.assertIn("Pass C refused to start", str(cm.exception))


class ExecutionDivergencePathResolutionTests(unittest.TestCase):
    """v1.5.6 fix-up 071 BUG-002: bin/skill_derivation/__main__.py
    Phase 4 Part B handler resolved `prev_runs` as
    `target_dir / "previous_runs"` — a path archive_run() never
    populates (archive_run writes to `target_dir/quality/previous_runs/`).
    The execution-divergence loader silently passed `None` for every
    legitimate archived run. Fix changed the path to
    `target_dir / "quality" / "previous_runs"`.

    These tests pin the path resolution by mocking
    divergence_execution.run_divergence_execution and asserting the
    config's previous_runs_dir is the quality/-prefixed path.
    """

    def _setup_minimal_phase4_target(self, tmp: Path) -> None:
        """Build the minimum scaffold Phase 4 Part B needs to reach
        the prev_runs computation: SKILL.md + a Pass-C output at
        quality/phase3/pass_c_formal.jsonl + a sections file."""
        (tmp / "SKILL.md").write_text(
            "---\nname: q\nmetadata:\n  version: 1.5.6\n---\n",
            encoding="utf-8",
        )
        p3 = tmp / "quality" / "phase3"
        p3.mkdir(parents=True)
        # Pass C output (the formal-doc manifest) — minimal valid file.
        (p3 / "pass_c_formal.jsonl").write_text(
            '{"req_id":"REQ-001","section_id":"s1","verbatim_quote":"x"}\n',
            encoding="utf-8",
        )
        # Sections file — minimal valid.
        (p3 / "pass_a_sections.jsonl").write_text(
            '{"section_id":"s1","heading_path":["#"],"body":"x"}\n',
            encoding="utf-8",
        )
        # Pass A draft + Pass B citations (Part B may consult).
        (p3 / "pass_a_drafts.jsonl").write_text("", encoding="utf-8")
        (p3 / "pass_b_citations.jsonl").write_text("", encoding="utf-8")

    def test_execution_divergence_resolves_quality_previous_runs(self) -> None:
        """Phase 4 Part B must resolve prev_runs as
        target_dir/quality/previous_runs/, not target_dir/previous_runs/."""
        from bin.skill_derivation import divergence_execution as de
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            self._setup_minimal_phase4_target(tmp)
            # Populate the canonical archive path.
            archive = tmp / "quality" / "previous_runs" / "20260101T000000Z" / "quality"
            archive.mkdir(parents=True)
            (archive / "BUGS.md").write_text(
                "### BUG-001: Sample\n**File:Line**: a.py:10\n",
                encoding="utf-8",
            )
            # The wrong-path location MUST NOT be created — pre-fix
            # used target_dir/previous_runs/ (no quality/ prefix);
            # this verifies the fix prefers the correct path.
            captured: list[object] = []

            def capture_run(cfg):
                captured.append(cfg)
                return {"divergences_emitted": 0}

            with mock.patch.object(
                de, "run_divergence_execution", side_effect=capture_run,
            ):
                main_mod._main([
                    str(tmp), "--phase", "4", "--part", "b",
                ])

            self.assertEqual(
                len(captured), 1,
                "expected divergence_execution to be invoked exactly once",
            )
            cfg = captured[0]
            self.assertIsNotNone(
                cfg.previous_runs_dir,
                "previous_runs_dir must NOT be None — pre-fix was None "
                "because target_dir/previous_runs/ doesn't exist; "
                "post-fix should resolve to target_dir/quality/previous_runs/",
            )
            # Resolve both for comparison — macOS symlinks /var→/private/var
            # so the captured path may have a /private/ prefix that the
            # expected path doesn't.
            self.assertEqual(
                cfg.previous_runs_dir.resolve(),
                (tmp / "quality" / "previous_runs").resolve(),
                "previous_runs_dir must be target_dir/quality/previous_runs/, "
                "matching where archive_run() actually writes",
            )

    def test_execution_divergence_returns_none_when_archive_absent(self) -> None:
        """When the canonical archive path doesn't exist, prev_runs
        is correctly None (regression-protection — the fix must not
        accidentally make a non-existent path look populated)."""
        from bin.skill_derivation import divergence_execution as de
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            self._setup_minimal_phase4_target(tmp)
            captured: list[object] = []

            def capture_run(cfg):
                captured.append(cfg)
                return {"divergences_emitted": 0}

            with mock.patch.object(
                de, "run_divergence_execution", side_effect=capture_run,
            ):
                main_mod._main([
                    str(tmp), "--phase", "4", "--part", "b",
                ])

            cfg = captured[0]
            self.assertIsNone(
                cfg.previous_runs_dir,
                "previous_runs_dir must be None when "
                "target/quality/previous_runs/ does not exist",
            )


if __name__ == "__main__":
    unittest.main()
