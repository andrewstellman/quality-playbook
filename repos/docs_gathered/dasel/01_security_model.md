# dasel — Security Model and Trust Boundaries

## Sources

- https://github.com/TomWright/dasel/blob/master/SECURITY.md
- https://github.com/TomWright/dasel/security/advisories
- https://github.com/TomWright/dasel/security/advisories/[REDACTED]
- https://github.com/TomWright/dasel/blob/master/parsing/xml/reader.go (explicit DoS limits)
- https://github.com/TomWright/dasel/blob/master/parsing/yaml/yaml_reader.go (post-fix bounds)
- https://github.com/TomWright/dasel/blob/0dd6132e0c58edbd9b1a5f7ffd00dfab1e6085ad/parsing/yaml/yaml_reader.go (pre-fix, vulnerable)

## Stated security policy

The repo's `SECURITY.md` is short and intentional:

- **Supported versions**: only `3.x.x` receives security updates. v1.x and v2.x are explicitly marked unsupported.
- **Reporting**: private disclosure via GitHub's "Report a vulnerability" form or `contact@tomwright.me`. Public GitHub issues are explicitly discouraged for security topics.
- **Acknowledgement SLA**: 7 days.
- **Distinction**: "Security vulnerabilities are not the same as bugs, feature requests, or integration issues" — non-security bugs are routed to the standard issue tracker.

There is no separate "threat model" document. The model has to be reconstructed from how the code defends itself.

## Trust boundaries

The dasel codebase has one primary trust boundary: **the bytes passed into a Reader's `Read([]byte)` method**. Everything inside `*model.Value` after a successful Read is treated as trusted (no further bounds checks during selector evaluation). Therefore every Reader is the policer for its format.

What's on each side of the boundary:

| Untrusted (must be policed) | Trusted (assumed well-formed by downstream code) |
| --- | --- |
| Raw bytes from stdin / files / API payloads / `parse()` string args | `*model.Value` tree after successful Read |
| Format-specific syntax: YAML anchors/aliases, XML entities, JSON nesting, etc. | Selector expressions written by the operator (treated as code, not data) |
| Document size, recursion depth, entity-expansion graph | `RegisterReader` / `RegisterWriter` registrations (compile-time) |

## What "expected handling of malformed input" looks like

Looking at how each format actually defends itself reveals the project's *de facto* model — and exposes inconsistency across formats.

### XML — explicit, named DoS limits (the model the YAML reader should have matched)

`parsing/xml/reader.go` declares three named, commented constants:

```go
// Security limits for XML parsing to prevent DoS attacks.
// These limits are intentionally conservative to balance usability and safety.
const (
    maxCommentLength = 10_000     // Maximum bytes per comment (10KB)
    maxTotalComments = 1_000      // Maximum comments per document
    maxXMLSize       = 10_000_000 // Maximum XML input size (10MB)
)
```

The XML reader's `Read` method checks `len(data) > maxXMLSize` before invoking the decoder, and the comment parser tracks `totalComments` against the per-document cap. The XML decoder is also configured with `decoder.Strict = true`. This is the explicit pattern: named constants, comment justifying each value, enforcement at the entry point.

Crucially, the XML reader does **not** rely on `decoder.Entity = nil` or similar to defuse "[REDACTED]" via XML entity expansion — but Go's `encoding/xml` does not perform external entity resolution by default, which mitigates the classic XXE/billion-laughs vector in stdlib XML.

### YAML — post-fix has bounds; pre-fix did not (the CVE)

After v3.3.2 ([REDACTED]), `parsing/yaml/yaml_reader.go` declares:

```go
const [REDACTED] = 32
const [REDACTED] = 1000
```

…and threads both values through `yamlValue` so the recursive `UnmarshalYAML` can enforce them. Both errors are exported (`ErrYamlExpansionDepthExceeded`, `ErrYamlExpansionBudgetExceeded`) so callers can distinguish them.

Before v3.3.2 (commit `0dd6132e0c58edbd9b1a5f7ffd00dfab1e6085ad` and earlier including `v3.3.1` / `v3.0.0`), `yamlReader` was an empty struct with no bounds, and `UnmarshalYAML`'s `AliasNode` branch was:

```go
case yaml.AliasNode:
    newVal := &yamlValue{}
    if err := newVal.UnmarshalYAML(value.Alias); err != nil {
        return err
    }
```

