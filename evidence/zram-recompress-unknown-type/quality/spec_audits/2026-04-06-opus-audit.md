# Spec Audit — zram 1.3.7 (Tester Role)

**Date:** 2026-04-06
**Auditor:** Independent Tester (Claude Opus)
**Scope:** Code-against-spec comparison for `zram_drv.c`, `zcomp.c`, `backend_zstd.c`, `backend_lzo.c`
**Specs used:** `quality/QUALITY.md`, `quality/REQUIREMENTS.md`, `Documentation/admin-guide/blockdev/zram.rst`, `docs_gathered/zram-community-development-history.md`, `docs_gathered/zsmalloc-design.md`

---

## D01 — `read_from_bdev_async` silently drops allocation failures

| Field | Value |
|---|---|
| **File** | `drivers/block/zram/zram_drv.c` |
| **Lines** | 1439–1447 (failure returns), 1510–1511 (caller always returns 0) |
| **Classification** | DIVERGENT |
| **Requirement** | [Req: inferred — from read_from_bdev_async() fallback path] NEEDS REVIEW |
| **Traced to** | REQ-014 condition 4; QUALITY.md Scenario 7 |

**Evidence:** When `kmalloc_obj()` (line 1440) or `bio_alloc()` (line 1444) fails, `read_from_bdev_async()` returns without setting `parent->bi_status` or calling `bio_endio(parent)`. The caller `read_from_bdev()` unconditionally returns `0` at line 1511 on the async path. Consequently `zram_bio_read()` at line 2731 sees a non-negative return and delivers stale/uninitialized page data to the block-layer consumer, then completes the parent bio at line 2746 with success status.

**Impact:** Silent data corruption on the read path under memory pressure — exactly the condition where zram is supposed to be most critical.

---

## D02 — `zram_bio_discard` omits `bio_endio` on unaligned-only fragment

| Field | Value |
|---|---|
| **File** | `drivers/block/zram/zram_drv.c` |
| **Lines** | 2698–2700 |
| **Classification** | DIVERGENT |
| **Requirement** | [Req: inferred — from zram_bio_discard() physical-block handling] NEEDS REVIEW |
| **Traced to** | REQ-015 condition 4; QUALITY.md Scenario 8 |

**Evidence:** When `offset != 0` and the entire discard request fits inside the leading unaligned fragment (`n <= (PAGE_SIZE - offset)`), the function returns at line 2700 without calling `bio_endio(bio)`. Every other exit from the three bio handlers (`zram_bio_read`, `zram_bio_write`, `zram_bio_discard`) calls `bio_endio`. This path strands the bio — a no-op discard that the block layer will never see completed.

**Impact:** Hung bio on any sub-page discard request that doesn't cross a physical page boundary.

---

## D03 — `io_stat` third column (`invalid_io`) hardcoded to zero

| Field | Value |
|---|---|
| **File** | `drivers/block/zram/zram_drv.c:1882` vs `Documentation/admin-guide/blockdev/zram.rst:242–246` |
| **Lines** | 1882 (format string literal `0`) |
| **Classification** | DIVERGENT |
| **Requirement** | [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§240–258] |
| **Traced to** | REQ-016 condition 1 |

**Evidence:** The `io_stat_show()` format string is `"%8llu %8llu 0 %8llu\n"`. The third column is the literal character `0`, not a counter read. The documentation describes it as `invalid_io` — "The number of non-page-size-aligned I/O requests." No `invalid_io` field exists in the stats struct and no code path increments such a counter. The counter was historically relevant before partial-I/O support was added; now it is dead but still documented.

**Impact:** Misleading stat output. Operators relying on `invalid_io` for diagnostics will always see zero regardless of actual I/O patterns.

---

## D04 — `recompress_store` does not validate unrecognized `type=` values

| Field | Value |
|---|---|
| **File** | `drivers/block/zram/zram_drv.c` |
| **Lines** | 2550–2557 |
| **Classification** | MISSING |
| **Requirement** | [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§500–510] |
| **Traced to** | REQ-010 (eligibility-driven selection) |

**Evidence:** The `type=` parameter block at lines 2550–2557 checks for `"idle"`, `"huge"`, and `"huge_idle"` with independent `if` statements but falls through with `continue` if none matches. The `mode` variable remains `0`, causing `scan_slots_for_recompress()` to skip all mode filters and select ALL eligible slots. Compare with writeback's `parse_mode()` (lines 1181–1197) which returns `-EINVAL` for unrecognized values.

**Impact:** `echo "type=typo" > recompress` silently recompresses every eligible page instead of returning an error. An operator misspelling the mode gets a full-device recompression pass without warning.

---

## D05 — `recompress_slot` does not clear `ZRAM_IDLE` when `read_from_zspool` fails

| Field | Value |
|---|---|
| **File** | `drivers/block/zram/zram_drv.c` |
| **Lines** | 2409–2418 |
| **Classification** | DIVERGENT |
| **Requirement** | [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§462–547] |
| **Traced to** | REQ-011 condition 1 |

