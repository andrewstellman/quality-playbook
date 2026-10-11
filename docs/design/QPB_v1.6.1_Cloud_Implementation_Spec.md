# QPB v1.6.1: implementation spec for the cloud session

Written 2026-10-01 by the Mac Cowork session for the cloud chat that is running the icalendar experiment (`HANDOFF-2026-10-01-cloud.md`). Andrew attaches this file. It is self-contained: the 1.6.1 design edits it summarizes are not on GitHub yet.

**Review this spec first and reply with a check-in, as in the handoff's §0.5.** Cover what you understood, any conflicts with your environment or with QPB's source as you find it, and your questions. Don't edit anything until Andrew says go.

## 0. Context and decisions already made

On 2026-10-01 Andrew set the scope of QPB **v1.6.1** to:

| Feature | What | Status before you start |
|---|---|---|
| **S** | Subagent execution allowed, if the parent agent re-runs the quality gate itself | Design only. Evidence comes from your icalendar run. |
| **R** | The open-source review and submission process, **inside the skill**, with external script files for `gh` | Used by hand across the 2026-09 campaign; not in the skill |
| **W** | Claims and copywriting rules for QPB's own output | Andrew agreed 2026-10-01 |
| A, B | Precision: NFR derivation and a fresh-context false-positive audit | Designed, not built. **Not part of this spec.** Andrew said the cloud chat may build them later. |

These decisions are settled. Don't reopen them:

- **Release order:** v1.6.1 merges into `main` only after (1) enough bugs from new projects are **merged upstream** and (2) A and B pass their acceptance test.
- **Version:** this is v1.6.1. There will be no separate version for the precision work.

Your output is a patch series for Andrew to apply and push from his Mac. You can't push.

## 1. Order of work

1. **Finish the icalendar run's §5 on stock QPB 1.6.0:** the baseline plus the four iterations, with your gate re-run after every Phase 6. This produces Feature S's evidence and the `BUGS.md` you'll test R on. Stop at the end of §5. Don't do the handoff's §6 by hand, because Feature R replaces it.
2. **Set up a separate QPB working tree for development.** Clone `https://github.com/andrewstellman/quality-playbook` and check out branch `1.6.1`. Record its HEAD. Never develop in the copy installed into icalendar.
3. **Implement S, W and R, in that order.** S and W are small and R builds on both.
4. **Run the test suite and a self-review panel** (§6).
5. **Test R on icalendar** (§5). Reinstall the modified skill into the icalendar target and take its `BUGS.md` through the new in-skill path. This replaces the handoff's §6. Everything in the handoff's §2 and §6.5 still applies: no submitting, one bug at a time, and Andrew submits.
6. **Deliver.** Run `git format-patch` for your commits on top of the recorded `1.6.1` HEAD, zip it with the logs, and present it.

## 2. Where things live in QPB (check this; don't assume)

- **`SKILL.md` and `references/`** sit at the repo root. `plugins/quality-playbook/skills/quality-playbook/SKILL.md` and its `references` are **symlinks** to them.
- **`agents/`, `phase_prompts/` and `scripts/`** exist only under `plugins/quality-playbook/skills/quality-playbook/`.
- **Bundle tests:** `bin/tests/test_install_skill_bundle_completeness.py` and `test_installed_bundle_freshness.py` check that the installable bundle is complete. Any new reference file or script must pass them.
- **Version source:** the frontmatter `version:` line in `SKILL.md`. **Leave it at 1.6.0.** Bumping it is a release step for Andrew.
- **Project conventions:** read `ai_context/DEVELOPMENT_PROCESS.md` and `ai_context/DEVELOPMENT_CONTEXT.md` before editing.
- **Known adopter problems, logged during your setup.** Fix them only if the fix is small and safe; otherwise record them in your report:
  - `python3 -m quality_playbook_cli install` fails on a raw clone (`_bundle` missing).
  - The validator blocks a repo that has a `.github` folder unless `--ai-tool claude` is passed.

## 3. Feature S: subagent execution, guarded by the parent's own gate run

**Why.** `SKILL.md` Mode A forbids running Phases 1–5 in subagents. The rule exists because of a 2026-05-16 failure: a delegated run hand-wrote `quality/results/quality-gate.log` reading PASS while the real gate failed, and the parent believed it. A ban stops that, but it also stops long runs that need context isolation. The parent's own gate run stops it more precisely: the verdict the operator sees comes from the parent, not the subagent.

**Change these:**

- **`SKILL.md`, the Mode A section** (the "Mode A means YOU execute the skill… DO NOT" list):
  - Replace the bullet forbidding Task/Agent subagents with a conditional rule. Phases may run in per-phase subagents (orchestrator pattern) if, after every Phase 6, the parent itself:
    - (a) runs `quality_gate.py` and pastes its verdict lines verbatim in its own chat;
    - (b) compares them with `quality/results/quality-gate.log`;
    - (c) stops and reports any mismatch.
  - Keep the Phase 6 fresh-context auditor rule and the Feature H exception.
  - Add: subagents can't spawn subagents, so the parent spawns the Feature H personas and the Phase 6 auditor.
  - Update the text that explains *why* the old rule existed, so it describes the new safeguard.
