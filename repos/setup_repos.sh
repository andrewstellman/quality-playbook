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
# After setup, run from the QPB clone root (defaults: Copilot,
# gpt-5.4, parallel, single-pass, no seeds):
#   python3 -m bin.run_playbook repos/chi-1.5.7          # canonical package form
#   python3 bin/run_playbook.py repos/chi-1.5.7          # equivalent script form

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
    # v1.5.7 instruction 050 A-7: bundle phase_prompts/ and agents/.
    # install_skill.py._bundle_files() already bundles these (lines
    # ~105-126); setup_repos.sh diverged when v1.5.6 added them
    # (phase_prompts BUG-001, agents cluster A). Without them a Mode A
    # agent reading the installed SKILL.md cannot resolve
    # phase_prompts/phaseN.md or the canonical agent file and produces
    # a 0-line EXPLORATION.md at Phase 1 (the post-049 codex UI virtio
    # symptom). Destination matches the setup_repos.sh .github/skills/
    # flat layout (same as SKILL.md line 216 + references/ line 217);
    # SKILL.md:72 resolves phase_prompts via the same fallback list as
    # references/, so .github/skills/phase_prompts/ is correct.
    # TODO(v1.5.7.x): consolidate this + the bin/ cp block below with
    # install_skill.py._bundle_files() so the two install lanes share
    # one bundle source of truth (instruction 050 chose the additive
    # option to keep this ship-blocker fix low-risk).
    mkdir -p "${dst}/.github/skills/phase_prompts"
    cp "${QPB_DIR}/phase_prompts/"*.md "${dst}/.github/skills/phase_prompts/" 2>/dev/null || true
    mkdir -p "${dst}/.github/skills/agents"
    cp "${QPB_DIR}/agents/"*.md "${dst}/.github/skills/agents/" 2>/dev/null || true
    cp "${QPB_DIR}/.github/skills/quality_gate/quality_gate.py" "${dst}/.github/skills/quality_gate.py" 2>/dev/null || true
    # v1.5.7 089n (#183 "B-9"): no longer copy LICENSE.txt or the
    # QPB-root AGENTS.md to the target. install_skill.py::_bundle_files()
    # ships neither — those copies were adopter-parity drift. The
    # from-prior fallback path at :203 already `rm -f`s AGENTS.md
    # with the comment "Generated by the skill, not part of source"
    # (B-17 generation flow at bin/run_playbook.py:3900-3916); the
    # clean-source path now agrees. LICENSE is cosmetic and not
    # referenced by any harness reader.
    mkdir -p "${dst}/bin"
    # v1.5.7 089n: install_skill.py copy is KEPT (NOT a parity match
    # with _bundle_files, which does not bundle install_skill.py
    # itself). Benchmark-harness need: a Mode-A benchmark agent must
    # be able to run the documented install step (A-18 mandate)
    # against the target. See README "How to install the Quality
    # Playbook" + AGENTS.md install procedure. Keep with this
    # justifying comment so a future reader doesn't mistake it for
    # drift.
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
    # v1.5.7 instruction 050 A-6.2: bundle the quality_playbook
    # closure so a Mode-A run hitting Phase 4's `python3 -m
    # bin.quality_playbook semantic-check ...` (phase_prompts/phase4.md
    # :26,43) resolves at target/bin/. install_skill.py._bundle_files()
    # bundles the SAME closure (canonical source of truth); this is
    # the additive mirror for the setup_repos.sh lane.
    # TODO(v1.5.7.x): consolidate — emit this list from
    # install_skill._bundle_files() so both install lanes share one
    # bundle source (instruction 050 chose additive cp to keep this
    # ship-blocker low-risk; the duplication is intentional + tracked).
    # __init__.py is required for the `from .` package syntax to
    # resolve at target/bin/.
    cp "${QPB_DIR}/bin/__init__.py" "${dst}/bin/__init__.py" 2>/dev/null || true
    # v1.5.7 089x: _purpose.py is the shared purpose-banner +
    # version-reader + attribution-banner helper that bundled bin/
    # modules import (lazily, with a file-path fallback). Required
    # at adopter targets so no-args invocations of bundled scripts
    # print a real purpose banner.
    cp "${QPB_DIR}/bin/_purpose.py" "${dst}/bin/_purpose.py" 2>/dev/null || true
    cp "${QPB_DIR}/bin/quality_playbook.py" "${dst}/bin/quality_playbook.py" 2>/dev/null || true
    cp "${QPB_DIR}/bin/archive_lib.py" "${dst}/bin/archive_lib.py" 2>/dev/null || true
    cp "${QPB_DIR}/bin/council_semantic_check.py" "${dst}/bin/council_semantic_check.py" 2>/dev/null || true
    cp "${QPB_DIR}/bin/migrate_v1_5_0_layout.py" "${dst}/bin/migrate_v1_5_0_layout.py" 2>/dev/null || true
    cp "${QPB_DIR}/bin/role_map.py" "${dst}/bin/role_map.py" 2>/dev/null || true
    cp "${QPB_DIR}/bin/council_config.py" "${dst}/bin/council_config.py" 2>/dev/null || true
    # v1.5.7 089n (#183 "B-9"): the A-26 trio (instruction 086).
    # install_skill.py::_bundle_files() ships these three at
    # bin/install_skill.py:220-227; setup_repos.sh diverged when
    # 086 added them and the benchmark was getting away with the
    # gap only because targets sit under the QPB clone and resolve
    # `python3 -m bin.X` against the clone's bin/ (the exact "lax
    # sandbox masks the gap" effect A-26 documents). Closure check
    # per 086: run_state_lib.py + qpb_config.py are stdlib-only;
    # validate_phase_artifacts.py's only internal import is
    # `from bin import role_map` (already copied above). The
    # benchmark bundle now matches the adopter bundle.
    cp "${QPB_DIR}/bin/run_state_lib.py" "${dst}/bin/run_state_lib.py" 2>/dev/null || true
    cp "${QPB_DIR}/bin/validate_phase_artifacts.py" "${dst}/bin/validate_phase_artifacts.py" 2>/dev/null || true
    cp "${QPB_DIR}/bin/qpb_config.py" "${dst}/bin/qpb_config.py" 2>/dev/null || true
    # v1.5.7 090k: ship qpb_validate.py so the benchmark bundle
    # matches the adopter closure (Phase 0 validator now lives at
    # the install root per the openfga-run3 dogfood fix).
    cp "${QPB_DIR}/bin/qpb_validate.py" "${dst}/bin/qpb_validate.py" 2>/dev/null || true
    # v1.5.7 089z: the per-target `bin/run_playbook.sh` wrapper
    # (F-5b + 089n) is removed. The canonical run forms remain
    # and are sufficient: from the QPB clone root,
    # `python3 -m bin.run_playbook repos/<target>` (package
    # form) or `python3 bin/run_playbook.py repos/<target>`
    # (script form). The wrapper was the one entry point in
    # the bin/ tree that still auto-launched on no-args after
    # 089x — removing it keeps the "no-args is safe" invariant
    # whole.
    # v1.5.7 089n (#183 "B-9"): no longer copy ai_context/
    # AI_ORCHESTRATION_PATTERNS.md to the target. install_skill.py
    # does not ship it; no benchmark-harness reader requires it at
    # the target (grep'd bin/ + .github/skills/ + repos/setup_repos.sh
    # — only setup_repos.sh itself referenced it, and historical
    # bootstrap docs that read from the QPB clone). Removed the
    # `mkdir -p "${dst}/ai_context"` along with the cp since no
    # other line writes to that directory.

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

echo "=== Setup complete. Next (from the QPB clone root): python3 -m bin.run_playbook repos/${REPOS[0]}-${VERSION} ==="
