## Phase 6: Verify

**v1.5.7 instrumentation:** Append `phase_start phase=6` now. At phase end, cross-validate (`quality/BUGS.md` non-empty with `^## BUG-` sections AND `quality/INDEX.md` updated with `gate_verdict` field) then append `phase_end phase=6`. After Phase 6 closes, append `run_end status=success` (or `aborted` / `failed` if applicable).

> **Required references for this phase:**
> - `references/verification.md` — 45 self-check benchmarks

**Why a verification phase?** AI-generated output can look polished and be subtly wrong. Tests that reference undefined fixtures report 0 failures but 16 errors — and "0 failures" sounds like success. Integration protocols can list field names that don't exist in the actual schemas. The verification phase catches these problems before the user discovers them, which is important because trust in a generated quality playbook is fragile — one wrong field name undermines confidence in everything else.

**Phase 6 execution model: incremental, not monolithic.** Phase 6 runs as a series of independent verification steps, each reading only the file(s) it needs, checking one thing, and writing its result to `quality/results/phase6-verification.log` before moving to the next step. Do NOT load all artifacts into context at once. Do NOT try to hold the full verification checklist in memory while reading artifacts. Each step below is self-contained — read the file, check the condition, append the result, drop the context.

### Step 6.1: Mechanical Verification Closure (mandatory first step)

If `quality/mechanical/` exists, the **literal first action** of Phase 6 is:

```bash
bash quality/mechanical/verify.sh > quality/results/mechanical-verify.log 2>&1
echo $? > quality/results/mechanical-verify.exit
```

Execute this command in the shell. Do not substitute a Python script, do not read the artifact file and assert on its contents, do not skip this step. The command must be `bash quality/mechanical/verify.sh` — not `python3 -c "..."`, not `cat quality/mechanical/... | grep ...`, not any other equivalent.

Record the exit code. If non-zero, **Phase 6 fails immediately.** Do not proceed to further steps. Go back to the extraction step: delete the mismatched `*_cases.txt`, re-run the extraction command with a fresh shell redirect, re-verify, and update all downstream artifacts that cited the old extraction.

Record in PROGRESS.md under `## Phase 6 Mechanical Closure` and append to `quality/results/phase6-verification.log`:
```
[Step 6.1] Mechanical verification: PASS (exit 0)
```

**Why this is non-substitutable:** In v1.3.23, the model replaced `bash verify.sh` with `python3 -c "from pathlib import Path; ..."` that read the (forged) artifact file and asserted on its contents — a circular check that passed despite the artifact being fabricated. The only trustworthy verification is re-running the same shell pipeline that produced the artifact and diffing the results. Any other method can be fooled by a corrupted intermediate file.

### Step 6.2: Run quality_gate.py (script-verified checks)

Run the mechanical validation gate:

```bash
python3 quality_gate.py . > quality/results/quality-gate.log 2>&1  # locate via fallback (six canonical layouts, in order): quality_gate.py, .claude/skills/quality-playbook/quality_gate.py, .github/skills/quality_gate.py, .cursor/skills/quality-playbook/quality_gate.py, .continue/skills/quality-playbook/quality_gate.py, .github/skills/quality-playbook/quality_gate.py
echo $? >> quality/results/phase6-verification.log
```

Read `quality/results/quality-gate.log`. If it reports any FAIL results, fix each failing check before proceeding. The most common FAILs are: (1) missing `quality/patches/BUG-NNN-regression-test.patch` files, (2) non-canonical JSON field names like `bug_id` instead of `id`, (3) missing `confirmed_open` in the TDD summary, (4) writeups without inline fix diffs, (5) missing TDD red/green log files. Do not proceed until `quality_gate.py` exits 0.

Append to `quality/results/phase6-verification.log`:
```
[Step 6.2] quality_gate.py: PASS (exit 0) — N checks passed, 0 FAIL, 0 WARN
```

