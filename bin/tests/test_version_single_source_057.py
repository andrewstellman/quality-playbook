"""v1.5.10 instruction 057 — version single-source consistency guard.

`SKILL.md` frontmatter `metadata.version` is THE single canonical
source of the skill version. Every other occurrence must derive from
it — read at runtime, or stamped at build/stage time. This guard reads
the frontmatter and asserts every derived location equals it; it FAILs
on any drift (the live failure mode that motivated 057: README had
already drifted to 1.5.10 while every other surface read 1.5.8).

Derived locations checked:
  - pyproject.toml `version`            (build-stamped)
  - package.json `version`              (build-stamped)
  - plugin.json `version`               (build-stamped)
  - README.md `**Version:**` badge      (build-stamped)
  - quality_playbook_cli.__version__    (runtime-derived)
  - benchmark_lib.RELEASE_VERSION       (runtime-derived)
  - staged _bundle/SKILL.md frontmatter (staged copy of the source)

DELIBERATELY EXCLUDED: `.claude-plugin/marketplace.json` — it is a
plugin *registry* (points at plugins by source path) and carries no
`version` field; the plugin's authoritative version lives in
plugin.json. Guarding a non-existent field would be vacuous, and adding
one would re-introduce the independent-literal drift 057 removes.

MUTATION-VERIFY EVIDENCE (per ai_context/DEVELOPMENT_PROCESS.md;
`__pycache__` purged between mutate/restore): hand-edit any one derived
location to a different version string (e.g. package.json `"version":
"9.9.9"`) → `test_all_derived_locations_match_frontmatter` FAILs with a
mismatch naming that file; restore → passes. Bite executed during 057
development; PASS→FAIL→PASS confirmed.
"""
from __future__ import annotations

import importlib
import json
import re
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_GATE_SCRIPTS = (
    _REPO / "plugins" / "quality-playbook"
    / "skills" / "quality-playbook" / "scripts"
)
if str(_GATE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_GATE_SCRIPTS))


def _frontmatter_version(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    block = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[:end]
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("version:"):
            return s.split(":", 1)[1].strip()
    raise AssertionError(f"no frontmatter version in {skill_md}")


def _pyproject_version() -> str:
    text = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version\s*=\s*"([^"]+)"', text,
                     re.MULTILINE).group(1)


def _json_version(path: Path) -> str:
    return json.loads(path.read_text(encoding="utf-8"))["version"]


def _readme_version() -> str:
    text = (_REPO / "README.md").read_text(encoding="utf-8")
    return re.search(r'^\*\*Version:\*\*\s*([^\s|]+)', text,
                     re.MULTILINE).group(1)


class VersionSingleSourceTests(unittest.TestCase):

    def setUp(self) -> None:
        self.frontmatter = _frontmatter_version(_REPO / "SKILL.md")

    def test_frontmatter_resolves(self) -> None:
        self.assertRegex(self.frontmatter, r"^\d+\.\d+\.\d+")

    def test_all_derived_locations_match_frontmatter(self) -> None:
        plugin_json = (
            _REPO / "plugins" / "quality-playbook"
            / ".claude-plugin" / "plugin.json"
        )
        # Runtime-derived values (imported fresh).
        import quality_playbook_cli
        importlib.reload(quality_playbook_cli)
        import benchmark_lib
        importlib.reload(benchmark_lib)

        derived = {
            "pyproject.toml": _pyproject_version(),
            "package.json": _json_version(_REPO / "package.json"),
            "plugin.json": _json_version(plugin_json),
            "README.md": _readme_version(),
            "quality_playbook_cli.__version__":
                quality_playbook_cli.__version__,
            "benchmark_lib.RELEASE_VERSION":
                benchmark_lib.RELEASE_VERSION,
        }
        mismatches = {
            name: val for name, val in derived.items()
            if val != self.frontmatter
        }
        self.assertEqual(
            mismatches, {},
            f"version drift from SKILL.md frontmatter "
            f"{self.frontmatter!r}: {mismatches}",
        )

    def test_staged_bundle_skill_md_matches_and_has_no_residual(self) -> None:
        """The staged `_bundle/SKILL.md` frontmatter equals the source,
        and the staged SKILL.md carries NO residual inline skill-version
        literal in its body (the source grep excludes _bundle, so an
        inline residual in the shipped bundle would otherwise go
        unchecked). The current skill-version string must appear in the
        staged SKILL.md exactly once — in the frontmatter — so no inline
        copy can silently disagree with it. (Historical `v1.4.x`
        examples / data `schema_version` values are a different string
        and a separate concept; they are not counted here.)"""
        from bin import build_channel_package as bcp
        with TemporaryDirectory() as t:
            dest = Path(t) / "_bundle"
            bcp.stage(_REPO, dest, clean=True)
            staged_skill = dest / "SKILL.md"
            self.assertTrue(staged_skill.is_file(),
                            "staged bundle must ship SKILL.md")
            self.assertEqual(
                _frontmatter_version(staged_skill), self.frontmatter,
            )
            # No residual inline occurrence of the CURRENT skill version
            # outside the frontmatter line (proves there's no inline
            # version that could disagree with frontmatter — the stale
            # NOTE described such inlines; 057 confirmed them gone).
            body = staged_skill.read_text(encoding="utf-8")
            occurrences = body.count(self.frontmatter)
            self.assertEqual(
                occurrences, 1,
                f"staged SKILL.md should carry the version {self.frontmatter!r} "
                f"exactly once (frontmatter only); found {occurrences} — "
                f"an inline residual would risk drift.",
            )


if __name__ == "__main__":
    unittest.main()
