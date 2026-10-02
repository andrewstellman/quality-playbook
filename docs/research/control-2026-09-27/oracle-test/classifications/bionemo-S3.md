# bionemo, classifier S3 (Claude Sonnet), blind

### bionemo-01
Oracle: `torchmetrics.Metric` semantics require `reset()` before accumulating a new independent computation, and the HF Trainer's `compute_result` flag contract (this function's own signature) implies each eval run should start clean; here `perplexity.reset()` only runs inside `if compute_result:` (metrics.py:66-67), so a run that never reaches `compute_result=True` (interrupted eval) leaves stale state for the next call. Note the file's own `# TODO (peter): Is this method even used?` (metrics.py:58) and a `grep` across the repo shows `compute_metrics` is never called anywhere else in this checkout, so the defect's real-world impact is unclear.
Type: known-external
Confidence: medium

### bionemo-02
Oracle: The sibling `thd` branch in the same function (collator.py:428-429) computes `max_length` from the just-sharded `batch_shard["cu_seq_lens_q_padded"]`, i.e. shard-local data; the `bshd` branch at line 435-436 instead reads `batch["input_ids"].shape[1]` — the pre-sharding, full-batch tensor — not `input_ids_sharded`/`batch_shard["input_ids"]`.
Type: in-repo
Confidence: high

### bionemo-03
Oracle: The sibling BSHD sharder `_process_tensor_bshd` (collator.py:829-833/847) explicitly checks `seq_len % total_chunks != 0` and raises `ValueError("...must be divisible by...")`; the THD path (`_split_batch_by_cp_rank`/`_process_tensor_thd`, collator.py:975-976) computes `slice_sizes = ... // total_slices_of_any_sequence` with no equivalent check, silently truncating any sequence whose padded length isn't divisible by `2*cp_world_size`.
Type: in-repo
Confidence: high

### bionemo-04
Oracle: The sibling transform `_pad_bias` in the same file (state_dict_convert.py:104-110) explicitly builds its padding tensor with `dtype=source_bias.dtype, device=source_bias.device`; `_pad_weights` (line 90) calls `torch.zeros(num_padding_rows, source_embed.size(1))` with no dtype/device args, defaulting to float32/CPU, which is then concatenated with `torch.cat` against the real (possibly bf16/CUDA) source tensor.
Type: in-repo
Confidence: high

### bionemo-05
Oracle: `amplify_hf.py` (lines 128-187) wires `bias=config.att_bias` / `bias=config.ffn_bias` throughout the parallel HF implementation of the same model, and `AMPLIFYConfig` (amplify_te.py) accepts and stores `att_bias`/`ffn_bias`; the TE `TransformerLayer` construction (amplify_te.py:190) hardcodes `bias=False`, ignoring those config fields entirely.
Type: in-repo
Confidence: high

### bionemo-06
Oracle: The docstring says `padded_vocab_size: ... If not provided, defaults to vocab_size` (modeling_esm_te.py ~118-119), but the `__init__` signature default is `64` (line 88), so "not provided" from a caller's perspective uses 64, not `vocab_size`; the `padded_vocab_size or self.vocab_size` fallback (line 145) only triggers when `None` is passed explicitly, contradicting the documented behavior and tripping the `assert padded_vocab_size >= vocab_size` (line 149) for any N > 64.
Type: in-repo
Confidence: high

### bionemo-07
Oracle: `__next__` (collator.py:511-521) immediately calls `self._kick_prefetch()` after consuming the current prefetch result, starting the fetch for batch k+1 before returning batch k; `state_dict()` (collator.py:592-599) forwards straight to `self.dataloader.state_dict()`, which by then reflects that in-flight/completed k+1 fetch, so a `load_state_dict` resume skips batch k+1.
Type: in-repo
Confidence: high

### bionemo-08
Oracle: The `if config.layer_norm_before_last_layer:` branch (amplify_te.py:298-301) passes an explicit `init_method=lambda x: torch.nn.init.uniform_(x, -decoder_init_range, decoder_init_range)` to `LayerNormLinear`; the sibling `else` branch constructing `transformer_engine.pytorch.Linear` (lines 298-301, the `else`) passes no `init_method`, so it falls back to TE's own default init rather than the documented `decoder_init_range`-uniform init used in the other branch.
Type: in-repo
Confidence: high

