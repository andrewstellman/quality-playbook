# Output for 007-section-hierarchy-and-renumber.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` | Item 2: `_render_product_section_count` helper; MP-5 fail-closed section check (manifest ≥2 product sections but 1 parseable section → FAIL); per-section checks skipped when `flattened` (no vacuous PASS). |
| `references/phase2_generation_guide.md` | Item 1: new "Section / requirement heading hierarchy" subsection — sections at `##`, `### REQ-NNN:` nested, with a worked example + the flattening prohibition. |
| `references/requirements_interview.md` | Item 4: "Renumber is the interview's terminal step" paragraph (E.6 once, terminally; updates the manifest's id cross-references atomically; leaves the content-keyed append-only confirmations untouched). |
| `bin/tests/test_render_contract_v160.py` | `SectionHierarchyTests` (MP-5 mutation bites + `_flattened_requirements_md` + per-section-non-vacuity proof + single-section-not-flagged); `SequentialIdOrderTests` (out-of-order-but-set-complete → FAIL); AUDIT row MP-5 (size 11→12). |
| `bin/tests/test_feature_d_interview_fixture_v160.py` | `TerminalRenumberTests` + `_render_requirements_md(manifest, renumber=…)`: add-into-early-section → sequential IDs; deferred renumber → "not sequential" FAIL; confirmation resolves by content. |

## Commits made
- `9143959` — v1.6.0 [instr 007]: section-hierarchy fail-closed + sequential-ID + terminal renumber (implementation).
- `c831b1c` — v1.6.0 [instr 007]: tracked self-Council synthesis.
- `<this commit>` — runner: output for instruction 007.

## Acceptance criteria — pass/fail per item
| Criterion | Result |
|-----------|--------|
| Flattened-doc FAIL/WARN now firing | **PASS** — MP-5 FAILs a multi-section manifest rendered flat (`test_mp5_fires_on_a_flattened_multi_section_render`), and the vacuous per-section PASS is suppressed. Mutation-bitten. |
| Per-section checks actually evaluate each section (non-vacuity) | **PASS** — `test_per_section_check_evaluates_each_section_when_nested`: a correctly-nested doc missing the 2nd section's overview FAILs. |
| Out-of-order-ID FAIL now firing | **PASS (already enforced)** — reproduced express's `…,4,3` case: the current check FAILs it. Pinned by `SequentialIdOrderTests`. See finding #1 below. |
| Terminal-renumber fixture: add-into-early-section → sequential IDs + confirmations resolve | **PASS** — `TerminalRenumberTests`; renumber=True → sequential; the added REQ's confirmation resolves by content. |
| Mutation: deferred renumber (out-of-order surviving) fails | **PASS** — `test_deferred_renumber_ships_out_of_order_and_fails` (renumber=False → "not sequential" FAIL). |
| Golden fixtures unaffected (already H2 sections) | **PASS** — chi/express/virtio use `##` requirement sections; no fixture correction needed. |
| Full suite + counts + Python version | **PASS** — `python3 -m unittest discover bin/tests` → **2609 tests, 0 failures, 14 skipped**, Python 3.14.6. |

## Council (if required)
**Verdict: unanimous SHIP** (single round, zero fix rounds). Three charters per the
instruction, each panelist worktree-isolated.

| Panelist | Charter | Verdict |
|----------|---------|---------|
| A | fail-closed section detection (MP-5) | **SHIP** |
| B | sequential-ascending-order ID check | **SHIP** |
| C | interview terminal-renumber + F-2a | **SHIP** |

- **A** confirmed MP-5 fires only on the exact collapse-to-1 case (no false positive on a
  genuine merge), mutation-bitten (precise single-test kill), the per-section non-vacuity proof
  is real, and the golden fixtures (H2 sections) are unaffected.
- **B** independently reproduced express's `…013, 035, 014…` shape and confirmed the current
  check **FAILs** it — work item 3 is a no-op on current code; the express premise does not
  reproduce. Mutation-bitten (degrading to a set-only check turns the new pin RED); all edge
  cases correct; flattening cannot mask the ID check.
- **C** adjudicated the `req_id` contradiction and confirmed the worker is **right to flag, not
  implement**: the confirmation record has no `req_id` (content-keyed per F-2a, which predates
  007 in `dd03e77`), and updating one would break both the append-only invariant and the
  not-id-keyed design. The terminal-renumber protocol + fixture are correct and order-dependent.

Artifacts: `RUNNER_ROOT/reviews/007_self_council/` (gitignored) and the tracked mirror
`docs/process/QPB_v1.6.0_Instruction_007_Self_Council/synthesis.md`.

## Notable observations

### The flattening now FAILs, and the vacuous PASS is gone
The exact chi shape — a single non-structural `## container` holding `### Section` subsections
interleaved with `### REQ-NNN:` — reproduced the vacuous pass on the pre-fix code ("PASS: all 1
requirement section(s) carry a section overview" for a multi-section manifest). MP-5 now FAILs
it ("requirements_manifest.json groups the product requirements into N sections, but
REQUIREMENTS.md exposes only 1 parseable requirement section — the section headers were most
likely rendered at the '### REQ-NNN:' heading level (H3) instead of one level up"), and the
per-section block is gated `if functional and not flattened:` so it no longer prints a
misleading PASS beside the FAIL.

### Every fixture change, and why
- **No golden fixture was edited.** The instruction anticipated the render-contract fixtures
  might need their section headers moved to H2 — but chi/express/virtio *already* use `##` for
  requirement sections with `### REQ-NNN:` nested (the flattening was in the separate
  `repos/{...}-test/` live-run outputs, not the golden `bin/tests/fixtures/render_contract_v160/`
  snapshots). So they pass MP-5 unchanged.
- **New inline test fixtures** (all in test files, not golden snapshots): `_flattened_requirements_md`
  (the flattening), the single-section manifest, the out-of-order-ID doc, and the
  add-into-early-section session — each a purpose-built input, not a golden snapshot edited to
  dodge a check.

### The out-of-order-ID FAIL — the express case reproduced
`test_deferred_renumber_ships_out_of_order_and_fails` and `SequentialIdOrderTests` both confirm
the render contract FAILs a set-complete-but-out-of-order ID sequence. See finding #1.

### F-1 coverage-and-gaps prominence (record, not fixed here)
Recommended: **yes, a prominence fix is worth a follow-up.** F-1 was omitted by 2 of 3 runs
(chi, express — WARN each) and by the earlier bus-tracker run. The recurrence pattern matches
the marker-format and section-hierarchy misses: the instruction is present in the guide but not
*salient* — it lives in a prose paragraph, not as a labelled part with a worked example. The
same fix that worked for the marker format (a labelled subsection + worked example showing the
literal coverage-and-gaps block in the Overview) would likely raise adherence. It stays advisory
(WARN); prominence, not enforcement, is the lever. Deferred to the orchestrator per the instruction.

### Also observed (for the orchestrator, out of scope)
- **Phase-0 double-marker block** (`.claude` + `.github`) caused friction in all three runs — noted.
- **Phase-2 validator requiring `bugs_manifest.json` at Phase 2** caused friction (Phase 2 is
  requirements generation; bugs are a Phase-3 artifact) — noted.

### Anything in §5.2 / §5.3 / §6 found underspecified or wrong

1. **Work item 3 (sequential-ID) is already satisfied by the current code — the express
   observation does not reproduce.** Check 1 compares the document-order REQ numbers against
   `[1..N]` (`numbers == expected`), which enforces ascending order, no-gaps, and start-at-1 all
   at once. I reproduced express's shape (set-complete IDs out of ascending order): the current
   contract **FAILs** it, both nested and flattened. So either the express observation predates
   this check or conflated it with the flattening (defect 1, which IS real — a flattened doc that
   the contract mis-parsed could have masked the ID disorder in the operator's reading, but the
   mechanical check still fires). I added `SequentialIdOrderTests` to *pin* the ascending-order
   behaviour so a future regression to a set-only check is caught, and flag that no code change to
   Check 1 was needed. **Recommend the design/instruction note that Check 1 already enforces
   ascending document order.**

2. **Work item 4's "update operator_confirmations.jsonl `req_id` fields" rests on a false
   premise — the record has no `req_id`.** F-2a (instruction 003, operator-approved) deliberately
   made confirmations **content-keyed** (`req_title` + `conditions_of_satisfaction`), explicitly
   *not* keyed on REQ id, *because* E.6 renumbers every run — and the log is **append-only**, so
   its records are never rewritten. There is therefore nothing to update: a confirmation resolves
   to its REQ by content after the renumber. Updating a stored req_id would both be impossible
   (no such field) and reverse the F-2a design + break the append-only invariant. I implemented
   the terminal renumber to update the manifest's real id-carrying cross-references and leave the
   confirmations untouched, and surfaced this rather than reverse F-2a. **Recommend §6 drop the
   "including operator_confirmations.jsonl req_id fields" clause — it contradicts §8 F-2a.**

3. **The section/requirement heading *hierarchy* was never stated in §5.2, only assumed by the
   code.** The contract has always treated `##` as the section level and `### REQ-NNN:` as the
   requirement level (the `_render_classify_sections` intent), but §5.2 and the generation guide
   described the *parts* without ever showing the *levels* — which is exactly why three capable
   runs flattened sections to `###`. §5.2 should state the H2/H3 hierarchy explicitly (now added
   to the generation guide with a worked example).

## Next action expected from orchestrator
Land the instruction-007 commits on `1.6.0` (worker never pushes/merges). Consider: (a) note in
§6 that Check 1 already enforces ascending order; (b) drop §6's "req_id fields" clause (contradicts
F-2a); (c) the F-1 prominence follow-up; (d) the Phase-0 / Phase-2 friction items. Track 2 remains
out of scope.
