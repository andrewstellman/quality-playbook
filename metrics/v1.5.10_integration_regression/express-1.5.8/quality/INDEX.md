# Quality Artifact Index — Express v5.2.1

> Quality Playbook v1.5.8 · last updated 2026-06-19 (Phase 3 complete)

## Phase status
- [x] Phase 1 — Explore · [x] Phase 2 — Generate · [x] Phase 3 — Code Review · [ ] Phase 4 — Spec Audit · [ ] Phase 5 — Reconciliation · [ ] Phase 6 — Verify

## Phase 3 result (Code Review + Regression Tests)
6 bugs confirmed (2 HIGH, 4 MEDIUM); 1 candidate demoted (jsonp whitelist — false positive).

| Artifact | Path |
|----------|------|
| Confirmed bugs | `quality/BUGS.md`, `quality/bugs_manifest.json` |
| Pass 1 (structural) | `quality/code_reviews/pass1_structural.md` |
| Pass 2 (requirements) | `quality/code_reviews/pass2_requirements.md` |
| Pass 3 (cross-requirement) | `quality/code_reviews/pass3_cross_requirement.md` |
| Combined summary | `quality/code_reviews/combined_summary.md` |
| Regression tests | `quality/test_regression.js` (6 `it.skip` guards) |
| Fix + regression-test patches | `quality/patches/BUG-00{1..6}-{fix,regression-test}.patch` (12 files) |
| Per-bug writeups | `quality/writeups/BUG-00{1..6}.md` |
| Compensation grids | `quality/compensation_grid.json`, `quality/compensation_grid_downgrades.json` |

## Bug summary
| ID | Sev | Site | One-liner |
|----|-----|------|-----------|
| BUG-001 | HIGH | request.js:309-314 | `req.protocol`/`secure` collapse for leading-empty `X-Forwarded-Proto` |
| BUG-002 | HIGH | response.js:759-766 | `res.cookie` sub-second `maxAge` → `Max-Age=0` vs future `Expires` |
| BUG-003 | MEDIUM | response.js:841,846-847 | `res.redirect` literal `undefined` for in-range unassigned status |
| BUG-004 | MEDIUM | response.js:137-153 | charset asymmetry string vs Buffer `send`/`res.set` |
| BUG-005 | MEDIUM | utils.js:89-120 | `acceptParams` quoted-`;` split + unclamped `q` |
| BUG-006 | MEDIUM | request.js:424-427 | leading-comma `X-Forwarded-Host` → undefined host getters |

Next phase: Phase 4 (Spec Audit — Council of Three), fresh context window.
