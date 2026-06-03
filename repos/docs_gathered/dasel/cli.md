# CLI

The `dasel` command-line interface lives under `cmd/dasel` and `internal/cli`. The `cmd/dasel/main.go` entry point detects whether standard input is a terminal or a pipe, then hands control to `cli.MustRun(stdin, stdout, stderr)`. Each supported format package is blank-imported in `main.go` so its `init()` registers itself with the format registry before any command runs.

## Command tree

Commands are defined with the Kong CLI library and live in `internal/cli`. The top-level structure is:

```go
type CLI struct {
    Globals
    Query       QueryCmd       `cmd:"" default:"withargs" help:"[default] Execute a query"`
    Version     VersionCmd     `cmd:"" help:"Print the version"`
    Interactive InteractiveCmd `cmd:"" help:"Start an interactive session (alpha)"`
}
```

`Query` is the default; running `dasel '...'` without naming a subcommand executes a query. `Version` prints `internal.Version`. `Interactive` launches a Bubble Tea terminal UI for iterative selector authoring.

## Query flags

`QueryCmd` is the main surface and its flag set is:

- `-i / --in <format>` — input format identifier (`json`, `yaml`, `toml`, `xml`, `csv`, `hcl`, `ini`).
- `-o / --out <format>` — output format identifier; defaults to the input format if only one is given.
- `--root` — after running the selector, write the whole modified root document rather than the selector's result.
- `--unstable` — opt in to features marked as not-yet-stable (e.g. the `branch` expression).
- `--it` — launch the interactive Bubble Tea session for this query.
- `--var name=value` — define a query variable; values may be inline (`foo=bar`), inline with format (`foo=json:{"a":1}`), or read from a file (`foo=json:file:./data.json`).
- `--rw-flag key=value`, `--read-flag key=value`, `--write-flag key=value` — pass format-specific extension flags such as `csv-delimiter=;` or `xml-mode=structured`.
- `-c / --config <path>` — path to a YAML config file; defaults to `~/dasel.yaml`.
- The positional argument is the selector expression itself.

## Configuration

`internal/cli/config.go` defines a small config struct:

```go
type Config struct {
    DefaultFormat string `yaml:"default_format"`
}
```

The file is optional; if it does not exist, an in-memory default (`DefaultFormat: "json"`) is used. The path may begin with `~/` and is expanded against the current user's home directory. The first successful load is cached in a package-level variable, so subsequent calls are cheap.

## Pipeline orchestration

`internal/cli/run.go` wires everything together. It loads the config, resolves the effective input and output formats, builds a `parsing.Reader` and `parsing.Writer` from the format registry, applies any read/write extension flags, reads stdin (when present), threads the input value into `execution.ExecuteSelector` along with variable and unstable options, optionally overrides the result with the root document when `--root` is set, and finally hands the result to the writer. Errors are wrapped with descriptive prefixes (`error loading config`, `failed to get input reader`, `error reading stdin`, etc.) so the CLI can surface a useful message before exiting.