### bionemo-09
Oracle: `close()` (collator.py:544-547) does `self._prefetch_thread.join(timeout=10); self._prefetch_thread = None` unconditionally — it clears the handle even if `join` timed out and the thread is still alive; `__iter__` (collator.py:500-504) calls `close()` then `self._kick_prefetch()` right after, so a still-running old thread and the freshly started new thread can both be inside `_send_data_to_cp_tp_ranks`/`scatter_object_list` concurrently.
Type: in-repo
Confidence: high

### bionemo-10
Oracle: `amplify_hf.py:361` unconditionally does `attention_mask.to(torch.bfloat16)`; `torch.nn.functional.scaled_dot_product_attention` and xformers `memory_efficient_attention` require the mask dtype to be compatible with the query/key dtype (bool, or matching float dtype) — a bf16 additive mask combined with fp32/fp16 q/k/v raises at the call. This is a direct runtime crash observable from the code itself.
Type: implicit
Confidence: high

### bionemo-11
Oracle: The exact-match branch just above (collator.py:293-296, `if current_length == self.max_tokens_per_batch: yield [...]`) shows the function's own intent that a batch exactly filling `max_tokens_per_batch` is complete and must be yielded, not treated as a dangling partial batch subject to `drop_last`; the post-loop `if not self.drop_last and samples: yield samples` (line 331) drops a `[B]` batch that is exactly full, not merely partial, whenever the stream ends right after it was started via the "yield-before, start-new" `split_samples=False` path.
Type: in-repo
Confidence: high

### bionemo-12
Oracle: `"cu_seq_lens_q_padded" in kwargs` (modeling_esm_te.py:735) only checks key presence, not that the value is non-`None`; `torch.diff(kwargs["cu_seq_lens_q_padded"])` (line 736) will raise a `TypeError`/crash if that value is `None`. Whether a caller realistically passes the key with value `None` (e.g. an HF-style kwargs dict with all optional fields present but unset) I can't confirm from this file alone, but the crash itself is self-evident from the code.
Type: implicit
Confidence: medium

### bionemo-13
Oracle: The `match config.hidden_act.lower():` (amplify_hf.py:148) has cases only for `"swiglu"`, `"relu"`, `"gelu"` and no wildcard/default case; for any other value `self.ffn` is never assigned, so the first `forward()` call reading `self.ffn` raises `AttributeError`. Self-evident from the code.
Type: implicit
Confidence: high

### bionemo-14
Oracle: `mask_ratio_observed = n_masked_per_seq.float() / src_lengths` (modeling_esm_te.py:740) with no guard against `src_lengths == 0`, producing NaN that then scales the embeddings. The repo's own tests assert `torch.isfinite(loss)` after forward passes (`tests/common/test_modeling_common.py:897,934,971,1021`), establishing that NaN propagation is treated as a defect in this codebase, but there's no explicit zero-length-sequence check anywhere in this function or its callers to show this input is disallowed.
Type: in-repo
Confidence: medium

### bionemo-15
Oracle: The line's own comment says "We need to find the number of masked tokens in each sequence **in the padded batch**" (modeling_esm_te.py:739), but the code immediately after uses `kwargs["cu_seq_lens_q"]` (the *unpadded* offsets, line 741) as the `nested_tensor_from_jagged` offsets into `is_masked`, not `cu_seq_lens_q_padded` — a direct contradiction between the stated intent and the implementation, given that `input_ids` is laid out by the padded offsets per the `_pad_sequences_to_be_divisible_by` collator path (collator.py:204-227).
Type: in-repo
Confidence: high

### bionemo-16
Oracle: `mapping` unconditionally includes `"layer_norm_2.weight": "decoder.layer_norm_weight"` (state_dict_convert.py:33); `amplify_hf.py:320-321` shows `layer_norm_2` is only constructed `if config.layer_norm_before_last_layer`. `apply_transforms`'s own error path (`state.py:323`, `raise ValueError(f"No matches found for source key: {source_key}")`) fires when the mapped source key is absent.
Type: in-repo
Confidence: high

### bionemo-17
Oracle: `_send_data_to_cp_tp_ranks` (collator.py:571-582) only catches `StopIteration` from `next(self._iterator)`; any other exception propagates out before rank 0 reaches `_scatter_batch_to_cp_tp_ranks`. `torch.distributed.scatter_object_list` is a collective operation that blocks until every rank in the process group participates — that contract (not documented in this repo) is what turns rank 0's early exit into the other ranks hanging until the process-group timeout.
Type: known-external
Confidence: high

