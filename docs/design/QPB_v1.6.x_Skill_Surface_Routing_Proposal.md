# QPB v1.6.x — Skill-Surface Routing (`--surface`) — PROPOSAL (split out of v1.5.10)

> **STATUS: PROPOSAL — captured 2026-06-21, deferred to its own future version + its own Council. Not in v1.5.10.** Split out of `QPB_v1.5.10_Language_Disclosure_And_Override_Design.md` per the 2026-06-21 adversarial review (#4): this is **pipeline routing**, not the language-disclosure hygiene close-out, and the v1.5.10 Council never saw it. Captured here so it isn't lost; needs its own design doc + 3-panel Council before any build.

## What it is
For a **Hybrid** repo (both a skill and code), let QPB choose — and let the operator override — **which QE surface** to run:
- `--surface code` → the v1.5.0 **code-divergence** pipeline (find bugs in the code).
- `--surface skill` → the **`bin/skill_derivation`** pipeline (derive REQs from `SKILL.md`+`references/`, audit coverage, divergence-detect the skill).

With a **Phase-0 dominance default** (run the larger surface by default — skill-content size vs counted source files) and archive-on-switch to run the other (reusing the same archive machinery as the language override).

## The skill-vs-doc Markdown model (the former D6)
Markdown is two different things and the surface feature is what distinguishes them:
- **A skill** (`SKILL.md` + `references/` present) is a **testable surface** via `skill_derivation` — not a testable *code language*, but real QE.
- **Plain docs** (a README / `docs/` tree with no skill) are non-testable context.

*(In v1.5.10, with this split out, Markdown reverts to simply "non-testable, never a target" — the disclosure is code-languages-only. This proposal is where the testable-skill-surface idea lives.)*

## Why it was split out
- It changes how QPB **routes** between two pipelines — core behavior, not hygiene.
- It inflates the v1.5.10 blast radius and test burden (Phase-0 classification, the v1.5.4 role-map model, the dominance measure).
- The v1.5.10 Council reviewed code-language disclosure only; this rode in afterward.

## Open questions for its own design + Council
- **Phase-0 classification (the v1.5.4 role-map model).** How is Code/Skill/Hybrid decided now (it moved from a standalone classifier to a role-map-derived model — `skill_derivation/pass_c.py`, `skill_derivation/__init__.py`)? Confirm before changing routing.
- **The dominance measure.** Skill-content size (SKILL.md+references bytes/tokens) vs counted source files — needs a defined, defensible metric.
- **Skill-surface classification edge cases (review #8).** A non-QPB `SKILL.md`; a `references/` that isn't skill references; a docs-heavy code repo. The "is this a skill surface" test is the riskiest classification and is currently hand-waved to "the worker confirms the role-map model."
- **Self-referential validation (review #9).** QPB-on-QPB is the test repo for the feature that decides QPB's *own* surface, and the prose↔code self-audit checks `SKILL.md` prose the same change wrote. Useful smoke tests, weak as correctness guarantees — pair each with an **independent fixture**.
- **Override-honoring + the `--surface` gate guard** (carries over from the language override's resolution).

## ⚠ Version sequencing is under re-assessment (2026-06-21)
**Do not treat the "1.6.x" label here as fixed.** The whole 1.6 line is being re-assessed: the 1.6.0 slot may be **reoriented to a security phase**, the current **Requirements Review** focus may bump to **1.7+**, and **another version may be inserted** before the requirements work. Experiments in a separate Cowork chat are informing this. So this proposal's version assignment (and its position relative to Requirements Review and the language-depth backlog) must be **set during that re-assessment**, not assumed from the current numbering. When the 1.6 sequencing is decided, fix this doc's target version accordingly.

## Disposition
Tracked for a future 1.6.x (or later) version — exact slot pending the re-assessment above. When scheduled: its own `docs/design/QPB_v<X>_Skill_Surface_*.md` + 3-panel Council chartered on Phase-0 routing + the dominance measure + the edge cases above. The language-disclosure primitives shipped in v1.5.10 (`detect_project_languages`, `--language`, archive-on-switch) are the substrate this builds on.
