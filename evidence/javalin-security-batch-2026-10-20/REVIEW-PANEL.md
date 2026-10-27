# Review panel: seven Javalin fixes (master 20ba71b)

Reviewer: independent code review, 2026-10-20. Read-only with respect to the source checkout and patches.

## How this review was done

- Read each patch in `out/*.patch`, the patched source in `src/` (line numbers below are into the patched working tree unless marked "master"), the BUGS.md entries and the challenge records.
- Checked the red, green and suite logs. All seven new tests fail on master with assertion errors (not compile errors), for example `final.red.log:75-77` (SSE: `Expecting empty but was: ["data: forged"]`). The suite result is `final.suite.log:1906`: 1020 tests, 0 failures, 5 errors, 2 flakes.
- Ran extra probes, using raw sockets so neither client normalises paths. These ran in a copy of the tree at `review/probe/` with a throwaway test, `review/probe/javalin/src/test/java/io/javalin/ReviewProbeTest.kt`. The probes ran against the patched sources (`review/probe.patched.log`) and against master sources (`review/probe.master.log`). SSE and HTML-escape output is in `review/probe-020-033.master.txt` and `review/probe-020-033.patched.txt`.
- Checked whether the patches apply. Each applies cleanly to master on its own. Applied one after another, the BUG-028 patch fails on `TestRequest.kt:18` because BUG-065 adds an import on the same line. A second-merged PR will need a trivial rebase.

Probe results that matter for the verdicts:

