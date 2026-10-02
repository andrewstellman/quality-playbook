# Code review: bionemo-recipes @ 11701476b005ca7bc489df924a398b8f12453f0b

Scope: `models/amplify/src/amplify/`, `models/esm2/` (excluding tests).

The modules could not be imported here because there is no torch or transformer_engine. Finding 1 was checked with a pure-Python simulation of the indexing logic. Every other finding comes from reading the code.

---

## 1. THD token-dropout counts masked tokens using unpadded offsets on a padded token stream (medium)

- **File/line:** `models/esm2/modeling_esm_te.py:740-744` (`NVEsmEmbeddings._apply_token_dropout_thd`)
- **What goes wrong:** When sequences are packed with per-sequence padding, `input_ids` uses the padded layout. This happens with `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=...)`, which sets `cu_seq_lens_q_padded` and `pad_between_seqs=True` (`collator.py:213-226`). In that layout, sequence *i* starts at `cu_seq_lens_q_padded[i]`. The per-sequence masked-token count, however, is computed as
  ```python
  n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"]).sum(1)
  ```
  This uses the **unpadded** offsets. Every sequence after the first is counted over the wrong window: part of the previous sequence, its padding, and part of the correct sequence. As a result, `mask_ratio_observed` and the token-dropout `scale_factor` are wrong for every sequence except the first.
- **Why it is wrong:** The same function expands the scale factor with `repeat_interleave(scale_factor, src_lengths_padded)` (line 744). That call assumes the tokens are in the padded layout, so the counting step contradicts the expansion step. The intended behaviour is spelled out in the comment at lines 773-779: scale by the observed mask fraction *per sample*. The BSHD path (`_apply_token_dropout_bshd`) computes it correctly per sequence.
- **Evidence:** I simulated 5 sequences of lengths 73/48/77/68/80, padded to multiples of 32, with ~12% masked tokens. Sequence 1 had 6 masked tokens but 2 were counted, giving a scale of 0.918 instead of 1.006. Sequence 3 had 10 masked but 4 were counted, giving 0.935 instead of 1.032. Only sequence 0 was correct. ESM-2 checkpoints have `token_dropout=True`, so this affects padded-THD training and inference. The existing test `test_golden_values_thd_padded` uses `golden_value_logits_atol=2.0`, which is loose enough to hide a few-percent embedding scale error.
- **Fix:** Count within the padded layout, then divide by the real lengths:
  ```python
  offsets = kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])
  n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=offsets).sum(1)
  mask_ratio_observed = n_masked_per_seq.float() / src_lengths
  ```
  Padding tokens are `pad_token_id`, not `mask_token_id`, so they do not inflate the count. Also use `kwargs.get(...) is not None` rather than `"cu_seq_lens_q_padded" in kwargs`, so that a key present with value `None` doesn't crash in `torch.diff`.

## 2. AMPLIFY HF→TE conversion builds padding rows with the wrong dtype and device (low-medium)

- **File/line:** `models/amplify/src/amplify/state_dict_convert.py:90`
- **What goes wrong:** `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))` is always float32 on CPU.
  - If the source HF model is on CUDA, `torch.cat((source_embed, padding_rows))` raises a device-mismatch error.
  - If the source is bf16/fp16, the concatenation silently promotes the embedding and decoder weights to float32. `apply_transforms` then fails its dtype-preservation assertion (`state.py:232-237`, "dtype mismatch for key ...").
