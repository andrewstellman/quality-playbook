# jq Behavioral Contracts and Edge Cases

Extracted from jq manual v1.8, GitHub issues, implementation details (execute.c, jv.c), and community discussions. This document specifies MUST/SHOULD behaviors and known edge cases for code quality auditing.

---

## 1. Type System — MUST Requirements

### Type Coercion
- jq MUST NOT perform implicit type coercion
- Operations between incompatible types MUST error: `1 + "1"` → Error
- Type predicates (isnumber, isstring, etc.) MUST return boolean, not error
- Type checking MUST be strict: `null == 0` → false (not coerced to equal)

### Comparison and Ordering
- Total type ordering MUST be: null < false < true < numbers < strings < arrays < objects
- Within types: numbers (numeric), strings (lexicographic UTF-8), arrays (element-wise), objects (key-wise)
- Comparison operators (<, >, <=, >=) MUST follow type ordering
- Equality (==) MUST NOT coerce types; different types are never equal
- NaN MUST compare as: NaN != NaN, NaN is not <, >, <=, >= to any value

### Sort Stability
- sort and sort_by MUST maintain relative order of equal elements (stable sort)
- This is critical for multi-field sorting: `sort_by(.type) | sort_by(.name)` must preserve .type groups

---

## 2. Null Handling — MUST/SHOULD

### Null Propagation
- `null | .foo` MUST return `null` (field access on null returns null)
- `null | .[0]` MUST return `null` (indexing null returns null)
- `null | .[]` MUST error: "Cannot iterate over null"
- `null | length` MUST return `null` (length of null is null)
- `null + 1` MUST error: "null cannot be added to number"

### Null as Value
- `null == null` MUST return true
- `[null]` MUST produce array with one element (null), not empty array
- `empty` MUST be distinct from `null` (zero outputs vs. one null output)
- `null // "default"` MUST return "default" (null is falsy in alternative operator)

### Null in Collections
- Objects with null values are allowed: `{a: null}`
- Arrays with null elements are allowed: `[1, null, 3]`
- keys on object with null values MUST include the key
- values on object with null values MUST include null

---

## 3. Number Representation — MUST/SHOULD

### IEEE754 Double Representation
- All numbers MUST be internally represented as IEEE754 64-bit doubles
- Arithmetic operations MUST produce doubles (never higher precision)
- Special values MUST be representable: Infinity, -Infinity, NaN

### Literal Form Preservation
- Number literals MUST preserve original form if unmutated: `echo '1.0' | jq '.'` → `1.0`
- After mutation, literal form MUST be discarded: `1.0 + 0` → `1`
- Mutation includes: arithmetic operations, logical operations, conditionals (any evaluation)
- Format MUST be preserved exactly as in source: `1e10`, `1.0`, `0.1` each output in original form if unmutated

### Number Precision and Overflow
- Precision MUST be limited to 53-bit significand (15-17 decimal digits)
- Overflow to Infinity: `1e308 * 10` MAY produce Infinity
- Underflow to zero: Very small numbers MAY underflow to zero
- Division by zero: `1 / 0` MUST return `null` (not Infinity or error)
- `0 / 0` MUST return `null` (not NaN)

### Rounding and Comparison
- Equality comparison MUST use IEEE754 semantics: `1.0 == 1` → true (numerically equal)
- Rounding errors MUST be handled by IEEE754: `0.1 + 0.2 == 0.3` → false (due to binary representation)
- Very large integers (>2^53) MUST lose precision when used in arithmetic

---

## 4. String Handling — MUST/SHOULD

### UTF-8 Encoding
- Strings MUST be UTF-8 encoded internally
- String indexing and slicing MUST operate on codepoints, not bytes
- `"你好" | length` MUST return `2` (codepoints), not byte count

### String Operations
- `split("")` MUST produce array of individual codepoints
- String concatenation MUST preserve UTF-8
- `startswith` and `endswith` MUST be case-sensitive
- Escape sequences MUST be interpreted: `"\n"` → newline, `"\u0041"` → 'A'

### String Interpolation
- `\(expr)` MUST evaluate expr with current input context
- Result MUST be JSON-serialized and embedded
- Nested `\(...)` MUST error (no recursive interpolation)
- Balanced parentheses inside `\(...)` MUST be counted correctly

---

## 5. Array Operations — MUST/SHOULD

### Indexing
- Zero-based indexing MUST apply: `.[0]` is first element
- Negative indices MUST work: `.[-1]` is last element
- Out-of-bounds on read: `.[1000]` on 5-element array MUST return `null`
- Out-of-bounds on write: `.[1000] = 1` MUST extend array with nulls
- Non-integer indices MUST error: `.[1.5]` → Error

