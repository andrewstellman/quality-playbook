# aiohttp code review — run09

**Repo:** aiohttp (https://github.com/aio-libs/aiohttp)
**Pinned commit:** e11d2836203a21bec59095498e578d37801027e7
**Scope:** `aiohttp/` (package source, tests excluded)
**Checkout:** `/tmp/control/aiohttp` (read-only)

Method: the scope was split three ways (client-side networking; server-side web framework;
low-level protocol/streaming/utility code) and each part was reviewed independently in full.
I then independently spot-verified a sample of the reported defects directly against the
checkout (reading the cited lines, and in a few cases tracing call sites) before including
them here. Every defect below was either directly re-confirmed by me by reading the cited
code, or is included with the supporting quote/line numbers from the sub-review so it can be
checked in one step. Findings that were speculative or unconfirmed were dropped.

---

## Defects

### 1. `aiohttp/web_log.py` — documented `%{FOO}e` and `%O` access-log directives crash on use

**Lines:** docstring 29–42 (esp. line 42 `%{FOO}e  os.environ['FOO']`), `LOG_FORMAT_MAP` (47–58), `FORMAT_RE` (62), `__init__`/`compile_format` (69–123).

The class docstring documents:
```
%{FOO}e  os.environ['FOO']
```
and `FORMAT_RE = re.compile(r"%(\{([A-Za-z0-9\-_]+)\}([ioe])|[atPrsbOD]|Tf?)")` still matches
both `%{FOO}e` and the bare `%O` directive. But `LOG_FORMAT_MAP` only has keys
`a, t, P, r, s, b, T, Tf, D, i, o` — there is no `"e"` or `"O"` entry, and there is no
`_format_e` method anywhere in the class (only `_format_i`, `_format_o`, `_format_a`, etc.
exist). `compile_format` does `self.LOG_FORMAT_MAP[atom[0]]` / `self.LOG_FORMAT_MAP[atom[2]]`
unconditionally for every atom matched by `FORMAT_RE`.

**Triggering input:** construct `AccessLogger(logger, "%O")` or `AccessLogger(logger, "%{FOO}e")`
(e.g. via `web.run_app(access_log_format=...)` or gunicorn's `worker.py`, which builds
`access_log_class(access_log, access_log_format)` per connection in `web_protocol.py`).

**Why it's wrong:** raises an uncaught `KeyError` (`'O'` or `'e'`) inside `AccessLogger.__init__`,
which is not wrapped in a try/except, directly contradicting the class's own documented format
directive. Because `RequestHandler.__init__` in `web_protocol.py` constructs a fresh
`AccessLogger` per incoming connection, a single bad (but *documented as valid*) format string
configured once at startup makes every connection's handler construction raise — not a one-time
startup failure but a crash repeated on every connection.

I confirmed directly: `grep -n "_format_e\|def _format" aiohttp/web_log.py` shows no `_format_e`
method exists, and `LOG_FORMAT_MAP` (read in full) has no `"e"` or `"O"` key.

**Severity:** medium (self-inflicted via operator misconfiguration, not remotely triggerable, but
it is a documented-vs-actual-behavior contradiction with a large blast radius once triggered).

**Suggested fix:** either implement `_format_e` (reading `os.environ.get(key, "-")`) and add
`"e": "environ"` to `LOG_FORMAT_MAP`, and re-add `O`'s formatter (or remove it from `FORMAT_RE`
and the docstring if `%O` was intentionally dropped — `CHANGES.rst` says "Dropped `%O` in access
logger" but the regex character class `[atPrsbOD]` was never updated to drop the `O`). Also
consider validating the format string eagerly (e.g. at `web.run_app` startup) rather than lazily
per connection.

---

### 2. `aiohttp/multipart.py:389` — `Content-Length: 0` body part silently bypasses exact-length framing

```python
if self._length:
    fresh = await self._read_chunk_from_length(want)
else:
    fresh = await self._read_chunk_from_stream(want)
```

`self._length` is set from the part's `Content-Length` header and can legitimately be `0` (an
empty body part with an explicit `Content-Length: 0`). The truthy check `if self._length:`
treats `0` the same as `None` (no declared length), so a part with `Content-Length: 0` is routed
to the boundary-scanning stream reader (`_read_chunk_from_stream`) instead of the exact-length
reader. Every other place in the same class correctly guards with `is not None` (e.g. the
mismatch check a few lines below at ~402–405, and the `_read_bytes == self._length` EOF check).
This means the length-based Content-Length-mismatch validation that `_read_chunk_from_length`
exists to perform is silently skipped for the `Content-Length: 0` case.

**Severity:** medium.

**Fix:** `if self._length is not None:`

---

### 3. `aiohttp/_websocket/reader_py.py:552` — off-by-one rejects a WebSocket message exactly at `max_msg_size`

