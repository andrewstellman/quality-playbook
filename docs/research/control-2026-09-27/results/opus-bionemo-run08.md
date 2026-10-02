# Code review: bionemo-recipes @ 11701476 — `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

Reviewer: opus (run08). Scope checkout: `/tmp/control/bionemo` (read-only). No PyTorch in the sandbox, so nothing was executed against real modules. Finding 1 was checked with a small pure-Python simulation of the index arithmetic.

## Defects

### 1. THD token-dropout scaling counts masked tokens in the wrong windows when sequences are padded (`pad_between_seqs`)
- **File/line:** `models/esm2/modeling_esm_te.py:734-744` (`NVEsmEmbeddings._apply_token_dropout_thd`), specifically line 741.
- **What goes wrong:** When `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=N)` is used (the context-parallel / padded-THD path), `input_ids` is laid out in the *padded* layout. The collator sets only `cu_seq_lens_q_padded` to the padded offsets and leaves `cu_seq_lens_q` as the unpadded cumulative lengths (`collator.py:213-226`). Line 741 still slices the per-token `is_masked` vector with `offsets=kwargs["cu_seq_lens_q"]`, which are the unpadded offsets. For every sequence after the first, the window is shifted by the padding that came before it. The window picks up pad tokens and the tail of the previous sequence, and it misses the tail of the current sequence. `n_masked_per_seq`, `mask_ratio_observed` and `scale_factor` are therefore wrong for those sequences.
  - Example (simulated): sequences of length 5 and 6, each padded to 8, with 1 and 3 `<mask>` tokens. Counting with `cu_seq_lens_q=[0,5,11]` gives `[1, 1]`. Counting with `cu_seq_lens_q_padded=[0,8,16]` gives the correct `[1, 3]`.
- **Why it is wrong:** The comment on line 739 says the goal is "the number of masked tokens in each sequence in the padded batch". Line 744 already treats the data as padded (`repeat_interleave(..., src_lengths_padded)`), so the counting and the scaling use inconsistent layouts. The padded THD output is also supposed to match unpadded THD (`tests/common/test_modeling_common.py::test_golden_values_thd_padded`). That test does not catch the mismatch because its logits tolerance is `atol=2.0`, and it is xfail'd on non-datacenter GPUs.
- **Severity:** medium. The error is silent and changes embeddings and loss in padded-THD / context-parallel training whenever `token_dropout=True`, which is the default for the ESM-2 checkpoints.
- **Suggested fix:** When padded offsets are present, count with them and divide by the real lengths:
  ```python
  offsets = kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])
  n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=offsets).sum(1)
  mask_ratio_observed = n_masked_per_seq.float() / src_lengths   # real (unpadded) lengths
  ```
  Pad tokens are never `<mask>`, so counting over the padded window is exact.

### 2. AMPLIFY TE model inverts attention masks that are not `int64`
- **File/line:** `models/amplify/src/amplify/amplify_te.py:245-247`.
- **What goes wrong:** The HF-style mask (1 = attend) is converted to TE's convention (True = masked) only when `attention_mask.dtype is torch.int64`. A mask of any other type is passed to TE unchanged: a `bool` mask in HF convention (e.g. `mask.bool()`), an `int32` mask, or a float mask. TE then treats the real tokens as masked and the padding as visible, so attention is silently inverted.
- **Why it is wrong:** The reference implementation this file is adapted from (`amplify_hf.py:360-361`) interprets the mask by value (`attention_mask == 1` means attend) whatever its dtype. The `forward` docstring describes `attention_mask` simply as "The attention mask", with no dtype requirement. The comment on line 246 says TE needs a boolean mask where True means masked, but the code performs that conversion only for one input dtype.
- **Severity:** medium. The output is wrong with no error for any caller that passes a bool or int32 mask.
- **Suggested fix:** Convert by value for all non-bool dtypes (`attention_mask = attention_mask == 0`). Either document that bool masks must already be in TE convention, or better, always normalise with `attention_mask = ~attention_mask.to(torch.bool)` when the input follows the HF 1/0 convention.

### 3. AMPLIFY HF model builds a bfloat16 additive mask regardless of model dtype, so fp32 models with padding fail
- **File/line:** `models/amplify/src/amplify/amplify_hf.py:361` (the mask is consumed at lines 255-270).
- **What goes wrong:** The additive mask is hard-cast with `.to(torch.bfloat16)`. When the model runs in float32 (the default `from_pretrained` dtype) and a non-trivial `attention_mask` is supplied:
  - On CPU, `scaled_dot_product_attention` requires `attn_mask` to be bool, float32, or the same dtype as the query. A bf16 mask with fp32 queries raises a `RuntimeError`.
  - On GPU, xformers `memory_efficient_attention` likewise expects `attn_bias` to have the same dtype as the query.
