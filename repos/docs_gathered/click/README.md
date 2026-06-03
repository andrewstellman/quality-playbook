# Click Documentation Collection

Curated documentation for the **Click** command-line-interface framework (Pallets project), gathered to support **Quality Playbook spec-auditing** — comparing actual code behavior against documented intent.

## Purpose

Provides:
1. **Official behavioral specifications** from the Click documentation (parameters, types, arguments, commands, exceptions).
2. **Exit-code and error-handling contracts** (the 0/1/2 contract, the exception hierarchy).
3. **Design opinions** (graceful degradation, `echo` over `print`, composability) that constrain expected behavior.
4. **Version-sensitive edge cases** flagged for the auditor (e.g. the Click 8.2 CliRunner stderr rework).

## Quick Navigation

### Start here
- **INDEX.md** — behavioral overview + the 21 critical specs to verify + highest-value bug surfaces.
- **README.md** — this file.

### Topic documents
1. **01_OVERVIEW.md** — what Click is, design opinions, canonical example.
2. **02_OPTIONS.md** — options (flags, multiple, count, prompt, envvar, callbacks, eager).
3. **03_ARGUMENTS.md** — arguments (nargs/variadic, escape `--`, envvar, required-degradation).
4. **04_PARAMETER_TYPES.md** — types (BOOL, Choice, Int/FloatRange, File, Path, DateTime, custom).
5. **05_COMMANDS_GROUPS_CONTEXT.md** — commands, groups, nesting, Context/`obj`, invoke/forward, chaining.
6. **06_EXCEPTIONS_AND_EXIT_CODES.md** — exception hierarchy + exit codes, Abort, standalone_mode.
7. **07_TESTING_UTILITIES_UNICODE.md** — CliRunner, echo/style, prompts, Windows/Unicode console.

## Source fidelity (important)

- **Directly fetched from the official docs (verbatim-grounded):** 01_OVERVIEW, 03_ARGUMENTS, 04_PARAMETER_TYPES.
- **Synthesized from Click's documented behavior at 8.x** (their pages would not render through the doc fetcher): 02_OPTIONS, 05_COMMANDS_GROUPS_CONTEXT, 06_EXCEPTIONS_AND_EXIT_CODES, 07_TESTING_UTILITIES_UNICODE. These are accurate at the API level; **the spec auditor should cross-check version-specific details against the cloned Click version**, especially the **8.2 CliRunner stderr rework**.

## Sources

1. **Official Click documentation** — https://click.palletsprojects.com/ (8.3.x / 8.4.x stable):
   - Welcome / Why Click? / CLI Design Opinions
   - Parameters, Parameter Types, Options, Option Decorators, Arguments
   - Commands & Groups / Context, Advanced Groups, Complex Applications
   - Help Pages, User Input Prompts, Handling Files, Advanced Patterns
   - Testing, Utilities, Shell Completion
   - **Exception Handling & Exit Codes**, Unicode Support, Windows Console Notes
   - API Reference
2. **Source / releases** — https://github.com/pallets/click, https://pypi.org/project/click/
3. License: BSD-3-Clause.

## Document Format

Each topic document follows: **Source & Date → Overview → Behavioral Specifications → CRITICAL BEHAVIORS (must verify) → Known Issues / Edge Cases → Spec Auditor Focus**.

## Note for the Windows benchmark run

This collection was gathered specifically to support a Windows Mode-A run of the Quality Playbook against Click. Click is pure Python with no compiled dependency, so it builds and tests on Windows with just Python 3.10+ (`pip install -e .` + `pytest`) — TDD red/green logs will generate. The **Windows console / Unicode** behavior (07) and the **CliRunner stderr** version-sensitivity are the most Windows-relevant audit areas.

## Last Updated

2026-05-21
