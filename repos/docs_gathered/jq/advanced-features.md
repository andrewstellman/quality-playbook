# jq Advanced Features — Definitions, Recursion, Variable Binding, Modules, and Special Functions

Extracted from jq manual v1.8, GitHub wiki (Advanced Topics), and builtin.jq implementation.

---

## 1. Function Definitions (def)

Syntax: `def name: body;` or `def name(args): body;`

```jq
def double: . * 2;
def add(x): . + x;
def f(x; y): x + y;             # Multiple arguments separated by semicolons
5 | double                      # → 10
5 | add(3)                      # → 8
```

### Function Scope
Functions are scoped **lexically** within the expression they're defined in:

```jq
def f: . + 1; [1,2,3] | map(f)  # → [2,3,4]
f                               # Error: f not defined in this scope
```

Functions defined at top-level scope are available throughout the program.

### Recursion
Functions can call themselves:

```jq
def factorial: if . <= 1 then 1 else . * ((. - 1) | factorial) end;
5 | factorial                   # → 120
```

**Recursion without arguments**: Eligible for tail-call optimization (TCO). Deep recursion won't overflow stack.

**Recursion with arguments**: Not TCO-optimized; deep recursion will exhaust stack.

### Mutual Recursion
Using local function definitions:

```jq
def f: if . <= 0 then "done" else (. - 1 | g) end;
def g: if . <= 0 then "done" else (. - 1 | f) end;
```

Mutual recursion requires both functions to be defined before either is called.

### Parameter Passing
Parameters are passed by value (filters, not values). A parameter is a filter that will be evaluated when referenced:

```jq
def f($x): $x + 1;              # $x is a value binding
def g(x): x + 1;                # x is a filter (expression)
5 | f(.)                        # Passes value 5
5 | g(.)                        # Passes filter . (identity)
```

In practice, all parameters should use `$` prefix to denote value bindings.

---

## 2. Variable Binding and Scoping

Variables are introduced with the `as` pattern: `expr as $var | rest`

```jq
.a as $x | .b as $y | $x + $y   # Binds .a to $x, .b to $y
[.a, .b] | .[0] as $x | .[1] as $y | $x + $y
```

### Scope Rules
A variable is scoped to the rest of the expression after binding:

```jq
(.a as $x | .b) + $x            # Error: $x not in scope for + operator
(.a as $x | .b + $x)            # OK: $x is in scope
.a as $x | (.b as $y | $x + $y) # OK: $x and $y are both in scope
```

### Lexical Scoping
Variables are **lexically scoped**, not dynamically scoped. Inner definitions shadow outer ones:

```jq
1 as $x | (2 as $x | $x)        # Inner $x (2) shadows outer $x
# → 2
```

### Multiple Patterns
The `as` operator supports pattern matching (advanced):

```jq
[1,2,3] as [$a, $b, $c] | $a + $b + $c  # Destructuring
{a:1,b:2} as {$a, $b} | $a + $b         # Object destructuring (shorthand)
```

---

## 3. Advanced Reduction and Iteration

### reduce
Stateful iteration with accumulator:

```jq
reduce .[] as $item (0; . + $item)      # Sum array elements
reduce .[] as $item ({}; .[$item|tostring] = 1)  # Create set
```

**Semantics**:
- `reduce EXPR as $VAR (INIT; UPDATE)`
- For each output of EXPR, bind it to $VAR
- Start with accumulator = INIT
- For each iteration, accumulator = UPDATE (where . is current accumulator)
- Final accumulator is the result

### foreach
Iterator with optional state emission:

```jq
foreach .[] as $item (0; . + $item)     # Sum (like reduce)
foreach .[] as $item (0; . + $item; if . > 10 then . else empty end)  # Emit conditionally
```

**Semantics**:
- `foreach EXPR as $VAR (INIT; UPDATE; EXTRACT?)`
- Similar to reduce, but can emit values at each step
- EXTRACT (optional) determines what to output; defaults to final accumulator
- If EXTRACT produces `empty`, nothing is emitted

### while and until
Loop constructs:

```jq
1 | while(. < 100; . * 2)       # Multiply by 2 while < 100
# → 1, 2, 4, 8, 16, 32, 64 (produces all intermediate values)

1 | until(. >= 100; . * 2)      # Multiply by 2 until >= 100
# → 128 (produces final value only)
```

**Semantics**:
- `while(COND; UPDATE)`: emit intermediate values while condition is true
- `until(COND; UPDATE)`: emit final value when condition becomes true
- Both are generators; produce multiple outputs

---

## 4. Label and Break

Control flow for breaking out of loops:

```jq
label $out | foreach .[] as $item (0; . + 1; if . == 3 then ., break $out else . end)
# Breaks when count reaches 3
```

**Semantics**:
- `label $name | expr`: establishes label
- `break $name`: causes the label to produce `empty` and exit
- Break relationship is **lexical**: $name must be visible from break

