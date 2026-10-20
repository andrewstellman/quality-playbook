# Behavioral Requirements — zram
Version: v1.0
Generated: 2026-04-06
Pipeline: contract-extraction v2 with narrative pass

## Project Overview

zram is a Linux kernel block driver that presents compressed RAM as `/dev/zramX` devices. Users configure it through sysfs, optionally pair it with a backing block device for writeback, and then hand it to swap, filesystems, or other block consumers. The core value proposition is straightforward: trade CPU time for memory efficiency without depending on a conventional swap disk. In practice, that means the driver has to be strict about lifecycle ordering, conservative under low-memory conditions, and safe when pages move between in-memory compressed storage and an optional backing device.

The subsystem is centered on `drivers/block/zram/zram_drv.c`, which owns the block-device surface, sysfs control plane, slot table, writeback engine, and recompression logic. Compression backends are abstracted through `zcomp.c` and the backend implementations (`backend_lzo.c`, `backend_zstd.c`, and peers). The slot table tracks per-page flags such as `ZRAM_SAME`, `ZRAM_HUGE`, `ZRAM_WB`, `ZRAM_IDLE`, and `ZRAM_INCOMPRESSIBLE`, and those flags govern which read/write path a page takes. The design is tightly coupled to zsmalloc's constraints: compressed objects live in a zsmalloc pool, same-filled pages avoid allocation entirely, and incompressible pages must never exceed `PAGE_SIZE`.

Administrators interact with zram almost entirely through sysfs. They select compression algorithms, dictionaries, disk size, writeback limits, and recompression modes by writing to device attributes before or during different lifecycle stages. That makes sysfs handlers part of the functional contract, not just convenience wrappers. Documentation in `Documentation/admin-guide/blockdev/zram.rst` is therefore authoritative for many behaviors, especially configuration ordering and control-surface semantics.

The biggest quality risks are not "obvious crashes" but **quiet contract drift**: a knob becoming mutable after init, a bio path returning without completion, a post-processing scan touching the wrong slot class, or a failure path that silently drops a backing-device operation. The requirements below are written to make those failure modes explicit and reviewable.

## Use Cases

### Use Case 1: Provision a new zram device
- **Actor:** System administrator
- **Preconditions:** zram module is loaded; a `/sys/block/zramX/` directory exists or can be created via `hot_add`.
- **Steps:**
  1. Admin creates or selects a zram device.
  2. Admin optionally selects the primary compressor and algorithm parameters.
  3. Admin writes a positive `disksize`.
  4. Kernel allocates metadata and compression backends.
- **Postconditions:** the device is initialized with a non-zero capacity and ready for swap/filesystem activation.
- **Alternative paths:** unsupported compressor; invalid size; metadata allocation failure; post-init attempts to change frozen knobs.
- **Requirements:** REQ-001, REQ-002, REQ-003, REQ-004

### Use Case 2: Tune compression behavior
- **Actor:** System administrator
- **Preconditions:** device exists; desired compressors are built in.
- **Steps:**
  1. Admin reads supported compressors.
  2. Admin selects primary and optional secondary compressors.
  3. Admin supplies optional dictionary, level, or backend-specific parameters.
- **Postconditions:** future writes use the selected backend set and parameter state.
- **Alternative paths:** unknown compressor; invalid priority; unsupported dictionary path; attempts to mutate frozen state after init.
- **Requirements:** REQ-003, REQ-004, REQ-005, REQ-011

### Use Case 3: Attach and use a backing device
- **Actor:** System administrator
- **Preconditions:** `CONFIG_ZRAM_WRITEBACK` is enabled; a block device is available.
- **Steps:**
  1. Admin writes `backing_dev`.
  2. Admin optionally enables `compressed_writeback`, sets batch size, and configures writeback limits.
  3. Admin triggers writeback by mode or page range.
- **Postconditions:** eligible slots migrate to the backing device and accounting reflects the result.
- **Alternative paths:** non-block or zero-sized backing device; exhausted writeback budget; failed backing bio; invalid selector syntax.
- **Requirements:** REQ-006, REQ-007, REQ-008, REQ-009

### Use Case 4: Recompress cold or huge pages
- **Actor:** System administrator
- **Preconditions:** `CONFIG_ZRAM_MULTI_COMP` is enabled; at least one secondary compressor is configured.
- **Steps:**
  1. Admin writes a recompression mode and optional limits.
  2. Kernel scans eligible slots.
  3. Kernel retries secondary compressors in priority order.
