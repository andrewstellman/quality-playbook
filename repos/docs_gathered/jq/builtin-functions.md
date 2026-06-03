# jq Builtin Functions — Type Introspection, Array/Object Operations, and Transformations

Extracted from jq manual v1.8 and builtin.jq/builtins.c implementations.

---

## 1. Type Introspection

### type
Returns the data type as a string.

```jq
1 | type                      # → "number"
"hello" | type                # → "string"
[] | type                     # → "array"
{} | type                     # → "object"
true | type                   # → "boolean"
null | type                   # → "null"
(1/0) | type                  # → "number" (even if Infinity)
```

### length
Returns the number of elements/characters/keys.

| Input | Output |
|-------|--------|
| `[1,2,3]` | `3` |
| `"hello"` | `5` |
| `{"a":1,"b":2}` | `2` |
| `null` | `null` (special case) |
| `42` | `42` (absolute value for numbers) |
| `true` | `1` |
| `false` | `0` |

**Behavior**:
- Strings: counts codepoints (not bytes)
- Objects: counts keys
- Numbers: returns absolute value
- null: returns null (not error)
- Booleans: return 1 or 0

### Type Predicates
Builtin predicates that return boolean:

```jq
isnumber              # true if input is number
isstring              # true if input is string
isarray               # true if input is array
isobject              # true if input is object
isnull                # true if input is null
isboolean             # true if input is boolean
isinfinite            # true if number is ±Infinity
isnan                 # true if number is NaN
isnormal              # true if number is normal (not subnormal/zero/inf/nan)
isfinite              # true if number is finite (not inf/nan)
```

---

## 2. Array Operations

### sort and sort_by
```jq
[3,1,2] | sort                # → [1,2,3]
[{a:2},{a:1}] | sort_by(.a)   # → [{a:1},{a:2}]
```

**Behavior**:
- Sorts in ascending order following jq's type ordering (null < booleans < numbers < strings < arrays < objects)
- Elements of the same type are sorted by natural order (numeric, lexicographic, etc.)
- Sorting is stable: equal elements maintain relative order

### reverse
```jq
[1,2,3] | reverse              # → [3,2,1]
"abc" | reverse                # → "cba"
```

### unique and unique_by
```jq
[1,2,1,3,2] | unique           # → [1,2,3]
[{a:1},{a:2},{a:1}] | unique_by(.a)  # → [{a:1},{a:2}]
```

**Behavior**:
- Returns sorted array with duplicates removed
- Comparison uses equality semantics (not identity)
- `unique_by(f)` groups by expression result and keeps first of each group

### group_by
```jq
[{a:1,b:2},{a:1,b:3},{a:2,b:4}] | group_by(.a)
# → [[{a:1,b:2},{a:1,b:3}], [{a:2,b:4}]]
```

**Behavior**:
- Groups consecutive equal values (sorted first by expression)
- Returns array of arrays, each group is an array

### flatten
```jq
[[1,[2]],3] | flatten           # → [1,2,3]
[[1,[2]],3] | flatten(1)        # → [1,[2],3] (flatten 1 level)
```

**Behavior**:
- `flatten` with no argument: completely flattens all nesting
- `flatten(n)`: flattens n levels deep
- Only flattens arrays (other values are left as-is)

### min, max, min_by, max_by
```jq
[3,1,2] | min                  # → 1
[3,1,2] | max                  # → 3
[{a:2},{a:1}] | min_by(.a)     # → {a:1}
```

**Behavior**:
- Uses type ordering for comparison
- Empty array: `min` and `max` error
- `min_by` and `max_by` extract first minimum/maximum

### add
```jq
[1,2,3] | add                  # → 6 (sum)
["a","b","c"] | add            # → "abc" (concatenation)
[[1,2],[3,4]] | add            # → [1,2,3,4] (concatenation)
[{a:1},{b:2}] | add            # → {a:1,b:2} (merge)
[] | add                        # → null (empty array)
```

**Behavior**:
- Sums numbers, concatenates strings/arrays, merges objects
- Order matters: right-associative merge for objects
- Empty array returns `null`

### indices
```jq
[0,1,2,1,3,1,4] | indices(1)    # → [1,3,5]
"abcabc" | indices("ab")        # → [0,3]
```

**Behavior**:
- Returns array of indices where value appears
- Works on strings (substring search) and arrays (element search)

### contains and inside
```jq
[1,2,3] | contains([2])        # → true
"foobar" | contains("bar")     # → true
{a:1,b:2} | contains({a:1})    # → true (subset check)
```

**Behavior**:
- `contains(x)`: true if input contains x (as substring, array element, or object subset)
- `inside(x)`: true if input is a subset of x (inverse of contains)
- Type-aware: string containment vs array element containment

---

## 3. String Functions

### split and join
```jq
"a,b,c" | split(",")           # → ["a","b","c"]
["a","b","c"] | join(",")      # → "a,b,c"
```

**Behavior**:
- `split(sep)`: splits string by separator (empty separator splits into characters)
- `join(sep)`: joins array of strings with separator
- null in array: converted to string "null"

