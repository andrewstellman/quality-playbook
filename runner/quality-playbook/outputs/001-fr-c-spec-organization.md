# Output for 001-fr-c-spec-organization.md

**Status:** completed

Scope executed: Phase 0 (base gate) + Track 1 Phase 1 (Feature C build) + Phase 2
(regeneration-fixture acceptance + self-Council). **Phase 3 not started**, per the
instruction.

Pre-flight: `git -C "$QPB_REPO" rev-parse --abbrev-ref HEAD` = `1.6.0` ✓.
Python 3.14.6. Nothing pushed; 12 local commits.

---

## Files created / changed

| Path | Lines | Note |
|---|---|---|
| `references/phase2_generation_guide.md` | +118 / -3 | 8-part document architecture (§5.2), tool-contract split (§5.1), sequential-ID rule, intent-form rule, F-1 slot; C-7 stamp templates parameterized |
| `references/requirements_pipeline.md` | +60 / -12 | Phase E made mandatory/unconditional; E.5 ordering + E.6 renumber enforced; new E.7 (tool-contract split); version-stamp section reconciled |
| `references/artifact_contract.md` | +6 / -4 | `RUN_CONTRACT.md` registered; 3 hardcoded `skill_version` literals parameterized |
| `references/recheck_mode.md` | +1 / -1 | hardcoded `skill_version` literal parameterized |
| `references/phase1_exploration_guide.md` | +1 / -1 | hardcoded `skill_version` literal inside an executable heredoc parameterized |
| `plugins/.../phase_prompts/phase2.md` | +12 / -3 | 8 artifact-location REQs redirected to `RUN_CONTRACT.md`; render-contract handoff |
| `plugins/.../scripts/quality_gate.py` | +560 | `check_render_contract` — 6 mechanical checks + §5.2 mandatory parts + F-1 advisory; CommonMark structure model |
| `plugins/.../scripts/validate_phase_artifacts.py` | +70 | conditional `RUN_CONTRACT.md` check at the Phase 2 boundary |
| `bin/tests/test_render_contract_v160.py` | 1,004 | mutation bites per defect class + AUDIT table |
| `bin/tests/test_render_regeneration_fixture_v160.py` | 566 | the acceptance oracle + manifest-unchanged invariant + its own mutation bites |
| `bin/tests/test_version_literal_sweep_v160.py` | 178 | AUDIT sweep for the C-7 defect class |
| `bin/tests/test_render_fence_differential_v160.py` | 322 | differential test vs a reference CommonMark parser (209 generated cases) |
| `bin/tests/test_validate_phase_artifacts.py` | +80 | tests for the conditional `RUN_CONTRACT.md` check |
| `bin/tests/test_phase_prompts_externalized.py` | +8 / -1 | phase2 byte-equality hash pin updated per its own contract |
| `bin/tests/fixtures/render_contract_v160/**` | 3,615 | 18 files: 3 targets × {REQUIREMENTS, RUN_CONTRACT, manifest, .before ×2, renumber_map} |
| `docs/process/QPB_v1.6.0_Instruction_001_Self_Council/**` | 3,396 | tracked Council record (12 files) |

**Not changed, deliberately:** `docs/design/QPB_v1.6.0_Implementation_Plan.md`. See
"Underspecified / contradictory" below — the Plan reserves itself as the
Cowork-editable planning surface, so a contradiction I found there is reported
rather than edited.

## Commits made

All local on `1.6.0`. **Never pushed.** Every unpushed commit from `71b1a81`
onward belongs to this instruction; `39cc939` (the instruction file itself) is the
orchestrator's and predates the session.

Deliberately a range, not a count. The first two versions of this line each gave an
absolute total, and each was falsified by the very commit that recorded it — a
count living inside the record it counts cannot survive its own landing. The table
below covers the substantive work through `9ca1029`; the record-keeping commits
after it are the corrections described here and are visible in `git log`.