This step covers verification benchmarks: 14 (sidecar JSON), 17 (test file extension), 18 (use case count), 20 (writeups), 23 (mechanical artifacts), 26 (version stamps), 27 (mechanical directory), 29 (triage-to-BUGS sync), 34 (BUGS.md exists), 38 (individual auditor reports), 39 (BUGS.md heading format), 40 (artifact file existence), 41 (sidecar JSON validation), 42 (script-verified closure), 43 (use case identifiers), 44 (regression-test patches), 45 (writeup inline diffs).

**v1.5.3 Layer-1 invariants also run here.** `quality_gate.py` additionally enforces schemas.md §10 invariants #1–#18 (summarized in Phase 5 above). In particular, the script re-runs `bin/citation_verifier.extract_excerpt` per schemas.md §5.4 on every Tier 1/2 citation and rejects any stored `citation_excerpt` that does not byte-equal the freshly-extracted output — this is the post-ingest tampering catch. If any Layer-1 invariant fails here, fix the underlying manifest record (not the gate, not the excerpt) and re-run.

### Step 6.3: Test execution verification

Run the functional test suite. Read only `quality/test_functional.*` to determine the test command:

- **Python:** `pytest quality/test_functional.py -v 2>&1 | tail -20`
- **Java:** `mvn test -Dtest=FunctionalTest` or `gradle test --tests FunctionalTest`
- **Go:** `go test -v` targeting the generated test file's package
- **TypeScript:** `npx jest functional.test.ts --verbose`
- **Rust:** `cargo test`
- **Scala:** `sbt "testOnly *FunctionalSpec"`

Check for both failures AND errors. Errors from missing fixtures, failed imports, or unresolved dependencies count as broken tests. Expected-failure (xfail) regression tests do not count against this check.

Append to `quality/results/phase6-verification.log`:
```
[Step 6.3] Functional tests: PASS — N tests, 0 failures, 0 errors
```

This covers benchmarks 8 (all tests pass) and 9 (existing tests unbroken).

### Step 6.4: Verification checklist — file-by-file checks

Process the remaining verification benchmarks from `references/verification.md` in small batches. For each batch, read only the file(s) needed, check the condition, and append the result. **Do not read more than 2 files per batch.**

**Batch A — QUALITY.md (benchmarks 1-2, 10):** Read `quality/QUALITY.md`. Count scenarios. Verify each scenario references real code (grep for cited function names). Append results.

**Batch B — Functional test file (benchmarks 3-7):** Read `quality/test_functional.*`. Check cross-variant coverage (~30%), boundary test count, assertion depth (value checks vs presence checks), layer correctness (outcomes vs mechanisms), mutation validity.

**Batch C — Protocol files (benchmarks 11-13):** Read `quality/RUN_CODE_REVIEW.md`, then `quality/RUN_INTEGRATION_TESTS.md`, then `quality/RUN_SPEC_AUDIT.md` — one at a time. Check each is self-contained and executable. Verify Field Reference Table in integration tests.

**Batch D — Regression tests (benchmarks 15-16, 24):** Read `quality/test_regression.*` if it exists. Verify skip guards reference bug IDs, verify patch validation gate commands, verify source-inspection tests don't use `run=False`.

**Batch E — Enumeration and triage checks (benchmarks 19, 21-22, 25, 36):** Read `quality/code_reviews/*.md` (just the enumeration sections). Read `quality/spec_audits/*triage*` (just the verification probe sections). Check two-list comparisons, executable probe evidence, no circular mechanical artifact references, contradiction gate.

**Batch F — Continuation mode (benchmarks 32-33):** Only if `quality/SEED_CHECKS.md` exists. Read it, verify mechanical execution, verify convergence section in PROGRESS.md.

Append each batch result to `quality/results/phase6-verification.log`:
```
[Step 6.4A] QUALITY.md scenarios: PASS — 8 scenarios, all reference real code
[Step 6.4B] Functional test quality: PASS — 30% cross-variant, assertion depth OK
[Step 6.4C] Protocol files: PASS — all self-contained and executable
[Step 6.4D] Regression tests: PASS — all skip guards present
[Step 6.4E] Enumeration/triage: PASS — two-list checks present, probes have assertions
[Step 6.4F] Continuation mode: SKIP — no SEED_CHECKS.md
```

