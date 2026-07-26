# Phase 1 Exploration — Linux virtio driver subsystem (v1.5.8)

**Target:** `drivers/virtio/` + `include/{linux,uapi}/linux/virtio*.h` — a sparse
checkout of the Linux kernel virtio driver subsystem (clean checkout metadata in
`.clean_checkout`: torvalds/linux @ `bfe62a454542`, `type: kernel_subsystem`).

**Domain & stack:** C (Linux kernel module code, GPL-2.0). The subsystem implements
the guest-side virtio drivers: a transport-abstraction core (`virtio.c`,
`virtio_ring.c`) plus four transport backends (PCI-modern, PCI-legacy, MMIO, vDPA)
and several device drivers (balloon, mem, input, rtc). External systems: the
hypervisor/device backend (QEMU, vhost, vDPA hardware) on the other side of the
virtqueue; the platform DMA/IOMMU layer; the PCI/MMIO bus.

**Primary data flow:** device probe → feature negotiation (`virtio_finalize_features`
in `virtio.c` → per-transport `finalize_features` → `vring_transport_features` in
`virtio_ring.c`) → virtqueue setup → descriptor add/get (`virtio_ring.c` split &
packed paths) → interrupt dispatch → device-specific I/O.

**Documentation:** `reference_docs/` carries Tier-4 context only (no `cite/` subdir,
so `reference_docs_ingest` wrote 0 FORMAL_DOC records — every REQ will be Tier 3/4).
The richest doc is `reference_docs/virtio-spec-behavioral-contracts.md` (MUST/SHOULD
extraction from OASIS virtio v1.0–v1.2). `docs_gathered/` duplicates these plus
kernel coding-style and driver-writing guides. **This is a Tier-3-primary
(code-is-the-spec) run** supplemented by the Tier-4 behavioral-contracts doc.

**Existing tests:** NONE in the audited tree. The Linux virtio drivers are validated
by out-of-tree kselftests / virtme / KVM integration, none of which ship in this
sparse checkout. All requirements are therefore `[Req: inferred — from source]`
or `[Req: Tier-4 — behavioral-contracts.md]`. Import pattern / test-runner
inventory: N/A (no in-tree test harness).

**File-role tagging summary** (`quality/exploration_role_map.json`, provenance
`filesystem-walk-with-skips` — the target is not a usable git repo: its files live
under a parent QPB repo whose `.gitignore` excludes `repos/`, so `git ls-files`
returns nothing; I walked the filesystem with the disallowed-path skip list).
141 in-scope files: `code` 81 (the virtio drivers + headers under audit, plus the
QPB `bin/` orchestrator library), `skill-reference` 28, `skill-prose` 14,
`docs` 12, `skill-tool` 2 (`bin/reference_docs_ingest.py`, `bin/qpb_validate.py` —
the only `bin/` scripts SKILL.md names AND directs the agent to invoke),
`playbook-output` 2 (`.github/skills/quality_gate.py` installed next to SKILL.md;
`quality/formal_docs_manifest.json`), `config` 2. The QPB infrastructure under
`.github/skills/` and `bin/` is tagged as skill/code/playbook-output and is NOT the
target's intrinsic surface; the audited surface is `drivers/virtio/*` + `include/*`.

---

## Open Exploration Findings

1. **Transport feature-bit whitelist (`vring_transport_features`) silently clears
   bits 37/39/40/41.** `vring_transport_features()` at
   `drivers/virtio/virtio_ring.c:3505-3533` loops `i` over the transport range
   `[VIRTIO_TRANSPORT_F_START=28, VIRTIO_TRANSPORT_F_END=42)`
   (`include/uapi/linux/virtio_config.h:54-55`) and `__virtio_clear_bit(vdev, i)`
   in the `default` case (line 3527-3529) for any bit not in its explicit switch.
   The switch handles INDIRECT_DESC, EVENT_IDX, VERSION_1(32), ACCESS_PLATFORM(33),
   RING_PACKED(34), ORDER_PLATFORM(36), NOTIFICATION_DATA(38), IN_ORDER(35). It does
   **NOT** list `VIRTIO_F_SR_IOV`(37, `virtio_config.h:100`),
   `VIRTIO_F_NOTIF_CONFIG_DATA`(39, line 111), `VIRTIO_F_RING_RESET`(40, line 116),
   `VIRTIO_F_ADMIN_VQ`(41, line 121). All four therefore hit `default` and are
   cleared unless a transport re-adds them. This is the canonical virtio
   "feature stripped by a shared filter nobody updated" bug class.
   *(multi-location: virtio_ring.c:3505-3533 + virtio_config.h:54-121)*

