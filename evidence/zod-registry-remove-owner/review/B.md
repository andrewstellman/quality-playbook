# BUG-012 review — B (BREAKER)

**Verdict: SHIP.** I couldn't falsify it. Every behaviour change I found is the bug being fixed or a direct consequence of it. No regressions.

## Tests (base = /tmp/zodw, fix = /tmp/zodfix/BUG-012)
- New test run against base src: FAILS (`expected undefined to be ZodNumber` on `_idmap.get("shared-id")`). Against fix: PASSES.
- registries, to-json-schema-methods, describe-meta-checks, from-json-schema: base 223 / fix 224 pass.
- to-json-schema.test.ts can't load in this sandbox because `@seriousme/openapi-schema-validator` is missing. I ran a copy with the Validator stubbed (review/tjs.test.ts): 167/167 pass on both base and fix.
- Full `src/v4`: base 2094 pass, fix 2095 pass. The same 5 files fail to load on both (missing deps).
- tsc --noEmit: 2 errors on base and 2 on fix, identical (TS2688, missing type libs). The fix adds no type errors.

## Probes the fixer's test doesn't cover (review/probe.ts; outputs in review/out_*.txt)
Each probe also loads `zod/compile`. Changed = base and fix differ.
- p3 remove(a) twice, plus remove(unregistered): base loses "x", fix keeps x→b. Changed (bug case).
- p5 metadata object mutated after add (m.id "x"→"y", where "y" is owned by b), then remove(a): base deleted **b's** "y" entry, fix keeps it. Changed, and the fix is correct. The fixer didn't mention this path.
- p6 globalRegistry via `.meta({id})` twice plus `.describe()`, then remove(first): base drops "G", fix keeps G→b. Changed (bug case).
- p7 zod/mini registry + toJSONSchema: same bug and same fix as classic. Changed (bug case).
- p8 nested: object with `$ref`s to the overwritten id. On base, toJSONSchema(reg) emits `{"$ref":"x"}` with no "x" definition anywhere (a dangling ref, so the output is invalid JSON Schema). The fix emits the "x" def. Changed. This is the strongest user-visible symptom and the PR could cite it. Sync and async parse of the object: identical on both.
- p10 three schemas share one id; remove the middle one, then the first: base loses "x", fix keeps x→c. Changed (bug case).
- Unchanged on both trees: p1 (same schema re-added under a new id), p2 (remove the current owner), p4 (id undefined / ""), p9 (clear then remove), p11 (remove, then re-add the old schema).

## Pre-existing issues the fix doesn't touch (not blockers, don't widen the PR)
- p1: `add(a,{id:"x"}); add(a,{id:"y"}); remove(a)` leaves a stale x→a in `_idmap` after a is gone from `_map`. toJSONSchema still emits it. This happens because `add()` never unmaps an old id when the same schema is re-registered.
- p2: `remove(b)` when b is the current owner leaves the older schema a in `_map` with id "x" but no `_idmap` entry, so a disappears from toJSONSchema(reg). Restoring the previous owner would be a design change and is out of scope.

## Notes
- The test reaches into `_idmap`, but the existing neighbour test at line 219 already does that, so it matches the file's style. The toJSONSchema assertion covers the public behaviour.
- I made no changes to tracked files. All artifacts are under review/.
