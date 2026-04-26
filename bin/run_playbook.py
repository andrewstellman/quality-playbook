"""Python runner for the Quality Playbook.

Invoke with one or more target-directory paths (relative or absolute) or with
no positional args to run against the current working directory. The runner
does not resolve short names against a benchmark folder — every positional
argument is treated literally as a directory path.
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

try:
    from . import benchmark_lib as lib
    from . import archive_lib
    from . import progress_monitor
except ImportError:
    import benchmark_lib as lib
    import archive_lib
    import progress_monitor


ALL_STRATEGIES = ["gap", "unfiltered", "parity", "adversarial"]
VALID_STRATEGIES = frozenset(ALL_STRATEGIES)
PID_FILE = lib.QPB_DIR / ".run_pids"


def parse_strategy_list(value: str) -> List[str]:
    """Parse --strategy value into an ordered list of concrete strategies.

    Accepts a single strategy name, a comma-separated list of names, or the
    shorthand ``all`` (expands to the full canonical order). Rules:

    - Every item must be one of ``gap``, ``unfiltered``, ``parity``, ``adversarial``.
    - ``all`` is only valid as a bare value; it may not appear inside a list.
    - Duplicates (e.g. ``gap,gap``) are rejected.
    - Empty values / whitespace-only tokens are rejected.
    """
    if not value or value.strip() == "":
        raise argparse.ArgumentTypeError("strategy value cannot be empty")

    raw_items = [item.strip() for item in value.split(",")]
    if any(not item for item in raw_items):
        raise argparse.ArgumentTypeError(
            f"strategy value '{value}' contains an empty token"
        )

    if len(raw_items) == 1 and raw_items[0] == "all":
        return list(ALL_STRATEGIES)

    if "all" in raw_items:
        raise argparse.ArgumentTypeError(
            "'all' is only valid as a bare value; it cannot appear inside a "
            "comma-separated strategy list. Use --strategy all to run the full "
            "chain, or list the specific strategies you want."
        )

    seen = set()
    for item in raw_items:
        if item not in VALID_STRATEGIES:
            raise argparse.ArgumentTypeError(
                f"invalid strategy '{item}'. Must be one of: "
                f"{', '.join(ALL_STRATEGIES)}, all"
            )
        if item in seen:
            raise argparse.ArgumentTypeError(
                f"strategy '{item}' appears more than once in '{value}'"
            )
        seen.add(item)

    return raw_items


@dataclass
class GateCheck:
    ok: bool
    messages: List[str]


def _parse_progress_interval(value: str) -> int:
    """Parse the --progress-interval argument. Range 1..60 seconds.

    v1.5.1 Item 2.2 / Impl-Plan Open Question 4: 2s feels responsive;
    1s is busier; 5s feels slow. The upper bound at 60s is a sanity
    cap — polling slower than once a minute isn't a progress monitor.
    """
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            f"--progress-interval must be an integer; got {value!r}"
        )
    if not 1 <= parsed <= 60:
        raise argparse.ArgumentTypeError(
            f"--progress-interval must be between 1 and 60 seconds; got {parsed}"
        )
    return parsed


# v1.5.1 Item 3.1: phase IDs supported by the orchestrator come from the
# one source of truth (phase_label's dict keys — see below). The parser
# derives its valid-phase set from this list so a future phase addition
# (e.g. v1.5.2 Phase 7) only needs to update phase_label().
_VALID_PHASE_IDS = frozenset({"1", "2", "3", "4", "5", "6"})


def _parse_iterations(value: str) -> List[str]:
    """Parse --iterations "strat1,strat2,..." into an ordered list.

    v1.5.1 Item 3.2. Strategies: gap, unfiltered, parity, adversarial.
    Order matters (gap -> unfiltered -> parity -> adversarial is the
    canonical discovery sequence, but operators may pick a subset).
    Rejects unknown strategies, duplicates, empty lists.
    """
    if not value or value.strip() == "":
        raise argparse.ArgumentTypeError("--iterations value cannot be empty")
    raw = [item.strip() for item in value.split(",")]
    if any(not item for item in raw):
        raise argparse.ArgumentTypeError(
            f"--iterations '{value}' contains an empty token"
        )
    seen: set[str] = set()
    for item in raw:
        if item not in VALID_STRATEGIES:
            raise argparse.ArgumentTypeError(
                f"--iterations: unknown strategy '{item}'. Must be one of: "
                f"{', '.join(ALL_STRATEGIES)}"
            )
        if item in seen:
            raise argparse.ArgumentTypeError(
                f"--iterations: strategy '{item}' appears more than once in '{value}'"
            )
        seen.add(item)
    return raw


def _parse_pace_seconds(value: str) -> int:
    """Parse --pace-seconds. Range 0..3600. Default 0."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            f"--pace-seconds must be an integer; got {value!r}"
        )
    if not 0 <= parsed <= 3600:
        raise argparse.ArgumentTypeError(
            f"--pace-seconds must be between 0 and 3600 seconds; got {parsed}"
        )
    return parsed


def _parse_phase_groups(value: str) -> List[List[str]]:
    """Parse a --phase-groups spec into a canonical list-of-lists.

    v1.5.1 Item 3.1. Input form: "N,N+N,N,..." — comma-separated groups,
    each group either a single phase ID or '+'-joined phase IDs.

    Validation (all violations raise argparse.ArgumentTypeError):
      - Empty spec rejected.
      - Empty group ('1,,2') rejected.
      - Empty '+' segment ('1+') rejected.
      - Non-integer tokens ('a', '1,b') rejected.
      - Phase IDs outside _VALID_PHASE_IDS rejected.
      - Duplicate phase IDs across the whole spec rejected.
      - Cross-group descending order rejected (first-phase-in-group key).
      - Within-group phase IDs may be supplied out of order; they are
        sorted before being returned (e.g. '4+3' normalizes to ['3','4']).

    Returns: a list of sorted phase-ID lists, with outer list in
    ascending first-phase order. Example: '1,3+4,6' -> [['1'], ['3','4'], ['6']].
    """
    if value is None:
        raise argparse.ArgumentTypeError("--phase-groups requires a value")
    if not value.strip():
        raise argparse.ArgumentTypeError("--phase-groups value cannot be empty")

    raw_groups = value.split(",")
    if any(not g.strip() for g in raw_groups):
        raise argparse.ArgumentTypeError(
            f"--phase-groups '{value}' contains an empty group "
            "(check for leading/trailing/double commas)"
        )

    parsed_groups: List[List[str]] = []
    seen_phases: set[str] = set()
    for raw in raw_groups:
        group_raw = raw.strip()
        segments = group_raw.split("+")
        if any(not s.strip() for s in segments):
            raise argparse.ArgumentTypeError(
                f"--phase-groups group '{group_raw}' contains an empty "
                "segment (check for trailing '+' or '++')"
            )
        phases_in_group: List[str] = []
        for seg in segments:
            phase = seg.strip()
            try:
                int(phase)
            except ValueError:
                raise argparse.ArgumentTypeError(
                    f"--phase-groups: '{phase}' is not an integer phase ID"
                )
            if phase not in _VALID_PHASE_IDS:
                raise argparse.ArgumentTypeError(
                    f"--phase-groups: phase '{phase}' is out of range; "
                    f"valid IDs are {sorted(_VALID_PHASE_IDS, key=int)}"
                )
            if phase in seen_phases:
                raise argparse.ArgumentTypeError(
                    f"--phase-groups: phase '{phase}' appears more than once "
                    f"in '{value}' (duplicates rejected)"
                )
            seen_phases.add(phase)
            phases_in_group.append(phase)
        phases_in_group.sort(key=int)
        parsed_groups.append(phases_in_group)

    # Cross-group ordering must be strictly ascending on the first-phase key.
    first_phases = [int(group[0]) for group in parsed_groups]
    if first_phases != sorted(first_phases):
        raise argparse.ArgumentTypeError(
            f"--phase-groups '{value}': groups must appear in ascending order "
            "by first phase (e.g. '1,3+4,6' is valid; '3,2' is not)"
        )
    return parsed_groups


def _format_phase_groups(groups: Sequence[Sequence[str]]) -> str:
    """Render a parsed phase-groups structure back into the CLI spec form."""
    return ",".join("+".join(g) for g in groups)


def _phase_groups_from_phase_mode(phase_mode: Optional[str]) -> Optional[List[List[str]]]:
    """Translate legacy --phase / --phase all into canonical phase-groups.

    --phase all       -> [['1'], ['2'], ..., ['6']]  (seven-group full sweep)
    --phase 3,4,5     -> [['3'], ['4'], ['5']]
    --phase 3         -> [['3']]
    --phase (empty)   -> None
    None              -> None
    """
    if not phase_mode:
        return None
    if phase_mode == "all":
        return [[p] for p in sorted(_VALID_PHASE_IDS, key=int)]
    return [[p] for p in phase_mode.split(",") if p]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Quality Playbook against one or more target directories.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parallel_group = parser.add_mutually_exclusive_group()
    parallel_group.add_argument("--parallel", dest="parallel", action="store_true", default=True, help="Run all targets concurrently (default).")
    parallel_group.add_argument("--sequential", dest="parallel", action="store_false", help="Run targets one after another.")

    runner_group = parser.add_mutually_exclusive_group()
    runner_group.add_argument("--claude", dest="runner", action="store_const", const="claude", default="copilot", help="Use claude -p instead of gh copilot.")
    runner_group.add_argument("--copilot", dest="runner", action="store_const", const="copilot", help="Use gh copilot (default).")

    seed_group = parser.add_mutually_exclusive_group()
    seed_group.add_argument("--no-seeds", dest="no_seeds", action="store_true", default=True, help="Skip Phase 0/0b seed injection (default).")
    seed_group.add_argument("--with-seeds", dest="no_seeds", action="store_false", help="Allow Phase 0/0b seed injection from prior or sibling runs.")

    parser.add_argument("--phase", help="Run specific phase(s): 1-6, all, or comma-separated values like 3,4,5.")
    parser.add_argument("--single-pass", dest="phase", action="store_const", const="", help=argparse.SUPPRESS)
    parser.add_argument("--multi-pass", dest="phase", action="store_const", const="all", help=argparse.SUPPRESS)
    # v1.5.1 Item 3.1: --phase-groups is the new canonical phase selector.
    # --phase N / --phase all remain as sugar that expands to phase-groups;
    # cross-flag mutex is enforced in parse_args() below (argparse's native
    # mutually_exclusive_group would reject legitimate --phase-groups +
    # --next-iteration combinations, so the check lives there instead).
    parser.add_argument(
        "--phase-groups",
        dest="phase_groups_raw",
        type=_parse_phase_groups,
        help=(
            "Phase grouping spec: comma-separated groups, each group 'N' or "
            "'N+N+...'. Example: '1,2,3+4,5+6' runs 4 prompts — phases 3 and "
            "4 share one prompt, phases 5 and 6 share another. Phase IDs "
            "must be 1-6, groups ascending, no duplicates."
        ),
    )
    parser.add_argument("--next-iteration", action="store_true", help="Iterate on an existing quality/ run.")
    parser.add_argument(
        "--full-run",
        action="store_true",
        help="Fresh main run followed by all four iteration strategies sequentially (gap -> unfiltered -> parity -> adversarial).",
    )
    parser.add_argument(
        "--strategy",
        default=["gap"],
        type=parse_strategy_list,
        help=(
            "Iteration strategy (or ordered list) to use with --next-iteration. "
            "Single: 'gap' | 'unfiltered' | 'parity' | 'adversarial'. "
            "Shorthand: 'all' (= gap,unfiltered,parity,adversarial). "
            "Custom list: comma-separated subset, in the order you want, e.g. "
            "'unfiltered,parity,adversarial'. "
            "Lists reject duplicates and do not accept 'all' as a member."
        ),
    )
    # v1.5.1 Item 3.2: unified --phase-groups + iterations invocation.
    # --iterations supersedes the --next-iteration + --strategy pair for
    # the unified path; the old flags remain for single-strategy use.
    parser.add_argument(
        "--iterations",
        dest="iterations",
        type=_parse_iterations,
        help=(
            "Iteration strategies to run after phase groups complete. "
            "Comma-separated; order matters. Strategies: gap, unfiltered, "
            "parity, adversarial. Can be combined with --phase-groups for "
            "a single unified invocation (e.g. --phase-groups '1,2,3+4' "
            "--iterations 'gap,unfiltered')."
        ),
    )
    parser.add_argument(
        "--pace-seconds",
        dest="pace_seconds",
        type=_parse_pace_seconds,
        default=0,
        metavar="N",
        help=(
            "Seconds of idle sleep between consecutive phase groups and "
            "between consecutive iteration strategies (0 <= N <= 3600, "
            "default 0). Use to throttle against per-minute rate limits."
        ),
    )
    parser.add_argument("--model", help="Runner model override (copilot: gpt-5.4, claude: sonnet/opus/etc).")
    parser.add_argument(
        "--no-formal-docs",
        dest="no_formal_docs",
        action="store_true",
        help=(
            "Suppress the pre-run warning when reference_docs/ is missing or empty. "
            "Use for self-audit bootstrap and minimal-repo cases that legitimately "
            "have no reference documentation. (Flag name preserved for backwards "
            "compatibility with v1.5.1 wrappers.)"
        ),
    )
    parser.add_argument(
        "--no-stdout-echo",
        dest="no_stdout_echo",
        action="store_true",
        help=(
            "Suppress stdout echo of logboth() output. The built-in run log "
            "is still written in full. Intended for AI-sandbox invocations "
            "that want silent stdout; the v1.5.1 isatty() gate that used "
            "to hide tee'd output is gone — this thread is the explicit "
            "opt-out (v1.5.1 Item 2.1, Risk Register row 1)."
        ),
    )
    # v1.5.1 Item 2.2: live progress monitor flags. --verbose and --quiet
    # are mutually exclusive; --progress-interval has a small 1..60 range.
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help=(
            "Stream the current phase's transcript to stdout in addition to "
            "PROGRESS.md headers. Useful for watching the run without "
            "opening a second terminal."
        ),
    )
    verbosity.add_argument(
        "--quiet",
        dest="quiet",
        action="store_true",
        help=(
            "Suppress both the PROGRESS.md header monitor and the --verbose "
            "transcript tail. Phase-boundary announcements and errors still "
            "print. The run log file is written in full regardless."
        ),
    )
    parser.add_argument(
        "--progress-interval",
        dest="progress_interval",
        type=_parse_progress_interval,
        default=2,
        metavar="N",
        help=(
            "Seconds between PROGRESS.md polls (1 <= N <= 60, default 2). "
            "Lower values are more responsive but produce more stat() calls; "
            "higher values feel slower."
        ),
    )
    parser.add_argument("--kill", action="store_true", help="Kill processes from the current or last parallel run.")
    parser.add_argument(
        "targets",
        nargs="*",
        help="Target directories to run against (relative or absolute paths). Defaults to the current directory.",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def _mark_iterations_explicit(argv: Sequence[str]) -> bool:
    """True only when --iterations (or its alias --strategy) appeared in argv directly.

    --full-run expansion sets this False; explicit lists set it True. When this
    flag is True, the strategy dispatcher must NOT apply the zero-gain
    early-stop — the user asked for every strategy in their list to run.
    """
    # The explicit_prefixes tuple is hardcoded by intent. v1.5.2 C13.10
    # Finding F was a false-negative caused by a set-intersection check
    # that missed the argparse `--flag=value` combined-token form. The
    # current implementation matches only the two flags below, in both
    # split (`--strategy adversarial`) and combined (`--strategy=adversarial`)
    # forms. If a NEW flag is added that should also force explicit-iteration
    # mode, append it to this tuple and add coverage in
    # `bin/tests/test_iterations_explicit.py` for both shapes plus the
    # `--full-run` override case. Do NOT generalize this to a substring
    # match against argparse internals — that path reintroduces the
    # false-positive class on tokens like `--strategy-foo` (a hypothetical
    # future flag whose name shares the prefix but should NOT trigger).
    explicit_prefixes = ("--iterations", "--strategy")
    has_explicit = any(
        t == prefix or t.startswith(prefix + "=")
        for t in argv
        for prefix in explicit_prefixes
    )
    return has_explicit and "--full-run" not in argv


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)

    # v1.5.2 Phase 6: record whether --iterations / --strategy was passed
    # explicitly on the command line. Downstream strategy dispatch checks
    # this to decide whether to honor the zero-gain early-stop.
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    args._iterations_explicit = _mark_iterations_explicit(effective_argv)

    if not args.kill and not args.targets:
        args.targets = ["."]
    if args.worker:
        args.parallel = False

    # v1.5.1 Item 3.1 mutex. --phase-groups vs --phase / --full-run are
    # redundant (--phase and --full-run are sugar). --phase-groups vs
    # --next-iteration is allowed (Item 3.2 relies on this).
    phase_groups_raw = getattr(args, "phase_groups_raw", None)
    if phase_groups_raw is not None and args.phase:
        parser.error(
            "--phase-groups is not compatible with --phase. --phase is sugar "
            "for a single-group spec; pass one or the other."
        )
    if phase_groups_raw is not None and args.full_run:
        parser.error(
            "--phase-groups is not compatible with --full-run. --full-run is "
            "sugar for a fixed phase-groups + iterations plan."
        )

    if args.next_iteration and args.phase:
        parser.error("--next-iteration is not compatible with --phase. Iteration uses a single prompt.")
    if args.full_run and args.next_iteration:
        parser.error("--full-run and --next-iteration are mutually exclusive. --full-run already chains all iterations after the main run.")
    if args.full_run and args.phase:
        parser.error("--full-run is not compatible with --phase. Full-run uses a single-prompt main run followed by all iterations.")
    if args.phase:
        validate_phase_mode(args.phase, parser)
    if not args.next_iteration and not args.full_run and args.strategy != ["gap"]:
        print("WARNING: --strategy is ignored without --next-iteration or --full-run", file=sys.stderr)

    # v1.5.1 Item 3.2 mutex.
    if args.iterations is not None and args.full_run:
        parser.error(
            "--iterations is not compatible with --full-run. --full-run is "
            "sugar for a fixed iterations plan; pass one or the other."
        )
    if args.iterations is not None and args.next_iteration:
        parser.error(
            "--iterations is not compatible with --next-iteration. "
            "--iterations is the multi-strategy successor; use it alone."
        )

    # v1.5.1 Item 3.1: canonicalize phase selection into args.phase_groups.
    # Precedence: explicit --phase-groups > --full-run > --phase > none.
    if phase_groups_raw is not None:
        args.phase_groups = phase_groups_raw
    elif args.full_run:
        args.phase_groups = [[p] for p in sorted(_VALID_PHASE_IDS, key=int)]
    else:
        args.phase_groups = _phase_groups_from_phase_mode(args.phase)

    # v1.5.1 Item 3.2: --full-run sugar also expands to the full iterations
    # list so the unified dispatcher sees a uniform shape. Explicit
    # --iterations wins; absent both, args.iterations stays None.
    if args.iterations is None and args.full_run:
        args.iterations = list(ALL_STRATEGIES)
    return args


