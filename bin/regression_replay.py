"""Regression replay apparatus — v1.5.4 Phase 5.

Runs current QPB against historical benchmark targets to measure
recall against the benchmark's historical bug list, then writes a
cell record per ``metrics/regression_replay/SCHEMA.md``.

The apparatus has two modes:

1. **Replay mode** (``--invoke-runner``): the apparatus invokes
   ``python3 -m bin.run_playbook`` against the target with the
   specified phase scope, then reads the produced
   ``<target>/quality/BUGS.md`` as the "current" bug set.
   This is the production path used by Phase 6+ calibration cycles.

2. **Measurement-only mode** (default): the operator points the
   apparatus at an already-existing ``--current-bugs`` BUGS.md path
   and the apparatus only does the parse/match/recall/cell-write
   work. This is the smoke-test and CI path used in Phase 5 and
   for re-measuring an existing cell pair without burning LLM time.

Both modes produce identical cell.json shapes; the difference is
only WHERE the "current" BUGS.md comes from.

The matcher reduces a bug record to its (requirement, file_basename)
spec-basis tuple. BUG-NNN ID renumbering is normal between runs
(LLMs renumber sequentially); file:line ranges shift slightly as
code drifts; the (REQ, file basename) tuple is the stable identity.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

try:
    from bin import benchmark_lib  # type: ignore
except Exception:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from bin import benchmark_lib  # type: ignore


SCHEMA_VERSION = "1.5.4"
DEFAULT_OUTPUT_DIR = Path("metrics/regression_replay")
DEFAULT_NOISE_FLOOR = 0.05


# Regex inventory. Both v1.3-era and v1.5-era BUGS.md shapes are
# supported. The v1.3-era shape uses bold-key fields
# (``- **Requirement:** REQ-NNN``); the v1.5-era shape uses
# plain-key fields (``- Primary requirement: REQ-NNN``). The
# matcher normalizes both.
# Council 2026-04-30 P0-1 (corpus-real-file-coverage):
# - chi-1.5.1 archives use `### BUG-001` with NO colon and NO inline
#   title; the original `:\s+(.*)$` regex matched zero records.
# - bus-tracker-1.5.0 uses bold-key Primary requirement / Location
#   variants (`- **Primary requirement:** REQ-004`,
#   `- **Location:** \`bus_tracker.py:...\``); the original plain-key
#   variants matched zero of those either.
# Tolerant heading: colon + title both optional; bold-key variants
# added for both Primary requirement and Location.
#
# Council Round 2 2026-04-30 P0-3: 15 archive files (chi-1.3.13..16/46,
# express-1.3.14/15/16/21/25, virtio-1.3.13/18/19/21-manual/22) use H2
# `## BUG-NNN` headings. Round 1's `^###` pin missed them — chi-1.3.46
# parsed to 0 records when the real recall is 3. Fix: accept any
# heading depth >=2 (`^##+`). H1 is intentionally excluded so a
# documentation/wishlist `# BUG-NNN` outline doesn't false-positive
# (empirically: 0 archive files use H1, so this is safe).
_BUG_HEADING_RE = re.compile(r"^##+\s+(BUG-\d+)(?::\s+(.*))?$", re.MULTILINE)
_REQ_FIELD_RES = (
    re.compile(r"^-\s+\*\*Requirement:\*\*\s+(\S+)\s*$", re.MULTILINE),
    re.compile(r"^-\s+\*\*Primary requirement:\*\*\s+(\S+)\s*$", re.MULTILINE),
    re.compile(r"^-\s+Primary requirement:\s+(\S+)\s*$", re.MULTILINE),
    re.compile(r"^-\s+Requirement:\s+(\S+)\s*$", re.MULTILINE),
)
_FILE_FIELD_RES = (
    re.compile(r"^-\s+\*\*File:\*\*\s+`([^`]+)`", re.MULTILINE),
    re.compile(r"^-\s+\*\*Location:\*\*\s+`([^`]+)`", re.MULTILINE),
    # Council Round 2 2026-04-30 P0-3 (corpus-extension): chi-1.3.46
    # and virtio-1.3.13 use bold-key `**File:Line:**` (capital-L)
    # variant. Without this, primary_file remained None even after
    # the heading regex fix recognized the records.
    re.compile(r"^-\s+\*\*File:Line:\*\*\s+`([^`]+)`", re.MULTILINE),
    # v1.5.6 (corpus-extension): chi-1.3.45 post-lever records use
    # bold-lowercase `**File:line:**` (lowercase l) variant. Without
    # this regex, every post-lever chi-1.3.45 record's primary_file
    # was None during cycle execution; cycle file-overlap analysis
    # collapsed.
    re.compile(r"^-\s+\*\*File:line:\*\*\s+`([^`]+)`", re.MULTILINE),
    # v1.5.6 (corpus-extension): virtio-1.5.1 post-lever records use
    # `**File:line:**` (lowercase l) WITHOUT backticks around the
    # path, with optional trailing prose like " (compensator);". The
    # regex captures up to the first whitespace, semicolon, comma, or
    # paren so trailing prose doesn't leak into primary_file.
    re.compile(r"^-\s+\*\*File:line:\*\*\s+([^\s`;,()]+)", re.MULTILINE),
    # v1.5.5 item D (corpus-extension): chi-1.5.1 records grew from 9
    # to 16 and the new entries use bold-key `**Citation:**` for the
    # file location instead of `**File:**` / `**Location:**`. Without
    # this regex, every chi-1.5.1 record's primary_file was None and
    # match_key derivation collapsed across the whole archive.
    re.compile(r"^-\s+\*\*Citation:\*\*\s+`([^`]+)`", re.MULTILINE),
    re.compile(r"^-\s+File:line:\s+`([^`]+)`", re.MULTILINE),
    re.compile(r"^-\s+File:\s+`([^`]+)`", re.MULTILINE),
    re.compile(r"^-\s+Location:\s+`?([^`\n]+?)`?\s*$", re.MULTILINE),
)


@dataclass(frozen=True)
class BugRecord:
    """A single ``### BUG-NNN`` record extracted from a BUGS.md file.

    The match key for recall accounting is ``(requirement,
    primary_file)`` — both normalized. ``primary_file`` is the
    basename of the first cited file, with line ranges stripped.
    """

    bug_id: str
    title: str
    requirement: Optional[str]
    primary_file: Optional[str]
    raw_file_field: Optional[str]

    @property
    def match_key(self) -> Optional[Tuple[str, str]]:
        if self.requirement is None or self.primary_file is None:
            return None
        return (self.requirement, self.primary_file)


def _strip_lines(file_field: str) -> str:
    r"""Drop ``:line-range`` suffix from a BUGS.md file citation.

    ``middleware/compress.go:218-220,240-245`` → ``middleware/compress.go``
    ``tree.go:706-745`` → ``tree.go``
    Multi-file citations like ``mux.go:127-133\`, \`mux.go:368-371`` get
    the first file's path; downstream callers use the basename.
    """
    first = file_field.split(",")[0].split("`")[0].strip()
    if ":" in first:
        return first.split(":", 1)[0]
    return first


