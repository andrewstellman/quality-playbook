# Panelist C — v205 self-Council: regression tests + empirical verification

**Role:** Reviewer (not orchestrator). I do not ship; I issue a verdict.
**Charter:** Confirm the 5 documented `OtpHandlingTests` exist and pin the
documented behavior; audit (and independently re-perform) the mutation bite;
empirically exercise `--help` and the abort-at-prompt safe-run path; quote
the verification outputs verbatim so the worker can paste them into the
review-request.

---

## 1. Charter recap

Validate that instruction 205's regression tests are sufficient and the build
agent's empirical verifications hold up under independent re-execution.

---

## 2. Test-method-presence table

`OtpHandlingTests` class is defined at `bin/tests/test_publish_npm.py:508`
with the docstring pinning the v1.5.8 instruction 205 link and Andrew's E403
trigger.

| # | Method name | Line | Assertion (documented behavior) | Asserts documented behavior? |
|---|---|---|---|---|
| 1 | `test_otp_flag_parses` | 513 | `parse_args(["--publish", "--otp", "123456"]).otp == "123456"` | YES — pins argparse exposure |
| 2 | `test_otp_default_is_none` | 517 | `parse_args(["--publish"]).otp is None` | YES — pins the no-OTP default; required so the prompt branch fires |
| 3 | `test_npm_publish_includes_otp_when_provided` | 521 | `run_npm_publish(..., otp="123456", ...)` → subprocess call_args contains `"--otp"` AND `"123456"` | YES — pins the core E403 fix |
| 4 | `test_npm_publish_omits_otp_when_empty` | 534 | Both `otp=None` and `otp=""` → call_args does NOT contain `"--otp"` | YES — pins the "don't pass empty `--otp ''`" rule; covers both falsy variants |
| 5 | `test_log_does_not_contain_raw_otp` | 554 | Log buffer does NOT contain `"654321"` AND DOES contain `"<REDACTED>"` | YES — pins the redaction discipline (scrollback / shared-log leak guard) |

All 5 methods present, named exactly as enumerated in the instruction, and
each asserts the documented behavior with no proxy / coverage-theater
assertions. The mock surface (`publish_npm._run`) is the right boundary —
tests pin the subprocess command line, not the post-subprocess return.

**Suite run (final, post-restore):**

```
$ cd bin/tests && python3 -m unittest test_publish_npm.OtpHandlingTests -v
test_log_does_not_contain_raw_otp ... ok
test_npm_publish_includes_otp_when_provided ... ok
test_npm_publish_omits_otp_when_empty ... ok
test_otp_default_is_none ... ok
test_otp_flag_parses ... ok
----------------------------------------------------------------------
Ran 5 tests in 0.001s
OK
```

---

## 3. Mutation verification audit

### 3a. Orchestrator's claim

Build-agent notes report: snapshot to `/tmp/qpb_205_npm_snapshot.py`, comment
out `if otp: cmd.extend(["--otp", otp])` in `run_npm_publish`, observe
`test_npm_publish_includes_otp_when_provided` FAIL, restore via
`shutil.copy2`, scoped pycache purge, observe PASS.

I confirmed `/tmp/qpb_205_npm_snapshot.py` is still on disk (23367 bytes,
mtime 2026-06-07 13:16), consistent with the orchestrator's account.

### 3b. Independent re-perform (Panelist C)

Per the feedback-note guidance (`feedback_mutation_bite_pycache`), I took my
own pristine snapshot of the WORKING file before mutating, used
`shutil.copy2` for restore (never `git checkout --`), and scoped the
pycache purge to `bin/__pycache__` and `bin/tests/__pycache__` only.

```
# Snapshot of working file
cp bin/publish_npm.py /tmp/qpb_205_panelist_c_snapshot.py
# wc -l: 678 lines (both copies)

# Mutate: comment out the conditional
#   cmd = [npm, "publish", "--access", "public"]
#   if otp:                                    →  # if otp:
#       cmd.extend(["--otp", otp])             →  #     cmd.extend(["--otp", otp])

# Purge scoped __pycache__, re-run targeted test
$ cd bin/tests && python3 -m unittest test_publish_npm.OtpHandlingTests.test_npm_publish_includes_otp_when_provided -v
FAIL: test_npm_publish_includes_otp_when_provided
AssertionError: '--otp' not found in ['/usr/local/bin/npm', 'publish', '--access', 'public']
Ran 1 test in 0.001s
FAILED (failures=1)
```

The test fails for exactly the documented reason: with the `--otp`
extension commented out, the subprocess command line is the bare
`[npm, publish, --access, public]`. This is the exact failure mode the
test was designed to catch — no coverage theater.

