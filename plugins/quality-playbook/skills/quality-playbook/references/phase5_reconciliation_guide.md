# Phase 5: Post-Review Reconciliation and Closure Verification — detail

*Extracted from SKILL.md in v1.5.10 (instr 052) — loaded on entering Phase 5. SKILL.md keeps the `## Phase 5` heading, the instrumentation + source-edit guardrail + required-references preamble, and the mandatory end-of-phase message block (with its inverted default-continue boundary) inline; this file carries the entry gate, challenge gate, terminal gate, and reconciliation sub-gates.*

**Phase 5 entry gate (mandatory — HARD STOP).** Before proceeding, verify ALL of the following Phase 4 artifacts exist:

1. `quality/spec_audits/` directory exists and contains at least one `*triage*` file (the triage synthesis)
2. `quality/spec_audits/` contains at least one `*auditor*` file (individual auditor reports)
3. `quality/PROGRESS.md` exists and its Phase 4 line is marked `[x]`

If any of these are missing, STOP and go back to Phase 4. Do not proceed with reconciliation until the spec audit artifacts are confirmed present — reconciliation without triage data produces an incomplete closure report.

Re-read `quality/PROGRESS.md` — specifically the cumulative BUG tracker. This is the authoritative list of all findings across both code review and spec audit.

**Challenge gate (mandatory before reconciliation).** Before running closure verification, apply the challenge gate to every confirmed bug that matches an auto-trigger pattern. Read `references/challenge_gate.md` for the full protocol. In summary:

1. Scan the BUG tracker for bugs matching any auto-trigger pattern (security-class findings, code with design-decision comments at the cited location, findings with no spec basis, sibling code paths handling the same concern differently, findings about missing functionality).
2. For each triggered bug, run the two-round challenge using fresh sub-agents as described in the reference.
3. Record verdicts in `quality/challenge/BUG-NNN-challenge.md`.
4. Apply verdicts: CONFIRMED bugs proceed normally. DOWNGRADED bugs get their severity adjusted. REJECTED bugs are removed from the BUG tracker and relocated to a "Reviewed and dismissed" appendix in BUGS.md with the challenge reasoning.

**Apply common sense throughout.** The challenge gate's primary purpose is to catch findings where pattern-matching overrode judgment. If a bug would make you look foolish reporting it to the upstream maintainer — a self-documenting placeholder flagged as a critical vulnerability, a documented design decision flagged as a defect, an intentional feature gap flagged as a security hole — it should not survive the challenge. The common-sense test is not one factor among many; it is the framing for the entire review.

**Why this gate exists:** In v1.4.6 edgequake benchmarking, the code review confirmed 42 bugs including 7 rated CRITICAL. After manual review, the strongest finding was HIGH severity, not CRITICAL. Six "CRITICAL" tenant-isolation bugs were documented feature gaps with explicit annotations explaining the intentional design choice. One "CRITICAL" JWT finding was a self-documenting development placeholder containing the literal string "change-me-in-production." The model defended these findings through multiple rounds of pushback because its instinct was to find and defend bugs, not to apply common sense about what constitutes a defect. The challenge gate forces that common-sense review to happen before findings are finalized.

1. **Run the Post-Review Reconciliation** as described in `references/requirements_pipeline.md`. Update COMPLETENESS_REPORT.md.
2. **Run closure verification:** For every row in the BUG tracker, verify it has either a regression test reference or an explicit exemption. If any BUG lacks both, write the test or exemption now.
3. **Triage-to-BUGS.md sync gate (mandatory).** Re-read the triage report (`quality/spec_audits/*-triage.md`). For every finding confirmed as a code bug, verify it appears in `quality/BUGS.md`. If BUGS.md does not exist, create it now. If BUGS.md exists but is missing confirmed bugs from the triage, append them. A triage report with confirmed code bugs and no corresponding BUGS.md entries is non-conformant — the phase cannot be marked complete until they are synced. This gate exists because a prior benchmark observed a triage confirming bugs while BUGS.md was never created.
4. **Clean up after spec-audit reversals:** If the spec audit reclassified any code review BUG as a design choice or false positive, remove or relocate the corresponding regression test per `references/review_protocols.md`.
5. **Resolve CR vs spec-audit conflicts:** If the code review and spec audit disagree on the same finding (one says BUG, the other says design choice), deploy a verification probe per `references/spec_audit.md` and record the resolution in the BUG tracker.

