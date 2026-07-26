# VERDICT: FIX-REQUIRED

Focused-panel review of instruction 002, items **1, 2, 4, 5** (item 3 has its own
panelist). Reviewer: focused panelist, 2026-07-20. Branch `1.6.0`.

Two blocking defects, both small and both in items already substantially correct.
The measurement work in item 4 and the source-verification work in item 5 are the
strongest parts of this instruction and both survived independent re-execution
without correction.

---

## Blocking

### B-1 (item 1) — a third producer surface authors the exact clause shape the rule was written to prevent, and did not get the rule

`bin/skill_derivation/prompts/pass_a_uc_section.md` is a standalone Pass A prompt
for execution-mode sections. It is not a variant of `pass_a_section.md` and does
not include it by reference — it restates the whole task from scratch. It emits
**two** record kinds, and both carry the defective field:

- REQ drafts with `"acceptance_criteria": "<testable condition>"`
- UC drafts with `"acceptance": "<what determines whether the scenario succeeded>"`

Neither carries the no-disjunctive-acceptance rule, and neither carries the
one-claim-per-REQ rule that `pass_a_section.md` already had.

This is not a hypothetical gap. **One of the five live instances the instruction
names is a UC acceptance clause**: express UC-06.b, verified verbatim at
`bin/tests/fixtures/render_contract_v160/express/quality/REQUIREMENTS.md:156`:

> UC-06.b: the same charset sent as a **Buffer** body must follow the same
> documented rule, or the divergence must be explicitly specified.

So the rule as landed cannot prevent recurrence of the second row of the very
table item 5 writes down.

This also makes a tracked document say something untrue. The header of
`docs/process/QPB_v1.6.0_Regeneration_Expectations.md` states:

> Rule that prevents recurrence: `references/phase2_generation_guide.md` §
> "One required behavior per requirement — no disjunctive acceptance", and the
> matching rule in `bin/skill_derivation/prompts/pass_a_section.md`.

For row 2 that claim does not hold. A future regeneration that reproduces
UC-06.b would be read as a prompt-rule failure when the prompt in question never
carried the rule.

I do not think this is the worker being careless. The instruction frames the
seam as "**both** producers per the OD-10 seam", and at producer granularity the
worker satisfied it exactly and said which it touched — the literal acceptance
criterion is met. The gap is intra-producer: the skill-derivation producer has
two Pass A prompts and only one was hardened. But the item's stated purpose is
prevention at source, and prevention does not reach the surface that emitted one
of the five exhibits.

**Fix:** add the rule to `pass_a_uc_section.md`, covering both `acceptance_criteria`
(REQs) and `acceptance` (UCs) — the UC field arguably needs it *more*, since
"what determines whether the scenario succeeded" is a natural invitation to
hedge. Then correct the provenance line in `QPB_v1.6.0_Regeneration_Expectations.md`
to name all three surfaces.

### B-2 (item 2) — the deleted renderer is still documented as present, in the module the worker deliberately preserved

`bin/skill_derivation/curate_requirements.py` opens:

```
"""curate_requirements.py — Phase 5 Stage 5A: curated REQUIREMENTS.md
generator.
...
  5. Render to REQUIREMENTS.md with phase-by-phase grouping using
     SKILL.md heading hierarchy.
```

Step 5 no longer exists, and the module is no longer a "REQUIREMENTS.md
generator" — `curate()` is now a pure computation returning a summary dict, which
is precisely what the commit message says it made it. The docstring was not
touched by `f1b228d`.

This is drift the commit itself created, and the worker's own stated principle
covers it: *"Leaving those as orphans would be dead code left behind by a commit
whose subject is removing dead code."* The same argument applies to a docstring
promising a render step. It is also aimed straight at the reader the worker
preserved the module for: the next person to pull B-4 reads this docstring first
and is told the module renders a document it does not render.

