status: merged
title: javalin: a percent-encoded or double-slash path bypasses a path-scoped before-handler for static files
link: https://github.com/javalin/javalin/pull/2665
updated: 2026-10-27
note: BUG-055 of the 2026-09-29 javalin run. Merged by the maintainer, David Åse, on 2026-10-22 and released in Javalin 7.2.4 on 2026-10-25, whose release notes credit @andrewstellman.

## History

- Record as of 2026-10-21: BUG-055 of the 2026-09-29 javalin campaign run. Javalin has no security policy or private vulnerability reporting, so Andrew emailed the maintainer, David Åse, at the address on his commits on 2026-10-20 16:16 -0400 from andrew@stellman.com, with the fix and test attached (text as sent is quoted in sent-followup-email.eml; draft in EMAIL-AS-DRAFTED.md). That email proposed a PR on 2026-11-03; the follow-up at 16:21 withdrew the date and defers to his timeline, since nothing needs to be public for the paper. Fix revised after the 2026-10-20 review to also close the // alias; module suite 1020 tests, 0 failures (REVIEW.md). Do not open a public PR without his reply, or a nudge first if none comes. 2026-10-21: maintainer David Åse replied by email (18:22Z) that he reproduced the reported items and asked for PRs, one per issue with small tests. PR #2665 opened by Andrew at about 19:47Z from andrewstellman:static-path-aliases (patch and text in harness_runs/security-disclosure-2026-10-20/stage-javalin-1021/).