- **Postconditions:** pages that improve class/threshold are rewritten with higher-priority compressors; others keep their old representation or become marked incompressible.
- **Alternative paths:** invalid threshold; no eligible secondary compressor; page already small enough; page touched concurrently.
- **Requirements:** REQ-010, REQ-011, REQ-012

### Use Case 5: Serve block I/O
- **Actor:** Block layer / swap subsystem / filesystem
- **Preconditions:** device is initialized and open.
- **Steps:**
  1. Kernel receives read, write, discard, or write-zeroes bio.
  2. zram resolves the slot representation (same-filled, compressed, huge, or written-back).
  3. zram reads, writes, or frees slot state and updates stats/access markers.
- **Postconditions:** bio completes exactly once and the slot table remains internally consistent.
- **Alternative paths:** partial I/O; compression failure; backing-device read path; unaligned discard; slot changed during deferred decompression.
- **Requirements:** REQ-009, REQ-010, REQ-012, REQ-013, REQ-014, REQ-015

### Use Case 6: Reset or remove a zram device
- **Actor:** System administrator / module teardown
- **Preconditions:** device exists.
- **Steps:**
  1. Admin writes `reset` or removes the device via `hot_remove`/module exit.
  2. Kernel blocks new opens, drains pending I/O, and tears down metadata/backends.
  3. Device returns to zero-capacity or disappears.
- **Postconditions:** no live metadata, open path, or backing-device state survives teardown.
- **Alternative paths:** device still open; removal during reset; leaked allocations after partial init.
- **Requirements:** REQ-001, REQ-014, REQ-016, REQ-017, REQ-018

## Cross-Cutting Concerns

**Lifecycle ordering.** zram is intentionally strict about pre-init versus post-init operations. Configuration that changes storage layout or compressor identity must happen before `disksize` initializes metadata, while runtime knobs like `mem_limit` and post-processing triggers remain available later. REQ-002 through REQ-008 and REQ-016 capture that split.

**Flag-driven state.** Slot flags are the driver's state machine. Read, writeback, recompression, stats, and debugfs all interpret the same flags, so requirements must verify not just one path but the transitions between `SAME`, `HUGE`, `WB`, `IDLE`, `INCOMPRESSIBLE`, and post-processing ownership. REQ-009 through REQ-015 encode those invariants.

**Failure signaling over silent fallback.** Because zram runs in degraded-memory environments, allocation or I/O failures are expected. The quality bar is not "never fail" but "fail explicitly, keep counters coherent, and never strand a bio or corrupt slot ownership." REQ-008, REQ-013, REQ-015, and REQ-018 cover that philosophy.

## Device lifecycle and control-plane requirements

These requirements cover device creation, initialization, configuration freeze points, and teardown. Reviewers should read them against the sysfs handlers and the add/remove paths in `zram_drv.c`; most real regressions in this area come from adding a new knob without deciding whether it is pre-init-only or runtime mutable.

### REQ-001: Device creation exposes a zero-capacity control surface
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §1, §7]

**Summary:** Newly created zram devices must exist in an uninitialized, zero-capacity state until an administrator explicitly writes `disksize`.

**User story:** As an administrator provisioning swap or tmp storage, I expect a fresh `/dev/zramX` to start empty so that configuration happens before any storage layout is committed, **so that** I can safely pick compressors and backing options first.

**Implementation note:** `zram_add()` allocates the gendisk, sets capacity to zero, installs default compression state, and publishes sysfs/debugfs without allocating metadata pages.

**Conditions of satisfaction:**
1. A newly added device reports `initstate == 0`.
2. A newly added device has capacity zero until `disksize_store()` succeeds.
3. `hot_add` returns the created device id and `hot_remove` removes by id.

**Alternative paths:** module parameter `num_devices`; dynamic `hot_add`; cleanup after partial add failure.

**References:** `drivers/block/zram/zram_drv.c:3042-3113`, `3180-3225`; `Documentation/admin-guide/blockdev/zram.rst:64-75,177-196`

**Specificity:** specific

### REQ-002: Disksize is the initialization gate and freezes layout-sensitive knobs
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§76-145,307-317]

