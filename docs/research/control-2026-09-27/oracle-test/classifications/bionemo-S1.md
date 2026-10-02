# bionemo, classifier S1 (Claude Sonnet), blind

### bionemo-01
Oracle: `perplexity` (metrics.py:26) is a single module-level `Perplexity` instance, and `.reset()` (line 67) is called only inside `if compute_result:` — any evaluation run that stops before a `compute_result=True` call leaves accumulated state for the next caller. The function is also never called anywhere else in the repo (no other references), and carries its own `# TODO (peter): Is this method even used?` comment.
Type: in-repo
Confidence: medium

### bionemo-02
Oracle: in the same loop, the sibling `thd` branch three lines above computes `max_length` from `batch_shard["cu_seq_lens_q_padded"]` (the already-sharded per-rank tensor), while the `bshd` branch at collator.py:435-436 uses `batch["input_ids"].shape[1]` — the pre-shard, unsharded batch.
Type: in-repo
Confidence: high

### bionemo-03
Oracle: the sibling `_process_tensor_bshd` explicitly raises `ValueError` when `seq_len % (2*cp_world_size) != 0` ("must be divisible by ... for BSHD context parallelism"), showing the intended contract; `_process_tensor_thd`/`_split_batch_by_cp_rank` instead does `slice_sizes = (...) // total_slices_of_any_sequence` with no divisibility check, silently truncating the remainder.
Type: in-repo
Confidence: high

### bionemo-04
Oracle: `io.apply_transforms` (esm2/state.py:236, shared code) itself raises `f"dtype mismatch for key {key}: {target_orig_dtypes[key]} vs {target_new_dtypes[key]}"` — the exact message quoted in the finding — when a transform's output dtype doesn't match the target parameter; `torch.zeros(num_padding_rows, source_embed.size(1))` at state_dict_convert.py:90 has no `dtype=`/`device=`, so it defaults to float32/CPU regardless of the source tensor.
Type: in-repo
Confidence: high

### bionemo-05
Oracle: `AMPLIFYConfig.att_bias`/`ffn_bias` ("Whether to use bias in the attention/feedforward network") are correctly wired into `nn.Linear(..., bias=config.att_bias/ffn_bias)` in the HF sibling implementation (amplify_hf.py `EncoderBlock.__init__`); amplify_te.py's `TransformerLayer(...)` construction hardcodes `bias=False` regardless of these same config fields.
Type: in-repo
Confidence: high

### bionemo-06
Oracle: the docstring says `padded_vocab_size`: "If not provided, defaults to vocab_size," but the parameter's actual signature default is `64` (line 88), and `self.padded_vocab_size = padded_vocab_size or self.vocab_size` (line 145) only falls back when `None` is explicitly passed — an omitted argument silently becomes 64, contradicting the doc, and the assertion at line ~149 then fails for `vocab_size > 64`.
Type: in-repo
Confidence: high

### bionemo-07
Oracle: `__next__` joins the prefetch thread for batch k, immediately kicks a new prefetch for batch k+1, then returns batch k — so the wrapped dataloader's own iterator state has already advanced past (or is concurrently advancing past) what the caller received by the time `state_dict()` can be called; `state_dict()`/`load_state_dict()` (lines 592-609) simply delegate to the wrapped dataloader with no accounting for the in-flight prefetch. No explicit spec promises exact resume, but that's the entire purpose of exposing these two methods.
Type: in-repo
Confidence: medium

### bionemo-08
Oracle: in the same `__init__`, the `layer_norm_before_last_layer=True` branch passes `init_method=lambda x: torch.nn.init.uniform_(x, -decoder_init_range, decoder_init_range)`; the `else` branch (plain `Linear`) omits it. Compounding this, `AMPLIFYForMaskedLM.__init__` never calls `self.post_init()` itself (only the inner `AMPLIFY.__init__` does, for its own submodules), so nothing else applies `_init_weights`'s decoder_init_range logic to `self.decoder` either.
Type: in-repo
Confidence: high

### bionemo-09
Oracle: `close()`'s own docstring says "Must be called before destroy_process_group()," implying the thread must actually be stopped; timing out at `join(timeout=10)` and setting `_prefetch_thread = None` anyway lets `__iter__` start a second thread while the first may still be inside `scatter_object_list`, a collective every rank must call in lockstep.
Type: implicit
Confidence: medium

### bionemo-10
Oracle: PyTorch's `scaled_dot_product_attention` and xformers' `memory_efficient_attention` require the additive float `attn_mask`/`attn_bias` to match the query/key dtype; forcing the mask to `torch.bfloat16` unconditionally (amplify_hf.py:361) while running an fp32/fp16 model violates that library contract.
Type: known-external
Confidence: medium

### bionemo-11
Oracle: the field docstring says `drop_last` is "Whether to drop the last batch **if it's less than max_length**" — implying only partial batches should be dropped — but a batch that lands exactly at `max_tokens_per_batch` via the `split_samples=False` overflow branch is held in `samples`, not yielded inline, and is then silently discarded by `if not self.drop_last and samples: yield samples` at stream end, even though it was never "less than max_length."
Type: in-repo
Confidence: high

