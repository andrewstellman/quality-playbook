# bionemo, classifier O2 (Claude Opus), blind

### bionemo-01
Oracle: Leftover state only shows up if an evaluation is aborted partway. torchmetrics' documented accumulate-until-`reset()` behaviour would then mix two runs, but nothing in the repo defines what should happen after an abort. The function's own comment says "TODO (peter): Is this method even used?", so it may be dead code.
Type: none
Confidence: low

### bionemo-02
Oracle: This is only wrong if TE's context-parallel attention expects per-shard `max_seqlen`. As far as I recall, TE takes the global value and divides it by the CP size internally. The THD branch (collator.py:433) also uses global, unsharded `cu_seq_lens_q_padded` lengths, so the BSHD branch is at least consistent with it. I would need to read TE's CP contract to be sure.
Type: fetch-external
Confidence: low

### bionemo-03
Oracle: The sibling BSHD path, `_process_tensor_bshd` (collator.py:845-849), raises `ValueError` when the sequence length "must be divisible by {total_chunks} (2 * cp_world_size)". The THD path accepts the same kind of non-divisible input and silently drops tokens. The input breaks a precondition that `pad_sequences_to_be_divisible_by` should enforce, but the path does not validate it.
Type: in-repo
Confidence: medium

### bionemo-04
Oracle: The ESM2 twin of this function, `_pad_weights` (esm2/convert.py:243-245), builds the padding with `dtype=source_embed.dtype, device=source_embed.device`. So does `_pad_bias` in the same file (state_dict_convert.py:113-115). `apply_transforms` enforces the dtype check that then raises (amplify state.py:242).
Type: in-repo
Confidence: high

### bionemo-05
Oracle: `AMPLIFYConfig` documents `att_bias`/`ffn_bias` as "Whether to use bias in the attention / feedforward network". The HF model honours them (amplify_hf.py:128, 160, 167), but the TE model hard-codes `bias=False` (amplify_te.py:190), so the conversion silently drops weights. The published checkpoints probably have both flags False, which limits the impact.
Type: in-repo
Confidence: medium

### bionemo-06
Oracle: The docstring says of `padded_vocab_size`: "If not provided, defaults to vocab_size." The signature default is 64, so that fallback only happens when `None` is passed. `export.py:78` passing `padded_vocab_size=None` explicitly suggests the authors work around this. The 64 default may be deliberate for ESM-2 FP8 (vocab 33), so the docstring may be what is wrong.
Type: in-repo
Confidence: medium

### bionemo-07
Oracle: The torchdata `StatefulDataLoader` contract is that `state_dict()` reflects the batches yielded to the caller. `recipes/esm2_native_te/checkpoint.py` saves that dataloader state and resumes at `step + 1`, which assumes the two line up. The prefetch makes the saved state one batch ahead, so a batch is skipped on resume. The llama3 and mixtral copies of this wrapper do the same, so the repo has no correct version to compare against.
Type: known-external
Confidence: medium

### bionemo-08
Oracle: The other branch passes `init_method=... uniform_(-decoder_init_range, decoder_init_range)` (amplify_te.py:293-295). `AMPLIFYPreTrainedModel._init_weights` (amplify_te.py:122-125) also intends that uniform init for `transformer_engine.pytorch.Linear`, but `AMPLIFYForMaskedLM` never calls `post_init`. This only affects from-scratch training with a rarely used flag.
Type: in-repo
Confidence: low

### bionemo-09
Oracle: The docstring says "Stop the prefetch thread. Must be called before destroy_process_group()", but after a timed-out `join` the thread keeps running. torch.distributed requires collectives on one process group to be issued in a consistent order, not concurrently from two threads. This needs a prefetch that takes more than 10 s.
Type: in-repo
Confidence: low

### bionemo-10
Oracle: PyTorch's `scaled_dot_product_attention` requires `attn_mask` to be bool or to match the query dtype, and xformers `attn_bias` has a similar dtype requirement, so a hard-coded bf16 mask with fp32/fp16 queries raises. Every repo test runs in bf16 or under bf16 autocast, and this module is adapted from upstream, so it may be a bf16-only design.
Type: known-external
Confidence: medium

### bionemo-11
Oracle: The field docstring says `drop_last`: "Whether to drop the last batch if it's less than max_length." `[B]` has exactly `max_tokens_per_batch` tokens, so it is a full batch and should not be dropped. The code misses it because it never re-checks `current_length == max_tokens_per_batch` after resetting to `padded_len` (lines 306 and 322).
Type: in-repo
Confidence: high

### bionemo-12
Oracle: `torch.diff(None)` raises. The encoder treats a `None` value as absent (`kwargs.get("cu_seq_lens_q_padded", None)` at modeling_esm_te.py:285), so the `in` check here is inconsistent with it.
Type: implicit
Confidence: low

### bionemo-13
Oracle: Construction succeeds and the first forward pass raises `AttributeError`. `"silu"` is not supported anyway, so the only harm is a late, confusing error in place of an early `ValueError`.
Type: implicit
Confidence: low

### bionemo-14
Oracle: 0/0 gives NaN, but when the padded length is also 0, `repeat_interleave` at line 744 applies that scale factor to no tokens. Nothing in the repo says zero-length sequences must be handled, and I can't point to any visible harm.
Type: none
Confidence: low

### bionemo-15
Oracle: The code's own comment at modeling_esm_te.py:739 says: "We need to find the number of masked tokens in each sequence in the padded batch." Line 744 then expands using `src_lengths_padded`, which shows the padded layout is understood. Line 741 still takes its windows from the unpadded `cu_seq_lens_q` offsets.
Type: in-repo
Confidence: high

