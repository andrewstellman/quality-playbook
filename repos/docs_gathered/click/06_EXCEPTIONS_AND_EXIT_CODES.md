# Exception Handling and Exit Codes

**Source:** Click documented behavior — https://click.palletsprojects.com/en/stable/exceptions/ + API (exceptions) (Click 8.x stable). *(Page did not render through the doc fetcher; synthesized from Click's documented exception/exit-code behavior — cross-check against the cloned source version.)* Gathered 2026-05-21.

## Overview

Click defines an exception hierarchy whose members carry a documented **exit code** and a `show()` method that formats the error to stderr. In standalone mode, Click catches these, prints them, and calls `sys.exit` with the right code.

## Behavioral Specifications (exit codes)

- **Success → exit 0.**
- **`ClickException` (base) → exit code 1.** Has `exit_code = 1` and `show()` printing `Error: <message>` to stderr.
- **`UsageError` → exit code 2.** Raised for command-line misuse; `show()` prints the usage line + `Try '<cmd> --help' for help.` + `Error: <message>`. Subclasses:
  - **`BadParameter`** — invalid parameter value; message names the parameter (`Invalid value for '<param>': ...`).
  - **`MissingParameter`** — a required parameter was not provided.
  - **`NoSuchOption`** — an unknown option was passed (offers "did you mean" suggestions when close).
  - **`BadOptionUsage` / `BadArgumentUsage`** — option/argument used incorrectly.
- **`Abort` → exit code 1**, prints `Aborted!` to stderr. Raised by `ctx.abort()`, by confirmation prompts answered "no" / `abort=True`, and by Ctrl-C/EOF at a prompt.
- **`Exit(code)`** — `ctx.exit(code)` raises this to exit with an explicit code (default 0).
- **Unhandled non-Click exceptions** propagate (Python prints a traceback, exit code 1 via the interpreter) — unless caught by embedding code.

## Behavioral Specifications (control)

- **`standalone_mode`:** default `True` — Click catches `ClickException`/`Abort`, prints, and exits. With `standalone_mode=False`, these propagate to the caller instead (used by `CliRunner` and embedding).
- **`self.fail(message, param, ctx)`** in a `ParamType.convert()` raises `BadParameter` with the correct framing — custom types must use it rather than letting `ValueError` leak.
- **`ctx.fail(message)`** raises a `UsageError`.

## CRITICAL BEHAVIORS (must verify)

1. **Exit-code contract:** 0 success, **1** for `ClickException`/`Abort`/generic, **2** for `UsageError` family. A command that returns the wrong code (e.g. exits 1 on a usage error, or 0 on failure) is a real defect.
2. **Errors print to stderr, not stdout** (so piped stdout stays clean).
3. **`Abort` prints `Aborted!` and exits 1**; prompt "no"/Ctrl-C/EOF routes to `Abort`.
4. **`BadParameter`/`MissingParameter` name the offending parameter** in the message.
5. **`standalone_mode=False` propagates exceptions** instead of exiting — embedding/test code relies on this.
6. **Custom type failures go through `fail()` → `BadParameter`**, never a raw `ValueError` reaching the user.

## Known Issues / Edge Cases

- Distinguishing `UsageError` (exit 2) from application `ClickException` (exit 1) is the most common exit-code bug class.
- "Did you mean" suggestions for `NoSuchOption` depend on edit-distance thresholds — over/under-suggesting is a subtle defect.
- Ctrl-C handling differs between a running command (KeyboardInterrupt) and a prompt (`Abort`).

## Spec Auditor Focus

- Trace every error path to its exit code and confirm it matches the 0/1/2 contract.
- Confirm error text goes to stderr and names the parameter where applicable.
- Confirm prompts/confirmations route refusal and Ctrl-C/EOF to `Abort` (exit 1, "Aborted!").
- Confirm custom types fail via `fail()` and that `standalone_mode=False` propagation holds.
