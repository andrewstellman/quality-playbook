# Output for 027-feature-c-render-labeled-slots.md
**Status:** completed

## What this instruction was
The final simplification (Fable Q4). Feature C's render-contract gate had four
checks that mechanized a prose-QUALITY judgment as a hard FAIL — the same smell as
the advisory floor. `_render_rationale_present` had already false-FAILed two
well-formed specs (chi's bare "so", virtio's "Rationale:" label). Fable rejected a
plain FAIL→WARN downgrade as too weak and prescribed **labeled-slot format
contracts**: the generation guide requires a labeled slot; the gate FAILs on the
slot's ABSENCE (structural); content quality goes to the interview + rubric.

## Terminal verdict: unanimous SHIP (0 FIX-REQUIRED)
| Charter | Verdict |
|---------|---------|
| A — The gate keeps its teeth (absence FAILs structurally) | **SHIP** |
| B — No phrasing/length/quality judgment remains | **SHIP** |
| C — The generator emits the slots + no scope creep | **SHIP** |

Each panelist ran the gate against the reviewed commit and mutation-bit the teeth.

## The conversions (before → after)
| # | Conversion | Before | After |
|---|-----------|--------|-------|
| 1 | **Organizing principle + rationale → one labeled slot** | `_render_rationale_present` scored ≥2 sentences of ≥4 words OR a 27-alternation connector list; `_RENDER_PRINCIPLE_RE` matched prose phrasing | require `Organizing principle: <name> — Rationale: <text>`; FAIL only on label absent / name empty / rationale empty (`_RENDER_PRINCIPLE_SLOT_RE`). **Deleted** `_RENDER_RATIONALE_CONNECTOR_RE`, `_render_rationale_present`, `_RENDER_SENTENCE_SPLIT_RE`, `_RENDER_RATIONALE_MIN_WORDS`, `_RENDER_PRINCIPLE_RE` |
| 2 | **Singleton justification → labeled presence** | keyword scan `singleton\|stands alone\|only requirement\|…` of the content | require a `Standalone rationale: <why>` slot; FAIL on absence (`_RENDER_SINGLETON_LABEL_RE`). **Deleted** the keyword scan |
| 3 | **Section overview → presence, not length** | `len(intro) >= 40` | `bool(intro)` (non-empty). **Deleted** the 40-char threshold |
| 4 | **Generator emits the slots** | prose ("Organized by … because …") | `references/phase2_generation_guide.md` + `requirements_pipeline.md` E.5 require the labeled slots |

## Invariants held (Council-confirmed)
- **Teeth intact (Panelist A):** an absent slot / singleton justification / section
  overview each still **FAILs structurally** (empty-name FAILs too); each teeth is
  mutation-confirmed load-bearing; all three call `fail()`, not `warn()` — stronger
  than a WARN a generator could skip.
- **No quality judgment (Panelist B):** all five deleted symbols gone; terse, weak
  ("it seemed reasonable"), bare-"so", 1-char-overview, and nonsense-content
  singleton slots all pass 0 FAIL. The two recorded false-FAIL cases (chi "so",
  virtio "Rationale:") pass.
- **Generator↔gate consistency (Panelist C):** the guide's own example slot passes
  the gate; a compliant generator produces a passing spec.

## The two real false-FAIL cases now passing
- chi's bare **"so"** rationale → `Organizing principle: … — Rationale: … so …` passes (no connector gymnastics).
- virtio's explicit **"Rationale:"** label → the slot's `Rationale:` half is exactly the format now; passes.
Both built as fixtures and verified through the gate at 0 FAIL.

## Absent-slot cases still FAILing (teeth)
- Missing `Organizing principle:` slot → FAIL "no organizing-principle slot".
- Label present, empty `— Rationale:` half → FAIL "missing its rationale text".
- Singleton section without `Standalone rationale:` → FAIL.
- Section with empty/absent overview → FAIL "lack a section overview".

## Fixture discipline
The render-contract test fixtures (clean/use-case/flattened/single-section), the
`OrganizingPrinciple` + `C3` tests, and the interview-fixture rendered spec were
migrated to the slot format with reversal comments (a format migration). The
chi/express/virtio regeneration **golden files were NOT hand-edited** (Panelist C
confirmed the diff touches no `fixtures/` file) — their recorded principle-gap FAIL
was only re-worded in `EXPECTED_FIXTURE_FAILS` + the assertion; their true
regeneration remains a standing carry-forward run.

## Files changed
| File | Change |
|------|--------|
| `plugins/.../scripts/quality_gate.py` | slot/singleton/overview conversions; deleted 5 phrasing/threshold symbols; new `_RENDER_PRINCIPLE_SLOT_RE` + `_RENDER_SINGLETON_LABEL_RE`; rewrote `_render_organizing_principle_stated` |
| `references/phase2_generation_guide.md` | generator emits the labeled slots |
| `references/requirements_pipeline.md` | E.5 worked example → slot format |
| `bin/tests/test_render_contract_v160.py` | fixtures + `OrganizingPrinciple`/`C3` tests → slot; new `LabeledSlot027Tests` |
| `bin/tests/test_render_regeneration_fixture_v160.py` | recorded principle-gap FAIL re-worded (no golden edit) |
| `bin/tests/test_feature_d_interview_fixture_v160.py` | interview fixture spec → slot |

## Commits made (branch `1.6.0`, local only — never pushed)
- `c5e068d` — the labeled-slot conversion (gate + guide + tests).
- `883ebfe` — tracked self-Council synthesis.

## The simplification sweep is complete
Instructions **023–027** are done — all unanimous SHIP:
- 023 — Feature G floor → hard signals.
- 024 — Feature G classifier wired + loud failures.
- 025 — Feature G advisory floor operator-rescuable.
- 026 — Feature H directive-narrowing + dead-code deletion + tier-guard pin.
- 027 — Feature C render labeled-slot format contracts. **← this instruction**

## Remaining release items (OUT of this scope — for the orchestrator)
- Broader 1.6.0 acceptance testing + Phase 8 tag/merge.
- Set OD-9 from instr 019 data (0 spurious grounded adds).
- Feature-G non-plaintext-contract → FORMAL_DOC wiring.
- chi/express/virtio Slice-1 coherence-fixture regeneration (a real run — now doubly
  needed: the classifier tiering (024) AND the labeled-slot render (027) both changed
  what a regenerated spec looks like; the recorded principle-gap FAIL resolves then).
- OD-11 drop/selective-revert BUG-reference re-point hardening.
- Design-doc refresh (the historical `QPB_v1.6.0_Design.md` still describes the
  removed fabrication-tell as a Verification-3 backstop — instr-026 non-blocking).

## Artifacts
- Gitignored: `runner/quality-playbook/reviews/027_self_council/` (three panelist verdicts).
- Tracked: `docs/process/QPB_v1.6.0_Instruction_027_Self_Council/synthesis.md`.
