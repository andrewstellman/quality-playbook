# bionemo-amplify: notes for Andrew (not for the PR)

## What to paste
- PR title: the first line of `PR-DRAFT.md`, without the `**Title:**` prefix.
- PR body: everything after the title line.
- Apply the patch: `git am 0001-*.patch` on a branch from `11701476b0`. Upstream main may have moved, so rebase if needed. The commit is authored as you. It has no `Signed-off-by` and no `Assisted-by` trailer.

## Things only you can decide or do
- **Disclosure line.** It says you reviewed the change yourself before opening the PR. Make sure that's true when you send it, or reword it.
- **Signed-off-by.** The repo has no DCO bot and CONTRIBUTING doesn't ask for one. O1 noted that a service-account PR (#1746) includes one anyway. If you want it, run `git commit --amend -s`. It's your attestation, so I didn't add it.
- **CI gate.** You're an outside contributor, so CI won't start until an NVIDIA org member comments `/ok to test`. They have to do it again for each new commit you push. copy-pr-bot handles this.

## What was and wasn't verified
- **Verified on CPU:** the extracted `_pad_weights` returns `torch.float32` for a bf16 source before the change and `torch.bfloat16` after it. The new test fails before, passes after, and fails again with the source change reversed (`red.log`, `green.log`, `revert.log`).
- **Not run:**
  - the `cuda` test case (skipped: no GPU);
  - the device-mismatch failure in `torch.cat`;
  - the `apply_transforms` dtype assertion on a real bf16 conversion;
  - the project's own pytest, because `transformer_engine` won't import without CUDA;
  - the rest of `test_amplify_model.py`.
- **Wording.** The PR says "most likely fails at that assertion" and "should make `torch.cat` fail" for these reasons. Don't strengthen those phrases without a GPU run.
- **Assertion caveat.** I didn't check whether an end-to-end bf16 conversion trips the `apply_transforms` assertion on some other key first, independent of this fix. That's another reason the PR says "most likely".
- **Harness stubs.** The harness stubs only `io.TransformCTX`, which is used in the function's type annotation. Everything else is extracted verbatim. The source and test line ranges and their sha256 prefixes are printed at the top of each log.

## Housekeeping
- The usage snippet in the PR (`from_pretrained(..., dtype=torch.bfloat16)`) is illustrative and labelled "not run".
- The reviewer panel's other suggestions are already applied: the test is in the existing file, the docstring is one line, and there's no new license header.
