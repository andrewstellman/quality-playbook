"""v1.5.7 157 — gitignore_remediation_followed becomes an outcome
check (reads target/.gitignore), not a stream-regex check.

Empirical motivation: 2026-05-29 ship-readiness retest's three
copilot runs all achieved the correct outcome (the target's
.gitignore contains the load-bearing entries from
skill-template.gitignore) via two different mechanisms:

  * keto  (201847Z/run-03) — canonical bash:
        `cat skill-template.gitignore >> .gitignore`
  * chi   (235425Z/run-06) — Edit tool (no `cat ... >>` in stream).
  * express (235425Z/run-05) — Write tool (no `cat ... >>` in stream).

Pre-157 stream-regex: keto ✓, chi/express ✗ (false-fail). Post-157
outcome check: all three ✓. The fix penalizes IMPROVISATION
(`printf '\\nquality/\\n' >> .gitignore`) as a quality bug
regardless of outcome, but accepts any other path that produces the
correct .gitignore content. When target_dir is unavailable, the
pre-157 stream-regex path remains as a fallback for back-compat.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bin.harness import facts as F


# ---------------------------------------------------------------------------
# Skill-template entries — sanity guard
# ---------------------------------------------------------------------------


class LoadBearingEntriesContractTests(unittest.TestCase):
    """Pin the 3-entry intersection at the module level so any future
    re-derive of the set from skill-template.gitignore is an explicit
    decision (not a silent regression)."""

    def test_load_bearing_entries_are_the_three_observed(
            self) -> None:
        self.assertEqual(
            F._GITIGNORE_LOAD_BEARING_ENTRIES,
            ("docs_gathered/", "**/docs_gathered/", "quality/runs/"))

    def test_load_bearing_entries_present_in_skill_template(
            self) -> None:
        # The 3 entries MUST appear in skill-template.gitignore;
        # otherwise we'd be checking for the wrong markers.
        repo_root = Path(__file__).resolve().parents[3]
        # v1.5.8 instruction 209: skill-template.gitignore lives
        # under the standard self-hosted marketplace plugin layout
        # alongside the rest of the bundle.
        template = (
            repo_root / "plugins" / "quality-playbook"
            / "skills" / "quality-playbook"
            / "skill-template.gitignore"
        )
        self.assertTrue(template.is_file())
        text = template.read_text(encoding="utf-8")
        for entry in F._GITIGNORE_LOAD_BEARING_ENTRIES:
            self.assertIn(entry, text, f"missing {entry!r}")


# ---------------------------------------------------------------------------
# _gitignore_outcome_check direct
# ---------------------------------------------------------------------------


class GitignoreOutcomeCheckTests(unittest.TestCase):

    def _write_gitignore(self, target: Path, lines) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / ".gitignore").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")

    def test_returns_true_when_all_three_entries_present(
            self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "t"
            self._write_gitignore(target, [
                "docs_gathered/", "**/docs_gathered/",
                "quality/runs/"])
            self.assertTrue(F._gitignore_outcome_check(target))

    def test_returns_true_with_extra_entries(self) -> None:
        # keto's full 25-line append (all 5 template entries + extra
        # project rules) trivially passes — the check looks for the
        # 3-entry intersection, not equality.
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "t"
            self._write_gitignore(target, [
                "# project rules", "node_modules/",
                "docs_gathered/", "**/docs_gathered/",
                "quality/runs/", "!quality/RUN_INDEX.md",
                "quality/logs/"])
            self.assertTrue(F._gitignore_outcome_check(target))

    def test_returns_false_when_one_entry_missing(self) -> None:
        # Mutation-bite: changing the `all(...)` to `any(...)` makes
        # this incorrectly pass.
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "t"
            self._write_gitignore(target, [
                "docs_gathered/", "**/docs_gathered/"])  # no quality/runs/
            self.assertFalse(F._gitignore_outcome_check(target))

    def test_returns_false_when_gitignore_absent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "t"
            target.mkdir()
            self.assertFalse(F._gitignore_outcome_check(target))

    def test_returns_false_when_target_dir_none(self) -> None:
        self.assertFalse(F._gitignore_outcome_check(None))

    def test_returns_false_when_target_dir_nonexistent(self) -> None:
        # Defensive: target_dir is a Path but doesn't exist on disk.
        self.assertFalse(
            F._gitignore_outcome_check(Path("/tmp/does-not-exist-157")))


# ---------------------------------------------------------------------------
# parse_transcript end-to-end — the combined logic
# ---------------------------------------------------------------------------


class ParseTranscriptGitignoreTests(unittest.TestCase):

    def test_outcome_check_overrides_stream_when_target_dir_supplied(
            self) -> None:
        # Stream has NO canonical `cat ... >>` line — pre-157 would
        # mark False. Post-157 with target_dir → reads .gitignore →
        # all 3 entries present → True.
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "t"
            target.mkdir()
            (target / ".gitignore").write_text(
                "docs_gathered/\n**/docs_gathered/\nquality/runs/\n",
                encoding="utf-8")
            transcript = "Read .gitignore\nRead skill-template.gitignore\nEdit .gitignore\n"
            _phase0, install, _b, _s = F.parse_transcript(
                transcript, target_dir=target)
            self.assertTrue(install.gitignore_remediation_followed)

    def test_improvisation_stream_overrides_outcome(self) -> None:
        # Even if the outcome (the .gitignore content) is correct, an
        # improvisation pattern in the stream marks the run as
        # not-followed — improvisation is a quality bug independent
        # of outcome (it usually means the runner didn't read the
        # template).
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "t"
            target.mkdir()
            (target / ".gitignore").write_text(
                "docs_gathered/\n**/docs_gathered/\nquality/runs/\n",
                encoding="utf-8")
            transcript = "$ printf \"\\nquality/\\n\" >> .gitignore\n"
            _phase0, install, _b, _s = F.parse_transcript(
                transcript, target_dir=target)
            self.assertFalse(install.gitignore_remediation_followed)

    def test_fallback_to_stream_regex_when_target_dir_none(
            self) -> None:
        # Back-compat: existing tests pass parse_transcript without
        # target_dir; the canonical regex still drives the result.
        transcript = (
            "$ cat /opt/playbook/skill-template.gitignore >> "
            "/tmp/target/.gitignore\n")
        _phase0, install, _b, _s = F.parse_transcript(transcript)
        self.assertTrue(install.gitignore_remediation_followed)

    def test_fallback_to_stream_regex_when_gitignore_missing(
            self) -> None:
        # target_dir provided but .gitignore not present → fall back
        # to stream-regex. Used by tests that mock target_dir without
        # populating the file.
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "t"
            target.mkdir()
            transcript = "$ cat skill-template.gitignore >> .gitignore\n"
            _phase0, install, _b, _s = F.parse_transcript(
                transcript, target_dir=target)
            self.assertTrue(install.gitignore_remediation_followed)


# ---------------------------------------------------------------------------
# Real-world empirical regression — the 2026-05-29 23:54 + 20:18 runs
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _real_world_target(rel: str) -> "Path | None":
    """Return ``<repo>/<rel>`` if it exists; else None (so the test
    skips when the dev tree's harness_runs/ has been pruned)."""
    p = _REPO_ROOT / rel
    return p if p.is_dir() else None


class RealWorldCopilotRunsRegressionTests(unittest.TestCase):
    """The empirical proof: all 3 copilot runs (which achieved correct
    outcomes via two different mechanisms) now show
    gitignore_remediation_followed=True. Pre-157, chi + express showed
    False even though their .gitignores were correct."""

    def _check(self, rel: str) -> None:
        target = _real_world_target(rel)
        if target is None:
            self.skipTest(
                f"{rel} not on disk (harness_runs/ pruned); skip")
        self.assertTrue(F._gitignore_outcome_check(target),
                        f"{rel}: outcome check should be True")

    def test_keto_201847Z_run_03_target_canonical_bash(self) -> None:
        self._check("harness_runs/20260529T201847Z/run-03/target")

    def test_chi_235425Z_run_06_target_edit_tool(self) -> None:
        # The bug regression test: pre-157 chi was False because
        # copilot used Edit instead of `cat ... >>`. Post-157 the
        # outcome check sees the correctly-appended .gitignore.
        self._check("harness_runs/20260529T235425Z/run-06/target")

    def test_express_235425Z_run_05_target_write_tool(self) -> None:
        self._check("harness_runs/20260529T235425Z/run-05/target")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
