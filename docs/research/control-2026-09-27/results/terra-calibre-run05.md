model: gpt-5.6-terra
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:34:31 UTC; finished 2026-09-28 23:37:18 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Calibre `src/calibre/srv/` review

Reviewed commit: `7691f4f1a155d799afdfec99e2cdc2716c178402`

## Findings

### 1. Successful HTTP/1.0 requests are emitted as HTTP/1.1, and may use HTTP/1.1 chunking

- **Severity:** medium
- **Location:** `src/calibre/srv/http_response.py:561`, `src/calibre/srv/http_response.py:582`
- **Trigger and impact:** A normal successful HTTP/1.0 request (for example, `GET / HTTP/1.0`) is parsed with `self.response_protocol` set to `HTTP/1.0` in `HTTPRequest.parse_request_line()`.  `job_done()` nevertheless always starts the response with the `HTTP11` constant.  Separately, it passes `self.method is HTTP1` to `finalize_output()`; a method is a value such as `"GET"`, so that identity comparison is always false.  Consequently an HTTP/1.0 client that requests gzip for a sufficiently large compressible response can receive `Transfer-Encoding: chunked`, which is an HTTP/1.1 transfer coding.
- **Why this is wrong:** The class explicitly tracks `response_protocol` and uses it for simple/error responses (for example `simple_response()` at line 471), while `finalize_output()` names its final argument `is_http1` and uses it to suppress compression/chunking.  The successful-response path bypasses both mechanisms.
- **Suggested fix:** Pass `self.response_protocol is HTTP1` at line 561 and build the status line from `self.response_protocol` at line 582.  Add a raw HTTP/1.0 success-response test, including a gzip-capable large response, to verify the response line and absence of chunked transfer coding.

### 2. TLS cleanup removes the wrong connection-map entry after a read error

- **Severity:** medium
- **Location:** `src/calibre/srv/loop.py:615-616`
- **Trigger and impact:** With TLS enabled, `drain_ssl_buffer()` can set a connection's `ready` flag false on an SSL/socket read error (lines 321-335).  `tick()` records that connection as `(s, conn)` in `close_needed` (line 605), but the cleanup loop calls `self.close(s, conn)` instead of `self.close(x, conn)`.  If the failed connection is not the last entry visited by the preceding `connection_map` loop, `s` refers to a different live connection.  `close()` removes that unrelated descriptor from the map and closes the failed connection, leaving the failed descriptor mapped to a closed object; the live connection is then no longer serviced or tracked.
- **Why this is wrong:** The loop intentionally binds the descriptor as `x`, and `close_needed` stores that descriptor precisely for later removal.  Using the stale outer-loop variable contradicts the same-file timeout cleanup immediately above, which correctly calls `self.close(s, conn)` with its own loop binding.
- **Suggested fix:** Change line 616 to `self.close(x, conn)`.  Exercise a TLS read failure while at least one other connection is active.

### 3. Old rendered-book cache directories are never pruned from the cache directory

- **Severity:** low
- **Location:** `src/calibre/srv/books.py:108-116`
- **Trigger and impact:** Once a rendered-book manifest is older than `interval`, `clean_final()` is meant to delete its containing cache entry.  `x` is only the basename returned by `os.listdir(fdir)`, but line 116 calls `safe_remove(x)` rather than removing `os.path.join(fdir, x)`.  The stale cache directory under `books_cache_dir()/f` remains indefinitely; in an unusual process working directory containing the same relative name, that unrelated path can instead be removed.
- **Why this is wrong:** The comment at lines 114-115 says the old book cache entry should be deleted, and the mtime checked at line 111 is explicitly `os.path.join(fdir, x, 'calibre-book-manifest.json')`.  The deletion must address the same path.
- **Suggested fix:** Call `safe_remove(os.path.join(fdir, x), False)` (or otherwise pass the fully qualified cache-entry path) and add a test using an expired cache entry.

### 4. A valid zero-length suffix range produces an invalid 206 response

- **Severity:** low
- **Location:** `src/calibre/srv/http_response.py:152-161`
- **Trigger and impact:** For `Range: bytes=-0` on a nonempty file, `stop` becomes zero and the `else` branch returns `Range(content_length, content_length - 1, 0)`.  The response path treats this as a valid range and emits `206 Partial Content` with an impossible `Content-Range` such as `bytes 100-99/100` and `Content-Length: 0`, instead of treating the range as unsatisfiable.
- **Why this is wrong:** `get_ranges()` documents that an empty result means no valid range was found (lines 123-125), and the caller maps that case to `416 Requested Range Not Satisfiable` (lines 764-765).  A suffix length of zero selects no bytes, so constructing a range whose start exceeds its stop violates the `Range` invariant used by the rest of this code.
- **Suggested fix:** Reject `stop <= 0` in the suffix-range branch before constructing a `Range`; add `bytes=-0` to `test_range_parsing` and an end-to-end response assertion.

## Files read

- `src/calibre/srv/ajax.py`
- `src/calibre/srv/auth.py`
- `src/calibre/srv/books.py`
- `src/calibre/srv/cdb.py`
- `src/calibre/srv/code.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/convert.py`
- `src/calibre/srv/fts.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/jobs.py`
- `src/calibre/srv/library_broker.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/metadata.py`
- `src/calibre/srv/opds.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/opts.py`
- `src/calibre/srv/tests/http.py`
