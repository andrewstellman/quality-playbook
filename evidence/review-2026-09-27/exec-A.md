# Executor A — red/green re-run report

Fixes covered: aiohttp-readuntil, chi-gethead, express-cookie, calibre-opds, bionemo-amplify, bionemo-thd.
Each fix was worked in its own clean copy under `/tmp/review/exec/A/<ID>/`, scratch cleaned and disk checked (`df -h /tmp`) between fixes, bionemo fixes done last as instructed. All verbatim logs are at `/sessions/kind-zealous-edison/mnt/QPB/evidence/review-2026-09-27/exec-A/<ID>-{red,green,revert,suite-base,suite-fixed}.log`.

---

## aiohttp-readuntil

Pinned base SHA: `e11d2836203a21bec59095498e578d37801027e7`

Commands:
```
cp -a /tmp/review/src/aiohttp/base/. <dir>/ && chmod -R u+w <dir> && rm -f <dir>/.git && git init && git add -A && git commit -m base
git apply --include=tests/test_streams.py 0001-*.patch          # RED
AIOHTTP_NO_EXTENSIONS=1 PYTHONPATH=. /tmp/aiohttp-venv/bin/python -m pytest -p no:cacheprovider -n0 --no-cov tests/test_streams.py -k readuntil -v
git apply --exclude=tests/test_streams.py 0001-*.patch          # GREEN (fix)
... same pytest command ...
git apply -R --exclude=tests/test_streams.py 0001-*.patch       # REVERT
... same pytest command ...
git apply --exclude=tests/test_streams.py 0001-*.patch          # re-apply
pytest tests/test_streams.py                                     # SUITE fixed
(separately, clean base copy) pytest tests/test_streams.py       # SUITE base
```

