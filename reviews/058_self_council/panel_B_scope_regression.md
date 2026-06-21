# Panel B — Scope Discipline / Regression Safety — Instruction 058 (v1.5.10)

**Role:** Independent adversarial reviewer, Panel B of the 058 self-Council.
Charter: single-language path untouched; no skill-surface scope leak; archive
error-gate can't lose data; INDEX/schemas/validator lockstep; phase2 + hash
coherence. Grounded against the git-tracked source
(`plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py`),
not the `.github` stale copy. All line refs verified against the working tree.

---

## 1. SINGLE-LANGUAGE PATH UNTOUCHED — PASS

The pre-058 path is byte-identical for a one-testable-language (or none) repo.

- **Winner is byte-identical by construction.** `detect_project_language` is
  now a thin delegate: `detect_project_languages(repo_dir)[0][0] if ranked
  else ""` (`quality_gate.py:2810-2818`). The plural builds the *same* `counts`
  via the *same* walk / extension set / `_INSTALL_MARKER_DIRS` excludes
  (only the return statement changed: `:2805-2810`). The old winner was
  `max(counts, key=lambda lang: (counts[lang], -order_index[lang]))`; the new
  one is `sorted(counts.items(), key=lambda kv: (-kv[1], order_index[kv[0]]))[0]`.
  Highest count first in both; on a tie, `max` picks the largest `-order_index`
  (= smallest `order_index`), and `sorted` ascending puts the smallest
  `order_index` at `[0]`. Identical winner. Empty repo: old returned `""`,
  new returns `[]` → delegate returns `""`. Equivalent.
  Pinned by `test_baseline_repos_winner_byte_identical`,
  `test_vaelii_winner_byte_identical_MANDATORY`, and
  `test_narrow_margin_tiebreak_winner_byte_identical`
  (`test_language_disclosure_override_058.py:140-186`) — vaelii (the only clj
  winner) and a `rs=6 == ts=6` margin fixture are both in the pin set, exactly
  as the design's re-Council A/C fixes require.

- **Disclosure conditional actually gates.** `_disclosure_fires` requires
  `len(languages_over_disclosure_threshold(ranked)) >= 2`
  (`quality_gate.py:2884-2886`). `_maybe_record_language_disclosure` early-
  returns when `len(over) < 2` (`:2900-2902`). For a single/zero-testable repo
  the disclosure ledger stays empty → `_emit_language_disclosures` iterates
  nothing → no new stdout. Verified by
  `test_single_lang_without_disclosure_passes` and
  `test_below_threshold_does_not_fire` (`:204`, `:287`).

- **INDEX check conditional + legacy exemption.** The new block is
  `if not is_legacy and _disclosure_fires(detect_project_languages(q.parent))`
  (`quality_gate.py:5537`+). The new keys are NOT in
  `_V150_REQUIRED_SUMMARY_KEYS` (the unconditional loop at `:5533`), so no
  single-language or archived run is failed for omitting them. `is_legacy` is
  the same in-scope flag computed at `:5480-5497`. Verified by
  `test_legacy_schema_exempt` and `test_single_lang_without_disclosure_passes`.

- **Extension check default branch unchanged.** `check_test_file_extension`
  gained an optional `language=None` param; when falsy it falls through to the
  unchanged `detect_project_language(repo_dir)` path (`:3981-3987`).
  `lang_to_valid` was lifted verbatim to module-scope `_LANG_TO_VALID` with the
  identical 11 entries (`:3895` vs old inline dict) — no key/value change.
  Pinned by `test_without_override_detected_language_used` (`:396`).

No regression on the single-language path.

## 2. NO SKILL-SURFACE SCOPE LEAKED IN — PASS

`git diff | grep -in surface` yields four hits, all benign:
- `run_playbook.py:232` comment — the verb "surface and bail".
- `quality_gate.py` detector docstring — "never surfaced as a (testable)
  language" (the opposite of leaking surfaces in).
- two hits in `docs/design/QPB_v1.6.0_Design.md` — prose that explicitly marks
  the surface-routing work as split-out/provisional for 1.6.x.

No `--surface` flag, no Phase-0 Hybrid dominance, no "testable Markdown surface"
model, no pipeline routing. Markdown/shell/edn are explicitly excluded from the
testable language set (`detect_project_languages` counts only `language_order`
extensions; docstring `:2722-2731`). The split-out proposal lives in its own
untracked design file (`QPB_v1.6.x_Skill_Surface_Routing_Proposal.md`), out of
scope for this release. Clean.

## 3. ARCHIVE ERROR-GATE CAN'T LOSE DATA — PASS

`archive_on_language_switch` (`run_playbook.py:3357-3415`) replicates BOTH
except branches of `archive_previous_run` (`:3280-3307`):
- `except archive_lib.ArchiveError` → stderr WARN → `return False` BEFORE
  `_clear_live_quality` (`:3398-3406`).
- `except Exception` (bare, `# noqa: BLE001`) → stderr WARN → `return False`
  BEFORE clear (`:3407-3413`).