Scoped narrowly: the `_print_purpose` block at the bottom is *also* inaccurate
("normalizes Phase 1 requirements into the canonical schema", "imported by
skill_derivation pass A"), but it was inaccurate **before** this instruction —
pre-existing, out of scope, follow-up only.

**Fix:** drop step 5 and re-title the docstring line. One edit.

---

## Item-by-item findings

### Item 1 — no-disjunctive-acceptance rule

**Rule present and prompt-shaped: yes.** `references/phase2_generation_guide.md`,
new `#### One required behavior per requirement — no disjunctive acceptance`,
placed inside the REQ-authoring rules block immediately after the intent-form /
noun-phrase rules and immediately before the F-1 coverage-and-gaps slot. That is
where a generating agent authoring REQ text is already reading. Judged as a
prompt rather than as prose it holds up well: it enumerates four concrete
rejected shapes with a worked example each, gives the positive replacement
("state the decision procedure that selects between them"), and — the part that
matters most for a generating agent — names the escape valve, so an agent that
genuinely cannot decide has somewhere to put the uncertainty (coverage-and-gaps
statement / validation interview) other than into the requirement. Without that
clause the rule would just push the hedge into different wording.

**No mechanical gate check added: verified by execution.** `git diff --name-only
f1b228d^..1d3cbc8` shows `quality_gate.py` touched by exactly one commit in the
range, `0e75fd2` — item 3's glossary WARN, the other panelist's scope. `f8b73dc`
touches only `pass_a_section.md` and `phase2_generation_guide.md`. The commit
message's claim "quality_gate.py is untouched by this commit, which is the
verifiable form of that claim" is true.

**Over-correction risk: handled.** The guide carries the discriminating pair
explicitly — "Returns 400 or 422 depending on which validator rejected the
payload" as a *good* requirement against "rejects or clamps" as a bad one. The
distinction it draws is the right one: the good case names the selecting
condition, the bad case does not. A generating agent applying this rule as
written would not strike legitimate disjunction. The rule also states its own
rationale for not being mechanized, in-band, which forecloses a later reader
"fixing" the missing check — a genuinely good move.

**Pass A prompt placement: good, and the disambiguation is necessary.**
`pass_a_section.md` already carried a one-claim-per-REQ rule, and the new section
opens by distinguishing them ("that one says don't *merge* claims; this one says
don't leave a single claim *undecided*"). Without that sentence the two would
read as duplicates and an agent would likely apply only the first. Placement is
immediately after the testability rules and before the high-recall instruction,
which is correct — recall guidance last, so it does not override the constraint.

**Mirror surfaces: not an issue.** `references/phase2_generation_guide.md` exists
in five other locations. `.claude/`, `.github/`, `.codex/` copies are untracked
install artifacts (`git ls-files` returns nothing for them) and were already
drifted before this instruction; `quality_playbook_cli/_bundle/` is an untracked
build output and is byte-identical to `references/`. No action needed. Flagging
only so a later reviewer does not re-derive it.

**Third surface: see B-1.**

### Item 2 — deleting the dead renderer

**Deletion verified.** `_render_requirements_md` and `_section_meta` are gone;
the `curate()` call site is gone; repo-wide grep for `_render_requirements_md`
returns nothing outside the instruction text itself. The two render assertions
and the `_write_sections` helper are gone from the test. The `# QPB v1.5.3`
literal is gone.

**Module still healthy.** `from bin.skill_derivation.curate_requirements import
curate, CurateConfig` imports; `CurateConfig.__dataclass_fields__` is
`['formal_path', 'target_min', 'target_max', 'initial_k', 'jaccard_threshold',
'max_iterations']` — the two removed fields are gone and nothing else moved.

**The scope decision is defensible; I checked Design §1.3 and §7 myself rather
than taking the commit message's word.**

- §1.3 (`docs/design/QPB_v1.6.0_Design.md:51`) names the file by path and ties it
  to B-4: *"the curated QPB self-derivation settled at 171 REQs against an
  [80,110] target because `bin/skill_derivation/curate_requirements.py` caps
  per-partition but never merges across partitions (backlog B-4 …)"*.
- §7 (`:173`) makes B-4 first in line: *"B-4 first in line (its 171-REQ output is
  an at-scale readability problem and the natural next pull after Feature C
  ships)"*, restated at `:20`, `:63`, `:209`, `:222`, `:260`.

So the Design does name this module as live backlog substrate, and B-4 is the
first point-release candidate. Deleting the module would have destroyed the
subject of the next planned work item. The worker read this correctly, flagged
the ambiguity rather than resolving it silently, and preserved exactly the part
the Design cares about (the partition/dedup/K-iteration algorithm — B-4 is a
statement about that algorithm's cross-partition behavior, not about rendering).
The operator meant to delete the renderer, and the renderer is what was deleted.

**Removing the config fields broke nothing.** The `sections_path` /
`output_path` grep hits elsewhere in the repo (`divergence_internal.py`,
`divergence_execution.py`, `pass_a.py`, `pass_d.py`, `regression_replay.py`,
`visualize_calibration.py`) are all independent same-named locals and fields in
unrelated dataclasses, none reaching into `CurateConfig`.

**Stale consumers: one blocking (B-2), one follow-up.**
`ai_context/IMPROVEMENT_LOOP.md:107` still describes "the curation algorithm that
produces the bootstrap REQUIREMENTS.md (`curate_requirements.py`)". Arguably
still true of the *algorithm's purpose* rather than its code, and orientation
docs carry their own release gate (Toolkit Test Protocol), so I am not blocking
on it — follow-up F-2.

**Suite green: confirmed independently, see Cross-cutting.**

### Item 4 — the corrected figures

This is the strongest item. I re-derived every number from scratch and the
worker's account survives; where it contradicts the instruction, **the worker is
right and the instruction is wrong**.

**Before-state counts, re-measured with current code** (via
`test_render_regeneration_fixture_v160._run_render_contract_on_before`, at the
harness's current `FIXTURE_SKILL_VERSION = "1.6.0"`):

| target | FAIL | WARN |
|---|---|---|
| chi | **13** | 2 |
| express | **12** | 2 |
| virtio | **9** | 2 |

13 / 12 / 9 confirmed. The corrected table also records WARN 2 on the before
column and WARN 1 on the after column, which matches item 3's glossary check
landing.

**Delta composition — reconstructed by checking out each intervening commit and
re-running the harness against it:**

| commit | subject | chi | express | virtio |
|---|---|---|---|---|
| `edc5cec` | the regeneration fixture | 11 | 9 | 6 |
| `f9984ae` | close self-Council round 1 | 11 | **10** | **7** |
| `a95dcb5` | close self-Council round 2 | **13** | **12** | **9** |
| `3ef3a7e` | round 3 | 13 | 12 | 9 |
| `b863deb` | round 4 | 13 | 12 | 9 |
| `8db8af3` | evidence doc committed | 13 | 12 | 9 |

So the original 11 / 9 / 6 was measured at `edc5cec` and the doc was committed at
`8db8af3` — five commits and two step-changes later. The instruction's diagnosis
of *why* the figures were stale is exactly right.

**The stamp component is real, and the mechanism the worker gives is correct.**
Diffing the FAIL records for express across `edc5cec` → `f9984ae` shows exactly
one new record: `generator stamp says v1.5.8 but the skill version is v1.6.0`.
chi is unchanged across that commit and already carried a `v1.5.3` stamp FAIL at
`edc5cec` — which is C-7 itself, exactly as the worker states. The mechanism:
at `edc5cec` the harness signature was `_run_render_contract_on_before(target,
skill_version="1.5.8")`; it is now `skill_version=FIXTURE_SKILL_VERSION` (1.6.0).
The worker's sentence "round 1 measured the `.before` documents at
`skill_version=1.5.8`, where express's and virtio's stamps *matched* and passed"
is literally accurate — I confirmed it against the historical source, not the
commit message.

**The worker is right and the instruction is wrong about the chi intro-prose
FAIL.** Instruction 002 line 42 says the delta is "the MP-1 checks plus a chi
intro-prose FAIL." Verified false: chi's delta is `11 → 13`, exactly +2, both
records being `no Actors & roles section` and `no Traceability appendix section`
(the MP-1 block, landing at `a95dcb5`). The intro-prose FAIL
(`1 functional section(s) lack intro prose`) is present in chi's FAIL list at
`edc5cec` — i.e. it was already inside the original 11. It cannot be part of the
delta. The worker contradicting the instruction here was correct, and correct to
say so in the record rather than quietly conform.

**Full composition, independently confirmed:**

```
chi      11 +2 MP-1            = 13
express   9 +2 MP-1  +1 stamp  = 12
virtio    6 +2 MP-1  +1 stamp  =  9
```

**Both files corrected.** `runner/quality-playbook/outputs/001-fr-c-spec-organization.md:100`
now reads `13 FAIL → 0 / 12 FAIL → 0 / 9 FAIL → 0`, and
`docs/process/QPB_v1.6.0_Instruction_001_Self_Council/evidence_c1_c7_before_after.md`
carries the corrected table plus a provenance section. The commit-count line was
handled by replacing the count with a range statement rather than another number,
which is the right shape — a second transcribed count would rot the same way.

**Sequencing reasoning was correct.** Item 3 moves the before-fixture WARN column
1 → 2 and the after-fixture column 0 → 1. Had item 4 run first, the WARN figures
in both corrected files would have gone stale *within the same instruction* —
which is the exact failure class being corrected. Measuring after `0e75fd2` was
right. (One caveat: the FAIL counts would not have changed, only WARN. The
reasoning is sound but the blast radius was narrower than stated.)

**One factual slip, non-blocking (F-1 below):** the evidence doc says "MP-1 is
the §5.2 mandatory-part block added in self-Council **round 3**." It landed at
`a95dcb5`, whose subject is "close the self-Council findings (**round 2**)".

### Item 5 — the regeneration expectations doc

`docs/process/QPB_v1.6.0_Regeneration_Expectations.md`, 249 lines, tracked at
`1d3cbc8`.

**All five clauses covered.** Read against Finding 2 of the Council synthesis
(`~/Documents/AI-Driven Development/Quality Playbook/Reviews/QPB_v1.6.0_Slice1_Readability_Council_Synthesis.md:17-33`),
the doc's five sections map one-to-one onto the synthesis's five-row table
(chi REQ-002; express REQ-005/UC-06.b; express REQ-003; virtio REQ-005 item 5;
virtio REQ-009). The synthesis's *secondary* items (para 33) are also carried, in
a clearly-separated "Secondary items" section — good, since they are not
disjunctive-acceptance defects and merging them would have blurred the file's
purpose.

**Every "current text" quotation verified against the actual fixture. All five
are accurate**, differing from the fixture only in line-wrapping and added bold:

| # | claimed location | verified |
|---|---|---|
| 1 | chi REQ-002 | `chi/quality/REQUIREMENTS.md:122` ✓ |
| 2 | express UC-06.b | `express/quality/REQUIREMENTS.md:156` ✓ |
| 3 | express REQ-003 | `express/quality/REQUIREMENTS.md:125` ✓ |
| 4 | virtio REQ-005 item 5 | `virtio/quality/REQUIREMENTS.md:187-188` ✓ |
| 5 | virtio REQ-009 | `virtio/quality/REQUIREMENTS.md:245-246` ✓ |

This was the check most likely to catch a doc that sends a future regeneration
chasing a clause that does not exist. It does not.

**The fabrication risk — the item's highest-risk failure mode — was found by the
worker and is now source-verified.** The doc states outright that its own first
draft asserted two code facts it had not checked (that express's JSONP guard
rejects chains; that virtio clamps oversize queues), that both were wrong, and
that both were corrected against source. I re-checked every remaining source
claim independently:

- `repos/express-1.5.8/lib/response.js` — `case 'string'` at `:135`, the
  `setCharset(type, 'utf-8')` rewrite at `:140` ✓. The `ArrayBuffer.isView`
  (Buffer) branch at `:150-153` calls `this.type('bin')` and never calls
  `setCharset` ✓, so "an explicitly-set charset survives" is correct.
- `response.js:286` — `callback = callback.replace(/[^\[\]\w$.]/g, '')` ✓. It
  sanitizes in place and does not reject; `.`, `[`, `]` are in the permitted set,
  so member access is allowed by design ✓. `:300` wraps in
  `'/**/ typeof ' + callback + " === 'function' && " + callback + '(' + body + ');'`
  ✓; nosniff and `text/javascript` set at `:282-283` ✓.
- `repos/virtio-1.5.8/drivers/virtio/virtio_ring.c:3342-3343` — `if (num >
  vq->vq.num_max) return -E2BIG;` ✓ (reject, not clamp).
- `virtio_ring.c:1262-1270` — the `num /= 2` loop is gated on
  `vring_size(num, vring_align) > PAGE_SIZE` and returns `-ENOMEM` when
  `!may_reduce_num` ✓. The doc's claim that this is allocation pressure and not
  the device-advertised maximum is correct, and the observation that the REQ
  conflates two different conditions is a genuinely good catch that goes beyond
  what the Council supplied.

Every citation checks out. **No invented technical facts remain.** The
three-tier provenance labelling (Council-supplied / Source-verified / Open
question) is the right structural response to having made that mistake once, and
is more valuable than the corrections themselves.

**Fidelity to the Council.** Where the Council supplied fixes (synthesis:31 —
"commit to a behavior in express REQ-005 UC-06.b; state express REQ-003's
callback grammar as prose; choose reject-or-clamp in virtio REQ-009") the doc
attributes them inline and follows them. For chi REQ-002 and virtio REQ-005
item 5 the Council supplied no fix; the doc's forms are minimal — strike the
escape clause, keep the behavior — and both route the intent question to the
validation interview rather than guessing. That is the defensible choice.

On express REQ-003 the worker goes past the Council: the Council said "state the
grammar", the worker states the grammar *and* determines from source that the
guard sanitizes rather than rejects — then explicitly declines to decide whether
permitting member-access chains is the intended contract or a latent defect,
routing that to the operator. Exactly the right line between what source can
settle and what it cannot.

**"Not fixture edits" stated plainly enough: yes.** It is the first section under
the title, bolded (*"These are expectations for a future regenerated run. They
are NOT edits to the fixtures."*), it names the three fixture paths explicitly,
it gives the reason (the oracle would become a test of hand-written exemplars no
pipeline generates), and the check-a-regenerated-run procedure closes with "Do
not resolve it by editing the regenerated document." Restated a third time in
the "Why this file is" paragraph. A reader would have to work at
misunderstanding it.

---

## Cross-cutting

**Full suite: 2551 tests, `OK (skipped=13)`, 92s. Python 3.14.6.** Green.

**A transient RED that is not a defect — recorded so it is not re-discovered.**
My first suite run reported `Ran 2551 tests / FAILED (failures=1, skipped=14)`,
the failure being `test_render_contract_v160` asserting the glossary block has no
`fail()` path, with the block text showing `fail("REQUIREMENTS.md", "has no
glossary…")`. Investigated rather than reported: no copy of `quality_gate.py`
anywhere in the tree contains that text; the committed (`0e75fd2`) and working
versions both read `warn(`; `pgrep` showed a **concurrent** pytest process
running from a peer agent's working copy. This was the item-3 panelist's
revert→fail→restore mutation bite racing my full-suite run. Re-run with a
`shasum` taken before and after confirmed `quality_gate.py` byte-identical across
the run and the suite green. **Two agents sharing one working tree while one runs
source-mutation bites will produce phantom failures in the other's suite** — a
process note for the orchestrator, not a defect in this work.

**Fixture constraint honored.** `git diff --name-only f1b228d^..1d3cbc8` contains
no path under `bin/tests/fixtures/render_contract_v160/*/quality/REQUIREMENTS.md`.
The only fixture-adjacent files touched are the two *test* modules
(`test_render_contract_v160.py`, `test_render_regeneration_fixture_v160.py`), both
in item 3's commit. **No fixture document was hand-edited.** The standing
constraint holds.

**Tree state.** `git status --porcelain` shows `docs/design/QPB_v1.6.0_Design.md`
and `docs/design/QPB_v1.6.0_Requirements_Readability_Rubric.md` modified, plus the
untracked instruction file. None of these are instruction-002 work products — the
rubric edit is Council synthesis Finding 3's Complete/Honest fix, which the
synthesis assigns to the *orchestrator*, and the instruction file is the
operator's. Not this worker's to commit. No stray artifacts from items 1/2/4/5.

**Nothing pushed, nothing merged.** Branch is `1.6.0`. Commit policy honored.

**Where the instruction itself is wrong** (worth carrying into the output doc):
line 42's attribution of part of the delta to "a chi intro-prose FAIL" is false,
as established above. The worker caught it and said so; that should be visible in
`outputs/002-render-contract-hardening.md`, not only in a commit message.

---

## Non-blocking follow-ups

- **F-1.** `evidence_c1_c7_before_after.md` says MP-1 "added in self-Council round
  3"; it landed at `a95dcb5` = round 2. One-word fix in a tracked historical
  record, worth making since the whole point of that section is provenance.
- **F-2.** `ai_context/IMPROVEMENT_LOOP.md:107` still describes
  `curate_requirements.py` as producing the bootstrap REQUIREMENTS.md. Defensible
  as a statement about the algorithm's purpose; orientation docs have their own
  release gate (Toolkit Test Protocol), so route it there rather than here.
- **F-3.** The `_print_purpose` block in `curate_requirements.py` ("normalizes
  Phase 1 requirements into the canonical schema", "imported by skill_derivation
  pass A") is inaccurate and was already inaccurate before instruction 002.
  Pre-existing; fold into B-4 when that module is next opened. Same for the
  unused `from typing import Optional`, which the worker correctly identified and
  correctly left alone.
- **F-4.** Item 4's sequencing note slightly overstates its case — item 3 moves
  only the WARN column, not the FAIL counts. The conclusion (measure last) is
  right; the stated blast radius is wider than the facts.
- **F-5.** `pass_a_uc_section.md` also lacks the pre-existing one-claim-per-REQ
  rule that `pass_a_section.md` carries. Out of scope for instruction 002, but the
  two prompts having divergent authoring rules is the underlying condition that
  produced B-1, and it will produce the next one too.

---

## Summary

Items 4 and 5 are excellent and survive independent re-execution intact — item 4's
figures reproduce exactly, its delta decomposition is correct commit-by-commit, and
its contradiction of the instruction is the worker being right. Item 5's
quotations are all accurate against the fixtures and every source citation checks
out, including the two it had to correct itself on. Item 2's scope reasoning is
sound and I verified the Design sections it rests on rather than accepting the
commit message. Item 1's rule is well-written and the no-gate-check discipline was
kept.

FIX-REQUIRED rests on two items: a producer surface that emits one of the five
documented exhibits and did not get the rule (B-1, which also makes a tracked
document's provenance claim untrue), and a docstring left describing the renderer
the commit deleted (B-2). Both are small. Neither undermines the rest of the work.
