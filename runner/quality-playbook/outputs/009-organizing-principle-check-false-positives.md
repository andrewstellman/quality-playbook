# Output for 009-organizing-principle-check-false-positives.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` | Work items 1+2. New `_render_rationale_present` (structural rationale test) + `_RENDER_RATIONALE_CONNECTOR_RE`, `_RENDER_SENTENCE_SPLIT_RE`, `_RENDER_RATIONALE_MIN_WORDS`, `_RENDER_PRINCIPLE_LABEL_RE`. Rewrote `_render_organizing_principle_stated(text, zone_end, level2)` to widen the search zone through the first section's intro + honor a labelled `## Organizing principle` H2 anywhere. Updated the `check_render_contract` caller to compute `zone_end` (first REQ of the first functional section). |
| `bin/tests/test_render_contract_v160.py` | +5 test methods in `OrganizingPrincipleTests` (`test_009_*`) with the mutation bites; a "therefore" case added to the structural-detector test. |
| `references/phase2_generation_guide.md` | Work item 3. Disambiguated item 4's "top of the section list" → own paragraph / labelled `## Organizing principle` block placed after Actors & roles and immediately before the first requirement section, rationale in the same paragraph. |
| `docs/process/QPB_v1.6.0_Instruction_009_Self_Council/synthesis.md` | Tracked self-Council synthesis (SHIP). |
| `runner/quality-playbook/reviews/009_self_council/{panelist_A,panelist_B,panelist_C,synthesis}.md` | Gitignored full self-Council artifacts. |

## Commits made (branch `1.6.0`, local only — nothing pushed)
- `a88dc11` — fix false positives in the organizing-principle render-contract check (code + 5 mutation-bite tests).
- `2b9229c` — disambiguate organizing-principle placement in the generation guide (work item 3).
- `4a3cace` — add "therefore" to the rationale connector set (self-Council Panelist A follow-up).
- `91c10fd` — tracked self-Council synthesis.

## Acceptance criteria — pass/fail per item
| Criterion | Result |
|-----------|--------|
| Work item 1: rationale detection robust, not connector-keyword-brittle | **PASS** — structural test is the load-bearing arm (2+ substantive non-naming sentences, connector-free); connector list is a supporting signal for the single-sentence case. |
| WI-1 mutation bites: three real phrasings pass; bare "Organized by feature." FAILs | **PASS** — pinned by `test_009_rationale_detection_is_structural_not_keyword`. |
| Work item 2: zone accepts standalone-para / labelled-section / top-of-first-section placements | **PASS**. |
| WI-2 mutation bites: top-of-first-section passes; buried mid-section mention does not | **PASS** — `test_009_zone_accepts_principle_at_top_of_first_section`, `test_009_principle_buried_in_mid_section_is_not_accepted`, `test_009_labelled_principle_section_honored_anywhere`. |
| Work item 3: guide placement instruction disambiguated with the worked example | **PASS**. |
| No weakening: name-only FAILs; principle-less doc FAILs | **PASS** — verified by Panelist C on the real harness; existing `test_mp4_*` bites stay green. |
| No fixture hand-editing to pass; real phrasings/placements added as fixtures | **PASS**. |
| Track 2 untouched | **PASS**. |
| Self-Council (3 charters, mutating panelists in own worktrees) → SHIP | **PASS** — unanimous SHIP. |
| Full suite verified + counts + Python version | **PASS** — 2614 passed / 0 failed / 13 skipped; Python 3.14.6. |
| Verification against real docs (before/after) | **PASS** — see below. |

## Rationale-robustness approach chosen: STRUCTURAL (with a keyword *supporting* signal)
`_render_rationale_present(para)` returns True when the naming paragraph carries content
beyond merely naming the principle, via either arm:
- **(a) Structural, connector-free (load-bearing):** the naming sentence is followed by
  **two or more** substantive explanatory sentences. This carries chi and virtio and is
  robust to unseen phrasings — no keyword needed. A *single* trailing note (e.g. a lone
  section-ordering remark) is deliberately not enough, so a named-but-unjustified principle
  still FAILs.
- **(b) Connective/label (supporting):** a justificatory connector or "Rationale:" label
  anywhere in the naming paragraph (bare "so", because, since, thus, hence, therefore, in
  order to, "matches how/both/the", "maps cleanly/onto", "mirrors the", …). Needed only for
  the terse single-sentence case, where nothing structural can separate a reason clause from
  a name list ("organized by X because Y" vs "organized by X, Y and Z").

