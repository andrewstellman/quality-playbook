# Self-Council synthesis — instruction 014 (Feature H slice 2: orchestration + isolation)

**Verdict: unanimous SHIP** across all three security charters, with two cheap
non-blocking findings closed post-panel. This was the full 3-charter security
Council the instruction required (this is the security core of Feature H).

Reviewed code: branch `1.6.0`, commit `8b38a33` (persona orchestration + isolation).
Three panelists, each in its own git worktree, each writing a full verdict to
`reviews/014_self_council/panelist_{A,B,C}_*.md`.

## Charters + verdicts
- **A — isolation is prevention, not detection: SHIP.** Staging omits the impl
  tree / `.env` / `operator_confirmations.jsonl` (proven absent by enumeration);
  the tool allowlist denies every shell/network alias while allowing only Read
  rooted at the per-persona staging dir. Every out-of-bounds vector was contained:
  forbidden-name staging (direct and traversal-named) raises, file- and
  directory-symlinks are caught (the `is_symlink()` check precedes `is_dir()` so
  rglob never recurses through a dir-symlink), real subdirs raise, traversal names
  are flattened and did not escape, sibling persona dirs are unreachable from
  another's read_root. Mutation bites (weaken `denies`, drop the forbidden-name
  guard, no-op `assert_isolation`) each fail the suite — load-bearing. Fabrication-
  tell confirmed advisory-only backstop.
- **B — independence + diff-set integrity: SHIP.** `run_personas` calls
  `executor(persona, staging_dir, tool_config)` with no diff-set or sibling-dir
  parameter and no shared mutable state — genuinely blind; the 3-persona spy probe
  confirmed distinct staging dirs each rooted at its own read_root. The raw diff-
  set is well-formed (confirm/correct/add/drop only; `defer`, unknown moves,
  missing-key, non-dict all rejected) and each move carries req/section + reason +
  citation for slices 3-5. No merge/apply/renumber/grounding leaked in. Mutation
  (accept `defer`) fails the suite; restored.
- **C — substrate fidelity + target-agnostic reuse + scope: SHIP.** The code IS
  the pinned §8b substrate (staging = prevention-by-absence; tool config = Read-
  only/no-shell/no-network rooted at the staging dir; fabrication-tell backstop;
  plus `assert_isolation`'s conservative symlink/subdir/escape checks). A Feature-
  B-shaped `provision` (finding+source+REQ+rubric — the opposite, more-restrictive
  isolation) drove `run_personas` unchanged — the seam is genuinely target-agnostic
  and B can bind it. No OS/network-sandbox or later-slice scope crept in (stdlib-
  only, no subprocess/socket/seccomp); the live spawn is correctly a deterministic
  `executor` seam; the module is not bundled adopter-side yet (explicit allowlist,
  same precedent as slice 1).

## Findings closed post-panel (`2476984`)
- **A (test-coverage gap, LOW):** removing the traversal-flatten `Path(item.name).name`
  broke no test though the flatten is security-load-bearing. Closed with
  `test_traversal_named_input_is_flattened_not_escaped` — a `"../../passwd"` input
  lands flattened inside the staging dir and does not escape.
- **C (nit):** dropped the unused `Dict` import.

## Noted non-defects (correct as designed)
- **B:** the persona loop is sequential, not literally parallel — parallelism is
  the slice-7 live-spawn's job; blindness is order-independent, which is what
  guard 3 requires. Sibling isolation rests on the per-persona read_root allowlist
  (guard 2), correct within this slice.
- **C:** the live sub-agent spawn is behind the `executor` seam (slice 7), not
  faked — this slice tests the mechanism deterministically.

## Recorded for the orchestrator
- `persona_orchestration.py` (and `persona_catalog.py`) are NOT bundled adopter-side
  yet — the live-run slice (7) that wires persona execution at adopter runtime must
  add both to all five bundle-drift sites.
- Sibling-persona isolation ultimately depends on the live spawn honoring `read_root`
  (the harness contract) — the config is correct; the enforcement is the spawn's.

## Verification
Full suite green (2687 → 2688 after the +1 traversal test; see the instruction
output for the exact count); Python 3.14.6. All 16 orchestration tests pass.

**Terminal verdict: SHIP.** Isolation is prevention-by-construction and load-bearing;
personas are independent; the diff-set is clean; the seam is target-agnostic; no
OS-sandbox/later-slice scope crept in.