- **Why it is wrong:** The ESM-2 copy of the same helper (`models/esm2/convert.py:243-245`) explicitly passes `dtype=source_embed.dtype, device=source_embed.device`. `_pad_bias` in this same file (line 113-115) does the same. The AMPLIFY version is an inconsistent copy.
- **Fix:** `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

## 3. TE AMPLIFY only converts the attention mask when it is int64; other HF-style masks reach TE with the wrong meaning (low)

- **File/line:** `models/amplify/src/amplify/amplify_te.py:245-247`
- **What goes wrong:** The HF 1=attend / 0=pad mask is inverted into TE's True=masked convention only when `attention_mask.dtype is torch.int64`. Any other dtype is passed to TE unchanged:
  - A bool mask in HF convention (True = attend) gets inverted semantics: TE masks the real tokens and attends to padding.
  - An int32 or float 0/1 mask is not a boolean mask at all.
- **Why it is wrong:** The method documents `attention_mask` as the ordinary HF attention mask, and the TE comment at line 246 says the conversion is what TE needs. The reference HF implementation (`amplify_hf.py:360-361`) handles any dtype via `attention_mask == 1`.
- **Fix:** Convert regardless of dtype, for example `attention_mask = attention_mask == 0` (or `~attention_mask.bool()`).

## 4. `NVEsmConfig.padded_vocab_size` default contradicts its docstring (low)

- **File/line:** `models/esm2/modeling_esm_te.py:88` vs. docstring lines 119-120 and code line 145
- **What goes wrong:** The docstring says "If not provided, defaults to vocab_size", and line 145 implements that fallback (`padded_vocab_size or self.vocab_size`). But the signature default is `64`, not `None`, so the fallback only applies when the caller explicitly passes `None`.
  - Constructing `NVEsmConfig(vocab_size=N)` with N > 64 and no `padded_vocab_size` fails the assertion at line 149.
  - Loading a config.json that lacks `padded_vocab_size` silently pads to 64.
- **Fix:** Default `padded_vocab_size: Optional[int] = None`, or correct the docstring and make callers set it explicitly.

## 5. Converter kwargs cannot override keys already in the HF config (low)

- **File/line:** `models/esm2/convert.py:63`, `models/amplify/src/amplify/state_dict_convert.py:47`
- **What goes wrong:** `NVEsmConfig(**model_hf.config.to_dict(), **config_kwargs)` raises `TypeError: got multiple values for keyword argument` whenever a `config_kwargs` key is already in the HF config. Examples are `token_dropout`, `dtype`, and `max_position_embeddings`. The AMPLIFY converter has the same pattern.
- **Why it is wrong:** The docstrings say `**config_kwargs` are "Additional configuration kwargs to be passed to NVEsmConfig". Overriding an HF field, such as disabling `token_dropout` for CP (as the CP tests do after loading), is a natural use. `convert_esm_te_to_hf` has the same pattern at line 102.
- **Fix:** Merge the dicts first: `NVEsmConfig(**{**model_hf.config.to_dict(), **config_kwargs})`.

## 6. `ContextParallelDataLoaderWrapper`: a non-StopIteration error on rank 0 deadlocks the other CP/TP ranks (low)

- **File/line:** `models/esm2/collator.py:577-585`
- **What goes wrong:** Only `StopIteration` from `next(self._iterator)` is converted into a scattered sentinel. Any other exception on rank 0 escapes `_send_data_to_cp_tp_ranks` before `scatter_object_list` is called; examples are a collator `ValueError` such as `TokenPackingDataset`'s oversize-sample error, or a tokenization error. Rank 0 records and re-raises it. Ranks 1..N stay blocked inside `scatter_object_list` until the process-group timeout.
- **Why it is wrong:** The code already sets up the pattern for propagating end-of-data to all ranks ("we want to raise this error on all the CP ranks", line 581). Other errors break the collective contract instead.
- **Fix:** Catch `Exception` on rank 0 as well, and scatter `[ex] * num_cp_tp_ranks`. Then have every rank raise if the received object is an `Exception`.

## 7. `TokenPackingDataset` with `drop_last=True` can drop a batch that is exactly full (low)

- **File/line:** `models/esm2/collator.py:303-306` and `319-322`
- **What goes wrong:** When the current batch overflows, a new batch is started with `samples = [sample]; current_length = padded_len`, without checking `current_length == max_tokens_per_batch`. If that single sample fills the batch exactly, it is not yielded immediately; it waits for the next sample to overflow it. If the stream ends first, `drop_last=True` discards it.
- **Why it is wrong:** `drop_last` is documented as "Whether to drop the last batch if it's less than max_length" (line 239). This batch is exactly full.
- **Fix:** After resetting `samples`/`current_length`, yield immediately if `current_length == self.max_tokens_per_batch`, or make the final check `if samples and (not self.drop_last or current_length == self.max_tokens_per_batch)`.

---

No confident defects found in: `amplify/rmsnorm.py`, `amplify/rotary.py`, `amplify/metrics.py`, `amplify/export.py`, `esm2/export.py`, the QKV pack/unpack and vocab pad/unpad transforms in `esm2/convert.py`, or `state.py`. `amplify/state.py` is a byte-identical copy of `esm2/state.py` apart from the copied-file notice. The unused `TransformFns` helpers there reference Megatron-only config fields, but nothing in scope calls them.

## Files actually read

- `models/esm2/modeling_esm_te.py`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/state.py`
- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/state.py` (via diff against esm2/state.py)
- For context (out of scope): `models/esm2/tests/test_modeling_esm_te.py` (`get_test_input_data`, tolerances), `models/esm2/tests/common/test_modeling_common.py` (padded-THD tests), grep over `models/esm2/tests` for token_dropout usage