```python
if self._payload_bytes_to_read >= self._max_msg_size - partial_len:
    raise WebSocketError(
        WSCloseCode.MESSAGE_TOO_BIG,
        f"Message size {int(self._payload_bytes_to_read) + partial_len} "
        f"exceeds limit {self._max_msg_size}",
    )
```

For a message whose total size is exactly `max_msg_size` (`payload_bytes_to_read + partial_len
== max_msg_size`), `>=` is true and the frame is rejected, even though the message does not
*exceed* the limit — contradicting the error text ("exceeds limit"). I confirmed the sibling
check on the decompressed payload a few hundred lines earlier (line ~326) uses strict `>`,
consistent with "exceeds" semantics; this one does not.

**Severity:** low/medium (off-by-one, not a crash or security issue, but a real behavioral bug —
legitimate maximum-size messages are rejected).

**Fix:** change `>=` to `>`.

---

### 4. `aiohttp/http_writer.py` — `write_eof()` does not enforce the remaining Content-Length budget

`write()` (around lines 194–202) truncates any chunk to the remaining declared
`Content-Length` (`self.length`):
```python
if self.length is not None:
    chunk_len = len(chunk)
    if self.length >= chunk_len:
        self.length = self.length - chunk_len
    else:
        chunk = chunk[: self.length]
        ...
```
`write_eof()` (lines ~276–352) has no equivalent logic anywhere — I read it in full and
confirmed `self.length` is never referenced inside it. For the non-chunked, non-compressed final
branch it just does `self._write(chunk)` with whatever `chunk` it was given.

**Triggering situation:** a response/request declares `Content-Length: N` and the final
`write_eof(chunk)` call is passed more than the remaining `N` bytes (e.g. a caller that computes
its own final chunk incorrectly, or a payload whose actual size doesn't match the declared
`Content-Length`).

**Why it's wrong:** more bytes than the declared `Content-Length` get written to the wire.
On a keep-alive connection this desyncs framing for the next request/response, since the peer
will read exactly `Content-Length` bytes as this message's body and interpret the surplus bytes
as the start of the next message.

**Severity:** medium.

**Fix:** apply the same `self.length` truncation to `chunk` in `write_eof()` before it is
written, mirroring `write()`.

---

### 5. `aiohttp/cookiejar.py:531–545` (`_is_domain_match`) — cookie domain matching is case-sensitive, contradicting RFC 6265 and the method's own docstring

```python
@staticmethod
def _is_domain_match(domain: str, hostname: str) -> bool:
    """Implements domain matching adhering to RFC 6265."""
    if hostname == domain:
        return True
    if not hostname.endswith(domain):
        return False
    ...
```

I confirmed there is no `.lower()`/case-folding of `domain` anywhere in `cookiejar.py` or
`_cookie_helpers.py`. `hostname` (from the request/response URL) is normalized to lowercase by
yarl, but `domain` comes straight from the raw `Set-Cookie: ...; Domain=...` attribute value and
is never case-folded.

**Triggering input:** `Set-Cookie: sess=x; Domain=EXAMPLE.COM` received from
`http://example.com/`. `_is_domain_match('EXAMPLE.COM', 'example.com')` returns `False`
(`'example.com'.endswith('EXAMPLE.COM')` is `False`), so the cookie is dropped at line ~372–374
(`if domain and hostname and not self._is_domain_match(domain, hostname): continue`) with no
warning.

**Why it's wrong:** RFC 6265 §5.1.3 / §4.1.2.3 require ASCII case-insensitive domain matching;
the docstring on `_is_domain_match` itself claims RFC 6265 compliance. Servers that send a
mixed/upper-case `Domain` attribute (legal per RFC 6265, common from some frameworks/CDNs) will
have their cookies silently dropped by aiohttp's client.

**Severity:** medium (functional/interop bug — breaks session persistence for affected servers;
not a security/leak issue since it fails closed).

**Fix:** lowercase `domain` before comparing (either once when the cookie is parsed in
`_update_cookies`, or inside `_is_domain_match` itself).

---

### 6. `aiohttp/streams.py:399` (`readuntil`) — multi-byte separators spanning two `feed_data()` chunks are never found

```python
ichar = self._buffer[0].find(separator, offset) + 1
```

The search for `separator` is scoped to a single buffer chunk (`self._buffer[0]`) rather than
across the whole buffered stream. If a multi-byte `separator` straddles a boundary between two
`feed_data()` calls (i.e. the first N-1 bytes of the separator end one chunk and the rest start
the next chunk), the first chunk is consumed by `_read_nowait_chunk` without matching, and once
consumed its trailing partial-separator bytes are gone from the buffer — the full separator can
then never be found in a later chunk, since the search never looks backward across the
consumed/current chunk boundary.

