# S8 — contribution-process compliance review (round 2)

Persona: contribution-process compliance reviewer. Checked each v2 patch/PR-DRAFT against its
project's own CONTRIBUTING/AGENTS/PR-template/changelog/commit-message/CLA/AI-policy/license-header
rules, read from the base checkout under `/tmp/review/src/<repo>/base/`, plus one upstream fetch
(issue #15158, cited in the otel-urlparser draft) to spot-check a citation. I did not read other
reviewers' files, only `SYNTHESIS.md` and each fix's `CHANGES-FROM-V1.md` as instructed, plus the
round-2 exec-A/exec-B reports.

---

### aiohttp-readuntil
Verdict: FIX-REQUIRED
Confidence: high

Findings:
1. `AGENTS.md` "Changelog" section: fragments are named `CHANGES/{pr_or_issue}.{type}.rst`; every
   fragment on `master` (checked `CHANGES/13561.contrib.rst`, `13509.bugfix.rst`, `3310.bugfix`,
   etc., and `CONTRIBUTING.rst`'s own instruction "name it `<issue_or_pr_num>.<type>.rst`, e.g.
   `588.bugfix.rst`") uses a real number. The patch ships `CHANGES/PRNUMBER.bugfix.rst` — a literal
   placeholder, not a number. It must be renamed to the actual PR number after the PR is opened
   (`git mv CHANGES/PRNUMBER.bugfix.rst CHANGES/<N>.bugfix.rst`) before merge, or CI's towncrier
   check will not recognize it as a valid fragment name.
2. `AGENTS.md` "PRs" — disclosure line: `Drafted with <agent name and version>; reviewed by <human
   handle>.` PR-DRAFT.md ends with exactly `Drafted with Claude Opus 5.5; reviewed by
   andrewstellman.` — compliant.
3. `AGENTS.md` — "No `Co-Authored-By:` LLM trailers in commits or PR body." Commit message has no
   trailer of any kind — compliant.
4. `AGENTS.md` — "Commits: Don't use conventional commits; match recent imperative subjects."
   Subject `Fix readuntil() missing a separator split across chunks` is imperative, not
   conventional-commit-prefixed — compliant. Matches the style of the base tree's own last commit
   (`Fix secure shared cookie (#13830)`).
5. `.github/PULL_REQUEST_TEMPLATE.md` sections (What do these changes do? / Are there changes in
   behavior? / substantial burden? / Related issue number / Checklist) are all present and answered
   in PR-DRAFT.md — compliant. The "Documentation reflects the changes" box is left unchecked with
   `N/A, no API change` written next to it, matching `AGENTS.md`'s "write N/A next to ones that do
   not [apply]" instruction — compliant.
6. `CONTRIBUTORS.txt`: patch adds `Andrew Stellman` in alphabetical position between `Andrew Lytvyn`
   and `Andrew Svetlov` — compliant with the template's "keep alphabetical order" instruction.
7. `AGENTS.md` — "Agent run output (test logs) goes in a collapsed `<details>` block below the
   template summary." The test-output block is a collapsed `<details>` below all the template
   sections — compliant.

Round-1 required changes: made / not made, item by item (from `CHANGES-FROM-V1.md`):
1. Single AGENTS.md-form disclosure line [O1, O5, S3] — made.
2. Keep `CHANGES/PRNUMBER.bugfix.rst`, rename after the PR exists [O1, S8] — made (kept as-is, with
   the rename step documented in `NOTES-FOR-ANDREW.md`, not in the PR body itself). This is the
   correct call for the PR body, but it means the rename is still an outstanding manual step for
   Andrew before merge, which is why I still flag it above as FIX-REQUIRED-before-merge rather than
   SHIP — the file as committed today would fail towncrier's filename pattern if left unrenamed.
3. Cut the `<details>` cross-suite counts to short form [O5] — made.
4. State the `max_size` behavior change [O3] — made, in "Are there changes in behavior for the
   user?".
5. Comment on `tail`/`head`/`n` arithmetic [S1] — made (two comment lines added, no code change).
6. Drop `test_readuntil_separator_split_after_wait` [O1, O5] — made.

After reading exec-A.md: exec-A independently reproduced RED (14 failed/10 passed) → GREEN (24
passed) → REVERT (14 failed, same set) → SUITE (136→160 passed, no regressions), confirming the
functional claim. That doesn't change any compliance finding above.

---

### otel-urlparser
Verdict: FIX-REQUIRED
Confidence: high

Findings:
1. `CONTRIBUTING.md` "Changelog": "Do not add a changelog entry for normal changes." This is a bug
   fix, not a breaking/deprecation change, and the patch does not touch `CHANGELOG.md` —
   compliant.
2. `.github/pull_request_template.md` is only an HTML comment reminding not to add a changelog
   entry unless deprecating/breaking. PR-DRAFT.md has no HTML comments addressed to a maintainer or
   to Andrew and doesn't add a changelog entry — compliant.
3. Commit trailer `Assisted-by: Claude Opus 5.5` on its own line after a blank line — correct git
   trailer form, matching the maintainer-context recommendation ("OpenTelemetry ... recommends an
   `Assisted-by:` trailer").
4. EasyCLA: nothing in this checkout enforces or records EasyCLA sign-off (it's a GitHub-App-level
   org policy, not a repo file), so I can't verify it directly here, but per the brief's maintainer
   context this is required and isn't something a patch file can satisfy — it's an account-level
   action. **Action item, not a patch defect**: Andrew must have EasyCLA signed under the GitHub
   account that opens the PR before the PR can be merged (the check runs automatically on PR open).
5. Citation check: PR-DRAFT.md says "the same as `HostAddressAndPortExtractor` (#19540)" and that
   the pulsar `UrlParser` "has the same first-`:` split." I fetched
   `github.com/open-telemetry/opentelemetry-java-instrumentation/issues/15158` — it is titled
   "Consider ipv6 when extracting server name from host header," opened by `@laurit`, and closed by
   `#19540`. The citation is accurate.
6. No `CONTRIBUTING.md` requirement to open an issue first for a bug fix — compliant without one.
7. Gradle/spotless: the repo's actual gate is Gradle (`./gradlew :module:check`, which runs
   spotless). Neither the packet nor `CHANGES-FROM-V1.md` show a real Gradle run — only a
   `google-java-format --dry-run` on the changed files (which found no diffs) is offered, and
   `CHANGES-FROM-V1.md` itself says this "is not a substitute for `spotlessCheck`." Round-1's
   requirement to run the actual Gradle check has not been met. **Andrew should run `./gradlew
   :instrumentation-api-incubator:spotlessCheck :instrumentation-api-incubator:check` (and the
   equivalent reactor-netty module target) locally before opening the PR**, since CI will run it
   regardless and a spotless failure is an easy, avoidable red X on a first-time contribution.

Round-1 required changes:
1. Bound the `]` search [O2, O3] — made (verified independently by exec-B: base gives `"["`/`"[x"`
   for the two malformed rows, fix gives `null`).
2. Gradle/spotless run [O1, O4, O5, exec-B] — **not made**; `google-java-format --dry-run` was
   substituted and the evidence file itself says so. This is a disclosed substitution, which is the
   right way to handle an environment gap, but the underlying gate is still open.
3. Remove HTML provenance comment, keep `Assisted-by:` [O1, O5] — made.
4. Sign EasyCLA [O1, O4, O5] — Andrew's action, not verifiable from the patch; correctly deferred to
   `NOTES-FOR-ANDREW.md` per `CHANGES-FROM-V1.md`.
5. Mention ClickHouse caller [O1, O4] — made (named in PR body).
6. Mention pulsar follow-up [O1, O3] — made.
7. State `getPort()` now returns the port [S5] — made.

After reading exec-B.md: independent javac+JUnit run confirms RED/GREEN/REVERT/SUITE exactly as
claimed, and separately confirms the two malformed-URL rows (base → `"["`/`"[x"`, fix → `null`).
Exec-B explicitly lists everything Gradle-specific that was *not* run (compileJava/compileTestJava
for the full module, `spotlessCheck`, checkstyle, error-prone, muzzle, japicmp) — this independently
confirms finding 7 above; the Gradle gate is still fully open, not partially covered.

---

### otel-forwarded
Verdict: SHIP (after the same two account/environment actions as otel-urlparser)
Confidence: high

Findings:
1. Same changelog / PR-template / commit-trailer analysis as otel-urlparser applies verbatim and is
   compliant for the same reasons (no `CHANGELOG.md` entry added; `Assisted-by:` trailer present and
   correctly formed; no HTML comments in the PR body).
2. Follow-up framing: PR-DRAFT.md correctly cites "#15158 / #19540" as the issue/fix this is a
   sibling of — same citation verified above.
3. Same Gradle/spotless gap as otel-urlparser: `CHANGES-FROM-V1.md` reports a `google-java-format
   --dry-run` substitute only, explicitly flagging one unrelated pre-existing formatting complaint in
   `HttpServerAttributesExtractorTest.java` (lines the patch doesn't touch, and the same flag appears
   on base) so it isn't new. Real `spotlessCheck` still not run — same action item as urlparser:
   **run `./gradlew :instrumentation-api:spotlessCheck :instrumentation-api:check` locally before
   opening.**
4. Same EasyCLA action item as urlparser.
5. No new files, so no license-header question.

Round-1 required changes:
1. Gradle/spotless [O1, O4, O5, exec-B] — not made (same disclosed substitute).
2. Remove HTML comment, keep trailer [O1, O5] — made.
3. Sign EasyCLA [O1, O4, O5] — Andrew's action.
4. Mention unterminated-`[` fall-through [S5, O2] — made (explicit paragraph in PR body).
5. Clearer comment wording [S2] — made, and `CHANGES-FROM-V1.md` flags a real nuance worth keeping in
   mind: the new wording is nicer prose but diverges from the terse in-repo convention at
   `HttpServerAddressAndPortExtractor.java:91`; a maintainer could ask for the terser house style
   back. Not a compliance defect, just a heads-up.

After reading exec-B.md: independently confirms RED (23/127 fail, exact patterns) → GREEN (127/127)
→ REVERT (same 23 fail) → SUITE (429→452, clean). Same Gradle-not-run disclosure as urlparser.

I'm marking this one SHIP rather than FIX-REQUIRED (unlike urlparser) because its only open items are
the two account/environment actions (EasyCLA, Gradle spotless check) that apply identically across
both otel fixes and are not defects in the patch text itself — there is no unresolved code-level gap
like urlparser's unbounded-`]`-search finding from round 1. If you want one bar for both, downgrade
this to FIX-REQUIRED too, since the Gradle gate is equally unmet on both.

---

### calibre-opds
Verdict: SHIP
Confidence: high

Findings:
1. calibre has no `CONTRIBUTING.md`, no `.github/pull_request_template.md`, and no `AGENTS.md` /
   `CLAUDE.md` at the repo root that governs external contribution process (there is a
   `local-agent.md` — see below). Contribution guidance lives only in the external manual page
   linked from `README.md`. There is nothing to check the PR body's structure against beyond
   general correctness and the maintainer-context note.
2. `local-agent.md` at repo root is an AI-agent runtime/environment config (build/test/verification
   commands: `./setup.py build`, `./setup.py test`, `./setup.py check --fix --no-editor && ./setup.py
   type_check`) that explicitly says "Do not use generic toolchains such as `pytest`." PR-DRAFT.md's
   verification section describes running `ruff check`/`ruff format --check` and a hand-built
   stub-execution harness under plain `pytest`-style execution — it does not report running
   `./setup.py build`, `./setup.py test`, or `./setup.py type_check`. This is a real gap against the
   repo's own documented verification pipeline, though a large mitigating fact applies: `opds.py`'s
   handlers have zero existing test coverage (`srv/tests/ajax.py:374`: "Not going test legacy and
   opds as they are too painful") and, per exec-A's independent reproduction, `setup.py test
   find_tests` fails before collection on a CPU-only sandbox because it needs calibre's compiled
   extensions (`ModuleNotFoundError: No module named 'calibre_extensions.translator'`). So the
   documented pipeline can't fully run here either way. **Andrew should still run `./setup.py build`
   and `./setup.py check --fix --no-editor` on his own machine (which has the compiled extensions)
   before opening the PR**, and say so in the PR body instead of only citing ruff, since `local-agent.md`
   is the repo's own stated bar for AI-assisted changes and a maintainer could reasonably ask why it
   wasn't followed.
3. No CLA/DCO/Signed-off-by requirement found anywhere in this checkout.
4. No new files created — no license-header question. (calibre files that do exist, e.g.
   `src/calibre/srv/opds.py`, don't carry a per-file SPDX/license header to match.)
5. Maintainer-context check: "None of these are security issues" (Kovid's past pushback on framing).
   PR-DRAFT.md frames this purely as a 404-vs-500 correctness/log-noise fix, with no "security" or
   "vulnerability" language anywhere — compliant with that lesson.
6. Commit message is a single-line imperative subject, no trailer, no body — fine for a change this
   size and consistent with what a maintainer merging small fixes from the same tool would expect
   (per the brief's context that Kovid has already merged similar small fixes).

Round-1 required changes:
1. Send the three-handler (`alt/`) version [O1, O2, O3, O4, O5, S3, S4, exec-A] — made; this is now
   the only patch and touches `opds_navcatalog`, `opds_category`, `opds_categorygroup`.
2. Drop the `if not which` check (unreachable over HTTP) [O1, O4, O5] — made; not present in this
   patch's diff, and `CHANGES-FROM-V1.md` documents the reachability proof, independently
   re-confirmed by exec-A's own reachability table.
3. Delete the bracketed "[If sending the alternative patch, add:]" placeholder [O1, O4, O5, S2, S3]
   — made; PR-DRAFT.md is three clean paragraphs with no editorial placeholders.
4. Cut the body, no security framing — made (see finding 5 above).

After reading exec-A.md: independently re-ran the harness against RED (4 unhandled exceptions:
`IndexError`, two `binascii.Error` variants, `UnicodeDecodeError`) → GREEN (drops to 1, the
documented-unreachable empty case) → REVERT (back to 4) — matches the packet's own claims exactly.
This doesn't change the compliance verdict; the `local-agent.md` verification-pipeline gap (finding
2) stands regardless of what the harness numbers show, since that gap is about which commands were
run, not whether the fix works.

---

### bionemo-amplify
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. `.github/pull_request_template.md` sections (Description / Usage / Type of changes / CI Pipeline
   Configuration / Pre-submit Checklist) are all present in PR-DRAFT.md, in the template's order —
   compliant, and a real improvement over a from-scratch layout.
2. Pre-submit Checklist: three of four boxes are left unchecked (`I have tested these changes
   locally`, `I have updated the documentation accordingly`, `All existing tests pass successfully`)
   each with an inline explanation of why (no GPU, N/A, relying on CI). The template gives no "N/A"
   convention the way aiohttp's does, so an unchecked box could be misread as "not done" rather than
   "honestly can't verify here" — worth a one-line addition ("see note") right after the checklist to
   make the distinction obvious to a first-time reader who doesn't parse the inline parentheticals.
   This is a clarity nit, not dishonesty — the parenthetical text is accurate and undersells nothing.
3. `AGENTS.md` "General development": "Add or update focused tests when changing model behavior,
   conversion logic..." — satisfied, `test_pad_weights_dtype_device` added right next to
   `test_convert_state_dict` per `CHANGES-FROM-V1.md`.
4. `AGENTS.md` "Copied files": `state_dict_convert.py` is **not** listed in
   `ci/scripts/check_copied_files.py`'s `SOURCE_TO_DESTINATION_MAP` (checked directly — only
   `models/amplify/src/amplify/state.py` appears under "amplify"), so no copy-sync step applies here
   — correctly not attempted.
5. "Authorizing CI Runs" (`.github/pull_request_template.md`): as a presumably-untrusted first-time
   contributor, CI will not run until "an NVIDIA org member... leave[s] an `/ok to test` comment."
   Nothing in the PR text needs to address this — it's on the maintainers — but Andrew should expect
   the PR to sit with no CI signal until that happens, and shouldn't read silence as a problem with
   the PR.
6. No CLA/DCO/Signed-off-by requirement found in `CONTRIBUTING.md` or the PR template.
7. Commit message: 4 lines (subject + 3-line body describing the bug and the fix), no
   `Co-Authored-By`/`Assisted-by` trailer, no AI-attribution convention documented anywhere in this
   repo's own files (unlike aiohttp/otel) — nothing to check it against beyond "does it read like it
   was written by the author," and it does.
8. License headers: `state_dict_convert.py` and other files in this repo do carry SPDX headers
   (`SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION...` / `SPDX-License-Identifier:`),
   but no new file is created by this patch (the test is added to an existing file), so no header is
   needed and none is missing.
9. **Round-1's still-unresolved concern, restated for compliance**: the PR checklist item "I have
   tested these changes locally" is honestly unchecked, but the PR's own prose still leans on
   untested reasoning for its headline claim about full-conversion impact ("most likely fails,"
   "should fail in `torch.cat`") — this is disclosed as unverified in the same paragraph, which is
   the right pattern, but it's worth Andrew flagging in the PR itself that CI is the only place this
   can be confirmed, since a reviewer skimming only the top of the description could still walk away
   thinking the impact claim was confirmed.

Round-1 required changes (from `CHANGES-FROM-V1.md` and `SYNTHESIS.md`):
1. Correct the impact claim, frame as matching `_pad_bias`/ESM2 [O1, O4, O5, S3, S8] — made; "silently
   upcasts" language is gone, replaced with the function-level fact plus explicitly-labeled
   speculation about `apply_transforms`.
2. Fix misattached clause implying ESM2 has the bug [O3, O4, O5] — made (commit body rewritten).
3. Rewrite into repo's own PR template, delete provenance/DCO-speculation/evidence-README references
   [O1, O5, S3, S8] — made.
4. Move test into `tests/test_amplify_model.py`, cut docstring, use 2026 in any new header [O1, O4,
   O5] — made for the move and docstring; N/A for the header since no new file/header was created.
5. Device assertion pinned nothing (CPU-to-CPU) [S4] — made; now parametrized `cpu`/`cuda` with a
   `skipif` guard, and PR text says only the CPU half ran.

After reading exec-A.md: independently re-ran RED (fp32-vs-bf16 assertion fails on base source) →
GREEN (passes on v2) → REVERT (fails again, identical assertion) using the harness's own
`run_extracted.py`, and independently reproduced the "real suite uncollectable" claim
(`ModuleNotFoundError: No module named 'datasets'`) on both base and fixed. This confirms the PR's
verification claims are accurate as stated; it doesn't change the checklist-clarity finding above.

---

### bionemo-thd
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. Same PR-template-section compliance as bionemo-amplify — compliant, same structure.
2. Same Pre-submit Checklist pattern (3 of 4 unchecked with inline reasons) — same clarity nit as
   amplify: consider one line making explicit that unchecked ≠ untested-and-unexplained.
3. `AGENTS.md` "Copied files": `models/esm2/collator.py` **is** an intentionally-duplicated file (10
   total copies across `models/{esm2,llama3,mixtral,qwen}` and 6 `recipes/*`, per the patch's own
   file list). The commit message states the copies were regenerated with `python
   ci/scripts/check_copied_files.py --fix`, and `CHANGES-FROM-V1.md` confirms `python
   ci/scripts/check_copied_files.py` then exits 0. Exec-A independently re-ran the checker against
   the patched tree (exit 0) and, as a sanity check that the checker isn't a no-op, against a
   deliberately-desynced copy (correctly failed with a specific mismatch error) — this is exactly the
   procedure `AGENTS.md` requires and is fully satisfied.
4. `AGENTS.md` "General development": tests added/updated for the changed behavior — satisfied, two
   new tests in `test_collator_context_parallel.py`.
5. Error message quality (this is a user-facing string, not process compliance, but the round-1
   synthesis raised it under this fix's required changes so I checked it): "Padded sequence length(s)
   [10] must be divisible by 4 (2 * cp_world_size) for THD context parallelism; set
   pad_sequences_to_be_divisible_by to a multiple of 4" — no private function name, actionable,
   truncates to 5 lengths + "(and N more)" for large batches. Matches round-1's ask.
6. Same "Authorizing CI Runs" / `/ok to test` gate as amplify — same note: expect no CI signal until
   an NVIDIA member comments.
7. No CLA/DCO requirement found; no new files, so no license-header gap.
8. Commit message: 6 lines per `CHANGES-FROM-V1.md`, no AI-attribution trailer (same as amplify — no
   documented convention to check against in this repo).

Round-1 required changes:
1. Replace "silently lose training tokens" with the demonstrated fact only [O1, O3, O4] — made; PR
   states the collator drops remainder tokens and explicitly says TE's downstream handling "was
   never checked."
2. State `L0_sanity_cp.yaml` is safe, guard is for user overrides [O4, O5] — made, with the specific
   numbers (16, `cp_size: 2`) and the one other config that sets the value (mixtral, doesn't use CP).
3. Actionable error message, drop private function name [O1, O2, O5] — made (see finding 5).
4. Note CP-rank scatter timeout when rank 0 raises; offer config-time-check alternative [O2, O1, O4]
   — made (both present as explicit paragraphs).
5. Warn that a config that silently dropped tokens will now fail [S5] — made ("Behaviour change" line
   in the Description).
6. Repo PR template; move tests; trim commit message [S3, S8, O1, O4, O5, S2] — made.

After reading exec-A.md: independently re-ran RED (regression test DID NOT RAISE on base; harness
demo shows positions [16, 17] dropped) → GREEN (6 passed, demo raises the exact message) → REVERT
(fails again identically) → `check_copied_files.py` (exit 0 on the patched tree, and independently
verified the checker itself is a real comparator, not a no-op, by breaking one copy and watching it
fail). This confirms the compliance-relevant "copies regenerated and verified" claim in finding 3 is
not just asserted but independently checked.

---

## Overall summary

- **Two fixes are ready to submit as-is**: calibre-opds and otel-forwarded (the latter modulo two
  account/environment actions that aren't patch defects).
- **Four fixes need action before submission**, none of them code changes:
  - aiohttp-readuntil: rename `CHANGES/PRNUMBER.bugfix.rst` to the real PR number after opening the
    PR (or the towncrier check will reject the filename).
  - otel-urlparser: run the real `./gradlew :module:spotlessCheck :module:check` locally (only a
    `google-java-format --dry-run` substitute has been run so far) — same for otel-forwarded, and
    both need EasyCLA signed on Andrew's GitHub account before either PR can be merged.
  - calibre-opds: optionally run `./setup.py build` / `./setup.py check --fix --no-editor` on a
    machine with calibre's compiled extensions, since `local-agent.md` documents that pipeline as the
    project's own bar for AI-assisted changes, even though the sandbox here genuinely can't run it.
  - bionemo-amplify / bionemo-thd: no outstanding compliance defects found beyond the checklist-
    clarity nit (unchecked boxes read ambiguously without reading the inline parenthetical); both
    will sit with no CI signal until an NVIDIA org member comments `/ok to test`, which is expected,
    not a sign of a problem.
- I did not find a CLA/DCO/Signed-off-by requirement for aiohttp, calibre, or bionemo-recipes in
  their own repo files — only OpenTelemetry (both otel fixes) has one, per the brief's maintainer
  context (EasyCLA), which I could not independently verify from the checkout since it's an
  org-level GitHub App, not a repo file.
- Nothing I checked required a new file, so the "license headers on new files" item in my brief is
  N/A for all six fixes as submitted (all patches modify existing files only).
- Not checked: whether Andrew's GitHub account is currently EasyCLA-signed for the OpenTelemetry
  org (no tool available here to check that), and whether `local-agent.md`'s build/test/type_check
  commands would actually pass on Andrew's own machine for calibre (only ruff was run here, and the
  sandbox can't run the compiled-extension build to check further).
