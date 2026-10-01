# O2 — Security engineer review (defensive)

Reviewer: O2 (security engineer). For each fix I asked two questions: (1) does the fix introduce a new weakness (unbounded work on untrusted input, new exceptions escaping to callers, changed validation, information leaking into logs or error messages)? (2) is the original bug security-relevant in a way that would call for the project's private disclosure process instead of a public PR?

Method: I read each packet and the base/fixed source. Where it was cheap I ran targeted checks in `/tmp/review/work/O2/`: a differential fuzz of aiohttp `readuntil` plus an adversarial-chunking timing run, and one Go test for chi (the URLFormat interaction). I did not build or run OTel, assertj, calibre, bionemo or express. Those findings are reasoned from the source only.

## Initial verdicts (written before reading any validator README or exec report)

### aiohttp-readuntil
Verdict: SHIP
Confidence: high
Findings:
1. **No new unbounded work.** The added overlap check (`aiohttp/streams.py` fixed, lines ~399-407) slices `tail = chunk[1 - seplen:]` and `head = self._buffer[0][offset : offset + seplen - 1]`, then runs `find` on at most `2*(seplen-1)` bytes. That is O(seplen) per buffered chunk, independent of chunk contents. `seplen` comes from the caller, not from the peer. The existing `max_size` / `LineTooLong` check (`streams.py:409-410` base) still runs on every iteration, so total work stays bounded by `max_size` (default `_high_water`). Measured with 200,000 one-byte chunks and a 1000-byte separator that never matches: 1.82 s base vs 2.19 s fixed, about 20% more in a deliberately worst-case shape. No new quadratic behaviour. The pre-existing `chunk += data` concatenation dominates and is unchanged.
2. **Correctness under adversarial chunking.** I ran a 20,000-case differential fuzz (random separators of 1-5 bytes over a 2-letter alphabet, so self-overlapping separators like `aab` and `aaba` are included, with random chunk splits) against a `bytes.find` reference. Base: 2021 mismatches. Fixed: 0.
3. **No new exceptions, and the error content is unchanged.** `LineTooLong(chunk[:100] + b"...")` was already there. It echoes up to 100 bytes of peer data into the exception message, but that behaviour exists in base too.
4. **Not a private-disclosure case.** Inside aiohttp, every caller goes through `readline()`, which uses the one-byte default separator `b"\n"` (`streams.py:378-379`, `multipart.py:404,500,514,887`). Those callers are unaffected by the bug. Only third-party code that calls `readuntil()` with a multi-byte separator is affected. For those callers the bug is a framing error: the call returns data past the separator, or waits until `max_size`. It could matter to someone building a protocol parser on top of it, but aiohttp's `SECURITY_EXTRA.md` requires "a reproducer that makes an HTTP request" through aiohttp, and no in-library HTTP path reaches the multi-byte branch. A public PR is appropriate. Do not frame it as a security fix.

### chi-gethead
Verdict: SHIP
Confidence: medium
Findings:
1. **No new weakness.** The look-ahead (`middleware/get_head.go` fixed, lines 23-41) only decides whether to rewrite `rctx.RouteMethod` to `GET`. The request is still routed by the sub-router with the same middleware stack. A wrong look-ahead result can only produce either GET-handler-for-HEAD, which was the behaviour before, or a 405. Neither path skips any middleware. `Match` on the root is the same bounded tree walk as before (`mux.go:373-408`), and no new panics are possible.
2. **Limitation to document (not blocking).** The fix swaps the sub-relative `routePath` for the raw `r.URL.RawPath`/`r.URL.Path`. If a root-level middleware has already rewritten `rctx.RoutePath` (`middleware/url_format.go:67`, `clean_path.go:23`, `strip.go:28`), the look-ahead path and the path actually routed differ again. I checked this with a Go test: with `r.Use(URLFormat)` on the root, `HEAD /api/hi` reaches the sub-router's HEAD handler, but `HEAD /api/hi.json` still gets the GET handler. This is not a regression, since base gets the GET handler too, and it has no security impact. One sentence in the PR ("look-ahead uses the request URL, so root-level RoutePath rewrites are not reflected") would head off a reviewer's objection.
3. **Not security-relevant.** The worst case in base is a 405 or the GET handler serving a HEAD request, which is availability and correctness only. chi's `SECURITY.md` routes vulnerabilities through GHSA, but nothing here warrants it.

