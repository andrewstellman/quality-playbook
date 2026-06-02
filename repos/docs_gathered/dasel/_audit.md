# Audit — dasel at pinned revision

## Sources consulted (whitelist verification)

In-tree files at the pinned revision:

- /tmp/gather_dasel/README.md
- /tmp/gather_dasel/CONTRIBUTING.md
- /tmp/gather_dasel/Dockerfile
- /tmp/gather_dasel/go.mod
- /tmp/gather_dasel/api.go
- /tmp/gather_dasel/cmd/dasel/main.go
- /tmp/gather_dasel/internal/cli/command.go
- /tmp/gather_dasel/internal/cli/query.go
- /tmp/gather_dasel/internal/cli/run.go
- /tmp/gather_dasel/internal/cli/config.go
- /tmp/gather_dasel/internal/cli/variable.go
- /tmp/gather_dasel/internal/cli/read_write_flag.go
- /tmp/gather_dasel/selector/README.md
- /tmp/gather_dasel/selector/parser.go
- /tmp/gather_dasel/selector/lexer/token.go
- /tmp/gather_dasel/selector/lexer/tokenize.go (head)
- /tmp/gather_dasel/selector/ast/ast.go
- /tmp/gather_dasel/selector/ast/expression_complex.go (head)
- /tmp/gather_dasel/selector/parser/parser.go
- /tmp/gather_dasel/execution/README.md
- /tmp/gather_dasel/execution/context.go
- /tmp/gather_dasel/execution/execute.go
- /tmp/gather_dasel/execution/execute_recursive_descent.go (head)
- /tmp/gather_dasel/execution/func.go
- /tmp/gather_dasel/execution/options.go
- /tmp/gather_dasel/model/README.md
- /tmp/gather_dasel/model/value.go (head)
- /tmp/gather_dasel/model/value_comparison.go (head)
- /tmp/gather_dasel/model/error.go
- /tmp/gather_dasel/model/go_value.go
- /tmp/gather_dasel/parsing/format.go
- /tmp/gather_dasel/parsing/reader.go
- /tmp/gather_dasel/parsing/writer.go
- /tmp/gather_dasel/parsing/json/json.go
- /tmp/gather_dasel/parsing/json/json_reader.go (head)
- /tmp/gather_dasel/parsing/yaml/yaml.go
- /tmp/gather_dasel/parsing/yaml/yaml_reader.go (head)
- /tmp/gather_dasel/parsing/toml/toml.go
- /tmp/gather_dasel/parsing/xml/xml.go
- /tmp/gather_dasel/parsing/csv/csv.go
- /tmp/gather_dasel/parsing/hcl/hcl.go
- /tmp/gather_dasel/parsing/ini/ini.go
- /tmp/gather_dasel/parsing/d/reader.go
- Directory listings of cmd/, internal/, model/, parsing/ (each subdirectory), selector/ (and subdirectories), execution/

External documentation sources:

- daseldocs.tomwright.me — attempted a Wayback Machine fetch to pin temporally before the pinned commit's date; both attempts timed out. No external doc-site content was incorporated; all documentation in this corpus is derived from in-tree sources only.

## Sources explicitly NOT consulted (blacklist verification)

- GitHub Security tab: NOT READ
- GitHub Issues: NOT READ
- GitHub Pull Requests: NOT READ
- Commits later than the pinned revision: NOT READ
- The pinned commit's own diff or message beyond what `git log -1 --format` showed (used only to confirm SHA reachability); no file diffs read
- CHANGELOG.md: NOT READ (skipped entirely rather than filter, to avoid any risk of incidental contamination)
- SECURITY.md: NOT READ
- Third-party advisory databases (NVD, CVE.org, GHSA, Snyk, Wiz): NOT READ
- External blog posts, Stack Overflow, Reddit, conference talks: NOT READ
- /Users/andrewstellman/Documents/QPB/repos/docs_gathered.contaminated/: NOT READ (per the extra hard constraint for this task)

## Self-check verdict

- Forbidden vocabulary scan: PASS. Searched all seven content files for the banned terms (vulnerability, advisory, exploit, patched, disclosed, security fix, known issue, hardened, footgun, CVE/GHSA/CWE/PYSEC prefixes, hotfix, backport, breaking change, rewritten, rebuilt, high-churn, audit, coordinated, "the bug was", "the flaw was", "the root cause was"). None present.
- Equal subsystem depth check: PASS. The seven content files cover the seven major public subsystems at roughly comparable depth: overview.md (~390 words), cli.md (~470), selector_language.md (~470), execution_engine.md (~470), value_model.md (~470), parsing_formats.md (~510), library_api.md (~510). No file is positioned as more important than the others; naming is neutral and subsystem-focused.
- Fix-narrative scan: PASS. No file frames any feature as "fixed in", "since vX", "before vX", "after vX", "until vX", "added because of", or any other fix-context construct. Versioning references are limited to the module path's `/v3` marker and the Go-version line from `go.mod`.
- Code-quote check (architecture-only): PASS. Quoted constructs are limited to type declarations, interface signatures, top-level function signatures, enum/constant blocks, and CLI flag declarations. No function bodies are quoted. The few multi-line snippets reproduced are the package-level `type` declarations of `Value`, `Options`, `ReaderOptions`, `WriterOptions`, `Reader`/`Writer` interfaces, `Format`, the `CLI` Kong struct, and the top-level `Query` / `Select` / `Modify` signatures — public API surface only.

## Gatherer

- subagent / cowork instance
- date: 2026-06-02

## Notes

- Per the task instructions, CHANGELOG.md was skipped entirely rather than filtered line-by-line. The risk of an oversight while editing security-related lines out of a 30 KB changelog exceeded the modest benefit of any historical context it might have provided for the general-purpose reference.
- The Wayback Machine fetch against the public doc site (daseldocs.tomwright.me) timed out on both attempts; rather than retry indefinitely, the corpus was completed from in-tree sources, which are sufficient to describe every public subsystem at the level of detail required.
- Subsystems intentionally given lighter coverage in this pass: the interactive Bubble Tea mode (`internal/cli/interactive*.go`) is mentioned briefly in `cli.md` but not given its own file, because it is a UI wrapper over the same query pipeline rather than a distinct subsystem. The `internal/ptr` helper is too small to warrant a file. The `model/orderedmap` helper is mentioned within `value_model.md` for the same reason.
