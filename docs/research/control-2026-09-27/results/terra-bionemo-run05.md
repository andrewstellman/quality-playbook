model: gpt-5.6-terra
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:49:53 UTC; finished 2026-09-28 23:52:25 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review — `models/amplify/src/amplify/` and `models/esm2/`

## Findings

### 1. AMPLIFY conversion cannot pad half-precision or CUDA weights

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/state_dict_convert.py:85-91`
- **What goes wrong:** `convert_amplify_hf_to_te()` fails while padding the word-embedding or decoder weight whenever the source checkpoint is `float16`/`bfloat16` or is on CUDA. `_pad_weights()` creates `padding_rows` with the default dtype and device (`float32` on CPU), then concatenates it with `source_embed`. `torch.cat` requires matching dtype and device.
- **Why this is wrong:** The conversion API accepts an arbitrary Hugging Face module, and its docstring promises to convert that model. This path is mandatory for the normal AMPLIFY vocabulary-padding conversion (`encoder.weight` and `decoder.weight` are both transformed at lines 94-102). The nearby ESM2 implementation correctly constructs its padding tensor with `dtype=source_embed.dtype, device=source_embed.device` (`models/esm2/convert.py:243-245`), establishing the required behavior.
- **Suggested fix:** Construct `padding_rows` with `dtype=source_embed.dtype` and `device=source_embed.device`.

### 2. The TE AMPLIFY model ignores both configured bias options

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/amplify_te.py:176-191`
- **What goes wrong:** An `AMPLIFYConfig(att_bias=True)` or `AMPLIFYConfig(ffn_bias=True)` still creates every Transformer Engine layer with `bias=False`. The converted/inference model therefore omits all attention and feed-forward biases. A conversion from the non-TE AMPLIFY implementation with either flag enabled also silently drops the source bias weights, since the conversion mapping contains no bias entries.
- **Why this is wrong:** `AMPLIFYConfig` documents `ffn_bias` and `att_bias` as controlling feed-forward and attention bias use (`amplify_te.py:81-83`). The reference AMPLIFY implementation honors them: attention projections use `bias=config.att_bias` (`amplify_hf.py:125-143`) and its ReLU/GELU feed-forward linear layers use `bias=config.ffn_bias` (`amplify_hf.py:163-188`). Hard-coding `bias=False` contradicts the configuration and produces a model with a different architecture and predictions.
- **Suggested fix:** Pass the supported bias setting(s) through to `TransformerLayer` (or reject unsupported non-default configurations explicitly), and add mappings/transforms for the corresponding bias state-dict entries.

### 3. Boolean and non-`int64` AMPLIFY masks have their meaning reversed

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/amplify_te.py:244-247`
- **What goes wrong:** The TE implementation inverts a Hugging Face-style mask only when its dtype is exactly `torch.int64`. Passing an otherwise equivalent boolean (or `int32`) mask sends it unchanged to Transformer Engine. Thus `True`/`1` valid-token entries are treated as masked and `False`/`0` padding entries as visible.
- **Why this is wrong:** The comment immediately above states that Transformer Engine uses boolean masks where `True` means masked. The public forward argument is simply documented as an attention mask (`amplify_te.py:232-233`), while the non-TE AMPLIFY implementation interprets `1` as attend and `0` as mask (`amplify_hf.py:359-366`). Masks with the same values but a common boolean/integer dtype must not change model semantics.
- **Suggested fix:** Normalize ordinary 0/1 masks regardless of integer/boolean dtype, for example `attention_mask = ~attention_mask.to(torch.bool)`. If TE-native boolean masks are to be accepted separately, expose an explicit option rather than inferring it from dtype.

### 4. THD context-parallel sharding silently discards sequence tails

- **Severity:** high
- **Location:** `models/esm2/collator.py:974-987`
- **What goes wrong:** For THD input, `_split_batch_by_cp_rank()` computes each per-sequence shard width with floor division by `2 * cp_world_size` and does not validate divisibility. For example, with `cp_world_size=2` and a sequence length of 5, `slice_size` is 1; ranks select indices `[0, 3]` and `[1, 2]`, and token 4 is never sent to any rank. Sequences shorter than `2 * cp_world_size` produce zero-length shards.
- **Why this is wrong:** The function says it supports variable-length THD sequences (`collator.py:940-946`) and documents no divisibility precondition. Its BSHD sibling explicitly rejects non-divisible lengths rather than corrupting them (`collator.py:845-849`). The THD implementation instead loses input tokens and labels, which corrupts training/inference without an error.
- **Suggested fix:** Before calculating `slice_sizes`, verify every padded sequence length is divisible by `2 * cp_world_size` and raise `ValueError` otherwise. Alternatively, pad each sequence in this function to that multiple and update the cumulative lengths consistently.

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
- `models/esm2/README.md`
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/state.py`
