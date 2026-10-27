status: merged
title: javalin: UploadedFile.filename() keeps the directory components the client sent
link: https://github.com/javalin/javalin/pull/2675
updated: 2026-10-27
note: BUG-060 of the 2026-09-29 javalin run. Reported to the maintainer by email on 2026-10-21; he reproduced it and asked for a PR. Opened 2026-10-22, merged 2026-10-23, released in Javalin 7.2.4 on 2026-10-25, whose release notes credit @andrewstellman. The docs note for 7.2.3 and earlier is javalin/website#319, merged after the maintainer pointed out that a Path.of(...).getFileName() workaround in the first draft does not reject "..".

## History

- Red on origin/master and green on the PR branch: redgreen-second-batch.log (all four PRs of this batch). Full javalin module suite with all four applied: 1024 tests, 0 failures, 2 errors, both in the browser test class TestJavalinVueBrowser (14 of its 16 tests skipped) (javalin-security-batch-2026-10-20/suite-second-batch.log).
