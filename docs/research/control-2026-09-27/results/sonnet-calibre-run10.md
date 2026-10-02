# Code review: calibre `src/calibre/srv/`

Repo: https://github.com/kovidgoyal/calibre, pinned commit `7691f4f1a155d799afdfec99e2cdc2716c178402`
Scope: `src/calibre/srv/`

All findings below were independently verified by reading the cited lines directly and, where applicable, by running small scripts against the actual code (`python3 -c "import ast; ast.parse(...)"` for syntax, and standalone reproductions of the unpacking bug).

---

## 1. `loop.py:570` — Python 2 exception syntax, module fails to import

```python
except AttributeError, OSError:
```

`except A, B:` is Python 2 tuple-exception syntax. Under Python 3 this is a hard `SyntaxError`:

```
File "loop.py", line 570
    except AttributeError, OSError:
SyntaxError: multiple exception types must be parenthesized
```

Confirmed with `python3 -c "import ast; ast.parse(open('src/calibre/srv/loop.py').read())"`.

- **What goes wrong / when**: the module fails to import at all under any Python 3 interpreter, not just when this branch executes.
- **Why it's wrong**: calibre's server targets Python 3 (this checkout targets 3.14); this is invalid Python 3 syntax. Every other file in `srv/` imports `calibre.srv.loop` (it defines the `Connection` base class used throughout), so this breaks the entire server module tree.
- **Severity**: high
- **Fix**: `except (AttributeError, OSError):`

## 2. `content.py:358` — same Python 2 exception syntax defect

```python
try:
    q = path_from_root(base, bytes.fromhex(encoded_fname).decode('utf-8'), reject_colon=iswindows)
except ValueError, UnicodeDecodeError:
    raise HTTPNotFound(f'Reader background {encoded_fname} not found')
```

Same `SyntaxError: multiple exception types must be parenthesized` under Python 3, confirmed via `ast.parse`. This breaks import of `content.py`, which defines the book/cover/thumbnail/data-file serving endpoints (`/get/...`, notes, etc.) — i.e. the majority of what an end user does through the content server.

- **Severity**: high
- **Fix**: `except (ValueError, UnicodeDecodeError):`

## 3. `standalone.py:209` — same Python 2 exception syntax defect

```python
try:
    manage_users_cli(opts.userdb, args[1:])
except KeyboardInterrupt, EOFError:
    raise SystemExit(_('Interrupted by user'))
```

