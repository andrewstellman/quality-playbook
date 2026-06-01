# jq Filter Language — Grammar, Parsing, and Advanced Syntax

Extracted from jq parser.y (Bison grammar), compile.c, and language specification.

---

## 1. Grammar Overview

The jq filter language is an expression-oriented language with a formal grammar defined in parser.y. This document covers the formal structure and semantics of the language.

### Expression Categories

1. **Atomic expressions**: literals, identity, variable references
2. **Composite expressions**: arrays, objects, conditionals
3. **Operator expressions**: arithmetic, comparison, logical
4. **Pipe expressions**: sequential filter composition
5. **Functional expressions**: function calls, definitions

### Precedence and Associativity

Operators are listed from highest to lowest precedence. All binary operators are left-associative unless otherwise noted.

```
Precedence (highest to lowest):
1. Atomic: . | field | [expr] | {expr} | literal | $var | (expr)
2. Postfix: .[] | .[n] | .[n:m] | ? | @ format
3. Unary: not | - (negation)
4. Multiplicative: * | / | %
5. Additive: + | -
6. Comparison: == != < > <= >=
7. Logical AND: and
8. Logical OR: or
9. Alternative: //
10. Conditional: if-then-else
11. Assignment: |= //= += -= *= /= %=
12. Pipe: |
13. Comma: ,
```

---

## 2. Formal Grammar (Simplified BNF)

```
Program := Expression EOF

Expression := ConditionalExpr

ConditionalExpr := OrExpr 
                 | IfExpr

IfExpr := 'if' OrExpr 'then' Expression ('elif' OrExpr 'then' Expression)* 'else' Expression 'end'

OrExpr := AndExpr ('or' AndExpr)*

AndExpr := AlternativeExpr ('and' AlternativeExpr)*

AlternativeExpr := ComparisonExpr ('//' ComparisonExpr)*

ComparisonExpr := AdditiveExpr (('==' | '!=' | '<' | '>' | '<=' | '>=') AdditiveExpr)*

AdditiveExpr := MultiplicativeExpr (('+' | '-') MultiplicativeExpr)*

MultiplicativeExpr := PostfixExpr (('*' | '/' | '%') PostfixExpr)*

PostfixExpr := PrimaryExpr PostfixOperator*

PostfixOperator := '[' Expression ']'      # Array indexing
                 | '[' Expression ':' Expression ']'  # Slicing
                 | '.' FieldName           # Field access
                 | '.[]'                   # Iterator
                 | '?'                     # Optional
                 | '@' Format              # Format string

PrimaryExpr := '.' 
             | Literal
             | '$' Identifier
             | Identifier                 # Function call or variable reference
             | Identifier '(' FuncArgs ')'
             | '[' Expression ']'         # Array construction
             | '{' ObjectContents '}'     # Object construction
             | '(' Expression ')'         # Grouping
             | TryCatchExpr
             | ReduceExpr
             | ForeachExpr

Literal := NUMBER | STRING | 'true' | 'false' | 'null'

TryCatchExpr := 'try' Expression ('catch' Expression)?

ReduceExpr := 'reduce' Expression 'as' '$' Identifier 
              '(' Expression ';' Expression ')'

ForeachExpr := 'foreach' Expression 'as' '$' Identifier
               '(' Expression ';' Expression (';' Expression)? ')'
```

---

## 3. Update and Assignment Operators

Update operators modify values in-place and return the modified structure:

### Assignment Operators

| Operator | Meaning |
|----------|---------|
| `\|=` | Update operator: `.field \|= expr` |
| `//=` | Alternative update: `.field //= expr` |
| `+=` | Addition assignment: `.field += value` |
| `-=` | Subtraction assignment: `.field -= value` |
| `*=` | Multiplication assignment: `.field *= value` |
| `/=` | Division assignment: `.field /= value` |
| `%=` | Modulo assignment: `.field %= value` |

