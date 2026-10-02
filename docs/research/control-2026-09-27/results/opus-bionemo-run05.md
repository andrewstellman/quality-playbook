# Code review: bionemo-recipes @ 11701476 — `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

Reviewer: opus (run05). I read the code statically. Nothing was executed, because torch and transformer_engine are not installed here.

## Defects

### 1. THD token-dropout uses unpadded offsets on padded packed input (medium)

- **File/line:** `models/esm2/modeling_esm_te.py:734-744` (`NVEsmEmbeddings._apply_token_dropout_thd`), specifically line 741.
- **What goes wrong:** When the batch comes from `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=...)` (`collator.py:204-227`), `input_ids` are laid out using the *padded* offsets `cu_seq_lens_q_padded`, because each sequence is followed by its pad tokens. The per-sequence count of masked tokens is still computed with
  `torch.nested.nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"])`, which uses the *unpadded* offsets. From the second sequence on, the window used for sequence *i* is `[c_i, c_{i+1})`, but the sequence actually sits at `[p_i, p_i + len_i)`. The window drifts by the accumulated padding, so mask tokens get counted against the wrong sequence or dropped from the count. `offsets[-1]` is also smaller than `is_masked.numel()`, which leaves trailing values uncovered. As a result `mask_ratio_observed` and `scale_factor` are wrong for every sequence after the first.
- **Why it's wrong:** The function explicitly handles `cu_seq_lens_q_padded` (lines 735-738) and uses the padded lengths for `repeat_interleave`. That shows padded THD input is meant to be supported. The docstring says the function computes "per-sequence mask ratios".
- **Fix:** Split with the padded offsets and divide by the real lengths:
  ```python
  offsets = kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])
  n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=offsets).sum(1)
  mask_ratio_observed = n_masked_per_seq.float() / src_lengths
  ```
  Pad tokens are never the mask token, so counting over the padded span gives the right numerator.

### 2. AMPLIFY TE model only converts the HF attention mask when its dtype is int64 (medium)

- **File/line:** `models/amplify/src/amplify/amplify_te.py:245-247`
- **What goes wrong:** `if attention_mask is not None and attention_mask.dtype is torch.int64: attention_mask = ~attention_mask.to(bool)`. Any other dtype passes through to TE unchanged. That includes a `bool` mask where True means attend, an int32 mask, or a float mask of 1s and 0s. TE reads True/non-zero as **masked** (as the comment on line 246 says), so the model hides exactly the real tokens and attends to the padding. The output is silently wrong.
- **Why it's wrong:** The docstring describes `attention_mask` as the standard HF attention mask. The HF reference implementation this model mirrors (`amplify_hf.py:360-361`) accepts any dtype and treats `== 1` as attend. The TE model should apply the same meaning whatever the dtype.
- **Fix:** Normalize every non-None mask: `attention_mask = ~attention_mask.to(torch.bool)`. If callers are allowed to pass a TE-convention bool mask directly, handle that as an explicit, documented case.

### 3. AMPLIFY `_pad_weights` builds its padding rows as float32 on the CPU (low-medium)

- **File/line:** `models/amplify/src/amplify/state_dict_convert.py:87-91`
- **What goes wrong:** `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))` has no `dtype` or `device`. Two cases break:
  - If the source HF model is on GPU, `torch.cat` fails with a device mismatch.
  - If the source is bf16 or fp16, type promotion makes the result float32. `apply_transforms` then fails its final dtype assertion (`state.py:232-237`, "dtype mismatch for key amplify.encoder.weight"), because the target TE model was built with `te_config.dtype`, which comes from the HF config.
