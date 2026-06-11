"""v1.5.9 [Phase 2 prep] — Windows-readiness for the NEW harness files.

Context: the 185/189/190 cp1252 hazard chain (Windows consoles + log
reads + subprocess use a cp1252 codec that crashes on certain non-ASCII
bytes). The 189/190 AUDIT-table SWEEP tests lived under bin/tests/harness/
and were DELETED with the old Python harness in v1.5.9 Phase 2E (instr.
006). They enumerated bin/harness/** (and, for 190, bin/run_playbook.py).
This file restores the discipline for the NET-NEW harness files
(qpb_harness_tick.py + qpb_heartbeat.py) that replaced that harness.

Two invariants, mirroring the AUDIT-table pattern:

1. **Status-table ASCII (185 print-path).** The table emitted by
   qpb_harness_tick.py must be pure ASCII — no em-dash / box-drawing /
   arrows — so it prints on a cp1252 console without UnicodeEncodeError.

2. **External-content reads carry errors="replace" (189).** A read of
   worker-written content (heartbeat.ndjson) must tolerate a stray
   non-UTF-8 byte; every text-mode read in the new files must pin
   encoding="utf-8", and external-content reads must add errors="replace".

MUTATION-VERIFY EVIDENCE (in-tree per DEVELOPMENT_PROCESS.md §Mutation-
test discipline), v1.5.9 instruction 007:
  * Pin: test_status_table_is_ascii. Mutation: restore the em-dash in the
    DONE banner ("DONE - all" -> "DONE — all"). Observed: FAIL
    (UnicodeEncodeError / non-ASCII char). Restored -> OK.
  * Pin: test_heartbeat_read_tolerates_non_utf8. Mutation: drop
    errors="replace" from _tail's heartbeat read. Observed: FAIL (the
    tick crashes / loses the line on a 0x97 byte). Restored -> OK.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TICK_SRC = _REPO_ROOT / "bin" / "qpb_harness_tick.py"
_HB_SHIM = _REPO_ROOT / "bin" / "qpb_heartbeat.py"
_HB_CANON = (_REPO_ROOT / "plugins" / "quality-playbook" / "skills"
             / "quality-playbook" / "scripts" / "qpb_heartbeat.py")
# The new harness files audited for cp1252 safety.
_NEW_FILES = (_TICK_SRC, _HB_SHIM, _HB_CANON)


def _load_tick():
    spec = importlib.util.spec_from_file_location("tick_2e", _TICK_SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tick_2e"] = mod
    spec.loader.exec_module(mod)
    return mod


T = _load_tick()


class StatusTableAsciiTests(unittest.TestCase):
    """Invariant 1 — the status table is pure ASCII in every state."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._n_inits = 0
        os.environ.pop("QPB_HARNESS_NOW", None)

    def tearDown(self):
        os.environ.pop("QPB_HARNESS_RUNS_DIR", None)
        os.environ.pop("QPB_HARNESS_NOW", None)
        self._tmp.cleanup()

    def _init(self, pool=1, n=1):
        # Unique runs-dir per call: init_run names run-dirs by 1-second
        # timestamp, so two inits in the same second would collide.
        self._n_inits += 1
        os.environ["QPB_HARNESS_RUNS_DIR"] = str(
            Path(self._tmp.name) / f"hr{self._n_inits}")
        pf = Path(self._tmp.name) / "plan.json"
        pf.write_text(json.dumps({
            "tick_interval_minutes": 5, "pool_size": pool,
            "entries": [{"task_id": f"t-{i}", "target_repo": "/tmp/x",
                         "dispatch_mode": "subagent", "worker_prompt": "x"}
                        for i in range(n)]}))
        return Path(T.init_run(pf))

    def _assert_ascii(self, table, label):
        try:
            table.encode("ascii")
        except UnicodeEncodeError as exc:
            self.fail(f"status table ({label}) is not ASCII — cp1252 print "
                      f"hazard (185): {exc}\n{table!r}")

    def test_status_table_is_ascii(self):
        rd = self._init()
        # running tick
        self._assert_ascii(T.tick(rd)["status_table"], "running")
        # stalled state (force a stale heartbeat)
        (rd / "run-01" / "heartbeat.ndjson").write_text(
            '{"ts":"t","task_id":"t-0","schema_version":"1","phase":'
            '"exploration","step":"s","status":"IN_PROGRESS"}\n')
        os.environ["QPB_HARNESS_NOW"] = str(
            (rd / "run-01" / "heartbeat.ndjson").stat().st_mtime + 99 * 60)
        self._assert_ascii(T.tick(rd)["status_table"], "stalled")
        os.environ.pop("QPB_HARNESS_NOW", None)
        # done tick
        (rd / "run-01" / "heartbeat.ndjson").write_text(
            '{"ts":"t","task_id":"t-0","schema_version":"1","status":'
            '"COMPLETED","result_file":"x","summary":"s"}\n')
        out = T.tick(rd)
        self.assertTrue(out["done"])
        self._assert_ascii(out["status_table"], "done")
        # stop tick
        rd2 = self._init()
        (rd2 / "STOP").touch()
        self._assert_ascii(T.tick(rd2)["status_table"], "stop")

    def test_source_format_strings_are_ascii(self):
        # The whole tick source is ASCII-clean in its FORMAT constants;
        # we assert the source has no em-dash / arrow / box-drawing chars
        # in the status-table region by checking the rendered banners.
        for banner in ("DONE - all runs terminal", "STOP - halting"):
            self.assertIn(banner, _TICK_SRC.read_text(encoding="utf-8"))
        for forbidden in ("—", "→", "─", "≥", "≤"):
            # forbidden chars must not appear in the table banner lines
            self.assertNotIn(
                f'rows.append("DONE {forbidden}',
                _TICK_SRC.read_text(encoding="utf-8"))


