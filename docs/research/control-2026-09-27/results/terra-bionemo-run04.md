model: gpt-5.6-terra
repo: bionemo
pinned commit: 11701476b005ca7bc489df924a398b8f12453f0b
date/time started and finished: started approximately 2026-09-28 23:49:24 UTC; finished 2026-09-28 23:51:57 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# BioNeMo review — AMPLIFY and ESM2

## Findings

### 1. TE conversion configuration overrides always fail for settings already present in the source config

- **Severity:** medium
- **Location:** `models/esm2/convert.py:63`
- **What goes wrong:** `convert_esm_hf_to_te(model, hidden_size=...)`, or any other override whose key is already emitted by `model.config.to_dict()`, raises `TypeError: ... got multiple values for keyword argument ...` before conversion begins.
- **Why this is wrong:** The function's docstring explicitly says that `config_kwargs` are additional configuration kwargs for `NVEsmConfig`, but line 63 expands the source config and `config_kwargs` as two separate `**` arguments. Python rejects duplicated keyword names rather than allowing the supplied override to replace the source value.
- **Suggested fix:** Merge the dictionaries before the call, with caller settings last, e.g. `te_config = NVEsmConfig(**(model_hf.config.to_dict() | config_kwargs))` (or `config_dict = model_hf.config.to_dict(); config_dict.update(config_kwargs)`).

### 2. AMPLIFY conversion has the same unusable configuration-override API

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/state_dict_convert.py:47`
- **What goes wrong:** Passing a documented configuration override that is already in an AMPLIFY source configuration, such as `max_length` or `padded_vocab_size` when present, raises the same duplicate-keyword `TypeError`.
- **Why this is wrong:** Lines 37–42 document `config_kwargs` as settings passed to `AMPLIFYConfig`, but line 47 passes `**model_hf.config.to_dict()` and `**config_kwargs` independently. Every normal configuration field is already included in the former dictionary, so callers cannot override it.
- **Suggested fix:** Build one merged dictionary and update it with `config_kwargs` before constructing `AMPLIFYConfig`.

### 3. AMPLIFY checkpoint conversion cannot pad a GPU or non-float32 source embedding

- **Severity:** medium
- **Location:** `models/amplify/src/amplify/state_dict_convert.py:90`
- **What goes wrong:** Converting a Hugging Face AMPLIFY model whose weights are on CUDA fails in `_pad_weights`: `padding_rows` is a CPU tensor and `torch.cat` cannot concatenate it with a CUDA `source_embed`. On CPU float16/bfloat16 inputs it also silently promotes the padded weight to float32, which later conflicts with conversion's dtype preservation checks.
- **Why this is wrong:** Both embedding and decoder weights go through `_pad_weights` (lines 94–102), while line 90 constructs padding without the source tensor's `dtype` or `device`. The adjacent bias-padding transform correctly supplies both at lines 113–115, demonstrating the required behavior.
- **Suggested fix:** Construct the rows with `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device)`.

### 4. Token-dropout scaling uses the wrong sequence boundaries after per-sequence THD padding

- **Severity:** medium
- **Location:** `models/esm2/modeling_esm_te.py:740`
- **What goes wrong:** With `DataCollatorWithFlattening(pad_sequences_to_be_divisible_by=...)` and `config.token_dropout=True`, mask counts for every sequence after the first are taken partly from the preceding sequence's padding and partly from the next sequence. For example, two three-token sequences padded to four occupy `[seq1, pad, seq2, pad]`, but `cu_seq_lens_q` remains `[0, 3, 6]`; line 740 therefore treats elements `3:6` as the second sequence instead of `4:7`. This applies an incorrect mask-dropout scale to the second and subsequent sequences.
- **Why this is wrong:** The collator deliberately retains the original cumulative lengths and publishes padded boundaries separately at `models/esm2/collator.py:224-226`. This method already uses those padded lengths at lines 735–744 to repeat scale factors across the physical input, but calls `nested_tensor_from_jagged(... offsets=kwargs["cu_seq_lens_q"])` at line 740 to count masks. Those offsets do not describe the padded tensor.
- **Suggested fix:** When `cu_seq_lens_q_padded` is present, use it as the jagged offsets for `is_masked` too; retain the unpadded `src_lengths` as the denominator for the actual-token mask ratio.

### 5. Flattening collator produces inconsistent token and sequence-length tensors for supplied attention masks

- **Severity:** medium
- **Location:** `models/esm2/collator.py:166-177`
- **What goes wrong:** A feature with padded tokens represented by an `attention_mask` containing zeros yields an `input_ids`/`labels` tensor that excludes those positions (lines 169–170), but the packed metadata still includes them. `_pt_flatten_collate(features)` at line 166 sums the raw `input_ids` lengths and builds `cu_seq_lens_q` from them. Thus a feature such as `input_ids=[0, 5, 1]`, `attention_mask=[1, 1, 0]` produces two data tokens with a cumulative end offset of three, causing invalid THD metadata and downstream attention failures or incorrect slicing.
- **Why this is wrong:** The public docstring says features may include `attention_mask` (lines 108–115) and promises that the returned packed input and cumulative sequence lengths describe the same flattened batch (lines 121–130). The two paths disagree whenever a supplied mask excludes any original position.
- **Suggested fix:** Normalize/truncate each feature to its valid mask positions before both calling the MLM collator and `_pt_flatten_collate`, or derive the packed tokens and cumulative lengths from the same masked representation.

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
