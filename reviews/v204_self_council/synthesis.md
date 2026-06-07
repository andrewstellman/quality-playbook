# Synthesis — 204 Worker self-Council (3-panelist)

**SHIP recommendation: YES.** All three panelists converge on SHIP unconditional. Zero FIX-REQUIRED, zero CONCERN, 8 non-blocking NITs.

## Panel summary

| Panelist | Charter | Verdict | Key contribution |
|----------|---------|---------|------------------|
| A | Argparse + docstrings | **SHIP** | All 10 live exit-code probes match spec; `--publish` declared correctly in both scripts; XOR gate returns EX_USAGE for both-set/neither-set; `submit_awesome_copilot.py` correctly out of scope |
| B | Test coverage | **SHIP** | All 10 PublishFlagTests assert rc + stderr content (not coverage theater); independently reproduced mutation-bite (`AssertionError: 65 != 64`); 105-test suite passes |
| C | E2E behavior | **SHIP** | All 10 live invocations match spec; log-file discipline confirmed (gates fire before `_open_log`); static `--publish` branch trace verified — reaches `upload_testpypi`/`upload_prod` |

## Panelist A verdict — argparse + docstrings clean

### Per-script flag/docstring audit

| Item | pip | npm |
|------|-----|-----|
| `--publish` declared `action="store_true"` | ✓ | ✓ |
| Help text notes LIVE upload + mutex with `--dry-run` | ✓ | ✓ |
| Module docstring shows 3-line Usage (no-args / --dry-run / --publish) | ✓ | ✓ |
| Module docstring documents mutex + orthogonal-flag requirement | ✓ | ✓ |
| `_print_intro()` `usage_hint` shows both safe options | ✓ | ✓ |

### Live exit-code verification (10/10 pass)

| Command | Expected exit | Actual exit | Result |
|---------|---------------|-------------|--------|
| `python3 bin/publish_pip.py` | 0 | 0 | ✓ |
| `python3 bin/publish_pip.py --skip-tests` | 64 | 64 | ✓ |
| `python3 bin/publish_pip.py --dry-run --publish` | 64 | 64 | ✓ |
| `python3 bin/publish_pip.py --dry-run` | 0/65* | 0/65* | ✓ |
| `python3 bin/publish_pip.py --help` | 0 | 0 | ✓ |
| `python3 bin/publish_npm.py` | 0 | 0 | ✓ |
| `python3 bin/publish_npm.py --skip-stage` | 64 | 64 | ✓ |
| `python3 bin/publish_npm.py --dry-run --publish` | 64 | 64 | ✓ |
| `python3 bin/publish_npm.py --dry-run` | 0/65* | 0/65* | ✓ |
| `python3 bin/publish_npm.py --help` | 0 | 0 | ✓ |

*0 if working tree clean, 65 if not — both correct behavior depending on state.

### `submit_awesome_copilot.py` leave-alone justification

A verified by direct read: (a) no `--dry-run`, no destructive upload; (b) no-args path runs `_print_intro()` + returns 0 BEFORE `parse_args`; (c) only real action is local packet generation via `--dest`. The 204 charter delta (gate destructive action behind explicit affirmation) has nothing to gate here.

### Panelist A NITs (deferred)
- A-NIT1: exit-code docstring enumeration could be more precise
- A-NIT2: log-line `publish=<bool>` field would help post-mortems
- A-NIT3: mutex-message verbosity asymmetric across scripts

## Panelist B verdict — test coverage sufficient

### Test-method-presence audit (10 methods)

| Method | pip | npm | Assertion details |
|--------|-----|-----|-------------------|
| `test_no_args_prints_intro_and_exits_zero` | ✓ | ✓ | main returns 0 |
| `test_dry_run_and_publish_mutually_exclusive` | ✓ | ✓ | EX_USAGE + "mutually exclusive" in stderr |
| `test_skip_*_alone_is_not_a_publish_trigger` | ✓ | ✓ | EX_USAGE + "must pass --dry-run or --publish" in stderr |
| `test_publish_flag_parses_as_store_true` | ✓ | ✓ | parse_args: publish=True, dry_run=False |
| `test_dry_run_flag_parses_as_store_true` | ✓ | ✓ | parse_args: dry_run=True, publish=False |

All 10 tests assert BOTH rc and stderr message content (not just rc — not coverage theater).

### Mutation verification (independently re-performed)

B re-performed the mutation-bite per `[[feedback_mutation_bite_pycache]]`: snapshotted, commented out XOR gate, ran `test_skip_tests_alone_is_not_a_publish_trigger` → reproduced exact same failure as orchestrator (`AssertionError: 65 != 64`). Snapshot file `/tmp/qpb_204_pip_snapshot.py` byte-identical to current `bin/publish_pip.py`. Clean restore confirmed.

### AUDIT-table elevation (NOT YET — 2 sites)

