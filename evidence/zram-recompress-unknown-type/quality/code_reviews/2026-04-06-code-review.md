# Code Review: zram subsystem
**Date:** 2026-04-06
**Reviewer:** Copilot (three-pass review per `quality/RUN_CODE_REVIEW.md`)
**Files reviewed:** `drivers/block/zram/zram_drv.c`, `zcomp.c`, `backend_zstd.c`, `backend_lzo.c`
**Reference docs:** `Documentation/admin-guide/blockdev/zram.rst`, `docs_gathered/zram-community-development-history.md`, `docs_gathered/zsmalloc-design.md`, `quality/QUALITY.md`, `quality/REQUIREMENTS.md`

---

## Pass 1: Structural Review

### drivers/block/zram/zram_drv.c

- **Line 1440–1446:** **BUG** — `read_from_bdev_async()` silently discards allocation failures without signaling the parent bio.

  ```c
  req = kmalloc_obj(*req, GFP_NOIO);
  if (!req)
      return;                          // ← no error propagation

  bio = bio_alloc(zram->bdev, 1, parent->bi_opf, GFP_NOIO);
  if (!bio) {
      kfree(req);
      return;                          // ← no error propagation
  }
  ```

  `bio_inc_remaining(parent)` is only reached if both allocations succeed (line 1460). If either fails, the parent bio is never told about the missing child read. The caller `read_from_bdev()` (line 1510) returns 0 regardless. The caller's caller `zram_read_page()` then returns 0, and `zram_bio_read()` never increments `failed_reads` or sets `bi_status`. Under memory pressure—exactly the scenario where zram is deployed as swap—this silently serves stale or zeroed data to the page consumer.

  **Confirmed BUG.** Regression test: `quality/test_regression.py::TestConfirmedBugs::test_async_backing_read_setup_failure_is_reported`

- **Line 2698–2700:** **BUG** — `zram_bio_discard()` returns early without completing the bio when an entire discard request fits within a leading unaligned fragment.

  ```c
  if (offset) {
      if (n <= (PAGE_SIZE - offset))
          return;    // ← bio_endio(bio) never called
  ```

  `bio_endio(bio)` at line 2715 is only reached when the function falls through to the `while (n >= PAGE_SIZE)` loop. If the discard is completely contained within one page's tail fragment (offset > 0 and n ≤ PAGE_SIZE − offset), the function returns bare. The bio is neither completed nor redirected. From the block layer's perspective the request is permanently in flight; this hangs the submitter or corrupts the request queue depending on the I/O scheduler.

  **Confirmed BUG.** Regression test: `quality/test_regression.py::TestConfirmedBugs::test_unaligned_single_fragment_discard_completes_bio`

- **Line 1699 (`algorithm_params_store`):** **BUG** — `algorithm_params_store()` modifies `zram->params[prio]` at any time, including after `disksize_store()` has initialized the device and created live compressor objects.

  ```c
  static ssize_t algorithm_params_store(...) {
      // no init_done(zram) check anywhere in this function
      ...
      ret = comp_params_store(zram, prio, level, dict_path, &deflate_params);
  ```

  `comp_params_store()` (line 1675) calls `comp_params_reset()` first, which calls `vfree(params->dict)` (line 1668). For the zstd backend, `zstd_setup_params()` creates a `cdict` and `ddict` via `zstd_create_cdict_byreference()` (backend_zstd.c:72–83). The `byreference` variant holds a pointer into `params->dict`—not a copy. Freeing `params->dict` while the live cdict still references it is a use-after-free during any subsequent compression call. Even for non-dict backends, this mutates configuration state that all peer handlers treat as frozen.

  **Confirmed BUG.** Regression test: `quality/test_regression.py::TestConfirmedBugs::test_algorithm_params_are_frozen_after_init`

- **Line 1242 (`writeback_store`):** **QUESTION** — `nr_pages` is snapshotted from `zram->disksize` before the `dev_lock` write-lock is acquired at line 1250.

  ```c
  u64 nr_pages = zram->disksize >> PAGE_SHIFT;   // line 1242, pre-lock
  ...
  guard(rwsem_write)(&zram->dev_lock);           // line 1250
  if (!init_done(zram))
      return -EINVAL;
  ```

  A concurrent `disksize_store()` setting `disksize` from 0 between lines 1242 and 1250 leaves `nr_pages = 0` while `init_done` returns true inside the lock. The scan range becomes `[0, 0)`, writeback does nothing, and the sysfs write returns success. This is a silent no-op rather than corruption or a hang. **QUESTION** (impact: misleading success response; not data-integrity-threatening).

