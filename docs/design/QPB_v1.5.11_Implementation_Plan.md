# Quality Playbook v1.5.11 — Implementation Plan

*Companion to: `QPB_v1.5.11_Design.md`*

*Status: created 2026-06-07 as `QPB_v1.5.10_Implementation_Plan.md`; **renumbered to v1.5.11 on 2026-06-11** (the SKILL.md trim became its own v1.5.10 release when v1.5.9 refocused on the harness + standalone distribution). Inherits the broader-scope phases originally drafted as v1.5.9, deferred when v1.5.9 was scoped down. Implementation begins after v1.5.10 ships.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Operating Principles

- **v1.5.11 picks per-item priorities** at implementation start based on what's empirically most blocking after v1.5.9 ships. The design enumerates 1 ship-gate feature + 8 capabilities (B-1 through B-8); v1.5.11 likely won't implement all of them. Default subset: ship-gate Part 1 + B-1 + B-8.
- **Worker-lane edits** for all source changes. Cowork files instructions; worker implements; Council reviews.
- **Per-capability sub-phasing.** Each B-N capability has its own implementation sub-phase + Council review. Skip-able if the capability is deferred.

---

## Phase 0 — v1.5.9 Stabilization Confirmation

Before any v1.5.11 work begins, confirm v1.5.9 has fully shipped:

- `v1.5.9` tag on origin
- `1.5.9` branch merged to `main`
- pip + npm + awesome-copilot (if applicable) channels published
- Harness-as-skill MVP validated and `bin/harness/` Python code deleted (or marked for deletion)
- SKILL.md trim complete; token-ceiling test ratcheted to the post-trim size

**Worker instruction at start of v1.5.11:** `cd ~/Documents/QPB && git checkout main && git pull && git checkout -b 1.5.10 && git push -u origin 1.5.10`.

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

Author the audit prompt. Run it against the v1.5.11 trimmed SKILL.md as the first empirical test of the prompt's signal-to-noise.

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

## Phase 5 — Capability B-9 (Fix cost/benefit evaluation)

**Per Design § 2.9.** Origin: 2026-06-08 closure of gson PR #3036 after Marcono1234's review surfaced that the fix's per-call overhead wasn't justified by the bug's rare incidence. The lesson: QPB Phase 6 verifies bug-exists + fix-correct; it doesn't evaluate fix-worth-shipping. B-9 closes that gap.

### Phase 5A — Evaluation sub-pass scaffold

Add a new sub-pass between Phase 5 (reconcile) and Phase 6 (verify) that evaluates each TDD-verified bug across the five dimensions enumerated in Design § 2.9: incidence, fix overhead distribution, security framing, architectural cost, symmetry-as-contract.

Output schema: a per-bug classification (SHIP-WORTHY / OPT-IN-WORTHY / LOCAL-FIX-WORTHY / DEFENSIVE-NOTE) plus a one-paragraph rationale per dimension. Lives at `quality/fix_evaluation.json` (new artifact).

### Phase 5B — Static analysis hooks for incidence + overhead

The evaluation needs measurable inputs. Build:

- **Incidence estimator**: count trigger-condition occurrences in the target codebase via the existing role-map traversal. Cross-reference with QPB's existing benchmark corpus to calibrate "common case" thresholds empirically.
- **Overhead estimator**: static analysis of the fix's locus — does it add work in the hot path (every map serialization) or only in the bug-trigger path (when a specific condition is met)?
- **Security framing classifier**: cross-reference the bug's category (read-side parser input vs. write-side output emission vs. logic vs. state mutation) with known CVE patterns.

### Phase 5C — Integration with B-7 (bugspec emit) and B-6 (combine PRs)

Phase 7 bugspec emission becomes classification-aware: only SHIP-WORTHY bugs get emitted by default. OPT-IN-WORTHY emits to a separate `quality/config_flag_candidates.json` stream for operator triage.

B-6 (combine findings into PR) groups SHIP-WORTHY bugs into clusters. OPT-IN-WORTHY and LOCAL-FIX-WORTHY bugs don't enter the upstream-PR pipeline.

### Phase 5D — Operator override mechanism

The evaluation is a recommendation, not a gate. Operator can force any classification to SHIP-WORTHY (or downgrade SHIP-WORTHY to LOCAL-FIX-WORTHY) via `quality/fix_evaluation_overrides.yaml`. Overrides are logged in BUGS.md with the rationale the operator provides.

### Phase 5E — Empirical validation against historical PRs

Run B-9 retrospectively against QPB's history of generated upstream PRs:

- **PR #3035 (gson BUG-001)** — should classify SHIP-WORTHY. Real correctness consequence, tight fix, no per-call overhead.
- **PR #3036 (gson BUG-002)** — should classify OPT-IN-WORTHY or LOCAL-FIX-WORTHY. Rare corner case, per-call overhead. Matches Marcono1234's review verdict.
- Any other past PRs filed and accepted or rejected by upstream maintainers — verify the classification matches the empirical outcome.

If the retrospective classification doesn't match outcomes, recalibrate the dimensions before shipping.

### Phase 5 Ship Gate

- Self-Council Protocol 1 — panelists cover: classification correctness on the historical PR corpus; static-analysis hook reliability; operator-override safety.
- Empirical validation against the historical PR set — at least 5 past PRs classified with matching outcomes
- Integration tested with B-7's bugspec emit filter

---

## Phase 6 — Capability B-10 (Claim-vs-implementation consistency check)

**Per Design § 2.10.** Origin: 2026-06-08 review of BUG-005 from gson run `20260604T220125Z` — QPB Phase 3's fix claimed to mirror `JsonReader.nextInt` but used different operators (`BigDecimal.intValueExact()` vs `(int) asDouble; compare`) producing different semantics at the 2^53 boundary. The lesson: TDD verification + cost/benefit + weak-assertion gates don't catch patches whose semantics diverge from the writeup's claimed mirror. B-10 closes that gap.

### Phase 6A — Adversarial boundary input generator

Build the Level 3 boundary-input generation infrastructure (Design § 2.10 Level 3). Hand-curated boundary sets per type:

- Integer types: `MIN_VALUE`, `MAX_VALUE`, `MIN_VALUE - 1`, `MAX_VALUE + 1` (as strings to bypass overflow), 0, ±1
- Floating point: `MIN_VALUE`, `MAX_VALUE`, smallest subnormal, NaN, ±Infinity, ±0.0, 2^53, 2^53 + 1
- Strings: empty, UTF-8 boundary characters (surrogate pair starts, high-bit-set), control characters
- Booleans: trivial
- Composite: empty collections, single-element, max-size at the type's documented limit

The generator emits input candidates per detected type signature; subsequent phases run both reference and patch against each.

### Phase 6B — Reference site detection + AST parsing

For each generated patch, detect what code locations the writeup claims to mirror:

1. Parse the writeup's frontmatter / structured citations for explicit `file:line` references (preferred — force into writeup format)
2. Fall back to LLM extraction of prose claims like "mirrors X" / "same pattern as Y" → resolve to source file:line

For each claimed reference: parse the AST (Java via JavaParser-style tooling, Python via `ast`, etc.). Extract operators, types, control flow. Same for the patch's modified code.

### Phase 6C — Level 1 + Level 2 (structural) implementation

- Level 1: raw AST diff. Flag operator-class divergence (cast vs method call, arithmetic vs comparison, etc.).
- Level 2: equivalence-by-similarity. Same operator FAMILY on equivalent types? Use type lattice + operator categories.

These are weaker pre-filters; output feeds into the Level 3 trigger.

### Phase 6D — Level 3 (adversarial boundary) execution

For each (reference, patch, generated-input) triple:

1. Compile / load both reference and patch
2. Execute reference with input → record result (return value, exception class, exception message)
3. Execute patch with input → record result
4. Compare. If different: flag with input + both behaviors

The execution sandbox must isolate the reference and patch (separate classloaders for Java, separate modules for Python) to avoid state leak.

### Phase 6E — Operator-decidable surface

A B-10 failure doesn't auto-reject. The flag is presented to the operator with:

- The boundary input that triggered the divergence
- The reference's behavior on that input
- The patch's behavior on that input
- The writeup's claim verbatim
- Two suggested resolutions: "update writeup to match patch's stronger contract" OR "update patch to literally mirror"

Operator picks. Resolution gets logged to `quality/claim_implementation_resolutions.json`.

### Phase 6F — Integration with B-7 + B-8 + B-9

- After B-8 weak-assertion gate passes (test catches the bug)
- After B-9 cost/benefit classification (SHIP-WORTHY, etc.)
- B-10 runs as a gate before B-7's bugspec emit
- A B-10 unresolved failure blocks bugspec YAML emission for that bug; operator must resolve before the bug ships

### Phase 6G — Empirical validation against BUG-005

Run B-10 retrospectively against the BUG-005 patch:

- Reference: `JsonReader.nextInt`'s `(int) asDouble; compare` pattern at the cited file:line
- Patch: `JsonTreeReader.nextInt`'s proposed `BigDecimal.intValueExact()` change
- Generated input `"9007199254740993"` should trigger divergence
- Expected output: reference returns `9007199254740992`, patch throws `ArithmeticException`
- B-10 surfaces this with both behaviors named; operator resolves

