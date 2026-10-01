# S5 — Backward-compatibility review, round 2

Persona: for each fix, enumerate every observable behavior change an existing caller could see
(return values, exceptions, status codes, attribute values, error messages, config that used to
work and now fails), identify who is affected by grepping the base tree, and judge whether the
PR/changelog states each change. Read-only; no source under `/tmp/review/src` or
`/tmp/review/packets2` was modified.

---

### aiohttp-readuntil

**Verdict:** SHIP
**Confidence:** high

**Findings:**
1. `aiohttp/streams.py:396-420` (base) — `readuntil()` searched `self._buffer[0]` in isolation per
   loop iteration (`self._buffer[0].find(separator, offset)`), so a separator whose bytes straddle
   two buffered chunks was never matched. The v2 fix (`streams.py`, `tail`/`head` concat) closes
   this. `readline()`, which defaults to the one-byte `b"\n"` separator, is unaffected — the new
   `if chunk and seplen > 1:` branch is skipped whenever `seplen == 1`.
2. **Observable change #1 (return value):** for a multi-byte separator, `readuntil()` now returns
   data cut exactly at the separator in strictly more cases than before. Previously, a caller could
   receive extra bytes past the separator (e.g. `b"line1\r\nline2"` instead of `b"line1\r\n"`) when
   the separator was split across chunks. Grep of the base tree (`grep -rn "readuntil(" aiohttp/`)
   shows no internal caller uses a multi-byte separator — `readline()` is the only internal caller
   and uses the single-byte default. So this only affects external callers who invoke
   `StreamReader.readuntil()` directly with a multi-byte separator (a public, documented API since
   aiohttp 3.x). Any such caller was, by construction, getting wrong data before; this is a
   correctness fix, not a contract change.
3. **Observable change #2 (exception behavior), self-disclosed in the PR):** "a line that exactly
   fits `max_size` but whose separator is split across chunks is now returned instead of raising
   `LineTooLong`." This is a real, user-visible change — a caller whose exception-handling path
   depended on `LineTooLong` firing in that specific split-boundary edge case will stop seeing it.
   Given the trigger condition (max_size exactly hit by a chunk-boundary artifact of the buggy
   scanner) is not something any reasonable caller could have relied on deliberately, this is
   acceptable as a bug fix, and it is explicitly named in "Are there changes in behavior for the
   user?" in `PR-DRAFT.md` — good disclosure.
4. `CONTRIBUTORS.txt` and the `Drafted with Claude Opus 5.5; reviewed by andrewstellman.` line
   match the exact form aiohttp's `AGENTS.md` requires (one plain disclosure line, no
   `Co-Authored-By:` trailer). Verified against `AGENTS.md`'s "Disclosure" section in the base tree.
5. No config, return-type, or public-signature change. `readuntil()`'s signature and default are
   unchanged.

**Round-1 required changes** (from `v2/CHANGES-FROM-V1.md`):
- Disclosure line in AGENTS.md form: **made** — verified byte-for-byte match against `AGENTS.md`.
- State the `max_size`/`LineTooLong` behavior change: **made** — present in the PR body, and I
  independently confirm the underlying claim is accurate (see finding 3).
- Comment on `tail`/`head`/`n` arithmetic: **made** (comment only, no logic change, consistent with
  the brief).
- Drop the private-`_waiter`-reading test: **made**; the executor's red/green/revert cycle still
  reproduces the fix cleanly with 8 remaining test functions instead of 9.

