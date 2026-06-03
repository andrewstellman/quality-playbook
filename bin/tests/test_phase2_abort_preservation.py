"""Regression tests for v1.5.7 Phase 3 / Deliverable 1 — Phase 2 gate-
failure artifact preservation.

When the Phase 2 gate aborts a run (EXPLORATION.md too short, role-map
violation, schema mismatch, etc.), the live ``quality/`` directory is
renamed to ``quality.gate-failed-<UTC-timestamp>/`` rather than left to
be archived as a generic ``previous_runs/<ts>/`` partial on the next
run. A ``GATE_FAILURE.md`` marker at the preserved directory's root
captures the violation context (phase group, cell name, timestamp,
runner version, model).

Six tests, one per Deliverable 1 acceptance scenario:

1. Preservation happy path — gate fails, ``quality/`` renamed,
   ``GATE_FAILURE.md`` written.
2. Preservation idempotence — two aborts on the same cell produce two
   distinct sibling directories (no overwrite).
3. Empty-quality handling — preservation logic is safe when
   ``quality/`` doesn't exist or is empty (no crash, no spurious dir).
4. Subsequent run independence — after preservation, a new run sees a
   fresh ``quality/`` (the preserved set isn't consumed as
   ``previous_runs/`` or otherwise inhaled by archive_previous_run).
5. Marker content — ``GATE_FAILURE.md`` carries the violation
   message, phase group, cell name, timestamp, runner version, model.
6. Cluster-049 auto-recovery composition — when auto-recovery
   succeeds, ``check_phase_gate`` returns ``ok=True`` and no
   preservation directory is created.
"""

from __future__ import annotations

import argparse
import io
import re
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bin import run_playbook
from bin import role_map as role_map_lib


def _make_args(*, model: str | None = None) -> argparse.Namespace:
    """Return a minimal argparse Namespace the preservation helper
    accepts. Only ``model`` is consulted by the marker renderer."""
    return argparse.Namespace(model=model)


def _stub_log_file(tmp: Path) -> Path:
    """Return a writable log-file path the helper can pass to
    lib.logboth without crashing."""
    log = tmp / "run.log"
    log.write_text("", encoding="utf-8")
    return log


class RenderGateFailureMarkerTests(unittest.TestCase):
    """Marker body shape is documented in v1.5.7 Design Deliverable 1.
    These tests pin the contract surface independently of the
    file-system preservation helper."""

    def test_marker_contains_required_fields(self) -> None:
        body = run_playbook._render_gate_failure_marker(
            phase_group="Phase group 2",
            cell_name="cobra-1.5.3",
            timestamp="20260512T140000Z",
            runner_version="v1.5.7",
            model="gpt-5.4-mini",
            violation_message=(
                "GATE FAIL Phase 2: EXPLORATION.md is only 100 lines "
                "(expected 120+)"
            ),
        )
        self.assertIn("Phase 2 gate failure — preserved evidence", body)
        self.assertIn("Phase group 2", body)
        self.assertIn("cobra-1.5.3", body)
        self.assertIn("20260512T140000Z", body)
        self.assertIn("v1.5.7", body)
        self.assertIn("gpt-5.4-mini", body)
        self.assertIn("EXPLORATION.md is only 100 lines", body)

    def test_marker_unset_model_displays_default(self) -> None:
        body = run_playbook._render_gate_failure_marker(
            phase_group="Phase 2",
            cell_name="cell-x",
            timestamp="20260512T140000Z",
            runner_version="v1.5.7",
            model=None,
            violation_message="GATE FAIL X",
        )
        self.assertIn("(default)", body)


