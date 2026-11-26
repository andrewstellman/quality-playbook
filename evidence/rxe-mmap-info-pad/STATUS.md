status: applied
title: rxe: rxe_create_mmap_info() didn't zero struct mminfo, so do_mmap_info() copied 4 uninitialized pad bytes to user space
link: https://lore.kernel.org/linux-rdma/20261123140620.64393-1-astellman@stellman-greene.com/
updated: 2026-11-26
note: Applied by Leon Romanovsky to the rdma tree on 2026-11-26 as 5d298f34048ba4; not yet in mainline. Reviewed-by Zhu Yanjun. Sent 2026-11-23 to Zhu Yanjun, Cc Jason Gunthorpe, Leon Romanovsky, linux-rdma, linux-kernel.

## Files

- The patch as sent.
- The reproducer and logs are kept with the run records until the fix is in a released kernel.
