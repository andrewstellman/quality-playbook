# CPython Numeric Stack

## Overview

Python's numeric system is structured as a tower of abstract types defined in `Lib/numbers.py` (PEP 3141), with concrete implementations spanning built-in C types and several pure-Python or C-extension modules in the standard library. The numeric ABC hierarchy and the concrete types together ensure that general numeric algorithms can be written against abstract interfaces, while specialized applications can opt into exact arithmetic or hardware-aligned types.

## The Numeric ABC Tower

`numbers.py` defines five abstract base classes arranged in a subtype hierarchy:

```
Number
  └── Complex
        └── Real
              └── Rational
                    └── Integral
```

- `Number` — the root; has no required operations, only `__hash__ = None`.
- `Complex` — defines `__complex__`, `__bool__`, `.real`, `.imag`, `__add__`, `__radd__`, `__neg__`, `__pos__`, `__abs__`, `__mul__`, `__rmul__`, `__truediv__`, `__rtruediv__`, `__pow__`, `__rpow__`, `__eq__`, `conjugate`.
- `Real` — adds `float` coercion, comparison operators, `__floor__`, `__ceil__`, `__trunc__`, `__round__`, and `__divmod__`.
- `Rational` — adds `.numerator` and `.denominator` properties.
- `Integral` — adds `__int__`, `__index__`, bitwise operators, `__lshift__`, `__rshift__`.

The built-in `complex` registers as `Complex`, `float` as `Real`, `int` as `Integral`. Note that `decimal.Decimal` is intentionally not registered as `Real` because Decimal values do not interoperate with binary floats.

## Built-in `int`

Python integers are arbitrary precision (no fixed bit width). The C implementation uses a digit-array representation in base 2^30 (default) or 2^15 (`--enable-big-digits=15`). Arithmetic involving large integers falls back from hardware instructions to multi-word algorithms implemented in `Objects/longobject.c`. The Python-level `_pylong.py` provides additional utilities (e.g., the Karatsuba-based multiplication path for very large numbers).

`int.bit_length()`, `int.bit_count()`, `int.to_bytes(length, byteorder)`, `int.from_bytes(bytes, byteorder)`, `int.as_integer_ratio()` are among the important methods. The `__index__` protocol (returning an integer without truncation) is required for use as a sequence index; types that implement `__index__` are accepted everywhere an exact integer is required.

## Built-in `float`

`float` wraps a C `double` (IEEE 754 binary64). Conversion from `int` may be lossy for very large integers; `float.as_integer_ratio()` returns the exact `(numerator, denominator)` pair. `math.isfinite`, `math.isinf`, `math.isnan` test for special values.

## `decimal` — Exact Decimal Arithmetic

`decimal.Decimal` implements IBM's General Decimal Arithmetic specification. Key features:

- Arbitrary precision controlled by the thread-local `decimal.Context` object (`getcontext()` / `setcontext()`). Default precision is 28 significant digits.
- Exact representation: `Decimal('0.1') + Decimal('0.2') == Decimal('0.3')` is `True`.
- Configurable rounding modes: `ROUND_HALF_UP`, `ROUND_HALF_EVEN` (banker's rounding), `ROUND_CEILING`, `ROUND_FLOOR`, `ROUND_DOWN`, `ROUND_UP`, `ROUND_05UP`.
- Signal trapping: `decimal.InvalidOperation`, `decimal.DivisionByZero`, `decimal.Overflow`, `decimal.Underflow`, `decimal.Inexact`, `decimal.Rounded`, `decimal.Subnormal` can be set to raise exceptions.
- Context construction: `decimal.localcontext()` is a context manager that provides a thread-local copy of the active context, allowing temporary precision/rounding changes without affecting other threads.

The C extension `_decimal` (based on the `mpdecimal` library) is used when available; `Lib/_pydecimal.py` is the pure-Python fallback.

## `fractions` — Exact Rational Arithmetic

`fractions.Fraction` represents exact rational numbers as a pair of arbitrary-precision integers (numerator, denominator in lowest terms). It implements the `Rational` ABC.

Constructors accept:
- Two integers: `Fraction(3, 7)`.
- A `float` or `decimal.Decimal`: `Fraction(1.5)` → `Fraction(3, 2)`.
- A string: `Fraction('22/7')`, `Fraction('3.14159')`.

`Fraction.limit_denominator(max_denominator=10**6)` finds the best rational approximation with denominator ≤ max. This is useful for recovering exact rationals from floating-point measurements.

## `math` Module

`math` provides access to the C standard math library (via `libm`), plus additional utilities:

- Basic: `floor`, `ceil`, `trunc`, `fabs`, `factorial`, `gcd`, `lcm`, `comb`, `perm`.
- Powers and logarithms: `sqrt`, `exp`, `exp2`, `log`, `log2`, `log10`, `pow`.
- Trigonometric: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `hypot` (generalized n-dimensional), `degrees`, `radians`.
- Hyperbolic: `sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh`.
- Special: `erf`, `erfc`, `gamma`, `lgamma`.
- Floating-point utilities: `frexp`, `ldexp`, `modf`, `copysign`, `nextafter`, `ulp`, `isclose`, `isfinite`, `isinf`, `isnan`, `fsum` (exact floating-point sum), `prod`, `dist` (Euclidean distance).
- Constants: `math.pi`, `math.e`, `math.tau`, `math.inf`, `math.nan`.

## `cmath` Module

`cmath` mirrors `math` for complex numbers: `sqrt`, `exp`, `log`, `sin`, `cos`, `tan`, `phase`, `polar`, `rect`. It handles branch cuts consistently with the IEEE standard for complex arithmetic.

## `statistics` Module

`statistics` (added in Python 3.4) provides statistical functions operating on sequences of `int`, `float`, `Decimal`, or `Fraction` values:

- Central tendency: `mean`, `fmean` (fast float mean), `geometric_mean`, `harmonic_mean`, `median`, `median_low`, `median_high`, `median_grouped`, `mode`, `multimode`.
- Spread: `pstdev`, `pvariance` (population), `stdev`, `variance` (sample).
- Relationships: `covariance`, `correlation`, `linear_regression`.
- Distributions: `NormalDist` — a class encapsulating mean and standard deviation with methods for PDF, CDF, inverse CDF, and random sampling.

## `random` Module

`random` provides a Mersenne Twister PRNG (MT19937) plus a `SystemRandom` subclass that delegates to `os.urandom()`. The public API includes:
- `random()` — uniform float in [0.0, 1.0).
- `randint(a, b)`, `randrange(start, stop[, step])`.
- `choice(seq)`, `choices(population, weights, k)`, `sample(population, k)`, `shuffle(x)`.
- Distributions: `uniform`, `triangular`, `gauss`, `normalvariate`, `lognormvariate`, `expovariate`, `vonmisesvariate`, `gammavariate`, `betavariate`, `paretovariate`, `weibullvariate`.

## `struct` Module

`struct` packs and unpacks C-compatible binary data according to format strings. Format characters specify types (`b`, `B`, `h`, `H`, `i`, `I`, `l`, `L`, `q`, `Q`, `f`, `d`, `s`, `p`, `?`) and endian prefixes (`@`, `=`, `<`, `>`, `!`). `struct.pack(fmt, *values)` → `bytes`; `struct.unpack(fmt, buffer)` → tuple.

`struct.Struct(fmt)` compiles a format string into an object with `pack`, `unpack`, `pack_into`, `unpack_from`, `iter_unpack` methods, avoiding recompilation on repeated use.
