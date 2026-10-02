model: gpt-5.6-terra
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:55:11 UTC; finished 2026-09-28 23:57:21 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review: bionemo recipes — AMPLIFY and ESM2

Reviewed commit `11701476b005ca7bc489df924a398b8f12453f0b` in the requested scope.

## Defects

1. **High — pre-padded features produce invalid THD sequence metadata**

   - **File / lines:** `models/esm2/collator.py:165-170`, `models/esm2/collator.py:706-724`
   - **Trigger:** Pass `DataCollatorWithFlattening` features which already have right-padding and an `attention_mask`, such as batches tokenized with `padding="max_length"`.
   - **What goes wrong:** The input and labels inserted into `packed_batch` are compacted with `bshd_batch["attention_mask"].bool()` (lines 169-170), so every zero-mask token is removed.  But `_pt_flatten_collate(features)` builds `sample_lengths` from `len(sample["input_ids"])` and derives `cu_seq_lens_q/k` from those untrimmed lengths (lines 706-724).  Consequently `cu_seq_lens_q[-1]` is larger than the packed `input_ids` length, and its boundaries no longer identify the actual sequences.  The THD model path passes that metadata to Transformer Engine as cumulative sequence lengths, so Flash Attention either rejects the batch or uses wrong sequence boundaries.
   - **Why this is wrong:** The collator’s own documentation says features may contain `attention_mask` and promises that the output’s `cu_seq_lens_q/k` preserves packed sequence boundaries.  The two representations must therefore describe the same flattened token stream.
   - **Suggested fix:** Derive the flattened token stream and `sample_lengths` from each feature’s valid (`attention_mask == 1`) positions, or reject pre-padded features.  In either case, construct `cu_seq_lens_*` from the same per-sample valid lengths used to build `masked_input_ids`.

2. **Medium — boolean attention masks have their semantics inverted in the Transformer Engine AMPLIFY model**

   - **File / lines:** `models/amplify/src/amplify/amplify_te.py:244-247`
   - **Trigger:** Call `AMPLIFY` or `AMPLIFYForMaskedLM` with a standard boolean Hugging Face attention mask, where `True`/`1` denotes a real token and `False`/`0` denotes padding.
   - **What goes wrong:** The code correctly states that Transformer Engine expects `True` to mean “masked,” and inverts an `int64` mask.  A boolean mask bypasses that branch and is passed unchanged to every TE layer.  Valid tokens are then masked while padding tokens are attended to.  Float and integer mask types other than `int64` similarly bypass the conversion.
   - **Why this is wrong:** The forward argument is documented simply as an attention-mask tensor, while the non-TE AMPLIFY implementation accepts the conventional 1/0 form regardless of its tensor dtype (`amplify_hf.py:359-368`).  The TE implementation’s comment establishes the required inverse convention but applies it only to one dtype.
   - **Suggested fix:** Normalize all conventional binary masks before the TE call, for example `attention_mask = ~attention_mask.to(torch.bool)` when a mask is supplied (with validation or a separate branch if additive masks are intentionally supported).

3. **Low — AMPLIFY HF-to-TE conversion fails for half/bfloat16 checkpoints or GPU-resident source weights**

   - **File / lines:** `models/amplify/src/amplify/state_dict_convert.py:85-91`
   - **Trigger:** Call `convert_amplify_hf_to_te` on a model loaded with `torch_dtype=torch.float16`/`torch.bfloat16`, or after moving the source model to CUDA.
   - **What goes wrong:** `_pad_weights` creates padding using bare `torch.zeros(...)`, which always creates a CPU `float32` tensor.  Concatenating it with a half/bfloat16 source tensor raises a dtype error; concatenating it with a CUDA source tensor raises a device error.  This blocks conversion whenever vocabulary padding is needed.
   - **Why this is wrong:** The converter accepts an arbitrary `nn.Module` and the surrounding export/load code supports dtype-controlled model loading.  The equivalent ESM2 converter explicitly preserves both `source_embed.dtype` and `source_embed.device` in its padding allocation (`models/esm2/convert.py:238-246`).
   - **Suggested fix:** Allocate the added rows from the source tensor’s options, e.g. `source_embed.new_zeros((num_padding_rows, source_embed.size(1)))`.

## Files read

- `models/amplify/src/amplify/__init__.py`
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
