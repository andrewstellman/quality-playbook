# Code review: bionemo-recipes — models/amplify/src/amplify/, models/esm2/ (excl. tests)

Repo: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
Pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
Checkout: /tmp/control/bionemo (read-only)

## Summary

I read every non-test file in the two review-scope directories. I did not find a defect I'm
confident is real and worth blocking on. Most of the logic in these files is either (a) vendored
verbatim from chandar-lab's AMPLIFY implementation (rotary.py, rmsnorm.py, amplify_hf.py) or the
HuggingFace ESM implementation, or (b) a generic state-dict-transform library
(state.py, identical between amplify/ and esm2/ apart from a "copied file" notice) that is
carefully defended with shape/dtype assertions. The QKV pack/unpack transforms, the vocab-padding
logic, the RoPE/attention-mask handling in the TE model classes, and the context-parallel
zig-zag sharding in collator.py all cross-checked out consistently against each other and
against their own docstrings/comments.

I spent the most time on the sections most likely to hide a real bug — the TE attention-mask
sign conventions in amplify_te.py vs. modeling_esm_te.py, the QKV interleaving in
state_dict_convert.py / convert.py, and the context-parallel index arithmetic in collator.py
(`_process_tensor_thd`, `_process_tensor_bshd`, `TokenPackingDataset.__iter__`) — and could not
find an input or configuration under which they produce an incorrect result, given how they are
actually invoked in this codebase.

I am flagging one low-severity issue below that I am confident is real (visible directly in the
code), but whose practical impact is limited and whose target function may not even be live code
(it is marked with a "TODO: is this method even used?" in the source itself).

## Finding 1 (low severity, low-to-medium confidence in impact)

**File:** `models/amplify/src/amplify/metrics.py`, lines 26, 48-68

**What:** `perplexity = Perplexity(ignore_index=-100, sync_on_compute=False)` is a single
module-level `torchmetrics` object. `compute_metrics()` calls `perplexity(logits, labels)` on
every batch and only calls `perplexity.reset()` inside the `if compute_result:` branch, i.e.
only once the eval loop is judged complete.

**Why it's wrong:** If an evaluation run is interrupted before `compute_result=True` is ever
passed (an exception mid-eval, an early-stopped run, or any caller that invokes
`compute_metrics` again without having driven a prior call to completion), the accumulated
state inside the shared `perplexity` object is never cleared. Because the object is
module-level rather than constructed fresh per evaluation, the next evaluation's perplexity
would be computed over its own batches *plus* whatever was left over from the aborted run,
silently corrupting the reported metric.

**Severity:** low — the file itself contains `# TODO (peter): Is this method even used?`,
suggesting this path may be dead code in current pipelines, and under the intended
happy-path usage (drive the HF `Trainer`'s eval loop to normal completion every time) the bug
never manifests.

**Suggested fix:** construct a fresh `Perplexity()` instance per evaluation (e.g., store it on
whatever object owns the eval loop, or reset it in a `on_evaluate_begin`-style hook) rather than
relying on a process-wide singleton that is only reset on the success path.

## Areas checked with no defect found

- `models/amplify/src/amplify/rotary.py`, `rmsnorm.py` — unmodified vendor code (RoPE math,
  broadcast-shape assertions, RMSNorm) — checked against their own docstrings, consistent.
- `models/amplify/src/amplify/amplify_hf.py` — HF/xformers reference implementation; attention
  mask construction, SwiGLU intermediate-size rounding, and MaskedLM loss all consistent with
  the module's own docstrings.
- `models/amplify/src/amplify/amplify_te.py` — TE model class. Verified: `padded_vocab_size`
  invariant is asserted; the boolean attention-mask inversion (`~attention_mask.to(bool)`)
  correctly flips "1 = valid" to TE's "True = masked" convention; the padded-vocab logit
  truncation in `AMPLIFYForMaskedLM.forward` is a no-op (not a bug) when
  `layer_norm_before_last_layer=False`, since in that branch the decoder already emits
  `vocab_size` columns.
- `models/amplify/src/amplify/state_dict_convert.py` — `_pack_qkv_weight`'s
  reshape/transpose sequence produces per-head-interleaved QKV rows, matching
  `qkv_weight_interleaved=True` used when constructing the TE `TransformerLayer`s in
  amplify_te.py. `_pad_bias`'s use of `torch.finfo(dtype).min` (vs. zero for
  `_pad_weights`) is intentional: combined with zero-padded decoder weight rows it drives the
  padded-vocab logits to a very negative value so they never win an argmax.
