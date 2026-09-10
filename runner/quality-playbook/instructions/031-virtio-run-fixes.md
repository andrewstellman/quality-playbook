# Instruction 031 — v1.6.0: three fixes from the virtio phase 1–3 acceptance run

A fresh sonnet run of virtio phases 1–3 confirmed the 030 classification review works end-to-end (plain-language show, zero-citable surfaced, operator promotion recovers the spec → requirements cite it). It also surfaced three real defects. Fix all three.

## Fix 1 — the classification-review "worked example" suggests the WRONG file (030 defect)
**Symptom:** when the show invites the operator to name their spec, its example picks the **largest background doc by byte size** — for virtio that's `linux-coding-style.rst` (a Linux style guide, 45 KB) instead of the actual spec `virtio-spec-behavioral-contracts.md` (7.8 KB). The feature we built to help the operator recover a mis-classified spec actively suggests promoting a **style guide** as their specification. The code's own comment admits it only fixed an earlier alphabetical-pick bug; the size heuristic still can't tell a style guide from a spec.
**Fix:** the worked example must not confidently name a document that isn't plausibly a specification. Prefer **name/content signals** that identify a likely spec (filename or title containing `spec`, `specification`, `contract`, `reference`, `protocol`, `api`, `rfc`, `standard`; or the doc self-identifying as one) over byte size. **If no background doc plausibly looks like a spec, use a neutral placeholder** in the example (e.g. *"treat `<the-file>` as my specification"`) rather than naming a real, wrong file. Never suggest a doc whose only qualification is being the largest. (Location: the worked-example / suggestion logic in `doc_classification.classification_review` in `plugins/quality-playbook/skills/quality-playbook/scripts/doc_classification.py`.)

## Fix 2 — the persona pass is not disclosed in the end-of-Phase-2 operator message (transparency)
**Symptom:** the persona validation pass runs at the Phase 2→3 boundary and **auto-applies grounded changes to the requirements**, but the standard end-of-Phase-2 operator message (`references/what_just_happened.md`, State P2) has **no mention** that it ran or that the requirements were modified. An operator relying on the standard message never learns their spec was auto-changed unless they separately open `persona_review_summary.json`. This violates the release's "surface, don't silently apply" / operator-visibility principle.
**Fix:** when the persona pass has run, the end-of-Phase-2 message must **disclose it in plain language** — that expert reviewers checked the requirements and what they did (added / changed / flagged-as-candidate counts), with a pointer to review the changes and that they can be undone. Plain language (no "Feature H", "agent-validation", "persona" internal jargon — say "expert reviewers" / "I had reviewers double-check your requirements"). Consistent with the 030 UX plain-language standard (see `~/Documents/AI-Driven Development/Quality Playbook/QPB_v1.6.0_UX_Language_Draft.md`). If the pass did NOT run (disabled / no operator), no disclosure is added.

## Fix 3 — setup_repos.sh produces an install that blocks Phase 0 on missing scaffolding
**Symptom:** a benchmark repo built by `setup_repos.sh` is missing `ai_context/TOOLKIT.md`, `skill-template.gitignore`, and the `.gitignore` QPB sentinel, so Phase 0 returns `status=blocked` on every benchmark run. 028 fixed the validator's *layout* recognition but not the missing files. (Real adopter installs via `install_skill.py` stage these, so this is benchmark-only — but it blocks every benchmark run.)
**Fix:** make `repos/setup_repos.sh` stage `skill-template.gitignore` + `ai_context/TOOLKIT.md` into the target and create the target `.gitignore` with the `quality/` sentinel — so a freshly set-up benchmark repo validates Phase 0 clean (matching what `install_skill.py` produces). Do NOT weaken the validator's requirement; complete the benchmark install.

## Read first
- `plugins/quality-playbook/skills/quality-playbook/scripts/doc_classification.py` — `classification_review` (fix 1).
- `references/what_just_happened.md` (State P2) + `references/requirements_pipeline.md` §E.9 — the end-of-Phase-2 message (fix 2); the persona-pass outputs (`persona_review_summary.json`, its applied/candidate/conflict counts).
- `repos/setup_repos.sh` + `install_skill.py` (what a real install stages) — fix 3.
- `~/Documents/AI-Driven Development/Quality Playbook/QPB_v1.6.0_UX_Language_Draft.md` — plain-language standard for fix 2.

## Acceptance oracle
1. **Fix 1:** given a corpus whose only spec-like doc is smaller than a large non-spec doc (build the virtio case: `virtio-spec-behavioral-contracts.md` vs `linux-coding-style.rst`), the worked example either names the spec-like doc or uses a neutral placeholder — it does NOT name the style guide. Test it.
2. **Fix 2:** an end-of-Phase-2 message after a persona pass that applied changes discloses (plain-language, no internal jargon) that reviewers ran + what they changed + that it's reviewable/revertible; a run where the pass didn't run adds no such disclosure.
3. **Fix 3:** a `setup_repos.sh` target validates Phase 0 clean (the three scaffolding items present); the validator is unchanged.
4. Full suite green.

## Fixture discipline
Do NOT hand-edit golden fixtures. New fixtures (the spec-vs-style-guide worked example, the persona disclosure present/absent, the Phase-0-clean benchmark) are expected.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**.
- Self-Council per §13 — focused (fix 1 touches the operator-facing 030 show; fix 2 the operator-visibility message; fix 3 benchmark setup): (a) fix 1 never suggests a non-spec doc; (b) fix 2 discloses the persona pass in plain language when-and-only-when it ran, no jargon; (c) fix 3 completes the install without weakening the validator. Artifacts under `RUNNER_ROOT/reviews/031_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_031_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/031-virtio-run-fixes.md`: each fix before/after + its test; the worked-example spec-vs-style-guide result; the persona-disclosure sample (plain language); the Phase-0-clean benchmark proof; and remaining release items.
