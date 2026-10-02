# Code review: aiohttp `aiohttp/` package (pinned e11d2836203a21bec59095498e578d37801027e7)

Reviewer: opus, run09. Checkout `/tmp/control/aiohttp` (read-only). Scratch scripts ran from `/tmp/control-work/opus-aiohttp-run09/` against the pure-Python code paths, using the `/tmp/aiohttp-venv` interpreter.

Every defect below except #9 was reproduced with a small script. The observed output is quoted in each entry.

---

## 1. The `_charset_` form-data field breaks multipart parsing: the delimiter line is never consumed

- **File/line:** `aiohttp/multipart.py` 802-816 (`MultipartReader.next`)
- **What goes wrong:** When the first form-data part is named `_charset_`, the code does two things:
  1. It reads at most 32 bytes with `part.read_chunk(32)`.
  2. It calls `self.fetch_next_part()` directly.

  It never drains the `_charset_` part and never calls `_read_boundary()`. So `_read_headers()` starts on the `--boundary` delimiter line and treats it as a header line. What happens next depends on the boundary:
  - **Boundary without a colon** (e.g. `short`): `InvalidHeader: b'--short'` is raised, so `request.post()` fails.
  - **Boundary longer than 30 characters:** `read_chunk(32)` → `_read_chunk_from_stream(32)` hits `assert size >= self._boundary_len` (multipart.py 450-452) and raises `AssertionError`. Browser boundaries are this long, e.g. Chrome's `----WebKitFormBoundary7MA4YWxkTrZu0gW`: 40 bytes with the `--` prefix, so `_boundary_len` is 42.
  - **Boundary containing a colon** (e.g. `:`, the one used in the existing tests `test_read_form_default_encoding` / `test_read_form_invalid_default_encoding`): it only appears to work because `--:` happens to parse as a header named `--`. Reproduced: the next part's headers come back as `{'--': '', 'Content-Disposition': 'form-data; name="a"'}`.
- **Reproduced:**
  - `short` → `InvalidHeader 400 ... Invalid HTTP header: b'--short'`
  - WebKit-style boundary → `AssertionError Chunk size must be greater or equal than boundary length + 2`
- **Why wrong:** The code cites RFC 7578 §4.6, which says `_charset_` supplies the default charset. It is not meant to corrupt parsing of the rest of the body. `web_request.BaseRequest.post()` (web_request.py 803-816) goes through this path, so a browser form with a hidden `_charset_` input makes the handler fail (500/400).
- **Severity:** high. It is triggered by ordinary browser input, and `request.post()` fails outright.
- **Fix:**
  - Read the charset part fully, capped: loop over `read_chunk()` with a size ≥ `_boundary_len`, or use `await part.read()` with a length check.
  - Then call `await self._read_boundary()` (or `_maybe_release_last_part()` + `_read_boundary()`) before `fetch_next_part()`.
  - Also check whether `_read_boundary` set `_at_eof`, in case `_charset_` was the only part.

## 2. `StreamReader.readuntil()` misses a multi-byte separator that spans buffered chunks

- **File/line:** `aiohttp/streams.py` 396-410
- **What goes wrong:** The separator is searched for only inside `self._buffer[0]` (`self._buffer[0].find(separator, offset)`). If a multi-byte separator is split across two fed chunks (e.g. `b"abc\r"` + `b"\ndef\r\n..."`), neither chunk contains it on its own. The first chunk is consumed whole, and the search restarts on the next chunk, so the first real separator is skipped.
- **Reproduced:** `feed_data(b"abc\r"); feed_data(b"\ndef\r\nxyz"); readuntil(b"\r\n")` returned `b'abc\r\ndef\r\n'`. The correct result is `b'abc\r\n'`.
- **Why wrong:** `docs/streams.rst`: "Read until separator, where `separator` is a sequence of bytes." TCP segmentation decides where chunk boundaries fall, so the result depends on the network.
- **Severity:** medium. It is public API, and internal callers only use the 1-byte `\n` default, which is unaffected.
- **Fix:** Search the accumulated `chunk` tail (last `seplen-1` bytes) together with the new buffer, or keep a rolling window. When the match straddles the boundary, read only up to the end of the separator.

