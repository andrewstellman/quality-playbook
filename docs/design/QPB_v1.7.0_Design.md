# Quality Playbook v1.7.0 — Design Document

*Renumbered on 2026-07-20: this release (the security work) moved from v1.5.11 to v1.7.0, and the file was `git mv`'d from `QPB_v1.5.11_Design.md` accordingly (operator decision). Internal self-references below have been updated to v1.7.0; historical provenance mentions of prior names/numbers are left as-is.*

*Status: created 2026-06-07 as `QPB_v1.5.10_Design.md`; **renumbered to v1.5.11 on 2026-06-11** when the SKILL.md trim moved out of v1.5.9 (which refocused on the harness + its standalone distribution) into its own v1.5.10 release. Inherits the broader-scope work originally drafted as v1.5.9 (2026-06-06 Cowork session) and deferred when v1.5.9 was scoped down. The v1.7.0 work begins after v1.5.10 (SKILL.md trim) ships.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Clean starting point inherited from v1.5.10 (2026-06-18)

v1.5.10 was expanded (operator decision) from a SKILL.md trim into a **repo-hygiene release** specifically so that v1.7.0 — the security work — starts from a clean, sensibly-organized repo. By the time v1.7.0 begins, v1.5.10 has delivered:

- A trimmed canonical `SKILL.md` (~12K tokens) with per-phase detail in lazy-loaded `references/*.md`, and a reference-resolves validator.
- The canonical `SKILL.md` + `references/` **relocated to the repo root** (real file at root; in-tree skill locations are symlinks), with the install-location fallback contract, packaging, and tests rewired to match.
- Committed run-output and orphaned partial copies (`quality/previous_runs/`, top-level `previous_runs/`, `spike/`, the orphaned `.github/skills/quality_gate/`) removed from tracking and gitignored.
- An arunner regression run confirming the trimmed/relocated skill still works end-to-end.

Security-relevant implication: the v1.7.0 prompt-injection-isolation work (B-1) and the phase-isolated security improvement loop (B-2) build on the relocated root layout and the cleaned `references/` tree. Any path assumptions in the B-items below that referenced `plugins/quality-playbook/skills/quality-playbook/SKILL.md` should be re-read against the v1.5.10 root layout before implementation. See `QPB_v1.5.10_Design.md`.

**Note on B-2 / B-5 vs. the 2026-06 security experiments (corrected 2026-06-20 against the gen-003 artifacts + the end-of-thread Council retraction).** The gen-003 experiments found the adversarial-LLM clearing pass (B-5 as originally drafted) **unreliable**. They did **NOT** establish that "the deterministic tool-belt approach is reliable" — that earlier summary overstated the evidence. What the artifacts actually support:

- **Tier 1 (demonstrated, narrow):** where the off-the-shelf tool *is* the detector — ReDoS via `recheck`, raw sinks (`shell=True`) via `semgrep` — it wins cleanly. 2 clean hits of 7 targets. QPB barely participates.
- **Tier 2 (HYPOTHESIS — never demonstrated):** the actual "use exploration/QE knowledge to direct the tools" capability — the LLM reads the code, identifies the framework-specific taint *source*, and authors a `semgrep` taint rule the tool then verifies. **No Tier-2 case was ever executed end-to-end; every executed Tier-2 case (nltk path-traversal, lmdeploy SSRF) MISSED.** It needs a real MISS→HIT demonstration before it can be claimed.
- **Tier 3 (open):** incomplete-guard / logic bugs — **unsolved**.

**Reconciling the two security results (the unresolved framing tension).** gen-000's "4 CVEs detected blind" is a *model-as-detector* result; the thesis the experiments landed is that the model is **unreliable as a standalone detector** (6/10 missed; confident false positives like the flatted phantom). The honest synthesis — neither "great detector" nor "proven tool-director" — is: **the model is a useful HIGH-RECALL flagger whose flags require deterministic verification + triage.** Tier-1 tools verify a cheap subset; Tier-2 (LLM-directed taint rules) is the unproven bet that must be demonstrated MISS→HIT; Tier-3 is open. Before implementing B-2/B-5, build the security-profile spec around *that* synthesis, not around "the tool-belt is reliable."

