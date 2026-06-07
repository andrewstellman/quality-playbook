# Synthesis — 206 Worker self-Council (3-panelist)

**SHIP recommendation: YES** — after applying B's CONCERN remediation + C's AUDIT-table elevation pre-push.

## Panel summary

| Panelist | Charter | Initial verdict | After remediation |
|----------|---------|----------------|-------------------|
| A | Automation correctness + step sequence | **SHIP** | (unchanged) |
| B | Destructive-action safety + idempotency | **CONCERN** (step6 diff invisibility) | **SHIP** (step6 reordered: stage before preview) |
| C | Test coverage + AUDIT-table elevation | **CONCERN** (AUDIT elevation warranted) | **SHIP** (sweep test landed) |

Both Panelist A and B required socket-retry due to API errors mid-execution — re-spawned with incremental-write discipline and both completed cleanly on retry.

## Panelist A verdict — automation clean

- All 7 driver steps wire correct subprocess invocations with halt-on-error returncode checks
- Driver returns `EX_SOFTWARE(70)` on first failure
- Step ordering literal (lines 926-934): fork → upstream → branch → copy → npm start → commit/push → PR
- **XOR check (lines 1049-1064) fires BEFORE `_open_log` (line 1104) + BEFORE `write_packet` + BEFORE any subprocess** — no side effect when args invalid
- gh CLI flags all well-formed:
  - `gh auth status`
  - `gh repo fork github/awesome-copilot --clone=true --remote-name origin -- <path>` (the `--` separator passes the clone dir through to git clone)
  - `gh pr create --repo ... --base ... --title ... --body-file ...`
- Branch name `add-{SKILL_NAME}-{version}` (line 923) is pinned by `test_submit_branch_create_uses_versioned_name` to `add-quality-playbook-1.5.8`

### Panelist A NITs (deferred)
- A-NIT1: step3 reuse path doesn't check `r_br.returncode` (operator-visible fallthrough, not silent)
- A-NIT2: step5's "README.md not modified" condition is a warning that continues (acceptable given step6 tolerates "nothing to commit")
- A-OBS: driver actually wires 7 steps (PR-open is its own confirmable step), not 6 as the build agent's note said. Charter orderings still map cleanly.

## Panelist B verdict — destructive-action safety + idempotency

### Destructive-action gates (all present)

| Op | Gate? | Location | State-on-N message |
|----|-------|----------|--------------------|
| `git push` | y/N + diff preview | step6 | "operator declined commit+push; SKILL.md was copied + npm start ran" (updated post-fix) |
| `gh pr create` | y/N + title/base/body | step7 | Hands operator a literal `gh pr create …` rescue command (gold-standard) |
| `git remote set-url upstream` | y/N (only when upstream mismatch) | step2 | Operator-visible state msg |
| `git reset --hard upstream/staged` | y/N (only when branch diverges) | step3 | Operator-visible state msg |

### Idempotency (all dimensions detected)

- Packet generated → re-uses; fork cloned → skips `gh fork`; node_modules → skips `npm install`; upstream remote → skips re-add; branch exists → reuses; file copy → no-op; partial commit → "nothing to commit" treated as success.

### Panelist B CONCERN (B-C1) — RESOLVED PRE-PUSH

**Issue**: `step6_commit_and_push` at L809 ran `git diff --stat` (no ref) BEFORE `git add`. Git semantics: this shows only modifications to already-tracked files and omits untracked. The brand-new `skills/quality-playbook/SKILL.md` (just written by `step4_copy_skill_md` into a freshly-created subdirectory) is untracked when the diff runs, so it does NOT appear in the preview shown to the operator. **Operator sees only the README.md row and approves the push without seeing the headline file.** B verified empirically with a sandbox repro at `/tmp/diff-test`.

**Resolution**: Reordered step6 — `git add` runs FIRST (idempotent on already-staged paths), then `git diff --stat --cached` shows the STAGED changes (which includes the new SKILL.md). The y/N prompt follows the now-accurate preview. The N-confirmation halt message also updated to reflect the new state: "changes are now staged in the fork; no commit was made. Re-run --submit to retry, or `git reset HEAD` in the fork to un-stage and inspect." Docstring documents the fix + cites Panelist B + instruction 206.

