# aiohttp: `StreamReader.readuntil()` misses a separator split across chunks

Verdict: confirmed on current master, fixed locally, not submitted.

- Repository: https://github.com/aio-libs/aiohttp
- Pinned commit: `e11d2836203a21bec59095498e578d37801027e7` (master, committed 2026-09-27T20:36:58+01:00, "Fix secure shared cookie (#13830)")
- Origin: Quality Playbook run, `repos/secbench2_widenet/wn-py-09-aiohttp/quality/BUGS.md` BUG-006; triaged in `docs/research/triage-2026-09-27/nonlinux/REPORT.md` section 1 at commit 25f3057. Reproduction and fix in this folder were done by Claude (Opus 5.5) in a Linux sandbox.

## Defect

`aiohttp/streams.py` at the pinned commit, lines 396-407:

```python
        while not_enough:
            while self._buffer and not_enough:
                offset = self._buffer_offset
                ichar = self._buffer[0].find(separator, offset) + 1
                # Read from current offset to found separator or to the end.
                data = self._read_nowait_chunk(
                    ichar - offset + seplen - 1 if ichar else -1
                )
                chunk += data
                chunk_size += len(data)
                if ichar:
                    not_enough = False
```

The search runs on one buffered chunk (`self._buffer[0]`) at a time. When a separator of two or more bytes starts in one chunk and ends in the next, neither `find` sees it. The first chunk is consumed whole, the search resumes at the start of the next chunk, and the separator is skipped. `readuntil` then returns everything up to the next complete in-chunk separator, or up to EOF, or keeps waiting for more data if neither arrives.

Example: `feed_data(b"line1\r")`, `feed_data(b"\nline2")`, `feed_eof()`, then `readuntil(b"\r\n")` returns `b"line1\r\nline2"`. The same bytes fed as one chunk return `b"line1\r\n"`. If the reader is already waiting when the second half arrives and no EOF follows, the call does not return.

A side effect: `max_size` can raise `LineTooLong` for a line that fits, because the overrun data past the missed separator is counted (test `test_readuntil_separator_split_max_size`).

`readline()` calls `readuntil(b"\n")`; a one-byte separator cannot be split, so `readline()` is not affected.

## Expected behaviour and its source

`docs/streams.rst` lines 82-88 at the pinned commit: "Read until separator, where `separator` is a sequence of bytes. If EOF is received, and `separator` was not found, the method will return the partial read bytes." The result should not depend on how the bytes were segmented by the transport. The same method in `asyncio.StreamReader.readuntil` finds separators across its buffer regardless of segmentation. The existing test `test_readuntil` (tests/test_streams.py) already feeds data in several chunks with a 2-byte separator, but always with the separator inside one chunk.

## C/Cython paths

`setup.py` builds `_websocket/mask`, `_http_parser`, `_http_writer` and `_websocket/reader_c`. None implements `readuntil` or `readline`; `_http_parser.pyx` only instantiates the Python `StreamReader`. `readuntil` is pure Python in every build, so the tests exercise the only implementation. All runs used `AIOHTTP_NO_EXTENSIONS=1`; no extensions were built.

## Scope check (security)

In-tree callers at the pinned commit: `multipart.py` lines 404, 500, 514, 887, 927 call `self._content.readline()`, which is the one-byte `b"\n"` separator and is unaffected. Nothing in `aiohttp/` calls `readuntil` with a multi-byte separator. HTTP request and response parsing (`http_parser.py`, `_http_parser.pyx`/llhttp) does its own framing and does not use `StreamReader.readuntil`. So there is no HTTP parser desync or request-smuggling path inside aiohttp. The impact is on applications that call `response.content.readuntil(b"\r\n")` (or another multi-byte separator) to frame their own data: they can get two records merged or a call that waits for data that already arrived. I treated this as a correctness bug and did not investigate application-level consequences further. See open questions.

## Reproduction

Environment: Ubuntu 22.04 aarch64 sandbox, Python 3.10.12 (master requires >= 3.10), `requirements/test.txt` in a venv, tests run from the checkout with `AIOHTTP_NO_EXTENSIONS=1 PYTHONPATH=.`. `pip install -e .` failed because the `vendor/llhttp` submodule was not initialised; it is not needed for pure-Python mode. Details in `environment.txt`.

New tests in `tests/test_streams.py::TestStreamReader`, in the style of the existing `test_readuntil_*` tests:

| Test | What it covers | Unpatched |
|---|---|---|
| `test_readuntil_separator_split_between_chunks[sep-k]` | `b"\r\n"`, `b"\r\n\r\n"`, `b"--xyz"` split after every byte position k, including k=0 and k=len(sep) as controls | 8 of 14 fail; the 6 controls pass |
| `test_readuntil_separator_split_one_byte_per_chunk` | whole stream fed one byte per chunk (separator across 4-5 chunks) | fail |
| `test_readuntil_separator_split_partial_overlap` | separator `b"aab"` where a partial match must be retried one byte later (`xa`+`a`+`b`, `xaa`+`ab`); control `xa`+`aab` | 2 fail, control passes |
| `test_readuntil_separator_split_with_false_start` | `b"\r\n\r"` prefix that does not complete, then a real split separator | fail |
| `test_readuntil_separator_split_after_wait` | reader already waiting; remaining separator bytes arrive one feed at a time after earlier bytes were consumed | fail (times out after 1 s; `wait_for` keeps the test from hanging) |
| `test_readuntil_separator_split_eof` | split separator immediately followed by EOF | passes (control) |
| `test_readuntil_partial_separator_eof` | EOF before the separator completes returns the partial data | passes (control) |
| `test_readuntil_separator_split_max_size` | line exactly `max_size` long with a split separator | fails with spurious `LineTooLong` |
| `test_readuntil_separator_split_line_too_long` | line over `max_size` with a split separator still raises `LineTooLong` | passes (control) |

