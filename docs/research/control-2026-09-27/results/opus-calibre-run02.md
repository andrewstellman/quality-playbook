# Code review: calibre `src/calibre/srv/` (pinned 7691f4f1)

Reviewer: opus, run 02. Checkout: `/tmp/control/calibre` (read-only). I checked some findings by running the relevant functions in isolation, copied out of the checkout into the work directory. The whole package can't be imported here.

---

## 1. A negative chunk size bypasses `max_request_body_size`

- **File/line:** `src/calibre/srv/http_request.py:426-437` (`read_chunk_length`), plus `read_chunk` at 439-443
- **What goes wrong:** The chunk size is parsed with `int(line.strip(), 16)`. Python's `int` accepts a sign, so a chunk-size line of `-100000` parses to a negative number.
  - The size check `bytes_read[0] + chunk_size + 2 > self.max_request_body_size` passes.
  - `read_chunk` is then entered with `end = buf.tell() + chunk_size`, which is before the current position. `self.read()` returns True immediately.
  - `bytes_read[0] += chunk_size` then *decreases* the running total.
  - A client can repeat "negative chunk, then a large real chunk" as many times as it likes. The request body has no size limit, and it is spooled to disk in `tdir` through `SpooledTemporaryFile`.
  - `int(..., 16)` also accepts `0x` prefixes and `_` separators. RFC 7230 §4.1 does not allow either.
- **Checked:** `int('-5', 16) == -5` and `int(' 0x1_0 ', 16) == 16`.
- **Why it is wrong:** The limit exists to cap the request body (`Chunked request is larger than ...`). RFC 7230 defines `chunk-size = 1*HEXDIG`, so a negative or prefixed size is malformed and should get a 400.
- **Severity:** high. An unauthenticated client can fill the disk or use unbounded resources before auth or routing runs.
- **Fix:** Validate the chunk-size token before calling `int`: strip any `;ext` part, then require `re.fullmatch(rb'[0-9a-fA-F]+', token)`. Also reject `chunk_size < 0` defensively.

## 2. The HTTP/1.0 check compares the method, not the protocol, so HTTP/1.0 clients get chunked, gzip and range responses

- **File/line:** `src/calibre/srv/http_response.py:561`
- **Code:** `output = self.finalize_output(output, data, self.method is HTTP1)`
- **What goes wrong:** `self.method` is a verb such as `'GET'`, and `HTTP1` is `'HTTP/1.0'`, so `is_http1` is always False. `finalize_output` uses `is_http1` to turn off compression, `Accept-Ranges` and chunked output (lines 757 and 759). For an HTTP/1.0 request:
  - a compressible response is sent with `Transfer-Encoding: chunked`, which HTTP/1.0 does not support;
  - output with no length (`GeneratedOutput`) is also chunked.
  - The status line is always `HTTP/1.1` (line 582), so the client sees chunked framing it can't decode.
- **Why it is wrong:** The `is_http1` parameter only makes sense as "the response protocol is 1.0". `simple_response` compares `self.response_protocol is HTTP1` correctly at line 460. The method/protocol mix-up is clearly unintended.
- **Severity:** medium. Responses to HTTP/1.0 clients (some proxies, simple tools) come out garbled whenever they send `Accept-Encoding: gzip`.
- **Fix:** `self.finalize_output(output, data, self.response_protocol is HTTP1)`.

## 3. A Range request on compressible content sends both `Transfer-Encoding: chunked` and `Content-Length`, with a body that isn't chunked

