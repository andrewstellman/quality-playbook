"""
HARNESS EXECUTION (not a real import): models/esm2/collator.py has module-level imports of
`transformer_engine.pytorch.attention...` and `nvtx`, both of which require a CUDA-capable
environment / GPU toolkit that isn't available in this CPU-only sandbox, so the real module
cannot be imported here.

Instead, the pure-tensor sharding logic is copied VERBATIM from:
  models/esm2/collator.py:733-868   (_find_seq_dim, _process_tensor_thd, _process_tensor_bshd
                                      -- unchanged, shared by both the buggy and fixed variants)
  models/esm2/collator.py:930-996   (_split_batch_by_cp_rank -- BUGGY / unpatched, current main)

The only edit relative to the source is deleting the `@nvtx.annotate(...)` decorator line on
_split_batch_by_cp_rank (930), since the `nvtx` package is unavailable here; nvtx.annotate is a
no-op profiling context manager and does not affect behavior.

This is single-process, non-distributed: `cp_rank` is passed explicitly (the function's own
`cp_rank: int | None = None` parameter, documented at collator.py:955-956, exists precisely to
let a caller shard "as if it were executing on that rank without querying
torch.distributed.get_rank" -- so no torch.distributed process group is needed to exercise this
code path).
"""

import torch


# ============================================================================
# VERBATIM: models/esm2/collator.py:733-868 (_find_seq_dim, _process_tensor_thd,
# _process_tensor_bshd) -- identical in buggy and fixed variants, not part of the bug.
# ============================================================================
def _find_seq_dim(tensor: torch.Tensor, seq_len: int) -> int:
    """Find which dimension of tensor matches the expected sequence length.

    Args:
        tensor: The tensor to inspect.
        seq_len: The expected sequence length to match against tensor dimensions.

    Returns:
        The dimension index that matches the sequence length.

    Raises:
        ValueError: If no dimension matches the expected sequence length.
    """
    if tensor.ndim == 1:
        if tensor.shape[0] == seq_len:
            return 0
        raise ValueError(f"1D tensor shape {tensor.shape} doesn't match sequence length {seq_len}")
    elif tensor.ndim >= 2:
        if tensor.shape[1] == seq_len:
            return 1
        elif tensor.shape[0] == seq_len:
            return 0
        raise ValueError(f"Tensor shape {tensor.shape} doesn't match sequence length {seq_len} in dim 0 or 1")
    raise ValueError(f"Unexpected tensor ndim={tensor.ndim}")


def _process_tensor_thd(
    val: torch.Tensor | None,
    seq_len: int,
    slice_sizes: torch.Tensor,
    cu_seqlens_padded: torch.Tensor,
    cp_rank: int,
    total_slices: int,
) -> torch.Tensor | None:
    """Extract the THD context-parallel shard for a single tensor.

    For each sequence in the batch, selects two slices (one from the beginning and one from the end)
    corresponding to the given CP rank, following the zigzag CP sharding pattern.

    Args:
        val: The tensor to shard, or None (returned as-is).
        seq_len: Total sequence length (from cu_seqlens_padded[-1]).
        slice_sizes: Per-sequence slice sizes, computed as sequence_lengths // total_slices.
        cu_seqlens_padded: Cumulative sequence lengths including padding.
        cp_rank: The context parallelism rank index.
        total_slices: Total number of slices per sequence (2 * cp_world_size).

    Returns:
        The sharded tensor for the given CP rank, or None if val is None.
    """
    if val is None:
        return val

    seq_dim = _find_seq_dim(val, seq_len)

    cp_rank_slices = []
    for slice_size, seq_start in zip(slice_sizes, cu_seqlens_padded[:-1]):
        # 1st segment
        cp_rank_slices.append(
            torch.arange(
                seq_start + (cp_rank * slice_size),
                seq_start + ((cp_rank + 1) * slice_size),
                device=val.device,
            )
        )

        # 2nd segment
        cp_rank_slices.append(
            torch.arange(
                seq_start + ((total_slices - cp_rank - 1) * slice_size),
                seq_start + ((total_slices - cp_rank) * slice_size),
                device=val.device,
            )
        )

    return val.index_select(seq_dim, torch.cat(cp_rank_slices))


