# dasel — Input Handling Across Formats

## Sources

- https://github.com/TomWright/dasel/blob/master/parsing/yaml/yaml_reader.go
- https://github.com/TomWright/dasel/blob/master/parsing/json/json_reader.go
- https://github.com/TomWright/dasel/blob/master/parsing/xml/reader.go
- https://github.com/TomWright/dasel/blob/0dd6132e0c58edbd9b1a5f7ffd00dfab1e6085ad/parsing/yaml/yaml_reader.go (pre-fix)
- https://github.com/TomWright/dasel/security/advisories/GHSA-4fcp-jxh7-23x8
- https://github.com/advisories/GHSA-hp87-p4gw-j4gq (CVE-2022-28948 — go-yaml v3 DoS)
- https://github.com/advisories/GHSA-r88r-gmrh-7j83 (CVE-2021-4235 — go-yaml v2 DoS)
- https://github.com/advisories/GHSA-6q6q-88xp-6f2r (CVE-2022-3064 — go-yaml v2 excessive CPU/memory)
- https://github.com/advisories/GHSA-wxc4-f4m6-wwqv (CVE-2019-11254 — billion laughs via go-yaml in Kubernetes)
- https://pkg.go.dev/go.yaml.in/yaml/v4

## Per-format input-handling characteristics

### YAML — the format with the most attack surface

**Backing library**: `go.yaml.in/yaml/v4` (this is the post-rc release of the canonical Go YAML library; functionally equivalent to `gopkg.in/yaml.v3` and `go-yaml/yaml`). The dasel module pins `v4.0.0-rc.3` per the advisory's test environment.

**Decoding path used**: `yaml.NewDecoder(...).Decode(&yamlValue)` where `yamlValue` implements `Unmarshaler`. This is the **custom-unmarshal path**, which is **fundamentally different** from `yaml.Unmarshal(data, &v)` into a plain Go value.

**Why that distinction matters**:

The advisory text spells it out:

> go-yaml v4 has two decoding paths:
> 1. **`Unmarshal` into Go values**: Tracks alias expansion count and rejects documents with excessive aliasing (`"yaml: document contains excessive aliasing"`).
> 2. **`Decode` into `yaml.Node` / custom `UnmarshalYAML`**: Passes a compact Node tree where alias nodes are pointers to their anchors. No expansion occurs at this level.

On path 1, the library counts alias expansions internally and aborts when the count exceeds an internal cap. On path 2, the library hands you a compact `*yaml.Node` tree where alias nodes are pointer references to their anchors — no expansion has happened yet, and the library cannot count something it isn't doing. The custom unmarshaler is then expected to follow the alias pointers, and is fully responsible for bounding that traversal.

**Anchors and aliases**:

```yaml
a: &a [lol,lol,lol,lol,lol,lol,lol,lol,lol]   # anchor a → 9 strings
b: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a]            # anchor b → 9 references to a → 81 strings on expansion
c: &c [*b,*b,*b,*b,*b,*b,*b,*b,*b]            # 729 strings on expansion
…
i: &i [*h,*h,*h,*h,*h,*h,*h,*h,*h]            # 9^9 = 387,420,489 strings on expansion
```

This is the classic "billion laughs" / "billion anchors" attack from XML, ported to YAML. The pre-fix dasel reader followed `value.Alias` recursively with no bound. The advisory's 342-byte PoC did not complete within 5 seconds and consumed 100% CPU with growing memory.

**Post-fix bounds in dasel**: `maxExpansionDepth = 32`, `maxExpansionBudget = 1000` (see `02_api_contract.md` for the threading mechanism). Two errors: `ErrYamlExpansionDepthExceeded` and `ErrYamlExpansionBudgetExceeded`.

