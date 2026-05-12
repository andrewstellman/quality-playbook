# Quality Playbook v1.5.7 — Design Document

*Status: drafted 2026-05-09. Implementation begins after operator review of this doc and the companion Implementation Plan.*
*Authored: 2026-05-09*
*Owner: Andrew Stellman*
*Depends on: v1.5.6 shipped (tag `v1.5.6` on origin at SHA `292e484`; `1.5.6` branch HEAD past tag with post-tag fix-up clusters covering Phase 2-5 validator hardening, AGENTS.md three-tier priority order, README open-target install flow).*

> **Where v1.5.7 sits in the arc.** v1.5.6 shipped three large deliverables that retroactively validated v1.5.5 (Pattern 7 calibration cycle, adopter distribution via `bin/install_skill.py`, `AI_ORCHESTRATION_PATTERNS.md`) plus a substantial post-tag fix-up backlog driven by an in-flight model-comparison benchmark sweep (12 target repos × multiple LLMs, generating research data for an upcoming paper). That fix-up backlog already shipped clusters 044 (`--next-iteration` suggestion form), 049 (role-map auto-recovery via deterministic exclude filter), and 050 (`--benchmark-mode` flag + Phase 4 Council roster banner + BENCHMARK_PROTOCOL.md / TOOLKIT.md docs) inside the v1.5.6 timeline. v1.5.7 picks up the remaining items the same sweep surfaced — the ones that didn't fit cleanly into v1.5.6's Phase 5 release window — plus a metrics-formalization deliverable carried forward from v1.5.6 close-out. v1.6 (Requirements Review) and v1.7 (Statistical Process Control) come after; v1.5.7 is deliberately scoped tight so v1.7's SPC machinery has a runner whose output is reproducible, self-contained, and instrumented.

---

## Motivation

### Six deliverables, one release, picked together for a reason

v1.5.7 ships six things. Three came from the v1.5.6 model-comparison benchmark sweep; one is a v1.5.6 close-out carry-forward; one is an architectural improvement surfaced by the awesome-copilot Skill Validator; one closes a Council-resilience gap that surfaced in the same PR review (`gh copilot` silently dropped `gemini-2.5-pro` support, breaking the v1.5.6 Phase 4 Council for adopters using the copilot runner):

1. **Phase 2 gate-failure artifact preservation.** When the Phase 2 gate aborts, the cell's `quality/` directory is empty by the time the operator inspects it. The agent's outputs that triggered the abort — the rejected EXPLORATION.md, the malformed role map, the partial PROGRESS.md — are gone. The operator can read the gate's diagnostic message in the runner's log, but cannot inspect WHAT the agent produced. v1.5.7 preserves the failed artifact set into `quality.gate-failed-<UTC-timestamp>/` for diagnostic inspection. (Workspace-side staging brief at `Quality Playbook/Reviews/QPB_v1.5.7_Backlog/PreserveQualityOnGateFail.md` for original symptom + reproduction + patch sketch.)

2. **Role-map query cookbook.** Agents in Phase 2 routinely construct `jq` queries against `quality/exploration_role_map.json` to enumerate files by role. Without a canonical query reference, agents (observed: gemini-2.5-pro on virtio) hallucinate non-existent paths like `.roles.source[]` instead of the actual `.files[] | select(.role == "code")`. Hallucinated queries return empty, downstream artifacts are silently impoverished, and the gate doesn't catch it. v1.5.7 adds `references/role_map_queries.md` with canonical patterns and a Phase 2 prompt addition pointing at it.

3. **Centralized log emission at `quality/logs/<run-id>/`.** v1.5.6 writes logs to multiple paths inside and outside the cell directory (`<parent>/<cell>-playbook-<ts>.log`, `quality/control_prompts/`, `quality/results/`, `quality/run_state.jsonl`), with no canonical "everything from this run" location. Operator wrappers like the model-comparison sweep's `run-model-folder.sh` resort to `/tmp` for driver logs, which clears on reboot. For research workflows where every log is potential evidence, this is data loss waiting to happen. v1.5.7 centralizes all log emission under `quality/logs/<run-id>/`, adds `quality/logs/` to the documented `.gitignore` template, and provides a `--logs-flat` legacy flag for adopters whose tooling reads from the old paths.

