# EXEC-A results (executor). Scratch: /tmp/adonreview/scratch/EXEC-A/<ID>/ (base copy + patch, node_modules symlinked to /tmp/adonw's)

Method: per ID, copy base, `git apply --include='tests/*'` -> run the patch's spec file (RED); `git apply --exclude='tests/*'` -> same file (GREEN); `git apply -R --exclude='tests/*'` -> same file (REVERT); re-apply, run the full suite; `tsc --noEmit -p .`; eslint on the patch's two files; confirmer repro from /tmp/adonv/BUG-NNN/repro.ts run against base (/tmp/adonw) and fixed copy (paths sed-rewritten). Verbatim red assertion text in the table.

| ID | red (assertion text) | green | revert | suite | tsc | PASS/FAIL |
|---|---|---|---|---|---|---|
| uuid-matcher | `AssertionError: expected true to be false` (1 failed/5) | 5/5 | same failure | 661/0 | exit 0 | PASS |
| redirect-qs-separator | `expected '/foo?username=virk?age=28' to equal '/foo?username=virk&age=28'` | 28/28 | same | 661/0 | 0 | PASS |
| cookie-maxage-zero | `expected undefined to equal 'Max-Age=0'` | 12/12 | same | 661/0 | 0 | PASS |
| toroute-qs-mutation | `expected '/posts/1' to equal '/posts/1?published=true'` | 28/28 | same | 661/0 | 0 | PASS |
| send-error-object | `expected "content-type" of "text/plain; charset=utf-8", got "application/json; charset=utf-8"` | 95/95 | same | 661/0 | 0 | PASS |
| lookup-route-error | `expected [Function] to throw 'Exception' but 'Error: Cannot lookup route "posts.sho...' was thrown` | 78/78 | same | 661/0 | 0 | PASS on the new test; PR claim incomplete (see below) |
| unknown-content-type | `expected "content-type" of "application/octet-stream", got "false"` | 95/95 | same | 661/0 | 0 | PASS |
| reset-content-body | `expected '11' to equal '0'` (content-length) | 95/95 | same | 661/0 | 0 | PASS |

eslint: exit 0 on all 16 changed files. Every red fails for the claimed reason. Confirmer repros: base exits 1 (BUG PRESENT) and fixed exits 0 for 7 of 8; lookup-route-error fixed still exits 1 (BUG PRESENT).

### uuid-matcher
Verdict: SHIP
Confidence: high
Findings:
1. Repro fixed: `matcher.test(zzzzzzzz-...) = false`, `router.match(/posts/gggggggg-...) => null`. Test asserts both z and g.
2. Existing uppercase test (matchers.spec.ts ~L35) still passes; no behaviour change for valid UUIDs. Only users relying on non-hex ids matching are affected; PR does not mention it (optional one-liner).
3. The "(it looks like a typo from #53...)" aside is unverified by me (S7 territory); trim it if not checked.

### redirect-qs-separator
Verdict: SHIP
Confidence: medium
Findings:
1. Repro fixed gives `Location = /foo?a=1&b=2`, control unchanged. Green/revert as required.
2. `url.includes('?')` also matches a `?` inside a `#fragment` (`/foo#a?b`) and a trailing bare `?` (`/foo?` becomes `/foo?&b=2`). Neither is tested; I did not run them. Not regressions vs base (base was also wrong) but the PR says "leaving the target's existing query text untouched" without scope. Acceptable; mention or ignore.

### cookie-maxage-zero
Verdict: SHIP
Confidence: medium
Findings:
1. Repro fixed: `Max-Age=0` emitted for 3/3 cases, `Max-Age=60` unchanged. Test goes through CookieSerializer.encode; the PR's example uses `response.plainCookie` but the repro covers that path (b/c/d cases).
2. src/helpers.ts: `options.maxAge || options.maxAge === 0 ? ... : undefined` is correct but reads awkwardly; `options.maxAge !== undefined && options.maxAge !== null && options.maxAge !== ''` would change other falsy cases, so the narrow form is defensible. Maintainer may ask for `options.maxAge === 0 ||` ordering or a one-line comment; not blocking.
3. PR claims "config default maxAge also lost" and "clearCookie already relies on an expired Max-Age": I did not verify either.

### toroute-qs-mutation
Verdict: FIX-REQUIRED
Confidence: high
Findings:
1. Code is right: repro base `[ '302 /new?a=1', '302 /new', '302 /new' ]`, fixed `[ .../new?a=1 x3 ]`, options object unchanged afterward.
2. Title and commit subject say `fix(response)` but the change is in src/redirect.ts only. Use `fix(redirect): ...` (nearby history uses `redirect` scope words, e.g. "feat(router): forward query string in declarative redirects"). Must change in both the commit and PR title.
3. `const { qs, ...urlOptions } = options || {}` now always passes an object (`{}`) to urlFor where base passed `undefined` when no options were given. Suite passes (661), so harmless, but mention nothing; just be aware.

### send-error-object
Verdict: FIX-REQUIRED
Confidence: medium
Findings:
1. Functionally passes (repro: `Error -> text/plain "Error: boom"`, `TypeError -> "TypeError: bad"`). The doc sentence is verbatim at reference_docs/cite/v6-docs_basics_response.md:319 ("Regular expressions and error objects are converted to a string by calling the `toString` method.").
2. Undisclosed behaviour change: `content instanceof Error` now precedes the `dataType === 'object'` JSON branch, so an Error subclass that defines `toJSON()` or enumerable fields (previously serialized through `serializeJSON`) is now sent as `String(err)`. From reading src/response.ts ~L307; I did not run a test. The PR should state this and the test should include one subclass case, or the condition should be narrowed. Note also the sent text now exposes `message` to the client where before it sent `{}`; say so in one line (docs cited are v6 docs; say so).
3. Test placed mid-file between "get regexp" and "parse array"; fine. Only asserts content-type and text; no subclass case.

### lookup-route-error
Verdict: FIX-REQUIRED
Confidence: high
Findings:
1. Incomplete relative to the documented contract. Confirmer repro on the FIXED tree still reports BUG PRESENT: `router.urlBuilder.urlFor("missing") -> Error "Cannot lookup route \"missing\"" code= undefined status= undefined instanceof E_CANNOT_LOOKUP_ROUTE= false`. src/client/url_builder.ts:54 and :56 still `throw new Error(...)`. The docs sentence the PR cites (reference_docs/cite/v6-docs_references_exceptions.md:140) says the error is raised "when you attempt to create a URL for a route using the URL builder", which is exactly this path (also what `Redirect#toRoute` calls). Fix both throw sites (import the error in client/url_builder.ts) and add a urlFor assertion, or narrow the PR title/body to findOrFail and say urlBuilder is untouched.
2. PR sentence "This also covers makeUrl, the legacy builder and signedUrlFor, which go through findOrFail" is true for makeUrl (main.ts:768), makeSignedUrl (main.ts:796) and signed_url_builder.ts:61, but the reader will take it to include the modern URL builder. Reword.
3. `new E_CANNOT_LOOKUP_ROUTE([id])` then overwriting `error.message` for the method variant works (stack header verified: `Exception: Cannot lookup route "u" for method "POST"`) but is a hack; a maintainer may prefer a second error or an extended message template. Low priority.
4. Observable change: messages identical, but `ExceptionHandler.shouldReport` now returns false for these errors (repro: true before, false after) because E_CANNOT_LOOKUP_ROUTE is in ignoreExceptions (src/exception_handler.ts:97). Errors from bad route names will stop being reported/logged. PR must say this.

### unknown-content-type
Verdict: SHIP
Confidence: medium
Findings:
1. Repro fixed: `type('.nope')` and download of extension-less LICENSE give `application/octet-stream`; controls for .txt and plain send unchanged. Test asserts content-type and content-length and body.
2. The "as Express's res.type() does" claim: I did not verify it. Drop or have S7 verify.
3. `response.type('')` or other falsy input also gets octet-stream now; not tested, not in PR. Fine.

### reset-content-body
Verdict: FIX-REQUIRED
Confidence: medium
Findings:
1. Repro fixed: 205 has `content-length: 0`, no content-type, empty body, and the follow-up request on the same socket parses correctly (keep-alive framing intact). Base carried 9 bytes.
2. Only `send(string)` is covered. Not tested: `resetContent()` (PR claims it "now takes the same path", was chunked before), HEAD, and streams/`download` with a 205. Add a `resetContent()` test or drop the claim.
3. The new block sits after the 1xx/204/304 branch and before the `hasEmptyBody` branch, so an empty 205 now also gets `Content-Length: 0` (previously the `hasEmptyBody` path removed Content-Length). That is a header change for existing empty-205 users; PR says so only for resetContent. State it.
4. Comment wording "As per https://www.rfc-editor.org/rfc/rfc9110#section-15.3.6. Node does not..." is a run-on; split the sentences. RFC quote in PR body unverified by me.

## Summary
- All 8 tests fail for the stated reason without the fix, pass with it, fail again on revert; suite 661/0, tsc and eslint clean on every tree.
- Clean to send: uuid-matcher, redirect-qs-separator, cookie-maxage-zero, unknown-content-type.
- Must change first: lookup-route-error (urlBuilder.urlFor still throws plain Error; repro still fails), toroute-qs-mutation (wrong `response` scope), send-error-object (undisclosed toJSON/subclass change), reset-content-body (untested resetContent claim, undisclosed empty-205 header change).
