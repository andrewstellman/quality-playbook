# Code Review — aiohttp

- Repo: aiohttp (https://github.com/aio-libs/aiohttp)
- Pinned commit: e11d2836203a21bec59095498e578d37801027e7
- Review scope: `aiohttp/` (package, excluding tests)
- Checkout: `/tmp/control/aiohttp` (read-only)

## Result

**No defects found that meet the required confidence bar.**

I reviewed the highest-risk parsing and concurrency code in the `aiohttp/` package — manual byte parsing, buffer/length arithmetic, header parsing, cookie domain/path matching, multipart boundary parsing, chunked-encoding handling, redirect/auth logic, connection-pool reuse, HTTP range/conditional-request handling, and WebSocket frame parsing — looking for logic errors, edge-case mishandling, standards violations, error-handling mistakes, concurrency problems, and API misuse.

Two of the most novel/custom code paths were verified with runnable repros rather than by inspection alone:

- **`BodyPartReader._read_chunk_from_stream` / `_align_base64_chunk`** (`aiohttp/multipart.py`) — a heavily customized base64-carry/boundary-detection implementation. I wrote and ran a repro (`repro_multipart3.py`) that round-trips base64-encoded multipart bodies through `BodyPartReader.read(decode=True)` at payload sizes from 10 to 500,000 bytes, crossing the 8192-byte internal chunk boundary at various offsets. All cases decoded correctly (`decoded == raw`). I also hand-traced the "walk back to find a whole quartet" carry logic for edge cases (a single truncated quartet, non-base64 bytes interspersed) — it is correct. The one case where it deliberately does not carry (fewer than 4 base64 chars available in a non-final chunk) is explicitly documented in the code as an accepted tradeoff, not an oversight.
- **Nested-boundary / epilogue push-back logic** in `MultipartReader._read_boundary` / `_maybe_release_last_part` — traced the interaction between the list-based `_unread` stack and `BodyPartReader._unread` deque; ordering is preserved correctly for the documented code path (confirmed with a basic two-part multipart repro, `repro_multipart.py`).

Also traced carefully, without finding defects:

- **`aiohttp/web_fileresponse.py`** — Range / If-Range / If-Match / If-None-Match / If-Modified-Since precedence and ETag weak/strong comparison against RFC 9110 §13.1, including the tail-range (`bytes=-N`) and out-of-range (`start >= file_size` → 416) edge cases.
- **`aiohttp/http_parser.py`** — chunked transfer-encoding state machine, chunk-extension stripping, Transfer-Encoding/Content-Length conflict rejection (request-smuggling defense), and the deliberate strict-vs-lax asymmetry between `HttpRequestParser._is_chunked_te` (rejects duplicate/malformed `chunked`) and `HttpResponseParser._is_chunked_te` (lax, checks only the last token) — intentional per the inline RFC 9112 citations in the code.
- **`aiohttp/cookiejar.py`** — RFC 6265 domain-match, default-path computation (including the `rfind("/")` slicing math), host-only cookie tracking, expiry-heap bookkeeping.
- **`aiohttp/connector.py`** — `_available_connections` per-host/global limit arithmetic, `_get`/`_release`/`_release_acquired` connection-pool acquire/reuse/close paths, `_wait_for_available_connection`'s re-check loop (race between limit check and acquisition), and the placeholder-based `connect()` path (no `await` between adding the real proto to `_acquired` and returning, as required by an inline comment).
- **`aiohttp/client.py`** — cross-origin redirect header stripping uses `popall` for `Authorization` / `Cookie` / `Proxy-Authorization` (correct — matches the documented 3.14.3 fix for a prior "only first header dropped" bug), env-proxy-auth re-resolution on each redirect hop.
- **`aiohttp/client_middleware_digest_auth.py`** — RFC 7616 HA1/HA2/response digest construction, `-sess` algorithm handling, nonce-count tracking, protection-space prefix matching.
- **`aiohttp/_websocket/reader_py.py`** — frame header/length/mask parsing, control-frame ≤125-byte enforcement, fragmentation/continuation-opcode validation, RSV-bit and compressed-bit state tracking, size-limit check against `max_msg_size` before buffering payload.
- **`aiohttp/http_writer.py`, `aiohttp/web_response.py`, `aiohttp/web_protocol.py`, `aiohttp/compression_utils.py`, `aiohttp/formdata.py`, `aiohttp/payload.py`, `aiohttp/base_protocol.py`, `aiohttp/client_proto.py`** — Content-Length/chunked serialization, keep-alive timeout rescheduling, decompression `max_length` bounds and concatenated-member handling, read-timeout drop/reschedule around pause/resume.

Nothing found rises to a confirmed, citable defect (confident + specific line citation + a standard/doc/comment it contradicts). Given the ground covered, this report states that plainly rather than including a padded, low-confidence finding.

## No additional defects found with confidence

Beyond the above: none.

## Files read

- `aiohttp/web_fileresponse.py`
- `aiohttp/multipart.py`
- `aiohttp/http_parser.py`
- `aiohttp/cookiejar.py`
- `aiohttp/connector.py`
- `aiohttp/client_reqrep.py` (partial — redirect/release/connection-lifecycle sections)
- `aiohttp/streams.py`
- `aiohttp/web_request.py` (headers/range/etag/cookie sections)
- `aiohttp/web_response.py`
- `aiohttp/formdata.py`
- `aiohttp/helpers.py` (ETag/date/is_ip_address/must_be_empty_body sections)
- `aiohttp/client_proto.py`
- `aiohttp/http_writer.py`
- `aiohttp/web_protocol.py` (request loop / keepalive sections)
- `aiohttp/client.py` (redirect loop, proxy/auth sections)
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/client_middlewares.py` (grep survey)
- `aiohttp/resolver.py` (partial)
- `aiohttp/web_middlewares.py`
- `aiohttp/compression_utils.py`
- `aiohttp/payload.py` (partial)
- `aiohttp/base_protocol.py`
- `aiohttp/_websocket/reader_py.py`
- `CHANGES.rst`, `aiohttp/__init__.py` (version context only)

## Verification artifacts

Repro scripts run against the checkout to confirm multipart base64 decoding correctness across chunk-boundary-crossing payload sizes and basic two-part multipart parsing (executed in the isolated work directory, not against the read-only checkout).
