# jq Architecture — Lexer, Parser, Compiler, Bytecode VM

Extracted from jqlang/jq source code (src/lexer.c, src/parser.y, src/compile.c, src/execute.c) and GitHub wiki documentation.

---

## 1. Overall Pipeline

jq follows a classic compiler architecture with distinct phases:

1. **Lexing** — Input text → tokens (lexer.c using Flex)
2. **Parsing** — Tokens → Abstract Syntax Tree / Block IR (parser.y using Bison)
3. **Compilation** — Block IR → bytecode with binding resolution and optimization (compile.c)
4. **Execution** — Bytecode → JSON results via stack-based VM (execute.c)
5. **Output Formatting** — JSON printing (jv_print.c)

Each phase is cleanly separated, allowing incremental processing of large datasets and efficient memory usage.

---

## 2. Lexer (lexer.c / lexer.l)

The lexer is built with Flex and maintains a state machine for nested structures.

### Token Classes
- **Literals**: Numbers, strings, booleans, null
- **Identifiers**: Function names, variable names (prefixed with `$`)
- **Operators**: `.`, `|`, `,`, `+`, `-`, `*`, `/`, `//`, `==`, `!=`, `<`, `>`, `<=`, `>=`, `and`, `or`, `not`
- **Keywords**: `if`, `then`, `else`, `elif`, `end`, `def`, `try`, `catch`, `reduce`, `foreach`, `as`, `import`, `include`
- **Delimiters**: `(`, `)`, `[`, `]`, `{`, `}`, `;`, `:`
- **Special**: String interpolation markers `\(`, `)`

### String Handling
The lexer recognizes string literals with escape sequences and embedded expressions via `\(...)` syntax. Nested parentheses within `\(...)` must be balanced. The lexer maintains a state stack to handle this nesting correctly.

### Number Token Preservation
When a number token is lexed, the original literal form (as it appeared in source) is preserved separately from its IEEE754 double representation. This allows the compiler to distinguish between a number that was mutated (must output as double) versus unmutated (output in original literal form).

---

## 3. Parser (parser.y / Bison)

The Bison-based parser converts tokens to a Block IR—a doubly-linked list of instructions.

### Grammar Structure
The grammar is expression-centric:
- **Expressions** compose from atomic values, operators, and function applications
- **Pipes** (|) bind left-to-right with lower precedence than most operators
- **Commas** (,) separate multiple expressions and have lowest binding power
- **Parentheses** override precedence

### Block Representation
A "block" is a linked list of instructions (struct inst):
- Each instruction has an opcode, operands, and pointers to next/previous instructions
- Blocks form the intermediate representation between parsing and compilation
- A complete program is a single block tree with all sub-expressions nested as block references

### Precedence (highest to lowest)
1. Primary expressions: `.`, field access, array indexing, literals, parentheses
2. Postfix operators: `.[]`, `?` (optional)
3. Array/object slicing and construction: `[...]`, `{...}`
4. Pipe: `|`
5. Comma: `,`

---

## 4. Compiler (compile.c)

The compiler transforms the Block IR into bytecode while resolving variable bindings and performing optimizations.

### Binding Resolution
The compiler maintains a symbol table for:
- **Value bindings**: Variables (`$foo`, `$bar`), scoped lexically
- **Function definitions**: `def name: body;`, with recursive self-reference allowed

Scoping rule: A symbol can only be referenced if it has been defined "to the left" (earlier in the expression). Functions are the only exception—they can reference themselves for recursion.

### Bytecode Generation
The compiler produces bytecode as arrays of 16-bit values (struct bytecode). This compact representation allows efficient interpretation by the VM.

Key optimizations performed:
- Constant folding for literal expressions
- Dead code elimination
- Tail-call optimization (TCO) for functions with no arguments
- Lazy evaluation of generator expressions (comma operator produces multiple outputs without collecting)

