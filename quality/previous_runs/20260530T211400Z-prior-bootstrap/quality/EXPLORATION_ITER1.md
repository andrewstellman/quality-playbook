# PARITY Iteration — Cross-Implementation Findings
Date: 2026-05-19
Strategy: parity
Parallel groups probed: 5 (Mode A vs B, install paths, manifest schemas, validator vs gate, +verdict taxonomy plumbing)

Scope notes: BUG-001..006 (Phase 3 code review) are NOT re-found here; this
iteration probes implementation-divergence defects across parallel surfaces
that the structural review missed.

---

## Group 1: Mode A vs Mode B

### Resource lifecycle parity: Mode A walkthrough has no archive step
- Path 1 (Mode B): `bin/run_playbook.py:3829` — orchestrator unconditionally
  calls `archive_lib.archive_run(...)` before launching Phase 1, snapshotting
  the prior `quality/` into `quality/previous_runs/<TIMESTAMP>/`. SKILL.md:122
  and SKILL.md:150 advertise this contract to operators ("Any prior `quality/`
  directory is auto-archived").
- Path 2 (Mode A): SKILL.md:85-93 ("For each phase 1..6, in order...") and
  `phase_prompts/phase1.md` contain ZERO mention of archival. Grep
  `phase_prompts/*.md` for `archive|previous_runs` returns only one match
  (phase5.md:157, an unrelated INDEX schema_version note). A Mode A operator
  starting a re-run against a target that already has a populated `quality/`
  has no documented step to archive it.
- Divergence: Mode B always snapshots and lands the live tree under
  `quality/previous_runs/<ts>/`; Mode A silently lets the agent overwrite (or
  worse, partially clobber) prior artifacts, breaking the "every prior run is
  preserved" invariant only one of the two paths upholds.
- Severity hypothesis: HIGH (silent data loss / RUN_INDEX.md history gap; the
  paths SKILL.md sells as equivalent are not).
- Promotion recommendation: PROMOTE TO BUG (BUG-007-PARITY)

### Capability/feature-bit parity: Phase 0 install-validator gate is Mode-A-only
- Path 1 (Mode A): SKILL.md:77 — "Phase 0 (MANDATORY first action): run the
  QPB install validator" via `python3 bin/qpb_validate.py <target-repo>`,
  with non-negotiable wait until `event=validation_complete status=ok`.
- Path 2 (Mode B): `bin/run_playbook.py` performs its own pre-flight checks
  (sentinel files, gate-script resolution, source-edit baseline) but does NOT
  invoke `bin/qpb_validate.py`. Grep `bin/run_playbook.py` for `qpb_validate`
  returns zero hits.
- Divergence: the validator that catches the documented "2026-05-17 httpx
  install-path root cause" is mandatory in Mode A but absent in Mode B. A
  Mode B operator launching the orchestrator against a broken install gets
  no equivalent gate.
- Severity hypothesis: MEDIUM (operators expect Mode B to be the higher-rigor
  path; absence of a gate that Mode A treats as "non-negotiable" inverts the
  rigor ranking).
- Promotion recommendation: PROMOTE TO BUG (BUG-008-PARITY)

### Iteration/collection parity: Mode A excludes iteration strategies; Mode B owns them
- Path 1 (Mode A): SKILL.md:101 — "Iteration strategies (gap / unfiltered /
  parity / adversarial) ... In Mode A, after Phase 6 completes cleanly, hand
  off to Mode B for iterations." Mode A IS scoped to phases 1-6 only.
- Path 2 (Mode B): `bin/run_playbook.py:52` — `ALL_STRATEGIES = ["gap",
  "unfiltered", "parity", "adversarial"]`; bare invocation runs all four
  (SKILL.md:122).
- Divergence: this is documented and intentional, NOT a bug — but it
  inverts the typical agent expectation that "Mode A == doing it yourself"
  covers the full skill surface. Worth flagging because the parity table at
  SKILL.md:57-60 ("Both modes use the same phase prompt content") elides this
  capability asymmetry.
- Severity hypothesis: LOW (design intent, not divergence).
- Promotion recommendation: DEMOTE (documented design choice — SKILL.md
  §"Mode A scope — what's covered, what's Mode-B-only" enumerates the gap).

---

## Group 2: Install paths

