# QPB v1.5.5 — Remaining Work (Spec + Plan)

*Self-contained spec and implementation plan for everything left in v1.5.5 after the foundation work currently committed locally on the `1.5.5` branch.*

*Companion to (read first): `QPB_v1.5.5_Design.md` and `QPB_v1.5.5_Implementation_Plan.md`. Those describe the foundation. This doc covers what's left.*

---

## What's already done (foundation, committed locally on the `1.5.5` branch)

Four commits on `1.5.5`, ahead of origin:

- `bf9d399` — v1.5.5 design + implementation plan docs landed in `docs/design/`.
- `91be97f` — `references/run_state_schema.md` (event taxonomy + post-condition rules + format invariants), `bin/run_state_lib.py` (read/validate helpers + `write_progress_md` + `append_event`), `bin/tests/test_run_state_lib.py` (21 tests), `SKILL.md` instrumentation prose at every phase boundary.
- `dc35e9a` — `agents/calibration_orchestrator.md` (the procedure one AI session follows to run a calibration experiment end-to-end).
- `c33cc3c` — Council round 1 fixes: PROGRESS.md initialization conflict resolved, per-phase reminders added, Council mechanics in the orchestrator aligned to `CALIBRATION_PROTOCOL.md`, dangerous `git reset --hard` removed in favor of `git revert`, subprocess invocation pattern documented honestly (spawn-and-resume).

**Status:** `1.5.5` branch HEAD is `c33cc3c`. Origin/1.5.5 is at `3c0ea4f` (the v1.5.4 hotfix). The four commits above need to be pushed before this remaining work begins. Push is operator-side; the bash sandbox can't authenticate.

---

## Remaining items (eight)

| ID | Item | Class |
|---|---|---|
| A | Apply 7 v1.5.4 self-audit bug fixes | Defect remediation |
| B | Phase 5 source-edit guardrail | New post-condition rule + SKILL.md prose |
| C | `AGENTS.md` `quality_gate.sh` → `quality_gate.py` drift fix | Documentation drift |
| D | Resolve 4 pre-existing `test_regression_replay` failures | Test cleanup |
| E | Replace "substrate" jargon throughout docs | Terminology cleanup |
| F | Build four visualization charts | New deliverable |
| G | Run the Pattern 7 displacement-recovery experiment | First calibration cycle using the new procedure |
| H | Mechanical release (version bump, README, tag, push, merge to main) | Release |

---

## Spec

### Item A — Apply 7 v1.5.4 self-audit bug fixes

**What to deliver:** the seven defects identified in the v1.5.4 self-audit (BUG-001 through BUG-007) fixed in the canonical `1.5.5` branch, each with its regression test.

**Source of fixes:** patches already produced by the Codex bootstrap run live at `~/Documents/QPB/repos/quality-playbook-1.5.4-bootstrap/quality/patches/BUG-NNN-fix.patch` and `BUG-NNN-regression-test.patch` for each bug. Defect descriptions live at `~/Documents/QPB/repos/quality-playbook-1.5.4-bootstrap/quality/BUGS.md`.

**The seven defects:**

| ID | Severity | File | Class |
|---|---|---|---|
| BUG-001 | critical | `bin/skill_derivation/runners.py` | Subprocess invocation: CopilotRunner uses argv for the prompt instead of stdin (silent failure for prompts >ARG_MAX) |
| BUG-002 | high | `bin/progress_monitor.py` | Encoding: byte offset used to seek a text-mode file (UTF-8 multi-byte content desyncs the monitor) |
| BUG-003 | high | `bin/progress_monitor.py` | Threading: `_printed_headers` set mutated without lock |
| BUG-004 | high | `agents/quality-playbook-claude.agent.md` | Skill-resolution order disagrees with `bin/run_playbook.py:718-722` |
| BUG-005 | high | `README.md` | Documents `python3 bin/run_playbook.py ...` invocations the runner rejects with `EX_USAGE=64` |
| BUG-006 | high | `SKILL.md` | Tells operators to put docs in `docs_gathered/`; `bin/reference_docs_ingest.py` only reads `reference_docs/` |
| BUG-007 | medium | `bin/quality_playbook.py` | Help text says `quality/runs/` but archive lib uses `quality/previous_runs/` |

