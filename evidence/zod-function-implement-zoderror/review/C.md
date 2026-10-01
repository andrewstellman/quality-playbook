# BUG-015 review C (TEXT)  Verdict: FIX-REQUIRED (text and test formatting only; code not judged here)

Checked PR-DRAFT.md, the commit message and the test against `git show`, core/schemas.ts:4882-4936, the confirmer's REPORT.md, api.mdx:3444 and changelog.mdx:215-216.

## Verified true
- Core implement/implementAsync use core parse/parseAsync (core/schemas.ts:4882-4915). True.
- `_zod.parse` calls `inst.implement` / `inst.implementAsync` (core/schemas.ts:4934-4936), so the object-schema claim holds.
- api.mdx:3444 says "This function will throw a `ZodError` if the input is invalid". Quote is accurate.
- Zod Mini is untouched by the diff. True.
- The test covers bad arg and bad return, sync and async, as the PR says.

## Problems
1. **Changelog claim overreaches (PR line 1).** changelog.mdx:215-216 are comments on two removed issue types in a `ZodIssue` union ("z.function throws ZodError directly"). They are not a statement about the class thrown by an implemented function. Drop the changelog citation; the api.mdx sentence carries the argument on its own.
2. **Padding and restatement.** The PR body re-narrates the diff ("This change re-wires ... to the classic parse/parseAsync") and the final sentence ("The new test pins ...") describes the test. Delete both. The 'cause' sentence is useful but wordy.
3. **"never swapped them ... the way ZodType.parse does"** is a claim about design intent/history that nobody checked. Say what the code does, not what it "never" did.
4. **Attribution line** ("Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.") is trailing prose glued to the last paragraph. Keep the disclosure if the campaign requires it, but as its own line after a blank line. Not verifiable by me either way.
5. **Commit message** is fine on the subject. Body's "unlike schema.parse" is ok; "lacked .format()/.flatten()" is true of $ZodError only if those are classic-only (REPORT says so). Acceptable, but shorten.
6. **Code comment** in classic/schemas.ts is one very long line and explains what and why in a single run. Shorten to `// Core's implement/implementAsync throw $ZodError; use the classic parsers so ZodError is thrown.`
7. **Test formatting:** no blank line between the new test and `test("function inference 1"` (neighbours are separated by one). Add it.
8. **Test naming/behaviour:** name matches neighbours' plain style; asserts class, not implementation. Good. Optional: a maintainer may prefer `.flatten()` asserted once, since the reported harm is missing methods; not required.
9. `as any` casts in the test: `"nope" as any` matches neighbours' `13 as any`; fine.

## Proposed replacement PR text
Title: fix(function): throw ZodError from implement() and implementAsync()

A function created with `z.function({ input: [z.string()], output: z.number() }).implement(...)` throws a core `$ZodError` on a bad argument or return value. `err instanceof z.ZodError` is false and `.format()` / `.flatten()` are missing. `implementAsync` rejects with the same error. The docs say the function "will throw a `ZodError` if the input is invalid" (api.mdx), and `schema.parse` throws `ZodError`.

Core `implement`/`implementAsync` validate with the core `parse`/`parseAsync`, which throw `$ZodRealError`. The classic `ZodFunction` now overrides both to use the classic `parse`/`parseAsync`. Parsing a function through another schema goes through `inst.implement`, so it is fixed too. Zod Mini is unchanged.

(blank line)
Found with Quality Playbook (AI code review) and Claude; I reviewed the change.

## Proposed commit body
Core implement/implementAsync validate with the core parsers, which throw $ZodError rather than ZodError. Override them in the classic ZodFunction to use the classic parsers.
