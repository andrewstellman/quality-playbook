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


def now_utc_compact_subsecond() -> str:
    # F-2 fix: microsecond precision so two reconstruction runs in the
    # same UTC second produce distinct backup directory names. Two
    # runs colliding within a single microsecond is statistically
    # negligible; if it ever happens, backup_existing() falls back to
    # a counter suffix.
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


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
    # F-2 fix: subsecond timestamp + counter-suffix fallback. The
    # subsecond timestamp alone covers the practical case (two runs
    # within the same UTC second); the counter suffix is a belt-and-
    # braces fallback for microsecond collisions (e.g., on filesystems
    # whose mtime resolution drops microseconds, or in tests that mock
    # the clock to return identical values).
    base = f".backup-{now_utc_compact_subsecond()}"
    backup_dir = target_dir / base
    counter = 0
    while backup_dir.exists():
        counter += 1
        backup_dir = target_dir / f"{base}-{counter}"
        if counter > 999:
            raise RuntimeError(
                f"Could not find a free backup directory name under "
                f"{target_dir} (tried {base}-0 through {base}-999)"
            )
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
    skipped_by_quarter: Dict[str, List[Dict[str, str]]],
) -> Dict[str, dict]:
    """Build {quarter: aggregate_dict} for the bootstrap_recall output.

    F-3 fix: `skipped_by_quarter` is a per-quarter map (not a single
    global list). Each quarter's aggregate carries only its own skip
    records; `--quarter both` no longer cross-contaminates Q1 and Q2.
    """
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
            # F-3 fix: per-quarter skip list, not the global accumulator
            "skipped_cells": list(skipped_by_quarter.get(q, [])),
        }
    return out


QPB_VERSION_FROM_NAME_RE = re.compile(
    r"quality-playbook(?:-bootstrap)?-(?P<v>\d+\.\d+(?:\.\d+)?)"
)


