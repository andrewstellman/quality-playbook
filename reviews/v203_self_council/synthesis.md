# Synthesis — 203 Worker self-Council (3-panelist)

**SHIP recommendation: YES.** All three panelists converge on SHIP without escalation. Zero FIX-REQUIRED, zero CONCERN, 9 non-blocking NITs.

## Panel summary

| Panelist | Charter | Verdict | Key contribution |
|----------|---------|---------|------------------|
| A | Root-cause correctness + audit completeness | **SHIP** | Full print-call audit (3 prints classified); discipline comment + `import sys` verified; live `npm pack` stdout confirmed pure JSON |
| B | Defense-in-depth correctness | **SHIP** | All 3 cases covered (clean / polluted / no-`[`); log discipline preserved (unmodified `r.stdout` written BEFORE strip); 34/34 publish_npm tests pass |
| C | Regression test sufficiency + mutation verification | **SHIP** | Independently re-performed mutation-bite + got identical failure; AUDIT-pattern elevation correctly declined (first known firing; needs 3 to graduate) |

## Panelist A verdict — root-cause clean

### Print-call audit (full file)

| Line | Content | Classification | stderr-routed? |
|------|---------|---------------|----------------|
| 541 | `print(_purpose.get_version())` | STDOUT-intended (`--version` consumer payload) | NO ✓ correct |
| ~557 | stamp-manifest progress | STDERR-intended (diagnostic) | YES ✓ (`file=sys.stderr`) |
| ~568 | staged-files progress (the 202 root cause) | STDERR-intended (diagnostic) | YES ✓ (`file=sys.stderr`) |

- `import sys` present at line 40 (already load-bearing pre-203; used at lines 65, 118, 454, 582)
- Discipline comment at lines 544–548 cites instruction 203, the npm-pack-prepack consumer, AND the `--version` carve-out
- Live verification: `npm pack --dry-run --json 2>/dev/null | head -3` → first line is `[`
- Indirect stdout writers in `main()` (`_purpose.print_command_intro`, `print_help_banner`) only fire on no-args / `--help` paths; never reached by prepack's `--stage` invocation

### Panelist A NITs (deferred)
- A-NIT1: module-docstring discipline note
- A-NIT2: stylistic line wrap
- A-NIT3: future-channel-hook risk for other `_purpose` callers

## Panelist B verdict — defense-in-depth clean

### Case-coverage table

| Case | Stdout shape | Covered by | Assertion |
|------|--------------|------------|-----------|
| (a) clean | starts with `[` | `test_clean_pack_passes` | `assertTrue(ok)` + `assertIn("SKILL.md", ...)` |
| (b) polluted | progress prefix then `[` | `test_polluted_stdout_with_progress_line_parses` | `assertTrue(ok)` + `assertIn("SKILL.md", ...)` after defensive strip |
| (c) no `[` | no JSON marker anywhere | `test_stdout_with_no_bracket_fails_with_clear_error` | `assertFalse(ok)` + `assertIn("no '['", msg)` + `assertIn(<stdout snippet>, msg)` |

- 6/6 in `NpmPackDryRunTests` pass; 34/34 in full `test_publish_npm.py` pass
- Log discipline: `bin/publish_npm.py:303` writes `r.stdout or ""` UNMODIFIED before any analysis (line 313+). Only a local slice (`stdout[json_start:]`) is parsed.
- Explicitly asserted by `test_log_captures_full_unmodified_stdout` — pollution prefix survives in the log.
- Degenerate-case error: `repr()`-quoted, length-capped stdout snippet (informative without unbounded log growth)

### Panelist B NITs (deferred)
- B-NIT1: error message could specify stdout BYTE count for context
- B-NIT2: `find("[")` finds first `[` — could match a `[` inside a progress message
- B-NIT3: consider also stripping leading whitespace before `find("[")`

## Panelist C verdict — regression test sound + mutation independently reproduced

### Test design audit