### Iteration/collection parity: WARN message lists 6 of 10 layouts
- Path 1 (canonical): SKILL.md:215-224 + `bin/run_playbook.py:1078-1090`
  (`SKILL_FALLBACK_GUIDE`) + `bin/benchmark_lib.py:52-65`
  (`SKILL_INSTALL_LOCATIONS`) + `bin/run_playbook.py:4510-4521`
  (`_GATE_INSTALL_LOCATIONS`) + `phase_prompts/phase6_auditor.md:39-49` —
  ALL enumerate the same canonical TEN install layouts, in matching order.
- Path 2 (drifted): `bin/run_playbook.py:1051-1062` — `WARN: No QPB-installed
  SKILL.md found...` message enumerates ONLY 6 layouts: `SKILL.md`,
  `.claude/...`, `.github/skills/SKILL.md`, `.cursor/...`, `.continue/...`,
  `.github/skills/quality-playbook/SKILL.md`. MISSING: `.codex/`,
  `.windsurf/`, `.cline/`, `.aider/`. The internal v1.5.7 instruction-046
  comment at line 1048 reads "list all 6 canonical install layouts (was 3
  pre-fix)" — a literal carry-over from before the 6→10 expansion.
- Divergence: an adopter who installs into `.codex/skills/quality-playbook/`
  and runs Mode B from a sibling target gets a WARN that says "expected at
  one of [6 layouts]" with their actual install path NOT in the list, and a
  truncated 5-bullet message ending with `.continue/...` — which suggests
  their layout isn't supported. It IS supported; the warning text wasn't
  updated when `SKILL_FALLBACK_GUIDE` / `SKILL_INSTALL_LOCATIONS` /
  `_GATE_INSTALL_LOCATIONS` were expanded.
- Severity hypothesis: MEDIUM (adopter-facing diagnostic that misrepresents
  supported layouts; recreates the failure mode the v1.5.6 BUG-002 fix was
  supposed to close).
- Promotion recommendation: PROMOTE TO BUG (BUG-009-PARITY)

### Iteration/collection parity: install_skill intro_short lists 4 of 8 markers
- Path 1 (canonical): `bin/install_skill.py:46-58` — `KNOWN_ENVIRONMENTS`
  scans 8 marker directories (claude, github, cursor, continue, codex,
  windsurf, cline, aider). `install_skill.py:66-81` (`AI_TOOL_MAP`) also
  carries 8 (9 if you count the `github`/`copilot` alias).
- Path 2 (drifted): `bin/install_skill.py:786-791` — `intro_short` operator-
  facing message says "auto-detection scans for the marker (.cursor/,
  .claude/, .github/, .continue/)". Only 4 of the 8 markers `detect_environment`
  actually scans are listed. The companion `intro_verbose` at lines 792-801
  similarly enumerates 4 example markers but at least the `--ai-tool` help
  string mentions all 8 (lines 789-790).
- Divergence: a `cline` or `windsurf` user reading the installer's first
  emitted line ("auto-detection scans for the marker (.cursor/, .claude/,
  .github/, .continue/)") is told their tool isn't auto-detected. It IS
  auto-detected. The drift is inside the same file as the canonical list.
- Severity hypothesis: LOW (cosmetic/UX diagnostic, but a documented contract
  drift — KNOWN_ENVIRONMENTS expansion in instruction-046 didn't update the
  intro message).
- Promotion recommendation: PROMOTE TO BUG (BUG-010-PARITY)

### Resource lifecycle parity: install_skill.py has no uninstall
- Path 1 (forward): `bin/install_skill.py:752-1041` — full `install()`
  function with bundle copy, smoke checks, sentinel files, downgrade refusal.
- Path 2 (reverse): no `uninstall`, `remove`, or `cleanup` function exists.
  Grep `def uninstall|def remove|def cleanup` in `bin/install_skill.py`
  returns zero matches.
- Divergence: the installer creates 25+ files plus 2 sentinels plus a marker
  directory; there is no documented mechanism to reverse the operation. An
  adopter who runs `python3 -m bin.install_skill --ai-tool cursor` and later
  wants to remove QPB has no tooling.
- Severity hypothesis: LOW (operator-managed `rm -rf` is acceptable; design
  choice).
- Promotion recommendation: DEMOTE (design choice — adopter-managed
  uninstall via filesystem operations is the documented model; no operator
  has requested an uninstall function).

---

## Group 3: Manifest schemas

