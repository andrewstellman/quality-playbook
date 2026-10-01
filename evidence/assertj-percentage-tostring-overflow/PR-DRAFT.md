# PR draft (not submitted)

**Base:** `main` (CONTRIBUTING: "Rebase your PR on `main` (no merge!)")
**Title:** `Fix Percentage.toString() for integral values larger than Integer.MAX_VALUE`

## Body

#### Check List:
* Fixes #??? (ignore if not applicable)
* Unit tests : YES
* Javadoc with a code example (on API only) : NA
* PR meets the [contributing guidelines](https://github.com/assertj/assertj/blob/main/CONTRIBUTING.md)

`Percentage.toString()` casts integral values to `int`:

```java
return noFractionalPart() ? "%s%%".formatted((int) value) : "%s%%".formatted(value);
```

`withPercentage()` accepts any non-negative `double`, so a large integral value saturates at `Integer.MAX_VALUE`. For example, `withPercentage(3_000_000_000d).toString()` returns `2147483647%`. The wrong number then appears in `isCloseTo`/`isNotCloseTo` failure messages:

```
by more than 2147483647% but difference was 99.99999998999999%.
```

This PR prints the integral branch with `new BigDecimal(value).toPlainString()`. That is exact for any integral `double` and doesn't depend on the locale, and `10.0` still prints as `10%`. Fractional values are unchanged.

Tests: two rows added to `Percentage_Test.toString_should_display_fractional_part_when_present` (`3000000000` and `1e20`). Both fail on `main` and pass with the fix. `assertj-core` and `assertj-core-tests` pass in full (14441 + 6340), and `spotless:check` / `license:check` are clean.

The bug was found by a [Quality Playbook](https://github.com/andrewstellman/quality-playbook) code-review run. Reproduction, the test, and the fix were done by Claude (Anthropic), and I reviewed them before submitting.

## Before opening (for Andrew)
- [ ] Decide whether CONTRIBUTING's Legal Disclaimer ("You will only submit contributions where you have authored 100% of the content") is compatible with submitting Claude-authored code. Adjust or keep the disclosure paragraph above.
- [ ] Choose `BigDecimal` (as patched) or the smaller `(long) value`. With `(long)`, drop the `1e20` test row, since it would print `9223372036854775807%`.
- [ ] Optional: open an issue first. CONTRIBUTING does not require one, and the template says "ignore if not applicable".
- No DCO/Signed-off-by is required by this project.
