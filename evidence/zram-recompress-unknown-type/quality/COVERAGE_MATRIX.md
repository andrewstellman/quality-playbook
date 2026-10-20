# Contract Coverage Matrix
Generated: 2026-04-06
Total contracts: 34
Covered: 34 (100%)
Uncovered: 0 (0%)
Partially covered: 0 (0%)

## Fully covered contracts
- `zram_drv.c` same-filled detection/storage/readback → REQ-012
- `zram_drv.c` mem-limit parsing and alignment → REQ-003
- `zram_drv.c` mem-used-max zero-only reset → REQ-003
- `zram_drv.c` idle marking skips `WB`/`SAME` and uses access time → REQ-011
- `zram_drv.c` `idle_store()` input rules → REQ-010, REQ-011
- `zram_drv.c` compressed-writeback pre-init guard → REQ-007
- `zram_drv.c` writeback-limit alignment → REQ-007
- `zram_drv.c` writeback batch-size nonzero validation → REQ-007
- `zram_drv.c` backing-device validation/order → REQ-006
- `zram_drv.c` reserve/release backing blocks and `bd_count` → REQ-009
- `zram_drv.c` writeback rollback on failed bio → REQ-007, REQ-009
- `zram_drv.c` writeback eligibility scan → REQ-009
- `zram_drv.c` legacy and key=value writeback parsing → REQ-008
- `zram_drv.c` stale-`WB` deferred decompression safety → REQ-014
- `zram_drv.c` worker-based sync backing read → REQ-014, REQ-017
- `zram_drv.c` primary compressor validation/freeze → REQ-004
- `zram_drv.c` algorithm parameter parsing, mapping, and intended pre-init freeze → REQ-005
- `zram_drv.c` `io_stat` field order → REQ-016
- `zram_drv.c` metadata allocation and per-slot lock init → REQ-002
- `zram_drv.c` `slot_free()` state cleanup → REQ-009, REQ-013, REQ-018
- `zram_drv.c` slot-representation read dispatch → REQ-014
- `zram_drv.c` write-path routing across same/huge/compressed states → REQ-012, REQ-013
- `zram_drv.c` recompression progress/threshold logic and selector validation intent → REQ-010, REQ-011
- `zram_drv.c` discard whole-page-only behavior → REQ-015
- `zram_drv.c` read/write bio loop, counters, access marks → REQ-014, REQ-015
- `zram_drv.c` submit-bio op dispatch → REQ-015
- `zram_drv.c` slot-free notify and miss-free accounting → REQ-016
- `zram_drv.c` reset clears capacity/state/default compressor → REQ-002, REQ-018
- `zram_drv.c` `disksize_store()` init gate and backend creation → REQ-002
- `zram_drv.c` reset claim/open synchronization → REQ-018
- `zram_drv.c` open refusal while claimed → REQ-018
- `zram_drv.c` add/remove/hot_add/hot_remove lifecycle → REQ-001, REQ-018
- `zcomp.c` backend advertisement and per-CPU stream safety → REQ-004, REQ-017
- `backend_zstd.c` parameter setup and error propagation → REQ-005
- `backend_lzo.c` context allocation and backend error propagation → REQ-017
- `Documentation/admin-guide/blockdev/zram.rst` pre-init ordering and reset contract → REQ-002, REQ-004, REQ-006, REQ-007
- `Documentation/admin-guide/blockdev/zram.rst` writeback/recompression syntax → REQ-008, REQ-010, REQ-011
- `docs_gathered/zsmalloc-design.md` PAGE_SIZE ceiling for allocations → REQ-013
- `docs_gathered/zram-community-development-history.md` lifecycle/reset expectations → REQ-001, REQ-002, REQ-018

## Partially covered contracts
None.

## Uncovered contracts
None.

## Coverage notes

- The repo snapshot contains no in-tree zram-specific selftests or KUnit cases, so executable traceability is provided by `quality/test_functional.py` and `quality/test_regression.py`, which validate the source snapshot against these contracts.
- Two doc claims were intentionally treated as documentation-validation concerns rather than functional requirements: the `-EAGAIN` concurrency note and the `invalid_io` counter wording. They are reviewed in the spec-audit artifacts, not promoted as authoritative behavior requirements.
