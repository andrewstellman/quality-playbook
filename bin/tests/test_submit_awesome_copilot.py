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
                rc = sub.main(["--dest", str(dest)])
        self.assertEqual(rc, sub.EX_OK)

    def test_main_halts_on_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_fake_repo(root, pkg_version="2.0.0")
            dest = root / "out"
            with mock.patch.object(
                sub, "__file__", str(root / "bin" / "submit_awesome_copilot.py")
            ), mock.patch("sys.stdout", new=io.StringIO()):
                rc = sub.main(["--dest", str(dest)])
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
                rc = sub.main(["--dest", str(dest)])
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


if __name__ == "__main__":
    unittest.main()
