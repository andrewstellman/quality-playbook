"""v1.5.7 180-followup-7: launch-failure diagnosability tests.

Andrew's 5th Windows fire on 20260601T182846Z surfaced FINDING-9
(``signal.SIGKILL``) via a one-line clue in manifest.json
(``AttributeError`` happened to embed the missing attribute name).
We got lucky — generic exceptions like ``RuntimeError`` or
``OSError`` would have left the operator hunting blind.

FINDING-11: capture the full traceback to ``run-NN/launch_error.txt``
and embed a compact ``exc + last frame file:line:qualname`` summary
in the manifest's terminal_reason.

FINDING-12: per-run ``run-NN/launch.log`` JSON-lines breadcrumbs
one line per step in the launch chain so a hang OR a crash both
surface "last step in flight".

FINDING-13: harness-run ``harness_env.json`` written immediately
after the harness-run dir is created — python version, platform,
filtered env, source-file hashes. Cross-platform bug paper trail.
"""
from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[3]


class FormatLaunchFailureSummaryTests(unittest.TestCase):
    """v1.5.7 180-followup-7 FINDING-11: the compact-summary
    helper extracts ``<exc-repr> at <file>:<line> in <qualname>``
    from the exception's traceback."""

    def test_helper_exists(self) -> None:
        from bin.harness import plan_runner
        self.assertTrue(hasattr(
            plan_runner, "_format_launch_failure_summary"))

    def test_summary_includes_last_frame_location(self) -> None:
        from bin.harness import plan_runner
        try:
            # Synthesize a real exception with a real traceback
            # so the helper has a frame to extract.
            def _inner() -> None:
                raise RuntimeError("synthetic")
            _inner()
        except RuntimeError as exc:
            import traceback as _tb
            summary = (
                plan_runner._format_launch_failure_summary(
                    exc, _tb.format_exc()))
        self.assertIn("RuntimeError", summary)
        self.assertIn("synthetic", summary)
        # Last frame is _inner() inside this test file.
        self.assertIn("test_launch_diagnosability_180_7", summary)
        self.assertIn(" in _inner", summary)

    def test_summary_falls_back_to_repr_when_no_traceback(
            self) -> None:
        from bin.harness import plan_runner
        exc = ValueError("no tb attached")
        summary = plan_runner._format_launch_failure_summary(
            exc, "")
        # No __traceback__ → just repr.
        self.assertIn("ValueError", summary)
        self.assertIn("no tb attached", summary)

    def test_summary_qualname_module_for_module_load_failures(
            self) -> None:
        # Simulating a module-load-time AttributeError (the
        # FINDING-9 shape). The qualname should surface as
        # ``<module>`` so the operator immediately knows this is
        # an import-time failure.
        from bin.harness import plan_runner
        import types
        # Build a synthetic module that raises at import time.
        with tempfile.TemporaryDirectory() as td:
            modfile = pathlib.Path(td) / "boom.py"
            modfile.write_text(
                "raise AttributeError('synthetic import failure')\n",
                encoding="utf-8")
            import sys, importlib.util
            spec = importlib.util.spec_from_file_location(
                "boom_180_7", modfile)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
            except AttributeError as exc:
                import traceback as _tb
                summary = (
                    plan_runner
                    ._format_launch_failure_summary(
                        exc, _tb.format_exc()))
        self.assertIn("<module>", summary)
        self.assertIn("synthetic import failure", summary)


