# S2 — Readability review (tests + prose)

Persona: readability reviewer for tests and prose. I did not run any code; findings are from reading
the patches, the PR drafts, and (where shown in the diff context) the surrounding test files for
existing conventions. I have not read the validator README or executor reports yet — this is the
step-1 blind verdict.

---

### aiohttp-readuntil
Verdict: SHIP
Confidence: high

Findings:
1. `tests/test_streams.py` — nine new test functions (`test_readuntil_separator_split_between_chunks`,
   `..._one_byte_per_chunk`, `..._partial_overlap`, `..._with_false_start`, `..._after_wait`,
   `..._eof`, `test_readuntil_partial_separator_eof`, `..._max_size`, `..._line_too_long`). Names are
   specific and self-describing, each isolates one edge case, and the parametrization style
   (`pytest.mark.parametrize` over separator/split-position pairs) matches the file's existing
   conventions (visible in the surrounding, unmodified test class). This is the strongest test set of
   the nine fixes.
2. `test_readuntil_separator_split_partial_overlap`'s parametrize table (`chunks`, `expected` tuples
   like `((b"xa", b"a", b"b", b"rest"), b"xaab")`) has no `id=` or comment explaining what makes each
   row interesting (self-overlapping separator `aab` split mid-repeat). A reader has to mentally
   simulate the chunking to see why these three rows are non-redundant. Suggest adding
   `pytest.param(..., id="repeat-char-in-separator")`-style ids, or a one-line comment per row.
