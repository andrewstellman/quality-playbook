# BUG-003 review C (TEXT)

Verdict: FIX-REQUIRED (text only; diff and test are fine to ship).

Checked: new test fails on base ("Unmergable intersection") and passes on fix (20/20). Changelog quote (changelog.mdx:737) is accurate. compile.ts:1933 does reuse mergeValues, so the compiled-path claim is true structurally.

Problems in PR-DRAFT.md
1. One 200-word paragraph that narrates the diff ("The change extends the equality check...", "The new test ... pins all three inputs"). The last sentence restates the diff; the "unlike Object.is" aside is defensible but only matters if a reviewer asks.
2. Overclaim / against the confirmer's advice: "safeParse is documented (basics.md) to return a result object rather than throw". basics.mdx:114 only says safeParse avoids a try/catch for validation errors; it does not promise it never throws, and the changelog says unmergable throws by design. The report said explicitly: do not frame as "safeParse should never throw". Cut that clause.
3. "the sharpest form of this is that z.nan().and(z.nan()) can never be satisfied" is clumsy and is the report's opinion, not evidence-neutral. Keep the fact, drop "sharpest form".
4. "compile.ts reuses the same mergeValues, so the compiled path is covered" is true of the code but no test exercises z.compile. Say "shares" without "covered", or drop it (it is padding for a one-line change).
5. Ambiguity: "both operands pass the same NaN through" is fine, but the NaN-in-loose-object case is hand-wavy; say "an unrecognized key holding NaN".
6. The "Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change." line is a disclosure, not a claim about the diff; OK if the author wants it, but it is not traceable to anything in the diff and reads as boilerplate. Author's call. Also no "Fixes #" line: report says no upstream issue, so that is correct.

Proposed replacement body:

  `mergeValues` decides two values are the same with `a === b`, which is false for NaN. When both sides of an intersection produce NaN, the merge is classed as unmergable and `safeParse` throws `Unmergable intersection`:

  ```ts
  z.nan().and(z.nan()).safeParse(NaN);
  z.unknown().and(z.unknown()).safeParse(NaN);
  z.looseObject({ a: z.string() }).and(z.looseObject({ b: z.string() })).safeParse({ a: "x", b: "y", c: NaN });
  ```

  The changelog reserves that throw for "an intersection of two incompatible types". Two NaNs from the same input are not incompatible; `z.nan().and(z.nan())` currently cannot accept any value. The check now also accepts NaN on both sides. `0` and `-0` still merge as before (`Object.is` would have split them).

Commit message: accurate and short. Nits: "loose object intersection whose passthrough key holds NaN" is fine; "nothing that merged before changes" is true (added disjunct only widens equality for NaN pairs). Keep.

Test: name "identical NaN merges" fits the terse neighbours. Placement is between "invalid array merge" and "invalid object merge", i.e. inside the run of failure-case tests; it is a success case, so move it after "deep intersection of arrays" (before "invalid intersection types", ~line 137). Assertions check behaviour (result data), not implementation. Suggest also asserting nested (e.g. inside an array element) is unnecessary; skip.

Code comment "NaN !== NaN, but two NaNs from the same input are not a conflict." is true and useful; "from the same input" is slightly off for the unknown/nan cases but harmless.
