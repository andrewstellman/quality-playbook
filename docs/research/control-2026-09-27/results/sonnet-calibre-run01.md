# Code review: calibre `src/calibre/srv/`

Repo: https://github.com/kovidgoyal/calibre
Pinned commit: `7691f4f1a155d799afdfec99e2cdc2716c178402`
Scope: `src/calibre/srv/`

## Defects found

### 1. `content.py:358` — Python-2-only exception syntax; module fails to compile

```python
@endpoint('/reader-background/{encoded_fname}', android_workaround=True)
def reader_background(ctx, rd, encoded_fname):
    base = os.path.abspath(os.path.normpath(os.path.join(config_dir, 'viewer', 'background-images')))
    try:
        q = path_from_root(base, bytes.fromhex(encoded_fname).decode('utf-8'), reject_colon=iswindows)
    except ValueError, UnicodeDecodeError:      # line 358
        raise HTTPNotFound(f'Reader background {encoded_fname} not found')
```

`except ValueError, UnicodeDecodeError:` is Python 2 syntax for binding the exception instance to a name (`except Exc, var:`). It was removed in Python 3.0 (over 15 years ago) and is a hard `SyntaxError` in every Python 3 version, including the 3.14 this codebase targets:

```
SyntaxError: multiple exception types must be parenthesized
```

Confirmed with `ast.parse()` on the file — it does not compile at all. Since `content.py` implements most of the content-server endpoints (`/get`, `/icon`, `/reader-background`, etc.), any attempt to import this module raises `SyntaxError` and the whole module — not just this one function — becomes unusable.

- Severity: **high**
- Fix: parenthesize the tuple and bind with `as` if the exception object is needed: `except (ValueError, UnicodeDecodeError):`

### 2. `loop.py:570` — same Python-2 exception syntax; breaks the core event loop

```python
    def setup_socket(self):
        ...
        if hasattr(socket, 'AF_INET6') and self.socket.family == socket.AF_INET6 and self.bind_address[0] in ('::', '::0', '::0.0.0.0'):
            try:
                self.socket.setsockopt(IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except AttributeError, OSError:     # line 570
                # Apparently, the socket option is not available in
                # this machine's TCP stack
                pass
```

Same defect as #1: `except AttributeError, OSError:` is invalid Python 3 syntax (`SyntaxError: multiple exception types must be parenthesized`). `loop.py` implements `ServerLoop`/`Connection`, the core of the whole `srv` package's networking; almost every other module in this directory (`http_request.py`, `http_response.py`, `web_socket.py`, `auth.py`, etc.) imports from it. A syntax error here means the entire content server cannot start.

- Severity: **high**
- Fix: `except (AttributeError, OSError):`

### 3. `standalone.py:209` — same Python-2 exception syntax; breaks the CLI entry point

```python
    if opts.manage_users:
        try:
            manage_users_cli(opts.userdb, args[1:])
        except KeyboardInterrupt, EOFError:      # line 209
            raise SystemExit(_('Interrupted by user'))
        raise SystemExit(0)
```

Same defect again: `except KeyboardInterrupt, EOFError:` fails to parse under Python 3. `standalone.py` contains `main()` for the `calibre-server` command-line entry point, so the server binary cannot even be imported/launched.

- Severity: **high**
- Fix: `except (KeyboardInterrupt, EOFError):`

(I grepped the whole `srv/` tree for the old comma-exception pattern and other Python-2-isms — `.has_key(`, `xrange(`, `print "`, `basestring`, `unichr(` — and these three sites in `content.py`, `loop.py`, and `standalone.py` are the only comma-exception occurrences; no other Python-2-only constructs were found.)

### 4. `http_request.py:426` (`read_chunk_length`) — negative chunk size bypasses the request-body size limit and desyncs chunked decoding

```python
def read_chunk_length(self, inheaders, line_buf, buf, bytes_read, event):
    line = self.readline(line_buf)
    if line is None:
        return
    bytes_read[0] += len(line)
    try:
        chunk_size = int(line.strip(), 16)                       # accepts a leading '-'
    except Exception:
        return self.simple_response(http.client.BAD_REQUEST, f'{reprlib.repr(line.strip())} is not a valid chunk size')
    if bytes_read[0] + chunk_size + 2 > self.max_request_body_size:
        return self.simple_response(...)                         # intended cap on total body size
    if chunk_size == 0:
        self.set_state(READ, self.read_chunk_separator, inheaders, Accumulator(), buf, bytes_read, last=True)
    else:
        self.set_state(READ, self.read_chunk, inheaders, buf, chunk_size, buf.tell() + chunk_size, bytes_read)
```

