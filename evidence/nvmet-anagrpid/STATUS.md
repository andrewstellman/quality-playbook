status: applied
title: nvmet: ANA group ID 128 clamped to 0 by array_index_nospec()
link: https://lore.kernel.org/r/20261106134313.34829-1-astellman@stellman-greene.com
updated: 2026-11-06
note: Applied to nvme-7.4 by Keith Busch on 2026-11-06 (commit f3c20e42ff5628b93ed0084154cf62082a2157b2); not yet in mainline. v2 sent to linux-nvme 2026-11-06 (Message-ID <20261106134313.34829-1-astellman@stellman-greene.com>), rebased on next-20261105, answering Sagi's v1 question on testing. Yuehong Wu had posted the same fix on 2026-11-06, credited v1 and said he had no objection to the original being taken; v2 credits him and invites his Tested-by; Andrew replied in his thread pointing to v2 the same day.

## History

- Record as of 2026-10-27: Sent to linux-nvme 2026-09-10; awaiting review (see README). Not in mainline on 2026-10-27 (history of the touched files in torvalds/linux on GitHub). On v1, Sagi Grimberg asked whether it had been tested; that went unanswered until v2.

- Record as of 2026-10-01: Sent to linux-nvme 2026-09-10; awaiting review (see README).
