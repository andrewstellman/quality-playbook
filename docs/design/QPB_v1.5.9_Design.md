# Quality Playbook v1.5.9 — Design Document

*Status: drafted 2026-06-06 with broad scope, revised 2026-06-07 to scope down to two focus items per operator direction, **revised 2026-06-09 to replace the proposed external scheduler with in-session `ScheduleWakeup` polling** — same primitive the v1.5.7 watcher (`ai_context/WATCHER_PROMPT.md`) has used reliably for weeks. Two earlier drafts proposed external mechanisms (Cowork's `mcp__scheduled-tasks` MCP, then a self-spawned Python sidecar daemon firing `claude --print`) and both failed against deployment constraints: the MCP is unavailable in build-agent sub-sessions and Cowork-locked anyway, the daemon's fire mechanism hit the June 15 `claude -p` deprecation. The daemon-architecture branch is preserved as `archive/1.5.9-daemon-architecture`. See `QPB_v1.5.9_Harness_Skill_Design.md` for the empirical rationale. The previously-in-scope ship-gate feature, B-1 through B-8 capabilities, and related design decisions move to `QPB_v1.5.10_Design.md`.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Where v1.5.9 sits in the arc

v1.5.9 is scoped to **two focused workstreams**, independent of each other and parallelizable:

1. **Harness-as-skill** — replace the Python subprocess harness (`bin/harness/`, `subprocess_runner.py`, the TUI) with a `quality-playbook-harness` skill that runs inside the operator's Claude Code session and dispatches workers via the `Task` tool. The harness's cadence is driven by `ScheduleWakeup` — the same in-session polling primitive the v1.5.7 watcher uses. Retires the substrate-immutability rule and the `claude -p` dependency without introducing a new external dependency (no MCP, no daemon, no cron). Detailed sub-design lives in `QPB_v1.5.9_Harness_Skill_Design.md` (this document references it as authoritative for the harness work).

2. **SKILL.md trim** — move content from the 1256-line source `SKILL.md` into `references/*.md` files that the skill loads on-demand per phase. Goal: source SKILL.md small enough (~200-400 lines) that the awesome-copilot submission can ship the **full canonical** SKILL.md without the redirect-to-install framing that the maintainers explicitly reject.

Everything else from the prior v1.5.9 broad-scope draft — ship-gate feature, prompt-injection isolation for ingested docs, weak-assertion detection from Marcono1234's feedback, bugspec-format Phase 7 emit, harness resume/iterate, combine-findings PR generation, adversarial fresh-context review pass — moves to **v1.5.10**. See `QPB_v1.5.10_Design.md` for that scope.

The two v1.5.9 workstreams are independent: SKILL.md trim affects what the skill ships and how it loads; harness-as-skill affects the test harness invocation substrate. They share neither files nor sequencing. Either could ship without the other.

---

## Part 1 — Harness-as-skill

**Status:** detailed sub-design exists at `QPB_v1.5.9_Harness_Skill_Design.md`, Council-reviewed, FIX-REQUIRED items folded in (tick-based execution via scheduled-tasks MCP, atomic claim two-phase commit, cross-CLI path passing via absolute paths in prompt body, write-temp-then-rename for whole-file writes, mandatory 3-min keepalive in heartbeat, etc.).

**Summary (canonical text in sub-design):**

- Two skills cooperate: `quality-playbook-harness` (new orchestration skill) + `quality-playbook` (existing worker skill, modified to emit a deterministic heartbeat contract).
- **Tick-based execution via in-session `ScheduleWakeup`.** The harness runs inside one operator Claude Code session (the operator pastes a bootstrap prompt; that session becomes the harness orchestrator for the plan's duration). Each tick is one agent turn: run the `qpb_harness_tick.py` Python script, parse its JSON output, dispatch any new `Task` subagents, print the status table, call `ScheduleWakeup(now + N minutes)`. State machine lives entirely on disk; the deterministic Python script is the state-machine engine; the agent's per-tick prose is small and fixed.
- **Folder-based communication** with A2A-ready schemas (schemas designed so future cross-machine A2A migration is a transport swap, not a redesign).
- **Dispatch is Mode 1 (`Task` subagent) only for MVP.** Cross-CLI dispatch (Mode 2 in earlier drafts) and operator-manual (Mode 3) are deferred to v1.6+ — they have unresolved questions about heartbeat observability and process lifecycle that v1.5.9 should not absorb.
- **Heartbeat contract** added to `quality-playbook` SKILL.md: emit via `bin/qpb_heartbeat.py` helper at phase boundaries, every ~3 min mid-phase mandatory keepalive, on any error, and terminal sentinel on completion.
- **MVP host: Claude Code only.** `ScheduleWakeup` is Claude Code's primitive. Other host CLIs become a v1.6+ question.

**What this retires:**

- `bin/harness/launcher.py`, `bin/harness/sentinel_reader.py`, the harness TUI, `subprocess_runner.py`, all the Windows compat fixes (180-190 chain), the substrate-immutability rule. Nothing in the new architecture invokes `claude -p` / `claude --print` — the orchestrator runs inside the operator's existing session, so the June 15 deprecation is moot.
- The earlier v1.5.9 draft's "Part 0" sentinel-and-paste-buffer design — substantially obviated by the harness skill model. What remains needed for Mode A (interactive QPB without harness) + one-shot worker invocations migrates to the harness sub-design's §0.6 Mode A path and is handled there.

**Out of scope for v1.5.9 (deferred to v1.5.10 or later):**

- A2A transport implementation (schemas are A2A-ready, transport stays filesystem)
- Cross-machine dispatch
- Web UI or TUI beyond what the host CLI's conversation provides + optional `qpb-monitor` read-only viewer

---

## Part 2 — SKILL.md trim

**Goal.** Reduce the source `SKILL.md` from 1256 lines / 132KB / ~33K tokens to ~200-400 lines / ~30-50KB / ~8-12K tokens. Phase-specific operational detail moves into `references/phase_<N>_<purpose>.md` files that the skill loads on-demand when entering each phase.

**Why this matters:**

1. **awesome-copilot submission.** The trimmed SKILL.md the awesome-copilot script generates is a different document from the source — explicitly a redirect to "install via pip/npm" rather than the actual skill. Maintainers reject this framing. If the source SKILL.md is small enough to ship verbatim, the trim becomes unnecessary and awesome-copilot gets the **canonical** functional skill.
2. **Per-invocation token cost.** SKILL.md is loaded into the agent's context on every invocation. 33K tokens × every QPB run × every adopter is significant cost. Lazy-loading phase content cuts the per-run baseline substantially.
3. **Maintenance.** A 1256-line SKILL.md is hard to navigate and edit. Phase-isolated reference files give clearer separation of concerns; editing Phase 3 prose doesn't touch Phase 1 content.

**Design — what stays vs what moves.**

Stays in source SKILL.md (the trimmed canonical version):

- Frontmatter (`name`, `description`, `license`, version, author, github)
- Phase Overview — the "plan overview" prose that describes what each phase does at a high level (~200-300 words)
- Phase entry contracts — what each phase reads and produces, in tabular form
- Invocation forms (Mode A / Mode B / harness)
- The reference file load instructions — "for Phase N detail, read `references/phase_N_guide.md`"
- Critical contract content that's not phase-specific (run_state.jsonl schema, install-location fallback list, version-stamp invariants)

Moves to `references/`:

- Phase 1 detailed exploration patterns + role-map querying detail → `references/phase1_detail.md` (consolidate with existing `phase1_exploration_guide.md`)
- Phase 2 generation step-by-step instructions → `references/phase2_detail.md` (consolidate with existing `phase2_generation_guide.md`)
- Phase 3-6 corresponding detail files
- Challenge-gate prose (already partially in `references/challenge_gate.md` — consolidate)
- Spec-audit Council protocol details (already in `references/spec_audit.md` — verify completeness)
- Run-state event taxonomy detail (most already in `references/run_state_schema.md` — verify completeness)

**Loading model.** The skill loads the trimmed SKILL.md at session start, then loads each `references/phase_N_*.md` file when the agent enters Phase N. The orchestrator agent reads the reference file via `Read` tool when crossing the phase boundary. This is the same on-demand model the existing references/ work uses — extending it to cover more of the per-phase content.

**Backward compatibility.** Adopters running QPB skills installed pre-v1.5.9 (whose SKILL.md still has the full 1256-line content) keep working. The trim is a source-side change; installed-skill semantics are identical for the previous installation.

**Validator updates.** `quality_gate.py` gains an invariant that scans SKILL.md's `Read references/X.md` references and confirms each resolves to an existing file. Without this, a stale reference quietly breaks a phase mid-run.

**Token-ceiling test (`bin/tests/test_skill_md_size.py`).** The current ceiling is 32K tokens (v1.5.7 instruction 090m). v1.5.9 ratchets it down to ~12K with the same rationale-doc-on-bump policy: future SKILL.md bloat is detected immediately.

---

## Sequencing within v1.5.9

The two workstreams are independent:

- **Harness-as-skill** lands when the sub-design's MVP scope completes: SKILL.md + schemas + helper script + end-to-end validation against a 2-3 repo plan with mixed dispatch (per `QPB_v1.5.9_Harness_Skill_Design.md` § MVP scope).
- **SKILL.md trim** lands when the trimmed SKILL.md passes the new validator + the token-ceiling test + a regression run against the standard benchmark set (3-5 repos) confirms no recall degradation.

Either can ship first. Both must ship before v1.5.9 tag. Council reviews are per-workstream (one for harness-skill ship, one for SKILL.md trim ship).

---

## What v1.5.9 explicitly does NOT do

To make the scoping unambiguous:

- **No ship-gate feature work** (Part 1 of prior draft) — `quality_gate.py` extension for invariants, cross-artifact consistency invariants, semantic Council audit prompt, bootstrap-as-regression-test framing. All in `QPB_v1.5.10_Design.md`.
- **No new capabilities B-1 through B-8** — prompt-injection isolation, phase-isolated security improvement loop, harness resume/iterate, bug-neighborhood iteration, adversarial fresh-context review, combine-findings PR, bugspec emit, weak-assertion detection (Marcono1234). All in `QPB_v1.5.10_Design.md`.
- **No methodology lesson docs as deliverables** — carry-forward lessons from the v1.5.7/v1.5.8 arc absorbed into `ai_context/DEVELOPMENT_PROCESS.md` directly when surfaced. They don't need a separate Design.md section.

---

## Open design questions (resolve during implementation)

### Harness-as-skill

Inherited from `QPB_v1.5.9_Harness_Skill_Design.md`'s Open Questions section — most are MVP-deferred or empirical:

- Polling cadence default (sub-design proposes 10 min)
- Stall threshold default (sub-design proposes 45 min global + 3-min mandatory keepalive)
- Cross-CLI auth pre-flight check shape
- Resume-from-disk schema versioning

### SKILL.md trim

- **Boundary criteria — what's "phase-specific" enough to move?** Some content is read in Phase 1 but referenced in Phase 4 (defensive patterns, exploration role-map). Single-phase content moves cleanly; cross-phase content needs design decisions on duplication vs cross-references.
- **Eager vs lazy reference loading.** Eager (load all phase references at session start) is simpler but defeats the point — we still pay the token cost. Lazy (load when entering phase) is the goal but requires the agent to actually invoke `Read` at phase boundaries, which the skill prose must enforce.
- **Adopter-install upgrade path.** If an adopter has v1.5.8 installed and we ship a smaller SKILL.md in v1.5.9, do we tell them to re-install via `quality-playbook install`? Or does the next QPB run detect old-SKILL.md and prompt for update?
- **Token-ceiling target.** 12K is a guess. The empirical question is "how small can we make SKILL.md while preserving recall on the standard benchmark set." Implementation pass needs to measure.

---

## Risks

| Risk | Mitigation |
|---|---|
| SKILL.md trim degrades recall on the benchmark set | Standard 3-5 repo benchmark run before ship; abort if recall drops materially |
| Harness skill subagent context bloat over long runs | Each tick is fresh-context (tick-based architecture, per sub-design) — no long-lived in-context state |
| Phase-specific reference files have implicit dependencies on each other | Validator scans for `references/X.md` mentions and resolves them; cycle detection added |
| Reference files duplicate content already in SKILL.md | Trim audit step: any content moved to references is REMOVED from SKILL.md; no copy-and-keep |
| Adopter-install migration breaks active QPB runs | Backward compat is intentional — v1.5.8-installed skill keeps working; upgrade is opt-in |

---

*End of v1.5.9 Design. Umbrella implementation plan (Phase 0 + SKILL.md trim + release) in `QPB_v1.5.9_Implementation_Plan.md`. Harness skill detailed design in `QPB_v1.5.9_Harness_Skill_Design.md`, with its companion plan `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md` (Phase 1). Deferred broader scope in `QPB_v1.5.10_Design.md`.*
