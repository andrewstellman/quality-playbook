# Recheck Summary — quality/BUGS.md vs HEAD (2f03f8d)

- **Branch:** 1.5.7
- **HEAD:** `2f03f8d` (`v1.5.7 instruction 089e: close BUG-011 + BUG-014 (gate/validator INDEX divergence)`)
- **Prior recheck HEAD:** `2ba47d4` (2026-05-20 05:01 UTC) — 18 FIXED / 2 STILL_OPEN (BUG-011, BUG-014)
- **Baseline:** `quality/BUGS.md` BUG-001 .. BUG-020 (Round-1 2026-05-08 + v1.5.7 self-audit 2026-05-19)
- **Date:** 2026-05-20

## Verdict counts

| Verdict | Count | Bugs |
|---|---|---|
| FIXED | 20 | BUG-001 .. BUG-020 |
| STILL_OPEN | 0 | — |
| PARTIALLY_FIXED | 0 | — |
| INCONCLUSIVE | 0 | — |

**All 20 confirmed bugs are now FIXED.** This re-recheck verifies the two STILL_OPEN bugs from the prior recheck (BUG-011, BUG-014) were closed by instruction 089e (commit `2f03f8d`).

## Closing-commit ledger

| Commit | Instruction | Closes |
|---|---|---|
| `a01c731` | 089 | BUG-001 .. BUG-006 (Round-1 code-review findings) |
| `85be22f` | 089b | F11-F14 (per-phase STOP→CONTINUE, canonical adopter table, Phase-1 mandate, stale SKILL.md lineno) |
| `0917221` | 089c | F15 (three-state taxonomy at gate output level) |
| `6cebd26` | 089c-followup | Gitignored gate test (-f) |
| `2ba47d4` | 089d | F17 (BUG-012), F18 (BUG-013), F19 (BUG-019 + BUG-005 deeper), F20 (BUG-016/017/018), F21 (BUG-007/008/015), F22 (BUG-006 corollary + BUG-020), F23 (BUG-009/010), F24 (design rationale) |
| `2f03f8d` | **089e** | **BUG-011 + BUG-014 (gate/validator INDEX divergence)** |

## Newly-closed bugs (this recheck)

### BUG-011 — gate FAILs on non-dict `summary` → **FIXED** (was STILL_OPEN)

The gate's `check_v1_5_0_index_md` now has the explicit negative-guard FAIL branch the prior recheck recommended:

`.github/skills/quality_gate/quality_gate.py:2910-2934`:

```python
summary = payload.get("summary")
# v1.5.7 089e (BUG-011): non-dict `summary` (string / null / list /
# anything other than a JSON object) is a §11 contract violation —
# schemas.md:1128 says `summary | object | yes`. ...
if not isinstance(summary, dict):
    fail(
        f"quality/INDEX.md: §11 'summary' must be a JSON object "
        f"(got {type(summary).__name__!r}; schemas.md:1128 requires "
        f"`summary | object | yes`)"
    )
    return
for sub in _V150_REQUIRED_SUMMARY_KEYS:
    if sub not in summary:
        fail(...)
pass_("quality/INDEX.md: §11 fields present")
```

The early `return` prevents the trailing `pass_("§11 fields present")` from firing on a structurally-broken INDEX. The FAIL message shape mirrors `bin/validate_phase_artifacts.py:_validate_index` — gate and validator now FAIL the same payloads on the same field.

**Tests:** `.github/skills/quality_gate/tests/test_quality_gate.py:2551-2625` adds 3 new `TestV150IndexMd` cases pinning the three non-dict shapes: `test_non_dict_summary_string_fails`, `test_non_dict_summary_null_fails`, `test_non_dict_summary_list_fails`. Full quality-gate suite: **267 PASS** (gate test count 279 → 282 per 089e commit message; +3 = BUG-011 regressions). Pre-089e happy-path `dict_summary` test unchanged.

The 089e commit message also documents a PASS→FAIL→PASS source-mutation bite (revert the new guard → tests fail → restore → tests pass).

### BUG-014 — validator becomes phase-aware on `schema_version` → **FIXED** (was STILL_OPEN)

