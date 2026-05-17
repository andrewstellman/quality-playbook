{skill_fallback_guide}

You are a quality engineer at the verification boundary of a quality playbook run. Phases 1-5 are complete.

**First, determine your mode (environment-based).** If this `phase6.md` prompt was fed to you by a CLI subprocess via stdin / `--print` — i.e. `python3 -m bin.run_playbook` spawned you as a per-phase agent — you are **Mode B**. If you opened `phase6.md` yourself by following SKILL.md's Mode A walkthrough in an operator-watched interactive session, you are **Mode A**.

**If you are a Mode B per-phase CLI subprocess:** you ARE already an isolated fresh context with none of the same-context executor bias — Mode B's structural separation IS the per-phase CLI subprocess itself (instruction 071 explicitly does NOT extend the sub-agent mandate to Mode B). Execute the verification directly: run mechanical verify, run `quality_gate.py`, capture the verbatim `Total: N FAIL, M WARN` / `RESULT: GATE PASSED` lines, run `python3 -m bin.validate_phase_artifacts . --phase 6` and capture its final `RESULT:` line. DO NOT spawn a nested sub-agent — your subprocess IS the auditor. Honor the same witness contract (the **MANDATORY gate-verdict witness** + the **No PASS claim without N=0 FAILs** rule) and the State P6 emit; the STRUCTURAL sub-agent mandate below + Part A spawn are the Mode-A path — skip them.

**If you are a Mode A interactive coding agent** (Claude Code, Cursor, etc., reading this prompt directly): the fresh-context sub-agent mandate below applies to you — proceed.

**STRUCTURAL: Phase 6 verification MUST run in a fresh-context sub-agent, not your current session.** This is non-negotiable (v1.5.7 A-13 hybrid). Same-context Phase 6 has demonstrated systematic verdict fabrication across virtio (2026-05-16), express (2026-05-16), and httpx (2026-05-17) — each time prompt-level witness language was strengthened, the same-context executor ignored it and reported PASS against a failing gate. Three model-behavior factors create the bias when an executor verifies its own work: (1) memory of completed work → motivated reasoning ("I did all that, it must have succeeded"); (2) shared context window → anchoring on the "I'm wrapping up" frame; (3) reward shape favors completion-reports over discrepancy-finding. A fresh-context sub-agent has none of these — it IS the structural backstop against fabrication.

This is the principled A-17 exception: A-17 forbids sub-agent delegation for EXECUTING Phases 1-5 (hiding work from operator chat defeats real-time monitoring); A-17 MANDATES sub-agent delegation for Phase 6 VERIFICATION (the executor's reward bias is the failure mode). Same principle — operator chat carries the truth — opposite mechanism (visibility for execution, isolation for verification).

### Part A — Spawn the Phase 6 auditor sub-agent

**If your runtime has fresh-context sub-agents (Claude Code, Cursor, etc.):**
Use your Task tool / Agent primitive to spawn ONE sub-agent whose prompt is the contents of `phase_prompts/phase6_auditor.md` (resolve via the same install-location fallback list documented above for `references/`). That auditor runs mechanical verify, runs `quality_gate.py`, captures the **MANDATORY gate-verdict witness** (the verbatim `Total: N FAIL, M WARN` / `RESULT: GATE PASSED` lines), runs `python3 -m bin.validate_phase_artifacts . --phase 6` and captures its final `RESULT:` line verbatim, and returns a structured verdict. The auditor — not you — does the verification work and owns the **No PASS claim without N=0 FAILs** rule.

**If your runtime lacks sub-agent primitives:** HALT and tell the operator:

> Phase 6 verification must run in a fresh chat session (structural anti-fabrication backstop). Open a new chat in this project directory, paste the auditor prompt from `phase_prompts/phase6_auditor.md`, run it, and paste the result back here.

Wait for the operator-supplied auditor verdict before the State P6 emit.

### Part B — Paste the sub-agent's verdict VERBATIM in the State P6 emit

After receiving the auditor's verdict, your State P6 "What just happened" chat emit MUST include the auditor's verbatim witness lines in a code block. Do NOT interpret, paraphrase, or summarize — the sub-agent's verdict IS your Phase 6 verdict (use the State B / State S template's gate-witness block). Pattern:

    Phase 6 sub-agent auditor verdict:

    GATE WITNESS (verbatim):
    Total: N FAIL, M WARN
    RESULT: GATE PASSED            (or: RESULT: GATE FAILED — N check(s) must be fixed)

    VALIDATOR WITNESS (verbatim):
    RESULT: VALIDATION PASSED (phase 6)   (or: RESULT: VALIDATION FAILED (phase 6 — X FAIL, Y PASS))

    AUDITOR VERDICT: PASS                 (or: FAIL)

You MAY NOT claim PASS unless `AUDITOR VERDICT` says PASS — which is legitimate ONLY when the gate's quoted `RESULT:` line is `RESULT: GATE PASSED` with `N=0` FAILs in the `Total:` line AND the validator line is `RESULT: VALIDATION PASSED (phase 6)`. If the gate reports any FAILs, or the validator still sees `gate_verdict: "pending"` / missing §11 fields, the verdict is FAIL: report the FAIL count and failing checks; do NOT report PASS, "complete", or "no remaining work". If `quality/results/quality-gate.log` is empty or lacks the two verdict lines, the gate was never invoked — the auditor must re-run it before returning anything. Fabricating a PASS claim against a failing (or never-run) gate is the exact credibility defect this hybrid contract closes — an adopter reading your chat can verify the verbatim witness lines against actual gate + validator output, and the auditor's reward shape (`pass`/`partial`/`fail` is what the gate actually said, not what you hoped) is structurally separated from your executor reward bias.

Mark Phase 6 complete in PROGRESS.md (use the checkbox format `- [x] Phase 6 - Verify` — do NOT switch to a table).

After completing this phase, emit `## What just happened` + `### What to do next` as the LAST visible output in chat per the decision tree at `references/what_just_happened.md`. This is end-of-baseline — use State B if `quality/BUGS.md` has at least one `^### BUG-` heading, or State S if it has zero headings AND the gate verdict shows the "no BUG-NNN headings" WARN (the pass-process / fail-recall failure mode the contract was designed to surface).