def infer_qpb_version_for_cell_group(
    cells: Sequence[CellObservation],
    rr_cells: Sequence[Tuple[Path, dict]],
) -> Optional[str]:
    """F-1 fix (round 2): best-effort QPB version inference for a
    (benchmark, version) cell group.

    Source order (most authoritative first):
      1. matching regression_replay cell.json with
         `qpb_version_under_test` set
      1.5 `quality/run_metadata.json` `skill_version` / `qpb_version`
          field (the spec-documented per-cell metadata file; see
          `docs/design/QPB_v1.5.7_Design.md` Deliverable 4 and
          instruction 009's "Fallback source: read run_metadata.json
          if the directory naming doesn't yield a version")
      2. `quality/run_state.jsonl` `_index` event's `schema_version`
         field
      3. benchmark name pattern `quality-playbook[-bootstrap]-X.Y.Z`
         (where the QPB version is literally in the benchmark name)

    Returns None when no signal is available — the caller logs this
    as "qpb_version=unknown" rather than silently producing None.
    """
    if not cells:
        return None
    benchmark = cells[0].benchmark
    version = cells[0].version

    # Source 1: matching regression_replay cell.json
    for _rr_path, rr_data in rr_cells:
        rr_benchmark = rr_data.get("benchmark")
        rr_version = rr_data.get("historical_qpb_version") or rr_data.get("historical_version")
        if rr_benchmark == benchmark and rr_version == version:
            v = rr_data.get("qpb_version_under_test")
            if v:
                return str(v)

    # Source 1.5: per-cell quality/run_metadata.json. The spec
    # documents this as a primary fallback for cells whose directory
    # naming doesn't encode a QPB version. Whether current cells have
    # the file or not is irrelevant to whether the script must read
    # it — adopters re-running reconstruction against their own
    # cell roster may populate `quality/run_metadata.json` and expect
    # the script to use it.
    for cell in cells:
        rm = cell.cell_path / "quality" / "run_metadata.json"
        if not rm.is_file():
            continue
        try:
            data = json.loads(rm.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            continue
        # Try common field names in order of preference:
        for field in ("qpb_version", "skill_version", "schema_version",
                      "qpb_version_under_test", "version"):
            v = data.get(field)
            if v:
                return str(v)

    # Source 2: run_state.jsonl _index.schema_version
    for cell in cells:
        rs = cell.cell_path / "quality" / "run_state.jsonl"
        if not rs.is_file():
            continue
        try:
            for line in rs.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("event") == "_index" and rec.get("schema_version"):
                    return str(rec["schema_version"])
        except (OSError, json.JSONDecodeError, UnicodeError):
            continue

    # Source 3a: the benchmark IS quality-playbook itself (after the
    # parse_cell_directory_name regex stripped the version into
    # cell.version), so the QPB version equals cell.version.
    for cell in cells:
        if cell.benchmark in {"quality-playbook", "quality-playbook-bootstrap"}:
            if cell.version:
                return cell.version

    # Source 3b: pre-strip naming pattern (e.g., archive cells whose
    # `benchmark` is the raw directory name like
    # `quality-playbook-1.5.4-bootstrap`).
    for cell in cells:
        m = QPB_VERSION_FROM_NAME_RE.search(cell.benchmark)
        if m:
            return m.group("v")

    return None


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
    rr_cells: Sequence[Tuple[Path, dict]] = (),
) -> Dict[str, dict]:
    """Build {benchmark: trajectory_dict} for cross_version_trends output.

    F-1 fix: `qpb_version` per versions_observed[] record is now
    populated by best-effort inference from regression_replay
    cell.json + run_state.jsonl + benchmark-naming pattern (see
    `infer_qpb_version_for_cell_group`). Leaves None only when no
    signal is available, which the caller logs as "qpb_version=unknown".
    """
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
            qpb_version = infer_qpb_version_for_cell_group(group, rr_cells)
            versions_observed.append({
                "version": version,
                "qpb_version": qpb_version,
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
    # v1.5.7 089x: no-args is purpose-banner-safe.
    _argv_list_089x = list(sys.argv[1:] if argv is None else argv)
    try:
        from bin._purpose import print_command_intro as _print_command_intro
        from bin._purpose import print_help_banner as _print_help_banner
    except ImportError:
        from _purpose import print_command_intro as _print_command_intro  # type: ignore[no-redef]
        from _purpose import print_help_banner as _print_help_banner  # type: ignore[no-redef]
    if not _argv_list_089x:
        _print_command_intro(
            name='metrics_reconstruction',
            summary=(
            "Reconstruct calibration metrics from a historical run's "
            "fixtures (benchmark archive analysis). "
            ),
            role=(
            "Operator-side analytics — NOT used during a playbook "
            "run. Reads the benchmark archive and emits CSV/JSON "
            "summaries for calibration tracking. "
            ),
            usage_hint='python3 -m bin.metrics_reconstruction --runs <pattern>',
        )
        return 0

    # v1.5.7 090a: full attribution banner at top of --help.
    _print_help_banner(_argv_list_089x)

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

    # F-3 fix: per-quarter skip bucket from the start, so each
    # quarter's aggregate sees only its own skips. The legacy global
    # `skipped` list is kept for the script's stdout summary only.
    skipped: List[Dict[str, str]] = []
    skipped_by_quarter: Dict[str, List[Dict[str, str]]] = {q: [] for q in quarters_in_scope}

    observations = walk_cells_root(cells_root, skipped)
    rr_cells = load_regression_replay_cells(target, skipped)
    cal_cycles = load_calibration_cycles(target, skipped)

    # Bucket the global skip list by quarter (best-effort: cells whose
    # path contains a regression_replay/<timestamp>/ segment get that
    # timestamp's quarter; cell BUGS.md paths fall under the cell's
    # detected quarter via determine_quarter_from_observation; if no
    # signal, the fallback_quarter receives it).
    for skip_record in skipped:
        path = skip_record.get("path", "")
        q = _quarter_for_skip_path(path, fallback_quarter)
        if q in skipped_by_quarter:
            skipped_by_quarter[q].append(skip_record)
        else:
            skipped_by_quarter.setdefault(fallback_quarter, []).append(skip_record)

    ground_truths = compute_ground_truths(observations)
    bootstrap = build_bootstrap_recall_aggregates(
        observations, rr_cells, cal_cycles,
        quarters_in_scope, fallback_quarter, skipped_by_quarter,
    )
    trends = build_cross_version_trends(observations, ground_truths, rr_cells)

    # F-1 logging: count cells whose qpb_version inference returned None
    unknown_qpb_versions = 0
    for trend in trends.values():
        for vo in trend["versions_observed"]:
            if vo.get("qpb_version") is None:
                unknown_qpb_versions += 1

    actions = write_outputs(target, bootstrap, trends, args.dry_run)

    print(f"metrics_reconstruction v{lib.RELEASE_VERSION}")
    print(f"  cells-root:       {cells_root}")
    print(f"  target:           {target}")
    print(f"  observations:     {len(observations)} cells walked")
    print(f"  regression cells: {len(rr_cells)}")
    print(f"  calibration:      {len(cal_cycles)} cycles")
    print(f"  benchmarks:       {len(ground_truths)} (with ground-truth)")
    print(f"  quarters:         {quarters_in_scope}")
    print(f"  skipped (global): {len(skipped)}")
    if any(skipped_by_quarter.values()):
        print(f"  skipped per-quarter:")
        for q, items in skipped_by_quarter.items():
            if items:
                print(f"    {q}: {len(items)}")
    if unknown_qpb_versions:
        print(f"  qpb_version=unknown for {unknown_qpb_versions} (benchmark, version) rows "
              f"in cross_version_trends (no signal in cell.json, run_metadata.json, "
              f"run_state.jsonl, or naming)")
    if actions["backed_up_to"]:
        print(f"  backed up to:     {actions['backed_up_to']}")
    print(f"  wrote {len(actions['written'])} files" if not args.dry_run
          else f"  would write {len(actions['would_write'])} files")
    return 0


def _quarter_for_skip_path(path_str: str, fallback_quarter: str) -> str:
    """F-3 helper: derive a quarter for a skipped-cell path.

    For paths under `metrics/regression_replay/<ts>/`, parse the
    `<ts>` segment as a UTC timestamp and return its quarter. For
    other paths (BUGS.md cells), there's no embedded date — return
    the fallback. This is best-effort; the F-3 contract is "no
    cross-quarter contamination", not "perfect quarter attribution".
    """
    m = re.search(r"metrics/regression_replay/(?P<ts>\d{8}T\d{6}Z)/", path_str)
    if m:
        q = quarter_for(m.group("ts"))
        if q is not None:
            return q
    return fallback_quarter


if __name__ == "__main__":
    raise SystemExit(main())
