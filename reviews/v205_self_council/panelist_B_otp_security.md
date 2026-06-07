# Panelist B — OTP-leak resistance + log discipline (instruction 205)

Repo: `/Users/andrewstellman/Documents/QPB/` @ HEAD `8625474` (branch `1.5.8`).

## 1. Charter recap

Confirm `bin/publish_npm.py` redacts the 2FA OTP value (`<REDACTED>`) before any log write, never echoes it via print/log in `main()`, never leaks npm-side stderr containing the OTP back to the log on failure, uses `getpass.getpass()` so terminal scrollback stays clean, and pin those properties with `OtpHandlingTests.test_log_does_not_contain_raw_otp`.

## 2. OTP touch-point audit table

| # | Location (file:line) | What happens to the OTP value | Verdict |
|---|----------------------|--------------------------------|---------|
| 1 | `publish_npm.py:22` (module docstring) | Literal `--otp 123456` in usage example. Not runtime data. | OK |
| 2 | `publish_npm.py:487-496` (argparse) | `--otp CODE` registered; metavar=`CODE`. No echo. | OK |
| 3 | `publish_npm.py:647` (`otp = args.otp`) | Read from CLI args into local. | OK |
| 4 | `publish_npm.py:648-655` (interactive fallback) | `getpass.getpass(...)` with no-echo prompt; `.strip()` applied. `EOFError` → `otp = ""`. | OK |
| 5 | `publish_npm.py:658` (`run_npm_publish(... otp or None ...)`) | Passes raw OTP into `run_npm_publish`. Not logged here. | OK |
| 6 | `publish_npm.py:385-387` (`cmd.extend(["--otp", otp])`) | Raw OTP placed in subprocess argv list (`cmd`). Still in memory only. | OK |
| 7 | `publish_npm.py:390-394` (redacted_cmd build + `_log(...)`) | A **copy** of `cmd` is mutated so the token after `--otp` becomes `<REDACTED>`; the **redacted** copy is logged. The raw `cmd` is never logged. | OK |
| 8 | `publish_npm.py:395` (`_run(cmd, capture=False)`) | Raw OTP passed to npm via argv. `capture=False` ⇒ stdout/stderr stream to terminal, NOT captured into the Python `r.stdout`/`r.stderr` strings. | OK (see §5) |
| 9 | `publish_npm.py:397` (failure message) | Logs only `"npm publish failed (exit {r.returncode})."` — exit code, no stderr, no OTP. | OK |
| 10 | `publish_npm.py:565-566` (startup log) | Logs `dry_run`, `version`, `log`. **No `args.otp` interpolated.** | OK |

`grep "args\.otp\|f\"otp\|print.*otp"` confirms `args.otp` is referenced exactly once (line 647) and never interpolated into a print/log f-string anywhere in main() or elsewhere.

## 3. Log-redaction verification (CLI → main → run_npm_publish → log)

1. CLI: `--otp 123456` is parsed into `args.otp = "123456"` (argparse).
2. `main()` line 647: `otp = args.otp` (or `getpass.getpass(...)` when None).
3. `main()` line 658: `run_npm_publish(repo_root, npm, otp or None, log_fh)`.
4. `run_npm_publish` (lines 385-394):
   - Line 385: `cmd = [npm, "publish", "--access", "public"]` — no OTP yet.
   - Lines 386-387: `if otp: cmd.extend(["--otp", otp])` — raw OTP appended **to argv only**.
   - Lines 390-393: `redacted_cmd = list(cmd)` (shallow copy is fine — elements are str, immutable) then scan for the `--otp` token and overwrite its successor with `"<REDACTED>"`.
   - Line 394: `_log(log_fh, f"npm publish cmd: {redacted_cmd}")` — **only the redacted copy** is written.
   - Line 395: `_run(cmd, ...)` — the raw `cmd` is then handed to subprocess. The redaction happens BEFORE the subprocess fires AND BEFORE the only log write that mentions the command.

Observed log content confirms (from test run):
```
npm publish cmd: ['/usr/local/bin/npm', 'publish', '--access', 'public', '--otp', '<REDACTED>']
```
The raw OTP `654321` from `test_log_does_not_contain_raw_otp` appears nowhere in `log_fh.getvalue()` — pinned.

