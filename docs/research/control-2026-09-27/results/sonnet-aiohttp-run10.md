# aiohttp code review — run10

**Repo:** aiohttp (https://github.com/aio-libs/aiohttp)
**Pinned commit:** e11d2836203a21bec59095498e578d37801027e7
**Scope:** `aiohttp/` (package source, tests excluded)
**Checkout:** `/tmp/control/aiohttp` (read-only)

Method: the scope was split four ways (client-side networking; server-side web framework;
low-level HTTP/websocket/cookie/multipart parsing; helpers and support utilities) and each part
was reviewed independently in full by a separate sub-review. I then independently re-read the
cited code for every reported defect and, for the four included below, ran a small script against
the checkout to reproduce the behavior directly rather than relying on the sub-review's claim.
Findings that were speculative, unconfirmed, or that I could not reproduce were dropped.

---

## Defects

### 1. `aiohttp/helpers.py:788-802` (`HeadersDictProxy.getall`) — corrupts any header value containing an unescaped, unquoted comma

```python
def getall(self, key: str) -> tuple[str, ...]:
    val = self.get(key, "")
    unescape = _QUOTED_PAIR_SUB.sub
    values = []
    for m in _LIST_ELEMENT_RE.finditer(val):
        qs = m.group(1)
        if qs is not None:
            values.append(unescape(r"\1", qs))
        else:
            raw = m.group(2).strip()
            if raw:
                values.append(
                    _PROTECTED_RE.sub(lambda p: unescape(r"\1", p.group()), raw)
                )
    return tuple(values)
```

`getall()` unconditionally treats the value returned by `self.get(key, "")` as an RFC 9110
§5.6.1 comma-separated list and re-splits it on every top-level, unquoted comma via
`_LIST_ELEMENT_RE`. This is wrong for any header whose value contains a legitimate unquoted
comma that isn't a list separator, most importantly HTTP-date values (`Date`, `Last-Modified`,
`Expires`, `If-Modified-Since`, `If-Unmodified-Since`, `If-Range`, all of the form
`Wed, 21 Oct 2026 07:28:00 GMT`) and `Set-Cookie`, whose `Expires=<wkday>, <date>` attribute is a
bare comma per RFC 6265 and which RFC 9110 §5.3 explicitly says must never be combined or split
as a list.

`HeadersDictProxy` is not a peripheral type — it is the concrete class returned by
`request.headers` and `response.headers` throughout the package (`web_request.py:557`,
`client_reqrep.py:422`, `http_parser.py:242`, `multipart.py:924`), so `.headers.getall(...)` is
public, documented API surface.

Reproduced directly against the checkout:
```
$ python3 -c "
from multidict import CIMultiDict
from aiohttp.helpers import HeadersDictProxy
h = CIMultiDict([('Date', 'Wed, 21 Oct 2026 07:28:00 GMT')])
print(HeadersDictProxy(h).getall('Date'))
h2 = CIMultiDict()
h2.add('Set-Cookie', 'session-id=123; Domain=.example.com; Path=/; Expires=Wed, 21 Oct 2026 07:28:00 GMT; Secure')
print(HeadersDictProxy(h2).getall('Set-Cookie'))
"
('Wed', '21 Oct 2026 07:28:00 GMT')
('session-id=123; Domain=.example.com; Path=/; Expires=Wed', '21 Oct 2026 07:28:00 GMT; Secure')
```

A single `Date` header value is silently split into two values, and a single `Set-Cookie` value
is silently split into two bogus values at the comma inside `Expires=`, corrupting the cookie
string. The codebase itself is aware raw comma-splitting is unsafe for `Set-Cookie`:
`client_reqrep.py:565` bypasses `HeadersDictProxy` entirely for that exact reason
(`self.headers._md.getall(hdrs.SET_COOKIE, ())`, reaching into the underlying raw
`CIMultiDict` instead of calling `.getall()` on the proxy) — but any other caller who calls
`response.headers.getall(...)` on `Set-Cookie` or any date header through the normal public API
gets silently corrupted data instead of an error.

