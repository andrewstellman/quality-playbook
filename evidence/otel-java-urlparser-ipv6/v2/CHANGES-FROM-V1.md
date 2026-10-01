# otel-urlparser: changes from v1

Source: `review-2026-09-27/SYNTHESIS.md`, section "otel-urlparser", plus O1, O2, O3, S2, S5.

| Synthesis item | What v2 does |
|---|---|
| Bound the `]` search to the authority (O2, O3) | `getHostEndIndexExclusive` now scans from the `[` and stops at the first `]`, `/`, `?` or `#`. If it reaches `]` first, the host ends after it. Otherwise (including end of string) it returns `startIndex`, which `getHost`/`getPort`/`getPath` already treat as "no host". This is the same bound as `notFound(ipv6End, end)` in `HttpServerAddressAndPortExtractor`, written as a small loop so the incubator and reactor-netty copies stay identical (the reactor-netty copy has no generic end-index helper). Applied identically to both copies. |
| Test row `http://[::1/path]` returning null | Added `getHost("http://[::1/path]")` isNull and `getHost("http://[x/p?token=abc]")` isNull to `testGetHostAndPortWithIpv6` in both `UrlParserTest` copies. |
| Show the bound matters | `v1-code-v2-tests.log`: v1 main code with v2 tests fails on the new row (`expected: null but was: "::1/path"`) in both copies. Its appended probe shows v1 gave `x/p?token=abc` as the host; v2 gives null. |
| Gradle, spotless (O1, O4, O5, exec-B) | Not run here. See NOTES-FOR-ANDREW.md. google-java-format 1.36.1 `--dry-run` on the five changed files reports no changes; that is not a substitute for `spotlessCheck`. |
| HTML provenance comment | Removed. The PR body has no HTML comments and nothing addressed to Andrew. `Assisted-by: Claude Opus 5.5` stays as the commit trailer; the PR ends with one disclosure sentence. The Quality Playbook link was dropped to keep that to one sentence. The v1 reference to "OTel's GenAI policy" is not repeated anywhere, since S7 could not locate that policy. |
| EasyCLA | Andrew's action; see NOTES-FOR-ANDREW.md. |
| Mention ClickHouse caller (O1, O4) | PR lists `ClickHouseClientV2Singletons` (`CurrentServerInfo`) among affected callers. No ClickHouse test was added (O1 said "consider"). |
| Mention pulsar `UrlParser` as follow-up (O1, O3) | PR has a paragraph saying pulsar has the same first-`:` split and is left for a follow-up. Pulsar code was not changed. |
| State `getPort()` now returns the port (S5) | PR says `getPort` now returns the port (8080 in the example) instead of null. |
| PR template / CONTRIBUTING | `.github/pull_request_template.md` is only a comment saying not to add a CHANGELOG entry except for deprecations or breaking changes. None is added. CONTRIBUTING: bug-fix PRs need no issue first. |
| Commit message short and proportional | Subject unchanged; a three-line body explains the bug and fix, then the trailer. |

Not changed, deliberately:
- S2's optional split of `testGetHostAndPortWithIpv6` into three methods. It matches the file's existing style; synthesis did not require it.
- O3 finding 3 (`http://[]:80/` gives host null but port 80). Harmless, pre-existing shape, not in the synthesis.
- Userinfo (`http://user@[::1]:80/`) remains unsupported, as on base. Not claimed as fixed.

Also changed: the PR's reactor-netty line now names `ReactorNettyHttpClientAttributesGetter` and describes what the getter returns, based on reading its code (lines 92-115 at the pinned commit). This was not checked end to end with a real span.

## Evidence in this folder
- `red.log`: base main code + v2 tests. incubator 20 passed / 2 failed (`expected "::1" but was "["`; `ServicePeerResolverTest` `expected "ipv6PortSvc" but was null`); reactor 0/1 failed (`expected "::1" but was "["`). Exit 1.
- `green.log`: v2. 22/0 and 1/0. Exit 0.
- `revert.log`: v2 with the two main `UrlParser.java` files checked out from base, tests kept. The same failures as red. Exit 1.
- `suite-before.log`: base, 39/0 (incubator: UrlParserTest, ServicePeerResolverTest, ServicePeerAttributesExtractorTest, HttpClientServicePeerAttributesExtractorTest) and 8/0 (reactor UrlParserTest).
- `suite-after.log`: v2, 42/0 and 9/0.
- `v1-code-v2-tests.log`: described above.
- `probe.log`: every example URL in PR-DRAFT.md, run against both copies at base and at v2.
- `harness/`: `run.sh` (unchanged from v1), `otel-verify.sh` (the driver that produced the logs), `deps.SHA1SUMS` (all 24 jars matched).

All runs used javac + JUnit Platform console on JDK 25.0.4.1 (Linux arm64). Gradle was not used.