**TDD sidecar-to-log consistency check (mandatory).** For every bug entry in `tdd-results.json`, verify the corresponding log files exist and agree. If `tdd-results.json` contains a bug with `verdict: "TDD verified"`, then `quality/results/BUG-NNN.red.log` must exist with first line `RED` and `quality/results/BUG-NNN.green.log` must exist with first line `GREEN`. If the sidecar claims "TDD verified" but no red-phase log exists, the verdict is unsubstantiated — either create the log by running the test, or downgrade the verdict to `"confirmed open"`. This check exists because agents have been observed writing "TDD verified" verdicts in the JSON based on narrative reasoning without ever executing the test.

**Executed evidence outranks narrative artifacts (contradiction gate).** Before running the terminal gate, check for contradictions between executed evidence and prose artifacts. Executed evidence includes: mechanical verification artifacts (`quality/mechanical/*`), verification receipt files (`quality/results/mechanical-verify.log`, `quality/results/mechanical-verify.exit`), regression test results (`test_regression.*` with `xfail` outcomes), TDD red-phase log files (`quality/results/BUG-NNN.red.log`), and any shell command output saved during the pipeline. Prose artifacts include: `REQUIREMENTS.md`, `CONTRACTS.md`, code reviews, spec audit triage, and `BUGS.md`. If an executed artifact shows a constant is absent (mechanical check), a test fails (regression test), or a red-phase confirms a bug (TDD traceability) — but a prose artifact claims the constant is present, the bug is fixed, or the code is compliant — the executed result wins. Re-open and correct the contradictory prose artifact before proceeding. Specifically: if `mechanical-verify.exit` contains a non-zero value, PROGRESS.md may not claim "Mechanical verification: passed" and the terminal gate may not pass — regardless of what any other artifact says. The pattern this gate catches: a triage claims a constant is preserved, BUGS.md claims "fixed in working tree," but TDD traceability shows the assertion failing on the current source. Those three cannot all be true — the executed failure is the ground truth.

**Version stamp consistency check (mandatory).** Read the `version:` field from the SKILL.md metadata (using the reference file resolution order). Then check every generated artifact: PROGRESS.md's `Skill version:` field, every `> Generated by` attribution line, every code file header stamp, and every sidecar JSON `skill_version` field. Every version stamp must match the SKILL.md metadata exactly. A single mismatch is a benchmark failure — fix the stamp before proceeding. This check exists because agents have been observed leaving stale version stamps in output (most often by copying a hardcoded number from an older template) — the stamps must agree across every emitted artifact.

**Mechanical directory conformance check.** If `quality/mechanical/` exists, it must contain at minimum a `verify.sh` file. An empty `quality/mechanical/` directory is non-conformant — it implies the step was attempted but abandoned. If no dispatch-function contracts exist in this project's scope, do not create a `mechanical/` directory at all. Instead, record in PROGRESS.md: `Mechanical verification: NOT APPLICABLE — no dispatch/registry/enumeration contracts in scope.` If dispatch contracts do exist, `verify.sh` must include one verification block per saved extraction file under `quality/mechanical/` (not just one). A verify.sh that checks only one artifact when multiple exist is incomplete.

**Verification receipt gate (mandatory before terminal gate).** If `quality/mechanical/` exists, the following receipt files must also exist before the terminal gate may run:
- `quality/results/mechanical-verify.log` — full stdout/stderr from `bash quality/mechanical/verify.sh`
- `quality/results/mechanical-verify.exit` — a single line containing the exit code (e.g., `0`)

