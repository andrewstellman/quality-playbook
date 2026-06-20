# 056 self-Council — SYNTHESIS — unanimous SHIP (round 1)

Mandatory 3-panel adversarial self-Council on the Clojure-blind quality-gate fix (instruction 056), branch `1.5.10`.

| Panel | Charter | Verdict |
|-------|---------|---------|
| A | correctness (dominant-by-count + depth≥5 + scoped-to-known-exts + lang_map reachability) | **SHIP** |
| B | regression safety (no flip Go/Rust/C/JS/TS/Java; build-output + install-marker exclusions; defensive sweep) | **SHIP** (1 out-of-scope NIT) |
| C | test sufficiency (realistic Clojure fixture; Java pin bites; mutation-verified) | **SHIP** (1 NIT) |

**Unanimous SHIP, round 1** — no FIX-REQUIRED.

## Confirmed
- `detect_project_language` is dominant-language-by-count: counts only `language_order` extensions, walks depth 5 (reaches `src/main/clojure/<ns>/<ns>.clj`), most-files-wins with earliest-in-order tiebreak, `""` when none. Build-output dirs (`dist/build/out/target`) + `_INSTALL_MARKER_DIRS` (incl. `bin`) excluded.
- Clojure wired into `language_order`, `lang_to_valid`, `count_source_files` exts, and `lang_map` (+ `_CLOJURE_ASSERTION_PATTERNS` + `_clojure_test_function_bodies` + `_body_has_real_assertion` clj branch) — reachability proven (hollow deftest FAILs, `(is …)` PASSes).
- No detection flip for existing languages; gson 2026-05-16 Java fix preserved; TS build-output exclusion proven.
- Both detection pins (Clojure + Java) independently reproduced to BITE on revert to first-match (Panels B and C each rebuilt the pre-056 detector). Mutation-verify executed by the worker: PASS→FAIL×2→PASS, restored byte-identical.

## Carried-forward (non-blocking)
1. **[B, out-of-scope NIT]** `bin/classify_project.py:198 EXTENSION_LANGUAGE` is Clojure-blind (and `.agc`-blind) — dict-lookup (no first-match bug), drives Code/Skill/Hybrid classification not gate detection, so it can't reproduce the adopter bug. The instruction explicitly scopes it OUT; documented follow-up.
2. **[C, NIT]** Full `bin/tests/` carries 5 pre-existing failures (README/doc-drift from the unrelated v1.5.10 docs workstream) — proven NOT 056 regressions (same 5 with the 056 diff removed). Noted in the output.

VERDICT: SHIP
