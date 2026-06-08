"""SKILL.md self-encoding prose-contract tests (v1.5.4 Phase 3.9, B-18b).

After the Phase 3.9 rewrite, SKILL.md self-encodes the canonical
invocation, bootstrap mode, v1.5.4 mechanics pointers, the
operational guardrails, and the output artifact contract — so that a
single-line operator prompt ("Run the Quality Playbook") pointed at
any AI agent against any QPB-installed target produces a v1.5.4-shape
bootstrap run without further hand-holding.

These tests are coarse string-presence assertions. They protect
against accidental regressions during future SKILL.md edits — if a
maintainer trims the prose and drops the canonical-invocation
reference, the no-delegation guardrail, etc., the matching test
fires.

The tests do NOT pin exact wording. The brief explicitly framed
these as "string-presence" assertions; they catch the load-bearing
content disappearing, not phrasing changes. If a future edit
substantively reshapes the section AND the corresponding test fails,
update the test alongside the prose — the test pins the contract,
not a literal copy.
"""

from __future__ import annotations

import unittest
from pathlib import Path


# v1.5.8 instruction 208: SKILL.md + references/ moved into the plugin skill folder.
_SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "quality-playbook"
SKILL_MD = _SKILL_DIR / "SKILL.md"
PHASE2_GUIDE = _SKILL_DIR / "references" / "phase2_generation_guide.md"


def _read_skill_md() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def _read_phase2_corpus() -> str:
    """v1.5.7 Phase 7: SKILL.md + references/phase2_generation_guide.md
    concatenated. After the Phase 7 trim, Phase 2 guardrail / completion-
    gate prose lives in the references file; SKILL.md retains only a
    pointer. Tests that assert Phase 2 prose content now check the
    combined corpus (the agent reads both files at Phase 2 entry per
    `phase_prompts/phase2.md`)."""
    text = SKILL_MD.read_text(encoding="utf-8")
    # v1.5.7 Phase 7 FIXUP-1: after the trim, Phase 2 guardrail prose
    # lives ONLY in references/phase2_generation_guide.md. The prior
    # conditional `if PHASE2_GUIDE.is_file()` was correct during the
    # move (when prose existed in both SKILL.md and the references
    # file) but is a silent-failure vector now — deleting the
    # references file would degrade 4 guard tests to vacuous passes.
    # The assertion fails loudly instead.
    assert PHASE2_GUIDE.is_file(), (
        "references/phase2_generation_guide.md missing — Phase 7 trim "
        "moved Phase 2 guardrail prose there; deletion silently "
        "degrades 4 guard tests to vacuous passes"
    )
    text += "\n" + PHASE2_GUIDE.read_text(encoding="utf-8")
    return text


class SkillMdSelfEncodingTests(unittest.TestCase):
    """v1.5.4 Phase 3.9 (B-18b): pin the load-bearing prose
    contract. Each test corresponds to one of the 6 brief-mandated
    string-presence assertions."""

    def test_skill_md_documents_canonical_invocation(self) -> None:
        text = _read_skill_md()
        # The canonical invocation pattern. Operators / AI agents
        # reading this section should infer `python3 -m bin.run_playbook
        # <target>` from the prose without ambiguity.
        self.assertIn("python3 -m bin.run_playbook", text)

    def test_skill_md_documents_bootstrap_mode(self) -> None:
        text = _read_skill_md()
        # "Bootstrap" framing: target == QPB repo, archive of existing
        # quality/ to previous_runs/ is automatic, the operator
        # doesn't need to clean anything manually.
        self.assertIn("Bootstrap mode", text)
        self.assertIn("python3 -m bin.run_playbook .", text)
        self.assertIn("previous_runs", text)

    def test_skill_md_names_role_map_artifact(self) -> None:
        text = _read_skill_md()
        # v1.5.4 architecture anchor: the role map is the canonical
        # routing input for downstream pipelines. Naming it in
        # SKILL.md makes the architecture operator-visible.
        self.assertIn("exploration_role_map.json", text)
        self.assertIn("schema_version", text)
        self.assertIn("target_role_breakdown", text)

    def test_skill_md_forbids_sub_agent_delegation(self) -> None:
        text = _read_skill_md()
        # The B-15 failure mode (Phase 1 completes, phases 2-6 die in
        # a delegated agent) is the most consequential v1.5.4
        # guardrail. SKILL.md must explicitly forbid sub-agent
        # delegation in operator-facing prose.
        self.assertIn("Task tool", text)
        # The "Synchronous execution" framing surfaces the
        # discipline as a hard constraint, not a suggestion.
        self.assertIn("Synchronous execution", text)
        self.assertIn("sub-agent", text)

    def test_skill_md_forbids_source_patching(self) -> None:
        text = _read_skill_md()
        # If you encounter a bug in QPB source mid-run, STOP +
        # report; do not patch. Codex's 2026-04-29 self-audit
        # attempt patched bin/archive_lib.py mid-run; the structural
        # backstop catches it but the prose discipline names it.
        self.assertIn("STOP and report", text)
        self.assertIn("Don't patch QPB source", text)

    def test_skill_md_forbids_sentinel_deletion(self) -> None:
        text = _read_skill_md()
        # `.gitignore !`-rule sentinels (.gitkeep files etc.) keep
        # tracked directories present. Codex deleted them; SKILL.md
        # must explicitly tell the agent not to.
        self.assertIn("sentinel", text.lower())
        self.assertIn(".gitkeep", text)
        self.assertIn("Don't delete sentinel files", text)


