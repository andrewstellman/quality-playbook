# Code review: bionemo-recipes @ 11701476b005ca7bc489df924a398b8f12453f0b

Scope: `models/amplify/src/amplify/`, `models/esm2/` (excluding tests).

Nothing could be run. PyTorch and TransformerEngine are not installed in this environment, so every finding below comes from reading the code. Each one cites the code or comment that shows what the intended behaviour is.

---

## 1. ESM-2 THD token-dropout counts masked tokens in the wrong windows when sequences are padded individually

- **File/line:** `models/esm2/modeling_esm_te.py:734-744` (`NVEsmEmbeddings._apply_token_dropout_thd`), specifically line 741.
- **What goes wrong:** `DataCollatorWithFlattening` can be built with `pad_sequences_to_be_divisible_by`. In that case `_pad_sequences_to_be_divisible_by` (`collator.py:204-227`) puts padding tokens after each sequence inside `input_ids` and emits `cu_seq_lens_q_padded`. `cu_seq_lens_q` keeps the boundaries without padding. Line 741 then splits the padded `is_masked` vector using the unpadded offsets:
  `torch.nested.nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"])`
  Every sequence after the first is counted over a window that is shifted left by the padding accumulated before it. That window takes in the tail of the previous sequence and its padding, and it misses the last tokens of the sequence itself. As a result, `n_masked_per_seq` and `scale_factor` are wrong for those sequences. Line 744 then spreads the wrong factors over the padded layout using `src_lengths_padded`. There is no error; the embedding scaling is just silently wrong.
- **Why it is wrong:** The comment on line 739 says "We need to find the number of masked tokens in each sequence in the padded batch". The same function already handles the padded layout correctly for `repeat_interleave` (lines 735-738, 744), and the docstring says it handles `cu_seq_lens_q_padded`. Only the counting step ignores the padded offsets. `token_dropout` is `True` in the ESM-2 configs. The existing CP tests (`test_cp_thd.py`, `test_cp_bshd.py`) turn it off, and no test combines token dropout with per-sequence padding.
- **Trigger:** An ESM-2 TE model with `attn_input_format="thd"`, `token_dropout=True`, and batches from `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=N)` where any sequence needs padding.
- **Severity:** Medium. It silently changes training and inference numerics.
- **Fix:** Count masks over the padded offsets. Keep the unpadded lengths as the denominator:
  ```python
  offsets = kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])
  n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=offsets).sum(1)
  mask_ratio_observed = n_masked_per_seq.float() / src_lengths
  ```
  This is correct because padding tokens are never the mask token.

## 2. AMPLIFY TE model only converts `int64` attention masks; a bool (or int32/float) mask is passed to TE with the opposite meaning

- **File/line:** `models/amplify/src/amplify/amplify_te.py:245-247`.
- **What goes wrong:**
  ```python
  if attention_mask is not None and attention_mask.dtype is torch.int64:
      # TE expects a boolean attention mask, where "True" indicates a token to be masked.
      attention_mask = ~attention_mask.to(bool)
  ```
  The inversion only runs for `int64`. Suppose a caller passes the usual HF mask (1/True = attend) as a `bool` tensor. It reaches TE unchanged, and TE reads `True` as "masked". Real tokens are then masked out and padding is attended to, with no error. An `int32` or float mask is also passed through without conversion, with the same wrong meaning or a dtype failure inside TE.
- **Why it is wrong:** The comment states TE's convention (True = masked). The model's own HF reference (`amplify_hf.py:360-361`) treats any mask as 1/True = attend, whatever the dtype, so the two implementations disagree on the same input. The ESM-2 TE model handles this for any dtype by going through `AttentionMaskConverter.to_4d(...) < -1` (`modeling_esm_te.py:497-502`).
- **Severity:** Medium. Output is silently wrong for callers who build bool masks.
- **Fix:** Convert every non-None mask: `attention_mask = ~attention_mask.to(torch.bool)`. If the goal was to accept masks that are already in TE form, document that and add a separate flag, rather than keying the behaviour on dtype.

## 3. AMPLIFY HF→TE conversion builds padding rows as CPU float32 no matter what the source dtype or device is

- **File/line:** `models/amplify/src/amplify/state_dict_convert.py:85-91` (`_pad_weights`, used for `encoder.weight` and `decoder.weight`).
- **What goes wrong:** `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))` is always float32 on CPU.
  - If the source model is on GPU, `torch.cat` fails with a device mismatch.
  - If the source is bf16 or fp16, `torch.cat` promotes the embedding and decoder weights to float32. `apply_transforms` then swaps in float32 parameters, and its dtype check (`state.py:232-237`) fails with `dtype mismatch for key amplify.encoder.weight`. That check runs whenever the target was built in bf16/fp16, which happens when `te_config.dtype` is taken from the HF config.
