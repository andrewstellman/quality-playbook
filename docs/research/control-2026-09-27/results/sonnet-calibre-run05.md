# Code review: calibre `src/calibre/srv/`

Repo: https://github.com/kovidgoyal/calibre, pinned commit `7691f4f1a155d799afdfec99e2cdc2716c178402`
Scope: `src/calibre/srv/` (checkout at `/tmp/control/calibre`, read-only)

## Method

Compiled every `.py` file in scope with `python3 -m py_compile` (Python 3.10) to catch
outright syntax errors, then read the auth, HTTP parsing/response, and content-serving
modules line by line looking for logic errors, edge-case mishandling, and
concurrency/resource bugs. One suspected logic bug (in `auth.py`'s `BanList`) was
verified by copying the class into an isolated script and exercising it directly.

Note: `routes.py` fails to compile under Python 3.10 (`def endpoint[**P](...)` at line
112), but that's valid PEP 695 generic-function syntax introduced in Python 3.12 — this
checkout targets Python 3.14 per the task brief, so that is not a defect, just a
version mismatch in my toolchain. I did not report it below.

## Defects found

### 1. `content.py:358` — Python 2 exception syntax, module fails to import (SyntaxError)

```python
    try:
        q = path_from_root(base, bytes.fromhex(encoded_fname).decode('utf-8'), reject_colon=iswindows)
    except ValueError, UnicodeDecodeError:
        raise HTTPNotFound(f'Reader background {encoded_fname} not found')
```

`except ValueError, UnicodeDecodeError:` is Python 2's exception-binding syntax
(`except Type, name:`), which was removed in Python 3. In Python 3 (verified with both
3.10 and this is not version-specific — the syntax was dropped in Python 3.0), multiple
exception types must be parenthesized: `except (ValueError, UnicodeDecodeError):`. As
written, the module raises `SyntaxError: multiple exception types must be parenthesized`
at import time — confirmed with `python3 -m py_compile content.py`:

```
  File "content.py", line 358
    except ValueError, UnicodeDecodeError:
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
SyntaxError: multiple exception types must be parenthesized
```

This is clearly intended to catch both `ValueError` (from `path_from_root`, which the
sibling `static()` and `icon()` endpoints in the same file catch as `ValueError` for the
same "naughty path" case) and `UnicodeDecodeError` (from `.decode('utf-8')`), i.e. the
author meant `except (ValueError, UnicodeDecodeError):`. Because `content.py` cannot be
imported at all, this breaks not just the `/reader-background/{encoded_fname}` endpoint
but the entire content-server module (everything else defined in this file — `get`,
`book_fmt`, `cover`, `static`, `icon`, the note-resource endpoints, etc.).

**Severity: high** (the whole module is unimportable, not just one endpoint).

**Fix:**
```python
    except (ValueError, UnicodeDecodeError):
        raise HTTPNotFound(f'Reader background {encoded_fname} not found')
```

### 2. `loop.py:570` — same Python 2 exception syntax, module fails to import

```python
        if hasattr(socket, 'AF_INET6') and self.socket.family == socket.AF_INET6 and self.bind_address[0] in ('::', '::0', '::0.0.0.0'):
            try:
                self.socket.setsockopt(IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except AttributeError, OSError:
                # Apparently, the socket option is not available in
                # this machine's TCP stack
                pass
```

Same defect as #1: `except AttributeError, OSError:` is invalid Python 3 syntax; needs
parentheses. `loop.py` is the core connection/event-loop module used by every other
`srv/` module (imported by `http_request.py`, `handler.py`, etc.), so this single
syntax error prevents the entire server from starting.

**Severity: high.**

**Fix:**
```python
            except (AttributeError, OSError):
```

### 3. `standalone.py:209` — same Python 2 exception syntax, module fails to import

```python
    if opts.manage_users:
        try:
            manage_users_cli(opts.userdb, args[1:])
        except KeyboardInterrupt, EOFError:
            raise SystemExit(_('Interrupted by user'))
        raise SystemExit(0)
```

Same defect again: `except KeyboardInterrupt, EOFError:` must be
`except (KeyboardInterrupt, EOFError):`. `standalone.py` is the server's command-line
entry point, so this breaks `calibre-server --manage-users` (and prevents the module
from being imported at all).

**Severity: high.**

**Fix:**
```python
        except (KeyboardInterrupt, EOFError):
```

(I grepped the rest of `src/calibre/srv/*.py` and `src/calibre/srv/tests/*.py` for the
same `except X, Y:` pattern and for any other syntax errors via `py_compile`; these
three files — `content.py`, `loop.py`, `standalone.py` — are the only ones affected.)

### 4. `auth.py:44-60` — `BanList.failed()` never prunes expired entries (dead pruning loop, unbounded growth)

```python
    def failed(self, key):
        if not self._active:
            return
        with self.lock:
            x = self.items.pop(key, None)
            fail_count = 0 if x is None else x[1]
            now = monotonic()
            self.items[key] = now, fail_count + 1
            remove = []
            for old in reversed(self.items):
                previous_fail = self.items[old][0]
                if now - previous_fail > self.interval:
                    remove.append(old)
                else:
                    break
            for r in remove:
                self.items.pop(r, None)
```

`self.items` is an `OrderedDict` keyed by `remote_addr`; each call pops the current
key (if present) and re-inserts it at the *end*, so the most-recently-failed key is
always last and the least-recently-failed key is always first. The loop is clearly
meant to expire stale entries so `self.items` doesn't grow without bound as different
client addresses fail to log in over the life of the server (that's the whole point of
tracking `previous_fail` timestamps and `self.interval`).

But the loop iterates with `reversed(self.items)`, i.e. newest-first. The very first
key it looks at is the one that was just inserted a few lines above (`self.items[key] =
now, ...`), whose `previous_fail == now`, so `now - previous_fail` is always `0`, which
is never `> self.interval`. The loop therefore hits the `else: break` on the *first*
iteration on every single call, and the `remove` list stays empty — the expiry logic
never removes anything, no matter how old the oldest entries are. (Iterating in
insertion order and breaking on the first non-expired entry, i.e. `for old in
self.items:` without `reversed()`, would correctly prune the *oldest* entries at the
front while stopping as soon as a still-valid one is reached.)

I verified this by lifting the class logic into an isolated script and feeding it 20
distinct keys spaced 100 seconds apart with a 60-second ban interval — all 20 entries
remained in `self.items` at the end (none were ever pruned):

```
items retained: 20
```

Practical effect: on a long-running server that logs failed-login attempts from many
different addresses (or, on the Content-server default of `ban_after=5` failures, any
addresses that generate a handful of failed logins), `AuthController.ban_list.items`
grows without bound for the lifetime of the process — a slow memory leak, and one an
attacker with a rotating/spoofable source (or just many distinct users occasionally
mistyping passwords) can accelerate.

**Severity: medium** (unbounded memory growth over time, not an immediate crash or
data-integrity bug, but directly contradicts the pruning intent of the code).

**Fix:** iterate in forward (oldest-first) order and stop at the first non-expired
entry:
```python
            remove = []
            for old in self.items:
                previous_fail = self.items[old][0]
                if now - previous_fail > self.interval:
                    remove.append(old)
                else:
                    break
            for r in remove:
                self.items.pop(r, None)
```

## Areas checked with no confident findings

- `auth.py`: Digest-auth construction/validation (`DigestAuth`, `validate_nonce`,
  `is_nonce_stale`, `AuthController.do_http_auth`) — logic matches RFC 2617 as
  documented in the surrounding comments; no defect found.
- `http_request.py`: request-line/header parsing, chunked-transfer-encoding reads,
  Content-Length validation, 100-continue handling — walked through the state machine
  (`parse_request_line` → `parse_header_line` → `finalize_headers` →
  `read_request_body`/`read_chunk_length`/`read_chunk`/`read_chunk_separator`); did not
  find a defect.
- `http_response.py`: `get_ranges()` (HTTP Range header parsing) and
  `parse_multipart_byterange()` — matched against RFC 7233 byte-range semantics; no
  defect found.
- `content.py`: `static()` and `icon()` endpoints' use of `path_from_root(...,
  reject_colon=True)` for path-traversal protection looked correct (aside from defect
  #1 above, which is in a different endpoint in the same file).

Given the size of the review scope (`src/calibre/srv/` is ~13,700 lines across ~30
files) and the effort budget for this pass, I concentrated on the authentication,
HTTP-parsing, and content-serving code as the highest-risk areas for the categories of
defect requested (logic errors, edge-case handling, error handling, concurrency, API
misuse), plus a full syntax/compile sweep of every file in scope. I did not do a
line-by-line review of every file (e.g. `fts.py`, `opds.py`, `render_book.py`,
`legacy.py`, `web_socket.py`, `pool.py`, `jobs.py`, `cdb.py`, `books.py`, `ajax.py`,
`opts.py`, `changes.py`, `code.py`, `embedded.py`, `bonjour.py`, `auto_reload.py`,
`last_read.py`, `convert.py`, `manage_users_cli.py`, `users.py`, `users_api.py`,
`metadata.py`, `fast_css_transform.cpp`, `html_as_json.cpp`) beyond the compile check
and directory-wide greps for the same syntax-error pattern; I'm not reporting anything
in those files because I don't have confident findings there, not because I've ruled
them out to the same depth as the files above.

## Files read

- `/tmp/control/TASK-calibre.md`
- `/tmp/control/calibre/src/calibre/srv/auth.py`
- `/tmp/control/calibre/src/calibre/srv/http_request.py`
- `/tmp/control/calibre/src/calibre/srv/http_response.py` (lines 1-172, 200-230 in detail; skimmed remainder)
- `/tmp/control/calibre/src/calibre/srv/content.py`
- `/tmp/control/calibre/src/calibre/srv/routes.py` (lines 95-130, to confirm the PEP 695 syntax is intentional)
- `/tmp/control/calibre/src/calibre/srv/loop.py` (lines 560-578 in detail; compiled whole file)
- `/tmp/control/calibre/src/calibre/srv/standalone.py` (lines 200-215 in detail; compiled whole file)
- Directory listing and `wc -l` of all files in `/tmp/control/calibre/src/calibre/srv/`
- `python3 -m py_compile` run against every `.py` file in `/tmp/control/calibre/src/calibre/srv/` and `/tmp/control/calibre/src/calibre/srv/tests/`
- `grep` for `except [A-Za-z_.]*, [A-Za-z_.]*:` across all `.py` files in scope
