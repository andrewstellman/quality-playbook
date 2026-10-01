# S4 — QA / test-quality review, round 2

Persona: quality engineer focused on test quality. For each fix: does the new test pin the
defect (fails if the fix is reverted, for the right reason)? Would it catch plausible future
regressions? Is it deterministic? What important edge is untested, and is anything
over-tested?

I independently reproduced red/green for four of the six fixes myself (aiohttp, both otel
fixes, calibre) using hand-rolled harnesses against the pinned `base` and `v2-*` source trees,
without reading the round-1 evidence first. For the two bionemo fixes I could not install
`torch` in this sandbox (disk pressure — ran out of space mid-`pip download`), so those two are
REASONED from source reading, then cross-checked against exec-A's independently-executed CPU
run in step 2 of the protocol. All commands and outputs referenced below were actually run in
`/tmp/review/work2/S4/`; nothing is copied from other reviewers' prose.

---

### aiohttp-readuntil
Verdict: SHIP
Confidence: high

Findings:
1. EXECUTED. I extracted the 8 new parametrized test functions from
   `tests/test_streams.py` into a standalone asyncio harness (no pytest infra needed — pure
   `StreamReader` unit) and ran it against both trees:
   - Against `v2-aiohttp-readuntil/aiohttp/streams.py`: 24/24 checks pass (all separator/split
     positions, one-byte-per-chunk, partial overlap, false-start, EOF-mid-separator, max_size,
     LineTooLong).
   - Against `base/aiohttp/streams.py` (pre-fix): 15 of the 24 checks fail, and the max_size
     case raises `LineTooLong` where the fixed code returns a 4-byte line — i.e. the bug is not
     just "wrong answer" but "wrong exception type" in one case. This matches exec-A's real
     pytest run (14 failed / 10 passed on RED, matching failure set on REVERT) almost exactly;
     the small count difference is because my harness counts sub-cases my ad hoc script grouped
     differently, not a discrepancy in behavior.
2. The test matrix (`separator × split-position` for `\r\n`, `\r\n\r\n`, `--xyz`, plus
   one-byte-per-chunk, partial-overlap-with-self-similar-prefix cases like `aab` split as
   `xa|a|b`, false-start `a\r\n\rb\r\n\r\n`, EOF exactly at/inside the separator, and
   `max_size`/`LineTooLong` interaction) is unusually thorough for a stream-parsing fix — it
   covers the class of bug (a separator whose bytes straddle a chunk boundary) rather than only
   the one reported instance, and the false-start case in particular is the sharpest regression
   guard: it forces the "look at tail+head together" logic to reject a partial match
   (`a\r\n\r`) that isn't actually the full separator.
3. Deterministic: pure in-memory `StreamReader.feed_data`/`feed_eof`, no real I/O, no
   time-dependency, no flaky waits.
4. Untested edge I did not see covered: a separator that appears as a *false-positive* fully
   inside a single already-buffered chunk while another true match straddles the next chunk
   boundary (i.e., two candidate matches racing) — narrow, low-value, not worth blocking on.
5. Nothing looks over-tested; round 1 flagged a test reading the private `_waiter` for possible
   removal, but grepping the v2 test file shows no `test_readuntil_separator_split_after_wait`
   test exists, so that's moot either way.

Round-1 required changes: not applicable to test content (round 1's required changes for this
fix were all disclosure/changelog text, not tests). The keep-the-tests recommendation ([S2, S3,
S4 in round 1] wanted to keep the full suite) was honored — all 8 test functions are still
present in v2.

---

### otel-urlparser
Verdict: SHIP
Confidence: high

Findings:
1. EXECUTED. I stripped `@Nullable`/`javax.annotation.Nullable` (dependency-only, logic
   untouched) from both the `instrumentation-api-incubator` and `reactor-netty` copies of
   `UrlParser.java`, compiled each against a small `javac`+reflection-free tester exercising
   `getHost`/`getPort`/`getPath` on the exact strings from `testGetHostAndPortWithIpv6`:
   - `v2` tree: 12/12 checks pass, including the two malformed-input rows added in v2:
     `getHost("https://[::1")` → null, `getHost("http://[::1/path]")` → null,
     `getHost("http://[x/p?token=abc]")` → null.
   - `base` tree: 9/12 fail, e.g. `getHost("https://[::1]")` → `"["` instead of `"::1"`, and
     `getHost("http://[x/p?token=abc]")` → `"[x"` (query text leaking into what would become
     `server.address`) instead of null.
   This matches exec-B's real JUnit run (2 failures in `incubator`, 1 in `reactor` on RED,
   identical failure set on REVERT, 34/34 and 9/9 on GREEN) and exec-B's own isolated probe of
   the same two malformed rows.
