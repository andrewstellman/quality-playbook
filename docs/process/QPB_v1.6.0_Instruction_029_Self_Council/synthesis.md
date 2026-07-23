# Instruction 029 — Feature H guardrail carve-out: self-Council synthesis

**Terminal verdict: unanimous SHIP** across all three charters, zero FIX-REQUIRED.
Reviewed commit `5a82e98`.

## What was reviewed
The live virtio acceptance run surfaced a self-contradiction inside SKILL.md: the
Feature H persona validation pass (`bin/persona_apply.run_feature_h`, run automatically
at the Phase 2→3 boundary; Design §8b) must spawn fresh-context persona sub-agents, but
SKILL.md's "Synchronous execution — no sub-agent delegation" guardrail forbids the Task
tool for phases 1–5. A faithful agent obeyed the guardrail, **disabled Feature H, and
disclosed the conflict** — so the release's headline validation feature was wired yet
never ran for an adopter. The fix (operator decision, option A) adds the persona pass as
an **explicit, narrowly-scoped second sanctioned exception** to the guardrail, mirroring
the existing Phase 6 verification exception, and makes the Phase 2→3 boundary prose
consistent so a live agent runs the pass rather than re-hitting the contradiction.

Because this touches a **safety guardrail that exists for two verified failure modes**
(a delegated phase dies silently in a lost session; a spawned sub-skill fabricates a
gate PASS), a full 3-charter self-Council ran. Each panelist reviewed the committed
content of `5a82e98` (the worktrees were cut from an ancestor, so panelists read the fix
via `git show 5a82e98:<path>` and ran the pinned tests against the fixed content via
swap-and-restore — valid reviews of the correct content).

## Files changed by 5a82e98
- `SKILL.md` — new EXCEPTION block after the Phase 6 exception; inline note appended to
  the numbered no-sub-agent guardrail (#1); sanctioned-exception note on the Feature H
  auto-run description.
- `references/requirements_pipeline.md` §E.9 — sanctioned-exception sentence at the live
  persona-spawn description.
- `references/phase2_generation_guide.md` — Phase 2→3 boundary note naming the persona
  pass as the sanctioned exception, with the imperative "do NOT disable Feature H over a
  perceived guardrail conflict."

## Charters + verdicts

- **A — Scope: SHIP.** The exception names ONLY `run_feature_h` / "the Feature H persona
  validation pass"; it does not license general Phase 1–5 delegation, worker spawning,
  or the fabrication-prone patterns. Each edited file reaffirms the general rule holds
  for all other Phase 1–5 work. Both failure modes are explicitly rebutted (bounded
  remediation returning to the session, not a delegated phase; mandatory
  operator-visible, tagged, revertible, opt-out review summary, not a fabricated PASS).
  No scope leak — the carve is anchored to a named binary plus a named artifact.

- **B — Visibility preserved: SHIP.** All five carve-out locations state or sit inside
  prose stating the three visibility mechanisms — mandatory operator-visible
  `quality/persona_review_summary.json`, `agent-validation`-tagged + revertible changes,
  opt-out off-switch. The claims are backed by Design §8b and `persona_apply.py`
  (`write=True` default, `revert()` filters agent-validation records, `enabled=False`
  off-switch, `AGENT_VALIDATION` tag), not merely asserted. The "operator chat carries
  the truth" principle is honored, not bypassed. No mechanism weakened.

- **C — Internal consistency: SHIP.** The EXCEPTION block, guardrail #1 inline note,
  Feature H description, and both boundary-prose locations all agree the persona spawn is
  a sanctioned second exception (sibling to Phase 6). The boundary prose closes the
  disable-on-conflict path at the exact decision point. The one un-annotated forbidder
  (`:94` "Spawn a sub-agent via your Task tool") is the general rule the adjacent
  EXCEPTION blocks qualify — the same structure SKILL.md already uses for Phase 6, and it
  is deliberately pinned by `test_mode_a_self_execution_contract.py`, so it must remain a
  general forbidder. Mutation-bite confirmed the carve is load-bearing; no second missed
  forbidder exists. Non-blocking note: `:94` could take a "(except the two sanctioned
  exceptions below)" clause for parity, but it is not required for consistency.

## Verification
Full suite **2787 / 0 / 13 skipped**, Python 3.14.6. `test_mode_a_self_execution_contract`,
`test_skill_md_size` (19,474 tokens < 32,000), and doc-consistency tests all green — an
exception was **added**, the forbidding rule was not removed, so the pinned contract
tests remain satisfied.

**Terminal verdict: SHIP.** The persona pass is a named, narrowly-scoped, operator-visible
sanctioned exception; SKILL.md and the boundary prose are internally consistent; a
faithful agent now runs Feature H at the Phase 2→3 boundary instead of disabling it.
