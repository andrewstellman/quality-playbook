model: gpt-6-sol
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:27:14 UTC; finished 2026-09-28 23:28:39 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review — `11701476b005ca7bc489df924a398b8f12453f0b`

## Findings

1. **Medium — AMPLIFY TE reverses only `int64` attention masks.** `models/amplify/src/amplify/amplify_te.py:245-247`. A normal boolean attention mask (`True` for a real token and `False` for padding), or an `int32` 0/1 mask, is passed unchanged to Transformer Engine. The adjacent comment explicitly says TE interprets `True` as *masked*, so boolean inputs mask valid tokens and expose padding; `int32` inputs can also violate the TE mask type. The HF implementation in `amplify_hf.py:360-365` treats 1 as an attended token, establishing the public mask convention. Convert all accepted 0/1 masks with `~attention_mask.to(torch.bool)`; validate any other mask representation separately.

2. **Medium — AMPLIFY TE ignores both bias configuration flags.** `models/amplify/src/amplify/amplify_te.py:190`. `AMPLIFYConfig` documents and stores `att_bias` and `ffn_bias` (`:82-83`, `:104-105`), and the HF implementation applies them to its attention and feed-forward layers (`amplify_hf.py:128-187`). The TE transformer is always created with `bias=False`. A config with either flag enabled therefore builds a different model; HF-to-TE conversion cannot preserve its bias parameters. Pass the requested bias settings to TE where supported, or reject unsupported configurations explicitly before conversion.

3. **Medium — AMPLIFY conversion allocates padding rows on CPU even for GPU weights.** `models/amplify/src/amplify/state_dict_convert.py:90`. `_pad_weights` concatenates `source_embed` with `torch.zeros(...)` that has no `device` or `dtype`. Converting a model whose weights are on CUDA fails at `torch.cat` with a device mismatch; non-default dtypes are also changed or rejected. The function's stated purpose is to pad the source embedding/decoder weights, and both `_pad_embeddings` and `_pad_decoder_weights` use it. Allocate with `source_embed.new_zeros((num_padding_rows, source_embed.size(1)))`.

4. **Medium — pre-padded ESM2 samples produce inconsistent packed metadata.** `models/esm2/collator.py:165-170` and `:706-720`. `DataCollatorWithFlattening` selects the packed IDs and labels using the BSHD collator's `attention_mask`, but `_pt_flatten_collate` computes `cu_seq_lens_q`, positions, and the maximum length from the full `input_ids` lengths. For a valid feature such as `input_ids=[0,5,2,1]`, `attention_mask=[1,1,1,0]`, the packed tensor has three tokens while the cumulative length ends at four. Flash Attention / THD padding then receives a boundary beyond the tensor, or the returned position IDs have the wrong length. The collator's documented feature input explicitly allows `attention_mask` and promises metadata that describes the packed tensor (`:109-135`). Derive all packed lengths, position IDs and metadata from the selected non-padding tokens, or reject pre-padded features before flattening.

## Files read

- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/tests/test_collator.py` (context only; excluded from review scope)
