# Code review: bionemo-recipes @ 11701476 — `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

Reviewer: opus (run09). Static review only. Nothing could be executed because torch and transformer_engine are not installed. Each finding below comes from reading the code.

---

## 1. THD token-dropout scaling uses unpadded offsets on a padded token layout (medium)

- **File:** `models/esm2/modeling_esm_te.py`, lines 734–744 (`NVEsmEmbeddings._apply_token_dropout_thd`)
- **What goes wrong:** When the batch comes from `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=N)` (collator.py 204–227), each sequence in `input_ids` is padded, so its tokens sit at the offsets in `cu_seq_lens_q_padded`. `cu_seq_lens_q` still holds the unpadded boundaries. The function knows the layout is padded, because it expands the scale factor with `src_lengths_padded` (line 744). But it counts masked tokens per sequence with `torch.nested.nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"])` (line 741), which uses the unpadded offsets.
  - Example: two sequences of length 5 and 6, padded to multiples of 8. The layout is `[s1 ×5, pad ×3, s2 ×6, pad ×2]`, `cu_seq_lens_q=[0,5,11]` and `cu_seq_lens_q_padded=[0,8,16]`.
  - The window used for sequence 2 is `[5,11)`. That covers 3 pad tokens and only the first 3 tokens of s2.
  - So `<mask>` tokens at s2 positions 3–5 are not counted, and the offsets do not cover the full values tensor. The per-sequence `mask_ratio_observed`, and therefore the embedding scale, is wrong for every sequence after the first. It may also fail outright.
- **Why it is wrong:** The docstring (lines 721–731) says the function computes "per-sequence mask ratios", and the code already expands with the padded lengths. The count must use the same (padded) layout that `input_ids` is in. `token_dropout=True` is the ESM-2 default.
- **Fix:** Build the jagged tensor with the padded offsets when they are present:
  `offsets = kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])`. Padding tokens are never `<mask>`, so the counts are then correct. Keep `src_lengths` (unpadded) as the denominator.

## 2. AMPLIFY TE: a boolean or non-int64 attention mask is passed to TE without being inverted (medium)

- **File:** `models/amplify/src/amplify/amplify_te.py`, lines 245–247
- **What goes wrong:** The mask is converted to TE's convention (True = masked) only when `attention_mask.dtype is torch.int64`. Any other dtype goes to `TransformerLayer` unchanged:
  - A `torch.bool` mask in the usual HF convention (True = attend) has the opposite meaning in TE, so real tokens get masked and padding gets attended.
  - An int32 or float mask is not converted to bool at all.
- **Why it is wrong:** The comment on line 246 states the contract: TE expects a boolean mask where True means masked. The forward docstring accepts a plain "attention mask" with HF semantics. For comparison, the ESM model in the same repo (`modeling_esm_te.py` 497–502) normalises any dtype through `AttentionMaskConverter` before inverting.
- **Fix:** Normalise regardless of dtype: `attention_mask = ~attention_mask.to(torch.bool)`. If callers are allowed to pass an already-TE-convention bool mask, document that and branch on it explicitly.

## 3. CP dataloader wrapper: a non-StopIteration error on rank 0 hangs every other CP/TP rank (medium)

- **File:** `models/esm2/collator.py`, lines 577–585 (`ContextParallelDataLoaderWrapper._send_data_to_cp_tp_ranks`)
- **What goes wrong:** Only `StopIteration` from `next(self._iterator)` is caught and scattered to the other ranks. Any other exception on rank 0 (a collator `ValueError`, a `TokenPackingDataset` "exceeds max_tokens_per_batch" error, an I/O error) propagates before `_scatter_batch_to_cp_tp_ranks` is called. Rank 0 then raises in `__next__`, but the other ranks stay blocked inside `torch.distributed.scatter_object_list`, which is a collective. They wait until the NCCL/Gloo timeout instead of failing.
- **Why it is wrong:** The StopIteration branch shows the intent: dataloader-side conditions must be broadcast so that all ranks see them ("we want to raise this error on all the CP ranks").
- **Fix:** Catch `Exception` as well, scatter it to all ranks (`combined_batch = [ex] * self.num_cp_tp_ranks`), and raise it on every rank (check `isinstance(batch_on_this_rank, Exception)`).

## 4. CP dataloader wrapper: `__iter__` swaps the iterator before stopping the in-flight prefetch thread (low)

- **File:** `models/esm2/collator.py`, lines 500–509
- **What goes wrong:** `__iter__` assigns `self._iterator = iter(self.dataloader)` and only then calls `self.close()`, which joins the prefetch thread started by the previous `__next__`. That thread reads `self._iterator` when it runs, so it can pull the first batch from the new iterator. That batch is then thrown away when `_kick_prefetch()` overwrites `_prefetch_result`, and the first batch of the new pass is silently skipped.
  - The race happens when iteration is restarted mid-epoch (for example after a `break`).
  - `close()` also uses `join(timeout=10)`. If the old thread is still blocked in the scatter collective, it keeps running and races the new thread.
