# BUG-015 review — B (BREAKER)

Verdict: SHIP (no falsifying input found)

## Tests
- New test "implemented function throws ZodError": FAILS on base (a copy of /tmp/zodw with only the new test file swapped in; 1 failed, 21 passed), PASSES on fix (22/22).
- src/v4/classic + src/v4/mini: base 1660 passed, fix 1661 passed (+1 = new test). The same 3 suites fail on both before collection (file, redos, to-json-schema): environment/missing deps, not the fix.
- src/v4/core: 660 on both, plus the new test on fix. treeshake + polyfill-collision fail on both (missing esbuild).
- tsc --noEmit: 2 errors on base, 2 on fix, identical text after the 'Cannot find module' filter. No new type errors.
- out/0001-*.patch is byte-identical to `git format-patch -1` of the commit.

## Inputs the fixer's test does not cover (review/edge.ts; outputs in review/out_zodw.txt and review/out_BUG-015.txt)
20 cases run on both trees. The ONLY differences are the thrown class (and flatten() existing) in these cases:
- z.object({f: fnSchema}).parse(...).f(bad) (the path through _zod.parse): $ZodError -> ZodError
- promise-output fn parsed through an object (routes through implementAsync): $ZodError -> ZodError
- z.function().input([...]).output(...) chain (new F via inst.constructor gets the override): -> ZodError
- z.compile(z.object({f})) and z.compile(fnSchema).implement: -> ZodError
- a function returning a function, validated by a nested z.function output: -> ZodError
- implementAsync with an async refine on the output: -> ZodError
- z.config({customError}) active: -> ZodError
In every one of these, issues (code, path) and the message are identical between base and fix.

Unchanged on both trees, as they should be:
- zod/mini implement (still $ZodError), and core $ZodFunction constructed directly (still $ZodError)
- no input/output schemas; `this` binding; transforms in args (returns the transformed value)
- user function throws its own TypeError (sync, and sync throw inside implementAsync): passes through untouched
- sync implement with an async refine: $ZodAsyncError on both (matches schema.parse)
- implement(123): same plain Error message
- implemented fn: _zod === schema._zod, non-enumerable, name "" and length 0 on both (still anonymous)

## Residual notes (not blocking; for A/C)
- The override copies core's 35-line bodies. If core's implement changes later, the classic copy can drift. An alternative would be a core hook (inject the parse functions or an Err class), but that is a larger change.
- Each classic ZodFunction instance now allocates the core closures and then replaces them. Cost is per schema, not per call. Negligible.
- The fix drops core's comment about keeping the closure anonymous. Behaviour is preserved (name ""), but the reason is not in the classic copy.
