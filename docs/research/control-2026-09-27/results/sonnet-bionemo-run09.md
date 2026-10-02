# Code Review: bionemo-recipes — AMPLIFY and ESM2 models

Repo: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
Pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
Scope: `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

## Defect 1: AMPLIFY HF→TE weight-padding helper creates zero-padding on the wrong dtype/device

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

This function is used (via `io.state_transform`) both for `_pad_embeddings` (`encoder.weight`) and `_pad_decoder_weights` (`decoder.weight`) inside `convert_amplify_hf_to_te` (lines 51–56). `padding_rows` is created with `torch.zeros(num_padding_rows, source_embed.size(1))`, which defaults to `dtype=torch.float32` on the CPU, regardless of `source_embed`'s actual dtype/device. `torch.cat` requires all inputs to share dtype and device, so if `source_embed` is anything other than float32-on-CPU (e.g. a checkpoint loaded in bf16/fp16, or already moved to a CUDA device — both routine when converting real checkpoints, especially larger ones), `torch.cat((source_embed, padding_rows), dim=0)` raises a `RuntimeError` (dtype/device mismatch), and the conversion fails.

This is not a hypothetical inconsistency: the equivalent helper in the ESM2 conversion code, `models/esm2/convert.py` lines 238–246, does it correctly:

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

The AMPLIFY version is missing the `dtype=source_embed.dtype, device=source_embed.device` arguments that the near-identical ESM2 version has, which is why the sibling `_pad_bias` in the same AMPLIFY file (lines 109–117) correctly sets `dtype=source_bias.dtype, device=source_bias.device` on its `torch.ones(...)` call but `_pad_weights` in the same file does not. This is an inconsistent omission, not an intentional design choice.

- **Severity:** Medium (correctness bug that only manifests under valid, common usage — converting a non-default-dtype or GPU-resident checkpoint — silent success on the default CPU/float32 path masks it).
- **Fix:** Add `dtype=source_embed.dtype, device=source_embed.device` to the `torch.zeros(...)` call, matching `models/esm2/convert.py`'s `_pad_weights`.

## Defect 2: AMPLIFY TE decoder ignores `padded_vocab_size` when `layer_norm_before_last_layer=False`

**File:** `models/amplify/src/amplify/amplify_te.py`, lines 286–301

```python
if config.layer_norm_before_last_layer:
    self.decoder = transformer_engine.pytorch.LayerNormLinear(
        config.hidden_size,
        config.padded_vocab_size,
        ...
    )
else:
    self.decoder = transformer_engine.pytorch.Linear(
        config.hidden_size, config.vocab_size, params_dtype=config.dtype
    )