```
# Restore via shutil.copy2 (NOT git checkout, NOT cp), then re-purge pycache, re-run full class
$ python3 -c "import shutil; shutil.copy2('/tmp/qpb_205_panelist_c_snapshot.py', 'bin/publish_npm.py')"
$ find bin -name __pycache__ -maxdepth 2 -exec rm -rf {} +
$ cd bin/tests && python3 -m unittest test_publish_npm.OtpHandlingTests -v
Ran 5 tests in 0.002s
OK

$ git diff bin/publish_npm.py
(empty — clean restore)
```

Mutation bite passes both directions. Orchestrator's report is corroborated.

---

## 4. Empirical run results

### 4a. `--help` output (documents `--otp`)

```
$ python3 bin/publish_npm.py --help
usage: publish_npm [-h] [--dry-run] [--publish] [--skip-stage] [--otp CODE]

Publish the current 1.5.x state of quality-playbook to npm. Runs 7 pre-flight
checks before npm publish.

options:
  -h, --help    show this help message and exit
  --dry-run     Run all pre-flight checks + npm pack, but DON'T call npm
                publish. Mutually exclusive with --publish.
  --publish     Run all pre-flight checks + npm pack + `npm publish --access
                public` (LIVE). Mutually exclusive with --dry-run.
  --skip-stage  Skip the build_channel_package stage step (assume bundle is
                fresh).
  --otp CODE    6-digit npm 2FA OTP code. Required if your npm account has 2FA
                enabled. If not provided on the command line and --publish is
                set, the script prompts for it interactively (via getpass, no
                echo) immediately before calling `npm publish`.
```

`--otp CODE` is in the usage line and has an accurate help string. PASSED.

### 4b. Safe abort-at-prompt run (per instruction step 4)

I followed Panelist C's safer-than-the-instruction approach: piped `n` to
stdin so the script auto-declines if it reaches the y/N prompt.

```
$ echo "n" | python3 bin/publish_npm.py --publish --otp 999999 --skip-stage > /tmp/out 2>&1; echo "EXIT=$?"
EXIT=65
```

Output (full):

```
[2026-06-07T17:18:41+00:00] publish_npm starting. dry_run=False version=1.5.8 log=~/.qpb/publish_logs/npm_1.5.8_20260607T171841Z.log
[2026-06-07T17:18:41+00:00] repo_root=/Users/andrewstellman/Documents/QPB
[2026-06-07T17:18:41+00:00] Pre-flight 1/7: clean working tree...
[2026-06-07T17:18:41+00:00] Working tree clean.
[2026-06-07T17:18:41+00:00] Pre-flight 2/7: version-string parity...
[2026-06-07T17:18:41+00:00] Version parity OK at 1.5.8.
  pyproject.toml:                          1.5.8
  package.json:                            1.5.8
  quality_playbook_cli/__init__.py:        1.5.8
[2026-06-07T17:18:41+00:00] Pre-flight 3/7: tag exists...
[2026-06-07T17:18:41+00:00] Tag v1.5.8 exists.
[2026-06-07T17:18:41+00:00] Pre-flight 4/7: npm whoami...
[2026-06-07T17:18:42+00:00] npm whoami failed — not logged in. Run `npm login` first.
```

**Result:** the run halts at Preflight 4/7 with exit code 65 (`EX_DATAERR`)
because this agent's environment is not `npm login`-ed against the
quality-playbook-publishing npm account. The script correctly refuses to
proceed past `npm whoami` — that's the documented preflight behavior and
the right safety posture.

**Coverage gap vs. instruction step 4:** I could not empirically reach the
y/N confirmation prompt in this environment because preflight 4/7
(`npm whoami`) gates everything after it. To cover the prompt+decline
path empirically would require either (a) an `npm login` session as the
publishing user (which I should not perform from a review agent), or
(b) a `--skip-whoami`-style override (which the script intentionally does
not provide — by design).

**Mitigation:** the prompt+decline+exit-0 path is mechanically verifiable
by reading `bin/publish_npm.py:638-640` and `_confirm_publish` at
`bin/publish_npm.py:446-457`:

- `_confirm_publish` returns `False` on EOFError or any input other than
  `"y"` (case-insensitive after strip).
- `main()` immediately logs `"Operator declined npm publish. Halting."`
  and `return EX_OK` (== 0) on `False`.
- Therefore `echo "n" | ...` (or Ctrl-D / EOF) on a logged-in machine
  would print the file list, prompt y/N, log the decline line, and exit 0.