def validate_phase_mode(phase_mode: str, parser: argparse.ArgumentParser) -> None:
    if phase_mode == "all":
        return
    for phase in phase_mode.split(","):
        if phase not in {"1", "2", "3", "4", "5", "6"}:
            parser.error(f"Invalid phase '{phase}'. Must be 1-6 or 'all'.")


def phase_list_from_mode(phase_mode: Optional[str]) -> List[str]:
    if not phase_mode:
        return []
    if phase_mode == "all":
        return ["1", "2", "3", "4", "5", "6"]
    return [phase for phase in phase_mode.split(",") if phase]


def _is_bare_name(raw: str) -> bool:
    """True if ``raw`` is eligible for the version-append fallback.

    Bare name = no path separators, no leading ``.`` / ``..`` / ``~``, not
    absolute. Only bare names get the ``<name>-<version>`` retry — anything
    that looks like an explicit path is taken literally.
    """
    if not raw:
        return False
    if raw.startswith(("/", "~", ".")):
        return False
    if "/" in raw or "\\" in raw:
        return False
    # Windows drive letters ("C:..." etc.).
    if len(raw) >= 2 and raw[1] == ":":
        return False
    return True


def resolve_target_dirs(paths: Sequence[str]) -> Tuple[List[Path], List[str], List[str]]:
    """Resolve user-supplied paths into absolute directories.

    Returns (resolved_dirs, warnings, errors). A missing SKILL.md is a warning
    (the directory may still be a valid target); a non-directory path is an
    error and that entry is dropped.

    Version-append fallback: if a bare name (``chi``, ``virtio``) doesn't
    exist as a directory, re-try ``<name>-<skill_version>`` using the
    SKILL.md version at the QPB root. This replaces the short-name lookup
    the retired ``repos/run_playbook.sh`` provided, without bringing back
    the whole benchmark-folder scanning behavior.
    """
    resolved: List[Path] = []
    warnings: List[str] = []
    errors: List[str] = []
    for raw in paths:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        candidate = candidate.resolve()

        if not candidate.is_dir():
            # Only bare names get the version-append retry. Anything path-like
            # is taken literally.
            version = lib.skill_version() if _is_bare_name(raw) else None
            if version:
                versioned_name = f"{raw}-{version}"
                versioned = (Path.cwd() / versioned_name).resolve()
                if versioned.is_dir():
                    print(
                        f"INFO: resolved '{raw}' to '{versioned_name}' (via SKILL.md version)",
                        file=sys.stderr,
                    )
                    candidate = versioned
                else:
                    errors.append(
                        f"ERROR: '{raw}' is not a directory (resolved to {candidate}; "
                        f"also tried '{versioned_name}')"
                    )
                    continue
            else:
                errors.append(f"ERROR: '{raw}' is not a directory (resolved to {candidate})")
                continue

        if lib.find_installed_skill(candidate) is None:
            warnings.append(
                f"WARN: No SKILL.md found for {candidate}. Expected at "
                ".github/skills/SKILL.md, .claude/skills/quality-playbook/SKILL.md, or SKILL.md "
                "at the target root — the playbook may not be installed there."
            )
        resolved.append(candidate)
    return resolved, warnings, errors


def phase_label(phase: str) -> str:
    return {
        "1": "Explore",
        "2": "Generate",
        "3": "Code Review",
        "4": "Spec Audit",
        "5": "Reconciliation",
        "6": "Verification",
    }[phase]


SKILL_FALLBACK_GUIDE = (
    "Read the quality playbook skill using the documented install-location fallback list: "
    "SKILL.md, .claude/skills/quality-playbook/SKILL.md, "
    ".github/skills/SKILL.md, .github/skills/quality-playbook/SKILL.md. "
    "Resolve reference files using the same documented fallback order."
)


def phase1_prompt(no_seeds: bool) -> str:
    seed_instruction = ""
    if no_seeds:
        seed_instruction = "Skip Phase 0 and Phase 0b entirely - do not look for quality/runs/ or sibling versioned directories. This is a clean benchmark run. Start directly at Phase 1."

    return f"""You are a quality engineer. {SKILL_FALLBACK_GUIDE} For this phase read ONLY the sections up through Phase 1 (stop at the \"---\" line before \"Phase 2\"). Also read the reference files (under whichever references/ directory matches the install path you resolved) that are relevant to exploration.

{seed_instruction}

Execute Phase 1: Explore the codebase. The reference_docs/ directory contains gathered documentation - read it to supplement your exploration. Top-level files are Tier 4 context (AI chats, design notes, retrospectives). Files under reference_docs/cite/ are citable sources (project specs, RFCs). If reference_docs/ is missing or empty, proceed with Tier 3 evidence (source tree) alone and note this in EXPLORATION.md.

When Phase 1 is complete, write your full exploration findings to quality/EXPLORATION.md. This file must contain:
- Domain and stack identification
- Architecture map (key modules, entry points, data flow)
- Existing test inventory
- Specification summary (from reference_docs/ and any inline docs)
- Quality risks identified
- Skeleton/dispatch/state-machine analysis (if applicable)
- Testable requirements derived (REQ-NNN format)
- Use cases derived (UC-NN format)

### MANDATORY CARTESIAN UC RULE (Lever 1, v1.5.2)

For every requirement with a `References` field naming ≥2 files (or ≥2 file:line ranges in distinct files), apply the **Cartesian eligibility check** before deciding whether to emit a single umbrella UC or per-site UCs:

**Gate 1 — Path-suffix match.** At least two references must share a path-suffix role: the last segment before the extension, or a matching function-name pattern that appears across the files.
- Example of a match: `virtio_mmio.c`, `virtio_vdpa.c`, `virtio_pci_modern.c` all implement `_finalize_features`. The `_finalize_features` function is the shared role.
- Example of a non-match: `CONFIG_FOO`, `CONFIG_BAR` flags in the same kconfig file — same kind of thing, but not parallel implementations.

**Gate 2 — Function-level similarity.** Each matching reference must cite a line range of similar size (within 2× of the median) and each range must be inside a function body — not a file-header, a kconfig block, or a macro expansion list.

**Decision:**
- **Both gates pass →** emit one UC per site, numbered `UC-N.a`, `UC-N.b`, `UC-N.c`, …  Each per-site UC has its own Actors, Preconditions, Flow, Postconditions. The parent REQ-N remains as the umbrella.
- **Only Gate 1 passes →** keep a single umbrella UC and mark the reference cluster `heterogeneous` in a `<!-- cluster: heterogeneous -->` HTML comment in the UC body. Phase 3 can still override if it finds per-site divergence.
- **Neither gate passes →** single umbrella UC, no special marking.

### Worked example — REQ-010 / VIRTIO_F_RING_RESET (virtio)

Suppose Phase 1 derives:

    ### REQ-010: Virtio transports must honor VIRTIO_F_RING_RESET negotiation
    - References: drivers/virtio/virtio_mmio.c, drivers/virtio/virtio_vdpa.c, drivers/virtio/virtio_pci_modern.c
    - Pattern: whitelist

Applying the Cartesian check:
- Gate 1: all three files contain `_finalize_features` functions — matches.
- Gate 2: each cited range is inside a function body of similar size — matches.

Both gates pass → emit per-site UCs:

    ### UC-10.a: VIRTIO_F_RING_RESET on PCI modern transport
    - Actors: virtio_pci_modern driver, guest kernel
    - Preconditions: device advertises VIRTIO_F_RING_RESET
    - Flow: vp_modern_finalize_features propagates bit through config space …
    - Postconditions: feature_bit reflected in final config

    ### UC-10.b: VIRTIO_F_RING_RESET on MMIO transport
    - Actors: virtio_mmio driver, guest kernel
    - Preconditions: device advertises VIRTIO_F_RING_RESET
    - Flow: vm_finalize_features must mirror PCI modern behavior …
    - Postconditions: feature_bit survives finalize call

    ### UC-10.c: VIRTIO_F_RING_RESET on vDPA transport
    - Actors: virtio_vdpa driver, vdpa device backend
    - Preconditions: device advertises VIRTIO_F_RING_RESET
    - Flow: virtio_vdpa_finalize_features forwards through set_driver_features …
    - Postconditions: feature_bit visible to vdpa backend

### CONFIRMATION CHECKLIST (Cartesian UC rule)

Before completing Phase 1, confirm each item explicitly in EXPLORATION.md under a section titled "Cartesian UC rule confirmation":

1. For every REQ with ≥2 References, I ran Gate 1 (path-suffix match).
2. For every REQ that passed Gate 1, I ran Gate 2 (function-level similarity).
3. Where both gates passed, I emitted per-site UCs (UC-N.a, UC-N.b, …).
4. Where only Gate 1 passed, I marked the cluster `<!-- cluster: heterogeneous -->`.
5. Where neither gate passed, I kept a single umbrella UC without marking.
6. For each REQ with a pattern match in Gate 1, I added `Pattern: whitelist|parity|compensation` to the REQ block.

Also initialize quality/PROGRESS.md with the run metadata and the phase tracker in the EXACT checkbox format below. This format is a hard contract: the Phase 5 gate checks for the substring `- [x] Phase 4` before allowing reconciliation to start, and it only matches the checkbox form. Do NOT substitute a Markdown table, bulleted prose, or any other layout — table-format runs have aborted mid-pipeline because the gate does not see "Complete" in a table cell as equivalent.

Template for the phase tracker section of PROGRESS.md (fill in the Skill version from SKILL.md metadata):

```
# Quality Playbook Progress

Skill version: <vX.Y.Z>
Date: <YYYY-MM-DD>

## Phase tracker

- [x] Phase 1 - Explore
- [ ] Phase 2 - Generate
- [ ] Phase 3 - Code Review
- [ ] Phase 4 - Spec Audit
- [ ] Phase 5 - Reconciliation
- [ ] Phase 6 - Verify
```

As each later phase completes it will flip its own `- [ ]` to `- [x]` — keep the line text (including the phase name after the dash) stable so substring matching in the Phase 5 gate and downstream tooling works.

IMPORTANT: Do NOT proceed to Phase 2. Your only job is exploration and writing findings to disk. Write thorough, detailed findings - the next phase will read EXPLORATION.md to generate artifacts, so everything important must be captured in that file.
"""


def phase2_prompt() -> str:
    return """You are a quality engineer continuing a phase-by-phase quality playbook run. Phase 1 (exploration) is already complete.

Read these files to get context:
1. quality/EXPLORATION.md - your Phase 1 findings (requirements, risks, architecture)
2. quality/PROGRESS.md - run metadata and phase status
3. .github/skills/SKILL.md - read the Phase 2 section (from \"Phase 2: Generate the Quality Playbook\" through the \"Checkpoint: Update PROGRESS.md after artifact generation\" section). Also read the reference files cited in that section.

**Field preservation rule (v1.5.2, Lever 2).** When transcribing REQ hypotheses from EXPLORATION.md into `quality/REQUIREMENTS.md` and `quality/requirements_manifest.json`, every `- Pattern: <value>` field present on the source hypothesis MUST appear on the corresponding REQ in both output files. Pattern values are `whitelist | parity | compensation`. Phase 1's Cartesian UC rule (confirmation checklist item 6) requires Pattern tagging for every REQ where both UC gates match; Phase 2 must not silently drop these tags. If a hypothesis lacks Pattern but you believe it should have one (per-site UCs emitted with `UC-N.a`/`UC-N.b` suffixes, multi-file `References` suggesting a parallel structure), add Pattern during Phase 2 — do not omit the field. The Phase 5 cardinality gate cannot enforce coverage on a REQ it doesn't know is pattern-tagged; silent omission is a documented v1.4.5-regression vector.

Execute Phase 2: Generate all quality artifacts. Use the exploration findings in EXPLORATION.md as your source - do not re-explore the codebase from scratch. Generate:
- quality/QUALITY.md (quality constitution)
- quality/CONTRACTS.md (behavioral contracts)
- quality/REQUIREMENTS.md (with REQ-NNN and UC-NN identifiers from EXPLORATION.md)
- quality/COVERAGE_MATRIX.md
- Functional tests (quality/test_functional.*)
- quality/RUN_CODE_REVIEW.md (code review protocol)
- quality/RUN_INTEGRATION_TESTS.md (integration test protocol)
- quality/RUN_SPEC_AUDIT.md (spec audit protocol)
- quality/RUN_TDD_TESTS.md (TDD verification protocol)
- quality/COMPLETENESS_REPORT.md (baseline, without verdict)
- If dispatch/enumeration contracts exist: quality/mechanical/ with verify.sh and extraction artifacts. Run verify.sh immediately and save receipts.

Update PROGRESS.md: mark Phase 2 complete (use the checkbox format `- [x] Phase 2 - Generate` — do NOT switch to a table), update artifact inventory.

IMPORTANT: Do NOT proceed to Phase 3 (code review). Your job is artifact generation only. The next phase will execute the review protocols you generated.
"""


