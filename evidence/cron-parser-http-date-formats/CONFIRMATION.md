# BUG-023: String dates in the RFC 850 and asctime HTTP date formats are rejected although the README lists HTTP

Claim: `new CronDate(s, 'UTC')` (and so `currentDate: s` in the parser) with s = `Sunday, 06-Nov-94 08:49:37 GMT` or `Sun Nov  6 08:49:37 1994` throws `CronDate: unhandled timestamp`; expected is 1994-11-06T08:49:37.000Z, because README.md:87-89 lists "HTTP and RFC2822" as a supported string format and luxon's `DateTime.fromHTTP` accepts both.

Verdict: CONFIRMED (LOW, ordinary correctness; a maintainer may instead answer "docs only").

Repro source: /work/batch/runs/cron-parser/scratch/confirm-cron-parser-http-date-formats-confirmer/repro.ts (my own; tries the three HTTP date forms, compares with luxon fromHTTP).
Commit check: clone HEAD = 5b08cdf831c94a656def5a6ab7008f1e497d21b2 = the run's commit = upstream tip. No newer commits.

Output (TZ=UTC ts-node repro.ts, exit=1):
IMF-fixdate: input="Sun, 06 Nov 1994 08:49:37 GMT"
  actual=1994-11-06T08:49:37.000Z
  expected=1994-11-06T08:49:37.000Z
  luxon.fromHTTP valid=true
RFC 850: input="Sunday, 06-Nov-94 08:49:37 GMT"
  actual=THROWS: CronDate: unhandled timestamp: Sunday, 06-Nov-94 08:49:37 GMT
  expected=1994-11-06T08:49:37.000Z
  luxon.fromHTTP valid=true
asctime: input="Sun Nov  6 08:49:37 1994"
  actual=THROWS: CronDate: unhandled timestamp: Sun Nov  6 08:49:37 1994
  expected=1994-11-06T08:49:37.000Z
  luxon.fromHTTP valid=true
With the run's one-line fix applied in the clone (then reverted): repro exit 0, all three print the expected value, project suite "Tests: 338 passed, 338 total".

Expectation check:
- README.md:85 "When using string dates, the following formats are supported:", README.md:87 "- ISO8601", :88 "- HTTP and RFC2822", :89 "- SQL" (grep -n on reference_docs/cite/README.md and the clone). The README gives no example strings, so "HTTP" is read through the link added in 9332e6b (luxon "HTTP and RFC2822" section, which is fromHTTP and fromRFC2822).
- Code: src/CronDate.ts:50-53 (blame b5f41940, TypeScript rewrite #360) tries fromISO, fromRFC2822, fromSQL, then fromFormat 'EEE, d MMM yyyy HH:mm:ss'. The v4 code (lib/date.js before b5f4194) had the same chain. `git log --all -S"fromHTTP"` is empty: it was never called.
- No test, comment, CHANGELOG entry or doc says HTTP is meant to be limited. tests/CronDate.test.ts:388-430 test ISO, ISO date, RFC2822, RFC2822 without offset, SQL, one invalid string; no HTTP case. The v4 comment only explains the fromFormat line ("used in tests").
- Weakness: the IMF-fixdate form (the one HTTP servers send today) already parses via fromRFC2822, so "HTTP" in the README may have meant only that. Not proven either way.

Duplicate search: none found. known_open_bugs.md (operator gh export of 2026-10-05; 9 issues, 4 PRs) lists nothing about string date formats. #446 touches src/CronDate.ts but is about the DST repeated hour in prev(). In upstream-check (189 pr/* refs): no commit or PR head mentions fromHTTP or asctime (git log --all -S'fromHTTP' empty; git grep over every pr head for fromHTTP/asctime in src and tests empty). Closed issues and PRs on the forge were not searched.
dup queries:
- fromHTTP
- "HTTP and RFC2822"
- asctime currentDate
- "unhandled timestamp"
- RFC 850 date string
- string date formats supported README

Security: no. A clean Error on an obsolete date format; wrong/unsupported input, not a hang, loop, memory or ReDoS case.

Likely maintainer pushback:
- "HTTP" in the README means the IMF-fixdate (already works); RFC 850 and asctime are obsolete (RFC 9110 says recipients must accept them, senders must not send them). Answer: the README names luxon's HTTP section; the fix is one line, no suite change. Counter-risk: a maintainer may prefer a README wording change instead.
- Inputs like `Sun Nov  6 08:49:37 1994` carry no zone; fromHTTP reads them as GMT, so with a non-UTC tz option the instant differs from what a caller expecting local time would get. Today they throw, so no existing user is affected, but the semantics should be named in the PR.
- Low value: nobody has reported it in about 5 years.

## Parent re-run

Command: cd <confirmer clone> && TZ=UTC ./node_modules/.bin/ts-node repro.ts
Exit code: 1
```
IMF-fixdate: input="Sun, 06 Nov 1994 08:49:37 GMT"
  actual=1994-11-06T08:49:37.000Z
  expected=1994-11-06T08:49:37.000Z
  luxon.fromHTTP valid=true
RFC 850: input="Sunday, 06-Nov-94 08:49:37 GMT"
  actual=THROWS: CronDate: unhandled timestamp: Sunday, 06-Nov-94 08:49:37 GMT
  expected=1994-11-06T08:49:37.000Z
  luxon.fromHTTP valid=true
asctime: input="Sun Nov  6 08:49:37 1994"
  actual=THROWS: CronDate: unhandled timestamp: Sun Nov  6 08:49:37 1994
  expected=1994-11-06T08:49:37.000Z
  luxon.fromHTTP valid=true
```

Correction (round 2, 2026-10-10): the line "No newer commits" above was wrong. Upstream master was at 5033a312f1fe04665060eacf4378f16c48ca4ea8 when the panel ran; the fix was rebased onto it in round 2.
