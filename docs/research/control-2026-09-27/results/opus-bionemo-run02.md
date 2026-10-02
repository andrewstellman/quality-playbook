# Code review: bionemo (models/amplify/src/amplify/, models/esm2/ excluding tests)

Checkout: `/tmp/control/bionemo` @ 11701476b005ca7bc489df924a398b8f12453f0b
Reviewer: opus, run02

Nothing could be executed: the modules import torch, transformer_engine, and xformers, and none are installed. Every finding below comes from reading the code and tracing the logic by hand.

---

## 1. THD token-dropout scaling uses unpadded offsets on padded input
- **File/line:** `models/esm2/modeling_esm_te.py:740-744` (`NVEsmEmbeddings._apply_token_dropout_thd`)
- **What goes wrong:** Suppose a THD batch has padding between sequences. That happens when `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=...)` produces it, which sets `cu_seq_lens_q_padded` and `pad_between_seqs=True`. In that case `input_ids` is in the *padded* layout, with length `cu_seq_lens_q_padded[-1]`. The code builds `is_masked` from that padded array, but then splits it into per-sequence windows with `offsets=kwargs["cu_seq_lens_q"]`, which are the *unpadded* boundaries. From the second sequence on, each window is shifted: it includes the previous sequence's pad tokens and cuts off the tail of the current sequence. `n_masked_per_seq` is therefore counted over the wrong tokens, and so are `mask_ratio_observed` and the per-sequence `scale_factor`. That wrong factor then scales every token of the sequence through `repeat_interleave(..., src_lengths_padded)`. `values` is also longer than `offsets[-1]`.
  - Example: sequence lengths 5 and 6, padded to multiples of 8. The padded layout is seq1 at `[0,5)`, pad at `[5,8)`, seq2 at `[8,14)`, pad at `[14,16)`. `cu_seq_lens_q` is `[0,5,11]`, so "sequence 2" is counted over `[5,11)`: three pad tokens plus the first three tokens of seq2.
- **Why it's wrong:** The code's own comment at line 739 says "We need to find the number of masked tokens in each sequence in the padded batch". The ratio has to be computed over each sequence's real tokens, the same way the BSHD path does it at lines 713-716. ESM-2 checkpoints ship with `token_dropout=True`, so this path is active by default, including at inference. The existing padded-THD golden test would not catch it because its logits tolerance is `atol=2.0` (`tests/test_modeling_esm_te.py:145`).
- **Severity:** medium. It silently skews embeddings and training numerics for padded THD batches.
- **Fix:** When `cu_seq_lens_q_padded` is present, split the padded array with the padded offsets and divide by the real lengths:
  ```python
  offsets = kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])
  n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=offsets).sum(1)
  mask_ratio_observed = n_masked_per_seq.float() / src_lengths   # real lengths
  ```
  Pad tokens are never the mask token, so counting over the padded window gives the correct count.

## 2. AMPLIFY `_pad_weights` builds padding rows with the default dtype and device
- **File/line:** `models/amplify/src/amplify/state_dict_convert.py:73-74` (`_pad_weights`, used for both `encoder.weight` and `decoder.weight`)
- **What goes wrong:** `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))` is always float32 on CPU. There are two failure cases:
  - The HF source model is on GPU. `torch.cat` fails with a device-mismatch error.
  - The source is bf16/fp16 on CPU. `torch.cat` type-promotes the result to float32. The TE target was built with `params_dtype=config.dtype` (bf16), so `apply_transforms` then fails its dtype-preservation assertion (`state.py:233-237`, "dtype mismatch for key amplify.encoder.weight").
  
  Conversion only works for an fp32 CPU source, which is how `export.py` happens to load it.
