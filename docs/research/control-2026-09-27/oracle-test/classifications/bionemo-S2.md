# bionemo, classifier S2 (Claude Sonnet), blind

### bionemo-01
Oracle: `perplexity` is a module-level `torchmetrics.text.Perplexity` accumulator that `compute_metrics` only calls `.reset()` on inside the `compute_result=True` branch (metrics.py:52-53, 65-67); a stateful `torchmetrics` metric is expected to be reset between independent evaluation runs. Also note the function itself is flagged `# TODO (peter): Is this method even used?` (metrics.py:56) and I could not find it referenced anywhere else in the repo, which weakens how much this matters in practice.
Type: in-repo
Confidence: medium

### bionemo-02
Oracle: In the same function, the `thd` branch computes `max_length` from the shard-local `cu_seq_lens_q_padded` (collator.py:432-433, post-split), but the `bshd` branch at line 434 uses `batch["input_ids"].shape[1]` — the unsharded batch, not `batch_shard["input_ids"]`. The sibling branch shows the intended (shard-local) value.
Type: in-repo
Confidence: high

### bionemo-03
Oracle: `_split_batch_by_cp_rank`'s THD path computes `slice_sizes = (cu_seqlens_padded[1:] - cu_seqlens_padded[:-1]) // total_slices_of_any_sequence` (collator.py:974-975) with plain integer division and no check that each sequence's padded length is divisible by `2 * cp_world_size`; `_process_tensor_thd` then builds shard indices purely from `slice_size`, so remainder tokens are silently excluded from every rank's slice. No assertion or docstring states the divisibility requirement, and the function returns normally.
Type: in-repo
Confidence: medium

### bionemo-04
Oracle: `_pad_weights` builds padding with `torch.zeros(num_padding_rows, source_embed.size(1))`, which defaults to float32/CPU, while the sibling `_pad_bias` in the same file explicitly passes `dtype=source_bias.dtype, device=source_bias.device` (state_dict_convert.py:105-108). The mismatched dtype/device then hits `apply_transforms`'s own dtype-mismatch check (state.py, "dtype mismatch for key") or `torch.cat`'s device-mismatch error.
Type: in-repo
Confidence: high

### bionemo-05
Oracle: `AMPLIFYConfig` stores `self.att_bias`/`self.ffn_bias` and the HF sibling model (amplify_hf.py:128-187) passes `bias=config.att_bias` / `bias=config.ffn_bias` into its own Linear layers, but `amplify_te.py`'s `TransformerLayer` construction hardcodes `bias=False` (amplify_te.py:190) regardless of those config fields.
Type: in-repo
Confidence: high

### bionemo-06
Oracle: The docstring says "padded_vocab_size: ... If not provided, defaults to vocab_size" (modeling_esm_te.py:118-119), but the signature default is `64`, not `None` (line 88), so the fallback `padded_vocab_size or self.vocab_size` (line 145) only ever fires when the caller explicitly passes `None`. The docstring and the default value directly contradict each other.
Type: in-repo
Confidence: high

### bionemo-07
Oracle: `__next__` returns `self._prefetch_result` and only afterward calls `self._kick_prefetch()` to start fetching batch k+1 in a background thread (collator.py:511-517); `state_dict()` calls `self.dataloader.state_dict()` directly (line 596-597) with no join/lock against that thread, so it can capture state that already reflects the in-flight or completed k+1 fetch.
Type: in-repo
Confidence: high

### bionemo-08
Oracle: When `config.layer_norm_before_last_layer` is `True`, the decoder is `LayerNormLinear(..., init_method=lambda x: torch.nn.init.uniform_(x, -self.config.decoder_init_range, self.config.decoder_init_range))`; the `else` branch (`transformer_engine.pytorch.Linear(config.hidden_size, config.vocab_size, params_dtype=config.dtype)`, amplify_te.py:298-301) omits `init_method` entirely, so it falls back to TE's own default initializer instead of the configured uniform range.
Type: in-repo
Confidence: high

