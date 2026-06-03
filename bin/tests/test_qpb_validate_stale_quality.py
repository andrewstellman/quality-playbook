"""v1.5.7 instruction 084 (A-20 reframed) regression tests.

Sibling file, consistent with the existing test_qpb_validate_*
split (remediation_commands / platform_detection / etc.).
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from bin import qpb_validate as v


class StaleQualityDirTests(unittest.TestCase):
    """v1.5.7 instruction 084 (A-20 reframed): the validator emits a
    `stale_quality_dir` blocked finding when <target>/quality/ contains
    files but no active-run marker. Agents observe and halt rather than
    treating stale artifacts as resumable work.

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED:
      Mutation: change severity from "blocked" to "remediable" in
        FINDING_CATALOG['stale_quality_dir'].
      Observed failure (purged __pycache__ first):
        FAIL: test_stale_quality_dir_severity_is_blocked
        AssertionError: 'remediable' != 'blocked'
      Mutation reverted; tests pass.
    """

    def test_stale_quality_dir_severity_is_blocked(self) -> None:
        self.assertEqual(
            v.FINDING_CATALOG["stale_quality_dir"]["severity"], "blocked")

    def test_check_stale_quality_dir_empty_dir_no_finding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / "quality").mkdir()
            self.assertEqual(v.check_stale_quality_dir(target), [])

    def test_check_stale_quality_dir_with_content_emits_finding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            qdir = target / "quality"
            qdir.mkdir()
            (qdir / "BUGS.md").write_text("stale content from prior run")
            findings = v.check_stale_quality_dir(target)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["code"], "stale_quality_dir")

    def test_check_stale_quality_dir_with_recent_run_start_no_finding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            qdir = target / "quality"
            qdir.mkdir()
            (qdir / "BUGS.md").write_text("active run content")
            now_iso = datetime.now(timezone.utc).isoformat()
            (qdir / "run_state.jsonl").write_text(
                f'{{"event": "run_start", "ts": "{now_iso}"}}\n'
            )
            self.assertEqual(v.check_stale_quality_dir(target), [])


if __name__ == "__main__":
    unittest.main()