- **Line 1881–1885 (`io_stat_show`):** **QUESTION** — the `invalid_io` column is hardcoded to `0` in the format string.

  ```c
  ret = sysfs_emit(buf, "%8llu %8llu 0 %8llu\n", ...)
  ```

  `Documentation/admin-guide/blockdev/zram.rst §205–210` defines the third column as "number of non-page-size-aligned I/O requests." There is no `invalid_io` counter in `struct zram_stats`. On 4K page systems `is_partial_io()` always returns false so there would be no such requests, but on non-4K systems the driver silently accepts sub-page vectors without counting them. **QUESTION** (potential docs-vs-code drift; likely harmless on common 4K page systems).

- **Line 948–954 (`zram_writeback_complete`):** **QUESTION** — `ZRAM_HUGE` flag is intentionally not cleared on successful writeback.

  ```c
  if (test_slot_flag(zram, index, ZRAM_HUGE))
      atomic64_dec(&zram->stats.huge_pages);
  // ZRAM_HUGE flag left set — slot is now WB+HUGE
  ...
  set_slot_flag(zram, index, ZRAM_WB);
  ```

  The comment in `slot_free()` (line 1997) explains: "Writeback completion decrements `->huge_pages` but keeps ZRAM_HUGE flag for deferred decompression path." `decompress_bdev_page()` (line 1356–1358) checks ZRAM_HUGE and returns 0 without decompressing—correct because huge pages are stored uncompressed on the backing device in both `compressed_writeback` modes. This is an undocumented implicit protocol but appears internally consistent. **QUESTION** (not a bug; documentation gap in `zram.rst`).

### drivers/block/zram/backend_zstd.c

- **Lines 72–83 (`zstd_setup_params`):** **QUESTION** — `zstd_create_cdict_byreference` stores a pointer to `params->dict` rather than copying it. This is only exploitable via the `algorithm_params_store` post-init bug. Once that guard is added this concern is moot. Classified as QUESTION rather than independent BUG.

### drivers/block/zram/zcomp.c

- No structural bugs found. `zcomp_stream_get()` correctly handles migration races via the `buffer == NULL` liveness check (line 126). CPU hotplug callbacks are registered with `cpuhp_state_add_instance` and streams are properly released via `zcomp_cpu_dead`. The `zcomp_strm_free` / `zcomp_strm_init` lifecycle is clean.

---

## Pass 2: Requirement Verification

#### REQ-002: Disksize is the initialization gate and freezes layout-sensitive knobs
**Status:** SATISFIED
**Evidence:** `zram_drv.c:2886` — `if (init_done(zram)) { ... return -EBUSY; }`; `zram_drv.c:2916–2918` — `out_free_comps` tears down comps and meta on backend failure.
**Analysis:** `disksize_store()` holds the write lock, checks `init_done`, allocates meta and all configured compressors, sets `disksize` only on full success, and rolls back all allocations on any backend failure. Satisfies all four conditions of satisfaction.

---

#### REQ-003: Runtime memory limits and statistics-reset input are narrow and explicit
**Status:** SATISFIED
**Evidence:** `zram_drv.c:390–392` — `memparse` for `mem_limit`; `zram_drv.c:408–410` — `if (err || val != 0) return -EINVAL` for `mem_used_max`.
**Analysis:** `mem_limit_store` accepts suffix-form sizes, page-aligns, and stores without an init gate (runtime-mutable as documented). `mem_used_max_store` accepts only literal `0` and snapshots the pool total when initialized.

---

#### REQ-004: Primary compressor selection is limited to supported pre-init algorithms
**Status:** SATISFIED
**Evidence:** `zram_drv.c:1637–1638` — `if (sz >= ZRAM_MAX_ALGO_NAME_SZ) return -E2BIG`; `zram_drv.c:1648–1651` — `if (!zcomp_available_algorithm(compressor)) return -EINVAL`; `zram_drv.c:1654–1658` — `if (init_done(zram)) ... return -EBUSY`.
**Analysis:** All four conditions of satisfaction are met. Secondary compressors (`recomp_algorithm_store`) use the same `__comp_algorithm_store` path and therefore the same guards.

---

