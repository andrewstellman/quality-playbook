"""Tests for the regression-replay apparatus (v1.5.4 Phase 5).

Coverage:
- BUGS.md parser handles both v1.3-era (`- **Requirement:**`) and
  v1.5-era (`- Primary requirement:`) field shapes
- File-citation parser strips line ranges and reduces to basename
- Recall calculator handles perfect-match, partial-match,
  zero-current, zero-historical, and missing-fields cases
- Cell-record builder populates every SCHEMA.md-required field
- write_cell follows the SCHEMA.md path convention
- The CLI's measurement-only mode produces a valid cell.json against
  the chi-1.3.45 archive end-to-end (the Phase 5 smoke deliverable)
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import regression_replay as rr


REPO_ROOT = Path(__file__).resolve().parents[2]
CHI_1_3_45_BUGS = REPO_ROOT / "repos" / "archive" / "chi-1.3.45" / "quality" / "BUGS.md"
CHI_1_3_46_BUGS = REPO_ROOT / "repos" / "archive" / "chi-1.3.46" / "quality" / "BUGS.md"
CHI_1_5_1_BUGS = REPO_ROOT / "repos" / "archive" / "chi-1.5.1" / "quality" / "BUGS.md"
VIRTIO_1_3_13_BUGS = REPO_ROOT / "repos" / "archive" / "virtio-1.3.13" / "quality" / "BUGS.md"
BUS_TRACKER_1_5_0_BUGS = REPO_ROOT / "repos" / "bus-tracker-1.5.0" / "quality" / "BUGS.md"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class BugsMdParserTests(unittest.TestCase):

    def test_parses_v13_era_bold_field_shape(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "BUGS.md"
            _write(
                p,
                "### BUG-001: Title one\n"
                "- **Requirement:** REQ-009\n"
                "- **File:** `middleware/compress.go:218-220,240-245`\n"
                "- **Severity:** High\n"
                "\n"
                "### BUG-002: Title two\n"
                "- **Requirement:** REQ-013\n"
                "- **File:** `middleware/route_headers.go:85-92`\n",
            )
            recs = rr.parse_bugs_md(p)
            self.assertEqual(len(recs), 2)
            self.assertEqual(recs[0].bug_id, "BUG-001")
            self.assertEqual(recs[0].requirement, "REQ-009")
            self.assertEqual(recs[0].primary_file, "compress.go")
            self.assertEqual(recs[1].requirement, "REQ-013")
            self.assertEqual(recs[1].primary_file, "route_headers.go")

    def test_parses_v15_era_plain_field_shape(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "BUGS.md"
            _write(
                p,
                "### BUG-001: Title\n"
                "- Source: Phase 3 review\n"
                "- File:line: `middleware/compress.go:214-246`\n"
                "- Primary requirement: REQ-007\n"
                "- Severity: MEDIUM\n",
            )
            recs = rr.parse_bugs_md(p)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0].requirement, "REQ-007")
            self.assertEqual(recs[0].primary_file, "compress.go")

    def test_strips_line_ranges_from_multifile_citation(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "BUGS.md"
            _write(
                p,
                "### BUG-001: Multi-file\n"
                "- Primary requirement: REQ-005\n"
                "- File:line: `mux.go:127-133`, `mux.go:368-371`\n",
            )
            recs = rr.parse_bugs_md(p)
            # Multi-file citation; primary_file is the FIRST file's basename.
            self.assertEqual(recs[0].primary_file, "mux.go")

    def test_records_with_missing_fields_have_no_match_key(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "BUGS.md"
            _write(
                p,
                "### BUG-001: Bare heading only\n"
                "Some prose, no fields.\n",
            )
            recs = rr.parse_bugs_md(p)
            self.assertIsNone(recs[0].requirement)
            self.assertIsNone(recs[0].primary_file)
            self.assertIsNone(recs[0].match_key)

    def test_missing_file_raises_filenotfounderror(self) -> None:
        with self.assertRaises(FileNotFoundError):
            rr.parse_bugs_md(Path("/nonexistent/BUGS.md"))


class StripLinesTests(unittest.TestCase):

    def test_simple_path_with_line_range(self) -> None:
        self.assertEqual(
            rr._strip_lines("middleware/compress.go:218-220,240-245"),
            "middleware/compress.go",
        )

    def test_multi_file_takes_first(self) -> None:
        self.assertEqual(
            rr._strip_lines("mux.go:127-133`, `mux.go:368-371"),
            "mux.go",
        )

    def test_path_with_no_line_range_passes_through(self) -> None:
        self.assertEqual(
            rr._strip_lines("middleware/route_headers.go"),
            "middleware/route_headers.go",
        )


class RecallMeasurementTests(unittest.TestCase):

    def _rec(self, bug_id: str, req: str, basename: str) -> rr.BugRecord:
        return rr.BugRecord(
            bug_id=bug_id,
            title=f"title for {bug_id}",
            requirement=req,
            primary_file=basename,
            raw_file_field=basename,
        )

    def test_perfect_recall_when_self_matched(self) -> None:
        bugs = [self._rec("BUG-001", "REQ-001", "a.go"),
                self._rec("BUG-002", "REQ-002", "b.go")]
        m = rr.measure_recall(bugs, bugs)
        self.assertEqual(m.recall, 1.0)
        self.assertEqual(m.recovered_ids, ["BUG-001", "BUG-002"])
        self.assertEqual(m.missed_ids, [])
        self.assertEqual(m.spurious_ids, [])

    def test_partial_recall(self) -> None:
        historical = [self._rec("BUG-001", "REQ-001", "a.go"),
                      self._rec("BUG-002", "REQ-002", "b.go"),
                      self._rec("BUG-003", "REQ-003", "c.go")]
        # Current finds REQ-001 and REQ-003 plus one new bug.
        current = [self._rec("BUG-007", "REQ-001", "a.go"),
                   self._rec("BUG-008", "REQ-003", "c.go"),
                   self._rec("BUG-009", "REQ-099", "z.go")]
        m = rr.measure_recall(historical, current)
        self.assertAlmostEqual(m.recall, 2 / 3)
        self.assertEqual(m.recovered_ids, ["BUG-001", "BUG-003"])
        self.assertEqual(m.missed_ids, ["BUG-002"])
        self.assertEqual(m.spurious_ids, ["BUG-009"])

    def test_id_renumbering_does_not_affect_match(self) -> None:
        """Critical contract: BUG-NNN IDs are renumbered between runs;
        match identity is (REQ, file basename), not the ID."""
        historical = [self._rec("BUG-001", "REQ-005", "mux.go")]
        current = [self._rec("BUG-042", "REQ-005", "mux.go")]
        m = rr.measure_recall(historical, current)
        self.assertEqual(m.recall, 1.0)
        self.assertEqual(m.recovered_ids, ["BUG-001"])
        self.assertEqual(m.spurious_ids, [])

    def test_zero_historical_returns_zero_recall(self) -> None:
        m = rr.measure_recall([], [self._rec("BUG-001", "REQ-001", "a.go")])
        self.assertEqual(m.recall, 0.0)
        self.assertEqual(m.recovered_ids, [])
        self.assertEqual(m.spurious_ids, ["BUG-001"])

    def test_zero_current_returns_zero_recall(self) -> None:
        historical = [self._rec("BUG-001", "REQ-001", "a.go")]
        m = rr.measure_recall(historical, [])
        self.assertEqual(m.recall, 0.0)
        self.assertEqual(m.missed_ids, ["BUG-001"])

    def test_records_with_no_match_key_are_treated_as_unmatched(self) -> None:
        historical = [rr.BugRecord("BUG-001", "?", None, None, None)]
        current = [rr.BugRecord("BUG-002", "?", None, None, None)]
        m = rr.measure_recall(historical, current)
        # Neither side matches anything.
        self.assertEqual(m.recall, 0.0)
        self.assertEqual(m.recovered_ids, [])
        # The current bug has no key, so it falls into spurious.
        self.assertEqual(m.spurious_ids, ["BUG-002"])


class CellRecordBuilderTests(unittest.TestCase):
    """Every SCHEMA.md-required field must appear in the built cell."""

    REQUIRED_TOP_FIELDS = (
        "schema_version",
        "timestamp",
        "benchmark",
        "qpb_version_under_test",
        "historical_qpb_version",
        "historical_bug_id",
        "historical_bug_count",
        "current_bug_count",
        "current_bug_ids",
        "recovered_bug_ids",
        "missed_bug_ids",
        "spurious_bug_ids",
        "recall_against_historical",
        "lever_under_test",
        "lever_change_summary",
        "before_lever",
        "after_lever",
        "regression_check",
        "noise_floor_source",
        "apparatus",
        "notes",
    )

    REQUIRED_REGRESSION_CHECK_FIELDS = (
        "status", "checked_cells", "regressed_cells", "noise_floor_threshold"
    )

    REQUIRED_APPARATUS_FIELDS = (
        "qpb_commit_sha", "target_commit_sha", "phase_scope",
        "iteration_strategies", "runner", "model", "wall_clock_seconds",
    )

    def _build(self) -> dict:
        bugs = [
            rr.BugRecord("BUG-001", "t", "REQ-001", "a.go", "a.go:1-2"),
            rr.BugRecord("BUG-002", "t", "REQ-002", "b.go", "b.go:1-2"),
        ]
        m = rr.measure_recall(bugs, bugs)
        with TemporaryDirectory() as tmp:
            inputs = rr.CellInputs(
                benchmark="chi",
                historical_qpb_version="1.3.45",
                historical_bug_id="all",
                historical_path=Path(tmp) / "h.md",
                current_path=Path(tmp) / "c.md",
                target_dir=None,
                qpb_dir=Path(tmp),
            )
            return rr.build_cell_record(inputs, m)

    def test_every_top_level_field_present(self) -> None:
        rec = self._build()
        for field in self.REQUIRED_TOP_FIELDS:
            self.assertIn(field, rec, f"missing {field!r}")

    def test_regression_check_subfields_present(self) -> None:
        rec = self._build()
        for field in self.REQUIRED_REGRESSION_CHECK_FIELDS:
            self.assertIn(field, rec["regression_check"])

    def test_apparatus_subfields_present(self) -> None:
        rec = self._build()
        for field in self.REQUIRED_APPARATUS_FIELDS:
            self.assertIn(field, rec["apparatus"])

    def test_recall_in_cell_matches_measurement(self) -> None:
        rec = self._build()
        self.assertEqual(rec["recall_against_historical"], 1.0)
        self.assertEqual(rec["recovered_bug_ids"], ["BUG-001", "BUG-002"])

    def test_schema_version_is_v154(self) -> None:
        self.assertEqual(self._build()["schema_version"], "1.5.4")


class WriteCellTests(unittest.TestCase):

    def test_path_convention_followed(self) -> None:
        record = {
            "schema_version": "1.5.4",
            "benchmark": "chi",
            "historical_qpb_version": "1.3.45",
            "historical_bug_id": "all",
        }
        with TemporaryDirectory() as tmp:
            out = rr.write_cell(record, Path(tmp), run_timestamp="20260501T120000Z")
            self.assertEqual(
                out,
                Path(tmp) / "20260501T120000Z" / "chi-1.3.45-all.json",
            )
            self.assertTrue(out.is_file())
            on_disk = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["benchmark"], "chi")

    def test_per_bug_filename_uses_bug_id(self) -> None:
        record = {
            "schema_version": "1.5.4",
            "benchmark": "virtio",
            "historical_qpb_version": "1.3.50",
            "historical_bug_id": "BUG-007",
        }
        with TemporaryDirectory() as tmp:
            out = rr.write_cell(record, Path(tmp), run_timestamp="20260501T120000Z")
            self.assertEqual(out.name, "virtio-1.3.50-BUG-007.json")


class CorpusRealFileParserTests(unittest.TestCase):
    """Council Round 1 + Round 2 2026-04-30 P0-1 / P0-3 regression pin:
    parse against the actual benchmark archive corpus, not synthetic
    fixtures.

    Methodology lesson from two consecutive Council reviews:
    ``synthetic-fixture coverage masked the real-input failure``.
    Round 1's gap was bold-key field variants and the bare-heading
    case (chi-1.5.1, bus-tracker-1.5.0). Round 2's gap was H2
    headings (chi-1.3.46 + 14 other archive files) — the Round 1
    fix-up's fixture set was the right shape but didn't enumerate
    every distinct heading depth in ``repos/archive/``.

    **Discipline for adding new fixtures.** Before writing a new
    fixture-from-memory, run something like

        find repos/archive -name BUGS.md -exec head -1 {} \\;

    to surface every distinct file shape in the corpus. As of
    2026-05-01 the corpus uses two heading depths:
    - H3 (``### BUG-NNN``): 56 files, both v1.3-era bold-key
      (chi-1.3.45) and v1.5-era plain-key / bold-key
      (chi-1.5.1, bus-tracker-1.5.0).
    - H2 (``## BUG-NNN``): 15 files, all v1.3-era
      (chi-1.3.13/14/15/16/46, express-1.3.14/15/16/21/25,
      virtio-1.3.13/18/19/21-manual/22).

    H1 (``# BUG-NNN``) is unused in the corpus — the H1-negative
    test below pins this so a future regex over-broadening to
    ``^#+`` doesn't silently false-positive on documentation
    headings."""

    def test_chi_1_5_1_archive_parses_with_match_keys(self) -> None:
        """Empirical reproduction of P0-1 claim 1: chi-1.5.1's bare
        ``### BUG-NNN`` headings (no colon, no inline title)."""
        if not CHI_1_5_1_BUGS.is_file():
            self.skipTest(f"missing {CHI_1_5_1_BUGS}")
        recs = rr.parse_bugs_md(CHI_1_5_1_BUGS)
        # The chi-1.5.1 archive carries 9 confirmed bugs.
        self.assertEqual(len(recs), 9, "chi-1.5.1 record count drift")
        keyed = [r for r in recs if r.match_key is not None]
        self.assertEqual(
            len(keyed), 9,
            "every chi-1.5.1 record must have a match_key — bold/plain "
            "field variants must all be recognized"
        )

    def test_bus_tracker_1_5_0_bold_key_variants_recognized(self) -> None:
        """Empirical reproduction of P0-1 claims 2 and 3:
        bus-tracker-1.5.0 uses bold-key Primary requirement / Location
        variants. Removing either bold variant from the regex set
        drops match_key counts to zero."""
        if not BUS_TRACKER_1_5_0_BUGS.is_file():
            self.skipTest(f"missing {BUS_TRACKER_1_5_0_BUGS}")
        recs = rr.parse_bugs_md(BUS_TRACKER_1_5_0_BUGS)
        self.assertEqual(len(recs), 18, "bus-tracker-1.5.0 record count drift")
        keyed = [r for r in recs if r.match_key is not None]
        self.assertEqual(
            len(keyed), 18,
            "every bus-tracker-1.5.0 record must have a match_key — "
            "bold-key Primary requirement / Location variants must work"
        )
        # Spot-check first record's normalized fields.
        self.assertEqual(recs[0].requirement, "REQ-004")
        self.assertEqual(recs[0].primary_file, "bus_tracker.py")

    def test_chi_1_3_45_legacy_bold_key_still_works(self) -> None:
        """Cross-check: the v1.3-era ``- **Requirement:** /
        - **File:**`` shape that worked before P0-1 fix must still
        parse — the bold-key additions for v1.5 must NOT regress
        v1.3 coverage."""
        if not CHI_1_3_45_BUGS.is_file():
            self.skipTest(f"missing {CHI_1_3_45_BUGS}")
        recs = rr.parse_bugs_md(CHI_1_3_45_BUGS)
        self.assertEqual(len(recs), 10)
        self.assertTrue(all(r.match_key is not None for r in recs))

    def test_chi_1_3_46_h2_archive_parses(self) -> None:
        """Council Round 2 P0-3: chi-1.3.46 uses H2 ``## BUG-NNN:``
        headings; the Round 1 fix-up's ``^###`` pin missed it,
        producing 0 records when the real recall is 3. The Round 2
        fix loosens the heading regex to accept any depth >=2.

        Also pins the ``**File:Line:**`` (capital-L) variant added
        for chi-1.3.46 / virtio-1.3.13 — without it, primary_file
        stays None even with the heading fix.

        Note: chi-1.3.46 records do NOT carry a structured
        Requirement field (the REQ is embedded inline in the
        ``**Source:**`` field). match_key is therefore None for
        these records — that's correct apparatus reporting (the
        data IS missing); recovering inline-prose REQs would be a
        separate parser change beyond P0-3's scope."""
        if not CHI_1_3_46_BUGS.is_file():
            self.skipTest(f"missing {CHI_1_3_46_BUGS}")
        recs = rr.parse_bugs_md(CHI_1_3_46_BUGS)
        self.assertEqual(
            len(recs), 3,
            "Council Round 2 P0-3 pin: chi-1.3.46 must parse to 3 "
            "records (was 0 with the H3-only regex)."
        )
        # Primary file extraction must work via the **File:Line:**
        # bold-key variant added in P0-3.
        files = [r.primary_file for r in recs]
        self.assertEqual(
            len([f for f in files if f]), 3,
            "all 3 chi-1.3.46 records must have primary_file extracted "
            "via the **File:Line:** capital-L variant"
        )
        # Spot-check the first record matches Council Round 2's
        # documented expectation.
        self.assertEqual(recs[0].bug_id, "BUG-001")
        self.assertEqual(recs[0].primary_file, "compress.go")

    def test_virtio_1_3_13_h2_archive_parses(self) -> None:
        """Council Round 2 P0-3: at least one express/virtio H2
        archive must be in the fixture set per the Council's
        explicit recommendation. virtio-1.3.13 uses
        ``## BUG-NNN: title`` with bold-key ``**File:Line:**`` —
        same shape family as chi-1.3.46."""
        if not VIRTIO_1_3_13_BUGS.is_file():
            self.skipTest(f"missing {VIRTIO_1_3_13_BUGS}")
        recs = rr.parse_bugs_md(VIRTIO_1_3_13_BUGS)
        self.assertGreaterEqual(len(recs), 1)
        # File extraction works via **File:Line:** variant.
        self.assertEqual(recs[0].bug_id, "BUG-001")
        self.assertEqual(recs[0].primary_file, "virtio_mmio.c")

    def test_h1_headings_do_not_false_positive(self) -> None:
        """Council Round 2 P0-3 explicit caution: ``# BUG-001`` (H1)
        must NOT match the heading regex — it could appear in
        documentation outlines or wishlists. The current corpus uses
        only H2/H3, so widening to ``^#+`` would over-broaden.

        Mutation contract: changing the regex to ``^#+`` makes this
        test fail because the synthetic H1 fixture would then match."""
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "BUGS.md"
            _write(
                p,
                "# BUG-001: This is a heading-1 outline marker, NOT a bug record\n"
                "\n"
                "## BUG-001: Real H2 bug record\n"
                "- **Source:** Code Review\n"
                "- **File:Line:** `foo.go:1-2`\n",
            )
            recs = rr.parse_bugs_md(p)
            # Exactly one record: the H2 one. The H1 outline must be
            # silently rejected.
            self.assertEqual(
                len(recs), 1,
                "H1 `# BUG-NNN` headings must not match — they appear "
                "in outlines/wishlists and would false-positive."
            )


class SmokeTestAgainstChi1345Archive(unittest.TestCase):
    """Phase 5 deliverable: end-to-end run against the chi-1.3.45
    archive. Uses measurement-only mode (the historical baseline IS
    the "current" bug set) so the smoke run is instant and produces
    a perfect-recall cell — useful only as proof the apparatus
    plumbing works end-to-end. Real calibration cycles in Phase 6+
    use a separate "current" path produced by an actual QPB run."""

    def setUp(self) -> None:
        if not CHI_1_3_45_BUGS.is_file():
            self.skipTest(
                f"chi-1.3.45 archive not present at {CHI_1_3_45_BUGS}"
            )

    def test_full_set_recall_against_historical_baseline_is_perfect(self) -> None:
        recs = rr.parse_bugs_md(CHI_1_3_45_BUGS)
        # The chi-1.3.45 archive carries 10 confirmed bugs.
        self.assertEqual(len(recs), 10)
        m = rr.measure_recall(recs, recs)
        self.assertEqual(m.recall, 1.0)
        self.assertEqual(len(m.recovered_ids), 10)

    def test_cli_smoke_run_writes_valid_cell(self) -> None:
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            argv = [
                "--benchmark", "chi",
                "--historical-version", "1.3.45",
                "--historical-bugs", str(CHI_1_3_45_BUGS),
                "--current-bugs", str(CHI_1_3_45_BUGS),
                "--bug-id", "all",
                "--output-dir", str(output_dir),
                "--run-timestamp", "20260501T000000Z",
                "--notes", "Phase 5 smoke test cell.",
            ]
            rc = rr.main(argv)
            self.assertEqual(rc, 0)
            cell_path = output_dir / "20260501T000000Z" / "chi-1.3.45-all.json"
            self.assertTrue(cell_path.is_file())
            cell = json.loads(cell_path.read_text(encoding="utf-8"))
            # Smoke contract: every required SCHEMA.md field appears,
            # recall is 1.0 (self-match), and the schema_version is v1.5.4.
            self.assertEqual(cell["schema_version"], "1.5.4")
            self.assertEqual(cell["benchmark"], "chi")
            self.assertEqual(cell["historical_qpb_version"], "1.3.45")
            self.assertEqual(cell["historical_bug_id"], "all")
            self.assertEqual(cell["historical_bug_count"], 10)
            self.assertEqual(cell["current_bug_count"], 10)
            self.assertEqual(cell["recall_against_historical"], 1.0)
            self.assertEqual(len(cell["recovered_bug_ids"]), 10)
            self.assertEqual(cell["missed_bug_ids"], [])


class CliValidationTests(unittest.TestCase):
    """Council 2026-04-30 P1-1: --runner argparse validation must
    reject typos rather than silently dispatching to the default
    --copilot fallback."""

    def test_runner_typo_rejected_by_argparse(self) -> None:
        parser = rr._build_parser()
        # argparse calls sys.exit(2) on choices= violation.
        with self.assertRaises(SystemExit):
            parser.parse_args([
                "--benchmark", "chi",
                "--historical-version", "1.3.45",
                "--historical-bugs", "/tmp/h.md",
                "--current-bugs", "/tmp/c.md",
                "--runner", "cursr",  # typo
            ])

    def test_all_four_supported_runners_accepted(self) -> None:
        parser = rr._build_parser()
        for runner in ("claude", "copilot", "codex", "cursor"):
            args = parser.parse_args([
                "--benchmark", "chi",
                "--historical-version", "1.3.45",
                "--historical-bugs", "/tmp/h.md",
                "--current-bugs", "/tmp/c.md",
                "--runner", runner,
            ])
            self.assertEqual(args.runner, runner)


class InvokeRunnerExitCodeTests(unittest.TestCase):
    """Council 2026-04-30 P1-2: a non-zero runner exit must abort the
    cell write rather than producing a cell against a stale BUGS.md."""

    def test_invoke_runner_returns_returncode(self) -> None:
        from unittest import mock
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=42)
            result = rr._invoke_runner(
                Path("/tmp/target"), "1,2,3", "claude", ""
            )
        self.assertEqual(result.returncode, 42)
        self.assertIsInstance(result.wall_clock_seconds, int)

    def test_main_aborts_on_runner_failure(self) -> None:
        from unittest import mock
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            (target / "quality").mkdir(parents=True)
            (target / "quality" / "BUGS.md").write_text(
                "### BUG-001: existing\n- **Requirement:** REQ-1\n- **File:** `a.go:1`\n",
                encoding="utf-8",
            )
            output_dir = Path(tmp) / "out"
            with mock.patch.object(rr, "_invoke_runner") as mock_inv:
                mock_inv.return_value = rr.RunnerInvocationResult(
                    returncode=99, wall_clock_seconds=5
                )
                rc = rr.main([
                    "--benchmark", "chi",
                    "--historical-version", "1.3.45",
                    "--historical-bugs", str(target / "quality" / "BUGS.md"),
                    "--target-dir", str(target),
                    "--invoke-runner",
                    "--output-dir", str(output_dir),
                ])
            # Should propagate the non-zero exit, not return 0.
            self.assertEqual(rc, 99)
            # No cell written.
            self.assertFalse(list(output_dir.rglob("*.json")))


class ReplayModeOrderOfOperationsTests(unittest.TestCase):
    """Phase 6 prep / F-N regression pin: in replay mode, the
    historical baseline must be parsed BEFORE _invoke_runner is
    called, never after.

    Failure mode: when --historical-bugs points at the target's own
    pre-existing BUGS.md (the natural case for an archive that IS
    its own ground truth — every chi-1.3.x cycle works this way),
    the runner's startup archives target/quality/ → previous_runs/.
    A read AFTER the runner finds the file moved out from under it
    and raises FileNotFoundError, aborting the cell write before
    measurement is captured.

    Mutation contract: swapping the parse_bugs_md(historical) call
    back below the _invoke_runner call trips this test."""

    def test_historical_parsed_before_runner_archives_target(self) -> None:
        """Pin that the historical baseline carries the PRE-RUN
        match key, not the POST-RUN match key.

        The fixture sets up a divergent recall scenario:
        - Pre-run BUGS.md: BUG-001 / REQ-001 / foo.go  (the truth)
        - Post-run BUGS.md (what the mocked runner writes): BUG-042 /
          REQ-099 / unrelated.go  (current run found something else)

        With the fix in place (historical parsed BEFORE invoke):
        recall = 0/1 (the current run did not recover REQ-001/foo.go).
        Without the fix (historical parsed AFTER invoke): recall =
        1/1 because the apparatus reads the same post-runner file as
        BOTH historical and current — silent 100%-recall false
        positive that would corrupt every calibration cycle's data."""
        from unittest import mock
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            quality = target / "quality"
            quality.mkdir(parents=True)
            historical = quality / "BUGS.md"
            _write(
                historical,
                "### BUG-001: pre-run truth\n"
                "- **Requirement:** REQ-001\n"
                "- **File:** `foo.go:1-2`\n",
            )
            output_dir = Path(tmp) / "out"

            archived_dir = quality / "previous_runs" / "20260501T000000Z"
            archived_dir.mkdir(parents=True)
            archived_bugs = archived_dir / "quality" / "BUGS.md"
            archived_bugs.parent.mkdir(parents=True)

            def fake_invoke(target_dir, phase_scope, runner, model):
                # Simulate the runner's Phase 0 archive: the original
                # historical file moves to previous_runs/, and a
                # fresh BUGS.md (with DIFFERENT match key) is written
                # at the target's quality/BUGS.md path.
                historical.rename(archived_bugs)
                _write(
                    historical,
                    "### BUG-042: post-run finding (different match key)\n"
                    "- **Requirement:** REQ-099\n"
                    "- **File:** `unrelated.go:50-55`\n",
                )
                return rr.RunnerInvocationResult(
                    returncode=0, wall_clock_seconds=1
                )

            with mock.patch.object(rr, "_invoke_runner", side_effect=fake_invoke):
                rc = rr.main([
                    "--benchmark", "test",
                    "--historical-version", "1.0.0",
                    "--historical-bugs", str(historical),
                    "--target-dir", str(target),
                    "--invoke-runner",
                    "--output-dir", str(output_dir),
                    "--run-timestamp", "20260501T000001Z",
                ])
            self.assertEqual(rc, 0)
            cell_path = output_dir / "20260501T000001Z" / "test-1.0.0-all.json"
            self.assertTrue(cell_path.is_file())
            cell = json.loads(cell_path.read_text(encoding="utf-8"))
            # Mutation contract: with the fix in place, recall must
            # be 0.0 (historical = REQ-001/foo.go captured pre-run;
            # current = REQ-099/unrelated.go from the post-run file
            # — they don't match). If the order-of-operations
            # regression is reintroduced, both reads pull from the
            # post-run file and recall hits 1.0 — this assertion
            # trips with `1.0 != 0.0`.
            self.assertEqual(
                cell["recall_against_historical"], 0.0,
                "Recall must be 0.0 — the historical baseline must be "
                "captured BEFORE the runner archives the target's "
                "quality/BUGS.md. If recall is 1.0, the apparatus is "
                "reading the post-run file as BOTH historical and "
                "current (silent false-positive). The fix is "
                "`historical = parse_bugs_md(args.historical_bugs)` "
                "BEFORE `_invoke_runner`, never after."
            )
            # Sanity: the historical bug ID landed in missed_bug_ids.
            self.assertEqual(cell["missed_bug_ids"], ["BUG-001"])
            # Sanity: the post-run finding landed in spurious_bug_ids.
            self.assertEqual(cell["spurious_bug_ids"], ["BUG-042"])


class QpbVersionFieldSourceTests(unittest.TestCase):
    """Council 2026-04-30 P2-1: qpb_version_under_test must come from
    bin/benchmark_lib.RELEASE_VERSION per SCHEMA.md, not from
    SKILL.md via detect_skill_version (separate source of truth)."""

    def test_cell_record_qpb_version_matches_release_version(self) -> None:
        from bin import benchmark_lib
        with TemporaryDirectory() as tmp:
            inputs = rr.CellInputs(
                benchmark="chi",
                historical_qpb_version="1.3.45",
                historical_bug_id="all",
                historical_path=Path(tmp) / "h.md",
                current_path=Path(tmp) / "c.md",
                target_dir=None,
                qpb_dir=Path(tmp),  # empty dir → no SKILL.md visible
            )
            measurement = rr.measure_recall([], [])
            record = rr.build_cell_record(inputs, measurement)
        self.assertEqual(
            record["qpb_version_under_test"],
            benchmark_lib.RELEASE_VERSION,
            "qpb_version_under_test must come from RELEASE_VERSION "
            "(SCHEMA.md contract), not detect_skill_version fallbacks",
        )


if __name__ == "__main__":
    unittest.main()
