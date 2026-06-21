# QPB v1.5.10 — Language Disclosure + Override (Clojure fix close-out)

> **STATUS: DESIGN — DRAFT FOR OPERATOR REVIEW. No source touched.** Re-scoped 2026-06-21 after an adversarial review: **language-only**. The skill-surface work (`--surface code|skill`, the Phase-0 Hybrid dominance default, the skill-vs-doc Markdown model) is **split out** to its own future design + its own Council — it is pipeline routing, not this hygiene close-out (see `QPB_v1.6.x_Skill_Surface_Routing_Proposal.md`). Cowork authors this in the `docs/design/` lane; the **Claude Code worker** executes source mutations against the **git-tracked source of record** `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py`.
>
> **Canonical-source note (load-bearing).** The git-tracked source is `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` (21 clj refs; edited by commit `518270c` = the 056 fix). The `.github/skills/quality-playbook/quality_gate.py` copy is **gitignored, pre-056 (0 clj refs)** install cruft — it is NOT the source. The 2026-06-21 adversarial review grounded against that stale copy, which is why its findings #2 (Go/Python-only detector) and #10 (wrong line numbers) are **retracted as stale-copy artifacts** (see below). All line refs here are against the git-tracked source; the worker re-confirms before editing.

## Problem (grounded)

QPB is **single-language-per-repo by design.** `detect_project_language()` returns one language — `max(counts, …)`, dominant-by-count with a deterministic tiebreak (`quality_gate.py:2712`, dominant-by-count since 056). The functional-test gate validates the one test file against that one language: `valid_ext = lang_to_valid.get(detected_lang)` (`check_test_file_extension`, `:3840`; `lang_to_valid` `:3859`); a non-matching extension FAILs. So on a polyglot repo, QPB silently picks the plurality language and tests only that — the operator is never told other substantial languages exist or went untested.

This is **not** the 056 bug (misdetection from stray files — fixed) and **not** the substance gap (see next section — also already fixed for clj). It is the **disclosure/redirect layer**: detection is correct, but the single choice is silent and unredirectable.

## Clojure is ALREADY validated deeply — verify, do not rebuild (056)

The adversarial review claimed the hollow-test/no-op assertion detector is "Go + Python only," so a hollow `.clj` test would pass. **That is false for the real source** — it described the stale `.github` copy. In the git-tracked source, 056 already extended the deep substance check to Clojure:

- `_CLOJURE_ASSERTION_PATTERNS = (r"\(is\b", r"\(are\b")` (`quality_gate.py:~3954`)
- `_clojure_test_function_bodies(source)` — balanced-paren extraction of every `(deftest …)` form (`:3966`)
- `_body_has_real_assertion(body, "clj")` — checks the clj assertion patterns, no tautology stripping, mirroring Go (`:4078-4084`)
- `check_functional_test_has_assertions` — `lang_map = {"go","py","clj"}` (`:4118`), routes `clj` to `_clojure_test_function_bodies` (`:4143-4144`); the pass-through message reads "Go + Python + Clojure" (`:4127`)
- Covered by `bin/tests/test_quality_gate_language_detection.py`

So a hollow `(deftest …)` with no `(is …)`/`(are …)` **is caught today.** "QPB supports Clojure" already means *detect clj* **and** *verify the clj test asserts something* — both landed in 056. **v1.5.10 work for this is verification only:** confirm the test suite has an explicit hollow-`.clj`-FAILs case (add one if absent), and run the real-repo check (below). Do not re-implement the detector.

## The fix (language-only)

Keep the single-language model, make it honest and steerable:
1. **Choose the dominant testable language** — unchanged (056).
2. **Disclose** in the final report: which testable languages were detected, which one was tested, which other testable ones were skipped. (Markdown and other non-code content are **non-testable context, never a target** — see D1.)
3. **`--language <lang>` override** at start — run a fresh pass targeting a different testable language.
4. **Tell the operator how**, in the report, with an explicit warning that a re-run **archives** the current `quality/`.
5. **Defer full multi-language** (parallel per-language runs) to the 1.7+ backlog.

## Why this is cheap (Council-verified)
Archive-and-switch keeps only one language's artifacts in `quality/` at a time, **sidestepping per-language artifact namespacing** (~120 path refs). The lifecycle machinery exists: `archive_lib.archive_run()` snapshots `quality/` (copies, leaving it in place); `_clear_live_quality()` (`run_playbook.py:2606`) clears live artifacts preserving `previous_runs/`. No `--language` flag exists yet (additive). `quality/INDEX.md` §11 `summary` (gate-validated, `:5268-5409`) carries the persisted disclosure.

---

# Design

