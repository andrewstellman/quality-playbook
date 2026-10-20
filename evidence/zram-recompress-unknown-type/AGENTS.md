# AGENTS.md

## Project description

This repository snapshot is a focused Linux-kernel subtree for the zram compressed RAM block-device driver. The primary implementation lives in `drivers/block/zram/`, and the user-facing contract lives in `Documentation/admin-guide/blockdev/zram.rst`.

## Setup and environment notes

- Host in this session: Darwin, so live kernel-module execution is **not** available here.
- `make` on this host is GNU Make 3.81, but this repo requires GNU Make >= 4.0.
- There is no existing `AGENTS.md` or in-tree zram-specific selftest/KUnit harness in this snapshot.
- Supplemental docs were provided in `docs_gathered/` and were used during playbook generation.

## Build and test commands

- Structural quality tests for this repo snapshot:
  - `python3 -m unittest quality.test_functional -v`
  - `python3 -m unittest quality.test_regression -v`
- Kernel build/help check (on a suitable Linux/GNU Make 4+ host):
  - `make help`
- Live integration workflow (Linux root required): follow `quality/RUN_INTEGRATION_TESTS.md`

## Architecture overview

- `drivers/block/zram/zram_drv.c` — sysfs handlers, slot table, block I/O, writeback, recompression, reset/remove lifecycle
- `drivers/block/zram/zram_drv.h` — slot flags, stats, and core `struct zram`
- `drivers/block/zram/zcomp.c` / `zcomp.h` — backend registry and per-CPU compression streams
- `drivers/block/zram/backend_*.c` — compressor-specific setup and execution
- `Documentation/admin-guide/blockdev/zram.rst` — authoritative admin/user contract

## Key design decisions

- `disksize` is the initialization gate; several other knobs are intended to be pre-init-only.
- zram uses zsmalloc handles, so incompressible pages must never require allocations larger than `PAGE_SIZE`.
- Slot flags (`SAME`, `HUGE`, `WB`, `IDLE`, `INCOMPRESSIBLE`) are the core state machine and must be traced across reads, writes, writeback, recompression, and teardown.
- Reset/remove flows claim the device and drain block I/O before freeing metadata.

## Known quirks

- `docs_gathered/` contains at least two stale claims relative to the current source snapshot: the `-EAGAIN` concurrency note and the `invalid_io` counter wording.
- The generated executable tests are Python source-conformance checks because this repo snapshot does not include a runnable zram test harness in-tree.

## Quality Docs

- `quality/QUALITY.md`
- `quality/REQUIREMENTS.md`
- `quality/CONTRACTS.md`
- `quality/COVERAGE_MATRIX.md`
- `quality/COMPLETENESS_REPORT.md`
- `quality/RUN_CODE_REVIEW.md`
- `quality/RUN_INTEGRATION_TESTS.md`
- `quality/RUN_SPEC_AUDIT.md`
- `quality/REVIEW_REQUIREMENTS.md`
- `quality/REFINE_REQUIREMENTS.md`
- `quality/PROGRESS.md`
