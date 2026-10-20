# cRonstrue #423, round 2: Vietnamese month step

Prepared 2026-10-19 (about 22:10 UTC) after Brady Holt's "changes requested" review (5578034498, 21:32:53 UTC). His comment, as read from the PR page through a fetch tool, is "FYI @andrewstellman" on Copilot's thread about the vi verbose-off output. Nothing has been pushed or posted.

## The change

One new commit on top of the PR head 4b78257, so the branch fast-forwards and no force push is needed:

    239e2adb82cdf5138b6bd1e8f178f1aae735cce2  Use "mỗi %s tháng" for a month step in Vietnamese
    author and committer: Andrew Stellman <andrew@stellman.com>, no trailers
    src/i18n/locales/vi.ts | 2 +-
    test/i18n.ts           | 13 +++++++++++++

`commaEveryX0Months()` in `vi.ts` changes from `", mỗi ngày %s tháng"` to `", mỗi %s tháng"`, the same pattern as the vi phrases for days (`", mỗi %s ngày"`) and years (`", mỗi %s năm"`). The old string has been there since the vi locale was added (#285, 2023). Two vi tests are added in `test/i18n.ts` (there was no vi block before).

| Expression (vi, verbose off) | main 7211a58 | PR head 4b78257 | Round 2 |
|---|---|---|---|
| `0 9 * */3 *` | Vào 09:00 3 tháng | Vào 09:00 3 tháng | Vào 09:00, mỗi 3 tháng |
| `0 9 * 2,3-9/2 *` | Vào 09:00chỉ trong Tháng 2 và  2 tháng, Tháng 3 đến Tháng 9 | Vào 09:00, chỉ trong Tháng 2 và mỗi ngày 2 tháng, Tháng 3 đến Tháng 9 | Vào 09:00, chỉ trong Tháng 2 và mỗi 2 tháng, Tháng 3 đến Tháng 9 |

## Checks (cloud workspace, Node v22.22.0, Linux)

- Full suite on 239e2ad: 411 passing (409 before plus the 2 new tests). With only `vi.ts` reverted: 409 passing, 2 failing (the new tests). Log: `suite-round2.log`.
- Differential run, all 42 locales, 3,750 expressions (5 sample values for each field, 6 for day of week), verbose on and off (`probe.ts`; outputs in the three `.tsv.gz` files): against the PR head, output changed only in `vi` (3,000 outputs, all with a month step). Every changed output now reads "mỗi N tháng"; none reads "mỗi ngày N tháng". vi concise outputs with "mỗi ngày N tháng" or a time glued to "N tháng": 770 on the PR head, 0 on round 2.
- Merges cleanly with main 7211a58 (3.35.0). No commit on main since 872fffe touches `src/expressionDescriptor.ts`.
- `vi.ts` already failed `prettier --check` before this change (mixed CRLF and LF line endings); the commit keeps the file's line endings and does not reformat it.
- Not checked: a native speaker's view of "mỗi %s tháng"; a Mac run.
- Not changed (out of scope): `sw` and `id` have the same kind of prefix clash with their every-day phrase, on day phrases, already on main. A general fix in `transformVerbosity()` (matching only the whole every-day phrase) was tried and changed concise output in ar, bg, ja, ru and tg as well, so it is not used.

## To push (in your own clone of your fork)

Use the bundle; it carries the exact commit 239e2ad. The patch file also works, but `vi.ts` has CRLF line endings, so it needs `git am --keep-cr`.

    cd <your cRonstrue clone>
    git checkout fix-list-step-separator
    git log -1 --format=%H        # must be 4b78257d8df1d28eb9819a77e312ff9cebc042e0
    git fetch <path>/fix-list-step-separator-round2.bundle fix-list-step-separator:round2
    git merge --ff-only round2
    git log -1 --format=%H        # must be 239e2adb82cdf5138b6bd1e8f178f1aae735cce2
    npm ci --ignore-scripts && npm test    # expect 411 passing
    git push <your fork remote> fix-list-step-separator
    git branch -d round2

Then, on the PR, reply in Brady's comment thread (text below) and use "Re-request review".

## Reply to post (in Brady's "FYI" thread)

> Thanks. The cause is in the vi locale: the month step phrase was ", mỗi ngày %s tháng", and its first words are the every-day phrase that the verbose-off cleanup deletes, so a standalone `0 9 * */3 *` already printed "Vào 09:00 3 tháng". I pushed 239e2ad, which uses ", mỗi %s tháng" like the vi phrases for days and years, with two vi tests. `0 9 * */3 *` now prints "Vào 09:00, mỗi 3 tháng" and `0 9 * 2,3-9/2 *` prints "Vào 09:00, chỉ trong Tháng 2 và mỗi 2 tháng, Tháng 3 đến Tháng 9". Only vi output with a month step changes. I'm not a Vietnamese speaker, so the wording follows the locale's own pattern.
