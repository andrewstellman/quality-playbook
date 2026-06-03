# Quality Playbook — Bug-Report PR Automation (v1.6.x candidate)

*Status: NEW v1.6.x track, opened **2026-05-29**. Owner: Andrew Stellman. Depends on: v1.5.7 (shipping — gives us BUGS.md + `quality/patches/` artifact structure that this feature consumes). Not coupled to v1.6.0's NFR-discovery + FP-audit work; can ship in any order.*

*Motivated by the keto BUG-001 finding from the 2026-05-29 acceptance retest. That bug — gRPC/HTTP unknown-namespace parity in `internal/check/handler.go` — has a clean QPB-produced regression test, an obvious five-line fix, and the entire PR workflow ahead of it is mechanical. Doing it by hand is fine for one bug; doing it by hand for every QPB-derived finding across a 12-repo track-record campaign is not. The operator workflow is captured in `Quality Playbook/v1.5.7_runner/BUG_REPORT_WORKFLOW.md` (the two-commit red-then-green pattern); this feature is the automation of that workflow as a QPB subcommand.*

---

## ⚠️ Read this first — the problem

QPB v1.5.7 has produced everything needed to file high-quality bug-fix PRs:

- `quality/BUGS.md` enumerates the confirmed bugs with title, severity, source, file:line references, regression test patch path, and (sometimes) fix patch path.
- `quality/patches/BUG-NNN-regression-test.patch` is the load-bearing artifact — a failing test that *demonstrates* the bug in the upstream tree.
- `quality/patches/BUG-NNN-fix.patch` (when produced) is the source change that closes the regression test.
- The handwritten `BUG_REPORT_WORKFLOW.md` describes how to assemble these into a two-commit (red-then-green) PR by hand.

The gap is the assembly itself: every QPB-found bug currently requires the operator to clone the upstream repo, create a branch, apply the test patch, run the test to confirm it's red, commit, apply the fix patch, run the test to confirm it's green, run the broader suite to confirm no regressions, commit, push, and open the PR with the right body. Each of those steps is mechanical given the artifacts QPB already produces; *all* of them being manual is the friction that keeps the bug-report rate low.

The proposed feature replaces the manual assembly with a QPB subcommand that performs every step deterministically, with halts at any failure (test doesn't go red on commit 1, test doesn't go green on commit 2, broader suite regresses, push fails, PR creation fails). The operator stays in the loop for the *decisions* (which bugs to submit, how to handle a halt) and out of the loop for the *clerical work* (apply, test, commit, push).

---

## What the feature delivers

A new subcommand — working title `qpb submit-pr` or `qpb_harness submit-pr` (TBD; see "Open questions") — that takes a QPB run directory and one or more bug IDs, and produces a two-commit-per-bug PR on a fresh branch of the upstream repo.

### Operator-facing shape

```bash
# Single bug
qpb submit-pr <run-dir> --bug BUG-001

# Multiple bugs in one PR
qpb submit-pr <run-dir> --bug BUG-001 --bug BUG-003

# All confirmed bugs (with both test and fix patches)
qpb submit-pr <run-dir> --all

# Dry-run: do everything except push and PR-create
qpb submit-pr <run-dir> --bug BUG-001 --dry-run

# Explicit fork override (when the operator pushes to their fork, not upstream)
qpb submit-pr <run-dir> --bug BUG-001 --fork andrewstellman/keto
```

### What it does (high level)

