"""v1.5.8 instructions 208 + 209 — assert the standard self-hosted
marketplace repo layout invariants.

Pin the file locations Claude Code's plugin marketplace mechanism
requires, so future PRs that move files back to root or restructure
further can't silently break ``/plugin marketplace add`` or
``claude --plugin-dir``. Also pins the bundle-internal layout
invariants (``_bundle/`` stays flat, destination paths in
``_bundle_files()`` start with the FROZEN layout) so a future edit
to ``stage()`` or ``_bundle_files()`` that changes adopter-side
install paths trips the test.

File name retained as ``test_plugin_layout_208.py`` per instruction
209: the test pins the post-202-arc plugin-layout invariants; the
209 restructure shifted the canonical paths deeper but kept the same
class of invariants. Renaming the file would break the post-202-arc
naming continuity.

Tests use ``Path(__file__).parents[2]`` to locate the repo root —
the conventional pattern across ``bin/tests/`` — and reference
``plugins/quality-playbook/skills/quality-playbook/`` directly
because that's the contract this instruction pins (the standard
self-hosted marketplace layout — `.claude-plugin/marketplace.json`
at root, plugin manifests under `plugins/<name>/.claude-plugin/`).
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


class PluginLayoutTests(unittest.TestCase):
    """Layout-invariant assertions for the standard self-hosted
    marketplace restructure (209)."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.plugin_dir = (
            self.repo_root / "plugins" / "quality-playbook"
        )
        self.skill_dir = self.plugin_dir / "skills" / "quality-playbook"

    def test_plugins_quality_playbook_directory_exists(self) -> None:
        self.assertTrue(
            self.plugin_dir.is_dir(),
            f"plugins/quality-playbook/ must exist at "
            f"{self.plugin_dir} for the standard self-hosted "
            "marketplace plugin discovery to work",
        )

    def test_skill_md_at_canonical_plugin_location(self) -> None:
        skill_md = self.skill_dir / "SKILL.md"
        self.assertTrue(
            skill_md.is_file(),
            f"SKILL.md must live at {skill_md} for ``claude "
            "--plugin-dir plugins/quality-playbook`` to load the "
            "skill bundle",
        )

    def test_references_directory_in_skill_folder(self) -> None:
        refs = self.skill_dir / "references"
        self.assertTrue(refs.is_dir())
        # Sanity: at least one .md file present so the bundle has
        # something to ship.
        mds = list(refs.glob("*.md"))
        self.assertGreater(
            len(mds), 0,
            "references/ must contain at least one *.md file (the "
            "bundle's Phase 1 ingest sources)",
        )

    def test_phase_prompts_directory_in_skill_folder(self) -> None:
        prompts = self.skill_dir / "phase_prompts"
        self.assertTrue(prompts.is_dir())
        # Phase prompts are load-bearing for both Mode A + Mode B.
        for required in (
            "phase1.md", "phase2.md", "phase3.md",
            "phase4.md", "phase5.md", "phase6.md",
        ):
            with self.subTest(prompt=required):
                self.assertTrue(
                    (prompts / required).is_file(),
                    f"phase_prompts/{required} is mandatory (Mode A + "
                    "Mode B both load it at the matching phase boundary)",
                )

    def test_agents_directory_in_skill_folder(self) -> None:
        agents = self.skill_dir / "agents"
        self.assertTrue(agents.is_dir())
        for required in (
            "quality-playbook.agent.md",
            "quality-playbook-claude.agent.md",
        ):
            with self.subTest(agent=required):
                self.assertTrue(
                    (agents / required).is_file(),
                    f"agents/{required} is mandatory (README Step 4 "
                    "and the AGENTS.md install recipes both reference it)",
                )

    def test_quality_gate_in_scripts_folder(self) -> None:
        gate = self.skill_dir / "scripts" / "quality_gate.py"
        self.assertTrue(
            gate.is_file(),
            f"quality_gate.py must live at {gate} — the canonical "
            "Phase 5 gate script bundled with every install",
        )

    def test_toolkit_md_in_skill_ai_context_folder(self) -> None:
        toolkit = self.skill_dir / "ai_context" / "TOOLKIT.md"
        self.assertTrue(
            toolkit.is_file(),
            f"ai_context/TOOLKIT.md must live at {toolkit} — the "
            "doc-gathering protocol's Step 0 option (c) resolves here",
        )

    def test_skill_md_is_real_file_at_repo_root_v1_5_10(self) -> None:
        # v1.5.10 instr 052 RELOCATION: the canonical SKILL.md moved BACK to
        # the repo root as the REAL file; the in-tree skill-folder location is
        # now a relative symlink to it. This deliberately reverses the 208/209
        # "SKILL.md must NOT be at root" invariant (operator decision 2026-06-18).
        root_skill = self.repo_root / "SKILL.md"
        self.assertTrue(
            root_skill.is_file(),
            "v1.5.10 relocation: SKILL.md must be a real file at the repo root.")
        self.assertFalse(
            root_skill.is_symlink(),
            "the repo-root SKILL.md must be the REAL canonical file, not a "
            "symlink (the in-tree copy is the symlink).")
        intree = self.skill_dir / "SKILL.md"
        self.assertTrue(
            intree.is_symlink(),
            "the in-tree skill-folder SKILL.md must be a symlink to the root "
            "canonical file (v1.5.10 relocation).")
        self.assertEqual(
            intree.resolve(), root_skill.resolve(),
            "the in-tree SKILL.md symlink must resolve to the root SKILL.md.")

    def test_claude_plugin_marketplace_json_at_root(self) -> None:
        manifest = self.repo_root / ".claude-plugin" / "marketplace.json"
        self.assertTrue(
            manifest.is_file(),
            f".claude-plugin/marketplace.json must exist at "
            f"{manifest} at the repo ROOT (the standard self-hosted "
            "marketplace entry point ``/plugin marketplace add`` "
            "resolves to)",
        )

    def test_claude_plugin_plugin_json_inside_plugin_dir(self) -> None:
        plugin_json = (
            self.plugin_dir / ".claude-plugin" / "plugin.json"
        )
        self.assertTrue(
            plugin_json.is_file(),
            f".claude-plugin/plugin.json must exist at {plugin_json} "
            "(inside plugins/quality-playbook/, NOT at the repo root) "
            "— full plugin metadata in the standard self-hosted "
            "marketplace layout",
        )

    def test_plugin_json_not_at_repo_root(self) -> None:
        # 209 restructure: plugin.json MOVED out of root .claude-plugin/
        # into plugins/quality-playbook/.claude-plugin/. A copy left at
        # the root means the move was botched.
        root_plugin_json = (
            self.repo_root / ".claude-plugin" / "plugin.json"
        )
        self.assertFalse(
            root_plugin_json.is_file(),
            "plugin.json must NOT exist at the root "
            ".claude-plugin/ — instruction 209 MOVED it into "
            "plugins/quality-playbook/.claude-plugin/plugin.json. "
            "A copy left behind would make the layout the same "
            "non-standard hybrid that 208 produced (which failed "
            "the empirical --plugin-dir load test).",
        )

    def test_marketplace_json_source_points_to_plugin_dir(self) -> None:
        # 209: each marketplace.json plugin entry's source must point at
        # ``./plugins/<plugin-name>`` (the subdirectory holding that
        # plugin's own .claude-plugin/plugin.json) — NOT ``"."`` (the 208
        # hybrid). v1.5.9 1B: generalized to validate EVERY plugin entry
        # against its own dir (the harness is the 2nd plugin) — a stronger
        # check than pinning one literal source string.
        manifest = self.repo_root / ".claude-plugin" / "marketplace.json"
        with open(manifest, encoding="utf-8") as f:
            data = json.load(f)
        plugins = data.get("plugins", [])
        self.assertGreater(
            len(plugins), 0,
            "marketplace.json must declare at least one plugin entry",
        )
        for plugin in plugins:
            name = plugin.get("name")
            with self.subTest(plugin=name):
                source = plugin.get("source")
                self.assertEqual(
                    source, f"./plugins/{name}",
                    f"marketplace.json plugin '{name}' source must be "
                    f"``./plugins/{name}`` (standard self-hosted layout, "
                    f"209) — not ``.`` (the broken 208 hybrid) and not a "
                    f"path that disagrees with the plugin name.",
                )
                plugin_manifest = (
                    self.repo_root / source.lstrip("./")
                    / ".claude-plugin" / "plugin.json")
                self.assertTrue(
                    plugin_manifest.is_file(),
                    f"plugin '{name}' source {source} must contain "
                    f".claude-plugin/plugin.json (missing at "
                    f"{plugin_manifest}).",
                )

    def test_marketplace_json_drops_inline_skills_field(self) -> None:
        # Pre-208 had the invalid ``"skills": ["./SKILL.md"]``
        # declaration. With the standard layout
        # (skills/<name>/SKILL.md) Claude Code auto-discovers; the
        # field is dropped.
        manifest = self.repo_root / ".claude-plugin" / "marketplace.json"
        with open(manifest, encoding="utf-8") as f:
            data = json.load(f)
        for plugin in data.get("plugins", []):
            with self.subTest(plugin=plugin.get("name")):
                self.assertNotIn(
                    "skills", plugin,
                    "marketplace.json plugin entries must NOT carry an "
                    "inline ``skills`` field — auto-discovery is the "
                    "Claude Code default and the inline form is invalid",
                )
                self.assertNotIn(
                    "strict", plugin,
                    "marketplace.json plugin entries must NOT carry a "
                    "``strict: false`` workaround — strict-mode is the "
                    "default and full metadata belongs in plugin.json",
                )

    def test_plugin_json_version_matches_pyproject(self) -> None:
        """Defensive: catches the case where version stamping forgets
        plugin.json. ``stamp_channel_manifest_versions()`` writes both."""
        plugin_json = (
            self.plugin_dir / ".claude-plugin" / "plugin.json"
        )
        pyproject = self.repo_root / "pyproject.toml"
        with open(plugin_json, encoding="utf-8") as f:
            plugin_data = json.load(f)
        plugin_version = plugin_data.get("version")
        self.assertIsNotNone(
            plugin_version,
            "plugin.json must carry a top-level ``version`` field",
        )
        toml_text = pyproject.read_text(encoding="utf-8")
        match = re.search(
            r'^version\s*=\s*"([^"]+)"\s*$', toml_text, re.MULTILINE
        )
        self.assertIsNotNone(
            match,
            "pyproject.toml must carry a [project] version line "
            "matching the stamping regex",
        )
        self.assertEqual(
            plugin_version, match.group(1),
            f"plugin.json version ({plugin_version!r}) drifted from "
            f"pyproject.toml ({match.group(1)!r}) — "
            "stamp_channel_manifest_versions() must rewrite both in "
            "lockstep at build time",
        )

    def test_skill_md_present_at_repo_root_v1_5_10(self) -> None:
        # v1.5.10 instr 052: SKILL.md IS at the repo root (relocated, real file).
        files_at_root = {f.name for f in self.repo_root.iterdir() if f.is_file()}
        self.assertIn(
            "SKILL.md", files_at_root,
            "v1.5.10 relocation: the canonical SKILL.md lives at the repo root.",
        )

    def test_built_bundle_ships_real_skill_md_v1_5_10(self) -> None:
        """v1.5.10 relocation D6 / Council C4: the staged channel bundle must
        ship a REAL SKILL.md + references/ (the in-tree symlinks dereferenced by
        shutil.copy2), since adopters unpack the artifact where the symlink
        targets do not exist. Bites if a future copy variant preserves symlinks."""
        import os
        import sys as _sys
        import tempfile
        _sys.path.insert(0, str(self.repo_root / "bin"))
        import build_channel_package as bcp  # type: ignore[import-not-found]
        dest = Path(tempfile.mkdtemp()) / "_bundle"
        bcp.stage(self.repo_root, dest)
        sk = dest / "SKILL.md"
        self.assertTrue(sk.is_file(), "bundle must ship SKILL.md")
        self.assertFalse(
            os.path.islink(sk),
            "bundle SKILL.md must be a REAL file, not a symlink (copy2 deref).")
        self.assertEqual(
            sk.read_bytes(), (self.repo_root / "SKILL.md").read_bytes(),
            "bundle SKILL.md content must match the relocated root SKILL.md.")
        refs = list((dest / "references").glob("*.md"))
        self.assertTrue(refs, "bundle must ship references/*.md")
        self.assertFalse(
            any(os.path.islink(r) for r in refs),
            "bundle references must be real files, not symlinks.")

    def test_root_relocated_dirs_and_still_nested_dirs_v1_5_10(self) -> None:
        """v1.5.10 instr 052: references/ relocated to the repo root alongside
        SKILL.md (the in-tree skill-folder copy is a symlink). phase_prompts/,
        agents/, and the 208-era skills/ stay NESTED under plugins/ — they must
        NOT appear at the repo root."""
        # references/ IS now at root (real dir; in-tree copy is a symlink to it).
        root_refs = self.repo_root / "references"
        self.assertTrue(
            root_refs.is_dir() and not root_refs.is_symlink(),
            "references/ must be a real directory at the repo root (v1.5.10).")
        intree_refs = self.skill_dir / "references"
        self.assertTrue(
            intree_refs.is_symlink() and intree_refs.resolve() == root_refs.resolve(),
            "in-tree references/ must be a symlink resolving to root references/.")
        # These were NOT relocated — they stay nested under plugins/.
        for legacy in ("phase_prompts", "agents", "skills"):
            with self.subTest(dir=legacy):
                p = self.repo_root / legacy
                self.assertFalse(
                    p.is_dir(),
                    f"{legacy}/ must NOT exist at the repo root "
                    "(only SKILL.md + references/ were relocated in v1.5.10; "
                    f"{legacy}/ stays under plugins/quality-playbook/skills/"
                    "quality-playbook/)",
                )

    def test_bundle_internal_layout_frozen(self) -> None:
        """The bundle internal layout (_bundle/SKILL.md, _bundle/bin/*,
        etc.) MUST stay flat — adopter installs and the published
        v1.5.8 wheel/tarball expect this layout. Pin via
        ``_bundle_files()`` destination paths."""
        import sys
        sys.path.insert(0, str(self.repo_root / "bin"))
        from install_skill import _bundle_files  # type: ignore[import-not-found]
        pairs = _bundle_files(self.skill_dir)
        # No destination path should start with ``skills/`` or
        # ``plugins/`` — that would mean we accidentally relayered
        # the bundle.
        for _src, dst_rel in pairs:
            with self.subTest(dst=str(dst_rel)):
                self.assertFalse(
                    str(dst_rel).startswith("skills/"),
                    f"_bundle_files() destination {dst_rel} starts "
                    "with 'skills/' — bundle internal layout must "
                    "stay flat; only SOURCE paths shift",
                )
                self.assertFalse(
                    str(dst_rel).startswith("plugins/"),
                    f"_bundle_files() destination {dst_rel} starts "
                    "with 'plugins/' — bundle internal layout must "
                    "stay flat; only SOURCE paths shift",
                )


if __name__ == "__main__":
    unittest.main()