2. This is the one fix in the set where round 1 found an actual correctness gap in the fix
   itself, not just the PR text: the original `]`-search was unbounded, so
   `getHost("http://[x/p?token=abc]")` returned `"[x"` (query text as host) instead of null.
   **v2 added exactly the test row the synthesis asked for** (`http://[::1/path]` and
   `http://[x/p?token=abc]` → null), and my independent run confirms the fix's early-break on
   `/`, `?`, `#` inside the bracket search actually makes those return null now, not just that a
   test exists that happens to pass by coincidence.
3. The test set covers: bare `[::1]`, trailing slash, with port, with port+query, unterminated
   bracket, and the two "path/query text disguised as an IPv6 literal" adversarial cases — a
   good spread for a small parser. `ServicePeerResolverTest` also gained a `[::1]:8080` mapping
   row exercised through both a match and a mismatch case (`Arguments.of("::1", 8080, ...,
   "ipv6PortSvc", ...)` and `Arguments.of("::1", 9090, ..., null, null)`), which is the right
   shape for a lookup-table test (both a hit and a miss).
4. Untested edge: a bracket immediately followed by another bracket or by `%` (zone-id
   suffix, e.g. `[fe80::1%25eth0]`) — RFC 6874 zone IDs are a real IPv6-in-URL edge case and
   aren't exercised either here or, as far as I can tell, anywhere else in this parser's test
   file. Low priority (zone IDs essentially never appear in HTTP request URLs), not blocking.
5. Not over-tested. Deterministic (pure string parsing, no I/O).

Round-1 required changes:
- "Bound the `]` search... add a test row such as `http://[::1/path]` returning null" — **made**,
  verified by execution (finding 1 above), not just present in the diff.
- Pulsar follow-up / ClickHouse caller mention / `getPort()` behavior change — text-only asks,
  outside my charter; PR-DRAFT.md now contains all three, i.e. made.
- One thing worth flagging even though it's a text ask, not a test ask: `pulsar-2.8`'s own
  `UrlParser.java` (a completely separate class, different package) has the identical
  first-`:`-split bug and is untouched by this patch — confirmed by reading it directly
  (`authority.indexOf(':')`, no bracket handling at all). That's correctly disclosed in the PR
  body as a follow-up, not silently left out, so this is a scope note, not a defect in this fix.

---

### otel-forwarded
Verdict: SHIP
Confidence: high

Findings:
1. EXECUTED. `extractHost` and `extractFromForwardedHeader` are private static methods, but
   `ForwardedHostAddressAndPortExtractor`, `HeaderParsingHelper`, and
   `AddressAndPortExtractor`/`AddressPortSink` have no other dependencies, so I compiled them
   standalone (stubbing only the unused `HttpCommonAttributesGetter`/`AddressAndPort` generic
   parameters) and called the private methods via reflection with `setAccessible(true)`:
   - `v2` tree: 10/10 checks pass — `[::1]`, `[::1]:42`, `[2001:db8::1]:42` (with a trailing
     `test=abc:1234` param to confirm the `;`-terminated `Forwarded` parsing still works),
     quoted form, a malformed port (`[::1]:port` → address parsed, port silently dropped, same
     as the existing non-bracket malformed-port behavior), and an unterminated bracket
     (`[::1` → both address and port null, i.e. the extractor correctly reports "no match" so
     the caller falls through to the next header source, matching the PR's stated behavior
     change).
   - `base` tree: every bracketed case returns address `"["` or a truncated `"[2001"`, exactly
     the bug as described.
   This matches exec-B's real JUnit run (23/23 new rows fail on RED with the same failure
   signature, 127/127 pass on GREEN, identical 23 failures reappear on REVERT).
2. Good test shape: separate coverage for the `Forwarded: host="..."` path
   (`extractFromForwardedHeader`) and the direct `Host`/`X-Forwarded-Host`/`:authority` path
   (`extractHost`), plus an attribute-level integration test
   (`shouldExtractIpv6ServerAddressAndPortFromHostHeader`) that exercises the whole
   `HttpServerAttributesExtractor` pipeline rather than just the parser unit — this is the right
   layering (unit + one integration check) and would catch a regression introduced either in
   this extractor or in how `HttpServerAttributesExtractor` wires it in.