### express-cookie
Verdict: SHIP
Confidence: high
Findings:
1. **Security-direction check.** The fix rounds a positive sub-second `maxAge` up to `Max-Age=1` (`lib/response.js` fixed, lines 770-774), so the cookie lives at most 999 ms longer than the application requested. Base fails closed: the cookie is deleted immediately. The fix fails open by under one second. `Expires` is still `now + maxAge` (`response.js:769`). For any realistic use of a sub-second cookie, a delta under one second has no security meaning, and the PR draft states the rounding explicitly. Not a concern.
2. **No new exceptions.** Only a comparison is added. `maxAge: 0` and negative values still give `Max-Age=0`, so `clearCookie` semantics are untouched (`response.js:714-721` deletes `maxAge` anyway).
3. **Not security-relevant.** Losing a cookie is an availability problem. A public PR is fine, after the issue-first process step.

### otel-urlparser
Verdict: FIX-REQUIRED
Confidence: medium
Findings:
1. **Unbounded `]` search can pull path, query or fragment text into `server.address`.** `getHostEndIndexExclusive` (fixed `UrlParser.java`, lines 111-118, and the same code in the reactor-netty copy, lines 80-87) does `url.indexOf(']', startIndex)` across the rest of the URL. A malformed URL such as `http://[x/p?token=abc]` makes `getHost` return `x/p?token=abc`. OTel instrumentations redact sensitive query parameters in `url.full`, but a query value that ends up in the host attribute bypasses that redaction. Reaching this needs a malformed URL with `[` at the start of the host, so the risk is low. Still, the new code should not widen what can land in `server.address`. Fix: stop the `]` search at the first `/`, `?` or `#` after `startIndex` (or require the closing `]` to come before them), and treat the host as missing otherwise. That matches the bounded `notFound(ipv6End, end)` pattern already used in `HttpServerAddressAndPortExtractor.java:92-100`. Add a test row such as `getHost("http://[::1/path]")` returning null.
2. **Otherwise OK.** No new exceptions: `charAt(startIndex)` in `getHost` is guarded by the `endIndexExclusive == startIndex` early return. `indexOf` is linear, and `getPort` still requires `:` right after `]`.
3. **Not security-relevant as reported.** `"["` as a telemetry attribute is a data-quality bug. There is no `SECURITY.md` in the repo (I did not check the org-level policy). Public PR is fine.

### otel-forwarded
Verdict: SHIP
Confidence: medium
Findings:
1. **Bounded parsing.** The new branch (fixed `ForwardedHostAddressAndPortExtractor.java:87-99`) bounds the `]` search with `notFound(ipv6End, end)`, and `setPort` catches `NumberFormatException` and handles `start == end` (`HeaderParsingHelper.java:16-25`). No new exceptions. This mirrors the existing `for=` parsing in `HttpServerAddressAndPortExtractor.java:92-100`.
2. **Changed validation, noted.** An unterminated `[` now returns `false`, so the extractor falls through to the next header source (X-Forwarded-Host, then `:authority`, then `Host`). Base returned `true` with address `"["`. All of these headers are client-controlled, so an attacker who can send a malformed X-Forwarded-Host could already choose the value. The fall-through does not give an attacker anything new and arguably improves fidelity. Bracket contents are not validated as IPv6 (`[evil.example]` gives `evil.example`), but base already recorded arbitrary Host text, so this is not a new capability. `[]` gives an empty `server.address`. That is a cosmetic difference from the UrlParser fix, which returns null for `[]`. Optional: make them consistent.
3. **Not security-relevant.** Host-header-derived telemetry was attacker-influenced before and after the change. Public PR is fine.

### assertj-percentage
Verdict: SHIP
Confidence: high
Findings:
1. **No new weakness.** `new BigDecimal(value).toPlainString()` (fixed `Percentage.java:64`) is only reached when `value % 1 == 0`. That excludes `Infinity`, since `Infinity % 1` is NaN and takes the fractional branch, and `NaN`, which `checkArgument(value >= 0)` rejects at `Percentage.java:39`. So `BigDecimal(double)` cannot throw here. The largest possible output is about 309 digits for `Double.MAX_VALUE`, which is fine for an assertion message.
2. **Not security-relevant.** It only affects a test library's error message.
3. **Process (not security).** The PR draft already flags the CONTRIBUTING clause "authored 100% of the content". That has to be resolved before submitting, but it is not a code issue.

