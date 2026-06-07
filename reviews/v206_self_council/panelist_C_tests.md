# Panelist C — Test coverage + empirical + AUDIT-table elevation

QPB instruction 206, HEAD `c0dd3e0`, branch `1.5.8`.

## 1. Charter recap

Verify that the 10 new `SubmitFlagTests` methods exist and assert documented behavior, that the build agent's mutation test is reproducible, that `--help` and an empirical fork-path-missing run behave as documented, and — most importantly — make the call on whether the now-triplicated `--dry-run` XOR live-flag affirmation pattern crosses the AUDIT-table elevation threshold defined in `ai_context/DEVELOPMENT_PROCESS.md` § "AUDIT-table invariant test pattern (v1.5.7 184+)".

## 2. Test-method-presence table

`bin/tests/test_submit_awesome_copilot.py` — `SubmitFlagTests` (line 285) — 10 methods, all run green in this session (`Ran 10 tests in 0.040s — OK`).

| # | Method                                                | Line  | Asserts                                                                                            |
|---|-------------------------------------------------------|-------|----------------------------------------------------------------------------------------------------|
| 1 | `test_no_args_prints_intro_and_exits_zero`            | 329   | rc=0; intro banner contains version, `--dry-run`, `--submit`.                                       |
| 2 | `test_dry_run_and_submit_mutually_exclusive`          | 339   | `--dry-run --submit` returns `EX_USAGE`; stderr contains "mutually exclusive".                       |
| 3 | `test_neither_flag_errors_with_must_affirm`           | 346   | `--dest <td>` alone returns `EX_USAGE`; stderr contains "must pass --dry-run or --submit".          |
| 4 | `test_submit_calls_gh_fork_when_fork_path_missing`    | 358   | Exactly 1 `gh repo fork` call to `AWESOME_COPILOT_REPO` when fork-path absent; rc=`EX_SOFTWARE` after declining commit gate. |
| 5 | `test_submit_skips_fork_when_path_exists`             | 413   | Zero `gh repo fork` / `gh auth status` calls when fork-path has `.git/` + `package.json`; rc=`EX_SOFTWARE`. |
| 6 | `test_submit_branch_create_uses_versioned_name`       | 455   | Exactly 1 `git checkout -b add-quality-playbook-1.5.8 upstream/staged`.                              |
| 7 | `test_submit_halts_when_npm_start_fails`              | 502   | npm-start rc=2 ⇒ no `git commit` / `git push` calls; rc=`EX_SOFTWARE`.                              |
| 8 | `test_submit_skips_push_on_n_confirmation`            | 544   | `_confirm` returns False at commit gate ⇒ no commit, no push; rc=`EX_SOFTWARE`.                     |
| 9 | `test_submit_skips_pr_create_on_n_confirmation`       | 583   | `_confirm` True/False ⇒ exactly 1 push, zero `gh pr create`; rc=`EX_SOFTWARE`.                       |
| 10| `test_submit_logs_redacted_pr_url_on_success`         | 623   | All gates Yes ⇒ rc=`EX_OK`; exactly 1 `gh pr create --repo <repo> --base staged …`; PR URL surfaces to both stdout and log file. |

All 10 are real assertions on documented behavior (not tautologies). No charter gaps.

## 3. Mutation verification — independent re-perform

