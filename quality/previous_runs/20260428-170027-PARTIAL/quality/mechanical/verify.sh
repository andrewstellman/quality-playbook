#!/usr/bin/env bash
# Mechanical verification driver for Phase 2 closed-set claims.
#
# Runs each extractor in order, captures stdout/stderr to a log, and returns
# the aggregated exit code (0 if all extractors passed, non-zero if any
# extractor reported a divergence between source and Phase 2 docs).
#
# Run from the QPB root:
#     bash quality/mechanical/verify.sh
#
# Receipts:
#     quality/results/mechanical-verify.log   — full transcript
#     quality/results/mechanical-verify.exit  — aggregated exit code (single integer)

set -u
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QPB_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_DIR="$QPB_ROOT/quality/results"
LOG="$RESULTS_DIR/mechanical-verify.log"
EXITFILE="$RESULTS_DIR/mechanical-verify.exit"

mkdir -p "$RESULTS_DIR"
: > "$LOG"

EXTRACTORS=(
    "extract_install_locations.py"
    "extract_protected_prefixes.py"
    "extract_strategies.py"
    "extract_phases.py"
    "extract_verdict_enum.py"
)

AGG=0
for script in "${EXTRACTORS[@]}"; do
    {
        echo "=== $script ==="
    } >> "$LOG"
    if python3 "$SCRIPT_DIR/$script" >> "$LOG" 2>&1; then
        echo "[PASS] $script" >> "$LOG"
    else
        rc=$?
        echo "[FAIL rc=$rc] $script" >> "$LOG"
        AGG=1
    fi
    echo "" >> "$LOG"
done

{
    echo "=== SUMMARY ==="
    if [ "$AGG" -eq 0 ]; then
        echo "ALL PASS — $(( ${#EXTRACTORS[@]} )) extractor(s) agree with Phase 2 CURRENT claims."
    else
        echo "FAIL — at least one extractor reported a divergence."
    fi
} >> "$LOG"

echo "$AGG" > "$EXITFILE"

# Mirror the summary line to stdout so interactive callers see it too.
tail -1 "$LOG"
exit "$AGG"
