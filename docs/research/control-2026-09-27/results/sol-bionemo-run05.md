model: gpt-6-sol
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:33:40 UTC; finished 2026-09-28 23:35:37 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; model tests unavailable
interruptions or errors: torch unavailable in local Python environment
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review — `11701476b005ca7bc489df924a398b8f12453f0b`

## Findings

1. **Medium — AMPLIFY's CPU attention mask has the wrong dtype.** `models/amplify/src/amplify/amplify_hf.py:361` converts every supplied padding mask to `bfloat16`, while the default embedding, attention projections, and CPU query/key/value tensors are `float32`. The CPU path passes this additive mask to `torch.nn.functional.scaled_dot_product_attention` at line 268, which requires a floating mask compatible with the query dtype. Thus a default `AMPLIFY` model given ordinary `input_ids` and a nontrivial `attention_mask` fails during forward; the no-mask path works. The method's documented `attention_mask` argument and the branch explicitly intended to apply it establish that masked inference should work. **Fix:** cast the additive mask to the attention query dtype (and device), or use a boolean mask with the correct polarity for `scaled_dot_product_attention`.

2. **Medium — AMPLIFY TE reverses only `int64` masks.** `models/amplify/src/amplify/amplify_te.py:245-247` converts a standard `1=attend, 0=padding` mask to TE's `True=masked` convention only when its dtype is `torch.int64`. A boolean mask or `int32` mask representing the same valid positions bypasses conversion and reaches the TE layer at line 260 with inverted meaning (or an unsupported integer dtype). The comment at line 246 explicitly states TE's required convention. **Fix:** normalize supported 2-D padding masks by value, independent of integer/bool dtype, before passing them to TE; distinguish any already-inverted TE mask explicitly if that is supported.

3. **Medium — Per-sequence padding misattributes masked tokens during ESM2 THD token dropout.** `models/esm2/modeling_esm_te.py:740-744` uses the unpadded `cu_seq_lens_q` offsets to partition `input_ids` even when `cu_seq_lens_q_padded` is present. `models/esm2/collator.py:213-226` inserts padding *between* sequences and supplies both offset arrays. With original lengths `[3, 3]` padded to `[4, 4]`, the second real sequence begins at index 4, but the dropout code counts indices 3–5 as its tokens. A mask token at index 6 is omitted, so the scale factor is wrong for that sequence, changing model activations and training behavior. The code's own comment at line 739 says it must count masked tokens in each sequence in the padded batch. **Fix:** partition the padded IDs using `cu_seq_lens_q_padded`, then count masked tokens within each segment while dividing by the corresponding unpadded lengths.

4. **Low — Fully masked ESM2 sequences produce NaN embeddings.** In `models/esm2/modeling_esm_te.py:713-717` and `:740-745`, a sequence whose valid tokens are all the mask token has `mask_ratio_observed == 1`; the scale becomes infinite. `forward` zeroes those token embeddings at lines 780–785, then multiplies `0 * inf`, yielding NaNs that propagate through the model. Such a sequence is a valid unusual MLM input; the documented purpose is to scale unmasked embeddings, of which there are none. **Fix:** avoid division by zero, for example use a finite factor for sequences with no unmasked tokens, preserving their zero embeddings. Apply this to both BSHD and THD paths.

The checkout has no importable `torch` in the available Python environment, so these findings were checked by tracing the local code and its stated tensor conventions rather than running model tests.

## Files read

- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/README.md`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