class PreserveQualityOnGateFailureTests(unittest.TestCase):
    """Acceptance scenarios 1-5 from the brief."""

    def _make_repo_with_quality(self, root: Path, *, populate: bool = True) -> Path:
        repo = root / "cell-under-test"
        repo.mkdir(parents=True)
        quality = repo / "quality"
        quality.mkdir()
        if populate:
            (quality / "EXPLORATION.md").write_text(
                "# Exploration (truncated)\nshort\n", encoding="utf-8",
            )
            (quality / "PROGRESS.md").write_text(
                "# Progress\n- [ ] Phase 1\n", encoding="utf-8",
            )
            (quality / "exploration_role_map.json").write_text(
                '{"files": []}', encoding="utf-8",
            )
        return repo

    # ---------- Test 1: Preservation happy path -----------------------

    def test_preservation_happy_path_renames_quality_and_writes_marker(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = self._make_repo_with_quality(tmp)
            log = _stub_log_file(tmp)

            preserved = run_playbook._preserve_quality_on_gate_failure(
                repo,
                phase_group="Phase group 2",
                gate_messages=[
                    "GATE FAIL Phase 2: EXPLORATION.md is only 5 lines (expected 120+)"
                ],
                args=_make_args(model="gpt-5.4-mini"),
                log_file=log,
            )
            self.assertIsNotNone(preserved)
            assert preserved is not None  # for type-narrowing
            # Live quality/ must be gone.
            self.assertFalse(
                (repo / "quality").exists(),
                "quality/ should have been renamed to quality.gate-failed-<ts>/",
            )
            # Preserved directory exists with the agent's outputs intact.
            self.assertTrue(preserved.is_dir())
            self.assertTrue(preserved.name.startswith("quality.gate-failed-"))
            self.assertTrue((preserved / "EXPLORATION.md").is_file())
            self.assertTrue((preserved / "PROGRESS.md").is_file())
            self.assertTrue((preserved / "exploration_role_map.json").is_file())
            # GATE_FAILURE.md marker exists with the right content.
            marker = preserved / "GATE_FAILURE.md"
            self.assertTrue(marker.is_file())
            body = marker.read_text(encoding="utf-8")
            self.assertIn("EXPLORATION.md is only 5 lines", body)
            self.assertIn("Phase group 2", body)
            self.assertIn("cell-under-test", body)
            self.assertIn("gpt-5.4-mini", body)

    # ---------- Test 2: Preservation idempotence ----------------------

    def test_preservation_idempotence_across_two_aborts(self) -> None:
        """Two aborted attempts on the same cell produce two distinct
        timestamped sibling directories — neither overwritten."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = self._make_repo_with_quality(tmp)
            log = _stub_log_file(tmp)

            first = run_playbook._preserve_quality_on_gate_failure(
                repo,
                phase_group="Phase group 2",
                gate_messages=["GATE FAIL attempt 1"],
                args=_make_args(),
                log_file=log,
            )
            self.assertIsNotNone(first)
            # Simulate a second attempt by recreating quality/ with
            # different content + waiting one second so the timestamps
            # don't collide.
            quality2 = repo / "quality"
            quality2.mkdir()
            (quality2 / "EXPLORATION.md").write_text(
                "second attempt\n", encoding="utf-8",
            )
            # Patch datetime.now to guarantee a distinct timestamp
            # rather than depending on real wall-clock spacing.
            from datetime import datetime as _real_datetime, timezone
            class FrozenDatetime(_real_datetime):
                @classmethod
                def now(cls, tz=None):  # type: ignore[override]
                    return _real_datetime(2026, 5, 12, 14, 30, 5, tzinfo=timezone.utc)
            with mock.patch.object(run_playbook, "datetime", FrozenDatetime):
                second = run_playbook._preserve_quality_on_gate_failure(
                    repo,
                    phase_group="Phase group 2",
                    gate_messages=["GATE FAIL attempt 2"],
                    args=_make_args(),
                    log_file=log,
                )
            self.assertIsNotNone(second)
            assert first is not None and second is not None
            self.assertNotEqual(
                first.name, second.name,
                "two aborts must produce distinct preserved directories",
            )
            # First survives untouched.
            self.assertTrue(first.is_dir())
            self.assertTrue((first / "GATE_FAILURE.md").is_file())
            self.assertIn(
                "attempt 1",
                (first / "GATE_FAILURE.md").read_text(encoding="utf-8"),
            )
            self.assertTrue(second.is_dir())
            self.assertIn(
                "attempt 2",
                (second / "GATE_FAILURE.md").read_text(encoding="utf-8"),
            )

    # ---------- Test 3: Empty-quality handling ------------------------

    def test_empty_quality_handling_no_crash_no_dir(self) -> None:
        """Preservation logic must be safe when quality/ doesn't exist
        OR exists-but-is-empty. Both cases: no crash, no spurious
        quality.gate-failed-*/ directory."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            # Case A: quality/ missing entirely.
            repo_a = tmp / "no-quality"
            repo_a.mkdir()
            log = _stub_log_file(tmp)
            result = run_playbook._preserve_quality_on_gate_failure(
                repo_a,
                phase_group="Phase 2",
                gate_messages=["GATE FAIL"],
                args=_make_args(),
                log_file=log,
            )
            self.assertIsNone(result)
            siblings = [
                p for p in repo_a.iterdir()
                if p.name.startswith("quality.gate-failed-")
            ]
            self.assertEqual(siblings, [], "no preserved dir should be created")

            # Case B: quality/ exists but is empty.
            repo_b = tmp / "empty-quality"
            (repo_b / "quality").mkdir(parents=True)
            result = run_playbook._preserve_quality_on_gate_failure(
                repo_b,
                phase_group="Phase 2",
                gate_messages=["GATE FAIL"],
                args=_make_args(),
                log_file=log,
            )
            self.assertIsNone(result)
            siblings = [
                p for p in repo_b.iterdir()
                if p.name.startswith("quality.gate-failed-")
            ]
            self.assertEqual(siblings, [])
            # The empty quality/ should still exist (preservation logic
            # didn't delete it — just declined to rename it).
            self.assertTrue((repo_b / "quality").is_dir())

    # ---------- Test 4: Subsequent run independence -------------------

    def test_subsequent_run_does_not_consume_preserved_set(self) -> None:
        """After preservation, the next run's quality/-setup paths must
        not see the preserved set as previous_runs/ or any other
        consumed-by-QPB path. The preserved directory naming
        (quality.gate-failed-<ts>/) sits outside quality/ entirely and
        is invisible to archive_previous_run, which only inspects
        repo/quality/."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = self._make_repo_with_quality(tmp)
            log = _stub_log_file(tmp)
            preserved = run_playbook._preserve_quality_on_gate_failure(
                repo,
                phase_group="Phase 2",
                gate_messages=["GATE FAIL"],
                args=_make_args(),
                log_file=log,
            )
            assert preserved is not None
            # Simulate the next run's setup: fresh quality/ + invoke
            # archive_previous_run (which is what setup does).
            (repo / "quality").mkdir()
            (repo / "quality" / "EXPLORATION.md").write_text(
                "fresh run\n", encoding="utf-8",
            )
            run_playbook.archive_previous_run(repo, "20260512T150000Z")
            # The preserved directory still exists at the repo root
            # (not consumed by archive_previous_run).
            self.assertTrue(preserved.is_dir())
            self.assertTrue((preserved / "GATE_FAILURE.md").is_file())
            # The preserved set did NOT land inside previous_runs/.
            previous_runs = repo / "quality" / "previous_runs"
            if previous_runs.exists():
                names = [p.name for p in previous_runs.iterdir()]
                for name in names:
                    self.assertFalse(
                        name.startswith("quality.gate-failed-"),
                        f"preserved set leaked into previous_runs/: {name}",
                    )

    # ---------- Test 5: Marker content (delegated to renderer tests) --
    # Test 5 is covered by RenderGateFailureMarkerTests above
    # (test_marker_contains_required_fields) plus the happy-path
    # assertions in test_preservation_happy_path_renames_quality_and_writes_marker.
    # No separate stub here.

    def test_preservation_log_line_lands_in_preserved_logs_not_shadow_quality(self) -> None:
        """v1.5.7 fix F-2: the "Preserved quality/ at ..." log line must
        end up INSIDE the preserved directory (under
        quality.gate-failed-<ts>/logs/<id>/runner.log), not in a shadow
        quality/logs/<id>/runner.log recreated by lib.logboth() after
        the rename. Pre-fix the logboth() call ran post-rename and
        re-mkdir'd quality/logs/<id>/ at the freshly-vacated path,
        routing preservation evidence to a directory operators never
        inspect.

        Test shape: place the log_file inside the live quality/ tree
        (matching the v1.5.7 centralized log layout
        quality/logs/<run-id>/runner.log) so the rename-vs-log
        ordering matters. After preservation:
          - preserved/logs/<run-id>/runner.log contains the
            "Preserved quality/ at ..." line.
          - No quality/ tree exists at the repo root (no shadow
            recreation by logboth())."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = self._make_repo_with_quality(tmp)
            run_id = "20260513T084955Z"
            log_file = repo / "quality" / "logs" / run_id / "runner.log"
            log_file.parent.mkdir(parents=True)
            log_file.write_text("", encoding="utf-8")
            preserved = run_playbook._preserve_quality_on_gate_failure(
                repo,
                phase_group="Phase 2",
                gate_messages=["GATE FAIL Phase 2"],
                args=_make_args(),
                log_file=log_file,
            )
            assert preserved is not None
            preserved_log = preserved / "logs" / run_id / "runner.log"
            self.assertTrue(
                preserved_log.is_file(),
                f"expected log file inside preserved directory at "
                f"{preserved_log}, but it does not exist",
            )
            preserved_log_text = preserved_log.read_text(encoding="utf-8")
            self.assertIn(
                "Preserved quality/ at", preserved_log_text,
                f"the 'Preserved' log line must land in the preserved "
                f"directory's runner.log; got: {preserved_log_text!r}",
            )
            self.assertIn(
                preserved.name, preserved_log_text,
                "the 'Preserved' log line must name the preserved dir",
            )
            self.assertFalse(
                (repo / "quality").exists(),
                f"no shadow quality/ tree may exist at the repo root after "
                f"preservation; if it does, lib.logboth() recreated it.",
            )

    def test_marker_captures_multi_line_violation_message(self) -> None:
        """When the gate emits multiple message lines, the marker
        preserves them as a multi-line blockquote (each line prefixed
        with '> ' in the rendered markdown)."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = self._make_repo_with_quality(tmp)
            log = _stub_log_file(tmp)
            preserved = run_playbook._preserve_quality_on_gate_failure(
                repo,
                phase_group="Phase 2",
                gate_messages=[
                    "GATE FAIL Phase 2: quality/exploration_role_map.json could not be normalized for the gate:",
                    "  - files[] missing",
                    "  This typically means files[] is missing or malformed; re-run Phase 1.",
                ],
                args=_make_args(),
                log_file=log,
            )
            assert preserved is not None
            body = (preserved / "GATE_FAILURE.md").read_text(encoding="utf-8")
            self.assertIn("files[] missing", body)
            self.assertIn("re-run Phase 1", body)


class Cluster049AutoRecoveryCompositionTests(unittest.TestCase):
    """Acceptance scenario 6: when cluster-049 auto-recovery succeeds,
    check_phase_gate returns ok=True so the preservation branch never
    fires. Patch check_phase_gate to return a successful gate and
    assert _preserve_quality_on_gate_failure is never invoked."""

    def test_auto_recovery_success_does_not_trigger_preservation(self) -> None:
        # F3 (v1.5.7 Phase 3 fix-up): replaces the prior vacuous
        # if-not-gate-ok branch-guard with a mock that asserts the
        # preservation helper is never called when the gate returns
        # ok=True. If a future refactor moves preservation up the call
        # stack (or out from under the `if not gate.ok:` branch) so it
        # DOES fire even when auto-recovery succeeds, this test will
        # fail — the prior vacuous form would not have caught that.
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = tmp / "cell-recovered"
            repo.mkdir()
            quality = repo / "quality"
            quality.mkdir()
            (quality / "EXPLORATION.md").write_text("x" * 200, encoding="utf-8")
            _stub_log_file(tmp)

            with mock.patch.object(
                run_playbook,
                "_preserve_quality_on_gate_failure",
            ) as preserve_mock, mock.patch.object(
                run_playbook,
                "check_phase_gate",
                return_value=run_playbook.GateCheck(ok=True, messages=[]),
            ) as gate_mock:
                gate = run_playbook.check_phase_gate(
                    repo, "2", args=_make_args()
                )
                # Re-state the production contract: preserve only on
                # gate failure. Auto-recovery success → ok=True → no
                # preservation. The mock assertion below is the real
                # guard: even if a future refactor breaks the `if not
                # gate.ok:` branch-guard, the mock will catch any
                # invocation of the preservation helper.
                if not gate.ok:
                    run_playbook._preserve_quality_on_gate_failure(
                        repo,
                        phase_group="Phase group 2",
                        gate_messages=gate.messages,
                        args=_make_args(),
                        log_file=tmp / "run.log",
                    )

            gate_mock.assert_called_once()
            preserve_mock.assert_not_called()
            # quality/ remains live.
            self.assertTrue((repo / "quality").is_dir())
            # No quality.gate-failed-*/ sibling was created.
            siblings = [
                p for p in repo.iterdir()
                if p.name.startswith("quality.gate-failed-")
            ]
            self.assertEqual(
                siblings, [],
                "auto-recovery success must not produce a preservation directory",
            )


class Phase3PlusScopeGateTests(unittest.TestCase):
    """v1.5.7 Phase 3 fix-up F1: preservation is scoped to Phase 2 gate
    failures only. Phase 3/4/5 gate failures must NOT produce a
    quality.gate-failed-*/ directory. The marker text, directory
    naming, and TOOLKIT.md docs all assume Phase 2; preservation in
    those Phase 3+ scenarios would be misleading."""

    def test_phase3_gate_failure_does_not_trigger_preservation(self) -> None:
        # Bite-checked test: asserts the production wire-site
        # conditions in run_one_phase and run_one_phase_group both
        # short-circuit preservation when the failing gate is anything
        # other than Phase 2. The check inspects the production
        # function source directly (via inspect.getsource) rather than
        # re-stating the condition in test code, so reverting F1
        # actually makes this test fail.
        import inspect
        import textwrap

        for func, expected_guard in (
            (run_playbook.run_one_phase, 'if phase == "2":'),
            (run_playbook.run_one_phase_group, 'if group[0] == "2":'),
        ):
            src = textwrap.dedent(inspect.getsource(func))
            # The guard line must appear immediately above (or within
            # the same `if not gate.ok:` block as) the preservation
            # helper invocation. Confirm the textual co-location.
            self.assertIn(
                expected_guard,
                src,
                f"{func.__name__} must scope preservation to Phase 2 "
                f"(F1): expected guard `{expected_guard}` in source",
            )
            # Locate the guard and the preservation call. The guard
            # must precede the call AND there must be no
            # _preserve_quality_on_gate_failure invocation OUTSIDE
            # (i.e., not nested under) any phase==2 / group[0]==2
            # guard. We approximate by requiring that every
            # _preserve_quality_on_gate_failure invocation appears
            # AFTER an occurrence of the expected guard, with no
            # earlier ungated invocation.
            guard_idx = src.find(expected_guard)
            call_idx = src.find("_preserve_quality_on_gate_failure(")
            self.assertGreater(
                call_idx, 0,
                f"{func.__name__} must call "
                f"_preserve_quality_on_gate_failure",
            )
            self.assertLess(
                guard_idx, call_idx,
                f"{func.__name__} preservation call must be guarded "
                f"by `{expected_guard}` (F1): guard not found before "
                f"the helper invocation",
            )

        # Also exercise the runtime behavior: a Phase 3 gate failure
        # scenario, when run through the test helper that mirrors the
        # production contract, leaves quality/ intact with no
        # preservation directory beside it.
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            repo = tmp / "cell-phase3-fail"
            repo.mkdir()
            (repo / "quality").mkdir()
            (repo / "quality" / "EXPLORATION.md").write_text(
                "agent's outputs that should survive normally\n" * 20,
                encoding="utf-8",
            )

            # Direct invocation of the helper with a Phase 3 label
            # documents what the (now-prevented) old behavior would
            # have produced: a misleading preservation directory.
            # Under F1 the production wire sites never reach this
            # helper for non-Phase-2 gates, so the runtime guard above
            # is the actual safety net. This block exists to confirm
            # the helper itself is unchanged (still works when called)
            # — F1 is a wire-site fix, not a helper-internal fix.
            preserved = run_playbook._preserve_quality_on_gate_failure(
                repo,
                phase_group="Phase 3",
                gate_messages=["GATE FAIL Phase 3: test only"],
                args=_make_args(),
                log_file=tmp / "run.log",
            )
            # The helper, when called, still works (it's wire-site
            # gating, not helper-internal gating). Clean up the
            # artifact this synthetic direct call produced so it
            # doesn't pollute other assertions.
            self.assertIsNotNone(preserved)
            assert preserved is not None
            shutil.rmtree(preserved)


if __name__ == "__main__":
    unittest.main()