| SHA | Subject |
|---|---|
| `71b1a81` | [Phase 1] the REQUIREMENTS.md render contract, specified |
| `d8d4229` | [Phase 1] enforce the render contract in quality_gate.py |
| `edc5cec` | [Phase 2] the regeneration fixture — Feature C acceptance oracle |
| `f9984ae` | [Phase 2] close the self-Council findings (round 1) |
| `a95dcb5` | [Phase 2] close the self-Council findings (round 2) |
| `3ef3a7e` | [Phase 2] close the self-Council findings (round 3) |
| `b863deb` | [Phase 2] close the self-Council findings (round 4) |
| `4255002` | [Phase 2] extend the suppressed-region rule to HTML blocks |
| `94c7e3d` | [Phase 2] close B-6/B-7 and end the loop with a differential test |
| `7296569` | [Phase 2] close B-8 (HTML type 7) and generate the differential cases |
| `aa4b4f6` | [Phase 2] model all seven HTML block types; restore the type-6 bite |
| `8db8af3` | docs: tracked copy of the instruction-001 self-Council record |
| `9ca1029` | runner: this output file |

**One commit message was wrong and is corrected in the next one, not rewritten.**
`a95dcb5` claimed "the bite is re-pointed at a fixture WITH intro prose". It was
not — that commit touched two files and the test file was not one of them. Round 3
caught it by deleting the guard and finding the whole suite still green. History is
not rewritten here, so the correction of record lives in `3ef3a7e`. Flagged because
a verify-before-claim failure *inside the audit record* is worse than the gap it
described.

---

## The C-1…C-7 before/after table

Measured by re-evaluating each defect directly against the documents and manifests,
independently of the gate, so the gate is not its own witness. Full method in
`docs/process/QPB_v1.6.0_Instruction_001_Self_Council/evidence_c1_c7_before_after.md`.

| Defect | chi | express | virtio |
|---|---|---|---|
| **C-1** tool-contract REQs in product spec | 8 → **0** | 8 → **0** | 8 → **0** |
| **C-2** identifier sequence broken | yes → **no** | yes → **no** | yes → **no** |
| **C-3** unjustified singleton sections | 3 → **0** | 6 → **0** | 2 → **0** |
| **C-4** Overview present | ✗ → **✓** | ✗ → **✓** | ✓ → ✓ |
| **C-4** Cross-cutting present | ✗ → **✓** | ✗ → **✓** | ✓ → ✓ |
| **C-5** derivation internals | 2 → **0** | 1 → **0** | 1 → **0** |
| **C-6** titles > 120 chars | 7 → **0** | 1 → **0** | 3 → **0** |
| **C-6** titles with terminal period | 16 → **0** | 8 → **0** | 0 → 0 |
| **C-7** generator stamp | `v1.5.3` → **`v1.6.0`** | `v1.5.8` → `v1.6.0` | `v1.5.8` → `v1.6.0` |
| Gate verdict | 11 FAIL → **0** | 9 FAIL → **0** | 6 FAIL → **0** |
| Manifest record count | 16 → **16** | 16 → **16** | 17 → **17** |

**The oracle is not vacuous:** `test_before_documents_still_exhibit_the_defects`
fails if the preserved pre-v1.6.0 renders ever stop failing the contract.

**C-4 and C-7 are the discriminating cases.** virtio already had an Overview and
cross-cutting concerns; chi and express had neither — same pipeline, same skill
version, same day. chi stamped `v1.5.3` while express and virtio stamped `v1.5.8`.
Those are the "fires unpredictably" defects stated as measurements.

**C-7's root cause, found and fixed at source:** `phase2_generation_guide.md:43`
hardcoded `v1.5.3` in the mandatory stamp template, ten lines above a rule saying
the stamp must match SKILL.md `metadata.version`. chi copied the literal; express
and virtio followed the rule.

---

## The mechanical checks, and a test proving each fires

All in `check_render_contract`, registered in `check_repo()` (pinned by a test —
`quality_gate.py` has no check registry, so an unregistered check is inert).

