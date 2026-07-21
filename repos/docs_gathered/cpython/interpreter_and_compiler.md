# CPython Interpreter and Compiler Pipeline

## Overview

CPython transforms Python source code into executable bytecode through a well-defined pipeline of stages, each with clear data interfaces. Understanding this pipeline is essential for contributors working on the grammar, compiler optimizations, bytecode format, or the evaluation loop itself.

## The Compilation Pipeline

Source code travels through five stages before execution:

```
Source text
    ↓  Lexer / Tokenizer (Parser/lexer/, Parser/tokenizer/)
Token stream
    ↓  PEG Parser (Parser/parser.c)
Abstract Syntax Tree (AST)
    ↓  Compiler (Python/compile.c)
Instruction sequence
    ↓  Flow graph optimizer (Python/flowgraph.c)
Optimized control flow graph
    ↓  Assembler (Python/assemble.c)
Code object (PyCodeObject)
```

## Stage 1: Lexer and Tokenizer

The lexer lives in `Parser/lexer/` and `Parser/tokenizer/`. It reads source text (UTF-8 bytes or a string) and produces a stream of tokens. Token types are defined in `Grammar/Tokens` and exposed to Python via the `token` module. The `tokenize` module in the standard library (`Lib/tokenize.py`) provides a pure-Python interface to the same logic, useful for source analysis tools.

## Stage 2: PEG Parser

`Parser/parser.c` is generated from `Grammar/python.gram` by the PEG generator (`Tools/peg_generator/`). Python's PEG parser is unusual in that it operates on a token stream rather than a character stream. Key properties:
- Unlimited lookahead (memoization of results avoids exponential backtracking).
- Grammar is expressed in Extended BNF with PEG extensions (ordered choice `|`, `&` lookahead, `!` negative lookahead, `~` commit).
- The generated parser is table-driven; `make regen-pegen` regenerates `Parser/parser.c` from the grammar.

`Parser/Python.asdl` (Zephyr ASDL format) specifies the AST node types. `Parser/asdl_c.py` generates the C struct definitions (`Python/Python-ast.c`, `Include/cpython/Python-ast.h`) and the Python `ast` module bindings. Each grammar rule maps to one or more ASDL productions.

## Stage 3: The AST

The AST is a tree of C structs (e.g., `stmt_ty`, `expr_ty`, `mod_ty`). The `ast` module (`Lib/ast.py`) provides:
- `ast.parse(source, filename, mode)` — returns the root AST node.
- `ast.dump(node, indent)` — pretty-prints the tree.
- `ast.walk(node)` — iterator over all nodes.
- `ast.NodeVisitor` and `ast.NodeTransformer` — visitor/transformer base classes for tools that analyze or rewrite Python code.
- `ast.unparse(node)` — reconstructs a source string from an AST (implemented in `Lib/_ast_unparse.py`).

The `compile` built-in and `py_compile` both call into the compiler from this stage.

## Stage 4: Compiler (`Python/compile.c`)

The compiler performs a recursive descent over the AST, emitting an **instruction sequence** — a list of pseudo-instructions (including `SETUP_FINALLY`/`POP_BLOCK` markers for exception handling scope) and metadata about local variables, closures, and annotations.

Key responsibilities:
- **Symbol table analysis** (`Python/symtable.c`): classifies each name as local, cell (closed over), free (captured from enclosing scope), global, or builtin. The `symtable` module exposes this analysis to Python.
- **Scope tracking**: function bodies, class bodies, comprehensions, and lambdas each create new scopes. The compiler maintains a stack of `compiler_unit` objects.
- **Constant folding**: constant expressions are evaluated at compile time when safe to do so.
- **Annotation handling** (`Python/ast_preprocess.c`): PEP 563 / PEP 649 annotation semantics are applied.

## Stage 5: Control Flow Graph and Optimizer (`Python/flowgraph.c`)

The instruction sequence is converted into a Control Flow Graph (CFG): a set of basic blocks connected by jumps. The flow graph optimizer performs:
- Dead code elimination.
- Jump threading (collapsing chains of jumps).
- Constant propagation within basic blocks.
- Removal of `NOP` instructions.
- Exception table construction from `SETUP_FINALLY`/`POP_BLOCK` pairs.

## Stage 6: Assembler (`Python/assemble.c`)

The assembler converts the optimized CFG back to a flat bytecode array and constructs a `PyCodeObject`. It:
- Assigns final instruction offsets and resolves jump targets.
- Allocates the `co_varnames`, `co_names`, `co_consts`, `co_freevars`, `co_cellvars` tuples.
- Builds the exception table (`co_exceptiontable`).
- Builds the line number table (`co_linetable`) mapping instruction offsets to source lines.
- Computes `co_stacksize` (the maximum depth of the evaluation stack at any point).