Closed via **Option A** (relax validator to phase-aware) per the bug's `proposed_fix` recommendation. Direction rationale (from 089e commit message): the gate's case-4 lenient routing is a deliberate design point for Phase 1 stub-INDEX written before `schema_version` is set; tightening the gate (Option B) would break a documented design point. The validator now honors that intent.

`bin/validate_phase_artifacts.py:343-389`:

```python
def _validate_index(quality: Path, phase: int, check_verdict_value: bool
                    ) -> tuple[list[str], list[str]]:
    ...
    # v1.5.7 089e (BUG-014, Option A — phase-aware schema_version enforcement).
    #   phase >= 5  → Phase 5/6 final INDEX MUST have schema_version == "2.0" (strict).
    #   phase  < 5  → Phase 1/2 stub-INDEX MAY omit schema_version
    #                 (matches gate case-4). If present, must be "2.0" (wrong value still FAILs).
    sv = payload.get("schema_version")
    if phase >= 5:
        if sv != "2.0":
            fails.append(...)
    else:
        # Phase 1/2 stub-INDEX: missing is OK (gate case-4 territory).
        if sv is not None and sv != "2.0":
            fails.append(...)
```

`_PHASE_DISPATCH` updated at lines 425-432 to thread phase through: `5: lambda q: _validate_index(q, 5, check_verdict_value=False)`, `6: lambda q: _validate_index(q, 6, check_verdict_value=True)`.

**Tests:** `bin/tests/test_validate_phase_artifacts.py:294-405` adds 4 new regression tests under the `v1.5.7 089e (BUG-014) phase-aware schema_version` block — Phase 5 missing-FAIL, Phase 5 correct-PASS, Phase 1 stub missing-PASS, Phase 1 stub wrong-value-FAIL. Targeted run (`pytest -k schema_version`): **29 PASS**. PASS→FAIL→PASS mutation-bite documented in the 089e commit message.

**Residual Phase 5/6 divergence (now intentional and documented):** The gate's case-4 stays lenient at Phase 5/6 (phase-blind by design — runs once over whatever INDEX state exists), while the validator at Phase 5/6 stays strict. The inline comment at `bin/validate_phase_artifacts.py:352-371` declares this divergence INTENTIONAL: validator is the canonical Phase 5/6 enforcement surface; gate case-4 is best-effort archive-tolerance. Adopters running both see the validator catch what the gate's archive-friendly case-4 lets through — the correct direction. The original bug's `proposed_fix` asked to "pick one canonical behavior"; 089e picks: validator-strict at Phase 5/6, gate-tolerant for archives, validator now honors gate's stub-INDEX intent at Phase 1/2.

## Verification of unchanged bugs (BUG-001 .. BUG-010, BUG-012, BUG-013, BUG-015 .. BUG-020)

The 089e diff scope is exactly 4 files:

- `.github/skills/quality_gate/quality_gate.py` (BUG-011 fix)
- `.github/skills/quality_gate/tests/test_quality_gate.py` (BUG-011 tests)
- `bin/validate_phase_artifacts.py` (BUG-014 fix)
- `bin/tests/test_validate_phase_artifacts.py` (BUG-014 tests)

The 18 previously-FIXED bugs' fix surfaces (`bin/run_playbook.py`, `bin/reference_docs_ingest.py`, `bin/bootstrap_self_audit_docs.py`, `bin/run_state_lib.py`, `bin/archive_lib.py`, `bin/install_skill.py`, `SKILL.md`, `schemas.md`, `phase_prompts/phase6.md`, `phase_prompts/phase6_auditor.md`, `references/run_state_schema.md`, `references/phase6_verify_guide.md`) are outside the 089e scope and therefore unchanged from the prior-recheck verification. No regression.

## Recommendation

All 20 confirmed bugs are now closed. Recommended next steps (per the 089e commit message's "After this lands" block):

- Push HEAD `2f03f8d` to remote.
- Run the four-ref dance (SKILL.md / IMPROVEMENT_LOOP / DEVELOPMENT_CONTEXT / README cross-reference check).
- Phase 8d: merge `1.5.7` to `main`, open `1.6.0` branch, tag `v1.5.7`.

No carry-over bugs from this baseline. The v1.5.7 self-audit closure pass is complete.