- **Why it's wrong:** The ESM-2 copy of this same helper was fixed to pass `dtype=source_embed.dtype, device=source_embed.device` (`models/esm2/convert.py:243-245`). `_pad_bias` in the same AMPLIFY file also passes both.
- **Severity:** medium, since `convert_amplify_hf_to_te` is a public API and fails for any non-fp32 or GPU source.
- **Fix:** `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

## 3. HF AMPLIFY hard-codes the attention mask to bfloat16
- **File/line:** `models/amplify/src/amplify/amplify_hf.py:361`
- **What goes wrong:** The additive mask is always `.to(torch.bfloat16)`, whatever dtype the model runs in. With an fp32 or fp16 model:
  - The CPU path passes it as `attn_mask` to `scaled_dot_product_attention` (line 264-270). SDPA requires a float mask to match the query dtype, so it raises.
  - The CUDA path passes it as `attn_bias` to xformers `memory_efficient_attention`, which has the same dtype requirement.
  - The `output_attentions` path (line 248) adds a bf16 tensor to fp32 scores. That one works, but it computes in mixed precision.
  
  Any padded batch (a mask that is not all zeros) fails unless the model is bf16.
- **Why it's wrong:** The model's own dtype is the right mask dtype. Nothing in the config or docstring limits the model to bf16. The repo's test (`tests/test_encoder_block.py:84`) only exercises bf16.
- **Severity:** medium.
- **Fix:** `.to(self.encoder.weight.dtype)` (or the dtype of `x`) instead of `torch.bfloat16`.

## 4. `TokenPackingDataset` can drop a completely full final batch when `drop_last=True`
- **File/line:** `models/esm2/collator.py:300-306` (and `319-322`, `325-327`), combined with `331-332`
- **What goes wrong:** When a sample overflows the current batch, the code starts a new batch with `samples=[sample]` and `current_length=padded_len` but never checks whether that new batch is already exactly full. The split path at 327 does the same with the remainder. If the stream then ends, the `drop_last` check at 331 discards that batch even though it holds exactly `max_tokens_per_batch` tokens.
  - Example: `max_tokens_per_batch=10`, samples of length 6 then 10, `split_samples=False`. The first yield is `[A]`. Then `samples=[B]` with `current_length=10`, the iteration ends, and `[B]` is dropped.
- **Why it's wrong:** The `drop_last` field doc (line 239) says "Whether to drop the last batch if it's less than max_length". A batch equal to the maximum should not be dropped. It also isn't yielded straight away like the `==` branch at 295 does.
- **Severity:** low. It loses data only at the end of the stream.
- **Fix:** After resetting `samples`/`current_length` in the overflow branches, check `if current_length == self.max_tokens_per_batch: yield samples; samples = []; current_length = 0`. Alternatively, change the end-of-stream condition to `if samples and (not self.drop_last or current_length == self.max_tokens_per_batch)`.

## 5. Per-sequence padding leaves `attention_mask` and `position_ids` at their unpadded shape
- **File/line:** `models/esm2/collator.py:213-227` (`DataCollatorWithFlattening._pad_sequences_to_be_divisible_by`)
- **What goes wrong:** This step replaces `input_ids` and `labels` with the per-sequence-padded tensors and adds `cu_seq_lens_*_padded`. The `attention_mask` produced by `_pt_flatten_collate` (line 721-724) is left at the old unpadded length, and so is `position_ids` when `return_position_ids=True`. They no longer line up with `input_ids`. Contrast `_pt_pad_to_multiple_of` (lines 915-923), which pads both.
- **Why it's wrong:** The `__call__` docstring (lines 133-134) documents `attention_mask` as having "1s for actual tokens and 0s for padding tokens". Here the mask covers none of the inserted padding and has the wrong length. Any consumer that uses it, or `position_ids`, alongside `input_ids` will index or broadcast incorrectly. `NVEsmModel` happens to ignore both in THD mode.
- **Severity:** low.
- **Fix:** Rebuild or pad `attention_mask` (zeros at pad slots) and `position_ids` using `cu_seqlens_padded`, or drop both keys from the batch in this mode.

## 6. AMPLIFY TE only converts `int64` attention masks
- **File/line:** `models/amplify/src/amplify/amplify_te.py:245-247`
- **What goes wrong:** A mask is converted from HF convention (1 = attend) to TE convention (True = masked) only if its dtype is exactly `torch.int64`. An HF-convention mask of any other dtype is passed straight to TE: int32, float, or a bool mask where True means attend. TE then treats real tokens as masked and padding as visible, or gets a non-bool mask it doesn't expect.
- **Why it's wrong:** The `forward` docstring describes `attention_mask` only as "The attention mask", in an HF `PreTrainedModel` whose sibling HF implementation (`amplify_hf.py:361`) treats `attention_mask == 1` as attend for any dtype. The sign of the mask silently depends on its dtype.
- **Severity:** low. Tokenizers produce int64, so the common path works.
- **Fix:** Convert any non-bool mask (`attention_mask.dtype != torch.bool`), or document explicitly that bool masks must already be in TE (True = masked) convention.

## 7. AMPLIFY conversion breaks when `layer_norm_before_last_layer=False`
- **File/line:** `models/amplify/src/amplify/amplify_te.py:298-301` vs `models/amplify/src/amplify/state_dict_convert.py:33, 99-117`
- **What goes wrong:** With `layer_norm_before_last_layer=False`, the TE decoder is `Linear(hidden_size, vocab_size)`, but `_pad_decoder_weights` and `_pad_bias` always pad the decoder to `padded_vocab_size`. That causes a shape mismatch, and `apply_transforms` raises ValueError. The unconditional mapping entry `"layer_norm_2.weight"` also has no source key in that configuration, so `StateDictTransform` raises "No matches found for source key".
- **Why it's wrong:** `layer_norm_before_last_layer` is a documented config option (lines 56, 79). The LN branch sizes the decoder at `padded_vocab_size` (line 289), and `forward` slices logits to `vocab_size` (line 345-346), so the Linear branch is simply inconsistent.
- **Severity:** low. The released AMPLIFY checkpoints use `True`.
- **Fix:** Size the Linear decoder at `config.padded_vocab_size`, and make the `layer_norm_2` mapping entry conditional on the config.

## 8. Conversion helpers crash when a caller override duplicates a key already in the source config
- **File/line:** `models/esm2/convert.py:63` and `:102`; `models/amplify/src/amplify/state_dict_convert.py:47`
- **What goes wrong:** Each helper builds its config with `NVEsmConfig(**model_hf.config.to_dict(), **config_kwargs)`, or the `EsmConfig`/`AMPLIFYConfig` equivalent. If `config_kwargs` names a key that is already in the source config dict, Python raises `TypeError: got multiple values for keyword argument` before any conversion runs. Examples are `dtype`, `token_dropout`, and `hidden_dropout_prob` on the HF→TE path, or any HF-valid key on the TE→HF path.
- **Why it's wrong:** The docstrings say `**config_kwargs` are "Additional configuration kwargs to be passed to NVEsmConfig/EsmConfig/AMPLIFYConfig", which reads as a way to override settings. That works only for keys the source config doesn't already have.
- **Severity:** low.
- **Fix:** Merge the dicts first: `NVEsmConfig(**{**model_hf.config.to_dict(), **config_kwargs})`, and the same in the other two sites.

---

## Checked and not reported
- The MLM loss `.view()` on sliced logits: stride-compatible, so it works.
- QKV pack/unpack interleaving, zigzag CP sharding, TP/CP replication ordering, and `_pt_pad_to_multiple_of`: all consistent.
- The copied `state.py` helpers that reference Megatron-only config fields (`num_query_groups`, `kv_channels`) are unused by these models.

## Files read
- models/amplify/src/amplify/__init__.py (listed only), amplify_te.py, amplify_hf.py, rotary.py, rmsnorm.py, metrics.py, state_dict_convert.py, export.py, state.py (diffed against esm2/state.py)
- models/esm2/modeling_esm_te.py, convert.py, export.py, state.py, collator.py
- Context only: models/esm2/tests/test_modeling_esm_te.py (get_test_input_data, tolerances), models/esm2/tests/common/test_modeling_common.py (padded THD tests), models/amplify/tests/test_encoder_block.py (mask construction); grep results for token_dropout / cu_seq_lens_q_padded usage in recipes/
