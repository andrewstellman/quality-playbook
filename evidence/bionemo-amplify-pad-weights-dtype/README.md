# BioNeMo AMPLIFY `_pad_weights` — dtype/device dropped when padding

## Verdict: CONFIRMED (reachable via public API, not the repo's own default export path)

## Repo / pin
- Upstream: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
- Pinned HEAD at time of this run: `11701476b005ca7bc489df924a398b8f12453f0b` (committed 2026-09-18)
- Fresh `git clone --depth 1` performed 2026-09-27; HEAD matched the pin exactly (repo has not
  moved since the wave-2 triage scan).
- File: `models/amplify/src/amplify/state_dict_convert.py`, function `_pad_weights`, line 90
  (the `torch.zeros(...)` call inside the function body at lines 85-91).

## The bug
```python
def _pad_weights(ctx: io.TransformCTX, source_embed):
    """Pad the embedding layer to the new input dimension."""
    target_embedding_dimension = ctx.target.config.padded_vocab_size
    hf_embedding_dimension = source_embed.size(0)
    num_padding_rows = target_embedding_dimension - hf_embedding_dimension
    padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))   # <-- no dtype=/device=
    return torch.cat((source_embed, padding_rows), dim=0)
```
`torch.zeros` defaults to `dtype=torch.float32` on the CPU device. If `source_embed` is bf16
and/or on a CUDA device (a completely ordinary way to load a HF checkpoint for conversion —
`AutoModel.from_pretrained(..., dtype=torch.bfloat16)` then `.to("cuda")`), the padding rows are
float32/CPU. `torch.cat` on tensors with different dtypes upcasts silently (bf16 source is
silently promoted to fp32 in the concatenated result) or raises a device-mismatch `RuntimeError`
if the source is on CUDA and the zeros are on CPU.

The sibling function `models/esm2/convert.py:238-246` (`_pad_weights` for the ESM2 model) already
does this correctly:
```python
padding_rows = torch.zeros(
    num_padding_rows, source_embed.size(1), dtype=source_embed.dtype, device=source_embed.device
)
```
Same shape, same docstring, same call sites (`_pad_embeddings`, `_pad_decoder_weights`) — the
AMPLIFY copy is missing the two kwargs the ESM2 original has.

## Reachability (why this is CONFIRMED, not LATENT)
- `_pad_weights` is registered as a `state_transform` (`_pad_embeddings`, `_pad_decoder_weights`)
  and invoked by the module-level, user-facing `convert_amplify_hf_to_te(model_hf, **config_kwargs)`
  function — a general HF→TransformerEngine checkpoint conversion utility, not an internal helper.
- The repo's own `export.py::export_hf_checkpoint` calls `AutoModel.from_pretrained(...)` with no
  explicit `dtype=`, so it loads fp32/CPU by default and does **not** trip the bug — this is why
  the in-repo export script "works" today.
- However, any caller of `convert_amplify_hf_to_te` who loads `model_hf` with a non-default dtype
  or device (e.g. `dtype=torch.bfloat16` — the exact idiom `export.py` itself uses later, at
  line 108-110, to reload the *exported* checkpoint) hits the bug immediately. This is a standard,
  unremarkable way to use a HF `from_pretrained` call; nothing in the function's signature,
  docstring, or the module warns against it.
- Confirmed via `models/amplify/tests/test_amplify_model.py`: every GPU test in this file loads
  models in bf16 (`config.dtype = torch.bfloat16` fixture at `tests/conftest.py:40`,
  `model.to("cuda", dtype=torch.bfloat16)`) — i.e., bf16 is the model's *normal* runtime dtype
  throughout this test suite; it's only the specific `export_hf_checkpoint`/`test_convert_state_dict`
  code path that happens to use fp32 defaults today.

## Execution — HARNESS EXECUTION (not a live import)
`amplify.state_dict_convert` imports `amplify.amplify_te`, which does
`import transformer_engine.pytorch` at module level. `transformer_engine` requires a CUDA-capable
build environment and is not installable in this CPU-only, disk-constrained sandbox, so the real
module could not be imported and exercised directly.

