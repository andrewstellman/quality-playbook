# Phase 1 Exploration — go-chi/chi v1.5.8 (HTTP router)

**Target:** `github.com/go-chi/chi/v5` — a small, idiomatic, composable HTTP router for Go, built on a modified radix trie. Clean checkout commit `a54874f0` (branch `master`), see `.clean_checkout`.

**Domain & stack.** Go (module `go.mod`: `github.com/go-chi/chi/v5`, Go 1.26 toolchain available). Pure `net/http` router + a large middleware suite. The library's job is request multiplexing: parse a request path, match it against registered patterns in a radix trie (`tree.go`), capture URL params into a pooled routing `Context` (`context.go`), and dispatch to the matched `http.Handler` through a middleware chain (`chain.go`, `mux.go`). The composability story (sub-routers via `Mount`/`Route`, inline groups via `Group`/`With`) is chi's defining feature and its largest risk surface.

**Architecture map (entry points → modules).**
- `chi.go` — public package surface: `NewRouter()`, the `Router`/`Routes` interfaces, `Middlewares` type, package doc describing pattern grammar (`{name}`, `{name:regexp}`, `*`).
- `mux.go` — `Mux` (the `Router` implementation): registration (`Handle`/`Method`/verb helpers/`Mount`/`Route`/`Group`/`With`), request dispatch (`ServeHTTP` → `routeHTTP`), 404/405 handlers, sub-router path shifting (`nextRoutePath`).
- `tree.go` — the radix trie: node types (`ntStatic`/`ntRegexp`/`ntParam`/`ntCatchAll`), the method bitmask closed set (`methodMap`/`reverseMethodMap`/`mALL`), `InsertRoute`/`findRoute`/`FindRoute`, pattern parsing (`patNextSegment`/`patParamKeys`), and tree walking (`routes()`/`Walk`).
- `context.go` — the per-request `Context` (URL params, `RoutePath`, `RoutePattern()`), `RouteContext()` accessor, `RouteParams`.
- `chain.go` — middleware composition (`Chain`, `ChainHandler`, `chain()`).
- `middleware/` — ~40 standalone middleware (compression, content negotiation, real-IP, slash/path manipulation, throttle, timeout, recoverer, logging, etc.), each its own `http.Handler` decorator.

**Existing test inventory.** ~90 `func Test*` across 21 `_test.go` files (~5,000 LOC of tests). Heaviest: `mux_test.go` (57 KB), `tree_test.go` (24 KB), `middleware/strip_test.go`, `middleware/throttle_test.go`, `middleware/route_headers_test.go`. Notable coverage gaps surfaced below: `middleware/compress_test.go` has NO test for `Accept-Encoding: gzip;q=0` or `xgzip` (the substring-match shortcut is untested); `middleware/supress_notfound.go` has no test file at all.

**Reference docs.** `reference_docs/` is present (18 Tier-4 files: overview, routing fundamentals, middleware system, context/values, error handling, testing, performance, advanced topics, changelog). There is NO `reference_docs/cite/` subdirectory, so there are zero citable formal-spec sources — all reference material is Tier 4 context. (`docs_gathered/` is a duplicate of the same set.) The authoritative specs for the parsing findings below (RFC 7231 Accept-Encoding/`q=0`, RFC 7239/7230 X-Forwarded-For, RFC 2046 charset parameters) are external standards, not files in this tree.

**File-role tagging summary.** `quality/exploration_role_map.json` enumerates 94 in-scope chi files. Provenance is `filesystem-walk-with-skips` (see Finding 8): the target is gitignored inside the parent QPB repo, so `git ls-files` returns 0 entries and a filesystem walk with explicit skips is the only viable enumeration. Breakdown: 34 `code` (core router + middleware `.go`), 21 `test`, 28 `docs` (README/CHANGELOG/CONTRIBUTING/SECURITY + `_examples/`), 9 `config` (`go.mod`/`go.sum`/`Makefile`/`.gitignore`/`LICENSE`/`.clean_checkout`), 2 `fixture` (`testdata/*.pem`). Zero `skill-prose`/`skill-reference`/`skill-tool`/`playbook-output` entries: chi has no skill surface, and the vendored QPB infrastructure (`.github/skills/`, `bin/`, `reference_docs/`, `docs_gathered/`) is excluded from the role map as non-intrinsic to chi.

---

## Open Exploration Findings

