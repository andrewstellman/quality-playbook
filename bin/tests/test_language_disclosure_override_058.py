"""v1.5.10 instruction 058 — language disclosure + `--language` override.

Covers, red->green and mutation-verified (see the per-test MUTATION
notes; mutation discipline per ai_context/DEVELOPMENT_PROCESS.md):

  D1  detect_project_languages() ranking + the singular delegate;
      BYTE-IDENTICAL-WINNER regression pin across every available
      baseline repo + vaelii (MANDATORY — the only Clojure repo) + a
      narrow-top-2-margin fixture (vaelii's 341:6 is too wide to
      exercise tiebreak drift).
  D5  disclosure threshold (below / over / exactly-at, >=-inclusive).
  D2  disclosure: conditional INDEX.md check (>=2-testable FAILs when
      omitted; single-testable PASSes) + the per-repo stdout block.
      DISCLOSURE VENUE: a real baseline repo qualifies (secbench2 =
      ts+py over threshold); a labeled fixture is the hermetic unit
      venue (no qualifying-repo dependence in CI).
  D3  --language override: respected (validates the override extension,
      records ran_on), unknown -> exit 2, no-flag == unchanged.
  056 clj substance deep-check is VERIFIED here (not rebuilt) — hollow
      `(deftest)` FAILs, real `(deftest ... (is ...))` passes.
  D4  archive-on-switch + the error-gate (both except branches): a
      differing --language archives+clears; a forced archive failure
      does NOT clear.
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

# Import the canonical gate module the same way the sibling
# language-detection tests do (v1.5.8 209 relocation + 208 fallback).
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

from bin import archive_lib  # noqa: E402
from bin import run_playbook  # noqa: E402

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_DISCLOSURE_FIXTURE = _FIXTURES / "multilang_disclosure"      # go=20 + py=8
_NARROW_MARGIN_FIXTURE = _FIXTURES / "narrow_margin_tiebreak"  # rs=6 == ts=6

# Baseline repos for the byte-identical pin + the disclosure venue.
_BASELINE_REPOS = {
    "chi": _QPB_ROOT / "repos" / "chi-1.5.8",
    "virtio": _QPB_ROOT / "repos" / "virtio-1.5.8",
    "express": _QPB_ROOT / "repos" / "express-1.5.8",
    "secbench2": _QPB_ROOT / "repos" / "secbench2",
}
_VAELII = Path("/Users/andrewstellman/git/vaelii-alpha")


# --- the frozen pre-058 winner oracle (independent of the live code) ---

def _old_detect_winner(repo_dir) -> str:
    """A frozen snapshot of the pre-058 detect_project_language
    algorithm (ordered language_order, depth-5 walk, the exact excluded
    set incl. _INSTALL_MARKER_DIRS, ``max(counts, key=(count,
    -order_index))``). Hardcoded so any drift in the live
    detect_project_languages walk/exclude/tiebreak makes the pin bite.
    """
    import os
    language_order = [
        ("go", ".go"), ("py", ".py"), ("java", ".java"), ("kt", ".kt"),
        ("rs", ".rs"), ("ts", ".ts"), ("js", ".js"), ("scala", ".scala"),
        ("c", ".c"), ("clj", ".clj"), ("clj", ".cljc"), ("clj", ".cljs"),
        ("agc", ".agc"),
    ]
    install_markers = {
        ".claude", ".cursor", ".github", ".continue",
        ".codex", ".windsurf", ".cline", ".aider", "bin",
    }
    excluded = ({"vendor", "node_modules", ".git", "quality", "repos",
                 "dist", "build", "out", "target"} | install_markers)
    ext_to_lang, order_index = {}, {}
    for idx, (lang, ext) in enumerate(language_order):
        ext_to_lang[ext] = lang
        order_index.setdefault(lang, idx)
    known_exts = set(ext_to_lang)
    counts: dict = {}
    stack = [(Path(repo_dir), 1)]
    while stack:
        curr, depth = stack.pop()
        try:
            for entry in os.scandir(curr):
                name = entry.name
                if entry.is_dir(follow_symlinks=False):
                    if name in excluded:
                        continue
                    if depth < 5:
                        stack.append((Path(entry.path), depth + 1))
                elif entry.is_file(follow_symlinks=False):
                    dot = name.rfind(".")
                    if dot >= 0 and name[dot:] in known_exts:
                        counts[ext_to_lang[name[dot:]]] = (
                            counts.get(ext_to_lang[name[dot:]], 0) + 1
                        )
        except (OSError, PermissionError):
            continue
    if not counts:
        return ""
    return max(counts, key=lambda lang: (counts[lang], -order_index[lang]))


class ByteIdenticalWinnerPinTests(unittest.TestCase):
    """D1 regression pin: detect_project_language's winner is
    byte-identical pre/post the plural refactor — the 056 clj winner's
    only protection rests on vaelii (no baseline repo is Clojure).

    MUTATION: change the live walk/exclude/tiebreak (e.g. flip the
    tiebreak to latest-wins, drop a build-output exclude, or change the
    depth) and a winner shifts away from the frozen oracle -> bite.
    Empirically: flipping the live sort key to ``(kv[1], order_index)``
    flips the narrow-margin fixture rs->ts.
    """

    def _assert_winner_matches_oracle(self, name: str, repo: Path) -> None:
        ranked = quality_gate.detect_project_languages(str(repo))
        winner = quality_gate.detect_project_language(str(repo))
        # delegate is exactly the plural's [0][0]
        self.assertEqual(winner, ranked[0][0] if ranked else "")
        self.assertEqual(
            winner, _old_detect_winner(str(repo)),
            f"{name}: post-058 winner {winner!r} != frozen pre-058 "
            f"oracle {_old_detect_winner(str(repo))!r}",
        )

    def test_vaelii_winner_byte_identical_MANDATORY(self) -> None:
        if not _VAELII.is_dir():
            self.skipTest(f"vaelii not present at {_VAELII}")
        self._assert_winner_matches_oracle("vaelii", _VAELII)
        # vaelii must detect clj (056) — the load-bearing assertion.
        self.assertEqual(
            quality_gate.detect_project_language(str(_VAELII)), "clj",
        )

    def test_narrow_margin_tiebreak_winner_byte_identical(self) -> None:
        self.assertTrue(_NARROW_MARGIN_FIXTURE.is_dir())
        self._assert_winner_matches_oracle(
            "narrow_margin", _NARROW_MARGIN_FIXTURE,
        )
        # exact tie rs=6==ts=6 -> tiebreak picks rs (earlier in order).
        self.assertEqual(
            quality_gate.detect_project_language(str(_NARROW_MARGIN_FIXTURE)),
            "rs",
        )

    def test_baseline_repos_winner_byte_identical(self) -> None:
        checked = []
        for name, repo in _BASELINE_REPOS.items():
            if not repo.is_dir():
                continue
            self._assert_winner_matches_oracle(name, repo)
            checked.append(name)
        self.assertTrue(
            checked,
            "no baseline repo present — at least one expected under repos/",
        )


class DetectProjectLanguagesExposureTests(unittest.TestCase):
    """D1: the plural exposes the full ranking; empty -> []."""

    def test_two_languages_ranked_and_delegate_matches(self) -> None:
        with TemporaryDirectory() as t:
            for i in range(20):
                (Path(t) / f"a{i}.go").write_text("package main\n")
            for i in range(8):
                (Path(t) / f"b{i}.py").write_text("x=1\n")
            ranked = quality_gate.detect_project_languages(t)
            self.assertEqual(ranked, [("go", 20), ("py", 8)])
            self.assertEqual(quality_gate.detect_project_language(t), "go")

    def test_empty_repo_returns_empty(self) -> None:
        with TemporaryDirectory() as t:
            self.assertEqual(quality_gate.detect_project_languages(t), [])
            self.assertEqual(quality_gate.detect_project_language(t), "")


class DisclosureThresholdTests(unittest.TestCase):
    """D5: >=10% AND >=5 files, >=-inclusive; denominator = sum(counts)."""

    @staticmethod
    def _ranked(go: int, py: int):
        out = []
        if go:
            out.append(("go", go))
        if py:
            out.append(("py", py))
        return out

    def test_below_threshold_does_not_fire(self) -> None:
        # py=4 (< 5 files) -> only go clears -> no disclosure
        self.assertFalse(quality_gate._disclosure_fires(self._ranked(45, 4)))
        # py=5 files but < 10% (5 / 100 = 5%) -> no disclosure
        self.assertFalse(quality_gate._disclosure_fires(self._ranked(95, 5)))

    def test_exactly_at_threshold_fires_inclusive(self) -> None:
        # py=5 files AND exactly 10% (5 / 50) -> fires (>=-inclusive)
        over = quality_gate.languages_over_disclosure_threshold(
            self._ranked(45, 5)
        )
        self.assertEqual(over, [("go", 45), ("py", 5)])
        self.assertTrue(quality_gate._disclosure_fires(self._ranked(45, 5)))

    def test_over_threshold_fires(self) -> None:
        self.assertTrue(quality_gate._disclosure_fires(self._ranked(20, 8)))


class DisclosureIndexConditionalTests(unittest.TestCase):
    """D2: the conditional INDEX.md disclosure check.

    MUTATION: delete the conditional block in
    check_v1_5_0_index_md -> the >=2-testable + missing-keys case stops
    producing a languages_detected FAIL -> test_two_lang_missing_fails
    bites.
    """

    _INDEX_MIN = (
        '```json\n'
        '{"schema_version": "2.0", "summary": %s}\n'
        '```\n'
    )

    def _run_index_check(self, repo: Path, summary_json: str):
        q = repo / "quality"
        q.mkdir(parents=True, exist_ok=True)
        (q / "INDEX.md").write_text(
            self._INDEX_MIN % summary_json, encoding="utf-8"
        )
        quality_gate._reset_counters()
        quality_gate.check_v1_5_0_index_md(q)
        return [rec for _, rec in quality_gate._FAIL_RECORDS]

    def _disclosure_fails(self, fails):
        return [f for f in fails if "languages_detected" in f
                or "untested_testable_languages" in f or "ran_on" in f]

    def test_two_lang_missing_disclosure_fails(self) -> None:
        with TemporaryDirectory() as t:
            repo = Path(t)
            for i in range(20):
                (repo / f"a{i}.go").write_text("package main\n")
            for i in range(8):
                (repo / f"b{i}.py").write_text("x=1\n")
            fails = self._run_index_check(
                repo,
                '{"requirements": {}, "bugs": {}, "gate_verdict": "pass"}',
            )
            self.assertTrue(
                self._disclosure_fails(fails),
                "a >=2-testable run whose INDEX omits the disclosure fields "
                "must FAIL",
            )

    def test_two_lang_with_disclosure_passes(self) -> None:
        with TemporaryDirectory() as t:
            repo = Path(t)
            for i in range(20):
                (repo / f"a{i}.go").write_text("package main\n")
            for i in range(8):
                (repo / f"b{i}.py").write_text("x=1\n")
            fails = self._run_index_check(
                repo,
                '{"requirements": {}, "bugs": {}, "gate_verdict": "pass", '
                '"languages_detected": {"go": 20, "py": 8}, '
                '"ran_on": "go", "untested_testable_languages": ["py"]}',
            )
            self.assertFalse(
                self._disclosure_fails(fails),
                "a >=2-testable run WITH the disclosure fields must not raise "
                "a disclosure FAIL",
            )

    def test_single_lang_without_disclosure_passes(self) -> None:
        with TemporaryDirectory() as t:
            repo = Path(t)
            for i in range(20):
                (repo / f"a{i}.go").write_text("package main\n")
            fails = self._run_index_check(
                repo,
                '{"requirements": {}, "bugs": {}, "gate_verdict": "pass"}',
            )
            self.assertFalse(
                self._disclosure_fails(fails),
                "a single-testable-language run must not require disclosure "
                "fields",
            )

    def test_legacy_schema_exempt(self) -> None:
        # schema_version "1.0" (legacy archive) -> exempt even with 2 langs
        with TemporaryDirectory() as t:
            repo = Path(t)
            for i in range(20):
                (repo / f"a{i}.go").write_text("package main\n")
            for i in range(8):
                (repo / f"b{i}.py").write_text("x=1\n")
            q = repo / "quality"
            q.mkdir(parents=True, exist_ok=True)
            (q / "INDEX.md").write_text(
                '```json\n'
                '{"schema_version": "1.0", "target_project_type": "Code", '
                '"summary": {"requirements": {}, "bugs": {}, '
                '"gate_verdict": "pass"}}\n```\n',
                encoding="utf-8",
            )
            quality_gate._reset_counters()
            quality_gate.check_v1_5_0_index_md(q)
            fails = [rec for _, rec in quality_gate._FAIL_RECORDS]
            self.assertFalse(self._disclosure_fails(fails))


class DisclosureStdoutBlockTests(unittest.TestCase):
    """D2: the per-repo stdout disclosure block (after RESULT)."""

    def _gate_stdout(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = quality_gate.main(argv)
        return code, buf.getvalue()

    def test_fixture_disclosure_block_emitted(self) -> None:
        # Hermetic venue: the labeled fixture (go=20 + py=8).
        self.assertTrue(_DISCLOSURE_FIXTURE.is_dir())
        _, out = self._gate_stdout([str(_DISCLOSURE_FIXTURE)])
        self.assertIn("LANGUAGES DETECTED (testable)", out)
        self.assertIn("go=20", out)
        self.assertIn("py=8", out)
        self.assertIn("TESTED: go", out)
        self.assertIn("TESTABLE LANGUAGES NOT TESTED: py", out)
        # the disclosure block trails RESULT: (additive)
        self.assertLess(
            out.index("RESULT:"), out.index("LANGUAGES DETECTED"),
        )
        # ...and the ::QPB:: sentinel still trails the disclosure block
        self.assertLess(
            out.index("LANGUAGES DETECTED"), out.index("::QPB::"),
        )

    def test_override_changes_tested_language_in_block(self) -> None:
        # --language py -> TESTED flips to py, untested becomes go
        _, out = self._gate_stdout(["--language", "py",
                                    str(_DISCLOSURE_FIXTURE)])
        self.assertIn("TESTED: py", out)
        self.assertIn("TESTABLE LANGUAGES NOT TESTED: go", out)

    def test_secbench2_real_repo_disclosure_venue(self) -> None:
        # Committed real-repo venue (D2 review #3): secbench2 = ts+py
        # both over threshold. Skips only if the repo is absent locally.
        repo = _BASELINE_REPOS["secbench2"]
        if not repo.is_dir():
            self.skipTest("secbench2 not present; fixture venue covers D2")
        ranked = quality_gate.detect_project_languages(str(repo))
        over = quality_gate.languages_over_disclosure_threshold(ranked)
        self.assertGreaterEqual(
            len(over), 2,
            "secbench2 is the named real-repo disclosure venue (ts+py)",
        )


class LanguageOverrideTests(unittest.TestCase):
    """D3: override respected, unknown -> exit 2, no-flag unchanged."""

    def test_override_validates_override_extension(self) -> None:
        # go-dominant repo, .py functional test, --language py -> PASS
        with TemporaryDirectory() as t:
            repo = Path(t)
            for i in range(10):
                (repo / f"a{i}.go").write_text("package main\n")
            q = repo / "quality"
            q.mkdir()
            (q / "test_functional.py").write_text("def test_x():\n  assert 1\n")
            buf = io.StringIO()
            quality_gate._reset_counters()
            with redirect_stdout(buf):
                quality_gate.check_test_file_extension(repo, q, language="py")
            out = buf.getvalue()
            self.assertEqual(
                quality_gate.FAIL, 0,
                "with --language py the .py test must validate as the target",
            )
            self.assertIn("ran_on=py", out)

    def test_without_override_detected_language_used(self) -> None:
        # same repo, no override -> go detected, .py test MISMATCHES -> FAIL
        with TemporaryDirectory() as t:
            repo = Path(t)
            for i in range(10):
                (repo / f"a{i}.go").write_text("package main\n")
            q = repo / "quality"
            q.mkdir()
            (q / "test_functional.py").write_text("def test_x():\n  assert 1\n")
            quality_gate._reset_counters()
            buf = io.StringIO()
            with redirect_stdout(buf):
                quality_gate.check_test_file_extension(repo, q)
            self.assertEqual(
                quality_gate.FAIL, 1,
                "without override, a .py test in a go repo must FAIL",
            )

    def test_unknown_language_exits_2(self) -> None:
        with TemporaryDirectory() as t:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = quality_gate.main(["--language", "cobol", t])
            self.assertEqual(code, 2)
            self.assertIn("not a known", buf.getvalue())

    def test_known_but_validates_via_lang_to_valid(self) -> None:
        # every _LANG_TO_VALID key is accepted (no exit 2)
        for lang in quality_gate._LANG_TO_VALID:
            with TemporaryDirectory() as t:
                # empty repo -> exit 1 (no repos resolved) but NOT 2
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = quality_gate.main(["--language", lang, t])
                self.assertNotEqual(
                    code, 2, f"--language {lang} must be accepted",
                )


class CljDeepCheckVerifyTests(unittest.TestCase):
    """056 clj substance — VERIFIED here, not rebuilt. The hollow-clj
    FAILs / real-clj passes contract already lives in
    test_quality_gate_language_detection.py:305-338; this is a light
    confirmation that the deep-check primitives are live (so 058 didn't
    disturb 056)."""

    def test_clj_assertion_substance_live(self) -> None:
        self.assertTrue(
            quality_gate._body_has_real_assertion(
                "(deftest t (is (= 1 1)))", "clj"
            )
        )
        self.assertFalse(
            quality_gate._body_has_real_assertion("(deftest t)", "clj")
        )
        self.assertEqual(
            quality_gate._clojure_test_function_bodies(
                "(deftest a (is 1)) (deftest b)"
            ),
            ["(deftest a (is 1))", "(deftest b)"],
        )


class ArchiveOnLanguageSwitchTests(unittest.TestCase):
    """D4: archive-on-switch + the error-gate (both except branches)."""

    def _make_live_run(self, repo: Path, language: str) -> Path:
        q = repo / "quality"
        q.mkdir(parents=True, exist_ok=True)
        (q / "BUGS.md").write_text("# BUGS\n", encoding="utf-8")
        (q / "INDEX.md").write_text(
            '```json\n{"schema_version": "2.0"}\n```\n', encoding="utf-8"
        )
        run_playbook._write_run_language(q, language)
        return q

    def test_switch_archives_and_clears(self) -> None:
        with TemporaryDirectory() as t:
            repo = Path(t)
            q = self._make_live_run(repo, "go")
            switched = run_playbook.archive_on_language_switch(repo, "py")
            self.assertTrue(switched)
            prev = q / archive_lib.ARCHIVE_DIRNAME
            self.assertTrue(prev.is_dir())
            self.assertTrue(any(prev.iterdir()),
                            "previous_runs/ must hold the archived run")
            # live cleared (BUGS.md gone) but the language sentinel updated
            self.assertFalse((q / "BUGS.md").exists())
            self.assertEqual(run_playbook._read_run_language(q), "py")

    def test_same_language_no_switch(self) -> None:
        with TemporaryDirectory() as t:
            repo = Path(t)
            q = self._make_live_run(repo, "go")
            self.assertFalse(run_playbook.archive_on_language_switch(repo, "go"))
            self.assertTrue((q / "BUGS.md").exists())

    def test_error_gate_archive_error_does_not_clear(self) -> None:
        # MUTATION: drop the ArchiveError return branch -> live cleared on
        # a failed archive -> this test bites (BUGS.md would vanish).
        with TemporaryDirectory() as t:
            repo = Path(t)
            q = self._make_live_run(repo, "go")
            orig = archive_lib.archive_run

            def _boom(*a, **k):
                raise archive_lib.ArchiveError("forced")

            archive_lib.archive_run = _boom
            try:
                switched = run_playbook.archive_on_language_switch(repo, "py")
            finally:
                archive_lib.archive_run = orig
            self.assertFalse(switched)
            self.assertTrue(
                (q / "BUGS.md").exists(),
                "a failed (ArchiveError) archive must NOT clear live data",
            )

    def test_error_gate_bare_exception_does_not_clear(self) -> None:
        # MUTATION: drop the bare-Exception return branch -> bite.
        with TemporaryDirectory() as t:
            repo = Path(t)
            q = self._make_live_run(repo, "go")
            orig = archive_lib.archive_run

            def _boom(*a, **k):
                raise RuntimeError("unexpected")

            archive_lib.archive_run = _boom
            try:
                switched = run_playbook.archive_on_language_switch(repo, "py")
            finally:
                archive_lib.archive_run = orig
            self.assertFalse(switched)
            self.assertTrue(
                (q / "BUGS.md").exists(),
                "any unexpected archive failure must NOT clear live data",
            )


if __name__ == "__main__":
    unittest.main()