#### REQ-005: Algorithm parameters are bound by priority/algo selectors and explicit key parsing
**Status:** VIOLATED
**Evidence:** `zram_drv.c:1699–1771` — entire `algorithm_params_store()` body contains no `init_done(zram)` check.
**Analysis:** The function is the only configuration sysfs handler that mutates `zram->params[prio]` without a pre-init guard. Every peer handler (`comp_algorithm_store`, `backing_dev_store`, `compressed_writeback_store`) rejects post-init writes. Per `Documentation/admin-guide/blockdev/zram.rst §§96–126`, algorithm parameters are part of the pre-init configuration surface alongside compressor selection. Post-init writes can free the dictionary while active compressors reference it (see structural finding at backend_zstd.c:72–83).
**Severity:** HIGH — potential use-after-free on the zstd backend; silent behavioral mutation on all backends.

---

#### REQ-006: Backing device setup is pre-init-only and block-device-only
**Status:** SATISFIED
**Evidence:** `zram_drv.c:741–745` — `if (init_done(zram)) { err = -EBUSY; goto out; }`; `zram_drv.c:763–766` — `if (!S_ISBLK(...)) { err = -ENOTBLK; goto out }`; `zram_drv.c:769–773` — `if (!nr_pages) { err = -EINVAL; goto out }`; `zram_drv.c:782–787` — atomic assignment of all four state fields on success.
**Analysis:** All four conditions of satisfaction are met.

---

#### REQ-007: Writeback feature knobs preserve ordering and input bounds
**Status:** SATISFIED
**Evidence:** `zram_drv.c:563–565` — `compressed_writeback_store` returns `-EBUSY` when initialized; `zram_drv.c:632` — `val = rounddown(val, PAGE_SIZE / 4096)` for writeback limit; `zram_drv.c:662–663` — `if (!val) return -EINVAL` for batch size; `zram_drv.c:927–930` — `zram_account_writeback_rollback` increments limit on bio failure.
**Analysis:** Rollback at line 929 restores exactly `1 << (PAGE_SHIFT - 12)` units, matching the deduction in `zram_account_writeback_submit` (line 915). All four conditions of satisfaction are met.

---

#### REQ-008: Writeback request parsing supports both modern and legacy syntax
**Status:** SATISFIED
**Evidence:** `zram_drv.c:1284–1293` — valueless token handled as legacy mode; `zram_drv.c:1295–1303` — `type=` key; `zram_drv.c:1306–1325` — `page_index=` and `page_indexes=` keys; `zram_drv.c:1181–1196` — `parse_mode` accepts all four documented mode strings.
**Analysis:** All four conditions of satisfaction are met. The legacy compatibility path correctly invokes `scan_slots_for_writeback` via `break`, not `continue`, preventing stale `mode=0` scans.

---

#### REQ-009: Writeback selection and completion preserve slot ownership
**Status:** SATISFIED
**Evidence:** `zram_drv.c:1212–1224` — `scan_slots_for_writeback` excludes ZRAM_WB and ZRAM_SAME, then filters by mode flags; `zram_drv.c:943–946` — `if (!test_slot_flag(zram, index, ZRAM_PP_SLOT)) { zram_release_bdev_block(...); goto out; }` in `zram_writeback_complete`; `zram_drv.c:927–930` — budget rollback on bio failure.
**Analysis:** All five conditions of satisfaction are met. The reserved block is released on both the "lost ownership" path (line 944) and the "bio failure" path (line 930).

---

#### REQ-010: Recompression is eligibility-driven and progress-based
**Status:** SATISFIED
**Evidence:** `zram_drv.c:2358–2361` — `scan_slots_for_recompress` excludes WB, SAME, INCOMPRESSIBLE; `zram_drv.c:2406–2407` — skips objects already below threshold; `zram_drv.c:2455–2459` — `if (class_index_new >= class_index_old || ...) continue` rejects non-improving compressions; `zram_drv.c:2600–2601` — `if (threshold >= huge_class_size) return -EINVAL`.
**Analysis:** All four conditions of satisfaction are met. `max_pages` is decremented on every attempt (line 2472–2473), not only on successful improvement.

---

