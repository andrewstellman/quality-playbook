# S4 — Quality Engineer (test quality) review

Persona: does the new test actually pin the defect (fails if fix reverted, for the right reason);
would it catch plausible future regressions or only this exact input; is it deterministic; what's
untested; what's over-tested. Claims marked **[executed]** were run in `/tmp/review/work/S4/`;
claims marked **[reasoned]** were not run (no interpreter/build available, or explicitly out of
scope per the brief) and are derived from reading the code.

---

### aiohttp-readuntil
Verdict: SHIP
Confidence: high

Findings:
1. **[executed]** Copied `fixed-aiohttp-readuntil` into scratch, ran
   `pytest tests/test_streams.py -k 'readuntil_separator_split or readuntil_partial_separator'`:
   26 passed. Then copied the *same* (fixed) test file onto the *base* `streams.py` (i.e. tests
   only, unpatched production code) and reran: **16 failed, 10 passed** — reproduces the PR
   draft's own reported number exactly (`16 failed, 10 passed` before, `26 passed` after). This is
   as clean a pin as you can ask for: the tests fail specifically on the unpatched code and pass
   once the one-line-ish fix in `streams.py` lands.
2. Coverage is unusually thorough for a one-function fix: separator split at every byte boundary
   (`test_readuntil_separator_split_between_chunks`, parametrized over split point 0..len(sep)),
   one-byte-per-chunk worst case, ambiguous/false-start overlaps (`b"a\r\n\r" + b"b\r\n\r" + b"\nrest"`,
   `aab`-style partial-overlap parametrization), interaction with `feed_eof()` mid-separator
   (`readuntil_separator_split_eof`, `readuntil_partial_separator_eof`), and interaction with
   `max_size`/`LineTooLong` (`readuntil_separator_split_max_size`,
   `readuntil_separator_split_line_too_long` — these specifically guard against a fix that finds
   the separator correctly but breaks the existing size-limit enforcement). `after_wait` tests
   exercise the waiter/re-entry path when data arrives byte-by-byte after the reader is already
   blocked, using `asyncio.sleep(0)` spins — **[reasoned]** this yielding pattern already appears
   at lines 674/676/679/1133/1279 of the base test file, so it's consistent with the codebase's
   existing test idioms, not a novel source of flakiness.
3. Nothing obviously over-tested; each parametrization targets a distinct edge (chunk boundary
   position, separator length, EOF interaction, size-limit interaction) rather than restating the
   same case.
4. Gap (minor): no test with `separator` longer than 5 bytes or with repeating/self-overlapping
   separator content beyond `--xyz`/`\r\n\r\n` (e.g. `b"aaaa"` where a false match could
   self-overlap in more exotic ways) — but the existing `partial_overlap` cases (`aab` with
   overlapping `a`s) already probe exactly this class of bug, so this is a nice-to-have, not a
   hole.

### chi-gethead
Verdict: SHIP
Confidence: high

Findings:
1. **[executed]** Built fixed and base trees under Go 1.25.1 (`GOCACHE`/`TMPDIR` redirected off
   the full `/sessions` mount). `go test ./middleware/ -run TestGetHead -v` on the **fixed** tree:
   both `TestGetHead` and `TestGetHeadInMountedRouter` pass. Copying only the new test file onto
   the **base** `get_head.go`: `TestGetHeadInMountedRouter` fails on both assertions exactly as
   the PR draft describes — `HEAD /api/hi` returns the GET handler's body/header instead of the
   sub-router's HEAD handler, and `HEAD /api/only-get` returns 405 instead of falling back to GET.
   This is a real, direct pin of both symptoms named in the bug report.
2. The test is a single function with two `testRequest` assertions rather than parametrized, but
   that's appropriate here — it needs a full mounted-router topology (`sub := chi.NewRouter()`,
   `r.Mount("/api", sub)`, an `httptest.NewServer`), and both assertions share that fixture, so
   splitting them wouldn't add independent value.
