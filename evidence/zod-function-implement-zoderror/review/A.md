# BUG-015 review A (MAINTAINER): SHIP, with two optional nits

Diff: fix-015 @ 6ead1ad2, +37 lines in classic/schemas.ts (ZodFunction init), +12 lines in classic/tests/function.test.ts.

## Is it correct?
- Yes. Core $ZodFunction (core/schemas.ts:4882-4917) calls core parse/parseAsync, which are bound to $ZodRealError (core/parse.ts:39,63). The override calls classic parse.parse/parseAsync, which are bound to ZodRealError (classic/parse.ts:13,20). That's the same mechanism schema.parse uses.
- I checked each of these against the fix with tsx:
  - The thrown error passes `instanceof z.ZodError`, still passes `instanceof z.core.$ZodError`, and has `.flatten`.
  - A function nested in z.object(...).parse throws ZodError. core `_zod.parse` goes through `inst.implement`, so it picks up the override.
  - `.input([...]).implement` throws ZodError, because `new F` uses inst.constructor, which is ZodFunction.
  - `this` still binds through Reflect.apply.
- function.test.ts passes on the fix: 22/22.
- I found no case where the old behaviour was right and the new one is wrong.
  - The docs (api.md "will throw a `ZodError`") and the v4 changelog ("z.function throws ZodError directly", lines 215-216) both promise ZodError.
  - No existing test pins $ZodError. The only failure tests (function.test.ts:21,27) use a bare `.toThrow()`.
  - zod/mini is untouched and keeps $ZodError. That matches how mini behaves everywhere else.
- It doesn't change a deliberate design. `git log -S implementAsync` shows no commit choosing $ZodError for classic. Classic is meant to throw ZodError, and it already does that by binding core._parse(ZodRealError) in classic/parse.ts.

## Is it the smallest change, and written the way the file writes code?
- The objection Colin is most likely to raise is duplication. The override is a line-for-line copy of core's 35-line implement/implementAsync, with only `parse`/`parseAsync` swapped for `parse.parse`/`parse.parseAsync`. From now on, any fix to core's copy (the `this` handling, the `_zod` defineProperty, the non-function guard) has to be made twice.
- The only smaller fix touches core. core._parse already accepts `_params.Err` (core/parse.ts:30), so core's closures could pass an error class that classic sets. That needs a new internal hook on $ZodFunction, which is a design change in core. A maintainer can reject that more easily than a classic-only override.
  - The classic layer already follows the pattern this PR uses: wire core behaviour to ZodRealError on the classic side (classic/parse.ts).
  - So I'd accept the duplication and not ask for the core hook. If Colin prefers a core hook, that's a reasonable request for a follow-up, not a reason to hold this PR.
- Style matches the file. The closures are inline and anonymous, so they keep core's bundle-size property ("binding it to a `const` first names it"). They use `inst._def`, which is safe after core init because `_def` is defineProperty'd there. The long single-line comment matches how core writes its comments.
- Cost: every classic ZodFunction instance allocates core's two closures and then replaces them. That's negligible.

## Nits (optional, not blocking)
1. function.test.ts: add a blank line between the new test's closing `});` and `test("function inference 1"`. Every other test in the file is separated by one.
2. The new comment could note that the body mirrors core's $ZodFunction, so the two copies get kept in sync. For example, append: "Mirrors core's $ZodFunction implement/implementAsync; keep in sync."

## Verdict
SHIP. I'd merge it as it is, or after the two nits. It's correct, limited to classic, backed by the docs and changelog, and it has a regression test that covers all four paths (sync/async × args/return).
