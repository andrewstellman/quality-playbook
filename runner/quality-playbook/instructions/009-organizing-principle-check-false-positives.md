# Instruction 009 — v1.6.0 Feature C: fix false positives in the organizing-principle render-contract check

The organizing-principle check (`check_render_contract`, added instruction 006) **false-FAILs well-formed documents**. A 2026-07-21 three-repo test (Opus on chi/express/virtio, all post-008) produced three documents that each stated a named organizing principle *with* a clear rationale — and all three FAILed the check, for two distinct brittle reasons. This is a check-accuracy fix (the check is wrong), not a generation fix (the docs are right).

## The evidence (reproduce, don't trust)
On `repos/{chi,express,virtio}-t3/quality/REQUIREMENTS.md` (all H2 sections, F-1 present, sequential IDs — otherwise clean):

**Bug A — the rationale-connector regex is too narrow (chi, virtio).** `_RENDER_PRINCIPLE_RATIONALE_RE` (`quality_gate.py:7260-7264`) matches `because|since|as this|as it|to reflect|reflects|reflecting|so that|which lets|given that`. It does **not** match:
- chi's connector **"so"** (bare): *"…a router library is consumed feature-by-feature… **so** a capability grouping matches how the primary reader navigates."* (the regex has `so that`, not bare `so`).
- virtio's explicit label **"Rationale:"**: *"Organizing principle: functional hierarchy by virtio protocol subsystem. **Rationale:** the virtio specification is itself structured by protocol subsystem…"*

Both are unambiguous rationales; both FAIL. Last round a virtio doc passed *only because* it happened to use "because." The check recognizes one phrasing of a thing that has many.

**Bug B — the search zone excludes a principle placed at the top of the first section (express).** `_render_organizing_principle_stated(text, first_section_offset)` (`quality_gate.py:7267+`) looks only in `text[:first_section_offset]` — the zone *before* the first requirement section. express placed a fully-valid principle+rationale as a blockquote **immediately under the first section heading** (`## Response generation (res)` → `> Organizing principle: object/entity… because Express's public API is structured around exactly those objects…`). It contains "because" and would pass the regex, but sits just after `first_section_offset`, so the check reports "no organizing principle stated at the top." The guide's phrase "top of the section list" is ambiguous — express read it as "top of the first section."

## Work items

### 1. Make rationale detection robust, not connector-keyword-brittle (`quality_gate.py`)
The core defect is detecting "is there a reason given" by matching a fixed connector list — every widening misses the next valid phrasing. Prefer a **structural** test over an ever-growing keyword list: within the paragraph (or blockquote) that names the principle, a rationale is present if there is **substantive explanatory content beyond merely naming the principle** — e.g. the naming clause is followed by a reason clause / additional sentence(s) that justify the choice. A bare "Organized by feature." with no explanation must still FAIL.

If you keep a keyword component as one signal, it must at minimum also recognize bare **"so"**, an explicit **"Rationale:"** / **"rationale"** label, and common connectors (**thus, hence, in order to, this matches/fits, chosen because, rejected … because**) — but do not rely on the keyword list alone; the structural "has explanatory content" test is what makes it robust. Document that rationale *quality* remains a Feature D / Council-rubric judgment; the mechanical check only confirms a rationale is *present*.

**Mutation-bite it:** each of the three real phrasings passes — `"…grouped by feature, so a capability grouping matches…"`, `"…by subsystem. Rationale: the spec is structured that way…"`, `"…by object because the API maps to objects…"`; and a bare `"Organized by feature."` (name only, no reason) FAILs. A check that only passes the "because" phrasing is the bug.

### 2. Widen the search zone to where a principle is legitimately placed (`quality_gate.py`)
Accept the principle+rationale when it appears in any of the legitimate placements: (a) a standalone paragraph after Actors & roles and before the first requirement section (chi/virtio); (b) a labelled `## Organizing principle` section; (c) at the very top of the first requirement section (express's blockquote). Extend the zone to include the intro/top of the first requirement section, or detect a labelled `## Organizing principle` heading wherever it sits. Do not accept a principle buried deep inside a mid-document section — "prominent, near the section list" is the intent.

**Mutation-bite it:** a principle stated at the top of the first section PASSES; a principle mentioned only in passing deep in section 4 does not satisfy the check.

### 3. Disambiguate the guide's placement instruction (`references/phase2_generation_guide.md`)
"Top of the section list" caused express to place the principle inside the first section. Clarify — with the worked example — that the organizing-principle statement is its **own paragraph (or a labelled `## Organizing principle` block) placed after Actors & roles and immediately before the first requirement section**, and that its rationale (the *why this principle*) must be in the same paragraph that names it. This is prevention to complement the check-robustness fix.

## Scope / discipline
Check accuracy + zone + guide clarity for the organizing principle only. Do NOT weaken the check to always-pass (a name-only statement with no rationale must still FAIL, and a document with no principle at all must still FAIL). Do NOT hand-edit fixtures to pass; add fixtures for the three real phrasings and the placements. Do NOT touch Track 2.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight, `pre-flight-aborted` if wrong. Local commits only; never push/merge.
- Self-Council per §13: charters for (a) rationale-detection robustness incl. the four mutation bites (three phrasings pass, name-only fails), (b) the zone widening incl. its mutation bites (top-of-first-section passes, buried-mention fails), (c) guide-clarity + no-weakening (a principle-less doc still FAILs). Each mutating panelist gets its own worktree. Artifacts under `RUNNER_ROOT/reviews/009_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_009_Self_Council/`.
- Verify the full suite; report counts + Python version.
- **Verification against the real docs:** after the fix, running `check_render_contract` on `repos/{chi,express,virtio}-t3/quality/` must no longer FAIL on the organizing principle (they are genuinely well-formed). Report the before/after for each. (These are live-run outputs, not golden fixtures — safe to read.)
- Output `outputs/009-organizing-principle-check-false-positives.md`: the rationale-robustness approach chosen (structural vs keyword), the three real docs now passing, the mutation results, and anything in §5.2 you found underspecified.
