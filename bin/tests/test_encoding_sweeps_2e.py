"""v1.5.9 — cp1252 encoding AUDIT sweeps, restored post-harness-deletion.

The 185/189/190 cp1252 hazard chain (Windows consoles + log/heartbeat
reads + subprocess use a cp1252 codec that crashes on certain non-ASCII
bytes — see ai_context/DEVELOPMENT_PROCESS.md § AUDIT-table invariant test
pattern). The original 189 (log-read) and 190 (subprocess) AUDIT SWEEP
tests lived under bin/tests/harness/ and were DELETED with the old Python
harness in v1.5.9 Phase 2E (instruction 006) — they had enumerated
bin/harness/** (and, for 190, bin/run_playbook.py). That left the SURVIVING
production tree unswept. This file rebuilds both sweeps scoped to the
surviving tree (bin/**/*.py minus tests, + the bundled skill scripts).

RELATIONSHIP to bin/tests/test_harness_windows_readiness_2e.py: that file
is the harness-FILES-specific layer — it pins the qpb_harness_tick.py
status-table ASCII (185) and a BEHAVIORAL 0x97-byte tolerance test of the
heartbeat read. THIS file is the GENERAL surviving-tree layer — AST sweeps
asserting the contract at EVERY matching site. No duplicated assertions:
the harness file tests behavior + the table; these tests scan source.

Two sweeps:

190 (subprocess) — every subprocess.run/Popen/call/check_output with
text=True (or universal_newlines=True) in production code must pass
encoding="utf-8" AND an errors= handler (subprocess output is external by
nature: git/npm/claude/tool stdout can carry non-UTF-8 bytes). AUDIT: 17
text-mode sites at the 2026-06-11 rebuild; 12 were non-compliant and
FIXED (added encoding="utf-8", errors="replace"); 0 allow-listed.

189 (external log/heartbeat reads) — every text read whose target is a
LOG or a HEARTBEAT file (the external-output read class the original 189
covered) must carry an errors= handler. AUDIT:
  * qpb_harness_tick.py:_tail heartbeat read — errors="replace" (instr 007)
  * quality_gate.py check_heartbeat_sidecar heartbeat read — FIXED here
  * visualize_calibration.py lever-log read — FIXED here
  * run_playbook.py gate-log read — errors="ignore" (pre-existing, SAFE)
Adopter-doc reads (e.g. reference_docs_ingest._read_text) are NOT in this
class — they guard with an explicit UnicodeDecodeError->clean-error path
and are outside the log/heartbeat sweep by design.

MUTATION-VERIFY EVIDENCE (in-tree per DEVELOPMENT_PROCESS.md), instr 008:
  * 190 pin: drop errors="replace" from bin/regression_replay.py's git
    subprocess.run → test_subprocess_textmode_pins_encoding_and_errors
    FAILs. Restored -> OK.
  * 189 pin: drop errors="replace" from quality_gate.py's heartbeat read →
    test_external_log_and_heartbeat_reads_pin_errors FAILs. Restored -> OK.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _production_files() -> list[Path]:
    """Surviving production scope: bin/**/*.py excluding tests, + the
    bundled skill scripts."""
    files = [p for p in (_REPO_ROOT / "bin").rglob("*.py")
             if "tests" not in p.parts]
    files += list((_REPO_ROOT / "plugins" / "quality-playbook" / "skills"
                   / "quality-playbook" / "scripts").glob("*.py"))
    return sorted(set(files))


def _is_true(v) -> bool:
    return isinstance(v, ast.Constant) and v.value is True


_SUBPROCESS_FNS = {"run", "Popen", "call", "check_output", "check_call"}


class SubprocessEncodingSweep190Tests(unittest.TestCase):
    """190: text-mode subprocess output must be UTF-8 + errors-handled."""

    # file:line allow-list of justified exceptions (empty — all sites
    # comply at the 008 rebuild). Add "path:line: reason" if ever needed.
    _ALLOW = frozenset()

    def test_subprocess_textmode_pins_encoding_and_errors(self):
        violations = []
        for f in _production_files():
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            rel = f.relative_to(_REPO_ROOT).as_posix()
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr in _SUBPROCESS_FNS):
                    continue
                kw = {k.arg: k.value for k in node.keywords if k.arg}
                if not (_is_true(kw.get("text"))
                        or _is_true(kw.get("universal_newlines"))):
                    continue
                key = f"{rel}:{node.lineno}"
                if key in self._ALLOW:
                    continue
                if "encoding" not in kw or "errors" not in kw:
                    violations.append(
                        f"{key}: subprocess.{node.func.attr}(text=True) must "
                        f"pass encoding=\"utf-8\", errors=\"replace\" "
                        f"(cp1252 hazard / 190) — "
                        f"encoding={'encoding' in kw} errors={'errors' in kw}")
        self.assertEqual(violations, [], "190 subprocess-encoding sweep:\n"
                         + "\n".join(violations))


class ExternalLogHeartbeatReadSweep189Tests(unittest.TestCase):
    """189: reads of external LOG / HEARTBEAT files must handle decode
    errors (errors="replace"/"ignore") — they carry subprocess/worker
    output that can be non-UTF-8 on a cp1252 host."""

    # The read's target expression (receiver or first open() arg source)
    # matches one of these => it's an external log/heartbeat read.
    # `hb` is the heartbeat-buffer read receiver convention across the
    # surviving tree (qpb_harness_tick._tail, quality_gate.check_heartbeat_
    # sidecar); log_path / *.log / gate_log are the external-log reads.
    _EXTERNAL_READ_RE = re.compile(
        r"heartbeat|gate_log|log_path|\.log\b|_log\b|stdout_log|stderr_log"
        r"|\bhb\b")

    _READ_ATTRS = {"read_text", "read"}
    _ALLOW = frozenset()

    def _read_target_src(self, node: ast.Call, src_lines) -> str:
        try:
            if isinstance(node.func, ast.Attribute):
                seg = ast.get_source_segment(
                    "\n".join(src_lines), node.func.value)
                if seg:
                    return seg
            if node.args:
                seg = ast.get_source_segment(
                    "\n".join(src_lines), node.args[0])
                if seg:
                    return seg
        except Exception:
            pass
        return ""

    def test_external_log_and_heartbeat_reads_pin_errors(self):
        violations = []
        covered = 0
        for f in _production_files():
            text = f.read_text(encoding="utf-8")
            src_lines = text.splitlines()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            rel = f.relative_to(_REPO_ROOT).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                is_read = False
                if (isinstance(node.func, ast.Attribute)
                        and node.func.attr in self._READ_ATTRS):
                    is_read = True
                elif isinstance(node.func, ast.Name) and node.func.id == "open":
                    is_read = True
                if not is_read:
                    continue
                target = self._read_target_src(node, src_lines)
                # also consider the whole call line for the pattern
                line_src = src_lines[node.lineno - 1] if node.lineno - 1 < len(src_lines) else ""
                if not self._EXTERNAL_READ_RE.search(target + " " + line_src):
                    continue
                kw = {k.arg: k.value for k in node.keywords if k.arg}
                key = f"{rel}:{node.lineno}"
                if key in self._ALLOW:
                    continue
                covered += 1
                if "errors" not in kw:
                    violations.append(
                        f"{key}: external log/heartbeat read "
                        f"({target[:40]!r}) must pass errors=\"replace\" "
                        f"(cp1252 hazard / 189)")
        self.assertEqual(violations, [], "189 external-read sweep:\n"
                         + "\n".join(violations))
        # Guard against the sweep silently matching nothing (regex rot).
        self.assertGreater(covered, 0,
                           "189 sweep matched ZERO external log/heartbeat "
                           "reads — the detection regex may be broken.")


if __name__ == "__main__":
    unittest.main()
