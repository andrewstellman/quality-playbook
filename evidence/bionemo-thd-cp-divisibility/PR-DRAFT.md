# PR draft: guard THD context-parallel sharding against non-divisible padded lengths

**Base repo:** NVIDIA-BioNeMo/bionemo-recipes
**Base commit:** `11701476b005ca7bc489df924a398b8f12453f0b` (2026-09-18)
**Patch:** `0001-thd-cp-divisibility-guard.patch`

## Provenance (please keep this section in the PR body)
This finding was surfaced by an automated Quality Playbook review run. Reproduction (a
dependency-free harness reproducing the buggy vs. fixed sharding behavior) and the fix itself
were done by Claude (Anthropic). Andrew Stellman reviewed the diagnosis and patch before
submission; he is submitting this PR, not the AI.

## Summary
`_split_batch_by_cp_rank`'s THD branch (`models/esm2/collator.py`, canonical source for 8
byte-identical copies enforced by `ci/scripts/check_copied_files.py`) computes each sequence's
per-rank slice size via a plain floor division of the padded sequence length by
`2 * cp_world_size`, with no check that the division is exact. When a padded sequence length
isn't a multiple of `2 * cp_world_size`, the remainder tokens are silently dropped — never
selected by any context-parallel rank. The BSHD branch (`_process_tensor_bshd`) already raises a
`ValueError` on the identical condition; the THD branch has no equivalent guard.

This is reachable in normal use: the training recipes (`esm2_native_te`, `llama3_native_te`,
`opengenome2_llama_native_te`) only auto-derive a safe `pad_sequences_to_be_divisible_by` value
(`cp_mesh.size() * 2`) when the config leaves it unset. A caller who sets it explicitly — as
`recipes/esm2_native_te/hydra_config/L0_sanity_cp.yaml` already does, for FP8/hardware-alignment
reasons — can pick a value that isn't a multiple of `2 * cp_world_size` and silently lose training
tokens with no error.

## Fix
Added a divisibility guard to the THD branch mirroring the BSHD branch's existing one, raising
`ValueError` with the offending sequence length(s) before the floor division. Propagated the fix
to all 8 enforced copies via `python ci/scripts/check_copied_files.py --fix` (per `CONTRIBUTING.md`).
Added `models/esm2/tests/test_cp_thd_divisibility_guard.py`: one test asserting the guard raises
on a non-divisible padded length, one confirming no regression on a divisible-length case.

## Testing
Verified with a dependency-free harness reproducing the sharding logic outside the module (full
detail in the accompanying evidence README) — `transformer_engine` and `nvtx`, both unconditional
imports of this module, aren't installable in the reviewing sandbox (no GPU). Red on the
unpatched function (2 of 10 tokens in a non-divisible sequence are dropped by every CP rank on a
2-rank shard); green after the fix (raises `ValueError` instead, and a divisible-length case still
shards with zero tokens dropped). The new pytest tests use the function's own `cp_rank` parameter
to run single-process without `torch.distributed`, and should run cleanly under the project's own
CI image.

## Notes for maintainers
- Confirmed via GitHub issue search that issue #1561 (MFU/FLOPs Σ(Lᵢ²) accounting under
  `pad_to_multiple_of`) is a related-but-distinct concern in a different code path
  (`cu_seq_lens_q` mock-sequence padding, not `cu_seq_lens_q_padded` CP sharding) — not a
  duplicate of this fix.
- No `Signed-off-by` trailer was added — `CONTRIBUTING.md` and the PR template didn't mention a
  DCO requirement for this repo, but please add one if NVIDIA's process expects it.
