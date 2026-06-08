# QPB Development Process

*Last updated: 2026-05-23 (v1.5.7 ship — process documentation unchanged from v1.5.6 baseline, plus two v1.5.7 additions: the instruction-file numbering convention and the distribution-channel publish-safety gate. v1.5.7 ran end-to-end through the orchestrator/worker pattern via `v1.5.7_runner/`, with a council-of-two fallback (claude CLI + codex CLI) substituted for full Council-of-Three when the Copilot CLI — then the deprecated `gh copilot` extension; superseded by the standalone `copilot` CLI per v1.5.7 089f — was rate-limited mid-release. Per-release narrative on the council-of-two pattern, strict file:line consensus discipline, and the no-carry-forward principle is saved for v1.6.0). Single source of truth for how the Quality Playbook project is developed. Read at session start by any AI agent (Cowork, Claude Code, codex, etc.) orchestrating QPB development.*

This document covers **how QPB is developed** — the mechanical procedures, the rationale behind them, and the open directions for evolving the process itself. It is the parallel for QPB-the-project of what `IMPROVEMENT_LOOP.md` is for QPB-the-skill: the methodology doc.

Versioned historical artifacts (per-release retrospectives, Council syntheses, Bootstrap Findings, Scope Audits) live in `docs/process/QPB_v<X.Y.Z>_*.md` and are immutable once written. This doc is forward-facing and updated as the process evolves.

---

## 1. Mechanical procedures

### Release mechanics

- **Tag format:** `vX.Y.Z` — strict semver. Patch releases (`v1.5.4.1`) are reserved for corrective patches against a tagged release; feature work increments the minor (`v1.5.4` → `v1.6.0`). No date-based tags.
- **When to tag:** at the end of mechanical-release work (Phase 10 in the canonical Implementation Plan), after the Council umbrella review returns a Ship verdict and after every gating test has passed.
- **Who tags:** Andrew. Cowork and Claude Code never tag. The orchestrating AI prepares the mechanical-release commit (version stamps, README, CHANGELOG, schemas.md banner, orientation-doc updates) and STOPs at "ready to tag." Andrew tags + pushes + verifies origin.
- **Verify-before-claiming "shipped":** never declare a tag, push, or merge has landed without observing it directly. Required:
  - `git ls-remote origin <ref>` confirms the SHA on origin matches local
  - For commits: `git log origin/<branch> --oneline -5` shows the commit
  - When the bash sandbox can't authenticate to origin: explicitly say so and ask for confirmation rather than claiming success based on command issuance
  - This rule was born from the 2026-04-26 "v1.5.2 fully shipped" incident where a commit sat dangling locally for hours after a push that never reached origin
- **Merge to main:** at the end of release close-out, NOT at tag time. See close-out sequence below.

### Release close-out sequence

Once the work is implemented, tested, Council-reviewed Ship, and the tag is in place, the close-out sequence to fully ship a feature release runs these steps in order. Each step must complete cleanly before the next begins. The orchestrating AI prepares each step's artifacts; Andrew executes any irreversible action (push, publish, merge).

1. **Push the release branch** to origin (`git push origin <branch>`). Verify via `git ls-remote origin <branch>` per the verify-before-claiming rule.
2. **Move the tag if needed** and force-push (`git tag -f v<X.Y.Z> <commit> && git push --force origin refs/tags/v<X.Y.Z>`). Verify via `git ls-remote origin refs/tags/v<X.Y.Z>`. Default policy: the tag tracks the release-HEAD that includes all post-Council fixes the release actually shipped, so adopters who clone the tag get the working version. If a tag move would conflict with adopter consumption of a previously-published artifact, defer to operator judgment.
3. **Run live publishes** for every distribution channel via the scripted publish gates (`bin/publish_pip.py`, `bin/publish_npm.py`, `bin/submit_awesome_copilot.py`, plus any release-specific new channels). Each script enforces its pre-flight gate (clean tree, version parity, tag presence, no forbidden bundle contents, channel auth) before any irreversible upload. Two-phase where applicable: test channel first, operator-confirmed prod publish second.
4. **Update README.md + plugins/quality-playbook/skills/quality-playbook/ai_context/TOOLKIT.md** with the new release's install instructions for each channel. These updates land on the release branch as post-tag commits; they describe the just-published artifacts, so they can only be authoritative after step 3.
5. **Refresh ai_context/DEVELOPMENT_CONTEXT.md** to reflect any operationally-relevant changes (install flow, bootstrap completeness, new channels, new commands). Also a post-tag commit on the release branch.
6. **Ship any release-specific channel work** (e.g., new marketplace submission process, new packaging format, new plugin manifest). If a new publish script is warranted, file it as a runner instruction and let it land on the **release branch** BEFORE the merge. This keeps everything publish-channel-related contained in the release that owns it — no patch-branching or cherry-picking afterward.
7. **Merge the release branch into main** (`git checkout main && git pull && git merge --no-ff <branch> -m "Merge <branch> into main"`). Push main and verify on origin per the verify-before-claiming rule.
8. **Branch the next feature version off main** only AFTER step 7 lands cleanly on origin. Never cut the next-version branch before close-out is complete; in-flight publish-script work, README updates, and orientation-doc refreshes belong to the closing release, not the next one.

**Why merge happens at the end, not at tag time.** The methodology previously specified "merge to main at tag time." Empirically, v1.5.8's close-out (instructions 197-203) showed that real publish-channel work — discovering bugs in the publish scripts during dry-run, fixing them, adding new channels — happens AFTER the tag is in place. Merging at tag time would force all that work onto a patch branch (`v1.5.8.1`) or cherry-picked onto main, both of which fragment the release's history. Keeping the release branch open through full close-out lets every commit related to that release live in one branch boundary.

**Why publish happens before the README install instructions.** The install instructions describe the just-published artifacts. Merging install-instruction commits to main that point at a not-yet-published version is a documentation lie window — anyone reading main during that window gets instructions for non-existent artifacts. Publish first, document second.

**Why each publish channel needs a script and a dry-run gate.** Per § "Distribution-channel publish safety" below. Hand-typed publishes accumulate invisible failures; every new channel earns a script. The scripts MUST be exercised via `--dry-run` on the operator's machine before any live publish, because the dry-run gate validates the full publish path end-to-end against real artifacts (not mocked subprocess responses, which is the gap that produced instruction 203's npm-pack JSON parse bug).

