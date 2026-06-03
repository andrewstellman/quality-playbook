"""v1.5.7 089i — regression coverage for the four pre-tag cleanup
fixes:

  Fix 1 (W-A): layout-aware freshness check in
    ``bin/run_playbook.py:_check_installed_bundle_freshness``. Pre-089i
    the check took the UNION of both install layouts' manifests
    (``install_skill._bundle_files()`` + setup_repos.sh `${dst}/bin/`
    cp destinations) and emitted ``WARN: installed bundle stale ...
    Missing: bin/run_playbook.sh, bin/install_skill.py`` against
    every correct install_skill.py-layout install — those files
    are setup_repos.sh-only and that layout doesn't ship them.
    089i: detect the layout and expect only its manifest. A
    correct install_skill.py-layout install no longer false-positive
    WARNs; an incomplete install (missing one of its OWN manifest
    files) IS still flagged.

  Fix 2 (UTC run-id): ``execute_run`` and ``main`` now emit the
    display timestamp via ``datetime.now(timezone.utc).strftime(...)``
    instead of bare ``datetime.now().strftime(...)``. The downstream
    ``_compute_run_id`` adds the ``Z`` suffix; that suffix is now
    honest (the underlying UTC truth comes from the callers). The
    run-id now agrees with the archive directory and the run_state
    ``ts`` (both already UTC pre-089i).

Fix 3 (doc-currency) and Fix 4 (Python 3.10+ guard) are surface
fixes covered by existing tests (the catalog-size assertion in
test_qpb_validate.py, the assertNoLogs guard's own
``skipUnless``) or are non-test surface (README prereq).

Mutation-bite evidence inline; bites executed PASS→FAIL→PASS
during 089i development.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bin import run_playbook


# Helper: build a minimal args.Namespace matching the freshness-
# check call surface. The check itself only reads attributes via
# getattr with defaults, so this is conservative.
def _make_args(**kwargs) -> argparse.Namespace:
    defaults = dict()
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class LayoutAwareFreshnessCheckTests(unittest.TestCase):
    """Fix 1 (W-A): a correct install_skill.py-layout install must
    NOT be reported stale for setup_repos.sh-only files
    (``run_playbook.sh``, ``install_skill.py``). A genuinely
    incomplete install MUST still be flagged.

    The function under test is
    :func:`bin.run_playbook._check_installed_bundle_freshness`,
    which takes ``(qpb_root, target)`` and resolves the bundle
    directory internally via
    :func:`bin.benchmark_lib.find_installed_skill`.
    """

    def _make_install_skill_layout(
        self, target: Path, *, manifest: list, omit: list = None
    ) -> Path:
        """Construct an install_skill.py-layout install under
        ``target``. Uses one of the canonical install locations
        (``.claude/skills/quality-playbook/SKILL.md``) so
        ``find_installed_skill`` resolves correctly.

          target/.claude/skills/quality-playbook/SKILL.md
          target/.claude/skills/quality-playbook/bin/<file>  for each manifest entry not in omit
          target/.claude/skills/quality-playbook/references/  (stub)
          target/.claude/skills/quality-playbook/phase_prompts/  (stub)
          target/.claude/skills/quality-playbook/agents/  (stub)

        Stub subdirectories prevent the markdown-tree portion of
        the freshness check from emitting noise (it iterates
        references/phase_prompts/agents .md files; absence of the
        installed_dir triggers a per-file missing entry). For the
        test we only care about the bin/ portion, so we pre-stub
        the markdown trees as present + empty.

        Returns the bundle directory path.
        """
        omit = omit or []
        bundle_dir = target / ".claude" / "skills" / "quality-playbook"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "SKILL.md").write_text("# stub", encoding="utf-8")
        # Pre-stub the markdown subtrees so the markdown-tree check
        # doesn't add noise. (We mirror whatever .md files exist
        # in the source qpb_root subdirs; using stub empty dirs
        # would emit per-file missing entries from source.)
        qpb_root = Path(__file__).resolve().parents[2]
        for subdir in ("references", "phase_prompts", "agents"):
            src = qpb_root / subdir
            inst = bundle_dir / subdir
            inst.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                for mdf in src.glob("*.md"):
                    (inst / mdf.name).write_text("# stub", encoding="utf-8")
        # Now populate the bin/ files per manifest.
        bin_dir = bundle_dir / "bin"
        bin_dir.mkdir()
        for name in manifest:
            if name in omit:
                continue
            (bin_dir / name).write_text("# stub", encoding="utf-8")
        return bundle_dir

    def _get_install_skill_manifest(self) -> list:
        """Resolve the install_skill.py-layout bin/ manifest from the
        live source-of-truth — ``install_skill._bundle_files(qpb_root)``."""
        from bin import install_skill
        qpb_root = Path(__file__).resolve().parents[2]
        names = []
        for _src, dest in install_skill._bundle_files(qpb_root):
            parts = dest.parts
            if len(parts) == 2 and parts[0] == "bin":
                if parts[1] not in names:
                    names.append(parts[1])
        return names

    def test_correct_install_skill_layout_does_not_false_positive(self) -> None:
        """Pre-089i this test would fail because the freshness check
        emits ``bin/install_skill.py`` and ``bin/run_playbook.sh``
        as "missing" for a complete install_skill.py-layout install
        (both are setup_repos.sh-only files that this layout
        legitimately doesn't include).

        Mutation: revert to the pre-089i UNION-of-manifests behavior
        (expect both manifests for any layout).
        Expected failure: assertNotIn fires — ``bin/run_playbook.sh``
        appears in missing.
        Restoration: restore the layout-aware detection; passes.
        Bite executed during 089i Fix 1 development; PASS→FAIL→PASS
        confirmed.
        """
        manifest = self._get_install_skill_manifest()
        # Sanity: setup_repos.sh-only files MUST NOT be in this
        # layout's manifest, or the test is meaningless.
        self.assertNotIn("install_skill.py", manifest,
                         "install_skill.py-layout doesn't bundle itself")
        self.assertNotIn("run_playbook.sh", manifest,
                         "install_skill.py-layout doesn't bundle the wrapper")

        qpb_root = Path(__file__).resolve().parents[2]
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "adopter-repo"
            target.mkdir()
            self._make_install_skill_layout(target, manifest=manifest)
            missing = run_playbook._check_installed_bundle_freshness(
                qpb_root=qpb_root, target=target,
            )

        self.assertNotIn("bin/install_skill.py", missing,
                         "089i W-A: install_skill.py-layout install must "
                         "NOT be flagged for missing install_skill.py "
                         "(that file is setup_repos.sh-only)")
        self.assertNotIn("bin/run_playbook.sh", missing,
                         "089i W-A: install_skill.py-layout install must "
                         "NOT be flagged for missing run_playbook.sh "
                         "(that file is setup_repos.sh-only)")
        # Sanity: the bin/ files of THIS layout's manifest must
        # also be unmissed (no spurious extras).
        for name in manifest:
            self.assertNotIn(f"bin/{name}", missing,
                             f"complete install_skill.py-layout install "
                             f"must not flag manifest member bin/{name}")

    def test_incomplete_install_skill_layout_still_flagged(self) -> None:
        """A genuinely-incomplete install_skill.py-layout install
        (one of its OWN manifest files is missing) MUST still be
        flagged. 089i tightens scope but doesn't soften correctness.

        Mutation: 089i's layout dispatch returns ``expected_bin =
        []`` (skip-everything) for the install_skill.py branch.
        Expected failure: the incomplete-install assertion below
        fires — the missing file is no longer flagged.
        Restoration: restore expected_bin to the install_skill
        manifest; passes.
        """
        manifest = self._get_install_skill_manifest()
        self.assertGreaterEqual(len(manifest), 3,
                                "manifest must have ≥3 files to omit one "
                                "meaningfully")
        # Omit one file from the manifest — a genuine staleness.
        omit_file = manifest[0]

        qpb_root = Path(__file__).resolve().parents[2]
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "adopter-repo"
            target.mkdir()
            self._make_install_skill_layout(
                target, manifest=manifest, omit=[omit_file],
            )
            missing = run_playbook._check_installed_bundle_freshness(
                qpb_root=qpb_root, target=target,
            )

        self.assertIn(f"bin/{omit_file}", missing,
                      "089i W-A: a genuinely-incomplete install must "
                      "still be flagged — the layout-aware narrowing "
                      "tightens scope but preserves correctness")

    def test_install_with_missing_bin_tree_still_flags_manifest(self) -> None:
        """089i Council R1 regression: an install_skill.py-layout
        install whose SKILL.md is present but whose ENTIRE bin/
        subdirectory is absent must still be flagged for every
        bundled bin/ manifest entry as missing.

        Pre-089i: pre-089i would have UNIONed both manifests and
        reported every entry as missing (since none exist).
        Initial 089i implementation: silently emitted no findings
        (`expected_bin = []` in the else clause) — a diagnostic
        regression flagged by Council R1.
        Fixed: else branch now defaults to the install_skill.py
        manifest (broad-case adopter layout) checked against BOTH
        candidate bin/ locations; every entry reports missing when
        both locations are empty/absent.

        Mutation candidate: revert the else clause to
        ``expected_bin = []`` (the initial 089i shape). Expected
        failure: the assertGreater(len(missing), 0) below fires.
        """
        manifest = self._get_install_skill_manifest()
        self.assertGreater(len(manifest), 0,
                           "install_skill manifest must be non-empty")
        qpb_root = Path(__file__).resolve().parents[2]
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "adopter-repo"
            target.mkdir()
            # Build the install_skill.py layout WITHOUT any bin/
            # subdirectory — SKILL.md and markdown subtrees present,
            # bin/ entirely absent.
            bundle_dir = target / ".claude" / "skills" / "quality-playbook"
            bundle_dir.mkdir(parents=True)
            (bundle_dir / "SKILL.md").write_text("# stub", encoding="utf-8")
            for subdir in ("references", "phase_prompts", "agents"):
                src = qpb_root / subdir
                inst = bundle_dir / subdir
                inst.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    for mdf in src.glob("*.md"):
                        (inst / mdf.name).write_text(
                            "# stub", encoding="utf-8",
                        )
            # Deliberately do NOT create bundle_dir/bin/ or target/bin/.
            missing = run_playbook._check_installed_bundle_freshness(
                qpb_root=qpb_root, target=target,
            )

        # All install_skill manifest entries must appear as missing.
        missing_bin_set = {m for m in missing if m.startswith("bin/")}
        for name in manifest:
            self.assertIn(
                f"bin/{name}", missing_bin_set,
                f"089i Council R1 regression: install with absent "
                f"bin/ tree must still flag bin/{name} as missing — "
                f"the layout-aware narrowing must not silently "
                f"suppress findings when neither candidate bin/ "
                f"exists.",
            )
        # Negative pin: setup_repos.sh-only files must NOT be
        # speculatively reported here (the fix preserves 089i's
        # false-positive elimination — it uses install_skill_manifest,
        # not the union, on this branch).
        self.assertNotIn(
            "bin/run_playbook.sh", missing_bin_set,
            "089i Council R1 fix must NOT re-introduce the pre-089i "
            "false positive for setup_repos.sh-only files",
        )
        self.assertNotIn(
            "bin/install_skill.py", missing_bin_set,
            "089i Council R1 fix must NOT re-introduce the pre-089i "
            "false positive for setup_repos.sh-only files",
        )

    def test_setup_repos_flat_layout_missing_bin_flags_setup_manifest(self) -> None:
        """089i Council R1 cycle 2 regression: a setup_repos.sh flat
        install at ``.github/skills/SKILL.md`` whose ENTIRE ``target/
        bin/`` tree is absent must be flagged against the
        setup_repos.sh manifest, NOT the install_skill manifest.

        Cycle-2 R1 caught this gap: the initial else-branch fix used
        ``install_skill_manifest`` unconditionally, which under-
        reported the flat layout (setup-only files missed).
        Cycle-2 fix: discriminate by ``bundle_dir.name`` — ``skills``
        → setup_repos manifest; ``quality-playbook`` → install_skill
        manifest.

        v1.5.7 089z: dropped the ``run_playbook.sh`` wrapper +
        manifest entry — the test no longer asserts it's flagged.
        The ``install_skill.py`` setup-only file is still in the
        manifest and the assertion stays.

        Mutation candidate: revert the discrimination to unconditional
        ``install_skill_manifest``. Expected failure: the
        ``bin/install_skill.py`` assertion fires (setup_repos
        manifest entry is no longer in missing).
        """
        # Resolve the setup_repos manifest from the live source-of-
        # truth — parse setup_repos.sh's cp destinations.
        qpb_root = Path(__file__).resolve().parents[2]
        setup_repos_sh = qpb_root / "repos" / "setup_repos.sh"
        self.assertTrue(setup_repos_sh.is_file(),
                        "repos/setup_repos.sh must exist for this test")
        sr_text = setup_repos_sh.read_text(encoding="utf-8", errors="replace")
        setup_manifest: list = []
        for m in re.finditer(r'"\$\{dst\}/bin/([^"/]+)"', sr_text):
            name = m.group(1)
            if name not in setup_manifest:
                setup_manifest.append(name)
        self.assertIn("install_skill.py", setup_manifest,
                      "setup_repos.sh must stage install_skill.py")

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "adopter-repo"
            target.mkdir()
            # Construct the flat setup_repos.sh layout: SKILL.md at
            # .github/skills/SKILL.md (bundle_dir.name == "skills").
            # Do NOT create target/bin/ — that's the staleness.
            bundle_dir = target / ".github" / "skills"
            bundle_dir.mkdir(parents=True)
            (bundle_dir / "SKILL.md").write_text(
                "---\nname: quality-playbook\n---\n# stub",
                encoding="utf-8",
            )
            # Pre-stub the markdown subtrees at the bundle to avoid
            # noise from the markdown-tree check.
            for subdir in ("references", "phase_prompts", "agents"):
                src = qpb_root / subdir
                inst = bundle_dir / subdir
                inst.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    for mdf in src.glob("*.md"):
                        (inst / mdf.name).write_text(
                            "# stub", encoding="utf-8",
                        )
            missing = run_playbook._check_installed_bundle_freshness(
                qpb_root=qpb_root, target=target,
            )

        missing_bin_set = {m for m in missing if m.startswith("bin/")}
        # POSITIVE pin: setup_repos manifest entries (including
        # setup-only files) must be reported missing. v1.5.7 089z
        # dropped the run_playbook.sh wrapper from the manifest, so
        # the corresponding assertion was removed; install_skill.py
        # remains in the setup-only manifest and is still checked.
        self.assertIn(
            "bin/install_skill.py", missing_bin_set,
            "089i Council R1 cycle 2: flat setup_repos.sh install "
            "with absent target/bin/ must flag bin/install_skill.py "
            "as missing — it IS in this layout's manifest.",
        )

    def test_no_install_returns_empty(self) -> None:
        """No installed skill at the target → no missing entries
        (the freshness check soft-no-ops when there's nothing to
        check). 089i preserves this."""
        qpb_root = Path(__file__).resolve().parents[2]
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "empty-target"
            target.mkdir()
            missing = run_playbook._check_installed_bundle_freshness(
                qpb_root=qpb_root, target=target,
            )
        self.assertEqual(missing, [],
                         "freshness check must return [] when no "
                         "installed skill is found at the target")


class UtcRunIdTests(unittest.TestCase):
    """Fix 2 (UTC run-id): the display-timestamp sources at
    ``execute_run`` (~5355) and ``main`` (~5791) now use
    ``datetime.now(timezone.utc)``. The run-id _compute_run_id
    derives from is true UTC; its ``Z`` suffix is honest."""

    def test_execute_run_emits_utc_display_timestamp(self) -> None:
        """The execute_run display-timestamp source is wired to
        ``datetime.now(timezone.utc).strftime(...)``. Inspect the
        source to confirm the call shape (the actual datetime call
        is too deeply embedded to mock cleanly without rewriting
        the function).

        Mutation: revert ``datetime.now(timezone.utc).strftime(...)``
        to ``datetime.now().strftime(...)`` (the pre-089i shape).
        Expected failure: this test fails because
        ``datetime.now(timezone.utc).strftime`` no longer appears
        in execute_run's source.
        Restoration: restore the UTC call; passes.
        Bite executed during 089i Fix 2 development.
        """
        src = inspect.getsource(run_playbook.execute_run)
        # 089i: the entry point must emit the display timestamp in
        # UTC, not local.
        self.assertIn("datetime.now(timezone.utc).strftime",
                      src,
                      "089i UTC run-id: execute_run must build the "
                      "display timestamp via datetime.now(timezone.utc) "
                      "so the downstream _compute_run_id Z suffix is "
                      "honest. Found in source — but pre-089i the call "
                      "was bare datetime.now().strftime (local time "
                      "mislabeled UTC).")
        # Negative pin: the pre-089i shape (bare datetime.now()
        # producing a display string) must NOT appear unguarded.
        # Allow it inside a comment or string literal — we check
        # the executable form via a coarse regex.
        bare_pattern = re.compile(
            r"^[^#\n]*datetime\.now\(\)\.strftime\(",
            re.MULTILINE,
        )
        bare_matches = bare_pattern.findall(src)
        self.assertEqual(
            bare_matches, [],
            "089i UTC run-id: execute_run must NOT call bare "
            "datetime.now().strftime — that's the pre-089i shape "
            "that emitted local time mislabeled with Z. Use "
            "datetime.now(timezone.utc).strftime instead.",
        )

    def test_main_emits_utc_display_timestamp(self) -> None:
        """Same shape pin for the ``main`` entry point's display-
        timestamp source."""
        src = inspect.getsource(run_playbook.main)
        self.assertIn("datetime.now(timezone.utc).strftime", src,
                      "089i UTC run-id: main must emit a UTC display "
                      "timestamp")
        bare_pattern = re.compile(
            r"^[^#\n]*datetime\.now\(\)\.strftime\(",
            re.MULTILINE,
        )
        self.assertEqual(
            bare_pattern.findall(src), [],
            "089i UTC run-id: main must not call bare "
            "datetime.now().strftime",
        )

    def test_compute_run_id_passthrough_unchanged(self) -> None:
        """``_compute_run_id`` is unchanged at the function-body
        level — only its docstring is corrected. Re-pin its
        contract:
          - display form (YYYYMMDD-HHMMSS) → compact (YYYYMMDDTHHMMSSZ)
          - already-compact passes through
          - anything else passes through unchanged
        """
        # display → compact
        self.assertEqual(
            run_playbook._compute_run_id("20260520-143000"),
            "20260520T143000Z",
        )
        # already compact → passthrough
        self.assertEqual(
            run_playbook._compute_run_id("20260520T143000Z"),
            "20260520T143000Z",
        )
        # synthetic / unconventional → passthrough
        self.assertEqual(
            run_playbook._compute_run_id("weird-ts"),
            "weird-ts",
        )

    def test_run_id_sorts_lexicographically(self) -> None:
        """The resolver's most-recent-by-name relies on the run-id
        format YYYYMMDDTHHMMSSZ sorting lexicographically the same
        way it sorts chronologically. 089i preserves this — true-
        UTC run-ids still satisfy the property (in fact, more
        robustly than pre-089i, because cross-timezone runs no
        longer interleave wrong)."""
        run_ids = [
            "20260520T143000Z",   # 14:30 UTC
            "20260520T150000Z",   # 15:00 UTC
            "20260521T090000Z",   # next day 09:00 UTC
            "20260101T000000Z",   # earlier in year
        ]
        chronological = sorted(run_ids)  # alpha-sorted
        # Expected chronological order:
        expected = [
            "20260101T000000Z",
            "20260520T143000Z",
            "20260520T150000Z",
            "20260521T090000Z",
        ]
        self.assertEqual(chronological, expected,
                         "lexical sort must equal chronological sort "
                         "for the YYYYMMDDTHHMMSSZ format — the "
                         "resolver depends on this invariant")


class DocCurrencyTests(unittest.TestCase):
    """Fix 3 (doc-currency): the comment at bin/qpb_validate.py:278
    must match the actual ``len(FINDING_CATALOG)``."""

    def test_finding_catalog_comment_count_matches_actual(self) -> None:
        """The pre-089i comment claimed ``13 codes`` against an
        actual catalog of 14 entries. 089i updates the comment to
        match. Pin: a future catalog entry addition that forgets
        to update the comment fails this test."""
        from bin import qpb_validate

        actual_count = len(qpb_validate.FINDING_CATALOG)
        # Read the comment block at lines 277-279 (approximately).
        validate_src = (
            Path(qpb_validate.__file__).read_text(encoding="utf-8")
        )
        # Find the §3.3.2 Finding catalog comment and extract its
        # claimed count (digit cluster after "catalog (").
        match = re.search(
            r"§3\.3\.2 Finding catalog \((\d+) codes\)",
            validate_src,
        )
        self.assertIsNotNone(match,
                             "qpb_validate.py must contain the §3.3.2 "
                             "Finding catalog comment with a count")
        claimed_count = int(match.group(1))
        self.assertEqual(
            claimed_count, actual_count,
            f"089i doc-currency: §3.3.2 comment says "
            f"`{claimed_count} codes` but len(FINDING_CATALOG) is "
            f"{actual_count}. Update the comment when you add or "
            f"remove a catalog entry.",
        )


if __name__ == "__main__":
    unittest.main()
