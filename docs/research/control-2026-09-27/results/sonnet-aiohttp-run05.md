# Code review: aiohttp (pinned commit e11d2836203a21bec59095498e578d37801027e7)

Scope reviewed: `aiohttp/` package (excluding `tests/`), checkout at `/tmp/control/aiohttp`.

Method: manual reading plus differential comparison against the real, unmodified
aiohttp 3.14.3 package installed in the provided venv
(`/tmp/aiohttp-venv/lib/python3.10/site-packages/aiohttp/`), used only as a local
baseline to spot where this dev snapshot's refactored logic diverges from
previously-correct behavior (not as a source of "every diff is a bug" — the
checkout is an unreleased 4.0.0a2 snapshot with many legitimate new features, and
most diffs are legitimate). Existing test suites were run against several of the
areas discussed below. No web access, issue tracker, or other host directories
were used.

---

## 1. `ClientResponse.json()` no longer returns `None` for an empty/whitespace body

**File:** `aiohttp/client_reqrep.py`, `json()` (around lines 747–773)

```python
async def json(
    self, *, encoding=None, loads=DEFAULT_JSON_DECODER, content_type="application/json",
) -> Any:
    """Read and decodes JSON response."""
    await self.read()
    if content_type:
        if not is_expected_content_type(self.content_type, content_type):
            raise ContentTypeError(...)
    if encoding is None:
        encoding = self.get_encoding()
    return loads(self._body.decode(encoding))  # type: ignore[union-attr]
```

**What goes wrong:** the empty/whitespace-body short-circuit that used to exist
before decoding has been dropped. If a server returns a body that is empty or
contains only whitespace (e.g. a `204`, or any endpoint that legitimately returns
`""` with `Content-Type: application/json`), `loads(self._body.decode(encoding))`
is called on an empty string and raises `json.decoder.JSONDecodeError: Expecting
value: line 1 column 1 (char 0)` instead of returning `None`.

Verified directly:
```
>>> json.loads(b"".decode("utf-8"))
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Why it's wrong:** `docs/client_reference.rst` (unchanged by this checkout, lines
1727–1729) still documents:

> `:return:` BODY as JSON data parsed by *loads* parameter or **``None`` if BODY
> is empty or contains white-spaces only.**

The currently-released 3.14.3 implementation (`/tmp/aiohttp-venv/.../client_reqrep.py`,
`json()`) implements exactly that contract:

```python
stripped = self._body.strip()
if not stripped:
    return None
...
return loads(stripped.decode(encoding))
```

Nothing in `CHANGES.rst`/`CHANGES.d` in this checkout documents removing this
behavior — it reads as an accidental regression introduced during a refactor, not
an intentional 4.0 API change.

**Severity:** high — this breaks a long-standing, explicitly documented public API
contract with no deprecation, and will turn a previously-silent `None` into an
unhandled exception for any caller that follows the documented contract.

**Suggested fix:** restore the empty-body short-circuit before decoding:
```python
stripped = self._body.strip()
if not stripped:
    return None