### Branch model

- One feature branch per minor version (`1.5.4`, `1.6.0`). Long-lived during the release's development arc, INCLUDING through full close-out per the sequence above.
- Branched from main; merged back at the END of close-out (step 7 above), not at tag time.
- Patch corrections branch off the tag (`v1.5.4.1` from `v1.5.4`), merge back to main and to any in-flight minor branch.

### Commit hygiene

- **Subject format:** `vX.Y.Z [Phase Y]: <scope>` for phased work; `vX.Y.Z: <scope>` for non-phased.
- **Coherent commit boundaries:** one logical change per commit. F-1..F-4 + Phase 4 + Phase 5 was three commits, not one — three logically distinct units (bootstrap findings, schema, apparatus). Phase 3.9.1 was one commit because it was two related two-line fixes for a single bug class.
- **Body content:** what landed, why, test counts before/after, mutation-verification results for regression-pin tests, Co-Authored-By line for the implementing agent.
- **Commit cadence within a work session:** at coherent boundaries, not "once at the end." A 5-phase work session typically lands 3-5 commits.
- **No commits during STOP-and-ask boundaries:** if the orchestrating AI hits a decision point that needs Andrew, it stops without committing. Andrew commits when ready or instructs the agent to continue and commit.

### Claude Code (or any implementing-AI) handoffs

- **Minimal-prompt pattern.** The handoff prompt is short and points at canonical docs:
  ```
  Read these end-to-end:
    - <canonical design doc>
    - <canonical implementation plan>
    - <relevant findings doc>
    - ~/Documents/AI-Driven Development/CLAUDE.md
  Implement what's in scope per the plan. Decompose as you execute.
  Report at end-of-session or at a STOP-and-ask boundary.
  ```
- **No per-phase briefs.** The canonical design and implementation-plan docs are the spec. Generating per-phase briefs is over-engineering — it pre-decomposes the work in ways that often diverge from what's actually in the canonical docs, creating drift and dropped requirements.
- **Don't pre-decompose for the implementing AI.** It runs the same model class as the orchestrating agent; it can decompose during execution. The orchestrator's job is scope + STOP boundaries + canonical-doc pointers, not work breakdown.
- **STOP-and-ask boundaries** are few and explicit. Typical: end of a phase that requires Andrew's diagnostic input (calibration cycle diagnoses); pre-tag mechanical commit; any encountered bug in QPB source mid-run that's outside the in-scope finding set.
- **Multi-session coordination via shared directory.** For coordinating two AI sessions through a shared directory (a chat-side orchestrator and a coding-side worker exchanging instruction and output files), see `AI_ORCHESTRATION_PATTERNS.md`. This is the file-level realization of the diagnosis-then-Claude-Code-lane rule and the default execution mode for v1.5.6+ work that spans multiple sessions. **v1.5.6 was the first release implemented end-to-end via this pattern**: a `v1.5.6_runner/` runner folder coordinated the chat-side orchestrator and the coding-side worker across the release's full development arc (Pattern 7 cycle execution + adopter-facing install script). When the Anthropic budget became constrained mid-release, Codex was used as the worker for the non-Anthropic-budget phases by switching the runner backend; the file-based instruction/output protocol made the handoff clean. See `AI_ORCHESTRATION_PATTERNS.md` for the pattern itself and section 9's worked example for the v1.5.5/v1.5.6 runner walkthroughs.
- **Instruction-file numbering.** Runner instruction files use a `<work-item><letter>` scheme (e.g. `089m`, `089x`, `089z`). The letter is a sequential sub-step within a work-item; when the letters run out (`z`), the work-item number rolls and the suffix restarts at `a` — so `089z` is followed by `090a`. The roll is cosmetic: `090a` does NOT mean "`090` has sub-steps," it just means "the next instruction after `089z`." The runner keys off the filename, not the scheme, so the exact label never affects execution. Within a release's polish arc, keep advancing the letter suffix; only roll the work-item number when the prior letter space is full.

### Council protocol

QPB development uses Council-style review on substantial work. Three flavors, scaled to the work:

