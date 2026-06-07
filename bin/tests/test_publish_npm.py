"""v1.5.8 — tests for bin/publish_npm.py.

Covers each of the 7 pre-flight checks plus the --dry-run end-to-end
flow. Subprocess, npm CLI, and filesystem state are mocked so the
tests can run without npm installed and without npm credentials.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bin import publish_npm  # noqa: E402


def _make_fake_repo(
    root: Path,
    *,
    py_version: str = "1.5.8",
    pkg_version: str = "1.5.8",
    init_version: str = "1.5.8",
    stage_bundle: bool = True,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "quality-playbook"\nversion = "{py_version}"\n',
        encoding="utf-8",
    )
    (root / "package.json").write_text(
        json.dumps({"name": "quality-playbook", "version": pkg_version}) + "\n",
        encoding="utf-8",
    )
    cli = root / "quality_playbook_cli"
    cli.mkdir(parents=True, exist_ok=True)
    (cli / "__init__.py").write_text(
        f'__version__ = "{init_version}"\n', encoding="utf-8"
    )
    if stage_bundle:
        bundle = cli / "_bundle"
        bundle.mkdir(parents=True, exist_ok=True)
        (bundle / "SKILL.md").write_text("# fake skill\n", encoding="utf-8")
        (bundle / "quality_gate.py").write_text("# fake\n", encoding="utf-8")


class CheckCleanTreeTests(unittest.TestCase):
    def test_clean_tree_passes(self) -> None:
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            ok, msg = publish_npm.check_clean_tree(Path("/fake"))
        self.assertTrue(ok)

    def test_dirty_tree_fails(self) -> None:
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=0, stdout=" M f.py\n", stderr=""
            )
            ok, msg = publish_npm.check_clean_tree(Path("/fake"))
        self.assertFalse(ok)
        self.assertIn("f.py", msg)


class CheckVersionParityTests(unittest.TestCase):
    def test_parity_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            ok, msg = publish_npm.check_version_parity(root)
        self.assertTrue(ok, msg)

    def test_pyproject_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, py_version="2.0.0")
            ok, msg = publish_npm.check_version_parity(root)
        self.assertFalse(ok)
        self.assertIn("MISMATCH", msg)

    def test_package_json_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, pkg_version="1.4.0")
            ok, msg = publish_npm.check_version_parity(root)
        self.assertFalse(ok)

    def test_init_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, init_version="9.9.9")
            ok, msg = publish_npm.check_version_parity(root)
        self.assertFalse(ok)


class CheckTagExistsTests(unittest.TestCase):
    def test_tag_present_passes(self) -> None:
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=0, stdout="v1.5.8\n", stderr=""
            )
            ok, msg = publish_npm.check_tag_exists(Path("/fake"), "1.5.8")
        self.assertTrue(ok)

    def test_tag_missing_fails(self) -> None:
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            ok, msg = publish_npm.check_tag_exists(Path("/fake"), "1.5.8")
        self.assertFalse(ok)


class CheckNpmWhoamiTests(unittest.TestCase):
    def test_logged_in_passes(self) -> None:
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=0, stdout="andrewstellman\n", stderr=""
            )
            ok, msg = publish_npm.check_npm_whoami("/usr/local/bin/npm")
        self.assertTrue(ok)
        self.assertIn("andrewstellman", msg)

    def test_not_logged_in_fails(self) -> None:
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="ENEEDAUTH"
            )
            ok, msg = publish_npm.check_npm_whoami("/usr/local/bin/npm")
        self.assertFalse(ok)
        self.assertIn("npm login", msg)

    def test_npm_missing_fails(self) -> None:
        ok, msg = publish_npm.check_npm_whoami(None)
        self.assertFalse(ok)
        self.assertIn("PATH", msg)


class CheckStageBundleTests(unittest.TestCase):
    def test_stage_succeeds(self) -> None:
        log_fh = io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bin").mkdir()
            (root / "bin" / "build_channel_package.py").write_text(
                "# fake\n", encoding="utf-8"
            )
            with mock.patch.object(publish_npm, "_run") as m_run:
                m_run.return_value = mock.Mock(
                    returncode=0, stdout="staged ok\n", stderr=""
                )
                ok, msg = publish_npm.check_stage_bundle(root, log_fh)
        self.assertTrue(ok)

    def test_stage_failure_fails(self) -> None:
        log_fh = io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.object(publish_npm, "_run") as m_run:
                m_run.return_value = mock.Mock(
                    returncode=1, stdout="", stderr="staging failed: missing _purpose.py"
                )
                ok, msg = publish_npm.check_stage_bundle(root, log_fh)
        self.assertFalse(ok)
        self.assertIn("failed", msg.lower())

    def test_skip_passes(self) -> None:
        ok, msg = publish_npm.check_stage_bundle(
            Path("/fake"), io.StringIO(), skip=True
        )
        self.assertTrue(ok)


class CheckNoForbiddenInBundleTests(unittest.TestCase):
    def test_clean_bundle_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            ok, msg = publish_npm.check_no_forbidden_in_bundle(root)
        self.assertTrue(ok, msg)

    def test_pycache_in_bundle_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            cache = root / "quality_playbook_cli" / "_bundle" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "stale.pyc").write_bytes(b"\x00\x00")
            ok, msg = publish_npm.check_no_forbidden_in_bundle(root)
        self.assertFalse(ok)
        self.assertIn("__pycache__", msg)

    def test_quality_dir_in_bundle_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            q = root / "quality_playbook_cli" / "_bundle" / "quality"
            q.mkdir(parents=True)
            (q / "BUGS.md").write_text("# fake\n", encoding="utf-8")
            ok, msg = publish_npm.check_no_forbidden_in_bundle(root)
        self.assertFalse(ok)
        self.assertIn("quality/", msg)

    def test_env_file_in_bundle_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            (root / "quality_playbook_cli" / "_bundle" / ".env").write_text(
                "SECRET=x\n", encoding="utf-8"
            )
            ok, msg = publish_npm.check_no_forbidden_in_bundle(root)
        self.assertFalse(ok)
        self.assertIn(".env", msg)

    def test_missing_bundle_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, stage_bundle=False)
            ok, msg = publish_npm.check_no_forbidden_in_bundle(root)
        self.assertFalse(ok)
        self.assertIn("Staged bundle not found", msg)


class NpmPackDryRunTests(unittest.TestCase):
    def test_clean_pack_passes(self) -> None:
        payload = json.dumps(
            [
                {
                    "files": [
                        {"path": "package.json"},
                        {"path": "quality_playbook_cli/_bundle/SKILL.md"},
                    ]
                }
            ]
        )
        log_fh = io.StringIO()
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=0, stdout=payload, stderr=""
            )
            ok, msg, files = publish_npm.npm_pack_dry_run(
                Path("/fake"), "/usr/local/bin/npm", log_fh
            )
        self.assertTrue(ok)
        self.assertIn("SKILL.md", "\n".join(files))

    def test_pack_with_pyc_fails(self) -> None:
        payload = json.dumps(
            [
                {
                    "files": [
                        {"path": "package.json"},
                        {"path": "quality_playbook_cli/_bundle/x.pyc"},
                    ]
                }
            ]
        )
        log_fh = io.StringIO()
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=0, stdout=payload, stderr=""
            )
            ok, msg, files = publish_npm.npm_pack_dry_run(
                Path("/fake"), "/usr/local/bin/npm", log_fh
            )
        self.assertFalse(ok)
        self.assertIn(".pyc", msg)

    def test_pack_failure_fails(self) -> None:
        log_fh = io.StringIO()
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="npm ERR! invalid package"
            )
            ok, msg, files = publish_npm.npm_pack_dry_run(
                Path("/fake"), "/usr/local/bin/npm", log_fh
            )
        self.assertFalse(ok)

    def test_polluted_stdout_with_progress_line_parses(self) -> None:
        # Defense-in-depth (instruction 203): prepack progress line on
        # stdout before npm's JSON output must NOT break parsing. Find
        # the '[' and parse from there.
        payload = (
            "build_channel_package: staged 59 files into /tmp/_bundle\n"
            + json.dumps(
                [
                    {
                        "files": [
                            {"path": "package.json"},
                            {"path": "quality_playbook_cli/_bundle/SKILL.md"},
                        ]
                    }
                ]
            )
        )
        log_fh = io.StringIO()
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=0, stdout=payload, stderr=""
            )
            ok, msg, files = publish_npm.npm_pack_dry_run(
                Path("/fake"), "/usr/local/bin/npm", log_fh
            )
        self.assertTrue(ok, f"expected ok, got: {msg}")
        self.assertIn("SKILL.md", "\n".join(files))

    def test_stdout_with_no_bracket_fails_with_clear_error(self) -> None:
        # Degenerate case: stdout contains no '[' at all. Function
        # should return False with an error citing the stdout snippet.
        log_fh = io.StringIO()
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=0, stdout="nothing useful here\n", stderr=""
            )
            ok, msg, files = publish_npm.npm_pack_dry_run(
                Path("/fake"), "/usr/local/bin/npm", log_fh
            )
        self.assertFalse(ok)
        self.assertIn("no '['", msg)
        self.assertIn("nothing useful here", msg)

    def test_log_captures_full_unmodified_stdout(self) -> None:
        # Log captures unmodified stdout (including any pollution) for
        # post-mortem, even when we strip the prefix for parsing.
        polluted = "PREPACK NOISE\n" + json.dumps(
            [{"files": [{"path": "package.json"}]}]
        )
        log_fh = io.StringIO()
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(
                returncode=0, stdout=polluted, stderr=""
            )
            publish_npm.npm_pack_dry_run(
                Path("/fake"), "/usr/local/bin/npm", log_fh
            )
        log_contents = log_fh.getvalue()
        self.assertIn("PREPACK NOISE", log_contents)


class NpmPackRoundTripStdoutTests(unittest.TestCase):
    """Real round-trip against the on-disk package.json + prepack
    script — NOT a mock. Closes the test-coverage gap that let the
    prepack-stdout-pollution bug ship in 202. Skips if npm or python3
    aren't on PATH (CI without npm).
    """

    def test_npm_pack_dry_run_stdout_is_pure_json(self) -> None:
        import shutil as _shutil  # local import; module's top doesn't
        npm = _shutil.which("npm")
        py = _shutil.which("python3")
        if npm is None or py is None:
            self.skipTest("npm or python3 not on PATH")
        repo_root = Path(__file__).resolve().parents[2]
        if not (repo_root / "package.json").is_file():
            self.skipTest("package.json not at repo root")
        import subprocess as _sub  # local; module-level subprocess
        r = _sub.run(
            [npm, "pack", "--dry-run", "--json"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        self.assertEqual(
            r.returncode,
            0,
            f"npm pack failed (exit {r.returncode}):\n"
            f"stdout={r.stdout[:500]}\nstderr={r.stderr[:500]}",
        )
        # The contract: stdout starts with '[' (possibly with leading
        # whitespace), i.e., is pure JSON. No prepack-progress prefix.
        self.assertTrue(
            r.stdout.lstrip().startswith("["),
            "npm pack stdout is NOT pure JSON — prepack stdout "
            "pollution detected. First 200 chars of stdout:\n"
            + repr(r.stdout[:200]),
        )
        # Parse + validate the contract.
        data = json.loads(r.stdout)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        first = data[0]
        self.assertIn("files", first)
        self.assertEqual(first.get("name"), "quality-playbook")


class ScanForForbiddenTests(unittest.TestCase):
    def test_pycache_fragment(self) -> None:
        hits = publish_npm._scan_for_forbidden(["foo/__pycache__/x.pyc"])
        self.assertEqual(len(hits), 1)

    def test_clean_paths(self) -> None:
        hits = publish_npm._scan_for_forbidden(
            ["package.json", "quality_playbook_cli/_bundle/SKILL.md"]
        )
        self.assertEqual(hits, [])

    def test_metrics_fragment(self) -> None:
        hits = publish_npm._scan_for_forbidden(["x/metrics/snapshot.json"])
        self.assertEqual(len(hits), 1)


class DryRunMainTests(unittest.TestCase):
    def test_dry_run_succeeds_on_clean_fake_repo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            (root / "bin").mkdir(exist_ok=True)
            (root / "bin" / "build_channel_package.py").write_text(
                "# fake\n", encoding="utf-8"
            )
            fake_home = root / "fakehome"
            fake_home.mkdir()
            with mock.patch.object(
                publish_npm, "__file__", str(root / "bin" / "publish_npm.py")
            ), mock.patch.object(
                Path, "home", return_value=fake_home
            ), mock.patch.object(
                publish_npm, "_resolve_npm", return_value="/usr/local/bin/npm"
            ), mock.patch.object(
                publish_npm, "_run"
            ) as m_run:
                def _fake_run(args, **kw):
                    a0 = args[0]
                    if a0 == "git" and "status" in args:
                        return mock.Mock(returncode=0, stdout="", stderr="")
                    if a0 == "git" and "tag" in args:
                        return mock.Mock(
                            returncode=0, stdout="v1.5.8\n", stderr=""
                        )
                    if a0.endswith("npm") or a0 == "/usr/local/bin/npm":
                        sub = args[1] if len(args) > 1 else ""
                        if sub == "whoami":
                            return mock.Mock(
                                returncode=0, stdout="andrewstellman\n",
                                stderr=""
                            )
                        if sub == "pack":
                            payload = json.dumps([{"files": [
                                {"path": "package.json"},
                                {"path": "quality_playbook_cli/_bundle/SKILL.md"},
                            ]}])
                            return mock.Mock(
                                returncode=0, stdout=payload, stderr=""
                            )
                    # build_channel_package.py --stage
                    return mock.Mock(returncode=0, stdout="ok\n", stderr="")
                m_run.side_effect = _fake_run
                rc = publish_npm.main(["--dry-run", "--skip-stage"])
            self.assertEqual(rc, publish_npm.EX_OK)
            log_dir = fake_home / ".qpb" / "publish_logs"
            self.assertTrue(log_dir.is_dir())
            logs = sorted(log_dir.glob("npm_1.5.8_*.log"))
            self.assertGreaterEqual(len(logs), 1)
            body = logs[-1].read_text(encoding="utf-8")
            self.assertIn("Pre-flight checks PASSED", body)

    def test_dry_run_halts_on_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, init_version="1.0.0")
            fake_home = root / "fakehome"
            fake_home.mkdir()
            with mock.patch.object(
                publish_npm, "__file__", str(root / "bin" / "publish_npm.py")
            ), mock.patch.object(
                Path, "home", return_value=fake_home
            ), mock.patch.object(publish_npm, "_run") as m_run:
                m_run.return_value = mock.Mock(
                    returncode=0, stdout="", stderr=""
                )
                rc = publish_npm.main(["--dry-run", "--skip-stage"])
        self.assertEqual(rc, publish_npm.EX_DATAERR)


class NoArgsBannerTests(unittest.TestCase):
    def test_no_args_prints_banner_returns_zero(self) -> None:
        buf = io.StringIO()
        with mock.patch("sys.stdout", new=buf):
            rc = publish_npm.main([])
        self.assertEqual(rc, publish_npm.EX_OK)
        out = buf.getvalue()
        self.assertIn("Quality Playbook v", out)
        self.assertIn("Role in a playbook run:", out)
        self.assertIn("by Andrew Stellman", out)


class ArgParseTests(unittest.TestCase):
    def test_dry_run_flag_recognized(self) -> None:
        ns = publish_npm.parse_args(["--dry-run"])
        self.assertTrue(ns.dry_run)

    def test_help_does_not_crash(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            with mock.patch("sys.stdout", new=io.StringIO()):
                publish_npm.parse_args(["--help"])
        self.assertEqual(cm.exception.code, 0)


class OtpHandlingTests(unittest.TestCase):
    """v1.5.8 instruction 205 — OTP flag pass-through to npm publish.
    Pins the 2FA support added after Andrew's v1.5.8 publish hit E403
    on the first npm publish attempt."""

    def test_otp_flag_parses(self) -> None:
        args = publish_npm.parse_args(["--publish", "--otp", "123456"])
        self.assertEqual(args.otp, "123456")

    def test_otp_default_is_none(self) -> None:
        args = publish_npm.parse_args(["--publish"])
        self.assertIsNone(args.otp)

    def test_npm_publish_includes_otp_when_provided(self) -> None:
        # When otp is non-empty, the npm publish subprocess invocation
        # must include --otp <code>.
        log_fh = io.StringIO()
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
            publish_npm.run_npm_publish(
                Path("/fake"), "/usr/local/bin/npm", "123456", log_fh
            )
        call_args = m_run.call_args[0][0]
        self.assertIn("--otp", call_args)
        self.assertIn("123456", call_args)

    def test_npm_publish_omits_otp_when_empty(self) -> None:
        # If OTP is empty / None, the npm publish invocation must
        # NOT include --otp at all (avoid passing --otp '').
        log_fh = io.StringIO()
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
            publish_npm.run_npm_publish(
                Path("/fake"), "/usr/local/bin/npm", None, log_fh
            )
        call_args = m_run.call_args[0][0]
        self.assertNotIn("--otp", call_args)
        # Also test the empty-string case explicitly.
        with mock.patch.object(publish_npm, "_run") as m_run2:
            m_run2.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
            publish_npm.run_npm_publish(
                Path("/fake"), "/usr/local/bin/npm", "", log_fh
            )
        call_args2 = m_run2.call_args[0][0]
        self.assertNotIn("--otp", call_args2)

    def test_log_does_not_contain_raw_otp(self) -> None:
        # The publish log captures the npm publish command line but
        # MUST redact the OTP value. Pass a recognizable OTP; verify
        # the log contains <REDACTED> but not the raw value.
        log_fh = io.StringIO()
        with mock.patch.object(publish_npm, "_run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
            publish_npm.run_npm_publish(
                Path("/fake"), "/usr/local/bin/npm", "654321", log_fh
            )
        log_contents = log_fh.getvalue()
        self.assertNotIn("654321", log_contents)
        self.assertIn("<REDACTED>", log_contents)


class PublishFlagTests(unittest.TestCase):
    """v1.5.8 — pin the --publish vs --dry-run affirmation semantics
    added in instruction 204. main() must require an explicit choice
    between dry-run and live publish; no-args prints intro; passing
    both is mutually exclusive; passing any non-affirmation flag alone
    (e.g. --skip-stage) must NOT trigger live publish."""

    def test_no_args_prints_intro_and_exits_zero(self) -> None:
        with mock.patch.object(sys, "argv", ["publish_npm"]):
            with mock.patch("sys.stdout", new=io.StringIO()):
                rc = publish_npm.main()
        self.assertEqual(rc, 0)

    def test_dry_run_and_publish_mutually_exclusive(self) -> None:
        captured_err = io.StringIO()
        with mock.patch.object(
            sys, "argv", ["publish_npm", "--dry-run", "--publish"]
        ):
            with mock.patch("sys.stderr", new=captured_err):
                rc = publish_npm.main()
        self.assertEqual(rc, publish_npm.EX_USAGE)
        self.assertIn("mutually exclusive", captured_err.getvalue())

    def test_skip_stage_alone_is_not_a_publish_trigger(self) -> None:
        # Passing --skip-stage alone (no --dry-run, no --publish) must
        # NOT trigger live publish. Pins the pre-204 regression where
        # any-flag-fell-through to the live path.
        captured_err = io.StringIO()
        with mock.patch.object(sys, "argv", ["publish_npm", "--skip-stage"]):
            with mock.patch("sys.stderr", new=captured_err):
                rc = publish_npm.main()
        self.assertEqual(rc, publish_npm.EX_USAGE)
        self.assertIn("must pass --dry-run or --publish", captured_err.getvalue())

    def test_publish_flag_parses_as_store_true(self) -> None:
        args = publish_npm.parse_args(["--publish"])
        self.assertTrue(args.publish)
        self.assertFalse(args.dry_run)

    def test_dry_run_flag_parses_as_store_true(self) -> None:
        args = publish_npm.parse_args(["--dry-run"])
        self.assertTrue(args.dry_run)
        self.assertFalse(args.publish)


if __name__ == "__main__":
    unittest.main()
