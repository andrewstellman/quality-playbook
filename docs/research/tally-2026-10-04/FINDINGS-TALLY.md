# Relevant findings in the QPB evidence collection

Prepared 4 October 2026. This is a research tally of existing records, not a new reproduction run or a live check of upstream status. The unit is an evidence case, not a report file, failing test, code location, or unique underlying mechanism across projects.

**41 cases across 16 projects: 23 worth keeping in the main research pool, 8 conditional cases, and 10 excluded from the positive tally.** These are research-selection judgments, not 23 equally validated experiments. The reproduction qualifications below matter.

The claim being assessed is Andrew's: QPB can find defects that standard review with the same model misses, and some discoveries draw on information unavailable to that review. QPB itself contains a standard-review phase. This tally does not substitute a claim of general superiority or overall recall.

## Portfolio tally

| Group | Cases | Meaning |
|---|---:|---|
| Active/accepted submission portfolio | 20 | Local STATUS records: 2 merged, 8 open, 2 sent, 8 ready |
| Additional policy-held cases | 3 | AssertJ and two Pydantic findings remain research candidates despite filing restrictions |
| Conditional | 8 | Three Adonis fixes need work, three Zod cases await panel, Addressable template needs decision, chi GetHead patch regressed |
| Excluded from positive headline | 10 | Four dropped, two duplicates, three needing maintainer interpretation, one ruled out |
| **Total** | **41** | **16 projects** |

The eight `open` records comprise six PRs and two Zod issues. All STATUS records in this snapshot are dated October 1. They should not be reported as current upstream state. In particular, a later October 3 research handoff reports aiohttp merged, whereas its STATUS still says open. This tally preserves the discrepancy rather than silently changing the record. Gson and the earlier zram case have no case folder in this 41-record set; newer cloud-run evidence is also outside this bounded tally. Thus this is not the complete lifetime QPB portfolio.

## Existing standard-review comparisons

The table reports **hits**, so a smaller numerator means more misses. It combines the existing [Claude scoring](../control-2026-09-27/results/CLAUDE-SCORING.md) with the [new scoring of the existing GPT reports](CONTROL-SCORING.md). No new model runs were launched. There are 244 distinct reviews behind this table: 104 Claude and 140 GPT; a review can cover multiple target defects. Both scoring passes knew the targets.

| Evidence case | Opus | Sonnet | Sol | Terra | Research interpretation |
|---|---:|---:|---:|---:|---|
| calibre malformed OPDS hex | 0/10 | 0/10 | 0/10 | 0/10 | 40 misses; locally recorded upstream merge |
| BioNeMo THD token loss | 0/10 | 0/10 | 0/10 | 2/10 | 38 misses; harness reproduction, default padding safe |
| aiohttp split separator | 4/10 | 1/10 | 0/10 | 2/10 | 33 misses; actual package tests |
| chi mounted GetHead | 0/10 | 0/10 | 0/10 | 0/10 | 40 misses; original defect and regressing proposed fix must be separated |
| BioNeMo AMPLIFY dtype | 9/10 | 6/10 | 6/10 | 9/10 | Often found by review; useful contextual case |
| OpenTelemetry UrlParser IPv6 | 1/1 | 0/1 | 10/10 | 9/10 | Often found; Claude arm has only one trial per model |
| OpenTelemetry Forwarded IPv6 | 1/1 | 0/1 | 10/10 | 9/10 | Often found; Claude arm has only one trial per model |
| AssertJ percentage formatting | 1/1 | 0/1 | 10/10 | 8/10 | Often found; policy restriction does not invalidate defect |
| Express subsecond cookie | 0/10 | 0/10 | 0/10 | 0/10 | **Dropped: exclude from positive claim** |

Seven of the nine compared cases are in the main research pool; chi is conditional and Express is excluded. All seven have at least one missed control review, but that alone is a weak selection criterion. Calibre, THD and aiohttp provide the clearest repeated-miss observations. Pooling above is descriptive arithmetic over these runs, not a statistical detection-rate estimate for a shared model population.

