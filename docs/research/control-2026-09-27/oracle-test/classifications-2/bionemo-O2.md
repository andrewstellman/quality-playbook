bionemo-01 | input | Needs the case of an evaluation that stops before a compute_result=True call; the module-level metric plus a reset only inside that branch looks fine until then.
bionemo-02 | line | Line 436 reads the max length from the unsharded `batch["input_ids"]` inside the per-shard loop instead of from `batch_shard`.
bionemo-03 | input | Needs a padded sequence length not divisible by 2*cp_world_size; the floor division at line 976 has no divisibility check and only drops tokens for such a value.
bionemo-04 | line | `torch.zeros(...)` with no dtype or device, then `torch.cat` with the source tensor (the `_pad_bias` sibling just below does pass both).
bionemo-05 | nearby | Needs the `att_bias`/`ffn_bias` fields in `AMPLIFYConfig`, in the same file, to see that the hard-coded `bias=False` ignores them.
bionemo-06 | line | The signature default of 64 at line 88 means the `padded_vocab_size or self.vocab_size` fallback at line 145 never fires unless `None` is passed.
bionemo-07 | nearby | Needs a comparison of `state_dict()` with the prefetch-ahead behaviour of `__next__`/`_kick_prefetch` in the same class.
bionemo-08 | nearby | Needs the sibling `LayerNormLinear` branch directly above, which passes `init_method`; the `Linear` branch does not.
bionemo-09 | line | `join(timeout=10)` followed by an unconditional `_prefetch_thread = None`, with no `is_alive()` check.
bionemo-10 | input | Needs a model run in fp32 or fp16 with a padding mask; the hard-coded `.to(torch.bfloat16)` looks fine for the usual bf16 run.
bionemo-11 | input | Needs a concrete trace where an overflowing sample fills the new batch exactly and the stream ends there; the overflow branch never rechecks for == max.
bionemo-12 | input | Needs the case where the key is present but its value is `None`; `"key" in kwargs` reads as a reasonable guard.
bionemo-13 | line | The `match` on `hidden_act` has no `case _`, so `self.ffn` can be left unset.
bionemo-14 | input | Needs a zero-length sequence (two equal consecutive `cu_seq_lens_q` values) to get 0/0.
bionemo-15 | nearby | Needs line 741 (offsets from unpadded `cu_seq_lens_q`) compared with lines 736/744 of the same function, which treat the buffer as laid out by `cu_seq_lens_q_padded`.
bionemo-16 | nearby | Needs the HF model definition, which creates `layer_norm_2` only when `layer_norm_before_last_layer` is set, against the unconditional mapping entry.
bionemo-17 | input | Needs a non-StopIteration exception on rank 0; the handler catches only StopIteration, so rank 0 skips the collective the other ranks wait in.
bionemo-18 | input | Needs a re-iteration while the old prefetch thread has not yet called `next()`; the swap-iterator-then-`close()` ordering only goes wrong in that interleaving.
bionemo-19 | trace | Needs the TE decoder built with `vocab_size` put side by side with the converter, which always pads decoder weight and bias to `padded_vocab_size`.
bionemo-20 | nearby | Needs to know from `_pt_flatten_collate` (same file) that `position_ids` is in the batch, and that `_pad_sequences_to_be_divisible_by` rewrites only `input_ids`/`labels`.
bionemo-21 | trace | Needs the config mutation at line 187 followed through `save_pretrained` and a later load without a recipe.
bionemo-22 | line | Line 417 treats `cu_seq_lens_q_padded` as optional via `.get(..., None)`, while line 433 in the same loop indexes it directly.
bionemo-23 | input | Needs a bool, int32 or float mask with the HF convention (1 = attend); the `dtype is torch.int64` gate looks deliberate until then.
bionemo-24 | trace | Needs the CP collator (shards `input_ids`, passes global `cu_seq_lens_q` through) followed into the model's THD token-dropout code.
bionemo-25 | nearby | Needs the sibling `split_qkv`/`merge_qkv` in the same file, which read `num_key_value_heads` from `ctx.target`; the Megatron-style helpers read `num_query_groups`/`kv_channels`, and `split_qkv_bias` reads from source.
bionemo-26 | nearby | Needs to know from `_pt_flatten_collate` (same file) that `attention_mask` is in the batch and is left unpadded while `input_ids`/`labels` are replaced.
bionemo-27 | line | `Config(**model.config.to_dict(), **config_kwargs)` raises on any duplicate key.
bionemo-28 | line | The sort key returns an int for digit strings and a str otherwise, so any mixed list cannot be compared.
bionemo-29 | nearby | Needs the models' conditional `layer_norm_1` (`layer_norm_after_embedding`) compared with a mapping that has no entry for it.
bionemo-30 | input | Needs a row whose `attention_mask` is all zeros, giving `src_lengths == 0`.
