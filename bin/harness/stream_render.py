"""v1.5.7 173: Claude-Code-TUI-style stream.ndjson renderer.

Ported from the cowork-orchestrator's standalone
``claude_stream_render.py`` reference; resident in QPB so the TUI
output view, ``tail`` subcommand, and ``tui --dump output`` all
match the look-and-feel an operator sees running Claude Code
directly. Unicode glyphs ``━━━`` (session banner) / ``⏺``
(tool_use) / ``⎿`` (tool_result) / ``•`` (subagent task) /
``⟨thinking⟩`` (assistant reasoning).

Public entry: :func:`render_stream_line` — replaces the pre-173
:func:`bin.harness.status.render_stream_line` body (the public
``status.render_stream_line`` is now a thin delegator to keep the
call-site stable).

LOAD-BEARING ::QPB:: sentinel preservation:
  1. **Bare-line sentinel** — ``::QPB:: {...}`` at line start →
     :func:`bin.harness.status._format_sentinel_line` renders the
     phase/gate log line; raw fall-through if the payload is
     unknown.
  2. **Inline sentinel inside tool_result.content** — qpb_phase
     / quality_gate stdout captured by Claude as a tool_result
     (117 case). The sentinel is embedded mid-string; renderer
     scans :data:`_SENTINEL_INLINE_RE` and substitutes the
     phase/gate line for the ``⎿ <content>`` line.

Both behaviors come from
:mod:`bin.harness.status`'s exported sentinel helpers; the new
module imports them rather than duplicating the regexes /
:func:`_format_sentinel_line`.
"""
from __future__ import annotations

import json
from typing import Any, Iterable


# Unicode glyphs (matches Claude Code's terminal output).
GLYPH_TOOL = "⏺"      # ⏺
GLYPH_RESULT = "⎿"    # ⎿
GLYPH_BULLET = "•"    # •
GLYPH_RULE = "━"      # ━ (heavy horizontal)


def _rule(text: str) -> str:
    """Render a ``━━━ <text> ━━━`` session banner."""
    return f"{GLYPH_RULE * 3} {text} {GLYPH_RULE * 3}"


def _truncate(s: str, n: int) -> str:
    """Truncate to ``n`` chars with a tail marker. ``n=0`` disables."""
    if n <= 0 or len(s) <= n:
        return s
    return s[: n - 20].rstrip() + f" … [+{len(s) - n + 20} chars]"


def _short_repr(v: Any, n: int = 80) -> str:
    """Compact one-line repr of any value, truncated."""
    if isinstance(v, str):
        s = v.replace("\n", " ").replace("\r", " ")
        return _truncate(s, n)
    if isinstance(v, (dict, list)):
        return _truncate(
            json.dumps(v, separators=(",", ":"),
                        ensure_ascii=False), n)
    return _truncate(repr(v), n)


def _render_tool_use(c: dict, trunc: int) -> str:
    """``⏺ Bash(echo hi)`` — render an assistant tool_use block.

    Tool-specific arg formatting for the common Claude Code tools
    (Bash / Read / Write / Edit / NotebookEdit / Grep / Glob /
    Task / Skill / TodoWrite / WebFetch / WebSearch /
    AskUserQuestion). Unknown tools fall back to a compact input
    dict.
    """
    name = c.get("name", "?")
    inp = c.get("input", {}) or {}
    if name == "Bash":
        cmd = inp.get("command", "")
        return f"{GLYPH_TOOL} Bash({_short_repr(cmd, trunc)})"
    if name in ("Read", "Write", "Edit", "NotebookEdit"):
        path = inp.get("file_path", inp.get("path", "?"))
        return f"{GLYPH_TOOL} {name}({path})"
    if name == "Grep":
        pattern = inp.get("pattern", "?")
        filt = (inp.get("glob") or inp.get("path")
                or inp.get("type") or "")
        suffix = f", {filt}" if filt else ""
        return (f"{GLYPH_TOOL} Grep("
                f"{_short_repr(pattern, 60)}{suffix})")
    if name == "Glob":
        return (f"{GLYPH_TOOL} Glob("
                f"{inp.get('pattern', '?')})")
    if name == "Task":
        st = inp.get("subagent_type", "?")
        desc = inp.get("description", inp.get("prompt", ""))
        return (f"{GLYPH_TOOL} Task[{st}]("
                f"{_short_repr(desc, trunc)})")
    if name == "Skill":
        return f"{GLYPH_TOOL} Skill({inp.get('skill', '?')})"
    if name == "TodoWrite":
        todos = inp.get("todos", [])
        return f"{GLYPH_TOOL} TodoWrite({len(todos)} items)"
    if name == "WebFetch":
        return f"{GLYPH_TOOL} WebFetch({inp.get('url', '?')})"
    if name == "WebSearch":
        return (f"{GLYPH_TOOL} WebSearch("
                f"{_short_repr(inp.get('query', '?'), 60)})")
    if name == "AskUserQuestion":
        qs = inp.get("questions", [])
        return (f"{GLYPH_TOOL} AskUserQuestion("
                f"{len(qs)} question(s))")
    return f"{GLYPH_TOOL} {name}({_short_repr(inp, trunc)})"


