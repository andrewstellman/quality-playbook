status: merged
title: cron-parser: a crontab line or variable named __proto__ replaced the prototype of CronFileParser's result objects (security advisory, low)
link: https://github.com/harrisiirak/cron-parser/security/advisories/GHSA-vh7f-3c46-hfp3
updated: 2026-10-31
note: Published by the maintainer on 2026-10-31 as GHSA-vh7f (Low, CWE-1321) and fixed in cron-parser 5.10.3 by his own PR #461, which uses the same Object.defineProperty approach as the reported patch and also fixes predefined-expression lookups through Object.prototype. Andrew is the credited reporter (credit pending acceptance).

## History

- Record as of 2026-10-31: Private report GHSA-vh7f sent 2026-10-20, no maintainer response. 2026-10-31: Andrew commented (advisory-comment-348884) that it is Low at most and that he plans a public PR and notes on or after 2026-11-10 unless they want more time. Harri Siirak accepted the report at 14:01 -0400, released 5.10.3 (PR #461, merge 8ab5c19) and published the advisory at 14:17 -0400. The advisory's Patched versions field is empty.

- Record as of 2026-10-20: BUG-010 of the 2026-10-05 cron-parser campaign run. Private vulnerability report submitted by Andrew via the GitHub API (submit.sh) on 2026-10-20 at about 19:58 UTC, severity low, CWE-1321, range <= 5.10.2, with the fix and a regression test in tests/CronFileParser.test.ts embedded (349/349 tests, eslint, prettier and type tests clean). Their SECURITY.md lists this class as in scope. Reproduced the same day on main a70b68e (REPRO.md). Awaiting maintainer response.
