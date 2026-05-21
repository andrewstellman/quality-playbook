"""Tests for bin/visualize_calibration.py.

Light coverage — the script's job is to produce four PNG/Mermaid
artifacts from real cycle data. The load-bearing test runs against
the v1.5.4 cycle 1 fixture (chi-1.3.45) and verifies all four
artifacts appear with non-zero size. Pure-helper tests cover the
log-parsing and recall-extraction utilities.

matplotlib + numpy are runtime requirements of visualize_calibration
itself but not of QPB's core. Tests skip cleanly when either is
unavailable so that the global suite still passes on a system Python
without those packages installed.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    import matplotlib  # noqa: F401  (existence check)
    import numpy  # noqa: F401
    _HAS_MATPLOTLIB = True
except ImportError:
    _HAS_MATPLOTLIB = False


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKSPACE_ROOT = (
    Path.home() / "Documents" / "AI-Driven Development" / "Quality Playbook"
)
CYCLE_1_DIR = WORKSPACE_ROOT / "Calibration Cycles" / "2026-05-01-chi-1.3.45"


class HelperParserTests(unittest.TestCase):
    """Pure-Python helpers — no matplotlib needed."""

    def test_extract_recall_handles_fraction_and_percent(self) -> None:
        from bin import visualize_calibration as vc

        self.assertAlmostEqual(vc._extract_recall("recall = 4/10 = 40%"), 0.4)
        self.assertAlmostEqual(vc._extract_recall("recall = 8/10"), 0.8)
        self.assertAlmostEqual(vc._extract_recall("100%"), 1.0)
        self.assertIsNone(vc._extract_recall("no number here"))

    def test_extract_recall_returns_none_on_zero_denominator(self) -> None:
        """A 0/0 reading is undefined — return None rather than crash."""
        from bin import visualize_calibration as vc

        self.assertIsNone(vc._extract_recall("0/0"))

    def test_load_lever_log_parses_canonical_log(self) -> None:
        """Sanity check against the real lever log — at least one
        cycle entry must parse with a non-None lever_pulled and a
        recall_before / recall_after pair."""
        from bin import visualize_calibration as vc

        log_path = REPO_ROOT / "docs" / "process" / "Lever_Calibration_Log.md"
        if not log_path.is_file():
            self.skipTest(f"missing {log_path}")
        entries = vc.load_lever_log(log_path)
        self.assertGreater(len(entries), 0)
        # First entry should be the chi-1.3.45 cycle.
        first = entries[0]
        self.assertIn("chi-1.3.45", first["cycle_name"])
        self.assertIsNotNone(first["recall_before"])
        self.assertIsNotNone(first["recall_after"])
        # Pattern 7 was the lever pulled.
        self.assertIn("Pattern 7", first.get("lever_pulled") or "")

    def test_load_historical_bugs_reads_chi_1_3_45_baseline(self) -> None:
        """Spot-check the BUGS.md reader against a real archive.

        v1.5.6 BUG-006: skip cleanly when the chi-1.3.45 archive isn't
        staged in this environment (e.g., a fresh QPB clone where
        setup_repos.sh hasn't been run yet). Pre-fix this test
        intermittently failed because load_historical_bugs() returned
        ``[]`` for a missing archive — `len([]) >= 10` was always
        false. Post-fix the function returns ``None`` for a missing
        archive (caught by the explicit skip below); when the archive
        IS present the assertions still hold."""
        from bin import visualize_calibration as vc

        archive_dir = REPO_ROOT / "repos" / "archive"
        baseline_bugs_md = archive_dir / "chi-1.3.45" / "quality" / "BUGS.md"
        if not baseline_bugs_md.is_file():
            self.skipTest(
                f"chi-1.3.45 baseline archive not present at "
                f"{baseline_bugs_md} — run setup_repos.sh to stage it"
            )

        bugs = vc.load_historical_bugs(archive_dir, "chi-1.3.45")
        # Archive present → returns a list (NOT None).
        self.assertIsNotNone(
            bugs,
            "load_historical_bugs returned None despite the archive "
            "BUGS.md existing on disk — the missing-archive path is "
            "incorrectly triggering."
        )
        # Archive has at least 10 ### BUG- entries (the v1.3.45 baseline).
        self.assertGreaterEqual(len(bugs), 10)
        self.assertIn("BUG-001", bugs)

    def test_load_historical_bugs_returns_none_on_missing_archive(self) -> None:
        """v1.5.6 BUG-006: a missing archive must return None (not [])
        AND emit a WARNING-level log line so the caller can see the
        gap. Pre-fix this case returned an empty list, masking
        'archive missing' as 'archive present but empty'."""
        import logging
        from bin import visualize_calibration as vc

        with TemporaryDirectory() as temp_dir:
            empty_archive = Path(temp_dir)
            with self.assertLogs("bin.visualize_calibration", level=logging.WARNING) as cm:
                result = vc.load_historical_bugs(
                    empty_archive, "definitely-not-a-real-baseline"
                )
            self.assertIsNone(
                result,
                "load_historical_bugs must return None on missing "
                "archive so callers can distinguish 'archive missing' "
                "from 'archive present but empty'."
            )
            joined = "\n".join(cm.output)
            self.assertIn(
                "missing archive", joined,
                "missing-archive case must log a WARNING with the "
                "missing path so operators can see the gap.",
            )
            self.assertIn(
                "definitely-not-a-real-baseline", joined,
                "missing-archive log line must include the failed path "
                "for diagnosability.",
            )

    @unittest.skipUnless(sys.version_info >= (3, 10),
                         "assertNoLogs requires Python 3.10+ "
                         "(v1.5.7 089i: QPB's documented runtime "
                         "floor is Python 3.10+; this guard keeps "
                         "the suite green on older interpreters "
                         "while the test itself pins the "
                         "no-log-warning contract on supported "
                         "Pythons).")
    def test_load_historical_bugs_returns_empty_list_when_bugs_md_has_no_headings(self) -> None:
        """v1.5.6 BUG-006: when the archive IS present but BUGS.md
        contains zero parseable BUG- headings (a real "archive
        present but empty" state), the function returns ``[]``
        WITHOUT logging a warning — this is a legitimate state
        distinct from "archive missing"."""
        import logging
        from bin import visualize_calibration as vc

        with TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir)
            bugs_md = archive / "fake-1.0.0" / "quality" / "BUGS.md"
            bugs_md.parent.mkdir(parents=True)
            bugs_md.write_text(
                "# BUGS\n\nNo bugs tracked yet for this baseline.\n",
                encoding="utf-8",
            )
            # No log line should fire for this case.
            logger = logging.getLogger("bin.visualize_calibration")
            previous_level = logger.level
            try:
                logger.setLevel(logging.WARNING)
                with self.assertNoLogs("bin.visualize_calibration", level=logging.WARNING):
                    result = vc.load_historical_bugs(archive, "fake-1.0.0")
            finally:
                logger.setLevel(previous_level)
            self.assertEqual(
                result, [],
                "An archive present with no BUG- headings must return "
                "[] (NOT None) — the empty list is a real state, "
                "not a missing-archive marker."
            )


@unittest.skipUnless(_HAS_MATPLOTLIB, "matplotlib + numpy not installed")
class EndToEndArtifactTests(unittest.TestCase):
    """Run the full ``visualize`` pipeline against a real cycle fixture
    (or a TemporaryDirectory if the v1.5.4 cycle isn't present) and
    verify the four expected artifacts appear with non-zero size."""

    def _assert_four_artifacts(self, out_dir: Path) -> None:
        expected = [
            "per_bug_cycle_heatmap.png",
            "lever_benchmark_heatmap.png",
            "recall_trajectory.png",
            "lever_interaction.mermaid",
        ]
        for name in expected:
            path = out_dir / name
            self.assertTrue(path.is_file(), f"missing artifact: {path}")
            self.assertGreater(
                path.stat().st_size, 0, f"empty artifact: {path}"
            )

    def test_renders_all_four_artifacts_against_v154_cycle(self) -> None:
        """Load-bearing: produces meaningful charts against real data
        (the v1.5.4 chi-1.3.45 cycle data committed to the repo)."""
        if not CYCLE_1_DIR.is_dir():
            self.skipTest(f"missing fixture cycle: {CYCLE_1_DIR}")
        from bin import visualize_calibration as vc

        artifacts = vc.visualize(CYCLE_1_DIR)
        self.assertGreaterEqual(len(artifacts), 4)
        self._assert_four_artifacts(CYCLE_1_DIR / "visualizations")
        # Per-bug heatmap should be a substantial image (not the
        # 'no data' placeholder which is ~5KB). The real chart with
        # 10+ rows × 1 cycle is comfortably above 10KB at 120 dpi.
        size = (CYCLE_1_DIR / "visualizations" / "per_bug_cycle_heatmap.png").stat().st_size
        self.assertGreater(
            size, 10_000,
            f"per-bug heatmap suspiciously small ({size} bytes) — "
            f"may have rendered the 'no data' placeholder.",
        )

    def test_renders_placeholders_with_no_input_data(self) -> None:
        """When no metrics/cells are available, the script still
        produces all four files (placeholders rather than crashes)."""
        from bin import visualize_calibration as vc

        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            cycle_dir = tmp / "Calibration Cycles" / "test-cycle"
            cycle_dir.mkdir(parents=True)
            # Pass a workspace_root that exists but contains no cycles
            # data; the script will still try to read cells from
            # REPO_ROOT/metrics. Both code paths exercise load helpers
            # against missing/empty inputs.
            artifacts = vc.visualize(cycle_dir, workspace_root=tmp)
            self.assertGreaterEqual(len(artifacts), 4)
            self._assert_four_artifacts(cycle_dir / "visualizations")


if __name__ == "__main__":
    unittest.main()
