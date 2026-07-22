# Quality Playbook

**Version:** 1.6.0 | **Author:** [Andrew Stellman](https://github.com/andrewstellman) | **License:** Apache 2.0

**Find the bugs that code review misses**

Most code review looks at how the code is written. The Quality Playbook looks at what the code is supposed to do, and whether it actually does it.

Here's how Quality Playbook finds bugs in your code. It explores your codebase and works out its behavioral requirements from two sources: the code itself, and your documentation (specs, issues, chat history, post-mortems). Then it runs a three-pass code review and a multi-model spec audit (the Council of Three) against those requirements. The bugs it turns up are the ones that look correct to anyone who doesn't already know the spec:

- a function that silently returns null instead of throwing
- a duplicate-key check that passes when the first value is null
- sanitization that runs after the branch decision it was supposed to guard

It even catches bugs that a thorough adversarial code-review prompt with Claude Opus 4.8 misses. It doesn't stop at finding bugs, though. Along the way it builds the quality infrastructure your project keeps reusing, and every later review cycle runs against it:

- derived requirements
- functional and integration tests
- contracts and a coverage matrix
- the code-review, spec-audit, and TDD verification protocols themselves

*This isn't theoretical. Bugs the Quality Playbook found have been accepted and merged upstream, in Google's [gson](https://github.com/google/gson/pull/3006) and the Linux kernel's [zram](https://github.com/torvalds/linux/commit/2f529e73d72048743b6eaa241da6ac2bcb28099e).*

## Quick start

**Install** into your project's root directory (pick one):

```bash
npx quality-playbook install --into . --ai-tool claude     # from npm, no global install
pip install quality-playbook && quality-playbook install --into . --ai-tool claude   # from pip
git clone https://github.com/andrewstellman/quality-playbook   # or clone and ask your AI to install it
```

Swap `claude` for `cursor`, `copilot`, `continue`, `codex`, `windsurf`, `cline`, or `aider`. (Prerequisite: Python 3.10+ on your `PATH`.)

**Run** by opening your project in your AI coding tool and telling the agent:

> *"Run the Quality Playbook on this project."*

That's it — the agent auto-discovers the installed skill, runs all six phases, and drops the results into a `quality/` folder. Findings start in `quality/BUGS.md`.

<!-- TOKENS: pending benchmark run — replace with real input/output token usage from arunner recall runs, e.g. "A full baseline run against repos X / Y / Z cost N input / M output tokens." Do not invent numbers. -->

## Contents

- [How to install the Quality Playbook](#how-to-install-the-quality-playbook)
- [How to run the Quality Playbook](#how-to-run-the-quality-playbook)
- [Example output](#example-output)
- [Need help? Just ask your AI](#need-help-just-ask-your-ai)
- [Running the playbook](#running-the-playbook)
- [What the playbook produces](#what-the-playbook-produces)
- [How it works](#how-it-works)
- [Want to learn more?](#want-to-learn-more)
- [Recent releases](#recent-releases)
- [Running across many repos with arunner](#running-across-many-repos-with-arunner)
- [Repository structure](#repository-structure)
- [How we improve the playbook](#how-we-improve-the-playbook)
- [Context](#context)
- [License](#license)
- [Patent notice](#patent-notice)

## How to install the Quality Playbook

**The fastest path: install from npm or pip.** From your project's root directory, pick one:

```bash
# From npm — no global install:
npx quality-playbook install --into . --ai-tool <tool>

# From pip / uvx / pipx (Python 3.10+):
uvx quality-playbook install --into . --ai-tool <tool>           # one-shot, no global install
pipx run quality-playbook install --into . --ai-tool <tool>
pip install quality-playbook && quality-playbook install --into . --ai-tool <tool>
```

Where `<tool>` is one of `claude`, `cursor`, `copilot`, `continue`, `codex`, `windsurf`, `cline`, or `aider`. The skill installs into `.<tool>/skills/quality-playbook/` (or `.github/skills/quality-playbook/` for `copilot`). Concrete examples:

```bash
npx quality-playbook install --into . --ai-tool claude       # Claude Code
npx quality-playbook install --into . --ai-tool cursor       # Cursor
npx quality-playbook install --into . --ai-tool copilot      # GitHub Copilot
```

**Alternative: install via the Claude Code plugin marketplace.** If you use Claude Code, you can add QPB as a marketplace plugin — one command to add the marketplace, one command to install:

```
/plugin marketplace add https://github.com/andrewstellman/quality-playbook
/plugin install quality-playbook
```

Use the full `https://` URL — the shorthand `github.com/...` form makes Claude Code attempt an SSH clone, which fails on machines without a GitHub SSH key configured.

After install, the QPB skill is auto-discoverable in any project you open with Claude Code — no `quality-playbook install --into ...` step needed. To update later when a new QPB version ships: `/plugin marketplace update` then re-install.

For local development against an unmerged QPB checkout (e.g., testing a fork), use `--plugin-dir` instead of the marketplace:

```
claude --plugin-dir /path/to/quality-playbook/plugins/quality-playbook
```

The `--plugin-dir` argument takes an absolute path to the plugin directory inside the QPB clone, loading the plugin for that Claude Code session only.

**Alternative: ask your AI coding tool to install it from a clone of this repo.**

1. **Clone this repo** somewhere on your machine — for example, `git clone https://github.com/andrewstellman/quality-playbook ~/quality-playbook`. One clone installs into any number of projects.

2. **Open your target project** in Claude Code, Cursor, GitHub Copilot, Windsurf, Continue, or another AI coding tool.

3. **Ask the AI to install it.** Something like:

   > *"Install the Quality Playbook into this project from `~/quality-playbook`."*

   The agent reads [`AGENTS.md`](AGENTS.md), figures out which install location your tool uses, and runs the installer. Done.

Prefer to install by hand or use the script directly? Ask your AI tool with `TOOLKIT.md` loaded: *"Read TOOLKIT.md. How do I install the skill manually or via the `bin/install_skill.py` script directly?"*

**Prerequisite:** Python 3.10 or later on your `PATH`. QPB's runtime floor was raised from 3.9 to 3.10 in v1.5.7 089i — adopters must have 3.10+ available (the test suite uses 3.10-only features such as `unittest.TestCase.assertNoLogs`). The npm package is a thin shim over the same Python installer, so Python 3.10+ is required even when installing via `npx`.

**The more documentation you give it, the better it finds bugs.** The playbook reads written specs, design docs, GitHub or Jira issues from real users, chat history, and post-mortems — then derives what your code is *supposed* to do from those sources. Without documentation it still runs (from the source tree alone), but bug recall drops materially. Drop everything you have into a `reference_docs/` directory at the project root.

**Gather it in one step.** Copy [`references/DOC_GATHERING_PROMPT.md`](references/DOC_GATHERING_PROMPT.md), open your project in Claude Code, Codex, Copilot, Cursor, Windsurf (or any capable AI tool), paste it in, and run it — it confirms your project, then crawls its docs, issues, and advisories into `reference_docs/` for you.

## How to run the Quality Playbook

Open your project in your AI coding tool (Claude Code, Cursor, GitHub Copilot, Windsurf, Continue, etc.) and tell the agent:

> *"Run the Quality Playbook on this project."*

That one line is all you need — once the skill is installed, the agent auto-discovers it; you don't have to open, read, or point at `SKILL.md` or any other file. The agent runs all six phases — explore, generate requirements + tests + protocols, code review, spec audit, reconcile findings, verify — and drops the results into a `quality/` folder in your project.

A full six-phase run takes a while and uses a lot of tokens. To split it up across sessions (e.g., for daily token-budget management), tell the agent to run a subset:

> *"Run phases 1 to 3 of the Quality Playbook on this project."*

Then later:

> *"Continue the Quality Playbook from phase 4."*

When the run finishes, the `quality/` folder contains:

```
quality/
├── BUGS.md                  ← consolidated bug report with spec basis (start here)
├── REQUIREMENTS.md          ← behavioral requirements derived from your code + docs
├── EXPLORATION.md           ← Phase 1 findings — patterns explored, files tagged
├── QUALITY.md               ← quality constitution for your codebase
├── CONTRACTS.md             ← extracted behavioral contracts
├── COVERAGE_MATRIX.md       ← contract-to-requirement traceability
├── COMPLETENESS_REPORT.md   ← final gate report with post-reconciliation verdict
├── PROGRESS.md              ← phase checkpoint log + cumulative bug tracker
├── test_functional.py       ← functional tests traced to requirements
├── test_regression.py       ← regression tests for confirmed bugs
├── writeups/                ← per-bug detailed writeups with patches (BUG-NNN.md)
├── patches/                 ← fix and regression-test patches
├── code_reviews/            ← three-pass code review output
├── spec_audits/             ← Council of Three auditor reports + triage
└── results/                 ← TDD red/green logs, integration results, gate log
```

Start with `BUGS.md` for the headline findings. Then read `REQUIREMENTS.md` to see what the playbook learned your code is supposed to do — including requirements derived from issues and docs that you may not have realized were there. The gap between what `REQUIREMENTS.md` says and what your code actually does is exactly the bug surface the playbook is built to find.

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

## Need help? Just ask your AI

The rest of this README hits the high points of the playbook — phases, output files, automation flags. But the easiest way to get answers is to skip reading entirely: **download one file, attach it to your favorite AI chatbot, and ask it whatever you want to know.**

The file is [`ai_context/TOOLKIT.md`](https://github.com/andrewstellman/quality-playbook/blob/main/ai_context/TOOLKIT.md). It's a single Markdown document that explains everything about the Quality Playbook in a format designed for AI assistants to read and answer questions from.

Open a chat in whatever AI tool you use — Claude, ChatGPT, Cursor, GitHub Copilot, Gemini — attach `TOOLKIT.md`, and tell it:

> "Read TOOLKIT.md. Now you're an expert in the Quality Playbook."

<a href="https://chatgpt.com/share/69f78fc3-186c-83ea-9be6-70866b88db82"><img src="images/chatgpt-toolkit.png" alt="ChatGPT with TOOLKIT.md attached" width="1000"></a>

Then ask it anything: How do I set this up? What does Phase 3 actually do? How does it find bugs that structural code review misses? What's the difference between gap and adversarial iteration? Why did my run only find one bug? Your AI assistant will walk you through setup, running, interpreting results, and improving your next run.

[Here's what that conversation looks like in ChatGPT](https://chatgpt.com/share/69f78fc3-186c-83ea-9be6-70866b88db82) — it works the same in any other AI tool.

## Running the playbook

The playbook runs in **six phases**, each in its own context window. After each phase, say *"keep going"* to continue. The six phases:

| Phase | Purpose |
|-------|---------|
| 1 — Explore | Read code, tests, config, specs, commit history. Read `reference_docs/` if present. Understand both what the code does AND what it's supposed to do. |
| 2 — Generate | Five-phase pipeline derives behavioral requirements, generates functional tests, code-review protocol, integration tests, spec-audit protocol, TDD protocol, quality constitution. |
| 3 — Code review | Three-pass review: structural, requirement verification, cross-requirement consistency. Each confirmed bug gets a regression test. |
| 4 — Spec audit | Three independent AI models audit the code against requirements (Council of Three). Triage uses verification probes ("is this actually true?") rather than majority vote. |
| 5 — Reconciliation | Every bug from code review + spec audit tracked, regression-tested or explicitly exempted. |
| 6 — Verify | 45 self-check benchmarks validate generated artifacts. Final gate: GATE PASSED / GATE PASSED WITH CLEANUP NEEDED / GATE FAILED. |

After the baseline, **iterations** find more bugs: gap → unfiltered → parity → adversarial. Each strategy explores different classes of bug; running all four typically adds 40-60% on top of the baseline. Say *"Run the next iteration using the gap strategy"* to start.

After fixing bugs, say *"recheck"* — recheck mode verifies fixes against the existing bug report without re-running the full pipeline (2-10 minutes).

For autonomous / CI / runner-specific invocations, see *[Want to learn more?](#want-to-learn-more)* below (specifically `"Read TOOLKIT.md. How do I run the playbook autonomously or in CI?"`) and `agents/quality-playbook.agent.md` for the orchestrator-agent path.

### Rate limits and run budgets

Subscription tiers vary. A typical full baseline (six phases) on a 100K-LoC project is 1-2 hours of wall time and a meaningful chunk of a daily/weekly quota on most providers. The autonomous full-iteration run (six phases + four iteration strategies as separate sub-agents) is 60-180 minutes.

For multi-repo benchmark work, see [`harness_plans/`](harness_plans/) for parallel-pool plan formats and `docs/design/QPB_Test_Harness_*.md` for the harness internals.

### Known limitations

**Phase validator-invocation contracts are prose-enforced** (not mechanically enforced). Phase 1/2/5 require the agent to invoke `validate_phase_artifacts` and quote the verdict line; Phase 6 requires the fresh-context auditor sub-agent. Empirically, codex desktop has been observed reporting PASS while skipping the validator (2026-05-18 Phase 1 self-bootstrap). Operators reviewing phase verdicts should check for verbatim `RESULT: VALIDATION PASSED (phase N)` lines or fresh-context framing in the Phase 6 auditor verdict.

Structural enforcement is tracked for v1.6.x — see [`docs/design/QPB_v1.6.x_Phase6_Structural_Enforcement_Proposal.md`](docs/design/QPB_v1.6.x_Phase6_Structural_Enforcement_Proposal.md).

## What the playbook produces

The playbook generates these files:

| Artifact | Location | What it does |
|----------|----------|-------------|
| `REQUIREMENTS.md` | `quality/` | Behavioral requirements derived from code, docs, and community sources via a five-phase pipeline. This is the foundation -- without requirements, review is limited to structural bugs. |
| `QUALITY.md` | `quality/` | Quality constitution defining what "correct" means for this specific project, with fitness-to-purpose scenarios and coverage theater prevention. |
| `test_functional.*` | `quality/` | Functional tests in the project's native language, traced to requirements rather than generated from source code. |
| `RUN_CODE_REVIEW.md` | `quality/` | Three-pass protocol: structural review, requirement verification, cross-requirement consistency. Each pass finds bugs the others can't. |
| `RUN_SPEC_AUDIT.md` | `quality/` | Council of Three: three independent AI models audit the code against requirements. Different models have different blind spots, and the triage uses verification probes — targeted checks asking "is this actually true?" — rather than majority vote. |
| `RUN_INTEGRATION_TESTS.md` | `quality/` | End-to-end test protocol grounded in use cases, with a traceability column mapping each test to the user outcome it validates. |
| `RUN_TDD_TESTS.md` | `quality/` | Red-green TDD verification protocol: for each confirmed bug, prove the regression test fails on unpatched code and passes with the fix. |
| `BUGS.md` | `quality/` | Consolidated bug report with spec basis, severity, reproduction steps, and patch references for every confirmed finding. |
| `AGENTS.md` | project root | Bootstrap file so every future AI session inherits the full quality infrastructure. |

## How it works

The playbook's value comes from **requirement derivation**. AI code reviewers are bottlenecked by the same thing human reviewers are: if you don't know what the code is *supposed* to do, you can only find structural issues. The playbook's main job is figuring out intent — from your code, your specs, your issue tracker, your design docs, your chat history — and then using that intent to drive every downstream artifact.

The six phases are summarized in the *[Running the playbook](#running-the-playbook)* table above. For deeper detail on any phase:

> *"Read TOOLKIT.md. Walk me through Phase N in detail. What's the input, what's the output, what can go wrong?"*

The final gate produces one of **three verdicts**: `GATE PASSED` (review complete, nothing to do), `GATE PASSED WITH CLEANUP NEEDED` (bug findings are real and stand on their own; only the audit trail is incomplete), or `GATE FAILED` (substantive problem — review didn't complete, specs missing, or verdict was fabricated). The split lets you distinguish *"your code is broken in N ways"* from *"your audit trail is incomplete in N ways"*.

### Why documentation matters

Adding community documentation to the pipeline produces measurably better results. In a controlled experiment across multiple repositories, documentation-enriched runs found more bugs, different bugs, and higher-confidence bugs than code-only baselines. The documentation gives auditors spec language to check against, turning *"this code looks odd"* into *"this code contradicts the documented behavior"*.

## Want to learn more?

Most adopter questions are answered by loading `TOOLKIT.md` into your AI tool and asking — that's the design intent of `Need help? Just ask your AI` above. Here are example prompts for common moments:

**Setting up documentation:**

> *"Read TOOLKIT.md. What documentation should I provide and how do I gather it? What's the difference between top-level `reference_docs/` and `reference_docs/cite/`? What about projects with no documentation?"*

**Understanding what each phase does:**

> *"Read TOOLKIT.md. What does Phase 3 actually do? How does it find bugs that structural code review misses? How is it different from Phase 4?"*

**Choosing iteration strategies:**

> *"Read TOOLKIT.md. What are the four iteration strategies (gap, unfiltered, parity, adversarial)? When should I use each? What's the right order?"*

**Running autonomously or in CI:**

> *"Read TOOLKIT.md. How do I run the playbook autonomously across multiple iterations without babysitting it? What about CI?"*

**Interpreting low bug counts:**

> *"Read TOOLKIT.md. My run only found one bug. Is my code that clean, or did the playbook miss something? How do I tell?"*

**The Council of Three:**

> *"Read TOOLKIT.md. What is the Council of Three? Why three models? How does the triage handle disagreements?"*

**Manual install fallback:**

> *"Read TOOLKIT.md. The automatic install didn't work. How do I copy the skill files manually for Claude Code, Cursor, GitHub Copilot, Continue, Windsurf, Codex, Cline, or Aider?"*

**Tuning recall:**

> *"Read TOOLKIT.md. My playbook missed a bug I know is in the code. What can I tune on the next run?"*

**Understanding the gate verdicts:**

> *"Read TOOLKIT.md. What's the difference between GATE PASSED, GATE PASSED WITH CLEANUP NEEDED, and GATE FAILED?"*

If `TOOLKIT.md` doesn't answer your question, file an issue at https://github.com/andrewstellman/quality-playbook/issues.

## Recent releases

Per-release detail lives in [`CHANGELOG.md`](CHANGELOG.md). Highlights:

- **v1.5.10** — Repo-hygiene release. Canonical `SKILL.md` + `references/` moved back to the repo root as the single source of truth (in-tree skill locations are symlinks); `SKILL.md` trimmed, with per-phase detail lazy-loaded from `references/*.md`; committed run-output and orphaned partial copies removed from tracking. A clean base for the upcoming security work.
- **v1.5.8** — Distribution channels: published to pip (PyPI), npm, and the Claude Code plugin marketplace. Publish scripts with affirmation gates (`--dry-run` / `--publish`, `--otp` for 2FA, automated awesome-copilot submission). Repository restructured to Claude Code's standard self-hosted plugin marketplace layout (`plugins/quality-playbook/`).
- **v1.5.7** — Channel scaffolding (pip / uvx / pipx / npx). Phase-aware bundling. Council-of-Three review protocol formalized as load-bearing methodology. Worker self-Council pattern (parallel sub-agent reviewers via `Task` tool).
- **v1.5.6** — Improvement-loop methodology formalized. Two-half development arc declared: v1.5.x = QC infrastructure (find bugs, validate skill prose), v1.6+ = QI built on it (statistical control, multi-operator workflows).

Full chronological list (v1.3.20 → present): see [`CHANGELOG.md`](CHANGELOG.md).

## Running across many repos with arunner

For multi-repo runs, benchmark suites, or unattended batch work, drive the playbook with [**arunner**](https://github.com/andrewstellman/arunner) — a stdlib-only batch orchestrator for agentic coding systems. You point it at a list of jobs (run the playbook across these ten repos, audit these branches), and it runs them in a pool, watches each job's heartbeat, and leaves a complete record on disk. There's no server, daemon, or API key beyond your existing agent session, and crash recovery is "run one tick" — close the window or sleep the machine and it resumes exactly where it left off.

arunner is vendor-neutral by construction: the orchestration engine is plain Python, and a job is *anything that appends JSON lines to a file* — so a QPB run, a shell script, or a CI job all qualify. That makes it the recommended path for running QPB across a repo set without babysitting each one.

See the [arunner repository](https://github.com/andrewstellman/arunner) for the worker contract, plan formats, and host support table. (QPB-native multi-phase orchestration through arunner is in active development; until those job formats land, drive QPB through arunner as a shell/agent job, or run phase-by-phase per the *[How to run the Quality Playbook](#how-to-run-the-quality-playbook)* section above.)

## Repository structure

As of v1.5.10, the canonical `SKILL.md` and its `references/` directory live at the **repo root** as the single source of truth; the in-tree plugin skill locations are symlinks back to them. QPB still uses Claude Code's standard self-hosted marketplace layout: `.claude-plugin/marketplace.json` points at the plugin under `plugins/quality-playbook/`. The pip/npm publish channels stage real files from the root skill source (symlinks dereferenced).

```
quality-playbook/
├── SKILL.md                 # The skill — canonical source of truth (full operational instructions)
├── references/              # Protocol + per-phase pipeline reference docs (lazy-loaded per phase)
│   ├── DOC_GATHERING_PROMPT.md
│   ├── exploration_patterns.md
│   ├── requirements_pipeline.md
│   ├── review_protocols.md
│   ├── spec_audit.md
│   ├── verification.md
│   ├── phase1_exploration_guide.md
│   ├── phase2_generation_guide.md
│   ├── phase5_reconciliation_guide.md
│   ├── phase6_verify_guide.md
│   ├── phase7_guide.md
│   ├── recheck_mode.md
│   ├── run_state_schema.md
│   └── ... (other reference docs)
├── schemas.md               # Artifact schema definitions
├── AGENTS.md                # AI bootstrap file (repo root)
├── .claude-plugin/          # ROOT-only: marketplace catalog
│   └── marketplace.json     # Self-hosted marketplace entry (source: ./plugins/quality-playbook)
├── plugins/                 # Plugin tree (standard self-hosted marketplace layout)
│   └── quality-playbook/    # The plugin itself
│       ├── .claude-plugin/
│       │   └── plugin.json  # Plugin metadata (name, description, version, author)
│       └── skills/
│           └── quality-playbook/
│               ├── SKILL.md      # Symlink → repo-root SKILL.md
│               ├── references/   # Symlink → repo-root references/
│               ├── phase_prompts/   # Per-phase agent prompts (Mode A + Mode B)
│               ├── agents/          # Orchestrator agent files for autonomous runs
│               ├── ai_context/      # Adopter-facing AI context (TOOLKIT.md symlink)
│               └── scripts/         # Bundled scripts (quality_gate.py, install_skill.py, ...)
├── bin/                     # Repo-level runner + build scripts (Python 3.10+)
│   ├── run_playbook.py      # Mode B runner (positional args are target directories)
│   ├── build_channel_package.py  # Stages the pip/npm bundle (dereferences symlinks)
│   ├── publish_pip.py       # Pip publish path
│   ├── publish_npm.py       # Npm publish path
│   ├── install_skill.py     # Thin shim — delegates to the plugin's scripts/install_skill.py
│   └── tests/               # stdlib-only unit tests (python3 -m pytest bin/tests/)
├── pytest/                  # Local stdlib-only shim (python3 -m pytest works without installs)
├── ai_context/              # Maintainer orientation docs + adopter-facing TOOLKIT.md
│   ├── DEVELOPMENT_CONTEXT.md
│   ├── DEVELOPMENT_PROCESS.md
│   ├── IMPROVEMENT_LOOP.md
│   ├── TOOLKIT_TEST_PROTOCOL.md
│   ├── BENCHMARK_PROTOCOL.md
│   └── TOOLKIT.md           # Adopter-facing AI context; symlinked into the skill bundle
├── harness_plans/           # Parallel-pool benchmark plan formats
├── runner/                  # arunner run directories (per-version harness state)
├── docs/                    # Design docs, implementation plans, proposals
├── reviews/                 # Council-of-Three review artifacts
├── metrics/                 # Cross-version benchmark metrics
├── images/                  # README images
├── reference_docs/          # Documentation QPB reads to derive requirements
├── scripts/                 # Repo-level helper scripts
├── quality_playbook_cli/    # CLI package
├── quality/                 # Generated quality infrastructure (from running the skill on itself)
├── pyproject.toml           # Pip packaging + bundle globs
├── package.json             # npm shim packaging
├── CHANGELOG.md             # Per-release detail
└── LICENSE.txt              # Apache 2.0
```

The generated `quality/` directory (produced by running the skill on itself) holds the example output linked in *[Example output](#example-output)* above — `REQUIREMENTS.md`, `BUGS.md`, the review/audit protocols, per-bug writeups, patches, and TDD results.

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
