### Description

The THD branch of `_split_batch_by_cp_rank` floor-divides each padded sequence length by `2 * cp_world_size` without checking that the division is exact, so the remainder tokens reach no rank. For example, with `cu_seqlens_padded = [0, 8, 18]` and `cp_world_size = 2`, positions 16 and 17 are in neither rank's shard. The BSHD branch already raises for this; this adds the same check to THD.

The shipped CP configs are unaffected: they pad to a multiple of `2 * cp_size`. This only fires when `pad_sequences_to_be_divisible_by` is overridden to a value that isn't, and such a run now fails on the first affected batch instead of dropping tokens. Like the BSHD check, it raises on CP rank 0 and the other ranks wait for the process-group timeout. A config-time check is an alternative if you'd prefer one.

The eight copies were regenerated with `ci/scripts/check_copied_files.py --fix`.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

#### Usage

No interface change.

### Type of changes

- [x] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Refactor
- [ ] Documentation update
- [ ] Other (please describe):

### CI Pipeline Configuration

No extra labels requested.

### Pre-submit Checklist

- [ ] I have tested these changes locally: no GPU here. The new non-divisible test fails before the change and passes after, run outside the tree because `collator.py` imports `transformer_engine`.
- [ ] I have updated the documentation accordingly (not applicable)
- [x] I have added/updated tests as needed
- [ ] All existing tests pass successfully (needs a GPU; relying on CI)