def phase3_prompt() -> str:
    return """You are a quality engineer continuing a phase-by-phase quality playbook run. Phases 1-2 are complete.

Read these files to get context:
1. quality/PROGRESS.md - run metadata, phase status, artifact inventory
2. quality/EXPLORATION.md - Phase 1 findings (especially the \"Candidate Bugs for Phase 2\" section)
3. quality/REQUIREMENTS.md - derived requirements and use cases
4. quality/CONTRACTS.md - behavioral contracts
5. .github/skills/SKILL.md - read the Phase 3 section (\"Phase 3: Code Review and Regression Tests\"). Also read .github/skills/references/review_protocols.md.

Execute Phase 3: Code Review + Regression Tests.
Run the 3-pass code review per quality/RUN_CODE_REVIEW.md. For every confirmed bug:
- Add to quality/BUGS.md with ### BUG-NNN heading format
- Write a regression test (xfail-marked)
- Generate quality/patches/BUG-NNN-regression-test.patch (MANDATORY for every confirmed bug)
- Generate quality/patches/BUG-NNN-fix.patch (strongly encouraged)
- Write code review reports to quality/code_reviews/
- Update PROGRESS.md BUG tracker

### MANDATORY GRID STEP (Lever 2, v1.5.2) — pattern-tagged REQs only

For every REQ in quality/REQUIREMENTS.md that has a `Pattern:` field (`whitelist`, `parity`, or `compensation`), you MUST produce a compensation grid BEFORE writing any BUG entries for that REQ.

**Step 1. Enumerate the authoritative item set.** Mechanical extraction from source — uapi header, spec section, documented constants. Do NOT invent. Example: for VIRTIO_F_RING_RESET-family, grep `include/uapi/linux/virtio_config.h` for `VIRTIO_F_*` and list the bits the REQ covers.

**Step 2. Enumerate the sites.** From the REQ's per-site UCs (UC-N.a, UC-N.b, …). If the REQ has a single umbrella UC but is pattern-tagged, the grid is 1-dimensional over items.

**Step 3. Produce the grid.** Write `quality/compensation_grid.json` with one entry per REQ:

```json
{
  "schema_version": "1.5.2",
  "reqs": {
    "REQ-010": {
      "pattern": "whitelist",
      "items": ["RING_RESET", "ADMIN_VQ", "NOTIF_CONFIG_DATA", "SR_IOV"],
      "sites": ["PCI", "MMIO", "vDPA"],
      "cells": [
        {"cell_id": "REQ-010/cell-RING_RESET-PCI", "item": "RING_RESET", "site": "PCI", "present": true,  "evidence": "drivers/virtio/virtio_pci_modern.c:XXX-YYY"},
        {"cell_id": "REQ-010/cell-RING_RESET-MMIO", "item": "RING_RESET", "site": "MMIO", "present": false, "evidence": "drivers/virtio/virtio_mmio.c: no match for RING_RESET"}
      ]
    }
  }
}
```

Cell IDs are mechanical: `REQ-<N>/cell-<item>-<site>`. No whitespace, uppercase item/site identifiers where natural.

**Step 4. Apply the BUG-default rule.** For every cell where:
- the item is defined in authoritative source AND
- the item is absent from any shared filter AND
- the item is absent from the site's compensation path

→ the cell DEFAULTS to BUG. Emit one `### BUG-NNN` entry with the cell's file:line citation, spec basis, and expected-vs-actual behavior. Include a `- Covers: [REQ-N/cell-<item>-<site>]` line (see schemas.md §8 for the field contract).

**Step 5. Downgrade to QUESTION requires a structured JSON record.** Append one record per downgraded cell to `quality/compensation_grid_downgrades.json`:

```json
{
  "schema_version": "1.5.2",
  "downgrades": [
    {
      "cell_id": "REQ-010/cell-RING_RESET-MMIO",
      "authority_ref": "include/uapi/linux/virtio_config.h:116",
      "site_citation": "drivers/virtio/virtio_mmio.c:109-131",
      "reason_class": "intentionally-partial",
      "falsifiable_claim": "MMIO does not support RING_RESET because the MMIO transport predates the feature bit and kernel docs at Documentation/virtio/virtio_mmio.rst:42-55 state the transport is frozen at its v1.0 feature set; falsifiable by showing MMIO re-sets bit 40 under any kernel release."
    }
  ]
}
```

- `reason_class` enum: `out-of-scope | deprecated | platform-gated | handled-upstream | intentionally-partial`.
- `authority_ref`, `site_citation`, `falsifiable_claim` are required and non-empty.
- `falsifiable_claim` must state an observable condition that would make the claim wrong.
- Missing any required field, or `reason_class` outside the enum, or zero-length `falsifiable_claim` → cell REVERTS to BUG at Phase 5 gate time. There is no re-prompt loop.

**Step 6. Self-check.** Before finalizing BUGS.md for this REQ, verify that every cell in the grid appears in either:
- some BUG's `- Covers: [...]` list, OR
- a downgrade record in `quality/compensation_grid_downgrades.json`.

Any cell missing from both will fail the Phase 5 cardinality gate. This self-check is advisory in Phase 3; the blocking gate runs in Phase 5.

### Worked example — RING_RESET grid (virtio)

REQ-010 pattern: whitelist. Items: {RING_RESET, ADMIN_VQ, NOTIF_CONFIG_DATA, SR_IOV}. Sites: {PCI, MMIO, vDPA}. Grid: 4 × 3 = 12 cells.

Code inspection reveals PCI implements all four; MMIO implements none of the four (frozen at v1.0 feature set); vDPA implements NOTIF_CONFIG_DATA but not the other three.

Grid (present=T, absent=F):

|                       | PCI | MMIO | vDPA |
|-----------------------|-----|------|------|
| RING_RESET            |  T  |  F   |  F   |
| ADMIN_VQ              |  T  |  F   |  F   |
| NOTIF_CONFIG_DATA     |  T  |  F   |  T   |
| SR_IOV                |  T  |  F   |  F   |

BUG-default applies to every F cell (8 total). Possible consolidation:

### BUG-001: MMIO ignores VIRTIO_F_RING_RESET
- Primary requirement: REQ-010
- Covers: [REQ-010/cell-RING_RESET-MMIO]

### BUG-002: vDPA ignores VIRTIO_F_RING_RESET
- Primary requirement: REQ-010
- Covers: [REQ-010/cell-RING_RESET-vDPA]

### BUG-003: vDPA missing ADMIN_VQ hookup
- Primary requirement: REQ-010
- Covers: [REQ-010/cell-ADMIN_VQ-vDPA]

### BUG-004: MMIO ignores NOTIF_CONFIG_DATA negotiation (common filter gap)
- Primary requirement: REQ-010
- Covers: [REQ-010/cell-NOTIF_CONFIG_DATA-MMIO]

### BUG-005: MMIO + vDPA both miss SR_IOV propagation
- Primary requirement: REQ-010
- Covers: [REQ-010/cell-SR_IOV-MMIO, REQ-010/cell-SR_IOV-vDPA]
- Consolidation rationale: shared fix path in both transports goes through the same feature-bit filter; single patch on the shared helper closes both cells.

If the reviewer concluded MMIO ADMIN_VQ is intentionally out-of-scope because ADMIN_VQ is a PCI-only spec feature, the downgrade record would be:

```json
{
  "cell_id": "REQ-010/cell-ADMIN_VQ-MMIO",
  "authority_ref": "include/uapi/linux/virtio_pci.h:NN",
  "site_citation": "drivers/virtio/virtio_mmio.c: no admin virtqueue implementation",
  "reason_class": "out-of-scope",
  "falsifiable_claim": "ADMIN_VQ is MMIO-scoped — falsifiable by citing any virtio-spec normative text requiring ADMIN_VQ on non-PCI transports."
}
```

Union check: 8 BUG-covered cells + 1 downgrade cell = 9. Grid has 12 cells; 4 present cells don't need coverage. Total: 8 F cells covered via BUGs + 1 via downgrade = all 9 absent cells accounted for. Grid → clean.

### ITERATION mode addendum (MANDATORY INCREMENTAL WRITE, Phase 8)

When running in iteration mode (gap / unfiltered / parity / adversarial), write candidate BUG stubs to disk immediately on identification, not at end-of-review. Path: `quality/code_reviews/<iteration>-candidates.md`. One `### CANDIDATE-NNN` heading per candidate, with at least a file:line citation. Reviewer upgrades candidates to confirmed BUGs in BUGS.md only after full triage.

### CONFIRMATION CHECKLIST (Lever 2, v1.5.2)

Before writing the Phase 3 completion checkpoint to PROGRESS.md, confirm each item explicitly in your Phase 3 summary:

1. For every pattern-tagged REQ, I produced a compensation grid in `quality/compensation_grid.json`.
2. For every grid, I applied the BUG-default rule mechanically.
3. Every BUG emitted for a pattern-tagged REQ has a `- Covers: [...]` field with valid cell IDs.
4. Every BUG whose Covers list has ≥2 entries has a non-empty `- Consolidation rationale: ...` field.
5. For every downgraded cell, I wrote a complete structured record in `quality/compensation_grid_downgrades.json` with all five required fields and a valid `reason_class`.
6. For every pattern-tagged REQ, the union of Covers lists + downgrade cells equals the grid's cell set.

Mark Phase 3 (Code review + regression tests) complete in PROGRESS.md (use the checkbox format `- [x] Phase 3 - Code Review` — do NOT switch to a table).

IMPORTANT: Do NOT proceed to Phase 4 (spec audit). The next phase will run the spec audit with a fresh context window.
"""


def phase4_prompt() -> str:
    return """You are a quality engineer continuing a phase-by-phase quality playbook run. Phases 1-3 are complete.

Read these files to get context:
1. quality/PROGRESS.md - run metadata, phase status, BUG tracker
2. quality/REQUIREMENTS.md - derived requirements
3. quality/BUGS.md - bugs found in Phase 3 (code review)
4. .github/skills/SKILL.md - read the Phase 4 section (\"Phase 4: Spec Audit and Triage\"). Also read .github/skills/references/spec_audit.md.

Execute Phase 4: Spec Audit + Triage + Layer-2 semantic citation check.

Part A — spec audit:
Run the spec audit per quality/RUN_SPEC_AUDIT.md. Produce:
- Individual auditor reports at quality/spec_audits/YYYY-MM-DD-auditor-N.md (one per auditor)
- Triage synthesis at quality/spec_audits/YYYY-MM-DD-triage.md
- Executable triage probes at quality/spec_audits/triage_probes.sh
- Regression tests and patches for any net-new spec audit bugs
- Update BUGS.md and PROGRESS.md BUG tracker with any new findings

Part B — Layer-2 semantic citation check (v1.5.1):
The gate's invariant #17 (schemas.md §10) requires three Council members to
vote on each Tier 1/2 REQ's citation_excerpt. Execute these steps:

1. Generate per-Council-member prompts:
     python3 -m bin.quality_playbook semantic-check plan .
   This writes one or more prompt files to
   quality/council_semantic_check_prompts/<member>.txt per member in the
   Council roster (bin/council_config.py: claude-opus-4.7, gpt-5.4,
   gemini-2.5-pro). For >15 Tier 1/2 REQs, prompts are split into batches
   of 5 (<member>-batch<N>.txt).
   If no Tier 1/2 REQs exist (Spec Gap run), this step writes an empty
   quality/citation_semantic_check.json directly — skip steps 2-4.

2. For each Council member's prompt file, feed the prompt to that model
   (the same roster that ran Part A) and capture its JSON-array response
   to quality/council_semantic_check_responses/<member>.json. If the
   member was batched, concatenate the per-batch responses into a single
   array in the response file. Every entry must have req_id, verdict
   (supports|overreaches|unclear), and reasoning.

3. Assemble the semantic-check output:
     python3 -m bin.quality_playbook semantic-check assemble . \\
       --member claude-opus-4.7 --response quality/council_semantic_check_responses/claude-opus-4.7.json \\
       --member gpt-5.4         --response quality/council_semantic_check_responses/gpt-5.4.json \\
       --member gemini-2.5-pro  --response quality/council_semantic_check_responses/gemini-2.5-pro.json
   This writes quality/citation_semantic_check.json per schemas.md §9.

4. Verify the output file exists. Phase 6's gate invariant #17 requires
   it on every Tier 1/2 run.

Mark Phase 4 (Spec audit + triage + semantic check) complete in PROGRESS.md (use the checkbox format `- [x] Phase 4 - Spec Audit` — the Phase 5 entry gate looks for that exact substring and will abort if it finds a table row or any other layout).

IMPORTANT: Do NOT proceed to Phase 5 (reconciliation). The next phase will handle reconciliation and TDD.
"""


def phase5_prompt() -> str:
    return """You are a quality engineer continuing a phase-by-phase quality playbook run. Phases 1-4 are complete.

Read these files to get context:
1. quality/PROGRESS.md - run metadata, phase status, cumulative BUG tracker
2. quality/BUGS.md - all confirmed bugs from code review and spec audit
3. quality/REQUIREMENTS.md - derived requirements
4. .github/skills/SKILL.md - read the Phase 5 section (\"Phase 5: Post-Review Reconciliation and Closure Verification\"). Also read .github/skills/references/requirements_pipeline.md, .github/skills/references/review_protocols.md, and .github/skills/references/spec_audit.md.

Execute Phase 5: Reconciliation + TDD + Closure.

1. Run the Post-Review Reconciliation per references/requirements_pipeline.md. Update COMPLETENESS_REPORT.md.
2. Run closure verification: every BUG in the tracker must have either a regression test or an explicit exemption.
3. Write bug writeups at quality/writeups/BUG-NNN.md for EVERY confirmed bug. The canonical template is the \"Bug writeup generation\" section of .github/skills/SKILL.md — read that section before writing. Use the exact field headings listed there: **Summary, Spec reference, The code, Observable consequence, Depth judgment, The fix, The test, Related issues**. Sections 1–4, 6, 7 are required in every writeup; section 5 (Depth judgment) fires only when the consequence isn't self-evident from the immediate code; section 8 (Related issues) is included only when related bugs exist. Do NOT introduce fields that aren't in the template (no \"Minimal reproduction\" as a top-level field, no \"Patch path:\" as a top-level field — those belong inside Spec reference and The test respectively).

   **MANDATORY HYDRATION STEP.** Before writing a writeup, re-open quality/BUGS.md and locate the `### BUG-NNN:` entry for the bug you are about to write up. Every confirmed bug in BUGS.md already has the content you need — your job is to copy it into the writeup's sections, not to invent it. If a field is missing from BUGS.md, that is a reconciliation error to surface in PROGRESS.md, not a field to fabricate. Use this field map:

   | BUGS.md field              | Writeup section              | How to use it                                                                 |
   |----------------------------|------------------------------|-------------------------------------------------------------------------------|
   | Title line (### BUG-NNN:…) | Summary                      | One sentence naming the function/code path and the observable failure.        |
   | Primary requirement        | Spec reference               | `- Requirement: REQ-NNN`                                                      |
   | Spec basis                 | Spec reference               | `- Spec basis: <doc path + line range(s), semicolon-separated if multiple>` plus a ≤15-word contract quote copied verbatim from the cited lines. |
   | Location                   | The code                     | Cite `file:line` and describe what the current path does there.               |
   | Minimal reproduction       | Observable consequence       | Weave into the consequence paragraph as the triggering input.                 |
   | Expected + Actual behavior | Observable consequence       | The actual behavior is the observable failure; the expected defines the gap.  |
   | Regression test            | The test                     | `- Regression test: <function name>` — verbatim from BUGS.md.                 |
   | Patches (regression)       | The test                     | `- Regression patch: <path>` — verbatim from BUGS.md.                         |
   | Patches (fix)              | The fix + The test           | If a fix patch file exists, read it and paste the unified diff inside ```diff; also list the patch path as `- Fix patch: <path>` under The test. If no fix patch exists (confirmed-open bug), write the minimal concrete unified diff directly in The fix anyway — SKILL.md requires an inline diff in every writeup. In the no-patch case, omit the `Fix patch:` bullet from The test. |
   | Red/green logs             | The test                     | `- Red receipt: quality/results/BUG-NNN.red.log` and the matching green path. |

   **Worked example.** The BUGS.md entry for BUG-004 is:

       ### BUG-004: naive upstream timestamps crash ETA math
       - Source: Code Review
       - Severity: HIGH
       - Primary requirement: REQ-006
       - Location: bus_tracker.py:138-144
       - Spec basis: quality/REQUIREMENTS.md:163-172; quality/QUALITY.md:57-65
       - Minimal reproduction: Return a visit whose ExpectedArrivalTime is an ISO string
         without timezone information, such as 2026-04-21T12:00:00.
       - Expected behavior: The affected arrival degrades to unknown-time while the rest
         of the stop remains usable.
       - Actual behavior: datetime.fromisoformat() returns a naive datetime and
         subtracting it from datetime.now(timezone.utc) raises TypeError, aborting the
         stop/request path.
       - Regression test: quality.test_regression.TestPhase3Regressions.test_bug_004_fetch_stop_arrivals_degrades_naive_timestamps
       - Patches: quality/patches/BUG-004-regression-test.patch, quality/patches/BUG-004-fix.patch

   The hydrated writeup sections look like this (sketch — paste the real diff from the
   fix patch file into ```diff, don't make one up):

       ## Summary
       fetch_stop_arrivals() crashes the whole stop/request path when an upstream visit
       carries a naive ExpectedArrivalTime, instead of degrading that arrival to
       unknown-time.

       ## Spec reference
       - Requirement: REQ-006
       - Spec basis: quality/REQUIREMENTS.md:163-172; quality/QUALITY.md:57-65
       - Behavioral contract quote: \"degrade a bad per-arrival timestamp to unknown-time instead of aborting the whole response path\"

       ## The code
       At bus_tracker.py:138-144, the parser calls datetime.fromisoformat(...) on
       ExpectedArrivalTime and subtracts the result from datetime.now(timezone.utc)…

       ## Observable consequence
       When the upstream visit returns ExpectedArrivalTime=\"2026-04-21T12:00:00\"
       (no timezone), fromisoformat() returns a naive datetime, the subtraction
       raises TypeError, and the entire stop/request path aborts rather than the
       single affected arrival degrading to unknown-time.

       ## The fix
       ```diff
       <paste the real unified diff from quality/patches/BUG-004-fix.patch here>
       ```

       ## The test
       - Regression test: quality.test_regression.TestPhase3Regressions.test_bug_004_fetch_stop_arrivals_degrades_naive_timestamps
       - Regression patch: quality/patches/BUG-004-regression-test.patch
       - Fix patch: quality/patches/BUG-004-fix.patch
       - Red receipt: quality/results/BUG-004.red.log
       - Green receipt: quality/results/BUG-004.green.log

   **Confirmation checklist (per writeup, before moving to the next bug).** (a) Every
   required section has populated content copied from BUGS.md or the patch files —
   no empty backticks, no sentinel filler like \"is a confirmed code bug in ``\" or
   \"The affected implementation lives at ``\" or \"Patch path: ``\". (b) The ```diff
   fence contains at least one `+` or `-` line from the actual fix patch. (c) The
   Summary names a real function or code path, not the BUG identifier. (d) No
   angle-bracket placeholders (e.g., `<...>`) remain in the final writeup — those are
   pedagogical markers from the worked example and from SKILL.md, never acceptable
   output.
4. Run the TDD red-green cycle: for each confirmed bug, run the regression test against unpatched code -> quality/results/BUG-NNN.red.log. If a fix patch exists, run against patched code -> quality/results/BUG-NNN.green.log. If the test runner is unavailable, create the log with NOT_RUN on the first line.
5. Generate sidecar JSON: quality/results/tdd-results.json and quality/results/integration-results.json (schema_version \"1.1\", canonical fields: id, requirement, red_phase, green_phase, verdict, fix_patch_present, writeup_path).
6. If mechanical verification artifacts exist, run quality/mechanical/verify.sh and save receipts.
7. Run terminal gate verification, write it to PROGRESS.md.

### MANDATORY CARDINALITY GATE (Lever 3, v1.5.2)

Before finalizing this phase, run the cardinality reconciliation gate against the current repo state:

    python3 -c "import sys; sys.path.insert(0, '.github/skills/quality_gate'); import quality_gate; failures = quality_gate.validate_cardinality_gate('.'); sys.exit(1 if failures else 0)"

If the gate reports uncovered cells, malformed cell IDs, missing consolidation rationale on multi-cell Covers, or malformed downgrade records, STOP. Fix the BUGS.md entries or the `compensation_grid_downgrades.json` file. Do NOT proceed to completion until the gate returns clean.

For every pattern-tagged REQ, the Phase 5 contract is:
- Every grid cell with `"present": false` appears in either a BUG's `Covers:` list or a downgrade record.
- Every `Covers:` entry uses the canonical cell ID form `REQ-N/cell-<item>-<site>`.
- Every BUG with ≥2 `Covers:` entries has a non-empty `Consolidation rationale:` line.
- Every downgrade record has `cell_id`, `authority_ref`, `site_citation`, `reason_class` (in the enum), `falsifiable_claim` (non-empty).

The cardinality gate is blocking. It is intentionally stricter than the Phase 3 advisory self-check; the advisory check is meant to surface problems early, but Phase 5 is where they become fatal.

Mark Phase 5 complete in PROGRESS.md (use the checkbox format `- [x] Phase 5 - Reconciliation` — do NOT switch to a table).

IMPORTANT: quality_gate.py will FAIL Phase 5 if any writeup is missing a non-empty ```diff block or contains any of these sentinel phrases verbatim: \"is a confirmed code bug in ``\", \"The affected implementation lives at ``\", \"Patch path: ``\", \"- Regression test: ``\", \"- Regression patch: ``\". Those two checks are the hard gate. Skipping the BUGS.md hydration step above is not gate-enforced but will produce writeups that read as unpopulated stubs and fail a human review — do not skip it.
"""