| # | Check | Bite |
|---|---|---|
| 1 | REQ IDs sequential in document order | `test_c2_fires_on_out_of_order_ids`, `..._on_gap_in_sequence` |
| 2 | No `quality/`-only REQ in REQUIREMENTS.md; all in RUN_CONTRACT.md | `test_c1_fires_*` ×3 |
| 3 | Overview present; section intro prose; singleton merge-or-justify; cross-cutting | `test_c3_fires_*` ×2, `test_c4_fires_*` ×2 |
| 4 | No HTML comments / derivation vocabulary | `test_c5_fires_*` ×2 |
| 5 | REQ titles ≤120 chars, no terminal period | `test_c6_fires_*` ×2 + a 120-char boundary case |
| 6 | Generator stamp == single version source | `test_c7_fires_on_stale_stamp`, `..._on_absent_stamp` |
| F-1 | Coverage-and-gaps statement (**WARN only, never FAIL**) | `test_f1_warns_*`, `F1ScopingTests` |
| MP-1 | Actors / Use cases / Traceability mandatory (§5.2) | `test_mp1_*` ×3 |
| MP-2 | Requirements must live inside functional sections | `test_mp2_*` ×2 |
| MP-3 | Quoted headings are not structure | `test_mp3_*` ×8 |

Each bite re-introduces exactly one defect into an otherwise-conforming document,
paired against a clean-document baseline. `RENDER_CONTRACT_AUDIT` (10 rows) has a
size guard and derives each row's expected test-name prefix, so a check without a
bite fails the sweep.

**Mutation evidence executed, not asserted** — pristine snapshot via `shutil.copy2`,
scoped `__pycache__` purge, byte-comparison restore:

```
delete the `if not functional:` guard      -> 3 tests RED
delete the mandatory-part check tuple      -> 4 tests RED
revert structure detection to raw text     -> 1 test RED
disable fence blanking entirely            -> 7 tests RED
neuter HTML type 6 / types 3-4-5 / type 7  -> differential RED (each independently)
```

One bite initially did **not** fire: its assertion read `assertIn("Actors & roles",
out)`, which also matches `PASS: Actors & roles section present`. Four assertions of
that shape were tightened to FAIL-only phrasing.

---

## Manifest remains the source of truth

- Record counts unchanged (16/16/17); every `references` list byte-identical and
  still attached to its own record.
- The only fields that change are the three the design itself mandates — `id`
  (E.6 renumber), `title` (§5.4 intent-form), `functional_section` (E.5 merge) —
  plus `conditions_of_satisfaction` growing to absorb normative text a title
  rewrite displaced. Enforced field-by-field through a committed
  `renumber_map.json`, not by a set comparison.
- Manifest ids == rendered ids across **both** renderings; each REQ renders under
  the section its record names.
- Five mutations pinned, including two the first invariant survived: gutting every
  record, and rotating `references` onto the wrong records (which preserves the
  multiset a set-based check compares).

**The FP-audit dependency is protected**: it consumes the manifest and never the
render, and a title rewrite can no longer move contract text out of the manifest
(`test_displaced_title_text_survives_in_the_manifest`; 25 records folded).

---

## What changed in the render path vs. the manifest

**Render path only** — there is no Python renderer; REQUIREMENTS.md is written by
the Phase 2 agent following `references/`. So "the renderer" = the reference docs +
phase prompt, and the contract is enforced mechanically at the gate.

**Applied to both producers?** The documented seam (Plan OD-10) is the code-path
Phase A–E pipeline vs. `bin/skill_derivation/`. Feature C's render contract checks
the *rendered document*, so it covers both mechanically. The prompt-level changes
land on the code-path pipeline only; `bin/skill_derivation/curate_requirements.py`
has its own `_render_requirements_md()` which is **dead** (no callers outside its
test, not shipped in the bundle) and carries its own hardcoded `v1.5.3`. Left
alone as out of scope — flagged below.

---

## Self-Council

