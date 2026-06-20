# Panel C — test sufficiency — VERDICT: SHIP

Independent adversarial review of `bin/tests/test_quality_gate_language_detection.py` additions.

- **OK realistic-margin Clojure fixture at depth.** `_clojure_deep_target`: 3 `.clj` + 1 `.cljc` under `src/main/clojure/acme/` + 2 shallow `scripts/*.py`. Traced depth against the real walker: root=1, src=2, main=3, clojure=4, acme=5 — the `.clj` are scanned AT depth 5 (4 vs 2 margin, not lopsided). Docstring justifies counts + depth (why ≤3 mis-detects, why depth-5 fixes). Asserts `clj`.
- **OK Java pin BITES on first-match revert.** `_java_dominant_stray_py_target` puts `gen.py` in `scripts/` (NOT excluded), 3 `.java` vs 1 `.py` — genuinely distinct from the pre-existing `_flat_root_bin_target` (whose `.py` is in `bin/`, excluded both ways → does NOT bite a first-match revert). Both required by the instruction; both present.
- **OK existing-language regression pins** (Go/Rust/C/JS/TS via subTests) + TS-with-`dist` build-output fixture (2 `.ts` vs 3 `.js` in `dist/` → `ts`, proves the exclusion).
- **OK hollow-vs-real Clojure** (`test_clj_lang_map_reachable_hollow_fails_real_passes`): hollow `(deftest t-hollow)` → FAIL==1; `(is …)`-bearing → FAIL==0; confirms `lang_map["clj"]` reachable.
- **OK mutation evidence CREDIBLE — independently reproduced.** Rebuilt the pre-056 first-match (depth-3, no clj, from HEAD) in /tmp WITHOUT touching the real file: Clojure fixture → `py` (bite), Java fixture → `py` (bite), TS fixture → `ts` (correctly no bite), new module → clj/java/ts (correct). `bin` confirmed in `_INSTALL_MARKER_DIRS` so the reproduction matched real exclusion behavior.
- **NIT:** full `bin/tests/` is NOT fully green — 5 pre-existing failures (`test_readme_*`, `test_doc_drift`, `test_doc_gathering_skill_integration_132`, `test_mode_a_self_execution_contract`). Stash-tested with the entire 056 diff removed: the SAME 5 appear byte-identical → pre-existing v1.5.10 docs-workstream drift, NOT 056 regressions (Python 3.14.5). The worker output should note this so a reviewer isn't surprised.

VERDICT: SHIP
