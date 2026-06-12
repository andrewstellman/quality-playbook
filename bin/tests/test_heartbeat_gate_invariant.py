"""v1.5.9 Phase 1B — quality_gate.check_heartbeat_sidecar invariant.

The gate carries the harness heartbeat disciplines (Council C-3 / A-1)
into its validation surface: when a run was orchestrated by the harness
(a heartbeat.ndjson sits beside quality/), the gate warns on any line
that isn't valid JSON (A-1 framing) or carries a schema_version other than
"1" or "2" (C-3 drift; Postel — both known versions accepted). Non-blocking
by design — heartbeat is orchestration metadata, not a grading input.

MUTATION-VERIFY EVIDENCE (in-tree per DEVELOPMENT_PROCESS.md §Mutation-
test discipline), v1.5.9 instruction 005 / refreshed 010:
  Pin: test_warns_on_schema_version_drift.
  Mutation: in quality_gate.check_heartbeat_sidecar change the C-3
    comparison `obj.get("schema_version") not in ("1", "2")` to
    `in ("1", "2")`.
  Observed: test_warns_on_schema_version_drift FAILs (a drifted line no
    longer produces the C-3 warning). Restored → OK.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_QG = (_REPO_ROOT / "plugins" / "quality-playbook" / "skills"
       / "quality-playbook" / "scripts" / "quality_gate.py")


def _load_qg():
    spec = importlib.util.spec_from_file_location("quality_gate_hb_test", _QG)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["quality_gate_hb_test"] = mod
    spec.loader.exec_module(mod)
    return mod


QG = _load_qg()


def _run_check(heartbeat_lines):
    """Build a run-dir with quality/ + (optional) heartbeat.ndjson beside
    it, run check_heartbeat_sidecar(q), return captured stdout."""
    tmp = tempfile.mkdtemp()
    run_dir = Path(tmp)
    q = run_dir / "quality"
    q.mkdir()
    if heartbeat_lines is not None:
        (run_dir / "heartbeat.ndjson").write_text(
            "".join(ln + "\n" for ln in heartbeat_lines), encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        QG.check_heartbeat_sidecar(q)
    return buf.getvalue()


def _hb(**fields):
    return json.dumps(fields, separators=(",", ":"))


class HeartbeatGateInvariantTests(unittest.TestCase):

    def test_absent_heartbeat_is_info_only(self):
        out = _run_check(None)
        self.assertIn("not present", out)
        self.assertNotIn("WARN", out)

    def test_clean_heartbeat_passes(self):
        # current emit is v2 (label/data); the terminal sentinel too.
        lines = [
            _hb(ts="t", task_id="x", schema_version="2", label="2:generation",
                status="STARTING", data={"step": "s"}),
            _hb(ts="t", task_id="x", schema_version="2",
                status="COMPLETED", result_file="quality/SUMMARY.md",
                summary="done"),
        ]
        out = _run_check(lines)
        self.assertIn("all heartbeat lines are valid JSON", out)
        self.assertIn("schema_version in {'1','2'}", out)
        self.assertIn("terminal sentinel present", out)
        self.assertNotIn("WARN", out)

    def test_postel_accepts_v1_lines(self):
        # A legacy v1 line (phase/step, schema_version "1") must still pass
        # the C-3 check (Postel: the reader is liberal in what it accepts).
        lines = [
            _hb(ts="t", task_id="x", schema_version="1", phase="exploration",
                step="s", status="STARTING"),
            _hb(ts="t", task_id="x", schema_version="2", label="2:generation",
                status="IN_PROGRESS"),
        ]
        out = _run_check(lines)
        self.assertIn("schema_version in {'1','2'}", out)
        self.assertNotIn("WARN", out)

    def test_warns_on_torn_json_line(self):
        lines = [
            _hb(ts="t", task_id="x", schema_version="2", label="2:generation",
                status="STARTING"),
            '{"ts":"t","task_id":"x" TORN',  # A-1 framing violation
        ]
        out = _run_check(lines)
        self.assertIn("WARN", out)
        self.assertIn("not valid JSON", out)

    def test_warns_on_schema_version_drift(self):
        lines = [
            _hb(ts="t", task_id="x", schema_version="3", label="x",
                status="IN_PROGRESS"),  # C-3 drift — neither 1 nor 2
        ]
        out = _run_check(lines)
        self.assertIn("WARN", out)
        self.assertIn("schema_version", out)
        self.assertIn("C-3", out)

    def test_in_flight_run_no_terminal_is_info(self):
        lines = [
            _hb(ts="t", task_id="x", schema_version="2", label="2:generation",
                status="IN_PROGRESS"),
        ]
        out = _run_check(lines)
        self.assertIn("no terminal sentinel", out)


if __name__ == "__main__":
    unittest.main()
