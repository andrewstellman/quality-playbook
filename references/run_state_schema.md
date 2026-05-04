# Run-State Schema (v1.5.6)

*Authoritative schema for `quality/run_state.jsonl`, `quality/PROGRESS.md`, and `Calibration Cycles/<cycle>/run_state.jsonl`. The playbook AI writes these files directly via the file-tool layer; the orchestrator AI reads them to drive multi-benchmark calibration cycles.*

*Companion to: `docs/design/QPB_v1.5.5_Design.md` ("Design — Run-state event taxonomy" section).*

---

## File locations and ownership

- `<benchmark>/quality/run_state.jsonl` — per-run event log. Append-only. Written by the AI executing the playbook.
- `<benchmark>/quality/PROGRESS.md` — human-readable run status. Atomically rewritten by the AI on each event.
- `Calibration Cycles/<cycle>/run_state.jsonl` — cycle-level event log. Append-only. Written by the orchestrator AI.

All three live in the bind-mounted workspace owned by the user. The AI writes via Edit/Write file tools, never via shell redirection or `tee` (which routes through a different UID layer in some sandbox runtimes).

---

## Schema versioning

Every `run_state.jsonl` opens with an `_index` event recording `schema_version`. Current version: `"1.5.6"`. Schema bumps preserve backward compatibility — older files remain readable by newer parsers. Breaking schema changes bump the major number.

---

## Required fields (every event)

Every event object MUST have:

- `ts` — ISO 8601 UTC timestamp with `Z` suffix (e.g. `"2026-05-15T14:32:01Z"`). Sub-second precision allowed but not required.
- `event` — string, the event-type name. Must match one of the names listed in `_index.event_types`.

Events MAY have additional fields per their type's spec below. Unknown fields are tolerated by readers (forward-compatible).

---

## Per-run events (`<benchmark>/quality/run_state.jsonl`)

### `_index`

ALWAYS the first line. Records schema metadata.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | Always `"_index"` |
| `ts` | string | yes | ISO 8601 UTC |
| `schema_version` | string | yes | `"1.5.6"` |
| `event_types` | array of string | yes | Every event type this file uses |
| `benchmark` | string | yes | E.g. `"chi-1.3.45"`, `"virtio-1.5.1"` |
| `lever_state` | string | yes | E.g. `"pre-pattern7"`, `"post-pattern7"`, `"baseline"` |
| `started_at` | string | yes | ISO 8601 UTC, equals `ts` of this event |

### `run_start`

Marks the beginning of a playbook run.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"run_start"` |
| `ts` | string | yes | |
| `runner` | string | yes | One of `"claude"`, `"codex"`, `"copilot"`, `"cursor"` |
| `playbook_version` | string | yes | E.g. `"1.5.6-pre"`, `"1.5.6"` (matches `bin.benchmark_lib.RELEASE_VERSION`) |
| `target_path` | string | yes | Relative path to benchmark target |

### `phase_start`

Marks the beginning of one of the six playbook phases.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"phase_start"` |
| `ts` | string | yes | |
| `phase` | integer | yes | 1, 2, 3, 4, 5, or 6 |

### `pattern_walked`

Phase 1 only. Records that one of the seven exploration patterns was walked.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"pattern_walked"` |
| `ts` | string | yes | |
| `phase` | integer | yes | Always 1 |
| `pattern` | integer | yes | 1 through 7 |
| `findings_count` | integer | yes | Number of findings produced by this pattern |
| `duration_seconds` | number | optional | Wall-clock for this pattern walk |

### `pass_started` / `pass_ended`

Phase 4 only. Records start/end of one of the four skill-derivation passes.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"pass_started"` or `"pass_ended"` |
| `ts` | string | yes | |
| `phase` | integer | yes | Always 4 |
| `pass` | string | yes | One of `"A"`, `"B"`, `"C"`, `"D"` |
| `output_artifact` | string | optional | Relative path to pass artifact (on `pass_ended`) |