### bionemo-09
Oracle: `close()` does `self._prefetch_thread.join(timeout=10)` then unconditionally sets `self._prefetch_thread = None` (collator.py:544-547) without checking `is_alive()`; `__iter__` calls `self.close()` and then `self._kick_prefetch()` (lines 500-505), which starts a fresh thread even if the old one is still running past the 10s timeout — both threads can then be inside `_send_data_to_cp_tp_ranks`/`scatter_object_list` concurrently.
Type: in-repo
Confidence: high

### bionemo-10
Oracle: `attention_mask = torch.where(...).to(torch.bfloat16)` is unconditional (amplify_hf.py:359), regardless of the model's own `dtype`/parameter precision, so an fp32/fp16 model produces a bf16 mask tensor passed alongside fp32/fp16 queries into `scaled_dot_product_attention`/`memory_efficient_attention`, which reject mismatched dtypes.
Type: implicit
Confidence: high

### bionemo-11
Oracle: Tracing `__iter__` with samples of length 6 then 10 and `max_tokens_per_batch=10`: `[A]` is yielded via the overflow branch (collator.py:298-300, `not split_samples`) and `samples=[B]` is left as the *pending* accumulator with `current_length==10`. Because `current_length == max_tokens_per_batch` was only checked at the moment a sample is added within the loop (line 293) and B is added at the overflow branch, not the equality branch, the loop ends with `samples=[B]` un-yielded; `if not self.drop_last and samples: yield samples` (line 327-328) is gated on `drop_last`, so with `drop_last=True` the full, complete batch `[B]` is discarded, not just a genuinely incomplete tail.
Type: in-repo
Confidence: high

### bionemo-12
Oracle: `_apply_token_dropout_thd` checks `if "cu_seq_lens_q_padded" in kwargs:` (modeling_esm_te.py:733-734), which is true even when the key's value is `None`; the next line calls `torch.diff(kwargs["cu_seq_lens_q_padded"])`, and `torch.diff(None)` raises a `TypeError`.
Type: implicit
Confidence: high

### bionemo-13
Oracle: The `match config.hidden_act.lower():` block (amplify_hf.py:148-186) has cases only for `"swiglu"`, `"relu"`, `"gelu"` and no wildcard/default case, so `self.ffn` is never set for any other value (e.g. `"silu"`); the first `forward()` call then raises `AttributeError: 'EncoderBlock' object has no attribute 'ffn'`.
Type: implicit
Confidence: high

### bionemo-14
Oracle: `mask_ratio_observed = n_masked_per_seq.float() / src_lengths` where `src_lengths = torch.diff(kwargs["cu_seq_lens_q"])` (modeling_esm_te.py:734, 739); a zero-length sequence gives `src_lengths[i]==0`, producing `0/0 = NaN` with no guard. No exception is raised — the NaN silently propagates into `scale_factor` and then the embeddings.
Type: known-external
Confidence: medium

### bionemo-15
Oracle: The code's own comment says "We need to find the number of masked tokens in each sequence in the **padded** batch" (modeling_esm_te.py:736), i.e. `input_ids` is laid out per `cu_seq_lens_q_padded`, but the very next line builds `nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"])` (line 741) using the *unpadded* offsets — the comment directly contradicts the offsets actually used, and the worked example (5,6 padded to 8) shows sequence 2's window pulled from the wrong token range.
Type: in-repo
Confidence: high

### bionemo-16
Oracle: `mapping["layer_norm_2.weight"] = "decoder.layer_norm_weight"` is present unconditionally (state_dict_convert.py:33), but `layer_norm_2` is only constructed `if config.layer_norm_before_last_layer:` (amplify_hf.py:320-321); `apply_transforms` raises `ValueError(f"No matches found for source key: {source_key}")` (state.py:323) when the source model lacks that attribute.
Type: in-repo
Confidence: high