Instead, `_pad_weights` was copied **verbatim** into a harness test
(`harness/harness_pad_weights.py`), with the file path and line range recorded in the harness's
own docstring:
- Buggy version: `models/amplify/src/amplify/state_dict_convert.py:85-91` (current main, unpatched)
- Reference version: `models/esm2/convert.py:238-246` (already-correct sibling)
- Fixed version: same function with `dtype=source_embed.dtype, device=source_embed.device` added

Ran with a bf16 CPU tensor (torch 2.14.0+cpu, no GPU needed — bf16 is a CPU-supported dtype in
PyTorch, so the dtype-drop is fully reproducible without CUDA):
- `red.log` — buggy version: output dtype comes back as `float32` when source was `bfloat16` →
  assertion failure (RED).
- `green.log` — fixed version and the ESM2 reference both preserve `bfloat16` → assertions pass
  (GREEN); included for cross-check that the fix produces byte-identical behavior to the sibling.

## Existing CPU-runnable unit tests
**None.** `models/amplify/tests/conftest.py` unconditionally imports `transformer_engine.pytorch`
and `from datasets import Dataset` at module level, so `pytest` cannot even *collect* any test in
that directory without those packages installed — confirmed directly:
```
$ PYTHONPATH=src python3 -m pytest tests/test_pad_weights_dtype_device.py -q
ImportError while loading conftest '.../models/amplify/tests/conftest.py'.
tests/conftest.py:18: in <module>
    from datasets import Dataset
E   ModuleNotFoundError: No module named 'datasets'
```
(`pytest_collection_blocked.log`). This blocks the new regression test added in the patch from
running here too — it will run under the project's own CI/Docker image, which has these
dependencies, but not in this sandbox. No pre-existing test in this module could be run on CPU
either, before or after the fix.

## Fix applied
`models/amplify/src/amplify/state_dict_convert.py:85-91`: add
`dtype=source_embed.dtype, device=source_embed.device` to the `torch.zeros(...)` call, matching
`models/esm2/convert.py:238-246` exactly. Added `models/amplify/tests/test_pad_weights_dtype_device.py`,
a regression test using a `MagicMock` ctx (same pattern as the existing
`tests/test_amplify_model.py::test_convert_state_dict`), asserting the padded output preserves
`source_embed.dtype` and `.device`.

## Disclosure search
GitHub REST search API (`api.github.com/search/issues`) via `web_fetch`, scoped to
`repo:NVIDIA-BioNeMo/bionemo-recipes`:
- `pad_weights` → 0 hits
- `dtype device padding` → too large to inspect fully in this session (87KB+ result, mostly
  unrelated PRs matching on common words); not usable as a clean duplicate check. Treat as
  **not conclusively checked** for this query.
No exact duplicate found for the `pad_weights` search. Not exhaustive (GitHub lexical search
misses paraphrased issues; the second query above was not readable in full).

## Contributing / DCO requirements
`CONTRIBUTING.md` and `.github/pull_request_template.md` were read in full. Neither mentions a
Developer Certificate of Origin, `Signed-off-by`, or a CLA app. The only PR-gating mechanism found
is `copy-pr-bot` (`.github/copy-pr-bot.yaml`), which controls whether CI is auto-triggered for
trusted vs. untrusted contributors — it is not a signature/DCO requirement. **No DCO/sign-off
requirement was found; the patch does not include a `Signed-off-by` trailer.** If NVIDIA's actual
PR process does require one (not evidenced in this repo's docs), Andrew should add it himself
before submitting — do not add it on his behalf without him confirming the identity/email it
should carry.

## Disk / environment notes
CPU-only PyTorch 2.14.0+cpu installed into `/tmp/venv-bionemo` from
`https://download.pytorch.org/whl/cpu`. No other model dependencies (`transformer_engine`,
`transformers`'s heavier extras, `accelerate`, `datasets`) were installed, per the disk budget
constraint (~2GB free, shared with other agents). This is why harness-execution (verbatim copy)
was used instead of a live import — see "Execution" above.
