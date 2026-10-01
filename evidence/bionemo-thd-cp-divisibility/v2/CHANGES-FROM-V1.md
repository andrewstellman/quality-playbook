# bionemo-thd: v1 → v2

Base commit is unchanged: `11701476b005ca7bc489df924a398b8f12453f0b`. Patch: `0001-collator-reject-THD-CP-shards-with-non-divisible-pad.patch`.

## Code
- **Guard logic is the same.** The THD branch of `_split_batch_by_cp_rank` checks each padded length against `2 * cp_world_size` before the floor division. The implementation is slightly tighter: `bad_lengths` is computed once, with no separate `remainders`/`torch.any`.
- **Error message rewritten.**
  - v1: `Padded sequence length(s) [10] must be divisible by 4 (2 * cp_world_size) for THD context parallelism, matching the guard already enforced by the BSHD branch (_process_tensor_bshd).`
  - v2: `Padded sequence length(s) [10] must be divisible by 4 (2 * cp_world_size) for THD context parallelism; set pad_sequences_to_be_divisible_by to a multiple of 4`
  - The private function name is gone and the message tells the user what to change. It follows the BSHD message's shape and has no trailing period, like the BSHD message.
  - At most five bad lengths are listed, followed by "(and N more)" (O2). `green.log` shows the truncated form.
- **Copies regenerated.** The source edit was propagated with `python ci/scripts/check_copied_files.py --fix` (8 destinations). `python ci/scripts/check_copied_files.py` then exits 0 (`check_copied_files.log`). All 9 collator hunks are identical.
- **Tests moved.** v1 added a new file, `models/esm2/tests/test_cp_thd_divisibility_guard.py`, with a 2025 header and a long docstring. v2 adds two tests to the existing `models/esm2/tests/test_collator_context_parallel.py`, after the BSHD split tests, each with a one-line docstring:
  - `test_split_batch_by_cp_rank_thd_non_divisible` also matches the reported length and divisor (`[10] must be divisible by 4`).
  - `test_split_batch_by_cp_rank_thd_covers_all_tokens` checks that the sorted union of both ranks' shards equals the input, so each token appears exactly once.
- ruff 0.12.8 check and format pass on all 10 changed files (`lint.log`).

## Commit message
- It is now six lines, down from v1's four paragraphs. The provenance paragraph and the L0_sanity_cp reference are removed.

## PR text (`PR-DRAFT.md`)
- It is rewritten into the repo template.
- **Impact claim corrected.** v1 said "silently lose training tokens with no error". v2 says what was shown: the collator leaves remainder tokens out of every rank's shard, with an example (positions 16 and 17). It also says Transformer Engine's later handling of the mismatch was not checked.
- **Shipped configs.** v2 states that `L0_sanity_cp.yaml` is safe (16 with `cp_size: 2`), that the only other config setting the value (mixtral `L1_8x7B_B200.yaml`, 32) doesn't use CP, and that the guard is for user overrides. v1 cited L0_sanity_cp in a way that read as if it were affected.
- **Added:**
  - the behaviour-change warning: configs that drop tokens today will now fail (S5);
  - the process-group-timeout note: other CP ranks wait in the scatter when rank 0 raises (O2);
  - the config-time check, offered as an alternative the maintainers may prefer (O1, O2, O4).
- **Removed:** the provenance section, third-person text, the evidence-README pointer, the DCO speculation, and the #1561 note. The #1561 note wasn't needed and read as defensive (O5).
- **Checklist answered honestly.** "Tested locally" and "existing tests pass" are unchecked, with the reason and the harness result stated.

## Verification
- v1's harness hand-copied the functions. v2's `harness/run_extracted.py` uses `ast` to extract `_find_seq_dim`, `_process_tensor_thd`, `_process_tensor_bshd` and `_split_batch_by_cp_rank` from `models/esm2/collator.py`, with decorators and exact text, and stubs only `nvtx.annotate`. From the test file it extracts the two new tests, the four existing BSHD split tests and their two data helpers, and runs them under pytest.
- Red uses the pinned base source with the patched tests. Green uses the patched tree. Revert uses the patched commit with all 9 collator hunks reversed through `git apply -R`.
- Results: red has 1 failed ("DID NOT RAISE") and 5 passed. Green has 6 passed. Revert has 1 failed and 5 passed.
- A harness-only demo (not an upstream test) runs after pytest in each log. It prints the missing token positions ([16, 17]) on red and revert, and the ValueError text on green.
- `git am` of the patch onto a fresh checkout of the pinned commit gives a tree identical to the fix branch.
