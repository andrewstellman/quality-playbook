# Panel C — Test Sufficiency / Honesty Review (QPB 058, v1.5.10)

Role: independent adversarial reviewer (PANEL C). Charter: test sufficiency /
honesty. All claims grounded against the **git-tracked** source
`plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py`
(NOT the gitignored `.github` copy). Test file:
`bin/tests/test_language_disclosure_override_058.py`.

Baseline: full 058 suite green at start — `Ran 24 tests ... OK`.

---

## 1. PINS ACTUALLY BITE — VERIFIED (mutation-confirmed)

**Frozen oracle is real and independent.** `_old_detect_winner`
(test:67-114) is a fully self-contained re-implementation of the pre-058
algorithm: it hardcodes its own `language_order`, `install_markers`,
`excluded` set, depth-5 walk, and the `max(counts, key=(count,
-order_index))` tiebreak. It does NOT call any live `quality_gate` function,
so a winner shift in the live code cannot move the oracle in lockstep. The
pin (`_assert_winner_matches_oracle`, test:129-138) asserts the live
`detect_project_language` == oracle AND that the singular delegate ==
`detect_project_languages(...)[0][0]` — covering both the byte-identity and
the no-drift-by-construction claim (live source: singular delegates to plural
at quality_gate.py:2821-2822).

**vaelii present and MANDATORY pin lands.** `/Users/andrewstellman/git/vaelii-alpha`
exists; live detection returns `clj` (ranked `clj=128, py=3`). The
`test_vaelii_winner_byte_identical_MANDATORY` pin (test:140-147) does NOT
skip and carries the load-bearing `assertEqual(..., "clj")`. vaelii is the
only Clojure repo in the pin set (chi=go, virtio=c, express=js/ts,
secbench2=ts) — confirmed the 056 clj winner's protection rests here.

**Narrow-margin tiebreak fixture is a real tie.** `narrow_margin_tiebreak/`
has 6 `.rs` + 6 `.ts` files (rs=6==ts=6); live winner is `rs` (earlier in
`language_order`). vaelii's 128:3 margin is too wide to exercise tiebreak
drift, so this fixture is the genuine tiebreak guard.

**MUTATION TEST (mandated).** I flipped the live sort tiebreak at
quality_gate.py:2812 `order_index[kv[0]]` -> `-order_index[kv[0]]`, purged
`__pycache__`, and ran
`test_narrow_margin_tiebreak_winner_byte_identical`:

```
AssertionError: 'ts' != 'rs'
Ran 1 test in 0.001s
FAILED (failures=1)
```

The pin BIT — the live winner flipped rs->ts while the frozen oracle stayed
rs, exactly as the docstring predicts (test:124-127). I then reverted the
edit (restored `order_index[kv[0]]`), purged `__pycache__`, and re-ran: 058
suite `Ran 24 tests ... OK`. `git diff` confirms only `order_index[kv[0]]`
(no leading minus) at :2812 — my mutation is gone; the remaining diff is the
uncommitted 058 feature work, not my change.

Verdict on item 1: **PASS — the pin is real, independent, and bites.**

## 2. CLOJURE DEEP-CHECK VERIFIED, NOT REBUILT — VERIFIED

The 056 primitives are live and unchanged in the git-tracked source:
`_CLOJURE_ASSERTION_PATTERNS` (:4083), `_clojure_test_function_bodies`
(:4089), `_body_has_real_assertion(...,"clj")` (:4177), `check_functional_
test_has_assertions` with `lang_map` (:4213). The 058 test class
`CljDeepCheckVerifyTests` (test:435-456) only *exercises* these primitives
directly (light confirmation) — it does NOT re-declare patterns or
re-implement the detector. The substantive hollow-`.clj`-FAILs / real-passes
contract still lives in
`bin/tests/test_quality_gate_language_detection.py:305-338`
(`DominantLanguageDetectionTests.test_clj_lang_map_reachable_hollow_fails_
real_passes`) and runs green (verified: `Ran 1 test ... OK`; full sibling
file `Ran 9 tests ... OK`). No duplication, no rebuild.

Verdict on item 2: **PASS.**

## 3. DISCLOSURE VENUE HONESTY — VERIFIED

