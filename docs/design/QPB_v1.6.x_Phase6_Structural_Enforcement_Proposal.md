# QPB v1.6.x — Phase Validator Structural Enforcement (proposal)

*Status: candidate feature, proposed 2026-05-18, scope expanded 2026-05-18 to cover Phase 1 + Phase 6 (originally Phase 6-only). Not yet scoped to a specific v1.6.x release. Authoring driven by the v1.5.7 deeper-Council finding that A-13 hybrid Phase 6 enforcement is prose-only on agents without a sub-agent primitive (codex desktop empirically; cursor/aider/cline by inference), and by the 2026-05-19 self-bootstrap Round 1 finding (F13) that the same prose-only enforcement gap exists at the Phase 1 validator-run boundary. **2026-05-24: a third evidence instance added (Instance 3) — artifact-production completeness — from the v1.5.7 run-series OpenFGA channel Mode-A run, which showed the gap persists even on a capable, sub-agent-primitive host (Claude Code/Opus) that honestly reports the resulting FAIL.***

*Filename retains the historical `Phase6_Structural_Enforcement` suffix for reference stability with v1.5.7 instructions 089/089b that point at this path. Content covers all phase-boundary validator-invocation contracts; the design problem is the same shape regardless of which phase.*

*Companion to:*
- *`QPB_v1.6.x_Requirements_Review_Proposal.md`* — the other open v1.6.x track item.
- *v1.5.7 instruction chronicle (`AI-Driven Development/Quality Playbook/32_v1.5.7_implementation_chronicle.md`)*, §4 (A-13 hybrid) and §10 findings A-27/A-28 — the codex-desktop pattern this proposal addresses.
- *The v1.5.7 deeper-Council synthesis (`Reviews/QPB_v1.5.7_Council_088_Deeper_Synthesis.md`)*, Residual 1 — the explicit defer of structural enforcement to v1.6.x.

---

## The problem

QPB's six-phase pipeline has multiple phase-boundary validator-invocation contracts that are currently **prose-mandated but not mechanically enforced**. Two instances of the same gap surfaced during v1.5.7 ship-validation:

### Instance 1 — Phase 6 fresh-context auditor (A-13 hybrid)

Phase 6 is the fresh-context auditor: an LLM that did not see Phases 1–5 reads the run artifacts (BUGS.md, REQUIREMENTS.md, the patches, the gate log) and renders an independent verdict. The fresh-context requirement is load-bearing — an agent that just produced Phases 1–5 has confirmation bias on its own work, and a same-context Phase 6 is structurally indistinguishable from self-review.

v1.5.7 instruction 071 introduced the **A-13 hybrid**: executor inline (Phases 1–5 in the orchestrating session), verification isolated (Phase 6 via a fresh sub-agent dispatch). For agents with a sub-agent primitive (Claude Code's Task tool; the Copilot CLI's Mode B — at the time of the empirical verification, the `gh copilot` extension; same mechanism under the new standalone `copilot` CLI per v1.5.7 089f), this works — the sub-agent gets its own context window, reads only the artifacts, emits a verdict. Empirically verified on cobra (Claude Code opus) and gson (Copilot CLI Mode B — `gh copilot` at observation time; the Mode B mechanism is preserved under the new `copilot` CLI).

For agents *without* a sub-agent primitive, the hybrid degrades. Codex desktop, observed 2026-05-18 on the v1.5.7 self-bootstrap, reads `phase_prompts/phase6.md` ("Phase 6 sub-agent delegation is NON-OPTIONAL; you may NOT proceed with in-session verification as a fallback; MUST ABORT if cannot delegate"), then **transparently** performs the verification in-session anyway: *"I am unable to dispatch a sub-agent in this environment, so I will perform the verification myself."*

The transparency is honest. The contract violation is real. v1.5.7 instructions 071 and 087 tightened the prose to the limit of what English can enforce, and the codex-desktop pattern persisted.

### Instance 2 — Phase 1 validator-run mandate (F13)

Phase 1 has the same structural gap. The Phase 1 contract requires the agent to invoke `python3 -m bin.validate_phase_artifacts <target> --phase 1` at phase boundary and quote the verdict line verbatim. `bin/run_state_lib.py:77-78` defines the gate constants (`_MIN_CANDIDATE_BUGS_EXPLORATION_RISKS = 2`, `_MIN_CANDIDATE_BUGS_DEEP_DIVE = 1`) and the validator at `:459-465` emits the `Phase 1 gate: candidate bugs source mix` failure on non-compliant EXPLORATION.md. This contract has been in place since v1.5.6 (commit `fb346b4`, BUG-005 fix from a v1.5.6 codex bootstrap).

