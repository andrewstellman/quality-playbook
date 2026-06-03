# Library API

Dasel is usable from Go programs as well as from the command line. The public top-level API lives in `api.go` and is intentionally small — three functions and an option type — so that callers can drop the library into their own pipelines without having to learn the internal package layout.

## Top-level functions

```go
func Query(ctx context.Context, data any, selector string, opts ...execution.ExecuteOptionFn) ([]*model.Value, int, error)
func Select(ctx context.Context, data any, selector string, opts ...execution.ExecuteOptionFn) (any, int, error)
func Modify(ctx context.Context, data any, selector string, newValue any, opts ...execution.ExecuteOptionFn) (int, error)
```

- `Query` wraps the input with `model.NewValue`, executes the selector through `execution.ExecuteSelector`, and returns one or more `*model.Value` results along with their count. If the result is a branch or spread, each element is unfolded into its own slot in the returned slice; otherwise the result is a one-element slice.
- `Select` runs `Query` and then converts each result to a native Go value via `(*model.Value).GoValue()`. Map ordering is not guaranteed by `Select`, as the docstring notes.
- `Modify` runs `Query` and calls `Set` on every returned value with the new value the caller supplies. The input must be a pointer to a mutable structure for the change to be observable from the caller's side.

All three accept a variadic list of `execution.ExecuteOptionFn`. The available options are documented in the execution-engine reference; in practice the most common are `WithVariable` (inject named values reachable as `$name`), `WithFuncs` (swap or extend the built-in function table), and `WithUnstable` (enable expression kinds tagged unstable, currently `branch`).

## Idiomatic usage

A typical embedded use case looks like:

```go
ctx := context.Background()
data := map[string]any{"foo": map[string]any{"bar": "baz"}}
result, count, err := dasel.Select(ctx, data, "foo.bar")
```

Modification mirrors the same pattern but takes a pointer:

```go
data := map[string]any{"foo": map[string]any{"bar": "baz"}}
n, err := dasel.Modify(ctx, &data, "foo.bar", "bong")
```

For programs that already have a parsed AST, or that want to manage parsing separately from execution, the lower-level entry points are `selector.Parse(selectorStr)` (returns an `ast.Expr`) and `execution.ExecuteAST(ctx, expr, value, options)` (evaluates a pre-parsed expression).

## Working with the value model directly

Callers that want to stay inside the model can skip `GoValue()` and walk `*model.Value` directly. The relevant operations are listed in the value-model reference: `Type()`, `StringValue()`, `IntValue()`, `FloatValue()`, `BoolValue()`, `RangeMap(fn)`, `RangeSlice(fn)`, `Equal(other)`, `Compare(other)`, and `Set(newValue)`. This is the same surface the execution engine itself uses, so anything that can be expressed in a selector can also be expressed as a sequence of model calls.

## Imports and module layout

The module path at this version is `github.com/tomwright/dasel/v3`. Subpackages a library consumer typically imports are:

- `github.com/tomwright/dasel/v3` — the `Query`, `Select`, `Modify` surface.
- `github.com/tomwright/dasel/v3/execution` — `Options`, `ExecuteOptionFn`, `FuncCollection`, `WithVariable`, `WithFuncs`, `WithUnstable`.
- `github.com/tomwright/dasel/v3/model` — `Value`, `Type`, the typed error families.
- `github.com/tomwright/dasel/v3/parsing` and its subpackages — only needed when registering custom readers/writers or invoking format-aware parsing directly.

## Versioning and build

The minimum Go version declared by `go.mod` at this version is `go 1.25`. The `Dockerfile` shows the canonical build command: `go build -o /dasel -ldflags="-w -s -X 'github.com/tomwright/dasel/v3/internal.Version=${RELEASE_VERSION}'" ./cmd/dasel`. The same `-X` ldflag pattern is used to inject build version information into a library consumer's own binary if they want to surface it.
