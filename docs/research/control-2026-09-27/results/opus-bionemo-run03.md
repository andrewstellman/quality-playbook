# Code review: bionemo-recipes @ 11701476 — `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

Reviewer: opus (run03). I could not execute any of this code: PyTorch and transformer_engine are not installed. Every finding comes from reading the code and cross-checking callers and tests.

---

## 1. THD token-dropout rescaling counts masked tokens using the wrong offsets when sequences are padded, or when context parallelism shards the batch

- **File/line:** `models/esm2/modeling_esm_te.py:734-744` (`NVEsmEmbeddings._apply_token_dropout_thd`), line 741 in particular.
- **What goes wrong:**
  - `is_masked` is computed over the actual `input_ids` token buffer.
  - The buffer is split into per-sequence windows with `offsets=kwargs["cu_seq_lens_q"]`, which holds the unpadded cumulative lengths.
  - When `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=N)` is used, `collator.py:213-226` pads every sequence inside the buffer. It stores the real in-buffer boundaries in `cu_seq_lens_q_padded` and leaves `cu_seq_lens_q` unpadded.
  - Result: sequence *i*'s window starts at `cu_seq_lens_q[i]`, but its tokens actually start at `cu_seq_lens_q_padded[i]`. The windows drift further out of line as padding accumulates. Masked tokens get counted against the wrong sequence, and the final `offsets[-1]` no longer equals the buffer length.
  - This is the configuration used for THD context parallelism (the CP collator requires `cu_seq_lens_q_padded`). There, `DataCollatorForContextParallel` (`collator.py:415-425`) additionally shards `input_ids` to roughly `T / cp_size` tokens per rank but keeps the global `cu_seq_lens_q`, so the offsets point past the end of the local buffer.
- **Why it is wrong:**
  - The function builds `src_lengths_padded` from `cu_seq_lens_q_padded` for the `repeat_interleave` step. It therefore knows the buffer layout is the padded one.
  - Its own comment says "We need to find the number of masked tokens in each sequence in the padded batch", yet the counting step uses the unpadded offsets.
  - The per-sequence scale factor `(1 - 0.12) / (1 - mask_ratio_observed)` is then computed from the wrong counts. Depending on whether `nested_tensor_from_jagged` validates offsets, the result is either wrong embedding scaling or a runtime error.
  - Every THD/CP test that uses per-sequence padding passes `token_dropout=False` (`tests/test_cp_thd.py:187,238`), so this path is not tested. ESM-2 checkpoints ship with `token_dropout=True`.
- **Severity:** medium. It silently corrupts the input embeddings in packed + padded / CP training with the default ESM-2 config.
- **Fix:**
  - Count masked tokens over the padded windows: `offsets=kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])`. Pad tokens are never `<mask>`, so the counts come out right. Keep `src_lengths` (the unpadded lengths) as the denominator.
  - For CP-sharded inputs, compute the scale before sharding, or with rank-local offsets.

## 2. AMPLIFY (TE) only converts int64 attention masks; bool, int32 or float masks are passed to TE with inverted meaning

- **File/line:** `models/amplify/src/amplify/amplify_te.py:245-247`.
- **What goes wrong:**
  - The code only converts the mask when `attention_mask.dtype is torch.int64`. The conversion turns the HF convention (1 = attend) into the TE convention (True = masked).
  - A boolean mask in HF convention (True = real token, e.g. `inputs["attention_mask"].bool()`) goes to TE unchanged. TE then treats every real token as masked and every pad as visible.
  - An int32 or float mask is also passed through unconverted, either with inverted meaning or as a non-bool mask TE does not expect.
- **Why it is wrong:**
  - The comment on line 246 states TE's convention, but the conversion is gated on one dtype.
  - The reference model this port must match, `amplify_hf.py:360-361`, interprets the mask by value (`attention_mask == 1`) for any dtype. The two models give different results for the same boolean or int32 input.
  - ESM2's TE port normalises any dtype through `AttentionMaskConverter` (`modeling_esm_te.py:497-502`).
- **Severity:** medium. The attention output is silently wrong for callers that pass a boolean mask.
- **Fix:** Convert whenever the mask is not already in TE form, for example `attention_mask = ~attention_mask.to(torch.bool)` for any dtype. If you want to keep accepting a pre-inverted TE mask, document that and require a distinct flag for it.

## 3. AMPLIFY `_pad_weights` builds its padding rows with the default dtype and device, so conversion breaks for bf16 or GPU source models

- **File/line:** `models/amplify/src/amplify/state_dict_convert.py:85-91`, line 90 in particular.
- **What goes wrong:**
  - `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))` is always float32 on the CPU.
  - Case 1: the HF source model is loaded in bf16 or fp16. `convert_amplify_hf_to_te` builds the TE model with `te_config.dtype` taken from `model_hf.config`, so the target parameters are bf16. `torch.cat((source_embed, padding_rows))` promotes the result to float32. `apply_transforms` then raises at `state.py:241` with `dtype mismatch for key amplify.encoder.weight`.
  - Case 2: the source model is on CUDA. `torch.cat` fails because the two tensors are on different devices.
