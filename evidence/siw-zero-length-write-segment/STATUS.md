status: applied
title: siw: a zero length tagged WRITE segment with the L bit clear made siw read mem->stag through an unset rx_mem, and a remote peer could panic the host
link: https://lore.kernel.org/linux-rdma/20261120140552.62784-1-astellman@stellman-greene.com/
updated: 2026-11-26
note: v2 applied by Leon Romanovsky to the rdma tree on 2026-11-26 as dba1616eadfbcd; not yet in mainline. Acked-by Bernard Metzler. v1 sent 2026-11-19, v2 (full kernel log, as Leon asked) 2026-11-20, to Bernard Metzler, Cc Jason Gunthorpe, Leon Romanovsky, linux-rdma, linux-kernel.

## Files

- The v2 patch as sent.
- The reproducer and QEMU logs are kept with the run records until the fix is in a released kernel.