1. **Read the run.** Parse `quality/BUGS.md` + `quality/bugs_manifest.json`; enumerate confirmed bugs and verify the requested bug IDs are present with the required patches.
2. **Materialize an upstream clone.** Either re-use the run's `target/` (clean state required) or fresh-clone the upstream repo into a working dir. Operator preference; default fresh-clone.
3. **Create the branch** — `fix/qpb-<bug-id>` for single-bug; `fix/qpb-<run-timestamp>-<n>-bugs` for multi-bug. Configurable.
4. **For each bug, in the order given:**
   a. Apply `BUG-NNN-regression-test.patch`.
   b. Detect the project's test runner (see "Test runner detection" below) and run the targeted test.
   c. **Verify RED.** If the test passes, the bug is not present at HEAD — halt with an actionable message ("expected the test to fail; it passed — bug may already be fixed upstream").
   d. Commit with the templated message (see `BUG_REPORT_WORKFLOW.md` Step 2).
   e. Apply `BUG-NNN-fix.patch`. If the fix patch wasn't produced by QPB, halt with the bug description and ask the operator to hand-author the fix (interactive mode) or skip the bug (batch mode).
   f. Re-run the targeted test. **Verify GREEN.** If it still fails, halt with the test output ("fix did not close the regression").
   g. Run the broader package/module test suite. **Verify no regressions.** If any other test regresses, halt with the diff.
   h. Commit with the templated message.
