# Exploration Findings — Express v5.2.1

> Target: `/Users/andrewstellman/Documents/QPB/repos/express-1.5.8`
> The directory name `express-1.5.8` is the QPB **skill** version (1.5.8). The
> framework under audit is **Express v5.2.1** (`package.json:version`).

## Domain and Stack

- **Domain:** HTTP server framework for Node.js — routing, middleware composition,
  request parsing, and response shaping over `node:http`.
- **Language / runtime:** JavaScript (CommonJS), Node.js. `'use strict'` throughout.
- **Build / packaging:** npm; `package.json` declares `"version": "5.2.1"`,
  entry `index.js` → `lib/express.js`.
- **Test framework:** Mocha 10.7.3 + supertest; 70 test files under `test/`.
- **Key dependencies (behavioral boundaries):** `router@2.2.0` (all routing/mounting —
  NOT in `lib/`), `send@1.1.0` + `serve-static@2.2.0` (file streaming), `accepts@2.0.0` +
  `type-is@2.0.1` (negotiation), `fresh@2.0.0`, `etag@1.8.1`, `cookie@0.7.1` +
  `cookie-signature@1.2.1`, `proxy-addr@2.0.7` (trust proxy), `content-type@1.0.5`,
  `content-disposition@1.0.0`, `mime-types@3.0.0`, `qs@6.14.2`.
- **External systems:** none directly; the framework's "peers" are HTTP clients,
  reverse proxies (via `X-Forwarded-*`), template engines (via `__express`), and the
  filesystem (via `send`/`view`).
- **Primary output:** an `app` request handler `(req, res) => …` plus the augmented
  `req`/`res` prototypes.

## Architecture

