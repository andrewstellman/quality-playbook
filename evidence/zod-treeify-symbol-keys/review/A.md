# BUG-005 review A (MAINTAINER)

Verdict: FIX-REQUIRED (cosmetic, one line). The behaviour change is correct and I'd merge it, but not in this shape.

## Correctness
- Issue paths reaching treeifyError are always PropertyKey. $ZodMap only calls prefixIssues when `util.propertyKeyTypes.has(typeof key)` (core/schemas.ts ~3495); any other key goes to an invalid_key/invalid_element issue with no path segment. Records put string keys in paths, and arrays/tuples put numbers. So in practice the only input whose routing changes is a symbol, which moves from `items` to `properties`.
- The old code was never right for that input. Its result was an Array with a symbol-keyed expando. The declared return type `$ZodErrorTree<T>` (errors.ts:408-419) uses `properties?: {[K in keyof T]?}`, which includes symbol keys. flattenError, formatError and toDotPath (with an explicit symbol branch) all treat a symbol as an object key. Symbol shape keys are a supported feature (object.test.ts "symbol keys in object shape").
- The only theoretical regression is a hand-built `ctx.addIssue({ path: [<non-PropertyKey>] })`, which is off-type. Such a segment used to go to items[String(x)] and now goes to properties[String(x)]. Both are garbage-in, so this doesn't block.
- The __proto__/hasOwnProperty/defineProperty guard now runs on symbols too. Both calls accept symbols, and I checked it with a nested case.
- Checked, not assumed. error-utils.test.ts passes 37/37 on the fix and 36/36 on base. Nested `{[k]: [{a}]}` and `z.map(z.symbol(), z.string())` now land under properties[k] on the fix and under items on base. Number paths (`n.items[0]`) are unchanged.

## Deliberate design?
- I found no test pinning symbol→items. error-utils.test.ts uses symbols only in toDotPath cases. No code comment explains the string-only branch.
- The v4 changelog only says to use treeifyError in place of format/flatten. It says nothing about symbol handling.
- `git log -S`/blame on errors.ts fails in /tmp/zodw (missing blob 11438186…, partial clone), so I could not see the commit that introduced the branch. That history check is unverified. Nothing else suggests the behaviour was intentional.

## Requested change (why not SHIP)
The diff swaps the two branches and re-indents the whole guard block into `else`: 10 lines touched for a one-token semantic change. Colin reviews for minimal diffs. The same behaviour comes from one line with no block movement:

```diff
-          if (typeof el === "string") {
+          if (typeof el !== "number") {
```

The rest of the file stays byte-identical, which makes the blame easier to follow and the review trivial. Update the commit message to match, e.g. "Send every non-number segment to `properties`" instead of "Branch on numbers for `items`…".

## Test
- The placement (right after "z.treeifyError 2") and the name fit their neighbours. It asserts behaviour (`items` undefined, `properties[k].errors`), not implementation. Fine as written.
- Optional: neighbours use toMatchInlineSnapshot, but a snapshot can't show a symbol key clearly, so the explicit expects are the better choice here. Keep them.

## Would I merge?
Yes, after the one-line rewrite. Low severity, no API or type change, and it aligns treeifyError with its three sibling formatters.
