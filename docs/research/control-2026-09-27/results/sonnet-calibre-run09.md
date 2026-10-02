# Code review: calibre `src/calibre/srv/`

Repo: calibre, pinned commit `7691f4f1a155d799afdfec99e2cdc2716c178402`
Scope: `src/calibre/srv/`

## Method

Read every `.py` file under `src/calibre/srv/` (list below). Since the checkout doesn't
import as a package here (compiled extensions aren't built), I checked each file for
syntactic and logical correctness with `ast.parse()` / `compile()` as a first pass, then
read the higher-risk modules (auth, HTTP request/response parsing, content serving,
utils) closely for logic errors.

The `ast.parse()` pass flagged `src/calibre/srv/routes.py:112` (`def endpoint[**P](...)`)
as a syntax error, but that is PEP 695 generic-function syntax, valid in Python 3.12+
and expected here since this checkout targets Python 3.14 — not a defect.

## Defects found

### 1. `except ValueError, UnicodeDecodeError:` — Python 2 syntax, fatal `SyntaxError` under Python 3

**File/line:** `src/calibre/srv/content.py:358`

```python
@endpoint('/reader-background/{encoded_fname}', android_workaround=True)
def reader_background(ctx, rd, encoded_fname):
    base = os.path.abspath(os.path.normpath(os.path.join(config_dir, 'viewer', 'background-images')))
    try:
        q = path_from_root(base, bytes.fromhex(encoded_fname).decode('utf-8'), reject_colon=iswindows)
    except ValueError, UnicodeDecodeError:
        raise HTTPNotFound(f'Reader background {encoded_fname} not found')
```

**What goes wrong:** `except ValueError, UnicodeDecodeError:` is Python 2 syntax
(`except ExcType, name:` binds the caught exception to `name`). This form was removed
in Python 3.0; in Python 3 an `except` clause with two comma-separated names must be
written as `except (ValueError, UnicodeDecodeError):`. As written, the module fails to
compile at all — confirmed with `ast.parse()` / `compile()` against this exact file,
which raises `SyntaxError: multiple exception types must be parenthesized`. This is not
version-dependent (the syntax has been gone since Python 3.0), so it fails under the
target Python 3.14 the same as under the Python 3.10 used to check it here.

**Why it is wrong:** The rest of the file (and the whole codebase) is otherwise valid,
modern Python 3 (f-strings, type hints, `match`-free structured code, PEP 695 generics
elsewhere in the package). This single line prevents `calibre.srv.content` — which
implements `/get`, `/get-note*`, `/data-files/*`, `/icon`, `/static`, `/favicon*`, the
whole content-server surface — from being imported by any Python 3 interpreter. The
entire content server is unusable, not just this one endpoint.

**Severity:** high (fatal import-time error; takes down the whole module, not just the
`reader_background` endpoint).

**Suggested fix:**
```python
    except (ValueError, UnicodeDecodeError):
```

### 2. `except KeyboardInterrupt, EOFError:` — same Python 2 syntax error

**File/line:** `src/calibre/srv/standalone.py:209`

```python
    if opts.manage_users:
        try:
            manage_users_cli(opts.userdb, args[1:])
        except KeyboardInterrupt, EOFError:
            raise SystemExit(_('Interrupted by user'))
        raise SystemExit(0)
```

**What goes wrong / why it is wrong:** Same defect class as #1 — `except A, B:` is
Python 2 syntax. `ast.parse()` on this file raises `SyntaxError: multiple exception
types must be parenthesized` at this line. `standalone.py` implements the `calibre-server`
command-line entry point (`main()`, option parsing, `--manage-users`, `ensure_single_instance`,
etc.); this makes the whole standalone server executable fail to even start under Python 3.

**Severity:** high (fatal import-time error in the module that provides the `calibre-server`
executable's entry point).

**Suggested fix:**
```python
        except (KeyboardInterrupt, EOFError):
```

### 3. `except AttributeError, OSError:` — same Python 2 syntax error

**File/line:** `src/calibre/srv/loop.py:570`

```python
        if hasattr(socket, 'AF_INET6') and self.socket.family == socket.AF_INET6 and self.bind_address[0] in ('::', '::0', '::0.0.0.0'):
            try:
                self.socket.setsockopt(IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except AttributeError, OSError:
                # Apparently, the socket option is not available in
                # this machine's TCP stack
                pass
```

**What goes wrong / why it is wrong:** Same defect class again, this time in
`ServerLoop.setup_socket()` in `loop.py`, the core select/epoll event loop that every
other `srv/` module (`http_request.py`, `http_response.py`, `web_socket.py`, `auth.py`
via `Connection`) is built on. `ast.parse()` confirms `SyntaxError: multiple exception
types must be parenthesized` here as well. Because `loop.py` is imported by
`http_request.py` (`from calibre.srv.loop import READ, WRITE, Connection`), this single
syntax error is sufficient by itself to break every module in `srv/` transitively.

**Severity:** high (fatal import-time error in the module every other server module
depends on).

**Suggested fix:**
```python
            except (AttributeError, OSError):
```

## Notes

- These three defects are the same bug pattern (leftover Python 2 `except A, B:` syntax)
  independently present in three different files. Each is independently fatal (a
  `SyntaxError` at compile time, not a runtime edge case), and because of the import
  chain (`loop.py` → `http_request.py` → most of the rest of `srv/`), fixing only one
  or two of them would not be enough to make the package importable — all three need
  fixing together.
- I did not find other logic errors, edge-case handling bugs, concurrency problems, or
  API misuse that I'm confident are real defects in the modules I read closely
  (`auth.py`, `http_request.py`, `utils.py`, `content.py`). `auth.py`'s digest/basic
  auth implementation, nonce handling, and `BanList` looked internally consistent with
  their documented behavior (including the intentionally-documented weaknesses called
  out in `AuthController`'s docstring, e.g. cookie-based session hijacking over
  non-HTTPS and ignoring digest `nc` replay checks for Firefox compatibility — these
  are documented tradeoffs, not defects). `http_request.py`'s chunked/`Content-Length`
  parsing, header folding, and body-size limit checks looked correct for the cases I
  traced through.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/standalone.py` (relevant excerpt around line 209, plus surrounding `main()` logic)
- `src/calibre/srv/loop.py` (relevant excerpt around line 570, plus `serve()`/`setup_socket()` context)
- `src/calibre/srv/routes.py` (line 112 area, to confirm PEP 695 generic syntax is not a defect)
- File listing / line counts / `ast.parse()` syntax check on every `.py` file in `src/calibre/srv/` and `src/calibre/srv/tests/`: `ajax.py`, `auth.py`, `auto_reload.py`, `bonjour.py`, `books.py`, `cdb.py`, `changes.py`, `code.py`, `content.py`, `convert.py`, `embedded.py`, `errors.py`, `fts.py`, `handler.py`, `http_request.py`, `http_response.py`, `jobs.py`, `last_read.py`, `legacy.py`, `legacy_book_details.py`, `library_broker.py`, `loop.py`, `manage_users_cli.py`, `metadata.py`, `opds.py`, `opts.py`, `pool.py`, `pre_activated.py`, `render_book.py`, `routes.py`, `standalone.py`, `users.py`, `users_api.py`, `utils.py`, `web_socket.py`, `__init__.py`, and the `tests/` package.
