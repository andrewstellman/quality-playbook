model: gpt-5.6-terra
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:53:28 UTC; finished 2026-09-28 23:56:07 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review — bionemo-recipes `11701476b005ca7bc489df924a398b8f12453f0b`

## Findings

### 1. THD token-dropout groups tokens with the unpadded offsets after per-sequence padding

- **Severity:** high
- **Location:** `models/esm2/modeling_esm_te.py:741`
- **What goes wrong:** Context-parallel packed batches produced with
  `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=...)` contain padding
  between sequences.  The collator retains the original cumulative lengths in
  `cu_seq_lens_q` and supplies the physical positions in
  `cu_seq_lens_q_padded` (`collator.py:213-226`).  `_apply_token_dropout_thd`
  nevertheless passes the unpadded `cu_seq_lens_q` as the offsets for the padded
  `input_ids`.  For example, two length-3 sequences padded to length 8 have offsets
  `[0, 3, 6]` and `[0, 8, 16]`; grouping the 16-token tensor with `[0, 3, 6]`
  makes the second group consist of padding from the first sequence rather than the
  second sequence (and may be rejected by the jagged-tensor constructor because the
  offsets do not cover the values).  Consequently mask ratios are wrong, or the
  forward fails, whenever ESM's `token_dropout` is enabled and CP padding is used.
- **Why this is wrong:** The method explicitly says that it computes the observed
  ratio *per sequence* and already selects `cu_seq_lens_q_padded` at lines 735-738
  to align the scale factors with the padded layout.  The token groups must use the
  same layout.  The collator documents and produces those padded offsets precisely
  for per-sequence padding.
- **Suggested fix:** When `cu_seq_lens_q_padded` is present, use it as the
  `offsets` argument to `nested_tensor_from_jagged`; continue to divide by the
  unpadded `src_lengths` so inserted padding does not affect the mask ratio.

### 2. The reference AMPLIFY model creates an attention bias with a dtype incompatible with its FP32 queries

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/amplify_hf.py:360-366`
- **What goes wrong:** A normally constructed `AMPLIFY` uses FP32 embedding and
  projection weights.  If a batch has any padding, this code unconditionally makes
  the additive attention mask `torch.bfloat16`; on the CPU path it is supplied to
  `torch.nn.functional.scaled_dot_product_attention` with FP32 query/key/value
  tensors (lines 265-270).  SDPA requires a floating-point mask to have the query
  dtype (or to be boolean), so an FP32 model with a nontrivial padding mask raises a
  dtype error rather than producing logits.
- **Why this is wrong:** The implementation deliberately has an `else` branch for
  non-CUDA tensors, and `AMPLIFYConfig`/the embedding constructor do not make the
  default model BF16.  Thus the model's advertised forward path fails for the
  standard default configuration whenever padded inputs are used.
- **Suggested fix:** Build the additive mask in the attention input dtype, e.g.
  `attention_mask = torch.where(...).to(dtype=self.encoder.weight.dtype)`, or make
  it a boolean mask with the polarity required by SDPA.

### 3. The TE AMPLIFY forward reverses only `int64` masks and therefore inverts ordinary boolean masks

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/amplify_te.py:245-247`
- **What goes wrong:** Hugging Face-style boolean masks use `True`/`1` for a valid
  token.  Passing such a mask to this forward method skips the `int64`-only
  conversion and passes it directly to Transformer Engine, whose adjacent comment
  says `True` means *masked*.  Every valid token is masked and each padded token is
  exposed.  Integer masks other than `torch.int64` are likewise left in the wrong
  representation.
- **Why this is wrong:** The sibling reference implementation accepts a standard
  1/0 attention mask (`amplify_hf.py:360-366`), while this public forward accepts an
  unconstrained `torch.Tensor` attention mask.  The comment itself establishes that
  TE uses the opposite boolean convention.
- **Suggested fix:** Normalize all standard rank-2 binary masks, including bool and
  every integral dtype, with `~attention_mask.to(torch.bool)` before the TE layer.
  If TE-native masks are intended as an additional API, expose a separate explicit
  option rather than inferring it from the dtype.

### 4. AMPLIFY checkpoint conversion cannot pad a CUDA or non-FP32 source checkpoint

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/state_dict_convert.py:85-91`
- **What goes wrong:** `_pad_weights` creates the padding rows with bare
  `torch.zeros(...)`, which always creates a CPU FP32 tensor.  `torch.cat` therefore
  fails immediately when `source_embed` is on CUDA.  For a BF16/FP16 source on CPU,
  it promotes the padded tensor to FP32, so conversion no longer preserves the
  checkpoint dtype and can fail the dtype consistency check in `amplify/state.py`.
  This affects the documented generic `convert_amplify_hf_to_te(model_hf)` function
  whenever its caller supplies a model loaded in reduced precision or moved to GPU.
- **Why this is wrong:** The ESM2 counterpart handles this exact operation by
  constructing rows with `dtype=source_embed.dtype, device=source_embed.device`
  (`models/esm2/convert.py:238-246`).  The AMPLIFY converter's own bias-padding
  transform follows that rule at lines 113-115.
- **Suggested fix:** Construct `padding_rows` with `dtype=source_embed.dtype` and
  `device=source_embed.device` (or use `torch.zeros_like(source_embed[:num_padding_rows])`).

## Files read

- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/amplify/src/amplify/state.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/metrics.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/state.py`
- `models/esm2/export.py`
- `models/esm2/README.md`
