aiohttp-01 | input | Try `write_with_length(writer, 0)` and see that `remaining_content_len or DEFAULT_CHUNK_SIZE` turns a legitimate 0 into a 256 KiB read.
aiohttp-02 | nearby | Compare sync `_decode_content` (a single `decompress_sync(max_length=...)`) with `_decode_content_async`, which loops on `data_available`; the sync path silently drops the remainder.
aiohttp-03 | input | Send a 401 with two `WWW-Authenticate` headers (Basic first, then Digest) and see that only the joined first scheme token is checked.
aiohttp-04 | nearby | Compare `write_eof(chunk)` with `write()` in the same class; `write()` enforces `length` and the no-compression tail of `write_eof` does not.
aiohttp-05 | nearby | Compare `FORMAT_RE`'s `[ioe]` with the keys in `LOG_FORMAT_MAP` and the `_format_*` methods; `e` has none.
aiohttp-06 | trace | Follow `resp.links` into `HeadersDictProxy.getall` in helpers.py, which splits on every comma, and then supply a URL that contains a comma.
aiohttp-07 | nearby | Read the `redirects += 1; if redirects >= max_redirects` ordering against the documented meaning of `max_redirects` to see the off-by-one.
aiohttp-08 | line | `value in accept_encoding` is a substring test, so `gzip;q=0` matches; a token/q-value parse is needed.
aiohttp-09 | line | In `write_eof` the `must_be_empty_body` branch never closes a `Payload`, while the `elif` branch closes it in a `finally`.
aiohttp-10 | input | Feed `b'abc\r'` then `b'\ndef\r\nxyz'`; `find(separator)` runs per buffer chunk, so a separator split across chunks is missed.
aiohttp-11 | nearby | Compare the temporary `CookieJar(...)` arguments with the session jar's constructor options; `treat_as_secure_origin` is not copied.
aiohttp-12 | nearby | Compare how `_method` is stored with how routing and `allowed_methods` handle method case elsewhere; there is no `.upper()`.
aiohttp-13 | nearby | Compare `FORMAT_RE`'s `O` with the keys in `LOG_FORMAT_MAP`.
aiohttp-14 | nearby | The mid-read `max_size` branch in the same function closes `tmp`, but the top-of-loop `raise`s leave earlier fields' files open.
aiohttp-15 | nearby | `EmptyStreamReader.__init__` skips `super().__init__`; compare it with the `StreamReader` slots, which `total_raw_bytes` reads.
aiohttp-16 | nearby | Connect the assertion in `_read_chunk_from_stream` (size >= boundary length) to the hard-coded `read_chunk(32)` in `next()`, then pick a long boundary.
aiohttp-17 | nearby | Compare the `_charset_` branch of `next()` with the normal path, which calls `_read_boundary()` before `fetch_next_part()`.
aiohttp-18 | input | Try an empty or whitespace-only body; nothing guards it before `loads(...)`.
aiohttp-19 | nearby | `_read_boundary` uses `_readline` (which honours `_unread`), while the adjacent `_read_headers` reads `self._content.readline` directly.
aiohttp-20 | nearby | See what the cache key (the middleware tuple, holding credentials) retains in a module-level `lru_cache(maxsize=64)`.
aiohttp-21 | nearby | The max-redirects branch in the same loop closes `req._body`, but the method-change branch that sets `data=None` does not.
aiohttp-22 | input | Run `Response()` or `Response(status=204)` with compression enabled; only then does `assert self._body is not None` fail.
aiohttp-23 | input | Call `getall('Date')` or `getall('Set-Cookie')` with a value that contains a comma; the always-split list regex only shows its cost on that input.
aiohttp-24 | input | Try `Range: bytes=-0`; `start = -end` becomes 0, which is falsy in the later `if start` and `int(start) if start` tests.
aiohttp-25 | nearby | Read `_expire_cookie` and `_expirations` bookkeeping against the branch structure; a later cookie with no expiry never clears the older entry.
aiohttp-26 | input | Use an upper-case `Domain=`; `_is_domain_match` compares it case-sensitively with the host.
aiohttp-27 | input | Feed a multi-element `Forwarded` value; the loop only terminates pairs on `;`, so the comma case shows up only with such input.
aiohttp-28 | input | Call the handler with no `Expect` header; `expect` defaults to `''` and falls into the `raise`.
aiohttp-29 | nearby | Compare `__eq__` (delegates to the raw multidict) with `__getitem__`'s comma-joined view in the same class.
aiohttp-30 | line | `file_encoding not in accept_encoding` is a substring match where a token and q-value match is needed.
aiohttp-31 | trace | Follow the request loop in client.py to see it reuse the caller's header dict that `_update_headers` in client_reqrep.py mutates with `popall`.
aiohttp-32 | line | The quoted-string branch does `value[1:-1]` and never unescapes `\"` or `\\`.
aiohttp-33 | input | Use two headers differing only in case; the `set(...)` and `seen` de-duplication in `__iter__` and `__len__` is case-sensitive.
aiohttp-34 | line | `max(...)` is applied before the `== 0` check, so a nonzero `connect` masks a zero total.
aiohttp-35 | input | Feed a 2 MiB chunk-size line in one call; the length check only runs at the top of the next `feed_data`.
aiohttp-36 | input | Pass `max_size=0`; `max_size or self._high_water` treats it as unset.
aiohttp-37 | nearby | See that the local `keep_alive = False` is not written back to `self._keep_alive`, which is what the connection handling later uses.
aiohttp-38 | input | Feed a non-final chunk with fewer than 4 base64 characters; the `if not cut: return chunk` path only shows on that input.
aiohttp-39 | input | Try `for="a";by="b"`; the greedy `".*"` in `_FORWARDED_PAIR` only misbehaves when two quoted values are present.
aiohttp-40 | nearby | Compare `MaskDomain` (regex built with no `IGNORECASE` and no lowercasing) with the lower-case-only `re_part` and the case-insensitive host names it handles.
aiohttp-41 | nearby | Compare the bare `InvalidHeader(CONTENT_LENGTH)` with how sibling parser errors include the offending value.
aiohttp-42 | line | The `# TODO: Save and await this task.` comment and the `create_task` call with no retained reference are visible on inspection.
aiohttp-43 | input | Try `Max-Age=abc` together with an `Expires` in the past; the `elif` for Expires is skipped after the `except ValueError`.
aiohttp-44 | nearby | Compare the class-level `HTTP_NOT_FOUND = HTTPNotFound()` with the per-request `HTTPMethodNotAllowed(...)` next to it; a shared raised exception instance keeps accumulating `__traceback__`.
aiohttp-45 | input | Evaluate `CHAR ^ CTL ^ SEPARATORS` for chr(9), which is in all three sets, so the XOR puts it back.
aiohttp-46 | nearby | `EmptyStreamReader.__init__` sets only two attributes and skips `super().__init__`, so slots like `_exception` are unset when `readuntil` reads them.
aiohttp-47 | trace | Combine `_update_transfer_encoding` (which does nothing when `chunked` is in the header), the `Content-Length` assignment in `_update_body_from_data`, and `_create_writer`'s chunking decision.
aiohttp-48 | trace | Follow `__init__` (`_keepalive = False`), `connection_made`/`start`, and `_process_keepalive`'s early return to see that no timer is armed before the first request completes.
aiohttp-49 | line | `if self.chunked is not None: writer.enable_chunking()` is true for `chunked=False`.
aiohttp-50 | nearby | Read `BodyPartReaderPayload.write` (per-chunk `decode_iter`) against `_decode_content_async`, which builds a fresh `ZLibDecompressor` on each call.
aiohttp-51 | line | `if self._length:` treats a declared `Content-Length: 0` as absent.
aiohttp-52 | input | Feed an oversized trailer line with no CRLF in one call; the length check is only done on the next call via `_chunk_tail`.
aiohttp-53 | nearby | Compare the stateless per-chunk `a2b_qp` with the base64 carry logic (`_b64_carry`, `_align_base64_chunk`) that exists in the same class because chunk boundaries matter.
aiohttp-54 | line | `part.decode()` is called with no arguments while `encoding` and `errors` are passed to the headers' decode.
aiohttp-55 | line | `reuse_port=REUSE_ADDRESS` passes an address-reuse flag as a port-reuse argument.
aiohttp-56 | input | Try `GET http://example.com HTTP/1.1` (no path) and `...?x=1`, and follow the delimiter-search loop.
aiohttp-57 | line | `>= self._max_msg_size - partial_len` rejects an exact-limit message; the comparison should be `>`.
aiohttp-58 | trace | Follow `__call__`'s retry loop, `_authenticate`, and `AsyncIterablePayload.write_with_length` in payload.py; a one-shot async iterator is exhausted on the first send.
aiohttp-59 | nearby | Compare `decode()` with `size()`/`as_bytes()` in the same class, which account for the CRLF after each part and the closing `--boundary--\r\n`.
aiohttp-60 | line | `self._lines[-1] != "\r\n"` compares `bytes` with `str`, so it is always true.
aiohttp-61 | input | Compile `'%%  %a'` and check how `CLEANUP_RE` (`%[^s]`) rewrites `%%` after the `FORMAT_RE` substitution.
