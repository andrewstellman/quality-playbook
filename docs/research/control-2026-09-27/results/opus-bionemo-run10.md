# Code review: bionemo-recipes @ 11701476 — `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

Reviewer: opus (run10). Checkout: `/tmp/control/bionemo` (read-only). No torch/TE available, so findings are from reading the code, plus one pure-Python simulation for finding 1.

## Defects

### 1. THD token-dropout rescaling uses unpadded offsets on padded input. Per-sequence mask ratios come out wrong when sequences are padded.
- **File/line:** `models/esm2/modeling_esm_te.py:734-744` (`NVEsmEmbeddings._apply_token_dropout_thd`), especially line 741.
- **What goes wrong:** When `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=N)` is used, `input_ids` is laid out in the padded layout. `collator.py:213-226` pads each sequence and sets `cu_seq_lens_q_padded` and `pad_between_seqs=True`. But the masked-token count per sequence is computed with
  `torch.nested.nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"])`, which uses the **unpadded** offsets. From the second sequence on, each window is shifted onto the wrong tokens (the previous sequence's padding and tail), so `n_masked_per_seq` and the resulting `scale_factor` are wrong for every sequence after the first. The code's own comment says the count is meant to be taken "in the padded batch" (line 739). The later `repeat_interleave(..., src_lengths_padded)` also shows the tensor is expected to be in padded layout.
  - Simulation: seq A = `[cls, x, MASK, x, eos]` padded to 8, and seq B = `[cls, MASK, MASK, eos]` (already a multiple of 4). `cu_seq_lens_q=[0,5,9]` and `cu_seq_lens_q_padded=[0,8,12]`. With the code's offsets the counts are `[1, 0]`. The correct counts are `[1, 2]`. Seq B's embeddings get scaled by 0.88 instead of 0.88/(1-2/4)=1.76.
- **When:** `token_dropout=True` (the default in every facebook/esm2 config) together with THD input whose sequences are padded (`pad_sequences_to_be_divisible_by`, the context-parallel path). The embeddings are wrong for training and inference, with no error raised. The CP tests (`test_cp_thd.py`) set `token_dropout=False`, which hides the problem.
- **Severity:** high. Model outputs are silently wrong in a supported configuration.
- **Fix:** Compute the counts in padded space:
  ```python
  offsets = kwargs.get("cu_seq_lens_q_padded")
  if offsets is None: offsets = kwargs["cu_seq_lens_q"]
  n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=offsets).sum(1)
  ```
  (padding tokens are never `mask_token_id`, so the padded-window count equals the real count). Keep dividing by the unpadded `src_lengths`. Also use `.get(...) is not None` rather than `in kwargs` at line 735.

### 2. AMPLIFY TE only converts the attention mask when its dtype is exactly int64. Any other HF-style mask is applied with inverted meaning.
- **File/line:** `models/amplify/src/amplify/amplify_te.py:245-247`.
- **What goes wrong:** The forward follows the HF convention (1/True = attend) and converts it to TE's convention (True = masked) only `if attention_mask.dtype is torch.int64`. If the caller passes an HF-style mask as `bool`, `int32` or float, the mask goes to TE unchanged. TE then treats every real token as masked and every pad as attended, with no error. The reference implementation this file is adapted from (`amplify_hf.py:360-361`) interprets the mask by value (`attention_mask == 1`) regardless of dtype. The repo's own test builds a `bool` mask in HF convention (`tests/test_encoder_block.py:71-75`) and feeds it to the TE layer. The attention-output comparison there is commented out.
- **Severity:** medium. The HF tokenizer's default int64 mask works; other common mask dtypes give wrong results silently.
- **Fix:** Convert by value for any dtype, e.g. `attention_mask = ~attention_mask.to(torch.bool)`, or `attention_mask == 0`, for any non-None mask. Also reshape to `[b,1,1,s]` as the ESM2 path does.

### 3. AMPLIFY TE ignores `att_bias` / `ffn_bias`, and conversion silently drops those biases.
- **File/line:** `models/amplify/src/amplify/amplify_te.py:190` (`bias=False` hard-coded); `models/amplify/src/amplify/state_dict_convert.py:27-34`.
- **What goes wrong:** `AMPLIFYConfig` documents `ffn_bias` and `att_bias` (lines 82-83), and the HF reference honours them (`amplify_hf.py:128-160`). The TE model always builds its layers without bias. `apply_transforms` never checks for unconsumed *source* keys. So converting a checkpoint that has `att_bias=True` or `ffn_bias=True` succeeds but discards the q/k/v/wo/ffn biases, and the resulting model is numerically different.
- **Severity:** low. The published AMPLIFY checkpoints use `False`.
- **Fix:** Pass `bias=config.att_bias or config.ffn_bias`, or raise in `AMPLIFY.__init__` / `convert_amplify_hf_to_te` when either flag is True.

### 4. AMPLIFY decoder shape is inconsistent when `layer_norm_before_last_layer=False`. Conversion then fails.
- **File/line:** `models/amplify/src/amplify/amplify_te.py:298-301` vs `state_dict_convert.py:85-117`.
- **What goes wrong:** With `layer_norm_before_last_layer=True` the decoder has `padded_vocab_size` outputs. In the else branch it has `vocab_size` outputs. The converter always pads `decoder.weight` and `decoder.bias` to `padded_vocab_size`, so `apply_transforms` raises `Shape mismatch for parameter decoder.weight`. The embedding is padded in both cases, so the two branches are also asymmetric.
- **Severity:** low. This is a config-only path.
- **Fix:** Use `config.padded_vocab_size` in the else branch too. Forward already slices logits to `vocab_size`.

### 5. AMPLIFY `_pad_weights` builds padding rows with default dtype and device.
- **File/line:** `models/amplify/src/amplify/state_dict_convert.py:90`.
- **What goes wrong:** `torch.zeros(num_padding_rows, source_embed.size(1))` is float32 on CPU. For a bf16/fp16 source, `torch.cat` promotes the embedding and decoder weights to float32, and `apply_transforms` then fails its dtype-preservation assertion (`state.py:233-237`). For a source on GPU, `cat` raises a device mismatch. The identical ESM2 helper was written correctly (`models/esm2/convert.py:243-245`, `dtype=source_embed.dtype, device=source_embed.device`).
- **Severity:** low. The export script loads fp32 on CPU.
- **Fix:** Pass `dtype=source_embed.dtype, device=source_embed.device`.

### 6. `NVEsmEncoder` writes `layer_precision` into the shared config when only an FP8 recipe is passed.
- **File/line:** `models/esm2/modeling_esm_te.py:185-187`.
- **What goes wrong:** Constructing a model with `fp8_recipe=...` and `layer_precision=None` sets `self.config.layer_precision = ["fp8"] * n`. That is the model's shared `PretrainedConfig`, so `save_pretrained` persists it. Reloading that checkpoint without any recipe then runs every layer under FP8 autocast with the default recipe (`get_autocast_context`, lines 318-340, with only a warning). The config docstring says `None` means "no quantization is configured" (lines 125-127). A runtime-only recipe argument should not change the saved model definition.
- **Severity:** low.
- **Fix:** Store the effective precision list on the encoder (e.g. `self._layer_precision`) instead of mutating `config`.

### 7. `ContextParallelDataLoaderWrapper.__iter__` swaps in the new iterator before stopping the in-flight prefetch thread.
- **File/line:** `models/esm2/collator.py:500-509`.
- **What goes wrong:** Every `__next__` starts a background thread (`_kick_prefetch`, line 520) that calls `next(self._iterator)`. On re-iteration (e.g. the loop breaks after N steps, then a new `for` loop or epoch starts), `__iter__` first assigns `self._iterator = iter(self.dataloader)` and only then calls `close()` to join the old thread.
  - If the old thread has not yet read `self._iterator`, it consumes the first batch of the new iterator. That result is overwritten by the next `_kick_prefetch`, so a batch is silently lost.
  - With `persistent_workers=True`, `iter(dataloader)` resets the same iterator object while the other thread may be inside `next()` on it, which is a data race.
- **Severity:** low. The race window is narrow.
- **Fix:** Call `self.close()` (and use the result or discard it deliberately) before creating the new iterator.

## Checked and not reported
- The QKV pack/unpack interleaving in `esm2/convert.py` and `amplify/state_dict_convert.py` is consistent with `qkv_weight_interleaved=True`.
- RoPE: AMPLIFY adjacent-pair rotation maps to TE `interleaved=True`, and ESM rotate-half maps to the TE default.
- Slicing logits and then calling `.view(-1, vocab)` in the loss is valid.
- `TokenPackingDataset` split arithmetic: `tokens_available < sample_length` always holds.
- `_pt_pad_to_multiple_of` bookkeeping and CP zigzag sharding.
- The collator separator-label placement.

## Files read
- `models/amplify/src/amplify/`: `amplify_te.py`, `amplify_hf.py`, `rotary.py`, `rmsnorm.py`, `state_dict_convert.py`, `export.py`, `metrics.py`, `__init__.py`, `state.py` (diffed against esm2's copy: identical apart from the copy notice)
- `models/esm2/`: `modeling_esm_te.py`, `collator.py`, `state.py`, `convert.py`, `export.py`, `requirements.txt`, `Dockerfile`
- For context only (tests, out of scope): `models/amplify/tests/test_encoder_block.py` (parts), `models/esm2/tests/test_modeling_esm_te.py` (`get_test_input_data`), `models/esm2/tests/common/test_modeling_common.py` (THD padded tests), grep over `models/esm2/tests` for `token_dropout` / `cu_seq_lens_q_padded`
