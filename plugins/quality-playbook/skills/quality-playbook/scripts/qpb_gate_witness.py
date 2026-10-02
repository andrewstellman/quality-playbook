#!/usr/bin/env python3
"""qpb_gate_witness — the parent's own gate run, compared with the log
(v1.6.1 [S]).

Why: on 2026-05-16 a delegated run hand-wrote
``quality/results/quality-gate.log`` reading PASS while the real gate
reported 14 FAIL, and the parent trusted the log. v1.6.1 allows phases
to run in per-phase subagents on one condition: after every Phase 6 the
PARENT session runs this script itself and pastes its output in its own
chat. The script re-runs the gate the same way adopters do
(``python3 <quality_gate.py> .`` from the target repo root), extracts
the ``Total:`` and ``RESULT:`` lines, and compares them with the same
lines in ``quality/results/quality-gate.log``.

Usage:
  qpb_gate_witness <target-repo>

Exit codes:
  0  the gate's ``RESULT:`` line equals the log's, and its ``Total:``
     line equals the log's once the trailing ``, N WARN`` part is
     removed from both
  1  they differ (a ``MISMATCH`` line names which), the verdict state
     differs, the log carries no verdict state, or the gate printed
     no verdict lines

v1.6.1 [council-1]: the WARN count is left out of the comparison
because it can change between the subagent's gate run and the
parent's: the orchestrator writes AGENTS.md after the gate passes, and
a missing AGENTS.md is one WARN. FAIL / DECISION / CLEANUP counts and
the RESULT line are still compared exactly. Both full lines are
printed.

v1.6.1 [council-2]: a WARN can still change the verdict state (the
"no test functions found" WARN turns a pass "shallow"), so the witness
also compares the verdict state. Source, in order: the LAST
``::QPB::`` gate sentinel's ``gate_result`` + ``verdict_state``; for
a log with no sentinel (pre-1.6.1), the operator lead line
(``[PASS]/[WARN]/[FAIL] GATE ...``). A log with neither is a MISMATCH:
its verdict state cannot be witnessed.
  2  ``quality/results/quality-gate.log`` is missing, or the target /
     ``quality_gate.py`` cannot be found

The script never writes to the target: it reads the log and leaves it
as the subagent wrote it. Stdlib only, plus the bundled ``_purpose``
banner via the same 3-step anchored fallback qpb_phase.py uses.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


_NAME = "qpb_gate_witness"
_SUMMARY = (
    "Re-run quality_gate.py from the parent session and compare its "
    "verdict lines with quality/results/quality-gate.log."
)
_USAGE = "qpb_gate_witness <target-repo>"

LOG_REL = Path("quality") / "results" / "quality-gate.log"
_GATE_TIMEOUT_S = 1800


def _resolve_print_command_intro():
    """089x self-describing banner via the same 3-step anchored
    fallback qpb_phase.py uses (package / flat / path-load)."""
    try:
        from bin._purpose import (  # type: ignore[import]
            print_command_intro as _pci,
        )
        return _pci
    except ImportError:
        pass
    try:
        from _purpose import (  # type: ignore[no-redef, import]
            print_command_intro as _pci,
        )
        return _pci
    except ImportError:
        pass
    import importlib.util as _ilu
    _pp = Path(__file__).resolve().parent / "_purpose.py"
    _ps = _ilu.spec_from_file_location("_qpb_purpose_via_witness", _pp)
    if _ps is None or _ps.loader is None:
        raise ImportError(
            f"qpb_gate_witness: cannot resolve _purpose at {_pp}")
    _mod = _ilu.module_from_spec(_ps)
    sys.modules[_ps.name] = _mod
    _ps.loader.exec_module(_mod)
    return _mod.print_command_intro


def _print_intro() -> None:
    _resolve_print_command_intro()(
        name=_NAME,
        summary=_SUMMARY,
        role=(
            "v1.6.1 [S] — when phases ran in subagents, the parent "
            "session runs this after every Phase 6 and pastes its "
            "output; exit 1 (MISMATCH) means the log does not match "
            "the gate and the run stops."
        ),
        usage_hint=_USAGE,
    )


def find_gate_script() -> Optional[Path]:
    """Locate quality_gate.py relative to this file. QPB clone: the
    sibling in ``scripts/``. Adopter install / channel bundle: this
    file is ``<install_root>/bin/qpb_gate_witness.py`` and the gate is
    ``<install_root>/quality_gate.py``."""
    here = Path(__file__).resolve().parent
    for cand in (here / "quality_gate.py", here.parent / "quality_gate.py"):
        if cand.is_file():
            return cand
    return None


def verdict_lines(text: str) -> "tuple[Optional[str], Optional[str]]":
    """Return the LAST ``Total:`` line and the LAST ``RESULT:`` line in
    ``text`` (stripped), or None for each that is absent. Last wins
    because the gate prints its verdict at the end, after any
    per-check output."""
    total = result = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("Total:"):
            total = line
        elif line.startswith("RESULT:"):
            result = line
    return total, result


_SENTINEL_PREFIX = "::QPB::"
_LEAD_RE = re.compile(r"^\[(?:PASS|WARN|FAIL)\] GATE ")


def gate_sentinel_state(text: str) -> "Optional[tuple[str, str]]":
    """v1.6.1 [council-2]: ``(gate_result, verdict_state)`` from the
    LAST ``::QPB::`` line whose payload has ``kind == "gate"``, or
    None when there is no such line (pre-1.6.1 log, or a hand-written
    one). Unparseable sentinel lines are skipped."""
    found = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith(_SENTINEL_PREFIX):
            continue
        try:
            payload = json.loads(line[len(_SENTINEL_PREFIX):].strip())
        except ValueError:
            continue
        if isinstance(payload, dict) and payload.get("kind") == "gate":
            found = (str(payload.get("gate_result")),
                     str(payload.get("verdict_state")))
    return found


def lead_line(text: str) -> Optional[str]:
    """v1.6.1 [council-2]: the LAST operator lead line
    (``[PASS] GATE ...`` / ``[WARN] GATE ...`` / ``[FAIL] GATE ...``),
    stripped, or None."""
    found = None
    for raw in text.splitlines():
        line = raw.strip()
        if _LEAD_RE.match(line):
            found = line
    return found


def compare_verdict_state(gate_text: str, log_text: str) -> Optional[str]:
    """v1.6.1 [council-2]: None when the log's verdict state equals the
    gate's, else a one-line reason. Uses the sentinel when the log has
    one, else the lead line; a log with neither cannot be witnessed."""
    log_state = gate_sentinel_state(log_text)
    if log_state is not None:
        gate_state = gate_sentinel_state(gate_text)
        if gate_state != log_state:
            return (f"verdict state differs (::QPB:: gate_result/"
                    f"verdict_state: gate {gate_state}, log {log_state})")
        return None
    log_lead = lead_line(log_text)
    if log_lead is not None:
        gate_lead = lead_line(gate_text)
        if gate_lead != log_lead:
            return (f"verdict state differs (lead line: gate "
                    f"{gate_lead!r}, log {log_lead!r})")
        return None
    return ("quality-gate.log has no ::QPB:: gate sentinel and no "
            "[PASS]/[WARN]/[FAIL] GATE lead line, so its verdict state "
            "cannot be witnessed")


_WARN_TAIL_RE = re.compile(r",\s*\d+\s+WARN\s*$")


def total_without_warn(total: Optional[str]) -> Optional[str]:
    """v1.6.1 [council-1]: the ``Total:`` line with its trailing
    ``, N WARN`` part removed (WARN counts may legitimately change
    after the gate passes, e.g. AGENTS.md written later)."""
    if total is None:
        return None
    return _WARN_TAIL_RE.sub("", total)


def run_gate(gate: Path, target: Path) -> str:
    """Run the gate exactly as adopters do: ``python3 <gate> .`` with
    the target repo root as cwd. Returns combined stdout+stderr."""
    proc = subprocess.run(
        [sys.executable, str(gate), "."],
        cwd=str(target),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_GATE_TIMEOUT_S,
    )
    return proc.stdout or ""


def main(argv: "list[str] | None" = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list or argv_list in (["--help"], ["-h"]):
        _print_intro()
        return 0
    if len(argv_list) != 1:
        print(f"Usage: {_USAGE}", file=sys.stderr)
        return 2
    target = Path(argv_list[0]).resolve()
    if not (target / "quality").is_dir():
        print(f"ERROR: {target} has no quality/ directory", file=sys.stderr)
        return 2
    log_path = target / LOG_REL
    if not log_path.is_file():
        print(f"LOG MISSING: {LOG_REL} not found under {target}")
        return 2
    gate = find_gate_script()
    if gate is None:
        print("ERROR: quality_gate.py not found next to "
              f"{Path(__file__).resolve()} or one directory up",
              file=sys.stderr)
        return 2

    gate_text = run_gate(gate, target)
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    gate_total, gate_result = verdict_lines(gate_text)
    log_total, log_result = verdict_lines(log_text)

    print(f"Gate run by parent ({gate}):")
    print(f"  {gate_total or '<no Total: line>'}")
    print(f"  {gate_result or '<no RESULT: line>'}")
    print(f"Log ({LOG_REL}):")
    print(f"  {log_total or '<no Total: line>'}")
    print(f"  {log_result or '<no RESULT: line>'}")

    if gate_total is None or gate_result is None:
        print("MISMATCH: the gate printed no Total:/RESULT: verdict "
              "lines; stop and report.")
        return 1
    diffs = []
    if total_without_warn(gate_total) != total_without_warn(log_total):
        diffs.append("Total:")
    if gate_result != log_result:
        diffs.append("RESULT:")
    if diffs:
        print(f"MISMATCH: {' and '.join(diffs)} line(s) differ between "
              "the gate and quality-gate.log; stop and report.")
        return 1
    # v1.6.1 [council-2]: the verdict state (solid / shallow /
    # decisions / failed) can hinge on a WARN, so compare it too.
    state_diff = compare_verdict_state(gate_text, log_text)
    if state_diff is not None:
        print(f"MISMATCH: {state_diff}; stop and report.")
        return 1
    if gate_total != log_total:
        print("MATCH: the WARN count differs, but the RESULT: line, the "
              "FAIL / DECISION / CLEANUP counts and the verdict state "
              "equal the gate's.")
        return 0
    print("MATCH: the log's Total: and RESULT: lines and its verdict "
          "state equal the gate's.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
