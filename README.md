# Quality Playbook

**Version:** 1.5.6 | **Author:** [Andrew Stellman](https://github.com/andrewstellman) | **License:** Apache 2.0

## Find the 35% of bugs that code review misses

Most AI code review can only find structural issues: null dereferences, resource leaks, race conditions. That catches about 65% of real defects. The other 35% are intent violations -- bugs that can only be found if you know what the code is *supposed* to do. A function that silently returns null instead of throwing, a duplicate-key check that passes when the first value is null, a sanitization step that runs after the branch decision it was supposed to guard. These bugs look correct to any reviewer that doesn't know the spec.

The playbook closes that gap. It reads your codebase, derives behavioral requirements from every source it can find (code, docs, specs, comments, defensive patterns, community documentation), and uses those requirements to drive review. The result is a quality system grounded in intent, not just structure. For a deeper look at this problem, see the O'Reilly Radar article [AI Is Writing Our Code Faster Than We Can Verify It](https://www.oreilly.com/radar/ai-is-writing-our-code-faster-than-we-can-verify-it/).

## Need help? Just ask your AI

The rest of this README has detailed instructions for installing and running the playbook — commands, prompts, screenshots, the whole walkthrough. But the easiest way to get started is to skip the documentation entirely: **download one file, upload it to your favorite AI chatbot, and ask it for help.**

The file is [`ai_context/TOOLKIT.md`](https://github.com/andrewstellman/quality-playbook/blob/main/ai_context/TOOLKIT.md). It's a single Markdown document that explains everything about the Quality Playbook in a format designed for AI assistants to read and answer questions from.

Open a chat in whatever AI tool you use — Claude, ChatGPT, Cursor, GitHub Copilot, Gemini — attach `TOOLKIT.md`, and tell it:

> "Read TOOLKIT.md. Now you're an expert in the Quality Playbook."

<a href="https://chatgpt.com/share/69f78fc3-186c-83ea-9be6-70866b88db82"><img src="images/chatgpt-toolkit.png" alt="ChatGPT with TOOLKIT.md attached" width="1000"></a>

Then ask it anything: How do I set this up? What does Phase 3 actually do? How does it find bugs that structural code review misses? What's the difference between gap and adversarial iteration? Why did my run only find one bug? Your AI assistant will walk you through setup, running, interpreting results, and improving your next run.

[Here's what that conversation looks like in ChatGPT](https://chatgpt.com/share/69f78fc3-186c-83ea-9be6-70866b88db82) — it works the same in any other AI tool.

If you'd rather read the docs yourself, the rest of this README has the same information at higher resolution.

## Contents

- [How to use the Quality Playbook to find bugs in your code](#how-to-use-the-quality-playbook-to-find-bugs-in-your-code)
- [Running the playbook: phases, iterations, and macros](#running-the-playbook-phases-iterations-and-macros)
- [Rate limits and run budgets](#rate-limits-and-run-budgets)
- [What the playbook produces](#what-the-playbook-produces)
- [How it works](#how-it-works)
- [Roadmap](#roadmap)
- [Validation](#validation)
- [Setting up automation scripts](#setting-up-automation-scripts)
- [Repository structure](#repository-structure)
- [Example output](#example-output)
- [How we improve the playbook](#how-we-improve-the-playbook)
- [Context](#context)
- [License](#license)
- [Patent notice](#patent-notice)

## How to use the Quality Playbook to find bugs in your code

### Step 1: Install the skill

The playbook ships as a small set of files (`SKILL.md`, `quality_gate.py`, and the `references/` tree) that need to land in a directory your AI coding tool reads as a skill. The recommended path is to have your AI tool do the install for you.

**Recommended: have your AI tool install it.** Open a chat with Claude Code, Cursor, GitHub Copilot, or another AI coding assistant inside your target repo. Ask it:

> *"Read AGENTS.md from the Quality Playbook repo and follow the install procedure to set up the skill in this project."*

The AI agent reads [`AGENTS.md`](AGENTS.md), runs `python3 -m bin.install_skill` against the target, parses the structured output, and reports back. This is the default mode the install path is designed for.

**Alternative: run the script directly.** From your local QPB clone:

```bash
python3 -m bin.install_skill                                  # auto-detect from cwd
python3 -m bin.install_skill --into /path/to/target-repo      # scan a target repo, auto-detect AI tool inside it
python3 -m bin.install_skill --target /path/to/install-root   # literal install path (skip AI-tool auto-detect)
python3 -m bin.install_skill --verbose                        # human-readable output alongside structured events
```

`--into` and `--target` are different on purpose: `--into <target-repo>` walks INTO the named repo and auto-detects which AI-tool subdirectory to install into (`.claude/skills/quality-playbook/`, `.github/skills/`, `.cursor/skills/quality-playbook/`, or `.continue/skills/quality-playbook/`). `--target <path>` treats the path as the literal install root and writes `SKILL.md`, `quality_gate.py`, and `references/` directly there. The AI-agent-driven flow that AGENTS.md documents always uses `--into`; `--target` is for operators with a non-standard install location. They are mutually exclusive — `install_skill.py` errors if both are passed.

**Already manually copied SKILL.md to your skills directory?** Skip this step. The manual install paths described in Step 3 below continue to work — `bin/install_skill.py` is additive, not a replacement.

**What the install does:** copies `SKILL.md`, `quality_gate.py`, and `references/*.md` into the chosen install location. Runs a smoke check at the end (verifies `quality_gate.py` is loadable Python, `SKILL.md` parses with the expected frontmatter, `references/exploration_patterns.md` loads). Reports any failures in the structured output. Re-installs preserve operator-edited files as `<file>.operator-backup-<UTC-timestamp>` so your local edits aren't silently overwritten.

### Step 2: Provide documentation (strongly recommended)

The playbook produces better requirements, fewer false positives, and more specific
bugs when it has written documentation to work from. Plaintext files only —
`.txt` and `.md`. Convert other formats first:

- `pdftotext spec.pdf spec.txt`
- `pandoc -t plain spec.docx -o spec.txt`
- `lynx -dump https://example.org/spec.html > spec.txt`

**Where to put documentation in your target repo:**

    reference_docs/
    ├── claude-chat-2026-03-15.md    ← AI chat logs, design notes (Tier 4 context)
    ├── design-notes.md              ← exploratory writeups, retrospectives
    ├── incident-2026-02-retro.md    ← post-mortems, lessons learned
    └── cite/
        ├── my-project-spec.md       ← your project's own spec (citable)
        └── rfc7807.txt              ← external standards you cite (citable)

**Top-level `reference_docs/`** holds Tier 4 context — chat logs, design notes,
retrospectives, any exploratory material. The playbook reads these into Phase 1
as background but does not byte-verify quotes from them.

**`reference_docs/cite/`** holds citable material — specs, RFCs, API contracts,
published standards. Every file here produces a `FORMAL_DOC` record with a
mechanical citation excerpt that `quality_gate.py` byte-verifies. If you cite
it in a BUG or REQ, the gate checks the quote matches the bytes on disk.

You do not need a sidecar file, a frontmatter header, or any metadata.
Placement in `cite/` is the flag that says "this is citable." (Optional: the
first non-blank line of a `cite/` file may carry `<!-- qpb-tier: 2 -->` or
`# qpb-tier: 2` to mark it as Tier 2. Absent marker defaults to Tier 1.)

If you have no documentation at all, the playbook still runs. It will operate
from the source tree alone (Tier 3 evidence) and produce Tier 5 inferred
requirements. The results are weaker but valid.

**What does not belong in reference_docs:**

- Binary or formatted files (PDF, DOCX, HTML) — convert first, commit plaintext
- Code excerpts — the source tree is already Tier 3 authority
- Test fixtures or sample data — these are project artifacts, not documentation
- Anything private or sensitive that should not be read by an LLM — `reference_docs/`
  contents are loaded into Phase 1 prompts

### Step 3: Install the skill (manual flow — fallback)

If you prefer to do the install by hand instead of using `bin/install_skill.py` from Step 1, copy the skill files into your project directly:

**Claude Code:**
```bash
mkdir -p .claude/skills/quality-playbook/references
mkdir -p .claude/skills/quality-playbook/phase_prompts
cp SKILL.md .claude/skills/quality-playbook/SKILL.md
cp .github/skills/quality_gate/quality_gate.py .claude/skills/quality-playbook/quality_gate.py
cp references/* .claude/skills/quality-playbook/references/
cp phase_prompts/*.md .claude/skills/quality-playbook/phase_prompts/
# v1.5.2: single reference_docs/ tree at the target repo root.
# No README ships — cite/ contents are adopter-provided plaintext.
mkdir -p reference_docs reference_docs/cite
# Optional: append the suggested .gitignore rules for adopters (keeps bulk
# archived runs + reference_docs content out of version control while tracking
# the top-level RUN_INDEX.md).
cat skill-template.gitignore >> .gitignore
```

**GitHub Copilot (flat layout):**
```bash
mkdir -p .github/skills/references
mkdir -p .github/skills/phase_prompts
cp SKILL.md .github/skills/SKILL.md
cp .github/skills/quality_gate/quality_gate.py .github/skills/quality_gate.py
cp references/* .github/skills/references/
cp phase_prompts/*.md .github/skills/phase_prompts/
# v1.5.2: single reference_docs/ tree at the target repo root.
mkdir -p reference_docs reference_docs/cite
cat skill-template.gitignore >> .gitignore
```

**GitHub Copilot (nested layout):**
```bash
mkdir -p .github/skills/quality-playbook/references
mkdir -p .github/skills/quality-playbook/phase_prompts
cp SKILL.md .github/skills/quality-playbook/SKILL.md
cp .github/skills/quality_gate/quality_gate.py .github/skills/quality-playbook/quality_gate.py
cp references/* .github/skills/quality-playbook/references/
cp phase_prompts/*.md .github/skills/quality-playbook/phase_prompts/
# v1.5.2: single reference_docs/ tree at the target repo root.
mkdir -p reference_docs reference_docs/cite
cat skill-template.gitignore >> .gitignore
```

**Cursor, Windsurf, other tools:** Use any of the locations above, or put `SKILL.md`, `quality_gate.py`, and `references/` in your project root. The runner, gate, and orchestrator agents check all four locations — repo-root `SKILL.md`, Claude's `.claude/skills/quality-playbook/`, and both Copilot layouts.

**OpenAI Codex CLI:** v1.5.3 adds the standalone [codex CLI](https://github.com/openai/codex) (codex-cli 0.125+) as a third runner alongside claude and copilot. No separate skill-install layout — codex runs the playbook from any of the locations above. To use it via `bin/run_playbook.py`, pass `--codex` (see Step 4 + the "Running everything autonomously" section below).

### Step 4: Run the playbook

**Claude Code:**
```bash
claude --agent agents/quality-playbook.agent.md
```
Add `--dangerously-skip-permissions` to skip file-write approval prompts.

**GitHub Copilot:** Open the chat panel in VS Code, IntelliJ, or any IDE with Copilot support and say: *"Run the quality playbook on this project."* For the CLI, use `copilot-cli` with `--yolo` to skip prompts.

**OpenAI Codex CLI:**
```bash
python3 -m bin.run_playbook --codex ./my-project
```
This invokes `codex exec --full-auto` (sandboxed automatic execution; the codex equivalent of `gh copilot --yolo`) for each playbook phase. Codex picks its model from `~/.codex/config.toml` unless you pass `--model gpt-5-codex` (or another model name in your codex config).

**Cursor:** Open Composer (Cmd+I / Ctrl+I) and say: *"Read SKILL.md and run the quality playbook on this project."*

**Windsurf:** Open Cascade and say: *"Read SKILL.md and run the quality playbook on this project."*

<a href="images/claude-code-bootstrap-2.png"><img src="images/claude-code-bootstrap-0.png" alt="Giving Claude Code the initial prompt to start the playbook" width="700"></a>

The playbook runs in six phases. Each phase gets its own context window — this is what lets it do deep analysis instead of running out of context on large codebases. After each phase, say "keep going" to continue.

<a href="images/claude-code-bootstrap-2.png"><img src="images/claude-code-bootstrap-2.png" alt="Phase 1 results: 6 candidate bugs found" width="700"></a>

*After Phase 1, the playbook reports candidate bugs and tells you what to say next.*

<a href="images/claude-code-bootstrap-4.png"><img src="images/claude-code-bootstrap-4.png" alt="Phase 5: TDD verification of confirmed bugs" width="700"></a>

*Phase 5 confirms every bug with TDD red-green verification and generates fix patches.*

<a href="images/claude-code-bootstrap-5.png"><img src="images/claude-code-bootstrap-5.png" alt="Final results: 7 confirmed bugs with patches" width="700"></a>

*The final summary shows all confirmed bugs with regression tests, patches, and writeups.*

The six phases: **Explore** (read code + docs, find candidates) → **Generate** (requirements, tests, protocols) → **Code Review** (three-pass: structural, requirement verification, cross-requirement consistency) → **Spec Audit** (three independent auditors check code against requirements) → **Reconciliation** (every bug tracked, regression-tested, TDD-verified) → **Verify** (45 self-check benchmarks). The full cycle takes 15-90 minutes depending on project size and works with any language.

### Step 5: Run iterations

After the baseline, the playbook suggests iteration strategies that find different classes of bugs — typically 40-60% more on top of the baseline. Say *"Run the next iteration using the gap strategy"* to start, then follow the suggested order: gap → unfiltered → parity → adversarial.

### Running everything autonomously

To run the full baseline and all four iterations without manual intervention:

**Claude Code:**
```bash
claude --agent agents/quality-playbook-claude.agent.md --dangerously-skip-permissions -p \
  "Run the full quality playbook with all iterations. Run each phase as a separate
   sub-agent, then run all four iteration strategies (gap, unfiltered, parity,
   adversarial) in sequence, each as a separate sub-agent. Do not stop between
   phases or iterations — run everything end to end."
```

To capture the output to a log file, add `2>&1 | tee playbook-run.log` to the end.

**Via `bin/run_playbook.py` (any runner):** the Python orchestrator at `bin/run_playbook.py` accepts a runner-selection flag — pick one of `--claude` / `--copilot` (default) / `--codex`. Example: `python3 -m bin.run_playbook --codex ./my-project` runs all six phases via `codex exec --full-auto`. Use `--model <name>` to override the runner's default model (codex picks from `~/.codex/config.toml` when no `--model` is passed).

This uses the orchestrator agent (`quality-playbook-claude.agent.md`), which spawns a separate sub-agent for each of the six phases and each of the four iteration strategies. Each sub-agent gets its own context window, communicates with the others through files on disk (`quality/PROGRESS.md`, `quality/BUGS.md`, etc.), and exits when its phase is complete. The orchestrator reads the results and launches the next sub-agent.

Three things in the prompt matter:

**"Run each phase as a separate sub-agent"** — this is the most important part. Each phase needs the full context window for deep analysis. If the agent tries to run multiple phases in a single context, it runs out of room partway through Phase 3 on most projects, producing shallow analysis and fewer bugs. Separate sub-agents mean each phase gets ~200K tokens of context for investigation.

**"All four iteration strategies in sequence"** — iterations re-explore the codebase with different approaches: gap (areas the baseline missed), unfiltered (pure domain-driven exploration without structural constraints), parity (compare parallel code paths), and adversarial (challenge prior dismissals). Each strategy finds a different class of bug. Running all four typically adds 40-60% more confirmed bugs on top of the baseline.

**"Do not stop between phases or iterations"** — by default, the playbook pauses after each phase and waits for the user to say "keep going." This is useful when you want to review intermediate results, but for an autonomous run you want it to continue through all ten sub-agents (six phases + four iterations) without interruption.

The full autonomous run takes 60-180 minutes depending on codebase size and model. Add `--model sonnet` or `--model opus` to choose a specific model.

### Step 6: Fix bugs, then recheck

After fixing the bugs from BUGS.md, say *"recheck"* to verify your fixes. Recheck mode reads the existing bug report, checks each bug against the current source (reverse-applying patches, inspecting cited lines), and reports which bugs are fixed vs. still open. Takes 2-10 minutes instead of re-running the full pipeline.

## Running the playbook: phases, iterations, and macros

`bin/run_playbook.py` exposes three invocation modes:

**Mode 1 — Single baseline run (default):**

    python3 -m bin.run_playbook ./my-project

Runs Phase 1 through Phase 6 in sequence on one target.

**Mode 2 — Explicit iteration list:**

    python3 -m bin.run_playbook --iterations gap,unfiltered,parity,adversarial ./my-project

Runs baseline + the listed iteration strategies in order. **Early-stop is disabled** when `--iterations` is explicit — every strategy in the list runs regardless of prior yields.

**Mode 3 — `--full-run` macro:**

    python3 -m bin.run_playbook --full-run ./my-project

Equivalent to baseline + all four iteration strategies (`gap`, `unfiltered`, `parity`, `adversarial`) in order, **with early-stop enabled.** If yields drop below the threshold, remaining iterations are skipped.

Use Mode 2 when you want to force all four strategies to run even if early-stop would trigger. Use Mode 3 for unattended runs where you're happy to save budget on clearly-exhausted cycles.

## Rate limits and run budgets

- **GitHub Copilot GPT-5.4:** Copilot enforces a 54-hour cooldown on ~15M-token prompts. Plan benchmark re-runs accordingly — the casbin-1.5.1 incident locked out GPT-5.4 for two days mid-release.
- **Claude Code plan budget:** a full run of the playbook on a 50K-LOC project typically consumes ~30% of a Sonnet-family monthly budget. Budget surges during Phase 4 (Spec Audit, three parallel auditors) and Phase 5 (TDD red-green verification on many bugs).
- **Reference-doc scaling:** the playbook reads all of `reference_docs/` into Phase 1 context. Keep it under ~2M tokens to avoid context-budget pressure on downstream phases. For very large specs, curate the excerpts that are actually cited rather than dumping full RFCs.

### Why phases?

The playbook runs each phase in a separate context window on purpose. A single-session approach runs out of context partway through Phase 3 on most projects, which means shallow analysis and missed bugs. The phase-by-phase design gives each phase the full context budget for deep investigation. The tradeoff is saying "keep going" a few times — or use the autonomous mode above to skip the manual steps entirely.

## What the playbook produces

The playbook generates these files:

| Artifact | Location | What it does |
|----------|----------|-------------|
| `REQUIREMENTS.md` | `quality/` | Behavioral requirements derived from code, docs, and community sources via a five-phase pipeline. This is the foundation -- without requirements, review is limited to structural bugs. |
| `QUALITY.md` | `quality/` | Quality constitution defining what "correct" means for this specific project, with fitness-to-purpose scenarios and coverage theater prevention. |
| `test_functional.*` | `quality/` | Functional tests in the project's native language, traced to requirements rather than generated from source code. |
| `RUN_CODE_REVIEW.md` | `quality/` | Three-pass protocol: structural review, requirement verification, cross-requirement consistency. Each pass finds bugs the others can't. |
| `RUN_SPEC_AUDIT.md` | `quality/` | Council of Three: three independent AI models audit the code against requirements. Different models have different blind spots, and the triage uses confidence weighting, not majority vote. |
| `RUN_INTEGRATION_TESTS.md` | `quality/` | End-to-end test protocol grounded in use cases, with a traceability column mapping each test to the user outcome it validates. |
| `RUN_TDD_TESTS.md` | `quality/` | Red-green TDD verification protocol: for each confirmed bug, prove the regression test fails on unpatched code and passes with the fix. |
| `BUGS.md` | `quality/` | Consolidated bug report with spec basis, severity, reproduction steps, and patch references for every confirmed finding. |
| `AGENTS.md` | project root | Bootstrap file so every future AI session inherits the full quality infrastructure. |

## How it works

The playbook's value comes from requirement derivation. AI code reviewers are bottlenecked by the same thing human reviewers are: if you don't know what the code is *supposed* to do, you can only find structural issues. The playbook's main job is figuring out intent, then using that intent to drive every downstream artifact.

**Phase 1: Explore.** The AI reads source files, tests, config, specs, and commit history. If you provide community documentation (GitHub issues, user guides, API docs, forum discussions), it reads those too. The goal is to understand not just what the code does, but what it's supposed to do.

**Phase 2: Generate.** A five-phase pipeline extracts behavioral contracts from the codebase, derives testable requirements, verifies coverage, checks completeness, and adds a narrative layer with validated use cases. The pipeline also generates functional tests, review protocols, a TDD verification protocol, and the quality constitution.

**Phase 3: Code review.** A three-pass code review runs against HEAD: structural review with anti-hallucination guardrails, requirement verification checking each requirement against the code, and cross-requirement consistency checking whether requirements contradict each other. About 65% of findings come from Pass 1, 35% from Passes 2 and 3. Each confirmed bug gets a regression test.

**Phase 4: Spec audit.** Three independent AI models audit the code against the requirements. The triage process uses verification probes -- targeted checks that ask "is this actually true?" -- rather than dismissing single-model findings. As of v1.3.17, verification probes must produce executable test assertions (not just prose reasoning) to confirm or reject findings, which prevents the triage from hallucinating code compliance. The most valuable findings are often the ones only one model catches.

**Phase 5: Reconciliation.** Post-review reconciliation closes the loop: every bug from code review and spec audit is tracked, regression-tested or explicitly exempted, and the completeness report is finalized with one authoritative verdict.

**Phase 6: Verify.** 45 self-check benchmarks validate the generated artifacts against internal consistency rules -- requirement counts match across all surfaces, no stale text remains, every finding has a closure status, and triage probes include executable evidence.

### Why documentation matters

Adding community documentation to the pipeline produces measurably better results. In a controlled experiment across multiple repositories, documentation-enriched runs found more bugs, different bugs, and higher-confidence bugs than code-only baselines. The documentation gives auditors spec language to check against, turning "this code looks odd" into "this code contradicts the documented behavior."

## Roadmap

The Quality Playbook is developed in a two-half arc. The v1.5.x series is the QC half — the quality-control infrastructure for finding bugs and validating skill prose. The v1.6+ series is the QI half — quality-improvement built on top of that infrastructure: better requirements review, statistical control over the development process, and eventually multi-operator workflows. Each version below has a brief description, a tag (most recent for that minor version), and links to its design and implementation-plan documents.

- **v1.8 — Cross-operator workflow** *(future).* Multiple QPB operators sharing calibration data, lever-pull history, and benchmark results across sites. Lets a team adopt the playbook and accumulate evidence collectively rather than each operator running a private cycle. Design forthcoming.

- **v1.7 — Statistical process control machinery.** Statistical process control for both the improvement loop (multi-cycle calibration data with control charts on lever-pull deltas) and the SDLC itself (defect-rate trending, recurrence-class detection, process-change drivers). Includes **multi-cell calibration cycles** — multiple lever pulls in parallel using cell.json's structured output instead of one at a time — and **cross-version trend tracking** — recall trajectories per benchmark per release, with control limits inferred from accumulated history. Both are next iterations of QPB's own development process; the SPC framework's first proof point is the QPB development workflow itself. Design at [`docs/design/QPB_v1.7.0_Design.md`](docs/design/QPB_v1.7.0_Design.md), spec at [`docs/design/QPB_v1.7.0_Implementation_Plan.md`](docs/design/QPB_v1.7.0_Implementation_Plan.md).

- **v1.6 — Requirements review and management UX.** Operator-facing system for reviewing and managing the requirements QPB derives from a target. The UX walks the operator through each requirement (Wiegers quality attributes — clarity, completeness, consistency, testability, necessity, feasibility, verifiability), surfaces evidence from formal docs, informal sources (chat archives, design notes), and exploration findings, and helps validate or refine the REQ set. Includes **targeted playbook runs that check specific requirements against the code** — e.g., re-derive REQ-007 against the updated source, verify a logging requirement against `bin/audit_log.py`, compare the current REQ-set against a prior run for drift detection. Closes the QI loop: defect data from review sessions feeds back into Phase 1/2 prompt-tuning calibration cycles. Design at [`docs/design/QPB_v1.6.0_Design.md`](docs/design/QPB_v1.6.0_Design.md), spec at [`docs/design/QPB_v1.6.0_Implementation_Plan.md`](docs/design/QPB_v1.6.0_Implementation_Plan.md), feature proposal at [`docs/design/QPB_v1.6.x_Requirements_Review_Proposal.md`](docs/design/QPB_v1.6.x_Requirements_Review_Proposal.md).

- **v1.5.6 — Adopter-facing distribution + Pattern 7 displacement-recovery cycle.** Shipped turnkey install/distribution (`bin/install_skill.py`, AGENTS-driven setup, multi-environment auto-detection), code-only-mode documentation/instrumentation for empty `reference_docs/`, and adopter-grade AI orchestration patterns documentation; the Pattern 7 displacement-recovery cycle also shipped with a documented revert, keeping the budget cap at `3-5`. Tag [`v1.5.6`](https://github.com/andrewstellman/quality-playbook/releases/tag/v1.5.6). Design at [`docs/design/QPB_v1.5.6_Design.md`](docs/design/QPB_v1.5.6_Design.md), spec at [`docs/design/QPB_v1.5.6_Implementation_Plan.md`](docs/design/QPB_v1.5.6_Implementation_Plan.md).

- **v1.5.5 — Autonomous improvement-loop infrastructure.** Run-state instrumentation (`quality/run_state.jsonl`, `quality/PROGRESS.md`), phase-boundary cross-validation (catches the failure mode where a phase reports "complete" with empty artifacts), Phase 5 source-edit guardrail, calibration-cycle orchestrator template, four matplotlib visualization charts, plus seven v1.5.4 self-audit defect fixes and four inherited regression-replay test failures cleared. Tag: in flight (HEAD on the `1.5.5` branch; not yet tagged). Design at [`docs/design/QPB_v1.5.5_Design.md`](docs/design/QPB_v1.5.5_Design.md), spec at [`docs/design/QPB_v1.5.5_Implementation_Plan.md`](docs/design/QPB_v1.5.5_Implementation_Plan.md).

- **v1.5.4 — Skill-as-code via AI-driven file role tagging + Pattern 7.** Phase 1 produces `quality/exploration_role_map.json` with one record per in-scope file (role tag: `skill-prose` / `skill-tool` / `code` / `test` / `docs` / etc.); replaces v1.5.3's mechanical Code/Skill/Hybrid classifier whose LOC denominator was getting polluted by playbook artifacts shipped into benchmark targets. Pipeline activation reads the role map (always-Hybrid downstream). Pattern 7 — Composition and Mount-Context Awareness — added as the seventh exploration pattern. First calibration cycle measured +0.20 recall on chi-1.3.45 with documented displacement asterisk. Tag [`v1.5.4`](https://github.com/andrewstellman/quality-playbook/releases/tag/v1.5.4). Design at [`docs/design/QPB_v1.5.4_Design.md`](docs/design/QPB_v1.5.4_Design.md), spec at [`docs/design/QPB_v1.5.4_Implementation_Plan.md`](docs/design/QPB_v1.5.4_Implementation_Plan.md).

- **v1.5.3 — Four-pass skill-derivation pipeline + project-type classifier.** Extends the v1.5.0 divergence model to AI-skill targets where SKILL.md prose IS the spec. Phase 0 classifier (`bin/classify_project.py`) tags each target as Code / Skill / Hybrid. Four-pass derivation pipeline: Pass A naive coverage, Pass B mechanical citation extraction with Jaccard pre-filter (~93× speedup), Pass C formal REQ + UC production, Pass D coverage audit with structured Council inbox. Curated REQUIREMENTS.md comparable to the Haiku reference (~65 unique REQ definitions). Cross-target validation against five code targets and three pure-skill targets. Tag [`v1.5.3`](https://github.com/andrewstellman/quality-playbook/releases/tag/v1.5.3). Design at [`docs/design/QPB_v1.5.3_Design.md`](docs/design/QPB_v1.5.3_Design.md), spec at [`docs/design/QPB_v1.5.3_Implementation_Plan.md`](docs/design/QPB_v1.5.3_Implementation_Plan.md).

- **v1.5.2 — Council review hardening + cardinality gate.** Two nine-panelist Council-of-Three reviews cleared the release. New `_finalize_iteration` helper runs `quality_gate.py` as a subprocess after each iteration and writes structured PROGRESS.md output. Cardinality gate hardening: citation excerpts byte-equal verified against the producer's `extract_excerpt` output, strict boolean type checks, body-prose vs. tier-marker disambiguation. Citation verifier hardening — citation-stale detection now runs end-to-end. Phase 6 verdict-mapping guard so a `fail` finalizer no longer demotes to `partial` because the gate log contains "warn." Tag [`v1.5.2`](https://github.com/andrewstellman/quality-playbook/releases/tag/v1.5.2). Design at [`docs/design/QPB_v1.5.2_Design.md`](docs/design/QPB_v1.5.2_Design.md), spec at [`docs/design/QPB_v1.5.2_Implementation_Plan.md`](docs/design/QPB_v1.5.2_Implementation_Plan.md).

- **v1.5.1 — Phase 5 writeup hydration.** Phase 5 prompt carries a MANDATORY HYDRATION STEP — a BUGS.md → writeup field map, a worked BUG-004 example, and a per-writeup confirmation checklist forbidding empty backticks, empty diff fences, and angle-bracket placeholders. `quality_gate.py`'s `check_writeups` fails on any of five template-sentinel strings, or on `\`\`\`diff` fences containing no `+` / `-` lines. Case-insensitive diff-fence detection so mixed-case fences don't slip past the inline-fix-diff check. Tag [`v1.5.1`](https://github.com/andrewstellman/quality-playbook/releases/tag/v1.5.1). Design at [`docs/design/QPB_v1.5.1_Design.md`](docs/design/QPB_v1.5.1_Design.md), spec at [`docs/design/QPB_v1.5.1_Implementation_Plan.md`](docs/design/QPB_v1.5.1_Implementation_Plan.md).

- **v1.5.0 — Divergence model + consolidated `quality/` layout.** Introduces the divergence framing: a defect is a divergence between documented intent and code implementation, not a judgment about whether the code is "good." Bootstrap artifacts tracked in git as project history (`quality/runs/`, `quality/control_prompts/`). Foundation for the v1.5.x quality-control arc. Tag [`v1.5.0`](https://github.com/andrewstellman/quality-playbook/releases/tag/v1.5.0). Design at [`docs/design/QPB_v1.5.0_Design.md`](docs/design/QPB_v1.5.0_Design.md), spec at [`docs/design/QPB_v1.5.0_Implementation_Plan.md`](docs/design/QPB_v1.5.0_Implementation_Plan.md).

- **v1.4 — Six-phase architecture + iteration strategies + TDD red-green.** Playbook splits into six phases (Explore, Generate, Review, Audit, Reconcile, Verify), each running in its own context window with exit gates verifying prerequisites and artifact completeness. Four iteration strategies (gap, unfiltered, parity, adversarial) consistently add 40-60% more confirmed bugs on top of the baseline. Every confirmed bug requires a regression-test patch, a red-phase log proving the test fails on unpatched code, and a green-phase log proving the fix resolves it. Mechanical quality gate (`quality_gate.py`) validates artifact completeness as the final Phase 6 step. Validated against Express.js, Gson, virtio. Tag [`v1.4.6`](https://github.com/andrewstellman/quality-playbook/releases/tag/v1.4.6) (most recent v1.4.x). Design at [`docs/design/QPB_v1.4_Design.md`](docs/design/QPB_v1.4_Design.md). No standalone implementation plan — design contains the work breakdown.

- **v1.3 — Mechanical verification + iterative convergence.** Mechanical artifacts with integrity check: extraction commands (awk/grep) produce per-function evidence files, append themselves to `quality/mechanical/verify.sh`, and Phase 6 re-runs the script and diffs against saved files (catches the failure mode where the model executes the right command but writes fabricated output). Contradiction gate compares executed evidence (mechanical artifacts, regression-test results, TDD red-phase failures) against prose artifacts; if they contradict, the executed result wins. Self-contained iterative convergence: Phase 0 builds a seed list from prior runs, mechanically re-checks each seed; runs iterate up to 5 times until net-new bugs = 0. Tag [`v1.3.50`](https://github.com/andrewstellman/quality-playbook/releases/tag/v1.3.50) (most recent v1.3.x). Design across multiple incremental files: [`docs/design/QPB_v1.3.0_Design.md`](docs/design/QPB_v1.3.0_Design.md), [`docs/design/QPB_v1.3.7_Design.md`](docs/design/QPB_v1.3.7_Design.md), [`docs/design/QPB_v1.3.21_Design.md`](docs/design/QPB_v1.3.21_Design.md), [`docs/design/QPB_v1.3.35_Design.md`](docs/design/QPB_v1.3.35_Design.md), [`docs/design/QPB_v1.3.50_Design.md`](docs/design/QPB_v1.3.50_Design.md), and others — each captures the design state at that increment.

- **v1.2 — Initial public release.** First tagged version of the playbook with the inspection-style workflow (deskcheck → walkthrough → inspection) and the bug-finding-as-divergence-detection methodology. Tag [`v1.2.16`](https://github.com/andrewstellman/quality-playbook/releases/tag/v1.2.16) (most recent v1.2.x). Design at [`docs/design/QPB_v1.2.15_Design.md`](docs/design/QPB_v1.2.15_Design.md).

### What's new in v1.5.6

- **Adopter-facing distribution is now the default path.**
  QPB now ships a turnkey AI-agent-driven installer at
  [`bin/install_skill.py`](bin/install_skill.py), and the README quickstart is
  restructured so install is Step 1 instead of an afterthought.
- **The installer works in multiple environments without repo-specific hand edits.**
  It auto-detects `.claude/`, `.github/`, `.cursor/`, and `.continue/` targets,
  and it also supports explicit `--into <target-repo>` and `--target <path>`
  flags when the operator wants to pin the destination.
- **Cross-platform support is part of the release contract.**
  The install path is written for Windows, macOS, and Linux via `pathlib`-style
  path handling. Windows was asserted in code and tests, but not directly
  exercised in this release environment.
- **Re-installs are idempotent and preserve operator edits.**
  Existing files are not silently clobbered; operator-modified copies are
  preserved via timestamped backup handling so install automation does not erase
  local customization.
- **`AGENTS.md` now carries an install-procedure section meant for the AI itself.**
  An adopter can point Claude Code, Cursor, Copilot, or another coding agent at
  [`AGENTS.md`](AGENTS.md), ask it to follow the install procedure, and let the
  agent drive the setup using the script's structured output.
- **Missing-documentation runs now downgrade cleanly instead of feeling half-broken.**
  When `reference_docs/` is empty, the playbook proceeds in explicit code-only
  mode rather than implying docs should have been there.
- **That downgrade is visible in both artifacts and telemetry.**
  Phase 1 opens `quality/EXPLORATION.md` with code-only framing,
  `quality/run_state.jsonl` records a `documentation_state` event, and adopters
  now have [`references/code-only-mode.md`](references/code-only-mode.md)
  explaining the weaker evidence posture and how to upgrade later by adding docs.
- **AI orchestration patterns are documented for adopters, not just maintainers.**
  New [`ai_context/AI_ORCHESTRATION_PATTERNS.md`](ai_context/AI_ORCHESTRATION_PATTERNS.md)
  explains the orchestrator/worker pattern at adoption depth, with worked
  examples that cite the v1.5.5 ai_context-refresh runner and cross-links from
  [`ai_context/DEVELOPMENT_PROCESS.md`](ai_context/DEVELOPMENT_PROCESS.md) and
  [`agents/calibration_orchestrator.md`](agents/calibration_orchestrator.md).
- **The Pattern 7 displacement-recovery cycle completed, and the honest verdict is revert.**
  The cycle ran to completion on two benchmarks with substantive before/after
  recall (`chi-1.3.45`, `virtio-1.5.1`) plus an express pre-lever run used for
  context. Lowering Pattern 7's budget cap to `2-3` did recover
  `AllowContentEncoding`, but it did not recover `PathRewrite`, did not preserve
  the mount-context findings on chi, and left the load-bearing benchmark worse
  overall, so the cap stays at `3-5`.
- **The release keeps the evidence trail rather than smoothing it over.**
  The cycle audit at `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/audit.md`
  and the corresponding `Lever_Calibration_Log` entry are preserved as shipped
  deliverables, including the surfaced REQ-ID instability finding: replay
  matching by `(REQ_id, file)` is still noisy across runs at roughly 50%
  file-basename overlap and needs methodology work in the v1.7 SPC arc.
- **Two cycle-scope deferrals remain explicit.**
  Express post-lever orchestration was interrupted at the weekly API limit, and
  `chi-1.5.1` was dropped on time-budget grounds. Both follow-up questions move
  to v1.5.7 rather than being treated as silent omissions.
- **Known limitations remain in the release notes instead of being buried in validation output.**
  Windows install behavior is `untested-infrastructure-blocked-pathlib-coverage-extended`
  (no Windows machine, no Wine, no Windows container in the validation
  sandbox; cluster D extended `PureWindowsPath` coverage in the install-skill
  test surface in lieu of a direct run). The reused `chi-1.3.45` Phase 4
  evidence is still code-only rather than a fresh docs-backed validation run
  (cluster E diagnostic-only this release; the docs-backed re-run is a
  v1.5.7 calibration-session item).
- **Bootstrap self-audit fix-up: 22 named issues closed across 8 clusters.**
  v1.5.6's self-bootstrap run on 2026-05-02 surfaced 20 named bugs plus 2
  quality-gate self-consistency failures. All 22 are fixed in clusters 1-8
  (commits `aa24405` through `e2b6998`). GitHub
  [issue #1](https://github.com/andrewstellman/quality-playbook/issues/1)
  (Kevin McMahon, opened against v1.4.4) is fully closed: concerns 1-3 and
  5 by clusters 1, 2, 3, 5, 7 plus the v1.4.5 retirement of `quality_gate.sh`;
  concern 4 (the README Step 4 `claude --agent agents/...` invocation gap)
  by cluster A. Bootstrap fix-up summary at
  [`Reviews/QPB_v1.5.6_Bootstrap_Fixup_Verification.md`](https://github.com/andrewstellman/quality-playbook/tree/1.5.6).
- **`bin/install_skill.py` now bundles `agents/` alongside `references/` and `phase_prompts/`.**
  Cluster A (commit `161d923`). Adopters who follow the AGENTS.md install
  procedure now have `agents/quality-playbook.agent.md` and
  `agents/quality-playbook-claude.agent.md` at the install destination —
  the README Step 4 `claude --agent agents/...` invocation resolves from
  the target repo, not just from inside the QPB clone. Two regression
  tests (`test_agents_bundled_in_install`,
  `test_agents_bundled_via_target_override`) pin the bundle parity.
- **`.github/skills/quality_gate.py` is now a working Python shim instead of a broken symlink stub.**
  Cluster A (commit `161d923`). Pre-fix it was a git symlink that didn't
  materialize as a symlink on filesystems with `core.symlinks=false`,
  leaving a 28-byte text stub that crashed when invoked as Python. The
  new shim adds `quality_gate/` to `sys.path` and dispatches to its
  `main()`. Adopters never see the shim; `bin/install_skill.py` copies
  the canonical script directly to `<install_root>/quality_gate.py`.
- **Phase 2 = Generate, not Triage — across every surface.**
  Clusters 3 (commit `7ab8ef4`) and 6 (`54380f7`) reconciled the v1.5.5
  design's never-shipped triage model with the actually-shipped Generate
  contract: `references/orchestrator_protocol.md`, the agent files,
  `ai_context/DEVELOPMENT_CONTEXT.md`, and now
  `bin/run_state_lib.validate_phase_artifacts` Phase 2 + `SKILL.md` Phase 2
  instrumentation prose all describe the same 9-artifact contract
  (`REQUIREMENTS.md`, `QUALITY.md`, `CONTRACTS.md`, `COVERAGE_MATRIX.md`,
  `COMPLETENESS_REPORT.md`, four `RUN_*.md` files) plus a non-empty
  `quality/test_functional.<ext>`.
- **Phase prompts are now layout-agnostic.**
  Clusters 5 (commit `45880cb`) and B (`6a185c4`) replaced hardcoded
  `.github/skills/` paths in `phase_prompts/phase{1..6}.md` with the
  `{skill_fallback_guide}` placeholder that interpolates the canonical
  six-layout fallback list. Adopters using `.claude/`, `.cursor/`, or
  `.continue/` install layouts now get phase prompts that point at
  their actual install locations. The phase-prompt regression test
  surface (`PhasePromptHardcodedPathRegressionTests`) covers all six
  phases per-line; future single-layout hardcodes trip a clear failure.
- **`validate_phase_artifacts` validators match the shipped pipeline for every phase.**
  Cluster B (commit `6a185c4`) reconciled the Phase 3-6 validators against
  the shipped pipeline (Phase 3 = Code Review's `quality/code_reviews/`
  + conditional regression patches; Phase 4 = Spec Audit's
  `quality/spec_audits/` triage + auditor files; Phase 5 = Reconciliation's
  per-bug writeups + red-phase logs + `tdd-results.json`; Phase 6 = Verify's
  `quality-gate.log` + `Terminal Gate Verification` section). The
  `phase_names` dict in `write_progress_md` now uses shipped pipeline
  labels (Explore / Generate / Code Review / Spec Audit / Reconciliation /
  Verify) instead of the v1.5.5-design Triage-model labels.
- **`--require-docs` opt-out flag for missing-documentation runs.**
  Cluster C (commit `a3b94eb`). Operators who want a hard fail when
  `reference_docs/` is empty can pass `--require-docs` to
  `python3 -m bin.run_playbook` — the run aborts at Phase 1 entry with
  an `aborted_missing_docs` event in `quality/run_state.jsonl` and a
  clear `ERROR: aborted_missing_docs` block in `quality/PROGRESS.md`,
  before any LLM work. Default behavior unchanged: code-only mode is
  still the default downgrade. The flag is for compliance/policy
  contexts where a quiet code-only-mode run would mask a process gap.
- **`load_historical_bugs` returns `None`, not silent `[]`, on missing archives.**
  Cluster 8 (commit `e2b6998`). `bin/visualize_calibration.load_historical_bugs`
  now distinguishes "archive missing" (returns `None` and logs a WARNING
  with the missing path) from "archive present but contains zero bug
  headings" (returns `[]`, no log). Pre-fix the missing-archive case
  silently returned `[]`, masking it as "archive present but empty" —
  cycle replay charts couldn't tell the operator the baseline wasn't
  staged.
- **Calibration cycle protocol learned from execution.**
  Cluster F.1 (commit `ba64584`) folded three lessons from the 2026-05-02
  Pattern 7 cycle into `agents/calibration_orchestrator.md`:
  API-budget-exhausted recovery (the express post-lever case), the
  reduced-scope option's three preconditions (named in audit, flagged
  for follow-up, NOT the benchmark most directly tied to the
  hypothesis), and the mid-benchmark post-lever interruption failure
  mode.
- **Two follow-on items deferred to a v1.5.7 calibration session.**
  Cluster E (chi-1.3.45 docs-backed validation re-run) and cluster F.2-F.4
  (chi-1.5.1 follow-up cycle, express post-lever completion, audit
  refresh) require multi-hour LLM playbook subprocess executions per
  the calibration_orchestrator.md Mode 1 spawn-and-resume pattern —
  outside a coding-worker session's scope. Diagnostic findings for both
  are captured in
  [`v1.5.6_runner/outputs/032`](https://github.com/andrewstellman/quality-playbook/tree/1.5.6)
  and `034`. The 2026-05-02 cycle's `revert` verdict on Pattern 7
  budget-cap stands; cluster F.2-F.4 would close the original
  4-benchmark scope but won't change the verdict.

### What's new in v1.5.5

- **Run-state instrumentation.** Every meaningful playbook event lands in `quality/run_state.jsonl` (machine-readable, append-only) and is reflected in `quality/PROGRESS.md` (atomically rewritten human view). Schema at [`references/run_state_schema.md`](references/run_state_schema.md). Helpers at [`bin/run_state_lib.py`](bin/run_state_lib.py) — read/parse events, validate format invariants, render PROGRESS.md, append events. Replaces the v1.5.4 `/tmp/`-based scheduled-task loop, which did not survive sandbox runtime constraints (state-file UID locking, host-only paths, subprocess lifetimes).
- **Phase-boundary cross-validation.** Every `phase_end` event is written only after the AI verifies its phase produced the expected artifacts (Phase 1's `EXPLORATION.md` ≥ 200 bytes with finding sections; Phase 4's `REQUIREMENTS.md` + `COVERAGE_MATRIX.md` + per-pass outputs in `quality/phase3/` if skill-derivation ran; Phase 6's `BUGS.md` + `INDEX.md` with `gate_verdict`; etc.). Catches the v1.5.4 failure mode where a phase reported "complete" with a 0-line artifact. `bin/run_state_lib.validate_phase_artifacts()` performs the checks programmatically.
- **Resume capability.** A killed orchestrator re-launched against the same cycle reads `run_state.jsonl`, finds the last unfinished phase, and resumes from there. The policy is "trust artifacts more than events" — if events claim phase complete but the artifact is missing, the phase re-runs.
- **Phase 5 source-edit guardrail.** The Codex bootstrap on 2026-05-02 went off-rails in Phase 5 and edited five source files outside `quality/` before being killed. v1.5.5 mechanizes the rule: `bin/run_state_lib.validate_no_source_edits()` shells out to `git status --porcelain -z` at run end and flags any non-`quality/` path as a violation. `_finalize_iteration()` calls it in production; on violation, the run is downgraded to `aborted`, the violations are recorded in `quality/results/quality-gate.log` and `quality/PROGRESS.md`, and the iteration is non-shippable.
- **Calibration-cycle orchestrator.** [`agents/calibration_orchestrator.md`](agents/calibration_orchestrator.md) documents the spawn-and-resume procedure for autonomous calibration cycles — one Claude Code session reads the prompt, runs the cycle's benchmark list end-to-end, applies lever changes between pre/post-lever runs, and writes the cycle audit + `Lever_Calibration_Log.md` entry. Runs as long-lived but stateless across crashes (state IS the filesystem).
- **Calibration visualizations.** [`bin/visualize_calibration.py`](bin/visualize_calibration.py) produces four artifacts per cycle into `<cycle-dir>/visualizations/`: per-bug × cycle heatmap (the displacement story made visible), lever × benchmark heatmap (recall delta on a red↔green diverging map), recall trajectory chart (per-benchmark line plot with lever-pull annotations), and a Mermaid lever-interaction graph. matplotlib + numpy required (install in the QPB venv).
- **Seven v1.5.4 self-audit defects fixed.** BUG-001 (CopilotRunner now transports the prompt via stdin instead of argv — silent failure for prompts > ARG_MAX); BUG-002 (`progress_monitor` opens transcripts in binary mode and keeps every offset in bytes — UTF-8 multi-byte content no longer desyncs the monitor); BUG-003 (`_printed_headers` set guarded by a lock); BUG-004 (Claude agent's skill-resolution order corrected to match `bin/run_playbook.py:SKILL_FALLBACK_GUIDE`); BUG-005 (every README invocation example uses the package-module form `python3 -m bin.run_playbook`, since the runner exits `EX_USAGE=64` on script-style invocation); BUG-006 (every operator-facing surface — SKILL.md, agents/, references/, runner WARN messages — routes operators to `reference_docs/` instead of `docs_gathered/`); BUG-007 (`bin/quality_playbook.py` help text matches the actual `archive_lib.ARCHIVE_DIRNAME`). Each landed with a regression test under `bin/tests/`.
- **Pre-existing `test_regression_replay` failures resolved.** A new `**Citation:**` field regex extends `bin/regression_replay.py`'s parser to recognize chi-1.5.1's bold-key file-citation form (the v1.5-era variant — without it, every chi-1.5.1 record's `match_key` collapsed to None). The four fixture-count assertions now derive their expected counts from the actual fixture files at runtime so future archive growth doesn't re-stale the tests. Suite goes from 980 tests / 4 failures (inherited from v1.5.4) to 1017 tests / 0 failures.

### What's new in v1.5.4 (Part 1: Classification Redesign)

- **AI-driven file role tagging replaces the v1.5.3 mechanical Code/Skill/Hybrid classifier.** Phase 1 exploration produces `quality/exploration_role_map.json` with one record per in-scope file plus an aggregate breakdown (`skill_share`, `code_share`, `tool_share`, `other_share`). Each file is tagged by content (skill-prose, skill-reference, skill-tool, code, test, docs, config, fixture, formal-spec, playbook-output) — the LOC-pollution failure mode the v1.5.3 heuristic suffered when a target's `quality/` subtree from a prior run inflated its apparent code surface cannot recur, because prior-run artifacts tag as `playbook-output` and bucket into `other_share` rather than `code_share`. Design at [`docs/design/QPB_v1.5.4_Design.md`](docs/design/QPB_v1.5.4_Design.md) Part 1.
- **Pipeline activation reads the role map.** The four-pass skill-derivation pipeline activates iff `has_skill_prose(role_map)`; the code-review pipeline (Phase 3) activates iff `has_code(role_map)`; the prose-to-code LLM divergence check activates iff `has_skill_tools(role_map)`. Empty-side cases no-op cleanly. Both pipelines run together when both predicates are True ("always-Hybrid downstream" — the Code/Skill/Hybrid trichotomy is gone). Pass A's section enumeration walks exactly the role-map-tagged skill-prose / skill-reference files, so targets like `pdf-1.5.3` whose skill surface lives outside `references/` (FORMS.md, REFERENCE.md at the repo root) are enumerated correctly.
- **Backward compatibility for pre-iteration targets.** Targets that pre-date the v1.5.4 role-tagging architecture preserve v1.5.3 code-review behavior — Phase 3 runs as before when `quality/exploration_role_map.json` is absent. The four-pass skill-derivation pipeline and prose-to-code divergence checks require a Phase 1 role map to run; they no-op cleanly when it's missing rather than failing the run. The classifier at `bin/classify_project.py` survives as a debug utility.
- **INDEX.md schema versioning.** New runs emit `schema_version: "2.0"` with a `target_role_breakdown` field (the breakdown subtree of the role map). Legacy archives carrying `schema_version: "1.0"` (or no schema_version) with `target_project_type` are accepted with a single WARN; future schemas (>2.0) refuse with an explicit "newer than supported" error rather than silently misrouting. See `schemas.md` §11.
- **Where to look.** `bin/role_map.py` is the canonical schema + helpers (validator, breakdown calculator, activation predicates, legacy-project-type derivation for pass_c's disposition table). The Phase 1 prompt's role taxonomy is sourced from `bin/role_map.ROLE_DESCRIPTIONS` so adding a role updates the prompt automatically. Cross-check at `bin/tests/test_legacy_project_type_consistency.py` pins the legacy-project-type derivation across the bin/gate boundary.

### What's new in v1.5.4 (Part 2: Calibration Infrastructure)

- **`bin/regression_replay.py` apparatus.** Phase 5 shipped the regression-replay scaffolding: cell.json schema (`metrics/regression_replay/SCHEMA.md`), per-cycle data files at `metrics/regression_replay/<timestamp>/`, recall computation against historical baselines, and a noise-floor threshold for distinguishing real lever-pull effects from run-to-run variance. The script-based orchestrator that was prototyped for autonomous loop execution did not survive Cowork's sandbox runtime constraints (state-file UID locking across ticks, host-only paths, subprocess survival across 45-second sandbox sessions); v1.5.5 replaces the script orchestrator with AI-driven run-state instrumentation — one Claude Code session runs the full cycle end-to-end, instrumenting `quality/run_state.jsonl` and `quality/PROGRESS.md` directly via the file tool layer (no `/tmp` state, no per-tick UID concerns, no background-subprocess lifetime issues).
- **Methodology docs in `ai_context/`.** Two new orientation docs canonicalize the development process built up over v1.5.x: [`ai_context/DEVELOPMENT_PROCESS.md`](ai_context/DEVELOPMENT_PROCESS.md) (mechanical procedures + rationale for the SDLC actually in force across QPB releases), and [`ai_context/CALIBRATION_PROTOCOL.md`](ai_context/CALIBRATION_PROTOCOL.md) (the 12-step lever-pull workflow with Mode 1 autonomous and Mode 2 operator-in-loop variants, pre-flight checks, failure-mode table). Both are session-start reading for any Cowork or Claude Code session that touches QPB development.
- **`docs/process/Lever_Calibration_Log.md`.** Per-cycle record of QPB calibration cycles. Each entry follows the cell.json schema's calibration-log entry template — symptom, diagnosis, lever pulled, before/after recall, cross-benchmark check, verdict, audit-trail location.

### What's new in v1.5.4 (Part 3: First Calibration Cycle — Pattern 7)

- **Pattern 7 — Composition and Mount-Context Awareness** added to [`references/exploration_patterns.md`](references/exploration_patterns.md). A new bug-finding lens directing Phase 1 to enumerate, for each function or component that reads or writes state that *can be canonical-vs-raw under composition*, whether it correctly handles being composed inside a parent context. Direction-agnostic (read-side and write-side defects), 5 cross-domain examples (HTTP routing, transaction context, logging contextvars, locale-sensitive comparison, authorization scope), a 4-bullet seam list, a budget cap (3-5 highest-impact composition seams per pass), and a Pattern 4 disambiguation rule. Companion edit at `SKILL.md` lines 501 and 565 flips "six bug-finding patterns" / "all six analysis patterns" to seven — without these, Phase 1 walks patterns 1-6 and silently neuters Pattern 7. Cycle Finding C-3 captured this dependency-tracing class for future protocol revision.
- **Empirical evidence for Pattern 7 (with caveats — read carefully).** Pattern 7's evidence base is one clean before-and-after measurement plus three post-only measurements:
  - **chi-1.3.45 (clean before/after):** recall improved from 4/10 (40%) to 6/10 (60%). +0.20 measured delta, well above the 0.05 noise floor — real signal. The argument-based projection from the Pattern 7 walkthrough was +0.40; the actual delta came in at half that, with two displacement regressions (PathRewrite and AllowContentEncoding bugs that v1.5.3 caught are missed by v1.5.4 — Pattern 7 appears to redirect attention budget away from them). v1.5.5's first calibration cycle will tune the levers to recover the displacement losses while preserving Pattern 7's wins.
  - **chi-1.5.1, virtio-1.5.1, express-1.3.50:** post-Pattern-7 BUGS.md captured (16, 10, 9 bugs respectively). Pre-Pattern-7 baselines were not measured on these targets — the autonomous loop architecture that was supposed to run them did not survive Cowork's sandbox runtime, which scoped v1.5.5's design (autonomous loop, properly engineered, is v1.5.5's headline feature). Cross-benchmark validation for Pattern 7 is partial.
  - **chi-1.3.45 and chi-1.5.1 are the same chi Go source code.** Byte-identical Go files; the QPB-side metadata differs (`.github/skills/`, `AGENTS.md`) and the historical baselines differ (10 vs. 9 bugs tracked from prior QPB versions), but the application under test is the same. Cycle reports listing four benchmarks should be read as three distinct codebases (chi, virtio, express) with chi appearing twice against different historical baselines.
- **Net assessment.** v1.5.4 is at least as good as v1.5.3 on the headline skill-as-code dimension (4× the skill-divergence findings on the pdf wide-test) and net-positive on Pattern 7's chi target. Cross-benchmark Pattern 7 evidence is partial pending v1.5.5's autonomous loop. The Pattern 7 displacement asterisk (recovering PathRewrite + AllowContentEncoding) is the natural first test case for v1.5.5's automated lever-tuning loop.

### What's new in v1.5.3

- **Skill-as-code feature complete.** v1.5.3 extends the v1.5.0 divergence model to AI-skill targets — projects where SKILL.md prose IS the spec (no separate implementation). The originating evidence was the **2026-04-19 Haiku demonstration**: claude-haiku-4-5-20251001 generated a 2,129-line REQUIREMENTS.md against QPB's own SKILL.md from a simple two-turn interaction, demonstrating that earlier QPB releases were leaving substantial skill-prose coverage on the table because the heuristic pipeline was tuned for code projects.
- **Phase 0 project-type classifier.** `bin/classify_project.py` classifies every target as **Code**, **Skill**, or **Hybrid** based on a SKILL.md-prose-vs-code-LOC ratio with explicit override hooks for Council triage. Code targets continue through the v1.5.0 divergence pipeline unchanged; Skill / Hybrid targets get the new four-pass derivation pipeline. Council override workflow at [`docs/design/QPB_v1.5.3_Phase4_Council_Override_Workflow.md`](docs/design/QPB_v1.5.3_Phase4_Council_Override_Workflow.md).
- **Four-pass generate-then-verify skill-derivation pipeline.** Pass A (naive coverage, section-iterative) reads SKILL.md + every `references/*.md` file with high-recall LLM extraction. Pass B (mechanical citation extraction with token-overlap pre-filter) cuts the O(n×m) similarity match by ~93× via a Jaccard pre-filter (Round 6 follow-up, applied at v1.5.3 to keep cross-target wall-clock tractable). Pass C (formal REQ + UC production) applies the v1.5.3 disposition table with project-type-aware behavioral routing. Pass D (coverage audit + Council inbox) emits per-section accounting + a structured triage queue.
- **Skill-divergence taxonomy: internal-prose, prose-to-code, execution.** `BUG.divergence_type` extends to four values per `schemas.md` §3.8. Phase 4's detection machinery covers all three skill-divergence categories with a precision-tuned pipeline (four-prong filter for internal-prose, Tier-1-mechanical + Tier-2-LLM split for prose-to-code, archived-gate-result aggregation for execution). The detection ships under `bin/skill_derivation/divergence_*.py`.
- **Skill-project gate enforcement.** Four new gate checks in `quality_gate.py` (`check_skill_section_req_coverage`, `check_reference_file_req_coverage`, `check_hybrid_cross_cutting_reqs`, `check_project_type_consistency`) verify Skill/Hybrid invariants. Code projects SKIP the skill-specific checks rather than failing on them — the v1.5.3 surface is additive against Code-project gates.
- **Curated REQUIREMENTS.md bootstrap.** v1.5.3's self-audit produces a curated REQUIREMENTS.md with **comparable coverage** to the Haiku reference (~65 unique REQ definitions in the published Haiku artifact; v1.5.3's curated output renders at 171 REQs across 171 sections, sub-agent spot-check folded into the bootstrap commit). The curation algorithm groups by section, dedupes via Jaccard at 0.6 threshold, and caps at K REQs per partition. See `previous_runs/v1.5.3/REQUIREMENTS.md`.
- **Cross-target validation: 5 code regression + QPB Hybrid + 3 pure skills.** Phase 5 captured pre-v1.5.3 BUGS.md snapshots for chi-1.5.1, virtio-1.5.1, express-1.5.1, cobra-1.3.46, and ran v1.5.3 against three pure-skill targets (anthropic-skills/skills/skill-creator, pdf, claude-api). All three pure-skill cells classify as Skill, run cleanly through Phase 3 + Phase 4, and produce zero false-positive divergences after the Stage 1 precision tuning. The full code-target playbook regression sweep + cross-model second backend (opus) are deferred to a v1.5.3.1 patch.
- **Backward compatibility verified.** `python3 -m bin.classify_project --benchmark` returns `## Overall: PASS` for all 6 cells (5 code + QPB). Phase 4's skill-specific checks SKIP cleanly on Code projects; no `bin/run_playbook.py` changes shipped in v1.5.3.

Originating evidence and the full bootstrap archive (1369 formal REQs + 17 UCs + 11 internal-prose divergences + 4 LLM-judged prose-to-code divergences + 8 partition-density warnings + the curated REQUIREMENTS.md) live under `previous_runs/v1.5.3/`. Phase summaries: `quality/phase3/PHASE3B_SUMMARY.md`, `PHASE4_SUMMARY.md`, `PHASE5_SUMMARY.md`.

### What's new in v1.5.2

- **Two full Council-of-Three reviews cleared the release.** v1.5.2 went through two nine-panelist nested-panel reviews — Round 7 against the C13.6–C13.9 implementation surface, Round 8 against the C13.10 release-prep fixes. Round 8 was 8/9 ship + 1 block on a structural test-discipline issue (logged for v1.5.3). Synthesis docs at `Quality Playbook/Reviews/QPB_v1.5.2_Council_Round{7,8}_Synthesis.md` in the workspace.
- **Orchestrator-side authoritative finalization (C13.9).** A new `_finalize_iteration` helper in `bin/run_playbook.py` runs `quality_gate.py` as a subprocess after each iteration, captures real gate output to `quality/results/quality-gate.log`, and writes a structured block to `PROGRESS.md` with the verdict mapped into INDEX.md's `gate_verdict` field. This closes the v1.5.1 failure mode where the orchestrator's success path took the LLM's word for finalization rather than running the gate itself, producing stale `quality-gate.log` files (chi: 13 vs actual 15 bugs after parity) and silent half-state PROGRESS.md.
- **Cardinality gate hardening (C13.8).** Three Round 6 findings closed with regression tests: `_EVIDENCE_RE` rejects absolute paths and zero-line/zero-range citations; the `present` boolean field is strict-type-checked (no string `"true"` or integer `1` slipping through); `_parse_tier_marker` distinguishes body-prose mentions of `qpb-tier` from misplaced markers, so a doc that says "this file uses qpb-tier markers" no longer fails ingest.
- **Citation verifier hardening (C13.6).** `bin/citation_verifier.py` adds the `reference_docs/cite/` extension check, tier marker semantics, downgrade-record skip handling, and `present:true` evidence enforcement. Citation-stale detection now runs end-to-end: producer writes the document hash, consumer reads it, mismatches are caught when source files change post-ingest.
- **Schema contract fix — `document_sha256` (C13.10 Finding D).** `bin/reference_docs_ingest.py` now writes `document_sha256` matching the schema. Previously the producer wrote `sha256` while the gate read `document_sha256`, silently disabling the stale-citation invariant.
- **Phase 6 verdict-mapping guard (C13.10 Finding B).** A `fail` finalizer status no longer demotes to `partial` just because the gate log's last line happens to contain the substring "warn". Definite gate failures are now correctly recorded as `fail` in INDEX.
- **CLI parsing fix — `--flag=value` form (C13.10 Finding F).** `_mark_iterations_explicit` now handles argparse's combined-token form (`--strategy=adversarial`), not just the split-token form (`--strategy adversarial`). Users running with `=` syntax no longer silently fall through to the zero-gain early-stop default.
- **SKILL.md version stamps consistent (C13.10 Finding E).** All inline version references in SKILL.md updated to v1.5.2; a CI guard at `bin/tests/test_run_playbook.py:test_skill_version_matches_release_constant` fails loudly if a future release-prep misses the bump.
- **New orientation docs.** Three companion files now describe how the playbook is itself maintained: [`ai_context/IMPROVEMENT_LOOP.md`](ai_context/IMPROVEMENT_LOOP.md) (canonical methodology — PDCA loop, verification dimensions vs improvement levers, regression replay), [`ai_context/TOOLKIT_TEST_PROTOCOL.md`](ai_context/TOOLKIT_TEST_PROTOCOL.md) (release-gate review for orientation docs via 14 reader personas with PASS/DOC GAP/DOC WRONG/PANELIST DRIFT rubric), and a "How we improve the playbook" section in this README.
- **Honest statistical-control framing.** IMPROVEMENT_LOOP.md commits to a "moving toward statistical control" framing — instrumented and trend-aware, not yet under formal SPC. Cross-repo analysis of 197 BUGS.md files across 39 QPB versions confirmed within-version variance is large (chi-1.5.1: 9 vs 15 bugs across N=2 replicates, ~50% of mean), supporting conservative public-facing language: per-version trends are recorded, but adjacent-release comparisons of ±2 bugs should not be interpreted as real movement.
- **Submit-upstream workflow guidance (TOOLKIT.md).** New section explains the workflow for adopters who want to submit findings as upstream PRs: tier triage (standout / confirmed / probable / candidate), writeup-as-PR-body, regression-test patch portability, honest attribution framing ("AI-assisted" not "AI generated"), and defect-class consolidation (one consolidated PR vs N individual PRs for the same root-cause defect family). New Personas 14 (PR-submitter walkthrough) and 17 (defect-class consolidation) added to the Toolkit Test Protocol active set.
- **C13.11 cleanup pass queued for v1.5.3.** Six non-blocking hardening items surfaced in Round 8 are documented in IMPROVEMENT_LOOP.md for cleanup as a single commit early in v1.5.3 (centralize `RELEASE_VERSION` constant, extend version-stamp test to `detect_repo_skill_version()`, audit comment for `_mark_iterations_explicit`, mutation-integration test for citation_stale, sys.path cleanup, Phase 6 verdict matrix completion).

### What's new in v1.5.1

- **Phase 5 writeup hardening.** `bin/run_playbook.py::phase5_prompt()` now carries a MANDATORY HYDRATION STEP with a BUGS.md → writeup field map, a worked BUG-004 example, and a per-writeup confirmation checklist that prohibits empty backticks, empty diff fences, and angle-bracket placeholders. This closes the Phase 5 failure mode observed on `bus-tracker-1.5.0`, where the playbook produced skeletal writeups that passed the legacy gate despite having no file paths, no line ranges, no inline diffs, and no regression-test references.
- **Quality-gate writeup hydration checks.** `check_writeups` in `.github/skills/quality_gate/quality_gate.py` now fails when any writeup contains one of five template-sentinel strings (the stub language from `phase5_prompt()`'s pre-hydration template) or when a ` ```diff ` fence is present but contains no `+` / `-` lines other than file headers. Stub writeups can no longer slip past the gate by leaving template scaffolding intact.
- **Case-insensitive diff fence detection.** The hydration gate recognises ` ```diff `, ` ```Diff `, and ` ```DIFF ` uniformly via `_WRITEUP_DIFF_BLOCK_RE`, so inline-diff presence and content checks can't disagree on whether a fence exists. Previously a writeup with a mixed-case fence would trip a confusing "no inline fix diffs" FAIL despite containing a visible unified diff.
- **Quality-gate tests.** New unit-test coverage for sentinel detection and empty-diff-fence detection lands alongside the gate changes, extending the existing quality-gate test suite.

### What's new in v1.4.6

- **27 bugs fixed from the v1.4.5 bootstrap self-audit.** The Opus self-audit over v1.4.5 baseline + four iteration strategies (gap, unfiltered, parity, adversarial) confirmed 27 real defects spanning version parsers, phase entry gates, archive atomicity, runner reliability, quality-gate validation, prompt portability, and orchestrator bootstrap. All 27 shipped as fixes with passing regression tests; recheck reports 27/27 FIXED. Shipped in seven thematic commits. Highlights: the Phase 2 gate now FAILs below 120 lines instead of WARNing at 80 (matching SKILL.md §Phase 1 completion gate); the Phase 3 gate checks all nine Phase 2 artifacts instead of four; the Phase 5 gate enforces SKILL.md's hard-stop (`*triage*` + `*auditor*` files + Phase 4 `[x]`); `archive_previous_run` stages into a `.partial` subfolder under the runs archive and then atomically renames, preserving `control_prompts/` content instead of deleting it; `cleanup_repo` adds `AGENTS.md` to the protected-path set; child-process exit codes propagate through `run_one_phase` / `run_one_singlepass`; missing `docs_gathered/` WARNs and continues with code-only analysis instead of blocking; runner prompts now advertise all four documented install paths via a new `SKILL_FALLBACK_GUIDE` constant; `check_run_metadata` and `_check_exploration_sections` plug two long-standing gate gaps; `validate_iso_date` accepts ISO 8601 datetimes; `_parse_porcelain_path` unwraps Git's quoted paths; `detect_project_language` skips nested benchmark fixture repos. Full per-bug detail in `quality/results/recheck-summary.md`.
- **Bootstrap artifacts tracked in git.** The `quality/` tree — including archived prior runs under `quality/runs/` and per-phase prompt output under `quality/control_prompts/` — is in version control as project history. Earlier it was untracked to avoid `cleanup_repo`'s `git checkout .` wiping it; now `cleanup_repo` protects `quality/` explicitly, so the tree can be tracked without risk. Future iterations can diff against it. (Pre-v1.5.1 releases used root-level `previous_runs/` and `control_prompts/` directories; v1.5.1's `bin/migrate_v1_5_0_layout.py` moves those into `quality/` as part of the consolidated layout.)

### What's new in v1.4.5

- **Python runner with a path-based interface.** `bin/run_playbook.py` treats every positional argument as a directory path (relative or absolute) and defaults to the current directory when none are given. No more short-name resolution, no hardcoded `repos/` lookups — the runner works against any project you point it at. A narrow version-append fallback kicks in only for bare names (no path separators): if `chi` isn't a directory, the runner retries `chi-<skill_version>` once, using the `version:` line from `SKILL.md`. Log files live next to each target (`{parent}/{target-name}-playbook-{timestamp}.log`). Missing SKILL.md is a warning, not a fatal error, so first-time installs aren't blocked. 36 stdlib-only unit tests at release (grew to 92 with v1.4.6 regression coverage).
- **Python gate is the sole mechanical gate.** `quality_gate.sh` has been retired. `quality_gate.py` now handles JSON with `json.load` instead of grep-style parsing and lives at `.github/skills/quality_gate/` as a proper package with a 108-test unit-test suite. A stable symlink at `.github/skills/quality_gate.py` preserves the previous invocation path.
- **Benchmark set reduced to four targets** — bootstrap, chi, cobra, virtio — so full validation loops finish in a reasonable window. Bootstrap always runs last because fixes from the other three need to land before the playbook audits itself.
- **Rate limit warning added.** The README and runner docs now call out that running many targets in parallel with single-prompt mode can trigger multi-day Copilot cooldowns; `--phase all` with `--sequential` is the recommended mode.

### What's new in v1.4.4

- **Orchestrator hardening — "you are the orchestrator" architecture.** Motivated by failures on the casbin run, the orchestrator agents now explicitly forbid three failure modes: single-context collapse (running all six phases in one context window), `claude -p` subprocess spawning (forking new CLI sessions instead of using the Agent tool), and nested Agent-tool stripping (sub-agents trying to spawn their own sub-agents, which Claude Code silently strips). The session reading the agent file IS the orchestrator — it spawns one sub-agent per phase and nothing else.
- **Shared orchestrator protocol.** The hardening rules now live in `references/orchestrator_protocol.md` and are imported by both `agents/quality-playbook-claude.agent.md` and `agents/quality-playbook.agent.md`. Critical rules are also duplicated inline in each agent file so a partial read still enforces them.

### What's new in v1.4.3

- **Challenge gate for false-positive detection.** Before closure, the triage must re-review CRITICAL findings against common-sense reality checks. Motivated by edgequake benchmarking, where six "CRITICAL" tenant-isolation bugs turned out to be documented feature gaps and a seventh was a self-documenting `change-me-in-production` development placeholder. The gate forces that common-sense review to happen before findings are finalized.
- **Functional-test reference reorganized.** Per-language functional-test guidance was split into separate reference files, then re-merged back into a single `references/functional_tests.md` with the import patterns folded in. Easier to maintain, easier for agents to read.

### What's new in v1.4.2

- **25 bug fixes from Sonnet 4.6 bootstrap self-audit.** Fixed nullglob-vulnerable artifact detection across 7 locations (ls-glob replaced with find), severity-prefixed bug ID support (BUG-H1/BUG-M3/BUG-L6), TDD sidecar-to-log cross-validation, recheck-results.json gate validation, Phase 5 entry gate, and integration enum validation. All verified by recheck (25/25 FIXED).
- **Run metadata for multi-model comparison.** Every playbook run creates a timestamped `quality/results/run-YYYY-MM-DDTHH-MM-SS.json` recording model, provider, runner, timestamps, phase timings, bug counts, and gate results. Enables comparison across models and runs.
- **Sonnet recommended as default model.** Sonnet 4.6 found 25 bugs (3 HIGH) at ~3% weekly usage vs Opus's 19 bugs (1 HIGH) at ~8%. More bugs, more HIGH severity, lower cost.

### What's new in v1.4.1

- **Recheck mode.** After fixing bugs, say "recheck" to verify fixes without re-running the full pipeline. Reads the existing BUGS.md, checks each bug against the current source (reverse-applying patches, inspecting cited lines), and outputs machine-readable results to `quality/results/recheck-results.json`. Takes 2-10 minutes instead of 60-90.
- **19 bug fixes from bootstrap self-audit.** Fixed eval injection in quality_gate.sh, bash 3.2 empty array crashes, required artifacts downgraded to WARN, json_key_count false positives, missing artifact checks, and documentation inconsistencies. All verified by recheck (19/19 FIXED).

### What's new in v1.4.0

- **Six-phase architecture with clean context windows.** The playbook now runs as six distinct phases (Explore, Generate, Review, Audit, Reconcile, Verify), each designed to execute in a separate session with its own context window. Phase prompts include exit gates that verify prerequisites before starting and artifact completeness before finishing. This eliminates context-window exhaustion on large codebases and makes each phase independently re-runnable.
- **Phase-by-phase runner with `--phase` flag.** The standard-library Python runner at `bin/run_playbook.py` supports `--phase all` (run phases 1-6 sequentially with gates between each), `--phase 3` (run a single phase), or `--phase 3,4,5` (run a range). Each invocation gets a fresh CLI session, communicating through files on disk.
- **Four iteration strategies.** After the baseline run, the playbook supports four iteration strategies that find different classes of bugs: gap (explore areas the baseline missed), unfiltered (fresh-eyes re-review), parity (parallel path comparison), and adversarial (challenge prior dismissals and recover Type II errors). Iterations consistently add 40-60% more confirmed bugs on top of the baseline.
- **TDD red-green verification for every confirmed bug.** Every bug in BUGS.md must have a regression test patch, a red-phase log proving the test detects the bug on unpatched code, and a green-phase log proving the fix resolves it. The `tdd-results.json` sidecar (schema 1.1) tracks all verdicts with machine-readable fields.
- **Quality gate script.** A mechanical validation script (originally `quality_gate.sh`, now `quality_gate.py`) validates artifact completeness: patch files, writeups, TDD logs, JSON schema conformance, version stamps, and BUGS.md heading format. Runs as the final Phase 6 step.
- **Benchmark results across three codebases.** Validated against Express.js (14 confirmed bugs), Gson (9 confirmed bugs), and Linux virtio (8 confirmed bugs), all with 100% TDD red-phase coverage and 0 gate failures.

### What's new in v1.3.20

- **Mechanical verification artifacts with integrity check (council-recommended).** Before CONTRACTS.md can assert that a dispatch function handles specific constants, you must generate and execute a shell pipeline (awk/grep) that extracts actual case labels from the function body, saving to `quality/mechanical/<function>_cases.txt`. Each extraction command is also appended to `quality/mechanical/verify.sh`, which re-runs the same commands and diffs against saved files. Phase 6 must execute `verify.sh` — if any diff is non-empty, the artifact was tampered with. This integrity check was added because v1.3.19 testing showed the model can execute the correct command but write fabricated output to the file instead of letting the shell redirect capture it.
- **Source-inspection tests must execute (no `run=False`).** Regression tests that verify source structure (string presence, case label existence) are safe, deterministic, and must run. The `run=False` flag is banned for these tests. In v1.3.18, the correct assertion existed but never fired because `run=False` made it inert.
- **Contradiction gate.** Before closure, executed evidence (mechanical artifacts, regression test results, TDD red-phase failures) is compared against prose artifacts (requirements, contracts, triage, BUGS.md). If they contradict, the executed result wins — the prose artifact must be corrected before proceeding.
- **Effective council gating for enumeration checks.** If the council is incomplete (<3/3) and the run includes whitelist/dispatch checks, the audit cannot close those checks without mechanical proof artifacts.
- **Normative vs. descriptive contract language.** Requirements use "must preserve" (normative) unless a mechanical artifact confirms the claim, in which case "preserves" (descriptive) is allowed.
- **Self-contained iterative convergence.** New Phase 0 (Prior Run Analysis) builds a seed list from prior runs' confirmed bugs and mechanically re-checks each seed against the current source tree. After Phase 6, a convergence check compares net-new bugs against the seed list. When net-new bugs = 0, bug discovery has converged. When not converged, the skill automatically archives the current run to `quality/runs/` and re-iterates from Phase 0 — up to 5 iterations by default (configurable). No external scripts needed; the skill handles the full iteration loop internally with context-window awareness. A `run_iterate.sh` script is also available for shell-level orchestration.
- **45 self-check benchmarks** (up from 22).

## Validation

The playbook is validated against the [Quality Playbook Benchmark](https://github.com/andrewstellman/quality-playbook-benchmark): 2,564 real defects from 50 open-source repositories across 14 programming languages. Instead of injecting synthetic faults, we use real historical bugs tied to single fix commits as ground truth.

The key finding: approximately 65% of real defects are detectable by structural code review alone. The remaining 35% are intent violations that require knowing what the code is supposed to do. The playbook's value is in closing that gap.

## Setting up automation scripts

The repository includes a standard-library Python runner at `bin/run_playbook.py`.

Positional arguments are **directory paths** (relative or absolute). Omit positional args to run against the current directory. One convenience applies only to **bare names** (no path separators, no leading `.` / `..` / `~`): if `chi` isn't a directory, the runner retries `chi-<version>` using the `version:` line from `SKILL.md` at the QPB root. Path-like inputs (`./chi`, `/abs/chi`) are taken literally — no fallback.

The runner uses package-relative imports, so always invoke it as a package module (`python3 -m bin.run_playbook`) from the quality-playbook repo root.

```bash
cd /path/to/quality-playbook
python3 -m bin.run_playbook /path/to/my-project                          # single target
python3 -m bin.run_playbook --phase all /path/to/my-project              # phase-by-phase
python3 -m bin.run_playbook ./project1 ./project2                        # multiple targets
python3 -m bin.run_playbook --claude --model opus --phase all ./project1
python3 -m bin.run_playbook --next-iteration --strategy gap ./project1
```

For benchmark use, run from the QPB repo root so the bare-name convenience (`chi` → `chi-<version>`) resolves against `SKILL.md`'s version line:

```bash
cd /path/to/quality-playbook
python3 -m bin.run_playbook --phase all --sequential repos/chi-1.4.6
python3 -m bin.run_playbook chi     # resolves to chi-1.4.6 via SKILL.md version
```

**Rate limit warning:** Running multiple targets in parallel with single-prompt mode (no `--phase`) sends long autonomous prompts that consume large amounts of API quota. In testing, running 8 targets in parallel single-prompt mode triggered a 54-hour Copilot rate limit. Use `--phase all` instead — it runs each phase as a separate, shorter prompt with exit gates between phases. This uses less quota per prompt, produces better results (each phase gets a full context window), and is easier to resume if interrupted. For the same reason, prefer `--sequential` over `--parallel` unless you're confident in your rate limit headroom.

### Usage

```text
usage: run_playbook.py [-h] [--parallel | --sequential]
                       [--claude | --copilot | --codex]
                       [--no-seeds | --with-seeds] [--phase PHASE]
                       [--next-iteration]
                       [--strategy {gap,unfiltered,parity,adversarial,all}]
                       [--model MODEL] [--kill]
                       [targets ...]

Run the Quality Playbook against one or more target directories.

positional arguments:
  targets               Target directories to run against (relative or absolute
                        paths). Defaults to the current directory.

options:
  -h, --help            show this help message and exit
  --parallel            Run all targets concurrently (default).
  --sequential          Run targets one after another.
  --claude              Use claude -p instead of gh copilot.
  --copilot             Use gh copilot (default).
  --codex               Use codex exec --full-auto instead of gh copilot.
  --no-seeds            Skip Phase 0/0b seed injection (default).
  --with-seeds          Allow Phase 0/0b seed injection from prior or sibling runs.
  --phase PHASE         Run specific phase(s): 1-6, all, or comma-separated values like 3,4,5.
  --next-iteration      Iterate on an existing quality/ run.
  --strategy {gap,unfiltered,parity,adversarial,all}
                        Iteration strategy to use with --next-iteration.
  --model MODEL         Runner model override (copilot: gpt-5.4, claude: sonnet/opus/etc, codex: gpt-5-codex/etc).
  --kill                Kill processes from the current or last parallel run.
```

## Repository structure

```
quality-playbook/
├── SKILL.md                 # The skill (main file — full operational instructions)
├── references/              # Protocol and pipeline reference docs
│   ├── challenge_gate.md         # False-positive detection gate for CRITICAL findings
│   ├── constitution.md           # Guidance for drafting the quality constitution
│   ├── defensive_patterns.md     # Forensic inversion of try/except, null guards, fallback paths
│   ├── exploration_patterns.md   # Pattern library for Phase 1 exploration
│   ├── functional_tests.md       # Functional-test generation (all languages, import patterns)
│   ├── iteration.md              # Iteration strategies (gap, unfiltered, parity, adversarial)
│   ├── orchestrator_protocol.md  # Shared hardening rules for orchestrator agents
│   ├── requirements_pipeline.md  # Requirements derivation and post-review reconciliation
│   ├── requirements_refinement.md # Coverage / completeness refinement pass
│   ├── requirements_review.md    # Pre-finalization requirements review
│   ├── review_protocols.md       # Three-pass code review protocol
│   ├── schema_mapping.md         # tdd-results.json / recheck-results.json schema reference
│   ├── spec_audit.md             # Council of Three spec audit protocol
│   └── verification.md           # 45 self-check benchmarks for Phase 6
├── agents/                  # Orchestrator agent files for autonomous runs
│   ├── quality-playbook-claude.agent.md   # Claude Code orchestrator (sub-agent architecture)
│   └── quality-playbook.agent.md          # General-purpose orchestrator
├── bin/                     # Standard-library runner package (Python 3.8+)
│   ├── __init__.py
│   ├── benchmark_lib.py     # Shared logging, cleanup, artifact discovery, and summary helpers
│   ├── run_playbook.py      # Main entry point — positional args are target directories; defaults to cwd
│   └── tests/               # 92 stdlib-only unit tests (python3 -m pytest bin/tests/)
├── .github/skills/          # Installed-copy layout (also used in target repos)
│   ├── quality_gate.py      # Symlink → quality_gate/quality_gate.py (stable invocation path)
│   └── quality_gate/        # Gate script package (sole mechanical gate; bash version retired in v1.4.5)
│       ├── __init__.py
│       ├── quality_gate.py  # Mechanical validation script (14 check sections, 1100+ lines)
│       └── tests/           # 108 stdlib-only unit tests for the gate
├── pytest/                  # Local stdlib-only shim (python3 -m pytest works without installs)
├── ai_context/              # AI-readable context files (orientation docs)
│   ├── TOOLKIT.md           # For users' AI assistants (setup, run, interpret, recheck)
│   ├── DEVELOPMENT_CONTEXT.md  # For maintainers' AI assistants
│   ├── IMPROVEMENT_LOOP.md  # PDCA loop, verification dimensions, improvement levers, regression replay
│   ├── TOOLKIT_TEST_PROTOCOL.md  # Release-gate review for orientation docs (14 reader personas)
│   └── BENCHMARK_PROTOCOL.md  # Benchmark conventions and target-resolution rules
├── AGENTS.md                # AI bootstrap file (repo root)
├── LICENSE.txt              # Apache 2.0
└── quality/                 # Generated quality infrastructure (from running the skill on itself)
    ├── REQUIREMENTS.md     # Behavioral requirements
    ├── QUALITY.md          # Quality constitution
    ├── test_functional.py  # Spec-traced functional tests
    ├── CONTRACTS.md        # Extracted behavioral contracts
    ├── COVERAGE_MATRIX.md  # Contract-to-requirement traceability
    ├── COMPLETENESS_REPORT.md  # Final gate with verdict
    ├── PROGRESS.md         # Phase checkpoint log + bug tracker
    ├── BUGS.md             # Consolidated bug report with spec basis
    ├── RUN_CODE_REVIEW.md  # Three-pass review protocol
    ├── RUN_SPEC_AUDIT.md   # Council of Three audit protocol
    ├── RUN_INTEGRATION_TESTS.md  # Integration test protocol (use-case traced)
    ├── RUN_TDD_TESTS.md    # Red-green TDD verification protocol
    ├── TDD_TRACEABILITY.md # Bug → requirement → spec → test mapping
    ├── test_regression.*   # Regression tests for confirmed bugs
    ├── SEED_CHECKS.md     # Prior-run seed list (continuation mode)
    ├── results/            # TDD results, recheck results, verification logs
    ├── mechanical/         # Shell-extracted verification artifacts + verify.sh
    ├── writeups/           # Per-bug detailed writeups (BUG-NNN.md)
    ├── patches/            # Fix and regression-test patches
    ├── code_reviews/       # Code review output
    └── spec_audits/        # Auditor reports + triage
```

## Example output

The `quality/` directory contains the results of running the playbook against itself. These are real outputs, not samples — every file was generated by the skill analyzing its own repository.

| File | What to look at |
|------|----------------|
| [REQUIREMENTS.md](quality/REQUIREMENTS.md) | Behavioral requirements derived from the skill specification. This is the foundation that drives everything else. |
| [QUALITY.md](quality/QUALITY.md) | Quality constitution defining fitness-to-purpose scenarios and coverage targets for the playbook itself. |
| [test_functional.py](quality/test_functional.py) | Functional tests traced to requirements, written in the project's native language. |
| [CONTRACTS.md](quality/CONTRACTS.md) | Raw behavioral contracts extracted from the codebase before requirement derivation. |
| [COVERAGE_MATRIX.md](quality/COVERAGE_MATRIX.md) | Traceability matrix mapping every contract to the requirement that covers it. |
| [COMPLETENESS_REPORT.md](quality/COMPLETENESS_REPORT.md) | Final gate report with post-reconciliation verdict. |
| [RUN_CODE_REVIEW.md](quality/RUN_CODE_REVIEW.md) | Three-pass code review protocol ready for any AI session to execute. |
| [RUN_SPEC_AUDIT.md](quality/RUN_SPEC_AUDIT.md) | Council of Three spec audit protocol. |
| [RUN_TDD_TESTS.md](quality/RUN_TDD_TESTS.md) | Red-green TDD verification protocol for confirmed bugs. |
| [PROGRESS.md](quality/PROGRESS.md) | Phase-by-phase checkpoint log with cumulative bug tracker — the external memory that prevents findings from being orphaned. |
| [code_reviews/](quality/code_reviews/) | Actual code review output from the three-pass protocol. |
| [spec_audits/](quality/spec_audits/) | Individual auditor reports and triage from the Council of Three. |

## How we improve the playbook

The Quality Playbook is itself a quality-engineered piece of software. Each release goes through a Plan-Do-Check-Act loop with **benchmark recovery against pinned ground truth** as the Check step: a change is hypothesized, implemented, then run against three pinned benchmark repositories (`chi-1.5.1`, `virtio-1.5.1`, `express-1.5.1`) with known v1.4.5 ground-truth bug counts. The release ships only if both verification dimensions hold or improve.

Two pieces of vocabulary hold the loop together:

**Verification dimensions** are what we *measure* on every release. There are two — process compliance (does the run produce the right artifacts?) and outcome recall (does the run actually find the bugs we know are there?). A release must pass both. The most pernicious failure mode is pass-process / fail-recall: gates green, zero real bugs found.

**Improvement levers** are what we *change* to make the playbook better. Each lever is a decoupled surface — a known home in the codebase that can be tuned without affecting the others. The current inventory: exploration breadth/depth (`references/exploration_patterns.md`, `references/iteration.md`), code-derived vs domain-derived requirements (`references/requirements_*.md` plus `bin/citation_verifier.py`), gate strictness (`quality_gate.py`), finalization robustness (`bin/run_playbook.py::_finalize_iteration`), the mechanical-citation extractor (`bin/skill_derivation/citation_search.py`, with the v1.5.3 token-overlap pre-filter), and the four-pass skill-derivation pipeline (`bin/skill_derivation/pass_{a,b,c,d}.py` plus the divergence-detection modules under `bin/skill_derivation/divergence_*.py`).

The methodology that connects the levers to outcome recall is **regression replay**: take a pinned benchmark, roll back to a commit just before a known QPB-* bug was fixed, and run the playbook against that pre-fix commit. If the playbook finds the bug, the levers are sufficient for that class. If it misses the bug, diagnose which lever needs to be pulled, change it, and re-run — verifying both that the bug is now found and that recall on the rest of the benchmark is preserved. This produces a clean, decoupled signal: which lever solves which class of miss, with no cross-contamination.

Full detail — the lever inventory with file mappings, the verification-dimensions framing, the v1.5.4 work items (statistical-control machinery, regression-replay automation, cross-version-harness prose pinning), and the trajectory toward formal statistical process control — lives in [`ai_context/IMPROVEMENT_LOOP.md`](ai_context/IMPROVEMENT_LOOP.md). The orientation-doc release-gate review (the docs analogue of Council-of-Three) lives in [`ai_context/TOOLKIT_TEST_PROTOCOL.md`](ai_context/TOOLKIT_TEST_PROTOCOL.md).

## Context

This project accompanies the O'Reilly Radar article [AI Is Writing Our Code Faster Than We Can Verify It](https://www.oreilly.com/radar/ai-is-writing-our-code-faster-than-we-can-verify-it/), part of a [series on AI-driven development](https://oreillyradar.substack.com/p/the-accidental-orchestrator) by Andrew Stellman. The playbook was built using AI-driven development with [Octobatch](https://github.com/andrewstellman/octobatch), an open-source Python batch LLM orchestrator. This README was coauthored with Claude Cowork.

## License

Apache 2.0.

## Patent notice

Aspects of the methodology described in this repository are the subject of **US Provisional Patent Application No. 64/044,178**, filed April 20, 2026 by Andrew Stellman.

Users of this project are covered by the **Apache License 2.0**, which includes an **express patent grant** in Section 3. That grant is perpetual, worldwide, royalty-free, and irrevocable (except as described in the license), and extends to anyone using, reproducing, modifying, or distributing the Quality Playbook under the terms of the Apache 2.0 license. Nothing in this notice diminishes that grant.

The patent application exists to preserve a defensive priority date; it is not asserted against users, contributors, forks, or derivative works of this project practiced under Apache 2.0.