- **`agents/quality-playbook-claude.agent.md`, and `quality-playbook.agent.md` where it applies:** replace "AUTOMATION ONLY — DO NOT INVOKE FROM AN INTERACTIVE CODING SESSION" with the conditional rule, and add the parent gate re-run to the orchestrator's role.
- **`references/orchestrator_protocol.md`:** make the parent's gate re-run part of the mandatory post-phase verification gate for Phase 6.

**Tests:**

- update `bin/tests/test_mode_a_b_parity_documented.py` and any other pin test that freezes the old wording (grep for the old phrases);
- add a test that the rule text appears in all three files;
- add a fixture-based test: a `quality/` folder whose `quality-gate.log` claims PASS while running the real gate on it FAILs. Assert that the documented parent procedure's comparison flags it.

**Evidence:** include the "Evidence for the subagent-execution change" section of your `CLOUD-LOG.md` in the delivery.

## 4. Feature W: claims rules for QPB's own output

**Why.** Andrew supplied a copywriting standard (summarised below). Its reader model fits QPB's readers: a maintainer or adopter reads a claim the way they read a bug report: what happened, how often, can I reproduce it? Our worst PR-text defect in the campaign was a specific false claim ("`cafx` does not suggest `café`"), which five reviewers caught by running it.

**Create `references/claims_rules.md`** (short, QPB-specific) containing:

- **The two standards:**
  - **Tangible:** it names a number, a file:line, a command, a deliverable.
  - **Objective:** ten engineers would agree what it means. It passes or fails like a test.
- **Rules:**
  - **R1:** every claim has a measurable anchor.
  - **R2:** name the thing (file, function, test, command, RFC section), never gesture at it.
  - **R3:** describe the action or behaviour, not a feeling.
  - **R6:** one idea per claim.
  - **R7:** never promise what the material can't deliver.
  - **R8:** numbers are real (with their source) or clearly framed as targets. A specific behavioural claim ("X does not do Y") must have been *run*.
- **Leave out R4 (scenes) and R5 (before/after)** for bug reports, PRs and issues: maintainers read them as padding. R5 may be used in README and benchmark claims when both numbers are measured.
- **Flags that trigger a rewrite:**
  - unanchored intensifiers: "significantly", "robust", "comprehensive", "critical", "seamless";
  - "ensure", when nothing checks it;
  - "all" or "every", when they weren't enumerated;
  - any percentage without a source.
- **A pre-output checklist (R1–R3, R6–R8, flags)**, run silently before returning text. Precedence: the caller's voice and tone rules win on tone; these rules win on claims.

**Wire it in:**

- the end-of-phase message templates in `references/what_just_happened.md`;
- the `BUGS.md` / writeup guidance;
- Feature R's issue, PR and `REVIEW.md` templates;
- Feature R's slop and citation reviewer charters.

**Audit QPB's own claims, starting with this one.** The `SKILL.md` description, `SKILL.md` around lines 261, 294 and 660, and both agent files say QPB "Finds the 35% of real defects that structural code review alone cannot catch."

- Find the source of 35%: search `ai_context/`, `docs/`, the benchmark and experiment records and the git history.
- If it's a measured result, cite it where it's used.
- If not, reframe the line as what QPB targets, or drop the number.
- For context: the 2026-09 control study (`docs/research/control-2026-09-27/`) measured something different. Standard AI review found 2 of 6 QPB-found defects, and missed 4 in all 20 runs.
- **Report what you found before changing the wording; this one is Andrew's call.**

**Test:** one test that `claims_rules.md` exists and is referenced from the files it's wired into.

## 5. Feature R: the review and submission process in the skill

**Why.** The 2026-09 campaign took QPB findings to upstream fixes: merged in calibre and virtio-pci, plus earlier in Gson and zram, with more open. The panel caught real defects before submission:

- a false claim in a PR text;
- a fix that made a URL parser throw on `:` and added a quadratic regex;
- two fixes with bad side effects on existing users (javalin precompress → unbounded memory; setuptools MANIFEST `**` → venv/node_modules in sdists).

Today the process lives only in one-off briefs. Andrew: *"we've proven that it works, so we can ask the skill to analyze the findings, suggest bugs for review, run the review, and then prepare the PRs and guide through them."*

**Shape.** It's a new improvement path in Phase 7: **"Prepare upstream submissions"**. It's listed in Phase 7's improvement menu (`references/phase7_guide.md`) and specified in a new `references/upstream_submission.md`. It is operator-invoked, never automatic.