def _render_tool_result_text(content: str, is_err: bool,
                                trunc: int) -> str:
    """Render a tool_result content body. Multi-line content
    gets indented continuation lines so the ``⎿`` column is
    visually clean."""
    prefix = (f"{GLYPH_RESULT}  " if not is_err
              else f"{GLYPH_RESULT}  ⚠️ ERROR: ")
    truncated = _truncate(content, trunc)
    lines = truncated.split("\n")
    if len(lines) == 1:
        return prefix + lines[0]
    out = [prefix + lines[0]]
    for line in lines[1:]:
        out.append("   " + line)
    return "\n".join(out)


def _coerce_tool_result_content(c: dict) -> str:
    """Normalize a ``tool_result`` content to a flat string. Claude
    sometimes returns content as a list of typed dicts."""
    content = c.get("content", "")
    if isinstance(content, list):
        parts: "list[str]" = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                else:
                    parts.append(_short_repr(item, 100))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if not isinstance(content, str):
        return json.dumps(content, ensure_ascii=False)
    return content


def _render_tool_result(c: dict, trunc: int) -> str:
    """``⎿  ...content...`` — render a user/tool_result block.

    LOAD-BEARING: if the content contains an inline ``::QPB::``
    sentinel (the 117 case — qpb_phase / quality_gate stdout
    captured by Claude as a tool_result), render the phase/gate
    line instead of the raw content snippet.
    """
    # Lazy import to keep this module import-light and avoid
    # circulars on bin.harness.status (which itself ends up
    # importing pieces of plan_runner).
    from bin.harness.status import (
        _SENTINEL_INLINE_RE, _format_sentinel_line)

    content_str = _coerce_tool_result_content(c)
    # Inline-sentinel check (117 preservation).
    for m in _SENTINEL_INLINE_RE.finditer(content_str):
        try:
            payload = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        rendered = _format_sentinel_line(payload)
        if rendered is not None:
            return rendered
    is_err = bool(c.get("is_error", False))
    return _render_tool_result_text(content_str, is_err, trunc)


def _render_assistant(d: dict, show_thinking: bool, trunc: int
                       ) -> "Iterable[str]":
    """Yield rendered lines for an assistant message."""
    msg = d.get("message", {}) or {}
    for c in msg.get("content", []) or []:
        if not isinstance(c, dict):
            continue
        ct = c.get("type")
        if ct == "text":
            text = c.get("text", "")
            if text.strip():
                yield text
        elif ct == "thinking":
            if show_thinking:
                thinking = c.get("thinking", "")
                if thinking.strip():
                    yield (f"  ⟨thinking⟩ "
                           f"{_truncate(thinking, trunc)}")
        elif ct == "tool_use":
            yield _render_tool_use(c, trunc)
        else:
            yield (f"  ⟨assistant.{ct or 'unknown'}⟩ "
                   f"{_short_repr(c, 200)}")


def _render_user(d: dict, trunc: int) -> "Iterable[str]":
    """Yield rendered lines for a user message (often
    tool_result, often with an embedded ::QPB:: sentinel)."""
    msg = d.get("message", {}) or {}
    content = msg.get("content", [])
    if isinstance(content, str):
        yield f"[user] {_truncate(content, trunc)}"
        return
    for c in content or []:
        if not isinstance(c, dict):
            yield f"[user] {_short_repr(c, 200)}"
            continue
        ct = c.get("type")
        if ct == "tool_result":
            yield _render_tool_result(c, trunc)
        elif ct == "text":
            yield (f"[user] "
                   f"{_truncate(c.get('text', ''), trunc)}")
        else:
            yield (f"  ⟨user.{ct or 'unknown'}⟩ "
                   f"{_short_repr(c, 200)}")


def _render_system(d: dict, trunc: int) -> "Iterable[str]":
    """Yield rendered lines for a system message."""
    sub = d.get("subtype", "")
    if sub == "init":
        cwd = d.get("cwd", "?")
        sid = (d.get("session_id", "") or "")[:8]
        model = d.get("model") or "?"
        tools = d.get("tools", []) or []
        yield _rule(
            f"session {sid} started "
            f"(model={model}, cwd={cwd}, "
            f"{len(tools)} tools)")
    elif sub == "task_started":
        desc = d.get("description", "?")
        st = d.get("subagent_type", "?")
        yield (f"{GLYPH_BULLET} Task[{st}] started: "
               f"{_truncate(desc, trunc)}")
    elif sub == "task_progress":
        desc = d.get("description", "?")
        usage = d.get("usage", {}) or {}
        tools_used = usage.get("tool_uses", 0)
        last = d.get("last_tool_name", "")
        suffix = f" [last={last}]" if last else ""
        yield (f"{GLYPH_BULLET} Task progress: "
               f"{_truncate(desc, 100)} "
               f"(tools_used={tools_used}{suffix})")
    elif sub == "task_notification":
        status = d.get("status", "?")
        summary = d.get("summary", "?")
        usage = d.get("usage", {}) or {}
        dur_ms = usage.get("duration_ms", 0)
        yield (f"{GLYPH_BULLET} Task {status}: "
               f"{_truncate(summary, trunc)} "
               f"({dur_ms / 1000:.1f}s)")
    else:
        yield (f"⟨system.{sub or 'unknown'}⟩ "
               f"{_short_repr(d, 200)}")