**Acceptance criteria:**
- Each fix patch applies cleanly (or is adapted by the implementer if minor adjustment is needed).
- Each regression test patch applies and the test passes.
- The full `bin/tests/` suite passes after all seven fixes are applied.
- Each defect lands as its own commit (or batched by class — see Plan below) with a clear message naming the BUG-NNN, the file, and the failure mode.

**Out of scope:** any fix beyond the seven Codex identified. If the implementer notices an additional defect, file it as a follow-up but do not fix it in this work.

---

### Item B — Phase 5 source-edit guardrail

**What to deliver:** SKILL.md prose at Phase 5 that explicitly tells the AI "patches go to `quality/patches/`, never apply them to source." Plus a new post-condition check that fires if any non-`quality/` file was modified during the run on a self-audit (target == QPB itself).

**Source of finding:** Codex bootstrap run (2026-05-02) went off-rails in Phase 5, edited five source files outside `quality/` before being killed. Documented in `Calibration Cycles/2026-05-02-pattern7-displacement-recovery/` audit if Andrew has logged it; otherwise covered by the chat transcript.

**Acceptance criteria:**
- SKILL.md Phase 5 prose contains an explicit rule: "Patches produced in Phase 5 go to `quality/patches/<BUG-NNN>-fix.patch` as proposed-fix artifacts. Phase 5 must NOT apply patches to source files. Source-tree modifications during a self-audit are a defect, not legitimate audit output."
- A new post-condition check (or extension of an existing one) verifies the constraint. The simplest form: at run end, `git status --porcelain` of the target repo shows only changes inside `quality/` (and any operator-allowed scratch paths). If non-`quality/` files are modified, the run is marked aborted with a clear error event.
- Implementation lives in `bin/run_state_lib.py` (a new helper `validate_no_source_edits(target_dir)` that the playbook calls at run end) plus a one-line SKILL.md instruction to call it.
- Unit test in `bin/tests/test_run_state_lib.py` covers both the clean case (only `quality/` modified) and the violation case (a source file modified).

---

### Item C — `AGENTS.md` `quality_gate.sh` references

**What to deliver:** four references to `quality_gate.sh` in `AGENTS.md` updated to `quality_gate.py` (the actual file).

**Specific lines (from earlier grep):**
- Line 15: file table entry (`| quality_gate.sh | Mechanical validation script | ... |` → `quality_gate.py`)
- Line 32: install command (`cp quality_gate.sh .github/skills/quality_gate.sh` → `cp quality_gate.py .github/skills/quality_gate.py`)
- Line 44: install command (`cp quality_gate.sh .claude/skills/quality-playbook/quality_gate.sh` → `.py` form)
- Line 61: tree diagram (`quality_gate.sh ← artifact validation script` → `.py`)

**Acceptance criteria:**
- All four references updated to `.py`.
- File table description still accurate.
- Tree diagram still readable.

---

### Item D — `test_regression_replay` failures (4 tests)

**What to deliver:** the four pre-existing failures in `bin/tests/test_regression_replay.py` either fixed or deleted.

**Failing tests:**
- `test_chi_1_3_45_legacy_bold_key_still_works` (parser test)
- `test_chi_1_5_1_archive_parses_with_match_keys` (parser test)
- `test_cli_smoke_run_writes_valid_cell` (smoke test)
- `test_full_set_recall_against_historical_baseline_is_perfect` (smoke test)

**Context:** the `bin/regression_replay.py` apparatus was declared dead in v1.5.4 in favor of AI-orchestrated cycles (per `agents/calibration_orchestrator.md`). The orchestrator template still references the recall-computation utility from the same module, so the file itself stays.

**Decision criteria for fix-vs-delete (implementer judgment):**
- If the failures are surface-level (BUGS.md format mismatches, missing fixtures) and fix is small: fix them.
- If the failures point to deeper rot in the apparatus: delete the four failing tests and add a comment to `bin/regression_replay.py` noting the orchestrator pattern is canonical and these recall-computation helpers are utility code, not orchestration code.

**Acceptance criteria:**
- `python3 -m unittest bin.tests.test_regression_replay` either passes or runs without those four tests.
- The recall-computation utility functions in `bin/regression_replay.py` still callable from `agents/calibration_orchestrator.md`'s workflow.

---

### Item E — Replace "substrate" jargon throughout docs