No file, exception hierarchy, or Python fact needed independent verification beyond what I checked
(the pure-Python code path only; Cython-extension behavior was not exercised by executor A, per
their report, since `AIOHTTP_NO_EXTENSIONS=1` was used throughout — this means the C-accelerated
`readuntil` path, if one exists, was not independently confirmed. Worth a one-line flag to the
maintainers/executors, not a blocker: aiohttp's `AGENTS.md` itself says "Any parser/websocket
related changes have been tested with Cython extensions installed" — `readuntil` is a stream
reader method, not clearly in that bucket, but it's adjacent enough to name explicitly.)

---

### otel-urlparser

**Verdict:** SHIP
**Confidence:** high

**Findings:**
1. Base `UrlParser.getHostEndIndexExclusive` (`instrumentation-api-incubator/.../UrlParser.java:103-113`)
   scans for the first `:`, `/`, `?`, or `#` from `startIndex`. For `"http://[::1]:8080/"`,
   `startIndex` points at `[`; the first `:` found is one character later (inside the brackets), so
   `getHost` returns `"["` and `getPort` returns `null` (confirmed independently by re-reading the
   base source and by executor B's isolated probe: `base → "["`, `fix → "::1"`).
2. **Observable change (return value):** `getHost()` on a bracketed-IPv6 authority now returns the
   unbracketed address (`"::1"`) instead of the single-character garbage string `"["`; `getPort()`
   now returns the port instead of `null`. This is an attribute-value change that propagates to
   every caller listed in `PR-DRAFT.md`:
   - `ReactorNettyHttpClientAttributesGetter` — `server.address` changes from `"["` to `"::1"`
     (etc.), and `server.port` changes from a fallback default (80/443) to the actual port.
   - `ServicePeerResolver` — a `service_peer_mapping` entry keyed on a bracketed-IPv6 host now
     matches (it previously could never match anything, since every bracketed host parsed to `"["`).
   - `ClickHouseClientV2Singletons` (`CurrentServerInfo`) — same address/port fix for a configured
     IPv6 endpoint.
   All three are named in the PR body — this is a well-disclosed, itemized list of affected callers,
   which is exactly what a compat reviewer wants to see. I did not independently grep beyond
   confirming these three call sites exist in the two `UrlParser.java` copies' package trees; I
   accept the PR's own caller enumeration as the executor and round-1 panel already exercised it
   (`ServicePeerResolverTest` new IPv6 rows pass per executor B).
3. **New "malformed becomes null" case:** `getHost("http://[x/p?token=abc]")` (no closing `]` before
   `/`, `?`, or `#`) now returns `null` instead of the base behavior of `"[x"` (base) — confirmed by
   executor B's isolated probe (`base → "[x"`, `fix → null`). This is a second observable change,
   correctly covered by round-1 item "bound the `]` search to the authority" and tested in v2
   (`testGetHostAndPortWithIpv6`). Any caller currently getting `"[x"` as an address for a malformed
   URL was already getting nonsense; converting that to `null` (the same signal used for "no host")
   is consistent with the rest of the class's contract (`getHost` already returns `null` for other
   unparsable cases) and is not a new failure mode — it's the fix making an existing failure mode
   consistent.
4. No change to method signatures (`getHost(String)`, `getPort(String)`, `getPath(String)` all keep
   their existing signatures and `@Nullable` contracts).
5. `Assisted-by: Claude Opus 5.5` trailer present, matching the maintainer-context requirement for
   OpenTelemetry; PR text has a single disclosure sentence with no HTML comments or
   notes-to-Andrew. EasyCLA is Andrew's own action (correctly deferred, per `CHANGES-FROM-V1.md`).

**Round-1 required changes** (from `v2/CHANGES-FROM-V1.md`):
- Bound the `]` search to the authority: **made** — matches `HttpServerAddressAndPortExtractor`'s
  bound, confirmed by executor B's `v1-code-v2-tests.log`-equivalent probe (base gives `x/p?token=abc`
  as host on the pre-bound logic; fix gives null).
- Mention the ClickHouse caller: **made**, no test added (round-1 said "consider," not "require" —
  correctly optional).
- Mention pulsar's independent `UrlParser` as a deliberately-excluded follow-up: **made**, and this
  scoping is the right call — expanding scope to a third, unrelated copy of the parser in the same
  PR would make the diff harder to review and isn't needed to fix the claimed bug.
- State that `getPort()` now returns the port instead of null: **made**.

---

### otel-forwarded

**Verdict:** SHIP
**Confidence:** medium (one nuance below, not blocking)

**Findings:**
1. Base `ForwardedHostAddressAndPortExtractor.extractHost` (`instrumentation-api/.../ForwardedHostAddressAndPortExtractor.java:69-90`)
   has no `[`-aware branch; it splits at the first `:` unconditionally, matching the same class of
   bug as otel-urlparser. Confirmed by re-reading the base source.
