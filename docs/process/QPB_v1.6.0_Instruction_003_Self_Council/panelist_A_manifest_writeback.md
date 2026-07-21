# Panelist A — Manifest write-back correctness (v1.6.0 Feature D, instr 003)

VERDICT: FIX-REQUIRED

Reviewer: Panelist A (worker self-Council). Charter: manifest write-back correctness.
Commits reviewed: ca483e2, 5f1b3d6, dd03e77, bcc5585 (checked out at bcc5585 in an
isolated worktree). Full suite run: **2573 tests** (1 failure + 6 errors, all
environmental — see Appendix). Worktree clean after all mutation bites (`git status`
empty; all bites restored from pristine snapshots via `shutil.copy2`).

The verdict is FIX-REQUIRED on the strength of a single P1 finding: **the F-2a
append-only durability guarantee — the headline promise of the whole slice — is not
actually enforced in any real run.** Everything else the charter asked me to check is
sound; two of the tests are weaker than their names claim (P2), but the shipped gate
logic for source_type and invariant #21 is correct.

---

## P1 — F-2a append-only enforcement is inert: a truncating/wiping re-derivation PASSES the gate and destroys the operator's confirmations

**This is the load-bearing invariant of F-2a, and it does not hold end-to-end.**

`check_operator_confirmations_append_only` (quality_gate.py:7772-7852) only performs
the append-only prefix comparison **when `quality/operator_confirmations.prior.jsonl`
exists** (quality_gate.py:7829-7830). When no prior snapshot is present it falls
through to `elif shape_ok:` and emits a PASS.

**Nothing in the shipped system ever creates that `.prior.jsonl` snapshot.** I grepped
all shipped code, references, phase guides, and SKILL.md:

- The only three occurrences of `.prior` in shipped code are the gate *reading* it
  (quality_gate.py:7746, 7827, 7829) — and its bundled duplicate
  (quality_playbook_cli/_bundle/quality_gate.py, same three lines).
- The *only* writer of `operator_confirmations.prior.jsonl` in the entire tree is the
  test fixture itself (test_feature_d_interview_fixture_v160.py:418, 445), which
  manually writes the snapshot immediately before invoking the check.
- `run_state_lib.append_confirmation` only appends; `read_confirmations` only reads.
  Neither snapshots.
- `references/requirements_interview.md` (the protocol the agent actually follows)
  describes the append-only invariant in prose (L227-230) but **never mentions
  `.prior.jsonl`**, so an agent driving a re-run has no instruction to create it.

The gate's own comment (quality_gate.py:7825-7828) states the intended contract —
"A re-derivation that intends to preserve the log copies it to `.prior.jsonl` before
rewriting `quality/`" — but that copy step is implemented and documented **nowhere**.

**Empirically verified** (isolated `check_operator_confirmations_append_only` runs):

- **Case A — truncation without snapshot.** Interview writes 2 real confirmation
  records; a re-derivation truncates `operator_confirmations.jsonl` to empty; no
  `.prior.jsonl` exists → **FAIL=0**, gate prints
  `PASS: operator_confirmations.jsonl well-formed (0 record(s); no prior snapshot to
  diff against)`. The operator's work is destroyed and the gate certifies clean.
- **Case B — re-run rebuilds `quality/` from scratch.** The Design's own hazard framing
  is "QPB re-derives that manifest on every run." A run that rebuilds `quality/` leaves
  no jsonl at all → **FAIL=0**, gate prints
  `INFO: operator_confirmations.jsonl not present — no interview has run`. Total silent
  loss, certified clean.

This directly contradicts three shipped statements of the contract:

- **schemas.md §9.5.2:** "A derivation that **deletes, truncates, or shortens**
  `operator_confirmations.jsonl` fails the gate (`check_operator_confirmations_append_only`)."
- **references/requirements_interview.md:227-230:** "The derivation never rewrites or
  truncates it. A run that would delete or shorten it **fails the gate.** This is the
  load-bearing invariant."
- **Design §8 F-2a Verification:** "Mutation: a derivation path that truncates or
  overwrites the file fails the fixture."

