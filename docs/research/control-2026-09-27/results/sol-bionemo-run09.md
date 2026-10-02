model: gpt-6-sol
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:43:00 UTC; finished 2026-09-28 23:45:16 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; PyTorch checks unavailable
interruptions or errors: torch not installed
network access attempted (yes/no, and what): no attempt reported

# BioNeMo code review

Scope: `models/amplify/src/amplify/` and `models/esm2/` at `11701476b005ca7bc489df924a398b8f12453f0b`, excluding tests. I did not modify the checkout. Runtime verification was unavailable because this environment has no `torch` installation; the findings below follow directly from the code paths.

## Findings

1. **Medium — Padded THD sequences receive the wrong token dropout scale.** `models/esm2/modeling_esm_te.py:741` counts mask tokens in the already padded `input_ids`, but partitions them with the original, unpadded `cu_seq_lens_q`. For two length-three sequences padded to length four, the offsets remain `[0, 3, 6]` while the second sequence actually occupies padded positions `[4, 7]`. A masked token at position 6 is omitted from the second sequence's mask count; its ratio and scaling factor are then wrong. `DataCollatorWithFlattening._pad_sequences_to_be_divisible_by` explicitly retains original offsets while adding `cu_seq_lens_q_padded` (`models/esm2/collator.py:213-225`), and the dropout method says it computes a per-sequence mask ratio in the padded batch. Count using padded offsets, while excluding each sequence's padding from both mask count and denominator.

2. **Medium — Standard boolean attention masks are inverted for AMPLIFY TE.** `models/amplify/src/amplify/amplify_te.py:245-247` converts only `torch.int64` masks from the public convention (`True`/`1` means a valid token) to Transformer Engine's convention (`True` means masked). Passing a boolean mask such as `[[True, True, False]]` leaves it unchanged and masks the two real tokens while exposing the padding token. The code's own comment states the TE convention, and the Hugging Face AMPLIFY path interprets `1` as valid (`models/amplify/src/amplify/amplify_hf.py:345-352`). Convert every supported integral/bool public mask by `~attention_mask.to(torch.bool)`; reject unsupported formats explicitly if needed.

3. **Medium — Conversion of a GPU AMPLIFY model fails when vocabulary padding is needed.** `models/amplify/src/amplify/state_dict_convert.py:90-91` creates padding rows on CPU with the default dtype, then concatenates them with the source embedding or decoder weight. `convert_amplify_hf_to_te` accepts an `nn.Module` without restricting its device (`:37-45`), and a CUDA source weight cannot be concatenated with these CPU rows. Lower-precision CPU source weights are also promoted to the default dtype, potentially failing the converter's dtype check. Create rows with `source_embed.new_zeros((num_padding_rows, source_embed.size(1)))`, as the ESM converter already does (`models/esm2/convert.py:238-246`).

4. **Medium — Restarting the context-parallel data loader can consume a batch from the new iterator in the old prefetch thread.** `models/esm2/collator.py:500-508` replaces `self._iterator` before calling `close()` to join the previous prefetch thread. That thread reads `self._iterator` in `_send_data_to_cp_tp_ranks` (`:551-576`). If iteration is restarted while prefetch is still running, the old thread can advance the newly assigned iterator, and the first batch of the new pass is lost. The wrapper's documented purpose is to distribute each dataloader batch; it must not skip one at restart. Join the old thread before assigning a new iterator, and ensure the old thread has stopped before beginning the next prefetch.

## Files read

- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state.py` (selected sections)
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/state.py` (selected sections)
