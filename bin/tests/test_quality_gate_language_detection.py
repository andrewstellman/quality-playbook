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

# v1.5.8 instruction 209: quality_gate.py now lives under the
# standard self-hosted marketplace layout at
# plugins/quality-playbook/skills/quality-playbook/scripts/. 208
# placed it at skills/quality-playbook/scripts/; that path is
# retained as a fallback for transitional clones.
_QPB_ROOT = Path(__file__).resolve().parents[2]
_GATE_DIR_209 = (
    _QPB_ROOT / "plugins" / "quality-playbook"
    / "skills" / "quality-playbook" / "scripts"
)
_GATE_DIR_208 = _QPB_ROOT / "skills" / "quality-playbook" / "scripts"
_GATE_DIR = _GATE_DIR_209 if _GATE_DIR_209.is_dir() else _GATE_DIR_208
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


# ---------------------------------------------------------------------------
# v1.5.10 instruction 056 — dominant-language-by-count + Clojure support.
# ---------------------------------------------------------------------------


def _clojure_deep_target(tmp: Path) -> Path:
    """vaelii-shaped Clojure repo: deep `.clj` source under the standard
    Leiningen layout `src/main/clojure/<ns>/` (namespace files at DEPTH
    5) plus a couple of SHALLOW stray `.py` build scripts (depth 2).

    Why this shape (not a flat clj-dominant tree): it reproduces the
    real adopter bug. At walk depth <=3 the deep `.clj` is never reached
    (the walk stops before `src/main/clojure/acme/`), so only the 2
    shallow `.py` get counted → the OLD ordered first-match (which also
    lacked any `clj` entry) mis-detects Python. At depth 5 the 4 `.clj`
    files ARE counted (4 > 2) → Clojure wins. Margin is deliberately
    realistic (4 vs 2), not lopsided."""
    for ns in ("core", "util", "routes"):
        f = tmp / "src" / "main" / "clojure" / "acme" / f"{ns}.clj"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"(ns acme.{ns})\n", encoding="utf-8")
    (tmp / "src" / "main" / "clojure" / "acme" / "db.cljc").write_text(
        "(ns acme.db)\n", encoding="utf-8")
    scripts = tmp / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "build.py").write_text("x = 1\n", encoding="utf-8")
    (scripts / "release.py").write_text("x = 1\n", encoding="utf-8")
    return tmp


def _ts_with_dist_target(tmp: Path) -> Path:
    """A TypeScript project (2 `.ts` under src/) whose compiled output
    (3 `.js`) lives in `dist/`. Under dominant-count `dist/` MUST be
    excluded or the compiled `.js` (3) out-counts the `.ts` (2) and
    flips detection to `js` (ordered first-match was immune because
    `ts` precedes `js`)."""
    src = tmp / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "index.ts").write_text("export const x = 1;\n", encoding="utf-8")
    (src / "app.ts").write_text("export const y = 2;\n", encoding="utf-8")
    dist = tmp / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    for n in ("index", "app", "vendor"):
        (dist / f"{n}.js").write_text("var z=1;\n", encoding="utf-8")
    return tmp


def _java_dominant_stray_py_target(tmp: Path) -> Path:
    """A Java project (3 `.java` under src/, depth 2 — within the walk)
    plus ONE stray `.py` tool in scripts/ (depth 2). Under dominant-count
    java (3) wins over py (1). Under the OLD ordered first-match `py`
    precedes `java`, so a single `.py` made detection return 'py'. This
    is the first-match-bite pin — distinct from the bundled-bin
    exclusion pin above (which excludes `bin/` both ways and so does NOT
    bite on a first-match revert)."""
    src = tmp / "src"
    src.mkdir(parents=True, exist_ok=True)
    for n in ("Alpha", "Beta", "Gamma"):
        (src / f"{n}.java").write_text(f"class {n} {{}}\n", encoding="utf-8")
    scripts = tmp / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "gen.py").write_text("x = 1\n", encoding="utf-8")
    return tmp


