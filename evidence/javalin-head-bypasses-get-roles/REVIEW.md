# javalin: a HEAD request answered by a GET route is not checked against the GET route's roles

Status: written on 2026-10-20, before submission; `STATUS.md` has what happened since. `PR.md` and `PATCH-AS-SENT.patch` are what went upstream. The disclosure wording in this file is the pre-21 October draft; the PR uses the corrected line. Run record: BUG-050 in `../javalin-security-batch-2026-10-20/BUGS.md` (javalin campaign of 2026-09-29, Quality Playbook v1.6.0).

## The project

Javalin (https://github.com/javalin/javalin) is a lightweight web framework for Kotlin and Java on top of Jetty: HTTP routes, before/after handlers, WebSockets, SSE and static files from one `Javalin.create { }` config.

## The bug

- **Expected:** `HEAD /admin` on `get("/admin", handler, ADMIN)` is subject to the same role check as `GET /admin`; Javalin answers HEAD from the GET handler, so the roles should travel with it.
- **Actual:** `DefaultTasks.kt:26`: for HEAD with no HEAD route, `httpHandlerOrNull` is null, the request is treated as a static-resource request and its roles come from the static-file handler (empty). `beforeMatched { if (ADMIN in ctx.routeRoles()) throw UnauthorizedResponse() }` sees no roles; the HEAD is answered 200 with the GET handler's status and headers.
- **Why unnoticed:** the role tests cover GET only.

## Severity

MEDIUM in the run record (downgraded from HIGH: no body is returned). The response status and headers of a role-protected GET are exposed to any client, and any `beforeMatched` logic keyed on `routeRoles()` is skipped.

## The fix

When the method is HEAD and no HEAD route matched, look up the GET route for the path (`findFirstHttpHandlerEntry(GET, requestUri)`) and take the roles from it; such a request is no longer treated as a static-resource request.

```diff
diff --git a/javalin/src/main/java/io/javalin/http/servlet/DefaultTasks.kt b/javalin/src/main/java/io/javalin/http/servlet/DefaultTasks.kt
index 2cf1ab7..a3a5361 100644
--- a/javalin/src/main/java/io/javalin/http/servlet/DefaultTasks.kt
+++ b/javalin/src/main/java/io/javalin/http/servlet/DefaultTasks.kt
@@ -23,8 +23,10 @@ object DefaultTasks {
         val httpHandlerOrNull by javalinLazy {
             ctx.cachedHttpHandler { servlet.router.findFirstHttpHandlerEntry(ctx.method(), requestUri) }
         }
-        val isResourceHandler = httpHandlerOrNull == null && (ctx.method() == HEAD || ctx.method() == GET)
-        val matchedRouteRoles by javalinLazy { httpHandlerOrNull?.endpoint?.metadata(Roles::class.java)?.roles ?: emptySet() }
+        // HEAD is answered from the GET route, so it must be guarded by the GET route's roles
+        val headViaGet by javalinLazy { if (ctx.method() == HEAD && httpHandlerOrNull == null) servlet.router.findFirstHttpHandlerEntry(GET, requestUri) else null }
+        val isResourceHandler = httpHandlerOrNull == null && headViaGet == null && (ctx.method() == HEAD || ctx.method() == GET)
+        val matchedRouteRoles by javalinLazy { (httpHandlerOrNull ?: headViaGet)?.endpoint?.metadata(Roles::class.java)?.roles ?: emptySet() }
         val resourceRouteRoles by javalinLazy { servlet.cfg.resourceHandler?.resourceRouteRoles(ctx) ?: emptySet() }
         val willMatch by javalinLazy {
             ctx.setRouteRoles(if (isResourceHandler) resourceRouteRoles else matchedRouteRoles)
diff --git a/javalin/src/test/java/io/javalin/TestContextRouteRoles.kt b/javalin/src/test/java/io/javalin/TestContextRouteRoles.kt
index 25b391a..e154c18 100644
--- a/javalin/src/test/java/io/javalin/TestContextRouteRoles.kt
+++ b/javalin/src/test/java/io/javalin/TestContextRouteRoles.kt
@@ -5,8 +5,10 @@ import io.javalin.Role.B
 import io.javalin.Role.C
 import io.javalin.Role.D
 import io.javalin.http.Context
+import io.javalin.http.UnauthorizedResponse
 import io.javalin.security.RouteRole
 import io.javalin.testing.TestUtil
+import kong.unirest.HttpMethod
 import org.assertj.core.api.Assertions.assertThat
 import org.junit.jupiter.api.Test
 
@@ -53,4 +55,12 @@ class TestContextRouteRoles {
         http.get("/roles").let { assertThat(it.body).isEqualTo("!!![B, C, D]") }
     }
 
+    @Test
+    fun `HEAD request answered by a GET handler has the GET handler's route roles`() = TestUtil.test { app, http ->
+        app.unsafe.routes.beforeMatched { if (A in it.routeRoles()) throw UnauthorizedResponse() }
+        app.unsafe.routes.get("/admin", { it.result("secret") }, A)
+        assertThat(http.get("/admin").status).isEqualTo(401)
+        assertThat(http.call(HttpMethod.HEAD, "/admin").status).isEqualTo(401)
+    }
+
 }
```

## The regression test

`TestContextRouteRoles.HEAD request answered by a GET handler has the GET handler's route roles`. Written in the project's own test style (`TestUtil.test`, Unirest), placed in the existing test file.

