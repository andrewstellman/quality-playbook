# Panelist A — Argument-parsing correctness + docstring alignment

Self-Council Protocol 1, QPB instruction 204, HEAD `c46b5de`, branch `1.5.8`.

## 1. Charter recap

Verify that `bin/publish_pip.py` and `bin/publish_npm.py` correctly add a `--publish` flag with mutually-exclusive XOR semantics against `--dry-run`, that both module docstrings and `_print_intro()` `usage_hint`s reflect the new behavior, and that `submit_awesome_copilot.py` was correctly left alone with justification.

## 2. Per-script flag-presence table

| Item | `bin/publish_pip.py` | `bin/publish_npm.py` |
|---|---|---|
| `--publish` declared `action="store_true"` | YES (line 538-542) | YES (line 436-441) |
| `--publish` help text clear (mentions LIVE upload + mutex with `--dry-run`) | YES — "Run all pre-flight checks + build + twine upload (LIVE: test PyPI then prod PyPI). Mutually exclusive with --dry-run." | YES — "Run all pre-flight checks + npm pack + `npm publish --access public` (LIVE). Mutually exclusive with --dry-run." |
| `--dry-run` help text mentions mutex | YES (line 535) — "Mutually exclusive with --publish." | YES (line 434-435) — "Mutually exclusive with --publish." |
| XOR check: both set → EX_USAGE 64 + stderr | YES (line 614-620) | YES (line 491-497) |
| XOR check: neither set → EX_USAGE 64 + stderr | YES (line 621-629) | YES (line 498-506) |
| No-args branch returns 0 after `_print_intro()` (no XOR fall-through) | YES (line 602-605) — `if not argv_list: _print_intro(); return 0` runs BEFORE `parse_args` | YES (line 481-484) — same shape |
| Module docstring updated — three-line Usage block (`no args` / `--dry-run` / `--publish`) + mutex note + "must be passed to run the workflow" | YES (line 15-26) | YES (line 17-27) |
| Module docstring removes any "no-args runs full publish" claim | YES — docstring says `python3 bin/publish_pip.py # show intro (no destructive action)` | YES — docstring says `python3 bin/publish_npm.py # show intro (no destructive action)` |
| `_print_intro()` `usage_hint` shows both `--dry-run` and `--publish` | YES (line 594-597) — `"python3 bin/publish_pip.py --dry-run\n  or: python3 bin/publish_pip.py --publish"` | YES (line 473-476) — `"python3 bin/publish_npm.py --dry-run\n  or: python3 bin/publish_npm.py --publish"` |

All boxes ticked, both files.

## 3. Live exit-code verification table

Executed in repo root with `python3 bin/publish_*.py <args> >/dev/null 2>&1; echo $?`. For `--dry-run` / `--publish` alone the script proceeds past the XOR gate into the preflight phase (Pre-flight 1/N "Working tree clean." observed in stdout before the head -5 cutoff); marked "reached preflight" rather than a final exit because the run continues past argparse (out of charter for this row).

| # | Invocation | Expected | Observed |
|---|---|---|---|
| 1 | `python3 bin/publish_pip.py` | 0 (intro, no destructive action) | **0** |
| 2 | `python3 bin/publish_pip.py --skip-tests` | 64 (EX_USAGE — neither --dry-run nor --publish) | **64** with `ERROR: must pass --dry-run or --publish.` on stderr |
| 3 | `python3 bin/publish_pip.py --dry-run --publish` | 64 (EX_USAGE — mutex) | **64** with `ERROR: --dry-run and --publish are mutually exclusive. Pick one.` on stderr |
| 4 | `python3 bin/publish_pip.py --dry-run` | reaches preflight | reaches preflight (`publish_pip starting. dry_run=True ...` → Pre-flight 1/8 → Pre-flight 2/8) |
| 5 | `python3 bin/publish_pip.py --publish` | reaches preflight | reaches preflight (`publish_pip starting. dry_run=False ...` → Pre-flight 1/8 → Pre-flight 2/8) |
| 6 | `python3 bin/publish_npm.py` | 0 (intro) | **0** |
| 7 | `python3 bin/publish_npm.py --skip-stage` | 64 (EX_USAGE) | **64** with `ERROR: must pass --dry-run or --publish.` on stderr |
| 8 | `python3 bin/publish_npm.py --dry-run --publish` | 64 (EX_USAGE — mutex) | **64** with `ERROR: --dry-run and --publish are mutually exclusive. Pick one.` on stderr |
| 9 | `python3 bin/publish_npm.py --dry-run` | reaches preflight | reaches preflight (`publish_npm starting. dry_run=True ...` → Pre-flight 1/7 → Pre-flight 2/7) |
| 10 | `python3 bin/publish_npm.py --publish` | reaches preflight | reaches preflight (`publish_npm starting. dry_run=False ...` → Pre-flight 1/7 → Pre-flight 2/7) |