**Other YAML inputs that are bounded by the upstream library** (not dasel's responsibility):

- Maximum scalar length — bounded by the YAML scanner's token limits.
- Maximum recursion depth in the parser's own grammar — bounded by go-yaml internals.

dasel only owns the bounds for what dasel itself does — which is alias-pointer-following inside a custom `UnmarshalYAML`.

### JSON — backing library handles most concerns

**Backing library**: `github.com/goccy/go-json`. This is a high-performance JSON library that's a drop-in for `encoding/json`.

**Decoding path**: `json.NewDecoder(bytes.NewReader(data))` with `decoder.UseNumber()` to preserve full numeric precision. The dasel code then walks the token stream, recursing into `decodeObject` and `decodeArray` for nested containers.

**Recursion**: `decodeObject ↔ decodeArray` recurse on the tokens `jsonOpenObject` and `jsonOpenArray`. There is **no explicit nesting cap** in dasel's code. Risk: a deeply nested JSON `{"x":{"x":{"x":...}}}` could grow the Go stack until the runtime panics with stack overflow, or until the underlying library refuses (the dasel layer does not check).

**Numeric tokens**: routed through `json.Number`, then either `Float64()` (if the string contains `.`) or `Int64()`. Tokens that exceed `int64` range fail through the error path.

**NDJSON**: the JSON reader uses `decoder.More()` in a loop, returning a branch-marked slice for multi-value input — mirroring YAML's multi-document handling.

### XML — most defensively coded format

**Backing library**: `encoding/xml` (Go stdlib). Configured with `decoder.Strict = true`.

**Explicit caps** (from `parsing/xml/reader.go`):

```go
const (
    maxCommentLength = 10_000     // 10KB per comment
    maxTotalComments = 1_000      // per-document
    maxXMLSize       = 10_000_000 // 10MB input
)
```

`maxXMLSize` is checked before decoding starts (`if len(data) > maxXMLSize { return nil, fmt.Errorf(...) }`). The `totalComments` counter is threaded via pointer through the recursive element parser, similar to the post-fix YAML budget pattern.

**XML entity expansion (classic "billion laughs")**: Go's `encoding/xml` does not resolve external entity references and does not perform DTD-entity expansion by default. There is no `decoder.Entity` machinery enabled in dasel's XML reader. This means the XML billion-laughs vector is closed by the stdlib's defaults, and dasel doesn't need to add a defence beyond `maxXMLSize` and `decoder.Strict = true`.

**Two XML modes**: `friendly` (default, infers structure from element/attribute patterns) and `structured` (preserves the verbatim tree). Selected via `ReaderOptions.Ext["xml-mode"]`.

### TOML, CSV, HCL, INI, KDL

Each has its own subpackage and Reader (registered the same way). None are in CVE-2026-33320 scope. Their input-handling characteristics are not audited in this writeup, but the trust-boundary rule from `01_security_model.md` applies: each Reader owns the bounds for its format-specific resource-exhaustion vectors.

## Why the YAML billion-laughs pattern is a recurring issue in Go

This is the third or fourth time a Go YAML consumer has had to add an alias-expansion bound. The published advisories on `gopkg.in/yaml.vN` and library consumers form a clear pattern:

| Advisory | Affected package | Year | Mechanism |
| --- | --- | --- | --- |
| GHSA-wxc4-f4m6-wwqv (CVE-2019-11254) | `gopkg.in/yaml.v2` via Kubernetes | 2019 | Excessive aliasing → memory exhaustion |
| GHSA-r88r-gmrh-7j83 (CVE-2021-4235) | `gopkg.in/yaml.v2` | 2021 | Untrusted YAML → DoS via large input |
| GHSA-6q6q-88xp-6f2r (CVE-2022-3064) | `gopkg.in/yaml.v2` | 2022 | "Parsing malicious or large YAML documents can consume excessive amounts of CPU or memory" |
| GHSA-hp87-p4gw-j4gq (CVE-2022-28948) | `gopkg.in/yaml.v3` | 2022 | Untrusted YAML → DoS |
| GHSA-4fcp-jxh7-23x8 (CVE-2026-33320) | dasel | 2026 | Custom `UnmarshalYAML` bypasses go-yaml v4 internal limit |

The upstream library has progressively tightened its built-in defences against billion-laughs — `yaml.Unmarshal` into Go values now refuses excessive aliasing with the explicit error string `"yaml: document contains excessive aliasing"`. But every time a consumer adopts a custom `UnmarshalYAML`, they reopen the hole, because the library's counters are bypassed.

This is the lesson the dasel CVE crystallises: **the safe-default behaviour of the YAML library is not transitive to custom unmarshalers**. Anyone implementing `UnmarshalYAML(*yaml.Node)` against go-yaml has to think about alias expansion themselves, because the library is no longer doing it for them.

## How dasel's `parse(...)` selector function inherits these bounds

Within a dasel selector, `parse("yaml", someString)` is a function that takes a string from the model and re-parses it as the named format. Implementation-wise, it goes through the same `Format.NewReader(...).Read(...)` path as CLI input and library `Read` calls. Therefore the post-fix YAML bounds apply automatically — there is no separate `parse()` code path that bypasses them.

This is by design: putting the bounds inside the Reader (rather than in a CLI guard) means every entry path inherits them. The "every entry path" set includes:

- CLI: `dasel -f file.yaml '…'` and `cat file | dasel -i yaml '…'`
- Go library: `reader, _ := parsing.Format("yaml").NewReader(opts); reader.Read(bytes)`
- Selector-embedded `parse("yaml", str)` inside a dasel expression
- Any wrapper that calls `Reader.Read` directly

## Input-handling invariants

- **V-INP-1**: Custom `UnmarshalYAML(*yaml.Node)` implementations MUST count alias expansions because the upstream library's counter is not active on the custom-unmarshal path.
- **V-INP-2**: For YAML, both *depth* (per alias-chain) and *budget* (total expansions across the document) MUST be bounded — depth alone allows wide-fan attacks (the PoC pattern), budget alone allows long-chain attacks.
- **V-INP-3**: The YAML expansion budget MUST be reset per document in a multi-document stream so legitimate `---`-separated streams aren't penalised for cumulative alias use.
- **V-INP-4**: Bounds MUST live in the Reader so all input paths (CLI, library, `parse()` in selectors) inherit them.
- **V-INP-5**: For XML, total input size, per-comment length, and total comment count MUST be capped (`maxXMLSize`, `maxCommentLength`, `maxTotalComments` per `parsing/xml/reader.go`).
- **V-INP-6**: For JSON, nesting depth SHOULD be bounded (currently not enforced in dasel; relies on the backing library or runtime stack-overflow protection).
