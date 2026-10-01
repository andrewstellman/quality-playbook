# BioNeMo THD context-parallel sharding — silently drops remainder tokens on non-divisible padded lengths

## Verdict: CONFIRMED (reachable via an explicit user config override, not the safe auto-derived default)

## Repo / pin
- Upstream: https://github.com/NVIDIA-BioNeMo/bionemo-recipes
- Pinned HEAD at time of this run: `11701476b005ca7bc489df924a398b8f12453f0b` (committed 2026-09-18)
- Fresh `git clone --depth 1` performed 2026-09-27; HEAD matched the pin exactly.
- Canonical source file (per `ci/scripts/check_copied_files.py`): `models/esm2/collator.py`,
  function `_split_batch_by_cp_rank`, THD branch, line 976 (the floor division). Byte-identical
  enforced copies exist at `models/llama3/collator.py`, `models/mixtral/collator.py`,
  `models/qwen/collator.py`, `recipes/esm2_native_te/collator.py`, `recipes/esm2_peft_te/collator.py`,
  `recipes/llama3_native_te/collator.py`, `recipes/mixtral_native_te/collator.py`,
  `recipes/opengenome2_llama_native_te/collator.py`.

## The bug
```python
if qvk_format == "thd":
    if cu_seqlens_padded is None:
        raise ValueError("cu_seqlens_padded is required for THD format")

    total_slices_of_any_sequence = 2 * cp_world_size
    slice_sizes = (cu_seqlens_padded[1:] - cu_seqlens_padded[:-1]) // total_slices_of_any_sequence
    ...
```
`slice_sizes` is a plain floor division with no divisibility check. `_process_tensor_thd` then
selects exactly `2 * slice_size` tokens per sequence per rank; summed across all `cp_world_size`
ranks, that's `slice_size * total_slices_of_any_sequence` tokens — which equals the padded
sequence length only when it's exactly divisible. Any remainder is never selected by **any** rank:
silent, permanent data loss (not a crash, not a warning).

The BSHD branch (`_process_tensor_bshd`, lines 811-868) already guards the identical condition:
```python
if seq_len % total_chunks != 0:
    raise ValueError(
        f"Sequence length {seq_len} must be divisible by {total_chunks} "
        f"(2 * cp_world_size) for BSHD context parallelism"
    )
```
The THD branch has no equivalent.

## Reachability (why this is CONFIRMED, not LATENT)
Per-sequence padding is controlled by the `pad_sequences_to_be_divisible_by` config value, set in
`DataCollatorWithFlattening._pad_sequences_to_be_divisible_by` (`models/esm2/collator.py:204-224`),
which calls `pad_thd_sequences_for_cp` to pad each sequence to that value before building
`cu_seq_lens_q_padded`.

- **The safe path (default):** `recipes/esm2_native_te/dataset.py:255-258` (and the
  byte-identical llama3/opengenome2 recipe code) only auto-derives
  `pad_sequences_to_be_divisible_by = cp_mesh.size() * 2` when the caller leaves the Hydra config
  value unset (`null`). That value is, by construction, always a multiple of
  `2 * cp_world_size`, so the default recipe path never triggers the bug.
- **The unsafe path (reachable):** a caller who sets `dataset.pad_sequences_to_be_divisible_by`
  explicitly — a documented, supported override, not a misuse of the API — can pick any positive
  integer, e.g. for FP8/hardware-alignment reasons (8, 16, 32 are typical). Nothing checks that
  value against `2 * cp_world_size`. `recipes/esm2_native_te/hydra_config/L0_sanity_cp.yaml` does
  exactly this today (`cp_size: 2`, `pad_sequences_to_be_divisible_by: 16`) — safe only because
  16 happens to be divisible by 4; changing `cp_size` to 3 in that same config (or changing the
  hardcoded 16 to a value not divisible by `2 * cp_world_size`) would silently drop tokens with
  no error, no warning, on an active training path.
- This is exactly the kind of ordinary misconfiguration a divisibility guard exists to catch — the
  BSHD sibling already treats it as guard-worthy for the identical mathematical condition.

## Execution — HARNESS EXECUTION (not a live import)
`models/esm2/collator.py` unconditionally imports
`transformer_engine.pytorch.attention.dot_product_attention.context_parallel.pad_thd_sequences_for_cp`
and `nvtx` at module level; neither is installable in this CPU-only, disk-constrained sandbox
(transformer_engine requires a CUDA build; nvtx is a profiling marker package tied to the NVIDIA
toolkit). The real module could not be imported.

Instead, the pure-tensor sharding logic was copied **verbatim** into a harness
(`harness/harness_thd_sharding.py`), with file paths and line ranges recorded in its docstring:
- `_find_seq_dim`, `_process_tensor_thd`, `_process_tensor_bshd`: `models/esm2/collator.py:733-868`
  (unchanged, shared by buggy and fixed variants — not part of the bug)
