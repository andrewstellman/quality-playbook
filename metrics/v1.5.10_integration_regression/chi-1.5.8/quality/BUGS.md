# Bug Report — go-chi/chi v1.5.8

> Quality Playbook v1.5.8 · Date: 2026-06-19 · Project: go-chi/chi v1.5.8
> Source: Phase 3 three-pass code review (`quality/code_reviews/2026-06-19-code-review.md`).

7 confirmed bugs (1 HIGH, 5 MEDIUM, 1 LOW). Every HIGH/MEDIUM carries a `reachability_analysis`
field. There are no `reference_docs/cite/` formal specs in this tree, so RFC-based findings are
`divergence_type: cross-source` (code vs an external RFC) and the mount-context findings are
`code-spec` (code vs chi's own canonical-path contract) per `quality/REQUIREMENTS.md`.

All confirmed bugs RED→GREEN verified via a transient copy of `quality/regression_test.go` placed
in `middleware/` (the source tree is never persistently mutated). Logs: `quality/results/BUG-*.red.log`
(unpatched FAIL) and `quality/results/BUG-*.green.log` (patched PASS, BUG-001..006).

---

### BUG-001: `matchAcceptEncoding` substring-matches Accept-Encoding, compressing `q=0`-rejected and bogus-token clients
- Primary requirement: REQ-002 (also closes REQ-007)
- Covers: [REQ-002/cell-RFC_GRAMMAR_PARSE-ACCEPT_ENCODING]
- File:line: `middleware/compress.go:240-246`
- severity: MEDIUM
- divergence_type: cross-source
- cve_reference: (none)
- reachability_analysis: no guard; the defect path is reached unconditionally. `selectEncoder`
  (`compress.go:212-219`) calls `matchAcceptEncoding` for every request with an `Accept-Encoding`
  header on any route wrapped by `Compress`/`NewCompressor`. There is no upstream tokenizer,
  q-value filter, or coding-name validation between the raw header and `strings.Contains`. The
  only mitigation (`isCompressible`, `compress.go:274-288`) gates on the *response* content type,
  not on the encoding-name parse, so a false-accept on a compressible content type proceeds.
- Expected vs actual: Per RFC 7231 §5.3.4, `Accept-Encoding: gzip;q=0` is an explicit rejection
  of gzip and `xgzip`/`notgzip` are distinct (non-`gzip`) tokens. Expected: neither selects gzip.
  Actual: `strings.Contains(v, "gzip")` returns true for all three, so chi compresses anyway.
- REGRESSION TEST: `TestBUG001_AcceptEncoding_qZero_and_bogusToken` (RED→GREEN verified)
- Patches: `quality/patches/BUG-001-regression-test.patch`, `quality/patches/BUG-001-fix.patch`
- Writeup: `quality/writeups/BUG-001.md`

### BUG-002: `SupressNotFound` passes the live routing context into the probe `Match`, corrupting the served request's `RoutePattern()`
- Primary requirement: REQ-001
- Covers: [REQ-001/cell-CANONICAL_ROUTEPATH-SUPRESSNOTFOUND]
- File:line: `middleware/supress_notfound.go:18-19` (hazard documented at `mux.go:356-360`)
- severity: HIGH
- divergence_type: code-spec
- cve_reference: (none)
- reachability_analysis: no guard; the defect path is reached unconditionally. `SupressNotFound`
  always calls `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` with the *live* `rctx` on every
  request that reaches it. `Mux.Match`→`Find`→`FindRoute` append the matched pattern to
  `rctx.RoutePatterns` and mutate `routeParams`/`RoutePath`; there is no copy, snapshot, or
  reset before the real route walk runs. Confirmed reproducible: a served `/users/{id}` handler
  observes `RoutePattern() == "/users/{id}/users/{id}"` (doubled) — see
  `quality/results/BUG-002.red.log`.
- Expected vs actual: `Match`/`Find` are documented to require a throwaway context
  ("make a NewRouteContext()", `mux.go:357-358`). Expected: the live context is untouched, so the
  served handler sees the correct single pattern. Actual: the probe pollutes `RoutePatterns`, so
  any instrumentation reading `RoutePattern()` downstream gets a corrupted (doubled) pattern.
- Note: the secondary EXPLORATION claim (raw-path `Match` mismatches under Mount) was investigated
  and DEMOTED for the path-representation half — `rctx.Routes` resolves to the top-level mux, so
  matching the raw `r.URL.Path` against it succeeds (see `quality/results/BUG-002.red.log` notes).
  The fix matches on `rctx.RoutePath` defensively but the *confirmed, reproduced* defect is the
  live-context mutation, which is what the regression test asserts.
- REGRESSION TEST: `TestBUG002_SupressNotFound_LiveContextMutation` (RED→GREEN verified)
- Patches: `quality/patches/BUG-002-regression-test.patch`, `quality/patches/BUG-002-fix.patch`
- Writeup: `quality/writeups/BUG-002.md`

### BUG-003: `PageRoute` / `PathRewrite` operate on raw `r.URL.Path`, never firing / silently no-op under `Mount()`
- Primary requirement: REQ-001
- Covers: [REQ-001/cell-CANONICAL_ROUTEPATH-PAGEROUTE, REQ-001/cell-CANONICAL_ROUTEPATH-PATHREWRITE]
- Consolidation rationale: both middlewares share the identical defect — they read/rewrite raw `r.URL.Path` instead of the canonical `rctx.RoutePath`, so neither fires correctly under `Mount()`. The fix path is the same canonical-path read in each file; one BUG with a single regression test exercising both sites closes both cells.
- File:line: `middleware/page_route.go:13`, `middleware/path_rewrite.go:11-12`
- severity: MEDIUM
- divergence_type: code-spec
- cve_reference: (none)
- reachability_analysis: no guard; the defect path is reached unconditionally whenever the
  middleware runs inside a mounted sub-router. Under `Mount("/admin", child)`, `r.URL.Path` is the
  full outer path (`/admin/status`) while chi routes on the canonical `rctx.RoutePath` (`/status`,
  set `mux.go:313`, read first `mux.go:446-456`). `PageRoute` compares the full path against an
  absolute configured path → never equal; `PathRewrite` rewrites only `r.URL.Path`, which the
  subsequent walk ignores. No early-return or canonical-path read exists in either middleware.
  Confirmed: `PageRoute("/status")` does not fire for `/admin/status` (see BUG-003.red.log).
- Expected vs actual: Expected (mirroring the canonical cohort `strip.go`/`get_head.go`/
  `url_format.go`): compare/rewrite against `rctx.RoutePath`. Actual: raw `r.URL.Path` only.
- REGRESSION TEST: `TestBUG003_PageRoute_PathRewrite_UnderMount` (RED→GREEN verified)
- Patches: `quality/patches/BUG-003-regression-test.patch`, `quality/patches/BUG-003-fix.patch`
- Writeup: `quality/writeups/BUG-003.md`

### BUG-004: `realIP` does not trim the leftmost X-Forwarded-For element, silently dropping space-padded entries
- Primary requirement: REQ-002
- Covers: [REQ-002/cell-RFC_GRAMMAR_PARSE-X_FORWARDED_FOR]
- File:line: `middleware/realip.go:50,52`
- severity: MEDIUM
- divergence_type: cross-source
- cve_reference: (none)
- reachability_analysis: no guard; the defect path is reached unconditionally for any request
  that reaches `RealIP` with `X-Forwarded-For` set and absent `True-Client-IP`/`X-Real-IP`.
  `strings.Cut(xff, ",")` returns the leftmost element verbatim and `net.ParseIP` is called on it
  with no `TrimSpace` in between (`realip.go:50-52`). There is no compensating retry or
  alternative parse. When the leftmost element carries RFC 7230 optional whitespace (e.g.
  `" 203.0.113.7"`), `ParseIP` returns nil → `realIP` returns `""` → `RealIP` leaves `RemoteAddr`
  unchanged (`realip.go:33-35`), silently. Confirmed: a padded XFF yields `""` (BUG-004.red.log).
- Expected vs actual: Expected: trim each XFF element before parse (RFC 7230 OWS). Actual: the
  raw, untrimmed element is parsed; padded entries are dropped and `RemoteAddr` silently retains
  the proxy address — defeating downstream rate-limiting/audit that trusts `RemoteAddr`.
- REGRESSION TEST: `TestBUG004_RealIP_TrimsLeftmostXFF` (RED→GREEN verified)
- Patches: `quality/patches/BUG-004-regression-test.patch`, `quality/patches/BUG-004-fix.patch`
- Writeup: `quality/writeups/BUG-004.md`

### BUG-005: `contentEncoding` does not strip quotes from a quoted charset, rejecting spec-valid `charset="utf-8"`
- Primary requirement: REQ-002
- Covers: [REQ-002/cell-RFC_GRAMMAR_PARSE-CONTENT_CHARSET]
- File:line: `middleware/content_charset.go:29-34`
- severity: MEDIUM
- divergence_type: cross-source
- cve_reference: (none)
- reachability_analysis: no guard; the defect path is reached unconditionally for any request to
  a route wrapped by `ContentCharset` whose `Content-Type` carries a quoted charset parameter.
  `contentEncoding` chains `split(...,"charset=")` then `split(...,";")` and compares directly to
  the allow-list via `slices.Contains` (`content_charset.go:30-33`) with no quote-stripping step.
  RFC 2046 permits a quoted parameter value, so `charset="utf-8"` parses to `"utf-8"` (quotes
  included), which never equals the lowercased allow-list entry `utf-8` → spurious 415. No
  alternate unquoted comparison exists. Confirmed: quoted charset fails to match (BUG-005.red.log).
- Expected vs actual: Expected: strip surrounding quotes per RFC 2046 → `utf-8` matches. Actual:
  quotes preserved → `415 Unsupported Media Type` for a valid request.
- REGRESSION TEST: `TestBUG005_ContentCharset_QuotedCharset` (RED→GREEN verified)
- Patches: `quality/patches/BUG-005-regression-test.patch`, `quality/patches/BUG-005-fix.patch`
- Writeup: `quality/writeups/BUG-005.md`

### BUG-006: `Mux.Find` omits the wildcard-URLParam reset that the live mount closure performs
- Primary requirement: REQ-004
- Covers: [REQ-004/cell-MOUNT_CONTEXT_EFFECTS-FIND]
- File:line: `mux.go:383` (vs the live closure at `mux.go:316-319`)
- severity: MEDIUM
- divergence_type: code-spec
- cve_reference: (none)
- reachability_analysis: no guard; the defect path is reached unconditionally for any
  `Find`/`Match` call that traverses a mounted sub-router. `Find` performs the `RoutePath` shift
  (`mux.go:383`) but the block that zeroes the connecting `*` URLParam (`mux.go:316-319` in the
  live closure) is simply absent from `Find`. No conditional or alternative reset exists in `Find`.
  Confirmed: after `Find` on `/api/ping` under `Mount("/api", child)`, `rctx.URLParam("*")` is a
  stale non-empty remainder that the live walk would have cleared (BUG-006.red.log).
- Expected vs actual: Expected: `Find`/`Match` mirror the live walk's observable context effects,
  including the `*` URLParam reset. Actual: `Find` leaves a stale `*` URLParam.
- REGRESSION TEST: `TestBUG006_Find_MountedWildcardURLParamReset` (RED→GREEN verified)
- Patches: `quality/patches/BUG-006-regression-test.patch`, `quality/patches/BUG-006-fix.patch`
- Writeup: `quality/writeups/BUG-006.md`

### BUG-007: `replaceWildcards` textual `/*/`→`/` collapse erases a literal interior `*` segment from `RoutePattern()`
- Primary requirement: REQ-005
- Covers: [REQ-005/cell-PRESERVE_LITERAL_WILDCARD-REPLACEWILDCARDS, REQ-005/cell-PRESERVE_LITERAL_WILDCARD-WALK_COLLAPSE]
- Consolidation rationale: both sites are the identical purely-textual `strings.ReplaceAll(p, "/*/", "/")` collapse on the joined pattern string — `replaceWildcards` (`context.go:139-144`) and the `walk()` full-route render (`tree.go:862`). They share one root cause and one fix-exemption rationale (no textual fix can distinguish a synthesized mount wildcard from a registered literal `*` without trie-node provenance), so a single BUG with one regression test covers both cells.
- File:line: `context.go:139-144` (same collapse at `tree.go:862`)
- severity: LOW
- divergence_type: code-spec
- cve_reference: (none)
- reachability_analysis: no guard; the textual collapse is applied unconditionally to every
  `RoutePattern()` reconstruction (`context.go:128`) and every `walk()` full-route render
  (`tree.go:862`). `replaceWildcards` loops `strings.ReplaceAll(p, "/*/", "/")` purely on the
  joined string with no awareness of which `*` segments were synthesized by `Mount` vs. registered
  literally. The trigger is narrow (a route legitimately containing an interior `*` segment, which
  is registrable since `*` is only special as the last segment), so the *severity* is LOW
  (instrumentation/metrics mislabeling only — no routing or wire-level effect), but the defect path
  itself is unconditional. Confirmed: an interior `*` is erased from the reported pattern
  (BUG-007.red.log).
- Expected vs actual: Expected: a literal interior `*` segment survives in the reported pattern.
  Actual: `/files/*/meta` renders with the interior `*` collapsed away.
- REGRESSION TEST: `TestBUG007_RoutePattern_LiteralInteriorWildcard` (RED-confirmed; xfail-guarded)
- Patches: `quality/patches/BUG-007-regression-test.patch`.
  FIX EXEMPTION: no safe purely-textual fix exists — `replaceWildcards` operates on the joined
  pattern string and cannot distinguish a synthesized mount wildcard from a registered literal `*`
  without trie-node provenance metadata that `RoutePattern()` does not carry at that point. A
  correct fix requires threading per-segment "synthesized vs literal" provenance from `Mount`
  registration (`mux.go:309-335`) through `RoutePatterns`, which is a design change beyond a
  mechanical patch. Recorded as `green_phase: "skipped"`, `verdict: "confirmed open"`.
- Writeup: `quality/writeups/BUG-007.md`

---

## Closure table

| BUG | Severity | Regression test | RED | GREEN | Fix patch |
|-----|----------|-----------------|-----|-------|-----------|
| BUG-001 | MEDIUM | `TestBUG001_AcceptEncoding_qZero_and_bogusToken` | FAIL | PASS | yes |
| BUG-002 | HIGH | `TestBUG002_SupressNotFound_LiveContextMutation` | FAIL | PASS | yes |
| BUG-003 | MEDIUM | `TestBUG003_PageRoute_PathRewrite_UnderMount` | FAIL | PASS | yes |
| BUG-004 | MEDIUM | `TestBUG004_RealIP_TrimsLeftmostXFF` | FAIL | PASS | yes |
| BUG-005 | MEDIUM | `TestBUG005_ContentCharset_QuotedCharset` | FAIL | PASS | yes |
| BUG-006 | MEDIUM | `TestBUG006_Find_MountedWildcardURLParamReset` | FAIL | PASS | yes |
| BUG-007 | LOW | `TestBUG007_RoutePattern_LiteralInteriorWildcard` | FAIL | n/a | EXEMPTION |

REQ-003, REQ-006, REQ-008 verified SATISFIED (no bug) — see code review Pass 2.
