# Code review: bionemo-recipes @ 11701476 — `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

Reviewer: Opus (control run). Work was static reading plus small Python checks of language semantics. PyTorch, TE and xformers are not installed, so no model code was run.

## Defects

### 1. THD token-dropout counts masked tokens using unpadded offsets on padded-layout data (medium)

- **File/line:** `models/esm2/modeling_esm_te.py:734-744` (`NVEsmEmbeddings._apply_token_dropout_thd`)
- **What goes wrong:** This happens when a THD batch is produced by `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=N)` (`collator.py:204-227`) and `token_dropout=True`. That collator pads each sequence separately, so sequence *i* occupies `[cu_seq_lens_q_padded[i], cu_seq_lens_q_padded[i]+len_i)` in `input_ids`. The per-sequence mask count, however, is taken with
  `torch.nested.nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"])`, which uses the **unpadded** offsets. For every sequence after the first, the counting window starts too early. It takes in the previous sequence's trailing pad tokens and drops the last tokens of this sequence. As a result `n_masked_per_seq`, and so `scale_factor`, is wrong for those sequences. If `values` is longer than `offsets[-1]`, the nested-tensor construction may also reject the input outright.
- **Why wrong:** The function's own comment (line 739) says it must count masked tokens "in each sequence in the padded batch". The next line already uses `src_lengths_padded` to lay the scale factors over the padded layout (`repeat_interleave(scale_factor, src_lengths_padded)`). That means the code itself assumes the data is in padded layout, and the counting offsets disagree with it. The BSHD path and HF ESM compute the ratio over each sequence's own tokens.
- **Fix:** Build the jagged tensor with the padded offsets when they are present:
  ```python
  offsets = kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])
  n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=offsets).sum(1)
  ```
  Keep `src_lengths` (unpadded) as the denominator. Padding tokens are never `mask_token_id`, so counting over the padded window gives the correct count.

### 2. AMPLIFY HF→TE conversion pads embeddings/decoder with float32 CPU zeros regardless of source dtype/device (low–medium)

- **File/line:** `models/amplify/src/amplify/state_dict_convert.py:74` (`_pad_weights`)
- **What goes wrong:** `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))` is always float32 on the CPU.
  - If the source HF model is bf16/fp16, `torch.cat` promotes the padded tensor to float32. `apply_transforms` then fails its dtype-preservation assertion (`state.py:233-237`, "dtype mismatch for key amplify.encoder.weight").
  - If the source model is on CUDA, `torch.cat` raises a device-mismatch error.