Internal callers of `readuntil` (`readline`) only ever use the 1-byte separator `b"\n"`, so this
is not reachable via aiohttp's own internal call sites, but `readuntil` is a public method on
`StreamReader` accepting an arbitrary `separator`, and its contract (matching `asyncio.StreamReader.readuntil`) is to find the separator wherever it occurs in the stream.

**Severity:** medium (real defect in a public API; no confirmed internal trigger today).

**Fix:** track match state across chunk boundaries (e.g., keep the last `len(separator)-1` bytes
available to be combined with the next chunk during search), similar to how
`asyncio.StreamReader.readuntil` handles this.

---

### 7. `aiohttp/streams.py:394` and `aiohttp/payload.py` (multiple sites) — explicit `0` treated as "no limit" due to `x or DEFAULT`

- `aiohttp/streams.py:394`: `max_size = max_size or self._high_water` inside `readuntil()`. An
  explicit `max_size=0` (reachable via `readline(max_line_length=0)`) silently falls back to
  `self._high_water` instead of enforcing a zero-byte cap.
- `aiohttp/payload.py:512, 532, 784, 807`: `IOBasePayload`/`TextIOPayload`'s `_read`/`write`
  helpers use `remaining_content_len or DEFAULT_CHUNK_SIZE`. Confirmed by reading the docstrings
  at those sites, which describe `remaining_content_len` as "Optional limit … If specified" —
  `0` is a valid, meaningful explicit value (e.g., zero bytes remaining to write), but `0 or
  DEFAULT_CHUNK_SIZE` evaluates to `DEFAULT_CHUNK_SIZE`, causing a full blocking disk read of up
  to `DEFAULT_CHUNK_SIZE` bytes instead of reading nothing. (Downstream code in the same call
  chain slices the result to `remaining_content_len`, so no extra bytes reach the wire, but the
  read itself is incorrect/wasteful and violates the documented "0 means read nothing" contract
  implied by an explicit limit.)

**Severity:** low for both (edge case, not currently known to be exploitable or to corrupt
output, but a real logic bug against the documented contract).

**Fix:** replace the `x or DEFAULT` pattern with explicit `None` checks, e.g.
`DEFAULT_CHUNK_SIZE if remaining_content_len is None else remaining_content_len`.

---

## Lower-confidence / minor items (reported by sub-review, not independently re-verified line-by-line by me, included for completeness)

- `aiohttp/streams.py`, `EmptyStreamReader` (~602–678): `begin_http_chunk_receiving()` /
  `end_http_chunk_receiving()` are not overridden as no-ops like the rest of the class's methods,
  and would raise `AttributeError` if called (the base implementation reads
  `self._http_chunk_splits`, never set in `EmptyStreamReader.__init__`). No confirmed reachable
  call path today; low severity, latent trap.
- `aiohttp/test_utils.py:610–613`, `make_mocked_request`'s upgrade-detection does an exact-string
  compare of the whole `Connection` header (`headers.get(CONNECTION, "").lower() == "upgrade"`)
  instead of tokenizing on commas per RFC 9110 §7.6.1, unlike aiohttp's real parsers. This is a
  test-utility (not production networking) file, so impact is limited to false negatives in tests
  built on `make_mocked_request` with a multi-token `Connection` header. Low/low-medium severity.
- `aiohttp/client_middlewares.py:58` — `_cached_build_client_middlewares = lru_cache(maxsize=64)(build_client_middlewares)`,
  used from `client.py`'s `_request` (confirmed both the cache definition and its call site).
  Since the cache key includes the `middlewares` tuple, it holds strong references to middleware
  instances (which can carry secrets, e.g. `DigestAuthMiddleware` storing a password) for as long
  as they remain among the 64 most-recently-used cache entries, potentially outliving the
  `ClientSession`/middleware that created them. This is a real resource-retention behavior, but I
  could not confirm from the checkout alone whether a "no caching, to avoid holding references to
  stateful middleware" design constraint was previously documented elsewhere in the repo (a
  sub-review claimed this based on comparison with an installed older package version, which I
  did not independently verify). Treating this as a low-severity, low-confidence observation
  rather than a confirmed regression against this repo's own documentation.

---

## Areas reviewed with no confident defects found

Client: `client.py`, `client_reqrep.py`, `client_proto.py`, `client_ws.py`,
`client_exceptions.py`, `client_middleware_digest_auth.py`, `connector.py`, `resolver.py`,
`base_protocol.py`, `tcp_helpers.py`, `tracing.py` — redirect header stripping, WebSocket
handshake `Sec-WebSocket-Accept` verification, TLS fingerprint pinning, proxy CONNECT vs.
plain-HTTP-proxy `Proxy-Authorization` placement, digest-auth RFC 7616 implementation, and the
client-protocol tail/buffer-pause logic for pre-upgrade buffering were all specifically checked
and found correct.

