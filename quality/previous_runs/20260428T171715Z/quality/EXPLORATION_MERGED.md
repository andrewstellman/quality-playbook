# Merged Exploration — quality-playbook

Resolved skill path: `SKILL.md`
Resolved references path: `references/`
Date: 2026-04-28

## Open Exploration Findings

### [Iteration 1: baseline] Cross-surface drift already confirmed in the baseline run

1. `[Iteration 1: baseline]` `docs_present()` still keys docs-availability off `docs_gathered/` even though Phase 1 now treats `reference_docs/` as canonical (`bin/run_playbook.py:1552-1622`).
2. `[Iteration 1: baseline]` The Phase 2 executable gate still reduces the exploration contract to file presence plus line count (`bin/run_playbook.py:1152-1165`).
3. `[Iteration 1: baseline]` Live `quality/INDEX.md` writers still collapse non-Code classifications to `Code` (`bin/run_playbook.py:1819-1895`).
4. `[Iteration 1: baseline]` Cleanup without PID files still widens into workstation-scoped `pkill -f` patterns (`bin/run_playbook.py:2807-2875`).
5. `[Iteration 1: baseline]` Installed gate copies still drop the citation-verifier dependency surface (`repos/setup_repos.sh:195-200`; `.github/skills/quality_gate/quality_gate.py:32-44`).
6. `[Iteration 1: baseline]` Curated bootstrap docs still describe older releases and legacy docs paths as current (`docs_gathered/01_README_project.md:1-29`; `docs_gathered/29_improvement_axes_and_version_history.md:68-72`).
7. `[Iteration 1: baseline]` Direct-root bootstrap and harness installs still expose different effective Phase 1 docs trees (`repos/setup_repos.sh:216-220`; `docs_gathered/INDEX.md:1-37`).

### [Iteration 2: gap] Install-location fallback coverage the baseline left thin

8. `[Iteration 2: gap]` The fallback guide exists centrally in `SKILL_FALLBACK_GUIDE`, but only the entry prompts use it; Phase 2 through Phase 6 still hardcode `.github/skills/SKILL.md` and `.github/skills/references/...` (`bin/run_playbook.py:613-618`, `726-1090`).
9. `[Iteration 2: gap]` Repository-side install detection still uses an outdated search tuple that prefers flat Copilot before repo root and omits the nested Copilot path from warning text (`bin/benchmark_lib.py:42-47`, `144-164`; `bin/run_playbook.py:592-597`).
10. `[Iteration 2: gap]` The generic and Claude orchestrator agents disagree on Copilot fallback order, so the same shipped product teaches different first-hit semantics (`agents/quality-playbook.agent.md:37-45`; `agents/quality-playbook-claude.agent.md:45-54`).

### [Iteration 3: unfiltered] Gate-, citation-, and orchestration-runtime drift the baseline and gap iterations did not read

11. `[Iteration 3: unfiltered]` `verify_citation()` reads `Path(root) / source_path` with no boundary check, so a tampered manifest or auditor-supplied citation can read files outside the repo root (`bin/citation_verifier.py:244-266`).
12. `[Iteration 3: unfiltered]` The gate's `bug_count` formula at `.github/skills/quality_gate.py:824` omits `deep_headings` from the downstream coverage anchor, so `#### BUG-NNN` headings under-count expected sidecar / log entries.
13. `[Iteration 3: unfiltered]` The gate's per-bug field check uses `>=` instead of `==`, so a stale or merged `tdd-results.json` carrying excess bug entries silently passes (`.github/skills/quality_gate.py:875-883`).
14. `[Iteration 3: unfiltered]` The gate validates summary-key presence but never key values, so non-sensical totals (`total: 100, verified: -5`) PASS (`.github/skills/quality_gate.py:894-901`).
15. `[Iteration 3: unfiltered]` `bug_ids` is regex-extracted from the entire BUGS.md file, so prose mentions of historical bug IDs inflate the expected red-log set (`.github/skills/quality_gate.py:826-831`).
16. `[Iteration 3: unfiltered]` `check_run_metadata()` emits `pass_("run-metadata JSON present")` after the per-file loop, so a parse error or missing field PASSes the "present" sub-check while FAILing the field sub-check (`.github/skills/quality_gate.py:1538-1562`).
17. `[Iteration 3: unfiltered]` `_extract_first_json_array()` uses a greedy `\[[\s\S]*\]` regex; a model response with prose plus the JSON array trips greedy capture and reports "no JSON array" instead of recovering (`bin/council_semantic_check.py:319-343`).
18. `[Iteration 3: unfiltered]` Empty `reviews[]` in `quality/citation_semantic_check.json` is ambiguous — Spec Gap and "all auditors unavailable" produce identical manifests (`bin/council_semantic_check.py::write_semantic_check`).
19. `[Iteration 3: unfiltered]` Run-level timestamps mix naive local time (log filenames, archive keys) with UTC (PROGRESS.md heartbeat) inside one run (`bin/run_playbook.py:2964`, `2412-2415`).
20. `[Iteration 3: unfiltered]` The 1-second timestamp resolution at `bin/run_playbook.py:2964` allows two runs starting in the same second to overwrite each other's logs and archive keys (`bin/archive_lib.py:358`).
21. `[Iteration 3: unfiltered]` `reference_docs_ingest._iter_candidates()` follows symlinks via `is_file()`, so a symlink under `reference_docs/cite/` can ingest content from outside the project tree.

