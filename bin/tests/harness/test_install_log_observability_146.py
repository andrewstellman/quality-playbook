"""v1.5.7 146 — install observability: tee npm/pip install output to
per-run install.log + surface the tail on ABORTED_PREP.

The 2026-05-29 chi codex Mode B run ABORTED_PREP at 120s with zero
visibility into what npm/npx was actually doing. 146 tees the
install stdout/stderr (already captured via capture_output) to
``<run-NN>/install.log`` for ALL channels, and on a timeout/failure
carries the last-N lines on the PrepError so the caller surfaces
them inline in the ABORTED_PREP log line + grading.json — no
halt-and-diagnose cycle.

`install_log_path=None` (default) preserves pre-146 behavior. These
mock `subprocess.run` / `build_install_command` so no real install
runs; the plan_runner formatting helpers are tested directly.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bin.harness import prepare as P
from bin.harness import plan_runner as PR
from bin.harness.schema import InstallChannel


def _patched(*, run_side_effect=None, run_return=None):
    """Patch build_install_command (→ a no-op argv) + subprocess.run."""
    cmd_patch = mock.patch.object(
        P, "build_install_command", return_value=["true"])
    run_kw = {}
    if run_side_effect is not None:
        run_kw["side_effect"] = run_side_effect
    else:
        run_kw["return_value"] = run_return
    run_patch = mock.patch.object(P.subprocess, "run", **run_kw)
    return cmd_patch, run_patch


def _ok(stdout="", stderr=""):
    return subprocess.CompletedProcess(["true"], 0, stdout=stdout,
                                       stderr=stderr)


class InstallLogTeeTests(unittest.TestCase):

    def test_install_log_path_none_preserves_pre146_behavior(
            self) -> None:
        # No install_log_path → nothing written, no crash.
        c, r = _patched(run_return=_ok(stdout="x"))
        with c, r:
            P.install_skill_channel(
                InstallChannel.NPM_LOCAL_TGZ, Path("/tmp/t"),
                local_artifact=Path("x.tgz"))
        # (no assertion target — the point is it doesn't error/write)

    def test_install_log_captures_stdout_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            logp = Path(td) / "install.log"
            c, r = _patched(run_return=_ok(stdout="line A\nline B"))
            with c, r:
                P.install_skill_channel(
                    InstallChannel.NPM_LOCAL_TGZ, Path("/tmp/t"),
                    local_artifact=Path("x.tgz"),
                    install_log_path=logp)
            content = logp.read_text(encoding="utf-8")
            self.assertIn("line A", content)
            self.assertIn("line B", content)

    def test_install_log_captures_stderr_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            logp = Path(td) / "install.log"
            c, r = _patched(
                run_return=_ok(stdout="out", stderr="a warning"))
            with c, r:
                P.install_skill_channel(
                    InstallChannel.NPM_LOCAL_TGZ, Path("/tmp/t"),
                    local_artifact=Path("x.tgz"),
                    install_log_path=logp)
            content = logp.read_text(encoding="utf-8")
            self.assertIn("out", content)
            self.assertIn("a warning", content)  # not lossy

    def test_install_log_written_on_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            logp = Path(td) / "install.log"
            exc = subprocess.TimeoutExpired(
                cmd="true", timeout=120.0,
                output="fetching\nstill fetching\nhang", stderr="")
            c, r = _patched(run_side_effect=exc)
            with c, r:
                with self.assertRaises(P.PrepError) as ctx:
                    P.install_skill_channel(
                        InstallChannel.NPM_LOCAL_TGZ, Path("/tmp/t"),
                        local_artifact=Path("x.tgz"), timeout_s=120.0,
                        install_log_path=logp)
            self.assertIn("hang", logp.read_text(encoding="utf-8"))
            self.assertIn("hang", ctx.exception.install_log_tail)
            self.assertEqual(ctx.exception.install_log_path, str(logp))

    def test_aborted_prep_error_includes_tail_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            logp = Path(td) / "install.log"
            exc = subprocess.CalledProcessError(
                1, "true", output="step1\nstep2\nFATAL: boom",
                stderr="")
            c, r = _patched(run_side_effect=exc)
            with c, r:
                with self.assertRaises(P.PrepError) as ctx:
                    P.install_skill_channel(
                        InstallChannel.NPM_LOCAL_TGZ, Path("/tmp/t"),
                        local_artifact=Path("x.tgz"),
                        install_log_path=logp)
            self.assertIn("FATAL: boom",
                          ctx.exception.install_log_tail)

    def test_install_log_works_for_pip_channel(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            logp = Path(td) / "install.log"
            c, r = _patched(run_return=_ok(stdout="pip resolving"))
            with c, r:
                P.install_skill_channel(
                    InstallChannel.PIP_LOCAL_WHEEL, Path("/tmp/t"),
                    local_artifact=Path("x.whl"),
                    install_log_path=logp)
            self.assertIn("pip resolving",
                          logp.read_text(encoding="utf-8"))


class AbortedPrepFormattingTests(unittest.TestCase):
    """The plan_runner helpers that surface the tail in the
    ABORTED_PREP log line + grading.json."""

    def _exc(self, *, tail=None, path=None):
        return P.PrepError(
            "install_skill (npm-local-tgz) timed out after 120.0s",
            install_log_path=path, install_log_tail=tail)

    def test_log_msg_includes_inline_tail_and_path(self) -> None:
        exc = self._exc(
            tail=["a", "b", "c", "d", "e", "f"],
            path="/runs/run-02/install.log")
        msg = PR._aborted_prep_log_msg(exc)
        self.assertIn("ABORTED_PREP:", msg)
        self.assertIn("Last 5 lines of install.log:", msg)
        self.assertIn("    f", msg)            # last line indented
        self.assertNotIn("    a", msg)         # only last 5 → 'a' dropped
        self.assertIn("/runs/run-02/install.log", msg)

    def test_log_msg_without_tail_is_plain(self) -> None:
        exc = P.PrepError("leakage-gate ABORTED: ...")  # no install log
        msg = PR._aborted_prep_log_msg(exc)
        self.assertEqual(msg, "ABORTED_PREP: leakage-gate ABORTED: ...")
        self.assertNotIn("install.log", msg)

    def test_prep_error_fields_includes_log_when_present(self) -> None:
        exc = self._exc(tail=["x", "y"], path="/p/install.log")
        fields = PR._prep_error_fields(exc)
        self.assertEqual(fields["prep_error"], exc.reason)
        self.assertEqual(fields["install_log_path"], "/p/install.log")
        self.assertEqual(fields["install_log_tail"], ["x", "y"])

    def test_prep_error_fields_plain_when_no_log(self) -> None:
        exc = P.PrepError("some non-install prep failure")
        fields = PR._prep_error_fields(exc)
        self.assertEqual(fields, {"prep_error": exc.reason})
        self.assertNotIn("install_log_path", fields)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
