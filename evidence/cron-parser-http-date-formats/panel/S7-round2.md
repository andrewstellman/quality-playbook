# S7 round 2: FIX-REQUIRED (high)

Role S7, citations. Scope: every factual claim in PR.md (revised) and the commit message. All numbers, quotes and behaviours are true except one commit id, which is wrong for the tracker the maintainer sees, and one file:line that is true only after the patch. Both are one-line text edits. No code change.

Work done in my own clone /work/batch/runs/cron-parser/scratch/panel2-cron-parser-http-date-formats-S7 (clone of the fixed clone, node_modules linked, scratch scripts deleted afterwards, fixed clone untouched).

## Verified true (run or read by me)

- Base: upstream-check `master` = 5033a312f1fe04665060eacf4378f16c48ca4ea8; fixed clone HEAD~1 = 5033a31, HEAD = 7e1aa55. `git format-patch -1 --stdout` of my clone is byte-identical (minus the From line) to OUT/0001-*.patch. Patch index lines `d5e8cad` and `5627e3c` equal the blob ids of src/CronDate.ts and tests/CronDate.test.ts at 5033a31.
- Test counts: `bin/run-tests` on HEAD gives `Tests: 348 passed, 348 total`; on HEAD~1 gives `Tests: 346 passed, 346 total`. So "348 tests passed (346 before)" is right.
- `bin/full-check` on my clone: `full-check exit 0`, 348 passed, coverage `All files | 100 | 100 | 100 | 100`. This matches OUT/full-check.log (same steps, same counts). The script's steps are eslint, prettier --check on src and tests, rimraf+tsc+tsd, jest --coverage, which matches the PR.md parenthesis "(eslint, prettier `--check` on `src` and `tests`, build, tsd, jest with coverage thresholds)".
- Repro block (TZ=UTC, ts-node, importing ./src/CronDate), fixed tree:
  - `Sun, 06 Nov 1994 08:49:37 GMT` UTC -> 1994-11-06T08:49:37.000Z
  - `Sunday, 06-Nov-94 08:49:37 GMT` UTC -> 1994-11-06T08:49:37.000Z
  - `Sun Nov  6 08:49:37 1994` UTC and Europe/Athens -> 1994-11-06T08:49:37.000Z
  Old tree (src/CronDate.ts at HEAD~1): the last two throw `Error: CronDate: unhandled timestamp: Sunday, 06-Nov-94 08:49:37 GMT` and `... Sun Nov  6 08:49:37 1994`, byte for byte as the PR shows. The first form parses on the old tree.
- "The first form only works because it is also valid RFC 2822": luxon direct: `fromRFC2822('Sun, 06 Nov 1994 08:49:37 GMT').isValid` true; `fromRFC2822` false for the RFC 850 and asctime strings; fromISO, fromSQL and the fromFormat pattern are false for all three. Isolated, as I did not in round 1.
- "which is what luxon `DateTime.fromHTTP` returns": run, `fromHTTP(...).toUTC().toISO()` = 1994-11-06T08:49:37.000Z for all three. luxon 3 source (node_modules/luxon/src/datetime.js:946) says "Since HTTP dates are always in UTC, this has no effect on the interpretation of string", and its JSDoc examples (:952-954) list exactly these three forms.
- Zone paragraph: `new CronDate('Sun Nov  6 08:49:37 1994','Europe/Athens')` -> 1994-11-06T08:49:37.000Z (run). `new CronDate('Mon, 4 Jan 2021 10:00:00','Europe/Athens')` -> 2021-01-04T08:00:00.000Z, so it is read in tz (run). Test at tests/CronDate.test.ts:405 is named 'RFC2822-like without timezone offset'.
- "The zero-padded day form (`Sun Nov 06 08:49:37 1994`) is accepted too": run, Athens -> 1994-11-06T08:49:37.000Z; old tree throws. (`Sun Nov 6 08:49:37 1994`, one space, still throws; PR.md does not claim otherwise.)
- "These two formats used to throw": run on the old tree (above), in UTC and Europe/Athens.
- "Inputs that parse today never reach it": fromHTTP is the last `isValid ||` link (see finding 2 for the line number). sideeffect.log ends `inputs that parsed before and now differ: 0` (26 rows, 13 inputs x 2 zones; PR.md no longer cites the count, so nothing to check there).
- README.md:85 = "When using string dates, the following formats are supported:", README.md:88 = "- HTTP and RFC2822", at the tip (`git blame -L85,89 master -- README.md`, all b5f41940) and in the fixed clone (README untouched).
- Commit message: "CronDate never called DateTime.fromHTTP": `git grep fromHTTP HEAD~1 -- src` is empty; after the patch `grep -rn fromHTTP src` gives only src/CronDate.ts:54. The quoted strings and the "unhandled timestamp" error text match. "fromHTTP reads all HTTP dates as GMT" is backed by the luxon doc line above. Author `Andrew Stellman <andrew@stellman.com>`, no trailers, subject starts `fix: `.
- Test names in PR.md (`HTTP RFC 850`, `HTTP asctime, read as GMT`) match tests/CronDate.test.ts in the patch. red.log shows `Tests: 2 failed, 47 skipped, 49 total` with both new tests failing on `CronDate: unhandled timestamp`; revert.log `2 failed, 47 passed`; green.log `49 passed`.