secbench2 exists at `repos/secbench2`. Live
`detect_project_languages` returns `ts=14060, py=7944, go=1384, ...`;
`languages_over_disclosure_threshold` returns `[('ts',14060),('py',7944)]`
(>=2) and `_disclosure_fires` is True. The implementer's claim that
secbench2 is a genuine qualifying real-repo disclosure venue (ts+py over
threshold) is TRUE. The `test_secbench2_real_repo_disclosure_venue` test
(test:359-370) asserts `len(over) >= 2` and skips honestly if the repo is
absent — it does NOT fabricate a real-repo *validation* that didn't happen;
it only confirms the venue *qualifies*. The hermetic unit venue is the
labeled fixture `multilang_disclosure/` (go=20 + py=8), and the disclosure
stdout-block test (test:334-350) drives that fixture, not the real repo. The
design doc's "either real-repo or honestly fixture-only" requirement is met
honestly — both a real qualifying repo AND a labeled fixture are committed.

Verdict on item 3: **PASS — claim is honest and corroborated.**

## 4. LINE REFS / CLAIMS vs git-tracked source — VERIFIED

All symbols the test imports/asserts exist in the git-tracked gate at the
expected places: `detect_project_languages` (:2715), `detect_project_language`
delegate (:2815-2822), `_LANG_TO_VALID` (:2831), `languages_over_disclosure_
threshold` (:2855), `_disclosure_fires` (:2873), `check_test_file_extension`
with `language=None` param (:3959), `check_v1_5_0_index_md` (:5398),
`check_repo(..., language=None)` (:6807), `main` `--language` parse/validate
(:6900/6911/6930) and threading `check_repo(..., language=...)` (:6978) ->
`check_test_file_extension(..., language=language)` (:6830). `bin/run_playbook`
has `archive_on_language_switch` (:3355), `_read/_write_run_language`
(:3310/:3340), `_clear_live_quality` (:2660). `from bin import archive_lib`
resolves via the `bin/__init__.py` `__path__` extension to the canonical
scripts dir (no stale-copy dependence). The override threads end-to-end
(main->check_repo->check_test_file_extension), satisfying the re-Council A
"edit the call chain, not the function alone" requirement.

Verdict on item 4: **PASS.**

## 5. COMPANION PINS / BOUNDARIES / ERROR-GATE — VERIFIED

- **No-flag-unchanged companion pin:** `test_without_override_detected_
  language_used` (test:396-412) confirms that without `--language`, a `.py`
  test in a go repo FAILs (detected path unchanged); paired with the
  override test (test:376-394) this is the no-flag==unchanged guard.
- **Threshold boundary >=-inclusive:** `test_exactly_at_threshold_fires_
  inclusive` (test:210-216) uses py=5 files at exactly 10% (5/50) and asserts
  it fires; `test_below_threshold_does_not_fire` covers <5 files and <10%.
  Live source uses `>=` for both ratio and file count (:2868-2869) — boundary
  is correctly inclusive.
- **Archive error-gate BOTH branches:** live source has both `except
  archive_lib.ArchiveError` (:3394) AND `except Exception` (:3404), each
  returning before `_clear_live_quality`. Tests cover both:
  `test_error_gate_archive_error_does_not_clear` (test:493-513, raises
  ArchiveError) and `test_error_gate_bare_exception_does_not_clear`
  (test:515-534, raises RuntimeError) — both assert BUGS.md survives. The
  re-Council B "replicate both branches" requirement is met and tested.
- **INDEX conditional check:** gated `if not is_legacy and _disclosure_
  fires(...)` (:5550), enforces both presence AND non-empty values
  (:5554-5565), NOT added to `_V150_REQUIRED_SUMMARY_KEYS` — so single-language
  and legacy-schema runs are unaffected. Tests cover all four cases:
  two-lang-missing FAILs, two-lang-with-disclosure passes, single-lang
  passes, legacy schema exempt (test:251-322).

Verdict on item 5: **PASS.**

---

## Summary

Every charter item passes. The byte-identical-winner pin is genuinely
independent of the live code (frozen inline oracle) and mutation-confirmed to
bite (tiebreak flip -> rs!=ts FAIL). vaelii is present, mandatory, and
detects clj. secbench2 genuinely qualifies as a real disclosure venue (ts+py
over threshold) and the test claims nothing it didn't verify. The 056 clj
deep-check is verified, not rebuilt, and the canonical hollow-clj test still
passes. Override threads end-to-end; both archive error-gate branches and the
threshold inclusivity boundary are tested. Line refs match the git-tracked
source. I left the tree restored (mutation reverted, 058 suite green,
`git diff` shows no residue of my edit).

VERDICT: SHIP
