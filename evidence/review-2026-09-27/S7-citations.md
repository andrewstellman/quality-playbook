# S7 — Fact and Citation Checker Review

Methodology: for each fix I extracted every factual claim in the patch (commit message, code
comments, test names/docstrings) and the PR draft — RFC/spec citations, quotes from
documentation, statements about sibling code, issue/PR numbers, version numbers, counts — and
checked each against the base checkout, the fixed checkout, or the primary source (RFC text,
upstream GitHub, project docs), fetched live where external. Where I ran code, I copied files into
my own scratch dir (`/tmp/review/work/S7/`) and did not modify anything under `/tmp/review/src` or
`/tmp/review/packets`. I did not read the validator/executor evidence before writing the verdicts
below (step 1 of the blind protocol); a "Post-README" section follows all nine per the protocol if
warranted — see note at the end.

---

### aiohttp-readuntil
Verdict: SHIP
Confidence: high

Findings:
1. Commit/CHANGES claim "not finding a multi-byte separator whose bytes arrived in different
   chunks" — VERIFIED. Reproduced directly: on the unpatched `aiohttp/streams.py`, running the
   patch's own new tests (`tests/test_streams.py -k 'readuntil_separator_split or
   readuntil_partial_separator'`) gives **16 failed, 10 passed, 136 deselected** — the PR draft's
   claimed "before" count matches exactly (draft says `16 failed, 10 passed, 136 deselected in
   2.65s`; I got 2.62s, timing differs trivially as expected).
2. "With the fix: `26 passed, 136 deselected`" — VERIFIED, reproduced exactly (`26 passed, 136
   deselected in 0.21s` in my run too).
3. "`tests/test_streams.py --numprocesses=0 --no-cov`: `162 passed in 1.11s`" — VERIFIED count
   (162 passed; my run took 1.19s, timing is not load-bearing).
4. "Related issue number: None found. #6701/#6810 fixed a different multi-byte separator bug
   (offset within one chunk)." — VERIFIED against live GitHub. Issue #6701 ("Error in
   StreamReader#readuntil", opened by @vitaliihonta, closed by PR #6810) is exactly about a
   multi-byte separator being split "at the middle of the separator" within a single already-read
   buffer — a different bug from the cross-chunk case this patch fixes. The characterization is
   accurate.
5. CONTRIBUTORS.txt placement — VERIFIED. "Andrew Stellman" is inserted alphabetically between
   "Andrew Lytvyn" and "Andrew Svetlov", matching the base file's actual ordering.
