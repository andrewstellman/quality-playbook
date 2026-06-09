**Heartbeat (v1.5.9):** Before any Phase 4 work, emit `python3 -m bin.qpb_heartbeat emit --mode-a-noop --phase "Phase 4" --step start --status STARTING`. After all phase work completes and before yielding control, emit the same call with `--step complete --status COMPLETED`. Emit `--status IN_PROGRESS` heartbeats every ~3 min mid-phase. See SKILL.md § Heartbeat emission contract for invocation, env-var, and Mode A no-op detail.

{skill_fallback_guide}

You are a quality engineer continuing a phase-by-phase quality playbook run. Phases 1-3 are complete.

Read these files to get context:
1. quality/PROGRESS.md - run metadata, phase status, BUG tracker
2. quality/REQUIREMENTS.md - derived requirements
3. quality/BUGS.md - bugs found in Phase 3 (code review)
4. SKILL.md - read the Phase 4 section ("Phase 4: Spec Audit and Triage"). Also read references/spec_audit.md. Resolve SKILL.md and the references/ directory via the documented fallback list above; do NOT assume any single install layout.

Execute Phase 4: Spec Audit + Triage + Layer-2 semantic citation check.

Part A — spec audit:
Run the spec audit per quality/RUN_SPEC_AUDIT.md. Produce:
- Individual auditor reports at quality/spec_audits/YYYY-MM-DD-auditor-N.md (one per auditor)
- Triage synthesis at quality/spec_audits/YYYY-MM-DD-triage.md
- Executable triage probes at quality/spec_audits/triage_probes.sh
- Regression tests and patches for any net-new spec audit bugs
- Update BUGS.md and PROGRESS.md BUG tracker with any new findings

**Precision guardrails apply to net-new spec-audit bugs** (v1.5.7 090j; see references/challenge_gate.md "Precision guardrails"): every HIGH/MEDIUM bug emerging from the spec audit MUST carry a `reachability_analysis` field (D1); a CVE-cited bug must carry `cve_reference` + `cve_version_applies` (D3) and may need `classification: known-issue` if the audit did not independently locate the in-tree defect (D2). The Phase 6 gate enforces these via `check_v1_5_7_090j_triage_precision`.

Part B — Layer-2 semantic citation check (v1.5.1):
The gate requires three Council members to
vote on each Tier 1/2 REQ's citation_excerpt. Execute these steps:

1. Generate per-Council-member prompts:
     python3 -m bin.quality_playbook semantic-check plan .
   This writes one or more prompt files to
   quality/council_semantic_check_prompts/<member>.txt per member in the
   Council roster (bin/council_config.py: claude-opus-4.7, gpt-5.5,
   claude-sonnet-4.6). For >15 Tier 1/2 REQs, prompts are split into
   batches of 5 (<member>-batch<N>.txt).
   If no Tier 1/2 REQs exist (Spec Gap run), this step writes an empty
   quality/citation_semantic_check.json directly — skip steps 2-4.

2. For each Council member's prompt file, feed the prompt to that model
   (the same roster that ran Part A) and capture its JSON-array response
   to quality/council_semantic_check_responses/<member>.json. If the
   member was batched, concatenate the per-batch responses into a single
   array in the response file. Every entry must have req_id, verdict
   (supports|overreaches|unclear), and reasoning.

3. Assemble the semantic-check output:
     python3 -m bin.quality_playbook semantic-check assemble . \
       --member claude-opus-4.7  --response quality/council_semantic_check_responses/claude-opus-4.7.json \
       --member gpt-5.5          --response quality/council_semantic_check_responses/gpt-5.5.json \
       --member claude-sonnet-4.6 --response quality/council_semantic_check_responses/claude-sonnet-4.6.json
   This writes quality/citation_semantic_check.json with the assembled per-REQ verdicts (a `{schema_version, generated_at, reviews[]}` wrapper carrying one entry per Tier 1/2 REQ).

4. Verify the output file exists. Phase 6's gate invariant #17 requires
   it on every Tier 1/2 run.

Mark Phase 4 (Spec audit + triage + semantic check) complete in PROGRESS.md (use the checkbox format `- [x] Phase 4 - Spec Audit` — the Phase 5 entry gate looks for that exact substring and will abort if it finds a table row or any other layout).

IMPORTANT: Do NOT proceed to Phase 5 (reconciliation). The next phase will handle reconciliation and TDD.

After completing this phase, emit `## What just happened` + `### What to do next` as the LAST visible output in chat per the decision tree at `references/what_just_happened.md`. Use the State P4 template (Phase 4 just completed; next is Phase 5).
