# S8 round 2: SHIP (high)

Role: S8 compliance, round 2. Scratch copy: scratch/panel2-cron-parser-http-date-formats-S8/. The fixed clone was only read.

## Round-1 findings, one by one

1. Stale base: FIXED. `git clone upstream-check` is at `5033a31 chore: bump version`. `git am OUT/0001-*.patch` applied cleanly (new hash 0b83394 in my copy). `git diff HEAD~1` of my copy and of the fixed clone have the same md5 (f14589daa96716e341d53d8d73a92d62). The fixed clone is `7e1aa55` on `5033a31`. My `format-patch` output differs from the shipped patch only in the `From <hash>` line. Code and tests are unchanged from round 1 (one line in `src/CronDate.ts`, two tests in `tests/CronDate.test.ts`).
2. Counts: FIXED. PR.md says "348 tests passed (346 before)". I ran `bin/full-check` on my copy: `All matched files use Prettier code style!`, `Tests: 348 passed, 348 total`, `full-check exit 0`. `OUT/full-check.log` ends the same way (`Tests: 348 passed, 348 total`, `full-check exit 0`). `red.log` shows `2 failed, 47 skipped, 49 total`, `revert.log` `2 failed, 47 passed`, `green.log` `49 passed`, which supports "fail without the change".
3. Additional Notes sentence: FIXED. "The change is made on upstream master at 5033a31." The rebased box is ticked and that is now true.
4. Ticked npm-script boxes: FIXED. `All tests pass (npm test)`, `npm run lint`, `npm run format`, `npm run build` are unticked. Ticked: Bug fix, `Code coverage is maintained or improved` (full-check enforces thresholds, 100%), `I have added tests`, `All tests pass locally` (jest ran), `rebased`. The Testing sentence "I did not run the npm scripts themselves" and the Additional Notes sentence now agree with the unticked boxes. No contradiction left.
5. Optional unticked boxes (read CONTRIBUTING, clear commit messages, coding standards): left unticked. That is the safe direction and not a rejection ground.
6. Template stubs: FIXED. The Description "Fixes #" line is gone and Related Issues says `None.` The text does not claim "no duplicate". Slight deviation: the three empty `Closes #` / `Related to #` / `Fixes #` bullets were deleted, and so were the "Brief description" and "Any additional information" prompts. All 11 headings are kept (Description, Type of Change, Testing, Changes Made, Related Issues, Documentation, Performance, Breaking Changes, Code Quality, Checklist, Additional Notes). Placeholder prompts are not something a maintainer checks. SYNTHESIS finding 4 asked for it.
7. "13 inputs in three zones": the sentence was removed from PR.md. `sideeffect.log` ends `inputs that parsed before and now differ: 0`. Nothing left to verify.

## Process checks

- Author and committer in the fixed clone: `Andrew Stellman <andrew@stellman.com>`. Patch `From:` is the same. No `Signed-off-by`, `Co-Authored-By` or `Assisted-by` in the patch or the commit message (read both). POLICY.md: CLA/DCO none found; AI policy silent. So no trailer is required.
- Subject `fix: accept the RFC 850 and asctime HTTP date formats as string dates`: lower-case Conventional Commits (CONTRIBUTING.md:139-141 per POLICY.md). PR title in PR.md is the same text. Body is 5 lines of prose (POLICY.md says merged outside fixes have 2-10), names the cause and the GMT decision, does not restate the diff.
- CHANGELOG.md not touched (patch stat: `src/CronDate.ts`, `tests/CronDate.test.ts` only). Release workflow writes it from PR titles (POLICY.md).
- Tests in the existing `tests/CronDate.test.ts`, as POLICY.md records for merged fixes. No new file, so no licence header question. README untouched and PR.md says why.
- Disclosure: last line of PR.md is exactly `Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.` (checked with od, ends with a newline). No extension is required because POLICY.md quotes no AI rule.
- No em or en dashes in PR.md or the patch (grep -P returned nothing).
- Security tag: none. A clean `Error` on an obsolete date format; SECURITY.md puts correctness bugs in the normal path.
- Claims I re-checked against the repo: README.md:85 "When using string dates, the following formats are supported:" and README.md:88 "- HTTP and RFC2822" (sed on my copy). `src/CronDate.ts:54` is the `fromHTTP` line. `git show ef172bd` (Vano Devium, 2021-12-07, "readme: switched from moment to luxon") adds the list with `[HTTP and RFC2822](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)`, so the ef172bd sentence is true. `Sun Nov 06 08:49:37 1994` with `Europe/Athens` gives `1994-11-06T08:49:37.000Z` (ts-node run on my copy), so the zero-padded sentence is true. The Athens asctime result and the "RFC 2822 without offset is read in tz" contrast match `sideeffect.log` (Athens 10:00 gives 08:00Z).
- CONFIRMATION.md carries a dated correction of the "No newer commits" line. Its old "338 passed" repro line is labelled as the 5b08cdf run; it is not part of the PR text.

## Would it be rejected on process grounds?

No. Branch base, commit style, author, no trailers, no changelog edit, tests in the right file, template headings kept, ticks match commands run, disclosure line exact. Remaining risk is substantive (a maintainer may prefer a README edit; PR.md offers that) and not process.

## Not checked

- GitHub: closed issues and PRs, maintainer replies, whether an issue is wanted first. Tracker, API and `gh` are unreachable.
- The npm scripts by name (`npm test`, `npm run lint`, `npm run format`, `npm run build`). I ran `bin/full-check` only. PR.md says the same.
- The operator's Mac command (`npm ci --ignore-scripts && TZ=UTC npx jest`), luxon versions other than the installed one, and open PR #446 conflicts (not read).
- I did not re-read the sideeffect.log header lines beyond its tail and the 13 lines shown; I did not re-run the old-versus-new comparison.
