# Instruction 003 — v1.6.0 Track 1 (Phases 3–4): Feature D, the requirements validation interview

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§6** (Feature D — the three-stage protocol, the five moves, elicitation sourcing, supersession), **§8 F-2** *and* **§8 F-2a** (cross-run durability — added 2026-07-20; it changes where the interview writes, so read it before designing the write-back).
- `docs/design/QPB_v1.6.0_Implementation_Plan.md` **Phase 3** and **Phase 4**. The operating principle stands: *the design doc is the spec, no per-phase briefs.* **Decompose the work yourself.**
- `docs/design/QPB_v1.6.0_Requirements_Readability_Rubric.md` — the Wiegers dimensions. Feature D's interview is the operator-facing form of the same questions; **inherit this vocabulary rather than inventing a second one.** Stage 1 maps to *Complete* + *honest-about-gaps*; Stage 2 to *Consistent* + *Correct*; per-REQ drill-down to *Unambiguous* + *Verifiable*.
- `ai_context/DEVELOPMENT_PROCESS.md` — process, Council protocol, verify-before-claim, commit hygiene.

## Scope of THIS instruction
**Phase 3 (Feature D + F-2 + F-2a) + Phase 4 (acceptance + self-Council). Stop there and file your output. Do NOT start Track 2.**

Broad-repo validation across the non-fixture repos in `repos/docs_gathered/` is **the orchestrator's**, run after this lands — do not attempt it.

## Carried-forward item (FU-B, from instruction 002)
`references/requirements_pipeline.md` authors requirement text (*"State the requirement as a testable assertion"*) and does **not** carry instruction 002's no-disjunction rule. Add it, in the same form as the three surfaces 002 landed. **`references/phase1_exploration_guide.md` does NOT get the rule** — Phase 1 produces exploration output, not requirements; adjudicated 2026-07-20, don't re-open it.

## Design notes that are decided — do not re-litigate
- **Supersession, no deprecation shim.** The interview replaces `REVIEW_REQUIREMENTS.md` / `REFINE_REQUIREMENTS.md` generation. v1.5.8 was hand-published to PyPI/npm, so adopters may have the old files — the operator's decision (2026-07-20) is that the old artifacts are fine as they are and need no compatibility path. **Be accurate going forward:** a release-note line stating the change, no shim, no dual generation.
- **Delivery shape is settled** (Decision Record #7): skill-protocol chat — a protocol reference the agent follows in a normal session. **No new interactive Python surface.** Entry modes (guided / self-guided / cross-model) carry over from the shipped walkthrough.
- **MVP boundary is explicit** in §6's "Deferred from the proposal." Interview Dimensions 2/5/8 and QI-loop closure are out. Scope creep toward the full eight-dimension proposal is the named risk in the Plan — hold the line.

## Branch / commit policy
Work on **`1.6.0`**. Pre-flight: confirm `git -C "$QPB_REPO" rev-parse --abbrev-ref HEAD` is `1.6.0`; if not, write a `pre-flight-aborted` output and stop. Focused local commits. **Never push, never merge** — the operator lands.

## CRITICAL — the fixture constraint from 002 still holds
Do **not** hand-edit `bin/tests/fixtures/render_contract_v160/*/quality/REQUIREMENTS.md`. They are snapshots of pipeline output. The five disjunctive clauses recorded in `docs/process/QPB_v1.6.0_Regeneration_Expectations.md` are expectations for a future regenerated run — **not** edits to make.

## Council
Self-Council per Design §13 item 3: three panelists on **manifest write-back correctness**, **interview-artifact gate compliance**, and **supersession completeness** (no orphaned generation path left behind). Add a fourth charter for **F-2a durability** — verify the append-only artifact genuinely cannot be truncated or overwritten by a re-derivation, with a mutation proving it. Iterate to unanimous SHIP in-branch before filing.

Artifacts under `RUNNER_ROOT/reviews/003_self_council/` **and** a tracked copy under `docs/process/QPB_v1.6.0_Instruction_003_Self_Council/` — `reviews/` is gitignored by a bare pattern matching at any depth.

**Runner hazard you reported in 002:** two reviewers sharing one working tree produced phantom suite failures when one ran mutation bites. Give each panelist its own git worktree, or serialize any panelist that mutates.

## Acceptance
Per Plan Phase 4:
- **Fixture session** against the QPB self-derivation with a scripted test-double operator issuing one confirm, one correct, one add, one merge. Manifest updated with correctly-shaped records; re-render passes the Feature C render contract; defect log and transcript artifacts present and gate-validated.
- **Mutation:** a correction that never reaches the manifest must fail the fixture.
- **F-2a:** confirm-then-re-derive leaves the `.jsonl` intact and the prior confirmation reported; a truncating path fails.
- **Sweep test:** no remaining generator of the superseded walkthrough files.
- **Re-run the 2026-05-02 worked example** (`Reviews/QPB_v1.6.x_Requirements_Review_Worked_Example_2026-05-02.md`) as a semi-scripted walkthrough — it must produce stage-appropriate questions and durable corrections.
- Full suite result + counts + your Python version.

## Output
`outputs/003-feature-d-validation-interview.md` per the README schema, plus:
- how the interview's elicitation content maps onto the rubric's dimensions;
- what F-2a's artifact looks like in practice (a real record, redacted if needed);
- the supersession sweep result;
- **anything in §6, §8 F-2/F-2a, or Plan Phases 3–4 you found underspecified, contradictory, or wrong.** Instruction 001's most useful output was its list of Design defects; 002's was catching an acceptance criterion I wrote at the wrong granularity. Say it plainly.
