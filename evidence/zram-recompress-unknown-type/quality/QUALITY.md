# Quality Constitution: zram (Linux kernel compressed RAM block device)

## Purpose

Quality for this repo means preserving zram's contract as a RAM-backed block device that is **safe under memory pressure, strict about lifecycle ordering, and predictable at the sysfs boundary**. Per Deming, that bar has to be built into review prompts, requirements, and executable checks before edits land; a green compile alone is not enough for code that can silently lose pages, stall discard I/O, or corrupt the backing-device workflow.

Per Juran, fitness for use here means: a caller can provision `/dev/zramX`, select compression behavior, serve block I/O, and reset or remove the device **without silent data loss, hanging bios, or post-init configuration drift**. Per Crosby, spending effort on explicit contracts is cheaper than debugging low-memory writeback and recompression failures after the driver is deployed into swap-heavy systems.

## Coverage Targets

| Subsystem | Target | Why |
|-----------|--------|-----|
| `drivers/block/zram/zram_drv.c` | 95% | This file owns lifecycle, sysfs writes, block I/O, writeback, and recompression; subtle control-flow gaps can hang bios or free storage out from under active requests. |
| `drivers/block/zram/zcomp.c` | 90% | Per-CPU stream allocation and CPU hotplug safety protect the core compression path from concurrency and allocation failures. |
| Compression backends (`backend_*.c`) | 85% | Backend parameter/setup mistakes silently degrade compression or make dictionary-based configs unusable. |
| Admin/docs contract (`Documentation/admin-guide/blockdev/zram.rst`) | 85% spec trace | zram is configured through sysfs; docs are effectively the user-facing spec and must stay aligned with behavior. |
| Config surface (`drivers/block/zram/Kconfig`, `Makefile`) | 75% | Build-time feature gates control which sysfs knobs and state flags exist; lower logic density, but wrong assumptions here invalidate tests and protocols. |

## Coverage Theater Prevention

- Counting generated sysfs attribute names without checking the guarding logic in the corresponding `*_store()` or `*_show()` function.
- Asserting that docs mention `writeback` or `recompress` without verifying the driver actually enforces the documented ordering and error semantics.
- Treating `io_stat` or `mm_stat` formatting as coverage while never checking the counters and flags that feed those reports.
- Writing tests that only grep for helper names like `zram_write_page()` or `slot_free()` instead of checking the exact branches that protect same-filled, huge, idle, and writeback slots.
- Claiming block-I/O coverage after exercising aligned happy paths only; zram's fragile cases are partial I/O, writeback fallback, and state transitions during reset/remove.

## Fitness-to-Purpose Scenarios

### Scenario 1: Post-init knobs stay frozen

**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§2-4,10]

**What happened:** zram's sysfs control plane lets administrators pick compressors, backing devices, and writeback mode before the device is initialized. Once `disksize_store()` allocates metadata and compression streams, late changes can invalidate live state or make the device's stats and persistence assumptions lie. The code explicitly freezes `disksize` and `comp_algorithm` after init (`zram_drv.c:1653-1658`, `2872-2919`), and `compressed_writeback`/`backing_dev` are only safe before first use (`552-569`, `723-792`).

**The requirement:** configuration knobs that shape on-disk or in-memory layout must reject post-init mutation with a clear error path.

**How to verify:** `python3 -m unittest quality.test_functional.TestSpecRequirements.test_post_init_configuration_guards`

---

### Scenario 2: Incompressible pages never exceed zsmalloc's ceiling

**Requirement tag:** [Req: formal — docs_gathered/zsmalloc-design.md §§18-29]

**What happened:** zsmalloc cannot store objects larger than `PAGE_SIZE`. If zram tried to persist a page whose compressed form grew beyond the huge-class threshold, it would request an impossible allocation and fail under the exact low-memory conditions where zram is supposed to help. `zram_write_page()` routes `comp_len >= huge_class_size` into `write_incompressible_page()` (`2241-2272`), and that path stores a raw `PAGE_SIZE` object with `ZRAM_HUGE` bookkeeping (`2200-2238`).

**The requirement:** pages that do not compress below the huge threshold must be stored uncompressed, with stats and flags updated to preserve correct readback.

**How to verify:** `python3 -m unittest quality.test_functional.TestSpecRequirements.test_incompressible_pages_use_huge_path`

---

### Scenario 3: Same-filled pages stay metadata-only

**Requirement tag:** [Req: inferred — from page_same_filled()/write_same_filled_page()]

**What happened:** zero- and same-filled pages are common in swap/tmp workloads. If zram allocated zsmalloc objects for these pages, it would waste memory and distort `same_pages` accounting. `page_same_filled()` identifies the pattern (`340-360`), and `write_same_filled_page()` records the fill value in the slot handle without allocating pool memory (`2185-2198`).

**The requirement:** same-filled pages must bypass normal compression allocation and round-trip through the synthetic read path.

