aiohttp-01 | input | The `or DEFAULT_CHUNK_SIZE` idiom looks routine until you try a remaining length of 0 and see it become a 256 KiB read.
aiohttp-02 | nearby | The reviewer must read `ZLibDecompressor.decompress_sync` to learn that `max_length` truncates silently, and compare it with the async path.
aiohttp-03 | input | The code looks correct until you send two separate `WWW-Authenticate` headers and see that `headers.get` joins them so `Basic` comes first.
aiohttp-04 | nearby | Compare `write_eof` with `write` in the same class: `write` enforces `self.length`, and `write_eof` never does.
aiohttp-05 | nearby | `FORMAT_RE` contains `e`, but `LOG_FORMAT_MAP` a few lines above has no `e` entry and the docstring mentions `_format_e`.
aiohttp-06 | input | The reviewer must think of a comma inside a `<...>` URI in a Link header and run it through the comma splitter.
aiohttp-07 | line | `redirects` is incremented on line 769, then `redirects >= max_redirects` is tested on line 771, which is an off-by-one visible in the cited lines.
aiohttp-08 | line | The substring test `value in accept_encoding` ignores q-values and tokens, and is wrong on sight.
aiohttp-09 | line | Within `write_eof`, the `body is None or _must_be_empty_body` branch skips the `close()` that the Payload branch below it does.
aiohttp-10 | input | The reviewer must feed a separator split across two chunks and trace the `ichar - offset + seplen - 1` arithmetic.
aiohttp-11 | nearby | Compare the temporary `CookieJar(...)` arguments with the session jar's constructor to see that `treat_as_secure_origin` isn't copied.
aiohttp-12 | nearby | The reviewer must compare against how methods are upper-cased elsewhere (request/router) to see this one isn't.
aiohttp-13 | nearby | Same as aiohttp-05: `FORMAT_RE` accepts `O`, but `LOG_FORMAT_MAP` has no matching key.
aiohttp-14 | nearby | Compare the `post()` error paths, which close `tmp` for the current field, with the raises at the top of the loop that leave earlier fields' files open.
aiohttp-15 | nearby | The property reads `total_compressed_bytes`, and the reviewer must check that `EmptyStreamReader` (a slots class in the same file) never defines it.
aiohttp-16 | nearby | Compare the literal `32` in `next()` with the boundary-length assertion in `_read_chunk_from_stream`, which fires for long boundaries.
aiohttp-17 | nearby | The reviewer must read `fetch_next_part` and `_read_boundary` to see that they expect the boundary line to still be unread.
aiohttp-18 | input | The reviewer must try an empty or whitespace-only body with a JSON content type.
aiohttp-19 | input | The reviewer must construct a nested multipart body with no epilogue and follow `_unread` versus stream reads.
aiohttp-20 | line | A module-level `lru_cache` keyed on middleware instances is visibly a retention hazard for credential-holding objects.
aiohttp-21 | nearby | The TooManyRedirects branch just above closes `req._body`, while the method-change branch drops `data` without closing it.
aiohttp-22 | input | The reviewer must try a 204 or empty-body response with compression enabled and reach the `assert self._body is not None`.
aiohttp-23 | input | The reviewer must think of header values that legitimately contain commas (Date, Set-Cookie Expires) and pass one through `getall`.
aiohttp-24 | input | The reviewer must try `bytes=-0`: `start = -end` gives 0, which becomes `slice(0, None)`, the whole file.
aiohttp-25 | input | The reviewer must set a cookie with Max-Age, then replace it with one that has no expiry, and observe that the old expiration persists.
aiohttp-26 | nearby | The reviewer must compare the raw `Domain` attribute with the lower-cased host in `_is_domain_match` and notice the missing normalisation.
aiohttp-27 | line | The pair loop only splits on `;`, so a comma-separated second element can't be handled, which shows on inspection of the loop.
aiohttp-28 | trace | The handler looks wrong alone, but the reviewer must check the router to see it is only invoked when an Expect header exists.
aiohttp-29 | nearby | `__eq__` delegates to `_md` while `__getitem__` and `__iter__` present joined, deduplicated values, so the reviewer must compare them.
aiohttp-30 | line | Same substring test as aiohttp-08, `file_encoding not in accept_encoding`, ignoring q=0.
aiohttp-31 | trace | The `popall` mutation of the caller's headers matters only when `ClientSession._request` reuses the same dict across retry and redirect iterations.
aiohttp-32 | nearby | The reviewer must compare against the unescaping done in `getall`, and against the RFC 7239 quoted-string rules, to see it is absent here.
aiohttp-33 | input | The reviewer must try two keys differing only in case, because `__iter__` and `__len__` use a case-sensitive set over a case-insensitive dict.
aiohttp-34 | line | `max()` folds `connect` into `total` before the `total == 0` check, so the ordering is wrong on inspection.
aiohttp-35 | nearby | Compare the `_chunk_tail` handling with the other length checks in the same `feed_data` state machine to see that this path defers the check.
aiohttp-36 | line | `max_size or self._high_water` treats an explicit 0 as unset.
aiohttp-37 | line | `keep_alive` is a local that is set to False while `self._keep_alive` was already assigned earlier in the same function.
aiohttp-38 | input | The reviewer must try a non-final chunk shorter than 4 base64 characters and follow the back-walk to `cut == 0`.
aiohttp-39 | line | The greedy `".*"` in `_FORWARDED_PAIR` is wrong on inspection for a quoted-string pattern.
aiohttp-40 | nearby | The reviewer must compare `MaskDomain` against how hosts are normalised or case-folded elsewhere in routing.
aiohttp-41 | line | The exception is raised with a constant and drops the received value, visible on the cited line.
aiohttp-42 | line | `asyncio.create_task` with no retained reference or done-callback is a recognised smell on inspection.
aiohttp-43 | line | The `elif` for Expires hangs off the Max-Age truthiness test, so a failed Max-Age parse skips it, which is visible in the block.
aiohttp-44 | nearby | The class-level exception instance (975, 1023) is raised at 908, and the reviewer must connect the reuse to traceback accumulation.
aiohttp-45 | input | `TOKEN = CHAR ^ CTL ^ SEPARATORS` needs the reviewer to evaluate the set algebra, since tab is in both CTL and SEPARATORS and XOR cancels it.
aiohttp-46 | nearby | The reviewer must compare `EmptyStreamReader`'s slots and methods with `StreamReader.readuntil`, which uses `_exception`.
aiohttp-47 | trace | The reviewer must connect `_update_transfer_encoding`, `_update_body_from_data` and `_create_writer` to see how the header and body framing diverge.
aiohttp-48 | trace | The reviewer must follow the connection lifecycle across `__init__`, `connection_made` and `_process_keepalive` to see when the timer is armed.
aiohttp-49 | line | `if self.chunked is not None` is true for `chunked=False`, unlike the `elif self.chunked` truthiness test in `_update_transfer_encoding`.
aiohttp-50 | nearby | The reviewer must read `decode_iter` and `_decode_content_async` to see that a new decompressor is made per call, then look at the caller's per-chunk use.
aiohttp-51 | line | `if self._length:` treats a declared length of 0 as absent.
aiohttp-52 | nearby | Same as aiohttp-35, in the trailer state of the same function.
aiohttp-53 | input | The reviewer must think of a quoted-printable escape split at the 256 KiB read boundary and follow the per-chunk `a2b_qp` calls.
aiohttp-54 | line | `part.decode()` is called with no arguments inside a method that takes `encoding` and `errors`.
aiohttp-55 | line | `REUSE_ADDRESS` is passed as `reuse_port=`, a wrong argument name on sight.
aiohttp-56 | input | The reviewer must try an absolute-form request target with no path and follow the URL split.
aiohttp-57 | line | `>=` against the size limit is an off-by-one against the "exceeds" message.
aiohttp-58 | trace | The reviewer must combine the digest middleware's retry with the async-iterable payload's single-use `write_with_length`.
aiohttp-59 | nearby | Compare `MultipartWriter.decode` with the writer's serialize/`__iter__` path, which adds CRLFs and the closing boundary.
aiohttp-60 | line | `bytes != str` is always true, visible on the cited line.
aiohttp-61 | input | The reviewer must try a format containing `%%` and run it through `CLEANUP_RE` and `%`-formatting.
