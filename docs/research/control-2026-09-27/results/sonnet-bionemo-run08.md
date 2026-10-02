# Code review: bionemo-recipes — `models/amplify/src/amplify/` and `models/esm2/` (excl. tests)

Repo: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
Pinned commit: `11701476b005ca7bc489df924a398b8f12453f0b`
Scope: `models/amplify/src/amplify/`, `models/esm2/` (excluding `tests/`)

## Defect 1: `_apply_token_dropout_thd` segments the physically-padded `input_ids` tensor with un-padded offsets

**File:** `models/esm2/modeling_esm_te.py`, function `NVEsmEmbeddings._apply_token_dropout_thd`, line 741 (function spans 719–745).

```python
def _apply_token_dropout_thd(self, embeddings, input_ids, kwargs):
    ...
    src_lengths = torch.diff(kwargs["cu_seq_lens_q"])                       # line 734
    if "cu_seq_lens_q_padded" in kwargs:
        src_lengths_padded = torch.diff(kwargs["cu_seq_lens_q_padded"])     # line 736
    else:
        src_lengths_padded = src_lengths
    is_masked = (input_ids == self.mask_token_id).squeeze(0)
    n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"]).sum(1)  # line 741
    mask_ratio_observed = n_masked_per_seq.float() / src_lengths
    scale_factor = (1 - mask_ratio_train) / (1 - mask_ratio_observed)
    reshaped_scale_factor = torch.repeat_interleave(scale_factor, src_lengths_padded, dim=0)  # line 744
    return (embeddings * reshaped_scale_factor.unsqueeze(-1)).to(embeddings.dtype)
```

**What goes wrong:** When context-parallel (CP) sequence packing with inter-sequence padding is used — i.e. `kwargs` contains `cu_seq_lens_q_padded` (set by the collator whenever `pad_sequences_to_be_divisible_by`/`DataCollatorForContextParallel` is used, see `collator.py` lines 213–226) — the physical `input_ids` tensor passed into this function is laid out according to `cu_seq_lens_q_padded`, not `cu_seq_lens_q`. This is established by `collator.py`'s own `pad_thd_sequences_for_cp` call, and is explicitly verified by the project's own test `test_thd_padding_input_data_equivalence` in `tests/common/test_modeling_common.py` (lines 782–810), which shows that `input_data_thd_padded["input_ids"]` only equals the unpadded `input_ids` after re-indexing with offsets derived from `cu_seq_lens_q_padded`.

Despite this, line 741 builds `is_masked`'s nested/jagged segmentation using `offsets=kwargs["cu_seq_lens_q"]` — the **unpadded** cumulative lengths — even though `is_masked` was computed from the **padded** physical `input_ids`. `torch.nested.nested_tensor_from_jagged` requires `values.shape[0] == offsets[-1]`; when padding has been inserted, `cu_seq_lens_q[-1] < cu_seq_lens_q_padded[-1] == input_ids.shape[-1]`, so the offsets no longer describe the physical tensor's segment boundaries. The function even computes the correct `src_lengths_padded` (line 736) for the final `repeat_interleave` step but never uses `cu_seq_lens_q_padded` (or `src_lengths_padded`) as the segmentation offsets for `is_masked` itself — an internal inconsistency within the same function.

**Effect:** With `torch.nested`, this will either raise a `RuntimeError` (size mismatch between `values` and `offsets[-1]`) or, if it accepts the mismatched trailing values silently, produce wrong per-sequence mask-token counts by pulling mask-token statistics from the wrong token range (each subsequent sequence's masked-token count would be computed against boundaries that drift by the accumulated padding). Either way, the token-dropout compensation scaling (`_apply_token_dropout_thd`'s whole purpose, per its own docstring: "scales embeddings accordingly using repeat_interleave") is corrupted for THD+CP-padded batches whenever `token_dropout=True` (the ESM-2 default, inherited from `EsmConfig`).

**Why it's wrong:** The function's own comment/design intent (and the parallel BSHD implementation `_apply_token_dropout_bshd`, which correctly divides by real, un-padded token counts) requires computing masked-token counts per real sequence. The code already recognizes the padded/unpadded distinction (it computes `src_lengths_padded` separately and applies it via `repeat_interleave` at the end) but fails to apply the same padded/unpadded distinction to the `nested_tensor_from_jagged` offsets used to compute `n_masked_per_seq`, even though `is_masked` (like `embeddings` at the end) is a physically-padded tensor.

**Corroborating evidence:** The project's own CP+THD tests (`tests/test_cp_thd.py` lines 187 and 238) explicitly pass `token_dropout=False` when constructing models for THD+CP testing, and none of the CP collator tests exercise `_apply_token_dropout_thd` with `token_dropout=True`. This suggests the THD+CP+token_dropout=True combination is untested and the bug has gone unnoticed. The only test that would exercise a padded-THD forward pass with default `token_dropout=True` is `test_golden_values_thd_padded` in `tests/common/test_modeling_common.py`, which is marked `xfail` for lack of datacenter GPU hardware (for an unrelated reason) rather than for this issue.