- **Focused single-panel review** — for small commits (e.g., Phase 3.9.1's two-line fix). The orchestrating AI examines the diff, mutation-tests regression pins, checks scope discipline, writes a brief verdict. Single perspective; quick.
- **Parallel-Agent reviewers** — for larger commits (e.g., Phase 5 apparatus, ~700 LOC). The orchestrating AI spawns 3 Agent reviewers with orthogonal lenses (typically: correctness, scope/discipline, architectural integrity). Each reviews independently; orchestrator synthesizes findings into a single verdict (Ship / Hold-with-fixes / Block).
- **Full nested 9-perspective Council** — for foundational/architectural changes or umbrella reviews before tag. Three outer models (`gpt-5.4`, `gpt-5.3-codex`, `claude-sonnet-4.6`) via the Copilot CLI (the new standalone `copilot -p` per v1.5.7 089f, or the deprecated `gh copilot --prompt` extension during the grace period — both shimmed transparently by `bin/copilot_resolver.py`), each spawning its own three-reviewer panel internally. Protocol details in workspace CLAUDE.md (cd-into-repo discipline; nested-panel trigger header; suspicious-convergence flag).

**Iterate to clean review.** A first review surfacing P0 findings is normal and expected. Fix-up commit → focused re-review → if new findings, fix-up again. Multi-round (Round 1 → Round 2 → Round 3) is the norm, not a sign of trouble.

**Council on landed code.** Run reviews on commits that have landed in the working tree, not on briefs or proposals. Pre-implementation Council review (e.g., reviewing a brief before coding) is over-engineering — the implementing AI is competent enough that pre-review adds bureaucracy without catching what implementation review would catch anyway.

### Worker self-Council protocol (v1.5.7 187+)

Formalization of the "Parallel-Agent reviewers" Council flavor with stricter discipline. Used since 186-followup-1 across 187 / 188 / 189 / 190; has demonstrably caught ship-blockers a single-reviewer pass would have shipped (187's manifest round-trip persistence gap, 188's `_try_acquire_pool_slot` race, 188's 6-site `CANCELLED` display gap, 190's em-dash-IS-in-cp1252 boundary distinction). The pattern is now load-bearing methodology, not an option.

**When the worker (Claude Code or equivalent implementing AI) is in-flight on a FIX-REQUIRED instruction, before filing the v1 review-request to Cowork:**

1. The instruction's "Worker self-Council" section enumerates 3 panelist charters with distinct lenses (typically: correctness/spec-compliance, test sufficiency, regression-safety — adapt to instruction scope). The implementing AI spawns the three panelists in parallel via its native `Task` (or equivalent) tool, each receiving its charter as the prompt.

2. Each panelist writes its full verdict to a file: `Reviews/v<NNN>_self_council/panelist_<X>_<charter>.md`. The path is part of the panelist's prompt — without explicit Write-to-file, the artifact can be lost to streaming / TUI buffering misbehavior.

3. The implementing AI reads all 3 panelist files + synthesizes them to `Reviews/v<NNN>_self_council/synthesis.md`. The synthesis names where panelists agree (highest confidence), where they diverge (judgment calls), and a single SHIP / FIX-REQUIRED verdict.

4. **If self-Council surfaces FIX-REQUIRED, the implementing AI iterates on the fix BEFORE filing the v1 review-request.** Only files v1 when synthesis says SHIP. This makes the internal panel the load-bearing first-pass quality gate; the external Cowork review is the second layer.

**Why each panelist must write to file:** belt + suspenders. Even with `--max-turns 60` and stream-json output and tee'd stdout, transient buffering misbehavior can drop the panelist's verdict. The Write tool guarantees the artifact survives.

**Why the panel must be 3 separate subagents and not the implementing AI's own context:** the worker is the implementer; self-review by the same context gives no diversity. Each panelist is a separate subagent context with no exposure to the implementer's reasoning trace.

**Why FIX-REQUIRED iterates in-branch:** the protocol's whole point is that a green 1163-test suite would have shipped a regression that defeated the instruction's target plan (187's Panelist C example). Filing v1 with a known FIX-REQUIRED is shipping the bug.

**Adapting panelist charters to instruction scope:** the three panelists should be orthogonal lenses, not three views of the same thing. Worked examples that have shipped:
- 187: plan-schema correctness / launch-site correctness / regression safety
- 188: kill-semantics correctness / collector skip-CANCELLED correctness / status-TUI display correctness
- 189: sweep completeness / encoding-strategy correctness / regression and test quality
- 190: sweep completeness / encoding-strategy correctness / regression safety + test quality

The "sweep completeness" charter shows up specifically for AUDIT-table-pattern instructions (see next section); the "encoding-strategy correctness" charter showed up for both cp1252 instructions in the trifecta and codified the per-character boundary (Panelist B in 190 pinned that cp1252 actually maps U+2014 em-dash to byte 0x97 — only U+2265, U+2264, → and similar crash, not em-dashes).

### Defensive-sweep Council charter for content-fix instructions (v1.5.8 207+)

When an instruction enumerates specific text changes to a single artifact (template strings, hardcoded facts, prose corrections), at least one Council panelist's charter MUST include a defensive sweep: **"is this defect class present elsewhere in the same artifact?"** Not just "do the listed fixes match canonical sources" — the panelist actively grep's the same template / file / function for additional instances of the same defect shape that the instruction didn't enumerate.

**Why this matters.** An instruction's enumerated fix list + the worker's mechanical application can agree with each other while leaving identical defects elsewhere in the same artifact. The worker correctly applies the 6 listed fixes; the panelist correctly verifies the 6 listed fixes match canonical sources; both are technically right; the regenerated artifact still ships with 1-4 identical-class defects that were never enumerated. Without a defensive sweep, the next adopter or the next PR review surfaces those identical defects and we re-spend the same instruction-Council-fix cycle on what should have been one pass.

**Origin: 2026-06-07 instruction 207.** Andrew's review of the trimmed awesome-copilot SKILL.md surfaced 8 specific factual errors (Python version, command names, phase names, bundle count). The instruction enumerated all 8. Panelists A and B verified all 8 fixes matched canonical sources. Panelist C's defensive sweep caught a 9th instance in the SKILL.md body (the same "seven phase-prompt directories" miscount that PR_BODY error #6 fixed in a different file) — same defect class as an instruction-enumerated fix, present in a sibling artifact, NOT listed in the spec. C's `FIX-REQUIRED` correctly forced the worker back through the template with the same lens before push. Pre-207 default behavior was "fix exactly what's enumerated, NIT-defer everything else as out-of-scope"; that ships a half-fixed artifact.

**Structural shape.** This pattern echoes the 199 → 199-followup-1 mock-reality divergence (test mocks + production agreed with each other while disagreeing with reality). Both are instances of "two layers of verification agree with each other while leaving reality incomplete." For 199 it was mocks ↔ production; for 207 it's instruction-enumeration ↔ mechanical-application. The structural fix is the same: a verification step that grounds itself in reality / canonical truth / the same defect class, not in the prior layer's claims.

**Required Council charter language.** For any instruction that enumerates specific text fixes (vs. structural / behavioral / test-coverage changes), the panelist charter should include this clause verbatim or equivalent:

> "Identify whether the same defect class extends beyond the specific sites named in the spec. Grep the affected template / file / module for additional instances of the same shape. Treat any matches found as in-scope FIX-REQUIRED unless the instruction explicitly OUT-OF-SCOPED them with rationale."

Apply this for: hardcoded string corrections, factual-claim updates, terminology consistency, version-bump propagation, command-rename refactors, schema-field updates. Skip this for: pure behavior changes (a new function, an algorithm fix), test additions, refactors where the defect class is structural rather than textual.

### AUDIT-table invariant test pattern (v1.5.7 184+)

When a defect class shape is observed across multiple sites in the codebase, the fix is incomplete unless it includes an exhaustive-sweep invariant test that scans the entire relevant tree and asserts the contract holds at every site. Has shipped across 184 (`_pid_alive` divergence), 189 (log-read encoding fallback), 190 (subprocess stdin encoding) — three confirmed reuses graduate it from "pattern" to "standard mechanism."

**The pattern:**

1. **Identify the defect-class shape.** "X-shaped sites in tree Y must hold property Z."
2. **Find all instances via grep / inspection.** Document the result as an AUDIT table in the test file or its docstring: file:line → verdict (FIXED / SAFE-with-justification / DEFERRED-with-justification).
3. **Write a single sweep test that enumerates all sites and verifies the contract.** Use grep / regex / AST walk to find sites; check each against the AUDIT-table allow-list. Future PR readers adding new X-shaped sites must either land them with the contract OR add an explicit justified entry to the AUDIT.
4. **The test is the durable defense.** The targeted fix at the originally-discovered site is necessary; the sweep test is sufficient against the recurrence at a sibling site that hasn't been noticed yet.

**Worked examples:**

- 184 `NoResidualPidAliveDivergenceTests` (test_platform_compat_180.py:974): three tests — `test_184_no_local_pid_alive_definitions_in_bin` (regex sweep for `^def (_pid_alive|pid_is_alive|_pid_is_alive)\(`), `test_184_no_os_kill_pid_zero_outside_platform` (inverse sweep for `os.kill(<anything>, 0)` literals), `test_184_all_pid_alive_helpers_share_one_implementation` (runtime `is` identity check that all 5 alias sites resolve to `_platform.pid_alive`).
- 189 `test_no_unguarded_external_log_reads_remain` (test_log_read_encoding_189.py): 22-entry AUDIT table for `encoding="utf-8"` reads of external content; each must include `errors="replace"` OR be on the documented allow-list.
- 190 `test_no_subprocess_run_with_text_true_lacks_utf8` (test_subprocess_encoding_190.py): 14-entry per-file AUDIT table across `bin/run_playbook.py` + `bin/harness/**/*.py`; each `subprocess.run(text=True, ...)` site must explicitly pass `encoding="utf-8"` + `errors="replace"`.

**When to file an AUDIT sweep test:**

- The defect class fired **a third time across QPB**. (Two instances may be coincidence; three is a pattern.)
- The shape is identifiable via mechanical scan (regex, AST, identity-`is` check).
- A reasonable future PR could re-introduce the same defect at a new site without anyone noticing.

The cp1252-on-Windows hazard surface (185 print output + 189 log read + 190 subprocess stdin write) is the canonical worked example of a defect class fired three times: each instance was fixed at its specific site, AND each landed with its own AUDIT-table invariant test, AND the three sites together are now documented as a design contract in `docs/design/QPB_Test_Harness_1.5.7_Design.md` Section O ("Windows cp1252 hazard surface"). Future PR reviewers reference Section O before approving any new `subprocess.run` / `open(text=True)` site.

### Mutation-test discipline

For every regression-pin test (a test that exists specifically to prevent a known bug from re-emerging):

1. Revert the specific source line(s) the test pins
2. Run the test; confirm it fails with the expected error message
3. Restore via `git checkout <file>` or `git restore <file>`
4. Re-run; confirm the test passes again

Cite the mutation result in the commit message. Without mutation verification, "regression tests" don't actually pin anything — they could be tautological assertions that pass regardless of the source. Mutation testing is the proof that the test would catch reintroduction.

### Run-state instrumentation and the Phase 5 source-edit guardrail (v1.5.5+)

QPB runs (both adopter-facing and bootstrap/calibration) emit an append-only `quality/run_state.jsonl` event log. The format invariants and event taxonomy live in `plugins/quality-playbook/skills/quality-playbook/references/run_state_schema.md`; the read/parse/write helpers ship at `plugins/quality-playbook/skills/quality-playbook/scripts/run_state_lib.py` (the bundle copies it to `<install>/bin/run_state_lib.py` at adopter install time) (`read_events`, `last_in_progress_phase`, `validate_run_state_file`, `validate_phase_artifacts`, `validate_no_source_edits`, `append_event`, `write_progress_md`).

Two post-condition checks are wired in mechanically and matter for development discipline:

- **`validate_phase_artifacts`** fires at each phase boundary; a `phase_completed` event with a failing validation result indicates the phase produced an event but the artifact set was incomplete. Treat such states as malformed runs — diagnose the gap before progressing.
- **`validate_no_source_edits`** is wired into `bin/run_playbook.py:_finalize_iteration` as a mechanical Phase 5 source-edit guardrail. Any file modification outside `<target>/quality/` during finalization is recorded as a `validation_result` event with `status="fail"` and the run is tainted from a recall-comparison standpoint. **Implication for development sessions:** if you're hand-editing QPB source while a calibration cycle is running against the same checkout, the guardrail will fire on the cycle's Phase 5; use `git worktree add` to give each cycle its own checkout per `CALIBRATION_PROTOCOL.md` Pre-flight check #8.

The v1.5.5 substrate also includes the `agents/calibration_orchestrator.md` spawn-and-resume template (the Mode 1 autonomous-loop driver for cycles per `CALIBRATION_PROTOCOL.md`) and `bin/visualize_calibration.py` (four cycle charts: per-bug × cycle heatmap, lever × benchmark heatmap, recall trajectory, Mermaid lever-interaction graph). These are operational deliverables, not just docs — treat them as canonical when working on any cycle-related code.

### Calibrated reporting

When the orchestrating AI reports state to Andrew, each of these rules is about not over-claiming confidence in a specific dimension:

- **No wall-clock time estimates** (don't over-claim confidence about how long something will take). They've been consistently wildly wrong: 4m actual vs "30 minutes" estimated; ~2-3 hour actual vs "14-22 hours" estimated. Useless or actively misleading.
- **Don't claim "100% complete" without an audit** (don't over-claim confidence about scope completeness). When asked "is X complete?" — verify against canonical sources before answering yes. Cowork has a documented pattern of dropping things; never trust the orchestrator's recall as a completeness signal.
- **Don't conflate AI identities** (don't over-claim confidence about which agent did what). Codex desktop, Claude Code, and Cowork are distinct agents with distinct roles; codex desktop is the empirical-bootstrap agent, Claude Code is the development-session agent, Cowork is the orchestrating chat agent. Sloppy attribution causes confusion when reviewing artifacts later.

### SKILL.md token-ceiling discipline

`bin/tests/test_skill_md_size.py` pins SKILL.md below a BPE (cl100k_base) token ceiling — currently **32,000** (v1.5.7 instruction 090m). **This ceiling is an arbitrary, owner-chosen soft tripwire — NOT a hard technical limit.** It exists to catch unintended SKILL.md bloat, and is bumped DELIBERATELY when a change is worth the tokens. Per the 090m owner note: *"If an extra 2k tokens make a difference we're probably dealing with a far too limited AI to do this work anyway."* When a SKILL.md edit breaches the ceiling, the question is "is this change worth the tokens?" — if yes, bump the ceiling here (with a one-line rationale appended to the test's module docstring, the same way prior widenings were documented); if no, trim references/*.md or SKILL.md content. The bound is operational hygiene, not a model-capability constraint.

---

## 2. Rationale

Each rule in Section 1 emerged from a specific incident or recurring pattern. This section pairs the rule with what produced it, so anyone reading the rule later understands what bug the rule is meant to prevent — not just the rule itself, but the failure mode it's a response to.

### Verify-before-claiming "shipped"

**Origin: 2026-04-26 v1.5.2 push incident.**

Cowork told Andrew "v1.5.2 is fully shipped" after issuing a `git push` command, but the README commit (`bcdd08e`) had never actually reached origin. The bash sandbox couldn't authenticate to GitHub via HTTPS; the push command was issued but the orchestrating AI assumed success. The commit sat dangling locally for hours and almost got garbage-collected. Recovery required a multi-branch cherry-pick the next day.

**Failure mode:** confidence-calibration mistake — the orchestrator inferred "command issued = command succeeded" without verifying the resulting state.

**Generalization:** any external-state change requires direct observation, not inference from command issuance. Don't say "the harness is running" without `ps`; don't say "the test passed" without seeing test output; don't say "the file was created" without checking the path.

### Read canonical doc before authoring planning content

**Origin: 2026-04-26 v1.5.3 sequencing-edit misfire.**

Cowork wrote a v1.5.3 sequencing edit to `ai_context/IMPROVEMENT_LOOP.md` (commit `7d5e36c`) plus a C13.11 brief, a Round 9 Council prompt, and a Claude Code launch command — all without ever reading `docs/design/QPB_v1.5.3_Design.md` or `docs/design/QPB_v1.5.3_Implementation_Plan.md`. Those canonical docs documented v1.5.3's actual scope (Phase 0 project-type classifier + four-pass skill-derivation pipeline + skill-divergence taxonomy). The planning content Cowork wrote was approximately unrelated to that scope.

**Failure mode:** the orchestrator treated summary docs (IMPROVEMENT_LOOP.md, prior Council briefs) as if they were specifications. They aren't. Specifications live in `docs/design/<project>_v<X.Y.Z>_*.md`. Summaries describe specifications; they don't replace them.

**Diagnostic signature.** A planning doc that sequences work items with confident structural language but cites only summary-doc references ("per IMPROVEMENT_LOOP.md") rather than `docs/design/` line numbers is the smoking gun. Always cite the canonical doc by line/section reference; if you can't, you didn't read it.

### No per-phase briefs / don't pre-decompose for the implementing AI

**Origin: 2026-04-30 v1.5.x process retrospective.**

The v1.5.4 development arc accumulated per-phase briefs (Phase 3.6 Brief, Phase 3.7 Brief, Phase 3.8 Brief, etc.), each pre-decomposing the work for Claude Code in detail. The retrospective documented two consequences: (a) the briefs became surface area where requirements got dropped (B-18b deferred to "release coordination" framing instead of staying in v1.5.4 scope, until Andrew explicitly called it out); (b) the briefs duplicated content from canonical Implementation Plan + Findings docs, creating drift between the two sources.

**Failure mode:** the orchestrator mistook "showing my work" for "doing useful work." Pre-decomposition felt like rigor but was bureaucratic overhead that the implementing AI didn't need (it runs the same model class; it can decompose during execution) and that introduced errors the canonical docs didn't have.

**Generalization:** the orchestrator's job is scope + STOP boundaries + canonical-doc pointers. The implementing AI does the work breakdown.

### Iterate to clean review

**Origin: 2026-04-30 first and second Councils on v1.5.4 Phase 5 apparatus.**

Both Councils were intended as final pre-Phase-6 reviews. Both surfaced P0 findings the prior round didn't catch. First Council: P0-1 parser bug + P0-2 SHA256-substring-vs-actual-hash bug. Fix-up commit closed both. Second Council: P0-3 H2-heading parser gap + P0-4 `_QPB_SOURCE_PATHS` missing `phase_prompts/`. Same class of bugs (test-coverage shape gaps; architectural-update missing matching-guardrail update) — different specific instances.

**Failure mode:** "review found nothing" is rare on substantial work. Treating a single clean review as evidence the work is done risks missing the next class of similar bug.

**Generalization:** multi-round review is the norm on substantive commits, not a sign of trouble. Each round closes a class of finding; the next round may find the next class. The terminal condition is a clean review, not a single-pass review.

### Council on landed code

**Origin: 2026-04-30 retrospective + repeated experience that pre-implementation Council reviews of briefs add ceremony without catching what implementation review catches anyway.**

Briefs and proposals are abstract; landed code is concrete. Council reviewers reading a brief can flag scope concerns and catch architectural inconsistencies, but they can't catch the kinds of bugs that empirical inspection of the code finds (parser regex shape mismatches, missing guardrail updates, mutation-test gaps). Pre-implementation review duplicates the cheaper "Cowork sanity-checks the brief in chat" step without adding incremental value.

**Generalization:** Council protocol's strength is on landed code. Brief-time review is fine for sanity-checking framing, but the load-bearing review happens after the implementing AI has produced a diff that can be inspected.

### Distribution-channel publish safety

**Origin: 2026-05-23 v1.5.7 pip/npm channel saga + the pre-publish channel-architecture Council.**

The v1.5.7 distribution channels (pip / uvx / pipx + npx) produced a string of bugs that surfaced only when a human built and installed the *real artifacts* — none caught by the test suite: compiled `.pyc` cruft in the tarballs (089y); a silently-dropped `bin/_purpose.py` that crashed every install (090b); and — caught by the pre-publish Council *before* it shipped — a clean `python -m build` / `npm pack` that succeeded while shipping an **empty bundle**, plus a documented `python3 bin/build_channel_package.py --stage` that resolved `from bin import install_skill` to an unrelated sibling repo's `bin/` and produced a broken bundle (090c). Every one shared a root cause: the channel build/packaging path **diverged from what the clone-based tests exercised** (`python3 -m bin.X` with an intact `bin/` on `sys.path`), and nothing executed the *built artifact* end-to-end.

**Failure mode:** a published package version is effectively irreversible — PyPI and npm do not let you cleanly replace a version once published — and clone-based tests do not exercise the channel install path. So packaging bugs ship green and reach real adopters before anyone notices.

**Generalization — gate before any channel publish.** A release that publishes a distribution channel does not get tagged until: (1) a **clean-clone cold-build test** — build the wheel/sdist and `npm pack` from a fresh checkout with NO pre-staged bundle, asserting the artifacts contain the complete bundle (an empty or partial bundle must be impossible, not merely warned about at runtime); (2) a **built-artifact end-to-end test** — install the built wheel/tarball into a throwaway environment and run the real entry points (`install` + `validate`), not just the clone path; and (3) an **architecture review** (Council on the channel packaging) before the tag. Bundled scripts must be *foreign-`bin`-proof*: any `from bin import X` needs a path-load fallback (anchored on the script's own location) so it can never resolve to a sibling repo's `bin/`. Treat "the channel tests pass" as insufficient evidence until the built artifact has been installed and run from a clean clone.

### Publish scripts (pip + npm + awesome-copilot)

**Origin: 2026-06-06 v1.5.8 instruction 202 — hand-typed publishes accumulate invisible failures.**

The v1.5.8 ship sequence formalizes three publish channels into scripted form so each publish is reproducible and each pre-condition is checked before any irreversible upload:

- **pip** — `bin/publish_pip.py`. Eight pre-flight checks (clean tree, version parity across pyproject/package/init, tag exists, tag is HEAD ancestor, `bin/build_channel_package.py` stages cleanly + `python -m build` produces wheel+sdist, 089u parity test passes, no forbidden contents in dist artifacts, twine auth configured). Two-phase publish: test PyPI first → operator runs the printed `pip install -i https://test.pypi.org/simple/ ...` in a clean venv → operator confirms → prod PyPI upload → `pip index versions` verification (or curl fallback to `https://pypi.org/pypi/quality-playbook/json`). `--dry-run` flag exercises every step except the actual twine upload.

- **npm** — `bin/publish_npm.py`. Seven pre-flight checks (clean tree, version parity, tag exists, `npm whoami` succeeds, `build_channel_package.py --stage` succeeds, no forbidden contents in staged bundle, `npm pack --dry-run` succeeds and emits a clean file list). Operator-confirmed `npm publish --access public` then `npm view quality-playbook version` verification. `--dry-run` flag.

- **awesome-copilot** — `bin/submit_awesome_copilot.py`. The registry is `github/awesome-copilot` (34k stars, official GitHub org). Skills live at `skills/<skill-name>/SKILL.md` with frontmatter (`name`, `description`, `license`) and the registry's own tooling (`npm start` — canonical pre-submit command that runs `skill:validate` + regenerates top-level `README.md`) is intended to run inside a clone of awesome-copilot, not inside QPB. **PRs must target the `staged` branch, not `main`** — the registry's `CONTRIBUTING.md` warns that branches from `main` "may be outright rejected." Because the QPB skill ships seven support directories that would exceed the registry's typical-skill footprint as bundled assets, the QPB script generates a **submission packet** under `dist/awesome_copilot_submission/` containing (a) a trimmed `skills/quality-playbook/SKILL.md` that links back to the canonical QPB repo for the full toolkit, (b) `PR_BODY.md` with the registry's required checklist, (c) `MANUAL_STEPS.md` walking through the fork → branch-from-staged → copy in → `npm start` → push → `gh pr create --base staged` flow. The script does NOT call `gh pr create` or push directly; the operator runs the manual steps after reviewing the packet.

**Awesome-copilot operator workflow (paraphrased from `MANUAL_STEPS.md` in the generated packet):**

1. Run `python3 bin/submit_awesome_copilot.py` from a clean working tree at the target version.
2. Fork `github/awesome-copilot` once (`gh repo fork github/awesome-copilot --clone=true`); `npm install` in the fork.
3. Branch off `upstream/staged` — **not** `upstream/main` (`git checkout -b add-quality-playbook-<version> upstream/staged`). The registry's `CONTRIBUTING.md` warns that PRs targeting `main` "may be outright rejected."
4. Copy `dist/awesome_copilot_submission/skills/quality-playbook/SKILL.md` into the fork's `skills/quality-playbook/`.
5. Run `npm start` in the fork (canonical pre-submit command — runs `skill:validate` + regenerates the top-level `README.md`); iterate until it succeeds.
6. `git add skills/quality-playbook/ README.md` (top-level `README.md`, NOT `docs/README.skills.md`), commit, push to the fork.
7. `gh pr create --repo github/awesome-copilot --base staged --body-file <packet>/PR_BODY.md` — target the `staged` branch explicitly.

The generated `PR_BODY.md` includes the registry's required checklist: read CONTRIBUTING, targeting `staged`, contribution type (new skill), `npm start` run locally, and a license note flagging QPB's Apache-2.0 vs the registry's MIT-only PR-template assertion (the operator-visible flag asks the maintainers to confirm before merging).

The submission packet is regenerated each run so it always reflects the current QPB version + SKILL.md frontmatter; the version-string parity check at the top of the script halts before generating anything if the three manifests disagree.

**Logging.** All three publish scripts write a per-run log to `~/.qpb/publish_logs/<channel>_<version>_<UTC-ISO8601>.log` so post-mortem of a botched publish has a trail. The log captures every pre-flight check verdict + every subprocess's stdout/stderr.

**Generalization:** every release-time external interaction (PyPI upload, npm publish, registry PR) is scripted, dry-runnable, and idempotent. The operator's job is to review the packet/file-list/confirmation prompt and type `y`, not to remember the command syntax. Hand-typed publishes are the documented failure mode this avoids.

### Mutation-test discipline

**Origin: pattern across multiple Council rounds where unit tests passed but real-input behavior failed.**

The v1.5.4 first Council found that the BUGS.md parser had unit tests using synthetic v1.5-era field shapes, but real archive files used different shapes (bold variants, no colon on heading) — synthetic fixtures masked the real-input failure. The fix-up added corpus-real-file tests that loaded BUGS.md directly from `repos/archive/`. The second Council found the same class of bug for H2 headings (`## BUG-NNN` vs `### BUG-NNN`) — same lesson, different specific shape.

A regression-pin test that's never been mutation-verified is a tautology risk: it might pass regardless of source state. Mutation testing (revert the source line; confirm test fails; restore) is the proof that the test would catch reintroduction.

**Generalization:** for any test that exists specifically to prevent a known bug, mutation-verify before declaring the regression "pinned." For corpus tests, fixtures should load from `repos/archive/` directly, not be hand-written from memory.

### Don't claim "100% complete" without an audit

**Origin: 2026-04-30 Remaining Work Brief audit.**

Andrew asked "are you sure this is 100% of the outstanding work?" after Cowork had drafted a v1.5.4 Remaining Work Brief. Initial impulse was to say yes. Audit (against the canonical Design + Implementation Plan + Bootstrap Findings + the v1.6.0 Design's carry-forward section) found 11 gaps including the entire ~22-item v1.6.x carry-forward backlog, several Phase 10 enumerations, F-1 architectural concerns, and the canonical-doc-refresh requirement.

**Failure mode:** completeness-claim without verification is a confident-sounding hallucination. Cowork has a documented pattern of dropping things; never trust the orchestrator's recall as a completeness signal.

**Generalization:** when asked "is X complete?" — verify against canonical sources before answering. The audit tool (parallel Agent reviewers comparing the brief to canonical docs) is fast; not running it is the failure mode.

### No wall-clock time estimates

**Origin: 2026-04-30 Andrew explicit pushback.**

Cowork's wall-clock estimates were repeatedly wildly wrong: a "30 minute" Phase 3.8 fix took 4m20s; a "14-22 hour" Phase 3.6 effort took ~2-3 hours.

**Failure mode:** the orchestrator was generating wall-clock estimates from training-data priors about human software-engineering effort, not from the actual work being done. The priors don't apply when the implementing AI does work in minutes that humans take hours for.

**Generalization:** stop generating time estimates for software work. They're useless when AIs do the work; misleading when humans plan around them.

### Don't conflate AI identities

**Origin: 2026-04-30 F-1 architectural-review identity confusion.**

In a Cowork response to Andrew, Cowork referred to "Codex" when the agent doing the development work was actually Claude Code (resuming a previous session). Codex was the earlier empirical-bootstrap-test agent, not the development-session agent. Andrew corrected: *"the response i gave you earlier was from when i restarted this in claude code resuming my previous session."*

**Failure mode:** the orchestrator was using "Codex" loosely as a synonym for "the implementing AI," which became inaccurate when the implementing AI changed mid-arc.

**Generalization:** distinct agents play distinct roles. **Cowork** is the orchestrating chat agent (this one). **Claude Code** is the development-session agent (committing source, running tests, structuring work via tasks). **codex desktop** is the empirical-bootstrap agent (operator pastes a one-line prompt to validate B-18b). Sloppy attribution causes confusion when reviewing artifacts later — a Council synthesis citing "codex's diagnosis" should not refer to Claude Code's diagnostic reasoning, and vice versa.

---

## 3. Plans / open directions

This section captures directions the development process *might* evolve in. Nothing here is committed work — these are framings for future conversation, not a plan-of-record.

### Bringing the development process under statistical control

QPB-the-skill has `IMPROVEMENT_LOOP.md` documenting the QC/QI methodology for *artifacts under audit*: regression replay measures bug-recall on benchmark targets, calibration cycles diagnose missed-bug classes, lever pulls move recall numbers, the calibration log accumulates evidence over time. That methodology is operational as of v1.5.4 (apparatus) + v1.5.5 (orchestration substrate: per-cycle event log, orchestrator template, post-condition checks, cycle visualization). The protocol that drives a cycle end-to-end lives in `ai_context/CALIBRATION_PROTOCOL.md`.

QPB-the-project (this document's subject — how the project itself is developed) has no parallel measurement apparatus. The development process produces qualitative findings (Council syntheses, retrospectives, scope audits) but no quantitative time series that could be tracked release-over-release and brought under statistical control under the SEI / Humphrey lineage. **The v1.7.0 design (`docs/design/QPB_v1.7.0_Design.md` + `QPB_v1.7.0_Implementation_Plan.md`) closes this gap directly:** it scopes Shewhart control limits applied to **both** the improvement loop (calibration cycles) and the SDLC for QPB itself. The questions in this section that ask "should the dev process be SPC-able at all?" are answered affirmatively in the v1.7.0 design — the trigger has fired.

Candidate metrics if such an apparatus were built:

- **Council-finding recall by round.** Number of P0 findings caught in Round 1 vs Round 2 vs Round N. If Round 2 reliably catches the next class of bug Round 1 missed, the review process is converging. If consecutive Councils each find new P0 classes (the v1.5.4 pattern: synthetic-fixture coverage gaps in two flavors), the review apparatus itself has unmet coverage.
- **Bug-class re-emergence rate.** When the same class of bug appears across consecutive review rounds, the underlying discipline has not yet been internalized. Tracks whether mutation-test discipline, corpus-fixture discipline, and source-unchanged-invariant discipline are actually being learned, or just being applied case-by-case.
- **Spec-vs-actual variance.** How often does what landed match what the canonical Implementation Plan said would land? Frequent drift suggests the plan is stale, the implementation is straying, or the orchestrator is over-engineering scope.
- **Mutation-test pass rate.** What fraction of regression-pin tests actually fail when their target line is reverted? Pins that don't fire are tautologies. A drop in this rate would indicate test-discipline regression.
- **Brief-to-canonical-doc divergence.** Count of references in any handoff brief that don't have matching canonical-doc citations. Tracks the over-engineering pattern — briefs growing detached from canonical scope.

### A possible parallel apparatus

If the metrics above were tracked formally, the apparatus shape might be:

- `metrics/development_process/<release_timestamp>/<event_type>.json` — parallel to `metrics/regression_replay/`. Per-release, per-event records (one per Council round, one per retrospective, one per fix-up commit chain).
- `bin/development_process_replay.py` — parallel to `bin/regression_replay.py`. Reads recorded events, computes metrics, emits a release-summary cell that validates against a `metrics/development_process/SCHEMA.md`.
- The calibration-cycle analog would be: when a dev-process metric regresses release-over-release, identify the dev-process lever to pull (changes to `DEVELOPMENT_PROCESS.md` itself; changes to Council protocol; changes to mutation-test discipline; etc.). The "lever" is a change to how the project is developed; the "recall delta" is the metric's improvement on subsequent releases.

### Open questions

These are real questions, not rhetorical:

- **Should the development process be SPC-able at all?** Some aspects are inherently human-judgment-dependent (whether a commit fixed the right thing; whether a Council finding is real or noise). Hard statistical-control assumptions may not apply across all dimensions. The QPB-the-skill apparatus works because the skill processes large numbers of artifacts (10+ benchmarks, multi-bug per benchmark). The development process processes fewer events per release; SPC needs sample sizes that may not exist.
- **Where's the line between useful measurement and meta-overhead?** SPC-ifying the development process risks adding bureaucracy that costs more than the insights are worth. The QC/QI loop for QPB-the-skill is justified by adopters' bug recall improving; the QC/QI loop for QPB-the-project would have to be justified by the development pace or quality improving in measurable ways. That justification is not yet in evidence.
- **What's the right granularity?** Per-release metrics give a sparse time series (a few releases per quarter). Per-Council-round metrics give a denser series but each round is shorter and less independent. Per-commit metrics give the densest series but most commits are too small to measure meaningfully.
- **Who validates the dev-process metrics?** For QPB-the-skill, recall is mechanically measured — it doesn't depend on operator judgment. For dev-process metrics like "is this Council finding real or noise?", the operator (Andrew) is necessarily in the loop. That makes the loop tighter (faster correction) but also more effortful (every measurement needs human review).
- **Does this duplicate retrospectives?** Versioned retrospectives in `docs/process/` already capture release-by-release lessons qualitatively. Whether quantitative dev-process metrics would add insight beyond what the retrospectives already capture is an open empirical question.

### Disposition

The natural trigger anticipated when this section was written — a release where retrospective lessons feel like they should be measurable but aren't — has fired. The v1.7.0 design (`docs/design/QPB_v1.7.0_Design.md` + `QPB_v1.7.0_Implementation_Plan.md`) scopes the SPC machinery for both the improvement loop and QPB-the-project's SDLC. The questions in this section remain useful as the design context that the v1.7.0 plan answers; treat this section as the historical framing rather than open work.

---

## 4. Cross-references

Docs that inform or are informed by the development process. This is not a navigation guide — for that, see `README.md` and `AGENTS.md`. These are the touchpoints specifically relevant when reasoning about *how QPB is developed*.

### Parallel methodology

- **`ai_context/IMPROVEMENT_LOOP.md`** — the QC/QI methodology for the running skill (QPB-applied-to-skills-and-code-projects). This document is the parallel for QPB-the-project (QPB-applied-to-its-own-development). They cover different objects (skill artifacts vs project process) but the same shape: rules paired with rationale, plus open directions for measurement maturity.

### Versioned artifacts

- **`docs/design/QPB_v<X.Y.Z>_Design.md`** — per-release design specifications. The "what we're building and why" for each release. Read by the orchestrator before authoring any planning content per the read-canonical-doc rule.
- **`docs/design/QPB_v<X.Y.Z>_Implementation_Plan.md`** — per-release work-item enumeration. The "what to build and in what order" for each release. Same read-first rule applies.
- **`docs/process/QPB_v<X.Y.Z>_*.md`** — per-release historical process artifacts (retrospectives, Council syntheses, Bootstrap Findings, Scope Audits). Immutable once written; serve as the audit input that a CMMI-level-3+ review would consume. Naming pattern parallels `docs/design/`.

### Workspace context

- **`~/Documents/AI-Driven Development/CLAUDE.md`** — workspace-level conventions (cross-project navigation, source-edit lanes, verify-before-claiming, Council protocol mechanics including Copilot CLI invocation — the new standalone `copilot` per v1.5.7 089f, or the deprecated `gh copilot` extension during the grace period, the universal Cowork communication style for any conversation in the workspace). When a working convention applies to QPB specifically, the canonical version lives in this `DEVELOPMENT_PROCESS.md` file; the workspace CLAUDE.md may replicate it for orientation but is not the source of truth.

### Peer orientation docs (in `ai_context/`)

- **`TOOLKIT.md`** — adopter-facing toolkit-installation and bare-invocation guide.
- **`TOOLKIT_TEST_PROTOCOL.md`** — release-gate review protocol for orientation docs (the orientation-doc analog of Council-of-Three).
- **`DEVELOPMENT_CONTEXT.md`** — context-gathering recipes and "baseline runs" guidance for development sessions. Operational counterpart to this `DEVELOPMENT_PROCESS.md` (which is the durable conventions doc; `DEVELOPMENT_CONTEXT.md` is the per-session-context doc). Opens with a "How to read this doc" selective-load guide; benchmarking methodology lives in `BENCHMARK_PROTOCOL.md` and release history in `VERSION_HISTORY.md`.
- **`VERSION_HISTORY.md`** — curated release-evolution narrative (v1.3.13 → present): what changed each release and why it mattered. The mechanical per-release changelog is `CHANGELOG.md` at the repo root.
- **`CALIBRATION_PROTOCOL.md`** — the 12-step Mode 1 (autonomous) / Mode 2 (operator-driven) protocol for driving a QPB calibration cycle on a benchmark target. Read when working on any lever-pull release.
- **`IMPROVEMENT_LOOP.md`** — methodology context for the calibration cycles: WHY the lever inventory exists and WHAT each lever controls.
- **`BENCHMARK_PROTOCOL.md`** — clean-folder run protocol for contamination-free benchmarks; v1.5.5+ also documents the `quality/run_state.jsonl` event format and cross-validation rules.

### Top-level orientation

- **`README.md`** — adopter-facing top-level orientation. The first thing any new reader sees.
- **`AGENTS.md`** — operator-facing guide, orchestrator-generated post-Phase 6 in benchmark target repos. NOT the same audience as this development-process doc; AGENTS.md tells an adopter how to operate the skill, this doc tells AI agents how the project itself is developed.