### bionemo-17
Oracle: `_send_data_to_cp_tp_ranks` only special-cases `StopIteration` from `next(self._iterator)` (collator.py:582-587); any other exception propagates out of the `try` block entirely (before reaching `_scatter_batch_to_cp_tp_ranks`, whose body calls `scatter_object_list` per its own docstring/nvtx name, line 1014-1026) and is caught generically by `_do_one_prefetch`'s `except Exception` (line 538-539). Non-zero ranks unconditionally call `_scatter_batch_to_cp_tp_ranks(None, ...)` (line 585, runs on every rank) expecting rank 0's scatter, so they block until the process-group collective op times out.
Type: in-repo
Confidence: high

### bionemo-18
Oracle: `__iter__` executes `self._iterator = iter(self.dataloader)` before `self.close()` (collator.py:500-502, in that literal order), so a still-running prefetch thread from the previous iteration can call `next()` on the newly-assigned iterator before `close()`'s join catches up; that batch is then overwritten by the next `_kick_prefetch()` call rather than returned.
Type: in-repo
Confidence: medium

### bionemo-19
Oracle: `AMPLIFYForMaskedLM.__init__`'s `else` branch builds `transformer_engine.pytorch.Linear(config.hidden_size, config.vocab_size, ...)` (amplify_te.py:299-301) — using `vocab_size`, not `padded_vocab_size` — while `_pad_decoder_weights`/`_pad_bias` in state_dict_convert.py (lines 94-117) pad `decoder.weight`/`decoder.bias` to `config.padded_vocab_size`; `apply_transforms` then hits its own shape-mismatch check.
Type: in-repo
Confidence: high

### bionemo-20
Oracle: `_pt_flatten_collate` builds `position_ids` (when requested) from the unpadded `sample_lengths` (collator.py:724-727), and `_pad_sequences_to_be_divisible_by` (lines 204-227) only reassigns `input_ids`, `labels`, and `cu_seq_lens_*_padded` — it never touches `position_ids`, so the returned batch has `input_ids` at padded length/layout and `position_ids` at unpadded length/layout.
Type: in-repo
Confidence: high

### bionemo-21
Oracle: `self.config.layer_precision = ["fp8"] * self.config.num_hidden_layers` (modeling_esm_te.py:185) mutates the same `NVEsmConfig` object that was passed in and that `save_pretrained` later serializes; nothing in the docstring says whether `layer_precision` is meant to represent only an explicit user choice versus an auto-derived runtime default, so I can't point to anything that says this mutation itself is wrong, only that it has this persistence side effect.
Type: none
Confidence: low

### bionemo-22
Oracle: When `cp_world_size == 1`, `_split_batch_by_cp_rank` returns immediately without touching `cu_seqlens_padded` (collator.py:962-964), so the `.get("cu_seq_lens_q_padded", None)` at line 417 never surfaces a missing key there; but `batch_shard["cu_seq_lens_q_padded"]` is indexed directly (not via `.get`) two lines later for the `thd` branch (line 432), so if the wrapped collator didn't produce that key, this raises `KeyError`.
Type: implicit
Confidence: high

### bionemo-23
Oracle: The code's own comment states "TE expects a boolean attention mask, where 'True' indicates a token to be masked" (amplify_te.py:242-243), but the conversion is gated on `attention_mask.dtype is torch.int64` (line 241); a bool/int32/float mask using the conventional 1=attend semantics is passed to TE unconverted, inverting which positions are masked.
Type: in-repo
Confidence: high

### bionemo-24
Oracle: `DataCollatorForContextParallel.__call__` replaces `batch_shard["input_ids"]` with the CP-sharded, shorter tensor but leaves `batch["cu_seq_lens_q"]` (the un-padded, un-sharded cumulative lengths) in `batch_shard = dict(batch)` untouched (collator.py:421-429); `NVEsmEmbeddings._apply_token_dropout_thd` then reads `kwargs["cu_seq_lens_q"]` (modeling_esm_te.py:734, 741) as if it indexes into the local `input_ids` it's operating on, which under CP is only a fraction of the global sequence.
Type: in-repo
Confidence: medium

