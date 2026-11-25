status: applied
title: siw: a user send queue could post the kernel-only SIW_OP_REG_MR and SIW_OP_INVAL_STAG opcodes; REG_MR then used a user-supplied value as a kernel pointer
link: https://lore.kernel.org/linux-rdma/20261120140605.62810-1-astellman@stellman-greene.com/
updated: 2026-11-25
note: v2 applied by Leon Romanovsky to the rdma tree (rdma-rc) on 2026-11-25 as 94e81a1f3ffabb; not yet in mainline. Acked-by Bernard Metzler (siw maintainer). v1 sent 2026-11-19, v2 (full kernel log in the changelog, as Leon asked) 2026-11-20, to Bernard Metzler, Cc Jason Gunthorpe, Leon Romanovsky, linux-rdma, linux-kernel.

## Files

- The v2 patch as sent.
- The reproducer and QEMU logs are kept with the run records until the fix is in a released kernel.
