# Code Review: bionemo-recipes — AMPLIFY + ESM2 models

Repo: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
Pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
Scope: `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

## Defect 1 — `_pad_weights` in AMPLIFY's HF→TE converter ignores source tensor's dtype/device, unlike the identical helper in ESM2's converter

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

**What goes wrong:** `padding_rows` is created with `torch.zeros(num_padding_rows, source_embed.size(1))`, which uses the default dtype (`float32`) and default device (`cpu`). If `source_embed` (the HF checkpoint's embedding or decoder weight) is not `float32` on `cpu` — e.g. a checkpoint loaded as `bfloat16`, or converted on GPU — the subsequent `torch.cat((source_embed, padding_rows), dim=0)` will raise, because `torch.cat` requires all inputs to share dtype and device.

**Why it's wrong:** This function is applied (via `io.state_transform`, see `_pad_embeddings`/`_pad_decoder_weights` at lines 94-102) to both the `encoder.weight` embedding and the `decoder.weight` in `convert_amplify_hf_to_te`, which is a public conversion entry point (also called from `export.py`). The sibling helper doing exactly the same job for ESM2 — `_pad_weights` in `models/esm2/convert.py:238-246` — explicitly threads through `dtype=source_embed.dtype, device=source_embed.device`:

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

Additionally, within the same AMPLIFY file, `_pad_bias` (lines 105-117) already gets this right for the bias tensor (`torch.ones(..., dtype=source_bias.dtype, device=source_bias.device)`). So the codebase clearly knows the correct pattern and applies it consistently everywhere except this one function — `_pad_weights` is the outlier, strongly indicating an oversight rather than an intentional difference.

**Severity:** medium. The current `export_hf_checkpoint()` call site happens to load the HF model via plain `AutoModel.from_pretrained(...)` (CPU, default `float32`), so the bug doesn't trigger in that one path today. But `convert_amplify_hf_to_te` is a general-purpose conversion function, and it will raise a `RuntimeError` (dtype/device mismatch in `torch.cat`) as soon as it's invoked on a model that isn't `float32`-on-CPU (e.g. a GPU-resident model, or one loaded in `bfloat16`/`float16`).

**Suggested fix:**
```python
padding_rows = torch.zeros(
    num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device
)
```
(mirroring `models/esm2/convert.py`'s `_pad_weights`, or better, de-duplicating the two identical converters into a shared helper as the `# TODO (peter): ... maybe we can abstract` comment in `models/esm2/convert.py:62` already suggests).

---

## Defect 2 (lower confidence) — THD token-dropout scaling uses unpadded `cu_seq_lens_q` offsets to slice a physically-padded tensor

**File/line:** `models/esm2/modeling_esm_te.py:719-745`, specifically line 741

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
    mask_ratio_observed = n_masked_per_seq.float() / src_lengths
    scale_factor = (1 - mask_ratio_train) / (1 - mask_ratio_observed)
    reshaped_scale_factor = torch.repeat_interleave(scale_factor, src_lengths_padded, dim=0)
    return (embeddings * reshaped_scale_factor.unsqueeze(-1)).to(embeddings.dtype)
```

**What goes wrong:** `is_masked` is built from `input_ids`, which is the physical (potentially inter-sequence-padded) tensor that the collator produces when `pad_sequences_to_be_divisible_by` is set — see `models/esm2/collator.py:204-227` (`_pad_sequences_to_be_divisible_by`), which calls `pad_thd_sequences_for_cp` and sets `batch["pad_between_seqs"] = True` together with a distinct `cu_seq_lens_q_padded`. When that path is used, `cu_seq_lens_q` (the *unpadded* cumulative lengths) no longer describes offsets into the physical `input_ids`/`is_masked` buffer — only `cu_seq_lens_q_padded` does. The code is aware of this distinction one line above (it computes `src_lengths_padded` from `cu_seq_lens_q_padded` precisely because the physical layout differs from the logical one), but the `nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"])` call still slices the physical `is_masked` buffer with the *unpadded* offsets.

**Why it's wrong:** The comment on the line above ("We need to find the number of masked tokens in each sequence in the padded batch") states the intent is to count masked tokens per sequence *in the padded batch*, which requires offsets into the padded buffer (`cu_seq_lens_q_padded`), not `cu_seq_lens_q`. With inter-sequence padding present, `cu_seq_lens_q`'s boundaries fall at the wrong physical positions, so each per-sequence slice pulled out of `is_masked` will include a fragment of the following sequence's tokens (or of the padding) instead of the real sequence's full token range, and the resulting `n_masked_per_seq` / `mask_ratio_observed` / `scale_factor` will be computed on the wrong token spans, then broadcast onto embeddings via `repeat_interleave(..., src_lengths_padded, ...)`, silently mis-scaling some sequences' embeddings whenever `pad_sequences_to_be_divisible_by` (context-parallel padding) is combined with `token_dropout=True`.

**Severity:** medium — this only manifests for THD/packed-sequence + context-parallel training (`pad_sequences_to_be_divisible_by` set) on a config with `token_dropout=True` (true for the real ESM-2 checkpoints), and its effect is a silent numerical error (wrong embedding scaling) rather than a crash, so it would be easy to miss in testing.

**Suggested fix:** Use the padded offsets consistently when they're available:
```python
seq_offsets = kwargs.get("cu_seq_lens_q_padded", kwargs["cu_seq_lens_q"])
n_masked_per_seq = torch.nested.nested_tensor_from_jagged(is_masked, offsets=seq_offsets).sum(1)
```
(and correspondingly reconsider whether `mask_ratio_observed = n_masked_per_seq / src_lengths` should divide by the padded or unpadded length, depending on whether pad tokens should count toward the ratio).

---

## Other things checked, not flagged as defects

- `models/amplify/src/amplify/rotary.py`, `rmsnorm.py`, `amplify_hf.py`: closely mirror the upstream chandar-lab AMPLIFY reference implementation; nothing found that contradicts their own docstrings.
- `models/amplify/src/amplify/amplify_te.py`: `AMPLIFYForMaskedLM.forward`'s vocab-padding truncation (`logits[:, :, :vocab_size]`) is a no-op but harmless when `layer_norm_before_last_layer=False` (decoder already emits `vocab_size`-width logits in that branch).
- `models/amplify/src/amplify/state.py` and `models/esm2/state.py` are byte-identical except for the "copied file" notice comment, consistent with the file's own header instructing that `esm2/state.py` is the source of truth.
- `models/esm2/collator.py`: reviewed `TokenPackingDataset.__iter__`'s batch-splitting/padding arithmetic, `_split_batch_by_cp_rank`/`_process_tensor_thd`/`_process_tensor_bshd` zigzag CP sharding, and `_pt_pad_to_multiple_of`; the arithmetic checked out under the documented invariants (e.g. `pad_sequences_to_be_divisible_by` dividing evenly into `2 * cp_world_size` shard counts is a documented precondition, not silently violated by this code).
- `models/esm2/modeling_esm_te.py`: `NVEsmModel.forward`'s attention-mask construction (`AttentionMaskConverter(...).to_4d(..., query_length=1, ...)` then `< -1`) is consistent with a padding-only (non-causal) mask.
- Did not find a way to exercise any of this against real PyTorch/TransformerEngine execution — no PyTorch or `transformer_engine` available in this sandbox, so all analysis here is static/code-reading only.

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
- `models/esm2/state.py` (diffed against `models/amplify/src/amplify/state.py`; identical apart from a header comment)