If either file is missing, run `bash quality/mechanical/verify.sh > quality/results/mechanical-verify.log 2>&1; echo $? > quality/results/mechanical-verify.exit` now. If the exit code is not `0`, the terminal gate fails — do not proceed until the mechanical mismatch is resolved (by fixing the extraction, not by editing verify.sh or the receipt). PROGRESS.md may not claim "Mechanical verification: passed" unless `mechanical-verify.exit` contains `0`. This gate exists because v1.3.23 PROGRESS.md claimed all verification passed when verify.sh actually returned exit 1 — the receipt file makes this claim auditable.

**TDD Log Closure Gate (mandatory before terminal gate).** Before proceeding to the terminal gate, enumerate all confirmed bug IDs from `quality/BUGS.md` and verify:
1. `quality/results/BUG-NNN.red.log` exists for every confirmed bug.
2. If `quality/patches/BUG-NNN-fix.patch` exists for that bug, `quality/results/BUG-NNN.green.log` also exists.
3. The first line of each log file is one of: `RED`, `GREEN`, `NOT_RUN`, `ERROR`.
If any check fails, stop and generate the missing logs now using the language-aware test execution commands from the TDD execution enforcement section. Do not proceed to the terminal gate with missing TDD logs — a bug with a "TDD verified" verdict in tdd-results.json but no corresponding red-phase log is a contradiction.

**Terminal gate (mandatory before marking Phase 5 complete):**

**Prerequisite check:** The terminal gate may run only if Phase 3 (code review) and Phase 4 (spec audit) are both complete, or explicitly marked skipped with rationale in PROGRESS.md. A zero-bug outcome is valid only if code review and spec audit artifacts exist (i.e., `quality/code_reviews/` and `quality/spec_audits/` directories contain report files). If these artifacts are missing and the phases are not explicitly skipped, the terminal gate fails — do not mark Phase 5 complete.

**BUGS.md is always required.** Every completed run must produce `quality/BUGS.md`, regardless of whether bugs were found. If code review and spec audit confirmed zero source-code bugs, create BUGS.md with a `## Summary` stating "No confirmed source-code bugs found" and listing how many candidates were evaluated and eliminated (e.g., "Code review evaluated N candidates; spec audit evaluated M candidates; all were reclassified as design choices, test-only issues, or false positives"). This provides a positive assertion of a clean outcome rather than ambiguous file absence. A completed run with no BUGS.md is non-conformant.

**BUGS.md heading format.** Each confirmed bug must use the heading level `### BUG-NNN` (e.g., `### BUG-001` or `### BUG-H1`). Both numeric IDs (`BUG-001`) and severity-prefixed IDs (`BUG-H1`, `BUG-M3`, `BUG-L6`) are valid. This is the canonical heading format — not `## BUG-001`, not `**BUG-001**`, not a bullet point. The `### BUG-NNN` heading is what downstream tools grep for when counting bugs, and what the tdd-results.json `id` field must match. Inconsistent heading levels cause machine-readable counts to disagree with the document.

Re-read `quality/PROGRESS.md`. Count the BUG tracker entries. Then:

1. Print the following statement to the user (this is mandatory, not optional):

   > "BUG tracker has N entries. N have regression tests, N have exemptions, N are unresolved. Code review confirmed M bugs. Spec audit confirmed K code bugs (L net-new). Expected total: M + L."

2. Write the same statement into PROGRESS.md under a new `## Terminal Gate Verification` section (immediately after the BUG tracker table). This persists the gate into the artifact so reviewers can verify it without reading session logs.

If the tracker entry count does not equal M + L, stop and reconcile — a BUG was orphaned from the tracker. Do not mark Phase 5 complete until the counts match. This gate exists because agents reliably skip the tracker update after spec audit, orphaning a large fraction of confirmed bugs.

**Regression test function-name verification:** For each BUG tracker entry that references a regression test, grep for the test function name in the regression test file and confirm it exists. An agent can write a test name in the tracker without actually creating the test. If any referenced test function does not exist, write it now before passing the gate.

3. Verify the `With docs` metadata field in PROGRESS.md matches reality: if `reference_docs/` exists and contains files, it should say `yes`; otherwise `no`. Fix it if wrong.

