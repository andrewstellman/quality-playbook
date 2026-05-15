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

    def _make_qpb_source_with_bin(self, root: Path) -> None:
        """QPB source incl. the bundled bin/ modules
        install_skill._bundle_files copies (citation_verifier.py,
        reference_docs_ingest.py, benchmark_lib.py). SKILL.md +
        quality_gate.py are unconditional _bundle_files entries."""
        self._make_qpb_source(root)
        _write(root / "SKILL.md", "name: quality-playbook\n")
        _write(
            root / ".github" / "skills" / "quality_gate"
            / "quality_gate.py",
            "# gate\n",
        )
        _write(root / "bin" / "citation_verifier.py", "# cv\n")
        _write(root / "bin" / "reference_docs_ingest.py", "# ingest\n")
        _write(root / "bin" / "benchmark_lib.py", "# bench\n")

    def test_installed_bundle_freshness_warns_on_missing_bin_module(self) -> None:
        """v1.5.7 instruction 047 Item 2 (A-2-recast). A stale install
        missing bin/reference_docs_ingest.py (the actual root cause of
        the original A-2 codex Phase-1 failure) must now be reported
        by the freshness check, sourced from
        install_skill._bundle_files (NOT every *.py in QPB bin/).

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160): with the
        instruction-047 bin/ block deleted from
        _check_installed_bundle_freshness, this assertion fires
        (bin/reference_docs_ingest.py not in the returned list);
        restoring the block makes it pass. Bite verified during
        instruction 047 development.
        """
        with TemporaryDirectory() as qtmp, TemporaryDirectory() as ttmp:
            qpb_root = Path(qtmp)
            target = Path(ttmp)
            self._make_qpb_source_with_bin(qpb_root)
            skill_dir = target / ".github" / "skills"
            _write(skill_dir / "SKILL.md", "# installed snapshot\n")
            # Complete md trees so only the bin/ gap is exercised.
            for rel in (
                "references/what_just_happened.md",
                "references/verification.md",
                "phase_prompts/phase1.md",
                "agents/quality-playbook.agent.md",
            ):
                _write(skill_dir / rel)
            # Stale bin/: citation_verifier present, but the
            # instruction-046-diagnosed reference_docs_ingest.py +
            # benchmark_lib.py are MISSING (the exact A-2 shape).
            _write(skill_dir / "bin" / "citation_verifier.py")

            missing = run_playbook._check_installed_bundle_freshness(
                qpb_root, target
            )

            self.assertIn(
                "bin/reference_docs_ingest.py", missing,
                "the stale bundle is missing the Phase-1 ingest module "
                "(the A-2 root cause); freshness check must report it",
            )
            self.assertIn(
                "bin/benchmark_lib.py", missing,
                "reference_docs_ingest.py imports benchmark_lib; the "
                "missing transitive dep must also be reported",
            )
            self.assertNotIn(
                "bin/citation_verifier.py", missing,
                "a bin/ module present in the bundle must NOT be "
                "reported",
            )
            # md trees complete → no md-tree false positives.
            self.assertNotIn("references/what_just_happened.md", missing)

    def test_bin_check_noop_when_source_lacks_bundled_modules(self) -> None:
        """Defensive: if QPB source has no bundled bin/ modules
        (install_skill._bundle_files yields no bin/ entries), the bin/
        check is a no-op — no false positives, no crash."""
        with TemporaryDirectory() as qtmp, TemporaryDirectory() as ttmp:
            qpb_root = Path(qtmp)
            target = Path(ttmp)
            self._make_qpb_source(qpb_root)  # no bin/ modules
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
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
