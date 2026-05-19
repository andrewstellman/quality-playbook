# BUG-L24: integration-results.json Summary Sub-Keys Not Validated
<!-- Quality Playbook v1.4.1 — Bug Writeup — 2026-04-16 -->

## Summary

The quality gate checks that `integration-results.json` has a `summary` key (line 393) but never validates the four required sub-keys: `total_groups`, `passed`, `failed`, `skipped` (SKILL.md:1252-1255). By contrast, `tdd-results.json` summary sub-keys ARE checked at lines 259-265 (weakly, via `json_has_key` — which is itself BUG-L19, but at least present). The integration validation is one level worse: zero sub-key checks. An integration-results.json with `"summary": {}` or `"summary": {"status": "ok"}` (wrong keys) passes gate validation, breaking any downstream aggregation script.

## Spec Reference

REQ-027 (Tier 3): "Gate must validate integration-results.json summary sub-keys (total_groups, passed, failed, skipped) using json_key_count, consistent with tdd-results.json summary validation at quality_gate.sh:259-265."

SKILL.md:1252-1255: Defines integration-results.json summary schema with sub-keys `total_groups` (int), `passed` (int), `failed` (int), `skipped` (int).

## The Code

```bash
# quality_gate.sh:259-265 — tdd summary sub-keys ARE checked (weakly)
for skey in total verified confirmed_open red_failed green_failed; do
    if ! json_has_key "$tdd_json" "$skey"; then
        gate_fail "tdd-results.json: summary missing required sub-key '$skey'"
    fi
done
```

```bash
# quality_gate.sh:393-394 — integration summary: ONLY root key presence
if ! json_has_key "$int_json" "summary"; then
    gate_fail "integration-results.json: missing required key 'summary'"
fi
# (no sub-key loop follows)
```

This is a direct parity gap: tdd gets sub-key validation (even if weak per BUG-L19), integration gets none.

## Observable Consequence

1. Agent writes `"summary": {}`. Gate passes. Aggregation script doing `jq .summary.total_groups` returns `null`.
2. Agent writes `"summary": {"status": "complete"}`. Gate passes. All four required sub-keys absent, aggregation breaks silently.
3. Multi-run dashboard that sums `total_groups` across integration runs produces wrong totals — gate never caught the omission.

## The Fix

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ After integration summary root key check (line 393) @@
 if ! json_has_key "$int_json" "summary"; then
     gate_fail "integration-results.json: missing required key 'summary'"
 fi
+# BUG-L24 fix: validate integration summary sub-keys
+# SKILL.md:1252-1255: total_groups, passed, failed, skipped
+int_summary_keys=("total_groups" "passed" "failed" "skipped")
+for skey in "${int_summary_keys[@]}"; do
+    scount=$(json_key_count "$int_json" "$skey")
+    if [ "$scount" -eq 0 ]; then
+        gate_fail "integration-results.json: summary missing required sub-key '$skey' — SKILL.md:1252-1255"
+    fi
+done
```

Note: uses `json_key_count` (colon-anchored, strong) rather than `json_has_key` (no colon, weak — BUG-L19 class). This is strictly better than the tdd sub-key check pattern.

Full patch in `quality/patches/BUG-L24-fix.patch`.
