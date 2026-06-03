"""v1.5.7 113 — detached collector must infer COMPLETED from
the LAST `result` event (is_error:false), not solely from
`gate-report-latest.json` presence + status summary BLOCKED
column.

Surfaced on the AUP-experiment: two Mode A gson runs completed
the full pipeline cleanly — full ``quality/`` trees (all 6
phases: EXPLORATION → COMPLETENESS_REPORT, test files, patches),
``result`` event ``is_error:false``, no AUP — but the detached
collector marked them **FAILED**. Root cause: the 108
orphan-inference classifies COMPLETED **only** from
``gate-report-latest.json`` presence; 112 added
``is_error:true → BLOCKED``, but the ``is_error:false →
COMPLETED`` half was never added, so a clean run that didn't
write that one file fell through to FAILED. Same bug also
silently miscounted 112's BLOCKED runs in the status summary
(``P=`` column ate them).

Coverage:
  * ``runner._classify_stream_terminal`` — new generalized
    classifier:
      * ``is_error:true`` ⇒ ``(BLOCKED, reason)``
      * ``is_error:false`` ⇒ ``(COMPLETED, "")``
      * no parseable ``result`` event ⇒ ``(None, "")``
        (inconclusive — callers fall back to artifacts so
        Mode B isn't regressed)
      * missing file / malformed lines / multi-result: same
        defensive shape as 112's helper
  * ``runner._stream_ended_in_api_error`` — preserved 112 API
    as a thin wrapper over ``_classify_stream_terminal``.
  * Detached collector (``plan_runner._collect_one_run_detached``):
      * **THE 113 MUTATION-BITE** — clean ``result`` event +
        populated ``quality/`` tree but **no**
        ``gate-report-latest.json`` ⇒ collector classifies
        COMPLETED and grading runs. Revert to the
        gate-report-only logic ⇒ the run is mislabeled
        FAILED (the actual AUP-experiment misclassification)
        and this test FAILS.
      * AUP refusal (``is_error:true``) ⇒ still BLOCKED (112
        preserved); TIMED_OUT precedence preserved.
      * Mode B path (no Claude ``result`` envelope at all) +
        ``gate-report-latest.json`` present ⇒ falls back to
        artifact heuristic ⇒ COMPLETED (Mode B not
        regressed).
      * No ``result`` event + no quality/ tree + dead PID ⇒
        FAILED.
  * ``status._summarize_harness_run`` BLOCKED column: a
    harness-run containing a BLOCKED run shows ``B=1``, not
    ``P=1`` / ``F=1``. ``format_harness_run_summary``
    includes ``B=`` between ``T`` and ``AP``.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness import runner as RUN
from bin.harness import schema as S
from bin.harness import status as ST


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_AUP_REFUSAL_BODY = (
    "API Error: Claude Code is unable to respond to this "
    "request, which appears to violate our Usage Policy "
    "(see https://www.anthropic.com/aup). Request ID: "
    "req_abc123."
)


def _aup_result_stream() -> "list[str]":
    """A claude stream that ends in an AUP refusal."""
    return [
        json.dumps({"type": "system", "subtype": "init"}),
        json.dumps({"type": "assistant", "content": "…"}),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "result": _AUP_REFUSAL_BODY,
        }),
    ]


def _clean_result_stream() -> "list[str]":
    """A claude stream that ends in a clean result event
    (``is_error:false``) — the new 113 COMPLETED signal."""
    return [
        json.dumps({"type": "system", "subtype": "init"}),
        json.dumps({"type": "assistant", "content": "Done."}),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "All phases completed.",
        }),
    ]


def _no_result_event_stream() -> "list[str]":
    """A stream that has NO `type:"result"` event — the Mode B
    case (run_playbook doesn't emit Claude's result envelope)
    or a truncated mid-flight stream. The classifier returns
    (None, "") so callers fall back to the artifact heuristic."""
    return [
        "[2026-05-26T19:00:00Z] phase 1 (validation) START",
        "[2026-05-26T19:00:30Z] phase 1 (validation) DONE",
        "[2026-05-26T19:01:00Z] phase 2 (exploration) START",
    ]


def _write_quality_tree(target_dir: Path, *,
                          include_gate_report: bool) -> None:
    """Write a populated ``quality/`` tree under ``target_dir``.
    Mimics what a clean playbook run produces. The
    ``gate-report-latest.json`` is OPTIONAL so 113's
    mutation-bite can exercise the "clean run / no report"
    case the AUP-experiment hit in production."""
    q = target_dir / "quality"
    q.mkdir(parents=True, exist_ok=True)
    (q / "EXPLORATION.md").write_text(
        "# Exploration\n", encoding="utf-8")
    (q / "COMPLETENESS_REPORT.md").write_text(
        "# Completeness Report\n", encoding="utf-8")
    (q / "tests").mkdir(exist_ok=True)
    (q / "tests" / "test_x.py").write_text(
        "def test_x(): pass\n", encoding="utf-8")
    if include_gate_report:
        results_dir = q / "results"
        results_dir.mkdir(exist_ok=True)
        (results_dir / "gate-report-latest.json").write_text(
            json.dumps({"verdict": "pass"}),
            encoding="utf-8",
        )


def _build_manifest(harness_run: Path, *,
                     run_dir: Path, target_dir: Path,
                     stream_lines: "list[str]") -> None:
    """Build a single-entry manifest.json that the orphan-
    polling collector can consume. Mirrors the 112 test
    helper but with the run_dir + target_dir paths the test
    actually populated."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "stream.ndjson").write_text(
        "\n".join(stream_lines) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "harness_run_dir": str(harness_run),
        "plan": {"pools": {"claude": 1}},
        "runs": [{
            "index": 0,
            "description": "113 mutation-bite",
            "repo": "https://github.com/x/y",
            "runner": "claude", "model": "opus",
            "channel": "clone", "mode": "A",
            "target_dir": str(target_dir),
            "run_dir": str(run_dir),
            "run_id": "r", "pid": 88888,
            "started_at": "2026-05-26T19:00:00Z",
            "stream_path": str(run_dir / "stream.ndjson"),
            "status_path": str(run_dir / "status.json"),
            "max_duration_s": 60.0,
            "expect": {"gate_result": "PASS"},
        }],
    }
    (harness_run / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Task A — _classify_stream_terminal helper
# ---------------------------------------------------------------------------


class ClassifyStreamTerminalTests(unittest.TestCase):
    """Pin the new classifier's contract:
       * is_error:true ⇒ BLOCKED (preserves 112)
       * is_error:false ⇒ COMPLETED (NEW: the 113 fix)
       * no result event ⇒ None (Mode B / truncated)"""

    def test_clean_result_event_classifies_as_completed(
            self) -> None:
        """**The 113 new signal**: a `result` event with
        `is_error:false` ⇒ COMPLETED. Pre-113 the classifier
        only returned `(blocked_bool, reason)` (the 112
        helper) — the COMPLETED half wasn't exposed."""
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                "\n".join(_clean_result_stream()) + "\n",
                encoding="utf-8",
            )
            state, reason = RUN._classify_stream_terminal(stream)
            self.assertEqual(state, S.TerminalState.COMPLETED)
            self.assertEqual(reason, "")

    def test_aup_result_event_classifies_as_blocked(self) -> None:
        """The 112 BLOCKED signal is preserved via the new
        classifier — the AUP body is returned as the reason."""
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                "\n".join(_aup_result_stream()) + "\n",
                encoding="utf-8",
            )
            state, reason = RUN._classify_stream_terminal(stream)
            self.assertEqual(state, S.TerminalState.BLOCKED)
            self.assertIn("Usage Policy", reason)

    def test_no_result_event_returns_none(self) -> None:
        """**Mode B path**: no Claude `result` envelope ⇒
        classifier inconclusive (None) — callers fall back to
        the artifact heuristic. This is how 113 avoids
        regressing run_playbook (which doesn't emit Claude's
        stream-json protocol)."""
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                "\n".join(_no_result_event_stream()) + "\n",
                encoding="utf-8",
            )
            state, reason = RUN._classify_stream_terminal(stream)
            self.assertIsNone(state)
            self.assertEqual(reason, "")

    def test_missing_file_returns_none(self) -> None:
        """Missing stream.ndjson ⇒ inconclusive, NOT a forced
        FAILED. The collector's artifact heuristic is the
        decider in this case."""
        with tempfile.TemporaryDirectory() as tmp:
            state, reason = RUN._classify_stream_terminal(
                Path(tmp) / "does-not-exist.ndjson"
            )
            self.assertIsNone(state)
            self.assertEqual(reason, "")

    def test_malformed_lines_ignored(self) -> None:
        """Garbage JSON lines are skipped; the helper returns
        based on whatever valid `result` event it finds."""
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                "this is not json\n"
                + json.dumps({
                    "type": "result",
                    "is_error": False,
                    "result": "Done.",
                }) + "\n"
                + "another non-json line\n",
                encoding="utf-8",
            )
            state, _ = RUN._classify_stream_terminal(stream)
            self.assertEqual(state, S.TerminalState.COMPLETED)

    def test_last_result_wins_when_multiple_present(
            self) -> None:
        """If a stream has multiple `result` events (defensive
        — shouldn't happen in practice), the LAST one
        determines the outcome. A run that errored early then
        recovered must NOT be misclassified as BLOCKED."""
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                json.dumps({
                    "type": "result", "is_error": True,
                    "result": "early aup",
                }) + "\n"
                + json.dumps({
                    "type": "result", "is_error": False,
                    "result": "recovered, done.",
                }) + "\n",
                encoding="utf-8",
            )
            state, _ = RUN._classify_stream_terminal(stream)
            self.assertEqual(state, S.TerminalState.COMPLETED)