4. **`metrics/` formalization** (carry-forward from v1.5.6 close-out). The improvement-loop methodology referenced throughout `IMPROVEMENT_LOOP.md` cites a `metrics/` directory tree (recall data, calibration ledgers, regression-replay output) that's been growing organically since v1.5.4. v1.5.7 formalizes the directory structure, ships a `metrics/README.md` describing the tree's conventions, and adds a reconstruction script that rebuilds Q1 + Q2 historical data from current artifacts so the SPC machinery in v1.7 has a stable input shape to read from. (Pending task #113 from the v1.5.6 task list.)

5. **Trim `SKILL.md` by moving phase-specific content to `references/`.** The awesome-copilot Skill Validator flagged QPB's `SKILL.md` at 73K BPE tokens with the warning "comprehensive skills hurt performance by 2.9pp on average. Consider splitting into 2-3 focused skills." The "split into multiple skills" recommendation is wrong for QPB's architecture (the phase architecture already isolates cumulative token cost via per-phase sub-agent contexts), but the underlying observation is correct: every phase invocation loads the full `SKILL.md` whether or not the loaded content is relevant to that phase. v1.5.7 addresses this by moving phase-specific reference-grade content out of `SKILL.md` and into existing or new `references/*.md` files. Same one skill, same install, same adopter UX, same behavior — just a leaner orchestration spine that strengthens the phase architecture. The token reduction is not the goal in itself; the goal is alignment with the phase architecture's existing isolation principle.

6. **Council roster modernization, availability resilience, and override layer.** The Phase 4 Council currently encodes a fixed roster (`claude-opus-4.7`, `gpt-5.4`, `gemini-2.5-pro`) in `bin/council_config.py`. Two real problems with this: (a) `gh copilot` silently dropped `gemini-2.5-pro` support — so any adopter using the v1.5.6 skill with the copilot runner gets a broken Phase 4 Council; (b) more generally, models change faster than skill releases, so any roster pinned at ship time decays. v1.5.7 addresses this with a four-part deliverable: update the roster to a currently-deployable set (`claude-opus-4.7`, `gpt-5.5`, `claude-sonnet-4.6`); add fast-fail availability detection at Council launch with graceful 2-of-2 degradation when one member is unreachable and hard-fail when two or more are; add a `~/.qpb/config.yaml` persistence layer so adopters can override the roster locally without editing source; and ship a structured failure-recovery template that the orchestrating LLM fills in with current runner-specific model knowledge so adopters get actionable recovery guidance regardless of how stale their installed skill is. The reference document is a stable backgrounder (what runners are, install commands, why Council diversity matters), NOT a decay-prone availability matrix — the volatile information lives in the LLM's runtime knowledge, not in QPB source.

These six items share one property: **each one closes a research-data-integrity, methodology-machinery, architectural-alignment, or environmental-decay gap that surfaced during or immediately after v1.5.6 ship**. Bundling them produces a release whose theme is "v1.5.6's runner was correct; v1.5.7 makes its outputs research-grade, its supporting metrics tree formal, its skill prose better-aligned with the phase architecture, and its Council resilient to environmental drift."

### Why each was deferred to v1.5.7 rather than landed in v1.5.6

- **Phase 2 abort preservation.** The wipe-on-abort behavior (or the equivalent "quality/ is empty after abort" symptom — the cross-model chat noted the abort path at `bin/run_playbook.py:3378` only logs and returns; the actual disposal mechanism may be elsewhere) was an unintentional regression visible only when the model-comparison sweep started using QPB as a benchmark engine where every aborted cell is potential research data. Surfaced after v1.5.6 tag; preservation is a small change with high diagnostic value.

- **Role-map query cookbook.** The hallucination pattern was visible in earlier runs but only got root-caused when gemini-2.5-pro made the same mistake explicit in the Phase 2 transcript. Documentation-grade fix; doesn't require runner code changes; missed the v1.5.6 release window.

- **Centralized log emission.** The current scattered log layout has been QPB's shape since multi-phase orchestration was introduced; nobody complained until research-grade reproducibility became a requirement. The model-comparison sweep already lost driver logs to `/tmp` clearing; centralizing prevents recurrence and makes per-cell archives self-contained. Too invasive for the v1.5.6 close-out window.

- **`metrics/` formalization.** Tracked as task #113 in the v1.5.6 task list; deferred at v1.5.6 close-out as a "post-1.5.6" item. v1.5.7 is the natural home — the directory tree formalization is upstream of v1.7's SPC machinery, and shipping it in v1.5.7 lets v1.7 consume the formalized shape rather than spend time formalizing on the way to control charts.

- **`SKILL.md` trim.** The awesome-copilot Skill Validator's "comprehensive skill" warning surfaced during PR #1402 review on 2026-05-10. The fix isn't urgent (QPB still works correctly with a 73K-token `SKILL.md`), but the validator's observation is correct: per-phase token cost can be reduced by aligning the skill prose more tightly with the phase architecture. v1.5.7 is the natural home because (a) it's a cleanup release whose theme is "make v1.5.6's outputs better"; (b) the work fits the cleanup framing rather than feature work; (c) v1.6.0 is committed to Requirements Review and shouldn't absorb architectural-prose work.

- **Council resilience and override layer.** Surfaced on 2026-05-10 when `gh copilot` was observed to have silently dropped `gemini-2.5-pro` support, breaking v1.5.6's Phase 4 Council for any adopter using the copilot runner. The fix is urgent for adopters whose installed skill ships with the v1.5.6 roster — without the override layer + availability resilience, they have a broken Phase 4 with no recovery path that doesn't require updating QPB itself. v1.5.7 is the natural home because skills outlive model rosters in general (not just gemini-via-copilot), and an adopter's option to override the roster locally is a robustness property that should be in the system, not a per-incident hot-fix.

### What v1.5.7 explicitly does NOT do

It doesn't introduce new playbook capabilities. The skill prose, the phase architecture, the iteration strategies, the divergence model, the quality gate's set of validations — all of those are stable. v1.5.7 changes the runner's output shape (logs, abort behavior) and adds documentation references; it does not add new phases, new iteration strategies, new gate checks, or new artifact types beyond `metrics/`'s formalized tree.

It doesn't touch v1.6 scope. Requirements Review work (REQ schemas, Wiegers attributes, targeted re-derivation) stays out of every deliverable.

It doesn't ship statistical-control machinery. Control charts, run rules, multi-cell DoE, defect-rate dashboards — all v1.7. v1.5.7 makes v1.7's input data cleaner and its directory tree formal, but does not start v1.7 work.

It doesn't touch the Council membership or the Council's audit logic. The `--benchmark-mode` flag (v1.5.6 cluster 050) already gives operators the option to skip Phase 4 entirely; v1.5.7 doesn't change how Phase 4 works when it does run.

It doesn't change the role taxonomy, the role map's schema, or the Phase 2 gate's validation rules. The cookbook documents the existing schema; it doesn't modify it.

It doesn't split QPB into multiple skills. The awesome-copilot Skill Validator's "consider splitting into 2-3 focused skills" recommendation is rejected as architecturally wrong for QPB — splitting along phase boundaries would force adopters to install 2-3 skills, change the install_skill.py UX, change the awesome-copilot bundle structure, and complicate inter-phase handoff. Deliverable 5 addresses the underlying token-economy concern via `SKILL.md` content trim (move phase-specific content to `references/` that phases load on demand) — same one skill, same install, same UX.

It doesn't re-do work already shipped in v1.5.6 fix-up clusters 044, 049, or 050 — see the **Already-shipped work referenced for context** section below.

---

## Already-shipped work referenced for context

The model-comparison sweep that motivated v1.5.7 was running against v1.5.6 cells installed before three v1.5.6 fix-up clusters landed. That timing produced observed symptoms which were already addressed in subsequent v1.5.6 commits, NOT v1.5.7 work. Captured here so future readers don't mistake them for v1.5.7 deliverables:

- **Cluster 044 — `--next-iteration` suggestion form fix.** Shipped in v1.5.6. `bin/run_playbook.py:4287-4302` emits canonical `python3 -m bin.run_playbook` invocation; `runner_flag` dict includes `"copilot": " --copilot"`. Both the script-style invocation defect (rejected by the package-module guard) and the dropped `--copilot` flag for `--copilot` users are fixed.

- **Cluster 049 — Role-map auto-recovery via deterministic exclude filter.** Shipped in v1.5.6. `bin/role_map.py:675 maybe_recover_role_map` deterministically filters role maps via hardcoded excludes + `.gitignore` / `.hgignore` parsing (NOT `git ls-files` — the architectural rationale is VCS-agnostic: the helper works for git, hg, or no VCS at all). `provenance == "exclude-filtered"`. Wired into the Phase 2 gate handler at `bin/run_playbook.py:1100`. Argparse flag `--no-role-map-auto-recovery` registered at `bin/run_playbook.py:405`. Comprehensive regression tests at `bin/tests/test_role_tagging.py:1270-1581`.

- **Cluster 050 — `--benchmark-mode` flag + Phase 4 Council roster banner + docs.** Shipped in v1.5.6. Argparse flag at `bin/run_playbook.py:426`; mutual-exclusion logic with `--full-run` / `--phase` / `--next-iteration` / `--strategy` / `--iterations` at lines 661-686. Phase 4 Council roster banner ("defense-in-depth log signal so operators scanning logs see the model expansion") emitted regardless of `--benchmark-mode`. Documented in `ai_context/BENCHMARK_PROTOCOL.md:43-47` and `ai_context/TOOLKIT.md:391`.

These are noted because earlier v1.5.7 design drafts (since superseded by this revision) treated them as v1.5.7 deliverables. They are not.

---

## Scope

### Core deliverables

1. **Phase 2 gate-failure artifact preservation in `bin/run_playbook.py`.** Modify the abort path so that when a Phase 2 gate failure aborts the run, the cell's `quality/` directory is renamed to `quality.gate-failed-<UTC-timestamp>/` rather than being left empty. Write a marker file at the new location's root capturing the gate violation message, the phase group, the cell name, the abort timestamp, the runner version, and the runner's `--model` value. Multiple aborted attempts on the same cell accumulate as siblings. The actual disposal-mechanism location must be traced during implementation: the cross-model chat that surfaced the symptom noted that the explicit abort path "just logs and returns exit code 1 — it doesn't explicitly wipe `quality/`," so either there's a cleanup elsewhere or the agent's writes via tool calls didn't persist; the implementing worker must locate the disposal path before adding preservation logic.

2. **Role-map query cookbook at `references/role_map_queries.md`.** New reference file with canonical `jq` patterns for the role map: source-code paths, source filtered by extension, test paths, skill-tool paths with prose references, role-by-count aggregations, total-bytes-by-role aggregations. Enumerates anti-patterns (`.roles.source[]`, `.roles.code[]`, `.files.code[]`, `.files[] | select(.role == "source")`) with explicit "DO NOT use" annotations. Phase 2's prompt template gets a paragraph pointing agents at this file before constructing role-map queries.

3. **Centralized log emission at `quality/logs/<run-id>/` in `bin/run_playbook.py`, `bin/run_state_lib.py`, `phase_prompts/`, and `quality_gate.py`.** Move all QPB-emitted logs to `quality/logs/<run-id>/` where `<run-id>` is a UTC timestamp (e.g., `20260509T184231Z`). Migration scope: per-target playbook log moves from `<parent>/<cell>-playbook-<ts>.log` to `<cell>/quality/logs/<run-id>/runner.log`; per-phase control prompts move from `quality/control_prompts/` to `quality/logs/<run-id>/phase<N>.{input,output}.txt`; `run_state.jsonl` moves from `quality/run_state.jsonl` to `quality/logs/<run-id>/run_state.jsonl`; quality gate log moves from `quality/results/quality-gate.log` to `quality/logs/<run-id>/quality-gate.log`; run metadata moves from `quality/results/run-<ts>.json` to `quality/logs/<run-id>/run_metadata.json`. Add a `quality/logs/latest` symlink pointing at the most recent `<run-id>/`. Add `quality/logs/` to `setup_repos.sh`'s installed `.gitignore` template. Provide a `--logs-flat` (or `QPB_LOGS_LEGACY=1` env var) backward-compat path. v1.5.6's `--benchmark-mode` `RUN_MODE.md` marker (currently at `quality/RUN_MODE.md`) moves under `quality/logs/<run-id>/` with this deliverable.

4. **`metrics/` directory formalization.** Ship `metrics/README.md` documenting the directory tree's conventions (sub-directories: `regression_replay/`, `calibration/`, `bootstrap_recall/`, `cross_version_recall/`); add a `bin/metrics_reconstruction.py` script that rebuilds Q1 + Q2 historical data from current cell artifacts (per-cell `quality/run_metadata.json` and `quality/BUGS.md` heading parses). The reconstruction script is run once at v1.5.7 ship to produce a reference data set; it lives in `bin/` for adopters who want to regenerate metrics from their own historical cells. Backward compatibility: existing scripts that read from the (currently informal) `metrics/` paths continue working — the formalization adds documentation and one reconstruction tool, not new schemas.

5. **`SKILL.md` trim — pure refactor moving phase-specific content to `references/`.** Identify content in `SKILL.md` that's phase-specific reference-grade (defensive pattern taxonomies, Council audit rules, iteration-strategy descriptions, verification taxonomies, functional-test patterns, etc.). Move that content **verbatim** into existing or new `references/*.md` files; replace the `SKILL.md` location with a pointer (e.g., "See `references/X.md` for ..."). Update phase prompts in `phase_prompts/*.md` to load the references they need on demand. **Pure refactor — text preserved exactly; no consolidation of duplicated content, no rewording, no cleanup.** Result: same one skill, same install, same adopter UX, same six phases with the same gates and artifacts — but `SKILL.md` itself is materially smaller, and each phase's per-invocation context loads only the references that phase actually needs. Target: `SKILL.md` under the validator's "comprehensive" threshold (the validator's exact threshold isn't specified, but a target of <30K BPE tokens roughly halves the current size and aligns with the validator's "consider splitting into 2-3" arithmetic without actually splitting). Behavioral preservation is verified by a mechanical equivalence check: for each phase, the union of (`SKILL.md` + loaded references) must be byte-equivalent before vs. after the trim. Phase 8 integration testing additionally runs the existing benchmark recovery suite as a confidence-building exercise; that is NOT Phase 7's verification gate.

