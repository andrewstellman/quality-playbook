# Iteration 4 Exploration — `parity` strategy

Date: 2026-04-28
Project: quality-playbook (repo-root self-audit)
Strategy: cross-path comparison and diffing — line up parallel implementations of the same contract and surface drift

This iteration enumerates groups of code that implement the same logical contract via parallel paths, then diffs the paths against the documented contract source. Findings are written as concrete pairwise discrepancies with file:line citations on both sides of each diff. The previous-run scan covered `## Candidate Bugs for Phase 2` and `## Demoted Candidates` from `quality/EXPLORATION_MERGED.md`; nothing in this iteration re-litigates DC-001 through DC-004 (that is the adversarial strategy's job).

---

## Parallel groups enumerated

1. **Phase prompt family.** `phase1_prompt`, `phase2_prompt`, `phase3_prompt`, `phase4_prompt`, `phase5_prompt`, `phase6_prompt`, `iteration_prompt`, `single_pass_prompt` in `bin/run_playbook.py`. All eight prompts are children of the same six-phase contract documented in `SKILL.md:1026-1042`, the closed-set verdict and recommendation enums in `SKILL.md:160-178`, and the install-location fallback in `SKILL.md:49-58`.
2. **Citation verification layers.** `bin/citation_verifier.py` (Layer 1 byte-equality) and `bin/council_semantic_check.py` (Layer 2 semantic verdict). Both take `quality/formal_docs_manifest.json` as upstream input and produce structured verification outputs.
3. **Agent orchestrator briefs.** `agents/quality-playbook.agent.md` and `agents/quality-playbook-claude.agent.md`. (Codex agent file is not present in this checkout.) Both teach the orchestrator how to install / locate the skill, run the six phases, and run iterations.
4. **Phase 2 gate enforcers.** `SKILL.md:1026-1042` (authoritative spec, 13 criteria), `quality/mechanical/phase2_gate_required_headings.txt` (mechanical contract), `.github/skills/quality_gate.py::_check_exploration_sections()` (terminal gate, post-run), `bin/run_playbook.py::check_phase_gate(..., "2")` (runtime gate, pre-Phase-2).
5. **Sidecar / manifest JSON writers.** `bin/council_semantic_check.py::write_semantic_check()`, `bin/reference_docs_ingest.py::ingest()`, plus the (still informal) writers for `tdd-results.json` and `integration-results.json`. SKILL.md prescribes one wrapper for manifests (§1.6, lines 1091-1103) and a different wrapper for sidecars (lines 138-178).
6. **Setup vs cleanup paths in `bin/run_playbook.py`.** Run-start setup writes a `run_timestamp` and a stub INDEX; run-end cleanup re-renders INDEX and finalises archive payload. Both should agree on the timestamp identifier format.

---

## Pairwise comparisons traced (≥8 diffs)

### C-1 (Phase prompts) — install-location fallback list

| Side | File:line | What it teaches |
| --- | --- | --- |
| `phase1_prompt` | `bin/run_playbook.py:626` | Uses the central `{SKILL_FALLBACK_GUIDE}` interpolation (canonical four-path list) |
| `iteration_prompt` | `bin/run_playbook.py:1129` | Uses `{SKILL_FALLBACK_GUIDE}` (canonical four-path list) |
| `single_pass_prompt` | `bin/run_playbook.py:1124` | Uses `{SKILL_FALLBACK_GUIDE}` (canonical four-path list) |
| `phase2_prompt` | `bin/run_playbook.py:732, 763` | Hardcodes `.github/skills/SKILL.md` and `.github/skills/references/...` |
| `phase3_prompt` | `bin/run_playbook.py:918` | Hardcodes `.github/skills/SKILL.md` |
| `phase4_prompt` | `bin/run_playbook.py:974-980` | Hardcodes `.github/skills/SKILL.md` and `.github/skills/references/...` |
| `phase5_prompt` | `bin/run_playbook.py:1089-1090` | Hardcodes `.github/skills/SKILL.md` and `.github/skills/references/...` |
| `phase6_prompt` | `bin/run_playbook.py:1089-1093` | Hardcodes `.github/skills/SKILL.md` |

Contract source: `SKILL.md:49-58`. Already filed as BUG-008. Listed here only to ground the parity comparison; this iteration adds no net-new finding to that bug.

### C-2 (Phase prompts) — closed-set enum enumeration

| Side | File:line | What it teaches |
| --- | --- | --- |
| `phase4_prompt` (semantic-check verdicts) | `bin/run_playbook.py:948` | "Every entry must have req_id, verdict (`supports\|overreaches\|unclear`), and reasoning." Closed-set inline. |
| `phase5_prompt` (TDD verdicts) | `bin/run_playbook.py:1060` | "canonical fields: id, requirement, red_phase, green_phase, verdict, fix_patch_present, writeup_path" — names `verdict` but **does not enumerate the closed-set values**. |
| `phase5_prompt` (integration recommendations) | `bin/run_playbook.py:1060` | Mentions `integration-results.json` but does not list the `recommendation` closed-set. |

Contract source: `SKILL.md:160-161` (`verdict` ∈ `{"TDD verified", "red failed", "green failed", "confirmed open", "deferred"}`) and `SKILL.md:178` (`recommendation` ∈ `{"SHIP", "FIX BEFORE MERGE", "BLOCK"}`). **Net-new diff.**

### C-3 (Phase prompts) — PROGRESS.md authorship rule

| Side | File:line | What it teaches |
| --- | --- | --- |
| `iteration_prompt` | `bin/run_playbook.py:1130-1133` | Teaches BOTH: keep checkbox format `- [x] Phase N - <name>`, AND "the orchestrator appends `## Iteration: <strategy> started/complete` sections itself; iteration work should not touch the existing phase tracker lines." |
| `phase2_prompt`–`phase6_prompt` | `bin/run_playbook.py:749, 905, 961, 1080, 1107` | Each says "use the checkbox format `- [x] Phase N - <name>` — do NOT switch to a table." None mentions the orchestrator-appends rule. |
| `phase1_prompt` | `bin/run_playbook.py:700, 720` | Teaches checkbox format with rationale (Phase 5 entry-gate substring matching). Does not teach the orchestrator-appends rule. |

Contract source: the orchestrator/iteration boundary contract is taught in `references/iteration.md` and reinforced in `iteration_prompt`. Phase prompts do not teach it. **Net-new diff** — see F-1 below.

### C-4 (Citation verification) — manifest schema use

| Side | File:line | What it consumes |
| --- | --- | --- |
| Layer 1 — `bin/citation_verifier.py:244-266` | reads `formal_docs_manifest.json` records via caller-passed `formal_doc` dict; reads `source_path` and `excerpt`; opens `Path(root) / source_path` |
| Layer 2 — `bin/council_semantic_check.py:118-204` | reads `requirements_manifest.json` records (Tier 1/2 only); pulls `citation.citation_excerpt`, `citation.document`, `citation.section`, `citation.line` directly from each REQ record; never opens the source file |

The two layers consume disjoint manifests by design (`formal_docs_manifest.json` vs `requirements_manifest.json`). Path-traversal vulnerability is asymmetric: only Layer 1 dereferences `source_path`; Layer 2 reads excerpts already produced by Layer 1. This corroborates BUG-011 (filed in iteration 3 against `bin/citation_verifier.py:244-266`); no net-new diff here.

### C-5 (Citation verification) — empty-collection ambiguity

| Side | File:line | Empty-output meaning |
| --- | --- | --- |
| Layer 1 — `bin/citation_verifier.py` | Pure function; no JSON output. Empty `formal_docs_manifest.json[records]` is handled upstream by `quality_gate.py:1865`. |
| Layer 2 — `bin/council_semantic_check.py:451-457` | `plan_prompts()` writes `quality/citation_semantic_check.json` with `reviews=[]` for the Spec Gap case (zero Tier 1/2 REQs). |
| Layer 2 — `bin/council_semantic_check.py:393-411` | `write_semantic_check()` emits the same `reviews=[]` shape if all auditors fail to produce verdicts. |

Spec Gap and total auditor failure produce byte-identical `citation_semantic_check.json`. Already filed as BUG-018; this comparison is the cross-layer trace that confirms the same shape can mean two different things.

### C-6 (Phase 2 gate) — heading enforcement

| Enforcer | File:line | What it requires |
| --- | --- | --- |
| Spec | `SKILL.md:1026-1042` | 13 criteria: 5 named headings, ≥3 `## Pattern Deep Dive — ` sections, 120-line floor, content-depth checks (≥8 hypotheses, ≥3 multi-function traces, 3-4 patterns FULL, ≥2 deep-dives multi-function, candidate-stage-mix). |
| Mechanical contract | `quality/mechanical/phase2_gate_required_headings.txt:1-8` | 7 numbered items: items 1, 2, 3, 4, 6, 7, 8, 13. Items 5 (`## Pattern Deep Dive`), 9, 10, 11, 12 missing — line numbering jumps from 4 to 6, then 7, 8, 13. |
| Terminal gate | `.github/skills/quality_gate.py:1521-1527` | 5 named headings only (no Pattern Deep Dive count, no 120-line floor, no content-depth checks). |
| Runtime gate | `bin/run_playbook.py:1158-1165` | 120-line floor + file existence only (no heading checks at all). |

Each enforcer covers a strict subset of the spec's 13 criteria, and the subsets do not nest cleanly: the runtime gate has the line floor (which the terminal gate lacks), the terminal gate has the named-heading checks (which the runtime gate lacks), the mechanical contract names criteria 1, 2, 3, 4, 6, 7, 8, 13 (skipping 5, 9-12), and only the spec covers content-depth criteria 9-12. **Net-new diff** — see F-2 below. Note that BUG-002 already covers the runtime-gate side; the parity-bug here is the four-way spread, not the single runtime-gate gap.

### C-7 (Sidecar/manifest JSON writers) — atomic-write pattern

| Side | File:line | Write pattern |
| --- | --- | --- |
| `bin/council_semantic_check.py:407-410` (Layer 2 manifest) | direct `path.write_text(json.dumps(payload, indent=2) + "\n", ...)` — no temp file, no fsync, no atomic rename |
| `bin/reference_docs_ingest.py:296-299` (formal_docs manifest) | direct `out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", ...)` — same shape, no atomic rename |
| `bin/skill_derivation/pass_d.py:401-406` (intermediate Phase 2 artifact) | `.tmp` + `os.replace()` atomic rename |

The two gate-validated manifests use the non-atomic path; an internal Phase 2 helper uses atomic writes. A SIGTERM, SIGKILL, or kernel panic mid-write leaves a half-truncated `formal_docs_manifest.json` or `citation_semantic_check.json` on disk; both are top-level gate-checked artifacts (`SKILL.md:94, 98`). The runtime gate at `bin/run_playbook.py:1158-1165` would not catch this on Phase 2 entry; the terminal gate at `.github/skills/quality_gate.py:1865-1868` checks the file's existence and structural shape, but a half-written file is JSON-parse-broken before the structural check runs. **Net-new diff** — see F-3 below.

### C-8 (Setup vs cleanup) — run_timestamp identifier format

| Side | File:line | Format produced / consumed |
| --- | --- | --- |
| Setup (per-run) | `bin/run_playbook.py:2964` | `datetime.now().strftime("%Y%m%d-%H%M%S")` → e.g. `20260428-131715` (no `T`, no `Z`, naive local time). |
| Setup (top-level main) | `bin/run_playbook.py:3103` | Same `datetime.now().strftime("%Y%m%d-%H%M%S")`. |
| Archive helper — compact form | `bin/archive_lib.py:67-74` | `utc_compact_timestamp()` → `%Y%m%dT%H%M%SZ` → `20260428T131715Z`. |
| Archive helper — extended form | `bin/archive_lib.py:86-97` | `extended_from_compact(ts)` regex `^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$`; **returns input unchanged when it does not match**. |
| Live INDEX stub writer | `bin/run_playbook.py:1806, 1820-1821` | `start_ext = archive_lib.extended_from_compact(timestamp)`, then `"run_timestamp_start": start_ext`. |
| Phase 6 final INDEX writer | `bin/run_playbook.py:1896-1899` | Same `start_ext = archive_lib.extended_from_compact(timestamp)`. |
| Run-metadata sidecar filename gate | `.github/skills/quality_gate.py:1550` | regex `r"run-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.json$"` (extended-with-hyphen-time). |

Setup writes `20260428-131715`; the conversion helper expects `20260428T131715Z` and returns the input unchanged when the regex misses. The result is that the live INDEX.md stub at `bin/run_playbook.py:1820-1821` records `run_timestamp_start` and `run_timestamp_end` as `20260428-131715` — a non-ISO 8601 string that is neither compact nor extended. Three different timestamp formats are in use within one run: A `%Y%m%d-%H%M%S`, B `%Y%m%dT%H%M%SZ`, and C `%Y-%m-%dT%H-%M-%S` (used by run-metadata filenames). **Net-new diff** — see F-4 below.

### C-9 (Agent orchestrators) — SKILL.md fallback order

Already filed as BUG-010 (`agents/quality-playbook-claude.agent.md:47-54` reverses positions 3 and 4 vs `agents/quality-playbook.agent.md:39-42`). Listed here only to ground the parity comparison; no net-new finding.

### C-10 (Agent orchestrators) — references/ resolution rule

| Side | File:line | What it teaches the orchestrator |
| --- | --- | --- |
| Spec | `SKILL.md:49-58` | `references/` resolves through the same four-path fallback as `SKILL.md`: `references/`, `.claude/skills/quality-playbook/references/`, `.github/skills/references/`, `.github/skills/quality-playbook/references/`. |
| Generic agent | `agents/quality-playbook.agent.md:44` | "Also check for a `references/` directory alongside SKILL.md." (alongside-only — does not teach a separate fallback walk for references/.) |
| Claude agent | `agents/quality-playbook-claude.agent.md:54` | "Also check for a `references/` directory alongside SKILL.md." (same alongside-only rule.) |

Both agents teach that `references/` is alongside the resolved `SKILL.md`. In every standard install layout that is true — but the spec wording is broader, asking the consumer to "walk the fallback list above" for any reference file mention. The agents share the gap; they are not drifting *from each other*, they are drifting from the spec. Filed below as F-5 because it is a real cross-product drift even though it is symmetric across agents.

### C-11 (Agent orchestrators) — references/ directory verification rigor

| Side | File:line | Setup verification |
| --- | --- | --- |
| Generic agent | `agents/quality-playbook.agent.md:44` | Lists 11 expected reference files by name (`iteration.md, review_protocols.md, spec_audit.md, verification.md, requirements_pipeline.md, exploration_patterns.md, defensive_patterns.md, schema_mapping.md, constitution.md, functional_tests.md, orchestrator_protocol.md`). Verifies "at least 6 .md files." |
| Claude agent | `agents/quality-playbook-claude.agent.md:54` | "Also check for a `references/` directory alongside SKILL.md." No file list. No count check. |

Same shipped product, two orchestrators with materially different setup-verification rigor. The generic agent fails fast if `references/` is partial; the Claude agent does not. **Net-new diff** — see F-6 below.

---

## Concrete discrepancy findings

### F-1 — Phase prompts split the PROGRESS.md authorship contract

`iteration_prompt` (`bin/run_playbook.py:1127-1134`) is the only prompt that teaches the full PROGRESS.md authorship rule:

> "Any updates to quality/PROGRESS.md must keep the existing phase tracker in checkbox format (`- [x] Phase N - <name>`) — do not rewrite it as a table. The orchestrator appends `## Iteration: <strategy> started/complete` sections itself; iteration work should not touch the existing phase tracker lines."

`phase2_prompt`–`phase6_prompt` (`bin/run_playbook.py:749, 905, 961, 1080, 1107`) each teach only "use the checkbox format `- [x] Phase N - <name>` — do NOT switch to a table." None of them tells the phase agent that the orchestrator owns the iteration-section heartbeat. A phase agent invoked during an iteration could therefore add or rewrite `## Iteration: <strategy> started/complete` blocks in its own update without violating any rule it was told.

Bug hypothesis: when iteration_prompt and phase prompts are run by different agent invocations against the same PROGRESS.md, the phase prompts lack the authorship boundary that protects the iteration-section heartbeat. A phase agent that adds an `## Iteration: ...` section interleaves with the orchestrator's append-only writes. The fix is to copy the orchestrator-vs-iteration boundary text from `iteration_prompt` into each phase-prompt's PROGRESS.md instruction block.

Severity: **LOW–MEDIUM** (manifests as PROGRESS.md drift across multi-agent runs; not data-loss but reliability of run history).

Comparison sub-type: capability/feature-bit parity (different prompts enforce different slices of the same authorship contract).

### F-2 — Phase 2 gate is enforced by four enforcers that each cover a different subset of the spec

`SKILL.md:1026-1042` defines 13 criteria for Phase 2 entry. Four enforcers exist, and none of them covers all 13:

| Enforcer | File:line | Subset enforced |
| --- | --- | --- |
| Runtime gate | `bin/run_playbook.py:1158-1165` | Criteria 1 (line floor) and file existence. |
| Mechanical contract | `quality/mechanical/phase2_gate_required_headings.txt:1-8` | Criteria 1, 2, 3, 4, 6, 7, 8, 13 (skips 5, 9-12). |
| Terminal gate | `.github/skills/quality_gate.py:1521-1527` | Criteria 2, 3, 4, 6, 7 (no line floor, no Pattern Deep Dive count, no content-depth checks). |
| Spec | `SKILL.md:1026-1042` | All 13 criteria. |

The subsets do not nest. The runtime gate has the 120-line floor that the terminal gate lacks. The terminal gate has the named-heading checks that the runtime gate lacks. The mechanical contract has criterion 13 (`Candidate Bugs for Phase 2` candidate-stage mix) that neither gate enforces mechanically. Criteria 9-12 (content depth — hypothesis count, multi-function traces, FULL pattern count, deep-dive multi-function traces) are unenforceable mechanically with the current contract files and are absent from both gates.

Bug hypothesis: a Phase 1 EXPLORATION.md can be authored to pass any one of the four enforcers without satisfying all of them, and the operator gets no signal which criteria are unsatisfied. The runtime gate accepts a 120-line file with no headings; the terminal gate accepts a heading-correct file with 50 lines; both gates together accept either failure mode; criteria 9-12 are silently never enforced. BUG-002 already covers the runtime gate's line-only check, but the parity bug is the four-way spread — every enforcer should validate the same criterion set or explicitly delegate to another enforcer.

Severity: **MEDIUM** (under-enforcement is invisible to the operator; spec criteria 9-12 are dead letters).

Comparison sub-type: capability/feature-bit parity (multiple enforcers, each a different capability slice of the spec).

### F-3 — Two gate-validated JSON manifests use non-atomic write while internal Phase 2 helpers use atomic write

`bin/council_semantic_check.py:407-410` writes `quality/citation_semantic_check.json` with `path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")`. No temp file, no fsync, no atomic rename.

`bin/reference_docs_ingest.py:296-299` writes `quality/formal_docs_manifest.json` the same way — `out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")`. No atomic rename.

A signal during the write (SIGTERM, SIGKILL, or even the `_pkill_fallback` widening from BUG-004) leaves a half-written JSON file on disk. The next gate run reads a truncated file and either fails JSON parsing or, worse, parses a syntactically valid prefix and emits misleading verdicts.

Both files are top-level gate-validated artifacts (`SKILL.md:94, 98`; gate enforcement at `.github/skills/quality_gate.py:1865-1868`). The terminal gate's invariant check happens *after* JSON parse — a `json.JSONDecodeError` on a truncated file produces a generic FAIL but the operator's diagnostic path does not point at "writer is non-atomic."

Bug hypothesis: a run that is interrupted mid-Phase-1 or mid-Phase-4 leaves a permanently corrupt manifest in `quality/`. The corrupt file fails the next gate run; re-running Phase 1 / Phase 4 regenerates the file and the corruption disappears. The user sees a transient "manifest corrupt" error with no obvious cause. The fix is to use the atomic-write pattern already in use at `bin/skill_derivation/pass_d.py:401-406` and similar internal helpers (`.tmp` + `os.replace()`).

Severity: **LOW–MEDIUM** (rare on a quiet machine; reliable to reproduce by signalling the runner during Phase 1 ingest).

Comparison sub-type: resource lifecycle parity (some writers acquire-and-atomically-publish, others write-in-place).

### F-4 — Three timestamp formats in one run; setup writes a non-ISO form that the conversion helper does not recognise

`bin/run_playbook.py:2964` and `:3103` write `datetime.now().strftime("%Y%m%d-%H%M%S")` — e.g., `20260428-131715`. This is naive local time, no `T`, no `Z`. Iteration 3 already filed BUG-019 (timezone hygiene) and BUG-020 (1-second resolution). This finding is a different parity bug: the *format* is also drifting from the archive helpers.

`bin/archive_lib.py:67-74` defines `utc_compact_timestamp()` → `%Y%m%dT%H%M%SZ` → `20260428T131715Z`. `bin/archive_lib.py:86-97` defines `extended_from_compact(ts)` whose regex `^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$` matches *only* the compact-with-T-and-Z form. Per the function's own docstring: "Returns the input unchanged when it does not match the compact pattern."

The setup-side `run_timestamp` is then handed to `extended_from_compact()` at `bin/run_playbook.py:1806` and `:1896`. Because the setup format is `%Y%m%d-%H%M%S` (no `T`, no `Z`), the regex misses and the helper returns the input unchanged. The live `INDEX.md` stub at `bin/run_playbook.py:1820-1821` therefore records:

```
"run_timestamp_start": "20260428-131715",
"run_timestamp_end":   "20260428-131715",
```

Both fields are non-ISO 8601 strings that no downstream consumer can parse without re-implementing the dash convention. The Phase 6 final INDEX writer (`bin/run_playbook.py:1896-1899`) tries the same conversion on the same input and produces the same malformed string, then overwrites `run_timestamp_end` with `archive_lib.utc_extended_timestamp()` — proper extended ISO. The archived INDEX written by `bin/archive_lib.py` somewhere downstream produces a properly converted `run_timestamp_start` (visible in `quality/runs/20260428-131715/INDEX.md:9` for the most recent archived run), so a separate conversion path exists, but the live-tree INDEX is not on it.

A third format appears in `.github/skills/quality_gate.py:1550` for run-metadata filenames: regex `r"run-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.json$"` — extended ISO with hyphens for the time fields. Real run metadata file on disk: `quality/results/run-2026-04-28T18-11-05.json`. So three formats are live: A `%Y%m%d-%H%M%S` (run_timestamp), B `%Y%m%dT%H%M%SZ` (archive folder name + utc_compact_timestamp), C `%Y-%m-%dT%H-%M-%S` (run-metadata filename).

Bug hypothesis: any consumer that reads the live `quality/INDEX.md` and parses `run_timestamp_start` as ISO 8601 fails. The current consumer set is small (the file is mostly archive metadata), so the impact is bounded — but the contract claims ISO 8601 (`SKILL.md:130` "run-YYYY-MM-DDTHH-MM-SS.json" implies ISO 8601 for run identifiers). The fix is to either widen `extended_from_compact()` to accept the dash form, or to convert the setup-side timestamp once at allocation time (`bin/run_playbook.py:2964, 3103`) using `utc_compact_timestamp()` so the entire pipeline sees one canonical compact form.

Severity: **LOW** (live INDEX is rarely consumed externally; archived INDEX is correct via a parallel path; no current gate fails). The parity drift is real and the fix is small.

Comparison sub-type: identifier and index parity (parallel paths compute identifiers for the same logical entity in incompatible formats).

### F-5 — Both agent orchestrators teach a narrower references/ resolution rule than the spec

`SKILL.md:49-58` requires reference-file mentions to walk the same four-path fallback as `SKILL.md` itself:

> "All reference file mentions in this skill use the short form `references/filename.md`. If the relative path doesn't resolve, walk the fallback list above."

`agents/quality-playbook.agent.md:44` and `agents/quality-playbook-claude.agent.md:54` both teach only "Also check for a `references/` directory alongside SKILL.md." The orchestrator following either agent's instructions would resolve the SKILL.md fallback successfully but, when it later sees a relative `references/iteration.md` reference inside SKILL.md, would not know that this path also has a fallback list. In every standard install layout `references/` IS alongside the resolved `SKILL.md`, so the symptom is masked — but the agent's instruction carries less information than the spec.

The drift is symmetric across both agents (they are not drifting from each other) and so this is a parity gap relative to the *spec*, not relative to a sibling agent. Filed because the strategy is "compare parallel paths against the same documented contract" and both parallel paths are off-spec.

Bug hypothesis: a non-standard install (e.g., a fork that mirrors `SKILL.md` to the repo root but keeps `references/` only under `.github/skills/`) would pass the agent's setup check (SKILL.md found) and then fail at any reference-file mention. The fix is to teach both agents the explicit four-path fallback for `references/`, mirroring SKILL.md:49-58.

Severity: **LOW** (corner-case install layouts; standard layouts are unaffected).

Comparison sub-type: capability/feature-bit parity (agents enforce a smaller capability slice than the spec describes).

### F-6 — Generic agent verifies the references/ file set; Claude agent does not

`agents/quality-playbook.agent.md:44` lists eleven expected reference files by name and verifies "at least 6 .md files" exist in `references/`. `agents/quality-playbook-claude.agent.md:54` says only "Also check for a `references/` directory alongside SKILL.md." No file list, no count check, no validation that the directory contains the expected reference files.

This is a parity drift in setup-verification rigor between the two shipped orchestrators. The generic agent fails fast if a partial install lands `SKILL.md` but no references/. The Claude agent does not — it would proceed and let some downstream phase fail when an expected reference file is missing.

Bug hypothesis: an install that successfully copies `SKILL.md` but mis-mirrors `references/` (partial copy, wrong directory, deleted file) would be detected up front by the generic agent and would proceed silently under the Claude agent, surfacing only when a phase prompt cites a missing reference file. The fix is to add the same file-list and count check to the Claude agent's setup section.

Severity: **LOW** (most installs come from `repos/setup_repos.sh` which copies the full set; symptom only on partial / hand-curated installs).

Comparison sub-type: capability/feature-bit parity (one agent enforces a verification capability the other does not).

---

## Demoted parity candidates this iteration

### DC-005: PID file lifecycle drift between sequential and parallel modes

- **Source:** Iteration 4: parity (sub-agent enumeration).
- **Dismissal reason:** the PID file at `bin/run_playbook.py:38` and the `write_pid_file()` helper at `:2826-2833` are only written in the *parallel* mode dispatcher path at `:3007-3008`. The sequential dispatcher at `:3017-3018` calls `run_one()` directly with no PID file management. Sequential mode does not create a PID file, so it cannot leak one. The agent that flagged this asymmetry mistook "no PID file in sequential mode" for "PID file leaked in sequential mode."
- **Code location:** `bin/run_playbook.py:38, 2826-2833, 3007-3008, 3017-3018`.
- **Re-promotion criteria:** show a code path where the sequential dispatcher writes a PID file that subsequent cleanup never removes; or show a sequential code path where `--kill` is expected to find a sequential PID file that was never written.
- **Status:** FALSE POSITIVE [Iteration 4: parity]

### DC-006: `citation_semantic_check.json` and `formal_docs_manifest.json` omit `skill_version`

- **Source:** Iteration 4: parity (sub-agent enumeration).
- **Dismissal reason:** SKILL.md:1091-1103 says manifest files (the `formal_docs_manifest.json`, `requirements_manifest.json`, `use_cases_manifest.json`, `bugs_manifest.json`, and `citation_semantic_check.json` per §9.1) use the §1.6 wrapper with `schema_version` (which equals the skill's `metadata.version` at generation time) and `generated_at` only. Sidecars (`tdd-results.json`, `integration-results.json`) use a separate convention with `schema_version` (sidecar schema, currently "1.1") AND a separate `skill_version` field. The two writers in question correctly follow the manifest convention. Not a drift.
- **Code location:** `bin/council_semantic_check.py:393-405`, `bin/reference_docs_ingest.py:284-299`, `SKILL.md:1091-1103, 138-178`.
- **Re-promotion criteria:** show that SKILL.md or schemas.md actually requires `skill_version` to appear in `citation_semantic_check.json` or `formal_docs_manifest.json`.
- **Status:** FALSE POSITIVE [Iteration 4: parity]

### DC-007: iteration ask-user gating diverges between agents

- **Source:** Iteration 4: parity (sub-agent enumeration).
- **Dismissal reason:** both agents instruct the orchestrator to ask the user before running iterations. `agents/quality-playbook.agent.md:106` ("After Phase 6 completes, report the full results and ask if the user wants to run iteration strategies"); `agents/quality-playbook-claude.agent.md:88` ("After Phase 6, ask if the user wants iterations"). The wording differs but the contract is the same.
- **Code location:** `agents/quality-playbook.agent.md:106`, `agents/quality-playbook-claude.agent.md:88`.
- **Re-promotion criteria:** show a shipped agent revision where one orchestrator runs iterations without asking and the other does ask.
- **Status:** FALSE POSITIVE [Iteration 4: parity]

---

## Iteration 4 yield summary

- 6 parallel groups enumerated.
- 11 pairwise comparisons traced (C-1 through C-11).
- 6 net-new discrepancy findings (F-1 through F-6); 3 referenced existing bugs (BUG-008 / BUG-010 / BUG-011 / BUG-018) without re-filing.
- 3 demoted parity candidates (DC-005, DC-006, DC-007).
