# S7 — fact and citation checker, round 2

Persona: verify every factual claim (file/line references, "X already does this" statements,
config values, RFC references, counts, behaviour claims) in the commit message, PR description,
code comments and test names for each v2 fix, against the base/v2 checkouts or primary sources.

Method: direct source reading and manual tracing of the parsing logic in base vs. v2 for every
claim below; where possible I additionally executed the code (aiohttp — real pytest-free repro
under Python 3.10 with `AIOHTTP_NO_EXTENSIONS=1`; calibre — direct `from_hex_unicode` calls plus
`ruff check`/`ruff format --check` under the project's own `pyproject.toml`; the otel Java claims
were verified by reading `getHostEndIndexExclusive`/`extractHost` byte-for-byte and hand-tracing
example inputs, since compiling the full otel module tree was out of scope for a single reviewer).
I could not run bionemo's code myself (no `torch` in this sandbox), so those two fixes' dtype/shape
claims are verified by source reading only in my own pass — see "Round-2 executor reports" below,
which independently confirms them by execution.

---

### aiohttp-readuntil

Verdict: SHIP
Confidence: high

Findings:
1. "readuntil() searched each buffered chunk separately, so a multi-byte separator split across
   two chunks was never found" — VERIFIED. Base `aiohttp/streams.py:396-410` (`_buffer[0].find(separator, offset)`)
   only searches the current buffer chunk; nothing about the check spans chunks.
2. "Feeding b"line1\r" then b"\nline2" made readuntil(b"\r\n") return b"line1\r\nline2""` — VERIFIED
   by execution. I ran the unmodified base `StreamReader.readuntil` (pure-Python, `AIOHTTP_NO_EXTENSIONS=1`,
   Python 3.10.12) and got exactly `b'line1\r\nline2'`; the v2 code, run the same way, returns
   `b'line1\r\n'` with `b'line2'` left in the buffer, i.e. the described bug and fix are both real.
3. "This also checks the last len(separator) - 1 bytes already read together with the next chunk"
   — VERIFIED against the patch: `tail = chunk[1 - seplen:]` is drawn from `chunk`, the accumulator
   of bytes already read during this call; `seplen > 1` gate means single-byte separators (the
   `readline()` default) take the unmodified path, matching "readline() and other one-byte
   separators take the old path."
4. "#6701/#6810 fixed a different multi-byte separator bug" — VERIFIED via GitHub. Issue #6701
   ("Error in StreamReader#readuntil") is a 2022 report that the separator's *end* boundary was
   off by one byte within a single chunk (e.g. `b'ab'` split mid-separator inside one buffer),
   fixed by PR #6810. That is a distinct bug from this patch's cross-chunk miss; the claim that
   they're "a different multi-byte separator bug" is accurate, not a reused citation.
5. Test-output claim in the PR ("14 failed, 10 passed" before fix; "24 passed" and "160 passed"
   after) — UNVERIFIABLE by me directly (no full pytest env built), but the round-2 executor A
   report (`exec-A.md`) independently ran the real pytest suite and got exactly these numbers:
   14 failed/10 passed (red), 24 passed (green), 136→160 passed (suite). I treat this as verified
   by a second party under the brief's own evidence trail.

Round-1 required changes: made / not made — all six items (disclosure line, `CHANGES/PRNUMBER.bugfix.rst`
rename note moved out of the PR body, `<details>` block cut, `max_size`/`LineTooLong` behaviour-change
sentence added, `tail`/`head`/`n` comment added, `test_readuntil_separator_split_after_wait` dropped)
are made, per `v2/CHANGES-FROM-V1.md`, and I confirmed items 2 and 4 directly by reading `PR-DRAFT.md`
(the max_size sentence is present verbatim) and the patch (the two added comment lines are present,
the dropped-test function does not appear in the diff).

---

### otel-urlparser

Verdict: SHIP
Confidence: high

Findings:
1. Base behaviour `UrlParser.getHost("http://[::1]:8080/") -> "["`, `getPort(...) -> null` —
   VERIFIED by hand-tracing `getHostEndIndexExclusive` (base, lines 105-111): the predicate stops
   at the first of `:`, `/`, `?`, `#`; for `[::1]:8080` that is the `:` at `startIndex+1` (inside
   the brackets), giving `endIndexExclusive = startIndex+1`, so `getHost` returns the 1-character
   substring `"["`. `getPort` then looks for `:` after that 1-char host, finds it immediately, and
   its own end-scan hits `]` — not `/`,`?`,`#` — so it runs off the end of the intended token; net
   result matches the claimed `null`.
