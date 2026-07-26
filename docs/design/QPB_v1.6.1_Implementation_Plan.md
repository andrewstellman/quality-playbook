# Quality Playbook v1.6.1 — Implementation Plan (Precision)

*Companion to: `QPB_v1.6.1_Design.md`. Created 2026-07-21 by splitting Track 2 out of `QPB_v1.6.0_Implementation_Plan.md`; the phase content below is moved verbatim.*
*Version number provisional — see `QPB_v1.6.1_Design.md` Decision Record #2. **Resolve before Phase 5 starts.***
*Phase numbering is deliberately continued from the v1.6.0 plan (5, 6, 7) rather than restarted at 1, so landed commits and cross-references stay valid.*

---

## Operating Principles

Carried unchanged from the v1.6.0 plan:

- **The design doc is the spec.** This plan sequences and gates; it does not pre-decompose. The implementing AI reads `QPB_v1.6.1_Design.md` end-to-end and decomposes during execution, per `ai_context/DEVELOPMENT_PROCESS.md` (no per-phase briefs).
- **The manifest stays the source of truth.** The FP-audit consumes the manifest, never the rendered document.
- **Independence is load-bearing for the FP-audit:** the audit sub-agent gets finding + cited source + relevant derived REQ + rubric — never the running skill, phase prompts, or writeup reasoning.
- **Source edits go through the diagnosis→Claude Code lane** per workspace CLAUDE.md; this plan and the design doc are the Cowork-editable planning surface.
- **Branch + ship discipline:** never push from a sandbox; verify every remote claim with `git ls-remote`; no wall-clock estimates anywhere.

New for this release:

- **v1.6.0 must be shipped before Phase 5 starts.** The tracks were independent by design, but the split makes the ordering concrete.
- **This release runs v1.6.0's fixture suite before merging** (the track-coupling rule, now one-directional).

---

## Phase 0 — Base confirmation (operator gate)

