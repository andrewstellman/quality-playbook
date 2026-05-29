"""v1.5.7 144 (Option 2 ruling) — smarter `docs` default: auto-pick
up gathered docs at the documented `docs_gathered/<repo>/`
convention.

`PlanRun.docs` defaults to ``"gather"`` (a no-op — Phase 1 falls
back to Tier-3 source-only). 144 makes that default smarter: if
docs exist at the documented convention
``<runs_root|./repos>/docs_gathered/<repo>/``, auto-use them; else
preserve the no-op. Explicit paths always pass through (operator
opt-in wins).

Per the 144 Option-2 ruling, ONLY ``docs_gathered/<repo>/`` is a
candidate (the source-of-truth setup_repos.sh reads from); the
versioned ``<repo>-<version>/reference_docs/`` mirrors are NOT
consulted (ambiguous across versions/.bak; the halt surfaced a
gson case where the mirror diverged from the gathered source).

`_resolve_docs_source` is a pure read-only function (the tested
seam); the only filesystem effect downstream is
`populate_reference_docs` copying the resolved dir, unchanged.
"""
from __future__ import annotations

import contextlib
import tempfile
import unittest
from pathlib import Path

from bin.harness.prepare import _resolve_docs_source

GSON = "https://github.com/google/gson"


def _mk(p: Path, *, files=("01_overview.md",)) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    for f in files:
        (p / f).write_text("x", encoding="utf-8")
    return p


class ResolveDocsSourceTests(unittest.TestCase):

    def test_explicit_path_returned_unchanged(self) -> None:
        # operator opt-in always wins — returned verbatim, existence
        # irrelevant.
        self.assertEqual(
            _resolve_docs_source("./some/path", GSON, Path("repos")),
            "./some/path")

    def test_gather_no_dirs_present_is_gather(self) -> None:
        with tempfile.TemporaryDirectory() as cwd, \
                contextlib.chdir(cwd):
            rr = Path(cwd) / "runs"
            rr.mkdir()
            self.assertEqual(
                _resolve_docs_source("gather", GSON, rr), "gather")

    def test_gather_picks_up_runs_root_docs_gathered(self) -> None:
        with tempfile.TemporaryDirectory() as cwd, \
                contextlib.chdir(cwd):
            rr = Path(cwd) / "runs"
            want = _mk(rr / "docs_gathered" / "gson")
            self.assertEqual(
                _resolve_docs_source("gather", GSON, rr), str(want))

    def test_gather_repos_fallback_when_no_runs_root(self) -> None:
        with tempfile.TemporaryDirectory() as cwd, \
                contextlib.chdir(cwd):
            want = _mk(Path("repos") / "docs_gathered" / "gson")
            self.assertEqual(
                _resolve_docs_source("gather", GSON, None), str(want))

    def test_priority_runs_root_wins_over_repos_fallback(self) -> None:
        """Both candidates exist → the runs_root candidate wins.
        Mutation-bite: swap the candidate list order ⇒ this fails."""
        with tempfile.TemporaryDirectory() as cwd, \
                contextlib.chdir(cwd):
            rr = Path(cwd) / "runs"
            runs_root_docs = _mk(rr / "docs_gathered" / "gson")
            _mk(Path("repos") / "docs_gathered" / "gson")  # fallback also exists
            got = _resolve_docs_source("gather", GSON, rr)
            self.assertEqual(got, str(runs_root_docs))
            self.assertNotIn("repos/docs_gathered", got)

    def test_empty_docs_gathered_dir_treated_as_not_present(
            self) -> None:
        # An existing-but-empty docs_gathered/<repo>/ must NOT be
        # picked up (it'd starve Phase 1 of its source fallback).
        with tempfile.TemporaryDirectory() as cwd, \
                contextlib.chdir(cwd):
            rr = Path(cwd) / "runs"
            (rr / "docs_gathered" / "gson").mkdir(parents=True)  # empty
            self.assertEqual(
                _resolve_docs_source("gather", GSON, rr), "gather")

    def test_repo_name_strips_git_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as cwd, \
                contextlib.chdir(cwd):
            rr = Path(cwd) / "runs"
            want = _mk(rr / "docs_gathered" / "bar")
            self.assertEqual(
                _resolve_docs_source(
                    "gather", "git@github.com:foo/bar.git", rr),
                str(want))

    def test_repo_name_lowercased(self) -> None:
        with tempfile.TemporaryDirectory() as cwd, \
                contextlib.chdir(cwd):
            rr = Path(cwd) / "runs"
            want = _mk(rr / "docs_gathered" / "bar")
            self.assertEqual(
                _resolve_docs_source(
                    "gather", "https://github.com/Foo/BAR", rr),
                str(want))

    def test_empty_repo_name_falls_through_safely(self) -> None:
        # A URL with no path segment → no crash, safe "gather".
        for bad in ("", "/", "https://github.com/"):
            with self.subTest(bad=bad):
                self.assertEqual(
                    _resolve_docs_source("gather", bad, Path("runs")),
                    "gather")


class LiveReposTreeTests(unittest.TestCase):
    """The 'would the smarter default work on Andrew's gathered
    fixtures' proof. Skips when the transient repos/ tree is absent
    (gitignored)."""

    _REPO_ROOT = Path(__file__).resolve().parents[3]

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[3]
         / "repos/docs_gathered/gson").is_dir(),
        "live repos/docs_gathered/gson not present")
    def test_resolver_finds_gson_docs_at_real_location(self) -> None:
        with contextlib.chdir(self._REPO_ROOT):
            resolved = _resolve_docs_source(
                "gather", GSON, Path("repos"))
        self.assertEqual(Path(resolved),
                         Path("repos/docs_gathered/gson"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
