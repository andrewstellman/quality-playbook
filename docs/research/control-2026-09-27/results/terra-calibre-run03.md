model: gpt-5.6-terra
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:31:29 UTC; finished 2026-09-28 23:34:19 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Calibre `src/calibre/srv/` review

Reviewed commit `7691f4f1a155d799afdfec99e2cdc2716c178402`.

## Findings

### High — TLS EOF cleanup removes the wrong connection

**File:** `src/calibre/srv/loop.py:615`

When TLS is enabled and `drain_ssl_buffer()` finds an EOF for one connection while another connection is present, `close_needed` correctly stores `(s, conn)` for the closed connection at lines 600–605. The cleanup loop then ignores its `x` value and calls `self.close(s, conn)`, where `s` is the stale value left by a previous loop. This removes a different connection-map entry while closing the EOF connection object. The closed connection can remain registered under its old descriptor and the unrelated connection is no longer tracked, leading to stale/closed descriptors in `select()` and potentially terminating the server loop.

This contradicts the immediately preceding `remove` cleanup loop (lines 611–613), which closes the stored socket descriptor.

**Suggested fix:** Call `self.close(x, conn)` in the `close_needed` loop. Add a TLS regression test with at least two active connections, closing a non-final connection while the server drains TLS buffers.

### High — `max_job_time=0` aborts jobs despite being documented as unlimited

**File:** `src/calibre/srv/jobs.py:198-221`

With `max_job_time` set to zero, `__init__` stores `0` seconds (line 98). As soon as a job is started, `update_max_block()` computes a negative elapsed-time delta and sets `max_block` to zero (lines 202–207). The event loop immediately calls `abort_hanging_jobs()`, which sets the job's abort event because the same delta is non-positive (lines 214–221). Thus every worker process is aborted almost immediately.

`src/calibre/srv/opts.py:78-81` explicitly documents zero as “no limit,” so this is a behavior/documentation contradiction that breaks long-running conversion and rendering jobs for that valid configuration.

**Suggested fix:** Represent no timeout as `None` (or explicitly skip timeout calculations when `self.max_job_time == 0`) in both `update_max_block()` and `abort_hanging_jobs()`. Add a test that configures zero and verifies a job exceeding a short interval completes without an abort event.

### Medium — successful HTTP/1.0 requests receive an HTTP/1.1 status line and HTTP/1.1-only features

**File:** `src/calibre/srv/http_response.py:561,582`

For a successful HTTP/1.0 request, request parsing sets `self.response_protocol` to `HTTP/1.0` (`src/calibre/srv/http_request.py:322-326`). The normal worker-response path nevertheless hard-codes `HTTP11` for the status line at line 582. It also passes `self.method is HTTP1` at line 561; `self.method` is a request-method string such as `GET`, so this is always false. Consequently `finalize_output()` can enable gzip chunked transfer encoding and byte ranges for HTTP/1.0 requests (lines 752–759 and 793–794), even though the method's `is_http1` parameter is meant to suppress those features.

The existing tests deliberately exercise HTTP/1.0 request handling (`src/calibre/srv/tests/http.py:347-358`), so this is not an unsupported request form. HTTP/1.0 clients can therefore receive a response version and transfer framing they did not negotiate.

**Suggested fix:** Pass `self.response_protocol is HTTP1` to `finalize_output()` and construct the status line with `self.response_protocol` rather than `HTTP11`. Add assertions for `HTTPResponse.version`, absence of chunked framing, and absence of range support on successful HTTP/1.0 responses.

### Medium — absolute-form request target loses a query when it has no path

**File:** `src/calibre/srv/http_request.py:55-58`

For a valid absolute-form target such as `GET http://example.test?library_id=x HTTP/1.1`, `remainder.partition(b'/')` finds no slash. The code assigns the complete `example.test?library_id=x` string to `authority`, then sets `path` to `/`; the query is no longer part of `path`. `parse_uri()` only extracts a query from `path` at line 81, so the handler receives an empty query instead of `library_id=x`.

The adjacent comment documents the supported form as `host [ ":" port ] [ abs_path [ "?" query ]]` (lines 52–54), which expressly allows this input. This affects proxy clients that use HTTP absolute-form requests without an explicit `/` before the query.

**Suggested fix:** Split the authority at the first `/` *or* `?`, preserving `?query` as the path/query portion; for example, use a delimiter-aware split and produce `b'/?' + query` when the absolute URI has no path. Add tests for both `http://host?x=1` and `http://host/path?x=1`.

## Files read

- `src/calibre/srv/ajax.py`
- `src/calibre/srv/auth.py`
- `src/calibre/srv/auto_reload.py`
- `src/calibre/srv/books.py`
- `src/calibre/srv/cdb.py`
- `src/calibre/srv/changes.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/convert.py`
- `src/calibre/srv/fts.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/jobs.py`
- `src/calibre/srv/last_read.py`
- `src/calibre/srv/library_broker.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/metadata.py`
- `src/calibre/srv/opts.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/users.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/tests/http.py`
- `src/calibre/srv/tests/loop.py`
