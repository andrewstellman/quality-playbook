# Code review: bionemo-recipes — models/amplify/src/amplify/, models/esm2/ (excl. tests)

Repo: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
Pinned commit: `11701476b005ca7bc489df924a398b8f12453f0b`
Scope: `models/amplify/src/amplify/`, `models/esm2/` (excluding `tests/`)

Environment note: PyTorch/transformer_engine are not installed in the review sandbox, so this is a static review (with one cross-check against the project's own tests to confirm which code paths are/aren't exercised). No tests were executed.

## Defect 1 — `_pad_weights` in `state_dict_convert.py` creates padding on the wrong device/dtype

**File:** `models/amplify/src/amplify/state_dict_convert.py`, lines 85–91

```python
def _pad_weights(ctx: io.TransformCTX, source_embed):
    """Pad the embedding layer to the new input dimension."""
    target_embedding_dimension = ctx.target.config.padded_vocab_size
    hf_embedding_dimension = source_embed.size(0)
    num_padding_rows = target_embedding_dimension - hf_embedding_dimension
    padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))
    return torch.cat((source_embed, padding_rows), dim=0)
```

`padding_rows` is created with `torch.zeros(...)` and no `dtype=`/`device=` arguments, so it always lands on CPU in `float32`, regardless of `source_embed`'s actual dtype/device. This function backs both `_pad_embeddings` (`encoder.weight`) and `_pad_decoder_weights` (`decoder.weight`) in `convert_amplify_hf_to_te`.

This is inconsistent with two other places in the same codebase that solve the identical problem correctly:
- The sibling function `_pad_bias` in the very same file (lines 109–116) does specify `dtype=source_bias.dtype, device=source_bias.device`.
- The parallel `_pad_weights` in `models/esm2/convert.py` (lines 238–246) also specifies `dtype=source_embed.dtype, device=source_embed.device`.

That contrast makes it clear this is an oversight rather than an intentional choice.

