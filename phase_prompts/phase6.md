{skill_fallback_guide}

You are a quality engineer doing the verification phase of a quality playbook run. Phases 1-5 are complete.

Read SKILL.md (the Phase 6 pointer section) AND `references/phase6_verify_guide.md` (the full Phase 6 protocol — moved out of SKILL.md in v1.5.7 Phase 7 trim for size reduction). Resolve SKILL.md and reference files via the documented fallback list above; do NOT assume any single install layout. Follow the incremental verification steps (6.1 through 6.5).

Step 6.1: If quality/mechanical/verify.sh exists, run it. Record exit code.
Step 6.2: Run quality_gate.py. Locate it via the same fallback list used for SKILL.md (`quality_gate.py` sits in the same directory as SKILL.md in every install layout — e.g., `quality_gate.py`, `.claude/skills/quality-playbook/quality_gate.py`, `.github/skills/quality_gate.py`, `.cursor/skills/quality-playbook/quality_gate.py`, `.continue/skills/quality-playbook/quality_gate.py`, `.github/skills/quality-playbook/quality_gate.py`, `.codex/skills/quality-playbook/quality_gate.py`, `.windsurf/skills/quality-playbook/quality_gate.py`, `.cline/skills/quality-playbook/quality_gate.py`, `.aider/skills/quality-playbook/quality_gate.py`). Then run:
  python3 <resolved_quality_gate_path> .
Read the output carefully. For every FAIL result, fix the issue:
- Missing regression-test patches: generate quality/patches/BUG-NNN-regression-test.patch
- Missing inline diffs in writeups: add a ```diff block
- Non-canonical JSON fields: fix tdd-results.json (use 'id' not 'bug_id', etc.)
- Missing files: create them
After fixing all FAILs, run quality_gate.py again. Repeat until 0 FAIL.
Save final output to quality/results/quality-gate.log.

**MANDATORY gate-verdict witness (v1.5.7 A-13).** Your State P6 "What
just happened" chat emit MUST quote the gate's final verdict verbatim.
After running `python3 <resolved_quality_gate_path> .` and saving
output to `quality/results/quality-gate.log`, extract its literal last
two lines and paste them into your emit. The gate prints exactly these
two lines (from quality_gate.py):

    Total: N FAIL, M WARN
    RESULT: GATE PASSED            (or: RESULT: GATE FAILED — N check(s) must be fixed)

Both lines MUST appear verbatim in your "What just happened" emit (use
the State B / State S template's gate-witness block). If
`quality/results/quality-gate.log` is empty or does not contain these
two lines, the gate did not run successfully — it was never invoked
or its output was not captured; re-run it before emitting anything.

**No PASS claim without N=0 FAILs (v1.5.7 A-13).** Your end-of-Phase-6
verdict — in PROGRESS.md AND the State P6 chat emit — is PASS ONLY
when the quoted `RESULT:` line says `RESULT: GATE PASSED` with `N=0`
FAILs in the `Total:` line. If the gate reports any FAILs, your
verdict is FAIL: list the gate's FAIL count and the failing checks;
do NOT report PASS, "complete", or "no remaining work". Fabricating a
PASS claim against a failing (or never-run) gate is the exact
credibility defect this witness contract closes — an adopter reading
your chat output can verify the gate verdict line is present and
matches your claim.

Step 6.3: Run functional tests if a test runner is available.
Step 6.4: File-by-file verification checklist (read one file at a time, check, move on).
Step 6.5: Metadata consistency check.

Append each step's result to quality/results/phase6-verification.log.
Mark Phase 6 complete in PROGRESS.md (use the checkbox format `- [x] Phase 6 - Verify` — do NOT switch to a table).

After completing this phase, emit `## What just happened` + `### What to do next` as the LAST visible output in chat per the decision tree at `references/what_just_happened.md`. This is end-of-baseline — use State B if `quality/BUGS.md` has at least one `^### BUG-` heading, or State S if it has zero headings AND the gate verdict shows the "no BUG-NNN headings" WARN (the pass-process / fail-recall failure mode the contract was designed to surface).
