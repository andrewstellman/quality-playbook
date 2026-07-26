# VERDICT: SHIP

Round-2 closure panel over `0f7cc0a`. Charter: verify only what round 1 left
open. Reviewer: round-2 closure panelist, 2026-07-20. Branch `1.6.0`,
HEAD `0f7cc0a` confirmed.

Both blocking findings are genuinely closed, every factual claim in the commit
message reproduces, and no new defect is reachable. Six non-blocking follow-ups
below, one of them new.

---

## 1. B-1 — the missed third prompt: CLOSED

**Rule present.** `bin/skill_derivation/prompts/pass_a_uc_section.md:77`,
`## One required behavior per acceptance clause — no disjunction`.

**Governs both field shapes, explicitly.** First line of the section:
"Applies to **both** `acceptance_criteria` on REQs and `acceptance` on UCs."
That is the exact form B-1 asked for, and it names the reason (express UC-06.b)
in-band so a later editor cannot strip it as boilerplate.

**Placement is correct — arguably better than the REQ prompt's.** Section order
is `Section under review` → `Adjacent context` → `Your task — TWO record kinds`
(REQ drafts / UC drafts) → `Output rules` → **the new rule** → `## Begin`. It is
the last constraint an LLM reads before the emit instruction, after both record
schemas have been introduced. A generating agent cannot reach `Begin` without
passing it.

**Both prompts are live producers — verified at the call site, not assumed.**
`bin/skill_derivation/__main__.py:313-314` loads them as
`req_template_path=…/pass_a_section.md` and
`uc_template_path=…/pass_a_uc_section.md`. Both are real inputs to Pass A.

### The fourth-surface search

Exhaustive, and it comes back clean at the prompt level.

- `find` for any directory named `prompts`: exactly one,
  `bin/skill_derivation/prompts/`. It contains exactly two files, both of which
  now carry the rule (`grep -c acceptance` → 5 and 8).
- Repo-wide grep for `acceptance_criteria` / `acceptance` across `*.md`,
  `*.py`, `*.txt`, `*.json` (excluding `repos/`, `docs_gathered/`,
  `__pycache__`) returns ~100 files. Every hit falls into one of: generated
  fixtures/artifacts, tests, historical design and process docs, harness plans,
  or the three surfaces already carrying the rule. None of them *authors* REQ or
  UC acceptance text.
- Grep for `disjunctive|One required behavior` confirms exactly three
  authoring surfaces carry the rule: `references/phase2_generation_guide.md:164`,
  `pass_a_section.md:48`, `pass_a_uc_section.md:77` — plus the instruction and
  the expectations doc, which reference it rather than carrying it.

