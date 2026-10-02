model: gpt-5.6-terra
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:52:16 UTC; finished 2026-09-28 23:54:50 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review: AMPLIFY and ESM2

Reviewed commit `11701476b005ca7bc489df924a398b8f12453f0b` within the requested paths.

## Findings

### 1. Packed token-dropout counts masks from the wrong sequence after per-sequence padding

- **Severity:** medium
- **Location:** `models/esm2/modeling_esm_te.py:741`
- **What goes wrong:** With THD input, token dropout enabled, and `cu_seq_lens_q_padded` present (the output of `DataCollatorWithFlattening` when `pad_sequences_to_be_divisible_by` is used), the mask count for every sequence after the first is taken from the wrong region of `input_ids`. For example, two original sequences of length 5 padded to length 8 produce unpadded offsets `[0, 5, 10]` and padded token storage `[seq1(5), pad(3), seq2(5), pad(3)]`. The code groups the latter using `[0, 5, 10]`, so the second group contains three padding tokens and only two tokens from sequence 2. Its observed mask ratio, and therefore its embedding scale, are wrong.
- **Why it is wrong:** The collator deliberately retains original lengths in `cu_seq_lens_q` and writes padded boundaries separately to `cu_seq_lens_q_padded` (`models/esm2/collator.py:220-226`). `_apply_token_dropout_thd` correctly uses the padded lengths for `repeat_interleave` at lines 735-744, but line 741 constructs the jagged tensor with the *unpadded* offsets while passing the padded `input_ids`. This contradicts its own docstring's claim to calculate each packed sequence's mask ratio.
- **Suggested fix:** When `cu_seq_lens_q_padded` is supplied, construct the jagged mask tensor using that padded offset tensor, while retaining `torch.diff(cu_seq_lens_q)` as the denominator for real-token lengths. That counts masks from the actual padded segment belonging to each sequence and still excludes pad tokens from the ratio denominator.

### 2. AMPLIFY embedding and decoder conversion allocates vocabulary padding on the wrong device and in the wrong dtype

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/state_dict_convert.py:90`
- **What goes wrong:** `convert_amplify_hf_to_te` fails when the source AMPLIFY embedding or decoder weights are on CUDA: it attempts to concatenate a CUDA `source_embed` with CPU `padding_rows`. It also always creates `padding_rows` as the default dtype, instead of the source tensor's dtype. Thus converting a model that has been moved to GPU, or preserving a non-default source dtype, is not supported.
- **Why it is wrong:** `_pad_weights` builds the output by concatenating `source_embed` with `padding_rows` at line 91. PyTorch concatenation requires tensors on the same device. The analogous ESM2 converter explicitly preserves both dtype and device when creating these rows (`models/esm2/convert.py:243-246`), and the AMPLIFY bias-padding transform immediately below likewise specifies `dtype=source_bias.dtype, device=source_bias.device` (`state_dict_convert.py:113-115`).
- **Suggested fix:** Construct the padding with `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

## Files read

- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/README.md`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/state.py`