- **Why wrong:** `apply_transforms` requires converted parameters to keep the target dtype. The ESM2 copy of the same helper was fixed for exactly this (`models/esm2/convert.py:243-245`, which passes `dtype=source_embed.dtype, device=source_embed.device`).
- **Fix:** `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

### 3. TE AMPLIFY inverts the attention mask for any non-int64 mask (low)

- **File/line:** `models/amplify/src/amplify/amplify_te.py:245-247`
- **What goes wrong:** The HF convention mask (1/True = attend) is converted to TE's convention (True = masked) only when `attention_mask.dtype is torch.int64`. A bool, int32 or float mask with the same HF meaning goes to TE unchanged. For a bool mask, TE then masks every real token and attends only to padding. For int32 or float masks, TE receives a non-boolean mask it doesn't expect.
- **Why wrong:** The model's documented input is an HF-style attention mask (docstring line 233: "The attention mask"), and the HF reference (`amplify_hf.py:360-361`) treats `attention_mask == 1` as "attend" whatever the dtype. The ESM2 model normalizes any dtype through `AttentionMaskConverter` (`modeling_esm_te.py:497-502`).
- **Fix:** Convert every HF-style mask: `attention_mask = ~attention_mask.to(torch.bool)`, or `attention_mask == 0`.

### 4. HF AMPLIFY reference builds a bf16 additive mask regardless of the activation dtype (low)

- **File/line:** `models/amplify/src/amplify/amplify_hf.py:361`
- **What goes wrong:** `torch.where(...).to(torch.bfloat16)` produces a bf16 mask even when the model runs in fp32.
  - On CPU, `scaled_dot_product_attention` (line 264) rejects a mask whose dtype is neither bool, float32, nor the query dtype.
  - On GPU, xformers `memory_efficient_attention` requires `attn_bias` to have the query's dtype.
  - So any fp32 (or fp16) forward pass with a real padding mask fails. Only bf16 works.
- **Why wrong:** The additive mask has to match the query dtype for both attention back-ends the code dispatches to.
- **Fix:** `.to(x.dtype)` after computing the embeddings, or `.to(self.encoder.weight.dtype)`.

### 5. `convert_*` helpers cannot override any key already in the source config (low)

- **File/line:** `models/esm2/convert.py:63` (`NVEsmConfig(**model_hf.config.to_dict(), **config_kwargs)`), `models/esm2/convert.py:102` (`EsmConfig(**filtered_config, **config_kwargs)`), `models/amplify/src/amplify/state_dict_convert.py:31`.
- **What goes wrong:** Passing a config kwarg that already exists in the source config raises `TypeError: got multiple values for keyword argument ...`. Examples are `convert_esm_hf_to_te(m, token_dropout=False)`, `dtype=...`, or `max_position_embeddings=...`. I confirmed this Python behaviour with a one-line snippet.
- **Why wrong:** The docstrings say `**config_kwargs` are "Additional configuration kwargs to be passed to NVEsmConfig/EsmConfig/AMPLIFYConfig". Only kwargs that the HF config lacks actually work.
- **Fix:** Merge the dicts first: `NVEsmConfig(**{**model_hf.config.to_dict(), **config_kwargs})`, and do the same at the other two sites.

### 6. `NVEsmEncoder` silently writes FP8 layer precision into the shared, persisted config (low)

- **File/line:** `models/esm2/modeling_esm_te.py:185-187`
- **What goes wrong:** If you build a model with `fp8_recipe=...` and `layer_precision=None`, `self.config.layer_precision` is set to `["fp8"] * num_hidden_layers` on the model's own config object. `save_pretrained` then saves that config. Reloading the checkpoint later without any recipe (for example for BF16 inference) gives a model that runs every layer under FP8 autocast with TE's default recipe (line 337-340; only a warning is issued).
- **Why wrong:** The config docstring (lines 125-127) says `layer_precision=None` "means no quantization is configured". A runtime recipe argument should not permanently change the serialized configuration.
- **Fix:** Keep the effective precision on the encoder (for example `self._layer_precision`) and read it in `get_autocast_context`, leaving `config.layer_precision` untouched.

### 7. `ContextParallelDataLoaderWrapper.__iter__` swaps in the new iterator before stopping the old prefetch thread (low)

- **File/line:** `models/esm2/collator.py:502-504`
- **What goes wrong:** Re-iterating after an early `break`, which is common with step-limited training loops, leaves a prefetch thread outstanding. `__iter__` assigns `self._iterator = iter(self.dataloader)` first and only then calls `self.close()`. If the outstanding thread hasn't yet reached `next(self._iterator)` (`_send_data_to_cp_tp_ranks`, line 579), it pulls a batch from the **new** iterator. That batch is then overwritten by the newly started prefetch and lost, so the first batch of the new epoch is silently skipped on rank 0. `close()` also gives up after a 10 s join timeout and starts a second thread anyway, which can leave two threads issuing `scatter_object_list` collectives at the same time.
- **Why wrong:** `close()`'s docstring says it is meant to stop the prefetch thread. That has to happen before the iterator it reads from is replaced.
- **Fix:** Call `self.close()` (and clear `self._prefetch_result`) before creating the new iterator.

### 8. `state._match_keys` crashes when a wildcard matches both numeric and non-numeric segments (low)

- **File/line:** `models/esm2/state.py:432` (copied verbatim to `models/amplify/src/amplify/state.py`)
- **What goes wrong:** `wildcard_matches[i].sort(key=lambda x: int(x) if x.isdigit() else x)` mixes `int` and `str` keys. A pattern such as `model.*.weight` matching both `model.0.weight` and `model.norm.weight` raises `TypeError: '<' not supported between instances of 'str' and 'int'`. I confirmed this with a snippet.
- **Why wrong:** The `*` wildcard is documented as "Match any characters except dots" (line 409), so non-numeric matches are legal input.
- **Fix:** Use a total-order key, for example `key=lambda x: (0, int(x), "") if x.isdigit() else (1, 0, x)`.

### 9. `TransformFns.merge_qkv_bias` / `split_qkv_bias` / `merge_qkv_concat` / `merge_qkv_bias_concat` read Megatron-only config attributes (low)

- **File/line:** `models/esm2/state.py:549-554, 579-582, 628-631, 643-648`
- **What goes wrong:** These helpers read `config.num_query_groups` and `config.kv_channels`. Those attributes don't exist on HF-style configs (NVEsmConfig, Qwen2Config, and similar), so any use against the HF/TE models in this repo raises `AttributeError`. The companion `merge_qkv` and `split_qkv` in the same class use `num_key_value_heads` and `hidden_size // num_attention_heads`. `split_qkv_bias` also reads `ctx.source.config`, while its twin `split_qkv` reads `ctx.target.config`. The Qwen converter (`models/qwen/convert_qwen2.py:41,64`) re-implements the bias helpers locally, which shows the shared ones are unusable.
- **Why wrong:** The class is documented as "common functions used in state dict transformation" for HF↔TE conversion, but these four can't run against the configs it is used with.
- **Fix:** Derive `num_query_groups = config.num_key_value_heads` and `head_size = config.hidden_size // config.num_attention_heads`, as `merge_qkv` does, and read the config consistently from the HF side.

