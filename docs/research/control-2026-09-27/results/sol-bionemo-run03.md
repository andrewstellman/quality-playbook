model: gpt-6-sol
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:28:53 UTC; finished 2026-09-28 23:30:35 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review — `models/amplify/src/amplify/`, `models/esm2/`

Checkout: `11701476b005ca7bc489df924a398b8f12453f0b`

## Findings

1. **High — The AMPLIFY Hugging Face masked-LM wrapper cannot run.** `models/amplify/src/amplify/amplify_hf.py:392` reads `outputs.last_hidden_state`, but `AMPLIFY.forward` returns `MaskedLMOutput` containing `logits`, `hidden_states`, and `attentions` at lines 387–402. A normal `AMPLIFYForMaskedLM(...)(input_ids)` therefore raises `AttributeError`. Even substituting `outputs.logits` would feed a `[batch, sequence, vocab_size]` tensor into the wrapper's decoder, which expects `hidden_size` features (lines 327 and 387); the defaults are 27 versus 960. The wrapper's own docstring says its forward pass returns masked-LM logits. **Fix:** make the base `AMPLIFY` return hidden features for the wrapper to decode, or remove the extra decoder and return the base masked-LM output directly, preserving labels and hidden-state behavior.

2. **Medium — Boolean attention masks have their meaning reversed in AMPLIFY TE.** `models/amplify/src/amplify/amplify_te.py:245–247` inverts only `int64` masks. For a standard boolean mask with `True` at valid tokens and `False` at padding, the mask is passed unchanged into Transformer Engine, where the adjacent comment explicitly says `True` means *masked*. This hides real tokens and exposes padding during attention; `int32` 0/1 masks are likewise not converted to the required boolean polarity. **Fix:** normalize all supported 0/1 or boolean input masks with `~attention_mask.to(torch.bool)` before passing them to TE, and validate unsupported mask forms explicitly.

3. **Medium — Packed ESM-2 token-dropout counts use unpadded boundaries on padded tokens.** `models/esm2/modeling_esm_te.py:741` constructs jagged sequences from the padded `input_ids` with `cu_seq_lens_q`, whose offsets are for the original unpadded tokens. The collator's `_pad_sequences_to_be_divisible_by` at `models/esm2/collator.py:213–225` explicitly replaces `input_ids` with tokens padded *between* sequences while retaining the original offsets and adding `cu_seq_lens_q_padded`. For two length-3 sequences padded to length 4, the unpadded offsets `[0, 3, 6]` select the second sequence as positions 3–5: its first position is actually padding, and its final real token at position 6 is omitted. If that omitted token is masked, the second sequence gets the wrong scale factor, contrary to `_apply_token_dropout_thd`'s stated per-sequence mask-ratio behavior. **Fix:** count masked tokens using `cu_seq_lens_q_padded` as physical boundaries while excluding padding from the numerator and using the original lengths for the denominator.

## Files read

- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state.py` (part)
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/README.md` (part)
- `models/esm2/collator.py` (part)
- `models/esm2/convert.py` (part)
- `models/esm2/modeling_esm_te.py`
- `models/esm2/state.py` (part)
