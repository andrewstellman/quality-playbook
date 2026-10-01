# BUG-022 review, reviewer A (MAINTAINER)

Verdict: SHIP. Optionally add one sentence to the PR text (below).

## Is it the smallest correct change?
- Yes. It changes one line of code (`() => value` becomes `() => shallowClone(value)` in `constantCatch`, util.ts:1277) and adds one sentence to the docstring. `shallowClone` is already defined in the same file (util.ts:558), so there's no new import or helper.
- It fixes the single choke point. classic (schemas.ts:2517), mini (schemas.ts:1684) and core api (api.ts:1571) all send a constant catch value through `util.constantCatch`. The compiled path calls the tagged thunk once per failed parse (compile.ts:2261-2276 -> `runtimeCatch` -> `catchValue()`), so it inherits the fix without touching compile.ts. Verified: `z.compile(z.array(z.string()).catch([]))` after push returns `["x"]` on base and `[]` on fix.
- It reads the way the file already writes code. It mirrors the existing `.default()` getters (api.ts:1527, classic 2406/2436, mini 1588/1614), which use `util.shallowClone(defaultValue)`. The `CONSTANT_CATCH` tag and the user-callback path are untouched: a function passed to `.catch()` never goes through `constantCatch`.

## Does it touch a deliberate design?
- The `CONSTANT_CATCH` comment (util.ts:1272) is about provenance for codegen and error-map finalization. It says nothing about identity. The fix keeps the tag and the thunk shape, so compile.ts still recognizes the value as a constant.
- Tests: catch.test.ts has no identity pin; all its `toBe` checks are on primitive strings. default.test.ts:315-375 pins clone-on-read for `.default()`, which is the precedent this follows (#5173, #5855).
- changelog.mdx has no entry about `.catch()` value identity.
- `git log -S` is not runnable: the base clone is missing objects ("unable to read 6f711d93..."). Provenance of the touched line comes from the comments and the PR numbers in the confirmer's report, not from history.

## Where the old code was "right" and the new code differs
- Plain-object or array sentinels passed by reference no longer compare equal by identity. `const S = {none:true}; schema.catch(S).parse(bad) === S` is `true` on base and `false` on fix (verified). `.default()` made the same trade in #5173 without objection, and class instances, primitives, Dates and functions still pass through by reference (`shallowClone` returns them unchanged). A reviewer could raise it; the precedent answers it.
- It is still a shallow clone: nested objects stay shared. That matches `.default()`, and deep cloning would be a design change.
- `toJSONSchema` calls `catchValue(undefined)` (json-schema-processors.ts:786). It now gets a clone; the emitted `default` is identical (verified on `["a"]`).
- Cost: one spread per catch hit, and only when the value is a plain object, array, Map or Set. Negligible.
- v3 (`v3/types.ts:504,4683`) has the same by-reference behaviour and is not touched. That's correct scope for a v4 fix.

## Tests run (fix tree)
- catch.test.ts 32/32 pass. default.test.ts 23/23. mini/tests 205/205. core/tests 434/434, same as base; the esbuild-import failures happen on both trees.
- to-json-schema.test.ts can't load on either tree (missing `@seriousme/openapi-schema-validator`). This is an environment problem, not caused by the fix.
- I did not run the new test against base directly, because its file lives only in the fix tree. The repro and my compiled-path check show that base returns the mutated value, so the new assertions would fail there.

## Asks (non-blocking)
- PR text: add one line so Colin sees the trade-off up front: "A plain object or array passed to `.catch()` is no longer returned by identity, matching `.default()` since #5173."
- The test is placed and named like its neighbours and asserts behaviour (`not.toBe`, `toEqual([])`, `size`), not implementation. Fine as is.