### [Iteration 5: adversarial] Re-investigated previously dismissed candidates and challenged SATISFIED verdicts

28. `[Iteration 5: adversarial]` Re-confirmed BUG-011 candidate from iteration 3 with fresh code-trace and reduced reproduction; promoted to BUG-011 in this iteration with REQ-011 added to support the bug (`bin/citation_verifier.py:244-266`; `quality/REQUIREMENTS.md:328-346`).
29. `[Iteration 5: adversarial]` Re-confirmed BUG-012 (gate `bug_count` drops `deep_headings`), BUG-013 (`>=` vs `==` in TDD sidecar), BUG-014 (sidecar summary value sanity), BUG-015 (`bug_ids` regex inflated by prose), BUG-016 (`pass_("run-metadata JSON present")` after possibly-failing per-file validation), BUG-018 (Spec Gap vs council outage manifest ambiguity), BUG-021 (`_iter_candidates()` symlink boundary), BUG-022 (phase prompts split PROGRESS.md authorship contract), BUG-023 (Phase 5 prompt missing closed-set enums), BUG-024 (Phase 2 entry contract enforced by four non-nesting subsets), BUG-025 (non-atomic JSON manifest writes) as adversarial-confirmed candidates with fresh code traces. Each remains a pending candidate for future iteration cycles.
30. `[Iteration 5: adversarial]` Re-checked DC-001 through DC-007 against their re-promotion criteria; each FALSE POSITIVE verdict sustained with fresh code reads (`bin/run_playbook.py:2388-2410, 2826-2833, 3007-3018`; `agents/quality-playbook.agent.md:37-45, 106`; `agents/quality-playbook-claude.agent.md:88`).
31. `[Iteration 5: adversarial]` Challenged the REQ-001 SATISFIED verdict in the Phase 3 review. The mechanical `quality/mechanical/skill_entry_hashes.txt` only hashes two paths (repo-root `SKILL.md` and `.github/skills/SKILL.md`, the latter a symlink to the former), so the SATISFIED finding is trivially proven by a single artifact rather than parity across alternative installs. Sustained as SATISFIED with hardening recommendation: strengthen the mechanical contract to cover all four documented install paths and assert byte-copy parity (not symlink parity) when independent file copies exist.

### [Iteration 4: parity] Cross-path drift the baseline / gap / unfiltered iterations did not diff

