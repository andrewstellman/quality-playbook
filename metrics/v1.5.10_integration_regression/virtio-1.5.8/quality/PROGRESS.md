# Quality Playbook Progress

Skill version: v1.5.8
Date: 2026-06-19

## Phase tracker

- [x] Phase 1 - Explore
- [x] Phase 2 - Generate (completed 2026-06-19T22:09Z)
- [x] Phase 3 - Code Review (completed 2026-06-19; 3 bugs confirmed, 3 candidates rejected)
- [ ] Phase 4 - Spec Audit
- [ ] Phase 5 - Reconciliation
- [ ] Phase 6 - Verify

## Run metadata

- Project: linux-virtio (sparse kernel subsystem checkout; torvalds/linux @ bfe62a454542)
- Runner: claude-code (Mode A, skill-direct), arunner subagent phase1
- Playbook version: v1.5.8
- Audited surface: drivers/virtio/*.c|*.h + include/{linux,uapi}/linux/virtio*.h
- QPB infrastructure (.github/skills/, bin/) is NOT part of the audited surface.

## Scale / scope declaration

- Source files under audit (excluding tests/docs/QPB infra): 22 driver .c/.h files
  (~17k LOC) + ~50 headers. Below the 200-file threshold → full exploration, no
  mandatory scope-narrowing declaration required.
- Core modules explored in depth: virtio_ring.c (feature whitelist + ring barriers),
  virtio.c (negotiation core), virtio_pci_modern.c, virtio_mmio.c, virtio_vdpa.c,
  virtio_pci_legacy.c, virtio_pci_common.c (interrupt dispatch).
- Device drivers (balloon, mem, input, rtc) surveyed for surface but not deep-dived;
  the highest-yield risk surface is the transport/negotiation layer.

## Documentation depth assessment

- reference_docs/ has NO cite/ subdir → reference_docs_ingest wrote 0 FORMAL_DOC
  records → this is a Tier-3-primary (code-is-the-spec) run.

| Document | Depth | Subsystem | Requirements commitment | If excluded: justification |
|---|---|---|---|---|
| reference_docs/virtio-spec-behavioral-contracts.md | Deep (MUST/SHOULD extraction) | Feature negotiation, virtqueue, reset, interrupts, DMA | Will cover in Phase 2 (Tier-4 context backing REQ-001..004) | — |
| reference_docs/writing_virtio_drivers.rst | Moderate | Driver authoring API | Orientation only | Not a contract source |
| reference_docs/virtio.rst | Moderate | Subsystem overview | Orientation only | Overview-level |
| reference_docs/linux-coding-style.rst | Shallow | Style | Excluded | Style guide, not behavioral spec |

## Mechanical verification

- APPLICABLE — `vring_transport_features` is a dispatch/whitelist function.
  `quality/mechanical/vring_transport_features_cases.txt` to be generated in Phase 2
  via `awk '/void vring_transport_features/,/^}$/' drivers/virtio/virtio_ring.c | grep -E '^\s*case\s+'`.

## Existing test inventory

- NONE in the audited tree (Linux virtio is validated by out-of-tree kselftests/KVM).
  All requirements are inferred-from-source or Tier-4-backed. No in-tree import pattern
  or test runner to mirror.

## Artifact inventory (Phase 1)

- quality/exploration_role_map.json (141 files, provenance filesystem-walk-with-skips, normalized + validated)
- quality/EXPLORATION.md
- quality/formal_docs_manifest.json (0 cite records)
- quality/PROGRESS.md (this file)
- quality/run_state.jsonl

## Artifact inventory (Phase 2 — generated 2026-06-19)

- quality/QUALITY.md — generated (quality constitution; 8 fitness-to-purpose scenarios)
- quality/CONTRACTS.md — generated (32 behavioral contracts, 7 core files)
- quality/REQUIREMENTS.md — generated (17 REQs: REQ-001..009 virtio behavior + REQ-010..017
  artifact-location; 11 use cases UC-1.a/b/c, UC-2, UC-3.a/b/c, UC-4.a/b/c, UC-5; Pattern tags
  compensation/whitelist/parity preserved from Phase 1)
- quality/requirements_manifest.json — generated (records wrapper, 17 REQ records, no Tier 1/2)
- quality/use_cases_manifest.json — generated (records wrapper, 11 UC records)
- quality/bugs_manifest.json — generated (records wrapper, empty — bugs confirmed in Phase 3/4/5)
- quality/COVERAGE_MATRIX.md — generated (32/32 contracts covered, 100%)
- quality/COMPLETENESS_REPORT.md — generated (baseline, verdict DEFERRED to Phase 5)
- quality/test_functional.py — generated (23 source-inspection tests: 18 pass, 5 xfail candidate
  bugs; 3 groups: spec requirements / fitness scenarios / boundaries)
- quality/RUN_CODE_REVIEW.md — generated (3-pass protocol with mechanical enumeration check)
- quality/RUN_INTEGRATION_TESTS.md — generated (per-UC groups; QEMU/KVM matrix documented,
  environment-skipped in this sparse checkout)
- quality/RUN_SPEC_AUDIT.md — generated (Council of Three, extract-don't-assert spot-checks)
- quality/RUN_TDD_TESTS.md — generated (red/green source-inspection TDD protocol)
- quality/mechanical/verify.py — generated AND executed (subprocess.run of original shell
  extraction; v1.3.23 invariant honored)
- quality/mechanical/vring_transport_features_cases.txt — generated receipt (8 case labels)
- quality/mechanical/virtio_config_transport_bits.txt — generated receipt (transport bits [28,42))

Mechanical receipt confirms bits 37/39/40/41 are NOT case labels in vring_transport_features —
they hit the default: clear branch, matching EXPLORATION.md findings 1-5.

## BUG tracker (cumulative)

Phase 3 (Code Review) confirmed 3 bugs and rejected 3 of the 6 Phase-1 candidates.

| BUG | Source | File:line | Severity | Description | Closure |
|-----|--------|-----------|----------|-------------|---------|
| BUG-001 | Code Review | virtio_pci_modern.c:367-381 / virtio_ring.c:3511-3529 | MEDIUM | NOTIF_CONFIG_DATA(39) cleared by whitelist, never re-added by PCI compensator though vp_check_common_size validates it | test_regression.py::test_bug001_pci_compensator_readds_notif_config_data + patches/BUG-001-fix.patch |
| BUG-002 | Code Review | virtio_pci_common.c:120-123 | MEDIUM | vp_interrupt discards vp_config_changed's IRQ_HANDLED; returns IRQ_NONE for a config-only interrupt | test_regression.py::test_bug002_vp_interrupt_returns_handled_on_config + patches/BUG-002-fix.patch |
| BUG-003 | Code Review | virtio_mmio.c:251-257 | MEDIUM | vm_reset writes 0 but omits the spec §5 wait-for-status-zero poll | test_regression.py::test_bug003_vm_reset_polls_for_status_zero + patches/BUG-003-fix.patch |

Rejected/demoted Phase-1 candidates:
- Candidate #1 (MMIO/vDPA strip RING_RESET/ADMIN_VQ/SR_IOV): DEMOTED — RING_RESET unusable
  (no disable_vq_and_reset/enable_vq_after_reset ops → virtqueue_reset returns -ENOENT);
  ADMIN_VQ/SR_IOV are PCI-only. Recorded as downgrade cells in compensation_grid_downgrades.json.
  The one reachable cell (NOTIF_CONFIG_DATA on PCI) became BUG-001.
- Candidate #5 (missing barriers): REJECTED — barriers present at every index-update site.
- Candidate #6 (queue-size unbounded): REJECTED — size is device-sourced + is_power_of_2 +
  num_max bound in resize.

All 3 fix patches and 3 regression-test patches validated; RED→GREEN confirmed by
filesystem-copy execution (driver source is untracked, so the git-worktree pattern is N/A).

## Artifact inventory (Phase 3 — generated 2026-06-19)

- quality/BUGS.md — 3 confirmed bugs (### BUG-NNN format), Covers/severity/divergence_type/reachability_analysis
- quality/bugs_manifest.json — 3 records (classification=bug, all with reachability_analysis; no CVEs)
- quality/compensation_grid.json — REQ-001/002/003/004 grids (BUG-default rule applied)
- quality/compensation_grid_downgrades.json — 11 downgrade records (all 5 fields, valid reason_class)
- quality/test_regression.py — 3 strict-xfail source-inspection regression tests
- quality/patches/BUG-00{1,2,3}-regression-test.patch — MANDATORY, validated apply+XFAIL
- quality/patches/BUG-00{1,2,3}-fix.patch — validated git apply --check + RED→GREEN
- quality/code_reviews/2026-06-19-phase3-reviewer.md — 3-pass review + combined summary (FIX BEFORE MERGE)
