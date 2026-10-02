model: gpt-6-sol
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:03:36 UTC; finished 2026-09-28 23:05:33 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: `src/calibre/srv/` at `7691f4f1a155d799afdfec99e2cdc2716c178402`

## Findings

1. **Stale rendered-book cache entries are never removed** — `src/calibre/srv/books.py:116`  
   **Severity:** medium. When `clean_final()` finds a cache entry whose manifest is older than `interval`, it calls `safe_remove(x)` where `x` is only the directory name returned by `os.listdir(fdir)`. That removes a path relative to the server's working directory, while the manifest checked at line 111 is under `fdir`. Normally the old cache directory remains forever, so rendered books accumulate on disk; if an identically named working-directory entry exists, the function can remove that instead. The comment at line 115 expressly says this book should be deleted. **Fix:** call `safe_remove(os.path.join(fdir, x), False)`.

2. **Expired login failures persist and make later bans premature** — `src/calibre/srv/auth.py:48-60`  
   **Severity:** medium. After an IP reaches `ban_after` failures and its `ban_for` interval expires, the next single failed login sets `fail_count` to the previous count plus one and immediately bans it again. `failed()` never resets a count whose last failure is older than `self.interval`. Its pruning loop also walks `OrderedDict` in reverse, sees the just-inserted current entry first, and breaks before reaching any expired entries. Thus expired IP records accumulate indefinitely. The option descriptions in `src/calibre/srv/opts.py:189-199` describe a temporary ban after the configured number of login failures. **Fix:** reset an expired key's count before incrementing, and prune from the oldest end of the ordered dictionary until the first unexpired record.

3. **Valid chunked requests with extensions or trailers are rejected** — `src/calibre/srv/http_request.py:425-428,434-458`  
   **Severity:** low. A request body such as `4;foo=bar\r\nbody\r\n0\r\n\r\n` receives 400 because the parser passes the entire chunk-size line to `int(..., 16)`. Likewise, a trailer after the zero chunk receives 400 because `read_chunk_separator(..., last=True)` requires the next line to be blank. Both forms are part of HTTP/1.1 chunked transfer coding, which this parser says it supports at lines 372-384. Clients that use those forms cannot POST to the server. **Fix:** parse the hexadecimal size before any `;` extension, then after the zero chunk consume validated trailer fields until the terminating blank line, applying existing header and size limits.

## Files read

`src/calibre/srv/auth.py`, `src/calibre/srv/books.py`, `src/calibre/srv/cdb.py`, `src/calibre/srv/changes.py`, `src/calibre/srv/handler.py`, `src/calibre/srv/http_request.py`, `src/calibre/srv/last_read.py`, `src/calibre/srv/library_broker.py`, `src/calibre/srv/opts.py`, `src/calibre/srv/routes.py`, `src/calibre/srv/users.py`, `src/calibre/srv/users_api.py`, `src/calibre/srv/tests/auth.py`, `src/calibre/srv/tests/http.py`.
