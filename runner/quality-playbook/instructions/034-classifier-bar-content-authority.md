# Instruction 034 — Classifier bar: content-authority, not authorship provenance

**Branch:** `1.6.0` (continue on it; do not create a new branch).
**Commit policy:** commit locally on `1.6.0` when the work is done and self-Council says SHIP. **Never push.**
**Council:** REQUIRED — worker self-Council (Protocol 1), 3 panelists, iterate to unanimous SHIP before writing the output.
**Scope:** skill-source guidance edit. Primary file: `plugins/quality-playbook/skills/quality-playbook/references/phase1_exploration_guide.md`. Secondary (only if needed): `phase_prompts/phase1.md`, `scripts/doc_classification.py`. **Do NOT edit any `docs/design/` file** — §8a has already been updated by the orchestrator and is your spec anchor.

## Goal

The read-and-judge classifier is gating document promotion on **authorship provenance** ("were these written by the project's own maintainers?") instead of **content authority** ("does this read as a precise, contract-shaped reference/spec?"). Fix the model-facing classification guidance so the bar is content-authority, and so an authoritative-*genre* document the model is merely uncertain about goes to **Lane B `unconfirmed`** (cited + surfaced), never straight to background.

## Read first (end to end)

1. `docs/design/QPB_v1.6.0_Design.md` — **§8a Revision**, especially the three-lane rules, the Lane B definition (it names "chi/express's `.md` API references" as the canonical unconfirmed-cite case), the threat model (which deliberately de-emphasizes provenance suspicion), and the new **"The bar is content-authority, not authorship provenance"** paragraph (2026-07-26). That paragraph is your spec — implement it in the guidance.
2. `plugins/quality-playbook/skills/quality-playbook/references/phase1_exploration_guide.md` — the classification section (≈ lines 43–103). This is where the bar the model reads actually lives.
3. `plugins/quality-playbook/skills/quality-playbook/phase_prompts/phase1.md` — line ~285 ("read and categorize each gathered document") delegates the category vocabulary and the three lanes to the guide above.

## Why (the evidence — reproduce it, don't take it on faith)

A Phase-1 Sonnet acceptance run against `repos/chi-1.6.0` came out **`zero_citable: true`** — all 18 gathered docs demoted to background. Inspect `repos/chi-1.6.0/quality/classification_reads.json`:

- `13_api_reference.md` and `14_middleware_reference.md` were categorized `api-reference` (a *citable* category per the guide) but assigned **tier 4 (background)**. The recorded reasons demote them as "third-party API catalog, not chi's own published reference" and "compiled by an unnamed third party from 56 sources, not chi's own maintainers."
- The model, asked to explain, stated the **operative** rule was "not written by the project's own maintainers → background," applied uniformly to all 18 files; the real `Use(...) Router` signature error in `13` (chi's actual `Use()` returns void — verify against `chi.go` / `mux.go`) was *confirming evidence, not the deciding factor* (it demoted the error-free `14` on the same provenance rule).
- Contrast: the express acceptance run (`repos/express-accept/quality/classification_manifest.json`) promoted its `api-reference` doc to **Lane B `unconfirmed`** on the *same* third-party-compiled provenance (express's `docs_gathered` also ships a `sources.md`). So the bar is being applied **inconsistently** and **against §8a's own Lane B example**.

Three ways the provenance bar is wrong, all in §8a: (a) Lane B names chi/express `.md` API references as the unconfirmed-cite case; (b) the threat model de-emphasizes provenance; (c) gathered docs are third-party-compiled *by construction*, so "not maintainer-authored → background" defeats Feature G by design.

## Root cause

`references/phase1_exploration_guide.md` lists `api-reference` as a citable category (≈ line 45) and tells the model "Lane B — don't talk yourself out of a genuine spec" (≈ line 52), but it (1) never states that authorship provenance is **not** the bar, and (2) closes the classification section with "**On genuine ambiguity, background** — a missed grounding is recoverable, a false authoritative source poisons the derivation" (≈ line 71), which — with no provenance guard — gives the model cover to demote an authoritative-genre doc to background on a self-invented "maintainer-authored" rule. The bar is under-specified, so the model free-lances it.

## Tasks

1. **In `references/phase1_exploration_guide.md`, classification section (≈ lines 45–71), add explicit bar guidance** implementing §8a's new paragraph:
   - Authorship provenance — maintainer-authored vs. third-party-compiled — is **not** the promote/demote bar. Gathered documentation is third-party-compiled by construction (that is what dump-and-go produces), so "not written by the project's maintainers" is **never** a reason to demote.
   - The bar is **content-authority**: does the document read as a precise, contract-shaped reference/spec — concrete signatures, options, defaults, behavioral contracts?
   - An authoritative-**genre** document (spec / api-reference / rfc / contract) that reads as a precise contract but whose provenance or exact accuracy you are unsure of is a **Lane B `unconfirmed`** case — cited *and* surfaced — **not** background. Background is for documents that are background **in genre** (tutorial / guide / changelog / readme / retrospective).
   - A spotted inaccuracy in an authoritative-genre document does **not** demote it to background: it goes Lane B `unconfirmed` (so the operator and Phase 4 catch it) and may itself be a Phase 3/4 doc-vs-code discrepancy finding.
2. **Narrow the "on genuine ambiguity, background" line (≈ line 71)** so it is scoped to ambiguity **of genre** (cannot tell a spec from a guide → `candidate-spec` / background). It must not read as license to demote an authoritative-genre doc over provenance or minor-accuracy doubt. Preserve the conservative failure direction for genuinely genre-ambiguous docs; do not weaken the Lane C backstop (CVE/GHSA identifier, advisory URL, implementation-source file → operator-confirmation-required) at all.
3. **If `phase_prompts/phase1.md` (≈ line 285) restates the bar** in a way that could reinforce the provenance reading, bring its one-line summary in line; otherwise leave it (it delegates to the guide).
4. **Check `scripts/doc_classification.py`** — the lane mechanics and the `classification_review` operator-facing show. This is a model-judgment fix, so likely **no logic change**. Only edit if the show's wording implies provenance is the bar; keep any change surgical and note it.

## Acceptance criteria (pass/fail each)

1. The guidance in `references/phase1_exploration_guide.md` explicitly states: provenance is not the bar; the bar is content-authority; authoritative-genre-but-uncertain → Lane B `unconfirmed`, not background; a spotted inaccuracy → Lane B `unconfirmed`, not background. (Checkable in the text.)
2. The "on genuine ambiguity, background" guidance is scoped to genre ambiguity, not provenance/accuracy uncertainty.
3. **Regression fixture added to the classification test suite**: a compiled, authoritative-genre reference (e.g. an `api-reference`) that the model-read marks authoritative — including one variant carrying a single spotted inaccuracy — routes to **Lane B (`floor_rule: "llm"`, `confirmation: "unconfirmed"`, tier 1/2)**, NOT background. The fixture must be a real assertion of the lane mechanics (not vacuous). Note plainly in the output that the *model's judgment* itself cannot be unit-tested — the fixture pins the mechanics and the guidance text pins the judgment.
4. **No regression:** the Lane C backstop (CVE/GHSA, advisory URL, implementation-source → `operator-confirmation-required`) is unchanged; `zero_citable` / `unconfirmed_citable_count` / `awaiting_confirmation_count` disclosure still fire; express-style Lane B promotion still works; the conservative direction still holds for genre-ambiguous docs.
5. Full suite green (`python3 -m unittest discover bin/tests` and the gate suite per `DEVELOPMENT_CONTEXT.md`); `quality_gate.py` passes on a benchmark repo.

## Self-Council (Protocol 1) — 3 panelists, iterate to unanimous SHIP

- **Panelist A — spec fidelity.** Does the revised guidance faithfully implement §8a's "content-authority, not authorship provenance" paragraph and the Lane B intent (authoritative-genre-but-uncertain → Lane B `unconfirmed`)? Does it remove the provenance gate without over-correcting into "cite everything"?
- **Panelist B — regression safety.** Lane C backstop intact? Disclosure (`zero_citable`, unconfirmed/awaiting counts) intact? Conservative direction preserved for genuinely genre-ambiguous docs? Express Lane B path unbroken? Is the new fixture a real, non-vacuous assertion of the lane routing?
- **Panelist C — minimal-surface / no mechanical over-reach.** Is the change guidance-first (text where the bar is a model judgment), touching `doc_classification.py` only if the show wording genuinely implies provenance? No stray logic changes that would harden a model-judgment into mechanical policy?

Write panelist verdicts under `reviews/v034_self_council/`, synthesize, iterate the fix until all three SHIP, then write the output.

## Output

Write `outputs/034-classifier-bar-content-authority.md` per the runner schema (status; files changed with line notes; the exact guidance diff quoted; acceptance criteria pass/fail each; Council verdict + path to `reviews/` artifacts; commit SHA if you committed). Then rewrite `STATUS.md`.
