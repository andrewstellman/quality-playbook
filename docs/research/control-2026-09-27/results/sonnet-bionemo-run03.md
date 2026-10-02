# Code review: bionemo-recipes — AMPLIFY + ESM2

- Repo: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
- Pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
- Scope: `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

## Defect 1 — `_pad_weights` in AMPLIFY's HF→TE converter drops dtype/device, unlike the (correct) ESM2 sibling

**File/line:** `models/amplify/src/amplify/state_dict_convert.py:85-91`

```python
def _pad_weights(ctx: io.TransformCTX, source_embed):
    """Pad the embedding layer to the new input dimension."""
    target_embedding_dimension = ctx.target.config.padded_vocab_size
    hf_embedding_dimension = source_embed.size(0)
    num_padding_rows = target_embedding_dimension - hf_embedding_dimension
    padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))
    return torch.cat((source_embed, padding_rows), dim=0)
```

**What goes wrong:** `padding_rows` is created with `torch.zeros(...)` with no `dtype=` or `device=` argument, so it is always a CPU float32 tensor. `_pad_weights` is registered as the transform for both `encoder.weight` (embedding) and `decoder.weight` in `convert_amplify_hf_to_te` (lines 51-56/94-102). If the source HF model (`model_hf` argument to `convert_amplify_hf_to_te`, a general-purpose public function, not just the internal `export.py` caller which happens to load fp32-on-CPU weights) is on GPU and/or in a non-float32 dtype — e.g. bfloat16, which is exactly the dtype `export_hf_checkpoint`'s own smoke test loads models in (`export.py:108-112`, `dtype=torch.bfloat16`), and which is a completely normal thing to pass to a "convert this checkpoint" utility — `torch.cat((source_embed, padding_rows), dim=0)` will raise because the two operands have mismatched dtype and/or device (`torch.cat` does not perform type/device promotion the way arithmetic ops do).

**Why it is wrong:** This is a copy-pasted variant of the identical helper in `models/esm2/convert.py:238-246`, which is documented by the module docstring in `state.py` (shared by both models, "Do not modify this file directly") as adapting weights between model formats without altering their dtype (the shared `apply_transforms` even asserts afterwards that dtypes were not changed by the conversion — see `state.py:233-243`, the `target_orig_dtypes`/`target_new_dtypes` dtype-preservation check). The ESM2 version correctly preserves dtype/device:

```python
padding_rows = torch.zeros(
    num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device
)
```

The AMPLIFY version is missing exactly these two keyword arguments, so it silently breaks the "preserve dtype/device" contract that the sibling implementation (and the surrounding `apply_transforms` dtype check) both rely on/enforce.

**Severity:** Medium — it does not corrupt results (it fails loudly with a `RuntimeError` from `torch.cat`, or is masked to fp32-on-CPU only when the caller happens to load `model_hf` at default settings), but it makes `convert_amplify_hf_to_te` broken for GPU-resident or non-fp32 source checkpoints, a normal and supported use pattern (mirrored by the ESM2 sibling and by `export.py`'s own later use of `torch.bfloat16`).

**Suggested fix:**
```python
padding_rows = torch.zeros(
    num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device
)
```

---

## Defect 2 — `_apply_token_dropout_thd` slices the padded embeddings using the *unpadded* cumulative sequence lengths

**File/line:** `models/esm2/modeling_esm_te.py:719-745`, specifically line 741.

```python
def _apply_token_dropout_thd(self, embeddings, input_ids, kwargs):
    ...
    src_lengths = torch.diff(kwargs["cu_seq_lens_q"])
    if "cu_seq_lens_q_padded" in kwargs:
        src_lengths_padded = torch.diff(kwargs["cu_seq_lens_q_padded"])
    else:
        src_lengths_padded = src_lengths
    # We need to find the number of masked tokens in each sequence in the padded batch.
    is_masked = (input_ids == self.mask_token_id).squeeze(0)
    n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"]).sum(1)
    ...
    reshaped_scale_factor = torch.repeat_interleave(scale_factor, src_lengths_padded, dim=0)
    return (embeddings * reshaped_scale_factor.unsqueeze(-1)).to(embeddings.dtype)
```

**What goes wrong:** When context-parallel per-sequence padding is used (`models/esm2/collator.py`'s `DataCollatorWithFlattening._pad_sequences_to_be_divisible_by`, lines 204-227), the collator replaces `batch["input_ids"]` with the *physically padded* tensor (via `pad_thd_sequences_for_cp`) and adds `batch["cu_seq_lens_q_padded"]`/`cu_seq_lens_k_padded` (the boundaries matching that padded tensor) while leaving the original `batch["cu_seq_lens_q"]` (the unpadded boundaries) untouched in the same dict. Both keys therefore coexist in `kwargs` and `input_ids` is padded. In `_apply_token_dropout_thd`, `is_masked` is computed from this padded `input_ids` (so its length equals `cu_seq_lens_q_padded[-1]`), but it is then handed to `torch.nested.nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"])` — i.e., split using the *unpadded* boundaries, whose final offset (`cu_seq_lens_q[-1]`) is smaller than `is_masked`'s actual length. `nested_tensor_from_jagged` requires `offsets[-1] == values.shape[0]`, so this call is inconsistent whenever `pad_sequences_to_be_divisible_by`/context-parallel packing is combined with token dropout (`config.token_dropout=True`, the ESM-2 default) — it will either error or mis-partition tokens across sequence boundaries.

