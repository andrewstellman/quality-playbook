# Synthesis — 205 Worker self-Council (3-panelist)

**SHIP recommendation: YES.** All three panelists converge on SHIP unconditional. Zero FIX-REQUIRED, zero CONCERN, 9 non-blocking NITs.

## Panel summary

| Panelist | Charter | Verdict | Key contribution |
|----------|---------|---------|------------------|
| A | CLI + pass-through correctness | **SHIP** | All 5 charter items pass; `bin/publish_pip.py` confirmed untouched; 44/44 + 3178/3186 in full bin/tests/ pass |
| B | OTP-leak resistance + log discipline | **SHIP** | Redact-before-log ordering correct; `capture=False` at publish step closes npm's stderr-echo channel (stronger than charter required); `args.otp` referenced exactly once |
| C | Tests + empirical | **SHIP** | All 5 OtpHandlingTests at correct boundary; mutation independently re-performed with identical failure; `--help` documents `--otp`; abort-at-prompt step env-blocked but mechanically verified from static code |

## Panelist A verdict — CLI + pass-through

| Item | Result |
|------|--------|
| `--otp CODE` declared with `default=None` (publish_npm.py:486-496) | ✓ |
| Conditional `if otp: cmd.extend(["--otp", otp])` at line 386-387 — Python truthiness skips None AND "" | ✓ |
| `import getpass` (line 69); `getpass.getpass(...)` at line 650 (not input); EOFError → empty fallback | ✓ |
| Prompt timing correct: `_confirm_publish` → resolve OTP → `run_npm_publish` (~30s window guarded) | ✓ |
| Docstring (line 22 + lines 30-36) + `_print_intro` usage_hint (line 526) mention `--otp` | ✓ |
| `bin/publish_pip.py` NOT touched per § Out of scope | ✓ confirmed via `git diff` |

44/44 test_publish_npm.py pass; full bin/tests/ → 3178 passed + 8 skipped.

### Panelist A NITs (deferred)
- A-NIT1: `otp or None` truthiness style
- A-NIT2: empty-prompt recovery UX
- A-NIT3: doc-comment alignment

## Panelist B verdict — OTP-leak resistance

### Redact-before-log ordering (correct)

`bin/publish_npm.py:385-394` builds `redacted_cmd` (shallow copy of `cmd`), overwrites the post-`--otp` token with `<REDACTED>`, and `_log`s that redacted copy. THEN `_run(cmd, ...)` fires with the raw argv. The only log mention of the publish argv anywhere in the file is the redacted copy.

### `capture=False` closes npm's stderr echo channel

Line 395: `_run(cmd, cwd=repo_root, capture=False)`. With `stdout=None, stderr=None` (lines 147-148), npm streams directly to the operator's terminal; `r.stderr` is `None`. The failure-path log line is just `"npm publish failed (exit {r.returncode})."` — exit code only, no stderr text. **Stronger than charter item 3 required** (no captured stderr at all, rather than "captured but OTP-stripped"). If npm's own error message included the OTP value (highly unlikely), it would never reach the log.

### getpass + single-reference audit

- `getpass.getpass()` at line 650 is the OTP entry point. `input()` used only at line 454 for y/N confirmation, never for OTP. EOFError → `otp=""` → `--otp` omitted from npm argv.
- `args.otp` is referenced exactly once in the file (line 647), assigned to a local. No print/log statement in `main()` interpolates it. The startup log line (565-566) logs `dry_run`, `version`, `log` only.

### Test-coverage assessment

All 5 OtpHandlingTests pass. `test_log_does_not_contain_raw_otp` asserts BOTH `<REDACTED>` is present AND raw `654321` is absent in `log_fh.getvalue()` — the right discipline-test shape.

### Panelist B NITs (deferred)
- B-NIT1: defensive `mock.patch.object(publish_npm.getpass, "getpass")` test to pin the entry point
- B-NIT2: `.strip()` on `args.otp` to symmetrize with the `getpass` path
- B-NIT3: tighten the comment on line 388 to make the redact-before-log invariant explicit

## Panelist C verdict — Tests + empirical

### Test-method-presence (5/5)

All at `bin/tests/test_publish_npm.py:508`:
- `test_otp_flag_parses` (line 513)
- `test_otp_default_is_none` (line 517)
- `test_npm_publish_includes_otp_when_provided` (line 521)
- `test_npm_publish_omits_otp_when_empty` (line 534) — covers both `None` and `""`
- `test_log_does_not_contain_raw_otp` (line 554)

