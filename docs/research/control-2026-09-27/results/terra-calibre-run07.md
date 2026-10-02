model: gpt-5.6-terra
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:37:40 UTC; finished 2026-09-28 23:41:34 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# calibre `src/calibre/srv/` review

Reviewed commit `7691f4f1a155d799afdfec99e2cdc2716c178402`.

## Findings

### 1. Successful HTTP/1.0 requests are serialized as HTTP/1.1 and can receive chunked bodies

**Severity: medium**

**File:** `src/calibre/srv/http_response.py:561,582`

`HTTPRequest.parse_request_line()` sets `self.response_protocol` to `HTTP/1.0` for an HTTP/1.0 request (see `src/calibre/srv/http_request.py:322-326`), and error responses correctly use that value. Successful responses do not: `job_done()` passes `self.method is HTTP1` to `finalize_output()`, which is always false because `self.method` is a request method such as `GET`, and it writes a status line beginning with the hard-coded `HTTP11`.

Consequently, an HTTP/1.0 request for any successful endpoint receives an HTTP/1.1 status line. If it also accepts gzip and the body meets the compression threshold, the false `is_http1` value permits the chunked gzip path (`finalize_output()` at lines 752-757 and 793-794), so the HTTP/1.0 client is sent a `Transfer-Encoding: chunked` body that it cannot decode.

Use `self.response_protocol is HTTP1` when calling `finalize_output()`, and construct the successful status line from `self.response_protocol` rather than the `HTTP11` constant. This keeps successful and error responses on the same negotiated protocol and prevents HTTP/1.1-only transfer coding for HTTP/1.0 clients.

### 2. Iterable endpoint output always fails during response finalization

**Severity: medium**

**File:** `src/calibre/srv/http_response.py:749-760`

For an endpoint that returns an iterable/generator, the fallback at line 749 intentionally wraps it in `GeneratedOutput`; `write_response_body()` explicitly has a `GeneratedOutput` branch that serializes the iterable as chunked output (lines 651-652). But `GeneratedOutput` has `content_length = None` and does not define `accept_ranges`, while lines 755 and 759 unconditionally access both attributes under the default configuration. With the default positive `compress_min_size`, line 755 first raises `TypeError` for `None >= <int>`; if compression is disabled, line 759 instead raises `AttributeError` for the missing `accept_ranges`. Thus the supported generated-output path returns a 500 before any chunks are written.

Make generated outputs explicitly non-rangeable (`accept_ranges = False`) and only compare `content_length` with the compression threshold when it is not `None`. The existing chunked branch can then send the generated data as intended.

### 3. Invalid suffix byte ranges are emitted as malformed 206 responses

**Severity: low**

**File:** `src/calibre/srv/http_response.py:152-161`

The `get_ranges()` docstring says an empty result means no valid range was found. However, the suffix-range branch accepts non-positive suffix lengths. For example, `Range: bytes=--5` parses `stop` as `-5` and returns `Range(content_length + 5, content_length - 1, -5)`; `Range: bytes=-0` similarly returns a zero-length range, and `Range: bytes=-1` for an empty representation returns `Range(0, -1, 0)`. These are nonempty results, so `finalize_output()` treats them as satisfiable and emits `206 Partial Content` with invalid `Content-Range` / negative `Content-Length` values instead of its normal unsatisfiable-range response at lines 764-765.

Reject suffix lengths less than or equal to zero, and return no valid ranges when the representation length is zero. That causes these inputs to follow the existing 416 path.

## Files read

- `src/calibre/srv/ajax.py`
- `src/calibre/srv/auth.py`
- `src/calibre/srv/books.py`
- `src/calibre/srv/cdb.py`
- `src/calibre/srv/changes.py`
- `src/calibre/srv/code.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/convert.py`
- `src/calibre/srv/embedded.py`
- `src/calibre/srv/errors.py`
- `src/calibre/srv/fts.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/jobs.py`
- `src/calibre/srv/last_read.py`
- `src/calibre/srv/legacy.py`
- `src/calibre/srv/library_broker.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/metadata.py`
- `src/calibre/srv/opds.py`
- `src/calibre/srv/opts.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/standalone.py`
- `src/calibre/srv/users.py`
- `src/calibre/srv/users_api.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/tests/auth.py`
- `src/calibre/srv/tests/http.py`
- `src/calibre/srv/tests/routes.py`
- `src/calibre/srv/tests/web_sockets.py`
