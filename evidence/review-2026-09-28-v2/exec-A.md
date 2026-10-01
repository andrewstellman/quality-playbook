# Round-2 executor A report

All work done in `/tmp/review/exec2/A/<ID>/` on clean copies made from `/tmp/review/src/<repo>/base` and
`/tmp/review/src/<repo>/v2-<ID>` (read-only). Sources under `/tmp/review/src` and `/tmp/review/packets2`
were never modified. Verbatim logs are alongside this file as `<ID>-{red,green,revert,suite-base,suite-fixed}.log`
(`bionemo-thd` also has `bionemo-thd-check-copied-files.log`).

Disk was shared with executor B (~1.8 GB total, ~1.9 GB free at start). `df -h /tmp` was checked before
each fix; each fix's scratch tree was deleted (or, for aiohttp, moved out) before starting the next.
Free space at various points: ~1.9G (start) → 1.2G (after installing CPU torch) → 748–851M (during
bionemo). Never ran out.

---

## aiohttp-readuntil

**Pinned base SHA:** `e11d283` (verified via `git worktree list` in `/tmp/review/src/aiohttp/.repo`;
my own copy was re-init'd as a fresh git repo since `cp -a` carried a worktree-gitlink file, not usable
standalone).

Environment: reused the existing `/tmp/aiohttp-venv` (already had aiohttp's test deps installed).
Command form: `AIOHTTP_NO_EXTENSIONS=1 PYTHONPATH=. /tmp/aiohttp-venv/bin/python -m pytest -p no:cacheprovider -n0 --no-cov ...`

1. **RED.** Applied only the `tests/test_streams.py` hunk from `0001-*.patch` to a fresh git copy of
   `base`. Ran the 8 new test functions (`-k "readuntil_separator_split or readuntil_partial_separator_eof"`):
   **14 failed, 10 passed.** Two representative failures, both matching the claimed bug (separator bytes
   split across chunks are missed):
   - `test_readuntil_separator_split_with_false_start`: `assert b'a\r\n\rb\r\n\r\n' == line` →
     `AssertionError: ... b'a\r\n\rb\r\n\r\nrest'` (readuntil kept reading past the separator because the
     split copy of it wasn't recognized).
   - `test_readuntil_separator_split_max_size`: expected `readuntil(b"\r\n", max_size=4)` to return after
     4 bytes; instead raised `aiohttp.http_exceptions.LineTooLong: ... 'Got more than 4 bytes when
     reading: b'12\r\n3456...'` because the separator split across `b"12\r"` / `b"\n3456"` was never found.
   Log: `aiohttp-readuntil-red.log`.

2. **GREEN.** Applied the remaining (non-test) hunk (`aiohttp/streams.py`, `CONTRIBUTORS.txt`). Re-ran the
   same 8 test functions: **24 passed** (0 failed). Log: `aiohttp-readuntil-green.log`.

3. **REVERT.** Reversed only the `aiohttp/streams.py` hunk (kept the test file and `CONTRIBUTORS.txt`
   change). Re-ran: **14 failed, 10 passed** — identical failure set to RED. Log:
   `aiohttp-readuntil-revert.log`.

4. **SUITE.** Full `tests/test_streams.py`:
   - base (no patch at all): **136 passed**. Log: `aiohttp-readuntil-suite-base.log`.
   - fixed (full patch applied): **160 passed** (136 + 24 new, no regressions, no skips/xfails hiding
     anything). Log: `aiohttp-readuntil-suite-fixed.log`.

**Execution kind:** real pytest run of the actual `aiohttp.streams.StreamReader.readuntil` code
(`AIOHTTP_NO_EXTENSIONS=1` forces the pure-Python implementation, not the C extension — this is the
patched code path).

**Discrepancies:** none.

**PASS.**

---

## calibre-opds

**Pinned base SHA:** `7691f4f` (also stated in the evidence folder's `environment.txt`; confirmed via
`git worktree list` in `/tmp/review/src/calibre/.repo`).

**No test accompanies this patch** — confirmed independently: `src/calibre/srv/tests/ajax.py:374` in my
own copy contains the comment `# Not going test legacy and opds as they are too painful`, and
`setup.py test find_tests` fails before collection with
`ModuleNotFoundError: No module named 'calibre_extensions.translator'` (calibre needs its compiled
extensions to even import `calibre/__init__.py`), reproduced in my own copy. Used the validator's harness
(`/sessions/kind-zealous-edison/mnt/QPB/evidence/calibre-opds-navcatalog/harness.py`, copied verbatim into
my scratch dir, pointed at my own `tree/src`) — **labelled as a harness**, not a project test.

1. **RED** (harness against unpatched `base` copy): navcatalog malformed-input cases raising
   non-`HTTPNotFound` exceptions: **4** (`empty` → `IndexError`; `non-hex chars 'zz'` → `binascii.Error:
   Non-hexadecimal digit found`; `odd-length hex '4'` → `binascii.Error: Odd-length string`; `valid hex,
   invalid UTF-8 'ff'` → `UnicodeDecodeError`). `RESULT: RED`. Sibling handlers (`opds_category`,
   `opds_categorygroup`), informational only, also unhandled on the same malformed inputs. Log:
   `calibre-opds-red.log`.

2. **GREEN** (harness against a copy with `0001-*.patch` applied via `git apply`): navcatalog failures
   drop to **1** — only the `empty` case (`IndexError`), which the harness itself and `v2/CHANGES-FROM-V1.md`
   document as unreachable over HTTP (confirmed in my own run's reachability table:
   `/opds/navcatalog/` and `/opds/navcatalog//` both collapse to the 2-component path
   `('opds','navcatalog')` before ever reaching the 3-component route, so `which=''` can only occur via a
   direct function call). The three real HTTP-reachable malformed-hex cases (`zz`, `4`, `ff`) now return
   `HTTP404: HTTPNotFound(Not found)`. Sibling handlers also now 404 on the same malformed inputs (the v2
   patch, unlike v1, touches all three handlers). `RESULT: RED` is still printed by the harness's own exit
   logic because of the one remaining (unreachable) case — this matches the evidence folder's own
   `v2/green.log`, not a discrepancy. Log: `calibre-opds-green.log`.

3. **REVERT** (`git apply -R` the same patch, on the same copy): navcatalog failures return to **4**,
   identical set to RED. Log: `calibre-opds-revert.log`.

4. **SUITE.** No pytest/unittest suite could be run at all (see above; independently reproduced). In place
   of a suite comparison I re-ran `ruff check` and `ruff format --check` on the patched
   `src/calibre/srv/opds.py` in my own copy: `All checks passed!` / `1 file already formatted` — matches
   the claim in `PR-DRAFT.md`. Logs: `calibre-opds-suite-base.log` and `calibre-opds-suite-fixed.log`
   (both are the same explanatory note plus the independently-reproduced ruff output, since there is no
   base/fixed suite to diff — labelled accordingly in the log text itself).

**Execution kind:** harness (verbatim-extracted, unmodified `opds_navcatalog`/`opds_category`/
`opds_categorygroup` function bodies from my own copy, executed with stubbed request/context objects under
Python 3.14.7 at `/sessions/kind-zealous-edison/.local/bin/python3.14`) — not a project test, no test exists.

**Discrepancies:** none against the packet's own claims; the harness's exit code stays "RED" post-fix
because of the pre-existing unreachable-empty-string case, which is documented behavior, not a fix failure.

**PASS.**

---

## bionemo-amplify

**Pinned base SHA:** `1170147` (from `git worktree list` in `/tmp/review/src/bionemo/.repo`; my own copies
were re-init'd as fresh git repos, HEAD `f73a47210a05249289ac2c10287dc65c5d6fc106` for my `base` copy and
`a8312d1e0ded0b3c5a6c335f75947105989437f8` for my `v2-amplify` copy — these are my own commit hashes, not
upstream's; the content is the same as SHA `1170147`/v2 respectively).

**Execution kind: harness (labelled).** The real `amplify.state_dict_convert` module imports
`transformer_engine` via `amplify.amplify_te` (CUDA-only), so the project's own pytest can't collect it on
this CPU-only sandbox. Used
`/sessions/kind-zealous-edison/mnt/QPB/evidence/bionemo-amplify-pad-weights-dtype/v2/harness/run_extracted.py`,
copied verbatim into my scratch dir and pointed at my own `--src-tree` / `--test-tree` directories (not a
hard-coded path — confirmed by reading the script: it takes `--src-tree`/`--test-tree` args and `ast`-extracts
the named function/test bodies from whatever tree is passed). Installed CPU torch
(`torch-2.14.0+cpu`) via `pip install --index-url https://download.pytorch.org/whl/cpu torch` into a fresh
venv under `/tmp/review/exec2/A/bionemo/venv`.

1. **RED**: `run_extracted.py amplify --src-tree base --test-tree v2-amplify` (old source, new test).
   `test_pad_weights_dtype_device[cpu]` **FAILED**: `assert padded.dtype == torch.bfloat16` →
   `AssertionError: assert torch.float32 == torch.bfloat16` — exactly the claimed bug (padding rows
   built in fp32 regardless of the bf16 source embedding). `[cuda]` param skipped (no GPU). 1 failed, 1
   skipped. Log: `bionemo-amplify-red.log`.

2. **GREEN**: `run_extracted.py amplify --src-tree v2-amplify --test-tree v2-amplify`. **1 passed, 1
   skipped**, 0 failed. Log: `bionemo-amplify-green.log`.

3. **REVERT**: made a copy of `v2-amplify`, reversed only the `state_dict_convert.py` hunk (kept the test),
   confirmed via `git diff --stat` that only the source file changed (1 insertion, 3 deletions — the
   `dtype=`/`device=` args removed). Re-ran against the reverted source + v2 test: **failed again**,
   identical assertion (`torch.float32 == torch.bfloat16`). Log: `bionemo-amplify-revert.log`.

4. **SUITE.** The real `models/amplify/tests/test_amplify_model.py` cannot be collected on either base or
   fixed: `ImportError while loading conftest ... ModuleNotFoundError: No module named 'datasets'`,
   reproduced independently in both my `base` and `v2-amplify` copies — this matches (word-for-word) the
   evidence folder's own `pytest_collection_blocked.log`. No base-vs-fixed suite count is possible; logs:
   `bionemo-amplify-suite-base.log`, `bionemo-amplify-suite-fixed.log` (both show the same collection
   error against my own copies).

**Discrepancies:** none.

**PASS.**

---

## bionemo-thd

**Pinned base SHA:** `1170147` (my own git-repo copies: `base` unchanged HEAD hash differs run-to-run
since it's a fresh `git init`+commit, content matches the `1170147` tree; `v2-thd` copy likewise).

**Execution kind: harness (labelled)**, same `run_extracted.py` script, `thd` spec (extracts
`_find_seq_dim`, `_process_tensor_thd`, `_process_tensor_bshd`, `_split_batch_by_cp_rank` from
`models/esm2/collator.py`, plus the BSHD/THD test functions from
`models/esm2/tests/test_collator_context_parallel.py`, with a stub `nvtx` module standing in for the
CUDA-only profiling decorator — confirmed by reading the script, not just trusting its docstring). Same
CPU-torch venv as amplify.

1. **RED**: `run_extracted.py thd --src-tree base --test-tree v2-thd`. 4 pre-existing BSHD tests
   **PASSED** (unaffected), `test_split_batch_by_cp_rank_thd_covers_all_tokens` also happened to **PASS**
   on this particular input, but the fix's own regression test **FAILED**:
   `test_split_batch_by_cp_rank_thd_non_divisible`: `Failed: DID NOT RAISE ValueError` — the unpatched
   floor-division silently drops the remainder. The harness's own demo function (extracted, unmodified
   `_split_batch_by_cp_rank`, run against `cu_seqlens_padded=[0,8,18]`, `cp_world_size=2`) confirms the
   underlying claim directly: **token positions [16, 17] are assigned to no CP rank** (dropped), and for 7
   packed length-6 sequences, **14 token positions are dropped**. 1 failed, 5 passed. Log:
   `bionemo-thd-red.log`.

2. **GREEN**: `run_extracted.py thd --src-tree v2-thd --test-tree v2-thd`. **6 passed**, 0 failed. Demo
   now raises `ValueError: Padded sequence length(s) [10] must be divisible by 4 (2 * cp_world_size) for
   THD context parallelism; set pad_sequences_to_be_divisible_by to a multiple of 4` for both demo cases
   instead of silently dropping tokens. Log: `bionemo-thd-green.log`.

3. **REVERT**: copy of `v2-thd`, reversed only the `models/esm2/collator.py` hunk (`git diff --stat`
   confirmed 1 file, 10 deletions / 1 insertion — the divisibility check and its `ValueError` removed,
   test file untouched). Re-ran against reverted source + v2 test: **failed again**, identical
   `DID NOT RAISE ValueError`, and the demo again drops the same token positions. Log:
   `bionemo-thd-revert.log`.

4. **SUITE.** The real `models/esm2/tests/test_collator_context_parallel.py` cannot be collected on either
   base or fixed: `ImportError while loading conftest ... ModuleNotFoundError: No module named
   'transformer_engine'`, reproduced independently in both my `base` and `v2-thd` copies. Logs:
   `bionemo-thd-suite-base.log`, `bionemo-thd-suite-fixed.log`.

5. **`check_copied_files.py`** (patch touches 10 mirrored copies of the same function across
   `models/{esm2,llama3,mixtral,qwen}` and 6 `recipes/*`): ran
   `ci/scripts/check_copied_files.py` (no `--fix`, no args) from the root of my own `v2-thd` copy:
   **exit code 0, no output** — all 10 copies match. Sanity-checked the checker itself is real and not a
   no-op: ran it against `base` (also exit 0 — all copies match pre-fix, as expected since the patch is
   applied uniformly) and against a copy where I reversed the fix in only `models/esm2/collator.py` while
   leaving the other 9 copies patched — this **correctly failed**: `ValueError: Files
   models/esm2/collator.py and models/llama3/collator.py do not match (ignoring banner). Run
   ci/scripts/check_copied_files.py --fix to fix.`, exit code 1. This confirms `check_copied_files.py`
   does perform a real content comparison and that the v2 patch's 10 files are consistent with each other.
   Log: `bionemo-thd-check-copied-files.log` (the clean `v2-thd` run only; the sanity-check failure above
   is quoted in this report but its log line was not separately saved to the mount, since it was a
   throwaway consistency probe on a scratch copy already deleted — reported here verbatim from the
   terminal output captured in this session).

**Discrepancies:** none. (Minor process note: the `check_copied_files.py` sanity-check-of-the-checker run
against the deliberately-mismatched scratch copy was not saved to a log file before that scratch copy was
deleted, since it was not one of the five required log types — its output is quoted above from the actual
command output in this session, not fabricated or reconstructed from memory.)

**PASS.**

---

## Final table

| ID | red | green | revert | suite | execution kind | PASS/FAIL |
|---|---|---|---|---|---|---|
| aiohttp-readuntil | 14 failed / 10 passed, matching claimed cause | 24 passed | 14 failed (= RED) | base 136 passed; fixed 160 passed (136+24, no regressions) | real pytest, real code (C ext disabled) | PASS |
| calibre-opds | harness: 4 unhandled exceptions in navcatalog | harness: 1 (documented-unreachable) unhandled | harness: 4 (= RED) | no test suite exists (independently confirmed); ruff check/format pass | harness (verbatim function extraction + stubs), no project test exists | PASS |
| bionemo-amplify | harness: 1 failed (fp32 vs bf16 assertion) | harness: 1 passed | harness: 1 failed (= RED) | project suite uncollectable on both (missing `datasets`, independently confirmed) | harness (verbatim function/test extraction, CPU torch, no transformer_engine) | PASS |
| bionemo-thd | harness: 1 failed (DID NOT RAISE) + demo shows dropped tokens | harness: 6 passed + demo raises correctly | harness: 1 failed (= RED) + demo drops tokens again | project suite uncollectable on both (missing `transformer_engine`, independently confirmed); `check_copied_files.py` exit 0 on fixed, sanity-checked as a real comparator | harness (verbatim function/test extraction, CPU torch, no transformer_engine) | PASS |

No fabrication: every RED/GREEN/REVERT result above was actually executed against a clean copy made in
this session, not inferred from the evidence folder's own logs (those were read only in the earlier
research step, before independent re-execution).
