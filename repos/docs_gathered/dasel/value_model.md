# Value model

`model.Value` is the unified in-memory representation that every reader produces and every writer consumes. The package comment captures the intent simply: a `Value` is a wrapper around `reflect.Value` with extra logic for easier use. By routing everything through one type, the execution engine can stay format-agnostic while still preserving the structural detail each encoding needs.

## Core type

```go
type Value struct {
    value    reflect.Value
    Metadata map[string]any
    setFn    func(*Value) error
}
```

- `value` is the reflect handle on the underlying Go value.
- `Metadata` is an open key/value bag used by readers and writers to attach format-specific information (for example, a YAML node pointer, an XML element, or markers like "spread" or "branch").
- `setFn` is an optional callback that lets parent containers receive in-place writes; when present, calling `Set` on a value propagates the change back into the structure that produced it.

## Type tags

`model.Type` is a string enum that classifies a value at runtime:

```go
const (
    TypeString  Type = "string"
    TypeInt     Type = "int"
    TypeFloat   Type = "float"
    TypeBool    Type = "bool"
    TypeMap     Type = "map"
    TypeSlice   Type = "array"
    TypeUnknown Type = "unknown"
    TypeNull    Type = "null"
)
```

The companion files split the surface into focused groups: `value_literal.go` covers the scalar accessors (`StringValue`, `IntValue`, `FloatValue`, `BoolValue`), `value_map.go` and `value_slice.go` cover container operations (`RangeMap`, `RangeSlice`, `Append`, `SliceLen`, `MapKey`), `value_math.go` covers arithmetic, `value_comparison.go` covers `Equal`, `NotEqual`, `LessThan`, `Compare`, `value_set.go` covers in-place writes, and `value_metadata.go` covers the markers used by branch and spread.

## Construction and conversion

The public constructors are `NewValue(any)`, `NewNullValue`, `NewStringValue`, `NewSliceValue`, `NewNestedValue`. `NewValue` allocates a fresh `reflect.Value` of the appropriate kind, copying the input through an addressable pointer so subsequent `Set` calls can mutate it. `NewNestedValue` wraps an existing `*Value` so it can be embedded inside another structure without losing identity.

`GoValue()` converts back out of the model into native Go types — strings, ints, floats, bools, `map[string]any`, `[]any`, or `nil` for `TypeNull`. This is the bridge used by the library's `Select` function so callers get plain Go data structures rather than `*model.Value` handles.

## Comparison semantics

`value_comparison.go` defines `Compare`, `Equal`, and `NotEqual`. Integer and floating-point values cross-compare by widening: comparing `int` to `float` promotes the int to float before testing equality. Otherwise, mismatched types return `ErrIncompatibleTypes{A, B}` so the execution engine can surface a precise error to the caller. Equality on maps and slices delegates to per-type helpers (`EqualTypeValue`).

## Error vocabulary

`model/error.go` defines the package's typed errors: `MapKeyNotFound{Key}`, `SliceIndexOutOfRange{Index}`, `ErrIncompatibleTypes{A, B}`, `ErrUnexpectedType{Expected, Actual}`, and `ErrUnexpectedTypes{Expected, Actual}`. These are returned as concrete types (not strings) so callers — particularly the recursive-descent and search executors — can use `errors.As` to ignore expected mismatches when walking heterogeneous trees.

## Ordered maps

`model/orderedmap/` provides an ordered-map implementation used by readers that need to preserve key order on round-trips (notably JSON and YAML). Iteration follows insertion order, which keeps round-trip output stable.
