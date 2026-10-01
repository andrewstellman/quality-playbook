# BUG-022 review B (BREAKER): constantCatch shallow-clones

**Verdict: SHIP.** I couldn't break the fix. The behaviour changes it causes match what `.default()` already does on purpose.

## Tests (base = /tmp/zodw, fix = worktree)
- New test run against base: FAILS ("expected [ 'leak' ] not to be [ 'leak' ]"). Run against fix: passes.
- catch.test + default.test + all of src/v4/mini: base 259/259 pass, fix 260/260 pass.
- Full `src` suite: base 2642 pass, fix 2643 pass. Both trees fail the same 5 files at load time because packages are missing (`@seriousme/openapi-schema-validator`, `esbuild`, etc.). That means to-json-schema.test.ts and treeshake.test.ts did not run on either tree. I checked the JSON Schema path by hand (below). treeshake.test.ts has no reference to catch or shallowClone.
- tsc: base has 2 errors and fix has 2. The lists are identical (missing type defs for `recheck`/`vitest`). The fix adds no type errors.

## 18 edge inputs, base vs fix (review/edge.ts, output in review/edge.out)
Now fixed (base shared state across parses, fix returns a fresh value):
- async `parseAsync`
- `z.compile(...)`, both top-level and nested in an object. The compiled path calls the same tagged thunk through `runtimeCatch`, so it gets the clone for free.
- zod/mini `z.catch(...)`
- `Set`
- a catch nested inside array → record → array

Same on base and fix:
- a callback catch `() => shared` still returns the same reference. The user-callback path is untouched.
- `Date` is returned by identity
- valid input passes through unchanged
- `toJSONSchema(...).default` is `[]` and was already not identity-equal on base
- nested contents are still shared: `catch({t: []})`, then `.t.push` leaks into the next parse. The clone is shallow, same as `.default()`.

Behaviour changed for inputs the bug report did not cover. All four are plain objects or arrays that shallowClone rebuilds:
1. **Sentinel identity.** `schema.catch(FB).parse(bad) === FB` was true on base and is false on the fix. Code that tells "fell back" apart with `===` on a plain-object or array fallback will break. This is the one change a user could notice.
2. A null-prototype object comes back with `Object.prototype`.
3. A frozen array or object comes back unfrozen.
4. An Array subclass comes back as a plain `Array`, and a Map/Set subclass as a plain Map/Set, per shallowClone.
5. Getters on a plain-object fallback now run on every fallback, not never (getterCalls was 0 on base, 2 on fix).

On base, `.default()` shows the same result for items 1–4 (review/def.ts gives sentinel/nullProto/frozen/subclass all false). So the fix makes `.catch()` behave like `.default()`'s clone-on-read, which #5173 and #5855 made deliberate. It does not add a new kind of behaviour.

## Asks (none block the merge)
- Say in the PR body that `===` against a plain-object or array fallback no longer holds, and that `.catch(() => value)` is how to keep a shared reference. Colin may count that identity as API.
- Optional: add a `z.compile` assertion to the new test, since the compiled path is part of the claim ("keeping ... the compiled path") and nothing currently pins it.
