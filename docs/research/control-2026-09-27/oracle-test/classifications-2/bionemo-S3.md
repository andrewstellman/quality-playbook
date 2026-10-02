bionemo-01 | input | The reviewer has to picture an evaluation that stops before `compute_result=True`, then run a second evaluation against the leftover module-level `Perplexity` state.
bionemo-02 | nearby | The reviewer has to compare line 436, which reads unsharded `batch["input_ids"]`, with the per-shard `batch_shard` built a few lines above it.
bionemo-03 | input | The reviewer has to plug in concrete `cu_seqlens_padded` values and a cp size, because the `// (2*cp)` slicing only loses tokens when padded lengths aren't divisible by 2*cp.
bionemo-04 | nearby | The reviewer has to notice that the sibling `_pad_bias` passes `dtype` and `device` while `_pad_weights` builds `torch.zeros` without them, then think of a bf16 or CUDA source model.
bionemo-05 | nearby | The reviewer has to compare the hard-coded `bias=False` here with `att_bias`/`ffn_bias` in the HF `EncoderBlock` and the config.
bionemo-06 | nearby | The reviewer has to read the docstring ("defaults to vocab_size if not provided") and see that the signature default of 64 makes the `or self.vocab_size` fallback effectively dead.
bionemo-07 | trace | The reviewer has to follow the prefetch thread's read-ahead against the wrapped dataloader's `state_dict` and a later `load_state_dict` resume.
bionemo-08 | nearby | The reviewer has to compare the two decoder branches and see that only the `LayerNormLinear` branch passes `init_method`.
bionemo-09 | input | The reviewer has to picture the prefetch thread outliving `join(timeout=10)` and `__iter__` then starting a second thread.
bionemo-10 | line | A hard-coded `.to(torch.bfloat16)` on the mask, regardless of model dtype, looks wrong on inspection.
bionemo-11 | input | The reviewer has to try the boundary case where a held sample exactly fills `max_tokens_per_batch` at end of stream with `drop_last=True`.
bionemo-12 | nearby | The reviewer has to compare `"cu_seq_lens_q_padded" in kwargs` with the `kwargs.get(...) is not None` style used in `forward`, then think of a key present with value None.
bionemo-13 | line | The `match` on `hidden_act` has no default case, so `self.ffn` can be left unset, which is visible from the cited lines alone.
bionemo-14 | input | The reviewer has to try a zero-length sequence (equal consecutive `cu_seq_lens_q` values) to see the 0/0.
bionemo-15 | nearby | The reviewer has to notice that line 741 slices by unpadded `cu_seq_lens_q` while the comment and the `input_ids` layout are padded, and compare with the padded lengths used at line 744.
bionemo-16 | nearby | The reviewer has to compare the unconditional `layer_norm_2` mapping with the conditional `layer_norm_before_last_layer` branch in the model constructors.
bionemo-17 | trace | The reviewer has to reason about the collective `scatter_object_list` across ranks, where one rank raises before the call and the others block.
bionemo-18 | input | The reviewer has to construct a race where the old prefetch thread grabs a batch from the new iterator before `close()` joins it.
bionemo-19 | trace | The reviewer has to connect `AMPLIFYForMaskedLM`'s `vocab_size` decoder in `amplify_te.py` with the converter's padding to `padded_vocab_size` in `state_dict_convert.py`.
bionemo-20 | nearby | The reviewer has to notice that only `input_ids` and `labels` are padded in this function and compare with what else the flattening collator returns (`position_ids`).
bionemo-21 | trace | The reviewer has to follow the config mutation through `save_pretrained`, config.json and a later load without a recipe.
bionemo-22 | nearby | The reviewer has to compare the `.get(..., None)` at 417 with the direct indexing at 433 and think of a collator that produces no padded cu_seqlens.
bionemo-23 | input | The reviewer has to try a bool or int32 mask, since the `int64`-only condition looks intentional and is only wrong for those inputs.
bionemo-24 | trace | The reviewer has to connect the CP collator's sharded `input_ids` and global `cu_seq_lens_q` with the token-dropout offsets in the model.
bionemo-25 | trace | The reviewer has to see that the NeMo-style `config.num_query_groups` and `kv_channels` don't exist on the HF configs actually passed in, and compare against the `split_qkv` variant, across callers.
bionemo-26 | nearby | The reviewer has to compare the padded `input_ids`/`labels` with the `attention_mask` from `_pt_flatten_collate` that this function leaves untouched.
bionemo-27 | input | The reviewer has to try a `config_kwargs` key that is already in `to_dict()`, since the double-splat only fails on overlap.
bionemo-28 | input | The reviewer has to try a mixed numeric and non-numeric wildcard match, because the sort key returns int for some and str for others.
bionemo-29 | nearby | The reviewer has to compare the mapping against the `layer_norm_after_embedding` branch in the model, which builds `layer_norm_1`.
bionemo-30 | input | The reviewer has to try an all-zero attention-mask row to see the 0/0.
