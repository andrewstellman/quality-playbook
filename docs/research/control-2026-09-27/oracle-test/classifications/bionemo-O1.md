# bionemo, classifier O1 (Claude Opus), blind

### bionemo-01
Oracle: Nothing in the repo says what `compute_metrics` should do when an evaluation is cut short. The function's own comment (metrics.py:59) is "TODO (peter): Is this method even used?", and no caller in the repo uses the amplify version. The stale state only matters under HF Trainer's `batch_eval_metrics` contract, and I would have to check that contract to be sure how an aborted eval is handled.
Type: fetch-external
Confidence: low

### bionemo-02
Oracle: I can't name one. For THD, the same function computes `max_length` from the global, unsharded `cu_seq_lens_q_padded` (collator.py:433), so using the global length for BSHD matches that. As far as I know, Transformer Engine expects global max_seqlen under context parallelism. I'd have to check TE to confirm, but I see no evidence the value is wrong.
Type: none
Confidence: low

### bionemo-03
Oracle: The function silently drops tokens when a sequence length isn't divisible by `2*cp_world_size`. Transformer Engine's context-parallel load balancing requires each sequence to be padded to a multiple of 2×cp_size, and the TODO at collator.py:928 says this function stands in for TE's. The fault is a missing precondition check: invalid input doesn't raise, it just loses data.
Type: known-external
Confidence: medium

### bionemo-04
Oracle: The parallel ESM-2 implementation pads with `torch.zeros(..., dtype=source_embed.dtype, device=source_embed.device)` (models/esm2/convert.py:243-244). In the same file, `_pad_bias` (state_dict_convert.py:113-114) passes `dtype=source_bias.dtype, device=source_bias.device`. The `apply_transforms` dtype assert (state.py:241-243) then raises.
Type: in-repo
Confidence: high

### bionemo-05
Oracle: The HF reference `EncoderBlock` builds q/k/v/wo with `bias=config.att_bias` and the FFN with `bias=config.ffn_bias` (amplify_hf.py:125-188). The TE layer hardcodes `bias=False` (amplify_te.py:190) and ignores both config flags. The released default is False, so the bug is latent.
Type: in-repo
Confidence: medium

### bionemo-06
Oracle: The docstring at modeling_esm_te.py:119-120 says `padded_vocab_size` "If not provided, defaults to vocab_size", but the signature default is 64. The export scripts pass `padded_vocab_size=None` explicitly (esm2/export.py:78) to get the documented behaviour, which suggests the authors know the default doesn't do it.
Type: in-repo
Confidence: medium

### bionemo-07
Oracle: A resumable dataloader's `state_dict()` should let you resume right after the last batch handed to the caller (the torchdata StatefulDataLoader contract). Because of the prefetch, the wrapper reports state one batch ahead, so on resume a batch is skipped. No in-repo test covers wrapper resume.
Type: known-external
Confidence: medium

### bionemo-08
Oracle: The `LayerNormLinear` branch passes a uniform ±`decoder_init_range` `init_method` (amplify_te.py:293-295). `_init_weights` (amplify_te.py:121-127) and the HF reference (amplify_hf.py:284-288) both init decoders that way, but the `Linear` branch doesn't. Whether `_init_weights` still reaches this module through `post_init`/`from_pretrained` isn't clear from the code.
Type: in-repo
Confidence: low

### bionemo-09
Oracle: `close()`'s docstring says "Stop the prefetch thread", but after a 10 s timeout it forgets the thread without stopping it. Two threads then issue collectives on one process group, which can hang or mismatch the collectives.
Type: implicit
Confidence: low

### bionemo-10
Oracle: `torch.nn.functional.scaled_dot_product_attention` requires `attn_mask` to be bool or the same dtype as the query, and xformers `memory_efficient_attention` rejects a mismatched `attn_bias` dtype. Casting unconditionally to bf16 breaks fp32/fp16 models. The in-repo tests only run bf16 (tests/test_amplify_model.py:75-80), which is why they wouldn't catch this.
Type: known-external
Confidence: medium

