status: merged
title: javalin: Basic auth credentials are ignored when the scheme is not spelled exactly "Basic"
link: https://github.com/javalin/javalin/pull/2671
updated: 2026-10-27
note: BUG-065 of the 2026-09-29 javalin run. Merged by the maintainer, David Åse, on 2026-10-22 and released in Javalin 7.2.4 on 2026-10-25, whose release notes credit @andrewstellman.

## History

- Record as of 2026-10-21: BUG-065 of the 2026-09-29 javalin campaign run (quality/BUGS.md). Reproduced on master 20ba71b (2026-09-21) on 2026-10-20; fix and regression test prepared (0001-context-Accept-the-Basic-auth-scheme-name-case-insen.patch); javalin module suite with all seven javalin fixes 1020 tests, 0 failures (see REVIEW.md). Waiting on the channel decision (private advisory or public PR) and Andrew's review. 2026-10-21: maintainer David Åse replied by email (18:22Z) that he reproduced the reported items and asked for PRs, one per issue with small tests. PR #2671 opened by Andrew at about 19:47Z from andrewstellman:basic-auth-scheme-case (patch and text in harness_runs/security-disclosure-2026-10-20/stage-javalin-1021/).
