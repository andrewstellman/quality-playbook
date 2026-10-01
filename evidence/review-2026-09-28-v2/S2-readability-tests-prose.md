# S2 — readability review (tests and prose), round 2

Persona: readability of added tests (names, structure, parametrization, obvious intent, match
with the existing test file's conventions) and of the commit message / PR description (clear,
plain, concise, easy for a busy maintainer to scan, no padding).

Scope note: I did not evaluate correctness of the fixes themselves, only whether the tests and
prose communicate clearly and match house style. Where a readability issue also has a
correctness angle (e.g. assertion ordering hiding failures) I say so but defer the correctness
verdict to other reviewers.

---

### aiohttp-readuntil
Verdict: SHIP
Confidence: high

Findings:
1. Test names are systematic and descriptive: `test_readuntil_separator_split_between_chunks`,
   `_one_byte_per_chunk`, `_partial_overlap`, `_with_false_start`, `_split_eof`,
   `_split_max_size`, `_split_line_too_long`, plus `test_readuntil_partial_separator_eof`. Each
   name states the scenario, matching the file's existing naming (`test_readuntil_exception`,
   `test_readuntil_limit_*`).
2. Minor inconsistency: `test_readuntil_partial_separator_eof` swaps word order relative to its
   neighbor `test_readuntil_separator_split_eof` — the rest of the group uses
   `..._separator_split_<condition>`, this one uses `..._partial_separator_eof`. Purely cosmetic;
   rename to `test_readuntil_separator_split_partial_eof` for a scannable, alphabetically-grouped
   block. Not blocking.
3. Parametrization matches the file's own idiom (`@pytest.mark.parametrize(("separator", "split"), [...])`
   with a list comprehension generating the cross product) — this is the same shape used
   elsewhere in `test_streams.py` (e.g. `test_readuntil_limit_maxsize`). No new pattern introduced.
4. No docstrings on the new tests, but that matches the surrounding file: none of the existing
   `readuntil`/`readline` tests in this class have docstrings either — names carry the intent
   instead. Consistent.
5. Commit message: one-line subject + two-sentence body ("readuntil() searched each buffered
   chunk separately... Also search the last len(separator) - 1 bytes..."). Clear, plain, no
   padding. Good example of the terse form the workspace's maintainer-tone guidance (and the
   NVMe maintainer's "short and to the point" complaint cited in the brief) is asking for.
6. PR description: follows aiohttp's own template exactly (What/Behavior/Burden/Related
   issue/Checklist). The `<details>` test-output block is now three lines, not the old 16-file
   dump — easy to skim. One line answers "is this a burden" and one line states the sole
   visible behavior change (max_size + LineTooLong). This is close to ideal for a busy
   maintainer.

Round-1 required changes: made / not made / made wrongly, item by item:
1. Single AGENTS.md-form disclosure line — made (`Drafted with Claude Opus 5.5; reviewed by andrewstellman.`).
2. Keep `CHANGES/PRNUMBER.bugfix.rst`, defer rename — made (unchanged; rename left to NOTES-FOR-ANDREW.md, correctly not in the PR body).
3. Cut `<details>` block to short form — made (three-line summary, no 16-file dump, no command lines).
4. State the `max_size`/`LineTooLong` behavior change — made, worded plainly under "Are there changes in behavior for the user?".
5. Comment on `tail`/`head`/`n` arithmetic — made (two comment lines added; reads clearly, explains why the slice lengths guarantee a cross-boundary match).
6. Drop `test_readuntil_separator_split_after_wait` — made (CHANGES-FROM-V1.md and the patch both confirm; 8 test functions remain, not 9).

No new readability regressions introduced by the v2 edits.

---

### otel-urlparser
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. `UrlParserTest.java:249` (new `testGetHostAndPortWithIpv6`) combines `getHost`, `getPort`,
   *and* `getPath` assertions in a single test method. This breaks the file's own, very
   consistently applied convention: every other test in this class is scoped to exactly one
   function under test, with one scenario axis per method name — `testGetHost`,
   `testGetHostWithPort`, `testGetHostWithNoAuthority`, `testGetHostWithNoScheme`, then the same
   four for `testGetPort*`, then the same four for `testGetPath*` (12 methods total, verified by
   listing every `@Test` in the base file — no exceptions). The new combined test doesn't match
   that shape and reads as a grab-bag rather than "the getHost tests," "the getPort tests," etc.
