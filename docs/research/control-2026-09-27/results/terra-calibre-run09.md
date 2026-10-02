model: gpt-5.6-terra
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:41:45 UTC; finished 2026-09-28 23:45:16 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Calibre `src/calibre/srv/` review

Reviewed commit `7691f4f1a155d799afdfec99e2cdc2716c178402`.

## Findings

### High — conversion-job IDs let another restricted writer modify a book outside their restriction

- **Files/lines:** `src/calibre/srv/convert.py:220-257`, `src/calibre/srv/jobs.py:110-121`
- **What goes wrong:** Conversion jobs are stored in the process-global `conversion_jobs` dictionary and are addressed by the sequential `JobsManager` counter. `conversion_status()` accepts any caller that passes the generic `needs_db_write` check, finds a job by this predictable ID, and then calls `db.add_format(job_status.book_id, fmt, job_status.output_path)`. It never verifies that the caller started the job or that the caller can access `job_status.book_id`.

  For example, a non-readonly account restricted to book 1 can poll the completed job ID of a conversion started for book 2 in the same library. The status call imports the converted format into book 2. While the job is running, the same call can also request `abort_job`. A request naming a different library deletes the entry at line 232 before the library check at line 244, so it can discard another user's completed conversion result as well.
- **Why this is wrong:** `start_conversion()` explicitly enforces `ctx.has_id(rd, db, book_id)` before creating a job (lines 204-209), and other book-mutating endpoints enforce the same check, for example `book-set-last-read-position` at `src/calibre/srv/books.py:235-247`. `conversion_status()` is the endpoint that performs the permanent write, but it omits that authorization boundary. Sequential IDs are exposed to the client as the start response and are therefore readily guessable.
- **Suggested fix:** Store the initiating username and library ID in `JobStatus` when queuing the job. In `conversion_status()`, before aborting, removing, exposing results, or adding the output format, require the same owner (or an explicitly defined administrative authorization) and call `ctx.has_id(rd, db, job_status.book_id)`. Perform the library and authorization checks before `del conversion_jobs[job_id]` so an unauthorized request cannot consume the result.

### Medium — externally queued WebSocket frames and pings can remain unsent indefinitely

- **Files/lines:** `src/calibre/srv/web_socket.py:506-523`, `src/calibre/srv/loop.py:594-609`, `623-624`
- **What goes wrong:** `send_websocket_frame()` and `send_websocket_ping()` append to `control_frames` but do not change the connection's wait state or wake the event loop. If the connection is idle, `set_ws_state()` has selected `READ`, so the event loop blocks in `select()` for readable sockets and never calls `ws_write()` to drain the queued frame. The frame is sent only after unrelated inbound traffic, a timeout, or some other wakeup.
- **Why this is wrong:** `send_websocket_message()` immediately above deliberately sets `self.wait_for = RDWR` and invokes `self.wakeup()` (lines 498-504), which is required for a message queued from outside the current socket event. The frame and ping methods are also public sending APIs and use the same queueing pattern, but omit those steps. The loop only includes a socket in `write_needed` when its `wait_for` is `WRITE` or `RDWR`.
- **Suggested fix:** After appending a frame in both methods, set `self.wait_for = RDWR` and call `self.wakeup()` (ideally through a small shared enqueue helper that holds `cf_lock`).

## Files read

- `src/calibre/srv/ajax.py`
- `src/calibre/srv/auth.py`
- `src/calibre/srv/books.py`
- `src/calibre/srv/cdb.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/convert.py`
- `src/calibre/srv/fts.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/jobs.py`
- `src/calibre/srv/legacy.py`
- `src/calibre/srv/library_broker.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/opds.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/users.py`
- `src/calibre/srv/users_api.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/tests/ajax.py`
- `src/calibre/srv/tests/auth.py`
- `src/calibre/srv/tests/convert.py`
- `src/calibre/srv/tests/http.py`
