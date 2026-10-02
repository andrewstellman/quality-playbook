model: gpt-5.6-terra
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:50:39 UTC; finished 2026-09-28 23:53:09 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Code review: bionemo (AMPLIFY and ESM2)

Reviewed commit `11701476b005ca7bc489df924a398b8f12453f0b` in the requested scope.

## Findings

### 1. THD context-parallel sharding silently drops sequence tokens unless every sequence is divisible by `2 * cp_world_size`

- **File/line:** `models/esm2/collator.py:975-987` (with the truncating slice calculation at 975 and selection at 789-808)
- **Severity:** high
- **What goes wrong:** For THD input, the code computes each sequence's slice length with floor division and never checks the remainder.  For example, with `cp_world_size=2` and a padded sequence length of 10, `slice_size` is 2.  Rank 0 receives positions `[0,1,6,7]` and rank 1 receives `[2,3,4,5]`; positions `[8,9]` are sent to no rank.  Training therefore silently omits tokens and their losses rather than rejecting or padding an invalid batch.
- **Why this is wrong:** `_split_batch_by_cp_rank` describes its job as slicing the batch across CP GPUs, and the THD helper says each rank selects its two CP slices.  The BSHD branch immediately below explicitly rejects a sequence length that is not divisible by `2 * cp_world_size` (lines 841-849), but the THD branch accepts the equivalent invalid input and truncates it.  `DataCollatorForContextParallel` accepts an arbitrary wrapped collator, so there is no guarantee that its `cu_seq_lens_q_padded` lengths have already been padded to this divisor.
- **Suggested fix:** Before calculating `slice_sizes`, validate that every value in `cu_seqlens_padded[1:] - cu_seqlens_padded[:-1]` is divisible by `2 * cp_world_size`, raising `ValueError` otherwise.  Alternatively, pad every sequence to that divisor before sharding and update the cumulative lengths and labels accordingly.

### 2. Restarting the context-parallel loader can let the old prefetch thread consume the new iterator, and can issue overlapping collectives

- **File/line:** `models/esm2/collator.py:500-508`, `523-548`
- **Severity:** high
- **What goes wrong:** Calling `iter(wrapper)` while the previous epoch's prefetch is still running first replaces `self._iterator` (line 503), then calls `close()` (line 504).  The old thread dereferences `self._iterator` only later in `_send_data_to_cp_tp_ranks` (line 579), so it can consume the first batch of the *new* iterator.  `close()` also merely joins for ten seconds and then discards the thread reference without a cancellation mechanism.  If that thread is blocked in `scatter_object_list`, a subsequent `_kick_prefetch()` starts another thread that performs a distributed scatter concurrently with it, which can deadlock ranks or mismatch collective ordering.
- **Why this is wrong:** The class presents `close()` as stopping the prefetch thread and specifically says it must be used before `destroy_process_group()` (lines 544-548).  It neither stops nor verifies completion of a live thread, while `_send_data_to_cp_tp_ranks` performs a blocking distributed collective (lines 585 and 1029-1035).  A loader restart or shutdown with an outstanding prefetch thus has externally visible data loss or distributed-hang behavior.
- **Suggested fix:** Stop and join the old prefetch before assigning a new iterator, and make shutdown cooperative (for example with an event checked before entering the next fetch/collective).  Do not clear `_prefetch_thread` or start a replacement until the prior thread has completed; arrange collective shutdown consistently on every rank.

### 3. AMPLIFY CPU/float32 inference fails for ordinary padded attention masks

- **File/line:** `models/amplify/src/amplify/amplify_hf.py:360-366`, `263-270`
- **Severity:** medium
- **What goes wrong:** Whenever a nontrivial 0/1 attention mask is supplied, `forward` converts its additive mask to `torch.bfloat16` unconditionally.  A newly constructed AMPLIFY model is float32 by default, and its CPU attention path passes float32 queries together with that bfloat16 floating-point mask to `scaled_dot_product_attention`.  PyTorch's SDPA API requires a floating-point mask to have the query dtype (the alternative is a boolean mask), so normal padded float32 CPU inputs raise a dtype error instead of producing logits.
- **Why this is wrong:** The function accepts an `attention_mask` as part of its documented forward API (lines 334-350), and the CPU path deliberately uses PyTorch SDPA (lines 262-270).  The mask creation does not derive its dtype from `x`, so it violates SDPA's mask-dtype contract whenever model/input dtype is not bfloat16.
- **Suggested fix:** Build the additive mask in the query dtype, e.g. `.to(dtype=x.dtype, device=x.device)` after embeddings are available, or use a boolean mask with the polarity expected by SDPA.  The GPU/xFormers path should likewise receive a mask dtype compatible with its query tensor.

### 4. AMPLIFY checkpoint conversion creates CPU float32 padding rows regardless of the source checkpoint's device or dtype

- **File/line:** `models/amplify/src/amplify/state_dict_convert.py:85-91`
- **Severity:** medium
- **What goes wrong:** `_pad_weights` creates `torch.zeros(num_padding_rows, source_embed.size(1))` without `dtype` or `device`.  When `convert_amplify_hf_to_te` is called on a CUDA checkpoint (or a BF16/FP16 CPU checkpoint), concatenating its embedding or decoder weights with these default CPU float32 rows fails because `torch.cat` requires the same device and dtype, or produces the wrong dtype if an implementation permits promotion.
- **Why this is wrong:** `convert_amplify_hf_to_te` is documented to convert an arbitrary Hugging Face `nn.Module` (lines 37-45) and applies this transform to both embedding and decoder weights (lines 94-102).  The ESM2 converter implements the same operation with `dtype=source_embed.dtype, device=source_embed.device` ( `models/esm2/convert.py:238-246` ), which establishes the required preservation behavior for this shared conversion pattern.
- **Suggested fix:** Create the padding with `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)` (or `source_embed.new_zeros(...)`).

## Files read

- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/README.md`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/state.py`
