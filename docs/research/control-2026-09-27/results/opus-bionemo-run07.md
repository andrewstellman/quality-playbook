# Code review: bionemo (NVIDIA-BioNeMo/bionemo-recipes @ 11701476)

Scope: `models/amplify/src/amplify/`, `models/esm2/` (excluding tests).
Nothing could be executed: PyTorch and Transformer Engine are not installed. All findings come from reading the code, the in-repo tests, and the call sites in the repo.

---

## 1. THD token-dropout counts masked tokens over the wrong segments when sequences are padded (`pad_between_seqs`)

- **File/line:** `models/esm2/modeling_esm_te.py:734-745` (`NVEsmEmbeddings._apply_token_dropout_thd`)
- **What goes wrong:** When the batch comes from `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=N)`, `input_ids` uses the *padded* layout. Its length is `cu_seq_lens_q_padded[-1]`, and sequence *i* starts at `cu_seq_lens_q_padded[i]`. The code correctly uses `cu_seq_lens_q_padded` for `repeat_interleave` (line 744). But the per-sequence masked-token count at line 741 is taken with `nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"])`, which uses the *unpadded* offsets. For every sequence after the first, the count window `[cu_seq_lens_q[i], cu_seq_lens_q[i+1])` is shifted relative to where that sequence actually sits in the padded tensor. The window takes in the previous sequence's pad tokens and the tail of the sequence before it, and it misses this sequence's own last tokens. The values tensor is also longer than `offsets[-1]`, so the trailing tokens are never counted.
- **Effect:** `mask_ratio_observed` and the token-dropout `scale_factor` are wrong per sequence. So the embeddings, and therefore the logits and loss, differ between padded THD and unpadded THD/BSHD inputs for the same data. ESM-2 checkpoints ship with `token_dropout=True`, so this path is on by default. The padded-THD golden test (`tests/common/test_modeling_common.py::test_golden_values_thd_padded`) uses a logits `atol` of 2.0, which is loose enough to hide the difference.
- **Why it's wrong:** The docstring says it computes "per-sequence mask ratios", and the comment at line 739 says "We need to find the number of masked tokens in each sequence in the padded batch". The offsets used don't describe the padded batch.
- **Severity:** Medium (silent numerical error in training/inference with per-sequence padding, used for context parallelism and FP8 alignment).
- **Fix:** Count over the padded layout. Pad positions hold `pad_token_id`, not `<mask>`, so they don't change the count:
  ```python
  offsets = kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])
  n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=offsets).sum(1)
  mask_ratio_observed = n_masked_per_seq.float() / src_lengths   # real (unpadded) lengths
  ```

## 2. AMPLIFY HF→TE conversion breaks for any non-fp32 or non-CPU source model (padding rows are hard-coded fp32/CPU)

- **File/line:** `models/amplify/src/amplify/state_dict_convert.py:85-91` (`_pad_weights`)
- **What goes wrong:** `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))` is created with the default dtype (float32) on CPU. The default `vocab_size=27` and `padded_vocab_size=32` mean 5 rows are always padded.
  - If the HF model is bf16/fp16, `torch.cat` type-promotes the embedding/decoder weight to float32. The target model is built with `te_config.dtype`, taken from `model_hf.config`, so it is bf16. `apply_transforms` then fails its dtype check (`state.py:233-237`, "dtype mismatch for key amplify.encoder.weight").
  - If the HF model is on CUDA, `torch.cat` raises a device-mismatch error.
