# Confirmed Bugs — Express v5.2.1

> Quality Playbook v1.5.8 · 2026-06-19 · Phase 3 (Code Review). Source boundary: `lib/` only; all fixes expressed as patches under `quality/patches/`. Tier 3 (code-is-the-spec); `History.md` cited where it establishes v5 intent.

6 bugs confirmed from the 3-pass code review. Candidate #5 (jsonp member-access) was demoted to a FALSE POSITIVE (see code_reviews/pass1_structural.md area 1) — the callback filter strips every statement-breaking character, so no injection path is reachable.

---

### BUG-001: `req.protocol` returns `''` (and `req.secure` false) for a trusted `X-Forwarded-Proto` with an empty leading element
- Primary requirement: REQ-001
- File:line: `lib/request.js:309-314`, `lib/request.js:326-328`
- severity: HIGH
- divergence_type: code-spec
- Expected: `req.protocol` is the first **non-empty** trimmed comma-separated element of a trusted `X-Forwarded-Proto`, falling back to the socket scheme; always ∈ {http, https}.
- Actual: for `", https"` / `","`, `header.substring(0, header.indexOf(',')).trim()` is `''`; `req.secure` then reads false for a genuinely-secure request.
- reachability_analysis: no guard; the `index !== -1` branch (`request.js:312-313`) is reached unconditionally once trust passes and the header contains a comma — there is no non-empty-token check, retry, or fallback-to-`proto` when the first element is empty. `req.protocol` is a public getter read by `req.secure` and any HTTPS-gating middleware. Defect path reached unconditionally for any trusted comma-led XFP value.
- Spec basis: code inconsistency vs the getter's own documented intent ("first value … to be safe", `request.js:307-308`); no History.md line governs the empty-element case.
- Regression test: `it.skip("BUG-001: ...")` in `quality/test_regression.js`
- Patches: `quality/patches/BUG-001-regression-test.patch`, `quality/patches/BUG-001-fix.patch`

### BUG-002: `res.cookie` with sub-second `maxAge` emits `Max-Age=0` alongside a future `Expires`
- Primary requirement: REQ-002
- File:line: `lib/response.js:759-766`
- severity: HIGH
- divergence_type: code-spec
- Expected: `Expires` and `Max-Age` describe the same lifetime; an immediate-expiry cookie is produced only by `res.clearCookie`.
- Actual: `opts.maxAge = Math.floor(maxAge / 1000)` floors any `maxAge` in (0,1000) to `0` while `opts.expires` is in the future; UAs that prefer `Max-Age` delete the cookie immediately.
- reachability_analysis: no guard; the `Math.floor(maxAge/1000)` assignment (`response.js:764`) is reached unconditionally inside `if (!isNaN(maxAge))` for any numeric `maxAge`. There is no minimum, round-up, or `Max-Age`/`Expires` reconciliation. Any caller passing `0 < maxAge < 1000` (e.g. a 500ms flash/CSRF cookie) hits it.
- Spec basis: code inconsistency with C-3 contract; no History.md line.
- Regression test: `it.skip("BUG-002: ...")` in `quality/test_regression.js`
- Patches: `quality/patches/BUG-002-regression-test.patch`, `quality/patches/BUG-002-fix.patch`

### BUG-003: `res.redirect` emits literal `undefined` in body/title for an in-range status absent from `statuses.message`
- Primary requirement: REQ-003
- File:line: `lib/response.js:841`, `lib/response.js:846-847`
- severity: MEDIUM
- divergence_type: cross-source
- Expected: the redirect body and HTML `<title>` are human-readable for every accepted status.
- Actual: `statuses.message[status]` is `undefined` for an in-range unassigned 3xx (e.g. 310); string concat yields `"undefined. Redirecting to …"` and `<title>undefined</title>`.
- reachability_analysis: no guard; `res.status` (`response.js:70`) admits any integer 100–999, a strictly larger set than `statuses.message` covers, and the redirect body builder (`:841`, `:846-847`) reads `statuses.message[status]` with no fallback. Defect path reached for any in-range code the message map omits (e.g. 218, 310, 419). Cross-source: the range guard and the message map are two independent sources whose domains disagree.
- Spec basis: cross-implementation inconsistency between `res.status` range guard (`History.md`: "status code … greater than 99 and less than 1000") and the `statuses.message` lookup.
- Regression test: `it.skip("BUG-003: ...")` in `quality/test_regression.js`
- Patches: `quality/patches/BUG-003-regression-test.patch`, `quality/patches/BUG-003-fix.patch`