- RED: 16 failed / 27 passed. All 16 failures are the new `test_readuntil_separator_split_*` parametrized cases; representative failure: `test_readuntil_separator_split_max_size` raised `LineTooLong` because the buggy code counted the separator's second byte twice into `chunk_size`, i.e. exactly the claimed "separator split across chunks" defect, not an import/fixture error.
- GREEN: 43 passed, 0 failed.
- REVERT: 16 failed / 27 passed — identical to RED (same test names, same failure).
- SUITE: base tree `tests/test_streams.py` = 136 passed. Fixed tree = 162 passed (136 + 26 new passing tests from the patch's own additions). No regressions, no new failures.
- Execution kind: real project pytest suite, unmodified test runner/venv.
- Discrepancy from claim: none found.

## chi-gethead

Pinned base SHA: `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`

Commands (GOCACHE/GOMODCACHE pointed into the scratch dir):
```
git apply --include=middleware/get_head_test.go 0001-*.patch    # RED
go test ./middleware/... -run TestGetHead -v
git apply --exclude=middleware/get_head_test.go 0001-*.patch    # GREEN
go test ./middleware/... -run TestGetHead -v
git apply -R --exclude=middleware/get_head_test.go 0001-*.patch # REVERT
go test ./middleware/... -run TestGetHead -v
git apply --exclude=middleware/get_head_test.go 0001-*.patch    # re-apply
go test ./... ; go test -race ./middleware/...                   # SUITE fixed
(clean base copy) go test ./... ; go test -race ./middleware/... # SUITE base
```

- RED: `TestGetHead` passes; new `TestGetHeadInMountedRouter` fails both assertions — `HEAD /api/hi: expected X-Handler 'head', got "get" (status 200)` and `HEAD /api/only-get: expected 200 with X-Handler 'get', got "" (status 405)`. This is exactly the claimed defect (sub-router HEAD handler ignored; false 405).
- GREEN: both `TestGetHead` and `TestGetHeadInMountedRouter` pass.
- REVERT: fails identically to RED (same two assertion messages).
- SUITE: base and fixed both `go test ./...` → `ok github.com/go-chi/chi/v5`, `ok .../middleware` (26.1–26.2s); `go test -race ./middleware/...` → `ok` on both (27.2–27.3s). No regressions, no race flags raised by the fix.
- Execution kind: real project Go test suite.
- Discrepancy from claim: none found.

## express-cookie

Pinned base SHA: `9a34acf03cb818ff3f8bc40e44176e277a25cbb9`. `npm install` (403 packages) in each working copy.

Commands:
```
git apply --include=test/res.cookie.js 0001-*.patch     # RED
npx mocha --reporter spec test/res.cookie.js
git apply --exclude=test/res.cookie.js 0001-*.patch     # GREEN
npx mocha --reporter spec test/res.cookie.js
git apply -R --exclude=test/res.cookie.js 0001-*.patch  # REVERT
npx mocha --reporter spec test/res.cookie.js
git apply --exclude=test/res.cookie.js 0001-*.patch     # re-apply
npm test                                                   # SUITE fixed
(clean base copy, npm install) npm test                   # SUITE base
```

- RED: 20 passing, 1 failing — `should not set Max-Age=0 for a positive sub-second maxAge`: `expected "Set-Cookie" matching /name=tobi; Max-Age=1; .../, got "name=tobi; Max-Age=0; Path=/; Expires=..."`. Exactly the claimed defect. (The companion new test for `maxAge:0` passed even unpatched, as expected since that's the "no regression" control case.)
- GREEN: 21 passing, 0 failing.
- REVERT: 20 passing / 1 failing, identical failure text to RED.
- SUITE: base `npm test` = 1261 passing. Fixed = 1263 passing (1261 + 2 new tests from the patch). No regressions.
- Execution kind: real project mocha suite via `npm test`.
- Discrepancy from claim: none found.

## calibre-opds

Pinned base SHA: `7691f4f1a155d799afdfec99e2cdc2716c178402`.

**Finding, prominent: the patch contains no test.** `grep '^diff --git' 0001-*.patch` shows exactly one file touched: `src/calibre/srv/opds.py`. No test file is added or modified.

Per protocol, ran the validator's stubbed-extraction reproducer (`/sessions/kind-zealous-edison/mnt/QPB/evidence/calibre-opds-navcatalog/harness.py`) against my own clean copies, independently. This is **stubbed extraction of real handler code, not the real server and not a project test** — the harness `ast`-extracts `opds_navcatalog`/`opds_category`/`opds_categorygroup` verbatim from `src/calibre/srv/opds.py` and `parse_request_uri`/`parse_uri` from `http_request.py`, and stubs `RequestContext`, `get_all_books`, `get_navcatalog`. I confirmed independently (separately from the validator) that the real `calibre` package cannot be imported in this sandbox at all: `import calibre` fails with `AttributeError: module 'sys' has no attribute 'extensions_location'` (needs compiled extensions), on both base and fixed trees — so no real project test suite exists to run here regardless of patch state. I built a Python 3.14 venv via `uv` (matching the validator's environment note) since the harness needs match-statement/newer syntax support the sandbox's system Python 3.10 lacks (confirmed: system python3.10 fails on the annotated function def with `NameError: name 'Context' is not defined` due to a different code path unrelated to the patch — noted as my own environment finding, not a patch defect).

Commands:
```
git apply 0001-*.patch   # whole patch (no test-only subset exists)
.venv314/bin/python harness.py <base/src>      # RED
.venv314/bin/python harness.py <fixed/src>     # GREEN
```

- RED (base): 4 of 7 `opds_navcatalog` cases raise `UNHANDLED` exceptions — `IndexError: string index out of range` (empty `which`), `binascii.Error: Non-hexadecimal digit found` (`zz`), `binascii.Error: Odd-length string` (`4`), `UnicodeDecodeError` (`ff`). `RESULT: RED`.
- GREEN (fixed): all 7 cases pass; the same 4 malformed inputs now return `HTTP404`. `RESULT: GREEN`.
- REVERT: since there is no test-only subset to keep, "revert" here is simply re-running the harness against the base tree, which is the RED run above — already captured.
- SUITE: no project suite is runnable (import barrier independent of the patch, verified both trees). Logged as such.
- **Additional finding**: the harness's "informational, not counted" section shows `opds_category` and `opds_categorygroup` — siblings that parse the same kind of hex-id argument — still raise unhandled `binascii.Error` on malformed input on the FIXED tree (the patch only touches `opds_navcatalog`). This is a real, independently-observed scope gap: the same bug class is very likely present in the two sibling endpoints and the patch doesn't address them.
- Execution kind: validator's stubbed-extraction harness (verbatim real code + stubs), re-run independently against my own copies from the read-only base/patch. Not the real server, not a project test.

## bionemo-amplify

Pinned base SHA: `11701476b005ca7bc489df924a398b8f12453f0b`.

The real module cannot be imported here: `amplify.state_dict_convert` imports `amplify.amplify_te`, which does `import transformer_engine.pytorch` — CUDA-only, no CPU wheel, confirmed independently by direct import attempt on both trees. Installed CPU PyTorch via `uv pip install --index-url https://download.pytorch.org/whl/cpu torch` (with `TMPDIR`/`UV_CACHE_DIR` redirected onto the `/tmp` filesystem — the default `/sessions/...tmp` mount had only ~146 MB free and caused an extraction failure on the first attempt; documenting this as an environment note, not a patch issue). Confirmed the project's own pytest test-collection is blocked independent of torch/transformer_engine: `models/amplify/tests/conftest.py` does `from datasets import Dataset`, and `datasets` isn't installed (and installing it doesn't fix the deeper transformer_engine blocker).

Rather than use the validator's hardcoded harness as-is, I wrote my own `ast`-based extraction that pulls `_pad_weights` verbatim out of the real `state_dict_convert.py` in each tree (base pinned source, and my patched copy) and ran the exact scenario from the patch's own regression test (bf16, CPU, 10→12 padding rows).

- I first diffed the actual source at `models/amplify/src/amplify/state_dict_convert.py` lines 85-91 (base and patched) against the validator's hardcoded `pad_weights_amplify_buggy`/`pad_weights_amplify_fixed` functions: **identical, verbatim, both directions.** Also diffed the referenced ESM2 sibling `models/esm2/convert.py:238-246` against the validator's `pad_weights_esm2_reference`: **identical, verbatim.** So the validator's hardcoded copy is accurate; my own extraction is an independent second check using the real files rather than a copy.
- RED (base, my own harness): `source dtype=torch.bfloat16 device=cpu -> out dtype=torch.float32 device=cpu shape=(12, 4)` — dtype mismatch, confirming the claimed silent upcast to fp32. `RESULT: RED`.
- GREEN (patched): `out dtype=torch.bfloat16 device=cpu` — dtype preserved, shape correct. `RESULT: GREEN`.
- REVERT: re-running against the base tree reproduces RED exactly (same numbers).
- SUITE: not runnable — real test collection blocked by `datasets` import in `conftest.py`, and even past that, `transformer_engine` has no CPU path. This blocks base and fixed identically (verified both).
- Execution kind: my own ast-extraction of the verbatim real function (independent of, but cross-checked against, the validator's harness) with CPU PyTorch. Not a project test run.

## bionemo-thd

Pinned base SHA (same bionemo repo): `11701476b005ca7bc489df924a398b8f12453f0b`.

Same blocker class as amplify: `models/esm2/collator.py` does `import datasets` (line 26), `import nvtx` (line 27), and `from transformer_engine.pytorch.attention...` (line 29) at module scope — confirmed independently that real pytest collection of the patch's own `test_cp_thd_divisibility_guard.py` fails with `ModuleNotFoundError: No module named 'datasets'` on the patched tree (and would fail identically on base, since the import statement itself is unchanged by the patch).

I wrote my own `ast`-extraction harness pulling `_find_seq_dim`, `_process_tensor_thd`, `_process_tensor_bshd`, and `_split_batch_by_cp_rank` verbatim out of the real `models/esm2/collator.py` (base pinned source and my patched copy), and reproduced the patch's own three assertions (reject non-divisible length, accept divisible length with no dropped tokens, and a direct demonstration of the dropped-token count).

Cross-check against the validator's hardcoded harness (`harness_thd_sharding.py`): diffed the shared helper block (`_find_seq_dim`/`_process_tensor_thd`/`_process_tensor_bshd`, source lines 733-868) — byte-identical to the actual pinned source (only difference was a trailing comment artifact from my own `sed` extraction boundary, not a real discrepancy). Compared the buggy `_split_batch_by_cp_rank` via `ast.unparse()` against the harness's `_split_batch_by_cp_rank_buggy` — same control flow, same floor-division bug line, logically identical. The harness's "fixed" guard message text ("...for THD context parallelism") is a paraphrase of the actual patch's message ("...for THD context parallelism, matching the guard already enforced by the BSHD branch (_process_tensor_bshd)") — same trigger condition and exception type, message text not verbatim in the harness (this is the validator's simplification, not a defect in the patch).

- RED (base, my own harness): `rejects_non_divisible` → **FAIL** ("no ValueError raised (silent data loss path)"); `silent_data_loss_demo` → confirms it directly: `NO ERROR RAISED; tokens collected across all ranks=[0..15]; MISSING (dropped) tokens=[16, 17]` — i.e., with `len_b=10` and `total_slices=4`, tokens 16 and 17 (the remainder `10 % 4 = 2`) are silently never selected by any CP rank. This is the exact defect claimed. `accepts_divisible_no_regression` passes on base too (expected — the no-regression control case doesn't exercise the bug).
- GREEN (patched): `rejects_non_divisible` → PASS, raises `ValueError: Padded sequence length(s) [10] must be divisible by 4 (2 * cp_world_size) for THD context parallelism, matching the guard already enforced by the BSHD branch (_process_tensor_bshd).` `accepts_divisible_no_regression` still passes (all 16 tokens seen, no dropped tokens). The `silent_data_loss_demo` test now raises (this is the desired GREEN behavior — the label reads "FAIL/INFO" in my harness output because the demo's "success" condition was defined as "no error raised," which is what happens on the buggy tree; on the fixed tree the guard fires instead, which is correct).
- REVERT: re-run against base reproduces RED exactly (dropped tokens `[16, 17]`, no exception).
- Propagation check: confirmed via patch text (not independently executed) that the identical collator.py hunk (same guard, same line shape, only file-path header differs) is applied to `models/llama3/collator.py`, `models/mixtral/collator.py`, `models/qwen/collator.py`. Did not diff or execute the `recipes/*` copies beyond confirming their diff hunks exist in the patch — this is a gap in my verification, noted rather than glossed over.
- SUITE: not runnable — real pytest collection blocked by `datasets` import identically on both trees (verified).
- Execution kind: my own ast-extraction of the verbatim real function (cross-checked against the validator's harness) with CPU PyTorch. Not a project test run.

---

## Summary table

| ID | red | green | revert | suite | execution kind | PASS/FAIL |
|---|---|---|---|---|---|---|
| aiohttp-readuntil | fails, correct reason (16/43 new tests, separator-split defect) | 43/43 pass | fails again, identical to red | base 136 pass → fixed 162 pass, no regressions | real project pytest | **PASS** |
| chi-gethead | fails, correct reason (mounted-router HEAD ignored, false 405) | pass | fails again, identical to red | `go test ./...` and `-race ./middleware/...` both ok, base==fixed | real project go test | **PASS** |
| express-cookie | fails, correct reason (Max-Age=0 instead of 1) | 21/21 pass | fails again, identical to red | base 1261 → fixed 1263 pass, no regressions | real project mocha via npm test | **PASS** |
| calibre-opds | N/A (no test in patch) — validator harness RED: 4/7 cases UNHANDLED | validator harness GREEN: 7/7 pass | N/A (no test-only subset) | not runnable (import barrier, both trees) | validator's stubbed-extraction harness, verbatim source + stubs | **PASS** (fix verified via harness), but see finding: no test included, and sibling endpoints `opds_category`/`opds_categorygroup` still vulnerable to the same bug class |
| bionemo-amplify | my ast-extraction RED: dtype upcast to fp32 confirmed | GREEN: dtype preserved | fails again, identical to red | not runnable (transformer_engine/datasets import barrier, both trees) | my own ast-extraction of real verbatim source (cross-checked vs. validator harness — identical) | **PASS** |
| bionemo-thd | my ast-extraction RED: no guard, tokens [16,17] silently dropped | GREEN: guard raises `ValueError`, no dropped tokens, no-regression case intact | fails again, identical to red | not runnable (transformer_engine/datasets/nvtx import barrier, both trees) | my own ast-extraction of real verbatim source (cross-checked vs. validator harness — logically identical) | **PASS** |

## Findings Andrew must know

1. **calibre-opds ships with no test.** The PR draft/patch does not add or modify any test file (`grep '^diff --git'` shows one file changed). I verified the fix behavior only via the validator's stubbed-extraction harness (real code, ast-extracted, with stubbed `RequestContext`/`get_all_books`/`get_navcatalog`), not a project test, and not the real running server.
2. **calibre-opds fix is narrower than the underlying bug class.** `opds_category` and `opds_categorygroup` parse hex ids the same way as `opds_navcatalog` and, per the harness's own "siblings" section (independently re-run by me), still throw unhandled `binascii.Error` on malformed input after the patch is applied — i.e., the same 500-instead-of-404 defect is very likely still present in two sibling endpoints the patch doesn't touch.
3. **Both bionemo fixes are unrunnable as real project tests in any CPU sandbox**, not just this one: `transformer_engine` (CUDA-only, no CPU wheel) is imported transitively by both `amplify.state_dict_convert` and `models/esm2/collator.py`, and the esm2 collator additionally requires `datasets`/`nvtx` at import time. I verified this blocks the *unpatched* tree exactly as it blocks the patched tree, so it isn't something the patch introduced — but neither the patch's own new test nor any pre-existing test in these files can be run and reported as "passing" against real CI without a GPU environment. My verification for both is a from-scratch ast-extraction of the actual verbatim function bodies, cross-checked against the validator's own hardcoded harness (found to match).
4. Environment note (not a patch defect): the sandbox's `/sessions/...` tmp mount was at 99% capacity (146 MB free) while `/tmp` itself had headroom; the first `uv pip install torch` attempt failed on that mount until I redirected `TMPDIR`/`UV_CACHE_DIR` onto `/tmp`.
5. For bionemo-thd, I did not independently execute or diff the `recipes/*` collator.py copies (esm2_native_te, esm2_peft_te, llama3_native_te, mixtral_native_te, opengenome2_llama_native_te) beyond confirming their diff hunks exist in the patch text — only `models/esm2`, `models/llama3`, `models/mixtral`, `models/qwen` were hunk-diffed, and only `models/esm2` was executed.
