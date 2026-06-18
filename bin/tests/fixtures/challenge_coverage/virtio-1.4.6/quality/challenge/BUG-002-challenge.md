# Challenge Gate — BUG-002

## Trigger patterns
- The expected behavior is derived from sibling-path IRQ semantics.
- Another code path handles the same concern differently.

## Round 1
- **Verdict:** REAL BUG
- **Rationale:** Once `vp_interrupt()` reads a non-zero ISR and calls `vp_config_changed()`, returning only `vp_vring_interrupt()` can report `IRQ_NONE` after real work was serviced.

## Round 2
- **Best maintainer argument:** Pure config-only INTx interrupts are rare in practice and MSI-X keeps config and queue handlers separate, so the fallback path rarely exposes the bug.
- **Final stance:** STILL REAL BUG — rarity does not justify returning `IRQ_NONE` for an interrupt the handler already claimed and serviced.

## Final verdict
**CONFIRMED.** BUG-002 survives the challenge gate and remains a real IRQ-accounting defect.
