{skill_fallback_guide}

You are a quality engineer continuing a phase-by-phase quality playbook run. Phases 1-4 are complete.

Read these files to get context:
1. quality/PROGRESS.md - run metadata, phase status, cumulative BUG tracker
2. quality/BUGS.md - all confirmed bugs from code review and spec audit
3. quality/REQUIREMENTS.md - derived requirements
4. SKILL.md - read the Phase 5 section ("Phase 5: Post-Review Reconciliation and Closure Verification"). Also read references/requirements_pipeline.md, references/review_protocols.md, and references/spec_audit.md. Resolve SKILL.md and the references/ directory via the documented fallback list above; do NOT assume any single install layout.

Execute Phase 5: Reconciliation + TDD + Closure.

1. Run the Post-Review Reconciliation per references/requirements_pipeline.md. Update COMPLETENESS_REPORT.md.

   **Canonical verdict shape (v1.5.7 Fix 8, mandatory).** COMPLETENESS_REPORT.md must end with a canonical verdict block in exactly this shape — no variants:

   ```markdown
   ## Verdict

   PASS
   ```

   or

   ```markdown
   ## Verdict

   FAIL
   ```

   Rules:
   - The heading must be exactly `## Verdict` (level-2 ATX heading, capital V, no trailing punctuation or qualifier).
   - The next non-blank line must be exactly `PASS` or `FAIL` — uppercase, no markdown emphasis, no surrounding words ("Passed", "PASS!", "**PASS**" are all rejected by the gate).
   - Optional explanatory prose may follow on subsequent lines, but the first non-blank line after the heading is the verdict.
   - `## Verdict` must be the LAST level-2 heading in the file. No `## Postmortem`, `## Appendix`, or other `## ` sections may follow it. The Phase 6 gate's `check_verdict_shape` enforces terminal position via instruction 032 NCF-1 hardening (`quality_gate.py` line range `678-723`); a trailing `## ` heading after the verdict block fails the gate with "`## Verdict` is not the last level-2 heading".
   - Do NOT leave placeholder text like "verdict is rendered after Phase 6" or "verdict will be determined later". The Phase 6 gate's `check_verdict_shape` fails on placeholder phrases and on any verdict line that isn't exactly `PASS` or `FAIL`.

   This shape replaces the historical permissive variants (`## Status`, `VERDICT: PASS`, prose-only verdicts) that the gate tolerated through v1.5.6. The strict shape gives operators a single grep target and gives the gate something concrete to enforce.