**Evidence:** `read_from_zspool()` is called at line 2409. If it fails (decompression error), the function returns at line 2411 before reaching the `clear_slot_flag(zram, index, ZRAM_IDLE)` at line 2418. The code comment at lines 2413–2417 explicitly states the intent: "We touched this entry so mark it as non-IDLE … so that we don't incorrectly pick this entry for different post-processing type (e.g. writeback)." The requirement states: "Any recompression attempt clears ZRAM_IDLE before exit." The failed-read early return violates this contract.

**Impact:** A slot that fails recompression due to a read error retains ZRAM_IDLE, making it eligible for writeback targeting, where it would also fail to read.

---

## D06 — `zstd_create` error path releases shared per-compressor params

| Field | Value |
|---|---|
| **File** | `drivers/block/zram/backend_zstd.c` |
| **Lines** | 163–164 |
| **Classification** | DIVERGENT |
| **Requirement** | [Req: inferred — from zcomp.c backend and stream management] NEEDS REVIEW |
| **Traced to** | REQ-017 (backend lifecycle / hotplug safety) |

**Evidence:** `zstd_create()` is the per-CPU `create_ctx` callback. On error (line 163), it calls `zstd_release_params(params)`, which frees the shared `cdict`, `ddict`, and `zstd_params` struct, then sets `params->drv_data = NULL`. These params are owned by `zcomp_init()`, which also calls `release_params()` in its own cleanup path (zcomp.c:215). The double release is tolerated only because the first call nulls the pointer, but the ownership contract between `zcomp.c` and backend `create_ctx` is violated: per-CPU stream creation should never destroy shared compressor-wide state. No other backend (`backend_lzo.c`, `backend_lzorle.c`, etc.) exhibits this pattern.

**Impact:** Fragile code: any future change that allows concurrent CPU onlining or early compressor use during setup would expose use-after-free of cdict/ddict. Currently safe only because `cpuhp_state_add_instance` serializes and no I/O is in flight during init.

---

## D07 — `writeback_limit` documented as WO but is RW in code and usage text

| Field | Value |
|---|---|
| **File** | `Documentation/admin-guide/blockdev/zram.rst:214` vs `zram_drv.c:2996` |
| **Lines** | rst:214 (table says WO), rst:426–428 (shows `cat`), zram_drv.c:2996 (`DEVICE_ATTR_RW`) |
| **Classification** | DIVERGENT |
| **Requirement** | [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§205–226] |
| **Traced to** | REQ-016 (stats/docs alignment) |

**Evidence:** The sysfs attribute summary table at rst line 214 lists `writeback_limit` as `WO`. However, `zram_drv.c:2996` declares it as `DEVICE_ATTR_RW(writeback_limit)`, and the code provides both `writeback_limit_store()` (line 614) and `writeback_limit_show()` (line 640). Furthermore, the documentation itself at lines 426–428 instructs administrators to read the attribute: "If an admin wants to see the remaining writeback budget since last set: `$ cat /sys/block/zramX/writeback_limit`."

**Impact:** Documentation self-contradiction. The table and the prose disagree on whether the attribute is readable. Operators who trust the table may not realize they can query remaining budget; tooling generators will produce wrong permission expectations.

---

## Areas Examined Without Defects Found

| Area | Verdict |
|---|---|
| Init-order freeze of `disksize`, `comp_algorithm`, `backing_dev`, `compressed_writeback` | Correctly gated by `init_done()` |
| Writeback slot selection (`scan_slots_for_writeback`) for WB/SAME exclusion | Lines 1212–1214 correctly skip |
| Writeback rollback budget accounting (`zram_account_writeback_rollback`) | Correctly restores `bd_wb_limit` on bio failure |
| `bd_count` tracking via `zram_reserve_bdev_block` / `zram_release_bdev_block` | Correctly incremented/decremented at reserve/release |
| Incompressible page ceiling (`write_incompressible_page` allocates exactly PAGE_SIZE) | Matches zsmalloc max object size contract |
| `huge_class_size` threshold set from `zs_huge_class_size()` | Correctly initialized at first `zram_meta_alloc()` |
| Same-filled page detection, storage, and readback | `page_same_filled()` checks full page; write/read paths coherent |
| Writeback completion ZRAM_HUGE counter bookkeeping | Decrements before WB conversion; `slot_free` guards double-decrement |
| Reset/remove quiescing (`reset_store`, `zram_remove`) | Claims, syncs, resets, and double-resets after `del_gendisk` |
| `mm_stat` and `bd_stat` column alignment with docs | All columns match documented order and units |
| Debugfs block-state flag encoding (`s`, `w`, `h`, `i`, `r`, `n`) | Matches documented letters |
| `zcomp.c` per-CPU stream lifecycle and hotplug callbacks | Stream get/put handles migration race correctly |
| `backend_lzo.c` simplicity | No ownership or validation issues |