class SkillMdGuardrailsExtraTests(unittest.TestCase):
    """Additional contract pins for v1.5.4 mechanics not specifically
    enumerated in the 6-test brief but flagged by the brief's
    'Guardrails' subsection. These are auxiliary; failures here are
    real but lower-priority than the 6 above."""

    def test_skill_md_documents_git_ls_files_for_phase_1(self) -> None:
        text = _read_skill_md()
        # Phase 1 enumeration must use git ls-files (not os.walk /
        # find / listdir). Codex walked .git/ + .venv/ via os.walk
        # producing a 5287-entry role map.
        self.assertIn("git ls-files", text)

    def test_skill_md_lists_disallowed_path_prefixes(self) -> None:
        text = _read_skill_md()
        # The role-map validator rejects these prefixes; SKILL.md
        # documents them so the agent avoids producing them.
        for prefix in (".git/", ".venv/", "node_modules/"):
            self.assertIn(prefix, text)

    def test_skill_md_documents_full_run_default(self) -> None:
        text = _read_skill_md()
        # B-18a: bare invocation defaults to full-run. The prose
        # encodes this so the operator/AI doesn't add unnecessary
        # flags.
        self.assertIn("full run", text.lower())
        self.assertIn("6 phases", text)
        self.assertIn("4 iteration", text)


class SkillMdAgentsMdOwnershipTests(unittest.TestCase):
    """v1.5.4 F-2 (Bootstrap_Findings 2026-04-30): pin the orchestrator-
    owns-AGENTS.md contract so the Phase 2 LLM never modifies the
    target's `AGENTS.md` and trips the source-unchanged invariant.

    Failure mode being prevented: codex bootstrap test 2026-04-30
    where the Phase 2 LLM updated existing AGENTS.md (because old
    SKILL.md prose told it to), the orchestrator's source-unchanged
    gate detected the modification, and the run aborted before
    Phase 3."""

    def test_skill_md_phase2_does_not_own_agents_md(self) -> None:
        text = _read_skill_md()
        # Plan Overview Phase 2 entry must NOT enumerate AGENTS.md as
        # a Phase 2 deliverable. The contract is: orchestrator
        # generates it after Phase 6.
        self.assertIn(
            "AGENTS.md` at the target's repo root is generated by the orchestrator",
            text,
        )

    def test_skill_md_file6_section_forbids_phase2_agents_md(self) -> None:
        # v1.5.7 Phase 7: Phase 2 prose moved to references/
        # phase2_generation_guide.md; read combined corpus.
        text = _read_phase2_corpus()
        self.assertIn(
            "File 6: `AGENTS.md` (orchestrator-generated; you do NOT write this in Phase 2)",
            text,
        )

    def test_skill_md_artifact_inventory_marks_agents_md_post_phase_6(self) -> None:
        text = _read_skill_md()
        # The artifact inventory row for AGENTS.md must say "after
        # Phase 6" / "not a Phase 2 deliverable" — not "Phase 2".
        self.assertIn(
            "Generated by orchestrator after Phase 6 — not a Phase 2 deliverable",
            text,
        )

    def test_skill_md_phase2_completion_gate_excludes_agents_md(self) -> None:
        # v1.5.7 Phase 7: Phase 2 prose moved; read combined corpus.
        text = _read_phase2_corpus()
        self.assertIn("`AGENTS.md` is NOT in this list", text)


