# Code review: calibre `src/calibre/srv/`

Repo: calibre @ 7691f4f1a155d799afdfec99e2cdc2716c178402
Scope: `src/calibre/srv/`

## Defect 1: `is_http1` flag computed from the wrong attribute, always `False`

**File/line:** `src/calibre/srv/http_response.py:561`

```python
output = self.finalize_output(output, data, self.method is HTTP1)
```

**What goes wrong:** `finalize_output`'s third parameter, `is_http1`, is meant to tell the
method whether the response is being sent over HTTP/1.0 (which lacks chunked
transfer-encoding and other HTTP/1.1-only features). Instead of comparing the connection's
*protocol* (`self.response_protocol`), this line compares `self.method` — the HTTP request
method (`'GET'`, `'HEAD'`, `'PUT'`, `'POST'`, `'TRACE'`, `'DELETE'`, `'OPTIONS'`, set in
`http_request.py:315` and restricted to `HTTP_METHODS` at `http_request.py:21`) — against
`HTTP1`, which is the string constant `'HTTP/1.0'` (`src/calibre/srv/utils.py:25`).

`self.method` can never equal `'HTTP/1.0'`; it is always one of the seven HTTP verbs. So
`self.method is HTTP1` is unconditionally `False` for every request, regardless of whether
the client actually negotiated HTTP/1.0 or HTTP/1.1. `is_http1` is therefore always `False`,
even when `self.response_protocol is HTTP1` is true (i.e. the connection really is HTTP/1.0).

**Why it is wrong:** Elsewhere in the very same file the correct pattern is used —
`simple_response` at line 460 checks `if self.response_protocol is HTTP1:` to special-case
status codes HTTP/1.0 doesn't support. `finalize_output` uses `is_http1` to gate two things:

```python
compressible = (
    compressible
    and request.status_code == http.client.OK
    and (opts.compress_min_size > -1 and output.content_length >= opts.compress_min_size)
    and acceptable_encoding(request.inheaders.get('Accept-Encoding', ''))
    and not is_http1
)
...
accept_ranges = not compressible and output.accept_ranges is not None and request.status_code == http.client.OK and not is_http1
```

and, further down:

```python
if compressible or output.content_length is None:
    outheaders.set('Transfer-Encoding', 'chunked', replace_all=True)
```

Because `is_http1` is always `False`, the `not is_http1` guards never actually exclude
HTTP/1.0 connections. Concretely, for a client that sends `HTTP/1.0` in the request line
(`self.response_protocol` becomes `HTTP1`, see `parse_request_line` /
`self.response_protocol = protocol_map[min((1, 1), rp)]` in `http_request.py:326`) and a
`Content-Type` that is compressible (e.g. `text/html`) with `Accept-Encoding: gzip`, the
server will set `Transfer-Encoding: chunked` and stream a chunked, gzip-compressed body.
`Transfer-Encoding: chunked` is not a valid response framing for HTTP/1.0 (RFC 1945 /
RFC 7230 §3.3.1 restrict chunked encoding to HTTP/1.1), so an HTTP/1.0 client cannot
correctly determine where the body ends — it has to rely on connection close, which the
server has not necessarily promised (`close_after_response` handling for HTTP/1.0 is
handled independently of this code path). The result is a malformed/unparseable response
for legitimate HTTP/1.0 clients (or HTTP/1.1 clients that for some reason set
`response_protocol` to HTTP1, e.g. `min((1,1), rp)` truncation when a client sends a
higher/lower version) whenever the response would otherwise be compressed or has an
unknown content length. This is a real interoperability/protocol-conformance bug, not
just a style issue, since the code's own sibling check (`simple_response`) demonstrates the
intended semantics of "treat HTTP/1.0 specially," and this call clearly doesn't implement
that for the main response path.

**Severity:** High — every "normal" (non-error, non-HEAD) response prepared by
`job_done`/`finalize_output` silently loses its HTTP/1.0-specific handling for chunked
transfer-encoding and range/accept-ranges signaling. Any deployment or proxy that talks
HTTP/1.0 to calibre's content server can receive protocol-invalid responses.

**Suggested fix:**

```python
output = self.finalize_output(output, data, self.response_protocol is HTTP1)
```

(matching the pattern already used at `http_response.py:460`).

## Other areas reviewed, no confident defects found

- `auth.py` (Digest/Basic auth, nonce synthesis/validation, ban list): logic matches RFC 2617
  and the file's own comments about intentionally not checking nonce-count due to Firefox's
  non-conformant behavior. `check()` uses `==` rather than a constant-time comparison for
  password checks, which is a theoretical timing-attack surface, but I'm not confident this
  rises to a reportable defect given the threat model of a typically LAN-local server and the
  task's ask for "defects" over "speculative concerns" — noting it but not filing it as a
  finding.
- `http_request.py` (request-line/header parsing, chunked request body reading, Content-Length
  handling): parsing logic (chunk size limits, Content-Length vs Transfer-Encoding conflict
  detection, header continuation lines) looks correct and matches RFC 7230.
- `get_ranges()` / range-request handling in `http_response.py` (single and multi-range
  requests, `Content-Range` computation): checked the arithmetic for off-by-one errors;
  found none — `stop = min(stop, content_length - 1)` and the "last N bytes" branch both
  look correct.
- `utils.py` (`MultiDict`, header token parsing): no defects found in the portions read.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/utils.py` (partial — constants, `MultiDict`)
