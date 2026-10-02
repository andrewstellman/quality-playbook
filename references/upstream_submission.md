# Prepare Upstream Submissions (Phase 7 path)

*v1.6.1 [R]. The review-and-submission process from the 2026-09 campaign, run by the skill. The operator invokes it from the Phase 7 improvement menu (`references/phase7_guide.md`). It never starts on its own.*

This path takes confirmed bugs from `quality/BUGS.md` to upstream pull requests or issues: policy check, shortlist, confirmation, fix, review panel, then one bug at a time for the operator to submit. The operator submits. The skill prepares, explains, and records.

## Guardrails (binding)

- **The skill never submits.** It never marks a PR ready, never comments upstream, never merges, and never runs a `submit.sh` unless the operator explicitly asks in this session.
- **One bug at a time.** Present one bug, then stop. No schedules ("two today, three tomorrow"), no batching several bugs into one presentation, no queuing the next bug in the same message.
- **Policy first, and the project's policy wins.** Step 1 runs before anything else. If the project bans AI-assisted contributions or closes outside reports, stop and say so.
- **No security-angle PRs.** A finding with a security angle never becomes a public PR or issue; note it for private disclosure (the project's `SECURITY.md` or advisory process) and set it aside.
- **Disclosure line on every submission.** Default: "Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change." Extend it with whatever `POLICY.md` requires (model name, how it was used, a changelog line).
- **No agent trailers.** The commit is authored by the operator. No `Signed-off-by` or `Co-Authored-By` from the agent. If the project requires DCO sign-off, the operator adds it.
- **Side-effect rule.** A fix that is correct but would hurt existing users in a way they would not expect is dropped, not submitted.
- **Nesting rule.** Subagents cannot spawn subagents (`references/orchestrator_protocol.md`). The parent session spawns every confirmer, fixer, and panel reviewer below and passes results between them.
- **Claims rules.** Every PR, issue, commit message and REVIEW.md follows `references/claims_rules.md`. A specific behavioural claim ("X does not do Y") is run before it is written.

## Files

Everything lives under `quality/upstream/` in the target repo:

| Path | Written by | Contents |
|---|---|---|
| `POLICY.md` | Step 1 | The project's contribution rules |
| `SHORTLIST.md` | Step 2 | Candidates, reasons, set-asides |
| `scripts.json` | Steps 3, 6 | Spec for `upstream_scripts.py` |
| `dup-search.sh`, `dup-search.out` | generator; operator | Duplicate search and its output |
| `<slug>/CONFIRMATION.md` | Step 3 | Confirmer's report |
| `<slug>/red.log`, `green.log`, `revert.log`, `suite.log` | Step 4 | Fixer's test logs |
| `<slug>/0001-*.patch`, `PR.md` or `ISSUE.md` | Step 4 | The patch and the exact text |
| `<slug>/panel/<ROLE>.md`, `<slug>/SYNTHESIS.md` | Step 5 | Reviews and the verdict matrix |
| `<slug>/REVIEW.md` | Step 6 | What the operator reads before submitting |
| `<slug>/submit.sh`, `<slug>/verify.sh` | generator | Operator-run scripts |
| `<slug>/STATUS.md` | Steps 6, 7 | One-screen status |

Slugs are `<project>-<short-name>` in `[A-Za-z0-9._-]`, e.g. `cobra-suggest-runes`.

## Step 1: Contribution-policy check (first, always)

Read the target's `CONTRIBUTING*`, `AGENTS.md`, `CLAUDE.md`, `.github/` (PR and issue templates, any AI or assistant guidelines; also the org-level `.github` repo if the target has none), `CODE_OF_CONDUCT*`, the CLA or DCO, `SECURITY.md`, and the docs' "contributing" pages. Write `quality/upstream/POLICY.md`:

```
# Contribution policy: <owner/repo>  (read <date>)
AI policy: banned | allowed with conditions | silent — <quote, file:line or URL>
Conditions: <e.g. "certify you fully understand the code"; model named in commit message>
Outside reports: open | closed — <quote>
Issue first: yes | no — <quote>
PRs from non-collaborators: allowed | issues only
CLA / DCO: <none | CLA bot | DCO sign-off required>
Changelog: <none | newsfragment dir + naming | CHANGES entry>
Target branch: <name>
PR template: <path or none>; required sections: <list>
Disclosure line: <the default line, extended as the rules above require>
Sources read: <list of files and URLs>
```

If the AI policy is **banned**, or outside reports are **closed**: tell the operator, quote the rule, and stop this path. Examples from the 2026-09 campaign: one project banned AI contributions; one was closed to outside reports; one required human authorship; one limited PRs to collaborators (issues only); one required an issue first, the model and its use in the commit message, and an AI line in the changelog.

## Step 2: Shortlist, then stop

From `quality/BUGS.md` and `quality/bugs_manifest.json`, propose **3–4 bugs**. Prefer bugs that:

- rest on a requirement from outside the code: a Tier 1/2 citation in `reference_docs/cite/`, quoted verbatim and found by grep;
- look fine in isolation (the defect is a mismatch with the cited behaviour, not a code smell);
- have a small fix (a few lines plus one test);
- have a real user consequence you can state in one sentence;
- are **not** named in the gate's `── Bug evidence ──` line "rest on a requirement the reviewers questioned" (`quality/results/quality-gate.log`).

Set aside every bug with a security angle: list it with one line, "possible security impact; report privately via <SECURITY.md / advisory URL>, not as a PR".

Write `SHORTLIST.md` and show the operator a table: bug ID, title, cited requirement (file:line), fix size, user consequence, and why it was picked or set aside. Then **stop for the operator's pick.** Do not start Step 3 until the operator names the bugs.

## Step 3: Confirm (one fresh confirmer per picked bug)

The parent spawns one fresh-context confirmer subagent per picked bug, with this brief (fill the brackets):

> You are confirming one candidate bug from a Quality Playbook run. Find out whether it is real; do not just agree with the report. Inputs: the `quality/BUGS.md` entry for [BUG-ID], `quality/patches/` if present, the citable docs in `reference_docs/cite/`, and a scratch clone of the target at [path] (never edit the target repo itself). Steps: (1) restate the claim in one sentence: input, actual, expected, and the source of "expected"; (2) write a repro that prints the actual behaviour and exits 1 if the bug is present, 0 if not; run it and paste the output verbatim; (3) check the expected side: does the cited doc say that (quote it with file:line, grep to prove it)? Does a test, comment, changelog entry or closed issue make the current behaviour intentional? (4) duplicate search across issues **and** open PRs: if you can reach the forge, search it and give the closest match (number, title, state) or "none found" with your queries; if you cannot, write your queries under "dup queries" so the parent can generate `dup-search.sh`; (5) security angle: yes/no, one line; (6) verdict: CONFIRMED / DUPLICATE (cite) / NOT-A-BUG (why) / UNCLEAR (what a maintainer must decide) / COULD-NOT-RUN (what blocked you). Never push, post, comment, or open anything. Return, under 60 lines: id and title; claim; verdict; repro source; verbatim output; expectation check; duplicate search or dup queries; security line; likely maintainer pushback.

The parent saves each report to `<slug>/CONFIRMATION.md`.

**Duplicate search when `gh` is not available to the agent.** Put each candidate's queries in `scripts.json` (`dup_queries`), run the generator (see "Scripts"), and ask the operator to run `bash quality/upstream/dup-search.sh` and give you `quality/upstream/dup-search.out`. Read that file before giving any bug a final CONFIRMED. A query block reading `FAILED` counts as not searched.

Only CONFIRMED bugs go on. A security "yes" moves the bug to the set-aside list.

## Step 4: Fix (one fixer per confirmed bug)

The parent spawns one fixer subagent per confirmed bug:

> Produce a minimal, mergeable fix for ONE confirmed bug. Change only what the bug requires. Inputs: the BUGS.md entry, `<slug>/CONFIRMATION.md`, `quality/upstream/POLICY.md`, the citable docs. Work in a fresh clone: `git clone -q <target> <scratch>/<slug>`; set `user.name` / `user.email` to the operator's identity [given]. Read the project's CONTRIBUTING and PR template and 2–3 recent merged outside bug-fix PRs to copy their style. Steps: (1) test first, in the existing test file that covers the feature, named and written like its neighbours; run it: it fails for the claimed reason (read the assertion text) → `red.log`; (2) smallest code change that fixes it; (3) touched test file passes, and the full suite (or the whole package suite if the full one is impractical; say which) has no new failures → `green.log`, `suite.log`; run the project's formatter/linter on touched files; (4) revert only the source change, confirm the test fails again → `revert.log`; restore; (5) add the changelog entry `POLICY.md` requires; (6) commit: subject in the repo's style (≤ 72 chars), body 2–4 lines, the AI disclosure `POLICY.md` requires, no trailers, no Signed-off-by, no Co-Authored-By; (7) `git format-patch -1`; (8) write `PR.md` (or `ISSUE.md` for issue-first projects): first line `**Title:** <title>`, then the project's template if it has one, else: a minimal repro (actual vs expected), one or two sentences of cause with a file reference, one sentence on the fix, the doc/RFC sentence it relies on (verbatim, with where it lives); at most ~15 lines of prose; last line the disclosure line from `POLICY.md`. Follow `references/claims_rules.md`. Never push or post. Return under 40 lines: files changed (+/−), test name, red/green/revert key lines verbatim, suite result, lint result, commit subject, anything you were unsure about.

The parent copies the patch, the text and the logs into `<slug>/`.

## Step 5: Review panel

The parent spawns every reviewer; reviewers never spawn anyone. Give each reviewer a packet per bug: the patch, `PR.md`/`ISSUE.md`, `CONFIRMATION.md`, `POLICY.md`, the cited docs, and the path of the fixed clone (base = `HEAD~1`; never modify it; experiments go in the reviewer's own scratch clone).

**Default roster: the full panel below.** A smaller roster is the operator's explicit choice; record the choice and who chose it in `REVIEW.md`. If the runtime lets you choose subagent models, use the strongest model for the O-roles and a faster one for the S-roles and executors; otherwise record which model ran.

Charters (one per reviewer):

- **EXEC-A — executor.** In a scratch clone at `HEAD~1`: apply only the test part of the patch, confirm the new test fails for the claimed reason (read the assertion); apply the rest, confirm it passes; revert only the source part, confirm it fails again; run the touched test file and the suite; run the confirmer's repro. End with a table: red | green | revert | suite | repro | PASS/FAIL.
- **EXEC-B — executor.** Everything EXEC-A does, independently, plus 3 edge inputs of its own choosing run against base and fixed.
- **O1 — maintainer.** Read the diff as this project's maintainer, with its conventions and recent history (git log, recent merged PRs). Would you merge it as written? What would you ask to change?
- **O2 — security.** Does the fix add or remove security-relevant behaviour? Does the text frame something as security that isn't, or miss a consequence that is?
- **O3 — correctness.** Try to break the fix: inputs or configurations where the fixed code is still wrong or newly wrong, especially ones the new test doesn't build. Write and run small tests.
- **O4 — not-a-bug.** Argue the maintainer's side as hard as the evidence allows: intended, documented, tested, not worth the churn, better fixed elsewhere, previously declined. Check upstream issues and PRs. Concede only where source or docs force you, and quote what forced you.
- **O5 — slop (A).** A maintainer tired of AI PRs: text out of proportion to the change, claims beyond the evidence, restating the diff, unrelated changes, off-style tests, generated-sounding padding. Propose exact rewrites.
- **S1 — code readability.** Naming, structure, comments, consistency with the surrounding code and the project's idiom.
- **S2 — test readability.** Would the test catch a regression, fail for the right reason, and read like its neighbours?
- **S3 — slop (B).** O5's charter, independently.
- **S4 — QA coverage.** Untested paths the fix touches, missing negative cases, reliance on implementation details.
- **S5 — compat.** Every behaviour change for existing users, including users who rely on the old behaviour. Apply the side-effect rule: name who is affected, what happens to them, how likely; judge acceptable or bad enough to drop. Does the text state each change?
- **S6 — performance.** Cost on hot paths the fix touches; measure if a regex, loop or allocation changed.
- **S7 — citations.** Every factual claim in the PR/issue text and commit message: true of the code and traceable (doc sentence verbatim, RFC/PEP text, file:line, issue number). Run every specific behavioural claim; flag anything unverifiable or wrong.
- **S8 — compliance.** Check against `POLICY.md` and the repo: commit style, tests, changelog entry, DCO/CLA, PR template, AI-disclosure rules, licence, author identity in the patch. Would it be rejected on process grounds?

**Protocol.**

1. **Blind first.** Each reviewer writes an initial verdict per bug from the patch, the text and the source **before** reading `CONFIRMATION.md` or any other reviewer's output. After that it may read `CONFIRMATION.md` and add an "after reading" note instead of rewriting.
2. **Verdicts:** `SHIP` | `FIX-REQUIRED` (submit after the listed changes) | `REJECT` (should not be submitted) | `DROP` (correct, but a side effect on existing users is bad enough to drop it). Each with confidence (high/medium/low) and numbered findings citing file:line or a quote and saying what must change.
3. Each reviewer writes `<slug>/panel/<ROLE>.md` (under ~150 lines) and returns it as text. Never fabricate; paste command output verbatim; say what was not checked.

**Synthesis** (`<slug>/SYNTHESIS.md`, written by the parent):

```
| Item | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| <slug> | S | S | F | S | S | F | F | S | S | S | S | D | S | F | S |
```

S = SHIP, F = FIX-REQUIRED, R = REJECT, D = DROP, – = not run. Under the matrix, one bullet per item: the findings that must change, each with the reviewers who raised it.

**After the synthesis.**

- **Text-only fixes** (PR/issue text, commit message): apply them, and note each in `REVIEW.md`'s review history.
- **Code revisions** get a focused re-review: both executors plus every reviewer who flagged the item, each given the first panel's findings and the revision, with the side-effect rule applied to every behaviour change. Repeat until they say SHIP or the item is dropped.
- **Any REJECT or DROP** goes to the operator as a decision; the side-effect rule is binding, so a DROP is not overridden by the skill.

## Step 6: Prepare one bug at a time, then stop

For one surviving bug, re-check upstream (default-branch head; `git apply --check` of the patch on it), re-run the knock-on check, generate its scripts, write `<slug>/REVIEW.md`, and give the same explanation in chat. Then **stop**. Do not mention the next bug.

`REVIEW.md` shape (the 2026-10 cobra submission used it):

```
# <project>: <one-line bug title>

Status: **ready for the operator's review.**   (updated at each change)

## The project
<what it does, one or two sentences, with the repo link>

## The bug
<expected behaviour and its source, quoted with file:line or URL; what actually
happens; why it went unnoticed>

## The fix
<how it works, then the diff>

## Regression test
- Red: <the failure line, verbatim>
- Green: <touched file passes; full suite result>
- Revert: <fails again for the same reason>
- Logs: red.log, green.log, revert.log, suite.log

## Knock-on effects (run <date>)
- Callers of the changed code: <list, file:line>
- Before/after on ordinary inputs: <table, freshly run>
- Behaviour changes for existing users: <each one, judged under the side-effect rule>

## Review history
- Confirmed: CONFIRMATION.md
- Panel: SYNTHESIS.md (roster: full | <reduced, chosen by the operator on <date>>)
- Re-review: <if any>; text fixes applied: <list>
- Upstream check (<date>): <default branch> at <sha>; patch applies cleanly: yes/no

## Things to know before submitting
<related open PRs/issues; CLA/DCO steps; policy steps from POLICY.md; likely pushback>

## The PR as it will be submitted
**Title:** <title>
> <body, exactly as in PR.md>

## To submit
    bash quality/upstream/<slug>/submit.sh      (SKIP_TESTS=1 skips the local test run)
<what the script does; that it opens a draft; what it does not do>

## Submission record
(empty until the operator submits)
```

Also write `<slug>/STATUS.md` with `status: ready`.

## Step 7: Record

After the operator runs `submit.sh` and pastes its output:

1. Ask the operator to run `bash quality/upstream/<slug>/verify.sh <URL>` (or run it yourself if the operator asks and `gh` is available). It writes `verify.pr.json` + `verify.pr.diff` (or `verify.issue.json`).
2. Check the title and body in the JSON against `REVIEW.md`, character for character.
3. Check the diff: `python3 <install_root>/bin/upstream_scripts.py --compare-diff quality/upstream/<slug>/<patch> quality/upstream/<slug>/verify.pr.diff` must print `MATCH`. The commit hash differs from the local one because `git am` re-creates the commit; the blob hashes must not.
4. Fill in the Submission record: date; PR or issue link and number; head branch and commit; what was verified; bot actions (CLA, CI); what remains on the operator's side (sign a CLA, mark ready); maintainer responses. Update the `Status:` line at the top.
5. Update `<slug>/STATUS.md`. Later responses, revisions, merges or closures are appended to the same record.

`STATUS.md` has exactly these lines:

```
status: <value>
title: <one-line description>
link: <PR / issue / commit URL, or ->
updated: <YYYY-MM-DD>
note: <one line>
```

Status values: `merged`, `open`, `sent` (mailing list), `ready` (reviewed, not yet presented), `needs-work`, `held`, `decision` (waiting on the operator), `dropped`, `not-filed` (project policy or a failed fix), `duplicate`, `maintainer-view` (needs a maintainer's view rather than a patch), `ruled-out` (intended behaviour).

## Scripts

Never hand-write the operator's scripts. Write `quality/upstream/scripts.json` and run:

```
python3 <install_root>/bin/upstream_scripts.py quality/upstream/scripts.json quality/upstream
```

Spec fields (see the script's docstring for the full list): `upstream` (owner/repo), optional `expected_login`, and `bugs`: each with `slug`, optional `dup_queries`, and, once a patch exists, `branch`, `patch`, `title`, `body_file` (paths relative to `quality/upstream/<slug>/` or absolute), optional `kind` (`pr` default, `issue` for issue-first projects), `base` (from `POLICY.md`'s target branch), `test_command`, and `post_create` (`{"rename": {"from": "...", "to": "...{pr_number}..."}}`, e.g. a newsfragment named after the PR).

What the generated scripts do:

- **`dup-search.sh`** (per run): `gh search issues` and `gh search prs` for every query, scoped to the upstream repo, all into `dup-search.out`.
- **`<slug>/submit.sh`** (per bug): `set -euo pipefail`; checks `gh` is logged in; reads the default branch with `gh repo view`; forks if needed; clones to `${QPB_WORK_DIR:-$HOME/src/pr-work}/<repo>` if absent; adds the `upstream` remote; branches from the upstream base and refuses if the branch exists; `git am` with an abort message; runs `test_command` unless `SKIP_TESTS=1`; pushes to the fork; opens a **draft** PR with `--body-file` (or, for `kind: issue`, opens the issue with a compare link substituted for `__COMPARE__` and prints the next step); runs any post-create rename with `git push --force-with-lease`; prints the URL.
- **`<slug>/verify.sh`** (per bug): read-only `gh pr view --json` / `gh pr diff` (or `gh issue view --json`) into files.

No generated script contains `gh pr ready`, `gh pr merge`, `gh pr comment` or `gh issue comment`; those are the operator's actions in the web UI. Every spec value is shell-quoted. The agent does not run `submit.sh`; it runs `dup-search.sh` or `verify.sh` only when the operator asks and `gh` is available to it.
