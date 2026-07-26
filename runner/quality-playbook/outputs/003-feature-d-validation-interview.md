# Output for 003-feature-d-validation-interview.md
**Status:** completed

## Files created / changed
| Path | Lines | Note |
|------|-------|------|
| `references/requirements_interview.md` | +NEW | The Feature D protocol: three stages mapped to the Wiegers dimensions, five moves (confirm/correct/add/drop/defer), three entry modes, manifest write-back, F-2a durability discipline (snapshot-before-rederive + read-path-at-finalization). Supersedes the review+refine walkthrough. |
| `references/requirements_review.md` | −DELETED | Superseded generator of the old review walkthrough. |
| `references/requirements_refinement.md` | −DELETED | Superseded generator of the old refine walkthrough. |
| `schemas.md` | ± | §3.7 `operator-confirmation` source_type row (transcript-as-citable-source; skill_section absent); §9.5 `operator_confirmations.jsonl` record shape; §9.5.2 append-only invariant (byte-prefix + the two-mechanism enforcement). |
| `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` | ± | `operator-confirmation` added to `_V153_VALID_SOURCE_TYPES`; `_operator_confirmed_req_ids`, `_opconf_is_append_only`, `check_operator_confirmations_append_only` (with manifest-consistency enforcement), `check_requirements_review` (word-boundary Wiegers matching). |
| `plugins/quality-playbook/skills/quality-playbook/scripts/run_state_lib.py` | ± | `append_confirmation` (append-only, shape+move+newline validated), `read_confirmations`, `confirmations_append_only`. |
| `plugins/quality-playbook/skills/quality-playbook/scripts/qpb_validate.py` | ± | INSTALL_CLOSURE: −requirements_review.md −requirements_refinement.md +requirements_interview.md (net −1 = 62). |
| `references/phase7_guide.md` | ± | Improvement menu collapsed to 4 items (interview is #1); Path 1 rewritten with snapshot+read-path durability discipline. |
| `references/requirements_pipeline.md` | ± | FU-B no-disjunction rule added in B.3; "After the pipeline" rewritten for the interview; artifact table + supersession note. |
| `references/phase1_exploration_guide.md`, `SKILL.md` | ± | Phase 7 "offers the interview" (SKILL.md token ceiling verified holds). Per adjudication, phase1 does NOT get the no-disjunction rule. |
| `references/artifact_contract.md` | ± | REQUIREMENTS_REVIEW.md, operator_confirmations.jsonl, transcript rows (interview-conditional). |
| `bin/tests/test_feature_d_supersession_v160.py` | +NEW | Sweep: no generator, no orphaned gate check, templates deleted, interview exists. |
| `bin/tests/test_feature_d_interview_fixture_v160.py` | +NEW | Scripted session (confirm/correct/add/merge); `_apply_move`; `_render_requirements_md` (E.6 renumber); correction-must-reach-manifest mutation; F2a durability oracle (delete-hole + empty-hole); run_state_lib helper coverage; gate FAIL-path coverage; five-moves drift guard; the 2026-05-02 worked example. |
| `bin/tests/test_quality_gate_gates.py` | ± | `TestV160OperatorConfirmationSourceType` with bidirectional schema/enum drift guard. |
| `bin/tests/test_install_manifest_no_drift.py` | ± | Pinned closure count 63 → 62. |
| `bin/tests/test_render_contract_v160.py` | ± | No-fail-path test end-anchor moved past the two new conditional checks. |

## Commits made
- Pre-Council build chain on `1.6.0`: `ca483e2` (FU-B no-disjunction rule), `5f1b3d6` (schema + interview protocol), `dd03e77` (F-2a durability, gate wiring, supersession), `bcc5585` (acceptance fixture + worked example).
- `d562f73` — v1.6.0 [instr 003]: close the self-Council findings (P1 + P2s).
- `faa3288` — v1.6.0 [instr 003]: unanimous-SHIP closure — residual gate-type-check test + tracked self-Council artifacts + synthesis.
- `<this commit>` — runner: output for instruction 003 (this file + STATUS.md).

## Acceptance criteria — pass/fail per item
| Plan Phase 4 criterion | Result |
|------------------------|--------|
| Fixture session (confirm/correct/add/merge) → correctly-shaped manifest records | **PASS** — `test_feature_d_interview_fixture_v160.py`, scripted test-double operator. |
| Re-render passes the Feature C render contract | **PASS** — fixture renders through E.6 renumber and asserts against the real `check_render_contract`. |
| Defect log + transcript artifacts present and gate-validated | **PASS** — `check_requirements_review` + artifact_contract rows. |
| Mutation: a correction that never reaches the manifest fails | **PASS** — `CorrectionMustReachManifestMutationTests` drives a real session through a mutated write-back that skips the manifest write; acceptance property fails. |
| F-2a: confirm-then-re-derive leaves `.jsonl` intact + prior confirmation reported | **PASS** — `F2aDurabilityOracleTests` + `test_rederive_reports_prior_confirmations`. |
| F-2a: a truncating path fails | **PASS** — truncate/delete-hole/empty-hole all FAIL the gate (mutation-bitten). |
| Sweep: no remaining generator of the superseded walkthrough files | **PASS** — see Supersession sweep below; enforced by `test_feature_d_supersession_v160.py`. |
| Re-run the 2026-05-02 worked example as a semi-scripted walkthrough | **PASS** — `WorkedExample20260502Tests`: stage-appropriate questions + durable corrections. |
| Full suite result + counts + Python version | **2586 tests, 0 failures (14 skipped)**, Python 3.14.6. |

## Council (if required)
**Verdict: unanimous SHIP** (Round 2 closure). Self-Council per Design §13 item 3, four
charters, each panelist in its own git worktree (the runner hazard reported in 002: two
reviewers sharing one tree produced phantom failures under a mutation bite).

| Panelist | Charter | Round 1 | Round 2 |
|----------|---------|---------|---------|
| A | manifest write-back correctness | FIX-REQUIRED (1 P1, 3 P2) | **SHIP** |
| B | interview-artifact gate compliance | SHIP (4 P2) | **SHIP** |
| C | supersession completeness | SHIP | *stands (surface untouched)* |
| D | F-2a durability (+ mutation proof) | FIX-REQUIRED (1 P1, 3 P2) | **SHIP** |

**The P1, found independently by A and D:** the F-2a append-only durability guarantee —
the slice's headline promise — was *inert in every real run*. The gate enforced
append-only only against `operator_confirmations.prior.jsonl`, a snapshot nothing in
production creates, so a re-derivation that deleted or emptied the log PASSED as "no
interview has run," silently destroying the operator's corrections. Two panelists
reached it from different charters — the signal the isolated-charter design exists to
produce. Fixed with **manifest-consistency enforcement** (op-conf REQs in the manifest ⟹
log must exist and be non-empty; no snapshot needed), the prefix-vs-snapshot check
retained as a second mechanism, and the protocol + phase7 guide now instructing the
snapshot-before-rederive and read-and-surface-at-finalization steps. Mutation-bitten from
both charters.

All P2s closed (tautological mutation test → real broken-write-back session; one-way
drift guard → bidirectional; substring Wiegers → word-boundary; no FAIL-path coverage →
5-test class; permissive shape-check → non-empty-string type-check; dead run_state_lib
copy → direct test + drift guard; §9.5.2 line-count → byte-prefix). B's one non-blocking
residual (gate type-check had no committed test) closed in Round 2 by
`test_gate_rejects_a_malformed_record_directly`, mutation-bitten.

**Artifacts:** `RUNNER_ROOT/reviews/003_self_council/` (gitignored) and the tracked
mirror `docs/process/QPB_v1.6.0_Instruction_003_Self_Council/` — round-1 panelist files,
`round2_closure.md`, `synthesis.md`.

## Notable observations

### How the interview's elicitation maps onto the Wiegers rubric
The interview inherits the rubric vocabulary rather than inventing a second one (per the instruction's read-first). The three stages are the operator-facing form of the same dimensions:

| Interview stage | Move it invites | Rubric dimension(s) |
|-----------------|-----------------|---------------------|
| **Stage 1 — narrative playback** ("here's the system I understood") | *add* (name missed behavior), *defer* | **Complete** + **Honest-about-gaps** — surfaces what the derivation never captured. |
| **Stage 2 — sections & use cases** ("does this section hang together") | *correct*, *drop* | **Consistent** + **Correct** — catches cross-section contradiction and wrong intent. |
| **Per-REQ drill-down** (on demand) | *correct*, *confirm* | **Unambiguous** + **Verifiable** — tightens a single requirement's wording and its conditions of satisfaction. |

The rubric's sixth dimension, **Well-organized**, is *not* elicited by any interview stage — it is a structural property the Feature C render contract already enforces mechanically, so the interview correctly leaves it out. (The design/instruction doesn't say this explicitly; see Design defects #2.)

### What F-2a's artifact looks like in practice
`quality/operator_confirmations.jsonl`, one JSON object per line, append-only. A real record from the fixture's `correct` move (verbatim shape the sanctioned writer `run_state_lib.append_confirmation` emits):

```json
{"ts":"2026-07-21T15:05:00Z","move":"correct","req_title":"Manifest schema is enforced at phase-2 validation","conditions_of_satisfaction":"A manifest using 'requirements' rather than 'records' is rejected. The gate distinguishes substantive from record-keeping failures.","operator_statement":"The gate has to reject the wrong top-level key — that's the whole point of the schema check.","transcript_citation":"quality/review_sessions/2026-07-21T15-05.md:42","session_id":"sess-20260721-1505"}
```

- Keyed on **content** (`req_title` + `conditions_of_satisfaction`), never on REQ id — E.6 renumbers every run, so an id is meaningless across runs (Design §8 F-2a).
- `operator_statement` is the operator's words **verbatim** — that is what the read-path quotes back next run.
- `transcript_citation` is conditional: present only if the operator agreed to save the session transcript (F-2's transcript-as-citable-source). Absent otherwise; the gate treats it as optional.

### The supersession sweep result
**Clean.**
- The two superseded reference docs (`references/requirements_review.md`, `references/requirements_refinement.md`) are **deleted** from the tree.
- **No generator** anywhere in `plugins/`, `references/`, or `SKILL.md` emits `REVIEW_REQUIREMENTS.md` / `REFINE_REQUIREMENTS.md` / `REFINEMENT_HINTS.md`.
- The only surviving mentions of those names are **supersession/release-note context** (3 files: `requirements_interview.md:6,255`; `requirements_pipeline.md:466-467` "*Superseded (v1.6.0)*"; `phase1_exploration_guide.md:510`) — no dual-generation path, no shim, exactly the operator's 2026-07-20 decision.
- Enforced going forward by `test_feature_d_supersession_v160.py` (no generator, no orphaned gate check, templates deleted, interview exists) and the INSTALL_CLOSURE closure test.

### Design defects — underspecified / contradictory / wrong in §6, §8 F-2/F-2a, Plan Phases 3–4

1. **§8 F-2a mandates the guarantee but not the enforcement mechanism — and the natural implementation is inert.** F-2a says "a run that would delete or truncate it fails the gate," but says nothing about *how* a gate detects a delete across runs. The obvious reading — an append-only check against a prior snapshot — cannot fire, because the design never says who writes that snapshot, and nothing in production does. Both FIX-REQUIRED panelists (A, D) found this independently as the P1: the headline durability promise was enforced only against a snapshot that no real run creates. The design's own text points at the fix it omits to name: because "each record carries the REQ's content" and "a later run reads the file," the **manifest is the cross-reference** — if the manifest still carries operator-confirmation REQs while the log is gone or empty, that is provable data loss with no snapshot required. I made that the primary enforcement (manifest-consistency FAIL) and kept the prefix-vs-snapshot check as the second mechanism for cross-run truncation. **Recommend the design name manifest-consistency as the enforcement anchor, not just the outcome.**

2. **The read-path is specified as intent but not decomposed into a task.** §8 F-2a's "Read path: where a later run finalizes the manifest, it reads the file and reports…" is a real obligation, but Plan Phases 3–4 give it no home — there is no production Python surface (Decision Record #7), so "a later run reads the file and reports" has to live in the *protocol the agent follows*. I wired it into `requirements_interview.md` and `phase7_guide.md` Path 1 (snapshot-before-rederive + read-and-surface-at-finalization). Worth the Plan stating that the read-path is a protocol instruction, not code, so it isn't mistaken for an unbuilt feature.

3. **The rubric's "Well-organized" dimension is unmapped, with no note that this is deliberate.** Instruction §6 / the rubric map five of the six Wiegers dimensions to interview stages and silently drop Well-organized. It is correctly out of scope (the render contract owns structural organization), but a reader reconciling the interview against the rubric will read the gap as an omission. One sentence in §6 would close it.

None of these is blocking; #1 was the substance of the Council's P1 and is fixed. Reporting them plainly per the instruction's ask.

## Next action expected from orchestrator
Land the instruction-003 commits on `1.6.0` (worker never pushes/merges). Track 2 (broad-repo validation across `repos/docs_gathered/`) is the orchestrator's, to run after this lands.