22. `[Iteration 4: parity]` Phase prompts split the PROGRESS.md authorship contract: only `iteration_prompt` teaches the orchestrator-vs-iteration-section authorship boundary, while `phase2_prompt` through `phase6_prompt` only teach the checkbox-format rule (`bin/run_playbook.py:749, 905, 961, 1080, 1107, 1127-1134`).
23. `[Iteration 4: parity]` Phase 5 prompt names the `verdict` and `recommendation` fields without enumerating their closed-set values, while `phase4_prompt` enumerates the verdict closed-set inline (`bin/run_playbook.py:948, 1060`; contract source `SKILL.md:160-178`).
24. `[Iteration 4: parity]` Four enforcers cover the Phase 2 entry contract — runtime gate, mechanical contract file, terminal gate, and SKILL.md spec — and each covers a different non-nesting subset of the spec's 13 criteria (`bin/run_playbook.py:1158-1165`, `quality/mechanical/phase2_gate_required_headings.txt:1-8`, `.github/skills/quality_gate.py:1521-1527`, `SKILL.md:1026-1042`).
25. `[Iteration 4: parity]` Two gate-validated manifests (`citation_semantic_check.json`, `formal_docs_manifest.json`) write through `path.write_text(...)` with no atomic rename, while sibling Phase 2 helpers use `.tmp` + `os.replace()` (`bin/council_semantic_check.py:407-410`, `bin/reference_docs_ingest.py:296-299`, `bin/skill_derivation/pass_d.py:401-406`).
26. `[Iteration 4: parity]` Setup writes `run_timestamp` in `%Y%m%d-%H%M%S` form, but the conversion helper `extended_from_compact()` only matches `%Y%m%dT%H%M%SZ` and silently returns the input unchanged, so the live INDEX records a non-ISO 8601 string for both `run_timestamp_start` and `run_timestamp_end` (`bin/run_playbook.py:2964, 3103, 1806, 1820-1821, 1896-1899`; `bin/archive_lib.py:67-97`).
27. `[Iteration 4: parity]` Both shipped orchestrator agents teach a narrower references/ resolution rule than `SKILL.md:49-58`, and the Claude agent additionally omits the file-list / count check that the generic agent performs against `references/` (`agents/quality-playbook.agent.md:44`, `agents/quality-playbook-claude.agent.md:54`).

## Quality Risks

1. `[Iteration 1: baseline]` Modern installs can still be mislabeled as code-only, weakening operator trust in the evidence baseline.
2. `[Iteration 1: baseline]` Later phases can still inherit malformed exploration or incorrect project-type metadata while appearing successful.
3. `[Iteration 1: baseline]` Install-time packaging can still silently degrade citation verification or direct-root self-audit inputs.
4. `[Iteration 2: gap]` A run can be portable at Phase 1 entry and then become non-portable when later-phase prompts redirect the child to a flat Copilot-only path.
5. `[Iteration 2: gap]` Operators and orchestrators can get contradictory answers about which SKILL path is canonical because helper code and agent docs enumerate different orders.
6. `[Iteration 3: unfiltered]` Citation verification reads files outside the repo when manifests or auditor responses are tampered with, turning a verification step into an inadvertent file-read primitive.
7. `[Iteration 3: unfiltered]` Cross-artifact bug-count cross-checks at the gate accept divergent counts and shape-only summaries, so a sidecar-vs-BUGS.md drift can pass undetected.
8. `[Iteration 3: unfiltered]` Council Layer-2 manifests collapse two distinct outcomes (Spec Gap and total auditor failure) into one shape, hiding council outages.
9. `[Iteration 3: unfiltered]` Run identifiers mix timezones and round to one second, so multi-run correlation (and concurrent-run isolation) is unreliable.
10. `[Iteration 4: parity]` Phase agents and iteration agents are taught different slices of the PROGRESS.md authorship contract, so multi-agent runs can interleave incompatible writes against the phase tracker and iteration heartbeat.
11. `[Iteration 4: parity]` Phase 5 sub-agents are not constrained to a closed verdict / recommendation enum, while Phase 4 sub-agents are — so TDD and integration sidecars can ship typo'd values that silently pass the gate.
12. `[Iteration 4: parity]` The Phase 2 entry contract has four enforcers covering different subsets of the spec's 13 criteria, so under-enforcement is invisible: any single enforcer can pass while several spec criteria are silently never checked.
13. `[Iteration 4: parity]` Top-level gate-validated JSON manifests are written without atomic rename, so a signal during Phase 1 ingest or Phase 4 assembly can leave a corrupt JSON file that fails the next gate run with a generic parse error.
14. `[Iteration 4: parity]` Setup-side run identifiers are produced in a format the archive-helper conversion regex does not recognise, so the live `quality/INDEX.md` records a non-ISO 8601 timestamp; consumers that try to parse the live INDEX as ISO 8601 fail.
15. `[Iteration 4: parity]` The two shipped orchestrator agents teach a narrower `references/` resolution rule than `SKILL.md:49-58` and disagree on whether to verify the references file set, so non-standard installs degrade silently under the Claude agent and partially under the generic agent.
16. `[Iteration 5: adversarial]` A tampered `quality/formal_docs_manifest.json` or hostile auditor citation can turn the Layer 1 verifier into an out-of-tree file-read primitive because `verify_citation()` skips repository-root containment before `read_bytes()` (`bin/citation_verifier.py:244-266`).

