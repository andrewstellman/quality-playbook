# dasel — Known Security Advisories and Related CVEs

## Sources

- https://github.com/TomWright/dasel/security/advisories
- https://github.com/TomWright/dasel/security/advisories/[REDACTED]
- https://github.com/advisories/[REDACTED]
- https://nvd.nist.gov/vuln/detail/[REDACTED]
- https://github.com/TomWright/dasel[REDACTED] (the fix PR — "Fix yaml [REDACTED]", merged 2026-03-18)
- https://github.com/TomWright/dasel/releases/tag/v3.3.2 (the fix release)
- https://github.com/TomWright/dasel/blob/master/SECURITY.md
- https://github.com/advisories/[REDACTED] ([REDACTED] — go-yaml billion-laughs via Kubernetes)
- https://github.com/advisories/[REDACTED] ([REDACTED] — go-yaml v2 DoS)
- https://github.com/advisories/[REDACTED] ([REDACTED] — go-yaml v2 excessive CPU/memory)
- https://github.com/advisories/[REDACTED] ([REDACTED] — go-yaml v3 DoS)

## The in-scope CVE: [REDACTED] / [REDACTED]

### Summary

- **Title**: "Dasel has [REDACTED] in dasel leads to CPU/memory denial of service"
- **GHSA**: [REDACTED]
- **CVE**: [REDACTED]
- **Published**: 2026-03-19 (GitHub-reviewed); NVD published 2026-03-24
- **Severity**: Medium / CVSS 3.1 = 6.2 (`AV:L/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`)
- **CWE**: [REDACTED] (Uncontrolled Recursion)
- **Reporter**: kq5y (https://github.com/kq5y)
- **Affected**: `github.com/tomwright/dasel/v3` from v3.0.0 up to but not including v3.3.2
- **Fixed in**: **v3.3.2** (released 2026-03-18, [REDACTED] "Fix yaml [REDACTED]")
- **Vulnerable parent commit cited in advisory**: `0dd6132e0c58edbd9b1a5f7ffd00dfab1e6085ad`
- **v3.3.1 vulnerable commit cited**: `fba653c7f248aff10f2b89fca93929b64707dfc8`

### Root cause

dasel's YAML reader at `parsing/yaml/yaml_reader.go` implements `(*yamlValue).UnmarshalYAML(*yaml.Node)`. When the decoder encounters an `AliasNode`, the dasel implementation recursively calls itself on `value.Alias` (the anchor target). Pre-fix, this recursion had **no bound on depth and no bound on total alias resolutions**.

The advisory describes the precise failure mode:

> The root cause is that go-yaml v4 has two decoding paths:
>
> 1. **`Unmarshal` into Go values**: Tracks alias expansion count and rejects documents with excessive aliasing (`"yaml: document contains excessive aliasing"`).
> 2. **`Decode` into `yaml.Node` / custom `UnmarshalYAML`**: Passes a compact Node tree where alias nodes are pointers to their anchors. No expansion occurs at this level.
>
> Dasel receives the compact Node tree via its `UnmarshalYAML(*yaml.Node)` hook and then recursively follows `value.Alias` pointers, re-expanding aliases without a budget.

### Proof-of-concept (from the advisory)

The attack uses a 9-level pyramid where each level references the previous nine times. The input is 342 bytes; the expansion is 9⁹ ≈ 387,420,489 string occurrences:

```yaml
a: &a ["lol","lol","lol","lol","lol","lol","lol","lol","lol"]
b: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a]
c: &c [*b,*b,*b,*b,*b,*b,*b,*b,*b]
d: &d [*c,*c,*c,*c,*c,*c,*c,*c,*c]
e: &e [*d,*d,*d,*d,*d,*d,*d,*d,*d]
f: &f [*e,*e,*e,*e,*e,*e,*e,*e,*e]
g: &g [*f,*f,*f,*f,*f,*f,*f,*f,*f]
h: &h [*g,*g,*g,*g,*g,*g,*g,*g,*g]
i: &i [*h,*h,*h,*h,*h,*h,*h,*h,*h]
```

The advisory reports test-environment evidence:

```
Payload size: 342 bytes
Go version: go1.26.1
GOARCH: arm64

=== Test 1: Direct yaml.Unmarshal (should be rejected) ===
SAFE: Rejected in 824.042µs: yaml: document contains excessive aliasing

=== Test 2: Dasel YAML reader (VULNERABLE) ===
CONFIRMED: did not complete within 5s; [REDACTED] in progress
```

Note the contrast: a direct `yaml.Unmarshal` rejects the same payload in under a millisecond, because the library's built-in counter activates on that path. Dasel's custom `UnmarshalYAML` bypassed it.

### Impact (per advisory)

> An attacker who can supply YAML for processing by dasel can cause denial of service. The library's own `UnmarshalYAML` handler triggers [REDACTED] from a 342-byte input. The process consumes 100% CPU and exhibits growing memory usage until externally terminated.
>
> This affects:
> - CLI usage: when reading YAML from stdin or files via the CLI
> - Library usage: any application using dasel's YAML reader to parse untrusted YAML
> - The `parse("yaml", ...)` function in selectors

### Suggested fix (per advisory)

> One likely fix is to add an alias expansion counter to `UnmarshalYAML` that limits the total number of alias resolutions, similar to go-yaml v4's internal limit. For example, track a counter across all recursive calls and return an error when it exceeds a threshold (e.g., 1,000,000 expansions).

### Fix as landed ([REDACTED], v3.3.2)

The maintainer's fix went stricter than the suggestion and used two independent bounds:

```go
const [REDACTED] = 32       // chain-length cap
const [REDACTED] = 1000    // total-resolution cap (per document)
```

Both bounds enforced inside `(*yamlValue).UnmarshalYAML`; both distinguishable via separate sentinel errors. The budget is reset per document in multi-doc streams. See `02_api_contract.md` and `04_invariants.md` for the full mechanism.

PR title: "Fix yaml [REDACTED]". PR merged: 2026-03-18 19:09:55 UTC. Two commits, four files changed. Release v3.3.2 published 19:15:01 UTC the same day. Other items in the release (PR #527, PR #528) are unrelated.

### CVSS vector decoded

`CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H` =

- **AV:L** Attack vector: Local. The attacker needs to supply input to a dasel process locally — the advisory explicitly says CLI/library/`parse()`, not a network listener.
- **AC:L** Attack complexity: Low. A 342-byte file is enough.
- **PR:N / UI:N** No privileges or user interaction required.
- **C:N / I:N / A:H** No confidentiality or integrity impact, but high availability impact (DoS).

The local-AV classification matters because dasel is primarily a CLI; the attack surface is "whatever YAML the user is processing" rather than "network attacker." But the impact still applies any time dasel is embedded in a service that processes untrusted YAML — which is the harder scenario to spot.

## Prior dasel security advisories

Per https://github.com/TomWright/dasel/security/advisories — the API response for the repo's advisories list, scraped 2026-06-01, returned **only** the [REDACTED] advisory listed above. [REDACTED] is the first published GitHub Security Advisory against dasel.

## The "[REDACTED]" / "billion anchors" attack family

The dasel CVE is the latest in a family of resource-exhaustion attacks against parsers that follow declared back-references during decoding. The family includes:

### XML [REDACTED] (the original)

```xml
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  ...
]>
<lolz>&lol9;</lolz>
```

Defence (in dasel's XML reader): Go's `encoding/xml` doesn't expand DTD entities by default, plus `maxXMLSize` caps total input.

### YAML billion anchors (the dasel CVE shape)

```yaml
a: &a [x,x,x,x,x,x,x,x,x]
b: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a]
...
```

Defence (in dasel's post-fix YAML reader): two bounds on alias expansion (`[REDACTED]`, `[REDACTED]`).

### Related published CVEs in go-yaml itself

| GHSA / CVE | Package | Year | Severity | Mechanism |
| --- | --- | --- | --- | --- |
| [[REDACTED] / [REDACTED]](https://github.com/advisories/[REDACTED]) | gopkg.in/yaml.v2 (via Kubernetes) | 2019 | Medium | Excessive platform resource consumption — billion-laughs-style YAML |
| [[REDACTED] / [REDACTED]](https://github.com/advisories/[REDACTED]) | gopkg.in/yaml.v2 | 2022 | Medium | Untrusted YAML → DoS |
| [[REDACTED] / [REDACTED]](https://github.com/advisories/[REDACTED]) | gopkg.in/yaml.v2 | 2022 | High | "Parsing malicious or large YAML documents can consume excessive amounts of CPU or memory" |
| [[REDACTED] / [REDACTED]](https://github.com/advisories/[REDACTED]) | gopkg.in/yaml.v3 | 2022 | High | Untrusted YAML → DoS |

These four upstream advisories iteratively tightened the library's built-in defences against billion-laughs. By yaml.v3 (and now yaml.v4), the library refuses excessive aliasing on the `Unmarshal`-into-Go-value path with the explicit error `"yaml: document contains excessive aliasing"`. **This defence is the one bypassed by custom `UnmarshalYAML` implementations**, which is exactly the dasel [REDACTED] root cause.

### Pattern lesson

Every time a Go YAML library tightens its internal limit, consumers who implemented custom unmarshalers are unaffected by the fix — both for good (their code keeps working) and for ill (their code keeps being vulnerable). The dasel CVE is the canonical example of this anti-pattern's downstream cost. Auditors of any Go YAML consumer should specifically check whether the consumer implements `UnmarshalYAML(*yaml.Node)` and, if so, whether it counts alias expansions.

## Defensive coding signatures present in the dasel fix

The post-fix dasel code exhibits several patterns that make the fix robust to future drift:

1. **Named constants** rather than magic numbers (`[REDACTED] = 32`, `[REDACTED] = 1000`).
2. **Exported sentinel errors** (`ErrYamlExpansionDepthExceeded`, `ErrYamlExpansionBudgetExceeded`) so callers and tests can `errors.Is` them.
3. **Two independent bounds** for two distinct attack shapes (deep chain vs. wide fanout).
4. **Pointer-shared budget** across recursion so siblings can't separately exhaust their share.
5. **Per-document budget reset** so legitimate multi-doc streams aren't penalised.
6. **Four regression tests** (`yaml_test.go:420, 484, 550, 677`) pinning the boundary behaviour — including the explicit "either error is fine" check for the PoC, the at-limit-vs-over-limit boundary, and the per-doc reset.

## Disclosure timeline

- **Reporter discovers**: kq5y, private report via GitHub's advisory form.
- **Fix merged**: 2026-03-18 19:09:55 UTC ([REDACTED]).
- **v3.3.2 released**: 2026-03-18 19:15:01 UTC.
- **GHSA published / GitHub-reviewed**: 2026-03-19 12:50:57 UTC.
- **NVD published**: 2026-03-24 01:17:02 UTC.

The fix shipped within minutes of the merge, and the advisory went public ~17 hours later — a coordinated-disclosure pattern with very tight timing.
