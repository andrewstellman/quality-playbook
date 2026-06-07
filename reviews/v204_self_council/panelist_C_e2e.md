# Panelist C — End-to-end behavior + verification completeness

Repo `/Users/andrewstellman/Documents/QPB/` at HEAD `c46b5de` on branch `1.5.8`.

## 1. Charter recap

Confirm that `bin/publish_pip.py` and `bin/publish_npm.py` correctly implement the v204 `--publish` XOR `--dry-run` affirmation gate end-to-end: no-arg prints intro and exits 0 without a log file; `--dry-run` runs preflights; `--dry-run --publish` and bare `--skip-tests`/`--skip-stage` exit `EX_USAGE` (64); and the `--publish` static path reaches the live upload helpers exactly as the pre-204 `not args.dry_run` path did.

## 2. Live-invocation tables

### `publish_pip.py`

| # | Command | Expected exit | Actual exit | Notes |
|---|---------|---------------|-------------|-------|
| 1 | `python3 bin/publish_pip.py` | 0 | 0 | Intro printed (banner + "Quality Playbook v1.5.8 · publish_pip" + role + by-Andrew footer). Log-dir count unchanged at 23 — no log file created. |
| 2 | `python3 bin/publish_pip.py --dry-run` | 0 (preflights ran) | 0 | Tree was clean at run time, so preflight 1 PASSED (charter's "halt at preflight 1" prediction was based on operator state that no longer applied). All 8 preflights ran; upload_testpypi reported `[dry-run] Would upload to test PyPI: [...whl, ...tar.gz]`; prod prompt + upload skipped. No live twine.upload invoked. Charter's intent ("preflights run, build attempts, no upload occurs") fully satisfied. |
| 3 | `python3 bin/publish_pip.py --publish --dry-run` | 64 (EX_USAGE) | 64 | stderr: `ERROR: --dry-run and --publish are mutually exclusive. Pick one.` stdout empty. No log file created (gate fires before `_open_log()`). |
| 4 | `python3 bin/publish_pip.py --skip-tests` | 64 (EX_USAGE) | 64 | stderr: `ERROR: must pass --dry-run or --publish.` + helpful 2-line explanation. stdout empty. No log file created. |
| 5 | `python3 bin/publish_pip.py --publish` (NOT executed) | n/a | n/a | Static trace below. |

Log-file accounting after invocations 1–4: only invocation 2 (`--dry-run`) created a log. The XOR / "must pass one" gates at lines 614–629 fire BEFORE `_open_log()` at line 638, so usage errors leave the log directory untouched.

### `publish_npm.py`

| # | Command | Expected exit | Actual exit | Notes |
|---|---------|---------------|-------------|-------|
| 1 | `python3 bin/publish_npm.py` | 0 | 0 | Intro printed (banner + "Quality Playbook v1.5.8 · publish_npm" + role + footer). Log-dir count unchanged — no log file created. |
| 2 | `python3 bin/publish_npm.py --dry-run` | 0 | 0 | All 7 preflights PASSED (clean tree, parity 1.5.8, tag v1.5.8, npm whoami `andrewstellman`, stage bundle, no forbidden in 58 files, `npm pack --dry-run` OK 64 files). Final log line: `[dry-run] Skipping confirmation + npm publish.` No live `npm publish` invoked. |
| 3 | `python3 bin/publish_npm.py --publish --dry-run` | 64 | 64 | stderr: `ERROR: --dry-run and --publish are mutually exclusive. Pick one.` stdout empty. No log file created. |
| 4 | `python3 bin/publish_npm.py --skip-stage` | 64 | 64 | stderr: `ERROR: must pass --dry-run or --publish.` + 2-line explanation referencing `npm pack` / `npm publish --access public`. stdout empty. No log file created. |
| 5 | `python3 bin/publish_npm.py --publish` (NOT executed) | n/a | n/a | Static trace below. |

## 3. Static `--publish` branch trace

### `publish_pip.py` `--publish` path

Starting at `main()` line 601:

1. Line 603: `if not argv_list` — false (we have `--publish`), no early return.
2. Line 606: `parse_args(argv_list)` returns `Namespace(publish=True, dry_run=False, skip_tests=False, skip_build=False, ...)`.
3. Line 614: `if args.dry_run and args.publish` — `False and True` → false, no return.
4. Line 621: `if not args.dry_run and not args.publish` — `True and False` → false, no return.
5. Line 638: `_open_log(version_for_log)` opens `~/.qpb/publish_logs/pip_<v>_<ts>.log`.
6. Line 640: log records `dry_run=False`.
7. Lines 645–707: 8 preflights run unconditionally (skip flags affect specific checks but `args.dry_run=False` means line 706 `if not args.dry_run` evaluates True so a missing twine auth becomes hard-fail, NOT the `(twine auth missing — continuing because --dry-run)` soft-pass).
8. Line 712: `upload_testpypi(repo_root, log_fh, dry_run=args.dry_run)` — called with `dry_run=False`. Inside `upload_testpypi` (line 419), `if dry_run:` is False, so flow drops to lines 427–438 which invokes `python -m twine upload --repository testpypi dist/*` (LIVE).
9. Line 727: `if args.dry_run` — False, no early-return.
10. Line 731: `_confirm_prod()` prompts operator (interactive y/N).
11. Line 736: `upload_prod(repo_root, log_fh, dry_run=args.dry_run)` — called with `dry_run=False`. Inside `upload_prod` (line 442), drops to lines 450–460 which invokes `python -m twine upload dist/*` (LIVE).
12. Line 744: `verify_pypi_version(version, dry_run=args.dry_run)` — runs live `pip index versions` + PyPI JSON API fallback.

**Parity with pre-204**: pre-204 the live path was guarded by `if not args.dry_run:`. Post-204 it is reached when `args.publish=True` AND the XOR/required gates pass — which forces `args.dry_run=False`. So `upload_testpypi(..., dry_run=False)` and `upload_prod(..., dry_run=False)` are reached on identical conditions. No upload helper behavior changed; only the gating condition tightened.

### `publish_npm.py` `--publish` path

Starting at `main()` line 480:

1. Line 482: `if not argv_list` — false, no early return.
2. Line 485: `parse_args(argv_list)` returns `Namespace(publish=True, dry_run=False, skip_stage=False)`.
3. Lines 491, 498: XOR gates — both false, no return.
4. Line 512: log opened, line 514 records `dry_run=False`.
5. Lines 519–580: 7 preflights run. Note line 548 `if args.dry_run and npm is None:` — with `args.dry_run=False`, missing npm hard-fails as it should. Line 570–575 similarly: live mode requires npm or hard-fails.
6. Line 583: `if args.dry_run` — False, no early-return.
7. Line 587: `_confirm_publish(version, files)` prompts operator.
8. Line 592: `npm_publish(repo_root, npm, log_fh, dry_run=args.dry_run)` — called with `dry_run=False`. Inside `npm_publish` (line 361), `if dry_run:` false, drops to lines 370–376 which invokes `npm publish --access public` (LIVE).
9. Line 600: `verify_npm_version(npm, version, dry_run=args.dry_run)` — runs live `npm view quality-playbook version`.

**Parity with pre-204**: identical reasoning. `npm_publish(..., dry_run=False)` and `verify_npm_version(..., dry_run=False)` reach the same live npm-CLI invocations they did pre-204.

## 4. Per-finding narrative for CONCERN / FIX-REQUIRED

None. All 10 live-invocation rows match expected behavior; both static traces reach the live upload helpers on the `--publish` path with `dry_run=False`. Log-file discipline is also correct: usage errors return before `_open_log()`, so the gates don't leave half-written log files behind. The no-arg intro path uses `_print_intro()` and returns 0 before parse_args is even called — exactly the 089x self-describing-output contract.

## 5. Optional NITs

- **NIT (cosmetic):** Both error messages would read marginally cleaner with a trailing usage hint like `Try: python3 bin/publish_pip.py --help`. Current text is already actionable, so this is purely stylistic. Not blocking.
- **NIT (cosmetic):** The `publish_pip.py` "must pass --dry-run or --publish" error has a 3-line stderr (header + two bullet lines); the npm equivalent matches the same shape. Symmetry is good; no change needed.
- **Observation (not a defect):** Charter's prediction that preflight 1 would halt on a non-clean tree turned out to be inverted on the actual disk state at test time (the operator's tree was clean). The dry-run still demonstrated the intended behavior — all 8 preflights ran, upload step skipped — so the verification intent was fully satisfied via a different path through the script.

## 6. Final verdict

```
VERDICT: SHIP
```
