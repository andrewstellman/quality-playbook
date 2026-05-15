#!/bin/bash
# Set up benchmark repos for the current SKILL.md version.
#
# Default: copies from clean/ (pristine shallow clones) and docs_gathered/<repo>/
# (curated specification documents). This ensures zero contamination from prior runs.
#
# Fallback: if clean/<repo> doesn't exist, falls back to copying from the most
# recent prior version (the old behavior), with a loud warning.
#
# Usage:
#   ./setup_repos.sh              # All known repos
#   ./setup_repos.sh chi httpx    # Specific repos
#   ./setup_repos.sh --from-prior chi httpx   # Force old copy-from-latest behavior
#
#   # Override destination (e.g., to set up a single repo into a harness run dir):
#   ./setup_repos.sh --target-folder runs/cross_v1.4.5/casbin/replicate-1/ --replace casbin
#
# Flags:
#   --from-prior          Force copy-from-latest-prior-version fallback path
#   --target-folder PATH  Override destination from default repos/<repo>-<version>/.
#                         Requires exactly one positional repo argument. If PATH
#                         already exists, --replace must also be given.
#   --replace             Destructive: rm -rf an existing destination instead of
#                         backing it up. Required with --target-folder when the
#                         target path already exists. Without --target-folder
#                         (the common case), the default is now backup-by-default:
#                         existing repos/<repo>-<version>/ is renamed to
#                         repos/<repo>-<version>.bak-<UTC-ts>/ before the fresh
#                         install lands (v1.5.7 fix F-3, preserves prior repo
#                         state including D1 gate-failure dirs).
#
# Prerequisites:
#   ./create_clean_repos.sh       # Populate clean/ (one-time)
#
# Version-pinned source override:
#   QPB_SKILL_DIR=/path/to/version-pinned-qpb ./setup_repos.sh ...
#       (recognized by _benchmark_lib.sh; defaults to the parent of repos/)
#
# After setup, run (defaults: Copilot, gpt-5.4, parallel, single-pass, no seeds):
#   <repo>-<version>/bin/run_playbook.sh            # v1.5.7+ wrapper auto-discovers target
#   <repo>-<version>/bin/run_playbook.sh <other>    # explicit target override
#   python3 ../bin/run_playbook.py chi-1.5.7        # direct script form (v1.5.7+)
#   python3 -m bin.run_playbook chi-1.5.7           # from QPB root (canonical package form)

set -euo pipefail
source "$(dirname "$0")/_benchmark_lib.sh"

ALL_REPOS=(chi cobra express gson httpx javalin serde zod virtio okhttp axum pydantic)
FROM_PRIOR=false
TARGET_FOLDER=""
REPLACE=false

# Parse flags
POSITIONAL=()
while [ $# -gt 0 ]; do
    case "$1" in
        --from-prior)    FROM_PRIOR=true ;;
        --target-folder) TARGET_FOLDER="$2"; shift ;;
        --replace)       REPLACE=true ;;
        *)               POSITIONAL+=("$1") ;;
    esac
    shift
done

