# Quality Playbook Progress

Skill version: v1.5.8
Date: 2026-06-19

## Phase tracker

- [x] Phase 1 - Explore
- [x] Phase 2 - Generate
- [x] Phase 3 - Code Review
- [ ] Phase 4 - Spec Audit
- [ ] Phase 5 - Reconciliation
- [ ] Phase 6 - Verify

## Run metadata
Started: 2026-06-19T21:34:13Z
Project: express (Express.js web framework, package.json version 5.2.1)
Skill version: v1.5.8
With docs: yes (reference_docs/ has 15 Tier-4 gathered docs; reference_docs/cite/ is empty → 0 Tier-1/2 citable sources)

## Phase completion
- [x] Phase 1: Exploration — completed 2026-06-19T21:48Z
- [x] Phase 2: Artifact generation (QUALITY.md, REQUIREMENTS.md, tests, protocols, RUN_TDD_TESTS.md) — completed 2026-06-19T21:58Z
- [x] Phase 3: Code review + regression tests — completed 2026-06-19T22:15Z (6 bugs confirmed, 1 candidate demoted)
- [ ] Phase 4: Spec audit + triage
- [ ] Phase 5: Post-review reconciliation + closure verification
- [ ] TDD logs: red-phase log for every confirmed bug, green-phase log for every bug with fix patch
- [ ] Phase 6: Verification benchmarks
- [ ] Phase 7: Present, Explore, Improve (interactive)

## Scope declaration
Source file count (lib/ only, excluding tests/docs/examples/QPB tooling): 6 files, ~5,524 LOC.
Below the 200-file threshold → full exploration of lib/. The HTTP router is an external
dependency (`router@2.2.0`); node_modules is absent, so router internals are out of scope
and are treated as a behavioral-contract boundary (REQ references cite the call sites in
lib/application.js, not router source).

Subsystems covered this run:
1. Response surface (lib/response.js, 1047 LOC) — the highest-risk module.
2. Request surface (lib/request.js, 527 LOC) — trust-proxy + header parsing.
3. Application/config (lib/application.js, 631 LOC) — settings compilation, dispatch.
4. Utilities (lib/utils.js, 271 LOC) — ETag/trust/query/charset compilers + accept parser.
5. View rendering (lib/view.js, 205 LOC) and entry (lib/express.js, 81 LOC).

## Documentation depth assessment
reference_docs/ contains 15 markdown docs plus INDEX/README/sources/COLLECTION_SUMMARY.
Per `bin/reference_docs_ingest`, 0 cite records were written (reference_docs/cite/ empty),
so all 15 docs are Tier 4 context — informative for orientation but NOT citable for Tier 1/2
requirements. Run degrades gracefully into a Spec-Gap analysis: REQs will be Tier 3
(code-is-the-spec) with the gathered docs as supporting Tier-4 context.

| Document | Depth | Subsystem | Requirements commitment | If excluded: justification |
|----------|-------|-----------|------------------------|---------------------------|
| 01_API_Reference.md | Moderate | All res/req/app methods | Will cover (Tier 4 supporting) | n/a |
| 03_Routing_Guide.md | Moderate | Routing / mounting | Will cover (composition REQs) | n/a |
| 04_Middleware_Architecture.md | Moderate | app.use / handle | Will cover | n/a |
| 05_Error_Handling.md | Moderate | format / next(err) | Will cover | n/a |
| 06_Security_Best_Practices.md | Moderate | jsonp / cookies / proxy | Will cover (security REQs) | n/a |
| 14_Known_Vulnerabilities.md | Shallow | cross-cutting | Context only | Catalog, not contract |
| others (02,07,09–13,15) | Shallow | misc | Context only | Feature overviews, not contracts |

Mechanical verification: NOT APPLICABLE — Express's lib/ has no dispatch tables over named
constant sets (feature bits / opcode tables) that require shell-extraction witnesses. The
closest analogues (switch on `etag`/`query parser`/`trust proxy` setting names in
utils.js compile* functions) are small fixed switches reviewed inline in EXPLORATION.md.

