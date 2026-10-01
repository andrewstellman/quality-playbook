# Candidate bugs validated 2026-09-27

Each candidate below was taken from a past Quality Playbook run, checked against a fresh clone of the project's current main branch, and either reproduced or ruled out. Nothing has been submitted. Each confirmed folder holds a README (defect, source lines at the pinned commit, expected behaviour and its source, red/green, test-suite results, duplicate search) plus a `git format-patch` and a PR-DRAFT.md.

Scope was correctness bugs only. Findings with a security angle were set aside rather than reproduced.

## Confirmed, no existing report found

| Project | Bug | Pinned commit | How it was run | Evidence |
|---|---|---|---|---|
| aiohttp | `StreamReader.readuntil()` misses a separator split across two chunks; returns data past it, or hangs | `e11d2836` | Real code, project test suite. 16 new tests fail before, 162/162 pass after; re-checked independently by the orchestrating session | `aiohttp-readuntil-split-separator/` |
| go-chi/chi | `middleware.GetHead` inside a mounted sub-router ignores the sub-router's own HEAD handler, and can return 405 | `3d1777a1` | Real code, `go test ./...` and `-race` | `chi-gethead-mount/` |
| expressjs/express | `res.cookie` with `maxAge` < 1000 ms sends `Max-Age=0` with a future `Expires`, so the cookie is deleted | `9a34acf0` | Real code, full `npm test` | `express-cookie-subsecond-maxage/` |
| opentelemetry-java-instrumentation | `UrlParser` (incubator, reactor-netty) records `server.address="["` for `http://[::1]:8080/` | `78d71b58` | Unmodified sources + project JUnit tests via javac (not Gradle) | `otel-java-urlparser-ipv6/` |
| opentelemetry-java-instrumentation | `ForwardedHostAddressAndPortExtractor.extractHost` records `"[2001"` for bracketed IPv6; sibling of the already-fixed #19540 | `78d71b58` | Same as above | `otel-java-forwarded-host-ipv6/` |
| assertj | `Percentage.toString()` prints `2147483647%` for large whole values (int overflow in failure messages) | `7ca27151` | Real code, full assertj-core suites | `assertj-percentage-tostring-overflow/` |
| calibre | `/opds/navcatalog` returns 500 instead of 404 for malformed hex ids | `7691f4f1` | Harness: verbatim handler bodies, stubbed library context. Router path not executed | `calibre-opds-navcatalog/` |
| bionemo-recipes | AMPLIFY `_pad_weights` returns fp32 for a bf16 input | `11701476` | Harness: verbatim function copy (transformer_engine blocks import) | `bionemo-amplify-pad-weights-dtype/` |
| bionemo-recipes | THD context-parallel split drops remainder tokens when length isn't divisible | `11701476` | Harness: verbatim function copy, single process | `bionemo-thd-cp-divisibility/` |

## Reproduced, but already reported upstream

| Project | Bug | Existing report |
|---|---|---|
| chi | `AllowContentEncoding` rejects `gzip, deflate` | issue #959, open PR #1182 |
| chi | `Recoverer` exact-matches `Connection: Upgrade` | open PRs #1077 (Andrew's own), #1170, #1172 |
| chi | quoted charset in `ContentCharset` | PR #1139 (closed unmerged) |
| chi | compression honours `gzip;q=0` | issue #1069, PR #1177 |
| chi | `SupressNotFound` mutates route context | issue #939, PR #940 |
| express | `res.redirect` prints "undefined" for unassigned codes | open PR #7045 |
| express | `acceptParams` mis-splits quoted `;` | open PR #7479 |
| assertj | NaN in `DoubleComparator`/`FloatComparator` | #1390, declined by the project lead |

## Needs a maintainer's view rather than a patch

chi `Mux.Find` wildcard param after Mount; chi `PathRewrite`/`PageRoute` under Mount; chi `RegisterMethod` race (leans working-as-designed); assertj null handling in `ComparatorBasedComparisonStrategy`; flatted Python aliasing equal-but-distinct objects (its own test expects it).

## Ruled out

requests `codes.uri_too_long` (deliberate since PR #6680; a near-identical report, #7611, closed a month ago); express charset asymmetry (intended, #2238); assertj `NaNf` (intended, tested); assertj NumberGrouping regex (unreachable); rails findings (fixed upstream); calibre BUG-001/002 and BioNeMo BUG-003/006 (fixed upstream).

## Set aside: security angle

opentelemetry-java `Forwarded` header `indexOf` matching (BUG-003); express X-Forwarded-Proto/Host findings; most of the secbench trees. Not reproduced.

## Linux, not covered here

exfat O_APPEND stale data (embargo runbook at `~/src/qemu-lab/embargo-exfat/`, never run), sctp2 `SCTP_MAX_BURST` optlen, vsock SO_RCVLOWAT boundary. See `docs/research/triage-2026-09-27/linux/REPORT.md`. These need the QEMU guest.

## Suggested submission order

1. aiohttp: strongest evidence, active project, contributor workflow understood. Rename `CHANGES/PRNUMBER.bugfix.rst` once the PR number exists.
2. otel-java (both): clean fixes, real-code tests. Needs EasyCLA, and Spotless/checkstyle run with Gradle on the Mac first.
3. chi GetHead: small fix; chi merges slowly.
4. express cookie: their guide asks for an issue first.
5. assertj: their CONTRIBUTING requires 100% human authorship; decide whether that permits this patch.
6. calibre and bionemo: harness-only evidence and low impact; weakest cases.
