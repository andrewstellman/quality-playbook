bionemo-01 | line | The module-level `perplexity` object is only reset inside the `if compute_result:` branch, and both are visible in the ~20 lines of `compute_metrics`.
bionemo-02 | line | Line 436 reads `batch["input_ids"]` (unsharded) while the surrounding loop builds `batch_shard`, which looks like a leftover variable.
bionemo-03 | input | The `// (2*cp)` slicing looks plausible until the reviewer tries a `cu_seqlens_padded` such as `[0,8,18]` that is not a multiple of `2*cp_world_size`.
bionemo-04 | line | `torch.zeros(n, d)` has no `dtype` or `device` argument on the cited line.
bionemo-05 | nearby | The reviewer must compare the hard-coded `bias=False` with the `att_bias` and `ffn_bias` config fields defined earlier in the same file (and with the HF block's use of those fields).
bionemo-06 | nearby | The reviewer must compare the signature default `64` with the `or self.vocab_size` fallback on line 145 and with the docstring that says it defaults to `vocab_size`.
bionemo-07 | trace | The reviewer must follow the prefetch thread across `__iter__`, `__next__` and `_kick_prefetch`, then relate that to what the wrapped dataloader's `state_dict` counts as consumed.
bionemo-08 | nearby | The reviewer must compare the `Linear` branch with the `LayerNormLinear` branch directly above it, which passes `init_method`.
bionemo-09 | nearby | The reviewer must read `close()` together with `__iter__` and reason about `join(timeout)` expiring while the thread is still running.
bionemo-10 | line | `.to(torch.bfloat16)` is hard-coded regardless of the model dtype.
bionemo-11 | input | The reviewer must construct a stream ending on a batch of exactly `max_tokens_per_batch` tokens that sits in `samples` under `drop_last=True`.
bionemo-12 | input | The reviewer must think of `cu_seq_lens_q_padded=None` being present as a key, which the `in kwargs` check treats as present.
bionemo-13 | line | The `match` statement has no default case, so `self.ffn` is never set for an unlisted activation.
bionemo-14 | input | The reviewer must supply a `cu_seq_lens_q` with a zero-length sequence to see the 0/0 division.
bionemo-15 | nearby | The comment says counting is done "in the padded batch", and line 736 computes padded lengths, but line 741 uses the unpadded offsets. The reviewer has to compare these lines and know how padded THD input is laid out.
bionemo-16 | trace | The reviewer must know from the model and config code that `layer_norm_before_last_layer=False` creates no `layer_norm_2`, then see that the converter's static mapping ignores that flag.
bionemo-17 | trace | The reviewer must reason about the scatter collective across ranks, where only rank 0 raises before calling it while the other ranks wait in it.
bionemo-18 | nearby | The reviewer must notice in `__iter__` that the iterator is replaced before `close()` joins the old thread, and reason about the thread interleaving.
bionemo-19 | trace | The reviewer must connect the `vocab_size` decoder in `amplify_te.py` with the converter's padding to `padded_vocab_size` in a different file.
bionemo-20 | nearby | The reviewer must compare what `_pad_sequences_to_be_divisible_by` updates with the other fields the collator returns, and see that `position_ids` is not updated.
bionemo-21 | trace | The reviewer must follow the mutated shared config through `save_pretrained` and a later load, where the recipe is absent.
bionemo-22 | nearby | The reviewer must connect the `.get(..., None)` on line 417 with the direct indexing on line 433, and know which collator paths omit the key.
bionemo-23 | input | The reviewer must try a bool or int32 mask, since the code only handles int64.
bionemo-24 | trace | The reviewer must follow the sharded `input_ids` from the collator, which still carries the global `cu_seq_lens_q`, into the embedding module in another file.
bionemo-25 | nearby | The reviewer must compare these helpers with `split_qkv` and `merge_qkv`, which read `num_key_value_heads` and use `ctx.target`, and with the HF config attributes.
bionemo-26 | nearby | The reviewer must compare the padding function's updates with the `attention_mask` produced by `_pt_flatten_collate` elsewhere in the file.
bionemo-27 | line | `NVEsmConfig(**config_dict, **config_kwargs)` visibly duplicates keyword arguments on overlap.
bionemo-28 | line | The sort key visibly returns an int for digit strings and a str otherwise, so mixed keys cannot be compared.
bionemo-29 | trace | The reviewer must know that the model builds `layer_norm_1` under `layer_norm_after_embedding` and that the converter's mapping has no entry for it.
bionemo-30 | input | The reviewer must think of a row whose attention mask is all zeros to see the 0/0 division.
