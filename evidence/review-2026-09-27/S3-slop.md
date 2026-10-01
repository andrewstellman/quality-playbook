# S3 — "maintainer who rejects AI slop PRs" — independent review

Reviewed the packet (patch + commit message + PR-DRAFT.md) and the base checkout's own PR template / CONTRIBUTING / AI policy for each of the nine fixes. Did not coordinate with any other reviewer. Where I say "did not check," I mean it — I did not run code beyond reading diffs and, where noted, grepping the base checkout for template/policy text.

---

### aiohttp-readuntil
Verdict: SHIP
Confidence: high
Findings:
1. `packets/aiohttp-readuntil/PR-DRAFT.md` follows the shipped template (`base/.github/PULL_REQUEST_TEMPLATE.md`) section-for-section, and the base `AGENTS.md` "PRs" section (draft via `gh pr create --draft`, no `Co-Authored-By:`, one-line disclosure `Drafted with <agent>; reviewed by <human>`) is satisfied exactly: "Drafted with Claude Opus 5.5; reviewed by @andrewstellman." Patch has no `Co-Authored-By:` trailer.
2. Checklist is honestly filled: "Documentation reflects the changes: N/A" with a reason, "Related issue number: None found" — no invented issue link.
3. Test evidence block gives concrete before/after pytest counts (16 failed→26 passed; full suite 162 passed; before/after full-repo counts), which is exactly what a maintainer wants instead of a prose claim. Not a generated-sounding "I have thoroughly tested this" — it's a command and a number.
4. Minor: the PR draft adds a second attribution line below the required AGENTS.md disclosure line ("Found by a Quality Playbook run; reproduction and fix by Claude.") — redundant with the line above it. Cut it; AGENTS.md asks for exactly one plain line, and having two invites a maintainer to read this as over-explaining.
5. Test additions (124 lines, 9 new test functions) are large for a one-bug fix, but each covers a genuinely distinct edge case (chunk-boundary split, one-byte-at-a-time feed, partial-overlap false starts, EOF mid-separator, max_size interaction). Not padding — I'd keep all of them.