If any batch fails, fix the issue immediately before proceeding to the next batch.

### Step 6.5: Metadata Consistency Check

Read `quality/PROGRESS.md` (just the metadata and artifact inventory sections). Then spot-check:
- The requirement count is consistent across REQUIREMENTS.md header, PROGRESS.md artifact inventory, and COVERAGE_MATRIX.md header. All three must state the same number.
- The `With docs` field accurately reflects whether `reference_docs/` exists
- The Terminal Gate Verification section is present and filled in

Then read `quality/COMPLETENESS_REPORT.md` (just the verdict section). Verify no stale pre-reconciliation text remains — if both a `## Verdict` and an `## Updated verdict` (or `## Post-Review Reconciliation`) section exist, **delete the original `## Verdict` section entirely**. The final document must have exactly one `## Verdict` heading.

Append to `quality/results/phase6-verification.log`:
```
[Step 6.5] Metadata consistency: PASS — requirement counts match, version stamps consistent
```

If any metadata is stale, fix it now.

### Checkpoint: Finalize PROGRESS.md

Re-read `quality/PROGRESS.md`. Update:
- Mark Phase 6 (Verification benchmarks) complete with timestamp
- Verify the BUG tracker has closure for every entry
- Add a final summary line: "Run complete. N BUGs found (N from code review, N from spec audit). N regression tests written. N exemptions granted."
- **Print the suggested next prompt to the user (mandatory, all runs).** This applies to EVERY run, including baseline — it is not iteration-specific. Print the following block so the user can copy-paste it to start the next iteration:

  For a baseline run (no iteration strategy):
  ```
  ────────────────────────────────────────────────────────
  Next iteration suggestion:
  "Run the next iteration of the quality playbook using the gap strategy."
  ────────────────────────────────────────────────────────
  ```

  For iteration runs, use this mapping to determine the next strategy:
  - **gap** → suggest unfiltered
  - **unfiltered** → suggest parity
  - **parity** → suggest adversarial
  - **adversarial** → suggest "Run the quality playbook from scratch." (cycle complete)

The completed PROGRESS.md is a permanent audit trail. It documents what the skill did, what it found, and how it resolved each finding. Users can read it to understand the run, debug failures, and compare across runs.

### Convergence Check (continuation mode only)

> **Scope:** This subsection only. The suggested-next-prompt step above is unconditional and must execute on every run regardless of whether this convergence check is skipped.

**This step runs only if Phase 0 executed** (i.e., `quality/SEED_CHECKS.md` exists from prior-run analysis). If this is a first run with no prior history, skip to Phase 7.

Compare this run's bug list against the seed list:

1. **Count net-new bugs:** bugs in this run's BUGS.md that do NOT match any seed (by file:line). A bug is "net-new" if it was not found in any prior run.
2. **Count seed carryovers:** seeds that were re-confirmed in this run (FAIL result in Step 0b).
3. **Count seed resolutions:** seeds that are now passing (bug was fixed since prior run).

Write a `## Convergence` section to PROGRESS.md:

```markdown
## Convergence

Run number: N (N prior runs in quality/previous_runs/)
Seeds from prior runs: S (S confirmed, R resolved)
Net-new bugs this run: K
Convergence: [CONVERGED | NOT CONVERGED]

Net-new bugs:
- BUG-NNN: [summary] (file:line) — not in any prior run
```

**Convergence criterion:** The run is converged if **net-new bugs = 0** — every bug found in this run was already known from a prior run. This means further runs are unlikely to find additional bugs in the declared scope.

**If CONVERGED:** Print to the user: "This run found no new bugs beyond the N already known from prior runs. Bug discovery has converged for this scope. Total confirmed bugs across all runs: T." Then proceed to Phase 7.

**If NOT converged — automatic re-iteration.** When the convergence check shows net-new bugs > 0 and the iteration count has not reached the maximum (default: 5), the skill re-iterates automatically:

1. Record the iteration number and net-new count in PROGRESS.md.
2. Archive the current `quality/` directory via `bin/run_playbook.archive_previous_run(repo_dir, timestamp)` (or `bin.archive_lib.archive_run()` at Phase 6 success). These snapshot `quality/` into `quality/previous_runs/<timestamp>/quality/` and write the per-run `INDEX.md` plus a `RUN_INDEX.md` row.
3. Restart from **Phase 0** (which will now find the newly archived run in `quality/previous_runs/`).
4. Print to the user: "Iteration N found K net-new bugs. Archiving and starting iteration N+1 (max M)."

The iteration counter starts at 1 for the first run. Each archive-and-restart increments it. When the counter reaches the maximum, stop iterating even if not converged and print: "Reached maximum iterations (M) without convergence. K net-new bugs found in the last run. Total confirmed bugs across all runs: T."

**Iteration limits.** The default maximum is 5 iterations. If the user's prompt includes an explicit limit (e.g., "run the playbook with 3 iterations"), use that limit instead. If the user's prompt says "single run" or "no iteration," skip re-iteration entirely and treat NOT CONVERGED the same as the pre-iteration behavior: print the net-new count and suggest re-running.

**Context window awareness.** If at any point during re-iteration you detect that your context window is substantially consumed (e.g., you are producing noticeably shorter or lower-quality output than earlier iterations), stop iterating, write the current state to PROGRESS.md, and print: "Stopping iteration due to context constraints. Completed N of M iterations. Re-run the playbook to continue — Phase 0 will pick up the seed list from quality/previous_runs/." This is a safety valve, not a target — most codebases converge in 2-3 iterations.

**Why this matters:** A single playbook run explores a subset of the codebase non-deterministically. The first run on virtio might find BUG-001 and BUG-004 but miss BUG-005. The second run might find BUG-005 and BUG-006. By the third run, if no net-new bugs appear, the exploration has likely covered the high-value territory. The seed list ensures previously found bugs are never lost between runs, and the convergence check tells the user when additional runs have diminishing returns. Automatic re-iteration means the skill is self-contained — callers don't need external scripts or manual re-runs to achieve convergence.

**End-of-phase message (mandatory — print this after Phase 6 completes, then STOP):**

```
# Phase 6 Complete — All Phases Done

The quality playbook baseline run is complete. Here's the summary:

[Include: total confirmed bugs, quality gate pass/fail/warn counts,
list of all bug IDs with one-line summaries and severities.]

Key output files:
- quality/BUGS.md — all confirmed bugs with spec basis and patches
- quality/results/tdd-results.json — structured TDD verification results
- quality/patches/ — regression test and fix patches for every bug

You can now run iteration strategies to find additional bugs. Iterations typically
add 40-60% more confirmed bugs on top of the baseline. The recommended cycle is:
gap → unfiltered → parity → adversarial.

To run all four iterations automatically, say:

    Run all iterations.

I'll orchestrate each strategy as a separate sub-agent with its own context window.

To run one iteration at a time, say:

    Run the next iteration of the quality playbook.

Or ask me about the results: "Tell me about BUG-001" or "Which bugs are highest priority?"

After you fix the bugs, say "recheck" to verify the fixes were applied correctly.
```

**After printing this message, STOP. Do not proceed to iterations unless the user explicitly asks.**

**End-of-iteration message (mandatory — print this after each iteration completes, then STOP):**

```
# Iteration Complete — [Strategy Name]

[Summarize: N net-new bugs found in this iteration, total now at N.
List new bug IDs with one-line summaries.]

[If there are remaining strategies in the recommended cycle, suggest the next one:]
The next recommended strategy is [next strategy]. To run it, say:

    Run the next iteration using the [next strategy] strategy.

[If all four strategies have been run:]
All four iteration strategies have been run. Total confirmed bugs: N.
You can review the results, ask about specific bugs, or re-run any strategy.

After you fix the bugs, say "recheck" to verify the fixes were applied correctly.

Or say "keep going" to run the next iteration automatically.
```

**After printing this message, STOP. Do not proceed to the next iteration unless the user explicitly asks.**

---