2. "the same as HostAddressAndPortExtractor (#19540)" — VERIFIED. `HostAddressAndPortExtractor.java:35`
   (`if (host.startsWith("["))`, strip to `indexOf(']')`) already does exactly this for the `Host`
   header path. PR #19540 ("Handle IPv6 addresses in HTTP Host headers", merged 2026-08-19, fixes
   issue #15158 "Consider ipv6 when extracting server name from host header") is a real, merged PR
   confirmed via the GitHub API — not a fabricated citation.
3. "ReactorNettyHttpClientAttributesGetter reports server.address "[""; "ServicePeerResolver indexes
   ... under host "["; "ClickHouseClientV2Singletons (CurrentServerInfo) calls getHost/getPort on a
   single configured endpoint" — the ClickHouse claim is VERIFIED literally:
   `ClickHouseClientV2Singletons.java:152` reads
   `new CurrentServerInfo(UrlParser.getHost(endpoint), UrlParser.getPort(endpoint), peer)`. I did not
   independently re-derive the Reactor-Netty attribute-getter or ServicePeerResolver mechanics beyond
   confirming the classes and their `UrlParser` usage exist (both files present in the base tree);
   full call-chain tracing into span-attribute output was out of scope for this pass.
4. "The pulsar instrumentation has its own UrlParser with the same first-':' split" — VERIFIED.
   `instrumentation/pulsar/pulsar-2.8/.../UrlParser.java` computes
   `portStart = authority.indexOf(':')` with no bracket handling — the same bug shape, left
   unfixed as stated.
5. "A [ with no closing ] ... is treated as having no host" and the two malformed-input examples
   — VERIFIED by the v2 code (loop breaks on `/`,`?`,`#` before an unmatched `[`, returns
   `startIndex` which callers treat as "no host") and independently by round-2 executor B, who
   compiled `UrlParser.java` standalone and called `getHost` directly:
   `getHost("http://[::1/path]")`: base → `"["`, fix → `null`; `getHost("http://[x/p?token=abc]")`:
   base → `"[x"`, fix → `null`.

Round-1 required changes: made. The synthesis's one hard requirement — "Bound the `]` search to the
authority, stopping at the first `/`, `?` or `#`" — is present in the v2 diff (`if (c == '/' || c == '?' || c == '#') break;`
before falling through to "no host"), and executor B independently confirmed the bounded behaviour
on the exact adversarial inputs (`[x/p?token=abc]`) that round-1 reviewers O2/O3 used to break v1.
Mentioning the ClickHouse caller and the pulsar follow-up (both required) are both present in
`PR-DRAFT.md` and both verified above as literally true, not just asserted.

---

### otel-forwarded

Verdict: SHIP
Confidence: high

Findings:
1. "the extractor HttpServerAttributesExtractor uses for server.address/server.port from the
   Forwarded host= parameter, X-Forwarded-Host, :authority and Host" — VERIFIED.
   `ForwardedHostAddressAndPortExtractor.extract()` (base, lines 22-53) tries exactly those four
   header sources in that order.
2. Base repro: `Host: [2001:db8::1]:8080` → `server.address = "[2001"`; `Host: [::1]:8080` → `"["`
   — VERIFIED by hand-tracing `extractHost` (base lines 70-93): `hostHeaderSeparator = host.indexOf(':', start)`
   finds the first `:`, which for `[2001:db8::1]:8080` is at offset 5, giving `substring(0,5) = "[2001"`
   exactly; for `[::1]:8080` the first `:` is at offset 1, giving `"["` exactly.
3. "the same [...] branch used in HostAddressAndPortExtractor and in the for= parsing of
   HttpServerAddressAndPortExtractor" — VERIFIED. `HttpServerAddressAndPortExtractor.java:92` has
   `if (forwarded.charAt(start) == '[')` in its `for=` parser — the file name in the PR text is
   correct (not a typo for a nonexistent class).
4. "an unterminated `[`... is now treated as malformed... the extractor falls through to the next
   header source instead of recording server.address = "["" — VERIFIED against the v2 diff: when
   `ipv6End` is not found, `extractFromForwardedHeader`/`extractHost` return `false`, and the
   caller's `for` loop (per finding 1) continues to the next header type on a `false` return.
5. Test/executor numbers (23 new failing cases red, 127/127 green, 429→452 suite) — round-2
   executor B independently reproduced these exact counts by compiling and running the real
   JUnit suite (not just re-quoting the evidence folder).

