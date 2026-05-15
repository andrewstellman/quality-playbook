"""Python runner for the Quality Playbook.

Invoke with one or more target-directory paths (relative or absolute) or with
no positional args to run against the current working directory. The runner
does not resolve short names against a benchmark folder — every positional
argument is treated literally as a directory path.

Three invocation forms are supported (v1.5.7 fix F-5):

* ``python -m bin.run_playbook <target>`` — package-module form (canonical).
* ``python /path/to/QPB/bin/run_playbook.py <target>`` — direct script form
  (e.g. ``python ../bin/run_playbook.py <target>`` from ``repos/``).
* ``<target>/bin/run_playbook.sh [<target>]`` — wrapper installed into the
  target by ``setup_repos.sh``; auto-discovers the QPB clone via walk-up
  from the wrapper's location (with $QPB_HOME fallback).
"""

from __future__ import annotations

import sys
from pathlib import Path as _Path

# v1.5.7 fix F-5a: allow direct-script invocation
# (`python /path/to/QPB/bin/run_playbook.py <target>`) by ensuring QPB
# root is on sys.path before local imports. Without this, script-style
# invocation hit ImportError on the relative `from . import benchmark_lib`
# imports and the v1.5.4 __main__ guard refused the run. The injection
# is a no-op under `python -m bin.run_playbook` because QPB root is
# already on sys.path in that mode.
sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import io
import os
import platform
import shlex
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from bin import benchmark_lib as lib
from bin import archive_lib
from bin import progress_monitor
from bin import role_map as role_map_lib


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
        epilog=(
            "Default behavior (no flags): runs all 6 phases + all 4 iteration\n"
            "strategies (gap, unfiltered, parity, adversarial). Equivalent to\n"
            "--full-run. v1.5.4 Phase 3.6.6 (B-18a) made this the default; the\n"
            "v1.5.3 default was 'Phase 1 only'.\n"
            "\n"
            "Common overrides:\n"
            "  --phase N             Run a single phase (legacy v1.5.3 behavior\n"
            "                        was --phase 1).\n"
            "  --phase-groups SPEC   Run an explicit phase-group plan.\n"
            "  --strategy <name>     Run a specific iteration with --next-iteration.\n"
            "  --next-iteration      Iterate on an existing quality/ run.\n"
            "\n"
            "Cost: a bare invocation against a typical target runs ~5-10x longer\n"
            "than v1.5.3's legacy default. Use --phase 1 to recover the legacy\n"
            "'explore only' behavior, or --phase 1,2,3,4,5,6 with no\n"
            "--iterations to run all phases without iteration strategies.\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parallel_group = parser.add_mutually_exclusive_group()
    parallel_group.add_argument("--parallel", dest="parallel", action="store_true", default=True, help="Run all targets concurrently (default).")
    parallel_group.add_argument("--sequential", dest="parallel", action="store_false", help="Run targets one after another.")

    # v1.5.7 Phase 6c: runner default resolution chain:
    #   1. Explicit CLI flag (--claude / --copilot / --codex / --cursor)
    #   2. Per-operator config at ~/.qpb/config.json (key "runner")
    #   3. Built-in default "copilot"
    # The argparse default below is the built-in default; if no flag is
    # passed AND the config file has a "runner" key, args.runner is
    # post-processed in execute_run/main per the override layer.
    runner_group = parser.add_mutually_exclusive_group()
    runner_group.add_argument("--claude", dest="runner", action="store_const", const="claude", default="copilot", help="Use claude -p instead of gh copilot.")
    runner_group.add_argument("--copilot", dest="runner", action="store_const", const="copilot", help="Use gh copilot (default).")
    runner_group.add_argument("--codex", dest="runner", action="store_const", const="codex", help="Use codex exec --full-auto instead of gh copilot.")
    runner_group.add_argument("--cursor", dest="runner", action="store_const", const="cursor", help="Use cursor agent --print --force instead of gh copilot (cursor-cli 3.1+).")

    # v1.5.7 Phase 6c: --council-roster override flag. Resolution order:
    #   1. This CLI flag (comma-separated, e.g., "claude-opus-4.7,gpt-5.5,claude-sonnet-4.6")
    #   2. ~/.qpb/config.json "council_members" key
    #   3. bin/council_config.DEFAULT_COUNCIL_MEMBERS (built-in default)
    # Help text intentionally SUPPRESSED — the flag is documented in
    # references/runners_and_models.md; adopters discover it via the docs.
    parser.add_argument(
        "--council-roster",
        dest="council_roster",
        default=None,
        help=argparse.SUPPRESS,
    )

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
    parser.add_argument("--model", help="Runner model override (copilot: gpt-5.5, claude: sonnet/opus/etc, codex: gpt-5-codex/etc).")
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
    # v1.5.6 cluster C (Resolved Question 2 carry-forward): operators
    # who want a hard fail for missing docs can opt in. Default off —
    # code-only mode is still the documented default behavior. Mutually
    # informative with --no-formal-docs (which suppresses the WARN
    # banner for the same code-only-mode case): --require-docs is the
    # opt-IN counterpart to --no-formal-docs's opt-OUT.
    parser.add_argument(
        "--require-docs",
        dest="require_docs",
        action="store_true",
        help=(
            "Abort the run with an `aborted_missing_docs` event when "
            "reference_docs/ is empty at Phase 1 entry, instead of "
            "proceeding in code-only mode (the default). Use for "
            "compliance/policy contexts where docs are mandatory and "
            "a quiet downgrade would mask a process gap. See "
            "references/code-only-mode.md for the trade-off."
        ),
    )
    # v1.5.6 cluster 049: opt-out for the role_map auto-recovery
    # path (default: enabled). Auto-recovery filters too-large
    # role_maps via the deterministic exclude predicate
    # (HARDCODED_EXCLUDES + optional .gitignore/.hgignore parsing)
    # so an agent that walks vendored/build/cache content doesn't
    # discard its substantive Phase 1 work. Set this flag to
    # restore legacy behavior (abort on size violation).
    parser.add_argument(
        "--no-role-map-auto-recovery",
        dest="no_role_map_auto_recovery",
        action="store_true",
        help=(
            "Disable Phase 2 entry-gate auto-recovery for too-large "
            "role_maps. Default behavior (recovery enabled) filters "
            "vendored/build/cache content via the deterministic "
            "exclude predicate and re-validates; this flag restores "
            "legacy behavior of aborting on size violation. Use when "
            "the model is expected to enumerate correctly and any "
            "size violation is a real bug worth surfacing."
        ),
    )
    # v1.5.6 cluster 050: benchmark-mode flag for model-comparison
    # studies. Phase 4 uses a fixed Council roster (per
    # bin/council_config.DEFAULT_COUNCIL_MEMBERS — at v1.5.7 ship:
    # claude-opus-4.7, gpt-5.5, claude-sonnet-4.6) regardless of
    # --model, so any --model X run that completes Phase 4 produces
    # BUGS.md output that mixes X's Phase 1-3 findings with the
    # Council's audit. For SPC analysis or model comparison,
    # phases 4 onward are a contamination confound.
    parser.add_argument(
        "--benchmark-mode",
        dest="benchmark_mode",
        action="store_true",
        help=(
            "Constrain run to phases 1-3 (single-model only). Skips "
            "Phase 4 Council audit and Phase 5 reconciliation. Use "
            "for model-comparison studies where you want clean "
            "per-model output. Mutually exclusive with --full-run / "
            "--next-iteration / --strategy / --iterations (all of "
            "those rely on Council-contaminated artifacts). Forces "
            "--phase 1,2,3."
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
        "--allow-pkill-fallback",
        action="store_true",
        help=(
            "When --kill cannot find PID files, fall back to a workstation-wide "
            "pkill -f match against runner command-line substrings (claude -p, "
            "gh copilot -p, etc.). DEFAULT OFF — opt in only when you're sure "
            "no other interactive Claude or Copilot sessions are running on "
            "this machine, since the substring match cannot distinguish them "
            "from playbook workers (BUG-004 from the v1.5.6 codex recheck)."
        ),
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Target directories to run against (relative or absolute paths). Defaults to the current directory.",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)

    # v1.5.7 Phase 5 / Deliverable 3: opt-out flag for the centralized
    # quality/logs/<run-id>/ layout. With --logs-flat (or the
    # equivalent QPB_LOGS_LEGACY=1 env var), runner-owned logs are
    # written to the v1.5.6 paths byte-identically for adopters with
    # downstream tooling that hasn't migrated. See ai_context/TOOLKIT.md
    # for the migration timeline; the flag is documented but not
    # advertised in --help.
    parser.add_argument(
        "--logs-flat",
        dest="logs_flat",
        action="store_true",
        default=False,
        help=argparse.SUPPRESS,
    )

    # v1.5.4 Phase 3.6.1 Section A.1.a / A.3.a (codex-prevention):
    # operator overrides for the role-map validator and sentinel
    # pre-flight check. Use only when you know your target really
    # requires the bypass; the defaults exist for a reason.
    parser.add_argument(
        "--allow-disallowed-prefix",
        action="append",
        default=[],
        metavar="PREFIX",
        help=(
            "Suppress role-map validation errors for paths starting "
            "with PREFIX (e.g. 'dist/'). Repeatable. Use only when "
            "your target legitimately commits content under a "
            "normally-disallowed prefix. Default: none."
        ),
    )
    parser.add_argument(
        "--max-role-map-entries",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Override the role-map entry-count ceiling (default: "
            "2000). Use only when your target genuinely has more "
            "than 2000 in-scope files; a role map exceeding the "
            "default usually indicates Phase 1 walked .gitignored "
            "content."
        ),
    )
    parser.add_argument(
        "--allow-missing-sentinels",
        action="store_true",
        default=False,
        help=(
            "Proceed despite missing .gitignore !-rule sentinels "
            "(.gitkeep files etc.). Logs a warning per missing "
            "sentinel but does not abort. Use only when you "
            "intentionally removed a sentinel and haven't yet "
            "updated .gitignore."
        ),
    )
    # v1.5.4 Phase 3.6.3 (B-15): cross-version harness fix. When the
    # harness invokes pre-v1.5.2 QPB versions, it injects an explicit
    # no-delegation prefix so older copilot-cli LLMs don't background
    # phases 2-6 to a sub-agent that dies with the parent session.
    # The verified failure mode lived in cross_v1.5.0 / cross_v1.4.6
    # cells until the v1.5.2 prompts were tightened; --prompt-prefix
    # restores the same guard for cells run against the older code.
    parser.add_argument(
        "--prompt-prefix",
        type=str,
        default="",
        metavar="STRING",
        help=(
            "Prepend STRING to every phase prompt. Used by the "
            "cross-version harness to inject explicit no-delegation "
            "guardrails when running pre-v1.5.2 QPB cells; not "
            "intended for direct operator use. Default: empty."
        ),
    )
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


def _apply_qpb_config_overrides(
    args: argparse.Namespace,
    effective_argv: Sequence[str],
) -> None:
    """v1.5.7 Phase 6c: overlay ~/.qpb/config.json values onto args
    for fields the CLI didn't explicitly set.

    The argparse defaults always win when a flag IS explicitly
    passed; the config file fills in fields the operator didn't
    specify on the CLI. The built-in `DEFAULT_COUNCIL_MEMBERS`
    tuple wins when neither CLI nor config-file specifies the
    roster (resolution happens downstream via
    `_active_council_roster()`).
    """
    try:
        from bin import qpb_config
    except ImportError:
        return  # qpb_config module unavailable; argparse defaults stand
    cfg = qpb_config.load_config()
    if not cfg:
        return

    # Runner default override: only when no explicit --claude /
    # --copilot / --codex / --cursor flag was on the CLI.
    runner_flags = {"--claude", "--copilot", "--codex", "--cursor"}
    if not any(flag in effective_argv for flag in runner_flags):
        cfg_runner = cfg.get("runner")
        if isinstance(cfg_runner, str) and cfg_runner in {"claude", "copilot", "codex", "cursor"}:
            args.runner = cfg_runner

    # Council roster override: only when --council-roster wasn't on
    # the CLI. The resolved roster lives on args.council_roster as
    # a comma-joined string OR a list[str]; downstream
    # _active_council_roster() handles both.
    if args.council_roster is None:
        cfg_roster = cfg.get("council_members")
        if isinstance(cfg_roster, list) and cfg_roster:
            args.council_roster = ",".join(cfg_roster)


def _active_council_roster(args: argparse.Namespace) -> tuple[str, ...]:
    """v1.5.7 Phase 6c: resolve the active Council roster.

    Resolution order (most specific first):
      1. --council-roster CLI flag (parsed from args.council_roster).
      2. Config file's `council_members` (overlaid onto args during
         parse_args via _apply_qpb_config_overrides).
      3. bin/council_config.DEFAULT_COUNCIL_MEMBERS (built-in default).
    """
    raw = getattr(args, "council_roster", None)
    if raw:
        members = [m.strip() for m in raw.split(",")]
        members = [m for m in members if m]
        if members:
            try:
                from bin import qpb_config
                for warning in qpb_config.validate_roster(members):
                    print(f"WARN: {warning}", file=sys.stderr)
            except ImportError:
                pass
            return tuple(members)
    from bin.council_config import DEFAULT_COUNCIL_MEMBERS
    return DEFAULT_COUNCIL_MEMBERS


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)

    # v1.5.2 Phase 6: record whether --iterations / --strategy was passed
    # explicitly on the command line. Downstream strategy dispatch checks
    # this to decide whether to honor the zero-gain early-stop.
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    args._iterations_explicit = _mark_iterations_explicit(effective_argv)

    # v1.5.7 Phase 6c: per-operator config overlay (~/.qpb/config.json).
    # Resolution order for fields not explicitly set on the CLI:
    #   1. CLI flag (when explicitly present in effective_argv)
    #   2. Config file value
    #   3. argparse default
    _apply_qpb_config_overrides(args, effective_argv)

    if not args.kill and not args.targets:
        args.targets = ["."]
    if args.worker:
        args.parallel = False

    # v1.5.4 Phase 3.6.6 (B-18a): bare invocation defaults to
    # --full-run. When the operator types
    # `python -m bin.run_playbook <target>` without any phase /
    # iteration flags, run all 6 phases + all 4 iteration strategies
    # synchronously (the same plan --full-run produces). Single-phase
    # / iteration-only modes remain opt-in via --phases / --strategy /
    # --iterations / --next-iteration.
    phase_groups_raw = getattr(args, "phase_groups_raw", None)
    if (
        not args.full_run
        and not args.phase
        and phase_groups_raw is None
        and not args.next_iteration
        and args.iterations is None
        # v1.5.6 cluster 050: --benchmark-mode is also an explicit
        # phase-scope opt-in; the auto-full-run default must not
        # override it. The mutex check below would catch this with
        # a confusing error otherwise.
        and not getattr(args, "benchmark_mode", False)
    ):
        args.full_run = True
        # v1.5.4 Phase 3.7 Fix 1 (Round 8 BLOCK): tag this Namespace
        # so the dispatcher can emit the bare-invocation banner once
        # before the run starts. Operators who explicitly type
        # --full-run won't see the banner.
        args._auto_full_run = True
    else:
        args._auto_full_run = False

    # v1.5.1 Item 3.1 mutex. --phase-groups vs --phase / --full-run are
    # redundant (--phase and --full-run are sugar). --phase-groups vs
    # --next-iteration is allowed (Item 3.2 relies on this).
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
    # v1.5.6 cluster 050: --benchmark-mode forces --phase 1,2,3 and
    # is mutually exclusive with --full-run / --next-iteration /
    # --strategy (non-default) / --iterations. The latter all rely
    # on Council-contaminated artifacts.
    if getattr(args, "benchmark_mode", False):
        if args.phase and args.phase != "1,2,3":
            parser.error(
                "--benchmark-mode and --phase are mutually exclusive "
                "(benchmark-mode forces phases 1,2,3 to skip the Council-"
                "audited Phase 4 onward)."
            )
        if args.full_run:
            parser.error(
                "--benchmark-mode and --full-run are mutually exclusive. "
                "--full-run uses Phase 4-onward Council artifacts; "
                "--benchmark-mode skips Phase 4."
            )
        if args.next_iteration:
            parser.error(
                "--benchmark-mode and --next-iteration are mutually "
                "exclusive. Iterations consume Phase 4-5 Council artifacts."
            )
        if args.iterations is not None:
            parser.error(
                "--benchmark-mode and --iterations are mutually exclusive. "
                "Iterations consume Phase 4-5 Council artifacts."
            )
        if args.strategy != ["gap"]:
            parser.error(
                "--benchmark-mode and --strategy are mutually exclusive. "
                "Strategy is for iterations which consume Phase 4-5 "
                "Council artifacts."
            )
        # Force phase scope.
        args.phase = "1,2,3"
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
            # v1.5.7 BUG-004: list all 6 canonical install layouts
            # (was 3 pre-fix). Order matches lib.SKILL_INSTALL_LOCATIONS
            # which itself matches SKILL_FALLBACK_GUIDE.
            warnings.append(
                f"WARN: No QPB-installed SKILL.md found for {candidate}. "
                "Expected at one of the canonical install layouts: "
                "SKILL.md (root, bootstrap form — must have "
                "`name: quality-playbook` frontmatter), "
                ".claude/skills/quality-playbook/SKILL.md, "
                ".github/skills/SKILL.md, "
                ".cursor/skills/quality-playbook/SKILL.md, "
                ".continue/skills/quality-playbook/SKILL.md, or "
                ".github/skills/quality-playbook/SKILL.md — "
                "the playbook may not be installed there."
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
    ".github/skills/SKILL.md, .cursor/skills/quality-playbook/SKILL.md, "
    ".continue/skills/quality-playbook/SKILL.md, "
    ".github/skills/quality-playbook/SKILL.md. "
    "Resolve reference files using the same documented fallback order."
)


# v1.5.4 F-1 (Bootstrap_Findings 2026-04-30): phase prompt bodies are
# externalized to ``phase_prompts/*.md`` at the QPB repo root so that
# UI-context (skill-direct) and CLI-automation (runner-driven)
# execution modes read from the same single source of truth. Without
# this externalization, an edit to a phase prompt would have to be
# duplicated in two places. See ``phase_prompts/README.md`` for the
# substitution conventions.
PHASE_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "phase_prompts"


def _load_phase_prompt(name: str, **substitutions: str) -> str:
    """Load ``phase_prompts/<name>.md`` and apply optional substitutions.

    Two substitution mechanisms apply, in this order:

    1. ``skill_fallback_guide`` — substituted via ``str.replace()`` so
       the surrounding prompt does NOT need to double-escape every
       literal brace. v1.5.6 BUG-011/012: phase{2..6}.md hardcoded
       ``.github/skills/`` paths; the fix replaces those with a single
       ``{skill_fallback_guide}`` placeholder at the top of each file
       so the runtime-canonical fallback list (six install layouts) is
       the single source of truth. Phase 3 and Phase 5 contain JSON
       code blocks with single ``{`` / ``}`` braces; using
       ``str.replace`` for this placeholder lets those JSON blocks
       remain readable instead of being littered with ``{{``/``}}``.

    2. Remaining substitutions — applied via ``str.format(**...)`` for
       backward compatibility with phase1, single_pass, and iteration
       prompts that use ``{seed_instruction}``, ``{role_taxonomy}``,
       and ``{strategy}`` placeholders. Files that DO go through
       ``.format()`` must double-escape literal braces as ``{{`` /
       ``}}`` per Python's format-string rules. Phase{2..6} go ONLY
       through the ``str.replace`` path, so their JSON code blocks
       continue to use single ``{`` / ``}`` directly.

    When no substitutions are supplied the file is returned verbatim.
    """
    text = (PHASE_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    fallback = substitutions.pop("skill_fallback_guide", None)
    if fallback is not None:
        text = text.replace("{skill_fallback_guide}", fallback)
    if substitutions:
        text = text.format(**substitutions)
    return text


def _role_taxonomy_block() -> str:
    """Build the Phase 1 prompt's role-taxonomy section from
    bin.role_map.ROLE_DESCRIPTIONS so adding a role to that dict
    automatically updates the prompt. v1.5.4 Round 1 Council finding
    C3-1 (single source of truth)."""
    return "\n".join(
        f"- `{role}` — {desc}"
        for role, desc in role_map_lib.ROLE_DESCRIPTIONS.items()
    )


def phase1_prompt(no_seeds: bool) -> str:
    seed_instruction = ""
    if no_seeds:
        seed_instruction = "Skip Phase 0 and Phase 0b entirely - do not look for quality/previous_runs/ (or the legacy quality/runs/) or sibling versioned directories. This is a clean benchmark run. Start directly at Phase 1."
    return _load_phase_prompt(
        "phase1",
        skill_fallback_guide=SKILL_FALLBACK_GUIDE,
        seed_instruction=seed_instruction,
        role_taxonomy=_role_taxonomy_block(),
    )


def phase2_prompt() -> str:
    return _load_phase_prompt("phase2", skill_fallback_guide=SKILL_FALLBACK_GUIDE)


def phase3_prompt() -> str:
    return _load_phase_prompt("phase3", skill_fallback_guide=SKILL_FALLBACK_GUIDE)


def phase4_prompt() -> str:
    return _load_phase_prompt("phase4", skill_fallback_guide=SKILL_FALLBACK_GUIDE)


def phase5_prompt() -> str:
    return _load_phase_prompt("phase5", skill_fallback_guide=SKILL_FALLBACK_GUIDE)


def phase6_prompt() -> str:
    return _load_phase_prompt("phase6", skill_fallback_guide=SKILL_FALLBACK_GUIDE)


def _apply_prompt_prefix(body: str, prefix: str) -> str:
    """v1.5.4 Phase 3.6.3 (B-15): prepend ``prefix`` to ``body`` with a
    blank-line separator. Empty prefix returns body unchanged."""
    if not prefix:
        return body
    return f"{prefix}\n\n{body}"


def build_phase_prompt(
    phase: str, no_seeds: bool, *, prefix: str = ""
) -> str:
    body = {
        "1": phase1_prompt(no_seeds),
        "2": phase2_prompt(),
        "3": phase3_prompt(),
        "4": phase4_prompt(),
        "5": phase5_prompt(),
        "6": phase6_prompt(),
    }[phase]
    return _apply_prompt_prefix(body, prefix)


def single_pass_prompt(no_seeds: bool, *, prefix: str = "") -> str:
    seed_instruction = " Skip Phase 0 and Phase 0b - start directly at Phase 1." if no_seeds else ""
    body = _load_phase_prompt(
        "single_pass",
        skill_fallback_guide=SKILL_FALLBACK_GUIDE,
        seed_instruction=seed_instruction,
    ).rstrip("\n")
    return _apply_prompt_prefix(body, prefix)


def iteration_prompt(strategy: str, *, prefix: str = "") -> str:
    body = _load_phase_prompt(
        "iteration",
        skill_fallback_guide=SKILL_FALLBACK_GUIDE,
        strategy=strategy,
    ).rstrip("\n")
    return _apply_prompt_prefix(body, prefix)


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


def check_phase_gate(
    repo_dir: Path, phase: str, *, args: Optional[argparse.Namespace] = None
) -> GateCheck:
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
        # v1.5.4 Round 1 Council finding A1/B1/C1: Phase 2 gate must
        # also enforce the role-map presence + validity. Without this
        # check the L1 "classifier never wired in" failure mode
        # partially re-emerges — an LLM that writes a long
        # EXPLORATION.md but skips role tagging would otherwise pass
        # Phase 1 with no classification.
        role_map_path = role_map_lib.default_path(repo_dir)
        if not role_map_path.is_file():
            return GateCheck(
                ok=False,
                messages=[
                    "GATE FAIL Phase 2: quality/exploration_role_map.json "
                    "missing. Phase 1 must produce the role map before "
                    "Phase 2 begins. If Phase 1 ran with an LLM that "
                    "skipped role tagging, re-run Phase 1."
                ],
            )
        role_map_data = role_map_lib.load_role_map(role_map_path)
        if role_map_data is None:
            return GateCheck(
                ok=False,
                messages=[
                    f"GATE FAIL Phase 2: {role_map_path} could not be "
                    "loaded as a JSON object. Re-run Phase 1 to "
                    "regenerate it."
                ],
            )
        # v1.5.6 cluster 047 architectural fix: normalize the LLM-
        # written role_map's `breakdown` and `summary` fields by
        # recomputing them from `files[]`. The LLM is responsible for
        # the analytical work (file role tagging in `files[]`); the
        # mechanically-derivable fields (`breakdown` per
        # compute_breakdown, `summary` per summarize_role_map) are
        # owned by the runner. Sonnet-4.6 reliably produced
        # role_maps where the LLM-written summary/breakdown drifted
        # from the strict mechanical contract; this normalization
        # makes the Phase 2 entry-gate's self-consistency checks
        # pass by construction. Backward compat: legacy role_maps
        # already in the canonical shape recompute idempotently.
        normalize_ok, normalize_errs = role_map_lib.normalize_role_map_for_gate(
            role_map_path
        )
        if not normalize_ok:
            joined = "\n".join(f"  - {err}" for err in normalize_errs)
            return GateCheck(
                ok=False,
                messages=[
                    "GATE FAIL Phase 2: quality/exploration_role_map.json "
                    f"could not be normalized for the gate:\n{joined}\n"
                    "  This typically means files[] is missing or malformed; "
                    "re-run Phase 1 to regenerate the role map."
                ],
            )
        # Re-load after normalize so the validator sees the canonical
        # breakdown + summary the runner just wrote.
        role_map_data = role_map_lib.load_role_map(role_map_path)
        # v1.5.4 Phase 3.6.1 Section A.1.a: honour operator overrides
        # for the disallowed-prefix list and the entry-count ceiling.
        allowed_prefixes = (
            frozenset(getattr(args, "allow_disallowed_prefix", None) or ())
        )
        max_entries_override = (
            getattr(args, "max_role_map_entries", None) if args else None
        )
        validation_errors = role_map_lib.validate_role_map(
            role_map_data,
            allowed_disallowed_prefixes=allowed_prefixes,
            max_role_map_entries=max_entries_override,
        )
        # v1.5.6 cluster 049: auto-recovery for too-large role_maps.
        # When an agent walks vendored/build/cache content during
        # Phase 1, the LLM's role_map.files[] count exceeds
        # MAX_ROLE_MAP_ENTRIES and the validator's only complaint
        # is the size cap. Filter via the deterministic exclude
        # predicate (hardcoded excludes + .gitignore/.hgignore
        # parsing — NO git CLI dependency) and re-validate. If the
        # ONLY validation error was the size cap, recovery applies;
        # if other errors are present (disallowed prefixes, role
        # enum violations, etc.) recovery is skipped — the run
        # aborts as today.
        recovery_disabled = bool(getattr(args, "no_role_map_auto_recovery", False))
        if validation_errors and not recovery_disabled:
            # Recovery applies when EVERY validation error is one the
            # filter can address: the size-cap message, or a
            # disallowed-prefix entry (the filter drops those by
            # construction). Other validation errors (missing
            # required fields, schema_version mismatch, malformed
            # percentages) are NOT filterable — abort as today.
            def _filterable(err: str) -> bool:
                return (
                    "entries (limit" in err
                    or "starts with disallowed prefix" in err
                    or "ending with disallowed suffix" in err
                )
            recovery_eligible = (
                validation_errors
                and all(_filterable(e) for e in validation_errors)
            )
            if recovery_eligible:
                recovered, recovery_note = role_map_lib.maybe_recover_role_map(
                    repo_dir, role_map_data
                )
                if recovered is not None:
                    # Persist the filtered role_map; re-normalize so
                    # breakdown + summary reflect the filtered files
                    # list; re-load + re-validate.
                    import json as _json
                    role_map_path.write_text(
                        _json.dumps(recovered, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    norm_ok2, norm_errs2 = role_map_lib.normalize_role_map_for_gate(
                        role_map_path
                    )
                    if norm_ok2:
                        role_map_data = role_map_lib.load_role_map(role_map_path)
                        validation_errors = role_map_lib.validate_role_map(
                            role_map_data,
                            allowed_disallowed_prefixes=allowed_prefixes,
                            max_role_map_entries=max_entries_override,
                        )
                        # Surface the auto-recovery as a WARN
                        # message so adopters see when their model
                        # isn't following Phase 1 enumeration
                        # directives. The WARN is informational —
                        # the gate still passes as long as
                        # validation_errors is empty after
                        # recovery + normalize.
                        messages.append(
                            f"WARN Phase 2: role_map auto-recovered: "
                            f"{recovery_note} "
                            f"(model is not following Phase 1 enumeration "
                            f"directives; substantive Phase 1 work "
                            f"preserved). Pass --no-role-map-auto-recovery "
                            f"to disable this and abort instead."
                        )
        if validation_errors:
            joined = "\n".join(f"  - {err}" for err in validation_errors)
            return GateCheck(
                ok=False,
                messages=[
                    "GATE FAIL Phase 2: quality/exploration_role_map.json "
                    f"failed validation:\n{joined}"
                ],
            )
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
            # v1.5.4 Phase 2.1 (Round 4 finding A3): suppress when
            # Phase 3 was correctly skipped on a no-code target.
            if not _phase3_skipped_sentinel(repo_dir).is_file():
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
            # v1.5.4 Phase 2.1 (Round 4 finding A3): suppress when
            # Phase 3 was correctly skipped on a no-code target —
            # there's no code to find bugs in.
            if not _phase3_skipped_sentinel(repo_dir).is_file():
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
    if runner == "codex":
        # `codex exec --full-auto` reads instructions from stdin when
        # no positional prompt is given (codex-cli 0.125+). Putting
        # the prompt on argv would hit shell command-line length
        # limits on long phase prompts; the caller must pipe the
        # prompt on stdin instead. The "-" sentinel below makes the
        # intent explicit.
        command = ["codex", "exec", "--full-auto"]
        if model:
            command.extend(["-m", model])
        command.append("-")
        return command
    if runner == "cursor":
        # v1.5.4 F-1 (corrected post-bootstrap): `cursor agent
        # --print` reads the prompt on stdin ONLY when no positional
        # arg is given. Unlike codex 0.125+, cursor 3.1.10 does NOT
        # honor `-` as a stdin sentinel — it treats `-` as the
        # literal prompt content (cursor responds with "your last
        # message was only a hyphen, so there isn't a clear task
        # yet"). The fix: pass NO positional arg and pipe the prompt
        # on stdin (the run_prompt site below detects cursor and
        # sets run_kwargs["input"] = prompt). `--force` (alias
        # `--yolo`) skips confirmation prompts for unattended runs.
        # Original bug surfaced in the post-Phase-3.9.1 bootstrap
        # smoke test when `cursor agent --print --force -` aborted
        # Phase 1 with the literal-hyphen response.
        command = ["cursor", "agent", "--print", "--force"]
        if model:
            command.extend(["--model", model])
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


# v1.5.7 Phase 5 / Deliverable 3: centralized log emission. Runner-owned
# log artifacts (playbook log, run_state.jsonl, RUN_MODE.md) now land at
# quality/logs/<run-id>/ rather than scattered across the cell tree.
# Adopters who need the old layout (e.g., tooling that reads
# quality/run_state.jsonl directly without the resolve helper) can pass
# --logs-flat or set QPB_LOGS_LEGACY=1 to restore v1.5.6-byte-identical
# paths. The flag/env are also the safety hatch for partial-migration
# scenarios (e.g., a downstream consumer not yet updated).
_LOG_LAYOUT_CENTRALIZED = "v1.5.7-centralized"
_LOG_LAYOUT_FLAT = "v1.5.6-flat"


def _logs_legacy_mode(args: Optional[argparse.Namespace]) -> bool:
    """Return True when this run should emit logs in the v1.5.6 flat
    layout (quality/run_state.jsonl + scattered playbook logs) instead
    of the v1.5.7 centralized quality/logs/<run-id>/ layout. CLI flag
    --logs-flat (on args) wins over QPB_LOGS_LEGACY=1 env."""
    if args is not None and getattr(args, "logs_flat", False):
        return True
    return os.environ.get("QPB_LOGS_LEGACY") == "1"


def _compute_run_id(timestamp: str) -> str:
    """Convert the runner's display timestamp (`YYYYMMDD-HHMMSS`) into
    a sortable compact UTC ISO-8601 form (`YYYYMMDDTHHMMSSZ`).

    The display timestamp is local-time per `datetime.now()`; we
    re-render it in UTC compact form so the run-id directory sorts
    chronologically across timezones and matches the convention used
    everywhere else in the metrics tree (per
    metrics/regression_replay/SCHEMA.md). For runs where the supplied
    timestamp is already compact UTC (rare; only the regression-replay
    apparatus does this currently), pass through unchanged.
    """
    # Already compact UTC form (YYYYMMDDTHHMMSSZ): pass through.
    if len(timestamp) == 16 and timestamp.endswith("Z") and "T" in timestamp:
        return timestamp
    # Display form (YYYYMMDD-HHMMSS): re-render as UTC compact.
    if len(timestamp) == 15 and timestamp[8] == "-":
        return f"{timestamp[:8]}T{timestamp[9:]}Z"
    # Anything else: best-effort — preserve the timestamp but warn
    # readers via the unconventional shape. Should not occur in
    # production; tests may pass synthetic timestamps.
    return timestamp


def _run_log_dir(
    repo_dir: Path,
    run_id: str,
    *,
    args: Optional[argparse.Namespace] = None,
    create: bool = True,
) -> Path:
    """Return the centralized log directory for a given run.

    New layout: `<repo_dir>/quality/logs/<run-id>/`. With the legacy
    flag, returns `<repo_dir>/quality/` (so callers that append a
    filename produce the v1.5.6-byte-identical path).

    `create=True` (default) ensures the directory exists; pass False
    for read-only callers (e.g., the gate reading via fallback chain).
    """
    if _logs_legacy_mode(args):
        target = repo_dir / "quality"
    else:
        target = repo_dir / "quality" / "logs" / run_id
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def _control_prompts_dir(
    repo_dir: Path,
    *,
    args: Optional[argparse.Namespace] = None,
    timestamp: Optional[str] = None,
    create: bool = True,
) -> Path:
    """v1.5.7 Phase 5 FS-1: return the directory for control-prompt
    transcripts (per-phase input/output txt files).

    Centralized layout: `<repo_dir>/quality/logs/<run-id>/`. Legacy
    layout (or no run_id available): `<repo_dir>/quality/control_prompts/`.

    Callers WITH a timestamp in scope should pass it via `timestamp`.
    Callers WITHOUT a timestamp (e.g., banner-render helpers that
    run before the timestamp is in scope) fall back to the latest
    existing run-id directory under `quality/logs/`; if none exists
    yet, they fall back to the legacy path. This means a banner
    rendered very early in a run may show the legacy path even in
    centralized mode — that's acceptable for read-only display
    purposes (the banner just tells operators where to tail logs).
    """
    if _logs_legacy_mode(args):
        path = repo_dir / "quality" / "control_prompts"
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    if timestamp:
        run_id = _compute_run_id(timestamp)
        return _run_log_dir(repo_dir, run_id, args=args, create=create)
    # No timestamp: best-effort find the most-recent run-id directory
    logs_root = repo_dir / "quality" / "logs"
    if logs_root.is_dir():
        candidates = sorted(
            (p for p in logs_root.iterdir()
             if p.is_dir() and p.name != "latest"),
            reverse=True,
        )
        if candidates:
            return candidates[0]
    # Fall back to legacy path
    path = repo_dir / "quality" / "control_prompts"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _run_state_jsonl_path(
    repo_dir: Path,
    run_id: Optional[str] = None,
    *,
    args: Optional[argparse.Namespace] = None,
    create: bool = True,
) -> Path:
    """Return the write-target path for run_state.jsonl.

    In the centralized layout, the path is
    `<repo_dir>/quality/logs/<run-id>/run_state.jsonl`. In legacy
    layout (or when run_id is None and no other context is available),
    falls back to `<repo_dir>/quality/run_state.jsonl`.
    """
    if _logs_legacy_mode(args) or run_id is None:
        path = repo_dir / "quality" / "run_state.jsonl"
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path
    log_dir = _run_log_dir(repo_dir, run_id, args=args, create=create)
    return log_dir / "run_state.jsonl"


def log_file_for(
    repo_dir: Path,
    timestamp: str,
    *,
    args: Optional[argparse.Namespace] = None,
) -> Path:
    """Return the log path for a given target directory.

    v1.5.7 Phase 5: centralized layout puts the playbook log at
    `<repo_dir>/quality/logs/<run-id>/runner.log`. Legacy layout (via
    --logs-flat or QPB_LOGS_LEGACY=1) restores the v1.5.6 path:
    `{parent}/{name}-playbook-{ts}.log` (sibling-of-cell, not nested).

    The args argument is optional for backward compatibility with
    callers that don't have an argparse Namespace handy (e.g., test
    fixtures). Without args, the env var QPB_LOGS_LEGACY controls
    layout selection.
    """
    if _logs_legacy_mode(args):
        return repo_dir.parent / f"{repo_dir.name}-playbook-{timestamp}.log"
    run_id = _compute_run_id(timestamp)
    # NB: pass create=False so log_file_for stays a pure path computation
    # — callers (configure_logging, _execute_run) mkdir as needed at
    # write time. Eager mkdir here would break tests that construct
    # synthetic paths the filesystem can't accept.
    return _run_log_dir(repo_dir, run_id, args=args, create=False) / "runner.log"


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
    args: Optional[argparse.Namespace] = None,
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
    log_path = log_file_for(repo_dir, timestamp, args=args).resolve()
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
    args: Optional[argparse.Namespace] = None,
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
    # v1.5.7 Phase 5 FS-1: route through _control_prompts_dir so the
    # banner shows the centralized layout path when active. Timestamp
    # isn't available in scope here; the helper's fallback finds the
    # most-recent run-id directory or returns the legacy path.
    transcript_dir = _control_prompts_dir(
        repo_dir, args=args, create=False,
    )
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
        args=args,
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
            # Codex CLI takes the prompt on stdin (its argv carries
            # the `-` sentinel from command_for_runner). Claude and
            # Copilot take the prompt on argv. Detect the codex case
            # by the trailing `-` token.
            run_kwargs = dict(
                cwd=str(repo_dir),
                stdout=out_handle,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            if runner in ("codex", "cursor"):
                run_kwargs["input"] = prompt
            else:
                run_kwargs["stdin"] = subprocess.DEVNULL
            result = subprocess.run(command, **run_kwargs)
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
    if runner == "codex":
        return shutil.which("codex") is not None
    if runner == "cursor":
        return shutil.which("cursor") is not None
    return shutil.which("claude") is not None


def docs_present(repo_dir: Path) -> bool:
    # v1.5.5 BUG-006 follow-up: the canonical operator-supplied docs
    # directory is `reference_docs/` (this is what
    # bin/reference_docs_ingest.py reads). The pre-v1.5.2 layout used
    # `docs_gathered/`, which is still recognized as a fallback so
    # archived benchmarks with that layout don't suddenly report
    # "code-only" — but operator-facing prose now routes new users to
    # `reference_docs/` exclusively.
    if _reference_docs_plaintext(repo_dir / "reference_docs"):
        return True
    return _docs_gathered_has_plaintext(repo_dir)


# v1.5.2: pre-run reference_docs guard.
_REFERENCE_DOCS_PLAINTEXT_EXTS = frozenset({".txt", ".md"})
_REFERENCE_DOCS_SKIPPED = frozenset({"README.md"})


def _reference_docs_plaintext(reference_docs_dir: Path) -> List[Path]:
    """Return plaintext files under reference_docs/ that ingest would consider.

    v1.5.6 fix-up 070 NF-1: this function MUST mirror
    bin/reference_docs_ingest._iter_candidates() in scope (top-level
    files of reference_docs/ plus top-level files of
    reference_docs/cite/), since docs_present(),
    _evaluate_documentation_state(), and formal_docs_guard_banner() all
    consult this function to classify the target's documentation state,
    while ingest() / load_tier4_context() use _iter_candidates() /
    iterdir() respectively. Pre-fix this used rglob('*'), which made
    the three startup surfaces classify a nested-only reference_docs/
    as 'with_docs' while ingest produced an empty manifest — exactly
    the cross-surface coherence failure mode Council fix-up 067 C-6
    was supposed to close. C-7's _iter_candidates() rewrite created
    this asymmetry; 070 NF-1 closes it.
    """
    if not reference_docs_dir.is_dir():
        return []
    files: List[Path] = []
    # Top-level files of reference_docs/.
    for path in sorted(reference_docs_dir.iterdir()):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.name in _REFERENCE_DOCS_SKIPPED:
            continue
        if path.suffix.lower() in _REFERENCE_DOCS_PLAINTEXT_EXTS:
            files.append(path)
    # Top-level files of reference_docs/cite/.
    cite_dir = reference_docs_dir / "cite"
    if cite_dir.is_dir():
        for path in sorted(cite_dir.iterdir()):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            if path.name in _REFERENCE_DOCS_SKIPPED:
                continue
            if path.suffix.lower() in _REFERENCE_DOCS_PLAINTEXT_EXTS:
                files.append(path)
    return files


def _docs_gathered_has_plaintext(repo_dir: Path) -> bool:
    """Return True if the legacy ``docs_gathered/`` directory has at
    least one non-empty recognized-plaintext file (same predicate as
    ``_reference_docs_plaintext`` — `.md`/`.txt` only, README.md and
    dotfiles excluded).

    v1.5.6 fix-up 067 C-6: pre-fix only ``docs_present()`` honored the
    legacy ``docs_gathered/`` fallback; ``_evaluate_documentation_state()``
    and ``formal_docs_guard_banner()`` checked only ``reference_docs/``.
    A target with the legacy layout got contradictory startup messages
    across the three surfaces. The fallback is preserved (per the
    original comment in ``docs_present()``: "so archived benchmarks
    with that layout don't suddenly report 'code-only'") and now
    applied uniformly across all three surfaces.
    """
    docs_dir = repo_dir / "docs_gathered"
    if not docs_dir.is_dir():
        return False
    for f in sorted(docs_dir.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        if f.name in _REFERENCE_DOCS_SKIPPED:
            continue
        if f.suffix.lower() not in _REFERENCE_DOCS_PLAINTEXT_EXTS:
            continue
        if f.stat().st_size > 0:
            return True
    return False


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

    # v1.5.6 fix-up 067 C-6: honor the legacy docs_gathered/ fallback so
    # this banner agrees with docs_present() and _evaluate_documentation_state().
    legacy_has_docs = _docs_gathered_has_plaintext(repo_dir)
    if not reference_docs_dir.is_dir():
        if legacy_has_docs:
            return None
        trigger = f"neither reference_docs/ nor docs_gathered/ contains plaintext at {repo_dir}"
    else:
        plaintext = _reference_docs_plaintext(reference_docs_dir)
        if not plaintext:
            if legacy_has_docs:
                return None
            trigger = f"neither reference_docs/ nor docs_gathered/ contains plaintext at {repo_dir}"
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


# v1.5.6 P3: code-only-mode downgrade.
#
# When `reference_docs/` (and `reference_docs/cite/`) carry no plaintext
# content for a given run, the playbook proceeds in "code-only mode"
# rather than silently producing a low-quality run. The downgrade is
# observable via:
#   - a `documentation_state` event in `quality/run_state.jsonl`
#   - an opening section in `quality/EXPLORATION.md` pointing at
#     `references/code-only-mode.md`
#   - a "Documentation state: code_only" line in `quality/PROGRESS.md`
#
# These helpers are pure (testable in isolation against TemporaryDirectory).
# `run_one_phase` invokes them at phase=="1" entry (state evaluation +
# event + PROGRESS line) and after successful Phase 1 completion
# (EXPLORATION.md prepend, idempotent).

_CODE_ONLY_MARKER = "## Documentation status: code-only mode"
_CODE_ONLY_PROGRESS_LINE = "Documentation state: code_only"


def _evaluate_documentation_state(repo_dir: Path) -> str:
    """Return ``"code_only"`` if neither ``reference_docs/`` nor
    ``reference_docs/cite/`` contains any recognized plaintext file
    (under `_REFERENCE_DOCS_PLAINTEXT_EXTS`); ``"with_docs"`` otherwise.
    """
    refs = repo_dir / "reference_docs"
    if _reference_docs_plaintext(refs):
        return "with_docs"
    # v1.5.6 fix-up 067 C-6: honor the legacy docs_gathered/ fallback so
    # this surface agrees with docs_present() and formal_docs_guard_banner().
    if _docs_gathered_has_plaintext(repo_dir):
        return "with_docs"
    return "code_only"


def _emit_documentation_state_event(
    repo_dir: Path,
    state: str,
    reason: str,
    *,
    args: Optional[argparse.Namespace] = None,
    timestamp: Optional[str] = None,
) -> Optional[Path]:
    """Append a ``documentation_state`` event to
    ``<repo_dir>/quality/[logs/<run-id>/]run_state.jsonl``. Returns the
    path of the file that was written, or None if the write failed
    (the runner must not crash on a logging failure).

    v1.5.7 Phase 5 / Deliverable 3: when args+timestamp are supplied
    and legacy mode is off, writes to
    ``quality/logs/<run-id>/run_state.jsonl``; otherwise (back-compat,
    or --logs-flat) writes to ``quality/run_state.jsonl``."""
    try:
        from bin.run_state_lib import append_event
    except ImportError:
        return None
    run_id = _compute_run_id(timestamp) if timestamp else None
    jsonl_path = _run_state_jsonl_path(repo_dir, run_id, args=args)
    try:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        append_event(
            jsonl_path,
            {
                "event": "documentation_state",
                "ts": _iso_utc_now(),
                "state": state,
                "reason": reason,
            },
        )
        return jsonl_path
    except (OSError, ValueError):
        return None


def _emit_aborted_missing_docs_event(
    repo_dir: Path,
    reason: str,
    *,
    args: Optional[argparse.Namespace] = None,
    timestamp: Optional[str] = None,
) -> Optional[Path]:
    """Append an ``aborted_missing_docs`` event to
    ``<repo_dir>/quality/[logs/<run-id>/]run_state.jsonl``. Used when
    ``--require-docs`` forces an abort instead of the code-only-mode
    downgrade. Same defensive error-handling shape as
    ``_emit_documentation_state_event``: a logging failure must not
    crash the runner before it has a chance to write the
    operator-facing PROGRESS.md error line.
    """
    try:
        from bin.run_state_lib import append_event
    except ImportError:
        return None
    run_id = _compute_run_id(timestamp) if timestamp else None
    jsonl_path = _run_state_jsonl_path(repo_dir, run_id, args=args)
    try:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        append_event(
            jsonl_path,
            {
                "event": "aborted_missing_docs",
                "ts": _iso_utc_now(),
                "reason": reason,
            },
        )
        return jsonl_path
    except (OSError, ValueError):
        return None


_REQUIRE_DOCS_PROGRESS_MARKER = "ERROR: aborted_missing_docs"


def _add_aborted_missing_docs_to_progress(
    progress_md_path: Path, reason: str
) -> bool:
    """Append a clear ``ERROR: aborted_missing_docs`` block to
    PROGRESS.md so the abort is visible to anyone reading the artifact.
    Idempotent — re-runs against an already-marked file are a no-op.
    Returns True on success or no-op; False on write failure.
    """
    try:
        progress_md_path.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if progress_md_path.is_file():
            existing = progress_md_path.read_text(
                encoding="utf-8", errors="replace"
            )
        if _REQUIRE_DOCS_PROGRESS_MARKER in existing:
            return True
        block = (
            f"{_REQUIRE_DOCS_PROGRESS_MARKER} — {reason}\n"
            f"  --require-docs is set but reference_docs/ is empty. "
            f"Either populate reference_docs/ with plaintext "
            f"documentation (.md or .txt) or remove --require-docs "
            f"to fall back to code-only mode "
            f"(see references/code-only-mode.md)."
        )
        with progress_md_path.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write(f"{block}\n")
        return True
    except OSError:
        return False


def _add_documentation_state_to_progress(
    progress_md_path: Path, state: str
) -> bool:
    """Append a 'Documentation state: <state>' line to PROGRESS.md if
    the line isn't already present. Returns True if the line was added
    (or already present), False on write failure. Idempotent."""
    try:
        progress_md_path.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if progress_md_path.is_file():
            existing = progress_md_path.read_text(encoding="utf-8", errors="replace")
        line = f"Documentation state: {state}"
        if line in existing:
            return True
        with progress_md_path.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write(f"{line}\n")
        return True
    except OSError:
        return False


def _inject_code_only_section_into_exploration(exploration_md_path: Path) -> bool:
    """Prepend the code-only-mode section to EXPLORATION.md if not
    already present. Idempotent — calling twice produces the same
    file as calling once.

    Returns True on success or no-op (already present); False on
    write failure or missing source file."""
    if not exploration_md_path.is_file():
        return False
    try:
        original = exploration_md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if _CODE_ONLY_MARKER in original:
        return True
    section = (
        f"{_CODE_ONLY_MARKER}\n"
        "\n"
        "No `reference_docs/` content was found for this run. The playbook "
        "is operating in a documented mode, not a failure — see "
        "[`references/code-only-mode.md`](../../references/code-only-mode.md) "
        "for what to expect and how to upgrade. "
        "The playbook "
        "is operating in **code-only mode** — requirements are derived from "
        "code, comments, defensive patterns, tests, and any inline "
        "documentation. This typically produces fewer requirements and "
        "fewer findings than a run with `reference_docs/` content.\n"
        "\n"
        "See [`references/code-only-mode.md`](../../references/code-only-mode.md) "
        "for details and how to provide documentation for the next run.\n"
        "\n"
        "---\n"
        "\n"
    )
    try:
        exploration_md_path.write_text(section + original, encoding="utf-8")
        return True
    except OSError:
        return False


def _clear_live_quality(quality_dir: Path) -> None:
    """Remove every live child of quality/ except the archive subtrees
    and RUN_INDEX.md (the append-only history).

    v1.5.4 Phase 3.6.2 (B-19, H3 fix): preserves both the current
    archive directory (``previous_runs/``) AND the legacy directory
    (``runs/``) so archives written by older QPB versions survive the
    transition window."""
    if not quality_dir.is_dir():
        return
    preserved = (
        archive_lib.ARCHIVE_DIRNAME,
        archive_lib.LEGACY_ARCHIVE_DIRNAME,
        "RUN_INDEX.md",
    )
    for child in list(quality_dir.iterdir()):
        if child.name in preserved:
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


# v1.5.4 Phase 3.6.1 Section A.3 (codex-prevention): sentinel-file
# preservation. Codex's 2026-04-29 self-audit attempt deleted
# reference_docs/.gitkeep and reference_docs/cite/.gitkeep despite
# explicit `.gitignore !`-rules naming them as exceptions. Pre-flight
# parses the .gitignore for `!`-rules to derive the canonical sentinel
# list at runtime — adding a new sentinel to .gitignore automatically
# extends this check, no hardcoded list to drift.


def _discover_sentinel_files(repo_dir: Path) -> List[Path]:
    """Parse .gitignore !-negations to derive the sentinel-file list.

    Returns repo-relative paths matching `!path/to/.gitkeep`-style
    explicit unignore rules — i.e. concrete file paths.

    Skipped:
      - Patterns containing wildcards (``*``, ``?``, ``[``) — those
        are negation patterns, not single files.
      - Patterns ending with ``/`` — gitignore directory-level
        unignores (e.g. ``!reference_docs/cite/``). The sentinel
        check runs ``is_file()`` and would falsely report directories
        as missing files (Phase 3.9.1 BUG 1, surfaced during the
        2026-04-30 empirical bootstrap test against QPB itself
        where ``!reference_docs/cite/`` AND
        ``!reference_docs/cite/.gitkeep`` both appear in .gitignore).
    """
    gitignore = repo_dir / ".gitignore"
    if not gitignore.is_file():
        return []
    sentinels: List[Path] = []
    for raw in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line.startswith("!"):
            continue
        candidate = line[1:].strip()
        if not candidate:
            continue
        # Skip glob-pattern negations — they don't name a single file.
        if any(ch in candidate for ch in "*?["):
            continue
        # Phase 3.9.1 BUG 1: skip directory-level unignore patterns
        # (trailing slash). A directory is not a sentinel file; the
        # is_file() check in _verify_sentinels would always report
        # it as missing.
        if candidate.endswith("/"):
            continue
        sentinels.append(Path(candidate))
    return sentinels


def _verify_sentinels(repo_dir: Path) -> List[str]:
    """Return missing sentinel files as posix-style strings, or [] if
    all present. v1.5.4 Phase 3.6.1 Section A.3.a."""
    sentinels = _discover_sentinel_files(repo_dir)
    return [
        s.as_posix()
        for s in sentinels
        if not (repo_dir / s).is_file()
    ]


# v1.5.4 Phase 3.6.1 Section A.4 (codex-prevention): source-patching
# structural backstop. Captures QPB source state at run start and
# verifies it unchanged at every phase boundary. An autonomous LLM
# patch to bin/, .github/skills/, agents/, references/, or SKILL.md
# fails the gate with a diagnostic naming the modified files.

_QPB_SOURCE_PATHS = (
    "bin/",
    ".github/skills/",
    "agents/",
    "references/",
    "SKILL.md",
    # v1.5.4 Phase 3.7 Fix 6 (Round 8 HIGH): CLAUDE.md's source-edit
    # lane includes schemas.md and AGENTS.md too. Codex's specific
    # patch was to bin/archive_lib.py (already covered) but a future
    # LLM patching schemas.md (e.g., updating the role-map schema
    # mid-run to make a bogus role map "valid") or AGENTS.md (which
    # the v1.5.4 generator owns) would otherwise slip past the
    # source-unchanged invariant.
    "schemas.md",
    "AGENTS.md",
    # Council Round 2 2026-04-30 P0-4: F-1's externalization made
    # phase_prompts/*.md load-bearing single-source-of-truth runtime
    # prompt content read by both Mode A (skill-direct) and Mode B
    # (runner-driven). A mid-run Phase-N LLM rewriting any
    # phase_prompts/*.md file would shift downstream phases without
    # the SHA256 byte-equality test catching it (that test pins
    # between-commit drift, not within-run mutation). Same class of
    # gap as F-2 closed for AGENTS.md — F-1 introduced a new
    # load-bearing directory and missed the matching invariant
    # update.
    "phase_prompts/",
)


def _qpb_source_baseline_sha(qpb_dir: Path) -> Optional[str]:
    """Return the git HEAD SHA of the QPB checkout (where this module
    lives) at the moment of capture, or ``None`` if not a git repo
    (the structural backstop simply no-ops in that case rather than
    blocking development clones)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=qpb_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def _check_qpb_source_unchanged(
    args: argparse.Namespace, log_file: Path, *, phase: str
) -> bool:
    """Per-phase wrapper around :func:`_verify_qpb_source_unchanged`.

    Reads the baseline SHA stashed on ``args`` by ``execute_run``,
    runs the diff, and on a non-empty result logs the gate-fail
    diagnostic and returns ``False`` (so the caller aborts the run).
    Returns ``True`` when source is unchanged or no baseline was
    captured (e.g. QPB checkout isn't a git repo). v1.5.4 Phase
    3.6.1 Section A.4.b.
    """
    baseline = getattr(args, "_qpb_source_baseline_sha", None)
    if baseline is None:
        return True
    qpb_dir = Path(__file__).resolve().parents[1]
    modified = _verify_qpb_source_unchanged(qpb_dir, baseline)
    if not modified:
        return True
    lib.logboth(
        log_file,
        lib.log(
            f"  GATE FAIL after Phase {phase}: QPB source files modified "
            f"during run: {modified}. Per the source-edit lane discipline, "
            "autonomous patches to QPB source are not permitted during a "
            "run. The patches may be legitimate fixes — but they must be "
            "committed separately via Council review, not applied "
            "mid-run. Aborting."
        ),
    )
    return False


def _verify_qpb_source_unchanged(
    qpb_dir: Path, baseline_sha: Optional[str]
) -> List[str]:
    """Return list of QPB source paths *uncommittedly* modified since
    ``baseline_sha``, or [] when none (or no baseline to compare).

    Checks ``bin/``, ``.github/skills/``, ``agents/``, ``references/``,
    ``SKILL.md``, ``schemas.md``, ``AGENTS.md``, ``phase_prompts/``.
    Non-empty return signals an autonomous source patch — the run must
    abort. v1.5.4 Phase 3.6.1 Section A.4.b.

    v1.5.7 Issue 1 (chi-surfaced false-positive fix): the prior
    implementation ran ``git diff --name-only <baseline_sha>`` which
    diffs the baseline commit against the *working tree* — so a
    legitimate commit that landed on the branch *during* a
    long-running playbook (e.g. an orchestrator-driven fix committed
    between phases) was flagged identically to an autonomous
    uncommitted agent patch, aborting Phase 5 with a false positive.

    The guardrail's true intent is "no *uncommitted* mid-run source
    edits": an authorized mid-run commit went through the commit
    discipline and is fine; an uncommitted working-tree edit to source
    is the violation. Adapted detection (the actual function differs
    from instruction 044's `validate_no_source_edits` pseudocode — it
    is git-diff-based here, not mtime-based, so the per-file HEAD
    filter is applied to the real candidate set, and untracked-file
    detection is added explicitly because `git diff` never surfaces
    untracked paths):

      1. Candidate tracked files = ``git diff --name-only
         <baseline_sha> -- <SOURCE_PATHS>`` (preserves the run-window
         scope for tracked files).
      2. For each candidate, ``git diff-index --quiet HEAD -- <f>``:
         exit 0 ⇒ the file matches the committed HEAD state, i.e. the
         change arrived via a tracked commit during the run — ALLOW.
         Non-zero ⇒ staged/unstaged uncommitted modification, i.e. the
         autonomous-agent-patch case — VIOLATION.
      3. Brand-new untracked files under the source paths
         (``git ls-files --others --exclude-standard``) are violations
         unconditionally — an autonomous agent creating new source
         files is exactly what the guardrail exists to catch
         (conservative default per instruction 044 Task 1 edge case;
         ``git diff-index`` does not report untracked paths so they
         must be detected separately).
    """
    if baseline_sha is None:
        return []

    def _git(args: List[str]) -> Optional[subprocess.CompletedProcess]:
        try:
            return subprocess.run(
                ["git"] + args,
                cwd=qpb_dir,
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, FileNotFoundError):
            return None

    diff_res = _git(
        ["diff", "--name-only", baseline_sha, "--"] + list(_QPB_SOURCE_PATHS)
    )
    if diff_res is None or diff_res.returncode != 0:
        return []
    candidates = [line for line in diff_res.stdout.splitlines() if line.strip()]

    violations: List[str] = []
    for f in candidates:
        # Matches the committed HEAD state ⇒ change arrived via a
        # tracked commit during the run (legitimate; commit discipline
        # is enforced at review time, not by this guardrail). Only an
        # uncommitted modification is an autonomous agent patch.
        head_chk = _git(["diff-index", "--quiet", "HEAD", "--", f])
        if head_chk is not None and head_chk.returncode == 0:
            continue
        if f not in violations:
            violations.append(f)

    others_res = _git(
        ["ls-files", "--others", "--exclude-standard", "--"]
        + list(_QPB_SOURCE_PATHS)
    )
    if others_res is not None and others_res.returncode == 0:
        for f in others_res.stdout.splitlines():
            if f.strip() and f not in violations:
                violations.append(f)

    return violations


def _check_installed_bundle_freshness(
    qpb_root: Path, target: Path
) -> List[str]:
    """Return ``"<subdir>/<name>"`` entries present in QPB source's
    ``references/`` / ``phase_prompts/`` / ``agents/`` but missing
    from ``target``'s installed skill bundle. Empty when fresh, when
    there is no separately-installed bundle, or when the install IS
    the QPB source tree itself (self-audit).

    v1.5.7 Issue 2 (chi-surfaced): a target installed via
    ``setup_repos.sh`` / ``bin.install_skill`` is a point-in-time
    snapshot. A later QPB source addition (e.g.
    ``references/what_just_happened.md``, added in instruction 037)
    does not propagate, so the agent reports the file "isn't present
    in the repo." This is a soft signal — adopters may deliberately
    prune files — so the caller emits a non-fatal WARN, never a gate.

    Detection uses :func:`benchmark_lib.find_installed_skill` (the
    canonical six-layout resolver); the installed bundle directory is
    the parent of the resolved SKILL.md. When that parent resolves to
    the QPB source root itself (root-SKILL.md self-bootstrap layout),
    source and installed dirs coincide and nothing is reported.
    """
    installed_skill = lib.find_installed_skill(target)
    if installed_skill is None:
        return []
    bundle_dir = installed_skill.parent
    missing: List[str] = []
    for subdir in ("references", "phase_prompts", "agents"):
        source_dir = qpb_root / subdir
        installed_dir = bundle_dir / subdir
        if not source_dir.is_dir():
            continue
        try:
            if source_dir.resolve() == installed_dir.resolve():
                # Install IS the source tree (self-audit) — not stale.
                continue
        except OSError:
            pass
        source_files = sorted(source_dir.glob("*.md"))
        if not installed_dir.is_dir():
            missing.extend(f"{subdir}/{sf.name}" for sf in source_files)
            continue
        for sf in source_files:
            if not (installed_dir / sf.name).is_file():
                missing.append(f"{subdir}/{sf.name}")
    return missing


def _prior_run_id_from_live_index(quality_dir: Path) -> Optional[str]:
    """Return the prior run's compact archive timestamp from
    quality/INDEX.md, or None.

    v1.5.4 Phase 3.6.2 (B-19, M8 fix): pins the source field to
    ``run_timestamp_end`` (the Phase-6 finalization timestamp), NOT
    ``run_timestamp_start``. ``_end`` is the meaningful archival
    anchor — it's when the live tree's artifacts were finalized.
    Legacy INDEX files that only carry ``_start`` (or carry
    ``_end == _start`` from the stub) fall through to the
    ``compute_archive_timestamp`` chain via the caller's fallback.
    """
    index_path = quality_dir / "INDEX.md"
    if not index_path.is_file():
        return None
    payload = archive_lib.load_index_payload(index_path)
    if not isinstance(payload, dict):
        return None
    ts = payload.get("run_timestamp_end")
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return archive_lib.compact_from_extended(ts)
    except Exception:  # noqa: BLE001 — defensive parse fallback
        return None


def archive_previous_run(repo_dir: Path, current_run_timestamp: str) -> None:
    """Make room for a new run by archiving whatever live quality/ content remains.

    v1.5.1 unified pipeline: both the Phase-1 entry archive and the
    end-of-Phase-6 archive go through `archive_lib.archive_run()` so
    every archived run carries an `INDEX.md` with §11 fields and emits
    a row into `quality/RUN_INDEX.md`.

    v1.5.4 Phase 3.6.2 (B-19): archives now land under
    ``quality/previous_runs/`` instead of ``quality/runs/``. Both
    directories are checked when detecting "prior run already
    archived" (legacy archives are read-compatible). The archive
    timestamp pins to the prior run's ``run_timestamp_end`` (M8 fix)
    via :func:`archive_lib.compute_archive_timestamp`.

    Branches, in order:

    1. If quality/ has no live content beyond the archive subtrees,
       nothing to do.
    2. If quality/INDEX.md names a prior run whose archive folder
       already exists under either ``previous_runs/<prior-ts>/`` or
       the legacy ``runs/<prior-ts>/``, the prior run was
       auto-archived at its own Phase 6 — just clear the live tree.
    3. Otherwise archive the live tree as a partial prior run. The
       timestamp pins to the prior run's end-time via
       ``compute_archive_timestamp`` (INDEX.run_timestamp_end →
       BUGS.md mtime → current UTC).
    """
    quality_dir = repo_dir / "quality"
    if not quality_dir.is_dir():
        return
    archive_dirs = (
        archive_lib.ARCHIVE_DIRNAME,
        archive_lib.LEGACY_ARCHIVE_DIRNAME,
    )
    if not any(child.name not in archive_dirs for child in quality_dir.iterdir()):
        return

    prior_ts = _prior_run_id_from_live_index(quality_dir)
    if prior_ts and any(
        (quality_dir / d / prior_ts).is_dir() for d in archive_dirs
    ):
        _clear_live_quality(quality_dir)
        return

    archive_ts = prior_ts or archive_lib.compute_archive_timestamp(quality_dir)
    try:
        archive_lib.archive_run(
            repo_dir,
            archive_ts,
            status="partial",
            gate_verdict_override="partial",
        )
    except archive_lib.ArchiveError as exc:
        # v1.5.7 A-1 fix: an ArchiveError means the live tree was NOT
        # successfully preserved (timestamp collision with a *different*
        # run's archive, staging-dir collision, invalid status, missing
        # quality/, ...). Preserving adopter data is more important than
        # tidying up, so do NOT clear the live tree — surface the
        # failure and bail. The next run may write into a non-empty
        # quality/; the operator diagnoses and archives manually.
        sys.stderr.write(
            f"WARN: archive_previous_run could not archive the prior run "
            f"(archive_ts={archive_ts}): {exc}. Live quality/ tree "
            f"preserved at {quality_dir}; the next run may write into a "
            f"non-empty directory. Diagnose and manually rename/archive "
            f"before re-running.\n"
        )
        return  # IMPORTANT: do NOT fall through to _clear_live_quality
    except Exception as exc:  # noqa: BLE001 — defensive: never destroy data
        # v1.5.7 A-1 fix: any other failure also leaves the live tree
        # intact. archive_run touches the filesystem + git; an
        # unexpected OSError/shutil.Error/etc. must not cascade into
        # data loss.
        sys.stderr.write(
            f"WARN: archive_previous_run raised unexpected "
            f"{type(exc).__name__}: {exc}. Live quality/ tree preserved "
            f"at {quality_dir}.\n"
        )
        return
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
        # v1.5.4 Part 1 / Round 1 Council finding C2-1: schema_version
        # routes the gate between target_project_type (1.0 legacy) and
        # target_role_breakdown (2.0 current). Round 2 Step 5 polish:
        # the canonical version lives in bin.role_map so this site and
        # archive_lib.build_index_payload cannot drift apart.
        "schema_version": role_map_lib.INDEX_SCHEMA_VERSION_CURRENT,
        "run_timestamp_start": start_ext,
        "run_timestamp_end": start_ext,
        "duration_seconds": 0,
        "qpb_version": lib.detect_skill_version() or "unknown",
        "target_repo_path": ".",
        "target_repo_git_sha": archive_lib._git_head_sha(repo_dir),
        # v1.5.4 Part 1: target_project_type was retired in favour of the
        # Phase-1 role map. The stub runs BEFORE Phase 1 so the role map
        # does not yet exist; the field is null until write_live_index_final
        # re-renders the INDEX with the produced map.
        "target_role_breakdown": None,
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
    # v1.5.4 Part 1: read the Phase-1 role map (if present) and pass it
    # through; build_index_payload populates target_role_breakdown from
    # whatever the LLM emitted. None ⇒ Phase 1 didn't run for this target.
    role_map = role_map_lib.load_role_map(role_map_lib.default_path(repo_dir))
    payload = archive_lib.build_index_payload(
        repo_dir,
        quality_dir,
        target_repo_path=".",
        target_role_breakdown=role_map_lib.role_breakdown_for_index(role_map),
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


# v1.5.4 Phase 2.1 (Round 4 finding A3): Site 2's Phase 3 skip writes
# this sentinel to quality/ so Phase 4 and Phase 5 gates can
# distinguish "Phase 3 was correctly skipped on a no-code target" from
# "Phase 3 never ran" — without the sentinel the downstream WARNs about
# missing BUGS.md / code_reviews/ are misleading on a pure-skill run.
PHASE3_SKIPPED_SENTINEL_NAME = ".phase3-skipped-no-code-files"


def _phase3_skipped_sentinel(repo_dir: Path) -> Path:
    return repo_dir / "quality" / PHASE3_SKIPPED_SENTINEL_NAME


def _code_review_should_skip(repo_dir: Path) -> Optional[str]:
    """v1.5.4 Phase 2 Site 2: the code-review pipeline (Phase 3) no-ops
    when the Phase-1 role map shows zero ``code`` files. Returns a
    human-readable reason string when Phase 3 should skip, or ``None``
    when it should run normally.

    Pre-Phase-1 invocations (no role map yet) and pre-iteration
    targets that never produced one return ``None`` — Phase 3 runs as
    before so existing behaviour is preserved on any target that
    hasn't yet been classified.

    Asymmetry note (Phase 2.1): Sites 1 and 3 treat "no role map" as
    "skip"; Site 2 treats "no role map" as "run as before" so v1.5.3
    pre-iteration targets keep producing BUGS.md without operator
    intervention. See docs/design/QPB_v1.5.4_Implementation_Plan.md
    Phase 2 for the contract."""
    role_map_path = role_map_lib.default_path(repo_dir)
    if not role_map_path.is_file():
        return None
    role_map_data = role_map_lib.load_role_map(role_map_path)
    if role_map_data is None:
        return None
    if role_map_lib.has_code(role_map_data):
        return None
    return (
        "Phase 3 (Code Review) skipped: role map reports zero `code` "
        "files. The four-pass skill-derivation pipeline still runs "
        "over the skill-side surface."
    )


# v1.5.7 Phase 3 / Deliverable 1: Phase 2 gate-failure artifact
# preservation. When the Phase 2 gate aborts a run (role-map size,
# EXPLORATION.md too short, schema violation, etc.) the agent's
# outputs in quality/ would otherwise be wiped on the NEXT run by
# archive_previous_run() rolling them into previous_runs/<ts>/ as a
# generic partial archive — losing the diagnostic information about
# WHAT the agent produced just before the gate rejected it.
#
# Preservation runs at the gate-failure site (before the run returns),
# renaming the live quality/ to quality.gate-failed-<UTC-timestamp>/
# and dropping a GATE_FAILURE.md marker capturing the violation
# message + phase group + cell + model + runner version.

_GATE_FAILURE_MARKER_FILENAME = "GATE_FAILURE.md"
_GATE_FAILURE_DIRNAME_PREFIX = "quality.gate-failed-"


def _render_gate_failure_marker(
    *,
    phase_group: str,
    cell_name: str,
    timestamp: str,
    runner_version: str,
    model: Optional[str],
    violation_message: str,
) -> str:
    """Return the GATE_FAILURE.md marker body documenting a preserved
    Phase 2 gate failure. See v1.5.7 Design Deliverable 1 for the
    canonical content shape."""
    model_display = model if model else "(default)"
    return (
        "# Phase 2 gate failure — preserved evidence\n"
        "\n"
        "This directory is the contents of `quality/` at the time of a "
        "Phase 2 gate abort. It is preserved as-is for diagnostic "
        "purposes.\n"
        "\n"
        f"- **Phase group**: {phase_group}\n"
        f"- **Cell**: {cell_name}\n"
        f"- **Aborted at (UTC)**: {timestamp}\n"
        f"- **Runner version**: {runner_version}\n"
        f"- **Model**: {model_display}\n"
        "\n"
        "**Gate violation message:**\n"
        "\n"
        f"> {violation_message}\n"
        "\n"
        "The next run on this cell will create a fresh `quality/`. To "
        "clean up this preserved set, simply remove this directory.\n"
    )


def _preserve_quality_on_gate_failure(
    repo_dir: Path,
    phase_group: str,
    gate_messages: Sequence[str],
    args: Optional[argparse.Namespace],
    log_file: Path,
) -> Optional[Path]:
    """Rename `<repo_dir>/quality/` to
    `<repo_dir>/quality.gate-failed-<UTC-ts>/` and drop a
    GATE_FAILURE.md marker capturing the violation message + context.
    Idempotent + safe on empty/missing quality/: returns None if
    nothing was preserved (e.g., quality/ never created), else returns
    the preserved directory path.

    The UTC-timestamp suffix is compact ISO-8601 (``YYYYMMDDTHHMMSSZ``)
    per Phase 1's open-question resolution: always UTC, always sortable
    lexicographically, no local-time variation.

    Composes cleanly with v1.5.6 cluster 049 auto-recovery: when
    recovery succeeds inside check_phase_gate, the gate returns
    ok=True and this preservation path never fires.
    """
    quality = repo_dir / "quality"
    if not quality.exists() or not any(quality.iterdir()):
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    preserved = repo_dir / f"{_GATE_FAILURE_DIRNAME_PREFIX}{ts}"
    # v1.5.7 fix F-2: emit the "Preserved" log line BEFORE the rename so
    # it lands in the about-to-be-renamed quality/logs/<id>/runner.log
    # and therefore appears INSIDE the preserved directory after the
    # rename. Pre-fix, this logboth() ran post-rename and recreated a
    # shadow quality/logs/<id>/ hierarchy at the freshly-vacated path,
    # routing the preservation evidence into a directory operators
    # would never inspect.
    lib.logboth(log_file, lib.log(
        f"  Preserved quality/ at {preserved.name}/ for Phase 2 "
        f"gate-failure diagnosis. Next run will create a fresh quality/."
    ))
    quality.rename(preserved)
    violation_message = "\n> ".join(gate_messages) if gate_messages else "(no gate message captured)"
    marker_body = _render_gate_failure_marker(
        phase_group=phase_group,
        cell_name=repo_dir.name,
        timestamp=ts,
        runner_version=f"v{lib.RELEASE_VERSION}",
        model=getattr(args, "model", None) if args is not None else None,
        violation_message=violation_message,
    )
    (preserved / _GATE_FAILURE_MARKER_FILENAME).write_text(
        marker_body, encoding="utf-8"
    )
    return preserved


def run_one_phase(
    repo_dir: Path,
    phase: str,
    phase_list: Sequence[str],
    args: argparse.Namespace,
    log_file: Path,
    timestamp: str,
) -> bool:
    gate = check_phase_gate(repo_dir, phase, args=args)
    for message in gate.messages:
        lib.logboth(log_file, lib.log(f"  {message}"))
    if not gate.ok:
        # v1.5.7 Phase 3 / Deliverable 1 (+ fix-up F1): preserve
        # quality/ as quality.gate-failed-<UTC-ts>/ so the agent's
        # outputs survive for diagnostic inspection. Scoped to Phase 2
        # gate failures only — the marker text, directory naming, and
        # TOOLKIT.md docs all assume Phase 2. Phase 3/4/5 gate failures
        # do not produce a preservation directory; their post-mortem
        # path is the next-run setup's archive_previous_run roll-up.
        # Composes cleanly with cluster 049 auto-recovery (which
        # returns ok=True when it succeeds, so this branch only fires
        # on actual Phase 2 gate failures the runner cannot recover
        # from).
        if phase == "2":
            _preserve_quality_on_gate_failure(
                repo_dir,
                phase_group=f"Phase {phase}",
                gate_messages=gate.messages,
                args=args,
                log_file=log_file,
            )
        return False

    # v1.5.6 P3: code-only-mode downgrade. Detect at Phase 1 entry so
    # the run state log captures it before any LLM work, and so the
    # post-Phase-1 EXPLORATION.md prepend has a flag to key off.
    documentation_state: Optional[str] = None
    if phase == "1":
        documentation_state = _evaluate_documentation_state(repo_dir)
        if documentation_state == "code_only":
            # v1.5.6 cluster C: --require-docs short-circuits the
            # downgrade. Operators who passed the flag want a hard
            # fail, not a quiet code-only-mode run. Log the abort
            # event + write the operator-facing PROGRESS.md error,
            # then return False (the caller treats it like a gate
            # fail and stops the run before any LLM work).
            if getattr(args, "require_docs", False):
                _emit_aborted_missing_docs_event(
                    repo_dir,
                    "reference_docs/ empty and --require-docs set",
                    args=args,
                    timestamp=timestamp,
                )
                _add_aborted_missing_docs_to_progress(
                    repo_dir / "quality" / "PROGRESS.md",
                    "reference_docs/ empty and --require-docs set",
                )
                lib.logboth(log_file, lib.log(
                    "  ABORT Phase 1: --require-docs is set but "
                    "reference_docs/ is empty (see "
                    "references/code-only-mode.md)."
                ))
                return False
            _emit_documentation_state_event(
                repo_dir, "code_only", "reference_docs/ empty",
                args=args, timestamp=timestamp,
            )
            _add_documentation_state_to_progress(
                repo_dir / "quality" / "PROGRESS.md", "code_only"
            )

    if phase == "3":
        skip_reason = _code_review_should_skip(repo_dir)
        if skip_reason is not None:
            lib.logboth(log_file, lib.log(f"  {skip_reason}"))
            # Drop the Phase-3-skipped sentinel so Phase 4 and Phase 5
            # gates can distinguish "correctly skipped" from "never
            # ran" (Round 4 finding A3).
            sentinel = _phase3_skipped_sentinel(repo_dir)
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text(
                f"{skip_reason}\nat {timestamp}\n", encoding="utf-8"
            )
            _log_phase_completion(repo_dir, phase, log_file, args, timestamp)
            return True
        # v1.5.4 Phase 2.2 (Round 5 Panel B2): Phase 3 IS running this
        # session, so any sentinel left behind by a prior no-code run
        # is stale and would silently suppress Phase 4/5 WARNs about
        # missing code_reviews/ and BUGS.md. Remove it before the LLM
        # is invoked so the rest of the run sees a clean slate.
        _phase3_skipped_sentinel(repo_dir).unlink(missing_ok=True)

    phase_index = phase_list.index(phase) + 1 if phase in phase_list else 1
    prompt = build_phase_prompt(
        phase, no_seeds=args.no_seeds,
        prefix=getattr(args, "prompt_prefix", "") or "",
    )
    output_file = _control_prompts_dir(
        repo_dir, args=args, timestamp=timestamp,
    ) / f"phase{phase}.output.txt"
    lib.logboth(log_file, lib.log(f"  Phase {phase_index}/{len(phase_list) or 1} ({phase_label(phase)}): {repo_dir.name}"))
    # v1.5.6 cluster 050: surface Phase 4's multi-model expansion at
    # phase entry. The Council roster is read programmatically from
    # bin/council_config.py so it stays current if the roster ever
    # changes; no hardcoded names. This banner fires for ALL runs
    # that reach Phase 4 — including normal --full-run — so log
    # readers see the model expansion explicitly.
    if phase == "4":
        try:
            from bin import council_config as _council_config
            roster = ", ".join(_council_config.council_members())
        except (ImportError, AttributeError):
            roster = "(unavailable — see bin/council_config.py)"
        lib.logboth(log_file, lib.log(
            "  ============================================================"
        ))
        lib.logboth(log_file, lib.log(
            "  Phase 4 starting (Spec Audit / Council of Three)."
        ))
        lib.logboth(log_file, lib.log(
            f"  Council roster (NOT --model): {roster}"
        ))
        lib.logboth(log_file, lib.log(
            "  This phase contributes multi-model findings to BUGS.md "
            "regardless"
        ))
        lib.logboth(log_file, lib.log(
            "  of --model selection. For single-model runs, use "
            "--benchmark-mode"
        ))
        lib.logboth(log_file, lib.log(
            "  or --phase 1,2,3 to skip this phase."
        ))
        lib.logboth(log_file, lib.log(
            "  ============================================================"
        ))
    exit_code = run_prompt(repo_dir, prompt, f"phase{phase}", output_file, log_file, args.runner, args.model)
    if exit_code:
        lib.logboth(log_file, lib.log(f"  ABORT Phase {phase}: child runner exited {exit_code}"))
        return False

    # v1.5.4 Phase 3.6.1 Section A.4.b (codex-prevention): structural
    # backstop. If the LLM autonomously patched QPB source mid-run,
    # the post-phase diff against the captured baseline SHA names the
    # modified files and aborts the run.
    if not _check_qpb_source_unchanged(args, log_file, phase=phase):
        return False

    _log_phase_completion(repo_dir, phase, log_file, args, timestamp)

    # v1.5.6 P3: after Phase 1 completes successfully under code-only
    # mode, prepend the documented section to EXPLORATION.md so a
    # reviewer reading the artifact sees the downgrade on first read.
    # Idempotent — re-runs against an already-prepended file are a
    # no-op.
    if phase == "1" and documentation_state == "code_only":
        _inject_code_only_section_into_exploration(
            repo_dir / "quality" / "EXPLORATION.md"
        )

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


def _build_group_prompt(
    phases: Sequence[str], no_seeds: bool, *, prefix: str = ""
) -> str:
    """Concatenate per-phase prompt bodies for a multi-phase group.

    v1.5.1 Item 3.1. The first phase's prompt opens the combined prompt
    with no prefix; subsequent phases are separated by a single
    visible header line so the LLM can tell which phase's work
    it's producing. Per Impl-Plan Open Question 5 (lean: visible,
    minimal), the header is a plain `=== Phase N (Label) ===` string.

    v1.5.4 Phase 3.6.3 (B-15): the optional ``prefix`` keyword is
    applied to the whole combined prompt, not per-phase, so the
    no-delegation guardrail prose appears once at the top instead
    of being repeated.
    """
    parts: List[str] = []
    for i, phase in enumerate(phases):
        # build_phase_prompt is called WITHOUT its prefix kwarg here;
        # we apply the prefix once to the assembled group below.
        body = build_phase_prompt(phase, no_seeds=no_seeds)
        if i > 0:
            parts.append(f"\n\n=== Phase {phase} ({phase_label(phase)}) ===\n\n")
        parts.append(body)
    return _apply_prompt_prefix("".join(parts), prefix)


def _filter_group_for_code_review_skip(
    repo_dir: Path, group: Sequence[str]
) -> Tuple[List[str], Optional[str]]:
    """v1.5.4 Phase 2.1 (Round 4 polish, Step 4): drop Phase 3 from a
    multi-phase group when Site 2's code-review skip applies. Returns
    ``(filtered_group, skip_reason)`` where ``skip_reason`` is non-None
    iff Phase 3 was filtered out (caller should log it once)."""
    if "3" not in group:
        return list(group), None
    reason = _code_review_should_skip(repo_dir)
    if reason is None:
        return list(group), None
    filtered = [p for p in group if p != "3"]
    return filtered, reason


def _group_transcript_path(
    repo_dir: Path,
    phases: Sequence[str],
    *,
    args: Optional[argparse.Namespace] = None,
    timestamp: Optional[str] = None,
) -> Path:
    """Transcript file for a group. Single-phase groups reuse the
    legacy phaseN.output.txt name; multi-phase groups join with '-'
    (e.g. phase3-4.output.txt).

    v1.5.7 Phase 5 FS-1: routes through _control_prompts_dir so the
    new layout lands at quality/logs/<run-id>/. Legacy callers that
    don't yet pass args+timestamp get the most-recent-existing
    fallback (or the v1.5.6 path if no centralized run-id exists).
    """
    suffix = "-".join(phases)
    return _control_prompts_dir(
        repo_dir, args=args, timestamp=timestamp,
    ) / f"phase{suffix}.output.txt"


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

    # v1.5.4 Phase 2.1 (Round 4 polish): on a no-code target, drop
    # Phase 3 from this group BEFORE building the combined prompt so
    # multi-phase invocations like `--phase-groups '2+3'` don't pay an
    # LLM round-trip for code review the role map says to skip. Drop
    # the sentinel for the same reason the single-phase path does so
    # downstream Phase 4 / 5 gates suppress their own WARNs.
    filtered_group, skip_reason = _filter_group_for_code_review_skip(
        repo_dir, group
    )
    if skip_reason is not None:
        lib.logboth(log_file, lib.log(f"  {skip_reason}"))
        sentinel = _phase3_skipped_sentinel(repo_dir)
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(
            f"{skip_reason}\nat {timestamp}\n", encoding="utf-8"
        )
        if not filtered_group:
            # Phase 3 was the only phase in the group; record the
            # phase-3 completion and exit cleanly.
            _log_phase_completion(repo_dir, "3", log_file, args, timestamp)
            return True
        # Otherwise carry on with the surviving phases as the new group.
        group = filtered_group

    if len(group) == 1:
        phase = group[0]
        # Flatten every phase across all groups into the counter list so
        # single-phase groups keep their historical "Phase X/Y" header.
        # v1.5.4 Phase 3 Stage 3 (Round 5 finding B3-F2): when a multi-
        # phase group has been collapsed by the no-code filter (Phase 3
        # dropped because the role map shows zero code), apply the same
        # filter across every group so the X/Y counter reflects the
        # post-filter run shape rather than the pre-filter one. The
        # role-map condition is the same for the whole run, so any
        # other group containing Phase 3 would also drop it.
        if skip_reason is not None:
            flat = [
                p
                for g in phase_groups
                for p in (
                    _filter_group_for_code_review_skip(repo_dir, g)[0]
                )
            ]
        else:
            flat = [p for g in phase_groups for p in g]
        monitor.set_transcript_path(_group_transcript_path(
            repo_dir, [phase], args=args, timestamp=timestamp,
        ))
        return run_one_phase(repo_dir, phase, flat, args, log_file, timestamp)

    # Multi-phase group path.
    # v1.5.4 Phase 2.2 (Round 5 Panel B2): if Phase 3 is in this
    # surviving group, the role map currently reports code surface
    # (otherwise the filter above would have dropped Phase 3). Remove
    # any stale Phase-3-skipped sentinel left by a prior no-code run
    # so downstream Phase 4 / 5 gates don't silently suppress their
    # WARNs against this session's actual artifacts.
    if "3" in group:
        _phase3_skipped_sentinel(repo_dir).unlink(missing_ok=True)
    gate = check_phase_gate(repo_dir, group[0], args=args)
    for message in gate.messages:
        lib.logboth(log_file, lib.log(f"  {message}"))
    if not gate.ok:
        # v1.5.7 Phase 3 / Deliverable 1 (+ fix-up F1): preserve
        # quality/ on gate failure for the multi-phase group path.
        # Scoped to Phase 2 gate failures only (i.e., the group's entry
        # gate is the Phase 2 gate, group[0] == "2"). Same composition
        # with cluster 049 auto-recovery as the single-phase path
        # above.
        if group[0] == "2":
            _preserve_quality_on_gate_failure(
                repo_dir,
                phase_group=f"Phase group {'+'.join(group)}",
                gate_messages=gate.messages,
                args=args,
                log_file=log_file,
            )
        return False

    group_transcript = _group_transcript_path(
        repo_dir, group, args=args, timestamp=timestamp,
    )
    group_transcript.parent.mkdir(parents=True, exist_ok=True)
    # Per-phase transcript stubs + monitor registration. Earlier phases
    # in the group get a small pointer file; the last phase reuses the
    # group transcript path directly so tail + grep keep working.
    for i, phase in enumerate(group):
        per_phase_path = _group_transcript_path(
            repo_dir, [phase], args=args, timestamp=timestamp,
        )
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

    prompt = _build_group_prompt(
        group, no_seeds=args.no_seeds,
        prefix=getattr(args, "prompt_prefix", "") or "",
    )
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

    # v1.5.4 Phase 3.6.1 Section A.4.b: same structural backstop as
    # the single-phase path.
    if not _check_qpb_source_unchanged(args, log_file, phase=group_label):
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
            # v1.5.7 fix F-4z: dropped the v1.5.4 Phase-3.6.4 reorg into
            # quality/workspace/. The README's canonical layout is
            # top-level quality/<name>/, and the reshape was training
            # iter-N agents to write to non-canonical workspace/ paths
            # by reshaping the tree they then learned from. The Phase 6
            # gate now fails loudly if quality/workspace/ exists with
            # content (see quality_gate.check_no_workspace_dir).
            # v1.5.4 Phase 3.6.5 (B-17): generate per-project AGENTS.md
            # for an agent dropped into the repo afterward. Operator-
            # authored AGENTS.md (no QPB sentinel) is preserved with a
            # WARN; QPB-generated copies regenerate cleanly.
            try:
                outcome = _safe_write_agents_md(
                    repo_dir / "AGENTS.md",
                    _generate_agents_md_content(repo_dir),
                )
                lib.logboth(
                    log_file,
                    lib.log(f"  AGENTS.md {outcome}"),
                )
            except Exception as exc:  # noqa: BLE001 — log + continue
                lib.logboth(
                    log_file,
                    lib.log(f"  WARN AGENTS.md generation skipped: {exc}"),
                )
            try:
                archive_lib.archive_run(
                    repo_dir,
                    timestamp,
                    status="success",
                    gate_verdict_override="pass",
                )
            except archive_lib.ArchiveError as exc:
                lib.logboth(log_file, lib.log(f"  WARN archive_run skipped: {exc}"))


# v1.5.7 fix F-4z: removed _finalize_quality_layout, _WORKSPACE_DIRS,
# and _WORKSPACE_FILE_GLOBS. The v1.5.4 Phase 3.6.4 reshape moved
# intermediate artifacts under quality/workspace/, but the README's
# canonical layout is top-level quality/<name>/, and the runner-side
# reshape was training iter-N agents to write to non-canonical
# workspace/ paths (the iter-1 agent wrote to top-level, the runner
# reshaped, and the iter-2 agent then learned the workspace/ layout
# from the reshaped tree). The Phase 6 gate now enforces top-level
# canonical paths via check_no_workspace_dir.


# v1.5.4 Phase 3.6.5 (B-17): per-project AGENTS.md generation. The
# orchestrator writes a README-shaped AGENTS.md at the target's root
# at the end of Phase 6 so an agent dropped into the repo afterward
# can orient quickly: what's in quality/, what changed, how to
# re-run, where the open issues are.
# v1.5.4 Phase 3.7 Fix 3 (Round 8 HIGH): the sentinel constant carries
# the literal version (so an operator inspecting the file knows which
# QPB version produced it), but detection uses a PREFIX match. v1.5.5+
# will correctly recognise v1.5.4-generated AGENTS.md as QPB-managed
# and regenerate them rather than preserving them as if operator-
# authored. The prefix is the load-bearing part; the version after
# `QPB ` is informational only.
QPB_AGENTS_SENTINEL_PREFIX = "<!-- generated by QPB"
QPB_AGENTS_SENTINEL = f"{QPB_AGENTS_SENTINEL_PREFIX} v1.5.4 -->"


def _safe_write_agents_md(target_path: Path, content: str) -> str:
    """Write AGENTS.md at ``target_path`` while respecting
    operator-authored content.

    Returns one of:
      - ``"wrote"``        — no prior file; created fresh.
      - ``"regenerated"``  — existing file carried the
                             ``QPB_AGENTS_SENTINEL_PREFIX`` on one of
                             the first 5 non-empty lines (any QPB
                             version); refreshed in place with the
                             current version's full sentinel.
      - ``"preserved"``    — existing file lacked the QPB prefix
                             (operator-authored); left untouched and
                             a WARN line was emitted.

    v1.5.4 Phase 3.6.5 (B-17, H5 fix): the sentinel-on-first-lines
    discipline lets operators author their own AGENTS.md without
    losing it to a re-run. To opt back into QPB-managed
    regeneration, move the operator file aside (e.g. to
    ``AGENTS.qpb-preserved.md``) and re-run.

    v1.5.4 Phase 3.7 Fix 3 (Round 8 HIGH): detection matches on the
    ``QPB_AGENTS_SENTINEL_PREFIX`` rather than the literal v1.5.4
    string, so cross-version regeneration works (v1.5.5 detecting
    v1.5.4-generated files as QPB-managed; v1.5.4 detecting a
    hypothetical v1.5.5-generated file the same way).
    """
    if target_path.is_file():
        existing = target_path.read_text(encoding="utf-8", errors="ignore")
        head_lines = [
            ln for ln in existing.splitlines() if ln.strip()
        ][:5]
        if not any(QPB_AGENTS_SENTINEL_PREFIX in ln for ln in head_lines):
            print(
                f"WARN: AGENTS.md exists at {target_path} and appears "
                "operator-authored (no QPB sentinel in the first 5 "
                "non-empty lines). Preserving existing file. To opt "
                "into QPB-managed regeneration, move your AGENTS.md "
                "aside (e.g., AGENTS.qpb-preserved.md) and re-run.",
                file=sys.stderr,
            )
            return "preserved"
        outcome = "regenerated"
    else:
        outcome = "wrote"
    body = content if content.endswith("\n") else content + "\n"
    if not body.lstrip().startswith(QPB_AGENTS_SENTINEL_PREFIX):
        body = f"{QPB_AGENTS_SENTINEL}\n{body}"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(body, encoding="utf-8")
    return outcome


def _extract_exploration_narrative(quality_dir: Path) -> str:
    """Pull the architecture / domain narrative excerpt from
    EXPLORATION.md. v1.5.4 Phase 3.6.5 (M9 fix): the AGENTS.md
    "What this is" section needs more than the role-map percentages
    — operators want the architectural framing the LLM produced.

    Heuristic: find the first heading-section whose title contains
    'architecture', 'domain', or 'stack' (case-insensitive); return
    up to 800 characters of body text. Fall back to the first
    non-empty paragraph if no such heading exists. Returns "" when
    EXPLORATION.md is absent.
    """
    path = quality_dir / "EXPLORATION.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    import re as _re
    pat = _re.compile(
        r"^#+\s+([^\n]*(?:architect|domain|stack)[^\n]*)\n(.*?)(?=^#+\s|\Z)",
        _re.IGNORECASE | _re.MULTILINE | _re.DOTALL,
    )
    m = pat.search(text)
    if m:
        body = m.group(2).strip()
    else:
        # First non-empty paragraph after the title.
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        body = paragraphs[1] if len(paragraphs) > 1 else (paragraphs[0] if paragraphs else "")
    if len(body) > 800:
        body = body[:800].rsplit(" ", 1)[0] + " …"
    return body


def _extract_deferred_bugs(quality_dir: Path) -> list:
    """Return BUG entries from BUGS.md whose disposition is
    'deferred', for inclusion in AGENTS.md's Caveats section.
    Each entry is (bug_id, title)."""
    path = quality_dir / "BUGS.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    import re as _re
    out: list = []
    headings = list(_re.finditer(
        r"^###\s+(BUG-[A-Za-z0-9]+)(?:\s*[:.\-]\s*(.+))?$",
        text,
        _re.MULTILINE,
    ))
    for i, match in enumerate(headings):
        bug_id = match.group(1)
        title = (match.group(2) or "").strip()
        # Section runs from this heading's end to the next BUG heading
        # (or EOF). Bounding the search per-bug prevents disposition
        # lines from a later bug bleeding into this one's match.
        section_start = match.end()
        section_end = (
            headings[i + 1].start() if i + 1 < len(headings) else len(text)
        )
        section = text[section_start:section_end]
        if _re.search(
            r"(?im)^\s*-?\s*\*?\*?\s*Disposition\*?\*?\s*[:\-]\s*deferred",
            section,
        ):
            out.append((bug_id, title or "(no title)"))
    return out


def _generate_agents_md_content(repo_dir: Path) -> str:
    """Assemble the AGENTS.md body. Pulls role-map summary,
    EXPLORATION narrative, REQ/BUG counts, gate verdict, and deferred
    BUG list. v1.5.4 Phase 3.6.5 (B-17)."""
    quality = repo_dir / "quality"
    role_map_data = role_map_lib.load_role_map(role_map_lib.default_path(repo_dir))
    summary = (
        role_map_lib.summarize_role_map(role_map_data)
        if role_map_data is not None
        else None
    )
    pcts = (summary or {}).get("percentages") or {}

    # Counts from INDEX (best-effort; INDEX may be the stub).
    index_path = quality / "INDEX.md"
    req_count = 0
    bug_count = 0
    gate_verdict = "unknown"
    if index_path.is_file():
        payload = archive_lib.load_index_payload(index_path)
        if isinstance(payload, dict):
            summary_block = payload.get("summary") or {}
            reqs = summary_block.get("requirements") or {}
            if isinstance(reqs, dict):
                req_count = sum(
                    int(v) for v in reqs.values() if isinstance(v, int)
                )
            bugs = summary_block.get("bugs") or {}
            if isinstance(bugs, dict):
                # Severity-only sum (matches RUN_INDEX convention).
                bug_count = sum(
                    int(bugs.get(s, 0))
                    for s in ("HIGH", "MEDIUM", "LOW")
                    if isinstance(bugs.get(s, 0), int)
                )
            gate_verdict = str(summary_block.get("gate_verdict") or "unknown")

    narrative = _extract_exploration_narrative(quality)
    deferred = _extract_deferred_bugs(quality)

    lines: list = []
    lines.append(f"{QPB_AGENTS_SENTINEL}")
    lines.append("")
    lines.append("# AGENTS.md")
    lines.append("")
    lines.append(
        "Per-project orientation for agents working on this repository "
        "after a Quality Playbook run."
    )
    lines.append("")
    lines.append("## What this is")
    lines.append("")
    if summary:
        lines.append(f"- Files in scope: **{summary.get('file_count', 0)}**")
        lines.append(
            f"- Surface mix: skill {pcts.get('skill_share', 0.0):.0%} / "
            f"code {pcts.get('code_share', 0.0):.0%} / "
            f"tool {pcts.get('tool_share', 0.0):.0%} / "
            f"other {pcts.get('other_share', 0.0):.0%}"
        )
        lines.append(f"- Role-map provenance: `{summary.get('provenance', 'unknown')}`")
    else:
        lines.append(
            "- (No role map present — Phase 1 has not yet produced "
            "`quality/exploration_role_map.json`.)"
        )
    lines.append(f"- Requirements derived: **{req_count}**")
    lines.append(f"- Bugs surfaced: **{bug_count}**")
    lines.append(f"- Gate verdict: **{gate_verdict}**")
    lines.append("")
    if narrative:
        lines.append("### Architecture / domain (excerpt from EXPLORATION.md)")
        lines.append("")
        lines.append(narrative)
        lines.append("")
    lines.append("## Read first")
    lines.append("")
    lines.append("- `quality/REQUIREMENTS.md` — derived behavioral requirements + use cases.")
    lines.append("- `quality/BUGS.md` — every defect surfaced this run, with disposition.")
    lines.append("- `quality/EXPLORATION.md` — the architectural framing Phase 1 produced.")
    lines.append("- `quality/INDEX.md` — run metadata (timestamps, gate verdict, role breakdown).")
    lines.append(
        "- `quality/exploration_role_map.json` — per-file role tagging "
        "that drives Phase 2 wiring."
    )
    lines.append("- `quality/writeups/BUG-<id>.md` — per-bug writeups.")
    lines.append("- `quality/patches/` — fix and regression-test patches.")
    lines.append("- `quality/code_reviews/`, `quality/spec_audits/`, `quality/results/`, `quality/control_prompts/`, `quality/mechanical/` — intermediate pipeline artifacts.")
    lines.append("- `quality/previous_runs/` — historical archives.")
    lines.append("")
    lines.append("## How to extend the review")
    lines.append("")
    # v1.5.4 Phase 3.7 Fix 4 (Round 8 HIGH): use the actual flag names
    # (positional `.` for the target; `--phase` singular). The earlier
    # template strings referenced --target / --phases which don't
    # exist; every v1.5.4 run produced an AGENTS.md whose extension
    # commands would fail with "unrecognized arguments".
    lines.append("- Re-run a single phase: `python -m bin.run_playbook . --phase <N>`.")
    lines.append(
        "- Run an iteration strategy: `python -m bin.run_playbook . "
        "--strategy <gap|unfiltered|parity|adversarial> --next-iteration`."
    )
    lines.append(
        "- Re-run the gate offline: "
        "`python3 .github/skills/quality_gate.py .` from the target root."
    )
    lines.append("")
    lines.append("## Caveats and known issues")
    lines.append("")
    if deferred:
        for bug_id, title in deferred:
            lines.append(f"- **{bug_id}** — {title} (disposition: deferred)")
    else:
        lines.append(
            "- No bugs were marked `disposition: deferred` in this run."
        )
    lines.append("")
    return "\n".join(lines)


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
        args=args,
    )
    print_startup_banner(repo_dir, log_file, args)
    if not docs_present(repo_dir):
        print(lib.log(f"WARN: {repo_dir.name} - reference_docs/ (and legacy docs_gathered/) missing or empty; proceeding with code-only analysis"))
    if not getattr(args, "no_formal_docs", False):
        banner = formal_docs_guard_banner(repo_dir)
        if banner is not None:
            lib.logboth(log_file, banner, echo=True)

    # v1.5.7 Phase 5 / F-DEAD: emit a run_start event so downstream
    # tooling can identify the run's log_layout (centralized vs flat)
    # and resolve the run-id directory without recomputing it from
    # paths. The schema documents run_start in references/
    # run_state_schema.md; we emit additive fields run_id +
    # log_layout per the v1.5.7 layout discriminator there. Defensive
    # error handling: a logging failure must not crash the runner
    # before it has a chance to run the playbook.
    try:
        from bin.run_state_lib import append_event
        run_id = _compute_run_id(timestamp)
        layout = _LOG_LAYOUT_FLAT if _logs_legacy_mode(args) else _LOG_LAYOUT_CENTRALIZED
        jsonl_path = _run_state_jsonl_path(repo_dir, run_id, args=args)
        append_event(
            jsonl_path,
            {
                "event": "run_start",
                "ts": _iso_utc_now(),
                "runner": getattr(args, "runner", "") or "",
                "playbook_version": lib.RELEASE_VERSION,
                "target_path": str(repo_dir),
                "run_id": run_id,
                "log_layout": layout,
            },
        )
    except (ImportError, OSError, ValueError):
        # Logging failure → continue with the run. Operators can still
        # inspect quality/PROGRESS.md + the playbook log directly.
        pass

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

    _control_prompts_dir(repo_dir, args=args, timestamp=timestamp)
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
    # v1.5.7 Phase 5 FS-4 (follow-on): mirror run_one_singlepass's
    # symlink-update at the phased runner's successful-completion
    # path. The original FS-4 wiring missed this site; reviewer
    # caught it in the Phase 5 fix-up mini-review.
    _update_latest_symlink(repo_dir, timestamp, args, log_file)
    lib.cleanup_repo(repo_dir)
    return 0


def run_one_singlepass(repo_dir: Path, args: argparse.Namespace, timestamp: str) -> int:
    log_file = configure_logging(
        repo_dir,
        timestamp,
        no_stdout_echo=getattr(args, "no_stdout_echo", False),
        args=args,
    )
    print_startup_banner(repo_dir, log_file, args)
    if not docs_present(repo_dir):
        print(lib.log(f"WARN: {repo_dir.name} - reference_docs/ (and legacy docs_gathered/) missing or empty; proceeding with code-only analysis"))
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
        prompt = iteration_prompt(
            strategy_name, prefix=getattr(args, "prompt_prefix", "") or ""
        )
        pass_label = f"iteration-{strategy_name}"
        lib.logboth(log_file, lib.log(f"Starting iteration ({strategy_name}): {repo_dir.name} (runner={args.runner}, building on existing quality/)"))
    else:
        archive_previous_run(repo_dir, timestamp)
        write_live_index_stub(
            repo_dir,
            timestamp,
            **_index_flag_kwargs(args),
        )
        prompt = single_pass_prompt(
            no_seeds=args.no_seeds,
            prefix=getattr(args, "prompt_prefix", "") or "",
        )
        pass_label = "full"
        lib.logboth(log_file, lib.log(f"Starting playbook (single-pass): {repo_dir.name} (runner={args.runner})"))

    control_prompts = _control_prompts_dir(
        repo_dir, args=args, timestamp=timestamp,
    )
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
    # v1.5.7 Phase 5 FS-4: update quality/logs/latest -> <run-id>
    # symlink so operators can `cd quality/logs/latest` to inspect the
    # most recent run. Tolerate symlink-update failure on filesystems
    # that don't support symlinks; the resolver's most-recent-by-name
    # fallback (Source 2 in resolve_run_state_path) covers them.
    _update_latest_symlink(repo_dir, timestamp, args, log_file)
    lib.cleanup_repo(repo_dir)
    return 0


def _update_latest_symlink(
    repo_dir: Path,
    timestamp: str,
    args: argparse.Namespace,
    log_file: Path,
) -> None:
    """v1.5.7 Phase 5 FS-4: update <repo>/quality/logs/latest →
    <run-id> after a successful run. In legacy mode (--logs-flat /
    QPB_LOGS_LEGACY=1) this is a no-op because the legacy layout
    doesn't use the logs/ tree.

    The symlink is RELATIVE (target_is_directory=True; target string
    is just the run-id, not an absolute path) so the cell tree
    remains relocatable. On filesystems that don't support symlinks
    (or where the operation otherwise fails), a warning is logged
    and the function returns — the resolver's most-recent-by-name
    fallback covers operators who care about the "latest" semantics.
    """
    if _logs_legacy_mode(args):
        return
    run_id = _compute_run_id(timestamp)
    logs_root = repo_dir / "quality" / "logs"
    target = logs_root / "latest"
    try:
        if target.is_symlink() or target.exists():
            try:
                target.unlink()
            except OSError:
                # Pre-existing entry we can't remove (perhaps a real
                # directory): bail out gracefully rather than try
                # increasingly destructive removals.
                lib.logboth(log_file, lib.log(
                    f"  Could not update {target}: pre-existing entry "
                    f"can't be removed. Centralized resolver falls "
                    f"back to most-recent-by-name."
                ))
                return
        target.symlink_to(run_id, target_is_directory=True)
    except OSError as exc:
        lib.logboth(log_file, lib.log(
            f"  Could not update quality/logs/latest symlink: {exc}. "
            f"Centralized resolver falls back to most-recent-by-name."
        ))


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
# The six canonical install locations the v1.5.6+ resolver supports
# for the gate script. Order matches SKILL_FALLBACK_GUIDE and
# benchmark_lib.SKILL_INSTALL_LOCATIONS so a single test pins all
# three to the same canonical sequence. v1.5.6 BUG-013 added
# .cursor/skills/quality-playbook/quality_gate.py and
# .continue/skills/quality-playbook/quality_gate.py: the installer
# already supported those AI-tool environments, but the finalizer's
# resolver couldn't find the gate script there, so post-iteration
# verification silently fell through to "gate script not found."
_GATE_INSTALL_LOCATIONS = (
    "quality_gate.py",
    ".claude/skills/quality-playbook/quality_gate.py",
    ".github/skills/quality_gate.py",
    ".cursor/skills/quality-playbook/quality_gate.py",
    ".continue/skills/quality-playbook/quality_gate.py",
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

    # v1.5.5 item B + Council R2 P1.1: mechanical source-edit guardrail.
    # The Codex bootstrap on 2026-05-02 went off-rails in Phase 5 and
    # edited five source files outside quality/ before being killed.
    # Phase 5's job is to write proposed-fix patches to quality/patches/,
    # never to apply them. This block checks the post-condition; if any
    # non-quality/ file was modified during the run, the iteration is
    # downgraded to ABORTED with the violations recorded in both the
    # gate log and PROGRESS.md so the failure is auditable.
    source_edit_violations: list[str] = []
    try:
        from bin.run_state_lib import validate_no_source_edits

        ok, source_edit_violations = validate_no_source_edits(repo_dir)
        if not ok:
            try:
                with gate_log_path.open("a", encoding="utf-8") as handle:
                    handle.write(
                        "\n=== source-edit guardrail (validate_no_source_edits) ===\n"
                        "Non-quality/ files were modified during this run; Phase 5 must "
                        "produce proposed-fix patches in quality/patches/, not apply them. "
                        "Violations:\n"
                    )
                    for path in source_edit_violations:
                        handle.write(f"  - {path}\n")
            except OSError:
                pass
    except Exception as exc:  # noqa: BLE001 — guardrail failure must not crash the run
        try:
            lib.logboth(
                log_file,
                lib.log(f"[finalizer:{label}] source-edit guardrail failed: {type(exc).__name__}: {exc}"),
            )
        except Exception:  # noqa: BLE001
            pass

    if source_edit_violations:
        aborted = True
        joined = ", ".join(source_edit_violations[:5])
        if len(source_edit_violations) > 5:
            joined += f" ... (+{len(source_edit_violations) - 5} more)"
        abort_reason = f"source_edit_violations: {joined}"

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
    if source_edit_violations:
        block_lines.append(
            f"- Source-edit violations: {len(source_edit_violations)} "
            f"(see {receipt_note} for details)"
        )
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
        log_file = log_file_for(repo_dir, timestamp, args=args)
    else:
        log_file = configure_logging(
            repo_dir,
            timestamp,
            no_stdout_echo=getattr(args, "no_stdout_echo", False),
            args=args,
        )
        print_startup_banner(repo_dir, log_file, args)
        if not docs_present(repo_dir):
            print(lib.log(f"WARN: {repo_dir.name} - reference_docs/ (and legacy docs_gathered/) missing or empty; proceeding with code-only analysis"))
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

            prompt = iteration_prompt(
                strategy, prefix=getattr(args, "prompt_prefix", "") or ""
            )
            pass_label = f"iteration-{strategy}"
            output_file = _control_prompts_dir(
                repo_dir, args=args, timestamp=timestamp,
            ) / f"{pass_label}.output.txt"
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
    # v1.5.6 cluster 050: surface --benchmark-mode at run start so
    # operators of model-comparison sweeps can confirm the run is
    # constrained to phases 1-3 (single-model only). This banner
    # echoes BEFORE the standard header so it's the first thing in
    # the log.
    if getattr(args, "benchmark_mode", False):
        model_name = args.model or "(default)"
        print("============================================================")
        print(f"BENCHMARK MODE — phases 1-3 only, single model: {model_name}")
        print("Phase 4 Council audit, Phase 5 reconciliation, and iteration")
        print("strategies are SKIPPED. Output is suitable for clean per-model")
        print("comparison.")
        print("============================================================")
    print("=== Quality Playbook - Artifact Generation ===")
    print(f"Version:  {display_version or 'unknown'}")
    print(f"Runner:   {args.runner}")
    if args.runner == "copilot":
        print(f"Model:    {args.model or lib.DEFAULT_MODEL}")
    elif args.runner == "codex":
        print(f"Model:    {args.model or '(codex config default)'}")
    elif args.runner == "cursor":
        print(f"Model:    {args.model or '(cursor account default)'}")
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
        print(log_file_for(repo_dir, timestamp, args=args))
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


def kill_recorded_processes(allow_pkill_fallback: bool = False) -> int:
    pid_files = discover_pid_files()
    if not pid_files:
        if allow_pkill_fallback:
            print("No PID files found. --allow-pkill-fallback set; running pkill -f:")
            _pkill_fallback()
            return 0
        # BUG-004 (HIGH) from the v1.5.6 codex recheck: pkill -f against
        # substrings like "claude -p" matches every interactive Claude or
        # Copilot session on the workstation, not just playbook workers.
        # Default-off: print the manual-cleanup guidance instead.
        pid_dir = pid_file_for_parent().parent
        print("No PID files found. Refusing workstation-wide pkill cleanup.")
        print("To find playbook workers manually, run:")
        print("  ps -o pid,ppid,command -p $(pgrep -f bin/run_playbook) 2>/dev/null")
        print("  ps -o pid,ppid,command | grep -E 'bin/run_playbook|claude -p|claude --model|gh copilot -p'")
        print(f"PID-file directory: {pid_dir}")
        print("If you're certain no other Claude or Copilot sessions are running on this")
        print("machine, re-run with --kill --allow-pkill-fallback to invoke the legacy pkill path.")
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
    # Workers spawn as ``python -m bin.run_playbook``. v1.5.7 fix F-5a
    # restored script-style invocation as a working form for adopters
    # (via sys.path injection at the top of this module), but workers
    # continue to use the ``-m`` form because it preserves
    # ``__package__ == "bin"`` cleanly and keeps the spawn command
    # uniform across all platforms. The regression pin in
    # bin/tests/test_run_playbook.py::Phase38WorkerInvocationTests
    # catches reversion to script-path spawning, which would also
    # have worked post-F-5a but is gratuitously platform-fragile.
    command = [sys.executable, "-m", "bin.run_playbook", "--worker", "--sequential"]
    runner_flag = {
        "claude": "--claude",
        "codex": "--codex",
        "cursor": "--cursor",  # v1.5.4 F-1: Cursor CLI runner.
    }.get(args.runner, "--copilot")
    command.append(runner_flag)
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
    # v1.5.4 Phase 3.6.3 (B-15): forward the no-delegation prompt prefix
    # to subprocess workers so the cross-version harness's guardrail
    # injection survives the parent → worker dispatch.
    prompt_prefix = getattr(args, "prompt_prefix", "") or ""
    if prompt_prefix:
        command.extend(["--prompt-prefix", prompt_prefix])
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

    # v1.5.4 Phase 3.6.1 Section A.3.a / A.4.b (codex-prevention):
    # pre-flight sentinel check + capture QPB source baseline SHA.
    # The sentinel check aborts the run if any .gitignore !-rule
    # sentinel is missing (operator override: --allow-missing-sentinels).
    # The baseline SHA is stashed on args so per-phase verification
    # can detect autonomous QPB-source patches mid-run.
    qpb_dir = Path(__file__).resolve().parents[1]
    if not getattr(args, "allow_missing_sentinels", False):
        for repo_dir in repo_dirs:
            missing = _verify_sentinels(repo_dir)
            if missing:
                print(
                    "ERROR: Required sentinel files missing in "
                    f"{repo_dir}: {missing}. These files keep tracked "
                    "directories present and must not be deleted. "
                    "Restore with: `git checkout -- " + " ".join(missing) + "`. "
                    "Aborting run.\n\nIf you intended to remove a "
                    "sentinel, update .gitignore to drop the "
                    "corresponding `!`-rule and rerun. Override with "
                    "--allow-missing-sentinels (logs a warning but "
                    "proceeds).",
                    file=sys.stderr,
                )
                return 64  # EX_USAGE
    elif any(_verify_sentinels(rd) for rd in repo_dirs):
        for repo_dir in repo_dirs:
            missing = _verify_sentinels(repo_dir)
            if missing:
                print(
                    f"WARN: --allow-missing-sentinels: missing in "
                    f"{repo_dir}: {missing}. Proceeding per operator override.",
                    file=sys.stderr,
                )
    args._qpb_source_baseline_sha = _qpb_source_baseline_sha(qpb_dir)

    # v1.5.7 Issue 2 (chi-surfaced): warn (non-fatally) when a
    # target's installed skill bundle is missing files the current
    # QPB source carries (stale snapshot from an older setup_repos.sh
    # / install_skill). Adopters who deliberately prune a subset get
    # noise they can ignore — this is never a gate.
    for repo_dir in repo_dirs:
        stale = _check_installed_bundle_freshness(qpb_dir, repo_dir)
        if stale:
            bundle = lib.find_installed_skill(repo_dir)
            bundle_loc = bundle.parent if bundle is not None else repo_dir
            target_name = Path(repo_dir).name
            print(
                f"WARN: installed bundle stale at {bundle_loc}/.\n"
                f"  Missing: {', '.join(stale)}\n"
                f"  To refresh, run: cd repos && ./setup_repos.sh "
                f"{target_name}\n"
                f"  Or: python3 -m bin.install_skill --into {repo_dir} "
                f"--ai-tool <name>",
                file=sys.stderr,
            )

    # v1.5.4 Phase 3.7 Fix 1 (Round 8 BLOCK): bare-invocation banner.
    # When the auto-default-to-full-run fired (operator typed no
    # phase / strategy / iteration / full-run flags), signal the
    # cost change before the run starts so v1.5.3 muscle-memory
    # operators don't sink LLM budget unaware. Only fires once per
    # invocation; explicit --full-run skips the banner.
    if getattr(args, "_auto_full_run", False):
        print(
            "[v1.5.4] Bare invocation defaults to --full-run "
            "(all phases + all iterations).",
            file=sys.stderr,
        )
        print(
            "[v1.5.4] Use --phase 1 for the legacy v1.5.3 'explore only' "
            "behavior. Run starting now.",
            file=sys.stderr,
        )

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
        print_suggested_next_command(
            args, failures_occurred=overall_status > 0, repo_dirs=repo_dirs,
        )
    return overall_status


def print_suggested_next_command(
    args: argparse.Namespace,
    failures_occurred: bool = False,
    repo_dirs: Optional[Sequence[Path]] = None,
) -> None:
    if failures_occurred:
        # v1.5.7 fix F-6: when D1 gate-failure preservation has fired,
        # point the operator at the preserved diagnostics directly
        # instead of at the now-gone quality/ tree. Also drop the stale
        # "cell's" wording (legacy benchmark-harness term — the
        # operator-facing surface uses "repo").
        preserved_hints = []
        if repo_dirs:
            for repo_dir in repo_dirs:
                try:
                    preserved = sorted(repo_dir.glob(f"{_GATE_FAILURE_DIRNAME_PREFIX}*"))
                except OSError:
                    preserved = []
                if preserved:
                    most_recent = preserved[-1]
                    preserved_hints.append(
                        f"{repo_dir.name}/{most_recent.name}/logs/<run-id>/"
                    )
        if preserved_hints:
            joined = ", ".join(preserved_hints)
            print(
                "  Run finished with errors — gate-failure preservation "
                "triggered. Inspect the preserved diagnostics under "
                f"{joined} and re-run with --phase <N> after fixing the "
                "cause."
            )
        else:
            print(
                "  Run finished with errors — inspect the repo's "
                "phase-prompt input/output (under quality/logs/<run-id>/ "
                "for v1.5.7+ centralized layout, quality/control_prompts/ "
                "for --logs-flat / pre-v1.5.7) and re-run with --phase <N>"
            )
        return
    runner_flag = {
        "claude": " --claude",
        "copilot": " --copilot",
        "codex": " --codex",
        "cursor": " --cursor",  # v1.5.4 F-1: Cursor CLI runner.
    }.get(args.runner, "")
    model_flag = f" --model {shlex.quote(args.model)}" if getattr(args, "model", None) else ""
    interpreter = os.path.basename(sys.executable) if sys.executable else "python3"
    # Emit the canonical `python3 -m bin.run_playbook` form in suggested
    # next commands. v1.5.7 fix F-5a also restored the script-style
    # form (`python3 /path/to/QPB/bin/run_playbook.py`) as a working
    # invocation, but the package-module form is shorter and stays
    # consistent with how workers spawn themselves (build_worker_command
    # above). v1.5.6 cluster 044 originally pinned this to fix Bug A.
    invocation = f"{interpreter} -m bin.run_playbook"
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
        return kill_recorded_processes(
            allow_pkill_fallback=getattr(args, "allow_pkill_fallback", False)
        )

    if not ensure_runner_available(args.runner):
        if args.runner == "copilot":
            print("ERROR: 'gh copilot' not available. Install with: gh extension install github/gh-copilot", file=sys.stderr)
        elif args.runner == "codex":
            print("ERROR: 'codex' CLI not found. Install from https://github.com/openai/codex", file=sys.stderr)
        elif args.runner == "cursor":
            print("ERROR: 'cursor' CLI not found. Install from https://cursor.com/cli", file=sys.stderr)
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
    # v1.5.6 cluster 050: write a per-target RUN_MODE.md marker so
    # downstream model-comparison tooling can filter for clean
    # benchmark cells without parsing the runner banner. Fires only
    # for benchmark-mode runs to keep regular runs' quality/ tree
    # clean.
    if getattr(args, "benchmark_mode", False):
        for repo_dir in repo_dirs:
            try:
                _write_run_mode_marker(repo_dir, args, timestamp)
            except OSError:
                pass  # marker is best-effort; runs continue regardless
    return execute_run(args, repo_dirs, timestamp=timestamp)


def _write_run_mode_marker(
    repo_dir: Path, args: argparse.Namespace, timestamp: str
) -> None:
    """v1.5.6 cluster 050: write RUN_MODE.md identifying the current
    run as benchmark-mode (single-model, phases 1-3 only). Downstream
    model-comparison tooling reads this to confirm a cell is clean —
    i.e., not contaminated with Phase 4 Council audit findings.

    v1.5.7 Phase 5 / Deliverable 3: in the centralized layout the
    marker lands at quality/logs/<run-id>/RUN_MODE.md; in the legacy
    layout (--logs-flat / QPB_LOGS_LEGACY=1) it stays at
    quality/RUN_MODE.md byte-identically."""
    run_id = _compute_run_id(timestamp)
    if _logs_legacy_mode(args):
        out_dir = repo_dir / "quality"
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = _run_log_dir(repo_dir, run_id, args=args)
    model = args.model or "(default)"
    runner = args.runner or "(default)"
    content = (
        "# Run mode: benchmark\n"
        "\n"
        "This run was invoked with `--benchmark-mode`, constraining the\n"
        "playbook to phases 1-3 only (Explore + Generate + Code Review).\n"
        "Phase 4 (Spec Audit / Council of Three), Phase 5 (Reconciliation),\n"
        "and iteration strategies are SKIPPED. The output is single-model\n"
        "and suitable for model-comparison studies without Council\n"
        "contamination.\n"
        "\n"
        f"- Run ID: `{timestamp}`\n"
        f"- Runner: `{runner}`\n"
        f"- Model:  `{model}`\n"
        f"- Phase scope: 1,2,3\n"
        f"- Council audit: SKIPPED\n"
        f"- Iteration strategies: SKIPPED\n"
        "\n"
        "(Marker emitted by `bin.run_playbook._write_run_mode_marker`\n"
        "per v1.5.6 cluster 050 design.)\n"
    )
    (out_dir / "RUN_MODE.md").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    # v1.5.7 fix F-5a: the v1.5.4 __main__ guard that refused
    # script-style invocation is removed. The sys.path injection at
    # module top now makes `python /path/to/QPB/bin/run_playbook.py`
    # work via absolute `from bin import ...` imports. The codex
    # incident the guard was added for (2026-04-29 self-audit hit
    # ImportError on the old relative imports and unilaterally patched
    # archive_lib.py) is addressed at the root cause: script-mode
    # now works, so there's no failure mode for codex to "fix".
    raise SystemExit(main())