- **Why it is wrong:** The mask dtype should follow the activations (`x.dtype` / `self.dtype`). Nothing in the config restricts the model to bf16.
- **Severity:** low (this is the vendored reference model, used mostly in bf16 tests, but it is in scope).
- **Suggested fix:** `.to(self.encoder.weight.dtype)` (or the dtype of `x`) instead of `torch.bfloat16`.

### 4. AMPLIFY `_pad_weights` builds padding rows on the CPU in float32, ignoring the source tensor's dtype and device
- **File/line:** `models/amplify/src/amplify/state_dict_convert.py:85-91` (line 90).
- **What goes wrong:** `torch.zeros(num_padding_rows, source_embed.size(1))` is always CPU/float32:
  - If the HF model is on a GPU, `torch.cat` of a CUDA tensor and a CPU tensor raises.
  - If the HF model is in bf16/fp16, `torch.cat` promotes the padded embedding and decoder weights to float32. The dtype-preservation assertion in `state.apply_transforms` (`state.py:233-237`) then fails, or the checkpoint silently changes dtype.
- **Why it is wrong:** The same helper in `models/esm2/convert.py:243-245` was fixed to pass `dtype=source_embed.dtype, device=source_embed.device`, and `_pad_bias` in the same AMPLIFY file (lines 113-115) already does this.
- **Severity:** low.
- **Suggested fix:** `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

### 5. `NVEsmEncoder` writes an implicit FP8 `layer_precision` into the shared config, which is then persisted
- **File/line:** `models/esm2/modeling_esm_te.py:185-187`.
- **What goes wrong:** When an `fp8_recipe` is passed without `layer_precision`, the encoder assigns `self.config.layer_precision = ["fp8"] * num_hidden_layers`. That config object is the model's `PretrainedConfig`, so `save_pretrained` writes `layer_precision: ["fp8", ...]` to `config.json`. A later load of that checkpoint with no recipe gets FP8 autocast in every layer: `get_autocast_context` (lines 321-325 and 337-340) warns "No FP8 recipe provided, using default recipe" and enables FP8. That load was meant to be a plain BF16 load, and it fails on GPUs without FP8 support.
- **Why it is wrong:** The `NVEsmConfig` docstring (lines 125-127) says `layer_precision=None` means "no quantization is configured". A runtime-only recipe argument should not permanently change the serialized configuration.
- **Severity:** low.
- **Suggested fix:** Keep the derived per-layer precision in an encoder attribute (e.g. `self._layer_precision`) instead of mutating `config`, or copy the config before mutating it.

### 6. `NVEsmConfig.padded_vocab_size` default contradicts its documentation
- **File/line:** `models/esm2/modeling_esm_te.py:88` versus the docstring at lines 119-120, and line 145.
- **What goes wrong:** The docstring says "If not provided, defaults to vocab_size", but the parameter default is `64`. Omitting it therefore gives 64, not `vocab_size`. For any config with `vocab_size > 64` that does not pass `padded_vocab_size` explicitly, the assertion at lines 148-151 fails. For smaller vocabularies, the checkpoint silently gets 64-row embedding and decoder matrices.
- **Severity:** low.
- **Suggested fix:** Default the parameter to `None`, so that `padded_vocab_size or self.vocab_size` applies as documented. Alternatively, round up to a multiple of 16/64 explicitly, and change the docstring to match.

## Considered and not reported
- The QKV packing and unpacking (`_pack_qkv_weight` / `_unpack_qkv_weight`) are consistent with `qkv_weight_interleaved=True`.
- The SwiGLU `w12` to `fc1_weight` mapping matches the TE `swiglu` chunk order.
- The zig-zag CP sharding in `collator.py` is consistent.
- The split arithmetic in `TokenPackingDataset` is correct, and `tokens_available` is always strictly between 0 and the sample length.
- The `ContextParallelDataLoaderWrapper` iterator-reset race is too speculative to report.

## Files read
- models/amplify/src/amplify/__init__.py
- models/amplify/src/amplify/amplify_te.py
- models/amplify/src/amplify/amplify_hf.py
- models/amplify/src/amplify/rmsnorm.py
- models/amplify/src/amplify/rotary.py
- models/amplify/src/amplify/metrics.py
- models/amplify/src/amplify/state_dict_convert.py
- models/amplify/src/amplify/export.py
- models/amplify/src/amplify/state.py (diffed against esm2/state.py; identical apart from the copy notice)
- models/esm2/state.py
- models/esm2/convert.py
- models/esm2/export.py
- models/esm2/modeling_esm_te.py
- models/esm2/collator.py
- For context only (outside the scope): models/esm2/tests/test_modeling_esm_te.py (`get_test_input_data`), models/esm2/tests/common/test_modeling_common.py (THD padded tests, tolerances), models/amplify/tests/test_encoder_block.py (mask usage)
