"""v1.5.7 137 — artifact-based COMPLETED inference for non-Claude
streams.

The 2026-05-29 acceptance run's keto copilot/gpt-5.4 case finished
cleanly (`RESULT: GATE PASSED`, 2 real bugs found) but was recorded
`terminal_state=FAILED` because copilot/codex/cursor emit plain
text — no Claude `result` envelope — so 113's
`_classify_stream_terminal` returned None and the collector fell
through to its FAILED default.

137 extends the classifier with an artifact-based fallback: when no
Claude `result` event is found AND `<target>/quality/results/
quality-gate.log` carries a canonical `RESULT: GATE …` line, the
run COMPLETED (all three verdicts — the PASS/CLEANUP/FAIL GRADE is
decided downstream). The Claude `result` event still wins when
present (faster, authoritative).

Covers: each verdict, log-missing / no-result-line negatives,
Claude-event-precedence (load-bearing), back-compat (no target_dir),
and the real keto run-03 log (skips when the transient run dir is
absent, e.g. a fresh clone — repos/ is gitignored).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bin.harness.runner import _classify_stream_terminal, _gate_log_verdict
from bin.harness.schema import TerminalState


def _make_target(tmp: str, *, gate_log: "str | None") -> Path:
    """A run-NN target/ dir; optionally with a quality-gate.log."""
    target = Path(tmp) / "target"
    (target / "quality" / "results").mkdir(parents=True, exist_ok=True)
    if gate_log is not None:
        (target / "quality" / "results" / "quality-gate.log").write_text(
            gate_log, encoding="utf-8")
    return target


def _write_stream(tmp: str, lines: str) -> Path:
    p = Path(tmp) / "stream.ndjson"
    p.write_text(lines, encoding="utf-8")
    return p


# A representative non-Claude (copilot) stream: plain text, no
# Claude `result` envelope.
_COPILOT_STREAM = (
    "Phase 1/6 (Exploration) starting…\n"
    "Phase 6/6 (Verification) complete.\n"
    "RESULT: GATE PASSED\n"
)


class ArtifactFallbackTests(unittest.TestCase):

    def test_artifact_fallback_fires_when_gate_log_says_passed(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(tmp, gate_log="RESULT: GATE PASSED\n")
            stream = _write_stream(tmp, _COPILOT_STREAM)
            state, reason = _classify_stream_terminal(
                stream, target_dir=target)
            self.assertIs(state, TerminalState.COMPLETED)
            self.assertIn("gate log", reason)
            self.assertIn("GATE PASSED", reason)

    def test_artifact_fallback_fires_for_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(
                tmp,
                gate_log="RESULT: GATE PASSED WITH CLEANUP NEEDED\n")
            stream = _write_stream(tmp, _COPILOT_STREAM)
            state, _reason = _classify_stream_terminal(
                stream, target_dir=target)
            self.assertIs(state, TerminalState.COMPLETED)

    def test_artifact_fallback_fires_for_fail(self) -> None:
        """A FAILED gate verdict is still a COMPLETED terminal
        state — the run reached Phase 6; the GRADE is FAIL."""
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(
                tmp,
                gate_log=("RESULT: GATE FAILED — "
                          "3 substantive issue(s) must be fixed\n"))
            stream = _write_stream(tmp, _COPILOT_STREAM)
            state, _reason = _classify_stream_terminal(
                stream, target_dir=target)
            self.assertIs(state, TerminalState.COMPLETED)

    def test_artifact_fallback_does_not_fire_when_log_missing(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(tmp, gate_log=None)
            stream = _write_stream(tmp, _COPILOT_STREAM)
            state, reason = _classify_stream_terminal(
                stream, target_dir=target)
            self.assertIsNone(state)
            self.assertEqual(reason, "")

    def test_artifact_fallback_does_not_fire_when_log_has_no_result_line(
            self) -> None:
        """A partial run: gate log exists but never reached the
        Phase 6 `RESULT: GATE …` verdict → no fallback; default
        (None) so the collector treats it as FAILED."""
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(
                tmp,
                gate_log=("Phase 1/6 checks…\n"
                          "  PASS: BUGS.md exists\n"
                          "  PASS: REQUIREMENTS.md exists\n"))
            stream = _write_stream(tmp, _COPILOT_STREAM)
            state, _reason = _classify_stream_terminal(
                stream, target_dir=target)
            self.assertIsNone(state)

    def test_back_compat_no_target_dir_is_claude_only(self) -> None:
        """Pre-137 behavior preserved: with no target_dir, a stream
        lacking a Claude `result` event classifies as None
        regardless of any gate log."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_target(tmp, gate_log="RESULT: GATE PASSED\n")
            stream = _write_stream(tmp, _COPILOT_STREAM)
            state, reason = _classify_stream_terminal(stream)
            self.assertIsNone(state)
            self.assertEqual(reason, "")


class ClaudePrecedenceTests(unittest.TestCase):
    """The Claude `result` event is the faster, authoritative
    signal — it must win over the gate-log fallback."""

    def test_claude_result_event_still_wins_over_artifact_fallback(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(tmp, gate_log="RESULT: GATE PASSED\n")
            # Claude stream WITH a clean result event.
            stream = _write_stream(
                tmp,
                '{"type":"assistant","message":{"content":[]}}\n'
                '{"type":"result","subtype":"success",'
                '"is_error":false,"result":"done"}\n')
            state, reason = _classify_stream_terminal(
                stream, target_dir=target)
            self.assertIs(state, TerminalState.COMPLETED)
            # The Claude branch returns an EMPTY reason; the
            # gate-log fallback would have set "completed (gate
            # log: …)". Empty reason proves Claude precedence.
            self.assertEqual(reason, "")
            self.assertNotIn("gate log", reason)

    def test_claude_blocked_event_wins_over_passing_gate_log(
            self) -> None:
        """An AUP/API-error `is_error:true` result is BLOCKED even
        if a stale/partial gate log says PASSED — the Claude event
        is authoritative."""
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(tmp, gate_log="RESULT: GATE PASSED\n")
            stream = _write_stream(
                tmp,
                '{"type":"result","subtype":"success",'
                '"is_error":true,"result":"API Error: …AUP…"}\n')
            state, reason = _classify_stream_terminal(
                stream, target_dir=target)
            self.assertIs(state, TerminalState.BLOCKED)
            self.assertIn("AUP", reason)


class KetoRealLogTests(unittest.TestCase):
    """The diagnostic case that motivated 137. Skips when the
    transient run dir is absent (repos/ is gitignored, so a fresh
    clone / CI won't have it); the hermetic fixtures above cover
    the format deterministically."""

    _KETO = Path(__file__).resolve().parents[3] / (
        "repos/20260528T235659Z/run-03")

    @unittest.skipUnless(
        (_KETO / "target/quality/results/quality-gate.log").is_file(),
        "live keto run-03 gate log not present (transient repos/)")
    def test_keto_real_log_classifies_as_completed(self) -> None:
        target = self._KETO / "target"
        stream = self._KETO / "stream.ndjson"
        self.assertEqual(_gate_log_verdict(target), "GATE PASSED")
        state, reason = _classify_stream_terminal(
            stream, target_dir=target)
        self.assertIs(state, TerminalState.COMPLETED)
        self.assertIn("GATE PASSED", reason)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
