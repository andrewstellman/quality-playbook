# v3: tests trimmed (29 September 2026)

Andrew asked for the minimal commit. Code in `aiohttp/streams.py` is unchanged from v2.
Tests cut from 8 functions / 24 cases to 4 functions / 13 cases, following reviewer O5
(`evidence/review-2026-09-28-v2/O5-slop.md`, aiohttp finding 2):

- kept `test_readuntil_separator_split_between_chunks`, with `split` narrowed to
  `range(1, len(separator))` so the two always-pass endpoints per separator are gone;
- kept `_one_byte_per_chunk` (three-chunk straddle), `_partial_overlap` (the `aab`
  self-overlap; its third row, a control, dropped), `_max_size` (pins the declared
  behaviour change);
- dropped `_with_false_start`, `_split_eof`, `_partial_separator_eof`,
  `_split_line_too_long` (pass before the fix or duplicate the kept cases).

Red/green re-run on a fresh copy of e11d2836 (Python 3.10, pure-Python mode):
unfixed `streams.py` + new tests: 13 failed, 0 passed; fixed: 149 passed in
`tests/test_streams.py` (136 before this patch). black, isort, flake8 clean.
Diff: 4 files, +82 -5 (v2 was +122 -5).