- **Why it's wrong:** `apply_transforms` requires converted parameters to keep the target dtype. The ESM-2 copy of this helper (`models/esm2/convert.py:243-245`) was fixed to pass `dtype=source_embed.dtype, device=source_embed.device`. The AMPLIFY one was not. The tests only convert fp32 CPU models (`tests/test_amplify_model.py:72-76` converts first, then casts), so this goes unnoticed.
- **Severity:** Medium.
- **Fix:** `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

## 3. `ContextParallelDataLoaderWrapper.state_dict()` saves a state one batch ahead of training (the prefetched batch is lost on resume), and reads it while the prefetch thread may be mutating it

- **File/line:** `models/esm2/collator.py:511-521` (`__next__` → `_kick_prefetch`), `592-603` (`state_dict`)
- **What goes wrong:** Right after `__next__` returns batch *k*, it starts a background thread that calls `next(self._iterator)` for batch *k+1*. `state_dict()` delegates straight to `self.dataloader.state_dict()` on rank 0. When a checkpoint is saved after step *k*, the state already counts batch *k+1* as consumed, or is read while that `next()` is running on another thread. After `load_state_dict` and resume, batch *k+1* is skipped: it was never trained on. The race also makes the saved state nondeterministic.
- **Where it matters:** The in-repo recipe `recipes/opengenome2_llama_native_te/train_fsdp2_cp.py:280,347-355` passes this wrapper as the `dataloader` to `save_checkpoint_fsdp2` inside the training loop when `use_stateful_dataloader` is set.
- **Why it's wrong:** `state_dict`/`load_state_dict` claim to delegate the dataloader state for checkpoint/resume. With one-batch prefetch, the delegated state is not the state of the batches actually returned to the caller.
- **Severity:** Medium (silent data skipping on every resume; it matters for exact-resume reproducibility).
- **Fix:** In `state_dict()`, first join the prefetch thread. Then either snapshot the dataloader state *before* each prefetch (keep `self._state_before_prefetch`, captured in `_do_one_prefetch` before `next()`) and return that snapshot, or drop the prefetched batch and re-kick the prefetch after loading.
- **Related (low):** `__iter__` (lines 502-504) assigns `self._iterator = iter(self.dataloader)` *before* `self.close()` joins the previous prefetch thread. That thread reads `self._iterator` when it runs (line 579), so if it hasn't reached that line yet it pulls the first batch of the new iterator. That batch is then overwritten by the new prefetch and dropped. With a persistent-workers DataLoader, `iter()` also resets the same iterator object while the old thread may be inside `next()` on it. Fix: call `self.close()` before creating the new iterator.

## 4. `DataCollatorWithFlattening` with `pad_sequences_to_be_divisible_by` leaves `attention_mask` / `position_ids` at the unpadded length

- **File/line:** `models/esm2/collator.py:204-227` (`_pad_sequences_to_be_divisible_by`)
- **What goes wrong:** `input_ids` and `labels` are replaced with padded tensors. But `attention_mask` is always present when features come from a tokenizer (`_pt_flatten_collate` copies it, lines 721-724), and `position_ids` is present when `return_position_ids=True`. Neither is padded, so the returned batch has tensors of different lengths along the token dimension. Compare `_pt_pad_to_multiple_of` (lines 915-923), which pads both for the other padding mode.
- **Why it's wrong:** The class docstring says `attention_mask` has "1s for actual tokens and 0s for padding tokens (if any)" and is the same shape as `input_ids`. Any consumer that indexes `position_ids`/`attention_mask` against `input_ids` gets misaligned data. The NVEsm model itself drops `attention_mask` in THD mode, which is why this doesn't crash there.
- **Severity:** Low.
- **Fix:** Insert pad entries in the same places for `attention_mask` (0) and `position_ids` (0..pad-1, restarting per pad block), using the `cu_seqlens_padded` returned by `pad_thd_sequences_for_cp`. Or drop those keys in this mode.

## 5. AMPLIFY TE model's attention mask meaning depends on its dtype (only `int64` is inverted)

- **File/line:** `models/amplify/src/amplify/amplify_te.py:245-247`
- **What goes wrong:** An HF-convention mask (1 = attend) is inverted to TE's convention (True = masked) only when `attention_mask.dtype is torch.int64`. A mask given as `bool`, `int32`, or float, with the same 1 = attend meaning, is passed to TE unchanged. TE then masks exactly the real tokens and attends to padding. The reference HF model in the same package (`amplify_hf.py:367-368`, `torch.where(attention_mask == 1, 0, -inf)`) treats any dtype with 1 = attend. So the two models silently disagree for the same bool/int32 input.
- **Why it's wrong:** The comment says TE needs "True" for masked tokens. The code only adapts one integer dtype and silently accepts others with the opposite meaning. The in-repo encoder-block test feeds the same bool mask to both conventions, and its attention-output comparison is commented out (`tests/test_encoder_block.py:84,217,237-242`).
- **Severity:** Low (HF tokenizers return int64, so the common path works).
- **Fix:** Normalise regardless of dtype for non-bool masks: `attention_mask = attention_mask == 0` for any integer/float mask. Document that bool masks must already use TE's convention, or also convert bool masks with `~attention_mask`.

---

## Things checked and not reported (judged correct or intentional)

- `TokenPackingDataset.__iter__` split arithmetic: when `max_tokens_per_batch` is a multiple of `d`, `tokens_available` is always less than `sample_length`, so `_split_sample_by_num_tokens` never raises.
- CP zig-zag sharding in `_process_tensor_thd` and `_process_tensor_bshd`, and TP replication ordering.
- QKV pack/unpack in `convert.py`: `_pack_qkv_*` and `_unpack_qkv_*` are inverses.
- `_pad_bias`/`_unpad_bias` and vocab padding/truncation in `NVEsmForMaskedLM`.
- `state.py` key matching and transforms. The `TransformFns` helpers use inconsistent config attributes, but nothing in scope calls them.

## Files read

- `models/esm2/collator.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/convert.py`
- `models/esm2/state.py`
- `models/esm2/export.py`
- `models/esm2/esm_fast_tokenizer/special_tokens_map.json`, `tokenizer.json` (post-processor/vocab), `tokenizer_config.json` (partial)
- `models/amplify/src/amplify/__init__.py`, `amplify_te.py`, `amplify_hf.py`, `state_dict_convert.py`, `export.py`, `rmsnorm.py`, `rotary.py`, `metrics.py`, `state.py` (diffed against the esm2 copy; identical apart from the header notice)
- For context only: `models/esm2/tests/test_modeling_esm_te.py` (input-data helper), `models/esm2/tests/common/test_modeling_common.py` (padded-THD tests), `models/amplify/tests/test_encoder_block.py`, `models/amplify/tests/test_amplify_model.py` (grep), `recipes/opengenome2_llama_native_te/train_fsdp2_cp.py` (grep for checkpoint use of the wrapper)
