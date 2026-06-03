"""divergence_execution.py — Phase 4 Part B.2: REQ-to-gate-check
mapper + aggregator + reporter.

Reads pass_c_formal.jsonl and the {run_id -> {check_id ->
GateResult}} map from execution_gate_loader.load_archived_runs().
For each REQ that has a non-empty `gate_check_ids` field, the
module:

  1. Counts pass/fail of each associated check across the K most
     recent archived runs.
  2. If at least one of those checks failed in ≥1 run, emits an
     execution divergence record with confidence = high / medium /
     low per DQ-4-3.

REQs without `gate_check_ids` (the QPB self-audit case — none of
the 1369 REQs carry the field per Round 7) are skipped silently;
the per-REQ skip is logged via `gate_check_ids: missing`.

QPB self-audit expected outcome: empty pass_e_execution_divergences
.jsonl. This is documented and accepted in Phase 4 brief DQ-4-3.

Strict scope: structured-result aggregation only. No LLM evaluation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bin.skill_derivation.execution_gate_loader import (
    GateResult,
    load_archived_runs,
)


DEFAULT_K = 5
HIGH_CONFIDENCE_FAILS = 3  # ≥3 fails in ≥3 runs


@dataclass
class ExecutionDivergenceConfig:
    formal_path: Path  # input: pass_c_formal.jsonl
    previous_runs_dir: Optional[Path]
    output_path: Path  # output: pass_e_execution_divergences.jsonl
    sections_path: Path
    k_runs: int = DEFAULT_K
    starting_div_idx: int = 1


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _section_heading(sections_path: Path, document: str, section_idx) -> str:
    if section_idx is None or not sections_path.is_file():
        return ""
    payload = json.loads(sections_path.read_text(encoding="utf-8"))
    for s in payload.get("sections", []):
        if s.get("section_idx") == section_idx and s.get("document") == document:
            return s.get("heading", "") or ""
    return ""


def _confidence(fail_count: int, total_runs: int) -> str:
    """DQ-4-3 confidence ladder.
    - low: <3 archived runs available.
    - medium: 1-2 fails.
    - high: ≥3 fails in ≥3 runs.
    """
    if total_runs < 3:
        return "low"
    if fail_count >= HIGH_CONFIDENCE_FAILS:
        return "high"
    return "medium"


def run_divergence_execution(config: ExecutionDivergenceConfig) -> dict:
    """Drive Part B.2 end-to-end. Returns summary dict.

    Output schema per Phase 4 brief Part B.2.
    """
    reqs = _read_jsonl(config.formal_path)
    archived = load_archived_runs(config.previous_runs_dir)

    # Sort run_ids by name (the convention is run-YYYY-MM-DD or
    # similar; lexicographic sort approximates chronological for
    # ISO-shaped IDs). Take the last K.
    run_ids = sorted(archived.keys())
    recent_run_ids = run_ids[-config.k_runs:] if config.k_runs > 0 else run_ids

    output_lines: list[str] = []
    div_idx = config.starting_div_idx
    skipped_no_gate_check_ids = 0
    flagged = 0

    for req in reqs:
        gate_check_ids = req.get("gate_check_ids") or []
        if not gate_check_ids:
            skipped_no_gate_check_ids += 1
            continue

        failed_run_ids: list[str] = []
        for run_id in recent_run_ids:
            run_results = archived.get(run_id) or {}
            for cid in gate_check_ids:
                gr: Optional[GateResult] = run_results.get(cid)
                if gr is not None and gr.status == "fail":
                    failed_run_ids.append(run_id)
                    break  # one fail per run is enough for the count

        if not failed_run_ids:
            continue

        fail_count = len(failed_run_ids)
        total_runs = len(recent_run_ids)
        confidence = _confidence(fail_count, total_runs)

        # Default disposition mapping (Council can override):
        # - high confidence + multiple consistent fails -> code-fix
        #   (the prose is right; the code/agent isn't matching it).
        # - low confidence (<3 archived runs) -> mis-read default
        #   (not enough evidence to commit).
        # - medium -> spec-fix (prose may be too aggressive).
        if confidence == "high":
            disp = "code-fix"
        elif confidence == "low":
            disp = "mis-read"
        else:
            disp = "spec-fix"

        source_document = req.get("source_document") or "SKILL.md"
        section_idx = req.get("section_idx")
        rec = {
            "divergence_id": f"DIV-EXEC-{div_idx:03d}",
            "divergence_type": "execution",
            "req_id": req.get("id"),
            "gate_check_ids": list(gate_check_ids),
            "failed_run_ids": failed_run_ids,
            "fail_count": fail_count,
            "total_runs_considered": total_runs,
            "confidence": confidence,
            "rationale": (
                f"REQ {req.get('id')} has {len(gate_check_ids)} associated "
                f"gate check(s); {fail_count} of {total_runs} archived "
                f"runs failed at least one. Confidence={confidence}."
            ),
            "provisional_disposition": disp,
            "triage_batch_key": (
                f"{source_document}::{section_idx}"
                if section_idx is not None
                else f"{source_document}::unknown"
            ),
        }
        output_lines.append(json.dumps(rec, sort_keys=False))
        div_idx += 1
        flagged += 1

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.output_path.with_name(config.output_path.name + ".tmp")
    tmp.write_text(
        ("\n".join(output_lines) + "\n") if output_lines else "",
        encoding="utf-8",
    )
    os.replace(tmp, config.output_path)

    return {
        "divergences_emitted": flagged,
        "reqs_skipped_no_gate_check_ids": skipped_no_gate_check_ids,
        "archived_runs_considered": len(recent_run_ids),
        "total_archived_runs": len(run_ids),
    }


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.divergence_execution',
        summary=(
            "Execution-divergence detector — flags spec passages that "
            "diverge from implementation behavior at run-time. "
        ),
        role=(
            "Imported by skill_derivation passes B/C as one of the four "
            "divergence detectors that feed Phase 2 bug generation. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
