"""Tests for bin/quality_playbook.py (operator entry-point shim)."""

from __future__ import annotations

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import quality_playbook


class QualityPlaybookShimTests(unittest.TestCase):
    def test_no_args_prints_purpose_banner_and_exits_0(self) -> None:
        """v1.5.7 089x: no-args is purpose-banner-safe. Pre-089x,
        bare invocation exited 1 with a "usage" stub listing
        subcommands; 089x replaces that with the universal
        purpose-banner contract (every bin/*.py prints
        `Quality Playbook v<ver>` + `Role in a playbook run:` +
        the attribution footer and exits 0)."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = quality_playbook.main([])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("Quality Playbook v", out)
        self.assertIn("Role in a playbook run:", out)
        self.assertIn("by Andrew Stellman", out)

    def test_help_flag_exits_0(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = quality_playbook.main(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("subcommand", buf.getvalue())

    def test_unknown_subcommand_errors(self) -> None:
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = quality_playbook.main(["nonsense"])
        self.assertEqual(rc, 1)
        self.assertIn("unknown subcommand", buf.getvalue())

    def test_archive_dispatches_to_archive_lib(self) -> None:
        """`quality_playbook archive` is a thin wrapper over archive_lib.main."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "quality").mkdir()
            (repo / "quality" / "BUGS.md").write_text("bug", encoding="utf-8")
            # Redirect stderr so the test doesn't leak the archive log line.
            buf_out = io.StringIO()
            with redirect_stdout(buf_out):
                rc = quality_playbook.main(
                    ["archive", str(repo), "--status", "partial",
                     "--timestamp", "20260419T143022Z"]
                )
            self.assertEqual(rc, 0, buf_out.getvalue())
            # v1.5.4 Phase 3.6.2: previous_runs/<TS>/ + .partial sentinel.
            archive = repo / "quality" / "previous_runs" / "20260419T143022Z"
            self.assertTrue(archive.is_dir())
            self.assertTrue((archive / "INDEX.md").is_file())
            self.assertTrue((archive / ".partial").is_file())

    def test_migrate_dispatches_to_migration_script(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "control_prompts").mkdir()
            (repo / "control_prompts" / "phase1.output.txt").write_text("prompt")
            buf_out = io.StringIO()
            with redirect_stdout(buf_out):
                rc = quality_playbook.main(["migrate", str(repo)])
            self.assertEqual(rc, 0, buf_out.getvalue())
            self.assertTrue((repo / "quality" / "control_prompts" / "phase1.output.txt").is_file())

    def test_cli_invocation_via_python_m(self) -> None:
        """End-to-end: `python -m bin.quality_playbook --help` runs."""
        result = subprocess.run(
            [sys.executable, "-m", "bin.quality_playbook", "--help"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("archive", result.stdout)


if __name__ == "__main__":
    unittest.main()
