# BUG-003 review, charter A (MAINTAINER)

Verdict: SHIP. One optional style change is listed below; it does not block the merge.

## Diff as Colin would read it
- The change touches one line in `mergeValues` (packages/zod/src/v4/core/schemas.ts:2833) and adds one test. It is minimal, and there is no refactor or API change.
- Choosing `a !== a && b !== b` over `Object.is` is correct. `Object.is(0, -0)` is false, so `Object.is` would start throwing on +0/-0 merges that work today. I checked on the fix: `z.literal(0).and(z.number()).safeParse(-0)` still succeeds.
- The compiled path is covered. compile.ts:1933 injects the same `mergeValues` as a constant. I checked `z.compile(z.nan().and(z.nan())).safeParse(NaN)`, which gives `{ success: true, data: NaN }`.

## Deliberate design?
- The v4 changelog (changelog.mdx:735-737) keeps the throw for unmergable results and justifies it as "an intersection of two incompatible types". Two NaNs are not incompatible, so the fix keeps the design and removes a false positive.
- No existing test pins NaN behaviour. The throw tests in intersection.test.ts (invalid array/object merge) use genuinely conflicting values and still pass.
- `git log -S` / `git blame` could not run because a blob is missing in the base clone (`fatal: unable to read ded0da1b`). I could not check the line's history, but nothing in the code comments or the changelog marks `===` as intentional for NaN.
- Tests: intersection.test.ts has 19/19 passing on base and 20/20 on the fix.

## Is there a case where the old code was right?
- I found none. The only newly accepted inputs are NaN/NaN pairs, at the top level or nested in shared object keys or array slots. One example: two object sides whose transforms each produce NaN for the same key now merge to `{a: NaN}`. That matches how two sides that each produce `5` already merge, so it is consistent.
- `a !== a` is true only for the number NaN (and boxed values are not involved), so no other type is affected.

## Change I would ask for (optional, style)
- This codebase writes NaN checks as `Number.isNaN(x)` throughout (schemas.ts:1339, 1345, 1809, 4378; compile.ts, util.ts). It never uses the `x !== x` idiom. To match the file:
    if (a === b || (Number.isNaN(a) && Number.isNaN(b))) {
  `Number.isNaN` on `any` has the same semantics here and needs no comment. The added comment line could then be dropped, giving a one-line diff.
- The v3 copy (packages/zod/src/v3/types.ts:3245) has the same `a === b`. Leaving v3 alone is the right call because it is legacy and Colin would not want it in this PR. The PR does not claim to fix v3.

## PR text (maintainer's reading)
- The "basics.md says safeParse returns a result" sentence is fine, but it leans toward "safeParse should never throw", which the design deliberately rejects for incompatible types. The confirmer's report advised against that framing. I would drop that clause and keep the argument that identical NaN is not incompatible.

Merge decision: merge as-is. If requested, swap to `Number.isNaN` and drop the comment.
