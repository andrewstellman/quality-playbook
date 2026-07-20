# Output for 002-render-contract-hardening.md

**Status:** completed

All five items landed. Self-Council: item-3 charter **SHIP**, focused panel
**FIX-REQUIRED** (2 blocking, both closed), round-2 closure **SHIP**.

Pre-flight: `git -C "$QPB_REPO" rev-parse --abbrev-ref HEAD` = `1.6.0` ✓.
Python **3.14.6**. Suite **2551 / 0 failures / 14 skipped** (2543 before).

**The standing constraint held.** No fixture `REQUIREMENTS.md` was edited by any
instruction-002 commit — verified by `git diff f1b228d~1..HEAD` over that path
(zero files), and independently by both panelists. Nothing in the five items
required it.

---

## Files created / changed

| Path | Note |
|---|---|
| `references/phase2_generation_guide.md` | item 1 rule; item 3 glossary slot + architecture renumber |
| `bin/skill_derivation/prompts/pass_a_section.md` | item 1 rule (REQ-authoring prompt) |
| `bin/skill_derivation/prompts/pass_a_uc_section.md` | item 1 rule (Council B-1 — the missed third surface) |
| `bin/skill_derivation/curate_requirements.py` | item 2 renderer deleted; docstring corrected (Council B-2) |
| `bin/tests/test_curate_requirements.py` | item 2 render assertions + orphaned fixtures removed |
| `plugins/.../scripts/quality_gate.py` | item 3 glossary check + helper; `terms` regex fix; asymmetry priced |
| `bin/tests/test_render_contract_v160.py` | `GlossarySlotTests`; clean fixture gains a glossary |
| `bin/tests/test_render_regeneration_fixture_v160.py` | known-WARN allowlist + staleness guard + F-1 assertion |
| `runner/.../outputs/001-fr-c-spec-organization.md` | item 4 corrections |
| `docs/process/QPB_v1.6.0_Instruction_001_Self_Council/evidence_c1_c7_before_after.md` | item 4 corrections + provenance |
| `docs/process/QPB_v1.6.0_Regeneration_Expectations.md` | item 5 (new) |
| `docs/process/QPB_v1.6.0_Instruction_002_Self_Council/**` | tracked Council record (4 files) |

## Commits

Local on `1.6.0`, **never pushed**. Every commit from `f1b228d` onward is this
instruction's. (Stated as a range, per the lesson from 001: a count inside the
record it counts is falsified by its own landing.)

| SHA | Subject |
|---|---|
| `f1b228d` | item 2 — delete the dead renderer carrying the C-7 defect |
| `f8b73dc` | item 1 — no disjunctive acceptance clauses |
| `0e75fd2` | item 3 — glossary slot in the architecture, WARN only |
| `a59e5c6` | item 4 — regenerate the stale before-state figures |
| `1d3cbc8` | item 5 — record the regeneration expectations |
| `64b48c8` | item 5 — ground the expected forms in verified source |
| `0f7cc0a` | close the self-Council findings |
| `57bbb77` | price the structural-heading list; land the Council record |

---

## Item 1 — which producers were touched

**Three surfaces, not two.** The instruction said "apply to both producers per
the OD-10 seam"; both were addressed, and the focused panel still found a gap —
because the skill-derivation producer has **two** Pass A prompts:

| Surface | Producer | Authors |
|---|---|---|
| `references/phase2_generation_guide.md` | code-path pipeline | REQ text |
| `bin/skill_derivation/prompts/pass_a_section.md` | four-pass derivation | `acceptance_criteria` |
| `bin/skill_derivation/prompts/pass_a_uc_section.md` | four-pass derivation | `acceptance_criteria` **and** UC `acceptance` |

The third was missed in `f8b73dc` and added in `0f7cc0a`. It is not a
technicality: **express UC-06.b — one of the five live instances the
instruction names — is a use-case acceptance clause.** A rule landed only on the
REQ prompt would not have prevented the very defect it was written for. Round 2
searched for a fourth surface and found none; there is exactly one `prompts/`
directory with two files, both now carrying the rule.

**No mechanical gate check was added**, per the instruction. `quality_gate.py`
is touched only by item 3's and item 3's follow-up commits — the verifiable form
of that claim, and the panel checked it by diff.

