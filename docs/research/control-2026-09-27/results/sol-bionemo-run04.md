model: gpt-6-sol
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:30:45 UTC; finished 2026-09-28 23:33:26 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; model tests unavailable
interruptions or errors: PyTorch unavailable
network access attempted (yes/no, and what): no attempt reported

# Review: bionemo-recipes, `models/amplify/src/amplify/` and `models/esm2/`

## Findings

1. **High — Packed ESM token dropout uses the wrong sequence boundaries after per-sequence padding and during context parallelism.** `models/esm2/modeling_esm_te.py:741` segments `input_ids` using `cu_seq_lens_q`, even though `_apply_token_dropout_thd` explicitly accepts `cu_seq_lens_q_padded` and uses its lengths to expand the result (lines 733–745). `DataCollatorWithFlattening._pad_sequences_to_be_divisible_by` emits padded token data and separate padded offsets (`models/esm2/collator.py:213–225`). For two logical sequences of length 5 and 6 padded to 8 each, logical offsets `[0,5,11]` segment the padded 16-token array as `[0:5]` and `[5:11]`; the second segment includes padding from the first sequence and misses part of the second. A mask token in the missed part is counted for neither sequence, so the compensation scale is wrong. In context parallel execution the same code receives a shard of `input_ids` while the cumulative offsets remain for the full batch (`collator.py:416–435`), which can also cause an offset/tensor length mismatch. The method's docstring says it computes *per-sequence* mask ratios. Segment the padded input with `cu_seq_lens_q_padded` when present, retain unpadded lengths as the denominator, and compute or distribute per-sequence mask counts correctly for context-parallel shards.

2. **Medium — AMPLIFY TE ignores configured attention and feedforward biases.** `models/amplify/src/amplify/amplify_te.py:190` hard-codes `bias=False` for every `TransformerLayer`, although `AMPLIFYConfig` exposes and documents `att_bias` and `ffn_bias` (lines 60–61, 82–84). The HF implementation creates attention and feedforward linear biases when those flags are true (`amplify_hf.py:125–188`), and the HF-to-TE conversion mapping contains no bias entries (`state_dict_convert.py:27–34`). Converting such a checkpoint silently drops its trained biases, changing predictions; constructing the TE model directly also contradicts its config. Honor the two flags in the corresponding TE attention/MLP modules and map their bias tensors during conversion, or reject unsupported configurations explicitly.

3. **Medium — AMPLIFY conversion fails for non-CPU or non-float32 source weights when vocabulary padding is needed.** `models/amplify/src/amplify/state_dict_convert.py:90` creates `padding_rows` with default CPU/float32 properties, then line 91 concatenates it with `source_embed`. A CUDA source embedding raises a cross-device error; a lower-precision embedding can be promoted or produce an output dtype that fails the conversion's dtype check in `state.py:232–237`. The conversion function accepts a Hugging Face model without restricting its device or dtype (`state_dict_convert.py:37–60`), and ESM's analogous padding routine explicitly preserves both (`models/esm2/convert.py:238–246`). Create zeros with `dtype=source_embed.dtype, device=source_embed.device`.

4. **Medium — Boolean Hugging Face attention masks are interpreted backwards by AMPLIFY TE.** `models/amplify/src/amplify/amplify_te.py:245–247` inverts only `torch.int64` masks. Its own comment states TE expects `True` to mean *masked*, while the conversion of an integer mask shows that this model's public input uses 1/True for a valid token. A boolean mask with `True` for valid tokens (or an `int32` 0/1 mask) therefore reaches the TE layer unchanged, causing valid positions to be masked and padding to be attended. Normalize supported 0/1 mask dtypes to `~attention_mask.bool()` before calling the TE layer, or make the accepted mask convention explicit and validate it.

## Files read

- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/state.py` (conversion dtype-check excerpt)
- `models/amplify/src/amplify/export.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/state.py`
- `models/esm2/export.py`
- `models/esm2/tests/test_cp_thd.py` (excerpts)
- `models/esm2/tests/test_collator.py` (excerpts)
- `models/esm2/tests/test_modeling_esm_te.py` (searched excerpts)
- `models/esm2/tests/test_collator_context_parallel.py` (searched excerpts)
- `models/esm2/tests/test_cp_dataloader.py` (searched excerpts)
- `models/esm2/tests/common/test_modeling_common.py` (searched excerpts)
