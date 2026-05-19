# Recheck Results

> Recheck of quality/BUGS.md from 2026-04-16
> Recheck run: 2026-04-16
> Skill version: 1.4.1

## Summary

| Status | Count |
|--------|-------|
| Fixed | 25 |
| Partially fixed | 0 |
| Still open | 0 |
| Inconclusive | 0 |
| **Total** | **25** |

## Per-Bug Results

| Bug | Severity | Status | Evidence |
|-----|----------|--------|----------|
| BUG-H1 | HIGH | FIXED | repos/quality_gate.sh:77 colon-anchored grep in json_has_key() |
| BUG-H2 | HIGH | FIXED | repos/quality_gate.sh:866 outer-quoted array reconstruction |
| BUG-H17 | HIGH | FIXED | repos/quality_gate.sh:202,333-334 regex extended to BUG-([HML]\|[0-9]) |
| BUG-M3 | MEDIUM | FIXED | SKILL.md:963-979 Phase 2 entry gate now enforces all 12 checks |
| BUG-M4 | MEDIUM | FIXED | repos/quality_gate.sh:714-725 test_regression.* checked when bug_count > 0 |
| BUG-M5 | MEDIUM | FIXED | SKILL.md:334 empty previous_runs/ now emits warning and runs Phase 0b |
| BUG-M8 | MEDIUM | FIXED | repos/quality_gate.sh:170-173 spec_audits uses find; patches use per-bug iteration |
| BUG-M12 | MEDIUM | FIXED | repos/quality_gate.sh:628 func_test uses find instead of ls-glob |
| BUG-M13 | MEDIUM | FIXED | repos/quality_gate.sh:161-164 code_reviews uses find | grep -q . |
| BUG-M15 | MEDIUM | FIXED | repos/quality_gate.sh:540-579 full recheck-results.json validation section added |
| BUG-M16 | MEDIUM | FIXED | repos/quality_gate.sh:137-146 functional test uses find with all 4 patterns |
| BUG-M18 | MEDIUM | FIXED | repos/quality_gate.sh:398-444 sidecar-to-log cross-validation added |
| BUG-L6 | LOW | FIXED | repos/quality_gate.sh:83-98 json_str_val() returns __NOT_STRING__ for non-string values |
| BUG-L7 | LOW | FIXED | SKILL.md:7-9 frontmatter comment instructs updating all 8 version occurrences |
| BUG-L9 | LOW | FIXED | SKILL.md:1621 canonical and accepted naming formats documented |
| BUG-L10 | LOW | FIXED | SKILL.md:2044 rationale for recheck schema_version "1.0" documented |
| BUG-L11 | LOW | FIXED | SKILL.md:140-141,1458-1459 both templates now use harmonized REQ-NNN/enum format |
| BUG-L14 | LOW | FIXED | references/review_protocols.md:410 now shows [SHIP / FIX BEFORE MERGE / BLOCK] |
| BUG-L19 | LOW | FIXED | repos/quality_gate.sh:277-285 TDD summary sub-keys use json_key_count |
| BUG-L20 | LOW | FIXED | repos/quality_gate.sh:729-746 per-bug patch iteration instead of aggregate count |
| BUG-L21 | LOW | FIXED | SKILL.md:1654 Phase 5 entry gate (mandatory — HARD STOP) added |
| BUG-L22 | LOW | FIXED | SKILL.md:122 SEED_CHECKS.md added to artifact contract table |
| BUG-L23 | LOW | FIXED | repos/quality_gate.sh:513-530 groups[].result and uc_coverage enum validation added |
| BUG-L24 | LOW | FIXED | repos/quality_gate.sh:467-477 integration summary sub-keys validated |
| BUG-L25 | LOW | FIXED | SKILL.md:965 120-line minimum added to Phase 2 entry gate |

## Still Open — Details

None. All 25 bugs confirmed fixed.

## Verification Methodology

Reverse-apply check attempted for all 18 fix patches via `git apply --check --reverse`. All failed with "corrupt patch" — patches use illustrative diff format (not proper git-format with index lines), consistent with prior recheck behavior.

Source inspection performed for all 25 bugs:

- **quality_gate.sh bugs (14):** Read `repos/quality_gate.sh` at cited line numbers. Confirmed: colon-anchored json_has_key, __NOT_STRING__ in json_str_val, extended bug ID regexes, find-based artifact detection at all 5 previously vulnerable locations, test_regression.* existence check, per-bug patch iteration, sidecar-to-log cross-validation, TDD summary json_key_count, integration groups/summary/uc_coverage validation, recheck-results.json validation section, quoted array expansions.

- **SKILL.md bugs (10):** Read `SKILL.md` at cited line ranges. Confirmed: Phase 2 entry gate enforces all 12 checks including 120-line minimum; Phase 5 entry gate added; SEED_CHECKS.md in artifact contract table; Phase 0b handles empty previous_runs/; version consistency comment in frontmatter; auditor naming conventions documented; recheck schema 1.0 rationale documented; tdd-results.json templates harmonized.

- **review_protocols.md bug (1):** Confirmed recommendation enum updated to canonical values at line 410.

All 25 fixes confirmed present in current source tree (commit d7d65e8: "Fix all 25 bugs from Sonnet 4.6 bootstrap self-audit").
