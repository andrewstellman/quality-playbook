# Code Review — calibre `src/calibre/srv/`

Repo: https://github.com/kovidgoyal/calibre, pinned commit `7691f4f1a155d799afdfec99e2cdc2716c178402`
Scope: `src/calibre/srv/`

## Defect 1: `BanList.failed()` never prunes expired entries — unbounded growth of the ban-tracking dict

**File:** `src/calibre/srv/auth.py`, lines 44-60 (the pruning loop at lines 52-58)

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

**What goes wrong:** `self.items` is an `OrderedDict`. Every time a key fails, it is popped and re-inserted, so it moves to the *end* of the dict — meaning the dict is always ordered from oldest failure (front) to most recent failure (back). The just-inserted entry (`key`, just set two lines above with `previous_fail == now`) is therefore always the **last** item in iteration order.

The pruning loop iterates with `reversed(self.items)`, i.e. from the newest entry to the oldest. The very first entry it sees is the one that was just inserted, for which `now - previous_fail == 0`, which is never `> self.interval`. The loop hits the `else: break` branch immediately, on the first iteration, every single time `failed()` is called. `remove` is therefore always empty and no entry is ever pruned, regardless of how old the other entries are.

**Why it's wrong:** The code's own intent, per the comment-free but self-evident logic (and the docstring-implied purpose of `BanList` — track recent failures within `self.interval` to implement a rolling ban list), is to discard entries whose `previous_fail` is older than `self.interval` so the dict does not grow forever. The iteration direction is backwards: to correctly prune, it should iterate from the front of the `OrderedDict` (oldest first, via plain `for old in self.items:`), stopping at the first still-fresh (non-expired) entry, since entries are stored in ascending time order. Iterating from the back guarantees the loop always stops instantly.

I verified this by extracting the exact method into a standalone test with a shortened interval: after 5 keys fail and then time passes beyond the interval, calling `failed()` again with a 6th key leaves all 6 keys in `self.items` instead of pruning the 5 expired ones.

**Impact:** On a `calibre` content server exposed to the internet (or to any client population that trips failed-login bans — e.g. scanners/bots hitting `/ajax` or OPDS endpoints with bad credentials), `self.items` accumulates one entry per distinct client key (`data.remote_addr`) forever and is never cleaned up, for the lifetime of the server process. This is an unbounded-memory-growth (DoS-adjacent) bug in a long-running server process. It does not directly break the ban decision for a given key (that's a self-contained lookup that still applies `self.interval` correctly in `is_banned`), but the intended "self-cleaning" behavior of the ban tracker is completely absent.

**Severity:** Medium (unbounded memory growth in a long-running server driven by a remotely-triggerable event — repeated failed auth attempts from many distinct addresses — but not an immediate crash or auth bypass).

**Suggested fix:** Iterate in insertion (ascending-time) order instead of reversed order:

```python
for old in self.items:
    previous_fail = self.items[old][0]
    if now - previous_fail > self.interval:
        remove.append(old)
    else:
        break
```

(Or drop the early break and just prune every expired key: `remove = [k for k, (t, _) in self.items.items() if now - t > self.interval]`.)

---

## Defect 2: Chunked request bodies accept negative chunk sizes, corrupting the `Content-Length`/body-size accounting

**File:** `src/calibre/srv/http_request.py`, `read_chunk_length`, lines 420-437 (bug at line 426, exploited at lines 429 and 437)

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
```

**What goes wrong:** The chunk-size line is parsed with `int(line.strip(), 16)`. Per RFC 7230 §4.1, `chunk-size` is `1*HEXDIG` — hex digits only, no sign. But Python's `int(s, 16)` happily accepts an optional leading `+`/`-` sign (confirmed: `int('-1', 16) == -1`). A client can therefore send a chunk-size line such as `-1\r\n`, which parses successfully to `chunk_size = -1` instead of raising and being rejected as "not a valid chunk size".

With a negative `chunk_size`:
- The `max_request_body_size` guard (`bytes_read[0] + chunk_size + 2 > self.max_request_body_size`) is *weakened* rather than triggered, because adding a negative number makes the projected total smaller, not larger — it never rejects a negative-size chunk no matter how many are sent.
- Execution falls to the `else` branch (`chunk_size != 0`), calling `read_chunk` with `end = buf.tell() + chunk_size`, i.e. an end position *before* the current buffer position.
- In `read_chunk`/`read` (lines 261-271, 439-443): `size = endpos - buf.tell()` is negative, so `size > 0` is false and `read()` returns `True` immediately without consuming any bytes from the socket for this "chunk". `bytes_read[0] += chunk_size` then *decreases* the running total.
- The parser then transitions to `read_chunk_separator` expecting a literal `\r\n` next on the wire — but no chunk payload bytes were actually consumed, so whatever the client sends next (which could be an attacker-crafted line, not a real separator) is what gets read there.

**Why it's wrong:** The code's own size-limiting invariant — enforced everywhere else in this same function and in `read_chunk_separator` (line ~452: `if bytes_read[0] > self.max_request_body_size`) — is that `bytes_read[0]` accurately tracks total bytes consumed for the request body so the `max_request_body_size` cap (`self.opts.max_request_body_size`, enforced to protect the server from oversized/unbounded request bodies) is actually respected. Negative chunk sizes let a client repeatedly add negative contributions to `bytes_read[0]`, keeping the accounted total near zero or negative indefinitely while the connection's chunked-decoding state machine is driven through as many iterations as the attacker likes, defeating the entity-size cap that `finalize_headers`/`read_chunk_length` are supposed to enforce. It also desynchronizes the framing state machine's notion of buffer position from the byte stream (`end < buf.tell()`), which is not a state the chunked-transfer-encoding decoder is designed to handle.

**Severity:** Medium (resource-exhaustion / request-size-limit bypass in a remotely reachable, unauthenticated-until-`finalize_headers` HTTP parser; not a memory-corruption or auth-bypass bug, but it defeats an explicit anti-DoS control).

**Suggested fix:** Reject a chunk-size line containing anything other than hex digits explicitly, e.g.:

```python
raw = line.strip()
if not raw or any(c not in b'0123456789abcdefABCDEF' for c in raw):
    return self.simple_response(http.client.BAD_REQUEST, f'{reprlib.repr(raw)} is not a valid chunk size')
chunk_size = int(raw, 16)
```

(or equivalently check `chunk_size < 0` immediately after parsing and reject).

---

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py` (partial: range-header parsing, gzip helpers, range-writing code paths)
- `src/calibre/srv/web_socket.py` (partial: frame header parsing)
- `src/calibre/srv/library_broker.py` (partial: skimmed for locking structure, not fully reviewed)

Files in scope not reviewed in depth due to time budget: `ajax.py`, `auto_reload.py`, `bonjour.py`, `books.py`, `cdb.py`, `changes.py`, `code.py`, `content.py`, `convert.py`, `embedded.py`, `errors.py`, `fts.py`, `handler.py`, `jobs.py`, `last_read.py`, `legacy.py`, `legacy_book_details.py`, `loop.py`, `manage_users_cli.py`, `metadata.py`, `opds.py`, `opts.py`, `pool.py`, `pre_activated.py`, `render_book.py`, `routes.py`, `standalone.py`, `users.py`, `users_api.py` — no defects reported from these since they were not read closely enough to be confident.

I verified both defects by extracting the relevant logic into standalone Python 3 scripts in my work directory and confirming the buggy behavior directly (BanList pruning loop never removing stale entries; `int(x, 16)` accepting a leading `-`/`+` sign for chunk sizes).
