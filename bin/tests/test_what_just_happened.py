"""Tests for the v1.5.7 UX contract: mandatory `## What just happened`
+ `### What to do next` block at every phase boundary.

Surfaces pinned:

1. `references/what_just_happened.md` exists with the eight required
   run-state rows in its decision-tree section.
2. SKILL.md carries the cross-phase orientation-spine section
   establishing the contract (canonical phrasing) and pointing at the
   reference file.
3. Every `phase_prompts/*.md` (phase1-6, single_pass, iteration)
   includes a reference to `references/what_just_happened.md` and
   the emission instruction.
4. The iteration prompt built by `bin.run_playbook.iteration_prompt`
   (which loads `phase_prompts/iteration.md` at runtime) includes
   the tail emission instruction.

Each test is mutation-verified: removing the artifact / phrase /
tail makes the test fail, restoring it makes the test pass.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from bin import run_playbook

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REFERENCE_PATH = REPO_ROOT / "references" / "what_just_happened.md"
SKILL_PATH = REPO_ROOT / "SKILL.md"
PHASE_PROMPTS_DIR = REPO_ROOT / "phase_prompts"


class WhatJustHappenedReferenceExistsTests(unittest.TestCase):
    """`references/what_just_happened.md` is the single source of
    truth for the decision tree. The test verifies it exists with the
    eight required run-state rows. Bite-verified by renaming the file
    aside (then the existence assertion fires); restoring makes the
    test pass again.
    """

    REQUIRED_RUN_STATES = (
        "State P1",  # Phase 1 only completed (Mode A multi-pass)
        "State C",   # Phase 1 + code-only mode
        "State G",   # Phase 2 abort + D1 preservation
        "State S",   # pass-process / fail-recall (the v1.5.7 load-bearing case)
        "State B",   # Phases 1-6 baseline with N bugs
        "State I",   # One or more iteration strategies done
        "State F",   # All four iterations done
        "State R",   # Recheck done
    )

    def test_reference_file_exists(self) -> None:
        self.assertTrue(
            REFERENCE_PATH.is_file(),
            f"references/what_just_happened.md must exist at "
            f"{REFERENCE_PATH}. v1.5.7 UX contract single-source-of-"
            f"truth file; SKILL.md and every phase prompt point at it.",
        )

    def test_reference_file_lists_all_eight_run_states(self) -> None:
        text = REFERENCE_PATH.read_text(encoding="utf-8")
        for state_label in self.REQUIRED_RUN_STATES:
            self.assertIn(
                state_label,
                text,
                f"references/what_just_happened.md must define the "
                f"`{state_label}` run-state row. The eight states "
                f"(P1, C, G, S, B, I, F, R) cover every terminal "
                f"the v1.5.7 contract ships against.",
            )

    def test_reference_file_includes_contract_and_do_not_sections(self) -> None:
        text = REFERENCE_PATH.read_text(encoding="utf-8")
        for required_heading in ("## Contract", "## DO NOT"):
            self.assertIn(
                required_heading,
                text,
                f"references/what_just_happened.md must include the "
                f"`{required_heading}` section. The Contract section "
                f"establishes the mandatory emission rule; the DO NOT "
                f"section enforces plain-English framing.",
            )


class SkillMdEmitsWhatJustHappenedContractTests(unittest.TestCase):
    """SKILL.md must carry the cross-phase orientation-spine section
    that wires the contract into the skill body. Without this, phase
    prompts could carry the tail but the orchestration spine wouldn't
    say "this is mandatory at every phase boundary." Bite-verified by
    deleting the section from SKILL.md (then the test fires); restoring
    makes it pass.
    """

    REQUIRED_SECTION_HEADER = '## "What just happened" — required final block at every phase boundary'
    REQUIRED_REFERENCE_POINTER = "references/what_just_happened.md"
    REQUIRED_CONTRACT_PHRASE = "every phase boundary"

    def test_skill_md_has_what_just_happened_section(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn(
            self.REQUIRED_SECTION_HEADER,
            text,
            f"SKILL.md must include the `{self.REQUIRED_SECTION_HEADER}` "
            f"section as the orientation-spine entry for the v1.5.7 UX "
            f"contract. Without it, phase prompts may carry the tail "
            f"but the skill body doesn't establish the rule.",
        )

    def test_skill_md_points_at_reference_file(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn(
            self.REQUIRED_REFERENCE_POINTER,
            text,
            f"SKILL.md must include a reference to "
            f"`{self.REQUIRED_REFERENCE_POINTER}` (the decision tree's "
            f"single source of truth). Without this pointer, the agent "
            f"cannot discover the decision tree from the orientation "
            f"spine.",
        )

    def test_skill_md_uses_canonical_contract_phrase(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn(
            self.REQUIRED_CONTRACT_PHRASE,
            text,
            f"SKILL.md's What-just-happened section must use the "
            f"canonical phrase `{self.REQUIRED_CONTRACT_PHRASE}` so "
            f"the rule's scope is unambiguous. A doc edit that softens "
            f"it to 'sometimes' or 'where appropriate' would silently "
            f"degrade the contract.",
        )


class PhasePromptsIncludeWhatJustHappenedTailTests(unittest.TestCase):
    """Every `phase_prompts/*.md` that the runner loads must include a
    reference to `references/what_just_happened.md` and the emission
    instruction. Bite-verified by stripping the tail from any single
    phase prompt (then that subTest fires); restoring makes it pass.
    """

    PROMPT_FILES = (
        "phase1.md",
        "phase2.md",
        "phase3.md",
        "phase4.md",
        "phase5.md",
        "phase6.md",
        "single_pass.md",
        "iteration.md",
    )

    REQUIRED_REFERENCE_POINTER = "references/what_just_happened.md"
    REQUIRED_EMISSION_PHRASE = "## What just happened"

    def test_each_phase_prompt_references_decision_tree_file(self) -> None:
        for name in self.PROMPT_FILES:
            with self.subTest(prompt=name):
                path = PHASE_PROMPTS_DIR / name
                self.assertTrue(
                    path.is_file(),
                    f"phase_prompts/{name} must exist for the tail "
                    f"contract to be testable.",
                )
                text = path.read_text(encoding="utf-8")
                self.assertIn(
                    self.REQUIRED_REFERENCE_POINTER,
                    text,
                    f"phase_prompts/{name} must reference "
                    f"`{self.REQUIRED_REFERENCE_POINTER}` so the agent "
                    f"can look up which run-state template applies. "
                    f"The decision tree is single-sourced in the "
                    f"reference file; phase prompts MUST point at it "
                    f"rather than inline the tree.",
                )

    def test_each_phase_prompt_includes_emission_instruction(self) -> None:
        for name in self.PROMPT_FILES:
            with self.subTest(prompt=name):
                path = PHASE_PROMPTS_DIR / name
                text = path.read_text(encoding="utf-8")
                self.assertIn(
                    self.REQUIRED_EMISSION_PHRASE,
                    text,
                    f"phase_prompts/{name} must include the literal "
                    f"emission instruction `{self.REQUIRED_EMISSION_PHRASE}` "
                    f"so the agent knows the exact block header to "
                    f"emit. A softer phrasing (`a summary block`, "
                    f"`a recap`) would lose the load-bearing literal.",
                )


class IterationPromptIncludesWhatJustHappenedTailTests(unittest.TestCase):
    """The iteration prompt is built at runtime by
    `bin.run_playbook.iteration_prompt(strategy, prefix=...)`, which
    loads `phase_prompts/iteration.md` and applies substitutions. The
    tail must survive substitution and appear in the rendered prompt
    for every strategy. Bite-verified by reverting the tail addition
    in `phase_prompts/iteration.md` (then this test fires across all
    four strategies); restoring makes it pass.
    """

    STRATEGIES = ("gap", "unfiltered", "parity", "adversarial")

    REQUIRED_REFERENCE_POINTER = "references/what_just_happened.md"
    REQUIRED_EMISSION_PHRASE = "## What just happened"

    def test_every_strategy_renders_tail(self) -> None:
        for strategy in self.STRATEGIES:
            with self.subTest(strategy=strategy):
                body = run_playbook.iteration_prompt(strategy)
                self.assertIn(
                    self.REQUIRED_REFERENCE_POINTER,
                    body,
                    f"iteration_prompt({strategy!r}) must contain a "
                    f"reference to `{self.REQUIRED_REFERENCE_POINTER}`. "
                    f"Without it, the agent cannot pick the right "
                    f"State I / State F template at iteration end.",
                )
                self.assertIn(
                    self.REQUIRED_EMISSION_PHRASE,
                    body,
                    f"iteration_prompt({strategy!r}) must contain the "
                    f"literal `{self.REQUIRED_EMISSION_PHRASE}` emission "
                    f"instruction. v1.5.7 UX contract: the block is "
                    f"mandatory at every iteration boundary.",
                )

    def test_iteration_prompt_tail_survives_prefix_application(self) -> None:
        """The runner sometimes wraps the iteration prompt with a
        ``prefix`` argument (e.g., session continuity instructions).
        The tail must survive the prefix wrap — i.e., still appear in
        the final rendered prompt body."""
        body = run_playbook.iteration_prompt("gap", prefix="PREFIX-HEADER")
        self.assertIn("PREFIX-HEADER", body, "prefix should be present")
        self.assertIn(
            self.REQUIRED_REFERENCE_POINTER,
            body,
            "tail's reference pointer must survive prefix application",
        )
        self.assertIn(
            self.REQUIRED_EMISSION_PHRASE,
            body,
            "tail's emission instruction must survive prefix application",
        )


if __name__ == "__main__":
    unittest.main()
