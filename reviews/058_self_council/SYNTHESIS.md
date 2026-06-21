# 058 self-Council — SYNTHESIS — unanimous SHIP (round 1)

Mandatory 3-panel adversarial self-Council on instruction 058
(v1.5.10 language disclosure + `--language` override), branch `1.5.10`.
Panelists were independent Agent subagents with role-lock preambles,
each grounding against the **git-tracked** source
(`plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py`),
not the gitignored `.github` copy.

| Panel | Charter | Verdict |
|-------|---------|---------|
| A | correctness / spec compliance | **SHIP** (1 NIT) |
| B | scope discipline / regression safety | **SHIP** (1 NIT) |
| C | test sufficiency / honesty | **SHIP** (mutation-confirmed) |

**Unanimous SHIP, round 1** — no FIX-REQUIRED.

## Confirmed (where panels agree — highest confidence)
- **D1** `detect_project_language` is a thin delegate to
  `detect_project_languages(...)[0][0]`; the `sorted((-count,
  order_index))[0]` winner is **provably byte-identical** to the pre-058
  `max(counts, key=(count, -order_index))` (order_index unique per lang).
  Panel C **mutation-confirmed** the byte-identical pin bites: flipping
  the live tiebreak `order_index → -order_index` flipped the
  narrow-margin fixture rs→ts and failed the pin; reverted + re-ran green.
- **D3** `--language` threads end-to-end `main → check_repo →
  check_test_file_extension` (not the body alone); validates against
  `_LANG_TO_VALID` (exit 2 on unknown, confirmed live); validates the
  OVERRIDE extension and records `ran_on`.
- **D2** the stdout disclosure block (additive, after `RESULT:`, before
  `::QPB::`) and the conditional INDEX check fire on the **same**
  `_disclosure_fires(detect_project_languages(...))` predicate; **no
  RESULT/total/::QPB:: drift**; conditional keys are NOT in the
  unconditional `_V150_REQUIRED_SUMMARY_KEYS`; `is_legacy` exemption.
- **D4** `archive_on_language_switch` replicates **both** error-gate
  branches (`ArchiveError` + bare `Exception`), each returning before
  `_clear_live_quality`; `.qpb_language` sentinel preservation is
  provably additive (no pre-058 tree has the file); wired before
  `archive_previous_run` at both call sites (idempotent).
- **Scope**: single-language path byte-identical; **no skill-surface
  leaked in** (the `surface` grep hits are a comment verb, a
  "never surfaced as testable" docstring, and 1.6.x split-out prose);
  Markdown never a target.
- **Lockstep**: schemas.md §11 / gate / `validate_phase_artifacts.py`
  agree; the validator **imports the gate's own detector + threshold**
  so it cannot drift; no `schema_version` bump.
- **056 clj deep-check VERIFIED, not rebuilt**: the substantive
  hollow-`.clj`-FAILs test still lives at
  `test_quality_gate_language_detection.py:305-338` and passes; 058 only
  adds a light confirmation.
- **Disclosure venue honesty**: secbench2 genuinely qualifies as a real
  venue (ts=14060, py=7944, both over threshold); the labeled fixture is
  the hermetic unit venue; no claim exceeds what ran.
- Suite **2419 → 2443 (+24), 3× stable, Python 3.14.6** — only the 5
  documented pre-existing README/adopter-doc-drift baseline failures.

## NITs / follow-ups (non-blocking)
1. **[A]** The `ran_on` line emitted inside `check_test_file_extension`
   is an `info()` log line, distinct from the persisted INDEX `ran_on`
   field (written by the runner). Both layers exist; no gap.
2. **[B]** The validator exempts legacy via `sv != "1.0"` while the gate
   uses the broader `is_legacy`; the validator's pre-existing Phase-≥5
   `sv == "2.0"` requirement makes the divergence unreachable for any
   real legacy archive → no false FAIL.

VERDICT: SHIP