2. This isn't just a naming nit: round-2 executor B independently ran the malformed-URL rows in
   isolation and found the combined-assertion-chain has a real downside — `assertThat` is not a
   soft assertion, so a failure on an early line (say, one of the `getHost` assertions) would
   abort the method before the `getPort`/`getPath` assertions further down ever run
   (`exec-B.md`, "Malformed-URL rows, checked directly" section). A future regression in
   `getPort` alone could go unnoticed if an earlier `getHost` line in the same method already
   fails and masks it, or — more realistically — a maintainer reading a red run sees one
   `AssertionError` and has no way to tell from the test report whether the other two functions
   are also broken.
3. Round-1's synthesis item said this test "matches the file's existing style" and only listed
   the split as S2's *optional* suggestion, not required. Having now listed every `@Test` in the
   base file myself, I don't think that's accurate — the file has no precedent for a test that
   spans more than one function under test. I'm flagging this as a correction to the round-1
   record, not just a restated preference.
4. The fix: split into `testGetHostWithIpv6`, `testGetPortWithIpv6` (and either drop the single
   `getPath` line or fold it into whichever of the two already covers a query string, since no
   `testGetPathWithIpv6` sibling exists). This is a 5-minute mechanical split, keeps every
   existing assertion, and restores both the file's convention and clean failure isolation.
5. The reactor-netty copy (`instrumentation/reactor/.../UrlParserTest.java`) has the identical
   issue for the identical reason — its base file has the same one-method-per-function shape
   (verified: `testGetHost`, `testGetHostWithPort`, etc., no `testGetPort*`/`testGetPath*` shown
   in this stripped copy, but the pattern present is consistent, and `getPort` calls are mixed in
   here too). Same fix applies to both copies.
6. Everything else about the tests is good: names, use of `[::1]`/`[2001:db8::1]` as realistic
   IPv6 literals, and the negative cases (`https://[::1`, `http://[::1/path]`,
   `http://[x/p?token=abc]`) are exactly the boundary cases a reader would want to see spelled
   out.
7. PR description: well organized with headers and a bulleted "Callers affected" list, each
   named with the exact class. The code block showing before/after return values
   (`UrlParser.getHost("http://[::1]:8080/") -> "["`) is a good, concrete opening that lets a
   maintainer see the bug in three lines before reading any prose. This is the strongest-written
   PR body of the six.
8. Minor: the PR body is on the long side for the size of the change (roughly 25 lines of prose
   for a ~20-line fix), but every paragraph earns its place (affected callers, the RFC citation,
   the pulsar follow-up note, what changed for `getPort`) — I would not cut anything here. Compare
   to bionemo-thd below, which has padding this one doesn't.

Round-1 required changes: made / not made / made wrongly, item by item:
1. Bound the `]` search, add `http://[::1/path]` test row — made (row added to `testGetHostAndPortWithIpv6` in both copies; see the readability caveat above about where it landed).
2. Gradle/spotless — not made (explicitly deferred to Andrew in CHANGES-FROM-V1.md and NOTES-FOR-ANDREW.md; correctly disclosed, not silently skipped).
3. Remove HTML provenance comment — made (none present in PR-DRAFT.md).
4. EasyCLA — Andrew's action, correctly deferred, not a prose defect.
5. Mention ClickHouse caller — made ("Callers affected" bullet names `ClickHouseClientV2Singletons`).
6. Mention pulsar `UrlParser` as follow-up — made (explicit paragraph).
7. State `getPort()` now returns the port instead of null — made (explicit sentence: "`getPort` now returns the port (8080 above) instead of null").
8. S2's optional split into separate test methods — not made, and after re-reading the base file myself I now think this should be required rather than optional (see findings above).

---

### otel-forwarded
Verdict: SHIP
Confidence: high

Findings:
1. New rows in `ForwardedHostAddressAndPortExtractorTest`'s `arguments()` tables read cleanly
   next to the existing ones — same `arguments(list, expectedHost, expectedPort)` shape, no new
   helper introduced, and they're grouped together (all four IPv6 rows adjacent), which is easy
   to scan. No combined-test problem here: unlike `UrlParserTest`, this file's convention is
   already "one parametrized test, many argument rows," so adding rows is the correct and
   idiomatic way to extend it — nothing to fix.
2. `HttpServerAttributesExtractorTest.shouldExtractIpv6ServerAddressAndPortFromHostHeader` is a
   new, separate method rather than a new row in an existing parametrized test, which matches
   how the surrounding tests in that file are written (one `@Test` method per scenario, not
   parametrized) — correct convention match.
3. Commit message: one-line subject, two-sentence body with a concrete before/after
   (`Host: [::1]:8080 gave server.address "[" and no server.port`), `Assisted-by:` trailer. This
   is close to the terse form the aiohttp fix nailed — good.
