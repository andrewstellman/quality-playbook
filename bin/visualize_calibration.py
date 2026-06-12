"""Generate four calibration-cycle visualizations into a cycle directory.

Reads cycle history (run_state.jsonl), per-cycle recall data
(metrics/regression_replay/*/cell.json), historical baselines
(repos/archive/<bench>/quality/BUGS.md), and the lever log
(docs/process/Lever_Calibration_Log.md). Writes four artifacts into
``<cycle-dir>/visualizations/``:

1. ``per_bug_cycle_heatmap.png`` — rows=bugs, cols=cycles, cells=found/
   missed/unchanged/n-a. The displacement story made visible.
2. ``lever_benchmark_heatmap.png`` — rows=lever pulls, cols=benchmarks,
   cells=recall delta with red↔green gradient.
3. ``recall_trajectory.png`` — line plot, X=cycle ordinal, Y=recall,
   one line per benchmark, vertical dashed lines at lever-pull cycles.
4. ``lever_interaction.mermaid`` — Mermaid ``graph LR`` source. Nodes
   are levers/patterns, edges marked positive/negative. If
   ``mermaid-cli`` is installed and on PATH, also renders
   ``lever_interaction.png``; otherwise the .mermaid source is the
   final artifact.

Dependencies: matplotlib, numpy. Not part of the playbook runner —
this is an analysis utility invoked manually after a cycle closes.
Install in the QPB venv: ``./.venv/bin/pip install matplotlib numpy``.

CLI:

    python -m bin.visualize_calibration <cycle-dir>

Use ``--workspace-root`` to override the workspace root used to locate
``Calibration Cycles/`` and ``metrics/regression_replay/`` (defaults to
the parent of the QPB repo, since cycles live in
``~/Documents/AI-Driven Development/Quality Playbook/`` while QPB is
at ``~/Documents/QPB/``).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


_LOG = logging.getLogger(__name__)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE_ROOT = (
    Path.home() / "Documents" / "AI-Driven Development" / "Quality Playbook"
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_cells(metrics_dir: Path) -> list[dict[str, Any]]:
    """Load every ``cell.json`` under ``metrics_dir`` (recursively).

    Each cell is augmented with ``_path`` (its source file) and
    ``_run_timestamp_dir`` (the parent dir name, used as a stable
    chronological key when ``run_timestamp`` is missing or ambiguous).
    Returns cells sorted by ``run_timestamp`` ascending; cells without
    a parseable timestamp sort by directory name as a fallback.
    """
    cells: list[dict[str, Any]] = []
    if not metrics_dir.is_dir():
        return cells
    for path in sorted(metrics_dir.glob("**/*.json")):
        if path.name == "SCHEMA.md":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        data["_path"] = str(path)
        data["_run_timestamp_dir"] = path.parent.name
        cells.append(data)
    cells.sort(
        key=lambda c: (
            c.get("run_timestamp") or "",
            c.get("_run_timestamp_dir") or "",
        )
    )
    return cells


def load_cycles(cycles_root: Path) -> list[dict[str, Any]]:
    """Read each cycle's ``_index`` + ``cycle_start`` events and return
    a per-cycle summary dict ordered by directory name (which carries
    the YYYY-MM-DD- prefix).
    """
    cycles: list[dict[str, Any]] = []
    if not cycles_root.is_dir():
        return cycles
    for cycle_dir in sorted(cycles_root.iterdir()):
        if not cycle_dir.is_dir():
            continue
        state = cycle_dir / "run_state.jsonl"
        summary: dict[str, Any] = {
            "cycle_dir": str(cycle_dir),
            "cycle_name": cycle_dir.name,
            "lever_under_test": None,
            "benchmarks": [],
            "iteration": None,
            "events": [],
        }
        if state.is_file():
            for raw in state.read_text(encoding="utf-8").splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                summary["events"].append(obj)
                if obj.get("event") == "_index":
                    summary["lever_under_test"] = obj.get("lever_under_test")
                    summary["benchmarks"] = list(obj.get("benchmarks") or [])
                    summary["iteration"] = obj.get("iteration")
        cycles.append(summary)
    return cycles


_LEVER_HEADING_RE = re.compile(r"^##\s+Cycle:\s*(.+)$", re.MULTILINE)
_FIELD_RE = re.compile(
    r"^\*\*(Before|After[^:]*|Recall delta|Lever pulled|Verdict|Cell|Cross-benchmark):\*\*\s*(.+?)$",
    re.MULTILINE,
)


def load_lever_log(log_path: Path) -> list[dict[str, Any]]:
    """Parse ``docs/process/Lever_Calibration_Log.md`` into a list of
    per-cycle dicts ordered as they appear (chronological). Each dict
    carries the cycle name, the lever pulled, parsed before/after
    recall numbers (best-effort; None if not parseable), and a
    ``raw_block`` for the rest of the entry.
    """
    entries: list[dict[str, Any]] = []
    if not log_path.is_file():
        return entries
    # 189-class: a calibration LOG can carry captured subprocess output —
    # read with errors="replace" so a stray non-UTF-8 byte can't crash the
    # visualizer on a cp1252 host.
    text = log_path.read_text(encoding="utf-8", errors="replace")
    headings = list(_LEVER_HEADING_RE.finditer(text))
    for i, m in enumerate(headings):
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[start:end]
        entry: dict[str, Any] = {
            "cycle_name": m.group(1).strip(),
            "lever_pulled": None,
            "recall_before": None,
            "recall_after": None,
            "verdict": None,
            "raw_block": block,
        }
        for fm in _FIELD_RE.finditer(block):
            key = fm.group(1).strip()
            value = fm.group(2).strip()
            if key == "Lever pulled":
                entry["lever_pulled"] = value
            elif key == "Verdict":
                entry["verdict"] = value
            elif key == "Before":
                entry["recall_before"] = _extract_recall(value)
            elif key.startswith("After"):
                entry["recall_after"] = _extract_recall(value)
        entries.append(entry)
    return entries


_RECALL_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _extract_recall(text: str) -> float | None:
    """Pull a recall fraction from a freeform string. Tries N/M form
    first, then a percent. Returns None if neither parses."""
    m = _RECALL_RE.search(text)
    if m:
        n, d = int(m.group(1)), int(m.group(2))
        if d > 0:
            return n / d
    m = _PCT_RE.search(text)
    if m:
        return float(m.group(1)) / 100.0
    return None


def load_historical_bugs(
    repos_archive: Path, benchmark_version: str
) -> Optional[list[str]]:
    """Read the BUGS.md for ``benchmark_version`` (e.g. ``chi-1.3.45``)
    and return the list of historical bug IDs in source order.

    Returns:
        - ``None`` when the archive is missing — either
          ``repos_archive/<benchmark_version>/`` does not exist or its
          ``quality/BUGS.md`` is missing. A WARNING-level log line is
          emitted with the missing path so the caller can see the
          gap. v1.5.6 BUG-006: pre-fix this case returned an empty
          list, silently merging "archive missing" into "archive
          present but contains zero bugs", which made it impossible
          for callers (e.g. the per-bug heatmap renderer) to
          distinguish "the operator hasn't staged the historical
          baseline" from "the historical baseline really does have
          no bugs."
        - ``[]`` when ``BUGS.md`` exists but contains zero bug
          headings (a real "archive present but empty" state — rare
          but legitimate for a baseline that was set up before any
          bugs were tracked).
        - ``[bug_id, ...]`` in source order otherwise.

    Callers MUST handle ``None`` explicitly. Iterating ``for x in
    load_historical_bugs(...)`` directly will raise ``TypeError`` on
    a missing archive — the type signature is now ``Optional`` to
    surface this at call sites.
    """
    bugs_md = repos_archive / benchmark_version / "quality" / "BUGS.md"
    if not bugs_md.is_file():
        _LOG.warning(
            "load_historical_bugs: missing archive %s — "
            "returning None so caller can distinguish 'archive missing' "
            "from 'archive present but empty'.",
            bugs_md,
        )
        return None
    text = bugs_md.read_text(encoding="utf-8")
    return [m.group(1) for m in re.finditer(r"^###\s+(BUG-[A-Z0-9-]+)", text, re.MULTILINE)]


# ---------------------------------------------------------------------------
# Chart 1 — Per-bug × cycle heatmap
# ---------------------------------------------------------------------------


def render_per_bug_cycle_heatmap(
    cells: list[dict[str, Any]],
    repos_archive: Path,
    output_path: Path,
) -> None:
    """For each (benchmark, historical bug) pair, plot a row across
    cycles where each cell is found/missed/N-A. Rows are grouped by
    benchmark and ordered by historical bug ID."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.colors as mcolors
    import matplotlib.pyplot as plt
    import numpy as np

    # Collect (benchmark, version) pairs from cells.
    bench_versions: list[tuple[str, str]] = []
    for c in cells:
        key = (c.get("benchmark") or "?", c.get("historical_version") or "?")
        if key not in bench_versions:
            bench_versions.append(key)

    # Row index = (benchmark, version, bug_id); column index = cycle ordinal.
    # v1.5.6 BUG-006: load_historical_bugs returns None when the
    # archive is missing (logged at WARNING level inside the helper);
    # treat that as "no rows from this archive" — the fallback below
    # rebuilds rows from the cells' own bug lists.
    rows: list[tuple[str, str, str]] = []
    for bench, version in bench_versions:
        bug_ids = load_historical_bugs(repos_archive, f"{bench}-{version}")
        if bug_ids is None:
            continue
        for bug_id in bug_ids:
            rows.append((bench, version, bug_id))

    # If no historical bugs found anywhere, fall back to the union of
    # bug IDs the cells mention (recovered + missed).
    if not rows:
        for c in cells:
            bench = c.get("benchmark") or "?"
            version = c.get("historical_version") or "?"
            for bug_id in (c.get("recovered_bug_ids") or []) + (c.get("missed_bug_ids") or []):
                key = (bench, version, bug_id)
                if key not in rows:
                    rows.append(key)

    # Cycle ordinals are derived from cell run_timestamp dirs ordered.
    cycle_keys: list[str] = []
    for c in cells:
        k = c.get("_run_timestamp_dir") or c.get("run_timestamp") or ""
        if k and k not in cycle_keys:
            cycle_keys.append(k)

    if not rows or not cycle_keys:
        # Emit a placeholder chart so downstream tooling sees an output.
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(
            0.5, 0.5, "no data", ha="center", va="center", fontsize=14,
            color="gray",
        )
        ax.set_axis_off()
        ax.set_title("Per-bug × cycle heatmap (no data)")
        fig.tight_layout()
        fig.savefig(output_path, dpi=120)
        plt.close(fig)
        return

    # Encoding: 0 N/A, 1 missed, 2 found.
    matrix = np.zeros((len(rows), len(cycle_keys)), dtype=int)
    for c in cells:
        bench = c.get("benchmark") or "?"
        version = c.get("historical_version") or "?"
        col = cycle_keys.index(c.get("_run_timestamp_dir") or c.get("run_timestamp") or "")
        recovered = set(c.get("recovered_bug_ids") or [])
        missed = set(c.get("missed_bug_ids") or [])
        for ri, (rb, rv, rid) in enumerate(rows):
            if rb != bench or rv != version:
                continue
            if rid in recovered:
                matrix[ri, col] = 2
            elif rid in missed:
                matrix[ri, col] = 1

    cmap = mcolors.ListedColormap(["#f0f0f0", "#d62728", "#2ca02c"])
    norm = mcolors.BoundaryNorm([-0.5, 0.5, 1.5, 2.5], cmap.N)

    fig, ax = plt.subplots(
        figsize=(max(6, 0.5 * len(cycle_keys) + 4),
                 max(3, 0.25 * len(rows) + 2))
    )
    ax.imshow(matrix, aspect="auto", cmap=cmap, norm=norm, interpolation="nearest")
    ax.set_xticks(range(len(cycle_keys)))
    ax.set_xticklabels(cycle_keys, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(
        [f"{b}-{v}/{bug}" for (b, v, bug) in rows], fontsize=7
    )
    ax.set_title(
        "Per-bug × cycle heatmap (green=found, red=missed, gray=N/A)"
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Chart 2 — Lever × benchmark heatmap
# ---------------------------------------------------------------------------


def render_lever_benchmark_heatmap(
    lever_log: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """For each lever pull (row), the recall delta on each benchmark
    (column). Cells colored on a red↔white↔green diverging map."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.colors as mcolors
    import matplotlib.pyplot as plt
    import numpy as np

    benchmarks: list[str] = []
    for c in cells:
        b = c.get("benchmark")
        if b and b not in benchmarks:
            benchmarks.append(b)

    if not lever_log or not benchmarks:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "no data", ha="center", va="center", fontsize=14, color="gray")
        ax.set_axis_off()
        ax.set_title("Lever × benchmark heatmap (no data)")
        fig.tight_layout()
        fig.savefig(output_path, dpi=120)
        plt.close(fig)
        return

    matrix = np.full((len(lever_log), len(benchmarks)), np.nan)
    for r, entry in enumerate(lever_log):
        before = entry.get("recall_before")
        after = entry.get("recall_after")
        if before is None or after is None:
            continue
        delta = after - before
        # Apply the same delta to whichever benchmark this cycle named
        # (when the cycle name contains a benchmark token).
        for ci, bench in enumerate(benchmarks):
            if bench in entry["cycle_name"]:
                matrix[r, ci] = delta

    cmap = plt.get_cmap("RdYlGn")
    fig, ax = plt.subplots(
        figsize=(max(5, 1.2 * len(benchmarks) + 3),
                 max(2.5, 0.5 * len(lever_log) + 2))
    )
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=-1.0, vmax=1.0)
    ax.set_xticks(range(len(benchmarks)))
    ax.set_xticklabels(benchmarks, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(lever_log)))
    ax.set_yticklabels(
        [e["cycle_name"][:48] for e in lever_log], fontsize=8
    )
    ax.set_title("Lever × benchmark recall delta")
    fig.colorbar(im, ax=ax, label="Δ recall")
    # Annotate each cell with its delta where present.
    for r in range(matrix.shape[0]):
        for c in range(matrix.shape[1]):
            v = matrix[r, c]
            if not np.isnan(v):
                ax.text(c, r, f"{v:+.2f}", ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Chart 3 — Recall trajectory
# ---------------------------------------------------------------------------


def render_recall_trajectory(
    cells: list[dict[str, Any]],
    lever_log: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """X = cycle ordinal, Y = recall (0..1), one line per benchmark.
    Vertical dashed lines at lever-pull cycles."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cycle_keys: list[str] = []
    for c in cells:
        k = c.get("_run_timestamp_dir") or c.get("run_timestamp") or ""
        if k and k not in cycle_keys:
            cycle_keys.append(k)

    fig, ax = plt.subplots(figsize=(8, 4))

    by_bench: dict[str, list[tuple[int, float]]] = {}
    for c in cells:
        bench = c.get("benchmark")
        recall = c.get("recall_against_historical")
        if bench is None or recall is None:
            continue
        key = c.get("_run_timestamp_dir") or c.get("run_timestamp") or ""
        if key not in cycle_keys:
            continue
        by_bench.setdefault(bench, []).append(
            (cycle_keys.index(key), float(recall))
        )

    if not by_bench:
        ax.text(0.5, 0.5, "no data", ha="center", va="center",
                fontsize=14, color="gray", transform=ax.transAxes)
        ax.set_axis_off()
        ax.set_title("Recall trajectory (no data)")
    else:
        for bench, points in sorted(by_bench.items()):
            xs, ys = zip(*sorted(points))
            ax.plot(xs, ys, marker="o", label=bench)
        ax.set_xlabel("Cycle (ordinal)")
        ax.set_ylabel("Recall against historical baseline")
        ax.set_xticks(range(len(cycle_keys)))
        ax.set_xticklabels(cycle_keys, rotation=30, ha="right", fontsize=8)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, linestyle=":", alpha=0.4)
        ax.legend(loc="best", fontsize=8)
        # Vertical dashed lines at lever pulls (cycles with a Lever
        # Calibration Log entry whose name appears in the cycle key).
        for entry in lever_log:
            for i, key in enumerate(cycle_keys):
                if entry["cycle_name"].split()[0] in key:
                    ax.axvline(i, color="gray", linestyle="--", alpha=0.4)
                    ax.text(
                        i, 1.02, entry["cycle_name"][:30],
                        fontsize=7, ha="center", rotation=20, color="gray",
                    )
                    break
        ax.set_title("Recall trajectory across cycles")

    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Chart 4 — Lever interaction graph (Mermaid)
# ---------------------------------------------------------------------------


def render_lever_interaction_graph(
    lever_log: list[dict[str, Any]],
    output_mermaid_path: Path,
    output_png_path: Path | None,
) -> None:
    """Emit ``graph LR`` Mermaid source describing lever→pattern
    interactions observed across cycles. Tries to render to PNG via
    mermaid-cli if available; otherwise the .mermaid source is the
    final artifact."""
    lines = ["graph LR"]
    # Hand-curated edges from the v1.5.4 cycle 1 audit:
    # Pattern 7 boosted mount-context coverage but displaced
    # PathRewrite + AllowContentEncoding (per audit + log).
    lines.append('    %% Edges from v1.5.4 cycle 1 (chi-1.3.45) — '
                 'positive=boost, negative=displace.')
    lines.append('    L1["Lever 1: Pattern 7 (composition)"] -->|+| MC["Mount-context bugs (BUG-004/007/008/009)"]')
    lines.append('    L1 -.->|−| PR["PathRewrite (BUG-005)"]')
    lines.append('    L1 -.->|−| ACE["AllowContentEncoding (BUG-010)"]')
    if any("displacement-recovery" in e["cycle_name"] for e in lever_log):
        lines.append('    L1B["Lever 1b: Pattern 7 budget cap 2-3"] -.->|hyp+| PR')
        lines.append('    L1B -.->|hyp+| ACE')
        lines.append('    L1B -->|preserve| MC')
    output_mermaid_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # If mermaid-cli (mmdc) is on PATH, render to PNG.
    if output_png_path is None:
        return
    mmdc = shutil.which("mmdc")
    if mmdc is None:
        return
    try:
        subprocess.run(
            [mmdc, "-i", str(output_mermaid_path),
             "-o", str(output_png_path),
             "-b", "white"],
            check=True,
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Mermaid render failure is non-fatal — the .mermaid source
        # remains the canonical output.
        pass


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def visualize(cycle_dir: Path, workspace_root: Path | None = None) -> list[Path]:
    """Generate all four charts into ``<cycle_dir>/visualizations/``.
    Returns the list of artifact paths actually written."""
    cycle_dir = Path(cycle_dir).resolve()
    if not cycle_dir.is_dir():
        raise FileNotFoundError(f"cycle_dir does not exist: {cycle_dir}")

    workspace = workspace_root or DEFAULT_WORKSPACE_ROOT
    cycles_root = workspace / "Calibration Cycles"

    metrics_dir = REPO_ROOT / "metrics" / "regression_replay"
    repos_archive = REPO_ROOT / "repos" / "archive"
    log_path = REPO_ROOT / "docs" / "process" / "Lever_Calibration_Log.md"

    cells = load_cells(metrics_dir)
    lever_log = load_lever_log(log_path)
    # cycles loaded but not currently consumed by any chart; reserved
    # for future per-cycle annotations.
    load_cycles(cycles_root)

    out_dir = cycle_dir / "visualizations"
    out_dir.mkdir(exist_ok=True)

    artifacts: list[Path] = []

    bug_path = out_dir / "per_bug_cycle_heatmap.png"
    render_per_bug_cycle_heatmap(cells, repos_archive, bug_path)
    artifacts.append(bug_path)

    lev_path = out_dir / "lever_benchmark_heatmap.png"
    render_lever_benchmark_heatmap(lever_log, cells, lev_path)
    artifacts.append(lev_path)

    traj_path = out_dir / "recall_trajectory.png"
    render_recall_trajectory(cells, lever_log, traj_path)
    artifacts.append(traj_path)

    mermaid_path = out_dir / "lever_interaction.mermaid"
    interaction_png = out_dir / "lever_interaction.png"
    render_lever_interaction_graph(lever_log, mermaid_path, interaction_png)
    artifacts.append(mermaid_path)
    if interaction_png.is_file():
        artifacts.append(interaction_png)

    return artifacts


def main(argv: list[str] | None = None) -> int:
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
            name='visualize_calibration',
            summary=(
            "Render calibration history as HTML/SVG charts from a "
            "benchmark archive. "
            ),
            role=(
            "Operator-side analytics — NOT used during a playbook "
            "run. Reads the calibration journal and emits visual "
            "reports for release-prep review. "
            ),
            usage_hint='python3 -m bin.visualize_calibration --out report.html',
        )
        return 0

    # v1.5.7 090a: full attribution banner at top of --help.
    _print_help_banner(_argv_list_089x)

    parser = argparse.ArgumentParser(
        prog="visualize_calibration",
        description=__doc__,
    )
    parser.add_argument(
        "cycle_dir",
        type=Path,
        help="Path to a Calibration Cycles/<date>-<name>/ directory.",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help=(
            "Path to the AI-Driven Development/Quality Playbook/ workspace "
            "root. Defaults to ~/Documents/AI-Driven Development/Quality "
            "Playbook/."
        ),
    )
    args = parser.parse_args(argv)
    try:
        artifacts = visualize(args.cycle_dir, args.workspace_root)
    except FileNotFoundError as exc:
        print(f"visualize_calibration: {exc}", file=sys.stderr)
        return 64  # EX_USAGE
    for path in artifacts:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