### BUG-004: Charset asymmetry — `res.send` forces `charset=utf-8` for string bodies but preserves the caller's charset for Buffer bodies and via `res.set`
- Primary requirement: REQ-006
- Covers: [REQ-006/cell-CHARSET_INJECTION-STRING_SEND, REQ-006/cell-CHARSET_INJECTION-BUFFER_SEND, REQ-006/cell-CHARSET_INJECTION-RES_SET]
- Consolidation rationale: all three cells trace to one divergence — the string-`send` path overwrites the charset to utf-8 (`setCharset`) while the Buffer-`send` and `res.set` paths only add a charset when absent (`mime.contentType`) and never overwrite. A single fix that makes the charset rule uniform across the three surfaces closes all three cells through the shared content-type normalization seam.
- File:line: `lib/response.js:137-143`, `lib/response.js:150-153`, `lib/response.js:664-686`, `lib/utils.js:225-238`
- severity: MEDIUM
- divergence_type: internal-prose
- Expected: the charset advertised in the final Content-Type is a function of app intent, consistent across body type and across the `setCharset`-vs-`mime.contentType` paths (or the divergence is explicitly documented).
- Actual: `text/plain; charset=iso-8859-1` → string `send` advertises `charset=utf-8`; Buffer `send` / `res.set` advertise `charset=iso-8859-1`. Identical handler, different wire charset by body type.
- reachability_analysis: no guard; the string branch (`response.js:140`) and the Buffer branch (`:150-153`) are mutually exclusive arms of the same `switch (typeof chunk)` and each is reached unconditionally for its body type whenever a Content-Type with a charset is pre-set. No reconciliation step normalizes the two before headers flush.
- Spec basis: `History.md:15` documents the v5 perf change that introduced the string-only `setCharset` rewrite ("Avoid duplicate Content-Type header processing in res.send()") with no statement that the Buffer path should diverge — internal-prose gap.
- Regression test: `it.skip("BUG-004: ...")` in `quality/test_regression.js`
- Patches: `quality/patches/BUG-004-regression-test.patch`, `quality/patches/BUG-004-fix.patch`

### BUG-005: `acceptParams` splits quoted parameter values on an inner `;` and does not clamp `q` to `[0,1]`
- Primary requirement: REQ-005
- File:line: `lib/utils.js:89-120` (specifically `:99-108`, `:110-111`)
- severity: MEDIUM
- divergence_type: code-spec
- Expected (RFC 7231 §3.1.1.1): a quoted parameter value containing `;` is not split mid-value; `q` is parsed and clamped to `[0,1]`.
- Actual: `text/html;x="a;b";q=0.5` → `endIndex` lands on the `;` inside the quotes, so `value` is truncated to `"a` and the scan desyncs; `q=5` flows through `parseFloat` (`:111`) unclamped as `quality: 5`.
- reachability_analysis: no guard; the boundary scan (`utils.js:96-108`) uses `str.indexOf('=' / ';')` with zero quoted-string awareness, and `:111` assigns `parseFloat(value)` with no clamp. Reached unconditionally via `normalizeType` (`utils.js:61-64`) for any `Accept`/`res.format`/`res.type` media-type string containing a quoted `;` or an out-of-range `q`.
- Spec basis: RFC 7231 §3.1.1.1 (media-type parameter grammar with quoted-string values); `q` range is RFC 7231 §5.3.1.
- Regression test: `it.skip("BUG-005: ...")` in `quality/test_regression.js`
- Patches: `quality/patches/BUG-005-regression-test.patch`, `quality/patches/BUG-005-fix.patch`

### BUG-006: `req.host`/`req.hostname`/`req.subdomains` resolve to `undefined`/`[]` for a trusted `X-Forwarded-Host` with a leading comma
- Primary requirement: REQ-007
- Covers: [REQ-007/cell-LEADING_COMMA_AUTHORITY-HOST, REQ-007/cell-LEADING_COMMA_AUTHORITY-HOSTNAME, REQ-007/cell-LEADING_COMMA_AUTHORITY-SUBDOMAINS]
- Consolidation rationale: all three cells trace to one root defect at `host` — `substring(0, indexOf(','))` selects the empty leading element. `hostname` (`if (!host) return;`) and `subdomains` (`if (!hostname) return [];`) are strict downstream consumers, so a single fix at the `host` getter (select the first **present** authority) closes all three cells.
- File:line: `lib/request.js:424-427` (`host`), `lib/request.js:444-458` (`hostname`), `lib/request.js:383-394` (`subdomains`)
- severity: MEDIUM
- divergence_type: code-spec
- Expected: for a trusted XFH with a syntactically-present authority, `host` is that authority and `hostname`/`subdomains` resolve from it; never `undefined`/`[]` for a present host.
- Actual: trusted `",a.com"` → `host` `undefined` → `hostname` `undefined` → `subdomains` `[]`.
- reachability_analysis: no guard; the trusted-branch split (`request.js:424-427`) is reached unconditionally when trust passes and XFH contains a comma, and it always takes `substring(0, firstComma)` — `''` when the first comma is at index 0. There is no non-empty-authority selection. Defect path reached for any trusted comma-led XFH value.
- Spec basis: code inconsistency vs the getter's own "to be safe" intent (`request.js:425-426`) and the cross-getter parity with `req.protocol` (Pass 3); no History.md line.
- Regression test: `it.skip("BUG-006: ...")` in `quality/test_regression.js`
- Patches: `quality/patches/BUG-006-regression-test.patch`, `quality/patches/BUG-006-fix.patch`

---

## Grid self-check (Phase 3 advisory)

- **REQ-006** (3 cells): all 3 absent cells covered by BUG-004's `Covers` list; 0 downgrades. Union = grid. Clean.
- **REQ-007** (3 cells): all 3 absent cells covered by BUG-006's `Covers` list; 0 downgrades. Union = grid. Clean.

## Demoted (not confirmed)

- **Candidate #5 — jsonp member-access whitelist** (`response.js:286`): FALSE POSITIVE. reachability_analysis found a compensating mechanism — the `/[^\[\]\w$.]/g` filter strips every statement-breaking character (`( ) ' ; space /`), confining the survivor to the fixed `/**/ typeof CB === 'function' && CB(BODY);` template; `nosniff` + the `typeof` guard close the residual surface. No injection path reachable. Recorded as a QUESTION in pass1, excluded from the bug count.