# ---------------------------------------------------------------------------
# Task A — _stream_ended_in_api_error preserved (112 wrapper)
# ---------------------------------------------------------------------------


class StreamEndedInApiErrorPreservedTests(unittest.TestCase):
    """The 112 helper is now a thin wrapper over
    ``_classify_stream_terminal`` — verify its (bool, reason)
    shape stays intact so the 112 tests + any external callers
    keep working."""

    def test_wrapper_returns_true_on_aup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                "\n".join(_aup_result_stream()) + "\n",
                encoding="utf-8",
            )
            blocked, reason = RUN._stream_ended_in_api_error(
                stream)
            self.assertTrue(blocked)
            self.assertIn("Usage Policy", reason)

    def test_wrapper_returns_false_on_clean(self) -> None:
        """A clean run is NOT api-error — even though the
        underlying classifier now returns COMPLETED, the
        wrapper still maps it to ``(False, "")``."""
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                "\n".join(_clean_result_stream()) + "\n",
                encoding="utf-8",
            )
            blocked, reason = RUN._stream_ended_in_api_error(
                stream)
            self.assertFalse(blocked)
            self.assertEqual(reason, "")

    def test_wrapper_returns_false_on_inconclusive(
            self) -> None:
        """No `result` event ⇒ the classifier returns None;
        the 112 wrapper still maps that to ``(False, "")``
        (NOT blocked)."""
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                "\n".join(_no_result_event_stream()) + "\n",
                encoding="utf-8",
            )
            blocked, reason = RUN._stream_ended_in_api_error(
                stream)
            self.assertFalse(blocked)
            self.assertEqual(reason, "")


