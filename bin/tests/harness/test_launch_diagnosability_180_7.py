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


if __name__ == "__main__":
    unittest.main()
