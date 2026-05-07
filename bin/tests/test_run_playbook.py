from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
import argparse
import io
import json
import os
import sys
import unittest

from bin import role_map, run_playbook


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_role_map(quality_dir: Path, files=None) -> Path:
    """Write a valid quality/exploration_role_map.json into quality_dir.
    Used by Phase 2 gate tests (v1.5.4 Round 1 Council finding A1/B1/C1)
    that need a role map present on disk."""
    import json
    if files is None:
        files = [{
            "path": "src/main.py", "role": "code",
            "size_bytes": 100, "rationale": "fixture",
        }]
    payload = {
        "schema_version": role_map.SCHEMA_VERSION,
        "timestamp_start": "2026-04-29T00:00:00Z",
        "provenance": "git-ls-files",
        "files": files,
        "breakdown": role_map.compute_breakdown(files),
    }
    payload["summary"] = role_map.summarize_role_map(payload)
    quality_dir.mkdir(parents=True, exist_ok=True)
    out = quality_dir / "exploration_role_map.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


class RunPlaybookTests(unittest.TestCase):
    def test_parse_args_defaults_to_current_directory(self) -> None:
        args = run_playbook.parse_args([])
        self.assertEqual(args.targets, ["."])
        self.assertTrue(args.parallel)
        self.assertEqual(args.runner, "copilot")

    def test_parse_args_accepts_explicit_paths(self) -> None:
        args = run_playbook.parse_args(["./project-a", "/abs/project-b"])
        self.assertEqual(args.targets, ["./project-a", "/abs/project-b"])

    def test_parse_args_validates_iteration_vs_phase(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--next-iteration", "--phase", "3", "./somedir"])

    def test_parse_args_bare_invocation_defaults_to_full_run(self) -> None:
        """v1.5.4 Phase 3.6.6 (B-18a): bare invocation now defaults to
        --full-run. The historical assertion that args.full_run was
        False on a bare invocation is replaced; the v1.5.3 contract
        was that the operator had to type --full-run explicitly,
        which made the canonical command line longer than necessary."""
        args = run_playbook.parse_args(["./somedir"])
        self.assertTrue(args.full_run)

    def test_parse_args_accepts_full_run(self) -> None:
        args = run_playbook.parse_args(["--full-run", "./somedir"])
        self.assertTrue(args.full_run)

    def test_parse_args_rejects_full_run_with_next_iteration(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--full-run", "--next-iteration", "./somedir"])

    def test_parse_args_rejects_full_run_with_phase(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--full-run", "--phase", "3", "./somedir"])

    def test_phase1_prompt_mentions_seed_skip(self) -> None:
        prompt = run_playbook.phase1_prompt(no_seeds=True)
        self.assertIn("Skip Phase 0 and Phase 0b entirely", prompt)
        self.assertIn("quality/EXPLORATION.md", prompt)

    def test_phase1_prompt_pins_progress_md_checkbox_format(self) -> None:
        """Regression test for the 2026-04-21 bus-tracker curated-arm
        abort: Phase 5 gate checks for the substring `- [x] Phase 4` in
        PROGRESS.md, but Phase 1 used to leave the format ambiguous and
        agents sometimes picked a Markdown table. Pin the checkbox form
        in Phase 1's initialization instructions. If this regresses,
        table-format PROGRESS.md files slip through again and the
        Phase 5 gate fires a false abort."""
        prompt = run_playbook.phase1_prompt(no_seeds=True)
        # The exact Phase 1 line the template emits — makes the contract
        # visible in the assertion.
        self.assertIn("- [x] Phase 1", prompt)
        # The Phase 4 line must appear unchecked in the template so the
        # Phase 5 gate's substring check is the only live signal — the
        # template itself doesn't pre-satisfy the gate.
        self.assertIn("- [ ] Phase 4", prompt)
        # Explicit anti-pattern callout so agents know tables are not OK.
        self.assertIn("table", prompt.lower())

    def test_later_phase_prompts_include_checkbox_reminder(self) -> None:
        """Phases 2-6 must reinforce the checkbox format in their
        'mark Phase N complete' instructions — Phase 1's template alone
        isn't enough when an agent re-reads PROGRESS.md mid-run and
        decides to reshape it."""
        for phase_fn, label in (
            (run_playbook.phase2_prompt, "Phase 2 - Generate"),
            (run_playbook.phase3_prompt, "Phase 3 - Code Review"),
            (run_playbook.phase4_prompt, "Phase 4 - Spec Audit"),
            (run_playbook.phase5_prompt, "Phase 5 - Reconciliation"),
            (run_playbook.phase6_prompt, "Phase 6 - Verify"),
        ):
            prompt = phase_fn()
            self.assertIn(f"- [x] {label}", prompt,
                          msg=f"{phase_fn.__name__} missing checkbox reminder for '{label}'")

    def test_iteration_prompt_preserves_checkbox_tracker(self) -> None:
        """Iteration strategies must not reshape PROGRESS.md's phase
        tracker into a table when adding iteration sections."""
        prompt = run_playbook.iteration_prompt("gap")
        self.assertIn("checkbox", prompt.lower())
        self.assertIn("- [x] Phase N", prompt)

    def test_single_pass_prompt_changes_with_seed_mode(self) -> None:
        self.assertIn("Skip Phase 0 and Phase 0b", run_playbook.single_pass_prompt(no_seeds=True))
        self.assertNotIn("Skip Phase 0 and Phase 0b", run_playbook.single_pass_prompt(no_seeds=False))

    def test_phase4_prompt_includes_layer2_semantic_check_steps(self) -> None:
        """Phase 7 r1: phase 4 must instruct the agent to run the Layer-2
        semantic citation check between the spec audit triage and Phase 5."""
        prompt = run_playbook.phase4_prompt()
        # The plan and assemble subcommands must both be referenced.
        self.assertIn("semantic-check plan", prompt)
        self.assertIn("semantic-check assemble", prompt)
        # Output path must be mentioned so the agent verifies it.
        self.assertIn("quality/citation_semantic_check.json", prompt)
        # Council member identifiers come from the config module.
        self.assertIn("claude-opus-4.7", prompt)
        self.assertIn("gpt-5.4", prompt)
        self.assertIn("gemini-2.5-pro", prompt)
        # Spec Gap path must be called out so the agent knows to skip
        # dispatch when there are no Tier 1/2 REQs.
        self.assertIn("Spec Gap", prompt)
        # Invariant #17 framing so the agent understands why the check runs.
        self.assertIn("invariant #17", prompt)

    def test_phase2_gate_requires_exploration_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            gate = run_playbook.check_phase_gate(Path(temp_dir), "2")
            self.assertFalse(gate.ok)
            self.assertIn("EXPLORATION.md missing", gate.messages[0])

    def test_phase2_gate_requires_role_map(self) -> None:
        """v1.5.4 Round 1 Council finding A1/B1/C1: Phase 2 gate fails
        if Phase 1 produced EXPLORATION.md but no role map. Without
        this check the L1 'classifier never wired in' failure mode
        partially re-emerges."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            quality_dir = temp_path / "quality"
            write(quality_dir / "EXPLORATION.md", "x\n" * 200)
            gate = run_playbook.check_phase_gate(temp_path, "2")
            self.assertFalse(gate.ok)
            self.assertIn("exploration_role_map.json", gate.messages[0])
            self.assertIn("Phase 1", gate.messages[0])

    def test_phase2_gate_passes_with_role_map(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            quality_dir = temp_path / "quality"
            write(quality_dir / "EXPLORATION.md", "x\n" * 200)
            write_role_map(quality_dir)
            gate = run_playbook.check_phase_gate(temp_path, "2")
            self.assertTrue(gate.ok, msg=gate.messages)

    def test_phase2_gate_fails_on_invalid_role_map(self) -> None:
        """Bubble validation errors up through the gate so the operator
        knows what's wrong with the role map without grepping logs.

        v1.5.6 cluster 047 changed the gate's failure mode for
        role_maps missing 'files' (or with non-list 'files'): the
        runner-side normalize step catches this BEFORE the validator
        runs and emits a 'could not be normalized' message naming
        the broken field. This test was previously asserting on
        validate_role_map's error wording; updated to assert the
        normalize-step's wording, which is now what operators see
        for this failure mode. Other validate_role_map errors (e.g.
        disallowed-path entries, role enum violations) still bubble
        through with the 'failed validation' wording — exercised by
        other tests in the role_map fixture surface."""
        import json
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            quality_dir = temp_path / "quality"
            write(quality_dir / "EXPLORATION.md", "x\n" * 200)
            # Role map missing required keys (no 'files' field).
            (quality_dir / "exploration_role_map.json").write_text(
                json.dumps({"schema_version": role_map.SCHEMA_VERSION}),
                encoding="utf-8",
            )
            gate = run_playbook.check_phase_gate(temp_path, "2")
            self.assertFalse(gate.ok)
            # The normalize step catches the missing 'files' field
            # and emits an operator-actionable message.
            self.assertIn(
                "could not be normalized", gate.messages[0],
                msg=f"Expected normalize-step error; got: {gate.messages[0]!r}",
            )
            self.assertIn("files", gate.messages[0])

    def test_phase3_gate_requires_phase2_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            quality_dir = temp_path / "quality"
            write(quality_dir / "REQUIREMENTS.md", "ok")
            gate = run_playbook.check_phase_gate(temp_path, "3")
            self.assertFalse(gate.ok)
            self.assertIn("QUALITY.md", gate.messages[0])
            self.assertIn("CONTRACTS.md", gate.messages[0])

    def test_phase4_gate_warns_when_code_reviews_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            quality_dir = temp_path / "quality"
            write(quality_dir / "REQUIREMENTS.md", "ok")
            write(quality_dir / "RUN_SPEC_AUDIT.md", "ok")
            gate = run_playbook.check_phase_gate(temp_path, "4")
            self.assertTrue(gate.ok)
            self.assertEqual(gate.messages, ["GATE WARN Phase 4: no code_reviews/ - Phase 3 may not have run"])

    def test_phase_list_from_mode_expands_all(self) -> None:
        self.assertEqual(run_playbook.phase_list_from_mode("all"), ["1", "2", "3", "4", "5", "6"])
        self.assertEqual(run_playbook.phase_list_from_mode("3,4,5"), ["3", "4", "5"])

    def test_iteration_prompt_contains_strategy(self) -> None:
        """The prompt mentions the strategy by name. It no longer ends
        with exactly 'using the <strategy> strategy.' — the 2026-04-21
        format-drift fix appends a PROGRESS.md checkbox reminder after
        the strategy sentence, so the assertion is substring-based."""
        self.assertIn("using the parity strategy", run_playbook.iteration_prompt("parity"))

    def test_archive_previous_run_archives_and_removes_live_dirs(self) -> None:
        """v1.5.4 Phase 3.6.2 (B-19): archive_previous_run delegates
        to archive_lib.archive_run with status='partial', which now
        lands the archive at quality/previous_runs/<TS>/ with an
        in-archive .partial sentinel (no -PARTIAL filename suffix).

        M8 fix: the archive timestamp pins to the prior run's
        ``run_timestamp_end`` from INDEX.md (not the current run's
        timestamp). The fixture seeds INDEX so the test pin is
        deterministic; without it the chain falls through to
        BUGS.md mtime / current UTC."""
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            write(repo_dir / "quality" / "BUGS.md", "bug")
            write(repo_dir / "quality" / "control_prompts" / "phase1.output.txt", "prompt")
            write(
                repo_dir / "quality" / "INDEX.md",
                '# Run Index\n\n```json\n'
                '{"run_timestamp_start": "2026-04-18T11:30:00Z",'
                ' "run_timestamp_end":   "2026-04-18T12:00:00Z"}\n'
                '```\n',
            )

            run_playbook.archive_previous_run(repo_dir, "20260420T100000Z")

            # Live artifacts cleared; archive subtree survives.
            self.assertFalse((repo_dir / "quality" / "BUGS.md").exists())
            self.assertFalse((repo_dir / "quality" / "control_prompts").exists())
            archive_dir = (
                repo_dir / "quality" / "previous_runs" / "20260418T120000Z"
            )
            archive_root = archive_dir / "quality"
            self.assertEqual(
                (archive_root / "BUGS.md").read_text(encoding="utf-8"),
                "bug",
            )
            self.assertEqual(
                (archive_root / "control_prompts" / "phase1.output.txt").read_text(encoding="utf-8"),
                "prompt",
            )
            # Unified pipeline guarantees per-run INDEX.md + RUN_INDEX row +
            # the .partial sentinel for partial-status archives.
            self.assertTrue((archive_dir / "INDEX.md").is_file())
            self.assertTrue((archive_dir / ".partial").is_file())
            run_index = (repo_dir / "quality" / "RUN_INDEX.md").read_text(encoding="utf-8")
            self.assertIn("20260418T120000Z", run_index)

    def test_archive_previous_run_skips_already_archived_prior(self) -> None:
        """When quality/INDEX.md names a prior run whose archive folder
        already exists (under either previous_runs/ or the legacy runs/),
        archive_previous_run just clears the live tree without producing
        a duplicate archive."""
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            write(repo_dir / "quality" / "BUGS.md", "bug")
            # Pre-existing archive in the new layout.
            existing_archive = (
                repo_dir / "quality" / "previous_runs" / "20260419T100000Z"
            )
            write(existing_archive / "quality" / "BUGS.md", "archived")
            # Live INDEX referencing that run via run_timestamp_end (M8
            # fix: the prior_run lookup now reads _end, not _start).
            write(
                repo_dir / "quality" / "INDEX.md",
                '# Run Index\n\n```json\n'
                '{"run_timestamp_start": "2026-04-19T09:30:00Z",'
                ' "run_timestamp_end":   "2026-04-19T10:00:00Z"}\n'
                '```\n',
            )

            run_playbook.archive_previous_run(repo_dir, "20260420T100000Z")

            self.assertFalse((repo_dir / "quality" / "BUGS.md").exists())
            self.assertTrue(existing_archive.is_dir())
            # No duplicate archive created.
            self.assertFalse(
                (
                    repo_dir / "quality" / "previous_runs" /
                    "20260419T100000Z" / ".partial"
                ).exists()
            )

    def test_clear_live_quality_preserves_both_archive_dirs(self) -> None:
        """v1.5.4 Phase 3.6.2 (B-19, H3 fix): _clear_live_quality
        preserves both `previous_runs/` (current) and `runs/` (legacy)
        plus RUN_INDEX.md. Without this the migration window would
        wipe legacy archives the first time a v1.5.4 run cleared the
        live tree."""
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir) / "quality"
            write(quality / "BUGS.md", "live-bug")
            write(quality / "previous_runs" / "20260418" / "INDEX.md", "new-archive")
            write(quality / "runs" / "20260101" / "INDEX.md", "legacy-archive")
            write(quality / "RUN_INDEX.md", "history")
            run_playbook._clear_live_quality(quality)
            # Live artifact gone.
            self.assertFalse((quality / "BUGS.md").exists())
            # Both archive subtrees + RUN_INDEX preserved.
            self.assertTrue(
                (quality / "previous_runs" / "20260418" / "INDEX.md").is_file()
            )
            self.assertTrue(
                (quality / "runs" / "20260101" / "INDEX.md").is_file()
            )
            self.assertTrue((quality / "RUN_INDEX.md").is_file())

    def test_archive_previous_run_recognises_legacy_runs_layout(self) -> None:
        """v1.5.4 Phase 3.6.2 (B-19): archives from pre-v1.5.4 QPB
        sit under the legacy quality/runs/ layout. archive_previous_run
        must recognise them as already-archived so the live tree
        clears without a duplicate."""
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            write(repo_dir / "quality" / "BUGS.md", "bug")
            existing_archive = (
                repo_dir / "quality" / "runs" / "20260419T100000Z"
            )
            write(existing_archive / "quality" / "BUGS.md", "archived")
            write(
                repo_dir / "quality" / "INDEX.md",
                '# Run Index\n\n```json\n'
                '{"run_timestamp_end": "2026-04-19T10:00:00Z"}\n'
                '```\n',
            )

            run_playbook.archive_previous_run(repo_dir, "20260420T100000Z")

            self.assertFalse((repo_dir / "quality" / "BUGS.md").exists())
            self.assertTrue(existing_archive.is_dir())

    def test_write_live_index_stub_passes_gate_invariant_10(self) -> None:
        """Invariant #10: quality/INDEX.md must exist with §11 fields even
        mid-run. The stub at Phase 1 entry satisfies this."""
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(repo_dir, "20260419T143022Z")
            index = repo_dir / "quality" / "INDEX.md"
            self.assertTrue(index.is_file())
            text = index.read_text(encoding="utf-8")
            self.assertIn("```json", text)
            self.assertIn("run_timestamp_start", text)
            self.assertIn("2026-04-19T14:30:22Z", text)

    def test_final_artifact_gaps_reports_missing_and_empty_when_complete(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            missing = run_playbook.final_artifact_gaps(repo_dir)
            self.assertIn("quality/REQUIREMENTS.md", missing)
            self.assertIn("functional test", missing)

            for artifact in [
                "quality/REQUIREMENTS.md",
                "quality/CONTRACTS.md",
                "quality/COVERAGE_MATRIX.md",
                "quality/COMPLETENESS_REPORT.md",
                "quality/PROGRESS.md",
                "quality/QUALITY.md",
                "quality/RUN_CODE_REVIEW.md",
                "quality/RUN_INTEGRATION_TESTS.md",
                "quality/RUN_SPEC_AUDIT.md",
                "quality/RUN_TDD_TESTS.md",
            ]:
                write(repo_dir / artifact, "ok")
            write(repo_dir / "quality" / "test_functional.py", "ok")

            self.assertEqual(run_playbook.final_artifact_gaps(repo_dir), [])

    def test_command_for_runner_builds_claude_and_copilot_variants(self) -> None:
        claude_default = run_playbook.command_for_runner("claude", "prompt text", None)
        self.assertEqual(claude_default, ["claude", "-p", "prompt text", "--dangerously-skip-permissions"])

        claude_model = run_playbook.command_for_runner("claude", "prompt text", "sonnet")
        self.assertEqual(claude_model, ["claude", "--model", "sonnet", "-p", "prompt text", "--dangerously-skip-permissions"])

        copilot_default = run_playbook.command_for_runner("copilot", "prompt text", None)
        self.assertEqual(copilot_default, ["gh", "copilot", "-p", "prompt text", "--model", run_playbook.lib.DEFAULT_MODEL, "--yolo"])

        copilot_model = run_playbook.command_for_runner("copilot", "prompt text", "gpt-5.5")
        self.assertEqual(copilot_model, ["gh", "copilot", "-p", "prompt text", "--model", "gpt-5.5", "--yolo"])

    def test_build_worker_command_propagates_cursor_runner(self) -> None:
        """v1.5.4 F-1: when the operator passes --cursor, the spawned
        worker subprocess must also receive --cursor (not the default
        --copilot fallback). Regression pin: an earlier draft had the
        runner_flag dict missing the cursor entry."""
        cursor_args = run_playbook.argparse.Namespace(
            parallel=False,
            runner="cursor",
            no_seeds=False,
            phase="3",
            next_iteration=False,
            strategy=["parity"],
            model=None,
            kill=False,
            targets=["./project-a"],
            worker=False,
        )
        command = run_playbook.build_worker_command(cursor_args, "/abs/path/to/target")
        # The runner flag is the fourth element after [python, -m, module, --worker, --sequential]
        self.assertIn("--cursor", command)
        self.assertNotIn("--copilot", command)

    def test_command_for_runner_builds_cursor_variants(self) -> None:
        """v1.5.4 F-1 (post-bootstrap fix): cursor runner builds
        `cursor agent --print --force [--model <model>]` with NO
        positional argument. The prompt is piped on stdin via
        run_kwargs["input"] = prompt at the run_prompt site. Unlike
        codex, cursor 3.1.10 does NOT honor `-` as a stdin sentinel
        (it would be treated as the literal prompt content) — the
        original draft of this runner appended `-` and aborted
        Phase 1 with cursor responding "your last message was only a
        hyphen, so there isn't a clear task yet". The fix: no
        trailing `-`. This regression pin catches a future revert."""
        cursor_default = run_playbook.command_for_runner("cursor", "prompt text", None)
        self.assertEqual(
            cursor_default,
            ["cursor", "agent", "--print", "--force"],
        )
        # Crucial regression assertion: NO trailing "-".
        self.assertNotEqual(cursor_default[-1], "-")

        cursor_model = run_playbook.command_for_runner("cursor", "prompt text", "sonnet-4")
        self.assertEqual(
            cursor_model,
            ["cursor", "agent", "--print", "--force", "--model", "sonnet-4"],
        )
        self.assertNotEqual(cursor_model[-1], "-")

    def test_ensure_runner_available_recognizes_cursor(self) -> None:
        """v1.5.4 F-1: ensure_runner_available checks for the cursor
        binary on PATH. We mock shutil.which to verify the lookup
        targets the right binary name (we don't want the test to
        depend on cursor being installed in the test env)."""
        from unittest import mock
        with mock.patch("bin.run_playbook.shutil.which") as which:
            which.return_value = "/usr/local/bin/cursor"
            self.assertTrue(run_playbook.ensure_runner_available("cursor"))
            which.assert_called_with("cursor")

        with mock.patch("bin.run_playbook.shutil.which") as which:
            which.return_value = None
            self.assertFalse(run_playbook.ensure_runner_available("cursor"))
            which.assert_called_with("cursor")

    def test_command_preview_quotes_shell_arguments(self) -> None:
        preview = run_playbook.command_preview(["gh", "copilot", "-p", "contains spaces", "weird'quote"])
        self.assertEqual(preview, "gh copilot -p 'contains spaces' 'weird'\"'\"'quote'")

    def test_build_worker_command_passes_target_path(self) -> None:
        phased_args = run_playbook.argparse.Namespace(
            parallel=False,
            runner="claude",
            no_seeds=False,
            phase="3,4,5",
            next_iteration=False,
            strategy=["parity"],
            model="sonnet",
            kill=False,
            targets=["./project-a"],
            worker=False,
        )

        command = run_playbook.build_worker_command(phased_args, "/abs/path/to/target")

        # v1.5.4 Phase 3.8: workers invoke via `python -m bin.run_playbook`
        # rather than the script path so A.2's invocation guard
        # accepts them. Tail args are unchanged.
        self.assertEqual(command[0], run_playbook.sys.executable)
        self.assertEqual(command[1], "-m")
        self.assertEqual(command[2], "bin.run_playbook")
        self.assertEqual(
            command[3:],
            [
                "--worker",
                "--sequential",
                "--claude",
                "--with-seeds",
                "--phase",
                "3,4,5",
                "--strategy",
                "parity",
                "--model",
                "sonnet",
                "/abs/path/to/target",
            ],
        )

        iteration_args = run_playbook.argparse.Namespace(
            parallel=False,
            runner="copilot",
            no_seeds=True,
            phase=None,
            next_iteration=True,
            strategy=["parity"],
            model="gpt-5.4",
            kill=False,
            targets=["./project-a"],
            worker=False,
        )
        iteration_command = run_playbook.build_worker_command(iteration_args, "/home/user/project")
        # v1.5.4 Phase 3.8: prefix is python + -m + module name.
        self.assertEqual(
            iteration_command[3:],
            [
                "--worker",
                "--sequential",
                "--copilot",
                "--no-seeds",
                "--next-iteration",
                "--strategy",
                "parity",
                "--model",
                "gpt-5.4",
                "/home/user/project",
            ],
        )

    def test_build_worker_command_includes_full_run(self) -> None:
        full_run_args = run_playbook.argparse.Namespace(
            parallel=True,
            runner="copilot",
            no_seeds=True,
            phase=None,
            next_iteration=False,
            full_run=True,
            strategy=["gap"],
            model=None,
            kill=False,
            targets=["./project-a"],
            worker=False,
        )
        command = run_playbook.build_worker_command(full_run_args, "/abs/path/to/target")
        self.assertIn("--full-run", command)
        self.assertNotIn("--next-iteration", command)

    def test_next_strategy_chain(self) -> None:
        self.assertEqual(run_playbook.next_strategy("gap"), "unfiltered")
        self.assertEqual(run_playbook.next_strategy("unfiltered"), "parity")
        self.assertEqual(run_playbook.next_strategy("parity"), "adversarial")
        self.assertEqual(run_playbook.next_strategy("adversarial"), "")

    def test_print_suggested_next_command_includes_model_and_runtime(self) -> None:
        import io
        from contextlib import redirect_stdout

        args = run_playbook.argparse.Namespace(
            runner="claude",
            next_iteration=False,
            strategy=["gap"],
            model="sonnet",
            targets=["express-1.4.5"],
        )

        original_argv = run_playbook.sys.argv
        original_executable = run_playbook.sys.executable
        try:
            run_playbook.sys.argv = ["../bin/run_playbook.py"]
            run_playbook.sys.executable = "/usr/bin/python3"
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_playbook.print_suggested_next_command(args)
        finally:
            run_playbook.sys.argv = original_argv
            run_playbook.sys.executable = original_executable

        output = buf.getvalue()
        # v1.5.6 cluster 044: assertion updated from the pre-fix
        # `python3 ../bin/run_playbook.py` (script-path form) to the
        # canonical `-m bin.run_playbook` form. The script-path form
        # is rejected by the package-module guard at the bottom of
        # bin/run_playbook.py with EX_USAGE=64 — emitting it in the
        # suggestion was Bug A.
        self.assertIn("python3 -m bin.run_playbook", output)
        self.assertIn("--claude", output)
        self.assertIn("--model sonnet", output)
        self.assertIn("--next-iteration --strategy gap", output)
        self.assertIn("express-1.4.5", output)

    def test_print_suggested_next_command_omits_model_when_unset(self) -> None:
        import io
        from contextlib import redirect_stdout

        args = run_playbook.argparse.Namespace(
            runner="copilot",
            next_iteration=True,
            strategy=["unfiltered"],
            model=None,
            targets=["chi-1.4.5"],
        )

        original_argv = run_playbook.sys.argv
        try:
            run_playbook.sys.argv = ["bin/run_playbook.py"]
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_playbook.print_suggested_next_command(args)
        finally:
            run_playbook.sys.argv = original_argv

        output = buf.getvalue()
        self.assertNotIn("--model", output)
        self.assertNotIn("--claude", output)
        self.assertIn("--next-iteration --strategy parity", output)

    def test_count_lines_handles_missing_and_existing_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self.assertEqual(run_playbook.count_lines(temp_path / "missing.txt"), 0)
            write(temp_path / "present.txt", "one\ntwo\nthree\n")
            self.assertEqual(run_playbook.count_lines(temp_path / "present.txt"), 3)

    def test_check_phase_gate_covers_all_phases(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            quality_dir = temp_path / "quality"

            phase1 = run_playbook.check_phase_gate(temp_path, "1")
            self.assertTrue(phase1.ok)
            self.assertEqual(phase1.messages, [])

            write(quality_dir / "EXPLORATION.md", "x\n" * 10)
            phase2_fail = run_playbook.check_phase_gate(temp_path, "2")
            self.assertFalse(phase2_fail.ok)
            self.assertEqual(len(phase2_fail.messages), 1)
            self.assertIn("expected 120+", phase2_fail.messages[0])

            write(quality_dir / "EXPLORATION.md", "x\n" * 200)
            # v1.5.4 Phase 2 gate also requires the role map.
            write_role_map(quality_dir)
            phase2_ok = run_playbook.check_phase_gate(temp_path, "2")
            self.assertTrue(phase2_ok.ok, msg=phase2_ok.messages)
            self.assertEqual(phase2_ok.messages, [])

            for name in [
                "QUALITY.md", "CONTRACTS.md", "RUN_CODE_REVIEW.md", "REQUIREMENTS.md",
                "COVERAGE_MATRIX.md", "COMPLETENESS_REPORT.md",
                "RUN_INTEGRATION_TESTS.md", "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
            ]:
                write(quality_dir / name, "ok")
            phase3_ok = run_playbook.check_phase_gate(temp_path, "3")
            self.assertTrue(phase3_ok.ok)
            self.assertEqual(phase3_ok.messages, [])

            phase4_fail = run_playbook.check_phase_gate(Path(temp_dir) / "other", "4")
            self.assertFalse(phase4_fail.ok)
            self.assertIn("REQUIREMENTS.md missing", phase4_fail.messages[0])

            write(quality_dir / "RUN_SPEC_AUDIT.md", "ok")
            code_reviews = quality_dir / "code_reviews"
            code_reviews.mkdir(parents=True, exist_ok=True)
            write(code_reviews / "review.md", "ok")
            phase4_ok = run_playbook.check_phase_gate(temp_path, "4")
            self.assertTrue(phase4_ok.ok)
            self.assertEqual(phase4_ok.messages, [])

            write(quality_dir / "PROGRESS.md", "- [x] Phase 4\n")
            spec_audits = quality_dir / "spec_audits"
            spec_audits.mkdir(parents=True, exist_ok=True)
            write(spec_audits / "2026-04-19-triage.md", "ok")
            write(spec_audits / "2026-04-19-auditor-1.md", "ok")
            phase5_warn = run_playbook.check_phase_gate(temp_path, "5")
            self.assertTrue(phase5_warn.ok)
            self.assertEqual(phase5_warn.messages, ["GATE WARN Phase 5: no BUGS.md - Phase 3 may not have run"])

            write(quality_dir / "BUGS.md", "ok")
            phase5_ok = run_playbook.check_phase_gate(temp_path, "5")
            self.assertTrue(phase5_ok.ok)
            self.assertEqual(phase5_ok.messages, [])

            phase6_ok = run_playbook.check_phase_gate(temp_path, "6")
            self.assertTrue(phase6_ok.ok)
            self.assertEqual(phase6_ok.messages, [])

            phase6_fail = run_playbook.check_phase_gate(Path(temp_dir) / "missing-progress", "6")
            self.assertFalse(phase6_fail.ok)
            self.assertIn("PROGRESS.md missing", phase6_fail.messages[0])

    # --- Path-based target resolution (replaces the old version-matching tests) ---

    def test_resolve_target_dirs_absolute_path_passes_through(self) -> None:
        with TemporaryDirectory() as temp_dir:
            resolved, warnings, errors = run_playbook.resolve_target_dirs([temp_dir])
            self.assertEqual(resolved, [Path(temp_dir).resolve()])
            self.assertEqual(errors, [])
            # No skill installed -> warning about missing SKILL.md
            self.assertEqual(len(warnings), 1)
            self.assertIn("No SKILL.md found", warnings[0])

    def test_resolve_target_dirs_relative_path_anchors_to_cwd(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()
            sub = temp_path / "project"
            sub.mkdir()
            prior_cwd = Path.cwd()
            try:
                os.chdir(temp_path)
                resolved, _, errors = run_playbook.resolve_target_dirs(["./project"])
            finally:
                os.chdir(prior_cwd)
            self.assertEqual(resolved, [sub])
            self.assertEqual(errors, [])

    def test_resolve_target_dirs_dot_resolves_to_cwd(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()
            prior_cwd = Path.cwd()
            try:
                os.chdir(temp_path)
                resolved, _, errors = run_playbook.resolve_target_dirs(["."])
            finally:
                os.chdir(prior_cwd)
            self.assertEqual(resolved, [temp_path])
            self.assertEqual(errors, [])

    def test_resolve_target_dirs_non_directory_is_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "does-not-exist"
            resolved, warnings, errors = run_playbook.resolve_target_dirs([str(missing)])
            self.assertEqual(resolved, [])
            self.assertEqual(warnings, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("is not a directory", errors[0])

    def test_resolve_target_dirs_suppresses_skill_warning_when_installed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()
            write(temp_path / ".github" / "skills" / "SKILL.md", "version: 1.4.4\n")
            resolved, warnings, errors = run_playbook.resolve_target_dirs([str(temp_path)])
            self.assertEqual(resolved, [temp_path])
            self.assertEqual(warnings, [])
            self.assertEqual(errors, [])

    def test_log_file_for_places_log_beside_target(self) -> None:
        target = Path("/tmp/my-project").resolve()
        log_path = run_playbook.log_file_for(target, "20260418-130000")
        self.assertEqual(log_path.parent, target.parent)
        self.assertEqual(log_path.name, f"{target.name}-playbook-20260418-130000.log")

    # --- Strategy list parsing and dispatch (Issue 2) ---

    def test_parse_strategy_list_single(self) -> None:
        self.assertEqual(run_playbook.parse_strategy_list("gap"), ["gap"])
        self.assertEqual(run_playbook.parse_strategy_list("parity"), ["parity"])

    def test_parse_strategy_list_multi(self) -> None:
        self.assertEqual(
            run_playbook.parse_strategy_list("unfiltered,parity,adversarial"),
            ["unfiltered", "parity", "adversarial"],
        )

    def test_parse_strategy_list_all_expands_to_full_chain(self) -> None:
        self.assertEqual(
            run_playbook.parse_strategy_list("all"),
            ["gap", "unfiltered", "parity", "adversarial"],
        )

    def test_parse_strategy_list_rejects_all_in_list(self) -> None:
        import argparse as _argparse
        with self.assertRaises(_argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("all,gap")
        with self.assertRaises(_argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("gap,all")

    def test_parse_strategy_list_rejects_duplicate(self) -> None:
        import argparse as _argparse
        with self.assertRaises(_argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("gap,gap")
        with self.assertRaises(_argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("unfiltered,parity,unfiltered")

    def test_parse_strategy_list_rejects_unknown(self) -> None:
        import argparse as _argparse
        with self.assertRaises(_argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("bogus")
        with self.assertRaises(_argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("gap,bogus,parity")

    def test_parse_strategy_list_rejects_empty(self) -> None:
        import argparse as _argparse
        with self.assertRaises(_argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("")
        with self.assertRaises(_argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("gap,,parity")

    def test_parse_args_accepts_strategy_list(self) -> None:
        args = run_playbook.parse_args([
            "--next-iteration",
            "--strategy", "unfiltered,parity,adversarial",
            "./somedir",
        ])
        self.assertEqual(args.strategy, ["unfiltered", "parity", "adversarial"])

    def test_parse_args_default_strategy_is_list(self) -> None:
        args = run_playbook.parse_args(["./somedir"])
        self.assertEqual(args.strategy, ["gap"])

    def test_parse_args_strategy_all_expands(self) -> None:
        args = run_playbook.parse_args([
            "--next-iteration", "--strategy", "all", "./somedir",
        ])
        self.assertEqual(args.strategy, ["gap", "unfiltered", "parity", "adversarial"])

    def test_parse_args_rejects_invalid_strategy(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--strategy", "bogus", "./somedir"])

    def test_build_worker_command_serializes_strategy_list(self) -> None:
        args = run_playbook.argparse.Namespace(
            parallel=True,
            runner="copilot",
            no_seeds=True,
            phase=None,
            next_iteration=True,
            full_run=False,
            strategy=["unfiltered", "parity", "adversarial"],
            model=None,
            kill=False,
            targets=["./project-a"],
            worker=False,
        )
        command = run_playbook.build_worker_command(args, "/abs/path/to/target")
        # The list is serialized as a single comma-separated token so the worker's
        # parse_strategy_list reconstructs the same list.
        strategy_idx = command.index("--strategy")
        self.assertEqual(command[strategy_idx + 1], "unfiltered,parity,adversarial")

    def test_print_suggested_next_command_partial_phase_suggests_remaining(self) -> None:
        """After --phase 1,2, next step is --phase 3,4,5,6 — not an iteration."""
        import io
        from contextlib import redirect_stdout

        args = run_playbook.argparse.Namespace(
            runner="claude",
            next_iteration=False,
            strategy=["gap"],
            model="claude-opus-4-7",
            targets=["quality-playbook"],
            phase="1,2",
        )
        original_argv = run_playbook.sys.argv
        try:
            run_playbook.sys.argv = ["bin/run_playbook.py"]
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_playbook.print_suggested_next_command(args)
        finally:
            run_playbook.sys.argv = original_argv
        output = buf.getvalue()

        self.assertIn("--phase 3,4,5,6", output)
        self.assertIn("Next phase suggestion:", output)
        # Model override hint appears
        self.assertIn("swap --model", output)
        # Iteration suggestion must NOT appear after a partial phase run.
        self.assertNotIn("--next-iteration", output)

    def test_print_suggested_next_command_partial_phase_preserves_runner_and_target(self) -> None:
        import io
        from contextlib import redirect_stdout

        args = run_playbook.argparse.Namespace(
            runner="claude",
            next_iteration=False,
            strategy=["gap"],
            model="claude-opus-4-7",
            targets=["quality-playbook"],
            phase="3,5",
        )
        original_argv = run_playbook.sys.argv
        try:
            run_playbook.sys.argv = ["bin/run_playbook.py"]
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_playbook.print_suggested_next_command(args)
        finally:
            run_playbook.sys.argv = original_argv
        output = buf.getvalue()
        # Remaining phases are in numeric order, not source-list order.
        self.assertIn("--phase 1,2,4,6", output)
        self.assertIn("--claude", output)
        self.assertIn("--model claude-opus-4-7", output)
        self.assertIn("quality-playbook", output)

    def test_print_suggested_next_command_phase_all_keeps_iteration_suggestion(self) -> None:
        """--phase all means every phase ran; iteration suggestion stays."""
        import io
        from contextlib import redirect_stdout

        args = run_playbook.argparse.Namespace(
            runner="copilot",
            next_iteration=False,
            strategy=["gap"],
            model=None,
            targets=["chi-1.4.5"],
            phase="all",
        )
        original_argv = run_playbook.sys.argv
        try:
            run_playbook.sys.argv = ["bin/run_playbook.py"]
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_playbook.print_suggested_next_command(args)
        finally:
            run_playbook.sys.argv = original_argv
        output = buf.getvalue()
        self.assertNotIn("Next phase suggestion:", output)
        self.assertIn("--next-iteration --strategy gap", output)

    def test_print_suggested_next_command_phase_none_keeps_iteration_suggestion(self) -> None:
        """Single-prompt mode (no --phase) always suggests an iteration next."""
        import io
        from contextlib import redirect_stdout

        args = run_playbook.argparse.Namespace(
            runner="copilot",
            next_iteration=False,
            strategy=["gap"],
            model=None,
            targets=["chi-1.4.5"],
            phase=None,
        )
        original_argv = run_playbook.sys.argv
        try:
            run_playbook.sys.argv = ["bin/run_playbook.py"]
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_playbook.print_suggested_next_command(args)
        finally:
            run_playbook.sys.argv = original_argv
        output = buf.getvalue()
        self.assertNotIn("Next phase suggestion:", output)
        self.assertIn("--next-iteration --strategy gap", output)

    def test_print_suggested_next_command_explicit_full_phase_list_is_complete(self) -> None:
        """--phase 1,2,3,4,5,6 is equivalent to --phase all — iteration suggestion."""
        import io
        from contextlib import redirect_stdout

        args = run_playbook.argparse.Namespace(
            runner="copilot",
            next_iteration=False,
            strategy=["gap"],
            model=None,
            targets=["chi-1.4.5"],
            phase="1,2,3,4,5,6",
        )
        original_argv = run_playbook.sys.argv
        try:
            run_playbook.sys.argv = ["bin/run_playbook.py"]
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_playbook.print_suggested_next_command(args)
        finally:
            run_playbook.sys.argv = original_argv
        output = buf.getvalue()
        self.assertNotIn("Next phase suggestion:", output)
        self.assertIn("--next-iteration --strategy gap", output)

    def test_print_suggested_next_command_list_midchain(self) -> None:
        import io
        from contextlib import redirect_stdout

        args = run_playbook.argparse.Namespace(
            runner="copilot",
            next_iteration=True,
            strategy=["unfiltered", "parity"],  # ends at parity; successor is adversarial
            model=None,
            targets=["chi-1.4.5"],
        )
        original_argv = run_playbook.sys.argv
        try:
            run_playbook.sys.argv = ["bin/run_playbook.py"]
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_playbook.print_suggested_next_command(args)
        finally:
            run_playbook.sys.argv = original_argv
        output = buf.getvalue()
        self.assertIn("--next-iteration --strategy adversarial", output)
        self.assertNotIn("Iteration cycle complete", output)

    def test_print_suggested_next_command_list_ending_at_adversarial(self) -> None:
        import io
        from contextlib import redirect_stdout

        args = run_playbook.argparse.Namespace(
            runner="copilot",
            next_iteration=True,
            strategy=["parity", "adversarial"],
            model=None,
            targets=["chi-1.4.5"],
        )
        original_argv = run_playbook.sys.argv
        try:
            run_playbook.sys.argv = ["bin/run_playbook.py"]
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_playbook.print_suggested_next_command(args)
        finally:
            run_playbook.sys.argv = original_argv
        output = buf.getvalue()
        self.assertIn("Iteration cycle complete", output)
        self.assertIn("To start fresh", output)
        # Should NOT suggest --next-iteration anywhere (cycle is done).
        self.assertNotIn("--next-iteration", output)

    # --- v1.5.6 cluster 050: --benchmark-mode + Phase 4 Council banner ---

    def test_benchmark_mode_forces_phase_1_2_3(self) -> None:
        """`--benchmark-mode` forces args.phase = '1,2,3' regardless
        of any other phase config."""
        from bin import run_playbook
        args = run_playbook.parse_args([
            "--benchmark-mode", "--copilot", "--model", "haiku-4.5",
            "/some/target",
        ])
        self.assertTrue(args.benchmark_mode)
        self.assertEqual(args.phase, "1,2,3")

    def test_benchmark_mode_mutex_with_full_run(self) -> None:
        from bin import run_playbook
        with self.assertRaises(SystemExit):
            run_playbook.parse_args([
                "--benchmark-mode", "--full-run", "/some/target",
            ])

    def test_benchmark_mode_mutex_with_next_iteration(self) -> None:
        from bin import run_playbook
        with self.assertRaises(SystemExit):
            run_playbook.parse_args([
                "--benchmark-mode", "--next-iteration", "/some/target",
            ])

    def test_benchmark_mode_mutex_with_iterations(self) -> None:
        from bin import run_playbook
        with self.assertRaises(SystemExit):
            run_playbook.parse_args([
                "--benchmark-mode", "--iterations", "gap,unfiltered",
                "/some/target",
            ])

    def test_benchmark_mode_mutex_with_strategy(self) -> None:
        from bin import run_playbook
        with self.assertRaises(SystemExit):
            run_playbook.parse_args([
                "--benchmark-mode", "--strategy", "parity",
                "/some/target",
            ])

    def test_benchmark_mode_mutex_with_phase_other_than_123(self) -> None:
        from bin import run_playbook
        with self.assertRaises(SystemExit):
            run_playbook.parse_args([
                "--benchmark-mode", "--phase", "1,2,3,4",
                "/some/target",
            ])

    def test_benchmark_mode_phase_1_2_3_explicit_is_compatible(self) -> None:
        """Passing --phase 1,2,3 alongside --benchmark-mode is fine
        — they both express the same scope."""
        from bin import run_playbook
        args = run_playbook.parse_args([
            "--benchmark-mode", "--phase", "1,2,3", "/some/target",
        ])
        self.assertTrue(args.benchmark_mode)
        self.assertEqual(args.phase, "1,2,3")

    def test_benchmark_mode_banner_emitted_in_run_header(self) -> None:
        """display_run_header prints the BENCHMARK MODE banner before
        the standard header when args.benchmark_mode is True."""
        import io
        from contextlib import redirect_stdout
        from bin import run_playbook
        args = run_playbook.argparse.Namespace(
            benchmark_mode=True,
            runner="copilot",
            model="claude-haiku-4.5",
            no_seeds=True,
            no_formal_docs=False,
            no_stdout_echo=False,
            verbose=False,
            quiet=False,
            progress_interval=2,
            parallel=False,
            full_run=False,
            next_iteration=False,
            phase="1,2,3",
            strategy=["gap"],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            run_playbook.display_run_header(
                args, [Path("/some/target")], "1.5.6", ["1", "2", "3"], "20260507-000000",
            )
        output = buf.getvalue()
        self.assertIn("BENCHMARK MODE", output)
        self.assertIn("claude-haiku-4.5", output)
        self.assertIn("phases 1-3 only", output)
        # And the standard header still appears below.
        self.assertIn("=== Quality Playbook - Artifact Generation ===", output)

    def test_no_benchmark_banner_without_benchmark_mode(self) -> None:
        import io
        from contextlib import redirect_stdout
        from bin import run_playbook
        args = run_playbook.argparse.Namespace(
            benchmark_mode=False,
            runner="copilot",
            model="claude-haiku-4.5",
            no_seeds=True,
            no_formal_docs=False,
            no_stdout_echo=False,
            verbose=False,
            quiet=False,
            progress_interval=2,
            parallel=False,
            full_run=False,
            next_iteration=False,
            phase="all",
            strategy=["gap"],
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            run_playbook.display_run_header(
                args, [Path("/some/target")], "1.5.6",
                ["1", "2", "3", "4", "5", "6"], "20260507-000000",
            )
        output = buf.getvalue()
        self.assertNotIn("BENCHMARK MODE", output)

    def test_run_mode_marker_written_for_benchmark_mode(self) -> None:
        """quality/RUN_MODE.md is written when benchmark_mode is set."""
        from bin import run_playbook
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            args = run_playbook.argparse.Namespace(
                benchmark_mode=True,
                runner="copilot",
                model="haiku-4.5",
            )
            run_playbook._write_run_mode_marker(repo, args, "20260507-000000")
            marker = repo / "quality" / "RUN_MODE.md"
            self.assertTrue(marker.is_file())
            text = marker.read_text(encoding="utf-8")
            self.assertIn("benchmark", text)
            self.assertIn("haiku-4.5", text)
            self.assertIn("Phase scope: 1,2,3", text)
            self.assertIn("Council audit: SKIPPED", text)

    def test_phase4_council_banner_reads_roster_programmatically(self) -> None:
        """Phase 4 Council banner is wired into run_one_phase via a
        source-grep guard (the actual banner output is captured at
        run-time when a real Phase 4 invocation happens; this test
        pins the wiring so a future refactor can't silently drop it)."""
        import inspect
        from bin import run_playbook
        source = inspect.getsource(run_playbook.run_one_phase)
        # Pin: banner fires for phase=="4".
        self.assertIn('if phase == "4":', source)
        # Pin: roster is read programmatically from council_config.
        self.assertIn("from bin import council_config", source)
        self.assertIn("council_config.council_members()", source)
        # Pin: banner content includes the Council-of-Three label.
        self.assertIn("Council of Three", source)
        # Pin: banner mentions --benchmark-mode for the alternative.
        self.assertIn("--benchmark-mode", source)

    def test_council_config_provides_council_members_helper(self) -> None:
        """The cluster-050 banner reads the roster via
        bin.council_config.council_members(); pin that the helper
        exists and returns a non-empty tuple."""
        from bin import council_config
        roster = council_config.council_members()
        self.assertIsInstance(roster, tuple)
        self.assertGreater(len(roster), 0)
        # Each entry is a non-empty string (model name).
        for member in roster:
            self.assertIsInstance(member, str)
            self.assertTrue(member.strip())

    # --- v1.5.6 cluster 044: --next-iteration suggestion bugs A + B ---

    def test_print_suggested_next_command_uses_canonical_m_form(self) -> None:
        """Bug A regression: the suggestion line MUST emit the
        canonical `python3 -m bin.run_playbook` form, NOT the
        `<interpreter> <script_path>` form. The latter is rejected
        by the runner's own guard at the package-module check
        (sys.exit(64) EX_USAGE), so emitting it here would be
        self-contradictory and break copy-paste workflows.

        Verify across all four prefix-consuming call sites:
        --phase partial-coverage, --next-iteration with strategy,
        --next-iteration without strategy (cycle complete), and
        the no-iteration default-suggestion branch."""
        import io
        from contextlib import redirect_stdout

        scenarios = [
            # (description, args dict)
            ("partial-phase remaining", dict(
                runner="claude", next_iteration=False, strategy=["gap"],
                model="sonnet", targets=["chi-1.4.5"], phase="1,2",
            )),
            ("--next-iteration with strategy", dict(
                runner="claude", next_iteration=True, strategy=["gap"],
                model=None, targets=["chi-1.4.5"], phase="all",
            )),
            ("--next-iteration cycle complete", dict(
                runner="claude", next_iteration=True,
                strategy=["parity", "adversarial"],
                model=None, targets=["chi-1.4.5"], phase="all",
            )),
            ("default no-iteration", dict(
                runner="claude", next_iteration=False, strategy=["gap"],
                model=None, targets=["chi-1.4.5"], phase=None,
            )),
        ]

        for description, kwargs in scenarios:
            with self.subTest(scenario=description):
                args = run_playbook.argparse.Namespace(**kwargs)
                original_argv = run_playbook.sys.argv
                try:
                    # Set sys.argv to a script-path form to confirm the
                    # output does NOT echo it back. Pre-fix, the prefix
                    # was f"{interpreter} {sys.argv[0]}" which would
                    # leak this path into the output.
                    run_playbook.sys.argv = ["/full/path/to/bin/run_playbook.py"]
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        run_playbook.print_suggested_next_command(args)
                finally:
                    run_playbook.sys.argv = original_argv

                output = buf.getvalue()
                self.assertIn(
                    "-m bin.run_playbook", output,
                    f"[{description}] suggestion must emit the "
                    f"canonical `-m bin.run_playbook` form. Output: "
                    f"{output!r}",
                )
                # The pre-fix script-path form would appear as
                # `bin/run_playbook.py` (or the absolute path); both
                # are rejected by the runner's package-module guard.
                self.assertNotIn(
                    "/bin/run_playbook.py", output,
                    f"[{description}] suggestion must NOT emit the "
                    f"`<script-path>` form — the runner's own guard "
                    f"rejects it with EX_USAGE=64. Output: {output!r}",
                )
                self.assertNotIn(
                    " bin/run_playbook.py", output,
                    f"[{description}] same — relative-path script "
                    f"form is also rejected. Output: {output!r}",
                )

    def test_print_suggested_next_command_runner_flag_per_runner(self) -> None:
        """Bug B regression: the runner_flag dict must include
        `copilot`. Pre-fix the dict had only claude/codex/cursor;
        when the user invoked with --copilot, the suggestion silently
        dropped the flag and copy-paste switched the user to default
        --claude (since --claude is the new default per
        bin/run_playbook.py argparse).

        Parametric across all four supported runners. Each runner
        name must produce a `--<runner>` flag in the suggestion."""
        import io
        from contextlib import redirect_stdout

        for runner in ("claude", "copilot", "codex", "cursor"):
            with self.subTest(runner=runner):
                args = run_playbook.argparse.Namespace(
                    runner=runner,
                    next_iteration=False,
                    strategy=["gap"],
                    model=None,
                    targets=["chi-1.4.5"],
                    phase=None,
                )
                original_argv = run_playbook.sys.argv
                try:
                    run_playbook.sys.argv = ["bin/run_playbook.py"]
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        run_playbook.print_suggested_next_command(args)
                finally:
                    run_playbook.sys.argv = original_argv

                output = buf.getvalue()
                self.assertIn(
                    f"--{runner}", output,
                    f"--{runner} must appear in the suggestion when "
                    f"args.runner={runner!r}. Pre-fix the runner_flag "
                    f"dict was missing `copilot`, silently dropping "
                    f"the flag for copilot users. Output: {output!r}",
                )
                # And no other runner flag should appear (this catches
                # an inverse regression where runner_flag is hard-coded
                # to a single value).
                for other in ("claude", "copilot", "codex", "cursor"):
                    if other == runner:
                        continue
                    self.assertNotIn(
                        f"--{other}", output,
                        f"--{other} must NOT appear when "
                        f"args.runner={runner!r}. The suggestion is "
                        f"leaking a wrong runner flag. Output: {output!r}",
                    )

    # --- PID file (per-parent) cleanup (Issue 3) ---

    def test_pid_file_for_parent_is_unique_per_process(self) -> None:
        import os as _os
        expected = run_playbook.PID_FILE.parent / f"{run_playbook.PID_FILE.name}.{_os.getpid()}"
        self.assertEqual(run_playbook.pid_file_for_parent(), expected)

    def test_discover_pid_files_returns_all_per_parent_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            base = temp_path / ".run_pids"
            # Create three per-parent files
            (temp_path / f"{base.name}.111").write_text("111 repoA\n")
            (temp_path / f"{base.name}.222").write_text("222 repoB\n")
            (temp_path / f"{base.name}.333").write_text("333 repoC\n")
            # And an unrelated file that shouldn't match
            (temp_path / "unrelated.txt").write_text("skip")

            original_pid_file = run_playbook.PID_FILE
            try:
                run_playbook.PID_FILE = base
                found = run_playbook.discover_pid_files()
            finally:
                run_playbook.PID_FILE = original_pid_file

            self.assertEqual(len(found), 3)
            self.assertEqual(
                {p.name for p in found},
                {f"{base.name}.111", f"{base.name}.222", f"{base.name}.333"},
            )

    def test_write_pid_file_writes_to_per_parent_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            original_pid_file = run_playbook.PID_FILE
            try:
                run_playbook.PID_FILE = Path(temp_dir) / ".run_pids"
                path = run_playbook.write_pid_file([(4242, "chi-1.4.5"), (4243, "cobra-1.4.5")])
                self.assertTrue(path.exists())
                self.assertTrue(path.name.startswith(".run_pids."))
                content = path.read_text(encoding="utf-8")
                self.assertIn("4242 chi-1.4.5", content)
                self.assertIn("4243 cobra-1.4.5", content)
            finally:
                run_playbook.PID_FILE = original_pid_file


class FormalDocsGuardTests(unittest.TestCase):
    """v1.5.2: pre-run reference_docs/ guard + --no-formal-docs (flag name preserved)."""

    def test_missing_directory_triggers_warning(self) -> None:
        with TemporaryDirectory() as temp_dir:
            banner = run_playbook.formal_docs_guard_banner(Path(temp_dir))
            self.assertIsNotNone(banner)
            self.assertIn("reference_docs/ is missing", banner)
            self.assertIn("--no-formal-docs", banner)

    def test_empty_directory_triggers_warning(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "reference_docs").mkdir()
            banner = run_playbook.formal_docs_guard_banner(repo)
            self.assertIsNotNone(banner)
            self.assertIn("reference_docs/ is empty", banner)

    def test_top_level_file_is_clean(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            ref = repo / "reference_docs"
            ref.mkdir()
            write(ref / "design-notes.md", "Freeform notes.\n")
            self.assertIsNone(run_playbook.formal_docs_guard_banner(repo))

    def test_cite_file_is_clean(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            cite = repo / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            write(cite / "spec.md", "# Spec\n")
            self.assertIsNone(run_playbook.formal_docs_guard_banner(repo))

    def test_readme_only_is_empty(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            ref = repo / "reference_docs"
            ref.mkdir()
            write(ref / "README.md", "folder readme\n")
            banner = run_playbook.formal_docs_guard_banner(repo)
            self.assertIsNotNone(banner)
            self.assertIn("reference_docs/ is empty", banner)

    def test_parse_args_accepts_no_formal_docs(self) -> None:
        args = run_playbook.parse_args(["--no-formal-docs", "./somedir"])
        self.assertTrue(args.no_formal_docs)
        # Default off.
        args_default = run_playbook.parse_args(["./somedir"])
        self.assertFalse(args_default.no_formal_docs)

    def test_build_worker_command_propagates_no_formal_docs(self) -> None:
        args = run_playbook.argparse.Namespace(
            parallel=False,
            runner="claude",
            no_seeds=False,
            phase=None,
            next_iteration=False,
            full_run=False,
            strategy=["gap"],
            model=None,
            no_formal_docs=True,
            kill=False,
            targets=["./project-a"],
            worker=False,
        )
        command = run_playbook.build_worker_command(args, "/abs/target")
        self.assertIn("--no-formal-docs", command)
        # Flag appears before the positional target.
        self.assertLess(
            command.index("--no-formal-docs"), command.index("/abs/target")
        )

    def test_build_worker_command_omits_flag_when_unset(self) -> None:
        args = run_playbook.argparse.Namespace(
            parallel=False,
            runner="claude",
            no_seeds=False,
            phase=None,
            next_iteration=False,
            full_run=False,
            strategy=["gap"],
            model=None,
            no_formal_docs=False,
            kill=False,
            targets=["./project-a"],
            worker=False,
        )
        command = run_playbook.build_worker_command(args, "/abs/target")
        self.assertNotIn("--no-formal-docs", command)


class InvocationFlagsPersistenceTests(unittest.TestCase):
    """v1.5.1 Phase 1 rev (Council — gpt-5.4 blocker 2): the --no-formal-docs
    flag must land in quality/INDEX.md under invocation_flags so a later
    auditor can tell intent from accident."""

    @staticmethod
    def _load_index(repo_dir: Path) -> dict:
        import json as _json
        text = (repo_dir / "quality" / "INDEX.md").read_text(encoding="utf-8")
        start = text.index("```json")
        end = text.index("```", start + len("```json"))
        return _json.loads(text[start + len("```json"): end])

    def test_stub_defaults_no_formal_docs_false(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(repo_dir, "20260420T140000Z")
            payload = self._load_index(repo_dir)
            self.assertIn("invocation_flags", payload)
            self.assertEqual(payload["invocation_flags"]["no_formal_docs"], False)

    def test_stub_records_no_formal_docs_true(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(
                repo_dir, "20260420T140000Z", no_formal_docs=True
            )
            payload = self._load_index(repo_dir)
            self.assertEqual(payload["invocation_flags"]["no_formal_docs"], True)

    def test_final_preserves_no_formal_docs_true(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            # Phase 1 entry writes the stub with the flag.
            run_playbook.write_live_index_stub(
                repo_dir, "20260420T140000Z", no_formal_docs=True
            )
            # Phase 6 re-render must keep the flag.
            run_playbook.write_live_index_final(
                repo_dir,
                "20260420T140000Z",
                gate_verdict="pass",
                no_formal_docs=True,
            )
            payload = self._load_index(repo_dir)
            self.assertEqual(payload["invocation_flags"]["no_formal_docs"], True)
            # Sanity: existing §11 keys survive unchanged.
            for required in (
                "run_timestamp_start",
                "run_timestamp_end",
                "qpb_version",
                "phases_executed",
                "summary",
                "artifacts",
            ):
                self.assertIn(required, payload)

    def test_final_default_keeps_no_formal_docs_false(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(repo_dir, "20260420T140000Z")
            run_playbook.write_live_index_final(
                repo_dir, "20260420T140000Z", gate_verdict="partial"
            )
            payload = self._load_index(repo_dir)
            self.assertEqual(payload["invocation_flags"]["no_formal_docs"], False)


class ConfigureLoggingTests(unittest.TestCase):
    """v1.5.1 Item 2.1: configure_logging() is the single call site that
    produces the canonical log path, announces it, and installs line-
    buffered stdout. Tests use an explicit `stream=` kwarg so stdout
    capture is deterministic without monkey-patching sys.stdout."""

    def _restore_default_echo(self, original: bool) -> None:
        run_playbook.lib.set_default_echo(original)

    def test_returns_same_path_as_log_file_for(self) -> None:
        import io as _io
        original = run_playbook.lib.get_default_echo()
        try:
            with TemporaryDirectory() as temp_dir:
                repo = Path(temp_dir) / "subject"
                repo.mkdir()
                buf = _io.StringIO()
                path = run_playbook.configure_logging(
                    repo, "20260420T140000Z", stream=buf
                )
                expected = run_playbook.log_file_for(repo, "20260420T140000Z").resolve()
                self.assertEqual(path, expected)
                self.assertTrue(path.parent.is_dir())
        finally:
            self._restore_default_echo(original)

    def test_prints_stable_prefix_line(self) -> None:
        import io as _io
        original = run_playbook.lib.get_default_echo()
        try:
            with TemporaryDirectory() as temp_dir:
                repo = Path(temp_dir) / "subject"
                repo.mkdir()
                buf = _io.StringIO()
                run_playbook.configure_logging(
                    repo, "20260420T140000Z", stream=buf
                )
                output = buf.getvalue()
                self.assertTrue(output.startswith(run_playbook._CONFIGURE_LOGGING_PREFIX))
                # Path printed is absolute so operators can copy-paste it.
                path_text = output[len(run_playbook._CONFIGURE_LOGGING_PREFIX):].strip()
                self.assertTrue(Path(path_text).is_absolute())
        finally:
            self._restore_default_echo(original)

    def test_no_stdout_echo_flips_logboth_default(self) -> None:
        import io as _io
        original = run_playbook.lib.get_default_echo()
        try:
            with TemporaryDirectory() as temp_dir:
                repo = Path(temp_dir) / "subject"
                repo.mkdir()
                buf = _io.StringIO()
                run_playbook.configure_logging(
                    repo, "20260420T140000Z",
                    no_stdout_echo=True, stream=buf,
                )
                self.assertFalse(run_playbook.lib.get_default_echo())

                # logboth with default echo must now suppress stdout.
                from contextlib import redirect_stdout
                log_file = run_playbook.log_file_for(repo, "20260420T140000Z")
                captured = _io.StringIO()
                with redirect_stdout(captured):
                    run_playbook.lib.logboth(log_file, "silent in sandbox")
                self.assertEqual(captured.getvalue(), "")
                # Log file still written in full.
                self.assertIn(
                    "silent in sandbox",
                    log_file.read_text(encoding="utf-8"),
                )
        finally:
            self._restore_default_echo(original)

    def test_default_no_stdout_echo_keeps_echo_on(self) -> None:
        import io as _io
        original = run_playbook.lib.get_default_echo()
        try:
            with TemporaryDirectory() as temp_dir:
                repo = Path(temp_dir) / "subject"
                repo.mkdir()
                buf = _io.StringIO()
                run_playbook.configure_logging(
                    repo, "20260420T140000Z", stream=buf
                )
                self.assertTrue(run_playbook.lib.get_default_echo())
        finally:
            self._restore_default_echo(original)


class NoStdoutEchoFlagTests(unittest.TestCase):
    """v1.5.1 Item 2.1: --no-stdout-echo parses, propagates to workers,
    and persists in invocation_flags."""

    def test_parse_args_accepts_no_stdout_echo(self) -> None:
        args = run_playbook.parse_args(["--no-stdout-echo", "./somedir"])
        self.assertTrue(args.no_stdout_echo)
        default_args = run_playbook.parse_args(["./somedir"])
        self.assertFalse(default_args.no_stdout_echo)

    def test_build_worker_command_propagates_no_stdout_echo(self) -> None:
        args = run_playbook.argparse.Namespace(
            parallel=False,
            runner="claude",
            no_seeds=False,
            phase=None,
            next_iteration=False,
            full_run=False,
            strategy=["gap"],
            model=None,
            no_formal_docs=False,
            no_stdout_echo=True,
            kill=False,
            targets=["./project-a"],
            worker=False,
        )
        command = run_playbook.build_worker_command(args, "/abs/target")
        self.assertIn("--no-stdout-echo", command)

    def test_invocation_flags_include_no_stdout_echo(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(
                repo_dir, "20260420T140000Z", no_stdout_echo=True
            )
            # Read back the payload from INDEX.md.
            text = (repo_dir / "quality" / "INDEX.md").read_text(encoding="utf-8")
            import json as _json
            start = text.index("```json") + len("```json")
            end = text.index("```", start)
            payload = _json.loads(text[start:end])
            self.assertTrue(payload["invocation_flags"]["no_stdout_echo"])

    def test_invocation_flags_default_no_stdout_echo_false(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(repo_dir, "20260420T140000Z")
            text = (repo_dir / "quality" / "INDEX.md").read_text(encoding="utf-8")
            import json as _json
            start = text.index("```json") + len("```json")
            end = text.index("```", start)
            payload = _json.loads(text[start:end])
            self.assertFalse(payload["invocation_flags"]["no_stdout_echo"])


class VerboseQuietProgressFlagTests(unittest.TestCase):
    """v1.5.1 Item 2.2 CLI flags: --verbose, --quiet (mutex),
    --progress-interval (1..60)."""

    def test_default_flag_values(self) -> None:
        args = run_playbook.parse_args(["./somedir"])
        self.assertFalse(args.verbose)
        self.assertFalse(args.quiet)
        self.assertEqual(args.progress_interval, 2)

    def test_verbose_sets_flag(self) -> None:
        args = run_playbook.parse_args(["--verbose", "./somedir"])
        self.assertTrue(args.verbose)
        self.assertFalse(args.quiet)

    def test_quiet_sets_flag(self) -> None:
        args = run_playbook.parse_args(["--quiet", "./somedir"])
        self.assertTrue(args.quiet)
        self.assertFalse(args.verbose)

    def test_verbose_and_quiet_are_mutually_exclusive(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--verbose", "--quiet", "./somedir"])

    def test_progress_interval_accepts_in_range(self) -> None:
        for value in ("1", "2", "30", "60"):
            args = run_playbook.parse_args(["--progress-interval", value, "./somedir"])
            self.assertEqual(args.progress_interval, int(value))

    def test_progress_interval_rejects_below_range(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--progress-interval", "0", "./somedir"])

    def test_progress_interval_rejects_above_range(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--progress-interval", "61", "./somedir"])

    def test_progress_interval_rejects_non_integer(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--progress-interval", "fast", "./somedir"])

    def test_build_worker_command_propagates_verbose(self) -> None:
        args = run_playbook.argparse.Namespace(
            parallel=False, runner="claude", no_seeds=False, phase=None,
            next_iteration=False, full_run=False, strategy=["gap"],
            model=None, no_formal_docs=False, no_stdout_echo=False,
            verbose=True, quiet=False, progress_interval=2,
            kill=False, targets=["./project-a"], worker=False,
        )
        command = run_playbook.build_worker_command(args, "/abs/target")
        self.assertIn("--verbose", command)
        self.assertNotIn("--quiet", command)
        # Default interval should NOT be propagated (keep the worker
        # invocation terse).
        self.assertNotIn("--progress-interval", command)

    def test_build_worker_command_propagates_quiet_and_custom_interval(self) -> None:
        args = run_playbook.argparse.Namespace(
            parallel=False, runner="claude", no_seeds=False, phase=None,
            next_iteration=False, full_run=False, strategy=["gap"],
            model=None, no_formal_docs=False, no_stdout_echo=False,
            verbose=False, quiet=True, progress_interval=5,
            kill=False, targets=["./project-a"], worker=False,
        )
        command = run_playbook.build_worker_command(args, "/abs/target")
        self.assertIn("--quiet", command)
        self.assertIn("--progress-interval", command)
        self.assertIn("5", command)

    def test_invocation_flags_persist_verbose_quiet_progress_interval(self) -> None:
        import json as _json
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(
                repo_dir, "20260420T140000Z",
                verbose=True, quiet=False, progress_interval=7,
            )
            text = (repo_dir / "quality" / "INDEX.md").read_text(encoding="utf-8")
            start = text.index("```json") + len("```json")
            end = text.index("```", start)
            payload = _json.loads(text[start:end])
            flags = payload["invocation_flags"]
            self.assertTrue(flags["verbose"])
            self.assertFalse(flags["quiet"])
            self.assertEqual(flags["progress_interval"], 7)

    def test_invocation_flags_defaults_for_phase_2(self) -> None:
        import json as _json
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(repo_dir, "20260420T140000Z")
            text = (repo_dir / "quality" / "INDEX.md").read_text(encoding="utf-8")
            start = text.index("```json") + len("```json")
            end = text.index("```", start)
            payload = _json.loads(text[start:end])
            flags = payload["invocation_flags"]
            self.assertFalse(flags["verbose"])
            self.assertFalse(flags["quiet"])
            self.assertEqual(flags["progress_interval"], 2)


class StartupBannerTests(unittest.TestCase):
    """v1.5.1 Item 2.3: cross-platform startup banner emits platform-
    appropriate watch-from-another-terminal recipes with absolute
    paths so operators can copy-paste without worrying about cwd."""

    def _phase_one_args(self) -> "run_playbook.argparse.Namespace":
        """Args namespace shaped like parse_args output for a --phase 1 run.
        v1.5.1 Item 3.1: phase_groups is the canonical phase-selection
        representation; the banner's _run_plan_entries keys off it."""
        return run_playbook.argparse.Namespace(
            phase="1", phase_groups=[["1"]],
            full_run=False, next_iteration=False, strategy=["gap"],
            iterations=None, pace_seconds=0,
        )

    def test_darwin_banner_uses_tail_f_and_portable_progress_loop(self) -> None:
        """v1.5.1 Phase 2.3 revision — macOS does not ship `watch(1)`, so
        the Darwin recipe must use a shell loop that runs on a stock
        install without brew."""
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            log = repo.parent / f"{repo.name}-playbook-ts.log"
            banner = run_playbook.build_startup_banner(
                repo, log, ["Phase 1 (Explore)"], platform_name="Darwin",
            )
            self.assertIn("tail -f", banner)
            # Portable shell loop, not `watch -n 2`.
            self.assertIn("while true; do clear;", banner)
            self.assertIn("grep -E '^##?'", banner)
            self.assertNotIn("watch -n 2", banner)
            self.assertNotIn("Get-Content", banner)
            self.assertNotIn("Non-Darwin/Linux/Windows", banner)

    def test_linux_banner_uses_tail_f_and_watch_grep(self) -> None:
        """Linux ships `watch(1)` — keep the concise form."""
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            log = repo.parent / f"{repo.name}-playbook-ts.log"
            banner = run_playbook.build_startup_banner(
                repo, log, ["Phase 1 (Explore)"], platform_name="Linux",
            )
            self.assertIn("tail -f", banner)
            self.assertIn("watch -n 2", banner)
            # The Darwin loop form must NOT leak into the Linux branch.
            self.assertNotIn("while true; do clear;", banner)
            self.assertNotIn("Get-Content", banner)

    def test_windows_banner_uses_get_content_and_select_string(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            log = repo.parent / f"{repo.name}-playbook-ts.log"
            banner = run_playbook.build_startup_banner(
                repo, log, ["Phase 1 (Explore)"], platform_name="Windows",
            )
            self.assertIn("Get-Content", banner)
            self.assertIn("-Wait", banner)
            self.assertIn("Select-String", banner)
            self.assertNotIn("tail -f", banner)

    def test_unknown_platform_falls_back_with_advisory_note(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            log = repo.parent / f"{repo.name}-playbook-ts.log"
            banner = run_playbook.build_startup_banner(
                repo, log, ["Phase 1 (Explore)"], platform_name="FreeBSD",
            )
            self.assertIn("tail -f", banner)
            self.assertIn("Non-Darwin/Linux/Windows", banner)
            self.assertIn("FreeBSD", banner)

    def test_banner_paths_are_absolute(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            log = repo.parent / f"{repo.name}-playbook-ts.log"
            banner = run_playbook.build_startup_banner(
                repo, log, ["Phase 1 (Explore)"], platform_name="Darwin",
            )
            expected_log = str(log.resolve())
            expected_progress = str(repo / "quality" / "PROGRESS.md")
            expected_transcript = str(
                repo / "quality" / "control_prompts" / "phase1.output.txt"
            )
            self.assertIn(expected_log, banner)
            self.assertIn(expected_progress, banner)
            self.assertIn(expected_transcript, banner)

    def test_banner_includes_run_plan_entries(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            log = repo.parent / f"{repo.name}-playbook-ts.log"
            banner = run_playbook.build_startup_banner(
                repo, log,
                ["Phase 3 (Code Review)", "Phase 4 (Spec Audit)"],
                platform_name="Linux",
            )
            self.assertIn("Plan:", banner)
            self.assertIn("Phase 3 (Code Review)", banner)
            self.assertIn("Phase 4 (Spec Audit)", banner)

    def test_run_plan_entries_from_phase_flag(self) -> None:
        """v1.5.1 Item 3.1 refactor: --phase N,M expands to phase groups so
        the plan renders per-group lines rather than per-phase labels."""
        args = run_playbook.parse_args(["--phase", "3,4", "./target"])
        plan = run_playbook._run_plan_entries(args)
        self.assertEqual(
            plan,
            ["Phase group 1      (phase 3)", "Phase group 2      (phase 4)"],
        )

    def test_run_plan_entries_from_full_run(self) -> None:
        """v1.5.1 Item 3.1 refactor: --full-run expands to all six phase
        groups plus the four iteration strategies."""
        args = run_playbook.parse_args(["--full-run", "./target"])
        plan = run_playbook._run_plan_entries(args)
        self.assertIn("Phase group 1      (phase 1)", plan)
        self.assertIn("Phase group 6      (phase 6)", plan)

    def test_print_startup_banner_writes_to_log_and_stdout(self) -> None:
        import io as _io
        from contextlib import redirect_stdout

        original = run_playbook.lib.get_default_echo()
        run_playbook.lib.set_default_echo(True)
        try:
            with TemporaryDirectory() as temp_dir:
                repo = Path(temp_dir).resolve()
                log_path = repo.parent / f"{repo.name}-playbook-ts.log"
                args = self._phase_one_args()
                buf = _io.StringIO()
                with redirect_stdout(buf):
                    run_playbook.print_startup_banner(
                        repo, log_path, args, platform_name="Linux",
                    )
                stdout_text = buf.getvalue()
                log_text = log_path.read_text(encoding="utf-8")
                # Both streams see the banner.
                self.assertIn("QPB v", stdout_text)
                self.assertIn("QPB v", log_text)
                # Post-Item-3.1 plan format: one line per phase group.
                self.assertIn("Phase group 1      (phase 1)", stdout_text)
                self.assertIn("tail -f", stdout_text)
        finally:
            run_playbook.lib.set_default_echo(original)


class PhaseGroupsParserTests(unittest.TestCase):
    """v1.5.1 Item 3.1: --phase-groups syntax validation."""

    def test_single_phase_group(self) -> None:
        self.assertEqual(run_playbook._parse_phase_groups("1"), [["1"]])
        self.assertEqual(run_playbook._parse_phase_groups("5"), [["5"]])

    def test_multi_group_singletons(self) -> None:
        self.assertEqual(
            run_playbook._parse_phase_groups("1,2,3,4,5,6"),
            [["1"], ["2"], ["3"], ["4"], ["5"], ["6"]],
        )

    def test_multi_group_with_concatenation(self) -> None:
        self.assertEqual(
            run_playbook._parse_phase_groups("1,2,3+4,5+6"),
            [["1"], ["2"], ["3", "4"], ["5", "6"]],
        )

    def test_full_concatenation(self) -> None:
        self.assertEqual(
            run_playbook._parse_phase_groups("1+2+3+4+5+6"),
            [["1", "2", "3", "4", "5", "6"]],
        )

    def test_within_group_unsorted_accepted_and_normalized(self) -> None:
        """Within-group phase IDs may be unsorted; parser sorts them."""
        self.assertEqual(run_playbook._parse_phase_groups("4+3"), [["3", "4"]])
        self.assertEqual(
            run_playbook._parse_phase_groups("6+4+5"), [["4", "5", "6"]]
        )

    def test_rejects_out_of_range(self) -> None:
        for bad in ("0", "7", "8", "-1", "99"):
            with self.assertRaises(argparse.ArgumentTypeError):
                run_playbook._parse_phase_groups(bad)

    def test_rejects_non_integer_tokens(self) -> None:
        for bad in ("a", "1,b", "x+1", "3+y"):
            with self.assertRaises(argparse.ArgumentTypeError):
                run_playbook._parse_phase_groups(bad)

    def test_rejects_cross_group_descending(self) -> None:
        for bad in ("3,2", "3+4,1", "5,2+3", "4+5,3+6"):
            with self.assertRaises(argparse.ArgumentTypeError):
                run_playbook._parse_phase_groups(bad)

    def test_rejects_duplicates(self) -> None:
        for bad in ("1,1", "1+2,2+3", "3+3", "2,4+2"):
            with self.assertRaises(argparse.ArgumentTypeError):
                run_playbook._parse_phase_groups(bad)

    def test_rejects_empty_groups(self) -> None:
        for bad in ("1,,2", "1+", ",1", ",", "1++2"):
            with self.assertRaises(argparse.ArgumentTypeError):
                run_playbook._parse_phase_groups(bad)

    def test_rejects_empty_spec(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            run_playbook._parse_phase_groups("")
        with self.assertRaises(argparse.ArgumentTypeError):
            run_playbook._parse_phase_groups("   ")


class PhaseGroupsArgparseIntegrationTests(unittest.TestCase):
    """v1.5.1 Item 3.1: sugar expansion and cross-flag mutex via parse_args."""

    def test_phase_all_expands_to_six_single_phase_groups(self) -> None:
        args = run_playbook.parse_args(["--phase", "all", "./r"])
        self.assertEqual(
            args.phase_groups,
            [["1"], ["2"], ["3"], ["4"], ["5"], ["6"]],
        )

    def test_phase_single_expands_to_one_group(self) -> None:
        args = run_playbook.parse_args(["--phase", "3", "./r"])
        self.assertEqual(args.phase_groups, [["3"]])

    def test_phase_groups_explicit(self) -> None:
        args = run_playbook.parse_args(["--phase-groups", "1,3+4,6", "./r"])
        self.assertEqual(args.phase_groups, [["1"], ["3", "4"], ["6"]])

    def test_full_run_expands_to_all_six_phases(self) -> None:
        args = run_playbook.parse_args(["--full-run", "./r"])
        self.assertEqual(
            args.phase_groups,
            [["1"], ["2"], ["3"], ["4"], ["5"], ["6"]],
        )
        self.assertTrue(args.full_run)

    def test_no_phase_flags_means_full_run_groups(self) -> None:
        """v1.5.4 Phase 3.6.6 (B-18a): bare invocation now triggers
        --full-run, which expands to one group per phase. The v1.5.3
        contract (no flags → no groups → operator must specify) is
        replaced; canonical bare invocation runs all 6 phases + all
        4 strategies."""
        args = run_playbook.parse_args(["./r"])
        self.assertEqual(
            args.phase_groups,
            [["1"], ["2"], ["3"], ["4"], ["5"], ["6"]],
        )

    def test_phase_groups_vs_phase_mutex(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(
                ["--phase-groups", "1,2", "--phase", "3", "./r"]
            )

    def test_phase_groups_vs_full_run_mutex(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(
                ["--phase-groups", "1,2", "--full-run", "./r"]
            )

    def test_phase_groups_with_next_iteration_allowed(self) -> None:
        """Item 3.2 depends on this: --phase-groups + --next-iteration
        is the unified-invocation entry point."""
        args = run_playbook.parse_args(
            ["--phase-groups", "1,2", "--next-iteration", "./r"]
        )
        self.assertEqual(args.phase_groups, [["1"], ["2"]])
        self.assertTrue(args.next_iteration)

    def test_phase_groups_persisted_in_invocation_flags(self) -> None:
        import json as _json
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(
                repo_dir, "20260420T180000Z",
                phase_groups="1,3+4,6",
            )
            text = (repo_dir / "quality" / "INDEX.md").read_text(encoding="utf-8")
            start = text.index("```json") + len("```json")
            end = text.index("```", start)
            payload = _json.loads(text[start:end])
            flags = payload["invocation_flags"]
            self.assertEqual(flags["phase_groups"], "1,3+4,6")
            self.assertFalse(flags["full_run"])

    def test_full_run_flag_persisted(self) -> None:
        import json as _json
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(
                repo_dir, "20260420T180000Z",
                full_run=True, phase_groups="1,2,3,4,5,6",
            )
            text = (repo_dir / "quality" / "INDEX.md").read_text(encoding="utf-8")
            start = text.index("```json") + len("```json")
            end = text.index("```", start)
            payload = _json.loads(text[start:end])
            self.assertTrue(payload["invocation_flags"]["full_run"])
            self.assertEqual(payload["invocation_flags"]["phase_groups"], "1,2,3,4,5,6")


class PhaseGroupsPromptConcatenationTests(unittest.TestCase):
    """v1.5.1 Item 3.1: multi-phase group prompt construction."""

    def test_single_phase_group_prompt_equals_legacy_build(self) -> None:
        single = run_playbook._build_group_prompt(["3"], no_seeds=True)
        legacy = run_playbook.build_phase_prompt("3", no_seeds=True)
        self.assertEqual(single, legacy)

    def test_multi_phase_group_includes_headers_between_phases(self) -> None:
        combined = run_playbook._build_group_prompt(["3", "4"], no_seeds=True)
        # First phase body is unprefixed (no leading === Phase 3 ===).
        self.assertFalse(combined.startswith("=== Phase 3"))
        # Second phase opens with a visible header.
        self.assertIn("=== Phase 4 (Spec Audit) ===", combined)

    def test_multi_phase_group_concatenation_order(self) -> None:
        """The first phase's prompt appears before the second phase's
        prompt body; the delimiter sits between them."""
        p3 = run_playbook.build_phase_prompt("3", no_seeds=True)
        combined = run_playbook._build_group_prompt(["3", "4"], no_seeds=True)
        self.assertTrue(combined.startswith(p3))
        self.assertIn("=== Phase 4 (Spec Audit) ===", combined[len(p3):])


class IterationsParserTests(unittest.TestCase):
    """v1.5.1 Item 3.2: --iterations "strat,strat,..." parser."""

    def test_single_strategy(self) -> None:
        self.assertEqual(run_playbook._parse_iterations("gap"), ["gap"])
        self.assertEqual(run_playbook._parse_iterations("adversarial"), ["adversarial"])

    def test_multi_strategy_preserves_order(self) -> None:
        self.assertEqual(
            run_playbook._parse_iterations("gap,unfiltered"),
            ["gap", "unfiltered"],
        )
        # Explicit ordering that differs from canonical sequence.
        self.assertEqual(
            run_playbook._parse_iterations("adversarial,parity,gap"),
            ["adversarial", "parity", "gap"],
        )

    def test_rejects_unknown_strategy(self) -> None:
        for bad in ("foo", "gap,bar", "GAP"):
            with self.assertRaises(argparse.ArgumentTypeError):
                run_playbook._parse_iterations(bad)

    def test_rejects_duplicates(self) -> None:
        for bad in ("gap,gap", "gap,unfiltered,gap"):
            with self.assertRaises(argparse.ArgumentTypeError):
                run_playbook._parse_iterations(bad)

    def test_rejects_empty_list(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            run_playbook._parse_iterations("")
        with self.assertRaises(argparse.ArgumentTypeError):
            run_playbook._parse_iterations("   ")
        with self.assertRaises(argparse.ArgumentTypeError):
            run_playbook._parse_iterations(",")

    def test_full_run_expands_iterations(self) -> None:
        args = run_playbook.parse_args(["--full-run", "./r"])
        self.assertEqual(args.iterations, ["gap", "unfiltered", "parity", "adversarial"])


class PaceSecondsParserTests(unittest.TestCase):
    """v1.5.1 Item 3.2: --pace-seconds N parser (0..3600)."""

    def test_accepts_in_range(self) -> None:
        for v in ("0", "1", "60", "600", "3600"):
            args = run_playbook.parse_args(["--pace-seconds", v, "./r"])
            self.assertEqual(args.pace_seconds, int(v))

    def test_rejects_negative(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--pace-seconds", "-1", "./r"])

    def test_rejects_above_range(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--pace-seconds", "3601", "./r"])

    def test_rejects_non_integer(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(["--pace-seconds", "abc", "./r"])

    def test_default_is_zero(self) -> None:
        args = run_playbook.parse_args(["./r"])
        self.assertEqual(args.pace_seconds, 0)


class Phase3MutualExclusionTests(unittest.TestCase):
    """v1.5.1 Item 3.2: new mutex rules around --iterations."""

    def test_iterations_vs_full_run_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(
                ["--iterations", "gap", "--full-run", "./r"]
            )

    def test_iterations_vs_next_iteration_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            run_playbook.parse_args(
                ["--iterations", "gap", "--next-iteration", "./r"]
            )

    def test_iterations_with_phase_groups_allowed(self) -> None:
        """The main unified-invocation use case."""
        args = run_playbook.parse_args([
            "--phase-groups", "1,2", "--iterations", "gap,unfiltered", "./r",
        ])
        self.assertEqual(args.phase_groups, [["1"], ["2"]])
        self.assertEqual(args.iterations, ["gap", "unfiltered"])

    def test_iterations_alone_allowed(self) -> None:
        args = run_playbook.parse_args(["--iterations", "gap", "./r"])
        self.assertIsNone(args.phase_groups)
        self.assertEqual(args.iterations, ["gap"])

    def test_phase_groups_alone_allowed(self) -> None:
        args = run_playbook.parse_args(["--phase-groups", "1,2", "./r"])
        self.assertEqual(args.phase_groups, [["1"], ["2"]])
        self.assertIsNone(args.iterations)


class Phase3InvocationFlagsTests(unittest.TestCase):
    """v1.5.1 Item 3.2: iterations, pace_seconds, full_run persist in
    invocation_flags alongside the Phase 1/2 keys."""

    @staticmethod
    def _load_flags(repo_dir: Path) -> dict:
        import json as _json
        text = (repo_dir / "quality" / "INDEX.md").read_text(encoding="utf-8")
        start = text.index("```json") + len("```json")
        end = text.index("```", start)
        return _json.loads(text[start:end])["invocation_flags"]

    def test_iterations_and_pace_persisted(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(
                repo_dir, "20260420T180000Z",
                iterations="gap,unfiltered",
                pace_seconds=60,
            )
            flags = self._load_flags(repo_dir)
            self.assertEqual(flags["iterations"], "gap,unfiltered")
            self.assertEqual(flags["pace_seconds"], 60)

    def test_full_run_persists_all_four_phase3_flags(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(
                repo_dir, "20260420T180000Z",
                full_run=True,
                phase_groups="1,2,3,4,5,6",
                iterations="gap,unfiltered,parity,adversarial",
                pace_seconds=0,
            )
            flags = self._load_flags(repo_dir)
            self.assertTrue(flags["full_run"])
            self.assertEqual(flags["phase_groups"], "1,2,3,4,5,6")
            self.assertEqual(flags["iterations"], "gap,unfiltered,parity,adversarial")
            self.assertEqual(flags["pace_seconds"], 0)

    def test_defaults_when_no_phase3_flags(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(repo_dir, "20260420T180000Z")
            flags = self._load_flags(repo_dir)
            self.assertIsNone(flags["phase_groups"])
            self.assertIsNone(flags["iterations"])
            self.assertEqual(flags["pace_seconds"], 0)
            self.assertFalse(flags["full_run"])

    def test_all_nine_flags_present(self) -> None:
        """Sanity check: Phase 1 (1) + Phase 2 (4) + Phase 3 (4) = 9 keys."""
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            run_playbook.write_live_index_stub(repo_dir, "20260420T180000Z")
            flags = self._load_flags(repo_dir)
            expected = {
                "no_formal_docs", "no_stdout_echo", "verbose", "quiet",
                "progress_interval", "phase_groups", "iterations",
                "pace_seconds", "full_run",
            }
            self.assertEqual(set(flags.keys()), expected)


class RunPlanPrinterTests(unittest.TestCase):
    """v1.5.1 Item 3.2: _run_plan_entries emits iteration + pace lines
    when the invocation includes them."""

    def test_iterations_rendered_in_plan(self) -> None:
        args = run_playbook.parse_args([
            "--phase-groups", "1", "--iterations", "gap,unfiltered", "./r",
        ])
        plan = run_playbook._run_plan_entries(args)
        self.assertIn("Iteration:            gap", plan)
        self.assertIn("Iteration:            unfiltered", plan)

    def test_pace_line_shown_when_nonzero(self) -> None:
        args = run_playbook.parse_args([
            "--phase-groups", "1", "--pace-seconds", "30", "./r",
        ])
        plan = run_playbook._run_plan_entries(args)
        self.assertIn("Pace:                 30s between prompts", plan)

    def test_pace_line_omitted_when_zero(self) -> None:
        args = run_playbook.parse_args(["--phase-groups", "1", "./r"])
        plan = run_playbook._run_plan_entries(args)
        for entry in plan:
            self.assertFalse(entry.startswith("Pace:"))

    def test_full_plan_matches_brief_layout(self) -> None:
        args = run_playbook.parse_args([
            "--phase-groups", "1,2,3+4,5+6",
            "--iterations", "gap,unfiltered,parity,adversarial",
            "--pace-seconds", "60",
            "./r",
        ])
        plan = run_playbook._run_plan_entries(args)
        self.assertEqual(plan, [
            "Phase group 1      (phase 1)",
            "Phase group 2      (phase 2)",
            "Phase group 3      (phases 3, 4)",
            "Phase group 4      (phases 5, 6)",
            "Iteration:            gap",
            "Iteration:            unfiltered",
            "Iteration:            parity",
            "Iteration:            adversarial",
            "Pace:                 60s between prompts",
        ])


class UnifiedDispatcherPacingTests(unittest.TestCase):
    """v1.5.1 Item 3.2: _pace_between_prompts emits announcement, arms
    the monitor's pacing heartbeat, and calls the sleep fn once."""

    def test_zero_pace_is_noop(self) -> None:
        calls: list = []
        with TemporaryDirectory() as temp_dir:
            log = Path(temp_dir) / "log.txt"
            run_playbook._pace_between_prompts(
                0, log, monitor=None, sleep_fn=lambda s: calls.append(s),
            )
        self.assertEqual(calls, [])

    def test_positive_pace_calls_sleep(self) -> None:
        """v1.5.1 Phase 3 revision: _pace_between_prompts no longer
        emits its own "Pacing: Ns..." log line — the monitor's
        heartbeat is the single source of that output (covered by
        ProgressMonitorHeartbeatTests). This test now only asserts the
        sleep fn was called; the log-line assertion moved to the
        monitor tests."""
        calls: list = []
        with TemporaryDirectory() as temp_dir:
            log = Path(temp_dir) / "log.txt"
            run_playbook._pace_between_prompts(
                5, log, monitor=None, sleep_fn=lambda s: calls.append(s),
            )
            self.assertEqual(calls, [5])
            # Log file is not created when no logboth call happens.
            self.assertFalse(log.exists())

    def test_monitor_set_pacing_called_around_sleep(self) -> None:
        events: list = []

        class _Spy:
            def set_pacing(self, seconds: int) -> None:
                events.append(("set", seconds))

            def clear_pacing(self) -> None:
                events.append(("clear", None))

        with TemporaryDirectory() as temp_dir:
            log = Path(temp_dir) / "log.txt"
            run_playbook._pace_between_prompts(
                7, log, monitor=_Spy(),
                sleep_fn=lambda s: events.append(("sleep", s)),
            )
        # set_pacing before sleep, clear_pacing after — ordered.
        self.assertEqual(events, [("set", 7), ("sleep", 7), ("clear", None)])

    def test_clear_pacing_runs_even_if_sleep_raises(self) -> None:
        events: list = []

        class _Spy:
            def set_pacing(self, seconds: int) -> None:
                events.append(("set", seconds))

            def clear_pacing(self) -> None:
                events.append(("clear", None))

        def boom(_s):
            raise RuntimeError("sleep failed")

        with TemporaryDirectory() as temp_dir:
            log = Path(temp_dir) / "log.txt"
            with self.assertRaises(RuntimeError):
                run_playbook._pace_between_prompts(
                    5, log, monitor=_Spy(), sleep_fn=boom,
                )
        self.assertIn(("set", 5), events)
        self.assertIn(("clear", None), events)


class PhaseGroupsWorkerPropagationTests(unittest.TestCase):
    """v1.5.1 Item 3.1: the worker subprocess command must carry
    --phase-groups when the operator passed it explicitly."""

    def _args(self, **overrides):
        base = dict(
            parallel=False, runner="claude", no_seeds=True, phase=None,
            phase_groups_raw=None, phase_groups=None,
            next_iteration=False, full_run=False, strategy=["gap"],
            model=None, no_formal_docs=False, no_stdout_echo=False,
            verbose=False, quiet=False, progress_interval=2,
            iterations=None, pace_seconds=0,
            kill=False, targets=["./r"], worker=False,
        )
        base.update(overrides)
        return run_playbook.argparse.Namespace(**base)

    def test_explicit_phase_groups_propagated(self) -> None:
        raw = run_playbook._parse_phase_groups("1,3+4,6")
        args = self._args(phase_groups_raw=raw, phase_groups=raw)
        command = run_playbook.build_worker_command(args, "/abs/target")
        self.assertIn("--phase-groups", command)
        idx = command.index("--phase-groups")
        self.assertEqual(command[idx + 1], "1,3+4,6")
        self.assertNotIn("--phase", command)

    def test_phase_sugar_does_not_inject_phase_groups(self) -> None:
        """When the operator passed --phase N, the worker should keep
        receiving --phase N (not --phase-groups N) to preserve legacy
        worker test coverage."""
        args = self._args(phase="3")
        command = run_playbook.build_worker_command(args, "/abs/target")
        self.assertIn("--phase", command)
        self.assertNotIn("--phase-groups", command)

    def test_iterations_and_pace_propagated(self) -> None:
        raw = run_playbook._parse_phase_groups("1,2")
        args = self._args(
            phase_groups_raw=raw, phase_groups=raw,
            iterations=["gap", "unfiltered"],
            pace_seconds=60,
        )
        command = run_playbook.build_worker_command(args, "/abs/target")
        self.assertIn("--iterations", command)
        idx = command.index("--iterations")
        self.assertEqual(command[idx + 1], "gap,unfiltered")
        self.assertIn("--pace-seconds", command)
        idx = command.index("--pace-seconds")
        self.assertEqual(command[idx + 1], "60")

    def test_default_pace_zero_not_propagated(self) -> None:
        """Zero pace is the default; keep the worker invocation terse."""
        args = self._args(pace_seconds=0)
        command = run_playbook.build_worker_command(args, "/abs/target")
        self.assertNotIn("--pace-seconds", command)


class WorkerRoundtripTests(unittest.TestCase):
    """v1.5.1 Phase 3 revision (Council FAIL blocker): assert that argv
    produced by build_worker_command is accepted by a fresh parse_args.

    The Phase 3 kickoff split this into two test classes — one for what
    build_worker_command produces, one for what parse_args rejects on
    the worker side — but never composed them. That gap let a live bug
    land: parent --full-run expanded to args.iterations, worker argv
    carried both --full-run and --iterations, worker parse_args hit
    the Item 3.2 mutex and died. These tests close the gap.
    """

    @staticmethod
    def _worker_argv(args: "run_playbook.argparse.Namespace", target: str) -> list:
        """Return the portion of build_worker_command's output that
        worker parse_args actually sees: everything after the python
        invocation prefix.

        v1.5.4 Phase 3.8: prefix is now ``[sys.executable, '-m',
        'bin.run_playbook']`` (module-style), so the worker argv
        starts at index 3 — was index 2 in the script-style v1.5.3
        form."""
        command = run_playbook.build_worker_command(args, target)
        return command[3:]

    def _roundtrip(self, parent_argv: list) -> tuple:
        """Parse parent CLI, build worker cmd, parse that worker cmd
        through a fresh parse_args. Return (parent_args, worker_args,
        worker_command).

        v1.5.4 Phase 3.8: build_worker_command now uses module-style
        invocation (`python -m bin.run_playbook ...`) so the leading
        argv prefix is 3 elements (sys.executable, '-m',
        'bin.run_playbook') rather than the v1.5.3 2 elements
        (sys.executable, script_path). The worker_argv slice starts
        at index 3."""
        parent = run_playbook.parse_args(parent_argv)
        target_path = parent.targets[0]
        command = run_playbook.build_worker_command(parent, target_path)
        worker_argv = command[3:]  # drop python + -m + module name
        worker = run_playbook.parse_args(worker_argv)
        return parent, worker, command

    def test_full_run_roundtrips(self) -> None:
        """The regression test for the revision. Parent --full-run must
        produce a worker argv that the worker's own parse_args accepts."""
        parent, worker, command = self._roundtrip(["--full-run", "/tmp/repo"])
        self.assertTrue(parent.full_run)
        # The fix: --iterations must NOT appear in the worker argv
        # because the worker re-expands --full-run on its own side.
        self.assertIn("--full-run", command)
        self.assertNotIn("--iterations", command)
        # Canonical worker-side state matches parent after re-expansion.
        self.assertTrue(worker.full_run)
        self.assertEqual(
            worker.phase_groups,
            [["1"], ["2"], ["3"], ["4"], ["5"], ["6"]],
        )
        self.assertEqual(
            worker.iterations,
            ["gap", "unfiltered", "parity", "adversarial"],
        )

    def test_phase_all_roundtrips(self) -> None:
        parent, worker, command = self._roundtrip(["--phase", "all", "/tmp/repo"])
        self.assertIn("--phase", command)
        self.assertIn("all", command)
        self.assertNotIn("--phase-groups", command)
        self.assertEqual(
            worker.phase_groups,
            [["1"], ["2"], ["3"], ["4"], ["5"], ["6"]],
        )
        self.assertIsNone(worker.iterations)

    def test_phase_single_roundtrips(self) -> None:
        parent, worker, command = self._roundtrip(["--phase", "3", "/tmp/repo"])
        self.assertIn("--phase", command)
        self.assertIn("3", command)
        self.assertEqual(worker.phase_groups, [["3"]])

    def test_explicit_phase_groups_roundtrips(self) -> None:
        parent, worker, command = self._roundtrip(
            ["--phase-groups", "1,2,3+4", "/tmp/repo"]
        )
        self.assertIn("--phase-groups", command)
        idx = command.index("--phase-groups")
        self.assertEqual(command[idx + 1], "1,2,3+4")
        self.assertEqual(worker.phase_groups, [["1"], ["2"], ["3", "4"]])

    def test_explicit_iterations_roundtrips(self) -> None:
        parent, worker, command = self._roundtrip(
            ["--iterations", "gap,unfiltered", "/tmp/repo"]
        )
        self.assertIn("--iterations", command)
        idx = command.index("--iterations")
        self.assertEqual(command[idx + 1], "gap,unfiltered")
        self.assertEqual(worker.iterations, ["gap", "unfiltered"])
        self.assertIsNone(worker.phase_groups)

    def test_phase_groups_plus_iterations_roundtrips(self) -> None:
        parent, worker, command = self._roundtrip([
            "--phase-groups", "1,2",
            "--iterations", "gap,parity",
            "/tmp/repo",
        ])
        self.assertIn("--phase-groups", command)
        self.assertIn("--iterations", command)
        self.assertEqual(worker.phase_groups, [["1"], ["2"]])
        self.assertEqual(worker.iterations, ["gap", "parity"])

    def test_full_run_with_parallel_roundtrips(self) -> None:
        """Multi-target --parallel --full-run: each target's worker
        argv must roundtrip independently. Without the R1 fix this is
        the invocation that Council reproduced as broken."""
        parent = run_playbook.parse_args(
            ["--full-run", "--parallel", "/tmp/repo1", "/tmp/repo2"]
        )
        for target in parent.targets:
            command = run_playbook.build_worker_command(parent, target)
            # v1.5.4 Phase 3.8: prefix is python + -m + module name.
            worker_argv = command[3:]
            # The offending combination must not be present.
            self.assertIn("--full-run", command)
            self.assertNotIn("--iterations", command)
            worker = run_playbook.parse_args(worker_argv)
            self.assertTrue(worker.full_run)
            self.assertEqual(
                worker.phase_groups,
                [["1"], ["2"], ["3"], ["4"], ["5"], ["6"]],
            )
            self.assertEqual(
                worker.iterations,
                ["gap", "unfiltered", "parity", "adversarial"],
            )
            self.assertEqual(worker.targets, [target])


class IterationProgressHeartbeatTests(unittest.TestCase):
    """v1.5.1 Phase 2 revision: run_one_iterations must emit
    `## Iteration: <strategy> started` and `## Iteration: <strategy>
    complete` headers to quality/PROGRESS.md so the operator can tell
    a 15-minute iteration from a hung run."""

    def _args(self, **overrides):
        base = dict(
            parallel=False, runner="claude", no_seeds=True, phase=None,
            phase_groups_raw=None, phase_groups=None,
            next_iteration=False, full_run=False, strategy=["gap"],
            model=None, no_formal_docs=False, no_stdout_echo=False,
            verbose=False, quiet=False, progress_interval=2,
            iterations=None, pace_seconds=0,
            kill=False, targets=["./r"], worker=False,
        )
        base.update(overrides)
        return run_playbook.argparse.Namespace(**base)

    def test_iteration_writes_started_and_complete_sections(self) -> None:
        from unittest import mock

        with TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            (repo / "quality").mkdir()
            (repo / "quality" / "EXPLORATION.md").write_text("ok\n")

            def fake_run_prompt(repo_dir, prompt, pass_name, output_file,
                                log_file, runner, model):
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(f"[stub] {pass_name}\n")
                return 0

            args = self._args(iterations=["gap", "unfiltered"], pace_seconds=0)
            timestamp = "20260421-120000"

            with mock.patch.object(run_playbook, "run_prompt", fake_run_prompt), \
                 mock.patch.object(run_playbook.lib, "cleanup_repo", lambda d: None), \
                 mock.patch.object(run_playbook, "_finalize_iteration", return_value="pass"), \
                 mock.patch.object(run_playbook.lib, "count_bug_writeups",
                                   side_effect=[0, 1, 1, 1]):
                exit_code = run_playbook.run_one_iterations(
                    repo, ["gap", "unfiltered"], args, timestamp,
                    phases_already_ran=False,
                )

            # gap found 1 new bug (0 -> 1) so the loop continued.
            # unfiltered found 0 new bugs (1 -> 1) so it early-stopped.
            self.assertEqual(exit_code, 0)
            progress_text = (repo / "quality" / "PROGRESS.md").read_text(encoding="utf-8")
            self.assertIn("## Iteration: gap started", progress_text)
            self.assertIn("## Iteration: gap complete", progress_text)
            self.assertIn("## Iteration: unfiltered started", progress_text)
            self.assertIn("## Iteration: unfiltered complete", progress_text)
            # Completion line carries the bug-count breakdown.
            self.assertIn("net-new: 1", progress_text)
            self.assertIn("net-new: 0", progress_text)

    def test_iteration_progress_md_is_appended_not_overwritten(self) -> None:
        """Pre-existing PROGRESS.md content from the phase loop must
        survive the iteration heartbeat appends."""
        from unittest import mock

        with TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            (repo / "quality").mkdir()
            (repo / "quality" / "EXPLORATION.md").write_text("ok\n")
            seed = "# Run start\n\n## Phase 1 (Explore) complete\n"
            (repo / "quality" / "PROGRESS.md").write_text(seed, encoding="utf-8")

            def fake_run_prompt(*a, **kw):
                a[3].parent.mkdir(parents=True, exist_ok=True)
                a[3].write_text("ok\n")
                return 0

            args = self._args(iterations=["gap"])
            with mock.patch.object(run_playbook, "run_prompt", fake_run_prompt), \
                 mock.patch.object(run_playbook.lib, "cleanup_repo", lambda d: None), \
                 mock.patch.object(run_playbook, "_finalize_iteration", return_value="pass"), \
                 mock.patch.object(run_playbook.lib, "count_bug_writeups",
                                   side_effect=[0, 0]):
                run_playbook.run_one_iterations(
                    repo, ["gap"], args, "20260421-120000",
                    phases_already_ran=False,
                )

            text = (repo / "quality" / "PROGRESS.md").read_text(encoding="utf-8")
            # Seed survives.
            self.assertTrue(text.startswith(seed))
            # Heartbeat appended after.
            self.assertIn("## Iteration: gap started", text)
            self.assertIn("## Iteration: gap complete", text)


class SkillVersionStampTests(unittest.TestCase):
    """Pin the SKILL.md version stamp to the current release.

    `lib.detect_skill_version()` reads the repo's root SKILL.md and is the
    source the playbook uses to stamp every generated artifact. If a release
    bump misses an inline 1.5.x occurrence in SKILL.md, this test fails the
    release prep itself instead of letting the drift ship.
    """

    def test_skill_version_matches_release_constant(self) -> None:
        from bin import benchmark_lib as lib
        detected = lib.detect_skill_version()
        self.assertEqual(detected, lib.RELEASE_VERSION)

    def test_repo_skill_version_matches_release_constant(self) -> None:
        """The installed-copy reader must report the same version as the root.

        `detect_repo_skill_version()` walks `SKILL_INSTALL_LOCATIONS` and
        returns the first match. The root QPB checkout has SKILL.md at the
        repo root, so the function should find it via the `Path("SKILL.md")`
        fallback location. If the four install locations ever drift from
        each other (e.g., a packaging change adds a new SKILL.md without
        updating the version stamp), this test fails loudly during release
        prep instead of letting the drift ship.
        """
        from bin import benchmark_lib as lib
        detected = lib.detect_repo_skill_version(lib.QPB_DIR)
        self.assertEqual(detected, lib.RELEASE_VERSION)


class AgentsMdGenerationTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.5 (B-17): per-project AGENTS.md generated at
    end of Phase 6. Sentinel-on-first-lines protocol distinguishes
    QPB-managed from operator-authored copies."""

    def _seed_role_map(self, repo: Path) -> None:
        """Minimal valid role map so _generate_agents_md_content has
        a summary to render."""
        write_role_map(repo / "quality", files=[
            {"path": "src/main.py", "role": "code",
             "size_bytes": 100, "rationale": "fixture"},
        ])

    def _seed_index(
        self, repo: Path, *, gate_verdict: str = "pass",
        bug_count: int = 3, req_count: int = 7,
    ) -> None:
        write(
            repo / "quality" / "INDEX.md",
            '# Run Index\n\n```json\n'
            + json.dumps({
                "schema_version": "2.0",
                "summary": {
                    "requirements": {"1": req_count},
                    "bugs": {"HIGH": bug_count, "MEDIUM": 0, "LOW": 0},
                    "gate_verdict": gate_verdict,
                },
            })
            + "\n```\n",
        )

    def test_safe_write_creates_with_sentinel(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "AGENTS.md"
            outcome = run_playbook._safe_write_agents_md(target, "body")
            self.assertEqual(outcome, "wrote")
            text = target.read_text(encoding="utf-8")
            self.assertIn(run_playbook.QPB_AGENTS_SENTINEL, text)
            self.assertTrue(text.lstrip().startswith(run_playbook.QPB_AGENTS_SENTINEL))

    def test_safe_write_preserves_operator_authored(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "AGENTS.md"
            target.write_text("# Operator AGENTS.md\n\nDon't touch.\n")
            outcome = run_playbook._safe_write_agents_md(target, "regenerated")
            self.assertEqual(outcome, "preserved")
            self.assertEqual(
                target.read_text(),
                "# Operator AGENTS.md\n\nDon't touch.\n",
            )

    def test_safe_write_regenerates_qpb_managed(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "AGENTS.md"
            target.write_text(
                f"{run_playbook.QPB_AGENTS_SENTINEL}\n# QPB-managed\nold body\n"
            )
            outcome = run_playbook._safe_write_agents_md(target, "fresh body")
            self.assertEqual(outcome, "regenerated")
            self.assertIn("fresh body", target.read_text())
            # Sentinel still present.
            self.assertIn(
                run_playbook.QPB_AGENTS_SENTINEL,
                target.read_text(),
            )

    def test_generated_content_includes_required_sections(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_role_map(repo)
            self._seed_index(repo)
            content = run_playbook._generate_agents_md_content(repo)
            for required in (
                "## What this is",
                "## Read first",
                "## How to extend the review",
                "## Caveats and known issues",
                "REQUIREMENTS.md",
                "BUGS.md",
                "exploration_role_map.json",
                "workspace/",
                "previous_runs/",
            ):
                self.assertIn(required, content)
            # Counts pulled from INDEX.
            self.assertIn("**3**", content)  # bug count
            self.assertIn("**7**", content)  # req count

    def test_generated_content_pulls_exploration_narrative(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_role_map(repo)
            self._seed_index(repo)
            write(
                repo / "quality" / "EXPLORATION.md",
                "# Exploration\n\n## Architecture\n\n"
                "The repo is a CLI orchestrator with a single entry point at "
                "bin/run_playbook.py and an installable skill bundle under "
                ".github/skills/.\n\n## Other section\n\nbody\n",
            )
            content = run_playbook._generate_agents_md_content(repo)
            self.assertIn("Architecture / domain", content)
            self.assertIn("CLI orchestrator", content)

    def test_deferred_bugs_appear_in_caveats(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_role_map(repo)
            self._seed_index(repo)
            write(
                repo / "quality" / "BUGS.md",
                "# BUGS\n\n"
                "### BUG-001 - first deferred bug\n\n"
                "- Disposition: deferred\n\n"
                "### BUG-002 - shipped fix\n\n"
                "- Disposition: code-fix\n\n"
                "### BUG-003 - second deferred\n\n"
                "- Disposition: deferred\n",
            )
            content = run_playbook._generate_agents_md_content(repo)
            self.assertIn("BUG-001", content)
            self.assertIn("first deferred bug", content)
            self.assertIn("BUG-003", content)
            self.assertNotIn("BUG-002", content)

    def test_idempotent_regeneration(self) -> None:
        """Running the generator twice produces identical output the
        second time (modulo I/O timestamps the generator doesn't
        embed). v1.4.6 sentinel respect lives in the gate; the
        generator's contract is that a second invocation against a
        QPB-sentinel'd file regenerates cleanly."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_role_map(repo)
            self._seed_index(repo)
            target = repo / "AGENTS.md"
            content_1 = run_playbook._generate_agents_md_content(repo)
            run_playbook._safe_write_agents_md(target, content_1)
            text_after_first = target.read_text()
            content_2 = run_playbook._generate_agents_md_content(repo)
            run_playbook._safe_write_agents_md(target, content_2)
            self.assertEqual(text_after_first, target.read_text())


class FinalizeQualityLayoutTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.4 (B-16): _finalize_quality_layout moves
    intermediate pipeline artifacts under quality/workspace/ at end
    of Phase 6. Canonical deliverables stay at the top level so the
    operator-facing quality/ tree is human-readable."""

    def test_moves_workspace_dirs_to_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            q = repo / "quality"
            # Canonical (top-level after reorg).
            write(q / "REQUIREMENTS.md", "reqs")
            write(q / "BUGS.md", "bugs")
            # Intermediate (move to workspace/).
            write(q / "control_prompts" / "phase1.txt", "p1")
            write(q / "results" / "tdd-results.json", "{}")
            write(q / "code_reviews" / "review.md", "review")
            write(q / "phase3" / "pass_c_formal.jsonl", "{}")
            write(q / "EXPLORATION_ITER1.md", "iter1")
            write(q / "EXPLORATION_MERGED.md", "merged")

            run_playbook._finalize_quality_layout(repo)

            # Canonical preserved at top-level.
            self.assertTrue((q / "REQUIREMENTS.md").is_file())
            self.assertTrue((q / "BUGS.md").is_file())
            # Intermediates moved.
            self.assertFalse((q / "control_prompts").exists())
            self.assertFalse((q / "results").exists())
            self.assertFalse((q / "code_reviews").exists())
            self.assertFalse((q / "phase3").exists())
            self.assertTrue(
                (q / "workspace" / "control_prompts" / "phase1.txt").is_file()
            )
            self.assertTrue(
                (q / "workspace" / "results" / "tdd-results.json").is_file()
            )
            self.assertTrue(
                (q / "workspace" / "code_reviews" / "review.md").is_file()
            )
            self.assertTrue(
                (q / "workspace" / "phase3" / "pass_c_formal.jsonl").is_file()
            )
            # ITER + MERGED files moved.
            self.assertFalse((q / "EXPLORATION_ITER1.md").exists())
            self.assertFalse((q / "EXPLORATION_MERGED.md").exists())
            self.assertTrue((q / "workspace" / "EXPLORATION_ITER1.md").is_file())
            self.assertTrue((q / "workspace" / "EXPLORATION_MERGED.md").is_file())

    def test_idempotent_on_already_finalized_tree(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            q = repo / "quality"
            write(q / "BUGS.md", "bugs")
            write(q / "workspace" / "results" / "x.json", "{}")
            run_playbook._finalize_quality_layout(repo)
            # Pre-existing workspace child preserved unchanged.
            self.assertTrue((q / "workspace" / "results" / "x.json").is_file())
            # Top-level canonical preserved.
            self.assertTrue((q / "BUGS.md").is_file())

    def test_no_overwrite_when_workspace_child_already_exists(self) -> None:
        """If a re-run produces both top-level intermediates AND a
        pre-existing workspace child, preserve workspace and leave
        top-level alone (don't merge silently)."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            q = repo / "quality"
            write(q / "control_prompts" / "phase1.txt", "live")
            write(q / "workspace" / "control_prompts" / "phase1.txt", "old")
            run_playbook._finalize_quality_layout(repo)
            # Workspace preserved; top-level untouched (the rename
            # would have overwritten workspace, which we explicitly
            # avoid).
            self.assertEqual(
                (q / "workspace" / "control_prompts" / "phase1.txt").read_text(),
                "old",
            )
            self.assertEqual(
                (q / "control_prompts" / "phase1.txt").read_text(),
                "live",
            )

    def test_no_op_when_quality_dir_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            run_playbook._finalize_quality_layout(Path(tmp))


class GateResolveArtifactPathTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.4 (B-16, M5 fix): the gate's
    _resolve_artifact_path helper tries top-level first
    (legacy / pre-reorg), then quality/workspace/<name>
    (post-reorg). Imports the gate from its on-disk path since the
    gate ships outside the bin/ package tree."""

    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util
        repo_root = Path(__file__).resolve().parents[2]
        gate_path = (
            repo_root / ".github" / "skills" / "quality_gate" / "quality_gate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "qpb_gate_for_b16_test", gate_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.gate = module

    def test_top_level_wins_when_present(self) -> None:
        with TemporaryDirectory() as tmp:
            q = Path(tmp)
            (q / "results").mkdir()
            (q / "results" / "x.json").write_text("top", encoding="utf-8")
            (q / "workspace" / "results").mkdir(parents=True)
            (q / "workspace" / "results" / "x.json").write_text(
                "ws", encoding="utf-8"
            )
            resolved = self.gate._resolve_artifact_path(q, "results/x.json")
            self.assertEqual(resolved.read_text(), "top")

    def test_workspace_used_when_top_level_absent(self) -> None:
        with TemporaryDirectory() as tmp:
            q = Path(tmp)
            (q / "workspace" / "results").mkdir(parents=True)
            (q / "workspace" / "results" / "x.json").write_text("ws")
            resolved = self.gate._resolve_artifact_path(q, "results/x.json")
            self.assertEqual(resolved.read_text(), "ws")

    def test_returns_top_level_when_neither_exists(self) -> None:
        """Callers test .is_file()/.is_dir() — return top-level so
        downstream existence checks return False rather than raising."""
        with TemporaryDirectory() as tmp:
            q = Path(tmp)
            resolved = self.gate._resolve_artifact_path(q, "results/x.json")
            self.assertEqual(resolved, q / "results" / "x.json")
            self.assertFalse(resolved.exists())


class B18aBareInvocationDefaultsToFullRunTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.6 (B-18a): bare
    `python -m bin.run_playbook <target>` defaults to --full-run.
    Single-phase / iteration-only modes still available via
    --phases / --strategy / --iterations / --next-iteration."""

    def test_bare_invocation_sets_full_run(self) -> None:
        args = run_playbook.parse_args(["target"])
        self.assertTrue(args.full_run)
        # And the full-run sugar expansion populates phase_groups +
        # iterations to match --full-run's plan.
        self.assertIsNotNone(args.phase_groups)
        self.assertEqual(len(args.phase_groups), 6)  # all 6 phases
        self.assertEqual(args.iterations, list(run_playbook.ALL_STRATEGIES))

    def test_bare_invocation_matches_explicit_full_run(self) -> None:
        bare = run_playbook.parse_args(["target"])
        explicit = run_playbook.parse_args(["target", "--full-run"])
        self.assertEqual(bare.full_run, explicit.full_run)
        self.assertEqual(bare.phase_groups, explicit.phase_groups)
        self.assertEqual(bare.iterations, explicit.iterations)

    def test_explicit_phase_does_not_trigger_full_run(self) -> None:
        args = run_playbook.parse_args(["target", "--phase", "1"])
        self.assertFalse(args.full_run)

    def test_explicit_phase_groups_does_not_trigger_full_run(self) -> None:
        args = run_playbook.parse_args(
            ["target", "--phase-groups", "1,2,3"]
        )
        self.assertFalse(args.full_run)

    def test_next_iteration_does_not_trigger_full_run(self) -> None:
        args = run_playbook.parse_args(["target", "--next-iteration"])
        self.assertFalse(args.full_run)

    def test_explicit_iterations_does_not_trigger_full_run(self) -> None:
        args = run_playbook.parse_args(
            ["target", "--iterations", "gap,parity"]
        )
        self.assertFalse(args.full_run)


class PromptPrefixTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.3 (B-15): the cross-version harness wraps
    pre-v1.5.2 QPB cells with an explicit no-delegation guardrail
    via --prompt-prefix. The flag must apply to every prompt builder
    (per-phase, multi-phase group, single-pass, iteration) and must
    propagate through to subprocess workers."""

    def test_build_phase_prompt_no_prefix_unchanged(self) -> None:
        plain = run_playbook.build_phase_prompt("1", no_seeds=True)
        prefixed = run_playbook.build_phase_prompt(
            "1", no_seeds=True, prefix=""
        )
        self.assertEqual(plain, prefixed)

    def test_build_phase_prompt_with_prefix_prepends_with_blank_line(
        self,
    ) -> None:
        prefix = "PREFIX_GUARD_PROSE"
        body = run_playbook.build_phase_prompt(
            "1", no_seeds=True, prefix=prefix
        )
        self.assertTrue(body.startswith(f"{prefix}\n\n"))
        # And the original phase content still appears.
        self.assertIn("Execute Phase 1", body)

    def test_iteration_prompt_with_prefix(self) -> None:
        body = run_playbook.iteration_prompt("gap", prefix="ITER_PREFIX")
        self.assertTrue(body.startswith("ITER_PREFIX\n\n"))
        self.assertIn("gap strategy", body)

    def test_single_pass_prompt_with_prefix(self) -> None:
        body = run_playbook.single_pass_prompt(
            no_seeds=True, prefix="SP_PREFIX"
        )
        self.assertTrue(body.startswith("SP_PREFIX\n\n"))

    def test_argparse_prompt_prefix_default_is_empty(self) -> None:
        args = run_playbook.parse_args(["target"])
        self.assertEqual(getattr(args, "prompt_prefix", ""), "")

    def test_argparse_prompt_prefix_passes_through(self) -> None:
        args = run_playbook.parse_args(
            ["target", "--prompt-prefix", "no-delegation guard"]
        )
        self.assertEqual(args.prompt_prefix, "no-delegation guard")

    def test_build_worker_command_forwards_prompt_prefix(self) -> None:
        args = run_playbook.parse_args(
            ["target", "--prompt-prefix", "fwd-test"]
        )
        cmd = run_playbook.build_worker_command(args, "target")
        # --prompt-prefix appears immediately followed by the value.
        idx = cmd.index("--prompt-prefix")
        self.assertEqual(cmd[idx + 1], "fwd-test")


class CodexPreventionScriptInvocationGuardTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.1 Section A.2: refuse direct script-style
    invocation. The module relies on relative imports that fail under
    `python bin/run_playbook.py`; codex's 2026-04-29 self-audit
    attempt hit this and proceeded to patch QPB source. Now we
    refuse early with EX_USAGE (64)."""

    def test_script_style_invocation_exits_64(self) -> None:
        import subprocess
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "bin" / "run_playbook.py"
        result = subprocess.run(
            ["python3", str(script)],
            capture_output=True, text=True, cwd=str(repo_root),
        )
        self.assertEqual(
            result.returncode, 64,
            f"expected EX_USAGE (64), got {result.returncode}; "
            f"stderr={result.stderr!r}",
        )
        self.assertIn(
            "package module", result.stderr,
            f"stderr must explain the fix; got: {result.stderr!r}",
        )
        self.assertIn(
            "python -m bin.run_playbook", result.stderr,
            "stderr must show the correct invocation form",
        )


class CodexPreventionSentinelTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.1 Section A.3: sentinel-file preservation.
    `.gitignore !`-rule sentinels (.gitkeep files) keep otherwise-
    empty tracked directories present. Codex's 2026-04-29 self-audit
    attempt deleted `reference_docs/.gitkeep` and
    `reference_docs/cite/.gitkeep` despite the explicit `!`-rules."""

    def test_discover_sentinels_from_gitignore(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".gitignore").write_text(
                "# comment\n"
                "node_modules/\n"
                "*.log\n"
                "!reference_docs/.gitkeep\n"
                "!reference_docs/cite/.gitkeep\n"
                "!**/*-keep.md\n"  # globs are skipped
                "\n",
                encoding="utf-8",
            )
            sentinels = run_playbook._discover_sentinel_files(repo)
            posixes = {s.as_posix() for s in sentinels}
            self.assertIn("reference_docs/.gitkeep", posixes)
            self.assertIn("reference_docs/cite/.gitkeep", posixes)
            # Glob negation pattern is correctly skipped (no concrete path).
            self.assertEqual(len(sentinels), 2)

    def test_discover_sentinels_skips_directory_unignore_patterns(self) -> None:
        """v1.5.4 Phase 3.9.1 BUG 1 regression pin: surfaced during the
        2026-04-30 empirical bootstrap test. The QPB .gitignore carries
        BOTH `!reference_docs/cite/` (directory-level unignore — note
        the trailing slash) AND `!reference_docs/cite/.gitkeep`
        (file-level). Pre-fix, the parser picked up the directory
        pattern; _verify_sentinels then ran is_file() on the
        directory and reported it as a missing sentinel, aborting
        the run. Fix: trailing-slash patterns are directory unignores,
        not file sentinels — skip them. Only file-level `!`-rules
        appear in the output."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".gitignore").write_text(
                "node_modules/\n"
                "# Mirror of QPB's actual .gitignore shape:\n"
                "!reference_docs/cite/\n"           # directory unignore (skip)
                "!reference_docs/cite/.gitkeep\n"   # file unignore (keep)
                "!reference_docs/.gitkeep\n"        # file unignore (keep)
                "!some/other/dir/\n"                # another dir unignore (skip)
                "\n",
                encoding="utf-8",
            )
            sentinels = run_playbook._discover_sentinel_files(repo)
            posixes = {s.as_posix() for s in sentinels}
            # File-level unignores survive.
            self.assertIn("reference_docs/.gitkeep", posixes)
            self.assertIn("reference_docs/cite/.gitkeep", posixes)
            # Directory-level unignores (trailing slash) are skipped.
            self.assertNotIn("reference_docs/cite", posixes)
            self.assertNotIn("some/other/dir", posixes)
            # Belt-and-suspenders: no entry corresponds to an existing
            # tracked directory in the repo (which would falsely
            # appear missing under is_file()).
            self.assertEqual(len(sentinels), 2)

    def test_verify_sentinels_fails_when_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".gitignore").write_text(
                "!reference_docs/.gitkeep\n", encoding="utf-8"
            )
            # Don't create the sentinel.
            missing = run_playbook._verify_sentinels(repo)
            self.assertEqual(missing, ["reference_docs/.gitkeep"])

    def test_verify_sentinels_passes_when_all_present(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".gitignore").write_text(
                "!reference_docs/.gitkeep\n", encoding="utf-8"
            )
            (repo / "reference_docs").mkdir()
            (repo / "reference_docs" / ".gitkeep").write_text("")
            self.assertEqual(run_playbook._verify_sentinels(repo), [])

    def test_no_gitignore_yields_empty_sentinel_list(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                run_playbook._discover_sentinel_files(Path(tmp)), []
            )


class CodexPreventionSourceBackstopTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.1 Section A.4: structural backstop. If an LLM
    autonomously patches QPB source mid-run, the post-phase verifier
    detects the diff against the run-start baseline SHA and aborts.
    Codex's 2026-04-29 attempt patched bin/archive_lib.py; this is
    the regression pin."""

    def test_baseline_capture_returns_qpb_head_sha(self) -> None:
        # The QPB checkout is itself a git repo; the helper should
        # return the current HEAD SHA.
        qpb_dir = Path(__file__).resolve().parents[2]
        sha = run_playbook._qpb_source_baseline_sha(qpb_dir)
        self.assertIsNotNone(sha)
        # SHA-1 hex strings are 40 chars; allow Git's short-form just
        # in case (defensive).
        self.assertGreaterEqual(len(sha), 7)
        self.assertTrue(all(c in "0123456789abcdef" for c in sha))

    def test_baseline_returns_none_for_non_git(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertIsNone(
                run_playbook._qpb_source_baseline_sha(Path(tmp))
            )

    def test_verify_unchanged_returns_empty_on_clean_baseline(self) -> None:
        """When the working tree is clean (HEAD == working state),
        the diff against HEAD should be empty. Skipped on a dirty
        development checkout — that's the *expected* non-empty case
        the structural backstop is designed to catch."""
        import subprocess
        qpb_dir = Path(__file__).resolve().parents[2]
        # Detect dirty tree on the source paths; skip if dirty.
        dirty_check = subprocess.run(
            ["git", "status", "--porcelain", "--"]
            + list(run_playbook._QPB_SOURCE_PATHS),
            cwd=str(qpb_dir), capture_output=True, text=True, check=False,
        )
        if dirty_check.stdout.strip():
            self.skipTest(
                "working tree has pending changes on QPB source paths; "
                "the verifier correctly reports them as modified. The "
                "clean-baseline case is exercised in CI / by ops."
            )
        sha = run_playbook._qpb_source_baseline_sha(qpb_dir)
        modified = run_playbook._verify_qpb_source_unchanged(qpb_dir, sha)
        self.assertEqual(modified, [])

    def test_verify_unchanged_no_baseline_short_circuits(self) -> None:
        # When there's no baseline to compare against, the helper
        # returns [] (the structural backstop simply no-ops rather
        # than blocking development clones without git).
        qpb_dir = Path(__file__).resolve().parents[2]
        self.assertEqual(
            run_playbook._verify_qpb_source_unchanged(qpb_dir, None),
            [],
        )

    def test_verify_detects_committed_modification(self) -> None:
        """Construct a synthetic 'baseline' SHA that predates the
        latest commit touching bin/; the diff must include some
        bin/ file that changed since then. This proves the detector
        actually fires on non-empty diffs (the regression pin)."""
        import subprocess
        qpb_dir = Path(__file__).resolve().parents[2]
        # Find a SHA from before the most recent bin/ commit.
        result = subprocess.run(
            ["git", "log", "--format=%H", "-n", "20", "--", "bin/"],
            cwd=str(qpb_dir), capture_output=True, text=True, check=True,
        )
        commits = [c for c in result.stdout.splitlines() if c.strip()]
        if len(commits) < 2:
            self.skipTest(
                "need at least 2 historical bin/ commits for diff test"
            )
        # commits[0] is HEAD-most-recent for bin/; commits[1] is older.
        old_sha = commits[1]
        modified = run_playbook._verify_qpb_source_unchanged(
            qpb_dir, old_sha
        )
        self.assertGreater(
            len(modified), 0,
            f"diff against {old_sha[:7]} must surface at least one "
            f"bin/ change (or this test fixture needs updating)",
        )


class Round8Fix1HelpAndBannerTests(unittest.TestCase):
    """v1.5.4 Phase 3.7 Fix 1 (Round 8 BLOCK): B-18a discoverability.
    --help text documents the bare-invocation → full-run change;
    bare invocation emits a one-line stderr banner before the run
    starts; explicit --full-run does NOT emit the banner."""

    def test_help_text_documents_default_full_run(self) -> None:
        parser = run_playbook.build_parser()
        help_text = parser.format_help()
        self.assertIn("all 6 phases", help_text)
        self.assertIn("all 4 iteration", help_text)
        self.assertIn("--phase 1", help_text)
        # "Cost" warning so v1.5.3 muscle-memory operators see the
        # expense before they run.
        self.assertIn("5-10x", help_text)

    def test_bare_invocation_sets_auto_full_run_flag(self) -> None:
        args = run_playbook.parse_args(["target"])
        self.assertTrue(args._auto_full_run)
        self.assertTrue(args.full_run)

    def test_explicit_full_run_does_not_set_auto_flag(self) -> None:
        args = run_playbook.parse_args(["target", "--full-run"])
        self.assertFalse(args._auto_full_run)
        self.assertTrue(args.full_run)

    def test_explicit_phase_does_not_set_auto_flag(self) -> None:
        args = run_playbook.parse_args(["target", "--phase", "1"])
        self.assertFalse(args._auto_full_run)
        self.assertFalse(args.full_run)

    def test_bare_invocation_emits_banner_in_execute_run(self) -> None:
        """The banner fires from execute_run via stderr. Stub repo_dirs
        as empty so no actual phase work runs; the banner emission
        happens before the dispatch."""
        from contextlib import redirect_stderr
        from io import StringIO
        args = run_playbook.parse_args(["target"])
        buf = StringIO()
        with redirect_stderr(buf):
            try:
                run_playbook.execute_run(args, [], suppress_suggestion=True)
            except Exception:
                pass  # we only care about banner emission, not the dispatch result
        stderr = buf.getvalue()
        self.assertIn("[v1.5.4] Bare invocation", stderr)
        self.assertIn("--phase 1", stderr)

    def test_explicit_full_run_does_not_emit_banner(self) -> None:
        from contextlib import redirect_stderr
        from io import StringIO
        args = run_playbook.parse_args(["target", "--full-run"])
        buf = StringIO()
        with redirect_stderr(buf):
            try:
                run_playbook.execute_run(args, [], suppress_suggestion=True)
            except Exception:
                pass
        self.assertNotIn("Bare invocation", buf.getvalue())


class Round8Fix3SentinelPrefixMatchTests(unittest.TestCase):
    """v1.5.4 Phase 3.7 Fix 3 (Round 8 HIGH): AGENTS.md sentinel
    detection matches on the QPB_AGENTS_SENTINEL_PREFIX rather than
    the literal v1.5.4 string. v1.5.5+ correctly recognises
    v1.5.4-generated AGENTS.md as QPB-managed and regenerates them."""

    def test_sentinel_prefix_match_accepts_v1_5_4_format(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "AGENTS.md"
            target.write_text(
                "<!-- generated by QPB v1.5.4 -->\n# old body\n"
            )
            outcome = run_playbook._safe_write_agents_md(target, "new body")
            self.assertEqual(outcome, "regenerated")
            self.assertIn("new body", target.read_text())

    def test_sentinel_prefix_match_accepts_hypothetical_v1_5_5_format(
        self,
    ) -> None:
        """The regression pin: a v1.5.5 sentinel must be recognised
        by v1.5.4 detection (and vice-versa). Without prefix match,
        each version would refuse to regenerate the other's files."""
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "AGENTS.md"
            target.write_text(
                "<!-- generated by QPB v1.5.5 -->\n# v1.5.5 body\n"
            )
            outcome = run_playbook._safe_write_agents_md(
                target, "v1.5.4 regenerated body"
            )
            self.assertEqual(outcome, "regenerated")
            self.assertIn("v1.5.4 regenerated body", target.read_text())

    def test_sentinel_prefix_match_rejects_operator_authored(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "AGENTS.md"
            target.write_text("# Operator AGENTS.md\n\nNo QPB sentinel.\n")
            outcome = run_playbook._safe_write_agents_md(
                target, "this should not be written"
            )
            self.assertEqual(outcome, "preserved")
            self.assertNotIn(
                "this should not be written", target.read_text()
            )

    def test_full_sentinel_carries_literal_version(self) -> None:
        """Inspecting a generated AGENTS.md should reveal which QPB
        version produced it. The prefix-match is for detection; the
        full sentinel still embeds the version literally."""
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "AGENTS.md"
            run_playbook._safe_write_agents_md(target, "body")
            text = target.read_text()
            self.assertIn(run_playbook.QPB_AGENTS_SENTINEL, text)
            # Sentinel constant has the version literal.
            self.assertIn("v1.5.4", run_playbook.QPB_AGENTS_SENTINEL)


class Round8Fix4AgentsMdFlagNamesTests(unittest.TestCase):
    """v1.5.4 Phase 3.7 Fix 4 (Round 8 HIGH): the AGENTS.md generator's
    'How to extend the review' suggestions must use real argparse
    flag names. Pre-fix used --target . / --phases <N>; both wrong
    (positional target / --phase singular)."""

    def _seed_role_map(self, repo: Path) -> None:
        write_role_map(repo / "quality", files=[
            {"path": "src/main.py", "role": "code",
             "size_bytes": 100, "rationale": "fixture"},
        ])

    def test_generated_template_uses_positional_target(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_role_map(repo)
            content = run_playbook._generate_agents_md_content(repo)
            # New template form (positional, no --target prefix).
            self.assertIn(
                "python -m bin.run_playbook . --phase",
                content,
                "phase suggestion must use positional target + --phase singular",
            )
            # Old broken forms must not appear.
            self.assertNotIn("--target .", content)
            self.assertNotIn("--phases ", content)

    def test_generated_template_commands_parse(self) -> None:
        """The strongest pin: extract the suggested commands from the
        template and run each through argparse. They must parse
        without 'unrecognized arguments' errors."""
        import re
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_role_map(repo)
            content = run_playbook._generate_agents_md_content(repo)
            # Find each backtick-quoted python -m bin.run_playbook command.
            pattern = re.compile(
                r"`python(?:3)? -m bin\.run_playbook ([^`]+)`"
            )
            commands = pattern.findall(content)
            self.assertGreater(
                len(commands), 0,
                "template must contain at least one extension command",
            )
            for cmd in commands:
                # Substitute placeholder markers like <N> with concrete
                # values so argparse can parse.
                cmd_concrete = (
                    cmd.replace("<N>", "1")
                    .replace("<gap|unfiltered|parity|adversarial>", "gap")
                )
                argv = cmd_concrete.split()
                # parse_args raises SystemExit on bad flags; success
                # means the flag names are real.
                try:
                    run_playbook.parse_args(argv)
                except SystemExit as e:
                    self.fail(
                        f"AGENTS.md template command failed argparse: "
                        f"`python -m bin.run_playbook {cmd_concrete}` "
                        f"(argv={argv!r}, SystemExit={e.code})"
                    )


class Round8Fix6SourcePathsCoverageTests(unittest.TestCase):
    """v1.5.4 Phase 3.7 Fix 6 (Round 8 HIGH): _QPB_SOURCE_PATHS now
    covers schemas.md and AGENTS.md alongside the pre-existing
    bin/, .github/skills/, agents/, references/, SKILL.md."""

    def test_source_paths_includes_schemas_md(self) -> None:
        self.assertIn("schemas.md", run_playbook._QPB_SOURCE_PATHS)

    def test_source_paths_includes_agents_md(self) -> None:
        self.assertIn("AGENTS.md", run_playbook._QPB_SOURCE_PATHS)

    def test_source_paths_preserves_prior_coverage(self) -> None:
        """Negative control: the additions must not displace the
        pre-existing coverage."""
        for path in ("bin/", ".github/skills/", "agents/",
                     "references/", "SKILL.md"):
            self.assertIn(path, run_playbook._QPB_SOURCE_PATHS)

    def test_verifier_diffs_against_schemas_md_changes(self) -> None:
        """Pin that the actual diff machinery treats schemas.md as a
        watched path. Diff against a historical SHA that predates a
        schemas.md change; the modified-list must include it."""
        import subprocess
        qpb_dir = Path(__file__).resolve().parents[2]
        # Find a historical commit before the most recent schemas.md edit.
        result = subprocess.run(
            ["git", "log", "--format=%H", "-n", "20", "--", "schemas.md"],
            cwd=str(qpb_dir), capture_output=True, text=True, check=True,
        )
        commits = [c for c in result.stdout.splitlines() if c.strip()]
        if len(commits) < 2:
            self.skipTest(
                "need at least 2 historical schemas.md commits to verify "
                "the diff machinery sees the file"
            )
        # commits[1] is a SHA before commits[0]'s schemas.md change.
        modified = run_playbook._verify_qpb_source_unchanged(
            qpb_dir, commits[1]
        )
        self.assertIn(
            "schemas.md", modified,
            "_verify_qpb_source_unchanged must surface schemas.md "
            "modifications now that it's in _QPB_SOURCE_PATHS",
        )


class CouncilRound2P04PhasePromptsSourcePathTests(unittest.TestCase):
    """Council Round 2 2026-04-30 P0-4: phase_prompts/ is now
    load-bearing single-source-of-truth runtime prompt content
    (introduced by F-1 externalization). The source-unchanged
    invariant must watch it; otherwise a mid-run Phase-N LLM
    rewriting phase_prompts/phase3.md would not trip the gate.
    Same class of finding F-2 closed for AGENTS.md."""

    def test_source_paths_includes_phase_prompts(self) -> None:
        self.assertIn("phase_prompts/", run_playbook._QPB_SOURCE_PATHS)

    def test_verifier_diffs_against_phase_prompts_changes(self) -> None:
        """Pin that the actual diff machinery treats phase_prompts/
        as a watched path. The phase_prompts/ directory was first
        introduced in commit aee53c2 (F-1). Diffing from any pre-F-1
        baseline must surface phase_prompts/ entries — but ONLY if
        the path is in _QPB_SOURCE_PATHS (the diff is filtered by
        the path list).

        Mutation contract: removing 'phase_prompts/' from
        _QPB_SOURCE_PATHS makes this test fail because the diff
        filter no longer includes the directory and the modified
        list comes back empty for phase_prompts/ entries."""
        import subprocess
        qpb_dir = Path(__file__).resolve().parents[2]
        # Find a SHA from before phase_prompts/ was created. The
        # introducing commit is aee53c2; any earlier commit works.
        result = subprocess.run(
            ["git", "log", "--format=%H", "-n", "30", "HEAD"],
            cwd=str(qpb_dir), capture_output=True, text=True, check=True,
        )
        commits = [c for c in result.stdout.splitlines() if c.strip()]
        # Walk the history looking for a commit where phase_prompts/
        # didn't yet exist. The check `git ls-tree <sha> phase_prompts/`
        # returns empty when the directory wasn't tracked yet.
        pre_f1_sha = None
        for sha in commits:
            ls = subprocess.run(
                ["git", "ls-tree", sha, "phase_prompts/"],
                cwd=str(qpb_dir), capture_output=True, text=True, check=False,
            )
            if not ls.stdout.strip():
                pre_f1_sha = sha
                break
        if pre_f1_sha is None:
            self.skipTest(
                "no pre-F-1 commit available to diff against — git "
                "history may have been rewritten or shallow-cloned"
            )
        modified = run_playbook._verify_qpb_source_unchanged(
            qpb_dir, pre_f1_sha
        )
        phase_prompts_changes = [
            m for m in modified if m.startswith("phase_prompts/")
        ]
        self.assertGreater(
            len(phase_prompts_changes), 0,
            "_verify_qpb_source_unchanged must surface phase_prompts/ "
            "additions now that the directory is in _QPB_SOURCE_PATHS. "
            "If this assertion fails after a code change, the most "
            "likely cause is 'phase_prompts/' was removed from the "
            "tuple — restore it.",
        )

    def test_source_paths_preserves_prior_coverage_after_p04(self) -> None:
        """Negative control: P0-4's addition must not displace any
        prior coverage."""
        for path in ("bin/", ".github/skills/", "agents/", "references/",
                     "SKILL.md", "schemas.md", "AGENTS.md"):
            self.assertIn(path, run_playbook._QPB_SOURCE_PATHS)


class Phase38WorkerInvocationTests(unittest.TestCase):
    """v1.5.4 Phase 3.8: regression pin for ``build_worker_command``
    invoking the worker as ``python -m bin.run_playbook`` rather
    than ``python /full/path/run_playbook.py``.

    The Phase 3.6.1 A.2 invocation guard exits EX_USAGE=64 on
    script-style invocation. Workers spawned via the script-path
    form would die before any phase work runs. The regression was
    latent for 10 commits (Phase 3.6.1 → Phase 3.7) because no
    parallel-mode test exercised the spawn path. This test catches
    the next reversion immediately."""

    def _build(self, **overrides):
        # parse_args emits a Namespace with the full default flag
        # set, including the new --prompt-prefix etc. Use it rather
        # than hand-rolling so future flag additions don't break the
        # test.
        argv = overrides.pop("argv", ["target", "--phase", "1"])
        args = run_playbook.parse_args(argv)
        return run_playbook.build_worker_command(args, "target")

    def test_worker_invocation_uses_module_form(self) -> None:
        """The load-bearing pin: cmd[0:3] is
        [sys.executable, '-m', 'bin.run_playbook']. A future refactor
        that reverts to [sys.executable, str(Path(__file__).resolve()),
        ...] fails this test."""
        import sys as _sys
        cmd = self._build()
        self.assertEqual(cmd[0], _sys.executable)
        self.assertEqual(cmd[1], "-m")
        self.assertEqual(cmd[2], "bin.run_playbook")

    def test_worker_command_does_not_use_script_path(self) -> None:
        """Negative control: the worker command must NOT contain a
        path ending in ``run_playbook.py`` as a top-level argv
        element. The script-style form would have
        ``cmd[1] == "/full/path/.../bin/run_playbook.py"``; the
        module-style form has no such element."""
        cmd = self._build()
        for arg in cmd:
            self.assertFalse(
                arg.endswith("run_playbook.py")
                and ("/" in arg or "\\" in arg),
                f"worker command must not invoke script-style; "
                f"found path-like argv element: {arg!r}",
            )

    def test_worker_invocation_passes_a2_package_check(self) -> None:
        """End-to-end pin: spawn the worker form with `--help` and
        confirm the A.2 guard does NOT fire. ``--help`` short-circuits
        before any phase work runs but exercises the full
        ``__main__`` entry; if the guard fires, exit code is 64 and
        stderr names the package-module requirement. Module-style
        invocation must produce the standard argparse help output
        and exit 0."""
        import subprocess
        import sys as _sys
        result = subprocess.run(
            [_sys.executable, "-m", "bin.run_playbook", "--help"],
            cwd=str(Path(__file__).resolve().parents[2]),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            f"-m invocation should produce --help and exit 0; got "
            f"exit={result.returncode}, stderr={result.stderr[:300]!r}",
        )
        self.assertNotIn(
            "must be invoked as a package module",
            result.stderr + result.stdout,
        )


class FinalizerSourceEditGuardrailTests(unittest.TestCase):
    """v1.5.5 Council R2 P1.1: bin.run_state_lib.validate_no_source_edits
    must be wired into the production finalization path. Without this,
    item B's guardrail is advisory (only SKILL.md prose tells the AI
    to call it) instead of mechanical.

    Static-analysis test: read the source of _finalize_iteration and
    assert it imports + invokes validate_no_source_edits. A future
    refactor can move the call site (or rename the wrapper) but it
    must keep the call.

    Behavioral test: run _finalize_iteration against a tempdir that
    has both a clean quality/ tree and a dirty source file. Confirm
    the finalizer downgrades final_status to "aborted", appends the
    violation to the gate log, and surfaces it in PROGRESS.md.
    """

    def test_finalizer_imports_and_calls_validate_no_source_edits(self) -> None:
        import inspect

        source = inspect.getsource(run_playbook._finalize_iteration)
        self.assertIn(
            "validate_no_source_edits",
            source,
            "_finalize_iteration must call validate_no_source_edits "
            "(item B's source-edit guardrail must fire mechanically, "
            "not just advisorily via SKILL.md prose).",
        )
        self.assertIn(
            "from bin.run_state_lib import validate_no_source_edits",
            source,
            "_finalize_iteration must import validate_no_source_edits "
            "from bin.run_state_lib (the canonical location).",
        )

    def test_finalizer_aborts_when_source_edits_present(self) -> None:
        """End-to-end: stage a fake target repo with a dirty source
        file, invoke _finalize_iteration, confirm it returns 'aborted'
        and surfaces the violation in PROGRESS.md."""
        import subprocess as _subprocess

        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)

            def run_git(*args: str) -> None:
                _subprocess.run(
                    ["git", *args], cwd=str(tmp),
                    check=True, capture_output=True, text=True,
                )

            run_git("init", "-q")
            run_git("config", "user.email", "test@example.com")
            run_git("config", "user.name", "Test")
            run_git("config", "commit.gpgsign", "false")
            (tmp / "src").mkdir()
            (tmp / "src" / "code.py").write_text("print('orig')\n", encoding="utf-8")
            (tmp / "quality").mkdir()
            (tmp / "quality" / "BUGS.md").write_text("# Bugs\n", encoding="utf-8")
            run_git("add", ".")
            run_git("commit", "-q", "-m", "initial")

            # Mutate a source file outside quality/. The exact scenario
            # the guardrail catches.
            (tmp / "src" / "code.py").write_text(
                "print('phase 5 went off-rails')\n", encoding="utf-8"
            )

            log_file = tmp / "run.log"
            log_file.touch()

            status = run_playbook._finalize_iteration(
                tmp, label="post-test", log_file=log_file,
            )

            self.assertEqual(
                status, "aborted",
                "Finalizer must downgrade to 'aborted' when source "
                "edits are detected outside quality/.",
            )

            progress = (tmp / "quality" / "PROGRESS.md").read_text(encoding="utf-8")
            self.assertIn("Source-edit violations:", progress)
            self.assertIn("source_edit_violations", progress)
            self.assertIn("src/code.py", progress)

            gate_log = tmp / "quality" / "results" / "quality-gate.log"
            if gate_log.is_file():
                gate_text = gate_log.read_text(encoding="utf-8")
                self.assertIn("source-edit guardrail", gate_text)
                self.assertIn("src/code.py", gate_text)


class KillRecordedProcessesPkillSafetyTests(unittest.TestCase):
    """v1.5.6 fix-up 057 — BUG-004 (HIGH) workstation-wide pkill safety.

    The pre-fix `_pkill_fallback()` ran `pkill -f` against substrings like
    `claude -p` and `gh copilot -p`, killing every interactive Claude or
    Copilot session on the workstation when PID files were missing.
    Default behavior is now manual-intervention guidance; legacy pkill
    is preserved behind --allow-pkill-fallback for explicit opt-in.
    """

    def test_no_pid_files_default_does_not_invoke_pkill(self) -> None:
        with mock.patch.object(run_playbook, "discover_pid_files", return_value=[]), \
             mock.patch.object(run_playbook, "_pkill_fallback") as fallback, \
             mock.patch("sys.stdout", new=io.StringIO()) as captured:
            rc = run_playbook.kill_recorded_processes(allow_pkill_fallback=False)
            self.assertEqual(rc, 0)
            fallback.assert_not_called()
            output = captured.getvalue()
            self.assertIn("Refusing workstation-wide pkill cleanup", output)
            self.assertIn("--allow-pkill-fallback", output)

    def test_no_pid_files_with_flag_invokes_pkill(self) -> None:
        with mock.patch.object(run_playbook, "discover_pid_files", return_value=[]), \
             mock.patch.object(run_playbook, "_pkill_fallback") as fallback, \
             mock.patch("sys.stdout", new=io.StringIO()):
            rc = run_playbook.kill_recorded_processes(allow_pkill_fallback=True)
            self.assertEqual(rc, 0)
            fallback.assert_called_once()

    def test_default_invocation_has_no_flag(self) -> None:
        with mock.patch.object(run_playbook, "discover_pid_files", return_value=[]), \
             mock.patch.object(run_playbook, "_pkill_fallback") as fallback, \
             mock.patch("sys.stdout", new=io.StringIO()):
            run_playbook.kill_recorded_processes()
            fallback.assert_not_called()

    def test_main_kill_without_flag_does_not_invoke_pkill(self) -> None:
        with mock.patch.object(run_playbook, "discover_pid_files", return_value=[]), \
             mock.patch.object(run_playbook, "_pkill_fallback") as fallback, \
             mock.patch("sys.stdout", new=io.StringIO()):
            run_playbook.main(["--kill"])
            fallback.assert_not_called()

    def test_main_kill_with_allow_pkill_fallback_invokes_pkill(self) -> None:
        with mock.patch.object(run_playbook, "discover_pid_files", return_value=[]), \
             mock.patch.object(run_playbook, "_pkill_fallback") as fallback, \
             mock.patch("sys.stdout", new=io.StringIO()):
            run_playbook.main(["--kill", "--allow-pkill-fallback"])
            fallback.assert_called_once()

    def test_argparse_default_off(self) -> None:
        args = run_playbook.parse_args(["--kill"])
        self.assertFalse(args.allow_pkill_fallback)
        args = run_playbook.parse_args(["--kill", "--allow-pkill-fallback"])
        self.assertTrue(args.allow_pkill_fallback)


if __name__ == "__main__":
    unittest.main()
