# Quality Playbook v1.5.10 — Implementation Plan

*Companion to: `QPB_v1.5.10_Design.md`*

*Status: created 2026-06-07. Inherits the broader-scope phases originally drafted as v1.5.9, deferred when v1.5.9 was scoped down. Implementation begins after v1.5.9 ships.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Operating Principles

- **v1.5.10 picks per-item priorities** at implementation start based on what's empirically most blocking after v1.5.9 ships. The design enumerates 1 ship-gate feature + 8 capabilities (B-1 through B-8); v1.5.10 likely won't implement all of them. Default subset: ship-gate Part 1 + B-1 + B-8.
- **Worker-lane edits** for all source changes. Cowork files instructions; worker implements; Council reviews.
- **Per-capability sub-phasing.** Each B-N capability has its own implementation sub-phase + Council review. Skip-able if the capability is deferred.

---

## Phase 0 — v1.5.9 Stabilization Confirmation

Before any v1.5.10 work begins, confirm v1.5.9 has fully shipped:

- `v1.5.9` tag on origin
- `1.5.9` branch merged to `main`
- pip + npm + awesome-copilot (if applicable) channels published
- Harness-as-skill MVP validated and `bin/harness/` Python code deleted (or marked for deletion)
- SKILL.md trim complete; token-ceiling test ratcheted to the post-trim size

**Worker instruction at start of v1.5.10:** `cd ~/Documents/QPB && git checkout main && git pull && git checkout -b 1.5.10 && git push -u origin 1.5.10`.

---

## Phase 1 — Methodology absorption sweep

Per Design § Part 4. Verify the following lessons are documented in `ai_context/DEVELOPMENT_PROCESS.md`; if any are missing, file a micro-instruction for each:

- Patch-authoring discipline (2026-06-06 gson PR origin)
- Multi-step shell discipline (2026-06-06 gson recovery origin)
- Velocity-pressure self-imposed deadline pattern (2026-06-06 cross-chat audit origin)

This phase is cheap (one read of DEVELOPMENT_PROCESS.md + at most a few small instructions). Land it FIRST so feature work doesn't reintroduce the patterns these lessons protect against.

---

## Phase 2 — Ship-gate feature (Design § Part 1)

### Phase 2A — Architectural choice (Design § 1.5)

Operator picks: extend `quality_gate.py` vs new `bin/skill_gate.py` vs external. Recommended default: extend `quality_gate.py` with a sub-module pattern.

### Phase 2B — Mechanical invariants (Design § 1.1)

Implement the per-file invariants. Each invariant gets a regression test + AUDIT-table entry where applicable.

### Phase 2C — Cross-artifact consistency invariants (Design § 1.2)

Implement the across-file invariants.

### Phase 2D — Semantic Council audit prompt (Design § 1.3)

Author the audit prompt. Run it against the v1.5.10 trimmed SKILL.md as the first empirical test of the prompt's signal-to-noise.

### Phase 2E — Bootstrap-as-regression-test framing (Design § 1.4)

Wire the bootstrap run into the release-prep gate. Expected-bug set lives in `docs/regression/bootstrap_expected_bugs.json` (new file). Gate FAILS if recall drops or false-positive count rises.

### Phase 2 Ship Gate

- Self-Council Protocol 1 with three panelists (invariant correctness, consistency-check soundness, regression-test framing sanity)
- All gates green on a fresh QPB build

---

## Phase 3 — Capability B-1 (Prompt-injection isolation)

### Phase 3A — Sanitization pass

Phase 1 ingestion adds a sanitization step over `reference_docs/` content. Strip patterns: code-block executables, "ignore previous instructions"-class phrases, structured roleplay attempts.

### Phase 3B — Reference doc isolation

Tier 4 content gets a clearly-labeled "untrusted data, not instructions" wrapper in the Phase 1 prompt. Agent's prompt template updated.

### Phase 3C — Test fixture

Create a small benchmark repo with prompt-injection-laden `reference_docs/`. Verify the agent classifies it correctly (as data, not instructions).

### Phase 3 Ship Gate

- Self-Council Protocol 1
- Empirical fixture run shows the agent did NOT follow the injection attempts

---

## Phase 4 — Capability B-8 (Weak-assertion detection)

