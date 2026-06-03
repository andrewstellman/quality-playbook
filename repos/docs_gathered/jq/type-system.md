# jq Type System — Types, Values, Representation, and Comparison Semantics

Extracted from jq manual v1.8, source code (jv.h, jv.c), and GitHub discussions on type handling.

---

## 1. Type Categories

jq implements six JSON-compatible types plus error values:

| Type | Examples | Internal Representation |
|------|----------|------------------------|
| null | `null` | Single jv_NULL tag, no payload |
| boolean | `true`, `false` | jv_TRUE or jv_FALSE tag |
| number | `1`, `3.14`, `1e10` | IEEE754 double + optional literal form |
| string | `"hello"`, `""` | UTF-8 bytes with refcount, length field |
| array | `[1,2,3]`, `[]` | Doubly-linked list or contiguous array, refcount |
| object | `{"a":1}`, `{}` | Hash table (jv_object), refcount |
| error | (internal) | Special tagged value with error message |

---

## 2. Number Representation and Precision

### IEEE754 Double Precision
All arithmetic operations and number values are internally represented as IEEE754 64-bit doubles. This gives:
- **Range**: Approximately ±1.8e308 (min/max representable)
- **Precision**: 53-bit significand (about 15-17 decimal digits)
- **Special values**: +Inf, -Inf, NaN

### Literal Form Preservation
jq preserves the **original literal form** of number tokens from the source code as a separate string. This allows:
- `1.0 | .` outputs `1.0` (not `1`)
- `1e10 | .` outputs `1e10` (not `10000000000`)
- `1 | . * 1` outputs `1` (literal form lost after mutation)

### Mutation Rule
The literal form is **discarded** after any arithmetic or logical operation:
- `1.0 + 0` → `1` (double output)
- `1.0 | if . == 1 then . else . end` → `1` (condition evaluation mutates)
- `1.0 | .[0]` → Error (but literal form would be irrelevant since 1.0 is not indexable)

### Arithmetic Coercion
Type-specific arithmetic behavior:
- **Numbers**: Standard IEEE754 operations, result is always a double
- **Strings**: Concatenation with `+`, splitting with `/`
- **Arrays**: Concatenation with `+`, element removal with `-`
- **Objects**: Merging with `+` (right side wins on conflicts)
- **null**: Neutral in some contexts; errors in others

---

## 3. String Representation and Encoding

### UTF-8 Encoding
Strings are stored as UTF-8 byte sequences internally. String operations like `length`, `.[start:end]` work on codepoints, not bytes (though the underlying storage is bytes).

### Length Semantics
- `"hello" | length` → `5` (codepoint count)
- `"你好" | length` → `2` (codepoint count, not byte count)
- `null | length` → `null` (special case: null returns null)
- `3 | length` → `3` (number returns absolute value)

### Escape Sequences
Supported: `\"`, `\\`, `\/`, `\b`, `\f`, `\n`, `\r`, `\t`, `\uXXXX` (Unicode escape).

### String Interpolation
Strings can embed jq expressions via `\(expr)` syntax:
- `"Value: \(. + 1)"` interpolates the expression result as JSON
- Nested `\(...)` must have balanced parentheses
- Expression can fail, which fails the entire string interpolation

---

## 4. Array Representation and Semantics

### Storage
Arrays are ordered sequences with optional indexing optimizations. Internally, small arrays may use contiguous storage; large arrays use flexible structures.

### Indexing
- **Zero-based**: `.[0]` is the first element
- **Negative indices**: `.[-1]` is the last element; `.[-2]` is second-to-last
- **Out of bounds**: Returns `null` (on standard indexing) or error (on optional with `?`)
- **Non-integer index**: Always errors (no string keys on arrays)

### Iteration
- `.[]` generates individual elements (not an array)
- `.[n:m]` slices from index n to m (exclusive); omitted bounds are 0 and length
- `.[n:]` slices from n to end
- `.[:m]` slices from start to m

### Null Indexing
- `null[0]` → `null` (indexing null with number returns null)
- `null.foo` → `null` (indexing null with string returns null)
- `null | .[0]` → `null` (same as above via pipe)

---

## 5. Object Representation and Semantics

### Hash Table Storage
Objects are stored as hash tables (jv_object) with string keys and arbitrary jv values. Iteration order is insertion order (implementation detail, not guaranteed in spec).

### Key Access
- `.foo` accesses field "foo"
- `."foo-bar"` accesses field with special characters
- `.["key"]` computes key from expression (must be string)
- `.foo?` returns empty if field doesn't exist or input is not object

### Null Behavior
- `null.foo` → `null` (null.fieldname returns null)
- `null["foo"]` → `null` (null with computed key returns null)
- `null | .foo?` → `null` (optional access on null returns null, not empty)

### Computed Keys
- `{(.foo): .bar}` uses `.foo` as the key
- Key expression must produce a string; non-strings error