- **Why it's wrong:** The equivalent ESM-2 function (`models/esm2/convert.py:238-246`) already passes `dtype=source_embed.dtype, device=source_embed.device`. The AMPLIFY copy is missing that fix.
- **Fix:** `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

### 4. AMPLIFY TE decoder without the final LayerNorm is inconsistent with the padded vocab and with the converter (low)

- **File/line:** `models/amplify/src/amplify/amplify_te.py:298-301`, together with `state_dict_convert.py:156-163, 228-246`
- **What goes wrong:** When `layer_norm_before_last_layer=False`, the decoder is `Linear(hidden_size, config.vocab_size)`, but the LayerNorm branch uses `config.padded_vocab_size`. Two problems follow:
  - The converter always pads `decoder.weight` and `decoder.bias` to `padded_vocab_size`, so conversion fails with "Shape mismatch for parameter decoder.weight".
  - The mapping `layer_norm_2.weight -> decoder.layer_norm_weight` has no target key, so `StateDictTransform` raises "No matches found".

  An unpadded vocab of 27 also defeats the FP8 alignment that `padded_vocab_size` exists for ("The padded vocabulary size of the model to support fp8", line 81).
- **Fix:** Use `config.padded_vocab_size` in the non-LN branch too, and apply the same `init_method`. In the converter, map `layer_norm_2.weight` only when `layer_norm_before_last_layer` is True. The released AMPLIFY checkpoints use True, so they are not affected.

### 5. HF reference AMPLIFY hard-codes a bf16 attention mask, so fp32 inference with padding fails (low)

- **File/line:** `models/amplify/src/amplify/amplify_hf.py:361`, used at lines 255-270
- **What goes wrong:** The additive mask is always cast to `torch.bfloat16`. For a model running in float32:
  - On CPU, `scaled_dot_product_attention` rejects a mask whose dtype is neither bool, float32, nor the query dtype (bf16 vs fp32 query).
  - On GPU, xformers `memory_efficient_attention` requires `attn_bias` to match the query dtype.

  So any padded batch fails on a float32 model.
- **Fix:** Cast with `.to(x.dtype)`, or to the encoder's weight dtype, instead of `torch.bfloat16`. The code is inherited from upstream chandar-lab, but it is in scope.

### 6. `_pad_sequences_to_be_divisible_by` leaves `attention_mask` / `position_ids` at unpadded length (low)

- **File/line:** `models/esm2/collator.py:204-227`
- **What goes wrong:** `input_ids` and `labels` are replaced with per-sequence padded versions, but `attention_mask` (built in `_pt_flatten_collate` when the features contain it) and `position_ids` (when `return_position_ids=True`) keep the unpadded length and layout. The batch then holds tensors that no longer line up token for token. `DataCollatorForContextParallel` pops `attention_mask` (line 408) but not `position_ids`, and never shards `position_ids`. Any consumer that uses them (HF flash-attention paths, custom models) gets misaligned data.
- **Why it's wrong:** `_pt_pad_to_multiple_of` (lines 915-923), the other padding path in the same collator, does update `attention_mask` and `position_ids`. The two padding modes are inconsistent.
- **Fix:** Rebuild `attention_mask` (1 for real tokens, 0 for pads) and `position_ids` (restart at 0 for each padded sequence) from `cu_seq_lens_q` and `cu_seqlens_padded`, or drop both keys.

### 7. `DataCollatorForContextParallel` crashes on THD batches that have no `cu_seq_lens_q_padded` (low)

- **File/line:** `models/esm2/collator.py:417, 432-434`
- **What goes wrong:** Line 417 uses `batch.get("cu_seq_lens_q_padded", None)`, which tolerates the key being absent. But for `qkv_format == "thd"`, line 433 indexes `batch_shard["cu_seq_lens_q_padded"]` directly. With `cp_world_size == 1` (a TP-only mesh), `_split_batch_by_cp_rank` returns early without error, then line 433 raises `KeyError` whenever the wrapped collator used `pad_to_multiple_of` or no padding.
- **Fix:** Fall back to `cu_seq_lens_q` when the padded key is missing, or validate in `__post_init__` or `__call__` with a clear error message.

## Considered and not reported

- The QKV pack/unpack interleaving is consistent with `qkv_weight_interleaved=True`.
- The CP/TP shard replication ordering is correct.
- The split logic in `TokenPackingDataset` holds up. I checked that a sample can never fit entirely inside `tokens_available`.
- The label shift in the causal-LM CP path and the `separator_id` placement are correct.
- The `StateDictTransform` matching logic has no bugs I'm confident of.
- Token dropout with context parallelism is a known incompatibility (`recipes/esm2_native_te/train_ddp_cp.py:93`), so I did not report it.
- `TransformFns.merge_qkv_bias` and `split_qkv_bias` use Megatron config fields (`num_query_groups`, `kv_channels`), while `merge_qkv` uses HF fields. Neither function is used in scope, so I did not report it.

## Files read

- models/amplify/src/amplify/__init__.py
- models/amplify/src/amplify/rmsnorm.py
- models/amplify/src/amplify/metrics.py
- models/amplify/src/amplify/rotary.py
- models/amplify/src/amplify/export.py
- models/amplify/src/amplify/state_dict_convert.py
- models/amplify/src/amplify/amplify_hf.py
- models/amplify/src/amplify/amplify_te.py
- models/amplify/src/amplify/state.py (diffed against esm2/state.py: identical apart from the copied-file header)
- models/esm2/state.py
- models/esm2/convert.py
- models/esm2/export.py
- models/esm2/modeling_esm_te.py
- models/esm2/collator.py
- Grep only, for context: models/esm2/tests/test_modeling_esm_te.py, models/esm2/tests/test_cp_*.py, models/amplify/tests/test_encoder_block.py, recipes/esm2_native_te/train_ddp_cp.py

I did not review the non-Python files in models/esm2 (tokenizer JSON, README, Dockerfile, requirements, template).