def _process_tensor_bshd(
    val: torch.Tensor | None,
    cp_rank: int,
    cp_world_size: int,
) -> torch.Tensor | None:
    """Extract the BSHD context-parallel shard for a single tensor.

    Splits a BSHD-format tensor along the sequence dimension (dim=1) into 2*cp_world_size chunks,
    then selects the two chunks corresponding to the given CP rank (zigzag pattern).

    Args:
        val: The tensor to shard, or None (returned as-is).
        cp_rank: The context parallelism rank index.
        cp_world_size: Total number of context parallelism ranks.

    Returns:
        The sharded tensor for the given CP rank, or None if val is None.

    Raises:
        ValueError: If the tensor has fewer than 2 dimensions or its sequence length
            is not divisible by 2 * cp_world_size.
    """
    if val is None:
        return val

    if val.ndim < 2:
        raise ValueError(f"BSHD format requires at least 2D tensors, got {val.ndim}D")

    seq_len = val.shape[1]

    # Calculate chunk size
    total_chunks = 2 * cp_world_size
    chunk_size = seq_len // total_chunks

    if seq_len % total_chunks != 0:
        raise ValueError(
            f"Sequence length {seq_len} must be divisible by {total_chunks} "
            f"(2 * cp_world_size) for BSHD context parallelism"
        )

    # Determine which chunks this rank should get
    # Rank 0 gets chunks [0, total_chunks-1]
    # Rank 1 gets chunks [1, total_chunks-2]
    # Rank k gets chunks [k, total_chunks-k-1]
    chunk_indices = [cp_rank, total_chunks - cp_rank - 1]

    # Collect slices for this rank
    rank_slices = []
    for chunk_idx in chunk_indices:
        start_idx = chunk_idx * chunk_size
        end_idx = start_idx + chunk_size
        rank_slices.append(torch.arange(start_idx, end_idx, device=val.device))

    # Concatenate indices for all chunks this rank should get
    indices = torch.cat(rank_slices)

    # Select along sequence dimension (dim=1)
    return val.index_select(1, indices)


# ============================================================================
# VERBATIM (nvtx decorator removed, see module docstring): models/esm2/collator.py:930-996
# BUGGY / unpatched current main: no divisibility guard on the THD branch.
# ============================================================================
def _split_batch_by_cp_rank_buggy(
    cu_seqlens_padded: torch.Tensor | None,
    input_ids_padded: torch.Tensor,
    labels_padded: torch.Tensor,
    cp_group: torch.distributed.ProcessGroup | None = None,
    qvk_format: str = "thd",
    cp_rank: int | None = None,
    cp_world_size: int | None = None,
):
    """Slice batch input along sequence dimension into multiple chunks for THD or BSHD format.

    This function is intended for use in self attention. It will not work for cross attention because
    it does not handle the case where the sequence length of the query and key are different.
    Which are parallelized across GPUs in a context parallel group.
    This version works with variable-length sequences using cumulative sequence lengths for THD format,
    and with padded sequences for BSHD format.

    Args:
        cu_seqlens_padded: Cumulative sequence length. Required for THD format, optional for BSHD format.
        input_ids_padded: Input IDs.
        labels_padded: Labels.
        cp_group: Context parallel group.
        qvk_format: Format of the input data ("thd" or "bshd").
        cp_world_size: The size of the context parallelism group. If provided, the function will use this value to determine the rank.
        cp_rank: Optional manual CP rank index. When provided, the function shards tensors as if it
            were executing on that rank without querying `torch.distributed.get_rank`.
    """
    if qvk_format not in ["thd", "bshd", "sbhd"]:
        raise ValueError(f"Unsupported qvk_format: {qvk_format}!")

    if cp_world_size is None or cp_world_size <= 1:
        # No splitting needed
        return input_ids_padded, labels_padded

    if cp_rank is None:
        cp_rank = torch.distributed.get_rank(group=cp_group)
    elif not (0 <= cp_rank < cp_world_size):
        raise ValueError(f"cp_rank must be in [0, {cp_world_size}), but received {cp_rank}.")

    if qvk_format == "thd":
        if cu_seqlens_padded is None:
            raise ValueError("cu_seqlens_padded is required for THD format")

        # Calculate the chunk sizes for each sequence
        total_slices_of_any_sequence = 2 * cp_world_size
        slice_sizes = (cu_seqlens_padded[1:] - cu_seqlens_padded[:-1]) // total_slices_of_any_sequence

        # Ensure cu_seqlens_padded[-1] is a Python int, not a 0-dim tensor
        last_elem = cu_seqlens_padded[-1]
        seq_len_val = last_elem.item() if isinstance(last_elem, torch.Tensor) else last_elem

        input_ids_padded = _process_tensor_thd(
            input_ids_padded, seq_len_val, slice_sizes, cu_seqlens_padded, cp_rank, total_slices_of_any_sequence
        )
        labels_padded = _process_tensor_thd(
            labels_padded, seq_len_val, slice_sizes, cu_seqlens_padded, cp_rank, total_slices_of_any_sequence
        )

    elif qvk_format == "bshd":
        input_ids_padded = _process_tensor_bshd(input_ids_padded, cp_rank, cp_world_size)
        labels_padded = _process_tensor_bshd(labels_padded, cp_rank, cp_world_size)

    else:
        raise ValueError(f"Support not implemented yet for qvk_format: {qvk_format}!")

    return input_ids_padded, labels_padded


