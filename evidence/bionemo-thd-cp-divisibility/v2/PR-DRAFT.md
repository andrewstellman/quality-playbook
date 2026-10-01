**Title:** collator: reject THD CP shards with non-divisible padded lengths

### Description

In the THD branch of `_split_batch_by_cp_rank` (`models/esm2/collator.py`), each sequence's slice size comes from floor-dividing its padded length by `2 * cp_world_size`, with no check that the division is exact. If a padded length isn't a multiple, the remainder tokens of that sequence never reach any CP rank's shard. For example, with `cu_seqlens_padded = [0, 8, 18]` and `cp_world_size = 2`, positions 16 and 17 are missing from both ranks' shards. The BSHD branch already raises a `ValueError` for the same condition. This PR adds the equivalent check to the THD branch:

```
ValueError: Padded sequence length(s) [10] must be divisible by 4 (2 * cp_world_size) for THD context parallelism; set pad_sequences_to_be_divisible_by to a multiple of 4
```

The message shows at most five of the bad lengths, followed by "(and N more)".

Scope:
- I only tested the collator. I didn't check whether Transformer Engine's THD attention would later fail on the mismatch between the sharded tokens and the unsharded `cu_seq_lens_q_padded`. Today's behaviour could be a later, less clear error rather than training on fewer tokens.
- The shipped configs are safe. The CP recipes (esm2, llama3, opengenome2) derive `pad_sequences_to_be_divisible_by = 2 * cp_size` when it's unset. `recipes/esm2_native_te/hydra_config/L0_sanity_cp.yaml` sets 16 with `cp_size: 2`, and 16 is divisible by 4. The only other config that sets the value, `recipes/mixtral_native_te/hydra_config/L1_8x7B_B200.yaml` (32), doesn't use CP. This check is for users who set `pad_sequences_to_be_divisible_by` themselves to a value that isn't a multiple of `2 * cp_size`.
- Behaviour change: a config that drops remainder tokens today will now fail with this error on the first batch that contains an affected length.
- Failure mode under CP: the collator runs on CP rank 0 inside `ContextParallelDataLoaderWrapper`. When it raises, the other CP ranks wait in the scatter until the process-group timeout. The existing BSHD check behaves the same way. I haven't run this multi-rank; it comes from reading the code.
- Alternative: check `pad_sequences_to_be_divisible_by % (2 * cp_size) == 0` once where the dataloader is configured (for example next to the default in `recipes/esm2_native_te/dataset.py`). Every rank would then fail together at startup. The per-batch check here also covers callers that use the collator directly. I'm happy to switch to the config-time check or add it alongside this one if you prefer.

`models/esm2/collator.py` is the source file. The eight copies were regenerated with `python ci/scripts/check_copied_files.py --fix`, and `python ci/scripts/check_copied_files.py` passes. Two tests are added to `models/esm2/tests/test_collator_context_parallel.py`. One checks that a non-divisible length raises. The other checks that divisible lengths still give every token to exactly one rank.

I found this with help from Claude (an AI assistant) and reviewed the change myself before opening the PR.

#### Usage

No interface change. A run with, say, `cp_size: 3` and `dataset.pad_sequences_to_be_divisible_by: 16` now raises the error above on a batch that contains a padded length that isn't a multiple of 6, where before it dropped the remainder. A direct call:

```python
import torch
from collator import _split_batch_by_cp_rank

_split_batch_by_cp_rank(
    cu_seqlens_padded=torch.tensor([0, 8, 18], dtype=torch.int32),
    input_ids_padded=torch.arange(18).unsqueeze(0),
    labels_padded=torch.arange(18).unsqueeze(0),
    qvk_format="thd",
    cp_rank=0,
    cp_world_size=2,
)  # ValueError: Padded sequence length(s) [10] must be divisible by 4 ...
```

### Type of changes

- [x] Bug fix (non-breaking change which fixes an issue). See the behaviour-change note above.
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Refactor
- [ ] Documentation update
- [ ] Other (please describe):

### CI Pipeline Configuration

No extra labels requested.

### Pre-submit Checklist

- [ ] I have tested these changes locally. I couldn't run the project's pytest here because `collator.py` imports `transformer_engine` and `nvtx`, which need CUDA. On CPU, I pulled `_split_batch_by_cp_rank` and its helpers, the two new tests and the four existing BSHD split tests out of the tree verbatim and ran them under pytest. The non-divisible test fails before the change ("DID NOT RAISE") and passes after it. The other five tests pass both before and after.
- [ ] I have updated the documentation accordingly (not applicable)
- [x] I have added/updated tests as needed
- [ ] All existing tests pass successfully (not run locally, needs a GPU; relying on CI)