### bionemo-11
Oracle: The field docstring for `drop_last` (collator.py:238-239) says "Whether to drop the last batch if it's less than max_length". A carried-over batch of exactly `max_tokens_per_batch` tokens is full, yet it's dropped because the `==` check at line 295 isn't repeated after line 306 resets `current_length`.
Type: in-repo
Confidence: high

### bionemo-12
Oracle: `torch.diff(None)` raises a TypeError. Elsewhere the encoder treats a None value as absent (`kwargs.get("cu_seq_lens_q_padded", None)` at modeling_esm_te.py:285), so `in kwargs` is an inconsistent check. I found no in-repo caller that passes an explicit None.
Type: implicit
Confidence: low

### bionemo-13
Oracle: With an unsupported `hidden_act`, `self.ffn` is never set and the first forward raises AttributeError (amplify_hf.py:148-189, no `case _`). The config should reject the value at construction instead.
Type: implicit
Confidence: medium

### bionemo-14
Oracle: 0/0 gives NaN, but I can't point to anything saying zero-length sequences are valid input to this path. NaN is a numeric fault, not a crash. The formula matches the upstream ESM token-dropout formula.
Type: none
Confidence: low

### bionemo-15
Oracle: The comment at modeling_esm_te.py:739 says "We need to find the number of masked tokens in each sequence in the padded batch". Line 744 lays the scale factors out by `src_lengths_padded`, but line 741 slices the padded `input_ids` with the unpadded `cu_seq_lens_q` offsets, so each window after the first is misaligned.
Type: in-repo
Confidence: high

### bionemo-16
Oracle: The HF reference only creates `layer_norm_2` when `layer_norm_before_last_layer` is true (amplify_hf.py:320-325), and the TE model uses the same condition (amplify_te.py:286). The converter's unconditional mapping (state_dict_convert.py:33) therefore raises "No matches found for source key" (state.py:323). The config flag is documented, so it should be convertible.
Type: in-repo
Confidence: medium

### bionemo-17
Oracle: The comment at collator.py:581-582 says errors must be propagated "on all the CP ranks". That's done for StopIteration by scattering it, but any other exception is raised on rank 0 alone, so the peer ranks hang in `scatter_object_list`.
Type: implicit
Confidence: medium

### bionemo-18
Oracle: A dataloader wrapper should return every batch its iterator produces. Reassigning `self._iterator` before `close()` joins the old thread (collator.py:503-504) lets that thread consume the new iterator's first batch, which is then overwritten. Nothing in the repo states the no-loss requirement explicitly; it follows from the iterator contract.
Type: known-external
Confidence: low

### bionemo-19
Oracle: `forward` slices logits to `vocab_size` only when `padded_vocab_size != vocab_size` (amplify_te.py:345-346), which assumes the decoder outputs `padded_vocab_size`. The `LayerNormLinear` branch does that; the `Linear` branch (line 300) uses `vocab_size`, while the converter pads to `padded_vocab_size`. As a result, `apply_transforms` raises "Shape mismatch" (state.py:178).
Type: in-repo
Confidence: high

### bionemo-20
Oracle: The sibling padding path `_pt_pad_to_multiple_of` extends `position_ids` (and `attention_mask`) whenever it pads (collator.py:915-923). `_pad_sequences_to_be_divisible_by` (204-227) replaces `input_ids` and `labels` but leaves `position_ids` stale.
Type: in-repo
Confidence: medium

### bionemo-21
Oracle: The config docstring (modeling_esm_te.py:126-127) says `layer_precision` None "means no quantization is configured", yet a runtime recipe silently writes FP8 into the saved config. But the same mutation is repeated in every model (llama3, qwen2/3, mixtral, codonfm), and forward warns explicitly, so it looks deliberate. I can't point to anything that says a saved checkpoint shouldn't record this.
Type: none
Confidence: low

### bionemo-22
Oracle: Line 433 indexes `batch_shard["cu_seq_lens_q_padded"]` directly after line 417 treated the key as optional with `.get(..., None)`. When the key is missing, the result is an uncaught KeyError.
Type: implicit
Confidence: medium

