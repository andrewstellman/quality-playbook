# Panelist A — Root-Cause Correctness + Audit Completeness

Reviewer role-lock: I am Panelist A, a REVIEWER for QPB instruction 203
self-Council Protocol 1. I do not amend code. I produce a verdict.

## 1. Charter recap

Confirm that the prepack-stdout-pollution fix in
`bin/build_channel_package.py` is complete (progress messages routed to
stderr, `import sys` present, inline stdout-discipline comment present,
no other unaudited stdout prints) and verify by live observation that
`npm pack --dry-run --json` now emits parseable JSON on stdout.

## 2. Print-call audit table

`bin/build_channel_package.py` enumerated with
`grep -n "print(" bin/build_channel_package.py`:

| Line | Content (abbrev.) | Classification | stderr-routed? |
|------|--------------------|----------------|----------------|
| 541  | `print(_purpose.get_version())` (inside `if args.version:` block) | STDOUT-INTENDED — `--version` output is the script's consumer-facing payload; downstream tooling reads it from stdout. Explicitly carved out in the inline discipline comment (lines 544–548). | N/A (correct on stdout) |
| 554  | `print(f"build_channel_package: stamped {path}: {before} -> {after}", file=sys.stderr)` (stamp-manifest progress, in `for path, before, after in changed:` loop) | STDERR-INTENDED — diagnostic progress. | YES — explicit `file=sys.stderr` on line 557. |
| 564  | `print(f"build_channel_package: staged {len(staged)} files into {args.dest}", file=sys.stderr)` (the original offending message from instruction 202's npm-pack failure) | STDERR-INTENDED — diagnostic progress. THE ROOT-CAUSE LINE. | YES — explicit `file=sys.stderr` on line 568. |

No other `print()` calls exist in `bin/build_channel_package.py`.

Cross-audit of indirect stdout writes from `main()`:

- `_purpose.print_command_intro(...)` is called on the BARE-no-args path
  (line 465) only. Defaults to `sys.stdout` (per `_purpose.py:317–318`).
  This is correct: the no-args path is the interactive
  discovery/purpose-banner path and never runs from a prepack hook
  (prepack runs `--stage`, which takes the args-present branch).
- `_purpose.print_help_banner(argv)` is called on the args-present path
  (line 484) but only emits when `-h`/`--help` is in argv (per
  `_purpose.py:349`). Prepack passes `--stage`, so this short-circuits.
  Also stdout-intended (it's the consumer-facing `--help` header).
- The `_assert_mandatory_staged_members` and `enumerate_bundle`
  RuntimeError paths use raised exceptions, not `print()`. Tracebacks go
  to stderr by default. Correct.

Conclusion: every `print()` whose code path can be reached on the
prepack `--stage` invocation now routes to stderr. The only stdout
writer that can fire on `--stage` is argparse's own error path (e.g.,
`--unknown-flag`), which is acceptable and not in scope for instruction
203.

## 3. `import sys` confirmation

`grep -n "import sys" bin/build_channel_package.py` →
`40:import sys`

Confirmed: top-of-module, on its own line, alphabetically ordered with
`shutil` (39) above and `from pathlib import Path` (41) below. Also
used elsewhere in the module (line 65 `sys.modules[...]`, 118
`sys.modules[...]`, 454 `sys.argv[1:]`, 582 `sys.exit(main())`), so the
import was already load-bearing pre-203 — the 203 fix doesn't depend on
a fresh import being added correctly.

## 4. Inline comment confirmation

Lines 544–548 of `bin/build_channel_package.py`:

```python
    # Stdout discipline (instruction 203): nothing on stdout. All
    # progress/diagnostic messages go to sys.stderr so consumers (e.g.,
    # `npm pack --dry-run --json` via the prepack script) can parse our
    # stdout cleanly. `--version` is the only exception — that output
    # IS intended for stdout consumers.
```

The comment:

- Explicitly attributes itself to instruction 203 (audit traceability).
- States the invariant ("nothing on stdout").
- Cites the concrete consumer (`npm pack --dry-run --json`) and the
  delivery mechanism (the prepack script).
- Carves out the legitimate `--version` exception, matching the line
  541 print.

Comment is correctly placed inside `main()` immediately above the first
stamping-progress print, where any future contributor adding a new
print would see it before adding the wrong default. Good placement.

## 5. Live verification output

Command, executed verbatim per charter:

```
$ cd ~/Documents/QPB && npm pack --dry-run --json 2>/dev/null | head -3
[
  {
    "id": "quality-playbook@1.5.8",
```

First line is `[` — the JSON array opener. `npm pack --dry-run --json`
stdout is now pure JSON. The instruction-202 failure mode (prepack
progress line leaking into npm's stdout, breaking
`json.loads()`) is gone.

`2>/dev/null` correctly suppresses the progress message — confirming
that the progress message IS now on stderr (where it gets redirected to
`/dev/null`), not on stdout (where it would survive the redirection and
prefix the JSON).

## 6. Per-finding narrative for any CONCERN or FIX-REQUIRED items

None. All four audit items pass on direct observation, and the live
`npm pack` test produces parseable JSON.

## 7. Optional NITs

- **NIT-1 (not blocking).** The inline comment at 544–548 lives inside
  `main()` after `--version` handling but before manifest stamping. A
  future contributor adding a new top-level helper that prints (outside
  `main()`) would not see this comment. A short note at the module
  docstring (lines 1–33) referencing the stdout discipline would
  broaden the audit's reach. Not required for this instruction —
  the inline comment plus the npm-pack regression test
  (`test_npm_pack_dry_run_stdout_is_pure_json` per the commit message)
  already gives belt-and-suspenders coverage.
- **NIT-2 (not blocking).** Line 564 wraps the f-string across two
  arguments of `print()` — readable, but a small reformatting nit:
  consolidating into one f-string would put the `file=sys.stderr`
  kwarg unambiguously at the top of the call. Style only.
- **NIT-3 (not blocking).** `_purpose.print_command_intro` defaults to
  stdout. Today this is safe because no-args is not on any prepack
  path. If a future channel manifest adds `npm pack`-style hooks that
  invoke other QPB scripts bare, those scripts would re-introduce the
  pollution class. Not in scope for 203; flag for future
  surface-by-surface audit if a new channel hook lands.

## 8. Final verdict

```
VERDICT: SHIP
```
