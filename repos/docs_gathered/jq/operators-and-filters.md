# jq Operators and Basic Filters — Semantics and Composition Rules

Extracted from jq manual v1.8 and expression evaluation semantics in execute.c.

---

## 1. Identity and Data Access

### Identity (.)
The `.` operator returns the input unchanged. It's the identity element for piping.

```jq
. | . | .          # All equivalent to .
```

### Field Access (.foo)
- `.foo` returns the value of key "foo" in the input object
- `.foo.bar` chains field access
- On non-object, `.foo` errors (unless using optional with `?`)
- On null, `.foo` returns null (not error)

### String Keys with Special Characters
```jq
."foo-bar"         # Access field with hyphen
."foo.bar"         # Access field with dot
.["foo"]           # Equivalent to .foo
.["foo-bar"]       # Equivalent to ."foo-bar"
```

### Array Indexing
- `.[0]` — zero-based first element
- `.[-1]` — last element
- `.[n]` where n is not integer — **Error**
- `.[1000]` on array of length 5 — returns `null`
- `.[n]` on non-array — **Error** (unless using `?`)

### Array Slicing
- `.[2:5]` — elements at indices 2, 3, 4 (exclusive end)
- `.[2:]` — from index 2 to end
- `.[:5]` — from start to index 5
- `.[:]` — entire array (identity for arrays)
- `.[10:5]` — empty array (start > end)
- On non-array, slicing — **Error** (unless using `?`)

### Iterator (.[]`)
The `.[]` operator generates individual elements or values:
- `[1,2,3] | .[]` → Produces three outputs: `1`, `2`, `3`
- `{"a":1, "b":2} | .[]` → Produces two outputs: `1`, `2`
- `null | .[]` → **Error** (cannot iterate null)
- String iteration not supported; `.[]` on string — **Error**

---

## 2. Pipe Operator (|)

The pipe chains filters: `A | B` passes each output of A as input to B.

### Chaining Semantics
```jq
[1,2,3] | .[] | . + 1    # Produces 2, 3, 4 (three separate outputs)
[1,2,3] | map(. + 1)     # Produces [2, 3, 4] (collected into array)
```

### Generator Interaction
- If the left side produces multiple outputs, the right side is applied to each
- The right side doesn't know or care about the multiplicity; it just transforms values one at a time

### Associativity
Pipe is left-associative: `A | B | C` is `(A | B) | C`, equivalent to `(. | A) | B | C`.

---

## 3. Comma Operator (,)

The comma operator produces **multiple outputs** from a single expression.

```jq
1, 2, 3              # Produces three separate outputs: 1, 2, 3
.a, .b               # Multiple field access; produces value of .a then .b
```

### Comma vs Array Construction
```jq
1, 2, 3              # Three outputs (generator)
[1, 2, 3]            # One output: an array [1, 2, 3]
[., .]               # One output: array with two copies of input
.[], .[1]            # Multiple outputs: all elements, then element 1
```

### Interaction with Other Operators
- Comma has **lowest precedence**; binds weaker than pipe, conditionals, etc.
- `if . then 1, 2 else 3 end` produces 1 and 2 (or 3), depending on condition

### Context-Dependent Behavior
- In array construction `[...]`, comma is just a separator; outputs are collected
- Outside array construction, comma generates multiple outputs
- In function arguments, comma behavior depends on the function

---

## 4. Arithmetic Operators

### Addition (+)
Context-dependent behavior:

| Operands | Behavior |
|----------|----------|
| number + number | Arithmetic sum |
| string + string | Concatenation |
| array + array | Concatenation (combined array) |
| object + object | Merge (right side wins on key conflicts) |
| null + X | Error (null is not additive in arithmetic) |
| number + string | **Error** (no type coercion) |

### Subtraction (-)
- `number - number` — Arithmetic difference
- `array - array` — Remove elements: `[1,2,3] - [2]` → `[1,3]` (removes 2)
- `null - X` — **Error**
- Other combinations — **Error**

### Multiplication (*)
- `number * number` — Arithmetic product
- `string * number` — Repeat string: `"ab" * 3` → `"ababab"`
- `number * string` — Same as above (commutative)
- `object * object` — Recursive merge (conflicts favor right, nested objects recurse)
- `array * object` — Not directly supported; must be converted

### Division (/)
- `number / number` — Arithmetic division (returns IEEE754 double)
- `string / string` — Split: `"a,b,c" / ","` → `["a", "b", "c"]`
- Other combinations — **Error**

### Modulo (%)
- `number % number` — Remainder (IEEE754 semantics)
- Not supported for other types

---

## 5. Comparison Operators

All comparison operators follow jq's type ordering (see type-system.md).

### Equality and Inequality
- `a == b` — True if values are equal (no type coercion)
- `a != b` — Negation of equality
- Types must match; `1 == "1"` → `false`
- Comparison is recursive for arrays/objects

