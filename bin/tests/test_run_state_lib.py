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
            content = (
                "# Exploration\n\n"
                "## Finding 1: something interesting\n\n"
                + ("filler text " * 50)
                + "\n"
            )
            (quality / "EXPLORATION.md").write_text(
                content, encoding="utf-8"
            )
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertTrue(ok, msg=reason)
            self.assertEqual(reason, "")

    def test_validate_phase_artifacts_phase1_too_short(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "EXPLORATION.md").write_text(
                "## Finding 1\nshort\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("200-byte", reason)

    def test_validate_phase_artifacts_phase1_no_finding_section(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "EXPLORATION.md").write_text(
                ("filler " * 100) + "\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 1)
            self.assertFalse(ok)
            self.assertIn("finding section", reason)

    def test_validate_phase_artifacts_phase2_present(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "EXPLORATION_MERGED.md").write_text(
                "merged\n", encoding="utf-8",
            )
            ok, _ = lib.validate_phase_artifacts(quality, 2)
            self.assertTrue(ok)

    def test_validate_phase_artifacts_phase4_requires_both(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "REQUIREMENTS.md").write_text(
                "REQ-001 ...\n", encoding="utf-8",
            )
            ok, reason = lib.validate_phase_artifacts(quality, 4)
            self.assertFalse(ok)
            self.assertIn("COVERAGE_MATRIX.md", reason)
            (quality / "COVERAGE_MATRIX.md").write_text(
                "matrix\n", encoding="utf-8",
            )
            ok, _ = lib.validate_phase_artifacts(quality, 4)
            self.assertTrue(ok)

    def test_validate_phase_artifacts_phase6_empty_bugs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir)
            (quality / "BUGS.md").write_text("", encoding="utf-8")
            (quality / "INDEX.md").write_text("ok\n", encoding="utf-8")
            ok, reason = lib.validate_phase_artifacts(quality, 6)
            self.assertFalse(ok)
            self.assertIn("BUGS.md", reason)


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
            self.assertIn("- [x] Phase 1 — Exploration", text)
            self.assertIn("findings_total=12", text)
            self.assertIn("patterns_walked=7", text)
            self.assertIn(
                "- [ ] Phase 5 — Verification "
                "*(in progress, started 2026-05-15T14:58:31Z)*",
                text,
            )
            self.assertIn("- [ ] Phase 6 — Release readiness", text)
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
