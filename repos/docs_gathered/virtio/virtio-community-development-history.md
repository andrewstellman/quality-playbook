# virtio Community Development History

Compiled from LWN.net articles, OASIS specification documents, lore.kernel.org, Red Hat engineering blogs, and community documentation. This document captures design decisions, behavioral contracts, known edge cases, and specification requirements discussed in the Linux kernel and virtualization communities.

Sources: LWN.net (lwn.net/Articles/239238, 580186, 752745, 674285, 896938, 805235, 812055, 808235, 972314), OASIS specs (docs.oasis-open.org/virtio), lore.kernel.org, Red Hat blogs, Stefan Hajnoczi's blog (blog.vmsplice.net), Project ACRN docs, OSDev wiki.

---

## 1. Design Principles and Origin

### Original Vision (Rusty Russell, 2007)
Three guiding principles for virtio:
1. **Straightforward**: Devices use existing bus interfaces rather than proprietary hypervisor buses
2. **Efficient**: Batching and interrupt suppression are supported
3. **Extensible**: Feature negotiation allows both devices and drivers to declare capabilities

### Core Abstraction
Buffer abstraction based on scatterlists: buffers contain "out" entries (data sent to hypervisor) and "in" entries (returned data). Five core operations: add_buf(), sync(), get_buf(), detach_buf(), restart().

### OASIS Standardization
Virtio was standardized through OASIS to provide clear intellectual property frameworks. The standardization effort kept virtio's strengths while discarding problematic elements.

---

## 2. Specification Version Evolution

### Version 1.0 (March 2016) — First Standardized Version
- Added VIRTIO_F_VERSION_1 as mandatory feature bit to distinguish 1.0 devices
- Introduced FEATURES_OK bit for safer feature negotiation completion
- More flexible in-memory virtqueue layouts to prevent fragmentation
- Standardized on little-endian byte ordering
- Removed unused features (GSO support, barrier feature)

### Version 1.1 (April 2019) — Packed Ring Support
- Split virtqueues remained primary format
- Introduced Packed Virtqueues as alternative layout with improved cache efficiency
- All drivers/devices support either format or both

### Version 1.2 (July 2022) — Enhanced Functionality
- Added VIRTIO_F_RING_RESET for individual queue reset capability
- Improvements to DMA handling and error recovery

### Version 1.3 (Under development)
- Additional device types (virtio-rtc, virtio-spi)
- Further refinements to existing protocols

---

## 3. Virtqueue Design — Split Ring

### Three Memory Areas
1. **Descriptor Area**: Describes buffers, writable by driver only
2. **Available Ring (Driver Area)**: Data driver supplies to device
3. **Used Ring (Device Area)**: Data device returns to driver

Each area is writable by either driver or device, but NOT both. This separation is critical for cache coherence — prevents cache line contention between driver and device sides.

### Descriptor Table Constraints
- Size MUST be power of two for natural wrapping
- Index wrapping happens naturally: idx 1 references same entry as idx 257, 513 in a 256-entry ring
- Physical addresses of virtqueue parts MUST be multiples of specified alignment
- For VirtIO PCI, alignment is 4096 bytes
- Padding required between available and used rings to prevent cache line crossing

### Descriptor Chaining
- Descriptors can chain via `next` field for scatter-gather lists
- Single used descriptor corresponds to entire chain
- Only for available (device-writable) descriptors
- Drivers tend to avoid chaining when VIRTIO_F_RING_INDIRECT_DESC available

---

## 4. Virtqueue Design — Packed Ring (v1.1+)

### Design Motivation
Split ring has a critical performance limitation: the avail-used buffer cycle requires very sparse memory access patterns, causing poor cache utilization.

### How Packed Ring Differs
- Consolidates all three areas (descriptors, available, used) into one compact location
- Sequential data access fits better in CPU caches
- Reduces PCI transactions from consolidated layout
- Descriptor density avoids scattering data through memory

### Wrap Counter Mechanism
- Single-bit wrap counter distinguishes between empty and full ring states
- When descriptor index exceeds ring size, wraps to 0
- Counter toggled via XOR: `avail_wrap_counter ^= 1`
- Driver maintains internal wrap counter initialized to 1
- Counter flips each time last descriptor in ring becomes available

### Packed Descriptor Structure
Fields: addr, len, id, flags. The id field is opaque for the device, meaningful only to the driver.

---

## 5. Indirect Descriptors (VIRTIO_F_INDIRECT_DESC)

### Purpose
Allows driver to store a table of indirect descriptors anywhere in memory, effectively increasing ring capacity without increasing descriptor table size.

### Behavioral Constraints
- Main descriptor has VIRTQ_DESC_F_INDIRECT flag set
- Referred descriptor's addr and len point to indirect table
- Layout MUST match regular packed descriptors
- Buffers must come in order in indirect table
- ID field ignored in indirect table
- Only valid flag is VIRTQ_DESC_F_WRITE
- CANNOT chain indirect descriptors (no NEXT flag allowed)
- Maximum size limited to same count as main descriptor table

