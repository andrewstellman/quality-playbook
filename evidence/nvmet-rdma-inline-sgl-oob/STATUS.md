status: merged
title: nvmet-rdma: a wrapping offset check lets nvmet_rdma_map_sgl_inline() write out of bounds
link: https://lore.kernel.org/r/20261021050748.32491-1-astellman@stellman-greene.com
updated: 2026-11-06
note: In mainline as d1512773a0d5 (in v7.4-rc1; checked on GitHub 2026-11-06), applied via nvme-7.4 by Keith Busch on 2026-10-21. Queued for 7.3-stable by Sasha Levin on 2026-11-06. Bryam Vargas reported the same bug first (29 May 2026) and the patch credits him with Reported-by. Not reproduced at runtime: see README.md.