1. **`Accept-Encoding` is matched by substring, not by RFC token + q-value (multi-location trace).** `Compressor.selectEncoder` lowercases the header and splits on `,` (`middleware/compress.go:212-215`), then `matchAcceptEncoding` decides a candidate encoding is accepted iff `strings.Contains(v, encoding)` for any comma-element (`middleware/compress.go:240-246`). This is a spec shortcut with two concrete defects: (a) `Accept-Encoding: gzip;q=0` — an explicit *rejection* of gzip per RFC 7231 §5.3.4 — still contains the substring `gzip`, so chi compresses anyway; (b) a bogus token such as `xgzip` or `notgzip` contains `gzip` and falsely matches. The comma-split element is never trimmed and the `;q=` parameter is never parsed. `middleware/compress_test.go` (217 lines) exercises only well-formed single/multi encodings and has zero cases for `q=0` or substring false-positives, so the defect is invisible to the suite.

2. **`RealIP` reads the leftmost X-Forwarded-For element with no whitespace trim and a `net.ParseIP` gate that silently drops valid forms (multi-location trace).** `realIP` prefers `True-Client-IP`, then `X-Real-IP`, then takes the first comma-segment of `X-Forwarded-For` via `strings.Cut(xff, ",")` (`middleware/realip.go:42-51`), then requires `net.ParseIP(ip) != nil` or returns `""` (`middleware/realip.go:52-55`). Concerns: the cut result is not `TrimSpace`d, so a header like `X-Forwarded-For: 203.0.113.1, 10.0.0.1` is fine (no leading space on element 0) but any producer that emits a leading space before the first element yields `" 203.0.113.1"` which `ParseIP` rejects → RemoteAddr silently unchanged. `ParseIP` also rejects `host:port` and zone-id forms, so those XFF entries are dropped with no signal. The function caller (`RealIP`, `middleware/realip.go:31-40`) only overwrites `RemoteAddr` when `rip != ""`, so failures are silent (the original `RemoteAddr` survives), masking the parse gap.

3. **`SupressNotFound` matches the *raw* request path under composition and mutates the live routing context (multi-location trace).** `SupressNotFound` calls `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` (`middleware/supress_notfound.go:18-19`). It reads `r.URL.Path` (the full, outer URL) rather than the canonical mounted path `rctx.RoutePath` that `mux.go` maintains under `Mount()` (`mux.go:309-322` sets `rctx.RoutePath = mx.nextRoutePath(rctx)` when shifting into a sub-router; `mux.go:441-456` reads `rctx.RoutePath` first). When this middleware runs inside a mounted sub-router, `r.URL.Path` includes the mount prefix while the sub-router's trie is keyed on the mount-relative path → `Match` can mismatch. Compounding this, it passes the **live** `rctx` (not a throwaway `NewRouteContext()`) into `Match`, and `Mux.Match`/`Find` explicitly warn "the *Context state is updated during execution" (`mux.go:356-368`) — so a probe mutates the very context the real route walk will use. There is no `supress_notfound_test.go`, so neither the mount mismatch nor the context mutation is covered.

4. **The HTTP-method closed set is a hand-maintained bitmask shared across three structures that must stay in lock-step (multi-location trace).** Recognized methods live in `methodMap` (`tree.go:35-45`), the reverse map `reverseMethodMap` (`tree.go:47-57`), and the aggregate `mALL` (`tree.go:32-33`); `RegisterMethod` must update all three plus the bit width guard (`tree.go:61-77`). `routeHTTP` rejects a request whose `RouteMethod` is absent from `methodMap` with a 405 (`mux.go:462-466`), and `methodNotAllowedHandler` builds the `Allow` header from `reverseMethodMap` (`mux.go:518-526`). Any method present in one map but not the others (e.g. a future `RegisterMethod` path-skip, or `mALL` not OR-ing a new bit) silently breaks `Allow`-header reporting or wildcard registration. This is the Enumeration-Completeness pattern applied to chi's own method registry.

5. **`Mount` path-shift and wildcard reset are duplicated between the live dispatch closure and `Find` (multi-location trace).** The mount handler shifts the path with `rctx.RoutePath = mx.nextRoutePath(rctx)` and zeroes the connecting `*` URLParam (`mux.go:309-322`). `nextRoutePath` reconstructs the child-relative path from the last `*` routeParam (`mux.go:487-494`). `Mux.Find` re-implements the same shift (`mux.go:383-390`) for the no-execute lookup path but does NOT perform the wildcard-URLParam reset that the live closure does (`mux.go:316-319`). This is a cross-implementation parity surface: `Find`/`Match` are supposed to mirror real routing "without executing the handler" (`mux.go:353-368`), but the URLParam side-effect diverges — a `Find` against a mounted route leaves a stale `*` value the live path would have cleared.