---

## 6. Feature Negotiation Protocol

### Negotiation Sequence
1. Driver reads device features via DeviceFeatures register
2. Driver negotiates which features it supports
3. Driver sets FEATURES_OK bit (0x8) to acknowledge negotiation complete
4. Driver re-reads device status to verify FEATURES_OK still set
5. If NOT set, device doesn't support the feature subset; device is UNUSABLE

### Legacy Device Limitation
- Pre-v1.0 devices don't support FEATURES_OK bit
- No graceful failure mechanism for unsupported feature combinations
- No clear negotiation completion signal
- Devices finalize features on first-use (dangerous)

### Standard Feature Bits
- **VIRTIO_F_VERSION_1**: Indicates virtio 1.0 spec support
- **VIRTIO_F_EVENT_IDX**: Device supports event index notification mechanism
- **VIRTIO_F_RING_INDIRECT_DESC**: Device supports indirect descriptors
- **VIRTIO_F_RING_RESET**: Device supports individual queue reset (v1.2+)
- **VIRTIO_F_IOMMU_PLATFORM**: Device supports DMA via IOMMU/grant tables
- **VIRTIO_F_ACCESS_PLATFORM**: Platform-specific memory access

### Error Recovery
- **DEVICE_NEEDS_RESET (bit 64)**: Device signals unrecoverable error state
- Device SHOULD set this when entering error state requiring reset
- If DRIVER_OK set, device MUST send device configuration change notification
- Driver SHOULD NOT rely on completion of operations when this is set
- Driver CANNOT assume whether requests were completed or not

---

## 7. Interrupt and Notification Mechanisms

### Method 1: Flags-Based Suppression (Basic)
- `flags` field in available ring: crude enable/disable mechanism
- flags = 1: Device should NOT send notification
- flags = 0: Device MUST send notification

### Method 2: Event Index (VIRTIO_F_EVENT_IDX — Preferred)
- More performant alternative to flags
- Driver specifies `used_event`: descriptor ID threshold before which device should NOT notify
- Instead of binary enable/disable, allows specifying progress threshold
- Device checks after writing index: if idx equals used_event, send notification; otherwise skip
- Enables more efficient batching

### Critical Reliability Note
- NEITHER suppression method is fully synchronized with device
- Both serve as useful OPTIMIZATIONS only
- Notifications can be dynamically enabled/disabled
- Devices/drivers can batch notifications or actively poll

---

## 8. Memory Ordering Requirements

### Mandatory Barriers
- Drivers MUST perform suitable memory barriers before AND after updating shared structures
- Driver MUST perform memory barrier before reading flags or avail_event to avoid missing notifications
- Critical for ensuring device sees updated descriptor tables and available rings
- Must ensure device sees most up-to-date copy before index updates

### Cache Coherence Considerations
- Virtio rings laid out specifically to avoid cache effects from both driver and device writing same cache lines
- Cache line alignment crucial for performance
- Latency of L3 cache access can more than double if L3 needs to fetch latest value from L1/L2 of another core
- Split ring: separate areas help manage cache line pressure
- Packed ring: consolidated layout for better cache efficiency

---

## 9. DMA API and Platform-Specific Access

### Historical Issue
Virtio devices bypassed IOMMUs completely, assuming address_space_memory during DMA emulation. This was a significant security and correctness problem.

### Linux Kernel Fix (2016, commit 8607f5c3)
- Converted virtio core API to properly use DMA API
- Introduced transport-specific helper to query DMA address space
- Enabled DMA address translation when VIRTIO_F_IOMMU_PLATFORM feature enabled

### Xen-Specific Security Vulnerability
- **Problem**: Backend could map arbitrary guest/Dom0 pages with foreign mapping
- **Solution**: Grant-table-based mapping that restricts backends to only explicitly granted pages
- Requirements: VIRTIO_F_ACCESS_PLATFORM and VIRTIO_F_VERSION_1
- CONFIG_XEN_VIRTIO=y needed for ARM + virtio-mmio
- Requires modern transport supporting 64-bit addresses in virtqueues
- Forms special 64-bit DMA address using grant references

### DMA API Rollout Strategy
- Enabled by default only on Xen PV x86
- Optional module configuration on other platforms
- Architecture-specific DMA implementations for s390, alpha, big-endian

---

## 10. Device Reset and Queue Teardown

### Device Reset Requirements
- Device MUST present 0 in queue_enable on reset
- After writing 0 to device_status, driver MUST wait for read of device_status to return 0 before reinitializing

