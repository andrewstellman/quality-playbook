# Quality Playbook v1.5.7 — Implementation Plan

*Companion to: `QPB_v1.5.7_Design.md`*
*Status: drafted 2026-05-09. Implementation begins after operator review.*
*Depends on: v1.5.6 shipped (tag `v1.5.6` on origin at SHA `292e484`); `1.5.6` branch HEAD past tag with post-tag fix-up clusters covering Phase 2-5 validator hardening, AGENTS.md three-tier priority order, README open-target install flow, and clusters 044 (`--next-iteration` form) / 049 (role-map auto-recovery via deterministic exclude filter) / 050 (`--benchmark-mode` flag + Phase 4 Council roster banner + docs); v1.5.6 design + implementation plan present at `docs/design/QPB_v1.5.6_*.md`.*

---

## Operating Principles

- **One AI session per implementation phase.** Phases proceed sequentially. State lives in the filesystem (the cell directories for cycle work; `quality/run_state.jsonl` for substrate; `git` for source-edit phases).
- **Cowork-orchestrator / Claude-Code-worker pattern is the default execution mode.** v1.5.7's QPB-source edits go through the worker pattern documented in `ai_context/AI_ORCHESTRATION_PATTERNS.md` (the v1.5.6 deliverable). Cowork drives planning and Council coordination; the Claude Code worker (in `Quality Playbook/v1.5.7_runner/`) does the QPB-source edits per the workspace `CLAUDE.md` "diagnosis-then-Claude-Code lane" rule.
- **Orientation-doc edits use a different lane.** Per the workspace `CLAUDE.md` carve-out, edits to `ai_context/TOOLKIT.md`, `ai_context/BENCHMARK_PROTOCOL.md`, `ai_context/DEVELOPMENT_PROCESS.md`, `ai_context/IMPROVEMENT_LOOP.md`, `ai_context/CALIBRATION_PROTOCOL.md`, and `README.md` may be applied directly by Cowork (with diff-shown-first + operator-approval) and gate through the Toolkit Test Protocol, NOT Council-of-Three. Mixed commits (orientation doc + source) go through the Council/Claude-Code lane regardless.
- **Six deliverables, six core phases, plus stabilization and ship.** Total 8 phases (Phase 1 stabilization, Phases 2–7 deliverables, Phase 8 ship). Each deliverable phase is independently revertable — a phase whose Council review fails ships in a later release without blocking the others.
- **Deliverable ordering is smallest-and-safest first, with the highest-runtime-risk deliverable last.** Phase 2 is the cookbook (docs only, lowest risk). Phase 3 is abort preservation (small code change, single-file). Phase 4 is `metrics/` formalization (new directory tree + new script, no `SKILL.md` surface change). Phase 5 is log centralization (largest invasion of code call sites, but well-bounded with a `--logs-flat` legacy fallback). Phase 6 is Council roster modernization + availability resilience + override layer (touches Council invocation and adds a config-file persistence layer; bounded by per-Council-member fast-fail and the `~/.qpb/config.yaml` override hatch). Phase 7 is `SKILL.md` trim (highest runtime-behavior risk — every line of `SKILL.md` is potentially load-bearing for every QPB run going forward; sequenced last among source edits so a revert doesn't cascade into other phase work).
- **Each source-edit phase has a Council review.** Three flat lenses per CALIBRATION_PROTOCOL.md Mode 1 nested-panel rules from the workspace `CLAUDE.md`.
- **Backward compatibility on log paths until v1.6.0.** The `--logs-flat` legacy flag preserves v1.5.6 paths for adopters whose tooling depends on them. Drop the flag in v1.6.0 (one-version deprecation window — v1.5.7 is planned as the last v1.5.x release).
- **Don't touch v1.6 surfaces.** Requirements Review work is out of scope for every phase.
- **Honest framing on outcomes.** Each phase's audit reports what testing showed, not what makes the phase look complete. A `revert` verdict on any phase is a valid outcome.
- **Verify before claiming completion.** Per the workspace `CLAUDE.md` rule: don't claim a push has shipped, a tag has moved, a test has passed, or a phase has finished without direct observation of the actual end state.

---

## Phase 1 — v1.5.6 Stabilization Confirmation

Goal: confirm v1.5.6 is shipped and stable; the `1.5.6` branch is at the expected commit; the model-comparison benchmark sweep that motivated v1.5.7 is captured as evidence; the working tree is clean; resolve open questions and conditional candidates from the Design doc before any source edits begin.

Work items:

- `git ls-remote origin v1.5.6 1.5.6 main` returns the expected SHAs. Specifically: `v1.5.6` tag at `292e484`; `1.5.6` branch HEAD at the post-tag-fix-up SHA (whatever the latest cluster has produced); `main` at v1.5.6.
- Local `1.5.6` branch HEAD matches `origin/1.5.6`.
- `python3 -m unittest discover bin/tests` passes on the `1.5.6` branch with no regressions vs. v1.5.6 baseline.
- `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/` directory exists and is at terminal state per v1.5.6's Pattern 7 deliverable.
- The model-comparison benchmark sweep (currently running against pinned QPB versions) is informationally noted; v1.5.7 doesn't need to halt or freeze the sweep.
- Open the `1.5.7` branch off `1.5.6` HEAD: `git checkout -b 1.5.7 1.5.6`. Push to origin. (No commits yet; this is just the branch prep.)
- Read `~/Documents/AI-Driven Development/CLAUDE.md` end-to-end (workspace conventions). Confirm the "diagnosis-then-Claude-Code lane" rule and the orientation-doc carve-out are current.
- Read `ai_context/DEVELOPMENT_PROCESS.md` end-to-end. Confirm any rule changes since v1.5.6 docs were authored are noted.
- Read `ai_context/AI_ORCHESTRATION_PATTERNS.md` (the v1.5.6 deliverable) end-to-end. Confirm the worker-spin-up pattern that v1.5.7 will use is the canonical documented form.
- **Resolve Design doc open questions.** Three questions in the Design's "Open questions" section need operator decisions: `<run-id>` naming format, `quality.gate-failed-<ts>/` location, cookbook file location. Operator confirms or overrides the Design's recommendations; update the Design doc with the decisions before Phase 2.
- **Resolve Design doc conditional candidates.** Four items in the Design's "Conditional candidates from v1.5.6 close-out carry-forward" section need operator decisions: `--require-docs` opt-out, Windows path handling, Persona 19 deep work, adopter-grade orchestration-patterns doc. Operator decides which (if any) surfaced and should be committed to v1.5.7 as additional deliverables. If any commit, add new phase(s) to this Implementation Plan and renumber the integration phase.
- **Read `docs/design/QPB_v1.7.0_Design.md` and `QPB_v1.7.0_Implementation_Plan.md` end-to-end.** Phase 4 (`metrics/` formalization) requires v1.5.7's directory tree to be consistent with v1.7's planned SPC machinery. If the v1.7 design implies a layout that conflicts with the v1.5.7 Design's `metrics/` formalization scope, fix the v1.5.7 Design doc before Phase 4 begins.

Deliverable: a Phase 1 confirmation note posted to chat with: SHAs verified, test suite green, working tree clean, `1.5.7` branch open, model-comparison sweep state captured (informational), `AI_ORCHESTRATION_PATTERNS.md` re-read and consistent with planned usage, open-question + conditional-candidate decisions captured, v1.7 design alignment confirmed.

Gate to Phase 2: all of the above confirmed.

---

## Phase 2 — Deliverable 2: Role-map query cookbook

Goal: ship `references/role_map_queries.md` and add the Phase 2 prompt addition pointing at it. (Smallest, lowest-risk deliverable: docs only.)

Worker spin-up: `Quality Playbook/v1.5.7_runner/instructions/002-author-role-map-queries-cookbook.md`.

Work items:

- Worker reads `bin/role_map.py::ROLE_DESCRIPTIONS` to confirm the canonical role taxonomy values. The cookbook deliberately does NOT enumerate roles — it points at `bin/role_map.py::ROLE_DESCRIPTIONS` as the canonical source — so the cookbook doesn't drift if the taxonomy evolves.
- Worker reads `quality/exploration_role_map.json` schema (fields + types) by inspecting the role-map writer code in `bin/role_map.py`.
- Worker drafts `references/role_map_queries.md` per the Design doc's content outline:
  1. Schema description (top-level `files` array, per-file record fields, pointer to `ROLE_DESCRIPTIONS`).
  2. Canonical queries (source-code paths, source filtered by extension, test paths, skill-tool paths with prose refs, count-by-role, bytes-by-role).
  3. Anti-patterns with explicit "DO NOT use" annotations (`.roles.source[]`, `.roles.code[]`, `.files.code[]`, `.files[] | select(.role == "source")`).
  4. Discovery query (the one-liner that summarizes the role map: schema_version, provenance, files_count, distinct roles).
- Length target: 80–120 lines. Tone consistent with other `references/` files (terse, example-heavy, no over-explanation).
- Worker locates the Phase 2 prompt template. v1.5.6's install bundle places phase prompts at `phase_prompts/phase2.md`; the canonical source location in QPB may differ. The worker traces the path used by the runner during Phase 2 prompt construction, then adds the cookbook reference paragraph in the appropriate "tools" or "role map usage" section. Cite `references/role_map_queries.md` by relative path so the runner-installed and source-tree paths both resolve.
- Add regression tests:
  1. **Reference-file existence test:** assert `references/role_map_queries.md` exists and contains the four anti-patterns and the four canonical patterns named in the Design.
  2. **Phase 2 prompt content test:** assert the prompt template contains the cookbook reference paragraph and the path `references/role_map_queries.md`.
  3. **Token-budget test:** assert the cookbook reference paragraph adds <300 tokens to the Phase 2 prompt (use `tiktoken` or a documented approximation).
- Run `python3 -m unittest discover bin/tests`; confirm new tests pass on patched code and fail on unpatched code.
- Worker commits in two logical commits on `1.5.7` branch:
  1. "v1.5.7: add references/role_map_queries.md role-map jq query cookbook"
  2. "v1.5.7: Phase 2 prompt cites role_map_queries.md cookbook"

Council review (3 lenses):
- **Correctness:** canonical queries actually work against a real role map (worker tests one in a smoke check). Anti-patterns are actually wrong (worker confirms by running them and observing empty output).
- **Doc tone:** cookbook tone matches other `references/` files. Terse, example-heavy. Deliberate non-enumeration of role taxonomy is acknowledged.
- **Phase 2 prompt overhead:** the cookbook reference paragraph adds <300 tokens; no token-budget regression.

Council ratifies.

Gate to Phase 3: Council ratification + tests green.

---

## Phase 3 — Deliverable 1: Phase 2 gate-failure artifact preservation

Goal: when a Phase 2 gate failure aborts a run, preserve `quality/` to `quality.gate-failed-<UTC-timestamp>/` rather than wiping or leaving empty.

Worker spin-up: `Quality Playbook/v1.5.7_runner/instructions/003-phase2-abort-preservation.md`.

Work items:

- **Locate the disposal mechanism FIRST.** Per the Design doc's diagnostic note, the explicit abort path in `bin/run_playbook.py` only logs and returns; the actual `quality/` disposal happens elsewhere. The worker's first task is to trace where disposal occurs:
  - Search for `shutil.rmtree`, `Path.rmtree`, `quality.rmtree` in `bin/`, `lib/`, `repos/setup_repos.sh`, and `phase_prompts/`.
  - Check `setup_repos.sh --replace` and any cell-prep flow that runs before the next attempt against a cell.
  - Check whether the agent's tool-call writes to `quality/` are even persisting on disk in v1.5.6 (the cross-model chat noted this as an open possibility).
  - Check `bin/run_playbook.py` for any cleanup_repo-like helpers.
  - Document the located disposal path in the Phase 3 confirmation note.
- Implement preservation at the disposal site (NOT just in the abort path) so the rename happens before disposal regardless of the disposal mechanism's location:
  ```python
  quality = repo_dir / "quality"
  if quality.exists() and any(quality.iterdir()):
      ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
      preserved = repo_dir / f"quality.gate-failed-{ts}"
      quality.rename(preserved)
      marker = preserved / "GATE_FAILURE.md"
      marker.write_text(_render_gate_failure_marker(
          phase_group=group,
          cell_name=repo_dir.name,
          timestamp=ts,
          runner_version="v1.5.7",
          model=getattr(args, "model", None),
          violation_message=gate_violation_message,
      ))
      lib.logboth(log_file, lib.log(
          f"Preserved Phase 1 evidence at {preserved.name}/. "
          f"Next run will create a fresh quality/."
      ))
  ```
- New helper `_render_gate_failure_marker(...)` returns a multi-line markdown string per the Design's marker file content.
- Update the Phase 2 gate handler so the violation message is captured into a variable that's passed to the marker renderer (currently the message is logged inline; it now also needs to be captured for the marker).
- Update `ai_context/TOOLKIT.md` (orientation-doc lane: Toolkit Test Protocol gate, NOT Council) to document the preservation directory naming convention and the disk-cleanup discipline (`rm -rf quality.gate-failed-*` when no longer needed).
- Add regression tests in `bin/tests/test_run_playbook.py`:
  1. **Preservation happy path:** simulate a Phase 2 gate failure (e.g., agent produced a 100-line EXPLORATION.md against a 120-line gate). Assert that after abort, `quality/` does not exist (renamed) and `quality.gate-failed-<ts>/` exists with the agent's outputs intact and a `GATE_FAILURE.md` marker.
  2. **Preservation idempotence:** run multiple aborted attempts on the same cell; assert distinct timestamped sibling directories accumulate, none overwritten.
  3. **Empty-quality handling:** simulate a Phase 2 abort before `quality/` was created; the preservation logic doesn't crash; no `quality.gate-failed-*/` is created.
  4. **Subsequent run independence:** after preservation, run the cell again; assert the new run creates a fresh `quality/` that doesn't see the preserved set as `previous_runs/`.
  5. **Marker content:** assert `GATE_FAILURE.md` contains the violation message, phase group, cell name, timestamp, runner version, and model.
  6. **Cluster-049 auto-recovery composition:** when role-map auto-recovery succeeds, no preservation is triggered (the run proceeds without entering the abort path).
- Run tests; confirm pass on patched code and fail on unpatched code.
- Worker commits in one logical commit:
  - "v1.5.7: preserve quality/ as quality.gate-failed-<ts>/ on Phase 2 gate failure"
- Cowork applies the orientation-doc edit to `ai_context/TOOLKIT.md` directly (diff shown first, operator approves) and validates via Toolkit Test Protocol before merge.

Council review (3 lenses) — for the source change only; the orientation-doc edit gates separately:
- **Disposal-mechanism location traced:** the worker's confirmation note identifies where disposal actually occurs and explains why preservation is wired at that point.
- **Atomicity:** the rename happens before the marker write. If the runner crashes between rename and marker write, the preserved directory exists; recovery is straightforward.
- **Naming convention:** UTC timestamps avoid local-time variance; sortable lexicographically.
- **Interaction with cluster-049 auto-recovery:** preservation runs ONLY if auto-recovery did not succeed. When auto-recovery succeeds (and the run proceeds), no preservation; when auto-recovery fails or is opted out, preservation runs.

Council ratifies.

Gate to Phase 4: Council ratification + tests green + Toolkit Test Protocol on TOOLKIT.md edit green.

---

## Phase 4 — Deliverable 4: `metrics/` directory formalization

Goal: ship `metrics/README.md` (top-level + sub-directory READMEs) documenting the directory tree's conventions, plus `bin/metrics_reconstruction.py` for adopter-side regeneration. The Q1 + Q2 historical reconstruction is run once at v1.5.7 ship to produce a reference data set tagged with v1.5.7.

Worker spin-up: `Quality Playbook/v1.5.7_runner/instructions/004-metrics-formalization.md`.

Work items:

- **Read v1.7 design end-to-end (already done in Phase 1).** Confirm v1.7's planned SPC machinery's input-shape requirements are satisfied by the v1.5.7 layout. If a conflict surfaces here, halt and update the Design doc before continuing.
- Worker inventories current `metrics/` state:
  - What sub-directories exist? What's in them? What conventions are used (CSV/JSONL, column/field names, append-only vs mutable)?
  - What workspace-side artifacts (`Quality Playbook/Calibration Cycles/`, `Quality Playbook/Cross-Repo Analysis/`) should land in `metrics/<sub-directory>/` per the formalized convention?
- Author `metrics/README.md` documenting:
  - Top-level structure: `metrics/regression_replay/`, `metrics/calibration/`, `metrics/bootstrap_recall/`, `metrics/cross_version_recall/`.
  - Cross-references to per-sub-directory READMEs.
  - Relationship to `quality/run_state.jsonl` (cross-cell aggregate vs per-cell event log).
  - Relationship to workspace-side calibration cycle artifacts.
- Author each sub-directory's `README.md`:
  - File format conventions (CSV vs JSONL, column/field names).
  - UTC-timestamped ordering convention.
  - Immutable append-only vs mutable rules.
  - Schema versioning convention (if applicable).
- Implement `bin/metrics_reconstruction.py`:
  - Walk all cells under `repos/` (and an optionally-configured roster of historical cell roots).
  - Read each cell's `quality/run_metadata.json` and `quality/BUGS.md` heading-parses.
  - Emit per-quarter aggregates into `metrics/<sub-directory>/` using the documented conventions.
  - Backup-on-write logic: if `metrics/<sub-directory>/` contains existing data, write to `metrics/<sub-directory>/.backup-<ts>/` first.
  - Idempotence: same inputs produce same outputs (modulo timestamp).
  - Robustness: missing-data cells handled gracefully (logged, skipped, never crash).
- Add regression tests in `bin/tests/test_metrics_reconstruction.py`:
  1. **Reconstruction idempotence:** run reconstruction twice against the same cell roster; assert same output (modulo timestamp).
  2. **Missing-data handling:** include a cell roster with one corrupted `run_metadata.json`; assert reconstruction logs the corruption, skips that cell, and produces output for the others.
  3. **Backup-on-write:** run reconstruction against a directory with existing data; assert the original lands in `.backup-<ts>/`.
  4. **Sub-directory README presence:** assert each declared sub-directory has its README.
  5. **v1.7 input shape:** parse a representative output file and assert the columns/fields match what `docs/design/QPB_v1.7.0_*.md` declares as the SPC machinery's input.
- Run reconstruction against the actual cell roster (Q1 + Q2 historical data). Inspect outputs manually for sanity (counts, date ranges, recall trends).
- Run tests; confirm pass on patched code and fail on unpatched code.
- Worker commits in three logical commits:
  1. "v1.5.7: add metrics/ directory tree formalization (top-level + sub-directory READMEs)"
  2. "v1.5.7: add bin/metrics_reconstruction.py for Q1+Q2 historical aggregate generation"
  3. "v1.5.7: regression tests for metrics_reconstruction"
- Optional fourth commit (the Q1+Q2 actual data): "v1.5.7: Q1+Q2 historical metrics aggregates (reconstructed from v1.4.x — v1.5.6 cells)" — operator decides whether the reconstructed data lands in the QPB repo or stays workspace-side.

Council review (3 lenses):
- **v1.7 alignment:** the layout is consistent with v1.7's planned SPC machinery's input shape. Worker's Phase 1 v1.7-design read confirmed alignment; Council re-verifies after Phase 4 implementation.
- **Reconstruction robustness:** the script handles missing-data cells, partial cells, and corrupted artifacts gracefully (none crash; all are logged).
- **Sub-directory README accuracy:** each README's format conventions match what `bin/metrics_reconstruction.py` actually emits.

Council ratifies.

Gate to Phase 5: Council ratification + tests green.

---

## Phase 5 — Deliverable 3: Centralized log emission at `quality/logs/<run-id>/`

Goal: move all QPB-emitted logs to `quality/logs/<run-id>/`. Add the `--logs-flat` legacy flag for backward compat. Update gate validator and substrate readers to handle both layouts. Move v1.5.6 cluster 050's `RUN_MODE.md` writer under the new layout.

This is the largest and most invasive phase of v1.5.7. Spread across three sub-phases.

Worker spin-up: `Quality Playbook/v1.5.7_runner/instructions/005a-log-centralization-runner.md` (writers), `005b-log-centralization-readers.md` (gate, substrate, helpers), `005c-log-centralization-prompts-and-docs.md` (phase prompts, gitignore template, doc updates).

### Sub-phase 5a — Writers (`bin/run_playbook.py`)

Work items:

- Worker reads `bin/run_playbook.py` to inventory all log-write call sites:
  - `<parent>/<cell>-playbook-<ts>.log` (per-target playbook log)
  - `quality/control_prompts/phase<N>.input.txt` (per-phase prompt input)
  - `quality/control_prompts/phase<N>.output.txt` (per-phase prompt output)
  - `quality/run_state.jsonl` (substrate event log) — note this is also written by `bin/run_state_lib.py`; that's covered in 4b
  - `quality/results/quality-gate.log` (quality gate output) — note this is written by `quality_gate.py`; that's covered in 4b
  - `quality/results/run-<ts>.json` (run metadata)
  - `quality/RUN_MODE.md` (cluster 050 marker — currently lives at the cell-level `quality/`; v1.5.7 moves it under `quality/logs/<run-id>/`)
- Define a single helper `_run_log_dir(repo_dir: Path, run_id: str) -> Path` that returns `repo_dir / "quality" / "logs" / run_id`. The directory is created on first call.
- Define `_compute_run_id() -> str` that returns a UTC timestamp like `20260509T184231Z`. Called once per run; cached for the run's duration.
- Refactor every log-write call site to use `_run_log_dir(repo_dir, run_id)` for the path resolution. For each call site, the new path is:

  | Old | New |
  |---|---|
  | `<parent>/<cell>-playbook-<ts>.log` | `<cell>/quality/logs/<run-id>/runner.log` |
  | `<cell>/quality/control_prompts/phase<N>.input.txt` | `<cell>/quality/logs/<run-id>/phase<N>.input.txt` |
  | `<cell>/quality/control_prompts/phase<N>.output.txt` | `<cell>/quality/logs/<run-id>/phase<N>.output.txt` |
  | `<cell>/quality/results/run-<ts>.json` | `<cell>/quality/logs/<run-id>/run_metadata.json` |
  | `<cell>/quality/RUN_MODE.md` | `<cell>/quality/logs/<run-id>/RUN_MODE.md` |

- Update or remove the legacy `quality/control_prompts/` and `quality/results/` directory creation. The new layout doesn't need them.
- Add the `quality/logs/latest` symlink update logic. After each successful run, the symlink at `quality/logs/latest` is updated to point at the run's `<run-id>` directory.
- Add the `--logs-flat` flag (and `QPB_LOGS_LEGACY=1` env var) to argument parsing. When set, the runner writes to v1.5.6 paths exactly as before. The `_run_log_dir` helper short-circuits to the legacy location when this flag is active.
- Internal: add `log_layout` to the `cycle_start` event written via `run_state_lib.append_event`. Value is `"v1.5.7-centralized"` or `"v1.5.6-flat"` based on the legacy flag.

### Sub-phase 5b — Readers (`bin/run_state_lib.py`, `quality_gate.py`)

Work items:

- `bin/run_state_lib.py`:
  - `read_events(repo_dir)` — looks at `repo_dir/quality/logs/latest/run_state.jsonl`, then `repo_dir/quality/logs/<most-recent>/run_state.jsonl` if no `latest` symlink, then `repo_dir/quality/run_state.jsonl` (legacy). Returns events from the first that exists.
  - `append_event(repo_dir, event)` — writes to `repo_dir/quality/logs/<run-id>/run_state.jsonl` per the new layout, OR to `repo_dir/quality/run_state.jsonl` if the run is in legacy mode (detect via the runner-passed `log_layout` argument or via env var).
  - `validate_run_state_file(path)` — validates a given file regardless of location; layout-agnostic.
  - `last_in_progress_phase(repo_dir)` — uses `read_events`; layout-agnostic.

- `.github/skills/quality_gate/quality_gate.py` (the standalone module installed at adopter sites):
  - Update gate-log emission path: `quality/results/quality-gate.log` → `quality/logs/<run-id>/quality-gate.log`. The gate computes its own `<run-id>` from the cycle_start event in run_state.jsonl, OR falls back to `quality/logs/latest/` if the cycle_start lacks a `log_layout` field, OR falls back to `quality/results/quality-gate.log` (legacy).
  - Run-metadata read: same fallback chain (`quality/logs/<run-id>/run_metadata.json` → `quality/logs/latest/run_metadata.json` → `quality/results/run-<ts>.json` legacy).

- Update `bin/run_state_lib.py`'s schema documentation (and `references/run_state_schema.md`) to note the new `log_layout` field and the location convention.

### Sub-phase 5c — Phase prompts, gitignore template, doc updates

Work items:

- Search `phase_prompts/` for any references to `quality/control_prompts/` or `quality/results/` paths. Update each reference to the new `quality/logs/<run-id>/` path. (Phase prompts may not include literal output paths — the runner writes those itself — but if any reference is inline, update it.)
- Update `repos/setup_repos.sh` (or its installed `.gitignore` template documentation) to include:
  ```
  # QPB run logs — transient, not part of the artifact set
  quality/logs/
  ```
  Adopters who want to commit `quality/` artifacts can do so without per-file exclusion.
- Update orientation docs (Cowork-direct lane per CLAUDE.md carve-out, Toolkit Test Protocol gate):
  - `ai_context/TOOLKIT.md` — add a "Log layout (v1.5.7+)" section under the runner reference, documenting `quality/logs/<run-id>/` and the `--logs-flat` legacy flag.
  - `ai_context/BENCHMARK_PROTOCOL.md` — update the cluster-050 RUN_MODE.md path from `quality/RUN_MODE.md` to `quality/logs/<run-id>/RUN_MODE.md`; add a note about log centralization for benchmark archive workflows.
  - `ai_context/DEVELOPMENT_PROCESS.md` — note the layout for any QPB-development sessions that read logs.
  - `README.md` — one-line addition to the "What's new in v1.5.7" section pointing at the new layout.

### Regression tests across 5a/5b/5c

In `bin/tests/`:

- **Log-emission test:** run a complete Phase 1-3 cycle in test mode; assert `quality/logs/<run-id>/{runner.log, phase1.input.txt, phase1.output.txt, run_state.jsonl, run_metadata.json}` all exist and are non-empty. Assert `<parent>/<cell>-playbook-<ts>.log`, `quality/control_prompts/`, `quality/results/run-*.json` do NOT exist.
- **Multiple-run accumulation:** run twice against the same cell; assert `quality/logs/` contains TWO timestamped subdirectories, both intact, neither overwritten.
- **Latest-symlink:** after each run, `quality/logs/latest -> <most-recent-run-id>`. Assert symlink resolves correctly.
- **Legacy flag:** `--logs-flat` (and `QPB_LOGS_LEGACY=1`) restores v1.5.6 paths. Smoke test that adopter tooling reading v1.5.6 paths still works (mock a tooling read of `quality/control_prompts/phase1.output.txt` and confirm it succeeds).
- **Cluster-050 RUN_MODE.md migration:** with `--benchmark-mode`, `RUN_MODE.md` lands at `quality/logs/<run-id>/RUN_MODE.md`. With `--benchmark-mode --logs-flat`, RUN_MODE.md lands at the legacy `quality/RUN_MODE.md`.
- **Gitignore template:** assert the installed `.gitignore` (or documented one) excludes `quality/logs/`.
- **Run-state schema:** `run_state.jsonl` reader handles both new (`quality/logs/<run-id>/run_state.jsonl`) and legacy (`quality/run_state.jsonl`) locations. Each cell's first valid file wins.
- **Gate fallback:** `quality_gate.py` reads the gate log from the new location when present, falls back to the legacy location when not.

Run tests; confirm pass on patched code and fail on unpatched code.

Worker commits in five logical commits (one per sub-phase, plus tests + docs):

1. "v1.5.7: refactor bin/run_playbook.py log writes to use quality/logs/<run-id>/ layout (sub-phase 7a)"
2. "v1.5.7: bin/run_state_lib.py + quality_gate.py reader fallbacks for new log layout (sub-phase 5b)"
3. "v1.5.7: phase prompts + setup_repos.sh .gitignore template (sub-phase 5c source)"
4. "v1.5.7: regression tests for centralized log layout"
5. "v1.5.7: --logs-flat legacy backward-compat flag"

Cowork applies orientation-doc edits (TOOLKIT.md, BENCHMARK_PROTOCOL.md, DEVELOPMENT_PROCESS.md, README.md) directly per the workspace CLAUDE.md carve-out (diff shown first, operator approves), and validates via Toolkit Test Protocol before merge.

Council review (3 lenses) — for the source changes:
- **Migration completeness:** every log-write call site is updated. No legacy paths leak. Cluster-050's `RUN_MODE.md` writer is in the migration set.
- **Legacy flag fidelity:** `--logs-flat` produces output indistinguishable from v1.5.6 for adopters whose tooling depends on the old paths.
- **Schema additions:** the new `log_layout` field on `run_state.jsonl` events is additive; existing readers tolerant of missing fields per the schema's stated forward-compat rule.

Council ratifies.

Gate to Phase 6: Council ratification + tests green + Toolkit Test Protocol on orientation-doc edits green.

---

## Phase 6 — Deliverable 6: Council roster modernization, availability resilience, and override layer

Goal: update `bin/council_config.py` `DEFAULT_COUNCIL_MEMBERS` to the v1.5.7 roster `(claude-opus-4.7, gpt-5.5, claude-sonnet-4.6)`; add per-Council-member fast-fail availability detection with graceful 2-of-2 degradation and clear hard-fail diagnostics; add `~/.qpb/config.yaml` persistence layer; ship the LLM-fillable failure-recovery template; ship `references/runners_and_models.md` backgrounder.

Worker spin-up: `Quality Playbook/v1.5.7_runner/instructions/006a-council-roster-update.md` (Part A), `006b-council-availability-resilience.md` (Part B), `006c-council-config-persistence.md` (Part C), `006d-council-failure-template.md` (Part D), `006e-runners-and-models-doc.md` (Part E). Per workspace CLAUDE.md, `bin/council_config.py`, `bin/run_playbook.py`, and `bin/run_state_lib.py` are on the source-edit list — diagnosis-then-Claude-Code lane required. The new `references/runners_and_models.md` is also a source file (under `references/*.md` per the carve-out list), so its initial authoring goes through the worker too.

### Sub-phase 6a — Roster update

Work items:

- Worker reads `bin/council_config.py` to confirm the existing tuple shape.
- Update `DEFAULT_COUNCIL_MEMBERS` to `("claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6")`. Per the existing docstring rule, this is a swap to NEW identifiers, not a rename of existing ones — historical archives still reference the OLD strings verbatim.
- Worker greps `bin/run_playbook.py` for hardcoded `gpt-5.4` / `gemini-2.5-pro` strings: argparse help text (around line 419-435 — the cluster-050 `--benchmark-mode` help paragraph), banner construction (around line 2552-2561 — should already read dynamically from `council_config.council_members()`; verify it does and don't break the dynamic read), error messages.
- Update each occurrence to reflect the new roster (or remove the hardcoded reference and route through the dynamic banner if that's cleaner).
- Search the rest of the codebase (`bin/`, `references/`, `phase_prompts/`, `ai_context/`, `schemas.md`, `AGENTS.md`, `README.md`, `SKILL.md`) for the old roster strings; update each to the new strings or to a pointer at `bin/council_config.py` for the canonical list.
- Add roster-string regression test: `bin/tests/test_council_config.py` (or extend existing `test_council_semantic_check.py`) — assert `DEFAULT_COUNCIL_MEMBERS == ("claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6")`. Test fails if a future edit accidentally drifts the roster.

### Sub-phase 6b — Availability detection + graceful degradation

Work items:

- Worker locates Phase 4 Council launch logic in `bin/run_playbook.py`. Trace the path that invokes Council member audits — confirm or refactor as needed so that (a) all three reviewers' audit prompts dispatch in parallel via the chosen orchestrator runner, (b) per-reviewer error handling is granular (one reviewer's failure doesn't kill the others).
- Implement per-reviewer error classification:
  - `unsupported_model` (runner says "model X not supported" / "unknown model" / equivalent text patterns specific to each runner) → mark seat as unavailable, capture diagnostic.
  - `network` / `auth` / `timeout` / `other` → log distinctly; for v1.5.7's purposes, treat as unavailable for Council vote, but flag the actual cause in the failure diagnostic.
  - Per-reviewer timeout cap (default 60 seconds, configurable via env var `QPB_COUNCIL_TIMEOUT_SECONDS`) — if a reviewer hangs past the cap, kill the subprocess and mark unavailable.
- Implement vote tabulation:
  - 0 unavailable → normal 3-of-3 audit aggregation.
  - 1 unavailable → degrade to 2-of-2 vote. Emit a `council_degraded` event in `run_state.jsonl` (after Deliverable 3 lands; before Deliverable 3 ships, write to `quality/run_state.jsonl` per the legacy layout). Add a "Council audit composition" section to BUGS.md final summary naming the unavailable model + runner.
  - 2 or 3 unavailable → hard-fail Phase 4. Emit the failure-recovery template (Part D) to stderr + the runner log. Use Deliverable 1's preservation logic so partial Phase 1-3 artifacts survive in `quality.gate-failed-<ts>/`.
- Update `bin/run_state_lib.py` to add the `council_degraded` event type to the schema validator (additive change; existing readers tolerant of unknown event types).
- Update `bin/run_state_lib.py` `run_metadata.json` writer to capture the actual roster used for the run in a new `council_members` field. So historical analysis can distinguish runs that used the default vs. an overridden roster.
- Add regression tests in `bin/tests/test_council_availability.py`:
  1. **0-unavailable**: all three reviewers succeed; normal vote; no `council_degraded` event.
  2. **1-unavailable**: mock one reviewer's runner to return `unsupported_model`; assert 2-of-2 vote, `council_degraded` event present in `run_state.jsonl`, BUGS.md contains "Council audit composition" section naming the unavailable model.
  3. **2-unavailable**: mock two reviewers' runners; assert hard-fail; assert failure-recovery template emitted; assert preservation logic moved `quality/` to `quality.gate-failed-<ts>/`.
  4. **3-unavailable**: all three mock-fail; assert hard-fail with failure template.
  5. **Timeout-as-unavailable**: mock a reviewer's runner that hangs past the timeout cap; assert subprocess killed; assert seat marked unavailable.

### Sub-phase 6c — `~/.qpb/config.yaml` persistence layer

Work items:

- Worker designs the config schema (per Design):
  ```yaml
  runner: copilot
  council_members:
    - claude-opus-4.7
    - gpt-5.5
    - claude-sonnet-4.6
  ```
- Implement `bin/qpb_config.py` (new module): `load_config()` reads `~/.qpb/config.yaml` (XDG-respecting; check `$XDG_CONFIG_HOME/qpb/config.yaml` first, then `~/.qpb/config.yaml`). Returns a typed dict; missing fields return None.
- Implement `save_config(updates)`: writes the file, creating the directory if needed. Preserves any unknown keys in the file (forward-compat). Atomic write via temp-file rename.
- Update `bin/run_playbook.py` argument resolution:
  - Existing flag resolution: CLI `--claude/--copilot/--codex/--cursor` → `args.runner`. v1.5.7 change: if no flag given and `~/.qpb/config.yaml` has `runner: <name>`, use that; else use the existing default of `copilot`.
  - New `--council-roster <m1,m2,m3>` flag for one-run override of `DEFAULT_COUNCIL_MEMBERS`. Resolution: CLI flag → config file → `DEFAULT_COUNCIL_MEMBERS`.
  - Roster validation on read: each member string is checked against a list of well-known model identifiers (the union of v1.5.6's roster + v1.5.7's new roster + a curated short-list of common alternatives like `gpt-4.1`, `claude-sonnet-4.5`, `gemini-2.5-pro`); unknown identifiers emit a startup warning ("`council_members[1]` is `<string>` — unrecognized model identifier; will probe at Council launch") so adopters notice typos before Phase 4. The warning is non-fatal — adopters may have legitimate reasons to specify identifiers QPB doesn't know about.
- Add `qpb config` sub-commands to `bin/run_playbook.py`'s argparse (or a separate entry point if cleaner):
  - `qpb config show` — print current effective config (merged from CLI flags + file + defaults).
  - `qpb config set-runner <name>` — write `runner: <name>` to `~/.qpb/config.yaml`.
  - `qpb config set-roster <m1,m2,m3>` — write `council_members: [m1, m2, m3]` to `~/.qpb/config.yaml`.
  - `qpb config unset` — remove a key, restoring defaults.
- Add regression tests in `bin/tests/test_qpb_config.py`:
  1. **Built-in default used when no config file exists.**
  2. **Config file overrides built-in default.**
  3. **CLI flag overrides config file.**
  4. **Typo in `council_members` emits startup warning** (mock `sys.stderr` capture).
  5. **Round-trip**: `set-runner` then `load_config()` returns the new value; `set-roster` then `load_config()` returns the new tuple.
  6. **`unset` removes the key**, defaults take over.
  7. **Atomic write**: `save_config()` doesn't corrupt the file if interrupted (mock-test the temp-file rename path).

### Sub-phase 6d — Failure-recovery template (LLM-filled)

Work items:

- Worker authors the static template content per the Design (the example block with `[LLM: ...]` markers).
- Embed the template in `bin/run_playbook.py` (or a new module `bin/council_diagnostics.py` for cleanliness). The template is a multi-line string with substitution slots for the runner name, the unavailable model identifiers, and per-reviewer error diagnostics.
- Wire the template into the Sub-phase 6b hard-fail path: when 2-or-3 reviewers fail, build the template with substitutions filled and emit to stderr + runner log + a new file at `quality/logs/<run-id>/council_failure_recovery.md` (so the diagnostic survives even if the operator misses the stderr output).
- Add regression test: `bin/tests/test_council_failure_template.py` — mock 2-of-3 unavailable, capture the emitted template, assert it contains the unavailable model identifiers, the runner name, the override-path instructions, and the `[LLM: ...]` markers.
- Document in `references/runners_and_models.md` (Sub-phase 6e) that the template invites the orchestrating LLM to expand bracketed sections at runtime — this is part of the canonical recovery flow.

### Sub-phase 6e — `references/runners_and_models.md` reference document

Work items:

- Worker drafts `references/runners_and_models.md` (~150-300 lines) per the Design content outline:
  1. Overview: what the four runners are at conceptual level (vendor, scope, install command).
  2. Per-runner sections: `claude-cli`, `gh copilot`, `codex-cli`, `cursor-cli`. Each section: brief description, install command, vendor scope (single-family vs multi-family), authentication model, a deliberately-omitted-matrix note explaining that current model availability is volatile and the orchestrating LLM is the canonical source for runtime model knowledge.
  3. Why Council-of-Three diversity matters: short essay covering why three reviewers (one fewer than four catches almost as much), why model-family diversity (different blind spots), why 2-of-2 degradation is acceptable (still cross-family) but 1-of-1 is not (overreach risk).
  4. How to override the Council roster: cross-reference to `--council-roster` flag, `~/.qpb/config.yaml`, and the `qpb config set-roster` sub-command.
  5. Pointer to the cluster-050 Phase 4 Council banner: explains where adopters see the active roster at runtime.
- Stable content only: install commands, conceptual descriptions, override mechanics, the diversity rationale. NO model-availability matrix (decay-prone). NO claims about which models are reachable through which runners as of which date.
- Add to `references/` install bundle wildcard so it ships with QPB.
- Add regression test: `bin/tests/test_runners_and_models_doc.py` — assert the file exists; assert it contains entries for each of `claude`, `copilot`, `codex`, `cursor`; assert it does NOT contain a model-availability matrix (regex check against tabular formats with model identifiers as cells).

### Worker commits across 6a-6e

Worker commits in nine logical commits (one or two per sub-phase):

1. "v1.5.7: update Council roster to (claude-opus-4.7, gpt-5.5, claude-sonnet-4.6) (sub-phase 7a)"
2. "v1.5.7: regression test for Council roster string (sub-phase 6a tests)"
3. "v1.5.7: per-reviewer fast-fail availability detection + 2-of-2 degradation + hard-fail (sub-phase 6b)"
4. "v1.5.7: regression tests for Council availability paths (sub-phase 6b tests)"
5. "v1.5.7: ~/.qpb/config.yaml persistence layer + qpb config sub-commands (sub-phase 6c)"
6. "v1.5.7: regression tests for qpb config persistence (sub-phase 6c tests)"
7. "v1.5.7: failure-recovery template (LLM-filled) for hard-fail Council (sub-phase 6d)"
8. "v1.5.7: references/runners_and_models.md backgrounder (sub-phase 6e)"
9. "v1.5.7: regression tests for runners_and_models doc + failure template (sub-phases 6d-6e tests)"

Council review (3 lenses) — for the source changes:
- **Override-layer correctness**: config path resolution (XDG-respecting), CLI flag precedence over config, missing fields fall through to built-in defaults, typo validation surfaces unknown identifiers as warnings.
- **Degradation logic correctness**: 0/1/2/3-unavailable cases all behave per spec; per-reviewer timeout works as advertised; `council_degraded` events flow correctly into `run_state.jsonl`; BUGS.md "Council audit composition" section appears for degraded runs.
- **Failure-template accuracy**: static portion makes only stable claims (the override path, the runner names, the conceptual install pattern); volatile claims (which models work in which runners) are routed through `[LLM: ...]` markers, not asserted as fact in QPB source. `references/runners_and_models.md` confirmed to NOT contain a model-availability matrix.

Council ratifies.

Gate to Phase 7: Council ratification + tests green + roster string test pinned + degradation paths verified end-to-end.

---

## Phase 7 — Deliverable 5: Trim `SKILL.md` by moving phase-specific content to `references/`

Goal: reduce `SKILL.md` token count materially (target ~30K BPE tokens) by moving phase-specific reference-grade content into existing or new `references/*.md` files. Same one skill, same install, same adopter UX, same six phases with same gates and artifacts. Behavior preserved by regression-replay against pinned benchmarks before vs. after the trim. **This is the highest runtime-risk deliverable in v1.5.7; sequenced last among source-edit phases so a revert doesn't cascade into other phase work.**

Worker spin-up: `Quality Playbook/v1.5.7_runner/instructions/007a-skill-md-content-classification.md` (sub-phase 7a, the investigation memo) and `007b-skill-md-trim-execution.md` (sub-phase 7b, the moves themselves). Per workspace CLAUDE.md, `SKILL.md` is on the source-edit list — diagnosis-then-Claude-Code lane required.

### Sub-phase 7a — Content classification memo

Work items:

- Worker reads `SKILL.md` end-to-end (2,738 lines as of v1.5.6 ship).
- Worker reads each `references/*.md` file (16 files as of v1.5.6 ship: `challenge_gate.md`, `code-only-mode.md`, `constitution.md`, `defensive_patterns.md`, `exploration_patterns.md`, `functional_tests.md`, `iteration.md`, `orchestrator_protocol.md`, `requirements_pipeline.md`, `requirements_refinement.md`, `requirements_review.md`, `review_protocols.md`, `run_state_schema.md`, `schema_mapping.md`, `spec_audit.md`, `verification.md`).
- Worker reads each `phase_prompts/*.md` to understand which references each phase currently loads on demand.
- Classify each section/paragraph of `SKILL.md`:
  - **Orchestration-essential.** Phase ordering, gate criteria, run lifecycle, the thin glue that makes phases compose, anything cross-cutting that can't reasonably live in one phase's reference. MUST STAY.
  - **Reference-grade.** Domain content that a specific phase needs (defensive pattern taxonomies, Council audit rules, iteration logic, verification taxonomies, etc.) but doesn't drive the orchestration itself. CAN MOVE.
  - **Already-duplicated.** Content that exists both in `SKILL.md` and in a `references/*.md` file. Drift risk. CONSOLIDATE — keep the references/ version, remove from `SKILL.md`, replace with a pointer.
- Produce a memo at `Quality Playbook/v1.5.7_runner/SKILL_md_content_classification_memo.md`:
  - Per-section classification (orchestration-essential / reference-grade / already-duplicated).
  - Rough token-impact estimate per move (using `tiktoken` or chars/4 approximation).
  - Target `SKILL.md` size after trim. Default target: ~30K BPE tokens.
  - Risk flags for any content that's borderline (e.g., paragraph that mentions multiple phases — could go in any of several reference files).
  - Proposed move plan: per-section, source location → destination file/section.
- Operator reviews memo. Either approves the move plan, asks for revisions, or formally defers Deliverable 5 to its own track. **Operator approval of the memo is the gate to sub-phase 7b.**

Gate to 7b: operator approval.

### Sub-phase 7b — Capture pre-trim baseline + execute moves + verify

Work items:

- **Pre-trim regression-replay baseline.** Before any `SKILL.md` edits:
  - Run pinned benchmarks (chi-1.3.45, virtio-1.5.1, express-1.3.50, plus any others currently in `metrics/regression_replay/`) on the un-trimmed `SKILL.md`.
  - Snapshot per-benchmark recall, gate verdict, BUGS.md heading content. Archive these snapshots in `Quality Playbook/v1.5.7_runner/SKILL_md_pre_trim_baseline/`.
  - Use the same model and runner flags that the v1.5.6 baseline used (per `metrics/regression_replay/`'s convention).
- **Apply the moves per the approved memo:**
  - For reference-grade content with an existing target `references/*.md` file: move the prose, replace `SKILL.md` location with a brief pointer (e.g., "See `references/<name>.md` for the full <topic> taxonomy.").
  - For reference-grade content without an existing target file: create a new `references/*.md` file with appropriate naming, move the prose, add to the v1.5.6 install bundle's references list (which the install_skill.py copies via wildcard).
  - For already-duplicated content: remove the `SKILL.md` copy, keep the `references/` version, leave a pointer.
- **Update phase prompts.** For each phase that previously implicitly relied on content now moved out of `SKILL.md`, update `phase_prompts/<phaseN>.md` to load the new reference explicitly. Worker traces phase prompt construction in `bin/run_playbook.py` to verify the runner's substitution logic still finds the references after the move.
- **Bump `SKILL.md` version stamp** to v1.5.7. Per `SKILL.md`'s own version-bump comment: search for the old version string globally; one historical reference to v1.4.6 edgequake benchmarking is intentionally preserved and must NOT be bumped.
- **Post-trim regression-replay.**
  - Run the same benchmarks against the trimmed `SKILL.md` with the same model and flags.
  - Compare per-benchmark recall, gate verdict, BUGS.md heading content to the pre-trim baseline.
  - Tolerance: bug counts match within ±1, gate verdicts match exactly, BUGS.md headings overlap by >90%, no benchmark cell goes from PASS to FAIL on the gate.
  - **If any benchmark shows material recall regression, halt** and either revert the offending move(s) and re-run benchmarks, or revise the move plan.
- **Verify `SKILL.md` size below target.**
  - Use BPE tokenizer (`tiktoken` with `cl100k_base` or equivalent) to measure `SKILL.md` total tokens.
  - Document before/after counts in the commit message and in the v1.5.7 release notes.
  - Assert size below 30K BPE tokens (or the agreed target from the memo).
- **Add regression tests** in `bin/tests/`:
  - **Token count test (`test_skill_md_size.py`):** parse `SKILL.md`, count BPE tokens, assert < target threshold. Test fails if a future edit re-bloats `SKILL.md`.
  - **No-orphaned-pointer test:** for each `See \`references/X.md\`` pointer in `SKILL.md`, assert the target file exists.
  - **Phase-prompt reference-load test:** for each `phase_prompts/<N>.md` that loads a reference, assert the reference file exists and contains the expected content anchor (heading or section name).
- Worker commits in three logical commits:
  1. "v1.5.7: classify `SKILL.md` content + author classification memo (sub-phase 7a)"
  2. "v1.5.7: trim `SKILL.md` by moving phase-specific content to `references/` (sub-phase 7b core)"
  3. "v1.5.7: regression tests for `SKILL.md` trim invariants (token count, no-orphaned-pointer, phase-prompt reference-load)"

Council review (3 lenses):
- **Classification correctness:** every "moved to references" line is genuinely reference-grade, not silently load-bearing. Council samples the moves and inspects.
- **Behavioral preservation:** regression-replay before/after shows no material recall change on any pinned benchmark.
- **Target met:** `SKILL.md` is materially smaller and below the agreed token threshold; phase prompts correctly load the references their phases now depend on.

If Council surfaces a behavioral regression: revert the offending move(s) per the regression-replay diff, re-run benchmarks, iterate. If the entire deliverable surfaces unexpected regressions: revert all v1.5.7 `SKILL.md` changes, defer Deliverable 5 to a later release, ship v1.5.7 with Deliverables 1-4 only.

Council ratifies.

Gate to Phase 8: Council ratification + tests green + token count below target + regression-replay clean.

---

## Phase 8 — Integration testing and ship

Goal: full integration test of all six deliverables; tag and push v1.5.7.

Work items:

- Run a complete cycle against a small benchmark target (e.g., chi). Verify all six deliverables are visible:
  - **Cookbook:** `references/role_map_queries.md` ships in the install; Phase 2 prompt cites it.
  - **Abort preservation:** trigger a synthetic abort (e.g., truncate the agent's EXPLORATION.md to 100 lines before the gate runs); `quality.gate-failed-<ts>/` exists with marker; subsequent run independence verified.
  - **`metrics/` formalization:** `metrics/README.md` and sub-directory READMEs ship; `bin/metrics_reconstruction.py` runs end-to-end against the cell roster and produces output matching the documented conventions.
  - **Log centralization:** all log artifacts under `quality/logs/<run-id>/`; `latest` symlink set; `--logs-flat` smoke test produces v1.5.6 paths; cluster-050 `RUN_MODE.md` lands under `quality/logs/<run-id>/`.
  - **`SKILL.md` trim:** `SKILL.md` is below the size threshold; no-orphaned-pointer test passes; phase prompts load the right references; regression-replay shows no material recall change vs. pre-trim baseline.
- Run the full v1.5.7 test suite: `python3 -m unittest discover bin/tests`. All tests green.
- Run the existing v1.5.5 + v1.5.6 benchmark recovery tests (if present in `metrics/regression_replay/`) to confirm v1.5.7 doesn't regress recall against pinned ground truth.
- Update `CHANGELOG.md` with the v1.5.7 entry summarizing all six deliverables.
- Update `README.md` "What's new" section. Note specifically that the `SKILL.md` trim is invisible to adopters (same install, same UX) but improves per-phase context efficiency.
- Update `ai_context/IMPROVEMENT_LOOP.md` to note that v1.5.7 was driven by external research-grade workload pressure (the model-comparison sweep) plus v1.5.6 close-out carry-forward (`metrics/` formalization) plus an awesome-copilot Skill Validator finding that surfaced an architectural-alignment opportunity (`SKILL.md` trim), with explicit acknowledgment that this kind of pressure is a valid and useful loop input.
- Bump version stamps in `SKILL.md` and any other files carrying a version line. Per `SKILL.md`'s own version-bump comment: search for the old version string globally; one historical reference to v1.4.6 edgequake benchmarking is intentionally preserved in the challenge-gate section and must NOT be bumped.
- Final integration Council review (3 lenses) — only for source changes:
  - **Cross-deliverable interactions:** preservation + cluster-049 auto-recovery, `--logs-flat` + everything, log centralization + cluster-050 `RUN_MODE.md` migration, `metrics/` formalization + v1.7 design alignment.
  - **Adopter-facing readability:** README, CHANGELOG, BENCHMARK_PROTOCOL, TOOLKIT updates render cleanly. (Orientation-doc edits also gate through Toolkit Test Protocol separately.)
  - **Test coverage:** every deliverable has its own regression set + the integration tests cover combinations.
- After Council ratifies and Toolkit Test Protocol green:
  - `git tag v1.5.7 -m "v1.5.7: research-grade hardening (cookbook, abort preservation, metrics formalization, log centralization)"`
  - `git push origin 1.5.7 v1.5.7`
  - **Verify origin SHAs per the workspace CLAUDE.md verify-before-claim rule.** Run `git ls-remote origin v1.5.7 1.5.7 main 1.6.0` and confirm SHAs match what was pushed before claiming "shipped." v1.5.7 is the last v1.5.x release — the goal is to put all cleanup and remaining v1.5.x-related work into v1.5.7 and start the Requirements Review feature work with v1.6.0 (per `docs/design/QPB_v1.6.0_Design.md` and `QPB_v1.6.0_Implementation_Plan.md`). The next-version branch is therefore `1.6.0`.
  - Open the `1.6.0` branch off `1.5.7` HEAD per the standard cadence: `git checkout -b 1.6.0 1.5.7`. Push to origin.
  - Four-ref dance: confirm `v1.5.7`, `1.5.7`, `main`, `1.6.0` all resolve to the expected SHAs.

Deliverable: the v1.5.7 tag is on origin (verified via `git ls-remote`); CHANGELOG and IMPROVEMENT_LOOP.md updated; the `1.6.0` branch is open for Requirements Review feature work.

Gate to release: tag verified on origin via `git ls-remote`, NOT just from the operator's local view.

---

## Coordination with the model-comparison benchmark sweep

The model-comparison sweep that motivated v1.5.7 is operating against pinned QPB versions (v1.5.5 and v1.5.6). v1.5.7 work happens on the `1.5.7` branch and does NOT modify the v1.5.5 or v1.5.6 tags. The sweep can continue uninterrupted during v1.5.7 implementation.

After v1.5.7 ships, the sweep operator may CHOOSE to:

- Continue the existing sweep against v1.5.5/v1.5.6 (already in flight; v1.5.7 is irrelevant to it).
- Start a new sweep round against v1.5.7 to compare runner-version-induced variance.
- Adopt the v1.5.7 log layout for archive workflows (per-cell self-contained directory; no `/tmp` data loss).

These are operator decisions, not v1.5.7 implementation concerns.

---

## Risks and rollback

If any phase's Council review fails or surfaces an unanticipated regression:

- **Phase 2 (cookbook)** is doc-only and trivially revertable.
- **Phase 3 (abort preservation)** is a localized change to one disposal path. If the regression-tests-bite check fails or operator testing surfaces issues, revert the single source commit; preservation does not ship in v1.5.7. The disposal-mechanism trace from Phase 1/Phase 3 is preserved as reference material for the next release.
- **Phase 4 (`metrics/` formalization)** is mostly additive. The documentation files can ship even if the reconstruction script needs revision; if reconstruction surfaces issues, ship the READMEs only and defer the script + Q1/Q2 data to a later release.
- **Phase 5 (log centralization)** is the largest call-site invasion. If migration issues surface, the `--logs-flat` legacy flag becomes the operator's escape hatch. v1.5.7 ships with the flag defaulting to the new layout; if Council surfaces regressions, the default can flip to legacy until a later release.
- **Phase 7 (`SKILL.md` trim)** is the highest runtime-behavior risk. Every line of `SKILL.md` is potentially load-bearing for every QPB run going forward. If regression-replay shows material recall regression on any pinned benchmark: revert the offending move(s) per the diff, re-run benchmarks, iterate. If the entire deliverable surfaces unexpected regressions that can't be cleanly localized: revert all v1.5.7 `SKILL.md` changes, defer Deliverable 5 to a later release, ship v1.5.7 with Deliverables 1-4 only. The investigation memo from sub-phase 7a is preserved either way as reference material for the next attempt.

Worst-case rollback: the entire `1.5.7` branch is abandoned. v1.5.6 remains the latest tagged release. Each deliverable's brief and code review notes are preserved as reference material for whichever release picks the work up next.

---

## Open questions and conditional candidates (cross-reference to Design)

The Design doc enumerates open questions and conditional candidates. Phase 1 resolves them before any source-edit phase begins:

- **Three open questions** (`<run-id>` naming format, `quality.gate-failed-<ts>/` location, cookbook file location) — operator confirms or overrides Design recommendations; Design doc updated with decisions.
- **Four conditional candidates** carried forward from v1.5.6 close-out (`--require-docs` flag, Windows path handling, Persona 19 deep work, adopter-grade orchestration-patterns doc) — operator decides which (if any) surfaced and should be committed to v1.5.7. Default is defer to a later release. If any commit, this Implementation Plan adds new phases (between Phase 7 and Phase 8) and Phase 8's integration test scope expands accordingly.

Operator answers update the Design doc and this Implementation Plan before Phase 1 begins.
