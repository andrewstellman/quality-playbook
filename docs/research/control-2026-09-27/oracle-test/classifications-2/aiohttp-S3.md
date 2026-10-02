aiohttp-01 | input | The reviewer must try a remaining length of 0, because `remaining_content_len or DEFAULT_CHUNK_SIZE` reads fine until 0 is passed.
aiohttp-02 | nearby | Compare `_decode_content`, which decompresses once with `max_length`, against `_decode_content_async`, which loops `while d.data_available`.
aiohttp-03 | input | The reviewer must think of two `WWW-Authenticate` headers, Basic first and Digest second, since the `partition(" ")` scheme check looks fine for a single header.
aiohttp-04 | nearby | `write()` truncates to `self.length`, and the reviewer must compare that with `write_eof()`, which never checks the length.
aiohttp-05 | nearby | Compare the `FORMAT_RE` character class (`[ioe]`) with the keys in `LOG_FORMAT_MAP` and the `_format_*` methods.
aiohttp-06 | input | The reviewer needs a Link URL containing a comma, and must know `getall` splits on commas (helpers.py, a different file from client_reqrep.py).
aiohttp-07 | line | `redirects += 1` followed by `redirects >= max_redirects` is an off-by-one on inspection.
aiohttp-08 | line | Selecting the coding with `value in accept_encoding` is a substring match where q-values and tokens need parsing.
aiohttp-09 | nearby | The reviewer must compare the first `write_eof` branch with the Payload branch, which closes the payload, and notice the first branch skips the close.
aiohttp-10 | input | The reviewer must feed a separator split across two chunks; the `ichar - offset + seplen - 1` arithmetic hides the flaw until that case is run.
aiohttp-11 | nearby | The reviewer must compare the temporary `CookieJar(...)` arguments with the session jar's constructor options (`treat_as_secure_origin`).
aiohttp-12 | nearby | The reviewer must compare with sibling exceptions or the method-handling code to see that the method is not upper-cased.
aiohttp-13 | nearby | Same as 05: the `FORMAT_RE` atom `O` has no `LOG_FORMAT_MAP` key.
aiohttp-14 | nearby | The reviewer must read the `post()` loop and its error exits in the same function and see that no path closes the earlier fields' temp files.
aiohttp-15 | nearby | `EmptyStreamReader.__init__` sets only `total_bytes`, so the reviewer must compare it with `StreamReader.__init__` and the slots to see `total_compressed_bytes` is never set.
aiohttp-16 | nearby | The `read_chunk(32)` call must be compared with the `size >= self._boundary_len` assertion in `_read_chunk_from_stream`, plus a long boundary.
aiohttp-17 | nearby | The `_charset_` branch calls `fetch_next_part()` without consuming the boundary line; compare with the normal `next()` path.
aiohttp-18 | input | The reviewer must think of an empty or whitespace-only body, because `json()` looks fine otherwise.
aiohttp-19 | input | The reviewer must construct the nested body (`--inner--` directly followed by `--outer`) and see that `_read_headers` bypasses `_unread`.
aiohttp-20 | line | An `lru_cache` at module level keyed on middleware instances that hold credentials is a retention smell on inspection.
aiohttp-21 | nearby | The `max_redirects` branch just above closes `req._body`, and the reviewer must notice the method-change branch does not.
aiohttp-22 | trace | The reviewer must follow `prepare()` to `_prepare_headers` to `_do_start_compression` and see that a `None` body reaches `compress`.
aiohttp-23 | input | `getall` is generic list-splitting, and the reviewer must try a header value that contains a comma, such as `Date` or `Set-Cookie` Expires.
aiohttp-24 | trace | `http_range` turns `-0` into `slice(0, None)` in web_request.py, and `FileResponse` in another file consumes it as a full range.
aiohttp-25 | input | The reviewer must run two `Set-Cookie` headers for the same cookie, the first with Max-Age and the second without, to see the stale `_expirations` entry.
aiohttp-26 | input | The reviewer must think of an upper-case `Domain` attribute, since the domain match looks correct for lower-case input.
aiohttp-27 | trace | The pair loop only stops on `;`, but the field values come from `getall`, which splits on commas; the reviewer must trace both.
aiohttp-28 | line | `expect` defaults to `''` and any value other than `100-continue` raises, so a request with no header fails.
aiohttp-29 | nearby | `__eq__` delegates to the raw multidict, while `__getitem__` and `__iter__` present joined and de-duplicated values.
aiohttp-30 | line | Same substring-style check as 08 on `Accept-Encoding` for the `.gz` variant.
aiohttp-31 | trace | `headers.popall(HOST)` in client_reqrep.py mutates a dict that the retry loop in client.py reuses.
aiohttp-32 | nearby | The reviewer must compare the `value[1:-1]` quote stripping with the unescaping in `HeadersDictProxy.getall` or with the RFC.
aiohttp-33 | input | The reviewer must try headers differing only in case (`X` and `x`), because the `set`-based de-duplication looks fine otherwise.
aiohttp-34 | line | `max(self.total, connect...)` runs before the `== 0` check, so the ordering is wrong on inspection.
aiohttp-35 | input | The reviewer must think of a huge chunk-size line arriving in one `feed_data` call, since the length check only runs on `_chunk_tail` at the next call.
aiohttp-36 | input | The reviewer must think of `max_size=0`, because the `or` fallback looks intentional otherwise.
aiohttp-37 | nearby | Within `_prepare_headers`, the local `keep_alive` is set to False while `self._keep_alive` stays True; the reviewer must compare the two.
aiohttp-38 | input | The reviewer must try a non-final chunk of fewer than 4 base64 characters, which reaches the `cut == 0` path.
aiohttp-39 | line | The greedy `".*"` in `_FORWARDED_PAIR` spans past the closing quote.
aiohttp-40 | input | The reviewer must think of a mixed-case host, because `fullmatch` on a compiled mask has no case handling.
aiohttp-41 | nearby | The reviewer must compare with other `InvalidHeader` uses that include the offending value.
aiohttp-42 | line | The `# TODO: Save and await this task` comment beside an unreferenced `create_task` shows it on inspection.
aiohttp-43 | line | The `except ValueError` only blanks max-age and then skips the `elif` for Expires, which is visible in the if/elif structure.
aiohttp-44 | trace | The reviewer must follow the class-level exception instance through `SystemRoute._handle` and the request handler to see the traceback growth and retained requests.
aiohttp-45 | nearby | `TOKEN = CHAR ^ CTL ^ SEPARATORS` needs the CTL and SEPARATORS sets compared, since chr(9) appears in both and XOR cancels it.
aiohttp-46 | nearby | The reviewer must compare `EmptyStreamReader`'s `__init__` and slots with the attributes `StreamReader.readuntil` uses (`_exception`).
aiohttp-47 | trace | Three sites are needed: the `chunked` test in `_update_transfer_encoding`, the `Content-Length` decision in `_update_body_from_data`, and the writer choice in `_create_writer`.
aiohttp-48 | trace | The reviewer must follow `connection_made`, the keep-alive timer arming after a completed request, and the `_process_keepalive` early return.
aiohttp-49 | nearby | `if self.chunked is not None` in `_create_writer` must be compared with how `chunked` and `Content-Length` are set in `_update_body_from_data`.
aiohttp-50 | nearby | `write()` calls `decode_iter` per chunk, and the reviewer must compare it with `_decode_content_async` to see it creates a fresh decompressor each time.
aiohttp-51 | input | The reviewer must think of `Content-Length: 0`, because `if self._length:` looks fine for non-zero lengths.
aiohttp-52 | input | Same as 35 but for the trailers state: the reviewer must try an over-long trailer line arriving in one call.
aiohttp-53 | input | The reviewer must place a quoted-printable escape across the 256 KiB read boundary, since chunk-wise `a2b_qp` looks fine otherwise.
aiohttp-54 | line | `part.decode()` is called with no arguments inside `decode(encoding, errors)`.
aiohttp-55 | line | The default socket factory passes `reuse_port=REUSE_ADDRESS`, an address-reuse flag passed as a port-reuse argument.
aiohttp-56 | input | The reviewer must try an absolute-form target with no path (`GET http://example.com`) to see the empty `raw_path`.
aiohttp-57 | line | The `>=` comparison against `_max_msg_size` raises at exactly the limit, so the boundary is off on inspection.
aiohttp-58 | trace | The reviewer must combine the Digest middleware's retry loop with `AsyncIterablePayload` being consumed on the first send.
aiohttp-59 | nearby | The reviewer must compare `decode()`'s output with `MultipartWriter.write` and `as_bytes`, which emit CRLFs and the closing boundary.
aiohttp-60 | line | Comparing a `bytes` element with the `str` `"\r\n"` is wrong on inspection.
aiohttp-61 | input | The reviewer must compile a format containing `%%`, because `CLEANUP_RE` (`(%[^s])`) looks plausible for single-percent cases.
