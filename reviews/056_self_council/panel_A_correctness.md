# Panel A — correctness — VERDICT: SHIP

Independent adversarial review of the Clojure dominant-by-count gate fix (instruction 056), canonical source `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py`.

- **OK dominant-by-count, known-exts only.** `detect_project_language` builds `ext_to_lang`/`order_index` from `language_order` and counts only files whose extension is in `known_exts` — `.md`/`.sh`/`.edn`/`.txt` are not counted (empirically `''` for a no-source tree).
- **OK tiebreak.** `max(counts, key=lambda lang: (counts[lang], -order_index[lang]))` — most files wins; on equal counts the smaller index (earliest in `language_order`) wins. Traced 5 pairs (go-vs-py→go, ts-vs-js→ts, c-vs-clj→c, py-vs-clj→py, scala-vs-c→scala) — all correct. Returns `""` when empty.
- **OK depth 5 reaches deep source.** `if depth < 5` pushes subdirs; a dir popped at depth 5 still has its files scanned. Instrumented trace: canonical `src/main/clojure/<ns>/<ns>.clj` lands at depth 5 and is counted. vaelii-shape (128 deep `.clj` vs 3 shallow `.py`) → `clj`. `.clj`/`.cljc`/`.cljs` all map to `clj` and sum.
- **OK tables wired.** `clj` in `language_order`; `lang_to_valid["clj"]="clj cljc cljs"`; `count_source_files` exts include all three clj exts.
- **OK lang_map reachability (no dead code).** `lang_map={"go","py","clj"}`; dispatch → `_clojure_test_function_bodies`; `_body_has_real_assertion` live `clj` branch using `_CLOJURE_ASSERTION_PATTERNS` (`(is`/`(are`). End-to-end drive: hollow `(deftest …)`→fail, `(is …)`/`(are …)`→pass. Per-deftest balanced-paren extraction: a top-level `(is)` does not rescue a hollow deftest; `\(is\b` rejects `(island`; unbalanced parens → no crash.
- Note (not a defect): a 1-deep-clj vs 1-shallow-py tree is a genuine tie → `py` by tiebreak; decisiveness comes from margin (the suite fixture uses a realistic >1 margin).

Suite: `test_quality_gate_language_detection` 9/9 pass.

VERDICT: SHIP
