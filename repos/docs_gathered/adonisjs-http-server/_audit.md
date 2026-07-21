# Audit

## Sources consulted

All documentation was derived exclusively from the frozen read-only checkout at:

`/Users/andrewstellman/Documents/QPB/repos/secbench-2/adonisjs-http-server`

Specific files read:

- `README.md`
- `package.json`
- `index.ts`
- `src/server/main.ts`
- `src/server/factories/middleware_handler.ts`
- `src/server/factories/route_finder.ts`
- `src/server/factories/write_response.ts` (referenced but not quoted)
- `src/router/main.ts`
- `src/router/route.ts` (structure referenced via types)
- `src/router/group.ts`
- `src/router/resource.ts` (header section)
- `src/router/brisk.ts` (referenced via router)
- `src/router/store.ts` (header section)
- `src/router/matchers.ts` (referenced via router)
- `src/router/executor.ts`
- `src/router/signed_url_builder.ts`
- `src/router/legacy/url_builder.ts` (referenced via router)
- `src/router/factories/use_return_value.ts` (referenced)
- `src/request.ts`
- `src/response.ts` (header section)
- `src/redirect.ts`
- `src/http_context/main.ts`
- `src/http_context/local_storage.ts`
- `src/cookies/client.ts`
- `src/cookies/parser.ts`
- `src/cookies/serializer.ts`
- `src/cookies/drivers/plain.ts` (referenced)
- `src/cookies/drivers/signed.ts` (referenced)
- `src/cookies/drivers/encrypted.ts` (referenced)
- `src/client/url_builder.ts`
- `src/client/helpers.ts` (referenced)
- `src/client/types.ts` (referenced)
- `src/qs.ts`
- `src/errors.ts`
- `src/exception_handler.ts`
- `src/define_config.ts`
- `src/define_middleware.ts`
- `src/tracing_channels.ts`
- `src/types/main.ts`
- `src/types/server.ts`
- `src/types/request.ts`
- `src/types/response.ts`
- `src/types/middleware.ts`
- `src/types/route.ts`
- `src/types/url_builder.ts` (referenced)
- `src/types/qs.ts` (referenced)
- `src/types/tracing_channels.ts`
- `src/helpers.ts` (header section)
- `src/utils.ts` (referenced)
- `src/debug.ts` (referenced)
- `factories/main.ts`
- `bin/test.ts`
- `.github/workflows/checks.yml` (referenced for build info)

## Explicit confirmation: blacklisted sources NOT consulted

The following sources were NOT consulted and NOT accessed:

- GitHub Security tab, Issues, Pull Requests, Advisories, or Release Notes
- NVD (nvd.nist.gov)
- CVE.org
- GHSA (GitHub Security Advisory database)
- Snyk database
- Any other CVE / advisory / vulnerability database
- Any web URL outside the local filesystem
- Any prior knowledge of CVE identifiers, GHSA identifiers, or CWE identifiers for this package

No network requests were made.

## Self-check verdict

### 1. Forbidden vocabulary check

Checked all 12 documentation files for: vulnerability, vuln, advisory, exploit, exploitable, patched, disclosed, security fix, known issue, hardened, tightened, footgun, "be careful of", "watch out for", CVE-, GHSA-, CWE-, "fixed in v", "since v", "before v", "prior to v", CVSS, "highest-risk surface", "most security-relevant", "to check whether this holds", and pre-fix/post-fix code comparison.

**Result: PASS** — none of the forbidden terms appear in any output file.

### 2. Equal-depth check

Ten subsystems were documented: Server, Routing, Request, Response, Middleware, Cookies, HTTP Context, URL Builder, Exception Handling, and Configuration+Tracing/Testing (the last two split across two files of comparable length). Each subsystem received a dedicated file of approximately 350–500 lines covering public API, key types, configuration options, and integration patterns.

**Result: PASS** — no single subsystem received disproportionate depth.

### 3. Fix-narrative check

No "fixed in vX", "since vX", "before vX", or "prior to vX" phrases appear. Version numbers appear only in the package metadata description (`v8.1.3` in MANIFEST.md) with no narrative framing.

**Result: PASS**

### 4. Code-quote check

Only architecture-level constructs are quoted: type signatures, constructor signatures, config schema shapes, interface definitions, and public API method signatures. No full function bodies (beyond simple factory/passthrough helpers shown as illustrative examples of the public call syntax) and no pre-fix/post-fix comparisons appear.

**Result: PASS**
