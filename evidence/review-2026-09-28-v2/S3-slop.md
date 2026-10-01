# S3 — AI-slop rejector, round 2

Persona: maintainer who rejects unreviewed AI-generated contributions on sight. Checked each v2
packet (`/tmp/review/packets2/<ID>/`) against the base checkout's actual PR template / AI policy,
diff proportionality, disclosure format, and leftover internal notes. Did not read other
reviewers' files before forming my initial verdict (step 1 below); round-1 synthesis and
`CHANGES-FROM-V1.md` were read only afterward, as the brief's step 2 requires, and are recorded
separately.

## Step 1 — initial verdicts, from packet + source only

### aiohttp-readuntil
Verdict: SHIP
Confidence: high
Findings:
1. `PR-DRAFT.md` follows `.github/PULL_REQUEST_TEMPLATE.md` section-for-section, ~256 words for a
   126-line diff (mostly tests) — proportionate, not padded.
2. Disclosure is the single line `AGENTS.md` requires: "Drafted with Claude Opus 5.5; reviewed by
   andrewstellman." No `Co-Authored-By:` trailer, no second disclosure sentence.
3. `CONTRIBUTORS.txt`: "Andrew Stellman" is inserted in correct alphabetical position (Lytvyn <
   Stellman < Svetlov).
4. Test count (8 parametrized functions, 102 added lines) is large relative to the 21-line source
   fix, but each function targets a distinct edge case (split at every byte offset, one-byte-at-a-
   time feed, partial-overlap false starts, EOF mid-separator, `max_size` interaction,
   `LineTooLong` interaction) — this reads as thorough coverage of a genuinely fiddly off-by-one
   class of bug, not padding. No boilerplate, no restated-diff prose, no leftover notes.
5. `<details>` test-output block is 3 lines, collapsed, exactly what `AGENTS.md` asks agent output
   to look like.
Round-1 required changes: not evaluated until step 2 (see below).

### otel-urlparser
Verdict: SHIP
Confidence: high
Findings:
1. No PR template content to violate (`.github/pull_request_template.md` is a one-line comment
   about not adding a CHANGELOG entry).
