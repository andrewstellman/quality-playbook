# Quality Playbook v1.5.9 — Implementation Plan

*Companion to: `QPB_v1.5.9_Design.md`*

*Status: drafted 2026-06-06 (Cowork session ending v1.5.8-era bugspec + gson PR work). Implementation begins after v1.5.8 ships completely.*

*Depends on: v1.5.8 shipped (tag `v1.5.8` on origin, `main` merged, pip + npm published); v1.5.9 Design doc reviewed by operator; Part 1 architectural choice resolved (Cowork recommends C — see Design §1.5); v1.5.9 scope finalized (Section 0 mandatory + operator-selected subset of Part 1 / Part 2).*

*Authorship note: this Implementation Plan was created by Cowork Claude under explicit operator instruction overriding the default "QPB source files are propose-don't-edit" rule. Subsequent edits should follow the normal QPB-source-edit lane (diagnosis + Claude Code worker) per workspace `CLAUDE.md`.*

---

## Operating Principles

(Inherited from v1.5.7 / v1.5.8 implementation plans with v1.5.9-specific updates.)

- **One AI session per implementation phase.** Phases proceed sequentially. State lives in the filesystem.
- **Cowork-orchestrator / Claude-Code-worker pattern is the default execution mode.** v1.5.9's QPB-source edits go through the worker pattern documented in `ai_context/AI_ORCHESTRATION_PATTERNS.md`. Cowork drives planning and Council coordination; the Claude Code worker does the QPB-source edits.
  - **v1.5.9-specific:** worker invocations themselves change as part of Phase 1 (Section 0 substrate). Until Phase 1 ships, worker invocations use the existing `claude --max-turns N -p "$(cat instruction.md)"` pattern. After Phase 1 ships, worker invocations use the paste-buffer-launch pattern designed in §0.2 of the Design doc. Mid-release transition handled in Phase 1's own implementation.
- **Orientation-doc edits use the existing carve-out lane.** No change from v1.5.7/v1.5.8.
- **Each source-edit phase has a Council review.** Three flat lenses per `CALIBRATION_PROTOCOL.md` Mode 1 nested-panel rules from the workspace `CLAUDE.md`. v1.5.9 adds one specific lens: every Council prompt should ask the reviewer to check for residual `claude -p` references in the SKILL.md / phase prompts / reference docs, since Phase 1 changes the substrate.
- **Verify before claiming completion.** Per the workspace `CLAUDE.md` rule. v1.5.9 specifically: don't claim sentinel emission works without confirming an end-to-end harness run wrote a valid `sentinels.ndjson` and the file-watcher correctly classified the events. Direct observation, not inference from "the worker said it works."
- **Patch authoring discipline applies** (Design §4.1). Any patch produced during v1.5.9 work — for QPB source edits, for bugspec spec format generation, for instruction file edits — must be `git apply --check`ed against a temp empty repo before being considered ready.
- **Honest framing on outcomes.** Each phase's audit reports what testing showed, not what makes the phase look complete. A `revert` verdict on any phase is a valid outcome.

---

## Phase 0 — v1.5.8 Stabilization Confirmation

**Goal:** confirm v1.5.8 is fully shipped (origin tag, main merged, pip + npm published, README + TOOLKIT.md current); the working tree is clean; the v1.5.8 chronology in `ai_context/DEVELOPMENT_CONTEXT.md` is current; v1.5.8 pre-publish issues (per instructions 191 / 227) are all resolved or explicitly deferred to v1.5.9 with backlog entries.

**Work items:**