## Artifact inventory
| Artifact | Status | Path | Notes |
|----------|--------|------|-------|
| EXPLORATION.md | done | quality/EXPLORATION.md | Phase 1 findings |
| exploration_role_map.json | done | quality/exploration_role_map.json | 315 files, provenance=filesystem-walk-with-skips |
| formal_docs_manifest.json | done | quality/formal_docs_manifest.json | 0 FORMAL_DOC records (cite/ empty) |
| QUALITY.md | generated | quality/QUALITY.md | 8 fitness scenarios |
| REQUIREMENTS.md | generated | quality/REQUIREMENTS.md | REQ-001..016, UC-01..07.c (Tier 3) |
| CONTRACTS.md | generated | quality/CONTRACTS.md | C-1..C-8 + layout contracts |
| COVERAGE_MATRIX.md | generated | quality/COVERAGE_MATRIX.md | REQ→scenario→test→UC |
| COMPLETENESS_REPORT.md | generated | quality/COMPLETENESS_REPORT.md | baseline, no verdict |
| Functional tests | generated | quality/test_functional.js | Mocha+supertest, ~24 tests |
| RUN_CODE_REVIEW.md | generated | quality/RUN_CODE_REVIEW.md | 3-pass protocol |
| RUN_INTEGRATION_TESTS.md | generated | quality/RUN_INTEGRATION_TESTS.md | 9 groups, per-UC split |
| BUGS.md | deferred to Phase 3 | | bugs_manifest.json empty (no bugs confirmed yet) |
| RUN_TDD_TESTS.md | generated | quality/RUN_TDD_TESTS.md | red-green protocol |
| RUN_SPEC_AUDIT.md | generated | quality/RUN_SPEC_AUDIT.md | Council of Three |
| requirements_manifest.json | generated | quality/requirements_manifest.json | 16 REQ records |
| use_cases_manifest.json | generated | quality/use_cases_manifest.json | 11 UC records |
| bugs_manifest.json | generated | quality/bugs_manifest.json | 0 records (Phase 3+ populates) |

## Cumulative BUG tracker
<!-- Every confirmed BUG from code review and spec audit goes here. -->

| # | Source | File:Line | Description | Severity | Closure Status | Test/Exemption |
|---|--------|-----------|-------------|----------|----------------|----------------|
| BUG-001 | Code Review | lib/request.js:309-314 | `req.protocol`/`req.secure` collapse to `''`/false for trusted `X-Forwarded-Proto` with empty leading element | HIGH | open (fix patch) | test_regression.js it.skip BUG-001 |
| BUG-002 | Code Review | lib/response.js:759-766 | `res.cookie` sub-second `maxAge` emits `Max-Age=0` with future `Expires` | HIGH | open (fix patch) | test_regression.js it.skip BUG-002 |
| BUG-003 | Code Review | lib/response.js:841,846-847 | `res.redirect` emits literal `undefined` for in-range unassigned status | MEDIUM | open (fix patch) | test_regression.js it.skip BUG-003 |
| BUG-004 | Code Review | lib/response.js:137-153 | Charset asymmetry: string `send` forces utf-8, Buffer `send`/`res.set` preserve charset | MEDIUM | open (fix patch) | test_regression.js it.skip BUG-004 |
| BUG-005 | Code Review | lib/utils.js:89-120 | `acceptParams` splits quoted `;` and does not clamp `q` to [0,1] | MEDIUM | open (fix patch) | test_regression.js it.skip BUG-005 |
| BUG-006 | Code Review | lib/request.js:424-427 | trusted leading-comma `X-Forwarded-Host` → `host`/`hostname` undefined, `subdomains` [] | MEDIUM | open (fix patch) | test_regression.js it.skip BUG-006 |

**Demoted (excluded from bug count):** jsonp member-access whitelist (`response.js:286`) — FALSE POSITIVE; filter strips all statement-breaking chars + `nosniff`/`typeof` guard ⇒ no injection path reachable.

## Terminal Gate Verification
<!-- Filled in during Phase 5. Must match BUG tracker counts exactly. -->

## Exploration summary
Express v5.2.1, Node HTTP framework. 6 source files in lib/ (~5.5k LOC); routing is the
external router@2.2.0 dependency. Key risk areas: res.send/res.json/res.jsonp content-type
and charset handling (response.js), trust-proxy + X-Forwarded-* header parsing (request.js),
settings-compilation chain (application.js + utils.js compile*), and the hand-rolled
acceptParams parser (utils.js). 70 mocha test files cover the public surface broadly;
gaps concentrate at edge inputs (empty/comma-only forwarded headers, non-standard status
codes in redirect/sendStatus, charset asymmetry between string vs Buffer send bodies).
