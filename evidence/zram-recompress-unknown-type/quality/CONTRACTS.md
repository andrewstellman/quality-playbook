# Behavioral Contract Extraction
Generated: 2026-04-06
Source files analyzed: 7
Total contracts extracted: 34

## Summary by category
- METHOD: 11
- CONFIG: 8
- ERROR: 4
- INVARIANT: 4
- LIFECYCLE: 4
- THREAD: 2
- COMPAT: 1

### drivers/block/zram/zram_drv.c (24 contracts)

1. [INVARIANT] `page_same_filled()` returns true only when every machine word in a page matches the first and exports that fill value.
2. [CONFIG] `mem_limit_store()` accepts size strings via `memparse()` and stores a page-aligned limit.
3. [CONFIG] `mem_used_max_store()` accepts only `0` and resets the max-used counter from the current pool state.
4. [METHOD] `mark_idle()` skips unallocated, written-back, and same-filled slots when applying the `ZRAM_IDLE` flag.
5. [CONFIG] `idle_store()` accepts `all` or, with access-time tracking enabled, an age in seconds; otherwise it rejects input.
6. [CONFIG] `compressed_writeback_store()` is only legal before initialization and toggles compressed-vs-raw backing writes.
7. [CONFIG] `writeback_limit_store()` rounds budgets down to a page-aligned 4K-unit value to prevent unsigned underflow.
8. [CONFIG] `writeback_batch_size_store()` rejects zero and updates the maximum number of in-flight writeback requests.
9. [CONFIG] `backing_dev_store()` accepts only non-zero-size block devices and must run before initialization.
10. [METHOD] `zram_reserve_bdev_block()` allocates one free backing-device slot and increments `bd_count`.
11. [METHOD] `zram_release_bdev_block()` clears a previously reserved bit and decrements `bd_count`, warning on mismatches.
12. [ERROR] `zram_writeback_complete()` rolls back writeback budget and releases the reserved backing block on bio failure.
13. [METHOD] `scan_slots_for_writeback()` excludes slots already written back, same-filled, or outside the requested mode filter.
14. [COMPAT] `writeback_store()` supports both legacy valueless modes and newer `key=value` syntax.
15. [METHOD] `decompress_bdev_page()` zeroes stale data and returns `-EIO` if the slot lost `ZRAM_WB` before deferred decompression.
16. [THREAD] `read_from_bdev_sync()` uses a worker queue to avoid recursive block-layer submission deadlocks.
17. [CONFIG] `__comp_algorithm_store()` accepts only supported algorithms and rejects post-init changes.
18. [CONFIG] `algorithm_params_store()` parses `priority`, `level`, `algo`, `dict`, and `deflate.winbits` selectors into per-priority parameter state.
19. [METHOD] `io_stat_show()` emits failed-read, failed-write, invalid-io, and notify-free columns in fixed order.
20. [LIFECYCLE] `zram_meta_alloc()` allocates the slot table and zsmalloc pool together, initializing per-slot locks.
21. [LIFECYCLE] `slot_free()` clears idle/incompressible/post-processing flags, releases backing or zsmalloc storage, and updates stats.
22. [METHOD] `read_from_zspool()` dispatches same-filled, compressed, and huge/incompressible slots to different read helpers.
23. [METHOD] `zram_write_page()` stores same-filled pages without allocation, incompressible pages via the huge path, and other pages compressed.
24. [METHOD] `recompress_slot()` only keeps a recompressed object when it improves class/threshold, clears idle state, and can mark the slot incompressible.
25. [METHOD] `zram_bio_discard()` frees only whole physical pages and skips leading/trailing partial logical fragments.
26. [METHOD] `zram_bio_read()` and `zram_bio_write()` advance bio iterators page-by-page, update failure counters, and mark slots accessed.
27. [METHOD] `zram_submit_bio()` handles reads, writes, discards, and write-zeroes, warning on unsupported bio ops.
28. [LIFECYCLE] `zram_reset_device()` frees metadata, clears stats, resets capacity, and restores the default primary compressor.
29. [CONFIG] `disksize_store()` is required to initialize the device, page-aligns the capacity, creates compression backends, and rejects changes after init.
30. [LIFECYCLE] `reset_store()` rejects inactive values, blocks resets while open/claimed, drains I/O, and then tears down state.
31. [THREAD] `zram_open()` refuses new opens while a reset/remove claim is active.
32. [LIFECYCLE] `zram_add()` creates zero-capacity devices with the default compressor and deferred debugfs/sysfs exposure.
33. [LIFECYCLE] `zram_remove()` blocks removal while open, drains I/O, tears down state, and performs a final reset to avoid leaks.
34. [METHOD] `hot_add_show()` mutates system state by creating a device on read; `hot_remove_store()` removes devices by id.

### drivers/block/zram/zcomp.c (6 contracts)

1. [CONFIG] `lookup_backend_ops()` exposes only compiled-in compressors.
2. [METHOD] `zcomp_available_show()` renders the active backend in brackets and other supported backends as plain names.
3. [THREAD] `zcomp_stream_get()` retries if CPU migration races with stream teardown and returns a locked per-CPU stream.
4. [METHOD] `zcomp_compress()` always compresses from one page into a two-page scratch buffer.
5. [METHOD] `zcomp_decompress()` always expands into one page.
6. [LIFECYCLE] `zcomp_create()` allocates per-CPU streams, sets up backend params, and fails atomically if setup or CPU-hotplug registration fails.

### drivers/block/zram/backend_zstd.c (2 contracts)

1. [CONFIG] `zstd_setup_params()` installs a default compression level when none is provided and builds dictionary state by reference.
2. [ERROR] `zstd_create()` falls back between dictionary and workspace modes and converts backend setup failure into `-EINVAL`.

### drivers/block/zram/backend_lzo.c (2 contracts)

1. [METHOD] `lzo_create()` allocates the backend scratch context and fails with `-ENOMEM` on allocation failure.
2. [ERROR] `lzo_compress()` / `lzo_decompress()` translate library status codes into backend return values without swallowing failures.

## Spec and config sources (behavioral contracts outside code)

1. [CONFIG] `Documentation/admin-guide/blockdev/zram.rst`: `comp_algorithm`, `backing_dev`, and `compressed_writeback` are pre-init controls.
2. [CONFIG] `Documentation/admin-guide/blockdev/zram.rst`: `disksize` must be set before use and reset returns the device to size zero.
3. [METHOD] `Documentation/admin-guide/blockdev/zram.rst`: writeback supports `idle`, `huge`, `huge_idle`, `incompressible`, `page_index`, and `page_indexes`.
4. [METHOD] `Documentation/admin-guide/blockdev/zram.rst`: recompression supports `type`, `threshold`, `max_pages`, `algo`, and `priority`.
5. [INVARIANT] `docs_gathered/zsmalloc-design.md`: zsmalloc allocations larger than `PAGE_SIZE` are invalid; zram must special-case incompressible pages.
6. [LIFECYCLE] `docs_gathered/zram-community-development-history.md`: created devices start at zero memory usage and must be re-sized after reset before reuse.