**Summary:** Writing a positive `disksize` must initialize metadata and compression backends exactly once per lifecycle; subsequent attempts before reset must fail with a busy error.

**User story:** As an administrator bringing a device online, I expect `disksize` to be the one-way step that commits storage state, **so that** later writes cannot silently invalidate live pages.

**Implementation note:** `disksize_store()` page-aligns the requested size, allocates metadata, creates all configured backends, and returns `-EBUSY` when `init_done(zram)` is already true.

**Conditions of satisfaction:**
1. Zero or unparsable disk sizes are rejected.
2. Successful initialization allocates the slot table and every configured compressor.
3. A second `disksize` write after initialization returns busy without mutating state.
4. Reset returns the device to `disksize == 0`, requiring a new `disksize` write before reuse.

**Alternative paths:** metadata allocation failure; backend creation failure after partial progress; teardown during remove.

**References:** `drivers/block/zram/zram_drv.c:1958-1981,2872-2919,2922-2959`; `docs_gathered/zram-community-development-history.md:153-160`

**Specificity:** specific

### REQ-003: Runtime memory limits and statistics-reset input are narrow and explicit
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§147-165]

**Summary:** `mem_limit` must accept runtime size updates, while `mem_used_max` reset must accept only `0` as its control value.

**User story:** As an operator tuning memory pressure, I expect memory-limit writes to be accepted at runtime but stats-reset writes to be tightly validated, **so that** routine tuning cannot accidentally trigger unrelated state changes.

**Implementation note:** `mem_limit_store()` uses `memparse()` and page alignment; `mem_used_max_store()` accepts only zero and refreshes the counter from the pool.

**Conditions of satisfaction:**
1. `mem_limit` parses suffix-based sizes and stores page-aligned limits.
2. Invalid `mem_limit` input returns `-EINVAL`.
3. `mem_used_max` rejects any value other than zero.
4. When initialized, `mem_used_max` reset snapshots the current pool total.

**Alternative paths:** writes before initialization; runtime updates while I/O continues.

**References:** `drivers/block/zram/zram_drv.c:382-418`; `Documentation/admin-guide/blockdev/zram.rst:147-165`

**Specificity:** specific

### REQ-004: Primary compressor selection is limited to supported pre-init algorithms
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§76-95]

**Summary:** The primary compression algorithm must be chosen from compiled-in backends and must not change once the device is initialized.

**User story:** As an administrator choosing a compression algorithm, I expect zram to reject unknown or too-late selections, **so that** runtime storage layout stays coherent.

**Implementation note:** `__comp_algorithm_store()` copies the requested algorithm name, validates it through `zcomp_available_algorithm()`, and rejects post-init changes.

**Conditions of satisfaction:**
1. Unsupported compressor names return `-EINVAL`.
2. Overlong names return `-E2BIG`.
3. Post-init writes return `-EBUSY`.
4. `comp_algorithm_show()` brackets the active compressor in the advertised list.

**Alternative paths:** default compressor on add/reset; secondary compressor display when multi-comp is enabled.

**References:** `drivers/block/zram/zram_drv.c:1622-1796`; `drivers/block/zram/zcomp.c:75-108`

**Specificity:** specific

### REQ-005: Algorithm parameters are bound by priority/algo selectors and explicit key parsing
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§96-126]

**Summary:** Algorithm-parameter writes must accept only explicit `key=value` selectors (`priority`, `level`, `algo`, `dict`, `deflate.winbits`) and map them to one compressor priority.

**User story:** As an operator tuning compressor behavior, I expect zram to parse parameter writes deterministically, **so that** dictionaries and levels apply to the compressor I intended.

**Implementation note:** `algorithm_params_store()` tokenizes the input, resolves an optional algorithm name to a priority, and stores dictionary and level state in `zram->params[prio]`.

**Conditions of satisfaction:**
1. Valueless or unknown parameters are rejected.
2. Algorithm name and explicit priority must resolve to a valid compressor slot.
3. Dictionary paths are loaded from the filesystem into backend parameter memory.
4. Stored params survive until compressor creation or reset tears them down.
5. Once the device is initialized, writes that would change compressor-creation parameters are rejected rather than mutating live state in place.

**Alternative paths:** primary vs secondary compressors; missing dictionary; backend-specific parameters such as `deflate.winbits`; post-init writes after `disksize` has already created compressor instances.