3. Would it catch a regression, or only this exact input? It exercises the two structurally
   distinct failure modes named in the bug (sub-router's own HEAD handler being skipped; parent
   HEAD route at the same relative path blocking GET fallback), not just one specific URL, so a
   plausible variant of the same root cause (RoutePatterns-based lookahead using the wrong path)
   would very likely also be caught. It does not test a *doubly*-mounted router (`r.Mount("/api",
   subOuter)` where `subOuter` itself mounts a `sub2`) — the fix's `RawPath`/`Path` full-request-path
   approach should still work there since `rctx.Routes.Match` recurses, but that nesting depth
   isn't exercised. Low-value gap given the fix's mechanism, not blocking.
4. Deterministic: no timing, no goroutines beyond the httptest server's own request handling.

### express-cookie
Verdict: SHIP
Confidence: high

Findings:
1. **[executed]** Symlinked `node_modules` from an identical `package.json` already present in
   the shared scratch space (`/tmp/express`, verified `diff package.json` empty) into a copy of
   `fixed-express-cookie`. `npx mocha test/res.cookie.js --grep "sub-second|maxAge of 0"`: **2
   passing**. Copied the same test file onto **base** `lib/response.js` (unpatched): the
   sub-second test **fails** with `expected "Set-Cookie" matching /.../Max-Age=1.../, got
   "...Max-Age=0..."` — an exact, message-legible pin of the reported bug. The `maxAge: 0` test
   passes on both base and fixed, correctly acting as a non-regression check rather than a
   defect-pinning one.
2. Two tests, each doing one job: one proves the fix (500ms → Max-Age=1, not 0), one proves the
   fix didn't overreach (maxAge:0 still → Max-Age=0, not 1). That's the right shape — a fix that
   special-cased "the truthy branch" without the `maxAge > 0` guard would flip the second test.
3. Gap: no test for a negative `maxAge` (e.g. `-500`). The PR draft claims "negative values still
   produce Max-Age=0" but that's not quite precise either — **[reasoned]** by the same
   `Math.floor(maxAge/1000)` arithmetic, `maxAge=-500` produces `Math.floor(-0.5) = -1`, not `0`,
   so it never even reaches the new `maxAge > 0 && opts.maxAge === 0` branch and is unaffected by
   this patch either way. Worth a one-line clarifying comment in the PR description rather than a
   new test, since the behavior for negative values is simply unchanged and untouched by this fix.
4. Deterministic, no timing dependency (uses `Date.now()` internally but only regexes the
   `Max-Age=` token, not the `Expires=` value).

### otel-urlparser
Verdict: SHIP
Confidence: high

Findings:
1. **[executed]** The `UrlParser` classes have no framework dependencies beyond
   `javax.annotation.Nullable`, so I compiled the fixed `UrlParser.java`
   (`instrumentation-api-incubator` copy) standalone under JDK 25 with a stub `@Nullable` and ran
   the exact assertions from `testGetHostAndPortWithIpv6` plus two extra edge cases (no trailing
   slash, `getPath` on an unterminated bracket) by hand (no JUnit, plain `assert`-and-print) — all
   12 checks passed. Ran the same harness against the **base** (unpatched) file: `getHost` returns
   `"["` for `https://[::1]:8080/`, `getPort` returns `null`, and `getHost` returns `"[2001"` for
   the `2001:db8::1` case — exactly the three symptoms quoted in the PR draft, reproduced from the
   live base source, not just asserted by the draft.
2. Coverage is good: no-port / trailing-slash / with-port / with-query-string / unterminated
   bracket, plus `getPath` after a bracketed host. The unterminated-bracket case
   (`https://[::1` → `null`) specifically pins the "don't crash or silently truncate on malformed
   input" requirement, which a lazier fix (just search for `]` without checking `indexOf` result)
   would get wrong.