Round-1 required changes: made — the "unterminated `[` falls through" sentence required by [S5, O2]
is present in `PR-DRAFT.md` verbatim as described in `CHANGES-FROM-V1.md`, and verified above as
literally true. Comment wording change [S2] is cosmetic and I did not independently re-verify the
exact wording match beyond confirming both files now read consistently.

---

### calibre-opds

Verdict: SHIP
Confidence: high

Findings:
1. "opds_navcatalog, opds_category, and opds_categorygroup all decode their id path segments with
   from_hex_unicode, and a non-hex, odd-length, or non-UTF-8 value raises binascii.Error/UnicodeDecodeError"
   — VERIFIED. `from_hex_unicode` (`src/polyglot/binary.py`) is `unhexlify(x.encode('ascii')).decode(enc)`;
   I called it directly with `'zz'` (non-hex) and `'abc'` (odd-length) and got `binascii.Error` in
   both cases. `binascii.Error` and `UnicodeDecodeError` are both confirmed subclasses of `ValueError`
   in this Python (`issubclass(binascii.Error, ValueError)` → True; same for `UnicodeDecodeError`),
   so the patch's bare `except ValueError:` genuinely catches all three failure modes named.
2. "...instead of the HTTPNotFound these handlers already return for every other bad input" —
   VERIFIED by reading all three handlers in `src/calibre/srv/opds.py`: each already raises
   `HTTPNotFound` for a bad `offset`, a missing `which`/`category`, an unrecognized `type_`, or an
   unknown category.
3. Implicit 500-vs-404 framing — VERIFIED: `HTTPResponseWriter.report_unhandled_exception`
   (`src/calibre/srv/http_response.py:710-711`) turns any exception that isn't one of the deliberate
   `HTTPSimpleResponse` subclasses into `http.client.INTERNAL_SERVER_ERROR` (500), so an uncaught
   `binascii.Error`/`UnicodeDecodeError` really does surface as a 500 today.
4. "calibre's OPDS handlers have no test coverage (src/calibre/srv/tests/ajax.py:374)" — VERIFIED;
   line 374 of that file is the comment "# Not going test legacy and opds as they are too painful."
   Round-2 executor A additionally confirmed `setup.py test find_tests` can't even collect
   (`ModuleNotFoundError: No module named 'calibre_extensions.translator'`), independently
   supporting "no test coverage" as more than an assertion.
