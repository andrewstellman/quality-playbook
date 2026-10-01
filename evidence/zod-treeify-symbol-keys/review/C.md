# BUG-005 review C (TEXT)
Verdict: FIX-REQUIRED (text only; diff and test are fine)

Verified true against the diff/report:
- Cause and fix as described (errors.ts 446-467, `typeof el === "string"` -> `"number"`, else-branch holds the own-property guard).
- `$ZodErrorTree` declares `properties` over `keyof T`; flattenError/formatError file symbols via `node()`; toDotPath has a symbol branch.
- Docs sentence "mirrors the schema itself" exists (error-formatting.mdx:81; draft says .md).
- Test placed directly after "z.treeifyError 2", named in the file's `z.treeifyError ...` style, passes (37/37 in error-utils.test.ts), asserts output not implementation.

Problems:
1. PR body is one dense paragraph that restates the diff ("This change flips the branch: numbers go to items, everything else..."; "reusing the existing own-property guard"). The maintainer can read the diff; cut. "Pins that items stays undefined..." also narrates the test.
2. "The cause is the walker branching..." is fine but pad-worded; "hangs the node off that array as items[k]" is imprecise (an Array with a symbol property).
3. Commit body says the siblings treat symbols "alike as object keys ... matching ... toDotPath". toDotPath only formats a symbol segment as `["k"]`; it does not file it under an object. Overclaim. Drop toDotPath from the commit, or say "consistent with flattenError and formatError".
4. Commit body duplicates the PR; for a one-line fix, a shorter body is enough.
5. "Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change." Disclosure is fine but "I reviewed the change" is a claim only the submitter can make; keep it only if true for the human submitter.
6. Draft should note user-visible impact: previously `tree.properties` was undefined and the message lived on an Array, so `tree.properties[k]` threw/was undefined.
7. Path file name: error-formatting.mdx, not .md.

Test nit: `const tree: any` is needed since `$ZodErrorTree<{[k]: string}>` types fine; neighbours use typed access? If z.treeifyError's inferred type indexes `[k]` cleanly, drop `any` and the cast. Otherwise leave.

Proposed replacement PR text:

  **fix: file symbol path keys under `properties` in `treeifyError`**

  For `z.object({ [k]: z.string() })` with `k = Symbol("k")`, a failing value made `treeifyError` put the issue on `tree.items` (an array with a symbol property) and leave `tree.properties` undefined. The `$ZodErrorTree` type declares `properties` over `keyof T`, which includes symbols, and `flattenError` and `formatError` already treat a symbol path element as an object key.

  Only numeric path elements now go to `items`; strings and symbols go to `properties`. New test: `z.treeifyError symbol key`.

  Found with Quality Playbook (AI code review, with Claude).

Proposed commit:

  fix: file symbol path keys under properties in treeifyError

  Symbol path elements were sent to `items` because only strings went to
  `properties`. Send numbers to `items` and everything else to `properties`,
  as flattenError and formatError already do for object keys.