10/10 `SubmitFlagTests` still pass after the reorder (test_submit_skips_push_on_n_confirmation only asserts `git push` and `git commit` are NOT called on N — which still holds; the test doesn't assert about git add ordering).

### Panelist B NITs (deferred)
- B-NIT1: step2 N-halt message doesn't explicitly state on-disk state
- B-NIT2: step3 N-halt message doesn't explicitly state on-disk state
- B-NIT3: step3 divergence prompt doesn't show diverging-commits preview
- B-NIT4: no pre-flight duplicate-PR detection
- B-NIT5: `"nothing to commit"` substring match is locale-dependent

## Panelist C verdict — Tests + AUDIT-table elevation

### Test-method audit (10/10 + mutation)

- All 10 `SubmitFlagTests` methods at `bin/tests/test_submit_awesome_copilot.py:285-684`; 10/10 in 0.040s; assertions real not tautological
- Mutation verification independently re-performed: deleted XOR gate at lines 1047-1064, purged pycache, both gate tests failed (`AssertionError: 0 != 64` and `70 != 64`); restored via `shutil.copy2` from `/tmp/qpb_206_panel_c_snapshot.py` + pycache purge; 10/10 green; `git diff --stat` empty. Orchestrator's report confirmed.
- `--help` documents `--dry-run`, `--submit`, `--fork-path` with mutual-exclusion clauses
- Empirical fork-path-missing run: rc=70, halted at step 1 `gh auth status` on unauthenticated host

### Panelist C CONCERN (C-C1) — AUDIT-table elevation RESOLVED PRE-PUSH

**Issue**: Per `ai_context/DEVELOPMENT_PROCESS.md:116-139`, the AUDIT-table invariant test pattern uses 3 confirmed reuses as the elevation threshold + imperative "must" language:

> "the fix is incomplete unless it includes an exhaustive-sweep invariant test."

Three sites now share the XOR-affirmation contract:
- `publish_pip.py:614` (instruction 204)
- `publish_npm.py:542` (instruction 204)
- `submit_awesome_copilot.py:1049` (instruction 206)

All three policy criteria are met. The fix is incomplete without the sweep test.

**Resolution**: NEW `bin/tests/test_release_affirmation_sweep_206.py` with explicit AUDIT table (`RELEASE_AFFIRMATION_AUDIT`) + 6 invariant tests:
- `test_each_module_declares_ex_usage_64` — each module's EX_USAGE == 64
- `test_each_module_registers_dry_run_flag` — each module's `parse_args(["--dry-run"])` succeeds + sets `args.dry_run=True`
- `test_each_module_registers_live_affirmation_flag` — each module's `parse_args(["--<live>"])` succeeds + sets `args.<live>=True`
- `test_each_module_no_args_returns_zero` — each module's `main()` returns 0 on no-args (intro path)
- `test_each_module_both_flags_returns_ex_usage_mutually_exclusive` — each module's main rejects both-flags with EX_USAGE + stderr contains "mutually exclusive"
- `test_audit_table_size_matches_known_sites` — sweep-guard for size drift

Each test uses `unittest.subTest` to parametrize over `RELEASE_AFFIRMATION_AUDIT` so adding a new release-channel script is a single-row edit. 6/6 pass; 3 sites × 5 site-level invariants = 15 effective assertions plus the size-guard.

### Panelist C NITs (deferred)
- C-NIT1: argparse rc=2 vs EX_USAGE 64 for unknown flags (instruction allowed either; build agent went with argparse standard)
- C-NIT2: sweep test could also assert each module emits "must pass --dry-run or --<live>" on neither-flag case (deferred — current tests cover both-flags + no-args which form an XOR-shape proof together)
- C-NIT3: future bullet-proofing — add a CI hook that runs the sweep test on every commit touching `bin/publish_*.py` or `bin/submit_*.py`

## Key panel agreements

1. **All 7 automation steps wire correctly** (A); **all destructive ops gated** (B); **all 10 SubmitFlagTests + AUDIT sweep pass** (C)
2. **XOR check fires before any side-effect** — no log file, no subprocess on invalid args
3. **gh CLI flags well-formed** — fork + auth status + pr create syntax all match real gh
4. **B's step6 diff-invisibility bug** was a real defect (verified empirically by B; operator would have approved push without seeing the headline file). Resolved by staging before preview.
5. **AUDIT-table elevation warranted** per the policy's 3-instance threshold. Sweep test landed.
6. **Mutation-bite verified twice** (orchestrator + Panelist C). Both reproduced the failure trace.
7. **Test coverage**: 29 in `test_submit_awesome_copilot.py` (19 prior + 10 SubmitFlagTests) + 6 in NEW sweep test = 35 total.

## Recommendation

**SHIP** — after applying B's step6 reorder + C's AUDIT sweep test pre-push.

Push to origin/1.5.8 requires **operator confirmation** per instruction's "Done definition": "No push to origin without operator approval. Worker commits to 1.5.8 branch and STOPs at 'ready to push.' Andrew confirms before push."

## Operator notes — bundled changes in c0dd3e0

The build agent's `git commit` bundled the operator's pre-staged edits to `README.md` (28 lines), `ai_context/DEVELOPMENT_CONTEXT.md` (12 lines), and `ai_context/TOOLKIT.md` (2 lines) alongside the 206 work. The commit subject describes only the 206 fix; the file list in `git show --stat c0dd3e0` shows all 5 files. These appear to be the operator's in-progress release-tooling docs refresh aligning with the close-out sequence step 4 (README/TOOLKIT install instructions update). Left as-is rather than rewriting history.

## v1.5.x polish backlog (11 NITs from 206 Council)

From A (2): step3 returncode check; step5 README-modified warning verbosity.
From B (5): step2/3 N-halt state messages; step3 divergence preview; pre-flight duplicate-PR detection; locale-dependent "nothing to commit" match.
From C (3): argparse rc=2 vs EX_USAGE 64; sweep test could add neither-flag assertions; CI hook for sweep test.
From A (1): driver is 7 steps not 6 (observation, not bug).

(Plus 36 prior NITs from 202+203+204+205 backlog.)

## Methodology echo

The 206 fix completes the publish-channel hardening arc started by 202:
- 202 created scripts → 203 fixed prepack stdout pollution → 204 added explicit affirmation → 205 added OTP for 2FA → **206 automated awesome-copilot + elevated affirmation invariant to AUDIT-table form**.

Three sites now share the contract; the AUDIT sweep test (`test_release_affirmation_sweep_206.py`) becomes the regression net for any future release-channel script. Adding the 4th channel (Homebrew, Docker, Conda, etc.) is a single-row edit to `RELEASE_AFFIRMATION_AUDIT` — the invariant tests extend automatically.