**What to deliver:** "substrate" replaced with plain-English terminology (mostly "infrastructure," sometimes "the underlying procedure" or context-specific phrasing) in every QPB doc and workspace replica.

**Source of finding:** Andrew called out "substrate" as borrowed-from-chemistry jargon. Documented as task #62 in the running task list.

**Files and occurrences (full list):**

In `~/Documents/QPB`:
- `docs/design/QPB_v1.5.5_Design.md`: lines 8, 49, 50, 51, 212, 238, 240
- `docs/design/QPB_v1.5.5_Implementation_Plan.md`: lines 122, 189, 211, 222, 239
- `docs/design/QPB_v1.5.4_Design.md`: lines 90, 114, 118 (Andrew specifically asked for this one)
- `docs/design/QPB_v1.6.0_Design.md`: lines 20, 46, 96, 104
- `docs/design/QPB_v1.6.x_Requirements_Review_Proposal.md`: line 222
- `docs/design/QPB_v1.3.35_Design.md`: lines 21, 171
- `docs/design/QPB_v1.4_Design.md`: lines 175, 187
- `ai_context/CALIBRATION_PROTOCOL.md`: line 532
- `ai_context/IMPROVEMENT_LOOP.md`: lines 7, 15, 178

In `~/Documents/AI-Driven Development/Quality Playbook/`:
- `IMPROVEMENT_LOOP_v1.5.3_misfire_correction.md`: lines 7, 15, 168
- `Calibration Cycles/2026-05-02-pattern7-displacement-recovery/NEXT_STEPS.md`: lines 21, 75
- `CALIBRATION_PROTOCOL.md` (replica): line 532
- `Reviews/QPB_Process_Defect_Baseline.md`: lines 456, 701
- `Reviews/QPB_v1.6.0_Implementation_Plan_Draft.md`: line 20
- `Reviews/QPB_v1.5.4_Council_Synthesis_2026-04-30.md`: line 7
- `Reviews/QPB_v1.5.3_Round3_Review_Prompt.md`: line 19
- `Reviews/QPB_SDLC_Version_History.md`: lines 313, 383
- `Reviews/Requirements_Miss_Archeology.md`: lines 166, 170, 329, 331, 433, 476, 478
- `Reviews/QPB_v1.5.3_Phase3_Brief.md`: line 13
- `Reviews/QPB_v1.6.0_Design_Draft.md`: lines 30, 63, 107
- `Patent/Claims_Gap_Analysis.md`: lines 25, 121, 129, 167, 215

**Preserve (do not change):**
- `docs/bootstrap/Cowork-2026-04-06-Review Quality Playbook v1.3.7 results.md` — uses "substrate" in quoted external content (Tokio's "async execution substrate," virtio's "paravirtualization substrate"). These are quotations from established external CS jargon; preserving the quotation is correct.

**Replacement guidance (context-dependent):**
- "measurement substrate" → "measurement infrastructure"
- "v1.5.5 substrate" / "calibration substrate" / "orchestration substrate" → "v1.5.5 infrastructure" / "calibration infrastructure" / "orchestration infrastructure"
- "the substrate may not cooperate" → "the underlying procedure may not cooperate" or "LLM-driven processes may not cooperate" (depends on what "the substrate" refers to in context)
- Standalone "substrate" referring to an underlying execution layer → "infrastructure" or "the underlying procedure"
- Pattern-category names in `Requirements_Miss_Archeology.md` (like `infeasible-invariant-for-substrate`, `substrate-prevents-testability`): rename to `infeasible-invariant-for-llm` / `language-prevents-testability` (or equivalent context-faithful renames) — these are taxonomy labels, so the rename also needs the inline references to those category names updated.

**Acceptance criteria:**
- `grep -rn "substrate" --include="*.md" ~/Documents/QPB/ ~/Documents/AI-Driven\ Development/Quality\ Playbook/` returns only the preserved-quotation files.
- The replacements read naturally — not "v1.5.5 infrastructure of itself a deliverable" but "v1.5.5's infrastructure is itself a deliverable."

---

### Item F — Four visualization charts

**What to deliver:** `bin/visualize_calibration.py` script that produces four PNG charts from cycle data.

**The four charts:**

