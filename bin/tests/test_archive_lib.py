"""Tests for bin/archive_lib.py (Phase 5c archival + INDEX rendering)."""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import archive_lib as al


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)


def _commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", message, "--allow-empty"],
        cwd=repo,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _fixed_now() -> datetime:
    return datetime(2026, 4, 19, 14, 30, 22, tzinfo=timezone.utc)


class TimestampTests(unittest.TestCase):
    def test_utc_compact_format(self) -> None:
        self.assertEqual(al.utc_compact_timestamp(_fixed_now()), "20260419T143022Z")

    def test_utc_extended_format(self) -> None:
        self.assertEqual(al.utc_extended_timestamp(_fixed_now()), "2026-04-19T14:30:22Z")


class WriteTimestampedResultTests(unittest.TestCase):
    def test_writes_timestamped_and_latest_with_extension(self) -> None:
        with TemporaryDirectory() as tmp:
            quality = Path(tmp) / "quality"
            ts_path, latest_path = al.write_timestamped_result(
                quality,
                "recheck-results.json",
                "{\"ok\": true}",
                now=_fixed_now(),
            )
            self.assertEqual(ts_path.name, "recheck-results-20260419T143022Z.json")
            self.assertEqual(latest_path.name, "recheck-results-latest.json")
            self.assertTrue(ts_path.is_file())
            self.assertTrue(latest_path.exists())
            # Latest resolves to the timestamped file (symlink or copy).
            if latest_path.is_symlink():
                target = os.readlink(latest_path)
                self.assertEqual(target, ts_path.name)
            else:
                self.assertEqual(latest_path.read_text(encoding="utf-8"), "{\"ok\": true}")

    def test_writes_extensionless(self) -> None:
        with TemporaryDirectory() as tmp:
            quality = Path(tmp) / "quality"
            ts_path, latest_path = al.write_timestamped_result(
                quality,
                "gate-report",
                "pass",
                now=_fixed_now(),
            )
            self.assertEqual(ts_path.name, "gate-report-20260419T143022Z")
            self.assertEqual(latest_path.name, "gate-report-latest")

    def test_overwrites_latest_on_second_call(self) -> None:
        with TemporaryDirectory() as tmp:
            quality = Path(tmp) / "quality"
            first_now = datetime(2026, 4, 19, 10, 0, 0, tzinfo=timezone.utc)
            second_now = datetime(2026, 4, 19, 11, 0, 0, tzinfo=timezone.utc)
            al.write_timestamped_result(quality, "gate.json", "{\"v\": 1}", now=first_now)
            al.write_timestamped_result(quality, "gate.json", "{\"v\": 2}", now=second_now)
            latest = quality / "results" / "gate-latest.json"
            # latest should now point at the second write.
            if latest.is_symlink():
                target = os.readlink(latest)
                self.assertIn("11", target)  # second timestamp
            else:
                self.assertEqual(latest.read_text(encoding="utf-8"), "{\"v\": 2}")


class RunIndexRenderingTests(unittest.TestCase):
    def test_run_index_row_counts_bugs(self) -> None:
        payload = {
            "qpb_version": "1.5.1",
            "target_role_breakdown": {
                "files_by_role": {"code": 1},
                "size_by_role": {"code": 100},
                "percentages": {
                    "skill_share": 0.0,
                    "code_share": 1.0,
                    "tool_share": 0.0,
                    "other_share": 0.0,
                },
            },
            "summary": {
                "bugs": {"HIGH": 2, "MEDIUM": 3, "LOW": 1, "code-fix": 0, "spec-fix": 0},
                "gate_verdict": "pass",
            },
        }
        row = al.render_run_index_row("20260419T143022Z", payload)
        self.assertIn("| 20260419T143022Z ", row)
        self.assertIn("| 1.5.1 ", row)
        # v1.5.4 Part 1: project-type column replaced by role-breakdown
        # summary derived from target_role_breakdown.percentages.
        self.assertIn("skill 0% / code 100% / tool 0% / other 0%", row)
        self.assertIn("| pass ", row)
        self.assertIn("| 6 ", row)  # 2+3+1
        self.assertIn(
            "[INDEX.md](quality/previous_runs/20260419T143022Z/INDEX.md)",
            row,
        )

    def test_run_index_row_falls_back_to_na_when_role_map_absent(self) -> None:
        payload = {
            "qpb_version": "1.5.1",
            "target_role_breakdown": None,
            "summary": {"bugs": {"HIGH": 1}, "gate_verdict": "partial"},
        }
        row = al.render_run_index_row("20260419T143022Z", payload)
        self.assertIn("| n/a ", row)

    def test_run_index_header_has_columns(self) -> None:
        h = al.render_run_index_header()
        self.assertIn("| Run | QPB version |", h)
        self.assertIn("Role breakdown", h)

    def test_index_markdown_contains_provenance(self) -> None:
        rendered = al.render_index_markdown(
            "20260419T143022Z",
            {"qpb_version": "1.5.1", "summary": {"bugs": {}, "gate_verdict": "pass"}},
            provenance="written by test",
        )
        self.assertIn("written by test", rendered)
        self.assertIn("# Run Index — 20260419T143022Z", rendered)
        self.assertIn("```json", rendered)


