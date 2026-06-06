"""v1.5.8 — tests for bin/publish_pip.py.

Covers each of the 8 pre-flight checks plus the --dry-run end-to-end
flow. Subprocess and filesystem state are mocked so the tests can run
without a network, without a populated dist/, and without twine
credentials.

The tests pair PASS and FAIL fixtures for each check to guarantee the
check actually distinguishes the good/bad state (rather than always
returning True).
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bin import publish_pip  # noqa: E402


def _make_fake_repo(
    root: Path,
    *,
    py_version: str = "1.5.8",
    pkg_version: str = "1.5.8",
    init_version: str = "1.5.8",
) -> None:
    """Lay out a minimal fake QPB repo at ``root`` with the three
    version-bearing manifests + an empty bundle dir.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "quality-playbook"\nversion = "{py_version}"\n',
        encoding="utf-8",
    )
    (root / "package.json").write_text(
        json.dumps({"name": "quality-playbook", "version": pkg_version}) + "\n",
        encoding="utf-8",
    )
    cli_dir = root / "quality_playbook_cli"
    cli_dir.mkdir(parents=True, exist_ok=True)
    (cli_dir / "__init__.py").write_text(
        f'__version__ = "{init_version}"\n',
        encoding="utf-8",
    )


class ReadVersionTests(unittest.TestCase):
    """The version regexes catch the canonical shapes and skip noise."""

    def test_read_pyproject_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pyproject.toml"
            p.write_text('version = "1.5.8"\n', encoding="utf-8")
            self.assertEqual(
                publish_pip._read_version(p, publish_pip._VERSION_RE_TOML),
                "1.5.8",
            )

    def test_read_package_json_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "package.json"
            p.write_text(
                '{ "name": "quality-playbook", "version": "1.5.8" }\n',
                encoding="utf-8",
            )
            self.assertEqual(
                publish_pip._read_version(p, publish_pip._VERSION_RE_JSON),
                "1.5.8",
            )

    def test_read_init_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "__init__.py"
            p.write_text('__version__ = "1.5.8"\n', encoding="utf-8")
            self.assertEqual(
                publish_pip._read_version(p, publish_pip._VERSION_RE_PY),
                "1.5.8",
            )

    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(
            publish_pip._read_version(
                Path("/nonexistent/file"), publish_pip._VERSION_RE_TOML
            )
        )


class CheckCleanTreeTests(unittest.TestCase):
    """Check 1: git status --porcelain empty."""

    def test_clean_tree_passes(self) -> None:
        with mock.patch.object(publish_pip, "_run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            ok, msg = publish_pip.check_clean_tree(Path("/fake/repo"))
        self.assertTrue(ok)
        self.assertIn("clean", msg.lower())

    def test_dirty_tree_fails(self) -> None:
        with mock.patch.object(publish_pip, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=0,
                stdout=" M some_file.py\n?? another.py\n",
                stderr="",
            )
            ok, msg = publish_pip.check_clean_tree(Path("/fake/repo"))
        self.assertFalse(ok)
        self.assertIn("some_file.py", msg)

    def test_git_status_failure_halts(self) -> None:
        with mock.patch.object(publish_pip, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=128,
                stdout="",
                stderr="fatal: not a git repository",
            )
            ok, msg = publish_pip.check_clean_tree(Path("/fake/repo"))
        self.assertFalse(ok)
        self.assertIn("git status", msg.lower())


class CheckVersionParityTests(unittest.TestCase):
    """Check 2: pyproject + package.json + __init__.py agree."""

    def test_all_three_agree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            ok, msg = publish_pip.check_version_parity(root)
        self.assertTrue(ok, msg)
        self.assertIn("1.5.8", msg)

    def test_pyproject_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, py_version="1.5.9")
            ok, msg = publish_pip.check_version_parity(root)
        self.assertFalse(ok)
        self.assertIn("MISMATCH", msg)
        self.assertIn("1.5.9", msg)
        self.assertIn("1.5.8", msg)

    def test_package_json_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, pkg_version="1.4.0")
            ok, msg = publish_pip.check_version_parity(root)
        self.assertFalse(ok)
        self.assertIn("MISMATCH", msg)

    def test_init_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, init_version="2.0.0")
            ok, msg = publish_pip.check_version_parity(root)
        self.assertFalse(ok)
        self.assertIn("MISMATCH", msg)

    def test_missing_manifest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            (root / "pyproject.toml").unlink()
            ok, msg = publish_pip.check_version_parity(root)
        self.assertFalse(ok)
        self.assertIn("Missing", msg)