### Instruction Types
Common bytecode instructions include:
- **Load/Store**: `LOAD_CONST`, `LOAD_VAR`, `STORE_VAR`
- **Data access**: `INDEX`, `SLICE`, `ITERATE`
- **Operators**: `ADD`, `SUB`, `MUL`, `DIV`, `EQ`, `LT`, `GT`
- **Control flow**: `JUMP`, `BRANCH`, `CALL`, `RETURN`
- **Generators**: `GENERATOR`, `EMIT`
- **Error handling**: `TRY`, `CATCH`

---

## 5. Value Representation (jv type)

All values in jq are represented as the `jv` type (a tagged union).

### Type Tag
```c
enum jv_kind { JV_NULL, JV_FALSE, JV_TRUE, JV_NUMBER, JV_STRING, JV_ARRAY, JV_OBJECT };
```

### Storage
- **Scalar values** (null, true, false, numbers): 8 bytes (tag + payload)
- **Composite values** (strings, arrays, objects): Reference-counted heap allocations
  - Strings: UTF-8 byte sequences with refcount
  - Arrays: jv array with refcount
  - Objects: Hash table (jv_object) with refcount

### Number Storage
Numbers are stored as IEEE754 double precision internally. However, the original literal form (if unmutated) is preserved as a string for output purposes. This allows `echo '1.0' | jq '.'` to output `1.0` rather than `1`.

---

## 6. Virtual Machine (execute.c)

The VM is a stack-based interpreter that executes bytecode instructions.

### Stack Model
- **Value stack**: Stores jv values during execution
- **Call stack**: Manages function calls and return addresses
- **State stack**: For try-catch, reduce, and foreach constructs

### Execution Model
Each instruction is executed sequentially. Generators (expressions that produce multiple outputs) are implemented via:
- **Frame-based iteration**: When an expression should produce multiple values, the VM creates a frame that iterates through them
- **Lazy evaluation**: Generators don't materialize all values upfront; the VM materializes values on demand

### Error Propagation
Errors (type mismatches, division by zero, etc.) are represented as special error values. Error propagation is explicit: unless caught by `try-catch`, errors halt execution and are output as error objects.

### Generator Protocol
When a builtin function produces multiple outputs (e.g., `.[]` on an array), the VM manages state to emit each output in sequence. This is distinct from collecting outputs into an array with `[...]`.

---

## 7. Tail-Call Optimization

jq implements tail-call optimization (TCO) for functions with no arguments. A function call that appears in tail position (the last operation in the function body) is optimized to reuse the current stack frame rather than creating a new one.

### Limitation
TCO only applies to functions with **zero arguments**. Functions taking arguments cannot be tail-optimized because argument binding requires a new frame.

### Practical Impact
TCO enables efficient recursive functions like `def factorial: if . <= 1 then 1 else . * ((. - 1) | factorial) end;` without stack exhaustion on deep recursion.

---

## 8. Known Compiler/VM Behaviors

### Lazy Generator Semantics
The comma operator (`,`) produces a generator. Operations consuming it (like `map()`, `[...]`) materialize all outputs; direct piping leaves outputs lazy.

```jq
# Produces 3 separate outputs
1, 2, 3

# Collects into array [1,2,3]
[1, 2, 3]

# With map, produces 3 outputs (not an array)
(1, 2, 3) | map(. + 1)  # → 2, 3, 4 (three separate values)
```

### Variable Capture
Variables captured in closures are bound at definition time, not at use time. A variable `$x` defined in an outer scope is captured when referenced in a nested `def`, and its value is frozen at definition.

### Recursion Without TCO
Functions with arguments use standard function call semantics without TCO. Deep recursion will exhaust stack:

```jq
def fib($n): if $n <= 1 then $n else fib($n - 1) + fib($n - 2) end;
```

This function will overflow on large inputs due to lack of TCO.

---

## Sources

- jqlang/jq GitHub: https://github.com/jqlang/jq
- Internals Wiki: https://github.com/jqlang/jq/wiki/Internals:-the-compiler
- Source files: src/lexer.l, src/parser.y, src/compile.c, src/execute.c
