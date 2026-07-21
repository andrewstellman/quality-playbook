# Instruction 004 self-Council — Round 2 (closure)

Closure re-review of the fix commit **`cb3d966`** (closed C's orphan + B's marker-list
P2). Each closure panelist in its own isolated git worktree. Panelist A was not re-run —
its charter's surface (the fail-closed check in quality_gate.py) was untouched by the fix
round (which changed only two reference docs), so its Round-1 SHIP stands.

**Outcome: unanimous SHIP.**

---

## Panelist C — placement completeness → SHIP (orphan CLOSED)

- `references/phase1_exploration_guide.md:510` now states the Phase 2→3 boundary
  placement with the opt-in framing and the one-reminder-at-playbook-end fallback; the
  pre-reversal "Phase 7 offers … not a Phase 2 artifact" text is gone.
- **Independent sweep, nine surfaces:** the seven placement surfaces (six previously
  correct + the fixed phase1_exploration_guide.md) all agree — primary offer at Phase
  2→3, opt-in/never-auto-started, one reminder at end. The remaining hits
  (requirements_pipeline.md "after the pipeline" mechanics, artifact_contract.md table
  rows, phase2_generation_guide.md "opening move / natural organizer") carry no placement
  claim and are not orphans. Grep for `Phase 7 offers` and `not a Phase 2 artifact`
  returns zero hits across references/, phase_prompts/, SKILL.md.
- No new inconsistency introduced. Suite green (phase-prompt hash guards accept the edits).

## Panelist B — format-doc correctness → SHIP (P2 CLOSED)

- `references/phase2_generation_guide.md:146-155`: the prohibition list is split into
  contract-disabling forms (bold, em-dash, period — parser finds no heading, FAILs) and
  read-but-nonconforming forms (wrong level → WARN; un-padded `### REQ-7:` → parsed as
  REQ-7). Line 155 now states the gate does not reject un-padded IDs — a generator
  convention, not a checker rule.
- **Regex-behavior check (run directly):** `### REQ-7: Title` matches `_RENDER_REQ_HEADING_RE`;
  `int(m.group(2))==7` (padding discarded at quality_gate.py:7279); the sequential-ID
  check operates on int values only (a `REQ-001, REQ-2, REQ-003` sequence parses to
  `(1,2,3)`). The doc's claim now matches the mechanism exactly.
- Three-way binding intact and symmetric; worked example unchanged and correct; generator
  routing (phase2.md → phase2_generation_guide.md) confirmed. Fix diff narrowly scoped
  (only the two reference docs). Suite green.

## Panelist A — fail-closed check → SHIP (Round-1, stands)

Fail-closed logic in quality_gate.py was not touched by the fix round; the Round-1 SHIP
(split correct across edge cases, mutation-bitten, version-gate ordering correct, no
false positives) is unaffected.

## Disposition

Unanimous SHIP, zero open findings. Cleared to file. Worker never pushes/merges — the
operator lands the branch.

**Surfaced for the orchestrator (out of the worker's charter):** the design spec §5.3
(fail-closed) and §6 (placement) are UNCOMMITTED in the working tree — `git show
HEAD:docs/design/QPB_v1.6.0_Design.md` contains neither. The instruction treated them as
"the spec, read them first," but they are not in git, so the Round-1 panelists (reviewing
committed state) could not see them, and the design doc internally contradicts itself
(old "playbook-end summary offers" at Design:174 coexists with the new §6). The
orchestrator owns docs/design/ and should commit §5.3/§6 and remove the contradicting old
lines.
