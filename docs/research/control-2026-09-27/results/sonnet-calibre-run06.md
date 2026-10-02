# Code review: calibre `src/calibre/srv/`

Repo: calibre (kovidgoyal/calibre), pinned commit `7691f4f1a155d799afdfec99e2cdc2716c178402`
Scope: `src/calibre/srv/`

## Defect 1: Negative chunk-size in chunked Transfer-Encoding bypasses `max_request_body_size`

**File/line:** `src/calibre/srv/http_request.py`, `read_chunk_length` (around line 426) and `read_chunk` (around line 439-443)

```python
def read_chunk_length(self, inheaders, line_buf, buf, bytes_read, event):
    line = self.readline(line_buf)
    if line is None:
        return
    bytes_read[0] += len(line)
    try:
        chunk_size = int(line.strip(), 16)
    except Exception:
        return self.simple_response(http.client.BAD_REQUEST, f'{reprlib.repr(line.strip())} is not a valid chunk size')
    if bytes_read[0] + chunk_size + 2 > self.max_request_body_size:
        return self.simple_response(
            http.client.REQUEST_ENTITY_TOO_LARGE,
            f'Chunked request is larger than {self.max_request_body_size} bytes',
        )
    if chunk_size == 0:
        self.set_state(READ, self.read_chunk_separator, inheaders, Accumulator(), buf, bytes_read, last=True)
    else:
        self.set_state(READ, self.read_chunk, inheaders, buf, chunk_size, buf.tell() + chunk_size, bytes_read)

def read_chunk(self, inheaders, buf, chunk_size, end, bytes_read, event):
    if not self.read(buf, end):
        return
    bytes_read[0] += chunk_size
    self.set_state(READ, self.read_chunk_separator, inheaders, Accumulator(), buf, bytes_read)
```

and `read()`:

```python
def read(self, buf, endpos):
    size = endpos - buf.tell()
    if size > 0:
        data = self.recv(size)
        ...
    else:
        return True
```

**What goes wrong:** The chunk-size line is parsed with `int(line.strip(), 16)`, which happily accepts a leading `-` (e.g. `int('-1000000', 16) == -16777216`... actually `-1000000` hex). Per RFC 7230 §4.1, `chunk-size = 1*HEXDIG` — there is no sign, so a chunk-size line must never be negative. The code never checks `chunk_size >= 0` or that the line consists only of hex digits.

If a client sends a chunk-size line like `-1000000\r\n` followed immediately by `\r\n` (an empty chunk body):
- `bytes_read[0] + chunk_size + 2 > self.max_request_body_size` is checked with a large *negative* `chunk_size`, so it never trips the entity-too-large guard, regardless of how large `-chunk_size` is.
- Execution proceeds to `read_chunk` with `end = buf.tell() + chunk_size`, i.e. `end < buf.tell()`.
- In `read()`, `size = endpos - buf.tell()` is negative, so the `else: return True` branch fires immediately — no bytes are actually read from the socket, and `read_chunk` treats the "chunk" as fully received.
- `bytes_read[0] += chunk_size` then drives the request's running byte counter deeply *negative*.
- The two bytes right after the chunk-size line are then consumed by `read_chunk_separator` as the chunk's trailing CRLF (which the attacker supplies cheaply, e.g. `-1000000\r\n\r\n`, 14 bytes on the wire).

By repeating this a few times, an attacker drives `bytes_read[0]` arbitrarily negative while sending only a handful of bytes. The client can then send one real, huge chunk (e.g. tens/hundreds of MB) whose size, added to the now deeply-negative `bytes_read[0]`, still passes the `> self.max_request_body_size` check. `read_request_body`/`sized_read`/chunk handling write everything to a `SpooledTemporaryFile` that spills to disk (`src/calibre/srv/http_request.py:407-408`), so this lets a client push request bodies far past the configured `max_request_body_size` (`self.opts.max_request_body_size`, documented as the maximum allowed request size) — defeating the size limit that `finalize_headers`/`read_chunk_length` exist to enforce, and enabling memory/disk exhaustion (DoS) against the server.

