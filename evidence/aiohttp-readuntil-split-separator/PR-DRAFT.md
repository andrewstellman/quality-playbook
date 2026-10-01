# PR draft (not submitted)

Open as a draft (`gh pr create --draft`) per aiohttp AGENTS.md, after renaming `CHANGES/PRNUMBER.bugfix.rst` to the PR number.

**Title:** Fix readuntil() missing a separator split across chunks

---

## What do these changes do?

`StreamReader.readuntil()` searched each buffered chunk on its own, so a multi-byte separator whose bytes arrived in different chunks was never found. For example, feeding `b"line1\r"` then `b"\nline2"` made `readuntil(b"\r\n")` return `b"line1\r\nline2"`, and if the reader was already waiting and no EOF followed, the call did not return. This change also checks the last `len(separator) - 1` bytes already read against the start of the next chunk, without joining the buffer.

## Are there changes in behavior for the user?

`readuntil()` now stops at the first separator regardless of how the data was split into chunks, as documented. `readline()` and one-byte separators are unchanged, as are `max_size`/`LineTooLong` semantics.

## Is it a substantial burden for the maintainers to support this?

No. It is a local change inside the `readuntil()` loop plus tests in `tests/test_streams.py`.

## Related issue number

None found. #6701/#6810 fixed a different multi-byte separator bug (offset within one chunk).

## Checklist

- [x] I think the code is well written
- [x] Unit tests for the changes exist
- [ ] Documentation reflects the changes: N/A, the change restores the documented behaviour
- [x] If you provide code modification, please add yourself to `CONTRIBUTORS.txt`
- [x] Add a new news fragment into the `CHANGES/` folder

<details>
<summary>Test output</summary>

Pure-Python mode (`AIOHTTP_NO_EXTENSIONS=1 PYTHONPATH=.`), Python 3.10.12, Linux, based on e11d2836.

New tests without the fix:
```
$ pytest tests/test_streams.py -k 'readuntil_separator_split or readuntil_partial_separator' --numprocesses=0 --no-cov
================ 16 failed, 10 passed, 136 deselected in 2.65s =================
```

With the fix:
```
$ pytest tests/test_streams.py -k 'readuntil_separator_split or readuntil_partial_separator' --numprocesses=0 --no-cov
====================== 26 passed, 136 deselected in 0.21s ======================
$ pytest tests/test_streams.py --numprocesses=0 --no-cov
162 passed in 1.11s
```

Stream, multipart, HTTP parser, client and web test files (16 files):
```
before (master):  1888 passed, 40 skipped, 1 xfailed
after (this PR):  1914 passed, 40 skipped, 1 xfailed
```

The Cython extensions were not built; `readuntil()` has no compiled implementation.

</details>

Found by a Quality Playbook run; reproduction and fix by Claude.

Drafted with Claude Opus 5.5; reviewed by @andrewstellman.