### Use Cases
Breaking out of `reduce`, `foreach`, `while`, or deep nesting:

```jq
label $done | reduce .[] as $item (0; 
  if . > 100 then break $done else . + $item end
)
# Exits reduce early if accumulator exceeds 100
```

---

## 5. Environment Variables and Input

### $ENV
Access environment variables:

```jq
$ENV.HOME                       # → user's home directory
$ENV.PATH                       # → PATH environment variable
$ENV.MISSING                    # → null (undefined env vars are null)
```

**Behavior**:
- `$ENV` is an object with all environment variables as keys
- Accessing non-existent variable returns `null`
- Case-sensitive (Linux/Unix); case-insensitive on Windows

### env
Function form to access environment:

```jq
env.HOME                        # Equivalent to $ENV.HOME
env                             # Returns entire environment as object
```

### input and inputs
Read additional JSON values from input stream:

```jq
input                           # Reads next JSON value
inputs                          # Produces remaining JSON values as generator
```

**Use cases**:
- Process multiple JSON objects from stdin
- Read first value normally, then use `inputs` for rest

Example with multiple objects:

```jq
# Input: {"a":1}\n{"b":2}\n{"c":3}
. as $first | [inputs] | [$first] + .
# → [{"a":1}, {"b":2}, {"c":3}]
```

---

## 6. Error Handling: error and debug

### error
Produce an error:

```jq
if . < 0 then error("negative number") else . end
```

**Behavior**:
- Halts execution with given message
- Can be caught with `try-catch`

### debug
Output debug information to stderr and pass through input:

```jq
. | debug | . + 1
```

**Behavior**:
- Prints input to stderr with "DEBUG: " prefix
- Passes input unchanged to output
- Useful for debugging filter pipelines

---

## 7. Modules and Imports

### import and include
Load definitions from files:

```jq
import "module" as mod;         # Load module, prefix all defs with mod::
include "module";               # Load module, import all defs without prefix
import "foo/bar" as bar;        # Hierarchical module loading
```

**Search path**:
- Modules searched in: current directory, ~/.jq, /usr/local/lib/jq

### Module Definition
A module is a jq file with `def` statements:

```jq
# mymodule.jq
def double: . * 2;
def triple: . * 3;
```

Then import and use:

```jq
import "mymodule" as m;
5 | m::double                   # → 10
```

### Qualified Names
With `import ... as m`:
- All imported definitions prefixed with `m::`
- Avoids name collisions

With `include`:
- Definitions imported directly, no prefix
- Higher risk of name collision

---

## 8. limit and first

### limit
Limit number of outputs from a generator:

```jq
limit(3; .[] | . * 2)           # Produces first 3 outputs
```

**Behavior**:
- First argument: number of outputs to produce
- Second argument: generator expression
- Useful for preventing infinite generation

### first
Get first output (or first N):

```jq
first(.[] | select(. > 5))      # First element > 5
first(5; .[])                   # First 5 elements
```

**Behavior**:
- `first(expr)`: first output of expr
- `first(n; expr)`: first n outputs

---

## 9. until and limit

### recurse with depth limit
```jq
recurse(. * 2; . < 1000)        # Recurse with generator condition
limit(5; recurse(. * 2))        # Limit recursion depth
```

---

## 10. Variable Capture in Nested Definitions

Variables in outer scope are captured when inner function is defined:

```jq
def make_adder($n): def add: . + $n; add;
5 | make_adder(3)               # → 8 ($n is captured as 3)
```

The variable `$n` is bound at the time `make_adder` is called, not when `add` is called.

---

## 11. Known Advanced Feature Behaviors

### TCO Only for No-Arg Functions
Tail-call optimization applies **only** to functions with no parameters:

```jq
def f: if . <= 0 then 0 else (. - 1 | f) end;  # TCO applied
def g($n): if $n <= 0 then 0 else ($n - 1 | g($n - 1)) end;  # No TCO
```

### Recursive Definitions with Arguments
Function definitions with arguments capture their parameters:

```jq
def fib($n): if $n <= 1 then $n else fib($n - 1) + fib($n - 2) end;
```

This creates exponential branching without memoization (inefficient).

### Module Import Caching
Once imported, a module is cached; re-importing doesn't re-execute:

```jq
import "module" as m;
import "module" as m2;           # Same module, cached
```

---

## 12. SQL-Style Operators (if available)

Some jq builds support SQL-like operators:

```jq
group_by(.type) | map({type: .[0].type, count: length})
```

Not part of standard jq but useful for data manipulation.

---

## Sources

- jq Manual v1.8: https://jqlang.org/manual/
- Advanced Topics Wiki: https://github.com/jqlang/jq/wiki/Advanced-Topics
- builtin.jq: https://github.com/jqlang/jq/blob/master/src/builtin.jq
