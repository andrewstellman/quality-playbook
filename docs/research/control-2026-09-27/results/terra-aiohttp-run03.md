model: gpt-5.6-terra
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 22:12:53 UTC; finished 2026-09-28 22:16:48 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review — e11d2836203a21bec59095498e578d37801027e7

## Findings

### 1. `EmptyStreamReader.readuntil()` crashes for every bodyless request

- **File and line:** `aiohttp/streams.py:598-680`, especially line 662.
- **Severity:** medium.
- **What goes wrong:** Calling `await request.content.readuntil()` on a request that has no body raises `AttributeError` instead of returning `b""`. `BaseRequest.content` returns the `EMPTY_PAYLOAD` singleton for this case, whose concrete type is `EmptyStreamReader` (see `aiohttp/web_request.py:699-713`). `EmptyStreamReader` overrides `readline()`, `read()`, and `readany()` with empty-result implementations, but it does not override `readuntil()`.
- **Why it is wrong:** The inherited `StreamReader.readuntil()` immediately accesses state such as `_exception`, `_buffer`, and `_eof` (lines 388 onward), none of which `EmptyStreamReader.__init__()` establishes. The class itself contains `# TODO add async def readuntil` at line 662, while its other read APIs all consistently report EOF as `b""`; its intended empty-stream behavior is therefore unambiguously incomplete.
- **Suggested fix:** Add `async def readuntil(self, separator: bytes = b"\n", *, max_size: int | None = None) -> bytes: return b""` to `EmptyStreamReader`, matching `readline()` and the EOF behavior of `StreamReader.readuntil()`.

### 2. File responses return 304 for unsafe methods when a conditional matches

- **File and line:** `aiohttp/web_fileresponse.py:214-226`.
- **Severity:** medium.
- **What goes wrong:** If an application returns `FileResponse` from a `PUT`, `POST`, or other non-GET/HEAD handler, a matching `If-None-Match` or `If-Modified-Since` produces `_FileResponseResult.NOT_MODIFIED`, which becomes a 304 response at lines 282-285. For example, a `PUT /object` handled with `FileResponse(path)` and `If-None-Match: <current-etag>` receives 304.
- **Why it is wrong:** HTTP conditional-request semantics require a false condition to yield 304 only for GET or HEAD; for other methods it must yield 412 Precondition Failed. The adjacent `If-Match` and `If-Unmodified-Since` branches already return `_FileResponseResult.PRE_CONDITION_FAILED`, and the code imports and implements that 412 path at lines 279-280. The `If-None-Match`/`If-Modified-Since` branches omit the required method distinction entirely.
- **Suggested fix:** When either branch's condition matches, return `NOT_MODIFIED` only for `GET`/`HEAD`; return `PRE_CONDITION_FAILED` for every other request method. Keep the existing `If-None-Match` precedence over `If-Modified-Since`.

### 3. Compression selection ignores `q=0` and matches substrings in `Accept-Encoding`

- **File and line:** `aiohttp/web_fileresponse.py:241-243` and `aiohttp/web_response.py:348-352`.
- **Severity:** medium.
- **What goes wrong:** Both precompressed `FileResponse` selection and ordinary response compression treat `Accept-Encoding` as an arbitrary lowercase string. A client that sends `Accept-Encoding: gzip;q=0` is explicitly refusing gzip, yet a `.gz` sibling file is selected by `FileResponse`, and `StreamResponse.enable_compression()` enables gzip. Likewise, an unrelated token such as `xgzip` matches `gzip` as a substring.
- **Why it is wrong:** The comments in both paths identify this header as RFC 9110 content-coding negotiation, but lines 241-243 and 349-352 neither tokenize codings nor honor their quality values. In particular, a quality value of zero means that coding is unacceptable, so serving it with `Content-Encoding: gzip` contradicts the request's stated capabilities.
- **Suggested fix:** Parse the comma-separated coding tokens and their parameters once, then select only exact coding matches with an effective quality greater than zero (including wildcard handling). Use that shared parser for both `FileResponse`'s precompressed-variant choice and `StreamResponse._start_compression()`.

### 4. Digest authentication overlooks a valid Digest challenge in a second `WWW-Authenticate` field

- **File and line:** `aiohttp/client_middleware_digest_auth.py:418-429`.
- **Severity:** medium.
- **What goes wrong:** A 401 response that carries, for example, `WWW-Authenticate: Basic realm="legacy"` followed by `WWW-Authenticate: Digest realm="api", nonce="n"` is not retried with Digest authentication. `_authenticate()` uses `response.headers.get("www-authenticate", "")`, which retrieves only one field value; it then returns `False` when that first value is Basic.
- **Why it is wrong:** The middleware's public docstring says it intercepts 401 responses “containing a Digest authentication challenge” (lines 160-162). HTTP permits a server to advertise alternatives through multiple `WWW-Authenticate` field values, so the presence of Basic before Digest must not hide a usable Digest challenge. The parser's own documentation also recognizes multiple challenges (lines 122-125), but `_authenticate()` never passes it the later header values.
- **Suggested fix:** Iterate `response.headers.getall(hdrs.WWW_AUTHENTICATE, ())`, identify the Digest challenge in each field value (including a Digest challenge after other challenges where supported), and parse the first usable one. Only return `False` after no Digest challenge is found.

## Files read

- `aiohttp/cookiejar.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/streams.py`
- `aiohttp/web_request.py`
- `aiohttp/web_response.py`
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/http_parser.py`
- `aiohttp/client.py`
- `aiohttp/multipart.py`
- `tests/test_streams.py`
- `tests/test_web_sendfile_functional.py`
- `tests/test_client_middleware_digest_auth.py`