2. Run closure verification: every BUG in the tracker must have either a regression test or an explicit exemption.
3. Write bug writeups at quality/writeups/BUG-NNN.md for EVERY confirmed bug. The canonical template is the "Bug writeup generation" section of SKILL.md (resolve via the fallback list above) — read that section before writing. Use the exact field headings listed there: **Summary, Spec reference, The code, Observable consequence, Depth judgment, The fix, The test, Related issues**. Sections 1–4, 6, 7 are required in every writeup; section 5 (Depth judgment) fires only when the consequence isn't self-evident from the immediate code; section 8 (Related issues) is included only when related bugs exist. Do NOT introduce fields that aren't in the template (no "Minimal reproduction" as a top-level field, no "Patch path:" as a top-level field — those belong inside Spec reference and The test respectively).

   **MANDATORY HYDRATION STEP.** Before writing a writeup, re-open quality/BUGS.md and locate the `### BUG-NNN:` entry for the bug you are about to write up. Every confirmed bug in BUGS.md already has the content you need — your job is to copy it into the writeup's sections, not to invent it. If a field is missing from BUGS.md, that is a reconciliation error to surface in PROGRESS.md, not a field to fabricate. Use this field map:

   | BUGS.md field              | Writeup section              | How to use it                                                                 |
   |----------------------------|------------------------------|-------------------------------------------------------------------------------|
   | Title line (### BUG-NNN:…) | Summary                      | One sentence naming the function/code path and the observable failure.        |
   | Primary requirement        | Spec reference               | `- Requirement: REQ-NNN`                                                      |
   | Spec basis                 | Spec reference               | `- Spec basis: <doc path + line range(s), semicolon-separated if multiple>` plus a ≤15-word contract quote copied verbatim from the cited lines. |
   | Location                   | The code                     | Cite `file:line` and describe what the current path does there.               |
   | Minimal reproduction       | Observable consequence       | Weave into the consequence paragraph as the triggering input.                 |
   | Expected + Actual behavior | Observable consequence       | The actual behavior is the observable failure; the expected defines the gap.  |
   | Regression test            | The test                     | `- Regression test: <function name>` — verbatim from BUGS.md.                 |
   | Patches (regression)       | The test                     | `- Regression patch: <path>` — verbatim from BUGS.md.                         |
   | Patches (fix)              | The fix + The test           | If a fix patch file exists, read it and paste the unified diff inside ```diff; also list the patch path as `- Fix patch: <path>` under The test. If no fix patch exists (confirmed-open bug), write the minimal concrete unified diff directly in The fix anyway — SKILL.md requires an inline diff in every writeup. In the no-patch case, omit the `Fix patch:` bullet from The test. |
   | Red/green logs             | The test                     | `- Red receipt: quality/results/BUG-NNN.red.log` and the matching green path. |

   **Worked example.** The BUGS.md entry for BUG-004 is:

       ### BUG-004: naive upstream timestamps crash ETA math
       - Source: Code Review
       - Severity: HIGH
       - Primary requirement: REQ-006
       - Location: bus_tracker.py:138-144
       - Spec basis: quality/REQUIREMENTS.md:163-172; quality/QUALITY.md:57-65
       - Minimal reproduction: Return a visit whose ExpectedArrivalTime is an ISO string
         without timezone information, such as 2026-04-21T12:00:00.
       - Expected behavior: The affected arrival degrades to unknown-time while the rest
         of the stop remains usable.
       - Actual behavior: datetime.fromisoformat() returns a naive datetime and
         subtracting it from datetime.now(timezone.utc) raises TypeError, aborting the
         stop/request path.
       - Regression test: quality.test_regression.TestPhase3Regressions.test_bug_004_fetch_stop_arrivals_degrades_naive_timestamps
       - Patches: quality/patches/BUG-004-regression-test.patch, quality/patches/BUG-004-fix.patch

   The hydrated writeup sections look like this (sketch — paste the real diff from the
   fix patch file into ```diff, don't make one up):

       ## Summary
       fetch_stop_arrivals() crashes the whole stop/request path when an upstream visit
       carries a naive ExpectedArrivalTime, instead of degrading that arrival to
       unknown-time.

       ## Spec reference
       - Requirement: REQ-006
       - Spec basis: quality/REQUIREMENTS.md:163-172; quality/QUALITY.md:57-65
       - Behavioral contract quote: "degrade a bad per-arrival timestamp to unknown-time instead of aborting the whole response path"

       ## The code
       At bus_tracker.py:138-144, the parser calls datetime.fromisoformat(...) on
       ExpectedArrivalTime and subtracts the result from datetime.now(timezone.utc)…

       ## Observable consequence
       When the upstream visit returns ExpectedArrivalTime="2026-04-21T12:00:00"
       (no timezone), fromisoformat() returns a naive datetime, the subtraction
       raises TypeError, and the entire stop/request path aborts rather than the
       single affected arrival degrading to unknown-time.

       ## The fix
       ```diff
       <paste the real unified diff from quality/patches/BUG-004-fix.patch here>
       ```

       ## The test
       - Regression test: quality.test_regression.TestPhase3Regressions.test_bug_004_fetch_stop_arrivals_degrades_naive_timestamps
       - Regression patch: quality/patches/BUG-004-regression-test.patch
       - Fix patch: quality/patches/BUG-004-fix.patch
       - Red receipt: quality/results/BUG-004.red.log
       - Green receipt: quality/results/BUG-004.green.log

   **Confirmation checklist (per writeup, before moving to the next bug).** (a) Every
   required section has populated content copied from BUGS.md or the patch files —
   no empty backticks, no sentinel filler like "is a confirmed code bug in ``" or
   "The affected implementation lives at ``" or "Patch path: ``". (b) The ```diff
   fence contains at least one `+` or `-` line from the actual fix patch. (c) The
   Summary names a real function or code path, not the BUG identifier. (d) No
   angle-bracket placeholders (e.g., `<...>`) remain in the final writeup — those are
   pedagogical markers from the worked example and from SKILL.md, never acceptable
   output.
4. Run the TDD red-green cycle. **Probe the test runner FIRST (v1.5.7 089o):** run the runner's version probe (`mvn -version`, `pytest --version`, `cargo --version`, `go version`, etc.) and capture stdout+stderr+exit code to `quality/results/phase5_env.log` before any red/green/NOT_RUN determination — this artifact is required (the gate FAILs without it when bugs exist). Then for each confirmed bug, run the regression test against unpatched code -> quality/results/BUG-NNN.red.log. If a fix patch exists, run against patched code -> quality/results/BUG-NNN.green.log. If the probe **succeeded**, you MUST actually execute the tests — a `RED`/`GREEN` first-line tag asserts the test was really run, and a by-inspection prediction under a `RED`/`GREEN` tag is an overclaim that FAILs the gate. **Use the runner's default (online) mode (v1.5.7 089p):** run the test runner the way it resolves dependencies normally (plain `mvn test`, `pytest`, `cargo test`, `go test`) so it can fetch from its standard remote (Maven Central, PyPI, crates.io, the Go module proxy). Do NOT pass `-o`/`--offline`/cache-only flags by default — your Bash tool has the operator's network. If a run fails on dependency resolution while offline, retry once in online mode before concluding anything; a missing dependency the remote can supply is NOT grounds for `NOT_RUN`. Create the log with `NOT_RUN` on the first line **only if** the **online** attempt (probe or test run) itself exited non-zero AND no alternative runner is reachable — and quote that failing online output in the log. "I assumed it wasn't available" / "I assumed the network was restricted" / "by inspection" is not acceptable evidence; recording `NOT_RUN` while `phase5_env.log` shows the runner available FAILs the gate.

   **v1.5.7 090o — build-prep before the red/green (the Keto cold-cache fix).** After the probe succeeds AND before executing the red/green cycle for any bug, **prepare the build environment using the detected build system** so the test runner can actually execute within the step's time budget. Use whichever ecosystem-appropriate "fetch deps + compile without running tests" recipe matches the target:
   - **Go:** `go mod download` (fetch modules — this is what timed out on the 2026-05-24 Keto Mode-A run fetching `modernc.org/libc` indirectly via `modernc.org/sqlite`), then a compile warm-up such as `go test <pkg> -run '^$' -count=1` or `go build ./...` so the heavy deps compile once **before** the timed red/green step.
   - **Node:** `npm ci` (or `npm install`) before the test runner.
   - **Python:** `pip install -e .` / `pip install -r requirements*.txt` as applicable.
   - **Rust:** `cargo fetch`, then `cargo build` / `cargo test --no-run`.
   - **Java (Maven/Gradle):** offline dependency resolution / a no-test compile (`mvn -DskipTests install -o`, `gradle build -x test --offline`, etc.).
   - **Other ecosystems:** the analogous "fetch deps + compile without running tests" step.

   **CRITICAL: run the build-prep under the SAME environment the red/green will use.** If the red/green step uses a dedicated cache (e.g. `GOCACHE=/private/tmp/qpb-gocache`), warm THAT cache — warming the global cache alone is insufficient. Match `GOCACHE` / `CARGO_HOME` / `PIP_CACHE_DIR` / `M2_HOME` / etc. byte-for-byte between the prep step and the red/green step. The Keto run observed exactly this trap: a global-cache warm-up didn't help because the red/green ran with a per-run `GOCACHE` and re-fetched everything.

   **v1.5.7 090o — environment-failure remediation (do NOT degrade silently).** If, AFTER the prep attempt, the test runner STILL cannot execute because of an **environment/build problem**, emit a specific remediation block to chat and record an honest `NOT_RUN` receipt with an environment reason — never quietly fall back to patch-apply verification, never claim GREEN by inspection. Environment shapes that qualify for this path (and ONLY these):
   - dependency **download or network timeout** (e.g. `dial tcp ...: i/o timeout` fetching modules);
   - dependency **compile failure in a third-party module** (e.g. cgo failure inside `modernc.org/libc`);
   - **missing toolchain** (`command not found`, `bash: go: No such file or directory`);
   - cache/permission errors that prevent the runner from starting at all.

   The remediation block (emit to chat, NOT to the receipt log) MUST contain:
   - **what failed** — the runner + the specific dep/toolchain, quoted from the runner's error output;
   - **the exact fix command(s)** — e.g. *"run `go mod download && go build ./...` in the repo, then re-run Phases 5–6"* / *"install Go ≥1.21 from https://go.dev/dl/, then re-run Phases 5–6"*;
   - **the explicit instruction to re-run Phases 5–6** after the fix.

   Record the TDD receipt honestly per the existing 089m–q taxonomy: `NOT_RUN` on the first line of `quality/results/BUG-NNN.<red|green>.log` with the environment reason and the quoted runner error in the body (the 089o probe contract + the 089m–q honesty-not-overclaim taxonomy are unchanged by this — the addition is the prep attempt and the actionable remediation message; the receipt-acceptance behavior for the verdict is unchanged).

   **v1.5.7 090o — THE GUARD (load-bearing safety constraint): never excuse a genuine RED as "environment".** Build-prep + environment-remediation apply **ONLY** to the four environment shapes listed above, keyed off the runner's error output. **An assertion failure is a RED, not an environment failure.** When the test runner EXECUTED and a test assertion failed / the test returned a non-zero result on its own logic — that is exactly the signal the red phase is supposed to produce, and it MUST be reported as a real `RED` first-line receipt. Never reclassify an assertion failure as "environment"; never give a real RED the remediation-and-skip path; never excuse a real RED as a build/dep problem. The 089m–q TDD-credibility arc exists precisely to stop agents laundering failures into passes — this guard is the load-bearing constraint that 090o adds to the prep+remediation path so the prep doesn't open the laundering hole back up.

   Decision rule for the agent: if you see an assertion-failure / test-logic error (e.g. `assertEqual(...) failed`, `expected X got Y`, `FAIL: TestFoo`, `panic: ... in your_module/...`), that is a RED — record `RED` on the first line and quote the assertion output. If you see an environment-shaped error from the list above, that is the remediation path — record `NOT_RUN (environment: <reason>)` and emit the remediation block. When in doubt, default to RED (treat as a real test result) — the safety direction is "never launder."

   **v1.5.7 090g — green-phase apply→run→revert (Mode A
   compiled-language fix).** The canonical red-green protocol is an
   apply→run→revert cycle, with `git apply -R` mandatory after EACH
   log capture so the source tree is left in its pre-cycle state:

       RED:   git apply quality/patches/BUG-NNN-regression-test.patch
              <runner> ... > quality/results/BUG-NNN.red.log  (first line `RED`)
              git apply -R quality/patches/BUG-NNN-regression-test.patch
              git status   # confirm clean (non-quality/) tree
       GREEN: git apply quality/patches/BUG-NNN-regression-test.patch
              git apply quality/patches/BUG-NNN-fix.patch
              <runner> ... > quality/results/BUG-NNN.green.log  (first line `GREEN`)
              git apply -R quality/patches/BUG-NNN-fix.patch
              git apply -R quality/patches/BUG-NNN-regression-test.patch
              git status   # confirm clean (non-quality/) tree

   The run-end clean-tree check (`bin.run_state_lib.
   validate_no_source_edits`) is the hard backstop: if any non-
   `quality/` path is left dirty at run end the run aborts with
   `run_end status=aborted`. Apply-and-LEAVE is forbidden;
   apply-then-revert is permitted and expected. The SKILL.md
   source-edit guardrail was rewritten in 090g to make this
   explicit (was "must NOT apply" — the OpenFGA 2026-05-23
   dogfood agent read it literally and gate-FAILed every Mode-A
   run on Go/Java/Rust).

   **Co-located-test languages (Go `internal/` packages, Java,
   Rust):** the regression test MUST live in the source tree
   (e.g. `internal/authn/oidc/oidc_test.go`) to reach unexported
   code under test — a `quality/`-only reconstruction tests a
   copy, not the real code path, and is a weaker proof. The
   apply→revert flow is exactly what makes a real co-located
   test safe (it's reverted before run end). Prefer the real
   co-located test + revert over a `quality/` reconstruction
   when the runner is available.

   **v1.5.7 090g — patches must `git apply --check` clean.** Every
   emitted regression-test and fix patch in `quality/patches/`
   MUST pass `git apply --check <patch>` before being treated as
   final. The agent SHOULD self-verify each patch with
   `git apply --check` against the unpatched tree before
   finalizing; if a patch reports "corrupt patch at line N" or
   any other check failure, regenerate it in-run (do not defer
   the corruption to the operator). A non-applyable patch is a
   Phase 5 defect to fix here, not a handoff item. The OpenFGA
   2026-05-23 dogfood emitted patches with "corrupt patch at line
   61" that broke both the apply→revert cycle AND the operator
   handoff — the self-check would have caught it.

   **Alternative — ephemeral `git worktree`.** When you'd rather
   not touch the live source tree at all (e.g. an interpreted
   language where a `quality/`-only test exercises the real code
   path), validate in a disposable worktree: `git worktree add
   /tmp/qpb-validate-<bug-id> HEAD` → apply the regression-test
   patch → run (RED) → apply the fix patch → run (GREEN) →
   `git worktree remove /tmp/qpb-validate-<bug-id>`. This was the
   pre-090g recommendation and remains valid; the apply→revert
   pattern above is recommended when co-located tests are
   required (compiled languages with unexported APIs). The
   2026-05-18 Claude Code Opus 4.7 cobra run validated 5 bugs
   via the worktree approach.
5. Generate sidecar JSON: quality/results/tdd-results.json and quality/results/integration-results.json (schema_version "1.1", canonical fields: id, requirement, red_phase, green_phase, verdict, fix_patch_present, writeup_path).
6. If mechanical verification artifacts exist, run `python quality/mechanical/verify.py` and save receipts.
7. Run terminal gate verification, write it to PROGRESS.md.

### MANDATORY CARDINALITY GATE (Lever 3, v1.5.2)

Before finalizing this phase, run the cardinality reconciliation gate against the current repo state. Locate `quality_gate.py` via the same fallback list used for SKILL.md (it sits in the same directory as SKILL.md in every install layout), then invoke it as a script — `quality_gate.py` runs `check_v1_5_2_cardinality_gate(repo_dir)` as part of its standard pass:

    python3 <resolved_quality_gate_path> .

Where `<resolved_quality_gate_path>` is the first hit when walking the documented install-location fallback list, with `SKILL.md` swapped for `quality_gate.py` (e.g., `quality_gate.py`, `.claude/skills/quality-playbook/quality_gate.py`, `.github/skills/quality_gate.py`, `.cursor/skills/quality-playbook/quality_gate.py`, `.continue/skills/quality-playbook/quality_gate.py`, `.github/skills/quality-playbook/quality_gate.py`, `.codex/skills/quality-playbook/quality_gate.py`, `.windsurf/skills/quality-playbook/quality_gate.py`, `.cline/skills/quality-playbook/quality_gate.py`, `.aider/skills/quality-playbook/quality_gate.py`).

If the gate output contains any line beginning with `cardinality gate:`, or reports uncovered cells, malformed cell IDs, missing consolidation rationale on multi-cell Covers, or malformed downgrade records, STOP. Fix the BUGS.md entries or the `compensation_grid_downgrades.json` file. Do NOT proceed to completion until those failure lines no longer appear.

For every pattern-tagged REQ, the Phase 5 contract is:
- Every grid cell with `"present": false` appears in either a BUG's `Covers:` list or a downgrade record.
- Every `Covers:` entry uses the canonical cell ID form `REQ-N/cell-<item>-<site>`.
- Every BUG with ≥2 `Covers:` entries has a non-empty `Consolidation rationale:` line.
- Every downgrade record has `cell_id`, `authority_ref`, `site_citation`, `reason_class` (in the enum), `falsifiable_claim` (non-empty).

The cardinality gate is blocking. It is intentionally stricter than the Phase 3 advisory self-check; the advisory check is meant to surface problems early, but Phase 5 is where they become fatal.

### STEP — Write quality/INDEX.md (v1.5.7 A-15)

`quality/INDEX.md` is required on every run (schemas.md §10 invariant #10 / §11). In **Mode B** the runner/orchestrator emits it (it alone tracks phase timing + model assignments). In **Mode A** there is no runner — YOU must write it now, in Phase 5, before closing the phase. Write `quality/INDEX.md` as markdown containing a single fenced ` ```json ` block carrying the schemas.md §11 fields:

- `schema_version`: `"2.0"` (new runs MUST emit `"2.0"` — `"1.0"`/absent is the archived-legacy read path only).
- `run_timestamp_start`, `run_timestamp_end`: ISO 8601 with explicit timezone (Z preferred) — the run's actual start (when Phase 1 began) and now.
- `duration_seconds`: integer, end − start.
- `qpb_version`: from SKILL.md `metadata.version`.
- `target_repo_path`: the target repo path. `target_repo_git_sha`: `git rev-parse HEAD` (or `"unknown"` for non-git targets).
- `target_role_breakdown`: do NOT hand-author — derive from the normalized role map via the canonical helper:

      python3 -c "import sys, json; sys.path.insert(0, 'bin'); import role_map; rm = role_map.load_role_map('quality/exploration_role_map.json'); print(json.dumps(role_map.role_breakdown_for_index(rm)))"

- `phases_executed`: array of `{phase_id, model, start, end, exit_status}` — one entry per phase you ran (`model` = the model you are; `exit_status` = `"success"`).
- `summary`: object with `requirements` (counts by tier), `bugs` (counts by severity/disposition), and `gate_verdict` (`"pending"` now — Phase 6 updates it to `pass`/`partial`/`fail`).
- `artifacts`: array of the relative artifact paths produced this run.

Compute fields with Python where possible; do NOT hand-write counts. After writing INDEX.md, run the Phase 5 artifact-contract validator and quote its final `RESULT:` line verbatim in your chat output (it matches `RESULT: VALIDATION PASSED (phase 5)` or `RESULT: VALIDATION FAILED (phase 5 — X FAIL, Y PASS)` — VALIDATION FAILED means your artifacts violate the contract; fix them per the `FAIL:` messages above and re-run until VALIDATION PASSED):

    python3 -m bin.validate_phase_artifacts . --phase 5

Resolve `bin/` via the documented install-root fallback (`PYTHONPATH=<install_root>` for an `install_skill.py`-layout adopter). Exit 0 is required to proceed; a non-zero exit means INDEX.md is missing or missing required §11 fields — fix and re-run. This closes the 2026-05-16 express opus-4.6 Mode-A defect where INDEX.md was never written (no runner — Mode A), the gate FAILED on §10 invariant #10, and the agent reported PASS anyway.

Mark Phase 5 complete in PROGRESS.md (use the checkbox format `- [x] Phase 5 - Reconciliation` — do NOT switch to a table).

IMPORTANT: quality_gate.py will FAIL Phase 5 if any writeup is missing a non-empty ```diff block or contains any of these sentinel phrases verbatim: "is a confirmed code bug in ``", "The affected implementation lives at ``", "Patch path: ``", "- Regression test: ``", "- Regression patch: ``". Those two checks are the hard gate. Skipping the BUGS.md hydration step above is not gate-enforced but will produce writeups that read as unpopulated stubs and fail a human review — do not skip it.

After completing this phase, emit `## What just happened` + `### What to do next` as the LAST visible output in chat per the decision tree at `references/what_just_happened.md`. Use the State P5 template (Phase 5 just completed; next is Phase 6).