---

## Item 4 — the before/after gate counts I measured

| Target | reported | **measured** |
|---|---|---|
| chi | 11 FAIL, 1 WARN | **13 FAIL, 2 WARN** |
| express | 9 FAIL, 1 WARN | **12 FAIL, 2 WARN** |
| virtio | 6 FAIL, 1 WARN | **9 FAIL, 2 WARN** |

After-fixtures: **0 FAIL, 1 WARN** each (the WARN is item 3's glossary).

**Error direction safe** — actual detection is stronger than was reported. No
defect went unreported.

**Delta composition — and the instruction's account is wrong.** The instruction
says the delta is "the MP-1 checks plus a chi intro-prose FAIL". Measured:

```
chi      11  +2 MP-1              = 13
express   9  +2 MP-1  +1 stamp    = 12
virtio    6  +2 MP-1  +1 stamp    =  9
```

chi's delta is **exactly +2 MP-1**; its intro-prose FAIL was already inside the
original 11. The third component belongs to express and virtio and is a
*measurement-basis* effect: round 1 evaluated the `.before` documents at
`skill_version=1.5.8`, where their stamps matched and passed; the harness now
holds `1.6.0`, so they mismatch and fail. chi is unaffected because `v1.5.3`
mismatched either way — which is C-7 itself. The focused panel reconstructed
this commit-by-commit through worktrees (`edc5cec` 11/9/6 → `f9984ae` 11/10/7 →
`a95dcb5` 13/12/9) and confirmed it.

**Sequencing.** I did item 4 **last**, because item 3's glossary check moves the
WARN column (1→2 before, 0→1 after). Correcting the figures first would have
produced numbers that went stale inside the same instruction — the exact failure
being corrected. The panel confirmed the reasoning.

---

## Item 3 — the acceptance bar, met

All three fixtures **FAIL=0, WARN=1**, the WARN being the glossary. Zero new
FAILs against the `aa4b4f6` baseline.

WARN-never-FAIL is enforced three ways, not assumed:
behavioral tests (absent / near-empty / present / alternate headings); a
structural guard asserting the check's source block contains `warn(` and no
`fail(`; and a mutation bite — escalating to `fail(` turns **8 tests red**,
including all three fixtures, which is the signal the instruction says means
"implemented wrong".

The dedicated panelist built **15 adversarial documents** trying to force a
FAIL — fenced glossaries, HTML-block glossaries, REQ-bearing glossaries,
glossary-only documents, repositioned glossaries — and got FAIL=0 on all 15.

---

## Self-Council

Verdicts: item-3 **SHIP** · focused panel **FIX-REQUIRED** → closed → round-2
**SHIP**.

**Artifact paths and gitignore status** (the instruction asked; 001 established
the trap):

- `runner/quality-playbook/reviews/002_self_council/` — **GITIGNORED**
  (`.gitignore:82`, bare `reviews/` matching at any depth).
- `docs/process/QPB_v1.6.0_Instruction_002_Self_Council/` — **tracked**, 4
  files, verified identical to the runner copies.

### What the Council caught

- **B-1** — the missed UC prompt (above).
- **B-2** — `curate_requirements.py`'s docstring still described the renderer
  `f1b228d` had just deleted, in the module preserved specifically for a future
  B-4 reader. A commit whose subject is removing dead code left a dead
  description behind.
- **Non-blocking, closed** — bare `terms` in the structural-heading regex let a
  real functional section named "Terms" escape the intro-prose and singleton
  checks; MP-1 was attributed to round 3 when it landed at `a95dcb5` (round 2);
  the item-5 provenance line named only the REQ prompt.
- **Correction of record** — `0e75fd2`'s message explains the structural-regex
  widening as preventing the glossary being counted "as a functional section
  with no REQs". That inverts the mechanism: `_render_classify_sections` skips
  REQ-free sections *before* consulting the regex, so an ordinary glossary was
  never at risk; the widening matters only for a glossary that *contains* REQs.
  Code right, explanation wrong. History is not rewritten here, so the
  correction lives in `0f7cc0a` and here.

### Self-caught before the panel reported

The item-5 expectations doc asserted **two code facts it had never checked**,
and both were wrong:

- express REQ-003: I claimed the JSONP guard *rejects* member-access chains and
  invented a grammar. It **sanitizes in place** (`response.js:286`), and its
  permitted set *includes* `.`, `[`, `]` — which is exactly why the Council
  could not tell whether chains were "rejected or proven safe".
- virtio REQ-009: I claimed "clamping is what the code does". It **rejects**
  with `-E2BIG` (`virtio_ring.c:3342`). The halving loop I mistook for clamping
  (`:1262-1270`) answers a different question — allocation pressure, not the
  device maximum — so the REQ also conflates two conditions, which is a finding
  beyond the disjunction.

This is the fabrication class instruction 001's Council caught as a P0 in
virtio's coverage statement. Corrected against source in `64b48c8`, and
**recorded in the file itself** rather than quietly fixed: a document that tells
a future regeneration what to expect is worthless if its own claims were
invented. The doc now separates *Council-supplied* from *source-verified* from
*open-question* claims.

---

## Underspecified or wrong in this instruction

1. **The item-4 delta attribution is wrong** — "a chi intro-prose FAIL" was
   already inside the original 11 (evidence above). Minor, but it is a factual
   claim in an instruction correcting factual claims.
2. **"Both producers" was the wrong granularity for item 1.** The seam has two
   producers but three authoring surfaces, and the defect the instruction cites
   as evidence (express UC-06.b) lives on the surface the phrasing let me miss.
   A future instruction is better served by "every surface that authors
   acceptance text" than by naming the seam.
3. **Item 3's acceptance anticipated a FAIL collision; the real one was a WARN
   collision.** "Confirm zero new FAILs" was satisfiable immediately, but
   `test_regenerated_documents_emit_no_advisory_warnings` asserted *zero WARNs*
   on the fixtures. Resolved with a known-WARN allowlist plus a staleness guard
   and a live F-1 assertion, so a new advisory still fails while the recorded
   glossary gap does not — but the instruction's bar did not describe it.
4. **Item 2's "delete it and its test" is ambiguous** and the two readings
   differ materially. `_render_requirements_md` is called by `curate()`, so
   deleting only the function breaks the module; deleting the whole module
   destroys what Design §1.3/§7 names as the B-4 substrate and first
   point-release candidate. I deleted the renderer, its call site, `_section_meta`
   and the two now-dead config fields, and kept the algorithm. The panel checked
   §1.3 and §7 directly and judged the reading defensible.
5. **Design §5.2 and the Plan still say "eight-part".** Item 3 makes the
   architecture nine. Both are orchestrator-owned so I did not edit them; the
   guide states the relationship (the eight mandatory parts are unchanged, the
   glossary is a ninth advisory one) and flags that §5.2 should absorb it.

---

## Notable observations

**A shared-tree race is a real runner hazard.** Both panelists independently hit
a phantom suite failure caused by one agent running source-mutation bites while
another ran the suite. Neither was a defect, and both caught it by re-running
with a checksum — but concurrent reviewers on one working tree will keep
producing this. Worth serializing mutation bites, or giving each reviewer a
worktree.

**`definitions` still carries the bypass `terms` had.** Round 2 confirmed this
by execution. Left in place as a risk judgment — "Definitions" is a canonical
IEEE 830 §1.3 part name, "Terms" is an ordinary domain noun — but the judgment
is now written into the code so a future reader does not re-widen the list. That
is the same lesson as B-1 and as instruction 001's HTML type-7 exclusion: a
deliberate divergence recorded only in a commit message is one nobody checks.

---

## Next action expected from orchestrator

1. **Absorb the glossary into Design §5.2** (or reject it) — the guide currently
   carries a ninth advisory part the Design does not mention.
2. **Follow-up FU-B from round 2**, not closed here: `requirements_pipeline.md`
   and `phase1_exploration_guide.md` are live skill-authoring surfaces that may
   also warrant the no-disjunction rule. I scoped to the surfaces the
   instruction named plus the one the Council proved load-bearing; extending
   further is a scope call, not a worker judgment.
3. **Phase 3 (Feature D)** is unblocked by the Council's disposition — the
   interview walks the document structure, which scored 5 on Well-organized
   across nine panelists, and the disjunctive clauses are now prevented at
   source with expectations recorded for the next regeneration.
