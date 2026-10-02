model: gpt-5.6-terra
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 22:22:38 UTC; finished 2026-09-28 22:27:49 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review

## Defects

### 1. `StreamReader.readuntil()` misses a multi-byte separator split between buffered reads

- **Location:** `aiohttp/streams.py:399-407`
- **Severity:** medium
- **What goes wrong:** `readuntil(b"\r\n")` does not recognize a delimiter when the
  preceding buffered block ends in `b"\r"` and the following block begins with
  `b"\n"`. It consumes both blocks as ordinary data and then waits for more data
  (or returns data past the delimiter at EOF), instead of returning through the
  delimiter. Socket reads may split the two bytes this way.
- **Why it is wrong:** `readuntil` accepts an arbitrary `separator`, but it calls
  `self._buffer[0].find(separator, offset)` independently for each deque entry.
  No state is retained for a suffix of one entry that is a prefix of the separator,
  so a cross-entry match is impossible. This violates the method's delimiter
  contract and differs from the normal stream-reader behavior expected by callers
  using CRLF framing.
- **Suggested fix:** retain up to `len(separator) - 1` trailing bytes while scanning,
  or search a window composed from the unread suffix of the current buffer entry
  plus the next entry before consuming either. Preserve the maximum-length check
  over the bytes actually consumed.

### 2. `TextIOPayload` advertises the source file's byte count even when it transcodes the text

- **Location:** `aiohttp/payload.py:535-560`, used by `aiohttp/payload.py:779-808`
  and `aiohttp/client_reqrep.py:1279-1284`
- **Severity:** medium
- **What goes wrong:** Passing a text file with an encoding different from the
  `TextIOPayload` output encoding produces a wrong `Content-Length` and truncates
  the request body. For example, an ASCII file containing `"a"` used as
  `TextIOPayload(open(..., encoding="utf-8"), encoding="utf-16")` has a one-byte
  source file, but the encoded payload is four bytes (BOM plus one UTF-16 code
  unit). The request sets `Content-Length: 1`, and `write_with_length()` writes only
  the first byte of the encoded chunk.
- **Why it is wrong:** the inherited `IOBasePayload.size` returns
  `os.fstat(...).st_size - self._start_position` (the source file's bytes), while
  `TextIOPayload._read_and_available_len()` and `_read()` read characters and then
  encode them with `self._encoding`. `ClientRequest._update_body_from_data()` uses
  `body.size` to set `Content-Length`, and the writer explicitly slices every chunk
  to that content length. Thus the advertised and transmitted representation is
  neither the source file nor the requested text encoding.
- **Suggested fix:** make `TextIOPayload.size` return `None` unless the exact encoded
  byte length is known, causing chunked transfer, or compute the encoded length from
  the configured output encoding without consuming an unseekable stream. When a
  length is supplied, constrain writes in encoded bytes rather than using that byte
  count as a character-read limit.

### 3. Server compression treats encodings explicitly forbidden by `Accept-Encoding` as acceptable

- **Location:** `aiohttp/web_response.py:342-352`; the same faulty selection appears
  in `aiohttp/web_fileresponse.py:237-250`
- **Severity:** medium
- **What goes wrong:** a request with `Accept-Encoding: gzip;q=0` receives a gzip
  response when compression is enabled (or a `.gz` sibling through `FileResponse`).
  The substring checks also treat arbitrary tokens such as `xgzip` as accepting
  gzip.
- **Why it is wrong:** both paths read the `Accept-Encoding` request header and then
  select an encoding solely with `if value in accept_encoding` / `if file_encoding
  not in accept_encoding`. The surrounding comment identifies this as
  `Accept-Encoding` processing and cites RFC 9110 section 8.4.1; in that header,
  `q=0` means the coding is unacceptable. Sending it defeats content negotiation
  and can make the representation unusable to the client.
- **Suggested fix:** parse the comma-separated codings and their quality values,
  match coding tokens exactly (including wildcard and identity rules), and select
  only a coding with a positive quality value. Share that negotiation helper between
  `StreamResponse` and `FileResponse`.

### 4. The singleton empty payload reports a chunk boundary for non-chunked empty bodies

- **Location:** `aiohttp/streams.py:598-603, 667-672`
- **Severity:** low
- **What goes wrong:** after any caller invokes `await EMPTY_PAYLOAD.readchunk()`
  once, every later caller gets `(b"", True)`. `EMPTY_PAYLOAD` is shared across
  requests, so a response or request with no body can observe a chunk boundary based
  on unrelated prior traffic. The same reader returns `(b"", False)` only on its
  first use.
- **Why it is wrong:** `StreamReader.readchunk()` documents that the boolean is true
  only when data corresponds to the end of an HTTP chunk and is always false for
  non-chunked transfer (`aiohttp/streams.py:468-475`). `EMPTY_PAYLOAD` is a module
  singleton (`aiohttp/streams.py:681`) used for no-body parser results
  (`aiohttp/http_parser.py:514-516`), yet `EmptyStreamReader.readchunk()` mutates
  its `_read_eof_chunk` state and returns true on subsequent calls.
- **Suggested fix:** make `EmptyStreamReader.readchunk()` always return `(b"", False)`
  or stop using a shared mutable reader for empty payloads.

## Files read

`aiohttp/streams.py`, `aiohttp/payload.py`, `aiohttp/web_response.py`,
`aiohttp/web_fileresponse.py`, `aiohttp/http_parser.py`, `aiohttp/http_writer.py`,
`aiohttp/compression_utils.py`, `aiohttp/client.py`, `aiohttp/client_reqrep.py`,
`aiohttp/client_proto.py`, `aiohttp/web_protocol.py`, `aiohttp/web_request.py`,
`aiohttp/web_urldispatcher.py`, `aiohttp/multipart.py`, `aiohttp/formdata.py`,
`aiohttp/cookiejar.py`, `aiohttp/_cookie_helpers.py`, and `aiohttp/helpers.py`.