# ============================================================================
# FIXED variant: same as above, with the divisibility guard added to the THD branch,
# mirroring the guard the BSHD branch already has (collator.py:842-848,
# "Sequence length {seq_len} must be divisible by {total_chunks} (2 * cp_world_size)").
# ============================================================================
def _split_batch_by_cp_rank_fixed(
    cu_seqlens_padded: torch.Tensor | None,
    input_ids_padded: torch.Tensor,
    labels_padded: torch.Tensor,
    cp_group: torch.distributed.ProcessGroup | None = None,
    qvk_format: str = "thd",
    cp_rank: int | None = None,
    cp_world_size: int | None = None,
):
    if qvk_format not in ["thd", "bshd", "sbhd"]:
        raise ValueError(f"Unsupported qvk_format: {qvk_format}!")

    if cp_world_size is None or cp_world_size <= 1:
        return input_ids_padded, labels_padded

    if cp_rank is None:
        cp_rank = torch.distributed.get_rank(group=cp_group)
    elif not (0 <= cp_rank < cp_world_size):
        raise ValueError(f"cp_rank must be in [0, {cp_world_size}), but received {cp_rank}.")

    if qvk_format == "thd":
        if cu_seqlens_padded is None:
            raise ValueError("cu_seqlens_padded is required for THD format")

        total_slices_of_any_sequence = 2 * cp_world_size
        seq_lengths = cu_seqlens_padded[1:] - cu_seqlens_padded[:-1]

        # --- FIX: added divisibility guard, mirroring _process_tensor_bshd's existing guard ---
        remainders = seq_lengths % total_slices_of_any_sequence
        if torch.any(remainders != 0):
            bad = seq_lengths[remainders != 0].tolist()
            raise ValueError(
                f"Padded sequence length(s) {bad} must be divisible by {total_slices_of_any_sequence} "
                f"(2 * cp_world_size) for THD context parallelism"
            )
        # --- end fix ---

        slice_sizes = seq_lengths // total_slices_of_any_sequence

        last_elem = cu_seqlens_padded[-1]
        seq_len_val = last_elem.item() if isinstance(last_elem, torch.Tensor) else last_elem

        input_ids_padded = _process_tensor_thd(
            input_ids_padded, seq_len_val, slice_sizes, cu_seqlens_padded, cp_rank, total_slices_of_any_sequence
        )
        labels_padded = _process_tensor_thd(
            labels_padded, seq_len_val, slice_sizes, cu_seqlens_padded, cp_rank, total_slices_of_any_sequence
        )

    elif qvk_format == "bshd":
        input_ids_padded = _process_tensor_bshd(input_ids_padded, cp_rank, cp_world_size)
        labels_padded = _process_tensor_bshd(labels_padded, cp_rank, cp_world_size)

    else:
        raise ValueError(f"Support not implemented yet for qvk_format: {qvk_format}!")

    return input_ids_padded, labels_padded
