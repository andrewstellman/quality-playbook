# S8 — Contribution-process compliance review

Persona: contribution-process compliance reviewer. Scope: patch + PR draft vs. each project's own
CONTRIBUTING / PR template / commit conventions / changelog rules / CLA-DCO / AI-assistance policy /
issue-first process / license headers. I did not run builds or tests (that's the executors' job);
I read the base checkout's process docs, the patch, the PR draft, and — where no local checkout
existed (express) — the live GitHub org `.github` repo and search API. Everything below is
first-pass, before reading the validator README or executor reports.

---

### aiohttp-readuntil
Verdict: SHIP
Confidence: high
Findings:
1. `AGENTS.md` "PRs" section requires: shipped PR template, draft via `gh pr create --draft`,
   disclosure line `Drafted with <agent name and version>; reviewed by <human handle>`, no
   `Co-Authored-By:` trailer, CONTRIBUTORS.txt addition, news fragment in `CHANGES/`. The
   PR-DRAFT.md matches the template section-for-section (`.github/PULL_REQUEST_TEMPLATE.md`),
   ends with the exact disclosure line format (`Drafted with Claude Opus 5.5; reviewed by
   @andrewstellman.`), and explicitly instructs renaming `CHANGES/PRNUMBER.bugfix.rst` before
   opening — matching the template's own instruction to rename to the PR number once one exists.
2. Patch adds `CONTRIBUTORS.txt` entry ("Andrew Stellman", correct `<Name> <Surname>` format,
   alphabetically placed between "Andrew Lytvyn" and "Andrew Svetlov" — verified correct order).
