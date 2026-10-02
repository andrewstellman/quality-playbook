# aiohttp code review — opus-aiohttp-run05

Checkout: `/tmp/control/aiohttp` (pinned e11d2836203a21bec59095498e578d37801027e7). Scope: `aiohttp/` (package only).

I ran small scripts against the checkout, using `/tmp/aiohttp-venv`, to confirm most of the defects below. Each finding says whether it was reproduced or only read from the code.

---

## 1. `BaseRequest.forwarded` merges several quoted pairs into one value (greedy `".*"`)

- **File/line:** `aiohttp/web_request.py:138-141` (`_FORWARDED_PAIR`), used at `web_request.py:387-408`
- **What goes wrong:** The quoted-string alternative is `".*"`, which is greedy and then anchors on `(?:\Z|;)`. If one forwarded-element has two or more quoted values, the first pair swallows the rest of the element.
  - `Forwarded: for="[2001:db8::1]";proto="https"` gives `{'for': '[2001:db8::1]";proto="https'}`. `proto` is lost and `for` holds garbage.
  - `Forwarded: for="_gazonk";by="x", for=y` gives `{'for': '_gazonk";by="x'}`.
  - Reproduced with `make_mocked_request`.
- **Why it is wrong:** The docstring promises to parse each pair per RFC 7239 and to check "either a 'token' or a 'quoted-string'". RFC 7239 §4 allows several quoted values per element; its own examples quote IPv6 `for=` values. The module even defines `_QDTEXT` (lines 131-135) for this purpose, but never uses it. Applications that read `proto`/`for`/`host` from this property (for scheme or client-IP decisions behind a proxy) get wrong values.
- **Severity:** medium
- **Fix:** Match a real quoted-string, e.g. `rf'"(?:{_QDTEXT}|\\[\t !-~])*"'`, and unescape quoted-pairs in the value.

## 2. `ClientResponse.links` splits Link URIs that contain commas

- **File/line:** `aiohttp/client_reqrep.py:489-514` (uses `HeadersDictProxy.getall`, `aiohttp/helpers.py:788-803`)
- **What goes wrong:** `getall()` splits the header on every comma that is not inside a quoted-string or a comment. It does not protect `<...>` URI-references. Reproduced:
  - Input: `Link: <https://ex.com/items?ids=1,2,3>; rel="next", <https://ex.com/p1>; rel="prev"`
  - `getall` result: `('<https://ex.com/items?ids=1', '2', '3>; rel="next"', ...)`
  - Effect: the `next` link is dropped (the regex `\s*<(.*)>(.*)` does not match the fragments) or corrupted.
- **Why it is wrong:** RFC 8288 §3 puts a full URI-Reference inside `<` `>`. Commas are legal there (they are sub-delims, and are common in query strings such as pagination APIs).
- **Severity:** medium
- **Fix:** Split Link values with a parser that treats `<...>` as atomic, e.g. `re.split(r",\s*(?=<)", value)` per header. Or teach `_LIST_ELEMENT` a `<[^>]*>` branch.

## 3. `BodyPartReader.decode()` silently truncates decompressed output at 256 KiB

- **File/line:** `aiohttp/multipart.py:626-636` (`_decode_content`), reached from `decode()` at `multipart.py:590-602`
- **What goes wrong:** `decompress_sync(data, max_length=self._max_decompress_size)` returns at most `max_decompress_size` bytes (default `DEFAULT_CHUNK_SIZE` = 256 KiB). The rest of the output is dropped: no loop over `data_available`, no error. Reproduced: a gzip part holding 1,200,000 bytes decodes to 262,144 bytes.
- **Why it is wrong:** The docstring says it "Decodes data according the specified Content-Encoding". The async twin `_decode_content_async` (lines 638-651) loops while `d.data_available`, which shows the cap was meant to bound each step, not the total.
- **Severity:** medium (silent data loss)
- **Fix:** Loop `while d.data_available: out += d.decompress_sync(b"", max_length=...)`. If the cap is meant as a hard limit, raise instead of truncating.

## 4. Per-chunk decoding uses a fresh decoder for every chunk: compressed parts fail, quoted-printable parts are corrupted

- **File/line:**
  - `aiohttp/multipart.py:703-711` (`BodyPartReaderPayload.write`)
  - `aiohttp/web_request.py:833-852` (`BaseRequest.post`, file fields)
  - The per-call decoders are `multipart.py:604-617` / `638-667`.