**Verdict: SHIP**, at round 7. Six FIX-REQUIRED rounds preceded it; every finding
was closed in-branch before this output was filed, per the protocol's requirement
that the internal panel be the load-bearing gate rather than a formality.

**Artifact paths and their gitignore status — the instruction asked explicitly:**

- `runner/quality-playbook/reviews/001_self_council/` — **GITIGNORED**.
  `git check-ignore -v` reports `.gitignore:82: reviews/`. That is a bare pattern
  matching at **any depth**, so the runner's review directory is untracked. This is
  the v1.5.10 evidence-loss trap the instruction warned about, and it is live.
- `docs/process/QPB_v1.6.0_Instruction_001_Self_Council/` — **TRACKED**, verified
  by `git ls-files` (12 files, 3,396 lines) and confirmed byte-identical to the
  runner copies.

Round 1 ran three panelists on orthogonal charters (render-contract correctness
incl. mutation coverage / regeneration-fixture fidelity / regression safety on
manifest semantics), each a separate subagent context, each writing to file before
reporting. Rounds 2–7 were closure audits that re-derived the exploits rather than
reading the diffs.

**What the panel found that a single pass would have shipped:**

- **P0** — virtio's coverage-and-gaps statement said the per-device drivers were
  "outside the checkout entirely". Eight of them are *in* `drivers/virtio/` and
  none is covered by any REQ. The largest in-scope zero-coverage surface was
  described to the operator as out-of-scope — the exact failure F-1 exists to
  prevent, in the direction that manufactures false confidence.
- **P1** — two archived runs flipped GATE PASSED → GATE FAILED. The inertness
  predicate was heading-*shape*, not version, and `### REQ-NNN:` long predates
  v1.6.0 (49 archived trees carry it). Now gated on the run's own recorded skill
  version. Both flips verified restored; 105 archived trees swept, zero flips.
- **P1** — the manifest-unchanged invariant was vacuous on record content.
- **P1** — express and virtio rewrote titles without folding the displaced
  normative sentence into the manifest, so the FP-audit would have seen a weaker
  requirement than a human reader.
- **P1** — the defensive sweep stopped one file short (5 more version literals,
  one inside an executable heredoc, three feeding a blocking check).

---

## Notable observations

**1. The Design's C-2 diagnosis is incomplete, and the real cause is worse.**
The Design says Phase E.6's renumber "demonstrably does not fire". True, but the
cause is that `phase2_generation_guide.md:99` said "ordered by REQ id" while
`requirements_pipeline.md` E.5/E.6 said "reorder user-facing→infrastructure, then
renumber to document order". **An agent following the guide produced C-2 by doing
what it was told.** Resolved in favour of document order; both docs now agree.

**2. The three fixture manifests have three different record schemas** while all
declaring `schema_version: 1.5.8`. chi has `text` and no `title`; express has
`title`/`tier`/`conditions_of_satisfaction`/`specificity`; virtio has
`title`/`tier_label`/`source`/`formal_doc_refs` and no CoS. Any manifest-level
feature (Feature A's `nfr_class`, F-2's `operator-confirmation`) will meet this.
Not in scope here; worth a decision before Track 2.

**3. Section merges orphan `functional_section` on UC records.** virtio carries it
on all 11 UCs, chi and express on none. A merge that updates only REQ records
leaves UCs naming a section that no longer exists. E.5 now says to sweep both.

**4. A five-round loop, and how it ended.** Rounds 3–7 each found a bypass in the
same component, and every fix was correct about exactly the shape it was shown.
Round 5 named the exit condition — *"check the model against an authority"*, not
"enumerate harder" — which produced the differential test against `markdown_it`
(209 generated cases; test-only, optional, and a test asserts `quality_gate.py`
never imports a markdown library). Round 6 then found the same pattern one level up
(the case list was hand-written from the model it audits) and round 7 one level
up again (single-context generation let one construct backstop another). Both
closed. This is the most reusable thing this instruction produced.

**5. A concurrency artifact, not a problem.** Round 5 reported the working tree
going clean → dirty → committed under it. That was this worker committing while the
review ran. No second agent; no interference.

