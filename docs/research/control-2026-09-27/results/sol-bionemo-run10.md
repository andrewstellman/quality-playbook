model: gpt-6-sol
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:45:23 UTC; finished 2026-09-28 23:47:10 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review — `11701476b005ca7bc489df924a398b8f12453f0b`

## Findings

1. **Medium — Boolean AMPLIFY attention masks are used with the opposite meaning** (`models/amplify/src/amplify/amplify_te.py:245`). The conversion from a Hugging Face mask (1/`True` means valid token) to a TE mask (`True` means masked, as the adjacent comment states) runs only for `torch.int64`. If a caller passes the same mask as a boolean tensor, valid tokens remain `True` and are masked, while padding remains `False` and can be attended to. The original HF implementation in `amplify_hf.py:360-361` also treats 1 as valid, confirming the public mask convention. Convert every supplied binary attention mask with `attention_mask = ~attention_mask.to(torch.bool)`, regardless of its original dtype.

2. **Medium — Packed ESM token-dropout scaling counts the wrong sequence after per-sequence padding** (`models/esm2/modeling_esm_te.py:741`). `DataCollatorWithFlattening._pad_sequences_to_be_divisible_by` inserts padding between sequences and retains the unpadded `cu_seq_lens_q` alongside `cu_seq_lens_q_padded` (`models/esm2/collator.py:213-226`). The model then partitions the *padded* `input_ids` with unpadded offsets. For two three-token sequences padded to four tokens each, offsets `[0,3,6]` count the second sequence as `[first padding token, first two tokens of sequence 2]` and omit its last token. If that last token is masked, the second sequence receives the wrong scale factor. Use padded offsets to locate each sequence in the padded tensor, then count masks only through each sequence's original length before computing the ratio.

3. **Medium — Flattening a feature with an attention mask can produce inconsistent token lengths and attention metadata** (`models/esm2/collator.py:165-170`). The documented input permits an `attention_mask`, but `_pt_flatten_collate` builds cumulative lengths from the full `input_ids` lists (`collator.py:706-720`), while `__call__` removes every zero-mask token from `masked_input_ids` and `masked_labels`. For pre-padded features such as `input_ids=[5,6,1]`, `attention_mask=[1,1,0]`, the resulting packed IDs have length 2 but `cu_seq_lens_q[-1]` is 3. The attention kernel receives boundaries beyond the actual token tensor; optional padding can also be computed from the wrong structure. Compute cumulative lengths and all accompanying fields from the selected valid tokens, or reject features containing masked positions before packing.

## Files read

- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