**One near-miss I chased and cleared** (follow-up FU-B, not blocking).
`references/requirements_pipeline.md:107` (step B.3, "Write requirements …
Conditions of satisfaction come from the individual contracts") and
`references/phase1_exploration_guide.md:463` (the 7-field template's definition
of the Conditions-of-satisfaction field) are the two places on the *live-skill*
side where acceptance text is actually written, and neither carries the rule.
I do not treat this as a fourth B-1 for a structural reason: those are not
standalone LLM prompts. `phase_prompts/phase2.md:9` instructs the Phase 2 agent
to read `references/phase2_generation_guide.md` end-to-end **before generating
any artifacts**, and `requirements_pipeline.md:310` sends the reader back to the
render-contract section before Phase E. The rule is in the same context window
as the authoring step. That is materially different from `pass_a_uc_section.md`,
which *is* the entire context of one LLM call — which is precisely why B-1 was
blocking and this is not.

## 2. B-2 — the stale docstring: CLOSED

`curate_requirements.py:1` now reads "Phase 5 Stage 5A: requirements curation",
states plainly that it "does **not** render a document", records why the
renderer went (hardcoded `QPB v1.5.3`, the C-7 class, dead), why the algorithm
stayed (Design §1.3 / §7, B-4 backlog substrate), and replaces step 5 with the
actual return contract. That is more than B-2 asked for and it is aimed at
exactly the reader the module was preserved for.

**Sweep for other surfaces describing the deleted renderer.** Repo-wide grep for
`curate_requirements|_render_requirements_md` outside `repos/`, `docs_gathered/`
and `__pycache__` returns:

| hit | status |
|---|---|
| `curate_requirements.py:1` | fixed |
| `curate_requirements.py:236` `_print_purpose` | inaccurate, **pre-existing** (round 1's F-3) — FU-C |
| `bin/tests/test_curate_requirements.py:1` | "Phase 5 Stage 5A REQUIREMENTS.md curation" — imprecise, not renderer-describing — FU-D |
| `docs/design/QPB_v1.6.0_Design.md:51` | accurate (names the *algorithm*, which survives) |
| `ai_context/IMPROVEMENT_LOOP.md:107` | round 1's F-2, unchanged — FU-E |
| `runner/…/instructions/002-…md:29`, `runner/…/outputs/001-…md:188,310` | historical records correctly describing the pre-deletion state |

No `docs/`, `references/`, or README surface still claims the renderer exists.
The `__main__` purpose banner is the only remaining inaccuracy in the module and
it was inaccurate before instruction 002 touched it — correctly scoped out.

## 3. The `terms` regex change: verified in all four directions

Diff at `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py:6884`
drops bare `terms` from `_RENDER_STRUCTURAL_HEADING_RE`. Glossary detection
(`:7703`) keeps its own broader pattern, `terms(\s|$)`, unchanged.

**(a) A functional section named `Terms` now gets the checks — confirmed by
execution.** Built a synthetic document from the test module's hand-written
`_clean_requirements_md()`, renamed `## Error handling` to `## Terms` and
stripped its intro prose. `check_render_contract` emits:

```
REQUIREMENTS.md: 1 functional section(s) lack intro prose stating the
section's contract theme: 'Terms' (v1.6.0 Design §5.2 item 4).
```

Direct call to `_render_classify_sections` on the same document returns
`['Request routing', 'Terms']` — `Terms` is now classified functional. Before
the change it was silently skipped. The claimed bypass was real and is gone.

**(b) A `## Terms` glossary is still detected — confirmed, no regression to item
3's acceptance.** Same document with `## Glossary` renamed to `## Terms`: gate
output is all-PASS, zero FAIL, zero WARN, including
`PASS: glossary/definitions section present`. The section holds no REQs, so
`_render_classify_sections` skips it before the regex is ever consulted, and the
glossary matcher finds it on the `terms(\s|$)` alternative. Control case (no
glossary at all) produces exactly one WARN and zero FAIL, so the check is live
and the pass is not vacuous.

**(c) Three fixtures still FAIL=0 WARN=1.** Ran `check_render_contract` directly
against `bin/tests/fixtures/render_contract_v160/{chi,express,virtio}/quality`
at `skill_version=1.6.0`: all three report FAIL 0 / WARN 1. Item 3's stated
acceptance holds.

**(d) No archived tree can flip.** `find` over every `REQUIREMENTS*.md` in the
repo *including* `repos/` and `metrics/`, grepped for `^## Terms` or
`^## Definitions`: zero hits. No document anywhere in the tree uses either
heading at level 2, so the exit-code surface of the change is empty outside the
synthetic cases above. The 94 tests in `test_render_contract_v160.py` +
`test_render_regeneration_fixture_v160.py` pass.

**`Definitions` — the bypass does remain, and I am recording it as a follow-up
rather than a block.** Same probe with `## Definitions` as the REQ-holding,
intro-prose-less functional section: `_render_classify_sections` returns
`['Request routing']` only, and the gate reports zero non-PASS lines. The
identical defect-to-pass bypass the worker just closed for `terms` is still open
for `definitions`.

I judge leaving it defensible, narrowly. `Definitions` is a canonical IEEE 830
§1.3 structural part name; `Terms` is a common *domain* noun that a real
functional section could plausibly carry (contract terms, payment terms, search
terms). The risk asymmetry is real and the worker's line is on the right side of
it. But the residual is the same shape, and it is worth stating that the fix is
asymmetric by judgment rather than complete — see FU-A. (Note this property is
structural, not specific to `Definitions`: `Overview`, `Use cases` and the rest
behave the same way. The code comment at `:7242-7247` shows the author knew, and
the "functional ends up empty → its own FAIL" backstop only fires when *all*
REQs are parked structurally.)

## 4. The factual corrections: both accurate

**MP-1 at `a95dcb5`.** `git log -S'Actors & roles' -- …/quality_gate.py` returns
exactly one commit: `a95dcb5 v1.6.0 [Phase 2]: close the self-Council findings
(round 2)`. The subject itself says round 2. `evidence_c1_c7_before_after.md`
now reads "added at `a95dcb5` (self-Council round 2 … not round 3, as an earlier
draft of this note said)" — correct, and correct to leave the trace of the
correction in a provenance record.

**The item-5 provenance line.** `QPB_v1.6.0_Regeneration_Expectations.md:5-11`
now names `phase2_generation_guide.md` plus "**both** skill-derivation Pass A
prompts — `pass_a_section.md` and `pass_a_uc_section.md`", and states why the UC
half is load-bearing for row 2. Every named surface verified to carry the rule.
The claim is now true for all five rows.

## 5. No regressions

- **Full suite: `Ran 2551 tests in 88.9s`, `OK (skipped=13)`.** Python 3.14.
  Matches the commit message's claim exactly. One aborted first attempt (`python`
  not on PATH, exit before collection) — not a failure.
- **Fixture documents unedited.** `git diff --name-only f1b228d^..0f7cc0a`
  contains **no path under `bin/tests/fixtures/render_contract_v160/`** at all.
  Also checked commit-by-commit across all seven instruction-002 commits
  (`f1b228d`, `f8b73dc`, `0e75fd2`, `a59e5c6`, `1d3cbc8`, `64b48c8`, `0f7cc0a`):
  zero fixture `REQUIREMENTS.md` files touched by any of them. The standing
  constraint holds absolutely.