- `models/amplify/src/amplify/export.py` — sanity-checked control flow (save → patch config →
  smoke-test reload); no defect found (this is developer/export tooling, not modeling code).
- `models/esm2/state.py` — byte-for-byte identical to `models/amplify/src/amplify/state.py`
  apart from the "copied file" header (as documented by the file's own "BEGIN COPIED FILE
  NOTICE"); same conclusion as above.
- `models/esm2/modeling_esm_te.py` — cross-checked `NVEsmModel.forward`'s
  `AttentionMaskConverter(...).to_4d(...)` + `< -1` boolean-mask construction against TE's
  documented "True = masked" convention (matches). Checked `NVEsmEmbeddings`' token-dropout
  scaling order (mask → dropout-scale → layer_norm → attention_mask multiply) against the
  upstream HF ESM ordering described in the code's own comment — matches. Checked
  `padded_vocab_size` truncation in `NVEsmForMaskedLM.forward` and the `_tied_weights_keys`
  shapes — consistent.
- `models/esm2/convert.py` — verified `_pack_qkv_weight`/`_unpack_qkv_weight` and
  `_pack_qkv_bias`/`_unpack_qkv_bias` are exact inverses of each other for the interleaved
  layout TE expects; verified `_pad_weights`/`_unpad_weights` and `_pad_bias`/`_unpad_bias`
  round-trip correctly.
- `models/esm2/export.py` — `padded_vocab_size=None` passed intentionally to keep the exported
  checkpoint's embedding at the true vocab size (matches its own comment about
  `VocabParallelEmbedding` in vLLM).
- `models/esm2/collator.py` (1036 lines) — this got the closest scrutiny:
  - `DataCollatorWithFlattening.__call__`: the BSHD→THD "unpad via boolean mask on
    attention_mask" step and the `separator_id` boundary-masking (`cu_seq_lens_q[1:-1]`) are
    consistent with the documented packing behavior.
  - `TokenPackingDataset.__iter__`/`_padded_len`: the three branches (`==`, `>`, else) covering
    `current_length` vs. `max_tokens_per_batch`, and the `split_samples` sub-branch, are
    exhaustive and internally consistent; `_split_sample_by_num_tokens` correctly slices all
    sequence-typed fields.
  - `_pt_pad_to_multiple_of`: `remainder = -numel % pad_to_multiple_of` correctly computes the
    ceiling-padding amount; `cu_seq_lens_q`/`k`, `attention_mask`, and `position_ids` are all
    extended consistently for the appended mock sequence.
  - `_process_tensor_thd` / `_process_tensor_bshd` / `_split_batch_by_cp_rank`: implement the
    standard zig-zag CP split. `_process_tensor_thd` floor-divides each sequence's padded
    length by `2 * cp_world_size` without an explicit divisibility check (unlike
    `_process_tensor_bshd`, which raises `ValueError` on a non-divisible sequence length) —
    this *could* silently drop trailing tokens from a shard if a caller supplied a
    `cu_seqlens_padded` whose per-sequence lengths were not multiples of `2 * cp_world_size`.
    I'm not reporting this as a confirmed defect because every call site in this repository
    that sets `pad_sequences_to_be_divisible_by` (the value used to build `cu_seqlens_padded`)
    sets it to exactly `cp_mesh.size() * 2` (see `recipes/esm2_native_te/dataset.py:258`,
    `recipes/llama3_native_te/train_fsdp2_cp.py:220`, etc. — outside the review scope, but they
    are the only production callers), so the precondition that would trigger data loss is never
    violated by the codebase itself. It would be worth an explicit assertion in
    `_process_tensor_thd`/`_split_batch_by_cp_rank` for defense-in-depth, but I can't call this
    a confirmed defect within the reviewed files alone.

## Files read

- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/state.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/state.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/collator.py`

Also referenced (read-only, for context / cross-checking call sites, not part of the review
scope): `recipes/esm2_native_te/dataset.py`, `recipes/esm2_native_te/collator.py`,
`recipes/llama3_native_te/train_fsdp2_cp.py`, `recipes/opengenome2_llama_native_te/train_fsdp2_cp.py`
(grepped for `pad_sequences_to_be_divisible_by` usage only).