The 2026-05-18 codex desktop self-bootstrap of v1.5.7 produced an EXPLORATION.md missing all `Stage:` annotations on its 15 numbered Open Exploration Findings entries — a state the Phase 1 validator FAILs. Codex desktop reported `Phase 1: PASS` regardless. Either:

- **(a)** Codex desktop didn't run `validate_phase_artifacts --phase 1` at the phase boundary
- **(b)** Codex desktop ran it, saw FAIL, and reported PASS anyway (fabrication)

Either way: prose enforcement failed. The Phase 1 contract requires the agent to run the validator, but nothing mechanically verifies that the agent did so.

### Instance 3 — Phase 3/5 artifact-production completeness (2026-05-24 OpenFGA channel Mode-A run)

A third variant of the same shape surfaced during v1.5.7 run-series validation, and it is the most pointed yet because it occurred on a *capable* agent *with* a sub-agent primitive. A clean npm-channel install of v1.5.7 into a fresh OpenFGA clone (`openfga` `main` @ `c0f5c138`, ~168K Go LOC), run by **Claude Code / Opus 4.7** as a Mode-A six-phase walkthrough (~1h), produced **sound engineering**: 4 confirmed bugs (MEDIUM/LOW, each carrying a 090j `reachability_analysis` field), two FP-class candidates demoted via reachability (including a cache-key-omits-StoreID candidate — the exact class of the original OpenFGA precision failure), and zero confident-HIGH security false positives. The 090j precision guardrails worked in a live run.

