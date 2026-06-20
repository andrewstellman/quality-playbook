# Panel B — regression safety — VERDICT: SHIP

Independent adversarial review (built temp trees + called `detect_project_language`/`count_source_files`).

- **OK no detection FLIP** for existing single-language repos: Go/Rust/C/JS/TS/Java all still detect correctly under dominant-count; empty repo → `""`. Depth boundary: source at depth 5 detected, depth 6 missed (consistent with `depth < 5`). Tiebreak deterministic (go=2/py=2 → go, earliest).
- **OK build-output exclusion sound.** TS project with `dist/` of 4 `.js` (vs 2 `.ts`) → `ts`; same for `build`/`out`/`target`. Adversarial `target/`: a Rust repo with `src/*.rs` + `target/**` artifacts still → `rs` (real source under `src/` counted, build dir skipped) — excluding `target/` only removes generated artifacts, never primary source.
- **OK install-marker + bundled-bin exclusion preserved (2026-05-16 gson fix).** `_INSTALL_MARKER_DIRS` (incl. `bin` + 8 markers) still unioned into `excluded`. A Java repo with 6 bundled `bin/*.py` (outnumbering 2 `.java`) still → `java`; `count_source_files` returns 2 (real source only). gson regression stays fixed under dominant-count.
- **OK defensive sweep.** `lang_to_valid` (dict-keyed, clj added) and `lang_map` (dict-keyed, clj added) are NOT ordered first-match — no analogous bug. `count_source_files` ext set extended with all three clj exts.
- **OK accepted-tradeoff honesty.** Verified the tradeoff bites as documented (clj-1 vs py-3 tooling → `py`); the docstring states this explicitly and faithfully.
- **OK pin validity (independent mutation).** Re-implemented pre-056 ordered first-match (no clj) and ran the Clojure + Java targets → both `py`, confirming the shipped pins genuinely bite (not vacuous). Shipped test file 9/9.
- **NIT (known follow-up, OUT OF SCOPE per instruction):** `bin/classify_project.py:198 EXTENSION_LANGUAGE` is dict-lookup (no first-match bug) but Clojure-blind (no `.clj/.cljc/.cljs`; also no `.agc`). It drives Code/Skill/Hybrid classification, not gate language detection, so it cannot reproduce the adopter mis-detection. Flag for the documented follow-up; not fixed here.
- Minor (pre-existing, not a 056 regression): `.tsx`/`.jsx` and header-only `.h` dirs not in `language_order` (same set as before).

VERDICT: SHIP
