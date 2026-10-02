# Code Review: bionemo-recipes — `models/amplify/src/amplify/`, `models/esm2/` (excl. tests)

Repo: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
Pinned commit: `11701476b005ca7bc489df924a398b8f12453f0b`

## Defect 1 (High): missing `dtype`/`device` on padding tensor in AMPLIFY's HF→TE state-dict conversion

**File/line:** `models/amplify/src/amplify/state_dict_convert.py`, lines 85–91

```python
def _pad_weights(ctx: io.TransformCTX, source_embed):
    """Pad the embedding layer to the new input dimension."""
    target_embedding_dimension = ctx.target.config.padded_vocab_size
    hf_embedding_dimension = source_embed.size(0)
    num_padding_rows = target_embedding_dimension - hf_embedding_dimension
    padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))
    return torch.cat((source_embed, padding_rows), dim=0)
```

This function is used for both `_pad_embeddings` (`encoder.weight`) and `_pad_decoder_weights` (`decoder.weight`) in `convert_amplify_hf_to_te` (same file, lines 94–102). `torch.zeros(num_padding_rows, source_embed.size(1))` is created with the default dtype (`float32`) and default device (`cpu`), regardless of `source_embed`'s actual dtype/device.

**What goes wrong:** `torch.cat((source_embed, padding_rows), dim=0)` requires matching dtype and device between the two tensors it concatenates.
- If `source_embed` is anything other than float32 (e.g. the source HF checkpoint or `config_kwargs` requests bf16/fp16, which is exactly the scenario `padded_vocab_size` exists for — "to support fp8", per the config docstring at `amplify_te.py:81`), the `torch.cat` either raises a dtype error or silently produces a `float32` result. If it silently succeeds (PyTorch does allow this in some versions via implicit promotion in newer releases, but `apply_transforms` in `state.py` lines 233–243 asserts `target_orig_dtypes[key] == target_new_dtypes[key]` when `cast_dtype` is not passed), the conversion aborts with `AssertionError: dtype mismatch for key ...`.
- If `source_embed` lives on a CUDA device (e.g. the HF model was loaded with `device_map="cuda"` or moved to GPU before conversion — a normal thing to do before an export/conversion step), `torch.cat` raises `RuntimeError: Expected all tensors to be on the same device`.

**Why it is wrong:** The sibling, actively-maintained implementation of the exact same operation in `models/esm2/convert.py` (lines 238–246) gets this right:

```python
def _pad_weights(ctx: state.TransformCTX, source_embed):
    """Pad the embedding layer to the new input dimension."""
    target_embedding_dimension = ctx.target.config.padded_vocab_size
    hf_embedding_dimension = source_embed.size(0)
    num_padding_rows = target_embedding_dimension - hf_embedding_dimension
    padding_rows = torch.zeros(
        num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device
    )
    return torch.cat((source_embed, padding_rows), dim=0)
```

This is the same function, doing the same job (padding an embedding/decoder weight matrix from `vocab_size` rows to `padded_vocab_size` rows as part of an HF→TE conversion), and it correctly propagates `dtype`/`device` from the source tensor. The AMPLIFY copy dropped those two keyword arguments. Given the shared `state.py`'s own `apply_transforms` (used identically by both models) explicitly checks for dtype drift after conversion, the intended contract is clearly that transform functions must preserve dtype/device — `_pad_weights` in AMPLIFY violates that contract.

This is not a purely theoretical path: `export_hf_checkpoint` in `models/amplify/src/amplify/export.py` (line 60) calls `convert_amplify_hf_to_te(model_hf)` with no `config_kwargs`, which means `AMPLIFYConfig`'s default `padded_vocab_size=32` (vs. default `vocab_size=27`) is used, so `_pad_weights` always has real padding rows to add on the standard export path — it is not a no-op. Whether it happens to succeed today depends entirely on the source checkpoint's dtype/device matching the CPU-float32 default, which is incidental, not guaranteed, and breaks as soon as `config_kwargs` (e.g., `dtype=torch.bfloat16`, mirroring how the ESM2 export path already passes `config_kwargs` such as `padded_vocab_size=None`) or a GPU-resident source model is used.

**Severity:** High — this is a correctness/robustness bug in the conversion utility that is the sole path from published AMPLIFY HF checkpoints to the TE/fp8-capable format this repo exists to produce. It will crash (or, on some PyTorch versions/tensor combos, silently corrupt dtype) whenever the source tensor isn't float32-on-CPU.

**Suggested fix:**
```python
padding_rows = torch.zeros(
    num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device
)
```
(i.e., match the already-correct `models/esm2/convert.py` implementation.)

---

## Defect 2 (Medium): `state_dict_convert.py` unconditionally pads the decoder even when the model doesn't use a padded decoder

**File/line:** `models/amplify/src/amplify/amplify_te.py` lines 286–301, vs. `models/amplify/src/amplify/state_dict_convert.py` lines 37–60, 99–102, 105–117

`AMPLIFYForMaskedLM.__init__` builds the decoder differently depending on `config.layer_norm_before_last_layer`:

