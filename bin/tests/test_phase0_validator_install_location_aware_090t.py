"""v1.5.7 instruction 090t — Phase 0 validator invocation must be
install-location-aware in SKILL.md and AGENTS.md, mirroring Phase 1.

Motivated by the 2026-05-25 Ory Keto run4 first-probe failure
(Copilot / gpt-5.3-codex, channel install): the agent ran
``python3 bin/qpb_validate.py .`` from the target repo root and got
a path mismatch — no ``bin/qpb_validate.py`` at the repo root, the
validator lives at ``.github/skills/quality-playbook/bin/qpb_
validate.py``. 090k correctly shipped ``qpb_validate.py`` INTO the
install closure (the file now exists at
``<marker>/skills/quality-playbook/bin/qpb_validate.py``) but did
NOT update the SKILL.md / AGENTS.md INVOCATION guidance to tell
the agent how to find it — so the file is in the right place while
the prose still pointed at repo-root ``bin/``. A literal/weaker
agent followed the documented bare path and failed the first
probe. 090t fixes the prose so the invocation is install-location-
aware (mirroring SKILL.md:24's Phase 1 pattern).

Test surface (light presence-pin, per the instruction's Task B):

  * test_skill_md_phase0_invocation_is_install_location_aware:
    SKILL.md:77 (the Phase 0 numbered step) and SKILL.md:94 (the
    MANDATORY-first-action callout) both reference the install-
    location fallback list / install-root resolution AND the
    canonical ``<install_root>/bin/qpb_validate.py`` form.
  * test_agents_md_phase0_invocation_is_install_location_aware:
    AGENTS.md Mode-A entry sequence Phase 0 step gives the
    install-location-aware form (`<install_root>/bin/qpb_validate
    .py`) and names the failure mode (bare-path-from-repo-root
    fails on an installed-skill layout).
  * test_phase0_invocations_cite_run4_motivation: the new
    guidance cites the 2026-05-25 Keto run4 first-probe failure
    so a future reader understands the motivation. Mutation bite:
    drop the citation → readers won't know which adopter failure
    mode drove the rule.

Each test docstring records its mutation bite inline.
"""
from __future__ import annotations

import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


class Phase0InstallLocationAware090tTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = (_REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        cls.agents_text = (_REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    def test_skill_md_phase0_invocation_is_install_location_aware(
            self) -> None:
        """SKILL.md Phase 0 (both the numbered step ~line 77 and
        the MANDATORY-first-action callout ~line 94) must reference
        the install-location fallback list / install-root
        resolution AND the install-root-prefixed
        ``<install_root>/bin/qpb_validate.py`` form.

        Mutation bite: revert SKILL.md:77 or :94 to bare
        ``python3 bin/qpb_validate.py`` (the pre-090t shape) →
        this test FAILs because the install-root token disappears.
        """
        # The Phase 0 numbered step (~line 77) must carry the
        # 090t install-location-aware framing.
        self.assertIn(
            "Invocation form is install-location-aware (v1.5.7 090t)",
            self.skill_text,
            "SKILL.md Phase 0 numbered step must carry the 090t "
            "install-location-aware framing.",
        )
        # And the install-root-prefixed form.
        self.assertIn(
            "python3 <install_root>/bin/qpb_validate.py <target>",
            self.skill_text,
            "SKILL.md must give the install-root-prefixed Phase 0 "
            "invocation form.",
        )
        # The MANDATORY-first-action callout (~line 94) must ALSO
        # reference the install-root resolution — the agent reading
        # the Phase 0 callout in isolation must see it.
        self.assertIn(
            "Resolve the install root via the install-location fallback list",
            self.skill_text,
            "SKILL.md MANDATORY-first-action Phase 0 callout must "
            "reference the install-location fallback list.",
        )
        # The failure mode must be stated plainly so an agent
        # doesn't repeat the run4 bare-path-from-repo-root mistake.
        self.assertIn(
            "MUST prefix the install root", self.skill_text,
            "SKILL.md must call out that install_skill-layout "
            "adopters MUST use the install-root-prefixed form.",
        )

    def test_agents_md_phase0_invocation_is_install_location_aware(
            self) -> None:
        """AGENTS.md Mode-A entry sequence Phase 0 step (~line 210)
        must give the install-location-aware form AND name the
        failure mode (bare-path-from-repo-root fails on an
        installed-skill layout).

        Mutation bite: revert AGENTS.md:210 to bare
        ``python3 <qpb-clone>/bin/qpb_validate.py <target-repo>``
        (the pre-090t shape) → this test FAILs because the
        install-root token disappears AND the failure-mode call-
        out disappears.
        """
        self.assertIn(
            "Invocation form is install-location-aware (v1.5.7 090t)",
            self.agents_text,
            "AGENTS.md Mode-A entry sequence Phase 0 step must "
            "carry the 090t install-location-aware framing.",
        )
        self.assertIn(
            "python3 <install_root>/bin/qpb_validate.py <target-repo>",
            self.agents_text,
            "AGENTS.md must give the install-root-prefixed Phase 0 "
            "invocation form.",
        )
        # Failure mode must be named explicitly.
        self.assertIn(
            "running bare `python3 bin/qpb_validate.py <target>` "
            "from the target repo root FAILS",
            self.agents_text,
            "AGENTS.md must explicitly name the bare-path-from-"
            "repo-root failure mode that the 2026-05-25 Keto run4 "
            "hit.",
        )

    def test_phase0_invocations_cite_run4_motivation(self) -> None:
        """The 090t guidance must cite the 2026-05-25 Keto run4
        first-probe failure in both surfaces so a future reader
        understands which adopter failure mode drove the rule.

        Mutation bite: drop the citation → future readers won't
        know which adopter failure mode justifies the more
        verbose install-root-aware form.
        """
        for text, name in (
            (self.skill_text, "SKILL.md"),
            (self.agents_text, "AGENTS.md"),
        ):
            self.assertIn(
                "2026-05-25 Keto run4", text,
                f"{name}: must cite the 2026-05-25 Keto run4 first-"
                f"probe failure as the 090t motivation.",
            )

    def test_skill_md_size_under_ceiling(self) -> None:
        """Sanity-pin alongside the canonical test_skill_md_size:
        the 090t additions must keep SKILL.md under the 32,000 BPE
        soft tripwire. Redundant with test_skill_md_size_under_
        threshold, but cheap and locally surfaces a 090t-induced
        regression."""
        try:
            import tiktoken
        except ImportError:
            self.skipTest("tiktoken not installed")
        enc = tiktoken.get_encoding("cl100k_base")
        tokens = len(enc.encode(self.skill_text))
        self.assertLess(
            tokens, 32000,
            f"v1.5.7 090t additions pushed SKILL.md to {tokens} "
            f"BPE tokens; the 32K soft tripwire is the operational "
            f"hygiene ceiling (bumpable when worth the tokens).",
        )


if __name__ == "__main__":
    unittest.main()