- v1.6.0 tagged, merged, and its branch closed out; `1.6.1` (or its resolved number) branched from it, base SHA recorded in the branch's first commit message.
- The OpenFGA run fixtures preserved read-only as the precision oracle inputs.
- **Resolve the version number** (`QPB_v1.6.1_Design.md` Decision Record #2) and rename these two documents if it changes.

---

# Track 2 — Precision (independent; parallelizable with Track 1)

## Phase 5 — Slice 3: NFR discovery + FP-audit core (Features A + B)

Carried from the 2026-05-24 plan in substance; Design §3-§4 are the spec.

- **Feature A:** `nfr_class` + mandatory `acceptance_criterion`/`verification_method` in `schemas.md` + manifests (backward-compatible; functional REQs unchanged). **Manifest record-shape divergence — resolved 2026-07-20: tolerate, do not normalize.** The three benchmark manifests carry three different record shapes while all declaring `schema_version: 1.5.8` (chi: `text`, no `title`; express: `title`/`tier`/`conditions_of_satisfaction`/`specificity`; virtio: `title`/`tier_label`/`source`/`formal_doc_refs`, no CoS). `nfr_class` and the mandatory NFR fields must be **additive and shape-tolerant** — read defensively, never assume a sibling field exists, never rewrite an existing record's shape. A normalization pass is out of scope for v1.6.0; derivation of core classes (security, reliability, performance) with evidence tracing; the grounding rule (advisory/CVE with no derived-NFR violation → `KNOWN-ISSUE`); categorization-tier state confirmed in code before extending (incl. the B-13 reconcile note); gate FAILs aspirational NFRs (mutation-bitten). NFR sections render into the Feature C architecture (or the pre-C render if Track 2 lands first — the render slot degrades gracefully in both directions).
- **Feature B:** the fresh-context FP-audit pass post-triage / pre-finalization; core rubric (reachability, applicability incl. CVE version-range, source-of-truth, requirements-traceability); security highest-scrutiny; verdicts CONFIRMED / DEMOTED / RECLASSIFIED-KNOWN-ISSUE / UNCERTAIN with preserved transcript; independence sealed and verified; the `confirmed-open (integration-harness-required)` disposition admissible only on FP-audit CONFIRM; new dispositions narrated via the 090v verdict-explanation framework.

Tests: gate tests for NFR fields; derivation fixture (OpenFGA contextual-tuple restriction → derived REQ-SEC with acceptance criterion); FP-audit fixtures (BUG-003 → DEMOTED, BUG-006 → DEMOTED/RECLASSIFIED, BUG-009 → RECLASSIFIED-KNOWN-ISSUE, BUG-001/002/004 → CONFIRMED); one non-security demotion fixture (generality).

Gate to Phase 6: fixtures green; independence verified (auditor demonstrably lacks skill/writeup context).

## Phase 6 — Slice 3 acceptance: the OpenFGA re-run

- Re-run Mode-A against the preserved OpenFGA fixture tree with NFR discovery + FP-audit active. **⚠ Resolve OD-5 (the HIGH-precision bar) before this gate.**
- Acceptance: BUG-003/006/009 cannot stand as confirmed HIGH; BUG-001/002/004 still surface; precision ≥ bar; no genuine finding suppressed. Run output + audit transcripts preserved as acceptance evidence.

## Phase 7 — Slice 4 breadth + precision Council

- Remaining NFR classes (usability, portability, maintainability, interop); full FP-audit rubric (design-intent, compensation, severity-justification); per-run precision metrics.
- **Nested 3×3 Council** (per Design §13 item 4): NFR derivation testability, FP-audit independence (the fabrication-tell check), grounding rule, OpenFGA regression. Standard acceptance checks on responses (real source reads, three inner verdicts per outer file, convergence flags).

Gate: Council Ship within 3 cycles or HALT + recalibrate. **Track 2 complete.**

---

---

## Phase 8 — Release (both slices complete)

- Version stamps from the single version source (SKILL.md frontmatter per the v1.5.10 consolidation); channel package versions.
- README + CHANGELOG: framed as the precision release — NFR grounding and FP-audit precision, with the OpenFGA re-run as the headline. Restore 090j's framing to "mechanical backstop beneath Feature B," which is what OD-8 actually resolved (v1.6.0's notes describe it as that release's only precision guard, per the split).
- Whole-surface umbrella Council; then the standard close-out sequence per `DEVELOPMENT_PROCESS.md` (Andrew tags; scripted publish gates; verify-before-claiming on every remote ref).

---

## Risks and mitigations

Carried from the v1.6.0 plan, Track 2 items only:

- **FP-audit too aggressive / not actually fresh-context / cost** — carried unchanged from the 2026-05-24 plan (acceptance oracle protects recall; independence is a phase-gate item; scope starts at HIGH/MED if cost bites).
- **The render slot has been sitting unused since v1.6.0.** Feature C shipped `references/phase2_generation_guide.md`'s non-functional-sections slot as "absent until NFR derivation ships." Verify the slot still behaves as specified before building into it, rather than assuming a slot written months earlier still matches.

---

## Backlog — additional 1.6.1 candidates (not Track 2)

- **End-of-Phase-2 must ALWAYS disclose the agent (Feature H) review in full AND present the opt-in human-interview offer.** *(Flagged 2026-07-26 from a sonnet chi run.)* Observed: the Phase 2 end-of-phase message surfaced *some* of the persona-pass disclosure but did **not** present the requirements-validation interview offer, even though `phase_prompts/phase2.md` designates it "its primary offer" and the interview is opt-in / never-auto-starts — so an operator who is never shown the offer cannot take it, and the human-in-the-loop pass silently never happens. This is a **compliance/robustness gap** (the model omitted a mandated end-of-phase element), not a defect in the interview itself. Fix candidates: strengthen the mandate in `phase2.md` / `references/phase2_generation_guide.md` / the State-P2 template in `references/what_just_happened.md` so the end-of-phase block MUST carry (a) the full `persona_review_disclosure(...)` result — every persona that ran, every change applied, where to read it — and (b) the interview offer text, together; and evaluate whether `validate_phase_artifacts`/the gate can assert their presence (hard to mechanically check a chat-output element, so at minimum a hardened prompt-level requirement, ideally a witness the operator can see). Root cause is the same class as the Phase-6 "operator chat carries the truth" guardrail — a mandated disclosure that a weak or hurried model can skip.

- **Observable auditor sessions: when Phase 4 spawns a `claude` CLI auditor, stream its output so the orchestrator can monitor it live.** *(Flagged 2026-07-26 from a sonnet chi Phase 4 run.)* Observed: the Phase 4 Council spawned `claude --print` and `gh copilot` as background subprocesses; `gh copilot` streamed a live transcript (254 lines, "currently reading requirements_manifest.json") while the `claude` CLI auditor showed **0 lines for 15+ minutes** because the `claude` CLI **buffers by default** — leaving the orchestrator unable to tell "working slowly on a large read-heavy prompt" from "hung / waiting on a login." Intent: use a streaming output mode so a spawned `claude` auditor is observable live. **CAVEAT — do not naively add `--output-format stream-json --verbose`:** the workspace Council notes document that `claude --output-format stream-json --verbose -p "$(cat large_prompt.md)"` **silently exits after the init event** on large prompts (bit instructions 182/183/186); the standing workaround was to *drop* stream-json and use default text output — which is exactly what produces the buffered/invisible behavior seen here. So this item is a real tension to resolve, not a one-liner: (1) first re-test whether the stream-json silent-exit-on-large-prompt bug still reproduces on the current `claude` CLI (it may be fixed since v1.5.7); (2) if fixed, adopt stream-json for auditor spawns; (3) if not, use an alternative that is still observable — smaller/chunked prompts (the bug is large-prompt-triggered), a heartbeat/progress witness the auditor writes, or preferring the **worker self-Council subagent protocol** (Protocol 1), which is natively observable and was introduced precisely to avoid the CLI's buffering/silent-exit failure modes.

- **Push the model to write the correct NOT_RUN disposition marker the first time, not a bare NOT_RUN the gate has to reject.** *(Flagged 2026-07-26 from the sonnet chi Phase 5/6 run.)* Observed: two genuinely-untestable bugs (BUG-010 doc-only, BUG-011 an unreachable defensive branch) were given bare `NOT_RUN` TDD receipts, and the Phase 6 gate correctly **FAILED** them: `NOT_RUN is only honest when the test-runner probe itself failed OR the green receipt documents a no-in-tree fix` — but `phase5_env.log` showed the runner was available, so a bare `NOT_RUN` is an improper disposition. The *analysis* was right (the bugs really are untestable), the *receipt* was wrong, and the executor's chat summary then softened the gate FAIL into "honest NOT_RUN" rather than reporting the gate's actual instruction. Fix candidate: strengthen the Phase 5 TDD / receipt-writing guidance so a genuinely-untestable-or-no-in-tree-fix bug gets the explicit marker (`no in-tree fix` / documented-unreachable, with the white-box evidence) in the green receipt at write time — turning a guaranteed gate FAIL into a clean pass. Root cause is the same "operator chat carries the truth" class again: an executor narrating a gate FAIL as benign.

- **Resolve the `AGENTS.md` circular gate dependency so a genuinely-clean run can actually pass.** *(Flagged 2026-07-26 from the same run.)* The gate FAILs on `AGENTS.md missing (required at project root)`, but `AGENTS.md` is generated by the orchestrator **only after Phase 6 passes** — so any run that fails Phase 6 for any other reason *also* fails on missing `AGENTS.md`, compounding one root failure into two and making a would-be-clean run structurally unable to pass. Options to evaluate: don't gate `AGENTS.md` generation on Phase 6 success (generate it on the final pass attempt); OR have the gate suppress the `missing_artifact` FAIL for `AGENTS.md` when Phase 6 itself failed (don't double-count a cascade); OR emit a provisional `AGENTS.md`. Pick one so the artifact contract isn't self-blocking.

- **Automatic publish-on-tag (CI) for npm + PyPI.** *(Deferred from 1.6.0, 2026-07-26, operator decision.)* 1.6.0 ships via the manual `bin/publish_npm.py` / `bin/publish_pip.py` scripts (the designed path: pre-flights, two-phase test-PyPI→prod, `--publish` affirmation, verify-before-claiming). For 1.6.1, add a CI workflow that runs those same scripts automatically when a `v*` tag is pushed — reusing the existing pre-flight/verify logic, with npm + PyPI tokens as repo secrets. Keep the manual path available for high-stakes releases; auto-on-tag is for routine patches. Must not weaken the two-phase PyPI gate or the tag-is-ancestor pre-flight.