## The Code Object (`PyCodeObject`)

`PyCodeObject` (in `Objects/codeobject.c`) is the static descriptor of a compiled function or module. Key fields:
- `co_code` / `co_code_adaptive` — bytecode instruction array (16-bit code units).
- `co_consts` — tuple of constants referenced by `LOAD_CONST`.
- `co_names` — tuple of global/attribute names.
- `co_varnames` — tuple of local variable names.
- `co_freevars` / `co_cellvars` — closure variable names.
- `co_exceptiontable` — exception handler range table for zero-cost exception handling.
- `co_linetable` — compressed mapping from instruction offsets to source line numbers.
- `co_qualname` — qualified name for display in tracebacks.
- `co_flags` — bit flags (`CO_VARARGS`, `CO_VARKEYWORDS`, `CO_GENERATOR`, `CO_COROUTINE`, etc.).

## The Bytecode Format

Bytecode is stored as an array of 16-bit code units (`_Py_CODEUNIT`), each holding an 8-bit opcode and an 8-bit argument. Arguments larger than 255 are encoded with `EXTENDED_ARG` prefixes (up to three, allowing 32-bit arguments). The full opcode set is defined in `Python/bytecodes.c` (the DSL source) and generated into `Python/generated_cases.c.h`.

## The Adaptive Interpreter (Tier 1)

`Python/ceval.c` contains `_PyEval_EvalFrameDefault()`, the main evaluation loop. It decodes each code unit, dispatches on the opcode through a switch statement (or computed goto on supported compilers), and executes the corresponding case.

**Specialization** (PEP 659): certain opcodes (like `LOAD_ATTR`, `BINARY_OP`, `CALL`) are "adaptive" — they start as generic forms and replace themselves with specialized variants after observing a few executions. For example, `LOAD_ATTR` may specialize to `LOAD_ATTR_INSTANCE_VALUE` if it always sees the same object layout. Specialization data is stored in **inline cache entries** — extra code units that follow the opcode in the bytecode stream. The specialization machinery is in `Python/specialize.c`.

## The Tier 2 Optimizer and JIT

When a backward jump (`JUMP_BACKWARD`) becomes "hot" (its counter exceeds a threshold), `_PyOptimizer_Optimize()` is called. It:
1. Traces a likely execution path (superblock) starting from the jump, projecting control flow using runtime type and value information from Tier 1.
2. Translates each bytecode instruction into a sequence of micro-ops (uops) from the uop instruction set defined in `Python/bytecodes.c`.
3. Runs the micro-op optimizer (`Python/optimizer_analysis.c`) for type propagation and constant folding across the trace.
4. Produces an `_PyExecutorObject` that either runs in the uop interpreter (`Python/ceval.c` Tier 2 dispatch) or is compiled to machine code by the JIT.

The `JUMP_BACKWARD` instruction is replaced by `ENTER_EXECUTOR`, which directly invokes the executor. Executors form a graph: each exit point of one executor may connect to another, covering the hot regions of the program with optimized code.

The JIT uses a **copy-and-patch** compilation strategy: each uop has a machine-code template (generated by `Tools/jit/`) with placeholder slots that are filled in at JIT-compile time with runtime values like object addresses and type tags.

## Exception Handling

CPython uses zero-cost exception handling (documented in `InternalDocs/exception_handling.md`). In the common path (no exception raised), exception handling adds zero overhead: the `SETUP_FINALLY` and `POP_BLOCK` pseudo-instructions generate no bytecode; instead they populate the exception table. When an exception is raised, `get_exception_handler()` performs a binary search in the exception table to find the handler for the current instruction offset, then transfers control to it. If no handler is found in the current frame, the exception propagates to the caller by returning `NULL` from `_PyEval_EvalFrameDefault()`.

## Frames and the Call Stack

Each Python function call creates a `_PyInterpreterFrame` (defined in `Include/internal/pycore_interpframe_structs.h`) containing:
- The `PyCodeObject` being executed.
- Pointers to globals, builtins, and the locals dict.
- The instruction pointer (`instr_ptr`).
- The evaluation stack (`localsplus` array, which holds both fast locals and the stack).
- A link to the previous frame (`previous`).

Most frames are allocated on a per-thread stack (`_PyThreadState_PushFrame`) for locality and low overhead. Generator and coroutine frames are embedded in their respective objects and live on the heap. When Python code inspects a frame (via `sys._getframe()` or traceback construction), a heap-allocated `PyFrameObject` is created as a proxy; if the underlying `_PyInterpreterFrame` is later deallocated (the call returns), the `PyFrameObject` takes ownership of a copy.
