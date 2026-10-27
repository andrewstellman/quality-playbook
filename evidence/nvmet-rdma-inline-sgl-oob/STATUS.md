status: applied
title: nvmet-rdma: a wrapping offset check lets nvmet_rdma_map_sgl_inline() write out of bounds
link: https://lore.kernel.org/r/20261021050748.32491-1-astellman@stellman-greene.com
updated: 2026-10-27
note: Applied to nvme-7.4 by Keith Busch on 2026-10-21; not in mainline on 2026-10-27. Bryam Vargas reported the same bug first (29 May 2026) and the patch credits him with Reported-by. Not reproduced at runtime: see README.md.