class LaunchErrorTracebackPersistenceTests(unittest.TestCase):
    """v1.5.7 180-followup-7 FINDING-11: when the launch catch
    runs, the run-dir gets a ``launch_error.txt`` file with the
    full traceback AND the manifest entry's terminal_reason gets
    the compact summary."""

    def test_launch_catch_site_uses_format_launch_failure_summary(
            self) -> None:
        # Source-pin: the catch site at the
        # _finalize_pool_slot_failed call in plan_runner.py must
        # build the reason via _format_launch_failure_summary.
        src = (_REPO / "bin" / "harness" / "plan_runner.py").read_text(
            encoding="utf-8")
        # The compact-summary call must appear AT LEAST TWICE
        # (def + ≥1 call). Mutation-bite: removing the call drops
        # to 1.
        occ = src.count("_format_launch_failure_summary(")
        self.assertGreaterEqual(
            occ, 2,
            f"plan_runner.py must CALL "
            f"_format_launch_failure_summary at the launch "
            f"catch site (FINDING-11). Found {occ}; need ≥2.")

    def test_launch_catch_site_writes_launch_error_txt(
            self) -> None:
        # Source-pin: the catch site writes "launch_error.txt".
        src = (_REPO / "bin" / "harness" / "plan_runner.py").read_text(
            encoding="utf-8")
        self.assertIn(
            'launch_error.txt', src,
            "plan_runner.py launch catch must write "
            "run-NN/launch_error.txt (FINDING-11). The full "
            "traceback file is the forensic record; the "
            "manifest terminal_reason is just the summary.")

    def test_traceback_module_imported(self) -> None:
        # Source-pin: traceback module must be imported in
        # plan_runner.py for the helper / catch site.
        src = (_REPO / "bin" / "harness" / "plan_runner.py").read_text(
            encoding="utf-8")
        self.assertIn(
            "import traceback", src,
            "plan_runner.py must import the traceback module "
            "for FINDING-11's diagnosability work.")


class StepLogBreadcrumbsTests(unittest.TestCase):
    """v1.5.7 180-followup-7 FINDING-12: per-run launch-step
    breadcrumb log. JSON lines, one per step, appended to
    ``run-NN/launch.log``."""

    def test_step_log_class_exists(self) -> None:
        from bin.harness import plan_runner
        self.assertTrue(hasattr(plan_runner, "_StepLog"))

    def test_step_log_writes_json_lines(self) -> None:
        from bin.harness import plan_runner
        with tempfile.TemporaryDirectory() as td:
            log_path = pathlib.Path(td) / "launch.log"
            slog = plan_runner._StepLog(log_path)
            slog("starting launch", run_index=0)
            slog("spawning child", pid=999)
            self.assertTrue(log_path.is_file())
            lines = [
                json.loads(ln)
                for ln in log_path.read_text().splitlines()
                if ln.strip()
            ]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["step"], "starting launch")
            self.assertEqual(lines[0]["run_index"], 0)
            self.assertEqual(lines[1]["step"], "spawning child")
            self.assertEqual(lines[1]["pid"], 999)
            # Each line carries monotonic + absolute timestamps.
            self.assertIn("t_relative", lines[0])
            self.assertIn("t_absolute", lines[0])
            self.assertGreaterEqual(
                lines[1]["t_relative"], lines[0]["t_relative"])

    def test_step_log_swallows_oserror(self) -> None:
        # An unwritable target must NOT raise — breadcrumbs are
        # diagnostic, not correctness-critical.
        from bin.harness import plan_runner
        bogus = pathlib.Path("/nonexistent/qpb-180-7/launch.log")
        # Don't even rely on the __init__ touch behavior; the
        # call should also tolerate the unwritable path.
        slog = plan_runner._StepLog(bogus)
        slog("starting launch")  # no raise

    def test_read_last_launch_step_returns_most_recent(
            self) -> None:
        from bin.harness import plan_runner
        with tempfile.TemporaryDirectory() as td:
            log_path = pathlib.Path(td) / "launch.log"
            slog = plan_runner._StepLog(log_path)
            slog("starting launch")
            slog("cloning + installing")
            slog("spawning child")
            last = plan_runner._read_last_launch_step(log_path)
            self.assertEqual(last, "spawning child")

    def test_read_last_launch_step_returns_none_on_missing(
            self) -> None:
        from bin.harness import plan_runner
        self.assertIsNone(
            plan_runner._read_last_launch_step(
                pathlib.Path("/nonexistent/qpb-180-7")))

    def test_read_last_launch_step_returns_none_on_garbage(
            self) -> None:
        from bin.harness import plan_runner
        with tempfile.TemporaryDirectory() as td:
            log_path = pathlib.Path(td) / "launch.log"
            log_path.write_text(
                "not json\nstill not json\n", encoding="utf-8")
            self.assertIsNone(
                plan_runner._read_last_launch_step(log_path))

    def test_launch_chain_calls_step_log(self) -> None:
        # Source-pin: _launch_one_run_detached must call
        # step_log("starting launch" ...) at the entry of the
        # function. Also pin that the breadcrumb appears at the
        # spawn step ("spawning detached child process") and the
        # complete step ("launch complete").
        src = (_REPO / "bin" / "harness" / "plan_runner.py").read_text(
            encoding="utf-8")
        self.assertIn('step_log("launch starting"', src)
        self.assertIn('step_log("spawning detached child process"', src)
        self.assertIn('step_log("launch complete"', src)

    def test_launch_catch_site_appends_failed_breadcrumb(
            self) -> None:
        # Source-pin: the catch site appends "launch FAILED" so
        # the breadcrumb tail surfaces the crash even when the
        # exception bypassed the in-function step_log path.
        src = (_REPO / "bin" / "harness" / "plan_runner.py").read_text(
            encoding="utf-8")
        self.assertIn('"launch FAILED"', src)

    def test_launch_catch_site_embeds_last_step_in_summary(
            self) -> None:
        # Source-pin: terminal_reason in the catch site includes
        # the "[last step: <X>]" suffix from _read_last_launch_step.
        src = (_REPO / "bin" / "harness" / "plan_runner.py").read_text(
            encoding="utf-8")
        self.assertIn("_read_last_launch_step(", src)
        self.assertIn("last step:", src)


