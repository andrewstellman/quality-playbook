# BUG-022 review C (TEXT)

Verdict: FIX-REQUIRED (text only, no code change)

Checked against the diff, REPORT.md, git log and a compiled-path run.

True and traceable:
- #5173 is "ensure array defaults are shallow-cloned" and #5855 is "clone Map and Set in shallowClone ... across .default() parses". Both exist in the log, so the PR's attribution is correct.
- default.test.ts has clone tests for object, array, Map and Set at lines 315-350, plus the mutation tests. "pinning that behaviour" is accurate.
- The compiled path passes the same thunk through addUserConstant/runtimeCatch. I ran z.compile(z.array(z.string()).catch([])) on the fix: push, then parse again, and it returns []. "z.compile calls the same thunk" is true.
- The CONSTANT_CATCH tag is kept in the diff. The user-callback branch (`typeof catchValue === "function"`) never reaches constantCatch in the three call sites, so that claim is true too.
- The test sits at the end of catch.test.ts as a top-level `test(...)`, like its neighbours. It asserts observable behaviour: a fresh, empty result on the next parse. It does not assert that shallowClone was called.

Problems:
1. Commit and PR title use `fix:`. The neighbouring catch commits use `fix(v4): ...` (#6462, #6192, #6440, #5941, #5855, #5173). Change to `fix(v4): shallow-clone a constant .catch() value on every parse`.
2. The PR body is one 190-word paragraph that restates the diff. "the CONSTANT_CATCH tag is unchanged, so codegen still recognises a constant" and "the user-callback path is untouched because it never goes through constantCatch" are diff narration that the reviewer can read in the diff. "The added test pushes onto... and asserts..." restates the test. Colin will see all of it.
3. "so the gap went unnoticed" is speculation with no evidence. The evidence is only that catch.test.ts has no identity test. Cut it.
4. "Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change." Confirm this matches the campaign's disclosure convention. "AI code-review tool" is a fair description and "with Claude" is fine. I found nothing false in it.
5. The commit body says "setting into one fallback Map". Fine. It duplicates the PR text, which is acceptable.
6. Test nit: `expect(a1).not.toBe(a2)` is implied by `a2` equalling `[]` after a1 was pushed to. It is harmless but redundant, and dropping it makes the test smaller. Optional.
7. The doc comment on constantCatch adds a second sentence ("as the `.default()` getters do, so a caller mutating...") that runs long for this file. The file's comments are long, so this is acceptable, but it could be shortened to "Shallow-clones on every call, as `.default()` does, so one fallback result cannot be mutated into the next."

Proposed PR body (replaces the paragraph):

> `z.array(z.string()).catch([])` returns the same array on every failed parse, so `arr.parse(1).push("leak")` changes what the next `arr.parse(1)` returns. A `.catch(new Map())` fallback does the same, and so does the `z.compile` path, since it calls the same thunk.
>
> `.default()` already shallow-clones its value on every read (#5173 for arrays, #5855 for Map and Set). `constantCatch` now does the same. `catch.test.ts` had no test for it.
>
> Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

Note that I did not confirm the `.catch(new Map())` claim on the base tree myself. It comes from the REPORT, which says "Map likewise". The compiled-path claim I checked only on the fix, where it no longer leaks. The base leak in compile rests on the REPORT.
