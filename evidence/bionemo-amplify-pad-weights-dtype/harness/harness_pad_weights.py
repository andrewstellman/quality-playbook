"""
HARNESS EXECUTION (not a real import): transformer_engine.pytorch is an unconditional
module-level import of amplify.amplify_te (imported by amplify.state_dict_convert), and
transformer_engine has no CPU-only wheel / requires CUDA to import. This sandbox has no
GPU and is disk/network constrained, so the real module cannot be imported here.

Instead, _pad_weights is copied VERBATIM from:
  models/amplify/src/amplify/state_dict_convert.py:85-91   (BUGGY / unpatched, current main)
and the sibling from:
  models/esm2/convert.py:238-246                             (reference / correct behaviour)

A minimal stand-in `ctx` object replaces io.TransformCTX (only ctx.target.config.padded_vocab_size
is read by the function body).
"""

import torch


class _Cfg:
    def __init__(self, padded_vocab_size):
        self.padded_vocab_size = padded_vocab_size


class _Target:
    def __init__(self, padded_vocab_size):
        self.config = _Cfg(padded_vocab_size)


class _Ctx:
    def __init__(self, padded_vocab_size):
        self.target = _Target(padded_vocab_size)


# --- verbatim copy: models/amplify/src/amplify/state_dict_convert.py:85-91 (unpatched main) ---
def pad_weights_amplify_buggy(ctx, source_embed):
    """Pad the embedding layer to the new input dimension."""
    target_embedding_dimension = ctx.target.config.padded_vocab_size
    hf_embedding_dimension = source_embed.size(0)
    num_padding_rows = target_embedding_dimension - hf_embedding_dimension
    padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))
    return torch.cat((source_embed, padding_rows), dim=0)


# --- verbatim copy: models/amplify/src/amplify/state_dict_convert.py:85-91, patched per the fix ---
def pad_weights_amplify_fixed(ctx, source_embed):
    """Pad the embedding layer to the new input dimension."""
    target_embedding_dimension = ctx.target.config.padded_vocab_size
    hf_embedding_dimension = source_embed.size(0)
    num_padding_rows = target_embedding_dimension - hf_embedding_dimension
    padding_rows = torch.zeros(
        num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device
    )
    return torch.cat((source_embed, padding_rows), dim=0)


# --- verbatim copy: models/esm2/convert.py:238-246 (correct sibling, for cross-reference only) ---
def pad_weights_esm2_reference(ctx, source_embed):
    """Pad the embedding layer to the new input dimension."""
    target_embedding_dimension = ctx.target.config.padded_vocab_size
    hf_embedding_dimension = source_embed.size(0)
    num_padding_rows = target_embedding_dimension - hf_embedding_dimension
    padding_rows = torch.zeros(
        num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device
    )
    return torch.cat((source_embed, padding_rows), dim=0)


def run(fn, label):
    ctx = _Ctx(padded_vocab_size=12)
    source_embed = torch.randn(10, 4, dtype=torch.bfloat16)  # non-default dtype, CPU device
    out = fn(ctx, source_embed)
    print(f"[{label}] source dtype={source_embed.dtype} device={source_embed.device} "
          f"-> output dtype={out.dtype} device={out.device} shape={tuple(out.shape)}")
    assert out.dtype == source_embed.dtype, (
        f"{label}: expected dtype {source_embed.dtype}, got {out.dtype}"
    )
    assert out.device == source_embed.device, (
        f"{label}: expected device {source_embed.device}, got {out.device}"
    )
    print(f"[{label}] PASS: dtype/device preserved")


if __name__ == "__main__":
    import sys

    label = sys.argv[1] if len(sys.argv) > 1 else "buggy"
    if label == "buggy":
        run(pad_weights_amplify_buggy, "amplify-buggy (unpatched main)")
    elif label == "fixed":
        run(pad_weights_amplify_fixed, "amplify-fixed")
    elif label == "esm2-reference":
        run(pad_weights_esm2_reference, "esm2-reference (already correct upstream)")
    else:
        raise SystemExit(f"unknown label {label}")