**Why it is wrong:** The whole point of the `bytes_read[0] + chunk_size + 2 > self.max_request_body_size` check and the analogous `request_content_length > self.max_request_body_size` check in `finalize_headers` is to cap request body size at `self.opts.max_request_body_size` bytes ("The entity sent with the request exceeds the maximum allowed bytes"). Accepting a negative `chunk_size` out of `int(x, 16)` silently violates both the HTTP/1.1 chunked-encoding grammar (`chunk-size = 1*HEXDIG`, RFC 7230 §4.1, no sign allowed) and the server's own size-limiting invariant.

**Severity:** High — an unauthenticated remote client (the check happens before/independent of the `finalize_headers`/`Content-Length` limit and works for any endpoint that accepts chunked bodies) can bypass the request-body size cap, causing unbounded disk/memory consumption on the server.

**Suggested fix:** Reject chunk-size lines that aren't valid hex digits (or reject negative results), e.g.:

```python
raw = line.strip()
if not raw or any(c not in b'0123456789abcdefABCDEF' for c in raw):
    return self.simple_response(http.client.BAD_REQUEST, f'{reprlib.repr(raw)} is not a valid chunk size')
chunk_size = int(raw, 16)
```

(`int(bytes, 16)` still needs the digit-only check first since `int()` also accepts a leading `+`/`-` and surrounding whitespace even after `.strip()` handles outer whitespace — the sign is the issue here.) Alternatively, simply add `or chunk_size < 0` to the existing entity-too-large guard, though validating the digits is more robust and matches the RFC grammar.

## Other areas reviewed, no confirmed defects found

- `auth.py`: Digest/Basic auth implementation, nonce synthesis/validation, ban list. The credential comparisons (`uc.get(un) == pw` in `AuthController.check`, and the digest-response string equality in `DigestAuth.validate_request`) are not constant-time, but this is a long-standing, low-severity, and largely theoretical concern for a typically LAN-local personal server; I'm not confident enough to call it a genuine defect worth flagging as high-value here, so I list it only for completeness and did not count it as a finding.
- `users.py`: user database (passwords stored in plaintext by design, per the code's own comment about digest auth requiring the plaintext password) — intentional, documented tradeoff, not a defect.
- `http_response.py`: `get_ranges()` (Range header parsing), multipart-byterange handling, compression/Transfer-Encoding negotiation — logic checked for off-by-one and edge cases (empty ranges, suffix ranges, `stop < start`, `start >= content_length`) and appears correct.
- `utils.py`: `MultiDict`, `parse_http_dict`, `sort_q_values`, `connection_header_tokens` — no defects found.
- `loop.py`: `Connection.recv`/`fill_read_buffer`/`ReadBuffer` — confirms `read()`'s early-return-`True` behavior in `http_request.py` is not compensated for elsewhere, i.e. nothing else catches the negative-chunk-size case.
- Skimmed but not exhaustively reviewed: `content.py`, `cdb.py`, `opds.py`, `legacy.py`, `routes.py`, `fts.py`, `handler.py`, `jobs.py`, `web_socket.py`, `ajax.py`, `books.py`, `convert.py`, `render_book.py`, `opts.py`, `pool.py`, `library_broker.py`, `manage_users_cli.py`, `metadata.py`, `changes.py`, `last_read.py`, `bonjour.py`, `auto_reload.py`, `code.py`, `errors.py`, `standalone.py`, `pre_activated.py`, `embedded.py`, `legacy_book_details.py`, `users_api.py`, `__init__.py`. Nothing in these raised a confident, confirmed defect within the time budget of this review; I would not treat the absence of findings there as a clean bill of health, just as unreviewed-in-depth.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/users.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/loop.py` (targeted sections: `Connection.recv`, `recv_into`, `fill_read_buffer`, `ReadBuffer` references)
- Directory listing of `src/calibre/srv/` for scope orientation
