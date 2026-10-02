# Code Review: express `lib/` (expressjs/express @ 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

## Defect 1: `res.set()`/`res.header()` can write a literal `false` (as text) into the `Content-Type` header

- **File / line:** `lib/response.js`, lines 669–691 (the `res.set = res.header = function header(field, val)` block; the faulty statement is `value = mime.contentType(value)` at line 681).

- **What goes wrong:** When `res.set('Content-Type', <value>)` (or `res.header(...)`) is called with a string that has no `/` and is not a filename extension known to `mime-types`' extension table, `mime.contentType(value)` returns the boolean `false`. That `false` is assigned into `value` and then passed straight to `this.setHeader(field, value)` with no fallback. Node's `http.ServerResponse.setHeader` accepts the boolean silently and stringifies it when the response is flushed, so the client receives a literal `Content-Type: false` header.

  Reproduced against the actual checkout:
  ```js
  const express = require('express');
  const app = express();
  app.get('/', (req, res) => {
    res.set('Content-Type', 'foo');   // typo / unknown extension / empty upstream value
    res.end('ok');
  });
  ```
  Raw response observed:
  ```
  HTTP/1.1 200 OK
  X-Powered-By: Express
  Content-Type: false
  ...
  ```
  This also triggers for an empty string (`res.set('Content-Type', '')`) and for any unrecognized bare word (`'bogus-ext'`), which are realistic inputs when the value is forwarded from another source (e.g. proxying an upstream `Content-Type`, or a bug elsewhere that hands `res.set` an extension name instead of a MIME type).

- **Why it is wrong:** The function's own doc comment says: *"When the set header is 'Content-Type', the type is expanded to include the charset if not present using `mime.contentType()`."* Actually adding a charset never contemplates replacing the whole value with `false`. Contrast with `res.type()` a few lines earlier in the same file (`lib/response.js` line ~507-514), which calls the exact same API but explicitly guards the falsy case:
  ```js
  res.contentType =
  res.type = function contentType(type) {
    var ct = type.indexOf('/') === -1
      ? (mime.contentType(type) || 'application/octet-stream')
      : type;
    return this.set('Content-Type', ct);
  };
  ```
  `res.type()` knows `mime.contentType()` can return `false` and falls back to `application/octet-stream`; `res.set()`/`res.header()` makes the identical call with no such guard, so the exact same lookup failure that `res.type()` handles safely corrupts the header when reached through `res.set()`/`res.header()` instead. It is also inconsistent with the project's own `History.md` (Unreleased section), which documents that `res.set('Content-Type', 'text/plain; foo=bar')` is expected to be preserved as given (charset is only appended later, in `res.send()`, per the `content-type@^2.0.0` upgrade note) — not silently discarded.

  The existing test file `test/res.set.js` only exercises Content-Type values that already contain a `/` (e.g. `'text/x-foo; charset=utf-8'`, `'text/html; charset=lol'`), so this no-slash/unresolvable path has no test coverage.

- **Severity:** Medium-high. It's a silent data-corruption bug (a nonsensical header value shipped to clients), reachable with ordinary, plausible inputs (a typo, an empty string, or an unrecognized/forwarded value), and it fails silently rather than throwing — the opposite of the loud `TypeError`/`RangeError` this same file uses elsewhere for bad input (e.g. `res.status`). It's not itself a memory-safety or auth bypass issue, but a broken `Content-Type` can affect MIME-sniffing behavior in clients/browsers, which has downstream security implications when the body is attacker-influenced.

- **Suggested fix:** Mirror the guard already used in `res.type()`:
  ```js
  if (field.toLowerCase() === 'content-type') {
    if (Array.isArray(value)) {
      throw new TypeError('Content-Type cannot be set to an Array');
    }
    value = mime.contentType(value) || value;   // keep the original value instead of `false`
  }
  ```
  or throw a `TypeError` explaining the value could not be resolved to a content type, consistent with the array-value case just above it.

## Other areas reviewed, no defects found

I read through `lib/application.js`, `lib/express.js`, `lib/view.js`, `lib/utils.js`, and the rest of `lib/response.js` and `lib/request.js` looking for logic errors, edge-case mishandling, error-handling mistakes, concurrency issues, and API misuse. Items I specifically checked and confirmed are intentional/correct (not defects), using `History.md` in the same checkout and/or executing the code:

- `res.status()` throwing `TypeError`/`RangeError` for non-integer or out-of-range codes — documented intentional behavior change (`History.md` line ~99-101).
- `req.fresh` accepting `QUERY` in addition to `GET`/`HEAD` — documented intentional feature (`History.md`, "Allow conditional revalidation for QUERY requests").
- Removal of the `'back'` magic string from `res.redirect()`/`res.location()` — documented intentional removal (`History.md` line 103).
- `res.download()`'s cascading `typeof` checks for the `(path, filename, options, callback)` overloads — traced through all four call shapes; the third `if` block correctly restores `opts` after the second block nulls it out for the `(path, options, callback)` call shape. Behaves as intended.
- `app.defaultConfiguration()`'s trust-proxy inheritance back-compat (`trustProxyDefaultSymbol`) and the `mount` event's prototype rewiring — consistent, no logic gaps found.
- `View` lookup/resolve logic and `sendfile()`'s aborted/error/finish handling in `response.js` — standard, matches documented behavior, guards against double-firing the callback via the `done` flag.

## Files read

- `/tmp/control/express/lib/utils.js`
- `/tmp/control/express/lib/application.js`
- `/tmp/control/express/lib/request.js`
- `/tmp/control/express/lib/response.js`
- `/tmp/control/express/lib/view.js`
- `/tmp/control/express/lib/express.js`
- `/tmp/control/express/index.js`
- `/tmp/control/express/package.json`
- `/tmp/control/express/History.md`
- `/tmp/control/express/test/res.set.js` (to check existing test coverage around the defect)

Verification performed by copying `lib/` (plus `index.js`/`package.json`) into a scratch directory, installing the pinned dependency versions from `package.json`, and running the actual `res.set('Content-Type', 'foo')` path through a live `http.Server` to inspect the raw wire bytes.