### bionemo-16
Oracle: The TE model has an explicit `layer_norm_before_last_layer=False` branch (amplify_te.py:298-301) and the HF model makes `layer_norm_2` conditional (amplify_hf.py:320). The converter's unconditional mapping then raises "No matches found for source key" (amplify state.py:323) for a supported configuration.
Type: in-repo
Confidence: medium

### bionemo-17
Oracle: The other ranks hang in `scatter_object_list` until the process-group timeout. The comment at lines 581-582 shows the intent to propagate errors to all CP ranks, but it only does so for `StopIteration`. Rank 0 still raises, so the job dies eventually.
Type: implicit
Confidence: medium

### bionemo-18
Oracle: Python and DataLoader semantics mean a fresh `iter()` should yield from the first batch; losing that batch is a race. It needs the old prefetch thread not to have reached `next()` yet, which is a narrow window. Nothing in the repo specifies this directly.
Type: known-external
Confidence: low

### bionemo-19
Oracle: The converter pads `decoder.weight` to `padded_vocab_size`, but the non-LayerNorm branch builds the decoder with `config.vocab_size` outputs, so `apply_transforms` raises "Shape mismatch" (amplify state.py:178-181). The `LayerNormLinear` branch uses `padded_vocab_size` and forward slices logits at line 345, which shows padded is intended. bionemo-16 fires first on the same path.
Type: in-repo
Confidence: medium

### bionemo-20
Oracle: The sibling padding path `_pt_pad_to_multiple_of` (collator.py:920-923) extends `position_ids` along with `input_ids`, and this path does not. `NVEsm` ignores `position_ids`, so the practical impact is limited to other consumers.
Type: in-repo
Confidence: medium

### bionemo-21
Oracle: The config docstring says "`None` (the default) means no quantization is configured". The warning at line 186 frames the FP8 fallback as a runtime choice for this build, yet it is written into the config and persisted by `save_pretrained`. Persisting it could also be intended.
Type: in-repo
Confidence: low

### bionemo-22
Oracle: A `KeyError` is raised. With `cp_world_size > 1` the same input gets a clear `ValueError` ("cu_seqlens_padded is required for THD format", line 972), so this is a misconfiguration that fails with a worse message rather than a wrong result.
Type: implicit
Confidence: low

### bionemo-23
Oracle: The comment at amplify_te.py:246 says TE expects a mask where "True" means masked, and the conversion is gated on int64. The ESM2 sibling converts masks regardless of dtype (modeling_esm_te.py:497-502). Tokenizers produce int64, so only callers passing other dtypes are affected.
Type: in-repo
Confidence: medium

### bionemo-24
Oracle: `recipes/esm2_native_te/train_ddp_cp.py:93` says: "token_dropout is set to False because it's not compatible with context parallelism." The CP tests set `token_dropout=False` too. The incompatibility is documented and known; the only defect is that it isn't enforced by an error.
Type: in-repo
Confidence: low

### bionemo-25
Oracle: `models/qwen/convert_qwen2.py:41-80` reimplements `_merge_qkv_bias`/`_split_qkv_bias` using `num_key_value_heads` and `ctx.target`, which shows the shared helpers don't work with HF configs. Their variable name `megatron_config` shows they were written for Megatron configs, and neither ESM2 nor AMPLIFY calls them. The source/target inconsistency is visible against `split_qkv` (state.py:515).
Type: in-repo
Confidence: low

### bionemo-26
Oracle: `_pt_pad_to_multiple_of` (collator.py:915-918) pads `attention_mask` along with `input_ids`; this path does not. `DataCollatorForContextParallel` pops `attention_mask` (line 408) and the THD model sets it to `None`, so it is mostly unused downstream.
Type: in-repo
Confidence: low

### bionemo-27
Oracle: Passing the same keyword twice raises `TypeError` in Python. The docstring says `**config_kwargs` are "Additional configuration kwargs to be passed to NVEsmConfig", and overriding keys such as `token_dropout` is the obvious use. `convert_esm_te_to_hf` uses `filtered_config` but has the same problem for overlapping keys.
Type: implicit
Confidence: medium

### bionemo-28
Oracle: In Python 3, sorting a list that mixes `int` and `str` keys raises `TypeError`. No mapping in the repo uses such a pattern, so this is latent.
Type: known-external
Confidence: medium

### bionemo-29
Oracle: Both models build `layer_norm_1` when `layer_norm_after_embedding=True` (amplify_te.py:153-160, amplify_hf.py:309-314). `apply_transforms` requires every target key to be filled and raises "Additional keys ... in target model but not in source model" (amplify state.py, after the buffer loop). So this raises rather than silently skipping as the finding says, but it is still a defect for a supported flag.
Type: in-repo
Confidence: medium

### bionemo-30
Oracle: A row with no attended tokens is a degenerate input. The code matches Hugging Face's upstream `EsmEmbeddings` token-dropout logic as I remember it, and nothing in the repo says such rows must be handled.
Type: none
Confidence: low

**Hardest to classify.** The prefetch/threading findings (07, 09, 17, 18) were the hardest. The llama3/mixtral/qwen copies of the wrapper behave identically, so the repo has no correct version to compare against, and the real oracles (StatefulDataLoader resume semantics, torch.distributed collective ordering) are outside it. That made me pick between in-repo docstrings and external contracts. bionemo-02 was hard because whether per-shard `max_length` is wrong depends on TE internals I can't confirm without reading them. Several converter findings (05, 16, 19, 29) have clear in-repo oracles, since the flags exist and are honoured by one model but not the conversion path. But the published AMPLIFY checkpoints probably never set those flags, so defect status is clear while impact is uncertain. bionemo-06 and bionemo-24 were awkward the other way: the repo itself provides the oracle, but it points to a documented or deliberate choice (a docstring that may be what's wrong; a known CP/token-dropout incompatibility), not an unknown bug.