Each asserts at the right boundary (mocking `publish_npm._run` to inspect subprocess command line / log buffer). No coverage theater.

### Mutation verification (independently re-performed)

C took own snapshot to `/tmp/qpb_205_panelist_c_snapshot.py`, commented out the `if otp: cmd.extend(["--otp", otp])` block, scope-purged `bin/__pycache__` + `bin/tests/__pycache__`, observed `test_npm_publish_includes_otp_when_provided` FAIL with the exact expected assertion error (no `--otp` in cmd), restored via `shutil.copy2` per `[[feedback_mutation_bite_pycache]]`, re-purged pycache, observed all 5 tests PASS, confirmed `git diff bin/publish_npm.py` is empty. **Two independent confirmations** (orchestrator + Panelist C) — identical failure trace.

### `--help` empirical

`--otp CODE` documented in usage line and help string. Verified by direct invocation.

### Abort-at-prompt empirical (env-blocked)

Charter step 4 (`echo "n" | python3 bin/publish_npm.py --publish --otp 999999 --skip-stage`) halted at Preflight 4/7 (`npm whoami`) with EX_DATAERR=65 because the agent's sandbox is not `npm login`-ed. C filed as NIT-1, not CONCERN, because the prompt → decline → exit 0 path is mechanically verifiable from static code: `_confirm_publish` returns False on non-`y`/EOFError (line 446-457); `main()` logs "Operator declined npm publish. Halting." + returns EX_OK (line 638-640).

### Panelist C NITs (deferred)
- C-NIT1: env limitation for empirical step 4 (orchestrator has `npm login` so can verify on next pass if desired)
- C-NIT2: optional split of empty/None test (currently combined)
- C-NIT3: defense-in-depth redaction helper (e.g., `_redact_secret_arg(cmd, "--otp")`)

## Key panel agreements

1. **`--otp` flag declared correctly** (A, B, C independently verified)
2. **Conditional pass-through** uses Python truthiness (`if otp:`) — None + "" both skip
3. **Log redaction** correctly ordered (redact BEFORE log; `_run` gets raw cmd)
4. **`capture=False` at publish step** is stronger than charter required — closes npm's own stderr-echo channel
5. **getpass.getpass()** is the OTP entry point (B confirmed via grep; only `input()` use is the y/N confirmation)
6. **Prompt timing** is correct: after y/N confirmation, immediately before `npm publish` (minimizes OTP-expiry window)
7. **Mutation-bite reproducible** — orchestrator + C both got identical failure trace
8. **`bin/publish_pip.py` NOT touched** — per instruction § Out of scope

## Recommendation

**SHIP.** All three panelists converge on SHIP without iteration. Mutation-bite verified twice (orchestrator + Panelist C independent). Zero FIX-REQUIRED, zero CONCERN, 9 non-blocking NITs deferred to v1.5.x backlog.

Push to origin/1.5.8 requires **operator confirmation** per instruction's "Done definition": "No push to origin without operator approval. Worker commits to 1.5.8 branch and STOPs at 'ready to push.' Andrew confirms before push."

Current local state on 1.5.8 ahead of origin (10 commits):
- `8625474` (THIS commit — instruction 205)
- `09de4b6` (204 Council artifacts)
- `c46b5de` (204 fix)
- `2c290a1` (operator release close-out docs)
- `794ba1e` (203 Council artifacts)
- `36d53ed` (203 fix)
- `85d87b6` (operator v1.5.9 docs/design; tagged v1.5.8)
- `f0927e8` (operator harness_plans)
- `27e4db7` (202 Council remediation)
- `d2fd31f` (202 build)

Plus this Council-artifacts commit will follow.

## Methodology echo

The 205 fix completes the publish-channel hardening arc started by 202: created scripts → 203 fixed prepack stdout pollution → 204 added explicit --dry-run XOR --publish affirmation → 205 added OTP for 2FA-enabled npm accounts. Each was a real defect Andrew hit during the first attempt to ship v1.5.8 — and each was fixed in the script, not kludged around. The pattern: every release-time external interaction (PyPI upload, npm publish, registry PR) must be scripted, dry-runnable, and idempotent. The operator's job is to review the prompt and type `y` + the OTP; not to remember the command syntax or work around script defects.

After 205 lands on origin/1.5.8, Andrew re-runs `python3 bin/publish_npm.py --publish`, types `y`, enters fresh OTP at the interactive prompt, and npm publish should succeed. v1.5.8 close-out then resumes at the awesome-copilot submission step (step 3 final sub-task).