- **Tree clean.** `git status --porcelain` at the end is byte-identical to the
  start: `docs/design/QPB_v1.6.0_Design.md` and
  `docs/design/QPB_v1.6.0_Requirements_Readability_Rubric.md` modified (the
  orchestrator's Council-synthesis Finding 3 work, not this worker's), plus the
  operator's untracked instruction file. I ran **no source-mutation bites** —
  every directional check above was done on synthetic documents in a tmpdir, so
  no snapshot/restore was needed and no phantom failure could have been injected
  into a peer agent's suite run. My own suite run was clean on the first
  completed attempt.
- Nothing pushed, nothing merged.

## 6. Honesty check on the commit message's correction-of-record: the correction is accurate

`0f7cc0a` states that `0e75fd2`'s explanation inverted the mechanism, because
`_render_classify_sections` skips REQ-free sections *before* consulting the
structural regex. Read the function at
`quality_gate.py:7226-7249`:

```python
for idx, (heading, off) in enumerate(level2):
    body = text[off: bounds[idx + 1]]
    has_reqs = bool(_RENDER_REQ_HEADING_RE.search(body))
    if not has_reqs:
        continue
    if _RENDER_STRUCTURAL_HEADING_RE.match(heading):
        continue
    functional.append((heading, off))
```

The `has_reqs` guard is unconditionally first. An ordinary REQ-free glossary
never reaches the regex, so it was never at risk of being counted as a
REQ-less functional section. The widening only matters for a glossary that
*contains* REQs. The item-3 panelist was right, `0e75fd2`'s message was wrong,
and `0f7cc0a`'s correction of it is exactly right — including the judgment that
the *code* was correct and only the explanation was not. Confirmed independently
by execution in §3(b): the `## Terms` glossary is skipped at the `has_reqs`
guard.

I also confirm the rest of the commit message reproduces: "2551 tests / 0
failures" ✓, "three fixtures still FAIL=0 WARN=1" ✓, "fixture documents still
unedited" ✓, "Verified both directions: the bypass now FAILs, and a Terms-headed
glossary still passes clean" ✓ (both reproduced above). I found no false claim
in this commit message.

---

## Non-blocking follow-ups

- **FU-A (new).** `definitions` remains in `_RENDER_STRUCTURAL_HEADING_RE` and
  carries the identical defect-to-pass bypass just closed for `terms` — verified
  by execution, not inferred. Defensible on risk asymmetry (canonical §1.3 part
  name vs. plausible domain noun), but the fix is asymmetric by judgment, not
  complete. Worth one sentence in the code comment at `:6877` so the next reader
  does not re-derive this, or re-widen it.
- **FU-B (new).** `references/requirements_pipeline.md:107` (step B.3) and
  `references/phase1_exploration_guide.md:463` (the 7-field template's
  Conditions-of-satisfaction definition) are where live-skill acceptance text is
  actually authored, and neither carries the no-disjunction rule. Not blocking —
  the same agent is instructed to read `phase2_generation_guide.md` end-to-end
  first — but a one-line pointer from B.3 to the rule would close the last gap
  between "the rule exists in the run's context" and "the rule is at the
  keystroke."
- **FU-C.** `curate_requirements.py:236` `_print_purpose` still says "normalizes
  Phase 1 requirements into the canonical schema" / "Imported by
  skill_derivation pass A". Pre-existing (round 1's F-3), unchanged, correctly
  out of scope. Fold into B-4.
- **FU-D (new, trivial).** `bin/tests/test_curate_requirements.py:1` still reads
  "Phase 5 Stage 5A REQUIREMENTS.md curation". Not false — it is curation for
  REQUIREMENTS.md — but it reads as a renderer reference next to the corrected
  module docstring. One word.
- **FU-E.** `ai_context/IMPROVEMENT_LOOP.md:107` unchanged (round 1's F-2).
  Correctly routed to the Toolkit Test Protocol release gate rather than here.
- **FU-F.** Round 1's F-5 stands: `pass_a_uc_section.md` still lacks the
  *one-claim-per-REQ* rule that `pass_a_section.md:48` carries. The new section
  covers non-disjunction only. Explicitly out of instruction 002's scope, but it
  is the same divergent-authoring-rules condition that produced B-1, and it will
  produce the next one.

---

## Summary

B-1 is closed at the right surface, in the right place in the prompt, with the
both-fields scope stated explicitly and the reason cited in-band; and the
fourth-surface search comes back empty at the prompt level, with the one
near-miss cleared on a structural argument (standalone LLM context vs.
same-context reference read) rather than on assumption. B-2 is closed with more
than was asked, and the sweep finds no other surface claiming the renderer
exists. The `terms` change is correct in both directions — verified by
execution, including the negative control — with the three fixtures unmoved and
no document in the tree able to flip. Both factual corrections reproduce exactly
against `git log -S` and the source. The suite is green at 2551, no fixture
document was touched by any of the seven commits, and the tree is as I found it.

The correction-of-record in §6 is the part I most expected to find overstated,
and it is not: the code reads exactly as the correction says, and the worker
correctly separated "the code was right" from "the explanation was wrong"
instead of quietly editing either.

Nothing remaining is blocking. SHIP.
