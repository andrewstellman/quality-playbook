# Knock-on check for Money#/ (is_a?(self.class) -> is_a?(Money)).
# Run: LANG=C.UTF-8 BUNDLE_GEMFILE=$PWD/Gemfile bundle exec ruby -Ilib -rmoney knock_on.rb
# Library defaults. Rates are added to the default bank in this process only.
Money.default_bank.add_rate("GBP", "USD", 2)
Money.default_bank.add_rate("USD", "GBP", 0.5)
Money.default_bank.add_rate("EUR", "USD", 2)
Money.default_bank.add_rate("USD", "EUR", 0.5)

Sub  = Class.new(Money)
Sub2 = Class.new(Money)

def m(klass, cents, cur) = klass.new(cents, cur)

cases = [
  ["Money / Money",               -> { m(Money, 1000, "USD") / m(Money, 100, "USD") }],
  ["Money / Money (GBP, rate 2)", -> { m(Money, 1000, "USD") / m(Money, 400, "GBP") }],
  ["Money / Sub",                 -> { m(Money, 1000, "USD") / m(Sub, 100, "USD") }],
  ["Money / Integer",             -> { m(Money, 1000, "USD") / 4 }],
  ["Money / 0",                   -> { m(Money, 1000, "USD") / 0 }],
  ["Money / Money(0)",            -> { m(Money, 1000, "USD") / m(Money, 0, "USD") }],
  ["Sub / Sub",                   -> { m(Sub, 1000, "USD") / m(Sub, 100, "USD") }],
  ["Sub / Integer",               -> { m(Sub, 1000, "USD") / 4 }],
  ["Sub / Float",                 -> { m(Sub, 1000, "USD") / 2.5 }],
  ["Sub / BigDecimal",            -> { m(Sub, 1000, "USD") / BigDecimal("4") }],
  ["Sub / 0",                     -> { m(Sub, 1000, "USD") / 0 }],
  ["Sub / Money",                 -> { m(Sub, 1000, "USD") / m(Money, 100, "USD") }],
  ["Sub / Sub2",                  -> { m(Sub, 1000, "USD") / m(Sub2, 100, "USD") }],
  ["Sub / Money(0)",              -> { m(Sub, 1000, "USD") / m(Money, 0, "USD") }],
  ["Sub / Money (GBP, rate 2)",   -> { m(Sub, 1000, "USD") / m(Money, 400, "GBP") }],
  ["Sub / Money (JPY, no rate)",  -> { m(Sub, 1000, "USD") / m(Money, 400, "JPY") }],
  ["Sub.div(Money)",              -> { m(Sub, 1000, "USD").div(m(Money, 100, "USD")) }],
  ["Sub / String",                -> { m(Sub, 1000, "USD") / "abc" }],
  ["Sub / nil",                   -> { m(Sub, 1000, "USD") / nil }],
  ["Sub.allocate(2)",             -> { m(Sub, 1001, "USD").allocate([1, 1]).map(&:inspect).join(", ") }],
]

def show(v)
  case v
  when Money then "#{v.class.name || 'Sub'}(#{v.fractional.inspect} #{v.currency}) #{v.inspect}"
  else "#{v.class}: #{v.inspect}"
  end
end

cases.each do |label, fn|
  out = begin
    show(fn.call)
  rescue => e
    "raises #{e.class}: #{e.message}"
  end
  puts "#{label.ljust(30)} => #{out}"
end
