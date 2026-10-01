# BUG-012 review, reviewer A (MAINTAINER)

Verdict: SHIP

## The diff
- One condition added to `remove()` in `packages/zod/src/v4/core/registries.ts`: delete `_idmap[id]` only if `_idmap.get(meta.id!) === schema`. The file already uses the `meta.id!` style, and the line is 102 chars, under biome's lineWidth of 120. There's no new helper, rename or reformat. I can't see a smaller correct change.
- One test sits directly under "re-registering same id silently overwrites". It uses the same fixture shape (`reg`, `a = z.string()`, `b = z.number()`, `"shared-id"`), so it reads as a continuation of that test.

## Deliberate design?
- The fix doesn't change the design. It completes it. Commit adf65cde (#5574, "Drop id uniqueness enforcement at registry level") made "last add wins" the deliberate behaviour, and registries.test.ts:210-220 pins that `_idmap.get("shared-id")` is `b` after two adds. Before this fix, `remove()` of the displaced schema (the HMR / test re-import flow that #5574 names) undid that ownership. That contradicts #5574's intent.
- `toJSONSchema(registry)` builds its output from `_idmap.entries()` (json-schema-processors.ts:897,913). So the old behaviour silently dropped a live schema from the output, and that is visible to users.
- The v4 changelog has nothing on registry remove/idmap semantics. `git log -S` on the touched line can't be run in full because the base clone is partial (missing objects), so I relied on #5574 and the pinned test.

## Case where the old code was right?
I checked these against the base tree and the fix tree:
- Sole owner removed: both trees unmap the id. Same behaviour.
- add a, add b, remove b (current owner): both trees unmap the id. Same behaviour.
- add a, add b, remove a (the bug): base drops b; the fix keeps b.
- add a, add b, re-add a, remove b: base drops a; the fix keeps a. This is also correct.
If `_idmap[id]` points at a different schema, that schema is still registered and owns the id, so deleting the entry is never right. I found no input where the new code is wrong and the old code was right.

## Not addressed, left alone correctly
- Removing the current owner does not bring back a previous registrant of the same id (in the add a, add b, remove b case, `a` stays in `_map` but not in `_idmap`). That would need history tracking, which is a design change, and it behaves the same before and after the fix.
- Re-adding a schema with a different id or with no id leaves a stale `_idmap` entry. That is pre-existing and untouched here.
Neither belongs in this PR.

## Tests
- registries.test.ts: 20/20 pass on base, 21/21 on the fix.
- The new assertion (`_idmap.get("shared-id")` is `b`) fails on base, confirmed with a standalone script against /tmp/zodw.

## Optional nit (not blocking)
The test's third assertion (`toJSONSchema(...).schemas`) is the user-visible symptom and is worth keeping. The `has(b)` line is true on base as well, so it proves nothing about the fix. Colin may not mind it, but it can be dropped.

Would merge as is.
