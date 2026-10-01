**Title:** [plugins] Keep the context path in lowercase-path redirects

`enableRedirectToLowercasePaths()` loses the context path. With `config.router.contextPath = "/blog"` and a route `/users/{name}`, `GET /blog/Users/John` answers `301 Location: /users/John`, which is outside the app (404). Expected `Location: /blog/users/John`.

The plugin strips `ctx.contextPath()` from the path before looking up routes (`RedirectToLowercasePathPlugin.kt:52`), but then builds the Location as `"/" + clientSegments...` (`:90`) without putting it back. This prefixes the redirect with `ctx.contextPath()`, which is `""` for the root context, so apps without a context path are unaffected. Added a test to `TestRedirectToLowercasePathPlugin`.

Relevant docs (javalin.io/documentation, config section):
`config.router.contextPath = stringValue; // the context path (ex '/blog' if you are hosting an app on a subpath, like 'mydomain.com/blog')`
`config.bundledPlugins.enableRedirectToLowercasePaths(); // redirect /Users/John to /users/John`

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