- **Entry:** `lib/express.js:36-56` `createApplication()` builds the `app` function,
  mixes in `EventEmitter` + the `application` proto, creates per-app `request`/`response`
  prototypes (each `Object.create`'d from `lib/request.js`/`lib/response.js`) and calls
  `app.init()`.
- **Application layer:** `lib/application.js` — settings store, middleware mounting
  (`app.use` 190-244), HTTP-verb dispatch (`app[METHOD]` 471-482), request entry
  (`app.handle` 152-178 → `this.router.handle`), settings compilation (`app.set`
  351-383), view rendering (`app.render` 522-575).
- **Request layer:** `lib/request.js` — getters for `protocol`/`host`/`hostname`/`ip`/
  `ips`/`subdomains`/`fresh`, plus `accepts*`, `is`, `get`, `range`, `query`.
- **Response layer:** `lib/response.js` (1047 LOC, the most complex/fragile module) —
  `send`/`json`/`jsonp`/`sendFile`/`download`/`redirect`/`format`/`cookie`/`set` etc.
- **Utilities:** `lib/utils.js` — `compileETag`/`compileQueryParser`/`compileTrust`,
  `setCharset`, `normalizeType(s)`, hand-rolled `acceptParams`.
- **Views:** `lib/view.js` — `View` lookup/resolve/render with a two-level path fallback.
- **Data flow:** HTTP request → `app.handle` → `router.handle` (external) → middleware /
  route handler → `res.*` shaping → `res.end`. Most defects hide in the `res.*` shaping
  and in trust-proxy header parsing where the framework re-derives values from untrusted input.

## Existing Tests

- **Framework:** Mocha; import pattern is `var express = require('..')` (resolves to
  `index.js` → `lib/express.js`) — Phase 2/3 tests MUST use this exact `require('..')` form.
- **Support:** `test/support/env.js` (sets `NODE_ENV=test`, `NO_DEPRECATION`),
  `test/support/utils.js` (assertion helpers), `test/support/tmpl.js`.
- **Count / shape:** 70 `test/*.js` files, one per public method (`res.send.js`,
  `res.jsonp.js`, `req.host.js`, …), plus `test/acceptance/` exercising `examples/`.
- **Coverage character:** broad happy-path + a good number of edge cases per method.
  Observed gaps (see Quality Risks): non-standard status codes through `res.redirect`,
  empty/comma-only `X-Forwarded-*` headers, the string-vs-Buffer charset asymmetry in
  `res.send`, and `res.jsonp` callback-sanitization corner cases.

## Specifications

- `reference_docs/` holds 15 gathered markdown docs (API reference, routing/middleware
  guides, security best practices, known-vulnerabilities catalog). `reference_docs/cite/`
  is **empty** → `bin/reference_docs_ingest` wrote **0 FORMAL_DOC records** to
  `quality/formal_docs_manifest.json`. All gathered docs are **Tier 4** context.
- Consequence: the run is **Spec-Gap** for citation purposes — REQs will be Tier 3
  (code-is-the-spec) backed by Tier-4 docs. No fabricated Tier-1/2 citations.
- `History.md` (the changelog) is the strongest behavioral spec for v5 semantics: it
  documents (a) `res.status()` integer-only 100–999 (`History.md:63`), (b) removal of
  `res.send(status, body)` and `res.json(status, obj)` legacy signatures
  (`History.md:173-247`), (c) "Avoid duplicate Content-Type processing in `res.send()`"
  (`History.md:15`), (d) proper 205 support (`History.md:324`).

## Open Exploration Findings

1. **`res.send` forces charset to utf-8 for string bodies but preserves it for Buffers —
   an asymmetry.** For a string body, `lib/response.js:137-143` reads the existing
   `Content-Type` and, if present, rewrites it with `setCharset(type, 'utf-8')`
   (`lib/response.js:140`), overwriting any caller-set charset. For a Buffer/typed-array
   body the charset is left untouched (`lib/response.js:150-153` only sets `bin` when no
   type). The test suite locks both behaviors in: `test/res.send.js:112-121` asserts a
   string send overrides `charset=iso-8859-1`→`utf-8`, while `test/res.send.js:125-134`
   asserts a Buffer send keeps `charset=iso-8859-1`. This is intended v5 behavior but is a
   genuine "two surfaces that should behave the same drift on edge inputs" asymmetry worth
   a parity REQ (see Asymmetry-Promotion below): a caller who sets a non-utf-8 charset and
   sends a string silently gets utf-8.

2. **`req.protocol` trusts an empty `X-Forwarded-Proto` header over the real protocol.**
   `lib/request.js:309` computes `var header = this.get('X-Forwarded-Proto') || proto`.
   The `|| proto` fallback only fires when the header is *absent*. If a trusted proxy is
   misconfigured and sends `X-Forwarded-Proto:` (present but empty string), `this.get`
   returns `''` which is falsy, so `proto` is used — OK. But a header value of `" , https"`
   (leading empty element) makes `index = header.indexOf(',')` = 1 and returns
   `header.substring(0,1).trim()` = `''` (`lib/request.js:310-314`), yielding an empty
   protocol string instead of `http`/`https`. `req.secure` (`lib/request.js:326-328`) then
   compares `'' === 'https'` → false, silently downgrading a secure request.

3. **`req.host` mixes trust check and value selection so a present-but-empty
   `X-Forwarded-Host` from an untrusted peer is handled inconsistently.** `lib/request.js:418-431`:
   `val = this.get('X-Forwarded-Host')`; the guard `if (!val || !trust(...))` falls back to
   the `Host` header, but the comma-trimming branch (`else if (val.indexOf(',') !== -1)`,
   `lib/request.js:424-427`) only runs for trusted peers with a comma. A trusted XFH of
   `"a.com,"` (trailing comma) returns `val.substring(0, val.indexOf(',')).trimRight()` =
   `"a.com"` — fine — but `",a.com"` returns `""`. `req.hostname` (`lib/request.js:444-458`)
   then derives from an empty host and returns `undefined`, so `req.subdomains`
   (`lib/request.js:383-394`) returns `[]`. This traces a value across `host` → `hostname`
   → `subdomains`.

4. **`res.redirect` emits malformed bodies for status codes `statuses` doesn't know.**
   `lib/response.js:841` and `:846-847` build the body from `statuses.message[status]`.
   `res.redirect` accepts any number as the status (`lib/response.js:818-821`). For a
   non-redirect/unknown code (e.g. `res.redirect(310, '/x')` — 310 is unassigned),
   `statuses.message[310]` is `undefined`, so the text body becomes
   `"undefined. Redirecting to /x"` and the HTML `<title>undefined</title>`. `res.status`
   is later called with 310 (`lib/response.js:856`) which passes the 100–999 range check
   (`lib/response.js:70`), so nothing rejects it. Traces `redirect` → `format` →
   `statuses.message`.

5. **`res.jsonp` callback sanitization keeps `$`, `.`, `[`, `]` — produces member-access
   payloads in the response body.** `lib/response.js:286`:
   `callback = callback.replace(/[^\[\]\w$.]/g, '')`. The whitelist intentionally allows
   `[`, `]`, `$`, `.` to support `?callback=foo.bar` / `?callback=ns['fn']`. The body is
   then `'/**/ typeof ' + callback + ' === \'function\' && ' + callback + '(' + body + ');'`
   (`lib/response.js:300`). A callback like `a.constructor.constructor` survives the filter
   and is reflected into a `text/javascript` body (`lib/response.js:283`); the `/**/`
   prefix + `typeof … === 'function'` guard (`lib/response.js:298-300`) is the mitigation,
   but the whitelist is broader than a bare-identifier check. Worth a parsing-fidelity REQ.

6. **`res.set('Content-Type', …)` and `res.send`'s `setCharset` both touch the type, risking
   double processing.** `res.set` (`lib/response.js:672-677`) runs every Content-Type value
   through `mime.contentType(value)` (which appends `; charset=utf-8` for text types). Then
   for string `res.send`, `lib/response.js:140` calls `setCharset(type, 'utf-8')` on the
   already-charset-bearing value. `History.md:15` explicitly records a v5 fix to "avoid
   duplicate Content-Type header processing in `res.send()`", confirming this interaction is
   a known fragility surface. Traces `res.set` → `mime.contentType` → `res.send` →
   `setCharset` (`lib/utils.js:225-238`).

7. **`res.cookie` floors a sub-1000ms `maxAge` to `0` seconds while still setting a future
   `expires`.** `lib/response.js:759-766`: `opts.expires = new Date(Date.now() + maxAge)`
   (ms-accurate) but `opts.maxAge = Math.floor(maxAge / 1000)` (seconds). For
   `maxAge: 500`, the serialized cookie carries `Max-Age=0` (expire-now per RFC 6265 §5.2.2)
   alongside an `Expires` ~500ms in the future — contradictory directives; UAs that honor
   `Max-Age` over `Expires` drop the cookie immediately. `res.clearCookie`
   (`lib/response.js:709-716`) deliberately deletes `maxAge` to avoid this collision,
   showing the author is aware of the `expires`/`maxAge` interaction.

8. **`res.send` Content-Length uses string `.length` (UTF-16 code units) as the
   small-chunk gate, not byte length.** `lib/response.js:170`:
   `else if (!generateETag && chunk.length < 1000)` then `len = Buffer.byteLength(chunk, encoding)`.
   The *threshold test* is on character count, but the value assigned is byte length, so
   `Content-Length` itself is correct. The subtlety: a 999-character multibyte string
   (≈3000 bytes) takes the "small chunk" path and is `Buffer.byteLength`'d but never
   converted to a Buffer, while a ≥1000-char string is converted (`lib/response.js:173-177`).
   Both yield correct `Content-Length`; the residual risk is downstream code assuming the
   `< 1000` branch implies a small *payload*. Flagged as low-confidence.

9. **`req.ips` mutates the array returned by `proxyaddr.all` in place.** `lib/request.js:363`:
   `addrs.reverse().pop()` then `return addrs`. If `proxy-addr` ever returns a cached/shared
   array, the reverse+pop corrupts shared state. Today `proxyaddr.all` returns a fresh array,
   so this is latent, but it is an in-place mutation of a value owned by a dependency.

10. **`res.download` builds `Content-Disposition` from `name || path` without guarding a
    non-string `path`.** `lib/response.js:457`: `contentDisposition(name || path)`. When
    `download(path, opts)` is called with an options object as the 2nd arg
    (`lib/response.js:449-453` sets `name = null`), the disposition is derived from `path`.
    `res.sendFile` later enforces `typeof path === 'string'` (`lib/response.js:382-384`), but
    `contentDisposition` runs first (`lib/response.js:456-458`) — order means a non-string
    path throws inside `content-disposition` rather than via Express's clearer message.
    Traces `download` → `contentDisposition` → `sendFile` validation.

11. **`app.get` overloads "read a setting" and "register a GET route" by argument count.**
    `lib/application.js:471-482`: `if (method === 'get' && arguments.length === 1) return this.set(path)`.
    So `app.get('etag')` reads the setting, but `app.get('/etag')` with a single function
    arg-count of 1 (just the path, no handler) — actually `arguments.length === 1` means the
    path alone — returns the *setting value* for `'/etag'` (`undefined`) instead of creating a
    route. A caller who writes `app.get('/health')` intending to look up later, or who omits
    the handler, gets a silent settings read, not a route registration error.

12. **`View.prototype.resolve` returns `undefined` on miss with no error context, and the
    error string in `app.render` pluralizes ad hoc.** `lib/view.js:169-187` tries
    `<dir>/<file>.<ext>` then `<dir>/<basename>/index.<ext>` and returns `undefined` if both
    `tryStat` calls miss (`lib/view.js:197-205` swallows all stat errors). `app.render`
    (`lib/application.js:558-564`) then constructs a "Failed to lookup view" error, switching
    between "directory"/"directories" by hand. A permission error (`EACCES`) on the view dir
    is indistinguishable from "not found" because `tryStat` returns `undefined` for both.

## Quality Risks

1. **Secure-request downgrade via crafted `X-Forwarded-Proto` (HIGH).** Because
   `lib/request.js:309-314` returns `header.substring(0, index).trim()` for a comma-bearing
   value, a trusted-proxy request with `X-Forwarded-Proto: ", https"` makes `req.protocol`
   `''`, `req.secure` false (`lib/request.js:326-328`). Domain edge case: proxies that
   concatenate empty values. Wrong behavior: HTTPS-only middleware (`if (!req.secure) redirect`)
   loops or 403s a legitimately-secure client. Check: feed `X-Forwarded-Proto` values
   `""`, `","`, `", https"`, `"https,"` with trust proxy enabled.

2. **Cookie silently dropped for sub-second `maxAge` (HIGH).** `lib/response.js:764`
   `Math.floor(maxAge/1000)` yields `Max-Age=0` for any `maxAge < 1000`. Edge case: code
   that sets short-lived flash cookies (`maxAge: 250`). Wrong behavior: the cookie is
   serialized with `Max-Age=0`, instructing the UA to expire it immediately, even though
   `Expires` is in the future. Check: `res.cookie('x','1',{maxAge:500})` and assert the
   `Set-Cookie` does not contain `Max-Age=0`.

3. **`res.redirect` to a non-standard status emits `"undefined. Redirecting to …"`
   (MEDIUM).** `lib/response.js:841,846-847` dereference `statuses.message[status]` with no
   fallback; `res.redirect(310,'/x')` passes the range guard at `lib/response.js:70`/`:856`.
   Edge case: API gateways using 3xx codes outside the well-known set, or a typo'd status.
   Wrong behavior: the body and `<title>` contain the literal text `undefined`. Check: assert
   redirect body for an unknown 3xx code.

4. **JSONP callback whitelist admits member-access expressions (MEDIUM).**
   `lib/response.js:286` permits `[`, `]`, `$`, `.`; the reflected body at
   `lib/response.js:300` is `text/javascript`. Edge case: `?callback=a.b.c` or
   `?callback=x['y']`. Wrong behavior: although the `typeof … === 'function'` guard blocks
   execution of non-functions, the response still reflects attacker-influenced property
   chains into an executable content type; a stricter "valid JS identifier" check is the
   standard mitigation. Check: a callback of `alert(1)//` (filtered to `alert1`) vs
   `a.constructor` (survives).

5. **Charset asymmetry between string and Buffer `res.send` (MEDIUM).**
   `lib/response.js:140` forces utf-8 for strings; `lib/response.js:150-153` leaves Buffers
   alone. Edge case: an app that sets `charset=iso-8859-1` and conditionally sends a string
   or a Buffer for the same route. Wrong behavior: the declared charset depends on the body's
   JS type, not the app's intent — the same logical response advertises two different
   charsets. Check: send `'é'` as a string vs as `Buffer.from('é','latin1')` with a
   pre-set latin1 Content-Type and compare the emitted header.

6. **Present-but-empty `X-Forwarded-Host` yields `undefined` hostname/subdomains (MEDIUM).**
   `lib/request.js:424-427` + `:444-458` + `:383-394`. Edge case: trusted proxy sends
   `X-Forwarded-Host: ,real.example.com`. Wrong behavior: `req.hostname` is `undefined`,
   breaking subdomain-based routing/tenant resolution. Check: trusted XFH values with leading
   commas.

7. **`res.send` of `0` / `false` / `''` body interacts with 204/304 stripping (LOW–MEDIUM).**
   `lib/response.js:145-157` routes numbers/booleans/objects; the 204/304 branch
   (`lib/response.js:195-200`) blanks the body and strips Content-Length. Edge case: a
   handler that does `res.status(304).send(0)` expecting `"0"`. Wrong behavior: body is
   forced empty (spec-correct for 304, but surprising). Check: behavior of falsy bodies at
   204/304/205 (`lib/response.js:202-207`).

## Skeletons and Dispatch

- **Settings-compilation dispatch (`app.set`, `lib/application.js:363-380`).** A `switch`
  on the setting name compiles `etag`/`query parser`/`trust proxy` eagerly into functions
  (`compileETag`/`compileQueryParser`/`compileTrust`, `lib/utils.js:130-214`). Each compiler
  is itself a small `switch`/if-chain with a `default: throw new TypeError(...)`
  (`lib/utils.js:148`, `:180`). Defensive pattern: invalid setting values fail fast at
  config time, not request time.
- **`app[METHOD]` dynamic dispatch (`lib/application.js:471-482`).** Generated per HTTP
  method with the `get`-as-getter special case (line 473-476) — a state/branch worth tracing.
- **`res.send` type switch (`lib/response.js:133-158`).** `typeof chunk` →
  string/boolean/number/object branches; `null`→`''`, typed-array→`bin`, plain object→
  `this.json(chunk)`. The dispatch determines charset/Content-Type behavior.
- **`sendfile` streaming state machine (`lib/response.js:921-1009`).** `done` +
  `streaming` flags toggled by `onfile`/`onstream`/`onaborted`/`ondirectory`/`onerror`/
  `onend`/`onfinish`. The guard `if (streaming !== false && !done)` (`lib/response.js:971`)
  treats `undefined` streaming as "still streaming → abort".
- **Trust-proxy default inheritance (`lib/application.js:102-122`).** A
  `trustProxyDefaultSymbol` flag controls whether a child app inherits the parent's trust
  setting; `app.set('trust proxy', …)` clears it (`lib/application.js:371-377`).
- **No mechanical dispatch-table extraction applies** — these switches are over JS
  values/method names, not a closed set of named C-style constants, so no `*_cases.txt`
  witness is generated (recorded NOT APPLICABLE in PROGRESS.md).

## Pattern Applicability Matrix

| Pattern | Decision (`FULL` / `SKIP`) | Target modules | Why |
|---|---|---|---|
| Fallback and Degradation Path Parity | `SKIP` | trust-proxy fallbacks | Fallbacks exist (`req.protocol`/`host` proxy-vs-socket) but they are covered more directly by Cross-Implementation Consistency below; deferring avoids double-counting the same `X-Forwarded-*` code. |
| Dispatcher Return-Value Correctness | `SKIP` | `app[METHOD]`, `app.set` | The dispatchers return `this`/setting values uniformly; no Linux-style "return 0 instead of -ERR" surface. Low yield here. |
| Cross-Implementation Consistency | `FULL` | `lib/request.js`, `lib/response.js` | Multiple surfaces re-derive the same value (string vs Buffer charset; `X-Forwarded-Proto` vs `-Host` parsing) and must agree. High yield. |
| Enumeration and Representation Completeness | `SKIP` | `statuses.message`, `res.format` | Status/MIME sets are owned by dependencies (`statuses`, `accepts`); Express does not maintain a closed enum to audit for missing members. |
| API Surface Consistency | `FULL` | `lib/response.js` | `res.send`/`res.json`/`res.jsonp`/`res.set` share Content-Type/charset handling that drifts between surfaces; the v5 changelog (`History.md:15`) confirms this is a live consistency concern. |
| Spec-Structured Parsing Fidelity | `FULL` | `lib/utils.js`, `lib/request.js` | `acceptParams` (`utils.js:89-120`) hand-parses `;`-delimited media-type params, and `req.protocol`/`host` hand-split comma lists — ad hoc parsing of grammar-defined strings. High yield. |
| Composition and Mount-Context Awareness | `SKIP` | `app.use`, `app.path`, `router` | The interesting mount logic (baseUrl propagation, prefix stripping) lives in `router@2.2.0`, which is not in `lib/` and not present in node_modules; out of auditable scope this run. |

3 patterns marked `FULL` (Cross-Implementation Consistency, API Surface Consistency,
Spec-Structured Parsing Fidelity). The other 4 are `SKIP` with codebase-specific rationale.

## Pattern Deep Dive — Cross-Implementation Consistency

Two surfaces in Express derive a value the same protocol concept demands be consistent, yet
diverge on edge inputs.

- **`res.send` charset: string path vs Buffer path.** The string branch calls
  `setCharset(type, 'utf-8')` (`lib/response.js:140`), which parses and reformats the type
  via `contentType.parse`/`format` (`lib/utils.js:230-237`), *overwriting* any caller
  charset. The Buffer branch (`lib/response.js:150-153`) calls `this.type('bin')` only when
  no type is set and otherwise leaves the header verbatim. So `res.set('Content-Type',
  'text/plain; charset=iso-8859-1').send('x')` → `…charset=utf-8`, but the same with
  `Buffer.from('x')` → `…charset=iso-8859-1`. The tests pin both (`test/res.send.js:112-121`
  vs `test/res.send.js:125-134`), confirming the divergence is real and load-bearing.
- **`X-Forwarded-Proto` parsing vs `X-Forwarded-Host` parsing.** `req.protocol`
  (`lib/request.js:309-314`) *always* comma-splits the value (`indexOf(',')` then
  `substring`), even when untrusted logic has already gated it; `req.host`
  (`lib/request.js:424-427`) comma-splits *only inside the trusted branch* and uses the
  deprecated `.trimRight()` rather than `.trim()`. Two getters reading two `X-Forwarded-*`
  headers with the "same shape" use *different* split/trim discipline — a classic
  cross-implementation drift. A `", https"` value empties the protocol but the analogous host
  handling would fall back to `Host`. This deep dive traces `protocol` ↔ `host` ↔ `hostname`
  (`lib/request.js:297-315`, `:418-431`, `:444-458`) — three distinct functions.

## Pattern Deep Dive — API Surface Consistency

The Content-Type / charset story is spread across four response methods that must agree.

- `res.set` (`lib/response.js:664-686`) normalizes *every* Content-Type via
  `mime.contentType(value)` (`lib/response.js:676`), appending `charset=utf-8` for text types
  and throwing on arrays (`lib/response.js:673-675`).
- `res.type` (`lib/response.js:503-510`) sets Content-Type via `mime.contentType(type)` when
  the type lacks a `/`, defaulting to `application/octet-stream` — then delegates to
  `res.set`, so it also picks up charset injection.
- `res.json` (`lib/response.js:232-246`) sets `application/json` only when unset
  (`lib/response.js:241-242`) then calls `res.send`; the string branch of `send` then runs
  `setCharset(type, 'utf-8')` again (`lib/response.js:140`).
- `res.jsonp` (`lib/response.js:260-304`) sets `text/javascript` (`lib/response.js:283`) via
  `res.set`, and `res.send` re-applies `setCharset`.
The drift: `res.set` charset-injects via `mime.contentType`, while `res.send` charset-injects
via `setCharset` (`lib/utils.js:225-238`) — two different code paths reaching the "type has a
charset" state. `History.md:15` records a v5 fix to "avoid duplicate Content-Type header
processing in `res.send()` when sending string responses without an explicit Content-Type",
which is exactly the seam between `res.send`'s `this.type('html')` branch
(`lib/response.js:142`) and the explicit-type branch (`lib/response.js:139-140`). This traces
`res.set` → `mime.contentType`, `res.send` → `setCharset`, and `res.json`/`res.jsonp` →
`res.send` — four distinct identifiers across two files.

## Pattern Deep Dive — Spec-Structured Parsing Fidelity

Express hand-parses several grammar-defined strings instead of delegating to a parser.

- **`acceptParams` (`lib/utils.js:89-120`)** parses a media-type-with-params string
  (`type/subtype;q=…;key=val`). It scans for `=` (`lib/utils.js:96`), finds the bounding `;`
  (`lib/utils.js:99-100`), and has a recovery branch when `splitIndex > endIndex`
  (`lib/utils.js:102-104`) that rewinds via `lastIndexOf(';', splitIndex-1)`. Edge inputs:
  a parameter with no value (`;foo;`) breaks out at `lib/utils.js:97`; a quoted value
  containing `;` (`;name="a;b"`) is split at the inner `;` because there is no quoted-string
  awareness — RFC 7231 §3.1.1.1 allows quoted parameter values. `q` is parsed with
  `parseFloat` (`lib/utils.js:111`) with no clamp to `[0,1]`.
- **`req.protocol`/`req.host` comma-splitting (`lib/request.js:310-314`, `:424-427`)** parse
  comma-separated `X-Forwarded-*` lists with `indexOf(',')`+`substring` rather than a list
  parser, so empty list elements and surrounding whitespace are handled ad hoc (and
  inconsistently between the two, per the Cross-Implementation deep dive).
- **`res.cookie` value prefixing (`lib/response.js:751-757`)** ad hoc-prefixes `'j:'` for
  objects and `'s:'` for signed values; the JSON `'j:'` prefix is part of the
  cookie-parser round-trip contract and must stay in lockstep with the parser side.
This deep dive traces `acceptParams` (`lib/utils.js:89-120`), `req.protocol`
(`lib/request.js:297-315`), and `req.host` (`lib/request.js:418-431`) — three distinct
identifiers / locations parsing structured grammars by hand.

## Candidate Bugs for Phase 2

1. **`req.protocol` returns `''` (and `req.secure` false) for a trusted
   `X-Forwarded-Proto` whose first comma-separated element is empty.**
   - Stage: open exploration
   - File:line: `lib/request.js:309-314`, `lib/request.js:326-328`
   - Phase 3 should: verify whether the empty-first-element case (`", https"`, `","`) is
     guarded; add a test feeding those header values with trust proxy enabled and asserting
     `req.protocol`/`req.secure`.

2. **`res.cookie` with `maxAge < 1000` serializes `Max-Age=0`, expiring the cookie
   immediately despite a future `Expires`.**
   - Stage: quality risks
   - File:line: `lib/response.js:759-766`
   - Phase 3 should: confirm `Math.floor(maxAge/1000)` is intended; test
     `res.cookie('x','1',{maxAge:500})` and assert `Set-Cookie` lacks `Max-Age=0`, or that
     a documented floor/minimum exists.

3. **`res.redirect(status, url)` with a status `statuses.message` doesn't know emits a body
   containing the literal `"undefined"`.**
   - Stage: open exploration
   - File:line: `lib/response.js:812-864`, `lib/response.js:841`, `lib/response.js:846-847`
   - Phase 3 should: check for a fallback when `statuses.message[status]` is undefined; add a
     test asserting the redirect body for an unassigned 3xx code.

4. **Charset asymmetry: `res.send` overwrites a caller-set charset to utf-8 for string
   bodies but preserves it for Buffer bodies — the same route advertises different charsets
   depending on body type.** (Surfaced by the Cross-Implementation and API-Surface deep
   dives; this is the parity-asymmetry promoted to REQ-006 below.)
   - Stage: pattern deep dive + API Surface Consistency
   - File:line: `lib/response.js:137-143`, `lib/response.js:150-153`, `lib/utils.js:225-238`
   - Phase 3 should: confirm whether this divergence is documented intent vs a bug; test a
     pre-set latin1 Content-Type sent as string vs Buffer and compare emitted headers.

5. **JSONP callback whitelist (`/[^\[\]\w$.]/g`) admits member-access chains reflected into a
   `text/javascript` body.**
   - Stage: pattern deep dive + Spec-Structured Parsing Fidelity
   - File:line: `lib/response.js:286`, `lib/response.js:300`, `lib/response.js:283`
   - Phase 3 should: evaluate whether a stricter bare-identifier check is warranted; test
     callbacks `a.constructor` and `x['y']` to see what survives into the body.

6. **`acceptParams` has no quoted-parameter-value awareness, so `q`/params split on a `;`
   inside a quoted value, mis-parsing RFC-7231-legal media types.**
   - Stage: quality risks + Spec-Structured Parsing Fidelity
   - File:line: `lib/utils.js:89-120`
   - Phase 3 should: feed `text/html;x="a;b";q=0.5` and confirm `params.x`/`quality` are
     parsed per RFC 7231 §3.1.1.1; also confirm `q` is clamped to `[0,1]`.

7. **`req.host`/`req.hostname`/`req.subdomains` return `undefined`/`[]` for a trusted
   `X-Forwarded-Host` with a leading comma.**
   - Stage: open exploration
   - File:line: `lib/request.js:418-431`, `lib/request.js:444-458`, `lib/request.js:383-394`
   - Phase 3 should: test trusted XFH `",real.example.com"` and assert hostname resolution.

## Derived Requirements

> Tier 3 (code-is-the-spec) — 0 Tier-1/2 citable sources (reference_docs/cite/ empty).
> Gathered docs in reference_docs/ are Tier-4 supporting context.

### REQ-001: `req.protocol` must yield a non-empty, correct scheme for every trusted `X-Forwarded-Proto` value
- Tier: 3
- References: lib/request.js:297-315, lib/request.js:326-328
- Implementation: `req.protocol` getter comma-splits and trims the forwarded header; `req.secure` derives from it.
- Conditions of satisfaction: for header values `""`, `","`, `", https"`, `"https,"`, `"http, https"` with trust proxy enabled, `req.protocol ∈ {http, https}` and `req.secure` reflects the real scheme.
- Specificity: specific

### REQ-002: `res.cookie` must not emit a `Max-Age` that contradicts a future `Expires`
- Tier: 3
- References: lib/response.js:742-775, lib/response.js:759-766
- Implementation: `maxAge` (ms) is converted to `expires` and floored to seconds for `Max-Age`.
- Conditions of satisfaction: a sub-second `maxAge` must not serialize `Max-Age=0` alongside a future `Expires`; `res.clearCookie` (response.js:709-716) remains the only path that sets an immediate expiry.
- Specificity: specific

### REQ-003: `res.redirect` must produce a well-formed body for any accepted status code
- Tier: 3
- References: lib/response.js:812-864
- Implementation: the body is built from `statuses.message[status]` via `res.format`.
- Conditions of satisfaction: for a status with no `statuses.message` entry, the body and HTML `<title>` must not contain the literal string `undefined`.
- Specificity: specific

### REQ-004: `res.jsonp` callback names must be restricted to a safe, well-defined grammar
- Tier: 3
- References: lib/response.js:260-304, lib/response.js:286
- Implementation: the callback is filtered by `/[^\[\]\w$.]/g` then reflected into a `text/javascript` body guarded by `typeof … === 'function'`.
- Conditions of satisfaction: only callback strings matching the intended grammar reach the body; member-access chains either are rejected or are proven safe by the guard. `X-Content-Type-Options: nosniff` is always set on jsonp responses (response.js:271,282).
- Specificity: specific

### REQ-005: `acceptParams` must parse media-type parameters per RFC 7231 §3.1.1.1
- Tier: 3
- References: lib/utils.js:89-120, lib/utils.js:61-77
- Implementation: hand-rolled scan over `;`/`=` boundaries extracting `q` and `params`.
- Conditions of satisfaction: quoted parameter values containing `;` are not split mid-value; `q` is parsed and clamped to `[0,1]`; the `splitIndex > endIndex` recovery branch (utils.js:102-104) does not drop valid params.
- Specificity: specific

### REQ-006: Charset handling must be consistent across `res.send` body types and `res.set`/`res.type`/`res.json`/`res.jsonp` surfaces
- References: lib/response.js:137-143, lib/response.js:150-153, lib/response.js:664-686, lib/utils.js:225-238
- Pattern: parity
- Tier: 3
- Implementation: string `send` rewrites charset to utf-8 via `setCharset`; Buffer `send` preserves it; `res.set`/`res.type` inject charset via `mime.contentType`.
- Conditions of satisfaction (Cartesian per-site, see UC-06.a/b/c):
  - UC-06.a: a pre-set non-utf-8 charset sent as a **string** body must behave per the documented v5 rule (force utf-8) consistently.
  - UC-06.b: the same charset sent as a **Buffer** body must follow the same documented rule, or the divergence must be explicitly specified.
  - UC-06.c: `res.set('Content-Type', …)` charset injection (via `mime.contentType`) must agree with `res.send`'s `setCharset` injection for the same input.
- Specificity: specific

### REQ-007: `req.host`/`req.hostname`/`req.subdomains` must resolve consistently for all trusted `X-Forwarded-Host` shapes
- References: lib/request.js:418-431, lib/request.js:444-458, lib/request.js:383-394
- Pattern: parity
- Tier: 3
- Implementation: `host` selects/trims XFH then `Host`; `hostname` strips the port; `subdomains` splits on `.`.
- Conditions of satisfaction (per-site, see UC-07.a/b/c): for trusted XFH values `"a.com"`, `",a.com"`, `"a.com,"`, `"a.com:8080"`, `"[::1]:8080"`, each of `host`/`hostname`/`subdomains` returns the value implied by the leading authority, never `undefined` for a syntactically present host.
- Specificity: specific

### Architectural-guidance requirements
### REQ-008: Settings compilation must fail fast on invalid configuration
- Tier: 3
- References: lib/application.js:363-380, lib/utils.js:130-214
- Implementation: `compileETag`/`compileQueryParser`/`compileTrust` throw `TypeError` on unknown values at `app.set` time.
- Specificity: architectural-guidance (cross-cutting config invariant, not a single testable path)

## Cartesian UC rule confirmation

1. **Gate 1 (path-suffix match) run for every REQ with ≥2 References.** REQ-001 (request.js
   ×2 — same file, getter pair `protocol`/`secure`), REQ-006 (response.js ×3 + utils.js),
   REQ-007 (request.js ×3 — getters `host`/`hostname`/`subdomains`). Others have a single
   primary site.
2. **Gate 2 (function-level similarity) run where Gate 1 passed.** REQ-007's three references
   are sibling getters of comparable size inside function bodies → both gates pass. REQ-006's
   references span `res.send` string branch, `res.send` Buffer branch, `res.set`, and
   `setCharset` — parallel charset-handling sites → both gates pass.
3. **Per-site UCs emitted where both gates passed:** UC-06.a/b/c (REQ-006), UC-07.a/b/c
   (REQ-007). See Derived Use Cases.
4. **Gate-1-only clusters marked heterogeneous:** REQ-001's two references are a getter +
   its boolean derivative (not parallel implementations) → single umbrella UC-01,
   `<!-- cluster: heterogeneous -->`.
5. **Neither-gate clusters:** none.
6. **`Pattern:` added** to REQ-006 (`parity`) and REQ-007 (`parity`) — the two multi-site
   parity REQs.
7. **Asymmetry-Promotion applied.** The "string `res.send` forces utf-8 but Buffer `res.send`
   preserves charset" asymmetry (Open Exploration #1, both deep dives) was escalated to a
   multi-site `Pattern: parity` REQ (REQ-006), not demoted to prose. The
   `X-Forwarded-Proto` (always-split) vs `X-Forwarded-Host` (conditionally-split) asymmetry
   was escalated to REQ-007 (`Pattern: parity`) spanning the three host getters.

## Derived Use Cases

### UC-01: Reverse-proxy operator relies on `req.protocol`/`req.secure`
- Actor: backend developer behind a TLS-terminating proxy
- Trigger: a request arrives with `X-Forwarded-Proto`
- Expected outcome: `req.secure` correctly reflects HTTPS so HTTPS-only middleware behaves.
<!-- cluster: heterogeneous -->

### UC-02: Developer sets a short-lived cookie
- Actor: app developer setting a flash/CSRF cookie with `maxAge`
- Trigger: `res.cookie(name, val, {maxAge})`
- Expected outcome: the cookie lives for the requested duration, not expiring instantly.

### UC-03: API returns a redirect with a custom status
- Actor: API author issuing `res.redirect(status, url)`
- Trigger: a 3xx status outside the common set
- Expected outcome: a clean, human-readable redirect body — never the literal `undefined`.

### UC-04: Client consumes a JSONP endpoint
- Actor: legacy browser client passing `?callback=`
- Trigger: `res.jsonp(obj)`
- Expected outcome: a safe `text/javascript` payload invoking only a validly-named callback.

### UC-05: Client negotiates content with quality params
- Actor: HTTP client sending `Accept` with `q=` and media-type params
- Trigger: `req.accepts` / `res.format`
- Expected outcome: parameters (including quoted values) parsed per RFC 7231.

### UC-06.a: String body with a pre-set charset
- Actor: developer calling `res.set('Content-Type', 'text/plain; charset=iso-8859-1').send('é')`
- Expected outcome: documented, consistent charset behavior for string bodies.

### UC-06.b: Buffer body with a pre-set charset
- Actor: developer sending `Buffer.from('é','latin1')` with a latin1 Content-Type
- Expected outcome: charset behavior consistent with the string-body rule, or explicitly specified divergence.

### UC-06.c: Charset set via `res.set`/`res.type` then `send`
- Actor: developer setting the type via `res.type('html')` then `res.send`
- Expected outcome: `mime.contentType` injection and `setCharset` injection agree.

### UC-07.a: Trusted `X-Forwarded-Host` with a normal authority
- Actor: app behind a trusted proxy
- Expected outcome: `req.hostname`/`req.subdomains` resolve correctly.

### UC-07.b: Trusted `X-Forwarded-Host` with a leading/trailing comma
- Actor: app behind a proxy that concatenates forwarded hosts
- Expected outcome: hostname resolution never silently returns `undefined` for a present host.

### UC-07.c: `X-Forwarded-Host` carrying a port or IPv6 literal
- Actor: app behind a proxy forwarding `host:port` or `[::1]:port`
- Expected outcome: the port is stripped to a clean hostname.

## Notes for Artifact Generation

- **Import pattern is `require('..')`** — every functional/regression test must use it.
- **Mocha + supertest** is the test idiom; mirror `test/res.send.js` structure
  (`request(app).get('/').expect(...)`).
- Routing/mounting lives in `router@2.2.0` and node_modules is **absent** — do not write
  tests that depend on router internals; exercise behavior through `app.use`/`app[METHOD]`.
- 0 Tier-1/2 citations → keep all REQs Tier 3; do not fabricate citations
  (`quality_gate.py` re-verifies excerpts).
- `History.md` is the authoritative v5 behavioral record — cite changelog lines for
  intent-vs-bug triage in Phase 4.

## Gate Self-Check

This section proves the Phase 1 completion gate
(`bin/run_state_lib.validate_phase_artifacts`, checks 1–17) was executed against the
on-disk EXPLORATION.md.

1. **File ≥120 lines of substantive content** — PASS (file is several hundred lines of
   findings with citations).
2. **PROGRESS.md exists, Phase 1 marked `[x]`** — PASS (`- [x] Phase 1 - Explore` and
   `- [x] Phase 1: Exploration`).
3. **Derived Requirements has ≥1 `### REQ-NNN:` with file paths/function names** — PASS
   (REQ-001…REQ-008, each citing lib/*.js:line ranges).
4. **`## Open Exploration Findings` ≥8 numbered, each file:line, ≥4 distinct modules** —
   PASS (12 entries; cite request.js, response.js, utils.js, view.js, application.js).
5. **Open-exploration depth: ≥3 findings trace ≥2 locations** — PASS (#2,#3,#4,#6,#10,#12
   each cite ≥2 file:line ranges).
6. **`## Quality Risks` ≥5 numbered, each file:line + edge case + why-wrong** — PASS
   (7 ranked scenarios, each with citation, edge case, wrong behavior, and a check).
7. **`## Pattern Applicability Matrix` evaluates all patterns FULL/SKIP** — PASS (7 rows,
   each FULL or SKIP with rationale; ≥6 rows for check 17).
8. **3–4 patterns marked FULL** — PASS (3 FULL: Cross-Implementation Consistency, API
   Surface Consistency, Spec-Structured Parsing Fidelity).
9. **3–4 `## Pattern Deep Dive — ` sections matching FULL count** — PASS (3 deep dives).
10. **≥2 deep dives trace ≥2 identifiers/locations** — PASS (all 3 cite ≥2 backticked
    identifiers and ≥2 file:line ranges).
11. **`## Candidate Bugs for Phase 2` ≥4 entries with file:line + Stage + what-to-check** —
    PASS (7 entries, each with a `Stage:` line and file:line).
12. **Ensemble balance: ≥2 from open exploration/quality risks AND ≥1 from a pattern deep
    dive** — PASS (candidates 1,2,3,7 from exploration/risks; 4,5 from deep dives; 6 combo).
13. **Candidate-bug source mix (`Stage:` buckets)** — PASS (exploration/risks ≥2,
    deep dive ≥1; combo Stage on #4/#5/#6).
14. **Derived Requirements ≥1 REQ-NNN** — PASS (8 REQs).
15. **Open-exploration module spread ≥4 distinct modules** — PASS (≥5 lib files cited).
16. **Quality Risks ≥5 entries with file:line** — PASS (7 with citations).
17. **Pattern matrix ≥6 evaluated rows** — PASS (7 rows).