6. **Council roster modernization, availability resilience, and override layer.** Five sub-deliverables (described in detail in the Design section below): (a) update `bin/council_config.py` `DEFAULT_COUNCIL_MEMBERS` tuple to `(claude-opus-4.7, gpt-5.5, claude-sonnet-4.6)` and update banner/help-text strings everywhere the old roster is hardcoded; (b) fast-fail availability detection at Council launch — dispatch all three reviewers in parallel via the chosen orchestrator runner, catch the runner's "model not supported" error per reviewer, degrade to 2-of-2 if exactly one is unavailable, hard-fail if two or more are; (c) `~/.qpb/config.yaml` persistence layer that lets adopters override the default roster (and chosen orchestrator runner) without editing source — CLI flags override config, config provides defaults, built-in `DEFAULT_COUNCIL_MEMBERS` backfills; (d) structured failure-recovery template that the orchestrating LLM fills in with current runner-and-model knowledge — the template ships in QPB source as a stable form, the LLM provides volatile information at runtime; (e) `references/runners_and_models.md` reference document covering what each of the four runners is, install commands, and why Council-of-Three diversity matters — explicitly NOT a model-availability matrix (which would decay), but a stable backgrounder.

### Operating principles

- **All six deliverables are independently revertable.** If any one of them surfaces an unanticipated regression during Council review or operator testing, it ships in a later release — the others proceed.
- **Backward compatibility on log paths until v1.6.0.** The `--logs-flat` legacy flag preserves v1.5.6 paths for adopters whose tooling reads from those locations. Default is the new layout; legacy is opt-in. Drop the legacy flag in v1.6.0 (one-version deprecation window — v1.5.7 is the last v1.5.x release, so v1.6.0 is N+1).
- **Each deliverable has a Council review** (3 lenses per CALIBRATION_PROTOCOL.md Mode 1 nested-panel rules from the workspace CLAUDE.md). Orientation-doc edits (TOOLKIT.md, BENCHMARK_PROTOCOL.md, IMPROVEMENT_LOOP.md, README.md, DEVELOPMENT_PROCESS.md) under each deliverable get the Toolkit Test Protocol gate per the workspace CLAUDE.md carve-out, NOT Council; mixed commits (orientation doc + source) go through the Council/Claude-Code lane.
- **No changes to v1.6 surfaces.** Requirements Review work stays out of every deliverable.
- **No new playbook capabilities.** v1.5.7 hardens what v1.5.6 already does; it does not extend the playbook's substantive scope.
- **Honest framing on the empirical motivation.** This release was driven by external research-grade workload pressure (the model-comparison sweep) plus v1.5.6 close-out carry-forward. Document that explicitly in `IMPROVEMENT_LOOP.md`'s release notes section so future sessions reading the loop history see what kind of pressure produced this kind of release.

### Out of scope (deferred to later releases)

- **Council membership changes.** Adding/removing Council members, model swaps, dynamic-model Council. v1.7+ if motivated.
- **Schema changes to the role map.** v1.5.7's cookbook documents the existing schema; no shape changes.
- **Schema changes to `run_state.jsonl`.** v1.5.7 adds an additive `log_layout` field on the `cycle_start` event; event-type schemas and required field invariants are unchanged.
- **Multi-cell calibration cycles** (factorial, Latin square, augmented designs). v1.7.
- **SPC machinery** (control charts, run rules, X/MR analysis on cell.json). v1.7.
- **SDLC defect-rate dashboard.** v1.7.
- **Cross-version trend tracking pipeline.** v1.7.
- **Cross-operator workflow.** v1.8.
- **Requirements Review UX.** v1.6.
- **Phase-prompt restructuring beyond the cookbook reference.** The Phase 2 prompt gets one paragraph addition pointing at `references/role_map_queries.md`. No other phase prompts change in v1.5.7.

---

## Design

### Deliverable 1 — Phase 2 gate-failure artifact preservation

**Symptom.** When the Phase 2 gate aborts a run (role-map size, EXPLORATION.md too short, schema violation, etc.), the cell's `quality/` directory is empty by the time the operator inspects it. The agent's outputs that triggered the abort — the rejected EXPLORATION.md, the malformed role map, the partial PROGRESS.md — are not on disk. The operator can read the gate's diagnostic message in the runner's per-target log, but cannot inspect WHAT the agent produced.

For adopters this is a debuggability paper-cut. For research-grade workflows where every aborted cell is potential evidence (was the agent's EXPLORATION.md substantively short or stub-quality with placeholders? did the role map's wrong entries cluster in build outputs or vendored dependencies?), this is a data-loss vector that prevents per-cell forensic analysis.

**Reproduction (observed in v1.5.6 model-comparison sweep, 2026-05-08).** gpt-5.4-mini against cobra produced a 109-line EXPLORATION.md (the gate requires ≥120). After abort:

```
18:36:24   Phase 1 complete: 109 lines in EXPLORATION.md
18:36:24   GATE FAIL Phase 2: EXPLORATION.md is only 109 lines (expected 120+)
18:36:24 ABORT: Phase group 2 gate failed for cobra

$ ls cobra/quality/
ls: cannot access 'cobra/quality/': No such file or directory
```

The 109-line EXPLORATION.md the gate read is gone. Same pattern for express, where the gate failed on a missing `skill_prose_reference` field — the malformed role map is gone. (Full reproduction context in workspace-side staging brief at `Quality Playbook/Reviews/QPB_v1.5.7_Backlog/PreserveQualityOnGateFail.md`.)

**Diagnostic note for the implementing worker.** The cross-model chat that surfaced this symptom traced the abort path in `bin/run_playbook.py` and noted: "the abort path just logs and returns exit code 1 — it doesn't explicitly wipe `quality/`. So either there's a cleanup elsewhere or the agent's writes via tool calls didn't persist to disk in the way assumed." The implementing worker must locate the actual disposal mechanism (search for `quality.rmtree`, `shutil.rmtree`, `cleanup_repo`, or any path-removal call invoked from the Phase 2 abort path or from `setup_repos.sh --replace`) BEFORE adding preservation logic. If the disposal happens inside `setup_repos.sh`, the preservation must trigger before the next-run setup_repos invocation, not just inside `bin/run_playbook.py`.

**Preservation design.** When a Phase 2 gate failure aborts the run:

1. If `<cell>/quality/` exists and contains files at the time of abort, MOVE it to `<cell>/quality.gate-failed-<UTC-timestamp>/` (using a UTC ISO-8601 timestamp like `20260509T182942Z` — avoid local-time variation that would make sort order machine-dependent).
2. Write a `<cell>/quality.gate-failed-<ts>/GATE_FAILURE.md` marker file capturing:
   - The exact gate violation message
   - The phase group and check that failed
   - The cell name
   - The abort timestamp
   - The runner version (`v1.5.7`)
   - The runner's `--model` value (or `(default)` if unset)
   - A note: "This is preserved evidence from a failed run, NOT a successful artifact set. The next run on this cell will create a fresh `quality/`. To clean up, simply remove this directory."
3. Log: `"Preserved Phase 1 evidence at quality.gate-failed-<ts>/. Next run will create a fresh quality/."`

**Multiple aborted attempts.** If a cell aborts multiple times, each preservation creates a new sibling: `quality.gate-failed-20260509T120000Z/`, `quality.gate-failed-20260509T130000Z/`, … The current `quality/` always represents the most recent attempt; preserved sets are never overwritten or merged.

**Disk-space discipline.** Each preserved set carries the same disk footprint as a partial Phase 1 run (typically 10s of KB to a few MB). Adopters who run many failed cells should `rm -rf quality.gate-failed-*` periodically. Document in TOOLKIT.md.

**Interaction with v1.5.6 cluster 049 auto-recovery.** Auto-recovery (`bin/role_map.py:675 maybe_recover_role_map`) runs BEFORE the abort path. If auto-recovery succeeds, the run proceeds and no preservation is triggered. If auto-recovery fails (or is opted out via `--no-role-map-auto-recovery`), the abort path runs and `quality/` is preserved per this deliverable. The two compose cleanly.

**Idempotence and safety.** The preservation logic uses `Path.rename` which is atomic on POSIX filesystems. If the runner crashes between the rename and the marker-file write, the preserved directory exists but lacks the marker — recoverable, and the operator can identify the directory as "post-abort" by its naming convention.

### Deliverable 2 — Role-map query cookbook

**Symptom.** Agents in Phase 2 routinely construct `jq` queries against `quality/exploration_role_map.json` to enumerate files by role for downstream contract extraction, three-pass code review, and similar work. The role map's schema (top-level `files` ARRAY of records, each with a `role` field whose value is one of the documented taxonomy strings) is non-obvious for agents who guess based on intuition.

Empirically observed: gemini-2.5-pro on the virtio benchmark cell wrote `jq -r '.roles.source[]' quality/exploration_role_map.json | grep -E '\.c$'` — a query against a path (`.roles.source[]`) that doesn't exist in the schema. The query returned empty, the `$( ... )` substitution produced no file arguments, the downstream `grep` ran with no source files, and the contract extraction silently produced impoverished output.

The Phase 2 gate doesn't catch this — it validates artifact shape, not the substantive richness of intermediate query results.

**Cookbook design.** New reference file `references/role_map_queries.md` (~80–120 lines) with structure:

```markdown
# Role-map query cookbook

The role map at `quality/exploration_role_map.json` has a top-level `files`
array (NOT a `.roles` object). Each file record is `{path, role, size_bytes,
rationale}` (plus `skill_prose_reference` for `skill-tool` entries). Roles
are taxonomy values defined in `bin/role_map.py::ROLE_DESCRIPTIONS`
(see that file for the canonical list — DO NOT enumerate roles in this
cookbook because the cookbook would drift).

## Canonical queries

(All source-code file paths)
    jq -r '.files[] | select(.role == "code") | .path' quality/exploration_role_map.json

(Source files filtered by extension — example: C)
    jq -r '.files[] | select(.role == "code") | .path' quality/exploration_role_map.json | grep -E '\.c$'

(All test file paths)
    jq -r '.files[] | select(.role == "test") | .path' quality/exploration_role_map.json

(All skill-tool paths with their prose references)
    jq -r '.files[] | select(.role == "skill-tool") | "\(.path)\t\(.skill_prose_reference)"' quality/exploration_role_map.json

(Count files by role)
    jq -r '.files | group_by(.role) | map({role: .[0].role, count: length})' quality/exploration_role_map.json

(Total bytes by role)
    jq -r '.files | group_by(.role) | map({role: .[0].role, bytes: ([.[] | .size_bytes] | add)})' quality/exploration_role_map.json

## Anti-patterns (DO NOT use)

- `.roles.source[]` — `.roles` does not exist in the schema
- `.roles.code[]` — same; the role map is `.files[]`, not `.roles.<name>[]`
- `.files.code[]` — `.files` is an array, not an object
- `.files[] | select(.role == "source")` — there is no "source" role; the implementation-code role is `code`

## Discovery — what's in the role map?

If you're constructing a query and don't remember the schema, peek at the top:

    jq '. | {schema_version, provenance, files_count: (.files | length),
            roles: (.files | [.[] | .role] | unique)}' quality/exploration_role_map.json

This returns the schema version, provenance, total file count, and the
distinct roles present, all in one query. Use it to ground subsequent queries.
```

Note the deliberate decision to NOT enumerate roles in the cookbook itself — the canonical taxonomy lives in `bin/role_map.py::ROLE_DESCRIPTIONS` and the cookbook points there to avoid drift. The discovery query at the bottom reads the live role set.

**Phase 2 prompt addition.** In the Phase 2 prompt template (per `phase_prompts/phase2.md` in the v1.5.6 install bundle, or wherever the Phase 2 prompt template currently lives), insert a paragraph in the appropriate "tools" or "role map usage" section:

> When querying `quality/exploration_role_map.json` to enumerate files by
> role, consult `references/role_map_queries.md` for canonical jq patterns.
> Do NOT construct jq paths from memory — the role map's list-of-records
> shape is non-obvious and several intuitively-named paths (e.g.,
> `.roles.source[]`) do not exist. Read the cookbook, copy a canonical
> query, then adapt extension filters as needed.

**No runtime/code change.** This deliverable is documentation-only on the QPB-source side. The runner does not validate that agents read the cookbook; the cookbook is a quality-of-life prompt enhancement.

### Deliverable 3 — Centralized log emission at `quality/logs/<run-id>/`

**Symptom.** v1.5.6 writes logs to multiple paths inside and outside the cell directory:

