With a reference timezone that differs from the process timezone, "this week/month/year", "last night" and dates without a year ("Feb 15", "15 Feb", "2/15", "February") use the process timezone's calendar. "today" and "next month" already use the reference timezone's.

```ts
// process at TZ=UTC
const ref = { instant: new Date("2012-07-31T22:00:00Z"), timezone: "JST" }  // Aug 1, 07:00 in Tokyo
chrono.parse("this month", ref)[0].start.get("month")  // 7, expected 8
```

These parsers read the reference instant directly. The change makes them call `context.reference.getDateWithAdjustedTimezone()`, as `ENWeekdayParser` and `ENEndOfCurrentMonthParser` already do.

Only references with a `timezone` that differs from the process timezone get different results. A plain `Date` reference behaves as before. `SlashDateFormatParser` is shared, so other locales that use it are affected too. I added a test for English only.

The new test in `test/en/en_relative.test.ts` fails before the change and passes after it. The full suite passes (754 tests).

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
