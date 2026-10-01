# bionemo-thd: notes for Andrew (not for the PR)

## What to paste
- PR title: the first line of `PR-DRAFT.md`, without the `**Title:**` prefix.
- PR body: everything after the title line.
- Apply the patch: `git am 0001-*.patch` on a branch from `11701476b0`. The patch touches 10 files: the source, 8 regenerated copies and the test file. If upstream has moved, rebase, then run `python ci/scripts/check_copied_files.py --fix` and `python ci/scripts/check_copied_files.py` again before pushing. A copied file that changed upstream will conflict in all 9 places. The commit has no `Signed-off-by` and no `Assisted-by` trailer.

## Things only you can decide or do
- **Disclosure line.** It says you reviewed the change yourself. Make sure that's true, or reword it.
- **Signed-off-by.** It's optional here: the repo has no DCO bot. If you want it, run `git commit --amend -s`.
- **CI gate.** CI needs an NVIDIA org member to comment `/ok to test`, again for each new commit.
- **Config-time check.** The PR offers it as an alternative and says you're happy to switch. If a maintainer takes you up on it, that's a different patch, which would go in the recipes' `dataset.py`/`train_fsdp2_cp.py` where the default is derived. It hasn't been written.

## What was and wasn't verified
- **Verified on CPU**, with functions and tests extracted verbatim from the tree:
  - The base function leaves positions 16 and 17 out of both ranks' shards for lengths [8, 10] with `cp_world_size=2`.
  - The patched function raises the new ValueError instead.
  - The divisible case and the four existing BSHD split tests pass before and after.
  - Reversing the source change brings the failure back.
  - The logs are `red.log`, `green.log` and `revert.log`. `check_copied_files.py` passes (`check_copied_files.log`).
- **Not run:**
  - anything involving Transformer Engine;
  - whether TE would already fail downstream on today's code;
  - multi-rank behaviour, including the process-group-timeout hang, which comes from reading the code (O2);
  - the project's pytest, because the conftest imports `transformer_engine`;
  - the rest of `test_collator_context_parallel.py`, including `test_dataloader_scatter_*` and the tokenizer-based tests.
- **Harness stubs.** The only stub is `nvtx.annotate`, a pass-through decorator. Source and test line ranges and their sha256 prefixes are printed at the top of each log.
- **Usage snippet.** The `_split_batch_by_cp_rank` call in the PR's Usage section uses the same inputs as the harness demo, whose output is in `green.log`. The `cp_size: 3` / `16` example is arithmetic (16 % 6 != 0), not a training run.
- **Performance.** The guard calls `.tolist()` on the per-sequence lengths. O2 noted this adds no new sync point, because the function already calls `.item()` on `cu_seqlens_padded[-1]` a few lines later. I didn't measure it.
