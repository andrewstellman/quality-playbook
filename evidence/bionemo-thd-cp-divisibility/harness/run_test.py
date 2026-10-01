"""
Test scenario: two sequences packed THD-style, cp_world_size=2 (total_slices=4).
Sequence A padded length = 8  (divisible by 4  -> fine)
Sequence B padded length = 10 (NOT divisible by 4 -> the bug: 10 // 4 = 2, drops 2 tokens)

cu_seqlens_padded = [0, 8, 18]   (0, 8, 8+10)
Total tokens = 18. All ranks together should reconstruct all 18 real (non-pad) input_ids.
For sequence B's 10 tokens, buggy slice_size = 10 // 4 = 2, so each rank only takes
2*slice_size = 4 tokens per rank => 2 ranks * 4 = 8 of B's 10 tokens are ever selected by
ANY rank -> 2 tokens permanently lost. The fixed version raises instead of silently dropping.
"""

import sys
import torch

sys.path.insert(0, ".")
from harness_thd_sharding import _split_batch_by_cp_rank_buggy, _split_batch_by_cp_rank_fixed  # noqa: E402


def build_batch():
    len_a, len_b = 8, 10
    cu_seqlens_padded = torch.tensor([0, len_a, len_a + len_b], dtype=torch.int32)
    total = len_a + len_b
    # Use distinct token ids per position so we can tell which original tokens survive.
    input_ids = torch.arange(total, dtype=torch.long).unsqueeze(0)  # shape [1, total] (THD: batch=1)
    labels = input_ids.clone()
    return cu_seqlens_padded, input_ids, labels, total


def run_buggy():
    cu_seqlens_padded, input_ids, labels, total = build_batch()
    cp_world_size = 2
    seen = set()
    for cp_rank in range(cp_world_size):
        sharded_ids, _ = _split_batch_by_cp_rank_buggy(
            cu_seqlens_padded=cu_seqlens_padded,
            input_ids_padded=input_ids,
            labels_padded=labels,
            qvk_format="thd",
            cp_rank=cp_rank,
            cp_world_size=cp_world_size,
        )
        seen.update(sharded_ids.flatten().tolist())

    missing = sorted(set(range(total)) - seen)
    print(f"[buggy]  total tokens={total}, union of tokens assigned to any rank={len(seen)}, missing={missing}")
    assert missing, "expected the bug to silently drop tokens, but none were dropped"
    print("[buggy]  RED confirmed: tokens", missing, "are dropped by every CP rank (silent data loss)")


def run_fixed():
    cu_seqlens_padded, input_ids, labels, total = build_batch()
    cp_world_size = 2
    try:
        for cp_rank in range(cp_world_size):
            _split_batch_by_cp_rank_fixed(
                cu_seqlens_padded=cu_seqlens_padded,
                input_ids_padded=input_ids,
                labels_padded=labels,
                qvk_format="thd",
                cp_rank=cp_rank,
                cp_world_size=cp_world_size,
            )
        raise AssertionError("expected ValueError to be raised for non-divisible padded length")
    except ValueError as e:
        print(f"[fixed]  GREEN confirmed: raises ValueError instead of silently dropping tokens: {e}")


def run_fixed_valid_case_still_works():
    # Sanity: divisible lengths should still shard correctly with the fixed version (no regression).
    len_a, len_b = 8, 8
    cu_seqlens_padded = torch.tensor([0, len_a, len_a + len_b], dtype=torch.int32)
    total = len_a + len_b
    input_ids = torch.arange(total, dtype=torch.long).unsqueeze(0)
    labels = input_ids.clone()
    cp_world_size = 2
    seen = set()
    for cp_rank in range(cp_world_size):
        sharded_ids, _ = _split_batch_by_cp_rank_fixed(
            cu_seqlens_padded=cu_seqlens_padded,
            input_ids_padded=input_ids,
            labels_padded=labels,
            qvk_format="thd",
            cp_rank=cp_rank,
            cp_world_size=cp_world_size,
        )
        seen.update(sharded_ids.flatten().tolist())
    missing = sorted(set(range(total)) - seen)
    assert not missing, f"regression: fixed version drops tokens on a divisible-length case: {missing}"
    print("[fixed]  no-regression check passed: divisible lengths still fully covered, no tokens dropped")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "buggy"
    if mode == "buggy":
        run_buggy()
    elif mode == "fixed":
        run_fixed()
        run_fixed_valid_case_still_works()
    else:
        raise SystemExit(f"unknown mode {mode}")