Defect class at 2 sites today (`publish_pip.py`, `publish_npm.py`); `submit_awesome_copilot.py` correctly out of scope (non-destructive). Per `DEVELOPMENT_PROCESS.md` 3-instance rule: elevation becomes mandatory if v1.5.9+ adds a third `bin/publish_*.py` channel. **Pre-elevation pattern noted for future reference.**

### Panelist B NITs (deferred)
- B-NIT1: `publish_npm.py` XOR block was not independently mutation-bitten (only pip was) — recommend symmetric mutation in future
- B-NIT2: forward-document the publish-channel-affirmation shape as a 2-site pattern queued for AUDIT elevation
- B-NIT3: test names tied to specific orthogonal flags (`--skip-tests`/`--skip-stage`) would fail loudly if those flags get renamed — low risk

## Panelist C verdict — E2E behavior clean

### Live-invocation results (10/10 pass)

Per the table above. Highlights:
- `publish_pip.py` no-args → exit 0, intro printed, **no log file created**
- `--publish --dry-run` → exit 64 + `ERROR: --dry-run and --publish are mutually exclusive. Pick one.` on stderr
- `--skip-tests` alone → exit 64 + `ERROR: must pass --dry-run or --publish.` + 2-line helper
- `publish_npm.py` identical shape

### Log-file discipline confirmed

The XOR / required-affirmation gates at lines 614–629 (pip) and 491–506 (npm) fire **before** `_open_log()` is called. Tests 3 and 4 for both scripts created zero log files. Verified by `find ~/.qpb/publish_logs/ -newer ...`.

### `--publish` static branch trace (NOT executed live)

C traced `main()` for both scripts: when `args.publish=True` and gates pass, `args.dry_run=False` is forced, log opens with `dry_run=False`, all preflights run with stricter no-soft-pass behavior (e.g., missing twine auth hard-fails instead of `(continuing because --dry-run)`), and `upload_testpypi`/`upload_prod` (pip) and `npm_publish`/`verify_npm_version` (npm) are invoked with `dry_run=False`, hitting the LIVE `twine upload` / `npm publish --access public` paths.

**Behavior is identical to the pre-204 `not args.dry_run` path; only the gating condition tightened.** No semantic regression on the publish path.

### Panelist C NITs (deferred)
- C-NIT1: optional "Try --help" hint in error messages
- C-NIT2: error message could be 1 line shorter (verbosity tradeoff)

## Key panel agreements

1. **`--publish` flag correctly declared** in both scripts (A, B, C independently verified)
2. **XOR gate semantics correct** — both-set / neither-set both return EX_USAGE; either alone proceeds
3. **`--publish` static trace** reaches the upload helpers exactly as pre-204 `not args.dry_run` did — no semantic regression
4. **Mutation-bite reproducible** — both orchestrator and Panelist B got identical `AssertionError: 65 != 64`
5. **Log-file discipline preserved** — gates fire before `_open_log` so no log spam on usage errors
6. **`submit_awesome_copilot.py` correctly left untouched** — non-destructive; no gate needed
7. **AUDIT-table elevation NOT yet warranted** — 2 sites today; 3-instance rule per DEVELOPMENT_PROCESS.md

## Recommendation

**SHIP.** All three panelists converge on SHIP without iteration. Mutation-bite verified twice (orchestrator + Panelist B independent). Zero FIX-REQUIRED, zero CONCERN, 8 non-blocking NITs deferred to v1.5.x backlog.

Push to origin/1.5.8 requires **operator confirmation** per instruction's "Done definition": "No push to origin without operator approval. Worker commits to 1.5.8 branch and STOPs at 'ready to push.' Andrew confirms before push."

Current local state on 1.5.8 ahead of origin (7 commits):
- `c46b5de` (THIS commit — instruction 204)
- `794ba1e` (203 Council artifacts)
- `36d53ed` (203 fix)
- `85d87b6` (operator v1.5.9 docs/design; tagged v1.5.8)
- `f0927e8` (operator harness_plans)
- `27e4db7` (202 Council remediation)
- `d2fd31f` (202 build)
- + `2c290a1` (operator release close-out docs)

Plus this synthesis-and-artifacts commit will follow.

## Methodology generalization

The 204 fix closes a UX defect that's structurally similar to the 199-followup-1 mock-reality divergence pattern: the docstring claimed one behavior (`no-args = full publish`), the code did another (`no-args = print intro`), and NO flag in the CLI semantically meant "yes do the live upload." The pattern: any script with both a destructive and a safe mode must have an explicit flag for the destructive mode — not "absence of safe flag = destructive." Future publish-channel scripts (Homebrew, Docker, Conda, etc.) should adopt the same `--dry-run` XOR `--publish` structure from the start, not retrofit it after first publish attempt.

After 204 lands on origin/1.5.8, the v1.5.8 close-out can proceed to step 3 (live publishes) per `ai_context/DEVELOPMENT_PROCESS.md` § "Release close-out sequence" — operator runs `bin/publish_pip.py --dry-run` then `--publish`, then npm, then awesome-copilot.