### `finding_logged`

Records that a finding (skill-divergence, code-bug, etc.) was logged in the current phase.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"finding_logged"` |
| `ts` | string | yes | |
| `phase` | integer | yes | 1-6 |
| `finding_id` | string | yes | E.g. `"BUG-007"`, `"REQ-042"` |
| `category` | string | yes | E.g. `"code-bug"`, `"skill-divergence"`, `"missing-citation"`, `"prose-to-code-mismatch"` |

### `artifact_written`

Records that an artifact file was produced/updated.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"artifact_written"` |
| `ts` | string | yes | |
| `relative_path` | string | yes | Path relative to benchmark target (e.g. `"quality/EXPLORATION.md"`) |
| `byte_size` | integer | optional | Size of the file at write time |
| `line_count` | integer | optional | Line count |

### `gate_check`

Records the outcome of a single quality-gate check.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"gate_check"` |
| `ts` | string | yes | |
| `gate_name` | string | yes | Identifier from `quality_gate.py` |
| `verdict` | string | yes | One of `"pass"`, `"fail"`, `"warn"`, `"skip"` |
| `reason` | string | optional | Human-readable explanation |

### `phase_end`

Marks the end of a phase. Cross-validated against the phase's expected artifacts before being written (see "Cross-validation rules" below).

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"phase_end"` |
| `ts` | string | yes | |
| `phase` | integer | yes | 1-6 |
| `key_counts` | object | yes | Phase-specific counts (see below) |
| `artifacts_produced` | array of string | yes | Relative paths of artifacts produced this phase |
| `duration_seconds` | number | optional | Wall-clock for the whole phase |

`key_counts` per phase:

- Phase 1: `{"findings_total": N, "patterns_walked": M}` (M should be 7 for full Phase 1)
- Phase 2: `{"findings_promoted": N, "findings_dropped": M}`
- Phase 3: `{"bugs_identified": N, "bug_writeups": M}`
- Phase 4: `{"req_count": N, "uc_count": M, "passes_complete": K}` (K should be 4)
- Phase 5: `{"gate_checks_total": N, "gate_failures": M}`
- Phase 6: `{"bugs_md_count": N, "gate_verdict": "pass|fail|partial"}`

### `error`

Records an error during the run.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"error"` |
| `ts` | string | yes | |
| `phase` | integer | optional | If error is phase-scoped |
| `message` | string | yes | Human-readable description |
| `recoverable` | boolean | yes | If true, the run will retry the affected phase; if false, the run is aborting |

### `documentation_state`

v1.5.6+. Records the documentation-availability state at Phase 1 entry. Currently the only emitted state is `"code_only"`, indicating that `reference_docs/` and `reference_docs/cite/` carry no recognized plaintext content (`.md` or `.txt`) and Phase 1 is proceeding in code-only mode (see `references/code-only-mode.md`). A `"with_docs"` value is reserved for future explicit emission; today the absence of a `documentation_state` event implies docs were present.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"documentation_state"` |
| `ts` | string | yes | |
| `state` | string | yes | Currently `"code_only"`. Future values may include `"with_docs"`. |
| `reason` | string | yes | Free-form (e.g. `"reference_docs/ empty"`) |

When `documentation_state state="code_only"` is emitted, the playbook also prepends a "Documentation status: code-only mode" section to `quality/EXPLORATION.md` and adds a "Documentation state: code_only" line to `quality/PROGRESS.md` so the downgrade is visible to anyone reading either artifact. New runs adding the `documentation_state` event must include it in the `_index.event_types` list.

### `run_end`

