# Quality Playbook v1.5.9 — Design Document

*Status: Initialized 2026-06-06 from Cowork session. Promoted from `~/Documents/AI-Driven Development/Quality Playbook/Reviews/v1.5.9_backlog.md` Section 0 + sections A-F. Implementation begins after v1.5.8 ships completely (`v1.5.8` tag on origin, `main` merged, pip + npm published).*

*Authored: 2026-06-06 (Cowork session, after gson PR #3035 / #3036 cascade and post-mortem)*

*Owner: Andrew Stellman*

*Depends on: v1.5.8 shipped (tag `v1.5.8` on origin); v1.5.7 substrate (psutil migration, Windows compat suite, Mode A include_iterations, kill cancels PENDING, harness log-read encoding fallback, run_playbook subprocess stdin utf-8); workspace `CLAUDE.md` rules current.*

*Note on file authorship: this Design doc was created by Cowork Claude under explicit operator instruction overriding the default "QPB source files are propose-don't-edit" rule. The carve-out was operator-approved during the 2026-06-06 session ending v1.5.8-era work; subsequent edits to this file should follow the normal QPB-source-edit lane (diagnosis + Claude Code worker) per workspace `CLAUDE.md`.*

---

## Where v1.5.9 sits in the arc

v1.5.9 has **one forcing function** and **multiple opportunistic items**.

The forcing function is Anthropic's announced 2026-06-15 deprecation of `claude -p` (non-interactive print/stream-json mode) on the subscription tier the QPB harness, runner, and worker invocations all depend on. Without a substrate replacement, the harness stops working on June 15 and the runner's `claude` provider lane breaks with it. Section 0 below specifies the replacement: paste-buffer launch + file-based sentinels + heartbeat liveness.

The opportunistic items are v1.5.8 deferrals and emergent lessons from the v1.5.7/v1.5.8 work cycle:

- **B-8 — weak-assertion detection** (new this release, originated from Marcono1234's 2026-06-05 review of gson PR #3035): catch tests that pass for the wrong reasons before they ship to upstream maintainers.
- **A — skill ship-gate feature**: the 16-category audit framework that emerged from the v1.5.8 codex pre-publish audit (#227).
- **B-1 through B-7**: capabilities deferred from v1.5.8 — prompt-injection isolation, phase-isolated security improvement loop, harness run resumption, bug-neighborhood iteration, adversarial code review pass, sibling-PR combining, bugspec-format Phase 7 emission.
- **C — design decisions** that need resolution before A/B work begins.

Scope discipline: v1.5.9 **must ship** Section 0 (the substrate replacement). Everything else is candidate scope, prioritized by readiness and bounded by what fits without delaying Section 0's June 15 deadline.

After v1.5.9 ships, v1.6.0 is planned as the QC→QI inflection (per v1.5.4 design doc framing — using the measurement infrastructure for continuous lever-pull improvement). Whether v1.5.10 happens depends on what's left over from v1.5.9; v1.5.x may end at v1.5.9 with v1.6.0 next.

---

## Part 0 — `claude -p` deprecation workaround (FIRST PRIORITY)

*Origin: Anthropic deprecation announcement, effective 2026-06-15. Designed in Cowork session 2026-06-06.*

### 0.1 Problem statement

After 2026-06-15, `claude -p` is no longer available on the QPB subscription tier. Without a replacement, three things break:

1. **QPB harness pool of `claude -p` subprocesses** — `bin/harness/run_playbook.py`, `bin/harness/manager.py`, `bin/harness/scheduler.py`, and the collector parsing of stream-json output.
2. **QPB runner's claude provider lane** — the CLI invocation in `run_playbook.py` for direct `claude` runs (Mode A and Mode B both).
3. **Worker invocations** — the `claude --max-turns N -p "$(cat instruction.md)"` pattern used to fire worker instructions (in this session: 197 through 201; this pattern will continue post-v1.5.9 unless replaced).

**Unaffected:**

- bugspec (uses `gh`, `git`, `mvn` subprocesses; no `claude` calls in its workflow).
- Octobatch (uses Anthropic API directly, not the CLI).
- QPB provider lanes for `copilot` and `codex` — separate CLIs with their own (independent) deprecation timelines. Out of scope for v1.5.9.

### 0.2 Design — paste-buffer launch + file-based sentinels

The substrate replacement keeps QPB inside Andrew's Claude subscription (no API spend) by replacing `claude -p` calls with `claude` (the interactive Claude Code TUI), launched manually by a human in a new terminal window, and monitored via files the agent writes from inside the run.

**Launch sequence (per run):**

1. Harness prepares the run directory at the canonical path (`harness_runs/<ts>/run-NN/`).
2. Harness creates an empty `sentinels.ndjson` file in the run directory — this empty file is the marker that signals "you are running under the harness; emit sentinels."
3. Harness writes the prompt to the OS paste buffer via the `pyperclip` library (which abstracts `pbcopy` on Mac, `clip` on Windows, `xclip`/`xsel` on Linux).
4. Harness displays a banner in the TUI showing the operator: "Open a new terminal window. Paste and run this command: `cd <run-dir> && claude --model <model> --dangerously-skip-permissions`".
5. Operator copies the banner command, opens a new terminal, pastes the command, hits Enter. Claude Code TUI launches in the run directory.
6. Operator pastes (Cmd+V / Ctrl+V) the prompt that's already on the system clipboard, hits Enter. The agent starts the run.
7. Harness monitors `sentinels.ndjson` for the agent's emitted events.

The human step is bounded: one paste + Enter at launch, then the run is unattended unless something goes wrong.

### 0.3 Sentinel file contract

**Path:** `./sentinels.ndjson` in the run directory. Resolved relative to the agent's cwd, which is set by step 5 of the launch sequence.

**Format:** Append-only NDJSON. One JSON object per line. Each line is a complete event with at minimum:

```json
{"ts": "2026-06-06T12:34:56Z", "event": "<event_type>", "...": "<event-specific fields>"}
```

**Required event types:**

| Event | When emitted | Required fields beyond `ts` + `event` |
|---|---|---|
| `run_started` | First action after agent reads prompt | `model`, `prompt_fingerprint` (sha256 of the prompt), `cwd` |
| `phase_started` | At each phase boundary the playbook defines | `phase_name` |
| `phase_completed` | At end of each phase | `phase_name`, `outcome` (`OK`/`FAIL`/`SKIPPED`), optional `notes` |
| `tool_call` | Every tool invocation (Read, Grep, Bash, Edit, Write, Glob, Task) | `tool_name`, `arg_summary` (≤ 120 chars; not full content) |
| `error` | Any caught exception or runtime error the agent observes | `error_type`, `message` (one line) |
| `run_completed` | Terminal success state | `outcome_summary` |
| `run_failed` | Terminal failure state | `failure_reason` (one line) |

**Write discipline:**

- One complete JSON object per `Write` tool call.
- Each call appends a single line ending in `\n`.
- The harness tolerates a trailing partial line if the agent crashes mid-write — parse-or-discard.
- Schema validation in `bin/sentinels.py` (new module) — runtime check at emit time so malformed events fail loud rather than silently corrupt the file.

### 0.4 Heartbeat as liveness signal

Without stream-json's token-by-token output, the harness cannot detect a stalled run from subprocess state alone (and the subprocess isn't its child anymore). The `tool_call` event doubles as a heartbeat: during normal operation the agent makes tool calls frequently (typically every few seconds during active phases), so `sentinels.ndjson` mtime advances continuously.

**Harness liveness rule:**

- File mtime advances within the heartbeat window (default 5 minutes — tunable per plan) → run is ALIVE.
- File mtime stalls beyond the window → mark as STALLED, surface in TUI with a "go check this window" prompt to the operator.
- Operator can kill the terminal window manually → harness detects via either (a) explicit `qpb kill <run-id>` subcommand from the operator, or (b) mtime stall AND no `run_completed`/`run_failed` written within a grace period → mark as ABANDONED_USER.

**Tuning:** The 5-minute default is provisional. Long tool calls (large `Bash` commands running mvn test suites, large `Read` of full files) can exceed several minutes. Implementation phase should empirically measure mtime gaps during real runs and adjust the default accordingly. The window is tunable per plan via a `heartbeat_window_seconds` field in the plan JSON.

### 0.5 Mode A vs Mode B — conditional sentinel emission in SKILL.md

Sentinel emission is overhead the harness consumes. Mode A users (interactive Claude Code without the harness) shouldn't pay for it cognitively or in token budget.

**Convention:** The agent emits sentinels **if and only if** `./sentinels.ndjson` exists in cwd when the agent starts. The harness creates the empty file before launch; Mode A users never have it.

**SKILL.md sentinel section (sketch — final wording during implementation):**

> ### Sentinel emission under the QPB harness
>
> At the start of every run, check whether `./sentinels.ndjson` exists in your current working directory. Use a `Bash` call: `test -f ./sentinels.ndjson && echo "harness" || echo "interactive"`.
>
> **If it exists** (harness mode), you must emit sentinel events to `./sentinels.ndjson` at the moments specified in §X. Each emission is a single `Write` tool call that appends one JSON line. Events: `run_started` (immediately after this check), `phase_started` and `phase_completed` at each phase boundary, `tool_call` before every tool invocation, `error` for caught errors, and `run_completed` or `run_failed` at terminal state.
>
> **If it does not exist** (interactive mode), you are running outside the harness. Skip sentinel emission entirely. Proceed with the rest of the playbook.

The conditional keeps the contract one place (SKILL.md) and lets Mode A stay clean of overhead.

### 0.6 Trade-offs accepted

Per Andrew's explicit confirmation in the 2026-06-06 design conversation:

- **Pool concurrency limited.** No way to spawn parallel claude-code windows from automation. User launches one window per run. Pool size is bounded by what the user is willing to manage. For benchmark sweeps the user can launch 3-4 windows at the start and let them run; for true `pool=10` benchmark scales, this substrate is not viable.
- **Overnight unattended runs broken.** Cannot launch new runs at 3am without a human at the keyboard. Acceptable per Andrew — benchmark runs in v1.5.7/v1.5.8 were already actively monitored.
- **stdout reasoning chain lost.** stream-json carried the agent's reasoning tokens, useful for diagnostics in the `claude-stream-render` view (instruction 173). File-based sentinels carry only structured events. To recover any diagnostic detail, agents may **optionally** write to `./trace.log` alongside `./sentinels.ndjson` — not required by contract, but agents can be instructed to do so for runs where debug detail matters.
- **Hard agent failures (OOM, model error, network drop) may write nothing before terminal close.** If Claude Code crashes hard, the last sentinel might be minutes old. Harness detects via mtime stall; the operator signals failure via the existing kill subcommand path (E keybinding from instruction 186).

### 0.7 Risk register

| Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|
| `pyperclip` fails on some Linux desktop env (no clipboard daemon) | Medium | Low | Fall back to "the prompt is at `<run-dir>/prompt.txt`, copy it manually" |
| Agent forgets to emit sentinels under long context | Medium | High | SKILL.md reinforcement + QPB-on-QPB bootstrap regression catches this (see §A-4 bootstrap-as-regression-test) |
| Heartbeat window too short → false STALLED alerts | High first week | Medium | Window is tunable; start at 5 min and adjust based on real-run mtimes |
| Heartbeat window too long → real stalls go undetected | Low | Medium | Floor at 5 min minimum; operator can override the surface "go check this window" prompt |
| Claude Code TUI behavior changes during v1.5.9 implementation | Unknown | High | Design must remain swappable; SKILL.md and `bin/harness/sentinel_reader.py` are the only Claude-Code-TUI-aware components |
| `claude --dangerously-skip-permissions` semantics change | Unknown | Critical | Direct dependency on Anthropic's flag — if this changes, design needs revision. Monitor Anthropic announcements. |
| Subscription concurrency limit bites at 3-4 parallel windows | Unknown | Medium | Test during implementation; reduce pool defaults if it does |

### 0.8 Open design questions (resolve during implementation phase)

1. **Heartbeat window default value.** 5 min for first cut. Real-world tool calls (mvn test, large file reads) may need 10-15 min. Tune empirically once running.
2. **Sentinel payload minimums.** What fields are mandatory vs. optional per event type? `ts` + `event` are universal; per-event required fields listed in §0.3 are the floor. Full spec during implementation.
3. **Banner UX.** The launch banner must be unambiguous about "open a new window and paste THIS command" vs "paste the prompt." Test wording with at least one fresh user (someone who hasn't seen QPB before) to catch ambiguities. Consider color or boxing for visual separation.
4. **Multi-run launch ergonomics.** If pool size is 3, the harness shows 3 banners. Does the user open 3 windows sequentially, or all at once? Does the TUI sequence the banners or display all three? UX work during implementation.
5. **Anti-gravity provider lane (future).** When Anthropic ships anti-gravity (or whatever the successor agent product is named), does it follow `claude -p` semantics (automation-friendly) or Claude Code TUI semantics (paste-buffer)? If the former, anti-gravity re-opens the automation path; the paste-buffer flow becomes a fallback. If the latter, it slots into the same paste-buffer lane.
6. **Subscription concurrency limits.** Unknown whether running 3-4 concurrent Claude Code windows hits per-user limits on Andrew's tier. Test during implementation; adjust pool defaults.
7. **`copilot` and `codex` lane futures.** Out of scope for v1.5.9 substrate change but worth noting: if either CLI gets a similar deprecation, the same paste-buffer + file-sentinel pattern likely applies. Design Section 0 to be CLI-agnostic where reasonable.

### 0.9 Connection to the deferred unified library

A unified Python library across Octobatch / QPB harness / QPB runner / bugspec was discussed in the same Cowork session. Andrew explicitly **deferred** the library work pending v1.5.9 substrate change shipping. The library question gets clearer after Section 0 lands — the paste-buffer-launched, file-sentinel-monitored lifecycle becomes one Provider flavor among several (API providers, `claude -p`-style providers, paste-buffer providers, future flavors). Library design picks up post-v1.5.9.

Cross-reference: when library work resumes, Section 0's substrate becomes the prototype for the library's "human-launched provider" abstraction.

---

## Part 1 — Skill ship-gate feature (candidate scope)

*Origin: codex pre-publish audit of 1.5.8 (2026-06-04) caught 7 real bugs Cowork's own pre-publish scan missed (#227). The bugs cluster into 16 categories — half are mechanical/regex-able, half need model judgment. The deeper framing: QPB-on-QPB (bootstrap run) should catch every one of these. If it doesn't, the skill reviewer is the broken thing.*

This is the largest non-Section-0 work. Andrew should decide pre-implementation whether it lands fully in v1.5.9 or spans v1.5.9 + v1.5.10. The four sub-parts and the architectural choice are below.

### 1.1 Mechanical invariants (`quality_gate.py` extension)

Cheap, no model needed, regression-safe. Add as new Layer-1 invariants in `schemas.md` §10 numbered #19+. Each gets a `quality_gate.py` check:

- **Version drift sweep.** Every version-bearing site must agree: `pyproject.toml::version`, `package.json::version`, `quality_playbook_cli/__init__.py:__version__`, SKILL.md frontmatter `version`, sidecar JSON `skill_version` examples, recheck template, CHANGELOG entry header, README "Version:" line. The 1.5.8 release missed `__init__.py:64` despite a "version-bump checklist" comment in SKILL.md — the checklist needs to BE a test.
- **Package completeness.** Every file path SKILL.md or `references/**/*.md` cites must resolve in the installed bundle. The 1.5.8 release shipped 171 dangling `schemas.md` references (FINDING-50 in 191) because no test caught the gap.
- **Dead-reference resolver.** Every URL / file path / module name cited in shipped prose must resolve. Same shape as package completeness but covers URLs and module imports too.
- **Runtime-token-bloat regex.** Date-shape regex (`\b202[0-9]-\d{2}-\d{2}\b`), instruction-code regex (`\b\d{3}[a-z]\b` for `089u`-style, `F-\d+`, `A-\d+`, `D\d+`), past-version regex (`v1\.[0-9]\.[0-9]+` when the file isn't a CHANGELOG). Hits don't auto-fail — they get flagged for review. The current trim-pass discipline becomes mechanical.
- **Supply-chain hygiene.** Bundle must NOT contain `__pycache__/`, `*.pyc`, `.env`, `quality/` (the playbook's own outputs), `previous_runs/`, `harness_runs/`, `metrics/`, `.git/`, `node_modules/`. Each is an explicit fail-pattern.
- **Marketplace metadata presence.** `pyproject.toml` must have `name`, `version`, `description`, `license`, `authors`, `keywords`, `classifiers`, `[project.urls]`, `requires-python`. `package.json` must have `name`, `version`, `description`, `license`, `author`, `keywords`, `repository`, `bugs`, `engines`. Missing field = fail.
- **Command-safety forbidden-pattern grep.** `rm -rf` without explicit scope; bare `--force`; `curl ... | bash` without explanation paragraph above; `git clean -fdx`; `git reset --hard` without "this discards work" caution. Flagged for review, not auto-fail.
- **Portability grep.** Unix-only commands without Windows alternative documented (`grep` without `findstr`, `which` without `where`, forward-slash-only paths, `python` vs `python3` ambiguity), `bash`-isms in published shell snippets.

### 1.2 Cross-artifact consistency invariants

Multi-file reads, still gate-able:

- **Install-path consistency.** SKILL.md's 10-layout fallback list (~lines 218-229 currently) must match what `bin/qpb_validate.py` actually probes. If a new install layout is added to one, it must be in the other.
- **Artifact contract drift.** SKILL.md's "Complete Artifact Contract" table (~lines 269-295 currently) must match what `quality_gate.py` actually requires. If the gate requires a file the table doesn't list, or the table lists a file the gate doesn't check, fail.
- **Phase prompt ↔ SKILL.md consistency.** Each phase prompt's "what this phase produces" claim must match the artifact-contract table for that phase. Catches drift where a phase prompt is updated but the table isn't (or vice versa).

### 1.3 Semantic Council audit prompt

New Phase 4 sub-pass. One prompt per reviewer, structured per-category verdicts. Same shape as Layer-2 semantic citation check. Categories the Council scores:

- **Ambiguous authority.** Multiple "single source of truth," "mandatory first action," "canonical," "non-negotiable" claims that conflict. (Codex flagged this in 1.5.8.)
- **Mode boundary bugs.** Mode A vs Mode B contradictions, interactive vs runner contradictions, phase-specific vs full-run contradictions, recheck vs normal run contradictions. (Codex falsely flagged Phase-1-only vs full-run in 1.5.8 — Council needs to be sharper than this false positive.)
- **Phase 0 / Phase 7 dual-meaning hazards.** Was a real bug in 1.5.8 (FINDING-52, FINDING-53 in 191). The Council prompt should look for term reuse across distinct concepts.
- **Public tone / embarrassing language.** Internal failure anecdotes that aren't load-bearing, adversarial internal phrasing, named-repo postmortems. Council flags; operator decides. NOT a copy-editor (the forceful framing is intentional and load-bearing).
- **Network/CLI assumptions.** References to `claude`, `copilot`, `codex`, `cursor`, model names, or shell access that may not exist for adopters without a documented fallback or detection path. **v1.5.9 update:** this Council category should specifically check for any lingering references to `claude -p` post-Section-0 substrate change.
- **Prompt-injection exposure.** Skill instructions that tell agents to ingest arbitrary docs/issues/Slack without isolating untrusted instructions from project facts. (See B-1 — this category becomes a check ONCE the underlying capability lands.)

### 1.4 Bootstrap-as-regression-test framing

The bootstrap run (QPB-on-QPB) becomes the regression test for whether the skill reviewer catches the audit findings. Every 1.5.8 finding (FINDING-48 through FINDING-54 in instruction 191) becomes a "would QPB have caught this?" test case.

Implementation: a new sub-suite `bin/tests/test_skill_reviewer_regression.py` reads each historical FINDING-NN, replays a synthetic version of the bug into a fixture SKILL.md / bundle, runs the gate or the Council prompt, and asserts the bug surfaces. If a future skill-reviewer change silently regresses the catch, this suite goes red.

### 1.5 Architectural choice — pick before implementing 1.1-1.3

| Option | Shape | Trade-off |
|---|---|---|
| **A. Fifth pass on existing pipeline** | Add "ship hygiene" as a fifth pass alongside the four skill-derivation passes | Bolt-on; reuses existing infrastructure; risks the ship-hygiene pass being treated as optional |
| **B. Separate ship gate** | New `quality_ship_gate.py` that runs alongside `quality_gate.py` when the target is a publishable skill | Cleanly separable; "is it shippable?" is a different question than "is it correct?" |
| **C. Layered (Cowork-recommended)** | Mechanical + cross-artifact checks become new invariants in `quality_gate.py`. Semantic checks become a new Council audit prompt at Phase 4. | Matches existing architecture (Layer-1 invariants + Layer-2 Council citation check are exactly this shape). Each check goes where its cost/leverage fits. |

**Cowork recommendation:** Option C. Operator decides during implementation.

---

## Part 2 — New capabilities

These are not "more checks" — they're new features. Each is independently scoped and independently shippable. v1.5.9 should pick a subset that fits beside Section 0 + Part 1; remainder defers to v1.5.10 or v1.6.0.

### 2.1 B-1: Prompt-injection isolation for ingested `reference_docs/`

*Origin: v1.5.8 reference_docs/ contamination findings — bug-tipping terms in adopter docs could become bugspec-quality input for adversaries.*

The skill currently has no isolation between "this is your project's documentation" and "this is an instruction we found in untrusted text." A motivated attacker could embed instructions in a reference doc that the agent then follows. v1.5.9 (or later) should add an isolation layer that frames ingested text as data, not instructions.

Specific mechanism is open design — likely either (a) wrap all `reference_docs/` content in `<untrusted>` tags before injecting into prompts, or (b) require explicit operator approval before any reference_doc content reaches an agent that has tool access.

This is foundational for v1.6.x security work. Probably defers to v1.5.10 or v1.6.0 unless prioritized in v1.5.9.

### 2.2 B-2: Phase-isolated improvement loop for security-bug targeting

*Origin: v1.5.7 blind CVE benchmark work surfaced that QPB's improvement loop tightly couples skill-derivation passes. Security-bug targeting needs a different optimization function — false-positive rate matters more than recall.*

The improvement loop in v1.5.7/v1.5.8 optimizes for a unified "find bugs that maintainers accept." For security work, false-positives are vastly more costly (filing 100 false security PRs = banned account). The phase-isolated improvement loop should let the security-bug targeting phase run a separate optimization that prioritizes precision.

Design brief required. Likely smaller than Part 1 but still non-trivial.

### 2.3 B-3: Harness — resume an aborted/blocked run, or iterate on a completed run

*Origin: operator pain in v1.5.7/v1.5.8 — aborted runs (network drop, model timeout) lose all state and must restart from Phase 0. Completed runs that find no bugs can't be re-prompted with "look harder at file X" without manual replay.*

Two capabilities, related but distinct:

- **Resume**: aborted run can pick up from the last completed phase. Requires state-on-disk discipline (already partially there via `quality/`).
- **Iterate**: completed run can be re-prompted with operator-supplied "look harder at X" context, reusing existing exploration as a starting point.

Strong candidate for v1.5.9 — the substrate change in Section 0 already changes how runs launch, so resumption semantics could land in the same release.

### 2.4 B-4: Bug-neighborhood iteration strategy

*Origin: Andrew's 2026-06-05 cross-PR observation — when one bug is found (e.g., `MapTypeAdapterFactory` dup-key write-side), nearby bugs in adjacent code paths or related abstractions are often present (e.g., dup-key read-side at the same line range). Currently the playbook treats each finding as isolated.*

After Phase 6 confirms a bug, optionally launch a follow-up exploration pass on the immediate code neighborhood (file siblings, callers, callees) looking for "more like this." Each adjacent finding goes through the normal verification pipeline.

Composability: B-4 deepens coverage around findings; B-5 broadens coverage to bugs the main pipeline missed. They work together.

### 2.5 B-5: Adversarial code review pass (independent fresh-context strategy)

*Origin: Andrew, 2026-06-05, after a side-by-side comparison of QPB's 4 gson findings against an adversarial-prompt review (Claude Code with ChatGPT/Gemini-collaborated prompt) that produced 3 different findings — 2 net-new (JsonPrimitive equals/hashCode contract violation + non-transitivity) and 1 complementary to QPB's Map dup-key write-side finding (the read-side cross-API inconsistency).*

The empirical evidence: QPB and adversarial review find DIFFERENT bug classes:

- **QPB catches** method-vs-method contract divergence based on derived REQs. The 4 gson bugs were all in number-handling — divergence between writer/reader/parser surfaces of the same documented behavior.
- **Adversarial review catches** Java object-contract violations (equals/hashCode) and test-gap-masks-bug patterns (existing tests only check value=0 where the two hash branches coincidentally agree). QPB's REQ-derivation methodology doesn't naturally surface these because the contracts aren't called out in the project's own Javadocs.

Neither approach is strictly better. They're complementary. Combining both = better coverage than either alone.

**Proposed mechanism:** add `--strategy adversarial-review` as a Phase 4 sub-pass (or as a new Phase 7-style optional pass after Phase 6). Architecture follows Andrew's design constraints:

1. **Fresh-context subagent.** Spawned via the worker's Task tool. Does NOT see EXPLORATION.md, REQUIREMENTS.md, BUGS.md, or any prior phase output beyond a minimal project-context summary.
2. **Explicit instruction to ignore `quality/`.** The subagent is told to find bugs INDEPENDENTLY of what the main pipeline already found. Anchoring is the failure mode this avoids.
3. **Static template + Phase 1 injected context.** The adversarial prompt has 6 universal focus areas (Public API contract violations, API-layer inconsistencies, Type system / dispatch / resolution bugs, Security/robustness/DoS, Backward compatibility, Test gaps that hide defects) plus the finding format and review standards. Phase 1 injects project-specific variables.

**Phase 1 outputs the subagent needs** (becomes part of Phase 1's exploration deliverables):

- `{public_api_classes}` — list of N most important user-facing classes/modules
- `{core_pipeline_summary}` — 2-3 sentence description of how data flows through the system
- `{dispatch_mechanism}` — how the library decides which code to run (e.g., "TypeAdapter resolution" / "HTTP router" / "middleware chain")
- `{external_specs}` — relevant RFCs/specs the project follows (RFC 8259 for JSON libraries, RFC 7230 for HTTP, etc.)
- `{language_runtime_variants}` — Java versions / Node versions / Python versions / .NET versions
- `{api_path_inventory}` — list of parallel API surfaces to check for consistency (e.g., for gson: "fromJson vs toJson vs JsonReader vs JsonParser vs TypeAdapter")

**Output integration.** The subagent writes findings to `quality/adversarial_findings.md` in the same `## FINDING-N` format. Phase 4 (Spec Audit) optionally promotes adversarial findings into the main BUGS.md tracker with `source: adversarial_review`. They then go through Phase 5 TDD verification like any other confirmed bug.

**Empirical validation already exists.** The 2026-06-05 gson side-by-side run was the proof-of-concept. The adversarial pass took ~12 minutes (vs QPB's ~45 minutes) and found 3 findings (2 net-new + 1 complementary). A v1.5.9 implementation would reproduce that result automatically as part of the QPB pipeline rather than requiring a manual separate run.

**Open questions:**

1. **When does the adversarial pass run?** As a Phase 4 sub-pass (parallel with Spec Audit) gets it integrated. As Phase 7 (optional, post-Phase-6) keeps it isolated.
2. **Should the adversarial reviewer see the project's documentation?** Yes for project-internal docs (Javadocs, README, user guide), no for QPB's `quality/` outputs.
3. **Default-on or opt-in?** Probably default-on for benchmark runs, opt-in for adopter Mode A runs (doubles pipeline runtime).

### 2.6 B-6: Combine related findings into a single coherent PR

*Origin: Andrew, 2026-06-05, after observing that QPB BUG-002 (Map serialization emits duplicate keys — write-side) and the adversarial-review FINDING-3 (Map read paths handle duplicates inconsistently — read-side) are two sides of the same underlying gson Map-dup-key abstraction. Filing them as separate PRs splits a coherent fix into fragments; filing them together gives the maintainer one logical change with a complete story.*

After Phase 6 confirms multiple bugs that are clearly related (same file region, same abstraction, same root cause), an optional Phase 7-or-later step composes a single PR with all the related fixes. The PR description names each finding as a sub-section so reviewers can accept/reject piecemeal.

Smaller scope than B-5. Probably 1-2 weeks of work. Strong candidate for v1.5.9.

### 2.7 B-7: QPB Phase 7 emits bugspec-format YAML for each TDD-verified bug

*Origin: cross-project integration with bugspec (the upstream-PR-filing tool built in this session). Phase 6 produces a TDD-verified red→green pair. Bugspec consumes a YAML spec describing the bug + patches. v1.5.9 closes the loop.*

After Phase 6 confirms a bug, Phase 7 emits a bugspec-compatible YAML spec at `quality/bugspec/<bug-id>.yaml` (or equivalent path). The operator can then `bugspec process examples/.../specs/<bug-id>.yaml` to file the upstream PR with zero additional authoring.

The YAML format is specified by bugspec v0.3.0+; QPB needs only to generate-and-emit. Probably small implementation: a Jinja-style template + a writer in `bin/phase7.py`.

Cross-references:

- Bugspec design: `~/Documents/QPB/repos/bugspec/design/bugspec_Design.md` (v0.2.0 + v0.3.0 sections current; v0.3.1, v0.3.2 polishing)
- Bugspec spec format: see `examples/gson_bugs/specs/001-BUG-001.yaml` for a worked example
- Bugspec's own v0.3.3 candidate: patch validation at spec-load time (would have caught today's off-by-one hunk-header errors); cross-cuts QPB v1.5.9 work

Strong v1.5.9 candidate — small effort, large operator-value payoff.

### 2.8 B-8: Weak-assertion / "passes for the wrong reasons" detection on QPB-generated tests

*Origin: Marcono1234 review comment on google/gson PR #3035 (BUG-001), 2026-06-05: "with this null check the assertion below would also succeed if one implementation returns null and the other throws an exception. That would probably not be desired." The QPB-generated BUG-001 regression test wrapped both writer calls in try-catch + boolean and asserted `treeOk == stringOk`. The assertion is strictly weaker than the test method's name implies — it would silently pass in degenerate cases (both throw, both null, one null + one throws). Marcono1234 proposed dropping the try-catch and using two direct `assertThat(...).isNotNull()` calls. He was right.*

The class of bug: **tests that pass for the wrong reasons.** QPB's TDD verification (Phase 5) confirms the test goes red on clean HEAD and green after the fix. That's necessary but not sufficient — a test can satisfy red→green AND still admit silent passes in regression scenarios that don't match the test's stated intent.

#### Three complementary detection layers

**Layer 1 — Static pattern detection (cheap, mechanical).** A `bin/test_quality_gate.py` (or a Layer-1 invariant on test files specifically) that runs over generated regression tests and flags known weak-assertion patterns:

- **try-catch wrapping non-exception-testing assertions.** `try { ... boolean x = (result != null); } catch (E e) { x = false; }` followed by `assertThat(x).isEqualTo(y)` — defensive boolean comparison. Marcono1234's exact catch.
- **Boolean comparison of swallowed exception outcomes.** Any assertion comparing two booleans where each came from a try-catch where the catch sets the boolean false. Strictly weaker than direct assertions.
- **Empty or pass-through catch blocks.** `catch (Exception ignored) {}` or `catch (E e) { /* expected */ }` without a corresponding assertion that the exception WAS expected.
- **Self-referential assertions.** `assertEquals(method(x), method(x))` — passes trivially.
- **No-op assertions.** `assertNotNull(new Object())`, `assertTrue(true)`, `assertFalse(false)`.
- **Boolean-style asserts where direct asserts exist.** `assertEquals(false, x)` instead of `assertFalse(x)`. Style.
- **Test method name ↔ assertion intent mismatch.** Heuristic: if the test name contains `accepts` or `succeeds`, the assertion should be a direct `isNotNull`/`isInstanceOf`/`isEqualTo(expected)` — NOT a boolean comparison of two try-catch outcomes. If the test name contains `throws` or `rejects`, the assertion should use `assertThrows`. Fuzzy but the high-confidence cases (name says `accepts`, body has try-catch + boolean comparison) are flaggable.

Language-aware variants needed for: Java (JUnit/Truth, the gson case), pytest (Python), Jest (JS), Go test, cargo test. Each gets its own pattern set; common patterns share infrastructure.

**Layer 2 — Adversarial test critique (subtle cases, model judgment).** A Phase 5.5 sub-pass (or augmentation to Phase 5's existing TDD verification): an isolated subagent reads ONLY the generated test + the PR body/writeup, and answers:

> "This test allegedly demonstrates the bug described. Could this test pass for ANY reason OTHER than the stated bug being absent? Construct degenerate scenarios where the test passes but the bug is still present. If you find any, the test is too weak."

Output is either APPROVED or weak-with-suggestions. The subagent doesn't see the fix code, the original repo source, or QPB's other phases — it only sees the test + the claimed intent. If it can construct a "test passes despite bug still being present" scenario, the test needs tightening.

This is exactly the form of Marcono1234's review applied to ALL generated tests, automatically, before the patch leaves QPB. Cost: one subagent per generated test, probably ~$0.02 in Haiku tokens.

**Layer 3 — Counterfactual mutation (expensive, deep).** After TDD verification (Phase 5):

1. Verify "red on clean HEAD" — already done ✓
2. Verify "green after fix" — already done ✓
3. NEW: Apply a "no-op fix" (e.g., add a comment to the target file) and verify test STILL FAILS. Catches tests that don't actually depend on the fix.
4. NEW: Apply a "wrong fix" (revert a different part of the target file) and verify test FAILS. Catches tests that pass due to incidental code paths.
5. NEW: Apply the fix BUT remove the test's actual assertion (replace with `assertTrue(true)`) and verify test PASSES. Sanity-check that the test infrastructure is wired correctly.

Step 3 is the load-bearing addition. If a "no-op fix" makes the test pass, the test wasn't actually catching the bug — it was catching something else.

#### Where this lands in the QPB pipeline

| Layer | Phase | Cost | Trigger |
|---|---|---|---|
| 1 (static patterns) | Phase 5 post-TDD-verify | seconds | Always |
| 2 (adversarial critique) | Phase 5.5 sub-pass | ~10s + tokens | Always |
| 3 (counterfactual mutation) | Phase 6 (pre-bugspec-emit) | minutes | Optional — full bench runs only? |

Layer 1 + Layer 2 should be DEFAULT-ON. Layer 3 is expensive enough to defer to opt-in flag or benchmark-mode-only.

#### Connection to bugspec v0.3.3+

Independently, bugspec's TOOLKIT.md should gain a "Patch authoring conventions" rule: *"Don't wrap assertions in try-catch unless the test specifically verifies the exception type. Default to direct assertions so failure messages name the real symptom rather than a boolean-comparison artifact."* This is a static rule that applies even to hand-authored patches. v1.5.9's QPB-side check enforces it for QPB-generated tests; bugspec's docs enforce it for everyone.

#### Empirical validation already exists

The 2026-06-05 Marcono1234 review IS the proof case. Layer 1 would have caught the try-catch-boolean pattern by literal regex. Layer 2 would have caught it via the "could this pass without the bug being absent?" prompt (the maintainer's exact framing). A v1.5.9 implementation would catch this class automatically before any future PR ships.

**Strong v1.5.9 candidate.** The lesson is fresh, the cost is bounded, and the upside (no more Marcono1234-style "your test is weaker than you think" comments) directly impacts QPB's maintainer-acceptance signal.

#### Open questions for design phase

1. **Should Layer 1 hard-fail or just warn?** A hard-fail might reject legitimate exception-typing tests (where try-catch IS the assertion). A warn-with-required-acknowledge probably better.
2. **How does Layer 2 know what the test's "stated intent" is?** Three candidate sources: the test method name (parseable), the PR body's "Testing" section (extractable), the writeup's "## 7. The test" section. Probably all three composed.
3. **Layer 3 cost on a 20-bug run.** Five extra mvn invocations per bug × 20 bugs × 30s each = 50 min added to a 4-hour benchmark run. Worth it on benchmark; probably too expensive for adopter Mode A.

---

## Part 3 — Design decisions to make before implementation

### 3.1 Architectural choice for Part 1 (see §1.5 table)

Cowork leans C (layered: mechanical + cross-artifact in gate; semantic in Council). Decision still required before implementation begins.

### 3.2 Scope: which of Part 1 + Part 2 lands in v1.5.9

Section 0 (Part 0) **must** ship — non-negotiable forcing function.

After Section 0, candidate ordering by Cowork's read of risk/value:

1. **B-7** (bugspec-format Phase 7 emit) — small effort, large payoff, fresh from session
2. **B-8** (weak-assertion detection) — small effort, fresh-evidence-backed (Marcono1234), high upside
3. **B-3** (resume/iterate) — moderate effort, large operator-value, ergonomically synergistic with Section 0
4. **B-6** (combine related findings) — moderate effort, clear scope
5. **Part 1 layered** (mechanical + cross-artifact + Council prompt) — large effort, value compounds across releases
6. **B-5** (adversarial review) — moderate effort, requires Phase 1 output extensions
7. **B-4** (bug-neighborhood iteration) — composes with B-5; defer if scope tight
8. **B-1, B-2** — security/isolation work; probably v1.6.0

Andrew decides during v1.5.9 kickoff after reading this doc and consulting load.

### 3.3 Voice / opinionation level of the public-tone check (Council category in §1.3)

Some 1.5.8 framing is intentionally forceful ("non-negotiable," "mandatory first action"). The public-tone Council check should flag candidates without auto-recommending softening — operator decides whether the force is load-bearing.

### 3.4 Scope: QPB-only vs every-adopter-skill

Part 1's ship-gate checks: do they apply only to QPB's own SKILL.md, or to every adopter's skill? Likely QPB-only for v1.5.9, generalize in v1.6.x.

---

## Part 4 — Carry-forward methodology lessons from v1.5.7 / v1.5.8 / Cowork session 2026-06-06

These are not v1.5.9 features. They are workflow rules that v1.5.9 work should follow.

### 4.1 Patch-authoring discipline (origin: 2026-06-06 gson PR cascade)

Two off-by-one hunk-header errors in hand-authored patches (BUG-001 said `+1,35` for 36-line content; BUG-002 said `+1,61` for 60-line content) broke the gson PR recovery. Pattern:

- **Don't hand-author `.patch` files.** Write the source file, format it with the target repo's formatter, then `git diff > foo.patch` to generate.
- **`git apply --check` every patch against a temp empty repo** before considering it ready.
- **Verify line counts mechanically.** `wc -l file | awk '{print $1-6}'` (file lines minus 6 header lines) should equal the hunk's `+1,N` declared content count.

This belongs in `ai_context/DEVELOPMENT_PROCESS.md` as a standing rule for any session that produces patches. v1.5.9 work that emits patches (B-7's bugspec-format emit, for instance) must follow these rules.

### 4.2 Multi-step shell discipline (origin: 2026-06-06 gson recovery script failures)

Multi-line shell scripts proposed to the operator must:

- **Assert cwd at every destructive step**, not just at the top.
- **Verify-before-mutate ordering**: create new content, verify it, then destroy old. Never `git rm OLD; create NEW` because the create can fail silently.
- **Use atomic operations where possible** (`git mv` over `git rm` + `git add`).
- **Include checkpoint assertions** (`[ -s file ] || exit 1`) before subsequent steps depend on prior steps' outputs.

This is a Council-of-Three-aware rule: any Council prompt that reviews multi-step shell content should check for these properties. Add to Council prompt template.

### 4.3 Formatter deference (origin: 2026-06-06 Spotless reflow surprises)

For any target repo with a formatter:

1. Apply the patch.
2. Run `spotless:apply` (or equivalent) to let the formatter dictate the form.
3. Commit the result.
4. Then check `spotless:check` passes.

Don't guess what the formatter wants. Let it tell you. v1.5.9's bugspec-format Phase 7 emit (B-7) should produce patches that pass formatter-check on common formatter-enforced projects (gson uses Spotless; Hangfire uses dotnet format; etc.).

### 4.4 Self-imposed velocity pressure → output overproduction (origin: 2026-06-06 forensic audit)

A behavioral pattern surfaced in the 2026-06-06 Cowork session: the assistant defaults to per-turn deliverable production (affirmation opening + substantive content + action proposals + structural elaboration), regardless of input shape. Multiple failure modes today traced to this:

- Multi-line shell scripts produced as runnable deliverables before verification gates were checked.
- Off-by-one patches produced as ready-to-publish artifacts before `git apply --check`.
- Recommendations delivered with "I lean X" then "your call" performative neutrality.

This pattern is documented as `radar_article_2026_06_06_velocity_pressure.md` (or equivalent — the Radar article that emerged from the session's forensic audit). v1.5.9 Council reviews should be aware of this pattern when reviewing worker outputs.

The countermeasure proposed: document-embedded rules with temporal precedence (loaded at session start before any input shapes behavior), specific observable triggers (not "be careful"), and mechanical verifiability (not "I'll watch myself"). This shape works because `CLAUDE.md`'s verify-before-claim rule has held across many sessions on exactly this structure.

---

## Out of scope for v1.5.9

- **Unified library across Octobatch / QPB / bugspec.** Deferred per Andrew's 2026-06-06 decision pending v1.5.9 substrate change shipping.
- **`copilot` / `codex` lane substrate changes.** Separate CLIs with independent deprecation timelines; reassess when those announcements land.
- **Public PR submission automation in QPB.** That's bugspec's job. QPB emits the bugspec-format spec (B-7); bugspec files the PR.
- **v1.6.0 QI work.** v1.5.9 stays in QC infrastructure. v1.6.0 begins continuous improvement loop using v1.5.4's measurement machinery.

---

## Open design questions consolidated

1. Heartbeat window default (§0.8.1)
2. Sentinel payload minimums (§0.8.2)
3. Banner UX (§0.8.3)
4. Multi-run launch ergonomics (§0.8.4)
5. Anti-gravity provider lane future (§0.8.5)
6. Subscription concurrency limits (§0.8.6)
7. `copilot`/`codex` lane futures (§0.8.7)
8. Part 1 architectural choice — A vs B vs C (§1.5)
9. Scope: Part 1 + Part 2 subset that fits in v1.5.9 (§3.2)
10. Public-tone Council check opinionation level (§3.3)
11. Ship-gate scope: QPB-only vs adopter-general (§3.4)
12. B-5 adversarial pass: Phase 4 sub-pass vs Phase 7 (§2.5)
13. B-5 default-on vs opt-in (§2.5)
14. B-8 Layer 1 hard-fail vs warn (§2.8)
15. B-8 Layer 2 intent source (§2.8)
16. B-8 Layer 3 cost-benefit on benchmark vs adopter Mode A (§2.8)

---

*End of Design Document. Implementation plan: see `QPB_v1.5.9_Implementation_Plan.md`.*