class AppendRunIndexRowTests(unittest.TestCase):
    def _payload(self, verdict: str = "pass") -> dict:
        return {
            "qpb_version": "1.5.1",
            "target_role_breakdown": None,
            "summary": {"bugs": {"HIGH": 1}, "gate_verdict": verdict},
        }

    def test_creates_file_with_header_when_absent(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            al.append_run_index_row(repo, "20260419T100000Z", self._payload())
            text = (repo / "quality" / "RUN_INDEX.md").read_text(encoding="utf-8")
            self.assertIn("| Run | QPB version |", text)
            self.assertIn("| 20260419T100000Z ", text)

    def test_appends_to_existing_file_without_rewriting_prior_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            al.append_run_index_row(repo, "20260419T100000Z", self._payload("pass"))
            al.append_run_index_row(repo, "20260420T100000Z", self._payload("partial"))
            text = (repo / "quality" / "RUN_INDEX.md").read_text(encoding="utf-8")
            self.assertIn("| 20260419T100000Z ", text)
            self.assertIn("| 20260420T100000Z ", text)
            # First row still says pass.
            first_row_line = next(
                line for line in text.splitlines() if "20260419T100000Z" in line
            )
            self.assertIn(" pass ", first_row_line)

    def test_is_idempotent_for_duplicate_run_id(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            al.append_run_index_row(repo, "20260419T100000Z", self._payload())
            before = (repo / "quality" / "RUN_INDEX.md").read_text(encoding="utf-8")
            al.append_run_index_row(repo, "20260419T100000Z", self._payload())
            after = (repo / "quality" / "RUN_INDEX.md").read_text(encoding="utf-8")
            self.assertEqual(before, after)


class ArchiveRunTests(unittest.TestCase):
    def _seed_live_run(self, repo: Path) -> None:
        _init_git(repo)
        _write(repo / "quality" / "BUGS.md", "# Bugs\n\n<!-- Quality Playbook v1.5.1 -->\n\n### BUG-001\n\n**Severity**: HIGH\n")
        _write(repo / "quality" / "REQUIREMENTS.md", "# Requirements\n\n### REQ-001\n\n**Tier**: 3\nBody.\n")
        _write(repo / "quality" / "PROGRESS.md", "## Phase completion\n\n- [x] Phase 1: Exploration\n- [x] Phase 2: Generation\n")
        _commit(repo, "seed run content")

    def test_success_archive_has_no_suffix(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_live_run(repo)
            archive = al.archive_run(repo, "20260419T143022Z", status="success")
            self.assertEqual(archive.name, "20260419T143022Z")
            self.assertTrue((archive / "quality" / "BUGS.md").is_file())
            self.assertTrue((archive / "INDEX.md").is_file())
            self.assertTrue((repo / "quality" / "RUN_INDEX.md").is_file())
            # Live quality/ remains in place.
            self.assertTrue((repo / "quality" / "BUGS.md").is_file())

    def test_failed_archive_has_failed_suffix(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_live_run(repo)
            archive = al.archive_run(repo, "20260419T143022Z", status="failed")
            self.assertEqual(archive.name, "20260419T143022Z-FAILED")
            payload = al.load_index_payload(archive / "INDEX.md")
            self.assertEqual(payload["summary"]["gate_verdict"], "fail")

    def test_partial_archive_writes_sentinel_no_filename_suffix(self) -> None:
        """v1.5.4 Phase 3.6.2 (B-19): partial runs land at the bare
        timestamp folder name with an in-archive `.partial` sentinel
        — no `-PARTIAL` filename suffix. Pins the migration."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_live_run(repo)
            archive = al.archive_run(repo, "20260419T143022Z", status="partial")
            self.assertEqual(archive.name, "20260419T143022Z")
            self.assertTrue(
                (archive / al.PARTIAL_SENTINEL_NAME).is_file(),
                f"expected {al.PARTIAL_SENTINEL_NAME} sentinel inside the "
                "archive folder for partial runs",
            )
            payload = al.load_index_payload(archive / "INDEX.md")
            self.assertEqual(payload["summary"]["gate_verdict"], "partial")

    def test_archive_lands_under_previous_runs_not_runs(self) -> None:
        """v1.5.4 Phase 3.6.2 (B-19): canonical archive directory is
        `previous_runs/`, not the legacy `runs/`."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_live_run(repo)
            archive = al.archive_run(repo, "20260419T143022Z", status="success")
            self.assertEqual(archive.parent.name, "previous_runs")
            self.assertFalse(
                (repo / "quality" / "runs").exists(),
                "fresh archive must not create the legacy quality/runs/ dir",
            )

    def test_archive_refuses_when_target_exists(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_live_run(repo)
            al.archive_run(repo, "20260419T143022Z", status="success")
            with self.assertRaises(al.ArchiveError):
                al.archive_run(repo, "20260419T143022Z", status="success")

    def test_archive_excludes_archive_subtrees(self) -> None:
        """v1.5.4 Phase 3.6.2 (H2 fix): archive_run must not recurse
        into either previous_runs/ or the legacy runs/. Without this
        every fresh archive grows unbounded."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_live_run(repo)
            # Pre-existing archived runs in BOTH layouts. Neither
            # should be copied into the new archive.
            _write(
                repo / "quality" / "previous_runs" / "priorrun" / "INDEX.md",
                "prior-current",
            )
            _write(
                repo / "quality" / "runs" / "legacyrun" / "INDEX.md",
                "prior-legacy",
            )
            archive = al.archive_run(repo, "20260419T143022Z", status="success")
            self.assertFalse(
                (archive / "quality" / "previous_runs").exists(),
                "fresh archive must not include quality/previous_runs/",
            )
            self.assertFalse(
                (archive / "quality" / "runs").exists(),
                "fresh archive must not include the legacy quality/runs/",
            )

    def test_archive_run_appends_run_index_row(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_live_run(repo)
            al.archive_run(repo, "20260419T143022Z", status="success")
            text = (repo / "quality" / "RUN_INDEX.md").read_text(encoding="utf-8")
            self.assertIn("20260419T143022Z", text)
            self.assertIn(
                "[INDEX.md](quality/previous_runs/20260419T143022Z/INDEX.md)",
                text,
            )

    def test_archive_rejects_when_quality_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with self.assertRaises(al.ArchiveError):
                al.archive_run(repo, "20260419T143022Z", status="success")

    def test_archive_rejects_invalid_status(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._seed_live_run(repo)
            with self.assertRaises(al.ArchiveError):
                al.archive_run(repo, "20260419T143022Z", status="cancelled")


class CLITests(unittest.TestCase):
    def test_cli_exits_zero_on_success(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_git(repo)
            _write(repo / "quality" / "BUGS.md", "# bugs\n")
            _commit(repo, "init")
            self.assertEqual(
                al.main([str(repo), "--status", "partial", "--timestamp", "20260419T143022Z"]),
                0,
            )
            # v1.5.4 Phase 3.6.2: partial → previous_runs/<ts>/.partial
            archive = (
                repo / "quality" / "previous_runs" / "20260419T143022Z"
            )
            self.assertTrue((archive / "INDEX.md").is_file())
            self.assertTrue((archive / al.PARTIAL_SENTINEL_NAME).is_file())

    def test_cli_exits_one_on_missing_quality(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.assertEqual(
                al.main([str(repo), "--timestamp", "20260419T143022Z"]),
                1,
            )


class ComputeArchiveTimestampTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.2 (B-19, M8 fix): pin the timestamp source
    chain — INDEX.run_timestamp_end → BUGS.md mtime → current UTC.
    The prior implementation used INDEX.run_timestamp_start (the
    *stub* timestamp written before Phase 1), which was the wrong
    field — `_end` is when the artifacts were finalized."""

    def test_uses_run_timestamp_end_from_index(self) -> None:
        with TemporaryDirectory() as tmp:
            quality = Path(tmp)
            (quality / "INDEX.md").write_text(
                '# Run Index\n\n```json\n'
                '{"run_timestamp_start": "2026-04-18T11:30:00Z",'
                ' "run_timestamp_end":   "2026-04-18T12:34:56Z"}\n'
                '```\n',
                encoding="utf-8",
            )
            ts = al.compute_archive_timestamp(quality)
            self.assertEqual(ts, "20260418T123456Z")

    def test_falls_back_to_bugs_mtime_when_index_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            quality = Path(tmp)
            bugs = quality / "BUGS.md"
            bugs.write_text("# bugs", encoding="utf-8")
            # Force a known mtime so the assertion is deterministic.
            target_epoch = 1745000000  # 2025-04-18T16:53:20Z
            os.utime(bugs, (target_epoch, target_epoch))
            ts = al.compute_archive_timestamp(quality)
            from datetime import datetime, timezone
            expected = datetime.fromtimestamp(
                target_epoch, tz=timezone.utc
            ).strftime("%Y%m%dT%H%M%SZ")
            self.assertEqual(ts, expected)

    def test_final_fallback_to_now_when_both_absent(self) -> None:
        from datetime import datetime, timezone
        with TemporaryDirectory() as tmp:
            quality = Path(tmp)
            # Empty quality dir — no INDEX, no BUGS.md.
            fixed_now = datetime(
                2026, 4, 30, 1, 23, 45, tzinfo=timezone.utc
            )
            ts = al.compute_archive_timestamp(quality, now=fixed_now)
            self.assertEqual(ts, "20260430T012345Z")

    def test_index_with_only_start_falls_through(self) -> None:
        """Pre-v1.5.4 INDEX files only carry run_timestamp_start (the
        stub timestamp). M8 fix: those fall through past INDEX to the
        BUGS.md mtime / current UTC chain rather than mis-pinning."""
        from datetime import datetime, timezone
        with TemporaryDirectory() as tmp:
            quality = Path(tmp)
            (quality / "INDEX.md").write_text(
                '# Run Index\n\n```json\n'
                '{"run_timestamp_start": "2026-04-18T11:30:00Z"}\n'
                '```\n',
                encoding="utf-8",
            )
            fixed_now = datetime(
                2026, 4, 30, 1, 23, 45, tzinfo=timezone.utc
            )
            ts = al.compute_archive_timestamp(quality, now=fixed_now)
            # No BUGS.md, no run_timestamp_end → current UTC.
            self.assertEqual(ts, "20260430T012345Z")


class LegacyArchiveLayoutCompatTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.2 (B-19): pre-v1.5.4 archives sit under
    ``quality/runs/``; new archives land under
    ``quality/previous_runs/``. The legacy directory remains readable
    for backward-compat. These tests pin both directions."""

    def test_legacy_runs_dir_excluded_from_fresh_archive(self) -> None:
        # Already covered by test_archive_excludes_archive_subtrees,
        # but pin again from the legacy-compat angle to make the
        # contract explicit.
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            quality = repo / "quality"
            quality.mkdir()
            (quality / "BUGS.md").write_text("bug")
            (quality / "runs" / "legacy-20260101").mkdir(parents=True)
            (quality / "runs" / "legacy-20260101" / "INDEX.md").write_text("legacy")
            archive = al.archive_run(
                repo, "20260430T020000Z", status="success"
            )
            self.assertFalse(
                (archive / "quality" / "runs").exists(),
                "legacy runs/ tree must NOT be recursively included",
            )
            # Legacy archive itself is untouched.
            self.assertTrue((quality / "runs" / "legacy-20260101").is_dir())

    def test_constants_exposed(self) -> None:
        """Constants are part of the public API per the brief — they
        get referenced by run_playbook (preserve list), the harness
        scripts (sentinel scan), and downstream consumers."""
        self.assertEqual(al.ARCHIVE_DIRNAME, "previous_runs")
        self.assertEqual(al.LEGACY_ARCHIVE_DIRNAME, "runs")
        self.assertEqual(al.PARTIAL_SENTINEL_NAME, ".partial")


class BugHeadingPatternTests(unittest.TestCase):
    """v1.5.6 codex bootstrap fix (065) — BUG-006 (MEDIUM).

    Pre-fix _BUG_HEADING_PATTERN matched only the bare form
    `### BUG-NNN`, missing the canonical `### BUG-NNN: Title` form
    that QPB itself produces. _extract_bug_counts() undercounted
    severity totals when BUGS.md used the titled form.
    """

    def test_bug_006_archive_bug_count_accepts_titled_bug_headings(self) -> None:
        """The regex must match `### BUG-NNN: Title` (with title suffix)
        — that's the canonical form the playbook itself produces."""
        with TemporaryDirectory() as tmp:
            run_folder = Path(tmp)
            _write(
                run_folder / "quality" / "BUGS.md",
                "# Bugs\n\n"
                "### BUG-001: Cite-only docs trigger false code-only warning\n\n"
                "**Severity**: HIGH\n",
            )
            counts = al._extract_bug_counts(run_folder)
            self.assertEqual(
                counts["HIGH"], 1,
                "_extract_bug_counts must recognize the canonical "
                "`### BUG-NNN: Title` heading form; pre-fix it only "
                "matched bare `### BUG-NNN`",
            )

    def test_bug_006_archive_bug_count_still_accepts_bare_bug_headings(self) -> None:
        """Backward compatibility: the bare form `### BUG-NNN` (no title)
        must still match — some legacy archives use it."""
        with TemporaryDirectory() as tmp:
            run_folder = Path(tmp)
            _write(
                run_folder / "quality" / "BUGS.md",
                "# Bugs\n\n### BUG-001\n\n**Severity**: MEDIUM\n",
            )
            counts = al._extract_bug_counts(run_folder)
            self.assertEqual(counts["MEDIUM"], 1)

    def test_bug_006_archive_bug_count_handles_mixed_bare_and_titled(self) -> None:
        """A BUGS.md with both forms (some bare, some titled) must
        count every entry exactly once."""
        with TemporaryDirectory() as tmp:
            run_folder = Path(tmp)
            _write(
                run_folder / "quality" / "BUGS.md",
                "# Bugs\n\n"
                "### BUG-001: First with title\n\n**Severity**: HIGH\n\n"
                "### BUG-002\n\n**Severity**: HIGH\n\n"
                "### BUG-003: Third with title\n\n**Severity**: LOW\n",
            )
            counts = al._extract_bug_counts(run_folder)
            self.assertEqual(counts["HIGH"], 2)
            self.assertEqual(counts["LOW"], 1)

    def test_duration_seconds_handles_mixed_naive_aware_iso(self) -> None:
        """v1.5.6 fix-up 071 carry-over: _parse_iso() returns
        UTC-aware datetimes for ISO strings with a Z suffix or
        +HH:MM offset, but NAIVE for bare strings like
        '2026-05-08T12:34:56'. Pre-fix _duration_seconds() did
        (b - a).total_seconds() directly, which raises TypeError on
        mixed naive/aware inputs. Codex hit this on a fresh 2026-05-08
        skill-direct bootstrap via write_live_index_final().
        """
        # Naive start, UTC-aware end.
        start_naive = "2026-05-08T12:00:00"
        end_aware_z = "2026-05-08T12:00:30Z"
        # Must NOT raise TypeError; result is non-negative.
        result = al._duration_seconds(start_naive, end_aware_z)
        self.assertEqual(result, 30)

        # UTC-aware start, naive end.
        start_aware_z = "2026-05-08T12:00:00Z"
        end_naive = "2026-05-08T12:00:45"
        result = al._duration_seconds(start_aware_z, end_naive)
        self.assertEqual(result, 45)

        # Both naive (no Z, no offset) — must still work.
        result = al._duration_seconds(
            "2026-05-08T12:00:00", "2026-05-08T12:01:00"
        )
        self.assertEqual(result, 60)

        # Both aware — must still work.
        result = al._duration_seconds(
            "2026-05-08T12:00:00+00:00", "2026-05-08T12:00:15+00:00"
        )
        self.assertEqual(result, 15)

    def test_ps_6_archive_bug_count_accepts_hyphenated_suffix_bug_ids(self) -> None:
        """v1.5.6 fix-up 067 PS-6: capture group widened from
        [A-Za-z0-9]+ to [A-Za-z0-9][A-Za-z0-9\\-]* so suffixed BUG IDs
        like BUG-001-fix-2 or BUG-001a match. Currently latent (no
        BUG IDs use suffixes) but cheap to widen now."""
        with TemporaryDirectory() as tmp:
            run_folder = Path(tmp)
            _write(
                run_folder / "quality" / "BUGS.md",
                "# Bugs\n\n"
                "### BUG-001-fix-2: Title with hyphenated suffix\n\n"
                "**Severity**: HIGH\n",
            )
            counts = al._extract_bug_counts(run_folder)
            self.assertEqual(
                counts["HIGH"], 1,
                "regex must accept BUG-NNN-suffix form, not just bare BUG-NNN",
            )

        # And group 1 captures the whole hyphenated ID, not just the
        # numeric prefix.
        match = al._BUG_HEADING_PATTERN.search(
            "### BUG-001-fix-2: Title\n"
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "001-fix-2")


if __name__ == "__main__":
    unittest.main()