return loads(stripped.decode(encoding))
```

---

## 2. `test_utils.py`'s test-server socket factory sets `SO_REUSEPORT` instead of `SO_REUSEADDR`

**File:** `aiohttp/test_utils.py`, lines 65, 78–81

```python
REUSE_ADDRESS = os.name == "posix" and sys.platform != "cygwin"
...
socket_factory: Callable[[str, int, socket.AddressFamily], socket.socket] = (
    lambda h, p, f: socket.create_server((h, p), family=f, reuse_port=REUSE_ADDRESS)
),
```

**What goes wrong:** the `REUSE_ADDRESS` flag — named for, and historically used
to set, `SO_REUSEADDR` (the old `get_port_socket()` helper did
`s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)` when `REUSE_ADDRESS` was
true) — is now passed into `socket.create_server`'s `reuse_port=` keyword, which
controls the unrelated `SO_REUSEPORT` option. `SO_REUSEPORT` lets **multiple
independent listening sockets bind to the same address/port simultaneously** for
kernel-level load balancing; it is not a substitute for `SO_REUSEADDR` (which lets
a single socket rebind a recently-closed port). `socket.create_server` already
sets `SO_REUSEADDR` appropriately on POSIX by default, so this line adds
`SO_REUSEPORT` as a new, unintended behavior rather than "translating" the old
option.

**Why it's wrong:** the variable name and the removed `get_port_socket()`
docstring/usage establish that `REUSE_ADDRESS` was always meant to gate
`SO_REUSEADDR`, a TIME_WAIT rebind workaround — not `SO_REUSEPORT`. With this
code, on POSIX, every `BaseTestServer` (used throughout aiohttp's own suite and by
`AioHTTPTestCase`/`pytest-aiohttp` users) listens with `SO_REUSEPORT` enabled. Two
test servers that end up bound to the same port (concurrent test runs, or a fixed
`port=` reused across tests) will silently coexist and have the kernel
load-balance connections between them instead of the second `bind()` failing with
"Address already in use" — producing flaky, hard-to-diagnose test failures where
requests intended for one server land on a different one.

**Severity:** medium (test-infrastructure correctness bug, not the production
request path, but it is shipped, user-facing test-utility code that other
projects' test suites depend on).

**Suggested fix:** don't feed `REUSE_ADDRESS` into `reuse_port=`. Either drop the
argument entirely (relying on `create_server`'s own default `SO_REUSEADDR`
behavior), or build the socket manually and set `SO_REUSEADDR` explicitly if
finer control is needed, as the old `get_port_socket()` did.

---

## 3. `_cached_build_client_middlewares` re-introduces the stateful-middleware retention problem that the code explicitly used to avoid

**Files:** `aiohttp/client_middlewares.py` line 58; call site `aiohttp/client.py`
around lines 715–722

```python
# client_middlewares.py
_cached_build_client_middlewares = lru_cache(maxsize=64)(build_client_middlewares)
```
```python
# client.py — module-level, not a closure, "so it has a stable identity
# for the _cached_build_client_middlewares cache key"
async def _connect_and_send_request(req: ClientRequest) -> ClientResponse: ...
...
effective_middlewares = self._middlewares if middlewares is None else tuple(middlewares)
if effective_middlewares:
    handler = _cached_build_client_middlewares(_connect_and_send_request, effective_middlewares)
```

**What goes wrong:** the released 3.14.3 `build_client_middlewares()` docstring
states the design intent explicitly:

> "This implementation avoids using partial/update_wrapper to minimize overhead
> **and doesn't cache to avoid holding references to stateful middleware**."

This checkout deletes that clause and wraps the same function in a
module-level, process-lifetime `lru_cache(maxsize=64)`. The cache key includes the
`middlewares` tuple itself — i.e. the actual user-supplied middleware callables
(e.g. `DigestAuthMiddleware` instances holding login/password, or any closure
capturing per-session state). Up to 64 distinct `(handler, middlewares)` cache
entries are now kept alive at module scope for the life of the process, sharing
built wrapper closures — and the objects they close over — across every
`ClientSession` in the process, well past any individual session's or request's
lifetime.

**Why it's wrong:** this is not a deliberate optimization documented anywhere in
`CHANGES.rst`; it silently contradicts the (now-removed) comment describing the
prior, deliberate design choice, and reintroduces the exact retention concern that
comment called out — most notably for auth-carrying middleware like
`DigestAuthMiddleware`, whose login/password/nonce state would now be pinned in a
global cache alongside up to 63 other middleware-tuple entries.

**Severity:** medium — this is a memory-retention / stale-credential-longevity
issue rather than a crash, and its practical impact scales with how many distinct
middleware tuples an application uses across the process lifetime, but it is a
real, silent regression against the codebase's own stated design rationale.

**Suggested fix:** either scope the built-handler cache per `ClientSession`
instance (built once when middlewares are set, not via a global `lru_cache`), or
drop the caching and rely on the already-present "single middleware" fast path,
as the original comment argued was sufficient.

---

## 4. `BodyPartReader._align_base64_chunk` can hand back a chunk with fewer than 4 base64 characters, which `base64.b64decode` will reject

**File:** `aiohttp/multipart.py`, `_align_base64_chunk` (~lines 408–434)

```python
def _align_base64_chunk(self, chunk: bytes, size: int) -> bytes:
    at_end = self._at_eof or (self._length is not None and self._read_bytes >= self._length)
    if not at_end and len(chunk) > size:
        self._b64_carry = chunk[size:]
        chunk = chunk[:size]

    remainder = len(chunk.translate(None, _NON_BASE64_BYTES)) % 4
    if not remainder or at_end:
        return chunk

    cut = len(chunk)
    left = remainder
    while left:
        cut -= 1
        if chunk[cut] in _BASE64_CHARS:
            left -= 1
    if not cut:
        # No whole quartet to hand back ... return chunk unchanged
        return chunk

    self._b64_carry = chunk[cut:] + self._b64_carry
    return chunk[:cut]
