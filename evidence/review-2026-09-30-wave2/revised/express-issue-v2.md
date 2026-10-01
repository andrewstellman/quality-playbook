**Title:** res.cookie sends Max-Age=0 (cookie deleted) for a positive maxAge under 1000 ms

`res.cookie(name, value, { maxAge: 500 })` sends a cookie the browser deletes on arrival:

```
a=b; Max-Age=0; Path=/; Expires=<now + 500 ms, truncated to the whole second>
```

In `lib/response.js` (line 769), `opts.maxAge = Math.floor(maxAge / 1000)` turns any positive `maxAge` below 1000 into `Max-Age=0`. `Expires` is an HTTP date with one-second resolution, so it lands anywhere from half a second before to half a second after the response. RFC 6265 gives `Max-Age` precedence over `Expires` (§4.1.2.2) and treats `Max-Age=0` as "expire now" (§5.2.2), so the cookie is removed immediately, the same effect as `res.clearCookie`. The rounding happens in Express, not in the `cookie` package, which serializes whatever `maxAge` it is given.

This comes up when `maxAge` is computed, for example from the time left in a session (`maxAge: session.expiresAt - Date.now()`): in the last second the cookie is deleted instead of kept for the time remaining.

The docs say: "The `maxAge` option is a convenience option for setting “expires” relative to the current time in milliseconds." That doesn't suggest that values under one second delete the cookie.

Reproduces on `master` (9a34acf, express 5.2.1, Node 22):

```js
const express = require('express')
express().get('/', (req, res) => res.cookie('a', 'b', { maxAge: 500 }).end())
  .listen(3000)
// curl -si localhost:3000 | grep -i set-cookie
```

Proposed fix: keep the floor, but send `Max-Age=1` when a positive `maxAge` would otherwise floor to 0. Values of 0 or below, and values of 1000 ms or more, are unchanged. I have a patch with tests (the full test suite passes) and can open a PR if this is wanted.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