class DominantLanguageDetectionTests(unittest.TestCase):
    """v1.5.10 instruction 056: `detect_project_language` switched from
    ordered first-match to dominant-language-by-count (walk depth 5,
    known-extension counting only, build-output dirs excluded), with
    Clojure added to the tables + the hollow-test `lang_map`.

    MUTATION-VERIFY EVIDENCE (per ai_context/DEVELOPMENT_PROCESS.md;
    `__pycache__` purged between mutate/restore): reverting
    `detect_project_language` to the pre-056 ordered first-match body
    (the `for lang, ext in language_order: if present(...): return lang`
    form, with no `clj` entry) turns BOTH detection pins below red:
      - Clojure pin → first-match has no `clj` entry and finds the
        shallow `scripts/*.py` first → returns 'py' (AssertionError
        'py' != 'clj').
      - Java pin → first-match checks `py` before `java`; the lone
        `scripts/gen.py` is present → returns 'py' (AssertionError
        'py' != 'java').
    Bite executed during 056 development; PASS→FAIL→PASS confirmed."""

    def test_clojure_deep_source_beats_shallow_stray_py(self) -> None:
        with TemporaryDirectory() as t:
            target = _clojure_deep_target(Path(t))
            self.assertEqual(
                quality_gate.detect_project_language(str(target)), "clj",
                "deep .clj (depth 5) must out-count shallow stray .py",
            )

    def test_ts_project_excludes_build_output_dist(self) -> None:
        with TemporaryDirectory() as t:
            target = _ts_with_dist_target(Path(t))
            self.assertEqual(
                quality_gate.detect_project_language(str(target)), "ts",
                "dist/ compiled .js must be excluded so .ts dominates",
            )

    def test_java_dominant_over_stray_py_bites_first_match(self) -> None:
        with TemporaryDirectory() as t:
            target = _java_dominant_stray_py_target(Path(t))
            self.assertEqual(
                quality_gate.detect_project_language(str(target)), "java",
                "3 .java must out-count 1 stray .py (first-match returned py)",
            )

    def test_single_language_pins_unchanged(self) -> None:
        """Go / Rust / C / JS / TS single-language repos still detect
        correctly under dominant-count (regression pins)."""
        cases = {
            "go": "main.go", "rs": "lib.rs", "c": "core.c",
            "js": "app.js", "ts": "app.ts",
        }
        for lang, fname in cases.items():
            with self.subTest(lang=lang), TemporaryDirectory() as t:
                (Path(t) / fname).write_text("// x\n", encoding="utf-8")
                self.assertEqual(
                    quality_gate.detect_project_language(str(t)), lang,
                )

    def test_clj_lang_map_reachable_hollow_fails_real_passes(self) -> None:
        """Work item 4: the `lang_map` `clj` entry makes the hollow-test
        content check reachable for Clojure. A `(deftest ...)` with no
        `(is ...)` FAILs; one with `(is ...)` PASSes — proving the
        Clojure assertion patterns + `(deftest ...)` body extractor are
        not dead code."""
        with TemporaryDirectory() as t:  # hollow
            q = Path(t)
            (q / "test_functional.clj").write_text(
                "(ns acme.functional-test "
                "(:require [clojure.test :refer :all]))\n"
                "(deftest t-hollow)\n",
                encoding="utf-8",
            )
            quality_gate._reset_counters()
            quality_gate.check_functional_test_has_assertions(q)
            self.assertEqual(
                quality_gate.FAIL, 1,
                "a hollow Clojure deftest (no (is ...)) must FAIL",
            )
        with TemporaryDirectory() as t:  # real
            q = Path(t)
            (q / "test_functional.clj").write_text(
                "(ns acme.functional-test "
                "(:require [clojure.test :refer :all]))\n"
                "(deftest t-real (is (= 4 (+ 2 2))))\n",
                encoding="utf-8",
            )
            quality_gate._reset_counters()
            quality_gate.check_functional_test_has_assertions(q)
            self.assertEqual(
                quality_gate.FAIL, 0,
                "a Clojure deftest with (is ...) must PASS",
            )


if __name__ == "__main__":
    unittest.main()