**What goes wrong, and when:** `convert_amplify_hf_to_te()` builds the target TE model on the `meta` device via `init_empty_weights()` with `dtype=te_config.dtype` (taken from the HF model's config), then calls `apply_transforms`, which (unless `cast_dtype` is passed) asserts that every target parameter's dtype is unchanged from what the empty/meta model was constructed with (`state.py` lines 238–243: `assert target_orig_dtypes[key] == target_new_dtypes[key]`).

- If `model_hf`'s embedding/decoder weights are on CUDA when passed into `convert_amplify_hf_to_te` (e.g. a caller loads the checkpoint onto GPU before converting, or upstream code moves the model to CUDA first — a natural thing to do for large checkpoints), `torch.cat((source_embed, padding_rows), dim=0)` will raise a device-mismatch `RuntimeError`, because `source_embed` is on CUDA and `padding_rows` is on CPU.
- If `model_hf`'s weights are in `bfloat16`/`float16` (e.g. loaded with `dtype=torch.bfloat16`) but stay on CPU, `torch.cat` between a `bfloat16` tensor and a `float32` tensor performs type promotion to `float32`, silently changing `amplify.encoder.weight`'s and `decoder.weight`'s dtype. This then trips the dtype-preservation assertion in `apply_transforms` (`state.py` ~line 241), aborting conversion with an `AssertionError`.

The project's own tests (`tests/test_amplify_model.py::test_convert_state_dict`, `test_te_trained_model_loss`, etc.) always call `amp_hf.AMPLIFY.from_pretrained(...)` (which defaults to CPU/`float32`) and only move to CUDA/`bfloat16` *after* calling `convert_amplify_hf_to_te`, so this path is never exercised by the existing test suite — the bug is latent, not caught by CI.

**Severity:** Medium. It doesn't silently corrupt model outputs in the common CPU/float32 path exercised by the test suite, but it breaks `convert_amplify_hf_to_te` (and therefore `export_hf_checkpoint`, `export.py`) for any caller who loads the source HF checkpoint onto GPU or in a non-`float32` dtype before converting — a realistic pattern for larger checkpoints.

**Suggested fix:** Mirror `_pad_bias` (same file) and `esm2/convert.py::_pad_weights`:

```python
padding_rows = torch.zeros(
    num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device
)
```

## Defect 2 — `AMPLIFY.forward` (TE) only converts `int64` attention masks, silently mishandling other mask dtypes

**File:** `models/amplify/src/amplify/amplify_te.py`, lines 244–247

```python
# Attention mask
if attention_mask is not None and attention_mask.dtype is torch.int64:
    # TE expects a boolean attention mask, where "True" indicates a token to be masked.
    attention_mask = ~attention_mask.to(bool)
```

The comment states the intended contract: TE needs a boolean mask where `True` = "mask this token out". The code only performs the inversion (`~attention_mask.to(bool)`, which correctly turns the standard HF convention — `1`/`True` = attend, `0`/`False` = pad — into TE's `True` = masked convention) when `attention_mask.dtype is torch.int64`.

If a caller passes an `attention_mask` that is already `torch.bool` (a perfectly standard/expected type for an "attention mask" argument — `torch.Tensor` is all the type hint promises, and HF's own `_prepare_4d_attention_mask`-style utilities and many custom collators use `bool` masks) or any integer dtype other than `int64` (e.g. `int32`), the `is torch.int64` check is `False`, so **no inversion happens**. The mask is then handed to `transformer_engine.pytorch.TransformerLayer` unchanged, i.e. with `True` = attend / `False` = pad — exactly the opposite of what the code's own comment says TE requires. The practical effect: valid tokens get masked out and padding tokens get attended to, silently producing wrong (not even NaN, just quietly incorrect) results whenever a non-`int64` mask is supplied.

For comparison, the HF reference implementation in the same package, `amplify_hf.py` (lines 360–361), builds its additive mask with a value comparison (`torch.where(attention_mask == 1, ...)`), which is dtype-agnostic and works correctly for `int`, `bool`, or `float` masks alike. The TE port is therefore both less robust than its HF sibling and inconsistent with `models/esm2/modeling_esm_te.py`'s `NVEsmModel.forward`, which derives its boolean TE mask via `AttentionMaskConverter(...).to_4d(...)` followed by a numeric threshold (`extended_attention_mask < -1`) rather than a dtype sniff — that approach is immune to this class of bug.

In the checked-in test fixtures (`tests/conftest.py::input_data`), the mask always comes from `DataCollatorForLanguageModeling`/tokenizer output, which is `int64`, so this path isn't exercised by the test suite either.

**Severity:** Medium/Low — real correctness bug (silently inverted masking) under a plausible but not-default input (non-`int64` attention mask). Not observed to be hit by any in-scope caller with a non-`int64` mask, so I can't point to a concrete call site that triggers it today, hence the lower-than-Defect-1 confidence.

**Suggested fix:** Convert unconditionally and robustly, independent of dtype, mirroring the HF version's dtype-agnostic approach, e.g.:

```python
if attention_mask is not None:
    attention_mask = ~attention_mask.to(torch.bool)
```

(or an explicit `if attention_mask.dtype != torch.bool:` guard if there's a real need to accept pre-inverted boolean masks as-is — but if so, that contract should be documented, since right now nothing distinguishes "not yet inverted" from "already TE-format" except an incidental `int64` dtype check that also excludes `int32`.)

## Other things checked, no defect found

- `rotary.py`, `rmsnorm.py`: unmodified vendor copies from the upstream AMPLIFY repo; look correct against the standard interleaved-RoPE / RMSNorm formulas.
- `amplify_hf.py` / `amplify_te.py` config, `EncoderBlock`, RoPE application, SwiGLU intermediate-size rounding, vocab padding + logit truncation (`padded_vocab_size` vs `vocab_size`), weight tying: consistent between the two implementations and internally consistent.
- `state.py` (identical in both `amplify/` and `esm2/`, as its own header requires): the `StateDictTransform`/`apply_transforms` machinery, wildcard matching, and dtype-preservation checks look correct; traced through several non-trivial paths (multi-source vs multi-target matching, `TransformFns.merge_qkv`/`split_qkv`) without finding an off-by-one or shape error.
- `state_dict_convert.py` (amplify) / `convert.py` (esm2): the `_pack_qkv_weight`/`_unpack_qkv_weight` and bias equivalents are correct inverses of each other (traced the head/QKV reshape-transpose sequence both directions).
- `modeling_esm_te.py`: `NVEsmModel`'s padding-mask construction via `AttentionMaskConverter.to_4d(...)` + `< -1` threshold is correct and dtype-robust; token-dropout scaling (`_apply_token_dropout_bshd`/`_apply_token_dropout_thd`) matches the documented/original HF ESM formula; `layer_precision`/FP8/FP4 recipe validation in `NVEsmEncoder.__init__`/`get_autocast_context` is internally consistent; `padded_vocab_size` truncation and weight tying in `NVEsmForMaskedLM` are consistent with the embedding size.
- `collator.py`: traced `_pt_flatten_collate`, `_pt_pad_to_multiple_of` (including the mock-padding-segment's effect on `cu_seq_lens_q`/`max_length_q`), `_split_sample_by_num_tokens`, `TokenPackingDataset.__iter__`'s batch-splitting logic, and the THD/BSHD context-parallel sharding helpers (`_process_tensor_thd`/`_process_tensor_bshd`/`_split_batch_by_cp_rank`). These are intricate but I did not find a concrete defect I'm confident in; the zigzag CP zig-zag chunk indexing and the `remainder`-based `max_length_q` update after padding both check out against their invariants. (I'd treat this file as the highest-remaining-risk area given its complexity and lack of a runnable environment to verify against; a reviewer with a working PyTorch/TE environment should re-check the CP-sharding math with real tensors.)
- `export.py` (both packages), `metrics.py`: no logic defects; `metrics.py`'s module-level `Perplexity` singleton is a minor design smell (shared mutable state across calls) but not a defect per se, and the function itself even flags `# TODO (peter): Is this method even used?`.

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
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/state.py`
- For context only (not in review scope, read to understand call sites / expected behavior, not for defects): `models/amplify/tests/conftest.py`, `models/amplify/tests/test_amplify_model.py`, `models/amplify/tests/test_export.py`, `models/amplify/tests/test_encoder_block.py` (grep only), `models/esm2/tests/test_collator.py` (grep + excerpt), `models/esm2/esm_fast_tokenizer/` (directory listing only, data files not code)
