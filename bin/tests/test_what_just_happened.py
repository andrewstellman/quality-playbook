"""Tests for the v1.5.7 UX contract: mandatory `## What just happened`
+ `### What to do next` block at every phase boundary.

Surfaces pinned:

1. `references/what_just_happened.md` exists with the thirteen required
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
# v1.5.8 instruction 208: bundled skill files moved to skills/quality-playbook/.
_SKILL_DIR = REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
REFERENCE_PATH = _SKILL_DIR / "references" / "what_just_happened.md"
SKILL_PATH = _SKILL_DIR / "SKILL.md"
PHASE_PROMPTS_DIR = _SKILL_DIR / "phase_prompts"


class WhatJustHappenedReferenceExistsTests(unittest.TestCase):
    """`references/what_just_happened.md` is the single source of
    truth for the decision tree. The test verifies it exists with the
    thirteen required run-state rows. Bite-verified by renaming the
    file aside (then the existence assertion fires); restoring makes
    the test pass again.
    """

    REQUIRED_RUN_STATES = (
        "State P1",  # Phase 1 only completed (Mode A multi-pass)
        "State P2",  # Phase 2 just completed (added in instr 038 fix-up)
        "State P3",  # Phase 3 just completed (added in instr 038 fix-up)
        "State P4",  # Phase 4 just completed (added in instr 038 fix-up)
        "State P5",  # Phase 5 just completed (added in instr 038 fix-up)
        "State C",   # Phase 1 + code-only mode
        "State G",   # Phase 2 abort + D1 preservation
        "State E",   # Agent-emitted unrecoverable error (added in instr 038 fix-up)
        "State S",   # pass-process / fail-recall (the v1.5.7 load-bearing case)
        "State B",   # Phases 1-6 baseline with N bugs
        "State I",   # One or more iteration strategies done
        "State F",   # All four iterations done
        "State R",   # Recheck done
    )

    # v1.5.7 instruction 038 round-2 fix-up: also pin that each state
    # carries an explicit `### State <X> —` template heading in the
    # reference file (not just a passing mention). A regression that
    # deletes a template section's heading would still leave the state
    # name in the rules-table row above, so checking the name alone
    # isn't sufficient — pin the heading too.
    REQUIRED_TEMPLATE_HEADINGS = (
        "### State P1",
        "### State P2",
        "### State P3",
        "### State P4",
        "### State P5",
        "### State C",
        "### State G",
        "### State E",
        "### State S",
        "### State B",
        "### State I",
        "### State F",
        "### State R",
    )

    def test_reference_file_exists(self) -> None:
        self.assertTrue(
            REFERENCE_PATH.is_file(),
            f"references/what_just_happened.md must exist at "
            f"{REFERENCE_PATH}. v1.5.7 UX contract single-source-of-"
            f"truth file; SKILL.md and every phase prompt point at it.",
        )

    def test_reference_file_lists_all_thirteen_run_states(self) -> None:
        """v1.5.7 instruction 038 round-2 fix-up: the state inventory
        expanded from 8 (P1, C, G, S, B, I, F, R) to 13 after round-1
        added P2/P3/P4/P5 + State E. This test now pins all 13."""
        text = REFERENCE_PATH.read_text(encoding="utf-8")
        for state_label in self.REQUIRED_RUN_STATES:
            self.assertIn(
                state_label,
                text,
                f"references/what_just_happened.md must define the "
                f"`{state_label}` run-state row. The 13 states "
                f"(P1, P2, P3, P4, P5, C, G, E, S, B, I, F, R) cover "
                f"every terminal the v1.5.7 contract ships against.",
            )

    def test_reference_file_has_explicit_template_for_every_state(self) -> None:
        """v1.5.7 instruction 038 round-2 fix-up: each state must
        carry a `### State <X> — …` template heading in the
        decision-tree section. A regression that deleted, say, the
        P4 template section would still leave 'State P4' in the
        rules table above and pass the name-presence test — pinning
        the heading too closes that gap."""
        text = REFERENCE_PATH.read_text(encoding="utf-8")
        for heading in self.REQUIRED_TEMPLATE_HEADINGS:
            self.assertIn(
                heading,
                text,
                f"references/what_just_happened.md must include the "
                f"`{heading} — …` template heading. Each state needs "
                f"its own per-template prose; substituting a phase "
                f"number into a different template (as round-1's "
                f"State Pn fallback did) produced factually wrong "
                f"messages and was the load-bearing complaint that "
                f"closed codex round-1 finding #3.",
            )

    def test_reference_file_includes_contract_and_do_not_sections(self) -> None:
        text = REFERENCE_PATH.read_text(encoding="utf-8")
        # v1.5.7 instruction 038 codex review fix-up: the contract
        # section was renamed from "## Contract" to "## Scope and
        # contract" so the load-bearing scope clarification (which
        # boundaries are in-scope vs. out-of-scope per finding #5
        # of the codex review) is visible from the heading itself.
        for required_heading in ("## Scope and contract", "## DO NOT"):
            self.assertIn(
                required_heading,
                text,
                f"references/what_just_happened.md must include the "
                f"`{required_heading}` section. The scope-and-contract "
                f"section establishes both the mandatory emission rule "
                f"AND the out-of-scope cases (aborted_missing_docs, "
                f"SIGKILL/crash); the DO NOT section enforces plain-"
                f"English framing.",
            )


class SkillMdEmitsWhatJustHappenedContractTests(unittest.TestCase):
    """SKILL.md must carry the cross-phase orientation-spine section
    that wires the contract into the skill body. Without this, phase
    prompts could carry the tail but the orchestration spine wouldn't
    say "this is mandatory at every phase boundary." Bite-verified by
    deleting the section from SKILL.md (then the test fires); restoring
    makes it pass.

    v1.5.7 instruction 038 codex review fix-up (finding #6): the
    section-presence + pointer + canonical-phrase checks were too
    shallow — they could pass even if the SKILL.md section lost
    `### What to do next`, "LAST visible output," or the full
    thirteen-state coverage. This class now extracts the section
    body and asserts the full contract surface inside it, not just
    the header presence.
    """

    REQUIRED_SECTION_HEADER = '## "What just happened" — required final block at every phase boundary'
    REQUIRED_REFERENCE_POINTER = "references/what_just_happened.md"
    REQUIRED_CONTRACT_PHRASE = "every phase boundary"

    # v1.5.7 instruction 038 fix-up: the SKILL.md section body must
    # carry both block headings, the "last visible content" rule,
    # and the single-source-of-truth pointer. Each phrase is a
    # load-bearing piece of the agent-prompt contract.
    #
    # v1.5.7 instruction 041 NC-sub-6 polish: the "last" pin was
    # tightened to "**last** visible" so that a future edit that
    # removed the load-bearing rule but kept any other use of "last"
    # (e.g., "last 10 events" elsewhere in the body) cannot silently
    # pass. The pin requires both the markdown-bold marker and the
    # "visible" follow-on word from the canonical phrasing at
    # SKILL.md:1154 ("as the **last** visible content of the phase").
    REQUIRED_SECTION_BODY_PHRASES = (
        "## What just happened",        # the literal block header
        "### What to do next",          # the literal second-half subheader
        "**last** visible",             # the "last visible content" rule (tightened in instruction 041)
        "every phase boundary",         # the scope clause
        "Markdown",                     # the chat-rendering reason
        "Single source of truth",       # the no-inline-rewrite discipline (canonical capitalization in SKILL.md)
    )

    @classmethod
    def _extract_section_body(cls, text: str) -> str:
        """Return the SKILL.md region from the section header up to
        (but not including) the next top-level `## ` heading. If the
        section header isn't present, return the empty string so the
        caller's `assertIn` fires correctly.

        Skips fenced code blocks (``` ... ```) when scanning for the
        next section delimiter — otherwise the section body's
        own block-shape demo (which includes `## What just happened`
        inside a fence) would be misread as a sibling section."""
        marker = cls.REQUIRED_SECTION_HEADER
        if marker not in text:
            return ""
        start = text.index(marker)
        # Walk line-by-line from just after the section header,
        # tracking whether we're inside a ``` fenced code block.
        lines = text[start + len(marker):].split("\n")
        in_fence = False
        body_end_line = len(lines)  # default: end of text
        for i, line in enumerate(lines):
            if line.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if line.startswith("## "):
                body_end_line = i
                break
        body_tail = "\n".join(lines[:body_end_line])
        return marker + body_tail

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

    def test_skill_md_section_body_carries_full_contract(self) -> None:
        """v1.5.7 instr 038 fix-up: the section body — not just the
        header or some unrelated table row — must carry every
        load-bearing phrase of the contract. This guards against a
        future edit that keeps the section header but guts the
        body."""
        text = SKILL_PATH.read_text(encoding="utf-8")
        body = self._extract_section_body(text)
        self.assertTrue(
            len(body) > 200,
            f"SKILL.md's What-just-happened section body must be "
            f"substantive (>200 chars); got {len(body)} chars. A "
            f"section that's only the header is not a contract.",
        )
        for phrase in self.REQUIRED_SECTION_BODY_PHRASES:
            self.assertIn(
                phrase,
                body,
                f"SKILL.md's `{self.REQUIRED_SECTION_HEADER}` section "
                f"body must contain the literal phrase `{phrase!r}`. "
                f"Each required phrase is load-bearing: the two block "
                f"headings (`## What just happened` / `### What to "
                f"do next`) pin the canonical block shape; the 'last "
                f"visible content' rule pins emission ordering; the "
                f"'every phase boundary' phrase pins scope; the "
                f"Markdown-rendering reason pins WHY it goes in chat "
                f"not just PROGRESS.md; the single-source-of-truth "
                f"pointer pins the no-inline-rewrite rule. Missing "
                f"any of these in the section body silently degrades "
                f"the contract.",
            )

    def test_skill_md_section_body_points_at_reference_file(self) -> None:
        """v1.5.7 instr 038 fix-up: the reference pointer must appear
        INSIDE the section body, not just somewhere else in SKILL.md
        (e.g., the Reference Files table). The agent reads the
        orientation-spine section first; the pointer has to be there
        to be discoverable from that reading path."""
        text = SKILL_PATH.read_text(encoding="utf-8")
        body = self._extract_section_body(text)
        self.assertIn(
            self.REQUIRED_REFERENCE_POINTER,
            body,
            f"SKILL.md's What-just-happened section BODY must include "
            f"the cross-reference `{self.REQUIRED_REFERENCE_POINTER}` "
            f"(not just the Reference Files table row). The orientation-"
            f"spine reader has to discover the decision tree from this "
            f"section, not from a table 30 lines later.",
        )

    def test_skill_md_uses_canonical_contract_phrase(self) -> None:
        """Preserved from the round-1 baseline: the canonical scope
        phrase must appear somewhere in SKILL.md. The
        section-body test above is stricter; this assertion remains
        as a coarse-grained guard against the phrase migrating out
        of SKILL.md entirely (e.g., into a separate docs/ file)."""
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn(
            self.REQUIRED_CONTRACT_PHRASE,
            text,
            f"SKILL.md must use the canonical phrase "
            f"`{self.REQUIRED_CONTRACT_PHRASE}` so the rule's scope "
            f"is unambiguous. A doc edit that softens it to "
            f"'sometimes' or 'where appropriate' would silently "
            f"degrade the contract.",
        )


class PhasePromptsIncludeWhatJustHappenedTailTests(unittest.TestCase):
    """Every `phase_prompts/*.md` that the runner loads must include
    BOTH `## What just happened` AND `### What to do next` emission
    instructions, the "LAST visible output" ordering rule, and the
    single-source pointer at `references/what_just_happened.md`.
    Bite-verified by stripping the tail from any single phase prompt
    (then that subTest fires); restoring makes it pass.

    v1.5.7 instruction 038 codex review fix-up (finding #6): the
    round-1 tests checked only `## What just happened` and the
    pointer; a prompt could lose `### What to do next` or the "LAST
    visible output" ordering rule and still pass. This class now
    asserts the full per-prompt contract.
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
    REQUIRED_BLOCK_HEADER = "## What just happened"
    REQUIRED_SUBHEADER = "### What to do next"
    REQUIRED_ORDERING_PHRASE = "LAST"  # "as the LAST visible output"

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
                    self.REQUIRED_BLOCK_HEADER,
                    text,
                    f"phase_prompts/{name} must include the literal "
                    f"emission instruction `{self.REQUIRED_BLOCK_HEADER}` "
                    f"so the agent knows the exact block header to "
                    f"emit. A softer phrasing (`a summary block`, "
                    f"`a recap`) would lose the load-bearing literal.",
                )

    def test_each_phase_prompt_includes_what_to_do_next_subheader(self) -> None:
        """v1.5.7 instr 038 fix-up: a phase prompt that names only
        `## What just happened` without also naming `### What to do
        next` would let an agent emit a block missing the
        actionable second half. Without the second half, the user
        has no concrete next prompt — the whole point of the v1.5.7
        UX defect closure."""
        for name in self.PROMPT_FILES:
            with self.subTest(prompt=name):
                path = PHASE_PROMPTS_DIR / name
                text = path.read_text(encoding="utf-8")
                self.assertIn(
                    self.REQUIRED_SUBHEADER,
                    text,
                    f"phase_prompts/{name} must include the literal "
                    f"`{self.REQUIRED_SUBHEADER}` subheader so the "
                    f"agent emits the actionable second half of the "
                    f"block. The UX defect this contract closes is "
                    f"adopters not knowing what to type next; the "
                    f"subheader is the load-bearing half.",
                )

    def test_each_phase_prompt_pins_last_output_ordering(self) -> None:
        """v1.5.7 instr 038 fix-up: a phase prompt that names the
        block headers but doesn't say "as the LAST visible output"
        would let the agent emit the block mid-summary, where it'd
        be buried below later artifact discussion. The block MUST
        be the last visible chat content so adopters see it bright
        at the end of scrollback."""
        for name in self.PROMPT_FILES:
            with self.subTest(prompt=name):
                path = PHASE_PROMPTS_DIR / name
                text = path.read_text(encoding="utf-8")
                self.assertIn(
                    self.REQUIRED_ORDERING_PHRASE,
                    text,
                    f"phase_prompts/{name} must use the literal "
                    f"`{self.REQUIRED_ORDERING_PHRASE}` phrase (as in "
                    f"'as the LAST visible output in chat') to pin "
                    f"emission ordering. Without this, the agent "
                    f"could emit the block mid-chat where it gets "
                    f"buried below later artifact discussion.",
                )


class IterationPromptIncludesWhatJustHappenedTailTests(unittest.TestCase):
    """The iteration prompt is built at runtime by
    `bin.run_playbook.iteration_prompt(strategy, prefix=...)`, which
    loads `phase_prompts/iteration.md` and applies substitutions. The
    tail must survive substitution and appear in the rendered prompt
    for every strategy. Bite-verified by reverting the tail addition
    in `phase_prompts/iteration.md` (then this test fires across all
    four strategies); restoring makes it pass.

    v1.5.7 instruction 038 codex review fix-up (finding #6): the
    round-1 assertions checked only the pointer + `## What just
    happened`. They missed: the `### What to do next` second-half
    subheader, and the State I / State F disambiguation hint the
    iteration prompt is supposed to give the agent (per the
    references/what_just_happened.md decision tree: State I if more
    strategies remain in the gap → unfiltered → parity → adversarial
    cycle; State F if this iteration is the last one). This class
    now asserts the full per-iteration-strategy contract.
    """

    STRATEGIES = ("gap", "unfiltered", "parity", "adversarial")

    REQUIRED_REFERENCE_POINTER = "references/what_just_happened.md"
    REQUIRED_BLOCK_HEADER = "## What just happened"
    REQUIRED_SUBHEADER = "### What to do next"
    REQUIRED_STATE_I_HINT = "State I"
    REQUIRED_STATE_F_HINT = "State F"
    REQUIRED_ORDERING_PHRASE = "LAST"  # "as the LAST visible output"

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
                    self.REQUIRED_BLOCK_HEADER,
                    body,
                    f"iteration_prompt({strategy!r}) must contain the "
                    f"literal `{self.REQUIRED_BLOCK_HEADER}` emission "
                    f"instruction. v1.5.7 UX contract: the block is "
                    f"mandatory at every iteration boundary.",
                )

    def test_every_strategy_renders_what_to_do_next_subheader(self) -> None:
        """v1.5.7 instr 038 fix-up: pin that the iteration prompt
        names BOTH halves of the block, not just the first header."""
        for strategy in self.STRATEGIES:
            with self.subTest(strategy=strategy):
                body = run_playbook.iteration_prompt(strategy)
                self.assertIn(
                    self.REQUIRED_SUBHEADER,
                    body,
                    f"iteration_prompt({strategy!r}) must contain the "
                    f"`{self.REQUIRED_SUBHEADER}` subheader. The "
                    f"second half (next-step prompt) is the load-"
                    f"bearing half for adopter UX; without it the "
                    f"agent could emit a block missing the action.",
                )

    def test_every_strategy_includes_state_i_f_disambiguation(self) -> None:
        """v1.5.7 instr 038 fix-up: the iteration prompt tail must
        name BOTH `State I` and `State F` so the agent knows the
        disambiguation rule (State I if more iterations remain;
        State F at the end of the gap → unfiltered → parity →
        adversarial cycle). A prompt that names only one of them
        would let the agent default to that state regardless of
        cycle position."""
        for strategy in self.STRATEGIES:
            with self.subTest(strategy=strategy):
                body = run_playbook.iteration_prompt(strategy)
                self.assertIn(
                    self.REQUIRED_STATE_I_HINT,
                    body,
                    f"iteration_prompt({strategy!r}) must name "
                    f"`{self.REQUIRED_STATE_I_HINT}` so the agent "
                    f"knows the mid-cycle template applies when more "
                    f"strategies remain.",
                )
                self.assertIn(
                    self.REQUIRED_STATE_F_HINT,
                    body,
                    f"iteration_prompt({strategy!r}) must name "
                    f"`{self.REQUIRED_STATE_F_HINT}` so the agent "
                    f"knows the all-four-done template applies when "
                    f"this is the last iteration in the cycle.",
                )

    def test_every_strategy_pins_last_output_ordering(self) -> None:
        """v1.5.7 instr 038 fix-up: pin the 'as the LAST visible
        output' ordering rule in the iteration prompt too — same
        rationale as the phase-prompt equivalent."""
        for strategy in self.STRATEGIES:
            with self.subTest(strategy=strategy):
                body = run_playbook.iteration_prompt(strategy)
                self.assertIn(
                    self.REQUIRED_ORDERING_PHRASE,
                    body,
                    f"iteration_prompt({strategy!r}) must use the "
                    f"`{self.REQUIRED_ORDERING_PHRASE}` ordering "
                    f"phrase. Without it, the agent could emit the "
                    f"block mid-summary where it gets buried.",
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
            self.REQUIRED_BLOCK_HEADER,
            body,
            "tail's emission instruction must survive prefix application",
        )
        self.assertIn(
            self.REQUIRED_SUBHEADER,
            body,
            "tail's `### What to do next` must survive prefix application",
        )


if __name__ == "__main__":
    unittest.main()
