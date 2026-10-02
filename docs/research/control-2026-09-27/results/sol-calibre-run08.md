model: gpt-6-sol
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:16:13 UTC; finished 2026-09-28 23:19:14 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; attempted tests, which could not start
interruptions or errors: checkout requires calibre built runtime unavailable to system Python
network access attempted (yes/no, and what): no attempt reported

# Review of `src/calibre/srv/` at `7691f4f1a155d799afdfec99e2cdc2716c178402`

## Findings

1. **High — Digest authorization can be replayed against a different query string** — `src/calibre/srv/auth.py:202–207`. `DigestAuth.validate_request()` parses the signed `uri` but compares only its path tuple with `data.path`. The digest calculation uses the signed URI, while the endpoint receives the query from the actual request. Thus a valid `Authorization` header for `GET /ajax/...?...=A` also authenticates `GET /ajax/...?...=B` when the path is the same. The implementation explicitly says the URI in the Request Line and Authorization header must match (line 206), and Digest's A2 includes the URI (lines 164–181). Since repeated nonce counts are intentionally accepted (lines 198–200; also tested in `tests/auth.py`), the changed-query request can reuse the captured header. Compare the entire request target, including query, with the digest `uri` before accepting it; normalize only equivalent URI forms if needed.

2. **Medium — Range plus gzip support emits conflicting framing and an unchunked body** — `src/calibre/srv/http_response.py:759–808`. For a compressible, range-capable file (for example `text/plain`) requested with both `Accept-Encoding: gzip` and `Range: bytes=0-9`, `compressible` remains true and `ranges` is nonempty. The server skips compression (line 784), sets `Transfer-Encoding: chunked` (lines 793–794), then adds `Content-Length: 10` and `Content-Range` (lines 796–801). `write_response_body()` sends the file range as raw bytes through `write_buf` (lines 638–647), without chunk framing. HTTP clients that honor `Transfer-Encoding` misparse or stall, and the response carries mutually conflicting length headers. The existing range tests assert a readable 206 body and length (`tests/http.py:441–446`). Once a range is selected, disable compression and its chunked transfer header before framing the 206 response.

3. **Medium — Streaming output crashes when gzip is accepted** — `src/calibre/srv/http_response.py:749–756`. An endpoint that returns an iterator becomes `GeneratedOutput`, whose `content_length` is `None` (`http_response.py:404–411`). For HTTP/1.1 with a compressible content type and `Accept-Encoding: gzip`, the expression `output.content_length >= opts.compress_min_size` raises `TypeError`. The default compression threshold is 1024 (`opts.py:59–63`). The response writer explicitly supports `GeneratedOutput` using chunked encoding (`http_response.py:651–652`), so this is a supported output form. Check that the length is numeric before comparing it; for unknown-length output, either stream uncompressed or compress the iterator properly.

4. **Medium — Valid chunked request trailers are rejected after the body** — `src/calibre/srv/http_request.py:434–459`. After a zero-length chunk, `read_chunk_separator()` insists that the very next line is CRLF. A valid chunked request ending `0\r\nChecksum: xyz\r\n\r\n` instead receives 400 `Chunk does not have trailing CRLF`. The code's own `Transfer-Encoding: chunked` support (lines 374–388) and HTTP chunk framing require consuming a trailer section terminated by an empty line. Read and validate trailer header lines with the existing header-size bounds before calling `prepare_response()`.

5. **Low — Absolute-form URI loses a query when the path is empty** — `src/calibre/srv/http_request.py:55–58`. For a request target such as `http://example.com?search=foo`, `remainder.partition(b'/')` puts `?search=foo` in `authority` and makes `path` `/`; `parse_uri()` consequently returns an empty query. The comment at lines 51–54 explicitly allows an absolute URL with a query after an optional path. Split authority at the first `/` **or** `?`, and preserve the query as part of the constructed path.

## Verification

Source control flow was checked against the existing HTTP and authentication tests. I attempted `PYTHONPATH=src python3 -m unittest calibre.srv.tests.http.TestHTTP.test_http_response`; it cannot import this checkout under the system Python because `calibre.constants` requires `sys.extensions_location`, supplied by calibre's build/runtime.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/opts.py` (relevant options)
- `src/calibre/srv/tests/auth.py` (relevant tests)
- `src/calibre/srv/tests/http.py` (relevant tests)
- Search-result excerpts in `src/calibre/srv/ajax.py`, `books.py`, `code.py`, `content.py`, `convert.py`, `fts.py`, `legacy.py`, `opds.py`, `render_book.py`, `users_api.py`, and `utils.py`.
