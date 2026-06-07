# Panelist A — CLI + Pass-Through Correctness (Instruction 205)

Repo: `/Users/andrewstellman/Documents/QPB/` @ `8625474` (branch `1.5.8`, unpushed).
Files reviewed: `bin/publish_npm.py`, `bin/tests/test_publish_npm.py`, `bin/publish_pip.py` (negative check).

## 1. Charter recap

Verify that `--otp` is wired into `publish_npm.py` correctly: optional CLI flag, conditional pass-through to `npm publish` only when non-empty, `getpass.getpass` for interactive entry, prompt fires after the y/N confirmation and just before `npm publish`, and docstring + usage_hint mention `--otp`.

## 2. Per-checklist-item table

| # | Charter item | Location | Status | Notes |
|---|---|---|---|---|
| 1 | `--otp` added as optional argument with default `None` | `bin/publish_npm.py:486-496` | PASS | `type=str, default=None, metavar="CODE"`. Help text describes 6-digit OTP + interactive fallback. Test `test_otp_default_is_none` (line 517) pins default; `test_otp_flag_parses` (line 513) pins parsing. |
| 2 | npm publish subprocess conditionally includes `["--otp", otp]` only when non-empty (None / "" both skip) | `bin/publish_npm.py:385-387` | PASS | `cmd = [npm, "publish", "--access", "public"]; if otp: cmd.extend(["--otp", otp])`. Python truthiness handles both `None` and `""` → falsy → skipped. Test `test_npm_publish_omits_otp_when_empty` (line 534) explicitly covers both `None` and `""`; `test_npm_publish_includes_otp_when_provided` (line 521) covers the truthy branch. |
| 3 | `getpass.getpass()` used for interactive prompt (not `input()`, no echo) | `bin/publish_npm.py:69` (import), `bin/publish_npm.py:650` (call site) | PASS | `import getpass` at line 69; `getpass.getpass("Enter npm 2FA OTP code (6 digits; leave empty if no 2FA on account): ")` at line 650, wrapped in `try/except EOFError` → `otp = ""` on EOF (correctly treats EOF as "no 2FA"). `.strip()` applied. |
| 4 | Prompt fires AFTER y/N confirmation and just before `npm publish` (OTP expiry window) | `bin/publish_npm.py:638-658` | PASS | Order: `_confirm_publish(...)` at line 638 → early-return on decline → CLI override resolved at line 647 → `getpass.getpass` at line 650 (only if `args.otp is None`) → `run_npm_publish(...)` at line 658. Comment at 642-646 explicitly documents the "~30s OTP-expiry window" rationale. No earlier OTP read in `main()` or in preflights 1-7. |
| 5 | Docstring + usage_hint mention `--otp` | `bin/publish_npm.py:22` (docstring usage block), `bin/publish_npm.py:30-36` (docstring 2FA paragraph), `bin/publish_npm.py:526` (`_print_intro` usage_hint) | PASS | Module docstring shows `python3 bin/publish_npm.py --publish --otp 123456` plus a 6-line paragraph covering the interactive prompt, getpass no-echo, log redaction, and the token-delete-after-use rationale. `_print_intro()` `usage_hint` emits `python3 bin/publish_npm.py --publish [--otp <code>]`. |

Out-of-scope sanity check: `git diff 09de4b6..8625474 --stat` shows only `bin/publish_npm.py` and `bin/tests/test_publish_npm.py` changed — `bin/publish_pip.py` is NOT touched, matching § Out of scope.

## 3. Live verification — `--help` excerpt

```
$ python3 bin/publish_npm.py --help
usage: publish_npm [-h] [--dry-run] [--publish] [--skip-stage] [--otp CODE]
...
  --otp CODE    6-digit npm 2FA OTP code. Required if your npm account has 2FA
                enabled. If not provided on the command line and --publish is
                set, the script prompts for it interactively (via getpass, no
                echo) immediately before calling `npm publish`.
```

`--otp CODE` appears in the usage line and gets a clear help entry explicitly documenting the interactive-fallback semantics.

Test run: `python3 -m pytest bin/tests/test_publish_npm.py -v` → 44 passed (includes 5-method `OtpHandlingTests`). Full publish suite (`bin/tests/`) → 3178 passed, 8 skipped.

Mutation check (paraphrased from commit message): comment out the `if otp: cmd.extend([...])` block; `test_npm_publish_includes_otp_when_provided` fails; restore via `shutil.copy2`; purge scoped `bin/__pycache__`; re-run passes. This matches the mutation-discipline pattern in `[[feedback_mutation_bite_pycache]]`.

## 4. Per-finding narrative

No CONCERN or FIX-REQUIRED findings on the CLI + pass-through axis.

The five charter items are each backed by a dedicated test (or two), the conditional `if otp:` line correctly handles both `None` and empty-string skip per Python truthiness, and the prompt-timing intent is both implemented and commented. The log-redaction code at lines 388-394 is a bonus that goes beyond the charter — it scans the cmd list for `--otp` and replaces the subsequent token with `<REDACTED>` before writing to the log. `test_log_does_not_contain_raw_otp` (line 554) pins the property: raw OTP must not appear in the log; `<REDACTED>` must.

The backwards-compat shim `npm_publish(repo_root, npm, log_fh, *, dry_run, otp=None)` at line 406 preserves the old call-site contract (only `dry_run=` was previously kw-only) while delegating live invocations to `run_npm_publish`. The `dry_run=True` branch returns a "would run" message without forwarding the OTP, which is correct: a dry-run that prints the OTP would defeat the whole redaction design.

`main()` only invokes `run_npm_publish` (live path) — never the `npm_publish` shim — so the OTP path through `main()` is single-purpose and easy to audit.

## 5. Optional NITs

- NIT (style, no fix required): Line 658 passes `otp or None`. After the getpass branch sets `otp = ""` on EOF (or strips to ""), the trailing `or None` collapses falsy values to `None` before calling `run_npm_publish`. This is harmless because `run_npm_publish` itself uses `if otp:` (truthy-check), so passing `""` vs `None` yields the same behavior. The belt-and-suspenders is fine, but a reader unfamiliar with the truthy-check might wonder whether `""` and `None` differ.

- NIT (UX, no fix required): The interactive prompt accepts an empty response as "no 2FA". An operator who momentarily forgets their OTP and hits Enter would then get an E403 from npm and have to re-run the entire 7-preflight + confirmation flow. Not a defect — the design intentionally supports non-2FA accounts — but a future enhancement could warn ("empty OTP entered; press y to proceed without --otp, or n to abort") to avoid wasted preflight cycles. Out of scope for instruction 205.

- NIT (docstring polish, no fix required): The module docstring 2FA paragraph at line 33 says the prompt fires "immediately after the y/N confirmation"; the inline comment at line 643 says "AFTER the y/N confirmation and immediately before `npm publish`". Both are accurate; the inline phrasing is slightly more precise. Could be aligned in a future polish pass.

## 6. Verdict

```
VERDICT: SHIP
```
