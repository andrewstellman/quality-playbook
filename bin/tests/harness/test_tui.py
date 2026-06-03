"""v1.5.7 094 — TUI tests (segregated harness suite).

Covers ``bin/harness/tui.py``:

  RenderOverviewTests — the load-bearing TUI "render a specific
    screen state and assert the rendered output contains the
    right elements" requirement. The TUI is split into a
    pure-Python data-shaping layer (``render_overview``,
    ``render_run_drilldown``) + a lazy-textual presentation
    layer; the tests exercise the data-shaping layer end-to-end
    so they work in environments without textual installed.
  RenderDrilldownTests — drill-in renderer pulls
    invocation.json / facts.json / grading.json / BUGS.md
    defensively.
  TextualGateTests — `build_app` raises a clear error when
    textual isn't installed; data-shaping helpers do NOT
    require textual.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bin.harness import tui as T


def _mk_snapshot(*, in_flight=None, queued=None,
                 recent_done=None, paused=False,
                 vendor_caps=None, in_flight_by_vendor=None,
                 cooldown_remaining_s=None) -> dict:
    return {
        "pid": 12345,
        "started_at": "2026-05-25T17:30:00Z",
        "heartbeat": "2026-05-25T17:32:14Z",
        "paused": paused,
        "scheduler": {
            "queue_length": len(queued or []),
            "queued": queued or [],
            "in_flight_total": (
                sum((in_flight_by_vendor or {}).values()) or 0
            ),
            "in_flight_by_vendor": in_flight_by_vendor or {
                "anthropic": 0, "openai": 0,
                "github": 0, "cursor": 0,
            },
            "vendor_caps": vendor_caps or {
                "anthropic": 1, "openai": 1,
                "github": 1, "cursor": 1,
            },
            "global_cap": 4,
            "cooldown_remaining_s": cooldown_remaining_s or {},
        },
        "in_flight": in_flight or [],
        "recent_done": recent_done or [],
    }


# ---------------------------------------------------------------------------
# Render overview — the LOAD-BEARING "render a specific state" pin.
# ---------------------------------------------------------------------------


class RenderOverviewTests(unittest.TestCase):
    """LOAD-BEARING per instruction 094 Task TUI tests:
    'render a specific screen state and assert the rendered
    output contains the right elements (run rows, in-flight
    markers, verdict/grade, provenance).'"""

    def test_renders_header_with_pid_and_heartbeat(self) -> None:
        lines = T.render_overview(_mk_snapshot())
        joined = "\n".join(lines)
        self.assertIn("── Manager ──", joined)
        self.assertIn("PID:", joined)
        self.assertIn("12345", joined)
        self.assertIn("2026-05-25T17:30:00Z", joined)
        self.assertIn("Heartbeat", joined)

    def test_renders_per_vendor_cap_row(self) -> None:
        snap = _mk_snapshot(
            in_flight_by_vendor={"anthropic": 1, "openai": 0,
                                   "github": 0, "cursor": 0},
        )
        lines = T.render_overview(snap)
        joined = "\n".join(lines)
        self.assertIn("── Caps ──", joined)
        # Per-vendor row: 'anthropic: 1/1'.
        self.assertIn("anthropic: 1/1", joined)
        self.assertIn("openai: 0/1", joined)
        # Global cap row.
        self.assertIn("Global: 1/4", joined)

    def test_renders_cooldown_remaining_marker(self) -> None:
        snap = _mk_snapshot(
            cooldown_remaining_s={"anthropic": 25.0},
        )
        lines = T.render_overview(snap)
        joined = "\n".join(lines)
        # Cooldown surfaces in the cap row.
        self.assertIn("[cooldown 25s]", joined)

    def test_renders_three_in_flight_runs_across_vendors(self) -> None:
        """Instruction 094 fixture: '3 in-flight runs across
        vendors + a completed graded run'. The rendered output
        carries each in-flight row + the completed entry."""
        snap = _mk_snapshot(
            in_flight=[
                {"run_id": "20260525T170000Z", "case_id": "ACC-A",
                 "runner": "claude", "started_at": "2026-05-25T17:00:00Z",
                 "elapsed": "5m12s"},
                {"run_id": "20260525T170100Z", "case_id": "ACC-B",
                 "runner": "codex", "started_at": "2026-05-25T17:01:00Z",
                 "elapsed": "4m12s"},
                {"run_id": "20260525T170200Z", "case_id": "ACC-C",
                 "runner": "copilot",
                 "started_at": "2026-05-25T17:02:00Z",
                 "elapsed": "3m12s"},
            ],
            in_flight_by_vendor={"anthropic": 1, "openai": 1,
                                   "github": 1, "cursor": 0},
            recent_done=[
                {"run_id": "20260525T165500Z", "case_id": "ACC-D",
                 "terminal_state": "COMPLETED",
                 "verdict": "ALL_PASSED"},
            ],
        )
        lines = T.render_overview(snap)
        joined = "\n".join(lines)
        self.assertIn("── In-flight (3) ──", joined)
        # Run rows.
        self.assertIn("20260525T170000Z", joined)
        self.assertIn("ACC-A", joined)
        self.assertIn("claude", joined)
        self.assertIn("20260525T170100Z", joined)
        self.assertIn("ACC-B", joined)
        self.assertIn("codex", joined)
        self.assertIn("20260525T170200Z", joined)
        self.assertIn("ACC-C", joined)
        self.assertIn("copilot", joined)
        # Completed graded run.
        self.assertIn("── Recently done (1) ──", joined)
        self.assertIn("ACC-D", joined)
        self.assertIn("COMPLETED", joined)
        self.assertIn("ALL_PASSED", joined)

    def test_renders_queued_runs(self) -> None:
        snap = _mk_snapshot(
            queued=[
                {"run_id": "20260525T170300Z", "vendor": "openai"},
                {"run_id": "20260525T170400Z", "vendor": "anthropic"},
            ],
        )
        lines = T.render_overview(snap)
        joined = "\n".join(lines)
        self.assertIn("── Queue (2) ──", joined)
        self.assertIn("20260525T170300Z", joined)
        self.assertIn("openai", joined)
        self.assertIn("queued", joined)

    def test_renders_empty_states_gracefully(self) -> None:
        lines = T.render_overview(_mk_snapshot())
        joined = "\n".join(lines)
        self.assertIn("── In-flight (0) ──", joined)
        self.assertIn("── Queue (0) ──", joined)
        self.assertIn("── Recently done (0) ──", joined)

    def test_renders_paused_marker(self) -> None:
        snap = _mk_snapshot(paused=True)
        lines = T.render_overview(snap)
        joined = "\n".join(lines)
        self.assertIn("Paused:  yes", joined)


