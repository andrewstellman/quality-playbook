# Code review: express `lib/` (pinned 9a34acf, package version 5.2.1)

Reviewer: opus (express control task, run08)

I checked each finding below by running a small script against a copy of `lib/`, with dependencies installed from `package.json` in a scratch directory. Observed output is quoted.

---

## 1. `res.send()` corrupts or drops the body for typed arrays other than `Uint8Array`, and for `DataView`

- **File/line:** `lib/response.js:151-154` (the `ArrayBuffer.isView` branch), plus `:166-178` (length and Buffer conversion)
- **What goes wrong:** `res.send()` accepts any `ArrayBuffer.isView(chunk)` value as binary. The later code treats it as a byte array:
  - With ETag generation on (the default, `etag: 'weak'`), line 175 runs `Buffer.from(chunk, encoding)`. For a `Uint16Array`, `Float32Array` and similar, `Buffer.from(typedArray)` copies element *values* truncated to 0-255. It does not copy the underlying bytes.
    - `res.send(new Uint16Array([256, 1]))` responds with `Content-Length: 2` and body `<00 01>`. The expected body is 4 bytes.
  - For a `DataView`, `Buffer.from(dataView)` returns an empty buffer. `res.send(new DataView(new ArrayBuffer(4)))` responds with `Content-Length: 0` and an empty body.
  - With ETag off (or an ETag already set), line 172 computes the length correctly. Then `res.end(uint16array)` throws `The "chunk" argument must be of type string or an instance of Buffer or Uint8Array`, so the request fails with a 500.
- **Why it's wrong:** line 151 explicitly accepts every ArrayBuffer view as a binary body and gives it the `bin` content type. The caller gets silently wrong data (default configuration) or an exception, depending on an unrelated setting.
- **Severity:** medium. The data corruption is silent.
- **Fix:** normalize views to a byte Buffer before length and ETag handling:

  ```js
  if (!Buffer.isBuffer(chunk)) chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)
  ```

  Alternatively, narrow the check to `chunk instanceof Uint8Array`.

## 2. `res.set('Content-Type', <extension-like string with no mime mapping>)` writes the literal header `Content-Type: false`

- **File/line:** `lib/response.js:677-682`
- **What goes wrong:** for Content-Type, the value goes through `mime.contentType(value)`. For a string with no `/`, mime-types treats it as an extension. If the lookup fails, it returns `false`, and `this.setHeader(field, false)` sends the header value `"false"`.
  - Observed: `res.set('Content-Type', 'foo')` gives `content-type: "false"`.
- **Why it's wrong:**
  - The doc comment (lines 660-661) says the set only *expands* the value to add a charset.
  - `res.type()` (lines 509-511) handles the same `false` result by falling back to `application/octet-stream`. This shows the intended handling.
  - Any code that reuses the header later also breaks, e.g. `res.send()` string path → `setCharset` → `contentType.parse('false')` throws.
- **Severity:** low
- **Fix:** `value = mime.contentType(value) || value` (or fall back to `application/octet-stream`, matching `res.type`).

## 3. `req.acceptsCharsets()` does not support the comma-delimited form its own documentation promises

- **File/line:** `lib/request.js:146-174`
- **What goes wrong:** the JSDoc says the argument may be "A comma-delimited list of charsets (e.g., `"utf-8, iso-8859-1"`)". It gives the example `req.acceptsCharsets('utf-8, utf-16') // => "utf-8"`. The implementation passes the string straight to `accepts().charsets()`, which does no splitting. The whole string is matched as one charset name.
  - Observed with `Accept-Charset: utf-8, iso-8859-1`: `req.acceptsCharsets('utf-8, utf-16')` returns `false`. The documented result is `"utf-8"`.
- **Why it's wrong:** the behavior contradicts the function's own documented contract and example.
- **Severity:** low
- **Fix:** split string arguments on `,` and trim before delegating:

  ```js
  charsets.flatMap(c => typeof c === 'string' ? c.split(',').map(s => s.trim()) : c)
  ```

  Alternatively, remove the claim from the doc.

## 4. `res.redirect()` renders "undefined" in the body for status codes with no standard message

- **File/line:** `lib/response.js:843, 848-849`
- **What goes wrong:** the body uses `statuses.message[status]` with no fallback.
  - Observed: `res.redirect(299, '/x')` produces the text body `undefined. Redirecting to /x`, and the HTML `<title>undefined</title>`.
- **Why it's wrong:** `res.sendStatus()` in the same file (line 326) guards exactly this case with `statuses.message[statusCode] || String(statusCode)`, so the intended handling is a fallback, not `undefined`.
- **Severity:** low
- **Fix:** compute `var msg = statuses.message[status] || String(status)` once and use it in both templates.

---

## Areas checked and not reported

I checked these and did not find defects I'm confident in:

- **`application.js`:**
  - `use`/mount prototype restoration
  - trust-proxy inheritance on mount
  - `set`/`enabled`
  - `render` option merge and cache
  - `listen` error wiring
- **`view.js`:** lookup and resolve, and the sync-to-async callback normalization.
- **`utils.js`:**
  - `acceptParams`: traced; the leading `;` is skipped via the `splitIndex > endIndex` branch.
  - `compileTrust`, `compileETag`, `compileQueryParser`.
- **`request.js`:** `protocol`, `host`/`hostname` (IPv6), `ips`, `subdomains`, `fresh`.
- **`response.js`:** `download` argument shuffling, `cookie`/`clearCookie`, `jsonp`, `format`, `sendfile` event handling.

## Files read

- /tmp/control/express/lib/application.js
- /tmp/control/express/lib/express.js
- /tmp/control/express/lib/request.js
- /tmp/control/express/lib/response.js
- /tmp/control/express/lib/utils.js
- /tmp/control/express/lib/view.js
- /tmp/control/express/package.json
- /tmp/control/express/test/req.acceptsCharsets.js (grep only)
- /tmp/control/express/test/res.send.js (grep only)
