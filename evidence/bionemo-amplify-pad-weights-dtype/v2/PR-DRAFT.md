**Title:** amplify: keep dtype/device of padding rows in `_pad_weights`

### Description

`_pad_weights` in `models/amplify/src/amplify/state_dict_convert.py` builds its padding rows with `torch.zeros(num_padding_rows, source_embed.size(1))`, so the padding rows are fp32 on CPU whatever the source embedding's dtype and device. For a bf16 source, `torch.cat` returns an fp32 tensor. For a CUDA source, the CPU padding rows should make `torch.cat` fail with a device mismatch. I haven't run that case because I don't have a GPU.

This PR passes `dtype=source_embed.dtype, device=source_embed.device`, the same as `_pad_bias` in the same file and `_pad_weights` in `models/esm2/convert.py`.

What this means for a full conversion: `convert_amplify_hf_to_te` calls `apply_transforms` without `cast_dtype`, and `apply_transforms` then asserts that every parameter kept its original dtype (`models/amplify/src/amplify/state.py:238-243`). So converting a bf16 model most likely fails at that assertion rather than quietly producing fp32 embeddings. I haven't run the end-to-end conversion, which needs Transformer Engine and a GPU. That comes from reading the code. `export.py` isn't affected today because it converts the fp32 CPU model that `from_pretrained` loads by default.

The test goes in `tests/test_amplify_model.py` next to `test_convert_state_dict`. It pads a bf16 embedding and checks the dtype, the device, the copied rows and the zero rows. The `cuda` case is skipped when CUDA isn't available.

I found this with help from Claude (an AI assistant) and reviewed the change myself before opening the PR.

#### Usage

No interface change. The affected path is converting a checkpoint that isn't fp32 on CPU, for example (I have not run this snippet):

```python
import torch
from transformers import AutoModel

from amplify.state_dict_convert import convert_amplify_hf_to_te

model_hf = AutoModel.from_pretrained(
    "chandar-lab/AMPLIFY_120M", trust_remote_code=True, revision="d918a9e8", dtype=torch.bfloat16
)
model_te = convert_amplify_hf_to_te(model_hf)
```

### Type of changes

- [x] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Refactor
- [ ] Documentation update
- [ ] Other (please describe):

### CI Pipeline Configuration

No extra labels requested.

### Pre-submit Checklist

- [ ] I have tested these changes locally. I couldn't run the project's pytest here because `transformer_engine` needs CUDA. On CPU, I pulled `_pad_weights` and the new test out of the tree verbatim and ran them under pytest. The `cpu` case fails before the change (the result is `torch.float32`) and passes after it. The `cuda` case was skipped, so the device half has not been run.
- [ ] I have updated the documentation accordingly (not applicable, no docs cover this function)
- [x] I have added/updated tests as needed
- [ ] All existing tests pass successfully (not run locally, needs a GPU; relying on CI)
