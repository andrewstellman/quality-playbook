# BUG-003 review, B (BREAKER)

**Verdict: SHIP.** I found no input whose behaviour changed except identical NaN pairs, and no type regressions.

## Tests
- New test `identical NaN merges`: it fails on the base src (the fix's test file run with ZOD_SRC=/tmp/zodw) and passes on the fix.
- intersection.test.ts plus src/v4/mini: base 224/224, fix 225/225.
- All of src/v4: base 2094 pass, fix 2095 pass. The same 5 test files fail to load on both trees (file, redos, to-json-schema, polyfill-collision, treeshake). These are environment/dependency failures and have nothing to do with this fix.
- tsc --noEmit: both trees give the same 2 errors (TS2688 missing 'recheck'/'vitest' type defs). The fix adds no new errors.

## Inputs the fixer didn't test (base -> fix)
Scripts: review/edge.ts, review/edge2.ts.
1. Compiled: `z.compile(z.nan().and(z.nan())).safeParse(NaN)`: THREW -> OK NaN. compile.ts:1933 hoists the same `mergeValues`, so the compiled path is fixed with no separate change.
2. zod/mini: `intersection(nan(), nan())`: THREW -> OK.
3. Async: `z.nan().and(z.unknown().refine(async()=>true)).safeParseAsync(NaN)`: THREW -> OK.
4. Nested in a rebuilt container: `z.object({c:z.array(z.unknown())})` ∩ itself on `{c:[1,NaN]}`: THREW (path ["c",1]) -> OK. This is a stronger case than the loose-object test. There, `c` is passed by reference and already merged via `a===b` on base when nested (`{c:{d:[NaN]}}` was OK on both trees). Worth considering as the test's object case.
5. Independent producers: `z.string().transform(()=>NaN).and(z.string().transform(Number))` on "abc": THREW -> OK. This does change behaviour: two different transforms that both yield NaN now merge. It is consistent with "same value" and I think it's correct, but it is the one case that goes beyond "the same NaN passed through".

## Unchanged (verified identical on both trees)
- NaN vs "NaN": still throws. NaN vs 1 (compiled): still throws.
- +0 vs -0: still merges to 0. The fixer's `a !== a && b !== b` form keeps this, where `Object.is` (the alternative the confirmer suggested) would have turned it into a throw. The chosen form is the safer one.
- `z.number().and(z.number())` on NaN: still a normal invalid_type failure (the bug never reached this).
- `new Number(NaN)`, the same Invalid Date reference, a nested record holding NaN: OK on both.
- The v3 `mergeValues` (v3/types.ts:3241) is not touched, so `z.nan().and(z.nan())` still fails in v3 (it returns an invalid_intersection_types issue and does not throw). This is out of scope for a v4 fix. If the PR text implies v3 is fixed, that should be corrected.

## Residual (not blocking)
- Two *distinct* Invalid Date objects still fail to merge (`+a === +b` is NaN === NaN). It's the same class of bug on the next line. I could not reach it through public schemas without a transform, so I'd leave it out unless Colin asks.