## Findings

1. FIX-REQUIRED (wrong citation): "That list came from commit ef172bd" (PR.md, Description, line after the README quote).
   - ef172bd is not on master. `git merge-base --is-ancestor ef172bd master` says NOT-ancestor; `git branch -a --contains ef172bd` lists only `remotes/pr/252`. It is the head commit of PR #252 ("readme: switched from moment to luxon", Vano Devium, 2021-12-07). The commit on master is the squash 9332e6b ("readme: switched from moment to luxon (#252)", 2021-12-22). A maintainer who runs `git show ef172bd` on a clone of master gets "bad object". On GitHub it would resolve only through the PR.
   - The lines the PR quotes (README.md:85-89) were written by b5f4194 ("Typescript rewrite (#360)", `git log -S'- HTTP and RFC2822'`). That commit dropped the luxon links; the old README (b5f4194^:README.md:141) has "- [`HTTP and RFC2822`](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)". So "that list came from" ef172bd is loose twice.
   - Change to: "The list goes back to 9332e6b (#252), which linked 'HTTP and RFC2822' to luxon's parsing docs (`#/parsing?id=http-and-rfc2822`); the TypeScript rewrite b5f4194 kept the text and dropped the links." Every id in that sentence I ran. The operator can shorten it to the first clause.
   - Not verified: that the luxon docs page has a section titled "HTTP and RFC2822" containing fromHTTP. The URL fragment in the old README says so; I have no network access to the site. "luxon's parsing section of the same name" rests on the URL only. Hedge or drop "of the same name".

2. Minor (file:line true only after the change): "`DateTime.fromHTTP` is the last attempt (`src/CronDate.ts:54`)".
   - At the upstream tip (5033a31) lines 50-53 are fromISO, fromRFC2822, fromSQL, fromFormat and line 54 is `}`. The fromHTTP line is :54 only in the patched file (checked: `sed -n '50,56p'` on my clone, and `git show HEAD~1:src/CronDate.ts | sed -n '53,55p'`). A maintainer reading master sees :53 as the last attempt.
   - Change to "(`src/CronDate.ts:54` with this change)" or cite the file without a line.

3. Low (loose wording): commit body "so the asctime form ignores the tz option". For reading the string that is true (luxon: no effect on interpretation). The `tz` option is still applied to the resulting CronDate (that is the `zone` that luxon sets for display). PR.md says it more exactly ("reads every HTTP date as GMT"). Optional: "so the asctime form is read as GMT whatever the tz option is". I did not run anything that shows how later next()/prev() treat the zone of such a date.

4. Note, not an error: the PR "Testing" sentence says "fail without the change". The logs are red.log (tests only applied) and revert.log (source reverted). I re-ran neither the red nor the revert step myself; I ran the old-tree repro above, which shows the same throw.

## Round 1 findings, status

- Stale base 5b08cdf and 340 count (my round-1 finding 1): fixed. PR.md says 5033a31 and 348 (346 before); patch rebased; logs show 348.
- Ticked npm-script boxes (my round-1 finding 2): fixed. `npm test`, `npm run lint`, `npm run format`, `npm run build` are unticked; the text says the npm scripts were not run. "All tests pass locally", "Code coverage is maintained" and "rebased on the latest master" are ticked; each backed by the full-check run and the tip check above. Caveat: "latest master" is what upstream-check showed at the stage start; I did not refetch.
- 13-inputs sentence (round 1 finding 3): removed from PR.md; nothing left to cite.
- README framing hedge (round 1 finding 4): kept ("If only the RFC 1123 form was meant by 'HTTP', the README line is what should change instead.").
- CONFIRMATION.md "No newer commits": now carries a dated correction at the end. The original wrong line is still in the body, but the file is not part of the PR text.

## Side-effect rule

No change from round 1: only strings that threw before now parse; the zone-less asctime case is now stated in PR.md. Acceptable; no drop.

## Not checked

GitHub issues and PRs (unreachable); the luxon website; whether upstream master moved after the stage began; the npm scripts by name; the operator's Mac command; luxon versions other than the one in node_modules (I did not read its package.json version; round 1 and the synthesis say 3.7.2).
