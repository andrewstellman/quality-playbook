# Panel synthesis: money-subclass-money-ratio (BUG-013)

Roster: full panel, 15 reviewers, all Sonnet (the rules fix the model). All 15 files exist in `panel/`. No REJECT, no DROP.

| Item | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| money-subclass-money-ratio | S | F | S | S | S | S | F | F | S | F | S | F | S | S | F |

S = SHIP, F = FIX-REQUIRED, R = REJECT, D = DROP, – = not run.

Outcome: **REVISE**. Every FIX-REQUIRED is about text (the commit message and PR.md). Nobody asked for a code or test change.

What the panel agrees on:
- Both executors reproduced red, green, revert and the suite: new spec fails on base with `expected #< fractional:1000 currency:USD> to be a kind of Float`, passes with the fix, fails again when only `lib/` is reverted. Suite `503 examples, 0 failures`. Lint clean on the two touched files. The confirmer's repro exits 1 on base and 0 on the fix.
- The change is one token at `lib/money/money/arithmetic.rb:205`. `sig/lib/money/money/arithmetic.rbs:128` already says `-> (Money | Float)`, so no RBS change.
- The only `is_a?(self.class)` in `lib/` came from 6abbc40 (2015). No reviewer found a reason to call it intended. O4 argued the maintainer's side and conceded on the doc sentence at `arithmetic.rb:193`.
- Side-effect rule: nobody asked for DROP. Affected users are code that divides a Money subclass instance by a plain Money or a sibling subclass. They got a wrong Money, now get the documented Float. Likelihood judged very low by all.
- Security: O2 found nothing security-relevant, and the text does not frame it as security.
- Performance: S6 found no measurable difference.

## Findings that must change

1. **Commit message has a body, POLICY.md says subject only.** Raised as FIX-REQUIRED by EXEC-B, O5, S1, S3, S8. Noted as a nit by EXEC-A, O1, O2, O3, O4, S4, S7. POLICY.md: "Commit style: subject only, no body, sentence case, imperative, no trailing period, no prefix"; the last three merged fixes (1d60efe, 7348778, 227f736) are subject only. Replace the whole message with exactly:
   `Return a Float from Money#/ for a plain Money divisor on a subclass`
   No trailers. Then regenerate `0001-*.patch` with `git format-patch -1`. The body's "as the other Money operators do" is also loose (S3, S7: `+` and `-` use `case ... when Money`, `*` takes no Money), which the subject-only message removes.

2. **PR.md does not state the cross-currency change.** Required by S5; supported by O2, O3, EXEC-B and S4 as optional. On base, a subclass receiver divided by a plain Money in another currency ignored the divisor's currency and returned a Sub. After the fix the divisor goes through `exchange_to`, so a missing rate raises `Money::Bank::UnknownRate`. Run by S5, O2, O3, O4, S4, EXEC-B on base and fixed. The side-effect rule says the text states each change, so add after the sentence ending "instead of `divided by Money(0)`.":
   > For a divisor in another currency, the old code did not convert it and returned a Sub with the receiver's amount unchanged. The new code converts it through the bank as `Money / Money` does, so a missing rate raises `Money::Bank::UnknownRate`.

3. **PR.md cause sentence is too narrow.** Raised by S5; the sibling-subclass case (`Sub / Sub2`) was run by EXEC-B, O1, O3, O4, S4, S5 and changes the same way. Replace "For a subclass receiver, a plain `Money` is not an instance of the subclass, so it takes the number branch." with:
   > For a subclass receiver, a divisor that is not an instance of that same subclass (a plain `Money`, or another subclass) takes the number branch.

4. **PR.md restates the diff.** Raised by O5, S3. Replace "The fix changes the check to `other.is_a?(Money)`. The new spec in `spec/money/arithmetic_spec.rb` fails without it and passes with it, and the full suite is `503 examples, 0 failures`." with:
   > The new spec fails without the change and passes with it. Full suite: `503 examples, 0 failures`.

5. **PR.md doc quote nests inline code inside quotation marks and ends in padding.** Raised by O5. Replace the last paragraph before the disclosure with:
   > The method docs say: "+Money/Numeric+ returns +Money+. +Money/Money+ returns +Float+." (`lib/money/money/arithmetic.rb:193`).

6. **PR.md repro comment is vague.** Raised by S1, S3. Replace
   `# actual:   a Sub with fractional 1000 (a Money, not a Float)` with `# actual:   #<Sub fractional:1000 currency:USD>`. Keep the `# expected: 10.0` line.

7. **PR.md zero-divisor sentence is a run-on.** Raised by S1, S3. Replace "A zero plain Money divisor on the subclass raised `ZeroDivisionError: divided by zero` instead of `divided by Money(0)`." with:
   > With a zero plain Money divisor, the subclass raised `divided by zero` instead of `divided by Money(0)`.

The disclosure line stays last and exact (S3, S7, S8, EXEC-B checked it).

## Findings not worth adopting