### Capability/feature-bit parity: gate accepts non-dict summary; validator rejects
- Path 1 (gate): `.github/skills/quality_gate/quality_gate.py:2858-2866`
  inside `check_v1_5_0_index_md`:
  ```
  summary = payload.get("summary")
  if isinstance(summary, dict):
      for sub in _V150_REQUIRED_SUMMARY_KEYS:
          if sub not in summary:
              fail(...)
  pass_("quality/INDEX.md: §11 fields present")
  ```
  If `summary` is present but not a dict (e.g., a string, a list, null), the
  gate emits PASS — the `if isinstance(summary, dict)` short-circuits silently.
- Path 2 (validator): `bin/validate_phase_artifacts.py:366-369`:
  ```
  summary = payload.get("summary")
  if not isinstance(summary, dict):
      fails.append("FAIL: quality/INDEX.md 'summary' is not an object ...")
  ```
  The validator explicitly FAILs on a non-dict summary.
- Divergence: a Phase 6 run with `"summary": "pending"` (string) passes the
  gate and fails the validator. The two surfaces enforce different contracts
  on the same field. Per schemas.md §11 line 1128 ("summary | object | yes"),
  the validator is correct and the gate has a soft-pass hole.
- Severity hypothesis: MEDIUM (the validator catches this so it is not
  silently exploitable end-to-end, but the gate is supposed to be the
  terminal authority; this is the validator carrying contract weight the
  gate documented but didn't enforce).
- Promotion recommendation: PROMOTE TO BUG (BUG-011-PARITY)

### Capability/feature-bit parity: schema gate_verdict enum missing "pass_with_cleanup"
- Path 1 (gate output v1.5.7 089c three-state):
  `.github/skills/quality_gate/quality_gate.py:230-235` — the gate now emits
  three distinct verdicts: `GATE PASSED`, `GATE PASSED WITH CLEANUP NEEDED`
  (exit 0), `GATE FAILED` (exit 1). `phase_prompts/phase6.md:48-52` and
  `phase_prompts/phase6_auditor.md:73-82` instruct the Phase 6 auditor to
  emit a three-state AUDITOR VERDICT: `PASS` / `PASS WITH CLEANUP NEEDED` /
  `FAIL`.
- Path 2 (schema): `schemas.md:1130` — `summary.gate_verdict` must be "One
  of `pass`, `fail`, `partial`." `bin/validate_phase_artifacts.py:109` —
  `_INDEX_VALID_VERDICTS = ("pass", "partial", "fail")`. NO "pass_with_cleanup"
  state, no documented mapping for the new third verdict.
- Divergence: a Phase 6 auditor following the phase_prompts/phase6.md
  protocol gets `AUDITOR VERDICT: PASS WITH CLEANUP NEEDED` and must record
  it in `quality/INDEX.md`. There is no defined mapping — does it map to
  `pass`? to `partial`? Both are accepted by the validator but mean
  different things. The 089c gate change shipped without a corresponding
  schema/validator/INDEX update.
- Severity hypothesis: HIGH (operators get conflicting guidance; the same
  successful run can be recorded in `gate_verdict` as either `"pass"` or
  `"partial"` depending on agent interpretation, defeating the audit-trail
  purpose of INDEX.md).
- Promotion recommendation: PROMOTE TO BUG (BUG-012-PARITY)

### Identifier/index parity: archive_lib regex never matches the v1.5.7 gate output
- Path 1 (gate output): the gate prints `RESULT: GATE PASSED|FAILED|PASSED
  WITH CLEANUP NEEDED` and `Total: N FAIL, M WARN` — see quality_gate.py:210-234.
  There is NO `gate_result: "PASS"` key anywhere in the gate output (grep
  `gate_result` returns zero matches in quality_gate.py).
- Path 2 (archive consumer): `bin/archive_lib.py:73` — `_GATE_RESULT_PATTERN
  = re.compile(r"gate_result['\"]?\s*[:=]\s*['\"](PASS|FAIL|WARN)['\"]?",
  re.IGNORECASE)`. Used at `_extract_gate_verdict()` lines 399 and 407
  to scan `quality/results/run-*.json` and `gate-report-latest.json` for
  a gate_result key. Falls through to PROGRESS.md text-match
  (`re.search(r"gate_result\s*[:.-]?\s*pass|\bPASS\b", tail)`) at line
  417, then to `return "unknown"` at line 419.
- Divergence: the archive verdict extractor was written for a gate-output
  format that no longer exists. Every Mode B archive run writes INDEX.md
  with `gate_verdict: "unknown"` (or possibly `"pass"` via the text-match
  fallback IF "PASS" happens to appear in the trailing PROGRESS.md
  Terminal Gate block), and `"unknown"` then fails the Phase 6 validator's
  `_INDEX_VALID_VERDICTS` enum at line 109.
- Severity hypothesis: HIGH (this is an end-to-end break: Mode B archive →
  INDEX.md → validator → FAIL on a successful run, masked only because the
  fallback-fallback text match for `\bPASS\b` in PROGRESS.md sometimes
  accidentally succeeds).
- Promotion recommendation: PROMOTE TO BUG (BUG-013-PARITY)

---

## Group 4: Validator vs gate

### Error/exception parity: gate stricter on INDEX presence than validator scope
- Path 1 (gate): `.github/skills/quality_gate/quality_gate.py:2776-2782` —
  `check_v1_5_0_index_md` only FAILs on missing INDEX.md if any v1.5.0
  artifact exists (`is_v150_run = any((q / name).is_file() for name in
  v150_artifacts)`). If no v1.5.0 manifests present, missing INDEX.md is a
  silent return (no FAIL, no WARN).
- Path 2 (validator): `bin/validate_phase_artifacts.py:318-323` —
  `_load_index_payload` unconditionally FAILs if INDEX.md is missing,
  with no `is_v150_run` short-circuit.
- Divergence: a Phase 5/6 run that hasn't produced any manifest yet but
  HAS reached Phase 5 (e.g., a degenerate target) gets PASS from the gate
  but FAIL from the validator. Documented intent in
  validate_phase_artifacts.py:42-48 is "validator-PASS is a strict subset
  of gate-PASS" — but this INDEX presence check is reversed (validator
  stricter than gate).
