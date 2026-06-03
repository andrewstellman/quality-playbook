# jq String Interpolation and Format Strings

Extracted from jq manual v1.8 and jv_print.c / builtins.c implementations.

---

## 1. String Interpolation Syntax

String interpolation embeds jq expressions inside string literals using `\(expr)` syntax:

```jq
"Hello, \(.name)!"             # Embeds .name value
"The answer is \(1 + 1)"       # Evaluates expression and converts to string
"Nested: \(.a | .b | .c)"      # Pipes are fully supported
```

### Basic Semantics
- Expression inside `\(...)` is evaluated with the current input as context
- Result is converted to JSON representation and inserted as string
- Literal backslash requires `\\`

### Nested Parentheses
Parentheses within `\(...)` must be balanced:

```jq
"Value: \(if .x > 0 then .x else 0 end)"  # Nested parentheses OK
```

The lexer counts parenthesis depth to find the matching `)` that closes `\(`.

### Multiple Interpolations
```jq
"First: \(.a), Second: \(.b)"  # Multiple interpolations in one string
```

### Expression Failures
If the interpolated expression produces an error, the string interpolation fails:

```jq
"Value: \(.foo)"                # Errors if .foo fails (e.g., on non-object)
"Value: \(.foo?)"               # With optional, suppresses error and produces null
```

### Empty Expression
An empty expression in `\(...)` produces error:

```jq
"\()"                           # Error: empty expression
```

---

## 2. String Conversion (tostring and type-specific output)

### tostring
Converts input to string representation:

```jq
123 | tostring                  # → "123"
true | tostring                 # → "true"
false | tostring                # → "false"
null | tostring                 # → "null"
[1,2,3] | tostring              # → "[1,2,3]"
{"a":1} | tostring              # → "{\"a\":1}"
```

**Behavior**:
- Produces JSON representation as string
- Numbers preserve original literal form if unmutated
- Arrays and objects are fully JSON-serialized

### type-specific Output
Each type can be converted to string in various formats:

| Type | Default Output |
|------|-----------------|
| number | Decimal digits, preserving literal form if unmutated |
| string | As-is (already a string) |
| boolean | "true" or "false" |
| null | "null" |
| array | JSON array syntax |
| object | JSON object syntax |

---

## 3. Format Strings (@-syntax)

Format strings provide context-specific encoding. Syntax: `@format` or `"string" | @format`.

### @text
Raw text (no JSON escaping):

```jq
"hello\nworld" | @text          # → hello\nworld (literal \n, no newline)
```

Used for plain text output without JSON encoding.

### @json
Produces JSON representation:

```jq
{a:1} | @json                   # → "{\"a\":1}"
"hello" | @json                 # → "\"hello\""
```

Equivalent to piping through `tojson`.

### @html
HTML-escapes special characters:

```jq
"<script>alert('xss')</script>" | @html
# → &lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;
```

Escapes: `<` → `&lt;`, `>` → `&gt;`, `"` → `&quot;`, `'` → `&#39;`, `&` → `&amp;`.

### @uri
URL-encodes (percent-encoding):

```jq
"hello world" | @uri            # → "hello%20world"
"a=1&b=2" | @uri                # → "a%3D1%26b%3D2"
```

Encodes all special characters for safe URL usage.

### @csv
Produces CSV line (comma-separated, quoted):

```jq
["a","b,c","d\"e"] | @csv       # → "a","b,c","d\"e"
[1,2,3] | @csv                  # → 1,2,3 (numbers not quoted)
```

