bionemo-01 | input | Reviewer has to imagine an evaluation that stops before a compute_result=True call; normally every eval ends with one, so the conditional reset of the module-level Perplexity looks fine.
bionemo-02 | line | Line 436 reads the unsharded `batch["input_ids"]` where the THD branch two lines up uses `batch_shard`.
bionemo-03 | input | Reviewer has to try a padded sequence length not divisible by 2*cp_world_size (e.g. 10 with cp=2) to see the floor division silently drop tokens.
bionemo-04 | line | `torch.zeros(...)` with no dtype or device, then concatenated onto an arbitrary source tensor, is wrong on sight.
bionemo-05 | nearby | Reviewer has to know AMPLIFYConfig (same file) defines att_bias/ffn_bias to see that the hardcoded `bias=False` ignores them.
bionemo-06 | line | A non-None default of 64 on line 88 makes the `padded_vocab_size or self.vocab_size` fallback on line 145 dead code, visible from the two cited lines.
bionemo-07 | nearby | Reviewer has to compare state_dict() with __next__/_kick_prefetch in the same class to see the dataloader is already one batch ahead when its state is read.
bionemo-08 | nearby | Reviewer has to compare with the LayerNormLinear branch just above, which passes init_method; the cited else-branch alone looks fine.
bionemo-09 | nearby | Reviewer has to know join(timeout) can return with the thread still alive, then read __iter__ to see a second prefetch thread started beside it.
bionemo-10 | line | The hardcoded `.to(torch.bfloat16)` on the mask, ignoring the model dtype, is wrong on sight.
bionemo-11 | input | Reviewer has to walk a specific sequence (lengths 6 then 10, drop_last=True) to see an exactly-full batch held as `samples` and then dropped at stream end.
bionemo-12 | line | An `in kwargs` membership check followed by torch.diff on the value misses a present-but-None key.
bionemo-13 | input | Reviewer has to supply an activation outside swiglu/relu/gelu to notice the match has no default case and self.ffn is never set.
bionemo-14 | input | Reviewer has to imagine a zero-length sequence (repeated cu_seq_lens_q value) to get the 0/0 division.
bionemo-15 | nearby | Reviewer has to compare line 741 (unpadded offsets on the input_ids buffer) with line 744 and the comment at 739, which treat that buffer as laid out by the padded offsets.
bionemo-16 | trace | Reviewer has to check amplify_hf.py to learn layer_norm_2 exists only when layer_norm_before_last_layer is set; the mapping looks fine alone.
bionemo-17 | line | Only StopIteration is caught before a collective scatter, so any other exception on rank 0 skips the collective the other ranks are blocked in.
bionemo-18 | nearby | Reviewer has to see that the prefetch thread's _send_data_to_cp_tp_ranks reads self._iterator, which makes the assign-before-close ordering in __iter__ a race.
bionemo-19 | trace | Reviewer has to match the TE decoder's vocab_size output against the converter's padding to padded_vocab_size in state_dict_convert.py.
bionemo-20 | nearby | Reviewer has to compare with the sibling pad path (_pt_pad_to_multiple_of, ~l.920), which extends position_ids; this function doesn't.
bionemo-21 | trace | Reviewer has to follow the mutated config through save_pretrained into a later load with no recipe; the line alone only shows a local default.
bionemo-22 | line | Line 417 treats cu_seq_lens_q_padded as optional (`.get`) while line 433 indexes it unconditionally in the THD branch.
bionemo-23 | input | Reviewer has to consider a bool/int32/float mask to see the `is torch.int64` gate pass it through with inverted polarity.
bionemo-24 | trace | Reviewer has to follow the CP collator (which shards input_ids but leaves cu_seq_lens_q global) into the model's token-dropout THD path.
bionemo-25 | nearby | Reviewer has to compare with sibling split_qkv/merge_qkv, which read num_key_value_heads from ctx.target, to see the Megatron-style attribute names and the source/target swap.
bionemo-26 | nearby | Reviewer has to compare with the sibling pad path (_pt_pad_to_multiple_of), which extends attention_mask; this function replaces input_ids/labels but leaves the mask unpadded.
bionemo-27 | line | `Config(**source.to_dict(), **config_kwargs)` raises on any overlapping key, a known Python pitfall visible on the line.
bionemo-28 | line | The sort key lambda returns int or str depending on the value, so a mixed list cannot be ordered.
bionemo-29 | trace | Reviewer has to know both the HF and TE AMPLIFY models build layer_norm_1 under layer_norm_after_embedding to see the mapping omits it.
bionemo-30 | input | Reviewer has to imagine an all-padding row (attention_mask sum 0) to get the 0/0 division.