- **What goes wrong:** Both call sites read the part in chunks and call `field.decode_iter(chunk)` on each chunk. `decode_iter` builds a new `ZLibDecompressor` on every call, and `binascii.a2b_qp` runs on each chunk in isolation. Only base64 has boundary handling (`_align_base64_chunk`).
  - **gzip/deflate:** forwarding a gzip `Content-Encoding` part whose compressed size exceeds one chunk via `BodyPartReaderPayload.write()` raises `zlib.error: incorrect header check` on the second chunk. Reproduced with a ~1 MB gzip part.
  - **quoted-printable:** in `Request.post()`, a `=XX` escape or `=\r\n` soft break that lands on a 256 KiB read boundary is left undecoded. Reproduced: a file field whose `=41` straddles the boundary comes back as literal `=41` instead of `A` (length 262155 instead of 262153).
- **Why it is wrong:** Content-Encoding and quoted-printable are stream codings. Decoder state has to carry across chunk boundaries, as `DeflateBuffer` does for HTTP bodies.
- **Severity:** medium for the `write()` failure; low-medium for the QP corruption (CTE is deprecated for form-data but still accepted and decoded here)
- **Fix:** Keep one decompressor per part across chunks (store it on the reader and create it lazily). For QP, carry a trailing incomplete `=`/`=X`/`=\r` sequence into the next chunk, as base64 already does.

## 5. `StreamReader.readuntil()` misses a multi-byte separator that spans two fed buffers

- **File/line:** `aiohttp/streams.py:381-420`
- **What goes wrong:** The separator is searched only inside `self._buffer[0]`. If the separator is split across two `feed_data()` calls, neither search finds it, and reading continues to the next complete occurrence. Reproduced: after `feed_data(b"abc\r")` and `feed_data(b"\ndef\r\nxyz")`, `readuntil(b"\r\n")` returns `b"abc\r\ndef\r\n"` instead of `b"abc\r\n"`.
- **Why it is wrong:** `docs/streams.rst` documents `readuntil(separator)` as "Read until separator, where separator is a sequence of bytes". Where TCP segments split data is arbitrary, so the result depends on packetization.
- **Severity:** medium for users of the public API. Internal callers only use the 1-byte `b"\n"`, so they are unaffected.
- **Fix:** Search `chunk[-(seplen-1):] + buffer[0]` (the previously consumed tail plus the new data), or search the concatenated pending data before consuming it.

## 6. CookieJar keeps a stale expiry when a cookie is replaced by one without Max-Age/Expires

- **File/line:** `aiohttp/cookiejar.py:407-423` (expiry scheduling in `_update_cookies`), with `_expirations` / `_do_expiration` at `cookiejar.py:282-341`
- **What goes wrong:** An expiration is recorded only when the new cookie carries `max-age` or `expires`. If `a=1; Max-Age=1` is later replaced by the session cookie `a=2`, the old entry in `_expirations[(domain, path, "a")]` is never cleared, so `a=2` is deleted when the old deadline passes. Reproduced: `filter_cookies` returns `a=2`, then an empty result 1.2 s later. The same happens when a later Max-Age is invalid: the `ValueError` branch clears the attribute but leaves the old deadline in place.
- **Why it is wrong:** RFC 6265 §5.3 step 3: a cookie without Max-Age/Expires is a non-persistent cookie whose expiry is "the latest representable date", and step 11 replaces the old cookie entirely. The class says it "Implements cookie storage adhering to RFC 6265".
- **Severity:** medium (sessions are dropped unexpectedly)
- **Fix:** In `_update_cookies`, when no valid max-age/expires is found, run `self._expirations.pop((domain, path, name), None)`. Stale heap entries are already ignored by `_do_expiration`'s equality check.

## 7. `Accept-Encoding` q-values are ignored, so a coding the client refused (`q=0`) is still used

- **File/line:**
  - `aiohttp/web_response.py:340-352` (`_start_compression`)
  - `aiohttp/web_fileresponse.py:236-251` (`_get_file_path_stat_encoding`)
- **What goes wrong:** Both use a substring test (`value in accept_encoding`). With `Accept-Encoding: gzip;q=0, identity`:
  - `enable_compression()` compresses with gzip.
  - `FileResponse` serves the pre-compressed `.gz` sibling with `Content-Encoding: gzip`.
- **Why it is wrong:** RFC 9110 §12.5.3: a coding with qvalue 0 is "not acceptable". Sending it anyway can make the response undecodable for that client.
- **Severity:** low-medium
- **Fix:** Parse Accept-Encoding into (coding, q) pairs and pick only codings with q > 0, preferring the highest q.

## 8. Digest auth ignores a Digest challenge that is not the first one

