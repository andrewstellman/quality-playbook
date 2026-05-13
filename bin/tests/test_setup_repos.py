"""Tests for repos/setup_repos.sh — v1.5.7 fix F-3 backup-by-default.

Pre-fix setup_repos.sh did `rm -rf "$dst"` on an existing destination
repo, eating any preserved diagnostics (notably the D1 gate-failure
sibling dirs that lived OUTSIDE quality/). The fix:

- Default behavior (no --replace): rename existing dst to
  ${dst}.bak-<UTC-ts>/ before the fresh install lands.
- --replace: legacy destructive behavior (rm -rf) — opt-in only.

The tests build a minimal hermetic fixture (tmp_qpb/repos/ with
SKILL.md, references/, clean/<short>/, _benchmark_lib.sh,
setup_repos.sh) and exercise the script via subprocess to verify
backup-vs-replace semantics.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _build_minimal_fixture(qpb_root: Path, short: str = "dummytest", version: str = "1.5.7") -> tuple[Path, Path]:
    """Build a minimal QPB-like layout under qpb_root that setup_repos.sh
    can run against. Returns (script_path, dst_path)."""
    (qpb_root / "SKILL.md").write_text(
        f"---\nversion: {version}\nname: x\ndescription: y\n---\n",
        encoding="utf-8",
    )
    (qpb_root / "references").mkdir()
    (qpb_root / "references" / "x.md").write_text("ref content\n", encoding="utf-8")
    (qpb_root / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    (qpb_root / ".github" / "skills" / "quality_gate").mkdir(parents=True)
    (qpb_root / ".github" / "skills" / "quality_gate" / "quality_gate.py").write_text(
        "# stub\n", encoding="utf-8",
    )
    (qpb_root / "bin").mkdir(exist_ok=True)
    (qpb_root / "bin" / "install_skill.py").write_text("# stub\n", encoding="utf-8")
    (qpb_root / "bin" / "citation_verifier.py").write_text("# stub\n", encoding="utf-8")
    repos = qpb_root / "repos"
    repos.mkdir()
    # Copy the real scripts so the test exercises the actual code.
    shutil.copy(REPO_ROOT / "repos" / "_benchmark_lib.sh", repos / "_benchmark_lib.sh")
    shutil.copy(REPO_ROOT / "repos" / "setup_repos.sh", repos / "setup_repos.sh")
    (repos / "setup_repos.sh").chmod(0o755)
    # v1.5.7 fix F-5b: install_skill_wrapper at repos/bin/run_playbook.sh.
    # Copy it so the fixture exercises the real wrapper-install path.
    (repos / "bin").mkdir()
    shutil.copy(REPO_ROOT / "repos" / "bin" / "run_playbook.sh", repos / "bin" / "run_playbook.sh")
    (repos / "bin" / "run_playbook.sh").chmod(0o755)
    # Clean source for the test repo.
    clean = repos / "clean" / short
    clean.mkdir(parents=True)
    (clean / "README.md").write_text("clean source\n", encoding="utf-8")
    return (repos / "setup_repos.sh"), (repos / f"{short}-{version}")


def _run_setup(script: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Run setup_repos.sh with the given args, return CompletedProcess."""
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


