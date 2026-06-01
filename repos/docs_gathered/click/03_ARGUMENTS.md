# Arguments

**Source:** https://click.palletsprojects.com/en/stable/arguments/ (Click 8.4.x stable). Gathered 2026-05-21.

## Overview

Arguments are **positional** parameters — a limited form of options that can take an arbitrary number of inputs and are documented manually (the help page does not auto-document them). Common kwargs: `default`, `nargs`, `type`, `required`, `envvar`.

## Behavioral Specifications

- **Minimal argument** takes one string: `@click.argument('filename')`. Default state: **required, no default, type `str`**.
- **Type inference:** if no `type` is given, the type of the `default` value is used; if there is no default, the type is `STRING`.
- **`nargs`:** any positive integer, or `-1`. `nargs=-1` makes it **variadic** (arbitrary count), can be used **only once** per command, and the values are **packed as a tuple** passed to the function. A variadic argument with no input yields an empty tuple.
- **Required degradation:** arguments can be made required with `required=True`, but Click **recommends against it** — CLI tools should "gracefully degrade into no-ops" (often invoked with wildcards that may be empty). By default a variadic argument is not required.
- **Escape sequences (`--`):** to pass argument values that look like options (e.g. a file named `-foo.txt`), pass the `--` separator first; after `--`, everything is treated as an argument. This is standard POSIX behavior. Alternatively, `@click.command(context_settings={"ignore_unknown_options": True})` skips unknown-option checking so option-looking values pass through as arguments.
- **Environment variables:** arguments read env vars only via an **explicitly named** `envvar=` (single name or list of names). With a list, the first set variable wins. (Contrast with options, which can auto-derive env var names with a prefix.)

## CRITICAL BEHAVIORS (must verify)

1. **`nargs=-1` packs into a tuple** and may appear at most once; an empty variadic yields `()`, not `None` or error.
2. **Type inference order:** explicit `type` > type of `default` > `STRING`.
3. **`--` terminates option parsing**; everything after is positional, even option-looking tokens.
4. **`ignore_unknown_options` lets option-looking tokens be consumed as arguments** without `--`.
5. **Arguments read env vars only from explicitly-named `envvar`** (no auto-prefix derivation).

## Known Issues / Edge Cases

- Mixing a required fixed-nargs argument before a variadic (`nargs=-1`) one: the fixed ones bind first, the variadic absorbs the rest.
- A variadic argument greedily consumes remaining tokens — interactions with trailing options or subcommands are a common source of surprising parses.

## Spec Auditor Focus

- Is the variadic-tuple contract honored (empty → `()`)?
- Is type inference exactly `explicit > default-type > STRING`?
- Are `--` and `ignore_unknown_options` handled per POSIX expectations?
- Does envvar resolution for arguments require an explicit name (and pick the first set name from a list)?
