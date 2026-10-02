# Code Review: calibre `src/calibre/srv/`

Repo: calibre (https://github.com/kovidgoyal/calibre)
Pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
Scope reviewed: `src/calibre/srv/`

## Method

I read through the server module (routing/auth/http parsing/response
generation/loop/standalone entry point) and additionally ran every file in
scope through Python's `ast.parse()` to catch syntax-level defects, since the
package cannot be imported as a whole in this environment (compiled
extensions not built, Python 3.10 available vs. the 3.14 the checkout
targets). I manually confirmed each `ast.parse()` failure by inspecting the
offending line and, where relevant, checking whether the construct is a
version-specific Python feature (in which case it is not a defect on this
checkout's target interpreter) or an actually-invalid construct.

I also extracted and executed the `get_ranges()` range-header parser in
isolation to confirm a suspected exception-handling gap.

## Defects found

### 1. `content.py:358` — invalid exception syntax, `except ValueError, UnicodeDecodeError:` (Python 2 syntax, invalid in all Python 3 versions)

```python
@endpoint('/reader-background/{encoded_fname}', android_workaround=True)
def reader_background(ctx, rd, encoded_fname):
    base = os.path.abspath(os.path.normpath(os.path.join(config_dir, 'viewer', 'background-images')))
    try:
        q = path_from_root(base, bytes.fromhex(encoded_fname).decode('utf-8'), reject_colon=iswindows)
    except ValueError, UnicodeDecodeError:                     # line 358
        raise HTTPNotFound(f'Reader background {encoded_fname} not found')
```

**What goes wrong:** `except ValueError, UnicodeDecodeError:` is Python 2's
"except type, name" syntax (where `UnicodeDecodeError` would have been bound
as the exception's local name). This syntax was removed in Python 3.0; in
Python 3 a multi-type except clause must be written
`except (ValueError, UnicodeDecodeError):`. This is a hard `SyntaxError`
under every Python 3 interpreter — confirmed directly:

```
$ python3 -c "import ast; ast.parse(open('content.py').read())"
SyntaxError: multiple exception types must be parenthesized (<unknown>, line 358)
```

**Why it is wrong:** The module cannot be compiled/imported at all under
Python 3, on any 3.x version, not just the specific interpreter available in
this environment. Since `content.py` is imported unconditionally by the
content-server routing (`routes.py`/`handler.py` wire up its `@endpoint`s),
this breaks import of the whole `calibre.srv` content-serving surface, not
just the `reader_background` endpoint.

**Severity:** high — the module fails to import, which is a build-breaking
defect, not just a runtime edge case.

**Suggested fix:**
```python
    except (ValueError, UnicodeDecodeError):
        raise HTTPNotFound(f'Reader background {encoded_fname} not found')
```

### 2. `loop.py:570` — same invalid exception syntax, `except AttributeError, OSError:`

```python
        if hasattr(socket, 'AF_INET6') and self.socket.family == socket.AF_INET6 and self.bind_address[0] in ('::', '::0', '::0.0.0.0'):
            try:
                self.socket.setsockopt(IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except AttributeError, OSError:                    # line 570
                # Apparently, the socket option is not available in
                # this machine's TCP stack
                pass
```

**What goes wrong / why it is wrong:** Same Python-2-only construct as
defect 1, confirmed with `ast.parse()`:
```
SyntaxError: multiple exception types must be parenthesized (<unknown>, line 570)
```
`loop.py` implements `ServerLoop`/`Connection`, which almost every other
file in `src/calibre/srv/` imports directly (`http_request.py`,
`http_response.py`, `web_socket.py`, `standalone.py`, etc.). A syntax error
here prevents the entire server subsystem from being imported at all.

**Severity:** high.

**Suggested fix:**
```python
            except (AttributeError, OSError):
                pass
```

### 3. `standalone.py:209` — same invalid exception syntax, `except KeyboardInterrupt, EOFError:`

```python
    if opts.manage_users:
        try:
            manage_users_cli(opts.userdb, args[1:])
        except KeyboardInterrupt, EOFError:                    # line 209
            raise SystemExit(_('Interrupted by user'))
        raise SystemExit(0)
```

**What goes wrong / why it is wrong:** Same construct, confirmed with
`ast.parse()`:
```
SyntaxError: multiple exception types must be parenthesized (<unknown>, line 209)
```
`standalone.py` is the `calibre-server` command-line entry point
(`main()`); this breaks `--manage-users` / the whole standalone server
executable from importing.

**Severity:** high.

**Suggested fix:**
```python
        except (KeyboardInterrupt, EOFError):
            raise SystemExit(_('Interrupted by user'))
```

(Note: I found one other superficially similar `ast.parse()` failure, in
`routes.py:112`, `def endpoint[**P](...)`. That is *not* a defect: it's PEP
695 generic-function syntax, valid from Python 3.12 onward. It only fails to
parse under the Python 3.10 interpreter available in this sandbox, which is
older than what this checkout targets (Python 3.14 per the task
instructions). I am not reporting it as a defect.)

### 4. `http_response.py:137-138` — `get_ranges()` raises an unhandled `ValueError` on a `Range` header entry with no `-` in it, instead of skipping it as the function's own docstring and surrounding code promise

```python
def get_ranges(headervalue, content_length):  # {{{
    """Return a list of ranges from the Range header. If this function returns
    an empty list, it indicates no valid range was found."""
    ...
    for brange in byteranges.split(','):
        start, stop = (x.strip() for x in brange.split('-', 1))   # line 138
        if start:
            ...
            try:
                start, stop = int(start), int(stop)
            except Exception:
                continue
            ...
        elif stop:
            ...
```

**What goes wrong, on what input:** A `Range` header whose byte-range-spec
has no hyphen at all, e.g. `Range: bytes=500`, causes
`brange.split('-', 1)` to return a 1-element list, and the
tuple-unpacking `start, stop = (...)` then raises
`ValueError: not enough values to unpack (expected 2, got 1)`, uncaught.
I reproduced this directly against the function body:

```
>>> get_ranges('bytes=500', 1000)
Traceback (most recent call last):
  ...
ValueError: not enough values to unpack (expected 2, got 1)
```

This exception is not caught anywhere between `get_ranges()` and
`HTTPConnection.finalize_output()` (`http_response.py`), which calls it
directly at line 760 (`ranges = get_ranges(request.inheaders.get('Range'), ...)`)
with no surrounding `try`/`except`. It propagates up to the connection's
event-processing loop (`loop.py`, `handle_event`'s `except Exception as e:`
block around line 662), which logs it as an "Unhandled exception" and turns
it into a generic `500 Internal Server Error` for that request (via
`report_unhandled_exception` → `simple_response(INTERNAL_SERVER_ERROR)`).

**Why it is wrong:** The function's own docstring states its contract is to
return a list ("an empty list... indicates no valid range was found") for
any input that doesn't yield a valid range, and every other kind of
malformed range-spec in this same loop is deliberately absorbed —
non-numeric bounds are caught by the `except Exception: continue` a few
lines down, `start >= content_length` and `stop < start` are `continue`d.
Only the "no dash present" case is unguarded, which is inconsistent with the
function's evident intent to tolerate malformed client-supplied `Range`
headers and simply ignore bad range-specs rather than error out. A
client sending a slightly malformed (but simple, plausible) `Range` header
gets a 500 instead of the resource being served normally/without ranges.

**Severity:** medium (does not crash the server — it's caught by the
top-level `Connection.handle_event` handler in `loop.py` and turned into a
per-request 500 — but it is a clear, reproducible correctness bug:
attacker- or client-controlled input reliably produces an unhandled
exception and an incorrect status code where the code's own contract calls
for graceful degradation).

**Suggested fix:** wrap the split/unpack in the same defensive style used
for the rest of the loop, e.g.:

```python
    for brange in byteranges.split(','):
        start, sep, stop = brange.partition('-')
        if not sep:
            continue
        start, stop = start.strip(), stop.strip()
        if start:
            ...
```

## Areas checked but no defect found

- `auth.py` (Digest/Basic auth, nonce synthesis/validation, ban list): logic
  reads correctly against RFC 2617 comments; nonce/ban-list locking looks
  sound. `AuthController.check()` uses `uc.get(un) == pw`, a non-constant-time
  string comparison, which is a timing-attack theoretical concern but not
  something I can confirm as an exploitable defect distinct from calibre's
  documented threat model in this class's own docstring (it already
  acknowledges cookie-based auth is sniffable and recommends HTTPS via
  reverse proxy), so I'm not reporting it as a confirmed defect.
- `http_request.py` (request-line/header/chunked-body parsing): checked
  Content-Length vs. Transfer-Encoding conflict handling, chunk-size limit
  accounting, and header continuation-line handling; found no defects.
- `utils.py` (`MultiDict`, `Offsets`, log rotation): reviewed, no defects
  found.
- `web_socket.py`: partially reviewed (frame header parsing); relies on the
  unbuilt `calibre_extensions.speedup` C extension for masking, so I could
  not exercise it at runtime and did not find a confirmable defect by
  inspection alone.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/content.py` (partial — favicon/icon/reader-background/background-image endpoints)
- `src/calibre/srv/books.py` (partial — path-handling helpers)
- `src/calibre/srv/loop.py` (partial — `ReadBuffer`, `setup_socket`, event-loop exception handling)
- `src/calibre/srv/routes.py` (partial — `endpoint` decorator signature)
- `src/calibre/srv/standalone.py` (partial — `main()` around `--manage-users`)
- `src/calibre/srv/web_socket.py` (partial — imports, frame constants, `ReadFrame.read_header`)
- All files in `src/calibre/srv/*.py` were additionally run through
  `ast.parse()` to check for syntax errors.