def parse_bugs_md(path: Path) -> List[BugRecord]:
    """Extract every ``### BUG-NNN`` record from a BUGS.md file.

    Handles both v1.3-era and v1.5-era field-name conventions.
    Records are returned in source order; missing fields are recorded
    as None (the match-key property treats those records as
    unmatched).
    """
    if not path.is_file():
        raise FileNotFoundError(f"BUGS.md not found: {path}")

    text = path.read_text(encoding="utf-8")
    records: List[BugRecord] = []

    headings = list(_BUG_HEADING_RE.finditer(text))
    for i, m in enumerate(headings):
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end]
        bug_id = m.group(1)
        # Council 2026-04-30 P0-1: title group is now optional (the
        # tolerant heading regex makes it None when the heading is
        # bare `### BUG-NNN`, as in chi-1.5.1).
        title = (m.group(2) or "").strip()

        requirement = None
        for req_re in _REQ_FIELD_RES:
            rm = req_re.search(body)
            if rm:
                requirement = rm.group(1).strip()
                break

        raw_file = None
        primary_file = None
        for file_re in _FILE_FIELD_RES:
            fm = file_re.search(body)
            if fm:
                raw_file = fm.group(1).strip()
                stripped = _strip_lines(raw_file)
                primary_file = stripped.rsplit("/", 1)[-1] if stripped else None
                break

        records.append(
            BugRecord(
                bug_id=bug_id,
                title=title,
                requirement=requirement,
                primary_file=primary_file,
                raw_file_field=raw_file,
            )
        )

    return records


