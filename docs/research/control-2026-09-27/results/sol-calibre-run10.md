model: gpt-6-sol
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:22:22 UTC; finished 2026-09-28 23:24:04 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran controlled-clock checks
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# calibre server review

Checkout: `7691f4f1a155d799afdfec99e2cdc2716c178402`; scope: `src/calibre/srv/`.

1. **Medium — A timed-out ban is immediately reinstated after one new failure.** `src/calibre/srv/auth.py:48-51` carries the old failure count forward even when the previous failure is older than `self.interval`. For a two-failure threshold, after a ban expires, one failed login sets the count to three and `is_banned()` immediately blocks the IP again. The `ban_for` option describes a temporary ban for the specified number of minutes, and `ban_after` specifies the number of failures needed; the existing `test_fail_ban` only checks that a correct login works after expiry. I confirmed this by executing the checked-out `BanList` class with a controlled clock. **Fix:** when loading the old entry in `failed()`, reset its count to zero if its timestamp is outside the ban interval, before incrementing.

2. **Medium — Expired failed-login records are never pruned.** `src/calibre/srv/auth.py:53-58` iterates `reversed(self.items)` just after appending the current failure. That visits the newest, unexpired record first and immediately breaks, so it never reaches older entries. As different IPs fail authentication over time, `self.items` grows without bound, contrary to the interval-based cleanup attempted here. I confirmed an expired entry remained after a failure by another IP with a controlled clock. **Fix:** iterate the `OrderedDict` from oldest to newest and remove expired entries until the first live entry.

3. **Low — A configured URL prefix does not restrict request routing.** `src/calibre/srv/routes.py:323-325` removes `self.strip_path` only when it matches; otherwise routing proceeds against the original path. With `url_prefix='/calibre'`, both `/calibre/get/...` and `/get/...` reach the same endpoint (and the root remains reachable at `/`). The option is documented in `src/calibre/srv/opts.py` as “A prefix to prepend to all URLs”; `Router.url_for()` also emits only prefixed URLs. **Fix:** when a prefix is configured, raise `HTTPNotFound` if the incoming path lacks it, then strip it before matching routes.

Files read: `src/calibre/srv/auth.py`, `src/calibre/srv/routes.py`, `src/calibre/srv/opts.py`, `src/calibre/srv/http_request.py`, `src/calibre/srv/handler.py`, `src/calibre/srv/code.py`, `src/calibre/srv/content.py`, `src/calibre/srv/last_read.py`, `src/calibre/srv/changes.py`, `src/calibre/srv/fts.py`, `src/calibre/srv/users_api.py`, `src/calibre/srv/users.py`, `src/calibre/srv/tests/auth.py`, `src/calibre/srv/tests/routes.py`, and `src/calibre/srv/tests/content.py`. (`handler.py`, `code.py`, `content.py`, `opts.py`, `http_request.py`, `tests/auth.py`, and `tests/content.py` were read in relevant excerpts.)
