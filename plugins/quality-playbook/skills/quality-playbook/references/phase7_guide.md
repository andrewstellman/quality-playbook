# Phase 7: Present, Explore, Improve — detail

*Extracted from SKILL.md in v1.5.10 (instr 052). SKILL.md keeps the `## Phase 7` heading + the canonical-treatment paragraph + a pointer here; this file carries Part 1 (summary table), Part 2 (drill-down), Part 3 (improvement menu), executing each improvement path, and iteration.*

### Part 1: The Summary Table

Present a single table the user can scan in 10 seconds:

```
Here's what I generated:

| File | What It Does | Key Metric | Confidence |
|------|-------------|------------|------------|
| REQUIREMENTS.md | Testable requirements with use cases | N requirements, N use cases | ██████░░ Medium — solid baseline from 5-phase pipeline, improves with refinement passes |
| QUALITY.md | Quality constitution | 10 scenarios | ██████░░ High — grounded in code, but scenarios are inferred, not from real incidents |
| Functional tests | Automated tests | 47 passing | ████████ High — all tests pass, 35% cross-variant |
| RUN_CODE_REVIEW.md | Three-pass code review | 3 passes | ████████ High — structural + requirement verification + consistency |
| RUN_INTEGRATION_TESTS.md | Integration test protocol | 9 runs × 3 providers | ██████░░ Medium — quality gates need threshold tuning |
| RUN_SPEC_AUDIT.md | Council of Three audit | 10 scrutiny areas | ████████ High — guardrails included |
| RUN_TDD_TESTS.md | TDD verification protocol | N bugs to verify | ████████ High — mechanical red-green cycle with spec traceability |
```

Adapt the table to what you actually generated — the file names, metrics, and confidence levels will vary by project. The confidence column is the most important: it tells the user where to focus their attention.

**Confidence levels:**
- **High** — Derived directly from code, specs, or schemas. Unlikely to need revision.
- **Medium** — Reasonable inference, but could be wrong. Benefits from user input.
- **Low** — Best guess. Definitely needs user input to be useful.

After the table, add a "Quick Start" block with ready-to-copy prompts for executing each artifact:

```
To use these artifacts, start a new AI session and try one of these prompts:

• Run a code review:
  "Read quality/RUN_CODE_REVIEW.md and follow its instructions to review [module or file]."

• Run the functional tests:
  "[test runner command, e.g. pytest quality/ -v, mvn test -Dtest=FunctionalTest, etc.]"

• Run the integration tests:
  "Read quality/RUN_INTEGRATION_TESTS.md and follow its instructions."

• Start a spec audit (Council of Three):
  "Read quality/RUN_SPEC_AUDIT.md and follow its instructions using [model name]."

• Run TDD verification for confirmed bugs:
  "Read quality/RUN_TDD_TESTS.md and follow its instructions to verify all confirmed bugs."
```

Adapt the test runner command and module names to the actual project. The point is to give the user copy-pasteable prompts — not descriptions of what they could do, but the actual text they'd type.

After the Quick Start block, add one line:

> "You can ask me about any of these to see the details — for example, 'show me Scenario 3' or 'walk me through the integration test matrix.'"

### Part 2: Drill-Down on Demand

When the user asks about a specific item, give a focused summary — not the whole file, but the key decisions and what you're uncertain about. Examples:

- **"Tell me about Scenario 4"** → Show the scenario text, explain where it came from (which defensive pattern or domain knowledge), and flag what you inferred vs. what you know.
- **"Show me the integration test matrix"** → Show the run groups, explain the parallelism strategy, and note which quality gates you derived from schemas vs. guessed at.
- **"How do the functional tests work?"** → Show the three test groups, explain the mapping to specs and scenarios, and highlight any tests you're least confident about.

The user may go through several drill-downs before they're ready to improve anything. That's fine — let them explore at their own pace.

### Part 3: The Improvement Menu

After the user has seen the summary (and optionally drilled into details), present the improvement options:

> "Five ways to make this better:"
>
> **1. Review requirements interactively** — Read `quality/REVIEW_REQUIREMENTS.md` for a guided walkthrough of the requirements organized by use case. You can pick specific use cases to drill into, or walk through all of them sequentially. A different model can also fact-check the completeness report (cross-model audit). Good for: finding gaps the pipeline missed.
>
> **2. Refine requirements with a different model** — Read `quality/REFINE_REQUIREMENTS.md` and run a refinement pass. You can run this with any AI model — Claude, GPT, Gemini — and each will catch different gaps. Run as many models as you want until you hit diminishing returns. Each pass backs up the current version and logs changes in `quality/VERSION_HISTORY.md`. Good for: pushing requirements from the baseline toward completeness.
>
> **3. Review and harden other items** — Pick any scenario, test, or protocol section and I'll walk through it with you. Good for: tightening specific quality gates, fixing inferred scenarios, adding missing edge cases.
>
> **4. Guided Q&A** — I'll ask you 3-5 targeted questions about things I couldn't infer from the code: incident history, expected distributions, cost tolerance, model preferences. Good for: filling knowledge gaps that make scenarios more authoritative.
>
> **5. Feed in additional documentation** — The requirements pipeline works better with more intent sources. Point me to any of these and I'll use them to refine the requirements and quality constitution:
>   - Exported AI chat history (Claude, Gemini, ChatGPT exports, Claude Code transcripts)
>   - Slack or Teams channels where the project was discussed
>   - Email threads, Jira/Linear tickets, or GitHub issues about the project
>   - Design documents, architecture decision records, or meeting notes
>   - Newsgroup posts, forum discussions, or mailing list archives
>
>   You can use tools like Claude Cowork, GitHub Copilot, or OpenClaw to connect to these sources and gather them into a folder, then point me at the folder. Good for: grounding scenarios and requirements in real project history instead of inference.
>
> "You can do any combination of these, in any order. Which would you like to start with?"

### Executing Each Improvement Path

**Path 1: Review requirements interactively.** Point the user to `quality/REVIEW_REQUIREMENTS.md` and offer to walk through it together. The protocol supports self-guided (pick use cases), fully guided (sequential walkthrough), and cross-model audit (different model fact-checks the completeness report). Progress is tracked in `quality/REFINEMENT_HINTS.md` so the user can pick up where they left off.

**Path 2: Refine requirements with a different model.** Point the user to `quality/REFINE_REQUIREMENTS.md`. Each refinement pass: backs up the current version to `quality/history/vX.Y/`, reads feedback from REFINEMENT_HINTS.md, makes targeted improvements, bumps the minor version, and logs changes in VERSION_HISTORY.md. The user can run this with Claude, GPT, Gemini, or any other model — each catches different blind spots. Run until diminishing returns.

**Path 3: Review and harden other items.** The user picks a scenario, test, or protocol section. Walk through it: show the current text, explain your reasoning, ask if it's accurate. Revise based on their feedback. Re-run tests if the functional tests change.

**Path 4: Guided Q&A.** Ask 3-5 questions derived from what you actually found during exploration. These categories cover the most common high-leverage gaps:

- **Incident history for scenarios.** "I found [specific defensive code]. What failure caused this? How many records were affected?"
- **Quality gate thresholds.** "I'm checking that [field] contains [values]. What distribution is normal? What signals a problem?"
- **Integration test scale and cost.** "The protocol runs [N] tests costing roughly $[X]. Should I increase or decrease coverage?"
- **Test scope.** "I generated [N] functional tests. Your existing suite covers [other areas]. Are there gaps?"
- **Model preferences for spec audit.** "Which AI models do you use? Have you noticed specific strengths?"

After the user answers, revise the generated files and re-run tests.

**Path 5: Feed in additional documentation.** The user points you to additional intent sources — chat history, Slack exports, email threads, Jira tickets, design docs, meeting notes, forum archives. These contain design decisions, incident history, and quality discussions that didn't make it into formal documentation.

1. Scan for index files and navigate to quality-relevant content (same approach as Step 0, but now with specific targets — you know which requirements need grounding, which scenarios need thresholds, which gaps need closing).
2. Extract: incident stories with specific numbers, design rationale for defensive patterns, quality framework discussions, cross-model audit results, and behavioral contracts that weren't visible from the code alone.
3. Feed findings into `quality/REFINEMENT_HINTS.md` as new feedback items, then run a refinement pass to update the requirements.
4. Revise QUALITY.md scenarios with real incident details. Update integration test thresholds with real-world values. Re-run tests after revisions.

If the user already provided chat history in Step 0, you've already mined it — but they may want to point you to specific conversations, connect additional sources, or ask you to dig deeper into a particular topic.

### Iteration

The user can cycle through these paths as many times as they want. Each pass makes the quality playbook more grounded. When they're satisfied, they'll move on naturally — there's no explicit "done" step.
