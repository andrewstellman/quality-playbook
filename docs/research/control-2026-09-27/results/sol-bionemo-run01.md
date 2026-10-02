model: gpt-6-sol
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:24:31 UTC; finished 2026-09-28 23:27:03 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; model tests unavailable
interruptions or errors: PyTorch unavailable in active environment
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review

Checkout: `11701476b005ca7bc489df924a398b8f12453f0b`. Scope: `models/amplify/src/amplify/` and `models/esm2/`, excluding tests.

## Findings

1. **High — THD token dropout uses full-batch offsets on context-parallel shards.** `models/esm2/modeling_esm_te.py:741`. With `attn_input_format="thd"`, `token_dropout=True`, and CP size greater than one, `DataCollatorForContextParallel` replaces `input_ids` with the rank's shard but preserves the original `cu_seq_lens_q` and `cu_seq_lens_q_padded` (`models/esm2/collator.py:424-425`). `_apply_token_dropout_thd` then passes the full-batch offsets to `nested_tensor_from_jagged` over the shorter shard. The final offset exceeds the shard length, so this can fail; even if accepted, mask counts cannot correspond to the shard's sequences. The method's docstring says it computes per-sequence mask ratios for packed inputs, and the CP collator is explicitly meant to produce model input shards. Compute the per-sequence mask ratios before sharding and distribute them, or calculate shard-local counts using CP-aware indices and aggregate counts across ranks.

2. **Medium — THD per-sequence padding makes mask counts cross sequence boundaries.** `models/esm2/modeling_esm_te.py:741`. Without CP, `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=...)` inserts padding between sequences and supplies `cu_seq_lens_q_padded` (`models/esm2/collator.py:213-226`). `_apply_token_dropout_thd` nevertheless partitions the padded `input_ids` with the *unpadded* `cu_seq_lens_q`. For example, original lengths `[3, 2]` and padded lengths `[4, 4]` give offsets `[0, 3, 5]` over a token tensor laid out as `[three real tokens, pad, two real tokens, two pads]`; the second mask count examines the pad plus only the first token of the second sequence. It therefore applies an incorrect scale to both sequences when masked positions occur near the boundary, contradicting the documented per-sequence scaling. Count masks within each sequence using padded starts and original lengths, excluding inter-sequence padding.

3. **Medium — AMPLIFY TE interprets boolean and non-int64 attention masks backwards.** `models/amplify/src/amplify/amplify_te.py:245-247`. The code converts only `torch.int64` masks from the usual `1=valid, 0=padding` convention into TE's `True=masked` convention. A boolean mask such as `[[True, True, False]]` is passed through unchanged, so TE masks both real tokens and exposes the padding token; `int32` masks likewise bypass conversion. The adjacent comment establishes TE's required meaning, while the conversion establishes the caller-facing 1/0 meaning. Normalize every supported 1/0 mask dtype with `~attention_mask.bool()` before calling the TE layer.

4. **Medium — AMPLIFY conversion fails for a source model on CUDA.** `models/amplify/src/amplify/state_dict_convert.py:90-91`. `convert_amplify_hf_to_te` accepts an arbitrary Hugging Face module, but `_pad_weights` creates CPU `float32` rows and concatenates them with the source embedding and decoder weights. When the supplied model is on CUDA, `torch.cat` raises a device mismatch instead of converting it. The analogous ESM converter creates padding rows with the source tensor's `dtype` and `device` (`models/esm2/convert.py:236-238`). Use `torch.zeros(..., dtype=source_embed.dtype, device=source_embed.device)` here too.

I could not run model tests because `torch` is not installed in this checkout's active Python environment. These findings follow from the data and metadata paths in the source.

## Files read

- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/state.py` (lines 80–245)
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/tests/test_cp_thd.py` (opening section)