3. Both copies (`instrumentation-api-incubator` and the `reactor-netty-1.0` fork) get identical
   fixes and identical new tests — appropriate, since these are independent classes (not
   DRY-shared code, so each needs its own coverage) rather than copies enforced by a shared-code
   check.
4. Gap (minor, matches otel-forwarded's pattern more thoroughly so worth calling out by
   contrast): no test for a zone-id IPv6 literal (`[fe80::1%eth0]`) — vanishingly rare in HTTP
   client code and not worth blocking on, but if the sibling `ForwardedHostAddressAndPortExtractor`
   fix ever needs it, this one would too.
5. Only the two `UrlParserTest` classes were exercised directly; the `ServicePeerResolverTest` new
   row (`[::1]:8080` → `ipv6PortSvc`) exercises a different class
   (`ServicePeerResolver`/`ServicePeerResolverTest`) that I did not extract and run standalone —
   **[reasoned only]** for that one row, based on reading the diff (it plugs the same fixed
   `UrlParser.getHost`/`getPort` output into an existing, unmodified matcher, so it should follow
   directly from finding #1, but I did not execute it).

### otel-forwarded
Verdict: SHIP
Confidence: high

Findings:
1. **[executed]** `ForwardedHostAddressAndPortExtractor.extractHost` is a private static method;
   built a standalone package with it plus its two real dependencies
   (`HeaderParsingHelper`, `AddressAndPortExtractor`/`AddressPortSink`, both copied verbatim from
   the base tree) and a stub `HttpCommonAttributesGetter`, then invoked `extractHost` via
   reflection (`setAccessible(true)`) with the 6 cases mirrored from the new test rows: plain
   `[::1]`, `[::1]:42`, `[2001:db8::1]:42`, a quoted `Forwarded: host="[::1]:42"` value, a bad-port
   `[::1]:port`, and the unterminated `[::1`. All 6 passed on the **fixed** source. Re-ran against
   the unmodified **base** `ForwardedHostAddressAndPortExtractor.java`: all 6 failed, with
   address `"["` or `"[2001"` and port always `null` — exactly the bug described, including the
   malformed/unterminated case incorrectly returning `"["` instead of `null` on base.
2. This is a strong regression-catching set specifically because it includes the RFC 7239
   required-quoting form (`host="[::1]:42"`) alongside the unquoted `Host:`/`X-Forwarded-Host`
   form — a fix that only patched the unquoted path (e.g. patching `extractHost`'s tail branch but
   not re-testing after the recursive unquote call) would still be caught. The bad-port case
   (`[::1]:port` → address parsed, port silently `null` via the existing `NumberFormatException`
   swallow in `HeaderParsingHelper.setPort`) checks that the new bracket branch composes correctly
   with pre-existing error handling rather than reimplementing it.
3. `HttpServerAttributesExtractorTest.shouldExtractIpv6ServerAddressAndPortFromHostHeader` (the
   attribute-level test) was not independently executed — **[reasoned only]**: it exercises the
   same `extractHost` code path at a higher level (through `HttpServerAttributesExtractor`), so
   given finding #1 it's very likely to pass, but I didn't build the full extractor stack to
   confirm.
4. No test for a `Forwarded` header with a `for=` IPv6 value — PR draft states the `for=` parsing
   already has bracket handling (pre-existing, not part of this fix), so this is correctly out of
   scope rather than a gap.

### assertj-percentage
Verdict: SHIP
Confidence: high

Findings:
1. **[executed]** `Percentage.toString()`'s two branches have no AssertJ dependencies — wrote a
   4-line standalone harness reproducing `noFractionalPart() ? ... : ...` with both the base
   `(int) value` cast and the fixed `new BigDecimal(value).toPlainString()`, run under JDK 25, for
   `{10, 10.0, 0.1, 0.103, 3_000_000_000d, 1e20}`. Base: `2147483647%` for both large values,
   matching the bug report byte-for-byte (including the `2147483647` int-overflow saturation
   value quoted in the draft). Fixed: `3000000000%` and `100000000000000000000%`, matching the two
   new CSV rows added to the parametrized test exactly.
2. The two new rows are appended to an existing `@CsvSource` parametrized test
   (`toString_should_display_fractional_part_when_present`) rather than a new test method — good
   reuse, keeps the assertion logic (`assertThat(new Percentage(value)).hasToString(expected)` or
   equivalent) DRY, and both existing small-value rows (`10`, `0.1`, `0.103`) continue to run
   alongside the new ones, so this can't regress the normal-value path while fixing the
   overflow path.
3. `1e20` is a good choice specifically because it's for beyond `Long.MAX_VALUE`
   (~9.2e18) too, not just `Integer.MAX_VALUE` (~2.1e9) — this rules out a lazier fix that swaps
   `(int)` for `(long)`, which the PR draft explicitly flags as an alternative to reject (would
   print `9223372036854775807%` for `1e20`, still wrong, just with a bigger ceiling). Good defense
   against a plausible "almost-fix."
4. Gap (minor): no test at the exact `Integer.MAX_VALUE` boundary itself (`2147483647.0`, which
   the base code already handles correctly) or `Integer.MAX_VALUE + 1.0` — the jump straight to
   `3e9` skips confirming the fix doesn't change output for values just at/under the old ceiling.
   Given the fix is unconditional (`BigDecimal` used for every integral value, not just large
   ones) and the existing `10`/`10.0` rows already confirm no formatting change for small
   integers, this is very low risk, not a real hole.
5. Process note, not a test-quality finding but relevant to whether this ships: AssertJ's
   `CONTRIBUTING.md` requires contributors to certify they authored 100% of the content, which
   this Claude-authored patch cannot honestly satisfy as-is — that's a submission blocker
   independent of test quality, flagged here per the brief's "maintainer context."

### calibre-opds
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. **No test was added.** The patch is a 7-line diff to `src/calibre/srv/opds.py` with zero test
   changes. The PR draft substitutes "verified before/after... by executing the unmodified handler
   with stubbed library/request objects under Python 3.14" — that verification was not committed
   as a runnable test, so nothing in the repository would catch a future regression of this exact
   bug (e.g. someone "simplifying" the try/except back out during a refactor).
2. **[executed]** Confirmed the exception-typing claim directly: imported the real
   `polyglot.binary.from_hex_unicode` (no calibre GUI/Qt/DB dependencies needed for this one
   function) and called it with `'zz'`, `'ff'`, `'Off'`, `''`, and a valid `'4f31'`. Results:
   `'zz'` → `binascii.Error` ("Non-hexadecimal digit found"), `'ff'` → `UnicodeDecodeError`, `'Off'`
   → `binascii.Error` ("Odd-length string"), all three are subclasses of `ValueError`, so the
   patch's `except ValueError` does catch all three failure modes named in the bug report (not
   just the hex-decode one). `''` decodes successfully to `''` — confirming why the separate
   `if not which: raise HTTPNotFound` guard is needed: without it, `from_hex_unicode('')` would
   succeed and then `which[0]` a few lines later would raise an uncaught `IndexError` (still a
   500, just via a different code path than the one this patch's except-block covers). Both
   guards are necessary and neither is redundant.
3. **[reasoned]** Checked whether the project's own test suite structurally supports testing this:
   `src/calibre/srv/tests/ajax.py` line 374 has a comment "Not going test legacy and opds as they
   are too painful" — so the *absence* of a check-in test is consistent with this module's
   existing (documented) testing philosophy, not a unilateral gap introduced by this patch. That
   softens the finding but doesn't erase it: a narrow, dependency-free unit test of just
   `opds_navcatalog`'s guard logic (calling it directly with a minimal stub `ctx`/`rd`, the same
   technique the PR author already used for manual verification per the draft's "stubbed
   library/request objects") would be cheap, wouldn't need the full content-server/DB stack the
   "too painful" comment is about, and is exactly the kind of test this repo is missing across the
   whole opds.py file, not just this fix.
4. What test is needed, concretely: a unit test (can live outside the existing `srv/tests`
   integration-style suite, or use the same stubbing approach as the PR author's manual repro)
   that calls `opds_navcatalog(ctx, rd, which='zz')` and `which=''` and asserts `HTTPNotFound` is
   raised in both cases, plus one case with a valid hex id (e.g. `'4f31'`) confirming it still
   reaches the feed builder rather than being swallowed by an overly broad except. Given the
   PR draft says the author already built exactly this harness for manual verification, turning it
   into a checked-in test should be low-cost.
5. The fix logic itself, based on my execution of the underlying decode function, is correct and
   matches the stated symptom precisely — this is a test-coverage objection, not a
   correctness objection.

### bionemo-amplify
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. **[reasoned only — no torch in this sandbox]** No PyTorch was available in my scratch
   environment (`python3 -c "import torch"` → `ModuleNotFoundError`), and installing it was not
   attempted given the brief's disk-tightness warning and "cheap, targeted runs only" guidance,
   so I could not execute `_pad_weights` or the new test directly. Verdict is based on code
   reading, consistent with the PR draft's own admission that `transformer_engine` (an
   unconditional transitive import via `amplify/__init__.py` → ... → `amplify/amplify_te.py:29:
   import transformer_engine.pytorch`, which I did confirm by grep) isn't installable in a
   GPU-less sandbox either.
2. The new test (`test_pad_weights_preserves_dtype_and_device`) would fail if the fix were
   reverted, for the right reason: on unpatched code, `torch.zeros(rows, cols)` defaults to
   `dtype=torch.float32`, and `torch.cat` of a `bfloat16` tensor with a `float32` tensor performs
   dtype promotion to `float32` (this is standard PyTorch `cat`/`stack` type-promotion behavior
   since ~1.5, not something I could execute here to double-confirm, so flagging as reasoned) —
   the test's `assert output.dtype == source_embed.dtype` (`bfloat16`) would then fail. That's a
   real pin of the dtype half of the bug.
3. **Gap: the device-mismatch half of the bug is untested.** The PR's own summary says the bug
   "either silently upcasts... to float32, or raises a device-mismatch error... depending on where
   the source tensor lives" — but the new test only constructs a CPU tensor
   (`torch.randn(10, 4, dtype=torch.bfloat16)`, no `device=` argument, so it's CPU by default).
   There's no CUDA-tensor case exercising the "raises a device-mismatch error" branch, and no
   `torch.device` assertion beyond the trivially-true CPU-to-CPU comparison. This is
   understandable given the sandbox has no GPU (same constraint I hit), and would need a
   `@pytest.mark.skipif(not torch.cuda.is_available())`-guarded case in the project's own CI
   rather than something addable here — but as filed, the fix's device= half of the fix is
   asserted by the test in name only (`output.device == source_embed.device` is checking
   `cpu == cpu`, which is true before AND after the fix, since `torch.zeros(...)` on CPU already
   defaults to the CPU device — this assertion does not actually pin the device regression at
   all, only the dtype one).
4. Test otherwise well-targeted and consistent with the existing `MagicMock`-based pattern in
   `test_amplify_model.py::test_convert_state_dict` (confirmed by reading; `ctx_mock =
   MagicMock(); ctx_mock.target.config.padded_vocab_size = 12` mirrors that file's style). Shape
   and content assertions (`output.shape == (12, 4)`, `torch.testing.assert_close(output[:10]...,
   source_embed...)`) are reasonable, not over-specified.
5. What's needed: either (a) add a `@pytest.mark.skipif(not torch.cuda.is_available())`
   CUDA-tensor variant of this test that actually exercises the device branch (padding a CUDA
   source embedding and asserting `output.device.type == "cuda"`, which would raise
   `RuntimeError` pre-fix rather than silently passing), or (b) if CUDA isn't available in this
   project's CI either, say so explicitly in the PR body rather than letting the "asserts
   dtype/device match" test description imply the device claim is verified when it isn't.

### bionemo-thd
Verdict: SHIP
Confidence: high

Findings:
1. **[executed]** Same `nvtx`/`transformer_engine` import-chain problem as bionemo-amplify (grep
   confirms `models/esm2/collator.py` imports both unconditionally), so I could not import the
   real module. Instead wrote a pure-Python (no torch) simulation of the THD sharding math
   (`slice_sizes = seq_len // total_slices`, then for each `cp_rank` union the two zigzag slices
   selected, exactly mirroring `_process_tensor_thd`'s index arithmetic) for the test's own inputs:
   `cu_seqlens_padded=[0,8,18]`, `cp_world_size=2` (so `total_slices=4`, and the second sequence's
   length 10 is not a multiple of 4). Result: tokens **16 and 17 are dropped by every rank** —
   exactly "2 of 10 tokens... dropped" as the PR draft claims, and these are real dropped tokens
   (never selected by rank 0 or rank 1), not a computation artifact. For the "no regression"
   test's divisible case (`[0,8,16]`, lengths 8 and 8), zero tokens dropped across both ranks.
2. This means the new tests pin the defect for the right reason: on unpatched code, no exception
   is raised and `pytest.raises(ValueError, match="must be divisible by")` around the
   non-divisible case would fail with "DID NOT RAISE" — the correct failure mode, not a wrong-error
   false pass.
3. The "no regression" test is well-designed for a sharding bug specifically: it doesn't just
   check "no exception," it unions the flattened output across every `cp_rank` in
   `range(cp_world_size)` and asserts the union equals `set(range(total))` — i.e., every token
   assigned to exactly the ranks it should be, with none dropped and (implicitly, since it's a
   `set`) none silently duplicated across ranks either. That's a stronger check than the PR
   description's "shards with zero tokens dropped" implies — it also incidentally guards against
   overlapping/duplicate assignment, a plausible different bug in the same function.
4. Coverage economy: the new test file was added only to the canonical `models/esm2/` copy, not
   to the other 8 files the patch touches (`llama3`, `mixtral`, `qwen`, and the 5 `recipes/*`
   collators). **[executed]** Verified this is sound rather than a gap: `grep -c "^diff --git"`
   on the patch shows all 9 `collator.py` files get byte-identical hunks (confirmed by comparing
   the diff hunks against each other — `models/llama3/collator.py`, `models/mixtral/collator.py`,
   and `models/qwen/collator.py`'s hunks are textually identical to each other and to the
   canonical one), and `ci/scripts/check_copied_files.py` (read directly) is a real pre-commit
   hook that recursively mirrors directories and would fail CI if any copy drifted from its
   source. Testing the canonical copy is sufficient given that enforcement; duplicating the test
   9 times would be pure redundancy, not more safety.
5. Minor gaps, not blocking: only one non-divisible sequence per batch is tested (not multiple
   bad sequences triggering the `bad_lengths` list with >1 entry); the exact contents of
   `bad_lengths` in the error message aren't asserted (only the "must be divisible by" prefix via
   `match=`); `cp_world_size=1` (the "no splitting needed" early-return path, which is untouched
   by this fix) isn't re-tested here, but it's also not part of what changed.
6. Deterministic: pure tensor arithmetic via the function's own `cp_rank` parameter, explicitly
   designed (per the PR draft) to avoid needing `torch.distributed` process-group setup — no
   flakiness surface.

---

## Overall summary

Six of nine ship clean on test quality, three with different flavors of gap:

- **aiohttp-readuntil, chi-gethead, express-cookie, otel-urlparser, otel-forwarded,
  bionemo-thd**: SHIP. I executed a defect-pinning check for all six (full test suite for
  aiohttp/express/chi; standalone-extracted-function harnesses for the two otel fixes and
  bionemo-thd, since those modules can't be imported without unavailable dependencies) and in
  every case the base code fails/misbehaves exactly as claimed and the fix's own tests would
  catch a regression, not just the one exact repro input.
- **calibre-opds**: FIX-REQUIRED — the fix is correct (verified the exception-typing claim
  directly against the real `from_hex_unicode`), but ships with zero automated tests; the
  project's own convention of not testing `opds.py` mitigates but doesn't excuse this, since a
  narrow stub-based unit test is cheap and the author already built the equivalent harness for
  manual verification.
- **bionemo-amplify**: FIX-REQUIRED — the dtype half of the fix is genuinely tested and would
  catch a regression; the device half is not (the test's device assertion is trivially true
  before and after the fix, since it never constructs a non-CPU tensor), despite the PR
  description explicitly listing "raises a device-mismatch error" as one of the two symptoms this
  patch addresses.

No fix in this set is REJECT-worthy on test-quality grounds alone; assertj-percentage's blocker
(CONTRIBUTING's 100%-authorship clause) is a submission-policy issue outside this persona's remit,
noted for completeness.

---

## After reading README + exec-A/exec-B (revisions only, initial verdicts above are unchanged as written)

I read all nine evidence-folder READMEs and both `exec-A.md`/`exec-B.md` after finishing the
verdicts above. They corroborate every defect and every red/green result I executed myself
(same failure counts, same assertion text, in some cases the identical `2147483647` /
`[16, 17]`-dropped / `"["`-host numbers I reproduced independently) — no discrepancies against my
own findings anywhere. Two things change or strengthen a verdict:

- **calibre-opds: strengthens FIX-REQUIRED, doesn't change it.** Executor A's report (section
  "calibre-opds", finding 2) independently re-ran the validator's harness and found that
  `opds_category`/`opds_categorygroup` — the two sibling endpoints that decode ids the same way as
  `opds_navcatalog` — **still raise unhandled `binascii.Error` on the FIXED tree**, since the patch
  only touches `opds_navcatalog`. I had read the PR draft's own bracketed aside ("If sending the
  alternative patch, add: `opds_category` and `opds_categorygroup`... get the same try/except")
  and treated it as an author-flagged open question rather than a confirmed live gap; exec-A's
  independent run confirms it's real, not hypothetical. From a test-quality angle this sharpens
  finding #4 in my calibre-opds section: the missing test isn't just "no regression test for the
  one function fixed," it's "no test exists that would have caught the author's own explicitly
  named todo (fixing the siblings) being dropped between the draft note and the submitted patch."
  Still FIX-REQUIRED, not REJECT — the fix that did ship is correct for what it covers.
- **bionemo-amplify: no change, but independent confirmation.** Exec-A's own from-scratch
  ast-extraction (not the validator's canned harness) reproduced the identical RED (fp32 upcast)
  and GREEN (bf16 preserved) result I reasoned through without executing. It also did not test the
  device-mismatch half of the bug (no GPU available to executor A either) — so my finding #3 (the
  test's `output.device == source_embed.device` assertion is CPU-to-CPU and doesn't pin the
  device-mismatch symptom named in the PR's own summary) stands unrebutted by anyone who *could*
  execute torch. Confidence raised from medium to **high** that the dtype half is correctly pinned;
  the device-coverage gap finding is unchanged.
- All other verdicts (aiohttp-readuntil, chi-gethead, express-cookie, otel-urlparser,
  otel-forwarded, bionemo-thd, assertj-percentage) are corroborated with matching numbers by
  exec-A/exec-B and require no revision. Confidence on chi-gethead and express-cookie raised to
  high (unchanged from my own execution, since I'd already run the full suite myself); confidence
  on otel-urlparser/otel-forwarded raised slightly by exec-B's use of the project's actual harness
  scripts and jar-checksum verification, which is more rigorous than my standalone
  reflection-based extraction.