### Phase 4A — Layer 1 static pattern detection (Design § 2.8 Layer 1)

Implement scanner for known weak-assertion patterns (try/catch+assertTrue(true), empty assertThrows, generic exception in assertThrows, etc.). Block weak-test marking.

### Phase 4B — Layer 2 adversarial test critique (Design § 2.8 Layer 2)

Add the adversarial critique sub-pass to Phase 3 verification. Test that "passes for the wrong reason" gets rejected.

### Phase 4C — Layer 3 counterfactual mutation (optional, benchmark-mode only) (Design § 2.8 Layer 3)

Implement only if benchmark validation budget supports it. Defer if expensive.

### Phase 4D — Bugspec coordination

Surface this work to the bugspec maintainers (Andrew) for v0.3.3+ adoption.

### Phase 4 Ship Gate

- Self-Council Protocol 1
- Mutation-verified pin tests: a known-weak test from past QPB runs (gson #3035 pre-203 pattern) gets correctly rejected by both Layer 1 and Layer 2

---

## Phase 5 — Remaining B-N capabilities (deferrable)

These are documented in Design § 2.1-2.7. Each has its own sub-phase if implemented, or moves to v1.5.11.

- B-2: Phase-isolated improvement loop for security-bug targeting (Design § 2.2)
- B-3: Harness resume/iterate semantics (Design § 2.3)
- B-4: Bug-neighborhood iteration strategy (Design § 2.4)
- B-5: Adversarial fresh-context review pass (Design § 2.5)
- B-6: Combine related findings into single coherent PR (Design § 2.6)
- B-7: Phase 7 bugspec-format emit (Design § 2.7)

Operator decides at Phase 5 entry which to land in v1.5.10. Default: defer all to v1.5.11 unless one becomes blocking.

---

## Phase 6 — Release prep + ship

After all selected phases ship:

- Version stamps to `1.5.10`
- README + TOOLKIT + DEVELOPMENT_CONTEXT updates for any user-visible changes
- CHANGELOG entry
- Council umbrella review
- Tag + release close-out per `DEVELOPMENT_PROCESS.md` § Release close-out sequence
- Merge to main
- Branch next version off main

---

## Sequencing summary

```
Phase 0 (v1.5.9 stabilization) ──→ Phase 1 (methodology absorption) ─┐
                                                                     ↓
Phase 2 (ship-gate) ─────┐
                         ├──→ Phase 6 (release ship) ──→ v1.5.10 tag
Phase 3 (B-1) ───────────┤
Phase 4 (B-8) ───────────┘
(Phase 5 capabilities — operator's pick; may all defer to v1.5.11)
```

Phases 2-4 are parallelizable.

---

## Council coordination notes

- Per-capability Council reviews use Self-Council Protocol 1
- The §1.3 semantic Council audit prompt becomes a NEW Council variant; first empirical use is on v1.5.10's own work
- Defensive-sweep charter from 207 applies to all content-fix sub-instructions during v1.5.10

---

## Open work-items tracker

| # | Item | Phase | Status |
|---|------|-------|--------|
| 1 | Verify methodology absorptions in DEVELOPMENT_PROCESS.md | 1 | Pending — first concrete step |
| 2 | Architectural choice for ship-gate (Design § 1.5) | 2A | Pending operator decision |
| 3 | Mechanical invariants implementation | 2B | Pending 2A |
| 4 | Cross-artifact consistency invariants | 2C | Pending 2A |
| 5 | Semantic Council audit prompt | 2D | Pending 2A |
| 6 | Bootstrap-as-regression-test | 2E | Pending 2A |
| 7 | Prompt-injection sanitization (B-1) | 3 | Pending |
| 8 | Weak-assertion Layer 1 static detection (B-8) | 4A | Pending |
| 9 | Weak-assertion Layer 2 adversarial critique (B-8) | 4B | Pending |
| 10 | B-2..B-7 capability scoping decision | 5 | Pending operator decision at Phase 5 entry |
| 11 | Release ship steps 1-8 | 6 | Pending Phase 2 + Phase 3 + Phase 4 ship gates |

---

*End of v1.5.10 Implementation Plan. Design in `QPB_v1.5.10_Design.md`. Predecessor scope in `QPB_v1.5.9_Design.md` + `QPB_v1.5.9_Implementation_Plan.md`.*
