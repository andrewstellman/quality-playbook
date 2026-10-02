model: gpt-5.6-terra
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:37:19 UTC; finished 2026-09-28 23:40:12 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Calibre `src/calibre/srv/` review

## Findings

### 1. Closed TLS connections remove the wrong connection-map entry

- **File / line:** `src/calibre/srv/loop.py:615-616`
- **Severity:** medium
- **What goes wrong:** In an SSL-enabled server, when `drain_ssl_buffer()` discovers that a connection has closed, it is appended to `close_needed` with its own socket descriptor (`x`). The subsequent loop closes the `conn` object but passes the stale `s` variable instead of `x` to `self.close()`. `ServerLoop.close()` removes only the key it is passed, then closes the supplied connection. With two or more connections, this can remove a different live connection from `connection_map` while leaving the now-closed connection mapped. The live connection then stops receiving events; the closed descriptor remains in the map and can make later select/event handling fail or act on a reused descriptor.
- **Why it is wrong:** `close_needed.append((s, conn))` at line 605 preserves the correct descriptor specifically for this deferred close. `ServerLoop.close(s, conn)` at lines 705-707 requires that descriptor to remove the corresponding map entry, but line 616 uses the unrelated loop variable left by the preceding iteration.
- **Suggested fix:** Change the loop to `for s, conn in close_needed: self.close(s, conn)` (or call `self.close(x, conn)`).

### 2. `Accept-Encoding: gzip;q=0` still causes a gzip response

- **File / line:** `src/calibre/srv/utils.py:232-248`, consumed by `src/calibre/srv/http_response.py:752-789`
- **Severity:** medium
- **What goes wrong:** A client that explicitly rejects gzip with `Accept-Encoding: gzip;q=0` receives a `Content-Encoding: gzip` response whenever compression is otherwise enabled. This can make a response unusable for clients that do not decode gzip and deliberately set quality zero.
- **Why it is wrong:** `sort_q_values()` retains entries with quality `0.0` and returns only their tokens. `acceptable_encoding()` iterates those tokens and returns `gzip` without observing the associated quality; `finalize_output()` treats that truthy result as permission to gzip the body. HTTP quality zero denotes an unacceptable coding.
- **Suggested fix:** Preserve quality values until selection and ignore entries whose quality is zero (also make wildcard handling explicit if it is intended).

### 3. Empty responses can be labelled as invalid gzip streams

- **File / line:** `src/calibre/srv/http_response.py:184-200`, reached from `src/calibre/srv/http_response.py:752-789`
- **Severity:** low
- **What goes wrong:** With `compress_min_size=0`, a GET for an empty compressible response with `Accept-Encoding: gzip` is labelled `Content-Encoding: gzip`, but the generated body lacks the mandatory gzip header. `compress_readable_output()` writes `gzip_prefix()` only inside the loop after it reads non-empty source data; for an empty source it emits only the deflate flush/trailer.
- **Why it is wrong:** `finalize_output()` allows zero-length output through the compression condition (`output.content_length >= opts.compress_min_size`) and advertises gzip at line 785. A gzip-coded response must begin with the header produced by `gzip_prefix()`, which the empty-input path never yields.
- **Suggested fix:** Yield `gzip_prefix()` before the read loop, or add it to the final yielded bytes when `prefix_written` is false. Alternatively, do not apply gzip to an empty response.

### 4. A positioned file-like WebSocket message is silently truncated

- **File / line:** `src/calibre/srv/web_socket.py:211-229`
- **Severity:** medium
- **What goes wrong:** `MessageWriter` supports a file-like object and intentionally starts at its current position. For a positioned buffer, it calculates `self.size` as the remaining byte count (lines 212-215) but compares that count to the *absolute* current offset at line 225. If the starting offset is sufficiently far into the file, the first partial frame is marked final and `self.exhausted` becomes true, dropping all remaining data. For example, a 500-byte buffer positioned at 300 with `chunk_size=150` has 200 bytes remaining: after sending 150 bytes the cursor is 450, and `200 > 450` is false, so the remaining 50 bytes are never framed.
- **Why it is wrong:** The public method `send_websocket_message()` documents that `buf` is a file-like object and delegates to `MessageWriter`; a file object's current position is therefore a supported input. The constructor explicitly preserves that position, but the final-frame calculation mixes relative and absolute quantities.
- **Suggested fix:** Record the absolute end position (for example `self.end = buf.tell()` after seeking to EOF) and use `self.end > buf.tell()`, or compare bytes read against the original remaining size.

### 5. A zero-length suffix range produces an invalid 206 response

- **File / line:** `src/calibre/srv/http_response.py:152-161`, used at `src/calibre/srv/http_response.py:796-801`
- **Severity:** low
- **What goes wrong:** `Range: bytes=-0` on a non-empty file produces `Range(content_length, content_length - 1, 0)`. The response path considers that a valid range and emits `206 Partial Content` with an impossible `Content-Range` such as `bytes 100-99/100` and zero length, rather than treating it as unsatisfiable.
- **Why it is wrong:** The range parser’s own contract says an empty range list means no valid range, and the response path uses that condition to return 416. A suffix range length of zero selects no bytes, but line 161 appends it as a valid range with start greater than stop, violating the range representation used at line 800.
- **Suggested fix:** Reject non-positive suffix lengths before appending (`if stop <= 0: continue`), allowing the existing empty-list/416 handling to run.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/errors.py`
- `src/calibre/srv/fts.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/jobs.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/opts.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/tests/auth.py`
- `src/calibre/srv/tests/http.py`
- `src/calibre/srv/tests/web_sockets.py`
