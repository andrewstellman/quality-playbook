# javalin: HttpResponseException messages are reflected unescaped with Content-Type text/html

Status: written on 2026-10-20, before submission; `STATUS.md` has what happened since. `PR.md` and `PATCH-AS-SENT.patch` are what went upstream. The disclosure wording in this file is the pre-21 October draft; the PR uses the corrected line. Run record: BUG-033 in `../javalin-security-batch-2026-10-20/BUGS.md` (javalin campaign of 2026-09-29, Quality Playbook v1.6.0).

## The project

Javalin (https://github.com/javalin/javalin) is a lightweight web framework for Kotlin and Java on top of Jetty: HTTP routes, before/after handlers, WebSockets, SSE and static files from one `Javalin.create { }` config.

## The bug

- **Expected:** a response served as `text/html` does not contain unescaped text taken from the request; the default error mapper should either escape or serve plain text.
- **Actual:** `HttpResponseExceptionMapper.kt:31`: when the client accepts HTML the mapper returns `plainResult` (message plus details, unescaped) with `Content-Type: text/html`. `throw BadRequestResponse("bad name: " + ctx.queryParam("n"))` with `n=<script>alert(1)</script>` reflects the script tag in an HTML body.
- **Why unnoticed:** the existing test checks the text/plain branch and the JSON branch; the HTML branch reuses the plain formatter.

## Severity

MEDIUM in the run record (downgraded from HIGH). Reflected XSS whenever application code puts request data into an `HttpResponseException` message, for clients that accept HTML (browsers).

## The fix

HTML-escape the formatted plain result (`&`, `<`, `>`, `"`, `'`) before serving it as `text/html`. Message and details are both covered because the escape runs over the whole formatted text.

```diff
diff --git a/javalin/src/main/java/io/javalin/router/exception/HttpResponseExceptionMapper.kt b/javalin/src/main/java/io/javalin/router/exception/HttpResponseExceptionMapper.kt
index 19dc556..a512213 100644
--- a/javalin/src/main/java/io/javalin/router/exception/HttpResponseExceptionMapper.kt
+++ b/javalin/src/main/java/io/javalin/router/exception/HttpResponseExceptionMapper.kt
@@ -28,7 +28,7 @@ import java.util.*
 object HttpResponseExceptionMapper {
 
     fun handle(e: HttpResponseException, ctx: Context) = when {
-        ctx.accepts(ContentType.HTML) -> ctx.answer(e, ::plainResult).contentType(ContentType.HTML)
+        ctx.accepts(ContentType.HTML) -> ctx.answer(e) { htmlEscape(plainResult(it)) }.contentType(ContentType.HTML) // never reflect raw text as HTML
         ctx.accepts(ContentType.JSON) -> ctx.answer(e, ::jsonResult).contentType(ContentType.JSON)
         else -> ctx.answer(e, ::plainResult).contentType(ContentType.PLAIN)
     }
@@ -83,4 +83,6 @@ object HttpResponseExceptionMapper {
 
     private fun String.jsonEscape() = JsonEscapeUtil.escape(this)
 
+    private fun htmlEscape(s: String) = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;").replace("'", "&#39;")
+
 }
diff --git a/javalin/src/test/java/io/javalin/TestHttpResponseExceptions.kt b/javalin/src/test/java/io/javalin/TestHttpResponseExceptions.kt
index 9de4522..1e86559 100644
--- a/javalin/src/test/java/io/javalin/TestHttpResponseExceptions.kt
+++ b/javalin/src/test/java/io/javalin/TestHttpResponseExceptions.kt
@@ -110,6 +110,15 @@ class TestHttpResponseExceptions {
         assertThat(response.body).isEqualTo("Forbidden\n\na:\nA\nb:\nB\n")
     }
 
+    @Test
+    fun `message is html-escaped when the response is served as html`() = TestUtil.test { app, http ->
+        app.unsafe.routes.get("/") { throw BadRequestResponse("bad name: " + it.queryParam("n")) }
+        val response = http.htmlGet("/?n=%3Cscript%3Ealert(1)%3C%2Fscript%3E")
+        assertThat(response.headers.getFirst(Header.CONTENT_TYPE)).isEqualTo(ContentType.HTML)
+        assertThat(response.body).doesNotContain("<script>")
+        assertThat(response.body).contains("&lt;script&gt;")
+    }
+
     @Test
     fun `response is formatted as json if client wants json`() = TestUtil.test { app, http ->
         app.unsafe.routes.post("/") { throw ForbiddenResponse("Off limits!") }
```

## The regression test

`TestHttpResponseExceptions.message is html-escaped when the response is served as html`. Written in the project's own test style (`TestUtil.test`, Unirest), placed in the existing test file.

- Red on unmodified master `20ba71b` (`../javalin-security-batch-2026-10-20/final.red.log`, 2026-10-20 15:5x UTC, the seven first-version tests with no fixes; `../javalin-security-batch-2026-10-20/final2.red.log`, 16:2x UTC, the revised BUG-055 and BUG-037 tests): `Expecting actual: "bad name: <script>alert(1)</script>" not to contain: "<script>"`.
- Green with the fixes (`../javalin-security-batch-2026-10-20/final2.green.log`): the eight test classes touched or adjacent pass, 157 tests, 0 failures.
- Full javalin module suite with all six patches applied together (`../javalin-security-batch-2026-10-20/final2.suite.log`, finished 2026-10-20 16:30 UTC): 1020 tests, 0 failures, 5 errors, 21 skipped, 1 flake. The 5 errors are `TestJavalinVueBrowser` ChromeDriver version errors (no matching Chrome in the environment; those tests are also randomly skipped, so the count varies run to run). The flake (`TestWsBeforeAfter.before handlers work`, an existing test that reads a concurrent queue before the close event lands) passed on rerun; websocket tests of the same shape flaked in the baseline run too.
- Baseline on unmodified master (`../javalin-security-batch-2026-10-20/baseline.suite.log`): 1013 tests, 0 failures, 1 ChromeDriver error, 25 skipped, 2 flakes (`TestWebSocket`, `TestWsContext`).
- Revert check: the seven tests fail on unmodified master and pass with the fixes; each branch holds exactly one commit, so reverting the commit is the red run.

## Knock-on effects

Only the HTML branch of `HttpResponseExceptionMapper` changes. Plain-text and JSON responses are byte-identical. HTML-accepting clients now see `&lt;` for `<` in messages; a message that intentionally contained HTML markup would now render as text. Nothing in Javalin itself emits markup in these messages.

## Things to know

- Javalin has no SECURITY.md and no security policy on its Security tab as of 2026-10-20 (checked on GitHub). Whether private vulnerability reporting is enabled was not visible from here. No CLA. The PR template asks for a description and tests.
- Likely pushback: A maintainer may prefer serving the HTML branch as `text/plain`, which would be a larger behaviour change (Content-Type) than escaping.
- Seven javalin bugs were prepared the same day as six patches (BUG-028 and BUG-037 share one); each patch is an independent commit on master `20ba71b`. The reviewer's severity view: only BUG-055 warrants a private advisory; the others are ordinary public fixes.

## Review history

- 2026-09-30: challenge gate in the run (two fresh sub-agents, see `../javalin-security-batch-2026-10-20/BUGS.md` and the run's `quality/challenge/BUG-033-challenge.md`).
- 2026-10-20: reproduced fresh on current master by the preparing session; independent review of all seven first-version patches by one Opus reviewer (`../javalin-security-batch-2026-10-20/REVIEW-PANEL.md`, with its probe logs). Its required changes were applied: BUG-055 also refuses empty segments (`//`), in both resource handlers, and its test asserts status codes for both aliases; BUG-028 and BUG-037 share one null-safe credential check and one patch, and the plugin KDoc no longer says WebSockets are excluded. Optional suggestions not taken: a startup-time failure for a credential-less BasicAuthPlugin, a config switch for the WebSocket check, hoisting the SSE regex, a details entry in the BUG-033 test. The revised patches were not re-reviewed by the panel; the full panel round of the submission protocol was not run. The deadline for the IEEE Software replication package (2026-11-05) is the reason, and this is noted here rather than hidden.

## Upstream check

- Default branch `master`, head `20ba71b211b5efa91f5c10ccb467326b86a1e5dc` (2026-09-21, "[workflow]: Bump codecov/codecov-action in the dependencies group (#2653)"), fetched 2026-10-20 15:35 UTC. The patch is a commit on that head; it applies cleanly by construction. Local commit: `8fde16f1b1e49feea2b79cfe6a75ffa41b85e495` (branch `bug-033` in the cloud clone; the patch file is the record).

## Text to submit

Title: [http] HTML-escape HttpResponseException messages served as

Body (PR or advisory description):

> Expected: a response served as `text/html` does not contain unescaped text taken from the request; the default error mapper should either escape or serve plain text.
>
> What happens: `HttpResponseExceptionMapper.kt:31`: when the client accepts HTML the mapper returns `plainResult` (message plus details, unescaped) with `Content-Type: text/html`. `throw BadRequestResponse("bad name: " + ctx.queryParam("n"))` with `n=<script>alert(1)</script>` reflects the script tag in an HTML body.
>
> The fix: HTML-escape the formatted plain result (`&`, `<`, `>`, `"`, `'`) before serving it as `text/html`. A regression test is included; the javalin module suite passes.
>
> Found with the Quality Playbook (an AI code-review and test-generation skill); the fix and test were reviewed and run by me.

## Command to submit (Andrew)

Private channel, if the Security tab offers "Report a vulnerability": open https://github.com/javalin/javalin/security/advisories/new, paste the title and body, attach `0001-http-HTML-escape-HttpResponseException-messages-serv.patch` as the suggested fix.

Public channel:

    cd <your javalin fork clone>
    git checkout -b bug-033 upstream/master      # upstream master must be 20ba71b or later
    git am <evidence>/javalin-exception-message-html-xss/0001-http-HTML-escape-HttpResponseException-messages-serv.patch
    mvn -B -pl javalin test -Dtest=<test class from the patch>
    git push origin bug-033
    gh pr create --draft --repo javalin/javalin --title "[http] HTML-escape HttpResponseException messages served as" --body-file <body.md>

## Submission record

PR #2669 opened by Andrew on 2026-10-21 at the maintainer's request (he had reproduced the privately reported bugs by email and asked for one PR per issue). See `STATUS.md`.
