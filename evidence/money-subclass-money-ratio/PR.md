**Title:** Return a Float from Money#/ for a plain Money divisor on a subclass

Repro, with library defaults (no global settings changed):

```ruby
Sub = Class.new(Money)
Sub.new(1000, "USD") / Money.new(100, "USD")
# actual:   #<Sub fractional:1000 currency:USD>
# expected: 10.0
```

`Money.new(1000, "USD") / Money.new(100, "USD")` returns `10.0`. With a zero plain Money divisor, the subclass raised `divided by zero` instead of `divided by Money(0)`.

For a subclass receiver and a divisor in another currency, the old code did not convert the divisor. It used the divisor's `to_d` as a plain number, so `Sub.new(1000, "USD") / Money.new(400, "GBP")` returned `#<Sub fractional:250 currency:USD>`. The new code converts the divisor through the bank as `Money / Money` does, so a missing rate raises `Money::Bank::UnknownRate`.

Cause: `Money#/` tests the divisor with `other.is_a?(self.class)` (`lib/money/money/arithmetic.rb:205`). For a subclass receiver, a divisor that is not an instance of that same subclass (a plain `Money`, or another subclass) takes the number branch. The other `Money` checks in that file use `is_a?(Money)` (lines 41, 66, 244, 302).

The new spec fails without the change and passes with it. Full suite: `503 examples, 0 failures`.

The method docs say: "+Money/Numeric+ returns +Money+. +Money/Money+ returns +Float+." (`lib/money/money/arithmetic.rb:193`).

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