### calibre-opds
Verdict: FIX-REQUIRED
Confidence: medium
Findings:
1. **The fix is correct and narrows exception exposure.** `from_hex_unicode` (`src/polyglot/binary.py:48-51`) can raise `UnicodeEncodeError`, `binascii.Error` or `UnicodeDecodeError`, and all three subclass `ValueError`, so `except ValueError` catches all of them. The `if not which` guard prevents the `IndexError` on `which[0]`. No new exceptions.
2. **Information leakage in base: none to the client.** An unhandled exception reaches `report_unhandled_exception`, which sends a bare 500 with no traceback (`srv/http_response.py:710-711`). The traceback goes only to the server log (`srv/loop.py:669`). The only effect is that any unauthenticated client who can reach the content server can write traceback spam into the log and force the connection to close. That is log noise, not a vulnerability. The PR draft's "do not call it a security fix" instruction is right, and it matches the maintainer's earlier comment that "None of these are security issues". A public PR is fine.
3. **Must change: include the sibling handlers.** `opds_category` (`opds.py:687`) and `opds_categorygroup` (`opds.py:739`, `745`) call `from_hex_unicode` on path components the same way and hit the same 500. The PR draft already has the "alternative patch" text for this. Send that version. A maintainer who merges the navcatalog-only fix will find the next two with a one-line grep, and fixing one of three identical sites looks careless.

### bionemo-amplify
Verdict: SHIP
Confidence: high
Findings:
1. **No security surface.** This is an offline checkpoint-conversion helper. The change (`models/amplify/src/amplify/state_dict_convert.py:90-92` fixed) only adds `dtype=` and `device=` keyword arguments, which removes a possible device-mismatch exception rather than adding one.
2. **No private-process concern.** NVIDIA's `SECURITY.md` (PSIRT) is for vulnerabilities, and a dtype upcast is not one.

### bionemo-thd
Verdict: SHIP
Confidence: medium
Findings:
1. **New exception escaping to callers (intended), with a distributed side effect the PR should mention.** The new `ValueError` (fixed `models/esm2/collator.py:978-984`) is raised from the collator, which runs on CP rank 0 inside `next(self._iterator)` (`collator.py:579` base, via `__call__` at `collator.py:416`). The other CP/TP ranks are already blocked in `_scatter_batch_to_cp_tp_ranks` (`collator.py:585`), so they hang until the process-group timeout instead of failing quickly. The existing BSHD guard (`collator.py:845-849`) behaves the same way, and a crash plus hang is still better than silent token loss. For a better fix, and at least a note in the PR: validate `pad_sequences_to_be_divisible_by % (2 * cp_world_size) == 0` once at dataloader construction (`dataset.py`, where the default is derived around line 256), so every rank fails together.
2. **Error-message size.** `bad_lengths = seq_lengths[remainders != 0].tolist()` embeds every offending length. A large packed batch could produce a very long error line. Optional: truncate it, for example to the first 10 plus a count. The message also names an internal function ("matching the guard already enforced by the BSHD branch (_process_tensor_bshd)"). That belongs in a code comment, not in a user-facing error. Minor.
3. **No hot-path cost.** `torch.any(...)` in the `if` forces a device sync, but the same function already calls `.item()` on `cu_seqlens_padded[-1]` a few lines later, so this adds no new synchronisation point.
4. **Not security-relevant.** Silent training-data loss is an integrity problem for the model owner's own pipeline, not an attacker-reachable one. Public PR is fine.

## After reading validator READMEs and exec reports

I read the nine evidence READMEs, searching them for security, disclosure, auth and my specific concerns, plus `exec-A.md` and `exec-B.md` in full. None of my verdicts change. Revisions and additions:

- **aiohttp-readuntil.** README "Scope check (security)" (line 44-46) reaches the same in-tree caller analysis independently. Its open question 4 leaves private notice to the THREAT_MODEL owners as Andrew's call. My view: a public PR is appropriate. The multi-byte `readuntil` path is not reachable from aiohttp's own HTTP handling, so under `SECURITY_EXTRA.md`'s bar ("a reproducer that makes an HTTP request") this is not a vulnerability report. Verdict unchanged: SHIP.
- **chi-gethead.** README line 50 notes the limitation only for rewrites *inside* the sub-router. My Go test adds a case: a **root-level** `URLFormat` (and by the same reasoning `CleanPath` or `StripSlashes` on the root) also defeats the fix for paths it rewrites (`HEAD /api/hi.json` gets the GET handler). This is not a regression and has no security impact. Verdict unchanged: SHIP. The known-limitation sentence in the PR should cover both cases.
- **otel-urlparser.** README line 46-47 covers only the *unterminated* `[::1/path` case. My finding is a different case: a `]` that appears later in the path, query or fragment is taken as the end of the host. Exec-B's runs don't exercise that case. Verdict unchanged: FIX-REQUIRED (bound the `]` search to the authority).
- **calibre-opds.** Correction to my initial finding 2: README line 47 says the endpoint is subject to the server's normal auth settings. So "unauthenticated client" should read "any client the server's auth configuration admits". The conclusion (log noise only, not a security issue) stands. Exec-A adds two points I agree with: the patch has **no test**, and exec-A independently observed the two sibling endpoints still returning 500 on the fixed tree. Verdict unchanged: FIX-REQUIRED. Send the alternative patch that covers all three handlers.
- **bionemo-thd.** The README (lines 43-61) confirms reachability only through an explicit config override. It does not discuss the rank-0-raises/other-ranks-hang-in-scatter behaviour, so my finding 1 stands as an addition. Exec-A notes the `recipes/*` copies were not executed. The patch text shows identical hunks, and `check_copied_files.py` in CI would catch any divergence. Verdict unchanged: SHIP. Mentioning the hang in the PR, or adding config-time validation, would improve it.
- **express, otel-forwarded, assertj, bionemo-amplify.** Nothing in the READMEs or exec reports bears on the security questions. Verdicts unchanged. Exec-B raises assertj NaN/Infinity as unverified; my finding 1 there covers it from source: `NaN` is rejected at `Percentage.java:39` and `Infinity` takes the fractional branch.

## Overall summary

- **Private disclosure: none of the nine needs it.** I checked each project's policy in the base checkout: aiohttp `SECURITY_EXTRA.md` + `THREAT_MODEL.md`, chi `SECURITY.md` (GHSA), calibre `SECURITY.md`, bionemo `SECURITY.md` (NVIDIA PSIRT). OTel has no in-repo `SECURITY.md`, and I did not check its org-level policy. The closest calls:
  - aiohttp: a framing bug in a public stream API, not reachable from aiohttp's own HTTP paths.
  - calibre: traceback-in-server-log from any admitted client. No traceback reaches the client (`http_response.py:710-711`).
- **Framing.** None of the PR drafts should use security language. The calibre draft already says so explicitly, which is correct given the maintainer's prior pushback.
- **New weaknesses introduced by the fixes:**
  - One real but low-severity issue: otel-urlparser's unbounded `]` search can place path, query or fragment text into `server.address`, bypassing query redaction on malformed URLs. It should be fixed before submitting.
  - Everything else: bounded work on untrusted input (aiohttp overlap scan is O(seplen) per chunk, fuzzed and timed), no new exception types escaping except bionemo-thd's intentional `ValueError`, and no new information in client-visible errors.

One-line verdicts:
- aiohttp-readuntil: SHIP. Overlap scan is bounded; not security-relevant to aiohttp itself.
- chi-gethead: SHIP. No new weakness; note the RoutePath-rewrite limitation in the PR.
- express-cookie: SHIP. Rounding up extends the cookie's lifetime by under 1 s; harmless.
- otel-urlparser: FIX-REQUIRED. Bound the `]` search to the authority so path/query text can't become the host.
- otel-forwarded: SHIP. Bounded parsing, mirrors the existing `for=` branch.
- assertj-percentage: SHIP. BigDecimal path can't throw given existing validation.
- calibre-opds: FIX-REQUIRED. Cover `opds_category`/`opds_categorygroup` too (and add a test); not a security issue, don't frame it as one.
- bionemo-amplify: SHIP. No security surface.
- bionemo-thd: SHIP. Intentional new `ValueError`; mention that other CP ranks hang in scatter until timeout, and optionally validate at config time and truncate `bad_lengths`.