class HarnessEnvSnapshotTests(unittest.TestCase):
    """v1.5.7 180-followup-7 FINDING-13: harness-run env
    snapshot written immediately after the harness-run dir is
    created. Cross-platform / cross-version bug paper trail."""

    def test_sha256_first_4k_returns_hex_digest(self) -> None:
        from bin.harness import plan_runner
        with tempfile.NamedTemporaryFile(
                "wb", delete=False, suffix=".tmp") as f:
            f.write(b"hello world" * 100)
            path = pathlib.Path(f.name)
        try:
            h = plan_runner._sha256_first_4k(path)
            self.assertIsNotNone(h)
            self.assertEqual(len(h), 64)  # hex sha256
            int(h, 16)  # parses as hex
        finally:
            path.unlink()

    def test_sha256_first_4k_returns_none_on_missing(
            self) -> None:
        from bin.harness import plan_runner
        self.assertIsNone(
            plan_runner._sha256_first_4k(
                pathlib.Path("/nonexistent/qpb-180-7-hash")))

    def test_write_harness_env_snapshot_creates_file(
            self) -> None:
        from bin.harness import plan_runner
        with tempfile.TemporaryDirectory() as td:
            hrd = pathlib.Path(td)
            plan_runner._write_harness_env_snapshot(hrd)
            snap_path = hrd / "harness_env.json"
            self.assertTrue(snap_path.is_file())
            snap = json.loads(snap_path.read_text())
            for key in (
                    "python_version", "python_executable",
                    "platform", "system", "machine",
                    "release", "cwd", "argv",
                    "env_filtered", "module_hashes"):
                self.assertIn(
                    key, snap,
                    f"harness_env.json must include {key!r} "
                    f"(FINDING-13)")
            # module_hashes must include at least the core
            # platform / harness modules.
            self.assertIn("bin/qpb_harness.py",
                          snap["module_hashes"])
            self.assertIn("bin/harness/_platform.py",
                          snap["module_hashes"])

    def test_env_snapshot_excludes_unallowed_env_vars(
            self) -> None:
        # Sanity: secrets / tokens MUST NOT leak into the
        # snapshot. The helper filters by an allow-list; this
        # test confirms a representative non-allowed env var
        # doesn't appear.
        from bin.harness import plan_runner
        import os as _os
        sentinel_key = "QPB_180_7_TEST_SENTINEL_TOKEN"
        sentinel_val = "should-not-appear-in-snapshot"
        _os.environ[sentinel_key] = sentinel_val
        try:
            with tempfile.TemporaryDirectory() as td:
                hrd = pathlib.Path(td)
                plan_runner._write_harness_env_snapshot(hrd)
                snap = json.loads(
                    (hrd / "harness_env.json").read_text())
                self.assertNotIn(
                    sentinel_key, snap["env_filtered"],
                    "env_filtered must use an allow-list to "
                    "prevent secret leakage")
                # Belt + suspenders: the value mustn't appear
                # anywhere serialized.
                serialized = json.dumps(snap)
                self.assertNotIn(sentinel_val, serialized)
        finally:
            _os.environ.pop(sentinel_key, None)

    def test_write_harness_env_snapshot_swallows_oserror(
            self) -> None:
        from bin.harness import plan_runner
        # Best-effort: unwritable target must NOT raise.
        plan_runner._write_harness_env_snapshot(
            pathlib.Path("/nonexistent/qpb-180-7"))

    def test_plan_runner_calls_env_snapshot_at_dir_creation(
            self) -> None:
        # Source-pin: _run_plan_detached calls
        # _write_harness_env_snapshot right after the
        # harness_run_dir.mkdir line. Occurrence-count check:
        # def + call ⇒ ≥2.
        src = (_REPO / "bin" / "harness" / "plan_runner.py").read_text(
            encoding="utf-8")
        occ = src.count("_write_harness_env_snapshot(")
        self.assertGreaterEqual(
            occ, 2,
            f"plan_runner.py must CALL "
            f"_write_harness_env_snapshot at harness-run dir "
            f"creation (FINDING-13). Found {occ}; need ≥2.")


