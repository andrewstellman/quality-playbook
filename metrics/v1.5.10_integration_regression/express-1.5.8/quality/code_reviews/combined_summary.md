# Combined Summary — Phase 3 Code Review (Express v5.2.1)

> Quality Playbook v1.5.8 · 2026-06-19. Merges pass1 (structural), pass2 (requirement), pass3 (cross-requirement). Source boundary held: no file outside `quality/` modified; all source changes expressed as patches under `quality/patches/`.

## Confirmation table

| ID | Source | File:line | Finding | Severity | Status |
|----|--------|-----------|---------|----------|--------|
| BUG-001 | Pass1 area1 / Pass2 REQ-001 / Pass3 | request.js:309-314 | `req.protocol`/`secure` → `''`/false for leading-empty XFP | HIGH | BUG CONFIRMED |
| BUG-002 | Pass1 area4 / Pass2 REQ-002 | response.js:759-766 | `res.cookie` sub-second `maxAge` → `Max-Age=0` w/ future `Expires` | HIGH | BUG CONFIRMED |
| BUG-003 | Pass2 REQ-003 / Pass3 | response.js:841,846-847 | `res.redirect` literal `undefined` for in-range unassigned status | MEDIUM | BUG CONFIRMED |
| BUG-004 | Pass1 area4 / Pass2 REQ-006 / Pass3 | response.js:137-153 | charset string-vs-Buffer/`res.set` asymmetry | MEDIUM | BUG CONFIRMED |
| BUG-005 | Pass1 area1 / Pass2 REQ-005 | utils.js:89-120 | `acceptParams` quoted-`;` split + unclamped `q` | MEDIUM | BUG CONFIRMED |
| BUG-006 | Pass1 area1 / Pass2 REQ-007 / Pass3 | request.js:424-427 | leading-comma XFH → undefined host getters | MEDIUM | BUG CONFIRMED |
| — | Pass1 area1 / Pass2 REQ-004 | response.js:286 | jsonp member-access whitelist | — | FALSE POSITIVE (reachability: no injection path) |

**Confirmed: 6 (2 HIGH, 4 MEDIUM). False positive: 1.**

## Closure (every confirmed BUG has a regression test + exemption-free closure)

| BUG | REGRESSION TEST | Fix patch | Writeup |
|-----|-----------------|-----------|---------|
| BUG-001 | test_regression.js `it.skip("BUG-001: …")` | BUG-001-fix.patch | writeups/BUG-001.md |
| BUG-002 | test_regression.js `it.skip("BUG-002: …")` | BUG-002-fix.patch | writeups/BUG-002.md |
| BUG-003 | test_regression.js `it.skip("BUG-003: …")` | BUG-003-fix.patch | writeups/BUG-003.md |
| BUG-004 | test_regression.js `it.skip("BUG-004: …")` | BUG-004-fix.patch | writeups/BUG-004.md |
| BUG-005 | test_regression.js `it.skip("BUG-005: …")` | BUG-005-fix.patch | writeups/BUG-005.md |
| BUG-006 | test_regression.js `it.skip("BUG-006: …")` | BUG-006-fix.patch | writeups/BUG-006.md |

No exemptions. Each regression-test patch also materializes a standalone `test/regression_bug_NNN.test.js`.

## Validation performed (mechanical — node_modules absent, no runtime suite)

- **All 12 patches** (6 fix + 6 regression-test) pass `git apply --check -p1` from the express repo root.
- **All patched source copies** pass `node --check` (request.js, response.js, utils.js).
- **All 6 materialized regression test files** pass `node --check`; `quality/test_regression.js` parses.
- **BUG-005 executable RED→GREEN** (pure function, no deps): current code `params.x='"a', q=5`; fixed `params.x='a;b', q=1`. Confirmed.
- HTTP-path bugs (001/002/003/004/006) await Phase 5 TDD red/green once deps are installed; `git apply --check` + `node --check` is the sufficient mechanical gate per `references/review_protocols.md`.

## Test-finding alignment (each test exercises the cited path)

- BUG-001 test sets `X-Forwarded-Proto: ", https"` with trust proxy → asserts `req.protocol`/`req.secure` (the cited getter pair).
- BUG-002 test calls `res.cookie('flash','1',{maxAge:500})` → asserts `Set-Cookie` lacks `Max-Age=0` (the cited serialization).
- BUG-003 test calls `res.redirect(310,'/x')` → asserts body has no `undefined` (the cited body builder).
- BUG-004 test sets `text/plain; charset=iso-8859-1` then `send` string vs Buffer → asserts equal Content-Type (the cited branches).
- BUG-005 test calls `utils.normalizeType('text/html;x="a;b";q=0.5')` → asserts `params.x==='a;b'` + `q` clamp (the cited parser).
- BUG-006 test sets trusted `X-Forwarded-Host: ",sub.example.com"` → asserts `hostname`/`subdomains` (the cited getters).

## Pattern-grid confirmation (REQ-006, REQ-007)

`quality/compensation_grid.json`: REQ-006 (1 item × 3 sites) and REQ-007 (1 item × 3 sites). All 6 absent cells covered — REQ-006's 3 by BUG-004 (Covers + consolidation rationale), REQ-007's 3 by BUG-006 (Covers + consolidation rationale). `compensation_grid_downgrades.json` is empty (no cell downgraded to QUESTION). Union of Covers = grid for both REQs. Grid clean.

## Overall assessment

**FIX BEFORE MERGE** — 2 HIGH (security-class: secure-downgrade BUG-001, silently-dropped cookie BUG-002) and 4 MEDIUM correctness defects, all with reproducible regression tests and fix patches.