The task brief mentioned `LimitOverrunError`; that is asyncio's exception. aiohttp raises `aiohttp.http_exceptions.LineTooLong`, and the existing tests use it, so the new tests do too.

## Red / green

- `red.log`: unpatched `aiohttp/` at the pinned commit plus the new tests: **16 failed, 10 passed**.
- `green.log`: same command with the fix: **26 passed**. Section 2 applies the patch file with `git am` to a fresh worktree of the pinned commit: `tests/test_streams.py` **162 passed** serially. With xdist the same 162 pass and pytest then exits 1 on a temp-directory cleanup error (`Directory not empty: 'test_static_directory_without_1'` under `/tmp/pytest-of-<user>`), left behind by an earlier `test_web_urldispatcher` run in this sandbox. That is shown verbatim in the log; it is not a test failure.
- `fuzz.log` / `fuzz_readuntil.py` (not part of the patch): 20,000 random separators, data and segmentations, with buffered and delayed feeds, compared against `bytes.find` on the joined stream. The fixed code matches on all; the unpatched code fails on the first split case it hits.

## The fix

When some data has already been read in this call and the separator is longer than one byte, check the last `len(separator) - 1` bytes already read together with the first `len(separator) - 1` bytes of the next chunk. If the separator is found there, read only up to its end. Otherwise search the chunk as before. The extra work is one join of at most `2 * (len(separator) - 1)` bytes per chunk; the buffer is never joined. The check uses the data read so far in this call, so it also works when the rest of the separator arrives after the reader started waiting. `readline()` (one-byte separator) takes exactly the old path. `max_size` / `LineTooLong` semantics are unchanged. The old `find(...) + 1` / `- 1` arithmetic became a plain `n` read length; the result is the same.

Diff to `aiohttp/streams.py`: 14 lines added, 5 removed. Patch: `0001-Fix-readuntil-missing-a-separator-split-across-chunk.patch` (author Andrew Stellman, based on e11d2836). It also adds `CHANGES/PRNUMBER.bugfix.rst` and `Andrew Stellman` to `CONTRIBUTORS.txt`.

Lint: black 26.5.1 and isort 9.0.1 (pre-commit pins) make no changes; flake8 with setup.cfg and codespell are clean. mypy 2.1.0 on `aiohttp/streams.py` reports 18 errors in 7 other files, identical before and after; none in streams.py. The full `pre-commit` hook set was not run.

## Existing tests

Files touching streams, readuntil or readline (16 files: test_streams, test_flowcontrol_streams, test_multipart, test_benchmarks_multipart, test_http_parser, test_client_proto, test_client_response, test_client_functional, test_client_ws_functional, test_web_functional, test_web_request, test_web_app, test_web_middleware, test_web_urldispatcher, test_web_websocket_functional, test_run_app):

- `suite-before.log` section A, pristine master: **1888 passed, 40 skipped, 1 xfailed**, exit 0.
- `suite-before.log` section B, unpatched code plus new tests: **16 failed, 1898 passed, 40 skipped, 1 xfailed**. The 16 failures are the new tests listed above.
- `suite-after.log`, with the fix: **1914 passed, 40 skipped, 1 xfailed**, exit 0.

No pre-existing failures. Skips are C-parser-only tests, Python 3.11+ features and wbits. The whole repository test suite was not run, and nothing was run with the Cython extensions built.

## Disclosure search

See `disclosure-search.md`. Fourteen GitHub API/HTML queries (readuntil, separator, chunk boundary, split delimiter, readline, comments, open items, security advisories). No existing issue, PR or advisory for this defect. Related but different: #6701/#6810 (intra-chunk offset, 2022), #8643 (multipart boundary split, different code), #13686/#13825 (docs signature). Search cannot prove the defect is unreported.

## Open questions for Andrew

1. **CHANGES fragment name.** It is `CHANGES/PRNUMBER.bugfix.rst` and must be renamed to the PR number after the draft PR exists (their template says to do this). The fragment signs as `:user:`andrewstellman``; confirm that is your GitHub handle.
2. **CONTRIBUTORS.txt.** Added as a first-time contributor. Drop that hunk if you have contributed to aiohttp before.
3. **AI disclosure line.** AGENTS.md requires `Drafted with <agent name and version>; reviewed by <human handle>.` PR-DRAFT.md uses "Claude Opus 5.5" and your handle; check that wording, and that you are comfortable being the named reviewer after reviewing the diff.
4. **Application-level impact.** No aiohttp-internal security path was found, but applications that frame a sub-protocol with multi-byte `readuntil` on attacker-controlled bodies get segmentation-dependent results. I don't consider this a vulnerability in aiohttp; if you think the THREAT_MODEL.md owners would want to hear about it privately first, that is your call.
5. **Cython build.** AGENTS.md asks for Cython testing only for parser/websocket changes. This change is neither, and `readuntil` has no compiled form, so no extension build was done. CI will cover it.
6. **Backport.** Backports to 3.x branches are made by a bot on maintainer request. Whether the 3.x branches contain the same `readuntil` code was not checked.
