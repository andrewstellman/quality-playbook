"""Regression test for the v1.5.7 Issue 2 fix (chi-surfaced):
run-start must detect when a target's installed skill bundle is a
stale snapshot missing files the current QPB source carries.

Reproduction (chi-1.5.1 sonnet run, Phase 4): the agent reported
"The references/what_just_happened.md file isn't present in the
repo" — that file was added to QPB source in instruction 037
(commit 7233b48) but the chi-1.5.1 target was installed via
setup_repos.sh BEFORE that commit, so the file is absent from
repos/chi-1.5.1/.github/skills/references/. The fix adds
`_check_installed_bundle_freshness`, called per-repo at run-start in
`execute_run`, emitting a non-fatal WARN.

Mutation-test evidence (in-tree per
`ai_context/DEVELOPMENT_PROCESS.md:152-160`; exercised during
instruction 044 development):

- `test_installed_bundle_freshness_warns_on_missing_file`
  Mutation: change the `if not (installed_dir / sf.name).is_file():`
  guard in `_check_installed_bundle_freshness` to `if False:`.
  Expected failure: `assertIn("references/what_just_happened.md",
  missing)` fires (empty list — the stale file is not detected).
  Restoration: passes. Bite verified.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import run_playbook


def _write(path: Path, content: str = "stub\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class InstalledBundleFreshnessTests(unittest.TestCase):
    """Pins the v1.5.7 Issue 2 invariant: a file present in QPB
    source's references/ / phase_prompts/ / agents/ but absent from
    the target's installed bundle is reported as missing."""

    def _make_qpb_source(self, root: Path) -> None:
        _write(root / "references" / "what_just_happened.md")
        _write(root / "references" / "verification.md")
        _write(root / "phase_prompts" / "phase1.md")
        _write(root / "agents" / "quality-playbook.agent.md")

    def _make_target_bundle(self, target: Path, *, include: set[str]) -> None:
        """Install a `.github/skills/` bundle (unambiguous nested
        layout). `include` is the set of '<subdir>/<name>' files to
        copy in; anything omitted simulates a stale snapshot."""
        skill_dir = target / ".github" / "skills"
        _write(skill_dir / "SKILL.md", "# installed skill snapshot\n")
        catalog = {
            "references/what_just_happened.md",
            "references/verification.md",
            "phase_prompts/phase1.md",
            "agents/quality-playbook.agent.md",
        }
        for rel in catalog & include:
            _write(skill_dir / rel)

    def test_installed_bundle_freshness_warns_on_missing_file(self) -> None:
        with TemporaryDirectory() as qtmp, TemporaryDirectory() as ttmp:
            qpb_root = Path(qtmp)
            target = Path(ttmp)
            self._make_qpb_source(qpb_root)
            # Stale snapshot: every file EXCEPT the instruction-037
            # addition references/what_just_happened.md.
            self._make_target_bundle(
                target,
                include={
                    "references/verification.md",
                    "phase_prompts/phase1.md",
                    "agents/quality-playbook.agent.md",
                },
            )

            missing = run_playbook._check_installed_bundle_freshness(
                qpb_root, target
            )

            self.assertIn(
                "references/what_just_happened.md", missing,
                "the stale snapshot is missing the instruction-037 "
                "file; freshness check must report it",
            )
            self.assertNotIn(
                "references/verification.md", missing,
                "files present in the bundle must NOT be reported",
            )
            self.assertNotIn("phase_prompts/phase1.md", missing)
            self.assertNotIn("agents/quality-playbook.agent.md", missing)

    def test_fresh_bundle_reports_nothing(self) -> None:
        with TemporaryDirectory() as qtmp, TemporaryDirectory() as ttmp:
            qpb_root = Path(qtmp)
            target = Path(ttmp)
            self._make_qpb_source(qpb_root)
            self._make_target_bundle(
                target,
                include={
                    "references/what_just_happened.md",
                    "references/verification.md",
                    "phase_prompts/phase1.md",
                    "agents/quality-playbook.agent.md",
                },
            )
            self.assertEqual(
                run_playbook._check_installed_bundle_freshness(
                    qpb_root, target
                ),
                [],
                "a complete bundle must report no missing files",
            )

    def test_no_installed_skill_reports_nothing(self) -> None:
        """A target with no installed QPB skill at all is out of
        scope — the freshness check must not fire (no bundle to
        compare against)."""
        with TemporaryDirectory() as qtmp, TemporaryDirectory() as ttmp:
            qpb_root = Path(qtmp)
            target = Path(ttmp)
            self._make_qpb_source(qpb_root)
            # No SKILL.md installed anywhere under target.
            self.assertEqual(
                run_playbook._check_installed_bundle_freshness(
                    qpb_root, target
                ),
                [],
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
