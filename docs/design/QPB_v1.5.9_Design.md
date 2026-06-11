# Quality Playbook v1.5.9 — Design Document

*Status: drafted 2026-06-06 with broad scope, revised 2026-06-07 to scope down to two focus items per operator direction, **revised 2026-06-09 to replace the proposed external scheduler with in-session `ScheduleWakeup` polling** — same primitive the v1.5.7 watcher (`ai_context/WATCHER_PROMPT.md`) has used reliably for weeks. Two earlier drafts proposed external mechanisms (Cowork's `mcp__scheduled-tasks` MCP, then a self-spawned Python sidecar daemon firing `claude --print`) and both failed against deployment constraints: the MCP is unavailable in build-agent sub-sessions and Cowork-locked anyway, the daemon's fire mechanism hit the June 15 `claude -p` deprecation. The daemon-architecture branch is preserved as `archive/1.5.9-daemon-architecture`. See `QPB_v1.5.9_Harness_Skill_Design.md` for the empirical rationale.*

***Revised 2026-06-11 (operator decision): v1.5.9 is now entirely focused on the agent-based harness — implementation (Phase 1, complete as of this revision: 1A spike PASS, 1B.0 + 1B landed and Council-SHIP'd, item-11 E2E PASS) plus its STANDALONE DISTRIBUTION (Part 2 below: naming, extraction to its own repo, pip/npm packaging, Claude marketplace submissions for both plugins). The SKILL.md trim moved intact to `QPB_v1.5.10_Design.md`; the previously-in-scope ship-gate feature, B-1 through B-8 capabilities, and related design decisions (formerly numbered v1.5.10) move to `QPB_v1.5.11_Design.md`.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Where v1.5.9 sits in the arc

v1.5.9 is **the harness release** — two sequential workstreams:

1. **Harness-as-skill** — replace the Python subprocess harness (`bin/harness/`, `subprocess_runner.py`, the TUI) with a `quality-playbook-harness` skill that runs inside the operator's Claude Code session and dispatches workers via the `Task` tool. The harness's cadence is driven by `ScheduleWakeup` — the same in-session polling primitive the v1.5.7 watcher uses. Retires the substrate-immutability rule and the `claude -p` dependency without introducing a new external dependency (no MCP, no daemon, no cron). Detailed sub-design lives in `QPB_v1.5.9_Harness_Skill_Design.md` (authoritative for the harness work). **Status: COMPLETE as of 2026-06-11** — 1A spike PASS, 1B.0 + 1B landed with Council SHIP, item-11 multi-entry E2E validation PASS.

2. **Standalone distribution** — extract the harness's generic core into its own downloadable artifact (own repo, own pip + npm packages) and submit both it and the Quality Playbook to the official Claude plugin directory (`anthropics/claude-plugins-official`). Rationale: the harness architecture (deterministic disk-truth state machine + idempotent tick script + prose orchestrator + `ScheduleWakeup`, no external infrastructure) is novel against the 2026 orchestration landscape and is article material — and articles need something readers can download and run. See Part 2 below.

The SKILL.md trim that previously occupied workstream 2 moves intact to **v1.5.10** (`QPB_v1.5.10_Design.md`). Everything from the prior broad-scope draft — ship-gate feature, prompt-injection isolation, weak-assertion detection, bugspec emit, harness resume/iterate, combine-findings PR, adversarial review pass — moves to **v1.5.11** (`QPB_v1.5.11_Design.md`).

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

**Out of scope for v1.5.9 (deferred to v1.5.11 — renumbered from v1.5.10 on 2026-06-11 — or later):**

- A2A transport implementation (schemas are A2A-ready, transport stays filesystem)
- Cross-machine dispatch
- Web UI or TUI beyond what the host CLI's conversation provides + optional `qpb-monitor` read-only viewer

---

## Part 2 — Standalone distribution

**Goal.** Package the harness's generic core as a downloadable artifact people can try in one sitting — `pip install <name>` / `npm install -g <name>`, paste one bootstrap prompt, watch a multi-job pool run with staggered dispatch in ~20 minutes, no API spend beyond the session. Then submit both the standalone harness plugin and the Quality Playbook plugin to the official Claude plugin directory.

**Why this matters.** The operator's article pipeline needs downloadable artifacts ("it's much easier to write things up when there's something people can download" — operator, 2026-06-11). The thesis is distinctive against the 2026 orchestration landscape (frameworks like LangGraph put the intelligence in external infrastructure; dashboards like the kanban-over-worktrees tools require active supervision; Claude Code's experimental Agent Teams is in-session but in-memory-coordinated): **all the determinism lives in a ~600-line stdlib script, the agent only relays and sleeps, disk is the database, and crash-resume is "re-paste the prompt."** The item-11 E2E run is the existence proof — the tick script orchestrated three stub workers with zero QPB involvement, because `worker_prompt` is an opaque payload.

**What's already settled:**

- The generic/QPB boundary is real and clean: tick script, harness SKILL.md prose, BOOTSTRAP_PROMPT, schemas, STATE_MACHINE.md are payload-agnostic. The only genericization needed is the heartbeat helper: the standalone version makes `phase` a free string (no `phase_identity` / run-state coupling); QPB's `qpb_heartbeat.py` keeps its phase-identity integration.
- QPB's publish machinery (`bin/publish_pip.py`, `bin/publish_npm.py`, `build_channel_package.py`, the dry-run gates per `DEVELOPMENT_PROCESS.md` § Distribution-channel publish safety) is the template for the standalone's channels.
- Claude marketplace path confirmed (2026-06-11): `anthropics/claude-plugins-official` (launched 2026-05-22, pre-registered by default in Claude Code), third-party submission via the plugin directory submission form, automated screening on entry, optional stricter review for an "Anthropic Verified" badge. Both plugins (QPB + harness) already have the required plugin layout + marketplace.json shape.
- The standalone's demo plan is essentially `testing/e2e_stub_plan.json` (the item-11 apparatus), genericized.

**OPEN DECISIONS — discussion in progress (operator + orchestrator, 2026-06-11; continue before instructions are filed):**

1. **Name.** Operator wants a broader brainstorm. Current shortlist with registry recon: `tickwork` (npm free; clockwork-architecture story, professional CLI feel), `wakeloop` (npm free; names the novel primitive), `wakecrew` (unchecked; wakes-and-checks-its-crew), `callboard` (unchecked; theater job-board metaphor), `coxswain` (best role metaphor — calls the cadence, doesn't row — but hard to spell/say), `octoharness`/`octoloop` (Octobatch brand family; insider-y). Ruled out for collisions: `powernap` (npm taken), `cadence` (Uber), `metronome` (billing co.), `bosun` (Stack Exchange monitoring), `nightwatch` (JS testing), `stagehand` (Browserbase). The name carries the article thesis — decide deliberately, then verify npm + PyPI + GitHub before committing anything.
2. **Repo model.** Leaning model 1 of 3 — standalone repo is canonical for the generic core; QPB keeps its vendored copy under `plugins/` with a lineage note (and possibly a drift test against a pinned upstream release). Ruled-out-leaning: QPB-depends-on-package (breaks QPB's self-contained install closure) and publish-from-QPB-monorepo (the article's URL would point into a QPB subfolder; extraction later breaks links). NOT yet operator-confirmed.
3. **Versioning/sequencing of the standalone's first release** relative to the QPB v1.5.9 tag (standalone starts at its own v0.x; does the QPB tag wait for the standalone's first publish or only for the marketplace submissions?).

**Scope for v1.5.9 (modulo the open decisions):**

1. Name chosen + verified across npm / PyPI / GitHub.
2. New repo scaffolded: generic tick script, generic heartbeat helper, harness SKILL.md, BOOTSTRAP_PROMPT.md, schemas, STATE_MACHINE.md, example stub plan (the 20-minute demo), tests, README that sells the thesis in 30 seconds, Apache-2.0.
3. pip + npm packages with publish scripts modeled on QPB's (dry-run gates mandatory before any live publish).
4. QPB's vendored copy annotated with the lineage note (+ drift test if model 1 confirmed).
5. Claude marketplace submissions: the standalone harness plugin AND the Quality Playbook plugin, via the official submission form.
6. `bin/harness/` (the old Python harness) deleted — the item-11 PASS satisfied the deletion gate.

---

## Sequencing within v1.5.9

The two workstreams are sequential:

- **Harness-as-skill** (Part 1) — **complete.** The sub-design's MVP scope landed: SKILL.md + schemas + helper scripts + tests + end-to-end validation against a 3-entry plan with staggered dispatch (item-11 PASS, 2026-06-11).
- **Standalone distribution** (Part 2) — gated on the open decisions above (name, repo model), then: extraction → packaging → publish dry-runs → marketplace submissions → `bin/harness/` deletion.

Release tag follows the umbrella plan's Phase 3 after Part 2's ship gate. Council reviews: Part 1's are done (1B.0 + 1B self-Councils, both SHIP); Part 2 gets its own review on the extracted artifact before first publish.

---

## What v1.5.9 explicitly does NOT do

To make the scoping unambiguous:

- **No SKILL.md trim** — moved intact to `QPB_v1.5.10_Design.md` (2026-06-11 operator decision).
- **No ship-gate feature work** (Part 1 of the original broad draft) — `quality_gate.py` extension for invariants, cross-artifact consistency invariants, semantic Council audit prompt, bootstrap-as-regression-test framing. All in `QPB_v1.5.11_Design.md`.
- **No new capabilities B-1 through B-8** — prompt-injection isolation, phase-isolated security improvement loop, harness resume/iterate, bug-neighborhood iteration, adversarial fresh-context review, combine-findings PR, bugspec emit, weak-assertion detection (Marcono1234). All in `QPB_v1.5.11_Design.md`.
- **No methodology lesson docs as deliverables** — carry-forward lessons from the v1.5.7/v1.5.8 arc absorbed into `ai_context/DEVELOPMENT_PROCESS.md` directly when surfaced. They don't need a separate Design.md section.

---

## Open design questions (resolve during implementation)

### Harness-as-skill

Inherited from `QPB_v1.5.9_Harness_Skill_Design.md`'s Open Questions section — most are MVP-deferred or empirical:

- Polling cadence default (sub-design proposes 10 min)
- Stall threshold default (sub-design proposes 45 min global + 3-min mandatory keepalive)
- Cross-CLI auth pre-flight check shape
- Resume-from-disk schema versioning

### Standalone distribution

The three OPEN DECISIONS in Part 2 (name, repo model, first-release sequencing), plus, once those settle: how the QPB-vendored copy tracks upstream (drift test vs deliberate fork), and whether the standalone's first release carries an `--init`-style demo scaffolder or just the example plan.

---

## Risks

| Risk | Mitigation |
|---|---|
| Harness skill subagent context bloat over long runs | Each tick is fresh-context (tick-based architecture, per sub-design) — no long-lived in-context state. Empirically clean across the spike + item-11 E2E. |
| Standalone/QPB copies drift accidentally | Repo-model decision includes a lineage note + candidate drift test against a pinned upstream release |
| Name collides with an existing tool after launch | Verify npm + PyPI + GitHub before committing; collision shortlist already pruned (see Part 2) |
| Publish-channel bugs reach adopters | Reuse QPB's scripted publish gates verbatim (clean-clone cold-build, built-artifact end-to-end test, dry-run before live) per `DEVELOPMENT_PROCESS.md` |
| Marketplace review rejects a plugin | Submission is non-blocking for the tag (decision 3 under Open decisions); iterate on feedback post-release |

---

*End of v1.5.9 Design. Umbrella implementation plan (Phase 0 + standalone distribution + release) in `QPB_v1.5.9_Implementation_Plan.md`. Harness skill detailed design in `QPB_v1.5.9_Harness_Skill_Design.md`, with its companion plan `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md` (Phase 1). SKILL.md trim in `QPB_v1.5.10_Design.md`. Deferred broader scope in `QPB_v1.5.11_Design.md`.*