class CheckTagExistsTests(unittest.TestCase):
    """Check 3: git tag --list v<version> returns the tag."""

    def test_tag_present_passes(self) -> None:
        with mock.patch.object(publish_pip, "_run") as m_run:
            m_run.side_effect = [
                mock.Mock(returncode=0, stdout="v1.5.8\n", stderr=""),
                mock.Mock(returncode=0, stdout="a33befa\n", stderr=""),
            ]
            ok, msg = publish_pip.check_tag_exists(Path("/fake"), "1.5.8")
        self.assertTrue(ok)
        self.assertIn("v1.5.8", msg)

    def test_tag_missing_fails(self) -> None:
        with mock.patch.object(publish_pip, "_run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            ok, msg = publish_pip.check_tag_exists(Path("/fake"), "1.5.8")
        self.assertFalse(ok)
        self.assertIn("does NOT exist", msg)


class CheckTagAncestorTests(unittest.TestCase):
    """Check 4: tag is ancestor of HEAD (or explicit confirm)."""

    def test_ancestor_passes(self) -> None:
        with mock.patch.object(publish_pip, "_run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            ok, msg = publish_pip.check_tag_ancestor_of_head(
                Path("/fake"), "1.5.8"
            )
        self.assertTrue(ok)

    def test_not_ancestor_with_yes_confirm_passes(self) -> None:
        with mock.patch.object(publish_pip, "_run") as m_run:
            m_run.return_value = mock.Mock(returncode=1, stdout="", stderr="")
            ok, msg = publish_pip.check_tag_ancestor_of_head(
                Path("/fake"), "1.5.8", confirm=True
            )
        self.assertTrue(ok)

    def test_not_ancestor_with_no_confirm_fails(self) -> None:
        with mock.patch.object(publish_pip, "_run") as m_run:
            m_run.return_value = mock.Mock(returncode=1, stdout="", stderr="")
            ok, msg = publish_pip.check_tag_ancestor_of_head(
                Path("/fake"), "1.5.8", confirm=False
            )
        self.assertFalse(ok)
        self.assertIn("declined", msg.lower())

    def test_not_ancestor_prompts_when_confirm_none(self) -> None:
        """With confirm=None and a piped EOF input, the check halts."""
        with mock.patch.object(publish_pip, "_run") as m_run, \
             mock.patch("builtins.input", side_effect=EOFError()):
            m_run.return_value = mock.Mock(returncode=1, stdout="", stderr="")
            ok, msg = publish_pip.check_tag_ancestor_of_head(
                Path("/fake"), "1.5.8", confirm=None
            )
        self.assertFalse(ok)


class CheckParityTestTests(unittest.TestCase):
    """Check 6: 089u parity test passes."""

    def test_parity_test_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bin" / "tests").mkdir(parents=True)
            (root / "bin" / "tests" / "test_pip_channel_package_parity_089u.py").write_text(
                "# fake\n", encoding="utf-8"
            )
            with mock.patch.object(publish_pip, "_run") as m_run:
                m_run.return_value = mock.Mock(
                    returncode=0, stdout="passed", stderr=""
                )
                ok, msg = publish_pip.check_parity_test(root)
        self.assertTrue(ok)

    def test_parity_test_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bin" / "tests").mkdir(parents=True)
            (root / "bin" / "tests" / "test_pip_channel_package_parity_089u.py").write_text(
                "# fake\n", encoding="utf-8"
            )
            with mock.patch.object(publish_pip, "_run") as m_run:
                m_run.return_value = mock.Mock(
                    returncode=1, stdout="1 failed", stderr=""
                )
                ok, msg = publish_pip.check_parity_test(root)
        self.assertFalse(ok)
        self.assertIn("FAILED", msg)

    def test_parity_test_skipped_passes(self) -> None:
        ok, msg = publish_pip.check_parity_test(Path("/fake"), skip=True)
        self.assertTrue(ok)
        self.assertIn("skipped", msg.lower())

    def test_parity_test_missing_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ok, msg = publish_pip.check_parity_test(Path(td))
        self.assertFalse(ok)
        self.assertIn("not found", msg.lower())


class CheckForbiddenContentsTests(unittest.TestCase):
    """Check 7: no forbidden paths inside dist/*.whl or dist/*.tar.gz."""

    def _build_clean_wheel(self, dist: Path) -> Path:
        dist.mkdir(parents=True, exist_ok=True)
        wheel = dist / "quality_playbook-1.5.8-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as zf:
            zf.writestr("quality_playbook_cli/__init__.py", "")
            zf.writestr("quality_playbook_cli/_bundle/SKILL.md", "# fake")
        return wheel

    def _build_dirty_wheel(self, dist: Path, fragment: str) -> Path:
        dist.mkdir(parents=True, exist_ok=True)
        wheel = dist / "quality_playbook-1.5.8-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as zf:
            zf.writestr("quality_playbook_cli/__init__.py", "")
            zf.writestr(fragment, "")
        return wheel

    def test_clean_wheel_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._build_clean_wheel(root / "dist")
            ok, msg = publish_pip.check_no_forbidden_contents(root)
        self.assertTrue(ok, msg)

    def test_wheel_with_pycache_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._build_dirty_wheel(
                root / "dist", "quality_playbook_cli/__pycache__/x.pyc"
            )
            ok, msg = publish_pip.check_no_forbidden_contents(root)
        self.assertFalse(ok)
        self.assertIn("__pycache__", msg)

    def test_wheel_with_quality_dir_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._build_dirty_wheel(
                root / "dist", "quality_playbook_cli/quality/BUGS.md"
            )
            ok, msg = publish_pip.check_no_forbidden_contents(root)
        self.assertFalse(ok)
        self.assertIn("quality/", msg)

    def test_wheel_with_env_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._build_dirty_wheel(root / "dist", "quality_playbook_cli/.env")
            ok, msg = publish_pip.check_no_forbidden_contents(root)
        self.assertFalse(ok)
        self.assertIn(".env", msg)

    def test_missing_dist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ok, msg = publish_pip.check_no_forbidden_contents(Path(td))
        self.assertFalse(ok)
        self.assertIn("dist/", msg)

    def test_empty_dist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "dist").mkdir()
            ok, msg = publish_pip.check_no_forbidden_contents(Path(td))
        self.assertFalse(ok)
        self.assertIn("No wheel or sdist", msg)