### bionemo-23
Oracle: The comment at amplify_te.py:246 says "TE expects a boolean attention mask, where 'True' indicates a token to be masked". The HF reference treats `mask == 1` as attend for any dtype (amplify_hf.py:361). A bool or int32 HF-style mask skips the conversion and ends up inverted.
Type: in-repo
Confidence: medium

### bionemo-24
Oracle: `DataCollatorForContextParallel` copies the unsharded batch, including the global `cu_seq_lens_q`, into every shard while replacing `input_ids` with the local shard (collator.py:424-425). `_apply_token_dropout_thd` then uses those offsets as jagged offsets into the local buffer (modeling_esm_te.py:741). The CP tests all force `token_dropout=False` (tests/test_cp_thd.py:187, 238), which suggests the combination doesn't work.
Type: in-repo
Confidence: medium

### bionemo-25
Oracle: The sibling helpers `split_qkv` and `merge_qkv` (state.py:510-541, 587-620) read HF-style `num_key_value_heads` and `hidden_size // num_attention_heads` from `ctx.target.config`, but these helpers read Megatron-only attributes (`num_query_groups`, `kv_channels`), and `split_qkv_bias` reads from `ctx.source`. Nothing in the repo calls them, so this is dead-code inconsistency rather than a live failure.
Type: in-repo
Confidence: low

### bionemo-26
Oracle: The sibling `_pt_pad_to_multiple_of` extends `attention_mask` when padding (collator.py:915-918), and the class docstring (lines 133-134) promises an `attention_mask` that marks the padding tokens. The per-sequence padding path leaves the mask shorter than `input_ids`. The THD model path and the CP collator (line 408) both discard `attention_mask`, which limits the impact.
Type: in-repo
Confidence: low

### bionemo-27
Oracle: Python raises `TypeError: got multiple values for keyword argument` when the same key comes from both `**dict` and `**kwargs`. The docstring says `config_kwargs` are "Additional configuration kwargs to be passed to NVEsmConfig", so overriding an existing key such as `token_dropout` is a natural use, and it crashes. The tests override `token_dropout` through `from_pretrained` instead (test_cp_thd.py:187).
Type: implicit
Confidence: medium

### bionemo-28
Oracle: In Python 3, comparing an int sort key with a str sort key raises TypeError. Every mapping in the repo uses `*` only over numeric layer indices, so the crash isn't reachable with the current mappings.
Type: implicit
Confidence: low

### bionemo-29
Oracle: The TE model creates `layer_norm_1` when `layer_norm_after_embedding` is true (amplify_te.py:153-160), and so does the HF model (amplify_hf.py:309-314). The mapping has no entry for it. `apply_transforms` then fails with "Additional keys ... in target model but not in source model" (state.py:217-218) or the meta-tensor assert, so the documented config option can't be converted. In practice conversion raises rather than silently dropping the weight.
Type: in-repo
Confidence: medium

### bionemo-30
Oracle: 0/0 gives NaN, but a sequence row with no attended tokens is degenerate input. The formula is the same as upstream HF ESM token dropout, and nothing in the repo says all-zero rows must be supported.
Type: none
Confidence: low

**Hardest to classify:** Four were hard.
- **bionemo-02 and bionemo-03:** whether they are wrong depends on Transformer Engine's context-parallel conventions (global vs. per-shard max_seqlen; the 2×cp_size divisibility precondition). I know those only roughly, and the in-repo THD path suggests global values are intended, so for 02 I couldn't separate a real bug from a correct convention without reading TE.
- **bionemo-21:** it is a real config-persistence side effect that contradicts the docstring. But the identical pattern appears in six model files with an explicit warning, which reads as a deliberate design choice, so "none" felt more honest than "in-repo".
- **bionemo-18 and bionemo-09:** both are race-condition findings where the harm (a lost batch, concurrent collectives) is clear in principle, but the only oracle is general iterator or collective-ordering contracts, not anything written in the repo, and the races are narrow.

For the crash findings (13, 22, 27, 28), "implicit" was easy. How confident to be depended on whether a real caller can reach the crash, and for 28 none can.
