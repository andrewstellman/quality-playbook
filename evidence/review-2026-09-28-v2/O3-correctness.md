# O3: correctness adversary, round 2 (v2 patches)

Scratch work: `/tmp/review/work2/O3/` (`aio/` for aiohttp, `otel/` for UrlParser, `thd/` for the THD model). Each finding is labelled **EXECUTED** (I ran code) or **REASONED** (read only). No torch in this sandbox, so neither bionemo fix was executed by me beyond a numpy model of the THD index arithmetic. I confirmed with `diff -rq` that each `v2-*` tree differs from `base` only in the files the patch touches.

---

## Step 1: initial verdicts (formed from the packet and source only)

### aiohttp-readuntil
Verdict: SHIP
Confidence: high
Findings:
1. **EXECUTED: differential fuzz, 80,000 cases, 0 mismatches.** `aio/fuzz.py` checks the v2 `StreamReader.readuntil` against a reference (`data.find(sep)`), with random separators of 1–5 bytes over small alphabets (`ab`, `abc`, `\r\n`, `a`) so that self-overlapping separators and false starts are common. Chunks are 1–4 bytes. `max_size` is random, and the reference raises `LineTooLong` iff `len(line) > max_size`. Each case makes up to 40 repeated `readuntil` calls on the same stream. Half the cases feed data after the reader is already waiting, which is the interleaving that the dropped `_waiter` test used to cover. Seeds 1 (30k) and 7 (50k) both pass. As a sanity check, the same fuzz on `base` fails at once (`sep=b'ababb'` split over 5 chunks returns data past the separator).
2. **REASONED: the new index arithmetic holds at its boundaries.** `tail` and `head` are each at most `seplen-1` bytes long. Any match in `tail+head` therefore starts inside `tail` (`ichar < len(tail)`), so `n = ichar + seplen - len(tail)` lies in `[1, seplen-1]`. `n` can never be 0, which matters because `_read_nowait_chunk(0)` would read nothing and spin. A straddling match always ends before any match wholly inside `buffer[0]`, so the loop still stops at the *first* separator. If `head` is shorter than `seplen-1` (a separator spread over 3 or more chunks), the straddle check misses. That is correct: the whole short chunk is consumed, `chunk` grows, and the next iteration's `tail` covers it (fuzz-covered).
3. **REASONED: other callers and sibling paths are fine.** `readline()` passes `b"\n"`, and `seplen > 1` gates the new code, so one-byte separators run the exact old path. `unread_data` (deprecated) resets `_buffer_offset` before `appendleft`, so `offset` is still valid. `feed_data` rejects empty chunks, so `buffer[0]` is never `b""`. `EmptyStreamReader` has no `readuntil` (a TODO at `streams.py:673`). `multipart.py` does its own boundary windowing and is not this bug. I found no other copy of the per-chunk `find` loop.
4. **EXECUTED: the PR's red count is accurate.** I re-implemented the 24 new test cases outside pytest (`aio/newtests.py`). On base, 14 fail and 10 pass, matching the PR. On v2, all 24 pass.
5. REASONED, cosmetic: `CHANGES/PRNUMBER.bugfix.rst` has to be renamed once the PR number exists. Everything else in the PR text is accurate, including the `max_size` behaviour change.

### otel-urlparser
Verdict: SHIP. Gradle/spotless and EasyCLA still have to happen on the Mac, but those are process steps, not correctness.
Confidence: high
Findings:
1. **EXECUTED: the bounded `]` search works.** I compiled the v2 incubator `UrlParser` standalone (`otel/T.java`, JDK 25) and compared it with `java.net.URI`:
   - `http://[::1]:8080` gives `::1`/8080.
   - `http://[::1/p` and `http://[` give null.
   - `http://[::1]x:80` and `http://[::1]]:80` give host `::1` with port null. URI rejects both, so this is lenient but harmless.
   - `http://[::1]#f` and `?q` give `::1`.
   - `http://[fe80::1%25eth0]:80/` gives host `fe80::1%25eth0`. The zone ID is still percent-encoded, which matches URI's raw form.
   Query or path text can no longer reach the host, which was the round-1 defect.
