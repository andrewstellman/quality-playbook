#!/usr/bin/env python3
"""Reconstruct cross-cell aggregates in metrics/ from current cell roster.

v1.5.7 Phase 4 / Deliverable 4. Walks the cell roster under repos/,
parses ### BUG-NNN headings from quality/BUGS.md files, reads existing
metrics/regression_replay/<ts>/*.json cell records and
metrics/calibration/*.json cycle summaries, and writes per-quarter
aggregates to metrics/bootstrap_recall/<YYYY>-<Q>.json plus
per-benchmark trajectories to metrics/cross_version_trends/<benchmark>.json.

Sub-directories skipped (not written to):
  - regression_replay/   (read-only here; produced by bin/regression_replay.py)
  - calibration/         (read-only here; operator-promoted from workspace)
  - sdlc_defects/        (v1.7-owned; bin/migrate_defect_baseline.py)

Sub-directories written to (backup-on-write):
  - bootstrap_recall/
  - cross_version_trends/

CLI:
  --target <metrics-root>    default: metrics/ in cwd
  --cells-root <repos-root>  default: repos/ in cwd
  --quarter Q1|Q2|both       default: both
  --dry-run                  print planned writes; don't write

Per-file documentation lives in metrics/<sub-directory>/README.md.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from bin import benchmark_lib as lib  # type: ignore
except Exception:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from bin import benchmark_lib as lib  # type: ignore

SCHEMA_VERSION = "1.5.7"
BUGS_HEADING_RE = re.compile(r"^###\s+BUG-(\d+)\b", re.MULTILINE)
BENCHMARK_VERSION_RE = re.compile(r"^(?P<benchmark>[a-z0-9]+(?:-[a-z0-9]+)*?)-(?P<version>\d+\.\d+(?:\.\d+)?)$")


@dataclass
class CellObservation:
    """One observation of a benchmark cell at a point in time.

    Sourced either from an existing regression_replay/<ts>/*.json
    record (preferred, has full metadata) or from a repos/<cell>/
    quality/BUGS.md heading-parse (fallback, just bug-count).
    """
    benchmark: str
    version: str
    bug_count: int
    bug_ids: List[str]
    cell_path: Path
    observation_timestamp: Optional[datetime]
    qpb_version: Optional[str]
    is_archive: bool = False


@dataclass
class ReconstructionPlan:
    cells: List[CellObservation] = field(default_factory=list)
    regression_replay_cells: List[Path] = field(default_factory=list)
    calibration_cycles: List[Path] = field(default_factory=list)
    skipped: List[Dict[str, str]] = field(default_factory=list)


def parse_bug_count(bugs_md: Path) -> Tuple[int, List[str]]:
    """Count ### BUG-NNN headings + return sorted BUG-NNN IDs.

    Returns (0, []) on empty/missing file. Raises on permission errors.
    """
    if not bugs_md.is_file():
        return 0, []
    text = bugs_md.read_text(encoding="utf-8", errors="replace")
    matches = BUGS_HEADING_RE.findall(text)
    bug_ids = sorted({f"BUG-{m.zfill(3)}" for m in matches})
    return len(bug_ids), bug_ids


def parse_cell_directory_name(name: str) -> Optional[Tuple[str, str]]:
    """Parse `<benchmark>-<version>` into (benchmark, version).

    Returns None for non-conforming names (e.g., directories that don't
    match the convention — `__pycache__`, `archive`).
    """
    m = BENCHMARK_VERSION_RE.match(name)
    if not m:
        return None
    return m.group("benchmark"), m.group("version")


def walk_cells_root(cells_root: Path, skipped: List[Dict[str, str]]) -> List[CellObservation]:
    """Walk repos/ + repos/archive/ for BUGS.md files; return observations."""
    observations: List[CellObservation] = []
    if not cells_root.is_dir():
        return observations
    for child in sorted(cells_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name in {"__pycache__", "archive"}:
            continue
        parsed = parse_cell_directory_name(child.name)
        if parsed is None:
            continue
        benchmark, version = parsed
        bugs_md = child / "quality" / "BUGS.md"
        try:
            count, ids = parse_bug_count(bugs_md)
        except (OSError, UnicodeError) as exc:
            skipped.append({
                "path": str(bugs_md),
                "reason": f"could not read/parse: {type(exc).__name__}: {exc}",
            })
            continue
        if count == 0:
            # Not necessarily an error — a cell without BUGS.md is in
            # an earlier phase. Record as a zero-observation; trend
            # charts can decide whether to include zeros.
            observations.append(CellObservation(
                benchmark=benchmark, version=version, bug_count=0, bug_ids=[],
                cell_path=child, observation_timestamp=None, qpb_version=None,
            ))
            continue
        observations.append(CellObservation(
            benchmark=benchmark, version=version, bug_count=count, bug_ids=ids,
            cell_path=child, observation_timestamp=None, qpb_version=None,
        ))

    archive_root = cells_root / "archive"
    if archive_root.is_dir():
        for benchmark_dir in sorted(archive_root.iterdir()):
            if not benchmark_dir.is_dir():
                continue
            prev_runs_root = benchmark_dir / "quality" / "previous_runs"
            if not prev_runs_root.is_dir():
                continue
            for prev_run in sorted(prev_runs_root.iterdir()):
                if not prev_run.is_dir():
                    continue
                bugs_md = prev_run / "quality" / "BUGS.md"
                try:
                    count, ids = parse_bug_count(bugs_md)
                except (OSError, UnicodeError) as exc:
                    skipped.append({
                        "path": str(bugs_md),
                        "reason": f"could not read/parse: {type(exc).__name__}: {exc}",
                    })
                    continue
                # benchmark name from the directory; version inferred
                # from the previous-run directory name (timestamp) is
                # not a benchmark version label — for archive cells we
                # use the directory name as the version label.
                observations.append(CellObservation(
                    benchmark=benchmark_dir.name, version=prev_run.name,
                    bug_count=count, bug_ids=ids, cell_path=prev_run,
                    observation_timestamp=None, qpb_version=None, is_archive=True,
                ))
    return observations


def load_regression_replay_cells(target: Path, skipped: List[Dict[str, str]]) -> List[Tuple[Path, dict]]:
    """Load every metrics/regression_replay/<ts>/*.json cell record."""
    rr_root = target / "regression_replay"
    cells: List[Tuple[Path, dict]] = []
    if not rr_root.is_dir():
        return cells
    for run_dir in sorted(rr_root.iterdir()):
        if not run_dir.is_dir():
            continue
        if run_dir.name.startswith(".backup-"):
            continue
        for json_path in sorted(run_dir.glob("*.json")):
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeError) as exc:
                skipped.append({
                    "path": str(json_path),
                    "reason": f"could not parse cell.json: {type(exc).__name__}: {exc}",
                })
                continue
            cells.append((json_path, data))
    return cells


def load_calibration_cycles(target: Path, skipped: List[Dict[str, str]]) -> List[Tuple[Path, dict]]:
    """Load every metrics/calibration/*.json cycle summary."""
    cal_root = target / "calibration"
    cycles: List[Tuple[Path, dict]] = []
    if not cal_root.is_dir():
        return cycles
    for json_path in sorted(cal_root.glob("*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            skipped.append({
                "path": str(json_path),
                "reason": f"could not parse cycle.json: {type(exc).__name__}: {exc}",
            })
            continue
        cycles.append((json_path, data))
    return cycles


def quarter_for(date_str: str) -> Optional[str]:
    """Return `<YYYY>-Q<n>` for an ISO-8601 date or timestamp string."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        # Compact form fallback
        try:
            dt = datetime.strptime(date_str[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    q = (dt.month - 1) // 3 + 1
    return f"{dt.year}-Q{q}"


def determine_quarter_from_observation(obs: CellObservation, fallback_quarter: str) -> str:
    """Best-effort quarter assignment for a CellObservation."""
    if obs.observation_timestamp is not None:
        q = (obs.observation_timestamp.month - 1) // 3 + 1
        return f"{obs.observation_timestamp.year}-Q{q}"
    if obs.is_archive and re.match(r"^\d{8}T\d{6}Z$", obs.version):
        q = quarter_for(obs.version)
        if q is not None:
            return q
    return fallback_quarter


def now_utc_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def current_quarter() -> str:
    now = datetime.now(timezone.utc)
    q = (now.month - 1) // 3 + 1
    return f"{now.year}-Q{q}"


def backup_existing(target_dir: Path) -> Optional[Path]:
    """Move existing data files (non-README, non-backup) into a backup dir.

    Returns the backup directory path if any files were backed up;
    None if there was nothing to back up. README.md files are
    preserved in place (they're documentation, not data).
    """
    if not target_dir.is_dir():
        return None
    movable = [
        p for p in target_dir.iterdir()
        if p.is_file() and p.name != "README.md" and not p.name.startswith(".")
    ]
    if not movable:
        return None
    backup_dir = target_dir / f".backup-{now_utc_compact()}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for p in movable:
        shutil.move(str(p), str(backup_dir / p.name))
    return backup_dir


def build_bootstrap_recall_aggregates(
    observations: Sequence[CellObservation],
    rr_cells: Sequence[Tuple[Path, dict]],
    cal_cycles: Sequence[Tuple[Path, dict]],
    quarters_in_scope: Sequence[str],
    fallback_quarter: str,
    skipped: Sequence[Dict[str, str]],
) -> Dict[str, dict]:
    """Build {quarter: aggregate_dict} for the bootstrap_recall output."""
    by_quarter: Dict[str, List[CellObservation]] = {q: [] for q in quarters_in_scope}
    for obs in observations:
        q = determine_quarter_from_observation(obs, fallback_quarter)
        if q in by_quarter:
            by_quarter[q].append(obs)

    rr_count_by_quarter: Dict[str, int] = {q: 0 for q in quarters_in_scope}
    for _path, data in rr_cells:
        ts = data.get("timestamp") or data.get("run_timestamp")
        q = quarter_for(ts) if ts else None
        if q in rr_count_by_quarter:
            rr_count_by_quarter[q] += 1

    cal_count_by_quarter: Dict[str, int] = {q: 0 for q in quarters_in_scope}
    for _path, data in cal_cycles:
        ts = data.get("cycle_kicked_off")
        q = quarter_for(ts) if ts else None
        if q in cal_count_by_quarter:
            cal_count_by_quarter[q] += 1

    ground_truth_by_benchmark = compute_ground_truths(observations)

    out: Dict[str, dict] = {}
    reconstruction_ts = now_utc_iso()
    for q in quarters_in_scope:
        cells = by_quarter[q]
        per_benchmark_groups: Dict[str, List[CellObservation]] = {}
        for c in cells:
            per_benchmark_groups.setdefault(c.benchmark, []).append(c)
        per_benchmark = []
        for benchmark in sorted(per_benchmark_groups):
            group = per_benchmark_groups[benchmark]
            ground_truth = ground_truth_by_benchmark.get(benchmark)
            recalls = []
            for c in group:
                if ground_truth and ground_truth.bug_count > 0:
                    matched = set(c.bug_ids) & set(ground_truth.bug_ids)
                    recalls.append(round(len(matched) / ground_truth.bug_count, 4))
                else:
                    recalls.append(0.0)
            per_benchmark.append({
                "benchmark": benchmark,
                "cells_in_quarter": len(group),
                "bug_count_total": sum(c.bug_count for c in group),
                "bug_count_per_cell": [c.bug_count for c in group],
                "recall_against_pinned_ground_truth": recalls,
            })
        out[q] = {
            "schema_version": SCHEMA_VERSION,
            "reconstruction_timestamp": reconstruction_ts,
            "quarter": q,
            "qpb_version_at_reconstruction": lib.RELEASE_VERSION,
            "per_benchmark": per_benchmark,
            "calibration_cycle_count": cal_count_by_quarter.get(q, 0),
            "regression_replay_cell_count": rr_count_by_quarter.get(q, 0),
            "skipped_cells": list(skipped),
        }
    return out


def compute_ground_truths(observations: Sequence[CellObservation]) -> Dict[str, CellObservation]:
    """For each benchmark, pin the most-detailed BUGS.md as ground truth.

    Tie-broken by lowest version string (lexicographic) per the
    cross_version_trends README convention.
    """
    by_benchmark: Dict[str, List[CellObservation]] = {}
    for obs in observations:
        if obs.is_archive:
            continue
        if obs.bug_count == 0:
            continue
        by_benchmark.setdefault(obs.benchmark, []).append(obs)
    ground_truths: Dict[str, CellObservation] = {}
    for benchmark, group in by_benchmark.items():
        group.sort(key=lambda o: (-o.bug_count, o.version))
        ground_truths[benchmark] = group[0]
    return ground_truths


def build_cross_version_trends(
    observations: Sequence[CellObservation],
    ground_truths: Dict[str, CellObservation],
) -> Dict[str, dict]:
    """Build {benchmark: trajectory_dict} for cross_version_trends output."""
    by_benchmark_version: Dict[Tuple[str, str], List[CellObservation]] = {}
    for obs in observations:
        if obs.is_archive:
            continue
        if obs.bug_count == 0 and obs.benchmark not in ground_truths:
            continue
        by_benchmark_version.setdefault((obs.benchmark, obs.version), []).append(obs)

    out: Dict[str, dict] = {}
    reconstruction_ts = now_utc_iso()
    for benchmark, gt in ground_truths.items():
        versions = sorted(
            v for (b, v) in by_benchmark_version if b == benchmark
        )
        versions_observed = []
        for version in versions:
            group = by_benchmark_version[(benchmark, version)]
            cell_count = len(group)
            avg_bug_count = sum(c.bug_count for c in group) / cell_count if cell_count else 0
            recall = avg_bug_count / gt.bug_count if gt.bug_count > 0 else 0.0
            cells = sorted(str(c.cell_path / "quality" / "BUGS.md") for c in group)
            versions_observed.append({
                "version": version,
                "qpb_version": None,
                "cell_count": cell_count,
                "bug_count_avg": round(avg_bug_count, 2),
                "recall_against_ground_truth": round(recall, 4),
                "cells": cells,
            })
        out[benchmark] = {
            "schema_version": SCHEMA_VERSION,
            "reconstruction_timestamp": reconstruction_ts,
            "qpb_version_at_reconstruction": lib.RELEASE_VERSION,
            "benchmark": benchmark,
            "ground_truth": {
                "version": gt.version,
                "bug_count": gt.bug_count,
                "path": str(gt.cell_path / "quality" / "BUGS.md"),
            },
            "versions_observed": versions_observed,
            "per_defect_class": [],
        }
    return out


def write_outputs(
    target: Path,
    bootstrap_by_quarter: Dict[str, dict],
    trends_by_benchmark: Dict[str, dict],
    dry_run: bool,
) -> Dict[str, List[str]]:
    """Write outputs (or list them when dry_run). Returns {action: paths}."""
    actions: Dict[str, List[str]] = {"written": [], "backed_up_to": [], "would_write": []}

    bs_dir = target / "bootstrap_recall"
    cv_dir = target / "cross_version_trends"

    for d in (bs_dir, cv_dir):
        d.mkdir(parents=True, exist_ok=True)

    if dry_run:
        for q in bootstrap_by_quarter:
            actions["would_write"].append(str(bs_dir / f"{q}.json"))
        for b in trends_by_benchmark:
            actions["would_write"].append(str(cv_dir / f"{b}.json"))
        return actions

    bs_backup = backup_existing(bs_dir)
    if bs_backup:
        actions["backed_up_to"].append(str(bs_backup))
    cv_backup = backup_existing(cv_dir)
    if cv_backup:
        actions["backed_up_to"].append(str(cv_backup))

    for q, agg in bootstrap_by_quarter.items():
        path = bs_dir / f"{q}.json"
        path.write_text(json.dumps(agg, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        actions["written"].append(str(path))
    for b, trend in trends_by_benchmark.items():
        path = cv_dir / f"{b}.json"
        path.write_text(json.dumps(trend, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        actions["written"].append(str(path))
    return actions


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconstruct cross-cell aggregates in metrics/ from "
                    "current cell roster (v1.5.7+).",
    )
    parser.add_argument(
        "--target", type=Path, default=Path("metrics"),
        help="Metrics tree root (default: metrics/)",
    )
    parser.add_argument(
        "--cells-root", type=Path, default=Path("repos"),
        help="Cell roster root (default: repos/)",
    )
    parser.add_argument(
        "--quarter", choices=("Q1", "Q2", "both"), default="both",
        help="Which quarters to reconstruct (default: both)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print planned writes; don't write",
    )
    parser.add_argument(
        "--year", type=int, default=None,
        help="Year for the quarter labels (default: current UTC year)",
    )
    args = parser.parse_args(argv)

    target: Path = args.target.resolve()
    cells_root: Path = args.cells_root.resolve()
    if not cells_root.is_dir():
        print(f"ERROR: cells-root does not exist: {cells_root}", file=sys.stderr)
        return 2

    year = args.year if args.year is not None else datetime.now(timezone.utc).year
    quarters_in_scope = ["Q1", "Q2"] if args.quarter == "both" else [args.quarter]
    quarters_in_scope = [f"{year}-{q}" for q in quarters_in_scope]
    fallback_quarter = current_quarter()
    if fallback_quarter not in quarters_in_scope:
        quarters_in_scope.append(fallback_quarter)

    skipped: List[Dict[str, str]] = []
    observations = walk_cells_root(cells_root, skipped)
    rr_cells = load_regression_replay_cells(target, skipped)
    cal_cycles = load_calibration_cycles(target, skipped)

    ground_truths = compute_ground_truths(observations)
    bootstrap = build_bootstrap_recall_aggregates(
        observations, rr_cells, cal_cycles,
        quarters_in_scope, fallback_quarter, skipped,
    )
    trends = build_cross_version_trends(observations, ground_truths)

    actions = write_outputs(target, bootstrap, trends, args.dry_run)

    print(f"metrics_reconstruction v{lib.RELEASE_VERSION}")
    print(f"  cells-root:       {cells_root}")
    print(f"  target:           {target}")
    print(f"  observations:     {len(observations)} cells walked")
    print(f"  regression cells: {len(rr_cells)}")
    print(f"  calibration:      {len(cal_cycles)} cycles")
    print(f"  benchmarks:       {len(ground_truths)} (with ground-truth)")
    print(f"  quarters:         {quarters_in_scope}")
    print(f"  skipped:          {len(skipped)}")
    if actions["backed_up_to"]:
        print(f"  backed up to:     {actions['backed_up_to']}")
    print(f"  wrote {len(actions['written'])} files" if not args.dry_run
          else f"  would write {len(actions['would_write'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
