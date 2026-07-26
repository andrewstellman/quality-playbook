# Output for 006-organizing-principle-selection.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` | Item 2: `_render_organizing_principle_stated` + principle/rationale regexes; MP-4 check (principle named + rationale → FAIL); section-check messages reframed "functional section"→"requirement section", "intro prose"→"section overview". |
| `references/requirements_pipeline.md` | Item 1: § E.5 rewritten into the six-step "Choose the organizing principle" selection pass, ahead of E.6. |
| `references/phase2_generation_guide.md` | Item 1: architecture part 4 renamed "Requirement sections (organized by the chosen principle)" with the IEEE 830 menu + stated-principle + section-overview requirements. Item 4: glossary moved part 4 → part 9 to match the design. |
| `references/requirements_interview.md` | Item 3: Stage 1 plays back the organizing principle (a change = `correct` → re-group+re-render); Stage 2 reads each section overview, principle-agnostic order. |
| `bin/tests/test_render_contract_v160.py` | `OrganizingPrincipleTests` (MP-4 mutation bites + `_use_case_organized_md` non-functional regression); AUDIT row MP-4 (size 10→11); reframed assertions. |
| `bin/tests/test_render_regeneration_fixture_v160.py` | Golden-fixture reconcile: `EXPECTED_FIXTURE_FAILS` allowlist + fail-line parser + staleness guard; oracle allows only the recorded principle gap. |
| `bin/tests/test_feature_d_interview_fixture_v160.py` | The interview re-render fixture (instr 003) gains a stated principle so it still passes the contract. |
| `docs/process/QPB_v1.6.0_Regeneration_Expectations.md` | Recorded the organizing-principle gap on the three golden fixtures + the row-4b/oracle design finding. |
| `plugins/quality-playbook/skills/quality-playbook/phase_prompts/phase2.md` | Council fix (B): render-contract summary in the routing prompt made principle-agnostic (dropped "functional sections ordered user-facing→infrastructure", added glossary). |
| `bin/tests/test_phase_prompts_externalized.py` | phase2 prompt hash recomputed (12810→13004) for the phase2.md reframe. |

## Commits made
- `1728ef3` — v1.6.0 [instr 006]: the derivation chooses the requirements' organizing principle (implementation).
- `2fb7857` — v1.6.0 [instr 006]: close self-Council findings (leftover ordering wording L167/L173 + principle-detector regex widen).
- `edce797` — v1.6.0 [instr 006]: close the third ordering-wording leftover (phase2 routing prompt) + phase2 hash.
- `2f2a78f` — v1.6.0 [instr 006]: tracked self-Council artifacts + synthesis.
- `<this commit>` — runner: output for instruction 006.

## Acceptance criteria — pass/fail per item
| Criterion | Result |
|-----------|--------|
| Non-functional-grouping fixture accepted by the contract | **PASS** — `_use_case_organized_md` (a use-case/journey-organized document) passes every render-contract check; `test_non_functional_grouping_is_accepted`. |
| Mutation: no principle → FAIL | **PASS** — `test_mp4_fires_when_no_principle_is_stated`; mutation-bitten (neutering the FAIL turns 10 tests RED, restored). |
| Mutation: principle named without rationale → FAIL | **PASS** — `test_mp4_fires_when_principle_named_without_rationale`. |
| Mutation: no section overview → FAIL (any principle) | **PASS** — `test_section_overview_missing_still_fails_for_non_functional`. |
| Contract does NOT judge principle optimality (row 4c) | **PASS** — MP-4 is presence-only; no check inspects WHICH principle. |
| Full suite + counts + Python version | **PASS** — `python3 -m unittest discover bin/tests` → **2600 tests, 0 failures, 14 skipped** (2599 at the build; +1 the Council regex-widen guard), Python 3.14.6. |

## Council (if required)
**Verdict: unanimous SHIP** (after two fix rounds). Three charters per the instruction, each
panelist worktree-isolated.