#### REQ-011: Recompression updates slot flags to match the new state
**Status:** SATISFIED
**Evidence:** `zram_drv.c:2418` — `clear_slot_flag(zram, index, ZRAM_IDLE)` before any compressor loop iteration; `zram_drv.c:2487–2489` — `ZRAM_INCOMPRESSIBLE` set only when `prio >= zram->num_active_comps`; `zram_drv.c:2515–2518` — successful recompression updates handle, size, and priority atomically under slot lock.
**Analysis:** All four conditions of satisfaction are met. The guard at line 2487 correctly distinguishes "exhausted all configured compressors" from "still have compressors to try."

---

#### REQ-012: Same-filled pages are stored and read through synthetic state
**Status:** SATISFIED
**Evidence:** `zram_drv.c:340–360` — `page_same_filled()` checks every word across the full page (both first and last word, then all middle words); `zram_drv.c:2188–2195` — `write_same_filled_page` calls `slot_free` before setting ZRAM_SAME and installing the fill value; `zram_drv.c:2041–2043` — `read_same_filled_page` synthesizes the page from the stored handle.
**Analysis:** All four conditions of satisfaction are met. Counter coherence: `slot_free` decrements `same_pages` (for prior SAME slots) and `pages_stored`, then `write_same_filled_page` increments both.

---

#### REQ-013: Incompressible pages are stored raw at page size
**Status:** SATISFIED
**Evidence:** `zram_drv.c:2269–2271` — `if (comp_len >= huge_class_size) { zcomp_stream_put(zstrm); return write_incompressible_page(...); }`; `zram_drv.c:2217–2220` — `zram_can_store_page` check before committing the slot; `zram_drv.c:2047–2061` — `read_incompressible_page` does a raw `copy_page` from zsmalloc.
**Analysis:** All four conditions of satisfaction are met.

---

#### REQ-014: Read dispatch follows slot representation and backing state
**Status:** PARTIALLY SATISFIED
**Evidence (satisfied paths):** `zram_drv.c:2120–2127` — `read_from_zspool` dispatches to same-filled, compressed, or incompressible path correctly; `zram_drv.c:2136–2148` — ZRAM_WB slots go to `read_from_bdev`; `zram_drv.c:2731–2734` — decompression failure sets `BLK_STS_IOERR` and increments `failed_reads`.
**Evidence (violated condition):** `zram_drv.c:1439–1446` — allocation failures in `read_from_bdev_async` return silently without setting `parent->bi_status` or calling `bio_endio(parent)`.
**Analysis:** Conditions 1–3 are satisfied. Condition 4 (failure surfaced as `BLK_STS_IOERR`) is satisfied for synchronous paths and for bio I/O errors in the async endio (line 1401), but **not** for the async setup allocation failure path.
**Severity:** HIGH — silent data corruption or bio hang under memory pressure on any writeback-backed slot.

---

#### REQ-015: Write, partial-write, and discard flows preserve untouched bytes and complete bios
**Status:** PARTIALLY SATISFIED
**Evidence (satisfied conditions):** `zram_drv.c:2310–2321` — partial write reads the full page, patches the requested bytes, then writes; `zram_drv.c:2328–2330` — full-page writes skip the temp page; `zram_drv.c:2706–2713` — discard frees only full physical pages.
**Evidence (violated condition):** `zram_drv.c:2699–2700` — `if (n <= (PAGE_SIZE - offset)) return;` exits before `bio_endio(bio)` at line 2715.
**Analysis:** Conditions 1–3 are satisfied. Condition 4 (bio always completed exactly once) is violated for the specific case where the discard request is entirely within a leading unaligned fragment.
**Severity:** HIGH — stranded bio; I/O hang on any filesystem or swap caller that issues a sub-page-aligned discard smaller than the leading fragment.

---

#### REQ-018: Reset and remove fully quiesce the device before freeing storage state
**Status:** SATISFIED
**Evidence:** `zram_drv.c:2934–2935` — `if (!do_reset) return -EINVAL`; `zram_drv.c:2942–2944` — `if (disk_openers(disk) || zram->claim) ... return -EBUSY`; `zram_drv.c:2952–2953` — `sync_blockdev(disk->part0)` before `zram_reset_device`; `zram_drv.c:3164–3165` — final `zram_reset_device(zram)` after `del_gendisk()` to catch late `disksize_store` races; `zram_drv.c:2853–2869` — `zram_reset_device` zeroes capacity, stats, limits, backing-device state, and compressor state.
**Analysis:** All five conditions of satisfaction are met. The "final reset after del_gendisk" pattern correctly handles the `disksize_store` / `del_gendisk` race documented in the comment at lines 3161–3164.

