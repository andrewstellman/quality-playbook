**Title:** fix: accept the RFC 850 and asctime HTTP date formats as string dates

## Description

String dates in the RFC 850 and asctime HTTP date formats throw in `CronDate`, although the README lists HTTP as a supported format.

Repro (`TZ=UTC`, ts-node against `src/`):

```
new CronDate('Sun, 06 Nov 1994 08:49:37 GMT', 'UTC')       -> 1994-11-06T08:49:37.000Z
new CronDate('Sunday, 06-Nov-94 08:49:37 GMT', 'UTC')      -> Error: CronDate: unhandled timestamp: Sunday, 06-Nov-94 08:49:37 GMT
new CronDate('Sun Nov  6 08:49:37 1994', 'UTC')            -> Error: CronDate: unhandled timestamp: Sun Nov  6 08:49:37 1994
expected for the last two                                    1994-11-06T08:49:37.000Z (what luxon `DateTime.fromHTTP` returns)
```

The README says "When using string dates, the following formats are supported:" and lists "- HTTP and RFC2822" (README.md:85 and README.md:88).

The constructor tries `fromISO`, `fromRFC2822`, `fromSQL` and one `fromFormat` pattern (`src/CronDate.ts:50-53`) and never `DateTime.fromHTTP`. The first HTTP form (`Sun, 06 Nov 1994 08:49:37 GMT`) only works because it is also valid RFC 2822.

The fix adds `DateTime.fromHTTP` as the last attempt (`src/CronDate.ts:54`). Inputs that parse today never reach it. I compared the old chain with the new one on 13 inputs in three zones (undefined, UTC, Europe/Athens): only the RFC 850 and asctime strings changed, from throwing to a date.

Zone: `fromHTTP` reads every HTTP date as GMT, including the asctime form, which has no zone. I ran `new CronDate('Sun Nov  6 08:49:37 1994', 'Europe/Athens')` and it gives `1994-11-06T08:49:37.000Z`. This differs from `Mon, 4 Jan 2021 10:00:00` (RFC 2822 without offset), which is read in the `tz` option. If you prefer asctime in `tz`, say so and I will change it.

If only the RFC 1123 form was meant by "HTTP", the README line is what should change instead.

Fixes # (issue number if applicable)

## Type of Change

Please check the relevant option:

- [x] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update (changes to documentation only)
- [ ] Code refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Test improvement or addition
- [ ] Build/CI/tooling changes

## Testing

Describe how you've tested your changes:

Two new tests in `tests/CronDate.test.ts` (`HTTP RFC 850`, `HTTP asctime, read as GMT`) fail without the change with `CronDate: unhandled timestamp: ...` and pass with it. I ran the project's full check (eslint, prettier `--check` on `src` and `tests`, build, tsd, jest with coverage thresholds) and it ended `full-check exit 0` with 340 tests passed (338 before). I did not run the npm scripts themselves.

- [x] All tests pass (`npm test`)
- [x] Code coverage is maintained or improved

## Changes Made

List the main changes in this pull request:

- `src/CronDate.ts`: try `DateTime.fromHTTP` after the existing string formats.
- `tests/CronDate.test.ts`: one test per newly accepted format.

## Related Issues

List any issues that are related to this PR:

- Closes #
- Related to #
- Fixes #

## Documentation

- [ ] Code is self-documenting with clear variable/function names
- [ ] Complex logic has helpful comments
- [ ] Public API changes are documented with JSDoc
- [ ] README updated (if user-facing changes)

README not changed: it already lists HTTP.

## Performance

If this PR affects performance:

- [ ] Benchmarks were run before and after changes
- [ ] Performance impact is acceptable or improved
- [ ] Results are documented in comments or PR description

## Breaking Changes

If this introduces breaking changes:

- [ ] Breaking changes are clearly documented
- [ ] Migration guide provided (if needed)
- [ ] Version bump strategy discussed
- [ ] Backwards compatibility considered

## Code Quality

- [ ] Code follows project style guidelines
- [x] ESLint checks pass (`npm run lint`)
- [x] Prettier formatting applied (`npm run format`)
- [x] TypeScript compilation successful (`npm run build`)
- [ ] No new TypeScript errors or warnings

## Checklist

- [ ] I have read and followed the [CONTRIBUTING.md](../../CONTRIBUTING.md) guidelines
- [ ] My code follows the project's coding standards
- [x] I have added tests for my changes
- [x] All tests pass locally
- [ ] I have updated documentation as needed
- [ ] My commits have clear, descriptive messages
- [ ] I have rebased my branch on the latest master

## Additional Notes

The change is made on upstream master at 5b08cdf. The Testing and Code Quality boxes above were ticked from the full check (eslint, prettier check, build and tsd, jest with coverage), which covers the same steps as the named npm scripts.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