2. EXECUTED, minor and not blocking: `http://[]:80/p` gives host null but port 80 and path `/p`. In `ServicePeerResolver.addMapping`, a peer of `[]:80` would be indexed under a `null` host key with port 80. That was already reachable on base through other malformed peers (for example `https://::1` gives a null host there too), so nothing new, and the input is garbage. `getHostEndIndexExclusive` could return `startIndex` for `[]` to make all three getters agree, but I wouldn't hold the PR for it.
3. EXECUTED, pre-existing, correctly not claimed: `http://user@[::1]:80/` still gives host `user@[`. Base gives the same, and userinfo is broken for IPv4 too (`user:pw@host` gives host `user`).
4. **REASONED: I checked every caller.** The callers are:
   - `ServicePeerResolver` (getHost/getPort/getPath on `"https://" + peer`)
   - `HttpClientServicePeerAttributesExtractor` (getPath on `url.full`)
   - `RestTemplateInstrumentation` (getPath on `uriTemplate`)
   - `ClickHouseClientV2Singletons` (getHost/getPort)
   - `ReactorNettyHttpClientAttributesGetter` (reactor copy)

   The only behaviour change for a well-formed URL is the intended one. The one getPath change affects malformed URLs only: `http://[x/p...` used to give path `/p` and now gives null. For `http://[::1]:8080/path`, getPath gives `/path` on both base and v2. For a bracketed `[::1]:8080` peer, `ServicePeerResolver` now adds an exact-address entry and a host entry under `::1` (`peer.equals(host)` is false). `hasMultipleEndpoints` does not misfire, because `ADDRESS_GROUP_PATTERN` only matches `(address=`.
5. REASONED: the two copies are identical in the patched regions. Pulsar is disclosed as a follow-up, which is right.