class CheckTwineAuthTests(unittest.TestCase):
    """Check 8: twine importable + credentials reachable."""

    def test_pypirc_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td)
            (fake_home / ".pypirc").write_text(
                "[pypi]\nusername = __token__\n", encoding="utf-8"
            )
            with mock.patch.object(Path, "home", return_value=fake_home):
                ok, msg = publish_pip.check_twine_auth()
        # In this test env twine may or may not be importable. If it is,
        # we expect the pypirc branch to be selected.
        if "not importable" in msg:
            self.skipTest("twine not installed in test env")
        self.assertTrue(ok)
        self.assertIn(".pypirc", msg)

    def test_env_vars_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td)  # No .pypirc inside.
            env = {
                "TWINE_USERNAME": "__token__",
                "TWINE_PASSWORD": "x" * 16,
            }
            with mock.patch.object(Path, "home", return_value=fake_home), \
                 mock.patch.dict(os.environ, env, clear=False):
                ok, msg = publish_pip.check_twine_auth()
        if "not importable" in msg:
            self.skipTest("twine not installed in test env")
        self.assertTrue(ok)
        self.assertIn("TWINE_USERNAME", msg)

    def test_no_creds_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td)
            scrub = {
                k: None for k in
                ("TWINE_USERNAME", "TWINE_PASSWORD", "TWINE_REPOSITORY_URL")
            }
            with mock.patch.object(Path, "home", return_value=fake_home), \
                 mock.patch.dict(os.environ, {}, clear=False):
                for k in list(scrub):
                    os.environ.pop(k, None)
                ok, msg = publish_pip.check_twine_auth()
        if "not importable" in msg:
            self.skipTest("twine not installed in test env")
        self.assertFalse(ok)
        self.assertIn("No twine credentials", msg)


class ScanArchiveTests(unittest.TestCase):
    """The internal scanner catches every forbidden shape."""

    def test_pycache_fragment(self) -> None:
        hits = publish_pip._scan_archive_for_forbidden(
            ["foo/__pycache__/x.pyc", "ok.py"]
        )
        self.assertEqual(len(hits), 1)

    def test_pyc_suffix(self) -> None:
        hits = publish_pip._scan_archive_for_forbidden(["foo/something.pyc"])
        self.assertEqual(len(hits), 1)

    def test_dotenv_basename(self) -> None:
        hits = publish_pip._scan_archive_for_forbidden(["foo/.env"])
        self.assertEqual(len(hits), 1)

    def test_node_modules(self) -> None:
        hits = publish_pip._scan_archive_for_forbidden(
            ["x/node_modules/foo/index.js"]
        )
        self.assertEqual(len(hits), 1)

    def test_clean_paths(self) -> None:
        hits = publish_pip._scan_archive_for_forbidden(
            ["quality_playbook_cli/__init__.py", "SKILL.md"]
        )
        self.assertEqual(hits, [])


