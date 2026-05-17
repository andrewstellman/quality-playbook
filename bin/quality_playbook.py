"""quality_playbook — operator-facing entry point for Quality Playbook subcommands.

Usage:

    python -m bin.quality_playbook <subcommand> [options]

Subcommands:

    archive [--status=success|failed|partial] [--timestamp=<ts>] [<repo>]
        Archive the live quality/ tree into quality/previous_runs/<ts>[-SUFFIX]/.
        Dispatches to bin.archive_lib.main. Used operator-side to preserve
        a failed or partial run before the next run's overwrite; the
        orchestrator auto-invokes the success path at end of Phase 6.

Design: this shim exists so the install-blocks in README.md, AGENTS.md,
and agents/quality-playbook.agent.md can document a single
`quality_playbook <subcommand>` command line rather than dispatching
adopters to module-specific `python -m bin.<module>` invocations. New
subcommands (e.g., `migrate`, `gate`) can be added here without
touching the install prose.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# v1.5.7 instruction 077 (addendum §5.2 W3 entry-point audit): put the
# QPB clone root on sys.path BEFORE the sibling-module imports below.
# Without this, `python <clone>/bin/quality_playbook.py …` from a
# foreign cwd reached the `except ImportError: import
# migrate_v1_5_0_layout` flat fallback, but migrate_v1_5_0_layout's
# own top-level `from bin import archive_lib` then failed with
# ModuleNotFoundError: No module named 'bin' (observed exit 1 at the
# instruction-077 baseline). No-op under `python -m bin.quality_playbook`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from . import archive_lib
    from . import council_semantic_check
    from . import migrate_v1_5_0_layout
except ImportError:  # running as a script from the repo root
    import archive_lib
    import council_semantic_check
    import migrate_v1_5_0_layout


_SUBCOMMANDS = {
    "archive": {
        "module": archive_lib,
        "help": "Archive the live quality/ tree. See `archive --help`.",
    },
    "migrate": {
        "module": migrate_v1_5_0_layout,
        "help": (
            "Idempotently migrate a pre-v1.5.1 repo into the consolidated "
            "quality/ layout. See `migrate --help`."
        ),
    },
    "semantic-check": {
        "module": council_semantic_check,
        "help": (
            "Assemble citation_semantic_check.json from captured Council "
            "member JSON responses. See `semantic-check --help`."
        ),
    },
}


def _usage() -> str:
    lines = ["quality_playbook <subcommand> [options]", "", "Subcommands:"]
    for name, spec in _SUBCOMMANDS.items():
        lines.append(f"  {name:<10} {spec['help']}")
    lines.append("")
    lines.append("Run `quality_playbook <subcommand> --help` for per-subcommand options.")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(_usage())
        return 0 if argv else 1

    subcommand, *rest = argv
    spec = _SUBCOMMANDS.get(subcommand)
    if spec is None:
        print(f"quality_playbook: unknown subcommand {subcommand!r}", file=sys.stderr)
        print("", file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 1
    return spec["module"].main(rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