**References:** `drivers/block/zram/zram_drv.c:1664-1772`; `drivers/block/zram/backend_zstd.c:51-90`

**Specificity:** specific

### REQ-006: Backing device setup is pre-init-only and block-device-only
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§345-351]

**Summary:** `backing_dev` must accept only a non-zero-sized block device before initialization and must provision a bitmap sized to the backing device's page capacity.

**User story:** As an operator enabling writeback, I expect zram to reject unusable backing targets early, **so that** later writeback requests do not fail on an impossible backing configuration.

**Implementation note:** `backing_dev_store()` copies the path, opens it exclusively, validates `S_ISBLK`, rejects zero-page devices, allocates a bitmap, and stores the resulting `bdev`/file pointers only on success.

**Conditions of satisfaction:**
1. Post-init writes return `-EBUSY`.
2. Non-block devices return `-ENOTBLK`.
3. Zero-sized block devices return `-EINVAL`.
4. Successful setup updates `backing_dev`, `bdev`, `bitmap`, and `nr_pages` together.

**Alternative paths:** replacing an earlier backing device; path with trailing newline; allocation failure while preparing the bitmap.

**References:** `drivers/block/zram/zram_drv.c:684-802`; `Documentation/admin-guide/blockdev/zram.rst:345-351`

**Specificity:** specific

### REQ-007: Writeback feature knobs preserve ordering and input bounds
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§398-458]

**Summary:** `compressed_writeback`, `writeback_limit_enable`, `writeback_limit`, and `writeback_batch_size` must honor their documented ordering and reject invalid inputs.

**User story:** As an operator managing flash wear and throughput, I expect writeback control knobs to preserve sane accounting, **so that** zram does not oversubscribe write budget or run with an impossible batch size.

**Implementation note:** `compressed_writeback_store()` is pre-init-only; `writeback_limit_store()` rounds down to page-aligned 4K units; `writeback_batch_size_store()` rejects zero.

**Conditions of satisfaction:**
1. `compressed_writeback` returns busy after init.
2. `writeback_limit` values are rounded down to a page-compatible 4K count.
3. `writeback_batch_size` rejects zero.
4. Rollback restores consumed budget when a backing bio fails.

**Alternative paths:** writeback-limit disabled; large page sizes; runtime batch-size changes between runs.

**References:** `drivers/block/zram/zram_drv.c:552-682,902-916`; `Documentation/admin-guide/blockdev/zram.rst:398-458`

**Specificity:** specific

## Writeback and recompression requirements

These requirements govern post-processing over existing slots. The main review trap here is checking only the happy path: the real correctness bar is whether scans exclude ineligible slots, budget accounting matches submitted bios, and flag transitions leave later reads/writes with a coherent view of the slot.

### REQ-008: Writeback request parsing supports both modern and legacy syntax
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§352-392]

**Summary:** `writeback` writes must support both legacy valueless mode selectors and the current `key=value` form for mode and page selectors.

**User story:** As an administrator using existing automation, I expect older `echo huge > writeback` commands and newer `type=...`/`page_indexes=...` commands to keep working, **so that** kernel updates do not silently break writeback scripts.

**Implementation note:** `writeback_store()` tokenizes the input, accepts legacy mode-only tokens, and parses `type`, `page_index`, and `page_indexes`.

**Conditions of satisfaction:**
1. Legacy mode-only writes parse as a valid writeback mode.
2. `type=` accepts `idle`, `huge`, `huge_idle`, and `incompressible`.
3. `page_index` and `page_indexes` reject out-of-range or malformed selectors.
4. The handler rejects writeback when the device is uninitialized or lacks a backing device.

**Alternative paths:** multiple page selectors; mode plus page range; invalid range order.

**References:** `drivers/block/zram/zram_drv.c:1141-1337`; `Documentation/admin-guide/blockdev/zram.rst:352-392`

**Specificity:** specific

### REQ-009: Writeback selection and completion preserve slot ownership
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§345-459]

**Summary:** Writeback must only target eligible slots, reserve one backing block per submitted bio, and convert the slot to `ZRAM_WB` only if post-processing ownership still belongs to the request at completion time.