**Artifact file-existence gate (mandatory before marking Phase 5 complete).** Before writing the Phase 5 completion checkbox, verify that every required artifact exists as a file on disk — not just mentioned in PROGRESS.md. Run these checks (use `ls` or equivalent):

- `quality/BUGS.md` exists (required for all completed runs, per benchmark 34)
- `quality/REQUIREMENTS.md` exists
- `quality/QUALITY.md` exists
- `quality/PROGRESS.md` exists (obviously — you're writing to it)
- `quality/COVERAGE_MATRIX.md` exists
- `quality/COMPLETENESS_REPORT.md` exists
- `quality/formal_docs_manifest.json` exists (written by `bin/reference_docs_ingest.py` in Phase 1; empty `records[]` is valid when no formal docs present)
- `quality/requirements_manifest.json` exists (authoritative REQ records, rendered to REQUIREMENTS.md)
- `quality/use_cases_manifest.json` exists (authoritative UC records, rendered to USE_CASES.md / the REQUIREMENTS.md narrative)
- `quality/citation_semantic_check.json` exists (Phase 4 Layer-2 output; empty `reviews[]` is valid for Spec Gap runs)
- If Phase 3 ran: `quality/code_reviews/` contains at least one `.md` file
- If Phase 4 ran: `quality/spec_audits/` contains a triage file AND individual auditor files
- If Phase 0 or 0b ran: `quality/SEED_CHECKS.md` exists as a standalone file (not inlined in PROGRESS.md)
- If confirmed bugs exist: `quality/bugs_manifest.json` exists (authoritative BUG records)
- If confirmed bugs exist: `quality/results/tdd-results.json` exists
- If confirmed bugs exist: `quality/results/BUG-NNN.red.log` exists for every confirmed bug ID in `quality/BUGS.md`
- If confirmed bugs exist with fix patches: `quality/results/BUG-NNN.green.log` exists for each bug that has a `quality/patches/BUG-NNN-fix.patch`

For each missing file, create it now. Do not mark Phase 5 complete with missing artifacts — the terminal gate verification in PROGRESS.md is meaningless if the files it references don't exist on disk. This gate exists because agents have been observed completing all phases and writing a terminal gate section in PROGRESS.md while BUGS.md, SEED_CHECKS.md, and code review/spec audit files were never written to disk.

**Sidecar JSON post-write validation (mandatory).** After writing `quality/results/tdd-results.json` and/or `quality/results/integration-results.json`, immediately reopen each file and verify it contains all required keys. For `tdd-results.json`, the required root keys are: `schema_version`, `skill_version`, `date`, `project`, `bugs`, `summary`. Each entry in `bugs` must have: `id`, `requirement`, `red_phase`, `green_phase`, `verdict`, `fix_patch_present`, `writeup_path`. The `summary` object must include `confirmed_open` alongside `verified`, `red_failed`, `green_failed`. For `integration-results.json`, the required root keys are: `schema_version`, `skill_version`, `date`, `project`, `recommendation`, `groups`, `summary`, `uc_coverage`. Both files must have `schema_version: "1.1"`. If any key is missing, add it now — do not leave a non-conformant JSON file on disk. This validation exists because agents frequently emit non-conformant sidecar JSON (invented alternate schemas, legacy shapes, omitted `summary` fields, invalid enum values) — the post-write check is the cheap way to catch and correct before the gate.

**Script-verified closure gate (mandatory, final step before marking Phase 5 complete).** Locate `quality_gate.py` using the same fallback as reference files — walk these ten canonical install layouts in order, taking the first hit: `quality_gate.py`, `.claude/skills/quality-playbook/quality_gate.py`, `.github/skills/quality_gate.py`, `.cursor/skills/quality-playbook/quality_gate.py`, `.continue/skills/quality-playbook/quality_gate.py`, `.github/skills/quality-playbook/quality_gate.py`, `.codex/skills/quality-playbook/quality_gate.py`, `.windsurf/skills/quality-playbook/quality_gate.py`, `.cline/skills/quality-playbook/quality_gate.py`, `.aider/skills/quality-playbook/quality_gate.py`. Run it from the project root directory. This script mechanically validates: file existence, BUGS.md heading format, sidecar JSON required keys AND per-bug field names (`id`, `requirement`, `red_phase`, `green_phase`, `verdict`, `fix_patch_present`, `writeup_path`) AND enum values AND summary consistency, use case identifiers, terminal gate section, mechanical verification receipts, version stamps, writeup completeness, **regression-test patch presence for every confirmed bug**, and **inline fix diffs in every writeup** (every `quality/writeups/BUG-NNN.md` must contain a ` ```diff ` block). If the script reports any FAIL results, fix each failing check before proceeding — the most common FAILs are: (1) missing `quality/patches/BUG-NNN-regression-test.patch` files, (2) non-canonical JSON field names like `bug_id` instead of `id`, (3) missing `confirmed_open` in the TDD summary, (4) writeups without inline fix diffs (section 6 must include a concrete diff, not just "see patch file"). Do not mark Phase 5 complete until `quality_gate.py` exits 0. Append the script's full output to `quality/results/quality-gate.log`.

**Layer-1 mechanical checks.** Beyond the legacy gate checks above, `quality_gate.py` also enforces a numbered set of structural invariants (#1–#18). A compact map of what each invariant covers:

- **#1–#10 — core contract checks.** Citation tier gating, citation document existence, citation hash match, citation excerpt presence + locatability (section/line only; page never sufficient), bug→REQ resolution, forward-link resolution, disposition completeness, functional section presence, no orphan formal docs, INDEX.md field presence.
- **#11 — citation excerpt byte-equality.** The gate re-runs `bin/citation_verifier.extract_excerpt` on every Tier 1/2 citation and rejects any stored `citation_excerpt` that does not byte-equal the freshly-extracted one. This is the Layer-1 anti-hallucination mechanism — it catches fabricated or paraphrased excerpts even when the locator is real.
- **#12 — legal `fix_type × disposition` combination.** The gate rejects illegal pairings (e.g., a `confirmed` BUG with no fix entry; a `regression_test` fix without an associated BUG). `quality_gate.py` is authoritative for the exact matrix.
- **#13 — manifest wrapper validity.** Each `quality/*_manifest.json` must wrap its record array in a standard envelope (`schema_version`, `generated_at`, `records` array). Malformed wrappers fail the gate.
- **#14 — REQ tier bound to cited FORMAL_DOC tier** (a Tier 1 REQ cannot cite a Tier 2 FORMAL_DOC).
- **#15 — ID uniqueness** within each manifest.
- **#16 — redundant citation metadata** (`version`, `date`, `url`, `retrieved`) must match FORMAL_DOC when present.
- **#17 — semantic-check majority rule.** ≥2 of 3 `overreaches` verdicts for the same Tier 1/2 REQ fails the gate (see Layer 2 sub-pass in Phase 4).
- **#18 — array value uniqueness** in `REQ.use_cases` and `UC.formal_doc_refs`.

**`citation_stale` is a gate-report marker, not a field on the citation record.** When the stored `citation.document_sha256` diverges from the live `FORMAL_DOC.document_sha256`, `quality_gate.py` writes a `citation_stale` entry into `quality_gate_report.json` (or equivalent). Do NOT write `citation_stale` onto the citation record itself — the record stays pure input, and the stale marker is gate-report output.

**Do not implement the gate in this prose.** The Layer-1 check list above is a summary of what `quality_gate.py` enforces. Implementation lives in `quality_gate.py`; SKILL.md describes the protocol but does not re-state the invariants in normative form.

**Use case identifier format.** REQUIREMENTS.md must use canonical use case identifiers in the format `UC-01`, `UC-02`, etc. for all derived use cases. Each use case must be labeled with its identifier. This is required for machine-readable traceability — the identifier format enables `quality_gate.py` and downstream tooling to count and cross-reference use cases programmatically. Use cases written as prose paragraphs without identifiers are non-conformant.

Update PROGRESS.md: mark Phase 5 complete. The BUG tracker should now show closure status for every entry.
