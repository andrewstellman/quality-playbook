# Quality Playbook — Artifact Index (Linux virtio)

> v1.5.8 · linux-virtio @ bfe62a454542 · last updated 2026-06-19 (Phase 3 complete)

## Phase status
- [x] Phase 1 — Explore
- [x] Phase 2 — Generate
- [x] Phase 3 — Code Review + Regression Tests  ← current
- [ ] Phase 4 — Spec Audit
- [ ] Phase 5 — Reconciliation
- [ ] Phase 6 — Verify

## Phase 3 result: 3 confirmed bugs (all MEDIUM), 3 candidates rejected

| BUG | Severity | File:line | Regression test | Fix patch |
|-----|----------|-----------|-----------------|-----------|
| BUG-001 NOTIF_CONFIG_DATA(39) stripped on PCI-modern | MEDIUM | virtio_pci_modern.c:367-381 | test_bug001_pci_compensator_readds_notif_config_data | patches/BUG-001-fix.patch |
| BUG-002 vp_interrupt IRQ_NONE for config-only | MEDIUM | virtio_pci_common.c:120-123 | test_bug002_vp_interrupt_returns_handled_on_config | patches/BUG-002-fix.patch |
| BUG-003 vm_reset omits §5 status poll | MEDIUM | virtio_mmio.c:251-257 | test_bug003_vm_reset_polls_for_status_zero | patches/BUG-003-fix.patch |

Rejected: candidate #1 (demoted — unreachable/out-of-scope), #5 (barriers present), #6 (queue-size bounded).

## Key artifacts
- quality/BUGS.md — confirmed bugs (### BUG-NNN, severity/divergence_type/reachability_analysis/Covers)
- quality/bugs_manifest.json — 3 bug records (no CVEs; all reachability_analysis present)
- quality/compensation_grid.json + compensation_grid_downgrades.json — REQ-001/002/003/004 grids (union self-check PASS)
- quality/test_regression.py — 3 strict-xfail source-inspection tests (RED on source, GREEN after fixes)
- quality/patches/BUG-00{1,2,3}-{regression-test,fix}.patch — all 6 validated
- quality/code_reviews/2026-06-19-phase3-reviewer.md — 3-pass review (verdict: FIX BEFORE MERGE)
- quality/PROGRESS.md — phase tracker + cumulative BUG tracker