**How to verify:** `python3 -m unittest quality.test_functional.TestFitnessScenarios.test_same_filled_pages_use_marker_storage`

---

### Scenario 4: Writeback only touches eligible slots

**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§322-459]

**What happened:** writeback is post-processing over live compressed slots. If it grabs `ZRAM_WB`, `ZRAM_SAME`, or non-matching slots, it can double-write backing storage, lose dedupe state, or violate the admin's selected `idle`/`huge`/`incompressible` mode. `scan_slots_for_writeback()` enforces those filters (`1199-1235`), and `zram_writeback_complete()` swaps ownership only if `ZRAM_PP_SLOT` is still present (`918-959`).

**The requirement:** writeback selection must be mode-filtered, race-aware, and rollback accounted when the backing bio fails.

**How to verify:** `python3 -m unittest quality.test_functional.TestFitnessScenarios.test_writeback_filters_and_rollbacks`

---

### Scenario 5: Recompression must not recycle stale idle state

**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§462-547]

**What happened:** recompression re-reads a live slot, tries secondary compressors, and may leave the page in memory if no better class is found. If zram preserved the old `ZRAM_IDLE` mark after touching the page, a later writeback run could immediately evict freshly examined data. `recompress_slot()` explicitly clears `ZRAM_IDLE` before trying alternative compressors (`2413-2419`) and marks the slot `ZRAM_INCOMPRESSIBLE` only after exhausting configured secondaries (`2479-2490`).

**The requirement:** recompression must clear stale idle state and accurately distinguish "no better algorithm" from "not yet tried."

**How to verify:** `python3 -m unittest quality.test_functional.TestFitnessScenarios.test_recompression_clears_idle_and_marks_incompressible`

---

### Scenario 6: Reset/remove quiesce openers before freeing metadata

**Requirement tag:** [Req: formal — docs_gathered/zram-community-development-history.md §§151-159]

**What happened:** reset and device removal free the zsmalloc pool, compression backends, and backing-device bitmap. If new opens or in-flight I/O slip through while teardown is running, a later read/write can dereference freed metadata. `reset_store()` and `zram_remove()` claim the disk under `open_mutex`, wait for `sync_blockdev()`, and only then call `zram_reset_device()` (`2922-2959`, `3124-3169`).

**The requirement:** lifecycle teardown must block new opens, drain pending I/O, and leave the device in a clean zero-capacity state before reopening.

**How to verify:** `python3 -m unittest quality.test_functional.TestFitnessScenarios.test_reset_and_remove_claim_before_freeing_state`

---

### Scenario 7: Async backing-device reads must fail loudly when setup allocation fails

**Requirement tag:** [Req: inferred — from read_from_bdev_async() fallback path]

**What happened:** a read served from the backing device can require allocating a request object and child bio. In low-memory situations, `read_from_bdev_async()` may fail both allocations (`1436-1447`). Today that function simply returns without setting `parent->bi_status` or completing the parent bio, which permits silent hangs or stale data if the caller assumes the child read was queued.

**The requirement:** async read setup failures must propagate an I/O error to the parent bio instead of silently returning.

**How to verify:** `python3 -m unittest quality.test_regression.TestConfirmedBugs.test_async_backing_read_setup_failure_is_reported`

---

### Scenario 8: Unaligned discard must still complete the bio

**Requirement tag:** [Req: inferred — from zram_bio_discard() physical-block handling]

**What happened:** zram intentionally skips sub-page discard fragments because freeing a partial physical page would cost memory rather than save it. But if the request fits entirely inside the skipped leading fragment, `zram_bio_discard()` returns early (`2698-2700`) before calling `bio_endio()`. On a live block device this would strand the request even though the correct behavior is "do nothing, but finish successfully."

**The requirement:** every discard path, including no-op unaligned fragments, must complete the bio exactly once.

**How to verify:** `python3 -m unittest quality.test_regression.TestConfirmedBugs.test_unaligned_single_fragment_discard_completes_bio`

## AI Session Quality Discipline

1. Read `quality/QUALITY.md` and `quality/REQUIREMENTS.md` before editing `drivers/block/zram/`.
2. Treat `Documentation/admin-guide/blockdev/zram.rst` as a contract, not commentary.
3. When touching sysfs handlers, verify pre-init vs post-init behavior explicitly.
4. For any change in slot flags or backing-device flow, trace read, write, reset, and stats consequences together.
5. Never claim zram behavior from docs alone; confirm the exact branch in `zram_drv.c`.
6. If new state flags or sysfs knobs are added, add a requirement, a scenario, and at least one executable check.

## The Human Gate

- Performance tradeoffs between compression ratio, latency, and flash wear.
- Whether undocumented behavior should become a supported contract or be tightened.
- Threshold tuning for writeback budgets, recompression modes, and batch sizes on real hardware.
- Review of changes that affect swap semantics, debugfs exposure, or user-visible kernel documentation.
