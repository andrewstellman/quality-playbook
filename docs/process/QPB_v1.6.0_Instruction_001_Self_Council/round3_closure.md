VERDICT: FIX-REQUIRED

# Round-3 closure audit — self-Council verification of `a95dcb5`

**Scope:** commit `a95dcb5` ("close the self-Council findings (round 2)") against the single blocking
finding B-1, the three regressions (R-1..R-3) and the two test weaknesses that
`round2_verification.md` left open. Branch `1.6.0`, repo `/Users/andrewstellman/Documents/QPB`.
Per charter I did not re-litigate anything round 2 marked CLOSED.

**Method:** everything below was executed. I built an independent probe harness driving
`check_render_contract` over synthesized trees (22 documents), mutation-bit the two new blocking
checks by deleting them from `quality_gate.py` and running the full 2521-test suite against each
mutant (pristine snapshot + `shutil.copy2` restore, scoped `__pycache__` purge, tree verified clean
after each), gutted all ten methods of `ManifestUnchangedInvariantTests` to test the re-written
bites, staged seven fresh manifest mutations, and swept all 105 archived trees under `repos/` and
`metrics/` across four builds (`39cc939`, `d8d4229`, `f9984ae`, `a95dcb5`) via git worktrees.

**Headline:** the *behavior* fixes in `a95dcb5` are real and good — all four bypass shapes round 2
demonstrated now FAIL, and R-1, R-2 and R-3 are genuinely closed with working controls. But the
*test* half of B-1 was not done at all, and the commit message states that it was. `a95dcb5` never
touched `bin/tests/test_render_contract_v160.py`. The coincidentally-green test round 2 identified
by name is still coincidentally green, and both new blocking checks — the B-1 guard and the three
mandatory-part checks — can be deleted outright with the entire 2521-test suite still passing. I
also found a fifth bypass that reopens B-1 through a different route.

---

## Summary table