**User story:** As an operator using writeback under memory pressure, I expect only the intended pages to move to backing storage and failed bios to leave the slot recoverable, **so that** writeback does not introduce silent state corruption.

**Implementation note:** `scan_slots_for_writeback()` filters slots; `zram_writeback_slots()` reserves blocks and submits bios; `zram_writeback_complete()` verifies `ZRAM_PP_SLOT` before mutating the slot and rolls back budget on failure.

**Conditions of satisfaction:**
1. Slots already marked `WB` or `SAME` are skipped.
2. Idle/huge/incompressible modes only select matching slots.
3. Each submitted writeback bio consumes exactly one reserved backing block.
4. Failed bios release the block and restore budget.
5. Completion only transforms a slot that still carries the current post-processing claim.

**Alternative paths:** backing device full; depleted writeback budget; slot freed or rewritten before completion.

**References:** `drivers/block/zram/zram_drv.c:918-1133,1199-1235`

**Specificity:** specific

### REQ-010: Recompression is eligibility-driven and progress-based
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§462-547]

**Summary:** Recompression must only visit eligible slots and must retain a recompressed object only when it improves class or satisfies the requested threshold.

**User story:** As an operator reclaiming memory from cold pages, I expect recompression to spend work only on pages that can improve memory usage, **so that** slow secondary compressors do not add churn without benefit.

**Implementation note:** `scan_slots_for_recompress()` filters by idle/huge plus current priority; `recompress_slot()` skips already-small objects and iterates secondary compressors until one improves class/threshold.

**Conditions of satisfaction:**
1. Recompression skips `WB`, `SAME`, and already-marked incompressible slots.
2. Slots already compressed with the same or a higher-priority compressor are skipped.
3. Thresholds at or above the huge-class size are rejected.
4. `max_pages` bounds the number of attempts, even when a page does not improve.
5. Unknown `type=` values are rejected instead of falling through to a mode that scans every eligible slot.

**Alternative paths:** explicit `algo`; explicit `priority`; mixed idle+huge mode; no eligible secondary compressors; misspelled or unsupported `type=` values.

**References:** `drivers/block/zram/zram_drv.c:2337-2678`; `Documentation/admin-guide/blockdev/zram.rst:462-547`

**Specificity:** specific

### REQ-011: Recompression updates slot flags to match the new state
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§503-547]

**Summary:** Recompression must clear stale idle state after touching a slot and mark a slot incompressible only after all configured secondaries fail to produce a useful result.

**User story:** As an operator combining recompression and writeback, I expect recompression to leave slot flags truthful, **so that** later post-processing decisions are based on current state rather than stale metadata.

**Implementation note:** `recompress_slot()` clears `ZRAM_IDLE` immediately after reading the slot and sets `ZRAM_INCOMPRESSIBLE` only when the highest allowed compressor cannot improve the page.

**Conditions of satisfaction:**
1. Any recompression attempt clears `ZRAM_IDLE` before exit.
2. Successful recompression updates handle, size, and compressor priority together.
3. Failed-but-exhausted attempts mark the slot incompressible.
4. Non-improving attempts leave the original object intact.

**Alternative paths:** threshold prevents adoption of a smaller-but-still-too-large result; allocation of the new object fails after successful compression.

**References:** `drivers/block/zram/zram_drv.c:2384-2523`

**Specificity:** specific

## Data-path and state-machine requirements

These requirements trace the actual page representations through read, write, discard, and stats paths. They are the heart of the subsystem: if the state machine around `SAME`, `HUGE`, `WB`, `IDLE`, and `INCOMPRESSIBLE` drifts, zram can return the wrong bytes while all the surface-level sysfs tests still look healthy.

### REQ-012: Same-filled pages are stored and read through synthetic state
**Requirement tag:** [Req: inferred — from page_same_filled()/read_same_filled_page()]

**Summary:** Same-filled pages must be stored as a fill value plus `ZRAM_SAME`, with no zsmalloc allocation, and reconstructed through the dedicated same-filled read path.

**User story:** As a system relying on zram for zero-heavy workloads, I expect all-zero and same-filled pages to consume minimal memory, **so that** swap/tmp compression gains are not lost to pointless metadata allocations.

**Implementation note:** `page_same_filled()`, `write_same_filled_page()`, and `read_same_filled_page()` implement this fast path.

