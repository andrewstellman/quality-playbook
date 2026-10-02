# Findings: express

Checkout: /tmp/control/express at 9a34acf03cb818ff3f8bc40e44176e277a25cbb9. Paths are relative to it.

| ID | Location | Observed behaviour |
|---|---|---|
| express-01 | lib/response.js:285-304 (`res.jsonp`) | For a request with `?callback=!!!`, `res.jsonp({a: 1})` responds with `Content-Type: text/javascript` and body `/**/ typeof  === 'function' && ({"a":1});` (the callback name is empty). |
| express-02 | lib/response.js:681 (`res.set` / `res.header`) | `res.set('Content-Type', 'foo'); res.end('x')` sends the header `Content-Type: false` (`res.get('Content-Type')` returns the boolean `false`). If `res.send('x')` is called after that `res.set`, the response goes out with `Content-Type: text/html; charset=utf-8`. |
| express-03 | lib/response.js:404 (`res.sendFile`) | `res.sendFile(path, { etag: false })` in an app with `etag` enabled sends the file with an `ETag` header; the caller's `etag` option is replaced by the app setting. |
| express-04 | lib/response.js:843, 848-849 (`res.redirect`) | `res.redirect(399, '/x')` sends the text body `undefined. Redirecting to /x`; the HTML body contains `<title>undefined</title>` and `<p>undefined. Redirecting to /x</p>`. |
| express-05 | lib/response.js:404 (`res.sendFile`) | After `res.sendFile(path, opts)` returns, the caller's `opts` object has had its `etag` property set to the app's `etag` setting. |
| express-06 | lib/request.js:172-174 (`req.acceptsCharsets`) | With `Accept-Charset: utf-8, iso-8859-1`, `req.acceptsCharsets('utf-8, utf-16')` returns `false`; the string is passed to `accepts().charsets()` unsplit and matched as one charset name. |
| express-07 | lib/response.js:175 (`res.send`) | With the default `etag` setting, `res.send(new Uint16Array([0x4142, 0x4344]))` responds with `Content-Length: 2` and body bytes `42 44` (one byte per element, each element value truncated to 0-255). `res.send(new DataView(buf))` responds 200 with `Content-Length: 0` and an empty body. |
| express-08 | lib/request.js:389 (`req.subdomains` getter) | With `Host: [::ffff:127.0.0.1]:80`, `req.subdomains` returns `["0", "[::ffff:127"]`. The hostname keeps its brackets, `isIP()` returns 0 for it, and it is split on `.`. |
| express-09 | lib/request.js:389 (`req.subdomains` getter) | With `Host: tobi.ferrets.example.com.` (trailing dot) and the default subdomain offset of 2, `req.subdomains` returns `["example", "ferrets", "tobi"]`. |
| express-10 | lib/response.js:172, 218 (`res.send`) | With `app.set('etag', false)`, `res.send(new Uint16Array([256, 513, 1]))` sets `Content-Length: 6`, then `this.end(chunk)` throws `ERR_INVALID_ARG_TYPE` ("must be of type string or an instance of Buffer or Uint8Array") and the request ends with a 500. |
| express-11 | lib/response.js:764-769 (`res.cookie`) | `res.cookie('a', 'b', { maxAge: 500 })` sends `Set-Cookie: a=b; Max-Age=0; Path=/; Expires=<now + 0.5 s>`. |
