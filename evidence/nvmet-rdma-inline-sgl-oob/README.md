# nvmet-rdma: out-of-bounds write in nvmet_rdma_map_sgl_inline()

The Quality Playbook's nvme-target run reported this as BUG-010: the inline-data offset check in
`nvmet_rdma_map_sgl_inline()` can wrap, so a crafted offset passes it and `inline_sg[page_idx]` is
indexed far out of bounds. A later static triage pass (claim N-02) re-traced the control flow in a
separate context and reached the same conclusion.

This patch did not go through the QEMU red/green pipeline described in `../README.md`. It went to
security@kernel.org on 2026-10-20 as a static-analysis finding, with a userspace harness that checks
only the arithmetic (`N-02-arith.c`, output in `N-02-arith.out`): the offset wraps, passes the
existing check, and the fixed check rejects it. It was not reproduced on a running kernel.

Jens Axboe asked for a proper patch, and `0001-nvmet-rdma-fix-oob-write-inline-sgl.patch` is the patch
as sent on 2026-10-21 (Message-ID 20261021050748.32491-1-astellman@stellman-greene.com). While preparing
it we found that Bryam Vargas had reported the same bug on 29 May 2026 with a KASAN reproduction; the
patch credits him with Reported-by and says the bug was found independently. Keith Busch applied it to
nvme-7.4 on 2026-10-21.
