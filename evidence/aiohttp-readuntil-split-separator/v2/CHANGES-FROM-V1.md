# aiohttp-readuntil: changes from v1 to v2

Source of items: `review-2026-09-27/SYNTHESIS.md`, section "aiohttp-readuntil" (detail in O1, O3, O5, S1).

| # | Synthesis item | What v2 does |
|---|---|---|
| 1 | One disclosure line, in AGENTS.md form [O1, O5, S3] | Done. The PR ends with one line: `Drafted with Claude Opus 5.5; reviewed by andrewstellman.` The "Found by a Quality Playbook run..." line is gone. The handle has no `@`, matching merged PR #13686 (cited by O1). |
| 2 | Keep `CHANGES/PRNUMBER.bugfix.rst`, rename after the PR exists [O1, S8] | Kept with unchanged content. The rename is in NOTES-FOR-ANDREW.md, not in the PR body. |
| 3 | Cut the `<details>` cross-suite counts to the short form [O5] | Done. The 16-file before/after counts, command lines and Cython paragraph are removed. The block now has three result lines (red, green, `tests/test_streams.py`). It stays a collapsed `<details>` block below the template, as AGENTS.md asks for agent test output. |
| 4 | State the `max_size` behaviour change [O3] | Done, in "Are there changes in behavior for the user?": a line that exactly fits `max_size` with a split separator is now returned instead of raising `LineTooLong`. v1's "`max_size`/`LineTooLong` semantics are unchanged" is removed because it contradicted this. |
| 5 | Comment on the `tail`/`head`/`n` arithmetic [S1] | Done, as two added comment lines under the existing one: tail and head are each shorter than the separator, so a match in `tail + head` must span both, and `n` counts its bytes in head. S1's helper-function extraction was not done; the brief asked for a comment only. No change to the code. |
| 6 | Drop `test_readuntil_separator_split_after_wait` (reads private `_waiter`) [O1, O5] | Done. The other 8 test functions are kept. None is clearly redundant: each non-failing one is a control for a different condition (split at 0/len, in-chunk overlap, EOF straight after a split separator, partial separator at EOF, over-long line still raising). |
| - | Short commit message | Done. It uses O5's three-line body: what was wrong and what the fix does. |
| - | No notes to Andrew in the PR body | Done. No HTML comments, no placeholders, no "open as draft" line, no references to evidence files. The PR title is not in PR-DRAFT.md; it is in NOTES-FOR-ANDREW.md. |

## Consequences worth knowing

- **Waiting-reader coverage is gone.** The dropped test was the only one that fed the rest of the separator after `readuntil()` was already waiting. The remaining tests all feed data before the call. The code path is the same (`tail` comes from `chunk`, which persists across waits), and O3's interleaving fuzz (8,000 cases, 0 failures on the fix) covers it, but that fuzz is not part of the patch. So the PR no longer claims that the unpatched call can hang; nothing in the PR's own test output shows it.
- **Red count went from 16 failed / 10 passed to 14 failed / 10 passed.** The difference is the two parametrizations of the dropped test. Green went from 26 to 24; `tests/test_streams.py` went from 162 to 160 passed.

## Verification (logs in this folder)

Work tree: `/tmp/fix/aiohttp`, a copy of the pinned tree (e11d2836) with a fresh `git init`; v1 applied with `git am`, then edited and amended.

| Log | State | Result |
|---|---|---|
| `red.log` | base `aiohttp/` + new tests only | 14 failed, 10 passed. Failures: 13 return data past the separator (for example `b'line1\r\nline2'` instead of `b'line1\r\n'`), 1 raises `LineTooLong` on the exactly-`max_size` line. |
| `green.log` | full patch | 24 passed |
| `revert.log` | full patch, `aiohttp/streams.py` restored to base | 14 failed, 10 passed; the same 14 tests as red |
| `suite-before.log` | base, `tests/test_streams.py` | 136 passed |
| `suite-after.log` | full patch, `tests/test_streams.py` | 160 passed (136 + 24 new) |
| `lint.log` | full patch | black 26.5.1, isort 9.0.1, flake8, codespell: all clean |

Not re-run for v2: mypy, the full `pre-commit` hook set, and the 16-file cross-suite run from v1. The code change in v2 is comments only, so these were not expected to change. The v1 fuzz was not re-run; the logic did not change.

The test venv `/tmp/aiohttp-venv` did not exist in this sandbox. I rebuilt it with `python3 -m venv` + `pip install -r requirements/test.txt` from the pinned tree, then added black/isort/flake8/codespell for the lint check.
