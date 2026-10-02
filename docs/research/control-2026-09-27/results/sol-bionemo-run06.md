model: gpt-6-sol
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:35:47 UTC; finished 2026-09-28 23:37:33 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review — scoped findings

1. **Medium — Boolean AMPLIFY attention masks are inverted** (`models/amplify/src/amplify/amplify_te.py:245`). `AMPLIFY.forward` converts an attention mask to TE's convention only when its dtype is exactly `torch.int64`. A normal Hugging Face boolean mask uses `True` for a valid token, while the comment at line 246 states that TE uses `True` for a token to mask. Passing a boolean mask therefore masks all valid tokens and exposes padding positions to attention. The same problem applies to integer masks with a dtype other than int64. Convert every supported 0/1 input mask with `~attention_mask.to(torch.bool)` (or validate and explicitly distinguish an already converted TE mask).

2. **Medium — THD token-dropout counts masks in the wrong sequences when there is inter-sequence padding** (`models/esm2/modeling_esm_te.py:741`). `_apply_token_dropout_thd` uses unpadded `cu_seq_lens_q` as offsets into `is_masked`, which is built from the *padded* `input_ids`. After padding the first sequence, subsequent offsets point too early; a mask near the end of a later sequence is counted in another sequence or not counted at all. For example, two length-three sequences padded to four tokens each have unpadded offsets `[0,3,6]`, but the second sequence occupies padded indices `[4,7)`, so a mask at index 6 is excluded from the second sequence's mask count. The method's docstring says it computes per-sequence mask ratios, and lines 735–745 explicitly use padded lengths for the output scaling. Count masks using `cu_seq_lens_q_padded` boundaries, excluding padding tokens, while dividing by the original sequence lengths.

3. **Medium — AMPLIFY conversion creates padding weights on the wrong device and with the wrong dtype** (`models/amplify/src/amplify/state_dict_convert.py:90`). `_pad_weights` creates `padding_rows` with implicit CPU/float32 defaults, then concatenates them with `source_embed`. Converting a GPU checkpoint fails at `torch.cat` with a device mismatch. Converting a CPU half-precision checkpoint promotes the padded embedding/decoder weight to float32; `amplify.state.apply_transforms` directly registers that tensor and asserts its dtype equals the original target parameter dtype at `models/amplify/src/amplify/state.py:237–243`, so the conversion fails. The equivalent ESM conversion creates padding on `source_embed.device` with `source_embed.dtype` (`models/esm2/convert.py`). Use `source_embed.new_zeros((num_padding_rows, source_embed.size(1)))`.

Files read: `models/amplify/src/amplify/amplify_hf.py`, `models/amplify/src/amplify/amplify_te.py`, `models/amplify/src/amplify/export.py`, `models/amplify/src/amplify/metrics.py`, `models/amplify/src/amplify/rotary.py`, `models/amplify/src/amplify/state.py`, `models/amplify/src/amplify/state_dict_convert.py`, `models/esm2/collator.py`, `models/esm2/convert.py`, `models/esm2/export.py`, `models/esm2/modeling_esm_te.py`.
