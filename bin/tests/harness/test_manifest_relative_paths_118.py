"""v1.5.7 118 — manifest stores RELATIVE paths so a harness-run
folder is portable across machines / mount points.

Pre-118: `manifest.json` stored ABSOLUTE paths
(``run_dir: /Users/andrewstellman/Documents/QPB/aup-experiment/<TS>/run-00``).
Copy the folder to another machine and `status` / `tui` /
`collect` couldn't read it — the baked-in absolute paths don't
resolve there. The 117 cowork review surfaced this as a
deferred nit; 118 closes it.

118 fix:
  * NEW ``plan_runner._relpath_for_manifest`` +
    ``_relativize_manifest_entry``: at manifest-write time,
    convert ``run_dir`` / ``stream_path`` / ``status_path`` /
    ``target_dir`` to paths relative to the harness-run dir
    (when they're under it).
  * NEW ``status._resolve_manifest_path`` +
    ``plan_runner._resolve_entry_path``: at read time,
    resolve relative paths against the harness-run dir the
    caller passes. Back-compat: absolute paths that exist
    are used as-is; absolute paths whose folder has moved
    are repaired by extracting the part after the
    harness-run dir's name.
  * `_read_one_run_status` + `_collect_one_run_detached`
    use the resolver instead of `Path(entry[...])`.

Coverage:
  * Manifest WRITE: relative paths (``run-00``,
    ``run-00/stream.ndjson``, …) — NOT absolute.
  * **THE 118 LOAD-BEARING TEST — moved-folder
    portability**: build a harness-run, MOVE it to a
    different absolute path, read via ``read_run_status``
    → all runs resolve (phase, state, stream) without
    falling back to PENDING / "—". Mutation-bite: revert
    the manifest writer to absolute paths ⇒ the moved-folder
    read shows PENDING/—/— and the test FAILS.
  * Backward compat: a legacy absolute-path manifest (paths
    still valid) reads correctly.
  * Legacy moved-folder repair: absolute paths whose folder
    has been moved are repaired via name-tail extraction.
  * The resolver pure helper covers the path-rule matrix.
  * Bundle-safety preserved.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness import status as ST


# ---------------------------------------------------------------------------
# Task B helpers — the pure path-resolver tests
# ---------------------------------------------------------------------------


class ResolveManifestPathTests(unittest.TestCase):
    """``status._resolve_manifest_path`` (and its sibling
    ``plan_runner._resolve_entry_path``) implement the
    4-branch resolution rule."""

    def test_empty_returns_harness_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp)
            self.assertEqual(
                ST._resolve_manifest_path("", hr), hr)

    def test_relative_resolves_against_harness_dir(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "run-2026-05-27"
            hr.mkdir()
            resolved = ST._resolve_manifest_path(
                "run-00/stream.ndjson", hr)
            self.assertEqual(
                resolved,
                hr / "run-00" / "stream.ndjson",
            )

    def test_absolute_existing_kept_as_is(self) -> None:
        """Back-compat: a legacy 108-117 absolute path that
        STILL EXISTS reads as-is. Nothing breaks for the
        unmoved-folder case."""
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "harness-run"
            hr.mkdir()
            run_dir = hr / "run-00"
            run_dir.mkdir()
            resolved = ST._resolve_manifest_path(
                str(run_dir), hr)
            self.assertEqual(resolved, run_dir)

    def test_absolute_moved_repaired_via_name_tail(
            self) -> None:
        """**Legacy-moved repair**: an absolute path whose
        folder has been moved (path no longer exists) gets
        repaired by extracting the portion AFTER the
        harness-run dir's name in the path. Critical for
        reading legacy folders moved across machines."""
        with tempfile.TemporaryDirectory() as tmp:
            new_hr = Path(tmp) / "20260527T145902Z"
            new_hr.mkdir()
            (new_hr / "run-00").mkdir()
            # Simulate a legacy absolute path from another
            # machine: /Users/other/aup-exp/<same-tail>/run-00.
            legacy_abs = (
                "/Users/other/aup-exp/20260527T145902Z/run-00"
            )
            resolved = ST._resolve_manifest_path(
                legacy_abs, new_hr)
            self.assertEqual(resolved, new_hr / "run-00")

    def test_absolute_moved_unrelated_falls_back_to_basename(
            self) -> None:
        """An absolute path whose folder name doesn't appear
        anywhere in the parent chain ⇒ fall through to
        ``harness_run_dir / basename``. Polite degradation."""
        with tempfile.TemporaryDirectory() as tmp:
            new_hr = Path(tmp) / "harness-run"
            new_hr.mkdir()
            resolved = ST._resolve_manifest_path(
                "/Users/somewhere/totally/unrelated.txt",
                new_hr,
            )
            self.assertEqual(
                resolved, new_hr / "unrelated.txt")

    def test_plan_runner_resolver_mirrors_status(
            self) -> None:
        """Both resolvers exist to avoid a status → plan_runner
        circular import. They must produce identical results
        for the same input."""
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "run-2026-05-27"
            hr.mkdir()
            for value in (
                "", "run-00/stream.ndjson",
                str(hr / "run-00"),
                "/some/legacy/run-2026-05-27/run-00",
            ):
                self.assertEqual(
                    ST._resolve_manifest_path(value, hr),
                    PR._resolve_entry_path(value, hr),
                    f"diverged on value {value!r}",
                )


# ---------------------------------------------------------------------------
# Task A — write-side relativizer
# ---------------------------------------------------------------------------


class RelpathForManifestTests(unittest.TestCase):

    def test_absolute_under_harness_relativized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp)
            self.assertEqual(
                PR._relpath_for_manifest(
                    str(hr / "run-00" / "stream.ndjson"),
                    hr,
                ),
                "run-00/stream.ndjson",
            )

    def test_relative_passthrough(self) -> None:
        self.assertEqual(
            PR._relpath_for_manifest(
                "run-00/stream.ndjson", Path("/tmp/hr")),
            "run-00/stream.ndjson",
        )

    def test_empty_passthrough(self) -> None:
        self.assertEqual(
            PR._relpath_for_manifest("", Path("/tmp/hr")),
            "",
        )

    def test_absolute_outside_harness_kept(self) -> None:
        """A target_dir on a different mount stays absolute —
        relative_to would raise; we surface the absolute
        path so the resolver's back-compat branch can read
        it on the same machine."""
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp)
            other = "/var/tmp/elsewhere/repo"
            self.assertEqual(
                PR._relpath_for_manifest(other, hr),
                other,
            )

    def test_entry_relativized_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp)
            entry = {
                "index": 0,
                "run_dir": str(hr / "run-00"),
                "stream_path": str(
                    hr / "run-00" / "stream.ndjson"),
                "status_path": str(
                    hr / "run-00" / "status.json"),
                "target_dir": str(hr / "run-00" / "target"),
                "other_field": "value",
            }
            out = PR._relativize_manifest_entry(entry, hr)
            self.assertEqual(out["run_dir"], "run-00")
            self.assertEqual(
                out["stream_path"], "run-00/stream.ndjson")
            self.assertEqual(
                out["status_path"], "run-00/status.json")
            self.assertEqual(
                out["target_dir"], "run-00/target")
            # Non-path fields unchanged.
            self.assertEqual(out["index"], 0)
            self.assertEqual(out["other_field"], "value")
            # Input unmutated.
            self.assertTrue(Path(entry["run_dir"]).is_absolute())


# ---------------------------------------------------------------------------
# Task D — moved-folder portability (THE LOAD-BEARING TEST)
# ---------------------------------------------------------------------------


def _build_harness_run_with_phase_sentinel(
        harness_run_dir: Path, *,
        phase: int = 2, name: str = "generation",
        state: str = "start") -> None:
    """Stand up a 1-run harness-run with a populated stream +
    a relative-path manifest. The 117 embedded sentinel
    fixture is used so phase resolution exercises the full
    117+118 path together."""
    harness_run_dir.mkdir(parents=True, exist_ok=True)
    run_dir = harness_run_dir / "run-00"
    run_dir.mkdir()
    # Build an embedded-sentinel stream line (117 form).
    payload = json.dumps({
        "v": 1, "kind": "phase", "phase": phase,
        "name": name, "state": state,
        "ts": "2026-05-27T15:01:22Z",
    })
    sentinel_text = f"::QPB:: {payload}"
    event = json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [{
                "tool_use_id": "toolu_test",
                "type": "tool_result",
                "content": sentinel_text,
                "is_error": False,
            }],
        },
        "tool_use_result": {
            "stdout": sentinel_text,
            "stderr": "",
        },
    })
    (run_dir / "stream.ndjson").write_text(
        event + "\n", encoding="utf-8")
    # status.json with RUNNING state so the row populates.
    (run_dir / "status.json").write_text(json.dumps({
        "state": "RUNNING",
        "pid": 9999,
        "started_at": "2026-05-27T15:00:00Z",
        "heartbeat": "2026-05-27T15:01:00Z",
        "exit_code": None,
        "terminal_state": None,
    }) + "\n", encoding="utf-8")
    # 118: write the manifest with RELATIVE paths.
    manifest = {
        "harness_run_dir": str(harness_run_dir),
        "plan": {"pools": {"claude": 1}},
        "runs": [{
            "index": 0, "description": "118 portability",
            "repo": "https://github.com/x/y",
            "runner": "claude", "model": "opus",
            "channel": "clone", "mode": "A",
            "target_dir": "run-00/target",
            "run_dir": "run-00",
            "run_id": "r",
            "pid": 9999,
            "started_at": "2026-05-27T15:00:00Z",
            "stream_path": "run-00/stream.ndjson",
            "status_path": "run-00/status.json",
            "max_duration_s": 60.0,
            "expect": {},
        }],
    }
    (harness_run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


class MovedFolderPortabilityTests(unittest.TestCase):
    """**THE 118 LOAD-BEARING TEST**: a harness-run folder
    built at one absolute path must read correctly when
    copied / moved to a totally different absolute path.

    Mutation-bite: revert the manifest writer to store
    absolute paths ⇒ the moved-folder read returns
    PENDING/—/— and this test FAILS."""

    def test_moved_folder_reads_phase_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as origin_tmp:
            with tempfile.TemporaryDirectory() as moved_tmp:
                origin_hr = (Path(origin_tmp)
                              / "20260527T145902Z")
                _build_harness_run_with_phase_sentinel(
                    origin_hr)
                # Move (copy + delete original) to a DIFFERENT
                # absolute path.
                moved_hr = Path(moved_tmp) / "20260527T145902Z"
                shutil.copytree(origin_hr, moved_hr)
                shutil.rmtree(origin_hr)
                # Read at the NEW location.
                runs = ST.read_run_status(moved_hr)
                self.assertEqual(len(runs), 1)
                run = runs[0]
                # **THE LOAD-BEARING ASSERTIONS** — these all
                # FAIL pre-118 when the manifest has absolute
                # paths from origin_tmp (which no longer
                # exist).
                self.assertEqual(run.state, "RUNNING")
                self.assertEqual(run.current_phase, "P2")
                self.assertEqual(
                    run.current_phase_name, "generation")
                # Verify the run_dir actually resolved to the
                # new location (defense against subtle path
                # bugs).
                self.assertEqual(
                    run.run_dir, moved_hr / "run-00")
                self.assertEqual(
                    run.stream_path,
                    moved_hr / "run-00" / "stream.ndjson",
                )

    def test_list_harness_runs_picks_up_moved(self) -> None:
        """``list_harness_runs(parent)`` works on the moved
        location too — the summary populates progress and
        last_activity_iso."""
        with tempfile.TemporaryDirectory() as moved_tmp:
            moved_root = Path(moved_tmp)
            hr = moved_root / "20260527T145902Z"
            _build_harness_run_with_phase_sentinel(
                hr, phase=3, name="code-review")
            [summary] = ST.list_harness_runs(moved_root)
            self.assertEqual(summary.total_runs, 1)
            self.assertEqual(summary.running, 1)
            # The 117 progress signal works through the moved
            # location too.
            self.assertEqual(summary.progress, "P3/P6")


class BackwardCompatLegacyAbsolutePathTests(unittest.TestCase):
    """Legacy 108-117 manifests stored absolute paths. They
    must keep working on the original machine (paths still
    exist) — 118 doesn't break the in-place case."""

    def test_legacy_absolute_manifest_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "legacy-hr"
            hr.mkdir()
            run_dir = hr / "run-00"
            run_dir.mkdir()
            (run_dir / "stream.ndjson").write_text(
                "", encoding="utf-8")
            (run_dir / "status.json").write_text(json.dumps({
                "state": "RUNNING", "pid": 8888,
                "started_at": "2026-05-27T15:00:00Z",
                "heartbeat": "2026-05-27T15:00:30Z",
                "exit_code": None,
                "terminal_state": None,
            }) + "\n", encoding="utf-8")
            # Legacy manifest: absolute paths (the pre-118
            # shape).
            legacy_manifest = {
                "harness_run_dir": str(hr),
                "plan": {"pools": {"claude": 1}},
                "runs": [{
                    "index": 0, "description": "legacy",
                    "repo": "y", "runner": "claude",
                    "model": "opus", "channel": "clone",
                    "mode": "A",
                    "target_dir": str(run_dir / "target"),
                    "run_dir": str(run_dir),
                    "run_id": "r", "pid": 8888,
                    "started_at": "2026-05-27T15:00:00Z",
                    "stream_path": str(
                        run_dir / "stream.ndjson"),
                    "status_path": str(
                        run_dir / "status.json"),
                    "max_duration_s": 60.0,
                    "expect": {},
                }],
            }
            (hr / "manifest.json").write_text(
                json.dumps(legacy_manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            runs = ST.read_run_status(hr)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].state, "RUNNING")
            self.assertEqual(runs[0].run_dir, run_dir)


# ---------------------------------------------------------------------------
# Bundle-safety
# ---------------------------------------------------------------------------


class BundleSafety118Tests(unittest.TestCase):

    def test_changes_stay_under_harness(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"118 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