### Queue Reset (VIRTIO_F_RING_RESET — v1.2+)
- Driver can reset individual virtqueue without full device reset
- Two-part process: (1) Driver disables virtqueue, (2) Driver may optionally re-enable
- Avoids full device reset when only one queue needs recovery

### Reset Notifications
- Device SHOULD set DEVICE_NEEDS_RESET when entering unrecoverable error state
- If DRIVER_OK set, device MUST send device configuration change notification after setting DEVICE_NEEDS_RESET
- Notification location found via VIRTIO_PCI_CAP_NOTIFY_CFG capability

---

## 11. Configuration Space and Device Discovery

### MMIO Configuration Registers
- Magic value: 0x74726976 ("virt" in little-endian)
- Device version: 0x2 for specification-compliant devices
- Subsystem Device ID must be non-zero (0x0 is invalid)
- Feature flags in 32-bit chunks, selected via DeviceFeaturesSel
- ISR Status field (8-bit, for INT#x interrupt handling)

### Configuration Access Requirements
- All 64-bit, 32-bit, 16-bit fields are little-endian
- 8-bit fields require 8-bit access
- 16-bit fields require 16-bit aligned access
- 32-bit and 64-bit fields require 32-bit aligned access

### PCI Device Identification
- Vendor ID: 0x1AF4 (Red Hat)
- Device IDs: 0x1000-0x107F range for virtio devices

---

## 12. Transport Layers

### Three Transport Types
1. **PCI/PCIe**: Most common, feature-rich. 161 files, 78K+ lines in Linux kernel.
2. **MMIO**: Lightweight alternative. 1 file, 538 lines. Preferred for lightweight VMMs.
3. **Channel I/O (CCW)**: For s390 architecture.

### MMIO Performance
- Originally limited to legacy interrupts only
- Recent enhancements added MSI support achieving PCI-equivalent performance
- With MSI: ~9,500 trans/s (matches virtio-PCI: 9,536-9,894 trans/s)
- Without MSI: 6,939-7,095 trans/s (significant penalty)

---

## 13. Vhost Architecture

### QEMU vs Vhost
- **QEMU virtio**: Full device emulation in userspace (QEMU process)
- **Vhost**: Backend moves to host kernel (vhost-net, vhost-blk, etc.)
- **Vhost-user**: Backend runs in userspace with vhost protocol

### Implementation
- Guest OS creates virtqueue, registered with hypervisor
- With kernel vhost, vhost kernel module directly handles I/O requests
- Data plane moved out of QEMU to kernel; control plane partially remains in QEMU
- Uses ioctl to exchange vhost messages between QEMU and kernel vhost
- irqfd/ioeventfd file descriptors for guest notifications
- Shared virtqueue between guest OS and host OS

### Benefits
- Reduced context switches vs pure QEMU emulation
- Direct kernel-level I/O request handling
- Better performance for high-throughput scenarios

---

## 14. Queue Design Comparisons (virtio vs NVMe vs io_uring)

Stefan Hajnoczi's comparative analysis reveals architectural tradeoffs:

### Data Embedding
- Virtio does NOT embed data in descriptors (due to layered architecture)
- NVMe and io_uring embed request structures in descriptors
- Impact: Reduces memory loads needed during request processing

### Descriptor Chaining
- Virtio supports chaining, but drivers avoid it when indirect descriptors available
- NVMe rejects chaining entirely
- Tradeoff: Chaining improves cache locality but creates variable queue depths

### In-Flight Request Limits
- Virtio: Restricted to descriptor table size (descriptors occupied until completion)
- NVMe: Limited to queue size
- io_uring: Allows more requests than queue size (includes backlog for overflow)

---

## 15. Hardware Implementations ("virtio without the virt")

### Three Hardware Approaches
1. **Full offloading**: Entire device passed to guests, hardware handles all operations
2. **vDPA (Virtual Data Path Acceleration)**: Vendor-specific drivers for control, hardware handles data paths
3. **vDPA Partitioning**: Flexible resource allocation through memory protection

### Benefits
- Existing guests work out of the box
- Seamless switching between hardware/software for debugging, optimization, live migration
- Hardware vendors reuse existing guest drivers (no proprietary interfaces needed)
- Virtio 1.1 spec defines optional features for selective hardware support

---

## 16. Key Maintainers and Community

### Primary Mailing Lists
- virtualization@lists.linux.dev (primary for virtio kernel changes)
- linux-kernel@vger.kernel.org (general kernel changes)
- virtio-dev@lists.oasis-open.org (specification discussion)

### OASIS Technical Committee
- GitHub repository: oasis-tcs/virtio-spec
- Issue tracking for spec clarifications and enhancements
- Maintains all official specification versions

### Key Contributors
- Rusty Russell: Original designer (2007)
- Michael S. Tsirkin (Red Hat): Long-time maintainer
- Jason Wang: virtio-net and vhost
- Stefan Hajnoczi: QEMU/virtio integration, virtio-fs