# ---------------------------------------------------------------------------
# Task A — detached collector COMPLETED inference (113 mutation-bite)
# ---------------------------------------------------------------------------


def _fake_facts_passing(target_dir, axes, transcript,
                          exit_code, raw_receipt,
                          timings=None, gate_stdout=None):
    """Stub for facts.extract_facts. The 113 mutation-bite
    only cares that the collector reaches the grading step
    (not what grade_expect produces) — but we still need a
    real RunFacts so grade_expect doesn't blow up."""
    from bin.harness.schema import (
        GateFacts, GateResult, VerdictFacts, VerdictState,
        Attribution, RunMetaFacts, Phase0Facts,
        ProvenanceFacts, InstallSurfaceFacts, RunFacts,
    )
    return RunFacts(
        phase0=Phase0Facts(status="ok", probe_attempts=1,
                            first_probe_ok=True),
        verdict=VerdictFacts(
            verdict_state=VerdictState.SOLID,
            attribution=Attribution.NONE,
            recommends_stronger_model=False,
            bugs_unverified_present=False,
        ),
        provenance=ProvenanceFacts(
            detected_runner="claude-code",
            selfreport_model_label=None,
            gate_bug_count=0,
            reported_bug_count=0,
            provenance_mismatch=False,
        ),
        gate=GateFacts(
            gate_total="Total: 0 FAIL, 0 WARN",
            gate_result=GateResult.PASS,
            cleanup_gaps=0,
            substantive_fail_count=0,
            record_keeping_fail_count=0,
        ),
        install=InstallSurfaceFacts(
            banner_rendered=True,
            gitignore_remediation_followed=True,
        ),
        run_meta=RunMetaFacts(
            blocked=False, stop_reason=None,
            exit_code=exit_code,
            timings=timings or {},
            raw_receipt=raw_receipt,
        ),
    )