`int(line.strip(), 16)` happily accepts a signed value such as `b'-1'` (verified: `int(b'-1'.strip(), 16) == -1`). Nothing rejects a negative chunk size before it is used.

With a negative `chunk_size`:
- The size-limit check `bytes_read[0] + chunk_size + 2 > self.max_request_body_size` is *harder* to trip (the running total goes down instead of up), so it doesn't reject anything — it actually defeats the very limit it's meant to enforce.
- `read_chunk` is entered with `end = buf.tell() + chunk_size`, i.e. `end < buf.tell()`. In `HTTPRequest.read()`:

```python
def read(self, buf, endpos):
    size = endpos - buf.tell()
    if size > 0:
        ...
    else:
        return True
```
  `size` is negative, so `read()` returns `True` immediately without consuming any bytes from the socket, and the state machine treats the (nonexistent) chunk as fully read. `bytes_read[0] += chunk_size` then *decrements* the tracked byte count.

A client can therefore send an endless stream of minimal frames like `-1\r\n\r\n` (each one decrements `bytes_read[0]` and satisfies the "chunk separator" check for free, since no real payload bytes were ever consumed from the wire) and keep the connection reading indefinitely while `bytes_read[0]` never approaches `self.max_request_body_size`. This defeats the documented purpose of the check ("Chunked request is larger than {max} bytes") and ties up a request-handling connection/thread indefinitely, i.e. a request-smuggling/resource-exhaustion vector via a value the code never validates as non-negative.

- Severity: **medium** (logic error that defeats a documented safety limit; requires a malicious/misbehaving client, not remotely as severe as the syntax errors above, but a real protocol/DoS defect)
- Fix: reject negative (and, per RFC 7230 §4.1, any non-hex-digit) chunk sizes explicitly, e.g.:
  ```python
  raw = line.strip()
  if not raw or any(c not in b'0123456789abcdefABCDEF' for c in raw):
      return self.simple_response(http.client.BAD_REQUEST, f'{reprlib.repr(raw)} is not a valid chunk size')
  chunk_size = int(raw, 16)
  ```

## Not reported as defects (considered, but not confident enough / out of scope)

- `auth.py`: `AuthController.check()` compares the stored password to the supplied one with plain `==` rather than a constant-time comparison (`hmac.compare_digest`), which is a timing side-channel in Basic auth. This looks like long-standing, deliberate design in this codebase (the class docstring already accepts a worse vulnerability — cookie-based session hijacking over plain HTTP — as a known tradeoff for a "private server"), and I have no direct evidence this specific line changed at the pinned commit, so I'm not confident enough to list it as an injected defect, just flagging it for awareness.
- `web_socket.py`: `MESSAGE_TOO_BIG` (close code 1009) is defined but never raised/used anywhere in the file. This looks like an incomplete feature (no max-message-size enforcement across fragmented messages) rather than a clear logic bug — the per-frame code path doesn't build up an unbounded in-memory buffer that I could find, so I did not treat it as a confirmed defect.
- `utils.py`: `Offsets.__init__` raises `HTTPNotFound` whenever `offset >= total`, which is also true when `total == 0` and `offset == 0`. Callers I traced (`opds.py`) mostly guard against an empty `ids`/`items` collection before constructing `Offsets`, so I could not confirm a reachable path where this actually misfires.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py` (partial, header/range-parsing sections)
- `src/calibre/srv/utils.py`
- `src/calibre/srv/web_socket.py` (frame parsing, control-frame handling)
- `src/calibre/srv/content.py` (icon/reader-background/get endpoints)
- `src/calibre/srv/opds.py` (`Offsets` call sites, `get_acquisition_feed`, `get_navcatalog`)
- `src/calibre/srv/loop.py` (`setup_socket` and surrounding `ServerLoop`/`Connection` code)
- `src/calibre/srv/standalone.py` (`main`, `manage_users` CLI path)
- `src/calibre/srv/routes.py` (checked only for syntax validity — uses PEP 695 generic-function syntax valid on Python 3.12+/3.14, not a defect)
- `src/calibre/srv/tests/http.py` (existing chunked-encoding test coverage, to confirm the negative-chunk-size case is untested)

I also ran `ast.parse()` against every `.py` file in `src/calibre/srv/` (top level) as a mechanical check for syntax errors, which is how defects #1–#3 were located and confirmed.
