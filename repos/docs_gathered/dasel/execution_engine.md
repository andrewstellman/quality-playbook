# Execution engine

The `execution` package walks a parsed selector AST against an in-memory `*model.Value`. Its public entry point combines parsing and evaluation in one call:

```go
func ExecuteSelector(ctx context.Context, selectorStr string, value *model.Value, opts *Options) (*model.Value, error)
```

Callers that already have an AST in hand can skip parsing with `ExecuteAST(ctx, expr, value, options)`.

## Options

`execution.Options` is the shared evaluation context:

```go
type Options struct {
    Funcs    FuncCollection
    Vars     map[string]*model.Value
    Unstable bool
}
```

Options are built with `NewOptions` plus zero or more `ExecuteOptionFn` mutators. The provided helpers are `WithFuncs` (override the function table), `WithVariable(name, value)` (register a named value reachable through `$name` in selectors), `WithUnstable` and `WithoutUnstable` (toggle access to expression kinds tagged unstable). When unset, `NewOptions` populates `Funcs` with `DefaultFuncCollection` and `Vars` with an empty map.

## Dispatch

`exprExecutor` is the central switch from AST node kind to an executor closure (`expressionExecutor`). Each concrete expression in `selector/ast` has a corresponding `execute_*.go` file:

- Literal nodes (`NumberIntExpr`, `NumberFloatExpr`, `StringExpr`, `BoolExpr`, `NullExpr`) — `execute_literal.go`.
- Arithmetic and comparison (`BinaryExpr`, `UnaryExpr`) — `execute_binary.go`, `execute_unary.go`.
- Traversal (`PropertyExpr`, `IndexExpr`, `RangeExpr`, `SpreadExpr`, `ArrayExpr`, `ChainedExpr`) — `execute.go`, `execute_array.go`, `execute_spread.go`.
- Higher-order (`MapExpr`, `EachExpr`, `FilterExpr`, `SearchExpr`, `SortByExpr`, `RecursiveDescentExpr`) — corresponding `execute_*.go` files.
- Control flow (`ConditionalExpr`, `BranchExpr`) — `execute_conditional.go`, `execute_branch.go`.
- Construction (`ObjectExpr`) — `execute_object.go`.
- Assignment — `execute_assign.go`.

Before dispatch, `exprExecutor` checks whether the node's Go type appears in `unstableAstTypes` (currently just `ast.BranchExpr`). If it does and `Unstable` is not set on options, evaluation refuses with a message directing the user to `--unstable`.

## Context threading

`execution/context.go` defines a small trio of helpers (`WithExecutorID`, `ExecutorPath`, `ExecutorDepth`) that thread an identifier, slash-separated path, and recursion depth through the standard library `context.Context`. Every executor that recurses into another expression calls `WithExecutorID(ctx, "...")` so deeply nested evaluations carry meaningful diagnostic state.

`ExecuteAST` also has a branch-aware fast path: if the incoming value is marked as a branch (a slice carrying special metadata; see the value model docs), the same executor is applied to every element and the results are reassembled into a new branch-marked slice. This is what makes spread (`...`) and search (`search(...)`) compose with everything downstream — every downstream operator transparently runs over each branch element.

## Built-in functions

`execution/func.go` defines `Func`, `FuncCollection`, and the validation helpers `ValidateArgsExactly`, `ValidateArgsMin`, `ValidateArgsMax`, `ValidateArgsMinMax`. The `DefaultFuncCollection` registers a standard library of built-ins: `len`, `add`, `toString`, `toInt`, `toFloat`, `merge`, `reverse`, `typeOf`, `max`, `min`, `ignore`, `base64Encode`, `base64Decode`, `parse`, `readFile`, `has`, `get`, `contains`, `sum`, `join`, `replace`. Each lives in its own `func_*.go`, with paired `func_*_test.go` for examples. Callers building a custom embedding use `WithFuncs` to swap in their own collection.
