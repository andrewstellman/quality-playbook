# Parsing and formats

The `parsing` package is the pluggable boundary between byte-level encodings and the unified value model. Every format implements two small interfaces and registers itself with the package-level maps during `init`. The CLI's `main` package blank-imports each format subpackage so registration happens before any command runs.

## The Format registry

`parsing/format.go` defines a `Format` string type and the registry helpers:

```go
type Format string
func (f Format) NewReader(options ReaderOptions) (Reader, error)
func (f Format) NewWriter(options WriterOptions) (Writer, error)
func (f Format) String() string

func RegisteredReaders() []Format
func RegisteredWriters() []Format
```

The maps `readers` and `writers` live in `parsing/reader.go` and `parsing/writer.go` respectively. Each format calls `RegisterReader(<format>, newXReader)` and `RegisterWriter(<format>, newXWriter)` from its `init()`.

## Reader / Writer interfaces

```go
type Reader interface { Read([]byte) (*model.Value, error) }
type Writer interface { Write(*model.Value) ([]byte, error) }

type ReaderOptions struct { Ext map[string]string }
type WriterOptions struct {
    Compact bool
    Indent  string
    Ext     map[string]string
}
```

The `Ext` maps carry format-specific tweaks delivered through CLI flags such as `--rw-flag csv-delimiter=;` or `--read-flag xml-mode=structured`. `DefaultReaderOptions` and `DefaultWriterOptions` return sensible starting points (two-space indent, non-compact output, empty extension map).

## Multi-document writing

`MultiDocumentWriter` wraps any registered writer so that values carrying the branch or spread marker are serialized as multiple documents joined by a per-format separator. A writer that wants something other than a single newline implements:

```go
type DocumentSeparator interface { Separator() []byte }
```

YAML, for example, uses `---` between documents. The wrapping happens automatically in `Format.NewWriter`, so every writer registered through the registry transparently gains multi-document output.

## Supported formats

- **`json`** (`parsing/json/`) — uses `github.com/goccy/go-json`. The reader walks the token stream (`UseNumber()` is enabled so numeric precision is preserved) and dispatches on the first token to `decodeObject`, `decodeArray`, or `decodeToken`. The writer mirrors the structure back out.
- **`yaml`** (`parsing/yaml/`) — uses `go.yaml.in/yaml/v4`. The reader decodes documents in a loop; multi-document files produce a slice marked as a branch.
- **`toml`** (`parsing/toml/`) — uses `github.com/pelletier/go-toml/v2`. Read and write live in `toml_reader.go` / `toml_writer.go`.
- **`xml`** (`parsing/xml/`) — internal types `xmlElement`, `xmlAttr`, `xmlProcessingInstruction`, `xmlComment` model element trees including attributes, PIs, and comments; the reader and writer convert between this representation and the value model.
- **`csv`** (`parsing/csv/`) — rows of records, with a configurable delimiter (`csv-delimiter` extension flag) and per-cell coercion through `valueFromString` / `valueToString`.
- **`hcl`** (`parsing/hcl/`) — uses `github.com/hashicorp/hcl/v2` and `github.com/zclconf/go-cty` to map HCL bodies into the model.
- **`ini`** (`parsing/ini/`) — uses `gopkg.in/ini.v1`.
- **`d` (Dasel)** (`parsing/d/`) — a read-only "format" that evaluates its input as a Dasel expression starting from a null value. It is registered as `"dasel"` and used by the CLI's `--var` flag so a variable definition like `--var foo=dasel:1+1` evaluates the right-hand side through the selector engine.

## Extending the registry

Adding a new format means writing a `Reader` and `Writer`, exposing a `Format` constant, and calling `parsing.RegisterReader` / `parsing.RegisterWriter` from an `init()`. Importing the new subpackage from `cmd/dasel/main.go` (or a custom binary) is enough to make it discoverable on the command line.