Ordering invariant (redact-before-log) verified.

## 4. getpass verification

- `import getpass` at line 69.
- The interactive fallback uses `getpass.getpass(...)` (line 650), NOT `input()`.
- `input()` is used once at line 454 — but only for the y/N confirmation prompt, not for the OTP. The OTP prompt is unambiguously `getpass`.
- `getpass.getpass()` on POSIX uses `termios` to disable terminal echo; on Windows it uses `msvcrt.getwch`. In both cases the typed digits do not appear in scrollback or in a `script(1)` capture of the terminal session. Charter item 4 satisfied.

Minor: `EOFError` is handled (line 654 → `otp = ""`) which is right — non-interactive runs without `--otp` get a clean empty string, and `run_npm_publish(... otp or None ...)` (line 658) collapses that to `None`, which omits `--otp` from npm argv entirely. (Pinned by `test_npm_publish_omits_otp_when_empty`.)

## 5. Subprocess-failure case

Charter item 3 is the most interesting one. Trace:

```python
r = _run(cmd, cwd=repo_root, capture=False)   # line 395
if r.returncode != 0:
    return False, f"npm publish failed (exit {r.returncode})."
```

`_run(..., capture=False)` sets `stdout=None`, `stderr=None` (lines 147-148), meaning subprocess inherits the parent's stdio — npm's output streams **directly to the operator's terminal**, never lands in `r.stdout`/`r.stderr` (which become `None`).

Consequence:
- The failure message logged into the publish file is `f"npm publish failed (exit {r.returncode})."` — exit code only. No stderr. No OTP.
- The npm CLI is known to echo `--otp <code>` back in some error messages (E403 "OTP required" never includes the value, but `--otp` flag errors and 401 "Invalid OTP" can include the code in some npm versions).
- Because we never `capture=True` at the publish step, that npm-side echo cannot enter the publish log. The only place a raw OTP could appear after a failure is the operator's terminal scrollback — which is BY DESIGN the place that ALSO got the redacted_cmd log line just before, so the operator sees both.

This is a deliberate, conservative choice: charter item 3 said "captured stderr is logged but the OTP value is NOT echoed back." Implementation goes one step stronger — stderr is not captured at all at the publish step, so there is zero risk of the publish log containing a raw OTP fragment that npm itself echoed.

Caveat I considered but dismissed:
- Pre-flight steps 5 (`build_channel_package --stage`) and 7 (`npm pack --dry-run`) DO use `capture=True` and write `r.stdout`/`r.stderr` verbatim into the log (lines 252-255, 318-321). Neither of these subprocesses ever sees the OTP — `--otp` is only on the `npm publish` argv. So even with `capture=True` upstream, the OTP cannot reach those buffers.
- `npm whoami` (`check_npm_whoami`) and `npm view quality-playbook version` (`verify_npm_version`) also never see the OTP. Their captured output may be logged (lines 233, 432-438), but again the OTP is not on their argv. Clean.

Failure-path is OTP-leak-resistant.

## 6. Test-coverage audit

`OtpHandlingTests` (5 tests, all pass — `Ran 5 tests in 0.002s OK`):

| Test | Surface pinned |
|------|-----------------|
| `test_otp_flag_parses` | argparse accepts `--otp 123456`. |
| `test_otp_default_is_none` | `args.otp` defaults to `None` (so the interactive prompt branches in). |
| `test_npm_publish_includes_otp_when_provided` | When `otp="123456"`, the subprocess argv (`_run` first positional) contains `--otp` AND `"123456"`. |
| `test_npm_publish_omits_otp_when_empty` | When `otp=None` OR `otp=""`, `--otp` does NOT appear in argv. |
| `test_log_does_not_contain_raw_otp` | When `otp="654321"`, `log_fh.getvalue()` contains `<REDACTED>` and does NOT contain `654321`. |

`test_log_does_not_contain_raw_otp` correctly pins the most load-bearing invariant: the log MUST contain `<REDACTED>` (positive assertion — catches accidental removal of the redaction line) AND MUST NOT contain the raw value (negative assertion — catches a regression where someone adds back `_log(log_fh, f"npm publish cmd: {cmd}")` against `cmd` instead of `redacted_cmd`). Both assertions on the same surface is the right shape.

