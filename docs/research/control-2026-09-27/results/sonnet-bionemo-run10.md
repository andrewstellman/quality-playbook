# Code Review: bionemo-recipes (models/amplify/src/amplify/, models/esm2/)

Repo: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
Pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
Scope: `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

## Defects found

### 1. `EncoderBlock.__init__` silently leaves `self.ffn` unset for any unrecognized `hidden_act`

- **File/line:** `models/amplify/src/amplify/amplify_hf.py:148-189`
- **What goes wrong:** The feedforward network is built with a `match` statement that only handles `"swiglu"`, `"relu"`, and `"gelu"` (case-insensitive):
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
  There is no `case _:` fallback. If `config.hidden_act` is any other string (a typo, or a value that's valid elsewhere but unsupported here, e.g. `"silu"`), the match falls through without raising and `self.ffn` is never assigned. The failure only surfaces later, in `_ff_block`, as `AttributeError: 'EncoderBlock' object has no attribute 'ffn'` — a confusing error far from the actual misconfiguration, with no message naming the invalid `hidden_act` value.
- **Why it is wrong:** `AMPLIFYConfig.hidden_act` is a free-form string with no enum/validation elsewhere in this file, so an invalid value is accepted at config-construction time and only blows up on first forward pass, with a misleading traceback. Contrast with the TE variant of this model (`amplify_te.py`), which passes `activation=config.hidden_act.lower()` straight into `transformer_engine.pytorch.TransformerLayer`, so an unsupported value gets a clear, immediate error from TE.
- **Severity:** Low (only affects misconfiguration/edge-case input, but the failure mode is confusing rather than a clean validation error).
- **Suggested fix:** Add a `case _: raise ValueError(f"Unsupported hidden_act: {config.hidden_act!r}")` (or validate `hidden_act` in `AMPLIFYConfig.__init__`, mirroring the `padded_vocab_size >= vocab_size` assertion already there).

### 2. Attention mask is hard-cast to `bfloat16` regardless of the model's actual dtype

- **File/line:** `models/amplify/src/amplify/amplify_hf.py:360-366`
- **What goes wrong:**
  ```python
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
  The additive mask is unconditionally cast to `torch.bfloat16`, independent of the model's parameter/activation dtype. This mask is then passed straight into `scaled_dot_product_attention`/`memory_efficient_attention` as `attn_mask`/`attn_bias` (`_att_block`, lines 255-270). Both APIs document/require the float attention-mask dtype to match the query/key/value dtype. If the model is run in its default fp32 (e.g. the CPU path at line 262-270, `scaled_dot_product_attention(..., attn_mask=attention_mask, ...)` with `query`/`key`/`value` still fp32), or fp16, the mask being forced to bf16 is a real dtype mismatch against the documented contract of these attention ops, unlike the rest of the model which respects whatever dtype the caller cast it to.
  Note that every existing test in `tests/test_amplify_model.py` casts the model to `torch.bfloat16` (or runs under a bf16 autocast) before calling forward, so this mismatch is not exercised by the current test suite — the CPU/non-bf16 code path this class explicitly supports (`if x.is_cuda: ... else: scaled_dot_product_attention(...)`) is untested here.
- **Why it is wrong:** The code has an explicit CPU fallback branch (the `else` of `if x.is_cuda:`) implying fp32/CPU inference is a supported configuration, but the attention-mask dtype is silently forced to bf16 in all cases, not derived from the model's configured dtype (there's no `config.dtype` plumbed into `AMPLIFY.__init__`/`nn.Embedding`/`nn.Linear` at all in this HF reference implementation — everything defaults to fp32 unless the caller calls `.to(dtype=...)` externally).
- **Severity:** Medium (silent, dtype-dependent defect; doesn't manifest for the bf16-only usage this repo's tests exercise, but breaks the model's own documented CPU/non-CUDA support path).
- **Suggested fix:** Cast the mask to the dtype of the hidden states/query being computed (e.g. `.to(x.dtype)`) rather than hardcoding `torch.bfloat16`.

## No other defects found with confidence

I reviewed the AMPLIFY TE model (`amplify_te.py`), rotary embeddings (`rotary.py`), RMSNorm (`rmsnorm.py`), the state-dict conversion utilities (`state_dict_convert.py`, `state.py`), metrics/export helpers, and the full ESM2 TE model (`modeling_esm_te.py`), the ESM2 `convert.py`/`state.py`/`export.py`, and the large custom data collator (`collator.py`, including the context-parallel/token-packing/flattening logic). These are mostly careful, deliberate ports of well-established reference implementations (the upstream AMPLIFY model, HF's ESM2, NeMo-style state-dict transform utilities), and I did not find defects I'm confident are real beyond the two above. Several things I specifically checked and ruled out as non-issues:

- `amplify_te.py`'s int64→bool attention-mask inversion (`~attention_mask.to(bool)`) is correct for the standard HF 1=valid/0=pad convention, and matches how the ESM2 collator always produces `attention_mask` as `dtype=torch.int64`.
- `amplify_hf.py`'s `layer_norm_before_last_layer=False` branch builds `self.decoder` with `config.vocab_size` (not `padded_vocab_size`) output features, which looked suspicious at first, but the subsequent `logits[:, :, :vocab_size]` slice in `forward()` is then a harmless no-op for that branch — not a bug.
- `models/esm2/state.py` is byte-for-byte identical to `models/amplify/src/amplify/state.py` (aside from the "copied file" notice), so there's no drift between the two copies the repo's `check_copied_files.py` is meant to guard against.
- The `NVEsmEmbeddings._apply_token_dropout_bshd`/`_apply_token_dropout_thd` division-by-zero risk when `mask_ratio_observed == 1` (an entire sequence consists of mask tokens) reproduces the original Facebook ESM2 token-dropout formula; not a defect introduced here.

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
- `models/esm2/modeling_esm_te.py`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/state.py`
- `models/esm2/export.py`

For context (not in review scope, read to understand intended behavior/usage):
- `models/amplify/tests/test_amplify_model.py`
- `models/amplify/tests/conftest.py`
