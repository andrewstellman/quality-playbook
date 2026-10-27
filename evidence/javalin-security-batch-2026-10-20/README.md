# Javalin: the bugs sent to the maintainer in October 2026

The Quality Playbook ran on javalin/javalin master on 2026-09-29 (QPB 1.6.0, Claude Opus 5.5 for all six phases) and reported 68 bugs. Javalin has no private vulnerability reporting, so Andrew emailed the maintainer, David Åse, about the security-relevant ones on 2026-10-20 and 2026-10-21. He reproduced them and asked for one pull request per issue with a small test.

| bug | folder | PR | result |
|---|---|---|---|
| BUG-055 | [javalin-static-encoded-path-before-handler](../javalin-static-encoded-path-before-handler/) | #2665 | merged 2026-10-22 |
| BUG-028 | [javalin-basicauth-unset-credentials](../javalin-basicauth-unset-credentials/) | #2666 | merged 2026-10-22 |
| BUG-037 | [javalin-basicauth-websocket-upgrade](../javalin-basicauth-websocket-upgrade/) | #2667 | open, held for Javalin 8 |
| BUG-050 | [javalin-head-bypasses-get-roles](../javalin-head-bypasses-get-roles/) | #2668 | merged 2026-10-22 |
| BUG-033 | [javalin-exception-message-html-xss](../javalin-exception-message-html-xss/) | #2669 | merged 2026-10-22 |
| BUG-020 | [javalin-sse-comment-cr-injection](../javalin-sse-comment-cr-injection/) | #2670 | merged 2026-10-22 |
| BUG-065 | [javalin-basicauth-scheme-case](../javalin-basicauth-scheme-case/) | #2671 | merged 2026-10-22 |
| BUG-013 | [javalin-static-hostedpath-prefix](../javalin-static-hostedpath-prefix/) | #2672 | merged 2026-10-23 |
| BUG-012 | [javalin-precompress-cache-shared](../javalin-precompress-cache-shared/) | #2673 | merged 2026-10-23 |
| BUG-022 | [javalin-ws-upgrade-creates-session](../javalin-ws-upgrade-creates-session/) | #2674 | merged 2026-10-23 |
| BUG-060 | [javalin-upload-filename-directory](../javalin-upload-filename-directory/) | #2675 | merged 2026-10-23 |
| BUG-036 | docs only: `website-docs-036.patch` | javalin/website#318 | merged 2026-10-23 |
| BUG-060 | docs only: `website-docs-060.patch` | javalin/website#319 | merged 2026-10-24 |

The merged fixes were released in Javalin 7.2.4 on 2026-10-25. BUG-027 (the rate limiter trusting a client-supplied X-Forwarded-For) was already public: the maintainer had filed it himself as #2654 for Javalin 8. The earlier ordinary bug from the same run, BUG-025, is [javalin-lowercase-redirect-contextpath](../javalin-lowercase-redirect-contextpath/) (#2660, merged 2026-10-22).

The first seven were sent as a batch, and the next four as a second batch, because the maintainer asked for all of them at once. That is an exception to the one-at-a-time rule in [`SUBMISSION-PROTOCOL.md`](../SUBMISSION-PROTOCOL.md).

## Files

- `REVIEW-PANEL.md`: the independent review of the first seven fixes on 2026-10-20, with the probe logs (`probe*.log`, `probe-020-033.*.txt`) and the red, green and full-suite logs (`batch.red.log`, `final*.log`, `baseline.suite.log`). The panel found that the BUG-055 fix still served `//secret/file.txt`; the fix was revised before it was sent, and `final2.*` are the logs after that revision.
- `KnockOnStaticTest.kt`, `knockon*.log`: before/after checks of ordinary static-file requests.
- `test-snippets/`: the regression tests and the helper scripts that inserted them.
- `suite-second-batch.log`: the full javalin module suite with the second batch (#2672 to #2675) applied.
- `website-docs-*.patch`, `website-docs-*-PR.md`: the two docs changes as sent.

The run's full `BUGS.md` (68 bugs) is not published yet. Some of its entries have not been fixed, and the maintainer will get the output of a re-run against the patched code first.
