# Instruction 026 — Feature H directive-narrowing: self-Council synthesis

**Terminal verdict: unanimous SHIP** across all three charters, zero FIX-REQUIRED.

The simplification sweep flagged Feature H's injection-detection as over-complex;
Fable Q3 corrected the first instinct — two layers are safe to remove, but the third
(`persona_grounding._AGENT_DIRECTIVE_RE`) is **load-bearing** (it uniquely catches a
byte-verified citation whose content is an instruction, on the one path that
auto-applies into generated code) and must be **kept, narrowed**. Because it touches
the auto-apply injection defense, a full 3-charter self-Council ran (each panelist in
its own worktree reset to `14b166e`, each running an adversarial driver and
mutation-biting).

## What changed
1. **Narrowed `_AGENT_DIRECTIVE_RE`:** dropped the bare
   `the (agent|validator|reviewer|…) must/should/shall` arm (it false-positived on
   spec prose like "the validator MUST reject malformed input"); kept the
   add/confirm/cite/classify/register-requirement arms + a self-contained tier-claim
   arm.
2. **Deleted `persona_orchestration.detect_fabrication`** (verified dead — consumed
   by nothing) + the `PersonaRun.fabrication_flags` field, and corrected the module
   docstring (only staging + the tool allowlist are load-bearing isolation).
3. **Made grounding self-contained:** moved the tier-claim detection from
   `doc_classification.injection_signature` into `persona_grounding._TIER_CLAIM_RE`,
   then deleted `doc_classification.injection_signature` + `_INJECTION_RE` — no
   cross-module injection coupling, the classifier is judgment-free, and
   `persona_grounding` no longer imports `doc_classification`. (This completes the
   untangling instruction 023 deliberately deferred here.)
4. **Mutation-pinned the Tier-1/2 grounded-citation guard** — now the last mechanical
   line in the upward/integrity direction.

## Charters + verdicts

- **A — The narrowed directive check still blocks the bypass: SHIP.** All 23
  byte-verified-injection payloads land candidate (never grounded); the FP fix is
  genuine (9/9 spec-prose grounded). A coverage-gap probe reconstructed the dropped
  bare-authority arm and confirmed the only strings it uniquely caught are
  no-requirement-verb FP prose — **no real injection payload was lost**. Every
  retained arm is mutation-confirmed load-bearing.

- **B — The Tier-1/2 guard is load-bearing and pinned: SHIP.** Tier 1/2 grounds,
  Tier 3/4 → candidate, non-resolving → candidate; the mutation pin reddens both the
  new pin and the existing `test_cited_tier4_doc_is_candidate`; the grounded/candidate
  split has no regression (48/48); the tier check runs before byte-verify, so no
  low-tier or non-resolving doc can sneak through.

- **C — Dead-code removal + decoupling truly inert + honesty: SHIP.**
  `detect_fabrication` was genuinely dead (repo-wide grep: zero runtime consumers;
  `persona_apply` reads only `diff_set`/`persona_id`); the decoupling is clean
  (nothing imports the deleted helper; grounding self-contained; `doc_classification`
  still bundled for Feature G); `_TIER_CLAIM_RE` is byte-identical to the old regex
  (faithful move, no tier-claim coverage lost); the docstrings are honest.

## Non-blocking observations (recorded, not actioned)
1. **A:** the `add REQ` arm is strictly dominated by the `add…requirement` arm
   (redundant, loses zero coverage). Pre-existing (not introduced by 026), and the
   instruction *explicitly names it as a kept arm* — so it is retained; the
   redundancy is recorded for a future cleanup, not optimized here.
2. **C:** the historical `docs/design/QPB_v1.6.0_Design.md` still describes the
   fabrication-tell as a Verification-3 backstop — out of 026's scope (which scoped
   honesty corrections to the two code artifacts), a dated snapshot, and it frames
   the tell as a backstop *behind the still-live tool allowlist* (so no false
   primary-control claim). That file is also the orchestrator's uncommitted edit —
   left alone. Recorded for the orchestrator.

## Verification
Full suite **2777 / 0 / 14**, Python 3.14.6. Reviewed commit `14b166e`.

**Terminal verdict: SHIP.** The directive check is narrowed (FP fixed, bypass still
blocked), the dead fabrication-tell is gone with an honest docstring, grounding is
self-contained with a judgment-free classifier, and the Tier-1/2 guard — now the last
upward-direction line — is mutation-pinned.
