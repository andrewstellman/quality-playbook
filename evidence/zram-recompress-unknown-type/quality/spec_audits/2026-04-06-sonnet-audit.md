# Independent Spec Audit — zram (Tester Perspective)

**Auditor:** Claude Sonnet 4  
**Date:** 2026-04-06  
**Audit Type:** Independent (no prior review/audit outputs consulted)  
**Focus Areas:** init-order sysfs knobs, read_from_bdev_async allocation-failure, zram_bio_discard completion, writeback selector/rollback/accounting, recompress semantics, zsmalloc PAGE_SIZE ceiling, stats/docs alignment

---

## Defects

### DEFECT-001: read_from_bdev_async silent failure on allocation error

**File:** `drivers/block/zram/zram_drv.c`  
**Lines:** 1432-1461  
**Classification:** MISSING  
**Requirement Tag:** [Req: inferred — from read_from_bdev_async fallback path] NEEDS REVIEW

**Description:**  
When `read_from_bdev_async()` fails to allocate the `req` structure (line 1440) or the bio (line 1444), the function returns without:
1. Setting `parent->bi_status` to an error
2. Calling `bio_endio(parent)` or decrementing the parent's remaining count

The caller `read_from_bdev()` at line 1510 calls `read_from_bdev_async()` and returns 0 unconditionally, assuming success. This leaves the parent bio stranded—never completed—causing silent hangs for reads of written-back pages under memory pressure.

**Spec Reference:** REQ-015 states "every discard path... must complete the bio exactly once"; QUALITY.md Scenario 7 explicitly identifies this as a confirmed bug. The code does not propagate allocation failures to the caller or parent bio.

**Code Evidence:**
```c
// Lines 1439-1447
req = kmalloc_obj(*req, GFP_NOIO);
if (!req)
    return;  // <-- No error propagation

bio = bio_alloc(zram->bdev, 1, parent->bi_opf, GFP_NOIO);
if (!bio) {
    kfree(req);
    return;  // <-- No error propagation
}
```

---

### DEFECT-002: zram_bio_discard missing bio_endio on early return

**File:** `drivers/block/zram/zram_drv.c`  
**Lines:** 2698-2700  
**Classification:** MISSING  
**Requirement Tag:** [Req: inferred — from zram_bio_discard() physical-block handling] NEEDS REVIEW

**Description:**  
When a discard request fits entirely within an unaligned leading fragment, `zram_bio_discard()` returns early at line 2700 without calling `bio_endio()`. This strands the bio and violates the block-layer contract that every submitted bio must be completed exactly once.

**Spec Reference:** REQ-015 Condition 4: "Discard and write-zeroes always complete the bio exactly once, including no-op unaligned fragments." QUALITY.md Scenario 8 confirms this as a known bug.

**Code Evidence:**
```c
// Lines 2698-2700
if (offset) {
    if (n <= (PAGE_SIZE - offset))
        return;  // <-- Missing bio_endio(bio)
    ...
}
```

---

### DEFECT-003: io_stat hardcodes invalid_io column to 0

**File:** `drivers/block/zram/zram_drv.c`  
**Lines:** 1881-1885  
**Classification:** DIVERGENT  
**Requirement Tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§235-258]

**Description:**  
The `io_stat_show()` function emits a hardcoded `0` for the third column (invalid_io):
```c
ret = sysfs_emit(buf,
        "%8llu %8llu 0 %8llu\n",  // <-- hardcoded 0
        ...);
```

Documentation states io_stat's third column should report "The number of non-page-size-aligned I/O requests". The code never tracks or reports this counter—it's always zero. Either the stat should be removed from documentation or the counter should be implemented.

**Spec Reference:** Documentation/admin-guide/blockdev/zram.rst lines 245-246 describe `invalid_io` as a real statistic, but the implementation outputs a constant.

---

### DEFECT-004: writeback_store breaks out of parsing on legacy mode

**File:** `drivers/block/zram/zram_drv.c`  
**Lines:** 1284-1293  
**Classification:** DIVERGENT  
**Requirement Tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§377-392]

**Description:**  
When parsing legacy valueless mode parameters, `writeback_store()` calls `scan_slots_for_writeback()` and then `break`s out of the parsing loop (line 1292). This prevents processing of subsequent parameters like `page_indexes` that may follow in the same command.

Similarly, when `type=` is parsed (lines 1295-1303), it also breaks immediately. According to documentation, users can combine modes with page selectors:
```
echo page_index=42 page_index=99 page_indexes=100-200 ...
```