- **File/line:** `aiohttp/client_middleware_digest_auth.py:403-428` (`_authenticate`)
- **What goes wrong:** `response.headers.get("www-authenticate")` returns every WWW-Authenticate header joined with ", " (`HeadersDictProxy.__getitem__`, `helpers.py:807-808`). The code then looks only at the first scheme token (`auth_header.partition(" ")`). A server that sends `WWW-Authenticate: Basic realm="x"` before `WWW-Authenticate: Digest realm=..., nonce=...` (common when several schemes are offered) is treated as "not digest". The middleware returns the 401 without trying Digest.
- **Why it is wrong:** RFC 7235 §4.1 allows several challenges, in one header or in several. The middleware's own docstring says it "intercepts 401 Unauthorized responses containing a Digest authentication challenge".
- **Severity:** low-medium
- **Fix:** Iterate over `response.headers._md.getall("www-authenticate")` (the raw values) and find the challenge whose scheme is `Digest`. Within one header value, locate the `Digest` scheme token rather than assuming it comes first.

## 9. `max_redirects` is off by one: N allows only N-1 redirects

- **File/line:** `aiohttp/client.py:769-777`
- **What goes wrong:** `redirects` is incremented before the check `redirects >= max_redirects`. With `max_redirects=1`, the first redirect raises `TooManyRedirects` and no redirect is followed. With `max_redirects=2`, a chain of exactly two redirects fails.
- **Why it is wrong:** `docs/client_reference.rst:481-482` says "Maximum number of redirects to follow. TooManyRedirects is raised if the number is exceeded." That text says `max_redirects=N` should follow N redirects.
- **Severity:** low
- **Fix:** Use `if max_redirects and redirects > max_redirects:`. If the current semantics are intended, correct the docs instead (and the existing test at `tests/test_client_functional.py:1640`).

## 10. `Range: bytes=-0` returns the whole file with status 206 instead of 416

- **File/line:**
  - `aiohttp/web_request.py:682-685` (`http_range`: `start = -end` with `end == 0` gives `start = 0`)
  - `aiohttp/web_fileresponse.py:342-373`
- **What goes wrong:** A zero-length suffix range becomes `slice(0, None)`. `FileResponse` treats that as "from byte 0 to the end" and sends the full file as 206 with `Content-Range: bytes 0-(n-1)/n`.
- **Why it is wrong:** RFC 9110 §14.1.3/§14.1.1: a suffix-byte-range-spec is satisfiable only "with a non-zero suffix-length". The code's own comment at lines 363-369 cites this and expects 416.
- **Severity:** low
- **Fix:** In `http_range`, raise `ValueError` (which becomes 416) when the suffix length is 0.

## 11. `HeadersDictProxy` iteration and `len()` report duplicate keys that differ only in case

- **File/line:** `aiohttp/helpers.py:810-822`
- **What goes wrong:** `__iter__` and `__len__` deduplicate with a plain `set` of the CIMultiDict's original-case keys. For a request with `Foo: 1` and `foo: 2`:
  - `len(headers) == 2`
  - `list(headers) == ['Foo', 'foo']`
  - both keys map to `"1, 2"`
  - `dict(request.headers)` / `.items()` therefore duplicate the combined value.
  - Reproduced.
- **Why it is wrong:** The class is a case-insensitive `Mapping`. Keys that compare equal under `__getitem__` must appear once in iteration and count once in `len`.
- **Severity:** low
- **Fix:** Deduplicate on `k.lower()` (or `istr`) in both `__iter__` and `__len__`.

## 12. (Minor) `HttpParser.feed_eof` compares bytes with str

- **File/line:** `aiohttp/http_parser.py:315`
- **What goes wrong:** `self._lines[-1] != "\r\n"` compares a `bytes` line with a `str`, so it is always true, and `b""` is appended unconditionally. The effect is harmless today (the list never ends in `b""` at that point), but the check is dead code.
- **Severity:** low
- **Fix:** Compare with `b""`, which appears to be the intent.

---

## Files read

- `aiohttp/helpers.py` (full)
- `aiohttp/http_parser.py` (lines ~100-1274)
- `aiohttp/multipart.py` (lines 1-1000)
- `aiohttp/compression_utils.py` (full)
- `aiohttp/streams.py` (full)
- `aiohttp/cookiejar.py` (full)
- `aiohttp/_cookie_helpers.py` (full)
- `aiohttp/client_reqrep.py` (lines 440-640, 1080-1320)
- `aiohttp/client.py` (lines 520-880)
- `aiohttp/web_request.py` (lines 60-145, 360-910)
- `aiohttp/web_fileresponse.py` (lines 150-438)
- `aiohttp/web_response.py` (lines 90-560)
- `aiohttp/client_middleware_digest_auth.py` (lines 60-507)
- `aiohttp/web_urldispatcher.py` (StaticResource, ~lines 560-713)
- `aiohttp/http_writer.py` (lines 60-397)
- For context only: `docs/streams.rst` (readuntil), `docs/client_reference.rst` (max_redirects), `tests/test_client_functional.py` (max_redirects test), `tests/test_client_response.py` (links test names)
