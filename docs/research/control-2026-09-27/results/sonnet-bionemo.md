# Code Review: bionemo-recipes — AMPLIFY and ESM2 model code

Repo: bionemo (NVIDIA-BioNeMo/bionemo-recipes), pinned commit `11701476b005ca7bc489df924a398b8f12453f0b`
Scope: `models/amplify/src/amplify/`, `models/esm2/` (excluding tests)

## Defects found

### 1. `amplify_te.py`: attention-mask inversion only handles `torch.int64`, silently mishandles other dtypes

**File/line:** `models/amplify/src/amplify/amplify_te.py:245-247`

```python
if attention_mask is not None and attention_mask.dtype is torch.int64:
    # TE expects a boolean attention mask, where "True" indicates a token to be masked.
    attention_mask = ~attention_mask.to(bool)
```

The comment states the intended contract: incoming `attention_mask` uses the standard HF convention (1 = attend, 0 = pad), and TE needs the opposite (`True` = masked). The inversion is gated on `attention_mask.dtype is torch.int64`. If a caller passes an attention mask of any other dtype that still follows the 1=attend/0=pad convention — e.g. a `torch.bool` tensor (a very common thing to pass, since `attention_mask.bool()` is idiomatic), or an `int32` tensor (some tokenizer/dataset pipelines emit these) — the mask is passed to `transformer_engine.pytorch.TransformerLayer` **unmodified**, with the semantics silently inverted: positions the caller meant to attend to get masked out, and padding positions get attended to. This corrupts the forward pass without raising an error. Only `torch.int64` (which is what `transformers.AutoTokenizer(..., return_tensors="pt")` happens to produce) takes the correct path.