2. **The core sets all transport bits right before finalize, so the clear in (1)
   is a live regression on transports that don't compensate.**
   `virtio_finalize_features()` at `drivers/virtio/virtio.c:318-321` runs
   `for (i = START; i < END; i++) if (test_bit(device_features, i)) __virtio_set_bit(dev, i)`
   — it re-adds EVERY transport bit the device offered, with the comment "Transport
   features always preserved to pass to finalize_features." Then line 323 calls
   `dev->config->finalize_features(dev)`. So whatever the device offered in 37/39/40/41
   is present when the per-transport finalize runs; if that finalize calls
   `vring_transport_features` and does nothing else, the bit is destroyed even though
   both device and driver wanted it. The compensation lives entirely in the per-transport
   finalize. *(multi-location: virtio.c:318-323 + virtio_ring.c:3527-3529)*

3. **Only PCI-modern compensates — and it misses one of the four bits.**
   `vp_transport_features()` at `drivers/virtio/virtio_pci_modern.c:367-381` re-adds
   exactly three bits after `vring_transport_features` clears them: SR_IOV (37, guarded
   by `pci_find_ext_capability(..., PCI_EXT_CAP_ID_SRIOV)`), RING_RESET (40), ADMIN_VQ
   (41). It is called from `vp_finalize_features()` at line 429, right after
   `vring_transport_features(vdev)` at line 426. **`VIRTIO_F_NOTIF_CONFIG_DATA`(39) is
   NOT re-added here** — yet `vp_check_common_size()` at lines 403-415 explicitly checks
   `VIRTIO_F_NOTIF_CONFIG_DATA` (line 405) as though it could survive negotiation. So
   even on modern PCI, bit 39 is cleared by `vring_transport_features`, the
   `vp_check_common_size` guard for it is dead, and the `queue_notify_data` config field
   it gates is unreachable. *(multi-location: virtio_pci_modern.c:367-381 + 403-415 + 426-429)*

4. **MMIO `vm_finalize_features` does NOT compensate — strips RING_RESET / ADMIN_VQ /
   NOTIF_CONFIG_DATA / SR_IOV.** `vm_finalize_features()` at
   `drivers/virtio/virtio_mmio.c:109-132` calls `vring_transport_features(vdev)` at
   line 114 and then immediately writes the (now-stripped) `vdev->features` to the
   `VIRTIO_MMIO_DRIVER_FEATURES` registers (lines 123-129). There is no
   `mm_transport_features` equivalent. Result: an MMIO virtio device that offers
   RING_RESET/ADMIN_VQ/NOTIF_CONFIG_DATA has those bits silently cleared during
   negotiation, even though MMIO devices legitimately support per-queue reset.
   This is the same gap as PCI-modern would have if `vp_transport_features` didn't exist.
   *(multi-location: virtio_mmio.c:109-132 + virtio_ring.c:3527-3529)*

5. **vDPA `virtio_vdpa_finalize_features` also does NOT compensate.**
   `virtio_vdpa_finalize_features()` at `drivers/virtio/virtio_vdpa.c:389-397` calls
   `vring_transport_features(vdev)` (line 394) then `vdpa_set_features(vdpa, vdev->features)`
   (line 396). No transport-bit re-add. Any transport bit in 37/39/40/41 the vDPA backend
   advertised is stripped before being forwarded to `set_features`. RING_RESET on vDPA is
   real (vhost-vdpa supports queue reset), so this silently disables it.