1. **Per-bug × cycle heatmap.** Rows = each historical bug (across all benchmarks). Columns = cycles in chronological order. Cells = found (green) / missed (red) / unchanged (gray) / not-applicable (white). Shows displacement: a row that toggles green→red→green is a bug being clawed back and lost again.

2. **Lever × benchmark heatmap.** Rows = lever pulls (from `docs/process/Lever_Calibration_Log.md`). Columns = benchmarks. Cells = recall delta with red/green gradient.

3. **Recall trajectory chart.** Line plot, X = cycle ordinal, Y = recall (0.0-1.0), one line per benchmark, vertical dashed lines at lever-pull cycles with annotations.

4. **Lever interaction graph.** Mermaid `graph LR` syntax. Nodes = levers and patterns. Edges = positive (this lever boosts that one) or negative (this lever displaces that one). Hand-curated based on observed cycle data — initially populated from cycle 1's findings (Pattern 7 boosts mount-context but displaces PathRewrite + AllowContentEncoding). Emit `.mermaid` source; render to PNG via `mermaid-cli` if available, otherwise skip the PNG and document the source-only fallback.

**Inputs the script reads:**
- `Calibration Cycles/*/run_state.jsonl` (cycle history)
- `metrics/regression_replay/*/cell.json` (per-cycle recall data)
- `repos/archive/<bench>/quality/previous_runs/<latest>/quality/BUGS.md` (historical baselines for each benchmark)
- `docs/process/Lever_Calibration_Log.md` (per-cycle lever pulls)

**Outputs:** four PNGs (and one `.mermaid` source) into `Calibration Cycles/<cycle>/visualizations/`.

**Dependencies:** `matplotlib`, `numpy`. Add to a top-of-file requirements comment; the script imports directly. This is not part of the playbook runner; it's a separate analysis utility.

**Acceptance criteria:**
- `python3 -m bin.visualize_calibration <cycle-dir>` produces four PNGs (or three PNGs + one `.mermaid` if `mermaid-cli` not installed) into `<cycle-dir>/visualizations/`.
- Running against `Calibration Cycles/2026-05-01-chi-1.3.45/` (the v1.5.4 cycle 1 data) produces meaningful charts — chi-1.3.45 has both before/after data so the per-bug heatmap shows the displacement story clearly.
- Unit tests in `bin/tests/test_visualize_calibration.py` that produce charts to a tempdir and confirm files appear with non-zero size.

---

### Item G — Pattern 7 displacement-recovery experiment

**What to deliver:** the first end-to-end use of `agents/calibration_orchestrator.md` against a real cycle.

**Cycle setup (already initialized):**
- Cycle directory: `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/`
- `run_state.jsonl` already has `_index` + `cycle_start` events written.
- Lever: lower Pattern 7's budget cap from "3-5 highest-impact composition seams per pass" to "2-3 highest-impact composition seams per pass."
- Benchmarks: chi-1.3.45, chi-1.5.1, virtio-1.5.1, express-1.3.50.
- Iteration: 1 of cap 3.

**Hypothesis:** lowering Pattern 7's budget cap recovers PathRewrite and AllowContentEncoding (the two displacement regressions on chi-1.3.45 from cycle 1) while preserving Pattern 7's mount-context wins.

**Mechanism:** spawn-and-resume per `agents/calibration_orchestrator.md` Step 4 — launch each playbook run in background with `nohup`, return control after capturing PID, re-invoke the orchestrator periodically to advance.

**Acceptance criteria:**
- Cycle reaches a terminal state (`ship`, `revert`, `iterate` with iteration<cap, or `halt-iterate-cap`).
- Audit written at `Calibration Cycles/2026-05-02-pattern7-displacement-recovery/audit.md`.
- Lever Calibration Log entry appended at `docs/process/Lever_Calibration_Log.md`.
- Cell.json files written for each benchmark.
- Visualizations generated (Item F output) for the cycle.

---

### Item H — Mechanical release

**What to deliver:** v1.5.5 tagged on origin, main fast-forwarded, 1.6.0 branch open.