**Behavior**:
- Arrays converted to CSV row
- Strings with special chars (comma, quote, newline) are quoted
- Quote character (") inside string is escaped as ""
- Input must be array

### @tsv
Produces TSV line (tab-separated):

```jq
["a","b\tc","d"] | @tsv         # → a    b\tc    d
```

**Behavior**:
- Similar to @csv but uses tabs
- Quotes and escaping rules simpler (no quoting)
- Input must be array

### @sh
Shell-escapes (safe for shell usage):

```jq
"hello world" | @sh             # → 'hello world'
"it's" | @sh                    # → 'it'"'"'s'
```

**Behavior**:
- Wraps string in single quotes for shell safety
- Handles single quotes specially
- Input must be string or array (each element is escaped separately)

### @base64
Base64-encodes:

```jq
"hello" | @base64               # → "aGVsbG8="
```

Produces base64-encoded string.

### @base64d
Base64-decodes:

```jq
"aGVsbG8=" | @base64d           # → "hello"
```

Errors if input is not valid base64.

---

## 4. Format Functions (Alternative Syntax)

Format strings have function equivalents:

| Format String | Function Equivalent |
|---------------|-------------------|
| `@base64` | `tobase64` |
| `@base64d` | `frombase64` |
| `@uri` | Not directly available as function |
| `@csv` | `@csv` (no function form) |
| `@tsv` | `@tsv` (no function form) |
| `@html` | Not directly available as function |
| `@sh` | Not directly available as function |
| `@json` | `tojson` |
| `@text` | `tostring` |

### tojson and fromjson
```jq
{a:1} | tojson                  # → "{\"a\":1}"
"{\"a\":1}" | fromjson          # → {a:1}
```

**Behavior**:
- `tojson`: serializes to JSON string
- `fromjson`: parses JSON string (errors if invalid JSON)

---

## 5. String Building Patterns

### Array to String
```jq
["a","b","c"] | join(",")       # → "a,b,c"
["a","b","c"] | @csv            # → a,b,c (if no special chars)
```

### Conditionally Include
```jq
"Name: \(if .name then .name else "Unknown" end)"
```

### Iterate and Concatenate
```jq
[.[] | "Item: \(.)"] | join(", ")
```

### Number Formatting
jq has limited number formatting. To format numbers:

```jq
"Value: \(. | tostring)"        # Basic conversion
```

For locale-specific or advanced formatting, you must construct strings manually.

---

## 6. Edge Cases and Gotchas

### Null in String Interpolation
```jq
null | "Value: \(.)"            # → "Value: null"
```

Null is converted to the string "null".

### Empty Generator in Interpolation
```jq
"Values: \(if . then .x, .y else empty end)"
```

If expression produces `empty`, the interpolation produces error. Use alternative operator to handle:

```jq
"Values: \((.x, .y)? // "")"    # Safe version
```

### Numeric Precision in Output
```jq
1.0 | "Value: \(.)"             # → "Value: 1.0" (literal form preserved)
1.0 + 0 | "Value: \(.)"         # → "Value: 1" (literal form lost after operation)
```

### Recursive Interpolation
You cannot nest `\(...)` inside `\(...)`:

```jq
"Outer: \("Inner: \(.)")"       # Error: can't nest interpolations
```

Workaround: use variable binding:

```jq
. as $x | "Outer: \("Inner: \($x)")"  # Still problematic
```

Better approach: separate the inner computation:

```jq
("Inner: \(.)" | "Outer: \(.)") # Wrong approach
```

Actually, you must compute the inner string separately:

```jq
. as $x | ("\($x)" | "Outer: \(.)")  # Correct
```

### Format String Errors
If format string receives wrong type:

```jq
{a:1} | @csv                    # Error (requires array)
123 | @uri                       # Error (requires string)
```

Use `type` check or `?` optional to guard:

```jq
if type == "array" then @csv else tostring end
(@csv)?                         # Suppresses error, returns empty
```

---

## 7. Performance Considerations

### String Concatenation
Using `+` operator:

```jq
"a" + "b" + "c"                 # Creates intermediate strings
```

For many concatenations, collect and use `join`:

```jq
["a", "b", "c"] | join("")      # More efficient for many strings
```

### Interpolation Overhead
String interpolation evaluates expressions for each interpolation point. Avoid repeated expensive computations:

```jq
# Inefficient
"Names: \(.names[0]), \(.names[0])"

# Better
.names[0] as $first | "Names: \($first), \($first)"
```

---

## Sources

- jq Manual v1.8: https://jqlang.org/manual/
- jv_print.c: https://github.com/jqlang/jq/blob/master/src/jv_print.c
- builtins.c: https://github.com/jqlang/jq/blob/master/src/builtins.c