### Slicing
- `.[n:m]` MUST be exclusive on right: `.[0:2]` includes indices 0, 1
- Omitted indices: `.[:5]` → from start, `.[2:]` → to end
- Reversed slice: `.[10:5]` MUST return empty array (not error)
- Negative slice indices MUST work: `.[-2:]` is last two elements

### Iterator
- `.[]` on array MUST produce individual elements (not nested array)
- `.[]` on object MUST produce values (not keys)
- `.[]` on non-iterable MUST error
- `.[]?` (optional iterator) MUST produce `empty` on non-iterable (not error)

---

## 6. Object Operations — MUST/SHOULD

### Key Access
- `.foo` MUST access "foo" key in object
- `."foo-bar"` MUST access "foo-bar" key (quotes required for special characters)
- `.foo.bar` MUST chain access; each step checks type
- Non-existent key: `.missing` on `{}` MUST return `null`

### Key Type
- Keys MUST be strings; numeric keys stored as strings: `{1: "value"}` has string key "1"
- Accessing with non-string MUST error: `.[1]` on object with string keys → Error
- Computed keys: `{(.expr): value}` MUST evaluate expr to string

### Merging and Updates
- `{a:1} + {b:2}` MUST produce `{a:1,b:2}` (merge)
- Key conflicts: `{a:1} + {a:2}` MUST give right value (`{a:2}`)
- Recursive merge: `{a:{x:1}} * {a:{y:2}}` MUST give `{a:{x:1,y:2}}`
- `* {}` with deep nesting MUST recurse: `{a:{b:{c:1}}} * {a:{b:{d:2}}}` → `{a:{b:{c:1,d:2}}}`

---

## 7. Error Handling — MUST/SHOULD

### try-catch Semantics
- `try EXPR catch HANDLER` MUST catch errors from EXPR
- HANDLER MUST receive error message as string input
- `try EXPR` alone (no catch) MUST use `empty` as handler
- Uncaught errors MUST halt execution and produce error output

### Optional Operator (?)
- `EXPR?` MUST be equivalent to `try EXPR catch empty`
- Errors MUST convert to `empty` (no output), not error message
- Optional applies only to last operation: `.foo.bar?` is `(.foo).bar?`, not `.foo(.bar?)`

### Error Propagation
- Errors in sub-expressions MUST propagate unless caught
- `1 + error("msg")` MUST error (no auto-recovery)
- `(1 + error("msg"))?` MUST produce `empty`

### Type Errors
- Operations on wrong types MUST error with descriptive message
- Message format MAY vary by operation (implementation detail)
- Type error MUST NOT silently return null or default value

---

## 8. Generator and Multiplicity — MUST/SHOULD

### Multiple Outputs
- Comma operator MUST produce multiple outputs: `1, 2, 3` → three separate values
- Pipe to generator MUST apply right to each output: `[1,2,3] | .[] | . + 1` → 2, 3, 4
- Function calls MUST NOT automatically flatten multiple outputs from parameters

### Array Collection
- `[EXPR]` MUST collect all outputs into single array
- `[1, 2, 3]` as literals MUST produce single array (literal outputs collected)
- `[(1, 2, 3)]` MUST produce `[1, 2, 3]`

### Lazy vs. Eager Evaluation
- Comma operator MUST be lazy (outputs not materialized until needed)
- Array construction MUST materialize all outputs
- `map(EXPR)` MUST apply EXPR to each element and collect results
- Generator in function argument MUST pass all outputs (each separately evaluated)

---

## 9. Conditional and Boolean — MUST/SHOULD

### Truthiness
- Falsy values MUST be: `false`, `null`
- Truthy values: Everything else (`0`, `""`, `[]`, `{}` are all truthy)
- `if COND then A else B end` MUST use falsy rule (not JavaScript-style truthiness)

### and/or Short-Circuiting
- `false and EXPR` MUST NOT evaluate EXPR; return `false`
- `true or EXPR` MUST NOT evaluate EXPR; return `true`
- `true and EXPR` MUST evaluate and return EXPR
- `false or EXPR` MUST evaluate and return EXPR

### not Operator
- `not` MUST negate truthiness: `true | not` → `false`, `1 | not` → `false`
- `null | not` MUST return `true` (null is falsy)

---

## 10. Update Expressions — MUST/SHOULD

### Path Modification
- `.[0] = 1` MUST modify array at index 0
- `.foo = 1` MUST modify object field "foo"
- `.foo.bar = 1` MUST create intermediate objects if missing (null → {})
- `.|=` MUST return modified structure, not just the modified value