## Candidate Bugs for Phase 2

### BUG-001 candidate — docs_present ignores populated reference_docs trees

- **Source:** [Iteration 1: baseline]
- **Evidence:** `bin/run_playbook.py:1552-1622`
- **Disposition:** Confirmed in baseline as BUG-001.

### BUG-002 candidate — Phase 2 gate accepts line-count placeholders instead of the written exploration contract

- **Source:** [Iteration 1: baseline]
- **Evidence:** `bin/run_playbook.py:1152-1165`; `SKILL.md:1026-1042`
- **Disposition:** Confirmed in baseline as BUG-002.

### BUG-003 candidate — Live INDEX writers collapse non-Code classifications to Code

- **Source:** [Iteration 1: baseline]
- **Evidence:** `bin/run_playbook.py:1819-1895`; `bin/classify_project.py:261-286`
- **Disposition:** Confirmed in baseline as BUG-003.

### BUG-004 candidate — Cleanup without PID files widens to workstation-wide pkill patterns

- **Source:** [Iteration 1: baseline]
- **Evidence:** `bin/run_playbook.py:2807-2875`
- **Disposition:** Confirmed in baseline as BUG-004.

### BUG-005 candidate — Installed gate copy omits the citation verifier dependency

- **Source:** [Iteration 1: baseline]
- **Evidence:** `repos/setup_repos.sh:195-200`; `.github/skills/quality_gate/quality_gate.py:32-44`
- **Disposition:** Confirmed in baseline as BUG-005.

### BUG-006 candidate — Curated bootstrap docs still present older releases and legacy docs paths as current

- **Source:** [Iteration 1: baseline]
- **Evidence:** `docs_gathered/01_README_project.md:1-29`; `docs_gathered/29_improvement_axes_and_version_history.md:68-72`
- **Disposition:** Confirmed in baseline as BUG-006.

### BUG-007 candidate — Direct-root bootstrap exposes an empty reference_docs tree while harness installs mirror the curated docs set

- **Source:** [Iteration 1: baseline]
- **Evidence:** `repos/setup_repos.sh:216-220`; `docs_gathered/INDEX.md:1-37`
- **Disposition:** Confirmed in baseline as BUG-007.

### BUG-008 candidate — later-phase prompts still hardcode the flat Copilot layout

- **Source:** [Iteration 2: gap]
- **Evidence:** `phase2_prompt()` through `phase6_prompt()` direct children to `.github/skills/SKILL.md` and `.github/skills/references/...` instead of the documented fallback list (`bin/run_playbook.py:726-752`, `755-908`, `911-1090`; `SKILL.md:49-58`).
- **Disposition:** Promoted in gap iteration as BUG-008.

### BUG-009 candidate — repository-side skill detection still walks an outdated fallback list

- **Source:** [Iteration 2: gap]
- **Evidence:** `benchmark_lib.SKILL_INSTALL_LOCATIONS` prefers flat Copilot before repo root, and `resolve_target_dirs()` warning text omits the nested Copilot path entirely (`bin/benchmark_lib.py:42-47`, `144-164`; `bin/run_playbook.py:592-597`).
- **Disposition:** Promoted in gap iteration as BUG-009.

### BUG-010 candidate — the Claude orchestrator reverses the two Copilot fallback positions

- **Source:** [Iteration 2: gap]
- **Evidence:** `agents/quality-playbook-claude.agent.md:47-54` lists nested Copilot before flat Copilot, contradicting `SKILL.md:49-58` and `agents/quality-playbook.agent.md:37-45`.
- **Disposition:** Promoted in gap iteration as BUG-010.

### BUG-011 candidate — `verify_citation()` allows path traversal outside the repo root

