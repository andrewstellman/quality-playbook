# Challenge Gate — BUG-003

## Trigger patterns
- Another code path handles the same concern differently.

## Round 1
- **Verdict:** REAL BUG
- **Rationale:** Both PCI paths query `avq->vq_index`; MSI-X uses it for queue creation, while INTx uses it only in the queue name and then drops it in favor of `queue_idx++`.

## Round 2
- **Best maintainer argument:** In the common contiguous layout, `queue_idx` may equal `avq->vq_index`, making the bug latent.
- **Final stance:** STILL REAL BUG — the latent invariant is undocumented and unenforced, while the MSI-X path already shows the correct source of truth.

## Final verdict
**CONFIRMED.** BUG-003 survives the challenge gate and remains a real fallback-parity defect.