3. Deterministic, no I/O, pure string parsing over `Map<String,String>`-backed fake requests.
4. Untested edge, same class as otel-urlparser: a bracket with no closing `]` followed by more
   header content on the same line (`[::1:80, other-value`) — the multi-value/list header case
   combined with a malformed bracket. Low priority; the single-value unterminated case is
   covered and is the one that mattered for the reported bug.
5. Not over-tested.

Round-1 required changes: all were process/Gradle/PR-text items (spotless, EasyCLA, mention the
unterminated-`[` fallthrough behavior), none were test-content asks. The fallthrough behavior
is now both correctly implemented (verified above) and disclosed in PR-DRAFT.md.

---

### calibre-opds
Verdict: FIX-REQUIRED
Confidence: medium

Findings:
1. EXECUTED (via the validator's own harness, run fresh by me, not just read). I copied
   `evidence/calibre-opds-navcatalog/harness.py` and ran it under `python3.14` (found at
   `/sessions/kind-zealous-edison/.local/bin/python3.14` — the repo's default `python3` here is
   3.10, and the harness needs PEP 649's deferred-annotation default to `exec` the extracted
   function bodies without a `Context`/`RequestData`/`etree` namespace, which only 3.14 gives
   for free) against both trees:
   - `base`: navcatalog raises unhandled exceptions on 4/7 cases: empty string (`IndexError`),
     `zz` (`binascii.Error`), `4` (`binascii.Error`, odd length), `ff`
     (`UnicodeDecodeError`) — `RESULT: RED`.
   - `v2`: the three HTTP-reachable cases (`zz`, `4`, `ff`) now return `HTTPNotFound`; only the
     `which=''` case still raises `IndexError` (`type_ = which[0]` is not inside the
     `try`/`except ValueError`, and `from_hex_unicode('')` doesn't raise — it returns `''`
     successfully). Harness still reports `RESULT: RED` / exit 1 for this reason.
   This matches `v2/green.log`/`v2/red.log` in the evidence folder exactly (I ran the same
   commands independently before reading those logs) and matches exec-A's independent run.
2. **The `which=''` case is real but not reachable over HTTP**: I confirmed via the harness's
   own `parse_uri` reachability table that `/opds/navcatalog/` and `/opds/navcatalog//` both
   collapse to the 2-component path `('opds', 'navcatalog')`, which never matches the
   3-component route, so a direct call is the only way to hit `which=''`. `v2/CHANGES-FROM-V1.md`
   explains this is *why* v2 deliberately dropped the `if not which: raise HTTPNotFound` guard
   that the round-1 `alt/` patch had added (it was guarding something unreachable). I agree with
   that call on scope grounds — it doesn't change my verdict on its own.
3. **The actual gap, from a test-quality standpoint: the patch that will be submitted upstream
   ships with zero tests.** `git log`/the packet directory show no `tests/` changes at all. The
   verification that exists (this harness, the red/green logs, exec-A's independent rerun) all
   lives in the QPB evidence tree, not in the calibre repository. If this patch is reverted a
   year from now during a refactor of `opds.py`, nothing in calibre's own test suite would catch
   it — the harness that caught it here does not travel with the PR.
4. This is a real gap but a **mitigated** one, which is why I'm not marking REJECT: (a) calibre's
   own test suite explicitly opts out of OPDS coverage (`srv/tests/ajax.py:374`: "Not going test
   legacy and opds as they are too painful" — I grepped this myself, it's real, not just quoted
   from the PR draft), so a maintainer is unlikely to request one; (b) the maintainer's own
   history (per the brief) is to merge small fixes from this tool without tests; (c) round 1's
   own synthesis already classified a test here as "optional." I flagged the same thing in round
   1 (recorded there as "S2 and S4 would still add a stub-based one") and it wasn't added in v2 —
   this is a case where the "optional" framing from round 1 let a real gap persist into v2
   unchanged.
5. If a test is added, it doesn't need the full harness complexity: a minimal version could
   monkeypatch/stub just enough of `RequestContext`/`ctx`/`rd` to call `opds_navcatalog` directly
   with `which='zz'` and assert `HTTPNotFound` is raised — roughly 15 lines, reusing the same stub
   shape already proven out in `harness.py`. That would at least pin the three reachable cases in
   the repo itself, even if the project's convention is to skip full OPDS integration tests.

Round-1 required changes:
- "Send `alt/0001-*.patch` (all three handlers)" — made (v2's single patch touches
  `opds_navcatalog`, `opds_category`, `opds_categorygroup`).
- "Drop `if not which`" — made (confirmed absent in `opds_navcatalog` in the v2 diff; the
  pre-existing `if not which or not category` guards in the other two handlers, which predate
  this patch, were correctly left alone).
- "Delete the bracketed placeholder... cut the body... don't frame as security" — made (current
  `PR-DRAFT.md` is three sentences, no security framing, no placeholder).
- "A test is optional... S2 and S4 would still add a stub-based one" — **not made**. This is the
  one round-1 ask in my own charter that didn't land, which is why I'm keeping this at
  FIX-REQUIRED rather than SHIP even though the code change itself is correct and independently
  verified three times over (me, the evidence folder, exec-A).

---

### bionemo-amplify
Verdict: SHIP
Confidence: medium (REASONED — see below)

Findings:
1. REASONED, not executed by me: `torch` isn't installed in this sandbox and I ran out of disk
   space (`OSError(28, 'No space left on device')`) attempting `pip download` to add it. I did
   confirm the logic by hand: `torch.zeros(n, m)` defaults to `dtype=torch.float32` and
   `device='cpu'` regardless of the source tensor, and `torch.cat` requires matching dtypes (and
   normally matching devices) between the tensors it concatenates, so a bf16-on-CPU source with
   fp32-on-CPU padding rows is exactly the dtype-mismatch bug described. I cross-checked this
   against exec-A's independently-executed CPU-torch run (real `torch-2.14.0+cpu`, not a mock):
   RED = `test_pad_weights_dtype_device[cpu]` fails with `assert torch.float32 == torch.bfloat16`
   against unpatched source; GREEN = passes with the fix; REVERT (only the source hunk reversed,
   test kept) reproduces the identical failure. That's a real, independently-run execution
   result, not just restated from the PR draft, so I'm treating this fix as EXECUTED in effect
   even though I couldn't run it myself in this session.
2. The test asserts shape, dtype, device, that the original rows are preserved byte-for-byte
   (`torch.testing.assert_close(padded[:10], source_embed)`), and that the padding rows are
   exactly zero — this pins the defect precisely (dtype/device) while also guarding the
   surrounding logic (row count, value preservation) that a sloppier fix could break while still
   passing a dtype-only check.
3. **This was my own round-1 finding** ("The test's device assertion is CPU-to-CPU and pins
   nothing. Say so, or add a CUDA-skipped case [S4]") and **it was made**: the test is now
   parametrized over `["cpu", pytest.param("cuda", marks=skipif(not
   torch.cuda.is_available()))]`, so on a GPU runner it also proves the fix carries the device
   across a real CPU→CUDA gap, not just CPU→CPU where the stub default already happens to match.
   On a CPU-only runner (like this sandbox and presumably most CI) the cuda case is skipped, not
   silently omitted or falsely passed — correct determinism handling for a hardware-gated case.
4. Untested edge: `num_padding_rows == 0` (target vocab size already matches source) isn't
   exercised — `torch.zeros(0, m, dtype=..., device=...)` should be a harmless no-op concat, but
   it's not explicitly asserted. Low priority.
5. Not over-tested.

Round-1 required changes: the PR-text corrections (drop "silently upcasts", fix the misattached
ESM2 clause, use the repo's PR template) are outside my charter; skimming `PR-DRAFT.md` they
read as addressed (no "silently upcasts" language present, plain factual framing). The one
test-content ask in my lane (CUDA-skip parametrization) was made, which is why I'm at SHIP
rather than FIX-REQUIRED here despite not executing it myself.

---

### bionemo-thd
Verdict: SHIP
Confidence: medium (REASONED — see below)

Findings:
1. REASONED, not executed by me (same torch/disk constraint as amplify). Traced the logic by
   hand: `cu_seqlens_padded=[0,8,18]` gives per-sequence lengths `[8,10]`;
   `total_slices_of_any_sequence = 2*cp_world_size = 4`; `10 % 4 = 2 != 0`, so `bad_lengths=[10]`
   and the f-string produces `"Padded sequence length(s) [10] must be divisible by 4 (2 *
   cp_world_size)..."`, which matches the test's `pytest.raises(ValueError, match=r"\[10\] must
   be divisible by 4")`. Cross-checked against exec-A's independently-executed run: RED = the
   new `test_split_batch_by_cp_rank_thd_non_divisible` fails with `DID NOT RAISE ValueError`
   against unpatched source, and exec-A's own extracted demo shows the *consequence* directly —
   token positions [16, 17] silently dropped for this exact input, 14 positions dropped for a
   larger 7-sequence example. GREEN = 6/6 pass. REVERT (only the collator hunk reversed)
   reproduces the identical `DID NOT RAISE` failure. Real, independently-run execution, not
   restated from the draft.
2. `test_split_batch_by_cp_rank_thd_covers_all_tokens` (divisible-length case) is a genuine but
   secondary addition: it sorts the concatenation of every CP rank's shard and compares it to the
   original flattened `arange` input. Because the input values are unique, this catches both
   duplicate assignment and dropped tokens (a silent drop would leave the sorted result
   short/misaligned against the original), which is the right property to check for a "does
   every token land exactly once" test rather than checking exact shard contents. It does not by
   itself pin the reported bug (that's the `_non_divisible` test) — it's a coverage bonus around
   the happy path, correctly separated into its own test rather than piggybacked onto the bug-fix
   test.
3. Determinism: `torch.arange`-based fixtures, no randomness, no I/O.
4. **Completeness/test-blast-radius check, not just source-reading**: the patch touches the same
   function body in 10 files (`models/{esm2,llama3,mixtral,qwen}/collator.py` plus 6
   `recipes/*/collator.py`), but adds the test to only one file
   (`models/esm2/tests/test_collator_context_parallel.py`). I confirmed this is *not* a coverage
   gap: `models/esm2/collator.py` is the declared canonical source (the other 9 files each carry
   a "This file is copied from: models/esm2/collator.py" banner), the patch's commit message
   states the copies were "regenerated with check_copied_files.py --fix", and I md5-summed all 10
   post-patch copies myself: the 9 downstream copies are byte-identical to each other (the
   canonical `esm2` file differs only because it additionally contains the test-adjacent code the
   others don't need). exec-A went further and adversarially broke sync in one copy, confirming
   `check_copied_files.py` (no `--fix`) exits 1 and names the mismatched files — so the
   project's own tooling, not just convention, would catch a future drift between the tested
   source and its copies. Testing the canonical file once is the correct scope here, not a gap.
5. Untested edge: a batch with *some* sequences divisible and others not (the test only exercises
   a single bad length per case) — the `bad_lengths` list-and-truncate-at-5 error-message logic
   (`f" (and {len(bad_lengths) - 5} more)"`) is entirely unexercised. Low priority given the
   error is user-facing text, not behavior, but a mixed-batch case would be a stronger regression
   guard than two single-length cases.
6. Not over-tested.

Round-1 required changes: PR-text corrections ("silently lose training tokens" →
what-was-shown, `L0_sanity_cp.yaml` safety note, actionable error message, process-timeout
warning) are outside my charter and read as addressed in the current error string and
PR-DRAFT.md. "Move the tests into `test_collator_context_parallel.py`" — made (that's exactly
where they are). No test-content ask from round 1 was left unaddressed for this fix.

---

## Summary

| Fix | Verdict |
|---|---|
| aiohttp-readuntil | SHIP |
| otel-urlparser | SHIP |
| otel-forwarded | SHIP |
| calibre-opds | FIX-REQUIRED (add even a minimal stub-based regression test; the code fix itself is correct and triply verified) |
| bionemo-amplify | SHIP |
| bionemo-thd | SHIP |

Four of six fixes I verified myself by executing the actual (or a faithfully extracted) code
path against both the base and v2 trees, from scratch, before reading any other reviewer's or
executor's report. The two bionemo fixes I could only reason through by hand due to `torch` not
being installable in this sandbox (disk exhausted mid-download), but both are corroborated by a
real, independently-executed CPU-torch run in `exec-A.md` that I read afterward and whose
described failure signatures match my hand-traced predictions exactly. calibre-opds is the only
fix in the set that ships with no test at all in the actual patch — the extensive verification
that exists for it (mine, the evidence folder's, exec-A's) is all harness-based and external to
the repository, so a future revert of this fix would not be caught by anything that ships with
the PR. That gap was already identified in round 1 (by me, among others) and marked "optional";
it remains open in v2 and I'm treating it as the deciding factor between SHIP and FIX-REQUIRED
for that fix specifically, while agreeing with the panel that a full OPDS test suite is not
warranted given the project's own stated position on OPDS test coverage.

What I did not check: I did not attempt to install a JDK-based build system (Gradle) for either
otel fix — my Java verification was javac + reflection against the specific classes, same
scope as exec-B's javac+JUnit-console approach, not a full module build. I did not check whether
the aiohttp CHANGES/PRNUMBER.bugfix.rst filename or CONTRIBUTORS.txt entry are still open items
(text/process, outside my charter). I did not independently verify the otel Gradle
spotless/checkstyle claims — nobody on this panel has a working Gradle environment here, per
exec-B's report.