- **Fix:** Call `self.close()` before replacing `self._iterator`, and reset `_prefetch_result`.

## 5. `_pad_sequences_to_be_divisible_by` leaves `attention_mask` and `position_ids` at their unpadded length (low)

- **File:** `models/esm2/collator.py`, lines 213–227 (together with `_pt_flatten_collate` 721–728)
- **What goes wrong:** `_pt_flatten_collate` emits `attention_mask` whenever the features contain one (tokenized datasets usually do), and emits `position_ids` when `return_position_ids=True`. After per-sequence padding, `input_ids` and `labels` are longer, but `attention_mask` and `position_ids` keep the old length and old offsets. The batch is internally inconsistent.
  - `_pt_pad_to_multiple_of` (915–923) does pad both fields, so the two padding modes behave differently.
  - The ESM model happens to ignore these fields in THD mode. Any consumer that uses them, or that shards them with the CP collator, gets misaligned data.
- **Fix:** Pad or rebuild `attention_mask` and `position_ids` using `cu_seqlens_padded`, or drop them in this mode.

## 6. AMPLIFY TE: `layer_norm_before_last_layer=False` path ignores `padded_vocab_size` and cannot be converted (low)

- **File:** `models/amplify/src/amplify/amplify_te.py` lines 298–301, and `state_dict_convert.py` lines 386–393 and 453–476
- **What goes wrong:** In the else-branch the decoder is `Linear(hidden_size, vocab_size)`, not `padded_vocab_size`. The config documents `padded_vocab_size` as "the padded vocabulary size of the model to support fp8", and the other branch uses it.
  - `convert_amplify_hf_to_te` always pads `decoder.weight` and `decoder.bias` to `padded_vocab_size`, so converting such a model raises a shape mismatch in `apply_transforms`.
  - The mapping also unconditionally includes `layer_norm_2.weight` and never maps `layer_norm_1.weight`. Conversion therefore fails for any config with `layer_norm_before_last_layer=False` or `layer_norm_after_embedding=True`.
- **Fix:** Use `config.padded_vocab_size` in the else-branch. Build the mapping conditionally from the config flags, and add a `layer_norm_1` mapping.

## 7. AMPLIFY TE silently ignores `att_bias` / `ffn_bias` (low)

- **File:** `models/amplify/src/amplify/amplify_te.py`, line 190
- **What goes wrong:** `TransformerLayer(..., bias=False)` is hard-coded, but the config accepts and documents `att_bias` and `ffn_bias` (lines 82–83). A config with either set to True builds a model without biases, and no error is raised. Converting an HF checkpoint trained with biases would drop those weights (the `apply_transforms` source-side extra keys are not checked).
- **Fix:** Pass `bias=config.att_bias or config.ffn_bias`, or raise if either flag is True.

## 8. AMPLIFY HF reference model: the additive mask is always bfloat16, so fp32 inference with a mask fails (low)

- **File:** `models/amplify/src/amplify/amplify_hf.py`, line 361, used at lines 255–270
- **What goes wrong:** The additive mask is always cast to `torch.bfloat16`. With an fp32 model (the default dtype) and a non-trivial `attention_mask`:
  - On CPU, `scaled_dot_product_attention` rejects a mask whose dtype is neither bool nor the query dtype.
  - On CUDA, xformers `memory_efficient_attention` requires `attn_bias` to have the same dtype as the query.
  - So the model only works with masks when it runs in bf16.
- **Fix:** Cast to the activation dtype: `.to(self.encoder.weight.dtype)`, or to `x.dtype` inside the block.

---

### Considered and not reported
- QKV pack/unpack layout: it is consistent with TE `qkv_weight_interleaved=True`.
- `_pad_bias` using `finfo.min`: the padded logits are sliced off in any case.
- `TokenPackingDataset` split arithmetic: I checked that `tokens_available < sample_length` always holds.
- The `separator_id` indices.
- The CP zigzag shard indices.
- The TP replication ordering.
- `_pt_pad_to_multiple_of`.
- `NVEsmEncoder` mutating `config.layer_precision`: this looks intentional.
- Unused NeMo leftovers in `state.TransformFns`: these are not called by any in-scope code.

### Files read
- models/amplify/src/amplify/__init__.py
- models/amplify/src/amplify/amplify_hf.py
- models/amplify/src/amplify/amplify_te.py
- models/amplify/src/amplify/rmsnorm.py
- models/amplify/src/amplify/rotary.py
- models/amplify/src/amplify/metrics.py
- models/amplify/src/amplify/state_dict_convert.py
- models/amplify/src/amplify/export.py
- models/amplify/src/amplify/state.py (diffed against esm2/state.py; identical apart from a copied-file header)
- models/esm2/modeling_esm_te.py
- models/esm2/convert.py
- models/esm2/export.py
- models/esm2/collator.py
- models/esm2/state.py
- For context only, via grep: models/esm2/tests/test_cp_thd.py, test_cp_bshd.py, test_collator.py (token_dropout and padding usage)
