"""v1.5.7 instruction 054 (A-10): the gate's two file-tree walkers
(`detect_project_language`, `count_source_files`) and
`classify_project()` must SKIP adopter install marker dirs + the
bundled `bin/` so QPB's own Python closure modules don't poison
language detection / source counts in non-Python adopter projects.

Live reproduction (gson opus-4.6 Mode-A run, 2026-05-16): a Java
project with QPB installed had `detect_project_language` return "py"
(Python is checked before Java in the priority list and QPB's
bundled `bin/*.py` were found first) → 2 spurious gate FAILs until
the agent self-patched the exclusion set mid-run (line 1003, adding
`.claude` and `bin`).

DEPTH-AWARE FIXTURE NOTE (verify-before-claim — deviates from the
instruction's prescribed fixture, with rationale): the instruction's
A-10.2 #1 fixture is `target/.claude/skills/quality-playbook/bin/
quality_playbook.py`. That file is at depth 5;
`detect_project_language` walks only **maxdepth 3** (and
`count_source_files` only **maxdepth 4**), so that fixture returns
"java"/count=1 REGARDLESS of the exclusion fix — the depth limit,
not the exclusion, decides it, so a mutation bite on the exclusion
would NOT flip it (it was empirically confirmed not to flip during
054 development). Shipping such a test would be a non-credible
mutation-evidence claim — exactly the
instruction-051/053-class defect this series exists to eliminate.

The CREDIBLE, bite-flippable reproductions (empirically mapped on
the pre-054 buggy gate during 054 development) are:
  - `detect_project_language` (maxdepth 3): the bundled `bin/` at
    INSTALL ROOT — the `setup_repos.sh` flat layout
    `target/bin/*.py` (depth 2). Buggy gate → "py"; fixed → "java".
  - `count_source_files` (maxdepth 4): the same root `bin/` (depth
    2) AND the install-marker skill dir with files at depth ≤4
    (`target/<marker>/skills/quality-playbook/quality_gate.py`,
    depth 4). Buggy gate → counts QPB's .py; fixed → counts only
    real source.
  - `classify_project`: `os.walk` is unbounded-depth (it prunes
    `DEFAULT_IGNORE_DIRS`), so the deep marker layout DOES reach
    QPB's .py — the per-marker deep fixture is credible here.

Each per-marker test loops over all 8 distinct install markers from
`bin/install_skill.AI_TOOL_MAP.values()`
(.claude .cursor .github .continue .codex .windsurf .cline .aider).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# v1.5.8 instruction 208: quality_gate.py moved to skills/quality-playbook/scripts/.
_QPB_ROOT = Path(__file__).resolve().parents[2]
_GATE_DIR = _QPB_ROOT / "skills" / "quality-playbook" / "scripts"
if str(_GATE_DIR) not in sys.path:
    sys.path.insert(0, str(_GATE_DIR))
import quality_gate  # noqa: E402

from bin.classify_project import classify_project  # noqa: E402
from bin.install_skill import AI_TOOL_MAP  # noqa: E402

_MARKERS = sorted({marker for marker, _ in AI_TOOL_MAP.values()})


def _flat_root_bin_target(tmp: Path) -> Path:
    """setup_repos.sh flat layout: a Java project with QPB's bundled
    bin/*.py at the install ROOT (depth 2 — within both walkers'
    depth limits). This is the credible detect_project_language
    reproduction (the gson 2-FAIL → 0-FAIL path)."""
    (tmp / "Foo.java").write_text("class Foo {}\n", encoding="utf-8")
    bin_dir = tmp / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "quality_playbook.py").write_text("pass\n", encoding="utf-8")
    (bin_dir / "archive_lib.py").write_text("pass\n", encoding="utf-8")
    return tmp


def _marker_skilldir_target(tmp: Path, marker: str) -> Path:
    """install_skill.py layout: a Java project with QPB installed
    under <marker>/skills/quality-playbook/. quality_gate.py lands
    directly in quality-playbook/ (depth 4 — reachable by
    count_source_files' maxdepth-4 walk and by classify_project's
    unbounded os.walk). bin/*.py is at depth 5 (deeper)."""
    (tmp / "Foo.java").write_text("class Foo {}\n", encoding="utf-8")
    skill = tmp / marker / "skills" / "quality-playbook"
    skill.mkdir(parents=True, exist_ok=True)
    # depth 4 file (count_source_files maxdepth-4 reaches this):
    (skill / "quality_gate.py").write_text("pass\n", encoding="utf-8")
    # depth 5 files (only classify_project's os.walk reaches these):
    binp = skill / "bin"
    binp.mkdir(parents=True, exist_ok=True)
    (binp / "quality_playbook.py").write_text("pass\n", encoding="utf-8")
    return tmp


class GateWalkerInstallExclusionTests(unittest.TestCase):
    """A-10: both gate walkers + classify_project skip the bundled
    bin/ and the adopter install marker dirs."""

    def test_language_detection_skips_bundled_bin_at_install_root(self) -> None:
        """`detect_project_language` returns the project's REAL
        language (java), not "py" from QPB's bundled bin/*.py at the
        install root (the setup_repos.sh flat layout — the credible,
        depth-3-reachable gson reproduction).

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-054
        A-10:
          Mutation: remove ``"bin"`` from
          `.github/skills/quality_gate/quality_gate.py:
          _INSTALL_MARKER_DIRS`.
          Expected failure: THIS test fails with
            AssertionError: 'py' != 'java'
          because the depth-3 walk reaches `target/bin/` (depth 2),
          finds `quality_playbook.py`, and Python precedes Java in
          `language_order`.
          Restoration: re-add ``"bin"``; passes.
          Bite executed during instruction-054 development;
          PASS→FAIL→PASS confirmed (the pre-054 buggy gate was
          empirically mapped: flat-root-bin → detect='py';
          __pycache__ purged between mutate and restore).
        """
        with TemporaryDirectory() as t:
            target = _flat_root_bin_target(Path(t))
            self.assertEqual(
                quality_gate.detect_project_language(str(target)), "java"
            )

    def test_count_source_files_skips_bundled_bin_at_install_root(self) -> None:
        """`count_source_files` counts only Foo.java — not QPB's two
        bundled .py modules in the root-level bin/ (depth 2)."""
        with TemporaryDirectory() as t:
            target = _flat_root_bin_target(Path(t))
            self.assertEqual(
                quality_gate.count_source_files(str(target)), 1
            )

    def test_count_source_files_skips_marker_skill_dir(self) -> None:
        """`count_source_files` (maxdepth 4) skips the install-marker
        skill dir — `<marker>/skills/quality-playbook/quality_gate.py`
        at depth 4 is reachable and would otherwise be counted.
        Loops all 8 markers."""
        for marker in _MARKERS:
            with self.subTest(marker=marker), TemporaryDirectory() as t:
                target = _marker_skilldir_target(Path(t), marker)
                self.assertEqual(
                    quality_gate.count_source_files(str(target)), 1,
                    f"marker={marker}: QPB's bundled .py (depth 4) were "
                    f"counted as adopter source",
                )

    def test_classify_project_skips_install_marker_dirs(self) -> None:
        """`classify_project` (unbounded os.walk pruning
        DEFAULT_IGNORE_DIRS) sees only Java — QPB's bundled Python at
        any depth under a marker does not appear in code_languages or
        inflate total_code_loc. Loops all 8 markers."""
        for marker in _MARKERS:
            with self.subTest(marker=marker), TemporaryDirectory() as t:
                target = _marker_skilldir_target(Path(t), marker)
                result = classify_project(target)
                self.assertEqual(
                    result["evidence"]["code_languages"], ["Java"],
                    f"marker={marker}: QPB's bundled Python leaked into "
                    f"classify_project's language breakdown",
                )
                self.assertEqual(
                    result["evidence"]["total_code_loc"], 1,
                    f"marker={marker}: QPB's bundled .py inflated "
                    f"total_code_loc",
                )


if __name__ == "__main__":
    unittest.main()
