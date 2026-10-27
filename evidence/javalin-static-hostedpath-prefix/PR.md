Both static resource handlers matched `hostedPath` as a string prefix, so with `hostedPath = "/assets"` a request for `/assetsX/app.js` served `X/app.js` from the assets directory without running `before("/assets/*")`. The hosted path is now matched as a whole path segment. The test in `TestStaticFiles` covers both handlers.

Reported to @tipsy by email on 21 Oct. Found with the Quality Playbook, an AI code-review tool I maintain; Claude reproduced it and wrote the fix and test, and I reviewed them.
