aiohttp-01 | input | Needs a caller passing content_length=0, to see that `remaining_content_len or DEFAULT_CHUNK_SIZE` turns it into a 256 KiB read.
aiohttp-02 | nearby | Needs a comparison of sync `_decode_content` (one capped `decompress_sync`) with `_decode_content_async` just below, which loops on `data_available`.
aiohttp-03 | input | Needs a response with several challenges, Basic before Digest, which the proxy joins into one string whose first token is Basic.
aiohttp-04 | nearby | Needs `write_eof`'s uncompressed path compared with `write()`, which cuts chunks to `self.length`; `write_eof` never does.
aiohttp-05 | nearby | Needs `FORMAT_RE` (which accepts `e`) and the docstring's `%{FOO}e` checked against `LOG_FORMAT_MAP` and the `_format_*` methods a few lines up.
aiohttp-06 | input | Needs a Link URL that contains a comma, which the comma-splitting `getall` breaks before `links` parses it.
aiohttp-07 | line | `redirects += 1` followed by `redirects >= max_redirects` is an off-by-one on inspection.
aiohttp-08 | line | `value in accept_encoding` is a substring match where parsing tokens and q-values is needed.
aiohttp-09 | line | The `body is None or self._must_be_empty_body` branch skips the `try/finally: close()` that the Payload branch right below has.
aiohttp-10 | input | Needs a two-byte separator split across two fed buffers, because `find` searches one buffer at a time.
aiohttp-11 | nearby | Needs CookieJar's constructor options compared with the two fields copied into the temporary jar.
aiohttp-12 | nearby | Needs the convention that HTTP methods are upper-case elsewhere, since the constructor alone looks fine.
aiohttp-13 | nearby | Needs the letters in `FORMAT_RE` compared with the keys of `LOG_FORMAT_MAP`, where `O` is missing.
aiohttp-14 | nearby | Needs the top-of-loop limit raises compared with the mid-read path, which closes its temp file before raising; earlier fields' files are never closed.
aiohttp-15 | nearby | Needs `EmptyStreamReader.__init__` (sets only `total_bytes`) compared with the inherited `total_raw_bytes`, which reads `total_compressed_bytes`.
aiohttp-16 | nearby | Needs `read_chunk(32)` compared with the boundary-length assertion in `_read_chunk_from_stream`.
aiohttp-17 | nearby | Needs `_maybe_release_last_part`/`fetch_next_part` read to see that the `_charset_` part is never released (`_last_part` is still None), so its boundary is never consumed.
aiohttp-18 | input | Needs a JSON-typed response with an empty or whitespace-only body.
aiohttp-19 | nearby | Needs `_read_headers` (reads `_content` directly) compared with `_readline`, which drains `_unread` first.
aiohttp-20 | line | A module-level `lru_cache` keyed on middleware instances visibly keeps them alive after their session.
aiohttp-21 | nearby | Needs the GET-downgrade branch compared with the TooManyRedirects branch just above, which does `await req._body.close()`.
aiohttp-22 | input | Needs a Response with body None (204, or no body) plus compression, which reaches `assert self._body is not None`.
aiohttp-23 | input | Needs a single header value that legitimately contains commas (Date, cookie Expires) passed through the list-splitting `getall`.
aiohttp-24 | input | Needs `Range: bytes=-0`, where `start = -end` gives 0 and the file response serves the whole file.
aiohttp-25 | input | Needs a cookie that had Max-Age replaced by a session cookie of the same name, which leaves the old `_expirations` entry.
aiohttp-26 | input | Needs a Domain attribute in a different case from the host, since `_is_domain_match` compares raw strings.
aiohttp-27 | input | Needs a Forwarded field-value with comma-separated elements; the loop handles only `;` and breaks at the comma.
aiohttp-28 | line | The else branch raises for any value other than "100-continue", including the `""` default for a missing header.
aiohttp-29 | nearby | Needs `__eq__` (delegates to the raw multidict) compared with `__getitem__` just below, which joins values.
aiohttp-30 | line | `file_encoding not in accept_encoding` is a substring check that ignores q=0.
aiohttp-31 | trace | Needs `_update_headers` (client_reqrep.py) popping Host from a dict followed back to `ClientSession._request` reusing that dict on retry or redirect.
aiohttp-32 | nearby | Needs the docstring's "It un-escapes found escape sequences" compared with the plain `value[1:-1]` strip.
aiohttp-33 | input | Needs header names differing only by case, which the case-sensitive `seen` set and `set(keys())` count twice.
aiohttp-34 | line | The `total == 0` check runs after `max()` has already raised total up to connect/sock_read.
aiohttp-35 | input | Needs one oversized chunk-size block with no CRLF, which is stashed in `_chunk_tail` and checked only on the next call.
aiohttp-36 | line | `max_size or self._high_water` visibly turns an explicit 0 into the default.
aiohttp-37 | line | Only the local `keep_alive` is set to False; `self._keep_alive` was already assigned above and never updated.
aiohttp-38 | input | Needs a non-final chunk with fewer than 4 base64 characters, which reaches the `if not cut: return chunk` escape.
aiohttp-39 | line | The greedy `".*"` in `_FORWARDED_PAIR` runs to the last quote in the element.
aiohttp-40 | input | Needs a mixed-case Host header against a case-sensitive `fullmatch`.
aiohttp-41 | line | `InvalidHeader(CONTENT_LENGTH)` visibly omits the received value.
aiohttp-42 | line | `asyncio.create_task(...)` with no kept reference, next to a TODO saying so, drops the callback's exceptions.
aiohttp-43 | line | The `if max_age: ... except ValueError` / `elif expires` structure skips Expires when Max-Age is present but invalid.
aiohttp-44 | nearby | Needs the class-level `HTTP_NOT_FOUND = HTTPNotFound()` connected to `raise self._http_exception`, which re-raises one instance whose traceback keeps growing.
aiohttp-45 | line | `CHAR ^ CTL ^ SEPARATORS` uses symmetric difference, so TAB (in both CTL and SEPARATORS) is toggled back in.
aiohttp-46 | nearby | Needs the `# TODO add async def readuntil` in `EmptyStreamReader` combined with the base `readuntil` touching `_exception`, which `EmptyStreamReader` never initialises.
aiohttp-47 | nearby | Needs `_update_transfer_encoding`, `_update_body_from_data` and `_create_writer` compared: a user TE header never sets `chunked`, so Content-Length is added and no chunk framing is written.
aiohttp-48 | input | Needs an idle or partial-request client, since `_keepalive` is False until the first request completes and `_process_keepalive` returns early.
aiohttp-49 | line | `if self.chunked is not None` enables chunking when `chunked=False`.
aiohttp-50 | nearby | Needs the per-chunk `decode_iter` call compared with `_decode_content_async`, which builds a new `ZLibDecompressor` on each call.
aiohttp-51 | line | `if self._length:` treats Content-Length 0 as absent, unlike the `is not None` checks nearby.
aiohttp-52 | input | Needs one over-long trailer line with no CRLF arriving in a single feed, since the length check only runs on the next call.
aiohttp-53 | input | Needs a quoted-printable escape or soft break that straddles the 256 KiB chunk boundary.
aiohttp-54 | line | `part.decode()` is called without the `encoding`/`errors` arguments the method received.
aiohttp-55 | line | A flag named `REUSE_ADDRESS` is passed as `reuse_port=`.
aiohttp-56 | input | Needs an absolute-form target with no path (`http://example.com`), where the slice returns `''` rather than `/`.
aiohttp-57 | line | `>=` against `max_msg_size - partial_len` rejects a message exactly at the limit.
aiohttp-58 | trace | Needs the digest middleware's resend loop followed into the async-iterable payload, which the first (401) send drained.
aiohttp-59 | nearby | Needs `decode()` compared with `as_bytes()` right below it, which adds CRLF after each part and the closing boundary.
aiohttp-60 | line | A `bytes` list element is compared with the `str` `"\r\n"`, which is always unequal.
aiohttp-61 | input | Needs a format containing a literal `%%` run through `CLEANUP_RE` (`%[^s]`), which rewrites it wrongly.
