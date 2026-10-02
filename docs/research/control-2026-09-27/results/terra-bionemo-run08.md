model: gpt-5.6-terra
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:52:46 UTC; finished 2026-09-28 23:55:44 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review — `models/amplify/src/amplify/` and `models/esm2/`

Reviewed commit: `11701476b005ca7bc489df924a398b8f12453f0b`.

## Findings

### 1. Boolean attention masks are passed to Transformer Engine with the opposite meaning

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/amplify_te.py:245-247`
- **What goes wrong:** Passing a normal boolean Hugging Face attention mask (for example, `[[True, True, False]]`, where `True` denotes a real token) makes TE mask the real tokens and leave the padding token attendable.  The conversion to TE's convention runs only when the dtype is exactly `torch.int64`; boolean masks (and integer masks such as `int32`) bypass it unchanged.
- **Why this is wrong:** The adjacent comment states that TE uses `True` to mean “token to be masked.” The other AMPLIFY implementation treats a standard 1/0 attention mask as attended/masked respectively (`amplify_hf.py:359-368`).  A boolean standard mask has the same 1/0 semantics, so passing it directly reverses the mask at the TE layer.
- **Suggested fix:** Normalize every ordinary 1/0 mask independent of its integer/boolean dtype, e.g. validate that it is a padding mask and use `attention_mask = ~attention_mask.to(torch.bool)`. If additive/TE-native masks are intended to be accepted too, add an explicit format/dtype contract and separate branch rather than treating all non-`int64` tensors as TE-native.

### 2. AMPLIFY checkpoint conversion fails for source weights on CUDA

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/state_dict_convert.py:85-91`
- **What goes wrong:** `convert_amplify_hf_to_te()` fails while padding embeddings/decoder weights when the source HF model has been moved to CUDA. `_pad_weights` allocates `padding_rows` with no `device` or `dtype`, so it is a CPU `float32` tensor; `torch.cat((source_embed, padding_rows))` cannot concatenate it with CUDA source weights (and can also introduce an unwanted dtype promotion for non-float32 source weights).
- **Why this is wrong:** This is the padding transform used by the public converter at lines 51-56. The neighboring `_pad_bias` correctly allocates using `dtype=source_bias.dtype, device=source_bias.device` at lines 113-115, demonstrating the needed preservation of the source tensor placement and type.
- **Suggested fix:** Create the padding rows with `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)` (or `torch.zeros_like(source_embed[:num_padding_rows])`).

### 3. Restarting the context-parallel iterator can leave an old prefetch collective running concurrently with a new one

- **Severity:** medium
- **Location:** `models/esm2/collator.py:500-508` and `544-548`
- **What goes wrong:** Calling `iter(wrapper)` while its previous prefetch is blocked for more than ten seconds clears the old thread handle and immediately starts a new prefetch thread. Both can then call the ordered distributed `scatter_object_list` collective concurrently. Further, `__iter__` replaces `self._iterator` before it calls `close`, so the older thread may consume the new iterator. This can reorder collectives across ranks or cause a distributed deadlock.
- **Why this is wrong:** `_do_one_prefetch` performs a collective scatter (lines 528-542 and 585 in `_send_data_to_cp_tp_ranks`), which must be invoked in the same order on every rank. `close` claims to “Stop the prefetch thread,” but only waits ten seconds and drops the reference even if the daemon thread is still alive. The next `__iter__` call then starts another thread at line 508.
- **Suggested fix:** Close and fully join the existing prefetch before replacing `_iterator` or starting another prefetch. Do not discard a live thread after a timeout; either wait for completion (with a documented cancellation/teardown path) or fail loudly so no second collective can begin. Assign the replacement iterator only after the old prefetch is known to be finished.

## Files read

- `AGENTS.md`
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