The fixture's durability oracle (`F2aDurabilityOracleTests.test_truncating_rederive_fails`,
bcc5585 test file L441-453) only exercises truncation **with** a hand-written
`.prior.jsonl` — a precondition that holds only inside the test. dd03e77's commit
message asserts "a truncating path FAILs substantively, which is the whole point of
F-2a"; that claim is true only under the test's artificial setup, not in any real run.

**Severity — P1, borderline P0.** It is silent data loss of the release's headline
feature, and the gate the spec designates as the protection is inert against it. It sits
just short of P0 only because the *intended happy path* (a re-derivation that leaves the
append-only file untouched) does preserve the data by discipline — but the whole point
of a gate is to catch the paths that lack that discipline, and this one catches none of
them. The Design explicitly scopes the write path (manifest **and** the append-only
artifact) into "the Feature D slice, not a later retrofit" (§8 F-2a), so the missing
snapshot writer is in-scope for exactly these commits.

**Direction of fix (not my job to apply):** either (a) make the sanctioned re-derivation
path snapshot `operator_confirmations.jsonl → .prior.jsonl` before it may touch
`quality/`, and gate on the snapshot's presence when a prior run existed; or (b) drop the
`.prior.jsonl` indirection and have the gate compare against the archived prior run
directly. As written, the invariant is enforced only against a file the system never
produces.

---

## P2 — The drift guard `test_schema_table_and_gate_enum_agree` is one-directional; the charter's exact mutation leaves it GREEN

The charter predicted that removing `operator-confirmation` from the gate enum while
leaving it in schemas.md would turn `test_schema_table_and_gate_enum_agree` RED.
**Mutation-bite refutes that** (bite performed, restored):

- `test_schema_table_and_gate_enum_agree` → **stays GREEN ("ok")**. It only iterates
  `for value in _V153_VALID_SOURCE_TYPES` and asserts each value has a schemas.md row —
  i.e. it enforces `gate-enum ⊆ schema` only. Shrinking the enum leaves every remaining
  value documented, so it passes. The reverse divergence — a value documented in
  schemas.md §3.7 but **missing from the gate enum** — is exactly the direction it does
  not check.
- The mutation *is* caught, but by **sibling** tests: `test_operator_confirmation_in_allowlist`
  (explicit membership), `test_operator_confirmation_req_passes_invariant_21`, and
  `TestV153SourceTypeValidation::test_v153_shaped_with_operator_confirmation_source_type_passes`
  all go RED.

Why this matters beyond the specific value: the more insidious real-world drift is
"document a new source_type, forget the gate enum" — the docs promise a type the gate
then rejects, failing legitimately-shaped manifests. The guard whose name promises
value-for-value agreement misses precisely that direction. 5f1b3d6's commit message
overstates it: "asserts the gate enum and the schemas.md §3.7 table **agree
value-for-value**" — it asserts one-way containment. Low practical risk today (the one
new value has dedicated positive tests), so P2, not P1. A future value added to schemas
without its own membership test would slip past.

## P2 — `CorrectionMustReachManifestMutationTests` is a tautology; the real coverage lives elsewhere

`CorrectionMustReachManifestMutationTests.test_correction_only_in_transcript_is_caught`
(bcc5585 test file L358-399) hand-builds a divergent tree (writes the confirmation log
claiming a correction, writes the manifest *without* it) and then asserts the divergence
exists (`assertFalse(correction_reached)`, `assertNotEqual(correction_reached, claimed)`).
It **never calls `_apply_move`** and never invokes the fixture's acceptance assertion —
so it would pass unchanged even if the entire write-back were broken. It is decoupled
from the code under test; it demonstrates a scenario rather than testing a code path.