---

## Anything underspecified, contradictory, or wrong in the Design

Asked for plainly, so stated plainly.

1. **The Plan's manifest invariant is contradicted by the Design.** Plan:45 says
   `requirements_manifest.json` is *"unchanged modulo the renumber map"*. Design
   §5.4 (intent-form titles) and §5.2 (section merges) both **mandate** manifest
   field rewrites. Measured: records identical modulo `id` are chi 11/16, virtio
   8/17, **express 0/16**. Three statements of the invariant existed — the Plan, the
   Design, and the test docstring — and none agreed. **Not edited**: the Plan
   reserves itself as the Cowork-editable planning surface. The honest invariant is
   in the test docstring; **the Plan needs a one-line correction.**

2. **"Re-render … through the new renderer" presumes a renderer that does not
   exist.** Nothing in the shipped skill renders REQUIREMENTS.md; it is LLM prose
   following `references/`. The oracle was executed by rendering the three fixtures
   as the Phase 2 agent would, then checking mechanically. **Consequence the
   orchestrator should weigh:** the fixtures are golden files, so a regression in
   the reference-doc prose cannot fail the suite. Whether Feature C should ship a
   deterministic renderer is a real architectural fork the Design leaves open, and
   I did not take it unilaterally.

3. **§5.3 lists six checks; §5.2 lists eight mandatory parts.** Implementing only
   §5.3 leaves Actors & roles, Use cases and the Traceability appendix unchecked —
   which is how a flat document passed for three rounds. §5.3 should say it is not
   the complete check list.

4. **F-1 is specified as "Overview contains a non-empty gaps statement" but §8 also
   calls it advisory.** A gate cannot both require and not require. Implemented as
   WARN-only per §8's explicit "never a gate FAIL", with the non-emptiness enforced
   inside the WARN.

5. **§5.1 says the tool-contract REQs "remain gate-enforced per-run" without saying
   where.** Implemented at both the Phase 2 boundary (conditionally) and the Phase 6
   gate. Deliberately *not* added to `run_state_lib.py`'s unconditional
   `required_fixed`, which would retroactively fail every archived Phase-2 tree.

6. **Dead code carrying the C-7 defect.** `bin/skill_derivation/curate_requirements.py`
   `_render_requirements_md()` hardcodes `"# QPB v1.5.3"`. No callers outside its
   test, not shipped. Left alone as out of scope; worth deleting or fixing.

7. **Design §5.3 check 4 seeds the deny-list with "pass names" but the pre-v1.6.0
   version-stamp template emitted one** (`Pipeline: contract-extraction v2 with
   narrative pass`). The spec asked to reject a string the spec also told the agent
   to write. Removed from the template.

---

## Known residual risk

Recorded rather than hidden. All are model-level or require deliberately quoting
section headings inside a suppressing construct — not shapes an honest renderer
produces.

- **Closing-hash ATX** (`## Actors and roles ##`) is a model-level disagreement in
  the conservative direction; correct at gate level.
- **CRLF** line endings: model-level only, benign at the gate.
- **Blockquoted / list-nested / setext headings** are enumerated in
  `INTENTIONAL_DIVERGENCES` with justification, guarded by a test asserting no
  divergence may ever be permissive and another that fails when a row goes stale.

---

## Next action expected from orchestrator

1. Correct the Plan's manifest-unchanged invariant (§ observation 1) — worker
   declined to edit the planning surface.
2. Decide the renderer fork (§ observation 2) before Phase 3: Feature D consumes
   this render, and the fixtures are golden files until a renderer exists.
3. Decide the manifest-schema divergence (§ observation 2 in Notable) before
   Track 2 lands `nfr_class`.
4. Review the regenerated fixtures as *prose*. The Design's oracle has a judgment
   half — "a focused Council on the three rendered documents returns Ship on
   readability" — which is an operator/Council call, not a worker one. The
   mechanical half is satisfied.