```

`AMPLIFYConfig.padded_vocab_size` is documented as "The padded vocabulary size of the model to support fp8" (docstring, lines 80–81), and `padded_vocab_size >= vocab_size` is asserted at config construction (lines 109–111). Everywhere else in the model (the input embedding at lines 146–151, and the `LayerNormLinear` branch of the decoder itself) is sized with `padded_vocab_size`. But when `layer_norm_before_last_layer=False`, the decoder `Linear` layer is sized with plain `vocab_size`, not `padded_vocab_size`. This:

1. Defeats the documented purpose of `padded_vocab_size` (fp8-alignment) for this code path.
2. Breaks `state_dict_convert.py`'s `_pad_decoder_weights`/`_pad_bias` transforms when converting into a TE model configured this way: those transforms compute a padded tensor of shape `(padded_vocab_size, hidden_size)` (`state_dict_convert.py` lines 85–91, 109–117) to assign into `decoder.weight`/`decoder.bias`, but the actual target module's parameter only has shape `(vocab_size, hidden_size)`/`(vocab_size,)`. `state.py`'s `apply_transforms` explicitly checks for this and raises `ValueError: Shape mismatch for parameter decoder.weight ...` (`state.py` lines 176–181).

This path isn't hit by the default config (`layer_norm_before_last_layer=True`), so it won't reproduce with the stock AMPLIFY_120M/350M checkpoints, but `layer_norm_before_last_layer` is a documented, user-settable config flag, and setting it to `False` on a TE model with `padded_vocab_size != vocab_size` (the config default is `padded_vocab_size=32, vocab_size=27`) will crash weight conversion or silently drop the fp8 padding guarantee.

- **Severity:** Medium (latent; only triggered by a non-default but supported config option).
- **Fix:** Use `config.padded_vocab_size` in the `else` branch's `Linear` construction as well (and truncate to `vocab_size` in `forward`, which the code already does at lines 345–346).

## Defect 3: `DataCollatorForContextParallel` computes `max_length` from the un-sharded batch in BSHD mode

**File:** `models/esm2/collator.py`, lines ~430–442 (inside `DataCollatorForContextParallel.__call__`)

```python
for cp_rank in range(self.cp_world_size):
    input_ids_sharded, labels_sharded = _split_batch_by_cp_rank(
        cu_seqlens_padded=batch.get("cu_seq_lens_q_padded", None),
        input_ids_padded=batch["input_ids"],
        labels_padded=batch["labels"],
        qvk_format=self.qkv_format,
        cp_rank=cp_rank,
        cp_world_size=self.cp_world_size,
    )
    batch_shard = dict(batch)
    batch_shard["input_ids"] = input_ids_sharded
    ...
    # Now determine the max length of the sequence.
    if self.qkv_format == "thd":
        seqlens_q = batch_shard["cu_seq_lens_q_padded"][1:] - batch_shard["cu_seq_lens_q_padded"][:-1]
        max_length = seqlens_q.max().item()
    elif self.qkv_format == "bshd":
        max_length = batch["input_ids"].shape[1]
    else:
        raise ValueError(f"Unsupported qvk_format: {self.qkv_format}!")

    batch_shard["max_length_k"] = batch_shard["max_length_q"] = ((max_length + 63) // 64) * 64
```

For `qkv_format == "bshd"` with `cp_world_size > 1`, `_process_tensor_bshd` (`collator.py` lines 252–309) splits the sequence dimension into `2 * cp_world_size` chunks and gives each rank 2 chunks — i.e. `input_ids_sharded` (assigned into `batch_shard["input_ids"]` immediately above) has a sequence length of `seq_len / cp_world_size`, strictly smaller than the original `batch["input_ids"]`. But the `max_length` computed for this shard reads `batch["input_ids"].shape[1]` — the pre-split, full-length tensor — instead of `batch_shard["input_ids"].shape[1]` (or equivalently the length of `input_ids_sharded`). Every CP rank therefore reports a `max_length_q`/`max_length_k` describing the *global* unsharded sequence length even though it only holds `1/cp_world_size` of the tokens.

By contrast, the `thd` branch two lines above correctly derives its length from the per-shard value (`batch_shard["cu_seq_lens_q_padded"]`), which highlights that the `bshd` branch's reference to `batch` (rather than `batch_shard`) is inconsistent with the surrounding code's own convention, and is not computing what its own comment ("Now determine the max length of the sequence [for this shard]") describes.

Since `max_length_q`/`max_length_k` are forwarded as `max_seqlen_q`/`max_seqlen_kv` into `transformer_engine.pytorch.TransformerLayer` (see `modeling_esm_te.py` lines 278–290), supplying a value roughly `cp_world_size` times larger than the actual local tensor's sequence length can cause incorrect kernel selection/buffer sizing in TE's attention path when BSHD + context parallelism are combined.

- **Severity:** Medium (only affects the `qkv_format == "bshd"` + `cp_world_size > 1` combination; `thd` is unaffected).
- **Fix:** Use `batch_shard["input_ids"].shape[1]` (or `input_ids_sharded.shape[1]`) instead of `batch["input_ids"].shape[1]` on line ~438.

## Lower-confidence observation (not reported as a defect)

`models/amplify/src/amplify/amplify_hf.py`, line 360: `if attention_mask is not None and not torch.all(attention_mask == 0):` causes the code to treat a fully-zero attention mask (every position padding) as `attention_mask = None`, i.e. no masking at all, for that batch. This is the opposite of what an all-padding row should produce. However, this file is adapted near-verbatim from the upstream `chandar-lab/AMPLIFY_120M` reference implementation (see file header) and the pattern is unchanged from upstream, and a real batch with a fully-padded row is unusual (most tokenizers/collators would not produce one). I'm not confident enough this is a defect introduced by this repo (versus inherited, low-impact upstream behavior) to report it as one, but flagging it here in case it's useful.

## Files read

- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/amplify/src/amplify/state.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/state.py` (diffed against `models/amplify/src/amplify/state.py`; identical apart from the "copied file" header comment)