class StepLogReattachTests(unittest.TestCase):
    """v1.5.7 180-followup-8 FINDING-14: catch-site reattach
    preserves the launch.log timeline instead of resetting
    t_relative=0 on the 'launch FAILED' breadcrumb."""

    def test_reattach_anchors_t0_to_first_entry_t_absolute(
            self) -> None:
        from bin.harness import plan_runner
        from datetime import datetime, timezone, timedelta
        with tempfile.TemporaryDirectory() as td:
            log_path = pathlib.Path(td) / "launch.log"
            # Seed the log with a "launch starting" entry 5s ago.
            then = (datetime.now(timezone.utc)
                    - timedelta(seconds=5.0))
            iso = then.isoformat(
                timespec="milliseconds").replace("+00:00", "Z")
            log_path.write_text(json.dumps({
                "t_relative": 0.0,
                "t_absolute": iso,
                "step": "launch starting",
            }) + "\n", encoding="utf-8")
            # Reattach + emit.
            slog = plan_runner._StepLog.reattach(log_path)
            slog("synthetic next step")
            entries = [
                json.loads(ln)
                for ln in log_path.read_text().splitlines()
                if ln.strip()
            ]
            self.assertEqual(len(entries), 2)
            # The second entry's t_relative should be ~5.0
            # (within a generous ±1s tolerance for clock skew /
            # test scheduling latency).
            self.assertAlmostEqual(
                entries[1]["t_relative"], 5.0, delta=1.0)

    def test_reattach_on_missing_log_returns_fresh_steplog(
            self) -> None:
        from bin.harness import plan_runner
        with tempfile.TemporaryDirectory() as td:
            log_path = pathlib.Path(td) / "no_such.log"
            slog = plan_runner._StepLog.reattach(log_path)
            self.assertIsInstance(slog, plan_runner._StepLog)
            # No anchor → _t0 is approximately current monotonic.
            import time as _t
            self.assertAlmostEqual(
                slog._t0, _t.monotonic(), delta=1.0)

    def test_reattach_on_garbage_first_line_returns_fresh_steplog(
            self) -> None:
        from bin.harness import plan_runner
        import time as _t
        with tempfile.TemporaryDirectory() as td:
            log_path = pathlib.Path(td) / "launch.log"
            log_path.write_text(
                "not json at all\n", encoding="utf-8")
            slog = plan_runner._StepLog.reattach(log_path)
            # No usable anchor → fresh _t0.
            self.assertAlmostEqual(
                slog._t0, _t.monotonic(), delta=1.0)

    def test_reattach_on_empty_log_returns_fresh_steplog(
            self) -> None:
        from bin.harness import plan_runner
        import time as _t
        with tempfile.TemporaryDirectory() as td:
            log_path = pathlib.Path(td) / "launch.log"
            log_path.write_text("", encoding="utf-8")
            slog = plan_runner._StepLog.reattach(log_path)
            self.assertAlmostEqual(
                slog._t0, _t.monotonic(), delta=1.0)

    def test_catch_site_uses_reattach(self) -> None:
        # Source-pin: plan_runner.py contains
        # "_StepLog.reattach(" within ~400 chars of the LAST
        # "launch FAILED" string (the actual catch site, NOT
        # the docstring mention on the reattach method).
        src = (_REPO / "bin" / "harness" / "plan_runner.py").read_text(
            encoding="utf-8")
        idx = src.rfind('"launch FAILED"')
        self.assertGreater(idx, 0)
        window = src[max(0, idx - 400):idx + 400]
        self.assertIn(
            "_StepLog.reattach(", window,
            "catch site must use _StepLog.reattach to preserve "
            "the launch.log timeline (FINDING-14).")