4. PR description: opens with a one-line summary, then the origin story ("Follow-up to #15158 /
   #19540"), the visible symptom with two concrete examples, then a "Tests:" list naming the exact
   test classes. It's a little denser than aiohttp's (four short paragraphs vs. a template with
   headers) but every sentence carries information; nothing reads as filler.
5. Comment wording change (from the terse original to the fuller explanation matching the
   UrlParser patch) is a real readability improvement — it now explains *why* (`":' characters
   inside the brackets") rather than just labeling the branch "ipv6 address... case".

Round-1 required changes: made / not made / made wrongly, item by item:
1. Run Gradle `:instrumentation-api:check` including spotless — not made, explicitly disclosed as not run in CHANGES-FROM-V1.md (google-java-format dry-run substitute noted as not equivalent). Correctly flagged rather than glossed over.
2. Remove HTML provenance comment, keep `Assisted-by:` trailer — made.
3. EasyCLA — Andrew's action, correctly deferred.
4. Mention the unterminated `[` fall-through behavior change — made (explicit paragraph: "an unterminated `[`... is now treated as malformed... falls through to the next header source").
5. Reuse clearer comment wording from the UrlParser patch — made, with a footnote in CHANGES-FROM-V1.md noting the old wording actually mirrored a comment already in `HttpServerAddressAndPortExtractor.java:91`, so a maintainer might still prefer the house phrasing. Worth being aware of but not a defect — it's disclosed.

---

### calibre-opds
Verdict: SHIP
Confidence: medium

Findings:
1. No test accompanies this patch, and the PR description says why in the same sentence as the
   verification claim: "calibre's OPDS handlers have no test coverage
   (`src/calibre/srv/tests/ajax.py:374`)". That citation is checkable and correct — I confirmed
   the comment `# Not going test legacy and opds as they are too painful` is really at that line
   in the base tree. This is the right way to handle "no test" honestly rather than silently.
2. PR description is a single dense paragraph. It's short (one paragraph, under 100 words) which
   fits calibre's maintainer's demonstrated preference against over-explaining ("none of these
   are security issues" — i.e., don't oversell), but cramming "what changed," "why," "who wrote
   it," and "how it was verified" into one run-on sentence with semicolons makes it a harder
   single skim than it needs to be. Suggested rewrite, same content, three sentences:

   > `opds_navcatalog`, `opds_category`, and `opds_categorygroup` all decode their id path
   > segments with `from_hex_unicode`; a non-hex, odd-length, or non-UTF-8 value currently raises
   > `binascii.Error`/`UnicodeDecodeError` instead of the `HTTPNotFound` these handlers already
   > return for every other bad input. This wraps each decode in try/except and returns 404
   > instead; valid ids are unaffected. Found with an automated review tool, patch written with
   > Claude and reviewed by me — verified by exercising the handler code directly with stubbed
   > request/library objects (calibre's OPDS handlers have no test coverage,
   > `src/calibre/srv/tests/ajax.py:374`); malformed ids now 404 in all three handlers, valid ids
   > still reach the feed builders, and `ruff check`/`ruff format --check` pass.

   This is the same information, same length, but three sentence breaks instead of one long
   comma/semicolon chain — easier to scan in the few seconds a maintainer gives a small PR body.
3. Commit message is a single-line subject with no body. That's appropriately terse for a
   one-line-per-handler mechanical fix, and it's unchanged from a version round 1 already
   accepted as fine.
4. `try`/`except ValueError: raise HTTPNotFound('Not found')` is repeated identically three
   times in the diff (once per handler). This is a diff-readability point more than a test/prose
   one, but worth a one-line mention: a reviewer skimming the diff sees the same 4-line block
   three times, which is easy to verify is correct precisely because it's so repetitive and
   uniform — I don't think this needs a shared helper for a 3-call-site patch, but if the
   maintainer asks for one, the readability cost of *not* extracting it is low.

Round-1 required changes: made / not made / made wrongly, item by item:
1. Send the three-handler (`alt/`) version — made (all three handlers patched, confirmed in the diff).
2. Drop `if not which: raise HTTPNotFound` — made (not present in this patch's diff).
3. Delete the "[If sending the alternative patch, add:]" placeholder — made (no bracketed editorial text in PR-DRAFT.md).
4. Cut the body to ~3 sentences, no security framing — partially made: length is right (one paragraph, no security language), but it's one long paragraph rather than three sentences a reader can see as three sentences (see finding 2 above — same content, worse punctuation-driven structure).
5. Test optional — correctly left out, with the "why" cited inline.

---

### bionemo-amplify
Verdict: FIX-REQUIRED
Confidence: high

Findings:
1. Test placement and naming: `test_pad_weights_dtype_device` sits directly after
   `test_convert_state_dict` in `tests/test_amplify_model.py`, matching round 1's required move
   out of a standalone file. The name is clear and specific. Its one-line docstring
   ("`_pad_weights` pads with zeros in the source embedding's dtype and on its device.") is
   actually more documentation than the neighboring `test_convert_state_dict`, which has none —
   so it's not under- or over-documented relative to the file.
2. `@pytest.mark.parametrize("device", ["cpu", pytest.param("cuda", marks=pytest.mark.skipif(...))])`
   is a correct and idiomatic way to make the CUDA half of the test skip cleanly, and it directly
   answers round 1's S4 finding that the old CPU-only version "pinned nothing." Good fix.
3. The PR description repeats a "haven't run / haven't tested / not run" hedge three separate
   times in slightly different words: "I haven't run that case because I don't have a GPU," "I
   haven't run the end-to-end conversion, which needs Transformer Engine and a GPU," and "(I have
   not run this snippet)" attached to the usage example. Each instance is individually honest and
   necessary (this is exactly the kind of unverifiable-claim discipline round 1 asked for), but
   three near-identical disclaimers in a five-paragraph PR reads as repetitive rather than
   careful. Suggest consolidating into one clearly-labeled "Not verified" note near the top (or
   bottom) of the description that lists all three unverified claims together, rather than
   scattering the same caveat through the prose. This would also make it easier for a maintainer
   to see at a glance exactly what has and hasn't been run, instead of having to collect three
   separate parenthetical hedges.
4. The description's second paragraph runs two claims together in one sentence: "For a bf16
   source, `torch.cat` returns an fp32 tensor. For a CUDA source, the CPU padding rows should
   make `torch.cat` fail with a device mismatch." — this is clear, but immediately followed by "I
   haven't run that case because I don't have a GPU" makes it read like a hedge stapled onto a
   claim; the rewritten single "Not verified" section (finding 3) would fix this too by moving
   the hedge out of the middle of the explanation.
5. The reproduction snippet under "Usage" is genuinely useful — a maintainer can paste it — and
   is clearly marked as unrun, which is honest. No change needed there beyond the consolidation
   above.

Round-1 required changes: made / not made / made wrongly, item by item:
1. Correct the "silently upcasts" impact claim, describe only the function-level fact — made. The PR now says "the padding rows are fp32/CPU regardless of the source" and separately, clearly marked as inference from reading `state.py:238-243` rather than observed, that a real bf16 conversion "most likely fails at that assertion."
2. Fix the misattached clause implying ESM2 has the bug — made (commit message and PR both now frame the change as *matching* ESM2's `_pad_weights` and the same file's `_pad_bias`, not fixing a bug in either).
3. Rewrite the PR in the repo's own template — made (Description / Usage / Type of changes / CI Pipeline Configuration / Pre-submit Checklist, matching the template's section names).
4. Move the test into `tests/test_amplify_model.py`, cut the docstring, use 2026 in any new header — made for the move and the docstring cut; no new file, so no header question arises (correctly noted as N/A in CHANGES-FROM-V1.md rather than silently skipped).
5. Address the CPU-to-CPU test pinning nothing — made (see finding 2, `cuda` param added).

---

### bionemo-thd
Verdict: FIX-REQUIRED
Confidence: high

Findings:
1. Test names `test_split_batch_by_cp_rank_thd_non_divisible` and
   `test_split_batch_by_cp_rank_thd_covers_all_tokens` match the file's naming exactly
   (`test_split_batch_by_cp_rank_bshd_single_sequence`, `_bshd_multiple_sequences`, `_bshd_cp4`,
   `_bshd_3d_tensor` are the direct siblings) — good, obvious continuation of an established
   pattern, easy for a maintainer to find by name alone.
2. One-line docstrings ("THD splitting raises when a padded sequence length is not divisible by
   2 * cp_world_size." / "...assigns every token to exactly one CP rank.") are shorter than most
   neighboring docstrings in this file, which mostly open with "Test that ..." and run 2–3 lines
   (e.g. `test_split_batch_by_cp_rank_bshd_single_sequence`'s docstring). This is a minor style
   drift, not a defect — the new docstrings are just as clear, just terser, and terser is
   consistent with round 1's own request to cut the original 8-line docstring. Not worth
   reverting; if anything I'd hold this file's older docstrings to the new, shorter standard
   rather than the other way around.
3. `test_split_batch_by_cp_rank_thd_non_divisible`'s regex assertion
   (`pytest.raises(ValueError, match=r"\[10\] must be divisible by 4")`) pins both the exact
   dropped-length value and the divisor in one line — a reader can see immediately what triggers
   the error without reading the source. Good, specific assertion.
4. The PR description is the longest of the six (roughly 40 lines of prose before the code
   block), organized under a "Scope" bullet list covering five separate points (untested TE
   interaction, which shipped configs are safe, the behavior change, the process-group-timeout
   failure mode, and an alternative design). Each bullet is individually well-written and
   necessary given round 1 asked for most of them, but the cumulative effect is dense — a
   maintainer has to read five bullets before reaching "Tests:". Two concrete suggestions:
   - Move the "Alternative: check ... once where the dataloader is configured" bullet (the last
     one) out of "Scope" and either drop it or fold it into a one-line closing question ("Happy to
     move this to a config-time check instead if you'd rather fail all ranks together at
     startup — let me know.") — right now it reads as a fifth caveat of the same weight as the
     others, when it's actually an open design question for the maintainer, which deserves to
     stand out rather than blend in.
   - The process-group-timeout bullet and the "I haven't run this multi-rank" hedge inside it
     could merge with the TE-interaction bullet's "I haven't run this" hedge (finding 5 in
     bionemo-amplify above shows the same pattern) — two of five bullets each end with a near-
     identical "I haven't run/checked this" disclaimer; consolidating the unverified-claims list
     once, as suggested for bionemo-amplify, would shorten this PR without losing any disclosure.
5. Commit message is now six lines (down from four paragraphs in v1) and reads well: what's
   wrong, what the fix does, and the mechanical note about regenerating copies. Good, proportional
   to a fix this size.
6. The `bad_lengths[:5]` / `more` truncation logic in the shared error message is exercised
   directly by name in the "green" harness log content described in CHANGES-FROM-V1.md, so the
   message's truncated form is at least demonstrated in the ten identical copies, not just
   asserted in prose.

Round-1 required changes: made / not made / made wrongly, item by item:
1. Replace "silently lose training tokens" with the demonstrated fact (drops remainder tokens; TE handling unchecked) — made.
2. State `L0_sanity_cp.yaml` is safe and the guard is for user overrides — made.
3. Make the error message actionable, drop the private function name — made (message now reads "...for THD context parallelism; set pad_sequences_to_be_divisible_by to a multiple of 4", no function name).
4. Note the process-group-timeout failure mode, offer a config-time alternative — made, though see finding 4 above on how it's presented (buried as one of five equally-weighted bullets rather than surfaced as an open question).
5. Warn that a config that silently dropped tokens will now fail — made ("Behaviour change: a config that drops remainder tokens today will now fail with this error...").
6. Repo PR template; move tests into `test_collator_context_parallel.py`; trim commit message — made (template sections present, tests moved and correctly named, commit trimmed to six lines).

---

## Overall summary

Test quality is strong and consistent across all six fixes: names match each file's existing
convention (aiohttp, bionemo-amplify, bionemo-thd all directly extend an established pattern),
and calibre's lack of a test is disclosed rather than hidden. The one real structural test
defect is **otel-urlparser's `testGetHostAndPortWithIpv6`**, which mixes three functions
(`getHost`/`getPort`/`getPath`) in one method against a file that otherwise never does that —
round 1 apparently checked this against the wrong precedent, and executor B's isolated re-run
shows the practical cost (an early assertion failure can mask later ones in the same method).
Split it into `testGetHostWithIpv6` and `testGetPortWithIpv6`.

Prose quality: aiohttp and otel-forwarded are close to ideal — short, concrete, no repeated
hedges. calibre-opds says everything it needs to in too few sentence breaks (a run-on rather than
too long — rewrite suggested above). bionemo-amplify and bionemo-thd both do the right thing by
disclosing every unverified claim, but the discipline of "one hedge per fact" from round 1 has
turned into three-to-five separate "I haven't run this" sentences scattered through each PR;
consolidating each into a single "not verified" list would keep all the same honesty in about a
third of the words.

Not checked: I did not re-run any tests or the harnesses myself — my findings on the otel-urlparser
assertion-ordering issue rely on executor B's independently-run probe (`exec-B.md`), which I read
but did not reproduce. I did independently verify, by listing every `@Test` method, that the base
`UrlParserTest.java` files (both copies) never combine more than one function under test in a
single method — that check I ran myself with `grep` against the files in `/tmp/review/src/otel/base/`.