- **File/line:** `src/calibre/srv/http_response.py:751-801`
- **When it happens:** The file is served from the filesystem (`accept_ranges=True`) and is compressible (text/*, JS, JSON, SVG, XML/OPF, and 1024 bytes or larger). The client sends `Accept-Encoding: gzip` and a valid `Range`. An example is a download manager resuming `/get/TXT/<id>`.
- **What goes wrong:**
  - `ranges` is still computed (line 760), because it depends on `output.accept_ranges`, not on `compressible`.
  - gzip is skipped because of `compressible and not ranges` (784).
  - `Content-Length` isn't set at 790 (`not compressible` is False).
  - Line 793 (`if compressible or ...`) adds `Transfer-Encoding: chunked`.
  - Lines 796-801 then set `Content-Length`/`Content-Range` and status 206.
  - The body is written raw by `write_buf`/`write_ranges`, not chunk-encoded.
- **Result:** The response carries both `Transfer-Encoding: chunked` and `Content-Length`. RFC 7230 §3.3.3 says Transfer-Encoding wins, so the client tries to parse the raw bytes as chunks and the download is corrupted or fails.
- **Why it is wrong:** The code already treats compression and ranges as mutually exclusive (`compressible and not ranges`, `not compressible and not ranges`). Line 793 misses that case. RFC 7230 §3.3.2 says a sender must not send Content-Length together with Transfer-Encoding.
- **Severity:** medium.
- **Fix:** Set `compressible = False` when `ranges` is non-empty, before headers are emitted. Or change line 793 to `if (compressible and not ranges) or output.content_length is None:`.

## 4. Malformed or negative `Range` values cause a 500 or an invalid 206

- **File/line:** `src/calibre/srv/http_response.py:137-161` (`get_ranges`)
- **Three cases, each checked by running `get_ranges` in isolation with `content_length=10`:**
  - `Range: bytes=5` (no dash): `start, stop = (x.strip() for x in brange.split('-', 1))` raises `ValueError: not enough values to unpack`. Nothing inside the function catches it. It escapes `finalize_output`/`job_done` and the loop turns it into a 500.
  - `Range: bytes=--5`: stop is `'-5'`, and `int('-5')` gives `Range(start=15, stop=9, size=-5)`. The client gets `206` with `Content-Length: -5` and `Content-Range: bytes 15-9/10`.
  - `Range: bytes=-0`: gives `Range(10, 9, 0)`, a 206 with a zero-length range. Also, for an empty file, `bytes=-5` gives `Range(0, -1, 0)`.
- **Why it is wrong:** The function's docstring says that failing to find a valid range means an empty list or None. RFC 7233 §3.1 says an invalid Range should be ignored (return 200). §2.1 says a zero suffix length, or a range on an empty representation, is unsatisfiable (416).
- **Severity:** medium. Any client can trigger a 500, and the server can emit a malformed 206 with negative `Content-Length`.
- **Fix:**
  - Use `start, sep, stop = brange.partition('-')` and skip the entry if `sep` is empty.
  - Parse `start`/`stop` only as non-negative decimal digits (`isdigit()`).
  - For suffix ranges, skip entries where `stop <= 0` or `content_length == 0`.

## 5. `ServerLoop.tick` closes SSL connections using the wrong loop variable

- **File/line:** `src/calibre/srv/loop.py:615-616`

```python
for x, conn in close_needed:
    self.close(s, conn)
```

- **What goes wrong:** The loop variable is `x`, but `s` is passed. `s` is left over from the earlier loops: the last connection key seen in `self.connection_map.items()`, or the last entry in `remove`.
  - `close()` does `self.connection_map.pop(s, None)`, which removes an unrelated live connection from the map. Its socket stays open (leaked) and it is never serviced again.
  - The connection that really needed closing stays in `connection_map` with a closed socket. On the next `select` that triggers the bad-fd recovery path.
  - This happens on SSL servers whenever `drain_ssl_buffer` marks a connection not ready, i.e. on a client EOF or SSL error.
- **Why it is wrong:** `close_needed` is built as `(s, conn)` pairs (line 605) so that each connection is closed under its own key.
- **Severity:** medium (SSL servers only).
- **Fix:** `for x, conn in close_needed: self.close(x, conn)`.

## 6. `BanList.failed` never expires old entries, so failures never reset and bans come back after a single failure

- **File/line:** `src/calibre/srv/auth.py:53-60`
- **What goes wrong:** The purge loop iterates `reversed(self.items)`, which starts from the newest entry. The newest entry is the key that was just re-inserted with `now`, so `now - previous_fail > self.interval` is False and the loop `break`s at once. Nothing is ever removed. As a result:
  - the dict grows without bound (one entry per remote address that ever failed);
  - fail counts accumulate forever. Once an address reaches `max_failures_before_ban`, the ban lapses after `interval`, but the count is never reset. The next single failed login, even days later, bans it again.
- **Checked:** With `ban_time=1min, max=2`: one failure at t=0, then one at t=1000s. The t=0 entry was not purged, and `is_banned('a')` returned True after only one new failure.
- **Why it is wrong:** The purge is meant to drop entries older than `interval`. OrderedDict insertion order is oldest-first, so the scan must start from the oldest end to hit expired entries before the `break`.
- **Severity:** low-medium. Legitimate users are re-banned after one typo, and memory grows without limit.
- **Fix:** Iterate `for old in self.items:` (oldest first), keeping the `break` on the first unexpired entry.

## 7. A valid digest login with a stale nonce is counted as a failed login

- **File/line:** `src/calibre/srv/auth.py:296-303`
- **What goes wrong:** When the digest response is correct but the nonce is stale, `nonce_is_stale` is True and the `return` is skipped. Execution then falls through to `log_msg = 'Failed login attempt ...'` and `self.ban_list.failed(ban_key)`.
  - Browsers keep reusing an old nonce until they are challenged with `stale=true`, so every nonce expiry (MAX_AGE_SECONDS) counts as a failed attempt for a legitimate user.
  - Combined with finding 6, these counts never reset, so users with correct passwords can end up banned.
- **Why it is wrong:** The code already tells the two cases apart: it sends `stale="true"`, which RFC 2617 §3.2.1 says means the credentials were valid and the client should retry silently. That is not an authentication failure.
- **Severity:** low-medium.
- **Fix:** Only call `ban_list.failed` and set `log_msg` when the credentials didn't validate. For example, when the nonce is stale, skip the failure branch and go straight to the challenge.

## 8. `Expect: 100-continue` requests lose `X-Forwarded-For`

- **File/line:** `src/calibre/srv/http_request.py:396-399`
- **What goes wrong:** On the `100-continue` path the function `return`s before line 399 (`self.forwarded_for = inheaders.get('X-Forwarded-For')`). `forwarded_for` stays None (reset in `connection_ready`). `RequestData.forwarded_for` and the access-log entry (`http_response.py:605`) therefore lose the real client IP for those requests. curl, for example, sends `Expect: 100-continue` for uploads over 1 KB.
- **Why it is wrong:** The non-Expect path clearly intends every request to record `X-Forwarded-For`.
- **Severity:** low. It affects logging and diagnostics for proxied uploads.
- **Fix:** Move the `self.forwarded_for = ...` assignment above the `Expect` check.

## 9. `/data-files/remove` can delete any file in the book folder, not just data files

- **File/line:** `src/calibre/srv/content.py:659-672`
- **What goes wrong:** `relpaths` from the request body is passed directly to `db.remove_extra_files(book_id, relpaths, permanent=True)`.
  - The backend (`db/backend.py:2324`) only checks that each path stays inside the book directory.
  - So `["metadata.opf", "cover.jpg", "Title - Author.epub"]` permanently deletes the book's format and cover files behind the database's back, and the DB then points at missing files.
- **Why it is wrong:** The endpoint is the data-files remover. Its sibling `upload_data_files` forces the `DATA_DIR_NAME/` prefix (line 637), and `get_data_file`/the list response are limited to `DATA_FILE_PATTERN`.
- **Severity:** low-medium. It needs write access, but it bypasses the DB's format and cover bookkeeping and is permanent.
- **Fix:** Reject or filter any relpath that doesn't start with `DATA_DIR_NAME + '/'`. Or intersect the list with `{e.relpath for e in db.list_extra_files(book_id, pattern=DATA_FILE_PATTERN)}`.

## 10. `Accept-Ranges: bytes` is sent for responses that don't support ranges

- **File/line:** `src/calibre/srv/http_response.py:759`
- **What goes wrong:** `accept_ranges = not compressible and output.accept_ranges is not None and ...`. `output.accept_ranges` is always a bool (True or False, never None), so this test is always true. Dynamic output (`dynamic_output` sets `accept_ranges = False`) and `GeneratedOutput` still advertise `Accept-Ranges: bytes`. Range requests for them are then silently ignored (line 760 honours `output.accept_ranges`).
- **Why it is wrong:** The intent is clearly to advertise ranges only when the output supports them, per RFC 7233 §2.3.
- **Severity:** low.
- **Fix:** Use `output.accept_ranges` (truthiness) instead of `is not None`.

---

## Considered and not reported

- The status line is always `HTTP/1.1`. RFC 7230 allows this.
- WebSocket close codes 1012-1014 are rejected. RFC 6455 doesn't define them.
- `parse_http_list`/`parse_http_dict` are broken for bytes input, but no caller in scope passes bytes.
- `None >= int` in the `compressible` computation for `GeneratedOutput`. No in-scope handler returns a generator.
- 408 sent while a slow job is in the WAIT state. This may be intended.

## Files read

- `src/calibre/srv/http_request.py` (full)
- `src/calibre/srv/http_response.py` (full)
- `src/calibre/srv/utils.py` (full)
- `src/calibre/srv/loop.py` (full)
- `src/calibre/srv/web_socket.py` (full)
- `src/calibre/srv/auth.py` (full)
- `src/calibre/srv/routes.py` (full)
- `src/calibre/srv/handler.py` (full)
- `src/calibre/srv/errors.py` (full)
- `src/calibre/srv/users.py` (full)
- `src/calibre/srv/content.py` (lines 260-450, 580-673, plus a grep of its definitions)
- `src/calibre/srv/opts.py` (grep of option defaults)
- `src/calibre/srv/tests/http.py` (grep only)
- `src/calibre/utils/filenames.py` (`path_from_root`)
- `src/calibre/db/backend.py` (`remove_extra_files`, `add_extra_file`)
- `src/calibre/db/cache.py` (`add_extra_files`, `remove_extra_files`)