### bionemo-18
Oracle: `__iter__` (collator.py:500-504) executes `self._iterator = iter(self.dataloader)` *before* `self.close()` (which joins the previous prefetch thread). If the old thread's `_do_one_prefetch` hasn't yet reached `next(self._iterator)`, it now runs against the newly-assigned iterator, and its result is subsequently overwritten by the freshly-kicked prefetch started right after `close()` returns — self-evident ordering bug from the code.
Type: in-repo
Confidence: high

### bionemo-19
Oracle: `AMPLIFYForMaskedLM.__init__`'s `else` branch (amplify_te.py:298-301, the `layer_norm_before_last_layer=False` case) builds `transformer_engine.pytorch.Linear(hidden_size, config.vocab_size, ...)`, i.e. unpadded `vocab_size`; the converter's `_pad_decoder_weights`/`_pad_bias` (state_dict_convert.py:94-117) unconditionally pad to `config.padded_vocab_size`, so `apply_transforms` compares a `(vocab_size, ...)` target parameter against a `(padded_vocab_size, ...)` transformed tensor and raises a shape mismatch.
Type: in-repo
Confidence: high

### bionemo-20
Oracle: The sibling padding path `_pt_pad_to_multiple_of` (collator.py:915-922) explicitly pads both `attention_mask` and `position_ids` alongside `input_ids`; `_pad_sequences_to_be_divisible_by` (collator.py:204-227) only re-pads `input_ids`/`labels` via `pad_thd_sequences_for_cp` and never touches `position_ids`, leaving it at its original unpadded layout while `input_ids` grows.
Type: in-repo
Confidence: high

### bionemo-21
Oracle: `self.config.layer_precision = ["fp8"] * self.config.num_hidden_layers` (modeling_esm_te.py:186) mutates the model's own config object in place; the config docstring states `layer_precision: ... None (the default) means no quantization is configured` — after this mutation and a `save_pretrained`, a fresh `from_pretrained` load with no recipe will see a populated `layer_precision` list (contradicting "no quantization configured" as the loader's actual intent) and run FP8 autocast with TE's default recipe, with only a runtime warning as a trace of the substitution.
Type: in-repo
Confidence: medium

### bionemo-22
Oracle: `DataCollatorForContextParallel.__call__` reads `batch.get("cu_seq_lens_q_padded", None)` (collator.py:417, comment: "This will be None for BSHD format") and passes it to `_split_batch_by_cp_rank`, which returns immediately without touching that value when `cp_world_size <= 1` (collator.py:960-961); back in `__call__`, line 433 unconditionally does `batch_shard["cu_seq_lens_q_padded"][1:] - ...`, a plain dict-subscript (not `.get`) that raises `KeyError` if the wrapped collator never produced that key.
Type: implicit
Confidence: high

### bionemo-23
Oracle: `AMPLIFY.forward` (amplify_te.py:245) only converts the mask when `attention_mask.dtype is torch.int64`; TE's documented mask convention (used consistently elsewhere in this same function/file, comment: `"TE expects a boolean attention mask, where 'True' indicates a token to be masked"`) requires True=masked. A bool/int32/float 1=attend mask skips the inversion and is passed through with the opposite polarity.
Type: in-repo
Confidence: high

### bionemo-24
Oracle: `DataCollatorForContextParallel.__call__` shards only `input_ids`/`labels` per CP rank (collator.py:414-425: `batch_shard = dict(batch); batch_shard["input_ids"] = input_ids_sharded`), while `cu_seq_lens_q`/`cu_seq_lens_k` are copied unchanged from the unsharded `batch`; `_apply_token_dropout_thd` (modeling_esm_te.py:734-744) then uses those unsharded, global offsets to index into the local (sharded) `input_ids`/`is_masked` tensor via `nested_tensor_from_jagged`, which will index past the local buffer's length.
Type: in-repo
Confidence: medium