Server: `web.py`, `web_app.py`, `web_protocol.py`, `web_request.py`, `web_response.py`,
`web_server.py`, `web_urldispatcher.py`, `web_ws.py`, `web_runner.py`, `web_middlewares.py`,
`web_fileresponse.py`, `web_exceptions.py`, `web_routedef.py`, `worker.py` — connection
pipelining/pause-resume, keep-alive timer handling, conditional-GET/Range-request semantics
(RFC 9110 §13), WebSocket close-handshake state machine, static-file path-traversal/symlink
defenses, and `normalize_path_middleware`'s leading-slash handling were specifically checked and
found correct.

Protocol/utility: `http_parser.py`, `http.py`, `http_exceptions.py`, `_http_parser.pyx` (request
smuggling vectors: TE+CL, duplicate headers, bare-LF, chunk extensions), `http_websocket.py` and
the rest of `_websocket/` (compression state, close-code validation, masking), `formdata.py`,
the rest of `payload.py` and `multipart.py` (RFC 2231/5987 parsing, base64 alignment, boundary
handling), `helpers.py`, `_http_writer.pyx`, `_cookie_helpers.py`, `compression_utils.py`
(decompression-bomb guards), the rest of `cookiejar.py` (path/expiry/host-only logic), `abc.py`,
`typedefs.py`, `hdrs.py`, `log.py`, and the rest of `test_utils.py` were reviewed with no
confirmed defects.

---

## Files read

All files in the review scope (`aiohttp/` excluding `tests/`) were read, specifically:

`aiohttp/__init__.py`, `aiohttp/_cookie_helpers.py`, `aiohttp/_http_parser.pyx` (skim),
`aiohttp/_http_writer.pyx` (skim), `aiohttp/_websocket/__init__.py`,
`aiohttp/_websocket/helpers.py`, `aiohttp/_websocket/models.py`, `aiohttp/_websocket/reader.py`,
`aiohttp/_websocket/reader_c.pxd` (skim), `aiohttp/_websocket/reader_py.py`,
`aiohttp/_websocket/writer.py`, `aiohttp/_websocket/mask.pyx` (skim), `aiohttp/abc.py`,
`aiohttp/base_protocol.py`, `aiohttp/client.py`, `aiohttp/client_exceptions.py`,
`aiohttp/client_middleware_digest_auth.py`, `aiohttp/client_middlewares.py`,
`aiohttp/client_proto.py`, `aiohttp/client_reqrep.py`, `aiohttp/client_ws.py`,
`aiohttp/compression_utils.py`, `aiohttp/connector.py`, `aiohttp/cookiejar.py`,
`aiohttp/formdata.py`, `aiohttp/hdrs.py`, `aiohttp/helpers.py`, `aiohttp/http.py`,
`aiohttp/http_exceptions.py`, `aiohttp/http_parser.py`, `aiohttp/http_websocket.py`,
`aiohttp/http_writer.py`, `aiohttp/log.py`, `aiohttp/multipart.py`, `aiohttp/payload.py`,
`aiohttp/resolver.py`, `aiohttp/streams.py`, `aiohttp/tcp_helpers.py`, `aiohttp/test_utils.py`,
`aiohttp/tracing.py`, `aiohttp/typedefs.py`, `aiohttp/web.py`, `aiohttp/web_app.py`,
`aiohttp/web_exceptions.py`, `aiohttp/web_fileresponse.py`, `aiohttp/web_log.py`,
`aiohttp/web_middlewares.py`, `aiohttp/web_protocol.py`, `aiohttp/web_request.py`,
`aiohttp/web_response.py`, `aiohttp/web_routedef.py`, `aiohttp/web_runner.py`,
`aiohttp/web_server.py`, `aiohttp/web_urldispatcher.py`, `aiohttp/web_ws.py`,
`aiohttp/worker.py`.

Supporting/context reads outside the review scope (to establish intended behavior, not
themselves reviewed for defects): `tests/test_client_proto.py`,
`tests/test_client_middleware_digest_auth.py`, `CHANGES.rst`.

I (the orchestrating review pass) additionally directly re-read and confirmed, against the live
checkout at `/tmp/control/aiohttp`, the exact cited lines for defects #1–#7 above:
`aiohttp/web_log.py` (lines 1–160), `aiohttp/multipart.py` (lines 375–415),
`aiohttp/_websocket/reader_py.py` (lines 530–560), `aiohttp/client_middlewares.py` (full file),
`aiohttp/client.py` (lines 220–245, 705–725), `aiohttp/cookiejar.py` (`_is_domain_match` and its
call site), `aiohttp/streams.py` (lines 370–410), `aiohttp/http_writer.py` (lines 185–355),
`aiohttp/payload.py` (`remaining_content_len` usages).
