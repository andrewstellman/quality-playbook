VERDICT: FIX-REQUIRED

# Panelist C — regression safety on manifest semantics, and blast radius

Commits reviewed: `71b1a81`, `d8d4229`, `edc5cec` (branch `1.6.0`).
Charter: is Feature C actually presentation-layer; blast radius of the new
blocking gate check; prompt/reference consumers; the RUN_CONTRACT.md
decision; test-suite health.

Everything below was executed, not read off. Test suite: **2485 tests, OK
(13 skipped), 102s** — the claimed 2441 → 2485 progression is real and the
tree is clean afterward (`git status --porcelain` empty).

---

## Summary

Two of the three commits are sound work. The render contract discriminates
rather than blanket-fails, the mutation-bite discipline is genuine, and the
tests are hermetic. But the load-bearing invariant the Implementation Plan
names — *"the manifest stays the source of truth; Feature C is
presentation-layer; Phase 1 carries a manifest-unchanged invariant"* — is
**not enforced by the tests that claim to enforce it, and is already
violated by the committed fixture**. Separately, the "inert on pre-v1.6.0
documents" escape hatch does not do what its own commit message and
`artifact_contract.md:50` claim it does: 49 archived trees fire the
contract, and two archived runs flip GATE PASSED → GATE FAILED.

---

## P0 — none

I found no defect that breaks recall measurement. I want to state that
precisely, because it was the charter's headline worry and it survived:
the recall-baseline targets (`repos/{chi,express,virtio}-1.5.8` and
`metrics/v1.5.10_integration_regression/*`) exit `1` both before and after
`d8d4229`. The new check adds FAILs to trees that were already failing; it
does not flip the measurement corpus. The P1s below are real regressions
but they are off the recall path.

---

## P1-1 — `ManifestUnchangedInvariantTests` is vacuous with respect to record content

`bin/tests/test_render_regeneration_fixture_v160.py:240-314`

The class docstring at `:241` promises *"same records, renumbered only"*.
The four tests verify: record **count** (`:254`), the sorted **multiset of
reference-lists** (`:265`), that after-ids are **dense** (`:284`), and that
**rendered ids equal manifest ids** (`:295`). Nothing compares any record's
`title`, `text`, `implementation`, `conditions_of_satisfaction`,
`functional_section`, `tier`, `source`, or `use_cases` across the boundary.

I constructed two mutations. Both survive all four tests:

**Mutation A — gut every record.** Copy the fixture; in each after-manifest
replace every field except `id` and `references` with the literal
`"PWNED"`. Result: `Ran 4 tests ... OK`. Every requirement in all three
targets can be replaced with a placeholder string and the "presentation-layer"
invariant still reports green.

**Mutation B — rotate references.** Shift `references[]` by one position
across the record list, so every REQ now cites the wrong source file. The
multiset of reference-lists is unchanged, so `test_reference_sets_are_
preserved` — the test whose own docstring says *"References are the REQ's
grounding; a renumber must not touch them"* — passes. Result: `OK`.
(`ToolContractSplitTests` gives incidental partial coverage here, but the
invariant class itself does not.)

The multiset comparison at `:271-277` is the specific defect: it discards
the record↔references association, which is the only thing that makes the
assertion meaningful.

**Fix:** match records before↔after by the renumber map (or by a stable
content key), then assert field-by-field equality on everything except
`id`, with an explicit allowlist for fields the design sanctions changing
(see P1-2). Re-run Mutations A and B as the bite.

## P1-2 — the committed fixture already violates the stated invariant, undetected

The Plan (`docs/design/QPB_v1.6.0_Implementation_Plan.md:45`) says the
manifest is *"unchanged modulo the renumber map"*. It is not:

| target | records identical modulo `id` |
|---|---|
| chi | 11 / 16 |
| express | **0 / 16** |
| virtio | 8 / 17 |

Every express record changed. `requirements_manifest.json` grew 184 → 244
lines. The changes are `title` rewrites (intent-form, Design §5.4) and
`functional_section` renames/merges (Phase E.5) — e.g.
`"Cookie serialization"`, `"Redirect response shaping"`, `"JSONP callback
safety"` all collapse into `"Response construction and serialization"`; the
title `"res.cookie must not emit a Max-Age that contradicts a future
Expires"` becomes `"res.cookie Max-Age and Expires directives that agree"`.

I checked content fidelity by hand on the risky cases (express REQ-009/010/011,
where two records share `references: ['quality/patches/']`) and found **no
requirement added, dropped, merged, or weakened** — the commit message's
fidelity claim holds. So this is not a correctness bug in the fixture. It is
a **spec/implementation divergence**: §5.2 and §5.4 make Feature C
manifest-mutating in two named fields, but the Plan's invariant text says
"renumber only" and the test class asserts "same records, renumbered only".
Three statements of the invariant, none of them agreeing, and the test is
loose enough that the divergence produced no signal.

**Fix:** reconcile the wording. The honest invariant is "unchanged modulo
the renumber map, plus `title` normalization and `functional_section`
reassignment, both traceable"; then have the test enforce *exactly* that —
which will, correctly, forbid Mutation A.