**Severity:** High. This corrupts embeddings (or crashes) for any training/inference run that combines THD sequence packing, context-parallelism (or any other caller that supplies `cu_seq_lens_q_padded`), and the model's default `token_dropout=True` setting — a supported, documented configuration combination.

**Suggested fix:** Use the padded offsets to segment the physically-padded `is_masked` tensor, consistent with how `reshaped_scale_factor` is later expanded:

```python
offsets_for_physical_layout = kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])
n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=offsets_for_physical_layout).sum(1)
```

(keeping `mask_ratio_observed = n_masked_per_seq.float() / src_lengths`, i.e. still normalizing by the *real*, un-padded sequence length, since the numerator should count only real mask tokens — which it will, since padding tokens are `pad_token_id`, not `mask_token_id`).

---

## Secondary observation (lower confidence): `AMPLIFY.forward` in `amplify_te.py` only inverts the attention mask for `torch.int64` masks

**File:** `models/amplify/src/amplify/amplify_te.py`, lines 244–247.

```python
if attention_mask is not None and attention_mask.dtype is torch.int64:
    # TE expects a boolean attention mask, where "True" indicates a token to be masked.
    attention_mask = ~attention_mask.to(bool)
```

The comment states the intended contract: an incoming `1=attend / 0=pad` mask must be inverted and turned boolean before being handed to Transformer Engine (which reads `True` as "mask this token"). This conversion is gated on `attention_mask.dtype is torch.int64` specifically. If a caller passes an attention mask of any other integer dtype (e.g. `torch.int32`, `torch.uint8`) or an already-boolean mask that uses the HF `1=attend` convention, the conversion is skipped and the mask is passed through unmodified — with `1=attend` semantics being interpreted by TE as `True=masked`, silently inverting which tokens are attended to. In common practice HF tokenizers emit `int64` attention masks, which likely explains why this hasn't surfaced, but the check as written is narrower than the stated contract ("TE expects a boolean attention mask ... indicates a token to be masked" — this is a statement about TE's expectation, not about the caller's dtype) and will silently produce incorrect attention for any caller supplying a differently-typed mask.

**Severity:** Low/Medium (narrow, dtype-dependent; not exercised by the tests in this checkout, which don't pass `attention_mask` to the TE model at all).

**Suggested fix:** Check the mask's *semantics*, not its dtype, e.g. always treat a non-bool integer/float mask as `1=attend` and convert, or explicitly document/assert the expected input dtype.

---

## Not flagged

I did not find defects I'm confident about elsewhere in scope, including in:
- `rotary.py`, `rmsnorm.py` — standard, matches well-known reference implementations.
- `amplify_hf.py` — standard HF reference implementation; the `attention_mask` all-zero short-circuit (lines 360–368) mirrors the upstream chandar-lab AMPLIFY code and only affects a degenerate all-padding-token edge case.
- `state_dict_convert.py` (amplify) / `convert.py` (esm2) — the QKV pack/unpack transforms are self-consistent inverses (verified the interleave/transpose/reshape math by hand); embedding/bias vocab-padding transforms are consistent between HF↔TE directions.
- `state.py` — generic transform-matching framework; complex but no defect found in shape/key handling, dtype tracking, or the wildcard-matching regex logic.
- `collator.py`'s CP zigzag sharding functions (`_process_tensor_thd`, `_process_tensor_bshd`, `_split_batch_by_cp_rank`) — index arithmetic is intricate but internally consistent; I did not find a discrepancy I could pin down with confidence (this required the most scrutiny after Defect 1 and could use closer review/test execution with GPU/CP hardware, which was unavailable in this environment).
- `export.py` (both models), `metrics.py` — no logic defects found.

## Environment note

No PyTorch/CUDA/`transformer_engine` was available in this environment, so this review is static (careful reading, cross-referencing with the project's own tests and docstrings) rather than execution-verified. I did not run any code.

## Files read

- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state.py` (diffed against esm2/state.py; identical apart from a "copied file" header)
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/amplify/tests/test_amplify_model.py` (for context: attention_mask usage)
- `models/amplify/tests/test_encoder_block.py` (for context: attention_mask usage)
- `models/esm2/collator.py` (full)
- `models/esm2/convert.py` (full)
- `models/esm2/export.py` (full)
- `models/esm2/modeling_esm_te.py` (full)
- `models/esm2/state.py` (full)
- `models/esm2/tests/common/test_modeling_common.py` (for context: THD/CP golden-value tests, `get_test_input_data`)
- `models/esm2/tests/test_cp_thd.py` (for context: `token_dropout=False` usage)
- `models/esm2/tests/test_cp_dataloader.py` (grep only, for `cu_seq_lens_q_padded` usage)
- `models/esm2/tests/test_collator.py`, `models/esm2/tests/test_collator_context_parallel.py` (grep only, for `cu_seq_lens_q_padded`/`pad_between_seqs` usage)
