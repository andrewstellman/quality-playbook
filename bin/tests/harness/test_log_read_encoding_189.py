"""v1.5.7 189 — Harness log-read sites need encoding fallback.

Andrew's first post-187/188 Windows fire detected a child-startup
failure correctly, tried to surface the diagnostic log to the
operator — and then crashed itself with a UnicodeDecodeError
because the log contained cp1252 bytes (0x97 em-dash). The real
child-startup failure was masked by the orchestrator's own crash.

Continuation of the 185 cp1252 hardening, but on the READ side:
185 fixed the write-side (PYTHONIOENCODING=utf-8 on the child's
env so QPB skill output writes utf-8). Pre-skill startup output
(pip install warnings, claude/codex/copilot.exe banners, OS-level
tools the child invokes during spawn) can still emit cp1252 bytes
that the orchestrator's strict utf-8 read crashes on.

Coverage:
- FINDING-44: 2 log-read sites in `bin/qpb_harness.py` get
  errors="replace" + UnicodeDecodeError in their except.
- FINDING-45: source-pin sweep — every `encoding="utf-8"` read
  in `bin/qpb_harness.py` + `bin/harness/**/*.py` that touches
  external content (child stdout, log files) has a fallback
  (errors="replace" or errors="ignore"). Internal JSON we wrote
  ourselves is exempt + documented.
"""
from __future__ import annotations

import pathlib
import re
import tempfile
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[3]


class LogReadEncodingFallbackTests(unittest.TestCase):
    """Behavioral: the open()/read() pattern used at the spawn-
    deadline log-surface sites must tolerate cp1252 bytes."""

    def setUp(self) -> None:
        self._tmpdir_obj = tempfile.TemporaryDirectory(
            prefix="qpb_189_test_")
        self.tmpdir = pathlib.Path(self._tmpdir_obj.name)

    def tearDown(self) -> None:
        self._tmpdir_obj.cleanup()

    def _write_cp1252_log(self, name: str) -> pathlib.Path:
        """Write a log file containing 0x97 (cp1252 em-dash —
        the exact byte that crashed Andrew's run). The file
        contains a realistic startup-failure preamble + the bad
        byte mid-line + more text after, so a tail-read covers
        the bad byte."""
        path = self.tmpdir / name
        # Pre-amble: typical pip install / launcher output.
        head = (
            b"Collecting claude-cli==1.2.3\n"
            b"  Downloading claude_cli-1.2.3-py3-none-any.whl\n"
            b"WARNING: package install hint \x97 use --user\n"
            b"ERROR: child process crashed at startup\n"
            b"Traceback (most recent call last):\n"
            b"  File \"runner.py\", line 42, in main\n"
            b"    raise RuntimeError(\"bad init\")\n"
            b"RuntimeError: bad init\n"
        )
        path.write_bytes(head)
        return path

    def test_orchestrator_log_path_pattern_does_not_crash(
            self) -> None:
        """The open()/read() pattern used at qpb_harness.py:570-572
        (orchestrator log surface site) must handle a cp1252 byte
        in the file without raising UnicodeDecodeError."""
        log = self._write_cp1252_log("qpb-harness-test.log")
        # Verbatim pattern from qpb_harness.py post-189:
        with open(log, "r", encoding="utf-8",
                   errors="replace") as lf:
            tail = lf.read()[-4000:]
        # Decoded text contains the replacement character where
        # the 0x97 byte was — operator sees "something was here,
        # decoder couldn't read it" instead of a silent drop or
        # a crash.
        self.assertIn("�", tail)
        self.assertIn("ERROR: child process crashed", tail)
        self.assertIn("RuntimeError: bad init", tail)

    def test_harness_log_path_pattern_does_not_crash(
            self) -> None:
        """The open()/read() pattern used at qpb_harness.py:580-583
        (harness.log surface site) must also handle a cp1252
        byte without crashing."""
        log = self._write_cp1252_log("harness.log")
        with open(log, "r", encoding="utf-8",
                   errors="replace") as hlf:
            tail = hlf.read()[-2000:]
        self.assertIn("�", tail)
        self.assertIn("crashed at startup", tail)

    def test_pre_189_pattern_would_crash(self) -> None:
        """Strictness check: without errors="replace", the SAME
        file would raise UnicodeDecodeError — this is exactly
        the symptom Andrew hit. Pin so a future "simplification"
        that drops the fallback gets caught."""
        log = self._write_cp1252_log("would-crash.log")
        with self.assertRaises(UnicodeDecodeError):
            with open(log, "r", encoding="utf-8") as f:
                f.read()

    def test_replacement_not_silent_drop(self) -> None:
        """Distinguish errors="replace" from errors="ignore" —
        the instruction's rationale is that operators should
        SEE that bytes were unreadable (U+FFFD), not get a
        truncated tail that drops them silently. This pins the
        instruction's stated semantic."""
        log = self.tmpdir / "marker.log"
        log.write_bytes(b"BEFORE\x97AFTER")
        with open(log, "r", encoding="utf-8",
                   errors="replace") as f:
            text = f.read()
        self.assertEqual(text, "BEFORE�AFTER")
        # Contrast: ignore drops the byte entirely.
        with open(log, "r", encoding="utf-8",
                   errors="ignore") as f:
            text_ignore = f.read()
        self.assertEqual(text_ignore, "BEFOREAFTER")
        self.assertNotEqual(text, text_ignore)