### D1 — Expose detected testable languages (code only)
Add `detect_project_languages(repo_dir)` returning the ranked **testable code-language** counts (the same extension set `detect_project_language` already counts). **No `doc`/Markdown tag** — Markdown is not a testable code language and is not surfaced as a target; it is, at most, ignored. `detect_project_language` (the winner) is re-expressed as a thin **delegate** to the plural — `detect_project_language(...)` returns `detect_project_languages(...)[0]` — so the walk/exclude/tiebreak **cannot drift** between them by construction. Its result must be **byte-identical** to today (regression pin, below) — do not re-perturb the 056 detection. [re-Council A]

### D2 — Disclosure in the final report (reliable, not prompt-only)
Two layers:
- **Deterministic gate output.** When ≥2 testable languages clear the threshold (D5), the gate emits a fixed-format per-repo block (in `check_repo` per-repo output, appended after `RESULT:` per the sanctioned `_emit_operator_verdict`/`::QPB::` precedent — do not alter `RESULT:` strings):
  ```
  LANGUAGES DETECTED (testable): go=120, py=44
  TESTED: go
  TESTABLE LANGUAGES NOT TESTED: py
  To run QPB on py: <override instructions>  (this ARCHIVES the current quality/ folder)
  ```
- **Persisted, gate-enforced disclosure in `INDEX.md` §11 `summary`** (`languages_detected` + `ran_on` + `untested_testable_languages`). **[Council carry-over] Conditional check inside `check_v1_5_0_index_md` (`:5266-5409`), firing only when ≥2 testable languages clear the threshold, EXEMPTING legacy `schema_version` archives. Do NOT add the keys to `_V150_REQUIRED_SUMMARY_KEYS` (`:4641`, iterated unconditionally `:5403`) — that would FAIL every single-language and archived run.**

