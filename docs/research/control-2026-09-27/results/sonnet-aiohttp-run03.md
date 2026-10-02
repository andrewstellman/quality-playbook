# Code review: aiohttp (`aiohttp/` package), commit e11d2836203a21bec59095498e578d37801027e7

Scope reviewed: everything under `aiohttp/` excluding `tests/`, per the task. Pure-Python files were reviewed in full; the Cython extension files (`_http_parser.pyx`, `_http_writer.pyx`, `_websocket/mask.pyx`, `_websocket/reader_c.pxd`) were out of scope and skipped, as agreed in the review instructions given to the reviewers.

Every defect below was independently reproduced against the checkout (either by tracing the code path line-by-line or by running a small script against the actual parser/classes in `/tmp/aiohttp-venv`), not just inferred from reading.

---

## Defect 1 — Resource leak: request body not closed when a redirect downgrades the method to GET

**File:** `aiohttp/client.py`, lines 778–786 (inside `ClientSession._request`'s redirect-handling loop)

```python
if (resp.status == 303 and resp.method != hdrs.METH_HEAD) or (
    resp.status in (301, 302) and resp.method == hdrs.METH_POST
):
    method = hdrs.METH_GET
    data = None
    if headers.get(hdrs.CONTENT_LENGTH):
        headers.pop(hdrs.CONTENT_LENGTH)
else:
    ...
    data = req._body
```

**What goes wrong:** When a POST (or non-HEAD) request is redirected with 301/302/303 and the method is downgraded to GET per the classic "mimic IE" behavior, `data` is set to `None` and the loop `continue`s. The previous `req` object — which still holds the outgoing payload in `req._body` — is simply dropped without being closed. On the next loop iteration a brand-new `ClientRequest` is built; the old `req` becomes unreachable and its payload's `close()` is never called.

**Why it's wrong:** Every other exit from this same loop explicitly closes the body first:
- `TooManyRedirects` path: `if req._body is not None: await req._body.close()` (line ~772)
- invalid redirect URL, non-HTTP scheme, invalid origin paths: all call `await req._body.close()` before raising
- the final exit after the loop ends (non-redirect case): `if req._body is not None: await req._body.close()`

The method-downgrade branch is the only redirect-loop exit that skips this. For a payload backed by a real file handle (e.g. `session.post(url, data=open("file", "rb"))`, which produces a `BufferedReaderPayload` with `_autoclose = False` — "Has file handle that needs explicit closing", per `payload.py`), the file descriptor stays open. Verified live: after `session.post()` to a server responding 302 to a POST, the underlying file object's `.closed` remains `False` even after the request completes and a forced `gc.collect()`.

**Triggering scenario:** POST (or PUT/etc. under 303) with a file-like or stream payload, to any endpoint that responds with a POST→GET-downgrading redirect (a very common "redirect after form submit" pattern).

**Severity:** Medium — not a crash, but a real, reproducible file-descriptor/resource leak that accumulates under normal traffic patterns and can exhaust file descriptors over time.

**Suggested fix:** close the outgoing body before discarding it, mirroring the other exit paths:
```python
if (resp.status == 303 and resp.method != hdrs.METH_HEAD) or (
    resp.status in (301, 302) and resp.method == hdrs.METH_POST
):
    method = hdrs.METH_GET
    if req._body is not None:
        await req._body.close()
    data = None
    ...
```

---

## Defect 2 — Cookie `Domain` attribute matching is case-sensitive, contradicting RFC 6265

**File:** `aiohttp/cookiejar.py`, `_update_cookies` (lines ~359–374) and `_is_domain_match` (lines 532–545)

```python
domain = cookie["domain"]
...
if domain and domain[0] == ".":
    domain = domain[1:]
    cookie["domain"] = domain

if domain and hostname and not self._is_domain_match(domain, hostname):
    continue
...
@staticmethod
def _is_domain_match(domain: str, hostname: str) -> bool:
    """Implements domain matching adhering to RFC 6265."""
    if hostname == domain:
        return True
    if not hostname.endswith(domain):
        return False
    ...
```

**What goes wrong:** `domain` is taken verbatim from the `Set-Cookie` header's `Domain=` attribute and never lower-cased, while `hostname` (`response_url.raw_host`) is already normalized to lowercase by `yarl`. `_is_domain_match` then does a plain case-sensitive `==`/`.endswith()` comparison. A `Set-Cookie` response whose `Domain` attribute differs from the request host only in case is silently rejected.

Verified directly against the parsing/matching logic in this checkout:
```
update_cookies_from_headers(["sess=1; Domain=Example.COM"], URL("http://example.com/"))
  -> cookie dropped ("example.com".endswith("Example.COM") is False)
update_cookies_from_headers(["sess=1; Domain=example.com"], URL("http://example.com/"))
  -> cookie accepted
```

**Why it's wrong:** RFC 6265 §5.1.3 defines domain-match as case-insensitive: "the domain string and the string will have been canonicalized to lower case at this point." This code performs the comparison without that canonicalization, so a legitimate, spec-conformant cookie is dropped purely because a server emitted `Domain=Example.COM` (or any other non-lowercase casing) instead of `domain=example.com`.

**Triggering scenario:** Any server that sets `Set-Cookie: name=value; Domain=<MixedCase>` — this silently breaks session/auth cookies with no error or log message, surfacing to users as "logged out for no reason."

**Severity:** Medium — silent, spec-violating behavior with real (if server-dependent) frequency; not itself a security bypass.

**Suggested fix:** lowercase the `domain` value when it's extracted from the cookie (e.g. `domain = cookie["domain"].lower()`), and keep it lowercase everywhere it's subsequently used as a dict/set key (`_cookies`, `_host_only_cookies`) so lookups in `filter_cookies` stay consistent.

---

## Defect 3 — `BaseRequest.raw_path` drops the leading `/` for absolute-form request targets with an empty path

**File:** `aiohttp/web_request.py`, lines 514–541 (`raw_path` property)

```python
if self._message.url.absolute and self._method != "CONNECT":
    scheme_sep = path.find("://")
    assert scheme_sep != -1
    cursor = scheme_sep + 3
    rel = len(path)
    for delimiter in "/?#":
        found = path.find(delimiter, cursor)
        if found != -1:
            rel = min(rel, found)
    return path[rel:]
return path
```

**What goes wrong:** For an absolute-form request-target with no path segment after the authority (a proxy-style request line, e.g. `GET http://example.com HTTP/1.1`), none of `/`, `?`, `#` are found after the authority, so `rel` stays at `len(path)` and `path[rel:]` returns `""` instead of `"/"`. If there's a query but no path (`GET http://example.com?x=1 HTTP/1.1`), the result is `"?x=1"` — missing the leading `/`, which is not a syntactically valid path.

Reproduced by feeding real request lines through `HttpRequestParser` and evaluating the property logic:
```
GET http://example.com HTTP/1.1       -> raw_path = ''      (request.path correctly returns '/')
GET http://example.com?x=1 HTTP/1.1   -> raw_path = '?x=1'  (request.path correctly returns '/?x=1')
GET http://example.com/ HTTP/1.1      -> raw_path = '/'      (correct)
```

**Why it's wrong:** Per RFC 9112 §3.2.2, an absolute-form target's path, when empty, is equivalent to `"/"` — exactly what `request.path` (backed by `yarl`'s URL normalization) already returns for the same input. The docstring for `raw_path` documents the contract as "The URL including raw *PATH INFO*", with its own worked example beginning with `/`. Here `raw_path` and `path` disagree (`''` vs `'/'`), and `raw_path` can return a value (`'?x=1'`) that isn't a valid path at all — this will break any code that assumes `raw_path` always starts with `/` (routing, WAF-style matching, access logging, cache-key derivation).

**Severity:** Medium — not a crash, but a documented public API returns a spec-violating, non-path value for a legitimate (if uncommon) request shape (explicit-proxy / absolute-form requests).

**Suggested fix:** normalize the result to always start with `/`, e.g.:
```python
rest = path[rel:]
return rest if rest[:1] in ("/", "?", "#") else "/" + rest
```

---

## Defect 4 — `%{FOO}e` access-log format directive is documented and matched by the regex but crashes with `KeyError`

**File:** `aiohttp/web_log.py`

- Docstring (lines 41–43) documents `%{FOO}e` → `os.environ['FOO']`.
- `FORMAT_RE` (line 62): `r"%(\{([A-Za-z0-9\-_]+)\}([ioe])|[atPrsbOD]|Tf?)"` — still matches the `e` variant.
- `LOG_FORMAT_MAP` (lines 47–59) has no `"e"` key (only `"i"` and `"o"` for the equivalent bracketed forms).
- There is no `_format_e` method on `AccessLogger` (only `_format_i`/`_format_o` exist), even though the docstring for `compile_format` (line 102) still says "Exceptions are `_format_e`, `_format_i` and `_format_o` methods which also receive key name."

**What goes wrong:** Constructing an `AccessLogger` (directly, or indirectly via `web.run_app(..., access_log_format=...)`) with any format string containing `%{FOO}e` raises an uncaught `KeyError: 'e'` at construction time, inside `compile_format()`:

```python
format_key2 = (self.LOG_FORMAT_MAP[atom[2]], atom[1])   # atom[2] == "e" -> KeyError
```

Reproduced directly:
```
$ python3 -c "from aiohttp.web_log import AccessLogger; import logging; AccessLogger(logging.getLogger('t'), '%a %{FOO}e')"
KeyError: 'e'
```

**Why it's wrong:** The class's own docstring documents `%{FOO}e` as a supported, working format directive, and the regex used to tokenize format strings still explicitly recognizes it (the `[ioe]` alternation) — but the lookup table and formatting method that would implement it were removed (or never added) without removing the `"e"` case from the regex/docs. The feature is advertised but unusable: any application that follows the documented format string crashes at server-startup / logger-construction time.

**Severity:** Medium — a straightforward, deterministic crash for anyone using a documented feature; no per-request DoS, but a real bug reachable via ordinary configuration (not a malicious/adversarial input).

**Suggested fix:** either restore the feature (add `"e": "environ_value"` to `LOG_FORMAT_MAP` and a `_format_e` method reading `os.environ.get(key, "-")`), or remove `e` from `FORMAT_RE`'s `[ioe]` alternation and strip the `%{FOO}e` line from the docstring and the `_format_e` mention in `compile_format`'s docstring, so the documented surface matches the implemented one.

---

## Defect 5 — Chunked-encoding chunk-size and trailer lines bypass the `max_line_size`/`max_field_size` bound when unterminated within a single `feed_data()` call

**File:** `aiohttp/http_parser.py`, `HttpPayloadParser.feed_data`, `ParseState.PARSE_CHUNKED` branch

- Bound check that only covers the *previous* call's leftover tail, run once at the top of the branch (lines 999–1007):
```python
if self._chunk_tail:
    if self._chunk != ChunkState.PARSE_CHUNKED_CHUNK:
        max_line_length = self._max_line_size
        if self._chunk == ChunkState.PARSE_TRAILERS:
            max_line_length = self._max_field_size
        if len(self._chunk_tail) > max_line_length:
            raise LineTooLong(self._chunk_tail[:100] + b"...", max_line_length)
    chunk = self._chunk_tail + chunk
    self._chunk_tail = b""
```
- The "no separator found yet" branches that store the *newly arrived* data with no length check at all, in `PARSE_CHUNKED_SIZE` (~line 1062) and `PARSE_TRAILERS` (~line 1112):
```python
else:
    if b"\n" in chunk:
        exc = TransferEncodingError("Bad chunk-size line ending, expected CRLF")
        ...
    self._chunk_tail = chunk
    return PayloadState.PAYLOAD_NEEDS_INPUT, b""
```

**What goes wrong:** If a single call to `feed_data()` delivers a chunk-size line (or trailer line) that is much larger than `max_line_size`/`max_field_size` and contains no CRLF, that entire block is stored into `self._chunk_tail` with no size check. The only bound check (lines 999–1007) validates the tail carried over from the *previous* call, before merging with the newly arrived data — so it only fires on the call *after* the oversized data has already been buffered. Compare this to the equivalent header-line-parsing path (`HttpParser.feed_data`, "no SEP found" branch, lines 522–530), which checks `len(self._tail) > self.max_line_size` and raises `LineTooLong` **immediately**, in the same call, before returning.

Verified directly: feeding `HttpRequestParser` a single `Transfer-Encoding: chunked` request whose body chunk begins with a 2 MiB block containing no CRLF, with `max_line_size=100`, was accepted without error and the full 2,097,152 bytes were held in `HttpPayloadParser._chunk_tail` — about 20,000× the configured limit. The eventual `LineTooLong` (on the next call with more data) is also not raised synchronously to the caller: `HttpParser.feed_data`'s exception handling only re-raises `InvalidHeader`/`TransferEncodingError` and instead attaches other exceptions (including `LineTooLong`) to `payload.exception()`, so the oversized buffer persists until the application reads `request.content`/`response.content`.

**Why it's wrong:** `max_line_size`/`max_field_size` exist to bound how much unterminated line data the parser will ever hold in memory — a guarantee the header-parsing path enforces synchronously (line 529–530) but the chunked-body/trailer path does not.

**Triggering scenario:** A peer (client hitting an aiohttp server, or a server being read by `ClientSession`) sends a `Transfer-Encoding: chunked` body whose chunk-size line or a trailer line is large and arrives without a CRLF within a single read/`feed_data()` call — plausible whenever the transport delivers more than a few KB per callback (large TCP reads, TLS record batching, pipelined/buffered input). This is a memory-exhaustion amplification vector across many connections.

**Severity:** Medium — bounded by how much data one `feed_data()` call can carry, but it's a clear, reproducible violation of a documented resource-bounding invariant, and it scales with connection count.

**Suggested fix:** in the "separator not found" branches of `PARSE_CHUNKED_SIZE` and `PARSE_TRAILERS`, check `len(chunk)` against `self._max_line_size` / `self._max_field_size` *before* storing it into `self._chunk_tail`, raising `LineTooLong` immediately — mirroring the existing immediate check on the non-chunked header-parsing path.

---

## Areas checked with no confident defect found

The following were reviewed in full (line-by-line reasoning, and in several cases live reproduction scripts against the checkout) with no defect confident enough to report:

- **Connection pooling / DNS resolution** (`connector.py`): placeholder-add/remove sequencing in `connect()`, `_release`/`_release_acquired`/`_release_waiter`, limit/semaphore accounting, `_DNSCacheTable` TTL/expiry, `_resolve_host_with_throttle`'s cancellation-shielding.
- **Cookie path defaulting** (`cookiejar.py`): the local `path.rstrip("/")` not being written back to `cookie["path"]` is intentional (it's what lets `filter_cookies`'s `len(cookie["path"]) > path_len` check reject over-long paths correctly).
- **`resolver.py`, `tracing.py`, `_cookie_helpers.py`**: DNS resolution logic (IPv4/IPv6/link-local handling, per-loop resolver sharing), `Signal`/tracing wiring, cookie header parsing/unquoting — no issues found.
- **Client request/response lifecycle** (`client_reqrep.py`, `client_proto.py`, `client_ws.py`, `client_exceptions.py`, `client_middlewares.py`, `client_middleware_digest_auth.py`): redirect-loop retry-on-`ClientOSError`, connection-lost exception classification, WebSocket close/heartbeat state machine, RFC 7616 digest-auth computation (including `auth-int` body-hash handling against one-shot streaming payloads) — no issues found.
- **`web.py`, `web_app.py`, `web_runner.py`, `web_server.py`**: application lifecycle, middleware caching, site/runner startup and shutdown — no issues found.
- **`web_protocol.py`**: pipelined-message queue depth cap, pause/resume backpressure, lingering-close handling, `handle_error` — a minor `message_consumed()`/parser in-flight-counter drift for synthetic parser-error messages was investigated and ruled out as having no observable effect (the error path always forces `keep_alive=False`).
- **`web_response.py`**: header preparation, compression, Content-Length/chunked/keep-alive interplay — no issues found.
- **`web_urldispatcher.py`**: `StaticResource`'s path-traversal normalization and symlink-sandbox checks (both `break_symlink_sandbox=True` and the default `resolve()+relative_to()` containment check), routing/matching for `PlainResource`/`DynamicResource`/`Domain` — no issues found; these already correctly guard the historical path-traversal CVE class.
- **`web_ws.py`**: WebSocket handshake header validation, heartbeat/ping-pong scheduling, `close()` state machine — no issues found.
- **`web_fileresponse.py`**: Range/If-Range/If-Match/If-None-Match/If-Modified-Since/If-Unmodified-Since precedence per RFC 9110 §13, suffix/open-ended range handling, 416 boundary cases, `sendfile`/fallback cleanup — no issues found.
- **`web_middlewares.py`**: `normalize_path_middleware`'s handling of the GHSA-v6wp-4m6f-gcjg protocol-relative-URL open-redirect fix — present and applied correctly.
- **`web_exceptions.py`**: exception/header construction — no issues found.
- **`multipart.py`, `payload.py`, `streams.py`, `formdata.py`, `compression_utils.py`, `helpers.py`, `worker.py`, `base_protocol.py`, `abc.py`, `hdrs.py`, `http.py`, `http_exceptions.py`, `http_websocket.py`, `tcp_helpers.py`, `typedefs.py`, `test_utils.py`, `_websocket/helpers.py`, `_websocket/models.py`, `_websocket/reader_py.py`, `_websocket/writer.py`, `http_writer.py`: read/reviewed in full; two candidate issues (concatenated-gzip/zstd decompression under a length cap, and a zero-length read in `IOBasePayload.write_with_length`) were investigated with reproduction scripts and ruled out — behavior was correct in both cases.

---

## Files read

- `aiohttp/client.py`
- `aiohttp/client_reqrep.py`
- `aiohttp/client_proto.py`
- `aiohttp/client_ws.py`
- `aiohttp/client_exceptions.py`
- `aiohttp/client_middlewares.py`
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/connector.py`
- `aiohttp/cookiejar.py`
- `aiohttp/_cookie_helpers.py`
- `aiohttp/resolver.py`
- `aiohttp/tracing.py`
- `aiohttp/web.py`
- `aiohttp/web_app.py`
- `aiohttp/web_protocol.py`
- `aiohttp/web_request.py`
- `aiohttp/web_response.py`
- `aiohttp/web_runner.py`
- `aiohttp/web_server.py`
- `aiohttp/web_urldispatcher.py`
- `aiohttp/web_ws.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_middlewares.py`
- `aiohttp/web_exceptions.py`
- `aiohttp/web_log.py`
- `aiohttp/http_parser.py`
- `aiohttp/http_writer.py`
- `aiohttp/multipart.py`
- `aiohttp/payload.py`
- `aiohttp/streams.py`
- `aiohttp/formdata.py`
- `aiohttp/compression_utils.py`
- `aiohttp/helpers.py`
- `aiohttp/worker.py`
- `aiohttp/base_protocol.py`
- `aiohttp/abc.py`
- `aiohttp/hdrs.py`
- `aiohttp/http.py`
- `aiohttp/http_exceptions.py`
- `aiohttp/http_websocket.py`
- `aiohttp/tcp_helpers.py`
- `aiohttp/typedefs.py`
- `aiohttp/test_utils.py`
- `aiohttp/_websocket/helpers.py`
- `aiohttp/_websocket/models.py`
- `aiohttp/_websocket/reader_py.py`
- `aiohttp/_websocket/writer.py`

Not reviewed (out of scope): `aiohttp/_http_parser.pyx`, `aiohttp/_http_writer.pyx`, `aiohttp/_websocket/mask.pyx`, `aiohttp/_websocket/reader_c.pxd`, `aiohttp/_cparser.pxd`, `aiohttp/_find_header.h`/`.pxd` (Cython/C extension sources), and all of `tests/`.

All five defects above were confirmed by direct code tracing plus a small executable reproduction against the checkout (via `/tmp/aiohttp-venv` and, for the parser, direct construction of `HttpRequestParser`/`AccessLogger` instances from the checked-out source), not inferred from reading alone.
