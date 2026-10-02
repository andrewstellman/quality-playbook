model: gpt-5.6-terra
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 22:19:21 UTC; finished 2026-09-28 22:22:29 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review — e11d2836203a21bec59095498e578d37801027e7

## Findings

### 1. `StreamReader.readuntil()` misses multi-byte separators split across buffered reads

- **File/line:** `aiohttp/streams.py:399-407`
- **Severity:** medium
- **What goes wrong:** `readuntil(b"\r\n")` searches only `self._buffer[0]`. If a peer delivers `b"foo\r"` and then `b"\nbar\r\n"`, the first CRLF crosses the two buffer entries and is not found. The method consumes both entries and returns `b"foo\r\nbar\r\n"`, rather than stopping at the first delimiter (`b"foo\r\n"`). This can merge adjacent protocol records whenever the delimiter crosses a transport-read boundary.
- **Why this is wrong:** `readline()` delegates directly to `readuntil()` at lines 378-379, and `readuntil(separator)` promises the normal delimiter-based read behavior. Lines 399-403 call `find(separator, ...)` on only the current deque entry and then remove that entry. No state preserves the trailing `len(separator) - 1` bytes to compare with the next entry, so cross-entry delimiters cannot be detected.
- **Suggested fix:** Retain and compare a suffix of up to `len(separator) - 1` bytes from the consumed data with the next buffer entry, or search a non-destructively assembled window spanning adjacent entries. Once found, consume only through the end of that first separator and leave subsequent bytes buffered. Add a regression case that feeds `b"foo\r"` and `b"\nbar\r\n"` separately and expects the first call to return only `b"foo\r\n"`.

### 2. Saving over an existing cookie file leaves its old permissions intact

- **File/line:** `aiohttp/cookiejar.py:166-175`
- **Severity:** medium
- **What goes wrong:** Calling `CookieJar.save()` on an already-existing cookie file with permissive mode (for example `0644`) rewrites the file but leaves it readable by other local users. Cookie jars can contain authentication and session tokens.
- **Why this is wrong:** The comment at lines 166-168 explicitly says the file must use `0o600` to protect sensitive credential data and “enforce least-privilege access.” The `mode` argument passed through the `opener` is used by `os.open()` only when a new file is created; opening an existing file with `"w"` truncates it but does not change its permission bits. Thus this path does not enforce the stated protection for the common refresh/overwrite case.
- **Suggested fix:** After opening the file, call `os.fchmod(f.fileno(), 0o600)` before writing (with an appropriate platform fallback if needed), or explicitly chmod the resolved file before serializing. Add a test that creates a cookie file with mode `0644`, saves a jar to it, and verifies mode `0600` afterward.

## Files read

- `aiohttp/base_protocol.py`
- `aiohttp/client.py`
- `aiohttp/client_reqrep.py`
- `aiohttp/client_ws.py`
- `aiohttp/compression_utils.py`
- `aiohttp/connector.py`
- `aiohttp/cookiejar.py`
- `aiohttp/formdata.py`
- `aiohttp/http_parser.py`
- `aiohttp/http_writer.py`
- `aiohttp/streams.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_request.py`
- `aiohttp/web_response.py`
- `aiohttp/web_ws.py`
- `aiohttp/_cookie_helpers.py`