### bionemo-25
Oracle: The sibling function `split_qkv` in the same class (state.py:509-518, docstring "export layer linear_qkv to HF {q|k|v}_proj") reads `ctx.target.config.num_key_value_heads` (HF-style attribute, on the HF-side `ctx.target`); `split_qkv_bias`, documented identically ("export layer linear_qkv bias to HF {q|k|v} bias", state.py:544-550), instead reads `ctx.source.config.num_query_groups`/`kv_channels` (Megatron-style attribute names, on the wrong side of the ctx). `NVEsmConfig`/HF `EsmConfig` has no `num_query_groups`/`kv_channels` attributes, so calling it with such a config raises `AttributeError`.
Type: in-repo
Confidence: high

### bionemo-26
Oracle: Same sibling comparison as bionemo-20: `_pt_pad_to_multiple_of` (collator.py:915-917) pads `attention_mask` alongside `input_ids`; `_pad_sequences_to_be_divisible_by` (collator.py:204-227) replaces `input_ids`/`labels` with per-sequence-padded tensors from `pad_thd_sequences_for_cp` but the `attention_mask` produced earlier by `_pt_flatten_collate` (line 721-724) is never touched, leaving it shorter than the now-padded `input_ids`.
Type: in-repo
Confidence: high

### bionemo-27
Oracle: `convert_esm_hf_to_te` (convert.py:63) calls `NVEsmConfig(**model_hf.config.to_dict(), **config_kwargs)`; `model_hf.config.to_dict()` already contains `token_dropout` (a genuine `EsmConfig`/`NVEsmConfig` field, used at modeling_esm_te.py:695) and any other real config field, so passing that same key in `config_kwargs` collides in the double-unpack and Python raises `TypeError: got multiple values for keyword argument`. `convert_esm_te_to_hf` and `convert_amplify_hf_to_te` build their target configs the same way (`state_dict_convert.py:47`). Self-evident from Python's keyword-argument semantics.
Type: implicit
Confidence: high

### bionemo-28
Oracle: `wildcard_matches[i].sort(key=lambda x: int(x) if x.isdigit() else x)` (state.py:432) produces a key that's an `int` for digit-strings and a `str` otherwise; sorting a list whose keys are a mix of both raises `TypeError: '<' not supported between instances of 'str' and 'int'` in Python 3 the moment both a numeric and non-numeric match exist for the same wildcard (e.g. `model.0.weight` and `model.norm.weight`). Self-evident from Python's ordering rules.
Type: implicit
Confidence: high

### bionemo-29
Oracle: `amplify_hf.py:309-310` shows `layer_norm_1` is constructed `if config.layer_norm_after_embedding`, i.e. it's a real, sometimes-present parameter; the `mapping` dict in `state_dict_convert.py:27-34` has no `"layer_norm_1.weight"` entry at all, so `apply_transforms` never copies it into the TE model regardless of config, leaving that TE weight at its (empty-init) default with no error raised (no entry means no lookup, unlike bionemo-16's missing-key error case).
Type: in-repo
Confidence: high

### bionemo-30
Oracle: Same pattern as bionemo-14 but in the BSHD path: `src_lengths = attention_mask.sum(-1)` (modeling_esm_te.py:712) can be 0 for an all-zero mask row, making `mask_ratio_observed = n_masked_per_seq / src_lengths` (line 715) 0/0 = NaN, which then multiplies that row's embeddings. As with bionemo-14, the repo's own `assert torch.isfinite(loss)` tests (`tests/common/test_modeling_common.py`) establish that NaN propagation is a defect the project cares about, though there's no explicit guard or test here for the all-masked-row case specifically.
Type: in-repo
Confidence: medium

Hardest to classify: bionemo-01, bionemo-12, bionemo-14/30, bionemo-21, and bionemo-24. bionemo-01 and bionemo-12 depend on whether a code path is actually reachable in practice (dead/unused `compute_metrics`; an unusual `None`-valued-but-present kwarg) rather than on what's wrong once reached, which the code alone can't settle. bionemo-14/bionemo-30 (the NaN cases) don't crash, so they fall outside the brief's clean "implicit" bucket even though they're clearly unwanted; I anchored them to the repo's own `isfinite(loss)` test assertions as the closest in-repo oracle, which is a weaker link than a direct sibling-function contradiction. bionemo-21 required judging whether mutating a config object in place, then serializing it, counts as breaking a documented contract (the "None means no quantization" docstring) versus just being an unusual but intentional design choice. bionemo-24 required combining two files (collator sharding + model-side token dropout) to see that CP-sharded local tensors get paired with unsharded global offsets, which is inferential rather than a single quoted line proving the mismatch.