These comparisons are scoped to known defect-containing directories at pinned commits ([scopes](../control-2026-09-27/SCOPES.md)). The Claude scoring explicitly says the historical discovery models are not matched. A model credited for September reproduction/fix work is not necessarily the model that discovered the defect in June. Several control runs also had missing dependencies or web-access deviations; preserve those qualifications from the original logs. The matched-model discovery/control linkage remains to be reconciled case by case, rather than inferred from model-family names. No conclusion is drawn here about other same-model records that may exist elsewhere.

## Which cases address the additional-information claim?

Three particularly useful issue-grounded candidates in this folder are:

- **Addressable route_from:** maintainer issue #126 supplies a round-trip expectation alongside RFC 3986.
- **Adonis UUID matcher:** issue #50 and PR #53 establish intended hexadecimal validation.
- **setuptools missing dynamic:** a maintainer comment on #4183 explains warn-and-ignore behavior, alongside PEP 621; the implementation crashes instead.

The two nvmet cases offer explicit protocol requirements with kernel/QEMU evidence. Adonis's 205-body case offers another explicit standard, although its patch is incomplete. Gson remains especially relevant to Andrew's issue-report hypothesis, but it is outside these 41 folders. A [Gson same-model control script](../control-2026-09-27/run-gson-control.sh) is present and names GPT-5.4; no Gson result reports were found in the research results directory during this tally. A script is not an executed comparison.

For each selected information-use example, link the original issue/document passage to the derived requirement and the discovery transcript, then to the matched control's actual information access. A citation in a later PR draft establishes an expectation; by itself it does not establish what caused the original discovery.

The strongest repeated-miss case, **calibre**, explicitly says its original report was derived solely from in-tree code. **aiohttp** and both **OpenTelemetry** cases identify their original runs as code-only Phase 3 review. These cases demonstrate useful discovery/miss observations, but should not be described as external-document-driven discoveries. Original records: [calibre](../../../repos/secbench2/sb2-24-calibre/quality/BUGS.md), [aiohttp](../../../repos/secbench2_widenet/wn-py-09-aiohttp/quality/BUGS.md), [OpenTelemetry](../../../repos/secbench2_widenet/wn-jvm-02-opentelemetry-java-instrumentation/quality/BUGS.md).

## Complete case ledger

The status links are the historical disposition; evidence links lead to the technical writeup when present. “Active” includes ready cases with remaining submission checks. “Policy-held” means retained for research, not automatically ready to publish or submit.

### 20 active portfolio cases

