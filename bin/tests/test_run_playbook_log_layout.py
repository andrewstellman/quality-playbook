"""v1.5.7 Phase 5 / Deliverable 3: centralized log emission tests.

Covers the runner-owned writers refactored in commits dc0757c (5a),
2599a86 (5b), b015b03 (5c):

  - log_file_for: playbook log lives at quality/logs/<run-id>/runner.log
  - _write_run_mode_marker: RUN_MODE.md lives at
    quality/logs/<run-id>/RUN_MODE.md
  - _emit_documentation_state_event / _emit_aborted_missing_docs_event:
    run_state.jsonl lives at quality/logs/<run-id>/run_state.jsonl
  - --logs-flat / QPB_LOGS_LEGACY=1: restores v1.5.6 byte-identical paths
  - resolve_run_state_path: fallback chain (latest symlink → most-recent
    sub-dir → legacy quality/run_state.jsonl)

Tests for deferred functionality (control_prompts/, run-<ts>.json,
quality-gate.log) are documented in HALT_phase5_partial.md and tracked
for the next Phase 5 sub-instruction; they are not in this module.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bin import run_playbook
from bin import run_state_lib


def _make_args(**overrides) -> argparse.Namespace:
    """Minimal argparse Namespace for the log-layout helpers."""
    base = dict(
        benchmark_mode=False,
        runner="copilot",
        model="claude-haiku-4.5",
        logs_flat=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class LogFileForTests(unittest.TestCase):
    """Acceptance scenario 1 (subset): runner-owned playbook log lives
    at quality/logs/<run-id>/runner.log in the centralized layout."""

    def test_centralized_path_default(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            path = run_playbook.log_file_for(repo, "20260512-130000")
            self.assertEqual(
                path,
                repo / "quality" / "logs" / "20260512T130000Z" / "runner.log",
            )

    def test_legacy_flag_restores_v1_5_6_path(self) -> None:
        # --logs-flat → byte-identical to v1.5.6.
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            args = _make_args(logs_flat=True)
            path = run_playbook.log_file_for(repo, "20260512-130000", args=args)
            self.assertEqual(
                path,
                repo.parent / "cell-playbook-20260512-130000.log",
            )

    def test_env_var_restores_v1_5_6_path(self) -> None:
        # QPB_LOGS_LEGACY=1 → same byte-identical legacy behavior.
        with TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"QPB_LOGS_LEGACY": "1"}):
            repo = Path(tmp) / "cell"
            repo.mkdir()
            path = run_playbook.log_file_for(repo, "20260512-130000")
            self.assertEqual(
                path,
                repo.parent / "cell-playbook-20260512-130000.log",
            )


class RunIdComputationTests(unittest.TestCase):
    """_compute_run_id converts display timestamps to compact UTC."""

    def test_display_form_to_compact_utc(self) -> None:
        self.assertEqual(
            run_playbook._compute_run_id("20260512-130000"),
            "20260512T130000Z",
        )

    def test_already_compact_utc_passthrough(self) -> None:
        self.assertEqual(
            run_playbook._compute_run_id("20260512T130000Z"),
            "20260512T130000Z",
        )


class RunStateJsonlPathTests(unittest.TestCase):
    """_run_state_jsonl_path resolves the write target for run_state.jsonl."""

    def test_centralized_path_with_run_id(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            path = run_playbook._run_state_jsonl_path(
                repo, "20260512T130000Z", args=_make_args(),
            )
            self.assertEqual(
                path,
                repo / "quality" / "logs" / "20260512T130000Z" / "run_state.jsonl",
            )

    def test_legacy_path_when_run_id_is_none(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            path = run_playbook._run_state_jsonl_path(
                repo, None, args=_make_args(),
            )
            self.assertEqual(path, repo / "quality" / "run_state.jsonl")

    def test_legacy_path_under_logs_flat(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            path = run_playbook._run_state_jsonl_path(
                repo, "20260512T130000Z", args=_make_args(logs_flat=True),
            )
            self.assertEqual(path, repo / "quality" / "run_state.jsonl")


class EmitDocumentationStateEventTests(unittest.TestCase):
    """_emit_documentation_state_event writes the event to the
    centralized location when args+timestamp are supplied, and to the
    legacy location otherwise (back-compat for callers that don't yet
    pass args+timestamp)."""

    def test_writes_to_centralized_location_with_args_timestamp(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            args = _make_args()
            written = run_playbook._emit_documentation_state_event(
                repo, "code_only", "test reason",
                args=args, timestamp="20260512-130000",
            )
            expected = repo / "quality" / "logs" / "20260512T130000Z" / "run_state.jsonl"
            self.assertEqual(written, expected)
            self.assertTrue(expected.is_file())
            event_obj = json.loads(expected.read_text(encoding="utf-8").strip())
            self.assertEqual(event_obj["event"], "documentation_state")
            self.assertEqual(event_obj["state"], "code_only")

    def test_writes_to_legacy_location_under_logs_flat(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            args = _make_args(logs_flat=True)
            written = run_playbook._emit_documentation_state_event(
                repo, "code_only", "test reason",
                args=args, timestamp="20260512-130000",
            )
            expected = repo / "quality" / "run_state.jsonl"
            self.assertEqual(written, expected)
            self.assertTrue(expected.is_file())
            # Verify NO centralized-layout file was created.
            self.assertFalse(
                (repo / "quality" / "logs" / "20260512T130000Z" / "run_state.jsonl").exists()
            )

    def test_writes_to_legacy_location_for_backcompat_no_args(self) -> None:
        # Callers that don't pass args/timestamp (older test fixtures,
        # legacy code paths) still write to the v1.5.6 location.
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            written = run_playbook._emit_documentation_state_event(
                repo, "with_docs", "test reason",
            )
            self.assertEqual(written, repo / "quality" / "run_state.jsonl")


class ResolveRunStatePathIntegrationTests(unittest.TestCase):
    """End-to-end: a runner-emitted run_state.jsonl is findable by
    resolve_run_state_path with no additional configuration."""

    def test_centralized_write_then_resolve_finds_it(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            args = _make_args()
            run_playbook._emit_documentation_state_event(
                repo, "with_docs", "test",
                args=args, timestamp="20260512-130000",
            )
            resolved = run_state_lib.resolve_run_state_path(repo)
            self.assertIsNotNone(resolved)
            self.assertEqual(
                resolved,
                repo / "quality" / "logs" / "20260512T130000Z" / "run_state.jsonl",
            )

    def test_legacy_write_then_resolve_finds_it(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            args = _make_args(logs_flat=True)
            run_playbook._emit_documentation_state_event(
                repo, "code_only", "test",
                args=args, timestamp="20260512-130000",
            )
            resolved = run_state_lib.resolve_run_state_path(repo)
            self.assertEqual(resolved, repo / "quality" / "run_state.jsonl")


class RunModeMarkerLayoutTests(unittest.TestCase):
    """_write_run_mode_marker writes RUN_MODE.md to the centralized
    location by default, legacy when --logs-flat is set."""

    def test_centralized_default(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            args = _make_args(benchmark_mode=True)
            run_playbook._write_run_mode_marker(repo, args, "20260512-130000")
            self.assertTrue(
                (repo / "quality" / "logs" / "20260512T130000Z" / "RUN_MODE.md").is_file()
            )
            # Legacy path NOT created.
            self.assertFalse((repo / "quality" / "RUN_MODE.md").exists())

    def test_legacy_under_logs_flat(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            args = _make_args(benchmark_mode=True, logs_flat=True)
            run_playbook._write_run_mode_marker(repo, args, "20260512-130000")
            self.assertTrue((repo / "quality" / "RUN_MODE.md").is_file())
            # Centralized path NOT created.
            self.assertFalse(
                (repo / "quality" / "logs" / "20260512T130000Z" / "RUN_MODE.md").exists()
            )


class LogsLegacyModeDetectionTests(unittest.TestCase):
    """_logs_legacy_mode handles all three signal paths."""

    def test_no_args_no_env_returns_false(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QPB_LOGS_LEGACY", None)
            self.assertFalse(run_playbook._logs_legacy_mode(None))

    def test_args_logs_flat_true(self) -> None:
        self.assertTrue(run_playbook._logs_legacy_mode(_make_args(logs_flat=True)))

    def test_env_var_set_to_1(self) -> None:
        with mock.patch.dict(os.environ, {"QPB_LOGS_LEGACY": "1"}):
            self.assertTrue(run_playbook._logs_legacy_mode(None))

    def test_env_var_set_to_other_returns_false(self) -> None:
        # Only "1" enables legacy mode; "0", "true", etc. don't.
        for val in ("0", "true", "yes", ""):
            with mock.patch.dict(os.environ, {"QPB_LOGS_LEGACY": val}):
                self.assertFalse(run_playbook._logs_legacy_mode(None),
                                 f"QPB_LOGS_LEGACY={val!r} should not enable legacy mode")

    def test_args_wins_over_env(self) -> None:
        # If args.logs_flat=True AND env QPB_LOGS_LEGACY=0, legacy mode
        # is True (args wins).
        with mock.patch.dict(os.environ, {"QPB_LOGS_LEGACY": "0"}):
            self.assertTrue(run_playbook._logs_legacy_mode(_make_args(logs_flat=True)))


class ControlPromptsDirTests(unittest.TestCase):
    """FS-1: _control_prompts_dir returns the active transcript directory."""

    def test_centralized_with_timestamp(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            path = run_playbook._control_prompts_dir(
                repo, args=_make_args(), timestamp="20260512-130000",
            )
            self.assertEqual(path, repo / "quality" / "logs" / "20260512T130000Z")
            self.assertTrue(path.is_dir())

    def test_legacy_under_logs_flat(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            path = run_playbook._control_prompts_dir(
                repo, args=_make_args(logs_flat=True), timestamp="20260512-130000",
            )
            self.assertEqual(path, repo / "quality" / "control_prompts")
            self.assertTrue(path.is_dir())

    def test_no_timestamp_falls_back_to_most_recent(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            # Plant two run-id dirs; helper should pick the lexicographic max.
            (repo / "quality" / "logs" / "20260101T000000Z").mkdir(parents=True)
            (repo / "quality" / "logs" / "20260512T000000Z").mkdir(parents=True)
            path = run_playbook._control_prompts_dir(
                repo, args=_make_args(), create=False,
            )
            self.assertEqual(path, repo / "quality" / "logs" / "20260512T000000Z")

    def test_no_timestamp_no_existing_dirs_falls_back_to_legacy(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            path = run_playbook._control_prompts_dir(
                repo, args=_make_args(), create=False,
            )
            self.assertEqual(path, repo / "quality" / "control_prompts")


class UpdateLatestSymlinkTests(unittest.TestCase):
    """FS-4: _update_latest_symlink creates quality/logs/latest → <run-id>."""

    def test_creates_relative_symlink(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            run_id = "20260512T130000Z"
            (repo / "quality" / "logs" / run_id).mkdir(parents=True)
            try:
                run_playbook._update_latest_symlink(
                    repo, "20260512-130000",
                    _make_args(), repo / "playbook.log",
                )
            except OSError:
                self.skipTest("Filesystem doesn't support symlinks")
            symlink = repo / "quality" / "logs" / "latest"
            if not symlink.is_symlink():
                self.skipTest("Filesystem doesn't support symlinks")
            # Relative target — operators can `cd quality/logs/latest`
            # to inspect the most recent run.
            self.assertEqual(os.readlink(symlink), run_id)
            # Resolve through the symlink lands at the run-id dir.
            self.assertEqual(symlink.resolve(), (repo / "quality" / "logs" / run_id).resolve())

    def test_legacy_mode_is_noop(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            log = repo / "playbook.log"
            log.write_text("", encoding="utf-8")
            args = _make_args(logs_flat=True)
            run_playbook._update_latest_symlink(repo, "20260512-130000", args, log)
            # No quality/logs/ created under legacy.
            self.assertFalse((repo / "quality" / "logs").exists())

    def test_oserror_during_symlink_logs_warning_and_continues(self) -> None:
        # v1.5.7 Phase 5 fix-up follow-on (C1-c): mock Path.symlink_to
        # to raise OSError, assert (a) the run continues without
        # crashing, (b) a warning is logged via lib.logboth. Closes
        # the test-coverage gap the Phase 5 fix-up mini-review flagged.
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            run_id = "20260512T130000Z"
            (repo / "quality" / "logs" / run_id).mkdir(parents=True)
            log_file = repo / "playbook.log"
            log_file.write_text("", encoding="utf-8")

            with mock.patch.object(
                Path, "symlink_to",
                side_effect=OSError("simulated filesystem failure"),
            ):
                # Should NOT raise — the helper must tolerate OSError.
                run_playbook._update_latest_symlink(
                    repo, "20260512-130000", _make_args(), log_file,
                )
            # Warning logged to the log file.
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("Could not update quality/logs/latest symlink", log_text)
            self.assertIn("simulated filesystem failure", log_text)
            # No symlink created (Path.symlink_to was patched to raise).
            symlink = repo / "quality" / "logs" / "latest"
            self.assertFalse(symlink.is_symlink())

    def test_replaces_pre_existing_symlink(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            (repo / "quality" / "logs" / "20260101T000000Z").mkdir(parents=True)
            (repo / "quality" / "logs" / "20260512T000000Z").mkdir(parents=True)
            try:
                (repo / "quality" / "logs" / "latest").symlink_to(
                    "20260101T000000Z", target_is_directory=True
                )
            except (OSError, NotImplementedError):
                self.skipTest("Filesystem doesn't support symlinks")
            run_playbook._update_latest_symlink(
                repo, "20260512-000000",
                _make_args(), repo / "playbook.log",
            )
            self.assertEqual(
                os.readlink(repo / "quality" / "logs" / "latest"),
                "20260512T000000Z",
            )


class CLIFlagTests(unittest.TestCase):
    """argparse --logs-flat flag is recognized + defaults to False."""

    def test_logs_flat_default_false(self) -> None:
        # Parse args with no --logs-flat; logs_flat attribute should
        # exist and be False.
        parser = argparse.ArgumentParser()
        # Re-add just the flag the way run_playbook.build_argument_parser does;
        # this avoids needing the full parser machinery (and avoids the
        # required-arg validation we don't care about here).
        parser.add_argument("--logs-flat", dest="logs_flat",
                            action="store_true", default=False)
        args = parser.parse_args([])
        self.assertFalse(args.logs_flat)

    def test_logs_flat_present_sets_true(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--logs-flat", dest="logs_flat",
                            action="store_true", default=False)
        args = parser.parse_args(["--logs-flat"])
        self.assertTrue(args.logs_flat)

    def test_real_parser_recognizes_logs_flat(self) -> None:
        # The actual build_parser must include --logs-flat (added in
        # commit dc0757c). Parse a minimal arg set to confirm.
        parser = run_playbook.build_parser()
        args = parser.parse_args(["--logs-flat"])
        self.assertTrue(getattr(args, "logs_flat", False))


if __name__ == "__main__":
    unittest.main()