**Why it is wrong:** The function's own comment at line 739 says "We need to find the number of masked tokens in each sequence *in the padded batch*" — i.e., the author's intent was clearly to operate on the padded layout — and two lines earlier the function already special-cases `cu_seq_lens_q_padded` for `src_lengths_padded` precisely because the padded and unpadded boundaries can differ. Line 741 is the one place that was not updated to use the padded offsets when they're available, contradicting both the comment and the parallel handling done for `src_lengths_padded` just above it.

**Severity:** High — this is a crash/data-corruption bug in a code path (THD packing + per-sequence CP padding + token dropout) that the collator explicitly supports and that is the default configuration for ESM-2 models (`token_dropout=True`).

**Suggested fix:**
```python
offsets = kwargs["cu_seq_lens_q_padded"] if "cu_seq_lens_q_padded" in kwargs else kwargs["cu_seq_lens_q"]
n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=offsets).sum(1)
```

---

## Defect 3 — `EncoderBlock.__init__`'s activation `match` has no default/error case

**File/line:** `models/amplify/src/amplify/amplify_hf.py:148-189`

```python
match config.hidden_act.lower():
    case "swiglu":
        ...
        self.ffn = SwiGLU(...)
    case "relu":
        self.ffn = nn.Sequential(...)
    case "gelu":
        self.ffn = nn.Sequential(...)
```

**What goes wrong:** If `config.hidden_act` (a plain, unvalidated `str` field on `AMPLIFYConfig`, see `amplify_hf.py:57,79`) is any value other than `"swiglu"`, `"relu"`, or `"gelu"` (case-insensitive) — e.g. a typo such as `"gelu_new"`, or any other HF-style activation name — none of the `case` branches match, there is no `case _:` fallback, and `self.ffn` is never assigned. `EncoderBlock` otherwise finishes constructing normally (norms, dropouts are still set), so the failure is deferred to the first call to `self._ff_block`/`self.ffn(x)` in `forward`, which raises a generic `AttributeError: 'EncoderBlock' object has no attribute 'ffn'` with no indication that the real cause was an unsupported `hidden_act` value.

**Why it is wrong:** The docstring for `hidden_act` (`amplify_hf.py:79`, "hidden_act (str): The activation function of the model.") gives no indication that only three specific strings are accepted, and nothing validates the value at config-construction time the way, e.g., `NVEsmConfig.__init__` validates `layer_precision` (`modeling_esm_te.py:153-158`, raising a `ValueError` with an explicit message for an unsupported value). The AMPLIFY HF path silently leaves the model half-constructed instead of failing fast with a clear error.

**Severity:** Low — the model still fails (it doesn't produce silently-wrong numerical results), but with a confusing, deferred `AttributeError` instead of an immediate, actionable error message.

**Suggested fix:** Add an explicit `case _:` branch that raises, e.g.:
```python
case _:
    raise ValueError(f"Unsupported hidden_act: {config.hidden_act!r}")
```

---

## Notes on things considered but not reported

- `AMPLIFY.forward`'s attention-mask handling in `amplify_hf.py` (skipping mask construction only when the *entire* mask tensor is all-zero, `amplify_hf.py:360`) and `AMPLIFYForMaskedLM.forward`'s attention-mask dtype check (`amplify_te.py:245`, only inverts the mask when `dtype is torch.int64`) both looked potentially fragile, but the first is vendored 1:1 from the upstream `chandar-lab/AMPLIFY` reference implementation (see file header) and the second matches the dtype that both `DataCollatorForLanguageModeling` and this repo's own `esm2/collator.py` produce for `attention_mask` (`torch.int64`, e.g. `collator.py:722-724`). I could not find a call path in-scope where a different dtype/shape would actually reach it, so I'm not confident enough to report either as a real defect.
- `DataCollatorForContextParallel.__call__` (`collator.py:396-457`) computes `max_length_q`/`max_length_k` from the *pre-CP-split* `cu_seq_lens_q_padded` (line 433) rather than the per-rank sharded lengths. This looks like it overestimates rather than underestimates the true post-split max length, which would be safe for buffer sizing rather than incorrect, so I did not report it as a confirmed defect.

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
- (for context, not in review scope) `models/amplify/tests/test_amplify_model.py`, `models/amplify/tests/test_encoder_block.py`, `models/amplify/tests/conftest.py`, `recipes/esm2_accelerate_te/tests/test_accelerate_amplify.py`, directory listings of `models/amplify/` and repo root.