| Case | Recorded status | Relevance and qualification |
|---|---|---|
| [addressable-route-from-base-query](../../../evidence/addressable-route-from-base-query/PR-DRAFT.md) | [ready](../../../evidence/addressable-route-from-base-query/STATUS.md) | RFC 3986 resolution plus maintainer issue #126 supplies a concrete round-trip expectation. Strong candidate for tracing issue-derived intent; panel and focused re-review approved. |
| [adonis-cookie-maxage-zero](../../../evidence/adonis-cookie-maxage-zero/CONFIRMATION.md) | [open](../../../evidence/adonis-cookie-maxage-zero/STATUS.md) | Zero is accepted by the API but a truthiness check drops Max-Age. Existing serializer/clearCookie behavior supports expected output. |
| [adonis-toroute-qs-mutation](../../../evidence/adonis-toroute-qs-mutation/CONFIRMATION.md) | [ready](../../../evidence/adonis-toroute-qs-mutation/STATUS.md) | Reusing caller options loses query parameters because toRoute mutates them; panel approved after text fixes. |
| [adonis-unknown-content-type](../../../evidence/adonis-unknown-content-type/CONFIRMATION.md) | [ready](../../../evidence/adonis-unknown-content-type/STATUS.md) | Unknown MIME type can produce Content-Type: false; media-type syntax and documented header behavior ground the mismatch. |
| [adonis-uuid-matcher](../../../evidence/adonis-uuid-matcher/CONFIRMATION.md) | [open](../../../evidence/adonis-uuid-matcher/STATUS.md) | Issue #50 / PR #53 provide historical intent; a-z accepts letters outside hexadecimal. Particularly useful issue-history case. |
| [aiohttp-readuntil-split-separator](../../../evidence/aiohttp-readuntil-split-separator/README.md) | [open](../../../evidence/aiohttp-readuntil-split-separator/STATUS.md) | Documented readuntil sequence contract, actual package red/green tests and asyncio parity. Original report explicitly code-only Phase 3; not evidence of external-document causation. STATUS says open; later Oct 3 handoff reports merged, not rechecked here. |
| [bionemo-amplify-pad-weights-dtype](../../../evidence/bionemo-amplify-pad-weights-dtype/README.md) | [open](../../../evidence/bionemo-amplify-pad-weights-dtype/STATUS.md) | CPU PyTorch harness executes copied function; dtype loss reproduced. Sibling implementation supplies intended behavior. Full package/CUDA path was not executed; control reports often find this. |
| [bionemo-thd-cp-divisibility](../../../evidence/bionemo-thd-cp-divisibility/README.md) | [open](../../../evidence/bionemo-thd-cp-divisibility/STATUS.md) | Copied tensor-function harness reproduces dropped remainder tokens with explicit padding override; shipped default padding is safe. Sibling BSHD guard supports expectation. Full distributed execution not performed. |
| [calibre-opds-navcatalog](../../../evidence/calibre-opds-navcatalog/README.md) | [merged](../../../evidence/calibre-opds-navcatalog/STATUS.md) | Malformed hex raises through handler instead of yielding expected client error; sibling handlers support behavior. AST-extracted real handler harness, not end-to-end. Local records confirm merge. Original report says solely in-tree code. |
| [cobra-complete-after-dashdash](../../../evidence/cobra-complete-after-dashdash/PR-DRAFT.md) | [ready](../../../evidence/cobra-complete-after-dashdash/STATUS.md) | Completion callback drops positional arguments after flag parsing stops; completion documentation gives expectation. Go tests/vet and re-review recorded. |
| [cobra-suggest-runes](../../../evidence/cobra-suggest-runes/REVIEW.md) | [open](../../../evidence/cobra-suggest-runes/STATUS.md) | Suggestion distance counts bytes instead of runes; Unicode behavior and red/green/revert evidence. Filed PR. |
| [javalin-lowercase-redirect-contextpath](../../../evidence/javalin-lowercase-redirect-contextpath/PR-DRAFT.md) | [ready](../../../evidence/javalin-lowercase-redirect-contextpath/STATUS.md) | Redirect loses configured context path; concrete routing behavior, panel approved. |
| [nvmet-anagrpid](../../../evidence/nvmet-anagrpid/README.md) | [sent](../../../evidence/nvmet-anagrpid/STATUS.md) | Boundary ANA group identifier misindexed; kernel/QEMU evidence and submitted patch. No matched standard-review result linked in this tally. |
| [nvmet-crto](../../../evidence/nvmet-crto/README.md) | [sent](../../../evidence/nvmet-crto/STATUS.md) | CRTO timeout derived from CSTS instead of CAP; protocol-based expectation and kernel/QEMU evidence. User reports maintainer asked for concise explanation; that is not merge acceptance. |
| [otel-java-forwarded-host-ipv6](../../../evidence/otel-java-forwarded-host-ipv6/README.md) | [ready](../../../evidence/otel-java-forwarded-host-ipv6/STATUS.md) | RFC host syntax, semantic conventions and related upstream IPv6 fix support expectation. Real Java source compiled/tested with standalone harness; Gradle run outstanding. Original discovery explicitly code-only Phase 3. |
| [otel-java-urlparser-ipv6](../../../evidence/otel-java-urlparser-ipv6/README.md) | [ready](../../../evidence/otel-java-urlparser-ipv6/STATUS.md) | Bracketed IPv6 parsing violates host expectation across two copies. Real Java source red/green with standalone harness; Gradle run outstanding. Original discovery explicitly code-only Phase 3. |
| [setuptools-missing-dynamic-crash](../../../evidence/setuptools-missing-dynamic-crash/PR-DRAFT.md) | [ready](../../../evidence/setuptools-missing-dynamic-crash/STATUS.md) | PEP 621 plus maintainer comment #4183 establishes warn-and-ignore behavior. Two fields crash instead. Strong issue/spec example; red/green/revert and panel re-review recorded. |
| [virtio-pci-intx](../../../evidence/virtio-pci-intx/README.md) | [merged](../../../evidence/virtio-pci-intx/STATUS.md) | Config-only interrupt incorrectly returns IRQ_NONE; QEMU/interrupt evidence and local record of upstream merge. |
| [zod-intersection-nan](../../../evidence/zod-intersection-nan/README.md) | [open](../../../evidence/zod-intersection-nan/STATUS.md) | Two branches yielding NaN fail intersection merge; actual source test/reverification evidence and filed issue. |
| [zod-registry-remove-owner](../../../evidence/zod-registry-remove-owner/README.md) | [open](../../../evidence/zod-registry-remove-owner/STATUS.md) | Removing previous owner deletes id now held by another schema. In-tree overwrite behavior and PR #5574 support intent; filed issue. |