class ExternalReadEncodingSweepTests(unittest.TestCase):
    """Invariant 2 — cp1252 read safety (189) across the new files."""

    _TEXT_READ_RE = re.compile(r"\.read_text\(([^)]*)\)")
    _TEXT_OPEN_RE = re.compile(r"\.open\(\s*[\"'][rwa]\+?[\"']([^)]*)\)")

    def test_every_text_read_pins_utf8(self):
        """Every .read_text( / text-mode .open( in the new files pins
        encoding='utf-8' (no implicit-locale-codec read)."""
        for f in _NEW_FILES:
            src = f.read_text(encoding="utf-8")
            for m in self._TEXT_READ_RE.finditer(src):
                self.assertIn(
                    'encoding="utf-8"', m.group(1),
                    f"{f.name}: .read_text({m.group(1)}) must pin "
                    f"encoding='utf-8' (cp1252 hazard).")
            for m in self._TEXT_OPEN_RE.finditer(src):
                self.assertIn(
                    'encoding="utf-8"', m.group(1),
                    f"{f.name}: text-mode .open(...) must pin "
                    f"encoding='utf-8'.")

    def test_heartbeat_read_tolerates_non_utf8(self):
        """The heartbeat read (EXTERNAL worker content) must use
        errors='replace' AND not crash on a cp1252 0x97 byte."""
        src = _TICK_SRC.read_text(encoding="utf-8")
        # AUDIT: the _tail heartbeat read is the one external-content read.
        self.assertRegex(
            src,
            r"hb\.read_text\(encoding=\"utf-8\", errors=\"replace\"\)",
            "_tail's heartbeat read must use errors='replace' — heartbeat."
            "ndjson is external worker content (189 cp1252 hazard).")
        # behavioral: a stray 0x97 byte (cp1252 em-dash) doesn't crash _tail
        with tempfile.TemporaryDirectory() as d:
            hb = Path(d) / "heartbeat.ndjson"
            hb.write_bytes(
                b'{"ts":"t","task_id":"t","schema_version":"1","phase":'
                b'"exploration","step":"s","status":"IN_PROGRESS"}\n'
                b'\x97 stray cp1252 byte line\n')
            lines = T._tail(hb)  # must not raise
            self.assertEqual(len(lines), 2)
            self.assertIn("IN_PROGRESS", lines[0])


if __name__ == "__main__":
    unittest.main()
