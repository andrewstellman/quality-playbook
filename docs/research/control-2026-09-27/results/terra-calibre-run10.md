model: gpt-5.6-terra
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:42:42 UTC; finished 2026-09-28 23:45:48 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Calibre `src/calibre/srv/` review

## Findings

### High — successful HTTP/1.0 requests are emitted as HTTP/1.1 and can use chunked transfer coding

- **File/lines:** `src/calibre/srv/http_response.py:561,582`
- **Trigger:** A successful HTTP/1.0 request, particularly one whose result is compressed or streamed (for example, a sufficiently large text response with `Accept-Encoding: gzip`).
- **What goes wrong:** `job_done()` passes `self.method is HTTP1` to `finalize_output()`. `self.method` is a request verb such as `GET`, so this condition is always false; it never identifies an HTTP/1.0 request. `finalize_output()` consequently permits HTTP/1.1-only chunked transfer coding for HTTP/1.0 responses. Independently, line 582 always serializes the successful response status line with `HTTP11`. Thus an HTTP/1.0 client receives a response claiming to be HTTP/1.1 and may receive chunked framing it did not negotiate or support.
- **Why this is wrong:** `connection_ready()` records the request protocol in `self.response_protocol`; `simple_response()` deliberately uses that protocol at line 460 and specifically translates status codes for HTTP/1.0. The normal success path should honor the same protocol and use it to decide whether HTTP/1.1 features are available.
- **Suggested fix:** Pass `self.response_protocol is HTTP1` to `finalize_output()` and build the status line from `self.response_protocol`, rather than `HTTP11`.

### High — TLS connections detected as closed are removed using a stale file descriptor

- **File/line:** `src/calibre/srv/loop.py:615-616`
- **Trigger:** More than one active connection, with TLS enabled, when `drain_ssl_buffer()` marks a connection not ready.
- **What goes wrong:** `close_needed` stores `(s, conn)` pairs, but the close loop binds the descriptor as `x` and calls `self.close(s, conn)`. `s` is left over from the preceding loops, usually the last entry examined in `connection_map` (or the final timed-out connection). The target connection object is closed, while `ServerLoop.close()` removes the unrelated stale descriptor from `connection_map`. The closed target can remain registered and an unrelated live connection can disappear from the map.
- **Why this is wrong:** The immediately preceding timeout loop correctly calls `self.close(s, conn)` using its own loop variable. `ServerLoop.close()` removes the passed key before closing the passed connection, so the key and connection must be from the same pair.
- **Suggested fix:** Bind the tuple as `for s, conn in close_needed:` (or call `self.close(x, conn)`).

### High — setting the documented “no limit” job timeout aborts every running worker job

- **File/lines:** `src/calibre/srv/jobs.py:198-224`
- **Trigger:** Configure `max_job_time=0`, then start any background job that does not finish before the event loop's next timeout check.
- **What goes wrong:** The manager stores zero at line 98. `update_max_block()` computes `0 - elapsed`, immediately sets `max_block = 0`, and the event loop then calls `abort_hanging_jobs()`, which sets every running job's `abort_event` because the same expression is `<= 0`. Jobs therefore get aborted instead of running without a limit.
- **Why this is wrong:** The option's own help text in `src/calibre/srv/opts.py:81` says, “Set to zero for no limit.” The timeout code treats zero as an already-expired limit.
- **Suggested fix:** Treat a zero `max_job_time` as disabled: leave `max_block` as `None` and skip timeout/abort calculations when the configured limit is zero.

### Medium — malformed Range headers can turn a normal file request into a 500 response

- **File/line:** `src/calibre/srv/http_response.py:137-138`
- **Trigger:** Request a file-producing endpoint with a header such as `Range: bytes=123` (a range item without `-`).
- **What goes wrong:** `brange.split('-', 1)` produces one item, but assignment to `start, stop` is outside a `try` block and raises `ValueError`. The exception escapes `get_ranges()` and the normal request-handler error path converts it to an internal-server-error response.
- **Why this is wrong:** The function's docstring says an empty result represents “no valid range,” and it already handles malformed unit/number forms by returning or continuing. A syntactically malformed range item should follow that invalid-range path, rather than crashing response finalization.
- **Suggested fix:** Catch `ValueError` around the split/unpack and continue to the next item (or return an empty list when no valid ranges remain).

### Medium — `Accept-Encoding: gzip;q=0` still enables gzip

- **File/lines:** `src/calibre/srv/http_response.py:101-105`; `src/calibre/srv/utils.py:232-248`
- **Trigger:** A client sends `Accept-Encoding: gzip;q=0` for a compressible response over HTTP/1.1.
- **What goes wrong:** `sort_q_values()` parses and sorts quality values, but returns only token names. `acceptable_encoding()` then returns `gzip` whenever it occurs, including at quality zero. `finalize_output()` treats that return value as permission to set `Content-Encoding: gzip`.
- **Why this is wrong:** Quality zero declares an encoding unacceptable. The helper's own documentation identifies these as q-value headers, and the parser clamps q to zero at `utils.py:243`; discarding that value causes the explicit rejection to be ignored.
- **Suggested fix:** Preserve q-values through selection, and only choose an allowed encoding whose q-value is greater than zero.

## Files read

- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/auth.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/books.py`
- `src/calibre/srv/cdb.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/jobs.py`
- `src/calibre/srv/opts.py`
- `src/calibre/srv/embedded.py`
- `src/calibre/srv/tests/loop.py`
- Context used to verify the data-file contract: `src/calibre/db/cache.py`, `src/calibre/db/backend.py`, and `src/calibre/db/constants.py`
