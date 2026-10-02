aiohttp-01 | input | Reviewer must consider remaining_content_len == 0; `x or DEFAULT_CHUNK_SIZE` looks like a harmless default until that value is tried.
aiohttp-02 | nearby | Compare _decode_content's single max_length-capped decompress_sync call with _decode_content_async just below, which loops on data_available.
aiohttp-03 | input | Reviewer must picture a 401 carrying several WWW-Authenticate headers (Basic first); single-challenge partition(" ") looks fine.
aiohttp-04 | nearby | Compare write_eof's final branches with write() (~line 195), which truncates to self.length; write_eof never consults it.
aiohttp-05 | nearby | Compare FORMAT_RE's `[ioe]` class with LOG_FORMAT_MAP a few lines above and the _format_* methods; there is no 'e' entry or method.
aiohttp-06 | trace | Must know that HeadersDictProxy.getall in helpers.py splits on commas outside quotes, then see a URL comma inside <...> gets split in ClientResponse.links.
aiohttp-07 | line | `redirects += 1` followed by `redirects >= max_redirects` is an off-by-one comparison visible in the cited lines.
aiohttp-08 | line | `value in accept_encoding` is a substring test on the raw header, ignoring token boundaries and q=0.
aiohttp-09 | line | The `body is None or self._must_be_empty_body` branch skips the Payload close that the elif branch right below performs.
aiohttp-10 | input | Reviewer must feed a separator split across two buffer entries; find() only searches within _buffer[0].
aiohttp-11 | nearby | Must check CookieJar's constructor to see that treat_as_secure_origin exists and is not copied into tmp_cookie_jar.
aiohttp-12 | nearby | Must compare with the router (web_urldispatcher.py:164 upper-cases methods) to see this constructor stores the method unnormalized.
aiohttp-13 | nearby | Compare FORMAT_RE's `O` alternative with LOG_FORMAT_MAP just above; there is no 'O' key.
aiohttp-14 | nearby | Compare the mid-read limit path that closes tmp with the top-of-loop raises that leave earlier fields' temp files in `out` open.
aiohttp-15 | nearby | Compare StreamReader.total_raw_bytes with EmptyStreamReader's __slots__/__init__ in the same file, which never set total_compressed_bytes.
aiohttp-16 | nearby | Compare next()'s part.read_chunk(32) with the assertion in _read_chunk_from_stream requiring size >= boundary length + 2.
aiohttp-17 | nearby | Compare with the earlier path in next(), which calls _read_boundary() before fetch_next_part(); the _charset_ path skips it.
aiohttp-18 | input | Reviewer must think of an empty or whitespace-only application/json body; loads(self._body.decode()) looks fine otherwise.
aiohttp-19 | nearby | Compare _read_headers, which reads self._content directly, with _readline just above, which drains self._unread first.
aiohttp-20 | line | The module-level lru_cache(maxsize=64) keyed on middleware tuples plainly pins those instances beyond session lifetime.
aiohttp-21 | nearby | Compare the 303/302→GET branch (data = None, no close) with the TooManyRedirects branch just above that calls req._body.close().
aiohttp-22 | input | Reviewer must consider Response() or status 204 with body None plus enable_compression reaching `assert self._body is not None`.
aiohttp-23 | input | Reviewer must try a non-list header whose value contains commas (Date, Set-Cookie Expires); getall list-splits every key.
aiohttp-24 | input | Reviewer must try `bytes=-0`; `start = -end` yields 0 and the slice becomes the whole file.
aiohttp-25 | input | Reviewer must run a Max-Age cookie followed by a plain re-set of the same name; nothing clears the earlier _expirations entry.
aiohttp-26 | input | Reviewer must try an upper-case Domain attribute against a lower-case hostname in _is_domain_match's endswith compare.
aiohttp-27 | input | Reviewer must feed a comma-separated multi-element value into the pair loop, which only advances on `;`.
aiohttp-28 | line | `expect` defaults to "" and the else branch raises for any value but 100-continue, including the absent header.
aiohttp-29 | nearby | Compare __eq__ (delegates to the raw multidict, never unwraps `other`) with __getitem__'s joined ", " view.
aiohttp-30 | line | `file_encoding not in accept_encoding` is a substring test, ignoring q=0.
aiohttp-31 | trace | Must connect _update_headers' popall on the caller's dict (client_reqrep.py) with ClientSession._request reusing that dict across retry/redirect iterations (client.py).
aiohttp-32 | line | `value[1:-1]` strips the quotes with no unescape step visible in the property.
aiohttp-33 | input | Reviewer must try two header names differing only in case; the dedup set is case-sensitive while lookups are not.
aiohttp-34 | line | max() runs before the `total == 0` check, so a nonzero sub-timeout masks total=0.
aiohttp-35 | nearby | Compare the length check at the top of the chunked branch (applied to an existing _chunk_tail) with the tail store at ~1062, which has no check.
aiohttp-36 | line | `max_size = max_size or self._high_water` turns an explicit 0 into the high-water default.
aiohttp-37 | line | self._keep_alive is assigned before the later `keep_alive = False` on the HTTP/1.0 path, which only updates the local.
aiohttp-38 | input | Reviewer must picture a non-final chunk holding fewer than 4 base64 chars; the `if not cut: return chunk` comment otherwise reads as reasoned.
aiohttp-39 | line | The quoted-value alternative `".*"` is greedy and spans past the closing quote.
aiohttp-40 | input | Reviewer must try a mixed-case Host; the mask regex is compiled without IGNORECASE and fullmatch is case-sensitive.
aiohttp-41 | line | InvalidHeader(CONTENT_LENGTH) is raised with only the header name, not the value.
aiohttp-42 | line | asyncio.create_task(cb(chunk)) is fire-and-forget with no saved reference (the TODO says as much).
aiohttp-43 | line | The except-ValueError path sits under `if max_age`, so the `elif expires` branch can never run after an invalid Max-Age.
aiohttp-44 | line | A class-level HTTPNotFound() instance is re-raised on every miss (cited lines 975/1023/908), accumulating traceback state.
aiohttp-45 | line | `CHAR ^ CTL ^ SEPARATORS` uses symmetric difference; chr(9) sits in both CTL and SEPARATORS and so is re-added.
aiohttp-46 | nearby | Compare EmptyStreamReader's __slots__/__init__ (and its "TODO add readuntil") with the inherited StreamReader.readuntil, which reads self._exception.
aiohttp-47 | nearby | Compare _update_transfer_encoding's header-present branch (sets nothing) with _update_body_from_data and _create_writer, which key only on self.chunked.
aiohttp-48 | input | Reviewer must picture a connection that never completes a request; the keep-alive timer is armed only after a response.
aiohttp-49 | line | `if self.chunked is not None` enables chunking when chunked=False.
aiohttp-50 | nearby | Compare write()'s per-chunk decode_iter call with _decode_content_async, which builds a fresh ZLibDecompressor on each call.
aiohttp-51 | line | `if self._length:` treats Content-Length 0 as absent.
aiohttp-52 | nearby | Compare the top-of-feed tail check with the PARSE_TRAILERS store of _chunk_tail at ~1112, which has no length check.
aiohttp-53 | nearby | Compare the base64 quartet-carry logic in read_chunk with the quoted-printable path, which has no carry for escapes split across chunks.
aiohttp-54 | line | part.decode() is called without the encoding/errors that decode() receives.
aiohttp-55 | line | A variable named REUSE_ADDRESS is passed as reuse_port=.
aiohttp-56 | input | Reviewer must try an absolute-form target with no path; the delimiter scan leaves rel at len(path) and returns "".
aiohttp-57 | line | `>=` against max_msg_size rejects a message exactly at the limit, contradicting the "exceeds" message.
aiohttp-58 | trace | Must follow DigestAuthMiddleware's two sends of the same request into AsyncIterablePayload, which drains the iterator on the first send.
aiohttp-59 | nearby | Compare decode() with the size computation just above, which counts a CRLF per part and the closing `--boundary--\r\n`.
aiohttp-60 | line | A bytes element is compared with the str "\r\n".
aiohttp-61 | input | Reviewer must run a format containing `%%` through FORMAT_RE.sub then CLEANUP_RE, which doubles the escaped percent.
