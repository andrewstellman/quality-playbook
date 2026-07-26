# Output for 029-feature-h-guardrail-carveout.md
**Status:** completed

## What this instruction was
The live virtio acceptance run surfaced a **self-contradiction inside SKILL.md**: the
Feature H persona validation pass (`bin/persona_apply.run_feature_h`, run automatically
at the Phase 2→3 boundary; instr 021, Design §8b) must spawn fresh-context persona
sub-agents, but SKILL.md's "no sub-agent delegation (phases 1–5)" guardrail forbids the
Task tool. A faithful agent correctly obeyed the guardrail, **disabled Feature H, and
disclosed the conflict** — so the release's headline validation feature was bundled and
wired yet **never actually ran** for an adopter. Fix (operator decision, option A):
carve out the persona pass as an **explicit, narrowly-scoped second sanctioned
exception**, mirroring the existing Phase 6 verification exception.

## Terminal verdict: unanimous SHIP (0 FIX-REQUIRED)
| Charter | Verdict |
|---------|---------|
| A — Exception narrowly scoped to `run_feature_h`; neither failure mode reopened | **SHIP** |
| B — Operator visibility preserved (mandatory review summary + revertible + opt-out) | **SHIP** |
| C — SKILL.md + boundary prose internally consistent; no remaining forbid+require sentence | **SHIP** |

Each panelist reviewed the committed content of `5a82e98` and adversarially mutation-bit
the carve-out (worktrees were cut from an ancestor, so panelists read the fix via
`git show 5a82e98:<path>` and ran the pinned tests against the fixed content via
swap-and-restore).

## The reconciled guardrail text (before → after)

**Before.** SKILL.md carried an unqualified rule — *"Synchronous execution — no
sub-agent delegation … Do NOT use the Task tool … for phases 1–5"* (closing failure
mode (a) a delegated phase dies silently in a lost session; (b) a spawned sub-skill
fabricates a gate PASS) — while the Feature H auto-run description said the persona pass
runs **automatically** and spawns **fresh-context, tool-restricted personas**. The two
were mutually contradictory: one place forbade exactly the spawn another place required.
Phase 6 verification already had a sanctioned EXCEPTION block; the persona pass did not.

**After.** Three SKILL.md additions + two boundary-prose additions, all naming the
persona pass as a **second sanctioned exception, sibling to the Phase 6 verification
exception**:
1. **New EXCEPTION block** after the Phase 6 exception — the general no-sub-agent rule
   still governs delegating a *phase's execution* (Phases 1–5); the persona validation
   pass is a scoped exception because (a) it does **not** delegate a phase's execution —
   it is a bounded validation remediation that runs at one boundary and returns to the
   session, never a worker running phases 2–6; (b) operator visibility is **preserved
   and mandatory** — it writes `quality/persona_review_summary.json`, its changes are
   `agent-validation`-tagged and revertible, and it is opt-out. "Scoped strictly to this
   pass; the no-sub-agent rule still holds for all other Phase 1–5 work."
2. **Inline note on numbered guardrail #1** — the automatic persona pass MAY spawn its
   fresh-context, tool-restricted personas; it is a bounded, operator-visible validation
   *remediation*, not a delegated phase, so neither failure mode applies; "all OTHER
   Phase 1–5 sub-agent delegation stays forbidden."
3. **Note on the Feature H description** — spawning its personas is a sanctioned
   exception (the second EXCEPTION block in the Mode A walkthrough, sibling to Phase 6
   verification), so a faithful agent runs it here rather than disabling it.
4. **`references/requirements_pipeline.md` §E.9** — the live sub-agent spawn is a
   sanctioned exception (instr 029; SKILL.md Mode A "EXCEPTION: the Feature H persona
   validation pass may spawn its personas"); a faithful agent runs the pass here and does
   **not** disable Feature H over a perceived guardrail conflict.
5. **`references/phase2_generation_guide.md`** — a Phase 2→3 boundary note naming the
   persona pass as the sanctioned exception, with the decisive imperative at the decision
   point: "do **not** disable Feature H over a perceived guardrail conflict; the carve-out
   is explicit."

## Acceptance oracle — pass/fail
| # | Item | Result |
|---|------|--------|
| 1 | No contradiction remains — persona pass is a named exception; a faithful agent runs it | **PASS** — Charter C (mutation-bite: the carve is load-bearing; no second missed forbidder) |
| 2 | Scope preserved — all OTHER Phase 1–5 delegation + both failure-mode patterns still forbidden; exception names only `run_feature_h` | **PASS** — Charter A |
| 3 | Visibility preserved — carve-out requires the operator-visible review summary + opt-out; not weakened | **PASS** — Charter B (confirmed against Design §8b + `persona_apply.py`) |
| 4 | Boundary prose consistent — Phase 2→3 guidance names the persona pass as the sanctioned exception | **PASS** — requirements_pipeline §E.9 + phase2_generation_guide |
| 5 | Doc-consistency / SKILL.md lint green; full suite green | **PASS** — 2787 / 0 / 13, Python 3.14.6; `test_mode_a_self_execution_contract` + `test_skill_md_size` (19,474 < 32,000) green |

The pinned mode-A contract tests stay green because an exception was **added**, not the
forbidding rule removed — the general `:94`/`:96` forbidders (which the tests `assertIn`)
are untouched.

## Files changed
| File | Change |
|------|--------|
| `SKILL.md` | new EXCEPTION block (after Phase 6 exception); inline note on guardrail #1; sanctioned-exception note on the Feature H description |
| `references/requirements_pipeline.md` | §E.9 sanctioned-exception sentence at the live persona-spawn description |
| `references/phase2_generation_guide.md` | Phase 2→3 boundary note naming the persona pass as the sanctioned exception |
| `docs/process/QPB_v1.6.0_Instruction_029_Self_Council/synthesis.md` | tracked Council synthesis |

## Commits made (branch `1.6.0`, local only — never pushed)
- `5a82e98` — the guardrail carve-out (SKILL.md + two boundary-prose files).
- `0877145` — tracked self-Council synthesis.
- `<output commit>` — runner: output for instruction 029.

## Notes
- SKILL.md is a symlink from the plugin path to the repo-root `SKILL.md`; the real
  repo-root file was edited (the plugin path resolves through the symlink).
- The orchestrator's uncommitted `docs/design/QPB_v1.6.0_Design.md` edit was left alone
  (not staged).
- A soft, non-blocking Charter-C observation: SKILL.md `:94` ("Spawn a sub-agent via
  your Task tool") could take a "(except the two sanctioned exceptions below)"
  parenthetical for belt-and-suspenders parity with guardrail #1 — not required for
  consistency, and it is the deliberately-pinned general forbidder, so it was left as is.

## Remaining release items (unchanged — for the orchestrator)
Now that Feature H can run live: broader 1.6.0 acceptance/release testing + Phase 8
tag/merge; set OD-9 from instr 019 data (0 spurious grounded adds); Feature-G
non-plaintext-contract → FORMAL_DOC wiring; chi/express/virtio Slice-1 coherence-fixture
regeneration (a real run); OD-11 drop/selective-revert BUG-reference re-point hardening;
design-doc refresh (Design.md still describes the removed fabrication-tell); minor
cleanups (redundant add-REQ regex arm); setup_repos.sh flat `.github` install
completeness (skill-template.gitignore + ai_context/TOOLKIT.md) decision.

## Artifacts
- Gitignored: `runner/quality-playbook/reviews/029_self_council/` (three panelist verdicts).
- Tracked: `docs/process/QPB_v1.6.0_Instruction_029_Self_Council/synthesis.md`.
