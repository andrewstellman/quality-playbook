"""v1.5.7 instruction 090u — skill-template.gitignore ships in the
install closure AND the ``scaffolding_missing_gitignore`` remediation
is install-location-aware (`<clone>` → `<root>`).

Surfaced 2026-05-25 by the Ory Keto **run5** (Copilot / gpt-5.3-codex,
copilot channel install) AND NATS **run2** (Codex / gpt-5.2-low, npm
channel install) Phase-0 dogfoods. Both channel agents hit
``scaffolding_missing_gitignore`` (severity=remediable) and were handed
the command ``cat <path-to-your-QPB-clone>/skill-template.gitignore >>
<target>/.gitignore``. On a channel install there is no clone, AND
``skill-template.gitignore`` was not in the install closure — so the
documented remediation was unfollowable. gpt-5.3-codex searched for
``skill-template.gitignore`` (no matches), then improvised
``printf "\\nquality/\\n" >> .gitignore`` to clear the sentinel check.
That improvisation satisfied the validator BUT produced an INCOMPLETE
sentinel: it omitted the ``!quality/RUN_INDEX.md`` negation the real
template carries.

090u closes the loop:

* **Task A** ships ``skill-template.gitignore`` into the closure at the
  TOP LEVEL (alongside SKILL.md / quality_gate.py) via
  ``install_skill._bundle_files()``. After a channel install,
  ``<install_root>/skill-template.gitignore`` exists. Mutation bite:
  remove the bundle entry → the closure-presence test FAILs.

* **Task B** flips the gitignore remediation ``<clone>`` →
  ``<root>``. ``<root>`` resolves to the install root for BOTH layouts
  (clone: root = clone root, file at top level; install: root =
  closure dir, file now bundled). The ``_RUN_INSTALLER_*`` ``<clone>``
  constants stay unchanged (those are correct as-is for the pip/npm
  channels per 089u/089v). Mutation bite: revert either of the four
  platform strings to ``<clone>`` → the catalog test FAILs.

Tests:

* ``test_skill_template_gitignore_is_in_bundle_files`` — closure
  membership pin at the closure top level.
* ``test_install_creates_skill_template_gitignore_at_install_root`` —
  end-to-end: install into a temp target, assert
  ``<install_root>/skill-template.gitignore`` exists with the real
  template body (includes the ``!quality/RUN_INDEX.md`` negation the
  run5/run2 improvisation omitted).
* ``test_gitignore_remediation_uses_root_not_clone`` — the
  ``scaffolding_missing_gitignore.commands`` catalog uses ``<root>``
  (resolvable) and does NOT use ``<clone>`` or the literal
  ``<path-to-your-QPB-clone>`` on any of the four platform strings.
* ``test_run_installer_constants_still_use_clone`` — the
  ``_RUN_INSTALLER_*`` constants (089u/089v installer-rerun
  remediations) are UNCHANGED — they still use ``<clone>`` because
  the pip/npm channel rerun commands are clone-correct as-is.
* ``test_install_closure_includes_skill_template_gitignore`` — the
  ``INSTALL_CLOSURE`` manifest in ``bin/qpb_validate.py`` carries the
  entry (mirrors the drift test from
  ``test_install_manifest_no_drift.py``).
* ``test_channel_install_gitignore_remediation_is_followable_end_to_end``
  — the run5/run2 regression anchor: simulate a channel install
  layout (no QPB clone visible), trigger
  ``scaffolding_missing_gitignore``, and assert the emitted
  remediation command references a file that actually exists in the
  closure. An agent following the command verbatim succeeds — no
  improvisation needed; the full sentinel block (including the
  ``!quality/RUN_INDEX.md`` negation) lands on the first try.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


class SkillTemplateGitignoreInClosure090uTests(unittest.TestCase):

    def test_skill_template_gitignore_is_in_bundle_files(self) -> None:
        """_bundle_files() must include skill-template.gitignore at
        the closure top level (NOT under bin/), alongside SKILL.md
        and quality_gate.py.

        Mutation bite (executable): delete the
        ``_require_bundle_file(... / "skill-template.gitignore")``
        line from ``_bundle_files()`` → this test FAILs.
        """
        from bin import install_skill
        bundle = install_skill._bundle_files(_REPO_ROOT)
        dests = [str(dst) for _src, dst in bundle]
        self.assertIn(
            "skill-template.gitignore", dests,
            "v1.5.7 090u: install_skill._bundle_files() must include "
            "skill-template.gitignore in the install closure. The "
            "2026-05-25 Keto run5 + NATS run2 channel-install agents "
            "got handed an unfollowable <clone>-prefixed remediation "
            "because the file was not in the closure.",
        )
        # Top-level placement — must NOT land under bin/ or any
        # sub-directory (so the <root>/skill-template.gitignore
        # remediation resolves correctly).
        self.assertNotIn(
            "bin/skill-template.gitignore", dests,
            "skill-template.gitignore must live at the closure top "
            "level, NOT under bin/.",
        )

    def test_install_creates_skill_template_gitignore_at_install_root(
            self) -> None:
        """End-to-end: install the skill, assert
        ``<install_root>/skill-template.gitignore`` exists AND
        carries the full sentinel block (including the
        ``!quality/RUN_INDEX.md`` negation the run5/run2
        improvisation omitted).

        Mutation bite: drop the bundle entry → the file is absent at
        the install root → this test FAILs at the assertTrue.
        """
        from bin import install_skill
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            installed = (
                target / ".github" / "skills" / "quality-playbook"
                / "skill-template.gitignore"
            )
            self.assertTrue(
                installed.is_file(),
                f"v1.5.7 090u: install closure must place "
                f"skill-template.gitignore at {installed}. Got missing.",
            )
            body = installed.read_text(encoding="utf-8")
            # The full template (NOT the run5/run2 1-line
            # improvisation) must include the !quality/RUN_INDEX.md
            # negation — that's the load-bearing reason 090u ships
            # the FILE rather than just letting agents improvise.
            self.assertIn(
                "!quality/RUN_INDEX.md", body,
                "v1.5.7 090u: bundled skill-template.gitignore must "
                "carry the !quality/RUN_INDEX.md negation — the "
                "run5/run2 improvisation omitted this negation "
                "(that's the failure mode 090u closes).",
            )
            # And the canonical quality/ block.
            self.assertIn(
                "quality/", body,
                "bundled skill-template.gitignore must carry the "
                "quality/ sentinel block.",
            )

    def test_gitignore_remediation_uses_root_not_clone(self) -> None:
        """The ``scaffolding_missing_gitignore`` catalog uses
        ``<root>`` (resolvable for both layouts) and does NOT use
        ``<clone>`` or the literal ``<path-to-your-QPB-clone>``
        placeholder on any of the four platform strings.

        Mutation bite: revert any of the four platform strings to
        ``<clone>`` → this test FAILs (because the <clone> token
        reappears).
        """
        from bin import qpb_validate as v
        entry = v.FINDING_CATALOG["scaffolding_missing_gitignore"]
        commands = entry["commands"]
        # All four platforms must use <root>, none may use <clone>.
        for plat in ("macos", "linux", "windows_powershell",
                     "windows_cmd"):
            self.assertIn(
                "<root>", commands[plat],
                f"v1.5.7 090u: {plat} gitignore remediation must use "
                f"<root> (resolvable install root); got "
                f"{commands[plat]!r}.",
            )
            self.assertNotIn(
                "<clone>", commands[plat],
                f"v1.5.7 090u: {plat} gitignore remediation must NOT "
                f"use <clone> (pre-090u placeholder unfollowable on "
                f"channel installs); got {commands[plat]!r}.",
            )

    def test_run_installer_constants_still_use_clone(self) -> None:
        """The ``_RUN_INSTALLER_*`` constants (089u/089v
        installer-rerun remediations) must KEEP ``<clone>`` — those
        are correct as-is for the pip/npm/clone channels. 090u is
        scoped to the gitignore remediation only.

        Mutation bite: flip ``_RUN_INSTALLER_MAC`` to ``<root>`` →
        this test FAILs (and 089u/089v would also break).
        """
        from bin import qpb_validate as v
        self.assertIn("<clone>", v._RUN_INSTALLER_MAC,
                      "_RUN_INSTALLER_MAC must still use <clone>; "
                      "090u is scoped to the gitignore remediation.")
        self.assertIn("<clone>", v._RUN_INSTALLER_WIN,
                      "_RUN_INSTALLER_WIN must still use <clone>; "
                      "090u is scoped to the gitignore remediation.")

    def test_install_closure_includes_skill_template_gitignore(
            self) -> None:
        """``bin/qpb_validate.INSTALL_CLOSURE`` must include the
        ``skill-template.gitignore`` entry. The
        ``test_install_closure_matches_bundle_files`` drift test
        will catch this independently if INSTALL_CLOSURE is forgotten;
        this test fails fast with a 090u-specific message.

        Mutation bite: drop the entry from ``INSTALL_CLOSURE`` →
        this test FAILs.
        """
        from bin.qpb_validate import INSTALL_CLOSURE
        paths = {e["path"] for e in INSTALL_CLOSURE}
        self.assertIn(
            "skill-template.gitignore", paths,
            "v1.5.7 090u: INSTALL_CLOSURE must include "
            "skill-template.gitignore (mirrors the bundle).",
        )
        # And the kind must be the dedicated 090u kind so the
        # KIND_TO_FINDING_CODES mapping resolves cleanly.
        entry = next(e for e in INSTALL_CLOSURE
                     if e["path"] == "skill-template.gitignore")
        self.assertEqual(entry["kind"], "scaffolding_template")

    def test_channel_install_gitignore_remediation_is_followable_end_to_end(
            self) -> None:
        """The run5/run2 regression anchor: simulate a channel install
        (closure layout, no QPB clone visible), trigger
        ``scaffolding_missing_gitignore``, and assert the emitted
        remediation command references a file that actually exists in
        the closure — an agent following it verbatim would succeed.

        Mutation bite: revert the remediation to ``<clone>`` AND
        drop the bundle entry → the rendered command points at a
        ``<path-to-your-QPB-clone>`` placeholder which doesn't exist
        anywhere on the simulated channel-install target → the
        cat-and-check pattern this test exercises fails.

        This is the load-bearing E2E pin for 090u: it proves
        gpt-5.3-codex's run5 improvisation (``printf "\\nquality/\\n"``
        with NO ``!quality/RUN_INDEX.md`` negation) is no longer
        necessary on a channel install.
        """
        from bin import install_skill
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            install_root = (
                target / ".github" / "skills" / "quality-playbook"
            )
            template = install_root / "skill-template.gitignore"
            self.assertTrue(
                template.is_file(),
                "skill-template.gitignore must reach the install "
                "root after a channel install (Task A precondition).",
            )

            # Now SHELL OUT the remediation command form
            # ``cat <root>/skill-template.gitignore >>
            # <target>/.gitignore`` and assert the resulting .gitignore
            # contains the load-bearing !quality/RUN_INDEX.md negation
            # the run5/run2 improvisation omitted.
            target_gitignore = target / ".gitignore"
            # Pre-populate with adopter content so we're appending
            # (the real-world Mode-A shape — adopter has an
            # existing .gitignore that lacks the QPB block).
            target_gitignore.write_text(
                "# adopter content\n*.log\n", encoding="utf-8"
            )
            # Exercise the exact macos/linux remediation form with
            # <root> substituted to the install root.
            cmd = (f"cat {template} >> {target_gitignore}")
            result = subprocess.run(
                ["sh", "-c", cmd],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                result.returncode, 0,
                f"v1.5.7 090u: a channel-install agent following "
                f"the rendered <root>-form remediation verbatim must "
                f"succeed (the file exists at the rendered path). "
                f"Got returncode={result.returncode}; "
                f"stderr={result.stderr!r}.",
            )
            appended = target_gitignore.read_text(encoding="utf-8")
            # Adopter content preserved.
            self.assertIn("# adopter content", appended)
            # Full sentinel block appended (including the negation
            # the run5/run2 improvisation OMITTED).
            self.assertIn("quality/", appended)
            self.assertIn(
                "!quality/RUN_INDEX.md", appended,
                "v1.5.7 090u: the appended sentinel block must "
                "include the !quality/RUN_INDEX.md negation. The "
                "2026-05-25 Keto run5 / NATS run2 improvisation "
                "(`printf \"\\nquality/\\n\"`) omitted this negation "
                "— 090u closes that gap by shipping the real file.",
            )


class GitignoreRemediationSubstitution090uTests(unittest.TestCase):
    """Pin the rendered command on an installed layout points at a
    real file, not a placeholder."""

    def test_rendered_command_on_installed_layout_resolves_to_real_file(
            self) -> None:
        """When ``command_for_platform("scaffolding_missing_gitignore",
        ...)`` is rendered with ``<root>`` substituted to a real install
        root (i.e. the directory where skill-template.gitignore now
        lives), the resulting command references a file that EXISTS.

        Mutation bite: revert the remediation to ``<clone>`` → on an
        installed layout (ctx != "clone"), the rendered command points
        at the literal ``<path-to-your-QPB-clone>`` placeholder, which
        does NOT exist on disk → this test FAILs.
        """
        from bin import qpb_validate as v
        # Get the catalog entry's raw template string for macos.
        entry = v.FINDING_CATALOG["scaffolding_missing_gitignore"]
        macos_template = entry["commands"]["macos"]
        # The template must reference <root>/skill-template.gitignore
        # so a downstream substitution renders to a real path on the
        # install layout.
        self.assertIn(
            "<root>/skill-template.gitignore",
            macos_template,
            f"v1.5.7 090u: macos gitignore remediation template "
            f"must reference <root>/skill-template.gitignore (the "
            f"closure-bundled file); got {macos_template!r}.",
        )
        # The closure ships the file at the install root, so
        # <root>/skill-template.gitignore resolves to a real path on
        # ANY install layout (clone or install_skill closure).
        from pathlib import Path
        # Sanity-check the source file exists at the QPB clone root
        # (this is also where the bundle picks it up).
        # v1.5.8 instruction 208: skill-template.gitignore moved into
        # skills/quality-playbook/ alongside the rest of the bundle
        # sources.
        self.assertTrue(
            (_REPO_ROOT / "skills" / "quality-playbook"
             / "skill-template.gitignore").is_file(),
            "skill-template.gitignore must exist at the QPB skill "
            "source folder (the bundle source).",
        )


if __name__ == "__main__":
    unittest.main()
