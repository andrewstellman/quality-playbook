# dasel — Invariants for Parser Bounds and Resource Exhaustion

## Sources

- https://github.com/TomWright/dasel/blob/master/parsing/yaml/yaml_reader.go
- https://github.com/TomWright/dasel/blob/master/parsing/yaml/yaml.go
- https://github.com/TomWright/dasel/blob/master/parsing/yaml/yaml_test.go (the "bounded yaml expansion" / "yaml expansion depth boundary" / "yaml expansion budget boundary" / "yaml expansion budget resets per document" tests)
- https://github.com/TomWright/dasel/blob/master/parsing/xml/reader.go
- https://github.com/TomWright/dasel/security/advisories/GHSA-4fcp-jxh7-23x8
- https://github.com/TomWright/dasel/blob/0dd6132e0c58edbd9b1a5f7ffd00dfab1e6085ad/parsing/yaml/yaml_reader.go (vulnerable parent commit)
- https://github.com/TomWright/dasel/pull/531 ("Fix yaml unbounded expansion")

## Method

These invariants are derived three ways:

1. **From the code**: post-fix `yaml_reader.go` and `xml/reader.go` show what the project currently enforces.
2. **From the diff** between vulnerable commit `0dd6132e0c58edbd9b1a5f7ffd00dfab1e6085ad` and master: what *had to be added* to close the CVE.
3. **From the regression tests** the maintainer wrote alongside the fix (`yaml_test.go` lines 420, 484, 550, 677). When a maintainer writes a regression test of the form "at limit: pass, over limit: fail", the boundary behaviour is the codified invariant.

Each invariant is paired with the source that establishes it and a brief statement of how a parser-bound auditor (or QPB) would detect a regression of that invariant.

## Core resource-bound invariants

### V-1: YAML alias expansion must be bounded by depth

**Statement**: The custom `UnmarshalYAML` implementation in `parsing/yaml/yaml_reader.go` MUST track the depth of alias-chain dereferencing and reject inputs whose alias chains exceed a fixed cap.

**Source**: 
- Post-fix: `const maxExpansionDepth = 32` in `yaml_reader.go`, threaded via `yamlValue.maxExpansionDepth`, checked at the top of every `UnmarshalYAML` call.
- Regression test: `yaml_test.go:484` `t.Run("yaml expansion depth boundary", ...)` — at-limit passes, over-limit returns `ErrYamlExpansionDepthExceeded`.

**Detection signature**: 
- The `AliasNode` case in `(*yamlValue).UnmarshalYAML` recurses with `expansionDepth: yv.expansionDepth + 1`. If a future commit changes that to `expansionDepth: yv.expansionDepth` (depth not incremented) or removes the `if yv.expansionDepth > yv.maxExpansionDepth` guard at the top of the function, the invariant is broken.
- A diff that touches `AliasNode` handling without preserving both the depth check and the depth-increment is suspect.

### V-2: YAML alias expansion must be bounded by a per-document budget

**Statement**: The custom `UnmarshalYAML` implementation MUST decrement a shared budget on every alias resolution and reject the document when the budget falls below zero.

**Source**:
- Post-fix: `const maxExpansionBudget = 1000` in `yaml_reader.go`, `expansionBudget *int` shared via pointer across all recursive `yamlValue` instances, decremented on every AliasNode resolution.
- Regression test: `yaml_test.go:550` `t.Run("yaml expansion budget boundary", ...)` — at-budget passes, over-budget returns `ErrYamlExpansionBudgetExceeded`.

**Detection signature**: 
- The pointer-sharing pattern is load-bearing. If a future refactor changes `expansionBudget *int` to `expansionBudget int` (value, not pointer), the decrement is no longer visible to sibling recursion — broken.
- The `AliasNode` case MUST contain `*yv.expansionBudget = *yv.expansionBudget - 1` and `if *yv.expansionBudget < 0 { return ErrYamlExpansionBudgetExceeded }`.

### V-3: Depth and budget bounds are independent (both must hold)

**Statement**: Depth alone and budget alone are each insufficient. Depth bounds a single long chain (`*a` → `*a` → `*a` …) but allows wide fanout. Budget bounds total expansions across the document but allows short chains.

**Source**:
- The advisory PoC uses a 9-deep, 9-fanout pyramid that produces 9⁹ ≈ 387M expansions — defeating any pure-depth check that wasn't set ≤ 9, while a budget cap of 1000 catches it inside the first hundredth of the explosion.
- A pure linear chain (`*a` → `*a` → … 100 levels) defeats a pure-budget check that allows the full budget on a single chain.
- Regression test: `yaml_test.go:420` `t.Run("bounded yaml expansion", ...)` — accepts an error of either kind: `if !errors.Is(gotErr, yaml.ErrYamlExpansionDepthExceeded) && !errors.Is(gotErr, yaml.ErrYamlExpansionBudgetExceeded) { t.Fatalf(...) }`. The test passes if either error fires, codifying that either bound catching the PoC is acceptable but at least one must catch it.

**Detection signature**: removal of either `maxExpansionDepth` or `maxExpansionBudget` weakens the defence against one of the two attack shapes. Auditing a YAML reader that has only one bound, not both, is a yellow flag.

### V-4: Budget must reset per document in multi-doc streams

**Statement**: In a YAML stream containing multiple documents (separated by `---`), each document gets a fresh budget. Cumulative legitimate alias use across documents must not exhaust the budget for the stream.

**Source**:
- Post-fix `Read`: at the top of each `Decode` iteration, `expansionBudget := j.maxExpansionBudget` creates a fresh per-document budget and a fresh `&yamlValue{expansionBudget: &expansionBudget}` for the decoder.
- Regression test: `yaml_test.go:677` `t.Run("yaml expansion budget resets per document", ...)`.

