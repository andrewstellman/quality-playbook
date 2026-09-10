# Instruction 032 — v1.6.0: classifier-cache footgun + two operator-facing polish fixes

Three small, pre-publish fixes surfaced by the chi/express acceptance runs and the v1.5.10↔v1.6.0 Phase-1 timing baselines. None changes a phase's shape; all three are corrections to existing 1.6.0 behavior. Do all three.

## Read first
- `plugins/quality-playbook/skills/quality-playbook/scripts/doc_classification.py` — `classify_documents` (the `prior_records` reuse branch, ~L688–766), `_newly_overridden` (~L573), `RULE_DEFAULT`/`CLASSIFIER_UNWIRED`/`CLASSIFIER_WIRED_OK` (~L65–94), the advisory-URL hard signal (`_ADVISORY_URL_RE` ~L155, its `Decision(... RULE_ADVISORY ...)` at ~L453), and the plain-language advisory reason in `classification_review` (~L917). Fixes 1 and 2.
- `plugins/quality-playbook/skills/quality-playbook/scripts/persona_apply.py` — the `persona_review_summary.json` constant + its 6 references (disclosure text, `revert_from_disk`, the `.undone.json` name). Fix 3.
- `plugins/quality-playbook/skills/quality-playbook/phase_prompts/phase2.md` + `bin/tests/test_persona_pipeline_v160.py` + `bin/tests/test_virtio_run_fixes_031.py` — the other live references to that filename (rename targets for fix 3).
- `docs/design/QPB_v1.6.0_Design.md` §8a (classification floor + cache + reproducibility) and §8b (persona pass) — the canonical behavior these fixes must stay consistent with. Read both sections end-to-end before editing; if a fix requires a design note, add it.
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Fix 1 — a live classifier must not be silently swallowed by the reproducibility cache
**Symptom (reproduced independently by two sonnet acceptance sub-agents, chi + a fresh virtio baseline).** The documented "you are the classifier" flow is: run the bare (unwired) ingest, then refine tiers. An agent that instead re-runs `ingest()`/`classify_documents()` **passing a live `llm_classifier` callable** gets it silently ignored: the first unwired ingest froze every doc at `floor_rule: "default-tier4"`, and on the second call the content-keyed `prior_records` cache matches each doc by sha and reuses the stale default — so the classifier never fires and the corpus stays all-Tier-4. The agent burns time diagnosing "why did 0 docs promote?", and an agent that does NOT notice ships a **silent `zero_citable` run** — the exact virtio failure mode Feature G exists to prevent.

**Fix.** In `classify_documents`, a cached record whose `floor_rule == RULE_DEFAULT` means "no classifier tier was ever assigned" — a bare unwired default, not a real decision. When a live classifier is available (`llm_classifier is not None`) and the cached record is that bare default, **do not reuse it** — discard the cache for that doc and re-derive so the classifier runs. This is additive to the existing override-bypass logic (`_newly_overridden`); place it so it fires for the plain unwired→wired case.

**Invariants (do NOT weaken).**
- A **genuinely-classified** cached record (`floor_rule: "llm"`, or any real floor rule) is still reused unchanged — reproducibility for unchanged, already-tiered content is preserved (Design §8a).
- The documented **edit-the-manifest-then-re-ingest-unwired** flow (which passes NO callable) is untouched: with `llm_classifier is None` the new branch cannot fire, so a hand-tiered `default-tier4→llm` record still stands.
- No floor is weakened: the classifier still cannot override a hard floor (advisory/injection remain), and content still cannot self-promote. Only the bare unclassified default is re-opened to the classifier.

## Fix 2 — the advisory-floor reason must be accurate for docs that merely *cite* advisory URLs
**Symptom (express run).** `_ADVISORY_URL_RE` matches an advisory-site URL (`snyk.io`, `cvedetails.com`, `nvd.nist.gov`, …) **anywhere** in content, so a bibliography / index / sources / collection-summary doc that only *references* those URLs floors to Tier 4 — correct outcome — but the operator-facing plain-language reason (`classification_review`, ~L917) tells them *"it's a security advisory — it describes known problems, not what your software is supposed to do."* That is factually wrong for `INDEX.md`, `sources.md`, `COLLECTION_SUMMARY.txt`: they are meta-documents about the doc set, not advisories. Verified: a `sources.md` listing `https://snyk.io/...` yields `reason: advisory (hard signal): advisory URL 'snyk.io'` and the "it's a security advisory" plain-language line.