@dataclass
class RecallMeasurement:
    """Result of matching current bugs against a historical baseline."""

    historical: List[BugRecord]
    current: List[BugRecord]
    recovered_ids: List[str]   # historical IDs that current matched
    missed_ids: List[str]      # historical IDs that current did not match
    spurious_ids: List[str]    # current IDs that matched no historical bug

    @property
    def recall(self) -> float:
        if not self.historical:
            return 0.0
        return len(self.recovered_ids) / len(self.historical)


def measure_recall(
    historical: Sequence[BugRecord], current: Sequence[BugRecord]
) -> RecallMeasurement:
    """Match current against historical by (requirement, file basename).

    A historical bug is "recovered" if at least one current bug
    shares its match_key. A current bug is "spurious" if it matches
    no historical bug. Bugs with missing match_key never match
    anything (their absence from both sets is the apparatus's
    "no signal" verdict — surface as needed).
    """
    historical_keys: Dict[Tuple[str, str], List[str]] = {}
    for rec in historical:
        key = rec.match_key
        if key is not None:
            historical_keys.setdefault(key, []).append(rec.bug_id)

    current_keys_seen: FrozenSet[Tuple[str, str]] = frozenset(
        rec.match_key for rec in current if rec.match_key is not None
    )

    recovered: List[str] = []
    missed: List[str] = []
    for key, ids in historical_keys.items():
        if key in current_keys_seen:
            recovered.extend(ids)
        else:
            missed.extend(ids)

    spurious: List[str] = []
    for rec in current:
        key = rec.match_key
        if key is None or key not in historical_keys:
            spurious.append(rec.bug_id)

    return RecallMeasurement(
        historical=list(historical),
        current=list(current),
        recovered_ids=sorted(set(recovered)),
        missed_ids=sorted(set(missed)),
        spurious_ids=sorted(set(spurious)),
    )


def _git_sha(repo: Path) -> str:
    """Return ``git rev-parse HEAD`` for ``repo``, empty on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return ""


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _utc_now_path_ts() -> str:
    """Path-friendly UTC timestamp matching the archive convention."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass
class CellInputs:
    """All inputs needed to build a cell record."""

    benchmark: str
    historical_qpb_version: str
    historical_bug_id: str
    historical_path: Path
    current_path: Path
    target_dir: Optional[Path]
    qpb_dir: Path
    lever_under_test: Optional[str] = None
    lever_change_summary: Optional[str] = None
    before_lever: Optional[str] = None
    after_lever: Optional[str] = None
    phase_scope: str = "1,2,3"
    iteration_strategies: Sequence[str] = field(default_factory=tuple)
    runner: str = "claude"
    model: str = ""
    wall_clock_seconds: int = 0
    regression_check_status: str = "skipped"
    regression_checked_cells: Sequence[str] = field(default_factory=tuple)
    regression_regressed_cells: Sequence[str] = field(default_factory=tuple)
    noise_floor_threshold: float = DEFAULT_NOISE_FLOOR
    noise_floor_source: str = (
        "single-run point estimate; σ unmeasured (acceptable for "
        "smoke / single-shot measurement — calibration cycles aggregate)"
    )
    notes: str = ""


