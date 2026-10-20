status: merged
title: zram: recompress_store() accepted an unrecognized type= value and recompressed every slot (SA-004)
link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=2f529e73d72048743b6eaa241da6ac2bcb28099e
updated: 2026-10-20
note: Patch sent to the zram maintainers and linux-mm on 2026-04-07 (https://lore.kernel.org/20260407153027.42425-1-astellman@stellman-greene.com); merged to mainline as 2f529e73 on 2026-04-18. Found by the v1.3.7 run of 2026-04-06 as spec-audit finding SA-004, confirmed by a verification probe during triage. This folder was recovered from a Time Machine backup on 2026-06-14 and added to evidence/ on 2026-10-20; see NOTE.md.