3. Patch adds `CHANGES/PRNUMBER.bugfix.rst` with the required `-- by :user:\`handle\`` signoff
   format and valid type (`bugfix`, defined in the template's category list).
4. Commit subject "Fix readuntil() missing a separator split across chunks" is imperative, no
   conventional-commit prefix — `AGENTS.md` explicitly says "Don't use conventional commits; match
   recent imperative subjects," and the one visible base-repo commit ("Fix secure shared cookie
   (#13830)") matches this imperative style.
5. No `Co-Authored-By:` trailer present in the patch — compliant with the explicit prohibition.
6. Checklist in the PR-DRAFT ticks match reality: tests exist (new tests + full run pass per the
   pasted test-output block), CONTRIBUTORS.txt box checked and done, CHANGES box checked and done,
   docs box correctly marked N/A with a one-line reason.
No blocking findings. This is the cleanest of the nine on process grounds.

---

### chi-gethead
Verdict: SHIP
Confidence: high
Findings:
1. `CONTRIBUTING.md` process is minimal: fork, branch, add tests, `go test`, `goimports -w .`,
   commit, PR. No PR template file exists in `.github/`, no CLA/DCO bot config found, no
   AI-disclosure policy exists for this repo.
2. Commit subject "middleware: fix GetHead look-ahead inside a mounted router" matches the
   `<package>: <verb> ...` convention visible in the one base-repo commit ("middleware: honor
   Discard when flushing (#1185)").
3. `CHANGELOG.md` entries are release-level ("History of changes: see .../compare/vX...vY"), not
   per-PR fragments — no changelog action required from the contributor.
4. The PR-DRAFT's voluntary attribution footnote ("found by a Quality Playbook run... reproduction
   and fix were done by Claude (Anthropic)") is not required by any chi policy, but given the
   general maintainer climate described in the brief (psf/requests distrust of AI reports), keeping
   it is the safer choice and it's already short.
No blocking findings.

---

### express-cookie
Verdict: FIX-REQUIRED
Confidence: medium-high
Findings:
1. **Issue-first step skipped.** `expressjs/.github`'s `CONTRIBUTING.md` (fetched live,
   `https://github.com/expressjs/.github/blob/HEAD/CONTRIBUTING.md`, commit `a0e05d5`), "Steps for
   contributing" step 1: "Create an issue for the bug you want to fix... Make sure to reference your
   issue from the pull request." The PR-DRAFT.md itself has this unchecked
   (`- [ ] Issue created first and referenced`) and the body has a placeholder
   `Refs #<issue number, if one is opened first per CONTRIBUTING>`. This is a real, stated project
   requirement, not optional boilerplate — Andrew must open the issue and get a real number before
   filing the PR, not leave the placeholder in.
2. **OpenJS AI Coding Assistants Policy unresolved.** PR-DRAFT.md flags this itself
   (`- [ ] Read the OpenJS AI Coding Assistants Policy... and adjust the disclosure line if it
   requires specific wording`). I could not fetch the policy text in this sandbox (repeated
   `web_fetch` attempts to openjsf.org returned empty) — I did not verify it, and neither has the
   draft. This must be read and the disclosure line checked against it before submission; don't
   submit on the assumption that the current wording ("found by a Quality Playbook... code found by
   Claude (Anthropic) and reviewed by me") satisfies it.
3. **DCO present and correctly identified.** Confirmed via GitHub search
   (`is:pr in:body DCO`, `expressjs/express`) that merged/attempted PRs do carry an HTML-comment DCO
   line (introduced by `expressjs/express#6048`, "docs: add DCO"), matching the PR-DRAFT's
   instruction to keep the org-level template's DCO comment in the body.
4. **Commit-message convention mismatch.** The project's actual commit history (visible in PR
   #6095's merge summary, live-fetched) is overwhelmingly conventional-commit style: `fix(buffer):
   use node:buffer...`, `refactor: improve readability`, `feat(deps): body-parser@^2.1.0`,
   `fix (deps): update deps`. The PR-DRAFT title correctly uses this style
   (`fix(res.cookie): don't send Max-Age=0 for a sub-second maxAge`), but the actual patch commit
   subject does not: `Fix res.cookie sending Max-Age=0 for a sub-second maxAge` (patch file
   `0001-Fix-res.cookie-sending-Max-Age-0-for-a-sub-second-ma.patch`, line 4). Align the commit
   subject with the PR title's conventional-commit form before submitting, or the two will visibly
   disagree in the PR history.
5. No CLA bot / EasyCLA requirement found for expressjs/express (Linux Foundation DCO-style
   self-certification, not employer CLA) — nothing further needed there beyond item 3.

Andrew must, in order: (a) open the GitHub issue and get its number, (b) read the actual OpenJS
policy text and adjust the disclosure line, (c) fix the commit subject to match conventional-commit
style, before this is ready to submit.

---

### otel-urlparser
Verdict: SHIP
Confidence: high
Findings:
1. `CONTRIBUTING.md`: "Pull requests for bug fixes are always welcome!" — issue-first is only
   "recommended" for new features/behavior changes, not bug fixes, so no issue is required here.
2. `CONTRIBUTING.md`: "The changelog is generated from merged pull requests. Do not add a changelog
   entry for normal changes." — neither patch touches `CHANGELOG.md`, which is correct; a manual
   entry would have been a compliance error in the other direction.
3. Commit carries `Assisted-by: Claude Opus 5.5` trailer (patch line 6) — matches the brief's
   description of OTel's generative-AI policy recommending this exact trailer. PR-DRAFT.md keeps
   the provenance HTML comment intact for the same purpose.
4. EasyCLA: no repo-level action needed pre-submission beyond having a GitHub account that can sign
   when the bot prompts on PR open (confirmed via `.github/workflows/*` references to "CLA approved
   bot" — this is CI-authorization tooling for NVIDIA/OTel bots, separate from the contributor-facing
   EasyCLA check, which fires automatically on PR creation and requires no pre-PR action).
5. PR-DRAFT correctly cross-references the two related, previously-merged fixes (#15158, #19540)
   rather than treating this as a fresh unrelated report — good practice given the maintainer
   climate described in the brief.
No blocking findings.

---

### otel-forwarded
Verdict: SHIP
Confidence: high
Findings: Same CONTRIBUTING.md applies as otel-urlparser (bug-fix PRs don't need a pre-filed issue;
no changelog fragment; `Assisted-by: Claude Opus 5.5` trailer present in the patch). PR-DRAFT
correctly frames this as a follow-up to #15158/#19540 rather than a novel finding. No blocking
findings.

---

### assertj-percentage
Verdict: FIX-REQUIRED
Confidence: high
Findings:
1. **Unresolved Legal Disclaimer conflict — this is the headline issue.** `CONTRIBUTING.md`'s
   "Legal Disclaimer" section states: "As a contributor: You will only submit contributions where
   you have authored 100% of the content." The PR-DRAFT.md itself surfaces this as an open,
   unchecked item (`- [ ] Decide whether CONTRIBUTING's Legal Disclaimer... is compatible with
   submitting Claude-authored code`) while simultaneously disclosing in the same draft body that
   "Reproduction, the test, and the fix were done by Claude (Anthropic), and I reviewed them before
   submitting." Those two statements are in direct tension: the disclaimer's plain text does not
   carve out AI-assisted authorship the way aiohttp's or OTel's policies explicitly do. This is not
   a minor gap — it's the one item in this whole panel where the project's own contributor
   agreement and the draft's own disclosure contradict each other, and the draft says so. Do not
   submit until this is resolved one of two ways: (a) Andrew substantially re-derives/rewrites the
   fix himself so he can honestly attest 100% authorship and drops the Claude-authorship language,
   or (b) he opens an issue asking maintainers whether AI-assisted contributions are acceptable
   before investing in a PR that a maintainer could summarily close over the disclaimer. Given that
   assertj has no published AI-assistance carve-out (unlike aiohttp/OTel), option (a) or a direct
   pre-PR question to maintainers is safer than submitting as drafted.
2. **PR checklist likely doesn't match live template.** No `.github/PULL_REQUEST_TEMPLATE.md`
   exists in the base checkout, and spot-checking three recent non-dependabot merged PRs
   (`assertj/assertj#4338`, `#4333`, `#4306`, fetched live via GitHub search API) shows none of them
   use any checklist format — they're free-form descriptions, often just a couple of sentences or a
   bare "Follow up to #X." The PR-DRAFT's `#### Check List:` block (`Fixes #???`, `Unit tests: YES`,
   `Javadoc with a code example... : NA`, link to CONTRIBUTING) doesn't correspond to any template
   file I could find and doesn't match recent maintainer practice; it may be copied from an older or
   different assertj-family repo's template. Verify against the actual "Open a pull request" form
   on GitHub before using it, or simplify to match the free-form style maintainers actually use.
3. `CONTRIBUTING.md`'s "Rebase your PR on main (no merge!)" is correctly cited in the PR-DRAFT's
   "Base" line. No DCO/CLA requirement found for assertj (confirmed: no bot config, no DCO text in
   CONTRIBUTING) — the draft's "No DCO/Signed-off-by is required" note is accurate.
4. Commit-message / test-naming conventions (`should_pass_xxx`/`should_fail_xxx`,
   GIVEN/WHEN/THEN) are a `Percentage_Test` naming and structure concern for the executor, not
   something I can fully verify from the packet without reading the actual added test rows in the
   fixed source tree — flagging as unchecked by me; the correctness/test-quality panelists should
   confirm the two new rows follow `should_pass_xxx`/`GIVEN`/`WHEN`/`THEN` structure.
Overall: this is the one fix on the panel where the compliance blocker is existential (the project's
contributor agreement), not just a missing checkbox.

---

### calibre-opds
Verdict: SHIP
Confidence: high
Findings:
1. Process description in the PR-DRAFT matches what's actually in the repo: `README.md` line 33
   states "GitHub is only used for code hosting and pull requests" (bugs go to Launchpad — matches
   the draft's opening line), and `manual/develop.rst` (lines 109-144) confirms both the GitHub PR
   flow and the `git format-patch` → Launchpad-ticket alternative the draft mentions.
2. No PR template, no CLA/DCO bot config, no changelog-fragment requirement found in the base
   checkout — `Changelog.txt`/`Changelog.old.txt` are maintainer-managed release notes, not
   contributor-authored fragments. The draft correctly asks for nothing here.
3. The draft explicitly avoids calling this a security fix ("Keep it short; do not call it a
   security fix"), which tracks the maintainer-context note in the brief ("None of these are
   security issues" on a prior similar submission) — good calibration, not just boilerplate.
4. The AI-authorship disclosure ("Found by a Quality Playbook analysis run; reproduction and fix
   were done with Claude (Anthropic)...") is not required by any calibre policy (no AGENTS.md-style
   contribution policy governs PR content — the repo's `local-agent.md` is a dev-environment/build
   config for coding agents, not a contribution-disclosure policy), but keeping it is reasonable
   given the general maintainer climate described in the brief, and it's already appropriately
   terse per the "short and to the point" maintainer feedback quoted in the brief.
No blocking findings.

---

### bionemo-amplify
Verdict: FIX-REQUIRED
Confidence: medium-high
Findings:
1. **PR body doesn't follow the repo's actual PR template.** `.github/pull_request_template.md`
   exists and has a specific structure: `### Description` / `#### Usage` (with a code snippet) /
   `### Type of changes` (checkboxes: Bug fix / New feature / Refactor / Documentation update /
   Other) / `### CI Pipeline Configuration` (ciflow label guidance) / `### Pre-submit Checklist`
   (4 checkboxes: tested locally, updated docs, added/updated tests, all existing tests pass). The
   PR-DRAFT.md for this fix uses none of that structure — it's a custom "Provenance / Summary / Fix
   / Testing / Notes for maintainers" layout. When opened on GitHub, the actual template will
   pre-populate the compose box; the draft content needs to be remapped into the template sections
   (at minimum, check "Bug fix" under Type of changes, and answer the four Pre-submit Checklist
   items honestly: tested locally — yes per the harness described; updated docs — no doc change
   needed, should say so explicitly rather than omit; added/updated tests — yes; all existing tests
   pass — the draft says this couldn't be verified in-sandbox because `transformer_engine` isn't
   installable, so this checkbox should be left unchecked with that caveat stated, not silently
   dropped).
2. **The draft's DCO/Signed-off-by speculation is off-target; the actual gate is copy-pr-bot
   authorization.** The draft says "No `Signed-off-by` trailer was added — `CONTRIBUTING.md` and the
   PR template didn't mention a DCO requirement for this repo, but please add one if NVIDIA's
   process expects it." I confirmed no DCO/CLA bot config exists in `.github/` — so the "add one if
   NVIDIA's process expects it" hedge is guessing at the wrong mechanism. The PR template (which the
   draft doesn't otherwise engage with) documents the actual gate: NVIDIA's `copy-pr-bot` — for an
   untrusted/first-time contributor, "an NVIDIA org member must leave an `/ok to test` comment on
   the pull request to trigger CI... for each new commit." Andrew should expect this and not be
   confused when CI doesn't run automatically; the PR body should not raise a DCO question that
   doesn't apply here.
3. License header on the new test file (`models/amplify/tests/test_pad_weights_dtype_device.py`,
   patch lines 42-55) correctly matches the project's SPDX header convention (`SPDX-FileCopyrightText:
   Copyright (c) 2025 NVIDIA CORPORATION...` / `SPDX-License-Identifier: LicenseRef-Apache2` +
   full Apache-2.0 boilerplate), matching the header on the file it modifies
   (`state_dict_convert.py`). No violation there.
4. Commit subject "AMPLIFY: preserve dtype/device in `_pad_weights` padding rows" matches the
   `<scope>: <description>` convention visible in the one base-repo commit ("ci: limit Dependabot to
   security updates only (#1753)").
5. `CONTRIBUTING.md`'s "Local Checks" section doesn't apply here (this isn't a copied file per
   `ci/scripts/check_copied_files.py`'s `SOURCE_TO_DESTINATION_MAP`, per the draft's own note that
   this is AMPLIFY-specific, unlike the THD fix) — correctly not run.
No CLA/DCO issue-first process beyond item 2. Fix the PR-body/template mismatch before submitting.

---

### bionemo-thd
Verdict: FIX-REQUIRED
Confidence: medium-high
Findings:
1. Same PR-template mismatch as bionemo-amplify: this draft also uses a custom
   Provenance/Summary/Fix/Testing/Notes layout instead of the repo's actual
   `.github/pull_request_template.md` (Description/Usage/Type of changes/CI Pipeline
   Configuration/Pre-submit Checklist). Same remediation: remap into the template, check "Bug fix,"
   and answer the four pre-submit checklist items explicitly and honestly (including the caveat that
   full test-suite pass couldn't be verified in-sandbox due to `transformer_engine`/`nvtx` not being
   installable).
2. Same DCO speculation issue as bionemo-amplify — no DCO/CLA bot exists; the actual gate is
   `copy-pr-bot` / `/ok to test` from an NVIDIA org member for untrusted contributors. Drop the DCO
   hedge, mention the actual authorization mechanism instead.
3. **Copied-files propagation correctly identified and executed as a process matter.** `AGENTS.md`
   ("Copied files" section) and `CONTRIBUTING.md` both require: edit the canonical source listed in
   `ci/scripts/check_copied_files.py`'s `SOURCE_TO_DESTINATION_MAP`, then run
   `check_copied_files.py --fix` to propagate to all copies, and never hand-edit destination copies.
   The PR-DRAFT explicitly states this was done ("Propagated the fix to all 8 enforced copies via
   `python ci/scripts/check_copied_files.py --fix`") — I could not independently verify the 8 copies
   are byte-identical from the patch/packet alone (that requires diffing the fixed tree against all
   8 destinations, which is really an executor-level check), so I'm flagging this as unverified by
   me rather than confirmed, but the process described is the correct one per `AGENTS.md`.
4. License header on the new test file
   (`models/esm2/tests/test_cp_thd_divisibility_guard.py`, patch lines 66-79) correctly matches the
   SPDX/Apache-2.0 header convention.
5. Commit subject "esm2/collator: guard THD context-parallel sharding against non-divisible padded
   lengths" matches the `<scope>: <description>` convention.
6. Good process discipline beyond what's required: the draft proactively checked GitHub issue
   #1561 to confirm it's related-but-distinct rather than a duplicate, before writing "not a
   duplicate" in the notes. That's the right move given the general climate of maintainers being
   skeptical of AI-surfaced reports.
Fix the PR-body/template mismatch and the DCO note before submitting; ask the executor/validator to
confirm the 8-copy propagation is exact.

---

## Overall summary

Of nine: **4 SHIP** (aiohttp-readuntil, chi-gethead, otel-urlparser, otel-forwarded), **1 SHIP**
(calibre-opds) — so 5 clean — and **4 FIX-REQUIRED** (express-cookie, assertj-percentage,
bionemo-amplify, bionemo-thd). No REJECTs from a pure process-compliance lens (I'm not assessing bug
correctness or reproduction quality, per my charter).

The two repos with published, AI-aware contribution norms (aiohttp, OpenTelemetry) are the two where
the drafts are most precisely compliant — they clearly targeted those policies directly (exact
disclosure-line format, exact `Assisted-by:` trailer). The repos where the drafts stumble are the
ones with either an unpublished/unmodeled process (express's issue-first step, bionemo's actual PR
template) or a contributor agreement that's flatly incompatible with AI-assisted authorship as
disclosed (assertj's 100%-authored clause) — that last one is the most serious finding on this
panel: it's not a missing checkbox, it's the draft admitting mid-document that it doesn't know if
it's allowed to exist.

Not independently verified by me (flagging rather than fabricating): the exact wording of the OpenJS
AI Coding Assistants Policy (fetch attempts to openjsf.org returned empty in this sandbox); whether
the assertj test rows follow the `should_pass_xxx`/`GIVEN`/`WHEN`/`THEN` conventions (packet-only
review, didn't diff the fixed test file); whether bionemo-thd's 8 copied-file destinations are
byte-identical after `--fix` (needs a tree diff, not just the patch).
