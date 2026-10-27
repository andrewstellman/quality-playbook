# javalin: a carriage return inside an SSE comment injects a field

Status: written on 2026-10-20, before submission; `STATUS.md` has what happened since. `PR.md` and `PATCH-AS-SENT.patch` are what went upstream. The disclosure wording in this file is the pre-21 October draft; the PR uses the corrected line. Run record: BUG-020 in `../javalin-security-batch-2026-10-20/BUGS.md` (javalin campaign of 2026-09-29, Quality Playbook v1.6.0).

## The project

Javalin (https://github.com/javalin/javalin) is a lightweight web framework for Kotlin and Java on top of Jetty: HTTP routes, before/after handlers, WebSockets, SSE and static files from one `Javalin.create { }` config.

## The bug

- **Expected:** the SSE spec treats CR, LF and CRLF as line terminators, so a comment is emitted with every line prefixed by `:`; `sendEvent` already strips CR and LF from event names, data and ids (the fix for #2579).
- **Actual:** `Emitter.kt:44` splits comment text on LF only. `sendComment("hello\rdata: forged")` writes `: hello\rdata: forged`, which a browser parses as a comment line followed by a `data: forged` line, dispatching a message the application never sent.
- **Why unnoticed:** #2579 fixed the event path and did not touch comments.

## Severity

MEDIUM in the run record (downgraded from HIGH). Needs application code that puts externally supplied text into `sendComment`; then the sender can inject `data:`, `event:` or `id:` lines the browser dispatches.

## The fix

Split the comment on `\r\n`, `\r` or `\n` instead of `\n` only, so every line gets the `:` prefix.

```diff
diff --git a/javalin/src/main/java/io/javalin/http/sse/Emitter.kt b/javalin/src/main/java/io/javalin/http/sse/Emitter.kt
index 32fa68d..06886e3 100644
--- a/javalin/src/main/java/io/javalin/http/sse/Emitter.kt
+++ b/javalin/src/main/java/io/javalin/http/sse/Emitter.kt
@@ -41,7 +41,7 @@ class Emitter(private var response: HttpServletResponse) {
 
     fun emit(comment: String) = synchronized(this) {
         try {
-            comment.split(NEW_LINE).forEach {
+            comment.split(Regex("\r\n|\r|\n")).forEach { // CR alone is also an SSE line terminator
                 write("$COMMENT_PREFIX $it$NEW_LINE")
             }
             response.flushBuffer()
diff --git a/javalin/src/test/java/io/javalin/TestSse.kt b/javalin/src/test/java/io/javalin/TestSse.kt
index ba91e12..2b93c53 100644
--- a/javalin/src/test/java/io/javalin/TestSse.kt
+++ b/javalin/src/test/java/io/javalin/TestSse.kt
@@ -301,6 +301,13 @@ class TestSse {
         }
     }
 
+    @Test
+    fun `carriage return in a comment cannot inject a field`() = TestUtil.test { app, http ->
+        app.unsafe.routes.sse("/sse") { it.doAndClose { it.sendComment("hello\rdata: forged") } }
+        val body = http.getBody("/sse", mapOf(Header.ACCEPT to "text/event-stream"))
+        assertThat(body.split("\r\n", "\r", "\n").filter { it.startsWith("data:") }).isEmpty()
+    }
+
     @Test
     fun `sse does not work without text-event-stream in Accept header`() = TestUtil.test { app, http ->
         app.unsafe.routes.sse("/sse") { it.doAndClose { it.sendEvent(event, data) } }
```

## The regression test

`TestSse.carriage return in a comment cannot inject a field`. Written in the project's own test style (`TestUtil.test`, Unirest), placed in the existing test file.

- Red on unmodified master `20ba71b` (`../javalin-security-batch-2026-10-20/final.red.log`, 2026-10-20 15:5x UTC, the seven first-version tests with no fixes; `../javalin-security-batch-2026-10-20/final2.red.log`, 16:2x UTC, the revised BUG-055 and BUG-037 tests): `Expecting empty but was: ["data: forged"]`.
- Green with the fixes (`../javalin-security-batch-2026-10-20/final2.green.log`): the eight test classes touched or adjacent pass, 157 tests, 0 failures.
- Full javalin module suite with all six patches applied together (`../javalin-security-batch-2026-10-20/final2.suite.log`, finished 2026-10-20 16:30 UTC): 1020 tests, 0 failures, 5 errors, 21 skipped, 1 flake. The 5 errors are `TestJavalinVueBrowser` ChromeDriver version errors (no matching Chrome in the environment; those tests are also randomly skipped, so the count varies run to run). The flake (`TestWsBeforeAfter.before handlers work`, an existing test that reads a concurrent queue before the close event lands) passed on rerun; websocket tests of the same shape flaked in the baseline run too.
- Baseline on unmodified master (`../javalin-security-batch-2026-10-20/baseline.suite.log`): 1013 tests, 0 failures, 1 ChromeDriver error, 25 skipped, 2 flakes (`TestWebSocket`, `TestWsContext`).
- Revert check: the seven tests fail on unmodified master and pass with the fixes; each branch holds exactly one commit, so reverting the commit is the red run.

## Knock-on effects

Only `Emitter.emit(comment)` changes. Comments without CR are byte-identical. A comment containing CRLF previously produced a line ending in `\r` followed by the next line; now both halves are separate comment lines, which is what the spec parses them as anyway.

## Things to know

- Javalin has no SECURITY.md and no security policy on its Security tab as of 2026-10-20 (checked on GitHub). Whether private vulnerability reporting is enabled was not visible from here. No CLA. The PR template asks for a description and tests.
- Likely pushback: Unlikely; it is the sibling of an accepted fix.
- Seven javalin bugs were prepared the same day as six patches (BUG-028 and BUG-037 share one); each patch is an independent commit on master `20ba71b`. The reviewer's severity view: only BUG-055 warrants a private advisory; the others are ordinary public fixes.

## Review history

- 2026-09-30: challenge gate in the run (two fresh sub-agents, see `../javalin-security-batch-2026-10-20/BUGS.md` and the run's `quality/challenge/BUG-020-challenge.md`).
- 2026-10-20: reproduced fresh on current master by the preparing session; independent review of all seven first-version patches by one Opus reviewer (`../javalin-security-batch-2026-10-20/REVIEW-PANEL.md`, with its probe logs). Its required changes were applied: BUG-055 also refuses empty segments (`//`), in both resource handlers, and its test asserts status codes for both aliases; BUG-028 and BUG-037 share one null-safe credential check and one patch, and the plugin KDoc no longer says WebSockets are excluded. Optional suggestions not taken: a startup-time failure for a credential-less BasicAuthPlugin, a config switch for the WebSocket check, hoisting the SSE regex, a details entry in the BUG-033 test. The revised patches were not re-reviewed by the panel; the full panel round of the submission protocol was not run. The deadline for the IEEE Software replication package (2026-11-05) is the reason, and this is noted here rather than hidden.

## Upstream check

- Default branch `master`, head `20ba71b211b5efa91f5c10ccb467326b86a1e5dc` (2026-09-21, "[workflow]: Bump codecov/codecov-action in the dependencies group (#2653)"), fetched 2026-10-20 15:35 UTC. The patch is a commit on that head; it applies cleanly by construction. Local commit: `02fb4f0fb78a77605d0d07547ee685d3a23b7316` (branch `bug-020` in the cloud clone; the patch file is the record).

## Text to submit

Title: [sse] Treat a carriage return as a line terminator in SSE

Body (PR or advisory description):

> Expected: the SSE spec treats CR, LF and CRLF as line terminators, so a comment is emitted with every line prefixed by `:`; `sendEvent` already strips CR and LF from event names, data and ids (the fix for #2579).
>
> What happens: `Emitter.kt:44` splits comment text on LF only. `sendComment("hello\rdata: forged")` writes `: hello\rdata: forged`, which a browser parses as a comment line followed by a `data: forged` line, dispatching a message the application never sent.
>
> The fix: Split the comment on `\r\n`, `\r` or `\n` instead of `\n` only, so every line gets the `:` prefix.. A regression test is included; the javalin module suite passes.
>
> Found with the Quality Playbook (an AI code-review and test-generation skill); the fix and test were reviewed and run by me.

## Command to submit (Andrew)

Private channel, if the Security tab offers "Report a vulnerability": open https://github.com/javalin/javalin/security/advisories/new, paste the title and body, attach `0001-sse-Treat-a-carriage-return-as-a-line-terminator-in-.patch` as the suggested fix.

Public channel:

    cd <your javalin fork clone>
    git checkout -b bug-020 upstream/master      # upstream master must be 20ba71b or later
    git am <evidence>/javalin-sse-comment-cr-injection/0001-sse-Treat-a-carriage-return-as-a-line-terminator-in-.patch
    mvn -B -pl javalin test -Dtest=<test class from the patch>
    git push origin bug-020
    gh pr create --draft --repo javalin/javalin --title "[sse] Treat a carriage return as a line terminator in SSE" --body-file <body.md>

## Submission record

PR #2670 opened by Andrew on 2026-10-21 at the maintainer's request (he had reproduced the privately reported bugs by email and asked for one PR per issue). See `STATUS.md`.