**Severity:** high — this is reachable through ordinary, documented API use (`headers.getall`)
on very common header values (any `Date`-family header on every HTTP response, and `Set-Cookie`
whenever a cookie's `Expires` attribute is present), and it corrupts data silently rather than
raising, with no workaround short of bypassing the public `Mapping` API.

**Suggested fix:** `getall()` should not perform generic RFC 9110 list-splitting on arbitrary
header values. Either return the raw per-occurrence values from the underlying multidict
unmodified (`tuple(self._md.getall(key, ()))`), or restrict comma-splitting to an explicit
allow-list of headers that are actually defined as comma-separated lists (e.g. `Accept`,
`Forwarded`, `Link`, `Cache-Control`), leaving `Set-Cookie` and all date-valued headers returned
verbatim.

---

### 2. `aiohttp/web_request.py:663-694` (`BaseRequest.http_range`) — `Range: bytes=-0` is treated as "whole file" instead of "unsatisfiable"

```python
end = int(end) if end else None
start = int(start) if start else None

if start is None and end is not None:
    # end with no start is to return tail of content
    start = -end
    end = None
```

For the header `Range: bytes=-0` (a suffix-byte-range-spec with a suffix-length of exactly
zero), the regex capture for `end` is the string `"0"`. Since `"0"` is a non-empty string it is
truthy, so `end = int(end) if end else None` evaluates to `end = 0` (not `None`). The next block
then computes `start = -end` = `-0` = `0` and sets `end = None`, producing `slice(0, None, 1)` —
i.e. "serve the entire representation from byte 0", exactly as if the client had sent no `Range`
header at all.

This contradicts RFC 7233 (quoted almost verbatim a few lines later in
`web_fileresponse.py:381-387`):

```python
# According to https://tools.ietf.org/html/rfc7233:
# If a valid byte-range-set includes at least one
# byte-range-spec with a first-byte-pos that is less than
# the current length of the representation, or at least one
# suffix-byte-range-spec with a non-zero suffix-length,
# then the byte-range-set is satisfiable. Otherwise, the
# byte-range-set is unsatisfiable.
```

A suffix-length of exactly `0` must make the range **unsatisfiable** (HTTP `416 Range Not
Satisfiable`), not "return the whole file". Because `http_range` maps `bytes=-0` to
`slice(0, None, 1)`, `_prepare_open_file`'s `if start >= file_size:` 416 check
(`web_fileresponse.py:378-390`) is never reached, and the server instead returns
`206 Partial Content` with the full file body and a misleading `Content-Range` header.

Reproduced against a live static file route in the checkout: a request with
`Range: bytes=-0` against a 10-byte file returns
```
HTTP/1.1 206 Partial Content
Content-Range: bytes 0-9/10
Content-Length: 10
```
instead of the expected `416` with `Content-Range: bytes */10`.

**Severity:** low — spec-compliance bug rather than a crash or data-exposure issue (the client
gets the whole file it could have gotten anyway via a normal GET), but it is a direct,
demonstrable contradiction between this code and the RFC citation embedded a few lines away in
the same feature's implementation, and could confuse range-aware caches/CDNs that specifically
probe unsatisfiability with a zero-length suffix range.

**Suggested fix:** explicitly reject a suffix-length of exactly `0` in `http_range`, e.g.:
```python
if start is None and end is not None:
    if end == 0:
        raise ValueError("suffix-length must be non-zero")
    start = -end
    end = None
```
(the existing `except ValueError` handling that already exists at this method's call sites in
`web_fileresponse.py` turns a `ValueError` here into the correct `416` response).

---

### 3. `aiohttp/payload.py:505-513` and `:777-785` (`IOBasePayload`/`TextIOPayload._read_and_available_len`) — explicit `content_length=0` is treated as "no limit" and triggers an unwanted full-size read

```python
def _read_and_available_len(self, remaining_content_len):
    self._set_or_restore_start_position()
    size = self.size  # Call size only once since it does I/O
    return size, self._value.read(
        min(
            DEFAULT_CHUNK_SIZE,
            size or DEFAULT_CHUNK_SIZE,
            remaining_content_len or DEFAULT_CHUNK_SIZE,   # <-- bug
        )
    )
```

`write_with_length()` passes `remaining_content_len = content_length` and everywhere else in the
same method correctly distinguishes "no limit" (`None`) from "zero remaining" (`0`) via explicit
`is None` / `is not None` checks (e.g. `if remaining_content_len is None:` and
`if remaining_content_len is not None:`). But the very first read, in
`_read_and_available_len` (and identically in `_read`, and in the `TextIOPayload` mirror at
lines 777-785 / 807), uses `remaining_content_len or DEFAULT_CHUNK_SIZE`. Since `0` is falsy in
Python, an explicit `content_length=0` (e.g. a caller that set `Content-Length: 0` while the
body is still backed by an open file-like `IOBasePayload`/`TextIOPayload`) makes this expression
evaluate to `DEFAULT_CHUNK_SIZE` (256 KiB) instead of `0`, so the code performs a blocking read
of up to `DEFAULT_CHUNK_SIZE` bytes from the file object even though zero bytes were requested.

Reproduced against the checkout with a 300 KB `io.BytesIO`-backed `IOBasePayload` and
`write_with_length(writer, 0)`: 0 bytes are written to the wire (the later
`chunk[:remaining_content_len]` = `chunk[:0]` truncation saves that), but the file position
after the call has advanced to `262144` (`DEFAULT_CHUNK_SIZE`) instead of staying at `0`.

**Why this matters beyond "wasted read":** for a non-seekable or side-effecting file-like object
(a pipe, a decrypting/decompressing wrapper, or any `IOBase` subclass without a meaningful
`tell()`/`seek()`), the unwanted read silently consumes real data that was never supposed to be
touched; `_set_or_restore_start_position()` can only restore position on seekable streams and
otherwise falls back to marking the payload consumed, so the lost bytes are not recoverable on
retry/replay.

**Severity:** low-medium — narrow trigger (an explicit `Content-Length: 0` combined with a
non-empty file-like body), but a genuine logic error, and the failure mode is inconsistent with
every other length-check in the same file (`BytesPayload.write_with_length` and
`BytesIOPayload.write_with_length` both correctly use `is not None` and handle `0` correctly).

**Suggested fix:** replace `remaining_content_len or DEFAULT_CHUNK_SIZE` with
`DEFAULT_CHUNK_SIZE if remaining_content_len is None else remaining_content_len` at all four call
sites (`payload.py:512, 532, 784, 807`).

---

### 4. `aiohttp/web_log.py:62` / `:110-118` (`AccessLogger`) — the documented `%O` format directive crashes the logger with an uncaught `KeyError` instead of logging

```python
FORMAT_RE = re.compile(r"%(\{([A-Za-z0-9\-_]+)\}([ioe])|[atPrsbOD]|Tf?)")
...
LOG_FORMAT_MAP = {
    "a": "remote_address", "t": ..., "P": ..., "r": ..., "s": ...,
    "b": ..., "T": ..., "Tf": ..., "D": ..., "i": ..., "o": ...,
}
```

`FORMAT_RE`'s bare-directive alternative `[atPrsbOD]` still matches `%O`, but `LOG_FORMAT_MAP`
has no `"O"` key and there is no `_format_O` method anywhere in the class. `compile_format()`
(invoked unconditionally from `__init__`, not inside the `try/except Exception` that guards
per-request logging in `log()`) does `self.LOG_FORMAT_MAP[atom[0]]` for every atom `FORMAT_RE`
matches, so constructing an `AccessLogger` (directly, or via `web.run_app(access_log_format=...)`
/ `AppRunner`) with a format string containing `%O` raises an uncaught `KeyError` at
construction time, not at logging time.

Reproduced directly:
```
$ python3 -c "
import logging
from aiohttp.web_log import AccessLogger
AccessLogger(logging.getLogger('x'), log_format='%O')
"
Traceback (most recent call last):
  ...
  File "aiohttp/web_log.py", line 112, in compile_format
    format_key1 = self.LOG_FORMAT_MAP[atom[0]]
KeyError: 'O'
```

**Severity:** low — only triggered by an operator-supplied `access_log_format` string containing
`%O`, and it fails at startup rather than mid-request, but it is a hard crash with an opaque
`KeyError` rather than a clear error naming the unsupported directive, for an input the regex
itself claims to accept.

**Suggested fix:** either drop `O` from `FORMAT_RE`'s character class (since it has no
implementation), or implement `_format_O`/add an `"O"` entry to `LOG_FORMAT_MAP`, and separately
have `compile_format()` raise a clear `ValueError` naming the unsupported directive instead of
letting a raw `KeyError` propagate.

