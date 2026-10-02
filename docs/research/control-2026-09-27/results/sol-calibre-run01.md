model: gpt-6-sol
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:01:26 UTC; finished 2026-09-28 23:03:20 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# calibre server review (`7691f4f1a155d799afdfec99e2cdc2716c178402`)

## Findings

1. **Medium — Expired authentication failures never reset or get pruned.** `src/calibre/srv/auth.py:48-58`. With banning enabled, fail a login `ban_after` times, wait longer than `ban_time_in_minutes`, then fail once more. `is_banned()` allows the request after the interval, but `failed()` retains the old count and increments it, so that single failure immediately bans the client again. The cleanup loop iterates `reversed(self.items)` after inserting the newest entry, sees that fresh entry first, and breaks; expired entries are never removed, so distinct failed client addresses also grow the map without bound. The constructor's `ban_time_in_minutes` and `max_failures_before_ban` options establish the intended time-limited threshold. Reset the count when the prior failure is outside the interval, and prune from the oldest end of the ordered map before inserting the new failure.

2. **Medium — Valid chunked requests with extensions or trailers receive 400.** `src/calibre/srv/http_request.py:426` and `:445-458`. For example, a request body `4;foo=bar\r\nbody\r\n0\r\n\r\n` fails `int(line.strip(), 16)` even though chunk extensions are valid HTTP chunk syntax. A body ending `0\r\nX-Checksum: value\r\n\r\n` fails because the zero-chunk handler expects an immediate blank line, although trailer fields are valid after the last chunk. This contradicts the module's stated “Transfer-Encoding support” and the chunked transfer coding it accepts and tests in `src/calibre/srv/tests/http.py:283-289`. Parse the hexadecimal size before an optional `;` extension; after a zero chunk, consume and validate trailer lines through the terminating blank line before dispatching the request.

3. **Medium — The interface response reveals books after a user's book restriction changes.** `src/calibre/srv/code.py:193-200` and `:225-227`. If a user reads a book and an administrator later excludes it with a library restriction, `/interface-data/update` still returns its cached recently-read entry, including the title, position, and tooltip, as long as the book and format still exist. The filter checks the library ID and physical format existence but never calls the restriction-aware `ctx.has_id()` used by book endpoints (`src/calibre/srv/handler.py:91-98`, `src/calibre/srv/books.py:239-240`). Filter cached entries through `ctx.has_id(rd, db, book_id)` as well as the format check.

4. **Medium — A GET or HEAD request disables full-text search.** `src/calibre/srv/fts.py:77-81`. `/fts/disable` calls `db.enable_fts(enabled=False)` but omits `methods`, so the route decorator allows both GET and HEAD by default (`src/calibre/srv/routes.py:28,114`). A browser prefetch, crawler, or link to this endpoint can therefore change library state merely by retrieving it; HEAD has the same side effect. Nearby state-changing FTS routes explicitly require POST (`src/calibre/srv/fts.py:85,103`). Restrict this route to POST and have clients invoke it with POST.

## Files read

`src/calibre/srv/auth.py`; `src/calibre/srv/http_request.py`; `src/calibre/srv/tests/http.py`; `src/calibre/srv/routes.py`; `src/calibre/srv/users.py`; `src/calibre/srv/handler.py`; `src/calibre/srv/books.py`; `src/calibre/srv/last_read.py`; `src/calibre/srv/fts.py`; `src/calibre/srv/code.py`; `src/calibre/srv/users_api.py`.