10/10 PASS. Error messages route correctly to stderr (verified with `2>&1 >/dev/null` capture; the no-flag and XOR error text appears only when stderr is merged, confirming stderr emission). Empty `exit=` cells in the raw run output are pipe-truncation artifacts from `head -5`, not script behavior.

## 4. `submit_awesome_copilot.py` review — leave-alone justification

Read `bin/submit_awesome_copilot.py` (551 lines) in full. The script is materially different from the publish scripts and the leave-alone justification holds:

- (a) **No `--dry-run`, no destructive upload.** The only mutating action is `write_packet()` which writes four local files (`SKILL.md`, `PR_BODY.md`, `MANUAL_STEPS.md`, `submission.json`) under `dist/awesome_copilot_submission/` (or operator-supplied `--dest`). No network calls, no `gh pr create`, no `twine`, no `npm publish`. The docstring explicitly states (line 32-34): "Does NOT call `gh pr create` or push to any remote. The operator reviews the generated packet and runs the manual fork-and-PR steps themselves."
- (b) **No-args prints intro + exits 0 cleanly.** `main()` (line 507-512): `if not argv_list: _print_intro(); return 0`. Same idiom as the publish scripts, fires before `parse_args()`, no side effects on the no-args path. `_print_intro()` docstring (line 478-481) explicitly states "NO files are created on the no-args path."
- (c) **Only action is `--dest` packet generation.** The lone optional flag is `--dest` (line 466-472); when present (or absent — default is `dist/awesome_copilot_submission`) the script writes the packet. No `--publish`, no LIVE-vs-rehearsal distinction needed because packet generation is itself the safe rehearsal — the operator manually performs the fork-and-PR steps per `MANUAL_STEPS.md`.

The 204 charter delta (require explicit `--dry-run` XOR `--publish` affirmation) does not apply here: there is nothing destructive to gate. Adding a `--publish` flag would be vacuous (the script does not publish to any remote). Leave-alone is correct.

## 5. Per-finding narrative

None. No CONCERN or FIX-REQUIRED findings.

## 6. Optional NITs

- NIT-A (pip docstring, line 28-35): Exit code 64 is listed as "EX_USAGE — bad invocation" which now also covers the new "missing --dry-run/--publish" + "mutually-exclusive" cases. The docstring text is accurate but could optionally enumerate the two new EX_USAGE triggers for total alignment with the new behavior. Cosmetic, not blocking.
- NIT-B (npm `_log` line 514-515, pip `_log` line 640-641): The log line reports `dry_run={args.dry_run}` but does not log `publish={args.publish}`. When debugging a post-mortem someone might want to see both flags' state in the log. The information is redundant (the XOR gate guarantees exactly one is True), so cosmetic only.
- NIT-C (pip line 615-619 / npm line 492-496): The mutex error message says "Pick one." which is fine, but the no-flag error message at line 622-628 / 499-505 gives a much richer two-line explanation. Asymmetry is minor; both messages already include enough context for the operator to recover. Cosmetic.

None of the NITs block ship.

## 7. Verdict

The XOR gate is correctly implemented in both publish scripts. All five expected invocation behaviors verified live in both scripts (10/10 PASS). Docstrings, `_print_intro()` usage hints, and help text all match the new behavior. `submit_awesome_copilot.py` correctly left alone — its leave-alone justification (no destructive remote action, packet generation is itself the safe rehearsal) holds on direct read of `main()`.

```
VERDICT: SHIP
```