- Severity hypothesis: LOW (the documented sub-set claim covers
  `generated_at` but the file-presence check is the inverse direction;
  worth noting but doesn't surface a real adopter failure mode because the
  gate's `is_v150_run` is True for any real Phase 5+ run).
- Promotion recommendation: DEMOTE (test-coherence documented; the
  scenario where it manifests as user-visible drift requires a malformed
  run state).

### Capability/feature-bit parity: validator schema_version stricter than gate
- Path 1 (gate): `quality_gate.py:2821-2837` — gate accepts FOUR
  schema_version states: `"1.0"` (legacy WARN), absent/empty + legacy
  heuristic (legacy WARN), `"2.0"` (current), absent/empty + non-legacy
  payload (current — treated as a v1.5.4 stub).
- Path 2 (validator): `bin/validate_phase_artifacts.py:350-356` — validator
  requires literal `schema_version == "2.0"`; absent or any other value
  is FAIL: "a current run MUST emit '2.0'".
- Divergence: the gate accepts a missing `schema_version` on a current run
  (case 4 in its logic); the validator rejects it. A Phase 5 INDEX.md that
  forgets to set schema_version passes the gate but fails the validator.
  Documented as "validator runs against the live run, so 2.0 is required",
  but the gate's case-4 fallback documentation says exactly the opposite
  ("treated as v1.5.4 stub that simply hasn't populated schema_version
  yet").
- Severity hypothesis: MEDIUM (a Mode B run between the v1.5.4 stub and
  the post-Phase-5 INDEX rewrite can hit this; the gate says PASS, the
  validator says FAIL, and the operator gets conflicting verdicts).
- Promotion recommendation: PROMOTE TO BUG (BUG-014-PARITY)

### Iteration/collection parity: validator covers only 4 of 6 phases
- Path 1 (gate): runs over ALL artifacts regardless of phase.
- Path 2 (validator): `bin/validate_phase_artifacts.py:392-397` —
  `_PHASE_DISPATCH = {1, 2, 5, 6}`. Phase 3 and Phase 4 have no boundary
  validator. SKILL.md:79, phase_prompts/phase1.md:79-81,
  phase_prompts/phase6_auditor.md:90 require the validator at boundaries
  1, 2, 5, 6 but Phase 3 (code review) and Phase 4 (spec audit) have no
  equivalent fast-fail.
- Divergence: the "fast-fail subset of quality_gate.py — run at phase
  boundaries" contract documented at validate_phase_artifacts.py:14 only
  applies at 4 of 6 boundaries. An agent producing malformed Phase 3 or
  Phase 4 artifacts won't be caught until the terminal gate.
- Severity hypothesis: LOW (design choice — instructions 065/072/073 only
  promoted A-14/A-15/A-16 to validator; Phase 3 / Phase 4 artifact-shape
  drift is captured by the terminal gate at Phase 6).
- Promotion recommendation: DEMOTE (deliberate per
  validate_phase_artifacts.py:14 "fast-fail SUBSET ... never a
  re-implementation of the full gate").

---

## Group 5 (self-discovered): Phase 6 sub-agent delegation Mode-B opt-out

### Allocation-context parity: phase6.md branches on Mode B vs Mode A but auditor prompt does not
- Path 1 (phase6.md branching): `phase_prompts/phase6.md:5-7` explicitly
  says Mode B per-phase subprocess IS its own isolated context: "you ARE
  already an isolated fresh context with none of the same-context executor
  bias ... Execute the verification directly: run mechanical verify, run
  `quality_gate.py`, capture the verbatim ... DO NOT spawn a nested
  sub-agent — your subprocess IS the auditor."
- Path 2 (phase6_auditor.md): `phase_prompts/phase6_auditor.md:1-134` —
  the auditor prompt has NO Mode-A/Mode-B branch. It assumes it is invoked
  as a sub-agent by a Mode A operator. There is no opt-out for "I am a
  Mode B subprocess that loaded this prompt directly because phase6.md
  told me to skip Part A and execute inline."
- Divergence: a Mode B agent reading `phase_prompts/phase6_auditor.md`
  (because phase6.md tells it to honor the "same witness contract" and
  it interprets that as "follow the auditor prompt") would then read
  "Your scope (audit-only — NO execution work) ... You did NOT execute
  Phases 1-5" — which is the OPPOSITE of Mode B's reality (the same
  per-phase subprocess executes prior phases too, just one-at-a-time).
  The two prompts disagree about what context they run in.
- Severity hypothesis: MEDIUM (the prompt-content single-source-of-truth
  claim at SKILL.md:62 is broken for phase6_auditor.md — it ONLY makes
  sense in Mode A; phase6.md tries to compensate but the disagreement is
  load-bearing for the Phase-6-fabrication failure mode the auditor exists
  to close).
- Promotion recommendation: PROMOTE TO BUG (BUG-015-PARITY)

---

## Promotion summary

| Finding                                                          | Group              | Category               | Recommendation              |
|------------------------------------------------------------------|--------------------|------------------------|-----------------------------|
| Mode A walkthrough has no archive step                           | 1 (Mode A vs B)    | resource lifecycle     | PROMOTE → BUG-007-PARITY    |
| Phase 0 install-validator is Mode-A-only                         | 1 (Mode A vs B)    | capability/feature-bit | PROMOTE → BUG-008-PARITY    |
| Mode A excludes iteration strategies (documented)                | 1 (Mode A vs B)    | iteration/collection   | DEMOTE (design)             |
| WARN message lists 6 of 10 install layouts                       | 2 (install paths)  | iteration/collection   | PROMOTE → BUG-009-PARITY    |
| install_skill intro_short lists 4 of 8 markers                   | 2 (install paths)  | iteration/collection   | PROMOTE → BUG-010-PARITY    |
| install_skill.py has no uninstall                                | 2 (install paths)  | resource lifecycle     | DEMOTE (design)             |
| Gate silently passes non-dict `summary`; validator rejects       | 3 (manifest schema)| capability/feature-bit | PROMOTE → BUG-011-PARITY    |
| Schema lacks `pass_with_cleanup` for 089c three-state            | 3 (manifest schema)| capability/feature-bit | PROMOTE → BUG-012-PARITY    |
| `archive_lib._GATE_RESULT_PATTERN` regex never matches v1.5.7    | 3 (manifest schema)| identifier/index       | PROMOTE → BUG-013-PARITY    |
| INDEX presence check inverted: gate softer than validator        | 4 (validator/gate) | error/exception        | DEMOTE (edge case)          |
| Validator stricter than gate on absent `schema_version`          | 4 (validator/gate) | capability/feature-bit | PROMOTE → BUG-014-PARITY    |
| Validator covers only phases 1/2/5/6                             | 4 (validator/gate) | iteration/collection   | DEMOTE (design)             |
| phase6_auditor.md has no Mode-B branch but phase6.md routes to it| 5 (self-discovered)| allocation context     | PROMOTE → BUG-015-PARITY    |

Pairwise comparisons traced with file:line: 13 promoted/considered + 4 demoted = 17 explicit comparisons.

---

## Bugs to promote into BUGS.md

### BUG-007: Mode A walkthrough has no `quality/` archive step; Mode B always archives
- Primary requirement: (parity contract — SKILL.md:57-65 + 122 + 150)
- Severity: HIGH
- Source: PARITY iteration (Group 1, resource lifecycle parity)
- File:line: `bin/run_playbook.py:3829-3836` (Mode B archive_run call);
  `bin/archive_lib.py:673-688` (canonical `archive_run`); SKILL.md:85-103
  (Mode A walkthrough — no archive guidance); `phase_prompts/phase1.md`
  (no archival mention)
- Expected behavior: SKILL.md:62 promises "Both modes use the same phase
  prompt content ... the only thing the two modes differ on is WHO drives".
  A Mode A operator re-running on an existing `quality/` should get the
  same auto-archive semantics Mode B advertises at SKILL.md:122 + 150.
- Actual behavior: Mode A has no documented archive step; the agent
  overwrites or partially clobbers the prior run's `quality/` content,
  losing the `previous_runs/<ts>/` history Mode B preserves. SKILL.md:154
  explicitly tells Mode A operators "`git restore quality/`" for abort
  recovery — implying delete-on-restart, not archive-on-restart.

### BUG-008: Phase 0 install-validator (`bin/qpb_validate.py`) is mandatory in Mode A, absent from Mode B
- Primary requirement: (Phase 0 contract — SKILL.md:77)
- Severity: MEDIUM
- Source: PARITY iteration (Group 1, capability/feature-bit parity)
- File:line: SKILL.md:77 (Mode A mandate, "non-negotiable; skipped/fabricated
  validation is the 2026-05-17 httpx/install-path root cause");
  `bin/run_playbook.py` (no `qpb_validate` invocation — grep returns 0 hits);
  `bin/qpb_validate.py:1` (script itself)
- Expected behavior: the install-validator that prevents the documented
  2026-05-17 httpx install-path failure mode should fire in BOTH modes,
  since Mode B is the path most likely to hit it (CI / batch / non-
  interactive).
- Actual behavior: Mode A operators run `bin/qpb_validate.py` as a hard
  gate; Mode B's `bin/run_playbook.py` performs its own pre-flight (sentinel
  files, source-edit baseline) but never invokes the install validator.
  The "non-negotiable" Phase 0 gate is non-existent in Mode B.

### BUG-009: WARN message at `bin/run_playbook.py:1051-1062` lists 6 of 10 canonical install layouts
- Primary requirement: (install-layout contract — SKILL.md:213-226 enumerates
  10 canonical layouts; benchmark_lib `SKILL_INSTALL_LOCATIONS`,
  `SKILL_FALLBACK_GUIDE`, and `_GATE_INSTALL_LOCATIONS` ALL carry 10)
- Severity: MEDIUM
- Source: PARITY iteration (Group 2, iteration/collection parity)
- File:line: `bin/run_playbook.py:1051-1062` (the drifted WARN);
  `bin/run_playbook.py:1048` (carry-over comment "list all 6 canonical
  install layouts — was 3 pre-fix"); `bin/run_playbook.py:1078-1090`
  (`SKILL_FALLBACK_GUIDE` — 10 layouts); `bin/benchmark_lib.py:52-65`
  (`SKILL_INSTALL_LOCATIONS` — 10 layouts)
- Expected behavior: the operator-facing WARN should enumerate the same 10
  canonical install layouts the resolver actually searches.
- Actual behavior: the WARN message lists `SKILL.md`, `.claude/...`,
  `.github/skills/SKILL.md`, `.cursor/...`, `.continue/...`, and
  `.github/skills/quality-playbook/SKILL.md` — 6 layouts. Missing:
  `.codex/skills/quality-playbook/SKILL.md`,
  `.windsurf/skills/quality-playbook/SKILL.md`,
  `.cline/skills/quality-playbook/SKILL.md`,
  `.aider/skills/quality-playbook/SKILL.md`. A `cline` / `windsurf` / `codex`
  / `aider` adopter reading the warning is told their layout is unsupported.

### BUG-010: `install_skill.py` `intro_short` lists 4 of 8 auto-detected markers
- Primary requirement: (auto-detection contract — `install_skill.py:46-58`
  `KNOWN_ENVIRONMENTS` enumerates 8 markers)
- Severity: LOW
- Source: PARITY iteration (Group 2, iteration/collection parity)
- File:line: `bin/install_skill.py:786-791` (the drifted `intro_short`);
  `bin/install_skill.py:46-58` (canonical KNOWN_ENVIRONMENTS — 8 markers);
  `bin/install_skill.py:66-81` (canonical AI_TOOL_MAP — 8 tools)
- Expected behavior: `intro_short` should name the same markers
  `detect_environment` actually scans.
- Actual behavior: `intro_short` says `"auto-detection scans for the marker
  (.cursor/, .claude/, .github/, .continue/)"` — 4 of the 8 markers the
  installer auto-detects. `intro_verbose` at lines 792-801 mentions 4
  examples plus referencing the `--ai-tool` choice list at lines 789-790
  (which IS complete). The visible intro_short message misrepresents
  auto-detection coverage to `cline` / `windsurf` / `codex` / `aider`
  adopters.

### BUG-011: `quality_gate.py::check_v1_5_0_index_md` silently passes when `summary` is not a JSON object
- Primary requirement: (schemas.md:1128 "summary | object | yes")
- Severity: MEDIUM
- Source: PARITY iteration (Group 3, capability/feature-bit parity)
- File:line: `.github/skills/quality_gate/quality_gate.py:2858-2866`
  (the soft-pass hole); `bin/validate_phase_artifacts.py:366-369` (the
  validator's explicit FAIL); schemas.md:1128 (contract)
- Expected behavior: if `quality/INDEX.md` carries `summary` as anything
  other than a JSON object (e.g., `"summary": "pending"`, `"summary": []`,
  `"summary": null`), the gate must FAIL — schemas.md:1128 declares the
  type "object", required yes.
- Actual behavior: the gate code reads `if isinstance(summary, dict):`
  before the required-keys loop; a non-dict summary skips the check
  entirely and the function ends with `pass_("quality/INDEX.md: §11 fields
  present")`. The validator catches this in Mode A walkthroughs, but the
  gate (the terminal authority) lets it through.

### BUG-012: 089c three-state verdict has no `gate_verdict` enum value in `schemas.md` / `INDEX.md`
- Primary requirement: (schemas.md:1130 + phase_prompts/phase6.md:48-52)
- Severity: HIGH
- Source: PARITY iteration (Group 3, capability/feature-bit parity)
- File:line: `.github/skills/quality_gate/quality_gate.py:230-235` (gate
  emits 3 verdicts including new `GATE PASSED WITH CLEANUP NEEDED`);
  `phase_prompts/phase6.md:48-52` + `phase_prompts/phase6_auditor.md:73-82`
  (auditor must emit 3-state AUDITOR VERDICT); schemas.md:1130 (only
  3 enum values: `pass`/`fail`/`partial`); `bin/validate_phase_artifacts.py:109`
  (validator's `_INDEX_VALID_VERDICTS = ("pass", "partial", "fail")`)
- Expected behavior: when the v1.5.7 089c instruction added a third gate
  verdict state (`PASS WITH CLEANUP NEEDED`), schemas.md §11 and the
  validator's enum should have been updated in lockstep, with a documented
  mapping from `AUDITOR VERDICT: PASS WITH CLEANUP NEEDED` to a canonical
  `gate_verdict` value (e.g., new `"pass_with_cleanup"` or explicit "this
  maps to `partial`" doc).
- Actual behavior: the gate emits three verdicts; the schema/validator/INDEX
  contract only knows three (`pass`/`fail`/`partial`) — different three.
  A Phase 6 run that gets `RESULT: GATE PASSED WITH CLEANUP NEEDED` has
  no defined `gate_verdict` value. An agent may pick `"pass"` (collapses
  the distinction the gate just made) or `"partial"` (collapses to "the
  run failed" semantics) — the audit-trail purpose of `gate_verdict` is
  broken either way.

### BUG-013: `archive_lib._GATE_RESULT_PATTERN` regex cannot match the v1.5.7 gate output format
- Primary requirement: (gate output format — quality_gate.py:210-234)
- Severity: HIGH
- Source: PARITY iteration (Group 3, identifier/index parity)
- File:line: `bin/archive_lib.py:73` (the stale regex
  `gate_result['\"]?\s*[:=]\s*['\"](PASS|FAIL|WARN)`);
  `bin/archive_lib.py:395-419` (`_extract_gate_verdict` consumer);
  `.github/skills/quality_gate/quality_gate.py:210-234` (actual gate
  output format `RESULT: GATE PASSED|FAILED|...`); zero matches of
  `gate_result` token anywhere in quality_gate.py
- Expected behavior: when Mode B's `archive_run()` builds `INDEX.md`'s
  `summary.gate_verdict`, it should parse the actual gate output format
  the v1.5.7 gate produces and emit one of `pass`/`fail`/`partial`
  matching schemas.md §11.
- Actual behavior: `_extract_gate_verdict` scans run JSON for a
  `gate_result: "PASS"` key/value that the gate has never emitted; the
  regex never matches; the function falls through to a PROGRESS.md text
  search for `\bPASS\b` (matches accidentally on any "PASS" substring)
  or returns `"unknown"`. The string `"unknown"` then fails the validator's
  `_INDEX_VALID_VERDICTS` enum at Phase 6, breaking a successful run's
  audit trail. The Mode-B archive pipeline silently degraded when the
  gate's output format changed.

### BUG-014: Validator requires `schema_version: "2.0"` literal; gate's case-4 fallback says missing is OK
- Primary requirement: (schemas.md:1119 "yes (v1.5.4+)" + gate at
  quality_gate.py:2755-2758 documents the case-4 fallback)
- Severity: MEDIUM
- Source: PARITY iteration (Group 4, capability/feature-bit parity)
- File:line: `bin/validate_phase_artifacts.py:350-356` (validator literal-
  match enforcement); `.github/skills/quality_gate/quality_gate.py:2821-2829`
  (gate case 4 — absent schema_version falls through to "current path")
- Expected behavior: gate and validator should agree on whether an absent
  `schema_version` is acceptable on a current Phase 5/6 run. The
  validator's docstring (line 346-349) claims agreement ("schemas.md §11
  is the canonical contract; test coherence pins the mirror"), but the
  literal check disagrees with the gate's documented fallback.
- Actual behavior: an INDEX.md missing `schema_version` (the Phase 1
  stub-INDEX case the gate explicitly tolerates) passes the gate and
  fails the validator — opposite enforcement direction. The mirror at
  `_INDEX_REQUIRED_FIELDS` does NOT include `schema_version` (line 96-107),
  yet the validator's literal check requires it. The gate's case-4
  documentation says absent is "treated as v1.5.4 stub"; the validator
  rejects that path outright.

### BUG-015: `phase_prompts/phase6_auditor.md` has no Mode-B branch despite phase6.md routing Mode B to it
- Primary requirement: (SKILL.md:62 single-source-of-truth claim +
  phase6.md:5-7 Mode B/A branch contract)
- Severity: MEDIUM
- Source: PARITY iteration (Group 5, allocation context parity)
- File:line: `phase_prompts/phase6.md:5-7` (says Mode B subprocess IS the
  auditor, executes inline, "honor the same witness contract");
  `phase_prompts/phase6_auditor.md:1-15` (assumes Mode-A sub-agent: "You
  did NOT execute Phases 1-5; your sole role is ground-truthing");
  `phase_prompts/phase6_auditor.md:16-30` ("You WILL NOT: Write new
  artifacts... Fix any FAIL")
- Expected behavior: Both prompts share the same load-bearing role
  description and witness contract. If phase6.md routes a Mode B
  subprocess to honor `phase6_auditor.md`'s witness contract, the auditor
  prompt should acknowledge the Mode-B context where the same agent DID
  just execute prior phases.
- Actual behavior: a Mode B agent that read phase6.md and tries to follow
  "honor the same witness contract" by reading `phase6_auditor.md` is
  told "You did NOT execute Phases 1-5" — directly contradicting its
  reality (same subprocess, just one-at-a-time, executes prior phases).
  The two prompts disagree about which context they apply in. The SKILL.md:62
  claim that "both modes use the same phase prompt content" is broken for
  `phase6_auditor.md` — it only makes structural sense under Mode A
  sub-agent invocation.