But the current code won't process `page_indexes` if `type=` appears before them.

**Spec Reference:** REQ-008 Condition 1-3 indicate multiple parameters should be parseable. Documentation examples show combined usage.

---

### DEFECT-005: scan_slots_for_writeback uses OR logic for mode filters instead of AND

**File:** `drivers/block/zram/zram_drv.c`  
**Lines:** 1216-1224  
**Classification:** DIVERGENT  
**Requirement Tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§362-370]

**Description:**  
The writeback slot scanning checks mode flags independently:
```c
if (mode & IDLE_WRITEBACK &&
    !test_slot_flag(zram, index, ZRAM_IDLE))
    goto next;
if (mode & HUGE_WRITEBACK &&
    !test_slot_flag(zram, index, ZRAM_HUGE))
    goto next;
```

For `huge_idle` mode (both IDLE and HUGE flags set), this logic requires slots to be BOTH idle AND huge—which matches documentation. However, for `mode=0` (PAGE_WRITEBACK), no mode checks are performed, so ALL allocated non-WB/non-SAME slots are selected. Documentation doesn't clearly specify this "select all" behavior for untyped page_index writeback.

**Spec Reference:** Documentation mentions `page_index=N` as selecting specific pages but doesn't clarify whether mode filtering applies. The implementation allows writing back any slot by index regardless of idle/huge state.

**Note:** This may be intentional behavior but is UNDOCUMENTED.

---

### DEFECT-006: recompress_slot marks incompressible only on prio_max boundary

**File:** `drivers/block/zram/zram_drv.c`  
**Lines:** 2479-2490  
**Classification:** DIVERGENT  
**Requirement Tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§527-534]

**Description:**  
The code marks a slot as ZRAM_INCOMPRESSIBLE only when:
```c
if (prio < zram->num_active_comps)
    return 0;
set_slot_flag(zram, index, ZRAM_INCOMPRESSIBLE);
```

This means if a user specifies `priority=2` (limiting to one algorithm), and that algorithm fails to improve the page, the slot is NOT marked incompressible—even though all requested algorithms were tried. The incompressible flag is only set when `prio >= num_active_comps`, i.e., all active compressors were exhausted.

Documentation states: "If none of the secondary algorithms can successfully re-compressed the page such a page is marked as incompressible." The implementation's behavior depends on whether the user limited algorithms via priority.

**Spec Reference:** Documentation/admin-guide/blockdev/zram.rst lines 532-534 suggest incompressible marking happens when "none of the secondary algorithms" succeed, not specifically "all configured algorithms."

---

### DEFECT-007: bd_stat reports 4K-scaled values inconsistently with PAGE_SIZE

**File:** `drivers/block/zram/zram_drv.c`  
**Lines:** 535-549  
**Classification:** UNDOCUMENTED  
**Requirement Tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§285-297]

**Description:**  
The `bd_stat_show()` uses `FOUR_K(x)` macro to convert page counts to 4K units:
```c
#define FOUR_K(x) ((x) * (1 << (PAGE_SHIFT - 12)))
```

On systems with PAGE_SIZE > 4KB (e.g., 16KB ARM64), this multiplies counts by 4. The documentation states units are "4K bytes" which is ambiguous—does it mean "4096-byte units" or "in 4K units relative to PAGE_SIZE"?

The writeback_limit_store (lines 624-637) explicitly documents the PAGE_SIZE alignment issue in comments but bd_stat doesn't document its scaling behavior.

**Spec Reference:** Documentation says bd_stat reports "4K bytes" units, but doesn't clarify behavior on large-PAGE_SIZE systems where one page = multiple 4K units.

---

### DEFECT-008: zstd_setup_params creates cdict/ddict even with no dictionary

**File:** `drivers/block/zram/backend_zstd.c`  
**Lines:** 51-90  
**Classification:** UNDOCUMENTED  
**Requirement Tag:** [Req: inferred — from backend_zstd.c dictionary handling] NEEDS REVIEW

**Description:**  
`zstd_setup_params()` unconditionally calls `zstd_create_cdict_byreference()` and `zstd_create_ddict_byreference()` even when `params->dict_sz == 0` and `params->dict == NULL`. While zstd may handle NULL/zero-size gracefully, the code path is inconsistent with `zstd_create()` which explicitly checks `params->dict_sz == 0` before deciding whether to use dictionary-based or workspace-based contexts.