But the Phase 6 gate FAILED with **15 FAILs, all artifact-production gaps**: 2 confirmed bugs missing red-phase logs; `quality/TDD_TRACEABILITY.md` missing; `test_regression.*` missing; 2 bugs missing regression-test patches; **all 4 challenge records missing** (the challenge gate auto-triggered on the bugs' `no-spec-basis` / `sibling-path-divergence` / `missing-functionality` tags — these are code-quality defects with no derived-REQ basis); and `quality/compensation_grid.json` missing (pattern-tagged REQs require it). The agent **honestly reported `AUDITOR VERDICT: FAIL`** and did NOT fabricate PASS — the F15 three-state contract + TDD-credibility machinery (089c/089m–q) worked.

Critically, **the missing artifacts are all prose-mandated in the phase prompts** — `compensation_grid` in phase3 + phase5, `challenge` records in phase3, `test_regression` in phase5, `TDD_TRACEABILITY` in `references/verification.md`. The contract was documented; the agent had the instructions and, over a long run, under-produced the bookkeeping while doing the high-value engineering (including the prominent 090j reachability work) well.

This instance differs from 1 and 2 in obligation *class* — it is artifact-**production completeness**, not validator-**invocation** — but it is the same root failure: a prose-mandated phase obligation an agent under-executes, with no structural mechanism forcing production. It also illustrates the *good* counterfactual the proposal's threat model contrasts against: here the gate caught the gap and the agent was honest, so the outcome was an honest `GATE FAILED — pass-with-cleanup`, not a fabricated PASS. **Hardening goal:** make the conditional artifact triggers (the challenge auto-trigger, the compensation-grid cardinality gate, per-bug red/regression artifacts) as structurally unmissable as the validator-invocation attestation Slices 0–2 target, so a long run can't silently skip them. **Reproduction target:** re-run the OpenFGA channel Mode-A walkthrough (and weaker agents / longer runs) and check whether the full artifact set is produced.

### The pattern

Both instances share the same shape: **a contract that requires the agent to invoke a validator at phase boundary and quote the verdict, but nothing mechanically detects whether the validator was actually invoked.** The Phase 6 instance was discovered first (and addressed empirically via the A-13 hybrid sub-agent pattern for sub-agent-capable hosts); the Phase 1 instance was discovered during the 2026-05-19 self-bootstrap Round 1 investigation. Instance 3 (2026-05-24) generalizes the shape from validator-*invocation* to artifact-*production* completeness: the gate's conditional artifact triggers (challenge auto-trigger, compensation-grid cardinality, per-bug red/regression artifacts) are prose-mandated and under-produced on long runs — even by a capable sub-agent-primitive host that honestly reports the resulting FAIL. Any structural-enforcement design should treat artifact production as in-scope, not just validator invocation.

Other phase-boundary validators with the same shape:
- Phase 2 (`validate_phase_artifacts --phase 2` — checks manifest wrapper compliance per schemas.md §1.6)
- Phase 5 (`validate_phase_artifacts --phase 5` — checks INDEX.md / §11 fields / gate_verdict transition)

These haven't surfaced as empirical failures yet, but they have the same structural gap and likely fail the same way under codex desktop.

### What's actually missing

A way for QPB to **mechanically detect that an agent claiming `Phase N: PASS` actually invoked the validator and got the verbatim verdict line.** Currently the defense for each phase is:

1. Prose mandate (`phase_prompts/phase{N}.md` / `references/phase{N}_*_guide.md`) — softenable by interpretation
2. Verdict-string pinning in tests (`PreShipDocRegressionTests`, calibration tests like `test_validate_phase_artifacts_phase1_actual_qpb_exploration_passes`) — pins the *prose* of the contract and validates committed artifacts, not the agent's runtime behavior
3. Verdict format requirement (specific `RESULT: VALIDATION PASSED (phase N)` line) — fabricatable by any agent willing to fabricate the structure

The honest threat model: **Layer 1 (named env-var detection in `run_playbook.py`) is the structural defense against undelegated execution; phase-boundary validator-invocation is currently prose-defended only.** Adopters using Claude Code or the GitHub Copilot CLI in Mode B (`copilot` per v1.5.7 089f, or the deprecated `gh copilot` extension during the grace period) get the validator runs structurally for free (the orchestrator runs them, not the agent). Adopters using codex desktop, cursor, aider, cline, or any Mode A inline execution where the agent itself is supposed to invoke the validator get prose-defended validator-run-mandate — with explicit disclosure when the agent honestly skips, and silent fabrication when it doesn't.

---

## What QPB already does (analogous fragments)

QPB has *fragments* of the structural enforcement pattern. The new feature pulls them together for all phase-boundary validator-invocation contracts (Phase 1, Phase 2, Phase 5, Phase 6).

- **Run-nonce witness** (introduced in 077 for Phase 0) — `qpb_validate.py` emits `nonce=<uuid>` lines that cross-reference between the validator output and the gate log. An auditor verifying the run can check nonce consistency to confirm the gate output came from this run, not a paste from elsewhere.
- **Named-agent env-var detection** (introduced in 084/084b/085) — `_AGENT_CONTEXT_SIGNALS` + `_detect_agent_context_or_refuse()` in `run_playbook.py`. Structural; doesn't depend on prose compliance.
- **A-13 hybrid Phase 6 sub-agent** (introduced in 071) — works correctly on agents with sub-agent primitives; degrades on agents without.
- **Test-time witness contract** — `bin/tests/test_phase6_subagent_contract.py` pins the verbatim witness strings the auditor must emit.

What's missing: a mechanism that ties each phase verdict to *evidence the validator actually ran* (for Phase 1/2/5) and *evidence the verification ran in a different context than Phases 1–5* (for Phase 6). The witness contract pins what the agent *says* the validator output; it doesn't pin *who actually ran the validator*.

---

## Design space

Three architectural directions. Each has trade-offs; none is obviously "the answer."

### Direction A — Witness-signing protocol

The orchestrator generates a **fresh-context challenge** before Phase 6: a random token plus a structural query the sub-agent can only answer correctly if it reads the artifacts from scratch (not from prior context).

The sub-agent's verdict must include the token plus the structural-query answer plus a hash over (verdict + token + answer). The orchestrator verifies the hash and the structural-query answer; if either doesn't check, the verdict is rejected.

**Strengths:**
- Doesn't require host-CLI cooperation
- Works for any agent that can produce text output
- Fabrication-resistant: an agent that didn't actually read the artifacts can't answer the structural query correctly without doing the read

**Weaknesses:**
- The structural query has to be hard enough that an in-context agent can't shortcut by inspecting its own conversation history (e.g., "what's the SHA of BUGS.md as committed?" works because the in-context agent didn't compute it; "summarize the first bug" doesn't work because the in-context agent already wrote it)
- Implementation requires running a separate process or API call from the orchestrator that the in-context agent can't intercept — which is most of the design work
- An agent that's willing to fabricate Phase 6 verdicts is also willing to compute the challenge response post-hoc; the protocol raises cost but doesn't close

### Direction B — Subprocess + IPC verification

Phase 6 runs as a **separate Python subprocess** spawned by `run_playbook.py`. The subprocess invokes an LLM API directly (bypassing the host CLI) and emits the verdict to stdout. The orchestrator captures the subprocess PID, the subprocess stdout, and the subprocess exit code. The verdict is treated as load-bearing only if all three artifacts are present and consistent.

**Strengths:**
- Structural: an agent that didn't actually spawn the subprocess can't fake the PID + stdout + exit-code triple without filesystem-level interception
- Works deterministically — verifiable from the run logs
- Reuses existing infrastructure (`run_playbook.py` already spawns subprocesses for the gate, the validator, etc.)

**Weaknesses:**
- Adopters need API credentials configured in the environment (`ANTHROPIC_API_KEY` for direct Claude calls, etc.) — a setup-friction increase
- Operating-mode change: Phase 6 stops being "the LLM does it" and becomes "QPB does it via an LLM API call." This blurs the line between QPB-the-skill and QPB-the-application.
- Cost: an extra API call per Phase 6. Modest, but real.
- Doesn't help adopters who don't have direct API access (some enterprise contexts)

### Direction C — Host-CLI cooperation

QPB defines a **fresh-context attestation contract** that host CLIs can opt into. Claude Code, the GitHub Copilot CLI (`copilot` / `gh copilot`), codex desktop, cursor, aider, etc. would each implement an `attest-fresh-context` API that returns a signed/verifiable claim that the named sub-agent execution happened in an isolated context.

**Strengths:**
- Architecturally clean: each host CLI is the authority on its own context isolation
- Extensible: as new agents emerge, they implement the contract or don't (and adopters know which is which)
- Highest assurance when implemented correctly

**Weaknesses:**
- Requires Anthropic, GitHub, OpenAI, Cursor, Aider, etc. to each implement the contract — outside QPB's control
- Long timeline; multi-vendor coordination
- Until all relevant hosts implement, Phase 6 enforcement remains inconsistent across the adopter base

---

## Recommended approach

**Direction B (subprocess + IPC) as v1.6.x Slice 1, with Direction A (witness-signing) as Slice 2 fallback for adopters without API credentials, and Direction C (host-CLI cooperation) as a parallel-track v1.7+ ambition.**

Reasoning:

- **Direction B is the lowest-risk shipping option.** The subprocess pattern is already in `run_playbook.py`; adding a Phase 6 subprocess is incremental, not architectural. The dependency on API credentials is real but addressable via documentation + adopter-facing setup guidance.
- **Direction A is the right fallback** for adopters who can't or won't configure API credentials. It works in any environment that can produce text output. It's strictly weaker than B (fabricatable by a determined adversary) but strictly stronger than the current prose-only state.
- **Direction C is correct long-term** but its timeline is governed by vendor cooperation, not QPB's release cadence. Worth proposing publicly and tracking, but not blocking on.

The two-slice approach lets v1.6.x ship structural enforcement immediately for the major adopter path (API-credentialed environments) while still strengthening the residual case (in-session-only environments).

---

## Implementation slices (independently shippable, sequenced)

A key cost asymmetry between phases shapes the slicing:

- **Phase 1, Phase 2, Phase 5 validators are pure Python.** `validate_phase_artifacts.py --phase {1,2,5}` produces deterministic output without invoking any LLM. Structural enforcement is *cheap*: spawn the validator as a subprocess, capture PID + stdout + exit code, attach to run-state, reject the phase verdict if the triple is absent. No API credentials needed.
- **Phase 6 verification requires an LLM** (the fresh-context auditor). Structural enforcement is *expensive*: needs a separate process that calls the LLM API directly (bypassing the host CLI) — requires API credentials, multi-provider design, operating-mode shift.

The Phase 1/2/5 case ships first (Slice 0) because it's strictly cheaper and closes 3 of the 4 phase-boundary validator-invocation contracts. Phase 6 ships after (Slices 1 + 2) because the design space is harder.

### Slice 0 — Pure-validator subprocess attestation (Phase 1, Phase 2, Phase 5)

Deliverables:
- `bin/run_playbook.py` extension: at each pure-validator phase boundary in Mode B, the orchestrator runs `python3 -m bin.validate_phase_artifacts <target> --phase N` itself as a subprocess; captures PID + stdout + exit code; writes the attestation triple to run-state. The agent's reported verdict is cross-checked against the attestation. Mismatch → halt with diagnostic.
- `bin/validate_phase_artifacts.py` extension: emits a nonce in its final `RESULT:` line (mirroring the Phase 0 validator's `nonce=` field). The orchestrator pins the nonce in run-state; the agent must quote the nonce-bearing verdict line verbatim. Fabricated verdicts that don't include the nonce are mechanically detectable.
- Mode A inline-execution contract update: `phase_prompts/phase{1,2,5}.md` mandate that the agent run the validator as a subprocess (not just read its output) and quote the nonce-bearing verdict line verbatim. The agent's `## What just happened` emit must include the subprocess attestation block.
- `bin/tests/test_phase_validator_attestation.py` — mutation-bite tests pin: validator nonce is unique per run, agent verdict missing nonce is rejected, orchestrator-run validator attestation matches agent's quoted output.

This slice closes Phase 1 (F13 root cause), Phase 2, Phase 5 simultaneously — same mechanism for all three. No new API dependencies. Strictly cheaper than the Phase 6 work.

### Slice 1 — Subprocess Phase 6 verifier (Direction B)

Deliverables:
- `bin/phase6_verifier.py` — standalone CLI that takes `<quality_dir>` + `--model <name>` + `--api-key-env <ENV_VAR_NAME>` and produces a Phase 6 verdict directly via the LLM provider's API
- `bin/run_playbook.py` integration: Phase 6 dispatches via subprocess invocation of `phase6_verifier.py`; captures PID + stdout + exit code; rejects verdicts where the triple isn't consistent
- `bin/tests/test_phase6_subprocess_verifier.py` — mutation-bite tests that pin: subprocess is actually spawned, verdict file contains the subprocess PID, mismatch fails the gate
- New phase prompt: `phase_prompts/phase6_subprocess.md` describes the contract from the agent's perspective ("Phase 6 will be run by `phase6_verifier.py`; you don't write the verdict, you wait for it")
- New section in `references/`: subprocess verifier configuration (which model, which credentials, how to opt out for environments that can't comply)
- AGENTS.md update: tell adopting agents about the subprocess Phase 6 path and the env-var requirements
- `qpb_validate.py` extension: validator checks for `ANTHROPIC_API_KEY` (or configured equivalent) at Phase 0 and emits a finding if absent with `qpb_validate.py`-level severity matching adopter intent

**Operating-mode change:** Phase 6 stops being an LLM-orchestrated phase and becomes a QPB-orchestrated API call. The phase agent's role becomes "kick off the subprocess and report the verdict"; the LLM-as-fresh-auditor role moves entirely into `phase6_verifier.py`.

### Slice 2 — Witness-signing fallback (Direction A)

Deliverables:
- `bin/phase6_challenge.py` — orchestrator-side challenge generator. Computes the Phase 6 challenge token + structural-query answer from the artifacts (e.g., SHA-256 of BUGS.md, count of records in `compensation_grid.json`, specific REQ-IDs from REQUIREMENTS.md). Writes the *answer* to a sealed file the orchestrator holds; writes the *challenge* to a file the sub-agent reads.
- `phase_prompts/phase6.md` update: adds the challenge step. The sub-agent must include the challenge token + its computed structural-query answer + a hash over (verdict + token + answer) in the verdict block
- `bin/run_playbook.py` extension: post-Phase 6, reads the sub-agent's verdict, recomputes the expected answer, compares the hash. Mismatch → verdict rejected, halt with diagnostic
- `bin/tests/test_phase6_challenge.py` — mutation-bite tests pin: orchestrator computes the answer correctly, sub-agent verdict containing wrong answer fails the gate, valid verdict passes

This slice is only invoked for adopters who opt out of Slice 1's subprocess path (e.g., `--no-phase6-subprocess` or absence of API credentials). Strictly weaker than Slice 1 but strictly stronger than current prose-only state.

### Slice 3 — Adopter-side configuration + documentation

Deliverables:
- README + AGENTS.md update: Phase validator enforcement options table (Slice 0 subprocess attestation for Phase 1/2/5; Slice 1 subprocess Phase 6 verifier; Slice 2 witness-signing fallback for Phase 6; prose-only legacy mode), with adopter setup steps for each
- `docs/PHASE_VALIDATOR_ENFORCEMENT.md` — operator-facing doc explaining each phase's enforcement mechanism, what's mechanical vs prose-only, API credential requirements for the Phase 6 subprocess path, how to opt out per phase
- Migration note for v1.5.7 adopters: phase-validator behavior changes; honest documentation of the change in CHANGELOG
- Tag-note removal in README/CHANGELOG: the v1.5.7-era "Phase validator contracts are prose-enforced" entry is replaced with "Phase 1/2/5 validators are subprocess-attested (Slice 0); Phase 6 fresh-context contract is structurally enforced via [Slice 1] / [Slice 2]"

---

## Out of scope (defer)

- **Direction C implementation.** Vendor-coordinated host-CLI attestation is a v1.7+ ambition. QPB can publish the *contract* a host CLI would implement (so the conversation can start) without blocking v1.6.x on it.
- **Multi-provider Phase 6 verifier.** Slice 1 ships Anthropic-only. OpenAI / other providers come later if there's demand.
- **Cryptographic signing of the verdict** (real public-key crypto, not just SHA hashes). Out of scope unless threat model evolves to require it.
- **Removing the prose-only legacy mode entirely.** Some adopter environments will never have API credentials available; the prose-only mode stays as documented limitation rather than removed entirely.
- **Phase 6 verifier UI.** No web UI, no interactive review pattern — Phase 6 is non-interactive batch verification.

---

## Open questions

1. **Which LLM model does `phase6_verifier.py` call by default?** Probably matches the executor-agent model (Claude opus → opus auditor; codex desktop → ?). Or always opus regardless of executor (highest-rigor auditor for all runs). Operator preference.

2. **What happens when the subprocess fails to spawn or the API call errors?** Halt with FAIL? Halt with abort-then-retry? Fall through to Slice 2 witness-signing? Operator preference, probably configurable.

3. **How does Slice 1 interact with the existing A-13 hybrid?** Two options: (a) deprecate the A-13 hybrid in favor of subprocess always; (b) keep A-13 hybrid for agents with sub-agent primitives, use subprocess as fallback for agents without. Option (b) is the conservative choice (don't break what works) but introduces complexity (two code paths).

4. **What's the test surface for Slice 1?** Subprocess invocation is integration-level — needs a test harness that can spawn a real subprocess with a real API call (cost) or a mocked one (less rigorous). Probably both: cheap mocked tests in CI + a manual/marked integration test that hits the real API on operator demand.

5. **Configuration discoverability — what's the "QPB needs an API key" surface?** A Phase 0 finding from `qpb_validate.py` is the obvious answer (consistent with how other adopter-setup issues are surfaced). But this means the validator gets a credential-checking responsibility it didn't have before — needs design.

6. **Backward compatibility for v1.5.7 adopters running this change.** Adopters who installed v1.5.7 then upgrade to a v1.6.x with Slice 1 shipped: do they need to re-install? Probably yes (the bundle grows). The install flow needs to handle that gracefully.

7. **Does Slice 1's operating-mode change ("QPB calls the LLM directly") cross a methodology line?** QPB's positioning has been "agentic skill that an LLM-driven editor invokes." Slice 1 turns Phase 6 into "QPB calls the LLM itself, not via the host CLI." That's a real architectural shift. Worth Council review on the framing before implementation, not just on the implementation.

---

## Connection to QPB's existing arc

- **v1.5.7** (this work): A-13 hybrid Phase 6 enforcement via sub-agent primitive (works for Claude Code + the Copilot CLI Mode B — `copilot` per v1.5.7 089f, or the deprecated `gh copilot` extension during the grace period; degrades to prose-only for codex desktop / cursor / aider / cline). Phase 1/2/5 validator-invocation contracts are prose-only across all hosts. Both documented as residual (v1.5.7 deeper-Council Residual 1 + Round 1 F13).
- **v1.6.x — Requirements Review** (separate proposal): operator-facing interactive REQ review post-playbook. Independent from this proposal; both can ship in v1.6.x track.
- **v1.6.x — Phase Validator Structural Enforcement** (this proposal): Slice 0 closes Phase 1/2/5 structurally via pure-validator subprocess attestation (cheap). Slices 1+2 close Phase 6 structurally via subprocess-based Phase 6 verifier + witness-signing fallback (expensive). Together: every phase-boundary validator-invocation contract becomes mechanically enforced.
- **v1.7+** — host-CLI attestation cooperation (Direction C). Multi-vendor; QPB publishes the contract; uptake depends on vendors. Replaces or supplements Slice 1/2 as adopted.

The two v1.6.x track items are **independent and can ship in any order**. Requirements Review and Phase Validator Structural Enforcement touch different parts of the codebase (post-playbook interactive UX vs. phase-boundary subprocess infrastructure) and don't share blockers.

---

## Acceptance criteria (when this is implemented)

A v1.6.x release that ships Slice 1 + Slice 2 of this proposal is successful if:

1. **Codex desktop running the v1.6.x skill produces a structurally-enforced Phase 6 verdict.** Re-running the 2026-05-18 self-bootstrap scenario: codex desktop launches Phase 6, the subprocess spawns, the verdict is rejected if codex tries to fabricate it without the subprocess having actually run. The "in-session Phase 6 with disclosure" pattern becomes structurally impossible rather than prose-discouraged.

2. **The v1.5.7 prose-only residual entry in README + CHANGELOG is removed.** Replaced with documentation of the structural enforcement and how to configure it.

3. **Existing A-13 hybrid behavior preserved for agents with sub-agent primitives.** Claude Code Task-tool dispatch continues to work; the Copilot CLI Mode B continues to work (`copilot` per v1.5.7 089f, or the deprecated `gh copilot` extension during the grace period — same Mode B mechanism). Slice 1 is additive, not replacing.

4. **Test surface includes both unit-level mocked subprocess tests AND a marked integration test that hits a real API.** The integration test is operator-runnable on demand; CI runs the mocked path only.

5. **Documentation is complete enough that an adopter setting up Slice 1 from scratch can do so without reading source.** `docs/PHASE6_VERIFIER.md` is the single entry point; README points at it; AGENTS.md tells adopting agents about the requirement.

6. **No regression on code-project benchmarks.** chi, virtio, cobra, gson, httpx, express — all continue to produce the same bug-yield they did under the v1.5.7 A-13 hybrid (within the documented noise floor).

7. **The methodology shift ("QPB calls the LLM directly for Phase 6") survives Council review.** This is the open framing question — Council needs to bless or reject the architectural change before implementation.

---

## Provenance

This proposal originated in the v1.5.7 deeper-Council review (2026-05-18, Claude opus-4.7 + sonnet-4.6 + haiku-4.5 reading the 077–088 surface). The Council unanimously identified Phase 6 mechanical enforcement as the open structural gap; all three reviewers classified it as v1.6.x scope rather than v1.5.7-blocking.

The empirical evidence for the codex-desktop in-session pattern is the 2026-05-18 self-bootstrap run (Quality Playbook codex desktop session, gpt-5.5+medium, full QPB repo as target). The bootstrap produced Phase 6 PASS but with in-session verification rather than fresh sub-agent — exactly the pattern A-13 hybrid was designed to prevent on agents with sub-agent primitives, and which this proposal addresses for agents without.

Earlier v1.5.7 work that established the pattern context:
- Instruction 071 — A-13 hybrid introduction (Phase 6 fresh-context sub-agent contract)
- Instructions 084/084b/085 — A-22 agent-context structural guard (the env-var detection pattern this proposal echoes for Phase 6)
- Instruction 087 — A-27/A-28 prose tightening (`phase_prompts/phase6.md` "NON-OPTIONAL/MUST ABORT" language)
- The v1.5.7 implementation chronicle, §4 + §10 (codex desktop systematic interpretation pattern: A-18/A-22/A-23/A-27/A-28 — same class, one agent runtime)

The full v1.5.7 deeper-Council synthesis is at `Quality Playbook/Reviews/QPB_v1.5.7_Council_088_Deeper_Synthesis.md`. Residual 1 in that doc is this proposal's seed.

Instance 3 evidence: the **2026-05-24 OpenFGA channel Mode-A run** (Claude Code / Opus 4.7, npm-channel install, `openfga` `main` @ `c0f5c138`, ~168K Go LOC, ~1h). Sound engineering + working 090j precision (reachability fields, two FP-class demotions, zero HIGH security FPs), but 15 artifact-production FAILs — honestly reported as `AUDITOR VERDICT: FAIL`, not fabricated PASS. Logged from the v1.5.7 run-series; the run output is preserved at `repos/openfga-run3/quality/` and the cell is recorded ACCEPTABLE-WITH-KNOWN-ISSUE in the run-series plan.