### Update on Multiple Paths
- `.[] |= EXPR` MUST apply EXPR to each element and return modified array
- Multiple paths (.a, .b): Each path is updated separately
- Updates MUST maintain structure (arrays stay arrays, objects stay objects)

### Null Propagation in Updates
- `null | .a = 1` MUST create object: `{a: 1}`
- `null | .[0] = 1` MUST create array: `[1]`
- Intermediate nulls MUST be converted to appropriate containers

---

## 11. Reduce and Foreach — MUST/SHOULD

### reduce Variable Scope
- Accumulator (.) MUST be available in UPDATE expression
- Generator variable ($VAR) MUST be available in UPDATE expression
- Variables MUST NOT leak out of reduce scope

### foreach Emit Behavior
- EXTRACT expression MUST control output
- `empty` in EXTRACT MUST produce no output for that iteration
- Multiple outputs in EXTRACT MUST produce multiple results for that iteration
- If EXTRACT omitted, final accumulator MUST be used

### Accumulator Semantics
- Accumulator MUST be piped through UPDATE: `(. | UPDATE where $VAR bound)`
- Each iteration MUST use the result of previous iteration
- Initial value MUST be used for first iteration

---

## 12. Path Expressions — MUST/SHOULD

### path Function
- `path(EXPR)` MUST return array of keys/indices to value
- Multiple outputs: if EXPR produces multiple paths, each MUST be returned
- Path MUST work with nested access: `path(.a.b.[0].c)`

### getpath/setpath/delpaths
- `getpath(PATH_ARRAY)` MUST retrieve value at path
- `setpath(PATH_ARRAY; VALUE)` MUST set value, creating intermediates
- `delpaths(ARRAY_OF_PATHS)` MUST delete multiple paths
- Non-existent paths in delete MUST be ignored (not error)

---

## 13. Recursion and TCO — MUST/SHOULD

### Tail-Call Optimization
- Functions with no arguments in tail position MUST be TCO-optimized
- Functions with arguments MUST NOT be TCO-optimized
- Tail position MUST be the last operation in function body
- TCO MUST not increase stack depth on deep recursion

### Recursion Limits
- Very deep recursion (>10k levels) without TCO SHOULD fail gracefully
- Stack exhaustion SHOULD produce clear error message
- TCO SHOULD enable practical deep recursion without limit

---

## 14. Known Implementation Divergences and Ambiguities

### Number Division Behavior
- `/` on numbers MUST produce double (standard)
- Division by zero behavior: some implementations return null, some infinity (jq returns null)

### Sorting Stability
- Implementations MUST maintain stable sort (equal elements preserve order)
- Pre-sorting before group_by MUST preserve groups in stable order

### Error Message Format
- Error messages MAY vary between implementations
- Applications MUST NOT depend on exact error message text
- Error type (type error, arithmetic error, etc.) MAY be indicated by message

### Module System Variations
- Module paths and search order MAY vary by implementation
- Module caching behavior MAY be implementation-defined
- Include vs. import semantics MUST be as specified, but caching policy is flexible

### Floating-Point Edge Cases
- NaN comparison results in unspecified order in sort
- Very large integers (>2^53) MUST have precision loss
- Subnormal numbers MUST be handled according to IEEE754

---

## 15. Edge Cases and Gotchas

### Object Iteration Order
- Object key iteration order SHOULD be insertion order (implementation detail)
- Code MUST NOT depend on alphabetical order (keys are unordered in spec)
- Iteration SHOULD be consistent within a session

### Recursive Structures
- Circular references MUST NOT be creatable (JSON constraint)
- Deep nesting (100+ levels) SHOULD work but MAY have performance implications
- Very deep recursion (>1000 levels) MUST NOT overflow stack for TCO functions

### Unicode and Encoding
- Surrogate pairs MUST be handled correctly (UTF-16 → UTF-8 conversion)
- Invalid UTF-8 SHOULD be rejected or handled gracefully
- Combining characters MUST be preserved as-is (no normalization)

### Empty Values
- `empty` MUST produce zero outputs (not null, not false, not missing)
- `[empty]` MUST produce `[]` (empty array, not error)
- Generator producing `empty` MUST be handled correctly in all contexts

---

## Sources

- jq Manual v1.8: https://jqlang.org/manual/
- GitHub Issues: https://github.com/jqlang/jq/issues
- jqlang/jq Wiki: https://github.com/jqlang/jq/wiki
- Implementation files: execute.c, jv.c, compile.c, builtin.jq