This is the finding that matters most for the FP-audit dependency. The Plan
justifies landing Feature C first on the grounds that the FP-audit consumes
the manifest and "must not be perturbed". Feature C perturbs `title` and
`functional_section` on 100% of express records, and the test that was
supposed to be the safety rail cannot see it.

## P1-3 — the pre-v1.6.0 escape hatch does not protect archived runs

`quality_gate.py:6906-6911` skips the contract when `REQUIREMENTS.md` has no
`### REQ-NNN:` headings. `d8d4229`'s message asserts this prevents the check
from *"retroactively FAIL[ing] every archived run"*, and
`references/artifact_contract.md:50` states archived trees *"validate
unchanged"*. Both claims are false. The predicate is a *heading-shape* test,
not a *version* test, and the `### REQ-NNN:` shape long predates v1.6.0.

Measured: **49 archived trees** under `repos/` and `metrics/` carry
`### REQ-NNN:` headings and now run the full contract. I ran the real gate
(before-commit binary vs. current, both from the real script dir so
`_resolve_phase_identity` resolves) across all 49:

```
before=0 after=1  repos/secbench2_widenet/wn-jsts-05-defu     <<< PASS -> FAIL
before=0 after=1  repos/secbench2/sb2-06-picklescan           <<< PASS -> FAIL
```

Both flips are caused entirely by the new block. For `wn-jsts-05-defu` the
delta is `Total: 0 FAIL, 3 WARN / RESULT: GATE PASSED` →
`Total: 4 FAIL (4 substantive) / RESULT: GATE FAILED`, from: absent
`RUN_CONTRACT.md`, one section lacking intro prose, no cross-cutting section,
and no attribution stamp. `sb2-06-picklescan` is the same shape, 3 FAILs.
Neither document has any v1.6.0 obligation.

Two further observations from the same sweep:

- Legacy documents with **no** attribution stamp at all (`repos/secbench-2/rollup`,
  `repos/secbench/CASE-001-setuptools`) FAIL check 6 while passing checks 1-5.
  Check 6 fires on legacy shapes with nothing to do with C-1..C-7.
- The new FAIL class has no curated message in the 090v verdict-explanation
  layer, so operator narration degrades to
  `• [generic] (4 FAILs) ... the v1.6.x verdict-explanation expansion will add
  a curated message for this code`. Not a break, but the first new FAIL class
  since 090v landed and it lands in the generic bucket.

**Fix:** gate the contract on something that actually means "this is a
v1.6.0 render". The run metadata already carries a skill version; or gate on
the presence of the v1.6.0 architecture markers. Failing that, restrict the
retroactive surface — check 6 (stamp-absent) and the `RUN_CONTRACT.md`-absent
FAIL are the two that manufacture the flips.

## P1-4 — check 3 is bypassable by a natural section name

`quality_gate.py:6848-6853`. `_RENDER_STRUCTURAL_HEADING_RE` alternates on
`requirements?`, so any level-2 heading beginning with the word
"Requirement(s)" is classified structural and its REQs vanish from
`functional`. I verified against the live function:

```
'Requirements'             FAIL=0   (structural)
'Functional Requirements'  FAIL=2   (functional)
'Requirement'              FAIL=0   (structural)
'NFR stuff'                FAIL=0   (structural)
```

A document that puts all its REQs under `## Requirements` — an entirely
natural choice, and one the guide does not forbid — silently opts out of the
intro-prose check, the singleton-discipline check, **and** the cross-cutting-
concerns mandate, i.e. most of C-3/C-4. Because `functional` is empty the
whole `if functional:` block at `:7022` is skipped. This is the escape hatch
an LLM will find by accident.

**Fix:** anchor `requirements?` more tightly (require it to be the whole
heading and to contain no REQ headings), or invert the classification to an
explicit structural allowlist matched on the full heading.

---

## P2-1 — a PASS message asserts something the gate did not verify

`quality_gate.py:6956-6959` prints
`PASS: no tool-contract REQs in REQUIREMENTS.md (8 routed to RUN_CONTRACT.md)`
*before* the `RUN_CONTRACT.md`-presence branch at `:6961`. On both flipped
targets the gate emits exactly that line, then immediately
`RUN_CONTRACT.md: absent`. The parenthetical is a claim about routing the
check has not made. Reword to "(8 tool-contract REQ(s) in the manifest)".

## P2-2 — RUN_CONTRACT.md is enforced at Phase 6, not at the Phase 2 boundary

The decision **not** to add `RUN_CONTRACT.md` to `run_state_lib.py:730-742`
`required_fixed` is correct as stated — that tuple is unconditional and
would retroactively fail every archived Phase-2 tree. The rationale is
documented at `references/artifact_contract.md:50`, which is good practice.

But the gap is real: a v1.6.0 run whose manifest carries tool-contract REQs
and whose Phase 2 omits `RUN_CONTRACT.md` **passes Phase 2 validation** and
only dies at the Phase 6 gate. That is precisely the failure mode the
comment sitting 10 lines above `required_fixed` says was closed on purpose:

