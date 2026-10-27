# money: `Money#/` on a Money subclass returns a Money instead of a Float for a plain Money divisor

Status: **ready for the operator's review.**

## The project
`money` is a Ruby gem that represents an amount of money with a currency. It does arithmetic, allocation (splitting an amount without losing a cent), rounding, currency exchange through a bank object, and formatting. Repository: https://github.com/RubyMoney/money (branch `main`, version 7.1.1 plus unreleased fixes).

## The bug
Dividing one `Money` by another `Money` is documented to give a plain ratio. The method docs say: "+Money/Numeric+ returns +Money+. +Money/Money+ returns +Float+." (`lib/money/money/arithmetic.rb:193`). The example in the same comment is `Money.new(100) / Money.new(10) #=> 10.0` (line 202).

Some applications subclass `Money`. If the left side is an instance of a subclass and the right side is a plain `Money` (or an instance of a different subclass), the method does not see a `Money` divisor. Its check is `other.is_a?(self.class)` (line 205), and `self.class` is the subclass. The plain `Money` falls through to the branch meant for numbers. So `Sub.new(1000, "USD") / Money.new(100, "USD")` returns a `Sub` holding 1000 cents instead of `10.0`. A zero plain `Money` divisor raises `divided by zero` instead of `divided by Money(0)`. A divisor in another currency is not converted: its cent amount is used as a bare number.

It went unnoticed because it needs a subclass on the left and a different class on the right, and the result is a plausible-looking `Money`, not an error. The other `Money` checks in the file use `is_a?(Money)` (lines 41, 66, 244, 302). The only `is_a?(self.class)` in `lib/` came from commit 6abbc40 ("Support subclassing of Money by never instantiating it by name"), per the confirmer's `git log -S`. Whether the narrow check was meant is not stated anywhere I could find.

Security angle: none. The wrong value is silent but there is no crash, hang, leak or bypass.

## The fix
One token. The divisor test becomes `other.is_a?(Money)`, so any `Money` takes the ratio branch, as it does for a plain `Money` receiver. The patch also adds one spec, a CHANGELOG bullet and the `AUTHORS` line (CONTRIBUTING.md:15-16 asks for both). No RBS change: `sig/lib/money/money/arithmetic.rbs:128` already says `-> (Money | Float)`.

Commit: subject only, `Return a Float from Money#/ for a plain Money divisor on a subclass`, authored by Andrew Stellman, no trailers (POLICY.md: subject only, no body).

```diff
diff --git a/AUTHORS b/AUTHORS
index 2d9b131..bb78bb6 100644
--- a/AUTHORS
+++ b/AUTHORS
@@ -7,6 +7,7 @@ AmineAffifSkello
 Andreas Loupasakis
 Andrei
 Andrei Andriichuk
+Andrew Stellman
 Andrew White
 Andrius Chamentauskas
 Anthony Hristov
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 519ff8f..adb06e8 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -2,6 +2,7 @@
 
 ## Unreleased
 
+- Fix `Money#/` on an instance of a `Money` subclass treating a plain `Money` divisor as a number, so it returned a `Money` instead of the documented `Float`
 - Fix `Money::Allocation.generate` converting a Rational with unlimited `to_d` precision. It now uses `Money.conversion_precision`
 - Fix `Money::Currency.reset!` keeping the cached key set, so a currency registered before the reset was still accepted by `Money::Currency.new` and raised `NoMethodError` instead of `UnknownCurrency`
 - Fix `Money::Bank::VariableExchange#import_rates` parsing `:json` with `JSON.load`, which instantiates any class named by a `json_class` key; it now uses `JSON.parse`
diff --git a/lib/money/money/arithmetic.rb b/lib/money/money/arithmetic.rb
index 9161dce..e43d95d 100644
--- a/lib/money/money/arithmetic.rb
+++ b/lib/money/money/arithmetic.rb
@@ -202,7 +202,7 @@ class Money
     #   Money.new(100) / Money.new(10) #=> 10.0
     #
     def /(other)
-      if other.is_a?(self.class)
+      if other.is_a?(Money)
         exchanged = other.exchange_to(currency)
         raise ZeroDivisionError, "divided by Money(0)" if exchanged.zero?
 
diff --git a/spec/money/arithmetic_spec.rb b/spec/money/arithmetic_spec.rb
index 5f1a4f7..4fcb48a 100644
--- a/spec/money/arithmetic_spec.rb
+++ b/spec/money/arithmetic_spec.rb
@@ -371,6 +371,13 @@ RSpec.describe Money::Arithmetic do
       expect(special_money_class.new(10_00, "USD") / 2).to be_a special_money_class
     end
 