### Semantics
Update operators are shorthand for `(path | expr) as $new | (path = $new)`:

```jq
.a |= . + 1                    # Update .a by adding 1 to it
.a += 1                        # Shorthand for .a |= . + 1
.[] |= . * 2                   # Update all array elements
.a.b.c |= . + 1                # Deep update
```

### Complex Paths
Updates work on arbitrary paths:

```jq
.items[] |= .price * 1.1       # Update all items' prices
.data[.index] |= . + 1         # Update element at computed index
```

### Null Propagation in Updates
If path evaluates to null, update creates intermediate objects:

```jq
null | .a.b = 1                # → {a:{b:1}}
{} | .a.b = 1                  # → {a:{b:1}}
```

### Multiple Updates
Update operator applies to **all paths** matching:

```jq
[1,2,3] | .[] |= . * 2         # All elements multiplied
```

---

## 4. Try-Catch Expressions

```jq
try EXPR
try EXPR catch HANDLER
EXPR?                          # Shorthand for: try EXPR catch empty
```

### Semantics
- If EXPR succeeds, output its results
- If EXPR fails with error, catch HANDLER and pass error message
- HANDLER receives the error message as input

Example:

```jq
try .foo catch "field missing"
try (.a / .b) catch "division failed: \(.)"
```

### Error Message Passing
The catch handler receives error message as a string:

```jq
try error("custom") catch .    # → "custom"
try (1 / 0) catch .            # → error message (implementation-specific)
```

### Optional Chaining
The `?` operator is shorthand for `try-catch empty`:

```jq
.foo?                          # Equivalent to: try .foo catch empty
.[]?                           # Equivalent to: try .[] catch empty
```

When an optional operation errors, it produces `empty` (no output), not an error message.

---

## 5. Reduce Expression

```jq
reduce GENERATOR as $VAR (INIT; UPDATE)
```

### Semantics
1. Evaluate GENERATOR to get a sequence of values
2. For each value, bind it to $VAR
3. Start with accumulator = INIT
4. For each iteration: `accumulator = (accumulator | UPDATE where $VAR is bound)`
5. Return final accumulator

### Examples

Sum of array:
```jq
reduce .[] as $item (0; . + $item)
# Input: [1,2,3]
# Step 1: accumulator = 0
# Step 2: accumulator = 0 + 1 = 1
# Step 3: accumulator = 1 + 2 = 3
# Step 4: accumulator = 3 + 3 = 6
# Output: 6
```

Count matches:
```jq
reduce .[] as $item (0; if $item > 5 then . + 1 else . end)
```

Group by key:
```jq
reduce .[] as $item ({};
  .[$item.type] //= [] | .[$item.type] += [$item]
)
```

### Variables in reduce
The variable $VAR is scoped within the reduce expression:

```jq
reduce .[] as $x (0; . + $x) | $x  # Error: $x not in scope
```

---

## 6. Foreach Expression

```jq
foreach GENERATOR as $VAR (INIT; UPDATE)
foreach GENERATOR as $VAR (INIT; UPDATE; EXTRACT)
```

### Semantics
Similar to reduce, but can emit values at each step:

1. For each generated value, bind to $VAR
2. Update accumulator: `accumulator = (accumulator | UPDATE)`
3. Emit result of EXTRACT (if provided; defaults to accumulator)
4. If EXTRACT produces `empty`, nothing is emitted

### Examples

Emit intermediate sums:
```jq
foreach .[] as $item (0; . + $item)
# Input: [1,2,3]
# Output: 1, 3, 6
```

Emit conditionally:
```jq
foreach .[] as $item (0; . + $item; if . > 2 then . else empty end)
# Input: [1,2,3]
# Output: 3, 6 (skips 1 and 2)
```

Running maximum:
```jq
foreach .[] as $item (0; if $item > . then $item else . end)
# Input: [3,1,4,1,5]
# Output: 3, 3, 4, 4, 5
```

