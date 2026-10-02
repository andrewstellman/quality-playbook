# Non-Linux historical finding triage — 27 September 2026

**Best next investment: aiohttp `StreamReader.readuntil` split-delimiter handling.** Exact current upstream code reproduced the defect. Flatted Python is a second, lower-confidence lead because its test suite embeds behavior that conflicts with the JavaScript reference. Most other tractable historical leads already have public reports or pending fixes. No upstream communication occurred.

## Scope and evidence level

Screened headings and summaries from **112 non-Linux `repos/**/quality*/BUGS.md` files**, covering archive (14), chi (3), express (2), qpb-ff (1), secbench (10), secbench-2 (26), secbench2 (23), and secbench2_widenet (33). There are 105 distinct report content hashes; these are **report counts, not distinct bug counts**. [Complete inventory](artifact-paths.txt), [screen extraction](screening.txt), [metrics](evidence/screen-metrics.json). Read the selected reports in depth; did not adjudicate every individual finding. Deduplicated selected defects by behavior/root cause; older chi versions repeat the same findings.

Eight surviving candidates across six projects were assessed, plus one fixed negative. Six defects across four projects were freshly demonstrated by **actual implementation execution** (three chi, one shell-quote, one flatted, one aiohttp). Minimatch and defu were source-only checks; Immutable was a current-source fixed check. No simplified modeled harness was counted as reproduction. New execution establishes specific behavior, not all environments or configurations; there is no fresh patch/green verification in this first pass.

Current source came from fresh shallow clones under `repos/validation-2026-09-27/nonlinux/`. [Exact revisions and commit dates](evidence/upstream-revisions.json), [environment and Python dependency versions](evidence/environment.txt), [machine-readable candidate records](candidates.json). Historical checkout HEADs are recorded separately and are **not proven discovery revisions**. macOS 26.3 arm64, Go 1.26.4, Node 26.3.1, Python 3.14.6. Existing runs, frozen benchmarks, and `docs/research/catalog` were unchanged.

## Ranked new-submission prospects