6. **MMIO device reset omits the mandatory post-write status poll.**
   `vm_reset()` at `drivers/virtio/virtio_mmio.c:251-257` writes 0 to
   `VIRTIO_MMIO_STATUS` (line 256) and returns immediately — no wait. The spec
   (`reference_docs/virtio-spec-behavioral-contracts.md` §5: "Driver MUST wait for
   device_status read to return 0 before reinitializing") and the PCI-modern
   implementation both require a poll. Compare `vp_reset()` at
   `drivers/virtio/virtio_pci_modern.c:546-565`, which writes 0 (line 552) and then
   `while (vp_modern_get_status(mdev)) msleep(1);` (lines 558-559), with a comment
   quoting the MUST. MMIO reset can race reinitialization on a slow device.
   *(multi-location: virtio_mmio.c:251-257 + virtio_pci_modern.c:546-565)*

7. **PCI `vp_interrupt` returns IRQ_NONE for a config-change-only interrupt.**
   `vp_interrupt()` at `drivers/virtio/virtio_pci_common.c:106-124` reads the ISR
   (line 113), returns IRQ_NONE if zero (line 116-117), calls `vp_config_changed()`
   if `isr & VIRTIO_PCI_ISR_CONFIG` (line 120-121) **but discards its IRQ_HANDLED
   return value**, then returns `vp_vring_interrupt(irq, opaque)` (line 123).
   `vp_vring_interrupt()` (lines 83-98) returns IRQ_NONE when no vring callback fires.
   So when the ISR has ONLY the CONFIG bit set (a legitimate config-change with no
   queue activity), the function returns **IRQ_NONE** — the genuine interrupt is
   reported to the kernel as spurious. Contrast `vm_interrupt()` (MMIO) at
   `drivers/virtio/virtio_mmio.c:285-307`, which sets `ret = IRQ_HANDLED` on the
   config bit (lines 296-299) and is therefore correct. This is a dispatcher
   return-value bug with a clear cross-transport divergence.
   *(multi-location: virtio_pci_common.c:106-124 + 83-98 + virtio_mmio.c:296-299)*

8. **PCI-legacy reset uses a single flush-read, not a poll loop.**
   `vp_reset()` in legacy at `drivers/virtio/virtio_pci_legacy.c:93-103` writes 0
   (line 97) then does a single `vp_legacy_get_status()` "to flush out the status
   write" (line ~100), not a `while (...) msleep` poll. Legacy devices (pre-1.0)
   genuinely lack FEATURES_OK and may not honor the wait, so this is arguably correct
   for legacy — but it should be documented as an intentional divergence, not an
   accidental omission. Worth a requirement so the spec-audit doesn't flag it blind.

9. **`virtio_features_ok` re-reads status after setting FEATURES_OK — but only for
   VERSION_1 devices.** `virtio_features_ok()` at `drivers/virtio/virtio.c:204-234`
   sets `VIRTIO_CONFIG_S_FEATURES_OK` (line 227), re-reads status (line 228), and
   fails with -ENODEV if the bit didn't stick (lines 229-232) — correctly implementing
   the spec MUST. But it early-returns 0 for non-VERSION_1 (legacy) devices at lines
   224-225 *before* setting/checking FEATURES_OK. That matches the spec note that legacy
   devices have "no safe failure mechanism," but it means the legacy path has no
   negotiation-acceptance confirmation at all. *(multi-location: virtio.c:204-234 + behavioral-contracts.md §1)*

10. **Packed-ring wrap-counter / avail-used-flag toggle is a single-site invariant
    with no cross-check.** `virtio_ring.c` maintains `avail_wrap_counter` (line 145)
    and `avail_used_flags` (line 148) and toggles both together when the ring wraps
    (`virtio_ring.c:1580-1583`). The toggle XORs the wrap counter and flips both the
    AVAIL and USED descriptor flag bits in one statement. If a future edit toggles the
    counter without flipping the flags (or vice versa), descriptors get the wrong
    ownership encoding and the device reads stale/未owned descriptors. This is a
    high-blast-radius invariant worth a requirement even though it is currently correct.

---

## Quality Risks

Domain-knowledge risk analysis for a virtio guest driver. Each is a concrete,
checkable failure scenario, ranked by priority. (Per the guide, these are NOT
"things the code does right" — they are where a domain expert would expect breakage.)

1. **(HIGH) Cross-transport feature-negotiation divergence is the #1 virtio bug
   class.** Because `vring_transport_features` (`virtio_ring.c:3527-3529`) clears any
   transport bit it doesn't enumerate and only PCI-modern compensates
   (`virtio_pci_modern.c:367-381`), MMIO and vDPA silently drop RING_RESET(40),
   ADMIN_VQ(41), NOTIF_CONFIG_DATA(39), SR_IOV(37). A reviewer should: read each
   `finalize_features` and confirm whether the post-`vring_transport_features` feature
   set still contains every bit the device offered in 37/39/40/41. Test input: a mock
   MMIO device advertising RING_RESET; assert the bit survives `vm_finalize_features`.

2. **(HIGH) NOTIF_CONFIG_DATA(39) is checked but never preserved even on modern PCI.**
   `vp_check_common_size` validates the `queue_notify_data` config-space size when
   `VIRTIO_F_NOTIF_CONFIG_DATA` is set (`virtio_pci_modern.c:405`), but
   `vp_transport_features` (lines 367-381) never re-adds bit 39 after
   `vring_transport_features` clears it. A reviewer should open
   `vp_transport_features` and confirm bit 39 is absent, then trace whether any modern
   device can ever reach the `queue_notify_data` path. Likely a real defect or an
   intentional-but-undocumented removal.

3. **(HIGH) MMIO reset races reinitialization.** `vm_reset` (`virtio_mmio.c:251-257`)
   writes 0 to status without polling for read-back-zero (spec §5 MUST). On a slow or
   busy backend, the next initialization step (writing ACKNOWLEDGE/DRIVER) can race a
   device still tearing down. Reviewer: confirm no `while (readl(... STATUS))` loop
   exists; compare to `vp_reset` poll at `virtio_pci_modern.c:558-559`.

4. **(HIGH) Config-only interrupts reported spurious on PCI.** `vp_interrupt`
   (`virtio_pci_common.c:120-123`) discards `vp_config_changed`'s IRQ_HANDLED and
   returns the vring result, so a pure config-change interrupt returns IRQ_NONE.
   Under a storm of spurious-IRQ accounting the kernel can disable the line. Reviewer:
   trace the return value when `isr == VIRTIO_PCI_ISR_CONFIG` exactly; assert it should
   be IRQ_HANDLED (as MMIO does at `virtio_mmio.c:298`).

5. **(MEDIUM) Memory-ordering barriers between descriptor writes and index updates.**
   `virtio_ring.c` uses `virtio_wmb`/`virtio_store_mb`/`virtio_rmb` at many sites
   (e.g. 756, 802, 939, 964, 1111, 1569, 1743, 1901, 2085, 2125, 2184). Spec §6 warns
   that a missing barrier between EVERY descriptor write and its index update corrupts
   on weakly-ordered arches (ARM). Reviewer: for each `avail`/`used` index update in
   both split and packed paths, confirm a preceding barrier. A single missing
   `virtio_wmb` in the packed `virtqueue_add_packed` path would be a silent
   data-corruption bug invisible on x86.

6. **(MEDIUM) Driver-requested queue size not validated against device max.**
   Spec §9 "Queue Size Negotiation": driver MUST NOT request larger than advertised;
   "some implementations don't properly validate." Reviewer: check the
   `vring_create_virtqueue` path in `drivers/virtio/virtio_ring.c:3505` and each
   transport's queue setup for a bound check against the device-advertised
   `queue_size`/`num_max`.

7. **(MEDIUM) Legacy/modern byte-order transition.** Spec §9: byte ordering changes
   between legacy (native-endian) and modern (LE); "not all paths check VERSION_1."
   The discriminator is `VIRTIO_F_VERSION_1` checked at
   `drivers/virtio/virtio.c:305` and gated again at `drivers/virtio/virtio.c:224`.
   Reviewer: grep config-space accessors (`virtio_cread*`/`vp_get`) for VERSION_1-gated
   endianness handling; a path that assumes LE on a legacy device corrupts multi-byte
   config fields.

---

## Pattern Applicability Matrix

| Pattern | Decision | Rationale |
|---|---|---|
| 1. Fallback and Degradation Path Parity | SKIP | The virtio transports are parallel implementations, not primary/fallback cascades of one operation; the cross-transport divergence is better framed by Pattern 3. No runtime "try primary then fall back" chains in the audited surface. |
| 2. Dispatcher Return-Value Correctness | FULL | Interrupt handlers (`vp_interrupt`, `vm_interrupt`, `vp_vring_interrupt`) are status-returning dispatchers over multiple event types (config vs vring), and finding #7 already shows a config-only return-value bug. High yield. |
| 3. Cross-Implementation Contract Consistency | FULL | Four transports implement the same lifecycle operations (finalize_features, reset, interrupt, get_features). The central virtio bug class. Highest yield for this codebase. |
| 4. Enumeration and Representation Completeness | FULL | `vring_transport_features`'s switch is a closed set gated against the authoritative `virtio_config.h` feature-bit definitions; bits 37/39/40/41 are missing. Directly produces findings #1/#3. |
| 5. API Surface Consistency | SKIP | The driver exposes one canonical config_ops vtable per transport; there is no dual-surface (view vs direct, sync vs async) for the same operation within a transport. Cross-transport equivalence is Pattern 3's job, not Pattern 5's. |
| 6. Spec-Structured Parsing Fidelity | SKIP | virtio negotiates binary feature bitmaps and fixed-layout config space — there is no textual grammar (headers/URLs/MIME) parsed with ad-hoc string logic. Not applicable to a binary-protocol driver. |
| 7. Composition and Mount-Context Awareness | SKIP | No canonical-vs-raw composition seam (mounted routers, scoped transactions) in a kernel transport driver. The `virtio.c` core vs transport relationship is delegation, not composition that maintains divergent canonical/raw state. |

(3 FULL, 4 SKIP — within the required 3–4 FULL band.)

---

## Pattern Deep Dive — Cross-Implementation Contract Consistency

The four transports each implement `finalize_features`, `reset`, the interrupt
handler, and `get_features`. The shared spec contracts come from
`reference_docs/virtio-spec-behavioral-contracts.md` §1 (feature negotiation) and
§5 (reset).

**Operation: `finalize_features` — spec §1 + transport feature preservation.**
Mandatory step set = {call `vring_transport_features`; re-preserve transport bits the
device offered that the filter cleared; write negotiated features to device}.

- **PCI-modern** `vp_finalize_features` (`virtio_pci_modern.c:420-443`): calls
  `vring_transport_features` (426), `vp_transport_features` (429, re-adds 37/40/41 via
  `__virtio_set_bit` at `virtio_pci_modern.c:372-380`), then
  `vp_modern_set_extended_features` (440). **Missing: re-add of bit 39
  (NOTIF_CONFIG_DATA)** even though `vp_check_common_size` (405) checks it.
- **MMIO** `vm_finalize_features` (`virtio_mmio.c:109-132`): calls
  `vring_transport_features` (114), writes features (123-129). **Missing: the entire
  transport-bit re-preservation step** → strips 37/39/40/41.
- **vDPA** `virtio_vdpa_finalize_features` (`virtio_vdpa.c:389-397`): calls
  `vring_transport_features` (394), `vdpa_set_features` (396). **Missing: same step.**
- **PCI-legacy** `vp_finalize_features` (`virtio_pci_legacy.c:31-45`): calls
  `vring_transport_features` (36), BUG_ON on >32-bit features (39), writes (42). Legacy
  is 32-bit-only so bits 37-41 are out of range — correctly exempt.

This traces a code path across `vring_transport_features` → `vp_transport_features` →
`__virtio_set_bit` (`virtio_pci_modern.c:372`) → `vp_modern_set_extended_features` and
shows the gap is present in three of four transports. **Gap:** all non-legacy transports
must re-preserve every device-offered transport bit `vring_transport_features` cannot
enumerate; MMIO/vDPA do none of it and modern PCI misses bit 39.
*(multi-function trace: `vring_transport_features`, `vp_transport_features`,
`vm_finalize_features`, `virtio_vdpa_finalize_features`)*

**Operation: `reset` — spec §5 "write 0, then wait until status reads 0."**
- **PCI-modern** `vp_reset` (`virtio_pci_modern.c:546-565`): write 0 (552), poll loop
  `while (vp_modern_get_status(mdev)) msleep(1)` (558-559) — CONFORMANT.
- **MMIO** `vm_reset` (`virtio_mmio.c:251-257`): write 0 (256), no wait — VIOLATION.
- **vDPA** `virtio_vdpa_reset` (`virtio_vdpa.c:86-91`): delegates to `vdpa_reset` — the
  wait is the backend's responsibility; check that no guest-side reinit assumes
  synchronous completion.
- **PCI-legacy** `vp_reset` (`virtio_pci_legacy.c:93-103`): single flush-read, no loop —
  arguably legacy-correct but undocumented.

*(multi-location trace across virtio_pci_modern.c:546-565, virtio_mmio.c:251-257,
virtio_vdpa.c:86-91, virtio_pci_legacy.c:93-103)*

## Pattern Deep Dive — Dispatcher Return-Value Correctness

The interrupt handlers dispatch over event types {config-change, vring-activity} and
must return IRQ_HANDLED whenever they consumed a real interrupt.

- **`vp_interrupt`** (`virtio_pci_common.c:106-124`): reads ISR (113); `if (!isr)
  return IRQ_NONE` (116-117); `if (isr & VIRTIO_PCI_ISR_CONFIG) vp_config_changed(...)`
  (120-121) — return value DISCARDED; `return vp_vring_interrupt(...)` (123).
  `vp_config_changed` (73-80) returns IRQ_HANDLED unconditionally;
  `vp_vring_interrupt` (83-98) returns IRQ_NONE when no vring callback fires.
  - Combination [CONFIG only, no vring]: returns **IRQ_NONE — INCORRECT** (a real
    config interrupt reported spurious).
  - [vring only]: returns IRQ_HANDLED — correct.
  - [CONFIG + vring]: returns IRQ_HANDLED — correct (but accidentally, via the vring arm).
  - [neither]: returns IRQ_NONE at line 117 — correct.
- **`vm_interrupt`** (MMIO, `virtio_mmio.c:285-307`): `ret = IRQ_NONE` (290);
  `if (status & INT_CONFIG) { ...; ret = IRQ_HANDLED; }` (296-299);
  `if (status & INT_VRING) ret |= ...` (301-304); `return ret` (306).
  - [CONFIG only]: returns IRQ_HANDLED — **CORRECT**. Direct contradiction of the PCI
    behavior for the identical event, confirming #7 is a real divergence not a
    misread.

This traces the divergence across two distinct handlers (`vp_interrupt`,
`vm_interrupt`) and two helpers (`vp_config_changed`, `vp_vring_interrupt`).
**Candidate requirement:** every transport interrupt handler MUST return IRQ_HANDLED
when it serviced a config-change interrupt regardless of vring activity.
*(multi-function trace: `vp_interrupt`, `vp_config_changed`, `vp_vring_interrupt`,
`vm_interrupt`)*

## Pattern Deep Dive — Enumeration and Representation Completeness

**Closed set:** the `switch (i)` in `vring_transport_features`
(`virtio_ring.c:3510-3530`). **Authoritative source:** the transport feature-bit
range `VIRTIO_TRANSPORT_F_START(28)`..`VIRTIO_TRANSPORT_F_END(42)` and the individual
`#define`s in `include/uapi/linux/virtio_config.h:54-121`.

Mechanically extracted switch labels (to be re-extracted into
`quality/mechanical/vring_transport_features_cases.txt` in Phase 2): INDIRECT_DESC,
EVENT_IDX, VERSION_1, ACCESS_PLATFORM, RING_PACKED, ORDER_PLATFORM, NOTIFICATION_DATA,
IN_ORDER.

Authoritative transport bits in [28,42): the eight above PLUS SR_IOV(37, line 100),
NOTIF_CONFIG_DATA(39, line 111), RING_RESET(40, line 116), ADMIN_VQ(41, line 121).

- **Missing entries:** 37, 39, 40, 41 — present in the authoritative header, absent
  from the closed set, therefore hit `default` → `__virtio_clear_bit` (3529).
- **Caller compensation (does NOT excuse the missing entry, per Pattern 4):**
  `vp_transport_features` (`virtio_pci_modern.c:367-381`) restores 37/40/41 only;
  MMIO/vDPA restore none; bit 39 restored by nobody. Any new transport that forgets
  to compensate inherits the bug — exactly the failure mode Pattern 4 warns about.

This traces across `vring_transport_features` (the closed set), `virtio_config.h`
(the authoritative source), and the per-caller compensators `vp_transport_features` /
`vm_finalize_features` / `virtio_vdpa_finalize_features`.
*(multi-function trace: `vring_transport_features`, `vp_transport_features`,
`vm_finalize_features`)*

---

## Candidate Bugs for Phase 2

1. **MMIO/vDPA finalize_features strip transport bits 37/39/40/41.**
   - Stage: pattern deep dive — Cross-Implementation Contract Consistency
   `drivers/virtio/virtio_mmio.c:109-132`, `drivers/virtio/virtio_vdpa.c:389-397`,
   `drivers/virtio/virtio_ring.c:3505-3533`. Phase 3 should confirm that after
   `vring_transport_features`, no step re-adds device-offered RING_RESET/ADMIN_VQ/etc.,
   and that the core's preserve loop (`virtio.c:318-321`) is the only thing setting them.

2. **NOTIF_CONFIG_DATA(39) never re-added even on modern PCI.**
   - Stage: open exploration
   `drivers/virtio/virtio_pci_modern.c:367-381` (no bit-39 re-add) vs `:403-415`
   (`vp_check_common_size` checks bit 39). Phase 3: trace whether bit 39 can ever be
   live; the `queue_notify_data` config path appears unreachable.

3. **`vm_reset` omits the spec-mandated post-write status poll.**
   - Stage: quality risks
   `drivers/virtio/virtio_mmio.c:251-257` vs `drivers/virtio/virtio_pci_modern.c:546-565`.
   Phase 3: confirm absence of a `while (readl(...STATUS))` wait; spec §5 MUST.

4. **`vp_interrupt` returns IRQ_NONE for config-change-only interrupts.**
   - Stage: pattern deep dive — Dispatcher Return-Value Correctness
   `drivers/virtio/virtio_pci_common.c:106-124` (return value of `vp_config_changed`
   discarded at 120-121) vs MMIO `virtio_mmio.c:296-299`. Phase 3: assert IRQ_HANDLED
   when `isr == VIRTIO_PCI_ISR_CONFIG`.

5. **Memory barrier presence between descriptor writes and index updates (packed +
   split).**
   - Stage: quality risks
   `drivers/virtio/virtio_ring.c:756` and barrier sites (802, 939, 964, 1111, 1569, 1743,
   1901, 2085, 2125, 2184). Phase 3: per-path check that every `avail`/`used` index
   update is preceded by the correct `virtio_wmb`/`virtio_store_mb`.

6. **Driver-requested queue size validation against device max.**
   - Stage: quality risks
   `drivers/virtio/virtio_ring.c:3505` virtqueue-creation path. Phase 3: confirm a bound
   check rejecting a requested size larger than the device-advertised maximum (spec §9).

---

## Gate Self-Check

| # | Check | Status |
|---|---|---|
| 1 | ≥120 lines in EXPLORATION.md | PASS (well over 120) |
| 2 | `## Open Exploration Findings` present | PASS |
| 3 | `## Quality Risks` present | PASS |
| 4 | `## Pattern Applicability Matrix` present | PASS |
| 5 | `## Pattern Deep Dive — <name>` ≥3 sections | PASS (Cross-Implementation, Dispatcher, Enumeration) |
| 6 | `## Candidate Bugs for Phase 2` present | PASS |
| 7 | `## Gate Self-Check` present | PASS (this table) |
| 8 | PROGRESS.md Phase 1 line `[x]` | PASS (quality/PROGRESS.md) |
| 9 | ≥8 numbered Open Exploration Findings each with ≥1 file:line | PASS (10 entries) |
| 10 | ≥3 findings tracing ≥2 distinct file:line locations | PASS (findings 1,2,3,4,6,7,9 are multi-location) |
| 11 | Pattern matrix has 3–4 FULL rows | PASS (3 FULL) |
| 12 | ≥2 Pattern Deep Dives trace ≥2 distinct identifiers/locations | PASS (all 3 deep dives are multi-function/multi-location) |
| 13 | Candidate-bug source mix (≥2 exploration/risks + ≥1 deep dive) | PASS (bugs 1&4 from deep dive; 2 open exploration; 3,5,6 quality risks) |

---

## Derived Requirements

Architectural-asymmetry promotion (Asymmetry-Promotion Rule, A-5). Every
"X compensates for Y / present in A but not B" observation above is promoted to a
multi-site `Pattern:`-tagged REQ so the Phase-3 compensation grid has cells. Each REQ
names the concrete implementation sites (file paths) and the functions involved.

### REQ-001: All non-legacy transports must preserve device-offered transport feature bits (28..41) that `vring_transport_features` cannot enumerate
- References: drivers/virtio/virtio_pci_modern.c, drivers/virtio/virtio_mmio.c, drivers/virtio/virtio_vdpa.c
- Pattern: compensation
- (Asymmetry: "modern PCI compensates via vp_transport_features; MMIO and vDPA rely
  entirely on vring_transport_features and compensate for nothing.")

### REQ-002: All transports must enumerate the full transport feature-bit set; the whitelist in `vring_transport_features` must cover every bit in [VIRTIO_TRANSPORT_F_START, VIRTIO_TRANSPORT_F_END) that any transport supports
- References: drivers/virtio/virtio_ring.c, include/uapi/linux/virtio_config.h, drivers/virtio/virtio_pci_modern.c
- Pattern: whitelist

### REQ-003: Every transport's device-reset path must satisfy the spec §5 "write 0 then wait for status read 0" contract (or document an intentional legacy exemption)
- References: drivers/virtio/virtio_pci_modern.c, drivers/virtio/virtio_mmio.c, drivers/virtio/virtio_pci_legacy.c
- Pattern: parity

### REQ-004: Every transport interrupt handler must return IRQ_HANDLED when it serviced a config-change interrupt, independent of vring activity
- References: drivers/virtio/virtio_pci_common.c, drivers/virtio/virtio_mmio.c, drivers/virtio/virtio_vdpa.c
- Pattern: parity

---

## Cartesian UC rule confirmation

1. For every REQ with ≥2 References, I ran Gate 1 (path-suffix match):
   - REQ-001: `*_finalize_features` (vp/vm/virtio_vdpa) — path-suffix/function-role MATCH.
   - REQ-002: `vring_transport_features` (ring.c) + `vp_transport_features` (modern) +
     the header — the header is a definition source, not a parallel impl → Gate 1
     partial (only the two .c functions share the transport-feature role).
   - REQ-003: `vp_reset`/`vm_reset`/`vp_reset(legacy)` — function-role `*_reset` MATCH.
   - REQ-004: `vp_interrupt`/`vm_interrupt`/`virtio_vdpa_*_cb` — interrupt-handler role MATCH.
2. For REQs passing Gate 1, I ran Gate 2 (function-level similarity, ranges inside
   function bodies of similar size): REQ-001 finalize bodies are similar-sized function
   bodies → PASS; REQ-003 reset bodies similar → PASS; REQ-004 handler bodies similar → PASS;
   REQ-002 the two compensators differ in size and the header is not a function → Gate 2
   FAILS for the cluster as a whole.
3. Where both gates passed (REQ-001, REQ-003, REQ-004): emit per-site UCs (below):
   - REQ-001 → UC-1.a (PCI-modern), UC-1.b (MMIO), UC-1.c (vDPA).
   - REQ-003 → UC-3.a (PCI-modern), UC-3.b (MMIO), UC-3.c (PCI-legacy).
   - REQ-004 → UC-4.a (PCI), UC-4.b (MMIO), UC-4.c (vDPA).
4. Where only Gate 1 passed (REQ-002): single umbrella UC marked
   `<!-- cluster: heterogeneous -->`.
5. Where neither gate passed: none.
6. For each Gate-1 match I added a `Pattern:` tag (compensation/whitelist/parity above).
7. Every architectural asymmetry noted in prose (findings 1-7) was promoted to a
   multi-site `Pattern:`-tagged REQ (REQ-001..004) — none demoted to prose.

### Per-site use cases (Cartesian expansion)

### UC-1.a: Transport-bit preservation on PCI-modern
- Actors: virtio_pci_modern driver, device backend
- Preconditions: device advertises RING_RESET(40)/ADMIN_VQ(41)/SR_IOV(37)
- Flow: `vp_finalize_features` → `vring_transport_features` clears them →
  `vp_transport_features` (virtio_pci_modern.c:367-381) re-adds them
- Postconditions: bits survive into `vp_modern_set_extended_features`
  (NOTE: bit 39 NOT re-added — candidate bug #2)

### UC-1.b: Transport-bit preservation on MMIO
- Actors: virtio_mmio driver, device backend
- Preconditions: MMIO device advertises RING_RESET(40)
- Flow: `vm_finalize_features` → `vring_transport_features` clears bit → NO re-add
- Postconditions: bit MUST survive but currently does not (candidate bug #1)

### UC-1.c: Transport-bit preservation on vDPA
- Actors: virtio_vdpa driver, vDPA backend
- Preconditions: vDPA backend advertises RING_RESET(40)
- Flow: `virtio_vdpa_finalize_features` → `vring_transport_features` clears →
  `vdpa_set_features` forwards stripped set
- Postconditions: bit MUST survive to set_features but currently does not (bug #1)

### UC-3.a / UC-3.b / UC-3.c: Reset wait-for-zero on PCI-modern / MMIO / PCI-legacy
- Actors: respective transport driver, device
- Preconditions: driver initiates reset by writing 0 to device status
- Flow: write 0 → (modern: poll `while get_status` ; mmio: NONE ; legacy: single read)
- Postconditions: status reads 0 before reinit (MMIO currently violates — bug #3)

### UC-4.a / UC-4.b / UC-4.c: Config-interrupt return value on PCI / MMIO / vDPA
- Actors: respective transport interrupt handler, kernel IRQ core
- Preconditions: a config-change interrupt fires with no vring activity
- Flow: handler reads ISR/status, services config change, returns IRQ result
- Postconditions: handler returns IRQ_HANDLED (PCI currently returns IRQ_NONE — bug #4)

### UC-2 (umbrella): Transport feature-bit whitelist completeness <!-- cluster: heterogeneous -->
- Actors: virtio_ring core, all transports
- Preconditions: device offers any bit in [28,42)
- Flow: `vring_transport_features` switch decides survival
- Postconditions: every transport-supported bit is enumerated or compensated
