"""v1.5.7 122 — human-readable Claude --print stream-json log
renderer (toggleable raw), shared by tail / TUI output /
`tui --dump output`.

The TUI/tail/`--dump output` views showed Claude runs as raw
``{"type":"assistant",...}`` JSON lines — noisy and unreadable.
122 templates each known Claude event type into a clean log
line (▶ / · / ⚙ / ← / ■ / ↳ / ⏳ icons) and de-jsonifies
unknown types into ``«type=… key=val»`` instead of raw JSON.
Non-Claude plain text (codex / copilot CLI / run_playbook
output) passes through unchanged.

Toggleable raw mode (default rendered):
  * TUI: ``j`` key flips RENDERED ⇔ RAW; mode shown in the
    status bar.
  * CLI: ``tail --raw`` and ``tui --dump output --raw`` emit
    verbatim wire-format lines.
  * `c`-copy + `--dump` reflect the active mode.

Coverage:
  * Each Claude event type renders to its templated log line
    (using fixtures lifted from a real
    ``claude --print stream-json`` stream).
  * Unknown event types render as ``«type=… key=val»`` (NOT
    raw JSON).
  * Embedded ``::QPB::`` sentinels (inside tool_result.content,
    per 117) render the phase/gate line — preferred over a
    plain `← <snippet>`.
  * Bare-line ``::QPB::`` sentinels still render (109/110
    back-compat).
  * Non-Claude plain text (codex / copilot / run_playbook
    `Phase 1/6 (Explore)`) passes through unchanged.
  * Non-Claude JSON (no ``type`` field) passes through.
  * ``rendered=False`` (raw mode) emits verbatim lines —
    **THE 122 MUTATION-BITE**: if rendering is always-on,
    the "raw emits verbatim" test FAILS; if rendering is
    skipped, the "known event renders to log line" test
    FAILS.
  * CLI flags ``tail --raw`` and ``tui --dump output --raw``
    end-to-end (subprocess invocation).
  * 119 import-safety preserved; bundle-safety green.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bin.harness import status as ST
from bin.harness import tui as TUI


_REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Real Claude --print stream-json fixtures (lifted verbatim)
# ---------------------------------------------------------------------------


# system/init — model + tools list announcement.
_REAL_INIT = (
    '{"type":"system","subtype":"init","cwd":"/x/y","model":'
    '"claude-opus-4-7","session_id":"abc123def456","tools":'
    '["Task","Bash","Read","Edit","Glob"]}'
)

# system/task_started — subagent spawn.
_REAL_TASK_STARTED = (
    '{"type":"system","subtype":"task_started","task_id":'
    '"bv01zo7m0","tool_use_id":"toolu_01","description":'
    '"Build gson","task_type":"local_bash"}'
)

# system/task_notification — subagent completion.
_REAL_TASK_NOTIFICATION = (
    '{"type":"system","subtype":"task_notification","task_id":'
    '"bv01zo7m0","status":"completed","summary":"Build gson"}'
)

# system/task_progress — periodic subagent progress.
_REAL_TASK_PROGRESS = (
    '{"type":"system","subtype":"task_progress","task_id":'
    '"abc","description":"Reading SKILL.md","usage":'
    '{"total_tokens":14290}}'
)

# assistant with text + tool_use blocks (thinking elided).
_REAL_ASSISTANT_WITH_TOOL = (
    '{"type":"assistant","message":{"role":"assistant",'
    '"content":[{"type":"thinking","thinking":"reasoning..."},'
    '{"type":"text","text":"Running the gate now."},'
    '{"type":"tool_use","name":"Bash","input":'
    '{"command":"python3 quality_gate.py"}}]}}'
)

# user / tool_result with a plain text result.
_REAL_USER_TOOL_RESULT = (
    '{"type":"user","message":{"role":"user","content":'
    '[{"type":"tool_result","tool_use_id":"t","content":'
    '"Launching skill: quality-playbook"}]}}'
)

# user / tool_result with an EMBEDDED ::QPB:: sentinel
# (117 — qpb_phase / quality_gate stdout captured as a
# tool_result by Claude).
_REAL_USER_EMBEDDED_SENTINEL = json.dumps({
    "type": "user",
    "message": {
        "role": "user",
        "content": [{
            "tool_use_id": "t",
            "type": "tool_result",
            "content": (
                "::QPB:: "
                + json.dumps({
                    "v": 1, "kind": "phase", "phase": 3,
                    "name": "code-review", "state": "start",
                    "ts": "2026-05-27T18:50:00Z",
                })
            ),
        }],
    },
})

# result/success — terminal event.
_REAL_RESULT_SUCCESS = (
    '{"type":"result","subtype":"success","is_error":false,'
    '"result":"All six phases complete."}'
)

# result with is_error (AUP / api error).
_REAL_RESULT_ERROR = (
    '{"type":"result","subtype":"success","is_error":true,'
    '"result":"API Error: violates Usage Policy …"}'
)

# rate_limit_event.
_REAL_RATE_LIMIT = (
    '{"type":"rate_limit_event","rate_limit_info":'
    '{"status":"allowed","rateLimitType":"five_hour"}}'
)

# An UNKNOWN event type — should de-jsonify, not pass through.
_UNKNOWN_TYPE = (
    '{"type":"future_event_type","important_field":'
    '"some-value","another":42}'
)


# ---------------------------------------------------------------------------
# Task A — per-event-type render contracts
# ---------------------------------------------------------------------------


class RenderStreamLineClaudeEventTests(unittest.TestCase):
    """Each known Claude event type renders to its templated
    log-line shape. Fixtures are realistic shapes (lifted from
    a real claude --print stream-json stream)."""

    def test_system_init_renders_session_start(self) -> None:
        out = ST.render_stream_line(_REAL_INIT)
        self.assertIn("▶ session start", out)
        self.assertIn("model=claude-opus-4-7", out)
        self.assertIn("tools=5", out)

    def test_system_task_started_renders_subagent_start(
            self) -> None:
        out = ST.render_stream_line(_REAL_TASK_STARTED)
        self.assertIn("↳ subagent bv01zo7m0 START", out)
        self.assertIn("Build gson", out)

    def test_system_task_notification_renders_status(
            self) -> None:
        out = ST.render_stream_line(_REAL_TASK_NOTIFICATION)
        self.assertIn("↳ subagent bv01zo7m0 completed", out)
        self.assertIn("Build gson", out)

    def test_system_task_progress_renders_with_tokens(
            self) -> None:
        out = ST.render_stream_line(_REAL_TASK_PROGRESS)
        self.assertIn("↳ subagent abc progress", out)
        self.assertIn("14290 tokens", out)
        self.assertIn("Reading SKILL.md", out)

    def test_assistant_renders_text_and_tool_use(self) -> None:
        """An assistant event with text + tool_use blocks
        renders as multi-line (text → `· …`, tool_use → `⚙
        name: cmd`). Thinking blocks are SKIPPED (operator
        doesn't need to see internal reasoning)."""
        out = ST.render_stream_line(_REAL_ASSISTANT_WITH_TOOL)
        self.assertIn("· Running the gate now.", out)
        self.assertIn("⚙ Bash: python3 quality_gate.py", out)
        # thinking text MUST NOT leak through.
        self.assertNotIn("reasoning", out)

    def test_user_tool_result_renders_with_arrow(self) -> None:
        out = ST.render_stream_line(_REAL_USER_TOOL_RESULT)
        self.assertIn("← Launching skill: quality-playbook",
                        out)

    def test_user_with_embedded_sentinel_renders_phase_line(
            self) -> None:
        """**Embedded-sentinel preference** (117): when a
        tool_result.content carries a ``::QPB::`` payload,
        render the phase/gate one-liner — NOT a plain
        ``← <snippet>`` showing the raw sentinel text."""
        out = ST.render_stream_line(_REAL_USER_EMBEDDED_SENTINEL)
        self.assertIn("phase 3", out)
        self.assertIn("code-review", out)
        self.assertIn("START", out.upper())
        # Should NOT render as a raw `←` snippet — the
        # sentinel takes precedence.
        self.assertNotIn("← ::QPB::", out)

    def test_result_success_renders_done_line(self) -> None:
        out = ST.render_stream_line(_REAL_RESULT_SUCCESS)
        self.assertEqual(
            out, "■ DONE: success is_error=False")

    def test_result_error_renders_with_reason(self) -> None:
        out = ST.render_stream_line(_REAL_RESULT_ERROR)
        self.assertIn("■ DONE: success is_error=True", out)
        self.assertIn("Usage Policy", out)

    def test_rate_limit_event_renders(self) -> None:
        out = ST.render_stream_line(_REAL_RATE_LIMIT)
        self.assertIn("⏳ rate-limit event", out)
        self.assertIn("allowed", out)
        self.assertIn("five_hour", out)


class RenderStreamLineUnknownTypeTests(unittest.TestCase):
    """Unknown Claude event types must de-jsonify to
    ``«type=… key=val …»`` — NEVER raw JSON."""

    def test_unknown_type_renders_dejsonified(self) -> None:
        out = ST.render_stream_line(_UNKNOWN_TYPE)
        # De-jsonified form.
        self.assertTrue(out.startswith("«"))
        self.assertTrue(out.endswith("»"))
        self.assertIn("type=future_event_type", out)
        self.assertIn("important_field=some-value", out)
        # The raw JSON form must NOT appear.
        self.assertNotIn('{"', out)
        self.assertNotIn("future_event_type\":", out)


# ---------------------------------------------------------------------------
# Passthrough contracts (non-Claude + non-JSON)
# ---------------------------------------------------------------------------


class RenderStreamLinePassthroughTests(unittest.TestCase):
    """Non-Claude streams must pass through verbatim. The
    renderer's job is to TRANSLATE Claude — not to interpret
    arbitrary text."""

    def test_run_playbook_phase_line_passes_through(
            self) -> None:
        """Mode B run_playbook lines look like
        ``10:59:05   Phase 1/6 (Explore): target`` — plain
        text; pass through unchanged."""
        line = "10:59:05   Phase 1/6 (Explore): target"
        self.assertEqual(
            ST.render_stream_line(line), line)

    def test_arbitrary_plain_text_passes_through(self) -> None:
        line = "WARN: something happened (codex stdout)"
        self.assertEqual(
            ST.render_stream_line(line), line)

    def test_non_claude_json_passes_through(self) -> None:
        """JSON WITHOUT a ``type`` field isn't a Claude event
        — pass through (it might be some other tooling's
        structured output)."""
        line = json.dumps(
            {"event": "build-complete", "elapsed_s": 12})
        self.assertEqual(
            ST.render_stream_line(line), line)

    def test_bare_qpb_sentinel_renders(self) -> None:
        """109/110 bare-line ``::QPB::`` sentinel still
        renders human-readably (back-compat preserved)."""
        line = (
            '::QPB:: {"v":1,"kind":"phase","phase":2,'
            '"name":"generation","state":"done",'
            '"ts":"2026-05-27T17:00:00Z"}'
        )
        out = ST.render_stream_line(line)
        self.assertIn("phase 2", out)
        self.assertIn("generation", out)
        self.assertIn("DONE", out.upper())


# ---------------------------------------------------------------------------
# Task B — toggle (rendered=False → raw passthrough)
# ---------------------------------------------------------------------------


class RenderedToggleTests(unittest.TestCase):
    """**THE 122 MUTATION-BITE**: rendered=False MUST emit
    the line verbatim. If rendering is always-on, this test
    FAILS. If rendering is never-on, the per-event-type
    rendering tests above FAIL. Both must hold."""

    def test_raw_mode_emits_verbatim_claude_event(
            self) -> None:
        out = ST.render_stream_line(_REAL_INIT, rendered=False)
        self.assertEqual(out, _REAL_INIT)

    def test_raw_mode_emits_verbatim_unknown_type(
            self) -> None:
        out = ST.render_stream_line(
            _UNKNOWN_TYPE, rendered=False)
        self.assertEqual(out, _UNKNOWN_TYPE)

    def test_raw_mode_emits_verbatim_bare_sentinel(
            self) -> None:
        line = '::QPB:: {"v":1,"kind":"phase","phase":1}'
        self.assertEqual(
            ST.render_stream_line(line, rendered=False), line)

    def test_raw_mode_emits_verbatim_plain_text(self) -> None:
        line = "plain text"
        self.assertEqual(
            ST.render_stream_line(line, rendered=False), line)


# ---------------------------------------------------------------------------
# build_rendered_output_lines + format_output_as_text — rendered toggle
# ---------------------------------------------------------------------------


class BuildRenderedOutputLinesRenderedToggleTests(
        unittest.TestCase):
    """The TUI/CLI `--raw` path goes through
    ``build_rendered_output_lines(rendered=False)`` /
    ``format_output_as_text(rendered=False)``."""

    def test_rendered_default_translates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "stream.ndjson").write_text(
                _REAL_INIT + "\n", encoding="utf-8")
            lines = TUI.build_rendered_output_lines(run_dir)
            self.assertEqual(len(lines), 1)
            self.assertIn("▶ session start", lines[0])

    def test_rendered_false_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "stream.ndjson").write_text(
                _REAL_INIT + "\n", encoding="utf-8")
            lines = TUI.build_rendered_output_lines(
                run_dir, rendered=False)
            self.assertEqual(lines, [_REAL_INIT])

    def test_format_output_as_text_raw_marker(self) -> None:
        """``format_output_as_text(rendered=False)`` adds a
        ``[RAW]`` marker to the header so operators can see
        the mode in `--dump` / clipboard."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "stream.ndjson").write_text(
                _REAL_INIT + "\n", encoding="utf-8")
            text = TUI.format_output_as_text(
                run_dir, rendered=False)
            self.assertIn("[RAW]", text)
            self.assertIn(_REAL_INIT, text)

    def test_format_output_as_text_rendered_default(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "stream.ndjson").write_text(
                _REAL_INIT + "\n", encoding="utf-8")
            text = TUI.format_output_as_text(run_dir)
            self.assertNotIn("[RAW]", text)
            self.assertIn("▶ session start", text)


# ---------------------------------------------------------------------------
# CLI end-to-end: tail --raw / tui --dump output --raw
# ---------------------------------------------------------------------------


class CliRawFlagTests(unittest.TestCase):
    """Subprocess-invoked ``qpb_harness tail`` and
    ``qpb_harness tui --dump output``: ``--raw`` flips off
    the renderer; default renders."""

    def test_tail_default_renders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-00"
            run_dir.mkdir()
            (run_dir / "stream.ndjson").write_text(
                _REAL_INIT + "\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "bin.qpb_harness",
                  "tail", str(run_dir)],
                cwd=str(_REPO_ROOT),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("▶ session start", proc.stdout)
            self.assertNotIn("\"type\":\"system\"", proc.stdout)

    def test_tail_raw_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-00"
            run_dir.mkdir()
            (run_dir / "stream.ndjson").write_text(
                _REAL_INIT + "\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "bin.qpb_harness",
                  "tail", str(run_dir), "--raw"],
                cwd=str(_REPO_ROOT),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn(_REAL_INIT, proc.stdout)
            # No rendered marker should leak.
            self.assertNotIn("▶ session start", proc.stdout)

    def test_dump_output_raw_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-00"
            run_dir.mkdir()
            (run_dir / "stream.ndjson").write_text(
                _REAL_INIT + "\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "bin.qpb_harness",
                  "tui", "--dump", "output",
                  "--dump-path", str(run_dir), "--raw"],
                cwd=str(_REPO_ROOT),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("[RAW]", proc.stdout)
            self.assertIn(_REAL_INIT, proc.stdout)
            self.assertNotIn("▶ session start", proc.stdout)

    def test_dump_output_default_renders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-00"
            run_dir.mkdir()
            (run_dir / "stream.ndjson").write_text(
                _REAL_INIT + "\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "bin.qpb_harness",
                  "tui", "--dump", "output",
                  "--dump-path", str(run_dir)],
                cwd=str(_REPO_ROOT),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertNotIn("[RAW]", proc.stdout)
            self.assertIn("▶ session start", proc.stdout)


# ---------------------------------------------------------------------------
# 119 import-safety + bundle-safety
# ---------------------------------------------------------------------------


class ImportSafety122Tests(unittest.TestCase):

    def test_status_import_clean(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-c",
              "from bin.harness import status; "
              "assert callable(status.render_stream_line)"],
            cwd=str(_REPO_ROOT),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            proc.returncode, 0,
            f"bin.harness.status import failed: "
            f"{proc.stderr[:400]!r}",
        )


class BundleSafety122Tests(unittest.TestCase):

    def test_changes_stay_under_harness(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"122 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
