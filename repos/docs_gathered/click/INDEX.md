# Click Documentation — Index & Behavioral Overview

Curated documentation for the **Click** CLI framework (Pallets), gathered for Quality Playbook spec-auditing. Click 8.3.x/8.4.x stable. Gathered 2026-05-21.

## Documents

| File | Area | Source fidelity |
|---|---|---|
| 01_OVERVIEW.md | What Click is, design opinions, canonical example | Fetched (welcome page) |
| 02_OPTIONS.md | Options: flags, multiple, count, prompt, envvar, callbacks, eager | Synthesized from documented behavior |
| 03_ARGUMENTS.md | Arguments: nargs/variadic, escape `--`, envvar, required-degradation | Fetched (arguments page) |
| 04_PARAMETER_TYPES.md | Types: BOOL/Choice/IntRange/FloatRange/File/Path/DateTime/custom | Fetched (parameter-types page) |
| 05_COMMANDS_GROUPS_CONTEXT.md | Commands, groups, nesting, Context/`obj`, invoke/forward, chaining | Synthesized from documented behavior |
| 06_EXCEPTIONS_AND_EXIT_CODES.md | Exception hierarchy + exit codes 0/1/2, Abort, standalone_mode | Synthesized from documented behavior |
| 07_TESTING_UTILITIES_UNICODE.md | CliRunner, echo/style, prompts, Windows/Unicode console | Synthesized (note 8.2 testing rework) |

> **Source fidelity note:** the parameter-types, arguments, and overview pages were fetched verbatim from the official docs. The options/commands/exceptions/testing pages would not render through the doc fetcher, so those files are synthesized from Click's documented behavior at 8.x — accurate at the API level, but the spec auditor should cross-check version-sensitive specifics (notably the **Click 8.2 CliRunner stderr rework**) against the *cloned* Click version under review.

## Critical Behavioral Specifications (must verify against code)

### Parameter conversion & types
1. **BOOL strings:** `1/true/t/yes/y/on`→True, `0/false/f/no/n/off`→False; nothing else.
2. **Choice returns the original choice**, not the user's spelling, after case-insensitive/normalized match.
3. **Ranges:** bounds closed by default; `clamp` substitutes the boundary silently; **FloatRange clamp requires closed bounds**.
4. **File** auto-closes on context teardown; `-` = stdin/stdout; lazy/atomic semantics.
5. **Path** with `exists=False` silently skips all checks if the path is absent; no `~` expansion.
6. **Custom `convert()`** must pass through already-correct values and tolerate `param=None`/`ctx=None`; fail via `self.fail()`.

### Parameters
7. **Options default `nargs=1`; variadic (`nargs=-1`) is arguments-only.**
8. **`multiple`→tuple (empty `()`), `count`→int (0), `is_flag`→bool** — empty-not-None contract.
9. **Arguments default to required but Click discourages required args** (graceful degradation); type inference: explicit > default-type > STRING.
10. **`--` terminates option parsing; `ignore_unknown_options` consumes option-looking tokens as args.**
11. **Eager options (`--help`/`--version`) process first and exit 0.**

### Commands / Context
12. **`ctx.obj` is inherited by child contexts** unless replaced.
13. **`invoke` uses supplied/default params; `forward` carries current params**; neither re-parses argv.
14. **`chain=True` runs subcommands in order; `result_callback` gets the ordered result list.**
15. **`standalone_mode=False` returns the value and propagates exceptions** instead of exiting.

### Exit codes & errors
16. **0 success / 1 ClickException+Abort+generic / 2 UsageError family.** Wrong exit code = real defect.
17. **Errors print to stderr** and name the offending parameter (`BadParameter`/`MissingParameter`).
18. **Abort prints `Aborted!`, exits 1**; prompt-"no"/Ctrl-C/EOF route to Abort.

### Output / platform
19. **`echo` strips ANSI color when not a TTY** (unless forced); routes to stderr only with `err=True`.
20. **CliRunner translates `SystemExit`→`exit_code`, captures exceptions** (catch_exceptions=True); **stderr handling is version-sensitive (8.2 rework).**
21. **Windows console** Unicode wrapping must be correct on console vs redirected pipe/file.

## Highest-Value Bug Surfaces (prioritize)

- **Parameter type conversion edge cases** (range clamp/open bounds, BOOL token sets, Choice canonicalization, Path silent-skip) — richest, most-documented surface.
- **Exit-code correctness** (UsageError=2 vs ClickException=1 vs success=0).
- **Context `obj` propagation and invoke/forward semantics** across nesting.
- **echo color/TTY/stream handling** and **CliRunner version-sensitive stderr behavior**.
- **Windows console** Unicode handling (especially relevant for the Windows benchmark run).
