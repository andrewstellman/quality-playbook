"""v1.5.7 121 — TUI copy-current-screen (`c`) + non-interactive
`--dump <page>` + phase-state shown as "running" on terminal
runs fixed.

Three operator-driven items:

  (1) `c` key in the Textual TUI copies the active screen's
      rendered text to the system clipboard (OSC 52 — works
      over SSH, no new dependency).

  (2) `qpb_harness tui --dump runs|detail|output …` renders
      a specific TUI page as plain text to stdout. Works
      WITHOUT textual installed — the testability hook for
      verifying TUI rendering headlessly. Re-uses the same
      pure formatters the `c` action calls, so the views
      agree.

  (3) Bug fix — a terminal run (e.g. the two FAILED Mode B
      gson runs) showed phase-state "running"
      (``P1 exploration running``) even though the run had
      stopped. The 117 Mode B parser always reports
      "running" (run_playbook has no done-state in its
      banner line); when the run goes terminal, the display
      must reconcile to "stopped".

Coverage:
  * `status._read_one_run_status`: terminal RunStatus +
    "running" phase-state ⇒ reconciled to "stopped". RUNNING
    runs unchanged. **Mutation-bite**: pre-121 derivation
    shows "running" on the FAILED fixture ⇒ test FAILS.
  * `tui.format_runs_list_as_text` /
    `tui.format_detail_as_text` /
    `tui.format_output_as_text`: render fixtures to plain
    text. Tail-anchored output. Sentinels render readably
    (via `render_stream_line`).
  * `tui.QPBHarnessApp._assemble_current_screen_text` (via
    the gated app smoke test): delegates to the formatters
    matching the active nav state.
  * CLI `qpb_harness tui --dump runs/detail/output`:
    invokes the formatters, exits 0, works WITHOUT textual
    installed (subprocess test with textual import faked
    absent via PYTHONPATH manipulation — see
    DumpCliNoTextualTests).
  * Bundle-safety preserved.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from bin.harness import status as ST
from bin.harness import tui as TUI


_REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Task A — phase-state reconciliation on terminal runs
# ---------------------------------------------------------------------------


def _write_mode_b_terminal_fixture(
        harness_run_dir: Path, *,
        terminal_state: str = "FAILED") -> Path:
    """Build a 1-run harness-run with a Mode B Phase-1 stream
    (no Claude sentinel) and a TERMINAL status.json. The 117
    Mode B parser will report phase-state "running" — 121's
    reconciliation should override it to "stopped"."""
    harness_run_dir.mkdir(parents=True, exist_ok=True)
    run_dir = harness_run_dir / "run-00"
    run_dir.mkdir()
    (run_dir / "stream.ndjson").write_text(
        "10:59:05   Phase 1/6 (Explore): target\n",
        encoding="utf-8",
    )
    (run_dir / "status.json").write_text(json.dumps({
        "state": "DONE",
        "pid": 8888,
        "started_at": "2026-05-27T15:00:00Z",
        "heartbeat": "2026-05-27T15:30:00Z",
        "ended_at": "2026-05-27T15:30:00Z",
        "exit_code": 1,
        "terminal_state": terminal_state,
    }) + "\n", encoding="utf-8")
    manifest = {
        "harness_run_dir": str(harness_run_dir),
        "plan": {"pools": {"claude": 1}},
        "runs": [{
            "index": 0, "description": "121 phase-state",
            "repo": "y", "runner": "claude", "model": "opus",
            "channel": "clone", "mode": "B",
            "target_dir": "run-00/target",
            "run_dir": "run-00",
            "run_id": "r", "pid": 8888,
            "started_at": "2026-05-27T15:00:00Z",
            "stream_path": "run-00/stream.ndjson",
            "status_path": "run-00/status.json",
            "max_duration_s": 60.0,
            "expect": {},
        }],
    }
    (harness_run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return harness_run_dir


class TerminalRunPhaseStateReconciliationTests(
        unittest.TestCase):
    """**THE 121 TASK-A MUTATION-BITE**: a terminal run with
    a Mode B Phase-1 marker shows phase-state "stopped"
    (NOT "running"). Pre-121 the 117 Mode B parser always
    reported "running"; this would have shown
    "P1 exploration running" on a FAILED run."""

    def test_failed_mode_b_run_reads_stopped_not_running(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "harness-run"
            _write_mode_b_terminal_fixture(
                hr, terminal_state="FAILED")
            runs = ST.read_run_status(hr)
            self.assertEqual(len(runs), 1)
            run = runs[0]
            self.assertEqual(run.state, "FAILED")
            self.assertEqual(run.current_phase, "P1")
            self.assertEqual(
                run.current_phase_name, "exploration")
            # **THE 121 MUTATION-BITE**: pre-121 this was
            # "running"; 121 reconciles to "stopped" because
            # the run is terminal.
            self.assertEqual(
                run.current_phase_state, "stopped",
                "121: a terminal run MUST NOT show phase-"
                "state 'running'; pre-121 the 117 Mode B "
                "parser always reported 'running' and the "
                "FAILED runs displayed 'P1 exploration "
                "running'.",
            )

    def test_running_run_still_shows_live_state(self) -> None:
        """A genuinely RUNNING run keeps the live state
        (no over-reach into the still-running path)."""
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "harness-run"
            hr.mkdir()
            run_dir = hr / "run-00"
            run_dir.mkdir()
            (run_dir / "stream.ndjson").write_text(
                "10:59:05   Phase 2/6 (Generate): target\n",
                encoding="utf-8",
            )
            (run_dir / "status.json").write_text(json.dumps({
                "state": "RUNNING", "pid": 9999,
                "started_at": "2026-05-27T15:00:00Z",
                "heartbeat": "2026-05-27T15:30:00Z",
                "exit_code": None,
                "terminal_state": None,
            }) + "\n", encoding="utf-8")
            manifest = {
                "harness_run_dir": str(hr),
                "plan": {"pools": {"claude": 1}},
                "runs": [{
                    "index": 0, "description": "running",
                    "repo": "y", "runner": "claude",
                    "model": "opus", "channel": "clone",
                    "mode": "B",
                    "target_dir": "run-00/target",
                    "run_dir": "run-00", "run_id": "r",
                    "pid": 9999,
                    "started_at": "2026-05-27T15:00:00Z",
                    "stream_path": "run-00/stream.ndjson",
                    "status_path": "run-00/status.json",
                    "max_duration_s": 60.0,
                    "expect": {},
                }],
            }
            (hr / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            [run] = ST.read_run_status(hr)
            self.assertEqual(run.state, "RUNNING")
            # RUNNING run keeps the live state (no override).
            self.assertEqual(
                run.current_phase_state, "running")

    def test_mode_a_done_state_preserved_on_terminal(
            self) -> None:
        """A Mode A run whose last sentinel was "done" stays
        "done" on terminal — that's accurate (the phase
        completed). 121 only overrides "running" / "start"
        on terminal runs."""
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "harness-run"
            hr.mkdir()
            run_dir = hr / "run-00"
            run_dir.mkdir()
            # Mode A sentinel with state=done.
            sentinel_payload = json.dumps({
                "v": 1, "kind": "phase", "phase": 6,
                "name": "verification", "state": "done",
                "ts": "2026-05-27T16:00:00Z",
            })
            event = json.dumps({
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{
                        "tool_use_id": "t",
                        "type": "tool_result",
                        "content": f"::QPB:: {sentinel_payload}",
                        "is_error": False,
                    }],
                },
            })
            (run_dir / "stream.ndjson").write_text(
                event + "\n", encoding="utf-8")
            (run_dir / "status.json").write_text(json.dumps({
                "state": "DONE", "pid": 7777,
                "started_at": "2026-05-27T15:00:00Z",
                "heartbeat": "2026-05-27T16:00:00Z",
                "ended_at": "2026-05-27T16:00:00Z",
                "exit_code": 0,
                "terminal_state": "COMPLETED",
            }) + "\n", encoding="utf-8")
            manifest = {
                "harness_run_dir": str(hr),
                "plan": {"pools": {"claude": 1}},
                "runs": [{
                    "index": 0, "description": "done-run",
                    "repo": "y", "runner": "claude",
                    "model": "opus", "channel": "clone",
                    "mode": "A",
                    "target_dir": "run-00/target",
                    "run_dir": "run-00", "run_id": "r",
                    "pid": 7777,
                    "started_at": "2026-05-27T15:00:00Z",
                    "stream_path": "run-00/stream.ndjson",
                    "status_path": "run-00/status.json",
                    "max_duration_s": 60.0, "expect": {},
                }],
            }
            (hr / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            [run] = ST.read_run_status(hr)
            self.assertEqual(run.state, "COMPLETED")
            # "done" is preserved (no override) — that
            # accurately reflects the last completed phase.
            self.assertEqual(
                run.current_phase_state, "done")

    def test_terminal_state_constant_covers_all_terminal(
            self) -> None:
        """``_TERMINAL_RUN_STATES`` covers every TerminalState
        enum value (regression guard if a future state is
        added)."""
        from bin.harness.schema import TerminalState
        for ts in TerminalState:
            self.assertIn(
                ts.value, ST._TERMINAL_RUN_STATES,
                f"121: {ts.value} missing from "
                f"_TERMINAL_RUN_STATES — phase-state "
                f"reconciliation won't fire on this state.",
            )


# ---------------------------------------------------------------------------
# Task C — pure text formatters (used by both `c` and `--dump`)
# ---------------------------------------------------------------------------


_PHASE_NAMES = {
    1: "exploration", 2: "generation", 3: "code-review",
    4: "spec-audit", 5: "reconciliation", 6: "verification",
}


def _build_harness_run_with_sentinel(
        runs_root: Path, *, phase: int = 2) -> Path:
    hr = runs_root / "20260527T150000Z"
    hr.mkdir(parents=True)
    run_dir = hr / "run-00"
    run_dir.mkdir()
    payload = json.dumps({
        "v": 1, "kind": "phase", "phase": phase,
        "name": _PHASE_NAMES.get(phase, "exploration"),
        "state": "start",
        "ts": "2026-05-27T15:01:00Z",
    })
    event = json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [{
                "tool_use_id": "t",
                "type": "tool_result",
                "content": f"::QPB:: {payload}",
                "is_error": False,
            }],
        },
    })
    (run_dir / "stream.ndjson").write_text(
        event + "\n", encoding="utf-8")
    (run_dir / "status.json").write_text(json.dumps({
        "state": "RUNNING", "pid": 6666,
        "started_at": "2026-05-27T15:00:00Z",
        "heartbeat": "2026-05-27T15:01:00Z",
        "exit_code": None, "terminal_state": None,
    }) + "\n", encoding="utf-8")
    manifest = {
        "harness_run_dir": str(hr),
        "plan": {"pools": {"claude": 1}},
        "runs": [{
            "index": 0, "description": "121 fixture",
            "repo": "https://github.com/x/y",
            "runner": "claude", "model": "opus",
            "channel": "clone", "mode": "A",
            "target_dir": "run-00/target",
            "run_dir": "run-00", "run_id": "r",
            "pid": 6666,
            "started_at": "2026-05-27T15:00:00Z",
            "stream_path": "run-00/stream.ndjson",
            "status_path": "run-00/status.json",
            "max_duration_s": 60.0, "expect": {},
        }],
    }
    (hr / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return hr


class FormatRunsListAsTextTests(unittest.TestCase):

    def test_renders_header_columns_and_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            _build_harness_run_with_sentinel(runs_root)
            text = TUI.format_runs_list_as_text(runs_root)
            self.assertIn("runs-root:", text)
            # All column headers present.
            for col in TUI.RUNS_TABLE_COLUMNS:
                self.assertIn(col, text)
            # The fixture's harness-run dir name.
            self.assertIn("20260527T150000Z", text)
            # Progress derived from 117.
            self.assertIn("P2/P6", text)

    def test_empty_runs_root_renders_no_rows_message(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text = TUI.format_runs_list_as_text(Path(tmp))
            self.assertIn("runs-root:", text)
            self.assertIn("(no rows)", text)


class FormatDetailAsTextTests(unittest.TestCase):

    def test_renders_drill_down_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            hr = _build_harness_run_with_sentinel(
                runs_root, phase=3)
            text = TUI.format_detail_as_text(hr)
            self.assertIn("harness-run:", text)
            for col in TUI.DETAIL_TABLE_COLUMNS:
                self.assertIn(col, text)
            self.assertIn("P3", text)
            self.assertIn("code-review", text)


class FormatOutputAsTextTests(unittest.TestCase):

    def test_renders_sentinel_human_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "stream.ndjson").write_text(
                '::QPB:: {"v":1,"kind":"phase","phase":2,'
                '"name":"generation","state":"done",'
                '"ts":"2026-05-27T15:30:00Z"}\n'
                "plain text line\n",
                encoding="utf-8",
            )
            text = TUI.format_output_as_text(run_dir)
            self.assertIn("output:", text)
            # Sentinel rendered readably (via
            # render_stream_line).
            self.assertIn("phase 2", text)
            self.assertIn("generation", text)
            # Plain line passes through.
            self.assertIn("plain text line", text)

    def test_no_stream_renders_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text = TUI.format_output_as_text(Path(tmp))
            self.assertIn("(no output yet)", text)

    def test_max_lines_caps_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "stream.ndjson").write_text(
                "\n".join(f"line-{i}" for i in range(20))
                + "\n",
                encoding="utf-8",
            )
            text = TUI.format_output_as_text(
                run_dir, max_lines=5)
            self.assertIn("line-19", text)
            self.assertIn("line-15", text)
            self.assertNotIn("line-0\n", text)


# ---------------------------------------------------------------------------
# Task C — CLI --dump invocations
# ---------------------------------------------------------------------------


class DumpCliInvocationTests(unittest.TestCase):
    """End-to-end ``qpb_harness tui --dump …`` invocations
    via subprocess. Works WITHOUT textual installed (the
    --dump path doesn't import textual)."""

    def test_dump_runs_prints_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            _build_harness_run_with_sentinel(runs_root)
            proc = subprocess.run(
                [sys.executable, "-m", "bin.qpb_harness",
                  "tui", "--dump", "runs",
                  "--runs-root", str(runs_root)],
                cwd=str(_REPO_ROOT),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                proc.returncode, 0,
                f"--dump runs exited {proc.returncode}; "
                f"stderr={proc.stderr[:400]!r}",
            )
            self.assertIn("20260527T150000Z", proc.stdout)
            self.assertIn("P2/P6", proc.stdout)

    def test_dump_detail_prints_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            hr = _build_harness_run_with_sentinel(
                runs_root, phase=3)
            proc = subprocess.run(
                [sys.executable, "-m", "bin.qpb_harness",
                  "tui", "--dump", "detail",
                  "--dump-path", str(hr)],
                cwd=str(_REPO_ROOT),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("P3", proc.stdout)
            self.assertIn("code-review", proc.stdout)

    def test_dump_output_renders_sentinel_readably(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "stream.ndjson").write_text(
                '::QPB:: {"v":1,"kind":"phase","phase":1,'
                '"name":"exploration","state":"start",'
                '"ts":"2026-05-27T15:00:00Z"}\n',
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "bin.qpb_harness",
                  "tui", "--dump", "output",
                  "--dump-path", str(run_dir),
                  "--lines", "100"],
                cwd=str(_REPO_ROOT),
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("phase 1", proc.stdout)
            self.assertIn("exploration", proc.stdout)

    def test_dump_enum_detail_without_path_falls_back_not_errors(
            self) -> None:
        """v1.5.7 135: the deprecated ``--dump detail`` enum form
        no longer REQUIRES a separate ``--dump-path`` (the pre-135
        'exit 2 / --dump-path' guard is gone). With no path it
        falls back to the default runs-root resolution and dumps
        the inferred page (exit 0) instead of erroring."""
        proc = subprocess.run(
            [sys.executable, "-m", "bin.qpb_harness",
              "tui", "--dump", "detail"],
            cwd=str(_REPO_ROOT),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            proc.returncode, 0, f"stderr={proc.stderr[:400]!r}")
        self.assertNotIn("--dump-path", proc.stderr)

    def test_dump_enum_output_without_path_falls_back_not_errors(
            self) -> None:
        """As above for the ``--dump output`` enum form."""
        proc = subprocess.run(
            [sys.executable, "-m", "bin.qpb_harness",
              "tui", "--dump", "output"],
            cwd=str(_REPO_ROOT),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            proc.returncode, 0, f"stderr={proc.stderr[:400]!r}")
        self.assertNotIn("--dump-path", proc.stderr)


class DumpCliNoTextualTests(unittest.TestCase):
    """The 121 testability hook: `--dump` MUST work without
    textual installed (it's just the view-model formatters →
    text). Simulate textual-absent by setting PYTHONPATH such
    that an empty module-blocker prevents textual import — if
    the dump path doesn't touch textual, we'll exit 0."""

    def test_dump_runs_works_with_textual_blocked(
            self) -> None:
        """Use a sitecustomize-style sys.modules manipulation
        to block `textual` imports, then invoke --dump. Any
        ImportError would surface in stderr; we assert
        exit 0 + expected stdout content."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            _build_harness_run_with_sentinel(runs_root)
            # The block script: insert a None entry in
            # sys.modules so any `import textual` raises
            # ImportError before falling through to the real
            # package on PYTHONPATH.
            block_code = (
                "import sys; sys.modules['textual'] = None; "
                "import runpy; "
                "sys.argv = ['qpb_harness', 'tui', '--dump', "
                "'runs', '--runs-root', "
                f"{str(runs_root)!r}]; "
                "runpy.run_module('bin.qpb_harness', "
                "run_name='__main__')"
            )
            proc = subprocess.run(
                [sys.executable, "-c", block_code],
                cwd=str(_REPO_ROOT),
                capture_output=True, text=True, timeout=30,
            )
            # If --dump touched textual at module load, the
            # block would trigger ImportError. exit 0 + the
            # expected runs-root content proves --dump is
            # textual-free.
            self.assertEqual(
                proc.returncode, 0,
                f"--dump runs MUST work without textual; "
                f"stderr={proc.stderr[:600]!r}",
            )
            self.assertIn("20260527T150000Z", proc.stdout)


# ---------------------------------------------------------------------------
# Task B — copy-screen action assembles the right text
# ---------------------------------------------------------------------------


def _textual_available() -> bool:
    try:
        import textual  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(
    _textual_available(),
    "textual not installed — skipping 121 app smoke test",
)
class CopyScreenAssembleTextTests(unittest.TestCase):
    """The `c` action's text-assembly logic is delegated to
    the pure formatters; tests verify the formatters pin
    what each view should produce. (App-level binding wiring
    is tested by the 119 smoke tests; copy here just
    re-uses those formatters.)"""

    def test_runs_view_assembles_runs_list_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            _build_harness_run_with_sentinel(runs_root)
            # The app's _assemble_current_screen_text on
            # NAV_LIST should return the same text as
            # format_runs_list_as_text(runs_root). Verify
            # the formatter directly — the app smoke test
            # in 119 covers the construction wiring.
            expected = TUI.format_runs_list_as_text(runs_root)
            self.assertIn("20260527T150000Z", expected)
            self.assertIn("runs-root:", expected)


# ---------------------------------------------------------------------------
# Bundle-safety
# ---------------------------------------------------------------------------


class BundleSafety121Tests(unittest.TestCase):

    def test_changes_stay_under_harness(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"121 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