I took a fresh snapshot at `/tmp/qpb_206_panel_c_snapshot.py` (the orchestrator's `/tmp/qpb_206_ac_snapshot.py` had been cleaned up by the OS). I then deleted the entire XOR gate block at `bin/submit_awesome_copilot.py:1047-1064` (both `if args.dry_run and args.submit` and `if not args.dry_run and not args.submit` branches), purged `bin/__pycache__/submit_awesome_copilot*.pyc`, and re-ran the two XOR tests:

```
FAIL: test_dry_run_and_submit_mutually_exclusive
AssertionError: 0 != 64
FAIL: test_neither_flag_errors_with_must_affirm
AssertionError: 70 != 64
Ran 2 tests in 2.796s — FAILED (failures=2)
```

Both failed with the gate removed — `--dry-run --submit` fell through to dry-run path (rc=0, matching the orchestrator's `0 != 64`), and `--dest <td>` alone fell through to live submission, halting at step 1 gh-auth check (rc=70=`EX_SOFTWARE`). Test 3 catches a slightly different downstream failure than test 2 but still flips from `EX_USAGE` to non-`EX_USAGE`, which is what the assertion pins.

Restored via `python3 -c "import shutil; shutil.copy2('/tmp/qpb_206_panel_c_snapshot.py', '…/bin/submit_awesome_copilot.py')"` + `bin/__pycache__` purge, re-ran the full `SubmitFlagTests` class: 10/10 pass. `git diff --stat bin/submit_awesome_copilot.py` is empty. Orchestrator's mutation report is confirmed.

## 4. `--help` empirical

`python3 bin/submit_awesome_copilot.py --help` (output abridged):

```
usage: submit_awesome_copilot [-h] [--dest DEST] [--dry-run] [--submit]
                              [--fork-path DIR]
  --dry-run        Generate the submission packet only. No fork, no push, no
                   PR. Mutually exclusive with --submit.
  --submit         Generate the packet AND automate steps 1-6 of
                   MANUAL_STEPS.md (fork+clone, upstream remote+fetch, branch,
                   copy SKILL.md, run `npm start`, commit+push, open PR) with
                   confirmation prompts before every destructive action.
                   Mutually exclusive with --dry-run.
  --fork-path DIR  Local clone of the operator's awesome-copilot fork. If the
                   directory doesn't exist and --submit is used, the script
                   offers to fork+clone via `gh repo fork`. Default:
                   ~/Documents/awesome-copilot-fork.
```

`--submit`, `--dry-run`, `--fork-path` all documented with mutual-exclusion clauses. Help text is accurate.

## 5. Empirical fork-path-missing run

`echo "n" | python3 bin/submit_awesome_copilot.py --submit --fork-path /tmp/no-such-dir`:

```
Pre-flight: version-string parity...
Version parity OK at 1.5.8.
Submission packet generated at: …/dist/awesome_copilot_submission
[…] Step 1: starting...
[…] Step 1: checking gh auth status...
[…] Step 1: `gh auth status` reports not authenticated. Run `gh auth login` first and re-run --submit.
[…] Step 1: HALT.
EXIT: 70
```

On my host gh is not authenticated, so the script halts at the auth check **before** the `gh repo fork` invocation — exactly the expected fail-safe ordering (auth precondition before the destructive fork+clone). `/tmp/no-such-dir` was never created. This is one notch upstream of the build agent's "reaches gh-fork prompt" observation (their host had gh logged in), but both empirical runs converge on the same conclusion: with `--fork-path` pointing nowhere, the script correctly walks the fork-creation path and gates it appropriately. No fork was created in either run.

Side observation: the script log goes to `~/.qpb/submit_logs/awesome_copilot_1.5.8_<UTC>.log`. That's fine for ops but the test correctly stubs `_open_log` to avoid polluting `$HOME`.

## 6. AUDIT-table elevation evaluation — the load-bearing call

### The policy (DEVELOPMENT_PROCESS.md § "AUDIT-table invariant test pattern (v1.5.7 184+)", lines 116-139)

The policy defines an elevation threshold:

> "When a defect class shape is observed across multiple sites in the codebase, the fix is incomplete unless it includes an exhaustive-sweep invariant test that scans the entire relevant tree and asserts the contract holds at every site. Has shipped across 184 (`_pid_alive` divergence), 189 (log-read encoding fallback), 190 (subprocess stdin encoding) — **three confirmed reuses graduate it from 'pattern' to 'standard mechanism.'**"

The decision criteria (lines 133-138):

> **When to file an AUDIT sweep test:**
> - The defect class fired **a third time across QPB**. (Two instances may be coincidence; three is a pattern.)
> - The shape is identifiable via mechanical scan (regex, AST, identity-`is` check).
> - A reasonable future PR could re-introduce the same defect at a new site without anyone noticing.

### Counting current sites

Three scripts share the affirmation contract:

| # | File                              | Line | Live flag    | Source of contract        |
|---|-----------------------------------|------|--------------|---------------------------|
| 1 | `bin/publish_pip.py`              | 614  | `--publish`  | Instruction 204           |
| 2 | `bin/publish_npm.py`              | 542  | `--publish`  | Instruction 204           |
| 3 | `bin/submit_awesome_copilot.py`   | 1049 | `--submit`   | Instruction 206 (this one)|

All three implement the identical XOR shape:

```python
if args.dry_run and args.<live>:
    print("ERROR: --dry-run and --<live> are mutually exclusive…", file=sys.stderr)
    return EX_USAGE
if not args.dry_run and not args.<live>:
    print("ERROR: must pass --dry-run or --<live>…", file=sys.stderr)
    return EX_USAGE
```

Each script also has a no-args banner path that returns 0 (the "discoverability invariant" — see `test_publish_pip.py:522` comment "the 089x discoverability invariant: no-args run prints the …").

### Does it cross the threshold?

Apply each of the three policy criteria:

1. **"Fired a third time across QPB"** — **Yes.** Instruction 204 landed the pattern at two sites (publish_pip + publish_npm); 206 lands a third at submit_awesome_copilot. That's exactly the "three is a pattern" trigger from the policy's verbatim language.
2. **"Identifiable via mechanical scan"** — **Yes.** A grep / AST walk of `bin/publish_*.py` and `bin/submit_*.py` (or a wider sweep of any operator-facing top-level entry in `bin/` that accepts destructive operations) can mechanically check that each such script: (a) imports/defines `EX_USAGE = 64`, (b) adds both `--dry-run` and a live flag via argparse, (c) emits the XOR-and-XOR-not gate immediately after `parse_args` and before any side-effect, (d) on no-args prints an intro and returns 0. This is regex-friendly and the AUDIT table is short (3 rows today).
3. **"A reasonable future PR could re-introduce the same defect at a new site without anyone noticing"** — **Yes, and demonstrably.** The next operator-facing publish/submit channel (e.g., `bin/publish_chocolatey.py`, `bin/publish_homebrew.py`, a `--rollback` companion) is going to be added by an LLM-driven instruction. Without a sweep test, that new script could ship without the gate (or with an OR-not-XOR variant) and the regression would only be caught at first operator use — i.e., live publication of a half-baked release. This is precisely the failure mode 204 itself was created to prevent.

### Call: **ELEVATION WARRANTED.**

The pattern is at the elevation threshold the policy specifies in plain text. The orchestrator should land a sweep test, ideally in `bin/tests/test_release_affirmation_sweep_206.py` (or fold into the existing 204-era release tests), that:

- Enumerates the in-scope release/submission scripts as an explicit allow-list (the AUDIT table proper: 3 rows today — pip/npm/awesome-copilot).
- For each, parses/inspects the source to assert:
  - `EX_USAGE = 64` is defined,
  - both `--dry-run` and a live flag are registered on the argparse parser,
  - both XOR branches are present in `main` (`(dry_run AND live) → EX_USAGE` and `(NOT dry_run AND NOT live) → EX_USAGE`),
  - the no-args path returns 0 and prints `--dry-run` and the live flag.
- The AUDIT-table docstring lists each row as `FIXED` with the instruction number.
- Future PRs adding a new `bin/publish_*.py` or `bin/submit_*.py` must either land it with the contract (and add a row) or add a `SAFE-with-justification` / `DEFERRED-with-justification` row — exactly mirroring 189 and 190.

This is the only finding that elevates beyond CONCERN, and it does so because the policy itself names "three" as the graduation count and uses the word **"must"**: *"the fix is incomplete unless it includes an exhaustive-sweep invariant test."* By the policy's own wording, 206 is incomplete without the sweep.

I'm not asking for the sweep test to land in this commit — but I do think Panel C should call it out as the load-bearing follow-on, and the orchestrator should decide whether to land it inside 206 or open it as 207. My recommendation: **land it as part of 206 before merge to main**, because the policy says "the fix is incomplete unless"; merging without it ships an explicitly-incomplete contract.

## 7. Per-finding narrative

### CONCERN-1: Missing AUDIT-table sweep test for the `--dry-run` XOR live-flag affirmation contract

**What.** Three operator-facing scripts (`bin/publish_pip.py:614`, `bin/publish_npm.py:542`, `bin/submit_awesome_copilot.py:1049`) share an identical XOR-affirmation gate shape with identical exit codes (`EX_USAGE=64`), identical error strings ("mutually exclusive", "must pass …"), and identical "no-args → intro → rc=0" discoverability shape. There is no sweep test that mechanically scans for new instances of this contract.

**Why this is incomplete per policy.** `ai_context/DEVELOPMENT_PROCESS.md` lines 116-139 explicitly define the elevation threshold as "three confirmed reuses" and uses imperative language: *"the fix is incomplete unless it includes an exhaustive-sweep invariant test."* All three criteria are met (third instance, mechanically scannable, reasonable future PR could regress).

**Suggested fix.** Add `bin/tests/test_release_affirmation_sweep_206.py` (or analogous filename) with an explicit AUDIT table of the three sites and per-site assertions on `EX_USAGE = 64`, both flags registered, the XOR-and-XOR-not gate present, and the no-args rc=0 discoverability branch. Document in the test's module docstring that future operator-facing release/submission scripts must either match the contract or carry a justified exemption row.

**Severity.** CONCERN — not FIX-REQUIRED because the 10 per-site tests already pin the contract at each existing site (the bug 206 itself was meant to prevent cannot ship today). The risk is forward-looking: the next new publish/submit script could regress the pattern silently. The orchestrator can defensibly land this as 207, but doing so leaves the policy-stated obligation open across a release boundary.

### NIT-1 (mentioned by build agent): `--some-other-flag` returns rc=2 not EX_USAGE=64

I confirmed: `python3 bin/submit_awesome_copilot.py --some-other-flag` → `error: unrecognized arguments: --some-other-flag` → rc=2. This is the standard `argparse` convention (Python documents `parser.error()` as calling `sys.exit(2)`). It's a documented Python behavior, predates `EX_USAGE`'s adoption in QPB, and is consistent across publish_pip and publish_npm too. The build agent's "standard convention" justification is correct; not a finding.

## 8. Optional NITs

- **NIT-2:** the `_print_intro` no-args path is asserted only at the surface level ("contains --submit"). The `test_publish_pip.py:522` "089x discoverability invariant" comment hints at a richer cross-script discoverability shape worth folding into the AUDIT sweep test if it lands.
- **NIT-3:** test 4 (`test_submit_calls_gh_fork_when_fork_path_missing`) asserts on `EX_SOFTWARE` after declining the commit gate, which is good — but the test exercises a 100+ line happy-path mock; if the script's step ordering ever changes, this test will need a rewrite. Not actionable today.
- **NIT-4:** the submit script log writes to `~/.qpb/submit_logs/awesome_copilot_<version>_<UTC>.log` and a real fork-path-missing run on my host left a real log file. Not a test-coverage concern (tests stub `_open_log`), but worth a `--no-log` flag for diagnostic re-runs at some point.

## 9. Final block

```
VERDICT: CONCERN
```

Reasoning: the 10 new tests are correct and mutation-verified; `--help` and the empirical run match documented behavior; the per-site contract is well-pinned. The CONCERN is the missing AUDIT-table sweep test — the policy in DEVELOPMENT_PROCESS.md uses imperative "must" language at the "three instances" threshold that this instruction crosses, and shipping 206 without the sweep test leaves the policy-stated obligation open. Not a FIX-REQUIRED because the per-site tests guard the existing sites; the risk is forward-looking. Orchestrator should either land the sweep in 206 or open 207 with explicit acknowledgement of the deferral.