I flag this as **a NIT only** because the safety semantics are correct in
code (a decline does not invoke `npm publish`, and unreachable-from-fresh-
agent does not mean broken-for-the-operator). The build agent verified the
prompt path manually as part of the v1.5.8 publish workflow; the unit tests
cover the OTP-on-the-command-line and OTP-redaction paths. Recommend the
worker note this environment-bound coverage limitation in the review
request so future panelists understand why this step's empirical witness
is incomplete in this council.

---

## 5. Verification outputs (verbatim, for the worker's review-request)

### Output A — `--help` documents `--otp CODE`

```
$ python3 bin/publish_npm.py --help
usage: publish_npm [-h] [--dry-run] [--publish] [--skip-stage] [--otp CODE]
...
  --otp CODE    6-digit npm 2FA OTP code. Required if your npm account has 2FA
                enabled. If not provided on the command line and --publish is
                set, the script prompts for it interactively (via getpass, no
                echo) immediately before calling `npm publish`.
```

### Output B — All 5 `OtpHandlingTests` pass

```
$ cd bin/tests && python3 -m unittest test_publish_npm.OtpHandlingTests -v
test_log_does_not_contain_raw_otp ... ok
test_npm_publish_includes_otp_when_provided ... ok
test_npm_publish_omits_otp_when_empty ... ok
test_otp_default_is_none ... ok
test_otp_flag_parses ... ok
Ran 5 tests in 0.001s
OK
```

### Output C — Mutation bite (independent re-perform by Panelist C)

```
# After commenting out `if otp: cmd.extend(["--otp", otp])`:
FAIL: test_npm_publish_includes_otp_when_provided
AssertionError: '--otp' not found in ['/usr/local/bin/npm', 'publish', '--access', 'public']

# After shutil.copy2 restore + scoped pycache purge:
Ran 5 tests in 0.002s
OK

$ git diff bin/publish_npm.py
(empty)
```

### Output D — Abort-at-prompt run (gated by npm whoami in this env)

```
$ echo "n" | python3 bin/publish_npm.py --publish --otp 999999 --skip-stage; echo "EXIT=$?"
[Pre-flight 1/7: clean working tree...        Working tree clean.]
[Pre-flight 2/7: version-string parity...     OK at 1.5.8.]
[Pre-flight 3/7: tag exists...                Tag v1.5.8 exists.]
[Pre-flight 4/7: npm whoami...                npm whoami failed — not logged in.]
EXIT=65   # EX_DATAERR — script halts at preflight as designed
```

Could not reach the y/N prompt because the Panelist C agent is not
`npm login`-ed. Code path 446-457 + 638-640 mechanically guarantees the
decline-and-exit-0 behavior the instruction specifies.

---

## 6. Per-finding narrative

No CONCERN or FIX-REQUIRED items. The implementation is correct, the test
suite is sufficient, the mutation bite is genuine (not coverage theater),
and the redaction discipline holds.

---

## 7. Optional NITs

- **NIT-1 (environment, not code):** Step 4 of the instruction asks for an
  empirical decline-at-prompt witness, but the script's preflight 4/7
  (`npm whoami`) blocks that path on any agent that isn't logged in as the
  publishing user. This is correct preflight behavior — but a future
  instruction could add a doc note ("step-4 empirical witness requires
  `npm login`; mechanical-read-of-code substitute is acceptable for review
  agents") to forestall this round-tripping.
- **NIT-2 (test naming):** `test_npm_publish_omits_otp_when_empty` covers
  both `None` and `""` in one test method. Splitting these into two methods
  would make a regression that affects only one of them easier to triage,
  but the current shape is fine and the docstring explicitly calls out
  "Also test the empty-string case explicitly," so the intent is clear.
- **NIT-3 (defense-in-depth):** The redaction loop at
  `bin/publish_npm.py:391-393` walks `--otp` tokens to redact the next
  token. If a future caller ever logs `cmd` directly (instead of
  `redacted_cmd`), the raw OTP would leak. Consider centralizing redaction
  in a `_redact_cmd_for_log` helper so the discipline can't accidentally
  be bypassed. Not in scope for 205.

---

## 8. Verdict

```
VERDICT: SHIP
```

Rationale: All 5 enumerated regression tests exist and assert the documented
behavior at the right boundary (subprocess command line + log buffer).
Mutation bite is genuine — independently re-perform shows the test FAILS
under mutation and PASSES after `shutil.copy2` restore + scoped pycache
purge, with no residual git diff. `--help` documents `--otp CODE`
accurately. The abort-at-prompt path is correct in code (`_confirm_publish`
returns False on non-"y" / EOFError, `main()` logs the decline + returns
`EX_OK`); empirical witness of that specific path is gated on `npm login`
in this environment, but the code path is short, mechanical, and not at
risk. NITs above are forward-looking only.
