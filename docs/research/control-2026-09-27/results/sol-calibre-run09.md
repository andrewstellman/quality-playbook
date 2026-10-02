model: gpt-6-sol
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:19:35 UTC; finished 2026-09-28 23:22:15 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# calibre server review

Checkout: `7691f4f1a155d799afdfec99e2cdc2716c178402`. Scope: `src/calibre/srv/`.

## Findings

1. **Expired login failures are never pruned and count toward a new ban** — `src/calibre/srv/auth.py:48-58`. **Severity: medium.** `BanList.failed()` inserts the current failure at the end of its `OrderedDict`, then scans in reverse and stops at the first non-expired entry. That first entry is always the one just inserted, so the cleanup loop never visits any older entry. It also reuses the old failure count without checking its age. With `ban_after=2` and a one-minute ban, a client that fails twice, waits 61 seconds, and fails once is immediately banned again; failures from distinct addresses remain in memory indefinitely. `is_banned()` at lines 39-42 explicitly treats a failure as expired after `self.interval`, establishing the intended time limit. I reproduced both outcomes by executing the repository's `BanList` class with a controlled monotonic clock. **Fix:** when retrieving an existing entry, reset its count if its timestamp has expired; prune expired entries by iterating from the oldest end of the ordered dictionary and stopping at the first fresh entry.

2. **A HEAD request disables full-text indexing** — `src/calibre/srv/fts.py:77-81`. **Severity: medium.** The `/fts/disable` endpoint calls `db.enable_fts(enabled=False)` but does not specify `methods`, so `endpoint()` supplies the default `{'HEAD', 'GET'}` (`src/calibre/srv/routes.py:28,114`). `Router.dispatch()` invokes the endpoint for either method (`routes.py:355-372`), so a HEAD probe changes persistent library state. HEAD is a safe retrieval method, and the adjacent mutating FTS routes explicitly require POST (`fts.py:85,103`). **Fix:** make `/fts/disable` POST-only and update its existing GET caller in `src/pyj/book_list/fts.pyj:313` to send POST.

## Files read

`src/calibre/srv/auth.py`; `src/calibre/srv/routes.py`; `src/calibre/srv/handler.py`; `src/calibre/srv/users.py`; `src/calibre/srv/changes.py`; `src/calibre/srv/http_request.py`; `src/calibre/srv/content.py`; `src/calibre/srv/fts.py`; `src/calibre/srv/utils.py`; `src/calibre/srv/library_broker.py`; `src/calibre/srv/tests/auth.py`; `src/calibre/srv/tests/routes.py`; `src/calibre/srv/tests/http.py`; `src/pyj/book_list/fts.pyj`; `src/pyj/ajax.pyj`.