**Steps:**
1. Bump `RELEASE_VERSION` in `bin/benchmark_lib.py` from `1.5.4` to `1.5.5`.
2. Bump SKILL.md frontmatter `version:` from `1.5.4` to `1.5.5`. Bump SKILL.md banner. Bump every `skill_version` JSON example. Bump every "Generated by Quality Playbook" template. (This is the same edit pattern as the v1.5.4 hotfix.)
3. Bump README.md version stamp (line 5).
4. Add a "What's new in v1.5.5" section to README covering: structured logging, post-condition checks, resume capability, calibration procedure, four charts, seven defect fixes, Pattern 7 displacement-recovery cycle outcome.
5. Run `python3 -m unittest discover bin/tests` — must pass (excluding the 4 regression_replay failures only if Item D deleted them).
6. Commit. Tag `v1.5.5`. Push branch. Push tag.
7. Fast-forward `main` to `v1.5.5`. Push `main`.
8. Create `1.6.0` branch from `v1.5.5`. Push.
9. Verify origin via `git ls-remote origin` for `1.5.5`, `v1.5.5`, `main`, `1.6.0`.

**Acceptance criteria:**
- `git ls-remote origin v1.5.5` returns the expected commit SHA.
- `git ls-remote origin main` matches `1.5.5` HEAD.
- `1.6.0` branch exists on origin from the v1.5.5 tag.

---

## Plan

### Sequence

Order: `A` → `B` → `C` → `D` → `E` → `F` → `G` → `H`.

Rationale:
- `A` (defect fixes) and `B` (guardrail) clean up known v1.5.4 issues before any further work — keeps subsequent work running on a debugged baseline.
- `C` (AGENTS.md drift) and `D` (regression_replay tests) and `E` (substrate cleanup) are all hygiene; can land in any order between `B` and `F`.
- `F` (visualizations) needs to land before `G` so the cycle close has charts to generate.
- `G` (cycle) is the longest item — needs ~30 min per benchmark × 8 benchmarks (4 pre-lever + 4 post-lever) = several hours of background playbook runs. Use spawn-and-resume per `agents/calibration_orchestrator.md`.
- `H` (release) ships everything.

### Per-item plan

**A — Apply 7 bug fixes**
- Read `~/Documents/QPB/repos/quality-playbook-1.5.4-bootstrap/quality/BUGS.md` first to understand each defect.
- For each BUG-NNN (1-7):
  1. `cd ~/Documents/QPB && git apply ../repos/quality-playbook-1.5.4-bootstrap/quality/patches/BUG-NNN-fix.patch`. If the patch doesn't apply cleanly, read the patch and the target file, adapt the change manually.
  2. `git apply ../repos/quality-playbook-1.5.4-bootstrap/quality/patches/BUG-NNN-regression-test.patch`. Same fallback.
  3. Run the regression test: `python3 -m unittest <new test name>`. Confirm it passes.
  4. Commit: `git commit -am "v1.5.5 fix: BUG-NNN <one-line summary> (from v1.5.4 self-audit)"`.
- After all seven applied, run the full `bin/tests/` suite. All previously-passing tests should still pass, plus the seven new regression tests.
- Optional batching: BUG-005, BUG-006, BUG-007 are all documentation/help-text drift. Could be one combined commit if preferred.

**B — Phase 5 source-edit guardrail**
- Add `validate_no_source_edits(target_dir: Path) -> tuple[bool, list[str]]` to `bin/run_state_lib.py`. Implementation: shell out to `git status --porcelain` in `target_dir`, parse the output, return `(False, [list of non-quality/ paths])` if any tracked file outside `quality/` is modified, otherwise `(True, [])`.
- Add a unit test in `bin/tests/test_run_state_lib.py` covering both clean and violation cases (use a tempdir with a fake git repo).
- Edit `SKILL.md` Phase 5 prose: add an explicit paragraph "Patches go to `quality/patches/`. Phase 5 must NOT apply patches to source files outside `quality/`. Source-tree modifications during a self-audit are a defect."
- Edit `SKILL.md` run-state instrumentation section to document the post-condition: at run end, call `validate_no_source_edits(target_dir)`. If it returns False, append `error recoverable:false` and abort the run with `run_end status=aborted`.
- Commit: `v1.5.5: Phase 5 source-edit guardrail`.

**C — AGENTS.md drift fix**
- Edit `AGENTS.md`. Four occurrences of `quality_gate.sh` → `quality_gate.py`. Confirm the file table description still reads correctly (was "Mechanical validation script" — should still apply since `quality_gate.py` IS a mechanical validation script).
- Commit: `v1.5.5 docs: AGENTS.md quality_gate.sh → quality_gate.py drift fix`.