- Red on unmodified master `20ba71b` (`../javalin-security-batch-2026-10-20/final.red.log`, 2026-10-20 15:5x UTC, the seven first-version tests with no fixes; `../javalin-security-batch-2026-10-20/final2.red.log`, 16:2x UTC, the revised BUG-055 and BUG-037 tests): `expected: 401 but was: 200`.
- Green with the fixes (`../javalin-security-batch-2026-10-20/final2.green.log`): the eight test classes touched or adjacent pass, 157 tests, 0 failures.
- Full javalin module suite with all six patches applied together (`../javalin-security-batch-2026-10-20/final2.suite.log`, finished 2026-10-20 16:30 UTC): 1020 tests, 0 failures, 5 errors, 21 skipped, 1 flake. The 5 errors are `TestJavalinVueBrowser` ChromeDriver version errors (no matching Chrome in the environment; those tests are also randomly skipped, so the count varies run to run). The flake (`TestWsBeforeAfter.before handlers work`, an existing test that reads a concurrent queue before the close event lands) passed on rerun; websocket tests of the same shape flaked in the baseline run too.
- Baseline on unmodified master (`../javalin-security-batch-2026-10-20/baseline.suite.log`): 1013 tests, 0 failures, 1 ChromeDriver error, 25 skipped, 2 flakes (`TestWebSocket`, `TestWsContext`).
- Revert check: the seven tests fail on unmodified master and pass with the fixes; each branch holds exactly one commit, so reverting the commit is the red run.

## Knock-on effects

Only `DefaultTasks` changes, only for HEAD requests with no HEAD route. A HEAD answered from a GET route now has that route's roles in `routeRoles()`; apps that deny on roles will now deny the HEAD too, which is the point. HEAD for static files (no GET route) is unchanged. Apps with an explicit HEAD route are unchanged.

## Things to know

- Javalin has no SECURITY.md and no security policy on its Security tab as of 2026-10-20 (checked on GitHub). Whether private vulnerability reporting is enabled was not visible from here. No CLA. The PR template asks for a description and tests.
- Likely pushback: A maintainer may ask whether the HEAD-from-GET fallback lives in the router rather than in `DefaultTasks`; the fix follows where the existing `isResourceHandler` decision is made.
- Seven javalin bugs were prepared the same day as six patches (BUG-028 and BUG-037 share one); each patch is an independent commit on master `20ba71b`. The reviewer's severity view: only BUG-055 warrants a private advisory; the others are ordinary public fixes.

## Review history

- 2026-09-30: challenge gate in the run (two fresh sub-agents, see `../javalin-security-batch-2026-10-20/BUGS.md` and the run's `quality/challenge/BUG-050-challenge.md`).
- 2026-10-20: reproduced fresh on current master by the preparing session; independent review of all seven first-version patches by one Opus reviewer (`../javalin-security-batch-2026-10-20/REVIEW-PANEL.md`, with its probe logs). Its required changes were applied: BUG-055 also refuses empty segments (`//`), in both resource handlers, and its test asserts status codes for both aliases; BUG-028 and BUG-037 share one null-safe credential check and one patch, and the plugin KDoc no longer says WebSockets are excluded. Optional suggestions not taken: a startup-time failure for a credential-less BasicAuthPlugin, a config switch for the WebSocket check, hoisting the SSE regex, a details entry in the BUG-033 test. The revised patches were not re-reviewed by the panel; the full panel round of the submission protocol was not run. The deadline for the IEEE Software replication package (2026-11-05) is the reason, and this is noted here rather than hidden.

## Upstream check

- Default branch `master`, head `20ba71b211b5efa91f5c10ccb467326b86a1e5dc` (2026-09-21, "[workflow]: Bump codecov/codecov-action in the dependencies group (#2653)"), fetched 2026-10-20 15:35 UTC. The patch is a commit on that head; it applies cleanly by construction. Local commit: `0421effd84bbf64c352f5961a5356df9968c3afe` (branch `bug-050` in the cloud clone; the patch file is the record).

## Text to submit

Title: [routing] Apply the GET route's roles to a HEAD request it

Body (PR or advisory description):

> Expected: `HEAD /admin` on `get("/admin", handler, ADMIN)` is subject to the same role check as `GET /admin`; Javalin answers HEAD from the GET handler, so the roles should travel with it.
>
> What happens: `DefaultTasks.kt:26`: for HEAD with no HEAD route, `httpHandlerOrNull` is null, the request is treated as a static-resource request and its roles come from the static-file handler (empty). `beforeMatched { if (ADMIN in ctx.routeRoles()) throw UnauthorizedResponse() }` sees no roles; the HEAD is answered 200 with the GET handler's status and headers.
>
> The fix: When the method is HEAD and no HEAD route matched, look up the GET route for the path (`findFirstHttpHandlerEntry(GET, requestUri)`) and take the roles from it; such a request is no longer treated as a static-resource request.. A regression test is included; the javalin module suite passes.
>
> Found with the Quality Playbook (an AI code-review and test-generation skill); the fix and test were reviewed and run by me.

## Command to submit (Andrew)

Private channel, if the Security tab offers "Report a vulnerability": open https://github.com/javalin/javalin/security/advisories/new, paste the title and body, attach `0001-routing-Apply-the-GET-route-s-roles-to-a-HEAD-reques.patch` as the suggested fix.

Public channel:

    cd <your javalin fork clone>
    git checkout -b bug-050 upstream/master      # upstream master must be 20ba71b or later
    git am <evidence>/javalin-head-bypasses-get-roles/0001-routing-Apply-the-GET-route-s-roles-to-a-HEAD-reques.patch
    mvn -B -pl javalin test -Dtest=<test class from the patch>
    git push origin bug-050
    gh pr create --draft --repo javalin/javalin --title "[routing] Apply the GET route's roles to a HEAD request it" --body-file <body.md>

## Submission record

PR #2668 opened by Andrew on 2026-10-21 at the maintainer's request (he had reproduced the privately reported bugs by email and asked for one PR per issue). See `STATUS.md`.
