# dasel — Project Overview

## Sources

- https://github.com/TomWright/dasel
- https://github.com/TomWright/dasel/blob/master/README.md
- https://daseldocs.tomwright.me
- https://daseldocs.tomwright.me/getting-started/readme.md
- https://api.github.com/repos/TomWright/dasel (repo metadata, retrieved 2026-06-01)
- https://github.com/TomWright/dasel/blob/master/parsing/format.go
- https://github.com/TomWright/dasel/blob/master/parsing/reader.go
- https://github.com/TomWright/dasel/blob/master/parsing/writer.go

## What dasel is

dasel (short for **Data-Select**) is a Go command-line tool and Go library for **querying, modifying, and transforming structured data files**. The project's tagline: "Unified querying, transformation, and modification of JSON, TOML, YAML, XML, INI, HCL, KDL and CSV." It is written entirely in Go (default branch `master`), MIT-licensed, owned by Tom Wright, created 2020-09-22, ~7,963 GitHub stars at time of writing. The major version under active development is **v3** (released December 2025); v3 is the only branch receiving security updates per the project's `SECURITY.md`.

The Go module path is `github.com/tomwright/dasel/v3`. The CLI entrypoint lives at `cmd/dasel`.

## Position in the ecosystem

dasel sits in the same "structured-data query/edit CLI" niche as `jq` (JSON only) and `yq` (YAML/JSON wrapper around jq), but with a deliberately wider format surface and a single unified selector syntax that works across formats. This is the load-bearing design claim: the same selector (e.g. `users.[0].name`) works whether the underlying document is JSON, YAML, TOML, XML, CSV, HCL, INI, or KDL.

GitHub topics declared on the repo: `cli, config, configuration, data-processing, data-structures, data-wrangling, devops-tools, go, golang, hcl2, json, json-processing, parser, query, selector, toml, update, xml, yaml, yaml-processor`.

## Supported formats and where each lives

The `parsing/` package contains one subpackage per format. Each subpackage registers a Reader and a Writer with the format registry at `init()` time:

| Format | Package | Reader file | Backing library |
| --- | --- | --- | --- |
| JSON | `parsing/json` | `json_reader.go` | `github.com/goccy/go-json` |
| YAML | `parsing/yaml` | `yaml_reader.go` | `go.yaml.in/yaml/v4` |
| TOML | `parsing/toml` | (see package) | (TOML lib in go.mod) |
| XML | `parsing/xml` | `reader.go` | `encoding/xml` (stdlib) |
| CSV | `parsing/csv` | (see package) | `encoding/csv` (stdlib) |
| HCL | `parsing/hcl` | (see package) | hashicorp/hcl |
| INI | `parsing/ini` | (see package) | INI lib |
| KDL | `parsing/kdl` | (see package) | KDL lib |
| `d` | `parsing/d` | (see package) | dasel native |

The top of `parsing/parsing_dir.json` lists the directory structure: `csv/`, `d/`, `format.go`, `hcl/`, `ini/`, `json/`, `kdl/`, `reader.go`, `toml/`, `writer.go`, `xml/`, `yaml/`.

## Usage modes

Three distinct usage modes, all of which take untrusted data through the same parsing pipeline:

1. **CLI on stdin/files** — `echo '{"foo":{"bar":"baz"}}' | dasel -i json 'foo.bar'` or `dasel -f config.yaml '.users.[0]'`. The input format is either inferred from extension or specified with `-i`.
2. **Library — direct parser invocation** — Go callers obtain a Reader via `parsing.Format("yaml").NewReader(parsing.DefaultReaderOptions())` and call `reader.Read(data)`. Common in tools that embed dasel for config manipulation.
3. **Selector-embedded `parse()` function** — Within a dasel selector expression, the `parse("yaml", ...)` function parses a string value as the named format and returns the decoded structure. This pulls untrusted-string parsing into the middle of selector evaluation.

All three modes funnel through the same registered Reader and therefore inherit the same parser-bounds behaviour. A bound that's enforced only on CLI input (and not on `parse()` calls inside a selector) is incomplete.

## Domain — what makes input "trusted" vs. "untrusted"

dasel is positioned in the README and docs as a tool for "devops, configuration, data wrangling" — implying input often originates in the operator's own files. But two realistic deployment patterns put untrusted content directly in front of the parser:

- **CI / config pipelines that consume third-party data**: webhook payloads, GitHub Action outputs, external API responses normalized through dasel.
- **Library consumers that build a service around dasel** (web service, MCP-style tool, internal API): the dasel parser becomes a parsing surface for whatever data the service accepts.

Both patterns mean the parser must be hardened against adversarial input even though the CLI ergonomics suggest a "trusted user files" mindset. The published CVE in scope here ([REDACTED], see `05_known_issues_and_advisories.md`) was discovered specifically because the library-usage path passes adversarial YAML into `(*yamlReader).Read` without any external bound.

## The parsing pipeline at 30,000 feet

```
   input bytes  ──▶  Format.NewReader(opts).Read(data)  ──▶  *model.Value  ──▶  selector evaluation  ──▶  Format.NewWriter(opts).Write(value)
                        │                                                                                           │
                        ▼                                                                                           ▼
              format-specific Reader                                                                 format-specific Writer
              (yaml_reader.go, json_reader.go, …)                                                    (yaml_writer.go, …)
```

Every Reader returns the same internal type, `*model.Value` — a tagged value (map, slice, string, int, float, bool, null) with metadata. This means a bound on Reader recursion or expansion is the only place where format-specific input shape can be policed; once the data is in `*model.Value` form, the shape of the source format is gone.

## Repo metadata snapshot

- Owner: TomWright (Tom Wright)
- License: MIT
- Default branch: master
- Module: `github.com/tomwright/dasel/v3`
- Latest release at time of writing: **v3.3.2** (published 2026-03-18), which contains the fix for [REDACTED] via [REDACTED] "Fix yaml [REDACTED]".
- Open issues: ~20
- Stars: ~7,963

## Invariants (project-level)

- **V-PROJ-1**: Only the v3.x major version is supported with security updates (per `SECURITY.md`). Adopters on v1.x or v2.x must upgrade, not backport.
- **V-PROJ-2**: All format Readers MUST conform to the `parsing.Reader` interface (`Read([]byte) (*model.Value, error)`). New formats register via `parsing.RegisterReader(format, fn)` in their package `init()`.
- **V-PROJ-3**: All parsing entrypoints (CLI, library `reader.Read`, in-selector `parse(...)`) flow through the same Reader instance. Any input bound MUST be in the Reader, not in CLI argument handling alone — otherwise the library and `parse()` paths bypass it.