**Detection signature**: a refactor that hoists `expansionBudget` outside the per-document loop — e.g. allocates it once on the `yamlReader` struct rather than per `Decode` — silently fails legitimate multi-doc YAML.

### V-5: Depth and budget bounds apply on every input path, not only on CLI

**Statement**: Any code path that reaches `(*yamlReader).Read([]byte)` MUST receive the bounded behaviour. The CLI, the library entry point, and the selector-embedded `parse("yaml", ...)` function all share the same Reader.

**Source**:
- `parsing/format.go` `Format.NewReader` is the single entry point; all three callers (CLI argparse, library callers, selector `parse()`) call it identically.
- The advisory's "Impact" section enumerates exactly these three paths.

**Detection signature**: any defence implemented in `cmd/dasel/` (CLI flag handling) rather than in `parsing/yaml/yaml_reader.go` would bypass paths 2 and 3. Auditors should look for the bound in the reader file, not in CLI argument parsing.

## XML resource-bound invariants

### V-6: XML input total-size cap

**Statement**: XML input larger than 10MB MUST be rejected before decoding begins.

**Source**: `parsing/xml/reader.go` — `const maxXMLSize = 10_000_000`, checked at the start of `(*xmlReader).Read`.

**Detection signature**: removal of the early `if len(data) > maxXMLSize` check, or replacement of the constant with a much larger value with no justification.

### V-7: XML comment-length cap per comment

**Statement**: A single XML comment MUST NOT exceed 10KB.

**Source**: `parsing/xml/reader.go` — `const maxCommentLength = 10_000`, enforced inside the comment parser.

### V-8: XML total-comment cap per document

**Statement**: A single XML document MUST contain at most 1,000 comments.

**Source**: `parsing/xml/reader.go` — `const maxTotalComments = 1_000`, threaded through `parseElement` as a `*int` pointer counter.

### V-9: XML decoder must use Strict mode

**Statement**: The `encoding/xml` decoder MUST be configured with `decoder.Strict = true` to refuse malformed XML rather than silently coercing it.

**Source**: `parsing/xml/reader.go` — `decoder.Strict = true` immediately after `xml.NewDecoder(...)`.

**Detection signature**: any commit that sets `decoder.Strict = false` is suspect.

## API-shape invariants supporting the above

### V-10: Reader errors must be returned as errors, never as panics

**Statement**: `Reader.Read` returns `(*model.Value, error)`. Panics must not escape — including those caused by adversarial input.

**Source**: the `parsing.Reader` interface contract in `parsing/reader.go`; the pattern used by every existing Reader (return-on-error rather than panic-on-error).

**Detection signature**: a `panic(...)` call in any reader file is presumptively wrong; `recover()` in `Read` is the safety net.

### V-11: Resource-exhaustion errors must be distinguishable sentinels

**Statement**: Different resource-exhaustion conditions MUST return distinct sentinel errors so callers can branch on them with `errors.Is`.

**Source**: post-fix YAML reader exports `ErrYamlExpansionDepthExceeded` and `ErrYamlExpansionBudgetExceeded`, and `yaml_test.go` uses `errors.Is(err, yaml.ErrYamlExpansionDepthExceeded)` to validate the boundary tests.

**Detection signature**: a refactor that collapses both into a single generic `errors.New("yaml resource exhausted")` loses the ability to test boundary behaviour precisely and breaks the existing regression tests.

### V-12: Bounds must be expressed as named constants in the reader file

**Statement**: Resource caps MUST be named, top-level constants in the reader file, not magic numbers buried in code.

**Source**: both `xml/reader.go` (three named constants with inline comments justifying the values) and post-fix `yaml/yaml_reader.go` (two named constants) follow this pattern.

**Detection signature**: a hardcoded `if depth > 32` without a `maxExpansionDepth` constant is a regression of readability and a yellow flag for "this got patched in a hurry without proper hygiene".

## Detection patterns for QPB hunt

Conditional on QPB hunting blind for the CVE-2026-33320-shaped flaw, the diagnostic that maximises detection probability:

**1. Look for `UnmarshalYAML(value *yaml.Node)` implementations that recurse on `value.Alias` (or `value.Kind == yaml.AliasNode`) without any visible counter.**

In dasel pre-fix:
```go
case yaml.AliasNode:
    newVal := &yamlValue{}                        // no counter fields
    if err := newVal.UnmarshalYAML(value.Alias); err != nil { return err }
```

In dasel post-fix:
```go
case yaml.AliasNode:
    if yv.expansionBudget != nil {
        *yv.expansionBudget = *yv.expansionBudget - 1
        if *yv.expansionBudget < 0 { return ErrYamlExpansionBudgetExceeded }
    }
    newVal := &yamlValue{
        expansionDepth:    yv.expansionDepth + 1,
        maxExpansionDepth: yv.maxExpansionDepth,
        expansionBudget:   yv.expansionBudget,
    }
```

The pre-fix structural marker: `&yamlValue{}` (empty initialiser, no counter) in the AliasNode arm. That's the most concise signature of the vulnerability.

**2. Look for the same shape in other formats**: any Reader that recurses on a pointer-link that the *input* controls — and where the pointer can form a cycle or DAG — needs a budget. XML attribute-default expansion, custom JSON references, INI include directives, etc. The pattern generalises.

**3. Check that bounds are exported sentinels** (V-11): `errors.New("yaml expansion depth exceeded")` paired with a separate test file invoking `errors.Is` is the project's idiom. Absence of either is suspect.

**4. Check for regression tests of the form "at limit, over limit"**: if the bound exists but no test pins the boundary behaviour, the bound is one refactor away from being silently weakened.
