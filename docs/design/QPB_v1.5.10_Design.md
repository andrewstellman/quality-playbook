# Quality Playbook v1.5.10 — Design Document

*Status: created 2026-06-07. Inherits the broader-scope work that was originally drafted as v1.5.9 (during the 2026-06-06 Cowork session) but deferred when v1.5.9 was scoped down to two focus items (harness-as-skill + SKILL.md trim). The v1.5.10 work begins after v1.5.9 ships.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Where v1.5.10 sits in the arc

v1.5.10 picks up everything that the original v1.5.9 broad-scope draft contained, minus the two items that v1.5.9 actually ships:

- Ship-gate feature (skill validation invariants, cross-artifact consistency, semantic Council audit, bootstrap-as-regression-test)
- B-1: Prompt-injection isolation for ingested `reference_docs/`
- B-2: Phase-isolated improvement loop for security-bug targeting
- B-3: Harness resume / iterate (under the new harness-as-skill substrate from v1.5.9)
- B-4: Bug-neighborhood iteration strategy
- B-5: Adversarial fresh-context code review pass
- B-6: Combine related findings into a single coherent PR
- B-7: QPB Phase 7 emits bugspec-format YAML for each TDD-verified bug
- B-8: Weak-assertion / "passes for the wrong reasons" detection on QPB-generated tests (from Marcono1234's PR #3035 feedback)

These items are independent of each other; v1.5.10's implementation plan picks per-item priorities based on what's empirically most blocking after v1.5.9 ships.

---

## Part 1 — Skill ship-gate feature

Mechanical validators that block release if a skill artifact fails. Three complementary layers.

### 1.1 Mechanical invariants (`quality_gate.py` extension)

New invariants the gate enforces on every commit:

- `references/X.md` references in `SKILL.md` resolve to existing files (carried forward from v1.5.9 Phase 2D — make sure v1.5.10 doesn't regress it)
- Version-string parity across `pyproject.toml`, `package.json`, `quality_playbook_cli/__init__.py`, and the version stamp inside `SKILL.md` frontmatter
- No new-source-file additions outside expected directories (catches accidental `quality/` or `previous_runs/` commits)
- No `print()` calls to stdout in `bin/` scripts that are consumed by JSON-parsing tools (carries the 203 prepack-stdout-pollution defect forward as a gate invariant)
- No forbidden filename patterns (`*.pyc`, `__pycache__/`, `.DS_Store`, etc.) tracked in git

### 1.2 Cross-artifact consistency invariants

Beyond per-file invariants, consistency *across* artifacts:

- The frontmatter `version:` in `SKILL.md` matches `pyproject.toml` (already in 1.1; explicit cross-check here)
- Every reference file mentioned in `SKILL.md` has at least one phase prompt that loads it
- Every phase prompt's "outputs" section maps to a `validate_phase_artifacts` invariant
- AGENTS.md references match `agents/*.agent.md` files actually present

### 1.3 Semantic Council audit prompt

A new Council variant: not "is the code correct" but "is the skill *coherent*." Reviewers read the trimmed SKILL.md + phase references and assert:

- Each phase's stated purpose maps to its actual prompt content
- Phase entry contracts (inputs / outputs) are consistent across SKILL.md and the phase prompt files
- The skill's voice and opinionation level is consistent — no "this is critical" attached to optional steps, no "consider doing" attached to mandatory ones
- The README's adopter-facing description matches what the skill actually does

### 1.4 Bootstrap-as-regression-test framing

The bootstrap run (QPB-on-QPB) becomes a fixed regression test artifact. Every release-prep run executes the bootstrap with the standard expected-bug set; gate FAILS if any new false-positive or recall regression appears.

### 1.5 Architectural choice — pick before implementing 1.1-1.3

Three implementation approaches with different cost/benefit:

| Approach | Cost | Benefit | Risk |
|---|---|---|---|
| Extend `quality_gate.py` directly | Low | Reuses existing infrastructure | Gate grows large, harder to maintain |
| New `bin/skill_gate.py` separate module | Medium | Cleaner separation; can be skipped per-context | Two gates means doubled invocation discipline |
| External validator service | High | Maximally decoupled | Operational overhead; another dependency |

Pick before implementing 1.1-1.3. Default recommendation: extend `quality_gate.py` with a sub-module pattern.

---

## Part 2 — New capabilities (B-1 through B-8)

### 2.1 B-1: Prompt-injection isolation for ingested `reference_docs/`

When QPB ingests adopter-provided docs (issue trackers, Slack exports, etc.), those documents can carry adversarial content that would steer the agent's behavior. v1.5.10 adds:

- Phase 1 sanitization pass: strip executable markdown (code blocks that look like CLI invocations), explicit prompt-injection patterns ("ignore previous instructions"), and structured roleplay attempts
- Reference doc isolation: any Tier 4 content is loaded into a clearly-labeled context block that the agent is instructed to treat as "data about what the codebase should do," not as instructions to follow
- Test fixture: a small benchmark repo with prompt-injection-laden `reference_docs/` that the agent should classify as untrusted data, not follow

### 2.2 B-2: Phase-isolated improvement loop for security-bug targeting

The current improvement loop adjusts whole-pipeline behavior. Security-bug-specific tuning often needs to adjust just one phase (e.g., Phase 3 review patterns for SQL injection) without touching Phase 4 audit weight. v1.5.10 adds:

- `--phase-only N` flag to the improvement loop driver
- Per-phase improvement artifacts stored in `quality/improvement/phase_N/`
- Regression isolation: phase-N tweaks don't propagate to phase-M outputs unless explicitly merged

### 2.3 B-3: Harness — resume an aborted/blocked run, or iterate on a completed run

Under v1.5.9's harness-as-skill substrate (tick-based on-disk state), resume is conceptually trivial — every tick is a resume. v1.5.10 formalizes:

- Explicit `qpb-harness resume <ts>` semantics for "pick up an aborted run" (not just "continue the next tick")
- `qpb-harness iterate <ts> --strategy <name>` for "run a follow-up cycle against the same target with adjusted parameters" (e.g., re-run Phase 4 with different reviewer composition)

### 2.4 B-4: Bug-neighborhood iteration strategy

When the first run finds a bug in `auth.go`, the iteration cycle should preferentially look for sibling bugs in `auth.go`'s neighborhood (same module, called-by chain, same pattern). v1.5.10 adds:

- Neighborhood definition: same module, importing modules, modules with shared call-graph depth ≤ 2
- Iteration cycle: a follow-up Phase 3 review constrained to the neighborhood of the previously-found bug, with Phase 4 audit weighted toward this neighborhood

### 2.5 B-5: Adversarial code review pass (independent fresh-context strategy)

Current adversarial iteration runs in the same context as the original review. A fresh-context adversary that reads ONLY the BUGS.md candidates + spec — not the codebase or prior context — provides a different lens. v1.5.10 adds:

- New iteration strategy `adversarial-fresh`
- Strategy spawns a fresh Claude/codex/copilot subagent with no exposure to the original review's reasoning
- Adversary reads BUGS.md + REQUIREMENTS.md only and argues against each finding
- Findings the fresh adversary cannot defeat are flagged HIGH confidence

### 2.6 B-6: Combine related findings into a single coherent PR

When QPB finds 5 bugs in `auth.go`, the operator wants ONE PR with all 5 fixes, not 5 separate PRs. v1.5.10 adds:

- Per-PR clustering: group bugs by file proximity + topic + fix locality
- Coherent commit message generation that explains the cluster's theme
- Per-cluster Phase 5 reconciliation that ensures the bugs don't have conflicting fixes
- Bugspec-format YAML emission per cluster (carries forward B-7 capability — see 2.7)

### 2.7 B-7: QPB Phase 7 emits bugspec-format YAML for each TDD-verified bug

For each bug QPB finds that has a passing TDD red→green test, emit a `bugspec`-format YAML file ready for upstream bug-fix PR automation. The YAML carries:

- Target repo + commit
- Pre-test source state (red)
- Patch (minimal-diff fix)
- Post-test source state (green)
- Test code
- Bug description + spec citation
- Confidence indicators

Integration with the standalone `bugspec` CLI for one-command upstream PR filing.

#### Constraint: no tool-promotional content in source artifacts

**Origin: 2026-06-08 gson PR #3035 review.** A QPB-generated test file landed in the PR with a header comment:

```java
// Generated by Quality Playbook v1.5.8 — https://github.com/andrewstellman/quality-playbook
// Author: Andrew Stellman · Date: 2026-06-04 · Project: gson
```

That comment doesn't belong in source code that becomes part of someone else's codebase. It reads as marketing inside the upstream's repository, persists forever in their codebase, and creates an awkward future-maintenance artifact (the next refactor either silently drops attribution or leaves a stale stamp).

**B-7 constraint:** generated patches MUST NOT include tool-promotional comments inside the source files. Specifically forbidden in source-code artifacts (`.py`, `.java`, `.go`, `.js`, etc. — any file that gets merged):

- "Generated by [Tool]" headers
- URLs to the generating tool's repository or homepage
- "Provenance" comments naming the tool or its version
- Author attribution that's not what a human-written file would carry (a normal `@author` Javadoc tag matching the PR author is fine; "Generated by QPB" is not)

**Where tool provenance DOES belong:**

- **PR description body** — the canonical place. A "Discovered by [Tool] · regression test TDD-verified" line is appropriate context for the reviewer and the merge commit message.
- **The bugspec YAML manifest** — separate from the source patches; lives in the bugspec ecosystem, not in the upstream codebase.
- **The QPB run logs and `quality/PROVENANCE.json` artifact** — internal to the QPB-on-target run.
- **The PR's commit message** — if the author chooses; analogous to how `git commit --author` would be used.

**Implementation:** B-7's emit logic strips these patterns from generated source files before they enter the bugspec YAML. A regression test pins the stripping (passes a candidate file with the forbidden header; asserts the output is clean). Cross-references the defensive-sweep methodology from instruction 207 — once 3+ tool-promotional patterns are observed, the AUDIT-table pattern from `ai_context/DEVELOPMENT_PROCESS.md` applies and the stripper gains a sweep test.

**Empirical validation:** the gson PR #3035 test file is the canonical positive example. After 207-style trim of these lines, the file reads as a normal upstream-contribution test, indistinguishable in surface from a human-authored test.

### 2.8 B-8: Weak-assertion detection on QPB-generated tests

**Origin: Marcono1234's feedback on PR #3035** (the gson regression test for BUG-001). The test pattern `try { ... } catch (Exception e) { assertTrue(true); }` passes for the wrong reason — any thrown exception passes the assertion, including degenerate ones. QPB's TDD verification needs to detect this class of "passes for the wrong reason" before claiming a test verifies the bug.

#### Three complementary detection layers

**Layer 1: Static pattern detection.** Scan generated test source for known weak-assertion patterns:

- `try { ... assertNull(...); } catch (...) {}` — exception path silently passes
- `assertTrue(true)` after a complex setup — assertion always true
- `assertEquals(x, x)` — trivially true (same variable)
- Empty `assertThrows` — doesn't verify the thrown exception's content
- Generic exception type in `assertThrows` — catches too broad

Each pattern blocks the test from being marked TDD-verified.

**Layer 2: Adversarial test critique.** A separate sub-pass reads each TDD-verified test plus the bug it's supposed to verify, and is prompted to find ways the test could pass without the bug being present. If the critique succeeds, the test is rejected.

**Layer 3: Counterfactual mutation (optional, benchmark-mode only).** Apply small mutations to the test and the fix and verify the test still catches the bug. Expensive; reserved for benchmark validation of QPB's own behavior.

#### Where this lands in the QPB pipeline

After Phase 3's TDD verification confirms red→green, before Phase 5's reconciliation. A test that fails any layer is excluded from the TDD-verified set and the bug it was supposed to verify gets a CONFIDENCE-MEDIUM or LOW classification rather than HIGH.

#### Connection to bugspec v0.3.3+

Bugspec inherits this defect class (it ships TDD tests with reproducible bug fixes). v0.3.3+ should adopt Layer 1 + Layer 2 statically. Coordination with bugspec maintainers as part of v1.5.10 design discussion.

#### Empirical validation already exists

The gson #3035 issue is the canonical positive example: pre-203's test passed for the wrong reason; Marcono1234 caught it; we tightened the test. The v1.5.10 work is a permanent automated check for this defect class so the next QPB-generated test doesn't ship with the same shape.

---

### 2.9 B-9: Fix cost/benefit evaluation before upstream PR submission

**Origin: 2026-06-08 Marcono1234 review of gson PR #3036.** QPB v1.5.8 found a real bug (MapTypeAdapterFactory write-side silently emits JSON with duplicate member names when distinct Map keys share a String.valueOf form, while the read-side rejects such input). The fix (track emitted names in a HashSet, throw on collision) is technically correct. Marcono1234's review pushed back: "this will cause overhead for every map serialization and the case it tries to account for seems like a rare corner case." Andrew agreed and closed the PR.

The lesson: **a bug being "real" doesn't mean its fix is "worth shipping" upstream.** QPB Phase 6 verifies bug existence and fix correctness; it doesn't evaluate fix cost vs. benefit. Filing PRs for every TDD-verified bug ignores that some bugs have fixes whose architectural cost outweighs the bug's incidence.

#### What B-9 evaluates

Before Phase 7 emits bugspec-format YAML (or any other upstream-PR-ready artifact), a cost/benefit sub-pass evaluates each TDD-verified bug across these dimensions:

- **Incidence** — how often does the trigger condition fire in real-world code? Common case vs. rare corner case. Sources: existing test coverage gaps (gaps suggest rarity), code-path frequency analysis from Phase 1's role-map traversal.
- **Fix overhead distribution** — does the fix add cost ONLY to the bug case, or to the common case too? The Marcono1234 #3036 framing: "overhead for every map serialization" when the bug only fires for non-String key types with colliding `toString`.
- **Security framing** — does the bug have security implications, or is it a quality/correctness concern? Read-side parser inconsistency has security weight (polyglot JSON CVE class); write-side strict-checking doesn't, generally.
- **Architectural cost** — API surface additions, new configurability flags, perpetual maintenance burden, code complexity.
- **Symmetry-as-contract arguments** — when the bug is "X path violates a symmetry with Y path," the argument is defensible but not bulletproof. Maintainers can reasonably accept asymmetry that doesn't have a security or correctness consequence.

#### Output and integration

Each TDD-verified bug gets a cost/benefit classification:

- **SHIP-WORTHY** — fix is bounded, incidence is meaningful, security or correctness consequence is real. File upstream PR.
- **OPT-IN-WORTHY** — fix is reasonable but adds overhead/API-surface; default-on may not be justified. Surface to operator as "consider a config flag" candidate.
- **LOCAL-FIX-WORTHY** — bug is real, fix is correct, but the upstream value doesn't justify the PR-review-and-merge cost. Note in BUGS.md as "applied locally; not upstreamed."
- **DEFENSIVE-NOTE** — bug is real but rare-corner-case + fix has overhead; document as a known quirk without trying to fix.

The Phase 7 bugspec emit (B-7) consumes this classification: only SHIP-WORTHY bugs become bugspec-format YAML by default. OPT-IN-WORTHY surfaces as a separate "config-flag candidate" stream the operator triages.

#### Where this lands in the QPB pipeline

After Phase 5 reconciliation, before Phase 6 verify. Phase 5 produces the consolidated bug set with TDD-verified patches; the cost/benefit evaluation runs over that set; Phase 6 verify uses the classification to decide what gets the SHIP verdict for upstream submission.

#### Connection to B-7 and B-8

- **B-7 (bugspec emit)** — gains a filter: only SHIP-WORTHY classifications become bugspec YAML. OPT-IN-WORTHY can optionally be emitted as a separate stream for operators who want to ship config-flag candidates.
- **B-8 (weak-assertion detection)** — addresses a different layer (is the test verifying the right thing?). B-9 addresses "given the test verifies the right thing, is the fix worth shipping?" The two are independent.

#### What this is NOT

- Not a vehicle for filtering out "uncomfortable" findings (security regressions, ship-blocker bugs). Those classifications are independent of the cost/benefit evaluation — security bugs are SHIP-WORTHY by default.
- Not a way for the agent to opine on upstream-maintainer aesthetics. The cost/benefit evaluation surfaces empirical dimensions (incidence, overhead, security weight); it doesn't try to predict whether a specific maintainer will like the fix.

#### Empirical validation

The closed gson PR #3036 is the canonical positive example: real bug, technically correct fix, maintainer-judgment said "not worth the overhead." A B-9 evaluation would have classified it as OPT-IN-WORTHY or LOCAL-FIX-WORTHY pre-filing, saving the maintainer's review time and the back-and-forth.

PR #3035 (gson BUG-001) by contrast was SHIP-WORTHY — the bug had real correctness implications, the fix was tight (no per-call overhead in the common case), and the maintainer accepted it. The B-9 framing predicts the right answer for both.

#### Open questions for design phase

- **Calibration**: how does QPB calibrate incidence estimates? Static analysis of the trigger condition's prevalence in the target codebase? Cross-repo benchmark from past QPB runs?
- **Operator override**: can the operator force a LOCAL-FIX-WORTHY classification to SHIP-WORTHY? Probably yes — the classification is a recommendation, not a gate.
- **Connection to B-6 (combine findings)**: when bugs cluster into a single PR, does cost/benefit apply per-bug or per-cluster?

## Part 3 — Design decisions to make before v1.5.10 implementation

### 3.1 Architectural choice for Part 1 (see §1.5 table)

`quality_gate.py` extension vs `bin/skill_gate.py` separate module vs external validator. Pick before §1.1-1.3 implementation begins.

### 3.2 Scope — which of Part 2 lands in v1.5.10 vs deferred further

9 capabilities (B-1 through B-9). Some are user-blocking (B-1 prompt-injection isolation is a security concern; B-8 weak-assertion blocks shipping flaky QPB tests; B-9 fix-worth-shipping evaluation prevents wasted upstream-maintainer review time). Some are nice-to-have (B-4 bug-neighborhood iteration is a quality-of-life improvement). v1.5.10 implementation should pick a subset based on:

- Empirical evidence from v1.5.9 release runs (what bit adopters?)
- Coordination availability with external maintainers (B-8 ties to bugspec; B-7 ties to bug-PR automation downstream; B-9 ties into B-7's emit filter)
- Token-cost budget (adding 9 capabilities at once is a large context expansion in SKILL.md, which v1.5.9 just trimmed)

Default recommendation: prioritize B-1 (security) + B-8 (test quality) + B-9 (fix-worth-shipping evaluation) for v1.5.10. Defer B-2 / B-4 / B-5 to v1.5.11 unless surfacing demand. B-9 is new (added 2026-06-08 after the gson PR #3036 closure) and is closely coupled to B-7's bugspec emit — the two should land together if either does.

### 3.3 Voice / opinionation level for the §1.3 semantic Council prompt

The Council audit prompt has to declare what "coherent skill" means. Subjective territory. Need a style guide before launching reviewers.

### 3.4 Scope — QPB-only vs every-adopter-skill validator

Part 1 ship-gate validators could remain QPB-specific (only `quality_gate.py` validates) OR become a reusable skill-validation library that other adopter skills can pull in. v1.5.10 should pick.

---

## Part 4 — Carry-forward methodology lessons

Lessons surfaced during v1.5.7 / v1.5.8 development that should be absorbed into `ai_context/DEVELOPMENT_PROCESS.md` before they fade:

- **Defensive-sweep Council charter** (origin: 207) — absorbed during v1.5.8 close-out. No v1.5.10 action needed.
- **Release close-out sequence** (origin: 2026-06-07) — absorbed during v1.5.8 close-out. No v1.5.10 action needed.
- **Patch-authoring discipline** (origin: 2026-06-06 gson PR cascade) — verify it's documented in DEVELOPMENT_PROCESS.md; if not, file a v1.5.10 micro-instruction to add it.
- **Multi-step shell discipline** (origin: 2026-06-06 gson recovery script failures) — same verification.
- **Velocity-pressure self-imposed deadline pattern** (origin: 2026-06-06 cross-chat audit) — same verification.

These are documentation actions, not feature work. v1.5.10 should sweep them early so the actual feature work isn't entangled with methodology corrections.

---

*End of v1.5.10 Design. Implementation plan in `QPB_v1.5.10_Implementation_Plan.md`. Predecessor scope in `QPB_v1.5.9_Design.md`.*