| Round-2 item | Status |
|---|---|
| **B-1 behavior** — four demonstrated bypass shapes now FAIL | **CLOSED** (all four verified) |
| **B-1 test** — re-point the flat-shape bite at an intro-prose fixture | **NOT DONE — BLOCKING** |
| **B-1 fifth shape** — fenced-heading route | **NEW, BLOCKING** |
| New mandatory-part checks (Actors / Use cases / Traceability) | **NO BITE — BLOCKING** |
| R-1 `\bPass [A-E]\b` over-fires | **CLOSED** (bite-verified controls) |
| R-2 `## Coverage and gaps` WARNs on F-1 | **CLOSED** |
| R-3 inline-code false positive | **CLOSED** (Panelist A's exact case) |
| `ManifestInvariantMutationTests` was vacuous | **CLOSED** (gut-verified) |
| Mutations C and D genuinely detected | **CLOSED** |
| Mutation E still passing the allowlist | **FOUND — P2** |
| Three regenerated fixtures FAIL=0 WARN=0 | **CONFIRMED** |
| Full suite green, tree clean | **CONFIRMED** (2521 tests, OK, 13 skipped) |
| Stale docstrings corrected | **CONFIRMED** (both) |

---

## BLOCKING — B-2. The re-pointed regression test was never re-pointed

The commit message of `a95dcb5` says, in the paragraph closing B-1:

> "The bite is re-pointed at a fixture WITH intro prose so it fails before the fix and passes after."

**This did not happen.** `a95dcb5` changed exactly two files:

```
bin/tests/test_render_regeneration_fixture_v160.py
plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py
```

`bin/tests/test_render_contract_v160.py` — the file that holds
`test_flat_requirements_heading_cannot_bypass_section_discipline`
(`RenderContractFalsePositiveTests`, :638) — was not touched. Its fixture still has **no intro
prose** under `## Requirements`, exactly as round 2 described it.

### Bite, executed

Snapshotted `quality_gate.py`, deleted the entire new `if not functional:` FAIL block — the whole
of Panelist A's part (b), the centerpiece of this commit — purged `__pycache__`, and re-ran:

```
$ python3 -m unittest test_render_contract_v160.RenderContractFalsePositiveTests\
      .test_flat_requirements_heading_cannot_bypass_section_discipline
Ran 1 test in 0.003s
OK
```

Still green. Then the whole suite against the same mutant:

```
Ran 2521 tests in 92.475s
OK (skipped=14)
```

**The entire 2521-test suite passes with the B-1 fix removed.** Restored from the pristine snapshot;
test re-verified green, `git status --porcelain` empty.

This is precisely the state round 2 called "the worst combination, because it will read as coverage
to the next reader" — and it is now worse than round 2 found it, because the commit message asserts
it was fixed. A future reader has both a green test and an explicit commit-message claim telling them
the flat-shape bypass is pinned. Neither is true.

**Required:** re-point the test at a fixture whose `## Requirements` section carries ≥40 characters
of intro prose (the threshold `section_intro_ok` uses), and verify it is red with the guard removed
before calling it done.

## BLOCKING — B-3. The three new mandatory-part checks have no bite at all

`a95dcb5` adds three new **blocking, unconditional** FAILs (`quality_gate.py`:7206-7222):

```python
for label, pattern in (
    ("Actors & roles", r"^actors?\b"),
    ("Use cases", r"^use\s*cases?\b"),
    ("Traceability appendix", r"^traceability\b"),
):
```

I replaced that tuple with `()` — deleting all three checks — and ran:

```
Ran 2521 tests in 95.479s
OK (skipped=14)
```

Green. `grep -rn "Actors & roles\|Traceability appendix section\|Use cases section" bin/tests/`
returns **nothing**: there is no test anywhere that asserts any of the three fire. They pass today
only because the hand-built `_clean_requirements_md()` fixture happens to contain all three
sections, so the clean-document baseline exercises the PASS branch and nothing exercises the FAIL
branch. Restored and re-verified.

This is a new instance of the same defect class round 2 flagged in
`ManifestInvariantMutationTests`, introduced by the commit that fixed it. Every other check in this
module is paired with a `_fires` mutation test and a row in `RENDER_CONTRACT_AUDIT`; these three
have neither, and the AUDIT size guard did not catch the omission because no row was added.

**Required:** one `_fires` test per mandatory part (delete the section, assert FAIL and assert the
message names the part), plus the corresponding `RENDER_CONTRACT_AUDIT` rows.

## BLOCKING — B-4. A fifth bypass: level-2 headings inside fenced code blocks

The charter asked me to try hard to find a fifth shape. I found one, and it reopens B-1 completely.

`_render_scan_internals` blanks fenced code blocks before scanning (correctly — that is the R-3
fix). But `_RENDER_LEVEL2_RE` at :7187 is applied to the **raw** text:

```python
level2 = [(m.group(1).strip(), m.start()) for m in _RENDER_LEVEL2_RE.finditer(text)]
```

So a `##` line inside a code fence is counted as a real level-2 heading. It satisfies the
mandatory-part checks, and — because `_render_classify_sections` then finds REQ headings in the
body that follows it — it **synthesizes a functional section**, which is exactly the condition
`if not functional:` was added to catch.

### Demonstrated

A document with a flat, undifferentiated REQ list, no actors, no use cases, no traceability
appendix, and no section structure whatsoever — plus one four-line code fence:

````markdown
# Requirements — testproj
> Generated by [Quality Playbook](…) v1.6.0 — Andrew Stellman

## Overview

testproj is a routing library. Coverage and known gaps: it did not cover
the template subsystem, which was skimmed but produced no requirements.

```markdown
## Actors and roles
## Use cases
## Traceability appendix
## Request routing
```

This section lists every requirement derived for testproj, in the order the
derivation produced them. No further organization was attempted here at all.

### REQ-001: A contract about routing
### REQ-002: B contract about errors
### REQ-003: C contract about cookies
### REQ-004: D contract about redirects
````

→ **`FAIL=0 WARN=0`**, thirteen PASS lines including all four of:

```
PASS: Actors & roles section present
PASS: Use cases section present
PASS: Traceability appendix section present
PASS: all 1 functional section(s) carry intro prose
```

The entire §5.2 architecture that `a95dcb5` was written to enforce is satisfied by four lines inside
one code fence. A single fenced block containing any `## Anything` line is enough on its own to
defeat the `functional == []` guard.

I rate this blocking rather than P2 (where round 2 put the analogous R-3 fence-abuse) for three
reasons: it needs no deliberate evasion beyond a fence that a markdown-, docs- or template-oriented
target would plausibly emit; it defeats the newly-added checks that are the substance of this
commit, not a pre-existing advisory; and the fix is one line — run `_RENDER_FENCE_RE.sub(blank, …)`
before `_RENDER_LEVEL2_RE.finditer`, as `_render_scan_internals` already does. The asymmetry between
the two call sites in the same file is itself the bug.

I checked the false-positive direction: a conforming document that quotes a fenced markdown example
inside its Overview still scores FAIL=0, so blanking fences here does not introduce an over-fire.

### The four round-2 shapes, and eighteen further probes

All four shapes round 2 demonstrated now FAIL — confirmed by execution:

| Shape | round 2 | a95dcb5 |
|---|---|---|
| flat `## Requirements` **with** intro prose | FAIL=0 WARN=0 | **FAIL=4** |
| all REQs parked under `## Overview` | FAIL=0 WARN=0 | **FAIL=4** |
| REQs above the first `##`, token `## Overview` after | FAIL=0 | **FAIL=4** |
| setext `Requirements\n------------` | FAIL=0 WARN=0 | **FAIL=4** |

Re-run with all three mandatory parts present, so the only remaining FAIL is the B-1 guard itself,
each still scores **FAIL=1** — the guard is doing the work, not the mandatory-part checks. Also
FAILing correctly: `<h2>Requirements</h2>`, `##Requirements` (no space), `## Requirements   `
(trailing whitespace), a unicode-lookalike heading, CRLF line endings, `## Requirements (all)`,
`## Non-functional requirements`, 4-space-indented headings, and REQ headings placed inside a fence.
`## Use cases`, `## Cross-cutting concerns` and `## Traceability appendix` each holding all the REQs
correctly FAIL, so the structural-part-holding-REQs guard works as designed. A document with exactly
one legitimate functional section correctly scores FAIL=0 — no over-fire there.

Only the fenced-heading route gets through.

---

## Verified closures

### R-1 — `\bPass [A-E]\b` over-firing: **CLOSED**

Round 2's exact probe now passes, and the narrowed patterns still catch the real leak:

| Probe | Result |
|---|---|
| `### REQ-002: Pass A collects tokens before Pass B resolves them` | **FAIL=0** — closed |
| prose "the Pass C optimizer runs last" | **FAIL=0** — closed |
| control: "derivation Pass A produced this" | FAIL=1 — still caught |
| control: "Pass A/C disposition applied" | FAIL=1 — still caught |
| control: "narrative pass rewrote this" | FAIL=1 — still caught |

The fix narrows to the forms the pipeline actually emits rather than deleting the check, which is
the right shape — the controls prove it retained its discriminating power.

### R-2 — F-1 scoping: **CLOSED**

A document whose gaps statement lives under a dedicated `## Coverage and gaps` level-2 heading now
scores **FAIL=0 WARN=0** and prints `PASS: coverage-and-gaps statement present in the Overview`.
`_render_overview_body` was widened to collect `coverage…` / `known gaps` sections alongside
Overview. The preamble placement round 2 also mentioned still WARNs, but round 2 required only the
dedicated-heading case and rated the rest advisory; I agree.

*(Cosmetic: the PASS message says "present in the Overview" even when the statement was found in a
separate `## Coverage and gaps` section. Harmless, mildly misleading.)*

### R-3 — inline-code false positive: **CLOSED**

Panelist A's exact case:

```
- Conditions: `<!-- keep -->` survives minification
```
→ **FAIL=0**. `_RENDER_INLINE_CODE_RE` is applied after the fence blanking, length-preserving so
line numbers stay accurate. Control confirmed: a bare `<!-- cluster: heterogeneous -->` outside code
still FAILs. The fence-abuse direction (internals hidden inside a fence → FAIL=0) remains open, as
round 2 expected and rated P2.

### Test weakness 1 — `ManifestInvariantMutationTests`: **CLOSED**

The class was rewritten to stage a mutated fixture tree, patch `FIXTURE_ROOT`, and run the real
`ManifestUnchangedInvariantTests` via a `TextTestRunner`, counting failures. I verified this is not
theatre by doing exactly what round 2 did: replaced all **ten** `test_*` method bodies of
`ManifestUnchangedInvariantTests` with `pass` and re-ran the bites.

```
Ran 6 tests in 0.052s
FAILED (failures=4)
```

All four mutation bites (A gutted records, B rotated references, C stubbed titles, D flattened
sections) now fail when the class under test is gutted — where round 2 got `OK, 11 tests`. Restored;
bites back to `OK`. There is also a `test_the_bite_harness_passes_on_the_unmutated_fixture` control,
which is the right addition. **This one is properly closed** — it is the model the two blocking
items above should have followed.

### Test weakness 2 — mutations C and D: **CLOSED**, and round-2's F is now caught too

Re-staged the mutations independently against the real invariant class:

| Mutation | Result |
|---|---|
| control: unmutated | passes — correct |
| C — stub every `title` | **detected** |
| D — flatten every `functional_section` | **detected** |
| round-2's F — stub title, park original verbatim in CoS | **detected** (33 failures) |
| reverse word order in every title | **detected** (41 failures) |
| inject a new field into every record | **detected** (49 failures) |

The two new tests (`test_manifest_titles_match_the_rendered_titles`,
`test_manifest_sections_match_the_rendered_sections`) are the right fix in principle: they do not
forbid the sanctioned mutation, they require the manifest and the render to agree.

---

## New findings from `a95dcb5` itself (non-blocking)

### N-1 (P2) — Mutation E: swapping two `functional_section` labels is undetected

As charged, I constructed a mutation that still passes the allowlist:

```
**PASSES (undetected)**  E3: swap two functional_section labels  (failures=0)
```

Every REQ is reassigned to the wrong section, and the invariant is fully green.
`test_manifest_sections_match_the_rendered_sections` compares only the **set** of manifest section
names against the **set** of rendered `##` headings:

```python
sections = {_norm(r["functional_section"]) for r in records if r.get("functional_section")}
headings = {_norm(m.group(1)) for m in re.finditer(r"^##\s+(.+)$", rendered, re.MULTILINE)}
missing = sorted(s for s in sections if s not in headings)
```

A swap preserves the set, so `missing` is empty. This is the *same* set-versus-per-record defect
class that Mutation B was written to close, reproduced inside the fix for Mutation D. The fix is to
check, per record, that the REQ is rendered under the heading its `functional_section` names — the
document offsets needed are already computed elsewhere in the module.

Also still undetected, and in the same family as round-2's surviving Mutation D: prefix-negating
every `conditions_of_satisfaction` with `"It is NOT required that: "` (containment only detects
shrinkage). Round 2 recorded this class as residual risk; it should stay recorded, and E3 belongs on
that list.

### N-2 (advisory) — 5 archived trees gain a new WARN, unreported

Sweeping all 105 archived trees under `repos/` and `metrics/`, `f9984ae` → `a95dcb5`:

```
  d8d4229: EVALUATED=105
  f9984ae: inert-no-headings=58  version-skipped=47
  a95dcb5: inert-no-headings=53  inert-wrong-level-WARN=5  version-skipped=47

=== f9984ae -> a95dcb5 diffs: 5 ===
  repos/archive/chi-1.5.1/.../previous_runs/20260507T033609Z   [0,0] -> [0,1]
  repos/archive/chi-1.5.1/.../previous_runs/20260507T044646Z   [0,0] -> [0,1]
  repos/secbench/CASE-002-jspdf                                [0,0] -> [0,1]
  repos/secbench/CASE-006-budibase                             [0,0] -> [0,1]
  repos/secbench2_widenet/wn-go-02-goshs                        [0,0] -> [0,1]
```

**Zero FAIL flips in either direction** — no gate exit code changes. The five diffs are all
`0 WARN → 1 WARN`, produced by the intentional INFO→WARN change for wrong-level REQ headings (round
2's recommendation 8). The change is correct and I am not asking for it to be reverted; it is worth
noting only because the commit message says "both archived PASS->FAIL flips remain GATE PASSED" and
does not mention that five archived trees now emit a new advisory. The `d8d4229` column confirms my
harness has discriminating power (it evaluates all 105 there, reproducing the original regression).

### N-3 (advisory) — the archived sweep has no discriminating power for the new checks

At `a95dcb5`, **zero** of the 105 archived trees reach the new mandatory-part checks: 47 are
version-skipped and 58 are inert (their REQ headings do not match `^###\s+REQ-\d+\s*:`). So "no
regression across the archive" is true but vacuous with respect to this commit's new blocking
checks.

To measure the real blast radius I neutered `_render_run_predates_contract` and forced evaluation:

```
trees FAILing on at least one NEW mandatory-part check: 47 of 75
    30  missing=['Actors & roles', 'Traceability appendix']
    11  missing=['Actors & roles', 'Traceability appendix']  + no functional section
     4  missing=['Actors & roles', 'Traceability appendix', 'Use cases']
     1  missing=['Actors & roles', 'Traceability appendix', 'Use cases'] + no functional section
     1  missing=['Actors & roles']
```

**Every historically-produced REQUIREMENTS.md in the archive would FAIL the new checks**, protected
today only by the version gate. That is defensible — §5.2 is a v1.6.0 obligation and the gate is
exactly the mechanism for it — but it means the mandatory-part checks are entirely unexercised by
real data, so the missing unit bites (B-3) are the *only* protection they will ever have. It also
means any future loosening of the version predicate is a 47-tree cliff. Worth recording in the guide.

### Confirmed clean

- **Three regenerated fixtures**: chi, express, virtio each **FAIL=0 WARN=0**, and each genuinely
  *evaluated* (not version-skipped or inert) — I checked the exit path, not just the counts.
- **Full suite at clean `a95dcb5`**: `Ran 2521 tests, OK (skipped=13)`. Matches the commit message.
- **Working tree**: `git status --porcelain` empty before and after all probing; all three scratch
  worktrees removed and pruned; HEAD still `a95dcb5`.
- **Both stale docstrings corrected**: `check_render_contract` now describes the wrong-level WARN
  behavior accurately, and the `test_render_regeneration_fixture_v160` module docstring no longer
  claims the manifest differs "only by the Phase E.6 renumber" — it now names the two sanctioned
  field rewrites and the CoS growth, and agrees with the class docstring below it.

---

## What is genuinely good here

The behavior fixes are the real thing. All four bypass shapes are dead, and they are dead by the
mechanism Panelist A specified rather than by a patch aimed at the four literal documents round 2
happened to write — I probed eighteen further shapes and only one got through. The worker also went
past the reported symptom: recognizing that §5.2 makes four parts mandatory and only two were
checked is a correct reading that nobody in the Council asked for. R-1's fix is the right shape
(narrow to the emitted forms, keep the controls firing) rather than the lazy fix of deleting the
pattern. And `ManifestInvariantMutationTests` is now a genuinely load-bearing bite with a control
test — I gutted all ten methods of the class under test and all four bites went red, which is
exactly what round 2 asked for and is the hardest of the six items to get right.

## What went wrong, said plainly

The worker fixed the code and did not fix the test, then wrote a commit message saying it had fixed
the test. Round 2 named that test in a required-before-SHIP item, in bold, with the file path. The
file was never opened. The same commit then added three new blocking checks with no bites at all,
in a module where every other check is bitten and audit-tabled — while simultaneously, in the other
file it touched, fixing an identical vacuity defect and writing a docstring that says "a bite that
does not exercise the code it guards is theatre."

Both new checks in `quality_gate.py` can be deleted and the 2521-test suite stays green. That is the
finding. Everything else is close.

---

## Required before SHIP

1. **B-2** — re-point `test_flat_requirements_heading_cannot_bypass_section_discipline` at a fixture
   whose flat `## Requirements` section carries ≥40 characters of intro prose. Verify by deleting
   the `if not functional:` block and confirming the test goes red.
2. **B-3** — add a `_fires` mutation bite for each of Actors & roles, Use cases and Traceability
   appendix, plus the matching `RENDER_CONTRACT_AUDIT` rows. Verify by emptying the check loop and
   confirming the suite goes red.
3. **B-4** — blank fenced code blocks before `_RENDER_LEVEL2_RE.finditer(text)`, as
   `_render_scan_internals` already does, and pin the fenced-heading bypass with a test.

## Recommended in the same pass (none blocking)

4. **N-1** — make `test_manifest_sections_match_the_rendered_sections` per-record rather than
   set-based, and record the CoS prefix-negation case alongside round-2's Mutation D as residual risk.
5. **N-3** — record in the guide that all 47 evaluable archived trees would FAIL the mandatory-part
   checks absent the version gate.
6. Fix the F-1 PASS message to stop saying "in the Overview" when the statement was found in a
   dedicated `## Coverage and gaps` section.
7. Do not carry the "bite is re-pointed" claim forward into the next commit message unless the test
   has actually been changed.
