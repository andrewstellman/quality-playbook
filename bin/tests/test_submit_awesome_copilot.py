"""v1.5.8 — tests for bin/submit_awesome_copilot.py.

The script is file-based (generates a submission packet for the
operator) rather than PR-based. Tests cover:

- Version-parity pre-flight check (pass + each kind of mismatch).
- Frontmatter parsing (round-trips QPB's SKILL.md frontmatter shape).
- Generated SKILL.md is well-formed (frontmatter delimiters + required
  fields).
- Generated PR body mentions the version + package name.
- Generated MANUAL_STEPS.md walks through fork → copy → validate → PR.
- ``submission.json`` is valid JSON pointing at the right files.
- End-to-end main() against a fake repo writes the four expected
  packet files.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bin import submit_awesome_copilot as sub  # noqa: E402


_SKILL_MD = """---
name: quality-playbook
description: "Run a complete quality engineering audit on any codebase. Trigger on 'quality playbook', 'spec audit'."
license: Complete terms in LICENSE.txt
metadata:
  version: 1.5.8
  author: Andrew Stellman
  github: https://github.com/andrewstellman/quality-playbook
---

# Quality Playbook Generator

(canonical body)
"""


def _make_fake_repo(
    root: Path,
    *,
    py_version: str = "1.5.8",
    pkg_version: str = "1.5.8",
    init_version: str = "1.5.8",
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
    (root / "SKILL.md").write_text(_SKILL_MD, encoding="utf-8")


class CheckVersionParityTests(unittest.TestCase):
    def test_parity_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            ok, msg, ver = sub.check_version_parity(root)
        self.assertTrue(ok, msg)
        self.assertEqual(ver, "1.5.8")

    def test_pyproject_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, py_version="9.9.9")
            ok, msg, ver = sub.check_version_parity(root)
        self.assertFalse(ok)
        self.assertIsNone(ver)
        self.assertIn("MISMATCH", msg)

    def test_missing_init_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            (root / "quality_playbook_cli" / "__init__.py").unlink()
            ok, msg, ver = sub.check_version_parity(root)
        self.assertFalse(ok)
        self.assertIn("Missing", msg)


class ReadFrontmatterTests(unittest.TestCase):
    def test_canonical_frontmatter_parses(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "SKILL.md"
            p.write_text(_SKILL_MD, encoding="utf-8")
            fm = sub.read_skill_frontmatter(p)
        self.assertEqual(fm.get("name"), "quality-playbook")
        self.assertIn("quality playbook", fm.get("description", "").lower())

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            sub.read_skill_frontmatter(Path("/nonexistent/SKILL.md"))

    def test_missing_delimiter_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "SKILL.md"
            p.write_text("# no frontmatter here\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                sub.read_skill_frontmatter(p)

    def test_unclosed_delimiter_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "SKILL.md"
            p.write_text(
                "---\nname: foo\n# never closed\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                sub.read_skill_frontmatter(p)


class GenerateSkillMdTests(unittest.TestCase):
    def test_skill_md_has_required_fields(self) -> None:
        fm = {
            "name": "quality-playbook",
            "description": 'Trigger on "quality playbook".',
        }
        out = sub.generate_trimmed_skill_md("1.5.8", fm)
        self.assertTrue(out.startswith("---"))
        # Two delimiters: opening + closing of frontmatter.
        self.assertGreaterEqual(out.count("\n---\n"), 1)
        self.assertIn("name: quality-playbook", out)
        self.assertIn("license: Apache-2.0", out)
        self.assertIn("compatibility:", out)
        self.assertIn('version: "1.5.8"', out)
        self.assertIn("# Quality Playbook", out)
        self.assertIn("pip install quality-playbook", out)
        self.assertIn(
            "https://github.com/andrewstellman/quality-playbook", out
        )

    def test_description_double_quotes_escaped(self) -> None:
        fm = {
            "name": "quality-playbook",
            "description": 'Has a "quoted" word.',
        }
        out = sub.generate_trimmed_skill_md("1.5.8", fm)
        # The description line must keep its outer double quotes intact.
        desc_line = [
            ln for ln in out.splitlines() if ln.startswith("description:")
        ][0]
        # Outer wrap must still be double quotes.
        self.assertTrue(desc_line.startswith('description: "'))
        self.assertTrue(desc_line.endswith('"'))


class GeneratePrBodyTests(unittest.TestCase):
    def test_pr_body_mentions_version_and_package(self) -> None:
        body = sub.generate_pr_body("1.5.8", {"description": "x"})
        self.assertIn("1.5.8", body)
        self.assertIn("quality-playbook", body)
        self.assertIn("pip install quality-playbook", body)
        self.assertIn("npx quality-playbook", body)


class GenerateManualStepsTests(unittest.TestCase):
    def test_manual_steps_covers_full_flow(self) -> None:
        steps = sub.generate_manual_steps("1.5.8")
        # The packet's flow: fork, branch, copy in, validate, push,
        # gh pr create.
        for expected in (
            "gh repo fork",
            "checkout -b",
            "skills/quality-playbook",
            "npm run skill:validate",
            "npm run build",
            "gh pr create",
            "PR_BODY.md",
            "1.5.8",
        ):
            self.assertIn(expected, steps, f"missing: {expected!r}")


class WritePacketTests(unittest.TestCase):
    def test_packet_files_written(self) -> None:
        fm = {
            "name": "quality-playbook",
            "description": "test description",
        }
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            sub.write_packet(dest, "1.5.8", fm)
        # Re-open in a fresh tempdir context since the dir was deleted.
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            sub.write_packet(dest, "1.5.8", fm)
            self.assertTrue((dest / "skills" / "quality-playbook" / "SKILL.md").is_file())
            self.assertTrue((dest / "PR_BODY.md").is_file())
            self.assertTrue((dest / "MANUAL_STEPS.md").is_file())
            self.assertTrue((dest / "submission.json").is_file())
            data = json.loads((dest / "submission.json").read_text(encoding="utf-8"))
            self.assertEqual(data["registry"], "github/awesome-copilot")
            self.assertEqual(data["skill_name"], "quality-playbook")
            self.assertEqual(data["version"], "1.5.8")
            self.assertEqual(
                data["files"]["skill_md"],
                "skills/quality-playbook/SKILL.md",
            )


class MainEndToEndTests(unittest.TestCase):
    def test_main_writes_packet(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            dest = root / "out"
            with mock.patch.object(
                sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")
            ), mock.patch("sys.stdout", new=io.StringIO()):
                # v1.5.8 instruction 206: --dry-run XOR --submit required.
                rc = sub.main(["--dry-run", "--dest", str(dest)])
        self.assertEqual(rc, sub.EX_OK)

    def test_main_halts_on_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, pkg_version="2.0.0")
            dest = root / "out"
            with mock.patch.object(
                sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")
            ), mock.patch("sys.stdout", new=io.StringIO()):
                rc = sub.main(["--dry-run", "--dest", str(dest)])
        self.assertEqual(rc, sub.EX_DATAERR)

    def test_main_halts_on_missing_skill_md(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            (root / "SKILL.md").unlink()
            dest = root / "out"
            with mock.patch.object(
                sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")
            ), mock.patch("sys.stdout", new=io.StringIO()):
                rc = sub.main(["--dry-run", "--dest", str(dest)])
        self.assertEqual(rc, sub.EX_DATAERR)

    def test_main_no_args_prints_banner(self) -> None:
        """No-args path prints the 089x intro and returns 0 without
        generating a packet (per the no-side-effects invariant)."""
        buf = io.StringIO()
        with mock.patch("sys.stdout", new=buf):
            rc = sub.main([])
        self.assertEqual(rc, sub.EX_OK)
        out = buf.getvalue()
        self.assertIn("Quality Playbook v", out)
        self.assertIn("Role in a playbook run:", out)


class ArgParseTests(unittest.TestCase):
    def test_default_dest_resolves(self) -> None:
        ns = sub.parse_args([])
        self.assertIsNone(ns.dest)

    def test_custom_dest(self) -> None:
        ns = sub.parse_args(["--dest", "/tmp/foo"])
        self.assertEqual(ns.dest, "/tmp/foo")

    def test_help_does_not_crash(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            with mock.patch("sys.stdout", new=io.StringIO()):
                sub.parse_args(["--help"])
        self.assertEqual(cm.exception.code, 0)


class SubmitFlagTests(unittest.TestCase):
    """v1.5.8 instruction 206 — automate the fork-and-PR steps via
    --submit. Pins the flag affirmation (XOR with --dry-run) and the
    automation step sequence. Subprocess calls are mocked; we assert
    on the call order + arguments, not on actual gh/npm/git
    invocations.
    """

    # -- helpers ----------------------------------------------------------

    def _make_completed(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> mock.MagicMock:
        cp = mock.MagicMock()
        cp.returncode = returncode
        cp.stdout = stdout
        cp.stderr = stderr
        return cp

    def _patch_subprocess(self, responses):
        """Patch subprocess.run inside the script module with a stateful
        responder. ``responses`` is a callable mapping argv -> CompletedProcess.
        Returns the patcher's mock plus the call-log list."""
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), dict(kwargs)))
            cp = responses(list(args), kwargs)
            return cp

        return mock.patch.object(sub.subprocess, "run", side_effect=fake_run), calls

    def _stub_log_open(self, root: Path):
        """Force _open_log to write inside a tempdir so tests don't pollute
        ~/.qpb/submit_logs."""
        log_dir = root / "submit_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        def fake_open_log(version):
            p = log_dir / f"awesome_copilot_{version}.log"
            return p, p.open("w", encoding="utf-8")

        return mock.patch.object(sub, "_open_log", side_effect=fake_open_log)

    # -- flag-affirmation tests ------------------------------------------

    def test_no_args_prints_intro_and_exits_zero(self) -> None:
        buf = io.StringIO()
        with mock.patch("sys.stdout", new=buf):
            rc = sub.main([])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("Quality Playbook v", out)
        self.assertIn("--dry-run", out)
        self.assertIn("--submit", out)

    def test_dry_run_and_submit_mutually_exclusive(self) -> None:
        stderr = io.StringIO()
        with mock.patch("sys.stderr", new=stderr):
            rc = sub.main(["--dry-run", "--submit"])
        self.assertEqual(rc, sub.EX_USAGE)
        self.assertIn("mutually exclusive", stderr.getvalue())

    def test_neither_flag_errors_with_must_affirm(self) -> None:
        # Pass only --dest, which is a real flag but doesn't satisfy the
        # XOR gate.
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("sys.stderr", new=stderr):
                rc = sub.main(["--dest", td])
        self.assertEqual(rc, sub.EX_USAGE)
        self.assertIn("must pass --dry-run or --submit", stderr.getvalue())

    # -- submission-step tests -------------------------------------------

    def test_submit_calls_gh_fork_when_fork_path_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            fork_path = root / "no-such-fork"  # absent on purpose
            packet = root / "out"

            # Responder: gh auth status OK; gh repo fork "creates" the dir
            # (we simulate by writing .git/ + package.json); subsequent
            # git/npm calls return 0.
            def responder(args, kwargs):
                if args[:3] == ["gh", "auth", "status"]:
                    return self._make_completed(0, "Logged in")
                if args[:3] == ["gh", "repo", "fork"]:
                    # Simulate the fork being cloned to fork_path.
                    fork_path.mkdir(parents=True, exist_ok=True)
                    (fork_path / ".git").mkdir(exist_ok=True)
                    (fork_path / "package.json").write_text("{}", encoding="utf-8")
                    return self._make_completed(0, "Cloned to " + str(fork_path))
                # Everything else: 0 / empty stdout-stderr.
                # For `git remote get-url upstream`: pretend upstream missing.
                if args[:4] == ["git", "remote", "get-url", "upstream"]:
                    return self._make_completed(1, "", "no such remote")
                # rev-parse upstream/staged for branch existence
                if args[:3] == ["git", "rev-parse", "upstream/staged"]:
                    return self._make_completed(0, "deadbeef\n")
                # branch existence rev-parse: pretend not present
                if len(args) >= 4 and args[0] == "git" and args[1] == "rev-parse" and args[2] == "--verify":
                    return self._make_completed(1, "", "no such ref")
                # default for npm install / npm start
                return self._make_completed(0, "ok")

            patcher, calls = self._patch_subprocess(responder)
            with patcher, self._stub_log_open(root), \
                    mock.patch.object(sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")), \
                    mock.patch.object(sub, "_confirm", side_effect=[False]), \
                    mock.patch("sys.stdout", new=io.StringIO()):
                rc = sub.main([
                    "--submit",
                    "--dest", str(packet),
                    "--fork-path", str(fork_path),
                ])
            # We expect the script to halt at the first confirmation gate
            # (which is step 6 commit+push, since fork was created clean,
            # branch created, npm start mocked OK). The presence of the
            # gh fork call is what we're pinning.
            gh_fork_calls = [c for c in calls if c[0][:3] == ["gh", "repo", "fork"]]
            self.assertEqual(
                len(gh_fork_calls), 1,
                f"expected exactly 1 `gh repo fork` call; got {len(gh_fork_calls)} of {len(calls)}",
            )
            self.assertIn(sub.AWESOME_COPILOT_REPO, gh_fork_calls[0][0])
            # Returned non-OK (we declined the commit gate) — script halts EX_SOFTWARE.
            self.assertEqual(rc, sub.EX_SOFTWARE)

    def test_submit_skips_fork_when_path_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            packet = root / "out"
            fork_path = root / "existing-fork"
            fork_path.mkdir()
            (fork_path / ".git").mkdir()
            (fork_path / "package.json").write_text("{}", encoding="utf-8")
            (fork_path / "node_modules").mkdir()  # skip npm install

            def responder(args, kwargs):
                # No gh auth / gh fork should be called.
                if args[:3] == ["gh", "auth", "status"]:
                    self.fail("gh auth status should not be called when fork exists")
                if args[:3] == ["gh", "repo", "fork"]:
                    self.fail("gh repo fork should not be called when fork exists")
                if args[:4] == ["git", "remote", "get-url", "upstream"]:
                    return self._make_completed(
                        0, "https://github.com/github/awesome-copilot.git\n"
                    )
                if args[:3] == ["git", "rev-parse", "upstream/staged"]:
                    return self._make_completed(0, "abc123\n")
                if len(args) >= 3 and args[0] == "git" and args[1] == "rev-parse" and args[2] == "--verify":
                    return self._make_completed(1, "", "no ref")
                return self._make_completed(0, "ok")

            patcher, calls = self._patch_subprocess(responder)
            with patcher, self._stub_log_open(root), \
                    mock.patch.object(sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")), \
                    mock.patch.object(sub, "_confirm", side_effect=[False]), \
                    mock.patch("sys.stdout", new=io.StringIO()):
                rc = sub.main([
                    "--submit",
                    "--dest", str(packet),
                    "--fork-path", str(fork_path),
                ])
            gh_fork_calls = [c for c in calls if c[0][:3] == ["gh", "repo", "fork"]]
            self.assertEqual(len(gh_fork_calls), 0)
            # Declined at commit gate.
            self.assertEqual(rc, sub.EX_SOFTWARE)

    def test_submit_branch_create_uses_versioned_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            packet = root / "out"
            fork_path = root / "fork"
            fork_path.mkdir()
            (fork_path / ".git").mkdir()
            (fork_path / "package.json").write_text("{}", encoding="utf-8")
            (fork_path / "node_modules").mkdir()

            def responder(args, kwargs):
                if args[:4] == ["git", "remote", "get-url", "upstream"]:
                    return self._make_completed(
                        0, "https://github.com/github/awesome-copilot.git\n"
                    )
                if args[:3] == ["git", "rev-parse", "upstream/staged"]:
                    return self._make_completed(0, "abc123\n")
                if len(args) >= 3 and args[0] == "git" and args[1] == "rev-parse" and args[2] == "--verify":
                    return self._make_completed(1, "", "no ref")
                return self._make_completed(0, "ok")

            patcher, calls = self._patch_subprocess(responder)
            with patcher, self._stub_log_open(root), \
                    mock.patch.object(sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")), \
                    mock.patch.object(sub, "_confirm", side_effect=[False]), \
                    mock.patch("sys.stdout", new=io.StringIO()):
                sub.main([
                    "--submit",
                    "--dest", str(packet),
                    "--fork-path", str(fork_path),
                ])
            checkout_calls = [
                c for c in calls
                if c[0][:3] == ["git", "checkout", "-b"]
            ]
            self.assertEqual(
                len(checkout_calls), 1,
                f"expected exactly 1 `git checkout -b` call; got {len(checkout_calls)}",
            )
            argv = checkout_calls[0][0]
            self.assertEqual(argv, [
                "git", "checkout", "-b",
                f"add-{sub.SKILL_NAME}-1.5.8",
                "upstream/staged",
            ])

    def test_submit_halts_when_npm_start_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            packet = root / "out"
            fork_path = root / "fork"
            fork_path.mkdir()
            (fork_path / ".git").mkdir()
            (fork_path / "package.json").write_text("{}", encoding="utf-8")
            (fork_path / "node_modules").mkdir()

            def responder(args, kwargs):
                if args[:4] == ["git", "remote", "get-url", "upstream"]:
                    return self._make_completed(
                        0, "https://github.com/github/awesome-copilot.git\n"
                    )
                if args[:3] == ["git", "rev-parse", "upstream/staged"]:
                    return self._make_completed(0, "abc123\n")
                if len(args) >= 3 and args[0] == "git" and args[1] == "rev-parse" and args[2] == "--verify":
                    return self._make_completed(1, "", "no ref")
                if args[:2] == ["npm", "start"]:
                    return self._make_completed(
                        2, "stdout junk", "ERROR: skill:validate failed",
                    )
                return self._make_completed(0, "ok")

            patcher, calls = self._patch_subprocess(responder)
            with patcher, self._stub_log_open(root), \
                    mock.patch.object(sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")), \
                    mock.patch("sys.stdout", new=io.StringIO()):
                rc = sub.main([
                    "--submit",
                    "--dest", str(packet),
                    "--fork-path", str(fork_path),
                ])
            # No commit / push attempted because step 5 halted.
            commit_calls = [c for c in calls if c[0][:2] == ["git", "commit"]]
            push_calls = [c for c in calls if c[0][:2] == ["git", "push"]]
            self.assertEqual(commit_calls, [])
            self.assertEqual(push_calls, [])
            self.assertEqual(rc, sub.EX_SOFTWARE)

    def test_submit_skips_push_on_n_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            packet = root / "out"
            fork_path = root / "fork"
            fork_path.mkdir()
            (fork_path / ".git").mkdir()
            (fork_path / "package.json").write_text("{}", encoding="utf-8")
            (fork_path / "node_modules").mkdir()

            def responder(args, kwargs):
                if args[:4] == ["git", "remote", "get-url", "upstream"]:
                    return self._make_completed(
                        0, "https://github.com/github/awesome-copilot.git\n"
                    )
                if args[:3] == ["git", "rev-parse", "upstream/staged"]:
                    return self._make_completed(0, "abc123\n")
                if len(args) >= 3 and args[0] == "git" and args[1] == "rev-parse" and args[2] == "--verify":
                    return self._make_completed(1, "", "no ref")
                return self._make_completed(0, "ok")

            patcher, calls = self._patch_subprocess(responder)
            # First _confirm call is the commit+push gate. Return False.
            with patcher, self._stub_log_open(root), \
                    mock.patch.object(sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")), \
                    mock.patch.object(sub, "_confirm", side_effect=[False]), \
                    mock.patch("sys.stdout", new=io.StringIO()):
                rc = sub.main([
                    "--submit",
                    "--dest", str(packet),
                    "--fork-path", str(fork_path),
                ])
            self.assertEqual(rc, sub.EX_SOFTWARE)
            push_calls = [c for c in calls if c[0][:2] == ["git", "push"]]
            commit_calls = [c for c in calls if c[0][:2] == ["git", "commit"]]
            self.assertEqual(push_calls, [], "push must NOT run on N confirmation")
            self.assertEqual(commit_calls, [], "commit must NOT run on N confirmation")

    def test_submit_skips_pr_create_on_n_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            packet = root / "out"
            fork_path = root / "fork"
            fork_path.mkdir()
            (fork_path / ".git").mkdir()
            (fork_path / "package.json").write_text("{}", encoding="utf-8")
            (fork_path / "node_modules").mkdir()

            def responder(args, kwargs):
                if args[:4] == ["git", "remote", "get-url", "upstream"]:
                    return self._make_completed(
                        0, "https://github.com/github/awesome-copilot.git\n"
                    )
                if args[:3] == ["git", "rev-parse", "upstream/staged"]:
                    return self._make_completed(0, "abc123\n")
                if len(args) >= 3 and args[0] == "git" and args[1] == "rev-parse" and args[2] == "--verify":
                    return self._make_completed(1, "", "no ref")
                return self._make_completed(0, "ok")

            patcher, calls = self._patch_subprocess(responder)
            # First _confirm = commit+push gate (True), second = PR gate (False).
            with patcher, self._stub_log_open(root), \
                    mock.patch.object(sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")), \
                    mock.patch.object(sub, "_confirm", side_effect=[True, False]), \
                    mock.patch("sys.stdout", new=io.StringIO()):
                rc = sub.main([
                    "--submit",
                    "--dest", str(packet),
                    "--fork-path", str(fork_path),
                ])
            self.assertEqual(rc, sub.EX_SOFTWARE)
            pr_calls = [c for c in calls if c[0][:3] == ["gh", "pr", "create"]]
            self.assertEqual(pr_calls, [], "gh pr create must NOT run on N PR confirmation")
            # Push DID run because we confirmed step 6.
            push_calls = [c for c in calls if c[0][:2] == ["git", "push"]]
            self.assertEqual(len(push_calls), 1, "push should have run on Y commit gate")

    def test_submit_logs_redacted_pr_url_on_success(self) -> None:
        """All gates Yes; gh pr create returns a PR URL; the URL is
        printed to stdout / written to the log file."""
        pr_url = "https://github.com/github/awesome-copilot/pull/12345"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root)
            packet = root / "out"
            fork_path = root / "fork"
            fork_path.mkdir()
            (fork_path / ".git").mkdir()
            (fork_path / "package.json").write_text("{}", encoding="utf-8")
            (fork_path / "node_modules").mkdir()

            def responder(args, kwargs):
                if args[:4] == ["git", "remote", "get-url", "upstream"]:
                    return self._make_completed(
                        0, "https://github.com/github/awesome-copilot.git\n"
                    )
                if args[:3] == ["git", "rev-parse", "upstream/staged"]:
                    return self._make_completed(0, "abc123\n")
                if len(args) >= 3 and args[0] == "git" and args[1] == "rev-parse" and args[2] == "--verify":
                    return self._make_completed(1, "", "no ref")
                if args[:3] == ["gh", "pr", "create"]:
                    return self._make_completed(0, pr_url + "\n", "")
                return self._make_completed(0, "ok")

            patcher, calls = self._patch_subprocess(responder)
            stdout_buf = io.StringIO()
            log_path_holder = {}

            log_dir = root / "submit_logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            def fake_open_log(version):
                p = log_dir / f"awesome_copilot_{version}.log"
                log_path_holder["p"] = p
                return p, p.open("w", encoding="utf-8")

            with patcher, \
                    mock.patch.object(sub, "_open_log", side_effect=fake_open_log), \
                    mock.patch.object(sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")), \
                    mock.patch.object(sub, "_confirm", side_effect=[True, True]), \
                    mock.patch("sys.stdout", new=stdout_buf):
                rc = sub.main([
                    "--submit",
                    "--dest", str(packet),
                    "--fork-path", str(fork_path),
                ])
            self.assertEqual(rc, sub.EX_OK)
            pr_calls = [c for c in calls if c[0][:3] == ["gh", "pr", "create"]]
            self.assertEqual(len(pr_calls), 1, "exactly 1 gh pr create call expected")
            argv = pr_calls[0][0]
            self.assertIn("--repo", argv)
            self.assertIn(sub.AWESOME_COPILOT_REPO, argv)
            self.assertIn("--base", argv)
            self.assertIn("staged", argv)
            # PR URL surfaces in stdout AND in the log file.
            out = stdout_buf.getvalue()
            self.assertIn(pr_url, out)
            log_text = log_path_holder["p"].read_text(encoding="utf-8")
            self.assertIn(pr_url, log_text)


if __name__ == "__main__":
    unittest.main()