- `_clear_live_quality` only on the success fall-through (`:3414`).
A failed archive can never clear live. Verified by
`test_error_gate_archive_error_does_not_clear` and
`test_error_gate_bare_exception_does_not_clear`
(`test_language_disclosure_override_058.py:493-535`), both asserting the live
tree survives — observed firing in the test run (the WARN lines print and the
tests pass).

**Additivity of the `.qpb_language` changes.** Both `_clear_live_quality`
preserving `_LANGUAGE_SENTINEL` (`:2664-2680`) and `archive_previous_run`'s
emptiness check adding it to `non_live` (`:3258-3261`) are no-ops for any
pre-058 tree, because the sentinel file is introduced by 058 and never exists
on an older `quality/`. So an old tree's clear/archive behavior is unchanged.
The double-archive guard (a tree holding only the sentinel counts as empty) is
correct and only relevant post-switch.

**Switch ordering is safe and idempotent.** In both `run_one_phased`
(`:4787-4793`) and `run_one_singlepass` (`:4900-4907`), `archive_on_language_switch`
runs BEFORE `archive_previous_run`; the switch clears the live tree (leaving
only the sentinel), so the subsequent auto-archive no-ops on the now-"empty"
tree. `_write_run_language` stamps the new language after. Consistent with D4.

## 4. INDEX / SCHEMAS / VALIDATOR LOCKSTEP — PASS

- **Conditional, no schema bump.** `SCHEMA_VERSION_CURRENT` is still `"2.0"`
  (`quality_gate.py:4751`); the only `schema_version` token in the diff is a
  comment. `schemas.md` §11 adds the three fields marked **conditional
  (v1.5.10 058)** with the exact ≥10%-AND-≥5-files trigger and the
  "Markdown never listed" note (`schemas.md:1157-1159`).
- **Validator imports the gate's detector — zero drift by construction.**
  `validate_phase_artifacts.py:113-137` path-loads `quality_gate.py` and binds
  `_gate_lang_helpers = (detect_project_languages, languages_over_disclosure_threshold)`.
  The conditional check (`:463-498`) calls `len(_over(_detect(quality.parent)))
  >= 2` — the *same functions* the gate's `check_v1_5_0_index_md` uses. No
  re-implemented threshold. Degrades gracefully (`_gate_lang_helpers = None` →
  skip) if the gate can't be located, with the gate remaining primary
  enforcement. Same field set and same empty-value FAIL shape as the gate.
- Verified by `test_two_lang_missing_disclosure_fails`,
  `test_two_lang_with_disclosure_passes`,
  `test_single_lang_without_disclosure_passes`, `test_legacy_schema_exempt`
  (`:251-333`). All 29 `test_validate_phase_artifacts` tests pass.

**NIT (non-blocking).** The validator exempts via `sv != "1.0"` (`:466`) while
the gate exempts via `is_legacy`, which is also True for the heuristic-legacy
case (`schema_version` None/"" with `target_project_type` but no
`target_role_breakdown`, `quality_gate.py:5482-5485`). The two exemptions are
not literally identical. In practice this is harmless: the validator already
FAILs any Phase ≥ 5 final INDEX whose `sv != "2.0"` (`:421-426`), so by the
time the disclosure check runs on a final INDEX, `sv` is "2.0" and neither the
`"1.0"` nor the heuristic-legacy branch is reachable; the heuristic case only
arises on stub INDEX (phase < 5) which is a different path. No false FAIL on a
real legacy archive results. Worth a one-line comment noting the equivalence,
but not a regression.

## 5. phase2.md EDIT + HASH BUMP COHERENT — PASS

`phase2.md` adds the `--language`/`LANGUAGE OVERRIDE` honoring note to the
"Functional tests" deliverable bullet (`phase2.md:22`). The byte-equality pin
in `test_phase_prompts_externalized.py:367-372` is updated to the new length
(10114 → 10395) and recomputed sha256, with an explanatory comment — the
sanctioned intentional-edit acknowledgement signal. The test runs green (in the
55-test 058 suite). The prompt directive emitted by
`run_playbook._language_prompt_directive` (`:1345-1361`) and the phase2 bullet
agree on the "one language per run / write tests in THAT language" contract.
`references/phase2_generation_guide.md` carries the matching guidance. Coherent.

---

## Test evidence
- `test_language_disclosure_override_058` + `test_phase_prompts_externalized`
  + `test_quality_gate_language_detection`: **Ran 55 tests — OK.**
- `test_validate_phase_artifacts`: **Ran 29 — OK.**
- `test_archive_preservation` + `test_archive_lib` + `test_quality_gate_gates`
  + `test_run_playbook`: **Ran 636 — OK (skipped=1).**
No failures across the suites touching this change.

## Verdict rationale
Single-language path is byte-identical and the new behavior is strictly
conditional behind `len(over) >= 2` + `not is_legacy`. No skill-surface scope
leaked in. The archive error-gate replicates both except branches and returns
before clear, with the sentinel changes additive (impossible to affect a
pre-058 tree). INDEX/schemas/validator are in lockstep via a shared, imported
detector with no schema bump. phase2 edit and hash bump are coherent. The one
finding (validator `sv != "1.0"` vs gate `is_legacy`) is a documentation NIT
with no reachable false-FAIL. Nothing rises to a regression or scope leak.

VERDICT: SHIP
