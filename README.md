# Quality Playbook

**Version:** 1.5.8 | **Author:** [Andrew Stellman](https://github.com/andrewstellman) | **License:** Apache 2.0

## Find the bugs that code review misses

Most AI code review can only find structural issues: null dereferences, resource leaks, race conditions. That catches about 65% of real defects. The other 35% are intent violations -- bugs that can only be found if you know what the code is *supposed* to do. A function that silently returns null instead of throwing, a duplicate-key check that passes when the first value is null, a sanitization step that runs after the branch decision it was supposed to guard. These bugs look correct to any reviewer that doesn't know the spec.

The playbook closes that gap. It reads your codebase, derives behavioral requirements from every source it can find (code, docs, specs, comments, defensive patterns, community documentation), and uses those requirements to drive review. The result is a quality system grounded in intent, not just structure. For a deeper look at this problem, see the O'Reilly Radar article [AI Is Writing Our Code Faster Than We Can Verify It](https://www.oreilly.com/radar/ai-is-writing-our-code-faster-than-we-can-verify-it/).

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

**Alternative: ask your AI coding tool to install it from a clone of this repo.**

1. **Clone this repo** somewhere on your machine — for example, `git clone https://github.com/andrewstellman/quality-playbook ~/quality-playbook`. One clone installs into any number of projects.

2. **Open your target project** in Claude Code, Cursor, GitHub Copilot, Windsurf, Continue, or another AI coding tool.

3. **Ask the AI to install it.** Something like:

   > *"Install the Quality Playbook into this project from `~/quality-playbook`."*

   The agent reads [`AGENTS.md`](AGENTS.md), figures out which install location your tool uses, and runs the installer. Done.

Prefer to install by hand or use the script directly? See [Step 1 of the walkthrough](#step-1-install-the-skill) for the script invocation and [Step 3](#step-3-install-the-skill-manual-flow--fallback) for the manual `cp` recipes.

**Prerequisite:** Python 3.10 or later on your `PATH`. QPB's runtime floor was raised from 3.9 to 3.10 in v1.5.7 089i — adopters must have 3.10+ available (the test suite uses 3.10-only features such as `unittest.TestCase.assertNoLogs`). The npm package is a thin shim over the same Python installer, so Python 3.10+ is required even when installing via `npx`.

**The more documentation you give it, the better it finds bugs.** The playbook reads written specs, design docs, GitHub or Jira issues from real users, chat history, and post-mortems — then derives what your code is *supposed* to do from those sources. Without documentation it still runs (from the source tree alone), but bug recall drops materially. See [Step 2: Provide documentation (strongly recommended)](#step-2-provide-documentation-strongly-recommended) for what to gather and the best ways to gather it.

**Gather it in one step.** Copy [`plugins/quality-playbook/skills/quality-playbook/references/DOC_GATHERING_PROMPT.md`](plugins/quality-playbook/skills/quality-playbook/references/DOC_GATHERING_PROMPT.md), open your project in Claude Code, Codex, Copilot, Cursor, Windsurf (or any capable AI tool), paste it in, and run it — it confirms your project, then crawls its docs, issues, and advisories into `reference_docs/` for you. See [Step 2](#step-2-provide-documentation-strongly-recommended) for details.

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

## Need help? Just ask your AI

The rest of this README has detailed instructions for installing and running the playbook — commands, prompts, screenshots, the whole walkthrough. But the easiest way to get started is to skip the documentation entirely: **download one file, upload it to your favorite AI chatbot, and ask it for help.**

The file is [`plugins/quality-playbook/skills/quality-playbook/ai_context/TOOLKIT.md`](https://github.com/andrewstellman/quality-playbook/blob/main/plugins/quality-playbook/skills/quality-playbook/ai_context/TOOLKIT.md). It's a single Markdown document that explains everything about the Quality Playbook in a format designed for AI assistants to read and answer questions from.

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

The playbook ships as a complete bundle of 50 files (`SKILL.md`, `quality_gate.py`, `references/`, `phase_prompts/`, `agents/`, and 13 `bin/*.py` modules — see `bin/install_skill.py::_bundle_files()` for the authoritative list, or the Step 3 manual recipe below) that need to land in a directory your AI coding tool reads as a skill. The recommended path is to have your AI tool do the install for you.

**Recommended: have your AI tool install it.** Open a chat with Claude Code, Cursor, GitHub Copilot, or another AI coding assistant inside your target repo. Ask it:

> *"Read AGENTS.md from the Quality Playbook repo and follow the install procedure to set up the skill in this project."*

The AI agent reads [`AGENTS.md`](AGENTS.md), runs `python3 -m bin.install_skill` against the target, parses the structured output, and reports back. This is the default mode the install path is designed for.

**Alternative: run the script directly.** From your local QPB clone:

```bash
python3 -m bin.install_skill --into /path/to/target-repo --ai-tool cursor   # canonical: name the AI tool
python3 -m bin.install_skill --into /path/to/target-repo                    # auto-detect via marker dir
python3 -m bin.install_skill --target /path/to/install-root                 # literal install path
python3 -m bin.install_skill --verbose                                      # human-readable output
```

`--ai-tool <name>` is the canonical way to invoke when you know which tool will use the project; values are `cursor`, `claude`, `copilot` (alias `github`), `continue`, `codex`, `windsurf`, `cline`, and `aider` — the full 8-tool set the installer supports. The script creates the marker directory if it doesn't exist and installs into that tool's canonical subdirectory (`.cursor/skills/quality-playbook/`, `.claude/skills/quality-playbook/`, `.github/skills/quality-playbook/`, `.continue/skills/quality-playbook/`, `.codex/skills/quality-playbook/`, `.windsurf/skills/quality-playbook/`, `.cline/skills/quality-playbook/`, or `.aider/skills/quality-playbook/`). Bare `--into <target-repo>` falls back to auto-detecting from a marker directory inside the target — which only works if the target has been opened by your AI tool at least once. Codex, Windsurf, Cline, and Aider don't pre-create a project marker directory (nor do Cursor and Copilot before first project open), so bare-`--into` auto-detection won't find them — but in the recommended flow (the "How to install" section above) you don't have to worry about this: the AI agent doing the install **self-identifies its own tool and passes the matching `--ai-tool` itself**, which installs to the canonical subdirectory and creates the marker dir whether or not it exists yet. You only pass `--ai-tool <tool>` yourself when you run the installer directly, with no agent in the loop. `--target <path>` treats the path as the literal install root and writes the skill files directly there; useful for operators with a non-standard install location. `--target` is mutually exclusive with both `--into` and `--ai-tool`.

**Alternative: install via pip or npm (no clone needed).** If you'd rather not clone the QPB repo, install from a package manager. As of v1.5.8 both channels are published and live on PyPI / npm. The Quality Playbook ships as an **application / scaffolder** that copies the skill into your project — not a library you import:

```bash
# pip / uvx / pipx (Python):
uvx quality-playbook install --into /path/to/target-repo --ai-tool <tool>        # one-shot, no global install
pipx run quality-playbook install --into /path/to/target-repo --ai-tool <tool>
pip install quality-playbook && quality-playbook install --into /path/to/target-repo --ai-tool <tool>

# npx (Node):
npx quality-playbook install --into /path/to/target-repo --ai-tool <tool>        # e.g. --ai-tool claude
```

Both channels run the **same Python installer** (Python 3.10+ is still required at runtime — the npm package is a thin Node shim, not a reimplementation), route the skill into the tool's canonical directory, and support the same `--ai-tool` self-identification described above. The channel sets `QPB_CHANNEL` (`pip` / `npm`) so the Phase-0 validator's remediation hints are channel-aware; neither channel ships compiled `.pyc` artifacts.

**Already manually copied SKILL.md to your skills directory?** Skip this step. The manual install paths described in Step 3 below continue to work — `bin/install_skill.py` is additive, not a replacement.

**What the install does:** copies the full skill bundle (50 files: `SKILL.md`, `quality_gate.py`, `references/`, `phase_prompts/`, `agents/`, and 13 `bin/*.py` modules — see `bin/install_skill.py::_bundle_files()` for the authoritative list) into the chosen install location. Runs a smoke check at the end (verifies `quality_gate.py` is loadable Python, `SKILL.md` parses with the expected frontmatter, `references/exploration_patterns.md` loads). Reports any failures in the structured output. Re-installs preserve operator-edited files as `<file>.operator-backup-<UTC-timestamp>` so your local edits aren't silently overwritten.

### Step 2: Provide documentation (strongly recommended)

The playbook produces better requirements, fewer false positives, and more specific bugs when it has written documentation to work from.

**Where to find documentation worth providing.** The single biggest leverage is **issue trackers** — GitHub issues, Jira tickets, Linear, Shortcut. Bug reports and feature requests written by real users tell you what they expect the code to do, which is usually *not* fully captured in any spec you've written. Other high-value sources, in rough order of leverage:

- **Issue trackers** — GitHub Issues, Jira, Linear, Shortcut. Filter for `bug` and `feature-request`; user words capture intent.
- **Project specs and design docs** — RFCs, API contracts, architecture decision records (ADRs). Authoritative when they exist.
- **Post-mortems and incident retrospectives** — capture intent that wasn't in the spec when the spec was written.
- **Chat history** — Slack channels, Microsoft Teams, Discord. Especially design discussions, triage threads, and on-call rotation handoffs.
- **AI chat logs** — Claude / ChatGPT / Cursor conversations where you reasoned through behavior.
- **Public standards you cite** — RFCs, W3C specs, vendor API docs.

**Tools that help gather these into plaintext.** Two open agent-driven tools fit this use case well:

- **[Cowork](https://claude.ai/cowork)** — Anthropic's desktop tool for non-developers; can connect to GitHub, Jira, Slack, Google Drive, Notion, and similar sources via MCP connectors, search across them, and export results to files. Good fit if you're already in the Anthropic ecosystem and want a graphical workflow.
- **[OpenClaw](https://openclaw.ai)** — open-source AI agent that runs as a local gateway connecting LLMs to your messaging platforms (Slack, Teams, Discord, IRC, plus 20+ others). Uses the same `SKILL.md`-based skills system QPB does, so you can give it tooling and ask it to traverse your channels and export the relevant threads. Good fit if your project's intent lives in chat history and you want self-hosted, open-source tooling.

**The easiest way: the guided gathering prompt.** Copy [`plugins/quality-playbook/skills/quality-playbook/references/DOC_GATHERING_PROMPT.md`](plugins/quality-playbook/skills/quality-playbook/references/DOC_GATHERING_PROMPT.md) (or fetch it raw from `https://raw.githubusercontent.com/andrewstellman/quality-playbook/refs/heads/main/plugins/quality-playbook/skills/quality-playbook/references/DOC_GATHERING_PROMPT.md`), paste it into any of the tools above, and run it — it only needs a project name to start. With QPB installed, you can also just ask your AI tool to gather docs for a project and it follows the same protocol. It identifies the project, proposes a source plan you can narrow or extend (including internal Jira/Confluence/Slack via your connectors), and writes well-structured files into `reference_docs/` (with `cite/` for authoritative specs). It grounds itself in the playbook first, so it gathers the *intent and invariants* QPB checks against rather than generic docs.

**Or a quick one-liner** if you just want something fast:

> *"Search [GitHub issues / Jira / Slack #project-channel / your-doc-source] for everything related to this codebase. Export to Markdown files in `reference_docs/`. Prioritize user-reported bugs and feature requests — those tell us what users expected that we may not have documented."*

After the playbook runs, **read `quality/REQUIREMENTS.md`** to see what it actually learned from those sources. The requirements there are what *the documentation says* your code is supposed to do — which is frequently not what you thought it did. That gap is the bug surface the playbook finds.

**File format.** Plaintext only — `.txt` and `.md`. Convert other formats first:

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
mkdir -p .claude/skills/quality-playbook/agents
mkdir -p .claude/skills/quality-playbook/bin
# v1.5.8 instruction 209: source paths nest through plugins/quality-playbook/skills/quality-playbook/
# (standard self-hosted marketplace plugin layout).
QPB_SKILL_SRC=plugins/quality-playbook/skills/quality-playbook
cp "$QPB_SKILL_SRC"/SKILL.md .claude/skills/quality-playbook/SKILL.md
cp "$QPB_SKILL_SRC"/scripts/quality_gate.py .claude/skills/quality-playbook/quality_gate.py
cp "$QPB_SKILL_SRC"/references/* .claude/skills/quality-playbook/references/
cp "$QPB_SKILL_SRC"/phase_prompts/*.md .claude/skills/quality-playbook/phase_prompts/
# v1.5.6: agents/*.md needed by README Step 4's `claude --agent agents/...` invocation.
cp "$QPB_SKILL_SRC"/agents/*.md .claude/skills/quality-playbook/agents/
# v1.5.7 089 (F1/A-29): the full bin/ closure SKILL.md + phase_prompts
# hard-reference. MIRRORED from install_skill.py::_bundle_files() and
# pinned by test_install_skill_bundle_completeness (drift recreates
# the A-26 ship-blocker via this doc-sanctioned manual path).
cp "$QPB_SKILL_SRC"/scripts/__init__.py                          .claude/skills/quality-playbook/bin/__init__.py
cp "$QPB_SKILL_SRC"/scripts/_purpose.py                          .claude/skills/quality-playbook/bin/_purpose.py
cp "$QPB_SKILL_SRC"/scripts/archive_lib.py                       .claude/skills/quality-playbook/bin/archive_lib.py
cp "$QPB_SKILL_SRC"/scripts/benchmark_lib.py                     .claude/skills/quality-playbook/bin/benchmark_lib.py
cp "$QPB_SKILL_SRC"/scripts/citation_verifier.py                 .claude/skills/quality-playbook/bin/citation_verifier.py
cp "$QPB_SKILL_SRC"/scripts/council_config.py                    .claude/skills/quality-playbook/bin/council_config.py
cp "$QPB_SKILL_SRC"/scripts/council_semantic_check.py            .claude/skills/quality-playbook/bin/council_semantic_check.py
cp "$QPB_SKILL_SRC"/scripts/migrate_v1_5_0_layout.py             .claude/skills/quality-playbook/bin/migrate_v1_5_0_layout.py
cp "$QPB_SKILL_SRC"/scripts/qpb_config.py                        .claude/skills/quality-playbook/bin/qpb_config.py
cp "$QPB_SKILL_SRC"/scripts/quality_playbook.py                  .claude/skills/quality-playbook/bin/quality_playbook.py
cp "$QPB_SKILL_SRC"/scripts/reference_docs_ingest.py             .claude/skills/quality-playbook/bin/reference_docs_ingest.py
cp "$QPB_SKILL_SRC"/scripts/role_map.py                          .claude/skills/quality-playbook/bin/role_map.py
cp "$QPB_SKILL_SRC"/scripts/run_state_lib.py                     .claude/skills/quality-playbook/bin/run_state_lib.py
cp "$QPB_SKILL_SRC"/scripts/validate_phase_artifacts.py          .claude/skills/quality-playbook/bin/validate_phase_artifacts.py
cp "$QPB_SKILL_SRC"/scripts/qpb_validate.py                      .claude/skills/quality-playbook/bin/qpb_validate.py
cp "$QPB_SKILL_SRC"/scripts/qpb_phase.py                         .claude/skills/quality-playbook/bin/qpb_phase.py
# v1.5.2: single reference_docs/ tree at the target repo root.
# No README ships — cite/ contents are adopter-provided plaintext.
mkdir -p reference_docs reference_docs/cite
# v1.5.7: the quality/RUN_INDEX.md sentinel for the gitignore negation
# rule (without it run_playbook.py's pre-flight aborts "Required
# sentinel files missing"; install_skill.py creates it too).
mkdir -p quality
echo "# Run Index" > quality/RUN_INDEX.md
# Optional: append the suggested .gitignore rules for adopters (keeps bulk
# archived runs + reference_docs content out of version control while tracking
# the top-level RUN_INDEX.md).
cat "$QPB_SKILL_SRC"/skill-template.gitignore >> .gitignore
```

**GitHub Copilot (flat layout):**
```bash
mkdir -p .github/skills/references
mkdir -p .github/skills/phase_prompts
mkdir -p .github/skills/agents
mkdir -p .github/skills/bin
# v1.5.8 instruction 209: source paths nest through plugins/quality-playbook/skills/quality-playbook/
# (standard self-hosted marketplace plugin layout).
QPB_SKILL_SRC=plugins/quality-playbook/skills/quality-playbook
cp "$QPB_SKILL_SRC"/SKILL.md .github/skills/SKILL.md
cp "$QPB_SKILL_SRC"/scripts/quality_gate.py .github/skills/quality_gate.py
cp "$QPB_SKILL_SRC"/references/* .github/skills/references/
cp "$QPB_SKILL_SRC"/phase_prompts/*.md .github/skills/phase_prompts/
# v1.5.6: agents/*.md needed by README Step 4's `claude --agent agents/...` invocation.
cp "$QPB_SKILL_SRC"/agents/*.md .github/skills/agents/
# v1.5.7 089 (F1/A-29): the full bin/ closure SKILL.md + phase_prompts
# hard-reference. MIRRORED from install_skill.py::_bundle_files() and
# pinned by test_install_skill_bundle_completeness (drift recreates
# the A-26 ship-blocker via this doc-sanctioned manual path).
cp "$QPB_SKILL_SRC"/scripts/__init__.py                          .github/skills/bin/__init__.py
cp "$QPB_SKILL_SRC"/scripts/_purpose.py                          .github/skills/bin/_purpose.py
cp "$QPB_SKILL_SRC"/scripts/archive_lib.py                       .github/skills/bin/archive_lib.py
cp "$QPB_SKILL_SRC"/scripts/benchmark_lib.py                     .github/skills/bin/benchmark_lib.py
cp "$QPB_SKILL_SRC"/scripts/citation_verifier.py                 .github/skills/bin/citation_verifier.py
cp "$QPB_SKILL_SRC"/scripts/council_config.py                    .github/skills/bin/council_config.py
cp "$QPB_SKILL_SRC"/scripts/council_semantic_check.py            .github/skills/bin/council_semantic_check.py
cp "$QPB_SKILL_SRC"/scripts/migrate_v1_5_0_layout.py             .github/skills/bin/migrate_v1_5_0_layout.py
cp "$QPB_SKILL_SRC"/scripts/qpb_config.py                        .github/skills/bin/qpb_config.py
cp "$QPB_SKILL_SRC"/scripts/quality_playbook.py                  .github/skills/bin/quality_playbook.py
cp "$QPB_SKILL_SRC"/scripts/reference_docs_ingest.py             .github/skills/bin/reference_docs_ingest.py
cp "$QPB_SKILL_SRC"/scripts/role_map.py                          .github/skills/bin/role_map.py
cp "$QPB_SKILL_SRC"/scripts/run_state_lib.py                     .github/skills/bin/run_state_lib.py
cp "$QPB_SKILL_SRC"/scripts/validate_phase_artifacts.py          .github/skills/bin/validate_phase_artifacts.py
cp "$QPB_SKILL_SRC"/scripts/qpb_validate.py                      .github/skills/bin/qpb_validate.py
cp "$QPB_SKILL_SRC"/scripts/qpb_phase.py                         .github/skills/bin/qpb_phase.py
# v1.5.2: single reference_docs/ tree at the target repo root.
mkdir -p reference_docs reference_docs/cite
# v1.5.7: the quality/RUN_INDEX.md sentinel for the gitignore negation
# rule (without it run_playbook.py's pre-flight aborts "Required
# sentinel files missing"; install_skill.py creates it too).
mkdir -p quality
echo "# Run Index" > quality/RUN_INDEX.md
cat "$QPB_SKILL_SRC"/skill-template.gitignore >> .gitignore
```

**GitHub Copilot (nested layout):**
```bash
mkdir -p .github/skills/quality-playbook/references
mkdir -p .github/skills/quality-playbook/phase_prompts
mkdir -p .github/skills/quality-playbook/agents
mkdir -p .github/skills/quality-playbook/bin
# v1.5.8 instruction 209: source paths nest through plugins/quality-playbook/skills/quality-playbook/
# (standard self-hosted marketplace plugin layout).
QPB_SKILL_SRC=plugins/quality-playbook/skills/quality-playbook
cp "$QPB_SKILL_SRC"/SKILL.md .github/skills/quality-playbook/SKILL.md
cp "$QPB_SKILL_SRC"/scripts/quality_gate.py .github/skills/quality-playbook/quality_gate.py
cp "$QPB_SKILL_SRC"/references/* .github/skills/quality-playbook/references/
cp "$QPB_SKILL_SRC"/phase_prompts/*.md .github/skills/quality-playbook/phase_prompts/
# v1.5.6: agents/*.md needed by README Step 4's `claude --agent agents/...` invocation.
cp "$QPB_SKILL_SRC"/agents/*.md .github/skills/quality-playbook/agents/
# v1.5.7 089 (F1/A-29): the full bin/ closure SKILL.md + phase_prompts
# hard-reference. MIRRORED from install_skill.py::_bundle_files() and
# pinned by test_install_skill_bundle_completeness (drift recreates
# the A-26 ship-blocker via this doc-sanctioned manual path).
cp "$QPB_SKILL_SRC"/scripts/__init__.py                          .github/skills/quality-playbook/bin/__init__.py
cp "$QPB_SKILL_SRC"/scripts/_purpose.py                          .github/skills/quality-playbook/bin/_purpose.py
cp "$QPB_SKILL_SRC"/scripts/archive_lib.py                       .github/skills/quality-playbook/bin/archive_lib.py
cp "$QPB_SKILL_SRC"/scripts/benchmark_lib.py                     .github/skills/quality-playbook/bin/benchmark_lib.py
cp "$QPB_SKILL_SRC"/scripts/citation_verifier.py                 .github/skills/quality-playbook/bin/citation_verifier.py
cp "$QPB_SKILL_SRC"/scripts/council_config.py                    .github/skills/quality-playbook/bin/council_config.py
cp "$QPB_SKILL_SRC"/scripts/council_semantic_check.py            .github/skills/quality-playbook/bin/council_semantic_check.py
cp "$QPB_SKILL_SRC"/scripts/migrate_v1_5_0_layout.py             .github/skills/quality-playbook/bin/migrate_v1_5_0_layout.py
cp "$QPB_SKILL_SRC"/scripts/qpb_config.py                        .github/skills/quality-playbook/bin/qpb_config.py
cp "$QPB_SKILL_SRC"/scripts/quality_playbook.py                  .github/skills/quality-playbook/bin/quality_playbook.py
cp "$QPB_SKILL_SRC"/scripts/reference_docs_ingest.py             .github/skills/quality-playbook/bin/reference_docs_ingest.py
cp "$QPB_SKILL_SRC"/scripts/role_map.py                          .github/skills/quality-playbook/bin/role_map.py
cp "$QPB_SKILL_SRC"/scripts/run_state_lib.py                     .github/skills/quality-playbook/bin/run_state_lib.py
cp "$QPB_SKILL_SRC"/scripts/validate_phase_artifacts.py          .github/skills/quality-playbook/bin/validate_phase_artifacts.py
cp "$QPB_SKILL_SRC"/scripts/qpb_validate.py                      .github/skills/quality-playbook/bin/qpb_validate.py
cp bin/qpb_phase.py                         .github/skills/quality-playbook/bin/qpb_phase.py
# v1.5.2: single reference_docs/ tree at the target repo root.
mkdir -p reference_docs reference_docs/cite
# v1.5.7: the quality/RUN_INDEX.md sentinel for the gitignore negation
# rule (without it run_playbook.py's pre-flight aborts "Required
# sentinel files missing"; install_skill.py creates it too).
mkdir -p quality
echo "# Run Index" > quality/RUN_INDEX.md
cat "$QPB_SKILL_SRC"/skill-template.gitignore >> .gitignore
```

**Cursor, Windsurf, other tools:** Use any of the locations above, or put the full skill bundle (50 files: `SKILL.md`, `quality_gate.py`, `references/`, `phase_prompts/`, `agents/`, and 13 `bin/*.py` modules — see `bin/install_skill.py::_bundle_files()` for the authoritative list, or the Step 3 manual recipe above) in your project root. The runner, gate, and orchestrator agents check all ten documented install layouts in order — repo-root `SKILL.md` plus the canonical `<marker>/skills/quality-playbook/` subdirectory for each of the 8 supported tools (`.claude`, `.github`, `.cursor`, `.continue`, `.codex`, `.windsurf`, `.cline`, `.aider`), with `.github/skills/` also accepted for the flat Copilot layout. The simplest path for any of these tools is still `python3 -m bin.install_skill --ai-tool <tool>`, which writes to the right subdirectory automatically.

**OpenAI Codex CLI:** v1.5.3 adds the standalone [codex CLI](https://github.com/openai/codex) (codex-cli 0.125+) as a third runner alongside claude and copilot. No separate skill-install layout — codex runs the playbook from any of the locations above. To use it via `bin/run_playbook.py`, pass `--codex` (see Step 4 + the "Running everything autonomously" section below).

### Step 4: Run the playbook

**Claude Code:** Open Claude Code in your project directory and say: *"Run the QPB install validator against this project (the `qpb_validate.py` entry point inside your QPB installation). For a clone-based install, the command is `python <path-to-your-QPB-clone>/bin/qpb_validate.py <this-project-absolute-path>` (substitute `<path-to-your-QPB-clone>` with your QPB clone path and `<this-project-absolute-path>` with this project's absolute path). Paste the complete structured output — every `event=` line including the run-nonce — into chat. Do not proceed past Phase 0 until `event=validation_complete status=ok`; if `status=remediable`, run each `event=remediation_suggestion`'s command verbatim (for a missing install the validator emits the platform-correct install command, e.g. `python <path-to-your-QPB-clone>/bin/install_skill.py --into <this-project-absolute-path> --ai-tool claude` — run it from your QPB clone) and re-run the validator. Then run the playbook including all four iteration strategies (the agent auto-discovers the installed skill). Execute Phases 1-5 yourself in this session — do not delegate execution to a sub-agent; Phase 6 verification uses a fresh-context auditor sub-agent per the skill's A-13-hybrid contract."* (The validator is the mandatory Phase 0 single source of truth — without a clean `status=ok` the artifact-contract validators and the Phase 6 gate are not at canonical locations; see AGENTS.md "Mode A entry sequence".)

Add `--dangerously-skip-permissions` when launching `claude` to skip file-write approval prompts during execution.

(For automated batch invocation — headless CI, scripted runs — use the orchestrator agent file via `claude --agent agents/quality-playbook.agent.md`. The orchestrator-agent path spawns sub-agents per phase and hides per-step output from operator chat, which is appropriate for unattended automation but NOT for interactive sessions where the operator monitors output. See `agents/quality-playbook.agent.md`'s "When to use this file" header for the full constraint.)

**GitHub Copilot:** Open the chat panel in VS Code, IntelliJ, or any IDE with Copilot support and say: *"Run the QPB install validator against this project (the `qpb_validate.py` entry point inside your QPB installation). For a clone-based install, the command is `python <path-to-your-QPB-clone>/bin/qpb_validate.py <this-project-absolute-path>`. Paste the complete structured output (every `event=` line) into chat. Do not proceed past Phase 0 until `event=validation_complete status=ok`; if `status=remediable`, run each `event=remediation_suggestion` command verbatim (the validator emits the platform-correct `--ai-tool copilot` install, run from the QPB clone) and re-run the validator. Then run the quality playbook on this project (the agent auto-discovers the installed skill)."* For the CLI, install the standalone `copilot` CLI (preferred — `brew install copilot-cli` on macOS, `winget install GitHub.Copilot` on Windows, or `curl -fsSL https://gh.io/copilot-install | bash` on Linux; npm: `npm install -g @github/copilot`) and invoke it with `copilot -p "<prompt>" --allow-all`. The deprecated `gh copilot` extension (`gh extension install github/gh-copilot`, then `gh copilot -p "<prompt>" --yolo`) still works during GitHub's grace period — QPB auto-detects which CLI is on `PATH` and routes accordingly via `bin/copilot_resolver.py` (v1.5.7 089f). (The validator is the mandatory Phase 0 — see AGENTS.md "Mode A entry sequence".)

**OpenAI Codex CLI:**
```bash
python3 -m bin.run_playbook --codex ./my-project
```
This invokes `codex exec --full-auto` (sandboxed automatic execution; the codex equivalent of the Copilot CLI's `--allow-all` / `--yolo`) for each playbook phase. Codex picks its model from `~/.codex/config.toml` unless you pass `--model gpt-5-codex` (or another model name in your codex config).

**Cursor:** Open Composer (Cmd+I / Ctrl+I) and say: *"Run the QPB install validator against this project (the `qpb_validate.py` entry point inside your QPB installation). For a clone-based install, the command is `python <path-to-your-QPB-clone>/bin/qpb_validate.py <this-project-absolute-path>`. Paste the complete structured output (every `event=` line) into chat. Do not proceed past Phase 0 until `event=validation_complete status=ok`; if `status=remediable`, run each `event=remediation_suggestion` command verbatim (the validator emits the platform-correct `--ai-tool cursor` install, run from the QPB clone) and re-run the validator. Then run the quality playbook on this project (the agent auto-discovers the installed skill)."* (The validator is the mandatory Phase 0 — see AGENTS.md "Mode A entry sequence".)

**Windsurf:** Open Cascade and say: *"Run the QPB install validator against this project (the `qpb_validate.py` entry point inside your QPB installation). For a clone-based install, the command is `python <path-to-your-QPB-clone>/bin/qpb_validate.py <this-project-absolute-path>`. Paste the complete structured output (every `event=` line) into chat. Do not proceed past Phase 0 until `event=validation_complete status=ok`; if `status=remediable`, run each `event=remediation_suggestion` command verbatim (the validator emits the platform-correct `--ai-tool windsurf` install, run from the QPB clone) and re-run the validator. Then run the quality playbook on this project (the agent auto-discovers the installed skill)."* (The validator is the mandatory Phase 0 — see AGENTS.md "Mode A entry sequence".)

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

### Running in CI

For headless / CI usage where `python3 -m bin.run_playbook` may be invoked
from a non-interactive context, see [`docs/CI_INTEGRATION.md`](docs/CI_INTEGRATION.md)
for the operator-side configuration steps.

**Non-interactive host-CLI invocation (auto-approval flag).** Each supported
host CLI needs its auto-approval flag (`--yolo` / `--dangerously-skip-permissions`
/ `--full-auto`) for non-interactive runs — omitting it makes the CLI silently
deny filesystem ops and cascade into a failed (or fabricated) run. See the
**Canonical adopter invocations** table in `AGENTS.md` for the exact
interactive vs non-interactive command per host CLI (Claude Code, the GitHub
Copilot CLI — new standalone `copilot` and the deprecated `gh copilot`
extension during the grace period per v1.5.7 089f, codex CLI, codex desktop).

### Known limitations

**Phase validator-invocation contracts are prose-enforced.** Phase 1, Phase 2,
Phase 5, and Phase 6 each require the agent to invoke `validate_phase_artifacts`
(Phase 1/2/5) or `quality_gate.py` + the fresh-context auditor (Phase 6) at phase
boundary and quote the verbatim verdict line. This is currently prose-mandated
in `phase_prompts/*.md` and the per-phase reference guides — agents are required
to comply but the requirement is not mechanically enforced. Empirically:

- **Phase 6** — codex desktop performs in-session verification with explicit
  disclosure rather than dispatching the mandated fresh-context sub-agent
  (observed 2026-05-18). Claude Code via Task tool + Copilot CLI Mode B dispatch
  the sub-agent correctly (Copilot CLI was the deprecated `gh copilot`
  extension at the time of observation; superseded by the standalone
  `copilot` CLI per v1.5.7 089f).
- **Phase 1** — codex desktop reported Phase 1 PASS while producing an
  EXPLORATION.md the validator would have FAILed (observed 2026-05-18
  self-bootstrap). Either the validator was not invoked, or its FAIL verdict
  was ignored.

Phase 2 and Phase 5 have the same structural shape and likely fail the same
way under the same conditions, though they have not surfaced empirically yet.

Operators reviewing phase verdicts should check for verbatim `RESULT: VALIDATION
PASSED (phase N)` lines (Phase 1/2/5) or fresh-context framing in the auditor
verdict (Phase 6). If absent, do not treat the verdict as load-bearing.

Structural enforcement is tracked for v1.6.x — see
`docs/design/QPB_v1.6.x_Phase6_Structural_Enforcement_Proposal.md` (filename
retains the historical `Phase6` suffix; content covers all phase-boundary
validator contracts via Slice 0 for Phase 1/2/5 subprocess attestation and
Slices 1+2 for Phase 6 subprocess verifier + witness-signing).

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

The gate ends with one of **three verdicts** (v1.5.7):

- **GATE PASSED** — the review completed and every audit record is in place. Nothing to do.
- **GATE PASSED WITH CLEANUP NEEDED** — the bug findings are real, reviewed, and stand on their own; only the audit trail is incomplete (a manifest record missing a field, a per-bug challenge record absent, a cross-site pattern tag not applied). This is **not a failure** — the review is done; only the paperwork needs filling in. Ask your AI assistant to complete the audit records without changing any findings.
- **GATE FAILED** — a substantive problem: the review didn't complete, specs are missing, the mechanical verifier never ran, or a verdict was fabricated. Fix the listed issues before treating the run as trustworthy.

The split exists so you can tell *"your code is broken in N ways"* apart from *"your audit trail is incomplete in N ways"* — earlier versions reported both as a flat `GATE FAILED — N checks`, and honest record-keeping-incomplete runs (which had found real, TDD-verified bugs) looked identical to runs where the review never happened.

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

### What's new in v1.5.8

v1.5.8 makes Windows a first-class supported platform for both Mode A (claude) and Mode B (codex via run_playbook), closes the cp1252-on-Windows hazard surface at all three sites where Python's system-locale default codec was eating data, formalizes the Worker self-Council protocol as load-bearing development methodology, graduates the AUDIT-table invariant test pattern to a standard mechanism after three confirmed reuses, and lands the v2 blind CVE benchmark methodology under `Security Research/CVE_BENCHMARK_METHODOLOGY_v2.md`.

- **Windows harness compatibility.** The 180 chain (10 followups) makes the harness fully cross-platform: psutil for process management (replaces POSIX-only `os.kill` / `os.killpg` — also fixes a latent Windows tree-kill-orphans-descendants bug), `CREATE_NO_WINDOW` instead of `DETACHED_PROCESS` so background spawns don't flash console windows, `windows-curses` automatically pulled in via the new `bin/harness/requirements.txt` (`sys_platform=='win32'` marker), `signal.SIGHUP` / `signal.SIGKILL` lazy-resolved (don't exist on Windows), git `core.longpaths=true` for MAX_PATH headroom. Install harness deps once via `python3 -m pip install -r bin/harness/requirements.txt`. Windows codex Mode B verified end-to-end with `gpt-5.5` / `gpt-5.4-mini`.
- **The cp1252-on-Windows hazard surface, closed.** On Windows, Python's default codec for stdout/stderr (pre-185), log file reads (pre-189), and subprocess stdin writes (pre-190) was cp1252 — which silently corrupts or hard-crashes on common high-bit characters (em-dash, `≥`, `←`, emoji verdict markers). v1.5.8 closes all three sites with explicit `encoding="utf-8"` + `errors="replace"`, AND each site landed with an AUDIT-table invariant test that prevents the same defect class from regressing at a new site. Future PR reviewers reference Section O ("Windows cp1252 hazard surface") in the design doc before approving any new `subprocess.run` / `open(text=True)` site.
- **`include_iterations` opt-in plan-row field (harness plans).** Per-row boolean (default `false`) — when `true`, the Mode A launch prompt drops the "Do not run the iteration strategies" exclusion clause so QPB runs all 4 iteration strategies (gap/unfiltered/parity/adversarial) per its documented default. **Empirical caveat**: in a 2026-06-03 blind-CVE benchmark A/B test, iterations made detection *worse* in 2/2 directly-comparable rows because the adversarial pass over-dismisses real findings when the model's call-graph reasoning is shallow. Default `include_iterations: false` is the recommended setting for security-targeted plans.
- **`kill <harness-run>` cancels PENDING runs + new `CANCELLED` terminal state.** Previously `kill` only SIGKILL'd RUNNING rows; PENDING rows would silently re-launch when a pool slot freed. Now `kill <harness-run>` stops EVERYTHING in the plan: RUNNING gets SIGKILL, PENDING gets transitioned to the new `CANCELLED` terminal state via the new `cancel_pending_run` helper. The collector and `_try_acquire_pool_slot` both treat CANCELLED as terminal. Status / TUI render CANCELLED rows in their own section with a `C` column.
- **The pre-186 `ABANDONED_STARVED` 3600s PENDING-run deadline is REMOVED.** For sequential `pool=1` plans with long-running rows (e.g., 7 × 45min security runs), the deadline killed runs before the pool could free a slot for them. Replaced with operator-visible signals: status shows `pending Nh Mm` waiting time + collector heartbeat-age health, and `qpb_harness force-run <run-NN>` (CLI) + `E` keybinding (TUI) explicitly launch a PENDING row out of pool when the operator decides the wait is wrong.
- **Worker self-Council protocol** ([`ai_context/DEVELOPMENT_PROCESS.md`](ai_context/DEVELOPMENT_PROCESS.md)). Formalization of the Parallel-Agent Council flavor with stricter discipline: 3 panelist charters in parallel via the implementing AI's Task tool, each Write-to-file artifact at `Reviews/v<NNN>_self_council/panelist_<X>_<charter>.md`, synthesis to `synthesis.md`, FIX-REQUIRED iterates in-branch BEFORE filing the v1 review-request. Has demonstrably caught ship-blockers across 187/188/189/190 that a single-reviewer pass would have shipped (187's manifest round-trip persistence gap, 188's `_try_acquire_pool_slot` race, 190's em-dash-IS-in-cp1252 boundary distinction).
- **AUDIT-table invariant test pattern.** When a defect class shape is observed across multiple sites, the fix is incomplete unless it includes an exhaustive-sweep invariant test that scans the entire relevant tree and asserts the contract holds at every site. Graduated from "pattern" to "standard mechanism" after 3 confirmed reuses (184 `_pid_alive` divergence, 189 log-read encoding, 190 subprocess stdin encoding). Documented in [`ai_context/DEVELOPMENT_PROCESS.md`](ai_context/DEVELOPMENT_PROCESS.md).
- **Blind CVE benchmark methodology v2.** `Security Research/CVE_BENCHMARK_METHODOLOGY_v2.md` extends the v1 framework with three orthogonal failure modes (token-level / structural / training-data contamination), explicit gathering whitelist + blacklist, two-gate verification (regex scan + blind-reviewer localization), baseline calibration requirement, and per-repo audit-trail discipline. Triggered by the 2026-06-02 Contamination Council finding that the v1-gathered `docs_gathered/` corpus was structurally contaminated. The 2026-06-03 blind benchmark run produced 2/7 DETECTED (setuptools CASE-001 + evervault-go CASE-009) — first methodologically-trustworthy blind security wins.
- **Test suite.** `bin/tests/harness`: 1198 OK / 0 fail / 1 skipped (+47 net new since v1.5.7).

### What's new in v1.5.7

v1.5.7 is a cleanup release that makes v1.5.6's runner output research-grade, formalizes the supporting metrics tree, aligns the skill prose with the phase architecture, and adds Council resilience and an adopter-side roster override.

- **Phase 2 gate-failure artifact preservation (D1).** When the Phase 2 gate aborts, the failed `quality/` directory is now preserved as `quality.gate-failed-<UTC-timestamp>/` instead of wiped. Operators can inspect the rejected EXPLORATION.md, the malformed role map, and the partial PROGRESS.md to diagnose what the agent actually produced.
- **Role-map query cookbook (D2).** New [`skills/quality-playbook/references/role_map_queries.md`](skills/quality-playbook/references/role_map_queries.md) gives Phase 2 agents canonical `jq` patterns against `quality/exploration_role_map.json`. Phase 2 prompts now point at it explicitly so agents stop hallucinating `.roles.source[]`-style query shapes that return empty.
- **Centralized log emission at `quality/logs/<run-id>/` (D3).** All log emission for a given run lands under one directory inside the cell. The `--logs-flat` legacy flag is available for adopters whose tooling reads from the old scattered paths. `quality/logs/` is included in the suggested `.gitignore` template.
- **`metrics/` formalization (D4).** The `metrics/` tree (recall data, calibration ledgers, regression-replay output) is now formally documented in [`metrics/README.md`](metrics/README.md). A reconstruction script rebuilds historical Q1+Q2 data from current artifacts so v1.7's SPC machinery has a stable input shape.
- **`SKILL.md` trim (D5).** Phase-specific reference-grade content moved from `SKILL.md` into `references/` files (same skill, same install, same behavior). Per-phase token cost is now better aligned with the existing phase architecture's isolation principle. The awesome-copilot Skill Validator's "comprehensive skill" warning prompted this; the underlying observation that every phase invocation loaded the full SKILL.md regardless of relevance was correct. SKILL.md dropped from 66,332 to 26,162 BPE tokens via pure move (no semantic changes, mechanical equivalence verified).
- **Council resilience and override layer (D6).** Phase 4 Council roster updated to `claude-opus-4.7`, `gpt-5.5`, `claude-sonnet-4.6` (replacing `gemini-2.5-pro` which the Copilot CLI silently dropped support for during the v1.5.6 sweep — observed under the then-active `gh copilot` extension and still missing under the new standalone `copilot` CLI per 089f). Adopters can now override the roster locally via `~/.qpb/config.json` (or `$XDG_CONFIG_HOME/qpb/config.json`) without editing source. v1.5.7 ships the roster modernization (sub-phase 6a) and this adopter override (6c); two further D6 sub-phases — fast-fail Council-launch availability detection (6b) and a structured failure-recovery template (6d) — are deferred to v1.5.7.x.
- **Ship-readiness fixes (F-1 through F-8).** Install/version detection now uses canonical six-layout markers instead of accepting any root `SKILL.md` as proof of install (F-1). Operator-facing six-layout fallback prose is consistent across SKILL.md, TOOLKIT, verification, review_protocols, and challenge_gate (F-2). *(Historical: the F-1/F-2 marker set was six layouts at v1.5.6; v1.5.7 expanded it to the canonical ten-layout list per A-3 + A-10 + A-11.)* `setup_repos.sh` archives existing target dirs as `.tar.gz` rather than deleting (F-3). The workspace/ guardrail also fails on empty workspace directories (F-4 amendment). *(F-5b — a `run_playbook.sh` wrapper that `setup_repos.sh` installed into target repos — was added then later removed in v1.5.7 089z; the canonical `python3 -m bin.run_playbook <target>` / `python3 bin/run_playbook.py <target>` forms are sufficient.)* Runner hint clarity on gate-failure-preservation state (F-6). Phase 3 BUGS.md/patches consistency gate check (F-7). The Phase 5 verdict shape is mechanically enforced as `## Verdict\n<PASS|FAIL>` (F-8).
- **Self-audit closures from ship-validation.** Three independent ship-validation runs (Codex bootstrap + chi/cobra copilot benchmarks on a fresh clone of the `v1.5.7` tag) surfaced 12 self-defects in v1.5.7 itself; all 12 are fixed (BUG-001 through BUG-007 from the bootstrap + Q1 through Q5 from the chi/cobra runs). The combined PROGRESS.md two-form schema not-in-drift test gives the deliverable-form and automation-form schemas a single shared test surface for future drift detection.
- **Test suite.** `bin/tests`: 1661 OK / 0 fail / 7 skipped. Quality-gate tests: 298 OK.

### What's new in v1.5.6

- **Adopter-facing distribution is now the default path.**
  QPB now ships a turnkey AI-agent-driven installer at
  [`bin/install_skill.py`](bin/install_skill.py), and the README quickstart is
  restructured so install is Step 1 instead of an afterthought.
- **The installer works in multiple environments without repo-specific hand edits.**
  It auto-detects `.claude/`, `.github/`, `.cursor/`, and `.continue/` targets,
  and it also supports explicit `--into <target-repo>` and `--target <path>`
  flags when the operator wants to pin the destination.
- **Cross-platform support is part of the release contract — and Windows is now directly validated.**
  The install path is written for Windows, macOS, and Linux via `pathlib`-style
  path handling. As of v1.5.7, Windows is exercised directly, not just asserted:
  `install_skill.py` installs cleanly on Windows (PowerShell), and full runs
  complete in both Mode A (Claude Code — natural-language install + run) and
  Mode B (`run_playbook.py` + the `copilot` CLI).
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
  now have [`skills/quality-playbook/references/code-only-mode.md`](skills/quality-playbook/references/code-only-mode.md)
  explaining the weaker evidence posture and how to upgrade later by adding docs.
- **AI orchestration patterns are documented for adopters, not just maintainers.**
  New [`ai_context/AI_ORCHESTRATION_PATTERNS.md`](ai_context/AI_ORCHESTRATION_PATTERNS.md)
  explains the orchestrator/worker pattern at adoption depth, with worked
  examples that cite the v1.5.5 ai_context-refresh runner and cross-links from
  [`ai_context/DEVELOPMENT_PROCESS.md`](ai_context/DEVELOPMENT_PROCESS.md) and
  [`skills/quality-playbook/agents/calibration_orchestrator.md`](skills/quality-playbook/agents/calibration_orchestrator.md).
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
- **The cycle is closed at 3 of 4 benchmarks.**
  The original 2026-05-02 cycle ran on chi-1.3.45 + virtio-1.5.1 + express-1.3.50
  with complete pre/post-lever cells (instruction 041 part 1 confirmed the
  express-1.3.50 cell.json files at `metrics/regression_replay/20260502T155324Z/`
  and the cycle subdirs DO exist — the audit prose claiming "interrupted before
  producing a replayable cell snapshot" was stale, not the data; the prose was
  reconciled in v1.5.6 fix-up 055). chi-1.5.1 was the original time-budget
  deferral; the v1.5.6 cluster F.2a follow-on pre-lever run with claude-opus-4-7
  produced 9/16 = 0.5625 substantive recall against the v1.5.1 baseline, and is
  documented separately below — it informs the historical baseline understanding
  but does not change the cycle's REVERT verdict, which was always concentrated
  on chi-1.3.45. The cycle is closed at 3 of 4 benchmarks; chi-1.5.1 is not a
  4th cell in the per-benchmark recall table.
- **Known limitations remain in the release notes instead of being buried in validation output.**
  Windows install + full runs are directly validated as of v1.5.7 (PowerShell;
  Mode A via Claude Code and Mode B via `run_playbook.py` + the `copilot` CLI).
  The one Windows-specific note: `quality/logs/latest` is a symlink that needs
  Developer Mode (or an elevated shell); when unavailable the runner writes a
  cross-platform `quality/logs/latest.txt` pointer and run resolution is
  unaffected. The reused `chi-1.3.45` Phase 4
  evidence remains code-only-mode reuse; the docs-backed re-validation was
  dropped in favor of the v1.5.6 cluster 047 architectural fix that closes
  the underlying defect class (see "Role_map architectural fix lands as the
  substantive Cluster E deliverable" below). The validation report's
  `pass-with-known-limitations` disposition stands.
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
  fallback list (six layouts when clusters 5/B landed; v1.5.7 expanded
  it to ten per A-3 + A-10 + A-11). Adopters using `.claude/`,
  `.cursor/`, `.continue/`, `.codex/`, `.windsurf/`, `.cline/`, or
  `.aider/` install layouts now get phase prompts that point at
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
- **chi-1.5.1 follow-on run lands; Pattern 7 cycle closes at 3 of 4 benchmarks.**
  Cluster F.2a (commit followed by no-commit per the cycle's no-source-change
  contract for benchmark replay) ran chi-1.5.1 pre-lever with claude-opus-4-7
  on 2026-05-07; substantive recall against the v1.5.1 baseline was 9/16 =
  0.5625 (recovered: CleanPath, SupressNotFound NPE, matchAcceptEncoding,
  AllowContentEncoding, Recoverer, RegisterMethod, BasicAuth, RouteHeaders,
  RealIP partial; missed: GetHead, the SupressNotFound mutate-live variant,
  Timeout, RequestID, Profiler, WrapResponseWriter, StripPrefix; 3 net-new
  findings: URLFormat dot-prefix, Mount collision probe, Sunset RFC-9745).
  This run informs the historical baseline understanding but does not change
  the original 2026-05-02 cycle's revert verdict — the displacement-recovery
  story was always concentrated on chi-1.3.45 (which was in the original
  3-of-4 scope and produced a negative result on the load-bearing measurement).
  chi-1.5.1 is therefore NOT a 4th cell in the cycle's per-benchmark recall
  table; the cycle is closed at 3 of 4 benchmarks. Audit at
  [`Calibration Cycles/2026-05-02-pattern7-displacement-recovery/audit.md`](https://github.com/andrewstellman/quality-playbook/tree/1.5.6).
- **Role_map architectural fix lands as the substantive Cluster E deliverable.**
  Cluster E (chi-1.3.45 docs-backed validation re-run, originally scoped in
  the v1.5.6 fix-up backlog) was dropped after two sonnet-4-6 attempts
  demonstrated a real bug: the LLM-written `role_map.json` `summary` field
  contract drifted from `summarize_role_map()` validation (file_count off
  by 8 the first time, structurally wrong shape the second). v1.5.6
  instruction 047 landed the architectural fix in commit `a85aa7c`: the LLM
  writes only `files[]` and `provenance`; the runner-side helper
  `bin.role_map.normalize_role_map_for_gate(path)` recomputes `breakdown`
  and `summary` from the canonical helpers between Phase 1 LLM exit and the
  Phase 2 entry-gate. Pre-cluster-047 the contract was "LLM produces summary;
  validator enforces it equals `summarize_role_map(role_map)`," which
  reliably failed for sonnet-class LLMs that reverted to intuitive
  summarization regardless of prompt strength. The deterministic computation
  is now runner-owned; the failure mode is unreachable for any future cycle
  work. This is the load-bearing Cluster E improvement; the chi-1.3.45
  docs-backed re-run itself was dropped because re-confirming what's already
  documented adds no new evidence about the cycle while the architectural
  fix removes a class of failures from all future cycles.
- **chi-1.3.45 Phase 4 validation evidence remains code-only-mode reuse.**
  The validation report at `Reviews/QPB_v1.5.6_Validation_Report.md` keeps
  its `pass-with-known-limitations` disposition. The chi-1.3.45 evidence
  there is the post-lever artifact set from the 2026-05-02 cycle, which
  ran in code-only mode (chi-1.3.45's `reference_docs/` was empty). The
  architectural fix from instruction 047 closes the underlying defect class
  for future cycles, but did not re-validate this specific run.
- **`--next-iteration` suggestion bug fixed (model-comparison sweep finding).**
  Instruction 044 (commit `2230ff5`) closed two defects in
  `bin/run_playbook.py`'s post-run "Next iteration suggestion" line:
  (A) the suggestion emitted `<interpreter> <script_path>` form which the
  v1.5.4-era package-module guard rejected with `EX_USAGE=64` at the time —
  self-contradictory, broke copy-paste workflows. (v1.5.7 fix F-5a later
  removed that guard via sys.path injection, so script-style invocation
  now works alongside the module form; the suggestion still emits the
  module form for shortness.)
  (B) the `runner_flag` dict was missing the `"copilot"` entry, so
  `--copilot` users got a suggestion that silently dropped the flag and
  copy-pasted them into default `--claude`. Reported during a
  model-comparison benchmark sweep on a v1.5.5 branch; lands on `1.5.6`.
  Two new regression tests pin both bugs.
- **Manual install recipes match the auto-installer (post-original-tag, instruction 062).**
  The auto-install via `python3 -m bin.install_skill` correctly bundles
  `agents/*.md` and `bin/citation_verifier.py` (per cluster A and BUG-005),
  but the manual `cp` recipes in README Step 3 (Claude Code, Copilot flat,
  Copilot nested blocks) and AGENTS.md (Copilot flat, Claude Code blocks)
  weren't updated to match. Adopters following the manual recipe verbatim
  got a broken install — README Step 4's `claude --agent agents/...`
  invocation found no `agents/` directory, and `quality_gate.py` fell back
  to a warning path because `bin/citation_verifier.py` wasn't installed.
  All five blocks now copy `agents/*.md` and `bin/citation_verifier.py`
  alongside the existing bundle. Empirically verified: Claude Code manual
  recipe against a tempdir target produces the same 31-file install as
  auto-install. Closes the residual portion of GitHub issue #1.
- **New "How to install the Quality Playbook" section in README (post-original-tag).**
  Added a top-level section before "Need help? Just ask your AI" that
  explains the recommended AI-driven install flow concisely (clone QPB →
  open clone in AI tool → ask AI to install) plus the auto-detection
  behavior, the `--ai-tool` and `--target` fallbacks when detection fails,
  the Python 3.10+ prerequisite, and a link to the manual `cp` recipes for
  operators who skip the AI handoff. First-time adopters now have a
  90-second readable overview before the detailed walkthrough.
- **`--ai-tool <name>` flag for explicit AI-tool selection (post-original-tag, instruction 064).**
  `bin/install_skill.py` auto-detection requires the target's AI-tool
  marker directory (`.cursor/`, `.claude/`, `.github/`, `.continue/`)
  to already exist. Some AI tools — notably Cursor and GitHub Copilot —
  don't reliably create that directory on first project open, so adopters
  who explicitly told their AI agent which tool they're using would still
  hit `event=detection_failed`. The new `--ai-tool <name>` flag accepts
  `cursor`, `claude`, `copilot` (alias `github`), or `continue`, maps to
  the canonical skill subdirectory, and creates the marker directory if
  it doesn't exist. Mutually exclusive with `--target`. Emits a structured
  event: `event=ai_tool_explicit ai_tool=<name> target=<base>
  marker=<.cursor|.claude|.github|.continue> install_path=<resolved>
  marker_created=<yes|no>`.
- **Install explainer + detection-failure recovery messaging (instruction 064).**
  The installer now emits an `event=intro` line at run start with a brief
  explanation of what's about to happen — the skill installs into a
  tool-specific subdirectory, detection looks for the marker directory,
  and `--ai-tool` overrides if detection fails. Verbose mode adds a fuller
  prose explainer. When auto-detection fails AND no `--target` AND no
  `--ai-tool` are passed, the existing refusal-to-guess behavior is
  preserved (script exits non-zero), and the failure event emits a
  structured recovery signal that AI agents reading the output can act on.
  9 new tests in `bin/tests/test_install_skill.py:AiToolFlagTests` covering
  all 5 choice values, github→copilot alias, target/ai-tool mutex, recovery
  emission, intro on success + on failure, and argparse rejection of bad
  values.
- **Codex bootstrap fixes (instruction 065).** Self-bootstrap audit on
  2026-05-08 with Codex GPT-5.4 Medium surfaced six bugs in QPB's own
  documentation/ingest/reporting paths. All six fixed across four commits:
  `docs_present()` and `_evaluate_documentation_state()` now share a
  single recognized-plaintext predicate so cite-only / README-only /
  binary-only trees classify consistently across all three startup
  surfaces (BUG-001/002); Tier 4 ingest restricted to top-level
  `reference_docs/` files (BUG-003); bootstrap mirror preserves the
  `cite/` subtree instead of silently dropping it (BUG-004); archive
  bug counter regex accepts the canonical `### BUG-NNN: Title` heading
  form QPB itself produces (BUG-006). 13 new regression tests, each
  bite-confirmed against unpatched code.
- **Phase 1 validator enforces the full SKILL.md gate (instruction 066).**
  Pre-fix the runtime validator at `bin/run_state_lib.validate_phase_artifacts()`
  enforced approximately 1 of the 13 checks documented at SKILL.md:1257-1273
  — file existence, ≥120 lines, and a generic findings-style heading regex.
  A 120-line placeholder `quality/EXPLORATION.md` with one heading and no
  analytical content passed the gate, recreating the v1.5.4 failure mode
  (phase reported "complete" with shallow output). The new validator
  enforces all 13 checks: six required headings (`## Open Exploration
  Findings`, `## Quality Risks`, `## Pattern Applicability Matrix`, ≥3
  `## Pattern Deep Dive — *`, `## Candidate Bugs for Phase 2`, `## Gate
  Self-Check`); PROGRESS.md Phase 1 line marked `[x]`; ≥8 findings with
  file:line citations; ≥3 multi-location findings; 3-4 FULL pattern
  matrix rows; ≥2 multi-function pattern deep dives; candidate-bug
  source mix (≥2 from exploration/risks AND ≥1 from pattern deep dive).
  Failure messages name which minimum failed and the SKILL.md line number.
  Calibrated against canonical EXPLORATION.md from the 2026-05-08 codex
  bootstrap as regression sanity (the canonical artifact passes the new
  validator). 14 new regression tests in `bin/tests/test_run_state_lib.py`.
- **Council post-tag fix-up — 13 items (instruction 067).** Council-of-Three
  review of post-tag work surfaced 13 findings; all closed in four
  commits. README bundle inventory updated at three locations to match
  the actual 31-file bundle. SKILL.md cross-validation rules table at
  line 501 now describes the 13-check gate accurately. `phase_prompts/phase1.md`
  rewritten to teach the six exact gate section titles + analytical
  minima — agent reading the new prompt produces gate-passing
  EXPLORATION.md. `bin/run_state_lib.py` empty-whitelist hole fixed
  (the `and declared_types` short-circuit that silently skipped the
  whitelist check is gone; empty whitelist now fails every subsequent
  event as the comment intended). Design + Implementation_Plan docs
  reconciled with shipped code (non-interactive structured-output,
  compile-only smoke check, full event format with all five fields).
  `docs_present()` / `_evaluate_documentation_state()` /
  `formal_docs_guard_banner()` unified on the docs_gathered fallback
  so legacy targets classify consistently. `bin/reference_docs_ingest.py`
  `_iter_candidates()` is now top-level only (no rglob); nested non-cite
  files no longer leak into ingest, and a nested non-cite `.pdf` no
  longer aborts Phase 1 ingest with `unsupported_extension`.
  `bin/bootstrap_self_audit_docs.py` mirror now cleans destination-only
  stale files. Plus five post-ship items (dead `_BUG_ENTRY_RE` regex
  level fix, module docstring v1.5.6, Check 13 per-entry diagnostic,
  programmatic mutex test, archive bug counter regex widen for
  hyphenated suffix BUG IDs).
- **Agent-asks-not-guesses contract (commit `a2ffe71` + instruction 068).**
  Original v1.5.6 README documented two recovery flags and their precedence
  for the auto-detection-failure case. The right contract is "agent asks
  the operator when it doesn't know which tool" — there's nothing the
  user needs to know about a recovery path. README "How to install"
  section simplified to a single sentence. AGENTS.md install-procedure
  Step 1 teaches the agent to ASK if the operator didn't name a tool
  in the original request; Step 4 detection-failure handling replaces
  "fall back to --ai-tool with whatever the operator said" with "STOP
  and ASK if you don't have the answer." Presence-check regression
  test in `bin/tests/test_agents_md.py` pins the contract.

### What's new in v1.5.5

- **Run-state instrumentation.** Every meaningful playbook event lands in `quality/run_state.jsonl` (machine-readable, append-only) and is reflected in `quality/PROGRESS.md` (atomically rewritten human view). Schema at [`skills/quality-playbook/references/run_state_schema.md`](skills/quality-playbook/references/run_state_schema.md). Helpers at [`skills/quality-playbook/scripts/run_state_lib.py`](skills/quality-playbook/scripts/run_state_lib.py) — read/parse events, validate format invariants, render PROGRESS.md, append events. Replaces the v1.5.4 `/tmp/`-based scheduled-task loop, which did not survive sandbox runtime constraints (state-file UID locking, host-only paths, subprocess lifetimes).
- **Phase-boundary cross-validation.** Every `phase_end` event is written only after the AI verifies its phase produced the expected artifacts (Phase 1's `EXPLORATION.md` ≥ 200 bytes with finding sections; Phase 4's `REQUIREMENTS.md` + `COVERAGE_MATRIX.md` + per-pass outputs in `quality/phase3/` if skill-derivation ran; Phase 6's `BUGS.md` + `INDEX.md` with `gate_verdict`; etc.). Catches the v1.5.4 failure mode where a phase reported "complete" with a 0-line artifact. `bin/run_state_lib.validate_phase_artifacts()` performs the checks programmatically.
- **Resume capability.** A killed orchestrator re-launched against the same cycle reads `run_state.jsonl`, finds the last unfinished phase, and resumes from there. The policy is "trust artifacts more than events" — if events claim phase complete but the artifact is missing, the phase re-runs.
- **Phase 5 source-edit guardrail.** The Codex bootstrap on 2026-05-02 went off-rails in Phase 5 and edited five source files outside `quality/` before being killed. v1.5.5 mechanizes the rule: `bin/run_state_lib.validate_no_source_edits()` shells out to `git status --porcelain -z` at run end and flags any non-`quality/` path as a violation. `_finalize_iteration()` calls it in production; on violation, the run is downgraded to `aborted`, the violations are recorded in `quality/results/quality-gate.log` and `quality/PROGRESS.md`, and the iteration is non-shippable.
- **Calibration-cycle orchestrator.** [`skills/quality-playbook/agents/calibration_orchestrator.md`](skills/quality-playbook/agents/calibration_orchestrator.md) documents the spawn-and-resume procedure for autonomous calibration cycles — one Claude Code session reads the prompt, runs the cycle's benchmark list end-to-end, applies lever changes between pre/post-lever runs, and writes the cycle audit + `Lever_Calibration_Log.md` entry. Runs as long-lived but stateless across crashes (state IS the filesystem).
- **Calibration visualizations.** [`bin/visualize_calibration.py`](bin/visualize_calibration.py) produces four artifacts per cycle into `<cycle-dir>/visualizations/`: per-bug × cycle heatmap (the displacement story made visible), lever × benchmark heatmap (recall delta on a red↔green diverging map), recall trajectory chart (per-benchmark line plot with lever-pull annotations), and a Mermaid lever-interaction graph. matplotlib + numpy required (install in the QPB venv).
- **Seven v1.5.4 self-audit defects fixed.** BUG-001 (CopilotRunner now transports the prompt via stdin instead of argv — silent failure for prompts > ARG_MAX); BUG-002 (`progress_monitor` opens transcripts in binary mode and keeps every offset in bytes — UTF-8 multi-byte content no longer desyncs the monitor); BUG-003 (`_printed_headers` set guarded by a lock); BUG-004 (Claude agent's skill-resolution order corrected to match `bin/run_playbook.py:SKILL_FALLBACK_GUIDE`); BUG-005 (README invocation examples use the package-module form `python3 -m bin.run_playbook` as the canonical form; v1.5.7 fix F-5a additionally restored script-style `python3 /path/to/QPB/bin/run_playbook.py` as a working alternative form via sys.path injection — the original script-style refusal guard is gone); BUG-006 (every operator-facing surface — SKILL.md, agents/, references/, runner WARN messages — routes operators to `reference_docs/` instead of `docs_gathered/`); BUG-007 (`bin/quality_playbook.py` help text matches the actual `archive_lib.ARCHIVE_DIRNAME`). Each landed with a regression test under `bin/tests/`.
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

- **Pattern 7 — Composition and Mount-Context Awareness** added to [`skills/quality-playbook/references/exploration_patterns.md`](skills/quality-playbook/references/exploration_patterns.md). A new bug-finding lens directing Phase 1 to enumerate, for each function or component that reads or writes state that *can be canonical-vs-raw under composition*, whether it correctly handles being composed inside a parent context. Direction-agnostic (read-side and write-side defects), 5 cross-domain examples (HTTP routing, transaction context, logging contextvars, locale-sensitive comparison, authorization scope), a 4-bullet seam list, a budget cap (3-5 highest-impact composition seams per pass), and a Pattern 4 disambiguation rule. Companion edit at `SKILL.md` lines 501 and 565 flips "six bug-finding patterns" / "all six analysis patterns" to seven — without these, Phase 1 walks patterns 1-6 and silently neuters Pattern 7. Cycle Finding C-3 captured this dependency-tracing class for future protocol revision.
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

Two invocation forms are supported (v1.5.7 fix F-5a):

- `python3 -m bin.run_playbook <target>` — canonical package-module form, runs from the quality-playbook repo root.
- `python3 /path/to/QPB/bin/run_playbook.py <target>` — direct script form, runs from any cwd. The runner injects QPB root into `sys.path` before importing sibling modules, so package-relative imports resolve regardless of how it's invoked. The pre-v1.5.7 script-style refusal guard is gone.

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
  --claude              Use claude -p instead of the Copilot CLI.
  --copilot             Use the GitHub Copilot CLI (default; auto-detects new standalone `copilot` with deprecated `gh copilot` extension as fallback per v1.5.7 089f).
  --codex               Use codex exec --full-auto instead of the Copilot CLI.
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

v1.5.8 instruction 208: restructured to Claude Code's plugin-native
layout so the marketplace mechanism (`/plugin marketplace add github.com/andrewstellman/quality-playbook`)
can auto-discover the skill. Bundled skill files now live under
`skills/quality-playbook/`; the pip/npm bundle internal layout
(`_bundle/SKILL.md`, `_bundle/bin/...`, etc.) is unchanged.

```
quality-playbook/
├── .claude-plugin/          # Claude Code plugin marketplace manifests
│   ├── marketplace.json     # Marketplace entry (auto-discovers skills/quality-playbook/)
│   └── plugin.json          # Plugin metadata (name, description, version, author)
├── skills/                  # Plugin-native skill folder layout (v1.5.8 208)
│   └── quality-playbook/
│       ├── SKILL.md         # The skill (main file — full operational instructions)
│       ├── references/      # Protocol and pipeline reference docs
│       │   ├── challenge_gate.md
│       │   ├── constitution.md
│       │   ├── defensive_patterns.md
│       │   ├── exploration_patterns.md
│       │   ├── functional_tests.md
│       │   ├── iteration.md
│       │   ├── orchestrator_protocol.md
│       │   ├── requirements_pipeline.md
│       │   ├── requirements_refinement.md
│       │   ├── requirements_review.md
│       │   ├── review_protocols.md
│       │   ├── schema_mapping.md
│       │   ├── spec_audit.md
│       │   └── verification.md
│       ├── phase_prompts/   # Per-phase agent prompts (Mode A + Mode B)
│       ├── agents/          # Orchestrator agent files for autonomous runs
│       │   ├── quality-playbook-claude.agent.md
│       │   └── quality-playbook.agent.md
│       ├── ai_context/      # Adopter-facing AI context
│       │   └── TOOLKIT.md   # For users' AI assistants (setup, run, interpret, recheck)
│       ├── scripts/         # Bundled scripts (canonical source; flattened to bin/ in the install bundle)
│       │   ├── quality_gate.py
│       │   ├── install_skill.py
│       │   ├── qpb_validate.py
│       │   └── ... (other bundled scripts)
│       └── skill-template.gitignore
├── bin/                     # Repo-level runner + build scripts (Python 3.10+)
│   ├── __init__.py
│   ├── run_playbook.py      # Mode B runner (positional args are target directories)
│   ├── build_channel_package.py  # Stages the pip/npm bundle from skills/quality-playbook/
│   ├── publish_pip.py       # Pip publish path
│   ├── publish_npm.py       # Npm publish path
│   ├── submit_awesome_copilot.py  # awesome-copilot submission automation
│   ├── install_skill.py     # Thin shim — delegates to skills/quality-playbook/scripts/install_skill.py
│   └── tests/               # stdlib-only unit tests (python3 -m pytest bin/tests/)
├── .github/skills/          # Installed-copy benchmark layout (preserved for setup_repos.sh)
├── pytest/                  # Local stdlib-only shim (python3 -m pytest works without installs)
├── ai_context/              # AI-readable maintainer-facing context (orientation docs)
│   ├── DEVELOPMENT_CONTEXT.md
│   ├── DEVELOPMENT_PROCESS.md
│   ├── IMPROVEMENT_LOOP.md
│   ├── TOOLKIT_TEST_PROTOCOL.md
│   └── BENCHMARK_PROTOCOL.md
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