Adequacy: the test exercises the **exact** code path the charter cares about — `run_npm_publish` is called directly with a recognizable OTP and the resulting `log_fh.getvalue()` is inspected. It's a unit test of the redact-before-log discipline. The fact that `test_npm_publish_includes_otp_when_provided` ALSO checks the raw value IS in the `_run` argv (subprocess), combined with the new log-discipline test asserting that raw value is NOT in the log, means a regression that swapped the variables would be caught by exactly one of these tests.

Coverage gaps I considered but do NOT recommend adding (out of scope or already covered):
- No test for npm-failure-path stderr leak. Justified: with `capture=False`, stderr never enters Python at all; the test would just assert `r.stderr is None`. Not load-bearing.
- No test that `args.otp` isn't echoed in the `publish_npm starting...` log line. The current startup log f-string is statically auditable (line 565-566); `grep` already shows `args.otp` referenced exactly once at line 647. Adding a regression test for "don't add args.otp to the startup log line" would test absence of a string that has never been there. NIT only — see §8.
- No test that `getpass.getpass` is the entry point (vs `input`). The `EOFError` branch (line 654) is a clue, but a defensive test could `mock.patch("getpass.getpass")` and assert it was called for the OTP prompt. NIT only — see §8.

## 7. Per-finding narrative

None. No CONCERN or FIX-REQUIRED findings.

## 8. Optional NITs

1. **Pin the `getpass.getpass` entry point** (NIT, not blocking). A defensive test:
   ```python
   def test_otp_prompt_uses_getpass_not_input(self):
       with mock.patch.object(publish_npm.getpass, "getpass", return_value="111111") as mg, \
            mock.patch.object(publish_npm, "input"):  # would fail if input() were called
           ...
       mg.assert_called_once()
   ```
   would catch a future refactor that accidentally swaps `getpass.getpass` for `input()`. The current code is clearly correct; this is belt-and-suspenders.

2. **Pin "args.otp not in startup log"** (NIT). A regression guard:
   ```python
   def test_startup_log_does_not_contain_otp(self):
       with mock.patch.object(sys, "argv", ["publish_npm", "--publish", "--otp", "999999"]):
           # ... drive a main() far enough to write the startup log, then assert "999999" NOT in log
   ```
   Currently impossible without extensive mocking of preflight checks. Skip unless we end up with a quality_gate-style end-to-end harness for publish_npm. Document the invariant in the redact-discipline comment instead.

3. **Comment audit** (NIT). The comment on line 388 says "write the command line with the OTP value redacted before invoking the subprocess." Strictly accurate, but the ordering also matters: redaction MUST happen before the `_log` call. Could be tightened to "build a redacted copy of the argv list; log the redacted copy; only then invoke the subprocess with the raw argv." Five-word change for absolute clarity.

4. **Strip whitespace defense** (NIT). Line 653 calls `.strip()` on the getpass result. Good. But `args.otp` (CLI-provided path) is not stripped. If an operator passes `--otp " 123456"` with a leading space (shell-quoted), `cmd.extend(["--otp", " 123456"])` would pass a malformed token to npm. Low-impact (npm would reject and operator would retry), but a `.strip()` on `args.otp` at line 647 would make the two paths symmetric.

None of these block.

## 9. Final verdict

**Strengths:**
- Redact-before-log ordering is provably correct: `redacted_cmd` is built and logged BEFORE `_run(cmd, ...)` is called. The only log mention of the publish argv is the redacted copy.
- `capture=False` at the publish step closes the npm-side stderr-echo channel entirely — npm's own error messages cannot enter the publish log.
- `getpass.getpass()` is the OTP prompt; `input()` is reserved for y/N confirmation only.
- `args.otp` appears exactly once in the source (line 647) — assigned to a local, never echoed.
- The new pin `test_log_does_not_contain_raw_otp` asserts BOTH positive (`<REDACTED>` present) and negative (raw `654321` absent), which is the right shape for a discipline test.
- All 5 `OtpHandlingTests` pass.

**Concerns:** None.

**Fix-required:** None.

```
VERDICT: SHIP
```
