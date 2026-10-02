bionemo-01 | input | The reviewer has to run two evaluations, the first stopping before a `compute_result=True` call, to see the module-level `perplexity` carry state into the second.
bionemo-02 | nearby | The reviewer has to compare the bshd branch, which reads the unsharded `batch["input_ids"]`, with the sharded `batch_shard["input_ids"]` used a few lines above, and see that `max_length` ignores the shard.
bionemo-03 | input | The reviewer has to plug in a `cu_seqlens_padded` whose lengths aren't multiples of `2*cp_world_size` (here 10 with cp=2) to see the floor division drop tokens. The divisibility contract is set elsewhere, by the padding code.
bionemo-04 | nearby | The reviewer has to compare `_pad_weights`, whose `torch.zeros` has no dtype or device, with the sibling `_pad_bias`, which passes both.
bionemo-05 | nearby | The reviewer has to compare the hardcoded `bias=False` with the `att_bias`/`ffn_bias` config fields and the HF model's use of them.
bionemo-06 | nearby | The reviewer has to compare the signature default of 64 with the docstring ("defaults to vocab_size") and the `or self.vocab_size` fallback.
bionemo-07 | input | The reviewer has to picture calling `state_dict()` after batch k has been returned and the k+1 prefetch has already advanced the underlying loader, then resuming.
bionemo-08 | nearby | The reviewer has to compare the `Linear` branch with the `LayerNormLinear` branch, which passes `init_method`.
bionemo-09 | input | The reviewer has to imagine the `join(timeout=10)` expiring while the thread is still alive, then `__iter__` starting a second thread.
bionemo-10 | input | The reviewer has to run a non-bf16 model with a padding mask to see the hardcoded bf16 cast clash with the query dtype.
bionemo-11 | input | The reviewer has to walk a stream where the last held sample is exactly `max_tokens_per_batch` with `drop_last=True` to see it get dropped.
bionemo-12 | input | The reviewer has to pass the key with a `None` value to see that `in kwargs` differs from the `.get(...) is not None` checks used in `forward`.
bionemo-13 | line | The `match` has no `case _` branch, so an unlisted `hidden_act` leaves `self.ffn` unset, which is visible on inspection.
bionemo-14 | input | The reviewer has to supply a `cu_seq_lens_q` with a zero-length sequence to see the 0/0 division.
bionemo-15 | nearby | The reviewer has to notice that the comment says "padded batch" and `src_lengths_padded` is computed just above, yet the masked-token count uses the unpadded `cu_seq_lens_q` offsets.
bionemo-16 | nearby | The reviewer has to compare the unconditional `layer_norm_2` mapping with the model file, where the decoder has no layer norm when `layer_norm_before_last_layer=False`.
bionemo-17 | trace | The reviewer has to follow the collective `scatter_object_list` across ranks to see that rank 0 raising before the call leaves the other ranks blocked.
bionemo-18 | input | The reviewer has to reason about the thread interleaving between reassigning `self._iterator` and `close()` joining the old prefetch thread.
bionemo-19 | nearby | The reviewer has to compare the two decoder branches in the same `__init__` (`padded_vocab_size` vs `vocab_size`) against what the converter pads to.
bionemo-20 | nearby | The reviewer has to compare which batch keys `_pad_sequences_to_be_divisible_by` rewrites with the keys the flattening collator produces (`position_ids`).
bionemo-21 | input | The reviewer has to run construction with an `fp8_recipe`, then `save_pretrained`, then reload without a recipe to see the mutated shared config matter.
bionemo-22 | input | The reviewer has to supply a batch without `cu_seq_lens_q_padded` to see the `.get` default followed by direct indexing on line 433.
bionemo-23 | input | The reviewer has to pass a bool, int32 or float mask, and know TE's True-means-masked convention, to see the int64-only conversion miss it.
bionemo-24 | trace | The reviewer has to follow the CP collator's sharded `input_ids` and global `cu_seq_lens_q` into the model's token-dropout code in another file.
bionemo-25 | nearby | The reviewer has to compare these helpers with `split_qkv`, which uses HF-style attributes and reads the config from `ctx.target`, and with the config classes actually passed in.
bionemo-26 | nearby | The reviewer has to compare which tensors the padding function replaces with the `attention_mask` built in `_pt_flatten_collate`.
bionemo-27 | input | The reviewer has to pass a `config_kwargs` key that is already in `to_dict()` to see the duplicate-keyword `TypeError`.
bionemo-28 | line | The sort key returns `int` for some strings and `str` for others, so mixed keys can't compare, which is visible on inspection.
bionemo-29 | nearby | The reviewer has to compare the mapping with the model, which conditionally builds `layer_norm_1`, to see that no entry covers it.
bionemo-30 | input | The reviewer has to supply an all-zero attention mask row to see the 0/0 division.