```

**What goes wrong:** when a non-final chunk contains fewer than 4 base64-alphabet
characters in total, the back-walk to find a quartet boundary reaches `cut == 0`,
and the function falls back to returning the chunk **unmodified**, with nothing
moved into `self._b64_carry`. Per `read_chunk`'s own comment ("every chunk is
decoded on its own, so a chunk should not end mid-quartet"), a caller decoding
each `read_chunk()` result independently (a supported public-API usage —
`read_chunk(size)` takes an explicit size) will pass this misaligned chunk to
`base64.b64decode`, which raises `binascii.Error` whenever the count of data
characters isn't a multiple of 4:
```
>>> base64.b64decode(b"A")   # binascii.Error: Invalid base64-encoded string...
>>> base64.b64decode(b"AA")  # binascii.Error: Incorrect padding
```

**Why it's wrong:** the surrounding code's whole purpose (the `_b64_carry`
mechanism) is to guarantee each independently-decoded chunk ends on a quartet
boundary; the `cut == 0` branch defeats that guarantee instead of buffering the
partial data forward.

**Severity:** low/medium — reachable only with an explicit small `read_chunk()`
size (well under the default 8192-byte `chunk_size`) or pathological
low-density-base64 input; unlikely to trigger via the normal `.read()`/iteration
path, but it is a real, public-API-reachable defect.

**Suggested fix:** when `cut == 0` and not `at_end`, carry the entire chunk
forward (`self._b64_carry = chunk`) and return `b""` instead of returning the
misaligned data — callers of `read_chunk()`/`read()` already tolerate empty
intermediate results.

---

## 5. `HTTPMethodNotAllowed` no longer upper-cases the stored method (low confidence / low severity)

**File:** `aiohttp/web_exceptions.py`, `HTTPMethodNotAllowed.__init__` (~lines
311–327)

```python
def __init__(self, method: str, allowed_methods: Iterable[str], *, ...) -> None:
    ...
    self._method = method