def phase6_prompt() -> str:
    return """You are a quality engineer doing the verification phase of a quality playbook run. Phases 1-5 are complete.

Read .github/skills/SKILL.md - the Phase 6 section (\"Phase 6: Verify\"). Follow the incremental verification steps (6.1 through 6.5).

Step 6.1: If quality/mechanical/verify.sh exists, run it. Record exit code.
Step 6.2: Run quality_gate.py:
  python3 .github/skills/quality_gate.py .
Read the output carefully. For every FAIL result, fix the issue:
- Missing regression-test patches: generate quality/patches/BUG-NNN-regression-test.patch
- Missing inline diffs in writeups: add a ```diff block
- Non-canonical JSON fields: fix tdd-results.json (use 'id' not 'bug_id', etc.)
- Missing files: create them
After fixing all FAILs, run quality_gate.py again. Repeat until 0 FAIL.
Save final output to quality/results/quality-gate.log.

Step 6.3: Run functional tests if a test runner is available.
Step 6.4: File-by-file verification checklist (read one file at a time, check, move on).
Step 6.5: Metadata consistency check.

Append each step's result to quality/results/phase6-verification.log.
Mark Phase 6 complete in PROGRESS.md (use the checkbox format `- [x] Phase 6 - Verify` — do NOT switch to a table).
"""


def build_phase_prompt(phase: str, no_seeds: bool) -> str:
    return {
        "1": phase1_prompt(no_seeds),
        "2": phase2_prompt(),
        "3": phase3_prompt(),
        "4": phase4_prompt(),
        "5": phase5_prompt(),
        "6": phase6_prompt(),
    }[phase]


def single_pass_prompt(no_seeds: bool) -> str:
    seed_instruction = " Skip Phase 0 and Phase 0b - start directly at Phase 1." if no_seeds else ""
    return f"{SKILL_FALLBACK_GUIDE} Execute the quality playbook for this project.{seed_instruction}"


def iteration_prompt(strategy: str) -> str:
    return (
        f"{SKILL_FALLBACK_GUIDE} Run the next iteration using the {strategy} strategy. "
        "Any updates to quality/PROGRESS.md must keep the existing phase tracker in checkbox "
        "format (`- [x] Phase N - <name>`) — do not rewrite it as a table. The orchestrator "
        "appends `## Iteration: <strategy> started/complete` sections itself; iteration work "
        "should not touch the existing phase tracker lines."
    )


def next_strategy(strategy: str) -> str:
    return {
        "gap": "unfiltered",
        "unfiltered": "parity",
        "parity": "adversarial",
        "adversarial": "",
    }.get(strategy, "gap")


def count_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def check_phase_gate(repo_dir: Path, phase: str) -> GateCheck:
    quality_dir = repo_dir / "quality"
    messages: List[str] = []

    if phase == "1":
        return GateCheck(ok=True, messages=[])
    if phase == "2":
        exploration = quality_dir / "EXPLORATION.md"
        if not exploration.is_file():
            return GateCheck(ok=False, messages=["GATE FAIL Phase 2: quality/EXPLORATION.md missing - run Phase 1 first"])
        line_count = count_lines(exploration)
        if line_count < 120:
            return GateCheck(ok=False, messages=[f"GATE FAIL Phase 2: EXPLORATION.md is only {line_count} lines (expected 120+)"])
        return GateCheck(ok=True, messages=messages)
    if phase == "3":
        required = [
            "REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md", "RUN_CODE_REVIEW.md",
            "COVERAGE_MATRIX.md", "COMPLETENESS_REPORT.md",
            "RUN_INTEGRATION_TESTS.md", "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
        ]
        missing = [name for name in required if not (quality_dir / name).is_file()]
        if missing:
            return GateCheck(ok=False, messages=[f"GATE FAIL Phase 3: missing {' '.join(missing)} - run Phase 2 first"])
        return GateCheck(ok=True, messages=[])
    if phase == "4":
        if not (quality_dir / "REQUIREMENTS.md").is_file():
            return GateCheck(ok=False, messages=["GATE FAIL Phase 4: REQUIREMENTS.md missing - run Phase 2 first"])
        if not (quality_dir / "RUN_SPEC_AUDIT.md").is_file():
            return GateCheck(ok=False, messages=["GATE FAIL Phase 4: RUN_SPEC_AUDIT.md missing - run Phase 2 first"])
        code_reviews = quality_dir / "code_reviews"
        if not code_reviews.is_dir() or not any(code_reviews.iterdir()):
            messages.append("GATE WARN Phase 4: no code_reviews/ - Phase 3 may not have run")
        return GateCheck(ok=True, messages=messages)
    if phase == "5":
        if not (quality_dir / "PROGRESS.md").is_file():
            return GateCheck(ok=False, messages=["GATE FAIL Phase 5: PROGRESS.md missing"])
        sa_dir = quality_dir / "spec_audits"
        if not sa_dir.is_dir():
            return GateCheck(ok=False, messages=["GATE FAIL Phase 5: spec_audits/ missing - run Phase 4 first"])
        triage_files = list(sa_dir.glob("*triage*"))
        if not triage_files:
            return GateCheck(ok=False, messages=["GATE FAIL Phase 5: spec_audits/ has no triage file - complete Phase 4 triage first"])
        auditor_files = list(sa_dir.glob("*auditor*"))
        if not auditor_files:
            return GateCheck(ok=False, messages=["GATE FAIL Phase 5: spec_audits/ has no auditor files - complete Phase 4 audit first"])
        progress_content = (quality_dir / "PROGRESS.md").read_text(encoding="utf-8", errors="replace")
        if "- [x] Phase 4" not in progress_content:
            return GateCheck(ok=False, messages=["GATE FAIL Phase 5: Phase 4 not marked complete in PROGRESS.md"])
        if not (quality_dir / "BUGS.md").is_file():
            messages.append("GATE WARN Phase 5: no BUGS.md - Phase 3 may not have run")
        return GateCheck(ok=True, messages=messages)
    if phase == "6":
        if not (quality_dir / "PROGRESS.md").is_file():
            return GateCheck(ok=False, messages=["GATE FAIL Phase 6: PROGRESS.md missing"])
        return GateCheck(ok=True, messages=[])
    raise ValueError(f"Unknown phase: {phase}")


def command_for_runner(runner: str, prompt: str, model: Optional[str]) -> List[str]:
    if runner == "claude":
        command = ["claude"]
        if model:
            command.extend(["--model", model])
        command.extend(["-p", prompt, "--dangerously-skip-permissions"])
        return command
    copilot_model = model or lib.DEFAULT_MODEL
    return ["gh", "copilot", "-p", prompt, "--model", copilot_model, "--yolo"]