This is only exercised by tests through the standard tokenizer path (`conftest.py`'s `input_data` fixture uses `DataCollatorForLanguageModeling`, which yields `torch.int64` attention masks), so the bug in the non-int64 branch is untested.

**Severity:** medium (silent correctness bug for a plausible but non-default input dtype; no exception is raised, so it fails silently rather than loudly).

**Suggested fix:** Convert based on semantics, not dtype — e.g. always do `attention_mask = ~attention_mask.bool()` when `attention_mask.dtype != torch.bool` produces a truthy 1-for-attend tensor, or more simply just always run `attention_mask = ~attention_mask.to(torch.bool)` unconditionally (the current `int64`-only guard serves no purpose other than to skip the conversion for other dtypes, which is the actual bug).

---

### 2. `modeling_esm_te.py`: division by zero in token-dropout scaling for a fully-padded (empty) sequence

**File/lines:** `models/esm2/modeling_esm_te.py:712-717` (BSHD) and `models/esm2/modeling_esm_te.py:733-744` (THD)

```python
def _apply_token_dropout_bshd(self, embeddings, input_ids, attention_mask):
    mask_ratio_train = 0.15 * 0.8
    src_lengths = attention_mask.sum(-1) if attention_mask is not None else input_ids.shape[1]
    n_masked_per_seq = (input_ids == self.mask_token_id).sum(-1).float()
    mask_ratio_observed = n_masked_per_seq / src_lengths
    scale_factor = (1 - mask_ratio_train) / (1 - mask_ratio_observed)
    return (embeddings * scale_factor[:, None, None]).to(embeddings.dtype)
```

`src_lengths` is `attention_mask.sum(-1)`, the number of valid (non-padding) tokens per sequence. If any row in the batch is entirely padding (`attention_mask` all zeros for that row — e.g. a dummy row added to pad a batch to a fixed size across distributed ranks, or an empty input), `src_lengths` is `0` for that row, so `mask_ratio_observed = 0 / 0 = NaN`. `scale_factor` becomes `NaN`, and the corresponding row of `embeddings` becomes entirely `NaN`. Since this feeds into the shared transformer encoder and the loss is computed over the full batch, a single degenerate row silently poisons the whole batch's loss/gradients rather than raising an error.

The THD variant (`_apply_token_dropout_thd`, lines 719-745) has the analogous problem: `src_lengths = torch.diff(kwargs["cu_seq_lens_q"])`; a zero-length packed sequence (two equal consecutive values in `cu_seq_lens_q`) produces the same `0/0` NaN.

This is only called when `self.token_dropout` is true, which is the default for Facebook's ESM2 configs, so this path is live in normal use — it just requires an unusual but not impossible input (a fully-masked/empty sequence in the batch).

**Severity:** medium (silent NaN corruption on a plausible edge case; no exception).

**Suggested fix:** Guard the division, e.g. `mask_ratio_observed = n_masked_per_seq / src_lengths.clamp(min=1)` and additionally zero out (or otherwise neutralize) scale_factor for rows where `src_lengths == 0`, since those rows have no real content and their scale is meaningless.

---

### 3. `collator.py`: `ContextParallelDataLoaderWrapper.close()` can leave a stray thread running distributed collectives concurrently with a newly spawned one

**File/lines:** `models/esm2/collator.py` — `close()` (~line 495) and `__iter__` (~line 470)

```python
def __iter__(self):
    if self.cp_tp_rank == 0:
        self._iterator = iter(self.dataloader)
    self.close()
    ...
    self._kick_prefetch()
    return self

def close(self):
    """Stop the prefetch thread. Must be called before destroy_process_group()."""
    if self._prefetch_thread is not None:
        self._prefetch_thread.join(timeout=10)
        self._prefetch_thread = None
```

`close()` documents its job as "Stop the prefetch thread," but it uses a `10`-second `join(timeout=10)` and then unconditionally sets `self._prefetch_thread = None` regardless of whether the thread actually finished. The background thread (`_do_one_prefetch` → `_send_data_to_cp_tp_ranks`) performs `torch.distributed.scatter_object_list`, a collective operation. If that thread is still in-flight after 10 seconds (e.g. a rank momentarily lagging or the collective blocked), `close()` abandons it — the thread is still alive and will eventually call `scatter_object_list` — while `__iter__` immediately proceeds to call `_kick_prefetch()`, spawning a *new* thread that will also call `scatter_object_list` on the *same* process group. Two threads issuing the same collective concurrently on one process group is unsafe with most distributed backends (collectives must be issued in a single, consistently-ordered sequence per rank) and can hang or corrupt the data exchanged between ranks.

**Severity:** low-medium (requires the prefetch to actually exceed the hardcoded 10s timeout, which should be rare, but when it happens the failure mode is a distributed hang/corruption rather than a clean error).

**Suggested fix:** Don't silently proceed past a `join` timeout for a thread doing collective communication — either block indefinitely (removing the timeout so `close()` genuinely stops the thread before returning), or track whether the join actually succeeded and refuse to kick a new prefetch (raising instead) if the old thread is still alive.

---

## Lower-confidence observation (not counted as a defect above)

`amplify_hf.py:360` — `if attention_mask is not None and not torch.all(attention_mask == 0):` only skips the additive-mask construction when the *entire* attention_mask tensor (across the whole batch) is all zeros. It does not guard against a single row within the batch being entirely masked (all-zero for that one sequence), which would still produce a row that is `-inf` everywhere in the additive mask and yields `NaN` from `softmax`/`memory_efficient_attention` for that example, similar in spirit to defect #2. I list this separately because it is a narrower, harder-to-trigger version of the same underlying "empty sequence in the batch" edge case and I'm less confident it's reachable via the model's typical call sites within this scope.

## Files read

- `models/amplify/src/amplify/__init__.py`
- `models/amplify/src/amplify/amplify_hf.py`
- `models/amplify/src/amplify/amplify_te.py`
- `models/amplify/src/amplify/export.py`
- `models/amplify/src/amplify/metrics.py`
- `models/amplify/src/amplify/rmsnorm.py`
- `models/amplify/src/amplify/rotary.py`
- `models/amplify/src/amplify/state.py`
- `models/amplify/src/amplify/state_dict_convert.py`
- `models/amplify/tests/conftest.py` (context only, not reviewed for defects)
- `models/amplify/tests/test_amplify_model.py` (context only, not reviewed for defects)
- `models/esm2/collator.py`
- `models/esm2/convert.py`
- `models/esm2/export.py`
- `models/esm2/modeling_esm_te.py`
- `models/esm2/state.py`
- Diffed `models/amplify/src/amplify/state.py` against `models/esm2/state.py` (confirmed identical aside from the "copied file" header notice)
