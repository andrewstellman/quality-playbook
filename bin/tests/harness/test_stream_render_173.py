"""v1.5.7 173 — unit tests for the new Claude-Code-TUI stream
renderer module (:mod:`bin.harness.stream_render`). The 122
contract tests live in test_streamjson_renderer_122.py (refreshed
to the new format); this file adds the 173-specific coverage:
multi-line indented tool_result, error variant, truncate behavior,
non-JSON / non-dict / no-type passthrough, raw-mode toggle, and
``show_thinking`` / ``truncate`` kwargs.

LOAD-BEARING ::QPB:: sentinel preservation is tested in BOTH
forms (bare-line + inline-in-tool_result).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from bin.harness import stream_render as SR  # noqa: E402


def _assistant(*content_blocks: dict) -> str:
    return json.dumps({
        "type": "assistant",
        "message": {"role": "assistant",
                     "content": list(content_blocks)},
    })


def _user(*content_blocks: dict) -> str:
    return json.dumps({
        "type": "user",
        "message": {"role": "user",
                     "content": list(content_blocks)},
    })


class SystemBannerTests(unittest.TestCase):

    def test_system_init_banner(self) -> None:
        line = json.dumps({
            "type": "system", "subtype": "init",
            "model": "claude-haiku-4-5",
            "session_id": "abc12345defghi",
            "cwd": "/x",
            "tools": ["Bash", "Read"],
        })
        out = SR.render_stream_line(line)
        self.assertIn("━━━", out)
        self.assertIn("session abc12345", out)
        self.assertIn("model=claude-haiku-4-5", out)
        self.assertIn("cwd=/x", out)
        self.assertIn("2 tools", out)


class AssistantTests(unittest.TestCase):

    def test_assistant_text_plain(self) -> None:
        out = SR.render_stream_line(_assistant(
            {"type": "text", "text": "Hello world."}))
        self.assertEqual(out, "Hello world.")

    def test_assistant_thinking_shown_by_default(self) -> None:
        out = SR.render_stream_line(_assistant(
            {"type": "thinking",
              "thinking": "this is my internal reasoning"}))
        self.assertIn("⟨thinking⟩", out)
        self.assertIn("internal reasoning", out)

    def test_assistant_thinking_skipped_with_flag(self) -> None:
        out = SR.render_stream_line(_assistant(
            {"type": "thinking",
              "thinking": "internal reasoning"}),
            show_thinking=False)
        self.assertEqual(out, "")

    def test_assistant_tool_use_bash(self) -> None:
        out = SR.render_stream_line(_assistant({
            "type": "tool_use", "name": "Bash",
            "input": {"command": "ls -la"}}))
        self.assertEqual(out, "⏺ Bash(ls -la)")

    def test_assistant_tool_use_read(self) -> None:
        out = SR.render_stream_line(_assistant({
            "type": "tool_use", "name": "Read",
            "input": {"file_path": "/tmp/x.md"}}))
        self.assertEqual(out, "⏺ Read(/tmp/x.md)")

    def test_assistant_tool_use_edit(self) -> None:
        out = SR.render_stream_line(_assistant({
            "type": "tool_use", "name": "Edit",
            "input": {"file_path": "/x/y.py"}}))
        self.assertEqual(out, "⏺ Edit(/x/y.py)")

    def test_assistant_tool_use_grep(self) -> None:
        out = SR.render_stream_line(_assistant({
            "type": "tool_use", "name": "Grep",
            "input": {"pattern": "foo", "glob": "*.py"}}))
        self.assertIn("⏺ Grep(", out)
        self.assertIn("foo", out)
        self.assertIn("*.py", out)

    def test_assistant_tool_use_skill(self) -> None:
        out = SR.render_stream_line(_assistant({
            "type": "tool_use", "name": "Skill",
            "input": {"skill": "quality-playbook"}}))
        self.assertEqual(out, "⏺ Skill(quality-playbook)")

    def test_assistant_tool_use_task(self) -> None:
        out = SR.render_stream_line(_assistant({
            "type": "tool_use", "name": "Task",
            "input": {"subagent_type": "general",
                       "description": "Do a thing"}}))
        self.assertIn("⏺ Task[general]", out)
        self.assertIn("Do a thing", out)

    def test_assistant_tool_use_todowrite(self) -> None:
        out = SR.render_stream_line(_assistant({
            "type": "tool_use", "name": "TodoWrite",
            "input": {"todos": [{}, {}, {}]}}))
        self.assertEqual(out, "⏺ TodoWrite(3 items)")

    def test_assistant_tool_use_unknown_tool_fallback(
            self) -> None:
        out = SR.render_stream_line(_assistant({
            "type": "tool_use", "name": "FancyTool",
            "input": {"k": "v", "a": 42}}))
        self.assertIn("⏺ FancyTool(", out)
        # input is compactly rendered.
        self.assertIn('"k":"v"', out)


class UserToolResultTests(unittest.TestCase):

    def test_tool_result_single_line(self) -> None:
        out = SR.render_stream_line(_user({
            "type": "tool_result",
            "content": "single line output"}))
        self.assertEqual(out, "⎿  single line output")

    def test_tool_result_multi_line_indented(self) -> None:
        out = SR.render_stream_line(_user({
            "type": "tool_result",
            "content": "line1\nline2\nline3"}))
        # First line gets the glyph, continuation lines get 3
        # spaces of indent so the glyph column aligns visually.
        self.assertEqual(out,
                          "⎿  line1\n   line2\n   line3")

    def test_tool_result_error_marker(self) -> None:
        out = SR.render_stream_line(_user({
            "type": "tool_result",
            "is_error": True,
            "content": "boom"}))
        self.assertIn("⎿", out)
        self.assertIn("⚠️ ERROR", out)
        self.assertIn("boom", out)

    def test_tool_result_list_content_flattens(self) -> None:
        out = SR.render_stream_line(_user({
            "type": "tool_result",
            "content": [{"type": "text", "text": "alpha"},
                          {"type": "text", "text": "beta"}]}))
        self.assertIn("⎿  alpha", out)
        self.assertIn("beta", out)


class ResultTerminalTests(unittest.TestCase):

    def test_result_success(self) -> None:
        line = json.dumps({
            "type": "result", "subtype": "success",
            "is_error": False, "num_turns": 12,
            "duration_ms": 5000,
            "total_cost_usd": 0.1234})
        out = SR.render_stream_line(line)
        self.assertIn("━━━", out)
        self.assertIn("SUCCESS", out)
        self.assertIn("turns=12", out)
        self.assertIn("duration=5.0s", out)
        self.assertIn("cost=$0.1234", out)

    def test_result_error_variant(self) -> None:
        line = json.dumps({
            "type": "result", "subtype": "error_during_execution",
            "is_error": True, "num_turns": 3,
            "duration_ms": 1500})
        out = SR.render_stream_line(line)
        self.assertIn("━━━", out)
        self.assertIn("ERROR (error_during_execution)", out)
        self.assertIn("turns=3", out)


class RateLimitTests(unittest.TestCase):

    def test_rate_limit_event(self) -> None:
        line = json.dumps({
            "type": "rate_limit_event",
            "rate_limit_info": {"status": "allowed",
                                  "rateLimitType": "five_hour"}})
        out = SR.render_stream_line(line)
        self.assertIn("⟨rate_limit⟩", out)
        self.assertIn("status=allowed", out)
        self.assertIn("type=five_hour", out)


class SubagentTests(unittest.TestCase):

    def test_task_started(self) -> None:
        line = json.dumps({
            "type": "system", "subtype": "task_started",
            "subagent_type": "general",
            "description": "Audit the harness"})
        out = SR.render_stream_line(line)
        self.assertEqual(
            out, "• Task[general] started: Audit the harness")

    def test_task_progress(self) -> None:
        line = json.dumps({
            "type": "system", "subtype": "task_progress",
            "description": "Half done",
            "usage": {"tool_uses": 7},
            "last_tool_name": "Bash"})
        out = SR.render_stream_line(line)
        self.assertIn("• Task progress", out)
        self.assertIn("Half done", out)
        self.assertIn("tools_used=7", out)
        self.assertIn("[last=Bash]", out)

    def test_task_notification(self) -> None:
        line = json.dumps({
            "type": "system", "subtype": "task_notification",
            "status": "completed",
            "summary": "Audit finished",
            "usage": {"duration_ms": 12345}})
        out = SR.render_stream_line(line)
        self.assertIn("• Task completed", out)
        self.assertIn("Audit finished", out)
        self.assertIn("(12.3s)", out)


class UnknownAndFallbackTests(unittest.TestCase):

    def test_unknown_type_fallback(self) -> None:
        out = SR.render_stream_line(json.dumps({
            "type": "future_event_type", "subtype": "x"}))
        self.assertIn("⟨future_event_type.x⟩", out)

    def test_non_json_passthrough(self) -> None:
        line = "10:59:05   Phase 1/6 (Explore): target"
        self.assertEqual(SR.render_stream_line(line), line)

    def test_non_dict_json_falls_through(self) -> None:
        # JSON list / scalar — render_unknown formats it.
        line = json.dumps([1, 2, 3])
        out = SR.render_stream_line(line)
        self.assertIn("⟨raw⟩", out)

    def test_dict_without_type_passes_through(self) -> None:
        line = json.dumps({"event": "build-complete",
                             "elapsed_s": 12})
        self.assertEqual(SR.render_stream_line(line), line)

    def test_empty_line_returns_empty(self) -> None:
        self.assertEqual(SR.render_stream_line(""), "")
        self.assertEqual(SR.render_stream_line("   \n"),
                          "   \n")


class RawModeTests(unittest.TestCase):
    """``rendered=False`` is the 122 raw-mode toggle, preserved
    by 173."""

    def test_raw_mode_passthrough_json(self) -> None:
        line = json.dumps({"type": "system", "subtype": "init"})
        self.assertEqual(
            SR.render_stream_line(line, rendered=False), line)

    def test_raw_mode_passthrough_plain(self) -> None:
        self.assertEqual(
            SR.render_stream_line("plain text",
                                    rendered=False),
            "plain text")


class TruncateTests(unittest.TestCase):

    def test_truncate_long_string_marker(self) -> None:
        # An assistant text block with a 2000-char string,
        # truncate=300 ⇒ output is bounded + marker present.
        long_text = "x" * 2000
        # Assistant text is yielded plain (not truncated by
        # _truncate at the text branch in the standalone port).
        # Tool-use args / tool_result content ARE truncated.
        out = SR.render_stream_line(_user({
            "type": "tool_result",
            "content": long_text}), truncate=300)
        # First line gets a glyph + truncated content; total
        # length should be <= ~300 + tail marker (a few dozen).
        self.assertIn("⎿", out)
        self.assertIn("… [+", out)


class SentinelPreservationTests(unittest.TestCase):
    """v1.5.7 173 LOAD-BEARING: ::QPB:: sentinel preservation in
    BOTH forms (bare-line + inline-in-tool_result.content).
    Replaces the equivalent 122 tests for the new format."""

    def test_bare_line_sentinel_preserved(self) -> None:
        line = (
            '::QPB:: {"v":1,"kind":"phase","phase":2,'
            '"name":"generation","state":"done",'
            '"ts":"2026-05-27T17:00:00Z"}'
        )
        out = SR.render_stream_line(line)
        self.assertIn("phase 2", out)
        self.assertIn("generation", out)
        self.assertIn("DONE", out.upper())
        # Should NOT render as ⎿ tool_result.
        self.assertNotIn("⎿", out)

    def test_inline_sentinel_in_tool_result_preserved(
            self) -> None:
        # tool_result content carrying a ::QPB:: payload (117).
        line = json.dumps({
            "type": "user",
            "message": {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": "t",
                "content": (
                    "::QPB:: "
                    + json.dumps({
                        "v": 1, "kind": "phase", "phase": 3,
                        "name": "code-review", "state": "start",
                        "ts": "2026-05-27T18:50:00Z",
                    })
                ),
            }]},
        })
        out = SR.render_stream_line(line)
        self.assertIn("phase 3", out)
        self.assertIn("code-review", out)
        self.assertIn("START", out.upper())
        # MUST NOT render as ⎿ snippet of raw sentinel text.
        self.assertNotIn("⎿  ::QPB::", out)

    def test_bare_line_unknown_kind_falls_through(self) -> None:
        # Unknown sentinel kind ⇒ format_sentinel_line returns
        # None ⇒ verbatim passthrough.
        line = (
            '::QPB:: {"v":1,"kind":"future_kind",'
            '"ts":"2026-05-27T17:00:00Z"}'
        )
        out = SR.render_stream_line(line)
        self.assertEqual(out, line)


class GlyphConstantsTests(unittest.TestCase):
    """v1.5.7 173: the module exports glyph constants that the
    cowork reference renderer also uses. Pin them so a typo in
    the unicode escape doesn't silently break rendering."""

    def test_glyphs_match_claude_code_tui(self) -> None:
        self.assertEqual(SR.GLYPH_TOOL, "⏺")  # ⏺
        self.assertEqual(SR.GLYPH_RESULT, "⎿")  # ⎿
        self.assertEqual(SR.GLYPH_BULLET, "•")  # •
        self.assertEqual(SR.GLYPH_RULE, "━")    # ━


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
