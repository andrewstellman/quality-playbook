`res.cookie(name, value, { maxAge: 500 })` sends a cookie the browser deletes on arrival:

```
a=b; Max-Age=0; Path=/; Expires=<now + 0.5 s>
```

In `lib/response.js`, `opts.maxAge = Math.floor(maxAge / 1000)` turns any positive `maxAge` below 1000 into `Max-Age=0`, while `Expires` is still set half a second in the future. RFC 6265 gives `Max-Age` precedence over `Expires` (§4.1.2.2) and treats `Max-Age=0` as "expire now" (§5.2.2), so the cookie is removed immediately, the same result as `res.clearCookie`.

The docs describe `maxAge` as "a convenience option for setting expires relative to the current time in milliseconds", which doesn't suggest that values under one second delete the cookie.

Reproduces on `master` (9a34acf, express 5.2.1, Node 22):

```js
const express = require('express')
express().get('/', (req, res) => res.cookie('a', 'b', { maxAge: 500 }).end())
  .listen(3000)
// curl -si localhost:3000 | grep -i set-cookie
```

Proposed fix: keep the floor, but send `Max-Age=1` when a positive `maxAge` would otherwise floor to 0. `maxAge: 0` and negative values would still send `Max-Age=0`, and values of 1000 ms or more are unchanged. I have a patch with tests (`npm test` passes) and can open a PR if this is wanted.

Found by a Quality Playbook (https://github.com/andrewstellman/quality-playbook) code-review run; the reproduction and the proposed fix were done with Claude (Anthropic) and reviewed by me.
