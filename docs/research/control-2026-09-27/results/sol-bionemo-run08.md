model: gpt-6-sol
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:40:42 UTC; finished 2026-09-28 23:42:40 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; torch reproductions unavailable
interruptions or errors: torch unavailable in local Python environment
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review (11701476b005ca7bc489df924a398b8f12453f0b)

## Findings

1. **Medium — Packed lengths disagree with the tensors for pre-padded features.** `models/esm2/collator.py:161-174` takes `masked_input_ids` and `masked_labels` only where the padded MLM collator's attention mask is true, but `_pt_flatten_collate` at lines 708-723 computes `cu_seq_lens_q` from the full lengths of the original `input_ids`. For a feature `input_ids=[0,5,1]`, `attention_mask=[1,1,0]`, the packed tensors have two tokens while the cumulative length says three. This contradicts the collator's documented contract that cumulative lengths delineate the packed tensor (lines 43-48, 120-133) and can make THD attention read past the tensor or segment subsequent examples incorrectly. **Fix:** derive lengths and all packed metadata from the same attention-mask-filtered tokens used for `input_ids`/`labels`, or reject features that already contain padding.

2. **Medium — THD token dropout counts masks from the wrong sequences when each sequence is padded.** `models/esm2/modeling_esm_te.py:740-744` creates `is_masked` from the physically padded `input_ids`, then segments it with the *unpadded* `cu_seq_lens_q` offsets. `DataCollatorWithFlattening._pad_sequences_to_be_divisible_by` (`models/esm2/collator.py:220-227`) inserts padding between sequences and provides separate `cu_seq_lens_q_padded`. For original sequence lengths `[3,3]` padded to `[4,4]`, the second unpadded interval `[3,6)` includes the first sequence's pad and misses the second sequence's last token. Thus its observed mask ratio and embedding scale are wrong; a mask at that last token is not counted. The method's own documentation says scaling is per sequence (lines 719-723). **Fix:** count masks over the padded intervals from `cu_seq_lens_q_padded`, excluding pad tokens when computing the numerator, while retaining the original lengths for the denominator.

3. **Medium — Causal label shifting crosses packed-sequence boundaries.** `models/esm2/collator.py:410-412` shifts the entire flattened `labels` tensor by one position when `is_causal_lm=True`. With two sequences packed as `[a,b,c,d]` and cumulative lengths `[0,2,4]`, the label for `b` becomes `c`, the first token of a different sequence, although the flattening collator promises that cumulative lengths preserve separate sequence boundaries (lines 75-79). This trains a cross-sequence prediction that the attention kernel cannot make because it isolates the sequences. `separator_id` is optional and defaults to `None` (line 93), so it does not normally prevent this. **Fix:** after shifting, set each sequence's final-token label to `-100` using the cumulative boundaries, including any padded-boundary handling.

4. **Medium — AMPLIFY TE handles only one integer attention-mask dtype.** `models/amplify/src/amplify/amplify_te.py:245-247` converts a Hugging Face style mask (`1` means valid, `0` means padding) to TE's opposite boolean convention only when `dtype is torch.int64`. An otherwise identical `torch.int32` or boolean `attention_mask` is passed to TE unchanged at line 260, so it either has the wrong polarity or an unsupported dtype, causing valid tokens to be masked and pad tokens to be attended. The adjacent comment explicitly establishes TE's `True`-means-masked convention. **Fix:** normalize all supported 0/1 mask dtypes with `~attention_mask.bool()`; reject unsupported mask representations explicitly.

## Verification and files read

These findings follow directly from tensor lengths, indexing, and mask conventions in the checkout. I could not execute Torch reproductions because `python3` in this environment has no `torch` module (`ModuleNotFoundError`). I did not modify the checkout or use the network.

Files read: `models/esm2/modeling_esm_te.py`, `models/esm2/collator.py`, `models/esm2/convert.py`, `models/esm2/export.py`, `models/esm2/README.md` (first 120 lines), `models/amplify/src/amplify/amplify_hf.py`, `models/amplify/src/amplify/amplify_te.py`, `models/amplify/src/amplify/rotary.py`, `models/amplify/src/amplify/rmsnorm.py`, `models/amplify/src/amplify/metrics.py`, `models/amplify/src/amplify/state_dict_convert.py`, `models/amplify/src/amplify/export.py`, and `models/amplify/src/amplify/state.py` (lines 80-240).