`NpmPackRoundTripStdoutTests.test_npm_pack_dry_run_stdout_is_pure_json` at `bin/tests/test_publish_npm.py:346-392`:
- Runs genuine `npm pack --dry-run --json` against on-disk `package.json` + `bin/build_channel_package.py` prepack — NOT mocked
- 3 CI-safe skip conditions: missing `npm`, missing `python3`, missing `package.json`
- Load-bearing assertion: `r.stdout.lstrip().startswith("[")` — the contract
- Identity check: `name == "quality-playbook"` prevents future identity drift
- Validates: `assertIsInstance(data, list)`, `assertGreater(len(data), 0)`, `assertIn("files", first)`

### Mutation verification (C independently re-performed)

C snapshotted the file separately, removed `file=sys.stderr,` from staged-files print, purged `bin/__pycache__`, and observed the EXACT failure the build agent reported (`build_channel_package: staged 59 files into ...` polluting stdout before the JSON `[`). Restored via `shutil.copy2` per `[[feedback_mutation_bite_pycache]]`; test passes on restore; `git diff` clean. Discipline per `DEVELOPMENT_PROCESS.md § Mutation-test discipline` (lines 122-131) satisfied.

### AUDIT-table elevation (correctly declined)

Per `DEVELOPMENT_PROCESS.md:97-118`, the AUDIT-table pattern requires three confirmed reuses to graduate. This is the FIRST known firing of "scripts consumed by JSON parsers must keep stdout pure." Instruction-203's response shape is correct for a first-fire defect:
- Site fix (build_channel_package.py)
- Module-top audit comment
- Defense-in-depth at the consumer (publish_npm.py:308-322 find-the-`[` parse)

Premature AUDIT-table elevation would be a maintenance hazard. Defer until 2 more sites surface the same class.

### Panelist C NITs (deferred)
- C-NIT1: test could also assert no `\n` before the `[` for stricter pin
- C-NIT2: skip-on-missing logic could log to test stderr for CI visibility
- C-NIT3: 120s timeout might be aggressive in slow CI

## Key panel agreements

1. **All 3 prints in `build_channel_package.py` correctly classified** — A audited; B + C independently spot-checked.
2. **Defense-in-depth covers all 3 cases** with passing tests + preserved log discipline.
3. **Mutation-bite was real** — C independently reproduced + got identical failure trace.
4. **AUDIT-pattern elevation NOT yet warranted** — first occurrence; needs 3 to graduate per documented policy.
5. **34/34 publish_npm tests + 91/91 across all 3 publish suites pass.**
6. **Test-coverage gap from 202 is now closed** — `test_npm_pack_dry_run_stdout_is_pure_json` exercises the real round-trip the 202 mocked tests missed.

## Recommendation

**SHIP.** All three panelists converge on SHIP without iteration. Mutation-bite verified twice (build agent + Panelist C). Zero FIX-REQUIRED, zero CONCERN, 9 non-blocking NITs deferred to v1.5.x backlog.

Push to origin/1.5.8 requires **operator confirmation** per instruction's "Done definition": "No push to origin without operator approval. Worker commits to 1.5.8 branch and STOPs at 'ready to push.' Andrew confirms before push."

Current local state on 1.5.8 ahead of origin:
- `36d53ed` (this commit — instruction 203)
- `85d87b6` (operator's v1.5.9 docs/design; tagged v1.5.8)
- `f0927e8` (operator's harness_plans)
- `27e4db7` (instruction 202 Council remediation)
- `d2fd31f` (instruction 202 initial build)

5 commits total awaiting operator push-approval.

The methodology generalization (documented in 202's DEVELOPMENT_PROCESS.md addition + reinforced by this instruction): every release-time external interaction must be scripted, dry-runnable, and idempotent. The 203 fix closes one specific failure mode (prepack stdout pollution) and adds belt+suspenders so the same pattern can't sneak back in via any future prepack change.
