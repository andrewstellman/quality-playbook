# javalin: the lowercase-path redirect drops the context path

Status: **open and ready for review (marked ready by Andrew on 2026-10-05), [javalin/javalin#2660](https://github.com/javalin/javalin/pull/2660).** Submitted by Andrew on 2026-10-05. See the submission record at the end.

## The project

[javalin/javalin](https://github.com/javalin/javalin) is a small web framework for Java and Kotlin, built on Jetty. You create an app, register routes, and it serves HTTP.

Two of its settings matter here (both from the configuration section of [javalin.io/documentation](https://javalin.io/documentation), read again on 2026-10-05):

```
config.router.contextPath = stringValue; // the context path (ex '/blog' if you are hosting an app on a subpath, like 'mydomain.com/blog')
config.bundledPlugins.enableRedirectToLowercasePaths(); // redirect /Users/John to /users/John
```

- **Context path:** the app lives under a prefix such as `/blog`, so a route `/users/{name}` is served at `/blog/users/{name}`.
- **Lowercase redirect:** a request with capitals in the path is answered with a 301 redirect to the lowercase path.

## The bug

Turn both settings on and the redirect points outside the app.

- App: `contextPath = "/blog"`, route `/users/{name}`, lowercase redirect enabled.
- Request: `GET /blog/Users/John`
- Answer today: `301 Location: /users/John`
- Expected: `301 Location: /blog/users/John`

`/users/John` is not under `/blog`, so the browser follows the redirect to a 404.

The cause is in `RedirectToLowercasePathPlugin.kt`. Line 52 strips the context path so it can look the route up. Line 90 builds the `Location` header from `"/"` and the lowercased segments, and never puts the context path back.

**Where the expectation comes from:** the two documentation lines above. The docs describe each setting separately. They do not have a sentence that says the two work together; the confirmer noted that. The expectation is that a redirect issued by the app stays inside the app.

## The fix

One line: prefix the redirect with `ctx.contextPath()`.

```diff
             ctx.redirect(
-                location = "/" + clientSegments.joinToString("/") + (ctx.queryString()?.let { "?$it" } ?: ""), // lowercase path
+                location = ctx.contextPath() + "/" + clientSegments.joinToString("/") + (ctx.queryString()?.let { "?$it" } ?: ""), // lowercase path
                 status = MOVED_PERMANENTLY
             )
```

`ctx.contextPath()` is the empty string when no context path is set, so apps without one get exactly the same header as before.

The test is added to the existing `TestRedirectToLowercasePathPlugin`:

```diff
+    @Test
+    fun `redirect keeps the context path`() = TestUtil.test(Javalin.create {
+        it.router.contextPath = "/blog"
+        it.registerPlugin(RedirectToLowercasePathPlugin())
+    }) { app, http ->
+        app.unsafe.routes.get("/users/{name}") { it.status(IM_A_TEAPOT) }
+        http.disableUnirestRedirects()
+        val response = http.get("/blog/Users/John")
+        http.enableUnirestRedirects()
+        assertThat(response.httpCode()).isEqualTo(MOVED_PERMANENTLY)
+        assertThat(response.headers.getFirst(Header.LOCATION)).isEqualTo("/blog/users/John")
+    }
```

Total: 2 files, 15 lines added, 1 removed (the plugin +1/-1, the test file +14 including one import).

## Regression test

Run again on 2026-10-05 in the cloud sandbox (OpenJDK 21, the project's own `./mvnw`), on upstream `master` at `20ba71b2`.

- **Green:** with the patch, the test class passes.
  `Tests run: 9, Failures: 0, Errors: 0, Skipped: 0 -- in io.javalin.TestRedirectToLowercasePathPlugin`, `BUILD SUCCESS`.
- **Revert:** with the one-line fix taken out and the test kept, the new test fails for the right reason.
  `expected: "/blog/users/John"` / `but was: "/users/John"` at `TestRedirectToLowercasePathPlugin.kt:94`, `BUILD FAILURE`.
- **Core module suite** (`./mvnw -B -pl javalin test`):
  - Unpatched: `Tests run: 1013, Failures: 0, Errors: 6, Skipped: 20, Flakes: 2`.
  - Fixed: `Tests run: 1014, Failures: 0, Errors: 3, Skipped: 23`.
  - Every error on both sides is a browser test (`TestJavalinVueBrowser`, `TestWebBrowser`) that could not start Chrome: `SessionNotCreated ... This version of ChromeDriver only supports Chrome version 154`. The two flakes on the unpatched run are websocket tests that passed on retry. The counts differ between the runs only in how many browser tests errored versus skipped.
  - The project's own `.github/copilot-instructions.md` says browser tests fail without WebDriver and that this is expected.
  - No non-browser test failed on either side.
- Earlier logs from the first run and the panel are in this folder: `red.log`, `green.log`, `green-class.log`, `revert.log`.

## Knock-on effects

- **Callers.** The plugin is turned on in one place, `BundledPluginsConfig.kt:63` (`enableRedirectToLowercasePaths()`), or by registering `RedirectToLowercasePathPlugin()` directly. The changed line is the only place the plugin builds a `Location`.
- **Before and after, 15 requests.** I ran the same requests against the unpatched and the fixed build on 2026-10-05. The probe route answers 418 so a route hit is easy to tell from a 404.

| Context path | Request | Before | After |
|---|---|---|---|
| none | `/Users/John` | 301 `/users/John` | same |
| none | `/users/John` | 418 (route) | same |
| none | `/USERS/John?x=1&Y=2` | 301 `/users/John?x=1&Y=2` | same |
| none | `/Users/John/` | 301 `/users/John` | same |
| none | `/nope/Here` | 404 | same |
| none | `/` | 418 (route) | same |
| `/blog` | `/blog/Users/John` | 301 `/users/John` | 301 `/blog/users/John` |
| `/blog` | `/blog/users/John` | 418 (route) | same |
| `/blog` | `/blog/USERS/John?x=1&Y=2` | 301 `/users/John?x=1&Y=2` | 301 `/blog/users/John?x=1&Y=2` |
| `/blog` | `/blog/Users/John/` | 301 `/users/John` | 301 `/blog/users/John` |
| `/blog` | `/blog/nope/Here` | 404 | same |
| `/blog` | `/blog/` | 418 (route) | same |
| `/blog` | `/Users/John` | 404 | same |
| `/api/v1` | `/api/v1/Users/John` | 301 `/users/John` | 301 `/api/v1/users/John` |
| `/api/v1` | `/api/v1/users/John` | 418 (route) | same |

- **What changes for users.** Only apps that set a context path and enable the lowercase redirect. Their redirects now include the context path. Everything else is identical: the query string is still carried over, the trailing slash is still dropped, and requests that did not redirect before still do not.
- **Who could be surprised.** Reviewer S5 raised one case: someone who noticed the broken `Location` and worked around it in a reverse proxy by adding the prefix there would now get the prefix twice. The panel judged that unlikely. It is the only case anyone found.

## Review history

- **Confirmed** by an independent confirmer: `docs/research/campaign-2026-09-29/confirm/LEDGER.md` line 148 (`BUG-025 lowercase redirect drops contextPath`, CONFIRMED).
- **Full panel** (2 executors and 13 reviewers), review id `jav-025`: `evidence/review-2026-09-30-wave2/SYNTHESIS.md`. 14 SHIP. S4 said FIX-REQUIRED with one optional suggestion: have the test follow the redirect as well as check the header. The synthesis ruled it not required.
- **O4** looked at how the project treats AI-assisted changes and found that it merges agent-written fixes (for example #2618 from the Copilot coding agent).

## Upstream check (2026-10-05)

- `master` is at `20ba71b2` (2026-09-21, a dependabot bump). The two commits before it are from the maintainers, on 2026-09-15 and 2026-09-04.
- The patch applies cleanly with `git am`. The base blobs match the patch (`8651f9ca`, `3e2d6af6`) and so do the results (`83b62813`, `f7ad8852`). Resulting tree: `26ab82b8527d144730f6d0e9fd7140f8c7ecf96b`.
- The line numbers in the PR text (`:52` and `:90`) are correct at this commit.
- **Duplicate scan by git.** I fetched all 1262 pull-request heads. 40 heads that are not on `master` touch the plugin or its test. All are older refactors (the newest is from 2026-03-19) and none changes how the redirect `Location` is built. Git cannot tell me which of those are open and which are closed, and I did not search the issue tracker (no `gh` here).

## Things to know before submitting

- **No contributor paperwork found.** The repository has no CONTRIBUTING, AGENTS.md or SECURITY file at this commit. I cannot see whether a CLA bot will comment after the PR opens.
- **Commit subject.** The project writes subjects as `[area] Description`. The patch has `[plugins] ...`, but plain `git am` removes a bracketed prefix from the subject. I changed one line in the submit script on 2026-10-05, from `git am "$PATCH"` to `git am --keep-non-patch "$PATCH"`, and confirmed here that the commit keeps `[plugins]`. The PR title is set separately and was always correct.
- **The script's local check** runs `./mvnw -B -q -pl javalin test -Dtest=TestRedirectToLowercasePathPlugin`. It needs a JDK (17 or newer) and downloads Maven dependencies the first time. `SKIP_TESTS=1` skips it; the same test ran here on the same upstream commit. If the check fails, the branch already exists, and the script will tell you the command to delete it before a rerun.
- **I checked the edited script with `bash -n` only.** There is no zsh in the shell I can reach, so the zsh syntax check was not run.
- **I did not see the project's CI.** The browser tests could not run here, on either the unpatched or the fixed build.
- **The docs do not promise the combination** in so many words (see "The bug"). The PR text quotes the two lines and does not claim more than that.

## The PR as it will be submitted

**Title:** [plugins] Keep the context path in lowercase-path redirects

> `enableRedirectToLowercasePaths()` loses the context path. With `config.router.contextPath = "/blog"` and a route `/users/{name}`, `GET /blog/Users/John` answers `301 Location: /users/John`, which is outside the app (404). Expected `Location: /blog/users/John`.
>
> The plugin strips `ctx.contextPath()` from the path before looking up routes (`RedirectToLowercasePathPlugin.kt:52`), but then builds the Location as `"/" + clientSegments...` (`:90`) without putting it back. The fix prefixes the redirect with `ctx.contextPath()`, which is `""` for the root context, so apps without a context path are unaffected. Added a test to `TestRedirectToLowercasePathPlugin`.
>
> Relevant docs (javalin.io/documentation, config section):
> `config.router.contextPath = stringValue; // the context path (ex '/blog' if you are hosting an app on a subpath, like 'mydomain.com/blog')`
> `config.bundledPlugins.enableRedirectToLowercasePaths(); // redirect /Users/John to /users/John`
>
> Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

**Commit message** (author Andrew Stellman <andrew@stellman.com>, no trailers):

```
[plugins] Keep the context path in lowercase-path redirects

RedirectToLowercasePathPlugin strips the context path to match routes
but built the Location from "/" alone, so with contextPath = "/blog" a
request to /blog/Users/John was redirected to /users/John, outside the
app. Prefix the redirect with ctx.contextPath().
```

## To submit

```zsh
zsh ~/Documents/QPB/evidence/SUBMIT/submit-javalin-lowercase-redirect-contextpath.sh
```

Or, to skip the local Maven check:

```zsh
SKIP_TESTS=1 zsh ~/Documents/QPB/evidence/SUBMIT/submit-javalin-lowercase-redirect-contextpath.sh
```

The script forks javalin/javalin if needed, creates branch `lowercase-redirect-context-path` from upstream `master`, applies the patch, pushes to your fork, and opens a **draft** PR. It prints the PR number, URL, draft state and title at the end.

## Submission record

- **Submitted:** 2026-10-05 by Andrew, after reviewing this file, using `submit-javalin-lowercase-redirect-contextpath.sh`. His paste of the script output: `"isDraft": true`, `"number": 2660`, `"title": "[plugins] Keep the context path in lowercase-path redirects"`.
- **PR:** [javalin/javalin#2660](https://github.com/javalin/javalin/pull/2660), opened as a **draft** from `andrewstellman:lowercase-redirect-context-path` into `javalin:master`; 1 commit, `99b9b6e8b38418ba8e5ff29841069d936283e08c`.
- **Verified by git (2026-10-05 15:23 UTC, `git fetch` of `refs/pull/2660/head`):**
  - One commit on top of `20ba71b2`, which is still the tip of `master`.
  - Tree `26ab82b8527d144730f6d0e9fd7140f8c7ecf96b`, identical to the reviewed tree. `git diff` between the reviewed commit and the PR head is empty.
  - Blobs: the plugin `8651f9ca..83b62813`, the test file `3e2d6af6..f7ad8852`, the same as the patch.
  - Subject is `[plugins] Keep the context path in lowercase-path redirects`, so the `--keep-non-patch` change worked. The commit message body matches the patch. No trailers.
  - Author: `Andrew Stellman <andrew@stellman.com>`. Committer: `andrewstellman <astellman@stellman-greene.com>`, 2026-10-05 11:22:27 -0400 (the local git identity on Andrew's Mac).
- **Title and description:** the title in Andrew's paste matches. The fetch tool's reading of the PR page gave the description word for word as above, base `javalin:master`, 1 commit, and no comments. That tool is a summary and has been wrong about draft state before, so treat the description check as likely, not proven. The exact check is `gh pr view 2660 --repo javalin/javalin --json title,body,isDraft`.
- **Not checked:** CI results, and whether any bot has commented since.
- **Still to do on Andrew's side:** nothing until a maintainer responds.
- **2026-10-05 17:53 -04:00:** Andrew ran `gh pr view --json number,isDraft,state,url` for this PR. Output: `draft=false  OPEN`. He had marked it ready in the web UI. It is open and ready for review.
- **Maintainer responses:** none seen.