### otel-forwarded
Verdict: SHIP. Gradle/spotless and EasyCLA remain Mac-side.
Confidence: high
Findings:
1. **REASONED: mirrors the upstream sibling.** The new branch matches `HostAddressAndPortExtractor.java:35-45` (the #19540 code) line for line. The only difference is that it respects the `[start, end)` window through `notFound(ipv6End, end)`, which is needed because the Forwarded path passes a sub-range. That bound is correct: a `]` beyond `;` counts as not found, so the value is malformed and the extractor falls through.
2. REASONED: boundaries. `host="[::1]"`, after quote stripping, gives `start+1 .. quoteEnd` and the bracket branch works inside it. `[::1]` then `end` means no port. `[::1]:` sends `setPort` an empty range and it returns. `[::1]:port` hits a NumberFormatException, which is ignored. `[]` sets `server.address=""`, the same as `HostAddressAndPortExtractor`, so it is consistent, if not ideal. A multi-element `Forwarded: host=[::1]:80, for=x` makes `setPort` try `"80, for=x"`, which fails, so there is no port. That is the same pre-existing limitation as for IPv4 (`end` stops only at `;`).
3. REASONED: the executor's 23 red / 23 revert failures match the claim, and the attribute-level test pins `server.port`. I found no other caller to break: the class is package-private and used by `HttpServerAttributesExtractor`.

### calibre-opds
Verdict: SHIP
Confidence: high
Findings:
1. **EXECUTED: `except ValueError` covers every failure mode of `from_hex_unicode`** (`polyglot/binary.py:48-51`). Non-hex, odd-length, whitespace and `0x` prefixes raise `binascii.Error`. Invalid UTF-8, including surrogate bytes `eda080`, raises `UnicodeDecodeError`. A non-ASCII path segment such as `é` raises **UnicodeEncodeError**, from `.encode('ascii')`. The PR doesn't list that case, but it is still a `ValueError`, so it is covered (Python 3.10 run).
2. REASONED: no remaining crash on empty input. `parse_uri` (`http_request.py:94`) drops empty segments, so `which` and `category` are never `''` over HTTP. Hex of even length that isn't empty always decodes to at least one character, so `which[0]` can't raise an IndexError after the fix. That makes dropping v1's `if not which` safe.
3. REASONED: I found no other `from_hex_unicode` call site in `srv/`, apart from the two in `srv/tests/content.py` on server-generated headers. All three handlers are covered.
4. REASONED, residual and out of scope: decoded ids can contain control characters (for example hex of `"N\x01"`). The paths I followed end in 404 (`category not in categories`, `not items`). I did not exhaustively check whether an XML-illegal character could reach lxml in `opds_category`'s `search` branch. It is not part of this fix.

### bionemo-amplify
Verdict: SHIP
Confidence: medium. The CUDA half and the end-to-end conversion were not run by anyone.
Findings:
1. REASONED: the change is right and complete. `_pad_weights` is used undecorated and then wrapped twice (`_pad_embeddings`, `_pad_decoder_weights`), and `io.state_transform(...)(fn)` returns a new `StateDictTransform` without mutating `_pad_weights`. So the test's direct call exercises the same body both transforms use. I grepped for sibling `_pad_weights` definitions: `models/esm2/convert.py:238` and `recipes/vllm_inference/esm2/convert.py:244` already pass dtype and device, and I found no other padding helper with the bug. `num_padding_rows == 0` works (`zeros(0, d)`). A negative count errors exactly as before.
2. REASONED: the PR's impact claim now matches the code. `state.py:238-243` asserts that dtypes are unchanged when `cast_dtype` is falsy, so a bf16 model with a bf16 target would fail loudly on base, not silently upcast. Mixing CUDA and CPU in `torch.cat` with 2-D tensors raises. Both are presented as "not run".
3. REASONED: `test_amplify_model.py` already imports `MagicMock` and `pytest`. The `cuda` parametrization is skip-guarded. The test still sits in a module that imports `transformer_engine`, so it runs only in NVIDIA's GPU CI. That is fine: CI is the gate there.

### bionemo-thd
Verdict: SHIP
Confidence: medium. Multi-rank behaviour was not run.
Findings:
1. **EXECUTED: a numpy model of `_process_tensor_thd`'s index arithmetic** (`thd/`):
   - `[0,8,18]`, cp=2: tokens 16 and 17 are missing. The guard flags `[10]`, as the PR says.
   - `[0,16,32]`, cp=3: 8 tokens are missing, and the guard flags `[16, 16]`.
   - `[0,0,8]`: a zero-length sequence passes, since `0 % n == 0`.
   - `[0,12,24]`, cp=3: clean.
2. **REASONED: I found no caller that produces a non-divisible length on a config that works today.**
   - The only producer of `cu_seq_lens_q_padded` is `DataCollatorWithFlattening._pad_sequences_to_be_divisible_by`, via TE's `pad_thd_sequences_for_cp` (one site per copy, `collator.py:224/230`).
   - The `pad_to_multiple_of` path appends a mock tail sequence of arbitrary length but never sets `cu_seq_lens_q_padded`, so THD+CP on that path already raised "cu_seqlens_padded is required" before this patch.
   - `cp_world_size <= 1` returns before the new check, so TP-only meshes (cp=1) are unaffected. Without that early return, cp=1 would have demanded even lengths.
   - Existing THD split tests use `divisibility_factor = 2 * cp_size`, or length 8 with cp=2, or `pad_divisor=32` with cp=2 (`llama3/tests/test_cp_thd.py`). I found none that the guard would newly break. I could not run them (no TE).
3. REASONED: every copy is covered. `grep total_slices_of_any_sequence` finds exactly the 9 patched files, and I found no other THD splitter in `recipes/` (codonfm, geneformer, evo2 and vit don't have one).
4. EXECUTED, cosmetic: the message lists lengths with repeats (`[16, 16]`). Wrapping `bad_lengths` in `sorted(set(...))` would make the message clearer. Not blocking.
5. REASONED, accepted and disclosed: the failure is data-dependent, so a bad config fails on the first batch that contains an offending length, not at startup. When rank 0 raises, the other ranks hang until the process-group timeout. The PR states both and offers a config-time check.

---

## Step 2: round-1 required changes (after reading SYNTHESIS.md, each CHANGES-FROM-V1.md, exec-A.md, exec-B.md)

### aiohttp-readuntil
- One disclosure line in AGENTS.md form: **made**. It is the last line of the PR: `Drafted with Claude Opus 5.5; reviewed by andrewstellman.` That matches `AGENTS.md:55`.
- Rename `PRNUMBER.bugfix.rst`: **not made (deferred, correctly).** It can't be done before the PR exists.
- Cut `<details>` to one short block: **made** (three result lines).
- State the `max_size` behaviour change: **made** ("a line that exactly fits `max_size` but whose separator is split across chunks is now returned").
- Comment on the tail/head/n arithmetic: **made** (`streams.py` +3 comment lines). My finding 2 confirms the comment is accurate.
- Drop the `_waiter` test: **made**. My interleaved fuzz covers the waiting-reader path the dropped test used to cover. That fuzz isn't in the patch, which CHANGES-FROM-V1 acknowledges.

### otel-urlparser
- Bound the `]` search at `/ ? #` and add a `[::1/path]` null row: **made.** The patch has both rows plus `[x/p?token=abc]`. I confirmed it by running the code (finding 1), and so did exec-B.
- Gradle, spotless, HTML comment, EasyCLA: the HTML comment removal is **made**. Gradle/spotless is **not made** (exec-B used javac and JUnit only). EasyCLA is Andrew's step.
- Mention the ClickHouse caller: **made**. Mention pulsar as a follow-up: **made**. Mention that `getPort` now returns the port: **made**.

### otel-forwarded
- Gradle `:instrumentation-api:check` with spotless: **not made** (still pending on the Mac).
- Remove the HTML comment and keep `Assisted-by:`: **made** (the trailer is in the patch).
- EasyCLA: Andrew's step.
- Mention the unterminated `[` fall-through: **made** (its own PR paragraph).
- Clearer comment: **made**. The new comment departs from the terse house wording at `HttpServerAddressAndPortExtractor.java:91`. That's a style choice, not a correctness problem.

### calibre-opds
- Send the three-handler version: **made** (all three handlers are in the single patch).
- Drop `if not which`: **made** (the patch adds no such line; my finding 2 confirms it's unreachable).
- Delete the placeholder: **made**.
- About three sentences, no security framing: **made, loosely.** It is three sentences, but the first runs to roughly 70 words. No security framing.

### bionemo-amplify
- Correct the impact claim to the function-level fact and the `state.py:238-243` assertion: **made**.
- Fix the misattached ESM2 clause: **made** (the commit message now reads "as `_pad_bias` in the same file and the ESM2 `_pad_weights` already do").
- Use the repo template and remove provenance, third-person text, the README pointer and the DCO note: **made**.
- Move the test into `test_amplify_model.py` with a short docstring: **made**. No new file, so the header year doesn't apply.
- Device assertion that pins nothing: **made.** There is now a CUDA-skipped case, and the PR says the device half hasn't been run.

### bionemo-thd
- Replace "silently lose": **made** (the text shows positions 16 and 17 and says TE's downstream handling was not checked).
- `L0_sanity_cp.yaml` is safe, and the change guards overrides: **made**. I checked that 16 with `cp_size: 2` is divisible by 4.
- Actionable message without the private name: **made**.
- Rank-0 hang and config-time alternative: **made**.
- Behaviour-change warning: **made**.
- Template, tests moved, commit trimmed: **made** (tests are in `test_collator_context_parallel.py`, and the commit body is 5 lines).

### Change of mind after reading
None. The executor reports agree with what I found, with no discrepancies: aiohttp 14/10, then 24, then 160. The executors ran the otel fixes with javac and JUnit, not Gradle, and ran bionemo in harnesses that need no TE.

---

## Overall
All six v2 patches hold up against adversarial inputs. The only regression-class defect from round 1 (otel-urlparser's unbounded `]`) is fixed, and I verified the fix by running it. I found no new wrong or newly-wrong behaviour in any fix. The remaining nits are all optional:
- otel-urlparser: `[]:80` gives host null but port 80.
- otel-forwarded: `[]` gives an empty address, matching the upstream sibling.
- bionemo-thd: the error message repeats lengths.

Not verified by me: Gradle/spotless for both otel fixes, anything that needs CUDA or Transformer Engine (both bionemo fixes), and the full aiohttp suite (the executors ran it: 160 passed).

| Fix | Verdict |
|---|---|
| aiohttp-readuntil | SHIP (high). 80k-case differential fuzz clean; rename the news fragment after the PR number exists |
| otel-urlparser | SHIP (high). Bounded `]` verified; Gradle and EasyCLA still pending |
| otel-forwarded | SHIP (high). Mirrors #19540 with correct range bounding; Gradle and EasyCLA pending |
| calibre-opds | SHIP (high). `ValueError` catches every decode failure, including UnicodeEncodeError |
| bionemo-amplify | SHIP (medium). Correct and complete across siblings; CUDA half unrun |
| bionemo-thd | SHIP (medium). No working config newly breaks; multi-rank behaviour unrun |
