# Testing, Utilities, and Unicode/Windows Console

**Source:** Click documented behavior — Testing + Utilities + Unicode Support + Windows Console Notes pages + API (Click 8.x stable). *(These pages did not render through the doc fetcher; synthesized from Click's documented behavior — cross-check against the cloned source version. The testing API in particular changed in 8.2 — see Known Issues.)* Gathered 2026-05-21.

## Testing (`click.testing.CliRunner`)

- **`CliRunner().invoke(cli, args, input=None, env=None, catch_exceptions=True, **extra)`** runs a command in-process and returns a `Result`.
- **`Result` attributes:** `exit_code` (int), `output` (captured text), `exception` (the caught exception, if any), `exc_info` (traceback tuple), `return_value` (when `standalone_mode=False`). `invoke` runs the command in `standalone_mode` so `SystemExit` is translated into `exit_code`.
- **`input=`** feeds stdin (for prompts); **`env=`** sets environment variables for the run.
- **`catch_exceptions=True`** (default) captures exceptions into `result.exception` rather than raising; set `False` to let them propagate into the test.
- **`runner.isolated_filesystem()`** is a context manager that runs inside a fresh temp working directory (and cleans up).

## Utilities

- **`click.echo(message=None, file=None, nl=True, err=False, color=None)`** — the canonical output function. Routes to stdout (or stderr with `err=True`), handles unicode/bytes, appends a newline by default, and **strips ANSI color codes when the stream is not a TTY** (unless `color` forces it).
- **`click.secho(...)`** — `echo` + styling. **`click.style(text, fg=, bg=, bold=, ...)`** wraps text in ANSI codes.
- **`click.prompt(text, default=, hide_input=, confirmation_prompt=, type=, value_proc=)`** and **`click.confirm(text, default=, abort=)`** — interactive input; `confirm(..., abort=True)` raises `Abort` on "no".
- Other helpers: `click.progressbar()`, `click.echo_via_pager()`, `click.clear()`, `click.getchar()`, `click.pause()`, `click.launch(url)`, `click.edit()`, `click.open_file()` (handles the `-` stdin/stdout sentinel), `click.get_app_dir(name)`, `click.format_filename()`.

## Unicode / Windows Console

- Click forces **UTF-8-aware** text handling and provides a compatibility layer so `echo`/streams behave consistently across platforms and Python builds.
- **Windows console:** historically the native console needed special handling for Unicode; Click wraps stdin/stdout/stderr to make Unicode output work. Behavior depends on whether output is a real console, a redirected pipe, or a file. `click.echo` chooses the right stream and encoding.
- **TTY detection** governs color stripping and prompt behavior — when stdout is redirected, colors are stripped and some interactive behaviors change.

## CRITICAL BEHAVIORS (must verify)

1. **`echo` strips ANSI color when the target is not a TTY** (unless `color=True` forces it) — leaking raw escape codes into a pipe/file is a bug.
2. **`echo` routes to stderr only with `err=True`**; default is stdout. Newline appended unless `nl=False`.
3. **`CliRunner.invoke` translates `SystemExit` into `result.exit_code`** and captures exceptions when `catch_exceptions=True`.
4. **`open_file` / `Path(allow_dash=True)` treat `-` as a standard stream.**
5. **Confirmation with `abort=True` raises `Abort` (exit 1) on "no".**
6. **Windows console wrapping** must produce correct Unicode on a real console and clean (non-wrapped, color-stripped) output when redirected.

## Known Issues / Edge Cases (version-sensitive)

- **CliRunner stderr handling changed in Click 8.2.** In 8.0–8.1, `CliRunner(mix_stderr=True)` (default) merged stderr into `result.output`; `mix_stderr=False` separated `result.stdout`/`result.stderr`. **In 8.2 the runner was reworked: `mix_stderr` was removed and stdout/stderr are separated, with `result.output`/`result.stderr` semantics adjusted.** A test (or the runner itself) that assumes the old merged behavior is version-sensitive — verify against the cloned Click version.
- Color/TTY behavior under capture differs from a real terminal (CliRunner is not a TTY), which can mask or expose color-stripping logic.
- Windows console encoding edge cases (non-UTF-8 code pages, redirected vs console) are a recurring bug area.

## Spec Auditor Focus

- Verify color stripping ↔ TTY detection in `echo`/`secho`.
- Verify stream selection (stdout vs stderr) and newline handling.
- Verify the CliRunner result contract for the **specific Click version** (especially the 8.2 stderr rework).
- Verify `-` standard-stream handling in `open_file`/`Path`.
- Verify Windows console Unicode wrapping across console/pipe/file targets.
