# Commands, Groups, and Context

**Source:** Click documented behavior — https://click.palletsprojects.com/en/stable/commands-and-groups/ + Advanced Groups + Complex Applications + API reference (Click 8.x stable). *(These pages did not render through the doc fetcher; synthesized from Click's documented behavior — cross-check against the cloned source version.)* Gathered 2026-05-21.

## Overview

`@click.command()` wraps a function into a `Command`. `@click.group()` makes a `Group` (a `Command` that dispatches to subcommands). Groups nest arbitrarily. Shared state flows through the `Context` object.

## Behavioral Specifications

- **Commands & groups:** `@click.group()` creates a dispatcher; `@group.command()` or `group.add_command(cmd, name=...)` registers subcommands. Invoking the group runs group-level logic, then dispatches to the named subcommand.
- **Context (`ctx`):** every command runs with a `Context`. `@click.pass_context` injects `ctx` as the first arg. `ctx.obj` is a free-form slot for passing application state down the command tree; `@click.make_pass_decorator(Type)` / `@click.pass_obj` retrieve it. A child context's `obj` defaults to the parent's unless set.
- **`ctx.invoke(other_cmd, **params)`** calls another command's *callback* with given params (defaults filled in). **`ctx.forward(other_cmd)`** invokes it forwarding the *current* command's params. Neither re-parses the command line.
- **`invoke_without_command=True`** on a group runs the group callback even when no subcommand is given (otherwise the group shows help/errors). Check `ctx.invoked_subcommand` to branch.
- **Chaining (`chain=True`):** a group can invoke multiple subcommands in one invocation, in order. `result_callback()` (a.k.a. `resultcallback` pre-8.0) receives the list of subcommand return values for post-processing.
- **Lazy subcommands:** groups support runtime lazy loading of subcommands (one of Click's three headline features) via a custom `Group.get_command`/`list_commands`.
- **`no_args_is_help`:** commands/groups can show help instead of erroring when invoked with no args.
- **Help & version:** `--help` is added automatically (eager, exits 0). `@click.version_option()` adds an eager `--version` that prints and exits 0.
- **Return values & `standalone_mode`:** normally a command runs in `standalone_mode=True` — Click handles exceptions and calls `sys.exit`. Calling a command with `standalone_mode=False` returns the callback's return value and lets exceptions propagate (used for embedding/testing).
- **Token normalization:** a `Context.token_normalize_func` can fold subcommand/option spellings (e.g. case-insensitive command names).

## CRITICAL BEHAVIORS (must verify)

1. **`ctx.obj` inheritance:** a child context inherits the parent's `obj` unless explicitly replaced — losing or shadowing it across nesting is a bug.
2. **`invoke` vs `forward`:** `invoke` uses supplied/default params; `forward` carries the current command's params. They call the callback, not the parser.
3. **`invoke_without_command` + `invoked_subcommand`:** group callback must branch correctly when no subcommand is present.
4. **`chain=True` ordering + `result_callback` receives the ordered list** of subcommand results.
5. **Help/version are eager and exit 0**; group dispatch must not run the subcommand when an eager short-circuit fired.
6. **`standalone_mode=False` returns the value and propagates exceptions** instead of exiting — embedding code depends on this.

## Known Issues / Edge Cases

- Pre-8.0 `resultcallback` was renamed `result_callback` — version-sensitive.
- Group-level options vs subcommand options: a group option consumed before the subcommand name vs after is a classic parsing-order pitfall.
- A group with required group-level options + `invoke_without_command`: the required options still apply.

## Spec Auditor Focus

- Verify `obj` propagation through `make_pass_decorator`/`pass_obj` across ≥2 nesting levels.
- Verify `invoke`/`forward` parameter semantics and that they don't re-parse argv.
- Verify chaining order + `result_callback` payload.
- Verify eager short-circuit (help/version) prevents subcommand execution and exits 0.
- Verify `standalone_mode=False` return/propagation contract.
