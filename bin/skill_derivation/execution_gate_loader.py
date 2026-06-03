"""execution_gate_loader.py — Phase 4 Part B.1: load archived gate
results across previous_runs/.

Reads each subdirectory under <repo_root>/previous_runs/ as one
"archived run", extracts gate results from the structured outputs
that quality_gate.py emits during a run, and returns an in-memory
map:

    {run_id -> {check_id -> {status: "pass"|"fail", rationale: str}}}

Tolerates missing previous_runs/ entirely (returns empty map; this
is QPB's current state per DQ-4-3). Tolerates partial archived
outputs (a run with no gate output is recorded as an empty
check-map under its run_id).

Strict scope per Phase 4 brief Part B: this module reads structured
results only. No LLM evaluation. No parsing of unstructured
reasoning.

Heuristic for gate result extraction: each archived run's
quality/results/quality-gate.log (or .json) contains the gate's
structured output. We parse the log line-by-line for `PASS:` and
`FAIL:` markers — the same shape `quality_gate.py::pass_()` /
`fail()` emit. The check_id is recovered from the line's text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Recognized gate output filenames inside an archived run's
# quality/ directory. We probe each in order; the first hit wins.
_GATE_OUTPUT_CANDIDATES = (
    "quality/results/quality-gate.log",
    "quality/results/quality_gate.log",
    "quality/results/quality_gate.json",
    "quality/results/quality-gate.json",
)

# Regex for the pass_/fail emitter. quality_gate.py prints lines like:
#     "  PASS: <description>"
#     "  <path>:<line>: <reason>"     (fail with structured form)
#     "  FAIL: <description>"          (legacy fail form)
# We extract the check identifier as the first whitespace-stripped
# token of the description (or the path on structured fails).
_PASS_RE = re.compile(r"^\s*PASS:\s+(?P<msg>.+)$")
_FAIL_LEGACY_RE = re.compile(r"^\s*FAIL:\s+(?P<msg>.+)$")
# Structured fail form (Phase 5 r3): "  <path>:<line>?: <reason>"
_FAIL_STRUCTURED_RE = re.compile(
    r"^\s*(?P<path>[^\s:]+(?:/[^\s:]+)*)(?::\d+)?:\s+(?P<reason>.+)$"
)


@dataclass
class GateResult:
    status: str  # "pass" or "fail"
    rationale: str


def _check_id_from_message(msg: str) -> str:
    """Heuristic: pick the first quoted-or-bracketed token, else the
    first word. This is rough; the value matters mostly as a stable
    grouping key across runs. For tests and known shapes (e.g.,
    "BUGS.md exists") the first word is informative."""
    msg = msg.strip()
    # Backtick-quoted token (e.g., "`phase1_finding_count` failed").
    m = re.search(r"`([^`]+)`", msg)
    if m:
        return m.group(1)
    # Bracketed token.
    m = re.search(r"\[([^\]]+)\]", msg)
    if m:
        return m.group(1)
    # Otherwise the first token, stripped of trailing punctuation.
    first = msg.split()[0] if msg.split() else msg
    return first.rstrip(":,.;")


def _parse_gate_log(text: str) -> dict[str, GateResult]:
    """Walk lines; return {check_id -> GateResult}. Last status wins
    if a check_id appears multiple times (latest line is most recent
    state)."""
    results: dict[str, GateResult] = {}
    for raw in text.splitlines():
        m = _PASS_RE.match(raw)
        if m:
            cid = _check_id_from_message(m.group("msg"))
            results[cid] = GateResult(status="pass", rationale=m.group("msg"))
            continue
        m = _FAIL_LEGACY_RE.match(raw)
        if m:
            cid = _check_id_from_message(m.group("msg"))
            results[cid] = GateResult(status="fail", rationale=m.group("msg"))
            continue
        m = _FAIL_STRUCTURED_RE.match(raw)
        if m and ":" in raw:
            # Structured fails always include a path with at least one
            # path separator OR a known path-shaped token; require this
            # to avoid eating PASS lines.
            path = m.group("path")
            if "/" in path or path.endswith(".md") or path.endswith(".py"):
                cid = path
                results[cid] = GateResult(
                    status="fail", rationale=m.group("reason"),
                )
                continue
    return results


def _parse_gate_json(text: str) -> dict[str, GateResult]:
    """Parse a JSON shape: {checks: [{check_id, status, rationale}]}.
    Returns {} on any parse failure."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    items = payload.get("checks") or []
    out: dict[str, GateResult] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        cid = it.get("check_id") or it.get("id")
        status = it.get("status", "").lower()
        if not cid or status not in ("pass", "fail"):
            continue
        out[cid] = GateResult(status=status, rationale=it.get("rationale", ""))
    return out


def load_archived_runs(
    previous_runs_dir: Optional[Path],
) -> dict[str, dict[str, GateResult]]:
    """Return {run_id -> {check_id -> GateResult}}.

    `previous_runs_dir` is typically <repo_root>/previous_runs/. If
    None, missing, or empty: return {}.

    Each immediate child directory is treated as one archived run;
    its name is the run_id. Tolerates missing gate output by recording
    an empty inner map under that run_id.
    """
    out: dict[str, dict[str, GateResult]] = {}
    if previous_runs_dir is None or not previous_runs_dir.is_dir():
        return out
    for child in sorted(previous_runs_dir.iterdir()):
        if not child.is_dir():
            continue
        run_id = child.name
        gate_results: dict[str, GateResult] = {}
        for candidate_rel in _GATE_OUTPUT_CANDIDATES:
            candidate = child / candidate_rel
            if not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8", errors="replace")
            if candidate.suffix == ".json":
                gate_results = _parse_gate_json(text)
            else:
                gate_results = _parse_gate_log(text)
            if gate_results:
                break
        out[run_id] = gate_results
    return out


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.execution_gate_loader',
        summary=(
            "Loader for the skill-derivation execution-gate config (which "
            "divergence detectors are enabled for a given target). "
        ),
        role=(
            "Imported by skill_derivation passes B/C to determine which "
            "detectors to fan out to. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