class StepLogSwallowsAllExceptionsTests(unittest.TestCase):
    """v1.5.7 180-followup-8 FINDING-15: breadcrumbs must never
    abort the launch chain. The __call__ swallow is broadened
    from OSError to Exception so a pathological kwarg's
    __str__/__repr__ raise can't bubble up."""

    def test_call_with_non_serializable_kwarg_does_not_raise(
            self) -> None:
        from bin.harness import plan_runner
        # An object whose __str__ raises. json.dumps with
        # default=str will call str() which raises → __call__
        # must swallow it.
        class _Pathological:
            def __str__(self) -> str:
                raise TypeError("synthetic __str__ failure")
            __repr__ = __str__
        with tempfile.TemporaryDirectory() as td:
            log_path = pathlib.Path(td) / "launch.log"
            slog = plan_runner._StepLog(log_path)
            # No raise (would propagate up to the launch chain
            # and cause spurious "launch failed" diagnoses).
            slog("synthetic", bad=_Pathological())

    def test_source_pin_swallow_is_exception_not_oserror(
            self) -> None:
        # Source-pin: _StepLog.__call__'s except clause matches
        # ``except Exception`` (not ``except OSError``). Search
        # within the class body for the pattern.
        src = (_REPO / "bin" / "harness" / "plan_runner.py").read_text(
            encoding="utf-8")
        # Find the _StepLog class block and look for "def
        # __call__" inside it, then check the except clause.
        class_idx = src.find("class _StepLog:")
        self.assertGreater(class_idx, 0)
        # Class body ends at the next top-level def/class.
        rest = src[class_idx:]
        import re
        m = re.search(r"\n(def |class )", rest[1:])
        body_end = m.start() + 1 if m else len(rest)
        body = rest[:body_end]
        call_idx = body.find("def __call__")
        self.assertGreater(call_idx, 0)
        call_body = body[call_idx:]
        self.assertIn(
            "except Exception", call_body,
            "_StepLog.__call__ must `except Exception` (not "
            "`except OSError`) — breadcrumbs are diagnostic, "
            "any swallow narrower than Exception leaves a "
            "load-bearing failure path (FINDING-15).")


class BreadcrumbCoverageSourceSweepTests(unittest.TestCase):
    """v1.5.7 180-followup-8 FINDING-16: every launch-shaped
    function in bin/harness/plan_runner.py must emit at least
    3 step_log breadcrumb calls (start / mid / end) so a hang
    or crash inside ANY launch path surfaces its 'where am I'
    signal. Without this sweep, a future PR could add a new
    launch path with no breadcrumbs and silently regress
    diagnosability."""

    def test_180_followup_8_all_launch_shaped_functions_emit_step_log_breadcrumbs(
            self) -> None:
        import re
        src = (_REPO / "bin" / "harness" / "plan_runner.py").read_text(
            encoding="utf-8")
        # Launch-shaped pattern: ``_launch_*_detached`` /
        # ``_launch_one_*``. Tightened to module-scope defs
        # only (^ at MULTILINE) so nested defs don't get
        # double-counted.
        func_pattern = re.compile(
            r"^def (_launch_(?:[a-z0-9_]+_detached"
            r"|one_[a-z0-9_]+))\(",
            re.MULTILINE)
        breadcrumb_pattern = re.compile(r"\bstep_log\(")
        matches = list(func_pattern.finditer(src))
        self.assertGreater(
            len(matches), 0,
            "no launch-shaped functions detected — pattern may "
            "be stale. If launch entry points were renamed, "
            "update the regex here AND "
            "[[methodology_lesson_22]].")
        for m in matches:
            func_name = m.group(1)
            start = m.end()
            # Extract function body by scanning to the next
            # top-level def/class (or EOF).
            next_top_level = re.search(
                r"\n(?:def |class )", src[start:])
            body_end = (start + next_top_level.start()
                        if next_top_level else len(src))
            body = src[start:body_end]
            count = len(breadcrumb_pattern.findall(body))
            self.assertGreaterEqual(
                count, 3,
                f"{func_name} emits {count} step_log() "
                f"breadcrumbs (need ≥3 to cover start, mid, "
                f"end). Without breadcrumbs a hang or crash "
                f"inside this launch path loses its 'where "
                f"am I' signal — see "
                f"[[methodology_lesson_22]].")


if __name__ == "__main__":
    unittest.main()