What to cut before submitting: the duplicate attribution sentence (finding #4). Nothing else.

---

### chi-gethead
Verdict: SHIP
Confidence: high
Findings:
1. `chi`'s `CONTRIBUTING.md` (base checkout) has no PR template and no AI policy — nothing to violate.
2. `PR-DRAFT.md` is proportionate to the diff: a 4-line repro snippet, one paragraph of mechanism, one sentence on test status ("It fails on master and passes with the fix. `go test ./...` passes."). No restating-the-diff-in-prose padding, no unsupported claims.
3. Attribution footer ("this issue was found by a Quality Playbook run... reproduction and fix were done by Claude") is a single italic line, appropriately unobtrusive.
4. The new test (`TestGetHeadInMountedRouter`) is properly sized — two assertions, no bloat.

Nothing to cut.

---

### express-cookie
Verdict: FIX-REQUIRED
Confidence: high
Findings:
1. The draft itself admits the process isn't finished: checklist item "Issue created first and referenced" is unchecked, and a template section literally says "Read the OpenJS AI Coding Assistants Policy... and adjust the disclosure line if it requires specific wording" — unchecked. Per the brief, "express asks for an issue before a PR." Submitting before that step is done invites an immediate close, independent of code quality.
2. No local `CONTRIBUTING.md`/PR template in this checkout (`base/.github` has only CI workflows) — the draft correctly says the template comes from the org-level `expressjs/.github` repo and quotes it from memory rather than fabricating a checklist it can't see. I did not independently fetch `expressjs/.github` to confirm the DCO-comment claim; flagging as unverified rather than asserting it's right.
3. The patch and test are appropriately small (5 lines + 2 tests) and the PR body is not padded — one paragraph of mechanism, one paragraph of fix, one line of test evidence ("`npm test` passes (1263) and `npm run lint` is clean"). No slop signature in the writing itself.
4. Not a code problem: this is a "don't submit yet" gate, not a "rewrite the patch" gate.

What must change before submission: open the issue first (or confirm express's async policy allows skipping it for a one-line security-adjacent fix), and check the OpenJS AI policy wording before finalizing the disclosure line. The patch/tests can ship as-is once that's done.

---

### otel-urlparser
Verdict: SHIP
Confidence: medium
Findings:
1. Patch carries `Assisted-by: Claude Opus 5.5` trailer, consistent with the brief's claim that OTel's generative-AI policy recommends it. I could not find the generative-AI policy text itself in this checkout (`base/CONTRIBUTING.md` has no AI/generative/EasyCLA section, and `base/.github/pull_request_template.md` is a two-line changelog reminder with no checklist) — so I can't confirm the exact required wording, only that the trailer is present and plausible. Flagging as unverified against source, not fabricated.
2. `PR-DRAFT.md` is tight: one repro snippet showing the actual wrong return values, a two-bullet "visible effects" list tied to real call sites (reactor-netty spans, `service_peer_mapping`), and a cross-reference to the sibling fix (`HostAddressAndPortExtractor`, #19540) instead of re-deriving the rationale from scratch. That cross-reference is a good sign — it shows the author looked at prior art rather than reinventing.
3. No unsupported claims: doesn't claim CVE/security severity, doesn't invent an issue number.

Nothing to cut. Confidence is medium only because I couldn't locate OTel's actual generative-AI policy text to check the trailer wording against it — should be confirmed before submission, but that's a verification gap, not a slop signal.

---

### otel-forwarded
Verdict: SHIP
Confidence: high
Findings:
1. Same `Assisted-by: Claude Opus 5.5` trailer as otel-urlparser.
2. `PR-DRAFT.md` explicitly ties itself to two prior issues/PRs ("Follow-up to #15158 / #19540") and explains why this is a *different* code path from the already-merged sibling fix, rather than just asserting novelty. That's the opposite of an unsupported claim — it's pre-empting the maintainer's first question ("didn't we already fix this?").
3. Concrete failure-mode quote in the draft ("expected: `2001:db8::1` but was: `[2001`") is a real assertion failure message, not a paraphrase.
4. Proportionate: one paragraph of mechanism, one paragraph of fix, one line of test description.

Nothing to cut.

---

### assertj-percentage
Verdict: REJECT (as currently packaged — see below)
Confidence: high
Findings:
1. `base/CONTRIBUTING.md:165-172` ("Legal Disclaimer"): **"You will only submit contributions where you have authored 100% of the content."** This project's contribution policy is a flat prohibition on submitting AI-authored code, full stop — not a disclosure-and-proceed policy like aiohttp's or OTel's. A patch whose commit message says "Reproduction, the test, and the fix were done by Claude (Anthropic)" is exactly the thing this clause exists to block.
2. To the packet's credit, the PR draft does *not* paper over this — it puts it in an explicit "Before opening (for Andrew)" checklist item: "Decide whether CONTRIBUTING's Legal Disclaimer... is compatible with submitting Claude-authored code." That is the single best piece of self-awareness in any of the nine packets; it's the opposite of a slop tell. But it doesn't resolve the conflict, it just surfaces it.
3. Given the brief's maintainer context ("a psf/requests maintainer recently accused a similar report of being LLM-fabricated... maintainers are primed to reject AI-generated PRs"), an assertj maintainer who reads a Claude-authored diff against a "100% authored" clause has grounds to close on sight, independent of whether the fix is correct.
4. The fix itself is small and plausible (`BigDecimal.toPlainString()` for the integral branch, two added test rows), and the draft honestly surfaces the `BigDecimal` vs. `(long)` tradeoff as an open decision rather than asserting one is obviously right — no slop there.

What must change: this cannot go out as a Claude-authored diff under this project's contribution terms. Either Andrew re-derives and writes the patch himself (using the finding only as a lead, not as text to paste), or it isn't submitted to this project. I'm not the right reviewer to decide whether a human rewrite still counts as compliant once Claude found the bug and drafted the reference implementation — that's a policy call for the operator, not a code-quality one — but the patch as packaged cannot be submitted with its current provenance line.

---

### calibre-opds
Verdict: FIX-REQUIRED
Confidence: high
Findings:
1. `PR-DRAFT.md` contains an unresolved internal instruction left in the draft: **"[If sending the alternative patch, add:] `opds_category` and `opds_categorygroup` decode their ids the same way and had the same 500, so they get the same `try/except`."** This is a bracketed note-to-self about a variant that isn't in the packet — the patch only touches `opds_navcatalog`. If pasted into a real PR body as-is, a maintainer sees an editorial fragment that was never cleaned up, which is exactly the "obviously-not-reviewed-by-a-human" tell this review is looking for.
2. I checked the base source (`base/src/calibre/srv/opds.py:675,687,726,739,745`): `opds_category` and `opds_categorygroup` do call `from_hex_unicode` on unguarded input the same way `opds_navcatalog` did, so the bracketed claim is technically accurate — but the packet ships a decision that was never made (fix one function or three?) baked into stray text instead of into the patch or a clear scope statement.
3. The draft's discipline on tone is otherwise good: it explicitly tells Andrew "do not call it a security fix," directly responding to the calibre maintainer's past complaint ("None of these are security issues") — that's the right lesson learned, correctly applied, not slop.
4. calibre's actual contribution process (README: GitHub for PRs only, Launchpad for bugs, no PR template, no CLA) is correctly described; nothing invented.

What must change: either extend the patch to cover all three sibling functions (`opds_category`, `opds_categorygroup`) with one `try/except` pattern, or delete the bracketed note and explicitly scope the PR body to "this fixes `opds_navcatalog` only; the sibling functions have the same bug and are not in scope of this PR" so the maintainer isn't left wondering whether a second version exists.

---

### bionemo-amplify
Verdict: FIX-REQUIRED
Confidence: high
Findings:
1. The project's real PR template (`base/.github/pull_request_template.md`) has a specific shape: `### Description` + a `#### Usage` code-snippet block + a `### Type of changes` checkbox list + a CI-label section + a `### Pre-submit Checklist`. `PR-DRAFT.md` uses none of this — it substitutes its own headers ("Provenance," "Summary," "Fix," "Testing," "Notes for maintainers"). This is the exact "does it follow the project's actual PR template" failure the brief asks me to check for, and it's the clearest one in the batch: nobody appears to have opened `.github/pull_request_template.md` before drafting.
2. Disproportionate explanation for the change size: the patch is one line (`torch.zeros(..., dtype=..., device=...)`) plus a 43-line test. The draft has a "Summary" paragraph and then a "Fix" paragraph that re-states the same mechanism a second time in slightly different words ("builds its zero-padding rows with a bare `torch.zeros(...)`" / "Add the same two kwargs AMPLIFY's ESM2 sibling already uses"), followed by a "Testing" paragraph and a "Notes for maintainers" paragraph speculating about a scenario ("a bf16/CUDA `from_pretrained` call is an ordinary way to invoke it") that isn't demonstrated to occur anywhere in the repo's own code paths — it's presented as a hedge against "this hasn't caused visible breakage," which is honest, but the whole apparatus is a lot of prose wrapped around a one-line dtype/device fix. This is the shape of PR the Linux NVMe maintainer quoted in the brief was complaining about ("a very long explanation for a simple protocol fix").
3. To its credit, the draft does not fabricate a full-suite test run — it's explicit that `transformer_engine` isn't installable in the sandbox and describes exactly what was and wasn't verified ("dependency-free harness reproducing `_pad_weights`' logic outside the module"). That's an honest scoping of what was checked, not an overclaim.
4. No DCO/Signed-off-by claim overreach — draft flags it as unknown and asks the maintainer to advise, rather than asserting compliance either way.

What must change: rewrite the PR body into the project's actual template (Description / Usage snippet / Type of changes / Pre-submit checklist), delete the redundant Summary/Fix split (say the mechanism once), and cut or shrink "Notes for maintainers" to the one sentence that matters (the disclosure line already covers provenance).

---

### bionemo-thd
Verdict: FIX-REQUIRED
Confidence: medium
Findings:
1. Same PR-template non-compliance as bionemo-amplify: this draft also ignores `.github/pull_request_template.md`'s Description/Usage/Type-of-changes/Pre-submit-checklist shape in favor of an invented Provenance/Summary/Fix/Testing/Notes structure. Given both bionemo packets make the identical template-shaped mistake, this looks systematic (the tool/prompt used to draft these doesn't read the target repo's PR template) rather than one-off.
2. Unlike bionemo-amplify, the verbosity here is more justified by real complexity: this is a genuine bug (silent token loss under CP sharding) that fans out across 9 mechanically-identical `collator.py` copies via the project's own `check_copied_files.py --fix` tooling, so a longer explanation of "why is a `ValueError` the right response, and is this reachable in practice" earns its keep. The reachability argument (`L0_sanity_cp.yaml` sets `pad_sequences_to_be_divisible_by` explicitly, bypassing the safe auto-derivation) is concrete and cites a real config file, not a hypothetical.
3. One good practice worth calling out, not cutting: the "Notes for maintainers" section proactively distinguishes this from GitHub issue #1561 and explains why it's not a duplicate ("a related-but-distinct concern in a different code path"). That's the kind of thing that prevents a maintainer from closing as duplicate — it's useful signal, not padding, and I would not ask to cut it despite my general skepticism of "Notes for maintainers" sections.
4. The test file mirrors the project's actual test patterns and stays small (two tests, ~50 lines) for a nontrivial fix — not oversized.
5. Same caveat as bionemo-amplify on Signed-off-by: draft correctly flags it as unverified rather than asserting an answer.

What must change: same template fix as bionemo-amplify (map the sections onto the actual template — Description/Usage/Type of changes/Pre-submit checklist), and merge the "Summary" and "Fix" sections, which currently explain the divisibility mechanism twice back-to-back. Keep the reachability argument and the issue-1561 disambiguation — those are real content, not slop.

---

## Overall summary

Six of nine are essentially clean prose-wise (aiohttp-readuntil, chi-gethead, otel-urlparser, otel-forwarded ship as-is or with a one-line trim; express-cookie is clean but has open pre-submission steps the draft itself flags). Three have concrete, fixable problems:

- **assertj-percentage** is the one genuine stop-sign: the target project's contribution terms flatly prohibit non-self-authored content, and the packet (to its credit) says so itself without resolving it. Don't submit this one under its current provenance.
- **calibre-opds** has a leftover bracketed editorial note that must be deleted or resolved before the PR body is usable, plus an unclear scope decision (one function vs. three).
- **bionemo-amplify** and **bionemo-thd** both ignore the target repo's actual PR template in favor of an invented structure, and bionemo-amplify in particular over-explains a one-line fix in exactly the way the Linux NVMe maintainer quote in the brief warns against.

None of the nine contain fabricated test results, invented issue numbers, or unrelated drive-by changes — the main failure modes here are process (wrong template, policy conflict, leftover draft artifacts) rather than "prose slop" in the classic sense. I did not run any code myself beyond reading diffs; all test-count claims above are as stated in the packets and were not independently re-executed by me.
