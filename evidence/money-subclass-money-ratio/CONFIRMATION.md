# BUG-013 money-subclass-money-ratio: Money#/ on a Money subclass instance, divided by a plain Money

## Claim
Input: `Sub.new(100) / Money.new(10)` (`Sub = Class.new(Money)`, USD). Actual: a `Sub` of 1000 cents, not a Float. Expected: `10.0`. Source of expected: the method doc, `reference_docs/cite/api_lib_money_money_arithmetic.txt:118`, "+Money/Numeric+ returns +Money+. +Money/Money+ returns +Float+." (the same text is at `lib/money/money/arithmetic.rb:192`).

## Verdict
Verdict: CONFIRMED (low severity, narrow reach). Side-effect rule: a fix changes only a case that today returns a value 10x too large for USD, so no user is likely to rely on it. RBS: no signature change (`sig/lib/money/money/arithmetic.rbs:128` already says `-> (Money | Float)`).

## Repro source
`/work/batch/runs/money/scratch/confirm-money-subclass-money-ratio-confirmer/repro.rb` (my own). It divides in five receiver/divisor combinations plus a zero divisor, and exits 1 on any wrong result. Settings: library defaults, `Money.add_rate("EUR", "USD", 2)`. That rate is added to the default bank only inside the script's process, so there is nothing to reset.

## Verbatim output (unpatched, exit=1)
```
Money / Money: actual=10.0 expected=10.0 ok
Money / Sub: actual=10.0 expected=10.0 ok
Sub / Sub: actual=10.0 expected=10.0 ok
Sub / Money: actual=#<Sub fractional:1000 currency:USD> expected=10.0 WRONG
Sub / Money(4 EUR): actual=#<Sub fractional:2500 currency:USD> expected=12.5 WRONG
Sub / Money(0): ZeroDivisionError: divided by zero
exit=1
```
With the run's one-token patch applied in the clone (`is_a?(self.class)` to `is_a?(Money)`), the same script gave all `ok`, zero divisor "divided by Money(0)", exit=0, and `run-tests` gave `502 examples, 0 failures`. Patch reverted afterwards (`git checkout lib`).

## Expectation check
- Doc: `grep -n "Money/Money" reference_docs/cite/*` gives only `api_lib_money_money_arithmetic.txt:118`. The `@example` at `arithmetic.rb:202` says `Money.new(100) / Money.new(10) #=> 10.0`.
- The documented text names `Money`, not "same class". Every other Money-vs-Money check uses `is_a?(Money)` (`==`, `<=>`, `+`, `-`, `divmod`, `remainder`, per BUGS.md; I did not re-check each).
- History: `git blame` line 205 is ca7b3456 (a lint commit, only touched the line). `git log -S"is_a?(self.class)"` gives 6abbc40 "Support subclassing of Money by never instantiating it by name". `git show 6abbc40` shows it changed `if value.is_a?(Money)` to `if value.is_a?(self.class)` in `/`. The commit's purpose was `self.class.new` instead of `Money.new`, so the guard change looks like an over-broad replace. That is my inference, not stated in the commit.
- Tests: `spec/money/arithmetic_spec.rb:588-595` divide a subclass by a Fixnum and by a subclass. None divides a subclass by plain Money. CHANGELOG: no line on this. Not intentional as far as I can find.

## Duplicate search
Closest match: none found. `known_open_bugs.md` (operator gh export 2026-10-05) lists open issues #1109 "Division by zero", #1104, #1099, and PRs #1213, #1159, #1120, #1098, #1092, #1069; none touches `arithmetic.rb`. #1109 is titled "Division by zero" only; I cannot see its body, so it may be about a different case (zero divisor). In `upstream-check`, no `pr/<N>` head changes the `/` method or its `is_a?(self.class)` line (checked pr heads whose diff to arithmetic.rb mentions `self.class`/`is_a?`; pr/1061 changes `**` only). Git cannot tell open from closed, and I did not search the tracker.

## Dup queries
- `Money subclass divide Money Float`
- `is_a?(self.class) arithmetic`
- `Money#/ subclass ratio`
- `subclass of Money division returns Money instead of Float`
- `"divided by Money(0)" subclass`

## Security line
No: a wrong value on ordinary input, no hang, crash, leak or bypass.

## Likely maintainer pushback
- "Subclass-vs-sibling mixing is unsupported." Reply: `+`, `-`, `==` and `divmod` already accept plain Money with a subclass receiver (spec lines 276-277, 308-309), and `Money / Sub` works.
- "Narrow case." True; it needs a Money subclass receiver and a different-class Money divisor. The wrong answer is silent, though (10x for USD, and the divisor's currency is ignored).
- The #1109 "Division by zero" issue may be read as related; the zero-divisor error message differs only as a side effect here.
- Not checked: other arithmetic paths with the same `self.class` pattern (only one `is_a?(self.class)` in `lib/`, by grep), and no Rails or other subclass users.

## Parent re-run
Command: `cd /work/batch/runs/money/scratch/confirm-money-subclass-money-ratio-confirmer && LANG=C.UTF-8 BUNDLE_GEMFILE=$PWD/Gemfile bundle exec ruby -Ilib -rmoney repro.rb`
Exit code: 1 (bug present, as expected)
```
Money / Money: actual=10.0 expected=10.0 ok
Money / Sub: actual=10.0 expected=10.0 ok
Sub / Sub: actual=10.0 expected=10.0 ok
Sub / Money: actual=#<Sub fractional:1000 currency:USD> expected=10.0 WRONG
Sub / Money(4 EUR): actual=#<Sub fractional:2500 currency:USD> expected=12.5 WRONG
Sub / Money(0): ZeroDivisionError: divided by zero
```