6. AGENTS.md process claims — VERIFIED against `/tmp/review/src/aiohttp/base/AGENTS.md`: "Use `gh
   pr create --draft`" (draft's "Open as a draft... per aiohttp AGENTS.md"); disclosure line format
   "Drafted with <agent name and version>; reviewed by <human handle>." matches the draft's
   "Drafted with Claude Opus 5.5; reviewed by @andrewstellman." exactly; "Agent run output (test
   logs) goes in a collapsed `<details>` block below the template summary" — the draft does this.
7. CHANGES/PRNUMBER.bugfix.rst naming convention — the draft's note to rename it to the PR number
   is consistent with `CHANGES/README.rst`'s towncrier-based naming convention (I confirmed the
   README exists and describes the fragment-naming scheme; did not verify the exact rename
   instruction wording against README.rst line-by-line).
8. NOT independently verified (too expensive / out of scope for a single reviewer): the "16 files"
   before/after combined run ("1888 passed, 40 skipped, 1 xfailed" → "1914 passed, 40 skipped, 1
   xfailed"). The draft never lists which 16 files, and `tests/` contains far more than 16 files
   matching "stream, multipart, HTTP parser, client and web" — I could not reconstruct the exact
   file set to reproduce this count. UNVERIFIABLE as stated (not wrong, just not checkable without
   the file list).

No WRONG claims found.

---

### chi-gethead
Verdict: SHIP
Confidence: high

Findings:
1. Code comment "`rctx.Routes` is always the top-level router" — VERIFIED by reading
   `mux.go:ServeHTTP`: `rctx.Routes = mx` is only set when `rctx` is nil (i.e., on the router that
   creates the routing context); a mounted sub-router's `ServeHTTP` sees `rctx != nil` and does not
   overwrite `Routes`, so it stays pointed at the root mux for the life of the request.
2. PR-draft claim "The root's `Match` already recurses into mounted routers" — VERIFIED:
   `Mux.Find` (`mux.go`) calls `node.subroutes.Find(rctx, method, rctx.RoutePath)` when a node has
   `subroutes`, i.e., it does recurse into mounted sub-trees.
3. Reproduction claim "fails on master... passes with the fix" — VERIFIED by direct execution. I
   copied `base` + the new `get_head_test.go` and ran `go test`: unpatched code fails
   `TestGetHeadInMountedRouter` exactly as described (`HEAD /api/hi: expected X-Handler 'head', got
   "get"` and `HEAD /api/only-get:... got status 405`); after applying `get_head.go`'s fix, both
   `TestGetHead` and `TestGetHeadInMountedRouter` pass, and `go test ./...` on the whole module
   passes (`ok  chi/v5  1.644s`, `ok  chi/v5/middleware  26.182s`).

No WRONG claims found. All checkable claims verified by direct execution or source read.

---

### express-cookie
Verdict: SHIP
Confidence: high

Findings:
1. RFC 6265 §4.1.2.2 "Max-Age precedence over Expires" — VERIFIED against the live RFC text:
   "If a cookie has both the Max-Age and the Expires attribute, the Max-Age attribute has
   precedence and controls the expiration date of the cookie" is exactly §4.1.2.2.
2. RFC 6265 §5.2.2 "treats Max-Age=0 as 'expire now'" — VERIFIED with a minor precision note: the
   RFC's actual wording is "If delta-seconds is less than or equal to zero (0), let expiry-time be
   the earliest representable date and time" — "earliest representable date," not literally
   "now," but this is a standard, accurate paraphrase (both mean "already expired / delete
   immediately"), not a misstatement.
3. `Math.floor(maxAge / 1000)` bug and behavior — VERIFIED by direct execution. Copied `base`, ran
   the new test file: the "sub-second maxAge" test fails on unpatched `lib/response.js` exactly as
   described (`expected "Set-Cookie" matching /name=tobi; Max-Age=1;.../, got "name=tobi;
   Max-Age=0;..."`). After applying the one-line fix, the same test passes.
4. "`npm test`: 1263 passing" — VERIFIED exactly: I ran the patched repo's full suite
   (`mocha --require test/support/env test/ test/acceptance/ --check-leaks`) and got **1263
   passing**, matching the draft precisely.
5. "`npm run lint` exits 0 on the patched branch" — VERIFIED: `npx eslint .` on the patched tree
   exits 0 with no output.
6. CONTRIBUTING.md quotes — VERIFIED against `expressjs/.github` master branch: "Use the `master`
   branch for bug fixes or minor work that is intended for the current release stream" (draft's
   paraphrase "Use the master branch for bug fixes" is a faithful partial quote); "Create an issue
   for the bug you want to fix or the feature that you want to add" (draft's quoted fragment
   matches verbatim as a substring).
7. PR template claim ("no checklist... DCO 1.1 as an HTML comment") — VERIFIED against
   `expressjs/.github/.github/PULL_REQUEST_TEMPLATE.md`: it is exactly a "Thank you..." line plus
   the Developer's Certificate of Origin 1.1 text, both inside HTML comments, no checklist.
