# O1 — Maintainer persona review (2026-09-27)

Reviewer: O1, "the project maintainer." For each fix I took the maintainer's seat for that project: read the base checkout's CONTRIBUTING / PR template / AGENTS / AI policy, looked at recently merged PRs and review comments on GitHub (web_fetch), then asked "would I merge this as written, and if not what would I say?"

What I actually ran (cheap, targeted, in `/tmp/review/work/O1/`, since cleaned up):
- aiohttp: a 20,000-case randomized differential test of `readuntil()` (random separators of 1–4 bytes, random data, random chunk splits) against a reference `bytes.find` splitter. Base: 1,868 mismatches. Fixed: 0.
- chi: the packet's `TestGetHeadInMountedRouter` plus my own two-level-mount test with URL params (`/api` -> `/v1` -> `/{id}`), under `go test -vet=off`. Base fails both, fixed passes both.
- Everything else: source reading only. I did **not** run Gradle, Maven, `npm test`, calibre's test suite, or any bionemo pytest.

Initial verdicts (steps 1 of the blind protocol) are below. Post-README revisions are in a separate section at the end.

---

## Initial verdicts (before reading validator README / exec reports)

### aiohttp-readuntil
Verdict: FIX-REQUIRED (small, process-only edits; the code I'd merge)
Confidence: high
Maintainer context: aiohttp AGENTS.md is explicit: use the template, keep sections to "a couple of sentences", open as `--draft`, and **"One plain line at the bottom: `Drafted with <agent name and version>; reviewed by <human handle>.`"** Recently merged PR #13686 (also a readuntil-adjacent change, "Drafted with Claude Opus 5; reviewed by hxperl.") shows exactly this shape is accepted. Checked upstream master `aiohttp/streams.py` today: bug still present. GitHub search: no open duplicate. #6701/#6810 are indeed different.
Findings:
1. The fix is correct. `aiohttp/streams.py:399-415` (fixed) checks `chunk[1-seplen:] + buffer[0][offset:offset+seplen-1]` for a straddling match before the in-chunk search. My 20k-case differential fuzz found 0 mismatches after the fix (1,868 before). One-byte separators (the `readline()` hot path) skip the new branch (`seplen > 1`), so no cost to the common case.
2. PR-DRAFT.md ends with two provenance lines: "Found by a Quality Playbook run; reproduction and fix by Claude." and "Drafted with Claude Opus 5.5; reviewed by @andrewstellman." AGENTS.md asks for *one* plain line. Fold into the single required line (e.g. "Drafted with Claude Opus 5.5; reviewed by andrewstellman.") and drop the tool plug, or move it inside the `<details>` block.
3. `CHANGES/PRNUMBER.bugfix.rst` must be renamed after the PR number exists (the draft says so; just don't forget, CI's towncrier check will fail otherwise).
4. Tests: 124 added lines / 9 test functions for a 15-line fix. As maintainer I'd accept them, but I'd likely ask to trim: `test_readuntil_separator_split_between_chunks` (parametrized over split point) plus the partial-overlap and after-wait cases carry the weight; the `max_size`/`LineTooLong`/EOF variants are nice-to-have. `test_readuntil_separator_split_after_wait` asserts on the private `stream._waiter` and uses `sleep(0)` x3 loops; that's the flaky-looking one I'd question first.
5. PR body: "Is it a substantial burden" / "changes in behavior" sections are appropriately short. Good. The `<details>` test-output block is placed below the template as AGENTS.md requires.
What I'd say in review: "Thanks, the fix looks right. Please drop to a single disclosure line per AGENTS.md and rename the fragment. Could you cut the tests down a bit? The `_waiter` one reaches into internals."

### chi-gethead
Verdict: SHIP
Confidence: medium-high
Maintainer context: chi's CONTRIBUTING is just "add tests, `go test`, `goimports`." Recently merged PRs (#1185, #1174, #1159, #1148 by/under VojtechVitek) are short-to-medium bodies with a repro and "go test ./... passes"; #1185 was merged with "Looks great! Thank you. LGTM". No AI policy. Relevant history: issue #755 ("Unexpected behavior with Route and middleware.GetHead") was closed with the advice to put `r.Use(middleware.GetHead)` *inside* the `Route()`/sub-router — i.e., exactly the configuration this PR fixes. There are three open duplicate PRs about GetHead + `Allow` headers (#1031, #1095, #1178, #1181), but none address the mount look-ahead; no duplicate of this one.
Findings:
1. Diagnosis is correct: `rctx.Routes` is set only at the top-level `Mux.ServeHTTP` (mux.go:83), while `rctx.RoutePath` is sub-router-relative after `nextRoutePath`; `Mux.Find` (mux.go:382-408) does recurse into mounted subroutes, so looking up the full URL path on the root is the right move.
2. Verified by running: packet test fails on base (`X-Handler "get"` and `405`), passes on fix. My extra nested case (`root.Mount("/api", mid)`, `mid.Mount("/v1", inner)`, `inner.Head("/{id}")`) also fails on base and passes on fix, including URL param propagation.
3. The heuristic `len(rctx.RoutePatterns) > 0` means "a parent router already matched." I checked the `StripSlashes` and `http.StripPrefix`-inside-a-`Handle` cases: behavior after the fix is the same as before (neither was working before), so no regression, but worth one sentence in the PR if asked.
4. Optional polish: add "See also #755" to the PR body — it shows this is the officially recommended configuration, which makes the maintainer's decision easy.
5. Commit subject has no body; fine for chi. PR footnote disclosure is proportionate.
What I'd say: "LGTM, thanks."

### express-cookie
Verdict: REJECT (as a PR). At most, open an issue first and let maintainers decide.
Confidence: medium
Maintainer context: expressjs CONTRIBUTING step 1 is "Create an issue for the bug you want to fix." In closed PR #7287 (a `res.cookie` maxAge edge-case fix for Infinity/NaN), maintainer bjohansebas replied: "if we were to support this, I think it would make more sense in the `cookie` package than in Express itself. Please open an issue first so we can discuss it." This PR is the same genre and would get the same reply.
Findings:
1. `lib/response.js:769-774` (fixed) special-cases `0 < maxAge < 1000` to `Max-Age=1`. That is a behavior choice (round-up only at the zero boundary), not an obvious bug fix. A maintainer will ask "why not `Math.ceil` everywhere, or `Math.round`?" and "why is Express, not `cookie`, the place for this?" The PR doesn't answer either.
2. The PR claim "Max-Age=0 with a future Expires" is imprecise: `Expires` is serialized as an HTTP-date with 1-second granularity, so `Date.now()+500` truncates to the current or next second. After the fix the two attributes disagree in the other direction (`Max-Age=1` vs an `Expires` that may equal "now"). The PR should acknowledge this or not claim consistency.
3. Real-world value is low: a sub-second cookie lifetime is essentially never intentional. The realistic trigger is a user who thinks `maxAge` is in seconds (issue #5234 "Cookie maxAge option should be seconds not milliseconds" shows this confusion exists), and for them `Max-Age=1` is just as broken as `Max-Age=0`.
4. The floor has been there since 4.x (the `cookie` module floored before Express 5 did it inline). Long-standing, unreported behavior.
5. No issue exists; the draft itself leaves "Issue created first" unchecked.
What I'd say: "Please open an issue first so we can discuss it. I'm not sure sub-second maxAge is something we want to special-case here."
Recommendation: don't spend a PR on this. If Andrew wants to pursue it, file a short issue asking whether sub-second `maxAge` should round up, with the 3-line repro, and stop there.

### otel-urlparser
Verdict: FIX-REQUIRED
Confidence: medium-high (code); the blockers are process
Maintainer context: OTel Java instrumentation CONTRIBUTING: "Pull requests for bug fixes are always welcome!" Changelog is generated; no entry needed for bug fixes. OTel GenAI policy recommends `Assisted-by:` trailer — the patch has it. Maintainers are actively merging IPv6 normalization work (#19540 "Handle IPv6 addresses in HTTP Host headers", merged 2026-08-19; #19366, #20015, #20016). Upstream main still has the bug; no open duplicate found.
Findings:
1. The change is correct and matches house style: `getHostEndIndexExclusive` ends the host at `]`, `getHost` strips brackets, unterminated `[` → no host. Same result shape as `HostAddressAndPortExtractor` (#19540).
2. **Blocking:** the draft's own HTML comment says tests ran in a "standalone javac + JUnit harness, not Gradle." Must run `./gradlew :instrumentation-api-incubator:test :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent-unit-tests:test spotlessCheck` before opening. A maintainer will not re-run your build for you; a red CI on first push costs credibility for an AI-assisted PR.
3. Missing impact: `instrumentation/clickhouse/clickhouse-client-v2-0.8/.../ClickHouseClientV2Singletons.java:152` also calls incubator `UrlParser.getHost/getPort` on configured endpoints (`CurrentServerInfo`), so single-IPv6-endpoint ClickHouse clients also get `server.address = "["` today. Mention it (one line); consider a test there, since #20008/#20011 recently touched that code and the reviewer will know it.
4. Scope note: `instrumentation/pulsar/pulsar-2.8/.../UrlParser.java` has the same first-colon split and is not touched. Fine to leave out, but say so or the reviewer will ask.
5. EasyCLA must be signed before the PR can merge (not checked by me).
6. Remove the provenance HTML comment block from the body before opening (it contains instructions to Andrew). Keep the one disclosure sentence + the `Assisted-by:` trailer.
What I'd say (laurit/trask style): "Thanks. Could you also check the ClickHouse endpoint path, which uses the same parser? Otherwise looks good once CI is green."

### otel-forwarded
Verdict: FIX-REQUIRED
Confidence: medium-high (code); the blockers are process
Maintainer context: as above. This is a direct follow-up to issue #15158 (raised by maintainer laurit: "could the host header contain an ipv6 address?") and #19540, which fixed only the sibling `HostAddressAndPortExtractor`. That history makes this an easy yes for a maintainer. Upstream main (fetched today) still splits at the first `:`; no open duplicate.
Findings:
1. Code is correct and minimal: new `[`…`]` branch in `extractHost` (`ForwardedHostAddressAndPortExtractor.java:87-99` fixed), reusing `HeaderParsingHelper.notFound`/`setPort`, placed after quote-stripping so `Forwarded: host="[::1]:42"` works. Unterminated `[` → `false`, consistent with an unterminated quote.
2. Tests are the right style (new `arguments(...)` rows in the existing parameterized tables plus one attribute-level test).
3. **Blocking:** same as otel-urlparser: not run under Gradle. Run `./gradlew :instrumentation-api:check` (includes spotless) before opening.
4. Reviewer may ask why the bracket parsing is now in three places (`HostAddressAndPortExtractor`, `HttpServerAddressAndPortExtractor` `for=` parsing, and here). Be ready to say "kept it local to match the existing pattern; happy to extract a helper."
5. Remove the provenance HTML comment; keep `Assisted-by:`. EasyCLA required (unchecked).
What I'd say: "Nice follow-up to #19540. LGTM once CI passes."

### assertj-percentage
Verdict: FIX-REQUIRED (blocking: legal/authorship). If that can't be resolved, REJECT.
Confidence: medium
Maintainer context: assertj CONTRIBUTING "Legal Disclaimer": "You will only submit contributions where you have authored 100% of the content." The PR template's last checkbox is "PR meets the contributing guidelines", which the draft ticks, while the same body says "Reproduction, the test, and the fix were done by Claude." A maintainer reading both lines sees a direct contradiction in the PR itself. I found assertj PRs with "Written with AI assistance (Claude)" footers (e.g. #4321) but no maintainer ruling on them in what I fetched, so I can't say how scordio/joel-costigliola would rule.
Findings:
1. The bug is real (`Percentage.java:62`, `(int) value` saturates) and the fix is correct: `new BigDecimal(value).toPlainString()` is exact for integral doubles and locale-independent; `Infinity` can't reach that branch (`Infinity % 1` is NaN), and NaN is rejected by `withPercentage`.
2. **Blocking:** resolve the Legal Disclaimer conflict before opening: either Andrew writes the (two-line) change himself and discloses assistance only for the diagnosis, or he asks the maintainers first (issue/discussion) whether AI-assisted contributions are acceptable under that clause. Submitting as drafted invites a close on policy grounds regardless of the code.
3. Value is marginal: a `Percentage` above 2,147,483,647% only appears in contrived tests. A maintainer may still take it because it's two lines, but it won't be a priority.
4. Minor: the new line is 114 characters; within assertj's Eclipse formatter `lineSplit` of 130, so spotless should be fine (PR claims it ran clean; I did not verify).
5. Minor: rows added to `toString_should_display_fractional_part_when_present`, whose name is about fractional parts. The existing table already mixes integral rows (`10`, `10.0`), so this matches house style; acceptable.
What I'd say: "Thanks. Before we look at the code: our contributing guide asks contributors to submit only content they authored. Can you clarify how this was produced?"

### calibre-opds
Verdict: FIX-REQUIRED
Confidence: high
Maintainer context: calibre takes GitHub PRs with very short bodies; merged examples this year (#3143, #3145, #3146, #3155, #3168) are 1–4 sentences plus a one-line "Tested with: ...". Kovid merges Copilot-authored PRs too (#3187, #3192), so AI provenance is not a blocker; framing is ("None of these are security issues").
Findings:
1. The fix is correct for `opds_navcatalog` (`src/calibre/srv/opds.py:660-669` fixed): `binascii.Error`, `UnicodeDecodeError`, and non-ASCII `UnicodeEncodeError` are all `ValueError` subclasses, so `except ValueError` covers every `from_hex_unicode` failure; the empty-id check covers `which[0]` IndexError.
2. **Incomplete as submitted:** `opds_category` (opds.py:687) and `opds_categorygroup` (opds.py:739, 745) decode their ids with `from_hex_unicode` the same way and 500 on the same input. The draft even has a placeholder "[If sending the alternative patch, add:] ...". Send the three-handler version as the only patch. A maintainer who sees one of three identical sites fixed will just fix the other two himself and may not bother merging.
3. Remove the bracketed placeholder line from the PR body.
4. Cut the body to three sentences: what 500s, what now 404s, "Tested with stubbed handlers under Python 3.14; ruff clean." The sentence about ajax.py/`reader_background` precedent is fine to keep; the Quality Playbook sentence can shrink to "Found with Claude-assisted review."
5. No test added; calibre doesn't require one for this, and there's no existing OPDS-malformed-id test to extend. Acceptable.
What I'd say (Kovid): merge silently, or "Fixed the other two as well" in a follow-up commit.

### bionemo-amplify
Verdict: FIX-REQUIRED
Confidence: medium
Maintainer context: bionemo-recipes is heavily AI-maintained (recent merges #1748, #1750, #1753 are Devin PRs; #1746 from a service account). Merged PRs follow the `.github/pull_request_template.md` sections (Description / Usage / Type of changes / CI Pipeline Configuration / Pre-submit Checklist) and are candid when local testing wasn't possible ("not possible: transformer_engine not installable ... Relying on CI"). AGENTS.md: keep changes scoped, add focused tests, follow nearest-model patterns.
Findings:
1. The code change is right and is exactly the ESM2 sibling (`models/esm2/convert.py:238-246`). One-line fix a maintainer will want.
2. **The impact statement is inaccurate.** `convert_amplify_hf_to_te` builds the target with `dtype=te_config.dtype` (`state_dict_convert.py:47-49`), and `apply_transforms` then **asserts** every converted parameter keeps its original dtype (`models/amplify/src/amplify/state.py`, the `target_orig_dtypes` / "dtype mismatch for key" assertion near the end of `apply_transforms`). So for a bf16 source the public conversion most likely fails loudly with an AssertionError rather than "silently upcasts." `_pad_weights` alone upcasts; the end-to-end path does not do so silently. I did not run it (no TE here), so reword to "converting a bf16 or CUDA-resident checkpoint fails (dtype assertion in `apply_transforms`, or device mismatch in `torch.cat`)" only after checking, or state only the function-level fact.
3. Use the repo's PR template. The draft's "Provenance / Summary / Fix / Testing / Notes for maintainers" layout doesn't match what gets merged here. Put the honest testing note in the Pre-submit Checklist as #1748 did.
4. Test placement: a new file `models/amplify/tests/test_pad_weights_dtype_device.py` for one 10-line test. Maintainers here would more likely want it next to `test_convert_state_dict` in `tests/test_amplify_model.py`. Also the docstring is 8 lines explaining history; trim to one line.
5. New file header says `Copyright (c) 2025`; the repo's `license_check.py` uses the current year for new files. Use 2026 (cosmetic; the regex accepts any year).
6. Drop the "Notes for maintainers" DCO paragraph; just add `Signed-off-by:` (costless, and the service-account PR #1746 does it).
What I'd say: "Thanks, good catch. Could you move the test into test_amplify_model.py and fill out the template? Also I think this raises in apply_transforms rather than silently upcasting; can you double check the description?"

### bionemo-thd
Verdict: FIX-REQUIRED
Confidence: medium-low (on the impact claim); medium (that a guard is welcome)
Maintainer context: same repo as above. Copy-file policy (AGENTS.md "Copied files") is followed correctly: source edit in `models/esm2/collator.py`, 8 destinations regenerated with `check_copied_files.py --fix`.
Findings:
1. The guard itself is reasonable and cheap: `seq_lengths % (2*cp_world_size)` check before the floor division (`models/esm2/collator.py:976-985` fixed). CPU tensors in the collator, so no GPU sync concern.
2. **The "silent data loss" claim is unproven end-to-end.** `DataCollatorForContextParallel.__call__` (collator.py:415-440) passes the *unsplit* `cu_seq_lens_q_padded` alongside the sharded `input_ids`; with a non-divisible length the per-rank token count won't match `cu_seq_lens_q_padded[-1] / cp`, and TE's THD context-parallel attention very likely errors on that mismatch downstream. If so, today's behavior is a confusing late crash, not silent token loss. The harness only exercised the split function. Reword ("fails late with a confusing TE error, or drops tokens if nothing downstream checks") unless verified on a GPU box. A maintainer who knows TE will catch an overclaim immediately.
3. Reachability is thin: the only config that sets `pad_sequences_to_be_divisible_by` explicitly with CP (`L0_sanity_cp.yaml`: `cp_size: 2`, value `16`) is safe. Say so honestly; the guard is defensive.
4. Error message: "matching the guard already enforced by the BSHD branch (_process_tensor_bshd)" names a private function in a user-facing error. Replace with actionable advice: "set `pad_sequences_to_be_divisible_by` to a multiple of 2 * cp_size."
5. A maintainer might prefer the check at configuration time (e.g. where `pad_sequences_to_be_divisible_by` is chosen in the CP dataloader factory, `recipes/esm2_native_te/dataset.py:255-258`) so it fails at startup instead of on the first batch. Worth offering as an alternative in the PR.
6. New test file for two tests; existing `models/esm2/tests/test_collator_context_parallel.py` already exercises `_split_batch_by_cp_rank` with `cp_world_size=2`; put them there. The pytest tests were never run (TE/nvtx not installable); say so in the checklist as #1748 does, not "should run cleanly."
7. Use the PR template; add `Signed-off-by:`; drop the DCO speculation paragraph.
What I'd say: "Makes sense as a guard. Can you make the error message tell users what to change, and move the tests into test_collator_context_parallel.py? I don't think this is silent today; TE should blow up on the cu_seqlens mismatch — did you see it actually train?"

---

## Initial overall summary

- Would merge as written: **chi-gethead**.
- Would merge after small process edits: **aiohttp-readuntil** (single disclosure line, fragment rename, trim tests), **otel-urlparser** and **otel-forwarded** (run Gradle/spotless first; mention ClickHouse for the UrlParser one), **calibre-opds** (fix all three handlers in one patch, shorten body).
- Need the story corrected before sending: **bionemo-amplify** (loud assertion, not silent upcast; template; test placement), **bionemo-thd** (unverified "silent" claim; actionable error message; template).
- Blocked on policy: **assertj-percentage** (the 100%-authored clause contradicts the draft's own disclosure).
- Don't send as a PR: **express-cookie** (design choice, low value, maintainers require an issue first and have already deflected this genre to the `cookie` package).

Cross-cutting maintainer observation: the drafts that match each project's house format (aiohttp template + one-line disclosure; chi short body; calibre three sentences) read like normal contributions. The ones with "Provenance (please keep this section)" headers and "Notes for maintainers" DCO speculation (both bionemo drafts) read like tool output. Match the house format and let the one-line disclosure do the disclosing.

---

## Revisions after reading validator READMEs and exec-A.md / exec-B.md (step 2)

The verdicts above were written before I read these. Nothing below overwrites them.

- **aiohttp-readuntil:** no change. exec-A's real pytest re-run (red 16 fail, green 43/43, revert identical, suite 136 -> 162) matches my fuzz result. The README confirms no in-tree caller uses a multi-byte separator (`multipart.py` uses one-byte `readline()`), so the PR's low-key "correctness bug" framing is right; keep it that way. Verdict stays FIX-REQUIRED for the process-only edits (single disclosure line, fragment rename, optional test trim).
- **chi-gethead:** no change, SHIP. exec-A reports `go test ./...` and `go test -race ./middleware/...` are clean on base and fixed. The README's own open question (the `RoutePatterns` heuristic is indirect; the "real" fix is exposing the sub-router on the context, #623) is the one thing a chi maintainer might raise. It's a reason to add one sentence to the PR, not a reason to hold it.
- **express-cookie:** no change, REJECT as a PR. The validator README's own "Open questions" section reaches the same place I did: "A maintainer could fairly reply 'cookie lifetimes are whole seconds; round your value'", no issue exists as CONTRIBUTING requires, and the OpenJS AI Coding Assistants Policy was never read. exec-A confirms the test mechanics are fine (1261 -> 1263 passing). The mechanics were never the problem.
- **otel-urlparser:** no change, FIX-REQUIRED. exec-B confirms red/green/revert with the javac+JUnit harness and states that spotless, checkstyle, errorprone, nullaway, and the Gradle test task were **not run**. That is exactly the blocking item. The README also names the ClickHouse `CurrentServerInfo.of` call site, "not traced further". Mention it in the PR.
- **otel-forwarded:** no change, FIX-REQUIRED for the same Gradle/spotless reason. exec-B's diff-verified identical red/revert failure set (23 cases) is strong evidence the code is right.
- **assertj-percentage:** no change, FIX-REQUIRED on the legal clause. exec-B ran the real Maven build (13/13, and 70/70 across the four `withPercentage` test classes) and confirmed `spotless:check`, so the code is ready. The README hands the legal decision to Andrew. As maintainer I'd want it settled before the PR, not in review.
- **calibre-opds:** refined, still FIX-REQUIRED. The README corrects something I got wrong. The empty-id `IndexError` is **not reachable over HTTP**, because `parse_uri` drops empty path segments, so `/opds/navcatalog/` never reaches the handler. My initial finding 1 said the empty check "covers `which[0]` IndexError". That is true only for a direct call. So:
  (a) drop the `if not which: raise HTTPNotFound` line (dead code on the HTTP path; Kovid will ask why it's there), and
  (b) send the README's `alt/` patch, which wraps all three handlers' decodes. exec-A independently confirmed that `opds_category`/`opds_categorygroup` still raise unhandled `binascii.Error` on the primary-patched tree.
  The README also says calibre's own srv tests skip OPDS on purpose ("too painful"), which confirms that shipping with no test is acceptable here.
- **bionemo-amplify:** no change, FIX-REQUIRED. Neither the README nor exec-A looked at `apply_transforms`' dtype-preservation assertion (`models/amplify/src/amplify/state.py`, near the end of `apply_transforms`). Both verified only that `_pad_weights` itself returns fp32, which is true. They did not verify the "silently upcasts" claim for the public `convert_amplify_hf_to_te` path, and I still think that path fails loudly. That remains unverified by anyone (no TE available). The PR wording must not claim "silent" at the API level without a GPU run. The README's own point that the test fixtures load in bf16 (`tests/conftest.py:40`) makes the reachability case stronger, and that's a better lead for the PR description.
- **bionemo-thd:** no change, FIX-REQUIRED. The README and exec-A both show token loss **inside `_split_batch_by_cp_rank`** (tokens 16 and 17 dropped). Neither traced what `DataCollatorForContextParallel` and TE do next with the unsplit `cu_seq_lens_q_padded`, so "silent, permanent data loss (not a crash, not a warning)" is still a claim about one function, stated as a claim about training. exec-A's note that the `recipes/*` copies were not executed doesn't worry me: `check_copied_files.py` enforces byte identity and CI will run it.

### Final one-line verdicts (after revisions)
| ID | Verdict |
|---|---|
| aiohttp-readuntil | FIX-REQUIRED (process only: one disclosure line, rename fragment, consider trimming tests); code is merge-ready |
| chi-gethead | SHIP |
| express-cookie | REJECT as a PR; at most file an issue asking whether sub-second maxAge should round up |
| otel-urlparser | FIX-REQUIRED: run Gradle + spotless, mention the ClickHouse call site, strip the HTML provenance comment, EasyCLA |
| otel-forwarded | FIX-REQUIRED: run Gradle + spotless, strip the HTML provenance comment, EasyCLA |
| assertj-percentage | FIX-REQUIRED: resolve the "100% authored" Legal Disclaimer conflict first (otherwise REJECT) |
| calibre-opds | FIX-REQUIRED: send the three-handler `alt/` patch, drop the unreachable `if not which` line, cut the body to ~3 sentences |
| bionemo-amplify | FIX-REQUIRED: correct "silently upcasts" (the public API likely asserts), use the PR template, move the test into test_amplify_model.py, 2026 header, Signed-off-by |
| bionemo-thd | FIX-REQUIRED: don't claim "silent" end-to-end without a GPU run, make the error message actionable (no private function name), use the PR template, co-locate the tests, Signed-off-by |

Checked vs. not checked, for the record: I ran the aiohttp fuzz and the chi tests myself. I read, but did not run, the otel, assertj, calibre, express and bionemo code. I did not run Gradle, Maven, npm, or any bionemo/calibre test. I did not verify EasyCLA status, the OpenJS AI policy text, or whether NVIDIA requires DCO for external contributors.