def build_cell_record(
    inputs: CellInputs, measurement: RecallMeasurement
) -> dict:
    """Assemble a cell record dict matching SCHEMA.md.

    The dict is JSON-serializable; callers write it via ``json.dump``
    with ``indent=2`` to keep cell records human-diffable.
    """
    # Council 2026-04-30 P2-1: SCHEMA.md states qpb_version_under_test
    # is "read from `bin/benchmark_lib.RELEASE_VERSION` at apparatus
    # invocation time." The earlier draft read `detect_skill_version`
    # (which parses SKILL.md) — a separate source of truth that could
    # drift, and that would silently fall back to SCHEMA_VERSION when
    # SKILL.md is missing (yielding qpb_version_under_test=1.5.4 when
    # the real release is older). Use RELEASE_VERSION to match the
    # schema contract.
    qpb_version = benchmark_lib.RELEASE_VERSION
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": _utc_now_iso(),
        "benchmark": inputs.benchmark,
        "qpb_version_under_test": qpb_version,
        "historical_qpb_version": inputs.historical_qpb_version,
        "historical_bug_id": inputs.historical_bug_id,
        "historical_bug_count": len(measurement.historical),
        "current_bug_count": len(measurement.current),
        "current_bug_ids": sorted(rec.bug_id for rec in measurement.current),
        "recovered_bug_ids": list(measurement.recovered_ids),
        "missed_bug_ids": list(measurement.missed_ids),
        "spurious_bug_ids": list(measurement.spurious_ids),
        "recall_against_historical": round(measurement.recall, 4),
        "lever_under_test": inputs.lever_under_test,
        "lever_change_summary": inputs.lever_change_summary,
        "before_lever": inputs.before_lever,
        "after_lever": inputs.after_lever,
        "regression_check": {
            "status": inputs.regression_check_status,
            "checked_cells": list(inputs.regression_checked_cells),
            "regressed_cells": list(inputs.regression_regressed_cells),
            "noise_floor_threshold": inputs.noise_floor_threshold,
        },
        "noise_floor_source": inputs.noise_floor_source,
        "apparatus": {
            "qpb_commit_sha": _git_sha(inputs.qpb_dir),
            "target_commit_sha": (
                _git_sha(inputs.target_dir) if inputs.target_dir else ""
            ),
            "phase_scope": inputs.phase_scope,
            "iteration_strategies": list(inputs.iteration_strategies),
            "runner": inputs.runner,
            "model": inputs.model,
            "wall_clock_seconds": inputs.wall_clock_seconds,
        },
        "notes": inputs.notes,
    }


def write_cell(
    record: dict, output_dir: Path, run_timestamp: Optional[str] = None
) -> Path:
    """Write the record under ``<output_dir>/<run_timestamp>/<benchmark>-<version>-<bug_id>.json``.

    Returns the absolute output path. Creates parent directories.
    """
    ts = run_timestamp or _utc_now_path_ts()
    cell_dir = output_dir / ts
    cell_dir.mkdir(parents=True, exist_ok=True)
    filename = (
        f"{record['benchmark']}-{record['historical_qpb_version']}-"
        f"{record['historical_bug_id']}.json"
    )
    out = cell_dir / filename
    out.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out


@dataclass
class RunnerInvocationResult:
    """Outcome of a runner subprocess invocation."""

    returncode: int
    wall_clock_seconds: int


def _invoke_runner(
    target_dir: Path, phase_scope: str, runner: str, model: str
) -> RunnerInvocationResult:
    """Replay-mode helper: invoke ``python3 -m bin.run_playbook`` against
    the target.

    Subprocess stdout / stderr are inherited so the operator sees
    progress. Council 2026-04-30 P1-2: returns the subprocess exit
    code so the caller can abort the cell write when the runner
    crashed (the original implementation discarded ``returncode`` and
    silently produced a cell against a stale BUGS.md).
    """
    runner_flag = {
        "claude": "--claude",
        "copilot": "--copilot",
        "codex": "--codex",
        "cursor": "--cursor",
    }[runner]  # KeyError = caller bug; --runner choices= guarantees membership
    argv = [
        sys.executable, "-m", "bin.run_playbook",
        runner_flag, "--phase", phase_scope,
    ]
    if model:
        argv.extend(["--model", model])
    argv.append(str(target_dir))
    start = time.monotonic()
    proc = subprocess.run(argv, check=False)
    return RunnerInvocationResult(
        returncode=proc.returncode,
        wall_clock_seconds=int(time.monotonic() - start),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="regression_replay",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--benchmark", required=True, help="Short benchmark name (e.g., chi).")
    p.add_argument(
        "--historical-version",
        required=True,
        help="Historical benchmark version label (e.g., 1.3.45).",
    )
    p.add_argument(
        "--historical-bugs",
        required=True,
        type=Path,
        help="Path to the historical baseline BUGS.md.",
    )
    p.add_argument(
        "--current-bugs",
        type=Path,
        default=None,
        help=(
            "Path to the BUGS.md produced by the current QPB run. "
            "If --invoke-runner is given, this defaults to "
            "<target>/quality/BUGS.md."
        ),
    )
    p.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="Target benchmark directory. Required when --invoke-runner is given.",
    )
    p.add_argument(
        "--bug-id",
        default="all",
        help="Historical bug ID this cell scopes to, or 'all' for full-set recall.",
    )
    p.add_argument(
        "--invoke-runner",
        action="store_true",
        help=(
            "Invoke `python3 -m bin.run_playbook` against --target-dir before "
            "measuring. Default is measurement-only (read --current-bugs as-is)."
        ),
    )
    p.add_argument("--lever-id", default=None)
    p.add_argument("--lever-summary", default=None)
    p.add_argument("--before-cell", default=None, help="Path to the before-lever cell.")
    p.add_argument("--after-cell", default=None, help="Path to the after-lever cell.")
    p.add_argument("--phase-scope", default="1,2,3")
    p.add_argument(
        "--runner",
        default="claude",
        # Council 2026-04-30 P1-1: choices= validation. Without this,
        # `--runner cursr` (typo) fell through to the --copilot
        # default in `_invoke_runner`'s runner_flag dict.
        choices=("claude", "copilot", "codex", "cursor"),
    )
    p.add_argument("--model", default="")
    p.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Cell output root (default: metrics/regression_replay).",
    )
    p.add_argument(
        "--run-timestamp",
        default=None,
        help=(
            "Override the auto-generated YYYYMMDDTHHMMSSZ run timestamp "
            "(useful when bundling related cells under one directory)."
        ),
    )
    p.add_argument(
        "--noise-floor",
        type=float,
        default=DEFAULT_NOISE_FLOOR,
        help="Noise-floor threshold for the regression-check field.",
    )
    p.add_argument("--notes", default="")
    return p