---

## Pass 3: Cross-Requirement Consistency

#### Shared Concept: Initialization freeze
**Requirements:** REQ-002, REQ-004, REQ-006, REQ-007
**Consistency:** INCONSISTENT (REQ-005 violates the pattern)
**Code evidence:**
- `disksize_store` (REQ-002): `if (init_done(zram)) return -EBUSY` at line 2886.
- `__comp_algorithm_store` (REQ-004): `if (init_done(zram)) return -EBUSY` at line 1654.
- `backing_dev_store` (REQ-006): `if (init_done(zram)) { err = -EBUSY; goto out; }` at line 741.
- `compressed_writeback_store` (REQ-007): `if (init_done(zram)) { return -EBUSY; }` at line 563.
- `algorithm_params_store` (REQ-005): **no `init_done` check anywhere.**
**Analysis:** Every other layout-altering sysfs handler consistently rejects post-init writes. `algorithm_params_store` is the sole exception. This violates the initialization-freeze contract that `Documentation/admin-guide/blockdev/zram.rst §§96–126` implies for pre-init configuration. The inconsistency is not a documentation ambiguity — the docs treat parameter setting as part of the pre-init setup sequence alongside compressor selection, using the same ordering language.

---

#### Shared Concept: Slot-state machine
**Requirements:** REQ-009, REQ-011, REQ-012, REQ-013, REQ-014, REQ-015
**Consistency:** CONSISTENT (with one intentional deviation noted)
**Code evidence:**
- ZRAM_SAME: set exclusively via `write_same_filled_page` after `slot_free`; read via `read_same_filled_page`; cleared in `slot_free`.
- ZRAM_HUGE: set in `write_incompressible_page`; cleared in `slot_free` for non-WB paths; intentionally **not** cleared in `zram_writeback_complete` (lines 948–954); `decompress_bdev_page` uses ZRAM_HUGE to skip decompression for WB+HUGE slots.
- ZRAM_WB: set only in `zram_writeback_complete` after ownership verified; cleared in `slot_free`; read path checks in `zram_read_page` (line 2136).
- ZRAM_IDLE: cleared in `mark_slot_accessed`, in `recompress_slot` (line 2418), and in `zram_writeback_complete` (line 948).
- ZRAM_INCOMPRESSIBLE: set in `recompress_slot` (line 2489); cleared in `slot_free` (line 1992); excluded from recompression scan.
- ZRAM_PP_SLOT: set in `place_pp_slot`; cleared in `release_pp_slot`; used as ownership signal in both `zram_writeback_complete` and `recompress_slot`.
**Analysis:** The state machine is internally consistent across all six requirements. The WB+HUGE dual-flag combination is an undocumented but intentional protocol: HUGE on a WB slot means "stored raw, no decompression needed on readback." No cross-requirement inconsistency exists in the slot state machine itself; the violations in REQ-014 and REQ-015 are bio-completion failures, not slot-flag errors.

---

#### Shared Concept: Backing-device accounting
**Requirements:** REQ-007, REQ-009, REQ-016 (bd_stat)
**Consistency:** CONSISTENT
**Code evidence:**
- `zram_reserve_bdev_block` (lines 804–814): `set_bit` + `atomic64_inc(&bd_count)` atomically paired.
- `zram_release_bdev_block` (lines 817–824): `test_and_clear_bit` + `atomic64_dec(&bd_count)` with WARN on double-free.
- `zram_account_writeback_submit` (lines 910–915): decrements `bd_wb_limit` before submission.
- `zram_account_writeback_rollback` (lines 902–908): increments `bd_wb_limit` on bio failure.
- `atomic64_inc(&bd_writes)` in `zram_writeback_complete` (line 934): only on success, after ZRAM_PP_SLOT re-check.
- `bd_stat_show` (lines 536–549): reports `bd_count`, `bd_reads`, `bd_writes` in 4K units via `FOUR_K()`.
**Analysis:** Accounting is consistent: block reservation and stat increment are always paired, rollback correctly restores budget, and `bd_stat` reflects actual state.

---