```

The released implementation does `self.method = method.upper()` (normalizing
case); this checkout stores the raw value in `self._method`, exposed unchanged via
the `method` property. In practice this has no observable effect in the request
path today, because both call sites in `web_urldispatcher.py` pass
`request.method`, which is already guaranteed upper-case. It would only matter if
a caller constructs `HTTPMethodNotAllowed("get", ...)` directly with a
non-uppercase string — `HTTPMethodNotAllowed` is public, exported API — in which
case `.method` would now preserve the original casing instead of normalizing it.

**Severity:** low.

**Suggested fix:** `self._method = method.upper()`.

---

## Areas reviewed with no confident defects found

- `client_middleware_digest_auth.py` — RFC 7616 digest logic, nonce-count
  handling, protection-space/domain scoping, header parsing regex — read in full,
  looks correct.
- `streams.py` (`StreamReader`, buffer/backpressure, `readuntil`/`read`/`readexactly`/
  `readchunk`) — read in full, consistent with documented semantics.
- `cookiejar.py` — domain matching (`_is_domain_match`), path defaulting,
  host-only cookie tracking, `filter_cookies` subdomain/path expansion — read in
  full, matches RFC 6265 semantics as documented in comments.
- `connector.py` — connection pooling (`_available_connections`, `_get`,
  `_release`, `_wait_for_available_connection`, `_release_waiter`) — read in full,
  race-handling comments match the code's actual behavior.
- `http_parser.py` — chunked transfer-encoding state machine, trailer parsing,
  Content-Length/Transfer-Encoding conflict rejection (request-smuggling
  prevention) — read in full.
- `web_fileresponse.py` — Range/If-Range/If-Match/If-None-Match handling — read
  in full, matches RFC 9110 §13 as cited in the comments.
- `web_middlewares.py` — `normalize_path_middleware` slash merge/append/remove
  ordering, including the `GHSA-v6wp-4m6f-gcjg` security fix — matches upstream.
- `client.py` — the redirect-handling loop (cross-origin auth/cookie stripping,
  301/302/303/307/308 method/body handling) — matches RFC 9110 §15.4.3 as cited.
- `helpers.py` — `is_ip_address`, `is_canonical_ipv4_address`.
- The full `web_*` server module (`web_app.py`, `web_protocol.py`,
  `web_request.py`, `web_response.py`, `web_routedef.py`, `web_runner.py`,
  `web_server.py`, `web_urldispatcher.py`, `web_ws.py`, `worker.py`,
  `web_log.py`), `payload.py`, `formdata.py`, `tracing.py`,
  `compression_utils.py` (including the new concatenated-gzip/deflate-member
  decompression path, fuzz-tested), `_cookie_helpers.py`, `http_websocket.py`,
  and the `_websocket/` package (reader/writer/helpers/models, including the new
  WebSocket backpressure/stalled-reader mechanism) — reviewed with test-suite runs
  and targeted repro scripts; no confirmed defects beyond item 5 above.
- `resolver.py`, `client_exceptions.py`, `tcp_helpers.py`, `hdrs.py`, `http.py`,
  `http_exceptions.py`, `abc.py`, `typedefs.py`, `client_ws.py`, `client_proto.py`
  (including its WebSocket-tail backpressure handling) — no confirmed defects.

## Files read

`aiohttp/client.py`, `aiohttp/client_reqrep.py`, `aiohttp/client_proto.py`,
`aiohttp/client_ws.py`, `aiohttp/client_exceptions.py`,
`aiohttp/client_middlewares.py`, `aiohttp/client_middleware_digest_auth.py`,
`aiohttp/connector.py`, `aiohttp/resolver.py`, `aiohttp/http_parser.py`,
`aiohttp/http_writer.py`, `aiohttp/_http_parser.pyx` (partial),
`aiohttp/abc.py`, `aiohttp/hdrs.py`, `aiohttp/http.py`,
`aiohttp/http_exceptions.py`, `aiohttp/tcp_helpers.py`, `aiohttp/typedefs.py`,
`aiohttp/multipart.py`, `aiohttp/test_utils.py`, `aiohttp/streams.py`,
`aiohttp/cookiejar.py`, `aiohttp/helpers.py`, `aiohttp/base_protocol.py`,
`aiohttp/payload.py` (targeted sections), `aiohttp/web_fileresponse.py`,
`aiohttp/web_middlewares.py`, `aiohttp/web_app.py`, `aiohttp/web_protocol.py`,
`aiohttp/web_request.py`, `aiohttp/web_response.py`, `aiohttp/web_routedef.py`,
`aiohttp/web_runner.py`, `aiohttp/web_server.py`, `aiohttp/web_urldispatcher.py`,
`aiohttp/web_ws.py`, `aiohttp/worker.py`, `aiohttp/web_exceptions.py`,
`aiohttp/web_log.py`, `aiohttp/formdata.py`, `aiohttp/tracing.py`,
`aiohttp/compression_utils.py`, `aiohttp/_cookie_helpers.py`,
`aiohttp/http_websocket.py`, `aiohttp/_websocket/reader_py.py`,
`aiohttp/_websocket/writer.py`, `aiohttp/_websocket/helpers.py`,
`aiohttp/_websocket/models.py`.

Also consulted for context/verification (not scored as review targets):
`docs/client_reference.rst`, `CHANGES.rst`, the reference aiohttp 3.14.3
installation at `/tmp/aiohttp-venv/lib/python3.10/site-packages/aiohttp/` (used
only as a differential baseline), and relevant files under `tests/` to run
existing suites against the areas discussed above.
