"""Tests for bin/install_skill.py.

Coverage: environment detection (.claude / .github / .cursor),
--target override, no-env-no-target refusal, idempotency with
operator-edit preservation, --force overwrite semantics, smoke pass on
clean install, smoke fail on broken quality_gate, structured-output
parseability, pathlib's handling of Windows-style path strings on POSIX.

All tests use TemporaryDirectory sandboxes — no test ever writes outside
the sandbox.
"""

from __future__ import annotations

import io
import re
import shutil
import unittest
from contextlib import redirect_stderr
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory

from bin import install_skill


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _capture_install(**kwargs) -> tuple[int, str]:
    """Run install_skill.install with output captured to a StringIO.
    Returns (exit_code, stdout_text)."""
    buf = io.StringIO()
    rc = install_skill.install(stream=buf, **kwargs)
    return rc, buf.getvalue()


def _write_minimal_env(target_root: Path, env_marker: str) -> None:
    """Drop a marker subdirectory so detect_environment sees the env."""
    (target_root / env_marker).mkdir()


class EnvironmentDetectionTests(unittest.TestCase):
    """The detect-environment-from-cwd flow auto-targets the right
    install path for each known AI tool."""

    def test_detect_claude_env(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_minimal_env(tmp, ".claude")
            rc, out = _capture_install(cwd=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            self.assertIn("event=detected_env env=.claude", out)
            target = tmp / ".claude" / "skills" / "quality-playbook"
            self.assertTrue((target / "SKILL.md").is_file())
            self.assertTrue((target / "quality_gate.py").is_file())
            self.assertTrue((target / "references" / "exploration_patterns.md").is_file())

    def test_detect_github_env(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_minimal_env(tmp, ".github")
            rc, out = _capture_install(cwd=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            self.assertIn("event=detected_env env=.github", out)
            target = tmp / ".github" / "skills" / "quality-playbook"
            self.assertTrue((target / "SKILL.md").is_file())

    def test_detect_cursor_env(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_minimal_env(tmp, ".cursor")
            rc, out = _capture_install(cwd=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            self.assertIn("event=detected_env env=.cursor", out)
            self.assertTrue(
                (tmp / ".cursor" / "skills" / "quality-playbook" / "SKILL.md").is_file()
            )

    def test_target_override(self) -> None:
        """--target wins even when an environment is detectable."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_minimal_env(tmp, ".claude")
            custom = tmp / "custom-install-path"
            rc, out = _capture_install(
                cwd=tmp, source_root=REPO_ROOT, target=custom,
            )
            self.assertEqual(rc, 0, out)
            self.assertIn("event=target_explicit", out)
            self.assertNotIn("event=detected_env", out)
            self.assertTrue((custom / "SKILL.md").is_file())
            # Auto-detect target was NOT used.
            self.assertFalse(
                (tmp / ".claude" / "skills" / "quality-playbook" / "SKILL.md").exists()
            )

    def test_no_environment_no_target_refuses(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            # Plain dir — no .claude / .github / .cursor / .continue
            (tmp / "src").mkdir()
            rc, out = _capture_install(cwd=tmp, source_root=REPO_ROOT)
            self.assertEqual(
                rc, 64,
                f"expected EX_USAGE refusal; got {rc}. Output: {out}",
            )
            self.assertIn("event=refuse", out)
            self.assertIn("reason=no-environment-detected", out)
            # Helpful prose names the alternative.
            self.assertIn(".claude", out)


class IdempotencyAndForceTests(unittest.TestCase):
    """Re-installing preserves operator edits as
    .operator-backup-<timestamp>; --force skips the backup."""

    def test_idempotent_preserves_operator_edits(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            # Initial install.
            rc1, _ = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc1, 0)
            # Operator edit: modify SKILL.md in target.
            skill = target / "SKILL.md"
            edited = skill.read_text(encoding="utf-8") + "\n# operator notes\n"
            skill.write_text(edited, encoding="utf-8")
            # Re-install WITHOUT --force.
            rc2, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc2, 0, out)
            # Backup exists with operator's content.
            backups = list(target.glob("SKILL.md.operator-backup-*"))
            self.assertEqual(
                len(backups), 1,
                f"expected exactly one backup, got {backups}",
            )
            self.assertIn("operator notes", backups[0].read_text(encoding="utf-8"))
            # New SKILL.md does NOT contain the operator edit.
            self.assertNotIn("operator notes", skill.read_text(encoding="utf-8"))
            # Status line shows backed_up.
            self.assertIn("status=backed_up", out)

    def test_force_overwrites(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            rc1, _ = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc1, 0)
            skill = target / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8") + "\n# operator notes\n",
                encoding="utf-8",
            )
            rc2, out = _capture_install(
                target=target, source_root=REPO_ROOT, force=True,
            )
            self.assertEqual(rc2, 0, out)
            backups = list(target.glob("SKILL.md.operator-backup-*"))
            self.assertEqual(backups, [])
            self.assertNotIn("operator notes", skill.read_text(encoding="utf-8"))
            self.assertIn("status=overwritten", out)


class IntoFlagTests(unittest.TestCase):
    """`--into` scans the target repo and resolves the install path from
    the detected AI-tool marker inside that repo."""

    def test_into_flag_detects_claude_in_target(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str).resolve()
            _write_minimal_env(tmp, ".claude")
            rc, out = _capture_install(into=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            install_path = tmp / ".claude" / "skills" / "quality-playbook"
            self.assertIn("event=detected_env_inside_target", out)
            self.assertIn(f"target={tmp}", out)
            self.assertIn("env=.claude", out)
            self.assertIn(f"install_path={install_path}", out)
            self.assertTrue((install_path / "SKILL.md").is_file())

    def test_into_flag_detects_cursor_in_target(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str).resolve()
            _write_minimal_env(tmp, ".cursor")
            rc, out = _capture_install(into=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            install_path = tmp / ".cursor" / "skills" / "quality-playbook"
            self.assertIn("event=detected_env_inside_target", out)
            self.assertIn(f"target={tmp}", out)
            self.assertIn("env=.cursor", out)
            self.assertIn(f"install_path={install_path}", out)
            self.assertTrue((install_path / "SKILL.md").is_file())

    def test_into_flag_detects_github_in_target(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str).resolve()
            _write_minimal_env(tmp, ".github")
            rc, out = _capture_install(into=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            install_path = tmp / ".github" / "skills" / "quality-playbook"
            self.assertIn("event=detected_env_inside_target", out)
            self.assertIn(f"target={tmp}", out)
            self.assertIn("env=.github", out)
            self.assertIn(f"install_path={install_path}", out)
            self.assertTrue((install_path / "SKILL.md").is_file())

    def test_into_flag_no_env_in_target_refuses(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str).resolve()
            (tmp / "src").mkdir()
            rc, out = _capture_install(into=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 64, out)
            self.assertIn("event=refuse", out)
            self.assertIn("reason=no-environment-detected-in-target", out)
            self.assertIn(f"target={tmp}", out)

    def test_target_and_into_mutually_exclusive(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            err = io.StringIO()
            with redirect_stderr(err):
                with self.assertRaises(SystemExit) as raised:
                    install_skill.main(
                        [
                            "--target", str(tmp / "install"),
                            "--into", str(tmp),
                        ]
                    )
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("not allowed with argument", err.getvalue())


class SmokeCheckTests(unittest.TestCase):
    """Smoke pass on a clean install; smoke fail when quality_gate.py
    is sabotaged."""

    def test_smoke_check_passes_on_clean_install(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            for check in (
                "quality_gate_help",
                "skill_md_frontmatter",
                "exploration_patterns_loaded",
            ):
                self.assertIn(
                    f"check={check} status=passed", out,
                    f"smoke check {check} did not pass; output: {out}",
                )

    def test_smoke_check_catches_broken_quality_gate(self) -> None:
        """Install with --no-smoke, deliberately break quality_gate.py
        in the target, then re-invoke the smoke check by re-installing
        with --force=False (the existing-file path) — but actually the
        cleanest reproduction is a separate install call that runs the
        smoke check against the broken target."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            # Initial install with smoke skipped.
            rc, _ = _capture_install(
                target=target, source_root=REPO_ROOT, no_smoke=True,
            )
            self.assertEqual(rc, 0)
            # Sabotage quality_gate.py — replace with non-Python garbage.
            (target / "quality_gate.py").write_text(
                "this is not valid python )(\n", encoding="utf-8",
            )
            # Re-install with --force so the broken file persists past
            # the copy step (force overwrites without backup, but the
            # source is identical so nothing happens — wait, we need
            # the smoke check to run AGAINST the broken file. The
            # cleanest path: re-run install with the same target but
            # have the source's quality_gate.py be the broken one.
            # Easier: directly call the smoke check.
            buf = io.StringIO()
            emitter = install_skill.Emitter(verbose=False, stream=buf)
            ok = install_skill.smoke_check_quality_gate(target, emitter)
            output = buf.getvalue()
            self.assertFalse(
                ok,
                f"expected smoke check to fail; output: {output}",
            )
            self.assertIn("status=failed", output)
            self.assertIn("compile-exit-", output)


class StructuredOutputTests(unittest.TestCase):
    """Default output is parseable as one event per line, key=value
    pairs."""

    def test_structured_output_parseable(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc, 0)
            event_re = re.compile(r"^event=\w+(\s+\w+=\S+)*\s*$")
            non_event = []
            for line in out.splitlines():
                if not line.strip():
                    continue
                if not event_re.match(line):
                    non_event.append(line)
            self.assertEqual(
                non_event, [],
                f"non-event lines in default output (verbose=False): {non_event}",
            )

    def test_verbose_adds_prose_lines(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            rc, out = _capture_install(
                target=target, source_root=REPO_ROOT, verbose=True,
            )
            self.assertEqual(rc, 0)
            # Verbose prose lines are 2-space indented, do not start
            # with "event=".
            prose_lines = [
                line for line in out.splitlines()
                if line.startswith("  ")
            ]
            self.assertGreater(
                len(prose_lines), 0,
                "verbose output should contain at least one prose line",
            )


class PathlibCrossPlatformTests(unittest.TestCase):
    """A Windows-style path string flows through pathlib.Path on POSIX
    by being interpreted as a forward-slash path; the bigger guarantee
    is that the script never uses string concatenation with '/' so any
    pathlib.Path or pathlib.PureWindowsPath works on its native OS."""

    def test_pathlib_handles_windows_path_string(self) -> None:
        # PureWindowsPath constructs cleanly; the script's internal
        # path operations would then run on it on Windows. On POSIX we
        # validate the path-construction half (no string concat
        # accidents).
        win = PureWindowsPath(r"C:\Users\op\.claude\skills\quality-playbook")
        self.assertEqual(win.name, "quality-playbook")
        self.assertEqual(win.parts[-3:], (".claude", "skills", "quality-playbook"))
        # Windows drive letter is preserved in the first part.
        self.assertTrue(win.parts[0].startswith("C:"))
        # The install script's bundle enumeration uses pathlib.Path
        # exclusively (verified by importing _bundle_files and
        # checking every path returned is a Path instance).
        bundle = install_skill._bundle_files(REPO_ROOT)
        for src, dst in bundle:
            self.assertIsInstance(src, Path)
            self.assertIsInstance(dst, Path)


class DowngradeRefusalTests(unittest.TestCase):
    """Refuse to install over a target whose SKILL.md version is HIGHER
    than the bundle's."""

    def test_downgrade_refused(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            target.mkdir()
            # Stage a target SKILL.md with a higher version than the
            # current bundle.
            target_skill = target / "SKILL.md"
            target_skill.write_text(
                "---\n"
                "name: quality-playbook\n"
                "description: stub\n"
                "metadata:\n"
                "  version: 99.0.0\n"
                "---\n",
                encoding="utf-8",
            )
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(
                rc, 65,
                f"expected EX_DATAERR (65) on downgrade refusal; got {rc}. {out}",
            )
            self.assertIn("event=refuse reason=downgrade", out)
            # Target SKILL.md must NOT have been overwritten.
            self.assertIn("99.0.0", target_skill.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
