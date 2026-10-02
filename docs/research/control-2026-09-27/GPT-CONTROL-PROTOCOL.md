# Control arm: standard code review with GPT (Sol and Terra)

This is the control condition for the Quality Playbook study. The question: when an ordinary AI code review is run on the same code at the same commit, with a standard review prompt and no Quality Playbook method, does it find the same defects? A Claude control arm (Opus and Sonnet) runs the identical prompt and scopes separately.

## What the orchestrating session must do, and must not do

- **Do not read anything else in this repository.** Not `evidence/`, not `docs/research/` beyond the three files named below, not `repos/` beyond the checkouts you create. Those folders contain the answers. In this folder, open only `GPT-CONTROL-PROTOCOL.md`, `STANDARD_REVIEW_PROMPT.md` and `SCOPES.md`. Do not open `results/`, `oracle-test/`, `PREDICTIONS.md`, `CLAUDE-SCORING.md` or `run-gson-control.sh`; write only to `results/`. The sub-agents must be even more isolated: give each one only the review prompt, its scope row, and the path to its checkout.
- Never push, open a PR or issue, comment, or post anything.
- Never fabricate. Record exactly what each sub-agent returned.

## Setup

Clone each repository at its pinned commit into `~/Documents/QPB/repos/control-2026-09-27/<repo>/` (that path is git-ignored). The pins and review scopes are in [SCOPES.md](SCOPES.md):

`git clone --filter=blob:none <url> <dir> && git -C <dir> checkout --detach <commit>`

After cloning, remove the remote (`git -C <dir> remote remove origin`) so a sub-agent can't fetch newer history. Newer history contains the fixes for some defects.

## Runs

**Ten runs per model per repository:** 7 repositories × 2 models (Sol, Terra) × 10 runs = 140 sub-agent runs. gson is not one of the seven; it runs separately through `run-gson-control.sh`. Repeating runs measures run-to-run variance: a defect found in 0 of 10 runs is a much stronger result than 0 of 1.

- Codex runs three sub-agents at a time, so batch them. Order doesn't matter.
- Every run must be a **fresh sub-agent** with no memory of earlier runs. Never reuse a sub-agent, and never show one run's output to another.
- Number the runs 01–10 for each model and repository.
- Each sub-agent may copy its checkout into its own scratch directory and run code there. It must not modify the shared checkout. Give each run its own scratch directory, for example `$TMPDIR/qpb-control/<model>-<repo>-runNN/`, and delete it when the run finishes.

Each sub-agent gets exactly this, and nothing else:

1. The full text of [STANDARD_REVIEW_PROMPT.md](STANDARD_REVIEW_PROMPT.md), verbatim.
2. Its row from SCOPES.md, and the line: "Your checkout is at `<absolute path>`. The review scope is relative to that directory."
3. The line: "Your scratch directory is `<absolute path>`. Do not modify the checkout itself. Do not use the web or fetch any code or packages from the network."
4. The line: "Write your review to `<absolute path of the output file>`."

The no-network line is there because several Claude control runs fetched the published package to diff against the checkout. That broke the prompt's no-web rule, and upstream code can contain the fixes.

Do not add hints, tell the sub-agent this is a study, or mention Quality Playbook, the other arm, or any expected defects. Do not paraphrase the prompt.

## Output

Each sub-agent writes `~/Documents/QPB/docs/research/control-2026-09-27/results/<model>-<repo>-runNN.md`, for example `results/sol-aiohttp-run01.md`. At the top of the file the orchestrating session adds a header block:

```
model: <exact model name as shown in the app>
repo: <repo>
pinned commit: <sha>
date/time started and finished:
tools the sub-agent used (read files, ran commands, ran tests):
interruptions or errors:
network access attempted (yes/no, and what):
```

The body is the sub-agent's review, unedited.

When all 140 are done, write `results/GPT-RUN-LOG.md` with one line per run: model, repo, run number, start/finish, number of defects reported, and any problems, including any network access. Don't evaluate the findings; scoring is done separately, blind to which arm produced them.