### 3 additional policy-held cases

| Case | Recorded status | Relevance and qualification |
|---|---|---|
| [assertj-percentage-tostring-overflow](../../../evidence/assertj-percentage-tostring-overflow/README.md) | [not-filed](../../../evidence/assertj-percentage-tostring-overflow/STATUS.md) | Large permitted percentage values saturate an int cast in toString; Maven red/green and related suites recorded. Contribution policy prevents filing, not research use. |
| [pydantic-multipleof-nonfinite](../../../evidence/pydantic-multipleof-nonfinite/PR-DRAFT.md) | [held](../../../evidence/pydantic-multipleof-nonfinite/STATUS.md) | Nonfinite values accepted by multiple_of; expected behavior grounded in numeric constraint semantics. Held for contribution-policy reasons. |
| [pydantic-typeddict-own-config](../../../evidence/pydantic-typeddict-own-config/PR-DRAFT.md) | [held](../../../evidence/pydantic-typeddict-own-config/STATUS.md) | TypedDict serialization ignores its own config; documented config behavior supports claim. Policy hold plus red/green not rerun after rebase. |

### 8 conditional cases

| Case | Recorded status | Relevance and qualification |
|---|---|---|
| [addressable-template-pct-encoded](../../../evidence/addressable-template-pct-encoded/PR-DRAFT.md) | [decision](../../../evidence/addressable-template-pct-encoded/STATUS.md) | RFC 6570 grounding, but panel split over behavior changes. Preserve as an adjudication case, not an unqualified positive. |
| [adonis-lookup-route-error](../../../evidence/adonis-lookup-route-error/CONFIRMATION.md) | [needs-work](../../../evidence/adonis-lookup-route-error/STATUS.md) | Documented E_CANNOT_LOOKUP_ROUTE and issue history support the mismatch; proposed fix misses urlBuilder.urlFor. |
| [adonis-redirect-qs-separator](../../../evidence/adonis-redirect-qs-separator/CONFIRMATION.md) | [needs-work](../../../evidence/adonis-redirect-qs-separator/STATUS.md) | Existing-query redirect gets a second question mark; proposed merge can duplicate hard-coded keys. Revise and re-review. |
| [adonis-reset-content-body](../../../evidence/adonis-reset-content-body/CONFIRMATION.md) | [needs-work](../../../evidence/adonis-reset-content-body/STATUS.md) | HTTP 205 no-content requirement is an explicit standard; fix coverage still omits stream/download. |
| [chi-gethead-mount](../../../evidence/chi-gethead-mount/README.md) | [not-filed](../../../evidence/chi-gethead-mount/STATUS.md) | Original mounted-router behavior reproduced in Go; proposed patch regressed during review. Keep original defect separate from failed fix. All controls missed it, but patch/adjudication work remains. |
| [zod-catch-shared-reference](../../../evidence/zod-catch-shared-reference/CONFIRMATION.md) | [held](../../../evidence/zod-catch-shared-reference/STATUS.md) | Shared constant catch value versus cloning expectation needs full panel; do not assume analogy with default establishes contract. |
| [zod-function-implement-zoderror](../../../evidence/zod-function-implement-zoderror/CONFIRMATION.md) | [held](../../../evidence/zod-function-implement-zoderror/STATUS.md) | Public ZodError contract versus internal error type; full panel and less-minimal fix still pending. |
| [zod-treeify-symbol-keys](../../../evidence/zod-treeify-symbol-keys/CONFIRMATION.md) | [held](../../../evidence/zod-treeify-symbol-keys/STATUS.md) | Symbol key classification into items rather than properties; expected API/type behavior needs full panel. |