Marks the end of the playbook run.

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"run_end"` |
| `ts` | string | yes | |
| `status` | string | yes | One of `"success"`, `"aborted"`, `"failed"` |
| `total_findings` | integer | optional | Sum across all phases |
| `final_verdict` | string | optional | The Phase 6 gate verdict |

---

## Cycle-level events (`Calibration Cycles/<cycle>/run_state.jsonl`)

### `_index` (cycle-level)

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"_index"` |
| `ts` | string | yes | |
| `schema_version` | string | yes | `"1.5.6"` |
| `event_types` | array of string | yes | |
| `cycle_name` | string | yes | E.g. `"2026-05-15-pattern7-displacement-recovery"` |
| `lever_under_test` | string | yes | E.g. `"lever-1-exploration-breadth-depth"` |
| `benchmarks` | array of string | yes | Cycle's pinned benchmark list |
| `iteration` | integer | yes | Iteration ordinal (1, 2, or 3 — see iterate-cap) |

### `cycle_start`

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"cycle_start"` |
| `ts` | string | yes | |
| `hypothesis` | string | yes | The cycle's testable hypothesis |
| `noise_floor_threshold` | number | yes | Recall delta below this is treated as noise (default 0.05) |

### `benchmark_start`

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"benchmark_start"` |
| `ts` | string | yes | |
| `benchmark` | string | yes | |
| `lever_state` | string | yes | `"pre-lever"` or `"post-lever"` |

### `lever_change_applied`

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"lever_change_applied"` |
| `ts` | string | yes | |
| `lever_id` | string | yes | E.g. `"lever-1-exploration-breadth-depth"` |
| `files_changed` | array of string | yes | Paths relative to QPB repo root |
| `commit_sha` | string | yes | Commit SHA on the implementing branch |
| `description` | string | yes | What the change is (e.g. `"Pattern 7 budget cap 3-5 → 2-3"`) |

### `lever_change_reverted`

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"lever_change_reverted"` |
| `ts` | string | yes | |
| `files_changed` | array of string | yes | |
| `commit_sha` | string | optional | Null/absent if revert is uncommitted |

### `benchmark_end`

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"benchmark_end"` |
| `ts` | string | yes | |
| `benchmark` | string | yes | |
| `lever_state` | string | yes | |
| `recall` | number | yes | 0.0-1.0 |
| `bugs_found` | array of string | yes | Bug IDs found this run |
| `bugs_missed` | array of string | yes | Bug IDs in baseline missed this run |
| `historical_baseline_path` | string | yes | Path to the baseline BUGS.md used for recall computation |

### `cycle_end`

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | `"cycle_end"` |
| `ts` | string | yes | |
| `verdict` | string | yes | One of `"ship"`, `"revert"`, `"iterate"`, `"halt-iterate-cap"` |
| `recall_before` | object | yes | Per-benchmark recall before lever change |
| `recall_after` | object | yes | Per-benchmark recall after lever change |
| `delta` | object | yes | Per-benchmark delta (recall_after - recall_before) |
| `cross_benchmark_check` | object | yes | `{"clean": bool, "regressions": [list of bench/bug pairs that regressed]}` |

---

## Cross-validation rules (per `phase_end`)

The AI verifies these conditions before appending a `phase_end` event. If any check fails, the AI appends an `error` event with `recoverable: true` and re-runs the failing phase.

| Phase | Required conditions |
|---|---|
| 1 | `quality/EXPLORATION.md` exists, file size ≥ 200 bytes, contains at least one finding section (regex `## Finding` or numbered `### N.` or similar) |
| 2 | At least one of `quality/EXPLORATION_MERGED.md` / `quality/triage/triage.md` / equivalent triage artifact exists, non-empty |
| 3 | `quality/RUN_CODE_REVIEW.md` exists; if `bugs_identified > 0`, then `quality/writeups/BUG-*.md` count ≥ `bugs_identified` |
| 4 | `quality/REQUIREMENTS.md` exists, non-empty; `quality/COVERAGE_MATRIX.md` exists. If the four-pass skill-derivation pipeline ran (i.e., `quality/phase3/` exists), then the per-pass artifacts under `quality/phase3/` (`pass_a_drafts.jsonl`, `pass_b_citations.jsonl`, `pass_c_formal.jsonl`, and the Pass D inbox) must all exist and be non-empty. (Spec/Code projects that skip skill-derivation produce no `quality/phase3/` directory; the per-pass requirement is conditional on its presence.) |
| 5 | `quality/results/quality-gate.log` exists, non-empty |
| 6 | `quality/BUGS.md` exists, non-empty, contains at least one BUG entry (regex `^## BUG-`); `quality/INDEX.md` updated with `gate_verdict` field |

