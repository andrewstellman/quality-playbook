# Code review: bionemo-recipes — `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

Repo: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
Pinned commit: `11701476b005ca7bc489df924a398b8f12453f0b`

## Defect 1 — `_pad_weights` in AMPLIFY's conversion util omits dtype/device, unlike the sibling ESM2 implementation

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

**What goes wrong:** `torch.zeros(num_padding_rows, source_embed.size(1))` is created with the default dtype (float32) and default device (CPU), regardless of `source_embed`'s actual dtype/device. `torch.cat` requires matching dtypes, so this raises `RuntimeError: Expected all tensors to be on the same device` or a dtype-mismatch error from `torch.cat` whenever `source_embed` is not a float32 CPU tensor — e.g. when the source Hugging Face model is loaded with `dtype=torch.bfloat16`/`torch.float16`, or already moved to `cuda` before conversion. `_pad_weights` is registered as the transform for both `encoder.weight` (embedding) and `decoder.weight` in `convert_amplify_hf_to_te` (lines 51–56, 94–102), so it runs on every AMPLIFY HF→TE conversion whenever `padded_vocab_size != vocab_size` (the default: 32 vs 27).

**Why it is wrong:** The essentially identical function in the parallel ESM2 module, `models/esm2/convert.py`, lines 238–246, explicitly propagates dtype and device:

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

Both functions carry the same docstring and exist to do the same job (pad an embedding/decoder matrix's vocab dimension). The AMPLIFY copy is missing the `dtype=`/`device=` arguments that the ESM2 copy has, so it will crash on any source tensor that isn't already float32-on-CPU. The current call path in `amplify/src/amplify/export.py` happens to load the HF model via `AutoModel.from_pretrained(..., trust_remote_code=True)` with no explicit `dtype=`, which defaults to float32 on CPU — this coincidentally avoids triggering the bug today, but it's a latent break for any bf16/fp16/GPU conversion.

**Severity:** Medium (silent-until-triggered `RuntimeError`; masked by the current default call site's fp32/CPU loading, but this project's own tests and other tooling routinely operate the AMPLIFY model in bf16, so any caller that pre-converts the source model's dtype/device before calling `convert_amplify_hf_to_te` will hit this).

**Suggested fix:** Mirror the ESM2 version:

```python
padding_rows = torch.zeros(
    num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device
)
```

---

## Defect 2 — `AMPLIFY.forward` (xformers/HF path) hardcodes the attention-mask dtype to bfloat16

**File:** `models/amplify/src/amplify/amplify_hf.py`, lines 359–368

```python
# Expand and repeat: (Batch, Length) -> (Batch, Heads, Length, Length)
if attention_mask is not None and not torch.all(attention_mask == 0):
    attention_mask = torch.where(attention_mask == 1, float(0.0), float("-inf")).to(torch.bfloat16)
    attention_mask = (
        attention_mask.unsqueeze(1)
        .unsqueeze(1)
        .repeat(1, self.config.num_attention_heads, attention_mask.size(-1), 1)
    )
else:
    attention_mask = None
```

**What goes wrong:** The additive attention mask is unconditionally cast `.to(torch.bfloat16)`, independent of the model's actual compute dtype. `AMPLIFYConfig` has no fixed dtype of its own (the config carries no `dtype` default, unlike the TE config path); the model's weights take whatever dtype the caller constructs/moves them to. If the model is used in float32 (e.g., `AMPLIFY(config)` with no explicit `.to(..., dtype=...)`, which is the state after plain construction/`post_init()`) or float16, the query/key/value tensors passed into `scaled_dot_product_attention`/`memory_efficient_attention` are float32/float16 while `attn_bias`/`attn_mask` is bfloat16 — a dtype mismatch that these attention kernels are not guaranteed to silently reconcile.

**Why it is wrong:** Compare with the TE model in `amplify_te.py` (lines 244–247), which builds a **boolean** mask with no coupling to compute dtype:
```python
if attention_mask is not None and attention_mask.dtype is torch.int64:
    # TE expects a boolean attention mask, where "True" indicates a token to be masked.
    attention_mask = ~attention_mask.to(bool)
```
The HF/xformers path in `amplify_hf.py` has no such dtype-agnostic design and instead bakes in an assumption that the model always runs in bf16.

**Severity:** Low (in this repo's actual usage — its own tests always run the HF AMPLIFY model in bf16 via `torch.amp.autocast(dtype=torch.bfloat16)` and/or `.to("cuda", dtype=torch.bfloat16)` — so the mismatch is not currently exercised. Flagging because the class is publicly reusable and nothing in the code or docstring documents a bf16-only constraint.)

**Suggested fix:** Cast the mask to the same dtype as the hidden states (e.g. `.to(x.dtype)` or the query tensor's dtype) instead of a hardcoded `torch.bfloat16`.

---

## Lower-confidence observation (not reported as a defect)

`models/amplify/src/amplify/amplify_te.py`, line 245: `if attention_mask is not None and attention_mask.dtype is torch.int64:` uses an exact-dtype identity check (`is torch.int64`) to decide whether to invert a raw 0/1 padding mask into TE's expected "True = masked" boolean mask. If a caller ever passes an `attention_mask` that is already a different integer dtype (e.g. `torch.int32`) but still uses the "1 = valid token" HF convention, this branch is skipped and the raw 0/1 values are passed straight through with inverted semantics (0 would then mean "not masked" to TE, the opposite of "1 = valid"). I could not find any call site inside the reviewed scope that supplies a non-int64, non-bool mask, so I'm not confident this is actually reachable in practice — noting it rather than reporting it as a confirmed defect.

---

## Files read

- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/state.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/export.py`
- `models/amplify/tests/test_amplify_model.py` (context only — to confirm real call-site dtype/usage patterns; not in review scope)
- `models/amplify/tests/conftest.py` (context only, not in review scope)
- `models/amplify/tests/test_encoder_block.py` (context only, not in review scope; grepped)
- `models/esm2/state.py`
- `models/esm2/convert.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/collator.py`
- `models/esm2/export.py`

No other defects I'm confident are real were found in the scoped paths. Several areas of the context-parallel sharding logic in `models/esm2/collator.py` (`_process_tensor_thd`, `_process_tensor_bshd`, `_split_batch_by_cp_rank`) and the FP8/FP4 per-layer autocast plumbing in `models/esm2/modeling_esm_te.py` (`NVEsmEncoder.get_autocast_context`) are intricate enough that I could not verify their numeric correctness without executing them (no PyTorch/CUDA available in this environment), so I did not flag anything there absent a concrete contradiction with the code's own documentation.
