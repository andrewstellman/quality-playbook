# Handoff: run the whole Quality Playbook bug pipeline in a cloud session

Written 2026-10-01 by the Cowork (Mac) session for a new **cloud** Claude session. This file is self-contained: the cloud session cannot see Andrew's Mac. Andrew attaches this file to the cloud chat.

## 0. What this experiment is

Andrew wants to know if the **entire** pipeline can run in a cloud sandbox, with no bridge to his computer:

1. clone a target project and Quality Playbook (QPB) into the cloud sandbox;
2. gather documentation;
3. run QPB through all six phases and all four iteration strategies, using subagents;
4. confirm the findings independently;
5. fix the chosen bugs with red/green;
6. run the full review panel on the fixes;
7. present each bug to Andrew under the submission protocol (§6), so he can submit it himself.

The result we care about has two parts: real bugs, and **an honest record of what the cloud environment could and couldn't do**. Keep `CLOUD-LOG.md` (see §8) as you go.

## 0.5 Your first reply: confirm, don't start

**Do not clone, install, probe or spawn anything in your first reply.** Read this whole file. Then reply with a short check-in, and wait for Andrew to say go:

1. **What you understood:** the goal, the target, and the steps, in 5–8 bullets.
2. **Your session setup, from what you can see:**
   - your model and effort level;
   - which tools you have (shell, web, subagents, and whether you can pick a subagent's model);
   - **whether anything connects you to Andrew's computer**, such as attached local folders or a desktop bridge. The experiment requires **no bridge**. If any is attached, say so and don't use it. Andrew will detach it, or tell you how to proceed.
3. **Anything in this file that conflicts with your environment or that you'd do differently**, with a reason.
4. **Your questions,** if any.

Only after Andrew confirms do you start §4. Log the check-in and his answer as the first entries in `CLOUD-LOG.md`.

## 1. Who Andrew is and how he works

Andrew Stellman wrote QPB and is the author of record for everything submitted. He is an O'Reilly author with books including Head First C#, Learning Agile and Head First PMP.

How to communicate with him:

- Use plain English, not AI shorthand. Use headers and bullets he can scan in 30 seconds.
- Lead with the answer.
- Surface decisions that are his to make; don't make them for him.
- End at a resting state. Don't queue up work for him to approve ("want me to…?").
- Never propose a schedule like "two today, three tomorrow".

## 2. Standing rules (non-negotiable)

- **Never push, post, comment, or open issues or PRs.** Andrew does every submission himself.
- **Never fabricate.** Paste command output verbatim. If you didn't check something, say so.
- **Never add `Signed-off-by` or `Co-Authored-By`.** Commits are authored by `Andrew Stellman <andrew@stellman.com>`, plus whatever the target project's AI policy requires (see §3).
- **Correctness bugs only.** Set aside anything with a security angle: injection, bypass, DoS, information exposure.
- **Minimal commits (YAGNI).** Change only what the bug requires. Use the smallest test that shows red/green.
- **No bad side effects.** If a fix is correct but would hurt existing users in a way they wouldn't expect, drop it. Example: a "fix" that makes existing config load every file into memory. Andrew decided this rule on 2026-10-01.
- **Verification gates** before you claim anything is done, passing or landed:
  - put the artifact's literal content next to the claim;
  - run the one command that would disprove the claim;
  - disclose any substitute, shim or workaround in the same breath;
  - treat a warning as a hard stop.
- **Disclosure line** at the end of every PR or issue body: `Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.` If the project's AI policy needs more, add it (see §3).

## 3. Target: icalendar (collective/icalendar)

**Choice:** [collective/icalendar](https://github.com/collective/icalendar), the main Python library for reading and writing iCalendar (`.ics`) files. It is pure Python.

**Pin:** `main` at `a2f557ec34bd8b7c51ead792bbac05c60b05d682` (last commit 2026-09-30). At the start, record the HEAD you actually clone in `CLOUD-LOG.md`. If `main` has moved, use the new HEAD and note the change.

**Why it's a good QPB target:**

- **Many formal specs.** `docs/reference/rfc-support.rst` claims support for RFC 5545, 6868, 7529, 9074, 7953, 7986 and 9253. QPB's strength is finding code that contradicts a written spec or the project's own docs: code that looks fine read on its own, but is wrong against a requirement written elsewhere. Every bug we have had merged so far was that kind (calibre, virtio-pci, gson, zram).
- **Edge-case-heavy domain.** Recurrence rules, time zones, parameter encoding, line folding and value types all have exact RFC grammar.
- **Active.** It had a commit the day before this handoff. It has 264 Python files under `src/` and its own `docs/` tree.
- **Explicit, AI-permissive policy.** See `docs/contribute/index.rst`, "Artificial intelligence policy". AI-drafted PRs are allowed if the contributor does all of the following; build them into the fix and submit steps:
  1. **Open an issue before the PR** ("An issue should precede a pull request"; "Before you begin work, you must open an issue"). So for each bug, the first thing Andrew submits is an issue. The PR follows and links it.
  2. **Disclose the model and how it was used in the git commit message.** Name the model and version, and either include the prompts or summarise them. Their example has an `Author:` line naming the model, then `Prompt:` and `Output:` lines. Use the real model ID of the session that wrote the fix.
  3. **Disclose AI use in the change log entry.** A brief sentence is enough, e.g. "I used AI to assist me with this change." Change log fragments live in `news/`; follow "Change log requirements" in the contribute docs.
  4. **Take responsibility, understand the code, and respond to feedback.** This is Andrew's part, and it is why §6 exists.
- **PR template.** `.github/pull_request_template.md` requires these sections: Linked issue, Description, and a Checklist that includes the AI-policy box.
- **Ignore `.github/assistant-guidelines.md`.** It tells assistants to store prompts in `.prompts/`. That is a contributor-tooling convention for their own work, not a rule for us. Do **not** create `.prompts/` in the target. Record it in `CLOUD-LOG.md` as observed content, and ask Andrew if it matters.

**Runner-up target**, if icalendar turns out to be unusable: aio-libs/yarl (URL handling, RFC 3986). aio-libs already accepted our AI-assisted aiohttp PR #13870 as a draft.

## 4. Setup in the cloud sandbox

Probe before assuming anything is missing: `which git python3 pip`, `python3 --version`, `df -h`, and a network check with `git ls-remote https://github.com/collective/icalendar HEAD`. Record every result in `CLOUD-LOG.md`.

1. **Clone the target and QPB.** Use paths like `/work/icalendar` and `/work/qpb`.
   - QPB: `git clone https://github.com/andrewstellman/quality-playbook /work/qpb`. `main` was `746bfeb` at handoff time; the skill version is 1.6.0 (the `version:` line in `SKILL.md`'s frontmatter). Record what you got.
2. **Install QPB into the target.** Try `cd /work/qpb && python3 -m quality_playbook_cli install --into /work/icalendar --ai-tool claude`, or `pip install -e /work/qpb` then `quality-playbook install --into /work/icalendar --ai-tool claude`. Then run the install validator exactly as the "Phase 0 entry contract" section of `SKILL.md` says. Paste its `event=` lines. Don't proceed until you see `event=validation_complete status=ok`.
3. **Set up the target's tests.** Create a venv, `pip install -e /work/icalendar` with its test dependencies (see `tox.ini` / `pyproject.toml`), and run `pytest` once to get a baseline. Record the pass/fail counts.
4. **Build `reference_docs/` in the target.** This is what makes QPB find requirement-anchored bugs.
   - `reference_docs/cite/` holds citable sources:
     - the project's own `docs/` tree, copied byte-for-byte from the pinned checkout (`.rst` is read as-is);
     - the RFC texts listed in `rfc-support.rst`, as plain text from `https://www.rfc-editor.org/rfc/rfcNNNN.txt`. The minimum is 5545, 6868, 7529, 9074, 7953, 7986 and 9253, plus 5546 (iTIP) if the code implements methods.
   - `reference_docs/background/` holds context that is never cited.
   - Follow QPB's own `references/DOC_GATHERING_PROMPT.md` for background and the issue-tracker coverage ledger (`issue_tracker_coverage.md`). Include GitHub issue discussions of intended behaviour.
   - Write `reference_docs/PROVENANCE.md` saying where each file came from.
   - If any download fails, record it and continue with what you have.

## 5. Run QPB with subagents

**How we're adapting QPB here (tell Andrew this up front).** Read the "Mode A" section of `SKILL.md`: for an interactive chat, QPB says to run Phases 1–5 yourself and **not** delegate them to subagents. Only Phase 6 verification goes to a fresh subagent. The per-phase subagent pattern lives in the skill's `agents/quality-playbook-claude.agent.md`, which is labelled "AUTOMATION ONLY". This experiment deliberately uses that automation pattern, because Andrew asked for QPB to run in subagents.

Two mitigations for the failure that rule exists to prevent (in May 2026, a delegated run hand-wrote a gate log reading "PASS" while the real gate failed):

1. **You are the orchestrator.** Your only jobs are to spawn one subagent per phase, verify its files on disk, and report. Never do phase work in your own context. Follow `references/orchestrator_protocol.md`: read it before Phase 1 and apply its per-phase verification gate, with content criteria such as "EXPLORATION.md has at least 120 lines".
2. **Run the Phase 6 gate yourself as well.** After the Phase 6 subagent returns, run `quality_gate.py` yourself. In the QPB repo the installable skill keeps it at `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py`, next to `scripts/qpb_validate.py`; in the installed copy, check what `SKILL.md` says. Paste its verdict lines verbatim and compare them with `quality/results/quality-gate.log`. If they differ, stop and tell Andrew.

**If this works, it becomes a proposed QPB change (Andrew's decision, 2026-10-01).** If subagent execution produces a sound run, `SKILL.md` should be updated to support subagent execution explicitly, **on condition that the parent agent re-runs the quality gate itself** and pastes its verdict lines verbatim. "Sound" means real artifacts on disk, the parent's own gate run matching the Phase 6 log, and confirmed bugs. That re-run is the check that closes the fabricated-PASS failure mode, so it can replace the blanket "no subagents in Mode A" rule.

Collect the evidence for this as you go, in `CLOUD-LOG.md` under a heading **"Evidence for the subagent-execution change"**:

- the parent's gate output next to the subagent's `quality-gate.log`, for every Phase 6, baseline and each iteration;
- any mismatch between them;
- any phase whose files failed the on-disk check.

At the end, write a short proposal: which `SKILL.md` sections change (the Mode A "do NOT spawn a sub-agent" list and the "AUTOMATION ONLY" header on `agents/quality-playbook-claude.agent.md`), and what the new rule says.

Don't edit QPB itself. QPB source changes go through Andrew's Claude Code lane with a Council review. This step is the proposal plus the evidence.

Steps:

- **Baseline.** Six sequential subagents, Phases 1 to 6. Each prompt follows the template in `agents/quality-playbook-claude.agent.md`: read `SKILL.md`, the references and `quality/PROGRESS.md`; execute Phase N exactly; write to `quality/`; update `PROGRESS.md`. Run the gate after each phase.
- **Iterations.** Gap, then unfiltered, then parity, then adversarial. Each one runs Phases 1–6 as separate subagents, using the skill's `phase_prompts/iteration.md` (the installed skill's copy, or `plugins/quality-playbook/skills/quality-playbook/phase_prompts/iteration.md` in the QPB repo) and `references/iteration.md`. `SKILL.md` says iterations are normally driven by the CLI runner (Mode B). Driving them from subagents is a second adaptation; log it.
- **Nesting limit.** Subagents can't spawn subagents. Two things in QPB spawn their own subagents:
  - the Feature H persona pass at the Phase 2→3 boundary;
  - the Phase 6 auditor.

  The Phase 6 auditor is covered, because Phase 6 already runs in its own fresh subagent. For Feature H, either spawn the personas yourself between Phase 2 and Phase 3, or record that it was skipped. Either way, write down which.
- **Disk only.** Phase subagents must write only inside the target's `quality/` folder. Check `git status` on the target after every phase.
- **Context.** If a subagent runs out of context, apply the error-recovery steps in `orchestrator_protocol.md`, and log it.

## 6. From findings to Andrew's submit button

Everything below is the process that produced the merged and open PRs so far. It is adapted for icalendar.

### 6.1 Confirm

Run one confirmer subagent per candidate bug. Prioritise bugs whose expected behaviour comes from an RFC or doc rather than from code alone. Each confirmer must:

1. Restate the claim: input, actual, expected, and the source of "expected" (quoted verbatim with file:line and grepped to prove it, or an RFC section).
2. Write a repro that exits 1 when the bug is present. Run it and paste the output.
3. Check whether the expected side really holds:
   - Is there a test, comment, changelog entry or closed issue that makes the current behaviour intentional?
4. Search for duplicates in collective/icalendar issues and PRs; give the queries and the closest match.
5. Flag any security angle (yes/no).
6. Give a verdict: CONFIRMED / CONFIRMED-DUPLICATE / NOT-A-BUG / UNCLEAR / COULD-NOT-RUN.

Keep `confirm/LEDGER.md` with one line per bug.

### 6.2 Select 1–2 bugs

From the CONFIRMED, unreported, non-security bugs, pick the ones that best show QPB's method: the expectation comes from a requirement outside the code (an RFC or the project docs); the code looks fine in isolation; the fix is small; the user consequence is real. Show Andrew the shortlist and your reasoning, then stop for his pick.

### 6.3 Fix

Use one fixer subagent per bug, in a fresh clone of the pinned target. Andrew wants minimal commits. The fixer must:

1. **Test first.** Add the test to the existing test file for that feature, styled like its neighbours, and save `red.log`.
2. **Make the smallest fix.**
3. **Save `green.log`** from the touched test file plus the full `pytest` suite: no new failures.
4. **Prove the test really checks the fix.** Revert only the source change; the test must fail again (`revert.log`). Then restore it.
5. **Add a `news/` change-log fragment** that includes the AI-use sentence.
6. **Commit** with author Andrew, a subject in the repo's style, and a 2–4 line body. Add the AI disclosure the policy requires: the model ID, plus a one-paragraph summary of how it was used ("Found by Quality Playbook (QPB 1.6.0) running on <model>; test and fix drafted by <model>; reviewed by Andrew Stellman"). No trailers.
7. **Generate the patch** with `git format-patch -1`, then write `ISSUE-DRAFT.md` and `PR-DRAFT.md`:
   - **The issue** gets a minimal `.ics` or Python repro (actual vs expected), the RFC or doc sentence quoted, and a short statement of the proposed fix.
   - **The PR** follows `.github/pull_request_template.md`: `Closes #<issue>` as a placeholder, a short Description, and only honest checklist ticks.
   - Both end with the disclosure line.

### 6.4 Review panel (2 executors + 13 reviewers)

Write a `PANEL.md` brief with the materials (patch, PR/issue text, confirmation evidence and the fixed worktree), disk rules, and the roster. Then spawn all 15 in parallel. Use Opus for the O roles and Sonnet for the S roles and the executors, if you can choose models; otherwise record what you used. Each writes its own file and returns it.

**Executors:**

- **EXEC-A, EXEC-B** (independent): for each fix, run red with the test only, then green, then revert-source; then the touched test file plus the full suite; then the confirmer's repro. EXEC-B also tries 3 edge inputs of its own, comparing base and fixed.

**Opus reviewers:**

- **O1 Maintainer:** reviews it as the icalendar maintainers would (git log, recent merged PRs). Would they merge it?
- **O2 Security:** does the fix add or remove any security-relevant behaviour?
- **O3 Correctness:** tries to break the fix with inputs the test doesn't build.
- **O4 Not-a-bug:** argues the maintainer's side hard; concedes only what the source or docs force; checks upstream history.
- **O5 Slop A:** a maintainer tired of AI PRs: text out of proportion, claims beyond the evidence, padding. Proposes exact rewrites.

**Sonnet reviewers:**

- **S1 Readability (code)**
- **S2 Readability (tests):** would the test catch a regression, and does it fail for the right reason?
- **S3 Slop B:** same charter as O5, independently.
- **S4 QA:** coverage gaps.
- **S5 Compat:** what changes for existing users? Apply the side-effect rule.
- **S6 Performance**
- **S7 Citations:** every factual claim is true and traceable, with doc sentences verbatim.
- **S8 Compliance:** the icalendar AI policy, issue-first rule, change log and PR template.

**Review protocol:**

- Reviewers form and write down their verdict **before** reading the confirmation evidence or any other reviewer's output. If the evidence changes their mind, they add an "after reading" note.
- **Verdicts:** SHIP / FIX-REQUIRED / REJECT (or DROP for a side effect), with numbered findings citing file:line.

**After the reviews:**

- Write `SYNTHESIS.md` with a verdict matrix and a disposition for each bug.
- **Text-only changes:** apply them.
- **Code changes:** revise, then run a **focused re-review** with both executors plus the reviewers who flagged each item. Apply the side-effect rule.
- **Always verify specific claims** (e.g. "X does not suggest Y") by running them, not by reading. The last panel caught a false claim of exactly that kind.

### 6.5 Submission protocol (one bug at a time; Andrew reviews)

Adopted 2026-10-01; this applies to every bug. **Present one bug, then stop.** In chat, give a brief explanation:

1. what icalendar does, in a sentence or two;
2. the bug: the expected behaviour and its source, what actually happens, and why it went unnoticed;
3. the fix, with the diff shown;
4. how it was regression-tested (red / green / revert, full suite);
5. knock-on effects:
   - who calls the changed code;
   - a before/after comparison on ordinary inputs, **run fresh at presentation time**;
   - any behaviour change for existing users;
6. things to know: related issues or PRs, the issue-first requirement, and likely pushback.

Write the same explanation into `evidence/<slug>/REVIEW.md`. Also include:

- the review history;
- an upstream check (current HEAD; does the patch still apply);
- the exact issue and PR text;
- the steps to submit;
- an empty Submission record.

**Then stop.** No schedule, no queuing the next bug, no batching.

**Submission order for icalendar:**

1. Andrew opens the issue.
2. He pastes the issue number back; you put it into the PR text.
3. He opens the PR.

You can't run `gh` against his account, so give him the exact commands he can run from a terminal with his own `gh` login. Example:

```
gh issue create --repo collective/icalendar --title "..." --body-file ISSUE.md
```

For the PR, give him a short script that does the following:

1. forks the repo;
2. applies the patch with `git am`;
3. runs the touched tests;
4. pushes a branch;
5. opens the PR with `gh pr create --draft`.

The PR opens as a **draft**. Andrew marks it ready after reviewing it on GitHub.

**After each submission,** check the issue or PR page on GitHub. Confirm the title and body, and confirm the diff matches the patch (compare blob hashes; `https://patch-diff.githubusercontent.com/raw/collective/icalendar/pull/N.diff` works). Then fill in the Submission record: date, links, branch and commit, what you verified, bot or CI gates, what Andrew still has to do, and maintainer responses.

## 7. Outputs and how they get back to Andrew

Andrew's Mac can't be reached from the cloud sandbox. Keep everything under one folder, e.g. `/work/out/`, shaped like this:

```
out/
  CLOUD-LOG.md
  icalendar-quality/               the target's quality/ folder (full copy)
  icalendar-reference_docs/
  confirm/LEDGER.md                + one folder per confirmed bug (repro, output)
  review/PANEL.md, SYNTHESIS.md    + every reviewer file
  evidence/<slug>/                 patch, red/green/revert logs, ISSUE-DRAFT.md,
                                   PR-DRAFT.md, REVIEW.md, submit script
```

At each milestone (after the baseline, after the iterations, after the panel), package it as a zip and present it as a downloadable file. On the Mac it later goes into `~/Documents/QPB/docs/research/cloud-2026-10/` and `~/Documents/QPB/evidence/`.

## 8. CLOUD-LOG.md (the experiment's main research output)

Keep one dated line per event:

- every probe and its result;
- anything the cloud environment blocked: network, disk, timeouts, subagent limits, no nesting, model choice unavailable, session interruptions;
- each substitute used, and why;
- each place this process deviated from `SKILL.md`;
- times (start and end of each phase and iteration);
- the token or usage numbers, if visible.

End with a short verdict on what worked in the cloud, what didn't, and what would have to change to make the cloud path the default. Then add the `SKILL.md` subagent-execution proposal described in §5, with its evidence.

## 8.5 Where this is heading (Andrew, 2026-10-01)

This run is the start of the QPB v1.6.1 acceptance test (`docs/design/QPB_v1.6.1_Implementation_Plan.md` in the QPB repo, "Release acceptance and cutover"). The test is bugs found in new projects, submitted under §6.5, and **merged upstream**.

Once enough have merged, these happen:
1. QPB 1.6.1 is merged;
2. `ai_context/DEVELOPMENT_CONTEXT.md` is updated;
3. Andrew moves fully to a cloud chat.

To get that chat up to date, he'll relay follow-up prompts between it and the Mac Cowork session. Expect specific questions, and answer them from files, not memory.

## 9. Campaign state at handoff (for context; Mac-side items need the bridge)

**Merged upstream:**

- Gson (#3006)
- Linux zram (`2f529e73`) and virtio-pci (`93fa0945`)
- calibre (#3310)

**Open:**

- aiohttp #13870
- bionemo #1764, #1765
- zod issues #6639, #6640
- adonisjs/http-server #144, #145 (ready for review)
- cobra #2514. This was the first submission under §6.5. On 2026-10-01 Andrew signed the CLA and marked it ready; it is open and awaiting review.

**Ready on the Mac, not yet presented under §6.5:** cobra complete-after-`--`, setuptools missing-dynamic crash, addressable `route_from` with a base query, and javalin lowercase redirect context path. Their kits are in `~/Documents/QPB/evidence/SUBMIT/`, and the explanations in `evidence/<slug>/`.

**Waiting on Andrew:**

- the addressable `{+var}` pct-encoding fix, where the panel split 6–3 under the side-effect rule;
- the otel PRs, which need a Gradle run on the Mac;
- adonisjs: revise two fixes, and write the issue for a third.

**Held:** pydantic (both), and three zod issues pending their panel review.

**Dropped:** javalin precompress (would cause an OOM), setuptools MANIFEST `**` (side effect), and the express sub-second maxAge issue.

**Blocked by project policy:** httpx (closed to outside reports), click (Pallets bans AI contributions), assertj (human-authorship clause).

**Research framing** (for the article and paper):

- Pre-registered tests in `~/Documents/QPB/docs/research/control-2026-09-27/`.
- On six QPB-found defects, standard AI review (Opus and Sonnet, 10 runs each) found two; four were found in 0 of 20 runs.
- Two pre-registered predictor hypotheses (oracle location, visibility level) failed to predict the hit rate across findings.
- **A cloud run of icalendar can also have a control arm:** 10 fresh subagents each do a standard code review of the same pinned checkout, with code only, no docs and no QPB.
  - **Pre-register first:** before the control runs, write `PREDICTIONS.md` stating, for each confirmed bug, whether you expect standard review to find it.
  - **Optional:** do it only if Andrew asks.