5. **Push the branch** to the configured remote (the operator's fork by default; upstream if the operator has push rights and `--push-upstream`).
6. **Create the PR** via `gh pr create` (or the GitLab/Gitea equivalents — see "VCS host coverage").
   - Title: from the bug entries (single bug: bug's suggested title; multi-bug: a roll-up).
   - Body: assembled from `BUG_REPORT_WORKFLOW.md`'s PR template — the per-bug Summary/Reproduction/Expected/Actual/Evidence sections concatenated, plus the two-commit-callout block, plus the discovery-context line.
7. **Report.** Print the PR URL and the bug-IDs filed to stdout; write a record to `<run-dir>/quality/submitted_prs.json` so a re-run is idempotent (won't re-file a bug that's already been submitted).

### Halt-and-resume

Every halt produces:

- A clear human-readable error explaining what went wrong and what the operator can do.
- A persisted state file (`<run-dir>/quality/submit_pr_state.json`) recording branch name, bugs processed, current bug, current step.
- An instruction for the operator to resume: `qpb submit-pr <run-dir> --resume` continues from the halted step after the operator's fix.

Halts are the load-bearing safety property — the feature never pushes a branch or creates a PR if any verification step failed. The operator gets the artifacts (committed branch on disk, halted state) but the upstream side is untouched until the entire two-commit-per-bug sequence is verified.

---

## Multi-bug mode — design intent

For a single PR carrying N bugs, the commit timeline is:

```
* Commit 2N — fix(check): BUG-N short fix description
* Commit 2N-1 — test(check): demonstrate BUG-N short bug summary
* ...
* Commit 4 — fix(api): BUG-002 short fix description
* Commit 3 — test(api): demonstrate BUG-002 short bug summary
* Commit 2 — fix(check): BUG-001 short fix description
* Commit 1 — test(check): demonstrate BUG-001 short bug summary
```

Each bug retains its own red-then-green pair. The PR body explicitly maps commits to bug IDs:

> This PR closes N bugs found by Quality Playbook v1.x.y. Each bug has its own two-commit red-then-green pair:
>
> | Bug | Test commit | Fix commit |
> |---|---|---|
> | BUG-001 | `<sha-1>` | `<sha-2>` |
> | BUG-002 | `<sha-3>` | `<sha-4>` |
> | …       | …       | …       |
>
> Each test commit's CI run fails specifically on the new test it adds. Each fix commit's CI run passes. Reviewers can checkout any test-commit SHA to reproduce the bug, and the matching fix-commit SHA to see it resolved.

**Why same-PR over per-PR for related bugs:** in practice, multiple bugs found in the same area (e.g., three keto findings in `internal/check/`) are likely to involve overlapping reviewer attention and may share fix patterns. Same-PR keeps that context together. For bugs in unrelated areas, the operator should run `submit-pr` once per bug with `--bug BUG-NNN` to get separate PRs.

The bug ordering is operator-determined (`--bug A --bug B` orders A first; `--all` orders by BUG-ID by default but accepts a `--order <bug-id-list>` override).

---

## Architecture

### Subcommand placement

`qpb_harness submit-pr` is the natural placement — it sits next to `run`, `run-plan`, `status`, `tui`, `kill`. The harness already knows about run directories and their artifact structure (BUGS.md, patches/, etc.); it does NOT need to know anything about the running QPB skill, so the v1.5.7 hands-off-from-shipped-code invariant holds: this is a HARNESS feature operating on QPB OUTPUT.

If we later want operators (not just harness operators) to use this without the harness, we can expose a thin `qpb submit-pr` wrapper that forwards to the harness implementation. v1.6.x scope can defer that.

### Internal modules

- `bin/harness/submit_pr.py` — the orchestrator: parses BUGS.md, enumerates bugs, drives the state machine, persists halt state, formats logging.
- `bin/harness/git_ops.py` — wraps the git operations (clone, apply patch, commit, push) as testable functions. Returns rich result objects (success, error, stderr capture) rather than raising.
- `bin/harness/test_runner_detect.py` — detects the project's test runner (Maven, Gradle, npm, pytest, sbt, dotnet, go, etc.) by inspecting the cloned tree (pom.xml, build.gradle, package.json, pyproject.toml, build.sbt, *.csproj, go.mod). Returns a `TestRunner` strategy with `run_targeted(test_id)` and `run_suite(scope)` methods.
- `bin/harness/vcs_host.py` — wraps `gh pr create` (GitHub), `glab mr create` (GitLab), `tea pull create` (Gitea/Forgejo). Single interface; runtime-selected by the upstream remote URL.
- `bin/tests/harness/test_submit_pr_*.py` — unit tests per submodule + end-to-end golden tests against a synthetic run directory with a synthetic upstream clone.

### Test runner detection

Looking at the v1.6.x candidate language coverage (Java, JS, Python, Scala, TypeScript, C# from the 2026-05-29 bug-report campaign), the detection rules:

| Marker file | Test runner | Targeted command shape |
|---|---|---|
| `pom.xml` | Maven | `mvn -pl <module> -Dtest=<TestClass>#<method> test` |
| `build.gradle` / `build.gradle.kts` | Gradle | `./gradlew :<module>:test --tests "<FQN>.method"` |
| `package.json` with `"test"` script + jest config | Jest | `npx jest <file> -t "<name>"` |
| `package.json` with `mocha` dep | Mocha | `npx mocha <file> --grep "<name>"` |
| `package.json` with `vitest` dep | Vitest | `npx vitest run <file> -t "<name>"` |
| `pyproject.toml` with `[tool.pytest.ini_options]` or `pytest.ini` | pytest | `pytest <file>::<class>::<method>` |
| `pyproject.toml` without pytest config | unittest | `python -m unittest <module.class.method>` |
| `build.sbt` | sbt | `sbt 'testOnly *<TestSpec> -- -z "<frag>"'` |
| `*.csproj` / `*.sln` | dotnet | `dotnet test --filter "FullyQualifiedName~<TestClass>.<method>"` |
| `go.mod` | go test | `go test -run <TestName> ./<pkg>/...` |

Detection runs against the cloned tree. When multiple markers are present (a polyglot repo like Ory keto has both `go.mod` and `package.json`), the rule is: prefer the marker that matches the file paths in `BUGS.md`'s bug entries. The detection is a `TestRunner` strategy object; tests cover ambiguous detection cases.

When detection fails (no recognized marker, or a custom build system), the feature halts with: "could not detect a test runner for this repository. Please re-run with `--test-runner <name>` and the test command pattern (see docs)." The operator-supplied command is then used verbatim.

### Patch application

Use `git apply --3way --index` for tolerance to small drift between QPB's working clone and the upstream HEAD. If `--3way` can't reconcile, halt with the rejected hunks visible for operator intervention.

### Verification of RED on commit 1

After `git apply` of the test patch and `git commit`, run the targeted test. The verification has three possible outcomes:

- **Test fails** (exit code != 0): expected. The bug is present at HEAD; we're good.
- **Test passes** (exit code == 0): unexpected. The bug may have been fixed upstream after the QPB run, or the test may not actually exercise the bug. Halt; the operator must investigate.
- **Test command errored** (test runner not available, target not found, etc.): halt; the operator must fix the environment.

The exact "fails" condition is per-runner; some return non-zero on test failure (most), others (e.g., jest with `--passWithNoTests`) require parsing output. The `TestRunner.run_targeted()` strategy returns a structured result so the orchestrator doesn't have to know exit-code conventions per runner.

### Verification of GREEN on commit 2

After `git apply` of the fix patch and `git commit`, re-run the targeted test (should pass) AND the broader suite (should not regress). The broader suite scope is per-runner:

- Maven/Gradle: the module containing the test.
- npm-based runners: the workspace containing the test (often the whole repo).
- pytest: the directory containing the test file.
- sbt: the project containing the test.
- dotnet: the test project containing the test class.
- go: the package containing the test.

This is a "reasonable default" scope — operators can override with `--suite-scope <path>`.

### Push and PR creation

Push is `git push <remote> <branch>`. Remote selection:

- Default: a `fork` remote pointing at the operator's fork. The feature configures this on first run if absent (interactive prompt, or `--fork <github-user/repo>` flag).
- Optional: `--push-upstream` pushes directly to the upstream's branch. Requires push rights; rare.

PR creation runs `gh pr create --title "..." --body-file <body.md> --base <upstream-default-branch>` (or the GitLab/Gitea equivalent based on the upstream remote URL). The body file is built from the bug entries' BUGS.md content + the `BUG_REPORT_WORKFLOW.md` PR template + the two-commit-callout.

If `gh` (or `glab`, `tea`) is not installed, halt with installation instructions and a fallback: print the title + body to stdout so the operator can paste it into the web UI manually.

---

## Out of scope (for the first slice)

- **Authoring fixes when QPB didn't produce a fix patch.** v1.5.7 sometimes produces only a regression test and not a fix patch (the keto BUG-001 case). The first slice halts in that case, gives the operator the bug description, and asks them to hand-author the fix between commit 1 and commit 2. A later slice could spin up a fresh-context fix-generation sub-agent (similar to v1.6.0's FP-audit pattern but for fix authoring) — that's a substantial feature in its own right.
- **Auto-detecting "this bug is already fixed upstream."** If commit 1's test passes (RED-verification fails), we halt rather than auto-skip. A later slice could check if the upstream's history contains a commit matching the bug description and short-circuit with a "looks like this was fixed upstream — here's the PR/commit reference, skipping." For now, manual investigation.
- **Maintainer-feedback iteration.** PR review may request changes to the test or the fix. The first slice doesn't help with that — the operator uses git directly (the `BUG_REPORT_WORKFLOW.md` Variations section describes how). A later slice could: take review feedback, generate a revised test or fix, amend the appropriate commit, force-push.
- **DCO / CLA handling.** Some upstream repos require Developer Certificate of Origin sign-offs (`git commit -s`) or Contributor License Agreements. The first slice supports `--signoff` to add the sign-off line; CLA bot interactions are operator-side.
- **Pre-flight check against existing issues/PRs.** Searching the upstream issue tracker for duplicates is an operator task (per `BUG_REPORT_WORKFLOW.md` Step 0). A later slice could call the GitHub Search API to flag likely duplicates.
- **VCS host coverage beyond GitHub.** The first slice supports `gh` for GitHub. GitLab (`glab`) and Gitea/Forgejo (`tea`) are sketched in `vcs_host.py` but unimplemented in the first slice; cover them once we have an actual GitLab/Gitea bug to file.
- **Anonymous / no-account submissions.** Some projects accept patches via email (`git send-email`). Out of scope; the first slice requires a GitHub/GitLab/Gitea account.

These are deliberately deferred so the first slice can ship as a clean "the mechanical work is done for you" feature without bloating into a "QPB does everything including authoring your fixes" feature.

---

## Open questions

1. **Subcommand placement: `qpb_harness submit-pr` vs `qpb submit-pr` vs a new tool?** The harness placement is the cleanest given the run-dir + artifact reuse, but the shipped QPB CLI doesn't currently know about runs (only the harness does). Likely answer: ship in the harness for v1.6.x, expose a thin `qpb submit-pr` wrapper later if adopters want it without installing the harness.
2. **Default branch naming scheme.** `fix/qpb-<bug-id>` for single-bug is uncontroversial. Multi-bug naming is harder — `fix/qpb-<run-timestamp>-<n>-bugs` is verbose but unambiguous; alternatives include `fix/qpb-<short-summary>` with a curated summary string. Operator's call via `--branch <name>`.
3. **Should the feature attempt to clone the official upstream when the QPB run was against a fork or pinned SHA?** For the keto BUG-001 case the run was against ory/keto master, so trivially yes. For a pinned-SHA run (gson 27d9ba1), the operator probably wants to file against ory/keto master, not the pinned SHA — but the bug may not exist at master if it's been fixed since. Detection: compare the run's HEAD SHA against `origin/<default-branch>` after fresh-clone; if they diverge, halt and ask the operator to confirm the target.
4. **PR body length for multi-bug.** N bugs concatenated produces a long PR body. Default: full body for N ≤ 3, summary-with-collapsible-details for N > 3 (using GitHub's `<details>` markdown). Operator's call via `--body-mode {full,summary}`.
5. **CI-on-each-commit interpretation.** Some upstream repos run CI only on the PR HEAD, not on intermediate commits. In that case the "red on commit 1, green on commit 2" visual is invisible. The first slice doesn't try to fight this — the two-commit history is still preserved for a reviewer who checks out by hand. A later slice could add a `--squash-on-submit` flag for projects where the upstream actively dislikes multi-commit PRs.

---

## Success criteria for the first slice

- An operator runs `qpb submit-pr <run-dir> --bug BUG-001 --dry-run` against the keto BUG-001 finding and sees: clone created, branch made, commit 1 applied + test RED verified, commit 2 applied + test GREEN verified + broader suite green, would-push, would-create-PR-with-body `<...>`. **No actual push, no actual PR.**
- Dropping `--dry-run` produces an actual PR on a fork (operator's fork of ory/keto) with two commits matching the BUG_REPORT_WORKFLOW.md template.
- The same flow works on a Java repo (gson) via Maven, a JS repo (express) via Mocha, a Python repo (requests) via pytest. (Track-record campaign coverage.)
- Multi-bug mode produces a PR with one branch, 2N commits in the right order, and a body table mapping commits to bugs.
- Halts are clear and resumable. Specifically: kill the process mid-flow → re-run with `--resume` → it continues from the halted step.

---

## Why ship this in v1.6.x

The 2026-05-29 bug-report campaign (gson + jackson-databind + express + lodash + requests + httpx + circe + cats + zod + vitest + AutoMapper + Polly across six languages) is exactly the workload this feature exists to support. Doing the campaign by hand will work — `BUG_REPORT_WORKFLOW.md` lays out the steps — but the friction-per-bug is high enough to cap the campaign's throughput. The feature's payoff scales linearly with the number of bug reports filed; the campaign is the proof of value.

The dependency story is clean: it consumes v1.5.7's BUGS.md + patches/ artifacts, doesn't touch the shipped skill, and doesn't conflict with v1.6.0's NFR/FP-audit work (different layer entirely). It can ship in any v1.6.x slot.