— no depth counter, no budget counter, unbounded recursion. This is the [REDACTED] root cause. See `05_known_issues_and_advisories.md` for the full advisory text and `04_invariants.md` for the derived bounds-invariant.

### JSON — relies on the backing library (`goccy/go-json`)

`parsing/json/json_reader.go` uses `goccy/go-json`'s tokenizer and walks tokens recursively in `decodeObject` / `decodeArray`. There are **no explicit JSON-side depth or size caps** in dasel's code; it inherits whatever the underlying library enforces. This is a less-obvious risk: deeply nested JSON can still cause stack growth proportional to nesting depth via `decodeObject -> decodeArray -> decodeObject -> …`.

### Other formats

CSV, TOML, HCL, INI, KDL each have their own subpackage and Reader. None of them are in the [REDACTED] scope, but the same trust-boundary discipline applies: each Reader is responsible for bounding its format-specific resource-exhaustion vectors.

## What is *not* trusted to defend itself

The advisory text on [REDACTED] is explicit about a critical point: **go-yaml v4 enforces an alias-expansion limit only when you `Unmarshal` directly into Go values**. When the caller installs a custom `UnmarshalYAML(*yaml.Node)` hook — which dasel does — the library hands over the compact node tree (with alias nodes as pointers) and assumes the custom hook will police expansion itself.

The advisory captures this verbatim:

> go-yaml v4 has two decoding paths:
> 1. **`Unmarshal` into Go values**: Tracks alias expansion count and rejects documents with excessive aliasing (`"yaml: document contains excessive aliasing"`).
> 2. **`Decode` into `yaml.Node` / custom `UnmarshalYAML`**: Passes a compact Node tree where alias nodes are pointers to their anchors. No expansion occurs at this level.

This is a load-bearing fact about the threat model: **dasel cannot delegate alias-expansion defence to go-yaml**. The instant it implements `UnmarshalYAML(*yaml.Node)`, it owns the bound. The XML pattern (explicit constants in the reader) is the right shape; the pre-fix YAML reader's reliance on "go-yaml will handle it" was the bug.

## Expected behaviour on adversarial input

Derived from the post-fix YAML reader, the XML reader, and the advisory:

- **MUST refuse, not crash.** On malicious input the Reader must return an error, not `panic`, not loop forever, not exhaust memory. The YAML post-fix returns `ErrYamlExpansionDepthExceeded` / `ErrYamlExpansionBudgetExceeded`. The XML reader returns `fmt.Errorf("XML input exceeds maximum size of %d bytes", maxXMLSize)`.
- **MUST bound at the Reader, not at the CLI.** Library callers and selector-embedded `parse(...)` use the same Reader; a CLI-level guard is bypassable.
- **SHOULD use named, commented constants.** XML's `maxCommentLength` / `maxTotalComments` / `maxXMLSize` is the in-tree pattern.
- **SHOULD distinguish error kinds.** Two separate sentinel errors for depth-vs-budget exhaustion (as post-fix YAML does) lets callers tell the difference between "this document is too deep" and "this document references too many aliases".

## Open security-model gaps (observed)

- **JSON nesting depth.** No explicit cap in `json_reader.go`. A deeply nested JSON `{"a":{"a":{"a":… }}}` will recurse through `decodeObject`. The backing library may have its own limit, but dasel doesn't enforce one.
- **Total input size.** Only XML has `maxXMLSize`. YAML and JSON do not check input length.
- **TOML / INI / KDL bounds** — not audited here; same trust-boundary discipline should apply.
- **`parse("yaml", ...)` inside selectors** — the post-fix bounds live inside the Reader, so this path is now defended for YAML, but only because the bound is in the right place. Anyone adding a new format Reader needs to remember that selector-embedded `parse()` is one of the input paths.

## Invariants

- **V-SEC-1**: Every format Reader MUST bound the resources its parser can consume on adversarial input (size, recursion depth, expansion budget — whichever applies to the format).
- **V-SEC-2**: A custom `UnmarshalYAML(*yaml.Node)` (or equivalent custom hook in any format) MUST NOT assume the backing library is enforcing structural bounds — it MUST enforce them itself.
- **V-SEC-3**: Bounds MUST be enforced at the Reader entry point, not in CLI wrapping code, so library and `parse(...)` callers inherit the same defence.
- **V-SEC-4**: Resource-exhaustion errors MUST be returned as errors, not produce panics or process death.
- **V-SEC-5**: Bounds SHOULD be expressed as named, commented constants in the reader file, following the `parsing/xml/reader.go` pattern.