- **Shorten the CHANGELOG bullet** (O1, O5, S1, S3, all optional). S8 checked it against the neighbours and found it in their style and length. Left to the operator. If taken, the shared wording is: "Fix `Money#/` on a `Money` subclass returning a `Money` instead of a `Float` when the divisor is a plain `Money`".
- **Add 309 to the line list, or drop the list** (S7, S3). The text says "the other `Money` checks", not "all", and the cited lines are correct. Line 41 is `eql?`, which S3 would drop, but it is still an `is_a?(Money)` check on the same pattern.
- **Spec changes** (O5 single `eq 10.0`, S1 retitle, S4 cross-currency spec, S2 placement). S2, S3, S4, S1 all argued to keep the two expectations: on base `Money == 10.0` raises, so `be_a Float` gives the readable failure. A cross-currency spec needs a bank rate or stub, which goes beyond the minimal-change rule.
- **Cite 6abbc40 in PR.md** (O4, S5). The "over-broad replace" reading is inference, and S7 notes the PR rightly does not repeat it. A history claim adds text for no gain.
- **Mention open issue #1109 "Division by zero"** (EXEC-A, O1, S3, S7, S8). Only its title is known. The PR makes no claim about it. Do not write "fixes #1109" or "no related issue".
- **CONFIRMATION.md cites the doc line as 192** (S1, S2, S4, S5, S8). The file has it at 193, and PR.md has 193. This is in the internal packet only, not in anything submitted.
- **`Money.default_infinite_precision = true` shows Float for `Sub / Money`, BigDecimal for `Money / Money`** (O3). The cause is that subclasses copy class settings when defined (`money.rb:243`), not this patch. Out of scope.
- **`Sub#div(Money)` also changes** (EXEC-B, O3, S4). It calls `self / value`, so it follows. No text change needed.

## Not checked by the panel

`rbs validate` (no `rbs` executable in the bundle), the live tracker including the body of #1109, a CLA bot, Ruby 3.1 on the operator's Mac, downstream gems that subclass Money.

## Next

Items 1 to 7 are text-only. The fixed clone was not touched. Apply them to the commit message and `PR.md`, regenerate the patch, and re-run the packet checks before Step 6.

## Round 2

Revision type: text only. No source or test change, so no fixer sub-agent was spawned. Round 1 files are in `rev0/` (patch, PR.md, logs).

What was changed:
1. Commit message: amended in `/work/batch/runs/money/scratch/fix-money-subclass-money-ratio` to the subject only, `Return a Float from Money#/ for a plain Money divisor on a subclass`. Same author, no trailers. Patch regenerated. `git am` of the patch on a clean clone of the base gives tree 8e2bbcf, equal to the tree at HEAD of the fixed clone. Suite `503 examples, 0 failures`; lint on the two touched files clean; `git status --porcelain` empty.
2. Cross-currency change (finding 2): added to PR.md, but NOT with the wording the synthesis proposed. "Returned a Sub with the receiver's amount unchanged" is wrong in general. The parent ran `Sub.new(1000,"USD") / Money.new(400,"GBP")` on base: `#<Sub fractional:250 currency:USD>`, which is 1000 / 4, the divisor's amount used as a bare number. On the fix: `Money::Bank::UnknownRate: No conversion rate known for 'GBP' -> 'USD'`, the same as `Money.new(1000,"USD") / Money.new(400,"GBP")`. New text: "the old code ignored the currency and divided the receiver's amount by the divisor's amount, returning a Sub."
3. Cause sentence (finding 3): replaced as proposed (plain `Money` or another subclass). `Sub / Sub2` run on base (Sub) and fix (10.0).
4. Diff restatement (finding 4): replaced as proposed.
5. Doc quote (finding 5): replaced as proposed. Line 193 re-read.
6. Repro comment (finding 6): `# actual:   #<Sub fractional:1000 currency:USD>`.
7. Zero-divisor sentence (finding 7): replaced as proposed. Base and fix output re-run.

Not adopted: everything in "Findings not worth adopting" above stands. The CHANGELOG bullet, the spec title and the line list were left as they were, because changing them is a code revision and none of them is a defect.

Re-review verdict row (focused, round 2): see below, filled in after the reviewers finish.

### Round 2 verdicts and the follow-up edit

| Item | EXEC-A | EXEC-B | O5 | S1 | S3 | S5 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|
| money-subclass-money-ratio (round 2) | S | S | S | S | S | F | S | S |

S5 (FIX-REQUIRED, medium, text only): "divided the receiver's amount by the divisor's amount" is imprecise. Base divides the receiver's `fractional` by the divisor's `to_d` (`as_d(other)` at `lib/money/money.rb:640`, `Money#to_d` at `:444`), so for GBP 400 the result is 1000 / 4 = 250, and for JPY 400 it is 1000 / 400 rounded to 3. S7 flagged the same wording and that the paragraph does not say "subclass receiver". Adopted: the PR.md sentence now reads "For a subclass receiver and a divisor in another currency, the old code did not convert the divisor. It used the divisor's `to_d` as a plain number, so `Sub.new(1000, "USD") / Money.new(400, "GBP")` returned `#<Sub fractional:250 currency:USD>`." The 250 output was run by the parent (round 1 of this step), S5, S7 and EXEC-B. The edit is PR.md only: patch, commit and logs are unchanged, so the executors' results stand. The edited sentence was checked by S5 (who proposed it, with the JPY/KWD runs) and by the parent against the source, not by a third reviewer.

Not adopted in round 2 (optional nits): add line 309 to the list, shorten the CHANGELOG bullet, spec retitle, a CHANGELOG mention of the cross-currency change. Reasons as in round 1.

Verdict: no REJECT, no DROP, every round 2 FIX-REQUIRED answered. Outcome SHIP.
