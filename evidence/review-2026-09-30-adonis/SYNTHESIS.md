# adonisjs/http-server: panel synthesis (2026-09-30)

Eight fixes, each confirmed by an independent confirmer, then fixed by a fixer (test first, red/green/revert, full suite 661/0, tsc, eslint, prettier). Panel: two red/green executors (Sonnet) and 13 blind personas (O1-O5 Opus, S1-S8 Sonnet), each reviewing all eight. Every raw review is in this folder.

## Executors
Both executors independently: every new test fails on base for the claimed reason (assertion text quoted), passes with the fix, fails again when only the source change is reverted; full suite 661 passed / 0 failed on every fixed tree; tsc, eslint, prettier clean. All eight stack without conflict (668 passed with all applied, O3). Confirmer repros flip on seven of eight; lookup-route-error's repro still fails because `urlBuilder.urlFor` is untouched.

## Verdict matrix (S = SHIP, F = FIX-REQUIRED, R = REJECT)

| Fix | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| uuid-matcher | S | S | S | S | S | S | S | S | S | F | S | S | S | F | S |
| toroute-qs-mutation | F | S | S | S | S | S | F | F | S | S | S | S | S | S | F |
| unknown-content-type | S | S | F | S | S | S | F | F | F | F | S | S | S | F | F |
| cookie-maxage-zero | S | F | F | S | F | F | F | F | S | F | F | F | S | F | S |
| redirect-qs-separator | S | S | S | F | S | F | S | F | F | F | F | S | S | S | S |
| reset-content-body | F | S | S | S | F | F | F | F | F | F | F | F | S | F | F |
| lookup-route-error | F | F | F | F | F | F | F | F | S | F | F | F | S | F | F |
| send-error-object | F | F | R | F | F | R | F | S | F | S | F | F | S | S | F |

## Disposition

**Ready after the text-only changes already applied (v2 PR text in each evidence folder):**
- uuid-matcher. S3/S7 only questioned "typo from #53"; O4 verified #50 asked for `[0-9A-Fa-f]` and thetutlage agreed, and #53 landed `a-z`. Text now states that and drops the RFC sentence.
- toroute-qs-mutation. Scope changed to `fix(redirect)` (5 reviewers). Diff-restating text and padding doc quote cut.
- unknown-content-type. RFC §8.3 sentence cut (wrong section, doesn't support the fallback). Express precedent kept (verified in Express source by S7, O4). States that direct `type()` calls change too.
- cookie-maxage-zero. Five reviewers found the undisclosed compat change: config `cookie: { maxAge: 0 }` now emits `Max-Age=0` on every cookie. Now stated. The misleading clearCookie sentence (clearCookie uses -1, never hit this) and the doc quote are cut.

**Needs a code revision and a second review:**
- redirect-qs-separator. O2: with query forwarding on, a forwarded request param now becomes a real duplicate of a key the developer hard-coded in the target (`/login?role=user&role=admin`; last-wins parsers read `admin`). Before, it was one garbled value. O4 also expects the maintainer to ask why the existing `appendQueryString` helper isn't used. Needs a merge-and-dedupe decision (developer's inline values win), plus a forwarding test.
- reset-content-body. `stream()` and `download()` still send a body with 205, so the title overclaims (O3, S4, S5); the `resetContent()` claim is untested (A, S1, S3, S4); S7 found the "unframed" justification overstated (bare Node already sends `content-length: 0`). O4: `resetContent()` is the intended 205 API and `send(body)` with 205 is caller error. Scope to `send()` and fix the text, or drop.

**Ask first (issue, not PR):**
- lookup-route-error. The regression is real (v7 threw the typed error from `route_finder.ts`; core#4456), but the fix misses `urlBuilder.urlFor` (src/client/url_builder.ts), which is the path the cited doc describes and `redirect().toRoute` uses; that module is deliberately dependency-free, so the right fix is a maintainer design call. It also silently stops logging these 500s (`ignoreExceptions`). File an issue describing both.

**Drop:**
- send-error-object. O1 and O4 reject; O2 found it opens a JSONP script-injection path (`jsonp(err)` emits `cb(<message>)` unquoted) and bypasses sanitizing `toJSON`; O3/S4/S5 show real Errors with fields (validation errors, poppinss Exceptions) regress from JSON to text; O4 found the "error objects ... toString" sentence is gone from the current v7 docs, and the code never behaved that way. Not a bug worth a PR.

## Process (S8)
adonisjs has no AI policy and no DCO/CLA. The org PR template asks for a linked issue, but the two most recent merged outside bug fixes (#138, #139) used a short Problem / Fix / Testing body with no linked issue; the v2 texts follow that. Send one or two at a time (O1, S8).
