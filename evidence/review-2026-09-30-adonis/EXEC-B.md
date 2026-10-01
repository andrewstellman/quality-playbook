# EXEC-B report (executor; scratch trees in /tmp/adonreview/scratch/EXEC-B/<ID>/, edge scripts in .../edge/)

Method: per ID, copy of /tmp/adonw (node_modules symlinked), split fix.patch into test part and src part (run.sh). Red = test part only; green = both; revert = src reverted; suite run serially (a first parallel run hit EADDRINUSE :3000, so suites were re-run one at a time); tsc, eslint, prettier --check on touched files; confirmer repro from /tmp/adonv/BUG-NNN run on base and fixed.

| ID | red (assertion text) | green | revert | suite | tsc | eslint/prettier | repro on fixed | result |
|---|---|---|---|---|---|---|---|---|
| uuid-matcher | "expected true to be false" (matchers.spec.ts:41, zzzz UUID) | 5/5 | fails | 661/0 | 0 | clean | bug absent | PASS |
| redirect-qs-separator | "expected '/foo?username=virk?age=28' to equal '/foo?username=virk&age=28'" | 28/28 | fails | 661/0 | 0 | clean | no bug | PASS |
| cookie-maxage-zero | "expected undefined to equal 'Max-Age=0'" | 12/12 | fails | 661/0 | 0 | clean | OK | PASS |
| toroute-qs-mutation | "expected '/posts/1' to equal '/posts/1?published=true'" (2nd request) | 28/28 | fails | 661/0 | 0 | clean | no bug | PASS |
| send-error-object | `expected "content-type" of "text/plain; charset=utf-8", got "application/json; charset=utf-8"` | 95/95 | fails | 661/0 | 0 | clean | OK | PASS |
| lookup-route-error | "expected [Function] to throw 'Exception' but 'Error: Cannot lookup route "posts.show"' was thrown" | 78/78 | fails | 661/0 | 0 | clean | **still prints BUG PRESENT**: urlFor unchanged | PASS (mechanical), see finding 1 |
| unknown-content-type | `expected "content-type" of "application/octet-stream", got "false"` | 95/95 | fails | 661/0 | 0 | clean | bug absent | PASS |
| reset-content-body | "expected '11' to equal '0'" (content-length) | 95/95 | fails | 661/0 | 0 | clean | OK, 205 then 200 framed on one connection | PASS |

Every red failure is for the claimed reason (the new test only; all other tests in the file passed in the red run).

## Verdicts (formed from patch, PR text and source before reading CONFIRMATION.md)

### uuid-matcher
Verdict: SHIP
Confidence: high
1. Edge (base -> fixed): `abcdef01-2345-6789-abcd-ef012345678g` true -> false; uppercase-valid `ABCDEF01-...` true -> true; nil UUID true -> true; trailing "\n" false -> false. Only g-z lowercase changes.
2. PR #53 (merged 2022-02-25, "support UUIDs as per RFC spec (#50)") exists, so "typo from #53" is supportable. Drop "it looks like" hedging or keep; either is fine. Anyone routing g-z "uuids" stops matching (intended).

### redirect-qs-separator
Verdict: SHIP
Confidence: medium
1. Edge (base -> fixed): `/foo?` + b=2: `/foo??b=2` -> `/foo?&b=2`; `/foo?a=1&`: `?a=1&?b=2` -> `?a=1&&b=2`; `/foo?a=1#frag`: `#frag?b=2` -> `#frag&b=2` (qs still lands inside the fragment; was already wrong, not made worse).
2. Existing helper `appendQueryString` (src/helpers.ts:321) merges queries but is lossy: `/foo#frag` becomes `/foo?frag=&a=2&b=3` and `/foo?a=1#frag` drops the fragment (my run). Reviewer will ask "why not the helper"; one sentence in the PR ("keeps the target's query text as written") answers it.
3. Colliding keys are not merged: target `?a=1` plus withQs('a',2) yields `a=1&a=2`. State it or leave it.

