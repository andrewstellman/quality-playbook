"""Regression tests for bin/metrics_reconstruction.py.

v1.5.7 Phase 4 / Deliverable 4 work item D. Five tests covering:

1. Reconstruction idempotence
2. Missing-data handling (corrupted JSON, unreadable cells)
3. Backup-on-write (existing data lands in .backup-<UTC-ts>/)
4. Sub-directory README presence (top-level + 5 sub-directory)
5. v1.7 input-shape compatibility (per QPB_v1.7.0_Design.md)

Each test exercises the production module's public surface — not a
re-statement of the production logic — so reverting an implementation
detail causes the corresponding test to fail.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import metrics_reconstruction as mr


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _make_cell(parent: Path, name: str, bug_ids: list[str]) -> Path:
    """Create a fake repos/<name>/quality/BUGS.md with the given BUG-NNN headings."""
    cell = parent / name
    quality = cell / "quality"
    quality.mkdir(parents=True, exist_ok=True)
    bugs_md = quality / "BUGS.md"
    lines = ["# Confirmed Bugs\n"]
    for bid in bug_ids:
        lines.append(f"\n## {bid}\n")
        lines.append("- placeholder body\n")
        # NOTE: BUGS_HEADING_RE matches `### BUG-NNN`. Use `### BUG-NNN`
        # not `## BUG-NNN` so the regex actually finds these.
    bugs_md.write_text(
        "# Confirmed Bugs\n"
        + "".join(f"\n### {bid}\n- placeholder body\n" for bid in bug_ids),
        encoding="utf-8",
    )
    return cell


def _make_metrics_tree(parent: Path) -> Path:
    """Create an empty metrics/ tree with the documented sub-directories."""
    metrics = parent / "metrics"
    for sub in ("regression_replay", "calibration", "bootstrap_recall",
                "cross_version_trends", "sdlc_defects"):
        (metrics / sub).mkdir(parents=True, exist_ok=True)
    return metrics


class ReconstructionIdempotenceTests(unittest.TestCase):
    """Acceptance criterion 1: same inputs produce same outputs modulo timestamp."""

    def test_two_back_to_back_runs_produce_same_data(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            cells_root = tmp / "repos"
            cells_root.mkdir()
            _make_cell(cells_root, "alpha-1.0", ["BUG-001", "BUG-002", "BUG-003"])
            _make_cell(cells_root, "alpha-1.1", ["BUG-001", "BUG-002"])
            _make_cell(cells_root, "beta-2.0", ["BUG-001"])
            metrics = _make_metrics_tree(tmp)

            rc1 = mr.main([
                "--target", str(metrics),
                "--cells-root", str(cells_root),
                "--quarter", "both",
                "--year", "2026",
            ])
            self.assertEqual(rc1, 0)
            snapshot1 = self._snapshot(metrics)

            rc2 = mr.main([
                "--target", str(metrics),
                "--cells-root", str(cells_root),
                "--quarter", "both",
                "--year", "2026",
            ])
            self.assertEqual(rc2, 0)
            snapshot2 = self._snapshot(metrics)

            # Strip out reconstruction_timestamp + skipped_cells[].path
            # (timestamp varies between calls; absolute paths in skipped
            # cells live under tmp and are stable here but we strip for
            # robustness).
            self.assertEqual(
                self._strip_volatile(snapshot1),
                self._strip_volatile(snapshot2),
                "Two back-to-back reconstruction runs must produce "
                "identical output (modulo reconstruction_timestamp).",
            )

    def _snapshot(self, metrics: Path) -> dict:
        """Return {relpath: parsed-json} for all bootstrap + trends files."""
        out: dict = {}
        for sub in ("bootstrap_recall", "cross_version_trends"):
            sub_dir = metrics / sub
            if not sub_dir.is_dir():
                continue
            for p in sorted(sub_dir.glob("*.json")):
                out[f"{sub}/{p.name}"] = json.loads(p.read_text(encoding="utf-8"))
        return out

    def _strip_volatile(self, snapshot: dict) -> dict:
        """Strip reconstruction_timestamp from each top-level dict."""
        out = {}
        for k, v in snapshot.items():
            v2 = dict(v)
            v2.pop("reconstruction_timestamp", None)
            out[k] = v2
        return out


class MissingDataHandlingTests(unittest.TestCase):
    """Acceptance criterion 2: corrupted/missing data is logged + skipped, not crash."""

    def test_corrupted_regression_replay_cell_is_skipped_not_crash(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            cells_root = tmp / "repos"
            cells_root.mkdir()
            _make_cell(cells_root, "alpha-1.0", ["BUG-001"])
            metrics = _make_metrics_tree(tmp)

            # Plant a corrupted cell.json in regression_replay/
            corrupted_dir = metrics / "regression_replay" / "20260501T120000Z"
            corrupted_dir.mkdir(parents=True)
            (corrupted_dir / "corrupted-1.0-all.json").write_text(
                "{ this is not valid json", encoding="utf-8",
            )
            # And a valid one alongside, to confirm the script keeps going.
            (corrupted_dir / "alpha-1.0-all.json").write_text(
                json.dumps({"timestamp": "2026-05-01T12:00:00Z"}), encoding="utf-8",
            )

            rc = mr.main([
                "--target", str(metrics),
                "--cells-root", str(cells_root),
                "--quarter", "both",
                "--year", "2026",
            ])
            self.assertEqual(rc, 0, "Reconstruction must not crash on corrupted JSON")

            # The Q2 aggregate (2026-05-01 → 2026-Q2) records the skip.
            q2_path = metrics / "bootstrap_recall" / "2026-Q2.json"
            self.assertTrue(q2_path.exists())
            q2 = json.loads(q2_path.read_text(encoding="utf-8"))
            skipped_paths = [s["path"] for s in q2["skipped_cells"]]
            self.assertTrue(
                any("corrupted-1.0-all.json" in p for p in skipped_paths),
                f"Corrupted cell must appear in skipped_cells; got {skipped_paths}",
            )
            # Valid cell counted once in regression_replay_cell_count.
            self.assertEqual(q2["regression_replay_cell_count"], 1)


class BackupOnWriteTests(unittest.TestCase):
    """Acceptance criterion 3: existing data lands in .backup-<UTC-ts>/."""

    def test_existing_aggregate_data_is_backed_up_before_rewrite(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            cells_root = tmp / "repos"
            cells_root.mkdir()
            _make_cell(cells_root, "alpha-1.0", ["BUG-001"])
            metrics = _make_metrics_tree(tmp)

            # Plant an existing aggregate so the next run must back it up.
            preexisting = metrics / "bootstrap_recall" / "2026-Q2.json"
            preexisting.write_text(
                json.dumps({"schema_version": "1.5.7", "marker": "preexisting"}),
                encoding="utf-8",
            )
            preexisting_trend = metrics / "cross_version_trends" / "alpha.json"
            preexisting_trend.write_text(
                json.dumps({"schema_version": "1.5.7", "marker": "preexisting"}),
                encoding="utf-8",
            )

            rc = mr.main([
                "--target", str(metrics),
                "--cells-root", str(cells_root),
                "--quarter", "both",
                "--year", "2026",
            ])
            self.assertEqual(rc, 0)

            # bootstrap_recall/.backup-<ts>/ contains the prior file.
            backup_dirs = sorted((metrics / "bootstrap_recall").glob(".backup-*"))
            self.assertEqual(
                len(backup_dirs), 1,
                f"Expected exactly one bootstrap_recall backup dir, got {backup_dirs}",
            )
            backed_up_q2 = backup_dirs[0] / "2026-Q2.json"
            self.assertTrue(backed_up_q2.exists())
            self.assertEqual(
                json.loads(backed_up_q2.read_text(encoding="utf-8"))["marker"],
                "preexisting",
            )

            # cross_version_trends/.backup-<ts>/ contains the prior trend.
            trend_backups = sorted((metrics / "cross_version_trends").glob(".backup-*"))
            self.assertEqual(len(trend_backups), 1)
            backed_up_alpha = trend_backups[0] / "alpha.json"
            self.assertTrue(backed_up_alpha.exists())

            # New aggregate is in place at the canonical path.
            new_q2 = json.loads((metrics / "bootstrap_recall" / "2026-Q2.json")
                                .read_text(encoding="utf-8"))
            self.assertNotEqual(new_q2.get("marker"), "preexisting",
                                "Old file was not replaced by fresh aggregate")


class SubDirectoryREADMEPresenceTests(unittest.TestCase):
    """Acceptance criterion 4: 6 READMEs exist (1 top-level + 5 sub-directory).

    Asserts against the LIVE repo tree, not a synthetic temp dir —
    this test fails if a future refactor deletes or relocates one of
    the README files.
    """

    def test_top_level_and_five_subdirectory_readmes_exist(self) -> None:
        metrics = REPO_ROOT / "metrics"
        self.assertTrue((metrics / "README.md").is_file(),
                        f"Missing top-level README at {metrics}/README.md")
        for sub in ("regression_replay", "calibration", "bootstrap_recall",
                    "cross_version_trends", "sdlc_defects"):
            readme = metrics / sub / "README.md"
            self.assertTrue(readme.is_file(),
                            f"Missing sub-directory README at {readme}")

    def test_top_level_readme_declares_all_five_subdirectories(self) -> None:
        top = (REPO_ROOT / "metrics" / "README.md").read_text(encoding="utf-8")
        for sub in ("regression_replay", "calibration", "bootstrap_recall",
                    "cross_version_trends", "sdlc_defects"):
            self.assertIn(
                f"{sub}/", top,
                f"Top-level README must mention `{sub}/` sub-directory.",
            )


class V17InputShapeCompatibilityTests(unittest.TestCase):
    """Acceptance criterion 5: output shape is what v1.7 SPC expects.

    Per QPB_v1.7.0_Design.md "Cross-version trend tracking":
    `metrics/cross_version_trends/<benchmark>.json` files carry
    per-benchmark trajectory data. v1.7 reads them as individual-
    observations input for SPC trend charts.

    The schema this test asserts on is documented in
    metrics/cross_version_trends/README.md (which v1.5.7 owns) and
    is forward-compatible with what v1.7's bin/cross_version_trends.py
    will produce.
    """

    def test_cross_version_trends_output_has_required_v17_fields(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            cells_root = tmp / "repos"
            cells_root.mkdir()
            _make_cell(cells_root, "alpha-1.0", ["BUG-001", "BUG-002", "BUG-003"])
            _make_cell(cells_root, "alpha-1.1", ["BUG-001", "BUG-002"])
            _make_cell(cells_root, "alpha-1.2", ["BUG-001"])
            metrics = _make_metrics_tree(tmp)

            rc = mr.main([
                "--target", str(metrics),
                "--cells-root", str(cells_root),
                "--quarter", "both",
                "--year", "2026",
            ])
            self.assertEqual(rc, 0)

            trend_path = metrics / "cross_version_trends" / "alpha.json"
            self.assertTrue(trend_path.exists())
            data = json.loads(trend_path.read_text(encoding="utf-8"))

            # Required top-level fields per the README schema.
            for field in ("schema_version", "reconstruction_timestamp",
                          "qpb_version_at_reconstruction", "benchmark",
                          "ground_truth", "versions_observed",
                          "per_defect_class"):
                self.assertIn(field, data,
                              f"Required field `{field}` missing from cross_version_trends output")

            # ground_truth is the most-detailed historical BUGS.md
            # (highest count, tie-broken by lowest version string).
            self.assertEqual(data["ground_truth"]["version"], "1.0")
            self.assertEqual(data["ground_truth"]["bug_count"], 3)

            # versions_observed is sorted, holds the three versions.
            versions = [v["version"] for v in data["versions_observed"]]
            self.assertEqual(versions, ["1.0", "1.1", "1.2"])
            recalls = [v["recall_against_ground_truth"]
                       for v in data["versions_observed"]]
            self.assertEqual(recalls, [1.0, round(2/3, 4), round(1/3, 4)])

            # per_defect_class is empty (v1.7 populates it; v1.5.7
            # ships the empty array as the forward-compatibility hook).
            self.assertEqual(data["per_defect_class"], [])

    def test_bootstrap_recall_output_has_required_fields(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            cells_root = tmp / "repos"
            cells_root.mkdir()
            _make_cell(cells_root, "alpha-1.0", ["BUG-001"])
            metrics = _make_metrics_tree(tmp)
            rc = mr.main([
                "--target", str(metrics),
                "--cells-root", str(cells_root),
                "--quarter", "both",
                "--year", "2026",
            ])
            self.assertEqual(rc, 0)

            q2_path = metrics / "bootstrap_recall" / "2026-Q2.json"
            self.assertTrue(q2_path.exists())
            data = json.loads(q2_path.read_text(encoding="utf-8"))
            for field in ("schema_version", "reconstruction_timestamp",
                          "quarter", "qpb_version_at_reconstruction",
                          "per_benchmark", "calibration_cycle_count",
                          "regression_replay_cell_count", "skipped_cells"):
                self.assertIn(field, data,
                              f"Required field `{field}` missing from bootstrap_recall output")
            self.assertEqual(data["schema_version"], mr.SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
