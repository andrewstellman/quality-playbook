# O4 round 2: SHIP (medium)

Role: not-a-bug, round 2. I argued the maintainer's side again against the rebased commit and the rewritten PR.md. I still cannot make it stick. One optional wording change (finding 1).

## Round-1 findings

1. Stale base (5b08cdf vs 5033a31): ADDRESSED. PR.md Additional Notes now says "upstream master at 5033a31". Evidence I ran: fresh clone of upstream-check master (5033a31), `run-tests` printed `Tests:       346 passed, 346 total`; after `git am` of the OUT patch (no conflicts) `Tests:       348 passed, 348 total`. That matches PR.md "348 tests passed (346 before)". OUT/full-check.log ends `Tests:       348 passed, 348 total` / `full-check exit 0`. red.log: `2 failed, 47 skipped, 49 total`; green.log: `49 passed`; revert.log: `2 failed, 47 passed`. CONFIRMATION.md now carries a dated correction of "No newer commits". Fixed clone HEAD is 7e1aa55 on 5033a31, author Andrew Stellman, no trailers in the commit body.
2. ef172bd sentence: ADDED, see finding 1 below for the one problem.
3. "inherited from fromHTTP" sentence: ADDED ("This is what `DateTime.fromHTTP` does; I did not add zone handling.").
4. Ticked npm boxes: ADDRESSED differently. The four npm boxes (`npm test`, lint, format, build) are now unticked and the Testing text keeps "I did not run the npm scripts themselves." Remaining ticks: "Code coverage is maintained or improved" (full-check enforces thresholds, log above), "All tests pass locally", tests added, rebased (true after the rebase). Acceptable.
5. Issue-first process worry: no text change was needed; POLICY.md says no issue for a bug fix. Unchanged.

## The ef172bd sentence

PR.md: "That list came from commit ef172bd, which linked 'HTTP and RFC2822' to luxon's parsing section of the same name."
`git show ef172bd` in upstream-check shows author Vano Devium, 2021-12-07, "readme: switched from moment to luxon", adding:
`+- [`HTTP and RFC2822`](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)`
(with `ISO8601` above it and `SQL` below). The sentence is TRUE.
But: `git merge-base --is-ancestor ef172bd master` returns rc=1, and `git for-each-ref --contains ef172bd` prints only `refs/remotes/pr/252`. So ef172bd is a PR #252 branch commit, not on master. `git log master --oneline | grep` finds `9332e6b readme: switched from moment to luxon (#252)` instead, and `git diff ef172bd 9332e6b -- README.md` prints nothing (same README). In a plain clone of master a maintainer cannot resolve ef172bd.

## New findings

1. (Optional, low) Replace "ef172bd" with "9332e6b (#252)" in PR.md. Same content, but it is the commit on master's history. If the operator keeps ef172bd, it is still true. I did not check whether GitHub resolves ef172bd from the PR page.
2. No other new problem. Checked by running (fixed code, TZ=UTC, ts-node --transpile-only, my copy):
   - `Sunday, 06-Nov-94 08:49:37 GMT`, `Sun Nov  6 08:49:37 1994` with UTC and Europe/Athens: `1994-11-06T08:49:37.000Z` (the repro block and Zone paragraph are true).
   - `Sun Nov 06 08:49:37 1994` (zero-padded) with Europe/Athens: `1994-11-06T08:49:37.000Z` (the new sentence is true).
   - `Mon, 4 Jan 2021 10:00:00` with Europe/Athens: `2021-01-04T08:00:00.000Z` (RFC 2822 without offset is read in tz; the contrast sentence is true).
   - `Sun Nov 6 08:49:37 1994` (single digit, one space): still throws `CronDate: unhandled timestamp`.
   - README.md at 5033a31: line 85 "When using string dates, the following formats are supported:", line 88 "- HTTP and RFC2822". Line numbers right.
   - src/CronDate.ts and tests/CronDate.test.ts in my 5033a31+patch copy are byte-identical to the fixed clone's HEAD.
3. sideeffect.log is dated 2026-10-07 (run on the pre-rebase clone) and was not regenerated. PR.md no longer cites it ("13 inputs" sentence removed), and the code is identical, so no claim depends on it.

## Maintainer-side arguments, re-run

- "HTTP means RFC 1123 only; the rest is obsolete." Forced to concede by the README list's origin: `- [`HTTP and RFC2822`](...#/parsing?id=http-and-rfc2822)` in 9332e6b, a link to luxon's section that covers fromHTTP. PR.md now shows this and offers the README change as the alternative. No test, comment or doc in the repo limits HTTP to one form.
- "Previously declined": `git log -S'fromHTTP' --all --oneline` in upstream-check printed nothing; `-S'HTTP and RFC2822'` found only ef172bd and 9332e6b. known_open_bugs.md (2026-10-05, open items only) has nothing on string formats. #446 touches src/CronDate.ts, but its diff against its merge base adds a method near line 339; the fix is at line 54. No textual overlap seen (a trial merge failed with "not something we can merge", so I did not test it).
- "Not worth the churn": one source line, 1 test per format, inputs that parse today never reach the new line (last link of the `||` chain).

## Side-effect rule

Affected: callers passing RFC 850 or asctime strings, who got an Error and now get a date. Zone-less asctime meant as local time is read as GMT. PR.md states both facts plainly ("These two formats used to throw. A caller who passes a zone-less asctime string that was meant as local time now gets a GMT date instead of an error."). Likelihood low, nobody can depend on a throw they did not know was a feature. Not a drop reason.

## Not checked

Closed issues and PRs on the forge; whether GitHub resolves ef172bd; the four npm scripts by name; the operator's Mac command; luxon other than the installed one; a real merge with pr/446; full-check (I used the logged run and my own `run-tests` only).