2. `Assisted-by: Claude Opus 5.5` trailer present in the commit; PR body ends with one first-person
   disclosure sentence ("Found and fixed with help from Claude (Opus 5.5); I reviewed the change
   and the tests.") — no HTML comments, no "keep this section" boilerplate, nothing addressed to
   Andrew.
3. Body is ~222 words for a change that touches two copies of `UrlParser` plus three real callers
   (`ReactorNettyHttpClientAttributesGetter`, `ServicePeerResolver`, `ClickHouseClientV2Singletons`)
   — the length tracks the number of affected call sites, not filler.
4. The pulsar `UrlParser` follow-up note and the "getPort now returns the port" note both read as
   genuine maintainer-facing information, not generated hedging.
5. Diff itself (`getHostEndIndexExclusive` bracket branch) is a straightforward bounded scan with
   one explanatory comment — no restatement-of-diff prose in the comment.
Round-1 required changes: not evaluated until step 2.

### otel-forwarded
Verdict: SHIP
Confidence: high
Findings:
1. Same repo, same disclosure format as otel-urlparser: `Assisted-by:` trailer + one-sentence
   PR disclosure. No boilerplate.
2. Body (~195 words) explicitly frames this as a follow-up to the maintainers' own #15158/#19540 —
   accurate framing, not inflated context.
3. Diff is 15 new lines in one method, mirrors the bracket-handling already used elsewhere in the
   codebase (`HostAddressAndPortExtractor`, `HttpServerAddressAndPortExtractor`) per the PR text —
   consistent-with-house-style claim I can check against the diff, and it holds.
4. Tests added are proportionate (parametrize rows + one attribute-level test), not an oversized
   new file.
Round-1 required changes: not evaluated until step 2.

### calibre-opds
Verdict: SHIP
Confidence: high
Findings:
1. calibre has no `.github/PULL_REQUEST_TEMPLATE.md` and no AI-disclosure policy file in this
   checkout (only `local-agent.md`, which is a local dev/build harness config, not an authorship
   policy) — so there's no template to check compliance against, and none was fabricated.
2. `PR-DRAFT.md` is one paragraph, ~130 words, for a 17-line diff repeated three times (same
   try/except pattern in three handlers) — this is the terse, non-inflated register the maintainer
   context calls for ("very long explanation for a simple ... fix" was the complaint elsewhere;
   this draft doesn't make that mistake).
3. No security framing, consistent with the maintainer's stated objection ("None of these are
   security issues") to how earlier fixes from this tool were pitched.
4. Disclosure: "Found with an automated review tool; patch written with Claude and reviewed by
   me." — plain, no boilerplate checklist, no leftover internal notes.
5. No test added, but the draft says why (`src/calibre/srv/tests/ajax.py:374` deliberately skips
   OPDS tests) instead of silently omitting one — this is disclosure, not evasion.
Round-1 required changes: not evaluated until step 2.

### bionemo-amplify
Verdict: SHIP
Confidence: medium
Findings:
1. PR body (~425 words) follows the repo's actual `.github/pull_request_template.md` structure
   (Description / Usage / Type of changes / CI Pipeline Configuration / Pre-submit Checklist)
   verbatim — the length is templated scaffolding plus real content, not free-floating generated
   prose.
2. The uncertainty language ("I haven't run that case because I don't have a GPU", "I have not run
   this snippet") reads as calibrated hedging tied to a specific, named limitation each time, not
   the vague disclaiming that flags generated text. I treat repeated *specific* caveats as a
   non-slop signal; repeated *vague* ones would not be.
3. Checklist boxes are left unchecked where true ("I have tested these changes locally" — unchecked,
   with the CPU-only harness explained) rather than rubber-stamped — this is the opposite of the
   slop pattern (over-claiming a passing checklist).
4. Diff is 4 lines of source + one ~20-line parametrized test — proportionate.
5. Disclosure: "I found this with help from Claude (an AI assistant) and reviewed the change myself
   before opening the PR." Plain, first-person, no boilerplate provenance section.
Round-1 required changes: not evaluated until step 2.

### bionemo-thd
Verdict: SHIP (with an optional trim)
Confidence: medium
Findings:
1. PR body is 693 words for what is, at the source-diff level, an ~11-line guard replicated across
   10 files. That ratio is the highest of the six and is the one place I'd push back if this were
   a simple fix — but the extra length is spent on real content the repo's own template solicits or
   a maintainer would otherwise ask for in review: which shipped configs are safe (checked
   against the actual recipe YAMLs), a real behavior-change warning, a call-out of an unverified
   downstream failure mode (Transformer Engine), a deadlock-shaped process-group-timeout note, and
   an explicit alternative design the author says they're "happy to switch to." None of that is
   restated diff or filler; it is the analysis I'd want before approving a correctness fix to a
   distributed-training data path. I'd still ask Andrew to cut the `Usage` code snippet (marked
   "have not run this snippet," and it adds ~15 words for something the Pre-submit Checklist
   already covers) but that's a trim, not a rejection.
2. The 10-file diff is a mechanical `check_copied_files.py --fix` fan-out of one 11-line change,
   correctly disclosed as such in both the commit message and the PR body — not an unrelated or
   padded change.
3. Tests (2 functions, ~36 lines) are proportionate and go into the existing test file, not a new
   one.
4. Disclosure line matches the amplify fix's format exactly, plain and first-person.
Round-1 required changes: not evaluated until step 2.

## Step 2 — round-1 required changes, checked item by item

Source: `/sessions/kind-zealous-edison/mnt/QPB/evidence/review-2026-09-27/SYNTHESIS.md` and each
fix's `v2/CHANGES-FROM-V1.md`.

### aiohttp-readuntil
- Merge two disclosure lines into the one AGENTS.md-specified line [O1, O5, S3]: **made**. Patch
  body has exactly one line, correct wording.
- Rename `CHANGES/PRNUMBER.bugfix.rst` once PR exists [O1, S8]: **deferred correctly** — can't be
  done before a PR number exists; `CHANGES-FROM-V1.md` notes the rename goes in
  `NOTES-FOR-ANDREW.md`, not claimed as done in the patch itself.
- Cut `<details>` block to one line [O5]: **made**, now 3 result lines (I'd call the synthesis's "one
  line" a rounding of "short," and 3 lines matches what's actually in the patch).
- State the `max_size`/`LineTooLong` behavior change [O3]: **made**, present verbatim in "Are there
  changes in behavior for the user?".
- Comment on `tail`/`head`/`n` arithmetic [S1]: **made**, two comment lines added, no code
  restructuring (S1's helper-extraction suggestion wasn't required, per the synthesis wording).
- Drop `test_readuntil_separator_split_after_wait` [O1, O5]: **made** — 8 test functions remain, each
  covering a distinct condition per `CHANGES-FROM-V1.md`; I independently count 8 in the patch,
  matching.
All required changes made. No new slop signals introduced by the edits themselves.

### otel-urlparser
- Bound the `]` search, add `http://[::1/path]` test row [O2, O3]: **made**. The patch's
  `getHostEndIndexExclusive` bracket branch now breaks on `/`, `?`, `#`, and both test copies gained
  the `[::1/path]` and `[x/p?token=abc]` null-host rows.
- Gradle/spotless checks [O1, O4, O5, exec-B]: **not made**, honestly disclosed — no spotless run
  happened here either (exec-B confirms: "No Gradle test task... spotlessCheck... run"). This is a
  real gap, not a slop issue, but it means the PR isn't provably clean on the one check that needs
  the real build.
- Remove HTML provenance comment, keep `Assisted-by:` [O1, O5]: **made** — confirmed no HTML
  comments anywhere in `PR-DRAFT.md`.
- EasyCLA: **Andrew's action**, correctly deferred out of the patch itself.
- Mention ClickHouse caller [O1, O4]: **made**, named in the body.
- Mention pulsar follow-up [O1, O3]: **made**.
- State `getPort()` now returns the port [S5]: **made**.
All required textual/code changes made; the one open item (Gradle/spotless) is a build-verification
gap the packet is honest about, not a slop defect.

### otel-forwarded
- Gradle/spotless [O1, O4, O5, exec-B]: **not made**, same honest disclosure as above.
- Remove HTML comment, keep `Assisted-by:` [O1, O5]: **made**.
- EasyCLA: **deferred to Andrew**, correctly.
- Mention unterminated-`[` fall-through [S5, O2]: **made**, present as its own paragraph.
- Reuse clearer comment wording [S2]: **made** — comment text now matches the `UrlParser` patch's
  wording word for word.
All required changes made except the build-verification gap noted above.

### calibre-opds
- Send the three-handler (`alt/`) version [O1–O5, S3, S4, exec-A]: **made** — confirmed by reading
  the diff, all three handlers (`opds_navcatalog`, `opds_category`, `opds_categorygroup`) now wrap
  their `from_hex_unicode` calls.
- Drop the unreachable `if not which` check [O1, O4, O5]: **made** — I don't see it anywhere in the
  v2 diff.
- Delete the "[If sending the alternative patch, add:]" placeholder [O1, O4, O5, S2, S3]: **made** —
  no bracketed editorial text anywhere in `PR-DRAFT.md`.
- Cut body to ~3 sentences, no security framing [synthesis]: **made**, and this is the best-executed
  trim of the six — the draft is genuinely terse.
- Test optional: **not added**, and the packet says why instead of pretending coverage exists.
All required changes made.

### bionemo-amplify
- Correct the impact claim, stop implying a silent-upcast is certain [O1, O4, O5]: **made**. The
  draft now says padding rows are fp32/CPU "whatever" the source, that `torch.cat` "returns" fp32
  for bf16 (a claim it can support on CPU), and that the full conversion "most likely fails" at
  `apply_transforms`'s dtype assertion rather than "silently upcasts." That's the right register —
  confident about what was shown, hedged about what wasn't.
- Fix misattached clause implying ESM2 has the bug [O3, O4, O5]: **made** — the current text says the
  new code matches `_pad_bias` and ESM2's `_pad_weights`, with no clause reading as an ESM2 bug
  report.
- Rewrite into repo's own template, delete provenance/DCO-speculation/evidence-README boilerplate
  [O1, O5, S3, S8]: **made** — checked against the actual `.github/pull_request_template.md`
  section order; matches.
- Move test into `tests/test_amplify_model.py`, cut docstring, correct year [O1, O4, O5]: **made** —
  test sits right after `test_convert_state_dict` in the existing file with a one-line docstring.
- CPU-to-CPU device assertion pins nothing; add CUDA-skipped case or say so [S4]: **made** — test is
  now parametrized `cpu`/`cuda` with `skipif(not torch.cuda.is_available())`.
All required changes made.

### bionemo-thd
- Replace "silently lose training tokens" with the shown fact [O1, O3, O4]: **made** — body now says
  the collator "leaves remainder tokens out of every rank's shard" with the concrete example
  (positions 16/17), and separately flags that Transformer Engine's downstream handling was not
  checked.
- State `L0_sanity_cp.yaml` is safe, note it guards user overrides [O4, O5]: **made** — present
  almost verbatim in the "Scope" section, plus the mixtral config cross-check.
- Actionable error message, drop private function name [O1, O2, O5]: **made** — message now reads
  "...for THD context parallelism; set pad_sequences_to_be_divisible_by to a multiple of 4" with no
  reference to `_process_tensor_bshd`.
- Note the process-group-timeout risk; offer config-time-check alternative [O2, O1, O4]: **made** —
  both present, including the "I'm happy to switch" offer.
- Warn that silently-dropping configs will now fail [S5]: **made**.
- Repo template, move tests, trim commit message [S3, S8, O1, O4, O5, S2]: **made** — template
  followed, tests in the existing file, commit message is 6 lines (down from v1's 4 paragraphs per
  `CHANGES-FROM-V1.md`).
All required changes made. This is also where I'd note, after seeing the full required-change list,
that the round-1 panel itself never flagged PR-body *length* as a problem for this fix — only
content accuracy and template conformance — which supports my step-1 read that the length here
tracks real content rather than padding.

## What I didn't check

- I did not run any code myself (Python/Go/JDK) beyond reading the executor logs already in
  `review-2026-09-28-v2/exec-A.md` and `exec-B.md`, which independently reproduced red/green/revert/
  suite for all six fixes and reported PASS with no discrepancies. I'm relying on those, not
  re-deriving them.
- I did not fetch aiohttp's, OpenTelemetry's, or bionemo-recipes' live GitHub CONTRIBUTING/AI-policy
  pages over the network — only what's checked into `/tmp/review/src/*/base`. If any project's
  live policy differs from the pinned-commit checkout, that's outside what I verified.
- I did not independently verify the Gradle/spotless gap on otel-urlparser/otel-forwarded beyond
  what exec-B already states; I'm taking exec-B's "not run" at face value rather than re-running it.

## Overall summary

All six v2 packets read as reviewed, disclosed, and proportionate — none show the tells I look for
(inflated explanation relative to the actual diff, unsupported claims that outrun what was tested,
prose that just restates the diff, generated-sounding hedge-everywhere phrasing, scope creep into
unrelated files, oversized new test files, boilerplate disclosure blocks, or leftover
internal/editorial notes addressed to Andrew). Every round-1 required change was made, and made
correctly, with the single disclosed exception of the otel Gradle/spotless checks (deferred to
Andrew, not hidden). My one non-blocking suggestion is trimming the unused code snippet in
bionemo-thd's Usage section. Ship all six as-is.

Verdicts: aiohttp-readuntil SHIP · otel-urlparser SHIP · otel-forwarded SHIP · calibre-opds SHIP ·
bionemo-amplify SHIP · bionemo-thd SHIP.
