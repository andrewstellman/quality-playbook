# Code Review — Linux virtio transport/negotiation layer (Phase 3)

> Quality Playbook v1.5.8 · 3-pass protocol per quality/RUN_CODE_REVIEW.md
> Date: 2026-06-19 · Reviewer: arunner phase3 subagent · Tree @ bfe62a454542
> Surface: drivers/virtio/*.c|*.h + include/{linux,uapi}/linux/virtio*.h

## Pass 1: Structural Review

### 1. Input validation and boundary handling
- `vring_create_virtqueue` → split/packed allocators: `vring_alloc_queue_split`
  (virtio_ring.c:1256-1258) rejects non-power-of-2 `num` with -EINVAL; modern PCI
  setup_vq (virtio_pci_modern.c:710-712) reads `num` FROM the device and rejects `!num`.
  `virtqueue_resize` (virtio_ring.c:3342-3346) bounds `num > vq->vq.num_max` → -E2BIG.
  REQ-009 satisfied — the "driver requests > device max" scenario is not reachable at
  creation because the size is device-sourced. (Phase-1 candidate #6 REJECTED.)

### 2. Resource lifecycle (reset)
- PCI-modern `vp_reset` (virtio_pci_modern.c:546-565): writes 0, then
  `while (vp_modern_get_status(mdev)) msleep(1)` — spec §5 satisfied.
- PCI-legacy `vp_reset` (virtio_pci_legacy.c:93-103): writes 0, single read-back —
  documented legacy exemption.
- **MMIO `vm_reset` (virtio_mmio.c:251-257): writes 0 and returns; NO read-back poll.**
  → **BUG-003** (spec §5 MUST unmet). Line 256 is the last statement.

### 3. Concurrency and state management
- `vp_interrupt` (virtio_pci_common.c:106-124): config dispatch at :120-121 **discards**
  `vp_config_changed`'s IRQ_HANDLED; returns `vp_vring_interrupt` (IRQ_NONE for config-only).
  → **BUG-002**. MMIO `vm_interrupt` (:296-299) handles this correctly (ret = IRQ_HANDLED).
- Packed wrap site (virtio_ring.c:1560-1583): XOR read-modify-write of `avail_wrap_counter`
  and `avail_used_flags` preserves other bits; preceded by `virtio_wmb` at :1569. Correct
  (REQ-007). Barriers present at every index-update site (756/964/1111 split, 1569/2246/2292
  packed). (Phase-1 candidate #5 REJECTED — no missing-barrier defect.)

### 4. Unit and encoding correctness
- Whitelist loop iterates `[VIRTIO_TRANSPORT_F_START(28), VIRTIO_TRANSPORT_F_END(42))`
  (virtio_config.h:54-55) — correct range.
- Legacy 32-bit boundary excludes bits 37-41 (legacy finalize is 32-bit bounded) — correct.

### 5. Enumeration / whitelist completeness — MECHANICAL CHECK
- **List A (code, from quality/mechanical/vring_transport_features_cases.txt):**
  INDIRECT_DESC, EVENT_IDX, VERSION_1, ACCESS_PLATFORM, RING_PACKED, ORDER_PLATFORM,
  NOTIFICATION_DATA, IN_ORDER (8 case labels, virtio_ring.c:3511-3525).
- **List B (spec, virtio_config.h):** adds SR_IOV(37), NOTIF_CONFIG_DATA(39),
  RING_RESET(40), ADMIN_VQ(41).
- **Diff:** 37/39/40/41 NOT in code → hit `default:` clear at 3527-3529.
- **Compensators:** vp_transport_features (virtio_pci_modern.c:372-380) re-adds 37/40/41
  but **NOT 39**; vm_finalize_features and virtio_vdpa_finalize_features re-add NONE.
- **NOTIF_CONFIG_DATA(39) is compensated by nobody** even though PCI validates it
  (vp_check_common_size :407) → **BUG-001**.

## Pass 2: Requirement Verification

| REQ | Verdict | Citation |
|-----|---------|----------|
| REQ-001 | PARTIALLY SATISFIED | PCI compensates 37/40/41 but not 39 (virtio_pci_modern.c:367-381); MMIO/vDPA compensate nothing but RING_RESET/ADMIN_VQ/SR_IOV are unusable/out-of-scope there → BUG-001 for bit 39 on PCI |
| REQ-002 | VIOLATED (1 bit) | vring_transport_features (virtio_ring.c:3511-3529, mechanical receipt) clears 37/39/40/41; only 39 is uncompensated → BUG-001 |
| REQ-003 | VIOLATED (MMIO) | vm_reset (virtio_mmio.c:251-257) lacks the §5 poll → BUG-003 |
| REQ-004 | VIOLATED (PCI) | vp_interrupt (virtio_pci_common.c:120-123) drops config IRQ_HANDLED → BUG-002 |
| REQ-005 | VIOLATED | vp_check_common_size validates bit 39 (virtio_pci_modern.c:407) but no compensator re-adds it → BUG-001 (validator/compensator disagreement) |
| REQ-006..009 | SATISFIED | features_ok re-checks; range boundaries 28/42; barriers present; queue-size bounded |
| REQ-010..017 | SATISFIED (presence) | artifact-location REQs — verified structurally by Phase 6 gate |

## Pass 3: Cross-Requirement Consistency

- **Transport bit 39 (NOTIF_CONFIG_DATA):** REQ-002 (whitelist clears it) ∧ REQ-005
  (vp_check_common_size validates it) ∧ REQ-001 (no compensator re-adds it) →
  INCONSISTENT, as predicted. Confirmed as BUG-001.
- **Compensation set union:** PCI re-adds {37,40,41}; MMIO/vDPA re-add {}. Bit 39
  compensated by nobody. MMIO/vDPA omissions of {37,40,41} are intentional
  (out-of-scope / no reset-vq ops) — see compensation_grid_downgrades.json.
- **Reset wait semantics:** PCI-modern polls, legacy single-reads (exempt), MMIO does
  neither → MMIO diverges from the §5 contract without documentation. BUG-003.

## Combined Summary

| Source | Finding | Severity | Status |
|--------|---------|----------|--------|
| Code Review | BUG-001 NOTIF_CONFIG_DATA(39) stripped on PCI-modern | MEDIUM | CONFIRMED |
| Code Review | BUG-002 vp_interrupt IRQ_NONE for config-only | MEDIUM | CONFIRMED |
| Code Review | BUG-003 vm_reset omits §5 status poll | MEDIUM | CONFIRMED |
| Code Review | Candidate #1 MMIO/vDPA strip RING_RESET/ADMIN_VQ/SR_IOV | — | DEMOTED (unreachable/out-of-scope) |
| Code Review | Candidate #5 missing barriers | — | REJECTED (barriers present) |
| Code Review | Candidate #6 queue-size not bounded | — | REJECTED (device-sourced size + bounds) |

**Overall assessment: FIX BEFORE MERGE** (3 MEDIUM correctness defects, all with
RED→GREEN-validated regression tests and fix patches).

## Closure checklist

- BUG count: 3. Regression test functions: 3 (test_bug001/002/003). Match. ✓
- BUG-001 → REGRESSION TEST: test_regression.py::TestRegressionConfirmedBugs::test_bug001_pci_compensator_readds_notif_config_data
- BUG-002 → REGRESSION TEST: test_regression.py::TestRegressionConfirmedBugs::test_bug002_vp_interrupt_returns_handled_on_config
- BUG-003 → REGRESSION TEST: test_regression.py::TestRegressionConfirmedBugs::test_bug003_vm_reset_polls_for_status_zero
- RED→GREEN: all 3 XFAIL on source; all 3 PASS after fix patches (filesystem-copy validation,
  source is untracked so git-worktree pattern N/A).
