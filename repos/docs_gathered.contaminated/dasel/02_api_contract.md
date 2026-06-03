# dasel — API Contract: Reader/Writer Pipeline and UnmarshalYAML

## Sources

- https://github.com/TomWright/dasel/blob/master/parsing/reader.go
- https://github.com/TomWright/dasel/blob/master/parsing/writer.go
- https://github.com/TomWright/dasel/blob/master/parsing/format.go
- https://github.com/TomWright/dasel/blob/master/parsing/yaml/yaml.go
- https://github.com/TomWright/dasel/blob/master/parsing/yaml/yaml_reader.go
- https://github.com/TomWright/dasel/blob/master/parsing/json/json_reader.go
- https://github.com/TomWright/dasel/blob/master/parsing/xml/reader.go
- https://pkg.go.dev/go.yaml.in/yaml/v4 (UnmarshalYAML contract)

## The four-layer pipeline

```
Caller ──▶ Format (string-typed)
            │
            ▼
         Format.NewReader(opts)  ──▶  parsing.Reader  (interface)
                                          │
                                          ▼
                                       Read([]byte) (*model.Value, error)
                                          │
                                          ▼
                                     format-specific reader
                                     (e.g. *yamlReader)
```

The same shape mirrors for writes: `Format.NewWriter(opts) -> parsing.Writer -> Write(*model.Value) ([]byte, error)`.

## Type definitions

### `parsing.Format`

`parsing/format.go`:

```go
// Format represents a file format.
type Format string

func (f Format) NewReader(options ReaderOptions) (Reader, error) {
    fn, ok := readers[f]
    if !ok {
        return nil, fmt.Errorf("unsupported reader file format: %s", f)
    }
    return fn(options)
}
```

Format is a string type. Registered names: `"yaml"`, `"json"`, `"xml"`, `"toml"`, `"csv"`, `"hcl"`, `"ini"`, `"kdl"`, `"d"`. Lookup is via package-level maps `readers` (for `Reader`) and `writers` (for `Writer`), populated by each format subpackage's `init()`.

### `parsing.Reader` interface

`parsing/reader.go`:

```go
type ReaderOptions struct {
    Ext map[string]string
}

type Reader interface {
    Read([]byte) (*model.Value, error)
}

type NewReaderFn func(options ReaderOptions) (Reader, error)

func RegisterReader(format Format, fn NewReaderFn) {
    readers[format] = fn
}
```

`ReaderOptions.Ext` is an extensibility bag — string-keyed string-valued map of format-specific switches (the XML reader, for example, checks `options.Ext["xml-mode"] == "structured"`).

### `parsing.Writer` interface and document separators

`parsing/writer.go`:

```go
type WriterOptions struct {
    Compact bool
    Indent  string
    Ext     map[string]string
}

type Writer interface {
    Write(*model.Value) ([]byte, error)
}

// DocumentSeparator is an optional interface a Writer can implement
type DocumentSeparator interface {
    Separator() []byte
}

// MultiDocumentWriter wraps a Writer to emit multi-doc output
func MultiDocumentWriter(w Writer) Writer { ... }
```

`Format.NewWriter` automatically wraps every Writer in `MultiDocumentWriter` so that `*model.Value` branch values produce multi-document output (used by YAML and other multi-doc formats).

## The YAML reader contract — the locus of [REDACTED]

### Registration (`parsing/yaml/yaml.go`)

```go
const YAML parsing.Format = "yaml"

func init() {
    parsing.RegisterReader(YAML, newYAMLReader)
    parsing.RegisterWriter(YAML, newYAMLWriter)
}

type yamlValue struct {
    node              *yaml.Node
    value             *model.Value
    compact           bool
    expansionDepth    int
    [REDACTED] int
    expansionBudget   *int
}
```

The `yamlValue` struct is the per-node bookkeeping for recursive unmarshalling. The bottom three fields (`expansionDepth`, `[REDACTED]`, `expansionBudget *int`) were **added in v3.3.2** as the CVE fix; they did not exist in the vulnerable parent commit `0dd6132e0c58edbd9b1a5f7ffd00dfab1e6085ad`.

### `(*yamlReader).Read` — post-fix

```go
const [REDACTED] = 32
const [REDACTED] = 1000

var ErrYamlExpansionDepthExceeded   = errors.New("yaml expansion depth exceeded")
var ErrYamlExpansionBudgetExceeded  = errors.New("yaml expansion budget exceeded")

func (j *yamlReader) Read(data []byte) (*model.Value, error) {
    d := yaml.NewDecoder(bytes.NewReader(data))
    res := make([]*yamlValue, 0)
    for {
        expansionBudget := j.[REDACTED]
        unmarshalled := &yamlValue{
            expansionDepth:    0,
            [REDACTED]: j.[REDACTED],
            expansionBudget:   &expansionBudget,
        }
        if err := d.Decode(&unmarshalled); err != nil {
            if err == io.EOF { break }
            return nil, err
        }
        // ... append, fall through to single/multi-doc handling
    }
}
```

The critical contract: **the budget is reset per document**. A multi-document YAML stream (separated by `---`) gets a fresh `expansionBudget := j.[REDACTED]` for each `Decode` call. There is also a regression test for this exact behaviour (`yaml expansion budget resets per document`, `yaml_test.go:677`).

### `(*yamlValue).UnmarshalYAML` — post-fix

The function is invoked by `go.yaml.in/yaml/v4`'s decoder whenever the destination type implements `Unmarshaler`. The contract from the upstream library:

> `Unmarshaler` is implemented by types that customise their YAML unmarshalling. Their `UnmarshalYAML` method is invoked with a `*yaml.Node` representing the YAML value being decoded. The node tree is shared with the decoder; alias nodes are pointers to their anchor nodes.

The post-fix dasel implementation enforces both bounds on entry:

```go
func (yv *yamlValue) UnmarshalYAML(value *yaml.Node) error {
    yv.node = value
    if yv.expansionDepth > yv.[REDACTED] {
        return ErrYamlExpansionDepthExceeded
    }
    switch value.Kind {
    case yaml.ScalarNode:    /* leaf, no recursion */
    case yaml.DocumentNode:  /* leaf */
    case yaml.SequenceNode:  /* recurse on each Content[i] with same depth */
    case yaml.MappingNode:   /* recurse on key/value pairs with same depth */
    case yaml.AliasNode:
        if yv.expansionBudget != nil {
            *yv.expansionBudget = *yv.expansionBudget - 1
            if *yv.expansionBudget < 0 {
                return ErrYamlExpansionBudgetExceeded
            }
        }
        newVal := &yamlValue{
            expansionDepth:    yv.expansionDepth + 1,  // ← depth only bumps on alias
            [REDACTED]: yv.[REDACTED],
            expansionBudget:   yv.expansionBudget,     // ← budget shared across all recursion
        }
        if err := newVal.UnmarshalYAML(value.Alias); err != nil {
            return err
        }
        yv.value = newVal.value
        yv.value.SetMetadataValue("yaml-alias", value.Value)
    }
    return nil
}
```

Two distinct mechanisms, intentionally separate:

1. **Depth counter (`expansionDepth`)** — increments only on `AliasNode`. Caps the maximum *chain length* of alias dereferences from any node back to a non-alias. Cap: 32.
2. **Budget counter (`expansionBudget *int`)** — pointer-shared across the whole document traversal, decremented on every alias resolution. Caps the *total number* of alias resolutions across the whole document. Cap: 1000.

The pointer-sharing is essential: a single document with many anchors but each short chain (like the PoC's nine-level pyramid) would exhaust budget long before exhausting depth. Conversely, a deep-but-linear alias chain would exhaust depth before exhausting budget. Both bounds together cover both attack shapes.

### `(*yamlValue).UnmarshalYAML` — pre-fix (vulnerable)

Same function in commit `0dd6132e0c58edbd9b1a5f7ffd00dfab1e6085ad` (and v3.3.1, v3.0.0):

```go
case yaml.AliasNode:
    newVal := &yamlValue{}
    if err := newVal.UnmarshalYAML(value.Alias); err != nil {
        return err
    }
    yv.value = newVal.value
    yv.value.SetMetadataValue("yaml-alias", value.Value)
```

No counters, no bounds, unconditional recursion. The empty `&yamlValue{}` initialiser is the diagnostic — no field on the struct existed yet to hold a depth or budget. A reviewer looking at this codepath in isolation could miss the issue because the recursion is structurally identical to the safe `SequenceNode` / `MappingNode` recursion **above the alias case** — but alias recursion is fundamentally different: a single alias node can expand to many anchors recursively, while a sequence/mapping node has fixed Content slice length determined by the parser.

## The JSON and XML reader contracts (for comparison)

### JSON

`parsing/json/json_reader.go` uses `github.com/goccy/go-json`. `decodeObject` and `decodeArray` recurse on `jsonOpenObject` and `jsonOpenArray` tokens. No explicit depth, size, or token-count cap in dasel. Numeric tokens go through `UseNumber()` for precision preservation.

### XML

`parsing/xml/reader.go` uses `encoding/xml` with `decoder.Strict = true`. Defends with three named constants:

```go
const (
    maxCommentLength = 10_000     // 10KB per comment
    maxTotalComments = 1_000      // per-document
    maxXMLSize       = 10_000_000 // 10MB input
)
```

Size is checked at the start of `Read`; comment count is threaded as `totalComments *int` through `parseElement`, similar to the post-fix YAML budget threading.

## Multi-document semantics

YAML's `Read` decodes in a loop until `io.EOF`, collecting `[]*yamlValue`. If only one document, returns its value directly; otherwise returns a `model.NewSliceValue()` marked as a branch via `slice.MarkAsBranch()`. JSON's `Read` mirrors this for NDJSON input. The branch marker on the writer side triggers `MultiDocumentWriter` to emit document separators.

## What the contract obliges every Reader to do

Distilled across all three (YAML, JSON, XML):

1. Accept `[]byte`. Return `(*model.Value, error)` or `(nil, error)`.
2. Never panic on adversarial input — convert all panics into errors.
3. Bound the parser against the format's resource-exhaustion vector.
4. Support multi-document input where the format permits, returning a branch-marked slice.
5. Respect `ReaderOptions.Ext` for format-specific switches.

## Invariants

- **V-API-1**: `Reader.Read` MUST return `(value, nil)` or `(nil, error)` — never panic.
- **V-API-2**: Each format Reader is responsible for its own bounds; the upstream library is NOT assumed to enforce them on the custom-unmarshal path.
- **V-API-3**: For YAML specifically, both `expansionDepth` (per-chain) and `expansionBudget` (per-document, shared via pointer) MUST be threaded through every recursive `yamlValue` so that the AliasNode branch can check and decrement them.
- **V-API-4**: For YAML specifically, the `expansionBudget` MUST be reset to `[REDACTED]` at the start of each new document in a multi-document stream.
- **V-API-5**: For any reader, a resource-exhaustion error MUST be a distinguishable sentinel (e.g. `ErrYamlExpansionDepthExceeded`) so callers can branch on it.