**Fix.** Keep the Tier-4 floor (demotion is correct and safe — these are background). Make the **operator-facing reason accurate**: a doc floored because it *references* a security-advisory source must not be described as *being* a security advisory. Reword so the reason reflects what was actually detected (e.g. it points to / cites security-advisory sources, so it reads as background rather than a specification) — phrasing that is true for both a real advisory and a bibliography that cites one. Do not claim the document "describes known problems" on the strength of a URL match alone. (A CVE/GHSA-id match in the doc's own text is a stronger "is an advisory" signal than a bare URL reference — you may distinguish the two reasons if that yields cleaner accuracy, but it is not required; the bar is that a URL-only match never asserts the document *is* an advisory.)

**Invariant (do NOT weaken).** The advisory floor still fires on the same hard signals; tiers are unchanged. This is a reason-string accuracy fix, not a floor change. The 025 operator advisory-rescue path is untouched.

## Fix 3 — rename `persona_review_summary.json` (the last internal label reaching an operator)
**Symptom.** Every operator-facing surface of the persona pass is otherwise jargon-free ("expert reviewers"), but the disclosure and the artifact path still name `quality/persona_review_summary.json` — the one place the word "persona" reaches an operator. Both chi and express sub-agents flagged it; it is 031's own carry-forward #8.

**Fix.** Rename the artifact to a jargon-free name (recommend `expert_review_summary.json`; likewise `..._review_summary.undone.json` → the matching undone name). Update **every live reference**: the constant(s) and all 6 uses in `persona_apply.py` (including the plain-language disclosure text and `revert_from_disk`'s read + the `.undone.json` rename), `phase_prompts/phase2.md`, and the two tests (`test_persona_pipeline_v160.py`, `test_virtio_run_fixes_031.py`). Grep the skill tree + `bin/tests` + `references/` + `schemas.md` afterward to confirm no live literal `persona_review_summary` remains. **Do NOT edit** the frozen Council synthesis records under `docs/process/QPB_v1.6.0_Instruction_0{21,22,29,31}_Self_Council/` — those are historical artifacts.

**Invariant.** Pure rename — no behavior change. The write → disclose → review → `revert_from_disk` round-trip must still work end-to-end under the new name (including the four refusal states 031 built), and the disclosure must still name the new path correctly.

## Acceptance oracle
1. **Fix 1:** a two-step sequence — unwired `classify_documents` (no classifier) producing all-`default-tier4`, then a re-run passing a classifier that tiers a doc to 1/2 — promotes that doc (classifier fires); test it. A genuinely-classified prior record (`floor_rule: "llm"`) is still reused on an unchanged-content re-run (reproducibility intact). With `llm_classifier is None`, a hand-edited `llm` record still stands (documented flow intact). Content still cannot self-promote; a hard advisory/injection floor still cannot be overridden by the classifier.
2. **Fix 2:** a bibliography/sources/index doc that only cites an advisory URL floors to Tier 4 with a reason that does NOT assert it is a security advisory (build the express `sources.md`/`INDEX.md` case). A real advisory (CVE/GHSA id or advisory content) still floors and reads as background. Tiers unchanged from before.
3. **Fix 3:** the review summary artifact is written, disclosed, and reverted under the new jargon-free name; no live literal `persona_review_summary` remains (grep-clean, excluding the frozen `docs/process/` records); the disclosure names the new path.
4. Full suite green.

## Fixture discipline
Do NOT hand-edit golden fixtures. New/updated fixtures (the unwired→wired promotion, the accurate advisory reason, the renamed artifact round-trip) are expected. Any golden that hard-codes the old filename is updated by regeneration, not by hand.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**. Touches QPB source (`doc_classification.py`, `persona_apply.py`, `phase2.md`, tests) — leave the orchestrator's uncommitted `docs/design/` edits and this mailbox alone.
- Self-Council per §13 — three charters: (a) **fix 1 correctness** — rescues the unwired→wired case without breaking reproducibility, the documented edit-flow, or any floor; content still can't self-promote; mutation-bitten. (b) **fix 2** — reason accuracy with the advisory floor and all tiers unchanged. (c) **fix 3** — complete rename, working write/disclose/revert round-trip, no jargon leak, frozen records untouched. Artifacts under `RUNNER_ROOT/reviews/032_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_032_Self_Council/`. Iterate to unanimous SHIP before declaring done.
- Verify the full suite; report counts + Python version.
- Output `outputs/032-classifier-cache-and-polish.md`: each fix before/after + its test; the fix-1 unwired→wired promotion proof AND the reproducibility-preserved proof; the fix-2 accurate-reason sample (before/after wording); the fix-3 grep-clean confirmation + round-trip; remaining release items.