Why not pure keyword-widening: the instruction is right that "every widening misses the next
valid phrasing." Arm (a) is the answer — a genuinely elaborated multi-sentence justification
passes with zero recognized connectives. Why keyword survives at all: the single-sentence
rationale is genuinely undecidable structurally, and the instruction explicitly permits a
keyword component "as one signal."

## The three real docs now passing (reproduced before AND after)
| Target | BEFORE (pre-fix) | AFTER |
|--------|------------------|-------|
| `repos/chi-t3/quality` | FAIL=1 — "named but carries no rationale" (Bug A: bare "so" unmatched) | **FAIL=0** — "organizing principle named with a rationale" |
| `repos/express-t3/quality` | FAIL=1 — "no organizing principle stated" (Bug B: blockquote at top of first section, outside zone) | **FAIL=0** |
| `repos/virtio-t3/quality` | FAIL=1 — "named but carries no rationale" (Bug A: "Rationale:" label unmatched) | **FAIL=0** |

(Live-run outputs, read directly per the instruction; each doc's only FAIL was the
organizing principle, so FAIL 1→0 is the whole delta.)

## Mutation results
- **Real-doc mutation (definitive):** the pre-fix source produces the three false-FAILs above;
  the fix clears all three. Panelists A & B independently reverted their charter's slice in an
  isolated worktree and reproduced the corresponding false-FAIL (A: narrow connector + no
  structural arm → chi/virtio re-FAIL; B: `zone_end`→`first_section_offset` → express re-FAILs).
- **Test-level mutation:** reverting `quality_gate.py` to the pre-fix version (727894a) while
  keeping the new tests makes the `test_009_*` bites fail (1 failure + symbol errors), proving
  they pin the fix rather than passing vacuously.

## Self-Council
**Unanimous SHIP**, zero fix-required rounds. Charters: (A) rationale robustness, (B) zone
widening/boundedness, (C) guide-clarity + no-weakening + defensive sweep. Each panelist ran in
its own git worktree and wrote a full verdict file. Artifacts:
`runner/quality-playbook/reviews/009_self_council/` (full) and
`docs/process/QPB_v1.6.0_Instruction_009_Self_Council/synthesis.md` (tracked). One
instruction-aligned additive follow-up applied post-panel per Panelist A ("therefore" connector,
`4a3cace`).

## §5.2 / underspecification found
- **Prescribe-narrow / accept-broad asymmetry (intentional, worth recording):** the guide now
  prescribes the principle as its own paragraph *before* the first requirement section, but the
  check *also* tolerates a principle at the top of the first section (express) and a labelled
  `## Organizing principle` H2 anywhere. Design §5.2 item 4 says "top of the section list"
  without pinning which of these placements is canonical; the guide edit picks the standalone-
  before-first-section placement as canonical while the check stays lenient. This is the safe
  direction (guide narrow, check broad) but §5.2 itself does not disambiguate it.
- **Rationale presence vs. quality boundary:** §5.2 item 4 / matrix row 4c defers *quality* to
  the Feature D interview + Well-organized rubric, but §5.2 does not spell out the mechanical
  floor for "present." This fix sets that floor operationally (structural: 2+ explanatory
  sentences, or a justificatory connective) — the design could state the floor explicitly.

## Recorded for the orchestrator (out of scope for 009)
- **Same defect class elsewhere (Panelist C defensive sweep):** the F-1 coverage-and-gaps
  check and the principle *naming* regex (`_RENDER_PRINCIPLE_RE`) both still use fixed
  keyword-cue lists — the same brittleness class this instruction fixed for rationale
  detection. Both predate 009 (F-1 is WARN-only from instr 008); neither is a regression this
  change introduces. Candidate for a future robustness pass if either surfaces a false-FAIL.
- **Bundled `quality_gate.py` copies** (`.claude/`, `.codex/`, `.github/`,
  `quality_playbook_cli/_bundle/`) are gitignored build artifacts regenerated at build/install
  time; not hand-synced here (canonical tracked source is `plugins/.../scripts/quality_gate.py`).

## Next action expected from orchestrator
Review the SHIP synthesis and the four `1.6.0` commits (`a88dc11`, `2b9229c`, `4a3cace`,
`91c10fd`). Decide whether the recorded F-1 / naming-regex keyword-brittleness warrants a
follow-up instruction.