### ltrimstr and rtrimstr
```jq
"foobar" | ltrimstr("foo")     # → "bar"
"foobar" | rtrimstr("bar")     # → "foo"
"foobar" | ltrimstr("baz")     # → "foobar" (no match, unchanged)
```

**Behavior**:
- Removes prefix/suffix if present; no error if not found
- Returns input unchanged if string doesn't start/end with the given string

### ascii_upcase and ascii_downcase
```jq
"Hello" | ascii_upcase         # → "HELLO"
"Hello" | ascii_downcase       # → "hello"
```

**Behavior**:
- Only affects ASCII characters (a-z, A-Z)
- Non-ASCII characters pass through unchanged

### startswith and endswith
```jq
"foobar" | startswith("foo")   # → true
"foobar" | endswith("bar")     # → true
```

**Behavior**:
- Returns boolean
- Case-sensitive

### implode and explode
```jq
[72, 101, 108, 108, 111] | implode   # → "Hello"
"Hello" | explode                    # → [72, 101, 108, 108, 111]
```

**Behavior**:
- `implode`: converts array of codepoints to string
- `explode`: converts string to array of codepoints
- Handles Unicode properly

---

## 4. Object and Array Transformation

### keys and keys_unsorted
```jq
{b:1,a:2} | keys               # → ["a","b"] (sorted)
{b:1,a:2} | keys_unsorted      # → ["b","a"] (insertion order)
[10,20,30] | keys              # → [0,1,2] (indices)
```

**Behavior**:
- `keys` returns sorted array of keys (or indices for arrays)
- `keys_unsorted` preserves insertion order (objects only)

### values
```jq
{a:1,b:2} | values             # → 1, 2 (produces multiple outputs)
[1,2,3] | values               # → 1, 2, 3 (same as .[])
```

**Behavior**:
- Returns values (not keys) from object or array
- Produces multiple outputs (like `.[]`)

### to_entries and from_entries
```jq
{a:1,b:2} | to_entries         # → [{key:"a",value:1},{key:"b",value:2}]
[{key:"a",value:1}] | from_entries  # → {a:1}
```

**Behavior**:
- `to_entries`: converts object to array of {key, value} objects
- `from_entries`: converts array of {key, value} objects to object
- `from_entries` is lenient: accepts `{name, value}` and `{key, value}` forms

### with_entries
```jq
{a:1,b:2} | with_entries(.value += 10)
# → {a:11,b:12}
```

**Behavior**:
- Shorthand for: `to_entries | map(...) | from_entries`
- Transforms while preserving structure

### map and select
```jq
[1,2,3] | map(. + 1)           # → [2,3,4]
[1,2,3,4] | map(select(. > 2)) # → [3,4]
```

**Behavior**:
- `map(f)`: applies filter to each element, collects results
- `select(cond)`: filters values by condition; produces empty if false
- `map(select(...))` filters and collects

---

## 5. Path Expressions and Manipulation

### path
```jq
{a:{b:1}} | path(.a.b)         # → ["a","b"]
[1,2,3] | path(.[1])           # → [1]
```

**Behavior**:
- Returns array of keys/indices to reach a value
- Can be used with `getpath`, `setpath`, `delpaths`

### getpath
```jq
{a:{b:1}} | getpath(["a","b"]) # → 1
[1,2,3] | getpath([1])         # → 2
```

**Behavior**:
- Retrieves value at the given path
- Path argument is an array of keys/indices

### setpath
```jq
{a:{b:1}} | setpath(["a","b"]; 2)
# → {a:{b:2}}
```

**Behavior**:
- Sets value at path, creating intermediate objects/arrays as needed
- If intermediate keys don't exist, creates them

### delpaths
```jq
{a:1,b:2,c:3} | delpaths([["a"],["c"]])
# → {b:2}
```

**Behavior**:
- Deletes multiple paths from input
- Returns modified structure

---

## 6. Iteration and Reduction (Core; see filter-language.md for details)

### Any and all
```jq
[true, false, true] | any       # → true
[true, true, true] | all        # → true
[1,2,3] | any(. > 5)            # → false
[1,2,3] | all(. > 0)            # → true
```

**Behavior**:
- `any`: true if any element matches condition (or is truthy)
- `all`: true if all elements match condition
- Empty array: `any` returns false, `all` returns true

### Index and Rindex
```jq
[1,2,3,2,1] | index(2)         # → 1 (first occurrence)
[1,2,3,2,1] | rindex(2)        # → 3 (last occurrence)
```

**Behavior**:
- `index(x)`: returns array index of first x
- `rindex(x)`: returns array index of last x
- Returns `null` if not found

---

## 7. Recursive Descent

### recurse and walk
```jq
{"a":{"b":{"c":1}}} | recurse   # Produces nested values recursively
[[1,2],[3,[4,5]]] | walk(if type == "array" then sort else . end)
```

**Behavior**:
- `recurse`: applies filter recursively until no new values
- `recurse(f)` with filter: recursively applies f
- `walk(f)`: recursively applies f to all values depth-first

---

## Sources

- jq Manual v1.8: https://jqlang.org/manual/
- builtins.c: https://github.com/jqlang/jq/blob/master/src/builtins.c
- builtin.jq: https://github.com/jqlang/jq/blob/master/src/builtin.jq
