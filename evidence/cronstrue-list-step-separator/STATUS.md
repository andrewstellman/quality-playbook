status: merged
title: Fix separators in lists with a plain first value and a step (0 9 * * 5,0-4/2 printed "AMonly ... and , every")
link: https://github.com/bradymholt/cRonstrue/pull/423
updated: 2026-10-20
note: Merged 2026-10-20 by Brady Holt as 068055cd on main (02:38:47 UTC, squash of 4b78257 and 239e2ad, author Andrew Stellman, no co-author lines), released in cronstrue 3.36.0 (70a7e48). The merged diff is identical by patch-id to 872fffe..239e2ad (4 files, +25 -2). Opened as a draft and marked ready 2026-10-10; Copilot flagged the disclosed Vietnamese side effect; the maintainer requested changes on 2026-10-19 and the second commit (239e2ad, the vi month-step string and two vi tests; see round2/ROUND2.md) answered it. Checked with git against the live repository on 2026-10-20.