def command_preview(command: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def append_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        return
    with destination.open("a", encoding="utf-8") as out_handle:
        out_handle.write(source.read_text(encoding="utf-8", errors="ignore"))


def log_file_for(repo_dir: Path, timestamp: str) -> Path:
    """Return the log path for a given target directory.

    Logs live next to the target: `{parent}/{name}-playbook-{ts}.log`.
    """
    return repo_dir.parent / f"{repo_dir.name}-playbook-{timestamp}.log"


# v1.5.1 Item 2.1: built-in logging + unbuffered stdout. The prior run
# ceremony required operators to set PYTHONUNBUFFERED=1 and pipe through
# tee; the built-in log + line-buffered stdout make both unnecessary.
_CONFIGURE_LOGGING_PREFIX = "Writing run log to: "


def configure_logging(
    repo_dir: Path,
    timestamp: str,
    *,
    no_stdout_echo: bool = False,
    stream: Optional[object] = None,
) -> Path:
    """Compute the canonical log path, announce it on stdout, and install
    line-buffered stdout. Called exactly once per run entry point.

    Implements v1.5.1 Item 2.1 (docs/design/QPB_v1.5.1_Design.md Item 3).

    - Canonical log path comes from log_file_for(); no path derivation is
      reinvented here. The directory is created on demand so the first
      lib.logboth() call never has to.
    - Prints "Writing run log to: <abs path>" as the very first line of run
      output so operators (and Item 2.3's banner) can key off a stable
      prefix. _CONFIGURE_LOGGING_PREFIX is exposed for tests.
    - Installs line-buffered stdout via sys.stdout.reconfigure(). Python
      3.7+; the project targets 3.10+. Replaces the operator-side
      PYTHONUNBUFFERED=1 / -u ceremony.
    - no_stdout_echo=True flips benchmark_lib.logboth's default echo to
      False for the whole run. The escape hatch for AI-sandbox invocations
      that legitimately want silent stdout (Risk Register row 1).
    - The optional `stream` kwarg lets tests capture the announcement
      without monkey-patching sys.stdout. Production callers leave it at
      None and inherit sys.stdout.
    """
    log_path = log_file_for(repo_dir, timestamp).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    lib.set_default_echo(not no_stdout_echo)

    # reconfigure() is a no-op on streams that don't support it (e.g. an
    # io.StringIO passed by tests); guard it to stay test-friendly.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, io.UnsupportedOperation):
        pass

    target = stream if stream is not None else sys.stdout
    target.write(f"{_CONFIGURE_LOGGING_PREFIX}{log_path}\n")
    try:
        target.flush()
    except (AttributeError, io.UnsupportedOperation):
        pass
    return log_path


# v1.5.1 Item 2.3: cross-platform startup banner. Per design-doc Item 5
# the canonical source for "how do I watch this run from a second
# terminal?" is the banner — documentation refers back to it rather than
# duplicating platform-specific commands. Keystroke mode switching
# (termios/tty/msvcrt) is explicitly deferred; we print static recipes.

_BANNER_RULE = "=" * 72


def _watch_commands_for_platform(
    platform_name: str,
    log_path: Path,
    transcript_path: Path,
    progress_path: Path,
) -> Tuple[List[str], Optional[str]]:
    """Return (recipe lines, optional advisory note) for a given
    platform.system() value. ``platform_name`` is passed in explicitly
    so tests can verify each branch without monkey-patching the
    platform module.

    v1.5.1 Phase 2.3 revision — Darwin is split from Linux. macOS does
    not ship `watch(1)` by default; pasting `watch -n 2 '...'` into
    stock zsh returns `zsh: command not found: watch`. The Darwin
    recipe now uses a portable shell loop (`while true; do clear;
    grep ...; sleep 2; done`) that runs on a fresh macOS install
    without `brew install watch`. Linux keeps the concise `watch`
    form since Linux ships it by default.
    """
    name = (platform_name or "").strip()
    darwin_progress = (
        f"Watch progress:    while true; do clear; "
        f"grep -E '^##?' {progress_path}; sleep 2; done"
    )
    linux_progress = f"Watch progress:    watch -n 2 'grep \"^##\\?\" {progress_path}'"

    if name == "Darwin":
        return (
            [
                f"Watch log:         tail -f {log_path}",
                f"Watch transcript:  tail -f {transcript_path}",
                darwin_progress,
            ],
            None,
        )
    if name == "Linux":
        return (
            [
                f"Watch log:         tail -f {log_path}",
                f"Watch transcript:  tail -f {transcript_path}",
                linux_progress,
            ],
            None,
        )
    if name == "Windows":
        return (
            [
                f"Watch log:         Get-Content -Path {log_path} -Wait -Tail 20",
                f"Watch transcript:  Get-Content -Path {transcript_path} -Wait -Tail 20",
                f"Watch progress:    Get-Content -Path {progress_path} -Wait | Select-String '^##?'",
            ],
            None,
        )
    # Unknown platform: fall back to the Darwin recipe (portable shell
    # loop) rather than the Linux `watch` form, since `watch` is the
    # most-often-missing of the two.
    return (
        [
            f"Watch log:         tail -f {log_path}",
            f"Watch transcript:  tail -f {transcript_path}",
            darwin_progress,
        ],
        (
            f"Non-Darwin/Linux/Windows platform detected ({name or 'unknown'}); "
            "commands may need adjustment."
        ),
    )


def build_startup_banner(
    repo_dir: Path,
    log_path: Path,
    run_plan: Sequence[str],
    *,
    qpb_version: Optional[str] = None,
    platform_name: Optional[str] = None,
) -> str:
    """Assemble the startup-banner string for a run.

    The orchestrator calls this once at run start and feeds the result
    through logboth() so it lands in both stdout and the log file.
    Paths in the banner are absolute so operators can copy-paste them
    into a second terminal without worrying about cwd.

    ``platform_name`` defaults to platform.system(); tests pass an
    explicit value ('Darwin', 'Linux', 'Windows', 'FreeBSD', ...) to
    exercise each branch.
    """
    log_path = log_path.resolve()
    repo_dir = repo_dir.resolve()
    transcript_dir = repo_dir / "quality" / "control_prompts"
    # First phase's transcript is a predictable, copy-paste-ready path.
    # When the run advances, operators update the N in phaseN.output.txt;
    # the banner's job is to give them a working starting point.
    transcript_path = transcript_dir / "phase1.output.txt"
    progress_path = repo_dir / "quality" / "PROGRESS.md"

    if platform_name is None:
        platform_name = platform.system()

    version = qpb_version or lib.detect_skill_version() or "unknown"

    lines = [
        _BANNER_RULE,
        f"QPB v{version} run starting",
        _BANNER_RULE,
        f"Target:            {repo_dir}",
        f"Log file:          {log_path}",
    ]
    recipe_lines, advisory = _watch_commands_for_platform(
        platform_name, log_path, transcript_path, progress_path
    )
    lines.extend(recipe_lines)
    if advisory:
        lines.append(f"  Note: {advisory}")
    lines.append("")
    lines.append("Plan:")
    if run_plan:
        for entry in run_plan:
            lines.append(f"  {entry}")
    else:
        lines.append("  (single-prompt run; no explicit phase list)")
    lines.append(_BANNER_RULE)
    return "\n".join(lines)


def _run_plan_entries(args: argparse.Namespace) -> List[str]:
    """Run-plan summary for the startup banner.

    v1.5.1 Item 2.3 base: phase list (from --phase / --full-run).
    v1.5.1 Item 3.1: when --phase-groups (or sugar that expanded to
    phase_groups) is in effect, render one line per group naming its
    phases. Multi-phase groups render as "Phase group K (phases N, M)".
    Iteration strategies and pace are Item 3.2 additions.
    """
    entries: List[str] = []
    phase_groups = getattr(args, "phase_groups", None)
    if phase_groups:
        for idx, group in enumerate(phase_groups, start=1):
            if len(group) == 1:
                entries.append(f"Phase group {idx}      (phase {group[0]})")
            else:
                joined = ", ".join(group)
                entries.append(f"Phase group {idx}      (phases {joined})")
    elif getattr(args, "next_iteration", False):
        strategies = ",".join(getattr(args, "strategy", []) or ["gap"])
        entries.append(f"Iteration strategies: {strategies}")
    # Item 3.2 iteration + pace block.
    iterations = getattr(args, "iterations", None)
    if iterations:
        for strat in iterations:
            entries.append(f"Iteration:            {strat}")
    elif getattr(args, "full_run", False):
        # full_run sugar is expanded in parse_args; guard here for
        # callers that pass a bare Namespace without going through
        # parse_args (e.g. tests and the internal full-run re-dispatch).
        for strat in ALL_STRATEGIES:
            entries.append(f"Iteration:            {strat}")
    pace = int(getattr(args, "pace_seconds", 0) or 0)
    if pace > 0:
        entries.append(f"Pace:                 {pace}s between prompts")
    return entries


def print_startup_banner(
    repo_dir: Path,
    log_path: Path,
    args: argparse.Namespace,
    *,
    platform_name: Optional[str] = None,
) -> None:
    """Emit the startup banner via logboth so it lands in both stdout
    and the run log file. Single call site in each run entry point."""
    banner = build_startup_banner(
        repo_dir,
        log_path,
        _run_plan_entries(args),
        platform_name=platform_name,
    )
    lib.logboth(log_path, banner)


def run_prompt(repo_dir: Path, prompt: str, pass_name: str, output_file: Path, log_file: Path, runner: str, model: Optional[str]) -> int:
    command = command_for_runner(runner, prompt, model)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("\n")
        handle.write("=" * 80 + "\n")
        handle.write(f"PLAYBOOK RUNNER - pass: {pass_name}\n")
        handle.write(f"Working directory: {repo_dir}\n")
        handle.write(f"Tool transcript (raw stdout/stderr): {output_file}\n")
        handle.write("=" * 80 + "\n")
        handle.write("SHELL COMMAND (exact invocation - cwd is repo root):\n")
        handle.write(f"  {command_preview(command)}\n\n")
        handle.write(f"--- BEGIN PROMPT ({len(prompt)} bytes) ---\n")
        handle.write(prompt)
        if not prompt.endswith("\n"):
            handle.write("\n")
        handle.write("--- END PROMPT ---\n\n")

    with output_file.open("w", encoding="utf-8") as out_handle:
        try:
            result = subprocess.run(
                command,
                cwd=str(repo_dir),
                stdout=out_handle,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            out_handle.write(f"ERROR: command not found: {command[0]}\n")
            result = subprocess.CompletedProcess(command, returncode=127)

    append_file(output_file, log_file)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"\n--- EXIT CODE: {result.returncode} ---\n")
    return result.returncode


def ensure_runner_available(runner: str) -> bool:
    if runner == "copilot":
        return lib.require_copilot()
    return shutil.which("claude") is not None


def docs_present(repo_dir: Path) -> bool:
    docs_dir = repo_dir / "docs_gathered"
    if not docs_dir.is_dir():
        return False
    return any(
        f for f in docs_dir.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.stat().st_size > 0
    )


# v1.5.2: pre-run reference_docs guard.
_REFERENCE_DOCS_PLAINTEXT_EXTS = frozenset({".txt", ".md"})
_REFERENCE_DOCS_SKIPPED = frozenset({"README.md"})


def _reference_docs_plaintext(reference_docs_dir: Path) -> List[Path]:
    """Return plaintext files under reference_docs/ that ingest would consider."""
    if not reference_docs_dir.is_dir():
        return []
    files: List[Path] = []
    for path in sorted(reference_docs_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in _REFERENCE_DOCS_SKIPPED:
            continue
        if path.suffix.lower() in _REFERENCE_DOCS_PLAINTEXT_EXTS:
            files.append(path)
    return files


def formal_docs_guard_banner(repo_dir: Path) -> Optional[str]:
    """Return a multi-line warning banner, or None if reference_docs/ is clean.

    v1.5.2: Clean = reference_docs/ exists and contains at least one plaintext
    file (under reference_docs/ or reference_docs/cite/). Missing or empty
    triggers a non-blocking warning and Phase 1 proceeds with Tier 3 evidence.

    Function name preserved for backwards compatibility with call sites that
    reference it by that name.
    """
    reference_docs_dir = repo_dir / "reference_docs"
    suppress_hint = (
        "Suppress this warning with --no-formal-docs for self-audit "
        "bootstrap / minimal-repo cases that legitimately have no reference docs."
    )

    if not reference_docs_dir.is_dir():
        trigger = f"reference_docs/ is missing at {reference_docs_dir}"
    else:
        plaintext = _reference_docs_plaintext(reference_docs_dir)
        if not plaintext:
            trigger = f"reference_docs/ is empty at {reference_docs_dir}"
        else:
            return None

    banner = [
        "",
        "=" * 72,
        "WARN: pre-run reference_docs guard triggered",
        "",
        f"  {trigger}",
        "",
        "  The playbook will proceed using only Tier 3 evidence (the source",
        "  tree itself). For better results, drop plaintext documentation into:",
        "    reference_docs/            ← AI chats, design notes, retrospectives (Tier 4)",
        "    reference_docs/cite/       ← project specs, RFCs, API contracts (Tier 1/2)",
        f"  {suppress_hint}",
        "=" * 72,
        "",
    ]
    return "\n".join(banner)


def _clear_live_quality(quality_dir: Path) -> None:
    """Remove every live child of quality/ except the runs/ archive subtree and
    RUN_INDEX.md (the append-only history that lives alongside runs/)."""
    if not quality_dir.is_dir():
        return
    for child in list(quality_dir.iterdir()):
        if child.name in ("runs", "RUN_INDEX.md"):
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def _prior_run_id_from_live_index(quality_dir: Path) -> Optional[str]:
    """Return the prior run's compact timestamp from quality/INDEX.md, or None."""
    index_path = quality_dir / "INDEX.md"
    if not index_path.is_file():
        return None
    payload = archive_lib.load_index_payload(index_path)
    if not isinstance(payload, dict):
        return None
    ts = payload.get("run_timestamp_start")
    if not isinstance(ts, str) or not ts:
        return None
    return archive_lib.compact_from_extended(ts)


def archive_previous_run(repo_dir: Path, current_run_timestamp: str) -> None:
    """Make room for a new run by archiving whatever live quality/ content remains.

    v1.5.1 unified pipeline (Phase 5 revision r1): both the Phase-1 entry
    archive and the end-of-Phase-6 archive go through
    `archive_lib.archive_run()` so every `quality/runs/<ts>/` folder has an
    `INDEX.md` with §11 fields and every run emits a row into
    `quality/RUN_INDEX.md`.

    Branches, in order:

    1. If quality/ has no live content beyond runs/, nothing to do.
    2. If quality/INDEX.md names a prior run whose archive folder already
       exists under quality/runs/<prior-ts>/, the prior run was auto-archived
       at its own successful Phase 6 — just clear the live tree.
    3. Otherwise archive the live tree as a partial prior run, using the
       prior run's own start timestamp when available (from INDEX.md), else
       falling back to the current run's timestamp.
    """
    quality_dir = repo_dir / "quality"
    if not quality_dir.is_dir():
        return
    if not any(child.name != "runs" for child in quality_dir.iterdir()):
        return

    prior_ts = _prior_run_id_from_live_index(quality_dir)
    if prior_ts and (quality_dir / "runs" / prior_ts).is_dir():
        _clear_live_quality(quality_dir)
        return

    archive_ts = prior_ts or current_run_timestamp
    try:
        archive_lib.archive_run(
            repo_dir,
            archive_ts,
            status="partial",
            gate_verdict_override="partial",
        )
    except archive_lib.ArchiveError:
        # Archive target already exists under a -PARTIAL suffix — the prior
        # attempt was already preserved. Clear the live tree and continue.
        pass
    _clear_live_quality(quality_dir)


def _build_invocation_flags(args: Optional[argparse.Namespace], **overrides) -> dict:
    """Assemble the invocation_flags dict persisted in INDEX.md.

    Follows the additive pattern established in Phase 1 revision
    (bin/archive_lib.py:404-441): new flags are additional keys in the
    same dict, never a reshape. Defaults come from argparse Namespace
    attributes with getattr() so legacy callers still work. Explicit
    kwargs override Namespace values for the (rare) call sites that
    pass a value directly for testability.

    v1.5.1 Phase 3: new keys ``phase_groups`` (string | null),
    ``iterations`` (string | null), ``pace_seconds`` (int, default 0),
    ``full_run`` (bool, default false).
    """
    defaults = {
        "no_formal_docs": False,
        "no_stdout_echo": False,
        "verbose": False,
        "quiet": False,
        "progress_interval": 2,
        "phase_groups": None,
        "iterations": None,
        "pace_seconds": 0,
        "full_run": False,
    }
    if args is not None:
        defaults["no_formal_docs"] = bool(getattr(args, "no_formal_docs", False))
        defaults["no_stdout_echo"] = bool(getattr(args, "no_stdout_echo", False))
        defaults["verbose"] = bool(getattr(args, "verbose", False))
        defaults["quiet"] = bool(getattr(args, "quiet", False))
        interval = getattr(args, "progress_interval", 2)
        defaults["progress_interval"] = int(interval) if interval is not None else 2
        # Phase 3 additions.
        phase_groups = getattr(args, "phase_groups", None)
        if phase_groups:
            defaults["phase_groups"] = _format_phase_groups(phase_groups)
        iterations = getattr(args, "iterations", None)
        if iterations:
            defaults["iterations"] = ",".join(iterations)
        defaults["pace_seconds"] = int(getattr(args, "pace_seconds", 0) or 0)
        defaults["full_run"] = bool(getattr(args, "full_run", False))

    # Explicit overrides win over args values.
    for key, value in overrides.items():
        if key == "progress_interval":
            defaults[key] = int(value)
        elif key == "pace_seconds":
            defaults[key] = int(value)
        elif key in ("phase_groups", "iterations"):
            defaults[key] = value  # keep None or string as provided
        elif key in ("no_formal_docs", "no_stdout_echo", "verbose", "quiet", "full_run"):
            defaults[key] = bool(value)
        else:
            defaults[key] = value
    return defaults


def _index_flag_kwargs(args: argparse.Namespace) -> dict:
    """Convert an args Namespace into the kwargs write_live_index_* expects.

    Centralizes the args-to-INDEX flag mapping so the three call sites
    (Phase 1 stub, singlepass stub, Phase 6 final re-render) stay in sync
    as new flags are added. `phase_groups` / `iterations` are serialized
    to their canonical string spec form.
    """
    phase_groups_list = getattr(args, "phase_groups", None)
    iterations_list = getattr(args, "iterations", None)
    return {
        "no_formal_docs": getattr(args, "no_formal_docs", False),
        "no_stdout_echo": getattr(args, "no_stdout_echo", False),
        "verbose": getattr(args, "verbose", False),
        "quiet": getattr(args, "quiet", False),
        "progress_interval": getattr(args, "progress_interval", 2),
        "phase_groups": _format_phase_groups(phase_groups_list) if phase_groups_list else None,
        "iterations": ",".join(iterations_list) if iterations_list else None,
        "pace_seconds": getattr(args, "pace_seconds", 0) or 0,
        "full_run": getattr(args, "full_run", False),
    }


def write_live_index_stub(
    repo_dir: Path,
    timestamp: str,
    *,
    no_formal_docs: bool = False,
    no_stdout_echo: bool = False,
    verbose: bool = False,
    quiet: bool = False,
    progress_interval: int = 2,
    phase_groups: Optional[str] = None,
    iterations: Optional[str] = None,
    pace_seconds: int = 0,
    full_run: bool = False,
) -> None:
    """Render a minimal quality/INDEX.md at run start so the gate's invariant #10
    check has something to validate if the run is interrupted mid-flight.

    v1.5.1 Phase 1 rev (Council — gpt-5.4 blocker 2): ``no_formal_docs`` is
    persisted under ``invocation_flags`` so later auditors can distinguish
    an intentionally-empty formal_docs/ run from an accidentally-empty one.

    v1.5.1 Phase 2: additional flags land in the same ``invocation_flags``
    dict — ``no_stdout_echo`` (Item 2.1), ``verbose`` / ``quiet`` /
    ``progress_interval`` (Item 2.2). The dict is additive per the
    convention in bin/archive_lib.py:404-441.
    """
    quality_dir = repo_dir / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    start_ext = archive_lib.extended_from_compact(timestamp)
    flags = _build_invocation_flags(
        None,
        no_formal_docs=no_formal_docs,
        no_stdout_echo=no_stdout_echo,
        verbose=verbose,
        quiet=quiet,
        progress_interval=progress_interval,
        phase_groups=phase_groups,
        iterations=iterations,
        pace_seconds=pace_seconds,
        full_run=full_run,
    )
    payload = {
        "run_timestamp_start": start_ext,
        "run_timestamp_end": start_ext,
        "duration_seconds": 0,
        "qpb_version": lib.detect_skill_version() or "unknown",
        "target_repo_path": ".",
        "target_repo_git_sha": archive_lib._git_head_sha(repo_dir),
        "target_project_type": "Code",  # TODO(v1.5.2): Code/Skill/Hybrid detector.
        "phases_executed": [],
        "summary": {"requirements": {}, "bugs": {}, "gate_verdict": "partial"},
        "artifacts": [],
        "invocation_flags": flags,
    }
    (quality_dir / "INDEX.md").write_text(
        archive_lib.render_index_markdown(
            timestamp,
            payload,
            provenance=(
                "written by bin/run_playbook at Phase 1 entry (stub; "
                "re-rendered at end of Phase 6)"
            ),
        ),
        encoding="utf-8",
    )


def write_live_index_final(
    repo_dir: Path,
    timestamp: str,
    *,
    gate_verdict: str,
    no_formal_docs: bool = False,
    no_stdout_echo: bool = False,
    verbose: bool = False,
    quiet: bool = False,
    progress_interval: int = 2,
    phase_groups: Optional[str] = None,
    iterations: Optional[str] = None,
    pace_seconds: int = 0,
    full_run: bool = False,
) -> None:
    """Re-render quality/INDEX.md at end of Phase 6 with the run's real counts.

    `gate_verdict` is one of pass | fail | partial. Counts come from
    `archive_lib.build_index_payload()` walking the live quality/ tree;
    `run_timestamp_start` is forced to the run's true start and
    `run_timestamp_end` is captured now so `duration_seconds` is real.

    v1.5.1 Phase 1 rev (Council — gpt-5.4 blocker 2): ``no_formal_docs`` is
    persisted under ``invocation_flags`` so the Phase-6 re-render preserves
    the flag state recorded by the Phase-1 stub.

    v1.5.1 Phase 2: additional flags land in the same ``invocation_flags``
    dict — ``no_stdout_echo`` (Item 2.1), ``verbose`` / ``quiet`` /
    ``progress_interval`` (Item 2.2).
    """
    quality_dir = repo_dir / "quality"
    flags = _build_invocation_flags(
        None,
        no_formal_docs=no_formal_docs,
        no_stdout_echo=no_stdout_echo,
        verbose=verbose,
        quiet=quiet,
        progress_interval=progress_interval,
        phase_groups=phase_groups,
        iterations=iterations,
        pace_seconds=pace_seconds,
        full_run=full_run,
    )
    payload = archive_lib.build_index_payload(
        repo_dir,
        quality_dir,
        target_repo_path=".",
        target_project_type="Code",
        gate_verdict_override=gate_verdict,
        invocation_flags=flags,
    )
    start_ext = archive_lib.extended_from_compact(timestamp)
    end_ext = archive_lib.utc_extended_timestamp()
    payload["run_timestamp_start"] = start_ext
    payload["run_timestamp_end"] = end_ext
    payload["duration_seconds"] = archive_lib._duration_seconds(start_ext, end_ext)
    (quality_dir / "INDEX.md").write_text(
        archive_lib.render_index_markdown(
            timestamp,
            payload,
            provenance="written by bin/run_playbook at end of Phase 6 (final counts)",
        ),
        encoding="utf-8",
    )


def final_artifact_gaps(repo_dir: Path) -> List[str]:
    artifacts = [
        "quality/REQUIREMENTS.md",
        "quality/CONTRACTS.md",
        "quality/COVERAGE_MATRIX.md",
        "quality/COMPLETENESS_REPORT.md",
        "quality/PROGRESS.md",
        "quality/QUALITY.md",
        "quality/RUN_CODE_REVIEW.md",
        "quality/RUN_INTEGRATION_TESTS.md",
        "quality/RUN_SPEC_AUDIT.md",
        "quality/RUN_TDD_TESTS.md",
    ]
    missing = [artifact for artifact in artifacts if not (repo_dir / artifact).is_file()]
    if lib.find_functional_test(repo_dir) is None:
        missing.append("functional test")
    return missing


def run_one_phase(
    repo_dir: Path,
    phase: str,
    phase_list: Sequence[str],
    args: argparse.Namespace,
    log_file: Path,
    timestamp: str,
) -> bool:
    gate = check_phase_gate(repo_dir, phase)
    for message in gate.messages:
        lib.logboth(log_file, lib.log(f"  {message}"))
    if not gate.ok:
        return False

    phase_index = phase_list.index(phase) + 1 if phase in phase_list else 1
    prompt = build_phase_prompt(phase, no_seeds=args.no_seeds)
    output_file = repo_dir / "quality" / "control_prompts" / f"phase{phase}.output.txt"
    lib.logboth(log_file, lib.log(f"  Phase {phase_index}/{len(phase_list) or 1} ({phase_label(phase)}): {repo_dir.name}"))
    exit_code = run_prompt(repo_dir, prompt, f"phase{phase}", output_file, log_file, args.runner, args.model)
    if exit_code:
        lib.logboth(log_file, lib.log(f"  ABORT Phase {phase}: child runner exited {exit_code}"))
        return False

    _log_phase_completion(repo_dir, phase, log_file, args, timestamp)
    return True


def _pace_between_prompts(
    seconds: int,
    log_file: Path,
    monitor: Optional["progress_monitor.ProgressMonitor"] = None,
    *,
    sleep_fn: Optional[callable] = None,
) -> None:
    """Sleep ``seconds`` between consecutive prompts, emitting a heartbeat.

    v1.5.1 Item 3.2 (Phase 3 revision: dedupe pacing heartbeat). When
    ``seconds > 0``:
      - If ``monitor`` is provided, call monitor.set_pacing(seconds)
        before sleeping. The monitor thread emits exactly one
        ``Pacing: Ns before next prompt…`` line on its next
        _poll_once() cycle (within progress_interval seconds).
      - Sleep for ``seconds``.
      - monitor.clear_pacing() in a try/finally so an exception during
        sleep (KeyboardInterrupt in practice) still disarms the monitor.

    Prior to the Phase 3 revision, this function also emitted a
    timestamped ``Pacing:`` line via logboth before set_pacing. Council
    (both adversarial seats) flagged that as duplicate output since the
    monitor's own heartbeat produces the same literal line. The
    monitor is now the sole source of the heartbeat; operators running
    with --quiet get no heartbeat (as expected — they opted out of
    progress output entirely).

    ``sleep_fn`` is patchable for tests; production callers leave it
    at None to use time.sleep().
    """
    if seconds <= 0:
        return
    if monitor is not None:
        monitor.set_pacing(seconds)
    try:
        (sleep_fn or time.sleep)(seconds)
    finally:
        if monitor is not None:
            monitor.clear_pacing()


def _build_group_prompt(phases: Sequence[str], no_seeds: bool) -> str:
    """Concatenate per-phase prompt bodies for a multi-phase group.

    v1.5.1 Item 3.1. The first phase's prompt opens the combined prompt
    with no prefix; subsequent phases are separated by a single
    visible header line so the LLM can tell which phase's work
    it's producing. Per Impl-Plan Open Question 5 (lean: visible,
    minimal), the header is a plain `=== Phase N (Label) ===` string.
    """
    parts: List[str] = []
    for i, phase in enumerate(phases):
        body = build_phase_prompt(phase, no_seeds=no_seeds)
        if i > 0:
            parts.append(f"\n\n=== Phase {phase} ({phase_label(phase)}) ===\n\n")
        parts.append(body)
    return "".join(parts)


def _group_transcript_path(repo_dir: Path, phases: Sequence[str]) -> Path:
    """Transcript file for a group. Single-phase groups reuse the
    legacy phaseN.output.txt name; multi-phase groups join with '-'
    (e.g. phase3-4.output.txt)."""
    suffix = "-".join(phases)
    return repo_dir / "quality" / "control_prompts" / f"phase{suffix}.output.txt"


def _group_pass_label(phases: Sequence[str]) -> str:
    """Pass label used by run_prompt (appears in the per-prompt log header)."""
    return "phase" + "-".join(phases)


def run_one_phase_group(
    repo_dir: Path,
    group: Sequence[str],
    phase_groups: Sequence[Sequence[str]],
    args: argparse.Namespace,
    log_file: Path,
    timestamp: str,
    monitor: "progress_monitor.ProgressMonitor",
) -> bool:
    """Execute a single phase group as one LLM call.

    v1.5.1 Item 3.1. For a single-phase group this is equivalent to the
    prior per-phase flow (and delegates to run_one_phase to preserve
    that path's per-phase post-hoc logging). For a multi-phase group
    the per-phase prompt bodies are concatenated into one prompt and
    submitted to the runner once; gate checks are performed at the
    group boundary (first-phase gate; a failure aborts the run).

    The progress monitor's set_transcript_path() is called once per
    phase in the group so the monitor-call count matches phase count,
    not group count — but for a multi-phase group all phase-level
    transcript pointers resolve to the group's consolidated file
    (stub per-phase files are created for operator-facing consistency).
    """
    if not group:
        return True

    if len(group) == 1:
        phase = group[0]
        # Flatten every phase across all groups into the counter list so
        # single-phase groups keep their historical "Phase X/Y" header.
        flat = [p for g in phase_groups for p in g]
        monitor.set_transcript_path(_group_transcript_path(repo_dir, [phase]))
        return run_one_phase(repo_dir, phase, flat, args, log_file, timestamp)

    # Multi-phase group path.
    gate = check_phase_gate(repo_dir, group[0])
    for message in gate.messages:
        lib.logboth(log_file, lib.log(f"  {message}"))
    if not gate.ok:
        return False

    group_transcript = _group_transcript_path(repo_dir, group)
    group_transcript.parent.mkdir(parents=True, exist_ok=True)
    # Per-phase transcript stubs + monitor registration. Earlier phases
    # in the group get a small pointer file; the last phase reuses the
    # group transcript path directly so tail + grep keep working.
    for i, phase in enumerate(group):
        per_phase_path = _group_transcript_path(repo_dir, [phase])
        monitor.set_transcript_path(per_phase_path)
        if i < len(group) - 1 and per_phase_path != group_transcript:
            per_phase_path.write_text(
                f"# Phase {phase} ran as part of group {'+'.join(group)}.\n"
                f"# Combined transcript: {group_transcript}\n",
                encoding="utf-8",
            )
    # Monitor ends up pointing at the last phase's transcript file; the
    # group actually writes to the group-transcript path, so point the
    # monitor there for the actual subprocess output.
    monitor.set_transcript_path(group_transcript)

    group_label = "+".join(group)
    labels = ", ".join(f"{p} ({phase_label(p)})" for p in group)
    lib.logboth(
        log_file,
        lib.log(f"  Phase group {group_label}: {labels} — single prompt"),
    )

    prompt = _build_group_prompt(group, no_seeds=args.no_seeds)
    exit_code = run_prompt(
        repo_dir,
        prompt,
        _group_pass_label(group),
        group_transcript,
        log_file,
        args.runner,
        args.model,
    )
    if exit_code:
        lib.logboth(log_file, lib.log(f"  ABORT Phase group {group_label}: child runner exited {exit_code}"))
        return False

    # Per-phase completion summaries: walk each phase's post-hoc output
    # expectations individually so the operator sees which phase wrote
    # which artifacts (matching the single-phase logging).
    for phase in group:
        _log_phase_completion(repo_dir, phase, log_file, args, timestamp)
    return True


def _log_phase_completion(
    repo_dir: Path,
    phase: str,
    log_file: Path,
    args: argparse.Namespace,
    timestamp: str,
) -> None:
    """Emit the same post-hoc completion logging single-phase groups do.

    Factored out so run_one_phase_group's multi-phase path and
    run_one_phase share the same line. Phase 6 also re-renders INDEX.md
    here — same behavior as before the refactor.
    """
    quality_dir = repo_dir / "quality"
    if phase == "1":
        lib.logboth(log_file, lib.log(f"  Phase 1 complete: {count_lines(quality_dir / 'EXPLORATION.md')} lines in EXPLORATION.md"))
    elif phase == "2":
        missing = [artifact for artifact in ["quality/REQUIREMENTS.md", "quality/QUALITY.md", "quality/CONTRACTS.md"] if not (repo_dir / artifact).is_file()]
        if missing:
            lib.logboth(log_file, lib.log(f"  WARN Phase 2: missing {' '.join(missing)}"))
        else:
            lib.logboth(log_file, lib.log("  Phase 2 complete: core artifacts generated"))
    elif phase == "3":
        bugs_count = lib.count_matching_lines(quality_dir / "BUGS.md", r"### BUG-")
        patch_count = sum(1 for _ in (quality_dir / "patches").glob("*") if (quality_dir / "patches").is_dir()) if (quality_dir / "patches").is_dir() else 0
        lib.logboth(log_file, lib.log(f"  Phase 3 complete: {bugs_count} bugs, {patch_count} patches"))
    elif phase == "4":
        spec_audits_dir = quality_dir / "spec_audits"
        auditor_reports = sum(1 for path in spec_audits_dir.glob("*auditor*") if path.is_file()) if spec_audits_dir.is_dir() else 0
        lib.logboth(log_file, lib.log(f"  Phase 4 complete: {auditor_reports} auditor reports"))
    elif phase == "5":
        writeups_dir = quality_dir / "writeups"
        results_dir = quality_dir / "results"
        writeups = sum(1 for path in writeups_dir.glob("*") if path.is_file()) if writeups_dir.is_dir() else 0
        red_logs = sum(1 for path in results_dir.glob("BUG-*.red.log") if path.is_file()) if results_dir.is_dir() else 0
        lib.logboth(log_file, lib.log(f"  Phase 5 complete: {writeups} writeups, {red_logs} TDD red-phase logs"))
    elif phase == "6":
        # v1.5.2 (C13.9, site 5): re-run the gate via _finalize_iteration
        # before reading quality-gate.log. The previous flow read whatever
        # the LLM session had last written, which could be stale by an
        # iteration. The finalizer overwrites the receipt with the
        # orchestrator-authoritative current state, then we read it.
        finalizer_status = _finalize_iteration(
            repo_dir,
            label="post-phase-6",
            log_file=log_file,
        )
        gate_log = quality_dir / "results" / "quality-gate.log"
        gate_result = "unknown"
        if gate_log.is_file():
            lines = gate_log.read_text(encoding="utf-8", errors="ignore").splitlines()
            if lines:
                gate_result = lines[-1]
        lib.logboth(log_file, lib.log(f"  Phase 6 complete: {gate_result}"))
        gate_passed = _gate_pass(gate_result, quality_dir)
        # v1.5.2 (C13.9): map the finalizer's status into INDEX's
        # pass|fail|partial schema. 'aborted' has no INDEX equivalent
        # and maps to 'partial' (incomplete-run code). For non-aborted
        # runs the finalizer's pass/fail aligns with the gate verdict
        # we just read; preserve the historical 'warn → partial' fallback
        # for the read-from-log path so behavior matches when the
        # finalizer agrees.
        if finalizer_status == "aborted":
            verdict = "partial"
        elif finalizer_status == "pass" and gate_passed:
            verdict = "pass"
        elif finalizer_status == "pass" and "warn" in gate_result.lower():
            verdict = "partial"
        else:
            verdict = "fail"
        try:
            write_live_index_final(
                repo_dir,
                timestamp,
                gate_verdict=verdict,
                **_index_flag_kwargs(args),
            )
        except Exception as exc:  # noqa: BLE001 — log and continue
            lib.logboth(log_file, lib.log(f"  WARN write_live_index_final skipped: {exc}"))
        if gate_passed:
            try:
                archive_lib.archive_run(
                    repo_dir,
                    timestamp,
                    status="success",
                    gate_verdict_override="pass",
                )
            except archive_lib.ArchiveError as exc:
                lib.logboth(log_file, lib.log(f"  WARN archive_run skipped: {exc}"))


def _gate_pass(gate_result_line: str, quality_dir: Path) -> bool:
    """Return True if the end-of-Phase-6 gate state indicates a clean pass."""
    if "PASS" in gate_result_line.upper() and "FAIL" not in gate_result_line.upper():
        return True
    latest = quality_dir / "results" / "gate-report-latest.json"
    if latest.is_file():
        try:
            import json

            data = json.loads(latest.read_text(encoding="utf-8", errors="ignore"))
            verdict = str(data.get("gate_verdict") or data.get("gate_result") or "").lower()
            return verdict == "pass"
        except (json.JSONDecodeError, OSError):
            return False
    return False


def run_one_phased(repo_dir: Path, phase_groups: Sequence[Sequence[str]], args: argparse.Namespace, timestamp: str) -> int:
    """Execute one or more phase groups for a single target repo.

    v1.5.1 Item 3.1: takes a list-of-lists (each inner list is a group).
    Single-phase groups hit the legacy run_one_phase path; multi-phase
    groups concatenate prompts via run_one_phase_group. Gate checks
    happen at the group boundary.
    """
    log_file = configure_logging(
        repo_dir,
        timestamp,
        no_stdout_echo=getattr(args, "no_stdout_echo", False),
    )
    print_startup_banner(repo_dir, log_file, args)
    if not docs_present(repo_dir):
        print(lib.log(f"WARN: {repo_dir.name} - docs_gathered/ is missing or empty; proceeding with code-only analysis"))
    if not getattr(args, "no_formal_docs", False):
        banner = formal_docs_guard_banner(repo_dir)
        if banner is not None:
            lib.logboth(log_file, banner, echo=True)

    flat_phases = [p for group in phase_groups for p in group]
    if "1" in flat_phases:
        archive_previous_run(repo_dir, timestamp)
        # Write a minimal quality/INDEX.md up front so an interrupted run
        # still satisfies schemas.md §10 invariant #10 when the gate is
        # invoked out-of-band on the partial tree.
        write_live_index_stub(
            repo_dir,
            timestamp,
            **_index_flag_kwargs(args),
        )

    (repo_dir / "quality" / "control_prompts").mkdir(parents=True, exist_ok=True)
    plan_desc = _format_phase_groups(phase_groups)
    lib.logboth(log_file, lib.log(f"Starting playbook (phase groups: {plan_desc}): {repo_dir.name} (runner={args.runner})"))

    # v1.5.1 Item 2.2: live progress monitor. Started here so the first
    # PROGRESS.md write (inside Phase 1) gets picked up within one poll
    # interval; torn down in the `finally` below so an abnormal Phase N
    # exit still joins the thread.
    monitor = progress_monitor.ProgressMonitor(
        progress_path=repo_dir / "quality" / "PROGRESS.md",
        log_file=log_file,
        emit=lib.logboth,
        interval=getattr(args, "progress_interval", 2),
        verbose=getattr(args, "verbose", False),
        quiet=getattr(args, "quiet", False),
    )

    exit_status = 0
    pace_seconds = int(getattr(args, "pace_seconds", 0) or 0)
    iterations_follow = bool(getattr(args, "iterations", None))
    with monitor:
        for index, group in enumerate(phase_groups):
            if not run_one_phase_group(
                repo_dir, group, phase_groups, args, log_file, timestamp, monitor
            ):
                lib.logboth(log_file, lib.log(f"ABORT: Phase group {'+'.join(group)} gate failed for {repo_dir.name}"))
                exit_status = 1
                break
            # v1.5.1 Item 3.2: inter-group pacing. Skipped after the
            # final group unless iterations follow (bridge pace).
            is_last_group = index == len(phase_groups) - 1
            if pace_seconds > 0 and (not is_last_group or iterations_follow):
                _pace_between_prompts(pace_seconds, log_file, monitor)
    if exit_status:
        return exit_status

    lib.logboth(log_file, lib.log(f"Playbook complete (phase groups: {plan_desc}): {repo_dir.name}"))

    missing = final_artifact_gaps(repo_dir)
    if missing:
        lib.logboth(log_file, lib.log(f"WARNING: Missing: {' '.join(missing)}"))
    else:
        lib.logboth(log_file, lib.log("All artifacts present"))
    lib.cleanup_repo(repo_dir)
    return 0


def run_one_singlepass(repo_dir: Path, args: argparse.Namespace, timestamp: str) -> int:
    log_file = configure_logging(
        repo_dir,
        timestamp,
        no_stdout_echo=getattr(args, "no_stdout_echo", False),
    )
    print_startup_banner(repo_dir, log_file, args)
    if not docs_present(repo_dir):
        print(lib.log(f"WARN: {repo_dir.name} - docs_gathered/ is missing or empty; proceeding with code-only analysis"))
    if not getattr(args, "no_formal_docs", False):
        banner = formal_docs_guard_banner(repo_dir)
        if banner is not None:
            lib.logboth(log_file, banner, echo=True)

    if args.next_iteration:
        if not (repo_dir / "quality" / "EXPLORATION.md").is_file():
            print(lib.log(f"SKIP: {repo_dir.name} - no quality/EXPLORATION.md to iterate on"))
            return 1
        # In the single-strategy path, args.strategy is a list with one item;
        # execute_strategy_list handles multi-item lists one strategy at a time.
        strategy_name = args.strategy[0]
        prompt = iteration_prompt(strategy_name)
        pass_label = f"iteration-{strategy_name}"
        lib.logboth(log_file, lib.log(f"Starting iteration ({strategy_name}): {repo_dir.name} (runner={args.runner}, building on existing quality/)"))
    else:
        archive_previous_run(repo_dir, timestamp)
        write_live_index_stub(
            repo_dir,
            timestamp,
            **_index_flag_kwargs(args),
        )
        prompt = single_pass_prompt(no_seeds=args.no_seeds)
        pass_label = "full"
        lib.logboth(log_file, lib.log(f"Starting playbook (single-pass): {repo_dir.name} (runner={args.runner})"))

    control_prompts = repo_dir / "quality" / "control_prompts"
    control_prompts.mkdir(parents=True, exist_ok=True)
    output_file = control_prompts / "playbook_run.output.txt"
    exit_code = run_prompt(repo_dir, prompt, pass_label, output_file, log_file, args.runner, args.model)

    # v1.5.2 (C13.9): label distinguishes the iteration branch (which goes
    # through this function via --next-iteration --strategy X) from the
    # baseline single-pass branch.
    finalize_label_base = (
        f"{args.strategy[0]}" if args.next_iteration else "singlepass"
    )

    if exit_code:
        lib.logboth(log_file, lib.log(f"ABORT: child runner exited {exit_code}"))
        # v1.5.2 (C13.9, site 4): orchestrator-authoritative finalization
        # on abort. Captures state-at-abort even when the LLM session ended
        # before its Phase 5 step 7. This is the express-1.5.1 case in
        # production — the runner exits mid-iteration and the orchestrator
        # would otherwise leave PROGRESS.md and the receipt in silent
        # half-state.
        _finalize_iteration(
            repo_dir,
            label=f"abort-during-{finalize_label_base}",
            log_file=log_file,
            aborted=True,
            abort_reason=f"runner exited {exit_code}",
        )
        return exit_code
    lib.logboth(log_file, lib.log(f"Playbook complete: {repo_dir.name}"))

    missing = final_artifact_gaps(repo_dir)
    if missing:
        lib.logboth(log_file, lib.log(f"WARNING: Missing: {' '.join(missing)}"))
    else:
        lib.logboth(log_file, lib.log("All artifacts present"))
    # v1.5.2 (C13.9, site 3): orchestrator-authoritative finalization after
    # a successful single-pass or single-strategy iteration run.
    _finalize_iteration(
        repo_dir,
        label=f"post-{finalize_label_base}",
        log_file=log_file,
    )
    lib.cleanup_repo(repo_dir)
    return 0


def _append_iteration_heartbeat(progress_path: Path, line: str) -> None:
    """Append a `## Iteration: ...` section to quality/PROGRESS.md.

    v1.5.1 Phase 2 revision. Iteration strategies (gap, unfiltered,
    parity, adversarial) can each run for tens of minutes against a
    real LLM. Without per-strategy PROGRESS.md updates the file goes
    stale at the Phase 6 line, and operators can't tell a 15-minute
    iteration from a hung run.

    Behavior:
      - mkdir parents on demand so this works even when iterations
        run before any phase wrote PROGRESS.md.
      - Append-only — the existing phase-loop content is preserved.
      - Each call writes one `## ` header followed by a blank line
        and one body line. ProgressMonitor's _printed_headers set
        (built around the `^##?\\s` regex) picks up the new section
        on its next poll cycle and surfaces it to stdout exactly
        once.
    """
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    with progress_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _iso_utc_now() -> str:
    """Compact ISO-8601 UTC timestamp for PROGRESS.md heartbeat lines."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# v1.5.2 (C13.9) — orchestrator-side post-iteration finalization.
# The four canonical install locations TOOLKIT.md documents for the gate
# script. Order matters: repo-root checkout is fastest to find for a
# source-tree run; the others mirror Claude Code / GitHub Copilot installs.
_GATE_INSTALL_LOCATIONS = (
    "quality_gate.py",
    ".claude/skills/quality-playbook/quality_gate.py",
    ".github/skills/quality_gate.py",
    ".github/skills/quality-playbook/quality_gate.py",
)


def _resolve_gate_script(repo_dir: Path) -> Optional[Path]:
    """Return the first existing quality_gate.py on TOOLKIT.md's install path
    list, or None when the gate script cannot be located. Pure path lookup —
    no I/O beyond ``Path.is_file()``."""
    for rel in _GATE_INSTALL_LOCATIONS:
        candidate = repo_dir / rel
        if candidate.is_file():
            return candidate
    return None


def _finalize_iteration(
    repo_dir: Path,
    label: str,
    log_file: Path,
    *,
    aborted: bool = False,
    abort_reason: str = "",
) -> str:
    """Orchestrator-authoritative post-iteration finalizer.

    Subprocesses ``quality_gate.py`` against ``repo_dir``, captures its full
    output (stdout+stderr) to ``quality/results/quality-gate.log`` (preserving
    the existing artifact contract — the receipt is exactly what the gate
    produces, no synthetic wrapping), and appends a structured
    ``## Run finalization`` block to ``quality/PROGRESS.md``.

    ``label`` distinguishes finalization runs in PROGRESS.md (e.g.
    "post-phase-6", "post-gap", "post-adversarial",
    "abort-during-adversarial").

    Returns one of: ``"pass"`` | ``"fail"`` | ``"aborted"``. Callers that pass
    the return value into ``write_live_index_final``'s ``gate_verdict``
    parameter must map ``"aborted"`` to ``"partial"`` (the existing INDEX
    schema only accepts pass/fail/partial).

    All errors are caught and logged via ``lib.logboth``; a finalizer failure
    must not propagate and crash the run, but it must leave a visible
    diagnostic in PROGRESS.md and the run log. See C13.9 brief edge cases 1–9
    for the full contract.
    """
    quality_dir = repo_dir / "quality"
    if not quality_dir.is_dir():
        # Edge case 4: legitimate state for a run that aborted before Phase 1
        # wrote anything. Nothing to finalize.
        try:
            lib.logboth(log_file, lib.log(f"[finalizer:{label}] skipped: no quality/ directory"))
        except Exception:  # noqa: BLE001 — finalizer must not crash run
            pass
        return "pass"

    results_dir = quality_dir / "results"
    progress_path = quality_dir / "PROGRESS.md"
    gate_log_path = results_dir / "quality-gate.log"
    results_dir.mkdir(parents=True, exist_ok=True)

    gate_script = _resolve_gate_script(repo_dir)
    gate_status: str  # "pass" | "fail"
    receipt_note: str

    if gate_script is None:
        # Edge case 1.
        gate_status = "fail"
        receipt_note = "<not produced — gate script not found>"
        try:
            gate_log_path.write_text(
                "=== finalizer: quality_gate.py not found in any of "
                f"{_GATE_INSTALL_LOCATIONS} ===\n",
                encoding="utf-8",
            )
        except OSError:
            pass
    else:
        try:
            completed = subprocess.run(
                ["python3", str(gate_script), str(repo_dir)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            combined = (completed.stdout or "") + (completed.stderr or "")
            try:
                gate_log_path.write_text(combined, encoding="utf-8")
            except OSError:
                pass
            gate_status = "pass" if completed.returncode == 0 else "fail"
        except subprocess.TimeoutExpired as exc:  # Edge case 3.
            partial = ""
            if exc.stdout:
                partial += exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode("utf-8", "replace")
            if exc.stderr:
                partial += exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", "replace")
            partial += "\n=== finalizer: gate timed out after 120s ===\n"
            try:
                gate_log_path.write_text(partial, encoding="utf-8")
            except OSError:
                pass
            gate_status = "fail"
        except Exception as exc:  # noqa: BLE001 — Edge case 2.
            try:
                gate_log_path.write_text(
                    f"=== finalizer: gate subprocess raised {type(exc).__name__}: {exc} ===\n",
                    encoding="utf-8",
                )
            except OSError:
                pass
            gate_status = "fail"
        receipt_note = "quality/results/quality-gate.log"

    final_status = "aborted" if aborted else gate_status

    # Edge case 6: BUGS.md may not exist; count_bug_writeups handles that.
    try:
        bug_count = lib.count_bug_writeups(repo_dir)
    except Exception:  # noqa: BLE001
        bug_count = 0

    block_lines = [
        "",
        f"## Run finalization ({label})",
        "",
        f"- Timestamp: {_iso_utc_now()}",
        f"- Bug count: {bug_count}",
        f"- Gate status: {final_status.upper()}",
        f"- Receipt: {receipt_note}",
    ]
    if aborted:
        block_lines.append(f"- Abort reason: {abort_reason}")
    block_lines.append("")
    block = "\n".join(block_lines)

    # Edge case 5: PROGRESS.md may not exist (iteration aborted before any
    # heartbeat-write). Append-or-create.
    try:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        with progress_path.open("a", encoding="utf-8") as handle:
            handle.write(block)
    except OSError:
        pass

    try:
        lib.logboth(
            log_file,
            lib.log(f"[finalizer:{label}] bugs={bug_count} status={final_status}"),
        )
    except Exception:  # noqa: BLE001
        pass

    return final_status


def run_one_iterations(
    repo_dir: Path,
    iterations: Sequence[str],
    args: argparse.Namespace,
    timestamp: str,
    *,
    phases_already_ran: bool = False,
) -> int:
    """Run a list of iteration strategies in one process, with per-strategy
    pacing and early-stop-on-zero-gain preserved.

    v1.5.1 Item 3.2. This is the in-worker counterpart to
    execute_strategy_list() (which spawns a fresh worker per strategy)
    — useful when the same invocation already ran phase groups in this
    process, so the whole unified run stays under a single log file and
    a single ProgressMonitor lifecycle.

    ``phases_already_ran`` skips the configure_logging / banner /
    archive_previous_run / stub-INDEX setup, since those already
    happened inside run_one_phased.
    """
    if phases_already_ran:
        log_file = log_file_for(repo_dir, timestamp)
    else:
        log_file = configure_logging(
            repo_dir,
            timestamp,
            no_stdout_echo=getattr(args, "no_stdout_echo", False),
        )
        print_startup_banner(repo_dir, log_file, args)
        if not docs_present(repo_dir):
            print(lib.log(f"WARN: {repo_dir.name} - docs_gathered/ is missing or empty; proceeding with code-only analysis"))
        if not getattr(args, "no_formal_docs", False):
            banner = formal_docs_guard_banner(repo_dir)
            if banner is not None:
                lib.logboth(log_file, banner, echo=True)

    if not (repo_dir / "quality" / "EXPLORATION.md").is_file():
        lib.logboth(
            log_file,
            lib.log(f"SKIP iterations: {repo_dir.name} - no quality/EXPLORATION.md"),
        )
        return 1

    monitor = progress_monitor.ProgressMonitor(
        progress_path=repo_dir / "quality" / "PROGRESS.md",
        log_file=log_file,
        emit=lib.logboth,
        interval=getattr(args, "progress_interval", 2),
        verbose=getattr(args, "verbose", False),
        quiet=getattr(args, "quiet", False),
    )

    pace_seconds = int(getattr(args, "pace_seconds", 0) or 0)
    progress_path = repo_dir / "quality" / "PROGRESS.md"
    with monitor:
        for index, strategy in enumerate(iterations):
            # v1.5.1 Phase 2 rev: PROGRESS.md heartbeat at iteration entry.
            _append_iteration_heartbeat(
                progress_path,
                f"\n## Iteration: {strategy} started\n\n{_iso_utc_now()}\n",
            )

            lib.logboth(log_file, lib.log(f"Starting iteration ({strategy}): {repo_dir.name}"))
            before = lib.count_bug_writeups(repo_dir)

            prompt = iteration_prompt(strategy)
            pass_label = f"iteration-{strategy}"
            output_file = repo_dir / "quality" / "control_prompts" / f"{pass_label}.output.txt"
            monitor.set_transcript_path(output_file)
            exit_code = run_prompt(
                repo_dir, prompt, pass_label, output_file, log_file,
                args.runner, args.model,
            )
            if exit_code:
                lib.logboth(log_file, lib.log(f"  ABORT iteration {strategy}: child runner exited {exit_code}"))
                # v1.5.2 (C13.9, site 2): orchestrator-authoritative
                # finalization on abort. Captures state-at-abort even when
                # the LLM session ended before its Phase 5 step 7.
                _finalize_iteration(
                    repo_dir,
                    label=f"abort-during-{strategy}",
                    log_file=log_file,
                    aborted=True,
                    abort_reason=f"runner exited {exit_code}",
                )
                return exit_code

            after = lib.count_bug_writeups(repo_dir)
            gained = after - before
            lib.logboth(log_file, lib.log(f"  Iteration {strategy}: {before} -> {after} bugs (+{gained})"))
            # v1.5.1 Phase 2 rev: PROGRESS.md heartbeat at iteration exit.
            _append_iteration_heartbeat(
                progress_path,
                f"\n## Iteration: {strategy} complete\n\n"
                f"{_iso_utc_now()} · bugs before: {before} · bugs after: {after} · net-new: {gained}\n",
            )
            # v1.5.2 (C13.9, site 1): orchestrator-authoritative finalization
            # after each successful iteration. Re-runs the gate so
            # quality-gate.log reflects the post-iteration state, not the
            # last LLM-written receipt.
            _finalize_iteration(
                repo_dir,
                label=f"post-{strategy}",
                log_file=log_file,
            )
            # Early-stop-on-zero-gain: unchanged semantics from
            # execute_strategy_list. v1.5.2 Phase 6: an explicit --iterations
            # list bypasses early-stop — the user asked for every strategy.
            if gained == 0 and not getattr(args, "_iterations_explicit", False):
                lib.logboth(log_file, lib.log("  No new bugs found - stopping early (diminishing returns)."))
                break
            is_last = index == len(iterations) - 1
            if pace_seconds > 0 and not is_last:
                _pace_between_prompts(pace_seconds, log_file, monitor)

    lib.cleanup_repo(repo_dir)
    return 0


def run_one(repo_dir: Path, phase_groups: Optional[Sequence[Sequence[str]]], args: argparse.Namespace, timestamp: str) -> int:
    """Dispatch one target through phases then iterations in this process.

    v1.5.1 Item 3.1 + 3.2. The worker-side unified path:
      1. If phase_groups set: run them (run_one_phased) — inter-group
         pacing lives there.
      2. If args.iterations set: run them (run_one_iterations) —
         inter-strategy pacing lives there. When phases just ran, the
         bridge pace between the last phase group and the first
         iteration is emitted by run_one_phased (see iterations_follow
         there).
      3. If neither: fall through to single-pass / legacy iteration.
    """
    iterations = list(getattr(args, "iterations", None) or [])
    if phase_groups:
        phased_status = run_one_phased(repo_dir, phase_groups, args, timestamp)
        if phased_status != 0:
            return phased_status
        if iterations:
            return run_one_iterations(
                repo_dir, iterations, args, timestamp, phases_already_ran=True
            )
        return 0
    if iterations:
        return run_one_iterations(repo_dir, iterations, args, timestamp)
    return run_one_singlepass(repo_dir, args, timestamp)


def count_total_bugs(repo_dirs: Sequence[Path]) -> int:
    return sum(lib.count_bug_writeups(repo_dir) for repo_dir in repo_dirs)


def execute_strategy_list(
    args: argparse.Namespace,
    repo_dirs: Sequence[Path],
    strategies: Sequence[str],
    timestamp: str,
) -> int:
    """Run each strategy in ``strategies`` in order, with early stop on zero-gain."""
    chain = " -> ".join(strategies)
    print(f"=== Running iteration strategies: {chain} ===\n")
    for strategy in strategies:
        print("=" * 58)
        print(f"  Strategy: {strategy}")
        print("=" * 58)
        before = count_total_bugs(repo_dirs)
        strategy_args = argparse.Namespace(**vars(args))
        strategy_args.strategy = [strategy]
        status = execute_run(strategy_args, repo_dirs, timestamp=timestamp, suppress_suggestion=True)
        after = count_total_bugs(repo_dirs)
        gained = after - before
        print(f"\n  Strategy {strategy}: {before} -> {after} bugs (+{gained})")
        if status != 0:
            return status
        if gained == 0 and not getattr(args, "_iterations_explicit", False):
            print("  No new bugs found - stopping early (diminishing returns).")
            break
        print("")
    print("\n=== Strategy-list run complete ===")
    print(lib.print_summary(repo_dirs))
    return 0


def display_run_header(args: argparse.Namespace, repo_dirs: Sequence[Path], display_version: str, phase_list: Sequence[str], timestamp: str) -> None:
    print("=== Quality Playbook - Artifact Generation ===")
    print(f"Version:  {display_version or 'unknown'}")
    print(f"Runner:   {args.runner}")
    if args.runner == "copilot":
        print(f"Model:    {args.model or lib.DEFAULT_MODEL}")
    else:
        print(f"Model:    {args.model or '(default)'}")
    print(f"No seeds: {args.no_seeds}  (Phase 0/0b skipped when true)")
    if getattr(args, "no_formal_docs", False):
        print("No formal docs: True  (pre-run reference_docs/ guard suppressed)")
    if getattr(args, "no_stdout_echo", False):
        print("No stdout echo: True  (logboth stdout default disabled)")
    if getattr(args, "verbose", False):
        print("Progress:  verbose  (phase transcript + PROGRESS.md headers stream to stdout)")
    elif getattr(args, "quiet", False):
        print("Progress:  quiet    (monitor suppressed; log file still written in full)")
    else:
        interval = getattr(args, "progress_interval", 2)
        print(f"Progress:  headers  (PROGRESS.md poll every {interval}s)")
    print(f"Parallel: {args.parallel}")
    if getattr(args, "full_run", False):
        print("Mode:     full-run (fresh main run + all four iteration strategies)")
    elif args.next_iteration:
        strategy_display = ",".join(args.strategy)
        print(f"Mode:     next-iteration (strategy: {strategy_display}, builds on existing quality/)")
    elif phase_list:
        print(f"Mode:     phase-by-phase ({','.join(phase_list)}) - separate session per phase with exit gates")
    else:
        print("Mode:     single-prompt (all phases in one session)")
    print("Targets:")
    for repo_dir in repo_dirs:
        print(f"  {repo_dir}")
    print(f"Run ID:   {timestamp}")
    print("")
    print("=== Runner logs (one file per target) ===")
    for repo_dir in repo_dirs:
        print(log_file_for(repo_dir, timestamp))
    print("")


def pid_file_for_parent() -> Path:
    """Return the PID file path for this parent process.

    Each parent uses its own file (``.run_pids.<parent_pid>``) so that
    concurrent parallel launches from different terminals don't overwrite
    each other's worker registrations. ``kill_recorded_processes`` globs
    every matching file to kill workers across all parents.
    """
    return PID_FILE.parent / f"{PID_FILE.name}.{os.getpid()}"


def discover_pid_files() -> List[Path]:
    """Return all per-parent PID files currently on disk."""
    parent = PID_FILE.parent
    if not parent.is_dir():
        return []
    return sorted(parent.glob(f"{PID_FILE.name}.*"))


def write_pid_file(entries: Sequence[Tuple[int, str]]) -> Path:
    """Write this parent's worker PIDs to its own file. Returns the path."""
    path = pid_file_for_parent()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for pid, repo_name in entries:
            handle.write(f"{pid} {repo_name}\n")
    return path


def _pkill_fallback() -> None:
    """Best-effort pattern kill when no PID file is available (e.g. after a crash)."""
    patterns = [
        "bin/run_playbook.py",
        "claude -p",
        "claude --model",
        "gh copilot -p",
    ]
    for pattern in patterns:
        try:
            result = subprocess.run(
                ["pkill", "-f", pattern],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError:
            print("  pkill not available; cannot do pattern-based cleanup")
            return
        if result.returncode == 0:
            print(f"  killed processes matching: {pattern}")
        else:
            print(f"  no processes matched: {pattern}")


def kill_recorded_processes() -> int:
    pid_files = discover_pid_files()
    if not pid_files:
        print("No PID files found. Falling back to pkill:")
        _pkill_fallback()
        return 0

    total_killed = 0
    for pid_file in pid_files:
        print(f"Killing PIDs from {pid_file}:")
        for line in pid_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            pid_text, _, repo_name = line.partition(" ")
            try:
                pid = int(pid_text)
            except ValueError:
                continue
            try:
                if os.name != "nt":
                    os.killpg(pid, signal.SIGTERM)
                else:
                    os.kill(pid, signal.SIGTERM)
                print(f"  kill {pid} [{repo_name}]")
                total_killed += 1
            except ProcessLookupError:
                print(f"  {pid} [{repo_name}] - already exited")
        pid_file.unlink(missing_ok=True)
    if total_killed == 0:
        print("All recorded processes had already exited.")
    return 0


def build_worker_command(args: argparse.Namespace, target_path: str) -> List[str]:
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--sequential"]
    command.append("--claude" if args.runner == "claude" else "--copilot")
    command.append("--no-seeds" if args.no_seeds else "--with-seeds")
    # v1.5.1 Item 3.1: prefer --phase-groups when the operator passed it
    # explicitly OR when sugar (--phase all / --full-run) produced groups.
    # --phase is only propagated when phase-groups was NOT derived.
    phase_groups_raw = getattr(args, "phase_groups_raw", None)
    if phase_groups_raw is not None:
        command.extend(["--phase-groups", _format_phase_groups(phase_groups_raw)])
    elif args.phase:
        command.extend(["--phase", args.phase])
    if args.next_iteration:
        command.append("--next-iteration")
    if getattr(args, "full_run", False):
        command.append("--full-run")
    if args.strategy:
        command.extend(["--strategy", ",".join(args.strategy)])
    if args.model:
        command.extend(["--model", args.model])
    if getattr(args, "no_formal_docs", False):
        command.append("--no-formal-docs")
    if getattr(args, "no_stdout_echo", False):
        command.append("--no-stdout-echo")
    if getattr(args, "verbose", False):
        command.append("--verbose")
    if getattr(args, "quiet", False):
        command.append("--quiet")
    interval = getattr(args, "progress_interval", 2)
    if interval and int(interval) != 2:
        command.extend(["--progress-interval", str(int(interval))])
    # v1.5.1 Item 3.2: unified iteration + pacing flags.
    # v1.5.1 Phase 3 revision (Council FAIL blocker): --full-run is a
    # sugar flag that the worker re-expands on its own side — the
    # parent-side args.iterations population is for dispatch + INDEX.md
    # persistence, but it must NOT leak into the worker argv alongside
    # --full-run. Worker parse_args enforces an `--iterations +
    # --full-run` mutex (Item 3.2 parser check), so emitting both here
    # makes the child exit with an argparse error before doing any work.
    # Mirrors the existing --phase-groups suppression gated on
    # phase_groups_raw is None.
    iterations = getattr(args, "iterations", None)
    if iterations and not getattr(args, "full_run", False):
        command.extend(["--iterations", ",".join(iterations)])
    pace = int(getattr(args, "pace_seconds", 0) or 0)
    if pace > 0:
        command.extend(["--pace-seconds", str(pace)])
    command.append(target_path)
    return command


def wait_for_processes(processes: Sequence[subprocess.Popen], pid_file: Path) -> int:
    failures = 0
    for process in processes:
        if process.wait() != 0:
            failures += 1
    # Remove only this parent's file; peer parents keep their own.
    pid_file.unlink(missing_ok=True)
    return failures


def execute_run(args: argparse.Namespace, repo_dirs: Sequence[Path], timestamp: Optional[str] = None, suppress_suggestion: bool = False) -> int:
    phase_groups = getattr(args, "phase_groups", None)
    # Legacy phase_list kept for display_run_header / suggestions that still
    # key off the flat list. Equivalent in content; derived from phase_groups
    # when present, else from args.phase.
    phase_list = [p for g in phase_groups for p in g] if phase_groups else phase_list_from_mode(args.phase)
    run_timestamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")

    # v1.5.1 Item 3.2: --full-run now produces phase_groups + iterations at
    # parse time and is dispatched through the unified worker-side path
    # (run_one handles phases then iterations under one process + one
    # monitor lifecycle). The legacy self-recursing dispatch that spawned
    # separate workers for phases vs iterations remains reachable only
    # when full_run is true AND the args don't carry the new canonical
    # attributes (defensive — shouldn't happen in practice since parse_args
    # always populates them).
    if getattr(args, "full_run", False) and not phase_groups and not getattr(args, "iterations", None):
        print("=== Full run: fresh main run + all iteration strategies ===\n")
        main_args = argparse.Namespace(**vars(args))
        main_args.full_run = False
        main_args.next_iteration = False
        main_args.strategy = ["gap"]
        main_status = execute_run(main_args, repo_dirs, timestamp=run_timestamp, suppress_suggestion=True)
        if main_status != 0:
            print("\n=== Full run halted: main run reported failures; skipping iterations. ===")
            return main_status
        iter_args = argparse.Namespace(**vars(args))
        iter_args.full_run = False
        iter_args.next_iteration = True
        iter_args.strategy = list(ALL_STRATEGIES)
        return execute_run(iter_args, repo_dirs, timestamp=run_timestamp, suppress_suggestion=suppress_suggestion)

    # Legacy multi-strategy iteration: chain each strategy in order with
    # early stop by spawning a worker per strategy. --iterations (Item 3.2)
    # is the unified in-worker replacement; it's dispatched via run_one.
    if args.next_iteration and len(args.strategy) > 1:
        return execute_strategy_list(args, repo_dirs, args.strategy, timestamp=run_timestamp)

    if args.parallel:
        processes = []
        pid_entries = []
        for repo_dir in repo_dirs:
            kwargs = {}
            if os.name != "nt":
                kwargs["start_new_session"] = True
            command = build_worker_command(args, str(repo_dir))
            process = subprocess.Popen(command, cwd=str(lib.QPB_DIR), **kwargs)
            processes.append(process)
            pid_entries.append((process.pid, repo_dir.name))
        pid_file_path = write_pid_file(pid_entries)
        print(f"PIDs written to {pid_file_path} - stop with: python bin/run_playbook.py --kill\n")
        failures = wait_for_processes(processes, pid_file_path)
        print(f"\n=== Parallel run complete. {failures} failures out of {len(repo_dirs)} targets. ===")
        print(lib.print_summary(repo_dirs))
        if not suppress_suggestion:
            print_suggested_next_command(args, failures_occurred=failures > 0)
        return 1 if failures else 0

    overall_status = 0
    for repo_dir in repo_dirs:
        overall_status = max(overall_status, run_one(repo_dir, phase_groups, args, run_timestamp))
        print("")

    print(lib.print_summary(repo_dirs))
    if not suppress_suggestion:
        print_suggested_next_command(args, failures_occurred=overall_status > 0)
    return overall_status


def print_suggested_next_command(args: argparse.Namespace, failures_occurred: bool = False) -> None:
    if failures_occurred:
        print("  Run finished with errors — inspect quality/control_prompts/ and re-run with --phase <N>")
        return
    runner_flag = " --claude" if args.runner == "claude" else ""
    model_flag = f" --model {shlex.quote(args.model)}" if getattr(args, "model", None) else ""
    interpreter = os.path.basename(sys.executable) if sys.executable else "python"
    script_path = sys.argv[0] if sys.argv and sys.argv[0] else "bin/run_playbook.py"
    invocation = f"{interpreter} {shlex.quote(script_path)}"
    prefix = f"{invocation}{runner_flag}{model_flag}"
    target_args = " ".join(shlex.quote(name) for name in args.targets)
    print("-" * 56)

    # If the user ran a strict subset of phases, the right next step is the
    # remaining phases — NOT an iteration. Iterations only make sense after the
    # full 6-phase cycle has completed. If --phase all was used (or the user
    # covered every phase explicitly), fall through to the iteration logic.
    phase_list = phase_list_from_mode(getattr(args, "phase", None))
    if phase_list:
        all_phases = {"1", "2", "3", "4", "5", "6"}
        ran = set(phase_list)
        remaining = sorted(all_phases - ran, key=int)
        if remaining:
            remaining_spec = ",".join(remaining)
            print("Next phase suggestion:")
            print(f"  {prefix} --phase {remaining_spec} {target_args}".rstrip())
            print("(You can swap --model between phase groups — e.g. Opus for 1-2, Sonnet for 3-6.)")
            print("-" * 56)
            return
        # All six phases covered — fall through to the iteration suggestion.

    if args.next_iteration:
        # Suggestion is based on the successor of the LAST strategy in the list.
        # Single-item lists behave the same as the old single-strategy case.
        last_strategy = args.strategy[-1] if args.strategy else "gap"
        next_name = next_strategy(last_strategy)
        if next_name:
            print("Next iteration suggestion:")
            print(f"  {prefix} --next-iteration --strategy {next_name} {target_args}".rstrip())
        else:
            print("Iteration cycle complete (gap -> unfiltered -> parity -> adversarial).")
            print(f"To start fresh:  {prefix} {target_args}".rstrip())
    else:
        print("Next iteration suggestion:")
        print(f"  {prefix} --next-iteration --strategy gap {target_args}".rstrip())
    print("-" * 56)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.kill:
        return kill_recorded_processes()

    if not ensure_runner_available(args.runner):
        if args.runner == "copilot":
            print("ERROR: 'gh copilot' not available. Install with: gh extension install github/gh-copilot", file=sys.stderr)
        else:
            print("ERROR: 'claude' CLI not found. Install from https://docs.anthropic.com/claude-code", file=sys.stderr)
        return 1

    repo_dirs, warnings, errors = resolve_target_dirs(args.targets)
    for message in warnings:
        print(message, file=sys.stderr)
    for message in errors:
        print(message, file=sys.stderr)
    if errors:
        return 1
    if not repo_dirs:
        print("ERROR: No target directories to run against.", file=sys.stderr)
        return 1

    display_version = lib.detect_repo_skill_version(repo_dirs[0])
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    display_run_header(args, repo_dirs, display_version, phase_list_from_mode(args.phase), timestamp)
    return execute_run(args, repo_dirs, timestamp=timestamp)


if __name__ == "__main__":
    raise SystemExit(main())
