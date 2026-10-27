# javalin: enableBasicAuth does not protect WebSocket upgrades

Status: written on 2026-10-20, before submission; `STATUS.md` has what happened since. `PR.md` and `PATCH-AS-SENT.patch` are what went upstream. The disclosure wording in this file is the pre-21 October draft; the PR uses the corrected line. Run record: BUG-037 in `../javalin-security-batch-2026-10-20/BUGS.md` (javalin campaign of 2026-09-29, Quality Playbook v1.6.0).

## The project

Javalin (https://github.com/javalin/javalin) is a lightweight web framework for Kotlin and Java on top of Jetty: HTTP routes, before/after handlers, WebSockets, SSE and static files from one `Javalin.create { }` config.

## The bug

- **Expected:** `enableBasicAuth("u", "p")` ("basic auth for all routes" in the docs) protects WebSocket endpoints as well as HTTP ones.
- **Actual:** the plugin installs a `before` handler only (`BasicAuthPlugin.kt:27`); WebSocket upgrades do not run before-handlers (`JavalinJettyServlet.kt:81-90`), so an upgrade without an `Authorization` header is answered 101. The raw-socket reproduction on unmodified master returned `HTTP/1.1 101 Switching Protocols` (`batch.red.log`, Bug037RegressionTest).
- **Why unnoticed:** the KDoc on the plugin notes that it does not cover WebSockets, and no test exercises it.

## Severity

MEDIUM in the run record (downgraded from HIGH: the plugin's KDoc admits the gap). Any client can open every WebSocket endpoint of an app that relies on `enableBasicAuth` for access control.

## The fix

The plugin also registers a `wsBeforeUpgrade` handler that runs the same `authorized(ctx)` check as the HTTP before-handler and throws `UnauthorizedResponse` with a `WWW-Authenticate: Basic` header when it fails. The KDoc line saying the plugin does not apply to WebSocket upgrades is replaced. Same patch as BUG-028.

```diff
diff --git a/javalin/src/main/java/io/javalin/plugin/bundled/BasicAuthPlugin.kt b/javalin/src/main/java/io/javalin/plugin/bundled/BasicAuthPlugin.kt
index 24b2840..ccca12b 100644
--- a/javalin/src/main/java/io/javalin/plugin/bundled/BasicAuthPlugin.kt
+++ b/javalin/src/main/java/io/javalin/plugin/bundled/BasicAuthPlugin.kt
@@ -7,14 +7,14 @@
 package io.javalin.plugin.bundled
 
 import io.javalin.config.JavalinState
+import io.javalin.http.Context
 import io.javalin.http.Header.WWW_AUTHENTICATE
 import io.javalin.http.UnauthorizedResponse
 import io.javalin.plugin.Plugin
 import java.util.function.Consumer
 
 /**
- * Adds a filter that runs before every http request.
- * Note: It does not apply to websocket upgrade requests
+ * Adds a filter that runs before every http request and every websocket upgrade request.
  */
 class BasicAuthPlugin(userConfig: Consumer<Config>) : Plugin<BasicAuthPlugin.Config>(userConfig, Config()) {
 
@@ -24,18 +24,15 @@ class BasicAuthPlugin(userConfig: Consumer<Config>) : Plugin<BasicAuthPlugin.Con
     }
 
     override fun onStart(state: JavalinState) {
-        state.routes.before { ctx ->
-            val matched = runCatching { ctx.basicAuthCredentials() }
-                .fold(
-                    onSuccess = { auth -> auth?.username == pluginConfig.username && auth?.password == pluginConfig.password },
-                    onFailure = { false }
-                )
+        state.routes.before { ctx -> if (!authorized(ctx)) { ctx.header(WWW_AUTHENTICATE, "Basic"); throw UnauthorizedResponse() } }
+        state.routes.wsBeforeUpgrade { ctx -> if (!authorized(ctx)) { ctx.header(WWW_AUTHENTICATE, "Basic"); throw UnauthorizedResponse() } }
+    }
 
-            if (!matched) {
-                ctx.header(WWW_AUTHENTICATE, "Basic")
-                throw UnauthorizedResponse()
-            }
-        }
+    private fun authorized(ctx: Context): Boolean {
+        val auth = runCatching { ctx.basicAuthCredentials() }.getOrNull() ?: return false
+        val username = pluginConfig.username ?: return false // no configured credentials: nothing can match, fail closed
+        val password = pluginConfig.password ?: return false
+        return auth.username == username && auth.password == password
     }
 
 }
diff --git a/javalin/src/test/java/io/javalin/TestRequest.kt b/javalin/src/test/java/io/javalin/TestRequest.kt
index 583919d..6e01add 100644
--- a/javalin/src/test/java/io/javalin/TestRequest.kt
+++ b/javalin/src/test/java/io/javalin/TestRequest.kt
@@ -18,6 +18,7 @@ import io.javalin.http.servlet.SESSION_CACHE_KEY_PREFIX
 import io.javalin.http.staticfiles.Location
 import io.javalin.plugin.bundled.BasicAuthPlugin
 import io.javalin.testing.TestUtil
+import io.javalin.testing.httpCode
 
 import kong.unirest.Unirest
 import okhttp3.OkHttpClient
@@ -327,6 +328,18 @@ class TestRequest {
         }
     }
 
+    @Test
+    fun `basic auth filter plugin denies every request when no credentials are configured`() {
+        val basicAuthApp = Javalin.create { cfg ->
+            cfg.registerPlugin(BasicAuthPlugin { })
+            cfg.routes.get("/hellopath") { it.result("Hello") }
+        }
+        TestUtil.test(basicAuthApp) { _, http ->
+            assertThat(http.get("/hellopath").httpCode()).isEqualTo(HttpStatus.UNAUTHORIZED)
+            Unirest.get("${http.origin}/hellopath").basicAuth("", "").asString().let { assertThat(it.httpCode()).isEqualTo(HttpStatus.UNAUTHORIZED) }
+        }
+    }
+
     @Test
     fun `servlet-context is not null`() = TestUtil.test { app, http ->
         app.unsafe.routes.get("/") { it.result(if (it.req().servletContext != null) "not-null" else "null") }
diff --git a/javalin/src/test/java/io/javalin/websocket/TestWsUpgrade.kt b/javalin/src/test/java/io/javalin/websocket/TestWsUpgrade.kt
index 5ad234a..f6c80b9 100644
--- a/javalin/src/test/java/io/javalin/websocket/TestWsUpgrade.kt
+++ b/javalin/src/test/java/io/javalin/websocket/TestWsUpgrade.kt
@@ -6,9 +6,12 @@
 
 package io.javalin.websocket
 
+import io.javalin.Javalin
+import io.javalin.http.Header
 import io.javalin.http.HttpStatus
 import io.javalin.security.RouteRole
 import io.javalin.testing.TestUtil
+import kong.unirest.Unirest
 import org.assertj.core.api.Assertions.assertThat
 import org.junit.jupiter.api.Test
 import org.junit.jupiter.api.Timeout
@@ -52,6 +55,19 @@ class TestWsUpgrade {
         assertThat(log).isEmpty()
     }
 
+    @Test
+    fun `basic auth plugin protects websocket upgrades`() = TestUtil.test(Javalin.create { it.bundledPlugins.enableBasicAuth("u", "p") }) { app, http ->
+        val log = ConcurrentLinkedQueue<String>()
+        app.unsafe.routes.ws("/ws") { ws -> ws.onConnect { log.add("connected") } }
+        val denied = http.wsUpgradeRequest("/ws")
+        assertThat(denied.status).isEqualTo(HttpStatus.UNAUTHORIZED.code)
+        assertThat(denied.headers.getFirst(Header.WWW_AUTHENTICATE)).isEqualTo("Basic")
+        val token = java.util.Base64.getEncoder().encodeToString("u:p".toByteArray())
+        val authorized = Unirest.get("${http.origin}/ws").header(Header.SEC_WEBSOCKET_KEY, "not-null").header(Header.SEC_WEBSOCKET_VERSION, "13").header(Header.AUTHORIZATION, "Basic $token").asString()
+        assertThat(authorized.status).isNotEqualTo(HttpStatus.UNAUTHORIZED.code)
+        assertThat(log).isEmpty()
+    }
+
     @Test
     fun `wsBeforeUpgrade exception pattern can be combined with a custom exception handler`() = TestUtil.test { app, http ->
         val log = ConcurrentLinkedQueue<String>()
```

## The regression test

`TestWsUpgrade.basic auth plugin protects websocket upgrades`; asserts 401 with `WWW-Authenticate: Basic` for an upgrade without credentials and not-401 with them. The upgrade request helper in the test suite (`HttpUtil.wsUpgradeRequest`) sends the handshake headers without `Upgrade`, so on unmodified master it gets 405 rather than 101; the 101 on unmodified master is shown by the raw-socket run in `batch.red.log` and by the reviewer's probe (`REVIEW-PANEL.md`). Written in the project's own test style (`TestUtil.test`, Unirest), placed in the existing test file.

- Red on unmodified master `20ba71b` (`../javalin-security-batch-2026-10-20/final.red.log`, 2026-10-20 15:5x UTC, the seven first-version tests with no fixes; `../javalin-security-batch-2026-10-20/final2.red.log`, 16:2x UTC, the revised BUG-055 and BUG-037 tests): `expected: 401 but was: 405`.
- Green with the fixes (`../javalin-security-batch-2026-10-20/final2.green.log`): the eight test classes touched or adjacent pass, 157 tests, 0 failures.
- Full javalin module suite with all six patches applied together (`../javalin-security-batch-2026-10-20/final2.suite.log`, finished 2026-10-20 16:30 UTC): 1020 tests, 0 failures, 5 errors, 21 skipped, 1 flake. The 5 errors are `TestJavalinVueBrowser` ChromeDriver version errors (no matching Chrome in the environment; those tests are also randomly skipped, so the count varies run to run). The flake (`TestWsBeforeAfter.before handlers work`, an existing test that reads a concurrent queue before the close event lands) passed on rerun; websocket tests of the same shape flaked in the baseline run too.
- Baseline on unmodified master (`../javalin-security-batch-2026-10-20/baseline.suite.log`): 1013 tests, 0 failures, 1 ChromeDriver error, 25 skipped, 2 flakes (`TestWebSocket`, `TestWsContext`).
- Revert check: the seven tests fail on unmodified master and pass with the fixes; each branch holds exactly one commit, so reverting the commit is the red run.

## Knock-on effects

Only `BasicAuthPlugin` changes. HTTP behaviour is identical. WebSocket upgrades on apps using the plugin now require the same credentials as HTTP requests; a client library that cannot send `Authorization` on the upgrade would be locked out, which is the documented intent of "basic auth for all routes". The reviewer asked for a config switch or an issue first rather than a silent default change; the patch changes the default, and the PR text says so, so the maintainer can ask for a switch. Ordering: a user's own `wsBeforeUpgrade` handlers registered before the plugin starts run before the plugin's check (the reviewer's probe showed this); the HTTP before-handler has the same property.

## Things to know

- Javalin has no SECURITY.md and no security policy on its Security tab as of 2026-10-20 (checked on GitHub). Whether private vulnerability reporting is enabled was not visible from here. No CLA. The PR template asks for a description and tests.
- Likely pushback: The maintainers documented the gap rather than closing it, so they may consider it intended. The counter-argument is that the plugin is sold as protecting all routes.
- Seven javalin bugs were prepared the same day as six patches (BUG-028 and BUG-037 share one); each patch is an independent commit on master `20ba71b`. The reviewer's severity view: only BUG-055 warrants a private advisory; the others are ordinary public fixes.

## Review history

- 2026-09-30: challenge gate in the run (two fresh sub-agents, see `../javalin-security-batch-2026-10-20/BUGS.md` and the run's `quality/challenge/BUG-037-challenge.md`).
- 2026-10-20: reproduced fresh on current master by the preparing session; independent review of all seven first-version patches by one Opus reviewer (`../javalin-security-batch-2026-10-20/REVIEW-PANEL.md`, with its probe logs). Its required changes were applied: BUG-055 also refuses empty segments (`//`), in both resource handlers, and its test asserts status codes for both aliases; BUG-028 and BUG-037 share one null-safe credential check and one patch, and the plugin KDoc no longer says WebSockets are excluded. Optional suggestions not taken: a startup-time failure for a credential-less BasicAuthPlugin, a config switch for the WebSocket check, hoisting the SSE regex, a details entry in the BUG-033 test. The revised patches were not re-reviewed by the panel; the full panel round of the submission protocol was not run. The deadline for the IEEE Software replication package (2026-11-05) is the reason, and this is noted here rather than hidden.

## Upstream check

- Default branch `master`, head `20ba71b211b5efa91f5c10ccb467326b86a1e5dc` (2026-09-21, "[workflow]: Bump codecov/codecov-action in the dependencies group (#2653)"), fetched 2026-10-20 15:35 UTC. The patch is a commit on that head; it applies cleanly by construction. Local commit: `5a2643872ddcdac2bf17a5ba39d3082638465103` (branch `bug-028-037` in the cloud clone; the patch file is the record).

## Text to submit

Title: [plugins] BasicAuthPlugin: fail closed without configured

Body (PR or advisory description):

> Expected: `enableBasicAuth("u", "p")` ("basic auth for all routes" in the docs) protects WebSocket endpoints as well as HTTP ones.
>
> What happens: the plugin installs a `before` handler only (`BasicAuthPlugin.kt:27`); WebSocket upgrades do not run before-handlers (`JavalinJettyServlet.kt:81-90`), so an upgrade without an `Authorization` header is answered 101. The raw-socket reproduction on unmodified master returned `HTTP/1.1 101 Switching Protocols` (`batch.red.log`, Bug037RegressionTest).
>
> The fix: The plugin also registers a `wsBeforeUpgrade` handler that runs the same `authorized(ctx)` check as the HTTP before-handler and throws `UnauthorizedResponse` with a `WWW-Authenticate: Basic` header when it fails. A regression test is included; the javalin module suite passes.
>
> Found with the Quality Playbook (an AI code-review and test-generation skill); the fix and test were reviewed and run by me.

## Command to submit (Andrew)

Private channel, if the Security tab offers "Report a vulnerability": open https://github.com/javalin/javalin/security/advisories/new, paste the title and body, attach `0001-plugins-BasicAuthPlugin-fail-closed-without-configur.patch` as the suggested fix.

Public channel:

    cd <your javalin fork clone>
    git checkout -b bug-028-037 upstream/master      # upstream master must be 20ba71b or later
    git am <evidence>/javalin-basicauth-websocket-upgrade/0001-plugins-BasicAuthPlugin-fail-closed-without-configur.patch
    mvn -B -pl javalin test -Dtest=<test class from the patch>
    git push origin bug-028-037
    gh pr create --draft --repo javalin/javalin --title "[plugins] BasicAuthPlugin: fail closed without configured" --body-file <body.md>

## Submission record

PR #2667 opened by Andrew on 2026-10-21 at the maintainer's request (he had reproduced the privately reported bugs by email and asked for one PR per issue). See `STATUS.md`.