- **Source:** [Iteration 3: unfiltered]; re-confirmed and promoted in [Iteration 5: adversarial].
- **Evidence:** `bin/citation_verifier.py:244-266`. `doc_path = Path(root) / source_path` with no `is_relative_to(root)` check; `source_path` flows from `formal_docs_manifest.json` (manifest tampering) or auditor-supplied citation records. Reduced reproduction in `quality/EXPLORATION_ITER5.md` finding A-1 confirms `read_bytes()` succeeds against an out-of-root absolute path and that `extract_excerpt(..., line=1)` returns the out-of-root content as a "valid" excerpt.
- **Severity:** HIGH
- **Disposition:** Promoted to **BUG-011** in iteration 5 (adversarial). REQ-011 added to support the bug. See `quality/BUGS.md` and `quality/test_regression.py::CodeReviewRegressionTests.test_bug_011_citation_verifier_rejects_out_of_root_paths`.

### BUG-012 candidate — gate's `bug_count` drops `#### BUG-NNN` headings from the downstream coverage anchor

- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `.github/skills/quality_gate.py:802-829`. The two arms of the count branch are asymmetric (line 821 includes `deep_headings`; line 824 omits it).
- **Severity:** MEDIUM
- **Disposition:** New in iteration 3 — pending Phase 2 promotion.

### BUG-013 candidate — TDD sidecar per-bug field check accepts excess entries via `>=`

- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `.github/skills/quality_gate.py:875-883`. `if fcount >= bug_count: pass_` lets a sidecar with more bug entries than BUGS.md silently pass.
- **Severity:** MEDIUM
- **Disposition:** New in iteration 3 — pending Phase 2 promotion.

### BUG-014 candidate — TDD sidecar `summary` values are checked for presence but never sanity

- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `.github/skills/quality_gate.py:894-901`. The loop only checks `if skey in summary`; values can be negative, exceed `total`, or contradict the per-bug verdict count without failing.
- **Severity:** MEDIUM
- **Disposition:** New in iteration 3 — pending Phase 2 promotion.

### BUG-015 candidate — gate's `bug_ids` is collected from the whole BUGS.md body, inflating expected red-log set

- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `.github/skills/quality_gate.py:826-831` plus downstream `check_tdd_logs()` at ~line 953. `re.findall` runs over the full file, so a casual prose mention of `BUG-099` adds it to `bug_ids`.
- **Severity:** LOW
- **Disposition:** New in iteration 3 — pending Phase 2 promotion.

### BUG-016 candidate — `check_run_metadata` emits `pass_("run-metadata JSON present")` after possibly-failing per-file validation

- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `.github/skills/quality_gate.py:1538-1562`. The terminal `pass_()` runs unconditionally after the loop, so a parse-error file produces both a FAIL and a PASS for the same artifact.
- **Severity:** LOW
- **Disposition:** New in iteration 3 — pending Phase 2 promotion.

### BUG-017 candidate — greedy `\[[\s\S]*\]` regex breaks JSON-array extraction from mixed-prose model responses

- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/council_semantic_check.py:319-343`. Responses with prose around or after the array trigger greedy capture; `json.loads` fails and the function returns None instead of recovering with a non-greedy or balanced parse.
- **Severity:** LOW–MEDIUM
- **Disposition:** New in iteration 3 — pending Phase 2 promotion.

### BUG-018 candidate — empty `reviews[]` in `citation_semantic_check.json` is ambiguous between Spec Gap and auditor failure

- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/council_semantic_check.py::write_semantic_check` writes `reviews=[]` for both the zero-Tier-1/2 case and the all-auditors-unavailable case; the gate's invariant on the manifest cannot distinguish them.
- **Severity:** MEDIUM
- **Disposition:** New in iteration 3 — pending Phase 2 promotion.

### BUG-019 candidate — runner timestamps mix naive local time (filenames) with UTC (PROGRESS.md heartbeat)

- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/run_playbook.py:2964` and `bin/run_playbook.py:3103` use `datetime.now()` (naive local); `bin/run_playbook.py:2412-2415` uses `datetime.now(timezone.utc)`. Both timestamps appear in artifacts produced by the same run.
- **Severity:** MEDIUM
- **Disposition:** New in iteration 3 — pending Phase 2 promotion.

### BUG-020 candidate — `"%Y%m%d-%H%M%S"` 1-second resolution allows two parallel runs to overwrite each other's logs

- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/run_playbook.py:2964` and `bin/run_playbook.py:3103` round timestamps to one second; `bin/archive_lib.py:358` collates archives by `run-{timestamp}` keys, so collisions silently overwrite the earlier run's log and archive key.
- **Severity:** LOW–MEDIUM
- **Disposition:** New in iteration 3 — pending Phase 2 promotion.

### BUG-021 candidate — `reference_docs_ingest._iter_candidates()` ingests symlinks via `is_file()`, breaking project-tree boundary

- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/reference_docs_ingest.py::_iter_candidates()` filters with `p.is_file()` (which follows symlinks) and never calls `p.is_symlink()` or resolves against root.
- **Severity:** MEDIUM
- **Disposition:** New in iteration 3 — pending Phase 2 promotion.

### BUG-022 candidate — phase prompts split the PROGRESS.md authorship contract

- **Source:** [Iteration 4: parity]
- **Evidence:** Only `iteration_prompt` (`bin/run_playbook.py:1127-1134`) teaches the orchestrator-vs-iteration authorship boundary; `phase2_prompt` through `phase6_prompt` (`bin/run_playbook.py:749, 905, 961, 1080, 1107`) teach only the checkbox-format rule, leaving phase agents unconstrained against rewriting `## Iteration: ...` sections.
- **Severity:** LOW–MEDIUM
- **Disposition:** New in iteration 4 — pending Phase 2 promotion.

### BUG-023 candidate — Phase 5 prompt does not enumerate verdict / recommendation closed-sets while Phase 4 prompt does

- **Source:** [Iteration 4: parity]
- **Evidence:** `phase4_prompt` enumerates inline at `bin/run_playbook.py:948` ("verdict (supports|overreaches|unclear)"); `phase5_prompt` at `bin/run_playbook.py:1060` lists `verdict` and `recommendation` as field names but omits the closed-sets specified in `SKILL.md:160-178` ({"TDD verified", "red failed", "green failed", "confirmed open", "deferred"} for verdict; {"SHIP", "FIX BEFORE MERGE", "BLOCK"} for recommendation).
- **Severity:** MEDIUM
- **Disposition:** New in iteration 4 — pending Phase 2 promotion.

### BUG-024 candidate — Phase 2 entry contract enforced by four enforcers covering non-nesting subsets of the 13 spec criteria

- **Source:** [Iteration 4: parity]
- **Evidence:** Spec at `SKILL.md:1026-1042` defines 13 criteria. Runtime gate at `bin/run_playbook.py:1158-1165` enforces criterion 1 only (line floor + existence). Mechanical contract at `quality/mechanical/phase2_gate_required_headings.txt:1-8` enforces criteria 1, 2, 3, 4, 6, 7, 8, 13 (skips 5 and 9-12). Terminal gate at `.github/skills/quality_gate.py:1521-1527` enforces criteria 2, 3, 4, 6, 7 (no line floor, no Pattern Deep Dive count, no content-depth checks). The four subsets do not nest; criteria 9-12 (content depth) are silently never enforced. BUG-002 covers the runtime-gate slice; the parity bug here is the four-way spread.
- **Severity:** MEDIUM
- **Disposition:** New in iteration 4 — pending Phase 2 promotion.

### BUG-025 candidate — gate-validated JSON manifests written non-atomically

- **Source:** [Iteration 4: parity]
- **Evidence:** `bin/council_semantic_check.py:407-410` and `bin/reference_docs_ingest.py:296-299` both call `path.write_text(json.dumps(...) + "\n", ...)` directly with no `.tmp` + `os.replace()` rename. Both files are top-level gate-validated artifacts (`SKILL.md:94, 98`). Sibling Phase 2 helpers at `bin/skill_derivation/pass_d.py:401-406` already use the atomic-write pattern, so the parity gap is internal to the codebase.
- **Severity:** LOW–MEDIUM
- **Disposition:** New in iteration 4 — pending Phase 2 promotion.

### BUG-026 candidate — setup-side `run_timestamp` format incompatible with `extended_from_compact()`