class SetupReposBackupTests(unittest.TestCase):
    """v1.5.7 fix F-3 — backup-by-default with --replace opt-in."""

    def test_existing_dst_backed_up_by_default(self) -> None:
        """Without --replace: existing repos/<short>-<version>/ is renamed
        to repos/<short>-<version>.bak-<UTC-ts>/ before the fresh install
        lands. The sentinel file pre-populated in the prior install must
        survive in the backup."""
        with TemporaryDirectory() as tmp_str:
            qpb_root = Path(tmp_str) / "qpb"
            qpb_root.mkdir()
            script, dst = _build_minimal_fixture(qpb_root)
            # Pre-populate dst with a sentinel.
            dst.mkdir()
            sentinel = dst / "preserved.sentinel"
            sentinel.write_text("must survive backup\n", encoding="utf-8")
            (dst / "quality.gate-failed-fake").mkdir()
            (dst / "quality.gate-failed-fake" / "GATE_FAILURE.md").write_text(
                "fake gate failure\n", encoding="utf-8",
            )

            result = _run_setup(script, ["dummytest"])
            self.assertEqual(
                result.returncode, 0,
                f"setup_repos.sh failed: stdout={result.stdout!r} "
                f"stderr={result.stderr!r}",
            )
            # Backup directory exists with the sentinel inside.
            backups = sorted(dst.parent.glob(f"{dst.name}.bak-*"))
            self.assertEqual(
                len(backups), 1,
                f"expected exactly one backup; got {backups}",
            )
            backup = backups[0]
            self.assertTrue(
                (backup / "preserved.sentinel").is_file(),
                f"sentinel must survive in backup; backup contents: "
                f"{list(backup.iterdir())}",
            )
            self.assertTrue(
                (backup / "quality.gate-failed-fake").is_dir(),
                "preserved D1 gate-failure dir must survive in backup",
            )
            # Fresh install landed at dst.
            self.assertTrue(dst.is_dir(), "fresh install must exist at dst")
            self.assertTrue(
                (dst / "README.md").is_file(),
                "clean source must have been copied into fresh dst",
            )
            self.assertFalse(
                (dst / "preserved.sentinel").exists(),
                "fresh install must NOT carry the prior sentinel",
            )
            self.assertIn("backing up", result.stdout.lower())

    def test_replace_flag_destroys_without_backup(self) -> None:
        """With --replace: existing repos/<short>-<version>/ is wiped
        (rm -rf), no backup created. Confirms the opt-in destructive
        behavior is preserved for operators who want it."""
        with TemporaryDirectory() as tmp_str:
            qpb_root = Path(tmp_str) / "qpb"
            qpb_root.mkdir()
            script, dst = _build_minimal_fixture(qpb_root)
            dst.mkdir()
            (dst / "preserved.sentinel").write_text("doomed\n", encoding="utf-8")

            result = _run_setup(script, ["--replace", "dummytest"])
            self.assertEqual(
                result.returncode, 0,
                f"setup_repos.sh --replace failed: stdout={result.stdout!r} "
                f"stderr={result.stderr!r}",
            )
            # No backup created.
            backups = sorted(dst.parent.glob(f"{dst.name}.bak-*"))
            self.assertEqual(
                backups, [],
                f"--replace must NOT create a backup; got {backups}",
            )
            # Fresh install landed.
            self.assertTrue(dst.is_dir())
            self.assertTrue((dst / "README.md").is_file())
            self.assertFalse(
                (dst / "preserved.sentinel").exists(),
                "--replace must have destroyed the prior content",
            )
            self.assertIn("removing", result.stdout.lower())

    def test_no_existing_dst_no_backup(self) -> None:
        """Sanity: if dst doesn't exist yet, no backup is created (only
        the fresh install). Catches accidental over-eager backup logic."""
        with TemporaryDirectory() as tmp_str:
            qpb_root = Path(tmp_str) / "qpb"
            qpb_root.mkdir()
            script, dst = _build_minimal_fixture(qpb_root)
            # dst not pre-created.
            result = _run_setup(script, ["dummytest"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(dst.is_dir())
            backups = sorted(dst.parent.glob(f"{dst.name}.bak-*"))
            self.assertEqual(backups, [])


class SetupReposRunnerWrapperTests(unittest.TestCase):
    """v1.5.7 fix F-5b: setup_repos.sh installs the runner wrapper at
    <repo>-<version>/bin/run_playbook.sh so adopters can invoke the
    runner from anywhere via the wrapper (auto-discovers QPB clone
    via walk-up from its own location, falls back to $QPB_HOME)."""

    def test_wrapper_installed_into_target(self) -> None:
        """After setup_repos.sh runs, the target carries an executable
        bin/run_playbook.sh wrapper that points (via walk-up) at the
        QPB clone the setup was sourced from."""
        with TemporaryDirectory() as tmp_str:
            qpb_root = Path(tmp_str) / "qpb"
            qpb_root.mkdir()
            script, dst = _build_minimal_fixture(qpb_root)
            result = _run_setup(script, ["dummytest"])
            self.assertEqual(result.returncode, 0, result.stderr)
            wrapper = dst / "bin" / "run_playbook.sh"
            self.assertTrue(
                wrapper.is_file(),
                f"runner wrapper missing at {wrapper}; output={result.stdout!r}",
            )
            self.assertTrue(
                os.access(wrapper, os.X_OK),
                f"runner wrapper not executable at {wrapper}",
            )
            # Content sanity: the wrapper must reference both
            # bin/run_playbook.py (walk-up sentinel) and the
            # `python3 -m bin.run_playbook` exec form.
            body = wrapper.read_text(encoding="utf-8")
            self.assertIn("bin/run_playbook.py", body)
            self.assertIn("python3 -m bin.run_playbook", body)

    def test_wrapper_invocation_resolves_to_real_qpb_via_walkup(self) -> None:
        """Run the installed wrapper with --help and assert it exits 0.
        The wrapper's find_qpb_home walks up to the real QPB clone (the
        fixture's bin/ has the wrapper but not a runnable run_playbook.py,
        so the wrapper must fall back to $QPB_HOME or further walk-up).
        Test sets $QPB_HOME to the real QPB clone to verify the fallback
        path works end-to-end."""
        with TemporaryDirectory() as tmp_str:
            qpb_root = Path(tmp_str) / "qpb"
            qpb_root.mkdir()
            script, dst = _build_minimal_fixture(qpb_root)
            result = _run_setup(script, ["dummytest"])
            self.assertEqual(result.returncode, 0, result.stderr)
            wrapper = dst / "bin" / "run_playbook.sh"
            env = os.environ.copy()
            env["QPB_HOME"] = str(REPO_ROOT)
            result2 = subprocess.run(
                ["bash", str(wrapper), "--help"],
                capture_output=True, text=True, timeout=30, env=env,
            )
            self.assertEqual(
                result2.returncode, 0,
                f"wrapper --help failed: stdout={result2.stdout!r} "
                f"stderr={result2.stderr!r}",
            )
            self.assertIn("usage:", result2.stdout)


if __name__ == "__main__":
    unittest.main()
