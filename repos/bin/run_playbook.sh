#!/bin/bash
# QPB v1.5.7 wrapper script. Auto-installed into <target>/bin/ by
# setup_repos.sh as part of fix F-5b (runner three-mode accessibility).
#
# Invokes the QPB runner against this repo as the target. Three invocation
# forms are supported by the runner:
#
#   1. python3 -m bin.run_playbook <target>          (from QPB root)
#   2. python3 /path/to/QPB/bin/run_playbook.py <target>  (direct script)
#   3. <target>/bin/run_playbook.sh                  (this wrapper, target inferred)
#   3'. <target>/bin/run_playbook.sh <other-target>  (this wrapper, explicit target)
#
# The wrapper auto-discovers the QPB clone by walking up from its own
# location looking for bin/run_playbook.py + references/exploration_patterns.md.
# Falls back to $QPB_HOME if walk-up fails.

set -euo pipefail

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
SELF_DIR="$(dirname "$SELF")"
TARGET="$(dirname "$SELF_DIR")"

find_qpb_home() {
    local dir
    dir="$(dirname "$SELF_DIR")"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/bin/run_playbook.py" && -f "$dir/references/exploration_patterns.md" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    if [[ -n "${QPB_HOME:-}" && -f "$QPB_HOME/bin/run_playbook.py" ]]; then
        echo "$QPB_HOME"
        return 0
    fi
    return 1
}

QPB_HOME_RESOLVED="$(find_qpb_home)" || {
    echo "ERROR: cannot locate QPB clone." >&2
    echo "  Walked up from $SELF_DIR looking for bin/run_playbook.py + references/." >&2
    echo "  \$QPB_HOME is unset or invalid." >&2
    echo "  Set QPB_HOME=<path-to-quality-playbook-clone> and retry," >&2
    echo "  or invoke the runner directly:" >&2
    echo "    python3 -m bin.run_playbook <target>   (from a QPB checkout)" >&2
    echo "    python3 /path/to/QPB/bin/run_playbook.py <target>   (script form)" >&2
    exit 1
}

# Run the runner from QPB root so `python3 -m bin.run_playbook` resolves.
# Pass through explicit target arg if given; otherwise default to the
# inferred TARGET (the repo this wrapper was installed into). Uses
# `cd && exec` rather than `env -C` for POSIX portability (BSD env
# lacks -C).
cd "$QPB_HOME_RESOLVED"
if [[ $# -gt 0 ]]; then
    exec python3 -m bin.run_playbook "$@"
else
    exec python3 -m bin.run_playbook "$TARGET"
fi