### Merging and Updates
- `+ {}` returns input unchanged
- `{a: 1} + {b: 2}` → `{a: 1, b: 2}` (merge)
- `{a: 1} + {a: 2}` → `{a: 2}` (right side wins on conflicts)
- `* {}` recursively merges (conflicts favor right, objects recurse)

---

## 6. Comparison and Ordering Semantics

### Type Ordering (for sort)
jq defines a total ordering across types:
```
null < false < true < numbers < strings < arrays < objects
```

Within each type:
- **Numbers**: IEEE754 comparison (NaN is problematic; see edge cases)
- **Strings**: Lexicographic (UTF-8 byte order)
- **Arrays**: Lexicographic by element (compares first differing element)
- **Objects**: Ordered by keys first (keys are sorted lexicographically), then by values

### Equality Comparison (==)
- `1 == 1.0` → `true` (numerically equal despite literal form difference)
- `"1" == 1` → `false` (type mismatch; no coercion)
- `null == null` → `true`
- `null == false` → `false`
- `[1,2] == [1,2]` → `true`
- `{a:1} == {a:1}` → `true` (key-value pairs must match)

### Inequality and Relational Operators
- `<`, `>`, `<=`, `>=` compare using type ordering
- `null < 1` → `true` (because null is first in type order)
- `"a" < "b"` → `true`
- `[1,2] < [1,3]` → `true`

### NaN Semantics
IEEE754 NaN has pathological comparison behavior:
- `nan == nan` → `false` (IEEE754 standard)
- `nan < 1` → `false`
- `nan > 1` → `false`
- `nan <= 1` → `false`
- Sorting arrays with NaN produces undefined order for the NaN

---

## 7. Type Coercion Rules

jq **does not perform implicit type coercion**. Operations between incompatible types always error:

- `1 + "1"` → **Error** (cannot add number and string)
- `"a" - 1` → **Error** (strings don't support subtraction)
- `.foo | tonumber` → **Error if .foo is not numeric string** (conversion fails)
- `{} | keys | .[0]` → May be string (keys returns string array)

Explicit conversion functions (type-changing):
- `tonumber` — string → number (or error if not parseable)
- `tostring` — number/boolean/null → string representation
- `toarray` — object → array of values
- `type` — returns type name as string

---

## 8. Null Semantics and Propagation

### Null is a Value
`null` represents absence of a value, but is itself a valid jq value (not void/undefined).

### Null Propagation Rules
| Operation | Behavior |
|-----------|----------|
| `null + 1` | Error |
| `null[0]` | `null` (indexing null returns null) |
| `.foo.bar.baz` on `null` | `null` (chain of field access returns null) |
| `null \| length` | `null` (length of null is null) |
| `null \| keys` | Error (keys requires object/array) |
| `null // "default"` | `"default"` (alternative operator treats null as false) |
| `if null then "yes" else "no" end` | `"no"` (null is falsy) |

### Null vs Empty
- `null` is a single value (the absence of a value)
- `empty` is the absence of any output (zero values produced)
- These are distinct: `[null]` produces one-element array; `[empty]` produces empty array

---

## 9. Type Checking Functions

### type
Returns type name as string:
- `1 \| type` → `"number"`
- `"x" \| type` → `"string"`
- `[] \| type` → `"array"`
- `{} \| type` → `"object"`
- `null \| type` → `"null"`
- `true \| type` → `"boolean"`

### Type Predicates
Built-in predicates for testing type membership:
- `isnumber` — true if number
- `isstring` — true if string
- `isarray` — true if array
- `isobject` — true if object
- `isnull` — true if null
- `isboolean` — true if boolean
- `isinfinite` — true if number is ±Inf
- `isnan` — true if number is NaN
- `isnormal` — true if number is normal (not subnormal/zero/inf/nan)

---

## 10. Known Type System Edge Cases

### Infinity and NaN Arithmetic
- `1 / 0` → `null` (division by zero returns null, not Inf; changed in 1.5)
- `0 / 0` → `null` (not NaN)
- `infinite * 0` → `null` (indeterminate form)
- `1e308 * 10` → `Infinity` (overflow to Inf in some operations)

### Array/Object with Mixed Types
- `[1, "a", null] | sort` → `[null, 1, "a"]` (sorts by type order)
- `{"a": 1, "b": "x"} | to_entries` → `[{key:"a", value:1}, {key:"b", value:"x"}]` (mixed types allowed in values)

### Recursive Comparison
- Arrays and objects are compared recursively
- `[[1]] == [[1]]` → `true`
- `{a: [1]} == {a: [1]}` → `true`
- Deep nesting is fully supported (though very deep recursion may cause stack issues)

---

## Sources

- jq Manual v1.8: https://jqlang.org/manual/
- Number representation discussion: https://github.com/jqlang/jq/issues/143
- Type system tests: https://github.com/jqlang/jq/tree/master/tests
