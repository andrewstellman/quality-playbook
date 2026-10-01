# PR draft (not submitted)

**Title:** Content server: return 404 instead of 500 for malformed hex ids in OPDS feeds

---

`opds_navcatalog`, `opds_category`, and `opds_categorygroup` all decode their id path segments with `from_hex_unicode`, and a non-hex, odd-length, or non-UTF-8 value raises `binascii.Error`/`UnicodeDecodeError` instead of the `HTTPNotFound` these handlers already return for every other bad input, so this wraps each decode in `try`/`except` and raises `HTTPNotFound('Not found')` on failure, leaving valid ids unaffected. Found with an automated review tool; patch written with Claude and reviewed by me. Verified by executing the unmodified handler code with stubbed request/library objects under Python 3.14, since calibre's OPDS handlers have no test coverage (`src/calibre/srv/tests/ajax.py:374`); malformed ids now 404 in all three handlers, valid ids still reach the feed builders, and `ruff check`/`ruff format --check` pass.
