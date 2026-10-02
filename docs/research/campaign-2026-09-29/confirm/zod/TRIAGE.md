# zod: confirmation of the Phase 5 bug list (snapshot 2026-09-29, 23 entries)

Method: one fresh Opus sub-agent per entry, brief in `CONFIRMER-BRIEF.md` (copied below the table). Each wrote a `repro.ts` (in `repros/`) run with tsx against the pinned source at `2bf7b063` (no build, zod has no runtime deps), checked the cited doc sentence and the test suite for anything pinning the current behaviour, searched github.com/colinhacks/zod issues and PRs, and gave a verdict. Full reports are in the Cowork transcript of 2026-09-29; this table is the digest. The list is QPB's Phase 5 output before the iteration strategies; later additions are triaged separately.

| Bug | Title (short) | Verdict | Basis for "expected" | Closest upstream | Note |
|---|---|---|---|---|---|
| 001 | compiled object accepts missing key (optional under intersection/success) | CONFIRMED | compile.md:9 "Results and errors are identical" + sibling test | none (#5050 runtime, PR #6559 unmerged) | weak security angle (validation bypass on uncommon composition) |
| 002 | intersection of two map()/set() throws Unmergable | DUPLICATE | api.md + sibling containers | #5201 (closed by reporter, unfixed) | |
| 003 | intersection throws on identical NaN | CONFIRMED | changelog's own rationale ("incompatible types") doesn't hold; `a === b` vs `Object.is` | none | one-token fix; `z.nan().and(z.nan())` unsatisfiable |
| 004 | exhaustive record accepts missing enum key when value accepts undefined | CONFIRMED | api.md:2134 + static type + JSON Schema `required` + PR #6460's stated model | none (#6163 adjacent) | fix in schemas.ts and compile.ts |
| 005 | treeifyError files symbol keys under `items` | CONFIRMED | `$ZodErrorTree` type + 3 sibling functions | none | one-line fix |
| 006 | toJSONSchema drops regex i/s/m flags | CONFIRMED | "closest equivalent" + never-narrower invariant | none | fix is a policy choice (omit / unrepresentable / rewrite) |
| 007 | templateLiteral ignores length bounds when part has regex | CONFIRMED | v4_index.md:712 "min/max refinements are enforced" | #4756 (closed, refinements only) | also drops all but the last `.regex()` |
| 008 | templateLiteral drops part regex flags (i rejects valid, u accepts invalid) | CONFIRMED | part vs template inconsistency; PR #1786 author noted `/i` unhandled | none | fix needs a design decision |
| 009 | .extend() on refined object doesn't throw unless key overlaps | NOT-A-BUG | api.md:1393 says throws | v4.3.0 notes, #4874 | code is intended; docs sentence imprecise |
| 010 | stringbool encodes lower-cased custom value | NOT-A-BUG | codecs.md:305 | #5011 (maintainer states design) | `case: "sensitive"` exists |
| 011 | json-schema docs show exclusiveMinimum for float32/int32, bare int() | CONFIRMED (docs) | doc vs pinned test snapshots | none (#4779 adjacent) | 4-line doc fix |
| 012 | registry.remove() deletes an id now owned by another schema | CONFIRMED | add()/has() contract + PR #5574's HMR rationale | none (#4145, #4834 adjacent) | one-line guard |
| 013 | metadata docs say duplicate id throws; it doesn't | CONFIRMED (docs) | doc vs PR #5574 + test | none | `toJSONSchema(registry)` also silently drops the shadowed schema |
| 014 | metadata docs say refined schema has no metadata; it inherits | CONFIRMED (docs) | doc vs test + PR #4255 | discussion #5337 repeats the wrong doc | doc example is false |
| 015 | z.function().implement() throws core $ZodError not z.ZodError | CONFIRMED | api.md:3444 + changelog + parse() sibling | none | `instanceof z.ZodError` guards miss it |
| 016 | fromJSONSchema compiles `pattern` without `u` | CONFIRMED | JSON Schema §6.3.3 SHOULD + toJSONSchema(z.emoji()) doesn't round-trip | none | experimental API; adding `u` can break sloppy patterns |
| 017 | fromJSONSchema rejects object/array const/enum members | CONFIRMED | JSON Schema §6.1.2–3 structural equality | none (#6634 adjacent) | also false-accepts: `const:[1,2]` accepts `2` |
| 018 | fromJSONSchema ignores keywords when `type` absent | DUPLICATE | JSON Schema §6 | #6634 (open, 2026-09-29, case 3) | mild security angle (fail-open) |
| 019 | fromJSONSchema allOf lets one branch bypass another's additionalProperties:false | CONFIRMED | JSON Schema §10.2.1.1; ajv rejects | none (#6634 same class) | mild security angle (fail-open); fix needs a distinct allOf combinator |
| 020 | mk locale leaves two templates in English | CONFIRMED | every other locale translates them | none | needs a native speaker for the wording |
| 021 | async parses order keys/entries/issues by settlement | CONFIRMED | sync path + "preserve key order" test; tuple path is the in-tree precedent | #6608 (unions only), #6612 | issue order becomes timing-dependent |
| 022 | constant .catch() value returned by reference | CONFIRMED | `.default()` clones (PRs #5173, #5855) | none (all about .default()) | |
| 023 | Date default shared across parses | UNCLEAR | compile.ts:1665 comment | #5855 (Map/Set only) | policy: how far does shallowClone's whitelist go |

Totals: 15 code defects confirmed and unreported; 3 documentation defects confirmed; 2 duplicates; 2 not bugs; 1 unclear.

## Candidate targets for the control comparison

Code defects only (the control has no docs, so 011/013/014 cannot be found by it and are excluded from targets; they are still worth filing). Set aside for the security-angle rule: 019 (fail-open validation under allOf); 001 is borderline and is kept. Experimental-API caveat on 016, 017: real, but a maintainer may deprioritise.

Strongest: 003, 004, 005, 012, 015, 021, 022 (small, unambiguous, non-experimental). Then 001, 007, 008, 006, 020, 016, 017.