# --target-folder requires exactly one repo argument (so we know which clean/<short>
# and docs_gathered/<short> to source from). Without --target-folder, the script
# falls back to the conventional repos/<repo>-<version>/ destination per repo.
if [ -n "$TARGET_FOLDER" ] && [ ${#POSITIONAL[@]} -ne 1 ]; then
    echo "ERROR: --target-folder requires exactly one positional repo argument" >&2
    echo "Usage:  ./setup_repos.sh --target-folder PATH [--replace] <repo>" >&2
    exit 2
fi

if [ ${#POSITIONAL[@]} -gt 0 ]; then
    REPOS=("${POSITIONAL[@]}")
else
    REPOS=("${ALL_REPOS[@]}")
fi

VERSION=$(detect_skill_version)
[ -z "$VERSION" ] && echo "ERROR: Can't detect version from SKILL.md" && exit 1

CLEAN_DIR="${SCRIPT_DIR}/clean"
DOCS_DIR="${SCRIPT_DIR}/docs_gathered"

echo "=== Quality Playbook — Repo Setup ==="
echo "Version: ${VERSION}"
echo "Source:  $([ "$FROM_PRIOR" = true ] && echo "prior version (--from-prior)" || echo "clean/")"
echo "Repos:   ${REPOS[*]}"
echo ""

# Helper: extract numeric version from a directory name like "httpx-1.3.21"
extract_version() {
    local dirname
    dirname=$(basename "$1")
    echo "$dirname" | sed -E 's/^[^-]+-//'
}

# Helper: compare two version strings numerically.
version_ge() {
    local higher
    higher=$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)
    [ "$higher" = "$1" ]
}

# Find the best prior version directory for fallback
find_prior_version() {
    local short="$1" dst="$2"
    local src="" src_version=""
    for candidate in "${SCRIPT_DIR}/${short}"-[0-9]*; do
        [ -d "$candidate" ] || continue
        [ "$candidate" = "$dst" ] && continue
        local cand_ver
        cand_ver=$(extract_version "$candidate")
        if [ -z "$src_version" ] || version_ge "$cand_ver" "$src_version"; then
            src="$candidate"
            src_version="$cand_ver"
        fi
    done
    echo "$src"
}

for short in "${REPOS[@]}"; do
    if [ -n "$TARGET_FOLDER" ]; then
        # Resolve to absolute path so subsequent operations are unambiguous.
        # Strip any trailing slash for clean dirname/basename behavior.
        case "$TARGET_FOLDER" in
            /*) dst="${TARGET_FOLDER%/}" ;;
            *)  dst="${PWD}/${TARGET_FOLDER%/}" ;;
        esac
        if [ -d "$dst" ]; then
            if [ "$REPLACE" != true ]; then
                echo "ERROR: target folder already exists: $dst" >&2
                echo "Pass --replace to overwrite." >&2
                exit 3
            fi
            log "EXISTS (--replace): removing ${dst}"
            rm -rf "$dst"
        fi
        # Make sure the parent exists (for paths like runs/cross_v1.4.5/casbin/replicate-1
        # where the harness's runs/ tree hasn't been pre-created for this cell).
        mkdir -p "$(dirname "$dst")"
    else
        dst="${SCRIPT_DIR}/${short}-${VERSION}"
        if [ -d "$dst" ]; then
            if [ "$REPLACE" = true ]; then
                log "EXISTS: removing ${dst} (--replace opted in)"
                rm -rf "$dst"
            else
                # v1.5.7 fix F-3: backup-by-default. Rename existing dst
                # to a timestamped .bak-* sibling so any preserved D1
                # gate-failure dirs (quality.gate-failed-<ts>/) survive a
                # subsequent setup. Operators who genuinely want the
                # destructive prior behavior can pass --replace.
                backup_dir="${dst}.bak-$(date -u +%Y%m%dT%H%M%SZ)"
                log "EXISTS: backing up ${dst} → $(basename "$backup_dir")/ (pass --replace to opt into destruction)"
                mv "$dst" "$backup_dir"
            fi
        fi
    fi

    if [ "$FROM_PRIOR" = false ] && [ -d "${CLEAN_DIR}/${short}" ]; then
        # --- Clean source (preferred) ---
        log "Copying clean/${short} → $(basename "$dst")"
        cp -a "${CLEAN_DIR}/${short}" "$dst"

        # Copy docs_gathered from centralized store
        if [ -d "${DOCS_DIR}/${short}" ] && [ -n "$(ls -A "${DOCS_DIR}/${short}" 2>/dev/null)" ]; then
            mkdir -p "${dst}/docs_gathered"
            cp -a "${DOCS_DIR}/${short}/"* "${dst}/docs_gathered/"
            doc_count=$(ls -1 "${dst}/docs_gathered" | wc -l | tr -d ' ')
            doc_size=$(du -sh "${dst}/docs_gathered" | cut -f1)
            log "  docs_gathered: ${doc_count} files (${doc_size})"
        else
            echo ""
            echo "  *** WARNING: No docs_gathered found for ${short} ***"
            echo "  Expected: ${DOCS_DIR}/${short}/"
            echo "  The playbook will run without gathered documentation,"
            echo "  which significantly reduces artifact quality."
            echo ""
        fi
    else
        # --- Fallback: copy from prior version ---
        if [ "$FROM_PRIOR" = false ]; then
            echo ""
            echo "  *** WARNING: clean/${short} not found — falling back to prior version ***"
            echo "  Run ./create_clean_repos.sh ${short} to create a pristine clone."
            echo ""
        fi

        src=$(find_prior_version "$short" "$dst")
        if [ -z "$src" ]; then
            log "SKIP: ${short} — no clean/ directory and no prior version to copy from"
            continue
        fi

        log "Copying $(basename "$src") → $(basename "$dst") (from prior version)"
        cp -a "$src" "$dst"

        # Clean stale artifacts from prior run
        rm -rf "${dst}/quality" "${dst}/control_prompts" "${dst}/previous_runs"
        rm -f "${dst}/playbook_progress.txt"
        rm -f "${dst}/AGENTS.md"  # Generated by the skill, not part of source

        if [ -d "${dst}/docs_gathered" ] && [ -n "$(ls -A "${dst}/docs_gathered" 2>/dev/null)" ]; then
            doc_count=$(ls -1 "${dst}/docs_gathered" | wc -l | tr -d ' ')
            doc_size=$(du -sh "${dst}/docs_gathered" | cut -f1)
            log "  docs_gathered: ${doc_count} files (${doc_size}) (carried from prior)"
        else
            echo "  *** WARNING: docs_gathered/ is missing or empty ***"
        fi
    fi

    # Install skill files
    mkdir -p "${dst}/.github/skills/references"
    cp "${QPB_DIR}/SKILL.md" "${dst}/.github/skills/SKILL.md"
    cp "${QPB_DIR}/references/"* "${dst}/.github/skills/references/" 2>/dev/null || true
    cp "${QPB_DIR}/LICENSE.txt" "${dst}/.github/skills/LICENSE.txt" 2>/dev/null || true
    cp "${QPB_DIR}/.github/skills/quality_gate/quality_gate.py" "${dst}/.github/skills/quality_gate.py" 2>/dev/null || true
    cp "${QPB_DIR}/AGENTS.md" "${dst}/AGENTS.md" 2>/dev/null || true
    mkdir -p "${dst}/bin"
    cp "${QPB_DIR}/bin/install_skill.py" "${dst}/bin/install_skill.py" 2>/dev/null || true
    # v1.5.6 BUG-005: bundle bin/citation_verifier.py so the installed
    # quality_gate.py can run the v1.5.1 byte-equality citation check
    # instead of silently falling back to the WARN path. Pre-fix the
    # gate's soft-import resolved only against the QPB source clone,
    # leaving harness-installed copies effectively without Layer-1
    # protection.
    cp "${QPB_DIR}/bin/citation_verifier.py" "${dst}/bin/citation_verifier.py" 2>/dev/null || true
    # v1.5.7 instruction 049 A-6: bundle bin/reference_docs_ingest.py so
    # Phase 1's mandatory ingest step (python3 -m bin.reference_docs_ingest .)
    # resolves. Without this, codex CLI runs against setup_repos.sh-installed
    # targets fail at Phase 1 with "No module named bin.reference_docs_ingest"
    # (codex correctly stops per the skill's stop-on-install-defect protocol;
    # Phase 2 gate then aborts on missing EXPLORATION.md). This was the
    # root cause of the May 14/15 codex CLI virtio Phase-1 failures.
    cp "${QPB_DIR}/bin/reference_docs_ingest.py" "${dst}/bin/reference_docs_ingest.py" 2>/dev/null || true
    # reference_docs_ingest.py imports `from bin import benchmark_lib`
    # at module load (version detection); benchmark_lib is stdlib-only
    # (no internal bin/ deps) so the closure is exactly these two.
    cp "${QPB_DIR}/bin/benchmark_lib.py" "${dst}/bin/benchmark_lib.py" 2>/dev/null || true
    # v1.5.7 fix F-5b: install the runner wrapper so adopters can
    # invoke `<repo>-<version>/bin/run_playbook.sh` from anywhere and
    # have it auto-discover the QPB clone via walk-up from its own
    # location (with $QPB_HOME as a fallback). The wrapper invokes
    # `python3 -m bin.run_playbook` against this repo as the target.
    if [ -f "${SCRIPT_DIR}/bin/run_playbook.sh" ]; then
        cp "${SCRIPT_DIR}/bin/run_playbook.sh" "${dst}/bin/run_playbook.sh"
        chmod +x "${dst}/bin/run_playbook.sh"
        log "  ✓ Installed runner wrapper at $(basename "$dst")/bin/run_playbook.sh"
    fi
    mkdir -p "${dst}/ai_context"
    cp "${QPB_DIR}/ai_context/AI_ORCHESTRATION_PATTERNS.md" "${dst}/ai_context/AI_ORCHESTRATION_PATTERNS.md" 2>/dev/null || true

    # v1.5.2+: reference_docs/ is the canonical documentation location read
    # by Phase 1's reference_docs_ingest. The legacy docs_gathered/ path
    # populated above is preserved for backward compat with pre-v1.5.2 QPB
    # versions (cross-version benchmark harness still runs older versions).
    #
    # Mirror docs_gathered/ → reference_docs/ so the v1.5.2+ playbook actually
    # finds and ingests the curated documentation. Without this mirror, the
    # gathered docs sit in docs_gathered/ where the modern playbook doesn't
    # look, and Phase 1 falls back to Tier 3 (source-only) review.
    #
    # Adopters can also drop their own plaintext into reference_docs/ (Tier 4)
    # or reference_docs/cite/ (Tier 1/2 citable) — the cp below preserves any
    # such adopter-supplied files because cp -R OVER an existing directory
    # only overwrites same-named files, not the whole tree.
    mkdir -p "${dst}/reference_docs/cite"
    if [ -d "${dst}/docs_gathered" ] && [ -n "$(ls -A "${dst}/docs_gathered" 2>/dev/null)" ]; then
        cp -R "${dst}/docs_gathered/." "${dst}/reference_docs/"
        ref_count=$(find "${dst}/reference_docs" -type f | wc -l | tr -d ' ')
        log "  reference_docs: ${ref_count} files (mirrored from docs_gathered/)"
    fi

    log "  ✓ ${short}-${VERSION} ready"
    echo ""
done

echo "=== Setup complete. Next: $(echo "${REPOS[0]}-${VERSION}")/bin/run_playbook.sh ==="