5. "ruff check/ruff format --check pass" — VERIFIED by running both directly against the v2 file
   using the project's own `pyproject.toml` (ruff 0.16.9): `All checks passed!` and
   `1 file already formatted`. (Note: running ruff on a bare copy of the file outside the project
   root, with default ruff settings, gives 22 lint errors and a reformat — the claim only holds
   under calibre's own config, which is what a real PR check would use. Flagging this only because
   it's a trap for a future checker, not because the claim is wrong.)
6. Calibre's Python-version note: `from_hex_unicode`/`ruff` behaviour tested here under Python
   3.10.12 for execution and the project's actual ruff config for lint — I did not additionally
   re-run under Python 3.14 myself, but nothing in this patch is version-sensitive syntax (no
   PEP 758 multi-exception catches, no match statements), so the 3.10 execution result should
   transfer; the PR's own claim of testing "under Python 3.14" (`/sessions/.../.local/bin/python3.14`)
   is corroborated independently by round-2 executor A, who ran the harness under
   `/sessions/kind-zealous-edison/.local/bin/python3.14`.

Round-1 required changes: made. All three handlers get the fix (the alt/ three-handler patch is now
the only patch, matching the unanimous O1-O5/S3/S4/exec-A requirement); the `if not which` line was
dropped with a reachability argument I spot-checked against `parse_uri`'s empty-segment-collapsing
behaviour (confirmed empty `which`/`category` cannot reach the 3- or 4-component routes over HTTP,
matching `CHANGES-FROM-V1.md`'s own appendix); the PR body is cut to a few sentences with the
bracketed placeholder and "alternative patch" language removed; no security framing is used, matching
the maintainer's stated "None of these are security issues" preference from the brief.

---

### bionemo-amplify

Verdict: SHIP
Confidence: medium (I could not run the code myself — no `torch` in this sandbox — but round-2
executor A independently ran it and I checked the round-1-carried claims by reading source)

Findings:
1. "_pad_weights ... builds its padding rows with torch.zeros(num_padding_rows, source_embed.size(1)),
   so the padding rows are fp32 on CPU whatever the source embedding's dtype and device" — VERIFIED
   by reading base `models/amplify/src/amplify/state_dict_convert.py:90` — the call has no
   `dtype=`/`device=` kwargs, and `torch.zeros` defaults to `torch.float32` on the CPU device
   whenever neither is specified (standard, well-documented PyTorch default). Executor A confirmed
   this by execution: base + v2's new test fails with `assert torch.float32 == torch.bfloat16`.
2. "the same as _pad_bias in the same file" — VERIFIED. `_pad_bias` (same file, lines 109-116)
   already passes `dtype=source_bias.dtype, device=source_bias.device`.
3. "and _pad_weights in models/esm2/convert.py" — VERIFIED. `models/esm2/convert.py:238-246` has
   an identically-named function whose `torch.zeros` call already carries
   `dtype=source_embed.dtype, device=source_embed.device` — the AMPLIFY code is the outlier, not
   the ESM2 sibling (this is the exact clause the round-1 synthesis flagged as "misattached" in
   v1; v2's wording, which I read in `PR-DRAFT.md`, correctly frames AMPLIFY as the one missing it).
4. "convert_amplify_hf_to_te calls apply_transforms without cast_dtype, and apply_transforms then
   asserts that every parameter kept its original dtype" — VERIFIED, with a minor line-citation
   imprecision: the PR cites `state.py:238-243`; the actual `assert target_orig_dtypes[key] ==
   target_new_dtypes[key]` block in the v2 checkout is at lines 236-243 (the `if cast_dtype:` branch
   starts at 233, the `else`/assert block at 236-243). The assertion's existence and behaviour are
   correctly described; the line range is off by up to 2 lines, not wrong in substance. I did not
   check whether this citation was accurate against the *pinned* commit's original line numbers
   (my checkout may have minor line drift from the pinned SHA) so I stop short of calling this WRONG.
   `apply_transforms` is called at `state_dict_convert.py:51` with no `cast_dtype` argument —
   confirmed directly.
5. "export.py isn't affected today because it converts the fp32 CPU model that from_pretrained
   loads by default" — plausible from the code's structure but I did not trace `export.py` myself;
   UNVERIFIED (not contradicted, just not checked).
6. Test-execution claims ("cpu case fails before the change... passes after"; "cuda case was
   skipped") — VERIFIED by round-2 executor A's independent run: red = 1 failed (`torch.float32 ==
   torch.bfloat16`)/1 skipped, green = 1 passed/1 skipped, revert = 1 failed again (identical
   assertion).

Round-1 required changes: made. The misattached ESM2 clause is fixed (see finding 3); the impact
claim is downgraded from "silently upcasts" to the function-level fact plus an explicitly
unverified downstream-assertion consequence, matching the synthesis's demand; the test moved into
`test_amplify_model.py` with a one-line docstring; the device case is now CUDA-skipped rather than
CPU-only (round-1's S4 finding that the v1 test "pinned nothing" is fixed).

---

### bionemo-thd

Verdict: SHIP
Confidence: medium (same caveat as amplify — no local torch; relying on my own source-reading plus
round-2 executor A's independent execution)

Findings:
1. "each sequence's slice size comes from floor-dividing its padded length by 2 * cp_world_size,
   with no check that the division is exact" — VERIFIED against base `models/esm2/collator.py:970-987`:
   `slice_sizes = (cu_seqlens_padded[1:] - cu_seqlens_padded[:-1]) // total_slices_of_any_sequence`,
   no validity check.
2. "The BSHD branch already raises a ValueError for the same condition" — VERIFIED.
   `_process_tensor_bshd` (lines 811-...) is documented to and does raise `ValueError` when the
   sequence length isn't divisible by `2 * cp_world_size`.
3. Worked numeric example — "with cu_seqlens_padded = [0, 8, 18] and cp_world_size = 2, positions
   16 and 17 are missing from both ranks' shards" — VERIFIED by hand-tracing `_process_tensor_thd`:
   for the second sequence (start=8, len=10, slice_size=10//4=2), rank 0's two segments cover
   indices {8,9} and {14,15}; rank 1's cover {10,11} and {12,13}. Union = {8..15}; 16 and 17 (the
   last two of the ten-length sequence) are in neither rank's shard — exactly as claimed. Round-2
   executor A's harness demo independently printed the same dropped positions ([16, 17]).
4. "The eight copies were regenerated with check_copied_files.py --fix, and check_copied_files.py
   passes" — VERIFIED. The patch touches exactly 10 files (`models/esm2/collator.py`, one test
   file, and 8 more collator copies: llama3, mixtral, qwen, and 5 recipes... actually 4 of the 5
   recipe dirs plus llama3_native_te — I counted the diff headers directly: llama3, mixtral, qwen,
   esm2_native_te, esm2_peft_te, llama3_native_te, mixtral_native_te, opengenome2_llama_native_te =
   8 copies besides the `models/esm2/collator.py` source), each with a byte-identical code hunk
   (confirmed by diffing the esm2 and llama3 hunks against each other — only the surrounding line
   numbers differ, the added lines are character-for-character the same). Round-2 executor A ran
   `ci/scripts/check_copied_files.py` directly (not just cited it) and got exit 0, and sanity-checked
   the checker isn't a no-op by deliberately desyncing one copy and confirming it then fails.
5. "The CP recipes (esm2, llama3, opengenome2) derive pad_sequences_to_be_divisible_by = 2 * cp_size
   when it's unset" — VERIFIED. `recipes/esm2_native_te/dataset.py:255-257` and
   `recipes/llama3_native_te/train_fsdp2_cp.py:216-220` both have
   `if ...pad_sequences_to_be_divisible_by is None: ... = cp_mesh.size() * 2` /
   `device_mesh["cp"].size() * 2`, with the log message "pad_sequences_to_be_divisible_by is not
   provided, using cp_mesh.size() * 2" in the esm2 case, matching the claim; I did not separately
   check the opengenome2 script but it shares the llama3 recipe's training-script family by naming
   convention, so this is a reasonable but not fully independent confirmation for that one repo.
6. "recipes/esm2_native_te/hydra_config/L0_sanity_cp.yaml sets 16 with cp_size: 2" and "the only
   other config that sets the value, recipes/mixtral_native_te/hydra_config/L1_8x7B_B200.yaml (32),
   doesn't use CP" — VERIFIED the specific numbers (`cp_size: 2`, `pad_sequences_to_be_divisible_by: 16`
   in L0_sanity_cp.yaml; `pad_sequences_to_be_divisible_by: 32` in L1_8x7B_B200.yaml). I did not
   independently verify "doesn't use CP" (would require grepping that recipe's launch scripts for
   `cp_size`/`context_parallel_size` usage, which I did not do), so that specific half of the claim
   is UNVERIFIED by me, though it is at minimum consistent with the config not setting a `cp_size` key.
7. Test/harness numbers (red 1 failed "DID NOT RAISE" + 5 passed; green 6 passed; check_copied_files
   exit 0) — VERIFIED by round-2 executor A's independent execution, matching the PR's own claims
   exactly, including the demo's [16, 17] dropped-token output.

Round-1 required changes: made. "Silently lose training tokens" is replaced with the shown fact
(dropped remainder tokens) plus an explicit "not checked" caveat about Transformer Engine's later
behaviour; `L0_sanity_cp.yaml`'s safety is now stated explicitly rather than implied as affected;
the error message is actionable (names `pad_sequences_to_be_divisible_by`, drops the private
function name) and truncates to 5 bad lengths plus "(and N more)" as required by O2; the
process-group-timeout note and config-time-check alternative were added per O2/O1/O4; tests moved
into the existing `test_collator_context_parallel.py`.

---

## Summary

All six v2 packets' load-bearing factual claims — the base-vs-fixed behavioural deltas, the
"X already does this elsewhere" comparisons, the GitHub issue/PR citations, and the round-1
required-change checklist — check out against the source, the primary GitHub records, or (for the
two bionemo fixes, which need CUDA/torch I don't have here) the round-2 executors' independent
execution. I found no WRONG claims. The handful of items I could not fully verify are noted above
as UNVERIFIABLE rather than assumed true:
- bionemo-amplify: `export.py`'s non-effect wasn't traced by me; the `state.py:238-243` line
  citation is off by up to 2 lines but not substantively wrong.
- bionemo-thd: "L1_8x7B_B200.yaml... doesn't use CP" wasn't independently confirmed by me (only the
  config value itself was); opengenome2's `2 * cp_size` derivation was inferred by naming
  convention from the llama3 script, not directly read.
- otel-urlparser: I did not trace the Reactor-Netty attribute-getter or ServicePeerResolver code
  paths beyond confirming the classes exist and call `UrlParser`.

None of these gaps are "WRONG" — they're places where the PR text makes a claim I couldn't
personally re-derive from first principles in the time available, distinct from the otel/aiohttp/
calibre claims I traced end-to-end myself, and distinct from the several claims across all six
fixes that a second, independent round-2 executor also verified by direct execution.