3. `test_readuntil_separator_split_with_false_start` — good name, but the body (`b"a\r\n\r"` +
   `b"b\r\n\r"` + `b"\n"`) would benefit from a one-line comment stating what the "false start" is
   (a `\r\n\r` prefix of the separator that doesn't complete, appearing twice before the real match).
   As written the reader has to trace the bytes by hand to see the point of the test.
4. Commit message and PR draft: concise, uses aiohttp's own PR template questions verbatim, includes a
   concrete before/after repro in the body, and quotes real red/green pytest output. No jargon, no
   padding. This is a model PR draft for the set.

Overall: ship as-is; the two comment/id suggestions (2, 3) are nice-to-have, not blocking.

---

### chi-gethead
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. `middleware/get_head_test.go`, `TestGetHeadInMountedRouter` — one test function covers two distinct
   scenarios (sub-router's own HEAD handler must win; a parent HEAD route at the same relative path
   must not block the sub-router's GET fallback) back-to-back with two separate `if` blocks and
   `t.Errorf` calls. If the first assertion fails, `t.Errorf` still lets the second one run (good), but
   a failure report just says "TestGetHeadInMountedRouter" — you have to read the error text to know
   which of the two scenarios broke. Splitting into `t.Run("sub-router HEAD handler wins", ...)` and
   `t.Run("parent HEAD route does not block GET fallback", ...)` would make `go test -run` output and
   `-v` failures self-locating, and is idiomatic Go table/subtest style. Not required for correctness,
   but worth doing since this file will be read by a maintainer skimming test output.
2. The two inline comments above each assertion ("The sub-router's own HEAD handler must be used." /
   "A HEAD route on the parent router at the same relative path must not stop the fallback...") are
   clear and match the style of the existing `chi` source comments. Good.
3. Commit message: single-line subject, no body. This matches chi's own terse commit style and the
   "short and to the point" preference reported from other Go maintainers — good fit, nothing to fix.
4. PR draft: short, leads with a code snippet showing the two bugs as bullet points, states the two
   `go test` facts (fails on master, passes with fix) in one line each. This is exactly the length and
   register a maintainer wants. No changes needed.

Overall: the code and prose are ready to submit; the only concrete ask is to split the combined test
into two subtests for isolatable failures.

---

### express-cookie
Verdict: SHIP
Confidence: high

Findings:
1. Test names — `'should not set Max-Age=0 for a positive sub-second maxAge'` and `'should set
   Max-Age=0 for a maxAge of 0'` — read as plain sentences and match the file's existing `it('should
   ...')` convention exactly (e.g., the neighboring `'should not mutate the options object'`). The pair
   also does the right thing for readability: one test pins the fix, the other pins the boundary case
   that must NOT change (`maxAge: 0` still produces `Max-Age=0`), so a reader immediately sees the
   edge being protected.
2. Both tests assert on the full `Set-Cookie` string via one `.expect(/regex/)`, consistent with
   the rest of the file — no new pattern introduced.
3. PR draft: clear "Body" section with a concrete before-example, one line naming the RFC sections
   without over-explaining them, and an explicit statement of what does/doesn't change ("`maxAge: 0`
   and negative values still produce `Max-Age=0`"). The "Template"/checklist section is placed after
   the main body and clearly flags the two open items (issue-first, AI policy) as unchecked TODOs for
   Andrew rather than burying them — good separation between "what a maintainer reads" and "what
   Andrew still needs to do before opening."

Overall: no changes needed.

---

### otel-urlparser
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. `testGetHostAndPortWithIpv6` (both `UrlParserTest` copies) bundles five `getHost` assertions, four
   `getPort` assertions, and one `getPath` assertion into a single test method. This matches the
   existing file's convention (the surrounding, untouched tests in the same class already group
   several `assertThat(...)` calls per method), so it's consistent rather than a regression — but it
   does mean a single failing line reports as "testGetHostAndPortWithIpv6 failed," and you have to
   scroll into the stack trace to see which of the nine assertions broke. Given this method is now the
   canonical IPv6 regression test for two copies of `UrlParser`, splitting it into
   `testGetHostWithIpv6`, `testGetPortWithIpv6`, `testGetPathWithIpv6` (still one line each) would cost
   nothing and make failures self-describing. Optional given it matches house style, but worth
   flagging since this is the fix most likely to be revisited later (there's a documented sibling bug,
   otel-forwarded, in the same area).
2. Inline comments read well: "an IPv6 address is enclosed in square brackets and contains ':'
   characters, so the host ends after the closing ']' (RFC 3986 §3.2.2)" is a complete, well-cited
   sentence, clearer than most of the surrounding code's comments.
3. PR draft: opens with a code block showing the exact broken output (`"["`, `"[2001"`), states the two
   concrete downstream effects as a bullet list, and cross-references the sibling fix (#19540) so a
   maintainer immediately sees this is filling a known gap rather than a novel finding. No jargon
   padding. This is a strong, maintainer-ready draft.

Overall: ship-quality prose; the only ask is splitting the combined test method for isolatable
failures (same class of nit as chi-gethead).

---

### otel-forwarded
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. New code comment `// ipv6 address enclosed in square brackets case` (lower-case, sentence
   fragment, no punctuation) is noticeably lower quality than the sibling otel-urlparser patch's
   comment on the identical logic ("an IPv6 address is enclosed in square brackets and contains ':'
   characters, so the host ends after the closing ']' (RFC 3986 §3.2.2)"). Since both patches land in
   the same review cycle and describe the same mechanism, recommend copying the better-written
   sentence over for consistency — a maintainer reviewing both PRs back to back will notice the
   mismatch in care between two patches from the same author/tool.
2. Test rows added to `ForwardedHostAddressAndPortExtractorTest`'s existing `arguments(...)` arrays
   (e.g. `arguments(singletonList("host=\"[::1]\""), "::1", null)`) follow the file's existing
   parametrized-arguments convention exactly — no new pattern, easy to scan alongside the pre-existing
   rows. Good.
3. `HttpServerAttributesExtractorTest.shouldExtractIpv6ServerAddressAndPortFromHostHeader` — clear,
   descriptive method name, single focused assertion. This is the best-named individual test in the
   whole batch of nine fixes.
4. PR draft: explicitly names the extractor this parallels ("the same `[`…`]` branch used in
   `HostAddressAndPortExtractor` ... and in the `for=` parsing of `HttpServerAddressAndPortExtractor`"),
   which is exactly the context a maintainer needs to sanity-check consistency across the three
   sibling extractors. Concrete before/after example included. Well organized, no padding.

Overall: prose is ready; fix the one sub-par inline comment (finding 1) before submitting.

---

### assertj-percentage
Verdict: FIX-REQUIRED
Confidence: high

Findings:
1. `Percentage_Test.java` — the two new rows (`"3000000000, 3000000000%"`, `"1e20,
   100000000000000000000%"`) were added to the existing `@CsvSource` for
   `toString_should_display_fractional_part_when_present`. That method name is about the *fractional*
   branch of `toString()`; the new rows exercise the *integral* branch for values that overflow `int`
   — they have no fractional part at all. A reader searching for "what covers the overflow bug" would
   never find it under a method named "...fractional_part_when_present." (This mismatch already
   existed for the pre-existing non-fractional row `"10, 10%"`, but the patch makes it worse by adding
   the two most important new cases to the same mislabeled bucket.) Recommend a separate,
   correctly-named method, e.g. `toString_should_not_overflow_for_large_integral_values`, with its own
   `@CsvSource` holding just the two new rows (or three, including `2147483647`/`2147483648` as the
   exact boundary). This is a one-line git diff to fix and meaningfully improves discoverability.
2. Commit message and PR body are otherwise excellent: the body shows the exact broken assertion
   message (`by more than 2147483647% but difference was 99.99999998999999%`), which is the single
   most persuasive line in the whole nine-fix set — it shows a maintainer-facing symptom, not just an
   internal number.
3. The "Before opening (for Andrew)" checklist at the end of the PR draft (CONTRIBUTING 100%-authorship
   conflict, `BigDecimal` vs `(long)` choice, optional issue-first) is clearly separated from the PR
   body proper and reads as an internal TODO list rather than something that would be pasted into the
   real PR. Good practice — worth reusing this "Before opening (for Andrew)" pattern in the other eight
   packets that carry open questions (only assertj and otel-urlparser/forwarded do this consistently
   today).

Overall: the prose is ready to ship. The one concrete change needed is renaming/splitting the test so
its name matches what it tests.

---

### calibre-opds
Verdict: FIX-REQUIRED
Confidence: high

Findings:
1. No test file is included in the patch at all — `git diff --stat` for this packet shows only
   `src/calibre/srv/opds.py | 7 ++++++-`. Every one of the other eight fixes ships at least one
   automated regression test; this is the only one that doesn't, so there is nothing to assess for
   test readability. The PR draft explains why (no full calibre build in the sandbox, verification
   done via "stubbed library/request objects" instead), which is honest and appropriately disclosed —
   but a maintainer who has merged this tool's earlier fixes and already pushed back once ("None of
   these are security issues") is likely to ask "where's the test?" on a bugfix PR. Recommend checking
   whether calibre's `self.test` / content-server test suite (if any) can host a lightweight
   regression test for `/opds/navcatalog` with a malformed id, using the same stub pattern described in
   the PR draft's verification note, and attaching it rather than only describing it in prose.
2. Commit message and PR draft are otherwise the most concise and best-targeted-to-the-maintainer of
   the nine: it correctly identifies calibre's own contribution mechanics (GitHub PRs only, no
   template, no CLA, `git format-patch` accepted), and proactively tells Andrew "do not call it a
   security fix" — directly defusing the exact pushback this maintainer gave on a prior PR. This is
   exemplary use of maintainer context in the prose.
3. One small prose nit: the PR draft's bracketed instruction "[If sending the alternative patch, add:]"
   refers to a variant (fixing `opds_category`/`opds_categorygroup` too) that isn't in this packet's
   actual patch. As written it reads like a leftover editorial note rather than PR body text; make sure
   it's stripped (or replaced with the real content) before this is pasted into an actual PR — as-is a
   maintainer copy-pasting the draft verbatim would ship a confusing bracketed aside.

Overall: prose quality is high, but the missing test is a real gap for a bugfix PR to this project.

---

### bionemo-amplify
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. `test_pad_weights_preserves_dtype_and_device` — good name, single focused behavior, clear docstring
   that states the regression being guarded against and cites the sibling implementation it now
   matches. Assertions (dtype, device, shape, then value-preserving via `assert_close`) are ordered
   sensibly from cheapest/most-specific to most-thorough. This is one of the best-structured
   individual tests in the batch.
2. Commit message body is a dense, multi-clause paragraph ("_pad_weights in state_dict_convert.py
   built its padding rows via a bare torch.zeros(...) with no dtype=/device= kwargs, unlike the
   parallel ESM2 _pad_weights (models/esm2/convert.py), which silently upcasts...") that restates,
   almost verbatim, the PR draft's "Summary" section. `git log --oneline` will show a reasonable
   subject line, but `git log` (full) duplicates the PR body's content in different words. Given
   the reported maintainer pushback elsewhere in this batch of fixes ("This is a very long explanation
   for a simple protocol fix... Short and to the point"), recommend trimming the commit body to
   2–3 short sentences (what broke, what changed, that a test was added) and letting the PR
   description carry the full reachability argument and comparison to the ESM2 sibling.
3. PR draft itself is well organized (Provenance / Summary / Fix / Testing / Notes headers), and the
   "Testing" section is admirably honest about what could *not* be run (`transformer_engine` not
   installable in the sandbox) rather than implying full CI coverage. No changes needed there.

Overall: ship the test as-is; trim the commit message body per finding 2.

---

### bionemo-thd
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. `test_cp_thd_divisibility_guard.py` — the two tests
   (`test_thd_cp_rejects_non_divisible_padded_length`, `..._accepts_divisible_padded_length_no_regression`)
   are a well-chosen pair: one proves the guard fires, the other proves it doesn't fire (and doesn't
   drop tokens) on the case that must keep working. Names are descriptive enough to stand alone in a
   test report. Docstrings explain the regression in plain language and cross-reference the sibling
   BSHD guard's exact error-message wording, which is a nice touch for anyone diffing the two error
   paths later.
2. Same issue as bionemo-amplify but more pronounced: the commit message body is a full paragraph
   restating the reachability argument (the `pad_sequences_to_be_divisible_by` config default vs.
   explicit-override case, with a specific yaml file cited) that is then repeated almost sentence-for-
   sentence in the PR draft's "Summary" section. Between the commit message and the PR body, the same
   argument is made in full twice. Recommend picking one place to carry the detailed reachability
   argument (the PR body, since that's what reviewers actually read and comment on) and cutting the
   commit message to what `git log`/`git blame` readers need: what was broken, what changed, that a
   test exists. This is the most verbose commit message of the nine and the one most likely to draw
   the "long explanation for a simple fix" reaction reported from another maintainer in this batch.
3. PR draft's "Notes for maintainers" section proactively distinguishes this fix from GitHub issue
   #1561 (a related but distinct FLOPs-accounting issue) — this is genuinely useful, maintainer-saving
   content, not padding, and is the single best "notes" section of the nine fixes. Keep it.
4. Minor: the patch touches 10 files (1 source + 1 test + 8 mechanically-propagated copies). The PR
   draft states this clearly up front ("canonical source for 8 byte-identical copies enforced by
   `ci/scripts/check_copied_files.py`"), so a maintainer scanning the diff stat won't be surprised by
   its size. No change needed here — flagging only because it's the kind of thing that would otherwise
   look like scope creep if unexplained, and the draft already explains it.

Overall: the tests are ready to ship; trim the commit message per finding 2.

---

## Summary

Test readability is strong across the board — every fix except calibre-opds ships at least one
regression test, and most follow their project's existing conventions closely (aiohttp and
express-cookie are the standouts; chi-gethead and otel-urlparser/otel-forwarded would benefit from
splitting combined test methods into isolatable subtests/methods, which is a nit, not a blocker).

The one real test-readability gap is assertj-percentage's mis-named test bucket (new integral-overflow
cases filed under a "fractional part" test) — that's a one-line fix and should be made before
submitting.

The one real test-coverage gap is calibre-opds having no automated test at all; the prose explains why,
but I'd expect the maintainer to ask for one anyway.

On prose: PR drafts are uniformly well structured and maintainer-aware (several explicitly route around
known maintainer complaints — calibre's "don't call it a security fix," aiohttp's own template, otel's
cross-references to prior PRs). The recurring prose issue is in the two bionemo commit messages
(amplify, thd), which restate the PR body's reasoning in full inside the commit message itself —
both should be trimmed given the documented maintainer preference elsewhere in this batch for short,
plain commit messages.