| Request | master | patched |
|---|---|---|
| `GET /%73ecret/file.txt` (before("/secret/*") guards it) | 200, file served | 404 |
| `GET //secret/file.txt` | **200, file served** | **200, file served** |
| `GET /./secret/file.txt`, `/x/../secret/file.txt`, `/secret;a=b/file.txt`, `/secret%2Ffile.txt`, `/%2Fsecret/file.txt`, `/secret%5Cfile.txt` | 404 | 404 |
| `GET /a+b.txt`, `/a%2Bb.txt`, `/caf%C3%A9.txt`, `/my%20file.txt` (knockon log) | 200 | 200 |
| `GET /a%7Eb.txt`, `/%41%31.txt`, `/plain%2Etxt` (existing files) | 200 | 404 |
| `HEAD /p/1` (GET `/p/{id}` with role A) | 200 | 401 |
| `HEAD /w/x/y` (GET `/w/*` with role A) | 200 | 401 |
| `HEAD /both` (GET with role A, plus an explicit HEAD route without roles) | 204 | 204 (HEAD route's own roles, correct) |
| `GET /p/1` with `X-HTTP-Method-Override: HEAD` | roles [] | roles [A], rejected |
| WS upgrade, enableBasicAuth, no credentials | 101 | 401 |
| WS upgrade, `Authorization: basic ...` (lowercase) | 101 | 101 (with BUG-065) |
| `sendComment("a\r\nb\rc\nd\n")` | `: a\r\n: b\rc\n: d\n: \n` | `: a\n: b\n: c\n: d\n: \n` |
| BadRequestResponse(`it's "x" & <b>`, details `k<` -> `v'>`), Accept text/html | raw | `it&#39;s &quot;x&quot; &amp; &lt;b&gt;` ... `k&lt;:` `v&#39;&gt;` |
| Same, no Accept header (text/plain) | raw | raw, unchanged |

---

## BUG-055: percent-encoded unreserved characters bypass path-scoped before-handlers for static files

Patch: `0001-Do-not-serve-static-files-whose-request-path-percent.patch`. Fix at `javalin/src/main/java/io/javalin/jetty/JettyResourceHandler.kt:29` (regex) and `:66-68` (early return in `findHandler`).

**1. Real? Correct and minimal?** Real. Routing matches against the raw `requestURI` (`http/Context.kt:104`, used at `http/servlet/JavalinServlet.kt:55`). `findHandler` passes the same raw string to Jetty's `Resource.resolve`, which decodes it. On master, `/%73ecret/file.txt` returns the file that `before("/secret/*")` is meant to block (probe, and `knockon.before.log`). Javalin sets `UriCompliance.LEGACY` (`jetty/JettyServer.kt:174-176`), so Jetty does not catch it.

The regex is exactly the RFC 3986 unreserved set. `[46][1-9a-f]` and `[57][0-9a]` cover A-Z and a-z, `3[0-9]` covers digits, and `2[de]`, `5f` and `7e` cover `-`, `.`, `_` and `~`. Matching is case-insensitive. Inputs it leaves alone: non-ASCII (`%C3%A9`), space (`%20`), a literal `+`, `%2B`, and `%2541` (an encoded `%` followed by `41`, which cannot match because the `%` before `41` is a literal character). All of these are served as before. Because `resourceRouteRoles` (`:79-80`) goes through the same `findHandler`, the role lookup and the served resource still agree.

**The fix is incomplete.** `GET //secret/file.txt` still returns the protected file on the patched tree. The router does not match `//secret/file.txt` against `/secret/*` (`treatMultipleSlashesAsSingleSlash` defaults to false, `config/RouterConfig.kt:33`), but `Resource.resolve` collapses the empty segment. Master has the same problem. It is the same class of bug (the router and the resource resolver disagree about which path a request names) and the same impact. Dot segments, `;` path parameters, `%2F`, `%5C` and upper-case variants all returned 404 in the probe, so the two gaps I found are encoded unreserved characters and empty segments. I did not test the Jetty-free resource handler for the `//` variant. BUGS.md says that handler does not decode, but it may still collapse slashes.

**2. Behaviour change for existing users.** Files are no longer served when the request over-encodes an unreserved character, for example `/a%7Eb.txt` for `a~b.txt` or `/plain%2Etxt`. These now return 404 instead of 200. Real clients do this occasionally: Python's `urllib.parse.quote` encoded `~` before 3.7, and some hand-rolled encoders encode `.` or `-`. A maintainer may notice this but is unlikely to block on it, because RFC 3986 §6.2.2.2 says such URIs should be normalised and they are rare. The other choice is to decode the unreserved characters and re-run routing, which is a much larger change.

**3. Test.** `TestStaticFiles.kt:182-188` uses the file's existing fixture (`defaultStaticResourceApp`, `public/protected/secret.html`) and sits next to the existing test it extends, `before-handler runs before static resources` (`:173-179`). It fails on master and passes with the fix. It pins the encoded-letter vector. Two weaknesses: it asserts only `doesNotContain("Secret file")`, so a 500 would also pass, and it does not cover `//`. Asserting the status (404) and adding the `//protected/secret.html` case would pin the whole class.

**4. Maintainer pushback.** The likely objections are these:
- "Use `staticFiles.roles` with `beforeMatched`; that is the documented access-control mechanism, and it is not bypassed." This is true, as the 2026-09-30 challenge record says. It does not settle the matter, though. The docs say before-handlers run "before every request (including static files)", and the project's own test `before-handler runs before static resources` (`TestStaticFiles.kt:173`) pins `before("/protected/*")` guarding a static subtree as supported behaviour. A tested, documented guard that a single encoded character defeats is a real bypass, not misuse.
- "This is a regex patch over a design gap; fix the normalisation once." A maintainer may prefer a general check: serve only when the path the resolver uses is the path the router saw. One way is to compare the decoded, slash-collapsed target with the raw target and refuse on any difference except encodings that must stay encoded (non-ASCII, space, reserved characters). That would close both vectors at once. The current patch fixes one vector and leaves the other open.
- Commit subject style. Upstream uses an `[area]` prefix, for example `[static-files] ...` (see `git log`).

**5. Severity.** Any unauthenticated remote client can read files under a static directory when the app protects a subfolder with a path-scoped `before()` handler instead of static-file roles. The attacker gets the file contents. No credentials or user interaction are needed. The precondition is a specific but documented and tested setup. **This warrants a private advisory.** It is the only one of the seven I would treat that way. Because the `//` variant is live on master and unfixed, a public PR for the `%XX` vector alone would point readers straight at the open variant. Report both privately and ship one fix that covers both.

**Verdict: APPROVE WITH CHANGES.**
- Required: close the empty-segment variant (`//secret/file.txt` serves the file on the patched tree). Either refuse targets that contain `//`, or switch to the general "decoded and normalised path must equal the routed path" check.
- Required: extend the test to assert the status code and to cover `//protected/secret.html`.
- Required: handle it as a private advisory covering both variants, not as a public PR.
- Suggested: use an `[static-files]` subject prefix and mention the over-encoded-unreserved 404 change in the PR or advisory text.

---

## BUG-028: BasicAuthPlugin lets requests through when no credentials are configured

Patch: `0001-Make-BasicAuthPlugin-reject-every-request-when-no-cr.patch`. Fix at `javalin/src/main/java/io/javalin/plugin/bundled/BasicAuthPlugin.kt:35-36`.

**1. Real? Correct and minimal?** Real. On master the comparison is `auth?.username == pluginConfig.username && auth?.password == pluginConfig.password` (master `BasicAuthPlugin.kt:30`). When there is no Authorization header and both config fields are null, this is `null == null && null == null`, which is true, so the request passes. The red log confirms it (`final.red.log:198-200`). The fix requires a non-null header and non-null configured fields, then compares. It is correct and minimal. Partial configurations (only one field set) were already rejecting every request, because parsed credentials are never null strings, and that does not change.

**2. Behaviour change.** An app that registers `BasicAuthPlugin { }` without setting both fields goes from fully open to 401 on every request. That is the intended direction, but it is silent: the app just locks everyone out, and nothing at startup says why.

**3. Test.** `TestRequest.kt:341-351` matches the neighbouring `basic auth filter plugin works` test, uses the same construction pattern, and pins exactly the null-config case. It also checks empty credentials (`basicAuth("", "")`), which is a sensible extra.

**4. Maintainer pushback.** The most likely request is to fail fast: `requireNotNull` (or a `JavalinException`) in `onStart` when either field is null. The challenge record's Round 2 suggests the same. That is more in keeping with how Javalin reports misconfiguration elsewhere (for example `getResourceBase` throws for a missing static directory), and it makes the lock-out visible. Either form would likely be accepted. Two practical points: this patch conflicts with BUG-065 on the `TestRequest.kt` imports, and it touches the same function as BUG-037, which duplicates the comparison (see BUG-037).

**5. Severity.** Only reachable through developer misconfiguration. The documented helper `enableBasicAuth(username: String, password: String)` (`config/BundledPluginsConfig.kt:39-43`) takes non-null values. The realistic case is a Java app doing `cfg.username = System.getenv("USER")` with the variable unset, which leaves the app open to anyone. **Ordinary bug fix (fail-closed hardening), public PR.** The challenge record's final MEDIUM is higher than its own Round 2 conclusion (LOW). LOW is the right rating.

**Verdict: APPROVE.** Suggested, not required: offer a fail-fast check in `onStart` as an alternative in the PR text. Rebase on BUG-065 or combine the two.

---

## BUG-050: HEAD requests skip the route roles of the GET endpoint that answers them

Patch: `0001-Apply-the-GET-route-s-roles-to-a-HEAD-request-it-ans.patch`. Fix at `javalin/src/main/java/io/javalin/http/servlet/DefaultTasks.kt:26-29`.

**1. Real? Correct and minimal?** Real. On master, a HEAD request with only a GET route has `httpHandlerOrNull == null`, so `isResourceHandler` is true and the request gets the static-resource roles (usually empty) instead of the GET route's roles. `beforeMatched` role checks then pass, and the HTTP task answers 200 (`DefaultTasks.kt:65-66`). The fix looks up the GET entry only for HEAD with no HEAD route, uses its roles, and stops treating that request as a resource request. That is now consistent with `willMatch` (`:102`) and with the HTTP task, which also never reaches the resource handler in this case.

Edge cases, all probed:
- When both GET and HEAD routes exist, `httpHandlerOrNull` is the HEAD route, `headViaGet` is null, and the HEAD route's own roles apply (204 in the probe). Correct.
- With path parameters (`/p/{id}`) and wildcards (`/w/*`), the GET lookup matches and roles apply (401).
- `X-HTTP-Method-Override: HEAD` on a GET is covered too, because `ctx.method()` honours the override (`http/Context.kt:101`).
- HEAD with no route at all still returns 404.

The lazy `headViaGet` only does extra work for HEAD requests without a HEAD route.

One small gap that is pre-existing and not made worse: for HEAD-via-GET, `beforeMatched` still sees no matched endpoint and no path parameters, because `:38-41` use `httpHandlerOrNull` rather than `httpHandlerOrNull ?: headViaGet`. The probe logged `pp={}` for `HEAD /p/1`. A `beforeMatched` handler that reads `ctx.pathParam("id")` on such a HEAD would throw. It is optional to fix here.

**2. Behaviour change.** A HEAD request to a role-protected GET route without credentials now gets the same 401 or 403 as GET, instead of 200. Uptime monitors or link checkers that HEAD protected URLs will see the change, and that is the point. Also, HEAD on a GET route no longer gets static-file roles. That was a mismatch, so the change is an improvement.

**3. Test.** `TestContextRouteRoles.kt:58-64` follows the file's pattern (`TestUtil.test`, `app.unsafe.routes`, role enum `A`). It checks the GET baseline and then HEAD, and pins exactly the bug. A path-parameter case would be a cheap addition but is not needed.

**4. Maintainer pushback.** There is little to object to. A maintainer might ask whether `matchedHttpEndpoint` and path parameters should also be set for HEAD-via-GET (the `:38` gap above). If so, it is a one-line follow-up.

**5. Severity.** Any client can send HEAD, but what it gets past the check is an empty 200. The GET handler never runs (`DefaultTasks.kt:65-66`), so no body and no handler-set headers are sent. The only information is that the route exists, and GET already reveals that (401 vs 404). Side effects in `beforeMatched` or `afterMatched` handlers would also run for an unauthorised HEAD. **Ordinary bug fix, public PR. Not a vulnerability.** The challenge record's final MEDIUM contradicts its own Round 2 (LOW). LOW is right.

**Verdict: APPROVE.** Optional: also pass `headViaGet` into the endpoint and path-parameter handling at `DefaultTasks.kt:38-41`.

---

## BUG-037: enableBasicAuth does not protect WebSocket upgrades

Patch: `0001-Make-enableBasicAuth-protect-WebSocket-upgrades.patch`. Fix at `javalin/src/main/java/io/javalin/plugin/bundled/BasicAuthPlugin.kt:27-31`.

**1. Real? Correct and minimal?** The behaviour is real: on master, an upgrade without credentials gets 101 and connects (probe). It is also documented and deliberate. The class KDoc says "Note: It does not apply to websocket upgrade requests" (`BasicAuthPlugin.kt:15-18`), and **the patch leaves that sentence in place, so after the patch the KDoc contradicts the code.** The user docs say "basic auth for all routes", which is where the bug report's argument comes from.

The mechanics are correct. Upgrades go through `JavalinJettyServlet.serviceWebSocketRequest`, which runs only `WEBSOCKET_BEFORE_UPGRADE` handlers (`jetty/JavalinJettyServlet.kt:81-82`) and no HTTP `before` handlers. The probe confirmed that `before` is not logged on an upgrade, so there is no double check. A rejection is turned into a 401 by `handleHttpException` (`:96-98`).

Ordering: the plugin registers its `wsBeforeUpgrade` in `onStart`, which runs after the user's config routes are added. In the probe, a user `wsBeforeUpgrade` registered in config ran on the unauthenticated, rejected request before the plugin rejected it. Any side effects in user upgrade handlers therefore happen before authentication. For a plugin that claims "all routes" this order is surprising, and it should be documented or the plugin handler should be registered first.

The credential comparison is copied from master's null-unsafe version: `it.username == pluginConfig.username && it.password == pluginConfig.password` (`:29`), not BUG-028's fixed version. It happens to fail closed, because parsed credentials are never null. Even so, there are now two hand-written copies of the auth check that already differ. A small private `credentialsMatch(ctx)` helper used by both handlers would remove that.

**2. Behaviour change. A maintainer is most likely to object here.** Every app that uses `enableBasicAuth` and also serves WebSockets will start rejecting upgrades that lack an Authorization header, and nothing lets them opt out. Browser `new WebSocket()` cannot set headers. Browsers often resend cached Basic credentials on a same-origin handshake, but not reliably and never cross-origin. Non-browser clients, and apps that authenticate WebSockets with a token query parameter while using Basic for pages, would break on upgrade.

**3. Test.** `TestWsUpgrade.kt:58-67` follows the file's pattern (`http.wsUpgradeRequest`, a `ConcurrentLinkedQueue` log). The negative half pins the bug. The positive half sends a Unirest GET with an Authorization header but without `Upgrade` or `Connection` headers. It asserts only that the status is not 401, and `log` stays empty, so it never shows that an authenticated client actually connects. A real WebSocket client with credentials, asserting `connected`, would make it a proper test. Minor style issue: it uses `java.util.Base64` fully qualified, while BUG-065's test imports it.

**4. Maintainer pushback.** Expect three questions: "This is documented as out of scope; why change the default?", "Where is the opt-out?", and "You left the KDoc saying the opposite." The maintainer may prefer a doc fix (correct "all routes"), an opt-in flag, or an opt-out flag. That choice belongs to upstream, so open an issue or a PR with a flag rather than a silent default change.

**5. Severity.** If an app relies on the "all routes" wording, anyone can open its WebSocket endpoints without credentials and get whatever the socket serves. But the limitation is stated in the plugin's own KDoc, and the project has a documented hook (`wsBeforeUpgrade`) for WebSocket auth. That makes it a documentation mismatch and a design choice, not a hidden flaw. **Ordinary bug or behaviour change, public issue or PR. Not an advisory.**

**Verdict: APPROVE WITH CHANGES.**
- Required: update the KDoc at `BasicAuthPlugin.kt:15-18`. It currently says the plugin does not apply to WebSocket upgrades.
- Required: add a config switch (for example `Config.protectWebSockets`; whether it defaults to on or off is for upstream to decide) or open it as an issue first. Do not change the default silently.
- Required: share one credential check between the HTTP and WebSocket handlers, using BUG-028's null-safe logic, so the two do not diverge. That probably means combining this PR with BUG-028.
- Suggested: make the positive test perform a real authenticated upgrade, and either document the ordering against user `wsBeforeUpgrade` handlers or register the plugin's handler first.

---

## BUG-065: Basic auth scheme name is matched case-sensitively

Patch: `0001-Accept-the-Basic-auth-scheme-name-case-insensitively.patch`. Fix at `javalin/src/main/java/io/javalin/http/servlet/JavalinServletContext.kt:239-240`.

**1. Real? Correct and minimal?** Real. RFC 9110 §11.1 makes the auth-scheme token case-insensitive. On master, `startsWith("Basic ")` rejects `basic` and `BASIC` (`final.red.log:182-184`). `startsWith(..., ignoreCase = true)` plus `substring("Basic ".length)` is correct and minimal. Pre-existing and unchanged: more than one space, or a tab, after the scheme still fails, because the Base64 decoder throws, the plugin catches it, and the request gets a 401. RFC 9110 allows `1*SP`, so trimming the token would be a cheap addition, but it is not required.

**2. Behaviour change.** The check accepts more. Requests that used to be anonymous (`ctx.basicAuthCredentials()` returned null) now yield credentials. That should not break anyone.

**3. Test.** `TestRequest.kt:313-319` sits beside the existing `basicAuthCredentials` tests, uses `TestUtil.test` and `http.getBody` with headers, and pins exactly the case-sensitivity bug.

**4. Maintainer pushback.** Unlikely. The only friction is the import conflict with BUG-028 in `TestRequest.kt`.

**5. Severity.** No security impact. Clients that spell the scheme differently are wrongly rejected. **Ordinary interoperability bug fix, public PR.** It does not belong in a security batch.

**Verdict: APPROVE.**

---

## BUG-020: a carriage return in an SSE comment can inject fields

Patch: `0001-Treat-a-carriage-return-as-a-line-terminator-in-SSE-.patch`. Fix at `javalin/src/main/java/io/javalin/http/sse/Emitter.kt:44`.

**1. Real? Correct and minimal?** Real. The WHATWG SSE parser treats CR, LF and CRLF all as line ends, and master splits comments only on LF. `sendComment("hello\rdata: forged")` produces a real `data:` line (`final.red.log:75-77`). The regex `\r\n|\r|\n` puts `\r\n` first, so a CRLF is one terminator, not two. The probe shows `"a\r\nb\rc\nd\n"` becomes four comment lines plus the pre-existing trailing empty `: ` line, with no blank line that could dispatch an event. On master a CRLF was written as `: a\r\n`, which a parser already read as one line, so the only byte change for CRLF input is that the CR is gone. The data path was already safe, because it uses `useLines` and `readLine` treats CR as a terminator (`:28-29`). The fix is consistent with the earlier #2579 hardening of `event` and `id` (`:18-21`).

**2. Behaviour change.** None that a maintainer would object to. A comment containing a lone CR now becomes several comment lines instead of a comment followed by a field.

**3. Test.** `TestSse.kt:304-309` uses the file's own `doAndClose` helper and `getBody` with the SSE Accept header. It splits the response on all three terminators, the way a client parser does, and asserts there is no `data:` line. It pins exactly the bug.

**4. Maintainer pushback.** Minor style: the `Regex` is compiled on every `emit` call. Hoist it to a private top-level `val` next to `NEW_LINE`. Some maintainers would argue that `sendComment` is not meant for untrusted input, but the project accepted #2579 for the sibling fields, so this should go through.

**5. Severity.** Only reachable when an application passes untrusted text to `sendComment`. When it does, an attacker can forge SSE events (`data`, `event`, `id`, `retry`) in that stream, including other users' streams if the app broadcasts the comment. **Ordinary bug fix (injection hardening), public PR**, matching how upstream handled #2579 and #2580 in public.

**Verdict: APPROVE.** Suggested: hoist the regex to a constant.

---

## BUG-033: HttpResponseException messages are reflected unescaped as text/html

Patch: `0001-HTML-escape-HttpResponseException-messages-served-as.patch`. Fix at `javalin/src/main/java/io/javalin/router/exception/HttpResponseExceptionMapper.kt:31` and `:86`.

**1. Real? Correct and minimal?** Real, with a condition. When the client accepts HTML, the mapper writes `plainResult` (the message plus details, unescaped) with `Content-Type: text/html` (master `:31`, `:57-61`). Javalin's own messages do not carry attacker-controlled markup. `EndpointNotFound` uses the raw request URI (`router/Endpoint.kt:78-81`), which browsers percent-encode, and validation errors go out as JSON (`validation/Validation.kt:54-57`). So the XSS needs application code that puts request data into a message, which is a common pattern (`BadRequestResponse("bad name: $name")`). The fix escapes the whole `plainResult` string, so **details are escaped too**: the probe shows the key `k<` became `k&lt;` and the value `v'>` became `v&#39;&gt;`. The five-character escape set (`& < > " '`) is the standard one, and `&` is replaced first, which is correct. The plain-text and JSON branches are byte-for-byte unchanged (probe `PROBE033plain`). Newlines and layout in the HTML branch are also unchanged, so `TestMethodNotAllowed.kt:21-30` still passes. Minimal.

**2. Behaviour change.** Apps that put HTML in exception messages on purpose, such as a link in a 403 message, will now see the markup displayed as text. Tests that compare HTML-branch bodies containing `'`, `"` or `&` will see entities. For example, "Can't" becomes "Can&#39;t". A maintainer could reasonably push back on that, but it is the right default.

**3. Test.** `TestHttpResponseExceptions.kt:113-120` uses `htmlGet`, checks the content type, and checks both that `<script>` is absent and that `&lt;script&gt;` is present. It pins the bug. Adding a details entry would also pin the details escaping, which the patch provides but the test does not cover.

**4. Maintainer pushback.** A maintainer may prefer to serve `text/plain` for this branch instead of escaping, since the docs (line 1070) promise "plain text" for non-JSON clients. That would also fix it, but it changes the content type for every browser client. Escaping is the smaller change. Expect either to be acceptable. Add the `[exceptions]` or a similar prefix to the subject.

**5. Severity.** Reflected XSS, but only in apps that put request data into an `HttpResponseException` message. The attacker needs a victim to follow a crafted link and gets script execution in the app's origin. **Ordinary hardening fix, public PR.** It is defence in depth for a common application pattern, not a flaw that Javalin's defaults expose on their own.

**Verdict: APPROVE.** Suggested: add a details entry to the test.

---

## Verdict lines

- BUG-055: APPROVE WITH CHANGES. Close the `//` empty-segment variant (the patched tree still serves `//secret/file.txt`), assert status and cover `//` in the test, and handle both variants as one private advisory.
- BUG-028: APPROVE. Optional: offer a fail-fast check in `onStart`. Rebase on BUG-065 (import conflict in `TestRequest.kt`).
- BUG-050: APPROVE. Optional: also use `headViaGet` for the endpoint and path parameters at `DefaultTasks.kt:38-41`.
- BUG-037: APPROVE WITH CHANGES. Fix the contradicting KDoc (`BasicAuthPlugin.kt:15-18`), add a config switch or raise an issue instead of a silent default change, share one null-safe credential check with BUG-028, and strengthen the positive test.
- BUG-065: APPROVE.
- BUG-020: APPROVE. Optional: hoist the regex to a constant.
- BUG-033: APPROVE. Optional: cover details in the test.

Only BUG-055 warrants a private advisory. The other six are ordinary public PRs. BUG-065 is not a security fix at all, and BUG-037 is a documented limitation.