class CollectorCompletedInferenceTests(unittest.TestCase):
    """The 108 orphan collector pre-113: ``COMPLETED`` was
    inferred ONLY from ``gate-report-latest.json`` presence.
    The AUP-experiment showed clean Mode A runs producing a
    full ``quality/`` tree WITHOUT that file (the report-
    writer step ran inconsistently across the experiment's
    runs); those were mislabeled ``FAILED``.

    Post-113: a ``result`` event with ``is_error:false`` is
    the authoritative COMPLETED signal. Artifact heuristic
    remains the fallback for Mode B / no-result-event
    streams.
    """

    def test_clean_result_event_yields_completed_without_gate_report(
            self) -> None:
        """**THE 113 MUTATION-BITE**: clean ``result`` event +
        populated ``quality/`` tree but **no**
        ``gate-report-latest.json`` ⇒ collector classifies
        COMPLETED and grading runs (result != "N/A" with a
        terminal_state of "FAILED").

        Pre-113 the collector required gate-report-latest.json
        for COMPLETED; without it, it fell through to FAILED.
        This test recreates the AUP-experiment's mis-label
        and asserts the new classifier closes the gap.

        Revert ``_classify_stream_terminal`` to None for
        ``is_error:false`` ⇒ the collector falls back to the
        artifact heuristic, sees no gate-report, marks
        FAILED, and this test FAILS."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            target_dir.mkdir(parents=True)
            _write_quality_tree(
                target_dir, include_gate_report=False,
            )
            _build_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=_clean_result_stream(),
            )
            from bin.harness import facts as F
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=False,
            ), mock.patch.object(F, "extract_facts",
                                   side_effect=_fake_facts_passing):
                outcomes = PR.collect_harness_run(harness_run)
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.COMPLETED.value,
                "113 mutation-bite: a clean `result` event "
                "MUST classify COMPLETED even without "
                "gate-report-latest.json — pre-113 the "
                "artifact-only logic mislabeled this exact "
                "shape FAILED (the AUP-experiment surfaced "
                "it on two real gson runs).",
            )
            # And grading actually ran (it's MET because the
            # fake facts return PASS).
            self.assertEqual(outcomes[0].result, "MET")

    def test_aup_stream_still_yields_blocked(self) -> None:
        """112 preserved: AUP refusal (``is_error:true``)
        forces BLOCKED, even with a populated ``quality/``
        tree (and even with a gate-report-latest.json from an
        earlier phase). The new classifier's BLOCKED branch
        is the same signal."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            target_dir.mkdir(parents=True)
            _write_quality_tree(
                target_dir, include_gate_report=True,
            )
            _build_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=_aup_result_stream(),
            )
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=False,
            ):
                outcomes = PR.collect_harness_run(harness_run)
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.BLOCKED.value,
            )
            self.assertEqual(outcomes[0].result, "N/A")
            status = json.loads(
                (run_dir / "status.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(status["terminal_state"],
                              "BLOCKED")
            self.assertIn("Usage Policy",
                            status.get("terminal_reason", ""))

    def test_mode_b_path_falls_back_to_artifact_heuristic(
            self) -> None:
        """**Mode B regression pin**: a stream with NO Claude
        `result` envelope (run_playbook output) + a
        ``gate-report-latest.json`` ⇒ classifier returns
        None (inconclusive) ⇒ collector falls back to the
        artifact heuristic ⇒ COMPLETED.

        Pre-113 this case worked via the artifact path; 113
        must NOT regress it. Revert
        ``_classify_stream_terminal`` to return FAILED on
        None ⇒ this test FAILS."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            target_dir.mkdir(parents=True)
            _write_quality_tree(
                target_dir, include_gate_report=True,
            )
            _build_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=_no_result_event_stream(),
            )
            from bin.harness import facts as F
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=False,
            ), mock.patch.object(F, "extract_facts",
                                   side_effect=_fake_facts_passing):
                outcomes = PR.collect_harness_run(harness_run)
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.COMPLETED.value,
                "113 must not regress Mode B: no Claude "
                "`result` event ⇒ classifier is "
                "inconclusive ⇒ artifact heuristic decides "
                "(gate-report-latest.json present ⇒ "
                "COMPLETED).",
            )

    def test_no_result_event_no_artifacts_yields_failed(
            self) -> None:
        """If the classifier is inconclusive AND there's no
        gate-report-latest.json AND no populated quality/
        tree, the collector marks FAILED (preserves the
        pre-113 fallback for a genuinely-dead run)."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            target_dir.mkdir(parents=True)
            # No quality/ tree, no gate-report.
            _build_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=_no_result_event_stream(),
            )
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=False,
            ):
                outcomes = PR.collect_harness_run(harness_run)
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.FAILED.value,
            )

    def test_stream_classifier_wins_over_max_duration_kill(
            self) -> None:
        """v1.5.7 120 inverted the precedence: a terminal
        `result` event in the stream WINS OVER the
        max-duration kill, because the kill is just reaping
        a hung-at-exit process (not interrupting work).
        Pre-120 (113's original assertion), this test
        asserted TIMED_OUT; the AUP-experiment showed why
        that was wrong (clean GATE-PASSED runs hit the
        claude --print exit-hang and were recorded
        TIMED_OUT). 120 fixes the precedence.

        For an AUP refusal stream specifically, the
        classifier returns BLOCKED — that's the recorded
        terminal state even when the deadline branch fires."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            target_dir.mkdir(parents=True)
            _build_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=_aup_result_stream(),
            )
            # Patch the manifest's max_duration_s to 0.0 so
            # the deadline trips on the first poll iteration.
            manifest_path = harness_run / "manifest.json"
            manifest = json.loads(manifest_path.read_text(
                encoding="utf-8"))
            manifest["runs"][0]["max_duration_s"] = 0.0
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )

            # PID stays alive ⇒ deadline branch fires.
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=True,
            ), mock.patch(
                "bin.harness.runner._kill_process_tree",
                return_value=None,
            ):
                outcomes = PR.collect_harness_run(harness_run)
            # v1.5.7 120: stream classifier wins. AUP-shaped
            # stream ⇒ BLOCKED (NOT TIMED_OUT). Pre-120 the
            # exit-hang made this fail when the run was
            # actually clean.
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.BLOCKED.value,
                "120: a terminal `result` event in the stream "
                "MUST win over the max-duration kill — the "
                "kill is just reaping a hung-at-exit process, "
                "not interrupting work. The AUP stream "
                "classifies BLOCKED.",
            )


# ---------------------------------------------------------------------------
# Task B — status.py BLOCKED column
# ---------------------------------------------------------------------------


def _write_status_json(run_dir: Path,
                        terminal_state: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(json.dumps({
        "state": "DONE",
        "pid": 7777,
        "started_at": "2026-05-26T19:00:00Z",
        "heartbeat": "2026-05-26T19:00:30Z",
        "ended_at": "2026-05-26T19:00:30Z",
        "exit_code": -1,
        "terminal_state": terminal_state,
        "terminal_reason": (
            "API Error … Usage Policy …"
            if terminal_state == "BLOCKED" else ""
        ),
    }, indent=2) + "\n", encoding="utf-8")


def _write_manifest_with_runs(
        harness_run_dir: Path,
        run_specs: "list[tuple[str, str]]") -> None:
    """``run_specs`` is a list of ``(run_id, terminal_state)``.
    Builds a manifest.json + per-run status.json with the
    given terminal_state. Used by the status-summary tests
    to drive `_summarize_harness_run` deterministically."""
    runs_entries = []
    for i, (run_id, terminal_state) in enumerate(run_specs):
        run_dir = harness_run_dir / f"run-{i:02d}"
        _write_status_json(run_dir, terminal_state)
        runs_entries.append({
            "index": i, "description": run_id,
            "repo": "x", "runner": "claude", "model": "opus",
            "channel": "clone", "mode": "A",
            "target_dir": str(run_dir / "target"),
            "run_dir": str(run_dir),
            "run_id": run_id, "pid": 7777,
            "started_at": "2026-05-26T19:00:00Z",
            "stream_path": str(run_dir / "stream.ndjson"),
            "status_path": str(run_dir / "status.json"),
            "max_duration_s": 60.0,
            "expect": {},
        })
    (harness_run_dir / "manifest.json").write_text(
        json.dumps({
            "harness_run_dir": str(harness_run_dir),
            "plan": {"pools": {"claude": 1}},
            "runs": runs_entries,
        }, indent=2) + "\n",
        encoding="utf-8",
    )


class StatusBlockedColumnTests(unittest.TestCase):
    """113 Task B: ``HarnessRunSummary`` gained a ``blocked``
    field. Pre-113 a BLOCKED run was miscounted as ``pending``
    (the AUP-experiment's run-00 showed ``P=1`` instead of
    ``B=1``)."""

    def test_summary_has_blocked_field_default_zero(
            self) -> None:
        """A harness-run with NO blocked runs ⇒ ``blocked == 0``
        (the field always exists, even when empty — operators
        can grep for ``B=0`` to confirm health)."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-26T19-00-00"
            harness_run.mkdir()
            _write_manifest_with_runs(harness_run, [
                ("r0", "COMPLETED"),
                ("r1", "COMPLETED"),
            ])
            [summary] = ST.list_harness_runs(runs_root)
            self.assertEqual(summary.blocked, 0)
            self.assertEqual(summary.completed, 2)

    def test_blocked_run_counted_in_blocked_column(
            self) -> None:
        """**Task B mutation-bite**: a harness-run with one
        BLOCKED run ⇒ ``B=1``, NOT ``P=1`` / ``F=1``. Revert
        ``_summarize_harness_run`` to the pre-113 branches
        (no BLOCKED case ⇒ `else: counts['pending']`) and
        this test FAILS — the AUP-experiment's run-00
        miscount."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-26T19-00-00"
            harness_run.mkdir()
            _write_manifest_with_runs(harness_run, [
                ("r0", "COMPLETED"),
                ("r1", "BLOCKED"),
                ("r2", "COMPLETED"),
            ])
            [summary] = ST.list_harness_runs(runs_root)
            self.assertEqual(
                summary.blocked, 1,
                "113 Task B: BLOCKED run must be counted in "
                "the BLOCKED column, not silently shoved into "
                "`pending` (pre-113 bug).",
            )
            self.assertEqual(summary.pending, 0)
            self.assertEqual(summary.failed, 0)
            self.assertEqual(summary.completed, 2)

    def test_format_includes_blocked_column(self) -> None:
        """``format_harness_run_summary`` must render ``B=`` in
        the row so the column shows up in ``qpb_harness status``."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-26T19-00-00"
            harness_run.mkdir()
            _write_manifest_with_runs(harness_run, [
                ("r0", "BLOCKED"),
            ])
            [summary] = ST.list_harness_runs(runs_root)
            line = ST.format_harness_run_summary(summary)
            self.assertIn("B= 1", line)

    def test_blocked_does_not_inflate_pending(self) -> None:
        """Pre-113 the pre-113 ``else`` branch silently shoved
        BLOCKED into ``pending``. Post-113 a BLOCKED run is
        counted as BLOCKED only — pending stays accurate."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-26T19-00-00"
            harness_run.mkdir()
            # Mix: 1 BLOCKED, 1 truly-PENDING (no status.json).
            _write_manifest_with_runs(harness_run, [
                ("r0", "BLOCKED"),
            ])
            # Add a pure-pending run (no status.json written)
            # by appending another manifest entry whose
            # run_dir doesn't have status.json.
            manifest_path = harness_run / "manifest.json"
            manifest = json.loads(manifest_path.read_text(
                encoding="utf-8"))
            pending_run_dir = harness_run / "run-01-pending"
            pending_run_dir.mkdir()
            manifest["runs"].append({
                "index": 1, "description": "pending",
                "repo": "x", "runner": "claude",
                "model": "opus", "channel": "clone",
                "mode": "A",
                "target_dir": str(pending_run_dir / "target"),
                "run_dir": str(pending_run_dir),
                "run_id": "pending", "pid": None,
                "started_at": "",
                "stream_path": str(
                    pending_run_dir / "stream.ndjson"),
                "status_path": str(
                    pending_run_dir / "status.json"),
                "max_duration_s": 60.0,
                "expect": {},
            })
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            [summary] = ST.list_harness_runs(runs_root)
            self.assertEqual(summary.blocked, 1)
            self.assertEqual(summary.pending, 1)


# ---------------------------------------------------------------------------
# Bundle-safety: 113 lives under bin/harness/ (excluded)
# ---------------------------------------------------------------------------


class BundleSafety113Tests(unittest.TestCase):

    def test_runner_and_plan_runner_and_status_under_harness(
            self) -> None:
        """113 touches bin/harness/runner.py +
        bin/harness/plan_runner.py + bin/harness/status.py +
        bin/tests/harness/test_collector_completed_inference_113.py
        — all under the excluded harness path."""
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"113 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
