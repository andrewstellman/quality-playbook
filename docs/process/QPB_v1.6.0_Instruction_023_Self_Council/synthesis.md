# Instruction 023 — Feature G floor simplification: self-Council synthesis

**Terminal verdict: unanimous SHIP** across all three charters, zero FIX-REQUIRED.

This change loosens a security-relevant floor (the documentation-classification
advisory floor), so per §13 it ran a full 3-charter self-Council — no shortcut.
Three panelists, each in its own git worktree reset to the reviewed commit
`2882f31`, each RUNNING an adversarial driver and mutation-biting the retained
controls.

The change enforces the Fable review's frame: **which direction does a check fail,
and what does failing cost?** Demotion (floors) = availability; promotion
(content-sniffing into citable) = integrity, strictly more dangerous. The floor now
enforces only hard, unambiguous, structural facts; fuzzy genre/code signals became
advisory hints; **nothing becomes citable on content-sniffing alone.**

## Charters + verdicts

- **A — Downward-safety preserved: SHIP.** Every retained hard floor fires under a
  promote-all LLM, content-keyed and unrescuable-by-content, mutation-confirmed
  load-bearing: CVE/GHSA id, advisory URL (incl. in a renamed `.proto`), the impl
  EXTENSION floor, the contract carve-out, the sidecar-rescues-impl-only rule, and
  the poison/cache guard (`_UNRESCUABLE_FLOOR_RULES = {advisory, background}`). The
  **edit-5 deviation was scrutinized and cleared**: the injection FLOOR is
  genuinely gone (no `RULE_INJECTION` branch, in neither floor set), and the
  retained `injection_signature` still backs `persona_grounding.grounding_
  injection_signature` (Guard 1) — a safe downward-direction change with the
  grounding directive check + Tier-1/2 guard as the backstop. Bite: neutering
  `injection_signature` breaks the Guard-1 tier-claim arm, proving the retention is
  load-bearing.

- **B — No upward promotion on content alone: SHIP** (integrity direction,
  scrutinized hardest). No content-only path (no `llm_tier`, no contract/impl
  extension) reaches Tier 1/2. The `"$schema"` deletion and the generic-brace
  deletion close the upward false-positives (mutation-confirmed: re-adding
  `"$schema"` reddens two tests). The version anchors bite — bare `openapi:` /
  `swagger:` and wrong-version near-misses no longer promote. `git show 2882f31`
  confirms the integrity direction was strictly **tightened**, not loosened (the
  edit also removed the worse pre-existing bare-`"openapi":` JSON collision).

- **C — The fuzzy signals are flags, not decisions: SHIP.** The virtio case is
  fixed (a dense-MUST/SHALL neutral-title spec with no hard signal is not floored
  and flows to the classifier). Genre-title and code-density inform only — they
  never floor and never promote, and `inspect.getsource(_classify)` confirms the
  decision path never branches on `advisory_hints`/`code_heavy` (attached
  post-decision, read only in `_record`, emitted only when present so no-hint
  records stay byte-clean for the content-key/reproducibility contract). The
  density predicate and `_NORMATIVE_RE`/`_HARDENING_SUBJECT_RE` are fully gone.

## The edit-5 deviation (recorded, reviewed, cleared)

Instruction edit 5 said "Remove `injection_signature` (:282-287) and
`_INJECTION_RE`." That step assumes the function is used only by the classifier
floor — but `persona_grounding.grounding_injection_signature` **composes** it for
the Guard-1 tier-claim arm, a DIFFERENT load-bearing auto-apply control the same
instruction explicitly keeps and forbids touching, and the suite must stay green.
So the worker executed edit 5's *intent* — remove the injection FLOOR (the
`classify_document` branch + `RULE_INJECTION` from both floor-rule sets), the
actual harm the instruction targets — and **retained the detection helper** for
its legitimate downstream reuse, flagging the deviation. Panelist A verified the
floor is genuinely gone AND `persona_grounding` still works AND the change is
downward-safe. The eventual removal of this reuse belongs to the later Feature-H
directive-narrowing instruction.

## Non-blocking observations

1. **A (addressed):** no test isolated the tier-claim contribution of the retained
   `injection_signature` (the persona suite's `_POISON_TXT` over-determines it via
   `_AGENT_DIRECTIVE_RE`), so a future silent deletion of the function would pass
   the suite. Addressed in commit `37c1293`: a pure-tier-claim assertion added to
   `test_injection_signature_detected` pins the retained detector.
2. **B (pre-existing, not introduced):** a `.md` whose prose contains `openapi:
   3…` or a bare `asyncapi:` still content-promotes (prose collision). The yaml-form
   openapi + asyncapi alternations predate this instruction and were unchanged; the
   edit only removed the worse bare-`"openapi":` JSON collision. Left for a later
   pass if the prose-collision surface is judged worth tightening.
3. **Environmental (all three):** `CorpusTierDistributionTests` /
   `CorpusFormalDocCitabilityTests` read gitignored `repos/{chi,express}-t3/
   docs_gathered/` absent in fresh worktrees; they pass in the provisioned main
   checkout (full suite 2748/0/14).

## Verification
Full suite **2748 / 0 / 14**, Python 3.14.6. Reviewed commit `2882f31`
(implementation) + `37c1293` (the test pin from observation 1).

**Terminal verdict: SHIP.** The floor enforces only hard structural facts; the
fuzzy signals inform without deciding; nothing content-promotes beyond anchored
format markers; the retained hard floors survive a promote-all LLM; and the
edit-5 deviation preserves the load-bearing Guard-1 control without touching
`persona_grounding`.