**Conditions of satisfaction:**
1. Same-filled detection checks the full page, not a prefix.
2. Same-filled writes free any existing slot contents before installing the marker.
3. Same-filled reads synthesize the page from the stored fill value.
4. `same_pages` and `pages_stored` counters stay coherent across write/free cycles.

**Alternative paths:** overwriting a previously same-filled slot; freeing a same-filled slot during discard or reset.

**References:** `drivers/block/zram/zram_drv.c:340-360,1983-2034,2036-2045,2185-2198`

**Specificity:** specific

### REQ-013: Incompressible pages are stored raw at page size
**Requirement tag:** [Req: formal — docs_gathered/zsmalloc-design.md §§25-29]

**Summary:** Pages whose compressed length crosses the huge threshold must be stored uncompressed at `PAGE_SIZE` with `ZRAM_HUGE` state and raw-copy readback.

**User story:** As a user writing already-compressed or random data into zram, I expect writes to succeed without impossible allocator requests, **so that** incompressible input degrades gracefully instead of failing outright.

**Implementation note:** `zram_write_page()` hands large compressed results to `write_incompressible_page()`, which allocates exactly `PAGE_SIZE`; reads route through `read_incompressible_page()`.

**Conditions of satisfaction:**
1. `comp_len >= huge_class_size` uses the huge path, not normal compressed storage.
2. Huge-page writes check `zram_can_store_page()` before adopting the new slot.
3. Huge-page reads copy the raw page bytes from zsmalloc.
4. Huge-page free and writeback completion keep `huge_pages` counters coherent.

**Alternative paths:** huge page later written back; huge page later recompressed; allocation failure under low memory.

**References:** `drivers/block/zram/zram_drv.c:1996-2004,2047-2061,2200-2238,2269-2272`

**Specificity:** specific

### REQ-014: Read dispatch follows slot representation and backing state
**Requirement tag:** [Req: inferred — from read_from_zspool()/zram_read_page()]

**Summary:** The read path must dispatch to same-filled, compressed, huge/raw, or backing-device read logic according to the slot flags and handle state, then report decompression failures as I/O errors.

**User story:** As a block-layer caller, I expect zram reads to return bytes matching the slot representation currently in effect, **so that** written-back or deduplicated pages remain transparent to consumers.

**Implementation note:** `read_from_zspool()` and `zram_read_page()` select the path; `read_from_bdev_sync()` / async path handle written-back slots; `zram_bio_read()` converts negative returns into failed-read accounting.

**Conditions of satisfaction:**
1. Same-filled or empty-handle slots read as synthetic filled pages.
2. Non-huge compressed slots use the active compressor priority for decompression.
3. `ZRAM_WB` slots read from the backing device, not the pool.
4. A decompression failure is surfaced as `BLK_STS_IOERR` and increments `failed_reads`.

**Alternative paths:** partial reads; stale `ZRAM_WB` state during deferred decompression; compressed writeback requiring a second decompression step.

**References:** `drivers/block/zram/zram_drv.c:2114-2183,2718-2747`

**Specificity:** specific

### REQ-015: Write, partial-write, and discard flows preserve untouched bytes and complete bios
**Requirement tag:** [Req: inferred — from zram_bvec_write_partial()/zram_bio_discard()]

**Summary:** Partial writes must reconstruct untouched bytes before rewriting a slot, and discard/write-zeroes paths must free only whole physical pages while still completing the bio.

**User story:** As a filesystem or swap caller issuing partial or discard bios, I expect zram to preserve data outside the requested range and to complete no-op discard fragments cleanly, **so that** block-layer semantics stay intact.

**Implementation note:** `zram_bvec_write_partial()` reads the full page into a temporary page before rewriting; `zram_bio_discard()` skips unaligned fragments but owns bio completion.

**Conditions of satisfaction:**
1. Partial writes allocate a temporary page, populate it from the current slot, patch the requested bytes, then call `zram_write_page()`.
2. Full-page writes bypass the temporary-page path.
3. Discard frees only full physical pages.
4. Discard and write-zeroes always complete the bio exactly once, including no-op unaligned fragments.

**Alternative paths:** discard ranges starting mid-page; discard ranges with both leading and trailing fragments; partial reads during writeback-backed storage.

**References:** `drivers/block/zram/zram_drv.c:2304-2330,2681-2800`

**Specificity:** specific