### Relational Operators
- `a < b`, `a > b`, `a <= b`, `a >= b` — Follow type ordering
- `null < 1 < "string" < [] < {}`
- Within each type, natural ordering (numeric, lexicographic, etc.)

### Comparison Chaining
jq does not support chained comparisons like `1 < 2 < 3`. You must use `and`:

```jq
(. > 0) and (. < 10)   # Correct: check both conditions
```

---

## 6. Logical Operators

### and
```jq
A and B              # If A is truthy, produces B; otherwise produces false
true and 1           # → 1
false and 1          # → false
null and 1           # → false (null is falsy)
```

Short-circuit semantics: if A is falsy, B is not evaluated.

### or
```jq
A or B               # If A is truthy, produces A; otherwise produces B
true or 1            # → true
false or 1           # → 1
null or "default"    # → "default"
```

Short-circuit semantics: if A is truthy, B is not evaluated.

### not
```jq
. | not              # Logical negation (true ↔ false, everything else → false)
true | not           # → false
false | not          # → true
null | not           # → true (null is falsy)
1 | not              # → false (numbers are truthy)
```

### Truthiness
Falsy values: `false`, `null`. Everything else (including `0`, `""`, `[]`, `{}`) is truthy.

---

## 7. Alternative Operator (//)

The alternative operator provides a default when the left side is false or null:

```jq
.foo // "default"             # Use .foo if truthy, else "default"
null // "default"             # → "default"
false // "default"            # → "default"
0 // "default"                # → 0 (zero is truthy)
"" // "default"               # → "" (empty string is truthy)
```

### Error Handling with //
The alternative operator does **not** catch errors; it only handles null/false:

```jq
(.foo | error) // "caught"    # Does NOT catch the error; still errors
```

Use `try-catch` to catch actual errors.

### Optional Chaining with //?
Combining optional with alternative:

```jq
.foo? // "default"            # If .foo errors or is absent, use default
.[]? // []                     # If .[] errors, use empty array
```

---

## 8. Conditional Expression (if-then-else)

```jq
if COND then A else B end
if COND then A elif COND2 then B else C end
```

### Truthiness in Conditions
Conditions use falsy rule: `false` and `null` are falsy; everything else is truthy.

```jq
if 0 then "yes" else "no" end           # → "yes" (0 is truthy)
if "" then "yes" else "no" end          # → "yes" (empty string is truthy)
if [] then "yes" else "no" end          # → "yes" (empty array is truthy)
if null then "yes" else "no" end        # → "no" (null is falsy)
```

### Multiple Branches
```jq
if A then B
elif C then D
elif E then F
else G
end
```

Branches are evaluated in order; first truthy condition's branch is taken.

### Generators in Branches
If a branch contains a generator, all outputs are produced:

```jq
if . > 0 then 1, 2 else 3 end  # Produces 1, 2 (or just 3 if . <= 0)
```

---

## 9. Optional Operator (?)

The `?` suffix suppresses errors and returns empty instead.

```jq
.foo?                  # Like .foo, but returns empty if input is not object
.[]?                   # Like .[], but returns empty if input is not iterable
.foo.bar?              # Optional applies to the last field access
.[0]?                  # Returns empty if input is not array or index out of bounds
tonumber?              # Suppresses error if not a parseable number
```

### Behavior
- If the operation would error, `?` converts it to `empty` (no output)
- If the operation would succeed, `?` has no effect (same output as without `?`)

### Chaining with try-catch
```jq
try .foo catch "error"         # Catches and handles error
.foo?                          # Same as: try .foo catch empty
```

---

## 10. Operator Precedence (highest to lowest)

1. **Primary**: `.`, literals, `(...)`, function calls
2. **Postfix**: `.[]`, `?`, slicing `[n:m]`, indexing `[n]`
3. **Unary**: `not`
4. **Exponentiation** (if supported): None in standard jq
5. **Multiplicative**: `*`, `/`, `%`
6. **Additive**: `+`, `-`
7. **Comparison**: `==`, `!=`, `<`, `>`, `<=`, `>=`
8. **Logical AND**: `and`
9. **Logical OR**: `or`
10. **Alternative**: `//`
11. **Conditional**: `if-then-else`
12. **Pipe**: `|`
13. **Comma**: `,`

### Precedence Examples
```jq
1 + 2 * 3              # → 7 (multiplication before addition)
.a | .b + .c           # → (.a | .b) + (.a | .c) is WRONG!
                       # Actually: ((.a) | (.b)) + (.c) — context matters
. | . + 1 | . * 2      # Parsed as: ((. | (. + 1)) | (. * 2))
```

---

## Sources

- jq Manual v1.8: https://jqlang.org/manual/
- Execute.c reference: https://github.com/jqlang/jq/blob/master/src/execute.c
