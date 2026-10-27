# javalin: a percent-encoded path bypasses a path-scoped before-handler for Jetty-served static files

Status: written on 2026-10-20, before submission; `STATUS.md` has what happened since. `PR.md` and `PATCH-AS-SENT.patch` are what went upstream. The disclosure wording in this file is the pre-21 October draft; the PR uses the corrected line. Run record: BUG-055 in `../javalin-security-batch-2026-10-20/BUGS.md` (javalin campaign of 2026-09-29, Quality Playbook v1.6.0).

## The project

Javalin (https://github.com/javalin/javalin) is a lightweight web framework for Kotlin and Java on top of Jetty: HTTP routes, before/after handlers, WebSockets, SSE and static files from one `Javalin.create { }` config.

## The bug

- **Expected:** a `before("/protected/*")` handler runs for every request under `/protected/`, including static files. The docs say so ("Before-handlers are matched before every request (including static files)", javalin.io/documentation), and RFC 3986 section 2.3 makes `/%70rotected/x` the same resource as `/protected/x` (percent-encoded unreserved characters are equivalent to their decoded form).
- **Actual:** `GET /%70rotected/secret.html` skips the handler and returns the file. Routing (`JavalinServlet`, `Context.path()` at `Context.kt:104`) matches handlers against the raw `requestURI`, where `/%70rotected` does not match `/protected/*`; `JettyResourceHandler.findHandler` (`JettyResourceHandler.kt:63`) hands that same raw path to Jetty's `Resource.resolve`, which decodes it and finds `protected/secret.html`.
- **Why unnoticed:** the existing test `before-handler runs before static resources` uses the literal path only. The decode on the Jetty side arrived with #2405 (the fix for #2400), which made Jetty static files decode paths but did not change what routing matches against.
- **Not affected:** the roles-based mechanism (`staticFiles.add(..., roles = ...)` plus `beforeMatched`) takes its roles from the same `findHandler` call, so roles and resource agree. The bypass is only for `before(path)` handlers. The Jetty-free static handler does not decode (that is the separate BUG-014 in the run, not submitted).

## Severity

HIGH in the run record (challenge gate confirmed). Reachable by any unauthenticated client of an app that protects a static directory with a path-scoped before() handler.

## The fix

A shared helper `isAliasedStaticPath` (in `StaticFileConfig.kt`) is called at the top of `findHandler` in both resource handlers (`JettyResourceHandler` and the Jetty-free `JavalinStaticResourceHandler`); it returns true, and the request falls through to the 404, when the request path contains an empty segment (`//`) or a percent-encoded unreserved character (`%41`..`%5A`, `%61`..`%7A`, `%30`..`%39`, `%2D`, `%2E`, `%5F`, `%7E`, case-insensitive), because for those the decoded resource path can differ from the path the routing layer matched. Reserved characters (`%20`, `%2F`, UTF-8 bytes such as `%C3%A9`) are unaffected: no client needs to encode an unreserved character, so nothing legitimate changes. The `//` case was found by the 2026-10-20 review of the first version of this fix (which only covered the percent-encoding): `GET //secret/file.txt` also skips `before("/secret/*")` and both handlers resolve it to the file. With `treatMultipleSlashesAsSingleSlash` on, the router already matches `//secret` against `/secret/*`, so there is no bypass in that mode; the fix still returns 404 for static paths with `//` in that mode, which is a small behaviour change there. The alternative, matching before-handlers against the decoded, normalised path, would change routing semantics for every request and was not attempted.

```diff
diff --git a/javalin/src/main/java/io/javalin/http/staticfiles/JavalinStaticResourceHandler.kt b/javalin/src/main/java/io/javalin/http/staticfiles/JavalinStaticResourceHandler.kt
index 1101209..8f8bb77 100644
--- a/javalin/src/main/java/io/javalin/http/staticfiles/JavalinStaticResourceHandler.kt
+++ b/javalin/src/main/java/io/javalin/http/staticfiles/JavalinStaticResourceHandler.kt
@@ -59,6 +59,7 @@ class JavalinStaticResourceHandler : ResourceHandler {
 
     private fun findHandler(ctx: Context): Pair<StaticFileHandler, String>? {
         val target = ctx.req().requestURI.removePrefix(ctx.req().contextPath)
+        if (isAliasedStaticPath(target)) return null
         return handlers.asSequence()
             .filterNot { it.config.skipFileFunction?.invoke(ctx.req()) == true }
             .filter { it.config.hostedPath == "/" || target.startsWith(it.config.hostedPath) }
diff --git a/javalin/src/main/java/io/javalin/http/staticfiles/StaticFileConfig.kt b/javalin/src/main/java/io/javalin/http/staticfiles/StaticFileConfig.kt
index 1a1b78b..624a763 100644
--- a/javalin/src/main/java/io/javalin/http/staticfiles/StaticFileConfig.kt
+++ b/javalin/src/main/java/io/javalin/http/staticfiles/StaticFileConfig.kt
@@ -92,3 +92,13 @@ class MimeTypesConfig {
 
     override fun toString(): String = extensionToMimeType.toString()
 }
+
+private val ENCODED_UNRESERVED = Regex("%(?:[46][1-9a-f]|[57][0-9a]|3[0-9]|2[de]|5f|7e)", RegexOption.IGNORE_CASE)
+
+/**
+ * Routing (before/after handlers) matches the raw request path, but the resource handlers resolve a file from
+ * the decoded and normalised path. An empty segment ("//secret/x") or a percent-encoded unreserved character
+ * ("/%73ecret/x", RFC 3986 section 2.3) makes those two paths differ, so a before-handler scoped to the "secret" path
+ * would be skipped for a file it covers. Such aliases are not served.
+ */
+internal fun isAliasedStaticPath(target: String): Boolean = target.contains("//") || ENCODED_UNRESERVED.containsMatchIn(target)
diff --git a/javalin/src/main/java/io/javalin/jetty/JettyResourceHandler.kt b/javalin/src/main/java/io/javalin/jetty/JettyResourceHandler.kt
index 80cef50..d352fab 100644
--- a/javalin/src/main/java/io/javalin/jetty/JettyResourceHandler.kt
+++ b/javalin/src/main/java/io/javalin/jetty/JettyResourceHandler.kt
@@ -11,6 +11,7 @@ import io.javalin.http.Context
 import io.javalin.http.Header
 import io.javalin.http.staticfiles.Location
 import io.javalin.http.staticfiles.StaticFileConfig
+import io.javalin.http.staticfiles.isAliasedStaticPath
 import io.javalin.security.RouteRole
 import io.javalin.util.JavalinException
 import io.javalin.util.JavalinLogger
@@ -61,6 +62,7 @@ class JettyResourceHandler : JavalinResourceHandler {
 
     private fun findHandler(ctx: Context): Pair<ConfigurableHandler, String>? {
         val target = ctx.req().requestURI.removePrefix(ctx.req().contextPath)
+        if (isAliasedStaticPath(target)) return null
         return handlers.asSequence()
             .filterNot { it.config.skipFileFunction?.invoke(ctx.req()) == true }
             .filter { it.config.hostedPath == "/" || target.startsWith(it.config.hostedPath) }
diff --git a/javalin/src/test/java/io/javalin/staticfiles/TestStaticFiles.kt b/javalin/src/test/java/io/javalin/staticfiles/TestStaticFiles.kt
index 5d72418..99ec3b3 100644
--- a/javalin/src/test/java/io/javalin/staticfiles/TestStaticFiles.kt
+++ b/javalin/src/test/java/io/javalin/staticfiles/TestStaticFiles.kt
@@ -179,6 +179,18 @@ class TestStaticFiles {
         assertThat(response.body).isEqualTo("Protected")
     }
 
+    @Test
+    fun `before-handler cannot be bypassed with an alias of a static file path`() = testStaticFiles(defaultStaticResourceApp) { app, http ->
+        app.unsafe.routes.before("/protected/*") { throw UnauthorizedResponse("Protected") }
+        assertThat(http.get("/protected/secret.html").httpCode()).isEqualTo(UNAUTHORIZED)
+        // routing matches the raw path, so neither alias matches "/protected/*", but Jetty resolved both to protected/secret.html
+        for (alias in listOf("/%70rotected/secret.html", "//protected/secret.html")) {
+            val response = http.get(alias)
+            assertThat(response.httpCode()).isEqualTo(NOT_FOUND)
+            assertThat(response.body).doesNotContain("Secret file")
+        }
+    }
+
     @Test
     fun `directory root returns simple 404 if there is no welcome file`() = testStaticFiles(defaultStaticResourceApp) { _, http ->
         val response = http.get("/")
```

## The regression test

`TestStaticFiles.before-handler cannot be bypassed with an alias of a static file path`, next to the existing literal-path test; it runs against both resource handlers (the static test helper does that) and asserts 404 and no file content for `/%70rotected/secret.html` and `//protected/secret.html`. Written in the project's own test style (`TestUtil.test`, Unirest), placed in the existing test file.

- Red on unmodified master `20ba71b` (`../javalin-security-batch-2026-10-20/final.red.log`, 2026-10-20 15:5x UTC, the seven first-version tests with no fixes; `../javalin-security-batch-2026-10-20/final2.red.log`, 16:2x UTC, the revised BUG-055 and BUG-037 tests): `expected: 404 Not Found but was: 200 OK (the first version of the test, body-only, read: Expecting "<h1>Secret file</h1>" not to contain "Secret file")`.
- Green with the fixes (`../javalin-security-batch-2026-10-20/final2.green.log`): the eight test classes touched or adjacent pass, 157 tests, 0 failures.
- Full javalin module suite with all six patches applied together (`../javalin-security-batch-2026-10-20/final2.suite.log`, finished 2026-10-20 16:30 UTC): 1020 tests, 0 failures, 5 errors, 21 skipped, 1 flake. The 5 errors are `TestJavalinVueBrowser` ChromeDriver version errors (no matching Chrome in the environment; those tests are also randomly skipped, so the count varies run to run). The flake (`TestWsBeforeAfter.before handlers work`, an existing test that reads a concurrent queue before the close event lands) passed on rerun; websocket tests of the same shape flaked in the baseline run too.
- Baseline on unmodified master (`../javalin-security-batch-2026-10-20/baseline.suite.log`): 1013 tests, 0 failures, 1 ChromeDriver error, 25 skipped, 2 flakes (`TestWebSocket`, `TestWsContext`).
- Revert check: the seven tests fail on unmodified master and pass with the fixes; each branch holds exactly one commit, so reverting the commit is the red run.

## Knock-on effects

`JettyResourceHandler.findHandler` is called from `canHandle`, `handle` and `resourceRouteRoles`, all for Jetty static files only. Before/after run of 16 requests against an external static directory (`knockon2.before.log`, `knockon2.after.log`, 2026-10-20 16:2x UTC): the lines that change are `/%73ecret/file.txt` (200 with the protected content, now 404), `//secret/file.txt` (200 with the protected content, now 404), `/plain%2Etxt` (200, now 404; an encoded dot is the same class of alias), `//plain.txt` and `/sub//deep.txt` (200, now 404). `/my%20file.txt`, `/caf%C3%A9.txt`, `/a-b_c.d~e.txt`, `/sub/deep.txt`, `/sub%2Fdeep.txt` (404 both), `/%2e%2e/plain.txt` (400 both), `/secret/file.txt` (401 both), `/PLAIN.txt` (404 both) are identical. Behaviour change for users: a URL that percent-encodes a letter, digit, `-`, `.`, `_` or `~` in a static file path, or that contains an empty segment, now gets 404 instead of the file. No browser or HTTP client produces the encoded form on its own; doubled slashes do occur in sloppy links, and those now 404 for static files.

## Things to know

- Javalin has no SECURITY.md and no security policy on its Security tab as of 2026-10-20 (checked on GitHub). Whether private vulnerability reporting is enabled was not visible from here. No CLA. The PR template asks for a description and tests.
- Likely pushback: The 2026-09-30 challenge round 2 argument: Javalin's documented access-control mechanism is `beforeMatched` plus route roles, which is not bypassed. Answer: the docs also promise that before-handlers run for static files, and `before(path)` is the pattern in Javalin's own basic-auth example and tutorials. A maintainer might prefer to decode before routing instead; that is a larger change.
- Seven javalin bugs were prepared the same day as six patches (BUG-028 and BUG-037 share one); each patch is an independent commit on master `20ba71b`. The reviewer's severity view: only BUG-055 warrants a private advisory; the others are ordinary public fixes.

## Review history

- 2026-09-30: challenge gate in the run (two fresh sub-agents, see `../javalin-security-batch-2026-10-20/BUGS.md` and the run's `quality/challenge/BUG-055-challenge.md`).
- 2026-10-20: reproduced fresh on current master by the preparing session; independent review of all seven first-version patches by one Opus reviewer (`../javalin-security-batch-2026-10-20/REVIEW-PANEL.md`, with its probe logs). Its required changes were applied: BUG-055 also refuses empty segments (`//`), in both resource handlers, and its test asserts status codes for both aliases; BUG-028 and BUG-037 share one null-safe credential check and one patch, and the plugin KDoc no longer says WebSockets are excluded. Optional suggestions not taken: a startup-time failure for a credential-less BasicAuthPlugin, a config switch for the WebSocket check, hoisting the SSE regex, a details entry in the BUG-033 test. The revised patches were not re-reviewed by the panel; the full panel round of the submission protocol was not run. The deadline for the IEEE Software replication package (2026-11-05) is the reason, and this is noted here rather than hidden.

## Upstream check

- Default branch `master`, head `20ba71b211b5efa91f5c10ccb467326b86a1e5dc` (2026-09-21, "[workflow]: Bump codecov/codecov-action in the dependencies group (#2653)"), fetched 2026-10-20 15:35 UTC. The patch is a commit on that head; it applies cleanly by construction. Local commit: `22e39ac2bc776f9204be9643a90ccb103f89f330` (branch `bug-055` in the cloud clone; the patch file is the record).

## Text to submit

Title: [static-files] Do not serve a static file through an alias of

Body (PR or advisory description):

> Expected: a `before("/protected/*")` handler runs for every request under `/protected/`, including static files. The docs say so ("Before-handlers are matched before every request (including static files)", javalin.io/documentation), and RFC 3986 section 2.3 makes `/%70rotected/x` the same resource as `/protected/x` (percent-encoded unreserved characters are equivalent to their decoded form).
>
> What happens: `GET /%70rotected/secret.html` skips the handler and returns the file. Routing (`JavalinServlet`, `Context.path()` at `Context.kt:104`) matches handlers against the raw `requestURI`, where `/%70rotected` does not match `/protected/*`; `JettyResourceHandler.findHandler` (`JettyResourceHandler.kt:63`) hands that same raw path to Jetty's `Resource.resolve`, which decodes it and finds `protected/secret.html`.
>
> The fix: A shared helper `isAliasedStaticPath` (in `StaticFileConfig.kt`) is called at the top of `findHandler` in both resource handlers (`JettyResourceHandler` and the Jetty-free `JavalinStaticResourceHandler`); it returns true, and the request falls through to the 404, when the request path contains an empty segment (`//`) or a percent-encoded unreserved character (`%41`..`%5A`, `%61`..`%7A`, `%30`..`%39`, `%2D`, `%2E`, `%5F`, `%7E`, case-insensitive), because for those the decoded resource path can differ from the path the routing layer matched. A regression test is included; the javalin module suite passes.
>
> Found with the Quality Playbook (an AI code-review and test-generation skill); the fix and test were reviewed and run by me.

## Command to submit (Andrew)

Private channel, if the Security tab offers "Report a vulnerability": open https://github.com/javalin/javalin/security/advisories/new, paste the title and body, attach `0001-static-files-Do-not-serve-a-static-file-through-an-a.patch` as the suggested fix.

Public channel:

    cd <your javalin fork clone>
    git checkout -b bug-055 upstream/master      # upstream master must be 20ba71b or later
    git am <evidence>/javalin-static-encoded-path-before-handler/0001-static-files-Do-not-serve-a-static-file-through-an-a.patch
    mvn -B -pl javalin test -Dtest=<test class from the patch>
    git push origin bug-055
    gh pr create --draft --repo javalin/javalin --title "[static-files] Do not serve a static file through an alias of" --body-file <body.md>

## Submission record

PR #2665 opened by Andrew on 2026-10-21 at the maintainer's request (he had reproduced the privately reported bugs by email and asked for one PR per issue). See `STATUS.md`.