### 5.1 Steps

1. **Contribution-policy check (first, always).**
   - **What to read:** the target's `CONTRIBUTING*`, `AGENTS.md`, `CLAUDE.md`, `.github/` (PR and issue templates, any AI or assistant guidelines), `CODE_OF_CONDUCT`, the CLA or DCO, and the docs' contribute pages.
   - **What to record:** the AI policy (banned / allowed with conditions / silent), issue-first rules, the CLA/DCO, how changelogs are added, and which branch to target.
   - **If AI contributions are banned, stop and say so.**
   - **Write** `quality/upstream/POLICY.md`.

   Campaign examples:
   - Pallets bans AI contributions.
   - encode/httpx is closed to outside reports.
   - assertj requires human authorship.
   - zod limits PRs to collaborators, so issues only.
   - icalendar requires: an issue first, the model and how it was used in the commit message, and an AI line in the change log.
2. **Shortlist.**
   - From `BUGS.md` and `bugs_manifest.json`, propose 3–4 bugs whose expected behaviour comes from a requirement outside the code (a Tier 1/2 citation, verified by grep). The code should look fine in isolation, the fix should be small, and there should be a real user consequence.
   - Set aside security-angle bugs, with a one-line note pointing to private disclosure.
   - Show the shortlist and the reasoning, then **stop for the operator's pick.**
3. **Confirm.** One fresh-context confirmer subagent per picked bug. Each one does the following:
   - restates the claim;
   - writes a repro that exits 1 when the bug is present, and runs it;
   - checks the expected side (tests, comments, closed issues that make it intentional);
   - runs the duplicate search across issues **and open PRs**;
   - flags any security angle;
   - gives a verdict: CONFIRMED / DUPLICATE / NOT-A-BUG / UNCLEAR / COULD-NOT-RUN.
4. **Fix.** One fixer subagent per confirmed bug, in a fresh clone:
   - test first, in the existing test file;
   - smallest fix;
   - red / green / revert logs;
   - touched suite plus full suite;
   - commit authored by the operator, with no trailers and the project-required AI disclosure;
   - `git format-patch`;
   - draft the issue and PR texts, following the project's templates and the claims rules.
5. **Review panel.** The parent spawns all of these, because subagents can't nest:
   - **Executors, EXEC-A and EXEC-B:** red / green / revert, suite, repro; B also tries 3 edge inputs.
   - **O1 maintainer, O2 security, O3 correctness** (tries to break it).
   - **O4 not-a-bug:** argues the maintainer's side and checks upstream history.
   - **O5 and S3 slop:** text out of proportion, claims beyond evidence.
   - **S1 code readability, S2 test readability, S4 QA coverage.**
   - **S5 compat:** applies the side-effect rule.
   - **S6 performance, S7 citations** (every claim true and traceable; specific claims *run*), **S8 compliance** (against `POLICY.md`).

   How it runs:
   - **Verdicts:** SHIP / FIX-REQUIRED / REJECT / DROP (side effect).
   - **Blind first:** each reviewer writes its verdict before reading the confirmation evidence or other reviewers' output.
   - **Synthesis:** a verdict matrix.
   - **Fixes:** text-only fixes are applied. Code revisions get a focused re-review: both executors plus the reviewers who flagged the item.
   - **Side-effect rule:** a fix that's correct but would hurt existing users unexpectedly is dropped. That is the operator's rule and it's binding.
   - **Default roster:** the full panel. A smaller one is an explicit operator choice, recorded in `REVIEW.md`.
   - **Model choice:** if the runtime lets you choose subagent models, use the strongest model for O-roles and a faster one for S-roles and executors; otherwise record what ran.
6. **Prepare, one bug at a time.** For each surviving bug, write `quality/upstream/<slug>/REVIEW.md`, show the same explanation in chat, and then **stop**. The explanation covers:
   - what the project does;
   - the bug and the source of the expected behaviour;
   - the fix, with the diff;
   - red / green / revert and the full suite;
   - a knock-on check run fresh: callers, before/after on ordinary inputs, behaviour changes for existing users;
   - things to know: related PRs, policy steps, likely pushback;
   - an upstream-head check (does the patch still apply);
   - the exact issue and PR text;
   - an empty Submission record.

   Don't propose a schedule, don't batch, and don't queue the next bug in the same message.
7. **Record.** After the operator submits and pastes the output, verify the submission on the forge: the title and body, and that the PR diff matches the patch by blob hash. Then fill in the Submission record and `quality/upstream/<slug>/STATUS.md`, using the status values in §5.3.

### 5.2 External script files for `gh` and other binaries

Andrew wants the skill to **generate script files** for operations that use the operator's credentials, so the operator doesn't have to approve each `gh` call in the agent's chat.

