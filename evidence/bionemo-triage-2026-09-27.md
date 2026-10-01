# BioNeMo (NVIDIA-BioNeMo/bionemo-recipes) — wave-2 correctness finding validation, 2026-09-27

Task: validate two historical correctness findings from the wave-2 scout triage
(`docs/research/triage-2026-09-27/scout-candidates-wave2.md`, rank #4 and #5, sourced from
`repos/secbench2/sb2-05-bionemo/quality/BUGS.md` BUG-004 and BUG-005) against latest upstream
main, and prepare confirmed ones for PR. Both were re-derived from source in this pass, not
assumed from the historical report.

## Environment
- Shallow clone (`git clone --depth 1`) into `/tmp/bionemo-recipes`.
- HEAD SHA: `11701476b005ca7bc489df924a398b8f12453f0b`, committed 2026-09-18. Matches the SHA
  the wave-2 triage cited exactly — main has not moved in the 9 days since that scan.
- Clone performed 2026-09-27 (today), this session.
- CPU-only PyTorch (`torch==2.14.0+cpu`, from `https://download.pytorch.org/whl/cpu`) installed
  into a venv at `/tmp/venv-bionemo`. No GPU available. No other model dependencies
  (`transformer_engine`, `nvtx`, `datasets`, `accelerate`, full `transformers`) were installed —
  disk budget was ~3GB free at session start, shared with other agents; both modules under test
  unconditionally import `transformer_engine` (a CUDA-only package) at module level, so neither
  could be truly imported here regardless of disk headroom. See each finding's README for the
  harness-execution approach used instead.
- `CONTRIBUTING.md`, `.github/pull_request_template.md`, and `.github/copy-pr-bot.yaml` were read
  in full. **No DCO / `Signed-off-by` / CLA requirement found** for this repo — only
  `copy-pr-bot`, which gates automatic CI triggering for trusted vs. untrusted contributors, not a
  signature requirement. Neither patch includes a `Signed-off-by` trailer. If NVIDIA's actual
  process expects one (not evidenced in-repo), Andrew should add it himself before submitting.

## Verdicts

| # | Candidate | Verdict | File:line | Reachability |
|---|---|---|---|---|
| 1 | AMPLIFY `_pad_weights` drops source dtype/device when padding | **CONFIRMED** | `models/amplify/src/amplify/state_dict_convert.py:85-91` | Reachable via the public `convert_amplify_hf_to_te` conversion API whenever the caller loads the HF source model in a non-default dtype/device (e.g. bf16/CUDA) — an ordinary usage pattern, though the repo's own `export.py` script doesn't currently trigger it (loads fp32 by default). |
| 2 | THD context-parallel sharding silently drops remainder tokens on non-divisible padded lengths | **CONFIRMED** | `models/esm2/collator.py:976` (canonical source; 8 enforced byte-identical copies) | Reachable when a caller explicitly sets `pad_sequences_to_be_divisible_by` to a value not divisible by `2 * cp_world_size` — a supported config override (already used for FP8/hardware-alignment reasons in `recipes/esm2_native_te/hydra_config/L0_sanity_cp.yaml`), not just the safe auto-derived default (`cp_mesh.size() * 2`). |

Both were confirmed present byte-for-byte at the pinned HEAD, executed via a dependency-free
harness (verbatim-copied function bodies, file paths and line ranges recorded — real module
import was blocked by mandatory `transformer_engine`/`nvtx` imports requiring a GPU/CUDA
toolchain not available in this sandbox), red on the unpatched function, green after a minimal
fix mirroring each bug's already-correct sibling implementation. Neither module has any
pre-existing CPU-runnable unit test — both test suites' `conftest.py` unconditionally import
`transformer_engine.pytorch` (blocking collection entirely), and the ESM2 CP test additionally
requires 2+ GPUs and NCCL.

## Disclosure search
GitHub REST search API (`api.github.com/search/issues`) via `web_fetch`, scoped to
`repo:NVIDIA-BioNeMo/bionemo-recipes`. No exact duplicate found for either finding.
- AMPLIFY: `pad_weights` → 0 hits. A second query (`dtype device padding`) returned a result too
  large to read in full in this session and was not usable as a clean check — treat that query as
  inconclusive, not "zero hits."
- THD CP: `context parallel dropped tokens` → 5 hits, all unrelated feature/recipe PRs.
  `cu_seqlens_padded divisible` → 4 hits, most relevantly issue #1561 (MFU/FLOPs accounting under
  the *separate* `pad_to_multiple_of` mock-sequence path) — related subsystem, explicitly a
  different code path per the issue's own text and maintainer comments, not a duplicate.
Neither search is exhaustive (GitHub lexical search misses paraphrased duplicates).

## Evidence packages
- `/sessions/kind-zealous-edison/mnt/QPB/evidence/bionemo-amplify-pad-weights-dtype/` — README.md,
  `0001-amplify-pad-weights-dtype-device.patch`, red.log, green.log,
  pytest_collection_blocked.log, PR-DRAFT.md, harness/harness_pad_weights.py.
- `/sessions/kind-zealous-edison/mnt/QPB/evidence/bionemo-thd-cp-divisibility/` — README.md,
  `0001-thd-cp-divisibility-guard.patch`, red.log, green.log, pytest_collection_blocked.log,
  PR-DRAFT.md, harness/harness_thd_sharding.py, harness/run_test.py.

## What was NOT done (scope discipline)
- No PR, issue, or comment was opened or submitted anywhere. Andrew reviews and submits.
- The other 5 historical bionemo bugs (BUG-001, BUG-002, BUG-003, BUG-006, BUG-007) were out of
  scope for this task (only BUG-004/BUG-005 were assigned) and were not re-validated here; the
  wave-2 triage doc already notes BUG-003/BUG-006 as already-fixed upstream and BUG-001/002/007
  as unlocatable after the repo's `sub-packages/` restructure.
- No attempt was made to install `transformer_engine`, `nvtx`, `datasets`, or full `transformers`
  — this would have both exceeded the disk budget and, for `transformer_engine`, likely failed
  outright without a GPU/CUDA toolchain regardless of disk space.
