# Integration Test Protocol: zram

## Working Directory

Run all commands from the project root using relative paths only.

## Safety Constraints

- Run only on a Linux host or VM where you can load and unload a test kernel/module safely.
- Do **not** point writeback at production storage.
- Create test files only under `./quality/results/` or a disposable loopback image.
- If a test fails, record it and move on. Do not patch the kernel while executing this protocol.

## Pre-Flight Check

- [ ] `uname -s` prints `Linux`
- [ ] `make --version` is GNU Make 4.0+ (this repo snapshot cannot build with the host's default Darwin `make 3.81`)
- [ ] Root or equivalent privileges available for `modprobe`, `mkswap`, `swapon`, loop devices, and sysfs writes
- [ ] Kernel config includes `CONFIG_ZRAM=y|m`; optional tests also require `CONFIG_ZRAM_WRITEBACK`, `CONFIG_ZRAM_MULTI_COMP`, and `CONFIG_ZRAM_MEMORY_TRACKING`
- [ ] `Documentation/admin-guide/blockdev/zram.rst` and `quality/test_functional.py` are present as the source-of-truth contracts

## Test Matrix

| Check | Method | Pass Criteria |
|-------|--------|---------------|
| Fresh-device lifecycle | Load zram, inspect `initstate`, set `disksize`, then reset | `initstate` toggles `0 -> 1 -> 0`, `disksize` returns to `0` after reset |
| Compressor freeze | Set `comp_algorithm`, then initialize and try changing it again | pre-init write succeeds; post-init write fails with non-zero exit / `-EBUSY` |
| Swap happy path | `mkswap` + `swapon` + memory pressure + `swapoff` | I/O succeeds; `mm_stat` counters move; no failed reads/writes |
| Partial-I/O correctness | Create a filesystem on zram, write/update a sub-page region, then read back | untouched bytes remain unchanged |
| Writeback path | Configure `backing_dev`, enable limits/batch size, trigger `writeback` | `bd_stat` increments and selected pages transition to `w` in debugfs when enabled |
| Recompression path | Configure secondary compressor and run `recompress` with threshold | eligible pages either get `r` state or stay intact with no failed writes |
| Discard semantics | Issue aligned and unaligned discards/write-zeroes | aligned pages free storage; unaligned no-op requests still complete successfully |

## Automated Integration Tests

### Host-side structural baseline

```bash
python3 -m unittest quality.test_functional -v
python3 -m unittest quality.test_regression -v
```

### Live kernel execution skeleton

```bash
# Example only: adapt paths to your build/install workflow
modprobe zram num_devices=1
echo lzo-rle > /sys/block/zram0/comp_algorithm
echo 256M > /sys/block/zram0/disksize
mkswap /dev/zram0
swapon /dev/zram0
cat /sys/block/zram0/mm_stat
swapoff /dev/zram0
echo 1 > /sys/block/zram0/reset
rmmod zram
```

## Manual Verification Steps

1. Verify `comp_algorithm`, `backing_dev`, and `compressed_writeback` reject post-init mutation.
2. If `CONFIG_ZRAM_WRITEBACK=y`, use a disposable loopback partition and inspect `bd_stat` plus debugfs block-state output.
3. If `CONFIG_ZRAM_MULTI_COMP=y`, configure a secondary compressor and confirm recompression updates slot state without increasing failure counters.
4. For discard testing, issue both aligned and sub-page discard/write-zeroes requests and confirm the caller does not hang.

## Execution UX (How to Present When Running This Protocol)

### Phase 1: The Plan

```markdown
## Integration Test Plan

| # | Test | What It Checks | Est. Time |
|---|------|----------------|-----------|
| 1 | Structural baseline | Source-level contract tests | ~5s |
| 2 | Fresh-device lifecycle | init/reset sequencing | ~30s |
| 3 | Swap happy path | end-to-end block I/O | ~2m |
| 4 | Writeback / recompress | optional feature flows | ~3m |
| 5 | Discard semantics | alignment-sensitive completion | ~1m |
```

### Phase 2: Progress

Use one-line heartbeats:

```text
✓ Test 1: Structural baseline — PASS (0.4s)
⧗ Test 3: Swap happy path... running
✗ Test 5: Discard semantics — FAIL (unaligned discard hung caller)
```

### Phase 3: Results

Summarize in a table and save details to `quality/results/YYYY-MM-DD-integration.md`.

## Field Reference Table (built from source/docs, not memory)

### `io_stat`
Sources: `Documentation/admin-guide/blockdev/zram.rst`, `drivers/block/zram/zram_drv.c:1874-1888`

| Field | Type | Constraints |
|-------|------|-------------|
| `failed_reads` | integer | monotonic counter |
| `failed_writes` | integer | monotonic counter |
| `invalid_io` | integer | emitted as third column |
| `notify_free` | integer | monotonic counter |

### `mm_stat`
Sources: `Documentation/admin-guide/blockdev/zram.rst`, `drivers/block/zram/zram_drv.c:1890-1923`

| Field | Type | Constraints |
|-------|------|-------------|
| `orig_data_size` | integer bytes | `pages_stored << PAGE_SHIFT` |
| `compr_data_size` | integer bytes | compressed bytes currently stored |
| `mem_used_total` | integer bytes | `zs_get_total_pages() << PAGE_SHIFT` |
| `mem_limit` | integer bytes | `limit_pages << PAGE_SHIFT` |
| `mem_used_max` | integer bytes | peak `zs_get_total_pages()` |
| `same_pages` | integer | same-filled slot count |
| `pages_compacted` | integer | zsmalloc compaction count |
| `huge_pages` | integer | current incompressible-page count |
| `huge_pages_since` | integer | historical incompressible-page count |

### `bd_stat`
Sources: `Documentation/admin-guide/blockdev/zram.rst`, `drivers/block/zram/zram_drv.c:536-550`

| Field | Type | Constraints |
|-------|------|-------------|
| `bd_count` | integer 4K units | current written-back storage |
| `bd_reads` | integer 4K units | backing-device read count |
| `bd_writes` | integer 4K units | backing-device write count |

### debugfs block-state letters
Sources: `Documentation/admin-guide/blockdev/zram.rst`, `drivers/block/zram/zram_drv.c:1565-1574`

| Field | Type | Constraints |
|-------|------|-------------|
| `s` | flag | same-filled slot |
| `w` | flag | written-back slot |
| `h` | flag | huge/incompressible slot |
| `i` | flag | idle slot |
| `r` | flag | recompressed slot |
| `n` | flag | none of the configured algorithms could compress it |

## Quality Gates

1. `mm_stat` must show `orig_data_size > 0` after real I/O and return to zero after reset.
2. Post-init writes to frozen config knobs must fail rather than silently changing live state.
3. When writeback is exercised, `bd_stat.bd_writes` must increase and `mm_stat.compr_data_size` must not increase for the migrated slots.
4. When recompression is exercised, slot flags must remain internally consistent (`r` implies a non-zero compression priority; recompressed pages must not remain stale-idle).
5. Discard/write-zeroes requests must always complete, even when they free no whole physical pages.
