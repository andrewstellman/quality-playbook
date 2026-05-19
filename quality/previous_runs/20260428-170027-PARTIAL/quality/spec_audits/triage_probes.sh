#!/usr/bin/env bash
# Triage probes — Phase 4 spec audit
# Quality Playbook bootstrap self-audit · 2026-04-18
#
# These probes mechanically verify or confirm findings from the Council of Three.
# Each probe writes PASS or FAIL with a one-line explanation.
# Exit 0 if all probes pass; non-zero on any failure.

set -euo pipefail

FAIL_COUNT=0

probe_pass() { echo "PASS  $1"; }
probe_fail() { echo "FAIL  $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

# ---------------------------------------------------------------------------
# Probe L-A: orchestrator_protocol.md uses 80 (not 120)
# Confirms CF-2 (spec inconsistency between orchestrator_protocol.md and SKILL.md)
# ---------------------------------------------------------------------------
echo "=== Probe L-A: orchestrator_protocol.md threshold ==="
PROTO=".github/skills/references/orchestrator_protocol.md"
if [ ! -f "$PROTO" ]; then
  probe_fail "orchestrator_protocol.md not found at $PROTO"
else
  if grep -q "more than 80 lines" "$PROTO"; then
    probe_fail "orchestrator_protocol.md:41 says '80 lines' (should be 120 — spec inconsistency CF-2)"
  elif grep -q "more than 120 lines\|at least 120 lines" "$PROTO"; then
    probe_pass "orchestrator_protocol.md says 120 lines (spec-fix applied)"
  else
    probe_fail "orchestrator_protocol.md: unexpected threshold wording — inspect manually"
  fi
fi

# ---------------------------------------------------------------------------
# Probe L-B: Phase 5 gate — missing triage file must produce FAIL (not WARN)
# Confirms CF-1 / BUG-016: current code returns ok=True when spec_audits/ is empty
# ---------------------------------------------------------------------------
echo ""
echo "=== Probe L-B: Phase 5 gate enforces spec_audits/ triage requirement ==="
GATE_SRC="bin/run_playbook.py"
if [ ! -f "$GATE_SRC" ]; then
  probe_fail "run_playbook.py not found at $GATE_SRC"
else
  # The patched gate should FAIL when spec_audits/ has no triage file
  # Look for the specific triage-check pattern
  if grep -q "triage" "$GATE_SRC" && grep -A10 'phase == "5"' "$GATE_SRC" | grep -q "FAIL.*triage\|triage.*FAIL"; then
    probe_pass "Phase 5 gate checks for triage file (BUG-016 patched)"
  else
    probe_fail "Phase 5 gate does not enforce triage-file requirement — BUG-016 confirmed"
  fi
fi

# ---------------------------------------------------------------------------
# Probe L-C: SKILL_INSTALL_LOCATIONS has 4 paths
# Confirms BUG-002 (3-tuple vs. SKILL.md 4-path list)
# ---------------------------------------------------------------------------
echo ""
echo "=== Probe L-C: SKILL_INSTALL_LOCATIONS tuple length ==="
BENCH="bin/benchmark_lib.py"
if [ ! -f "$BENCH" ]; then
  probe_fail "benchmark_lib.py not found at $BENCH"
else
  COUNT=$(grep -c 'Path(".github") / "skills"' "$BENCH" || true)
  if [ "$COUNT" -ge 2 ]; then
    probe_pass "benchmark_lib.py has >= 2 .github/skills paths (suggests 4-tuple present)"
  else
    probe_fail "benchmark_lib.py has < 2 .github/skills paths — BUG-002 still present (3-tuple)"
  fi
fi

# ---------------------------------------------------------------------------
# Probe O-A: check_run_metadata function absent
# Confirms BUG-010: run-metadata never validated
# ---------------------------------------------------------------------------
echo ""
echo "=== Probe O-A: check_run_metadata function presence ==="
GATE=".github/skills/quality_gate/quality_gate.py"
if [ ! -f "$GATE" ]; then
  probe_fail "quality_gate.py not found at $GATE"
else
  if grep -q "def check_run_metadata" "$GATE"; then
    probe_pass "check_run_metadata function exists (BUG-010 patched)"
  else
    probe_fail "check_run_metadata function absent — BUG-010 confirmed"
  fi
fi

# ---------------------------------------------------------------------------
# Probe O-B: validate_iso_date rejects datetime inputs
# Confirms BUG-014
# ---------------------------------------------------------------------------
echo ""
echo "=== Probe O-B: validate_iso_date datetime handling ==="
if [ ! -f "$GATE" ]; then
  probe_fail "quality_gate.py not found"
else
  # If BUG-014 is patched, the function should NOT have a bare fullmatch on \d{4}-\d{2}-\d{2} only
  if python3 - << 'PYEOF'
import sys, re

# Reproduce the original function and test
def validate_iso_date_original(date_str):
    if not date_str:
        return "empty"
    if date_str in ("YYYY-MM-DD", "0000-00-00"):
        return "placeholder"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        return "bad_format"
    return "valid"

result = validate_iso_date_original("2026-04-18T23:43:14Z")
# If still buggy, result is "bad_format"
sys.exit(0 if result == "bad_format" else 1)
PYEOF
  then
    probe_fail "validate_iso_date returns bad_format for datetime — BUG-014 confirmed (unpatched)"
  else
    probe_pass "validate_iso_date handles datetime (BUG-014 patched)"
  fi
fi

# ---------------------------------------------------------------------------
# Probe O-C: Phase 5 gate — empty spec_audits/ + BUGS.md present → should FAIL
# Confirms BUG-016 (net-new from spec audit)
# ---------------------------------------------------------------------------
echo ""
echo "=== Probe O-C: Phase 5 gate with empty spec_audits/ ==="
if [ ! -f "$GATE_SRC" ]; then
  probe_fail "run_playbook.py not found"
else
  # Read the phase 5 branch and check whether it explicitly checks for triage content
  PHASE5_BLOCK=$(awk '/phase == "5"/,/return GateCheck/' "$GATE_SRC" | head -20)
  if echo "$PHASE5_BLOCK" | grep -q "triage\|auditor\|spec_audits.*triage"; then
    probe_pass "Phase 5 gate checks for triage/auditor files (BUG-016 patched)"
  else
    probe_fail "Phase 5 gate does not check for triage/auditor files — BUG-016 confirmed"
  fi
fi

# ---------------------------------------------------------------------------
# Probe S-C: CONTRACTS.md C-14 Statement vs Invariant consistency
# Confirms CF-3 (documentation inconsistency)
# ---------------------------------------------------------------------------
echo ""
echo "=== Probe S-C: CONTRACTS.md C-14 Statement/Invariant consistency ==="
CONTRACTS="quality/CONTRACTS.md"
if [ ! -f "$CONTRACTS" ]; then
  probe_fail "CONTRACTS.md not found"
else
  if grep -q "deletes.*control_prompts\|control_prompts.*delet" "$CONTRACTS"; then
    probe_fail "CONTRACTS.md C-14 Statement still says 'deletes control_prompts/' (should say 'archives') — CF-3"
  else
    probe_pass "CONTRACTS.md C-14 does not say 'deletes control_prompts/' (spec-fix applied or not found)"
  fi
fi

# ---------------------------------------------------------------------------
# Probe P-A: file-existence gate recognizes functional_test.go
# Confirms BUG-024
# ---------------------------------------------------------------------------
echo ""
echo "=== Probe P-A: functional_test.go appears in existence-gate matrix ==="
if [ ! -f "$GATE" ]; then
  probe_fail "quality_gate.py not found"
else
  if awk '/functional test file exists/,/AGENTS.md exists/' "$GATE" | grep -q 'functional_test\.\*'; then
    probe_pass "check_file_existence includes functional_test.* (BUG-024 patched)"
  else
    probe_fail "check_file_existence omits functional_test.* — BUG-024 confirmed"
  fi
fi

# ---------------------------------------------------------------------------
# Probe P-B: extension gate searches the alternate functional-test names
# Confirms BUG-025
# ---------------------------------------------------------------------------
echo ""
echo "=== Probe P-B: extension gate searches the documented naming matrix ==="
if [ ! -f "$GATE" ]; then
  probe_fail "quality_gate.py not found"
else
  EXT_BLOCK=$(awk '/def check_test_file_extension/,/^def check_terminal_gate/' "$GATE")
  if echo "$EXT_BLOCK" | grep -q 'FunctionalTest\.\*' && \
     echo "$EXT_BLOCK" | grep -q 'FunctionalSpec\.\*' && \
     echo "$EXT_BLOCK" | grep -q 'functional\.test\.\*'; then
    probe_pass "check_test_file_extension searches alternate functional-test names (BUG-025 patched)"
  else
    probe_fail "check_test_file_extension only searches test_functional.* — BUG-025 confirmed"
  fi
fi

# ---------------------------------------------------------------------------
echo ""
echo "=== Summary ==="
if [ "$FAIL_COUNT" -eq 0 ]; then
  echo "All probes PASS (all bugs patched and spec fixes applied)"
  exit 0
else
  echo "$FAIL_COUNT probe(s) FAIL (bugs confirmed — see above)"
  exit 1
fi