| Priority | Finding | Fresh validation | Disclosure / practicality |
|---|---|---|---|
| 1 | **aiohttp BUG-006:** delimiter crossing buffered chunks is missed | Actual current implementation; same bytes, different segmentation | No exact issue found in focused search of 23 `readuntil` results. Related older multi-byte fix exists. Active development and explicit contributor workflow; prepare focused regression/fix next. |
| 2 | **flatted Python BUG-002:** equal but distinct objects become aliases | Actual current Python implementation + actual JS control | No exact issue found in focused Python searches. **Intent unresolved:** Python's own test expects equality dedup. Discuss compatibility/contract before presenting as unequivocal bug. |
| 3 | **chi BUG-002:** `SupressNotFound` mutates live route context | Actual current implementation duplicates RoutePattern | Same mutable-context mechanism publicly reported in [issue #939](https://github.com/go-chi/chi/issues/939) with [open PR #940](https://github.com/go-chi/chi/pull/940). Useful additional regression, not strong novelty. |

### 1. aiohttp: confirmed current behavior, potentially unreported boundary case

Historical evidence: [BUG-006](../../../../repos/secbench2_widenet/wn-py-09-aiohttp/quality/BUGS.md). Fresh commit **`25f30573cc01da08f5b962128eebb16b9701ada3`**. The [documented API](https://github.com/aio-libs/aiohttp/blob/25f30573cc01da08f5b962128eebb16b9701ada3/docs/streams.rst#L82) reads until a byte sequence. [Current implementation](https://github.com/aio-libs/aiohttp/blob/25f30573cc01da08f5b962128eebb16b9701ada3/aiohttp/streams.py#L398) searches each deque element separately and never tests bytes spanning their boundary.

[Reproducer](evidence/repro-aiohttp.py), [output](evidence/aiohttp-actual.log): feeding one `b'abc\r\nrest'` returns `b'abc\r\n'` and retains `b'rest'`; feeding `b'abc\r'`, then `b'\nrest'` returns **all** `b'abc\r\nrest'` and retains nothing. Both streams receive EOF. This executes fresh upstream `StreamReader`, imports confirmed source path, and does not copy or reimplement its algorithm. It uses pure Python mode; no HTTP parser or C extension executes.

Expected behavior is supported by the documented stop-at-separator contract and the segmentation control. Existing [issue #6701](https://github.com/aio-libs/aiohttp/issues/6701)/[PR #6810](https://github.com/aio-libs/aiohttp/pull/6810) fixed a different intra-chunk offset bug for multi-byte separators. Their presence does not establish that this boundary defect was disclosed; [full search records](evidence/extra-disclosure-search.json) preserve the results. Novelty remains provisional: issue search did not include every comment, advisory, or external tracker.

Practicality: fetched master includes commits from 27 September and [contributor instructions](https://github.com/aio-libs/aiohttp/blob/25f30573cc01da08f5b962128eebb16b9701ada3/CONTRIBUTING.rst) require tests and a changelog fragment. [AGENTS.md](https://github.com/aio-libs/aiohttp/blob/25f30573cc01da08f5b962128eebb16b9701ada3/AGENTS.md) additionally requires a human-reviewed draft and disclosure if later submitted. These are maintenance/workflow signals, **not a prediction of acceptance speed**. Next: add tests with delimiter length 2+, buffered and delayed feeds, several boundaries, EOF and limits; implement overlap-aware scanning without repeatedly joining all buffers. Historical coalescing patch only handles chunks already buffered and is not a complete fix for arrivals after consumption.

### 2. flatted: executed topology change, contract conflict still open

Historical evidence: [BUG-002](../../../../repos/secbench2_widenet/wn-jsts-01-flatted/quality/BUGS.md). Current **`e6f5ca700c4ca8104a6a83472c8219e267bd5e84`** (3.4.4, July 30). [Python source](https://github.com/WebReflection/flatted/blob/e6f5ca700c4ca8104a6a83472c8219e267bd5e84/python/flatted.py#L52) uses `list.index`, hence equality; [JS source](https://github.com/WebReflection/flatted/blob/e6f5ca700c4ca8104a6a83472c8219e267bd5e84/cjs/index.js#L91) uses reference-keyed `Map`.

[Python reproduction](evidence/repro-flatted.py) / [log](evidence/flatted-actual.log): two separately allocated `{'x':1}` objects serialize as `[["1","1"],{"x":1}]`; round-trip produces the same object twice, so mutating the first changes the second. [Actual JS control](evidence/flatted-js-control.log) retains two slots and mutation independence. This is not malformed-input fuzzing.

However, [the Python test](https://github.com/WebReflection/flatted/blob/e6f5ca700c4ca8104a6a83472c8219e267bd5e84/python/test.py#L45) explicitly expects equivalent composites to share slots. The README describes Python availability but does not explicitly promise identity-preserving cross-language round trips. **Classify validity unresolved, despite reproduced behavior.** Contributor PRs for Python exist ([#71](https://github.com/WebReflection/flatted/pull/71), [#89](https://github.com/WebReflection/flatted/pull/89)), and current README/package scripts include the port; maintenance exists, but JS is the main product. Next: determine whether aliases can be created/lost in documented Python use and whether identity preservation is intended; test genuine cycles and equal distinct cyclic containers before designing a fix. Do not transplant the historical PHP finding: PHP arrays have different value semantics.

## Surviving but already disclosed — avoid duplicate submissions

| Candidate | Current result | Primary upstream evidence |
|---|---|---|
| chi quoted `charset="utf-8"` (BUG-005) | Actual execution: body `"x"`, unquoted charset →204, quoted→415. Bodyless requests bypass validation, so the trigger must include a body. | Exact [closed, unmerged PR #1139](https://github.com/go-chi/chi/pull/1139). Closed is not fixed: fresh master still reproduces. |
| chi compression (BUG-001) | `gzip;q=0` and `x-gzip` both emit `Content-Encoding:gzip` | [Issue #1069](https://github.com/go-chi/chi/issues/1069) and many open proposals, including [#1177](https://github.com/go-chi/chi/pull/1177). Poor new contribution prospect due to duplication. |
| shell-quote trailing character (BUG-001) | `parse('a$!b', {'!':'BANG'})`→`['aBANG']`; quoted variant also loses suffix | Exact [open PR #30](https://github.com/ljharb/shell-quote/pull/30), created Sept12. Current canonical upstream `35c9b97a744211091b772f145bef0b6a5562b68e`; recent July changes and test suite are practical signals, but a new duplicate is unnecessary. |
| minimatch `[:print:]` (BUG-001) | Current source `ded1bbd01beca62a5978bc1650ed0a1ccf9039d5` still omits negation; **source only** here | Exact [open PR #309](https://github.com/isaacs/minimatch/pull/309), created June29. |
| defu missing `.fn/.arrayFn/.extend` (BUG-001) | Current source `82632b66f5914e9946edce300e10633a3d5c0cb7` still casts bare function to property-bearing interface; **source only** here | Exact [open PR #174](https://github.com/unjs/defu/pull/174). May17 last fetched main commit plus pending fixes are weaker throughput signals than aiohttp; no timing promise justified. |

[chi test source](evidence/chi-triage_test.go), [fresh failing log](evidence/chi-actual.log), [shell-quote source](evidence/repro-shell-quote.cjs), [fresh log](evidence/shell-quote-actual.log). Chi's current [CONTRIBUTING](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/CONTRIBUTING.md) asks for regression-first tests; September18 latest fetched commit indicates active maintenance, while long-lived pending middleware proposals counsel caution.

## Fixed / historical replay negative

**Immutable.js `Repeat.lastIndexOf`: exclude from current bug shortlist.** Current `686b8baf1dc825419f5ded2968b48e3432644aff` returns `size - 1` and handles empty repeats. [PR #2227](https://github.com/immutable-js/immutable-js/pull/2227) merged **22 June 2026**; [changelog](https://github.com/immutable-js/immutable-js/blob/686b8baf1dc825419f5ded2968b48e3432644aff/CHANGELOG.md) records release 5.1.7 and [CVE-2026-29063 advisory](https://github.com/immutable-js/immutable-js/security/advisories/GHSA-wf6x-7x77-mvgw). Historical QPB report is dated June23 against 5.1.4: at minimum, its reported finding postdates public upstream remediation. Do not count it as a currently unreported discovery.

Other secbench security claims remain screening leads, **not verified new upstream vulnerabilities**. Some reports explicitly describe fork-only changes (for example node-tar's relaxed symlink policy); existence in a benchmark checkout is not evidence current upstream contains them. No blanket “all secbench findings are known CVEs” inference was made. The machine record preserves source-only checks separately from execution and technical validity separately from disclosure/disposition.

## Repeat commands and limits

Run from `/Users/andrewstellman/Documents/QPB`:

```sh
node docs/research/triage-2026-09-27/nonlinux/evidence/repro-shell-quote.cjs
python3 docs/research/triage-2026-09-27/nonlinux/evidence/repro-flatted.py
AIOHTTP_NO_EXTENSIONS=1 repos/validation-2026-09-27/nonlinux/aiohttp-venv/bin/python docs/research/triage-2026-09-27/nonlinux/evidence/repro-aiohttp.py
```

Chi: `cd repos/validation-2026-09-27/nonlinux/chi`, then `GOCACHE=/tmp/qpb-nonlinux-go-cache go test -v -run TestTriage .` (expected exit 1 from three failing assertions). Fresh shallow clone commands and dependency installation are recoverable from [command ledger](evidence/commands.txt); actual test source is also preserved outside the checkout. No broad test sweep or full audit ran. Network reads used GitHub clones/API; API search body results and exact queries are preserved in [initial searches](evidence/disclosure-search.json) and [additional searches](evidence/extra-disclosure-search.json). Search incompleteness and mutable upstream state mean “no exact result found” cannot prove unpublished status. Human adjudication, patch regression verification, and any upstream submission remain subsequent work.