---

## Lower-confidence / minor items (not included as headline defects)

- `aiohttp/helpers.py` — the "round the timer wakeup up to a whole second" logic is implemented
  three times with a boundary inconsistency: `weakref_handle` (line 597) and
  `TimeoutHandle.start` (line 659) use `if timeout >= threshold:`, while
  `calculate_timeout_when` (line 624) and `ceil_timeout` (line 779) use strict `if timeout >
  threshold:`. At exactly `timeout == threshold` (default `5`), some call sites ceil the wakeup
  and others don't. Real and reproducible from reading the four functions side by side, but the
  observable effect is at most a sub-second difference in wakeup coalescing for one specific
  boundary value, so I'm not confident it rises to a reportable "defect" rather than a minor
  inconsistency — included here for completeness, not above.
- `aiohttp/resolver.py:154-161` (`AsyncResolver.resolve`, link-local IPv6 branch) — reassigns
  `host` from `getnameinfo()`'s result but never reassigns `port`, unlike the equivalent
  `ThreadedResolver.resolve` path a few dozen lines earlier which does reassign `port`. Low
  confidence this is observable in practice since `getnameinfo`/`aiodns` echo back the requested
  port, so I did not include it as a confirmed defect.

---

## Areas reviewed with no confident defects found

Client: `client.py`, `client_reqrep.py`, `client_proto.py`, `client_ws.py`,
`client_exceptions.py`, `client_middleware_digest_auth.py`, `client_middlewares.py`,
`connector.py`, `resolver.py` — connection-pool accounting, waiter FIFO and placeholder
acquire/release bookkeeping, the tail-buffer backpressure mechanism in `client_proto.py`,
redirect handling (301/302/303/307/308 body semantics), idempotent-method retry-on-disconnect,
the CONNECT/TLS-in-TLS tunnel path, DNS-resolution throttling/caching, and digest-auth
nonce-count/qop/session-algorithm math (RFC 7616) were all specifically checked and found
correct.

