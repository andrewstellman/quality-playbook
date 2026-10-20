**Title:** fix: accept the RFC 850 and asctime HTTP date formats as string dates

## Description

String dates in the RFC 850 and asctime HTTP formats throw, although the README lists "HTTP and RFC2822" as supported (README.md:88).

```
new CronDate('Sunday, 06-Nov-94 08:49:37 GMT', 'UTC')  // Error: CronDate: unhandled timestamp
new CronDate('Sun Nov  6 08:49:37 1994', 'UTC')        // Error: CronDate: unhandled timestamp
```

Both should give `1994-11-06T08:49:37.000Z`, as luxon's `DateTime.fromHTTP` does. The change tries `fromHTTP` last, so strings that parse today are unchanged.

`fromHTTP` reads the asctime form, which has no zone, as GMT rather than in the `tz` option. If you would rather have it read in `tz`, or meant only the RFC 1123 form, say so.

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

Two new tests in `tests/CronDate.test.ts` fail without the change and pass with it. The project's full check (eslint, prettier `--check`, build, tsd, jest with coverage) passes with 348 tests. I did not run the npm scripts by name.

- [ ] All tests pass (`npm test`)
- [x] Code coverage is maintained or improved

## Changes Made

List the main changes in this pull request:

- `src/CronDate.ts`: try `DateTime.fromHTTP` after the existing string formats.
- `tests/CronDate.test.ts`: one test per newly accepted format.

## Related Issues

List any issues that are related to this PR:

None.

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
- [ ] ESLint checks pass (`npm run lint`)
- [ ] Prettier formatting applied (`npm run format`)
- [ ] TypeScript compilation successful (`npm run build`)
- [ ] No new TypeScript errors or warnings

## Checklist

- [ ] I have read and followed the [CONTRIBUTING.md](../../CONTRIBUTING.md) guidelines
- [ ] My code follows the project's coding standards
- [x] I have added tests for my changes
- [x] All tests pass locally
- [ ] I have updated documentation as needed
- [ ] My commits have clear, descriptive messages
- [x] I have rebased my branch on the latest master

## Additional Notes

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
