# O5 round 2: FIX-REQUIRED (high)

Role: O5 slop (A), round 2. Code and tests are unchanged and fine (one line, two tests in the neighbours' style). One wrong citation must change before submitting. The Description is still too long. Both are text edits.

## Experiments (my copy: /work/batch/runs/cron-parser/scratch/panel2-cron-parser-http-date-formats-O5, clone of the fixed clone, HEAD 7e1aa55 on 5033a31)
```
7e1aa55 fix: accept the RFC 850 and asctime HTTP date formats as string dates
5033a31 chore: bump version
```
- run-tests with the fix: `Tests:       348 passed, 348 total`. After `git checkout HEAD~1`: `Tests:       346 passed, 346 total`. So "348 tests passed (346 before)" is true.
- ts-node, TZ=UTC, tz undefined and Europe/Athens: `Sunday, 06-Nov-94 08:49:37 GMT`, `Sun Nov  6 08:49:37 1994` and `Sun Nov 06 08:49:37 1994` all give `1994-11-06T08:49:37.000Z`. The zero-padded sentence is true.
- Plain npm scripts in the copy (no install): `npm run lint` exit 0, `npm run build` exit 0, `npm run format:check` exit 0 (it failed once on my own scratch file chk.ts, then passed after I deleted it), `npm test` exit 0 with `Tests:       348 passed, 348 total`.
- `grep -n "—" PR.md`: no em dashes. Last line is exactly the disclosure sentence. Commit has no trailers.

## Round-1 findings, status
1. Stale base and counts: FIXED. PR.md says 5033a31, 348/346; full-check.log ends `full-check exit 0` with 348 passed. Rebased box ticked after a real rebase.
2. Ticked boxes naming commands not run: FIXED by unticking, but see finding C below.
3. Description too long, restates diff: PARTLY. The two restating sentences are gone. But the section grew again (ef172bd sentence, "These two formats used to throw", zero-padded sentence). It is about 17 lines with the repro fence, against 2-10 lines of prose in merged fixes (POLICY.md line 12). See finding B.
4. Empty `Fixes #` and Related Issues stubs: FIXED (`None.`).
5. Commit body: FIXED. Body is five lines, states the GMT decision, no diff restatement. Subject unchanged.
6. Changes Made padding: not changed ("one test per newly accepted format"). Trivial, optional.
7. Tests style: no change needed.

## New and remaining findings

A. WRONG COMMIT HASH (must change). PR.md says: "That list came from commit ef172bd". `git merge-base --is-ancestor ef172bd HEAD` in the fixed clone prints `ef172bd-NOT-ancestor`. ef172bd is a pull-request-head commit that exists only in the fetched refs. The commit on master history is the squash:
```
9332e6b Vano Devium readme: switched from moment to luxon (#252)
```
`git show 9332e6b -- README.md` contains ``+- [`HTTP and RFC2822`](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)``, and `git log -S"HTTP and RFC2822" -- README.md` lists 9332e6b (then b5f4194, the TypeScript rewrite, which touched the line later). CONFIRMATION.md already says 9332e6b. A maintainer who runs `git show ef172bd` on a normal clone gets "bad object". Replace ef172bd with `9332e6b (#252)`. SYNTHESIS.md's optional item also carries the wrong hash; the operator should fix it there too.

B. Description length. Exact replacement for everything between `## Description` and `## Type of Change` (drops the repro fence, which repeats the first sentence, and the zero-padded sentence, which no one asked about):
```
`new CronDate('Sunday, 06-Nov-94 08:49:37 GMT', 'UTC')` and `new CronDate('Sun Nov  6 08:49:37 1994', 'UTC')` throw `CronDate: unhandled timestamp`. README.md:85 says "When using string dates, the following formats are supported:" and README.md:88 lists "HTTP and RFC2822". `Sun, 06 Nov 1994 08:49:37 GMT` works only because it is also valid RFC 2822. The README list was added in 9332e6b (#252), which linked "HTTP and RFC2822" to luxon's parsing section of the same name.

The fix tries `DateTime.fromHTTP` last (`src/CronDate.ts:54`), so inputs that parse today never reach it. Both strings now give `1994-11-06T08:49:37.000Z`.

`fromHTTP` reads every HTTP date as GMT, so the asctime form, which has no zone, ignores `tz`. `Mon, 4 Jan 2021 10:00:00` is read in `tz`. These two formats used to throw, so a caller who passes a zone-less asctime string meant as local time now gets a GMT date instead of an error. I did not add zone handling. If you prefer asctime in `tz`, say so and I will change it. If "HTTP" meant only the first form, the README line should change instead.
```
Every sentence was run or read: the throws (red.log, revert.log), 348/346 and the Athens case (above), sideeffect.log (`Mon, 4 Jan 2021 10:00:00` unchanged), README lines (`sed -n 80,92p README.md`), 9332e6b (above). If the operator prefers to keep the repro fence, keep it and delete the first sentence instead. Do not keep both.

C. Disclaimers and unticked boxes. Testing says "I did not run the npm scripts themselves." and Additional Notes repeats it ("...ran through the full check, not through the npm scripts named above, so those boxes are not ticked."). That is process chatter, said twice, and it leaves `npm test`, lint, build and "No new TypeScript errors" unticked although the checks are green. I ran the scripts in the copy (results above), so the cheap and honest fix is: the operator runs `npm test`, `npm run lint`, `npm run build`, `npm run format:check` on the Mac, then ticks "All tests pass (`npm test`)", "ESLint checks pass", "TypeScript compilation successful", "No new TypeScript errors or warnings", deletes "I did not run the npm scripts themselves.", and replaces Additional Notes with only the disclosure line. `npm run format` is `prettier --write`; leave that box unticked or run it and check `git status` is clean. If the operator will not run them, keep the current unticked boxes but delete the Additional Notes paragraph, since Testing already says it.

D. Minor. Testing sentence "(eslint, prettier `--check` on `src` and `tests`, build, tsd, jest with coverage thresholds)" is accurate but is a parenthesis the template does not ask for. Optional shorter form after C: "Two new tests in `tests/CronDate.test.ts` fail without the change with `CronDate: unhandled timestamp: ...` and pass with it. `npm test` passes: 348 tests (346 before)." Changes Made, optional: `- src/CronDate.ts: fall back to DateTime.fromHTTP.` and `- tests/CronDate.test.ts: RFC 850 and asctime cases.`

## Side-effect rule
Strings that parse today never reach `fromHTTP` (it is last in the `isValid ||` chain, src/CronDate.ts:54; sideeffect.log: only the two formats changed in three zones). Affected: callers who relied on a throw for RFC 850 or asctime strings (very unlikely), and callers who now pass a zone-less asctime string meant as local time and get GMT with no error (low). The PR states the second. Acceptable, not a DROP. Security angle: none.

## After reading CONFIRMATION.md
Its round-2 correction note on "No newer commits" is accurate. It cites 9332e6b, which is correct and disagrees with PR.md. Its "README.md:87-89" differs from PR.md's 85 and 88; both are right (85 is the sentence, 87-89 the list).

## Not checked
GitHub (open and closed PRs and issues, maintainer reaction), the operator's Mac command, luxon versions other than the installed one, `npm run format` (the `--write` form), whether `dist/` left by my build matters (copy only). I did not open the rev0 files.