### 10 cases excluded from the positive tally

| Case | Recorded status | Relevance and qualification |
|---|---|---|
| [adonis-send-error-object](../../../evidence/adonis-send-error-object/CONFIRMATION.md) | [dropped](../../../evidence/adonis-send-error-object/STATUS.md) | Dropped after panel. Do not use the original claimed behavior and proposed fix as a clean positive. |
| [chi-allowcontentencoding-comma](../../../evidence/chi-allowcontentencoding-comma/README.md) | [duplicate](../../../evidence/chi-allowcontentencoding-comma/STATUS.md) | Already reported upstream (#959 / PR #1182). May illustrate rediscovery, not a newly reported defect. |
| [chi-find-mount-wildcard](../../../evidence/chi-find-mount-wildcard/README.md) | [maintainer-view](../../../evidence/chi-find-mount-wildcard/STATUS.md) | Needs maintainer interpretation of routing behavior; not yet a settled positive. |
| [chi-pathrewrite-pageroute-mount](../../../evidence/chi-pathrewrite-pageroute-mount/README.md) | [maintainer-view](../../../evidence/chi-pathrewrite-pageroute-mount/STATUS.md) | Needs maintainer interpretation before counting as a settled defect. |
| [chi-recoverer-upgrade-token](../../../evidence/chi-recoverer-upgrade-token/README.md) | [duplicate](../../../evidence/chi-recoverer-upgrade-token/STATUS.md) | Existing upstream PRs cover the issue. Keep out of novel-discovery tally. |
| [chi-registermethod-race](../../../evidence/chi-registermethod-race/README.md) | [maintainer-view](../../../evidence/chi-registermethod-race/STATUS.md) | Local assessment leans working-as-designed; do not count as confirmed. |
| [express-cookie-subsecond-maxage](../../../evidence/express-cookie-subsecond-maxage/README.md) | [dropped](../../../evidence/express-cookie-subsecond-maxage/STATUS.md) | Dropped by Andrew: requested precision is below cookie resolution and proposed round-up changes lifetime. Forty misses do not make it a valid positive. |
| [javalin-precompress-maxsize-zero](../../../evidence/javalin-precompress-maxsize-zero/PR-DRAFT.md) | [dropped](../../../evidence/javalin-precompress-maxsize-zero/STATUS.md) | Documentation/code disagreement is real, but proposed interpretation recreates memory exhaustion. Useful ambiguous-requirement example; exclude positive tally. |
| [requests-uri-too-long](../../../evidence/requests-uri-too-long/README.md) | [ruled-out](../../../evidence/requests-uri-too-long/STATUS.md) | Ruled out as intentional upstream behavior; exclude positive tally. |
| [setuptools-manifest-include-globstar](../../../evidence/setuptools-manifest-include-globstar/PR-DRAFT.md) | [dropped](../../../evidence/setuptools-manifest-include-globstar/STATUS.md) | Dropped because making ** recursive changes existing manifests and includes unintended trees. Useful rejection, not a clean positive. |

## Practical next step

Use this collection to select a small set of well-supported cases, not to chase a larger raw count. Start by closing the discovery/control provenance for calibre, aiohttp and BioNeMo THD, and by tracing the issue-derived expectations for Addressable, Adonis UUID, setuptools and Gson. Those two tasks answer different parts of the proposed paper. A merged patch strengthens external validation; it does not replace the discovery/control or information-provenance evidence.

Machine-readable ledger: [findings.json](findings.json). GPT run-level scoring and source hashes: [controls.json](controls.json). Historical evidence and statuses were not changed, and no tests or upstream actions were performed for this tally.