```python
if config.layer_norm_before_last_layer:
    self.decoder = transformer_engine.pytorch.LayerNormLinear(
        config.hidden_size, config.padded_vocab_size, ...
    )
else:
    self.decoder = transformer_engine.pytorch.Linear(
        config.hidden_size, config.vocab_size, params_dtype=config.dtype
    )
```

Only the `True` branch (the default, per `AMPLIFYConfig.layer_norm_before_last_layer: bool = True` in `amplify_te.py:56`) produces a decoder sized to `padded_vocab_size`. The `False` branch produces a decoder sized to the unpadded `vocab_size`.

However, `convert_amplify_hf_to_te` (`state_dict_convert.py:37-60`) always registers `_pad_decoder_weights` and `_pad_bias`, both of which unconditionally pad to `ctx.target.config.padded_vocab_size` (lines 87 and 111) with no check of `layer_norm_before_last_layer`. If a caller passes `config_kwargs={"layer_norm_before_last_layer": False}` (a documented, supported config flag) together with a `padded_vocab_size` that differs from `vocab_size`, the transform produces a `(padded_vocab_size, hidden_size)` tensor for `decoder.weight`/`decoder.bias`, but the actual target parameter is shaped `(vocab_size, hidden_size)`. `apply_transforms` in `state.py` (lines 173-181) explicitly checks for this and raises `ValueError: Shape mismatch for parameter decoder.weight: target shape ... vs converted source shape ...`.

**Severity:** Medium — it fails loudly rather than silently corrupting data, and only affects a non-default configuration combination, but it is a real defect: the conversion code does not account for a configuration branch that legitimately exists in the model it converts.

**Suggested fix:** In `convert_amplify_hf_to_te`, branch the padding transforms on `te_config.layer_norm_before_last_layer` (only register `_pad_decoder_weights`/`_pad_bias` when it's `True`; use a plain rename/no-op copy of `decoder.weight`/`decoder.bias` otherwise).

---

## Other areas reviewed, no confident defects found

- `models/amplify/src/amplify/amplify_hf.py`, `rmsnorm.py`, `rotary.py`: vendored/adapted from the upstream `chandar-lab/AMPLIFY_120M` HF repo, unmodified in substance. The attention-mask handling in `AMPLIFY.forward` (`amplify_hf.py:360-368`, skip masking entirely when the whole mask is zero) looks unusual but matches upstream and only affects a degenerate all-padding input.
- `models/amplify/src/amplify/state.py` and `models/esm2/state.py`: byte-for-byte identical except for the "copied file" notice comment in the AMPLIFY copy, confirmed with `diff`. The generic `apply_transforms`/`StateDictTransform` machinery looks correct for the paths exercised by both models' `mapping`s.
- `models/esm2/modeling_esm_te.py`: `NVEsmConfig`, `NVEsmEncoder`, `NVEsmModel`, `NVEsmForMaskedLM`, `NVEsmLMHead`, `NVEsmEmbeddings`, `NVEsmForTokenClassification` — checked the FP8/FP4 recipe validation logic, the padded-vocab truncation logic (`padded_vocab_size != vocab_size` before slicing, consistent everywhere it's used), the THD/BSHD attention-mask conversion (`extended_attention_mask < -1`, consistent with `AttentionMaskConverter`'s dtype-min-for-masked convention), and the token-dropout scaling math (`_apply_token_dropout_bshd` matches upstream HF ESM's formula exactly). No confirmed defect found, though `_apply_token_dropout_thd`'s use of un-padded `cu_seq_lens_q` offsets against a potentially padded `input_ids` buffer when `cu_seq_lens_q_padded` differs from `cu_seq_lens_q` looked worth a second look; I could not build a confident case either way without being able to exercise it (no PyTorch/transformer_engine available in this environment), so I'm not reporting it as a defect.
- `models/esm2/collator.py`: reviewed `DataCollatorWithFlattening`, `TokenPackingDataset`, `DataCollatorForContextParallel`, and the CP-sharding helpers (`_process_tensor_thd`, `_process_tensor_bshd`, `_split_batch_by_cp_rank`, `_pt_pad_to_multiple_of`, `_pt_flatten_collate`, `_split_sample_by_num_tokens`). Arithmetic (cumulative sequence lengths, zigzag CP chunk indexing, padding-remainder computation) checked out algebraically against the docstrings' worked examples. No confirmed defect found.
- `models/esm2/export.py`, `models/amplify/src/amplify/export.py`, `models/amplify/src/amplify/metrics.py`: no defects found.

## Notes on verification

No PyTorch, CUDA, or `transformer_engine` were available in the review environment (per the task's constraints), so none of the above could be exercised by running the actual conversion/model code. Defect 1 and Defect 2 were confirmed by static reading plus a direct side-by-side comparison against the corresponding, correct implementation in `models/esm2/convert.py`, and by tracing the exact `torch.cat`/shape-check code paths that would be hit.

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
- `models/esm2/state.py` (diffed against the AMPLIFY copy)
- `models/esm2/convert.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/collator.py`
- `models/esm2/export.py`
