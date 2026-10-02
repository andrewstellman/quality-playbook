model: gpt-5.6-terra
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:45:23 UTC; finished 2026-09-28 23:48:51 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review — terra-bionemo-run01

## Findings

### Medium — THD token-dropout computes mask ratios against the wrong packed boundaries after CP padding

**File:** `models/esm2/modeling_esm_te.py:741`

`_apply_token_dropout_thd` builds its jagged `is_masked` tensor with
`cu_seq_lens_q`, even when the caller supplied `cu_seq_lens_q_padded` and the
physical `input_ids` tensor contains padding between sequences.  The function
then correctly uses the padded lengths at line 744 to expand the resulting
scale factors.  Those two choices describe different layouts.

For example, two three-token sequences padded to four tokens have physical
input positions `[seq1(3), pad, seq2(3), pad]`, while the unpadded offsets are
`[0, 3, 6]`.  Line 741 consequently groups the second sequence as
`[pad, seq2[0], seq2[1]]` and leaves `seq2[2]` outside the second group.  Its
masked-token count, observed mask ratio, and token-dropout scale are therefore
wrong.  The collator explicitly creates this layout: it replaces `input_ids`
with per-sequence-padded data and publishes `cu_seq_lens_q_padded` at
`models/esm2/collator.py:213-226`; the embedding implementation itself
acknowledges that padded offsets exist at lines 735-738.

This affects token-dropout-enabled ESM models using THD context parallelism
with `pad_sequences_to_be_divisible_by`: the affected sequences receive
incorrect embedding scaling during training or inference.

**Suggested fix:** use `cu_seq_lens_q_padded` as the offsets passed to
`torch.nested.nested_tensor_from_jagged` whenever it is supplied, while
retaining `torch.diff(cu_seq_lens_q)` as the denominator for each sequence's
real length.  The existing `repeat_interleave(..., src_lengths_padded)` then
continues to match the physical tensor layout.

## Files read

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