### bionemo-25
Oracle: `TransformFns.split_qkv_bias`/`merge_qkv_concat`/`merge_qkv_bias_concat`/`merge_qkv_bias` read `config.num_query_groups`/`config.kv_channels` (Megatron-style attribute names), while the sibling `split_qkv`/`merge_qkv` in the same class use `config.num_key_value_heads` (HF-style, state.py:518, 596) — and `split_qkv_bias` reads `ctx.source.config` where `split_qkv` reads `ctx.target.config` (line 515 vs 544). However, `models/esm2/convert.py` and `models/amplify/.../state_dict_convert.py` never call these four Megatron-style helpers (they define their own `_pack_qkv_bias`/`_pack_qkv_weight` instead); the same file is duplicated verbatim across llama3/qwen/mixtral, where it may be exercised against genuinely Megatron-style configs, so within the esm2/amplify code paths this looks like unused inherited boilerplate rather than a live defect.
Type: in-repo
Confidence: low

### bionemo-26
Oracle: `_pt_flatten_collate` sets `batch["attention_mask"]` from the unpadded, per-sample concatenation when `"attention_mask" in features[0]` (collator.py:719-722), and `_pad_sequences_to_be_divisible_by` (lines 204-227) never updates or removes it after padding `input_ids`/`labels`, so the returned `attention_mask` (if present) is shorter than the padded `input_ids`.
Type: in-repo
Confidence: high

### bionemo-27
Oracle: `NVEsmConfig(**model_hf.config.to_dict(), **config_kwargs)` (convert.py:63; same pattern at convert.py:102 and state_dict_convert.py:47) passes two separate `**` expansions to one call; if `config_kwargs` contains a key already present in the source config dict, Python itself raises `TypeError: got multiple values for keyword argument`, independent of any bionemo-specific logic.
Type: implicit
Confidence: high

### bionemo-28
Oracle: `wildcard_matches[i].sort(key=lambda x: int(x) if x.isdigit() else x)` (state.py:429-430, same at amplify/state.py:438) produces a mixed list of `int` and `str` keys whenever a wildcard matches both digit-only and non-digit segments (e.g. `model.0.weight` and `model.norm.weight`); Python's `sort()` then raises `TypeError: '<' not supported between instances of 'str' and 'int'`.
Type: implicit
Confidence: high

### bionemo-29
Oracle: The `mapping` dict (state_dict_convert.py:27-34) has no key for `layer_norm_1.weight`, but `layer_norm_1` is constructed `if config.layer_norm_after_embedding:` (amplify_hf.py:309-310, amplify_te.py:153-154); with that flag set, the source model's `layer_norm_1.weight` has no corresponding entry and is silently never copied to the TE model.
Type: in-repo
Confidence: medium

### bionemo-30
Oracle: `_apply_token_dropout_bshd` computes `src_lengths = attention_mask.sum(-1)` and `mask_ratio_observed = n_masked_per_seq / src_lengths` (modeling_esm_te.py:711-714) with no guard for an all-zero mask row; `0/0` is `NaN` in IEEE-754 float division, which then silently multiplies into that row's embeddings.
Type: known-external
Confidence: medium

Hardest to classify were the ones with no crash and no contradicting comment to point at — bionemo-14, bionemo-21, and bionemo-30. For 14 and 30 the "oracle" is really just IEEE-754 division-by-zero semantics plus the general ML-engineering expectation that embeddings shouldn't silently go NaN, which is a real but generic contract rather than anything bionemo-specific, so I called it known-external with medium confidence rather than in-repo. Bionemo-21 was hardest of all: mutating `self.config` and persisting it via `save_pretrained` is a real footgun, but nothing in the docstring or nearby code states what `layer_precision` is supposed to mean after auto-derivation, so I couldn't point to anything establishing it as wrong rather than an intentional (if surprising) "bake in the effective recipe" design choice. Bionemo-25 was hard in a different way — the code pattern is unambiguously self-inconsistent, but tracing actual call sites showed the buggy functions aren't wired into any esm2/amplify conversion path in this repo, so whether it's a live defect versus dead boilerplate copied from the Megatron-facing models is genuinely ambiguous from static reading alone.
