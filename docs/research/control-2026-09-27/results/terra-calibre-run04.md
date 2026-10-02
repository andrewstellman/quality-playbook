model: gpt-5.6-terra
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:34:08 UTC; finished 2026-09-28 23:37:01 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Calibre `src/calibre/srv/` review

Reviewed commit `7691f4f1a155d799afdfec99e2cdc2716c178402`.

## Findings

### High — `max_job_time=0` immediately aborts jobs instead of disabling the limit

- **File/line:** `src/calibre/srv/jobs.py:98`, `src/calibre/srv/jobs.py:198-221`
- **Trigger:** Configure the documented `max_job_time` setting to `0`, then start any worker-process job such as book rendering or conversion.
- **What goes wrong:** `opts.py` documents zero as “no limit,” but `JobsManager` stores zero as the timeout. Immediately after launching a job, `update_max_block()` calculates `0 - elapsed`, sets `max_block` to zero, and the event loop calls `abort_hanging_jobs()`, which sets the job's abort event. Thus jobs are aborted nearly immediately whenever the operator asks for no time limit.
- **Why this is wrong:** `src/calibre/srv/opts.py:79-81` explicitly says “Set to zero for no limit.” The code at `jobs.py:204-206` and `219-221` instead treats zero as already expired.
- **Severity:** High
- **Suggested fix:** Represent an unlimited timeout as `None` (or skip timeout processing when `self.max_job_time == 0`) in both `update_max_block()` and `abort_hanging_jobs()`.

### High — Any write-enabled user can abort or finalize another user's conversion job, including a book outside their restriction

- **File/line:** `src/calibre/srv/convert.py:220-257`
- **Trigger:** User A starts a conversion. A different authenticated, write-enabled user who can guess or observe its sequential `job_id` requests `/conversion/status/<job_id>?abort_job=1`, or waits for completion and requests `/conversion/status/<job_id>`.
- **What goes wrong:** The status endpoint looks up the process-wide `conversion_jobs` entry solely by `job_id`. While it is running, any caller can abort it (`:228-229`). When it has completed, any caller selecting the same library can cause `db.add_format(job_status.book_id, ...)` (`:243-252`), even if that caller is restricted from the source book. The result also exposes the other user's conversion traceback/log.
- **Why this is wrong:** Starting a conversion explicitly checks access to the requested book with `ctx.has_id(rd, db, book_id)` at `:203-206`. `conversion_status()` has no equivalent book-access or submitter check before it aborts the shared job or writes its output. `needs_db_write=True` only checks whether the account is readonly; `Context.check_for_write_access()` does not enforce per-book restrictions.
- **Severity:** High
- **Suggested fix:** Store the submitting username and library/book identity in `JobStatus`. In `conversion_status()`, require the same submitter (or an explicit administrator capability), validate `ctx.has_id(rd, db, job_status.book_id)` before both status/abort and finalization, and do those checks before deleting the job entry.

### Medium — Invalid `Range` values can either crash response processing or produce an invalid 206 response

- **File/line:** `src/calibre/srv/http_response.py:137-161`
- **Trigger:** Request a range-capable resource with `Range: bytes=0` (no dash), or `Range: bytes=-0`.
- **What goes wrong:** For `bytes=0`, unpacking `brange.split('-', 1)` at `:138` raises `ValueError` outside the function's error handling, rather than returning the documented empty/no-range result. For `bytes=-0`, `stop` is converted to `0` and the code constructs `Range(content_length, content_length - 1, 0)`. The response layer treats that as a real range and emits `206 Partial Content` with an invalid, inverted `Content-Range`, instead of treating the range as unsatisfiable.
- **Why this is wrong:** The function's own docstring (`:123-125`) specifies that no valid range is represented by an empty list. A zero-length suffix range does not identify any byte and cannot form the `start <= end` range emitted later by `finalize_output()`.
- **Severity:** Medium
- **Suggested fix:** Catch malformed range-spec splitting and continue/return an empty result. Reject suffix lengths less than or equal to zero, and only append ranges whose computed size is positive and whose start is no greater than stop.

### Low — The chunked request reader rejects valid chunk extensions and trailers

- **File/line:** `src/calibre/srv/http_request.py:420-459`
- **Trigger:** Send a valid HTTP/1.1 chunked request such as `4;foo=bar\r\ntest\r\n0\r\nX-Trace: x\r\n\r\n`.
- **What goes wrong:** `read_chunk_length()` passes the entire chunk-size line to `int(..., 16)` at `:426`, so a legal `;` extension produces `400`. Even without an extension, after the zero-sized final chunk the state machine calls `read_chunk_separator(..., last=True)` and requires the next line to be an immediate blank CRLF (`:434-435`, `:445-459`); valid trailer fields are rejected as “Chunk does not have trailing CRLF.”
- **Why this is wrong:** HTTP chunked framing permits optional chunk extensions and an optional trailer section between the final zero-sized chunk and the terminating empty line. These are legal request encodings, so rejecting them breaks compliant clients/proxies.
- **Severity:** Low
- **Suggested fix:** Parse the size portion before the first semicolon, and add a final-chunk trailer-reading state that consumes header lines until the terminating blank line (while applying the existing header size limits).

## Files read

- `src/calibre/srv/auth.py`
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
- `src/calibre/srv/last_read.py`
- `src/calibre/srv/library_broker.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/opts.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/users.py`
- `src/calibre/srv/users_api.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/tests/auth.py`
- `src/calibre/srv/tests/convert.py`
- `src/calibre/srv/tests/http.py`
- `src/calibre/srv/tests/loop.py`