- `git ls-remote origin v1.5.8 1.5.8 main` returns expected SHAs. `v1.5.8` tag on origin matches the post-publish-fix SHA. `1.5.8` branch HEAD is at or past tag with any post-tag fix-up commits applied. `main` is at v1.5.8 release content (per v1.5.8 publish sequence #222-#226).
- pip install verification: `pip install quality-playbook==1.5.8` in a clean venv on Mac and Windows. `qpb --version` prints `1.5.8`.
- npm install verification: `npm install -g quality-playbook@1.5.8`. CLI launches correctly.
- README install instructions current for pip + npm (per task #223).
- `ai_context/DEVELOPMENT_CONTEXT.md` refreshed for the v1.5.8 chronology (instructions 191-227 inclusive plus any v1.5.8 post-ship deferrals).
- v1.5.8 deferrals catalogued: every "deferred to v1.5.9" comment in code, SKILL.md, instructions, or Council synthesis docs is enumerated in this Implementation Plan or in `QPB_v1.5.9_Design.md`. If anything is uncatalogued, Phase 0 surfaces it.

**Council review:** Not required for Phase 0 (it's verification, not source change). Operator confirmation suffices.

**Gate:** Phase 1 cannot begin until Phase 0 completes. If Phase 0 finds v1.5.8 is incomplete in any material way, halt v1.5.9 and return to v1.5.8 publish work.

---

## Phase 1 — Section 0: `claude -p` deprecation workaround (FIRST PRIORITY)

**Goal:** ship the paste-buffer-launch + file-based-sentinel + heartbeat substrate before 2026-06-15. After this phase, QPB harness, runner, and worker invocations all work via the new substrate. Old `claude -p` path is removed; no backward-compatibility flag (per Design §0.6).

**Scope is large.** This is ~6-8 worker instructions worth of work. Break into sub-phases.

### Phase 1A — SKILL.md sentinel contract

**Work items:**

- New §X in SKILL.md titled "Sentinel emission under the QPB harness."
- Conditional check at start of every run: `test -f ./sentinels.ndjson` determines harness vs interactive mode.
- Event schema documented in SKILL.md with examples per event type (per Design §0.3).
- Heartbeat pattern documented: tool_call events serve as liveness signal.
- Mode A handling documented: skip sentinel emission entirely if marker file absent.

**Council review:** Required. Three lenses:

1. SKILL.md prose clarity (would an agent unfamiliar with QPB correctly understand the contract from the new §X alone?)
2. Mode A regression check (does the conditional correctly let Mode A skip emission without overhead?)
3. Sentinel emission completeness (are the 7 required event types all specified with clear "when emitted" rules?)

**Output artifacts:**

- SKILL.md updated.
- Example `sentinels.ndjson` file in `examples/` showing the expected output of one full successful run.
- `bin/tests/test_sentinels.py` — unit test for schema validation of the example file.

### Phase 1B — `bin/sentinels.py` module

**Work items:**

- New module: schema definition (Pydantic v2 models for each event type — reuse the bugspec spec.py pattern).
- Emission helper: `emit_event(event_type, payload)` that the playbook's helper scripts can call. Validates payload against schema and appends one NDJSON line to `./sentinels.ndjson`.
- Write discipline: line-buffered, append-only, atomic per-write (one event per file open/close cycle to minimize crash-window).
- Schema validation: fail loud at emit time if the payload doesn't match — catches author errors immediately.

**Council review:** Required. Three lenses:

1. Schema correctness (does the schema capture all the fields the harness reader needs?)
2. Failure mode coverage (what happens if `./sentinels.ndjson` is read-only, missing, or full disk?)
3. Test coverage (do the unit tests exercise schema validation + write discipline + crash recovery?)

**Output artifacts:**

- `bin/sentinels.py` with Pydantic models + emit helper.
- `bin/tests/test_sentinels.py` updated with full coverage.
- Documentation in module docstring.

### Phase 1C — `bin/harness/sentinel_reader.py` module

**Work items:**

- New harness module: file watcher (poll mtime + tail content; no need for inotify/FSEvents — polling is simpler and cross-platform).
- NDJSON parser with tolerance for trailing partial line.
- Event-stream-to-status-update bridge: emits the same status updates the existing collector emits (so downstream TUI/CLI consumers don't change).
- Liveness rule implementation: mtime-stall detection with tunable heartbeat window.
- STALLED state introduction: new run state in `harness/status.py` enum.
- ABANDONED_USER state: existing kill subcommand integration.

**Council review:** Required. Three lenses:

1. Cross-platform correctness (does the polling work identically on Mac, Windows, Linux? Especially around mtime granularity and clock-skew tolerance.)
2. STALLED state semantics (how does the harness behave when STALLED transitions back to ALIVE because the agent resumed? Idempotent classification?)
3. Backwards-compatibility removal (every reference to stream-json parsing in the harness is cleanly removed; no dead code paths remain)

**Output artifacts:**

- `bin/harness/sentinel_reader.py` with poll-based file watcher.
- Updated `bin/harness/status.py` with STALLED + ABANDONED_USER states.
- `bin/tests/test_sentinel_reader.py` with cross-platform tests.

### Phase 1D — `bin/harness/launcher.py` refactor

**Work items:**

- Remove subprocess spawn of `claude -p` (and all stream-json parsing infrastructure).
- Add paste-buffer launch flow:
  1. Create run directory.
  2. Create empty `sentinels.ndjson` marker file.
  3. Use `pyperclip` to write prompt to OS paste buffer.
  4. Display banner with cd + launch command for the operator to copy-run.
  5. Transition run state to `WAITING_FOR_HUMAN_LAUNCH`.
- New run state: `WAITING_FOR_HUMAN_LAUNCH` (in addition to existing PENDING / RUNNING / COMPLETED / FAILED / CANCELLED).
- Transition from `WAITING_FOR_HUMAN_LAUNCH` to `RUNNING` when the first sentinel event arrives (`run_started`).

**Dependency add:** `pyperclip>=1.8.0` to `requirements.txt` and `pyproject.toml`.

**Council review:** Required. Three lenses:

1. Banner UX clarity (would a fresh user correctly understand "paste this command into a new terminal" vs "paste the prompt"?)
2. State machine completeness (every transition between PENDING, WAITING_FOR_HUMAN_LAUNCH, RUNNING, STALLED, COMPLETED, FAILED, CANCELLED, ABANDONED_USER is exercised by tests)
3. Cross-platform paste buffer (Mac `pbcopy`, Windows `clip`, Linux `xclip`/`xsel` all work; fallback for headless Linux gracefully writes prompt to `./prompt.txt` with instructions)

**Output artifacts:**

- `bin/harness/launcher.py` refactored.
- `bin/harness/status.py` with WAITING_FOR_HUMAN_LAUNCH state.
- `bin/tests/test_launcher.py` updated.

### Phase 1E — TUI updates

**Work items:**

- TUI shows banner for `WAITING_FOR_HUMAN_LAUNCH` runs prominently (probably in a banner pane separate from the run table).
- Run table shows heartbeat status: last-mtime + heartbeat window remaining + STALLED indicator.
- STALLED runs surface a "go check this window" notification.
- Kill keybinding (E from instruction 186) marks the run ABANDONED_USER instead of CANCELLED when the run is in `WAITING_FOR_HUMAN_LAUNCH` or STALLED.
- Banner copy-to-clipboard: pressing C on a `WAITING_FOR_HUMAN_LAUNCH` run copies the launch command to clipboard (a nice convenience).

**Council review:** Required. Two lenses suffice (UX changes are smaller surface area):

1. Visual hierarchy (does the banner draw attention without overwhelming the run table?)
2. Color/strictness conventions (consistent with existing TUI rules from v1.5.7 status enum colors)

**Output artifacts:**

- `bin/qpb_tui.py` updated with new states + banner.
- Screenshot in `docs/screenshots/v1.5.9_tui_launch_banner.png` showing the banner UX.

### Phase 1F — Runner refactor

**Work items:**

- `bin/run_playbook.py` claude provider lane: replace `claude -p` subprocess with paste-buffer + sentinel-file pattern (same as Phase 1D but for the runner's single-shot case).
- Preserve `copilot` and `codex` lanes unchanged.
- Add `--launch-via {paste,subprocess}` flag for any users who somehow still have `claude -p` working and want to use it (probably remove this flag immediately; only here as an escape hatch during transition).

**Council review:** Required. Three lenses:

1. Lane isolation (paste-buffer changes don't leak into copilot/codex paths)
2. Single-shot ergonomics (the runner case is one run, not a pool — banner UX should be simpler than the harness pool case)
3. Backward-compat semantics of `--launch-via` flag (or removal thereof)

**Output artifacts:**

- `bin/run_playbook.py` refactored.
- `bin/tests/test_run_playbook.py` updated.

### Phase 1G — Worker invocation helper

**Work items:**

- Small utility script that takes a single instruction file and does the paste-buffer-launch dance for a one-shot worker run.
- Wraps Phase 1D's launcher logic in single-run mode.
- Used for firing instructions 197-style worker runs in the new substrate.

**Output artifacts:**

- `bin/fire_worker.py` (or whatever name the operator prefers).
- Documentation in `ai_context/TOOLKIT.md` for how to use it.

### Phase 1H — Documentation + integration

**Work items:**

- `ai_context/TOOLKIT.md` updated with the new launch sequence, sentinel file location, banner instructions.
- `ai_context/DEVELOPMENT_CONTEXT.md` v1.5.9 case-study entry on the June 15 forcing function.
- `ai_context/DEVELOPMENT_PROCESS.md` updated for the worker-invocation lane change.
- README install instructions check (no reference to `claude -p` left over in install or run docs).
- Cross-reference from bugspec docs back to QPB (if bugspec gains a similar paste-buffer flavor for any reason, the docs cross-link).

**Council review:** Toolkit Test Protocol (per workspace `CLAUDE.md` — orientation docs gate through Toolkit Test, not Council). Sequential: run through the new launch sequence end-to-end with a fresh test repo, confirm the docs describe what actually happens.

**Output artifacts:**

- Three orientation docs updated.
- Toolkit Test Protocol pass recorded in `quality/v1.5.9_toolkit_test.md`.

### Phase 1 Ship Gate

**Before Phase 2 begins:** end-to-end test of the new substrate.

1. Run a single full QPB run via the new launcher (one repo from the existing benchmark plans).
2. Confirm `sentinels.ndjson` is created, populated, and parsed correctly.
3. Confirm TUI displays banner, then run progress, then completion.
4. Confirm STALLED detection works (kill the terminal mid-run, watch the harness detect).
5. Confirm ABANDONED_USER state works (explicit kill subcommand from operator).
6. Confirm Mode A still works (interactive Claude Code without sentinels — no overhead, no errors).

**Gate criterion:** all six end-to-end tests pass on at least one Mac. Windows + Linux tests can be Phase 1 follow-up if time-pressed; they CANNOT be deferred past v1.5.9 ship.

---

## Phase 2 — B-8: Weak-assertion detection on QPB-generated tests

**Goal:** prevent another Marcono1234-class "your test is weaker than you think" maintainer comment on QPB-generated PRs. Three-layer detection per Design §2.8.

**Rationale for Phase 2 position:** small effort, fresh evidence (Marcono1234 2026-06-05), high upside (no more weak-test-design feedback from maintainers), composable with B-7 (Phase 7 emit) and bugspec workflow.

### Phase 2A — Layer 1 static pattern detection

**Work items:**

- New `bin/test_quality_gate.py`: runs over generated regression tests, flags known weak-assertion patterns per Design §2.8 Layer 1 list.
- Language-aware variants for Java (JUnit/Truth), Python (pytest), JavaScript (Jest), Go (go test), Rust (cargo test). Each language gets its own pattern set; shared infrastructure for common patterns (try-catch wrap, empty catch, no-op assertion).
- Fixture-based testing: `tests/fixtures/weak_assertions/<lang>_<pattern>.txt` containing characteristic offending code; cross-rejection assertions confirm patterns don't match on clean code.

**Council review:** Required. Three lenses:

1. Pattern correctness (do the regexes / AST patterns catch the offending cases without false positives on legitimate exception-typing tests?)
2. Language coverage (are the 5 languages each handled to the same depth?)
3. Severity calibration (which patterns hard-fail vs. warn-with-acknowledge?)

### Phase 2B — Layer 2 adversarial test critique sub-pass

**Work items:**

- New Phase 5.5 sub-pass in `bin/run_playbook.py`.
- Subagent prompt: "this test allegedly demonstrates the bug. Could it pass for any reason OTHER than the bug being absent? Construct degenerate scenarios."
- Subagent receives: the generated test + PR body's "Testing" section + writeup's "## 7. The test" section. Does NOT receive: the fix code, original repo source, other phase outputs.
- Output: APPROVED or WEAK + specific tightening suggestions.
- WEAK output triggers Phase 5 re-derivation with the critique in context.

**Council review:** Required. Three lenses:

1. Information isolation (does the subagent really not see the fix code? Verify via prompt inspection.)
2. Critique quality (does the WEAK output produce actionable tightening suggestions, not just "test is weak"?)
3. Re-derivation loop (does Phase 5 correctly use the WEAK critique to tighten the test on the next iteration?)

### Phase 2C — Layer 3 counterfactual mutation (optional, benchmark-mode only)

**Work items:**

- New `bin/counterfactual_mutation.py`: applies the 3 mutations from Design §2.8 Layer 3, runs the test against each, verifies expected fail/pass.
- Wired into Phase 6 as opt-in (benchmark mode default-on; adopter Mode A default-off).
- Time budget enforcement: per-test budget of 60s, total run budget tunable.

**Council review:** Required. Two lenses:

1. Mutation correctness (do the no-op, wrong-fix, removed-assertion mutations actually produce the expected fail/pass states reliably?)
2. Performance discipline (does the time budget actually constrain runtime so a 20-bug benchmark doesn't add more than ~1 hour?)

### Phase 2 Ship Gate

- Layer 1 catches Marcono1234's exact case (try-catch + boolean comparison + isEqualTo(stringOk)) as a hard fail on Java input.
- Layer 2 produces an APPROVED verdict on a known-good test fixture and WEAK on Marcono1234's case.
- Layer 3 catches a synthetic "test that passes via incidental code path" fixture.

---

## Phase 3 — B-7: QPB Phase 7 emits bugspec-format YAML

**Goal:** close the QPB→bugspec loop. After Phase 6 confirms a bug, Phase 7 emits a bugspec-format YAML spec ready for `bugspec process`.

**Rationale for Phase 3 position:** small implementation effort, large operator-value payoff. Composes with B-8 (Phase 5.5 tightening flows into Phase 7's emitted spec).

**Work items:**

- New `bin/phase7.py` module (or extension to existing Phase 7 code if any).
- Jinja-style template at `templates/bugspec_spec.yaml.j2`.
- Reads `quality/BUGS.md` confirmed bug entries; for each, emits `quality/bugspec/<bug-id>.yaml` with:
  - `bug_id` from BUGS.md
  - `title`, `upstream`, `fork`, `artifacts` (red_patch, green_patches, pr_body, writeup paths)
  - `branch` (generated from bug_id + short description)
  - `red_commit`, `green_commits` with auto-generated messages from BUGS.md content
  - `profile: maven` or `profile: pytest` etc. inferred from project type
  - `vars` block with module + test_class auto-derived
  - `pre_test_command` if target repo's CI is known to use a formatter
- Documentation in SKILL.md for how operators consume the emitted spec.

**Council review:** Required. Three lenses:

1. Spec correctness (does `bugspec validate` pass on every emitted spec?)
2. Profile inference (does the maven/pytest/etc. profile correctly match the target repo's actual test runner?)
3. Cross-project documentation (do operators know to run `bugspec process` on the emitted YAML?)

**Output artifacts:**

- `bin/phase7.py` (or extension).
- `templates/bugspec_spec.yaml.j2`.
- `bin/tests/test_phase7_bugspec_emit.py`.
- SKILL.md cross-reference to bugspec workflow.

**Dependency:** bugspec must be installable (pip + npm) so QPB users have a viable consumer. Verify bugspec v0.3.x has stable spec format before Phase 3 ships.

---

## Phase 4 — B-3: Harness resume + iterate

**Goal:** aborted runs (network drop, model timeout) can resume from the last completed phase. Completed runs can be re-prompted with operator-supplied "look harder at X" context.

**Rationale for Phase 4 position:** moderate effort, large operator-value, ergonomically synergistic with Phase 1's substrate change.

**Work items:**

- Phase-completion serialization: each phase emits a `quality/phase_<N>_state.json` snapshot at completion.
- Resume detection: harness on launch checks for partial state; if found, offers operator the option to resume from last completed phase.
- Iterate flag: `--iterate-from-phase N --hint "look harder at FooClass"` launches a re-run that reuses Phases 0-N artifacts.
- TUI surfaces resumable runs alongside fresh runs.

**Council review:** Required. Three lenses:

1. State idempotency (does resuming N times produce identical results to one fresh run through the same phases?)
2. Iterate hint integration (does the operator hint actually influence the subsequent phase's prompt?)
3. UX clarity (does the TUI clearly distinguish FRESH vs RESUMED vs ITERATED runs?)

---

## Phase 5 — B-6: Combine related findings into single coherent PR

**Goal:** when Phase 6 confirms multiple bugs in the same code region or abstraction, optionally emit a single bugspec spec covering all of them.

**Rationale for Phase 5 position:** composes with Phase 3 (bugspec emit). Small effort once Phase 3 lands.

**Work items:**

- New `bin/finding_clustering.py`: heuristic clustering of related findings (same file region within N lines, same module, same root cause class).
- Operator override: `--cluster-strategy {none, file-region, root-cause}` flag.
- Phase 3 (now Phase 7-equivalent) reads cluster output; emits one spec per cluster instead of per finding.
- Spec includes multiple commits (red commit per finding, green commits per fix) in the bugspec multi-fix shape.

**Council review:** Required. Two lenses suffice (clustering is heuristic, not load-bearing):

1. Cluster correctness (do the clusters group findings that maintainers would want combined?)
2. Multi-fix bugspec emit correctness (does `bugspec process` correctly handle the multi-commit shape?)

---

## Phase 6 — Part 1 (skill ship-gate) layered implementation

**Goal:** mechanical + cross-artifact checks become new invariants in `quality_gate.py`; semantic checks become a new Council audit prompt at Phase 4.

**Scope is large.** This is roughly 4-6 worker instructions worth of work. Break into sub-phases per Design §1.1, §1.2, §1.3.

### Phase 6A — Mechanical invariants

Per Design §1.1. Add as Layer-1 invariants #19+ in `schemas.md` §10.

**Council review:** Required. Three lenses focused on invariant correctness, false-positive rate, severity calibration.

### Phase 6B — Cross-artifact consistency invariants

Per Design §1.2. Multi-file reads but still gate-able.

**Council review:** Required.

### Phase 6C — Semantic Council audit prompt

Per Design §1.3. New Phase 4 sub-pass. One prompt per reviewer, structured per-category verdicts.

**Council review:** Required. The Council prompt itself goes through a Council review (recursive but tractable).

### Phase 6D — Bootstrap-as-regression-test

Per Design §1.4. `bin/tests/test_skill_reviewer_regression.py` with one test case per historical FINDING-NN.

**Council review:** Required. Lens: does the test suite actually catch the historical bugs when replayed against the fixture skill?

---

## Phase 7 — B-5: Adversarial code review pass (deferrable to v1.5.10)

**Goal:** complementary to QPB's REQ-derivation methodology — catch Java object-contract violations, test-gap-masks-bug patterns, and other classes the main pipeline misses.

**Rationale for Phase 7 position (potentially deferred):** moderate effort, requires Phase 1 output extensions to inject project-specific variables. If v1.5.9 ship window tightens, this defers to v1.5.10.

**Work items per Design §2.5.**

**Council review:** Required. Three lenses on fresh-context isolation, prompt quality, output integration.

---

## Phase 8 — B-4: Bug-neighborhood iteration (deferrable)

**Goal:** after Phase 6 confirms a bug, optionally explore the immediate code neighborhood for sibling bugs.

**Rationale for deferral:** composes with B-5; defer if v1.5.9 scope tightens.

---

## Phase 9 — Release prep + ship

**Work items:**

- Version bump 1.5.8 → 1.5.9 across all sites (see Phase 6A's version-drift sweep — Phase 9 is the first real test of the invariant).
- CHANGELOG entry for v1.5.9 covering all shipped phases.
- README update for any new flags / features.
- pip + npm publish per the v1.5.8 publish sequence (#222-#226 pattern).
- Tag `v1.5.9` on origin; merge `1.5.9` branch to `main`.
- `ai_context/DEVELOPMENT_CONTEXT.md` updated with full v1.5.9 chronology.

**Verify-before-claiming-shipped applies** per workspace `CLAUDE.md`. After every push, run `git ls-remote origin <ref>` to confirm SHA matches.

---

## Sequencing summary

```
Phase 0: v1.5.8 stabilization confirmation        [gate]
Phase 1: Section 0 substrate (sub-phases A-H)      [MANDATORY before June 15]
Phase 1 ship gate: end-to-end test                 [gate]
─────────────────── above is non-negotiable ───────────────────
Phase 2: B-8 weak-assertion detection              [strongly recommended]
Phase 3: B-7 bugspec-format Phase 7 emit           [strongly recommended]
Phase 4: B-3 resume + iterate                      [strongly recommended]
Phase 5: B-6 combine related findings              [recommended]
Phase 6: Part 1 layered ship-gate (sub-phases A-D) [aspirational; large scope]
Phase 7: B-5 adversarial review                    [deferrable to v1.5.10]
Phase 8: B-4 bug-neighborhood iteration            [deferrable to v1.5.10]
Phase 9: Release prep + ship
```

**Tightest viable v1.5.9:** Phases 0, 1, 9 only. Substrate replacement + ship. Cuts everything else to v1.5.10.

**Realistic v1.5.9 (Cowork recommendation):** Phases 0, 1, 2, 3, 4, 5, 9. Substrate + the four strongly-recommended capabilities + ship. Phase 6 (ship-gate) and Phases 7-8 defer to v1.5.10.

**Maximal v1.5.9:** all phases. Probably overruns the release window if started before mid-summer 2026.

Operator decides scope at Phase 0 → Phase 1 transition based on calendar.

---

## Council-of-Three coordination notes

Every source-edit phase has a Council review (per Operating Principles). v1.5.9-specific Council notes:

- **Phase 1's Council reviews must include a "no `claude -p` references" lens.** Every SKILL.md / phase prompt / orientation doc edit during Phase 1 should be checked for lingering references to the deprecated substrate.
- **Phase 2 (B-8) Council reviews must include a "Marcono1234 fixture passes" lens.** The known weak-test case from gson PR #3035 is the litmus test for whether the detection works.
- **Phase 3 (B-7) Council reviews must include a "bugspec validate passes" lens.** Every emitted spec must validate against bugspec's spec schema.
- **Phase 6 (Part 1) Council reviews use the recursive pattern:** the Council prompt itself goes through a Council review. Document this in the Phase 6C instruction.

---

## Open work-items tracker

(For operator to update as v1.5.9 progresses.)

| Phase | Status | Worker instruction | Council synthesis | Ship gate |
|---|---|---|---|---|
| 0 | not started | — | n/a | — |
| 1A SKILL.md sentinel | not started | TBD | TBD | TBD |
| 1B bin/sentinels.py | not started | TBD | TBD | TBD |
| 1C bin/harness/sentinel_reader.py | not started | TBD | TBD | TBD |
| 1D bin/harness/launcher.py | not started | TBD | TBD | TBD |
| 1E TUI | not started | TBD | TBD | TBD |
| 1F runner | not started | TBD | TBD | TBD |
| 1G fire_worker.py | not started | TBD | TBD | TBD |
| 1H docs | not started | TBD | TBD | TBD |
| 1 ship gate | not started | n/a | n/a | TBD |
| 2A weak-assertion Layer 1 | not started | TBD | TBD | TBD |
| 2B weak-assertion Layer 2 | not started | TBD | TBD | TBD |
| 2C weak-assertion Layer 3 | not started | TBD | TBD | TBD |
| 3 bugspec-format emit | not started | TBD | TBD | TBD |
| 4 resume + iterate | not started | TBD | TBD | TBD |
| 5 combine findings | not started | TBD | TBD | TBD |
| 6A mechanical invariants | not started | TBD | TBD | TBD |
| 6B cross-artifact invariants | not started | TBD | TBD | TBD |
| 6C Council audit prompt | not started | TBD | TBD | TBD |
| 6D bootstrap-as-regression | not started | TBD | TBD | TBD |
| 7 adversarial review | deferred? | TBD | TBD | TBD |
| 8 bug-neighborhood | deferred? | TBD | TBD | TBD |
| 9 release ship | not started | TBD | n/a | TBD |

---

*End of Implementation Plan. Companion: `QPB_v1.5.9_Design.md`.*