class DryRunMainTests(unittest.TestCase):
    """End-to-end --dry-run flow against a fake repo.

    Mocks everything that touches the network or filesystem outside the
    fake repo: subprocess for build + parity + twine, twine import, log
    directory location.
    """

    def test_dry_run_succeeds_on_clean_fake_repo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            # Build the layout the script expects: dist/ wheel, parity
            # test file, log dir under fake home.
            dist = root / "dist"
            dist.mkdir()
            wheel = dist / "quality_playbook-1.5.8-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as zf:
                zf.writestr("quality_playbook_cli/__init__.py", "")
            (root / "bin" / "tests").mkdir(parents=True)
            (root / "bin" / "tests" / "test_pip_channel_package_parity_089u.py").write_text(
                "# fake\n", encoding="utf-8"
            )
            fake_home = root / "fakehome"
            fake_home.mkdir()

            # The script resolves REPO_ROOT from __file__; override via
            # a patch.
            real_resolve = Path.resolve
            with mock.patch.object(
                publish_pip, "__file__", str(root / "bin" / "publish_pip.py")
            ), mock.patch.object(
                Path, "home", return_value=fake_home
            ), mock.patch.object(
                publish_pip, "_run"
            ) as m_run:
                # git status clean; git tag exists + rev-parse; git
                # merge-base ancestor; build stage + python -m build
                # succeed; pytest passes.
                def _fake_run(args, **kw):
                    a0 = args[0]
                    if a0 == "git" and "status" in args:
                        return mock.Mock(returncode=0, stdout="", stderr="")
                    if a0 == "git" and "tag" in args:
                        return mock.Mock(
                            returncode=0, stdout="v1.5.8\n", stderr=""
                        )
                    if a0 == "git" and "rev-parse" in args:
                        return mock.Mock(
                            returncode=0, stdout="abc1234\n", stderr=""
                        )
                    if a0 == "git" and "merge-base" in args:
                        return mock.Mock(returncode=0, stdout="", stderr="")
                    # Everything else (build, pytest, etc): succeed.
                    return mock.Mock(returncode=0, stdout="ok\n", stderr="")
                m_run.side_effect = _fake_run
                rc = publish_pip.main(["--dry-run", "--skip-build"])
            self.assertEqual(rc, publish_pip.EX_OK)
            # Log file is written under fake_home; assert before tempdir
            # cleanup tears it down.
            log_dir = fake_home / ".qpb" / "publish_logs"
            self.assertTrue(log_dir.is_dir())
            logs = sorted(log_dir.glob("pip_1.5.8_*.log"))
            self.assertGreaterEqual(len(logs), 1)
            body = logs[-1].read_text(encoding="utf-8")
            self.assertIn("Pre-flight checks PASSED", body)
            self.assertIn("[dry-run]", body)

    def test_dry_run_halts_on_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, pkg_version="1.4.0")
            fake_home = root / "fakehome"
            fake_home.mkdir()
            with mock.patch.object(
                publish_pip, "__file__", str(root / "bin" / "publish_pip.py")
            ), mock.patch.object(
                Path, "home", return_value=fake_home
            ), mock.patch.object(
                publish_pip, "_run"
            ) as m_run:
                m_run.return_value = mock.Mock(
                    returncode=0, stdout="", stderr=""
                )
                rc = publish_pip.main(["--dry-run", "--skip-build"])
        self.assertEqual(rc, publish_pip.EX_DATAERR)


class NoArgsBannerTests(unittest.TestCase):
    """The 089x discoverability invariant: no-args run prints the
    purpose banner and exits 0, with no side effects."""

    def test_no_args_prints_banner_returns_zero(self) -> None:
        buf = io.StringIO()
        with mock.patch("sys.stdout", new=buf):
            rc = publish_pip.main([])
        self.assertEqual(rc, publish_pip.EX_OK)
        out = buf.getvalue()
        self.assertIn("Quality Playbook v", out)
        self.assertIn("Role in a playbook run:", out)
        self.assertIn("by Andrew Stellman", out)


class ArgParseTests(unittest.TestCase):
    def test_dry_run_flag_recognized(self) -> None:
        ns = publish_pip.parse_args(["--dry-run"])
        self.assertTrue(ns.dry_run)

    def test_skip_flags_default_false(self) -> None:
        ns = publish_pip.parse_args([])
        self.assertFalse(ns.dry_run)
        self.assertFalse(ns.skip_tests)
        self.assertFalse(ns.skip_build)

    def test_help_does_not_crash(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            with mock.patch("sys.stdout", new=io.StringIO()):
                publish_pip.parse_args(["--help"])
        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
