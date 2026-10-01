# bionemo-amplify: v1 → v2

Base commit is unchanged: `11701476b005ca7bc489df924a398b8f12453f0b`. Patch: `0001-amplify-keep-dtype-device-of-padding-rows-in-_pad_we.patch`.

## Code
- **Source change:** identical to v1. `dtype=source_embed.dtype, device=source_embed.device` is added to the `torch.zeros` call in `_pad_weights`. Byte-for-byte the same hunk.
- **Test moved.** v1 added a new file, `models/amplify/tests/test_pad_weights_dtype_device.py`, with a 2025 header and an 8-line docstring. v2 adds `test_pad_weights_dtype_device` to the existing `models/amplify/tests/test_amplify_model.py`, directly after `test_convert_state_dict`, with a one-line docstring. There is no new file, so no license header is needed.
- **Device half.** The test is now parametrized over `cpu` and `cuda`, and the `cuda` case has `pytest.mark.skipif(not torch.cuda.is_available())`. In v1 the device assertion only compared CPU to CPU, which is true before and after the fix, so it pinned nothing (S4). The `cuda` case was **skipped** in every run here. The PR says only the dtype half was executed.
- The test also checks that the padding rows are zero. `assert_close` on the copied rows now compares in bf16 directly, without `.float()`.
- ruff 0.12.8 check and format pass on both files (`lint.log`).

## Commit message
- It is now four lines. The misattached clause is gone: v1's "unlike the parallel ESM2 _pad_weights ..., which silently upcasts" read as if ESM2 had the bug.
- The "Finding surfaced by a Quality Playbook automated review run ..." provenance paragraph is removed from the commit.

## PR text (`PR-DRAFT.md`)
- It is rewritten into the repo template: Description / Usage / Type of changes / CI Pipeline Configuration / Pre-submit Checklist.
- **Impact claim corrected.** v1 said a bf16 conversion "silently upcasts". v2 states the function-level fact: the padding rows are fp32/CPU regardless of the source, and `torch.cat` returns fp32 for bf16 (shown on CPU). It then says the full conversion most likely fails at the `apply_transforms` dtype assertion (`state.py:238-243`), and that a CUDA source should fail in `torch.cat`. Both are marked as not run.
- The change is framed as matching `_pad_bias` in the same file and the ESM2 `_pad_weights`.
- Removed: "Provenance (please keep this section…)", the third-person "he is submitting this PR, not the AI", the pointer to an evidence README maintainers can't see, and the DCO/Signed-off-by speculation. A single first-person disclosure line replaces them.
- The checklist answers are honest. "Tested locally" and "existing tests pass" are unchecked, with the reason. The harness method and its result are stated. "Added tests" is checked.

## Verification
- v1's harness hand-copied three function variants into a script. v2's `harness/run_extracted.py` uses `ast` to extract `_pad_weights` and the new test function from a real checkout, keeping their exact text, and runs the test under pytest.
- Red uses the pinned base source with the patched test. Green uses the patched tree. Revert uses the patched commit with the source hunk reversed through `git apply -R`.
- Results: red FAILED (`torch.float32 == torch.bfloat16`), green PASSED, revert FAILED. `cuda` was SKIPPED in all three.
- `git am` of the patch onto a fresh checkout of the pinned commit gives a tree identical to the fix branch.
