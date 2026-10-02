model: gpt-5.6-terra
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:28:04 UTC; finished 2026-09-28 23:31:04 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Calibre `src/calibre/srv/` review

## 1. A conversion status request authorizes neither the job nor its book

- **File and line:** `src/calibre/srv/convert.py:220-257`
- **Severity:** high

`conversion_status()` looks up a process-global job by its predictable numeric
ID and acts on it before establishing that the requesting user owns the job or
may access its book.  In particular, an authenticated read/write user can send
`?abort_job=1` for another user's still-running job at lines 226-230, even when
that job belongs to a different library.  Once the job is complete, any
read/write user who can select the same library can consume the result at lines
242-254; `db.add_format(job_status.book_id, ...)` writes the converted format
to the original book without the `ctx.has_id()` restriction check that
`start_conversion()` performs at lines 204-206.

This contradicts the access-control model in `Context.has_id()`
(`src/calibre/srv/handler.py:91-98`), which checks a user's library
restriction before a book operation.  `conversion_status()` stores no creator
identity in `JobStatus` and never calls that check.  For example, two
non-readonly users sharing a library but restricted to disjoint book sets can
use a guessed job ID to cancel each other's conversion; after completion, one
can cause a format to be added to a book outside their allowed set and retrieve
the job log/traceback.

**Suggested fix:** Record the submitting username in `JobStatus`.  Require the
same user when looking up a job (or implement an explicit privileged sharing
policy), and before aborting, reading a completed result, or adding its format,
load the job's library and require both the matching library ID and
`ctx.has_id(rd, db, job_status.book_id)`.

## 2. Starting another conversion can delete files needed by an active conversion

- **File and line:** `src/calibre/srv/convert.py:75-81, 190-192`
- **Severity:** medium

`expire_old_jobs()` removes every status entry that has not been polled for 360
seconds; it does not exclude entries whose `running` flag is still true.  It
then calls `JobStatus.cleanup()`, which recursively removes that job's temporary
directory.  `queue_job()` calls this function every time a new conversion is
started.

An active conversion that takes more than six minutes and whose client has not
polled its status can therefore have its temporary directory deleted simply
because another conversion starts.  That directory contains the copied input,
OPF, cover, status file, and output path created in `queue_job()` at lines
166-187.  The worker invoked by `convert_book()` uses those paths and changes
into that directory (`src/calibre/srv/convert.py:127-135`), so the job can fail
or finish with an unlinked output which can no longer be collected.  Its status
is also removed, making the result unavailable.

**Suggested fix:** Only expire completed jobs, for example by filtering on
`not job_status.running`; retain running jobs until their completion callback
marks them complete, then apply the inactivity TTL.  Alternatively track worker
activity separately and never clean the directory before the worker has exited.

## 3. The configured header limit only limits one line, leaving total headers unbounded

- **File and line:** `src/calibre/srv/http_request.py:346-356` and
  `src/calibre/srv/http_request.py:273-284`
- **Severity:** medium

The advertised `max_header_line_size` is applied by `readline()` to the current
`Accumulator`, which is emptied as soon as one CRLF-terminated line is returned.
`parse_header_line()` then accepts an unlimited number of such individually
valid lines into `HTTPHeaderParser.hdict`; there is no count or aggregate-byte
limit before `finalize_headers()` is reached.

The server option itself describes the setting as the maximum single-header
size (`src/calibre/srv/opts.py:53-55`), but accepting arbitrarily many headers
means a peer can send an unbounded header block on one connection and grow the
header dictionary/lists until memory is exhausted.  The per-line 8 KiB default
does not constrain that attack.

**Suggested fix:** Maintain a total header-byte counter and/or a header-count
counter in `HTTPHeaderParser`/`HTTPRequest`, reject the request with 431 or 400
when a bounded aggregate limit is exceeded, and make the aggregate limit
configurable if needed.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/auto_reload.py`
- `src/calibre/srv/bonjour.py`
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
- `src/calibre/srv/opts.py`
- `src/calibre/srv/opds.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/standalone.py`
- `src/calibre/srv/users.py`
- `src/calibre/srv/users_api.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/web_socket.py`