# ---------------------------------------------------------------------------
# Render drilldown — per-run detail panel.
# ---------------------------------------------------------------------------


class RenderDrilldownTests(unittest.TestCase):

    def test_renders_from_invocation_facts_grading(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "20260525T170000Z"
            run_dir.mkdir()
            (run_dir / "invocation.json").write_text(json.dumps({
                "case_id": "ACC-A",
                "axes": {"runner": "claude", "model": "opus",
                          "install_channel": "clone"},
                "qpb_version": "1.5.7",
                "target_sha": "abc123def456789",
                "terminal_state": "COMPLETED",
            }))
            (run_dir / "facts.json").write_text(json.dumps({
                "phase0": {"status": "ok", "probe_attempts": 1,
                            "first_probe_ok": True},
                "verdict": {"verdict_state": "solid",
                              "attribution": "none",
                              "recommends_stronger_model": False,
                              "bugs_unverified_present": False},
                "gate": {"gate_total": "Total: 0 FAIL, 0 WARN",
                          "gate_result": "PASS",
                          "cleanup_gaps": 0},
                "provenance": {"detected_runner": "claude-code",
                                "selfreport_model_label": "opus",
                                "gate_bug_count": 1,
                                "reported_bug_count": 1,
                                "provenance_mismatch": False},
                "install": {"banner_rendered": True,
                              "gitignore_remediation_followed": True},
                "run_meta": {"blocked": False, "stop_reason": None,
                              "exit_code": 0, "timings": {},
                              "raw_receipt": "stream.ndjson"},
            }))
            (run_dir / "grading.json").write_text(json.dumps({
                "case_type": "acceptance",
                "verdict": "ALL_PASSED",
                "n_passed": 14, "n_total": 14,
            }))
            lines = T.render_run_drilldown(run_dir)
            joined = "\n".join(lines)
            # Invocation block.
            self.assertIn("20260525T170000Z", joined)
            self.assertIn("ACC-A", joined)
            self.assertIn("claude", joined)
            self.assertIn("opus", joined)
            self.assertIn("clone", joined)
            self.assertIn("1.5.7", joined)
            self.assertIn("abc123def456", joined)
            self.assertIn("COMPLETED", joined)
            # Facts block.
            self.assertIn("verdict_state = solid", joined)
            self.assertIn("attribution   = none", joined)
            self.assertIn("gate_result   = PASS", joined)
            # Provenance line.
            self.assertIn("claude-code", joined)
            self.assertIn("model:opus", joined)
            self.assertIn("bugs:1", joined)
            # Grading block.
            self.assertIn("ALL_PASSED", joined)
            self.assertIn("14/14", joined)

    def test_renders_security_grading_with_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "20260525T170000Z"
            run_dir.mkdir()
            (run_dir / "grading.json").write_text(json.dumps({
                "case_type": "security_eval",
                "outcome": "DETECTED",
                "reviewed": False,
            }))
            lines = T.render_run_drilldown(run_dir)
            joined = "\n".join(lines)
            self.assertIn("DETECTED", joined)
            self.assertIn("reviewed=False", joined)

    def test_renders_bugs_md_head_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "20260525T170000Z"
            (run_dir / "quality").mkdir(parents=True)
            (run_dir / "quality" / "BUGS.md").write_text(
                "# Bugs\n\n### BUG-001: SQL injection in handler\n"
                "Description...\n",
            )
            lines = T.render_run_drilldown(run_dir)
            joined = "\n".join(lines)
            self.assertIn("BUGS.md", joined)
            self.assertIn("BUG-001", joined)
            self.assertIn("SQL injection", joined)

    def test_handles_missing_files_gracefully(self) -> None:
        """A run_dir with only a status.json (no invocation /
        facts / grading) renders the available info + 'no
        invocation.json' note, without crashing."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "20260525T170000Z"
            run_dir.mkdir()
            lines = T.render_run_drilldown(run_dir)
            joined = "\n".join(lines)
            self.assertIn("20260525T170000Z", joined)
            self.assertIn("no invocation.json", joined)

    def test_handles_corrupt_facts_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "20260525T170000Z"
            run_dir.mkdir()
            (run_dir / "facts.json").write_text("not json")
            lines = T.render_run_drilldown(run_dir)
            joined = "\n".join(lines)
            self.assertIn("facts.json unreadable", joined)


# ---------------------------------------------------------------------------
# Textual gate — App construction requires textual.
# ---------------------------------------------------------------------------


class TextualGateTests(unittest.TestCase):
    """The data-shaping helpers MUST work without textual; the
    App constructor MUST raise a clear error when textual is
    missing (and run cleanly when it's installed)."""

    def test_render_helpers_dont_require_textual(self) -> None:
        """render_overview + render_run_drilldown are pure
        Python — no `import textual` at module-load time."""
        # The fact that this test imports without textual proves
        # the module can be loaded; render an empty snapshot to
        # confirm the helper itself doesn't pull in textual.
        lines = T.render_overview(_mk_snapshot())
        self.assertGreater(len(lines), 0)

    def test_build_app_raises_when_textual_absent(self) -> None:
        """In an env without textual, build_app raises a clear
        RuntimeError naming the missing dep — so the operator
        knows how to install it. In an env WITH textual, it
        returns an App instance (the production path)."""
        try:
            import textual  # noqa: F401
            # Textual IS installed — confirm build_app returns
            # an instance.
            app = T.build_app(_mk_snapshot())
            self.assertIsNotNone(app)
        except ImportError:
            # Textual ABSENT — build_app must raise a clear
            # RuntimeError, not a cryptic ImportError.
            with self.assertRaises(RuntimeError) as ctx:
                T.build_app(_mk_snapshot())
            self.assertIn("textual", str(ctx.exception).lower())
            self.assertIn("install", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