The `zstd_create_cdict_byreference(NULL, 0, prm, custom_mem)` call may return NULL (triggering error path at line 77) or a degenerate cdict. This behavior is not documented.

**Spec Reference:** REQ-005 requires "Dictionary paths are loaded from the filesystem into backend parameter memory." The null-dictionary behavior in zstd backend is unclear.

---

### DEFECT-009: compressed_writeback not validated against backing_dev existence

**File:** `drivers/block/zram/zram_drv.c`  
**Lines:** 552-569  
**Classification:** UNDOCUMENTED  
**Requirement Tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§439-449]

**Description:**  
`compressed_writeback_store()` allows enabling compressed writeback before a backing device is configured. While this is technically pre-init state, the combination is meaningless—compressed writeback without a backing device serves no purpose.

The documentation states compressed_writeback "should be configured before the zramX device is initialized" but doesn't mention the backing_dev dependency. A user might enable compressed_writeback, then forget to set backing_dev, leading to confusion when writeback fails.

**Spec Reference:** Documentation doesn't clarify the ordering relationship between compressed_writeback and backing_dev configuration.

---

### DEFECT-010: scan_slots_for_recompress silently ignores mode=0

**File:** `drivers/block/zram/zram_drv.c`  
**Lines:** 2337-2375  
**Classification:** DIVERGENT  
**Requirement Tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§498-520]

**Description:**  
When `recompress_store()` is called without a `type=` parameter, `mode` remains 0. In `scan_slots_for_recompress()`, both IDLE and HUGE checks are skipped when their respective mode bits are not set:
```c
if (mode & RECOMPRESS_IDLE &&
    !test_slot_flag(zram, index, ZRAM_IDLE))
    goto next;
if (mode & RECOMPRESS_HUGE &&
    !test_slot_flag(zram, index, ZRAM_HUGE))
    goto next;
```

This means with `mode=0`, ALL non-WB, non-SAME, non-INCOMPRESSIBLE slots are candidates—regardless of idle/huge state. The documentation examples always show `type=` being specified, but the behavior when omitted is undocumented.

**Spec Reference:** Documentation doesn't specify default behavior when `type=` is omitted from recompress command.

---

### DEFECT-011: writeback rollback accounting races with concurrent limit changes

**File:** `drivers/block/zram/zram_drv.c`  
**Lines:** 902-916  
**Classification:** UNDOCUMENTED  
**Requirement Tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§398-437]

**Description:**  
`zram_account_writeback_rollback()` and `zram_account_writeback_submit()` assert `lockdep_assert_held_write(&zram->dev_lock)`, but `writeback_limit_store()` also takes the write lock. If an admin changes `bd_wb_limit` while writeback is in progress (between submit and complete), the rollback may restore an incorrect budget value.

The rollback adds `1UL << (PAGE_SHIFT - 12)` unconditionally, but if the limit was changed or disabled between submit and completion, accounting becomes inconsistent.

**Spec Reference:** REQ-007 Condition 4: "Rollback restores consumed budget when a backing bio fails." The interaction with concurrent limit changes is not specified.

---

## Summary

| ID | Classification | Severity | File:Line |
|----|---------------|----------|-----------|
| DEFECT-001 | MISSING | Critical | zram_drv.c:1432-1461 |
| DEFECT-002 | MISSING | Critical | zram_drv.c:2698-2700 |
| DEFECT-003 | DIVERGENT | Low | zram_drv.c:1881-1885 |
| DEFECT-004 | DIVERGENT | Medium | zram_drv.c:1284-1303 |
| DEFECT-005 | UNDOCUMENTED | Low | zram_drv.c:1216-1224 |
| DEFECT-006 | DIVERGENT | Medium | zram_drv.c:2479-2490 |
| DEFECT-007 | UNDOCUMENTED | Low | zram_drv.c:535-549 |
| DEFECT-008 | UNDOCUMENTED | Low | backend_zstd.c:51-90 |
| DEFECT-009 | UNDOCUMENTED | Low | zram_drv.c:552-569 |
| DEFECT-010 | DIVERGENT | Medium | zram_drv.c:2337-2375 |
| DEFECT-011 | UNDOCUMENTED | Low | zram_drv.c:902-916 |

**Critical defects (2):** DEFECT-001 and DEFECT-002 can cause hung I/O and system stalls.

**Defects by classification:**
- MISSING: 2
- DIVERGENT: 4  
- UNDOCUMENTED: 5

---

*Audit completed 2026-04-06*
