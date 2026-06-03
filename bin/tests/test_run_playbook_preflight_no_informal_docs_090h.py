"""v1.5.7 instruction 090h: retire `informal_docs/` — pre-flight
sentinel discovery must not require the retired sentinel.

Background: `bin/install_skill.py` no longer creates
`informal_docs/README.md` and `skill-template.gitignore` no longer
carries the `!informal_docs/README.md` rule. A LEGACY adopter who
previously appended the old skill-template.gitignore still has the
rule in their `.gitignore` — without a filter, the run_playbook
pre-flight `_discover_sentinel_files` would still list the retired
sentinel and every run would abort with "Required sentinel files
missing". The `_RETIRED_SENTINELS` filter in
`bin/run_playbook.py` is the upgrade-safe path.

This file tests the FILTER (the load-bearing coupling): a fresh
install discovers no informal_docs sentinel; a legacy-gitignore
install ALSO discovers no informal_docs sentinel (the filter
skips it); the `quality/RUN_INDEX.md` sentinel protection is
intact (a repo missing it still aborts).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bin import run_playbook


class DiscoverSentinelsTests(unittest.TestCase):
    """Pre-flight sentinel discovery: gitignore-driven; legacy
    informal_docs rule filtered."""

    def _write(self, repo: Path, gitignore_body: str) -> None:
        (repo / ".gitignore").write_text(gitignore_body,
                                         encoding="utf-8")

    def test_fresh_v157_gitignore_discovers_only_run_index(self) -> None:
        """Fresh adopter who appended the post-090h skill-template
        .gitignore: the only `!`-rule for a concrete file is
        `!quality/RUN_INDEX.md`."""
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            # The post-090h skill-template.gitignore body (rules
            # only, no header comments) — mirrors what an adopter
            # gets from `cat skill-template.gitignore >> .gitignore`.
            self._write(repo, (
                "docs_gathered/\n"
                "**/docs_gathered/\n"
                "quality/runs/\n"
                "!quality/RUN_INDEX.md\n"
                "quality/logs/\n"
            ))
            sentinels = run_playbook._discover_sentinel_files(repo)
            sentinel_strs = sorted(s.as_posix() for s in sentinels)
            self.assertEqual(sentinel_strs, ["quality/RUN_INDEX.md"])

    def test_legacy_gitignore_filters_retired_informal_docs(self) -> None:
        """Legacy adopter who appended the PRE-090h skill-template
        .gitignore: the rule `!informal_docs/README.md` is still in
        their `.gitignore`. The `_RETIRED_SENTINELS` filter MUST
        skip it so the discovered list contains ONLY
        `quality/RUN_INDEX.md` and the pre-flight does not abort.
        This is the load-bearing 090h upgrade-safety contract."""
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            # Pre-090h skill-template.gitignore body — both the
            # retired and the surviving negations.
            self._write(repo, (
                "informal_docs/*\n"
                "!informal_docs/README.md\n"
                "docs_gathered/\n"
                "quality/runs/\n"
                "!quality/RUN_INDEX.md\n"
            ))
            sentinels = run_playbook._discover_sentinel_files(repo)
            sentinel_strs = sorted(s.as_posix() for s in sentinels)
            self.assertEqual(sentinel_strs, ["quality/RUN_INDEX.md"],
                             "v1.5.7 090h: the retired "
                             "`informal_docs/README.md` sentinel "
                             "must be filtered out of legacy "
                             "gitignores so a v1.5.7-and-later run "
                             "does not abort.")

    def test_retired_sentinels_constant_includes_informal_docs(
            self) -> None:
        """The `_RETIRED_SENTINELS` frozenset MUST include
        `informal_docs/README.md`. Mutation bite: drop it from the
        set → `test_legacy_gitignore_filters_retired_informal_docs`
        fires."""
        self.assertIn("informal_docs/README.md",
                      run_playbook._RETIRED_SENTINELS)


class VerifySentinelsTests(unittest.TestCase):
    """`_verify_sentinels`: the function the pre-flight actually
    calls. Returns missing-sentinel paths or [] when all present."""

    def _make_repo(self, td: str, gitignore_body: str,
                   create_run_index: bool,
                   create_informal_docs: bool = False) -> Path:
        repo = Path(td)
        (repo / ".gitignore").write_text(gitignore_body,
                                         encoding="utf-8")
        if create_run_index:
            (repo / "quality").mkdir()
            (repo / "quality" / "RUN_INDEX.md").write_text(
                "# Run Index\n", encoding="utf-8")
        if create_informal_docs:
            (repo / "informal_docs").mkdir()
            (repo / "informal_docs" / "README.md").write_text(
                "# Informal\n", encoding="utf-8")
        return repo

    def test_fresh_install_with_run_index_no_informal_docs_passes(
            self) -> None:
        """The exact 090h regression case: a repo with
        `quality/RUN_INDEX.md` and NO `informal_docs/` directory
        must NOT abort. Mutation bite: re-add
        `informal_docs/README.md` to the sentinel-required list
        (e.g. drop it from `_RETIRED_SENTINELS`) → this test fires
        because the pre-flight reports `informal_docs/README.md`
        missing."""
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_repo(
                td,
                # Post-090h gitignore (no informal_docs rule).
                "quality/runs/\n!quality/RUN_INDEX.md\n",
                create_run_index=True,
                create_informal_docs=False)
            missing = run_playbook._verify_sentinels(repo)
            self.assertEqual(
                missing, [],
                f"Expected clean pre-flight, got missing: {missing}")

    def test_legacy_gitignore_no_informal_docs_dir_passes(self) -> None:
        """Legacy adopter (pre-090h gitignore) on a repo with NO
        `informal_docs/` directory: pre-flight must NOT abort. The
        `_RETIRED_SENTINELS` filter is the load-bearing
        upgrade-safety path."""
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_repo(
                td,
                # Pre-090h gitignore body — the retired rule is
                # still there; the directory is gone.
                "informal_docs/*\n!informal_docs/README.md\n"
                "quality/runs/\n!quality/RUN_INDEX.md\n",
                create_run_index=True,
                create_informal_docs=False)
            missing = run_playbook._verify_sentinels(repo)
            self.assertEqual(
                missing, [],
                f"Legacy gitignore + no informal_docs/: pre-flight "
                f"must not report missing sentinels, got: {missing}")

    def test_missing_run_index_still_aborts(self) -> None:
        """The `quality/RUN_INDEX.md` sentinel protection MUST
        remain after 090h. A repo whose `.gitignore` has
        `!quality/RUN_INDEX.md` but no file present aborts as
        before. This is the halt-condition: "Dropping the
        `quality/RUN_INDEX.md` sentinel or its pre-flight
        protection → self-halt"."""
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_repo(
                td,
                "quality/runs/\n!quality/RUN_INDEX.md\n",
                create_run_index=False,
                create_informal_docs=False)
            missing = run_playbook._verify_sentinels(repo)
            self.assertEqual(missing, ["quality/RUN_INDEX.md"])


if __name__ == "__main__":
    unittest.main()
