# QPB v1.6.x — Phase 6 Structural Enforcement (proposal)

*Status: candidate feature, proposed 2026-05-18. Not yet scoped to a specific v1.6.x release. Authoring driven by the v1.5.7 deeper-Council finding that A-13 hybrid Phase 6 enforcement is prose-only on agents without a sub-agent primitive (codex desktop empirically; cursor/aider/cline by inference).*

*Companion to:*
- *`QPB_v1.6.x_Requirements_Review_Proposal.md`* — the other open v1.6.x track item.
- *v1.5.7 instruction chronicle (`AI-Driven Development/Quality Playbook/32_v1.5.7_implementation_chronicle.md`)*, §4 (A-13 hybrid) and §10 findings A-27/A-28 — the codex-desktop pattern this proposal addresses.
- *The v1.5.7 deeper-Council synthesis (`Reviews/QPB_v1.5.7_Council_088_Deeper_Synthesis.md`)*, Residual 1 — the explicit defer of structural enforcement to v1.6.x.

---

## The problem

QPB's Phase 6 is the **fresh-context auditor phase**: an LLM that did not see Phases 1–5 reads the run artifacts (BUGS.md, REQUIREMENTS.md, the patches, the gate log) and renders an independent verdict. The fresh-context requirement is load-bearing — an agent that just produced Phases 1–5 has confirmation bias on its own work, and a same-context Phase 6 is structurally indistinguishable from self-review.

v1.5.7 instruction 071 introduced the **A-13 hybrid**: executor inline (Phases 1–5 in the orchestrating session), verification isolated (Phase 6 via a fresh sub-agent dispatch). For agents with a sub-agent primitive (Claude Code's Task tool; gh copilot's Mode B), this works — the sub-agent gets its own context window, reads only the artifacts, emits a verdict. Empirically verified on cobra (Claude Code opus) and gson (gh copilot Mode B).

For agents *without* a sub-agent primitive, the hybrid degrades. Codex desktop, observed 2026-05-18 on the v1.5.7 self-bootstrap, reads `phase_prompts/phase6.md` ("Phase 6 sub-agent delegation is NON-OPTIONAL; you may NOT proceed with in-session verification as a fallback; MUST ABORT if cannot delegate"), then **transparently** performs the verification in-session anyway: *"I am unable to dispatch a sub-agent in this environment, so I will perform the verification myself."*

The transparency is honest. The contract violation is real. v1.5.7 instructions 071 and 087 tightened the prose to the limit of what English can enforce, and the codex-desktop pattern persisted. The deeper-Council reviewers (opus, sonnet, haiku) unanimously classified this as **prose-only enforcement; structural detection requires v1.6.x work**.

### What's actually missing

A way for QPB to **mechanically detect that an agent claiming Phase 6 PASS actually ran the verification in a fresh context.** Currently the defense is:

1. Prose mandate (`phase_prompts/phase6.md`) — softenable by interpretation
2. Verdict-string pinning (`PreShipDocRegressionTests`) — pins the *prose* of the contract, not the *behavior*
3. Auditor verdict format requirement (specific witness format with run-nonce) — fabricatable by any agent willing to fabricate the structure

The honest threat model: **Layer 1 (named env-var detection in `run_playbook.py`) is the structural defense against undelegated execution; Phase 6 fresh-context is currently prose-defended only.** Adopters using Claude Code or gh copilot get the structural defense for free (their host CLIs cooperate). Adopters using codex desktop, cursor, aider, or cline get prose-defended Phase 6 — with explicit disclosure when the agent honestly degrades.

---

## What QPB already does (analogous fragments)

QPB has *fragments* of the structural enforcement pattern. The new feature pulls them together for Phase 6 specifically.

- **Run-nonce witness** (introduced in 077 for Phase 0) — `qpb_validate.py` emits `nonce=<uuid>` lines that cross-reference between the validator output and the gate log. An auditor verifying the run can check nonce consistency to confirm the gate output came from this run, not a paste from elsewhere.
- **Named-agent env-var detection** (introduced in 084/084b/085) — `_AGENT_CONTEXT_SIGNALS` + `_detect_agent_context_or_refuse()` in `run_playbook.py`. Structural; doesn't depend on prose compliance.
- **A-13 hybrid Phase 6 sub-agent** (introduced in 071) — works correctly on agents with sub-agent primitives; degrades on agents without.
- **Test-time witness contract** — `bin/tests/test_phase6_subagent_contract.py` pins the verbatim witness strings the auditor must emit.

What's missing: a mechanism that ties the Phase 6 verdict to *evidence the verification ran in a different context than Phases 1–5*. The witness contract pins what the auditor *says*; it doesn't pin *who said it*.

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

QPB defines a **fresh-context attestation contract** that host CLIs can opt into. Claude Code, gh copilot, codex desktop, cursor, aider, etc. would each implement an `attest-fresh-context` API that returns a signed/verifiable claim that the named sub-agent execution happened in an isolated context.

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
- README + AGENTS.md update: Phase 6 verifier options table (subprocess / witness-signing / prose-only legacy mode), with adopter setup steps for each
- `docs/PHASE6_VERIFIER.md` — operator-facing doc explaining what the subprocess Phase 6 does, why it requires API credentials, how to configure for different LLM providers (Anthropic, OpenAI, etc. if supported), how to opt out
- Migration note for v1.5.7 adopters: Phase 6 behavior changes; honest documentation of the change in CHANGELOG
- Tag-note removal in README/CHANGELOG: the v1.5.7-era "Known limitation — Phase 6 fresh-context contract is prose-enforced" entry is replaced with "Phase 6 fresh-context contract is structurally enforced via [Slice 1] / [Slice 2]"

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

- **v1.5.7** (this work): A-13 hybrid Phase 6 enforcement via sub-agent primitive. Works for Claude Code + gh copilot Mode B; degrades to prose-only for codex desktop / cursor / aider / cline. Documented as residual.
- **v1.6.x — Requirements Review** (separate proposal): operator-facing interactive REQ review post-playbook. Independent from Phase 6 enforcement; both can ship in v1.6.x track.
- **v1.6.x — Phase 6 Structural Enforcement** (this proposal): subprocess-based Phase 6 verifier + witness-signing fallback. Closes the v1.5.7 residual structurally.
- **v1.7+** — host-CLI attestation cooperation (Direction C). Multi-vendor; QPB publishes the contract; uptake depends on vendors. Replaces or supplements Slice 1/2 as adopted.

The two v1.6.x track items are **independent and can ship in any order**. Requirements Review and Phase 6 Structural Enforcement touch different parts of the codebase (post-playbook interactive UX vs. Phase 6 subprocess infrastructure) and don't share blockers.

---

## Acceptance criteria (when this is implemented)

A v1.6.x release that ships Slice 1 + Slice 2 of this proposal is successful if:

1. **Codex desktop running the v1.6.x skill produces a structurally-enforced Phase 6 verdict.** Re-running the 2026-05-18 self-bootstrap scenario: codex desktop launches Phase 6, the subprocess spawns, the verdict is rejected if codex tries to fabricate it without the subprocess having actually run. The "in-session Phase 6 with disclosure" pattern becomes structurally impossible rather than prose-discouraged.

2. **The v1.5.7 prose-only residual entry in README + CHANGELOG is removed.** Replaced with documentation of the structural enforcement and how to configure it.

3. **Existing A-13 hybrid behavior preserved for agents with sub-agent primitives.** Claude Code Task-tool dispatch continues to work; gh copilot Mode B continues to work. Slice 1 is additive, not replacing.

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
