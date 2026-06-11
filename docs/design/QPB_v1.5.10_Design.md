# Quality Playbook v1.5.10 — Design Document

*Status: created 2026-06-11. This release is the **SKILL.md trim** workstream, moved verbatim out of v1.5.9 (where it was Part 2 of `QPB_v1.5.9_Design.md`) when v1.5.9 refocused entirely on the agent-based harness + its standalone distribution (operator decision, 2026-06-11). The broader-scope backlog that previously held the v1.5.10 number is now `QPB_v1.5.11_Design.md`. Work begins after v1.5.9 ships.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Where v1.5.10 sits in the arc

One focused workstream: **SKILL.md trim** — move content from the 1256-line source `SKILL.md` into `references/*.md` files that the skill loads on-demand per phase. Goal: source SKILL.md small enough (~200-400 lines) that the awesome-copilot submission can ship the **full canonical** SKILL.md without the redirect-to-install framing that the maintainers explicitly reject.

**Why this matters:**

1. **awesome-copilot submission.** The trimmed SKILL.md the awesome-copilot script generates is a different document from the source — explicitly a redirect to "install via pip/npm" rather than the actual skill. Maintainers reject this framing. If the source SKILL.md is small enough to ship verbatim, the trim becomes unnecessary and awesome-copilot gets the **canonical** functional skill.
2. **Per-invocation token cost.** SKILL.md is loaded into the agent's context on every invocation. ~33K tokens × every QPB run × every adopter is significant cost. Lazy-loading phase content cuts the per-run baseline substantially.
3. **Maintenance.** A 1256-line SKILL.md is hard to navigate and edit. Phase-isolated reference files give clearer separation of concerns; editing Phase 3 prose doesn't touch Phase 1 content.

---

## Design — what stays vs what moves

Stays in source SKILL.md (the trimmed canonical version):

- Frontmatter (`name`, `description`, `license`, version, author, github)
- Phase Overview — the "plan overview" prose that describes what each phase does at a high level (~200-300 words)
- Phase entry contracts — what each phase reads and produces, in tabular form
- Invocation forms (Mode A / Mode B / harness)
- The reference file load instructions — "for Phase N detail, read `references/phase_N_guide.md`"
- Critical contract content that's not phase-specific (run_state.jsonl schema, install-location fallback list, version-stamp invariants)
- **v1.5.9 carry-forward:** the Heartbeat emission section (added in v1.5.9 Phase 1B) is contract-level content and stays.

Moves to `references/`:

- Phase 1 detailed exploration patterns + role-map querying detail → `references/phase1_detail.md` (consolidate with existing `phase1_exploration_guide.md`)
- Phase 2 generation step-by-step instructions → `references/phase2_detail.md` (consolidate with existing `phase2_generation_guide.md`)
- Phase 3-6 corresponding detail files
- Challenge-gate prose (already partially in `references/challenge_gate.md` — consolidate)
- Spec-audit Council protocol details (already in `references/spec_audit.md` — verify completeness)
- Run-state event taxonomy detail (most already in `references/run_state_schema.md` — verify completeness)

**Loading model.** The skill loads the trimmed SKILL.md at session start, then loads each `references/phase_N_*.md` file when the agent enters Phase N. The orchestrator agent reads the reference file via `Read` tool when crossing the phase boundary. This is the same on-demand model the existing references/ work uses — extending it to cover more of the per-phase content.

**Backward compatibility.** Adopters running QPB skills installed pre-v1.5.10 (whose SKILL.md still has the full content) keep working. The trim is a source-side change; installed-skill semantics are identical for the previous installation.

**Validator updates.** `quality_gate.py` gains an invariant that scans SKILL.md's `Read references/X.md` references and confirms each resolves to an existing file. Without this, a stale reference quietly breaks a phase mid-run.

**Token-ceiling test (`bin/tests/test_skill_md_size.py`).** The current ceiling is 32K tokens (v1.5.7 instruction 090m). v1.5.10 ratchets it down to ~12K with the same rationale-doc-on-bump policy: future SKILL.md bloat is detected immediately.

---

## Open design questions (resolve during implementation)

- **Boundary criteria — what's "phase-specific" enough to move?** Some content is read in Phase 1 but referenced in Phase 4 (defensive patterns, exploration role-map). Single-phase content moves cleanly; cross-phase content needs design decisions on duplication vs cross-references.
- **Eager vs lazy reference loading.** Eager (load all phase references at session start) is simpler but defeats the point — we still pay the token cost. Lazy (load when entering phase) is the goal but requires the agent to actually invoke `Read` at phase boundaries, which the skill prose must enforce.
- **Adopter-install upgrade path.** If an adopter has v1.5.9 installed and we ship a smaller SKILL.md in v1.5.10, do we tell them to re-install via `quality-playbook install`? Or does the next QPB run detect old-SKILL.md and prompt for update?
- **Token-ceiling target.** 12K is a guess. The empirical question is "how small can we make SKILL.md while preserving recall on the standard benchmark set." Implementation pass needs to measure.

---

## Ship criteria

- The trimmed SKILL.md passes the new validator + the token-ceiling test.
- A regression run against the standard benchmark set (3-5 repos) confirms no material recall degradation.
- Council Self-Review Protocol 1 (three panelists: audit-table completeness, mechanical-extraction correctness, recall-regression sufficiency), with the **defensive-sweep charter** per `DEVELOPMENT_PROCESS.md` (v1.5.8 207+): any panelist verifying content moves also greps the trimmed SKILL.md for the same defect class elsewhere.
- **awesome-copilot re-submission test:** regenerate the awesome-copilot packet WITHOUT the trim (ship the now-trimmed SKILL.md directly); confirm size is acceptable; submit PR. If accepted → trim succeeded its primary goal; if rejected → diagnose and iterate.

---

## Risks

| Risk | Mitigation |
|---|---|
| SKILL.md trim degrades recall on the benchmark set | Standard 3-5 repo benchmark run before ship; abort if recall drops materially |
| Phase-specific reference files have implicit dependencies on each other | Validator scans for `references/X.md` mentions and resolves them; cycle detection added |
| Reference files duplicate content already in SKILL.md | Trim audit step: any content moved to references is REMOVED from SKILL.md; no copy-and-keep |
| Adopter-install migration breaks active QPB runs | Backward compat is intentional — v1.5.9-installed skill keeps working; upgrade is opt-in |

---

*End of v1.5.10 Design. Implementation plan in `QPB_v1.5.10_Implementation_Plan.md`. Predecessor release (harness + standalone distribution) in `QPB_v1.5.9_Design.md`. Deferred broader scope in `QPB_v1.5.11_Design.md`.*
