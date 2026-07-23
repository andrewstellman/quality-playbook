# Instruction 024 — wire the LLM classifier + loud failures: self-Council synthesis

**Terminal verdict: unanimous SHIP** across all three charters, zero FIX-REQUIRED.
One non-blocking doc-honesty observation was fixed post-Council (a stale pre-023
line), prose-only, no product change.

This instruction fixes the *bigger* half of the virtio failure (Fable Q6): the
LLM classifier was never wired into the pipeline, so every non-floored doc silently
defaulted to Tier 4, and — with the 023 mis-floor — the whole corpus collapsed to
zero citable docs, silently. House rule: a degraded-capability path that silently
continues is the failure mode. Because it is correctness- and honesty-critical, a
full 3-charter self-Council ran (each panelist in its own worktree reset to the
reviewed commit `0c06e80`, each running a driver and mutation-biting).

## Charters + verdicts

- **A — The classifier is genuinely wired; floor precedence + downward-only
  preserved: SHIP.** `classify_reference_docs` threads the callback into
  `classify_documents`, which writes the new top-level fields to the on-disk
  manifest; a stubbed classifier lands an authoritative doc Tier 1/2. Floor
  precedence holds under a promote-all classifier (mutation-confirmed: making the
  classifier win over the floor reddens 8 floor tests). Hints are delivered to a
  3-arg classifier; the 2-arg path still works. The record-derived
  `classifier_status` upgrade cannot launder an advisory — a poisoned RULE_LLM
  prior on a CVE doc is defeated by the unrescuable-floor guard (tier stays 4); the
  status upgrade never changes a tier.

- **B — An unwired/failed classifier and a zero-citable corpus are impossible to
  miss: SHIP.** All three degraded states (unwired / error / zero-citable) fire on
  all three surfaces — the manifest `classifier_status`/`zero_citable` +
  `classification_disclosure`, the gate WARN, and the render+interview prose. The
  gate only ever WARNs (never FAILs) and is inert when the manifest is absent
  (a non-Feature-G run isn't penalized). The instruction's demanded mutation —
  "disable the classifier, confirm the run screams" — was verified, and each loud
  surface is mutation-confirmed load-bearing (silencing any one reddens a test).

- **C — No scope creep + no regression: SHIP.** The diff touches exactly the 7
  sanctioned files; the 023 floor logic and `reference_docs_ingest.py` are
  byte-unchanged (the new fields flow through automatically); the rescuable-ledger,
  Feature H, and render labeled-slots are untouched. The new top-level fields are
  additive — reproducibility/content-key contract intact. The `_accepts_hints`
  arity shim is safe across 14 callable shapes (no 2-arg-misread-as-3-arg
  TypeError). Every suite failure is environmental (gitignored `repos/*-t3/`
  absent in a fresh worktree).

## The design decision the Council scrutinized

The skill flow has **no Python classifier callback** — the agent classifies by
*refining the manifest* (assigning Tier 1/2, phase1_exploration_guide.md:43). A
naive "unwired = no callback" would WARN on every skill run even after the agent
classified. The **record-derived upgrade** resolves this: a no-callback run whose
(reused, agent-refined) records carry a `RULE_LLM` tier reads `wired-ok`, so the
WARN fires only on a genuinely floor-only corpus. Panelist A confirmed this opens
no integrity hole (a poisoned RULE_LLM prior is still re-floored by the
unrescuable-floor guard; the status upgrade never changes a tier). The prose
(behavior 1) requires re-running ingest after refinement so the status is fresh.

## Non-blocking observations

1. **A (fixed):** `phase1_exploration_guide.md:49` still called a security-genre
   *title* a Tier-4 floor and described the removed injection floor — stale after
   instruction 023 shrank the floor to hard signals, and contradicting the
   paragraph 024 added two lines above. Fixed in commit `07b5473` (prose-only): the
   line now says hard-signals-only (CVE/GHSA id + advisory URL) with
   genre-title/normative-density as advisory hints.
2. **C (no action):** a classifier with a keyword-only third arg
   (`def f(rel, text, *, hints)`) would fall back to the 2-arg call and TypeError —
   but that contradicts the documented positional-third convention and is not a
   common shape.
3. **Environmental (all three):** `CorpusTierDistributionTests` /
   `CorpusFormalDocCitabilityTests` / `test_setup_repos` need gitignored
   `repos/*-t3/` absent in fresh worktrees; they pass in the provisioned main
   checkout (full suite 2766/0/14).

## Verification
Full suite **2766 / 0 / 14**, Python 3.14.6. Reviewed commit `0c06e80` (the
wiring) + `07b5473` (the post-Council prose honesty fix).

**Terminal verdict: SHIP.** The classifier is wired at Phase-1 ingest, floor
precedence and downward-only hold, hints are delivered, and an
unwired/failed/zero-citable classification is impossible to miss on the manifest,
the gate, the Overview, and the interview — never a silent Tier-4 collapse.