### cookie-maxage-zero
Verdict: FIX-REQUIRED
Confidence: medium
1. Undisclosed behaviour change. `defineConfig({cookie:{maxAge:0}})` (normalised cfg keeps 0; src/define_config.ts:101 also uses truthiness) used to give session cookies and now gives `Max-Age=0` on every cookie set via response.cookie()/plainCookie()/encryptedCookie() (run: base `k=...; Path=/; HttpOnly; Secure; SameSite=Lax`, fixed `k=...; Max-Age=0; Path=/; ...`). Someone using 0 as "no default 2h" (cf. issue #108, users wanting session cookies) is silently broken. PR must say this, or the fix must be limited to per-call options.
2. String forms still throw: `maxAge:'0'` and `'0s'` -> `Invalid duration expression` in base and fixed. PR says "treats 0 as a valid value"; say "number 0".
3. PR sample comment "(session cookie; config default maxAge also lost)" is confusing; remove the parenthetical.
4. Condition `options.maxAge || options.maxAge === 0` is clumsy; `options.maxAge !== undefined` would also change null/''/false/NaN (they currently drop, and `-0` now emits Max-Age=0). Keep as is, but mention falsy others unchanged (PR already does).

### toroute-qs-mutation
Verdict: SHIP
Confidence: high
1. Edge (base -> fixed): frozen options `Object.freeze({qs:{a:1}})`: base throws "Cannot assign to read only property 'qs'", fixed `/posts/1?a=1`. `toRoute(..)` with no options and `{qs:{}}`: `/posts/1` unchanged. `{prefixUrl:'http://x.com', qs:{a:1}}`: `http://x.com/posts/1?a=1` unchanged.
2. Title scope: change `fix(response):` to `fix(redirect):` (file is src/redirect.ts; the sibling PR already uses fix(redirect)). Applies to the commit subject too.
3. `options || {}` now passes `{}` to urlFor instead of undefined; no observable difference in my runs.

### send-error-object
Verdict: FIX-REQUIRED
Confidence: high
1. Overrides a user-defined `toJSON` (src/response.ts:307, the new `instanceof Error` branch precedes the object/JSON branch). Run: `e.toJSON=()=>({message:'public',code:'E1'})`; base `200 application/json {"message":"public","code":"E1"}`, fixed `200 text/plain "Error: secret"`. Guard with `typeof content.toJSON !== 'function'` (or document precedence) and add a test.
2. Existing behaviour for errors with enumerable props changes: `@poppinss/utils` Exception with status/code: base `{"name":"Exception","status":400,"code":"E_X"}` application/json; fixed `text/plain "Exception [E_X]: bad"`. `Object.assign(new Error('with'),{status:418,extra:1})`: base `{"status":418,"extra":1}`, fixed `Error: with`. The PR frames this as `{}` -> string only; it must state that JSON becomes text/plain for every Error.
3. Information exposure now possible: message text reaches the client where `{}`/props did before. Apps doing `response.send(error)` in a catch block start echoing messages. Say so in the PR (it is what the docs specify, which is the justification).
4. `response.json(err)` is an alias of send (src/response.ts:892) so it now returns text/plain too; a `serializeJSON` configured to handle Errors is bypassed. Mention or restrict to send.
5. Expect the maintainer option "fix the docs instead" (docs line 319). The PR should say why behaviour, not docs, should change.

### lookup-route-error
Verdict: FIX-REQUIRED
Confidence: high
1. Incomplete vs the PR's own framing: `router.urlBuilder.urlFor('nope')` still throws a plain Error (src/client/url_builder.ts:54,56); confirmer repro on the fixed tree still prints `BUG PRESENT`. Covered after fix: findOrFail, makeUrl, makeSignedUrl, signedUrlFor, builder().make (all `code=E_CANNOT_LOOKUP_ROUTE status=500`). PR must say urlFor is intentionally untouched (client module is dependency-free) or fix it.
2. Undisclosed consequence: E_CANNOT_LOOKUP_ROUTE is in `ignoreExceptions` (src/exception_handler.ts:97), so a typo'd route name in makeUrl/redirect().toRoute inside a controller is no longer reported/logged (it was before, as a plain Error). The PR cites ignoreExceptions as support but omits this. Either state it or drop the claim.
3. `error.message = ...` reassignment after construction for the "for method" variant is a hack (template is `Cannot lookup route "%s"`, src/errors.ts:41). Ask whether a second error or an options override is preferred; at minimum comment it.
4. Red only exercised the first assertion; the POST-variant assertion was never red on its own. Split into two tests.

### unknown-content-type
Verdict: SHIP
Confidence: medium
1. Edge (base -> fixed): `type('')`, `type('.nope')` false -> application/octet-stream; `type('json')` and `type('text/plain','utf-8')` unchanged; `type('plain/text')`, `type('application/x-foo')` unchanged.
2. Masking case: `type('html','utf-8')` and `type('.nope','utf-8')` were `false`, are now `application/octet-stream`, because charset is appended before lookup (`html; charset=utf-8` is not resolvable). Not a regression, but the PR's "as Express does" is not exact (Express only looks up when there is no "/"). Soften to "falls back to octet-stream".
3. Test writes `LICENSE` under BASE_PATH; teardown removes BASE_PATH (tests/response.spec.ts:37), so no leak. Only the download path is tested, not `type()` directly.

### reset-content-body
Verdict: SHIP
Confidence: medium
1. Justification verified: one-line variant (add ResetContent to the existing 1xx/204/304 list, scratch variant205/) produced `HTTP/1.1 205 ... \r\n\r\n` with no Content-Length and no Transfer-Encoding, and the next pipelined response never arrived. So the explicit `Content-Length: 0` is needed. Fixed tree: 205 (`content-length: 0`) then 200 on one connection, correct. RFC 9110 15.3.6 quote is verbatim (checked against rfc9110.txt); 8.6 forbids Content-Length only on 1xx/204.
2. Edge (base -> fixed), all become `205, content-length 0, no content-type, empty body`: send(obj), send(null), resetContent() (was chunked), send with etag, json(), jsonp() (was text/javascript body), preset Content-Length 99. HEAD: 205 cl 0. Custom `Content-Type: x/y` is removed too.
3. Compat to state: apps that send a body with 205 lose it; resetContent() changes chunked -> Content-Length: 0 (PR states the latter). `stream`/`download` with 205 bypass writeBody and are unchanged.
4. Comment wording "As per <url>." copies the neighbour but reads as a fragment; rewrite as one sentence.

## After reading CONFIRMATION.md
No verdict changed. Confirmer's own pushbacks match mine: client url_builder dependency-free (lookup), toJSON precedence undecided (send-error), CL:0 vs strip/chunked concern (205; my wire test settles it). Not in CONFIRMATION and found here: cookie config maxAge:0 flip, ignoreExceptions silencing, Error.toJSON override.

## Summary
1. All 8 fixes: red for the claimed reason, green, red again on revert, suite 661/0, tsc/eslint/prettier clean, confirmer repros flipped (except lookup-route urlFor).
2. SHIP: uuid-matcher, redirect-qs-separator, toroute-qs-mutation (retitle fix(redirect)), unknown-content-type, reset-content-body.
3. FIX-REQUIRED (text and/or guard, not rewrite): cookie-maxage-zero (config maxAge:0 flip), send-error-object (toJSON override, JSON->text, message exposure), lookup-route-error (urlFor still plain Error, ignoreExceptions silences reports).
