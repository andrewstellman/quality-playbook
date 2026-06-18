# Challenge Gate — BUG-001

## Trigger patterns
- Another code path handles the same concern differently.

## Round 1
- **Verdict:** REAL BUG
- **Rationale:** PCI modern explicitly polls for reset completion with an inline spec citation; MMIO writes `0` and returns with no matching poll or rationale.

## Round 2
- **Best maintainer argument:** MMIO targets may complete reset synchronously in practice, making the read-back loop observationally redundant on today's emulators.
- **Final stance:** STILL REAL BUG — the formal reset contract is unconditional, and the PCI sibling shows the codebase knew that rule.

## Final verdict
**CONFIRMED.** BUG-001 survives the challenge gate and remains a real reset-contract defect.
