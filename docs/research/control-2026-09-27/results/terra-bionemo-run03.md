model: gpt-5.6-terra
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:47:29 UTC; finished 2026-09-28 23:50:20 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo AMPLIFY / ESM2 review

Reviewed commit `11701476b005ca7bc489df924a398b8f12453f0b`.

## Findings

### 1. Packed ESM2 token-dropout counts masks using unpadded offsets

- **Severity:** medium
- **Location:** `models/esm2/modeling_esm_te.py:741`
- **Trigger:** Run an ESM2 model with `token_dropout=True` (as used by ESM2 configurations), THD input, and per-sequence padding (`cu_seq_lens_q_padded`, produced by `DataCollatorWithFlattening(..., pad_sequences_to_be_divisible_by=...)`).
- **What goes wrong:** The code identifies masked tokens using offsets from `cu_seq_lens_q`, which describe the original packed layout, even though `input_ids` has had pad tokens inserted *between* sequences. For example, original lengths 3 and 5 have offsets `[0, 3, 8]`; after padding each sequence to 32 tokens, the second sequence begins at 32, but this code still treats indices 3 through 7 (the first sequence's padding and only part of the second sequence) as the second sequence. It therefore computes the wrong observed mask ratio for every sequence after the first and applies the wrong token-dropout scale factor.
- **Why this is wrong:** `_apply_token_dropout_thd` says it computes a per-sequence mask ratio and then repeats that factor over `src_lengths_padded` (lines 719-745). The collator documents that `cu_seq_lens_q_padded` is the padded layout and creates it after inserting per-sequence padding (`models/esm2/collator.py:213-226`). The offsets used to count masks must describe that same layout.
- **Suggested fix:** When `cu_seq_lens_q_padded` is present, pass it to `nested_tensor_from_jagged` for `n_masked_per_seq`; retain `cu_seq_lens_q` only as the denominator so padding tokens are excluded from the actual sequence length. Validate that the final padded offset matches the flattened input length.

### 2. AMPLIFY TE reverses only `int64` padding masks

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/amplify_te.py:245-247`
- **Trigger:** Call `AMPLIFY` or `AMPLIFYForMaskedLM` with a conventional boolean or `int32` Hugging Face padding mask (`True`/`1` for real tokens and `False`/`0` for padding).
- **What goes wrong:** Transformer Engine interprets boolean `True` as a position to mask, as the comment states. The code inverts that convention only when the input dtype is exactly `torch.int64`. A boolean mask is passed unchanged, so valid positions are masked and padding positions are attended; an `int32` mask is likewise not converted to the boolean mask TE expects.
- **Why this is wrong:** The comment at line 246 explicitly establishes TE's inverse boolean convention. The model's public `attention_mask` follows the normal transformer padding-mask API, and the `int64` branch itself shows the intended conversion. Limiting it to a single integer dtype makes equivalent standard masks produce opposite attention behavior.
- **Suggested fix:** Normalize every supported binary padding mask, regardless of integral or boolean dtype, with `attention_mask = ~attention_mask.to(torch.bool)`. If additive masks are meant to be supported too, distinguish and document that format explicitly rather than passing non-boolean tensors through.

### 3. AMPLIFY checkpoint conversion cannot pad non-CPU-float32 weights

- **Severity:** low
- **Location:** `models/amplify/src/amplify/state_dict_convert.py:90-91`
- **Trigger:** Convert a Hugging Face AMPLIFY model whose embedding or decoder weights are on CUDA or use a dtype such as `bfloat16`/`float16`.
- **What goes wrong:** `_pad_weights` always creates `padding_rows` as a CPU `float32` tensor. `torch.cat` immediately rejects CUDA source weights because the devices differ. For half/bfloat16 CPU weights, concatenation promotes the result to `float32`, after which the conversion's dtype-preservation check fails or the converted model has the wrong dtype.
- **Why this is wrong:** This helper pads the source embedding and decoder tensors during `convert_amplify_hf_to_te`. Unlike the analogous ESM2 helper (`models/esm2/convert.py:221-224`), it does not preserve the source tensor's `dtype` and `device`; conversion is otherwise written to preserve target parameter dtypes (`models/amplify/src/amplify/state.py:238-244`).
- **Suggested fix:** Construct padding with `torch.zeros(..., dtype=source_embed.dtype, device=source_embed.device)`.

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
- ESM2 tests consulted for behavior: `models/esm2/tests/test_collator.py`, `models/esm2/tests/test_modeling_esm_te.py`, and `models/esm2/tests/common/test_modeling_common.py`