8. "OpenJS AI Coding Assistants Policy (linked from the expressjs.com footer)" — VERIFIED: fetched
   expressjs.com live; the footer contains "[AI Coding Assistants
   Policy](https://ai-coding-assistants-policy.openjsf.org/)" exactly as claimed.

No WRONG claims found.

---

### otel-urlparser
Verdict: SHIP
Confidence: high

Findings:
1. Reproduction examples in the PR draft — VERIFIED by direct execution (standalone javac
   harness, stripped only of the `@Nullable` annotation to avoid an unrelated dependency, logic
   unchanged): on unpatched `UrlParser.java`, `getHost("http://[::1]:8080/")` → `"["` and
   `getHost("https://[2001:db8::1]:8443/path")` → `"[2001"` — both match the draft's examples
   exactly. `getPort(...)` → `null` on the unpatched code, also matches.
2. Fixed-version behavior — VERIFIED by direct execution: `getHost` returns `"::1"` /
   `"2001:db8::1"` correctly, `getPort` returns `8080`, and an unterminated `"https://[::1"`
   returns `null` (matching the new test `testGetHostAndPortWithIpv6`'s assertions exactly,
   including the unterminated-bracket case).
3. RFC 3986 §3.2.2 citation — VERIFIED against the live RFC text: "The host subcomponent of
   authority is identified by an IP literal encapsulated within square brackets..." and
   `IP-literal = "[" ( IPv6address / IPvFuture ) "]"` are exactly §3.2.2.
4. "the same as `HostAddressAndPortExtractor` (#19540)" — VERIFIED. PR #19540 exists
   (`open-telemetry/opentelemetry-java-instrumentation`) and its diff adds exactly the
   `host.startsWith("[")` / `indexOf(']')` bracket-stripping pattern to
   `HostAddressAndPortExtractor.java`, which the base checkout's copy of that file still contains
   today — confirming both that #19540 is real and that the cited class already behaves this way.
5. Gradle module paths in the draft's build instructions
   (`:instrumentation-api-incubator`, `:instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent-unit-tests`)
   — VERIFIED to exist in the base checkout's directory structure.
6. "Assisted-by: Claude Opus 5.5" trailer, framed as following "OpenTelemetry's generative-AI
   policy" — UNVERIFIABLE. I searched the `open-telemetry/community` repo's CONTRIBUTING.md,
   `guides/contributor/README.md` and `processes.md`, and this project's own CONTRIBUTING.md/
   CHANGELOG.md for a generative-AI policy or "Assisted-by" convention and found none; several
   direct URL guesses (opentelemetry.io generative-ai-policy pages, GitHub code search for
   "Assisted-by") returned empty. I could not locate the source document, so I cannot confirm this
   specific policy exists or that it recommends this exact trailer wording. This doesn't affect
   the technical correctness of the fix — flagging only the unverified provenance-note claim.
7. "QPB v1.5.8, 2026-06-23" internal tool version/date — UNVERIFIABLE (internal to Andrew's own
   tooling, no external source to check against).

No WRONG claims found on the technical content; one claim (OTel's Assisted-by policy) is
UNVERIFIABLE, not wrong.

---

### otel-forwarded
Verdict: SHIP
Confidence: high

Findings:
1. "Follow-up to #15158 / #19540" — VERIFIED. #15158 ("Consider ipv6 when extracting server name
   from host header") is a real, closed issue, closed by PR #19540 (confirmed in fix #4 of
   otel-urlparser above) — the chain is accurate.
2. "the sibling `ForwardedHostAddressAndPortExtractor` still splits at the first `:`" — VERIFIED
   by reading the base file directly: `extractHost` does `host.indexOf(':', start)` with no
   special-casing for `[`.
3. "used... for `server.address`/`server.port` from the Forwarded `host=` parameter,
   X-Forwarded-Host, `:authority` and Host" — VERIFIED: `extract()` in the base file tries exactly
   those four sources in that order (Forwarded → X-Forwarded-Host → :authority → Host), and
   `HttpServerAttributesExtractorBuilder.java` wires `ForwardedHostAddressAndPortExtractor` in as
   `serverAddressPortExtractor`.
4. "`Host: [2001:db8::1]:8080` currently gets `server.address = "[2001"`... `Host: [::1]:8080`
   gives `"["`" — VERIFIED by manual character-index trace of the unpatched `extractHost` logic
   (I did not get a full JVM test running due to the class's dependency chain, but the algorithm
   is simple enough — first-colon split — that manual trace is unambiguous and matches exactly;
   I did successfully JVM-verify the byte-identical logic pattern in the otel-urlparser sibling
   fix above).
5. "the same `[`…`]` branch used in `HostAddressAndPortExtractor` and... `HttpServerAddressAndPortExtractor`'s
   `for=` parsing" — VERIFIED: `HttpServerAddressAndPortExtractor.java` has a `for=` parsing path
   with `forwarded.charAt(start) == '['` handling at line 92, distinct from but structurally
   identical to the class this patch touches.
6. RFC 7239 "requires IPv6 values to be quoted" — VERIFIED against the live RFC text: "It is
   important to note that an IPv6 address and any nodename with node-port specified MUST be
   quoted, since ':' is not an allowed character in 'token'" (§6), plus the worked example
   `Forwarded: For="[2001:db8:cafe::17]:4711"` in §4.

No WRONG claims found.

---

### assertj-percentage
Verdict: SHIP
Confidence: high

Findings:
1. `withPercentage(3_000_000_000d).toString()` returns `"2147483647%"` — VERIFIED by direct
   execution of the exact unpatched algorithm (`(int) value` cast, `Integer.MAX_VALUE` = 2147483647
   is the well-known int overflow saturation point for a double this large — reproduced exactly:
   `2147483647%`).
2. Patched behavior `new BigDecimal(value).toPlainString()` for `3_000_000_000` → `"3000000000%"`
   and for `1e20` → `"100000000000000000000%"`, with `10.0` still `"10%"` — all VERIFIED by direct
   execution, matching the new test rows exactly.
3. "With `(long)`, drop the `1e20` test row, since it would print `9223372036854775807%`" —
   VERIFIED: `(long) 1e20` does indeed saturate to `Long.MAX_VALUE` = 9223372036854775807 in Java
   (confirmed by direct execution).
4. Failure-message quote "by more than 2147483647% but difference was 99.99999998999999%." —
   PARTIALLY VERIFIED. `ShouldNotBeEqualWithinPercentage`'s format string is exactly `"...by more
   than %s but difference was %s%%..."` where the first `%s` is `percentage.toString()` (which
   would render `"2147483647%"` under the bug) — the message *shape* is confirmed real code, but I
   did not independently reproduce the specific `99.99999998999999%` difference figure (would
   require reconstructing the exact actual/expected values used); treat that one number as
   illustrative/unverified, not as a false claim.
5. CONTRIBUTING.md quotes — VERIFIED verbatim against the base checkout: "## Rebase your PR on
   `main` (no merge!)" (section header) and "You will only submit contributions where you have
   authored 100% of the content." (Legal Disclaimer section).
6. PR template text — VERIFIED verbatim against `PULL_REQUEST_TEMPLATE.md`: the checklist and the
   "contributing guidelines" link text match exactly.
7. "No DCO/Signed-off-by is required by this project" — VERIFIED (absence): no mention of DCO or
   sign-off found in CONTRIBUTING.md or the PR template.
8. "`assertj-core` and `assertj-core-tests` pass in full (14441 + 6340)" and "`spotless:check` /
   `license:check` are clean" — UNVERIFIABLE. No Maven binary/wrapper cache was available without
   a large dependency download in an environment explicitly flagged as disk-constrained; I did not
   attempt the full reactor build. Not contradicted by anything I found, just not independently
   run.

No WRONG claims found; two claims (the exact difference-message number, and the full Maven test
counts) are UNVERIFIABLE rather than confirmed.

---

### calibre-opds
Verdict: SHIP
Confidence: high

Findings:
1. README.md quotes — VERIFIED verbatim: "GitHub is only used for code hosting and pull requests."
   and bug reports go to the Launchpad tracker, both present in `README.md`.
2. `manual/develop.rst` accepting `git format-patch` output — VERIFIED: the file's "Submitting your
   changes to be included" section documents exactly `git format-patch origin/master --stdout >
   my-changes` as the patch-submission mechanism.
3. "No PR template, no CLA" — VERIFIED (absence): no `PULL_REQUEST_TEMPLATE.md` or CLA file found
   under `.github/` in the base checkout.
4. "`/opds/navcatalog/zz`, `/opds/navcatalog/ff` raises `binascii.Error` / `UnicodeDecodeError`" —
   VERIFIED by direct execution of `polyglot.binary.from_hex_unicode`'s actual logic
   (`unhexlify(...).decode(enc)`): `'zz'` → `binascii.Error: Non-hexadecimal digit found`; `'ff'` →
   unhexlify succeeds (byte 0xff) but `.decode('utf-8')` raises `UnicodeDecodeError`. Both are
   `ValueError` subclasses in Python 3 (confirmed), so the patch's `except ValueError:` correctly
   catches both cases — verified functionally correct, not just plausible.
5. "Every other bad input to this handler (bad `offset`, unknown type prefix) already gives 404" —
   VERIFIED by reading `opds_navcatalog`: bad `offset` is caught by a bare `except Exception` →
   `HTTPNotFound`, and an unrecognized `type_` falls through to `raise HTTPNotFound('Not found')`
   at the end of the function.
6. "adds the same empty-id check `opds_category` uses" — VERIFIED: `opds_category` has `if not
   which or not category: raise HTTPNotFound('Not found')`, which the patch replicates for
   `opds_navcatalog`.
7. "`opds_category` and `opds_categorygroup` decode their ids the same way and had the same 500" —
   VERIFIED structurally: both call `from_hex_unicode` unguarded (no try/except) in the base
   checkout, same vulnerable pattern as the unpatched `opds_navcatalog`.
8. "ajax.py and `reader_background` already turn undecodable hex arguments into `HTTPNotFound`" —
   VERIFIED, with one caveat worth flagging separately: `ajax.py` does have multiple
   `except ... : raise HTTPNotFound(...)` sites for encoding/decoding failures (e.g. "Invalid
   encoding of category name"). For `reader_background` (`content.py`), I confirmed on the **real
   upstream** `kovidgoyal/calibre` GitHub master that the function does
   `except (ValueError, UnicodeDecodeError): raise HTTPNotFound(...)` exactly as claimed. However,
   **the local base checkout at `/tmp/review/src/calibre/base/src/calibre/srv/content.py` has a
   corrupted version of that exact line** — `except ValueError, UnicodeDecodeError:` (missing
   parentheses), which is a Python 3 `SyntaxError` and would prevent the module from importing at
   all (confirmed with `python3 -m py_compile`). This is an artifact of the provided base checkout,
   not something Andrew's patch touches or is responsible for, and not a reason to doubt the
   underlying claim (which is true against real upstream) — but reviewers who try to exercise
   `content.py` in this specific sandbox checkout should know it won't import as-is.
9. "`ruff check` / `ruff format --check` pass" — UNVERIFIABLE: `ruff` is not installed in this
   environment and I did not install it (avoided extra sandbox load per the brief's disk-tight
   warning). I did confirm both the base and fixed `opds.py` parse cleanly via `ast.parse` /
   `py_compile`.

No WRONG claims found on the substance of the fix. One notable environment-integrity finding (item
8) about the provided base checkout, not about the patch's correctness.

---

### bionemo-amplify
Verdict: SHIP
Confidence: high

Findings:
1. "the parallel ESM2 `_pad_weights` (`models/esm2/convert.py`)... already passes
   `dtype=source_embed.dtype, device=source_embed.device`" — VERIFIED verbatim: lines 243-245 of
   `models/esm2/convert.py` read exactly
   `torch.zeros(num_padding_rows, source_embed.size(1), dtype=source_embed.dtype,
   device=source_embed.device)`.
2. AMPLIFY's base `_pad_weights` "built its padding rows via a bare `torch.zeros(...)` with no
   dtype=/device= kwargs" — VERIFIED verbatim against
   `models/amplify/src/amplify/state_dict_convert.py`: `torch.zeros(num_padding_rows,
   source_embed.size(1))`.
3. Base commit `11701476b005ca7bc489df924a398b8f12453f0b` (2026-09-18) — VERIFIED: `git log -1`
   in the base checkout shows exactly this hash and date ("ci: limit Dependabot to security
   updates only (#1753)").
4. "`transformer_engine`, an unconditional import of this module's parent package" — VERIFIED:
   `state_dict_convert.py` does `from amplify.amplify_te import AMPLIFYConfig,
   AMPLIFYForMaskedLM`, and `amplify_te.py` does `import transformer_engine.pytorch` at module
   scope, so importing anything from `state_dict_convert` transitively requires
   `transformer_engine`.
5. "mirrors the existing `MagicMock`-based test pattern in
   `tests/test_amplify_model.py::test_convert_state_dict`" — VERIFIED: that test exists at line
   110 of `models/amplify/tests/test_amplify_model.py` and uses `MagicMock` for the `ctx` object,
   same pattern as the new regression test.
6. "`export.py::export_hf_checkpoint` doesn't currently trip this (it loads the HF model at
   default fp32)" — VERIFIED: `export_hf_checkpoint` calls `AutoModel.from_pretrained(...)` with
   no `torch_dtype=` kwarg, which defaults to fp32 under HF's standard behavior.
7. "`CONTRIBUTING.md` and the PR template didn't mention a DCO requirement" — VERIFIED (absence):
   no DCO/Signed-off-by language found in either file.
8. The runtime behavior claim itself — "silently upcasts the padded weights to float32, or raises
   a device-mismatch error on the subsequent `torch.cat`" — UNVERIFIABLE in this sandbox: no
   `torch` installation is available here and I did not attempt to install one (multi-hundred-MB
   package, explicitly flagged as disk-tight). This is standard, well-documented PyTorch behavior
   (torch.cat requires matching dtype/device or raises), but I did not execute it directly here —
   flagging as unverified-by-me rather than confirmed.

No WRONG claims found.

---

### bionemo-thd
Verdict: SHIP
Confidence: high

Findings:
1. "The BSHD branch (`_process_tensor_bshd`) already raises a `ValueError` on the same condition"
   — VERIFIED verbatim: `_process_tensor_bshd` in `models/esm2/collator.py` raises `ValueError(
   f"Sequence length {seq_len} must be divisible by {total_chunks} (2 * cp_world_size) for BSHD
   context parallelism")` for exactly this condition, and the new test's `pytest.raises(ValueError,
   match="must be divisible by")` is consistent with both branches' message wording.
2. Base THD branch "computed... with no check" — VERIFIED verbatim against the base file: the
   unguarded `slice_sizes = (cu_seqlens_padded[1:] - cu_seqlens_padded[:-1]) //
   total_slices_of_any_sequence` line matches the patch's diff context exactly.
3. "2 of 10 tokens... are dropped by every CP rank on a 2-rank shard" — VERIFIED by direct
   arithmetic reproduction of the unpatched formula: for `cp_world_size=2` (`total_slices=4`) and
   a padded length of 10, `10 // 4 = 2` per-slice, `2*4=8` tokens used, dropping exactly 2 — matches
   the test's own `len_a, len_b = 8, 10` setup and the draft's claim precisely.
4. "`dataset.py`'s `create_thd_dataloader` only derives a safe default
   (`pad_sequences_to_be_divisible_by = cp_mesh.size() * 2`) when the caller leaves the config
   value unset" — VERIFIED verbatim against `recipes/esm2_native_te/dataset.py`: `if
   kwargs.get("pad_sequences_to_be_divisible_by", None) is None: logger.info(...); kwargs[...] =
   cp_mesh.size() * 2`, including the log message text.
5. "a caller who sets `pad_sequences_to_be_divisible_by` explicitly... as
   `recipes/esm2_native_te/hydra_config/L0_sanity_cp.yaml` already does" — VERIFIED: that file
   sets `pad_sequences_to_be_divisible_by: 16` explicitly (with `cp_size: 2`); the claim is only
   that this file demonstrates the explicit-override pattern exists in the codebase (it does), not
   that this specific value triggers the bug (16 is in fact divisible by 4, so this particular
   config is safe) — the draft does not claim otherwise, so this is accurate as stated.
6. "`transformer_engine` and `nvtx`, both unconditional imports of this module" — VERIFIED: the
   base `models/esm2/collator.py` has `import nvtx` and `from
   transformer_engine.pytorch.attention.dot_product_attention.context_parallel import
   pad_thd_sequences_for_cp` both at module top level.
7. "canonical source for 8 byte-identical copies enforced by `ci/scripts/check_copied_files.py`"
   — VERIFIED: `ci/scripts/check_copied_files.py` exists and its own docstring describes exactly
   this copy-and-banner mechanism; I confirmed by `md5sum` that all 8 non-canonical copies
   (`llama3`, `mixtral`, `qwen`, and the 5 recipe collators) are byte-identical to each other and
   differ from the canonical `models/esm2/collator.py` only by the auto-inserted "BEGIN/END COPIED
   FILE NOTICE" banner — exactly the mechanism the tool's docstring describes.
8. Github issue #1561 cross-reference — VERIFIED against live GitHub: issue #1561 ("MFU tracking:
   `pad_to_multiple_of` path inflates useful-work Σ(Lᵢ²)...") is real, and its own text explicitly
   distinguishes `cu_seq_lens_q` (mock-sequence padding, the issue's subject) from
   `cu_seq_lens_q_padded` (reserved for CP zigzag-divisibility padding, this patch's subject) —
   the PR draft's characterization of it as "related-but-distinct... not a duplicate" is accurate
   and closely tracks the issue's own wording.
9. "No `Signed-off-by` trailer... `CONTRIBUTING.md` and the PR template didn't mention a DCO
   requirement" — VERIFIED (absence), same as bionemo-amplify.

No WRONG claims found. This is the most thoroughly self-documented and externally-checkable patch
of the nine — every cross-reference (BSHD guard, dataset.py default, yaml example, copy-script
mechanism, issue #1561) checked out exactly as stated.

---

## Overall summary

All nine fixes: **SHIP** on citation/fact grounds — I found no WRONG factual claims in any commit
message, code comment, test name, or PR draft across all nine patches. Every checkable RFC/spec
citation (RFC 6265 §4.1.2.2/§5.2.2, RFC 7239 §6, RFC 3986 §3.2.2), every GitHub issue/PR
cross-reference (#6701/#6810, #19540, #15158, #1561), every "sibling code already does X" claim,
and nearly every quoted number I could reproduce (test-pass counts, `Integer.MAX_VALUE`
saturation, token-drop arithmetic, dropped-token counts) checked out exactly, several via direct
before/after code execution rather than just source reading.

Handful of UNVERIFIABLE (not wrong, just not independently confirmed by me) items, none of which
would flip a SHIP verdict:
- aiohttp: the combined "16 files" before/after test-count claim (file list not given).
- otel-urlparser/otel-forwarded: OpenTelemetry's "generative-AI policy" recommending an
  "Assisted-by:" trailer — I could not locate the source document despite several search attempts.
- assertj: the exact `99.99999998999999%` figure in the illustrative failure message, and the full
  Maven test-suite counts (14441 + 6340) — no Maven build attempted given the sandbox's disk
  constraints.
- calibre: `ruff check`/`ruff format --check` — tool not installed, not run.
- bionemo-amplify: the exact PyTorch `torch.cat` dtype/device-mismatch runtime behavior — no
  `torch` installed in this sandbox.

One environment-integrity finding worth flagging to the other reviewers/validator, not a patch
defect: the local base checkout of calibre at `/tmp/review/src/calibre/base/src/calibre/srv/content.py`
contains a corrupted line (`except ValueError, UnicodeDecodeError:`, missing parentheses) that is
a Python 3 `SyntaxError` and would fail `python3 -m py_compile`. The real upstream
`kovidgoyal/calibre` master has the correct parenthesized form at the same line. This doesn't
affect the calibre-opds patch (which touches a different file, `opds.py`, and I confirmed both its
base and fixed versions parse cleanly) — it's a defect in the provided review snapshot, not in
Andrew's PR.