def _qpb_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    qpb_dir = _qpb_dir()

    # Phase 6 cycle 1 fix (apparatus order-of-operations): in replay
    # mode, the runner archives the target's pre-existing quality/
    # tree to quality/previous_runs/<TS>/ before producing fresh
    # artifacts. If the operator points --historical-bugs at the
    # target's own BUGS.md (the natural case when an archive IS its
    # own ground truth — every chi-1.3.x cycle works this way), the
    # historical file gets moved out from under us. Read the
    # historical baseline into memory BEFORE invoking the runner,
    # never after. Measurement-only mode is unaffected (no
    # invocation, no archival).
    historical = parse_bugs_md(args.historical_bugs)

    wall_clock = 0
    if args.invoke_runner:
        if args.target_dir is None:
            print(
                "ERROR: --invoke-runner requires --target-dir", file=sys.stderr
            )
            return 2
        result = _invoke_runner(
            args.target_dir, args.phase_scope, args.runner, args.model
        )
        wall_clock = result.wall_clock_seconds
        # Council 2026-04-30 P1-2: surface non-zero exit codes. The
        # earlier draft swallowed the runner's returncode and would
        # have written a cell record against whatever stale BUGS.md
        # was on disk — a calibration-data corruption vector.
        if result.returncode != 0:
            print(
                f"ERROR: bin.run_playbook exited {result.returncode}; "
                f"refusing to write cell against potentially-stale BUGS.md. "
                f"Use measurement-only mode (omit --invoke-runner) if you "
                f"want to record a cell from existing artifacts.",
                file=sys.stderr,
            )
            return result.returncode
        current_bugs = args.current_bugs or (
            args.target_dir / "quality" / "BUGS.md"
        )
    else:
        if args.current_bugs is None:
            print(
                "ERROR: --current-bugs is required in measurement-only mode",
                file=sys.stderr,
            )
            return 2
        current_bugs = args.current_bugs

    current = parse_bugs_md(current_bugs)
    measurement = measure_recall(historical, current)

    inputs = CellInputs(
        benchmark=args.benchmark,
        historical_qpb_version=args.historical_version,
        historical_bug_id=args.bug_id,
        historical_path=args.historical_bugs,
        current_path=current_bugs,
        target_dir=args.target_dir,
        qpb_dir=qpb_dir,
        lever_under_test=args.lever_id,
        lever_change_summary=args.lever_summary,
        before_lever=args.before_cell,
        after_lever=args.after_cell,
        phase_scope=args.phase_scope,
        runner=args.runner,
        model=args.model,
        wall_clock_seconds=wall_clock,
        noise_floor_threshold=args.noise_floor,
        notes=args.notes,
    )

    record = build_cell_record(inputs, measurement)
    output_path = write_cell(record, args.output_dir, args.run_timestamp)

    print(f"regression_replay: wrote {output_path}")
    print(
        f"  recall: {measurement.recall:.2%} "
        f"({len(measurement.recovered_ids)}/{len(historical)} historical bugs recovered)"
    )
    if measurement.missed_ids:
        print(f"  missed: {', '.join(measurement.missed_ids)}")
    if measurement.spurious_ids:
        print(f"  spurious (current-only): {', '.join(measurement.spurious_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
