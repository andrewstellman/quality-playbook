# Confirmed Bugs — Linux virtio driver subsystem

> Quality Playbook v1.5.8 · Phase 3 (Code Review + Regression Tests) · 2026-06-19
> Audited surface: drivers/virtio/*.c|*.h + include/{linux,uapi}/linux/virtio*.h @ bfe62a454542

Three bugs confirmed in Phase 3. Three Phase-1 candidates were rejected after
reachability analysis (see "Rejected candidates" at the bottom).

---

### BUG-001: NOTIF_CONFIG_DATA(39) stripped on PCI-modern despite validator + notify-data path
- Primary requirement: REQ-001 (also REQ-002 whitelist, REQ-005 validator/compensator agreement)
- Covers: [REQ-001/cell-NOTIF_CONFIG_DATA-PCI, REQ-002/cell-NOTIF_CONFIG_DATA-RING]
- Consolidation rationale: a single root cause — `vring_transport_features` clears bit 39 (the RING-site cell) and `vp_transport_features` is the missing compensator (the PCI-site cell). One fix (re-add bit 39 in the PCI compensator) closes both cells; they are not independently fixable.
- severity: MEDIUM
- divergence_type: cross-source
- File:line: drivers/virtio/virtio_pci_modern.c:367-381 (vp_transport_features — no bit-39 re-add); drivers/virtio/virtio_ring.c:3511-3529 (default: clear); drivers/virtio/virtio_pci_modern.c:407 (vp_check_common_size validates bit 39); drivers/virtio/virtio_pci_modern.c:676-702 (vp_notify_with_data uses queue_notify_data)
- reachability_analysis: "no guard; defect path reached unconditionally. vring_transport_features (virtio_ring.c:3505-3532) has no case label for VIRTIO_F_NOTIF_CONFIG_DATA(39), so every finalize hits the default branch at 3527-3529 and __virtio_clear_bit(vdev, 39). vp_transport_features (367-381) re-adds SR_IOV/RING_RESET/ADMIN_VQ but NOT bit 39 — searched the full function body, no conditional path re-adds it. Therefore after vp_finalize_features the bit is always 0 on modern PCI, even when the device offered it and vp_check_common_size (:407) already validated the common-cfg has the queue_notify_data field. The vp_notify_with_data path (:702) is selected on VIRTIO_F_NOTIFICATION_DATA(38), so bit 39's config-data variant is unreachable. Mechanical receipt quality/mechanical/vring_transport_features_cases.txt confirms 8 case labels, bit 39 absent."
- Expected: after `vp_finalize_features`, if the device offered NOTIF_CONFIG_DATA(39) and the common cfg is large enough (validated at :407), the bit survives so the queue_notify_data path can be used.
- Actual: the bit is cleared by `vring_transport_features` and never restored by `vp_transport_features`, making the validated feature dead.
- Closure: REGRESSION TEST: quality/test_regression.py::TestRegressionConfirmedBugs::test_bug001_pci_compensator_readds_notif_config_data

### BUG-002: vp_interrupt returns IRQ_NONE for a config-change-only interrupt
- Primary requirement: REQ-004
- Covers: [REQ-004/cell-CONFIG_IRQ_HANDLED-PCI]
- severity: MEDIUM
- divergence_type: code-spec
- File:line: drivers/virtio/virtio_pci_common.c:106-124 (vp_interrupt); :120-121 (vp_config_changed return discarded); :72-81 (vp_config_changed returns IRQ_HANDLED); :82-101 (vp_vring_interrupt returns IRQ_NONE when no vq serviced)
- reachability_analysis: "no guard; defect path reached unconditionally. In vp_interrupt (virtio_pci_common.c:111-124): isr is non-zero for a config interrupt (VIRTIO_PCI_ISR_CONFIG=0x2), so the `if (!isr) return IRQ_NONE` early-return at :116-117 is NOT taken. At :120-121 vp_config_changed(irq, opaque) is called but its IRQ_HANDLED return value is discarded. The function then `return vp_vring_interrupt(irq, opaque)` (:123), which iterates vp_dev->virtqueues and returns IRQ_NONE unless some vq's vring_interrupt returned IRQ_HANDLED. For a config-change-only interrupt with no concurrent vring activity, vp_vring_interrupt returns IRQ_NONE — so vp_interrupt reports IRQ_NONE despite having serviced the config change. No upstream guard prevents this; the discarded return is unconditional. (Single-MSI-X / INTx legacy path, where config and vring share one vector, is exactly when this is reachable.)"
- Expected: when the handler services a config-change interrupt it must return IRQ_HANDLED (parity with MMIO vm_interrupt at virtio_mmio.c:296-299), independent of vring activity.
- Actual: the config handler's IRQ_HANDLED is dropped; the overall return is whatever vp_vring_interrupt yields, i.e. IRQ_NONE for config-only. Under a shared IRQ line this can lead the kernel to treat the interrupt as spurious.
- Closure: REGRESSION TEST: quality/test_regression.py::TestRegressionConfirmedBugs::test_bug002_vp_interrupt_returns_handled_on_config

### BUG-003: vm_reset omits the spec §5 "wait for status read 0" poll
- Primary requirement: REQ-003
- Covers: [REQ-003/cell-RESET_WAIT_FOR_ZERO-MMIO]
- severity: MEDIUM
- divergence_type: code-spec
- File:line: drivers/virtio/virtio_mmio.c:251-257 (vm_reset); compare drivers/virtio/virtio_pci_modern.c:546-565 (vp_reset polls `while (vp_modern_get_status(mdev)) msleep(1)`)
- reachability_analysis: "no guard; defect path reached unconditionally. vm_reset (virtio_mmio.c:251-257) writes 0 to VIRTIO_MMIO_STATUS and returns immediately — the function body is two statements with no readback loop. There is no upstream caller-side poll: the core reset contract is expected to be satisfied inside the transport's .reset op (virtio_pci_modern vp_reset and virtio_pci_legacy both implement the readback themselves). No compensating wait exists between vm_reset return and the next device-status write. The MMIO spec §5 contract (write 0, then read device_status until it returns 0) is therefore unmet for every MMIO reset."
- Expected: per virtio spec §5, after writing 0 the driver MUST wait for a read of device_status to return 0 before reinitializing (as vp_reset and vp_legacy do).
- Actual: vm_reset writes 0 and returns with no read-back; a device that has not yet completed reset can be reinitialized against stale state.
- Closure: REGRESSION TEST: quality/test_regression.py::TestRegressionConfirmedBugs::test_bug003_vm_reset_polls_for_status_zero

---

## Rejected candidates (Phase-1 candidates demoted under reachability analysis)

- **Candidate #1 (MMIO/vDPA strip RING_RESET/ADMIN_VQ/SR_IOV):** DEMOTED. Reachability:
  MMIO and vDPA define neither `disable_vq_and_reset` nor `enable_vq_after_reset` in their
  `virtio_config_ops` (virtio_mmio.c / virtio_vdpa.c config_ops structs), so
  `virtqueue_reset` (virtio_ring.c:2704-2707) early-returns -ENOENT and RING_RESET is
  unusable even if the bit survived; ADMIN_VQ and SR_IOV are PCI-transport-specific. Stripping
  unusable/out-of-scope bits is correct. Recorded as downgrade cells in
  quality/compensation_grid_downgrades.json (intentionally-partial / out-of-scope). The ONE
  reachable cell of this family — NOTIF_CONFIG_DATA on PCI-modern, where the feature IS
  validated and a notify path exists — is confirmed as BUG-001.
- **Candidate #5 (missing memory barriers split/packed):** REJECTED. Barriers are present at
  every index-update site (virtio_ring.c:756 split avail, 1569 packed avail, 2246/2292 used,
  plus store_mb at 964/1034/1111/2085). The packed wrap site (1560-1583) performs a clean
  XOR read-modify-write of avail_wrap_counter and avail_used_flags preserving other bits,
  preceded by virtio_wmb at :1569. No missing-barrier defect.
- **Candidate #6 (queue-size not bounded vs device max at creation):** REJECTED. In the modern
  PCI path the queue size is read FROM the device (virtio_pci_modern.c:710
  vp_modern_get_queue_size) rather than driver-requested, with a `!num` reject (:711) and
  `is_power_of_2` validation in vring_alloc_queue_split (virtio_ring.c:1256-1258); the
  resize path bounds `num > vq->vq.num_max` -> -E2BIG (virtio_ring.c:3342). The
  "driver requests larger than device max" scenario is not reachable at creation.
