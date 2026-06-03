# Options

**Source:** Click documented behavior — https://click.palletsprojects.com/en/stable/options/ + API reference (Click 8.x stable). *(The options page did not render through the doc fetcher; this file is synthesized from Click's documented option behavior and should be cross-checked against the cloned source version.)* Gathered 2026-05-21.

## Overview

Options are optional named parameters (recommended for everything except subcommands, URLs, or files). They are fully documented on the help page and support automatic prompting, environment-variable fallback, flags, and callbacks. Default is **one value (`nargs=1`)**.

## Behavioral Specifications

- **Naming:** an option's Python parameter name is derived from the longest declared name (e.g. `--max-count` → `max_count`). Multiple declared names (`-c`, `--count`) bind to one parameter. A name may be split into the public flag and the internal name (e.g. `'--name', 'username'`).
- **Type & default:** type is inferred from `default` if `type` is not given; otherwise `STRING`. `show_default=True` displays the default in help.
- **Flags (`is_flag=True`):** boolean switch. A **slash flag pair** `'--shout/--no-shout'` creates an on/off pair with a single parameter. `flag_value=` allows multiple options writing distinct values to one parameter (feature switches).
- **`multiple=True`:** the option may be repeated; values are collected into a **tuple** (empty tuple if never given).
- **`count=True`:** repeated flag counts occurrences (e.g. `-vvv` → `3`); value is an int (default 0).
- **`required=True`:** option must be provided (else a UsageError).
- **`prompt=`:** if the option is not supplied, Click prompts interactively. `hide_input=True` (passwords), `confirmation_prompt=True` (ask twice and compare). `password_option` is the shortcut combining hide_input + confirmation.
- **`envvar=`:** fall back to a named environment variable (or list). With `auto_envvar_prefix` set on the context, options auto-derive `PREFIX_OPTIONNAME`. **`multiple` + envvar splits on whitespace; `nargs>1` + envvar also splits.**
- **Callbacks (`callback=`):** `f(ctx, param, value)` runs after conversion to further process/validate; its return value becomes the option value. **`is_eager=True`** makes the option process before non-eager ones (used by `--version`, `--help`).
- **`expose_value=False`:** the option is processed (callback runs) but not passed to the command function (used for eager side-effect options).
- **`nargs=N` (N>1):** collects exactly N values into a tuple. `nargs=-1` is **not** allowed for options (variadic is arguments-only).
- **Boolean default behavior:** an `is_flag` option defaults to `False` unless a default is set; a `/`-pair defaults to the second (off) value unless specified.

## CRITICAL BEHAVIORS (must verify)

1. **Default `nargs` is 1; options cannot be variadic (`nargs=-1`)** — that's arguments-only.
2. **`multiple=True` always yields a tuple** (empty `()` if absent), never `None`.
3. **`count=True` yields an int starting at 0.**
4. **Eager options (`is_eager`) process before others**; `--help`/`--version` short-circuit and exit 0.
5. **`expose_value=False` options still run their callback but are not passed to the command.**
6. **Env-var fallback:** named `envvar`, or `auto_envvar_prefix`-derived name; `multiple`/`nargs>1` split env values on whitespace.
7. **Prompt fallback fires only when the option is missing**, and `confirmation_prompt` must compare both entries.

## Known Issues / Edge Cases

- Slash-flag pairs (`--x/--no-x`) and `is_flag` interactions: the parameter name and default come from the first/second name respectively — easy to get the default polarity wrong.
- `flag_value` options writing to a shared parameter: last-one-wins ordering and default selection are subtle.
- Callback ordering depends on `is_eager`; a non-eager validation callback that assumes an eager option already ran can misfire.

## Spec Auditor Focus

- Verify tuple/int/bool defaults for `multiple`/`count`/`is_flag` (empty-but-not-None contract).
- Verify eager processing order and that help/version short-circuit with exit 0.
- Verify env-var resolution (named + auto-prefix) and the whitespace-split rule for multi-valued options.
- Verify prompt/hide_input/confirmation semantics fire only on missing input.
- Verify callbacks receive `(ctx, param, value)` and their return value replaces the value.
