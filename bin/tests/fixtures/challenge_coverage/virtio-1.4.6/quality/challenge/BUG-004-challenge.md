# Challenge Gate — BUG-004

## Trigger patterns
- The expected behavior is derived from ownership consistency with sibling teardown code.

## Round 1
- **Verdict:** REAL BUG
- **Rationale:** `vp_del_vqs()` explicitly routes admin queues through `vp_dev->admin_vq.info`, but both reset helpers index `vp_dev->vqs[]` unconditionally.

## Round 2
- **Best maintainer argument:** Admin queues may be unreachable through the queue-reset API today, making the missing guard dormant.
- **Final stance:** STILL REAL BUG — the invariant is implicit, unenforced, and already contradicted by teardown's explicit `vp_is_avq()` split.

## Final verdict
**CONFIRMED.** BUG-004 survives the challenge gate and remains a real metadata-ownership defect.
