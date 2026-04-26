# Quality Playbook Toolkit

> This file is for your AI assistant to read — not for you to read yourself.
> Open it in Claude Code, Cursor, Copilot, or any AI coding tool and say:
> "Read TOOLKIT.md and help me set up the quality playbook for my project."
> The AI will guide you through everything.
>
> Background: [AI Is Writing Our Code Faster Than We Can Verify It](https://www.oreilly.com/radar/ai-is-writing-our-code-faster-than-we-can-verify-it/) (O'Reilly Radar)

## How to respond when the user opens this file with you

This section is instructions for **you, the AI assistant** reading this file — not for the user.

When a user opens this file with you and says something like "now you're an expert in the Quality Playbook," "read TOOLKIT.md and help me," or just attaches the file with no specific question, **keep your first response brief — two or three sentences plus one question**:

1. One sentence on what the playbook does (a skill that explores any codebase from scratch and finds real bugs through structured exploration, requirement derivation, three-pass code review, and a multi-model spec audit — every confirmed bug gets a regression test).
2. One sentence on what you can help with (setting it up on a project, running it, interpreting results, troubleshooting, or explaining a specific technique).
3. One question asking what they want to do.

**Do not** summarize this document, lead with methodology framing (verification dimensions, improvement levers, anything from the "How we improve the playbook" section), open with scope limits and caveats, or volunteer the deep technique explanations. Those sections exist for when the user asks for them, not as the opening pitch. The user opened this doc because they want to *do something* with the playbook; the most helpful first move is to ask them what.

The rest of this document is reference material. Pull from the relevant section once the user tells you what they want.

## What this is

The Quality Playbook is a skill that explores any codebase from scratch and finds real bugs. It generates nine quality artifacts: exploration notes, requirements, a quality constitution, functional tests, a code review with regression tests, a consolidated bug report with patches, TDD verification, integration tests, and a multi-model spec audit. Every confirmed bug gets a regression test patch, a fix patch, and red/green TDD verification.

The skill file is `SKILL.md`. The iteration reference is `references/iteration.md`. These contain the full operational instructions the agent follows when running the playbook. This toolkit file is different — it helps you (through your AI assistant) set up, run, interpret, and iterate on the playbook. It also explains how the playbook works: what techniques it uses, why it uses them, and what makes them effective at finding bugs that other approaches miss.

## Quick start

The user wants to run the quality playbook on a codebase. Here's what to do:

1. **Copy skill files into the repo.** The playbook expects its files in one of four documented install locations, and every component (runner, gate, orchestrator agents) checks all four in order:

   1. **Repo root (source checkout):** `SKILL.md`, `references/`, `quality_gate.py` at the project root. Useful when running the playbook out of the quality-playbook checkout itself.
   2. **Claude Code:** `.claude/skills/quality-playbook/SKILL.md`, `.claude/skills/quality-playbook/references/`, `.claude/skills/quality-playbook/quality_gate.py`.
   3. **GitHub Copilot (flat):** `.github/skills/SKILL.md`, `.github/skills/references/`, `.github/skills/quality_gate.py`.
   4. **GitHub Copilot (nested):** `.github/skills/quality-playbook/SKILL.md`, `.github/skills/quality-playbook/references/`, `.github/skills/quality-playbook/quality_gate.py`.

   Create the directories if they don't exist. Copy from wherever the user has the playbook files. The source tree has the gate script inside a package directory with tests (`.github/skills/quality_gate/quality_gate.py` plus a `tests/` subdirectory) — target repos only need the standalone `quality_gate.py` file itself, not the package. `repos/setup_repos.sh` handles this automatically: it copies just the module file into each target's `.github/skills/quality_gate.py`.

2. **Add documentation (strongly recommended).**

   If the user has specs, API docs, design documents, AI chat logs, retrospectives,
   or community documentation, place them in a `reference_docs/` directory at the
   top of the target repo:

   - **Tier 4 context (AI chats, design notes, retrospectives)** → `reference_docs/`
     at the top level. No special treatment — these are read as background.

   - **Citable material (project specs, RFCs, API contracts)** → `reference_docs/cite/`
     subfolder. Every file here gets a byte-verified citation record. If a file is
     the adopter's project-internal spec or an authoritative external standard and
     you want the playbook to cite it with rigor, put it in `cite/`.

   - **File format** — plaintext only (`.txt` or `.md`). Convert binary/formatted
     sources first: `pdftotext spec.pdf spec.txt`, `pandoc -t plain spec.docx -o spec.txt`,
     `lynx -dump https://example.org/spec.html > spec.txt`. The ingest script
     rejects non-plaintext extensions.

   - **No sidecar needed** — folder placement is the flag. If the user asks how to
     mark something citable, tell them to move it into `reference_docs/cite/`.
     Do not create `.meta.json` files; the current schema does not use them.

   - **Optional Tier 2 marker** — a `cite/` file can declare Tier 2 with an
     in-file first-line marker: `<!-- qpb-tier: 2 -->` (Markdown) or
     `# qpb-tier: 2` (plaintext). Default when absent is Tier 1. Most adopters
     do not need this.

   - **If the user has documentation but is unsure what's citable** — default to
     top-level `reference_docs/` (Tier 4 context). Only move files into `cite/`
     when the adopter confirms the file is an authoritative source they want
     the playbook to cite by quote.

   When asked to help an adopter set up the playbook, run:

       mkdir -p reference_docs reference_docs/cite

   and then either move files they identify into the appropriate bucket or ask
   them to drop files in and classify afterward.

   Documentation-enriched runs find significantly more bugs and higher-confidence
   bugs than code-only runs. The playbook works without docs, but it works much
   better with them.

3. **Run the playbook — one phase at a time.** Give the agent this prompt:
   ```
   Run the quality playbook on this project.
   ```
   The playbook starts with Phase 1 (Explore) and stops after that phase, showing the user what happened and what to say next. The user drives each phase forward by saying "keep going" or "run phase 2". Running phases separately gives much better results — each phase gets the full context window for deep analysis instead of competing with other phases.

   If the user says "help" or "how does this work", the skill will explain itself. If the user says "what happened" or "what should I do next", the skill reads PROGRESS.md and gives a status update.

4. **Review results.** After all six phases, the key output files are:
   - `quality/BUGS.md` — confirmed bugs with file:line references
   - `quality/PROGRESS.md` — phase completion tracker and bug summary
   - `quality/results/tdd-results.json` — structured TDD verification results
   - `quality/results/recheck-results.json` — fix verification results (after recheck)
   - `quality/patches/BUG-NNN-regression-test.patch` — test that proves each bug
   - `quality/patches/BUG-NNN-fix.patch` — proposed fix for each bug

5. **Run iterations for more bugs.** After the baseline run, the user can run iteration strategies that typically find 40-60% more confirmed bugs. Say "run the next iteration" to start the gap strategy, or name a specific strategy: gap, unfiltered, parity, or adversarial. The recommended cycle runs all four in sequence.

6. **Verify bug fixes with recheck.** After the user fixes bugs from BUGS.md, say "recheck" to verify the fixes. Recheck mode reads the existing bug report, checks each bug against the current source (reverse-applying fix patches, inspecting cited lines, optionally running regression tests), and reports FIXED / STILL_OPEN / PARTIALLY_FIXED / INCONCLUSIVE for each bug. Results go to `quality/results/recheck-results.json` (machine-readable) and `quality/results/recheck-summary.md` (human-readable). Takes 2-10 minutes instead of re-running the full 60-90 minute pipeline.

## Is this for the user's codebase? (scope and limits)

The playbook is opinionated and earns its keep on a specific class of codebases and bugs. If the user asks "should I run this?" or describes a project that might be a poor fit, surface the relevant limit from this section before running.

**This is process verification, not bug guarantee.** The mechanical gate (`quality_gate.py`) verifies that the artifacts have the expected shape: BUGS.md uses the right heading format, every confirmed bug has a regression-test patch, the TDD log files exist, the requirements pipeline produced citations. Passing the gate proves the process completed. It does **not** prove that every bug in the codebase was found, or that the bugs that *were* found exhaust what an experienced human reviewer would have caught. A code-generation model can produce all the artifacts and pass all the gates while finding zero real bugs (see "Cursor" under Agent reference); the gate cannot tell that case apart from a real bug-bearing run. The gate constrains process compliance; bug recall depends on the agent's reasoning depth and the iteration strategies actually being run.

**Derive-from-code mode launders existing behavior into the spec.** When no `reference_docs/` are present, the playbook derives requirements from the source itself — comments, function signatures, error messages, test expectations. The resulting requirements describe what the code currently does. Pass 2 verification ("does the code satisfy this requirement?") then mostly returns SATISFIED, because the requirement was extracted from the same code being checked against it. Real bugs in this mode usually surface in Pass 3 (cross-requirement consistency) and the iteration strategies — adversarial in particular, which is designed to challenge SATISFIED verdicts — not in Pass 2. Documentation-enriched runs avoid this by anchoring requirements to an external source. If the only docs available are autogenerated from the same source code, treat the run as derive-from-code mode for this purpose.

**Mechanical verification constrains shape, not semantic correctness.** The mechanical extractions (switch-case constants, exception handlers, defensive patterns) and integrity checks prevent the model from hallucinating that a function handles a constant it doesn't list. They do **not** prove that the function handles those constants *correctly*. A two-list diff that comes back empty means every spec constant has a case label — it does not mean the case body does the right thing. The downstream code review still has to read the bodies. The mechanical layer's contribution is bounding the hallucination surface, not certifying behavior.

**`NOT_RUN` is acknowledgment, not verification.** When the test runner isn't available for the project's language (kernel C without a kernel build environment, embedded targets without their build harness, etc.), the playbook records `NOT_RUN` in the TDD log with an explanation rather than failing silently. This makes the missing verification *legible* — but the bug is still confirmed only by code-path trace, not by an executed regression test that fails red and passes green. Reviewers reading a writeup with a `NOT_RUN` log should treat the bug as confirmed at the evidentiary standard described in "The evidentiary standard for confirming bugs" below, but not as TDD-verified.

### Where this adds little

Domains the playbook is poorly matched to:

- **Mostly-CRUD application layers** (typical Rails apps, internal admin tools, auto-generated API stubs). Bugs in the bespoke business logic the playbook can find, but the structured exploration spends most of its budget on framework boilerplate the framework already enforces. Iterate on the bespoke modules; skip the runner over autogenerated layers.
- **Declarative infrastructure** (Terraform plans, Kubernetes manifests, Helm charts, CloudFormation templates). The "code" is configuration and the bugs are policy/intent mismatches against an infrastructure spec the playbook does not model. Use a domain-specific linter (tfsec, kube-score, conftest, checkov) instead.
- **Visual or numerical correctness** (GPU shaders, rendering pipelines, ML training loops, scientific simulations). The playbook can find structural bugs in these (resource leaks, error-path bugs, enumeration gaps) but cannot evaluate whether the output is correct — that requires reference images, reference distributions, or domain-specific correctness oracles.
- **Hot-path performance regressions.** The playbook does not run benchmarks. Performance is reasoned about, not measured.

If the user's project falls primarily into one of these domains, say so up front and offer a partial scope (e.g., "I can run the playbook over the bespoke service modules in your Rails app, but not the scaffolded controllers and migrations") rather than running it end-to-end and producing a thin or misleading bug report.

## Setting up automation scripts

Users often want to run the playbook across multiple repositories or automate the iteration cycle. The repository now ships a built-in standard-library runner, so prefer that over asking users to write new shell wrappers.

### Built-in runner

Positional arguments are directory paths (relative or absolute). No version resolution, no benchmark-folder lookups — every argument is taken literally. Omit positional args to run against the current directory.

```bash
cd my-project
python3 /path/to/quality-playbook/bin/run_playbook.py                      # run on cwd
python3 /path/to/quality-playbook/bin/run_playbook.py --phase all          # phase-by-phase on cwd
python3 /path/to/quality-playbook/bin/run_playbook.py ./project1 ./project2  # multiple targets
python3 /path/to/quality-playbook/bin/run_playbook.py --claude --model sonnet ./project1
python3 /path/to/quality-playbook/bin/run_playbook.py --next-iteration --strategy parity ./project1
```

For benchmark use, run from the `repos/` folder so relative paths work naturally:

```bash
cd repos
python3 ../bin/run_playbook.py --phase all --sequential chi-1.4.6
```

Key properties:
- Standard library only, Python 3.8+
- No `pip install`, no `requirements.txt`, no virtual environment creation
- Defaults to `.` (current directory) when no positional args are given
- Missing-SKILL.md produces a warning, not an error — useful for first-time installs

### Setup script

`repos/setup_repos.sh` still copies skill files into one or more target repos. Core logic:

```bash
# Adapt paths for the user's environment
SKILL_DIR="/path/to/quality-playbook"   # where SKILL.md etc. live
REPO_DIR="/path/to/repos"               # where target repos live

for repo in "$@"; do
    dst="${REPO_DIR}/${repo}/.github/skills"
    mkdir -p "${dst}/references"
    cp "${SKILL_DIR}/SKILL.md" "${dst}/SKILL.md"
    # iteration.md is now in references/ — copied by the wildcard below
    cp "${SKILL_DIR}/.github/skills/quality_gate/quality_gate.py" "${dst}/quality_gate.py"
    cp "${SKILL_DIR}/references/"*.md "${dst}/references/"
    echo "Set up ${repo}"
done
```

On Windows (PowerShell), replace the loop with `foreach ($repo in $args)` and use `Copy-Item` / `New-Item -ItemType Directory`.

### Runner behavior

`bin/run_playbook.py` is the entry point. The top-level flags are:
- `--parallel` or `--sequential`
- `--claude` or `--copilot`
- `--phase all`, `--phase N`, or `--phase 3,4,5`
- `--next-iteration --strategy gap|unfiltered|parity|adversarial|all`
- `--strategy` also accepts a comma-separated ordered subset (e.g. `unfiltered,parity,adversarial`)
- `--full-run` (fresh main run + all iteration strategies)
- `--model MODEL`
- `--kill`
- `--no-seeds` or `--with-seeds`

Positional arguments are **directory paths**. Version-append fallback: if a bare name (no path separators, no leading `.` / `..` / `~`) doesn't exist on disk, the runner retries `<name>-<skill_version>` using the `version:` line from `SKILL.md` at the QPB root. Path-like inputs are taken literally — no fallback. When the fallback hits, an `INFO: resolved '<name>' to '<name>-<version>' (via SKILL.md version)` line goes to stderr.

The runner writes one log file per target next to the target directory (at `{parent}/{target-name}-playbook-{timestamp}.log`), archives prior `quality/` runs before fresh baselines, and enforces phase prerequisite gates.

The iteration prompt is built from `SKILL_FALLBACK_GUIDE` in `bin/run_playbook.py`, so it advertises all four install locations instead of hardcoding one:
```
Read the quality playbook skill using the documented install-location fallback list:
SKILL.md, .claude/skills/quality-playbook/SKILL.md,
.github/skills/SKILL.md, .github/skills/quality-playbook/SKILL.md.
Resolve reference files using the same documented fallback order.
Run the next iteration using the <strategy> strategy.
```

Replace `<strategy>` with: gap, unfiltered, parity, or adversarial. The same fallback preamble fronts the phase prompts and the single-pass prompt.

If a user needs a custom wrapper for another environment, mirror the built-in Python runner rather than reviving the old shell script.

## Agent reference

The playbook works with any AI coding agent that can read files and execute shell commands. Here's what we know about each:

### Claude Code (CLI)

**Best overall results.** Claude Code with Opus follows the full instruction chain including TDD test execution — it actually runs the regression tests and captures red/green phase logs. Other agents tend to skip this step.

```bash
cd /path/to/repo
claude -p "Read the quality playbook skill at .github/skills/SKILL.md and execute the quality playbook for this project." --dangerously-skip-permissions
```

- `--dangerously-skip-permissions` lets it run shell commands without prompting (needed for test execution, mechanical verification, etc.)
- Add `--model opus` or `--model sonnet` to specify a model
- To capture output: pipe through `tee` — e.g., `claude -p "..." --dangerously-skip-permissions 2>&1 | tee output.log`
- Do NOT wrap with `script -q` — it buffers output and prevents live streaming

### GitHub Copilot (CLI)

**Good exploration, weak on TDD execution.** Copilot with gpt-5.4 finds bugs reliably but typically generates regression test patches without actually executing them. The TDD red/green logs will be missing or incomplete.

```bash
cd /path/to/repo
gh copilot -p "Read the quality playbook skill at .github/skills/SKILL.md and execute the quality playbook for this project." --model gpt-5.4 --yolo
```

- `--yolo` is Copilot's equivalent of skip-permissions
- Rate limits are aggressive: running 6+ repos in parallel with iteration cycles can trigger a 54-hour cooldown
- Stagger runs: 2-3 repos at a time, with pauses between batches

### Cursor (IDE)

**Good, but watch for two gotchas:**

1. **Isolate the repo.** Open ONLY the target repo folder in Cursor — not a parent directory containing other repos. Cursor's workspace scope bleeds upward, and it will find and read BUGS.md files from sibling directories, contaminating the run with prior findings.

2. **Choose the right model.** Cursor's "auto" mode may select a model that's too weak for deep code exploration. Code-generation models (like Codex) can produce all the artifacts and pass all the gates while finding zero bugs — they follow the structure without the reasoning depth. Explicitly select Claude Sonnet, Claude Opus, or GPT-5.4 in Cursor's model dropdown.

Prompt: paste the same prompt into the chat.

### Other agents

The playbook should work with any agent that can read markdown files and execute shell commands. The key requirement is **reasoning depth** — the agent needs to be able to read unfamiliar code, form hypotheses about edge cases, and trace code paths across multiple functions. Models optimized purely for code generation (autocomplete, inline suggestions) typically lack this capability.

---

## How the playbook works — detailed guide

This section explains the playbook's core techniques in detail so you can answer questions like "how does it find bugs?", "what is forensic inversion of try/catch blocks?", "why does it need three code review passes?", or "what's the difference between gap and adversarial iteration?" If the user asks how something works, look for the answer here first.

### The core insight: intent-driven bug discovery

Most AI code review can only find structural issues — null dereferences, resource leaks, race conditions, obvious logic errors. The harder class is intent violations: bugs that can only be found if you know what the code is *supposed* to do. A function that silently returns null instead of throwing, a feature-bit whitelist that silently drops a feature the spec says it should preserve, a sanitization step that runs after the branch decision it was supposed to guard. The code is structurally correct — it compiles, it doesn't crash, it handles its inputs gracefully. But it doesn't do what it's supposed to do. Intent violations were a substantial fraction of the confirmed bugs across the benchmark repos — enough that a structural-only reviewer would be missing material defects on every non-trivial run.

The playbook's main job is figuring out intent. It reads documentation, specs, code comments, test expectations, defensive patterns, and community documentation to derive what the code *should* do, then uses that knowledge to drive a code review that can find intent violations. Without requirements, a code reviewer can only ask "is this code correct?" With requirements, the reviewer can ask "does this code do what the spec says it should?"

### Phase 1: Exploration — understanding the codebase

The agent reads source files, tests, config, specs, and commit history. The goal is not just to catalog what exists, but to understand what the code is supposed to do and where it might fail. Exploration has several specific techniques:

#### Defensive pattern forensics (the "skeleton" technique)

Developers don't write try/catch blocks, null checks, or retry logic for fun. Every piece of defensive code exists because someone got burned — or because someone anticipated getting burned. The playbook treats defensive code as archaeological evidence of past failures.

The technique works by systematically grepping the codebase for defensive patterns (null guards, exception handlers, retry loops, sentinel values, fallback defaults) and then asking: "What failure does this code prevent? What input would trigger this path?" Each answer becomes a fitness-to-purpose scenario and a boundary test.

For example, a `try/except` around a JSON parse means malformed JSON happened in production. A null check on a user field means that field was sometimes missing when it shouldn't have been. An exponential backoff wrapper means the downstream service was unreliable. The playbook doesn't just note these patterns — it inverts them into test scenarios: "What happens if the JSON IS malformed? Does the error propagate correctly? Is the user notified? Is the partial state cleaned up?"

This inversion is particularly powerful because it generates test cases that the original developer already identified as important — they wrote defensive code for exactly these failure modes. The playbook ensures those failure modes are actually tested, not just guarded.

#### State machine analysis

When the codebase has status fields, lifecycle phases, or mode flags, the playbook traces the complete state machine: every possible state, every transition, every consumer that checks state. It specifically looks for states you can enter but never leave (terminal state without cleanup), operations that should be available in a state but are blocked by an incomplete guard, and state-checking code that doesn't handle all possible states.

State machine bugs are invisible during normal operation because they only surface when the system enters an unusual state — exactly when you need it to work correctly. A batch processor that can't be killed when it's "stuck," a watcher that never stops after all work completes, a UI that refuses to resume a "pending" run — these are all symptoms of incomplete state handling.

#### Enumeration and whitelist completeness

When a function dispatches on a set of named constants (switch/case, match expressions, if-else chains), the playbook performs a mechanical two-list check: extract every constant from the spec/header/enum (List A), extract every case label from the code (List B), and diff them. Any constant in A but not in B is a potential gap.

This mechanical check exists because AI models reliably hallucinate completeness for switch/case constructs. The model sees a function with many case labels, sees constants defined elsewhere, and concludes all constants are handled without checking. In one observed case, the model asserted a kernel feature-bit whitelist "preserves supported ring transport bits including VIRTIO_F_RING_RESET" when that constant was entirely absent from the switch. The two-list check catches this by forcing the agent to actually extract and compare rather than summarize from memory.

The extraction must be done mechanically — using shell commands like `awk`/`grep` that read file bytes and cannot hallucinate. The output is saved to `quality/mechanical/` and verified with an integrity check script. Downstream artifacts must cite the mechanical file, not a hand-written list.

#### Domain-knowledge risk analysis

Beyond code exploration, the playbook asks domain-specific questions based on the agent's training knowledge of what goes wrong in similar systems. For an HTTP client: redirect credential stripping, encoding detection failures, connection state leaking across requests. For a serialization library: null handling asymmetry between API surfaces, round-trip fidelity loss, lazy evaluation caching bugs. For a batch processor: crash recovery, idempotency, silent data loss, state corruption.

These hypotheses are grounded in the actual code: "Because `save_state()` at persistence.py:340 lacks an atomic rename pattern, a mid-write crash during a 10,000-record batch will leave a corrupted state file." The test: could a code reviewer read the scenario and immediately know what function to open and what input to test?

### Phase 2: Artifact generation

Exploration findings are distilled into nine quality artifacts through a structured pipeline.

#### The requirements pipeline

This is the playbook's core value. A five-phase pipeline converts exploration findings into testable behavioral requirements:

1. **Contract extraction** — Read all source files and list every behavioral contract (what the code promises to do). Written to `CONTRACTS.md`.
2. **Requirement derivation** — Group related contracts, enrich with user intent from documentation, write formal testable requirements. Each requirement cites a specific doc source with an authority tier (Tier 1 = formal spec, Tier 2 = official docs, Tier 3 = inferred from source code).
3. **Coverage verification** — Cross-reference every contract against every requirement. Fix gaps until coverage reaches 100%.
4. **Completeness check** — Apply a domain checklist, testability audit, and cross-requirement consistency check. Self-refine up to 3 times.
5. **Narrative pass** — Add an overview, derive use cases, reorder for readability.

The requirements are what make the three-pass code review and spec audit effective. Without them, a reviewer can only find structural bugs. With them, the reviewer can check "does this code do what the spec says?" — which is how you find the other 35%.

#### The quality constitution

`QUALITY.md` defines what "correct" means for this specific project. It includes fitness-to-purpose scenarios — concrete failure modes grounded in the actual codebase, not abstract quality goals. Each scenario reads like a vulnerability analysis: what could go wrong, what the consequences would be, and how to verify the system handles it. These scenarios are designed so that a future AI session reading them cannot argue the quality standard down.

#### Functional tests

Tests traced to requirements, not generated from source code. Organized into three groups: spec requirements (one test per testable spec section), fitness scenarios (one per QUALITY.md scenario), and boundaries/edge cases (one per defensive pattern from exploration). Every test cites the requirement it verifies.

### Phase 3: Three-pass code review

The code review runs in three passes, each finding different classes of bugs:

**Pass 1 — Structural review.** Read every function body in the project's source tree. For each function, check five mandatory scrutiny areas: error handling (catch blocks that swallow errors, error conditions that return success), resource management (open/close pairing, cleanup in all exit paths), concurrency safety (data accessed from multiple contexts, lock ordering), boundary conditions (off-by-one, empty inputs, integer overflow), and enumeration completeness (switch/case constructs with incomplete coverage).

Pass 1 catches the structural class of defects: race conditions, null pointer hazards, resource leaks, off-by-one errors, type mismatches — problems visible in the code itself. Passes 2 and 3 are needed to find intent violations and cross-requirement contradictions, which Pass 1 cannot reach.

**Pass 2 — Requirement verification.** For each testable requirement from the pipeline, check whether the code satisfies it. This is a pure verification pass — the reviewer's only job is "does the code satisfy this requirement?" Each requirement must get its own SATISFIED or VIOLATED verdict with a specific code citation (file:line). Requirements cannot be grouped into ranges like "REQ-003 through REQ-012 — satisfied" because that hides shallow verification.

Pass 2 catches intent violations — cases where the code doesn't do what the specification says it should. These are invisible to structural review because the code that IS there is correct; the bug is what's missing or what doesn't match the spec.

**Pass 3 — Cross-requirement consistency.** Compare pairs of requirements that reference the same field, constant, range, or security policy. Do numeric ranges match bit widths? Do security policies propagate to all connection types? Do validation bounds in one file agree with encoding limits in another?

Pass 3 catches contradictions where two individually-correct pieces of code disagree about a shared constraint. These bugs are invisible to both structural review and per-requirement verification because each requirement IS satisfied individually — the bug only appears when you compare them.

### Phase 4: Council of Three (multi-model spec audit)

Three independent AI model passes audit the code against the requirements. Why three? Because each model has different blind spots. In practice, different models catch different issues, and the most valuable findings are often the ones only one model catches.

The protocol defines a copy-pasteable audit prompt with guardrails, project-specific scrutiny areas, and a triage process. The triage is the critical step — it uses verification probes (targeted checks that ask "is this actually true?") rather than majority vote or confidence averaging.

**Why not majority vote?** A finding that only one of three auditors catches is disproportionately likely to be a real bug that two models missed. Discarding minority findings by default throws away the most interesting discoveries. Instead, every minority finding gets a re-investigation with fresh evidence.

**Verification probes must produce executable evidence.** When the triage confirms or rejects a finding, it must write a test assertion that mechanically proves the determination — not just prose reasoning. For rejections: an assertion that PASSES, proving the finding is wrong. For confirmations: an assertion that FAILS, proving the bug exists. This exists because in practice, the triage step hallucinated compliance with code — it claimed lines 3527-3528 "explicitly preserve VIRTIO_F_RING_RESET" when those lines actually contained the `default:` branch. Had it been required to write an assertion, the assertion would have failed, exposing the hallucination.

### Phase 5: Reconciliation and TDD

Post-review reconciliation closes the loop: every bug from code review and spec audit is tracked, regression-tested, and closed. Every confirmed bug gets:

- A regression test patch (`BUG-NNN-regression-test.patch`) — mandatory, proves the bug exists
- A fix patch (`BUG-NNN-fix.patch`) — strongly encouraged, proposes a fix
- Red-phase TDD log (`BUG-NNN.red.log`) — proves the regression test fails on unpatched code
- Green-phase TDD log (`BUG-NNN.green.log`) — proves the test passes after applying the fix

The TDD cycle is the strongest evidence a bug is real. A reviewer can disagree with the analysis, but they can't argue with a reproducing test that fails without the patch and passes with it.

**TDD enforcement applies to all runs including iterations (v1.3.49).** Every newly confirmed bug in every run must produce red-phase and green-phase logs. `quality_gate.py` checks for these files and FAILs if they're missing. If the test runner is not available for the project's language, the log file is still created with `NOT_RUN` on the first line and an explanation — the obligation is acknowledged, not silently skipped.

### Phase 6: Self-verification

45 self-check benchmarks validate the generated artifacts against internal consistency rules: requirement counts match across all surfaces, no stale text remains, every finding has a closure status, version stamps are consistent, triage probes include executable evidence, mechanical verification artifacts haven't been tampered with, and every confirmed bug has TDD log files.

---

## Iteration strategies — detailed explanation

After the baseline run, iteration strategies find additional bugs by re-exploring the codebase with different approaches. Each strategy targets a different failure mode of the baseline exploration.

### Why iterate?

A single playbook run explores the codebase through one path. On large codebases, a single run only covers 3-5 subsystems. On any codebase, the exploration path creates blind spots — areas that the first run's structure and focus prevented it from reaching. Iteration compensates by providing multiple independent exploration attempts with different constraints and emphases.

In benchmarking across 10+ open-source repos, iterations typically multiply the baseline bug count by 3-4x: baseline alone finds 1-3 bugs per repo on average, while a full iteration cycle finds 4-10.

### The recommended cycle: gap → unfiltered → parity → adversarial

Each strategy is designed to find a different class of bugs that the previous strategies missed. Running them in order maximizes cumulative yield.

### Strategy: `gap` — find what the previous run missed

**What it does:** Scans the previous run's EXPLORATION.md (using a lightweight coverage map, not loading the full file), identifies subsystems or code areas that were not explored or were explored shallowly, and runs a focused exploration targeting only those gaps.

**What it finds:** Bugs in subsystems the baseline didn't reach. On large codebases with many modules, the baseline run can only cover a subset. Gap fills in the rest.

**When it's most effective:** After a structurally sound baseline that covered a subset of the codebase. If the baseline was weak (few findings, shallow exploration), unfiltered may be a better first iteration than gap.

**How it differs from just re-running the baseline:** Gap is targeted — it knows what was already covered and deliberately avoids re-exploring the same areas. A fresh baseline would re-explore the same high-salience code paths it explored the first time.

### Strategy: `unfiltered` — pure domain-driven exploration without structure

**What it does:** Ignores the playbook's structured three-stage exploration (open exploration → quality risks → selected patterns) entirely. Instead, the agent explores the codebase the way an experienced developer would — reading code, following hunches, tracing suspicious paths. No pattern templates, no applicability matrices, no section format requirements.

**What it finds:** Bugs that the structured approach suppresses by over-constraining exploration. The structured approach excels at systematic coverage but can cause the agent to spend its context budget on format compliance (filling in template sections, checking applicability matrices) rather than deep code reading. Unfiltered removes that overhead and lets domain expertise drive discovery.

**When it's most effective:** On library and framework codebases where the bugs live in API surface inconsistencies, ad-hoc string parsing of structured formats, and edge-case inputs that a domain expert would know to try. Also effective when the baseline found zero bugs — the structure may have been the problem, not the codebase.

**Why it exists separately from baseline:** In benchmarking, the unfiltered domain-driven approach used in earlier skill versions (v1.3.25–v1.3.26) found bugs in web frameworks and HTTP libraries that the structured approach consistently missed. Rather than choosing one approach, the playbook offers both: structure for systematic coverage, unfiltered for discovery depth.

### Strategy: `parity` — cross-path comparison and diffing

**What it does:** Systematically enumerates parallel implementations of the same contract and diffs them for inconsistencies. It identifies groups of code that implement the same logical operation via different paths — transport variants (PCI vs MMIO vs vDPA), fallback chains (primary → fallback → last-resort), setup vs teardown, happy path vs error path, public API overloads — and then compares each pair using a structured checklist.

**The comparison checklist covers six sub-types:**
- **Resource lifecycle parity:** Does teardown release everything setup acquired?
- **Allocation context parity:** Do parallel paths use compatible allocation flags for their lock/interrupt context?
- **Identifier and index parity:** Do parallel paths compute indices the same way for the same logical entity?
- **Capability/feature-bit parity:** Do parallel paths check the same feature bits?
- **Error/exception parity:** Do fallback paths handle errors at least as robustly as primary paths?
- **Iteration/collection parity:** Do parallel paths iterate over the same collections?

**What it finds:** Inconsistencies between code paths that should behave the same way but don't. These bugs only emerge from cross-path comparison — they're invisible when exploring individual subsystems. A reset function that forgets to drain a list that the setup function populated, a fallback path that uses a different index calculation than the primary path, an error handler that's less robust than the happy path.

**When it's most effective:** On codebases with multiple implementations of the same interface (transport backends, protocol versions, sync/async variants). The more parallel paths exist, the more bugs parity will find.

**Why it exists:** In benchmarking on the Linux virtio subsystem, three bugs were found by lining up parallel code paths and spotting differences — not by exploring individual subsystems. The gap, unfiltered, and adversarial strategies all explore areas or challenge decisions, but none explicitly compare parallel paths. Parity fills that gap.

### Strategy: `adversarial` — challenge previous conclusions

**What it does:** Re-investigates what previous iterations dismissed, demoted, or marked SATISFIED. It reads the Demoted Candidates Manifest (findings that were rejected in previous iterations with structured re-promotion criteria), triage dismissals, and code review SATISFIED verdicts — then challenges those decisions with fresh evidence and a lower evidentiary bar.

**What it finds:** Type II errors — real bugs that conservative triage rejected because they looked ambiguous, could be interpreted as "design choices," or lacked dramatic runtime failures. By the adversarial iteration, the remaining undiscovered bugs are precisely the ones that conservative evidence thresholds keep filtering out.

**The lower evidentiary bar:** The baseline and gap strategies rightly demand strong evidence to avoid false positives during initial discovery. The adversarial strategy deliberately relaxes this. A code-path trace showing observable semantic drift (output differs from what spec or contract requires) is sufficient to confirm — you don't need a runtime crash. "Permissive behavior" is not automatically a design choice — if the spec defines the expected behavior and the code deviates, it's a bug.

**When it's most effective:** After gap, unfiltered, and parity have run. It specifically targets the accumulated dismissed findings from all previous iterations. Each dismissed finding has structured re-promotion criteria that tell the adversarial strategy exactly what evidence to gather.

**When to stop iterating:** After the adversarial iteration, returns diminish sharply. Starting a fresh baseline run from scratch often finds more than a fifth strategy would.

---

## Understanding results

### BUGS.md

Each confirmed bug has a heading `### BUG-NNN` with: file:line location, description, severity, spec basis (what documented contract it violates), regression test reference, and fix patch reference.

**Are these real bugs?** In benchmarking, 15 out of 15 spot-checked bugs were verified as real against actual source code. The playbook is conservative — it's more likely to miss bugs (Type II errors) than to report false positives (Type I errors). If BUGS.md says something is a bug, it almost certainly is.

### TDD verification

Each bug should have a red/green TDD cycle proving it's real:
- `quality/results/BUG-NNN.red.log` — the regression test fails on unpatched code (proves the bug exists)
- `quality/results/BUG-NNN.green.log` — the regression test passes after applying the fix patch (proves the fix works)

If these log files are missing, the agent generated the test patches but didn't execute them. This is a known issue with some agents (see "Agent reference"). You can run the TDD cycle manually:

```bash
# Red phase: revert fix, run test
git apply -R quality/patches/BUG-NNN-fix.patch
<test command for your language>
# Green phase: apply fix, run test
git apply quality/patches/BUG-NNN-fix.patch
<test command for your language>
```

### quality_gate.py

The gate script validates all artifacts mechanically. It is the sole mechanical gate — the legacy `quality_gate.sh` was retired in v1.4.5. Target repos install the standalone module at `.github/skills/quality_gate.py` (in the source tree this is a symlink into the `.github/skills/quality_gate/` package, which also ships the 171-test unit-test suite in `quality_gate/tests/`). Run it after the playbook completes:

```bash
python3 .github/skills/quality_gate.py .
```

If it reports FAIL results, the most common causes:
- Missing `quality/patches/BUG-NNN-regression-test.patch` files
- BUGS.md heading format (`### BUG-NNN` not `## BUG-NNN`)
- Missing fields in `tdd-results.json`
- Writeups without inline fix diffs (the presence check uses a case-insensitive regex as of v1.5.1, so ` ```Diff ` and ` ```DIFF ` fences are recognized and will not produce a spurious "no inline fix diffs" FAIL)
- Writeups containing unfilled template sentinels (v1.5.1 check — the five strings `"is a confirmed code bug in \`\`"`, `"The affected implementation lives at \`\`"`, `"Patch path: \`\`"`, `"- Regression test: \`\`"`, `"- Regression patch: \`\`"` are evidence the Phase 5 stub was emitted without hydrating from BUGS.md, which was the bus-tracker-1.5.0 failure mode)
- Writeups whose ` ```diff ` fence is present but contains no `+` / `-` hunk lines other than file headers (v1.5.1 check — a fence with only context lines or only `--- a/…` / `+++ b/…` headers is treated as empty)
- Missing red-phase or green-phase log files (v1.3.49+)
- Missing `quality/results/run-YYYY-MM-DDTHH-MM-SS.json` run-metadata file (v1.4.6 fix — `check_run_metadata` now enforces this)
- `EXPLORATION.md` missing one of the five required section headings: `## Open Exploration Findings`, `## Quality Risks`, `## Pattern Applicability Matrix`, `## Candidate Bugs for Phase 2`, `## Gate Self-Check` (v1.4.6 fix — `_check_exploration_sections` enforces these)
- Zero-bug runs where `BUGS.md` doesn't carry an anchored `## No confirmed bugs` heading (v1.4.6 fix — the sentinel no longer matches free prose containing the word "zero")
- Functional/regression test files whose extension doesn't match the detected project language — both `test_functional.*` and language-native names like `FunctionalTest.java`, `FunctionalSpec.scala`, `functional.test.ts`, `functional_test.go` are now gate-checked for extension match

---

## Submitting findings upstream

After a run produces BUGS.md, what to do with it depends on which bugs you want to submit and whether they cluster into a single defect class.

### Submitting individual bugs as PRs

**Before any tier triage, the threshold question: are you familiar enough with the project's domain, language, and conventions to defend this finding to a maintainer?** A real bug that you can't argue for — because you don't know the domain well enough to anticipate the pushback, cite the right spec, or recognize when a maintainer's "won't fix" reply is correct rather than dismissive — is noise to upstream regardless of whether the tool found a real defect. The right move in that case is to leave the bug in your local triage. The tool found it for your benefit (calibration, learning the codebase, deciding whether to use this dependency), not as a default mandate to push it upstream. This is especially relevant for codebases where the maintainers are world-class engineers who already know about AI-assisted code review and can run these tools themselves if they want — submitting unfamiliar-domain findings to such projects is more likely to burn maintainer goodwill than help. When in doubt, treat the bug as private validation of your own quality assessment, not as a PR pipeline obligation.

A 15-bug BUGS.md typically mixes standout-tier candidates (surprising, specific findings a senior maintainer would describe as "huh, didn't see that"), confirmed-tier candidates (solid bugs that pass the playbook's evidentiary standard but aren't surprising), and probable / candidate findings (flagged for review but not load-bearing). The categorization tagging planned for v1.5.3 will surface these tiers explicitly; until then, the operator picks standouts by reading the writeups and asking "would a senior maintainer of this project find this surprising?" Submit standouts upstream first; batch confirmed-tier with other fixes or save for a quiet release window; don't submit probable or candidate findings without further triage.

For each bug you submit, `quality/writeups/BUG-NNN.md` is designed to be the PR body — bug description, spec basis, code location, regression test, fix patch with inline diff, TDD verification results. The regression-test patch at `quality/patches/BUG-NNN-regression-test.patch` is structurally correct but uses the playbook's generic test infrastructure; most upstream projects expect tests in their existing test directory and harness, so port the test logic to match the project's conventions and verify it still fails on unpatched code and passes after the fix.

Use honest attribution framing: "Found this with the help of an AI-assisted code-review tool. The bug analysis, regression test, and fix patch are in this PR; happy to walk through any of it." That phrasing avoids both overclaiming ("Claude found this bug" — Claude is a model, not a methodology) and underclaiming ("I found this" — the maintainer may ask how, and it's better to be upfront). Title the PR by the bug, not by the methodology; reserve the methodology mention for the PR description. Maintainers care about the defect, not how it was found.

### Defect-class consolidation

If a run produces several BUGS.md entries describing the same underlying defect pattern at different entry points (e.g., six bugs that are all "cached wrapper doesn't invalidate on mutation method X"), file ONE consolidated PR rather than several individual ones. Maintainers prefer to review a defect class as a unit; submitting nine separate PRs for nine instances of the same issue feels mechanical and burns goodwill.

A consolidated PR has one title describing the defect class, one description that frames the class in a paragraph and enumerates the affected entry points (a table works well — one row per individual bug, so maintainers can spot any they think don't apply), one test that exercises all affected entry points in the project's test style, and one fix that addresses the root cause across all entry points. Include a traceability footer listing the QPB BUG-NNN identifiers from the originating run so each entry point can be traced back to the source finding.

The iteration-strategy taxonomy (gap, unfiltered, parity, adversarial) does not currently group bugs by root cause — each strategy finds whatever it finds independently. If two strategies hit the same defect at different sites, BUGS.md gets two separate `### BUG-NNN` entries; consolidating them is the operator's decision at submission time. A defect-class tagging pass is planned post-v1.5.3 (Lever 6 in IMPROVEMENT_LOOP.md); until then, treat each `### BUG-NNN` as one observation and consolidate when you recognize a pattern.

---

## Key techniques explained

This section provides detailed explanations of specific playbook techniques. Use this to answer "how does X work?" and "why does it do Y?" questions.

### Mechanical verification and anti-hallucination

**Problem:** AI models reliably hallucinate the contents of code when summarizing it. The model reads a function with many case labels, reads constants defined elsewhere, and concludes all constants are handled — without actually checking. In one observed case, the model asserted that a kernel function "preserves VIRTIO_F_RING_RESET" when that constant was entirely absent from the code.

**Solution:** For dispatch functions, registries, and any construct where completeness matters, the playbook requires mechanical extraction using shell commands (awk/grep) that cannot hallucinate. The output is saved to a file, verified with an integrity check script, and used as the sole source of truth for downstream artifacts.

**Why an integrity check?** In testing, the model executed the correct extraction command but wrote its own fabricated output to the file instead of letting the shell redirect capture it. The fabricated file included a constant that the real command does not produce. The integrity check re-runs the extraction and diffs against the saved file — any mismatch means the artifact was tampered with.

**Why can't downstream artifacts use their own lists?** A contamination chain was observed in v1.3.17: REQUIREMENTS.md asserted RING_RESET was preserved in a switch, the code review copied the list from REQUIREMENTS.md, three spec auditors inherited the claim from the code review prompt, and the triage accepted it — all without anyone reading the actual code. Requiring mechanical extraction at the source and citation of the mechanical file downstream breaks this chain.

### The contradiction gate

Before closure, the playbook compares executed evidence (mechanical artifacts, regression test results, TDD red-phase failures) against prose artifacts (requirements, contracts, triage, BUGS.md). If they contradict, the executed result wins — the prose artifact must be corrected before proceeding.

This exists because models can reconcile contradictions by changing the evidence rather than the conclusion. If a requirement says "function handles X" but the mechanical extraction shows it doesn't, the model might update the extraction file rather than the requirement. The contradiction gate catches this by requiring that executed evidence is immutable.

### Confidence tiers and traceability

Every requirement traces back to a source with a confidence tier:
- **Tier 1: Formal spec** — written by humans in an authoritative document. Highest confidence.
- **Tier 2: Official docs** — documentation that describes intended behavior but may be outdated.
- **Tier 3: Inferred from source** — deduced from code patterns, comments, or test expectations. Lowest confidence, flagged for review.

The traceability chain runs from gathered docs → requirements → bugs → tests. When a bug is reported upstream, the spec basis cites the exact passage that establishes the expected behavior. "Your code violates section X.Y of your own spec" is a much stronger report than "this looks like it might be a bug."

### Skip guards and the TDD cycle

Regression tests for confirmed bugs include "skip guards" — markers (like `xfail` in pytest, `@Disabled` in JUnit) that prevent the test from running in normal CI. This is because the bug hasn't been fixed yet — the test is supposed to fail. The skip guard ensures it doesn't break the project's test suite.

During the TDD cycle, the skip guard is temporarily removed:
- **Red phase:** Remove guard, run test on unpatched code. It must FAIL (proving the bug exists). Re-enable guard.
- **Green phase:** Remove guard, apply fix patch, run test. It must PASS (proving the fix works). Re-enable guard if the fix will be reverted.

The guard remains in the committed test file until the fix is merged upstream.

### Bug writeups

Each TDD-verified bug gets a self-contained writeup at `quality/writeups/BUG-NNN.md`. This file is designed to be emailed to a maintainer, attached to a Jira ticket, or reviewed outside the repository. It includes the bug description, spec basis, code location, regression test, fix patch with an inline diff, and the TDD verification results. A reviewer can read the writeup and understand the bug without navigating the rest of the quality artifacts.

**Hydration from BUGS.md (v1.5.1).** The Phase 5 prompt now carries a MANDATORY HYDRATION STEP: before writing a writeup, the agent re-opens `quality/BUGS.md`, locates the `### BUG-NNN:` entry, and copies specific fields (Location, Spec basis, Minimal reproduction, Expected / Actual behavior, Regression test, Patches) into specific writeup sections. The gate enforces two mechanical floor checks on the result — any of five template-sentinel strings in the rendered writeup fails the gate, as does a ` ```diff ` fence that contains no `+` / `-` hunk lines (only context lines or only file headers). These checks close the bus-tracker-1.5.0 failure mode where the playbook produced skeletal writeups that passed the legacy gate.

### The evidentiary standard for confirming bugs

The playbook uses a specific evidentiary standard: a code-path trace that demonstrates a specific behavioral violation IS sufficient evidence to confirm a bug. You do NOT need an executed test, a runtime crash, or an integration-level reproduction to confirm a finding. If the spec says the behavior should be X, and the code demonstrably produces Y (traceable through the code path), that is a confirmed bug.

This standard exists because earlier versions set the bar at "runtime proof before confirmation," which is backwards — the TDD protocol provides runtime evidence AFTER confirmation, not as a prerequisite. Setting the bar too high produced zero-bug runs on codebases where bugs were known to exist, because every candidate was deferred pending evidence that could only come from the TDD cycle that runs after confirmation.

### Coverage theater prevention

"Coverage theater" is when tests produce high coverage numbers without catching real bugs. Examples: asserting that imports worked, that dicts have keys, that mocks return what they were configured to return. The quality constitution calls this out explicitly with project-specific examples derived from exploration, so future AI sessions know what NOT to do.

---

## How we improve the playbook

If the user asks how the Quality Playbook is itself maintained or quality-engineered, here is the short version. For full detail, point them at `ai_context/IMPROVEMENT_LOOP.md`.

Each release goes through a Plan-Do-Check-Act loop with **benchmark recovery against pinned ground truth** as the Check step. Two pieces of vocabulary do the work:

**Verification dimensions** are what we *measure* on every release — process compliance (does the run produce the right artifacts? `quality_gate.py` enforces this) and outcome recall (does the run actually find the bugs we know are there? benchmark recovery against `chi-1.5.1`, `virtio-1.5.1`, `express-1.5.1` measures this). A release ships only when both dimensions hold or improve.

**Improvement levers** are what we *change* to make the playbook better. Each lever is a decoupled surface in the codebase that can be tuned without affecting the others. The current inventory: exploration breadth/depth, code-derived vs domain-derived requirements, gate strictness, finalization robustness, mechanical extraction surface (being cleaned up in v1.5.3), and categorization tier policy (planned for v1.5.3). Each lever has a known home in the code or references — see `IMPROVEMENT_LOOP.md` for the file mappings.

The methodology that connects the two is **regression replay**: take a pinned benchmark, roll back to the commit before a known QPB-* bug was fixed, run the playbook against that pre-fix commit. If the playbook finds the bug, the levers are sufficient for that class. If it misses, diagnose which lever needs to be pulled, change it, and re-run — verifying both that the bug is now found and that recall on the rest of the benchmark is preserved.

Two release-gate reviews enforce the loop. Code-bearing changes go through a Council-of-Three nested panel review (3 outer × 3 inner = 9 perspectives) before merge. Docs-only changes to orientation files (this file, `IMPROVEMENT_LOOP.md`, `TOOLKIT_TEST_PROTOCOL.md`, `README.md`, `DEVELOPMENT_CONTEXT.md`) go through the **Toolkit Test Protocol** instead — a panel of LLM sub-agents reads the doc through reader personas (skeptical reviewer, scope-edge adopter, zero-bug interpreter, vocabulary trap, etc.) and findings are converged before each version bump. See `TOOLKIT_TEST_PROTOCOL.md` for the protocol.

The honest framing of where the project is on the formal statistical-process-control trajectory: instrumented and trend-aware, not yet under statistical control in the formal SPC / CMMI level 4 sense. Multi-year horizon. Don't overclaim this when summarizing — the eventual claim depends on not overclaiming today.

## Rate limits and cost management

The quality playbook is a large workload — a full run with iterations can consume 15+ million tokens. This matters for rate limits and costs.

**GitHub Copilot:** Aggressive rate limits. Running 6 repos simultaneously through iteration cycles triggered a 54-hour cooldown. Recommendation: run 2-3 repos at a time, use individual iteration strategies instead of `--strategy all`, and pause between batches.

**Claude Code:** Usage counts against your Claude plan. The Max plan provides the most headroom. A single baseline run on a medium-sized repo is manageable; a full iteration cycle on a large repo (like a Linux kernel driver) is expensive.

**Cursor:** Usage depends on the model selected and the plan. Cursor Pro has a monthly API budget for premium models (e.g., $20/month); a single large Opus call can consume most of it. When the budget is exhausted, Cursor falls back to weaker models that lack the reasoning depth for effective bug finding. Stagger runs and monitor usage.

**General:** The playbook's multi-pass mode (explore in one session, generate artifacts in another) uses shorter sessions that each fit in a smaller context window. This can reduce per-session token usage compared to single-pass mode, at the cost of more manual coordination.

## Language support

The playbook works with any programming language. It adapts its exploration patterns, test generation, and regression test framework to the project's language:

- **Go:** `go test`, `t.Skip()` guards, `go vet` for static analysis
- **Python:** `pytest` with `@pytest.mark.xfail(strict=True)`, `mypy` for type checking
- **Java:** Maven/Gradle + JUnit 5, `@Disabled` annotations
- **Rust:** `cargo test`, `#[ignore]` attributes, `#[should_panic]` for panic-manifesting bugs
- **TypeScript/JavaScript:** Jest (`test.failing`) or Vitest (`test.fails`), ESLint
- **C:** Source-inspection tests via shell scripts (grep/awk on source files) for kernel-style projects where a full build environment may not be available

If the project's test runner isn't available (e.g., a C kernel module on a machine without the kernel build environment), the playbook records `NOT_RUN` in the TDD log with an explanation — it doesn't fail silently.

## Gathered documentation

The playbook works best when it has access to project documentation — specs, RFCs, API docs, design docs. If you have these, put them in a `reference_docs/` directory in the repo root before running the playbook (citable specs under `reference_docs/cite/`, everything else at the top level). The playbook will use them as the ground truth for what the code should do, which dramatically improves bug-finding accuracy.

If no docs exist, the playbook derives requirements from the code itself — comments, function signatures, error messages, test expectations. This works but produces weaker spec-basis evidence for each bug.

## Troubleshooting

**Zero bugs found on a non-trivial codebase:**
- Check which model the agent used. Code-generation models (Codex, small/fast variants) lack the reasoning depth for exploration. Switch to Claude Opus, Claude Sonnet, or GPT-5.4.
- Check that `.github/skills/SKILL.md` exists and was read. Some agents skip reading referenced files.
- Try the unfiltered iteration strategy — it removes structural constraints that can over-constrain weaker models.

**Agent found bugs but no TDD log files:**
- This is a known issue with Copilot and Cursor (see "Agent reference"). The agent wrote "TDD verified" in the JSON without actually running the tests.
- Run the TDD cycle manually using the bash template in the "TDD verification" section above.
- Or ask the agent in a follow-up prompt: "Read the TDD execution enforcement section in .github/skills/SKILL.md and execute the red/green TDD cycle for every confirmed bug."

**Rate limited (Copilot 54-hour cooldown):**
- Wait for the cooldown to clear. Reduce parallelism on the next batch.
- Switch to Claude Code or Cursor for immediate runs while waiting.
- Use individual iteration strategies instead of `--strategy all`.

**Cursor contamination from sibling directories:**
- Move the target repo to an isolated directory before opening in Cursor.
- Or open only the repo folder, not a parent directory.

**quality_gate.py fails:**
- Read the output carefully — each FAIL line tells you exactly what's wrong.
- The most common fix: missing patch files. Ask the agent to generate them.
- Second most common: heading format. BUGS.md must use `### BUG-NNN` (three hashes), not `## BUG-NNN`.
- Missing TDD log files (v1.3.49+): the agent generated tests but didn't run them. Ask the agent to execute the TDD cycle, or run it manually.

**Phase 0 finds seeds from a previous run:**
- This is expected if you're re-running on a repo that already has `quality/` artifacts from a prior run.
- If you want a clean baseline, delete or rename the existing `quality/` directory first.
- If you want to build on prior findings, leave it — Phase 0 will import previously confirmed bugs as seeds.

**How to verify bug fixes (recheck mode):**
- After the user fixes bugs from BUGS.md, say "recheck" to the playbook agent.
- Recheck reads BUGS.md, checks each bug against the current source, and reports which are fixed.
- For each bug, it tries: (1) reverse-applying the fix patch — if it succeeds, the fix is applied; (2) source inspection of the cited file:line; (3) optionally running the regression test patch.
- Results are written to `quality/results/recheck-results.json` and `quality/results/recheck-summary.md`.
- Recheck takes 2-10 minutes. It does NOT find new bugs — only verifies fixes for previously found bugs.
