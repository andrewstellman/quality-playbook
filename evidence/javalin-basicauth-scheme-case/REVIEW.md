# javalin: Basic auth credentials are ignored when the scheme is not spelled exactly "Basic"

Status: written on 2026-10-20, before submission; `STATUS.md` has what happened since. `PR.md` and `PATCH-AS-SENT.patch` are what went upstream. The disclosure wording in this file is the pre-21 October draft; the PR uses the corrected line. Run record: BUG-065 in `../javalin-security-batch-2026-10-20/BUGS.md` (javalin campaign of 2026-09-29, Quality Playbook v1.6.0).

## The project

Javalin (https://github.com/javalin/javalin) is a lightweight web framework for Kotlin and Java on top of Jetty: HTTP routes, before/after handlers, WebSockets, SSE and static files from one `Javalin.create { }` config.

## The bug

- **Expected:** RFC 9110 section 11.1: the auth-scheme is case-insensitive, so `Authorization: basic <token>` carries credentials.
- **Actual:** `JavalinServletContext.kt:239-240` checks `startsWith("Basic ")` case-sensitively, so `basicAuthCredentials()` is null and `enableBasicAuth` returns 401 for such a client.

## Severity

LOW. A standards-conforming client is rejected; no bypass.

## The fix

`startsWith("Basic ", ignoreCase = true)` and `substring("Basic ".length)` instead of the case-sensitive prefix check and `removePrefix`.

```diff
diff --git a/javalin/src/main/java/io/javalin/http/servlet/JavalinServletContext.kt b/javalin/src/main/java/io/javalin/http/servlet/JavalinServletContext.kt
index 34b0bc4..cd13f9b 100644
--- a/javalin/src/main/java/io/javalin/http/servlet/JavalinServletContext.kt
+++ b/javalin/src/main/java/io/javalin/http/servlet/JavalinServletContext.kt
@@ -236,8 +236,8 @@ fun urlDecode(s: String) =
  */
 fun getBasicAuthCredentials(authorizationHeader: String?): BasicAuthCredentials? =
     authorizationHeader
-        ?.takeIf { authorizationHeader.startsWith("Basic ") }
-        ?.removePrefix("Basic ")
+        ?.takeIf { authorizationHeader.startsWith("Basic ", ignoreCase = true) } // RFC 9110 §11.1: auth-scheme is case-insensitive
+        ?.substring("Basic ".length)
         ?.let { Base64.getDecoder().decode(it).decodeToString() }
         ?.split(':', limit = 2)
         ?.let { (username, password) -> BasicAuthCredentials(username, password) }
diff --git a/javalin/src/test/java/io/javalin/TestRequest.kt b/javalin/src/test/java/io/javalin/TestRequest.kt
index 583919d..754a869 100644
--- a/javalin/src/test/java/io/javalin/TestRequest.kt
+++ b/javalin/src/test/java/io/javalin/TestRequest.kt
@@ -18,6 +18,7 @@ import io.javalin.http.servlet.SESSION_CACHE_KEY_PREFIX
 import io.javalin.http.staticfiles.Location
 import io.javalin.plugin.bundled.BasicAuthPlugin
 import io.javalin.testing.TestUtil
+import java.util.Base64
 
 import kong.unirest.Unirest
 import okhttp3.OkHttpClient
@@ -309,6 +310,14 @@ class TestRequest {
         assertThat(response.body).isEqualTo("some-username|some-pass:::word")
     }
 
+    @Test
+    fun `basicAuthCredentials accepts the scheme name in any case`() = TestUtil.test { app, http ->
+        app.unsafe.routes.get("/") { ctx -> ctx.result(ctx.basicAuthCredentials()?.username ?: "null") }
+        val token = Base64.getEncoder().encodeToString("some-username:some-password".toByteArray())
+        assertThat(http.getBody("/", mapOf(Header.AUTHORIZATION to "basic $token"))).isEqualTo("some-username")
+        assertThat(http.getBody("/", mapOf(Header.AUTHORIZATION to "BASIC $token"))).isEqualTo("some-username")
+    }
+
     @Test
     fun `basic auth filter plugin works`() {
         val basicAuthApp = Javalin.create { cfg ->
```

## The regression test

`TestRequest.basicAuthCredentials accepts the scheme name in any case`. Written in the project's own test style (`TestUtil.test`, Unirest), placed in the existing test file.

- Red on unmodified master `20ba71b` (`../javalin-security-batch-2026-10-20/final.red.log`, 2026-10-20 15:5x UTC, the seven first-version tests with no fixes; `../javalin-security-batch-2026-10-20/final2.red.log`, 16:2x UTC, the revised BUG-055 and BUG-037 tests): `expected: "some-username" but was: "null"`.
- Green with the fixes (`../javalin-security-batch-2026-10-20/final2.green.log`): the eight test classes touched or adjacent pass, 157 tests, 0 failures.
- Full javalin module suite with all six patches applied together (`../javalin-security-batch-2026-10-20/final2.suite.log`, finished 2026-10-20 16:30 UTC): 1020 tests, 0 failures, 5 errors, 21 skipped, 1 flake. The 5 errors are `TestJavalinVueBrowser` ChromeDriver version errors (no matching Chrome in the environment; those tests are also randomly skipped, so the count varies run to run). The flake (`TestWsBeforeAfter.before handlers work`, an existing test that reads a concurrent queue before the close event lands) passed on rerun; websocket tests of the same shape flaked in the baseline run too.
- Baseline on unmodified master (`../javalin-security-batch-2026-10-20/baseline.suite.log`): 1013 tests, 0 failures, 1 ChromeDriver error, 25 skipped, 2 flakes (`TestWebSocket`, `TestWsContext`).
- Revert check: the seven tests fail on unmodified master and pass with the fixes; each branch holds exactly one commit, so reverting the commit is the red run.

## Knock-on effects

Only `getBasicAuthCredentials` changes. Headers that start with `Basic ` in that exact spelling behave as before; other spellings of the scheme now parse. No other code path reads the scheme.

## Things to know

- Javalin has no SECURITY.md and no security policy on its Security tab as of 2026-10-20 (checked on GitHub). Whether private vulnerability reporting is enabled was not visible from here. No CLA. The PR template asks for a description and tests.
- Likely pushback: Unlikely; small and standards-based.
- Seven javalin bugs were prepared the same day as six patches (BUG-028 and BUG-037 share one); each patch is an independent commit on master `20ba71b`. The reviewer's severity view: only BUG-055 warrants a private advisory; the others are ordinary public fixes.

## Review history

- 2026-09-30: challenge gate in the run (two fresh sub-agents, see `../javalin-security-batch-2026-10-20/BUGS.md` and the run's `quality/challenge/BUG-065-challenge.md`).
- 2026-10-20: reproduced fresh on current master by the preparing session; independent review of all seven first-version patches by one Opus reviewer (`../javalin-security-batch-2026-10-20/REVIEW-PANEL.md`, with its probe logs). Its required changes were applied: BUG-055 also refuses empty segments (`//`), in both resource handlers, and its test asserts status codes for both aliases; BUG-028 and BUG-037 share one null-safe credential check and one patch, and the plugin KDoc no longer says WebSockets are excluded. Optional suggestions not taken: a startup-time failure for a credential-less BasicAuthPlugin, a config switch for the WebSocket check, hoisting the SSE regex, a details entry in the BUG-033 test. The revised patches were not re-reviewed by the panel; the full panel round of the submission protocol was not run. The deadline for the IEEE Software replication package (2026-11-05) is the reason, and this is noted here rather than hidden.

## Upstream check

- Default branch `master`, head `20ba71b211b5efa91f5c10ccb467326b86a1e5dc` (2026-09-21, "[workflow]: Bump codecov/codecov-action in the dependencies group (#2653)"), fetched 2026-10-20 15:35 UTC. The patch is a commit on that head; it applies cleanly by construction. Local commit: `69e6ec4df1637d678c50d5f20f82d2848055b301` (branch `bug-065` in the cloud clone; the patch file is the record).

## Text to submit

Title: [context] Accept the Basic auth scheme name

Body (PR or advisory description):

> Expected: RFC 9110 section 11.1: the auth-scheme is case-insensitive, so `Authorization: basic <token>` carries credentials.
>
> What happens: `JavalinServletContext.kt:239-240` checks `startsWith("Basic ")` case-sensitively, so `basicAuthCredentials()` is null and `enableBasicAuth` returns 401 for such a client.
>
> The fix: `startsWith("Basic ", ignoreCase = true)` and `substring("Basic ".length)` instead of the case-sensitive prefix check and `removePrefix`.. A regression test is included; the javalin module suite passes.
>
> Found with the Quality Playbook (an AI code-review and test-generation skill); the fix and test were reviewed and run by me.

## Command to submit (Andrew)

Private channel, if the Security tab offers "Report a vulnerability": open https://github.com/javalin/javalin/security/advisories/new, paste the title and body, attach `0001-context-Accept-the-Basic-auth-scheme-name-case-insen.patch` as the suggested fix.

Public channel:

    cd <your javalin fork clone>
    git checkout -b bug-065 upstream/master      # upstream master must be 20ba71b or later
    git am <evidence>/javalin-basicauth-scheme-case/0001-context-Accept-the-Basic-auth-scheme-name-case-insen.patch
    mvn -B -pl javalin test -Dtest=<test class from the patch>
    git push origin bug-065
    gh pr create --draft --repo javalin/javalin --title "[context] Accept the Basic auth scheme name" --body-file <body.md>

## Submission record

PR #2671 opened by Andrew on 2026-10-21 at the maintainer's request (he had reproduced the privately reported bugs by email and asked for one PR per issue). See `STATUS.md`.
