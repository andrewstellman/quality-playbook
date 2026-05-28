"""v1.5.7 127 — Mode A phase-progress fallback from quality/
artifact presence (security review note #2).

The harness's phase visibility depends on the AI-CLI honoring
``bin/qpb_phase.py`` at each phase boundary (the ``::QPB::``
sentinel). If an agent skips one in Mode A, the TUI's
``current_phase`` falls back to ``—`` for the rest of the run
even though phases are progressing. The final gate verdict is
still authoritative — a UX gap, not a correctness issue — but a
Mode A run that finishes successfully should still show plausible
phase progress.

Mode B already has a fallback (``_mode_b_phase_from_stream``,
the ``Phase N/6 (Name)`` parse). Mode A didn't. 127 adds a
THIRD tier: scan ``<target>/quality/`` for known phase-boundary
artifacts (per ``_PHASE_ARTIFACTS``) and report the
highest-numbered phase whose primary artifact is present.

Three-tier resolution in ``_read_one_run_status``:
  Tier 1 — ``::QPB::`` sentinel (Mode A happy path)
  Tier 2 — Mode B ``Phase N/6`` stdout parse
  Tier 3 — quality/ artifact presence (this instruction)
  else   — ``—``

Sentinels and the Mode B fallback BOTH still WIN over the new
tier (load-bearing no-regression tests below).

Coverage:
  Unit (`_infer_phase_from_artifacts`):
    * None target / no quality dir ⇒ None
    * single Phase-1 artifact ⇒ P1 done
    * Phase-4 present, Phase-3 missing ⇒ P4 (reports highest
      EVIDENCE, never fabricates skipped progress)
    * Phase-3 alternates: BUGS.md alone ⇒ P3; RUN_CODE_REVIEW.md
      alone ⇒ P3
    * gate-report-latest.json (under results/, non-.md) ⇒ P6
    * secondary artifact (EXPLORATION_ITER2.md) ⇒ None (no
      misclassification of a half-finished Phase 1)
  Integration (`_read_one_run_status` via `read_run_status`):
    * **sentinel WINS over artifact fallback** (mutation-bite:
      if Tier 3 is mis-ordered above Tier 1, FAILS)
    * **Mode B fallback WINS over artifact fallback**
    * artifact fallback fires ONLY when both prior tiers empty
    * mid-run RUNNING + late artifact ⇒ latest-artifact phase,
      state "done"

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bin.harness import status as ST


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quality(target_dir: Path) -> Path:
    """Create + return ``<target>/quality/``."""
    q = target_dir / "quality"
    q.mkdir(parents=True, exist_ok=True)
    return q


def _touch(path: Path, body: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _embedded_sentinel_event(*, phase: int, name: str,
                                 state: str, ts: str) -> str:
    """A Claude stream-json event line carrying a ``::QPB::``
    phase sentinel embedded in tool_result.content (mirrors the
    real wire shape the 117 parser walks)."""
    sentinel_text = "::QPB:: " + json.dumps({
        "v": 1, "kind": "phase", "phase": phase,
        "name": name, "state": state, "ts": ts,
    })
    return json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [{
                "tool_use_id": "toolu_test",
                "type": "tool_result",
                "content": sentinel_text,
                "is_error": False,
            }],
        },
        "tool_use_result": {"stdout": sentinel_text,
                             "stderr": ""},
    })


def _write_run(harness_run_dir: Path, *,
                stream_lines: "list[str]",
                quality_artifacts: "list[str]" = (),
                status_state: "str | None" = None,
                terminal_state: "str | None" = None) -> None:
    """Stand up a one-run harness-run: a stream.ndjson, an
    optional status.json, and optional quality/ artifacts under
    the run's target dir. Mirrors the manifest shape
    `_read_one_run_status` consumes."""
    run_dir = harness_run_dir / "run-00"
    run_dir.mkdir(parents=True, exist_ok=True)
    target_dir = run_dir / "target"
    (run_dir / "stream.ndjson").write_text(
        ("\n".join(stream_lines) + "\n") if stream_lines else "",
        encoding="utf-8")
    if status_state is not None:
        (run_dir / "status.json").write_text(
            json.dumps({"state": status_state, "pid": None})
            + "\n", encoding="utf-8")
    for rel in quality_artifacts:
        _touch(target_dir / "quality" / rel)
    manifest = {
        "harness_run_dir": str(harness_run_dir),
        "plan": {"pools": {"claude": 1}},
        "runs": [{
            "index": 0, "description": "127 test",
            "repo": "https://github.com/x/y",
            "runner": "claude", "model": "opus",
            "channel": "clone", "mode": "A",
            "target_dir": str(target_dir),
            "run_dir": str(run_dir),
            "run_id": "r", "pid": None,
            "started_at": "",
            "stream_path": str(run_dir / "stream.ndjson"),
            "status_path": str(run_dir / "status.json"),
            "max_duration_s": 60.0,
            "expect": {},
            **({"terminal_state": terminal_state}
                if terminal_state else {}),
        }],
    }
    (harness_run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit — _infer_phase_from_artifacts
# ---------------------------------------------------------------------------


class InferPhaseFromArtifactsTests(unittest.TestCase):

    def test_none_target_returns_none(self) -> None:
        self.assertIsNone(ST._infer_phase_from_artifacts(None))

    def test_no_quality_dir_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # target exists but has no quality/ subdir.
            self.assertIsNone(
                ST._infer_phase_from_artifacts(Path(tmp)))

    def test_only_phase_1_artifact_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _touch(_quality(target) / "EXPLORATION.md")
            out = ST._infer_phase_from_artifacts(target)
            self.assertEqual(
                out, {"phase": 1, "name": "exploration",
                       "state": "done"})

    def test_phase_4_present_phase_3_missing(self) -> None:
        # Reports the HIGHEST evidence found — does NOT fabricate
        # progress for the skipped Phase 3.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            q = _quality(target)
            _touch(q / "EXPLORATION.md")
            _touch(q / "REQUIREMENTS.md")
            _touch(q / "COMPLETENESS_REPORT.md")  # phase 4
            out = ST._infer_phase_from_artifacts(target)
            self.assertEqual(out["phase"], 4)
            self.assertEqual(out["name"], "spec-audit")

    def test_phase_3_bugs_md_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _touch(_quality(target) / "BUGS.md")
            out = ST._infer_phase_from_artifacts(target)
            self.assertEqual(out["phase"], 3)
            self.assertEqual(out["name"], "code-review")

    def test_phase_3_run_code_review_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _touch(_quality(target) / "RUN_CODE_REVIEW.md")
            out = ST._infer_phase_from_artifacts(target)
            self.assertEqual(out["phase"], 3)

    def test_phase_6_gate_report_present(self) -> None:
        # gate-report-latest.json lives under quality/results/
        # (a subdir) — validates the non-.md is_file() check.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _touch(_quality(target) / "results"
                   / "gate-report-latest.json", "{}\n")
            out = ST._infer_phase_from_artifacts(target)
            self.assertEqual(out["phase"], 6)
            self.assertEqual(out["name"], "verification")

    def test_secondary_artifacts_ignored(self) -> None:
        # A secondary (iteration) artifact not in _PHASE_ARTIFACTS
        # must NOT count — a half-finished Phase 1 isn't complete.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _touch(_quality(target) / "EXPLORATION_ITER2.md")
            self.assertIsNone(
                ST._infer_phase_from_artifacts(target))


# ---------------------------------------------------------------------------
# Integration — three-tier resolution in _read_one_run_status
# ---------------------------------------------------------------------------


class ThreeTierResolutionTests(unittest.TestCase):

    def test_sentinel_wins_over_artifact_fallback(self) -> None:
        # **LOAD-BEARING / mutation-bite.** A sentinel AND a
        # quality artifact both present ⇒ the SENTINEL (Tier 1)
        # wins. If Tier 3 is mis-ordered above Tier 1, this FAILS.
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "run-A"
            _write_run(
                harness_run,
                stream_lines=[_embedded_sentinel_event(
                    phase=3, name="code-review", state="start",
                    ts="2026-05-28T01:00:00Z")],
                quality_artifacts=["EXPLORATION.md"],  # P1 evidence
            )
            runs = ST.read_run_status(harness_run)
            self.assertEqual(runs[0].current_phase, "P3")
            self.assertEqual(runs[0].current_phase_name,
                              "code-review")
            self.assertEqual(runs[0].current_phase_state, "start")

    def test_mode_b_fallback_wins_over_artifact_fallback(
            self) -> None:
        # **LOAD-BEARING.** A Mode B phase line AND a quality
        # artifact both present ⇒ the Mode B parse (Tier 2) wins.
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "run-B"
            _write_run(
                harness_run,
                stream_lines=[
                    "10:59:05   Phase 2/6 (Generate): target"],
                quality_artifacts=["EXPLORATION.md"],  # P1 evidence
            )
            runs = ST.read_run_status(harness_run)
            # Mode B says P2; artifact says P1 — Mode B wins.
            self.assertEqual(runs[0].current_phase, "P2")
            self.assertEqual(runs[0].current_phase_name,
                              "generation")

    def test_artifact_fallback_fires_when_prior_tiers_empty(
            self) -> None:
        # The 127 happy path: no sentinel, no Mode B line, only a
        # quality artifact ⇒ Tier 3 reports it.
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "run-C"
            _write_run(
                harness_run,
                stream_lines=["some unstructured agent text"],
                quality_artifacts=["EXPLORATION.md"],
            )
            runs = ST.read_run_status(harness_run)
            self.assertEqual(runs[0].current_phase, "P1")
            self.assertEqual(runs[0].current_phase_name,
                              "exploration")
            self.assertEqual(runs[0].current_phase_state, "done")

    def test_no_signal_no_artifact_stays_dash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "run-D"
            _write_run(
                harness_run,
                stream_lines=["nothing useful here"],
                quality_artifacts=[],
            )
            runs = ST.read_run_status(harness_run)
            self.assertEqual(runs[0].current_phase, "—")

    def test_mid_run_running_state_with_late_artifact(
            self) -> None:
        # status.json RUNNING (no terminal_state), P1 + P2
        # artifacts present ⇒ latest-artifact P2 done. The 121
        # terminal-override does NOT fire (state isn't terminal,
        # and "done" wouldn't be overridden anyway).
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "run-E"
            _write_run(
                harness_run,
                stream_lines=["unsentineled work"],
                quality_artifacts=["EXPLORATION.md",
                                    "REQUIREMENTS.md"],
                status_state="RUNNING",
            )
            runs = ST.read_run_status(harness_run)
            self.assertEqual(runs[0].current_phase, "P2")
            self.assertEqual(runs[0].current_phase_name,
                              "generation")
            self.assertEqual(runs[0].current_phase_state, "done")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
