# PR draft: AMPLIFY `_pad_weights` preserves source dtype/device

**Base repo:** NVIDIA-BioNeMo/bionemo-recipes
**Base commit:** `11701476b005ca7bc489df924a398b8f12453f0b` (2026-09-18)
**Patch:** `0001-amplify-pad-weights-dtype-device.patch`

## Provenance (please keep this section in the PR body)
This finding was surfaced by an automated Quality Playbook review run. Reproduction (a
dependency-free harness reproducing the buggy vs. fixed behavior) and the fix itself were done by
Claude (Anthropic). Andrew Stellman reviewed the diagnosis and patch before submission; he is
submitting this PR, not the AI.

## Summary
`_pad_weights` in `models/amplify/src/amplify/state_dict_convert.py` builds its zero-padding rows
with a bare `torch.zeros(num_padding_rows, source_embed.size(1))`, which defaults to
`dtype=torch.float32` on CPU regardless of the source embedding's actual dtype/device. The
parallel ESM2 implementation (`models/esm2/convert.py::_pad_weights`) already passes
`dtype=source_embed.dtype, device=source_embed.device`. Converting a bf16 and/or CUDA-resident
AMPLIFY checkpoint therefore either silently upcasts the padded weights to float32, or raises a
device-mismatch error on the subsequent `torch.cat`, depending on where the source tensor lives.

## Fix
Add the same two kwargs AMPLIFY's ESM2 sibling already uses. One-line change plus a regression
test (`models/amplify/tests/test_pad_weights_dtype_device.py`) that pads a bf16 CPU tensor and
asserts the output dtype/device match the input.

## Testing
Verified with a dependency-free harness reproducing `_pad_weights`' logic outside the module
(full detail in the accompanying evidence README) — `transformer_engine`, an unconditional
import of this module's parent package, isn't installable in the reviewing sandbox (no GPU). Red
on the unpatched function (dtype silently drops to float32), green after the fix (dtype/device
preserved, matching the ESM2 sibling's behavior exactly). The new pytest test mirrors the existing
`MagicMock`-based test pattern in `tests/test_amplify_model.py::test_convert_state_dict` and should
run cleanly under the project's own CI image.

## Notes for maintainers
- `export.py::export_hf_checkpoint` doesn't currently trip this (it loads the HF model at default
  fp32), so this hasn't caused visible breakage in the repo's own scripts — but
  `convert_amplify_hf_to_te` is a public conversion function and a bf16/CUDA `from_pretrained`
  call is an ordinary way to invoke it.
- No `Signed-off-by` trailer was added to the commit — `CONTRIBUTING.md` and the PR template
  didn't mention a DCO requirement for this repo, but please add one if NVIDIA's process expects
  it.