The Design §6 requirement ("a correction that never reaches the manifest must fail the
fixture") **is** genuinely met — but by `InterviewFixtureSessionTests`, not by the class
named for it. **Mutation-bite confirms** (performed, restored): editing `_apply_move`'s
`correct` branch to skip the manifest write turns `InterviewFixtureSessionTests::
test_correction_reached_the_manifest` **and** `test_touched_records_carry_operator_confirmation`
RED. So the protection is real and incidental; the "mutation" test named for it is
theater. P2: fine to ship, but the named guard gives false confidence and should either
drive the real fixture against the mutated write-back or be relabeled.

## P2 — The re-render acceptance is weaker than it reads

`_render_requirements_md` (bcc5585 L78-134) mutates the manifest in place (renumbers the
same dicts at L95-97, `manifest["records"] = ordered`) and then renders from those same
dicts — so **manifest↔render id agreement is tautological by construction** and cannot
fail. `check_render_contract` enforces only internal REQ-id sequentiality (Check 1) and
tool-contract leakage/relocation (Check 2); it does **not** enforce general manifest↔
render content agreement. So "re-render passes the Feature C render contract" is a real
but narrower guarantee than "the manifest and the render agree" — a real interview
re-render that dropped or mis-ordered a REQ relative to the manifest would not be caught
here (only tool-contract leakage would). The cross-section-singleton FAIL path is real in
the render contract (quality_gate.py:7560-7597, unjustified singleton → FAIL) and *is*
the correct behavior, but the fixture deliberately never exercises it — the merge is
within the Rendering section (test file L233-234) precisely to keep ≥2 REQs. Honest
limitation, pre-existing to Feature C; noting it so the panel doesn't over-credit the
re-render assertion.

## P2 (minor) — three uncoordinated copies of the five-moves tuple

`_OPCONF_MOVES` (quality_gate.py:7757), `_REQ_REVIEW_MOVES` (quality_gate.py:7860), and
`run_state_lib._CONFIRMATION_MOVES` (run_state_lib.py:1696) are three independent copies
of `("confirm","correct","add","drop","defer")`, plus the schemas.md §9.5.1 prose list —
with no drift guard between them (unlike the source_type enum, which at least has the
one-directional guard above). Adding a sixth move requires editing three tuples with
nothing to catch an omission. Same drift class as P2 #1.

---

## What is sound (charter items confirmed clean)

- **Item 1 — evidence shape.** `operator-confirmation` is present and consistent across
  all three sites: schemas.md §3.7 (row added, 5f1b3d6), `_V153_VALID_SOURCE_TYPES`
  (quality_gate.py:4793-4797), and the positive test. They agree.
- **Item 2 — skill_section / invariant #21.** `check_v1_5_3_skill_section_consistency`
  (quality_gate.py:6079-6135) enforces skill_section-absent for the new type via the
  generic `else:` branch (L6125-6133), which needed no change. **Bite confirmed**: an
  `operator-confirmation` REQ with a populated `skill_section` → **FAIL=1**
  (`skill_section='phase2_generation' populated but source_type='operator-confirmation'
  is not 'skill-section'`). Correct.
- **Item 4 — content-not-id keying.** Sound by design. Traceability is one-way
  REQ→UC keyed on stable UC ids (schemas.md §3.7 `use_cases`, §10 invariant #17); F-2a
  keys on content (`req_title` + `conditions_of_satisfaction`), never on REQ id
  (schemas.md §9.5.1); the citation is a transcript `path:line`, not a REQ id. No durable
  cross-reference stores a REQ id that E.6's renumber could orphan. `_apply_move`'s
  transient `REQ-{len(recs)+1:03d}` (test file L166) is immaterial — E.6 renumbers and
  nothing durable keys on it. The fixture's content-keyed assertions are the correct
  choice.
- **Item 5 — the real fixture is protective.** Proven by the bite above:
  `test_correction_reached_the_manifest` genuinely fails when the write-back drops the
  manifest write. (The *named* mutation class is a tautology — see P2 #2.)

## Appendix — suite state

`python3 -m pytest bin/tests/` → **Ran 2573 tests**, 1 failure + 6 errors, all
environmental and unrelated to Feature D: `test_language_disclosure_override_058`
(no baseline repo under `repos/`) and `test_setup_repos` (bundling — missing repos/
fixtures). All Feature D targeted tests pass (327 in the gate+fixture+supersession
selection; 18 in the two feature_d files after restore). Mutation bites were taken
against pristine `shutil.copy2` snapshots of `quality_gate.py` and the fixture file and
restored the same way; `__pycache__` purged between bites; final `git status` clean.
