model: gpt-6-sol
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:05:43 UTC; finished 2026-09-28 23:07:22 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# calibre server review

Checkout: `7691f4f1a155d799afdfec99e2cdc2716c178402`  
Scope: `src/calibre/srv/`

## Findings

1. **Medium — expired rendered books are never removed (and cleanup can target the working directory).** `src/calibre/srv/books.py:116` calls `safe_remove(x)` where `x` is only a name from `os.listdir(fdir)`. The age check reads the manifest under `fdir`, but deletion resolves `x` relative to the server's current working directory. When a cached render ages past `interval`, its cache directory remains; if a same-named directory happens to exist in the working directory, that directory is removed instead. The adjacent comment says to delete the stale book, and `job_done()` stores renders under `books_cache_dir()/f/<hash>` at lines 140–143. **Fix:** call `safe_remove(os.path.join(fdir, x), False)`.

2. **Medium — Digest authentication accepts a signed URI for a different query.** `src/calibre/srv/auth.py:202-207` compares only `parse_uri(self.uri)[1]` to `data.path`; `parse_uri()` drops the query into a separate return value (`http_request.py:81-96`). A valid Digest `Authorization` header for `GET /some-route?x=1` therefore authenticates `GET /some-route?x=2`, even though the digest calculation includes the first URI. This contradicts the method's own URI-mismatch error at line 206 and the RFC 2617 A2 calculation documented at lines 153–163, which binds the digest to the request URI. It matters particularly because nonce-count replay checks are intentionally disabled at lines 198–200. **Fix:** compare the complete request target in `self.uri` with `data.request_original_uri` (allowing the intended absolute-form/origin-form equivalence if needed), including the query, before accepting the digest.

3. **Medium — a valid chunked request with trailers is rejected.** `src/calibre/srv/http_request.py:434-450` handles a zero-size chunk by immediately requiring the next line to be a blank CRLF. For `Transfer-Encoding: chunked` with `0\r\nX-Check: value\r\n\r\n`, it returns 400 `Chunk does not have trailing CRLF`. Chunked framing permits trailer fields after the last chunk; the server advertises chunked-request support in `finalize_headers()` at lines 369–388 and tests only the no-trailer form in `tests/http.py:283-288`. **Fix:** after the zero chunk, consume and validate trailer lines through the terminating blank line, then process the body.

4. **Low — malformed byte ranges can raise an uncaught exception.** `src/calibre/srv/http_response.py:137` assumes every item after `bytes=` contains a hyphen. For `Range: bytes=abc`, `brange.split('-', 1)` has one element and tuple unpacking raises `ValueError`, instead of returning no valid range as `get_ranges()` documents at lines 123–125. `finalize_output()` calls this parser directly at line 760, so a malformed client header disrupts response generation. The existing range tests cover `bytes=a-2` but not a missing hyphen (`tests/http.py:127-143`). **Fix:** reject or skip items without exactly one separator before unpacking, and return the function's invalid-range result.

5. **Low — an absolute-form URI without a path loses its query.** `src/calibre/srv/http_request.py:56-58` splits the absolute URI only on `/`. For `http://host?x=1`, `remainder.partition(b'/')` treats `host?x=1` as the authority and manufactures the path `/`; `parse_uri()` then sees an empty query. The comment at lines 51–54 explicitly describes an HTTP URL with an optional path and query, so this is a supported request-target form. **Fix:** split authority at the first `/` *or* `?`, and preserve a query that follows an omitted path as `/?x=1`.

## Files read

`src/calibre/srv/auth.py`; `books.py`; `handler.py`; `http_request.py`; `http_response.py`; `last_read.py`; `opts.py`; `routes.py`; `tests/auth.py`; `tests/http.py`; `tests/routes.py`.