- **Source:** [Iteration 4: parity]
- **Evidence:** `bin/run_playbook.py:2964` and `:3103` use `datetime.now().strftime("%Y%m%d-%H%M%S")` (e.g., `20260428-131715`). `bin/archive_lib.py:67-97` defines `utc_compact_timestamp()` → `%Y%m%dT%H%M%SZ` and `extended_from_compact()` whose regex matches only the compact-with-T-and-Z form, returning input unchanged otherwise. The live INDEX writers at `bin/run_playbook.py:1806, 1820-1821, 1896-1899` therefore record `run_timestamp_start` and `run_timestamp_end` as non-ISO 8601 strings. Three timestamp formats are live in one run.
- **Severity:** LOW
- **Disposition:** New in iteration 4 — pending Phase 2 promotion.

### BUG-027 candidate — orchestrator agents teach narrower references/ resolution and unequal verification rigor

- **Source:** [Iteration 4: parity]
- **Evidence:** `SKILL.md:49-58` requires references/ to walk the same four-path fallback as SKILL.md. `agents/quality-playbook.agent.md:44` teaches only "Also check for a `references/` directory alongside SKILL.md" but lists 11 expected files and verifies "at least 6 .md files". `agents/quality-playbook-claude.agent.md:54` teaches the alongside-only rule and adds no file-list / count check. Both agents narrower than spec; the Claude agent narrower than the generic agent.
- **Severity:** LOW
- **Disposition:** New in iteration 4 — pending Phase 2 promotion.

## Demoted Candidates

### DC-001: iteration heartbeat rewrites the phase tracker

- **Source:** [Iteration 2: gap]
- **Dismissal reason:** direct code read showed `_append_iteration_heartbeat()` is append-only and does not rewrite existing tracker lines.
- **Code location:** `bin/run_playbook.py:2388-2408`
- **Re-promotion criteria:** show a concrete code path where the heartbeat helper truncates or rewrites the existing `## Phase tracker` block instead of appending a new `## Iteration: ...` section.
- **Status:** FALSE POSITIVE [Iteration 2: gap]; **sustained FALSE POSITIVE in [Iteration 5: adversarial]** — `_append_iteration_heartbeat` opens `progress_path` in mode `"a"` (append-only) and writes `line + "\n"`; both call sites at `bin/run_playbook.py:2639-2642, 2673-2677` prefix the line with `\n`.

### DC-002: the generic orchestrator fails to document the nested Copilot path

- **Source:** [Iteration 2: gap]
- **Dismissal reason:** the general orchestrator already lists all four documented paths in the canonical order.
- **Code location:** `agents/quality-playbook.agent.md:37-45`
- **Re-promotion criteria:** show a shipped orchestrator revision where the general agent drops one of the four paths or reorders them against `SKILL.md`.
- **Status:** FALSE POSITIVE [Iteration 2: gap]

### DC-003: `_append_iteration_heartbeat` corrupts PROGRESS.md when the file lacks a trailing newline

- **Source:** [Iteration 3: unfiltered]
- **Dismissal reason:** every call site (lines 2639-2642 and 2673-2677) prefixes the line with `\n`, so the appended block always starts on its own line regardless of the file's prior trailing-newline state. `mkdir(parents=True, exist_ok=True)` plus append-mode open also covers the missing-file case.
- **Code location:** `bin/run_playbook.py:2388-2410` and call sites at 2639-2677.
- **Re-promotion criteria:** show a call site that passes a non-newline-prefixed line, or a path where `progress_path` is opened in mode other than `"a"`, or a call that overwrites the file in-place.
- **Status:** FALSE POSITIVE [Iteration 3: unfiltered]

### DC-004: `--iterations` early-stop ignores user's explicit list

- **Source:** [Iteration 3: unfiltered]
- **Dismissal reason:** `_mark_iterations_explicit(argv)` is called at `bin/run_playbook.py:450` and stores its result on `args._iterations_explicit`. Tests in `bin/tests/test_iterations_explicit.py` exercise the parsing for both split and combined token forms (`--strategy adversarial`, `--strategy=parity,adversarial`, etc.).
- **Code location:** `bin/run_playbook.py:414-450`, `bin/run_playbook.py:2690`, `bin/run_playbook.py:2755`.
- **Re-promotion criteria:** show a CLI shape (or a future flag spelling) that bypasses `_mark_iterations_explicit` so the early-stop fires despite an explicit user list.
- **Status:** FALSE POSITIVE [Iteration 3: unfiltered]