- `_split_batch_by_cp_rank` (buggy): `models/esm2/collator.py:930-996`, current unpatched main.
  The only edit from the source is deleting the inert `@nvtx.annotate(...)` decorator line, noted
  in the harness docstring.
- `_split_batch_by_cp_rank` (fixed): same function with the BSHD-style divisibility guard added.

This is single-process/non-distributed: the function's own `cp_rank: int | None = None` parameter
(documented at `collator.py:955-956` as letting a caller "shard as if it were executing on that
rank without querying `torch.distributed.get_rank`") was used explicitly — no
`torch.distributed` process group, gloo or otherwise, was needed to exercise this code path.

**Test scenario:** two packed sequences, `cp_world_size=2` (`total_slices=4`). Sequence A padded
length 8 (divisible by 4, fine); sequence B padded length 10 (not divisible by 4 — buggy
`slice_size = 10 // 4 = 2`, so only `2 * 2 = 4` of B's 10 tokens are ever selected across both
ranks).
- `red.log` (buggy): `missing=[16, 17]` — the last two of sequence B's tokens are dropped by
  every CP rank. Assertion confirms this is non-empty (RED: the bug reproduces).
- `green.log` (fixed): raises `ValueError: Padded sequence length(s) [10] must be divisible by 4
  ...` instead of silently dropping tokens (GREEN), plus a no-regression check that a
  divisible-length case (8/8) still shards with zero tokens dropped.

## Existing CPU-runnable unit tests
**None.** `models/esm2/tests/conftest.py` unconditionally does `import transformer_engine.pytorch`
at module level — confirmed directly:
```
$ PYTHONPATH=. python3 -m pytest tests/test_cp_thd_divisibility_guard.py -q
ImportError while loading conftest '.../models/esm2/tests/conftest.py'.
tests/conftest.py:23: in <module>
    import transformer_engine.pytorch
E   ModuleNotFoundError: No module named 'transformer_engine'
```
(`pytest_collection_blocked.log`). `models/esm2/tests/test_cp_thd.py` itself additionally requires
2+ GPUs (`requires_multi_gpu`) and `torch.distributed.init_process_group(backend="nccl", ...)` —
not runnable on CPU under any circumstances, with or without transformer_engine installed. No
pre-existing test in this module could be run on CPU, before or after the fix.

## Fix applied
`models/esm2/collator.py` (canonical source): added a divisibility check inside the THD branch of
`_split_batch_by_cp_rank`, raising `ValueError` with the same message shape as the existing BSHD
guard, before computing `slice_sizes`. Ran `python ci/scripts/check_copied_files.py --fix` per
`CONTRIBUTING.md`'s instructions for copied files, which propagated the identical fix (byte-for-byte,
verified via `diff`) to all 8 enforced copies. Added
`models/esm2/tests/test_cp_thd_divisibility_guard.py` with two tests: rejects a non-divisible
padded length (`pytest.raises(ValueError, match="must be divisible by")`), and confirms no
regression on a divisible-length case.

## Disclosure search
GitHub REST search API (`api.github.com/search/issues`) via `web_fetch`, scoped to
`repo:NVIDIA-BioNeMo/bionemo-recipes`:
- `context parallel dropped tokens` → 5 hits, none is this bug (a new MFU/FLOPs feature PR, an
  Evo2 phage-generation recipe PR, an AI-code-review PR, a Mixtral recipe PR, a Qwen3 model PR —
  all unrelated).
- `cu_seqlens_padded divisible` → 4 hits, most relevantly **issue #1561** ("MFU tracking:
  `pad_to_multiple_of` path inflates useful-work Σ(Lᵢ²) by the mock-sequence contribution") — a
  real, related-but-distinct issue about MFU/FLOPs accounting in the *separate*
  `pad_to_multiple_of` code path (mock-sequence padding for FP8/FP4 alignment), explicitly not
  about `cu_seq_lens_q_padded`/CP sharding at all — its own text notes "`cu_seq_lens_q_padded`
  is reserved for TE's per-sequence CP zigzag-divisibility padding semantic," confirming the two
  code paths are understood by maintainers as separate. Not a duplicate of this finding.
No exact duplicate found for this specific silent-token-drop bug in either search. Not exhaustive.

## Contributing / DCO requirements
Same finding as the AMPLIFY package: `CONTRIBUTING.md` and `.github/pull_request_template.md`
mention no DCO/`Signed-off-by`/CLA requirement; only `copy-pr-bot` gates CI authorization. **No
`Signed-off-by` trailer was added.** Andrew should add one himself if NVIDIA's actual process
requires it.

## Disk / environment notes
Same CPU-only PyTorch 2.14.0+cpu venv as the AMPLIFY package (`/tmp/venv-bionemo`). No
`transformer_engine`, `nvtx`, `datasets`, or full `transformers` install attempted, per the disk
budget constraint.
