# Challenge Gate — BUG-006

## Trigger patterns
- The expected behavior is derived from setup/teardown symmetry.
- The finding is about missing functionality that should mirror an existing setup action.

## Round 1
- **Verdict:** REAL BUG
- **Rationale:** `enable_irq_wake(irq)` in `vm_find_vqs()` has no matching `disable_irq_wake(irq)` before `free_irq()`, including the error-unwind path.

## Round 2
- **Best maintainer argument:** Platform-device teardown may make the missing wake-disable hard to observe on systems that never rebind or hot-unplug the device.
- **Final stance:** STILL REAL BUG — the error-cleanup path is real, and the kernel wake-depth state is not safely unwound by `free_irq()` alone.

## Final verdict
**CONFIRMED.** BUG-006 survives the challenge gate and remains a real IRQ-wake symmetry defect.