| Log type | v1.5.6 path |
|---|---|
| Per-target playbook log | `<parent>/<cell>-playbook-<timestamp>.log` |
| Per-phase prompt input | `<cell>/quality/control_prompts/phase<N>.input.txt` |
| Per-phase prompt output | `<cell>/quality/control_prompts/phase<N>.output.txt` |
| Run-state event log | `<cell>/quality/run_state.jsonl` |
| Quality gate output | `<cell>/quality/results/quality-gate.log` |
| Run metadata | `<cell>/quality/results/run-<timestamp>.json` |
| Cluster-050 RUN_MODE marker | `<cell>/quality/RUN_MODE.md` |
| Wrapper-script driver log | (operator's choice; e.g., `/tmp/...`) |

Five problems:

1. **The runner log lives OUTSIDE the cell.** `<cell>-playbook-<ts>.log` sits at the parent level. `tar` or `cp -a` on the cell directory misses the log.
2. **Logs are scattered across `control_prompts/`, `results/`, `run_state.jsonl` directly under quality/, and outside-cell paths.** No canonical "logs from this run" location.
3. **`.gitignore` ergonomics are awkward.** Adopters wanting to commit `quality/` artifacts need per-file exclusions for transient logs.
4. **Operator wrappers default to `/tmp` for driver logs.** `/tmp` clears on reboot; research data evaporates.
5. **Substrate logs (`run_state.jsonl`) sit alongside artifact files (`BUGS.md`).** No clean separation between data and process records.

**Centralized layout (v1.5.7).**

```
<cell>/quality/
  logs/
    <run-id>/                           # UTC timestamp like 20260509T184231Z
      runner.log                        # was <parent>/<cell>-playbook-<ts>.log
      run_state.jsonl                   # was quality/run_state.jsonl
      run_metadata.json                 # was quality/results/run-<ts>.json
      phase1.input.txt                  # was quality/control_prompts/phase1.input.txt
      phase1.output.txt                 # was quality/control_prompts/phase1.output.txt
      phase2.input.txt
      phase2.output.txt
      ... (per phase)
      quality-gate.log                  # was quality/results/quality-gate.log
      driver.log                        # NEW — wrapper scripts write HERE
      RUN_MODE.md                       # was quality/RUN_MODE.md (cluster 050)
    latest -> <run-id>                  # symlink to most-recent run
  EXPLORATION.md                        # artifact files unchanged
  REQUIREMENTS.md
  CONTRACTS.md
  BUGS.md
  PROGRESS.md
  patches/
  ...
```

**Run-id naming.** UTC ISO-8601 timestamp without separators: `20260509T184231Z`. Always 16 characters. Sorts lexicographically in chronological order. Reproducible across machines (no local-time variation).

**Multiple-run accumulation.** Each run creates a new `<run-id>/` sibling. Earlier runs are never overwritten or merged. The `quality/logs/latest` symlink updates to point at the most recent. A cell that has been run 5 times has 5 sibling directories under `quality/logs/`.

**Artifact files unchanged.** `EXPLORATION.md`, `REQUIREMENTS.md`, `BUGS.md`, etc. continue to live directly under `quality/`. The latest run's artifacts are at the canonical paths; the logs that produced them are at `quality/logs/latest/`.

**Migration scope (files that must change).**

- `bin/run_playbook.py` — many call sites that emit log paths. Refactor to a single `_run_log_dir(repo_dir, run_id)` helper that returns `repo_dir / "quality" / "logs" / run_id`; update all log-write call sites to use it. The cluster-050 `RUN_MODE.md` writer is one of those call sites.
- `bin/run_state_lib.py` — the `append_event` and `write_progress_md` helpers write to `quality/run_state.jsonl`. Change to write to `quality/logs/<run-id>/run_state.jsonl`. Add a reader-side fallback: `read_events()` first looks at `quality/logs/<run-id>/run_state.jsonl`, then `quality/logs/latest/run_state.jsonl`, then `quality/run_state.jsonl` (legacy), and uses the first that exists.
- `phase_prompts/` — any prompt template that references `quality/control_prompts/phase<N>.input.txt` or similar must be updated.
- `quality_gate.py` (in `.github/skills/quality_gate/quality_gate.py`) — reads the gate log and run metadata. Update to look in `quality/logs/<run-id>/` (or `quality/logs/latest/`) first, then fall back to the legacy paths.
- `setup_repos.sh` — installs a `.gitignore` template (or documents one). Add `quality/logs/` to the gitignore.
- `ai_context/TOOLKIT.md`, `ai_context/BENCHMARK_PROTOCOL.md`, `ai_context/DEVELOPMENT_PROCESS.md` — documentation updates (orientation-doc lane: Toolkit Test Protocol gate, not Council).

**Backward compatibility (`--logs-flat` flag).** Adopters whose tooling reads from v1.5.6 paths can pass `--logs-flat` (or set `QPB_LOGS_LEGACY=1`) to restore v1.5.6 behavior. The legacy mode emits logs to the old scattered paths exactly as v1.5.6 did. The legacy flag is documented as deprecated; v1.6.0 removes it. One-version deprecation window (v1.5.7 is the last v1.5.x release).

**Wrapper-script benefit.** The model-comparison sweep's `run-model-folder.sh` (and equivalent operator wrappers) currently write driver logs to `/tmp/qpb-<model>-<round>-<ts>/`. After v1.5.7, wrappers should write to `<cell>/quality/logs/<run-id>/driver.log` instead. The wrapper computes the run-id at the moment it invokes the runner; the runner writes to the same `<run-id>` so wrapper output and runner output sit in the same directory. For QPB internally, the model-comparison sweep's `run-model-folder.sh` is updated as part of v1.5.7 (or shipped separately as an operator-script update). Adopter wrappers are out of scope for QPB to update; documentation explains the convention.

**Schema additions to `run_state.jsonl`.** Each `cycle_start` event gains a `log_layout` field (string, one of `"v1.5.7-centralized"` or `"v1.5.6-flat"`). Readers use this to detect which layout the run produced. Writers in v1.5.7 always emit `"v1.5.7-centralized"`; legacy-flag writers emit `"v1.5.6-flat"`.

### Deliverable 4 — `metrics/` directory formalization

**Symptom (carry-forward from v1.5.6 close-out, task #113).** The improvement-loop methodology referenced throughout `IMPROVEMENT_LOOP.md` (and increasingly throughout `DEVELOPMENT_PROCESS.md`, `CALIBRATION_PROTOCOL.md`, and `BENCHMARK_PROTOCOL.md`) cites a `metrics/` directory tree that grew organically as v1.5.4 added regression-replay machinery, v1.5.5 added the calibration substrate, and v1.5.6 ran the Pattern 7 displacement-recovery cycle. The current state:

- `metrics/regression_replay/` exists but lacks documentation of its expected shape.
- Calibration ledgers, bootstrap recall data, and cross-version recall tables live in workspace-side directories (`Quality Playbook/Calibration Cycles/`, `Quality Playbook/Cross-Repo Analysis/`) without canonical paths inside QPB.
- v1.7's planned SPC machinery requires a stable input shape — control charts and run rules need consistent column names and consistent file conventions.

**Formalization design.**

Ship `metrics/README.md` documenting:

- Top-level structure: `metrics/regression_replay/`, `metrics/calibration/`, `metrics/bootstrap_recall/`, `metrics/cross_version_trends/`, `metrics/sdlc_defects/`. Each sub-directory has a `README.md` of its own describing the convention. (`cross_version_trends/` matches v1.7's `bin/cross_version_trends.py` output naming; `sdlc_defects/` is a placeholder for v1.7's `bin/migrate_defect_baseline.py` output — v1.5.7 ships the directory + README only, v1.7 populates it.)
- File format conventions per sub-directory (CSV vs JSONL, column/field names, UTC-timestamped ordering, immutable append-only vs mutable).
- The relationship to `quality/run_state.jsonl` (`metrics/` is the cross-cell aggregate; `run_state.jsonl` is the per-cell event log) so v1.7 SPC machinery has unambiguous input.
- The relationship to workspace-side calibration cycle artifacts (`Quality Playbook/Calibration Cycles/`) — workspace artifacts are working-state and not formal; once a cycle terminates, its summary lands in `metrics/calibration/` per the documented convention.

Ship `bin/metrics_reconstruction.py`:

- Walks all cells under `repos/` (and optionally a configured roster of historical cell roots).
- Reads each cell's `quality/run_metadata.json` (post-Deliverable 3: `quality/logs/<run-id>/run_metadata.json`) and `quality/BUGS.md` heading-parses.
- Emits per-quarter aggregates into `metrics/<sub-directory>/` using the conventions documented in the sub-directory READMEs.
- Q1 (v1.4.x → v1.5.4) and Q2 (v1.5.4 → v1.5.6) reconstruction is the v1.5.7 ship gate; v1.5.7's tag includes the reconstructed data set.
- Adopters can re-run `bin/metrics_reconstruction.py` on their own historical cells to produce equivalent aggregates.

**Backward compatibility.** Existing scripts that read from informal `metrics/` paths (e.g., `bin/regression_replay/` consumers) are not broken — the formalization adds the `README.md` and one reconstruction tool. Sub-directory contents are unchanged unless the reconstruction script regenerates them, in which case backups are written to `metrics/<sub-directory>/.backup-<ts>/` so the original informal data is preserved.

**No schema changes to `run_state.jsonl`.** Reconstruction reads the existing schema; it does not modify the writers.

**Council review focus.** Whether the formalized layout is consistent with v1.7's planned SPC machinery (read `docs/design/QPB_v1.7.0_Design.md` and `QPB_v1.7.0_Implementation_Plan.md` end-to-end before this deliverable's Council review). If the v1.7 design implies a layout that conflicts with the v1.5.7 formalization, fix the v1.5.7 design before shipping rather than ship a layout v1.7 will need to migrate away from.

### Deliverable 5 — Trim `SKILL.md` by moving phase-specific content to `references/`

**Symptom.** `SKILL.md` is currently 2,738 lines / ~73K BPE tokens. The awesome-copilot Skill Validator flagged this on PR #1402 (2026-05-10) with the warning: *"Skill is 66,332 BPE tokens — comprehensive skills hurt performance by 2.9pp on average. Consider splitting into 2-3 focused skills."* The "split into multiple skills" recommendation is wrong for QPB — splitting along phase boundaries would force adopters to install 2-3 skills, change the install_skill.py UX, change the awesome-copilot bundle structure, and complicate inter-phase handoff. The architectural choice was deliberately one skill with phases that run in isolated sub-agent contexts.

But the validator's underlying observation is correct in a way the recommendation doesn't capture: **every phase invocation loads the full `SKILL.md` whether or not the loaded content is relevant to that phase**. The phase architecture bounds *cumulative* token cost across a run by isolating each phase in its own context window; it does NOT reduce per-invocation token load. A Phase 4 sub-agent doing Council audit work attends to Phase 1 prose, iteration-strategy descriptions, and Phase 5 reconciliation rules — all of them in its context whether or not it needs them. The validator's "comprehensive-skill performance hit" is the per-invocation cost the phase architecture doesn't address directly.

**The solution that aligns with the architecture, not against it.** Move phase-specific reference-grade content out of `SKILL.md` and into `references/*.md` files that the relevant phase loads on demand. `SKILL.md` becomes a thin orchestration spine: phase ordering, gate criteria, run lifecycle, the glue that makes phases compose. Phase-specific content lives where it logically belongs — in the reference file the phase loads when it runs. Same one skill, same install, same adopter UX, same six phases with the same gates and artifacts. The improvement is that each phase's per-invocation context loads only what it needs.

**Pure move only — no consolidation, no rewording, no cleanup** (scoping decision set 2026-05-11 during Phase 2 planning). Where a block of phase-specific content currently lives in `SKILL.md` AND a `references/*.md` file (i.e., it's already duplicated), the duplicate stays. Consolidating it would change text, which is outside this deliverable's scope. The trim is structurally a "cut from `SKILL.md`, paste verbatim into `references/<target>.md`, replace `SKILL.md` location with a pointer" exercise on phase-specific content that's NOT yet in references.

**Concrete move candidates** (initial list — the actual analysis happens in the Implementation Plan):

- Defensive pattern taxonomy prose in `SKILL.md` (where not already in `references/defensive_patterns.md`) → move
- Spec audit Council rules in `SKILL.md` (where not already in `references/spec_audit.md`) → move
- Iteration strategy descriptions in `SKILL.md` (where not already in `references/iteration.md`) → move
- Verification taxonomies in `SKILL.md` (where not already in `references/verification.md`) → move
- Functional test patterns in `SKILL.md` (where not already in `references/functional_tests.md`) → move
- Constitution / `QUALITY.md` format prose in `SKILL.md` (where not already in `references/constitution.md`) → move
- Challenge gate logic in `SKILL.md` (where not already in `references/challenge_gate.md`) → move
- Requirements pipeline detail in `SKILL.md` (where not already in `references/requirements_pipeline.md` / `requirements_refinement.md` / `requirements_review.md`) → move
- Run-state schema details in `SKILL.md` (where not already in `references/run_state_schema.md`) → move

The pattern: identify a block in `SKILL.md` that's phase-specific reference content. If the same block already exists in a `references/*.md` file, leave both alone (the duplication is pre-existing; consolidation is out of scope). If it exists only in `SKILL.md`, move it verbatim to the matching `references/*.md` file (or create a new one if no match exists), and replace the `SKILL.md` location with a pointer.

**Target.** `SKILL.md` under the validator's "comprehensive" threshold. The validator's exact threshold isn't published, but halving the current size (target ~30K BPE tokens) puts it well below the line. With pure-move-only scoping, the achievable reduction is bounded by how much phase-specific content isn't already in references; consolidating duplicates would achieve more but is deferred.

**Verification: mechanical equivalence, not regression-replay.** Because the trim is pure move with text preserved, behavioral equivalence is verifiable mechanically without running benchmarks. For each phase, compute the union of (`SKILL.md` content + the `references/*.md` files that phase's prompt template loads). Snapshot the union before the trim. Recompute after. Assert byte-equivalence (modulo whitespace cleanup at block boundaries). If the unions match, the LLM sees the same total prose at each phase — the only difference is which files it came from.

This replaces the originally-spec'd regression-replay (which was specified when consolidation was contemplated). With consolidation dropped, the mechanical equivalence check is a stronger guarantee (provably equivalent) at a fraction of the cost (5 minutes vs. 4-8 hours of benchmark time).

Phase 8 integration testing additionally runs the existing v1.5.5 + v1.5.6 benchmark recovery suite as a confidence-building exercise for v1.5.7 as a whole — that catches anything the mechanical equivalence check missed plus regressions from cross-phase interactions. But it's not Phase 7's gate.

**Phase prompt updates.** Each `phase_prompts/*.md` is examined for whether it loads the references it now needs. If a phase implicitly depended on content that's moving out of `SKILL.md`, the phase prompt is updated to load the new reference explicitly. The runner's prompt-construction logic in `bin/run_playbook.py` may also need updates if it references content paths inline.

**Schema impact.** None. Skill name (`quality-playbook`), bundle structure, install paths, adopter invocation, artifact shapes (`BUGS.md`, `EXPLORATION.md`, role map, `run_state.jsonl`, etc.) all unchanged.

**Council review focus.** Three questions: (a) move correctness — is each "moved to references" block genuinely reference-grade, not silently load-bearing for the orchestration spine? (b) text preservation — does the moved prose match the pre-trim version byte-for-byte (modulo whitespace cleanup at block boundaries)? (c) target met — is `SKILL.md` materially smaller and below the validator's threshold? Plus the mechanical equivalence check report.

**Why this is in v1.5.7 and not its own track.** The validator's recommendation pushed initial framing toward "skill restructuring" as a major architectural effort. After examining what's actually in `SKILL.md` (much of it duplicates content already in `references/*.md`) and reasoning through the architecture (the phases-isolate-context principle is strengthened, not weakened, by a leaner `SKILL.md`), the work is sized as cleanup-grade prose movement, not architectural surgery. v1.5.7's cleanup theme fits.

### Deliverable 6 — Council roster modernization, availability resilience, and override layer

**Symptom.** On 2026-05-10 (during awesome-copilot PR #1402 review), `gh copilot` was observed to have silently dropped `gemini-2.5-pro` from its `--model` whitelist. Any adopter using v1.5.6's Phase 4 Council with the copilot runner now hits an immediate failure when the runner tries to invoke `gemini-2.5-pro` — the audit prompt errors before producing any Council output, and Phase 4 hard-fails. The adopter has no recovery path that doesn't require updating QPB itself.

This is a special case of a more general property: **skills outlive model rosters**. Whatever Council members the skill ships with on its release date, the runners those models are reachable through will drop, rename, or deprecate them faster than QPB releases. Without a resilience-and-override layer, every Council roster decay turns into a hot-fix release.

**Five-part design.**

#### Part A — Roster update

`bin/council_config.py` `DEFAULT_COUNCIL_MEMBERS` tuple changes from:

```python
DEFAULT_COUNCIL_MEMBERS: tuple[str, ...] = (
    "claude-opus-4.7",
    "gpt-5.4",
    "gemini-2.5-pro",
)
```

to:

```python
DEFAULT_COUNCIL_MEMBERS: tuple[str, ...] = (
    "claude-opus-4.7",
    "gpt-5.5",
    "claude-sonnet-4.6",
)
```

Per the existing `council_config.py` docstring rule: identifiers are not renamed in place; the tuple's contents are swapped to NEW identifiers. Historical archives still reference the OLD identifiers verbatim (those strings still exist as canonical for old runs). The new roster is what new runs use.

The new roster is 2 Anthropic + 1 OpenAI, losing the Anthropic/OpenAI/Google triangle. This is forced by environmental constraint — there isn't currently a reliable way to invoke Gemini models through any of QPB's four orchestrator runners (`gh copilot` dropped gemini-2.5-pro; the other runners are family-specific). The cross-vendor diversity loss is acknowledged but unavoidable for this release.

Banner-string updates: search `bin/run_playbook.py` for hardcoded `gpt-5.4` and `gemini-2.5-pro` references in argparse help text, the cluster-050 Phase 4 banner, and any error messages. Update each occurrence to reflect the new roster. The cluster-050 Phase 4 banner already reads from `council_config.council_members()` dynamically (per `bin/run_playbook.py:2552-2561`); confirm and don't break the dynamic read.

#### Part B — Fast-fail availability detection + graceful degradation

When Phase 4 launches the Council, all three reviewers' audit prompts dispatch in parallel via the chosen orchestrator runner. Per-reviewer error handling:

- **Reviewer succeeds** → audit output captured normally
- **Reviewer's runner errors with "model not supported" / "unknown model" / equivalent** → mark this Council seat as unavailable, capture the diagnostic
- **Reviewer's runner errors with a different failure** (network, auth, etc.) → distinguish from "model unavailable" and log separately; for v1.5.7's purposes, treat as unavailable for Council purposes but flag the actual cause in the diagnostic

Council vote tabulation:

- **0 unavailable, 3 succeed** → normal 3-of-3 vote
- **1 unavailable, 2 succeed** → degrade to 2-of-2 vote. Log a `council_degraded` event in `quality/logs/<run-id>/run_state.jsonl` (after Deliverable 3 lands; until then `quality/run_state.jsonl`) capturing: the unavailable model, the orchestrator runner, the runner's diagnostic. Surface the degradation in the BUGS.md final-summary section so adopters know the audit was 2-of-2.
- **2 or 3 unavailable** → hard-fail Phase 4. Emit a clear diagnostic naming all unavailable models, the orchestrator runner, the runner's per-model error, and a pointer to `references/runners_and_models.md` plus the `~/.qpb/config.yaml` override path. The Phase 4 abort path uses Deliverable 1's preservation logic so the partial Phase 1-3 artifacts survive for inspection.

Why fast-fail (catch error at first audit invocation) rather than pre-flight probe: the runner CLIs typically error in seconds when they don't support a model. Pre-flight probing would add latency for every Council launch. Fast-fail discovers the same information in the natural failure path with zero upfront cost.

#### Part C — `~/.qpb/config.yaml` persistence layer

New config file location: `~/.qpb/config.yaml` (XDG-compliant; falls back to `$XDG_CONFIG_HOME/qpb/config.yaml` if set). Schema:

```yaml
runner: copilot                 # one of: claude, copilot, codex, cursor
council_members:
  - claude-opus-4.7
  - gpt-5.5
  - claude-sonnet-4.6
```

Both fields are optional; missing fields use built-in defaults. The CLI flags `--claude / --copilot / --codex / --cursor` and (new for v1.5.7) `--council-roster` override the config.

Resolution order for both runner and roster: CLI flag → `~/.qpb/config.yaml` → built-in default. The skill writes the config file when an adopter explicitly invokes a `qpb config set-runner <name>` or `qpb config set-roster <m1,m2,m3>` operation (sub-commands that v1.5.7 adds for this purpose), or manually edits the file. The skill never auto-writes the config without explicit user action — adopters who run with CLI flags don't accidentally get their preferences pinned.

When Council degradation occurs (Part B), the failure diagnostic explicitly tells the adopter what to write into `~/.qpb/config.yaml` to fix the problem permanently. Example:

```
COUNCIL DEGRADED: gpt-5.5 unavailable via copilot runner.
  Council ran with 2-of-2 (claude-opus-4.7, claude-sonnet-4.6 succeeded).

To choose a replacement Council member that's currently available
in your environment, edit ~/.qpb/config.yaml:

    council_members:
      - claude-opus-4.7
      - <your replacement here, e.g., gpt-5.4 if your copilot still
         supports it, or any other model your orchestrator runner reaches>
      - claude-sonnet-4.6

Or pass --council-roster <m1,m2,m3> on the next invocation. See
references/runners_and_models.md for context on each runner and how to
choose Council members.
```

#### Part D — Structured failure-recovery template (LLM-filled)

The Council failure diagnostic above is a static template shipped in QPB source. The volatile information — which models are currently reachable through which runners — lives in the orchestrating LLM's runtime knowledge, not in QPB source.

When Phase 4 hard-fails (Part B's 2-or-3-unavailable case), the runner emits the static template and explicitly invites the orchestrating LLM to expand it with current information:

```
COUNCIL FAILED: 2 of 3 reviewers unavailable.
  - claude-opus-4.7 via copilot: "model not supported"
  - gpt-5.5 via copilot: "model not supported"
  - claude-sonnet-4.6 via copilot: succeeded

Recovery options (LLM: please expand with current model knowledge):

  1. **Override the roster.** Pick replacement models that the copilot
     runner currently supports. To list candidates, run:
         gh copilot -p "What models does --model accept?"
     Or check `references/runners_and_models.md` for the runner's
     historical capabilities.

  2. **Switch orchestrator runner.** If copilot has dropped support
     for these models, another runner may still reach them:
         claude (Anthropic models): claude-cli
         copilot (multi-vendor): gh copilot
         codex (OpenAI models): codex-cli
         cursor (multi-vendor): cursor-cli
     [LLM: if you know which runner currently supports the desired
     Council models, name it here.]

  3. **Update QPB.** If your installed QPB skill version is significantly
     older than the current release, the shipped roster may be stale.
     Check `https://github.com/andrewstellman/quality-playbook/releases`
     for the current version.
```

The template's bracketed `[LLM: ...]` markers signal the orchestrating LLM to fill in current information at runtime. This sidesteps the maintenance burden of QPB shipping an accurate model-availability matrix that would decay between releases.

#### Part E — `references/runners_and_models.md` reference document

New reference file (~150-300 lines) covering:

- **What each of the four runners is.** One paragraph per runner (claude-cli, gh copilot, codex-cli, cursor-cli): vendor, scope (single-family vs multi-family), authentication model, install command. Explicitly NOT a model-availability matrix — those decay; this is the stable "what is this CLI" backgrounder.
- **Why Council-of-Three diversity matters.** Short explanation of why the audit benefits from multiple model families catching different defect classes; why 2-of-2 degradation is acceptable but 1-of-1 is not (overreach risk).
- **How to override the Council roster.** Cross-reference to Part C's persistence layer and the `--council-roster` CLI flag.
- **Pointer to v1.5.6 cluster 050 banner.** The Phase 4 startup banner already shows the active roster — this doc tells adopters where to look at runtime.

Stable content: install commands, conceptual descriptions, override mechanics. Volatile content (which models work in which runners on which date) deliberately omitted — runtime LLM-fill (Part D) handles that.

**Schema impact (additive only).**

- New `council_degraded` event type in `run_state.jsonl`. Schema: `{event: "council_degraded", timestamp: ..., unavailable: [<model>, ...], runner: <name>, diagnostic: <string>}`. Existing readers tolerant of unknown event types per the run-state schema's forward-compat rule.
- New `council_members` field in `run_metadata.json` capturing the actual roster used for the run (so historical analysis can distinguish runs that used the default vs. an overridden roster).
- New BUGS.md section: "Council audit composition" — one-line summary of the roster used, degradation status, and any unavailable models.

**Risks.**

- **The override layer surfaces a new failure mode**: adopter writes a typo into `~/.qpb/config.yaml` and a roster member becomes silently unreachable. Mitigation: the persistence layer validates roster strings against a list of well-known model identifiers on read; unknown identifiers emit a startup warning ("`council_members[1]` is `gpt-5.4-typo` — unrecognized model identifier; will probe at Council launch") so adopters notice typos before Phase 4.
- **Fast-fail timing assumption**: we assume runners error quickly when a model is unsupported. If a runner actually times out for 30 seconds before erroring, Council launch latency suffers. Mitigation: per-reviewer timeout (default 60 seconds) with explicit timeout-as-unavailable handling.
- **Template freshness**: the LLM-filled template (Part D) is only as accurate as the orchestrating LLM's training data. For models very recently released, the LLM may not know about them. Mitigation: the template invites the LLM to "fill in current information" rather than asserting the LLM knows everything; adopters can also paste the template into a fresh chat for current-knowledge consultation.

**Council review focus.** Three lenses: (a) override-layer correctness — config file is read from the right path, CLI flags override config, missing fields use defaults, validation catches typos; (b) degradation logic correctness — 0/1/2/3 unavailable cases all behave per spec; (c) failure-template accuracy — the static portion of Part D's template doesn't claim runner-model facts that decay (those go in `[LLM: ...]` brackets).

---

## Risks and migration

### Risks

- **Log-centralization migration is the largest change.** Many call sites in `bin/run_playbook.py` and the phase prompt templates reference current paths. A regression where the runner writes to the wrong location would break the gate validator, downstream tooling, or both. Mitigation: comprehensive regression tests (assert every log file is at the new location after a complete Phase 1-3 cycle); the `--logs-flat` flag exists specifically as a fallback if migration issues surface in operator testing.
- **Phase 2 abort preservation may surprise adopters whose disk is tight.** Each preserved set is typically small (10s of KB to a few MB), but a cell that aborts repeatedly could accumulate many sibling directories. Mitigation: documentation warns; operators can `rm -rf quality.gate-failed-*` whenever they want.
- **Disposal-mechanism location uncertainty.** The cross-model chat that surfaced the abort symptom couldn't pinpoint where `quality/` actually gets disposed. The implementing worker's first task is to locate the disposal call (it may be in `bin/run_playbook.py`, `lib/cleanup_repo.py`, `setup_repos.sh --replace`, or even an indirect side effect of an agent tool call that doesn't persist). Preservation must trigger before disposal, wherever disposal lives. Mitigation: the worker brief includes "trace disposal first" as the explicit first work item of Phase 3.
- **`metrics/` formalization may produce a layout v1.7 needs to change.** Mitigation: read v1.7 design end-to-end before this deliverable's Council review; if v1.7 implies an incompatible layout, fix v1.5.7 design first.
- **Cookbook reference paragraph adds Phase 2 prompt overhead.** Sub-300 tokens per the Implementation Plan's regression test; no real risk.
- **`SKILL.md` trim risk reduced by pure-move scoping.** With consolidation explicitly out of scope (text preserved verbatim), behavioral equivalence is verifiable mechanically: the union of (`SKILL.md` + loaded references) before vs. after must be byte-equivalent. The risk of a wrongly-moved block (a phase doesn't load the reference where the content went) is caught by the mechanical equivalence check, not just by runtime regression. Phase 8 integration testing additionally runs benchmark recovery as a final confidence check. Recovery: single git revert restores prior `SKILL.md` state. Implementation Plan sequences this deliverable as the last source-edit phase before ship by historical convention; with the risk now bounded by the equivalence check, the ordering rationale is less load-bearing than originally framed.
- **Council-resilience override layer adds a new failure mode**: typos in `~/.qpb/config.yaml`. Mitigation: roster strings are validated on read against a list of well-known identifiers; unknown identifiers emit a startup warning so adopters catch typos before Phase 4. Hard-fail Council errors carry the override-path instructions inline so adopters know how to fix the problem.
- **Council fast-fail relies on runners erroring quickly on unsupported models.** If a runner's "unsupported model" path is a 30-second timeout instead of a 2-second error, Council launch latency suffers. Mitigation: per-reviewer timeout cap (default 60 seconds) with explicit timeout-as-unavailable handling.
- **LLM-filled failure-recovery template assumes orchestrating LLM knowledge is current.** For very-recently-released models the LLM may not know enough to suggest replacements. Mitigation: the template invites the LLM to fill in what it knows rather than asserting it knows everything; adopters who get an empty template can paste it into a fresh chat with web-search enabled.

### Migration

For adopters running v1.5.6 against their own targets:

1. **Default behavior changes** in three visible ways:
   - When the Phase 2 gate aborts, `quality/` is preserved at `quality.gate-failed-<ts>/` instead of being left empty (no operator action needed; the new directory is documented).
   - Logs move to `quality/logs/<run-id>/` (operators whose tooling reads from old paths must either update their tooling or pass `--logs-flat`).
   - Phase 4 Council roster changes from `(claude-opus-4.7, gpt-5.4, gemini-2.5-pro)` to `(claude-opus-4.7, gpt-5.5, claude-sonnet-4.6)`. Adopters whose previous runs depended on the old roster (research-grade comparison studies) should pin v1.5.6 for those studies; new runs use the new roster. Adopters whose orchestrator runner cannot reach a member of the new roster get a clear failure with override instructions instead of a silent crash.
2. **Three new flags** are available:
   - `--logs-flat` for legacy log layout (deprecated; remove in v1.6.0).
   - `--council-roster <m1,m2,m3>` for one-run override of the Council member list.
   - `qpb config set-runner <name>` and `qpb config set-roster <m1,m2,m3>` sub-commands for persisting the override across runs.
3. **Two new reference files** are installed:
   - `references/role_map_queries.md` — role-map jq cookbook.
   - `references/runners_and_models.md` — runner backgrounder + Council-diversity rationale + override mechanics. Adopters using the manual install path should copy both alongside the existing references.
4. **`metrics/` directory** has new `README.md` files. Adopters who don't run the reconstruction script see no behavior change; those who do gain Q1/Q2 historical aggregates.
5. **`~/.qpb/config.yaml` is created on first explicit `qpb config ...` invocation.** Adopters who never write to it get exactly the built-in defaults — no migration needed.

### Backward compatibility commitment

- The `--logs-flat` flag is supported in v1.5.7 (the planned last v1.5.x release). v1.6.0 removes it.
- The `run_state.jsonl` `log_layout` field is additive; readers are tolerant of missing fields per the existing schema rules.
- All artifact shapes (BUGS.md, EXPLORATION.md, REQUIREMENTS.md, role map, etc.) are unchanged.

---

## Test strategy

Each deliverable carries its own regression-test set, integrated into `bin/tests/` and run via `python3 -m unittest discover bin/tests`. Per the Implementation Plan, each phase's Council review checks that the test set fails on the unpatched code (regression-tests-bite check) and passes on the patched code.

Cross-deliverable integration tests:

1. **Phase 2 abort + cluster-049 auto-recovery composition.** A run where the agent walks vendored content but only the entry-count violation is present: cluster-049 auto-recovery succeeds, run proceeds, no preservation triggered.
2. **Phase 2 abort + auto-recovery composition, recovery fails.** A run where the agent walks vendored content AND has `DISALLOWED_PATH_PREFIXES` violations: cluster-049 auto-recovery is not attempted (DISALLOWED is fatal), preservation runs, `quality.gate-failed-<ts>/` exists with the marker.
3. **Cluster-050 `--benchmark-mode` + log centralization.** A run with `--benchmark-mode`: phases 1-3 run, all log artifacts under `quality/logs/<run-id>/`, `RUN_MODE.md` at `quality/logs/<run-id>/RUN_MODE.md` (no longer at `quality/RUN_MODE.md`).
4. **`--logs-flat` legacy mode.** A run with `--logs-flat`: logs emitted to v1.5.6 paths exactly as before; `quality/logs/` is NOT created; existing v1.5.6-targeting tooling reads logs successfully. Cluster-050 `RUN_MODE.md` lands at the legacy `quality/RUN_MODE.md` location.
5. **`metrics/` reconstruction.** Run `bin/metrics_reconstruction.py` against a historical cell roster; assert per-quarter aggregates land in `metrics/<sub-directory>/` with the documented column/field shape.

6. **`SKILL.md` pure-move — mechanical equivalence check.** Capture per-phase loaded-content union before the move. Apply pure-move refactor (text preserved). Recompute per-phase loaded-content union after. Assert byte-equivalence modulo whitespace cleanup at block boundaries. Zero content drift across all six phases is required. (No benchmark run needed for verification; Phase 8 integration test runs benchmarks as a separate confidence-building exercise for the v1.5.7 release as a whole.)

7. **`SKILL.md` size invariant.** Static test: parse `SKILL.md` with a BPE tokenizer (tiktoken or equivalent), assert total tokens are below the v1.5.7 target (~30K BPE tokens; the validator's exact comprehensive-skill threshold isn't published but ~30K is comfortably below where the 2.9pp performance hit was observed).

8. **No-orphaned-pointer test.** For each "See `references/X.md` for ..." pointer added to `SKILL.md` during the trim, assert the target file exists and contains the expected anchor heading.

9. **Council roster string test.** Assert `bin/council_config.py` `DEFAULT_COUNCIL_MEMBERS` matches the v1.5.7 roster `(claude-opus-4.7, gpt-5.5, claude-sonnet-4.6)`. Assert no remaining hardcoded `gpt-5.4` or `gemini-2.5-pro` strings in `bin/run_playbook.py` argparse help text or banner construction.

10. **Council fast-fail availability paths.** Mocked-runner tests covering: 0-of-3 unavailable (normal), 1-of-3 unavailable (degrade to 2-of-2 with `council_degraded` event in `run_state.jsonl` + BUGS.md summary mention), 2-of-3 unavailable (hard-fail with diagnostic naming both unavailable models + `~/.qpb/config.yaml` override path), 3-of-3 unavailable (hard-fail). Per-reviewer timeout test (mock a runner that hangs; assert reviewer marked unavailable after timeout cap).

11. **Persistence-layer override resolution.** Tests covering: built-in default used when no config file exists; config file overrides built-in default; CLI flag (`--claude / --copilot / --codex / --cursor` and `--council-roster`) overrides config; typo in `council_members` emits startup warning. Round-trip test for `qpb config set-runner` and `qpb config set-roster` write/read cycle.

12. **Runners-and-models reference doc.** Static test asserting `references/runners_and_models.md` exists and contains an entry for each of `claude`, `copilot`, `codex`, `cursor`. Asserts the doc does NOT contain a model-availability matrix (the deliberately-omitted volatile content); regex check against tabular formats with model names listed under runner columns.

End-to-end smoke test: run a complete `--benchmark-mode` cycle against a small benchmark target (e.g., chi). Verify all six v1.5.7 deliverables are visible: preservation works on a synthetic abort; `references/role_map_queries.md` ships in the install bundle; all logs under `quality/logs/<run-id>/`; `metrics/README.md` and reconstruction script ship; `SKILL.md` is materially smaller and the run completes with no behavior change vs. pre-trim baseline; Council roster reflects the v1.5.7 update; a synthetic Council degradation (mock one reviewer's runner returning "unsupported model") produces the documented 2-of-2 degraded outcome with the expected `run_state.jsonl` event and BUGS.md summary entry.

---

## Council reviews

Per CALIBRATION_PROTOCOL.md Mode 1 nested-panel rules, each deliverable gets a Council-of-Three review before merge. The lenses vary by deliverable:

- **Deliverable 1 (abort preservation):** disposal-mechanism location traced correctly; atomicity (rename happens before marker write); naming convention (UTC timestamp, lexicographic sort); interaction with cluster-049 auto-recovery; disk-space messaging in TOOLKIT.md.
- **Deliverable 2 (cookbook):** doc tone consistency with other reference files; completeness of canonical queries vs. anti-patterns; deliberate non-enumeration of role taxonomy; Phase 2 prompt addition's prompt-token overhead under 300 tokens.
- **Deliverable 3 (log centralization):** migration completeness (every call site updated, including cluster-050's `RUN_MODE.md` writer); `--logs-flat` legacy behavior fidelity; `run_state.jsonl` schema additive-only; gate validator and adopter-tooling fallbacks; orientation-doc edits (TOOLKIT, BENCHMARK_PROTOCOL, DEVELOPMENT_PROCESS) routed through Toolkit Test Protocol gate per workspace CLAUDE.md.
- **Deliverable 4 (`metrics/` formalization):** v1.7 design read end-to-end and consistency check passed; sub-directory READMEs accurate; reconstruction script handles missing-data cells gracefully; Q1/Q2 aggregates are reproducible (same inputs produce same outputs, modulo timestamp).
- **Deliverable 5 (`SKILL.md` pure-move refactor):** move correctness — every "moved to references" block is genuinely reference-grade, not silently load-bearing for the orchestration spine (Council samples the moves and inspects); text preservation — moved prose matches pre-trim version byte-for-byte modulo whitespace cleanup (the mechanical equivalence check is the primary evidence); target met — `SKILL.md` is below the achievable threshold per pure-move scoping. Council also confirms phase prompts in `phase_prompts/*.md` correctly load the references their phases now depend on.
- **Deliverable 6 (Council roster + resilience + override):** override-layer correctness (config path, CLI flag precedence, typo validation); degradation logic correctness (0/1/2/3 unavailable cases all match spec); failure-template accuracy (static portion makes only stable claims; volatile claims are routed through `[LLM: ...]` markers, not asserted as fact); reference-doc stability (no model-availability matrix that would decay).

After all six deliverables pass Council and merge, a final integration Council reviews the v1.5.7 release as a whole — particularly the cross-deliverable interactions (preservation + cluster-049 auto-recovery, log centralization + cluster-050 `--benchmark-mode`, `metrics/` formalization + v1.7 design alignment, `SKILL.md` trim composes cleanly with all other deliverables' phase-prompt updates, Council degradation events flow correctly into `run_state.jsonl` and BUGS.md) — before tagging.

---

## Open questions and conditional candidates

### Open questions for operator review (resolved 2026-05-10 during Phase 1 stabilization)

All three resolved per the Design's pre-stated recommendations.

1. **`<run-id>` naming.** **DECISION: compact UTC ISO-8601** (`20260509T184231Z`, 16 chars). Sortable, reproducible, no local-time variation.

2. **`quality.gate-failed-<ts>/` location.** **DECISION: alongside `quality/`** (sibling, not nested in `quality/logs/`). Reason: simpler `rm -rf quality.gate-failed-*` cleanup when the operator just wants to reset the cell, doesn't hide the preserved data inside a `logs/` tree the operator may not realize contains it. TOOLKIT.md cross-reference included in Phase 3 (Deliverable 1) work items.

3. **Cookbook file location.** **DECISION: top-level `references/role_map_queries.md`** — not nested in another reference. Reason: the cookbook is queried by Phase 2; exploration patterns are queried by Phase 1; different consumers and different call paths warrant different files.

### Conditional candidates from v1.5.6 close-out carry-forward

These were enumerated in `docs/design/QPB_v1.5.6_Implementation_Plan.md`'s "Out-of-band carry-forward to v1.5.7 / v1.6.0" section as items that would land in v1.5.7 IF a specific condition surfaced. **All four deferred 2026-05-10 during Phase 1 stabilization** — none of the triggering conditions surfaced in v1.5.6 validation or post-ship reports. They remain candidates for a later release if evidence accumulates.

- **`--require-docs` opt-out flag** — v1.5.6 ships missing-documentation downgrade behavior (proceed in code-only mode with explicit framing). The carry-forward says: "if missing-documentation downgrade confuses operators in validation, add to v1.5.7." **Operator decision: did v1.5.6's validation surface confusion?** If yes, commit to v1.5.7 as a seventh deliverable; if no, defer to a later release.

- **Windows path handling in `bin/install_skill.py`** — v1.5.6's adopter distribution work didn't run a Windows install end-to-end. The carry-forward says: "if Phase 4 surfaces Windows-specific failures, v1.5.7." **Operator decision: any Windows install reports since v1.5.6 ship?** If yes, commit to v1.5.7; if no, defer.

- **Skill-as-code adopter Persona 19 deep work** — the carry-forward says: "if the adopter walkthrough in Phase 4 surfaces gaps specific to skill-as-code targets, document them as v1.5.7 candidates." **Operator decision: did the Phase 4 walkthrough or any subsequent skill-as-code adopter run surface gaps?** If yes, commit to v1.5.7; if no, defer to v1.6+.

- **Adopter-grade orchestration-patterns doc** — `ai_context/AI_ORCHESTRATION_PATTERNS.md` shipped in v1.5.6 as the QPB-development-grade version. The carry-forward says: "an adopter-facing version that lets adopters use the pattern in their own workflow is v1.5.7." **Operator decision: is the v1.5.6 doc QPB-development-grade only, or already adopter-usable?** If development-grade only, commit an adopter version to v1.5.7; if already adopter-usable, defer.

These four items are NOT committed deliverables in v1.5.7's current scope. Operator-review answers above either expand the scope (and trigger a corresponding update to the Implementation Plan's phase list) or formally defer the items to a later release. Default is defer; commitment requires explicit operator instruction.

---

## Appendix — workspace-side staging context

The original drafting of Deliverable 1 (Phase 2 gate-failure preservation) lives at `Quality Playbook/Reviews/QPB_v1.5.7_Backlog/PreserveQualityOnGateFail.md` in the AI-Driven Development workspace. That brief carries the original symptom report, full reproduction context, patch sketch, and proposed regression test list. Implementing workers may use it as supplementary material; the canonical scope for v1.5.7 is this Design doc + the Implementation Plan, not the workspace brief.