---

## 7. Object Construction

```jq
{key: value}                   # Static key
{(expr): value}                # Computed key
{a, b, c}                      # Shorthand for {a: .a, b: .b, c: .c}
{a: .x, b: .y}                 # Renamed fields
{...expr}                      # Object spread (if supported)
```

### Semantics

Static keys:
```jq
{a: 1, b: 2}                   # → {a: 1, b: 2}
```

Computed keys (key must be string):
```jq
{(.name): .value}              # Key from .name, value from .value
```

Shorthand (field from input):
```jq
{a, b}                         # → {a: .a, b: .b}
```

Expression values:
```jq
{name: (.first + " " + .last)} # Computed value
```

Multiple outputs:
```jq
{a: (1, 2)}                    # → {a:1}, {a:2} (produces two objects)
```

---

## 8. Array Construction

```jq
[expr]                         # Collect all outputs into array
[expr1, expr2, expr3]          # Multiple expressions
```

### Semantics
Array construction collects **all outputs** of the expression:

```jq
[1, 2, 3]                      # → [1, 2, 3] (three literal outputs, collected)
[.[] | . * 2]                  # Collects all multiplied elements
[if . > 5 then . else empty end]  # Collects only values > 5
```

Generator interaction:
```jq
[1, 2, 3]                      # One output: [1, 2, 3]
1, 2, 3                        # Three outputs: 1, 2, 3
[(1, 2, 3)]                    # One output: [1, 2, 3]
```

---

## 9. Variable Binding and Scoping

Binding with `as` pattern:

```jq
EXPR as $VAR | REST
```

### Scoping
Variable is scoped to REST; not available outside:

```jq
(.a as $x | .b + $x) + $x      # Error: $x not in scope after |
(.a as $x | .b + $x)           # OK
```

Nested bindings:
```jq
.a as $x | .b as $y | $x + $y  # Both $x and $y in scope
```

### Pattern Matching (if supported)
Some jq versions support destructuring:

```jq
[1, 2] as [$a, $b] | $a + $b   # → 3
{x: 1, y: 2} as {$x, $y} | $x + $y  # → 3
```

---

## 10. Recursion and tail-call Optimization

### Recursive Function Definition

```jq
def fib: if . <= 1 then . else ((. - 1) | fib) + ((. - 2) | fib) end;
```

### Tail Position

A recursive call is in **tail position** if it's the last operation in the function:

```jq
def f: if . <= 0 then "done" else (. - 1 | f) end;  # Tail position (TCO applied)
```

Not in tail position:
```jq
def f: (. - 1 | f) + 1;        # Not tail position (arithmetic after recursive call)
```

### TCO Limitation

TCO only applies to **functions with no arguments**:

```jq
def f: (. - 1 | f) end;        # TCO applies
def f($n): ($n - 1 | f($n)) end; # No TCO (function has parameter)
```

---

## 11. Pipe Operator Semantics

The pipe chains outputs through filters:

```jq
A | B | C
```

Is equivalent to:

```jq
. | A | (. | B) | (. | C)
```

Each segment receives the output of the previous as input.

### Generator Interaction

If A produces multiple outputs, B is applied to each:

```jq
[1,2,3] | .[] | . + 1          # → 2, 3, 4
(1, 2, 3) | . + 1              # → 2, 3, 4
```

---

## 12. Comma Operator

Lowest precedence; produces multiple outputs:

```jq
.a, .b, .c                     # Three separate outputs
if . then 1, 2 else 3 end      # Produces 1,2 or 3
1, (2, 3)                      # → 1, 2, 3 (flattened)
```

---

## Sources

- parser.y (Bison grammar): https://github.com/jqlang/jq/blob/master/src/parser.y
- jq Manual v1.8: https://jqlang.org/manual/
- compile.c: https://github.com/jqlang/jq/blob/master/src/compile.c
