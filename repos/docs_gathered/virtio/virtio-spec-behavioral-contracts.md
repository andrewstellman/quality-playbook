# virtio Specification — Behavioral Contracts and Edge Cases

Extracted from OASIS Virtual I/O Device specifications (v1.0, v1.1, v1.2), community discussions, and implementation experience. This document focuses specifically on MUST/SHOULD requirements and known edge cases that an auditor should check against the code.

Sources: OASIS specs v1.0-v1.2 (docs.oasis-open.org/virtio), GitHub issues (github.com/oasis-tcs/virtio-spec), lore.kernel.org patch discussions.

---

## 1. Feature Negotiation — MUST Requirements

### Driver Side
- Driver MUST NOT accept feature bits it does not understand
- Driver MUST set FEATURES_OK status bit after writing feature bits
- Driver MUST re-read device status after setting FEATURES_OK to confirm acceptance
- If FEATURES_OK is not set after re-read, driver MUST treat device as unusable
- Driver MUST NOT use device-specific features before feature negotiation completes

### Device Side
- Device MUST set FEATURES_OK only if it accepts the driver's feature subset
- Device MUST NOT change its advertised features after reset

### Legacy Compatibility
- Legacy devices (pre-1.0) do NOT support FEATURES_OK — no safe failure mechanism
- VIRTIO_F_VERSION_1 distinguishes legacy from modern devices
- If VIRTIO_F_VERSION_1 not negotiated, device operates in legacy mode with different byte ordering and layout assumptions

---

## 2. Virtqueue — MUST Requirements

### Descriptor Table
- Descriptor table size MUST be a power of two
- Driver MUST ensure descriptor physical addresses are aligned to required boundary
- Driver MUST NOT write to device-owned descriptors (descriptors in the used ring until device returns them)
- Each descriptor MUST specify either read-only (for device) or write-only (for device), not both

### Available Ring (Split)
- Driver MUST write descriptors to available ring in order
- Driver MUST update available index AFTER writing descriptors
- Driver MUST perform memory barrier between writing descriptors and updating available index

### Used Ring (Split)
- Device MUST write completed descriptor index to used ring
- Device MUST update used index AFTER writing used ring entries
- Driver MUST perform memory barrier before reading used ring entries

### Packed Ring Specifics
- Wrap counter MUST be toggled when descriptor index wraps around ring
- Driver MUST maintain consistent wrap counter state across all descriptors
- AVAIL and USED flags in descriptor determine ownership
- Driver MUST NOT modify descriptors owned by device (AVAIL != USED)

---

## 3. Indirect Descriptors — Constraints

When VIRTIO_F_RING_INDIRECT_DESC is negotiated:
- Indirect descriptor table MUST be laid out like regular descriptors
- Buffers MUST appear in order in indirect table
- ID field MUST be ignored by device in indirect descriptors
- Only VIRTQ_DESC_F_WRITE flag is valid in indirect descriptors
- VIRTQ_DESC_F_INDIRECT and VIRTQ_DESC_F_NEXT are NOT valid in indirect descriptors
- Maximum indirect table size MUST NOT exceed main descriptor table count
- A single descriptor with INDIRECT flag set describes the entire indirect table

---

## 4. Notification — MUST Requirements

### Without VIRTIO_F_EVENT_IDX
- If available ring flags field = 0, device MUST send notification after updating used ring
- If available ring flags field = 1, device SHOULD NOT send notification (optimization only)

### With VIRTIO_F_EVENT_IDX
- Device checks used_event after writing used ring
- If current used index equals used_event, device MUST send notification
- Otherwise device SHOULD NOT send notification (optimization)
- Driver MUST update used_event to control when it wants notification
- Neither method is fully synchronized — both are optimizations, not guarantees

---

## 5. Device Reset — MUST Requirements

- Driver MUST write 0 to device_status to initiate reset
- Driver MUST wait for device_status read to return 0 before reinitializing
- Device MUST present 0 in queue_enable on reset
- Device MUST reset all feature negotiation state
- Device MUST clear all virtqueue state

### Individual Queue Reset (v1.2+ with VIRTIO_F_RING_RESET)
- Two-part process: disable, then optionally re-enable
- Driver MUST NOT assume queue state is preserved across reset
- Queue memory MAY be different after re-enable

---

## 6. Error Handling — Edge Cases

### DEVICE_NEEDS_RESET
- Device SHOULD set bit 64 when entering unrecoverable error state
- If DRIVER_OK is set, device MUST send configuration change notification
- Driver SHOULD NOT rely on completion of in-flight operations
- Driver CANNOT determine whether in-flight requests completed or not
- This creates an ambiguous state — driver must handle both completed and uncompleted requests

### Descriptor Exhaustion
- When descriptor table is full, driver MUST wait for device to return descriptors via used ring
- Driver MUST NOT overwrite in-use descriptors
- Virtio has no backlog mechanism (unlike io_uring) — queue depth is hard-limited by descriptor table size

### Memory Ordering Failures
- Missing memory barriers between descriptor writes and index updates can cause device to process stale or partial descriptors
- This is a common source of subtle bugs — barrier must be between EVERY descriptor write and its corresponding index update
- ARM and other weakly-ordered architectures are most affected

---

## 7. Configuration Space — Access Requirements

- All multi-byte fields are LITTLE-ENDIAN
- 8-bit fields require exactly 8-bit wide access
- 16-bit fields require 16-bit aligned, 16-bit wide access
- 32-bit fields require 32-bit aligned, 32-bit wide access
- 64-bit fields require 32-bit aligned access (two 32-bit reads)
- Misaligned access is UNDEFINED BEHAVIOR on some transports

### MMIO-Specific
- Magic value at offset 0: MUST be 0x74726976 ("virt" in little-endian)
- Version at offset 4: MUST be 0x2 for modern devices
- DeviceID at offset 8: 0x0 is invalid (no device present)
- VendorID at offset 12: device-specific

---

## 8. DMA and Memory Access — Platform Contracts

### Without VIRTIO_F_IOMMU_PLATFORM
- Device accesses memory directly using physical addresses
- No IOMMU translation
- Simple but insecure — device can access any guest memory

### With VIRTIO_F_IOMMU_PLATFORM
- Device MUST use platform DMA API for all memory access
- Driver MUST provide DMA-mapped addresses, not physical addresses
- All virtqueue memory MUST be DMA-mapped before device access
- This includes descriptor table, available ring, used ring, and all data buffers

### Xen Grant Table Variant
- Uses VIRTIO_F_ACCESS_PLATFORM instead
- Restricts backend to only explicitly granted pages
- Requires 64-bit address support in virtqueues
- Special 64-bit DMA addresses encode grant references

---

## 9. Known Spec Ambiguities and Implementation Divergences

### Interrupt Coalescing
- Spec does not define mandatory interrupt coalescing behavior
- Implementations vary: some batch aggressively, some notify per-completion
- VIRTIO_F_EVENT_IDX provides the mechanism but not the policy

### Descriptor Ordering
- Spec requires available ring entries in order, but used ring entries may be out of order
- Some implementations assume in-order completion (violation of spec)
- Out-of-order completion is especially important for storage devices

### Legacy vs Modern Feature Interaction
- Some features have different semantics in legacy vs modern mode
- Byte ordering changes between legacy (native-endian) and modern (little-endian)
- Some drivers don't properly handle the transition
- VIRTIO_F_VERSION_1 is the discriminator but not all paths check it

### Queue Size Negotiation
- Device advertises maximum queue size
- Driver can request smaller size
- Driver MUST NOT request larger than advertised
- Some implementations don't properly validate driver-requested sizes
