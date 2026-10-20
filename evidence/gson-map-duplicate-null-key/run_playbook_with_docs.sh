#!/bin/bash
# v1.2.15 Quality Playbook — Gson end-to-end execution with doc-aware prompt 1
set -euo pipefail

PROMPT_DIR="control_prompts"
LOG_FILE="playbook_progress.txt"

if ! gh copilot --help &>/dev/null; then
    echo "ERROR: 'gh copilot' not available."
    exit 1
fi

COPILOT="gh copilot"

get_prompt_info() {
    case $1 in
        1) echo "Generate quality playbook (Phases 1-3)|prompt1_generate_playbook_with_docs.md|gpt-5.4" ;;
        2) echo "Run three-pass code review|prompt2_run_code_review.md|gpt-5.4" ;;
        3) echo "Run functional tests|prompt3_run_functional_tests.md|gpt-5.4" ;;
        4) echo "Run integration tests|prompt4_run_integration_tests.md|gpt-5.4" ;;
        5) echo "Spec audit — Auditor 1|prompt5_run_spec_audit_model1.md|gpt-5.4" ;;
        6) echo "Spec audit — Auditor 2|prompt6_run_spec_audit_model2.md|gpt-5.4" ;;
        7) echo "Spec audit — Auditor 3|prompt7_run_spec_audit_model3.md|gpt-5.4" ;;
        8) echo "Triage and summary|prompt8_triage_and_summary.md|gpt-5.4" ;;
        9) echo "Structural-only control review|prompt9_structural_only_review.md|gpt-5.4" ;;
        *) echo "" ;;
    esac
}

START=${1:-1}
END=${2:-9}

echo "=== v1.2.15 Quality Playbook — Gson with docs ===" | tee -a "$LOG_FILE"
echo "Starting at $(date), prompts ${START}-${END}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

for i in $(seq "$START" "$END"); do
    info=$(get_prompt_info "$i")
    if [ -z "$info" ]; then
        echo "SKIP: unknown prompt number $i" | tee -a "$LOG_FILE"
        continue
    fi

    description=$(echo "$info" | cut -d'|' -f1)
    filename=$(echo "$info" | cut -d'|' -f2)
    model=$(echo "$info" | cut -d'|' -f3)
    input_file="${PROMPT_DIR}/${filename}"

    if [ ! -f "$input_file" ]; then
        echo "SKIP: $input_file not found" | tee -a "$LOG_FILE"
        continue
    fi

    echo "$(date '+%H:%M:%S') [${i}/9] ${description} (model: ${model})" | tee -a "$LOG_FILE"

    output_file="${PROMPT_DIR}/${filename%.md}.output.txt"
    $COPILOT -p "Read and execute the instructions in ${input_file}" --model "$model" --yolo 2>&1 | tee "$output_file"

    echo "$(date '+%H:%M:%S') [${i}/9] Completed: ${description}" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
done

echo "=== Execution complete at $(date) ===" | tee -a "$LOG_FILE"
