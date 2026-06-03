"""v1.5.7 185 — Windows cp1252 output-encoding tests.

Andrew's 6th Windows fire (run dir
``harness_runs/20260602T015320Z``) saw all four runs hit a
single root cause:

- akka (codex Mode B): hard crash 20s after spawn —
  ``UnicodeEncodeError: 'charmap' codec can't encode
  character '<-'``.
- tokio / webpack / Newtonsoft.Json (claude): COMPLETED with
  substantive findings, but the harness's facts parser
  reported ``facts_error`` because the captured gate stdout
  contained garbled bytes / raw escapes where the canonical
  emoji verdict markers should have been.

Python 3.14 on Windows falls back to cp1252 codec when
stdout is piped (not a TTY). cp1252 can't encode emoji /
box-drawing / arrow characters. ``print()`` raises.

FINDING-27 closure: known crash-causing high-bit characters
removed from print paths.
FINDING-28 closure (commit 2/3): facts parser accepts ASCII
verdict markers (post-185) AND legacy emoji markers
(pre-185 backward-compat for existing harness_runs/ folders).
FINDING-29 closure (commit 3/3): spawned playbook child
gets ``PYTHONIOENCODING=utf-8`` in its env so future
regressions don't reintroduce the crash.
"""
from __future__ import annotations

import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[3]


class NoKnownCrashCharsInPrintPathsTests(unittest.TestCase):
    """v1.5.7 185 FINDING-27: the specific high-bit
    characters Andrew's fire crashed on must NOT appear in
    the documented print/log paths. The broader source AST
    contains many high-bit chars in docstrings / comments
    (~769 hits across 62 files, dominated by ~515 em-dashes
    in docstrings); those are NOT printed and don't crash.
    This test focuses on the empirically-verified crash
    sites: the BANNER_TEXT (printed via benchmark_lib.logboth)
    + the quality gate's 090v lead verdict line + the
    run_playbook reference_docs/cite WARN message."""

    # Characters that empirically crashed Windows cp1252
    # print() in run 20260602T015320Z.
    CRASH_CHARS = (
        "←",  # LEFTWARDS ARROW (akka crash literal)
        "═",  # BOX DRAWINGS DOUBLE HORIZONTAL
        "✅",  # WHITE HEAVY CHECK MARK
        "⚠",  # WARNING SIGN (base char of warning emoji)
        "❌",  # CROSS MARK
    )

    def test_banner_text_has_no_crash_chars(self) -> None:
        from bin import _purpose
        for ch in self.CRASH_CHARS:
            self.assertNotIn(
                ch, _purpose.BANNER_TEXT,
                f"_purpose.BANNER_TEXT still contains "
                f"crash char U+{ord(ch):04X}; the banner "
                f"is printed via benchmark_lib.logboth and "
                f"crashes Windows cp1252 print(). Use "
                f"ASCII equivalent (185 FINDING-27).")

    def test_banner_box_rule_is_ascii(self) -> None:
        from bin import _purpose
        # The rule MUST be a sequence of ASCII characters; no
        # high-bit char allowed.
        for ch in _purpose.BANNER_BOX_RULE:
            self.assertLess(
                ord(ch), 128,
                f"BANNER_BOX_RULE contains high-bit char "
                f"U+{ord(ch):04X}; should be ASCII "
                f"(185 FINDING-27).")

    def test_quality_gate_verdict_uses_ascii_markers(
            self) -> None:
        # Source-pin: the quality_gate.py emits the 090v lead
        # verdict line. Pre-185 it used emoji; post-185 it
        # MUST use ASCII bracketed forms
        # ([PASS]/[WARN]/[FAIL]).
        qg = (_REPO / ".github" / "skills" / "quality_gate"
              / "quality_gate.py")
        if not qg.is_file():
            self.skipTest("quality_gate.py not present")
        src = qg.read_text(encoding="utf-8")
        self.assertIn(
            "[PASS] GATE PASSED", src,
            "quality_gate.py must emit '[PASS] GATE PASSED' "
            "ASCII verdict marker (185 FINDING-27).")
        self.assertIn(
            "[WARN] GATE PASSED", src,
            "quality_gate.py must emit '[WARN] GATE PASSED' "
            "ASCII verdict marker for shallow pass (185 "
            "FINDING-27).")
        self.assertIn(
            "[FAIL] GATE FAILED", src,
            "quality_gate.py must emit '[FAIL] GATE FAILED' "
            "ASCII verdict marker (185 FINDING-27).")

    def test_quality_gate_emoji_lead_verdict_lines_removed(
            self) -> None:
        # The pre-185 emoji versions of the lead verdict line
        # MUST NOT appear in the gate. Backward-compat for
        # pre-185 harness_runs/ folders lives in
        # bin/harness/facts.py (FINDING-28 dual-form parser),
        # not in quality_gate.py.
        qg = (_REPO / ".github" / "skills" / "quality_gate"
              / "quality_gate.py")
        if not qg.is_file():
            self.skipTest("quality_gate.py not present")
        src = qg.read_text(encoding="utf-8")
        forbidden = [
            "✅ GATE PASSED",  # check mark
            "⚠️ GATE PASSED",  # warning + VS
            "❌ GATE FAILED",  # cross mark
        ]
        for s in forbidden:
            self.assertNotIn(
                s, src,
                f"quality_gate.py still emits the pre-185 "
                f"emoji verdict (U+{ord(s[0]):04X}); ASCII "
                f"forms are the post-185 contract (185 "
                f"FINDING-27).")

    def test_run_playbook_warn_arrow_is_ascii(self) -> None:
        # Source-pin: bin/run_playbook.py's
        # reference_docs/cite WARN message used the leftwards
        # arrow (the akka crash literal). Post-185 must use
        # ``<-``.
        rp = _REPO / "bin" / "run_playbook.py"
        src = rp.read_text(encoding="utf-8")
        self.assertNotIn(
            "← AI chats", src,
            "run_playbook.py still emits the leftwards-arrow "
            "AI-chats string (akka crash literal); use "
            "'<- AI chats' (185 FINDING-27).")
        self.assertNotIn(
            "← project specs", src,
            "run_playbook.py still emits the leftwards-arrow "
            "project-specs string; use '<- project specs' "
            "(185 FINDING-27).")


