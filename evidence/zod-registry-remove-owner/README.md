# zod ZD-012: registry.remove() deletes an id entry that now belongs to another schema

Verdict: CONFIRMED, severity LOW, no security angle (`CONFIRMATION.md`). Reported upstream as issue #6640, open (`STATUS.md`).

## The defect

`add()` lets a later schema take over an id: it sets `_idmap[id]` unconditionally (`registries.ts:39-41`). That behaviour is deliberate since commit adf65cde ("Drop id uniqueness enforcement at registry level", #5574), and the existing test "re-registering same id silently overwrites" (`registries.test.ts:210-220`) pins it. `remove()` (`registries.ts:51-58`) then deletes `_idmap[meta.id]` for any schema whose metadata carries the id, with no check that the schema still owns it. So:

```ts
r.add(a, { id: "x" });
r.add(b, { id: "x" });
r.remove(a);
```

leaves `r.has(b)` true but `_idmap` without `"x"`, and `z.toJSONSchema(r)` returns `{ schemas: {} }` instead of `{ schemas: { x: { type: "number" } } }`. (`CONFIRMATION.md` notes that `metadata.md:42`, which says a duplicate id throws, is stale relative to #5574.)

## Reproduction

`repro.ts` runs the sequence above against a zod source tree at `/tmp/zodw` and exits 1 if the bug is present. Its output is not captured in this folder.

## Red and green

The regression test is "removing the overwritten schema keeps the id for its current owner" in `packages/zod/src/v4/classic/tests/registries.test.ts`, added by the patch. The logs were run with vitest v4.1.11 in `/tmp/zodfix/BUG-012/packages/zod`. They carry times only (16:54:07, 16:54:09, 16:54:10); the patch is dated 2026-09-29 16:54:24 -0400.

- `red.log`, the new test against the unfixed source: `registries.test.ts` 21 tests, 1 failed, 20 passed. The failure is the new test, at `registries.test.ts:232` (`expect(reg._idmap.get("shared-id")).toBe(b)`): `expected undefined to be ZodNumber`.
- `green.log`, with the fix: 4 test files, 224 passed (`registries.test.ts` 21, `to-json-schema-methods.test.ts` 89, `from-json-schema.test.ts` 111, `describe-meta-checks.test.ts` 3).
- `revert.log`, the fix reverted: the same result as `red.log`, 1 failed and 20 passed in `registries.test.ts`, with the same failure.

## The fix

`0001-fix-registry-only-unmap-an-id-when-the-removed-schem.patch` adds one condition to `remove()` in `packages/zod/src/v4/core/registries.ts`: delete `_idmap[meta.id]` only when `this._idmap.get(meta.id!) === schema`. It also adds the 14-line test above, directly under "re-registering same id silently overwrites". `PR-DRAFT.md` is the pull request text.

## Review

Two reviewers, both SHIP (`review/A.md`, `review/B.md`).

- A checked the cases before and after the fix (sole owner removed, current owner removed, displaced schema removed, re-add then remove) and found no input where the old code was right and the new code is wrong. A reports `registries.test.ts` 20/20 on base and 21/21 on the fix.
- B reports the new test failing on base and passing on the fix; the four test files at 223 on base and 224 on the fix; the full `src/v4` suite at 2094 passed on base and 2095 on the fix, with the same 5 files failing to load on both from missing dependencies; and `tsc --noEmit` giving the same 2 errors on both. B's probes found a further symptom of the bug on base: an object that `$ref`s the overwritten id gets a dangling `{"$ref":"x"}` from `toJSONSchema`. B's probe script and outputs (`review/probe.ts`, `review/out_*.txt`, `review/tjs.test.ts`) are cited in `B.md` but are not in this folder.

No independent re-verification of the branch pushed for issue #6640 is recorded for ZD-012. The numbers above come from the logs and the two reviews only.

## Upstream status

Issue https://github.com/colinhacks/zod/issues/6640, open as of 2026-10-10 (`STATUS.md`). One comment, from anuj-hrcg on 2026-10-01, posts an "independent fix" implementing the same ownership guard and asks a maintainer to cherry-pick it. No maintainer response.

## Correction (2026-10-20)

Until 2026-10-20 this README held only a section titled "Independent re-verification of the submitted branch (2026-09-30)". That section was a word-for-word copy of the one in `../zod-intersection-nan/README.md` (ZD-003, the NaN intersection fix): its controls (the 0/-0 merge, conflicting intersections still throwing) belong to ZD-003, and no re-verification of ZD-012's pushed branch is recorded anywhere in this folder. An independent reproduction of the replication package caught it. The README was rewritten from this folder's own files; no other file in the folder was changed.