## 3. `CookieJar` keeps a stale expiry when a cookie is replaced by one without Max-Age/Expires

- **File/line:** `aiohttp/cookiejar.py` 396-423 (`_update_cookies`)
- **What goes wrong:** The expiry is only ever set (via `_expire_cookie`), never cleared. If `a=1; Max-Age=1` is replaced by `a=2` (a session cookie), the old entry stays in `self._expirations`. The heap then deletes the new session cookie at the old deadline.
- **Reproduced:** After the second Set-Cookie, `_expirations` still holds `('example.com', '', 'a')`. With the clock advanced 5 s, `filter_cookies()` returned `{}`.
- **Why wrong:** RFC 6265 §5.3 step 11: the new cookie replaces the old one. A cookie without Max-Age/Expires is a non-persistent cookie with no expiry (step 3), so it must not expire on the old cookie's schedule.
- **Severity:** medium. Sessions are silently lost.
- **Fix:** Pop any existing expiry before recording a new one. When neither max-age nor expires is set (or the value is invalid), do `self._expirations.pop((domain, path, name), None)`. The stale heap entry is then ignored because `_expirations.get(key) != when`.

## 4. `BodyPartReader.decode()` silently truncates Content-Encoding output to 256 KiB

- **File/line:** `aiohttp/multipart.py` 609-619 (`_decode_content`)
- **What goes wrong:** `decompress_sync(data, max_length=self._max_decompress_size)` is called once, and whatever remains is discarded. The async twin `_decode_content_async` (621-634) loops `while d.data_available`; this sync version does not.
- **Reproduced:** 1,000,000 bytes deflated → `decode()` returned 262,144 bytes, while `decode_iter()` returned 1,000,000.
- **Why wrong:** The docstring says it "Decodes data according the specified Content-Encoding". Returning a silently truncated body is data corruption, not a size-limit error.
- **Severity:** medium.
- **Fix:** Loop on `d.data_available` and concatenate, the same way the async path does. If a hard cap is wanted, raise instead of truncating.

## 5. `MultipartWriter.decode()` produces a malformed body

- **File/line:** `aiohttp/multipart.py` 1147-1160
- **What goes wrong:**
  - It omits the CRLF after each part and the closing delimiter `--boundary--\r\n`.
  - It ignores the `encoding`/`errors` arguments when decoding each part (`part.decode()`).
- **Reproduced:**
  - `decode()` returned `'--B\r\n...\r\n\r\na--B\r\n...\r\n\r\nb'`.
  - `as_bytes()` returned `'...a\r\n--B\r\n...b\r\n--B--\r\n'`.
- **Why wrong:** It is documented as the "string representation of the multipart data", but it does not match `as_bytes()`, `write()` or `size`. The output is not valid multipart: a part body runs into the next delimiter, and there is no close delimiter.
- **Severity:** low.
- **Fix:** Append `"\r\n"` after each part, append `"--" + boundary + "--\r\n"` at the end, and pass `encoding, errors` to `part.decode`.

## 6. Accept-Encoding matched by substring, so codings refused with `q=0` are still used

- **File/lines:**
  - `aiohttp/web_fileresponse.py` 242 (`if file_encoding not in accept_encoding`)
  - `aiohttp/web_response.py` 349-350 (`if value in accept_encoding`)
- **What goes wrong:** `Accept-Encoding: gzip;q=0, identity` still selects gzip. `FileResponse` serves the `.gz` sibling, and `enable_compression()` without a forced coding gzip-compresses the response.
- **Why wrong:** RFC 9110 §12.5.3: a qvalue of 0 means "not acceptable". The code comment at web_fileresponse.py 258-259 cites RFC 9110 for Accept-Encoding handling.
- **Severity:** low-medium. A client that explicitly refuses a coding receives it anyway.
- **Fix:** Parse the header into coding → q pairs (e.g. with `HeadersDictProxy.getall` + parameter parsing) and pick only codings with q > 0.

## 7. `Range: bytes=-0` is served as the whole file with 206 instead of 416

