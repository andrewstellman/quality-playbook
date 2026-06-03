# Parameter Types

**Source:** https://click.palletsprojects.com/en/stable/parameter-types/ + API reference (Click 8.3.x/8.4.x stable). Gathered 2026-05-21.

## Overview

Types are available to both options and arguments via `type=`. A type's job is to convert the incoming string (from the command line or environment) into the correct Python value, and to validate it. Values from user input or the command line are always strings, but **default values and Python-supplied arguments may already be the correct type** — a type's `convert()` must tolerate already-converted values and pass them through.

## Built-in Types — Behavioral Specifications

- **`str` / `click.STRING`** — default type; unicode strings.
- **`int` / `click.INT`** — accepts integers only.
- **`float` / `click.FLOAT`** — accepts floating-point values only.
- **`bool` / `click.BOOL`** — automatically used for boolean flags. **String→bool conversion is exact:** `"1"`, `"true"`, `"t"`, `"yes"`, `"y"`, `"on"` → `True`; `"0"`, `"false"`, `"f"`, `"no"`, `"n"`, `"off"` → `False`. Anything else is an error.
- **`click.UUID`** — accepts UUID values; represented as `uuid.UUID`. Not auto-guessed.
- **`click.Choice(choices, case_sensitive=True)`** — checks a value against a fixed set. **The resulting value is always one of the originally passed choices** (since 7.1), even when `case_sensitive=False` or token normalization makes the command-line spelling differ. Any iterable is accepted (since 8.2.0); if an `Enum` is passed, the enum member *names* are the valid choices. Works with `multiple=True` (a `default` must then be a list/tuple of valid choices). Choices must be unique after normalization.
- **`click.IntRange(min=None, max=None, min_open=False, max_open=False, clamp=False)`** / **`click.FloatRange(...)`** — restrict INT/FLOAT to a range. If `min` or `max` is omitted, that side is **unbounded**. Both bounds are **closed by default** (the boundary value is included); `min_open`/`max_open` exclude the boundary. **`clamp=True`** sets an out-of-range value to the nearest boundary instead of failing (e.g. range `0,5` returns `5` for `10`, `0` for `-1`). **FloatRange `clamp` is only allowed if both bounds are closed.**
- **`click.DateTime(formats=None)`** — converts date strings to `datetime`. Default formats (tried in order, first success wins): `'%Y-%m-%d'`, `'%Y-%m-%dT%H:%M:%S'`, `'%Y-%m-%d %H:%M:%S'`. Processed via `datetime.strptime`. Pass only a list/tuple of formats (other iterables give surprising results).
- **`click.File(mode='r', encoding=None, errors='strict', lazy=None, atomic=False)`** — declares a file parameter. **The file is automatically closed when the context tears down** (after the command finishes). The special value `-` means stdin or stdout depending on mode. `lazy` defers opening until first IO (default: non-lazy for stdin/stdout and read mode, lazy otherwise); a lazily-opened read file is still opened temporarily for validation. `atomic=True` writes to a temp file in the same folder and moves it over the target on completion.
- **`click.Path(exists=False, file_okay=True, dir_okay=True, writable=False, readable=True, executable=False, resolve_path=False, allow_dash=False, path_type=None)`** — like `File` but returns the filename, not an open file. **If `exists=False` and the path does not exist, all further checks are silently skipped.** `resolve_path` makes the value absolute and resolves symlinks (but does **not** expand `~` — that's the shell's job). `allow_dash` permits a single `-` (indicating a standard stream, not opened — use `open_file()` to handle it). `path_type` converts the result (e.g. `pathlib.Path`).

## Custom Types

Subclass `click.ParamType` and override `convert(self, value, param, ctx)`. Call `self.fail(message, param, ctx)` on failure. **`param` and `ctx` may be `None`** in some cases (e.g. prompts) — convert() must not assume they are present. The custom type should check at the top whether the value is already the correct type and pass it through (to support default/Python-supplied values). A plain function that raises `ValueError` is also accepted as a type, though discouraged.

## CRITICAL BEHAVIORS (must verify)

1. **Choice returns the original choice object/string**, never the user's command-line spelling, after case-insensitive or normalized matching.
2. **BOOL string conversion uses the exact documented token sets** — no other strings convert; unknown tokens error.
3. **Range bounds default to closed**; `clamp` silently substitutes the boundary (no error) — a clamp on the wrong side or with open bounds is a bug. **FloatRange clamp requires closed bounds.**
4. **File parameters auto-close on context teardown** — a leaked/early-closed handle is a bug.
5. **Path with `exists=False` silently skips all checks when the path is absent** — readable/writable/file_okay checks must not fire in that case.
6. **`-` maps to stdin/stdout for `File`**, and is a non-opened sentinel for `Path(allow_dash=True)`.
7. **Custom `convert()` must handle already-converted values and `param=None`/`ctx=None`.**

## Spec Auditor Focus

- Does each type's `convert()` pass through already-correct values (idempotent on non-strings)?
- Are range boundary conditions (open vs closed, clamp direction) exactly as documented?
- Does Choice return the canonical choice, and is normalization/uniqueness enforced?
- Does File honor lazy/atomic semantics and close on teardown? Does Path skip checks correctly when `exists=False`?
- Are error messages produced via `fail()`/`BadParameter` (not raw exceptions leaking to the user)?
