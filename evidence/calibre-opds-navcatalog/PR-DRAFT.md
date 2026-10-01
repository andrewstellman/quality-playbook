# PR draft (not submitted)

calibre takes GitHub pull requests (README: "GitHub is only used for code hosting and pull requests"; bugs go to Launchpad). No PR template, no CLA, no changelog entry required. `manual/develop.rst` also accepts `git format-patch` output. Keep it short; do not call it a security fix.

**Title:** Content server: return 404 instead of 500 for malformed /opds/navcatalog ids

---

`opds_navcatalog` passes the `{which}` path component straight to `from_hex_unicode`, so a non-hex, odd-length or non-UTF-8 id (e.g. `/opds/navcatalog/zz`, `/opds/navcatalog/ff`) raises `binascii.Error` / `UnicodeDecodeError`. The server logs an unhandled-exception traceback and returns 500. Every other bad input to this handler (bad `offset`, unknown type prefix) already gives 404, and ajax.py and `reader_background` already turn undecodable hex arguments into `HTTPNotFound`.

This catches the decode error and raises `HTTPNotFound('Not found')`, and adds the same empty-id check `opds_category` uses. Valid ids are unaffected.

[If sending the alternative patch, add:] `opds_category` and `opds_categorygroup` decode their ids the same way and had the same 500, so they get the same `try/except`.

Found by a Quality Playbook analysis run; reproduction and fix were done with Claude (Anthropic), by executing the unmodified handler with stubbed library/request objects under Python 3.14, since I did not have a full calibre build. Verified before/after: malformed ids now 404, valid `N`/`O` ids still reach the feed builders. `ruff check` / `ruff format --check` pass.
