# BUG-005 review B (BREAKER): treeifyError symbol keys

Verdict: SHIP

## New test, base vs fix
- On a copy of base with the new test file dropped in (review/basecopy), `z.treeifyError symbol key` fails with "expected [] to be undefined" (tree.items is an Array). The other 36 tests pass.
- On the fix: error-utils.test.ts, error.test.ts and src/v4/mini/tests all pass (290 tests; base has 289).
- Full src suite: base 2642 passed, fix 2643 passed. The same 5 files fail on both trees, only because packages are missing (esbuild, recheck, @web-std/file, @seriousme/openapi-schema-validator). The fix causes no failures.
- tsc --noEmit (excluding "Cannot find module"): 2 errors on both trees, and they are the same 2 (TS2688 for missing 'recheck'/'vitest' type definitions). The fix adds no type errors.

## Inputs the fixer did not cover (review/probe/p_{base,fix}.ts, q.ts)
Each probe below ran on both base and fix.
1. z.compile(object with symbol key): base puts it at items[k]; the fix puts it at properties[k]. Fixed.
2. zod/mini object with symbol key: fixed the same way.
3. Async refine on a symbol key (safeParseAsync): fixed.
4. array(object({[k]})) with the error at index 1: items[1] is still used for the index, and the symbol now goes to items[1].properties[k]. Correct.
5. tuple([object({[k]})]): same as 4. Correct.
6. union of two symbol-key objects: both union branch messages now land under properties[k]. Correct.
7. record(z.string(), ...) with a symbol own key (invalid_key): base splits the tree into properties.a plus items[k]. The fix puts both under properties. Correct.
8. A string key "a" and a Symbol("a") in the same object: they stay separate entries under properties. No collision.
9. Custom path ["a", 0, k, "0", -1, 1.5, NaN]: the numbers (including -1, 1.5 and NaN) still go to items and "0" still goes to properties. The output is identical to base except that k moves to properties.
10. record(z.number(), ...) and map number keys: these still go to items or properties exactly as on base. No change.

## Behaviour that changed outside the bug
- Custom-issue path elements that are not PropertyKeys (true, null, {}, 1n, undefined, all passed via `as any`) moved from an Array under `items` (keys "true", "null", ...) to `properties`. The issue path type is PropertyKey[], so these inputs are type-invalid, and the old placement (named keys on an Array) was no better. I found no schema that produces them: map value issues come out with path [] on both trees (a separate, pre-existing issue, not related to this fix). Not blocking. Mention it only if Colin asks about non-PropertyKey paths.
- The own-property / defineProperty guard now also runs for symbols. That is harmless because symbols can't collide with inherited string names.

## Minor (optional)
- The test casts the tree to `any`. The fixer could check whether `tree.properties?.[k]?.errors` type-checks without the cast, since `$ZodErrorTree` declares keyof T. That would pin the type too. Not required.

I could not break the fix. Every probe that changed moved a symbol from items[k] to properties[k], or moved a type-invalid path element the same way.