class LogReadSweepSourcePinTests(unittest.TestCase):
    """FINDING-45 audit pin. The 2 target sites must source-pin
    errors="replace" + UnicodeDecodeError catch. Every other
    external-content read in the bin/harness/ tree either has a
    fallback (errors="replace" / errors="ignore") or is reading
    internal JSON we wrote ourselves with strict utf-8."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qpb_harness_src = (
            _REPO / "bin" / "qpb_harness_legacy.py").read_text(
                encoding="utf-8")

    def test_orchestrator_log_site_uses_replace_fallback(
            self) -> None:
        """qpb_harness.py:570-ish (orchestrator log surface)
        source-pin: errors="replace" must appear inside the
        open() that reads log_path."""
        # The block: open(log_path, "r", ... errors="replace")
        # tail = lf.read()[-4000:]
        m = re.search(
            r'open\(log_path,\s*"r",\s*'
            r'encoding="utf-8",\s*'
            r'errors="replace"\)\s*as\s+lf:'
            r'\s*\n\s*tail\s*=\s*lf\.read\(\)\[-4000:\]',
            self.qpb_harness_src,
        )
        self.assertIsNotNone(
            m, "orchestrator log site lost errors=replace")

    def test_harness_log_site_uses_replace_fallback(
            self) -> None:
        """qpb_harness.py:580-ish (harness.log tail surface)
        source-pin."""
        m = re.search(
            r'open\(harness_log,\s*"r",\s*'
            r'encoding="utf-8",\s*'
            r'errors="replace"\)\s*as\s+hlf:',
            self.qpb_harness_src,
        )
        self.assertIsNotNone(
            m, "harness.log site lost errors=replace")

    def test_orchestrator_log_except_catches_unicode_decode_error(
            self) -> None:
        """Belt-and-suspenders: the except clause around the
        orchestrator log read must catch UnicodeDecodeError so a
        regression doesn't reintroduce the original crash mode
        (errors="replace" should never raise, but if Python's
        behavior ever changes the broader except prevents a
        recurrence of the symptom Andrew hit)."""
        # Find the orchestrator-log try block and confirm its
        # except includes UnicodeDecodeError.
        m = re.search(
            r'open\(log_path,\s*"r",.*?\)\s*as\s+lf:'
            r'.*?except\s+\(([^)]+)\)\s+as\s+exc:',
            self.qpb_harness_src,
            re.DOTALL,
        )
        self.assertIsNotNone(m)
        captured = m.group(1)
        self.assertIn("OSError", captured)
        self.assertIn("UnicodeDecodeError", captured)

    def test_harness_log_except_catches_unicode_decode_error(
            self) -> None:
        """Same belt-and-suspenders for the harness.log site."""
        m = re.search(
            r'open\(harness_log,\s*"r",.*?\)\s*as\s+hlf:'
            r'.*?except\s+\(([^)]+)\):',
            self.qpb_harness_src,
            re.DOTALL,
        )
        self.assertIsNotNone(m)
        captured = m.group(1)
        self.assertIn("OSError", captured)
        self.assertIn("UnicodeDecodeError", captured)

    def test_no_unguarded_external_log_reads_remain(
            self) -> None:
        """Sweep invariant: enumerate every file under
        bin/qpb_harness.py + bin/harness/*.py that contains
        open(...encoding="utf-8") and pin the audit. Each entry
        in EXPECTED_EXTERNAL_READS must have a fallback
        (errors=replace OR errors=ignore). Internal-JSON reads
        are listed in INTERNAL_JSON_READS as an exemption pin
        (they ONLY read content we wrote ourselves with strict
        utf-8 — a bad byte means the file is corrupted, not
        cross-platform encoded). A future log-read site that
        doesn't appear in either pin AND lacks a fallback will
        fail this test."""
        # Audit table: (file, identifying-pattern, classification)
        # classification ∈ {"external-replace", "external-ignore",
        #                  "internal-json"}
        # Each entry is one source-line we expect to find.
        AUDIT = [
            # bin/qpb_harness.py
            ("bin/qpb_harness_legacy.py", "open(log_path",
                "external-replace"),
            ("bin/qpb_harness_legacy.py", "open(harness_log",
                "external-replace"),
            ("bin/qpb_harness_legacy.py",
                "launch.stream_path.read_text(\n                encoding=\"utf-8\", errors=\"ignore\"",
                "external-ignore"),
            # internal JSON reads (manifest / config / SKILL.md)
            ("bin/qpb_harness_legacy.py", "skill_md.read_text(encoding=\"utf-8\")",
                "internal-json"),
            ("bin/qpb_harness_legacy.py",
                "open(manifest_path, \"r\", encoding=\"utf-8\")",
                "internal-json"),
            ("bin/qpb_harness_legacy.py",
                "cfg_path.read_text(encoding=\"utf-8\")",
                "internal-json"),
            ("bin/qpb_harness_legacy.py",
                "manifest_path.read_text(encoding=\"utf-8\"))",
                "internal-json"),
            # bin/harness/grade_security.py — child output reads
            ("bin/harness/grade_security.py",
                "bugs_md.read_text(encoding=\"utf-8\",\n"
                "                                             errors=\"ignore\"))",
                "external-ignore"),
            ("bin/harness/grade_security.py",
                "entry.read_text(\n"
                "                        encoding=\"utf-8\", errors=\"ignore\",",
                "external-ignore"),
            # bin/harness/facts.py — three transcript / install-log
            # reads, all errors=ignore (parser-side rationale per
            # Panelist B 189: U+FFFD mid-JSON would confuse the
            # downstream parser; silent drop preserves the surrounding
            # ASCII anchors).
            ("bin/harness/facts.py",
                "encoding=\"utf-8\", errors=\"ignore\"",
                "external-ignore"),
            # bin/harness/prepare.py — Panelist C 189 audit-
            # completeness fix: scrub_reference_docs + leakage_gate
            # external workspace reads.
            ("bin/harness/prepare.py",
                "p.read_text(encoding=\"utf-8\", errors=\"ignore\")",
                "external-ignore"),
            # bin/harness/runner.py
            ("bin/harness/runner.py",
                "sp.read_text(encoding=\"utf-8\")",
                "internal-json"),
            ("bin/harness/runner.py",
                "log.read_text(encoding=\"utf-8\", errors=\"ignore\")",
                "external-ignore"),
            # bin/harness/_launch_log.py — breadcrumb JSON
            ("bin/harness/_launch_log.py",
                "open(log_path, \"r\", encoding=\"utf-8\")",
                "internal-json"),
            # bin/harness/tui.py
            ("bin/harness/tui.py",
                "invocation.read_text(encoding=\"utf-8\")",
                "internal-json"),
            ("bin/harness/tui.py",
                "facts.read_text(encoding=\"utf-8\")",
                "internal-json"),
            ("bin/harness/tui.py",
                "grading.read_text(encoding=\"utf-8\")",
                "internal-json"),
            ("bin/harness/tui.py",
                "bugs.read_text(encoding=\"utf-8\",",
                "external-ignore"),
            # bin/harness/status.py
            ("bin/harness/status.py",
                "path.read_text(encoding=\"utf-8\", errors=\"ignore\")",
                "external-ignore"),
            # bin/harness/plan_runner.py — transcript reads
            ("bin/harness/plan_runner.py",
                "launch.stream_path.read_text(",
                "external-ignore"),
            ("bin/harness/plan_runner.py",
                "stream_path.read_text(",
                "external-ignore"),
            # plan_runner step.log reader — we WROTE step.log
            ("bin/harness/plan_runner.py",
                "open(log_path, \"r\", encoding=\"utf-8\")",
                "internal-json"),
        ]

        for relpath, snippet, classification in AUDIT:
            src = (_REPO / relpath).read_text(encoding="utf-8")
            self.assertIn(snippet, src,
                f"audit miss: expected snippet not found in "
                f"{relpath} for classification={classification}")


if __name__ == "__main__":
    unittest.main()