### 10. TE AMPLIFY ignores `att_bias`/`ffn_bias`; its non-default config branches don't match the converter (low)

- **File/line:** `models/amplify/src/amplify/amplify_te.py:190` (`bias=False` hard-coded), `amplify_te.py:298-301`, `state_dict_convert.py:17-24,39-58`
- **What goes wrong:**
  - `AMPLIFYConfig` exposes `att_bias` and `ffn_bias`, but the TE layers always use `bias=False`, so a config with `att_bias=True` or `ffn_bias=True` silently gets a model without biases.
  - With `layer_norm_before_last_layer=False`, the decoder is a plain `Linear(hidden, vocab_size)`: it is unpadded, even though `padded_vocab_size` exists "to support fp8".
  - For that configuration the converter fails at once in two ways. The mapping requires the source key `layer_norm_2.weight`, which is missing, and `_pad_decoder_weights` produces a `padded_vocab_size`-row tensor that doesn't match the target shape.
- **Why wrong:** The config fields are documented ("Whether to use bias in the feedforward network / attention"), but the model does not honour them.
- **Fix:** Pass `bias=config.att_bias or config.ffn_bias`, or raise when either is True. Use `padded_vocab_size` in the `Linear` branch too, and make the conversion mapping and transforms conditional on `layer_norm_before_last_layer`.

## Considered, not reported as confirmed

- `models/amplify/src/amplify/export.py:59,63` pins `revision="d918a9e8"` for both `chandar-lab/AMPLIFY_120M` and `AMPLIFY_350M`. A short git SHA is repo-specific, so this looks wrong for the 350M repo. I could not check it offline, so it is not listed as a defect.
- The `DataCollatorWithFlattening` `separator_id` label is not applied to the first sequence. HF sets it for every sequence, but the first label is dropped by the causal shift anyway, so the results are equivalent.

## Files read

- `models/amplify/src/amplify/__init__.py`, `amplify_hf.py`, `amplify_te.py`, `rmsnorm.py`, `rotary.py`, `metrics.py`, `state_dict_convert.py`, `export.py`, `state.py` (diffed against the esm2 copy; identical apart from the copy notice)
- `models/amplify/export.py` (caller context)
- `models/esm2/convert.py`, `export.py`, `modeling_esm_te.py`, `collator.py`, `state.py`
- Grep-level context only: `models/esm2/tests/*` (token_dropout / padded-THD usage), `recipes/esm2_native_te/train_*_cp.py`, `models/qwen/convert_qwen2.py`
