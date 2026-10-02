model: gpt-6-sol
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:12:05 UTC; finished 2026-09-28 23:13:32 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; checkout hash verified; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# calibre server review

Checkout: `7691f4f1a155d799afdfec99e2cdc2716c178402`. Scope: `src/calibre/srv/`.

## Findings

1. **Medium — Expired login failures never age out of the ban list.** `src/calibre/srv/auth.py:53-58` iterates `reversed(self.items)`, which visits the newest failure first. The failure just inserted at line 51 is always within the interval, so the loop immediately breaks and removes nothing. With many distinct source IPs, `items` grows without bound. More directly, after a ban expires, the next bad password for that IP inherits its old count at lines 48-51 and immediately bans it again, although the `ban_for` option describes a temporary ban after repeated failures (`src/calibre/srv/opts.py:183-200`). Iterate from oldest to newest and remove expired entries; reset a key's count when its last failure is outside the interval. The existing ban test checks successful login after expiry but does not check the next failed login.

2. **Medium — Rendered-book cleanup deletes the wrong path.** `src/calibre/srv/books.py:108-116` lists entries in the final-cache directory and reads each manifest through `os.path.join(fdir, x)`, but calls `safe_remove(x)` for an old entry. `x` is only the basename, so `safe_remove` resolves it relative to the server's current working directory. Old cached books are never removed in the normal case, allowing the rendered-book cache to grow indefinitely; a same-named directory in the working directory could instead be deleted. The adjacent comment says the old book should be deleted, and other callers of `safe_remove` pass full paths. Call `safe_remove(os.path.join(fdir, x), False)`.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/books.py`
- `src/calibre/srv/changes.py`
- `src/calibre/srv/last_read.py`
- `src/calibre/srv/users_api.py`
- `src/calibre/srv/opts.py`
- `src/calibre/srv/tests/auth.py`
- `src/calibre/srv/tests/content.py`
- `src/calibre/utils/filenames.py`