+    it "returns a Float when dividing a subclass of Money by a Money" do
+      special_money_class = Class.new(Money)
+      ratio = special_money_class.new(10_00, "USD") / Money.new(1_00, "USD")
+      expect(ratio).to be_a Float
+      expect(ratio).to eq 10.0
+    end
+
     describe "rounding preference" do
       before do
         allow(Money).to receive(:rounding_mode).and_return(rounding_mode)
```

## Regression test
- Red: `expected #< fractional:1000 currency:USD> to be a kind of Float` (`red.log`, spec `returns a Float when dividing a subclass of Money by a Money`, `spec/money/arithmetic_spec.rb:377`).
- Green: touched file `116 examples, 0 failures` (`green.log`). Full suite `503 examples, 0 failures` (`suite.log`). Lint: `2 files inspected, no offenses detected` (`lint.log`).
- Revert: with only the `lib/` change reverted, the spec fails again with the same line (`revert.log`).
- Logs: `red.log`, `green.log`, `revert.log`, `suite.log`, `lint.log`.

## Knock-on effects (run 2026-10-06)
- Callers of the changed code. `Money#/` has one definition, `lib/money/money/arithmetic.rb:204`. Inside `lib/` the only other call that goes through it is `Money#div` (`arithmetic.rb:229-230`, `self / value`), so `div` changes in the same way. `lib/money/money/allocation.rb:53` (`remaining_amount * part / parts_sum`) divides numbers, not `Money`, so it is not a caller. No other `lib/` code divides a `Money`. Ruby's `Numeric / Money` goes through `coerce` and `CoercedNumeric`, a different branch that this patch does not touch. The spec callers are in `spec/money/arithmetic_spec.rb`. Downstream gems that subclass `Money` were not checked.
- Before/after, freshly run with `knock_on.rb` (library defaults, rates added to the default bank inside the script's process only). Base is `HEAD~1` of the fixed clone, fixed is `HEAD`. Outputs: `knock_on.base.txt`, `knock_on.fixed.txt`. Both runs exit 0. Base suite there: `502 examples, 0 failures`; fixed: `503 examples, 0 failures`.

| Input | Base | Fixed | |
|---|---|---|---|
| `Money / Money` | `Float: 10.0` | `Float: 10.0` | same |
| `Money / Money (GBP, rate 2)` | `Float: 1.25` | `Float: 1.25` | same |
| `Money / Sub` | `Float: 10.0` | `Float: 10.0` | same |
| `Money / Integer` | `Money(250 USD) #<Money fractional:250 currency:USD>` | `Money(250 USD) #<Money fractional:250 currency:USD>` | same |
| `Money / 0` | `raises ZeroDivisionError: divided by zero` | `raises ZeroDivisionError: divided by zero` | same |
| `Money / Money(0)` | `raises ZeroDivisionError: divided by Money(0)` | `raises ZeroDivisionError: divided by Money(0)` | same |
| `Sub / Sub` | `Float: 10.0` | `Float: 10.0` | same |
| `Sub / Integer` | `Sub(250 USD) #<Sub fractional:250 currency:USD>` | `Sub(250 USD) #<Sub fractional:250 currency:USD>` | same |
| `Sub / Float` | `Sub(400 USD) #<Sub fractional:400 currency:USD>` | `Sub(400 USD) #<Sub fractional:400 currency:USD>` | same |
| `Sub / BigDecimal` | `Sub(250 USD) #<Sub fractional:250 currency:USD>` | `Sub(250 USD) #<Sub fractional:250 currency:USD>` | same |
| `Sub / 0` | `raises ZeroDivisionError: divided by zero` | `raises ZeroDivisionError: divided by zero` | same |
| `Sub / Money` | `Sub(1000 USD) #<Sub fractional:1000 currency:USD>` | `Float: 10.0` | **changed** |
| `Sub / Sub2` | `Sub(1000 USD) #<Sub fractional:1000 currency:USD>` | `Float: 10.0` | **changed** |
| `Sub / Money(0)` | `raises ZeroDivisionError: divided by zero` | `raises ZeroDivisionError: divided by Money(0)` | **changed** |
| `Sub / Money (GBP, rate 2)` | `Sub(250 USD) #<Sub fractional:250 currency:USD>` | `Float: 1.25` | **changed** |
| `Sub / Money (JPY, no rate)` | `Sub(3 USD) #<Sub fractional:3 currency:USD>` | `raises Money::Bank::UnknownRate: No conversion rate known for 'JPY' -> 'USD'` | **changed** |
| `Sub.div(Money)` | `Sub(1000 USD) #<Sub fractional:1000 currency:USD>` | `Float: 10.0` | **changed** |
| `Sub / String` | `raises ZeroDivisionError: divided by zero` | `raises ZeroDivisionError: divided by zero` | same |
| `Sub / nil` | `raises ZeroDivisionError: divided by zero` | `raises ZeroDivisionError: divided by zero` | same |
| `Sub.allocate(2)` | `String: "#<Sub fractional:501 currency:USD>, #<Sub fractional:500 currency:USD>"` | `String: "#<Sub fractional:501 currency:USD>, #<Sub fractional:500 currency:USD>"` | same |

- Behaviour changes for existing users. Six of the 20 inputs change, all with a subclass receiver and a divisor that is a `Money` of another class:
  1. `Sub / Money` and `Sub / Sub2` (same currency), and `Sub.div(Money)`: a `Sub` with the receiver's cents, now the documented `Float` (`10.0`). Affects code that divides a subclass instance by a plain or sibling `Money`. The old code divided the receiver's cents by the divisor's `to_d` (1 for 100 USD cents), so the result was the receiver's cents, 10 times the ratio. It was already wrong. Likelihood of reliance: very low. Judged acceptable.
  2. `Sub / Money(0)`: `divided by zero`, now `divided by Money(0)`. Same exception class (`ZeroDivisionError`), only the message differs. Acceptable.
  3. `Sub / Money` in another currency with a rate: the old result used the divisor's cents as a bare number (`Sub` of 250); now the divisor is exchanged first and the result is `1.25`. Acceptable, and the PR text states it.
  4. `Sub / Money` in another currency with no rate (JPY): the old result was a `Sub` of 3 cents; now it raises `Money::Bank::UnknownRate`, as `Money / Money` already does. This is the one change that turns a value into an exception. The old value was meaningless (the JPY amount as a bare number), so I judge it acceptable under the side-effect rule, and the PR text states it.
  Plain `Money` receivers, same-subclass pairs, and all numeric divisors are unchanged (14 of 20 inputs identical).

## Review history
- Confirmed: `CONFIRMATION.md` (verdict CONFIRMED, low severity, narrow reach).
- Panel: `SYNTHESIS.md` (roster: full, fifteen Sonnet reviewers). Round 1 outcome REVISE, text only. Round 2 outcome SHIP (`panel.outcome`).
- Re-review: round 2 by EXEC-A, EXEC-B, O5, S1, S3, S5, S7, S8. S5 flagged one sentence in PR.md (the cross-currency wording) and it was corrected. That edit was checked by S5 and by the parent against the source, not by a third reviewer. Text fixes applied: commit message cut to the subject only, cross-currency change added to PR.md, cause sentence widened to cover another subclass, diff restatement removed, doc quote simplified, repro comment replaced, zero-divisor sentence rewritten. Round 1 files are in `rev0/`.
- Upstream check (2026-10-06): `main` at `1d60efeaeea009cfc69374421561b23b851bd36e` (2026-09-29, "Keep a rational allocation amount exact (#1231)"), the same commit this run is based on. `git am` of the patch on a fresh clone of that tip: applies cleanly (new commit `27fedc5`). `run-tests` there: `503 examples, 0 failures`.
- Local check on the Mac command, `bundle install && bin/rspec`, run here on a fresh copy of the patched clone (Ruby 3.3.6, network allowed for this step only): `503 examples, 0 failures` (`localcheck.log`). Ruby 3.1 was not available here, so the operator's Mac is the first run on an older Ruby.

## Things to know before submitting
- Issue tracker. `reference_docs/known_open_bugs.md` is the operator's `gh` export of 2026-10-05T23:05:02Z (3 open issues, 6 open pull requests). None of the six open PRs touches `arithmetic.rb`. Open issue #1109 "Division by zero" has a title only in that file; its body was not seen, so it may or may not concern the zero-divisor message. The PR text makes no claim about it. Closed issues and merged or closed PRs were not searched, and the tracker itself was not searched from here (GitHub is not reachable). `submit-draft-pr.sh` runs the search before it opens anything.
- Pull-request heads in `upstream-check` touching the same files: none is newer than 2026-09-29 (the latest head is #1231), which is before the export. Heads that changed the `/` method or `arithmetic.rb`: #1148 (zero-division checks in `/`, `divmod`, from 2025-12; main already has the "divided by Money(0)" message), #1162 and #1186 (rename `value` to `other`; main already has the `other` name), #1230 (merged, one-line change at `arithmetic.rb:42`), and a set of 2025-12 lint PRs (#1183, #1184, #1187, #1194, #1198, #1202, #1203). Git cannot tell whether any of these is open. Only #1230 is a merged fix on this branch. None of them changes line 205.
- The panel was fifteen Sonnet reviewers (the rules fix the model), plus a round 2 re-review by eight of them.
- Findings the panel raised that were not adopted (from `SYNTHESIS.md`):
  - Shorten the CHANGELOG bullet (O1, O5, S1, S3; optional). S8 found it in the neighbours' style and length.
  - Add line 309 to the line list in the PR text or drop the list (S7, S3). The text says "the other `Money` checks", not "all".
  - Spec changes: a single `eq 10.0`, a retitle, a cross-currency spec (O5, S1, S4, S2). The two expectations stay because `Money == 10.0` raises on base, so `be_a Float` gives the readable failure. A cross-currency spec needs a bank rate or stub, beyond the minimal change.
  - Cite 6abbc40 in the PR text (O4, S5). "Over-broad replace" is inference.
  - Mention open issue #1109 (EXEC-A, O1, S3, S7, S8). Only its title is known.
  - CONFIRMATION.md cites the doc line as 192 where the file has 193 (S1, S2, S4, S5, S8). Internal packet only; PR.md says 193.
  - With `Money.default_infinite_precision = true`, `Sub / Money` gives a Float but `Money / Money` gives a BigDecimal (O3). The cause is that subclasses copy class settings when defined (`money.rb:243`), not this patch. Out of scope.
  - `Sub#div(Money)` also changes (EXEC-B, O3, S4). It follows from `div` calling `self / value`.
  - A CHANGELOG mention of the cross-currency change (round 2 nit). Left as is.
- Not checked by the panel: `rbs validate` (no `rbs` executable in the bundle; the patch changes no signature), the live tracker including the body of #1109, a CLA bot, downstream gems that subclass `Money`.
- POLICY.md items for the operator:
  - AI policy is silent, no conditions: the default disclosure line is the last line of the PR text. POLICY.md found no AI rule in the repository's own documents; the org `.github` profile README is empty.
  - No CLA or DCO file was found. Whether a CLA bot runs on GitHub was not checked.
  - No issue is required first and there is no PR template. No checkbox to tick.
  - CONTRIBUTING.md:16-17: "Upon merging of your first pull request, you will be given commit access to the repository." That is the maintainers' offer; nothing is needed before submitting.
  - AUTHORS: first-timer practice is mixed (POLICY.md), so the patch adds `Andrew Stellman`. If the maintainer prefers to add it at release, drop that hunk.
  - `scripts.json` has `expected_login` = `andrewstellman`. `submit.sh` stops if `gh` is logged in as someone else; check that this is the right login.
  - The CHANGELOG bullet is longer than some neighbours; the maintainer may ask to shorten it.
- Likely pushback: "narrow case, mixing subclasses is unsupported". Reply: per the confirmer (spec lines 276-277, 308-309, not re-checked by me), `+`, `-`, `==` and `divmod` already accept a plain `Money` with a subclass receiver. `Money / Sub` returns a Float (`knock_on.base.txt`).

## Checks by the orchestrating session (Opus, 2026-10-06, after the Sonnet workflow finished)

Everything above this section was written by the Sonnet-only workflow. These are my own runs.

- Upstream `main` refetched: still `1d60efea` (2026-09-29, #1231), 743 pull-request heads, newest #1231. The patch applies with `git am` to a fresh clone of that tip. Commit author `Andrew Stellman <andrew@stellman.com>`, no trailers, no body, 4 files, 10 insertions, 1 deletion.
- Suite on the patched tip: `503 examples, 0 failures`. With only `lib/money/money/arithmetic.rb` reverted: `503 examples, 1 failure`, the new example. RuboCop on the two touched Ruby files: no offenses.
- Every behavioural claim in the PR text, run on base and on the fix:
  - `Sub.new(1000, "USD") / Money.new(100, "USD")`: base `#<Sub fractional:1000 currency:USD>`, fix `10.0`.
  - Zero plain divisor: base `ZeroDivisionError: divided by zero`, fix `divided by Money(0)`.
  - `Sub.new(1000, "USD") / Money.new(400, "GBP")` with no rate: base `#<Sub fractional:250 currency:USD>`, fix `Money::Bank::UnknownRate`.
  - Lines 41, 66, 244 and 302 use `is_a?(Money)`; the doc sentence is at line 193.
- My own differential test: 2,160 divisions (receiver class Money, Sub or Sub2; divisor a Money, Sub or Sub2 of ten amounts, or one of six numbers; with and without infinite precision set on all three classes). Oracle: any Money divided by any Money must equal `Money / Money` for the same amounts.
  - Base: 800 results differ from the oracle. All 800 have a subclass receiver and a Money divisor of another class.
  - Fix: 0 differ. The 800 are exactly the results that changed. No division by a number changed.
- Where the line came from: commit 6abbc40 (2015-07-27, "Support subclassing of Money by never instantiating it by name") replaced `Money.new` with `self.class.new` across four files so that results keep the subclass, and in the same sweep changed this one test from `is_a?(Money)` to `is_a?(self.class)`. Its message is only about what class results have. Nothing in it says a plain Money divisor should be treated as a number.
- Open issue #1109 "Division by zero": I read the page with my fetch tool, which has misread GitHub pages before, so treat this as probable, not certain. It reports `Money.new(1) / Money.new(0)` returning infinity. Current `main` raises `divided by Money(0)` for that. It is about plain Money, not subclasses, so it is not this bug.
- One correction to the knock-on section above: it says the old result was "10 times the ratio". More exactly, the old code returned a Money whose amount in major units equals the ratio for a two-decimal currency (`Sub $10.00 / Money $4.00` gave `Sub $2.50`; the ratio is 2.5). So code that only called `.to_f` on the old result keeps getting the same number, and code that called Money methods on it (`.cents`, `.format`) will now get a `NoMethodError` on a Float. That is the real cost of this fix to anyone who relied on the old result, and it is the operator's call whether the documented return type outweighs it.

- Re-check on 2026-10-07 at 14:45 UTC, after the weekly usage limit paused the batch for a day and a half: upstream `main` is still `1d60efea`, 743 pull-request heads, newest #1231. The patch applies to a fresh clone of that tip; suite `503 examples, 0 failures`; with only `lib/money/money/arithmetic.rb` reverted, `503 examples, 1 failure` (the new example).

## The PR as it will be submitted
**Title:** Return a Float from Money#/ for a plain Money divisor on a subclass

> Repro, with library defaults (no global settings changed):
>
> ```ruby
> Sub = Class.new(Money)
> Sub.new(1000, "USD") / Money.new(100, "USD")
> # actual:   #<Sub fractional:1000 currency:USD>
> # expected: 10.0
> ```
>
> `Money.new(1000, "USD") / Money.new(100, "USD")` returns `10.0`. With a zero plain Money divisor, the subclass raised `divided by zero` instead of `divided by Money(0)`.
>
> For a subclass receiver and a divisor in another currency, the old code did not convert the divisor. It used the divisor's `to_d` as a plain number, so `Sub.new(1000, "USD") / Money.new(400, "GBP")` returned `#<Sub fractional:250 currency:USD>`. The new code converts the divisor through the bank as `Money / Money` does, so a missing rate raises `Money::Bank::UnknownRate`.
>
> Cause: `Money#/` tests the divisor with `other.is_a?(self.class)` (`lib/money/money/arithmetic.rb:205`). For a subclass receiver, a divisor that is not an instance of that same subclass (a plain `Money`, or another subclass) takes the number branch. The other `Money` checks in that file use `is_a?(Money)` (lines 41, 66, 244, 302).
>
> The new spec fails without the change and passes with it. Full suite: `503 examples, 0 failures`.
>
> The method docs say: "+Money/Numeric+ returns +Money+. +Money/Money+ returns +Float+." (`lib/money/money/arithmetic.rb:193`).
>
> Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

## To submit
    bash submit-draft-pr.sh

The workflow script writes that file after this step. It runs the tracker search, asks before continuing, and opens a DRAFT pull request.

## Submission record

- 2026-10-10 22:02 UTC: draft pull request https://github.com/RubyMoney/money/pull/1237 opened by Andrew with `submit-draft-pr.sh`.
- Duplicate search (`../dup-search.out`, 22:00 UTC): 10 searches, 0 hits, 0 failed.
- The first attempt stopped at the local test step: the Mac's Bundler does not know the Gemfile's `:windows` platform. Nothing was pushed. Rerun with `SKIP_TESTS=1`; the suite had passed at the same base commit in the sandbox (503 examples, 0 failures) at about 21:50 UTC.
- Checked after opening (git, sandbox): PR head `4f0d2c5eec7695bfd88ff47be82428d22f3cb4c1`, author Andrew Stellman <andrew@stellman.com>, one commit on `main` `1d60efe` (still the tip), tree `8e2bbcfbc6ed4877b5b1aecb827e2dd568125e35`, identical to the reviewed patch; no trailers.
- About 22:38 UTC: Andrew marked the pull request ready for review (his report; not checked from here, since `gh` is not available in the sandbox).