- **Per bug, `quality/upstream/<slug>/submit.sh` (zsh/bash).** The script must:
  - check `gh` is logged in;
  - fork if needed;
  - clone to a work dir if absent;
  - branch from the upstream default branch;
  - `git am` the patch, halting with a clear message on conflict;
  - run the touched tests (a `SKIP_TESTS=1` escape);
  - push to the operator's fork;
  - open a **draft** PR with the body file, or for issue-first projects, open the issue first and print the next step;
  - print the URL;
  - run any post-create step the project needs (e.g. renaming a newsfragment to the PR number, then force-pushing).

  It must stop at the first failure. It must never mark a PR ready, comment, or merge. Model it on the campaign scripts.

  Example skeleton:

  ```zsh
  set -euo pipefail
  ME=$(gh api user -q .login)
  DEFAULT=$(gh repo view "$UPSTREAM" --json defaultBranchRef -q .defaultBranchRef.name)
  gh repo fork "$UPSTREAM" --clone=false
  # clone, then: git switch --detach upstream/$DEFAULT; git switch -c $BRANCH
  git am "$PATCH"
  # <tests>
  git push -u origin "$BRANCH"
  gh pr create --draft --repo "$UPSTREAM" --head "$ME:$BRANCH" --base "$DEFAULT" --title "$TITLE" --body-file "$BODY"
  ```

- **Per run, `quality/upstream/dup-search.sh`.** For each candidate, run `gh search issues` and `gh search prs` with the queries the confirmer chose, scoped to the upstream repo, writing results to `quality/upstream/dup-search.out`. The skill reads that file once the operator has run the script. This also covers sandboxes where `gh` is blocked (as in your cloud session): the operator runs it on their machine and pastes or uploads the output.
- **Per bug, `quality/upstream/<slug>/verify.sh`.** Reads the PR or issue back with `gh pr view --json` / `gh issue view --json` and the diff, so the Submission-record check uses the forge's own data.

**Tests for the script generator:** a golden test that the generated `submit.sh` for a fixture bug contains `--draft`, has no `gh pr ready` / `gh pr merge` / `gh pr comment`, and starts with `set -euo pipefail`. Also run `bash -n` on every generated script.

### 5.3 `STATUS.md` values (same as `evidence/` in the QPB repo)

`merged`, `open`, `sent`, `ready`, `needs-work`, `held`, `decision`, `dropped`, `not-filed`, `duplicate`, `maintainer-view`, `ruled-out`. Each `STATUS.md` has these lines: `status:`, `title:`, `link:`, `updated:`, `note:`.

### 5.4 Guardrails that must be in the skill text, not only in docs

- The skill never submits, never marks ready, never comments upstream, and never runs a submit script itself unless the operator explicitly asks.
- One bug at a time, with no schedules.
- The policy check comes first, and the project's AI policy wins.
- Security-angle findings never become a PR.
- Every submission carries a disclosure line. The default is "Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.", extended to whatever `POLICY.md` requires.
- No `Signed-off-by` or `Co-Authored-By` from the agent.

### 5.5 What "done" means for R

1. The Phase 7 menu lists the path, and `references/upstream_submission.md` holds the briefs: policy check, shortlist, confirmer, fixer, panel roster, re-review, synthesis format, `REVIEW.md` template, script templates.
2. The tests pass, the bundle tests included.
3. **The real test is on icalendar.** Reinstall the modified skill into the icalendar target and invoke "Prepare upstream submissions" on its `BUGS.md`. Take it through the policy check, shortlist (stop for Andrew's pick), confirmers, fixes, panel, then the first bug's `REVIEW.md` and generated scripts. Andrew runs `dup-search.sh` and, if he approves, `submit.sh`.
   - Anything the skill text didn't cover that you had to improvise is a defect in R. Log it and fix it before delivery.

## 6. Review of your own changes

QPB source changes normally get a nested external Council (the `copilot` CLI), which your sandbox can't run. Use a **subagent panel** instead, and log it as a substitution:

- three reviewers with fresh context;
- one each for: correctness against this spec, test sufficiency, and regression safety (does Mode A still read coherently; is anything in the bundle missing);
- each writes a SHIP / FIX-REQUIRED verdict file with file:line citations.

Fix and re-review until all three say SHIP, then write a synthesis. Andrew may also run the external Council on the patch series from his Mac before pushing.

## 7. Delivery

A zip containing:

- **The patch series** (`git format-patch <recorded 1.6.1 HEAD>..HEAD`) and the base SHA;
- **Test output:** `bin/tests` full run, before and after;
- **The self-review:** the three panel files and the synthesis;
- **The icalendar test:** `quality/upstream/` and the `CLOUD-LOG.md` sections on Feature R;
- **The 35% report** (§4);
- **A list of everything you left undone or improvised.**

Present it. Andrew applies it on his Mac (`git am`), runs the tests, and pushes.
