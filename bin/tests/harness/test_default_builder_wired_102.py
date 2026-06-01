"""v1.5.7 102 — default artifact builders are LIVE, not stubs.

101 left ``_default_build_wheel`` / ``_default_build_tgz`` as
``raise NotImplementedError`` stubs and only exercised the
``BuilderHooks`` injection seam. 102 wired the live build (shell
out to ``build_channel_package.py --stage`` + ``python -m build
--wheel --outdir`` for the wheel; ``npm pack
--pack-destination`` for the tgz).

These tests exercise the **default code path** (NO ``BuilderHooks``
injection) with ``subprocess.run`` patched, so the real build
commands never run in unit tests but the default-builder argv /
cwd / file-discovery logic is verified end-to-end.

Coverage:
  * ``_default_build_wheel`` invokes ``build_channel_package.py
    --stage`` then ``python -m build --wheel --outdir
    <artifacts_dir>`` in the right order, with cwd at the QPB
    clone root, and returns the produced .whl.
  * ``_default_build_tgz`` invokes ``npm pack --pack-destination
    <artifacts_dir>`` with cwd at the clone root and returns
    the produced .tgz.
  * A failing subprocess (non-zero exit) propagates through
    ``build_artifacts`` ⇒ ``BuildError`` carrying the captured
    stderr; ``run_plan`` then aborts without launching any runs.
  * Output discovery: if the build command runs successfully
    but produces 0 or >1 ``.whl``/``.tgz`` in the artifacts dir,
    the default builder raises with an explicit count message.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness import schema as S


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_plan(channels: "list[str]") -> PR.Plan:
    runs = []
    for i, ch in enumerate(channels):
        runs.append({
            "description": f"run-{i}",
            "repo": "https://github.com/google/gson",
            "ref": "main",
            "runner": "claude",
            "model": "opus",
            "channel": ch,
            "expect": {},
        })
    return PR.parse_plan({"pools": {"claude": 1}, "runs": runs})


class _FakeSubprocess:
    """Stand-in for ``subprocess.run`` that records every call,
    creates the expected output files in the artifacts_dir, and
    returns a successful CompletedProcess. Tests inspect
    ``calls`` to verify argv + cwd were correct."""

    def __init__(self, *, drop_wheel: bool = True,
                 drop_tgz: bool = True,
                 wheel_filename: str = "quality_playbook-1.5.7-py3-none-any.whl",
                 tgz_filename: str = "quality-playbook-1.5.7.tgz",
                 ) -> None:
        self.calls: list[dict] = []
        self.drop_wheel = drop_wheel
        self.drop_tgz = drop_tgz
        self.wheel_filename = wheel_filename
        self.tgz_filename = tgz_filename

    def __call__(self, cmd, **kwargs):
        self.calls.append({"cmd": list(cmd), **kwargs})
        # If the call is `python -m build --wheel --outdir <D>`,
        # drop a fake wheel into <D>.
        if "build" in cmd and "--wheel" in cmd and self.drop_wheel:
            outdir = cmd[cmd.index("--outdir") + 1]
            (Path(outdir) / self.wheel_filename).write_bytes(
                b"FAKE WHEEL"
            )
        # If the call is `npm pack --pack-destination <D>`, drop
        # a fake tgz into <D>.
        if "npm" in cmd[0] and "pack" in cmd and self.drop_tgz:
            outdir = cmd[cmd.index("--pack-destination") + 1]
            (Path(outdir) / self.tgz_filename).write_bytes(
                b"FAKE TGZ"
            )
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr="",
        )


# ---------------------------------------------------------------------------
# Task A — default builders shell out to the right commands
# ---------------------------------------------------------------------------


class DefaultWheelBuilderWiredTests(unittest.TestCase):

    def test_default_wheel_runs_stage_then_python_m_build(
            self) -> None:
        """v1.5.7 102: ``_default_build_wheel`` shells out to
        ``bin/build_channel_package.py --stage`` THEN
        ``python -m build --wheel --outdir <artifacts_dir>`` in
        that order, with cwd at the QPB clone root."""
        fake = _FakeSubprocess()
        with tempfile.TemporaryDirectory() as tmp:
            artifacts_dir = Path(tmp)
            with mock.patch("bin.harness.plan_runner.subprocess.run",
                             side_effect=fake):
                whl = PR._default_build_wheel(artifacts_dir)
            # Exactly two subprocess calls.
            self.assertEqual(len(fake.calls), 2)
            stage_call = fake.calls[0]["cmd"]
            build_call = fake.calls[1]["cmd"]
            # Stage call.
            self.assertEqual(stage_call[1],
                              "bin/build_channel_package.py")
            self.assertIn("--stage", stage_call)
            # Build call.
            self.assertIn("-m", build_call)
            self.assertIn("build", build_call)
            self.assertIn("--wheel", build_call)
            self.assertEqual(
                build_call[build_call.index("--outdir") + 1],
                str(artifacts_dir),
            )
            # Both ran with cwd at the clone root (where
            # `bin/build_channel_package.py` lives + where
            # `pyproject.toml` is).
            clone_root = Path(fake.calls[0]["cwd"])
            self.assertTrue(
                (clone_root / "pyproject.toml").is_file(),
                f"cwd must be the QPB clone root, got "
                f"{clone_root}",
            )
            self.assertEqual(
                fake.calls[0]["cwd"], fake.calls[1]["cwd"],
            )
            # Returned the produced wheel.
            self.assertEqual(whl.parent, artifacts_dir)
            self.assertTrue(whl.is_file())

    def test_default_wheel_raises_on_zero_or_multiple_outputs(
            self) -> None:
        """If python -m build runs OK but yields 0 or >1 .whl
        files in artifacts_dir, the default builder raises with
        the count so the abort message is actionable."""
        # Subprocess succeeds but drops NO wheel.
        fake = _FakeSubprocess(drop_wheel=False)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("bin.harness.plan_runner.subprocess.run",
                             side_effect=fake):
                with self.assertRaises(RuntimeError) as ctx:
                    PR._default_build_wheel(Path(tmp))
            self.assertIn("expected exactly one .whl",
                            str(ctx.exception))


class DefaultTgzBuilderWiredTests(unittest.TestCase):

    def test_default_tgz_runs_npm_pack_pack_destination(self) -> None:
        """v1.5.7 102: ``_default_build_tgz`` shells out to
        ``npm pack --pack-destination <artifacts_dir>`` with cwd
        at the QPB clone root, and returns the produced .tgz."""
        fake = _FakeSubprocess()
        with tempfile.TemporaryDirectory() as tmp:
            artifacts_dir = Path(tmp)
            with mock.patch("bin.harness.plan_runner.subprocess.run",
                             side_effect=fake):
                tgz = PR._default_build_tgz(artifacts_dir)
            self.assertEqual(len(fake.calls), 1)
            pack_call = fake.calls[0]["cmd"]
            # v1.5.7 180-followup-4 FINDING-5: pack_call[0] is now
            # the resolved npm path (full executable path with
            # extension on Windows; .../npm on POSIX).
            import os as _os
            self.assertEqual(
                _os.path.basename(pack_call[0]).split(".")[0],
                "npm")
            self.assertEqual(pack_call[1], "pack")
            self.assertEqual(
                pack_call[pack_call.index("--pack-destination") + 1],
                str(artifacts_dir),
            )
            # cwd at clone root (top-level package.json present).
            clone_root = Path(fake.calls[0]["cwd"])
            self.assertTrue(
                (clone_root / "package.json").is_file(),
                f"cwd must be the QPB clone root, got "
                f"{clone_root}",
            )
            self.assertEqual(tgz.parent, artifacts_dir)
            self.assertTrue(tgz.is_file())

    def test_default_tgz_raises_on_zero_or_multiple_outputs(
            self) -> None:
        """npm pack succeeded but no .tgz dropped ⇒ explicit
        count error."""
        fake = _FakeSubprocess(drop_tgz=False)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("bin.harness.plan_runner.subprocess.run",
                             side_effect=fake):
                with self.assertRaises(RuntimeError) as ctx:
                    PR._default_build_tgz(Path(tmp))
            self.assertIn("expected exactly one .tgz",
                            str(ctx.exception))


# ---------------------------------------------------------------------------
# Task B — failure path: non-zero exit propagates through BuildError
# ---------------------------------------------------------------------------


class DefaultBuilderFailureAbortsRunPlanTests(unittest.TestCase):

    def test_default_wheel_failure_raises_build_error_with_stderr(
            self) -> None:
        """A non-zero ``subprocess.run`` from the DEFAULT (not a
        mock builder) wheel-build path propagates through
        ``build_artifacts`` as a BuildError carrying the captured
        stderr — actionable abort messaging."""
        def _fail(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=2,
                stdout="", stderr="boom: build broke",
            )
        plan = _mk_plan(["pip-local-wheel"])
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "h"
            harness_run.mkdir()
            with mock.patch("bin.harness.plan_runner.subprocess.run",
                             side_effect=_fail):
                with self.assertRaises(PR.BuildError) as ctx:
                    PR.build_artifacts(harness_run, plan)
            self.assertIn("wheel build failed", str(ctx.exception))
            self.assertIn("boom: build broke",
                            str(ctx.exception))

    def test_default_tgz_failure_raises_build_error_with_stderr(
            self) -> None:
        def _fail(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=1,
                stdout="", stderr="npm: missing package.json",
            )
        plan = _mk_plan(["npm-local-tgz"])
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "h"
            harness_run.mkdir()
            with mock.patch("bin.harness.plan_runner.subprocess.run",
                             side_effect=_fail):
                with self.assertRaises(PR.BuildError) as ctx:
                    PR.build_artifacts(harness_run, plan)
            self.assertIn("tgz build failed", str(ctx.exception))
            self.assertIn("npm: missing package.json",
                            str(ctx.exception))

    def test_default_builder_failure_aborts_run_plan_no_runs(
            self) -> None:
        """The 101 ``run_plan_aborts_no_runs_no_summary`` pin
        extended to the DEFAULT (live-shelled) builder, not just
        a mock raiser: with subprocess patched to fail, run_plan
        aborts; no run-NN dirs land; no SUMMARY.md."""
        def _fail(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=1,
                stdout="", stderr="build crashed",
            )

        def _fake_run(plan_run, run_dir):
            return {
                "terminal_state":
                    S.TerminalState.ABORTED_PREP.value,
                "facts": None,
                "transcript": "",
                "axes": S.RunAxes(
                    runner=plan_run.runner,
                    mode=plan_run.mode,
                    install_channel=plan_run.channel,
                    model=plan_run.model,
                ),
            }

        plan = _mk_plan(["pip-local-wheel"])
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            with mock.patch("bin.harness.plan_runner.subprocess.run",
                             side_effect=_fail):
                with self.assertRaises(PR.BuildError):
                    PR.run_plan(
                        plan, runs_root,
                        hooks=PR.PlanRunnerHooks(
                            fake_run=_fake_run),
                    )
            # Forensic trail: one harness-run dir, no run-NN
            # dirs, no SUMMARY.md.
            dirs = [d for d in runs_root.iterdir() if d.is_dir()]
            self.assertEqual(len(dirs), 1)
            harness_run = dirs[0]
            self.assertFalse(
                (harness_run / "SUMMARY.md").exists()
            )
            self.assertEqual(
                list(harness_run.glob("run-*")), [],
            )


# ---------------------------------------------------------------------------
# End-to-end: default path produces artifacts and lights the per-run wiring
# ---------------------------------------------------------------------------


class DefaultBuilderEndToEndPatchedTests(unittest.TestCase):

    def test_run_plan_default_builder_produces_artifacts(
            self) -> None:
        """With ``subprocess.run`` patched (so no real build
        runs), the default code path produces the wheel, lands
        it in ``<harness-run>/artifacts/``, writes the
        manifest.json, and the per-run artifact_used.json
        receipt — proving the default-builder wiring lights up
        everything 101 wired."""
        fake = _FakeSubprocess()

        def _fake_run(plan_run, run_dir):
            return {
                "terminal_state":
                    S.TerminalState.ABORTED_PREP.value,
                "facts": None,
                "transcript": "",
                "axes": S.RunAxes(
                    runner=plan_run.runner,
                    mode=plan_run.mode,
                    install_channel=plan_run.channel,
                    model=plan_run.model,
                ),
            }

        plan = _mk_plan(["pip-local-wheel"])
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            with mock.patch("bin.harness.plan_runner.subprocess.run",
                             side_effect=fake):
                outcomes = PR.run_plan(
                    plan, runs_root,
                    hooks=PR.PlanRunnerHooks(fake_run=_fake_run),
                )
            self.assertEqual(len(outcomes), 1)
            harness_run = next(
                d for d in runs_root.iterdir() if d.is_dir()
            )
            artifacts = harness_run / "artifacts"
            # Wheel landed.
            wheels = list(artifacts.glob("*.whl"))
            self.assertEqual(len(wheels), 1)
            # Manifest + per-run receipt.
            self.assertTrue(
                (artifacts / "manifest.json").is_file()
            )
            self.assertTrue(
                (harness_run / "run-00" /
                  "artifact_used.json").is_file()
            )


if __name__ == "__main__":
    unittest.main()