### D3 — `--language <lang>` override (start-time)
- **Gate:** additive flag in `main`'s arg loop (`def main` at `:6702`, the `for arg in argv` chain at `:6736`); when set, the override threads to `check_test_file_extension` (`:3840`) **so it validates against the override's `lang_to_valid` entry instead of calling `detect_project_language` at `:3853`.** **[re-Council A — REQUIRED] The worker MUST edit the call chain too — `main` → `check_repo` (`:6669`) → `check_test_file_extension` (`:3840`); editing the function body without threading the override through the call site leaves the gate validating the *detected* language while the agent tested the *override* (the exact mismatch this feature guards).** Unknown/non-testable value → usage error (exit 2). Records `ran_on: <override>`.
- **arunner-native threading (going-forward path):** pass the chosen language as an arunner `var` into the Phase-2 prompts (so generation scopes to it) and into the gate argv (so `validate_phase_artifacts`/`quality_gate` get `--language`).
- **`run_playbook.py` (cheap, deprecating):** a `--language` flag forwarding to the gate + phase prompts (legacy-path coherence; `run_playbook.py` is being retired).
- **Override-honoring — RESOLVED (was Open Decision 4).** The gate enforces (a) the test-file **extension** and (b) for go/py/**clj**, the **substance check** (the no-op/hollow detector runs). So `--language clj` gets enforcement of the test file's **extension AND substance** (a hollow clj test under the override FAILs) — though *not* a guarantee the agent **re-targeted generation** to that language; that part stays **prompt-level best-effort**, confirmed by the self-Council correctness panel. **No separate gate-guard-on-mismatch is added now**: for the deep-check languages (go/py/clj) the substance check *is* the enforcement; the residual best-effort gap exists only for languages without a deep check — which are the **backlog** item below, so the gate-guard rides with them, not here. This is documented as best-effort-with-real-enforcement-for-clj, not left open.

### D4 — Archive-on-switch
Record the run's language (the INDEX `ran_on` field, or a small `quality/.qpb_language` sentinel). On a new run whose requested language differs from the recorded one: `archive_run(...)` to snapshot `quality/` into `previous_runs/<ts>-<status>/`, **then** `_clear_live_quality(...)`. **[Council carry-over + re-Council B] If `archive_run` raises, do NOT clear** (a failed archive must not destroy live artifacts) — mirror the existing pattern at `run_playbook.py:3217-3243`, where **both** `ArchiveError` **and** a bare `Exception` `return` before `_clear_live_quality` (replicate **both** branches, not just `ArchiveError`). Idempotent with the pre-run auto-archive (`SKILL.md:141`) so a switch doesn't double-archive.

### D5 — Threshold (avoid noise)
Disclosure fires only when ≥2 testable languages each clear a minimum (recommend ≥ ~10% AND ≥ 5 files). **Denominator = `sum(counts.values())` from `detect_project_languages`, not `count_source_files()`** (different walkers).

---

# Implementation Plan (worker lane; red→green, mutation-verified, ASCII; against the git-tracked source)

1. `quality_gate.py:2712` — add `detect_project_languages()` (ranked testable counts); re-express `detect_project_language` as the testable winner — **result byte-identical to today** (regression pin).
2. `quality_gate.py` — add `--language <lang>` in `main` (`def main` `:6702`; the `for arg in argv` loop `:6736`); validate against `lang_to_valid` keys; exit 2 on unknown/non-testable. **Thread it through the chain `main → check_repo (:6669) → check_test_file_extension (:3840)`** — not the function alone.
3. `quality_gate.py:3840-3886` — when override set, use it; record `ran_on`.
4. `quality_gate.py` — per-repo disclosure block (in `check_repo`, additive after `RESULT:`); the **conditional** INDEX.md disclosure check (D2), NOT via `_V150_REQUIRED_SUMMARY_KEYS`.
5. `scripts/archive_lib.py` + clear helper — archive-then-clear with the error-gate (D4); reuse `archive_run` + `_clear_live_quality` (lift the latter to a shared module if the arunner path needs it outside `run_playbook.py`).
6. **arunner-native threading** — phase plan/prompts pass `--language` as a `var` into Phase-2 + the gate argv.
7. `bin/run_playbook.py` — cheap `--language` forward (deprecating).
8. `scripts/validate_phase_artifacts.py` — add to the lockstep (independent INDEX-summary validator).
9. SKILL.md ("Common overrides") + `references/runners_and_models.md` — document `--language` + the archive warning; `phase_prompts/phase2*` + `references/phase2_generation_guide.md` — honor the chosen language.
10. `schemas.md` §11 — `languages_detected`/`ran_on`/`untested_testable_languages` marked **conditional** (no `schema_version` bump).
11. **No detector work for clj** — it exists (056); add a hollow-`.clj`-FAILs test if not already present.

---

# Testing

### Unit / fixture (red→green, mutation-verified)
- **Detection exposure:** fixture with two testable langs → `detect_project_languages` ranks both; `detect_project_language` returns the same winner.
- **Byte-identical-winner regression pin (review #7):** assert `detect_project_language`'s winner is **byte-identical pre/post** the refactor across **every baseline repo + vaelii** — not just one fixture. **[re-Council A] vaelii is MANDATORY in the pin set** — no live baseline repo is Clojure (express=js+ts=one language, chi=go, virtio=c), so the 056 *clj* winner's protection rests on vaelii. **[re-Council C] Add a narrow-top-2-margin case** (a fixture with near-equal counts that flips if the tiebreak/order drifts — vaelii's 341:6 is too wide to exercise tiebreak drift). (Mutation: a different walk/exclude/tiebreak shifts a winner ⇒ bite.)
- **Disclosure required + correct (conditional):** a ≥2-testable run whose INDEX.md omits/mis-states the disclosure FAILs; a single-testable run with no disclosure PASSes. (Mutation: drop the conditional check ⇒ missing disclosure passes ⇒ bite.)
- **Override respected:** `--language py` on a go-dominant fixture validates the `.py` test as target + records `ran_on: py`; unknown `--language xyz` → exit 2. **[re-Council C] No-flag = unchanged companion pin:** without `--language`, behavior is byte-identical to today (so the override can't silently alter the default path).
- **Clojure substance — the hollow-`.clj`-FAILs test ALREADY EXISTS** at `test_quality_gate_language_detection.py:305-338` (hollow `(deftest)` → FAIL; real `(deftest … (is …))` → pass) — **confirmed present by the re-Council. Verify it runs green; do NOT add or rebuild.**
- **Archive-on-switch:** existing-language `quality/` + a differing `--language` run → archives into `previous_runs/`, clears live, **`previous_runs/` survives**; **error-gate**: a forced `archive_run` failure must NOT clear. (Mutation: drop the error-gate ⇒ bite.)
- **Threshold + boundary:** below-threshold second language → no warning; over-threshold → warning; an **exactly-at-threshold** case — the boundary is **≥-inclusive** (exactly ~10% AND exactly 5 files → fires).
- Full `bin/tests/` suite green ×3 + Python version.

### Real-repo validation (operator/worker-run)
- **vaelii (341 clj / 6 py / 15 sh) — detection + override + Clojure substance.** Confirms (a) 056 detection picks `clj`; (b) `--language py` runs a fresh pass on the Python slice and archives the clj `quality/`; (c) the **existing clj deep-check** catches a hollow clj test. **vaelii does NOT validate disclosure** — py is ~1.7% (6 / 347), below the threshold, so the multi-language block never fires here (review #1). Do not list vaelii as the disclosure test.
- **Disclosure — COMMITTED venue (review #3; re-Council C FIX — don't leave to discretion).** The worker FIRST runs `detect_project_languages` across the baseline (chi/virtio/express/gson/secbench2) and names the first repo with two **distinct** testable code languages over threshold (js+ts = one language via `lang_to_valid`'s `js → js ts`; Markdown not testable — so `express` does NOT qualify). **If none qualifies, the committed venue is a labeled in-repo fixture** `bin/tests/fixtures/multilang_disclosure/` (e.g. go=20 + py=8, both over threshold) — disclosure is validated there and the close-out states verbatim "disclosure: fixture-validated; no qualifying baseline repo." Either way a venue is committed in this design, not deferred to close-out discretion; and a real-repo disclosure claim is never made unless a named repo actually qualified.

### Self-Council (mandatory 3-panel before the worker files v1) — charter
(A) **correctness/spec** — `--language` threads end-to-end (gate + Phase-2 prompt); disclosure matches detection; no `RESULT:` drift; **the byte-identical-winner pin actually guards the 056 fix.** (B) **scope/regression** — single-language path untouched; archive error-gate can't lose data; INDEX/schemas/`validate_phase_artifacts` lockstep; **no skill-surface scope leaked back in.** (C) **test sufficiency/honesty** — pins bite; the **Clojure deep-check is verified (not rebuilt)** and the hollow-`.clj` test exists; the **disclosure test is real-repo or honestly fixture-only**; line refs are against the git-tracked source.

---

# Backlog (after v1.5.10, tracked — not in this release)
**Deep test-substance check for the remaining languages.** The no-op/hollow-assertion detector covers **go, py, clj** only; every other language is a conservative pass-through (extension-only). Extend it — same shape as go/py/clj — to **Rust, Java, C#, C, C++, JavaScript, TypeScript, Scala**, and other reasonable languages, each with its assertion-pattern set + body extractor + a hollow-test-FAILs test. The `--language` gate-guard-on-mismatch (D3) rides with this (real enforcement for a language requires its deep check). Also deferred: **full multi-language** (parallel per-language runs with combined reporting — Tier 1 fan-out / Tier 2 native) and the **skill-surface routing** feature (its own design + Council).

---

# Open decisions (Andrew's)
1. **Disclosure home** — INDEX.md §11 field + gate stdout block (recommended), vs. a dedicated `quality/LANGUAGES.md`.
2. **Threshold value** — *(recommend ≥ ~10% AND ≥ 5 files, tunable.)*
3. **Override config scope** — gate flag + arunner `var` + cheap `run_playbook.py` flag; also `~/.qpb/config.json`? *(recommend yes, mirroring `--council-roster`.)*

*(The former surface decisions are gone — split out. Override-honoring is now resolved in D3, not open.)*

---

# Council Review
**First Council (2026-06-20):** SHIP-WITH-FIXES on the original code-language proposal; its load-bearing fixes (conditional INDEX, archive error-gate, `validate_phase_artifacts` lockstep, `--council-roster` framing) are folded into D2/D3/D4. **Retracted as stale-copy artifacts (2026-06-21):** review findings #2 (Go/Python-only detector) and #10 (wrong line numbers) — both described the gitignored pre-056 `.github` copy, not the git-tracked source.

**Second Council (2026-06-21):** fresh 3-panel re-Council (opus/sonnet/opus) on the re-scoped language-only design, each verifying against the **git-tracked** source. **Unanimous SHIP-WITH-FIXES.** All three independently confirmed: the clj deep-check exists in the git-tracked source (`_CLOJURE_ASSERTION_PATTERNS:3960`, `_clojure_test_function_bodies:3966`, clj branch of `_body_has_real_assertion:4078-4084`, `lang_map={go,py,clj}:4118`→`:4143`), the stale-`.github`-copy thesis (0 clj, gitignored, pre-056), and that the **hollow-`.clj`-FAILs test already exists** (`test_quality_gate_language_detection.py:305-338`). No skill-surface leaked back; conditional-INDEX + archive error-gate confirmed correct. **Fixes folded into this revision:** (A) wrong line ref `:6420`→`main:6702`/loop `:6736`; thread `--language` through `main→check_repo:6669→check_test_file_extension:3840` (not the function alone); singular `detect_project_language` delegates to the plural; vaelii mandatory + a narrow-margin case in the byte-identical pin. (B) replicate **both** except branches in the archive error-gate (`run_playbook.py:3217-3243`); reuse the existing `is_legacy` flag for the INDEX exemption. (C) committed disclosure venue (named repo or labeled fixture, not discretion); no-flag-unchanged pin; threshold ≥-inclusive; sharpened the override-honoring phrasing (extension+substance enforced, generation-retargeting best-effort). Panelist files + synthesis: `AI-Driven Development/Quality Playbook/Reviews/QPB_v1.5.10_Language_Disclosure_ReCouncil/`. With these folded, the panel verdict is SHIP.