If B-10 doesn't surface this divergence with the BUG-005 patch, the boundary input generation needs recalibration before shipping.

### Phase 6 Ship Gate

- Self-Council Protocol 1 — three panelists: boundary-input generator coverage, AST extraction correctness, B-7/B-8/B-9 integration correctness
- BUG-005 retrospective produces the expected flag with both behaviors named
- At least 3 historical QPB-generated patches passed through B-10 retrospectively with predicted-vs-actual matching outcomes

---

## Phase 7 — Remaining B-N capabilities (deferrable)

These are documented in Design § 2.1-2.7. Each has its own sub-phase if implemented, or moves to v1.5.11.

- B-2: Phase-isolated improvement loop for security-bug targeting (Design § 2.2)
- B-3: Harness resume/iterate semantics (Design § 2.3)
- B-4: Bug-neighborhood iteration strategy (Design § 2.4)
- B-5: Adversarial fresh-context review pass (Design § 2.5)
- B-6: Combine related findings into single coherent PR (Design § 2.6)
- B-7: Phase 7 bugspec-format emit (Design § 2.7) — includes two sub-constraints per Design § 2.7's subsections, both implementable independently of the rest of B-7:
  - **Target-project conformance** (Design § 2.7 sub-constraint): a 7-dimension conformance pipeline (A no-tool-promo content, B no-new-directories, C integrate-into-existing-test-class, D match-target-test-style, E match-naming, F match-license-header, G test-scope-mirrors-fix-scope). Each dimension is a separable stripper / detector / generator with its own regression test. Born from gson PR #3035's 7 cleanup categories.
  - **Mutation verification before SHIP-WORTHY classification** (Design § 2.7 sub-constraint): every TDD-verified test runs a revert→run→restore→run cycle in a temp worktree; tests that don't fail on the unfix'd target get demoted to LOCAL-FIX-WORTHY. Complementary to B-8 (which catches assertion-quality issues); this gate catches any reason a test would pass without the fix. Logged to `quality/mutation_verification.json`.

Operator decides at Phase 7 entry which to land in v1.5.11. Default: defer all to v1.5.11 unless one becomes blocking.

---

## Phase 8 — Release prep + ship

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
Phase 3 (B-1) ───────────┤
Phase 4 (B-8) ───────────┼──→ Phase 8 (release ship) ──→ v1.5.11 tag
Phase 5 (B-9) ───────────┤
Phase 6 (B-10) ──────────┘
(Phase 7 capabilities B-2..B-7 — operator's pick; may all defer to v1.5.11)
```

Phases 2-6 are implementation-parallelizable. Runtime ordering at QPB execution time: B-8 → B-9 → B-10 → B-7 emit. Phase 5 (B-9) and Phase 6 (B-10) integrate with B-7's bugspec emit; if both land in v1.5.11, sequence Phases 5+6 before any Phase 7 work that depends on B-7.

---

## Council coordination notes

- Per-capability Council reviews use Self-Council Protocol 1
- The §1.3 semantic Council audit prompt becomes a NEW Council variant; first empirical use is on v1.5.11's own work
- Defensive-sweep charter from 207 applies to all content-fix sub-instructions during v1.5.11

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
| 10 | Fix cost/benefit evaluation sub-pass scaffold (B-9) | 5A | Pending |
| 11 | Static-analysis hooks for incidence + overhead (B-9) | 5B | Pending |
| 12 | Integration with B-7 (bugspec emit) + B-6 (combine PRs) (B-9) | 5C | Pending |
| 13 | Operator override mechanism (B-9) | 5D | Pending |
| 14 | Empirical validation against historical PRs incl. gson #3035 / #3036 (B-9) | 5E | Pending |
| 15 | Adversarial boundary input generator (B-10) | 6A | Pending |
| 16 | Reference site detection + AST parsing (B-10) | 6B | Pending |
| 17 | Level 1+2 structural diff (B-10) | 6C | Pending |
| 18 | Level 3 adversarial boundary execution (B-10) | 6D | Pending |
| 19 | Operator-decidable surface (B-10) | 6E | Pending |
| 20 | Integration with B-7+B-8+B-9 (B-10) | 6F | Pending |
| 21 | Empirical validation against BUG-005 (B-10) | 6G | Pending |
| 22 | B-2..B-7 capability scoping decision | 7 | Pending operator decision at Phase 7 entry |
| 23 | Release ship steps 1-8 | 8 | Pending Phase 2 + Phase 3 + Phase 4 + Phase 5 + Phase 6 ship gates |

---

*End of v1.5.11 Implementation Plan. Design in `QPB_v1.5.11_Design.md`. Predecessor scope in `QPB_v1.5.9_Design.md` + `QPB_v1.5.9_Implementation_Plan.md`.*