#### Shared Concept: Lifecycle teardown
**Requirements:** REQ-001, REQ-002, REQ-018
**Consistency:** CONSISTENT
**Code evidence:**
- `zram_add` (line 3042): capacity zero, no metadata allocated, default compressor only.
- `reset_store` (lines 2922–2959): claim → sync → reset → unclaim.
- `zram_remove` (lines 3124–3169): open-mutex claim → sync → reset → del_gendisk → final reset → free.
- `zram_reset_device` (lines 2853–2870): holds write lock, zeroes disksize, frees meta, destroys comps, zeroes stats, resets bdev.
**Analysis:** REQ-001 (zero-capacity initial state) and REQ-018 (safe teardown) are mutually consistent. The double-reset pattern in `zram_remove` (line 3150 + 3165) is a deliberate defense against the `disksize_store` / `del_gendisk` race.

---

## Combined Summary

| Source | Finding | Severity | Status | Regression Test |
|--------|---------|----------|--------|-----------------|
| Pass 1, `zram_drv.c:1440–1446` | `read_from_bdev_async()` silently drops allocation failures; parent bio never completed with error; silent data corruption or hang under memory pressure | HIGH | **BUG** | `test_regression.py::TestConfirmedBugs::test_async_backing_read_setup_failure_is_reported` |
| Pass 1, `zram_drv.c:2699–2700` | `zram_bio_discard()` returns without `bio_endio()` for unaligned single-fragment discard; I/O hang | HIGH | **BUG** | `test_regression.py::TestConfirmedBugs::test_unaligned_single_fragment_discard_completes_bio` |
| Pass 1, `zram_drv.c:1699` | `algorithm_params_store()` lacks `init_done` guard; post-init calls free dictionary referenced by active zstd cdict; use-after-free | HIGH | **BUG** | `test_regression.py::TestConfirmedBugs::test_algorithm_params_are_frozen_after_init` |
| Pass 1, `zram_drv.c:1242` | `nr_pages` snapshotted before lock in `writeback_store`; race with `disksize_store` causes silent no-op writeback | LOW | **QUESTION** | No regression test — not confirmed as data-integrity threat |
| Pass 1, `zram_drv.c:1881–1885` | `io_stat_show` hardcodes `invalid_io` column to `0`; no counter exists in `zram_stats` | LOW | **QUESTION** | No regression test — likely docs drift on 4K-page systems |
| Pass 2, REQ-005 | `algorithm_params_store` violates pre-init-only contract shared by all layout-altering knobs | HIGH | **VIOLATED** | `test_regression.py::TestConfirmedBugs::test_algorithm_params_are_frozen_after_init` |
| Pass 2, REQ-014 | Async backing-device read setup failure not surfaced as `BLK_STS_IOERR`; parent bio silently hangs | HIGH | **PARTIALLY SATISFIED** | `test_regression.py::TestConfirmedBugs::test_async_backing_read_setup_failure_is_reported` |
| Pass 2, REQ-015 | Unaligned single-fragment discard exits without completing bio | HIGH | **PARTIALLY SATISFIED** | `test_regression.py::TestConfirmedBugs::test_unaligned_single_fragment_discard_completes_bio` |
| Pass 3, REQ-002/004/006/007 vs REQ-005 | Init-freeze applied inconsistently: `algorithm_params_store` is the only layout-altering handler without a guard | HIGH | **INCONSISTENT** | Same as REQ-005 entry above |

### Totals by pass

| Pass | BUGs | Questions |
|------|------|-----------|
| Pass 1 | 3 confirmed | 2 questions |
| Pass 2 | 3 violations (1 VIOLATED, 2 PARTIALLY SATISFIED) | 0 |
| Pass 3 | 1 inconsistency | 0 |

### Overall assessment: **FIX FIRST**

Three confirmed bugs affect bio-completion safety and memory safety:

1. **`read_from_bdev_async` silent failure** (`zram_drv.c:1440–1446`) — fix: on each allocation failure, set `parent->bi_status = BLK_STS_IOERR` and call `bio_endio(parent)` before returning.
2. **`zram_bio_discard` stranded bio** (`zram_drv.c:2699–2700`) — fix: replace bare `return` with `bio_endio(bio); return`.
3. **`algorithm_params_store` missing freeze guard** (`zram_drv.c:1699`) — fix: add `guard(rwsem_write)(&zram->dev_lock)` and `if (init_done(zram)) return -EBUSY` at the start of the function, matching the pattern in all peer handlers.

All three confirmed BUGs are covered by existing `@unittest.expectedFailure` regression tests in `quality/test_regression.py`. After applying the fixes, those tests should be promoted to regular passing tests by removing `@unittest.expectedFailure`.