### DC-005: PID file lifecycle drift between sequential and parallel modes

- **Source:** [Iteration 4: parity]
- **Dismissal reason:** `write_pid_file()` at `bin/run_playbook.py:2826-2833` is only invoked from the parallel dispatcher path at `:3007-3008`. The sequential dispatcher at `:3017-3018` calls `run_one()` directly with no PID file management. Sequential mode does not create a PID file, so it cannot leak one. The "leak" hypothesis confused "no PID file in sequential mode" with "PID file leaked in sequential mode."
- **Code location:** `bin/run_playbook.py:38, 2826-2833, 3007-3008, 3017-3018`.
- **Re-promotion criteria:** show a code path where the sequential dispatcher writes a PID file that subsequent cleanup never removes; or show a sequential code path where `--kill` is expected to find a sequential PID file that was never written.
- **Status:** FALSE POSITIVE [Iteration 4: parity]; **sustained FALSE POSITIVE in [Iteration 5: adversarial]** — re-read confirmed sequential dispatcher takes the no-PID-file path.

### DC-006: `citation_semantic_check.json` and `formal_docs_manifest.json` omit `skill_version`

- **Source:** [Iteration 4: parity]
- **Dismissal reason:** SKILL.md:1091-1103 specifies that manifest files (including `citation_semantic_check.json` per §9.1 and `formal_docs_manifest.json`) use the §1.6 wrapper with `schema_version` (which equals the skill's `metadata.version` at generation time) and `generated_at` only. Sidecars (`tdd-results.json`, `integration-results.json`) use a separate two-version convention (`schema_version` + `skill_version`). The two manifest writers correctly follow the manifest convention.
- **Code location:** `bin/council_semantic_check.py:393-405`, `bin/reference_docs_ingest.py:284-299`, `SKILL.md:1091-1103, 138-178`.
- **Re-promotion criteria:** show that SKILL.md or schemas.md actually requires `skill_version` to appear in `citation_semantic_check.json` or `formal_docs_manifest.json`.
- **Status:** FALSE POSITIVE [Iteration 4: parity]

### DC-007: iteration ask-user gating diverges between agents

- **Source:** [Iteration 4: parity]
- **Dismissal reason:** both agents instruct the orchestrator to ask the user before running iterations. `agents/quality-playbook.agent.md:106` ("After Phase 6 completes, report the full results and ask if the user wants to run iteration strategies"); `agents/quality-playbook-claude.agent.md:88` ("After Phase 6, ask if the user wants iterations"). Wording differs; contract is the same.
- **Code location:** `agents/quality-playbook.agent.md:106`, `agents/quality-playbook-claude.agent.md:88`.
- **Re-promotion criteria:** show a shipped agent revision where one orchestrator runs iterations without asking and the other does ask.
- **Status:** FALSE POSITIVE [Iteration 4: parity]; **sustained FALSE POSITIVE in [Iteration 5: adversarial]** — both agents still instruct the orchestrator to ask the user.

### DC-008: REQ-001 SATISFIED verdict over-trusts symlink-based parity

- **Source:** [Iteration 5: adversarial] Pool C (Pass 2 SATISFIED challenge).
- **Dismissal reason:** the SATISFIED verdict is technically correct for the shipped product. Repo-root `SKILL.md` and `.github/skills/SKILL.md` are byte-identical because the latter is a symlink to the former; the documented two non-existent install paths cannot be hash-checked. Not promoted to a new BUG.
- **Code location:** `quality/code_reviews/2026-04-28-phase3-review.md` Pass 2 REQ-001; `quality/mechanical/skill_entry_hashes.txt:1-2`; symlink target in repo `.github/skills/SKILL.md` → `../../SKILL.md`.
- **Re-promotion criteria:** strengthen the mechanical contract to hash all four documented install paths if they exist (and record their absence explicitly when they don't); or demonstrate a non-symlink install path where two byte-independent files diverge in shipped artifacts. Either condition would make REQ-001's parity claim non-trivial.
- **Status:** SATISFIED-WITH-CAVEATS [Iteration 5: adversarial]. Logged as a hardening recommendation rather than a BUG.
