status: merged
title: javalin: HttpResponseException messages are reflected unescaped with Content-Type text/html
link: https://github.com/javalin/javalin/pull/2669
updated: 2026-10-27
note: BUG-033 of the 2026-09-29 javalin run. Merged by the maintainer, David Åse, on 2026-10-22 and released in Javalin 7.2.4 on 2026-10-25, whose release notes credit @andrewstellman.

## History

- Record as of 2026-10-21: BUG-033 of the 2026-09-29 javalin campaign run (quality/BUGS.md). Reproduced on master 20ba71b (2026-09-21) on 2026-10-20; fix and regression test prepared (0001-http-HTML-escape-HttpResponseException-messages-serv.patch); javalin module suite with all seven javalin fixes 1020 tests, 0 failures (see REVIEW.md). Held from public PR: sent privately to the maintainer, David Åse, with the patch attached, in a follow-up to the BUG-055 email (2026-10-20 16:21 -0400, from andrew@stellman.com; sent-followup-email.eml). It asks whether he objects to PRs and defers to his timeline. Do not treat silence as consent; nudge in the same thread before any public PR. 2026-10-21: maintainer David Åse replied by email (18:22Z) that he reproduced the reported items and asked for PRs, one per issue with small tests. PR #2669 opened by Andrew at about 19:47Z from andrewstellman:escape-html-error-message (patch and text in harness_runs/security-disclosure-2026-10-20/stage-javalin-1021/).