> *"Pre-fix the validator silently tolerated a Phase 2 with the markdown
> deliverables but no manifests, deferring the failure to the Phase 6 final
> gate — the same UX failure mode instruction 066 closed at Phase 1. Same
> logic applies here: phase boundaries should reject incomplete artifact
> sets at the boundary, not defer."*

The right fix is not `required_fixed`; it is a *conditional* check in the
same validator — the manifest is already in `quality_dir`, so
`_render_tool_contract_ids`-equivalent logic can run there and require
`RUN_CONTRACT.md` only when tool-contract records exist. That preserves
archived-tree compatibility and closes the deferral.

Blast radius on the runner is otherwise contained: `bin/run_playbook.py:4323-4325`
reads the `RESULT:` line and `_gate_pass` does substring matching, so a new
FAIL class does not break parsing. It does have a consequence worth naming —
`gate_passed` guards `archive_lib.archive_run(..., status="success")` at
`:4387`, so a v1.6.0 run whose *only* defect is presentational will not
archive.

## P2-3 — F-1 is scoped to the whole document but reports "in the Overview"

`quality_gate.py:7152-7159` searches all of `text`, then prints
`PASS: coverage-and-gaps statement present in the Overview`. A "not covered"
in a traceability appendix satisfies it. WARN-only, so low stakes, but the
message overstates what was checked.

---

## Charter item 3 — prompt/reference consumers: clean

Checked and found no breakage.

- `plugins/quality-playbook/skills/quality-playbook/references` is a symlink
  to repo-root `references/`, and `SKILL.md` likewise — so the four doc edits
  propagate to the plugin surface with no copy to drift.
- **SKILL.md token ceiling:** unaffected. `SKILL.md` is untouched by all
  three commits; `bin/tests/test_skill_md_size.py` bounds `SKILL.md` only,
  and the architecture detail correctly went into `references/` per the
  Phase 1 gate. (`phase2_generation_guide.md` is now 102 KB — no per-reference
  budget exists, which is a pre-existing gap, not this work's.)
- **Doc-drift guards, awesome-copilot trimmed generator, `build_channel_package.py`
  bundling:** all green in the full-suite run.
- **`phase2.md` byte-equality hash pin:** updated in `71b1a81` per its own
  change-acknowledgement contract; `bin/tests/test_phase_prompts_externalized.py`
  passes.

## Charter item 5 — test-suite health: clean

- 2485 tests, 0 failures, 13 skipped. Matches the commit messages exactly.
- **Hermetic.** Neither new module touches `repos/` (only prose mentions in
  the docstring), opens a socket, or reads the network. The one URL is a
  literal inside a fixture attribution string.
- **No tracked-file mutation.** `git status --porcelain` is empty after the
  run, and `test_fixture_files_are_not_mutated_by_the_test_run`
  (`:328-348`) pins the temp-tree staging so an in-place swap cannot be
  reintroduced. This is the right pattern and I want it noted as such.
- **Ordering-independent.** `_run_render_contract` / `_run_render_contract_on_before`
  reset `quality_gate.FAIL/WARN/_FAIL_RECORDS/_WARN_RECORDS` on entry
  (`:74-77`, `:101-104`) rather than trusting inherited state. Minor NIT:
  they leave the globals dirty on exit, so a downstream module that reads
  them without resetting would inherit; seven other test modules touch
  `quality_gate.FAIL`, all of which appear to reset on entry too, so this is
  latent rather than live.

---

## NIT

- `test_fixture_spans_three_distinct_repo_shapes` (`:130`) asserts
  `len(set(TARGETS)) == 3` — it verifies the constant has no duplicates, not
  that the shapes are distinct. Harmless, but it reads as coverage it isn't.
- `_RENDER_INTERNAL_VOCAB` (`:6839-6844`) uses bare `in text` substring
  matching; `"cluster:"` would false-positive on a legitimate sentence about,
  say, a Kubernetes cluster in a target's own domain vocabulary. Worth a word
  boundary given the contract is blocking.

---

## What would move this to SHIP

1. **P1-1 / P1-2 together.** Decide what the invariant actually is (it is not
   "renumber only" — the fixture proves it), write it down once in the Plan,
   and make `ManifestUnchangedInvariantTests` enforce that statement
   field-by-field with a record-level pairing. Mutations A and B must fail.
2. **P1-3.** Make the inertness predicate mean "pre-v1.6.0", not "no
   `### REQ-NNN:` heading" — or, at minimum, stop the two archived PASS→FAIL
   flips and correct the claims in the commit message and
   `artifact_contract.md:50`, which currently assert a protection that does
   not exist.
3. **P1-4.** Close the `## Requirements` bypass.

P2s are worth doing but do not gate. The render contract itself I judge
sound: it discriminates well across three repo shapes, the mutation-bite
coverage on the seven defect classes is real, and the F-1 WARN-never-FAIL
boundary is respected.