Same `SyntaxError` under Python 3, confirmed via `ast.parse`. This breaks import of `standalone.py` (the `calibre-server` executable's entry point, `main()`), and by extension `auto_reload.py`, which does `from calibre.srv.standalone import create_option_parser` at module scope.

- **Severity**: high
- **Fix**: `except (KeyboardInterrupt, EOFError):`

---

## 4. `loop.py:615-616` — wrong loop variable used when closing "close_needed" connections

```python
for s, conn in remove:
    self.log(f'Closing connection because of extended inactivity: {conn.state_description}')
    self.close(s, conn)

for x, conn in close_needed:
    self.close(s, conn)
```

`close_needed` is populated earlier in the same method (inside the connection-scan loop, when `conn.drain_ssl_buffer()` fails and the connection is no longer `ready`) as a list of `(s, conn)` pairs where `s` is that connection's own socket. When actually closing them, the loop correctly unpacks into `x, conn`, but the body then calls `self.close(s, conn)` — reusing the stale `s` left over from the immediately preceding `for s, conn in remove:` loop (whatever socket that loop last bound `s` to, or an earlier unrelated value if `remove` is empty).

- **What goes wrong / when**: happens whenever there is at least one entry in `close_needed` (an SSL connection whose buffer drain failed and is no longer ready) during a `tick()`. `Connection.close(self, s, conn)` does `self.connection_map.pop(s, None); conn.close()`. Because the wrong `s` is passed, the wrong (and possibly still-active) entry gets popped out of `connection_map`, while the entry keyed by `conn`'s real socket is never removed — even though `conn.close()` was just called on it.
- **Why it's wrong**: this corrupts the loop's connection bookkeeping. An unrelated live connection silently disappears from `connection_map` (it will never be polled again — its client hangs), while the actually-closed connection's stale entry remains in the map, where `tick()` will keep trying to operate on a dead socket/connection object on subsequent iterations.
- **Severity**: high
- **Fix**: `self.close(x, conn)`.

## 5. `http_response.py:561` — `is_http1` argument to `finalize_output` is always `False`

```python
output = self.finalize_output(output, data, self.method is HTTP1)
```

`self.method` holds the HTTP method string (`'GET'`, `'HEAD'`, `'POST'`, …); `HTTP1` is the string constant `'HTTP/1.0'` (`calibre.srv.utils.HTTP1`). `self.method is HTTP1` is therefore always `False` — comparing an HTTP method to a protocol-version string can never be true. The correct value, based on how the same flag is used everywhere else in this file (e.g. `simple_response` checks `self.response_protocol is HTTP1` at line 459), is `self.response_protocol is HTTP1`.

- **What goes wrong / when**: inside `finalize_output` (line 713 signature: `def finalize_output(self, output, request, is_http1)`), `is_http1` gates `compressible = ... and not is_http1` and `accept_ranges = ... and not is_http1` (around lines 757-759). Since `is_http1` is always `False` here, a genuine HTTP/1.0 client is still offered gzip compression with chunked transfer-encoding and byte-range support.
- **Why it's wrong**: chunked Transfer-Encoding is an HTTP/1.1-only wire format (RFC 7230 §3.3.1); an HTTP/1.0 client or proxy does not know how to de-chunk a body, so it will receive the literal `<hex-length>\r\n<chunk>\r\n...0\r\n\r\n` framing as if it were the actual entity body — a corrupted response. Range support is likewise offered to a version of the protocol that isn't supposed to get it via this flag.
- **Severity**: high
- **Fix**: `output = self.finalize_output(output, data, self.response_protocol is HTTP1)`

## 6. `http_response.py:582` — response status line hardcodes HTTP/1.1 regardless of the negotiated protocol

```python
buf = [HTTP11 + f' {data.status_code} ' + http.client.responses[data.status_code]]
```

This is in `job_done`, the normal (non-error) response path. Every other place in this file that writes a status line uses `self.response_protocol`: `simple_response` (line ~472: `f'{self.response_protocol} {status_code} ...'`), `send_range_not_satisfiable`, and `send_not_modified` all do this correctly. `job_done` instead hardcodes `HTTP11`.

- **What goes wrong / when**: any client whose request negotiated `self.response_protocol == HTTP1` (e.g. sent `HTTP/1.0`) still receives a status line reading `HTTP/1.1 200 OK`, even though the `Connection`/`Keep-Alive` header logic a few lines above (lines 568-576) correctly branches on the real `self.response_protocol` and behaves as HTTP/1.0.
- **Why it's wrong**: RFC 7230 §3.1.2 requires the status line to state the protocol version the server is actually using to respond; claiming HTTP/1.1 while behaving like HTTP/1.0 (and, combined with finding #5, potentially sending chunked bodies) can cause an HTTP/1.0 client/proxy to apply HTTP/1.1 semantics it does not support.
- **Severity**: medium
- **Fix**: `buf = [self.response_protocol + f' {data.status_code} ' + http.client.responses[data.status_code]]`

## 7. `http_response.py:138` — malformed `Range` header crashes the request instead of being ignored

```python
for brange in byteranges.split(','):
    start, stop = (x.strip() for x in brange.split('-', 1))
```

Only the initial `bytesunit, byteranges = headervalue.split('=', 1)` split (a few lines above) is guarded by `try/except`. This per-range unpack is not. If a range-spec has no `-` in it (e.g. `Range: bytes=abc`, or an empty item from a trailing comma like `Range: bytes=0-10,`), `brange.split('-', 1)` returns a single-element list and the tuple-unpack raises an uncaught `ValueError`.

Reproduced directly:
```
>>> get_ranges('bytes=abc', 100)
Traceback (most recent call last):
  ...
ValueError: not enough values to unpack (expected 2, got 1)
```

- **What goes wrong / when**: any client-supplied `Range` header with a syntactically invalid range-spec. This propagates out of `get_ranges()` (called from `finalize_output`, with no surrounding `try/except` at that call site) up into the connection handling, producing an unhandled exception (turned into a generic 500) instead of a normal response.
- **Why it's wrong**: the function's own docstring says "If this function returns an empty list, it indicates no valid range was found" — i.e. the documented contract is to *skip* invalid ranges, and every other field in the same loop (the `int()` conversions two lines below) is correctly wrapped in `try/except Exception: continue`. Per RFC 7233 §3.1, a `Range` header that is not syntactically valid must be ignored (treated as if absent, serving a normal 200), not fail the request with a server error. This is client-input-triggered, so it's a reachable, remotely-triggerable defect.
- **Severity**: medium
- **Fix**: guard the unpack the same way the rest of the loop is guarded, e.g.:
  ```python
  parts = brange.split('-', 1)
  if len(parts) != 2:
      continue
  start, stop = (x.strip() for x in parts)
  ```

## 8. `cdb.py:226` — recipe-format security check in `/cdb/set-fields` is missing a format the codebase itself treats as equally dangerous

The module defines and uses a shared helper for detecting recipe formats:

```python
def is_recipe_fmt(fmt: str) -> bool:
    fmt = fmt.lower().removeprefix('original_')
    return fmt in ('recipe', 'downloaded_recipe')
```

`cdb_add_book` (line 102) uses it correctly:
```python
if is_recipe_fmt(fmt):
    raise HTTPForbidden('Cannot use the add book interface to add recipe files, as they allow code execution')
```

But `cdb_set_fields`'s handling of `added_formats` (attaching an extra file/format to an *existing* book) reimplements the check inline and incompletely (line 226):
```python
if fmt.lower() in ('recipe', 'original_recipe'):
    raise HTTPForbidden('Cannot use the add book interface to add recipe files, as they allow code execution')
```

- **What goes wrong / when**: this inline check omits `'downloaded_recipe'` (and doesn't generically strip an `original_` prefix the way `is_recipe_fmt` does, so `original_downloaded_recipe` also passes). A user permitted to call `/cdb/set-fields` can attach a `downloaded_recipe`-format payload to a book via this endpoint even though the identical `.recipe`/`.downloaded_recipe` upload is explicitly forbidden one endpoint over, for the stated reason "they allow code execution."
- **Why it's wrong**: it's the same security guard, protecting the same risk (recipe files are executable Python, per calibre's own `recipe_input.py`, whose `file_types = {'recipe', 'downloaded_recipe'}`), reimplemented inconsistently in a second place instead of calling the shared helper — defeating its own stated purpose for one of the two recognized recipe format names.
- **Severity**: high
- **Fix**: replace the inline check with `if is_recipe_fmt(fmt):`.

## 9. `convert.py` — client-controlled `output_fmt` bypasses its own path-traversal sanitization

`JobStatus.__init__` (lines 42-46) sanitizes `output_fmt` before using it to build its bookkeeping path, with an explicit comment stating the intent:
```python
# sanitize output_fmt to prevent path traversal
output_fmt = conversion_data['output_fmt'].replace('/', '').replace('\\', '').lower()
self.output_path = os.path.join(tdir, 'output.' + output_fmt)
```

But `queue_job` (line 187) passes the **raw, unsanitized** `conversion_data['output_fmt']` — taken directly from the client's JSON POST body in `start_conversion` and never validated against the server-advertised output-format list — as the actual argument used to perform the conversion:
```python
job_id = ctx.start_job(
    f'Convert book {book_id} ({fmt})',
    'calibre.srv.convert',
    'convert_book',
    args=(src_file.name, opf_file.name, cover_path, conversion_data['output_fmt'], recs),
    job_done_callback=job_done,
)
```

Inside `convert_book` (line 133), that raw value builds the real output path, after `os.chdir()` into the job's temp directory:
```python
output_path = os.path.abspath('output.' + output_fmt.lower())
plumber = Plumber(path_to_ebook, output_path, log, ...)
```

- **What goes wrong / when**: an authenticated client with write access can call `/conversion/start/{book_id}` with an `output_fmt` value containing `../` sequences (e.g. `"../../../../tmp/pwned"`). `os.path.abspath('output.' + output_fmt.lower())` then resolves to a location outside the job's own temp directory, and the conversion pipeline (`Plumber`/`run()`) writes its converted output there — an arbitrary file write to a server-process-writable location chosen by the client.
- **Why it's wrong**: this directly contradicts the sanitization the code claims to have performed — the comment literally says "sanitize output_fmt to prevent path traversal" — but the sanitized value (`JobStatus.output_path`) is only used for later status bookkeeping (`conversion_status`), never for the value actually handed to `convert_book`, which is the one that matters for where the file lands. `sanitize_conversion_options` in the same file exists specifically to strip dangerous client-supplied options for exactly this class of risk (its docstring calls out path/URL-based options), but `output_fmt` itself isn't run through any such filter before being used as a raw path component.
- **Severity**: high
- **Fix**: sanitize `output_fmt` once (or validate it against the allowed output-format set from `get_conversion_options`/`get_sorted_output_formats`) and use that single sanitized value both for `JobStatus.output_path` and for the value passed into `ctx.start_job(...)` / `convert_book`.

## 10. `jobs.py` — `max_job_time = 0` ("no limit") instead aborts jobs almost immediately

`opts.py` documents the setting as:
> "Maximum amount of time worker processes are allowed to run (in minutes). **Set to zero for no limit.**" (`opts.py` line 81)

```python
self.max_job_time = max(0, opts.max_job_time * 60)   # line 98 — 0 stays 0
...
delta = self.max_job_time - (now - job.start_time)    # lines 204 and 219
if delta <= 0:
    ...   # abort_hanging_jobs(): job.abort_event.set()
           # update_max_block(): self.max_block = 0
```

- **What goes wrong / when**: when an admin sets `max_job_time` to `0` to disable the timeout (as the option's own help text instructs), `delta` becomes `0 - elapsed`, which is `<= 0` as soon as any measurable time has passed since the job started (i.e. almost immediately). `abort_hanging_jobs()` then marks the job's `abort_event`, and `update_max_block()` sets `self.max_block = 0` (causing the manager to busy-poll). In practice, setting the value meant to mean "unlimited" causes jobs (book conversion, adding books, etc.) to be aborted right after they start.
- **Why it's wrong**: this is the opposite of the documented behavior ("Set to zero for no limit"). `0` is never special-cased anywhere in the delta arithmetic.
- **Severity**: high (silently breaks a documented, user-facing configuration option; every background job is affected)
- **Fix**: special-case zero, e.g. skip the timeout checks entirely when `self.max_job_time == 0`:
  ```python
  if self.max_job_time and delta <= 0:
      ...
  ```
  (in both `update_max_block` and `abort_hanging_jobs`), or store `None`/a sentinel for "no limit" instead of `0`.

## 11. `jobs.py:235` — wrong attribute logged for job name in callback-error message

```python
self.log.error(f'Error running callback for job: {job.name}:\n{traceback.format_exc()}')
```

`Job.__init__` sets `self.job_name = start_event.name` (the human-readable name passed to `start_job`, e.g. `"Convert book 7 (EPUB)"`), while `self.name` is the inherited `threading.Thread.name`, set via `Thread.__init__(self, name=f'JobsMonitor{start_event.job_id}')`. Line 235 logs `job.name` (e.g. `"JobsMonitor42"`), not `job.job_name`, unlike the near-identical log line 4 lines later (line 239) which correctly uses `job.job_name`.

- **What goes wrong**: when a job's completion callback raises, the resulting error log identifies the job only by its internal thread name (`JobsMonitor42`) rather than its human-readable description, making the log line useless for figuring out which job's callback failed.
- **Severity**: low (log-message correctness only; no functional/behavioral impact)
- **Fix**: `self.log.error(f'Error running callback for job: {job.job_name}:\n{traceback.format_exc()}')`

---

## Not reported as defects (checked and ruled out)

- `pool.py` `ThreadPool.stop()`'s `break` on `Full` when sending shutdown sentinels could in theory strand some workers without a sentinel, but requires the request queue to already be saturated at shutdown time (default capacity 1000 vs. 10 workers) and workers are daemon threads, so this doesn't block process exit — not confident enough to call it a real defect.
- `users_api.py`'s password-change comparison uses `!=` rather than constant-time comparison, but the whole user-credential design in this codebase already stores/compares plaintext passwords elsewhere (documented as required for HTTP Digest auth), so this isn't a newly-introduced inconsistency.
- `auth.py`'s `AuthController.check()` does a non-constant-time `==` comparison of passwords — a timing-attack surface in principle, but this is consistent with the rest of the digest/basic-auth design in the same file (digest auth itself requires knowing the plaintext password to compute HA1) and I'm not confident this is a defect distinct from the scheme's known, documented trade-offs (see the class's own docstring about accepted vulnerabilities).
- `http_request.py`'s chunk-size parsing (`int(line.strip(), 16)`) doesn't strip RFC 7230 chunk-extensions (`;name=value`) before parsing, so a chunked request using extensions would be rejected as a malformed chunk size rather than accepted with the extension ignored. This is a minor spec-conformance gap, not a functional break (extensions are rare and RFC 7230 only says implementations "SHOULD ignore" unrecognized extensions), so I'm not confident enough to list it as a defect.

---

## Files read

- src/calibre/srv/auth.py
- src/calibre/srv/utils.py
- src/calibre/srv/http_request.py
- src/calibre/srv/http_response.py
- src/calibre/srv/loop.py
- src/calibre/srv/web_socket.py
- src/calibre/srv/users.py
- src/calibre/srv/users_api.py
- src/calibre/srv/manage_users_cli.py
- src/calibre/srv/cdb.py
- src/calibre/srv/legacy.py
- src/calibre/srv/legacy_book_details.py
- src/calibre/srv/last_read.py
- src/calibre/srv/changes.py
- src/calibre/srv/content.py
- src/calibre/srv/ajax.py
- src/calibre/srv/opds.py
- src/calibre/srv/books.py
- src/calibre/srv/code.py
- src/calibre/srv/metadata.py
- src/calibre/srv/render_book.py
- src/calibre/srv/convert.py
- src/calibre/srv/fts.py
- src/calibre/srv/routes.py
- src/calibre/srv/handler.py
- src/calibre/srv/library_broker.py
- src/calibre/srv/jobs.py
- src/calibre/srv/pool.py
- src/calibre/srv/auto_reload.py
- src/calibre/srv/opts.py
- src/calibre/srv/standalone.py
- src/calibre/srv/embedded.py
- src/calibre/srv/bonjour.py
- src/calibre/srv/pre_activated.py
- src/calibre/srv/errors.py

Context files read outside the scope (to verify call sites / cross-references):
- src/calibre/ebooks/conversion/plugins/recipe_input.py (confirms `downloaded_recipe` is a real, distinct recipe format)
- src/calibre/db/cache.py (confirms `add_format`/`copy_format_to` do no format-based validation)
- src/calibre/utils/filenames.py (`path_from_root`)
- src/calibre/gui2/ui.py (library-broker locking call sites)
- src/calibre/srv/tests/loop.py (existing test coverage for `JobsManager`)
- src/calibre/utils/logging.py (`Log` interface used by `pool.py`)

All syntax-error findings (items 1-3) were independently confirmed by running `python3 -c "import ast; ast.parse(open(<file>).read())"` against each file. The `Range`-header crash (item 7) was independently confirmed by extracting and running the relevant code in a standalone script. All other line-number citations were verified with `grep -n` against the checkout immediately before writing this report.
