### Description

`_pad_weights` creates its padding rows with a bare `torch.zeros(...)`, so they are always fp32 on CPU. For a bf16 source embedding the padded result is fp32, and for a CUDA source `torch.cat` gets tensors on different devices. This passes `dtype=` and `device=` from the source embedding, as `_pad_bias` in the same file and ESM2's `_pad_weights` already do.

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

- [ ] I have tested these changes locally: no GPU here. The new test's `cpu` case fails before the change and passes after, run outside the tree because `transformer_engine` needs CUDA. The `cuda` case is for CI.
- [ ] I have updated the documentation accordingly (not applicable)
- [x] I have added/updated tests as needed
- [ ] All existing tests pass successfully (needs a GPU; relying on CI)