---

## Where v1.7.0 sits in the arc

v1.7.0 picks up everything that the original v1.5.9 broad-scope draft contained, minus the two items that v1.5.9 actually ships:

- Ship-gate feature (skill validation invariants, cross-artifact consistency, semantic Council audit, bootstrap-as-regression-test)
- B-1: Prompt-injection isolation for ingested `reference_docs/`
- B-2: Phase-isolated improvement loop for security-bug targeting
- B-3: Harness resume / iterate (under the new harness-as-skill substrate from v1.5.9)
- B-4: Bug-neighborhood iteration strategy
- B-5: Adversarial fresh-context code review pass
- B-6: Combine related findings into a single coherent PR
- B-7: QPB Phase 7 emits bugspec-format YAML for each TDD-verified bug
- B-8: Weak-assertion / "passes for the wrong reasons" detection on QPB-generated tests (from Marcono1234's PR #3035 feedback)

These items are independent of each other; v1.7.0's implementation plan picks per-item priorities based on what's empirically most blocking after v1.5.9 ships.

---

## Part 1 — Skill ship-gate feature

Mechanical validators that block release if a skill artifact fails. Three complementary layers.

### 1.1 Mechanical invariants (`quality_gate.py` extension)

New invariants the gate enforces on every commit:

- `references/X.md` references in `SKILL.md` resolve to existing files (carried forward from v1.5.9 Phase 2D — make sure v1.7.0 doesn't regress it)
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

When QPB ingests adopter-provided docs (issue trackers, Slack exports, etc.), those documents can carry adversarial content that would steer the agent's behavior. v1.7.0 adds:

- Phase 1 sanitization pass: strip executable markdown (code blocks that look like CLI invocations), explicit prompt-injection patterns ("ignore previous instructions"), and structured roleplay attempts
- Reference doc isolation: any Tier 4 content is loaded into a clearly-labeled context block that the agent is instructed to treat as "data about what the codebase should do," not as instructions to follow
- Test fixture: a small benchmark repo with prompt-injection-laden `reference_docs/` that the agent should classify as untrusted data, not follow

### 2.2 B-2: Phase-isolated improvement loop for security-bug targeting

The current improvement loop adjusts whole-pipeline behavior. Security-bug-specific tuning often needs to adjust just one phase (e.g., Phase 3 review patterns for SQL injection) without touching Phase 4 audit weight. v1.7.0 adds:

- `--phase-only N` flag to the improvement loop driver
- Per-phase improvement artifacts stored in `quality/improvement/phase_N/`
- Regression isolation: phase-N tweaks don't propagate to phase-M outputs unless explicitly merged

### 2.3 B-3: Harness — resume an aborted/blocked run, or iterate on a completed run

Under v1.5.9's harness-as-skill substrate (tick-based on-disk state), resume is conceptually trivial — every tick is a resume. v1.7.0 formalizes:

- Explicit `qpb-harness resume <ts>` semantics for "pick up an aborted run" (not just "continue the next tick")
- `qpb-harness iterate <ts> --strategy <name>` for "run a follow-up cycle against the same target with adjusted parameters" (e.g., re-run Phase 4 with different reviewer composition)

### 2.4 B-4: Bug-neighborhood iteration strategy

When the first run finds a bug in `auth.go`, the iteration cycle should preferentially look for sibling bugs in `auth.go`'s neighborhood (same module, called-by chain, same pattern). v1.7.0 adds:

- Neighborhood definition: same module, importing modules, modules with shared call-graph depth ≤ 2
- Iteration cycle: a follow-up Phase 3 review constrained to the neighborhood of the previously-found bug, with Phase 4 audit weighted toward this neighborhood

### 2.5 B-5: Adversarial code review pass (independent fresh-context strategy)

Current adversarial iteration runs in the same context as the original review. A fresh-context adversary that reads ONLY the BUGS.md candidates + spec — not the codebase or prior context — provides a different lens. v1.7.0 adds:

- New iteration strategy `adversarial-fresh`
- Strategy spawns a fresh Claude/codex/copilot subagent with no exposure to the original review's reasoning
- Adversary reads BUGS.md + REQUIREMENTS.md only and argues against each finding
- Findings the fresh adversary cannot defeat are flagged HIGH confidence

### 2.6 B-6: Combine related findings into a single coherent PR

When QPB finds 5 bugs in `auth.go`, the operator wants ONE PR with all 5 fixes, not 5 separate PRs. v1.7.0 adds:

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

#### Sub-constraint: Target-project conformance

**Origin: 2026-06-08 gson PR #3035 cleanup.** Multiple QPB-generated artifacts in that PR didn't match gson's existing conventions:

1. A `// Generated by Quality Playbook v1.5.8 — https://github.com/andrewstellman/quality-playbook` header comment in the test source file
2. A `regression/` subdirectory created for QPB's tests, where gson's main branch has no such directory (gson tests live in `common/`, `functional/`, `integration/`, `internal/`, `metrics/`, `reflect/`, `stream/`)
3. A standalone `Bug001RegressionTest.java` / `JsonTreeWriterFiniteBigDecimalTest.java` rather than a test method added to the existing `JsonTreeWriterTest.java` for the file being patched
4. Test class naming using QPB's `BugNNNRegressionTest` template rather than gson's convention
5. Test method naming using camelCase verbs (`treeWriterAcceptsFiniteBigDecimal...`) rather than gson's `test...` prefix convention
6. Missing the Apache 2.0 license header that every gson source file carries
7. Test coverage for only BigDecimal even though the fix's guard handled BigDecimal AND BigInteger and the PR title named both

All seven failures are instances of the same underlying error: QPB's internal organizational, stylistic, and scope conventions appropriate for QPB-on-target runs are inappropriate for upstream submissions where the target project has its own established conventions.

**B-7 constraint:** generated upstream PR artifacts MUST conform to the target project's existing conventions across ALL of the following dimensions, discoverable from the target's main branch state:

**A. No tool-promotional content in source files.** Forbidden patterns inside files being merged (`.py`, `.java`, `.go`, `.js`, etc.):

- "Generated by [Tool]" headers
- URLs to the generating tool's repository or homepage
- "Provenance" comments naming the tool or its version
- Author attribution that's not what a human-written file would carry (a normal `@author` Javadoc tag matching the PR author is fine; "Generated by QPB" is not)

**B. No directory or package additions absent from target's main.** Before placing a file at `path/to/X.ext`, verify the parent directories exist in the target's main branch. Creating a new package or directory for QPB's tests when the target has no such structure leaves a foreign artifact behind. If creating a new directory is genuinely necessary, escalate to operator decision rather than silently inventing structure.

**C. Integrate into the existing test class for the file being patched, when one exists.** A source file `src/main/java/.../Foo.java` typically has a corresponding `src/test/java/.../FooTest.java`. New test methods belong as `@Test` methods inside that existing class, not as a standalone `BugNNNTest.java` file. Only create a new test file if no corresponding test class exists in the target.

**D. Match the target's test style.** If the existing test class for the file being patched uses unit-level testing (constructs the class under test directly, exercises one method), generated tests follow that pattern — not bring in integration-level patterns (whole-API surface, builder construction, etc.). Integration-level tests, when needed, belong in integration test files specific to the target's convention.

**E. Match the target's naming conventions.** Method naming, test class naming, file naming follow the target's existing patterns. If existing tests use the `testFoo` prefix, match it. If they use `fooDoesBar` declarative naming, match that. Don't impose QPB's `BugNNNRegressionTest` template.

**F. Match the target's license/header conventions.** Most upstream projects have a standard license header at the top of every source file. Generated files MUST carry the appropriate header; absence stands out and signals "this file wasn't authored using the project's conventions." Verify by reading an adjacent file in the destination directory and matching its header verbatim (substituting the year if needed).

**G. Test scope mirrors fix scope.** When the fix's guard mentions multiple classes, types, conditions, or branches, generated test coverage MUST exercise each — not just the smallest illustrative case. If the fix's guard is `!(value instanceof BigDecimal) && !(value instanceof BigInteger)`, generated test methods cover BOTH paths. A future refactor that breaks one path silently passes if only the other is tested. Enumerate the fix's guard clauses programmatically; generate one test method per branch.

**Where tool provenance DOES belong:**

- **PR description body** — the canonical place. A "Discovered by [Tool] · regression test TDD-verified" line is appropriate context for the reviewer and the merge commit message.
- **The bugspec YAML manifest** — separate from the source patches; lives in the bugspec ecosystem, not in the upstream codebase.
- **The QPB run logs and `quality/PROVENANCE.json` artifact** — internal to the QPB-on-target run.
- **The PR's commit message** — if the author chooses; analogous to how `git commit --author` would be used.

**Implementation:** B-7's emit logic operates as a target-conformance pipeline before generating bugspec YAML:

1. Strip tool-promotional content patterns (dimension A)
2. Resolve file destination paths against target's main branch — refuse to create directories not present (dimension B)
3. Detect the existing test class for the file being patched; if found, integrate as a method instead of a standalone file (dimension C)
4. Match style / naming / header against adjacent files in the destination directory (dimensions D/E/F)
5. Enumerate the fix's guard clauses and generate test coverage for each branch (dimension G)

Each dimension has a regression test in the emit pipeline. The defensive-sweep methodology from instruction 207 applies: once 3+ instances of the same conformance failure are observed across dimensions, the AUDIT-table pattern from `ai_context/DEVELOPMENT_PROCESS.md` applies and the conformance pipeline gains a sweep test.

**Empirical validation:** the gson PR #3035 cleanup is the canonical multi-dimensional positive example. All 7 conformance failures listed in Origin were corrected before the PR was approved: tool-promo lines removed (A), `regression/` directory deleted (B), test method moved into `JsonTreeWriterTest.java` (C), unit-level test style adopted (D), `testStrictWriter...` naming adopted (E), Apache 2.0 license header inherited from the destination class (F), and BigInteger test added alongside BigDecimal to mirror the fix's scope (G).

#### Sub-constraint: Mutation verification before SHIP-WORTHY classification

**Origin: 2026-06-08 gson PR #3035 mutation verification.** Even for a one-line fix (the `instanceof BigDecimal/BigInteger` guards), the mutation test was a meaningful sanity check: revert the fix in the working tree via `git checkout upstream/main -- <file>`, observe both BigDecimal and BigInteger tests fail with `IllegalArgumentException: JSON forbids NaN and infinities`, restore the fix via `git checkout HEAD -- <file>`, observe green. This confirmed the tests were non-tautological — the pass-state actually depended on the fix bytes being present.

**B-7 constraint:** every TDD-verified test generated for upstream PR submission MUST be auto-mutation-verified against the unfix'd target source location before being classified SHIP-WORTHY (per B-9). The verification cycle:

1. Revert the patch file(s) to the target's main-branch state in a worktree
2. Run the generated test against the reverted state
3. Confirm the test FAILS (red) with the specific exception class / assertion the test predicts pre-fix
4. Restore the fix
5. Confirm the test PASSES (green)

A test that passes when the fix is absent fails this gate and gets classified LOCAL-FIX-WORTHY or DEFENSIVE-NOTE (not SHIP-WORTHY) — the test doesn't pin the fix; it tests something else, or passes for the wrong reason (the B-8 case).

**Connection to B-8 weak-assertion detection.** B-8 catches tests that pass without the fix because of weak assertions (try/catch + assertTrue(true), empty assertThrows, etc.). This mutation-verification gate catches tests that pass without the fix for ANY reason — assertion weakness, test isolation problems, fixture-state leaks, parallel test interference, environment-dependent behavior. The two gates are complementary; both must pass for SHIP-WORTHY.

**Implementation:** B-7's emit pipeline gains a mutation-verification step before classification:

1. After Phase 3 produces a TDD-verified red→green test, the gate runs the mutation cycle (revert → run → restore → run) in a temporary worktree to avoid affecting the operator's working tree
2. If mutation produces the predicted red (matching exception class, location, and message substring), the bug becomes B-9-classifiable
3. If mutation produces unexpected green or an unexpected red signature, the bug gets demoted to LOCAL-FIX-WORTHY pending operator triage; the demotion reason is logged in `quality/mutation_verification.json`

**Empirical validation:** the gson PR #3035 mutation cycle (run on Andrew's machine 2026-06-08 against `upstream/main` for `JsonTreeWriter.java`) is the canonical positive example. The test correctly failed with the predicted `IllegalArgumentException: JSON forbids NaN and infinities: 1E+400` for the BigDecimal case and the corresponding BigInteger value; restoration produced green. The B-7 emit pipeline should automate this exact cycle for every generated test before SHIP-WORTHY classification.

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

Bugspec inherits this defect class (it ships TDD tests with reproducible bug fixes). v0.3.3+ should adopt Layer 1 + Layer 2 statically. Coordination with bugspec maintainers as part of v1.7.0 design discussion.

#### Empirical validation already exists

The gson #3035 issue is the canonical positive example: pre-203's test passed for the wrong reason; Marcono1234 caught it; we tightened the test. The v1.7.0 work is a permanent automated check for this defect class so the next QPB-generated test doesn't ship with the same shape.

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

### 2.10 B-10: Claim-vs-implementation consistency check on generated patches

**Origin: 2026-06-08 review of BUG-005 from gson run `20260604T220125Z`.** QPB Phase 3 generated a fix for `JsonTreeReader.nextInt` with a write-up claiming the patch *"mirrors JsonReader.nextInt"* — where the reference's pattern is `result = (int) asDouble; if (result != asDouble) throw NumberFormatException`. The actual patch used `new BigDecimal(prim.getAsString()).intValueExact()`. The two implementations agree on most inputs but diverge at the 2^53 boundary where double's mantissa precision runs out: the reference returns the lossy value silently; the patch throws ArithmeticException. The claim-vs-patch mismatch is invisible if you just compare them as code — both "throw on bad input, return on good." The mismatch only surfaces when reasoning about boundary inputs where the two implementations disagree.

QPB's current pipeline (Phase 1-6 + B-8 weak-assertion + B-9 cost/benefit) doesn't catch this class of error. The TDD test passes because the patch DOES fix the specific bug; B-9's cost/benefit evaluation is favorable; but the patch's actual semantics diverge from the writeup's claim. Filing upstream with this mismatch invites the maintainer to call it out ("you claim mirror but you don't").

#### What B-10 detects

When a bug writeup or fix description references mirroring, matching, or using the same pattern as an existing code location, B-10 verifies that the patch actually implements the same semantics. Three implementation levels in increasing sophistication:

**Level 1 — Structural pattern match.** Parse the cited reference's AST and the patch's AST. Flag divergence in operators, types, control flow shape. Catches obvious mismatches (e.g., reference uses `(int)` cast, patch uses BigDecimal method calls).

**Level 2 — Equivalence by structural similarity.** Beyond raw AST diff: does the patch use the same operator family on equivalent types? Catches "uses different-but-structurally-similar code" cases.

**Level 3 — Adversarial boundary testing.** The discriminating one. Generate inputs designed to expose divergence at:

- Type boundaries (max int, max long, byte/short overflow points)
- Precision boundaries (2^53 for double's mantissa, smallest subnormal, MIN_VALUE)
- Special values (NaN, Infinity, -0.0)
- Overflow / underflow transition points
- Encoding boundaries (UTF-8 multibyte starts, surrogate pairs for strings)

Run BOTH the reference pattern AND the patch on each input. Flag any disagreement with both behaviors named in the report.

Level 3 is the strongest and most practical for v1.7.0. Levels 1 and 2 are weaker fallbacks for when boundary-input generation is infeasible.

#### Empirical validation: BUG-005

BUG-005's fix is the canonical Level-3 example. Adversarial input generation should produce `"9007199254740993"` (= 2^53 + 1) among its test cases. Running:

- Reference pattern `(int) Double.parseDouble("9007199254740993")` returns `9007199254740992` silently (double mantissa rounds)
- Patch `new BigDecimal("9007199254740993").intValueExact()` throws `ArithmeticException`

B-10 flags the divergence with both behaviors named. The operator decides:

- Update the writeup ("strengthen the precision check beyond the streaming reader's") — keep the patch
- Update the patch to literally mirror (`(int) prim.getAsDouble(); compare`) — match the claim
- Either is operator-decidable; the gate just requires the choice be made explicitly before upstream submission.

#### Where this lands in the QPB pipeline

After B-9 cost/benefit classification, before Phase 7 / B-7 bugspec emit:

1. Phase 3 TDD: red → green
2. B-8 gate: test actually catches the bug, not passing for the wrong reason
3. B-9 classification: SHIP-WORTHY / OPT-IN-WORTHY / LOCAL-FIX-WORTHY / DEFENSIVE-NOTE
4. **B-10 gate: claimed pattern matches actual semantics**
5. Phase 7 / B-7: bugspec emit + target-conformance + mutation verification

A patch that fails B-10 doesn't get auto-demoted from SHIP-WORTHY. Instead, it gets flagged with the divergence specifically named, and the operator decides which side to update (writeup OR patch). The B-9 classification may be revisited after resolution if the stronger contract changes incidence or overhead estimates.

#### Connection to other capabilities

- **B-7 (bugspec emit)** target-conformance covers structural/stylistic/scope dimensions (where files live, naming conventions, license headers, test scope mirroring fix scope). B-10 covers the SEMANTIC dimension (do the operators in the patch implement the contract the writeup claims).
- **B-8 (weak-assertion)** addresses "is the test verifying the right thing?" B-10 addresses "does the patch's actual semantics match what we claim?" — different lens.
- **B-9 (cost/benefit)** addresses "is this fix worth shipping?" B-10 addresses "does what we ship match what we describe?" — different concern.

The four capabilities (B-7 / B-8 / B-9 / B-10) form complementary gates before upstream submission. None subsumes another.

#### Open questions for design phase

1. **AST parsing infrastructure**: which languages does B-10 target initially? Java (gson is a primary QPB benchmark) and Python (most QPB targets) are highest-priority. Other languages added as benchmark targets demand.
2. **Adversarial input generation strategy**: hand-curated boundary sets per type/operation, OR property-based generation (Hypothesis-style), OR LLM-driven adversarial generation. Different cost/effectiveness trade-offs; default for v1.7.0 implementation likely starts with hand-curated boundary sets for common types and grows.
3. **Reference site detection**: how does B-10 know which sites the patch claims to mirror? Explicit `file:line` citations in the writeup are the cleanest; free-prose phrases like "mirrors X" need extraction. Force writeup-format to include explicit citations? OR LLM-extract the references? Both have failure modes.
4. **What counts as "divergence"?**: should B-10 flag ALL behavioral differences, or only differences that would matter for the bug's input domain? The 2^53 case in BUG-005 might be intentional (operator wants stronger contract) — needs operator-decidable surface, not auto-reject.

#### What this is NOT

- Not a static-analysis-only check. Level 3 (adversarial boundary testing) requires runtime execution of both the reference pattern and the patch. The AST-level checks (Levels 1-2) are weaker pre-filters; Level 3 is the discriminating gate.
- Not a proof of equivalence. B-10 surfaces detected divergence on specific boundary inputs. Cases where reference and patch agree on ALL chosen inputs but might still differ on un-tested inputs are possible. The boundary-input set is the protocol's contract.
- Not a substitute for B-8 or B-9. A patch that passes B-10 (semantics match claim) can still fail B-8 (test passes for wrong reason) or B-9 (fix not worth shipping). All four gates apply independently.

## Part 3 — Design decisions to make before v1.7.0 implementation

### 3.1 Architectural choice for Part 1 (see §1.5 table)

`quality_gate.py` extension vs `bin/skill_gate.py` separate module vs external validator. Pick before §1.1-1.3 implementation begins.

### 3.2 Scope — which of Part 2 lands in v1.7.0 vs deferred further

10 capabilities (B-1 through B-10). Some are user-blocking (B-1 prompt-injection isolation is a security concern; B-8 weak-assertion blocks shipping flaky QPB tests; B-9 fix-worth-shipping evaluation prevents wasted upstream-maintainer review time; B-10 claim-vs-implementation consistency prevents semantically-wrong upstream submissions). Some are nice-to-have (B-4 bug-neighborhood iteration is a quality-of-life improvement). v1.7.0 implementation should pick a subset based on:

- Empirical evidence from v1.5.9 release runs (what bit adopters?)
- Coordination availability with external maintainers (B-8 ties to bugspec; B-7 ties to bug-PR automation downstream; B-9 ties into B-7's emit filter; B-10 ties into B-7/B-9 as a complementary gate)
- Token-cost budget (adding 10 capabilities at once is a large context expansion in SKILL.md, which v1.5.9 just trimmed)

Default recommendation: prioritize B-1 (security) + B-8 (test quality) + B-9 (fix-worth-shipping evaluation) + B-10 (claim-vs-implementation consistency) for v1.7.0. Defer B-2 / B-4 / B-5 to v1.7.0 unless surfacing demand. B-9 and B-10 are both new (added 2026-06-08 — B-9 after the gson PR #3036 closure; B-10 after the BUG-005 fix-claim review of gson run `20260604T220125Z`). All four default-set capabilities (B-1 / B-8 / B-9 / B-10) are complementary gates that share a B-7-emit-pipeline integration; they should land together for coherent v1.7.0 scope.

### 3.3 Voice / opinionation level for the §1.3 semantic Council prompt

The Council audit prompt has to declare what "coherent skill" means. Subjective territory. Need a style guide before launching reviewers.

### 3.4 Scope — QPB-only vs every-adopter-skill validator

Part 1 ship-gate validators could remain QPB-specific (only `quality_gate.py` validates) OR become a reusable skill-validation library that other adopter skills can pull in. v1.7.0 should pick.

---

## Part 4 — Carry-forward methodology lessons

Lessons surfaced during v1.5.7 / v1.5.8 development that should be absorbed into `ai_context/DEVELOPMENT_PROCESS.md` before they fade:

- **Defensive-sweep Council charter** (origin: 207) — absorbed during v1.5.8 close-out. No v1.7.0 action needed.
- **Release close-out sequence** (origin: 2026-06-07) — absorbed during v1.5.8 close-out. No v1.7.0 action needed.
- **Patch-authoring discipline** (origin: 2026-06-06 gson PR cascade) — verify it's documented in DEVELOPMENT_PROCESS.md; if not, file a v1.7.0 micro-instruction to add it.
- **Multi-step shell discipline** (origin: 2026-06-06 gson recovery script failures) — same verification.
- **Velocity-pressure self-imposed deadline pattern** (origin: 2026-06-06 cross-chat audit) — same verification.

These are documentation actions, not feature work. v1.7.0 should sweep them early so the actual feature work isn't entangled with methodology corrections.

---

*End of v1.7.0 Design. Implementation plan in `QPB_v1.7.0_Implementation_Plan.md`. Predecessor scope in `QPB_v1.5.9_Design.md`.*