class FactsParserAcceptsBothFormsTests(unittest.TestCase):
    """v1.5.7 185 FINDING-28: facts parser must accept the
    ASCII verdict markers (post-185) AND the legacy emoji
    markers (pre-185 backward-compat for existing
    harness_runs/ folders)."""

    def test_facts_parser_recognizes_ascii_pass(self) -> None:
        from bin.harness import facts as _facts
        stdout = (
            "Some preamble.\n"
            "[PASS] GATE PASSED -- this run looks solid\n"
            "Some postamble.\n"
        )
        self.assertEqual(
            _facts.parse_verdict_state(stdout), "solid")

    def test_facts_parser_recognizes_ascii_warn(self) -> None:
        from bin.harness import facts as _facts
        stdout = (
            "[WARN] GATE PASSED -- but this run looks shallow\n"
        )
        self.assertEqual(
            _facts.parse_verdict_state(stdout), "shallow")

    def test_facts_parser_recognizes_ascii_fail(self) -> None:
        from bin.harness import facts as _facts
        stdout = "[FAIL] GATE FAILED\n"
        self.assertEqual(
            _facts.parse_verdict_state(stdout), "failed")

    def test_facts_parser_recognizes_legacy_emoji_pass(
            self) -> None:
        # Backward-compat: pre-185 harness_runs/ folders have
        # the emoji form in their captured stream.ndjson. The
        # parser must still recognize them.
        from bin.harness import facts as _facts
        stdout = (
            "✅ GATE PASSED — this run looks solid\n"
        )
        self.assertEqual(
            _facts.parse_verdict_state(stdout), "solid")

    def test_facts_parser_recognizes_legacy_emoji_warn(
            self) -> None:
        from bin.harness import facts as _facts
        # U+26A0 + U+FE0F = warning sign + variation selector
        stdout = (
            "⚠️ GATE PASSED — "
            "but this run looks shallow\n"
        )
        self.assertEqual(
            _facts.parse_verdict_state(stdout), "shallow")

    def test_facts_parser_recognizes_legacy_emoji_fail(
            self) -> None:
        from bin.harness import facts as _facts
        stdout = "❌ GATE FAILED\n"
        self.assertEqual(
            _facts.parse_verdict_state(stdout), "failed")

    def test_facts_parser_no_marker_returns_none(
            self) -> None:
        from bin.harness import facts as _facts
        self.assertIsNone(_facts.parse_verdict_state(
            "Some unrelated stdout with no verdict.\n"))


class PythonIoEncodingSetInLaunchTests(unittest.TestCase):
    """v1.5.7 185 FINDING-29: the spawned playbook child must
    get ``PYTHONIOENCODING=utf-8`` in its env so future
    Unicode regressions don't crash Windows cp1252 print().
    Defensive layer — FINDING-27 stripped the known crash
    chars from print paths, but this env var catches
    anything FINDING-27 missed AND any future regression."""

    def test_runner_sets_pythonioencoding_utf8(self) -> None:
        # Source-pin: bin/harness/runner.py's launch-env
        # builder sets PYTHONIOENCODING. The instruction
        # explicitly identified runner.py as the env-build
        # site (plan_runner.py delegates env construction to
        # runner via LaunchSpec); the source-pin reflects that.
        src = (_REPO / "bin" / "harness" / "runner.py"
               ).read_text(encoding="utf-8")
        self.assertIn(
            "PYTHONIOENCODING", src,
            "bin/harness/runner.py must set "
            "PYTHONIOENCODING in the spawned playbook child "
            "env (185 FINDING-29).")
        self.assertIn(
            "utf-8", src,
            "PYTHONIOENCODING value must be 'utf-8' (185 "
            "FINDING-29).")

    def test_runner_env_uses_setdefault_for_pythonioencoding(
            self) -> None:
        # Source-pin: the env var is set via setdefault so
        # operators can override (the instruction's explicit
        # contract). A bare `env["PYTHONIOENCODING"] = "utf-8"`
        # would silently shadow operator config.
        src = (_REPO / "bin" / "harness" / "runner.py"
               ).read_text(encoding="utf-8")
        self.assertIn(
            'env.setdefault("PYTHONIOENCODING"', src,
            "bin/harness/runner.py must use env.setdefault "
            "for PYTHONIOENCODING so operator-set values "
            "win (185 FINDING-29).")

    def test_pythonioencoding_takes_effect_at_runtime(
            self) -> None:
        # Functional check: spawn a small subprocess with the
        # env var set; verify Python reports utf-8 stdout
        # encoding inside the child.
        import subprocess
        import sys
        env = {"PYTHONIOENCODING": "utf-8",
               "PATH": "/usr/bin:/bin"}
        proc = subprocess.run(
            [sys.executable, "-c",
             "import sys; print(sys.stdout.encoding)"],
            capture_output=True, text=True, env=env,
            timeout=10)
        self.assertEqual(proc.returncode, 0)
        # ``utf-8`` (Python normalizes to lowercase) on every
        # platform when PYTHONIOENCODING is set.
        self.assertIn("utf-8", proc.stdout.strip().lower())


if __name__ == "__main__":
    unittest.main()