2. **Observable change (return value):** for `Host`/`X-Forwarded-Host`/`:authority`/`Forwarded:
   host=` values with a bracketed IPv6 authority, `server.address`/`server.port` (via
   `HttpServerAttributesExtractor`) change from garbage (`"["`, `"[2001"`, no port) to the correct
   unbracketed address and port. Confirmed independently against executor B's RED/GREEN evidence
   (23 new parametrized failures on base, all passing on the fix, with example diffs quoted in
   their report matching the PR's own claim).
3. **Observable change (new failure mode), self-disclosed in the PR:** an unterminated bracket
   (`Host: [::1` with no closing `]`) is now treated as malformed and the extractor returns `false`
   for that header, falling through to the next header source (`X-Forwarded-Host` → `:authority` →
   `Host`, in the order `extract()` iterates). I traced this in the base source
   (`ForwardedHostAddressAndPortExtractor.java:extract()`, lines 22-48): the method loops over each
   header name in a fixed priority order and calls `extractHost`/`extractFromForwardedHeader` per
   header value; if none succeed, `extract()` returns without setting anything on `sink`. This
   mirrors the *already-existing* fallthrough behavior for a malformed quoted value (unterminated
   `"` in `extractHost`, base lines 72-79 — `notFound(quoteEnd, end)` also returns `false` and falls
   through), so this is not a *new* code path, only the bracketed-IPv6 case being routed into the
   same existing fallthrough. The PR states this plainly: "an unterminated `[`... is now treated as
   malformed... so the extractor falls through to the next header source instead of recording
   `server.address = "["`." Good disclosure.
4. **Nuance not explicitly called out (this is why confidence is "medium," not a blocker):** the
   fallthrough on a malformed bracketed value could, in principle, cause a *different* address to be
   picked up entirely (e.g. a malformed `Forwarded: host="[::1"` falling through to a well-formed
   but different `X-Forwarded-Host` or `Host` header), not just "no address" — this is a second-order
   effect of "fails and moves to the next source" rather than "fails and stops." Since the same
   fallthrough already existed for malformed quotes before this patch, this is pre-existing extractor
   behavior being extended to a new malformed-input shape, not a new interaction the fix introduces.
   I did not find this specific multi-header-fallthrough interaction called out in the PR text or in
   `CHANGES-FROM-V1.md`; it is minor (malformed unterminated-bracket headers are rare, and the
   existing quote-fallthrough precedent makes it consistent, unsurprising behavior) but worth a
   one-line mention if the panel wants belt-and-suspenders disclosure. Not a reason to hold the PR.
5. `Assisted-by: Claude Opus 5.5` trailer present; PR framed as a named follow-up to #15158/#19540.

**Round-1 required changes** (from synthesis references cited in the PR + `v2/CHANGES-FROM-V1.md`
pattern used for the sibling otel-urlparser fix — this fix's own `v2/CHANGES-FROM-V1.md` was not
present in its evidence folder listing at review time, so I rely on the PR body itself, which
already states the malformed-value behavior change and cites #19540/#15158 as precedent): the PR
explicitly documents the one behavior change I'd flag as most compat-relevant (finding 3), which is
the one round-1 (per the otel-urlparser precedent set by the same panel) would have asked for.

---

### calibre-opds

**Verdict:** SHIP
**Confidence:** high

**Findings:**
1. Base `opds_navcatalog`, `opds_category`, `opds_categorygroup` (`src/calibre/srv/opds.py`) call
   `from_hex_unicode(which)` unguarded. I verified independently (not just trusting the PR) that
   `binascii.Error` and `UnicodeDecodeError` are both subclasses of `ValueError`:
   `binascii.Error.__mro__ == (binascii.Error, ValueError, Exception, BaseException, object)`,
   `UnicodeDecodeError.__mro__ == (UnicodeDecodeError, UnicodeError, ValueError, Exception,
   BaseException, object)`. So `except ValueError:` in the v2 patch catches both exception types the
   PR claims are raised by malformed hex ids (non-hex chars → `binascii.Error`; odd-length →
   `binascii.Error`; valid hex but invalid UTF-8 → `UnicodeDecodeError`) — the exception-hierarchy
   claim in the PR is correct.
2. **Observable change (status code):** malformed `which`/`category` path segments in these three
   OPDS handlers now return `HTTP 404 Not Found` instead of `HTTP 500 Internal Server Error`. Any
   client (OPDS reader app, monitoring/scraper) that specifically branches on 500 vs. 404 for these
   endpoints would see a different code; I consider this an extremely unlikely legitimate dependency
   — no client should be relying on a malformed-input path returning 500, and every other malformed-
   input case in the same handlers (empty id, not-found category, etc.) already returns 404 via the
   same `HTTPNotFound` exception, so this makes the three fixed call sites *consistent* with the rest
   of the file rather than introducing new status-code semantics.
3. **Response body / server logs:** a 500 previously likely produced either a generic error page or
   (depending on calibre's error-handling config) a traceback; a 404 raises `HTTPNotFound('Not
   found')`, the same message used by the surrounding code (e.g. line 553, 555, 659 in base — grepped
   directly). No new/different message text is introduced; it reuses the existing string literal.
4. No config or public API change — this is server-side HTTP status codes for the content server's
   OPDS feed endpoints, no client library surface changes.
5. Framing check (maintainer context: "None of these are security issues"): the v2 PR title and body
   are framed strictly as a 500→404 correctness/log-noise fix, no security language — matches the
   maintainer's stated preference from the earlier round of merged fixes from the same tool.

**Round-1 required changes** (from `v2/CHANGES-FROM-V1.md`):
- Base patch swapped to the 3-handler `alt/` version: **made**.
- Dropped `if not which: raise HTTPNotFound(...)` (unreachable dead code, since `parse_uri` already
  drops empty path segments before this handler's route ever matches): **made**, and the reasoning
  is independently checkable — the appendix's `parse_uri` output table shows the empty-segment cases
  collapsing to a route that can't match a 3- or 4-component handler. I did not personally re-run
  `parse_uri`, but the transcript is internally consistent and the same fact is independently
  confirmed by executor A's harness run ("only the `empty` case... which the harness itself and
  `v2/CHANGES-FROM-V1.md` document as unreachable over HTTP").
- PR body rewritten, no security framing: **made** (see point 5 above).
- Fresh v2-specific verification: **made** per executor A's independent RED/GREEN/REVERT harness
  run (4 unhandled exceptions on base → 1 unreachable-only on fix → 4 again on revert).

---

### bionemo-amplify

**Verdict:** SHIP
**Confidence:** high

**Findings:**
1. Base `_pad_weights` (`models/amplify/src/amplify/state_dict_convert.py:85-91`) builds
   `padding_rows = torch.zeros(num_padding_rows, source_embed.size(1))` with no `dtype=`/`device=`,
   which defaults to `torch.float32` on CPU. `torch.cat((source_embed, padding_rows), dim=0)` then
   combines the source embedding with these fp32/CPU padding rows.
2. **Observable change (return dtype/device), for two distinct input shapes:**
   - **Non-fp32 source (e.g. bf16):** I could not run `torch.cat` locally to confirm whether it
     silently type-promotes to fp32 or raises on a dtype mismatch (no `torch` available in this
     sandbox — see caveat below), but either way the fix changes the result: either the previously
     *silent* upcast to fp32 (my best understanding of current PyTorch `torch.cat` type-promotion
     behavior, unverified here) now correctly returns bf16, or a previous hard crash on dtype
     mismatch (if no promotion occurs) is now avoided entirely. Executor A's harness independently
     confirms the CPU case: unpatched code fails `assert padded.dtype == torch.bfloat16` with
     `AssertionError: assert torch.float32 == torch.bfloat16`, and the patched code passes — this
     confirms silent fp32 upcasting is the base behavior (not a crash), so the observable change for
     CPU bf16 sources is "the returned tensor's dtype changes from float32 to the source dtype."
   - **Non-CPU source (CUDA):** `torch.cat` requires all tensors on the same device; before the fix,
     a CUDA source embedding combined with CPU padding rows would raise `RuntimeError` ("Expected
     all tensors to be on the same device..."). This case was not run by anyone (no GPU in this
     sandbox, none in the CI referenced) — the PR itself says "I haven't run that case because I
     don't have a GPU," which I consider adequately caveated, not a defect.
3. Who is affected: `_pad_weights` is used for both `_pad_embeddings` (source_key
   `embeddings.weight`, base file line ~93-97) and `_pad_decoder_weights` (source_key
   `decoder.weight`, lines ~99-102) — confirmed by re-reading `state_dict_convert.py`. Both callers
   get the same dtype/device fix. The PR further traces that `apply_transforms` (called without
   `cast_dtype`) asserts every parameter kept its original dtype (`state.py:238-243`), so a bf16
   conversion today most likely fails loudly at that assertion rather than quietly emitting fp32
   weights — meaning the "silent corruption" framing in v1 was corrected to "likely crashes anyway"
   in v2, and this correction is called out explicitly in `CHANGES-FROM-V1.md` ("Impact claim
   corrected... v2 states the function-level fact").
4. No public function signature change; `_pad_weights(ctx, source_embed)` keeps its signature.
   `export.py`'s default fp32-CPU path is unaffected (no change for the common case), per the PR's
   own "Usage" section — I did not independently verify this claim beyond reading it, since it
   requires tracing `from_pretrained`'s default dtype, which is a HuggingFace library fact outside
   the diff; flagging as unverified rather than asserting it.
5. Consistent with sibling code in the same file: `_pad_bias` already passes `dtype=`/`device=`
   (confirmed by re-reading lines 109-117) — the fix brings `_pad_weights` in line with the existing
   convention in the same file, which is a strong signal this is the intended behavior, not a new
   design decision.

**Round-1 required changes** (from `v2/CHANGES-FROM-V1.md`):
- Impact-claim correction (function-level fact instead of "silently upcasts"): **made**.
- Test moved into the existing test file, one-line docstring, no new file/license header needed:
  **made**.
- CUDA case parametrized and explicitly skipped when unavailable, rather than only testing CPU-to-
  CPU (which "pinned nothing," per round-1 finding S4): **made** — I confirm this matters: a
  CPU-only device-equality assertion is trivially true before and after the fix, so round 1 was
  right to flag it, and v2's `pytest.mark.skipif(not torch.cuda.is_available())` correctly narrows
  the claim to "CPU dtype verified, CUDA device path untested," which the PR states honestly.

**Caveat:** I do not have `torch` available in this sandbox and did not independently reproduce the
dtype-promotion or device-mismatch claims beyond what executor A's harness log already shows for the
CPU/bf16 case. The CUDA-device claim is unverified by anyone in this round, and both the PR and I
say so rather than asserting it.

---

### bionemo-thd

**Verdict:** SHIP (with one design nuance flagged for maintainer attention, not a blocker)
**Confidence:** high

**Findings:**
1. Base `_split_batch_by_cp_rank`'s THD branch (`models/esm2/collator.py:973-975`, mirrored in 9
   other files) computes `slice_sizes` via floor division:
   `(cu_seqlens_padded[1:] - cu_seqlens_padded[:-1]) // total_slices_of_any_sequence` with no
   remainder check, unlike the BSHD branch which already raises `ValueError` for the same shape of
   problem (I confirmed the BSHD branch has a pre-existing check by reading `_process_tensor_bshd`
   and the round-1/v2 doc's reference, though I did not re-derive it from scratch character-by-
   character beyond confirming the function exists and the file's `_process_tensor_bshd` handles a
   `cp_world_size`-divisibility case — the PR's central comparison to an *existing, already-shipped*
   check for the sibling code path is accurate and directly checkable in the base file).
2. Confirmed this branch is gated to only fire when context parallelism is actually enabled:
   `if cp_world_size is None or cp_world_size <= 1: return input_ids_padded, labels_padded` (base,
   `collator.py`, just above the `qvk_format == "thd"` branch). So the blast radius is exactly
   "THD-format training with `cp_world_size > 1`," not all users of the collator.
3. **Observable change (exception vs. silent data loss):** a training run using THD + CP with a
   padded sequence length not divisible by `2 * cp_world_size` previously *completed* (no exception)
   while silently dropping the remainder tokens from every CP rank's shard (executor A's demo:
   positions 16 and 17 dropped for `cu_seqlens_padded=[0,8,18]`, `cp_world_size=2`; scaled up, "14
   token positions dropped" across 7 length-6 sequences). After the fix, the same input raises
   `ValueError` on the first affected batch. This is the single most consequential compat change in
   this batch of six: a config that "worked" (produced output, just wrong/incomplete) now fails hard.
   This is unambiguously correct to fix (silent token loss during training is a much worse failure
   mode long-term), but it is a genuine breaking change for any existing run relying on the old
   (buggy) behavior to complete.
4. **Disclosure: excellent.** `PR-DRAFT.md` states this plainly ("a config that drops remainder
   tokens today will now fail with this error on the first batch that contains an affected length"),
   checks the shipped configs for safety (`L0_sanity_cp.yaml` uses 16 with `cp_size: 2`, divisible by
   4; the only other config setting the value doesn't use CP), and further identifies a **new
   operational risk this fix introduces**: under real multi-GPU CP training, the collator runs on CP
   rank 0 inside `ContextParallelDataLoaderWrapper`; when rank 0 raises, the PR states the other CP
   ranks "wait in the scatter until the process-group timeout" rather than failing together
   immediately — meaning a misconfigured run doesn't just error, it *hangs for the NCCL/process-group
   timeout* (commonly 10-30 minutes) across every other rank before the job dies. The PR explicitly
   labels this "I haven't run this multi-rank; it comes from reading the code" and offers an
   alternative (a config-time `pad_sequences_to_be_divisible_by % (2 * cp_size) == 0` check at
   dataloader setup, so every rank fails together at startup instead of one rank raising mid-run).
5. **My assessment of the disclosed nuance:** this is a legitimate design question, not a defect in
   the patch as submitted — the PR is honest that the per-batch check (matching the existing BSHD
   precedent's placement) trades "catches direct collator callers too" for "can hang other ranks
   until timeout in the CP case." Given how expensive a hung multi-GPU job is (wasted GPU-hours vs.
   the previous silent-corruption failure mode, which at least didn't waste compute), I'd recommend
   the panel/maintainers weigh in on whether to request the config-time check *in addition to* this
   one before merge — but the patch's correctness and its disclosure of this tradeoff are both sound,
   so I don't think this should block shipping the PR as a draft for maintainer discussion. Flagging
   as a discussion point for the synthesis, not a required change.
6. All 10 mirrored copies (`models/{esm2,llama3,mixtral,qwen}`, `recipes/*`) are identical (confirmed
   in the diff and by executor A independently running `ci/scripts/check_copied_files.py`, exit 0,
   and sanity-checking that the checker actually detects a real mismatch when one copy is reverted).
   No copy was missed.
7. No public function signature change; `_split_batch_by_cp_rank` keeps its existing parameters.

**Round-1 required changes** (from `v2/CHANGES-FROM-V1.md`):
- Error message tells the user what to change (`set pad_sequences_to_be_divisible_by to a multiple
  of N`) instead of naming a private function: **made**.
- Truncate to 5 bad lengths + "(and N more)": **made**, confirmed in executor A's green log.
- Impact-claim correction (concrete dropped-token example instead of "silently lose tokens with no
  error"): **made**.
- Shipped-configs safety check: **made**, and independently plausible given the gating condition
  confirmed in finding 2.
- Behavior-change warning (S5's own round-1 item, if I am this same persona from round 1 — noting it
  regardless of attribution): **made**, and the process-group-timeout consequence was *added* in v2,
  which is the most important compat-adjacent addition in this whole batch of six fixes.

---

## Overall summary

All six v2 patches are backward-compatible in the narrow sense of "no public signature changes, no
new required config," but four of the six change observable output for currently-malformed or
currently-mishandled inputs (calibre: 500→404; otel-urlparser and otel-forwarded: garbage
host/port strings → correct values or `null`; bionemo-thd: silent token drop → hard `ValueError`).
Every one of these four changes is explicitly named in its own PR-DRAFT.md, which is the right
place for it — none of these needs a separate deprecation cycle or major-version bump, since in
every case the "old" behavior was already a bug rather than a supported contract. aiohttp and
bionemo-amplify are narrower fixes (dtype/parsing correctness) with equally clear disclosure.

The one item I'd want the synthesis to weigh explicitly is bionemo-thd's process-group-timeout
risk (finding 5 above): turning a silent-corruption bug into a hard per-rank failure is the right
direction, but in a real multi-GPU job it currently trades "wrong answer, job finishes" for "job
hangs until NCCL timeout, then fails" for the *same* misconfiguration, and the author has already
proposed the config-time alternative that would avoid that trade. That's worth a maintainer
decision, not a hold on the PR itself.

**Not independently checked in this round:** the aiohttp C-extension `readuntil` path (only
`AIOHTTP_NO_EXTENSIONS=1` pure-Python was exercised, per executor A); the bionemo-amplify
CUDA-device `torch.cat` dtype-mismatch claim (no GPU or `torch` install available to me); Gradle-
level checks for both otel fixes (executor B ran javac + JUnit console only, no `./gradlew`,
spotless, checkstyle, or muzzle). None of these gaps changes my verdicts above, but they are gaps,
not confirmations.