| Panelist | Charter | Round 1 | Closure |
|----------|---------|---------|---------|
| A | principle-agnostic render contract (+ mutation bites, non-functional fixture) | SHIP (1 P2) | P2 closed |
| B | selection pass across pipeline + generation guide (routing) | FIX-REQUIRED (P1) | FIX-REQUIRED again, then **SHIP** |
| C | interview integration + glossary reconcile | SHIP (1 P2 = B's) | closed with B's P1 |

- **A** confirmed MP-4 with live mutation bites (neutering "no principle" → 10 tests RED),
  proved the use-case-organized document genuinely passes, and independently verified the
  golden-fixture oracle reconcile still catches a real C-2 regression (it injected one).
- **B** drove the routing-consistency finding across two rounds: the mechanical gate can't
  check literal section-ordering prose, so three docs still commanded the old
  "user-facing → infrastructure" ordering, contradicting the new principle-agnostic item 4 —
  `phase2_generation_guide.md:167`/`:173` (round 1) and `phase_prompts/phase2.md:50` (closure;
  the Phase 2 prompt the agent reads first, missed because my sweep grepped the *spaced*
  arrow while it used the *unspaced* one). All three reframed; B's final exhaustive sweep
  confirms only deliberate "generalization of the old rule" references remain.
- **C** confirmed Stage 1/2 interview additions, the glossary reconcile (guide now matches
  the design order-for-order, no leftover "meets vocabulary first" contradiction), and that
  `docs/design/` was correctly left untouched.

Artifacts: `RUNNER_ROOT/reviews/006_self_council/` (gitignored) and the tracked mirror
`docs/process/QPB_v1.6.0_Instruction_006_Self_Council/` — `round1_verdicts.md`,
`round2_closure.md`, `synthesis.md`.

## Notable observations

### The non-functional-grouping fixture (the headline regression)
`_use_case_organized_md()` renders REQ-001..005 under two **user-journey** sections
("Mounting a sub-router", "Handling a failing request"), states *"organized by user
journey because testproj is a workflow-shaped library…"*, and passes every render-contract
check — proving the contract accepts a correctly-organized **non-functional** grouping.
The mutation `test_section_overview_missing_still_fails_for_non_functional` proves the
section-overview requirement still bites regardless of principle.

### The mutation results
- **no principle stated → FAIL** ("no organizing principle stated…"); neutering the
  `if not named:` FAIL turns 10 tests RED (the mp4 tests + the golden-fixture oracle's
  expected-fail guards), restored via `shutil.copy2`.
- **principle named, no rationale → FAIL** ("…named but carries no rationale").
- **section overview missing → FAIL** (generalized intro-prose check).
- **use-case-organized document → PASS** (0 fails).

### Glossary placement — which I standardized on, and why
**I standardized on the design's placement — glossary as the final part (part 9, end).** I
matched `phase2_generation_guide.md` (which listed it part 4, after Actors) **to** the
design, **not** vice-versa. The instruction recommended the *reverse* (keep the guide's
after-Actors placement, fix the design). I reversed that recommendation for a concrete
safety reason: `docs/design/QPB_v1.6.0_Design.md` is orchestrator-owned and **currently
has uncommitted edits** in the working tree; editing it to move the glossary would risk
clobbering the orchestrator's in-flight work (the standing "leave docs/design alone"
constraint). Matching the guide to the design makes the two literally agree while touching
only a file I own. If the orchestrator prefers the after-Actors placement (the better
pedagogical order — reader meets vocabulary before the requirements), they can move the
design's part 9 to part 4 and the guide will need to follow. Recorded here so the choice
of direction is explicit.

### Anything in §5.2 / §6 found underspecified or wrong

1. **Row 4b (mandatory FAIL) conflicts with the §5 / §10-criterion-1 acceptance oracle
   until the golden fixtures are regenerated.** The design makes "organizing principle
   named" a *mandatory FAIL*, but the acceptance oracle (`test_render_regeneration_fixture_v160`)
   asserts the chi/express/virtio golden fixtures *pass* the contract with zero fails.
   Those two cannot both hold: the fixtures are pre-006 pipeline snapshots that state no
   principle, so a new mandatory check necessarily makes them fail, and they must not be
   hand-edited. I reconciled it the same way instruction 002 handled the glossary — but
   because row 4b is a FAIL (not a WARN), with a per-fixture `EXPECTED_FIXTURE_FAILS`
   allowlist that admits **only** "no organizing principle stated" while any *other*
   render-contract FAIL still fails the oracle, plus a staleness guard that drops the
   allowance once a fixture is regenerated with a principle. **Recommend the design state
   explicitly that row-4b compliance is expected only of post-006 renders (or schedule the
   fixture regeneration), so the "golden fixtures pass" oracle and the mandatory FAIL stop
   contradicting each other.** Recorded in `QPB_v1.6.0_Regeneration_Expectations.md`.

2. **The design's "section overview" and the pre-existing "intro prose" check are the same
   mechanism, but §5.2/§5.3 never say so.** Row 4b lists "per-section unifying overview" as
   a *new* mandatory check; the render contract already had an intro-prose check (§5.3
   check 3). They are one check — the instruction correctly says the overview "generalizes
   the existing intro-prose check." The design would read more clearly if the matrix noted
   that row 4b's overview clause **is** the existing §5.3-check-3 intro-prose mechanism,
   re-scoped, rather than implying a second, independent check.

3. **§5.2 item 4 keeps the label `functional_section` as the manifest field** even though
   sections are no longer necessarily functional. Not worth a migration (it is a stable
   manifest key with cross-references), but the field name now slightly misdescribes its
   contents under a non-functional grouping. A one-line note in the schema that
   `functional_section` holds the section name **under whatever organizing principle was
   chosen** would prevent a future reader from assuming functional grouping.

## Next action expected from orchestrator
Land the instruction-006 commits on `1.6.0` (worker never pushes/merges). Consider: (a) the
row-4b/acceptance-oracle conflict — regenerate the golden fixtures through the selection
pass, or scope row-4b to post-006 renders; (b) the glossary placement direction (I chose
the design's part-9; the orchestrator may prefer part-4 and can move the design). Track 2 /
NFR work remains out of scope.
