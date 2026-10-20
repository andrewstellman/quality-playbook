# S2 round 2: SHIP (high)

Role S2, test readability, round 2. The two tests are unchanged since round 1 and still do their job. No new problem in the revised PR.md or commit body that touches the tests. Copy used: scratch/panel2-cron-parser-http-date-formats-S2 (clone of the fixed clone, HEAD 7e1aa55 on 5033a31). The fixed clone's `git status --short` is empty after my runs.

## Round-1 findings, one by one
1. Stale base and counts: FIXED. `git log` in the clone: `7e1aa55 fix: accept ...` on `5033a31 chore: bump version`. PR.md says "upstream master at 5033a31" and "348 tests passed (346 before)". My own full run on the copy: `Tests:       348 passed, 348 total`. full-check.log ends `full-check exit 0` with the same 348. The patch file equals `git format-patch -1` of the clone (diff of the two, minus From/Date lines, was empty).
2. Ticks naming commands not run: FIXED. `npm test`, `lint`, `format`, `build` boxes are unticked, and the sentence says the npm scripts were not run and full-check was. Ticked boxes left: Bug fix, coverage, tests added, "All tests pass locally", rebased. Each follows from full-check or the rebase.
3. Template placeholders: FIXED. The Description "Fixes #" line is gone and Related Issues says `None.`
4. Rename of tests: correctly NOT ADOPTED. PR.md Testing names `HTTP RFC 850` and `HTTP asctime, read as GMT`, which match the test names in tests/CronDate.test.ts lines 447-455. Neighbours are `ISO 8601 without offset`, `RFC2822 with non-local offset`; the new names are short and the asctime one states the GMT decision. Fine.
5. "Last in chain" not pinned by the tests: still true, still acceptable, and PR.md no longer implies otherwise (the "13 inputs" sentence was dropped; the claim now rests on "inputs that parse today never reach it", which is a code fact at src/CronDate.ts:54).
6. No local-timezone-block test: correctly NOT ADOPTED, same reason as before.

## Experiments on the copy (commands: `bin/run-tests $S --runTestsByPath $S/tests/CronDate.test.ts -t HTTP`)
- M1 delete the `fromHTTP` line:
  `CronDate: unhandled timestamp: Sunday, 06-Nov-94 08:49:37 GMT`
  `CronDate: unhandled timestamp: Sun Nov  6 08:49:37 1994`
  `Tests:       2 failed, 47 skipped, 49 total`
  Both tests fail, with the message PR.md quotes. Right reason.
- M2 read asctime in `tz` (extra `fromFormat(timestamp, 'EEE MMM  d HH:mm:ss yyyy', dateOpts)` before `fromHTTP`):
  `● ... › HTTP asctime, read as GMT`
  `Expected: "1994-11-06T08:49:37.000Z"`
  `Received: "1994-11-06T06:49:37.000Z"`
  `Tests:       1 failed, 47 skipped, 1 passed, 49 total`
  The test pins the GMT decision that the commit body and PR.md state.
- M4 move `fromHTTP` ahead of `fromRFC2822`, full suite: `Tests: 348 passed, 348 total`. Order is not pinned by any test. Harmless here (IMF-fixdate gives the same instant either way); PR.md does not claim the tests protect order.
- M5 drop `dateOpts` from `fromHTTP(timestamp, dateOpts)`: `2 passed`. Not a behaviour change, as the later `setZone` equalises it. Not a gap worth a test.
(My first attempt at a "move fromHTTP first" mutation was malformed, it ran before `#date` was assigned, and gave 2 failed. I discarded it and did M4 instead.)

## New claims in the revision, checked
- "The zero-padded day form (`Sun Nov 06 08:49:37 1994`) is accepted too." Ran `new CronDate(s,'Europe/Athens')` through ts-node on the copy: `"Sun Nov 06 08:49:37 1994" 1994-11-06T08:49:37.000Z`. True.
- README.md:85 and :88 quotes: `sed -n 83,90p README.md` shows line 85 "When using string dates, the following formats are supported:" and line 88 "- HTTP and RFC2822". True.
- "That list came from commit ef172bd, which linked ...": `git show ef172bd` diff adds `+- [`HTTP and RFC2822`](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)`. True. The current README no longer has the link, and the sentence says "linked", which is past tense. Note `git log -S"HTTP and RFC2822" -- README.md` lists only 9332e6b (the squashed merge of that change), so the operator should say "ef172bd" only if it is reachable in the upstream history they push from; I saw it in this clone's history.
- Commit body: matches the SYNTHESIS item 6 text; no trailers; author Andrew Stellman. Its two behaviour claims (asctime ignores tz; inputs that parse today unchanged) are backed by the asctime test and by sideeffect.log (`inputs that parsed before and now differ: 0`, 13 rows).

## Side-effect rule
Unchanged from round 1. Strings that parsed before never reach `fromHTTP`. Newly accepted: two obsolete formats that threw. Callers who relied on the throw, or who pass zone-less asctime meant as local time, are named in PR.md in plain words. Low likelihood. Not a drop.

## Remaining, none blocking
- Test names are not perfectly parallel (`HTTP RFC 850` vs `HTTP asctime, read as GMT`). Cosmetic, left as is.
- The asctime test uses a double space in the day, which is what the format needs and is what the commit body shows. A reader may think it is a typo; a one-line comment is not needed (neighbours have none).

## Not checked
eslint, prettier and tsd by me (I rely on the full-check.log `full-check exit 0`; I did not rerun it). The operator's Mac command. Luxon versions other than the installed one. Whether `ef172bd` exists on the upstream remote (checked only in this clone). Closed issues and PRs on the forge.