**D — regression_replay test failures**
- Run `python3 -m unittest bin.tests.test_regression_replay -v` and read the failure output for each of the four tests.
- For each failure, decide:
  - If it's a small fix (missing fixture, format mismatch the apparatus should tolerate): apply the fix.
  - If it's a deep rot indicator (the apparatus's design assumption no longer holds because the orchestrator pattern superseded it): delete the test and add a comment in `bin/regression_replay.py` noting which functions are still in use as utility code.
- Run the suite again — should pass.
- Commit: `v1.5.5 cleanup: resolve test_regression_replay failures (<fix or delete>)`.

**E — Substrate cleanup**
- Work through the file list in the Spec section systematically.
- For each occurrence: read enough surrounding context to pick the right replacement (usually "infrastructure," sometimes context-specific).
- For `Requirements_Miss_Archeology.md` pattern category names: rename consistently across all references in that file.
- Commit per file or batch by directory: `v1.5.5 docs: replace 'substrate' jargon (<file or batch>)`.
- Verify with: `grep -rn "substrate" --include="*.md" ~/Documents/QPB/ ~/Documents/AI-Driven\ Development/Quality\ Playbook/` returns only the preserved-quotation file.

**F — Visualization charts**
- Create `bin/visualize_calibration.py`. Use matplotlib for charts 1-3 and Mermaid syntax for chart 4.
- Read inputs from the paths listed in the Spec.
- Output to `<cycle-dir>/visualizations/`.
- Add `bin/tests/test_visualize_calibration.py` with the basic "files appear with non-zero size" tests.
- Run against `Calibration Cycles/2026-05-01-chi-1.3.45/` to confirm charts render.
- Commit: `v1.5.5 Phase 4: bin/visualize_calibration.py (4 cycle charts)`.

**G — Pattern 7 cycle**
- Read `~/Documents/QPB/agents/calibration_orchestrator.md` end-to-end.
- The cycle dir at `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/` is already initialized — the `_index` and `cycle_start` events are written. Pre-flight (Step 1) is also done.
- Begin at Step 2 (pre-lever benchmark runs). Use spawn-and-resume.
- Iterate up to cap 3 if needed.
- Write the cycle audit + Lever Calibration Log entry + visualizations at cycle close.
- Commit the cycle's lever change + audit artifacts.

**H — Mechanical release**
- Per the Spec's nine steps. The bash sandbox can't push, so pause at step 6 and surface the push commands to the operator. Verify origin state after the operator confirms they ran the pushes.

### Council review

After Items A through F land (before kicking off G), invoke the Council via parallel sub-agents (three flat lenses: defect-fix correctness, prose-edit clarity, post-condition-check tightness). Apply any P0 findings; iterate up to 2 rounds.

After G's cycle reaches a terminal state, run a focused Council on the cycle's verdict (per `agents/calibration_orchestrator.md` Step 6) before proceeding to H.

### Acceptance for v1.5.5 ship-ready

All of:
- All seven BUG-NNN regression tests pass.
- `validate_no_source_edits` covered by a passing unit test.
- `AGENTS.md` reads `quality_gate.py` everywhere.
- `python3 -m unittest discover bin/tests` passes (or only fails on tests deliberately deleted in Item D).
- `grep -rn "substrate"` returns only the preserved external-quotation file.
- `bin/visualize_calibration.py` produces four outputs against the cycle 1 data.
- The Pattern 7 cycle reached a terminal state with a documented verdict.
- v1.5.5 tagged on origin; main matches; 1.6.0 branch open.

---

## Discipline reminders

- **Verify before claiming.** Don't say "the cycle shipped" without `git log` confirming the commit. Don't say "tests pass" without seeing the test output. (`~/Documents/AI-Driven Development/CLAUDE.md` calibrated-reporting rule.)
- **Read canonical docs before authoring planning content.** Already done for v1.5.5 (this doc IS the canonical for remaining work; the foundation docs are `QPB_v1.5.5_Design.md` and `QPB_v1.5.5_Implementation_Plan.md`).
- **No wall-clock estimates.** When sequencing, use ordinal counts ("three benchmarks remaining") not durations.
- **Council before claiming complete.** P0 findings get applied; iterate as needed.
- **Hand the push to the operator.** Bash sandbox can't authenticate to GitHub.