class SkillMdModeSplitTests(unittest.TestCase):
    """v1.5.4 F-1 (Bootstrap_Findings 2026-04-30): SKILL.md must
    distinguish the two execution modes — UI-context skill-direct
    (the agent IS the reasoning loop, walks through phases inline)
    vs. CLI-automation runner-driven (operator invokes
    `python3 -m bin.run_playbook` deliberately and the orchestrator
    spawns CLI agents per phase). Without this split SKILL.md
    produces the codex-on-codex indirection pathology where a UI
    agent mechanically invokes the runner that spawns a CLI version
    of itself."""

    def test_skill_md_pick_your_execution_mode_section_exists(self) -> None:
        text = _read_skill_md()
        self.assertIn("### Pick your execution mode", text)

    def test_skill_md_documents_mode_a_skill_direct(self) -> None:
        text = _read_skill_md()
        # Mode A header must exist and name "skill-direct" / "UI-context".
        self.assertIn("### Mode A — skill-direct walkthrough", text)
        self.assertIn("UI-context", text)

    def test_skill_md_documents_mode_b_runner_driven(self) -> None:
        text = _read_skill_md()
        self.assertIn("### Mode B — runner-driven invocation", text)
        self.assertIn("CLI-automation", text)

    def test_skill_md_mode_a_walkthrough_references_phase_prompts(self) -> None:
        """Mode A walkthrough must point the agent at the externalized
        phase_prompts/ files — that's the single-source-of-truth
        lever, and without the pointer the UI agent re-derives the
        prompt from scratch and drifts from the runner."""
        text = _read_skill_md()
        self.assertIn("phase_prompts/phaseN.md", text)

    def test_skill_md_mode_split_names_codex_on_codex_failure(self) -> None:
        """Pin the failure mode the split prevents — operator-visible
        rationale matters because it tells the agent why the choice
        is load-bearing, not just which mode to pick."""
        text = _read_skill_md()
        self.assertIn("codex-on-codex", text)

    def test_skill_md_default_to_mode_a_when_in_doubt(self) -> None:
        """The brief flagged that runtime detection (option a) is
        brittle; operator-instruction split (option b) is the
        adopted approach. The default-to-Mode-A guidance handles
        ambiguous cases without requiring runtime detection."""
        text = _read_skill_md()
        self.assertIn("default to Mode A", text)

    def test_skill_md_documents_cursor_runner_flag(self) -> None:
        """Mode B common-overrides table must list --cursor alongside
        the other runner flags. Operator visibility is the contract."""
        text = _read_skill_md()
        self.assertIn("`--cursor`", text)

    def test_skill_md_mode_a_documents_phase_0_phase_7_iteration_handoff(self) -> None:
        """Council 2026-04-30 P1-3: Mode A scopes itself to phases
        1..6; Phase 0/0b, Phase 7, and iteration strategies must be
        explicitly addressed (either inline or as Mode-B handoffs).
        The asymmetry the Council flagged was that Mode B covered
        these but Mode A silently dropped them."""
        text = _read_skill_md()
        # Section heading.
        self.assertIn("Mode A scope", text)
        # Each surface must be named.
        self.assertIn("Phase 0", text)
        self.assertIn("Phase 7", text)
        self.assertIn("Iteration strategies", text)
        # Mode-B handoff must be the documented escape for iterations.
        self.assertIn("--next-iteration --strategy", text)

    def test_skill_md_mode_b_points_at_bootstrap_hygiene(self) -> None:
        """Council 2026-04-30 P1-4: Mode B must point operators at
        the Bootstrap-mode hygiene paragraph for recovery from
        aborted runs. Without this pointer, only Mode A operators
        see the `git restore quality/` mechanic even though it
        applies to both modes."""
        text = _read_skill_md()
        self.assertIn(
            "Recovering from a partial / aborted runner-driven run", text
        )
        # The Mode B recovery section must explicitly reference the
        # Bootstrap-mode paragraph and the canonical command.
        self.assertIn("Bootstrap-run operator hygiene", text)
        self.assertIn("git restore quality/", text)


class SkillMdBootstrapHygieneTests(unittest.TestCase):
    """v1.5.4 F-4 (Bootstrap_Findings 2026-04-30): operator-hygiene
    note for recovering from a partial / aborted bootstrap run. The
    correct recovery is `git restore quality/` (and optionally `git
    clean -fd quality/`) — touching anything outside `quality/` will
    trip the source-unchanged invariant on the next run."""

    def test_skill_md_documents_partial_run_recovery(self) -> None:
        text = _read_skill_md()
        self.assertIn("Bootstrap-run operator hygiene", text)
        # The mechanical recovery command must appear verbatim so an
        # operator can copy it without ambiguity.
        self.assertIn("git restore quality/", text)

    def test_skill_md_recovery_warns_against_editing_outside_quality(self) -> None:
        text = _read_skill_md()
        self.assertIn("Do NOT** edit files outside `quality/`", text)


class SkillMdPhase2SourceGuardrailTests(unittest.TestCase):
    """v1.5.4 F-2: pin the Phase 2 source-modification guardrail.

    SKILL.md must tell the Phase 2 LLM that its filesystem effects
    are confined to `quality/` — no source files outside `quality/`
    may be created, modified, or deleted. This is the prose backstop
    behind the orchestrator's structural source-unchanged invariant
    (`_QPB_SOURCE_PATHS`)."""

    def test_skill_md_phase2_has_source_modification_guardrail(self) -> None:
        # v1.5.7 Phase 7: Phase 2 prose moved; read combined corpus.
        text = _read_phase2_corpus()
        self.assertIn("Phase 2 source-modification guardrail", text)

    def test_skill_md_phase2_guardrail_names_failure_mode(self) -> None:
        text = _read_skill_md()
        # The 2026-04-30 codex bootstrap test failure mode is named
        # in the prose so a future operator/AI understands WHY the
        # guardrail exists.
        self.assertIn("2026-04-30", text)
        self.assertIn("source-unchanged", text)

    def test_skill_md_phase2_guardrail_writes_only_into_quality(self) -> None:
        # v1.5.7 Phase 7: Phase 2 prose moved; read combined corpus.
        text = _read_phase2_corpus()
        self.assertIn("Phase 2 writes ONLY into `quality/`", text)


if __name__ == "__main__":
    unittest.main()