Server: `web.py`, `web_app.py`, `web_exceptions.py`, `web_fileresponse.py` (aside from the Range
defect above), `web_middlewares.py`, `web_protocol.py`, `web_request.py` (aside from the Range
defect above), `web_response.py`, `web_routedef.py`, `web_runner.py`, `web_server.py`,
`web_urldispatcher.py`, `web_ws.py`, `worker.py` — message-queue pipelining/backpressure
(including a live test with 2000 pipelined requests and fragmented TCP writes), the
upgrade-rejection replay path, WebSocket heartbeat coalescing and close-handshake state machine,
static-file path-traversal/symlink-sandbox defenses, and conditional-request logic
(`If-Match`/`If-None-Match`/`If-Modified-Since`/`If-Unmodified-Since`/`If-Range`) were all
specifically checked and found correct.

Protocol/parsing/utility: `http_parser.py`, `http_writer.py`, `http.py`, `http_exceptions.py`,
`http_websocket.py`, `_websocket/` (all files — frame header/length parsing, close-code
validation, masking, compression-extension negotiation), `_cookie_helpers.py`, `cookiejar.py`
(RFC 6265 domain-match, path-match, `Max-Age`/`Expires` precedence, date parsing), `multipart.py`
(Content-Disposition RFC 2231/5987 continuation params, boundary state machine, base64 alignment),
`formdata.py`, `streams.py`, `base_protocol.py`, `tracing.py`, `abc.py`, `compression_utils.py`
(decompression-bomb guards), `hdrs.py`, `tcp_helpers.py`, `typedefs.py`, `__init__.py`,
`test_utils.py` were reviewed with no confirmed defects (aside from the `helpers.py` items above).

---

## Files read