def _render_result(d: dict) -> str:
    """Terminal session banner — SUCCESS or ERROR with stats."""
    sub = d.get("subtype", "?")
    is_err = bool(d.get("is_error", False))
    cost = d.get("total_cost_usd")
    dur_ms = d.get("duration_ms", 0)
    turns = d.get("num_turns", 0)
    api_err = d.get("api_error_status")
    bits = [f"turns={turns}",
            f"duration={dur_ms / 1000:.1f}s"]
    if cost is not None:
        bits.append(f"cost=${cost:.4f}")
    if api_err:
        bits.append(f"api_error={api_err}")
    status = ("SUCCESS" if (sub == "success" and not is_err)
              else f"ERROR ({sub})")
    return _rule(
        f"session ended: {status} ({', '.join(bits)})")


def _render_rate_limit(d: dict) -> str:
    info = d.get("rate_limit_info", {}) or {}
    return (f"  ⟨rate_limit⟩ "
            f"status={info.get('status', '?')} "
            f"type={info.get('rateLimitType', '?')}")


def _render_unknown(d: dict) -> str:
    """Best-effort rendering for unrecognized JSON shapes."""
    if not isinstance(d, dict):
        return f"  ⟨raw⟩ {_short_repr(d, 200)}"
    if "type" in d:
        return (f"  ⟨{d['type']}."
                f"{d.get('subtype', '?')}⟩ "
                f"{_short_repr(d, 200)}")
    return f"  ⟨json⟩ {_short_repr(d, 200)}"


def _bare_sentinel(line: str) -> "str | None":
    """If ``line`` is a bare ``::QPB:: {...}`` sentinel and the
    payload renders to a phase/gate log line, return it. ``None``
    otherwise (caller passes through verbatim)."""
    from bin.harness.status import (
        _SENTINEL_PREFIX, _SENTINEL_RE, _format_sentinel_line)
    if not line.startswith(_SENTINEL_PREFIX):
        return None
    m = _SENTINEL_RE.match(line)
    if not m:
        return None
    try:
        payload = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    return _format_sentinel_line(payload)


def render_stream_line(line: str, *,
                         rendered: bool = True,
                         show_thinking: bool = True,
                         truncate: int = 800) -> str:
    """Render one ``stream.ndjson`` line. Multi-output is joined
    by ``\\n``; passthrough is returned unchanged.

    Args:
      line: raw stream.ndjson line (or any text).
      rendered: ``False`` ⇒ verbatim passthrough (raw mode, the
        ``j`` toggle's other state). ``True`` ⇒ Claude-Code-TUI-
        style rendering.
      show_thinking: ``True`` ⇒ render ``⟨thinking⟩`` blocks.
        ``False`` ⇒ skip them (compact log surfaces).
      truncate: cap string fields at N chars (default 800; 0 for
        no truncation).

    LOAD-BEARING ::QPB:: sentinel preservation: bare-line and
    inline-in-tool_result variants both substitute the phase/gate
    line for the raw content.
    """
    if not rendered:
        return line
    stripped_line = line.rstrip("\n")
    if not stripped_line.strip():
        return line
    # (1) Bare-line ::QPB:: sentinel — 109/117 form.
    sentinel = _bare_sentinel(stripped_line)
    if sentinel is not None:
        return sentinel
    # (2) JSON dispatch.
    try:
        d = json.loads(stripped_line)
    except (json.JSONDecodeError, ValueError):
        # Non-JSON plain text (codex / copilot CLI /
        # run_playbook stdout) — passthrough verbatim.
        return line
    if not isinstance(d, dict):
        return _render_unknown(d)
    t = d.get("type", "")
    if not t:
        # JSON but no ``type`` field — not a Claude event;
        # passthrough verbatim (other tools' structured output).
        return line
    out_lines: "list[str]" = []
    if t == "assistant":
        out_lines.extend(_render_assistant(
            d, show_thinking, truncate))
    elif t == "user":
        out_lines.extend(_render_user(d, truncate))
    elif t == "system":
        out_lines.extend(_render_system(d, truncate))
    elif t == "result":
        out_lines.append(_render_result(d))
    elif t == "rate_limit_event":
        out_lines.append(_render_rate_limit(d))
    else:
        out_lines.append(_render_unknown(d))
    if not out_lines:
        return ""
    return "\n".join(out_lines)