The `run_end` event additionally requires: all 6 `phase_end` events present in the log; the final BUGS.md count matches `phase_end phase=6 key_counts.bugs_md_count`.

---

## Resume semantics

When an AI session starts on a run directory:

1. If `quality/run_state.jsonl` does not exist: fresh run. Write `_index` + `run_start` + `phase_start phase=1`.
2. If it exists: read all events. Find the last `phase_start` not followed by a matching `phase_end`. Call it the "in-progress phase".
3. Verify the in-progress phase's expected artifacts (per cross-validation rules above):
   - If artifacts complete: append the missing `phase_end` event and proceed to the next phase. Note: this is the "session crashed mid-phase but the work is done" recovery path.
   - If artifacts incomplete: re-run that phase from scratch. The prior session left a partial state that can't be safely resumed.
4. If all 6 `phase_end` events are present but no `run_end`: append `run_end status=success` and finalize.

The policy is "trust artifacts more than events." If events claim phase 4 done but `REQUIREMENTS.md` doesn't exist, the AI re-runs phase 4. If events stop mid-phase but artifacts are complete, the AI catches up the events.

---

## PROGRESS.md format

Atomically rewritten on every event. Markdown.

```markdown
# QPB Run Progress

**Started:** 2026-05-15T14:32:01Z  **Benchmark:** chi-1.5.1  **Lever:** post-pattern7
**Runner:** claude  **Playbook version:** 1.5.6

## Phases

- [x] Phase 1 — Exploration (10:10, 12 findings, patterns 1-7 walked)
- [x] Phase 2 — Triage (0:42, 8 findings promoted)
- [x] Phase 3 — Investigation (15:31, 6 bugs identified)
- [x] Phase 4 — Skill-derivation (4 passes, 89 REQs produced)
- [ ] Phase 5 — Verification *(in progress, started 14:58:31Z)*
- [ ] Phase 6 — Release readiness

## Recent events (last 10)

- 2026-05-15T14:58:31Z — phase_start phase=5
- 2026-05-15T14:58:30Z — phase_end phase=4 passes=[A,B,C,D] req_count=89
- 2026-05-15T14:42:11Z — phase_end phase=1 findings=12

## Artifacts produced

- quality/EXPLORATION.md (12,034 bytes)
- quality/REQUIREMENTS.md (28,891 bytes)
- quality/COVERAGE_MATRIX.md (3,022 bytes)
```

Sections (header, phase checklist, recent events, artifacts produced) are required. Phase checklist uses `[x]` for complete phases (with summary stats), `[ ]` for incomplete, with in-progress phase noted explicitly with start time. Recent events shows last 10 event lines from `run_state.jsonl` in human-readable form. Artifacts produced shows files written this run with byte sizes.

---

## Format invariants (enforced by `bin/run_state_lib.py` validators)

1. `_index` is line 1.
2. Every line is valid JSON (one object per line).
3. Every event has `ts` and `event` fields.
4. Every `event` value appears in `_index.event_types`.
5. Append-only: events are added, never edited. Editing a prior event is a schema violation.
6. `phase_start` and `phase_end` events for a given phase appear at most once per run (no out-of-order or duplicate phase markers).
7. `run_start` is the second line (after `_index`); `run_end` is the last line if the run completed.

Validators are read-only checks. They surface violations as findings; they don't auto-correct.
