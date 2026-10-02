model: gpt-5.6-terra
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:46:08 UTC; finished 2026-09-28 23:48:11 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Code review — BioNeMo AMPLIFY / ESM2

Reviewed commit `11701476b005ca7bc489df924a398b8f12453f0b` within the requested scope.

## Findings

### 1. Packed collation emits sequence metadata for tokens it has removed

- **Severity:** high
- **Location:** `models/esm2/collator.py:166-170`
- **What goes wrong:** `DataCollatorWithFlattening` claims to accept features that may contain `attention_mask` (`:108-110`).  For pre-padded features, it builds `cu_seq_lens_*` and `max_length_*` from the full `input_ids` lengths in `_pt_flatten_collate` (`:706-720`), then strips every masked-out token from `input_ids` and `labels` at `:169-170`.  For example, two length-4 inputs with masks `[1,1,0,0]` produce a four-token packed tensor but `cu_seq_lens_q == [0,4,8]`.  Flash/TE attention is consequently told to read eight tokens and has invalid sequence boundaries.
- **Why it is wrong:** The class documentation promises packed sequence boundaries that correspond to the packed tensor (`:44-51`, `:83-86`), and its return documentation defines `cu_seq_lens_q` as cumulative lengths for the returned flattened token sequences (`:121-130`).  These values instead describe discarded padding.
- **Suggested fix:** Before calling `_pt_flatten_collate`, trim each feature's sequence fields to the true length indicated by its attention mask (or explicitly reject pre-padded features).  Construct the masked token tensor and cumulative lengths from that same normalized feature list.

### 2. Restarting the context-parallel iterator can silently discard the first batch of the new epoch

- **Severity:** medium
- **Location:** `models/esm2/collator.py:500-508`
- **What goes wrong:** `__iter__` installs `self._iterator = iter(self.dataloader)` before it waits for the previous background prefetch thread in `self.close()`.  The old thread calls `_send_data_to_cp_tp_ranks`, which dereferences `self._iterator` later at `:579`.  If it has not reached that line when a caller restarts iteration (for example, an epoch ends early), it fetches the first batch from the *new* iterator.  `close()` then joins the thread and clears it without yielding its `_prefetch_result`; the newly started prefetch begins at batch two.  All ranks receive a consistent stream, but the first new-epoch batch is lost.
- **Why it is wrong:** The class says it wraps a dataloader and materializes its batches across the CP/TP group (`:468-477`).  Recreating an iterator must begin from that iterator's first batch.  The shared mutable iterator and asynchronous prefetch make that guarantee race-dependent.
- **Suggested fix:** Call `self.close()` before assigning a new `self._iterator` in `__iter__`.  More robustly, pass the iterator captured for a prefetch to the worker instead of having the worker read `self._iterator`.

### 3. AMPLIFY conversion fails when the source checkpoint is on CUDA

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/state_dict_convert.py:85-91`
- **What goes wrong:** `_pad_weights` constructs `padding_rows` with neither `dtype` nor `device`.  PyTorch therefore creates a CPU `float32` tensor.  Converting an HF model that was moved to CUDA makes `torch.cat((source_embed, padding_rows))` fail because the source weights are CUDA while the padding is CPU.  A CPU BF16/FP16 source also has its padded weights promoted to float32 instead of preserving its precision.
- **Why it is wrong:** `convert_amplify_hf_to_te` advertises conversion of an arbitrary supplied HF model (`:37-45`), and `_pad_bias` immediately below correctly preserves both dtype and device (`:113-116`).  The ESM2 equivalent uses the same preservation explicitly (`models/esm2/convert.py:243-246`).
- **Suggested fix:** Allocate with `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

## Files read

- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/README.md`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`

I also consulted the ESM2 tests only to confirm intended call patterns; no test-file findings are reported.
