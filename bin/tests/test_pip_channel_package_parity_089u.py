"""v1.5.7 089u — pip channel package-data parity tests.

The pip distribution channel (`quality-playbook` console script) ships
the QPB tooling + skill bundle as **package data** assembled at
publish time from ``bin.install_skill._bundle_files()`` — the single
source of truth for what an adopter gets at install time.

These tests pin three obligations:

1. **Skill-bundle parity** — the set of source paths
   ``bin.build_channel_package.skill_bundle_paths(repo_root)``
   stages MUST equal ``install_skill._bundle_files(repo_root)``
   member-for-member (modulo file/source ordering). A future edit
   that drops a member from the build enumeration without dropping
   it from ``_bundle_files()`` (or vice-versa) breaks parity and
   the wheel ships a different bundle than the clone install.

2. **Executor inclusion** — ``executor_paths(repo_root)`` must
   include ``bin/install_skill.py`` (the executor the shim loads
   at adopter ``pip install`` time). install_skill.py is
   intentionally NOT in ``_bundle_files()`` (adopters don't get
   the installer at their target), so the pip-channel build
   stages it separately.

3. **Stage round-trip** — calling ``stage(repo_root, dest_dir)``
   produces a directory tree that mirrors the clone-relative
   source layout for every enumerated path: each source path
   ``src`` ends up at ``dest_dir / src.relative_to(repo_root)``.

**Mutation-bite evidence** (per ai_context/DEVELOPMENT_PROCESS.md):

- Drop a manifest entry from ``install_skill._bundle_files`` (or
  add a stray one to ``skill_bundle_paths`` not in
  ``_bundle_files``) — ``test_skill_bundle_parity_with_install_skill``
  fails with the missing/extra path named.
- Comment out the ``bin/install_skill.py`` entry in
  ``executor_paths`` — ``test_executor_includes_install_skill``
  fails because the pip wheel would not contain the script the
  shim loads.

Bites executed PASS → FAIL → PASS during 089u development.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Load via importlib — bin/build_channel_package.py is intentionally
# not exposed under bin.* (it's a publish-time script, not a runtime
# module). Using ``from bin import build_channel_package`` works
# because bin/ has an __init__.py in the clone.
from bin import build_channel_package  # noqa: E402
from bin import install_skill  # noqa: E402


class SkillBundleParity089uTests(unittest.TestCase):
    """Pin the build-time enumeration against ``_bundle_files()``."""

    def test_skill_bundle_parity_with_install_skill(self) -> None:
        """``skill_bundle_paths(repo_root)`` must equal the source-
        path set ``install_skill._bundle_files(repo_root)`` yields.

        Mutation candidate: drop a manifest entry from
        ``install_skill._bundle_files`` (e.g. remove the
        ``role_map.py`` line) or add a stray path to
        ``skill_bundle_paths`` not in the manifest. Expected
        failure: this test fails with the missing/extra path
        named."""
        from_bundle_files = {
            src for src, _dest_rel in install_skill._bundle_files(REPO_ROOT)
        }
        from_build_script = set(
            build_channel_package.skill_bundle_paths(REPO_ROOT)
        )
        missing = from_bundle_files - from_build_script
        extra = from_build_script - from_bundle_files
        self.assertEqual(
            missing, set(),
            f"089u parity: build script's skill_bundle_paths is "
            f"missing files _bundle_files() lists: "
            f"{sorted(str(p) for p in missing)}",
        )
        self.assertEqual(
            extra, set(),
            f"089u parity: build script's skill_bundle_paths "
            f"includes files NOT in _bundle_files(): "
            f"{sorted(str(p) for p in extra)}",
        )

    def test_executor_includes_install_skill(self) -> None:
        """The pip wheel must ship ``bin/install_skill.py`` —
        otherwise the shim has nothing to load at adopter ``pip
        install`` time.

        Mutation candidate: comment out the
        ``repo_root / 'bin' / 'install_skill.py'`` entry in
        ``executor_paths``. Expected failure: this test fails
        because ``install_skill.py not in executor_paths``."""
        executor_set = set(build_channel_package.executor_paths(REPO_ROOT))
        install_skill_path = REPO_ROOT / "bin" / "install_skill.py"
        self.assertIn(
            install_skill_path, executor_set,
            "089u: executor_paths must include bin/install_skill.py "
            "— without it, the pip wheel has no install script to "
            "load and quality-playbook --help would fail at runtime.",
        )
        # The executor MUST also not appear in the skill bundle —
        # install_skill is the executor at the SOURCE side, not the
        # adopter-target bundle. (If a future change moves
        # install_skill.py into _bundle_files() — making adopters
        # carry the installer at their target too — the executor_paths
        # decomposition needs to be revisited.)
        skill_set = set(build_channel_package.skill_bundle_paths(REPO_ROOT))
        self.assertNotIn(
            install_skill_path, skill_set,
            "089u: bin/install_skill.py must NOT be in the skill "
            "bundle (adopters don't get the installer at their "
            "target); the executor lane stages it separately. If "
            "this assertion fails, _bundle_files() was changed to "
            "include the installer — revisit the build script's "
            "executor_paths decomposition.",
        )

    def test_enumerate_bundle_is_union_of_lanes(self) -> None:
        """``enumerate_bundle`` must be exactly skill_bundle_paths
        ∪ executor_paths — no extras, no omissions."""
        skill = set(build_channel_package.skill_bundle_paths(REPO_ROOT))
        executor = set(build_channel_package.executor_paths(REPO_ROOT))
        full = set(build_channel_package.enumerate_bundle(REPO_ROOT))
        self.assertEqual(
            full, skill | executor,
            "089u: enumerate_bundle must be the union of "
            "skill_bundle_paths and executor_paths — no extras, "
            "no omissions.",
        )


class StageRoundTrip089uTests(unittest.TestCase):
    """Pin the on-disk staging shape — every enumerated source path
    ``src`` ends up at ``dest_dir / src.relative_to(repo_root)``."""

    def test_stage_mirrors_clone_relative_layout(self) -> None:
        """``stage(repo_root, dest_dir)`` produces a directory tree
        whose files mirror the clone-relative source layout for
        every member of ``enumerate_bundle(repo_root)``. In
        particular: ``SKILL.md`` at the dest root,
        ``.github/skills/quality_gate/quality_gate.py`` at its
        nested path, ``bin/install_skill.py`` at ``bin/``, etc."""
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "bundle"
            staged = build_channel_package.stage(REPO_ROOT, dest)

        # macOS symlinks /var → /private/var, so the dest the test
        # passes in (under /var/folders/…) is resolved by stage()
        # to /private/var/folders/… on the way out. Resolve both
        # sides before comparing.
        dest_resolved = dest.resolve()
        staged_rel = {Path(p).resolve().relative_to(dest_resolved) for p in staged}
        expected_rel = {
            p.resolve().relative_to(REPO_ROOT)
            for p in build_channel_package.enumerate_bundle(REPO_ROOT)
        }
        missing = expected_rel - staged_rel
        extra = staged_rel - expected_rel
        self.assertEqual(
            missing, set(),
            f"089u stage: files in enumerate_bundle were NOT staged: "
            f"{sorted(str(p) for p in missing)}",
        )
        self.assertEqual(
            extra, set(),
            f"089u stage: extra files appeared in the staging "
            f"output: {sorted(str(p) for p in extra)}",
        )

    def test_stage_handles_dotted_source_dirs(self) -> None:
        """The bundle includes ``.github/skills/quality_gate/
        quality_gate.py`` — a dotted-source-dir path. Confirm
        staging preserves the dot-prefix (setuptools package-data
        globs for the wheel include them explicitly; this test
        pins the staging-side behavior)."""
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "bundle"
            build_channel_package.stage(REPO_ROOT, dest)
            gate_path = dest / ".github" / "skills" / "quality_gate" / "quality_gate.py"
            self.assertTrue(
                gate_path.is_file(),
                f"089u stage: dotted-source-dir path .github/skills/"
                f"quality_gate/quality_gate.py was not preserved "
                f"under the staging dest {dest}.",
            )

    def test_stage_clean_removes_prior_contents(self) -> None:
        """``stage(..., clean=True)`` (the default) must remove any
        prior files in dest_dir before staging — guards against
        a stale build artifact leaking into the wheel."""
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "bundle"
            dest.mkdir()
            stale = dest / "stale-from-prior-build.md"
            stale.write_text("would leak into the wheel", encoding="utf-8")
            self.assertTrue(stale.is_file())
            build_channel_package.stage(REPO_ROOT, dest, clean=True)
            self.assertFalse(
                stale.is_file(),
                "089u stage(clean=True) must remove prior dest_dir "
                "contents before staging — a stale file leaked.",
            )


if __name__ == "__main__":
    unittest.main()