### REQ-016: Statistics and debug output reflect slot/accounting state
**Requirement tag:** [Req: formal — Documentation/admin-guide/blockdev/zram.rst §§197-283,549-588]

**Summary:** `io_stat`, `mm_stat`, `bd_stat`, `debug_stat`, and optional debugfs block-state output must report the counters and flags accumulated by the live data paths.

**User story:** As an operator diagnosing zram behavior, I expect the exported statistics to match what the driver actually did, **so that** I can distinguish memory pressure, writeback activity, and slot-state mix from guesswork.

**Implementation note:** the `*_show()` helpers emit formatted counter snapshots, and debugfs encodes slot flags as letters when memory tracking is enabled.

**Conditions of satisfaction:**
1. `io_stat` exposes failed reads, failed writes, invalid I/O column, and notify-free count in fixed order.
2. `mm_stat` reports orig/compressed size, mem usage, limits, same pages, compaction, and huge-page counters.
3. `bd_stat` reports backing-device counts in 4K units.
4. Debugfs block-state output uses `s`, `w`, `h`, `i`, `r`, `n` to encode slot flags.

**Alternative paths:** uninitialized device stats; configs with writeback or memory tracking disabled.

**References:** `drivers/block/zram/zram_drv.c:536-550,1540-1598,1874-1939`; `Documentation/admin-guide/blockdev/zram.rst:205-297,549-588`

**Specificity:** specific

## Compression-stream and teardown requirements

These requirements protect the less-visible concurrency and cleanup mechanics around compression contexts. They matter because zram is expected to keep working during CPU hotplug, allocation pressure, and teardown; if the stream or reset logic fails, the block-device surface sees it as a mysterious I/O bug.

### REQ-017: Compression backends are per-CPU, hotplug-safe, and backend-limited
**Requirement tag:** [Req: inferred — from zcomp.c backend and stream management]

**Summary:** zram must advertise only compiled-in compressors and manage per-CPU compression streams in a way that tolerates CPU migration and hotplug teardown.

**User story:** As a kernel integrator enabling different compression backends, I expect zram to use only compiled-in algorithms and to survive CPU online/offline transitions, **so that** compression does not race destroyed per-CPU contexts.

**Implementation note:** `lookup_backend_ops()` and `zcomp_available_show()` expose compiled backends; `zcomp_stream_get()` retries if migration races stream teardown; `cpuhp_setup_state_multi()` wires hotplug callbacks.

**Conditions of satisfaction:**
1. Only compiled-in backends appear in the advertised list.
2. The active backend is bracketed in `zcomp_available_show()`.
3. Per-CPU streams are created for each possible CPU and destroyed through hotplug callbacks.
4. Stream acquisition never returns a destroyed buffer after migration.

**Alternative paths:** CPU-hotplug registration failure; backend setup failure after stream allocation.

**References:** `drivers/block/zram/zcomp.c:23-257`, `drivers/block/zram/zram_drv.c:3257-3299`

**Specificity:** specific

### REQ-018: Reset and remove fully quiesce the device before freeing storage state
**Requirement tag:** [Req: formal — docs_gathered/zram-community-development-history.md §§151-165]

**Summary:** Reset and removal must block new opens, drain pending block I/O, free metadata/backing state/backends, and leave no leaked initialized state behind.

**User story:** As an administrator resetting or removing zram, I expect teardown to be safe even under concurrent I/O, **so that** the next initialization starts from a clean state instead of stale or freed metadata.

**Implementation note:** `reset_store()` and `zram_remove()` coordinate `claim`, `open_mutex`, and `sync_blockdev()` before calling `zram_reset_device()`; `zram_remove()` performs a final post-`del_gendisk()` reset to catch allocations raced in by `disksize_store()`.

**Conditions of satisfaction:**
1. Reset rejects a zero control value.
2. Reset and remove reject active openers.
3. Teardown drains pending I/O before freeing metadata.
4. Reset zeroes capacity, stats, limits, backing-device state, and compressor state.
5. Removal performs a final reset after `del_gendisk()` to avoid leaks from late `disksize_store()` activity.

**Alternative paths:** removal while a reset claim is active; partial initialization followed by module exit.

**References:** `drivers/block/zram/zram_drv.c:2829-2869,2922-2959,3124-3169`

**Specificity:** specific