6. **`RoutePattern()` reconstruction relies on iterative `/*/`→`/` collapse that can mis-handle a literal `*` segment.** `Context.RoutePattern()` joins the recorded `RoutePatterns` stack and calls `replaceWildcards` (`context.go:123-134`), which loops `strings.ReplaceAll(p, "/*/", "/")` until no `/*/` remains (`context.go:136-144`). `walk()` does the same collapse on full routes (`tree.go:862`). The collapse is purely textual: a route that legitimately contained a literal `*` segment (registrable, since `*` is only special as the *last* segment per `patNextSegment`, `tree.go:687-753`) would have an interior `/*/` rewritten away, corrupting the reported pattern used by instrumentation/metrics middleware. The TrimSuffix logic for trailing `//` and `/` (`context.go:129-132`) is also order-sensitive.

7. **Path-manipulation middleware split into a canonical-aware cohort and a raw-`URL.Path` cohort (multi-location trace).** Canonical-aware (read/write `rctx.RoutePath`): `StripSlashes` (`middleware/strip.go:17-29`), `RedirectSlashes` (`middleware/strip.go:44-49`), `GetHead` (`middleware/get_head.go:13-31`), `CleanPath` (`middleware/clean_path.go`), `URLFormat` (`middleware/url_format.go:54-67`). Raw-only (read/write `r.URL.Path`, ignoring chi's canonical mounted path): `SupressNotFound` (`middleware/supress_notfound.go:19`), `PageRoute` (`middleware/page_route.go:13`), `PathRewrite` (`middleware/path_rewrite.go:11-12`). The raw cohort behaves correctly at the top level (where `RoutePath == URL.Path`) but drifts under `Mount()`. This asymmetry is promoted to REQ-001 below.

8. **Target is not an enumerable git repo from this vantage; role map uses filesystem-walk provenance.** `git rev-parse --is-inside-work-tree` is `true`, but `git rev-parse --show-toplevel` resolves to `/Users/andrewstellman/Documents/QPB` and `git check-ignore` shows `repos/` is gitignored by the parent (`.gitignore:25:repos/`). Consequently `git ls-files` inside `repos/chi-1.5.8/` returns 0 entries — chi's files are untracked from the parent's perspective and there is no nested `.git` for chi itself. Per the SKILL.md provenance contract (`SKILL.md:180`), the role map records `provenance: "filesystem-walk-with-skips"` with explicit skips for `.git/`, the vendored QPB infra dirs, and all disallowed cache/build prefixes. The QPB infrastructure layered into this directory (`.github/skills/`, `bin/`, `reference_docs/`, `docs_gathered/`) is excluded from the role map as non-intrinsic to chi (it would otherwise inflate chi's apparent code surface — the v1.5.3 LOC-pollution failure mode).

9. **`compressResponseWriter.WriteHeader` and `selectEncoder` together can declare `Content-Encoding` for a body that was never compressed.** `selectEncoder` returns a non-empty `encoding` name purely from the (substring-matched, Finding 1) `Accept-Encoding` header (`middleware/compress.go:210-238`). `WriteHeader` then, if `cw.encoding != ""` and the content type is compressible, sets `Content-Encoding: <encoding>` and deletes `Content-Length` (`middleware/compress.go:308-315`) BEFORE the body is written. Because the actual encoder writer is only swapped in via `writer()` when `cw.compressible` (`middleware/compress.go:326-331`), the header/state coupling across `selectEncoder` → `WriteHeader` → `writer` is the surface where a substring-induced false accept (Finding 1) turns into a wire-level `Content-Encoding: gzip` on uncompressed bytes for `xgzip` clients.

10. **`findRoute` param backtracking maintains a manual value stack whose unwind is split across two cleanup sites.** `findRoute` pushes a candidate param value (`tree.go:457-458`), recurses, and on failure truncates back via `rctx.routeParams.Values[:prevlen]` (`tree.go:488-490`); a second, structurally similar unwind for non-static nodes happens at function tail (`tree.go:534-539`). The two cleanup paths must keep `routeParams.Keys` and `routeParams.Values` length-consistent; `FindRoute` later appends `paramKeys` to `URLParams` assuming exact correspondence (`tree.go:386-394`). Any path where a value is pushed but its key is not appended (or vice versa) yields a Keys/Values length skew that `Context.URLParam` (`context.go:100-107`) reads by index — a silent param-misalignment risk under deep backtracking with mixed param/regexp/catch-all siblings.

---

## Quality Risks

1. **Composition-time path representation (highest risk).** chi's entire value proposition is `Mount`/`Route` composition, yet three middleware (`SupressNotFound`, `PageRoute`, `PathRewrite`) read or write `r.URL.Path` instead of the canonical `rctx.RoutePath`. Under a mounted sub-router these silently misroute or never match. Edge case: `root.Mount("/api", child)` then a request to `/api/ping` — the middleware sees `/api/ping` but the child trie is keyed on `/ping`, so it produces a wrong 404 / never-match. Concretely visible at `middleware/supress_notfound.go:19`, `middleware/page_route.go:13`, `middleware/path_rewrite.go:11-12` vs the canonical handling in `mux.go:309-322` / `mux.go:441-456`.

2. **RFC-shortcut content negotiation produces wrong wire behavior.** `matchAcceptEncoding` (`middleware/compress.go:240-246`) uses `strings.Contains`, so the edge case `Accept-Encoding: gzip;q=0` (explicit rejection) still matches and the response is compressed anyway — the code does the opposite of what the client asked. Same shortcut family: `contentEncoding`/charset parsing splits on `;`/`charset=` without quoted-string awareness (`middleware/content_charset.go:29-34`), so `charset="utf-8"` fails to match. These pass the suite because tests use canonical inputs.

3. **Hand-maintained closed sets drift silently.** The method bitmask trio (`tree.go:32-57`) and the `defaultCompressibleContentTypes` whitelist (`middleware/compress.go:16-27`) are closed sets that must track external definitions. Edge case: `RegisterMethod` (`tree.go:61-77`) updating `methodMap` but a future change forgetting `mALL` — wildcard registration at `tree.go:355-365` then skips the method, and the 405 `Allow` builder (`mux.go:518-526`) reports the wrong allowed-set, both with no error.

4. **Live-context mutation by probes corrupts the in-flight walk.** `Mux.Match`/`Find` mutate the passed `*Context` (`mux.go:356-368`), and `SupressNotFound` passes the live `rctx` (`middleware/supress_notfound.go:19`). Edge case: the probe `Match` writes `routeParams`/`routePattern` into the very context the real route walk will then read, so the documented-but-unenforced "make a NewRouteContext()" contract being ignored can leak probe state into the served request.

5. **`net.ParseIP` over-rejection in RealIP fails silently.** Because `RealIP` only overwrites `RemoteAddr` on a non-empty parse (`middleware/realip.go:33-35,52-55`), every parse failure leaves the original `RemoteAddr`. Edge case: an `X-Forwarded-For` first element with a leading space or a `host:port` form (`middleware/realip.go:50,52`) — `ParseIP` returns nil, the middleware returns `""`, and operators relying on `RemoteAddr` for rate-limiting/audit unknowingly get the proxy's address instead of the client's.

6. **Textual wildcard collapse corrupts reported patterns.** `replaceWildcards` (`context.go:136-144`) and the `walk` collapse (`tree.go:862`) rewrite any `/*/`, not only synthesized mount wildcards. Edge case: a registered pattern with a legitimate interior segment that renders as `/*/` after the patterns are joined — the collapse erases it, so instrumentation reading `RoutePattern()` (`context.go:123-134`) reports a pattern that never existed, mislabeling metrics.

---

## Pattern Applicability Matrix

| # | Pattern | Decision | Rationale |
|---|---------|----------|-----------|
| 1 | Fallback and Degradation Path Parity | SKIP | chi has few primary/fallback cascades; the closest (default-vs-custom NotFound/MethodNotAllowed at `mux.go:396-412`) is thin and well-covered. Lower yield than the patterns chosen. |
| 2 | Dispatcher Return-Value Correctness | SKIP | `routeHTTP`/`findRoute` return handler-or-nil rather than status codes; the `methodNotAllowed` flag path (`tree.go:478,524`; `mux.go:480-484`) is the only dispatcher seam and is partially covered. Folded into Pattern 3/7 traces instead. |
| 3 | Cross-Implementation Contract Consistency | FULL | Multiple parallel implementations of the same operation: path-handling middleware cohort (canonical vs raw), and the `Mount`-shift logic duplicated between the dispatch closure and `Find` (`mux.go:309-322` vs `mux.go:383-390`). Strong yield. |
| 4 | Enumeration and Representation Completeness | FULL | chi maintains explicit closed sets: the HTTP-method bitmask trio (`tree.go:32-57`) gated by `RegisterMethod`, and the compressible content-type whitelist (`middleware/compress.go:16-27`). Classic missing-entry / drift surface. |
| 5 | API Surface Consistency | SKIP | Surface pairs exist (`Handle` vs `Method`, `Routes()` vs `Walk`) but behave consistently; no high-signal divergence found in open exploration. Deprioritized in favor of 6/7. |
| 6 | Spec-Structured Parsing Fidelity | FULL | The richest seam: `Accept-Encoding` substring match (`compress.go:240-246`), charset split (`content_charset.go:29-34`), X-Forwarded-For cut (`realip.go:50`), Content-Type media-type cut (`content_type.go`). RFC-defined grammars parsed with shortcuts. |
| 7 | Composition and Mount-Context Awareness | FULL | chi is the canonical example for this pattern. `RoutePath`/`RoutePattern` canonical state vs raw `r.URL.Path`; `SupressNotFound`/`PageRoute`/`PathRewrite` read/write the wrong representation under `Mount()`. Highest-impact pattern for this target. |

(3 FULL? — count: Patterns 3, 4, 6, 7 = **4 FULL**, within the 3–4 band.)

---

## Pattern Deep Dive — Spec-Structured Parsing Fidelity

Authoritative grammars: RFC 7231 §5.3.4 (Accept-Encoding, q-values), RFC 7230 §3.2.6 (token/comma-list/whitespace), RFC 2046 (media-type `charset` parameter), RFC 7239 (Forwarded / X-Forwarded-For convention).

- **`matchAcceptEncoding` — substring match (multi-identifier trace).** `selectEncoder` builds `accepted = strings.Split(strings.ToLower(header), ",")` (`middleware/compress.go:215`) and iterates `c.encodingPrecedence` calling `matchAcceptEncoding(accepted, name)` (`middleware/compress.go:218-219`). `matchAcceptEncoding` returns true on the first `strings.Contains(v, encoding)` (`middleware/compress.go:240-246`). Trace across `selectEncoder` → `matchAcceptEncoding` → `WriteHeader` (`compress.go:308-315`): a `q=0` rejection or an `xgzip` token survives the match and reaches the header-setting code. Spec-valid breaking input: `Accept-Encoding: gzip;q=0` (must NOT compress) and `Accept-Encoding: xgzip` (not a registered coding). No comma-element `TrimSpace`; no `;q=` parse.
- **`contentEncoding` / charset parse (multi-identifier trace).** `ContentCharset` → `contentEncoding` → `split` (`middleware/content_charset.go:18,29-34,37-45`). `split` cuts on a separator and `TrimSpace`s both halves; `contentEncoding` chains `split(...";")`, `split(...,"charset=")`, `split(...";")` then `slices.Contains(charsets, ce)`. Breaks on a quoted charset (`charset="utf-8"` keeps the quotes → no match) and on a `charset` substring inside another parameter value. The function name (`contentEncoding`) does not match what it parses (charset) — a maintainability hazard.
- **`realIP` X-Forwarded-For cut.** `strings.Cut(xff, ",")` takes the leftmost element (`middleware/realip.go:50`) with no trim, then `net.ParseIP` (`middleware/realip.go:52`). Spec-valid breaking inputs: a producer that pads with a space, or an entry carrying a port/zone. The leftmost-element choice itself is a trust-model decision (RFC 7239 leaves direction to deployment) that the doc comment (`middleware/realip.go:24-30`) flags but the parser hard-codes.
- **`AllowContentType` media-type cut.** `strings.Cut(Content-Type, ";")` then lowercase compare against the allow-set (`middleware/content_type.go`), no whitespace handling around `/` and no validation of `type/subtype` shape — a milder instance of the same shortcut family.

## Pattern Deep Dive — Composition and Mount-Context Awareness

Canonical state chi maintains under composition: `rctx.RoutePath` (active mounted path, set at `mux.go:313` and `mux.go:383`) and `rctx.RoutePattern()` (`context.go:123-134`). Raw state: `r.URL.Path` (full request URL, unchanged by mounting).

- **`SupressNotFound` reads raw path AND mutates live context (multi-identifier trace: `Match` + `RoutePath` + `r.URL.Path`).** `rctx.Routes.Match(rctx, r.Method, r.URL.Path)` (`middleware/supress_notfound.go:19`) reads `r.URL.Path` where canonical `rctx.RoutePath` is required under `Mount()` (canonical set at `mux.go:309-313`), and passes the live `rctx` into `Match` whose state-mutation hazard is documented at `mux.go:356-360`. Drift scenario: `root.Mount("/api", child)`, `child` uses `SupressNotFound`; request `/api/ping` → `Match` is called with `/api/ping` against the child trie keyed on `/ping` → spurious 404.
- **`PageRoute` raw equality (multi-location trace).** `strings.EqualFold(r.URL.Path, path)` (`middleware/page_route.go:13`) compares the full URL against an absolute configured path. Under `Mount("/admin", child)` with `PageRoute("/status", ...)`, request `/admin/status` has `r.URL.Path == "/admin/status"` ≠ `/status` → never matches. Correct representation is `rctx.RoutePath`.
- **`PathRewrite` rewrites raw path only (multi-location trace).** `strings.Replace(r.URL.Path, old, new, 1)` and writes back `r.URL.Path` (`middleware/path_rewrite.go:11-12`) without updating `rctx.RoutePath`. When mounted, the subsequent chi route walk reads `rctx.RoutePath` first (`mux.go:446-456`), so the rewrite is invisible to routing — the rewrite "succeeds" on `r.URL.Path` but chi routes the un-rewritten canonical path.
- **Contrast — the canonical-aware cohort gets it right.** `StripSlashes` reads `rctx.RoutePath` first and writes it back (`middleware/strip.go:17-29`); `GetHead` reads `rctx.RoutePath` with a `RawPath`/`Path` fallback only when empty (`middleware/get_head.go:13-21`); `URLFormat` updates `rctx.RoutePath` (`middleware/url_format.go:54-67`). The split between the two cohorts (Finding 7) is the asymmetry promoted to REQ-001.

## Pattern Deep Dive — Enumeration and Representation Completeness

- **HTTP-method bitmask trio (multi-identifier trace: `methodMap` + `reverseMethodMap` + `mALL`).** The closed set is defined three ways that MUST stay consistent: `methodMap` (string→bit, `tree.go:35-45`), `reverseMethodMap` (bit→string, `tree.go:47-57`), and `mALL` (OR of all bits, `tree.go:32-33`). `RegisterMethod` updates all three plus a bit-width guard (`tree.go:61-77`). Consumers: `routeHTTP` 405s on absence from `methodMap` (`mux.go:462-466`); the 405 handler builds `Allow` from `reverseMethodMap` (`mux.go:518-526`); `setEndpoint` fans a wildcard registration across every `methodMap` entry (`tree.go:355-365`). A method added to one map but not the others (or `mALL` not updated) silently drops it from `Allow` reporting or from `mALL` route registration. Authoritative source: the `net/http.Method*` constants the maps mirror (`tree.go:36-44`).
- **Compressible content-type whitelist (multi-location trace).** `defaultCompressibleContentTypes` (`middleware/compress.go:16-27`) is the closed set that gates whether a response body is eligible for compression; `isCompressible` checks membership after stripping params (`middleware/compress.go:274-288`). Missing common types (e.g. `application/vnd.api+json`, `text/csv`, `application/ld+json`) are silently not compressed — the "feature is defined but silently inert" signature of this pattern. The wildcard set (`allowedWildcards`, `compress.go:53,283-285`) partially mitigates only when the operator configures `type/*`.

---

## Candidate Bugs for Phase 2

1. **`matchAcceptEncoding` substring match compresses `q=0`-rejected and bogus-token (`xgzip`) clients.**
   - Stage: Spec-Structured Parsing Fidelity
   - `middleware/compress.go:240-246` (+ `compress.go:212-215`, `compress.go:308-315`). Promote to a requirement that Accept-Encoding be tokenized per RFC 7231 with `q=0` honored and exact coding-name match.

2. **`SupressNotFound` misroutes under `Mount()` and mutates the live routing context.**
   - Stage: Composition and Mount-Context Awareness
   - `middleware/supress_notfound.go:18-19` vs canonical `rctx.RoutePath` (`mux.go:309-313`, `mux.go:441-456`) and the live-context mutation hazard (`mux.go:356-360`).

3. **`PageRoute` / `PathRewrite` operate on raw `r.URL.Path`, never matching / silently no-op under mounting.**
   - Stage: open exploration
   - `middleware/page_route.go:13`, `middleware/path_rewrite.go:11-12`. (Asymmetry promoted to REQ-001.)

4. **`RealIP` silently leaves `RemoteAddr` unchanged on spec-valid-but-unparseable X-Forwarded-For (no trim, `net.ParseIP` over-rejection).**
   - Stage: quality risks
   - `middleware/realip.go:42-56`.

5. **HTTP-method closed-set trio can drift (`methodMap`/`reverseMethodMap`/`mALL`), corrupting `Allow` headers or wildcard registration.**
   - Stage: Enumeration and Representation Completeness
   - `tree.go:32-77`, consumed at `mux.go:518-526` and `tree.go:355-365`.

6. **`Mux.Find` omits the wildcard-URLParam reset that the live mount closure performs, diverging from real routing.**
   - Stage: open exploration + Cross-Implementation Contract Consistency
   - `mux.go:383-390` vs `mux.go:309-322`.

7. **`replaceWildcards` textual `/*/`→`/` collapse corrupts patterns containing a literal interior `*` segment.**
   - Stage: quality risks
   - `context.go:136-144`, `tree.go:862`.

8. **`contentEncoding` (mislabeled charset parser) fails on quoted `charset="utf-8"` and reordered parameters.**
   - Stage: Spec-Structured Parsing Fidelity
   - `middleware/content_charset.go:29-34`.

---

## Gate Self-Check

| # | Check | Status |
|---|-------|--------|
| 1 | EXPLORATION.md ≥ 120 lines | PASS — file is well over 120 lines. |
| 2 | `## Open Exploration Findings` present | PASS |
| 3 | `## Quality Risks` present | PASS |
| 4 | `## Pattern Applicability Matrix` present | PASS |
| 5 | `## Pattern Deep Dive — <name>` present (≥3) | PASS — 3 sections (Spec-Structured Parsing, Composition/Mount-Context, Enumeration/Representation). |
| 6 | `## Candidate Bugs for Phase 2` present | PASS |
| 7 | `## Gate Self-Check` present | PASS (this section) |
| 8 | PROGRESS.md Phase 1 marked `[x]` | PASS — `quality/PROGRESS.md` line `- [x] Phase 1 - Explore`. |
| 9 | ≥8 numbered Open Exploration Findings, each with ≥1 file:line | PASS — 10 numbered findings, all cited. |
| 10 | ≥3 findings trace ≥2 distinct file:line locations | PASS — Findings 1,2,3,4,5,7,9,10 are multi-location. |
| 11 | Matrix has 3–4 `FULL` rows | PASS — Patterns 3,4,6,7 = 4 FULL. |
| 12 | ≥2 Pattern Deep Dives trace ≥2 distinct identifiers/locations | PASS — Spec-Parsing dive traces `selectEncoder`/`matchAcceptEncoding`/`WriteHeader`; Mount-Context dive traces `Match`/`RoutePath`/`r.URL.Path`; Enumeration dive traces `methodMap`/`reverseMethodMap`/`mALL`. |
| 13 | Candidate-bug source mix: ≥2 from exploration/risks AND ≥1 from a pattern deep dive | PASS — exploration/risks: #3 (open exploration), #4 (quality risks), #6 (open exploration + …), #7 (quality risks); pattern deep dive: #1, #2, #5, #8. |

---

## Derived Requirements

> Cartesian UC rule applied below; see "Cartesian UC rule confirmation". Each REQ names specific files and functions: REQ-001 (`SupressNotFound`/`PageRoute`/`PathRewrite` reading `r.URL.Path`), REQ-002 (`matchAcceptEncoding`/`contentEncoding`/`realIP`), REQ-003 (`methodMap`/`reverseMethodMap`/`mALL`/`RegisterMethod`), REQ-004 (`Mux.Find` vs the mount closure), REQ-005 (`replaceWildcards`/`RoutePattern`).

### REQ-001: Path-manipulation middleware must operate on chi's canonical mounted path (`rctx.RoutePath`), not raw `r.URL.Path`, so behavior is correct under `Mount()`.
- References: middleware/supress_notfound.go, middleware/page_route.go, middleware/path_rewrite.go
- Pattern: parity
- (Asymmetry-promotion: the prose asymmetry "canonical-aware cohort reads `rctx.RoutePath`; raw cohort relies entirely on `r.URL.Path`" — Finding 7 — is promoted here to a multi-site parity REQ.)

### REQ-002: RFC-defined request-header parsing must follow the grammar (tokenize, honor `q=0`, trim whitespace, parse parameters), not substring/`Cut` shortcuts.
- References: middleware/compress.go, middleware/content_charset.go, middleware/realip.go
- Pattern: parity

### REQ-003: The HTTP-method closed set must stay consistent across all three structures and every consumer.
- References: tree.go, mux.go
- Pattern: whitelist

### REQ-004: `Mux.Find`/`Mux.Match` must mirror live routing's observable context effects (including the mount wildcard-URLParam reset) when traversing mounted routes.
- References: mux.go (mux.go:383-390 vs mux.go:309-322)
- Pattern: parity

### REQ-005: `RoutePattern()` reconstruction must not corrupt patterns that contain a literal interior wildcard segment.
- References: context.go, tree.go
- Pattern: parity

## Cartesian UC rule confirmation

1. **Gate 1 (path-suffix / function-role match) run for every REQ with ≥2 References.**
   - REQ-001 (3 refs): each middleware file defines a single decorating handler function reading/writing the request path — shared role "path-manipulation handler". **Gate 1 matches.**
   - REQ-002 (3 refs): `compress.go`/`content_charset.go`/`realip.go` each parse a distinct header with a distinct function (`matchAcceptEncoding`, `contentEncoding`, `realIP`) — same *kind* of operation (header parse) but no shared function-name suffix. **Gate 1 = heterogeneous match (same role, different names).**
   - REQ-003 (2 refs `tree.go`/`mux.go`): different files, no shared `_function` suffix; the method-map is defined in `tree.go` and consumed in `mux.go`. **Gate 1 does NOT match** (definition vs consumption, not parallel implementations).
   - REQ-004 (single file, two ranges in `mux.go`): the two ranges are the live mount closure vs `Find`; parallel implementations of the same shift. **Gate 1 matches (intra-file).**
   - REQ-005 (2 refs): `replaceWildcards` (`context.go`) and the inline collapse (`tree.go:862`) — same textual-collapse operation in two sites. **Gate 1 matches.**
2. **Gate 2 (function-level similarity) run where Gate 1 passed.**
   - REQ-001: each handler body is a small (~10-15 line) function of similar size, each inside a function body → **Gate 2 passes** → emit per-site UCs.
   - REQ-004: both ranges are inside function bodies of comparable size → **Gate 2 passes** → per-site UCs.
   - REQ-005: both sites are short same-shape collapses inside function bodies → **Gate 2 passes** → per-site UCs.
3. **Per-site UCs emitted where both gates passed:** REQ-001 → UC-1.a/.b/.c; REQ-004 → UC-4.a/.b; REQ-005 → UC-5.a/.b (below).
4. **Gate-1-only (heterogeneous) marked:** REQ-002 carries `<!-- cluster: heterogeneous -->` on its umbrella UC.
5. **Neither-gate-pass kept as single umbrella, no marking:** REQ-003 (definition-vs-consumption) → single umbrella UC-3, no per-site split.
6. **`Pattern:` tag added** to every REQ with a Gate-1 role match (REQ-001 parity, REQ-002 parity, REQ-003 whitelist, REQ-004 parity, REQ-005 parity).
7. **Every prose asymmetry promoted:** the only architectural asymmetry noted (canonical-aware vs raw-`URL.Path` cohort, Finding 7 / Quality Risks) is promoted to REQ-001 with three implementation sites — no asymmetry demoted to prose.

## Derived Use Cases (UC-NN)

### UC-1.a: `SupressNotFound` under a mounted sub-router
- Actors: chi `Mux`, an operator mounting a sub-router, an HTTP client
- Preconditions: `root.Mount("/api", child)`; `child` uses `SupressNotFound`
- Flow: request `/api/ping`; middleware must `Match` against the canonical `rctx.RoutePath` (`/ping`), not `r.URL.Path` (`/api/ping`), using a throwaway context
- Postconditions: a defined `/ping` route is found; no spurious 404; live `rctx` unmutated

### UC-1.b: `PageRoute` under a mounted sub-router
- Actors: chi `Mux`, operator, client
- Preconditions: `root.Mount("/admin", child)`; `child` uses `PageRoute("/status", h)`
- Flow: request `/admin/status`; the match must compare against `rctx.RoutePath` (`/status`)
- Postconditions: `PageRoute` fires for the mounted path

### UC-1.c: `PathRewrite` under a mounted sub-router
- Actors: chi `Mux`, operator, client
- Preconditions: `root.Mount("/svc", child)`; `child` uses `PathRewrite(old,new)`
- Flow: rewrite must update the canonical routing path so chi's subsequent walk (which reads `rctx.RoutePath`) observes the rewrite
- Postconditions: chi routes the rewritten path, not the original

### UC-2: RFC-correct request-header parsing (umbrella) <!-- cluster: heterogeneous -->
- Actors: compression/content-negotiation/real-IP middleware, HTTP client behind a proxy
- Preconditions: client sends `Accept-Encoding: gzip;q=0` / `Content-Type: text/plain; charset="utf-8"` / padded or ported `X-Forwarded-For`
- Flow: each parser tokenizes per its RFC (q-value honored, quoted params handled, whitespace trimmed) before deciding
- Postconditions: `q=0` suppresses compression; quoted charset matched; valid XFF entries accepted

### UC-3: HTTP-method closed-set consistency (umbrella)
- Actors: chi `Mux`, application calling `RegisterMethod`
- Preconditions: a custom method is registered, or a request uses an unsupported method
- Flow: `methodMap`, `reverseMethodMap`, and `mALL` are updated together; `routeHTTP` and the 405 `Allow` builder read a consistent set
- Postconditions: `Allow` header lists exactly the registered methods; wildcard registration covers the new method

### UC-4.a: `Find` mirrors live routing on a top-level route
- Actors: code calling `Mux.Find`
- Preconditions: a registered non-mounted route
- Flow: `Find` returns the pattern with the same context effects as a live walk
- Postconditions: pattern returned; context state consistent

### UC-4.b: `Find` mirrors live routing on a mounted route
- Actors: code calling `Mux.Find` against a mounted sub-router
- Preconditions: `root.Mount("/api", child)`
- Flow: `Find` shifts `RoutePath` AND performs the wildcard-URLParam reset the live closure does
- Postconditions: returned pattern and resulting context match the live path exactly

### UC-5.a: `RoutePattern()` for a route with a trailing wildcard
- Actors: instrumentation middleware reading `RoutePattern()`
- Preconditions: route `/files/*`
- Flow: `replaceWildcards` collapses only synthesized mount wildcards
- Postconditions: reported pattern preserves a legitimate trailing `*`

### UC-5.b: `walk()` full-route reconstruction with an interior literal `*`
- Actors: `Walk` consumers (docgen, route listing)
- Preconditions: a route whose pattern legitimately contains an interior `*` segment
- Flow: the `/*/`→`/` collapse must not erase a literal interior segment
- Postconditions: the walked full route is faithful to the registered pattern