- **Why it is wrong:** The shared helper this was derived from, `models/esm2/convert.py:243-245`, deliberately creates the padding with `dtype=source_embed.dtype, device=source_embed.device`. The AMPLIFY copy is missing that fix. The bias counterpart in the same AMPLIFY file (`_pad_bias`, lines 113-115) does pass dtype and device.
- **Severity:** medium. HF→TE conversion fails for any AMPLIFY source that is not fp32 and on the CPU.
- **Fix:** `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

## 4. AMPLIFY TE with `layer_norm_before_last_layer=False` sizes the decoder with `vocab_size`, contradicting the padded-vocab design and the converter

- **File/line:** `models/amplify/src/amplify/amplify_te.py:298-301`, compared with `state_dict_convert.py:27-34, 99-117`.
- **What goes wrong:**
  - In the `layer_norm_before_last_layer=True` branch, the decoder is sized to `config.padded_vocab_size`.
  - In the `else` branch it is sized to `config.vocab_size`, and it also skips the `init_method` that uses `decoder_init_range`.
  - The converter works as if the decoder were always padded: `_pad_decoder_weights` and `_pad_bias` always pad to `padded_vocab_size`, and `mapping` always requires `layer_norm_2.weight`.
  - So any AMPLIFY config with `layer_norm_before_last_layer=False` cannot be converted. It fails first with "No matches found for source key: layer_norm_2.weight" (`state.py:322-323`). Even without that, the decoder would hit a shape mismatch (padded 32 rows against 27).
  - It also defeats the purpose of `padded_vocab_size`, which the config documents as "to support fp8" (line 81): that branch gets an FP8-unfriendly output dimension.
- **Severity:** low. The default config uses `True`.
- **Fix:**
  - Use `config.padded_vocab_size` and the same `init_method` in the `else` branch.
  - In the converter, add the `layer_norm_2.weight` mapping only when `config.layer_norm_before_last_layer` is true.

## 5. AMPLIFY HF reference model always casts the additive mask to bfloat16, so fp32 or fp16 forwards with a mask fail

- **File/line:** `models/amplify/src/amplify/amplify_hf.py:361`.
- **What goes wrong:**
  - The additive mask is always `.to(torch.bfloat16)`, whatever the model dtype.
  - On CPU in fp32, `scaled_dot_product_attention` (line 264) requires a float `attn_mask` to match the query dtype, so it raises.
  - On CUDA, xformers `memory_efficient_attention` likewise needs `attn_bias` to match the query dtype, so fp32 and fp16 runs fail as well.
  - The model therefore only works in bf16 whenever padding is present. The tests only ever exercise bf16 under autocast (`tests/test_amplify_model.py`).
- **Why it is wrong:** The mask dtype should follow the activations. Nothing in the config or the docstrings restricts the model to bf16.
- **Severity:** low. This is the vendored reference model, but it is also the source for conversion.
- **Fix:** `.to(self.encoder.weight.dtype)`, or cast inside `_att_block` to `xq.dtype`.

## 6. `TransformFns` bias helpers read Megatron-only config attributes, unlike their weight counterparts

- **File/line:**
  - `models/esm2/state.py:555-561` (`split_qkv_bias`)
  - `state.py:585-589` (`merge_qkv_concat`)
  - `state.py:634-637` (`merge_qkv_bias_concat`)
  - `state.py:649-654` (`merge_qkv_bias`)
  - The same file is copied as `models/amplify/src/amplify/state.py`.
- **What goes wrong:**
  - These helpers read `config.num_query_groups` and `config.kv_channels`. Those are Megatron config fields.
  - The matching weight helpers in the same class (`split_qkv`, `merge_qkv`, lines 521-527 and 598-604) read the HF-style fields `num_key_value_heads` and `hidden_size // num_attention_heads`, which is what the models in this repo use.
  - `split_qkv_bias` also reads `ctx.source.config`, where `split_qkv` reads `ctx.target.config`.
  - Any HF/TE-style config passed to the bias helpers raises `AttributeError`. This is why `models/qwen/convert_qwen2.py:41,64` had to reimplement `_merge_qkv_bias`/`_split_qkv_bias` locally.
- **Severity:** low. ESM2 and AMPLIFY do not call these helpers.
- **Fix:** Use the same attribute derivation as `merge_qkv`/`split_qkv`: `num_key_value_heads`, `hidden_size // num_attention_heads`, and the same `ctx` side.

---

## Checked and not reported

- **QKV pack/unpack layout** (both converters) was checked against TE `qkv_weight_interleaved=True`. The layouts are consistent.
- **Rotary interleaving**: AMPLIFY uses complex pairs with `rotary_pos_interleaved=True`; ESM uses rotate_half with TE's default non-interleaved rope. Both are consistent.
- **Logits slicing and `.view`** on the padded vocab dimension is valid, because the batch and sequence dimensions stay mergeable.
- **`separator_id` placement** at `cu_seq_lens_q[1:-1]` is correct for unshifted causal labels.
- **`TokenPackingDataset` split arithmetic**: `tokens_available` is always less than the sample length.
- **CP/TP shard replication ordering** is correct.
- **`ContextParallelDataLoaderWrapper`**: I saw no confident defect. If rank 0 hits a non-StopIteration error, it never enters the scatter, so the other ranks block. That is ordinary distributed-failure behaviour and I did not report it.
- **HF revision hash `d918a9e8` reused for AMPLIFY_350M** (`amplify/src/amplify/export.py:59,63`). A revision hash normally belongs to one repository, so this looks suspicious. I could not verify it offline, so it is not reported.

## Files actually read

- `models/amplify/src/amplify/__init__.py` (listed only), `amplify_te.py`, `amplify_hf.py`, `rmsnorm.py`, `rotary.py`, `metrics.py`, `state.py` (diffed against esm2), `state_dict_convert.py`, `export.py`
- `models/amplify/tests/test_amplify_model.py` (context only)
- `models/esm2/modeling_esm_te.py`, `convert.py`, `export.py`, `state.py`, `collator.py`, `README.md` (first 80 lines), `esm_fast_tokenizer/tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`
- Grep only, for context: `models/esm2/tests/*`, `models/qwen/convert_qwen2.py`, `models/mixtral/convert.py`