- **Why it is wrong:** The ESM-2 copy of the same helper already fixes this: it passes `dtype=source_embed.dtype, device=source_embed.device` (`models/esm2/convert.py:243-245`). `_pad_bias` in the same AMPLIFY file also honours dtype and device (lines 113-115).
- **Severity:** Low. The default export path loads fp32 on CPU and works; any other source placement or precision breaks.
- **Fix:** `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

## 4. AMPLIFY TE model ignores `att_bias` / `ffn_bias`; conversion silently drops those biases

- **File/line:** `models/amplify/src/amplify/amplify_te.py:189` (`bias=False` hard-coded in `TransformerLayer`), together with the `mapping` in `state_dict_convert.py:27-34`.
- **What goes wrong:** `AMPLIFYConfig` has `att_bias` and `ffn_bias` fields (documented at lines 82-83), and the HF model honours them (`amplify_hf.py:128-143, 160, 167-173`). The TE model always builds the layers without bias. Converting a checkpoint with `att_bias=True` or `ffn_bias=True` leaves the source `q/k/v/wo` and `ffn` bias tensors unmapped. `apply_transforms` never complains about unmapped source keys, so the result is a TE model with those biases missing. It runs, but it computes a different function from the source model.
- **Why it is wrong:** The config documents these fields as controlling bias, and the TE model disregards them without any warning.
- **Severity:** Low. The published AMPLIFY checkpoints use `False` for both.
- **Fix:** Either pass `bias=config.att_bias or config.ffn_bias` and add the bias mappings and packing (the QKV bias would need interleaving like `_pack_qkv_bias` in ESM), or raise in `AMPLIFY.__init__` when either flag is `True`.

## 5. AMPLIFY TE `layer_norm_before_last_layer=False` path cannot be converted and skips vocab padding

- **File/line:** `models/amplify/src/amplify/amplify_te.py:298-301` and `state_dict_convert.py:99-102`.
- **What goes wrong:** With `layer_norm_before_last_layer=False`, the decoder is `Linear(hidden_size, config.vocab_size)`. The converter still pads `decoder.weight` and `decoder.bias` to `padded_vocab_size`, so `apply_transforms` raises `Shape mismatch for parameter decoder.weight` for any config where `padded_vocab_size != vocab_size` (the defaults are 32 vs 27). This branch also leaves out the `padded_vocab_size` output that the config says is there "to support fp8" (line 81).
- **Severity:** Low. The shipped configs do not use this path.
- **Fix:** Use `config.padded_vocab_size` for the `Linear` in the `else` branch. `forward` already slices logits back to `vocab_size` at lines 345-346.

## 6. AMPLIFY HF reference model: padding mask is always bf16, so SDPA fails for fp32/fp16 models

- **File/line:** `models/amplify/src/amplify/amplify_hf.py:361` and the SDPA call at 264-270. This file is copied from upstream chandar-lab.
- **What goes wrong:** `attention_mask = torch.where(...).to(torch.bfloat16)` is hard-coded. `scaled_dot_product_attention` (the CPU branch) only accepts an `attn_mask` that is bool, float32, or the same dtype as the query. An fp16 model with a padding mask on CPU therefore fails. The CUDA branch passes the same bf16 bias to xformers `memory_efficient_attention`, which requires the bias dtype to match the query, so an fp32 or fp16 model on GPU fails there too.
- **Severity:** Low. This is the reference implementation and the tests use it in bf16.
- **Fix:** `.to(x.dtype)` (or the embedding weight dtype) instead of `torch.bfloat16`.

---

## Items looked at and not reported (no confirmed defect)

- QKV packing and unpacking in both converters, checked against TE's `qkv_weight_interleaved=True` layout.
- The xformers SwiGLU `w12` ordering against TE's `fc1` split.
- Interleaved RoPE (AMPLIFY) against TE's `interleaved=True`.
- The logits slice followed by `.view` (it still works on the non-contiguous slice).
- `separator_id` labelling for causal LM together with the CP label shift.
- `TokenPackingDataset` split and padding arithmetic.
- CP zigzag sharding for THD and BSHD.
- `_pt_pad_to_multiple_of`.
- The `_match_keys` / `StateDictTransform` machinery for the patterns actually used.

## Files read

- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state.py` (compared by diff with `models/esm2/state.py`; the only difference is the copied-file header)
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/state.py`
- `models/esm2/README.md` (first lines only)
- Grep only, for context on test coverage: `models/esm2/tests/*.py`