- **File/line:** `aiohttp/web_request.py` 682-685. It is consumed at `web_fileresponse.py` 358-395.
- **What goes wrong:** With a suffix length of 0, `start = -end` gives `0` and `end = None`, so `slice(0, None)` is returned. `FileResponse` sees `start = 0` (not negative) and sends the entire file as `206 bytes 0-(n-1)/n`.
- **Why wrong:** RFC 9110 §14.1.1/§14.1.2: a suffix-range with suffix-length 0 is unsatisfiable. The code comment at web_fileresponse.py 383-386 quotes this rule ("a suffix-byte-range-spec with a non-zero suffix-length").
- **Severity:** low.
- **Fix:** In `http_range`, raise `ValueError` when `start` is empty and `end == 0`. `FileResponse` already turns that `ValueError` into a 416.

## 8. WebSocket reader rejects a message of exactly `max_msg_size` bytes

- **File/line:** `aiohttp/_websocket/reader_py.py` 552. The same source is compiled for the C reader.
- **What goes wrong:** `if self._payload_bytes_to_read >= self._max_msg_size - partial_len` rejects a frame whose total is exactly equal to the limit.
- **Reproduced:** With `max_msg_size=256`, a 255-byte binary frame is accepted. A 256-byte frame raises `Message size 256 exceeds limit 256`, which is self-contradictory.
- **Why wrong:** The error text says "exceeds limit". The compressed path (line 326) uses `len(payload_merged) > self._max_msg_size`, so it accepts exactly-limit messages. The docs describe it as the "maximum size of read websocket message".
- **Severity:** low (off-by-one).
- **Fix:** Use `>` (i.e. `self._payload_bytes_to_read > self._max_msg_size - partial_len`).

## 9. `HttpParser.feed_eof()` compares bytes to str (not run; follows from reading the code)

- **File/line:** `aiohttp/http_parser.py` 324 (`if self._lines[-1] != "\r\n":`)
- **What goes wrong:** `self._lines` holds `bytes`, so the comparison with the `str` `"\r\n"` is always unequal, and `b""` is always appended. The effect is benign today, because `parse_headers` stops at the first empty line. The intended check (only terminate the header block if it isn't already terminated) never happens.
- **Severity:** low.
- **Fix:** Compare against `b""`: `if self._lines[-1] != b"": self._lines.append(b"")`.

---

## Considered and not reported

- The `unescape_quotes` ordering in digest auth. It decodes correctly for every input the regex can produce.
- The `max_redirects` off-by-one style. It is long-standing and pinned by tests.
- The response-parser TE handling.
- The `_is_chunked_te` logic.
- `HttpPayloadParser` pause/resume paths.
- `DeflateBuffer`.
- Static-route traversal checks.
- Cross-origin redirect header stripping.

I found nothing I was confident was a defect in these.

## Files read

**In full or in large part:**
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/helpers.py`
- `aiohttp/http_parser.py`
- `aiohttp/streams.py`
- `aiohttp/multipart.py`
- `aiohttp/web_fileresponse.py` (lines 150-438)
- `aiohttp/cookiejar.py` (lines 180-520)
- `aiohttp/_cookie_helpers.py`
- `aiohttp/_websocket/reader_py.py` (lines 150-634)
- `aiohttp/http_writer.py` (lines 60-397)
- `aiohttp/compression_utils.py` (lines 150-420)

**Excerpts:**
- `aiohttp/web_request.py`: `_etag_values`, `if_match`/`if_none_match`/`if_range`, `http_range`, `post`
- `aiohttp/web_response.py`: compression selection
- `aiohttp/client.py`: `_request` loop, auth, redirects, retries
- `aiohttp/web_urldispatcher.py`: `StaticResource._handle` and `_resolve_path_to_response`
- `aiohttp/payload.py`: `decode` methods

**For context (outside scope):**
- `docs/streams.rst` (readuntil)
- `docs/client_reference.rst`, `docs/web_reference.rst` (max_msg_size)
- `tests/test_multipart.py` (the `Stream` helper and the `_charset_` tests)
- `tests/test_websocket_parser.py` (size-limit tests)