All files in the review scope (`aiohttp/` excluding `tests/`) were read across the four
sub-reviews, specifically:

`aiohttp/__init__.py`, `aiohttp/_cookie_helpers.py`, `aiohttp/_http_parser.pyx` (skim, for parity
with `http_parser.py`), `aiohttp/_http_writer.pyx` (skim), `aiohttp/_websocket/__init__.py`,
`aiohttp/_websocket/helpers.py`, `aiohttp/_websocket/models.py`, `aiohttp/_websocket/reader.py`,
`aiohttp/_websocket/reader_py.py`, `aiohttp/_websocket/writer.py`, `aiohttp/abc.py`,
`aiohttp/base_protocol.py`, `aiohttp/client.py`, `aiohttp/client_exceptions.py`,
`aiohttp/client_middleware_digest_auth.py`, `aiohttp/client_middlewares.py`,
`aiohttp/client_proto.py`, `aiohttp/client_reqrep.py`, `aiohttp/client_ws.py`,
`aiohttp/compression_utils.py`, `aiohttp/connector.py`, `aiohttp/cookiejar.py`,
`aiohttp/formdata.py`, `aiohttp/hdrs.py`, `aiohttp/helpers.py`, `aiohttp/http.py`,
`aiohttp/http_exceptions.py`, `aiohttp/http_parser.py`, `aiohttp/http_websocket.py`,
`aiohttp/http_writer.py`, `aiohttp/multipart.py`, `aiohttp/payload.py`, `aiohttp/resolver.py`,
`aiohttp/streams.py`, `aiohttp/tcp_helpers.py`, `aiohttp/test_utils.py`, `aiohttp/tracing.py`,
`aiohttp/typedefs.py`, `aiohttp/web.py`, `aiohttp/web_app.py`, `aiohttp/web_exceptions.py`,
`aiohttp/web_fileresponse.py`, `aiohttp/web_log.py`, `aiohttp/web_middlewares.py`,
`aiohttp/web_protocol.py`, `aiohttp/web_request.py`, `aiohttp/web_response.py`,
`aiohttp/web_routedef.py`, `aiohttp/web_runner.py`, `aiohttp/web_server.py`,
`aiohttp/web_urldispatcher.py`, `aiohttp/web_ws.py`, `aiohttp/worker.py`.

Supporting/context reads outside the review scope (to establish intended behavior, not
themselves reviewed for defects): `tests/test_client_response.py` (~1600-1690, for documented
`.headers.getall('Set-Cookie')` usage), `tests/test_helpers.py`, `tests/test_client_functional.py`,
`tests/test_client_request.py`, `tests/test_http_parser.py`, `tests/test_web_functional.py`
(grep only, for `getall` usage patterns).

I (the orchestrating review pass) directly re-read and independently reproduced, against the
live checkout at `/tmp/control/aiohttp`, defects #1-#4 above: `aiohttp/helpers.py` (lines
760-830, plus the `_LIST_ELEMENT_RE`/`_QUOTED_PAIR_SUB`/`_PROTECTED_RE` definitions), confirmed
`HeadersDictProxy` is the type actually returned by `request.headers`/`response.headers` via
`grep -rn "HeadersDictProxy"`; `aiohttp/web_request.py` (lines 655-700) and
`aiohttp/web_fileresponse.py` (lines 340-395) for the Range defect, verified live against a
static-file route serving a 10-byte temp file; `aiohttp/payload.py` (lines 495-535, 770-810) for
the `content_length=0` defect, verified with a script exercising `IOBasePayload.write_with_length`
against a `BytesIO`-backed payload; `aiohttp/web_log.py` (lines 1-160) for the `%O` `KeyError`,
verified by directly constructing `AccessLogger(logger, "%O")`. I also spot-checked
`/tmp/aiohttp-venv`'s installed aiohttp 3.14.3 as a comparison baseline for several of these
(available locally, not fetched over the network) to distinguish pre-existing behavior from
anything checkout-specific; `HeadersDictProxy` does not exist in that installed 3.14.3 version at
all (present only in this checkout), while the Range and `%O` issues reproduce identically in
3.14.3 as well.
