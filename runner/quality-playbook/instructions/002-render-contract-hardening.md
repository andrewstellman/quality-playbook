# Instruction 002 — v1.6.0 render-contract hardening (pre-Feature-D)

Small, self-contained follow-ups to instruction 001, landing **before** Feature D so the interview is built against a corrected spec. Four items; none should take long.

## Read first
- `docs/design/QPB_v1.6.0_Design.md` §5 (Feature C) and §8 (F-1 — the WARN-only precedent item 3 follows).
- `docs/design/QPB_v1.6.0_Implementation_Plan.md` Phase 2 — note the readability Council is now specified there and has **run**; its synthesis drove this instruction.
- `docs/design/QPB_v1.6.0_Requirements_Readability_Rubric.md` — the rubric the Council scored against.
- `ai_context/DEVELOPMENT_PROCESS.md` — process, Council, verify-before-claim, commit hygiene.

## CRITICAL CONSTRAINT — do not hand-edit the fixture documents

`bin/tests/fixtures/render_contract_v160/{chi,express,virtio}/quality/REQUIREMENTS.md` are **snapshots of what the pipeline produces**. Hand-polishing them would turn the acceptance oracle into a test of hand-written exemplars no pipeline generates. The Council found real defects in those documents; the fix for all of them is at the **source** (the generation guide), verified later by regeneration — never by patching the artifact.

If any work item seems to require editing a fixture `REQUIREMENTS.md`, stop and write a `pre-flight-aborted` output explaining why.

## Work items

### 1. Prompt-level guardrail: no disjunctive acceptance clauses
All nine Council panelists independently flagged requirements shaped **"X, *or* document that not-X."** They have no single pass/fail oracle — a test author cannot write a decisive test, and two implementations can both claim conformance. Live instances (do not edit these; they are evidence): chi REQ-002, express REQ-005/UC-06.b, express REQ-003, virtio REQ-005 item 5, virtio REQ-009.

Add a rule to `references/phase2_generation_guide.md`: **a requirement states one required behavior.** Never "X, or document that not-X"; never "rejects or clamps"; never "acceptable only if documented" without naming where that documentation lives and what it must say. If genuine alternatives are acceptable, the requirement states the decision procedure that selects between them.

**Do not add a mechanical gate check for this.** A regex would false-positive on legitimate disjunction ("returns 400 or 422") and false-negative on rephrasing; a FAIL on that basis is worse than the defect. The mechanical layer is the wrong instrument — the rubric's Verifiable dimension already catches it by judgment, and it did. This is prevention at source, the same shape as the C-7 fix (a hardcoded literal removed from the template, not a checker bolted on).

Apply to **both** producers per the OD-10 seam if the rule belongs to both; say which you touched.

### 2. Delete the dead renderer carrying the C-7 defect
`bin/skill_derivation/curate_requirements.py::_render_requirements_md()` hardcodes `"# QPB v1.5.3"` — the exact defect class C-7 fixed. Instruction 001 confirmed it is dead: no callers outside its own test, not shipped in the bundle. **Delete it and its test** rather than parameterize; per operator decision, it is not going to be used.

Verify no remaining callers before deleting, and confirm the suite is green after.

### 3. Glossary slot in the document architecture — WARN only
IEEE 830 §1.3 exists because terminology drift is a top defect class, and "Consistent" (terminology stability) is a dimension the Council scores. The eight-part architecture has no glossary.

Add a glossary/definitions slot to the architecture in `references/phase2_generation_guide.md`, and a render-contract check that it is present and non-empty — **advisory WARN, never a gate FAIL**, exactly as F-1's coverage-and-gaps statement is specified in Design §8.

**Acceptance is explicit here:** the three existing fixtures have no glossary and **must not begin failing.** Run the gate on all three and confirm zero new FAILs; a WARN on each is the expected and correct outcome. If this item would FAIL any existing fixture, it is implemented wrong.

### 4. Correct the stale numbers in `outputs/001-fr-c-spec-organization.md`
Independent verification found two figures that do not reproduce:
- The C-1…C-7 table and `docs/process/.../evidence_c1_c7_before_after.md` report before-state gate failures of **11 / 9 / 6** (chi/express/virtio). Re-running `check_render_contract` against the `.before` fixtures with current code gives **13 / 12 / 9** — the delta is the MP-1 checks plus a chi intro-prose FAIL. The evidence doc was committed at `8db8af3`, *after* the Phase-2 code commits, so it was written and never regenerated against final gate behavior.
- Line 10 reads "Nothing pushed; 12 local commits." The actual count was 16.

Regenerate both figures from current code and correct both files. Note in the output that the error direction was safe — actual detection is stronger than reported — and that this is the same failure class the instruction-001 self-Council caught at round 3.

### 5. Record the regeneration expectations
Write `docs/process/QPB_v1.6.0_Regeneration_Expectations.md`: for each of the five disjunctive clauses in item 1, the current text and the expected resolved form, so a future regenerated run can be checked against a written expectation rather than re-litigated. Source the expected forms from the Council synthesis (`~/Documents/AI-Driven Development/Quality Playbook/Reviews/QPB_v1.6.0_Slice1_Readability_Council_Synthesis.md`, Finding 2). State plainly that these are **expectations for a future run, not edits to the fixtures.**

## Branch / commit policy
Work on **`1.6.0`**. Pre-flight: confirm `git -C "$QPB_REPO" rev-parse --abbrev-ref HEAD` is `1.6.0`; if not, write a `pre-flight-aborted` output and stop. Focused local commits. **Never push, never merge** — the operator lands.

## Council
Given the size, a **focused single-panel review** is sufficient rather than a full three-panelist self-Council — with one exception: **item 3 requires a panelist charter of its own** verifying the WARN-never-FAIL property holds, including a test proving the check fires as WARN and cannot escalate to FAIL. Write artifacts under `RUNNER_ROOT/reviews/002_self_council/` **and** a tracked copy under `docs/process/QPB_v1.6.0_Instruction_002_Self_Council/` — the `reviews/` path is gitignored by a bare `reviews/` pattern matching at any depth (confirmed in 001).

## Acceptance
- Item 1: the rule is present in the generation guide; no mechanical check was added; both producers addressed or the omission explained.
- Item 2: function and test deleted; no callers remain; suite green.
- Item 3: glossary slot in the architecture; check present; **all three fixtures WARN and none newly FAIL**; a test proves the check cannot FAIL.
- Item 4: both figures regenerated from current code and corrected in both files.
- Item 5: expectations file written and tracked.
- Full suite result + counts + your Python version.

## Output
`outputs/002-render-contract-hardening.md` per the README schema, plus: which producer(s) item 1 touched, the before/after gate counts you measured for item 4, and anything in this instruction you found underspecified or wrong.