### bionemo-12
Oracle: it raises — `torch.diff(None)` throws `TypeError` immediately; `"cu_seq_lens_q_padded" in kwargs` only tests key presence, not that the value is non-`None`.
Type: implicit
Confidence: high

### bionemo-13
Oracle: it raises — the `match config.hidden_act.lower()` block has cases only for `"swiglu"`/`"relu"`/`"gelu"` with no `case _:`, so `self.ffn` is never assigned for any other value, and `forward`'s `self._ff_block` access then raises `AttributeError: 'EncoderBlock' object has no attribute 'ffn'`.
Type: implicit
Confidence: high

### bionemo-14
Oracle: `mask_ratio_observed = n_masked_per_seq.float() / src_lengths` (line 740) is an unguarded division; a sequence with `cu_seq_lens_q[i] == cu_seq_lens_q[i+1]` gives `src_lengths[i] == 0`, so `0/0 = NaN` with no check anywhere in the function.
Type: implicit
Confidence: high

### bionemo-15
Oracle: the function itself computes both `src_lengths` (from `cu_seq_lens_q`, unpadded) and `src_lengths_padded` (from `cu_seq_lens_q_padded`), showing it is aware the two layouts diverge — yet `nested_tensor_from_jagged(is_masked, offsets=kwargs["cu_seq_lens_q"])` (line 738) windows `is_masked`, which is derived from `input_ids`, using the unpadded offsets even though `input_ids` is laid out per the padded offsets (per `DataCollatorWithFlattening`'s own `pad_thd_sequences_for_cp` contract).
Type: in-repo
Confidence: high

### bionemo-16
Oracle: `layer_norm_2` is constructed only under `if config.layer_norm_before_last_layer:` (amplify_hf.py:320-321 / te analog), but `mapping` at state_dict_convert.py:33 unconditionally includes `"layer_norm_2.weight": "decoder.layer_norm_weight"`, and `io.apply_transforms` raises "No matches found for source key" when a mapped source key is absent from the source model.
Type: in-repo
Confidence: high

### bionemo-17
Oracle: it hangs — `scatter_object_list` is a collective every rank in the group must call the same number of times; the sibling `StopIteration` branch two lines above (`combined_batch = [ex] * self.num_cp_tp_ranks` then still calls `_scatter_batch_to_cp_tp_ranks`) shows the intended pattern of always scattering, even an error, to every rank — but any other exception from `next(self._iterator)` bypasses that scatter entirely, so the other ranks block until process-group timeout.
Type: in-repo
Confidence: high

### bionemo-18
Oracle: `close()`'s docstring ("Stop the prefetch thread") establishes that no prefetch should still be running once a new iteration starts, but `__iter__` reassigns `self._iterator = iter(self.dataloader)` before calling `self.close()`; if the stale thread hasn't yet called `next()` on the old iterator, it consumes the first item of the brand-new one, and that result is discarded when `_kick_prefetch()` immediately starts a second, unrelated fetch.
Type: in-repo
Confidence: medium

### bionemo-19
Oracle: amplify_te.py's `else` branch builds `Linear(hidden_size, config.vocab_size)` (27 outputs by default) while state_dict_convert.py's `_pad_decoder_weights`/`_pad_bias` pad to `ctx.target.config.padded_vocab_size` (32 by default) for the same `decoder.weight`/`decoder.bias` keys — `io.apply_transforms`'s own shape check raises the quoted "Shape mismatch for parameter" error (parallel to the dtype check that fires for bionemo-04).
Type: in-repo
Confidence: high

### bionemo-20
Oracle: the `__call__` docstring documents `position_ids` as a per-token field of the packed batch, but `_pad_sequences_to_be_divisible_by` (lines 204-227) only reassigns `input_ids`, `labels`, and the two `cu_seq_lens_*_padded` keys; `position_ids`, built earlier in `_pt_flatten_collate` from unpadded per-sequence lengths, is left untouched in the returned batch.
Type: in-repo
Confidence: high

### bionemo-21
Oracle: the constructor mutates `self.config.layer_precision` — the model's own live config object — purely as a side effect of being handed an `fp8_recipe` with no explicit `layer_precision`, and that same config object is what `save_pretrained` later serializes to `config.json`; nothing in the file documents this as intentional, only a `UserWarning` at construction time.
Type: in-repo
Confidence: medium

### bionemo-22
Oracle: it raises — `_split_batch_by_cp_rank` early-returns for `cp_world_size <= 1` (line ~962) before ever reaching its own `if cu_seqlens_padded is None: raise ValueError(...)` check for the "thd" branch, so a missing key is never caught there; the caller then indexes `batch_shard["cu_seq_lens_q_padded"]` unconditionally (line ~433) even though it was fetched via `.get(..., None)` two lines earlier, so a batch lacking that key raises `KeyError`.
Type: implicit
Confidence: high

### bionemo-23
Oracle: the comment directly above the line states TE's contract explicitly — "TE expects a boolean attention mask, where 'True' indicates a token to be masked" — but the inversion is gated on `attention_mask.dtype is torch.int64` (an identity check on one specific dtype) rather than on the mask's semantic convention, so a bool, int32, or float mask using the standard 1=attend convention bypasses the inversion and is passed straight to TE unchanged.
Type: in-repo
Confidence: high

### bionemo-24
Oracle: `DataCollatorForContextParallel.__call__` sets `batch_shard["input_ids"] = input_ids_sharded` (a fraction of the tokens) but `batch_shard = dict(batch)` copies `cu_seq_lens_q` from the wrapped collator's output unsharded (only `cu_seq_lens_q_padded` is consumed by `_split_batch_by_cp_rank`); `_apply_token_dropout_thd`, called downstream, then uses these global offsets against the local, truncated `input_ids` buffer — the same root cause and code paths verified for bionemo-12/15.
Type: in-repo
Confidence: high

### bionemo-25
Oracle: neither `NVEsmConfig` nor `AMPLIFYConfig` defines `num_query_groups` or `kv_channels` (confirmed by grep across both files), so calling these helpers with either config raises `AttributeError`; however, grepping every caller in the repo shows `split_qkv_bias`, `merge_qkv_concat`, `merge_qkv_bias_concat`, and `merge_qkv_bias` are never invoked anywhere — only the sibling `merge_qkv`/`split_qkv` (which correctly read `num_key_value_heads` from an HF-style config) are wired into the llama3/mixtral/qwen converters. The `ctx.source` vs `ctx.target` inconsistency between `split_qkv_bias` and `split_qkv` is real but currently unreachable dead code with an HF/ESM config in this repo's own call graph. Duplicated verbatim (and marked "copied file, do not modify directly") in amplify/state.py.
Type: in-repo
Confidence: medium

### bionemo-26
Oracle: same function as bionemo-20 — `attention_mask` (built in `_pt_flatten_collate` from unpadded per-sequence masks) is never touched by `_pad_sequences_to_be_divisible_by`, while `input_ids`/`labels` are replaced by longer, padded tensors, so the returned batch has `attention_mask.shape[1] < input_ids.shape[1]`, contradicting the docstring's own per-field shape documentation.
Type: in-repo
Confidence: high

### bionemo-27
Oracle: it raises — all three converters build `Config(**model_hf.config.to_dict(), **config_kwargs)` (confirmed at esm2/convert.py:63/102 and amplify/state_dict_convert.py:47); any `config_kwargs` key also present in `model_hf.config.to_dict()` (which contains every field of the source config, e.g. `token_dropout`) is unpacked twice into the same call, which Python itself rejects with `TypeError: got multiple values for keyword argument` before the target `Config.__init__` ever runs.
Type: implicit
Confidence: high

### bionemo-28
Oracle: it raises — `sort(key=lambda x: int(x) if x.isdigit() else x)` produces a mix of `int` and `str` sort keys whenever a wildcard matches both digit-like and non-digit-like captures (e.g. `"0"` and `"norm"`), and Python's `list.sort` attempting `<` between an `int` and a `str` raises `TypeError`. Verified duplicated verbatim at amplify/state.py:438 (marked as a copied file).
Type: implicit
Confidence: high

### bionemo-29
Oracle: `layer_norm_1` is constructed only under `if config.layer_norm_after_embedding:` (amplify_hf.py:309-310), mirroring the `layer_norm_2`/`layer_norm_before_last_layer` pattern that the converter does handle for bionemo-16 — but unlike that case, no `"layer_norm_1.weight"` entry exists anywhere in `mapping` at all, so the target `layer_norm_1` (when the source config enables it) is simply left at its `init_empty_weights` value with no error raised.
Type: in-repo
Confidence: high

### bionemo-30
Oracle: the BSHD sibling of bionemo-14's exact bug — `src_lengths = attention_mask.sum(-1)` is 0 for an all-zero-mask row, and `n_masked_per_seq / src_lengths` (line 715) divides by that zero with no guard, producing NaN that then multiplies the whole row's embeddings.
Type: implicit
Confidence: high

Hardest to classify: bionemo-07, bionemo-18, and bionemo-21. The first two depend on thread-timing races (whether the background prefetch thread has actually progressed past a given point when `state_dict()`/`close()`/`__iter__` run) that I can reason through from the code but can't prove deterministic without running it, and there's no docstring stating an exact-resume or no-overlap guarantee — I inferred the contract from what the methods are clearly *for* rather than from an explicit spec, which is weaker footing than a quoted docstring. bionemo-21 was hard because the "wrongness" is entirely a design judgment (should construction-time recipe availability silently become a persisted config default for reload?) with no comment or test asserting the alternative; I could equally see an author defending it as intentional convenience, so I lowered confidence rather than calling it a hard defect. bionemo-25 was also awkward: the AttributeError is real and verifiable by grep, but because none of the flagged functions are ever called in this repo's actual conversion paths, it sits in a gray zone between "provable defect" and "dead code nobody will hit."
