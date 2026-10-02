model: gpt-5.6-terra
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:31:12 UTC; finished 2026-09-28 23:33:56 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Calibre `src/calibre/srv/` review

Reviewed commit `7691f4f1a155d799afdfec99e2cdc2716c178402`.

## Defects

### 1. Normal HTTP/1.0 responses are emitted as HTTP/1.1 and may use chunked transfer coding

- **Location:** `src/calibre/srv/http_response.py:561,582`
- **Severity:** medium
- **Trigger and impact:** A successful request made with `HTTP/1.0` takes this path. `HTTPRequest.parse_request_line()` preserves HTTP/1.0 in `self.response_protocol` (`src/calibre/srv/http_request.py:322-326`), and the server's tests explicitly exercise HTTP/1.0 requests (`src/calibre/srv/tests/http.py:347-357`). But `job_done()` passes `self.method is HTTP1` to `finalize_output()`; `self.method` is an HTTP verb, so this is always false. Therefore an HTTP/1.0 request can select compression and `Transfer-Encoding: chunked`, which `finalize_output()` deliberately suppresses when its `is_http1` argument is true. It then unconditionally constructs the successful response status line with `HTTP11` at line 582, even though the request's selected response protocol is HTTP/1.0. HTTP/1.0 clients consequently receive an HTTP/1.1 status line and, for generated/compressed content, chunked framing they do not support.
- **Suggested fix:** Pass `self.response_protocol is HTTP1` to `finalize_output()`, and build the response status line from `self.response_protocol` rather than `HTTP11`.

### 2. `max_job_time=0` immediately aborts jobs instead of disabling the limit

- **Location:** `src/calibre/srv/jobs.py:98,198-212,214-224`
- **Severity:** medium
- **Trigger and impact:** The option description says that setting **Maximum time for worker processes** to zero means “no limit” (`src/calibre/srv/opts.py:78-81`). `JobsManager` converts zero to `self.max_job_time = 0`. After a job starts, `update_max_block()` computes `0 - (now - job.start_time)`, which is immediately non-positive, sets `max_block` to zero, and the event loop immediately calls `abort_hanging_jobs()`. That method repeats the same calculation and sets the job's abort event. Thus every job is treated as over its time limit when the documented no-limit value is configured.
- **Suggested fix:** Treat zero as disabled in `update_max_block()` and `abort_hanging_jobs()` (for example, return without scheduling/checking a timeout when `self.max_job_time == 0`).

### 3. SSL-read cleanup closes one connection but removes a different connection from the map

- **Location:** `src/calibre/srv/loop.py:615-616`
- **Severity:** medium
- **Trigger and impact:** During TLS operation, `tick()` adds a connection whose SSL buffer read made it not-ready to `close_needed` as `(s, conn)` (`src/calibre/srv/loop.py:600-605`). The cleanup loop binds the socket descriptor as `x`, but calls `self.close(s, conn)` using the stale `s` left by the earlier `connection_map` iteration instead. `close()` removes the descriptor it receives from `connection_map` and closes the supplied connection. With multiple active connections, this removes an unrelated live connection from `connection_map` while leaving the closed TLS connection mapped. The next event-loop iteration can then select or dispatch against the stale closed descriptor.
- **Suggested fix:** Call `self.close(x, conn)` in the `close_needed` loop.

### 4. Valid SMIL millisecond timestamps are rejected

- **Location:** `src/calibre/srv/render_book.py:300-303`
- **Severity:** low
- **Trigger and impact:** A SMIL media-overlay timestamp such as `500ms` reaches `parse_smil_time()`. The function's comment identifies SMIL timing syntax as its contract. Since `500ms` also ends in `s`, the first branch runs and evaluates `float('500m')`, raising `ValueError`; the later `endswith('ms')` branch is unreachable for every millisecond value. `transform_smil()` uses this parser for `clipBegin` and `clipEnd` (`src/calibre/srv/render_book.py:341-345`), so a book using millisecond offsets cannot be rendered for read-aloud synchronization.
- **Suggested fix:** Test the `ms` suffix before the generic `s` suffix.

## Files read

- `src/calibre/srv/ajax.py`
- `src/calibre/srv/auth.py`
- `src/calibre/srv/auto_reload.py`
- `src/calibre/srv/books.py`
- `src/calibre/srv/cdb.py`
- `src/calibre/srv/changes.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/convert.py`
- `src/calibre/srv/embedded.py`
- `src/calibre/srv/fts.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/jobs.py`
- `src/calibre/srv/legacy.py`
- `src/calibre/srv/library_broker.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/metadata.py`
- `src/calibre/srv/opds.py`
- `src/calibre/srv/opts.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/render_book.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/users.py`
- `src/calibre/srv/users_api.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/tests/http.py`
- `src/calibre/srv/tests/loop.py`
