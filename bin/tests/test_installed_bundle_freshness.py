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

    def _make_qpb_source_with_setup_repos(self, root: Path) -> None:
        """QPB source incl. bundled bin/ modules AND a synthetic
        repos/setup_repos.sh carrying the canonical
        `cp "${QPB_DIR}/bin/<x>" "${dst}/bin/<x>"` lines — the
        source of truth the freshness check parses for the
        setup_repos.sh layout."""
        self._make_qpb_source_with_bin(root)
        sr = root / "repos" / "setup_repos.sh"
        sr.parent.mkdir(parents=True, exist_ok=True)
        sr.write_text(
            "#!/usr/bin/env bash\n"
            'cp "${QPB_DIR}/bin/install_skill.py" "${dst}/bin/install_skill.py" 2>/dev/null || true\n'
            'cp "${QPB_DIR}/bin/citation_verifier.py" "${dst}/bin/citation_verifier.py" 2>/dev/null || true\n'
            'cp "${QPB_DIR}/bin/reference_docs_ingest.py" "${dst}/bin/reference_docs_ingest.py" 2>/dev/null || true\n'
            'cp "${QPB_DIR}/bin/benchmark_lib.py" "${dst}/bin/benchmark_lib.py" 2>/dev/null || true\n'
            'cp "${SCRIPT_DIR}/bin/run_playbook.sh" "${dst}/bin/run_playbook.sh"\n',
            encoding="utf-8",
        )

    def _make_qpb_source_050(self, root: Path) -> None:
        """instruction-050 superset: 049's setup_repos.sh source +
        the A-6.2 quality_playbook closure modules + __init__.py in
        bin/, phase_prompts/ + agents/ source, AND a synthetic
        setup_repos.sh whose cp lines include the closure (so the
        freshness check's two sources of truth — _bundle_files +
        parsed setup_repos.sh — both yield the closure as expected)."""
        self._make_qpb_source_with_setup_repos(root)
        for _m in (
            "__init__.py", "quality_playbook.py", "archive_lib.py",
            "council_semantic_check.py", "migrate_v1_5_0_layout.py",
            "role_map.py", "council_config.py",
        ):
            _write(root / "bin" / _m)
        _write(root / "phase_prompts" / "phase1.md")
        _write(root / "phase_prompts" / "phase2.md")
        _write(root / "agents" / "quality-playbook.agent.md")
        sr = root / "repos" / "setup_repos.sh"
        sr.write_text(
            sr.read_text(encoding="utf-8")
            + 'cp "${QPB_DIR}/bin/__init__.py" "${dst}/bin/__init__.py" 2>/dev/null || true\n'
            'cp "${QPB_DIR}/bin/quality_playbook.py" "${dst}/bin/quality_playbook.py" 2>/dev/null || true\n'
            'cp "${QPB_DIR}/bin/archive_lib.py" "${dst}/bin/archive_lib.py" 2>/dev/null || true\n'
            'cp "${QPB_DIR}/bin/council_semantic_check.py" "${dst}/bin/council_semantic_check.py" 2>/dev/null || true\n'
            'cp "${QPB_DIR}/bin/migrate_v1_5_0_layout.py" "${dst}/bin/migrate_v1_5_0_layout.py" 2>/dev/null || true\n'
            'cp "${QPB_DIR}/bin/role_map.py" "${dst}/bin/role_map.py" 2>/dev/null || true\n'
            'cp "${QPB_DIR}/bin/council_config.py" "${dst}/bin/council_config.py" 2>/dev/null || true\n',
            encoding="utf-8",
        )

    def test_freshness_auto_covers_closure_and_phase_prompts_050(self) -> None:
        """v1.5.7 instruction 050 A-7.3 + A-6.2.4. NO freshness-check
        code change was needed: the instruction-049 layout-agnostic
        design already (a) checks references/phase_prompts/agents at
        bundle_dir/<subdir> — which == target/.github/skills/<subdir>
        for a setup_repos.sh target, and (b) derives the expected
        bin/ set from install_skill._bundle_files + the parsed
        setup_repos.sh cp lines. Extending those two sources of truth
        (A-6.2.1 / A-6.2.2) automatically extends freshness coverage.
        This test PINS that auto-coverage so a future regression that
        narrows it is caught.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160): revert the
        instruction-050 A-6.2 closure block in
        install_skill._bundle_files() AND the closure cp lines in the
        synthetic setup_repos.sh (i.e. simulate the closure not being
        a bundle source of truth). Expected failure: this test's
        closure assertIns fire (the closure modules are no longer in
        the freshness expected set). Restore → passes. Bite verified
        during instruction 050 development.
        """
        with TemporaryDirectory() as qtmp, TemporaryDirectory() as ttmp:
            qpb_root = Path(qtmp)
            target = Path(ttmp)
            self._make_qpb_source_050(qpb_root)
            # setup_repos.sh-layout target: SKILL.md under
            # .github/skills/; bin/ at target root. Closure +
            # phase_prompts + agents ALL MISSING; only
            # citation_verifier present at target/bin/.
            _write(
                target / ".github" / "skills" / "SKILL.md",
                "# installed snapshot (setup_repos.sh layout)\n",
            )
            _write(target / "bin" / "citation_verifier.py")

            missing = run_playbook._check_installed_bundle_freshness(
                qpb_root, target
            )

            # A-6.2.4: closure modules reported (bin/ block; union of
            # _bundle_files + parsed setup_repos.sh; checked at
            # target/bin/ for the setup_repos.sh layout).
            for mod in (
                "bin/quality_playbook.py",
                "bin/archive_lib.py",
                "bin/council_semantic_check.py",
                "bin/migrate_v1_5_0_layout.py",
                "bin/role_map.py",
                "bin/council_config.py",
                "bin/__init__.py",
            ):
                self.assertIn(
                    mod, missing,
                    f"{mod} (quality_playbook closure) absent from a "
                    f"setup_repos.sh target must be reported (A-6.2.4 "
                    f"auto-coverage)",
                )
            # A-7.3: phase_prompts/ + agents/ reported (md-loop;
            # bundle_dir == target/.github/skills/ for setup_repos.sh).
            self.assertIn("phase_prompts/phase1.md", missing)
            self.assertIn(
                "agents/quality-playbook.agent.md", missing,
                "A-7.3: phase_prompts/agents absent from a "
                "setup_repos.sh target's .github/skills/ must be "
                "reported",
            )
            # No false positive on the one module that IS present.
            self.assertNotIn("bin/citation_verifier.py", missing)

    def test_freshness_detects_missing_bin_in_setup_repos_layout(self) -> None:
        """v1.5.7 instruction 049 A-2-recast-ext. setup_repos.sh
        installs SKILL.md at target/.github/skills/SKILL.md and bin/
        at target/bin/ (target root) — NOT bundle_dir/bin/. The
        instruction-047 check only looked at bundle_dir/bin/, so it
        missed (and would have false-positived on) setup_repos.sh
        targets. The freshness check must now scan target/bin/ too and
        report a module missing only if absent from BOTH locations.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160): replace the
        `for cand in (bundle_bin, target_bin):` candidate-location
        loop in _check_installed_bundle_freshness with
        `for cand in (bundle_bin,):` (the pre-049 install_skill.py-only
        behavior). Expected failure: this test's
        assertNotIn("bin/citation_verifier.py", missing) fires —
        citation_verifier.py (present at target/bin/ in the
        setup_repos.sh layout) is wrongly reported missing because
        only bundle_dir/bin/ was checked. Restore the two-location
        loop → passes. Bite verified during instruction 049
        development.
        """
        with TemporaryDirectory() as qtmp, TemporaryDirectory() as ttmp:
            qpb_root = Path(qtmp)
            target = Path(ttmp)
            self._make_qpb_source_with_setup_repos(qpb_root)
            # setup_repos.sh layout: SKILL.md under .github/skills/,
            # bin/ at the TARGET ROOT (not under .github/skills/).
            _write(
                target / ".github" / "skills" / "SKILL.md",
                "# installed snapshot (setup_repos.sh layout)\n",
            )
            # Stale target/bin/: citation_verifier present, the A-6
            # modules MISSING (the exact setup_repos.sh-target A-6
            # shape).
            _write(target / "bin" / "citation_verifier.py")
            _write(target / "bin" / "install_skill.py")
            _write(target / "bin" / "run_playbook.sh")

            missing = run_playbook._check_installed_bundle_freshness(
                qpb_root, target
            )

            self.assertIn(
                "bin/reference_docs_ingest.py", missing,
                "setup_repos.sh-layout target missing the Phase-1 "
                "ingest module at target/bin/ must be reported (A-6 / "
                "A-2-recast-ext)",
            )
            self.assertIn("bin/benchmark_lib.py", missing)
            self.assertNotIn(
                "bin/citation_verifier.py", missing,
                "citation_verifier.py is present at target/bin/ (the "
                "setup_repos.sh location) — must NOT be reported; "
                "pins the no-cross-layout-false-positive guarantee",
            )
            self.assertNotIn("bin/install_skill.py", missing)
            self.assertNotIn("bin/run_playbook.sh", missing)

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
