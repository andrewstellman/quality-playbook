"""v1.5.7 101 — run-plan auto-builds local artifacts.

The plan-runner now builds the pip wheel / npm tgz the plan
needs into ``<harness-run>/artifacts/`` once per harness run,
BEFORE launching any per-run executions. The build is mocked in
unit tests (no real `python -m build` / `npm pack`) via
``BuilderHooks``. Optional ``--wheel`` / ``--tgz`` overrides
copy a pre-built artifact into the folder instead.

Coverage:
  * Channel scan: `_required_local_channels` returns exactly the
    subset of channels that need a local artifact.
  * `build_artifacts` builds only what the plan needs, lands the
    files in ``<harness-run>/artifacts/``, computes sha256, and
    writes ``manifest.json``.
  * Per-run wiring: each local-channel run gets a
    ``<run-dir>/artifact_used.json`` with the matching channel +
    path + sha256; non-local runs do NOT.
  * Build-failure abort: a fake builder that raises ⇒
    `BuildError` propagates, no run-dirs land, no SUMMARY.md.
  * Overrides: ``wheel_override`` / ``tgz_override`` copy the
    given file into the folder and skip the build entirely.
  * Pre-100 baseline preserved: a plan with only ``clone`` runs
    needs no build (returns empty map, writes no manifest).

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness import schema as S


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_plan(channels: "list[str]") -> PR.Plan:
    """Build a plan with one run per supplied channel — the
    minimum needed to exercise the channel scan + per-run
    wiring."""
    runs = []
    for i, ch in enumerate(channels):
        runs.append({
            "description": f"run-{i} on {ch}",
            "repo": "https://github.com/google/gson",
            "ref": "main",
            "runner": "claude",
            "model": "opus",
            "channel": ch,
            "expect": {},
        })
    return PR.parse_plan({"pools": {"claude": 2}, "runs": runs})


def _fake_run(plan_run: PR.PlanRun, run_dir: Path) -> dict:
    """Minimal fake-runner that reports COMPLETED with no facts —
    enough to drive _execute_one_run to write its receipts."""
    return {
        "terminal_state": S.TerminalState.ABORTED_PREP.value,
        "facts": None,
        "transcript": "",
        "axes": S.RunAxes(
            runner=plan_run.runner,
            mode=plan_run.mode,
            install_channel=plan_run.channel,
            model=plan_run.model,
        ),
    }


def _make_builder(track: "dict[str, int]",
                   *, wheel_filename: str = "qpb-1.5.7.whl",
                   tgz_filename: str = "qpb-1.5.7.tgz",
                   wheel_content: bytes = b"FAKE WHEEL CONTENT",
                   tgz_content: bytes = b"FAKE TGZ CONTENT",
                   ) -> PR.BuilderHooks:
    """Builder hooks that count invocations + write small fake
    files into the artifacts dir. ``track`` is the operator-
    facing counter the test asserts on."""

    def _bw(artifacts_dir: Path) -> Path:
        track["wheel"] = track.get("wheel", 0) + 1
        p = artifacts_dir / wheel_filename
        p.write_bytes(wheel_content)
        return p

    def _bt(artifacts_dir: Path) -> Path:
        track["tgz"] = track.get("tgz", 0) + 1
        p = artifacts_dir / tgz_filename
        p.write_bytes(tgz_content)
        return p

    return PR.BuilderHooks(build_wheel=_bw, build_tgz=_bt)


# ---------------------------------------------------------------------------
# Task A.1 — channel scan: build only what the plan needs
# ---------------------------------------------------------------------------


class RequiredChannelsScanTests(unittest.TestCase):

    def test_only_wheel_channel_needs_only_wheel(self) -> None:
        plan = _mk_plan(["pip-local-wheel"])
        needed = PR._required_local_channels(plan)
        self.assertEqual(needed, {S.InstallChannel.PIP_LOCAL_WHEEL})

    def test_only_tgz_channel_needs_only_tgz(self) -> None:
        plan = _mk_plan(["npm-local-tgz"])
        needed = PR._required_local_channels(plan)
        self.assertEqual(needed, {S.InstallChannel.NPM_LOCAL_TGZ})

    def test_both_needed_when_plan_mixes_them(self) -> None:
        plan = _mk_plan(["pip-local-wheel", "npm-local-tgz",
                          "pip-local-wheel"])
        needed = PR._required_local_channels(plan)
        self.assertEqual(needed, {
            S.InstallChannel.PIP_LOCAL_WHEEL,
            S.InstallChannel.NPM_LOCAL_TGZ,
        })

    def test_clone_only_plan_needs_nothing(self) -> None:
        plan = _mk_plan(["clone", "clone"])
        needed = PR._required_local_channels(plan)
        self.assertEqual(needed, set())

    def test_registry_channels_need_nothing(self) -> None:
        plan = _mk_plan(["pip-registry@1.5.7",
                          "npm-registry@1.5.7"])
        needed = PR._required_local_channels(plan)
        self.assertEqual(needed, set())


# ---------------------------------------------------------------------------
# Task A.2 — build_artifacts: folder placement, sha256, manifest
# ---------------------------------------------------------------------------


class BuildArtifactsFolderTests(unittest.TestCase):

    def test_no_local_channels_writes_nothing(self) -> None:
        plan = _mk_plan(["clone", "clone"])
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "h"
            harness_run.mkdir()
            track: dict[str, int] = {}
            result = PR.build_artifacts(
                harness_run, plan,
                builder=_make_builder(track),
            )
            self.assertEqual(result, {})
            self.assertEqual(track, {})
            self.assertFalse((harness_run / "artifacts").exists())

    def test_only_wheel_invokes_only_wheel_builder(self) -> None:
        plan = _mk_plan(["pip-local-wheel"])
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "h"
            harness_run.mkdir()
            track: dict[str, int] = {}
            result = PR.build_artifacts(
                harness_run, plan,
                builder=_make_builder(track),
            )
            self.assertEqual(track, {"wheel": 1})
            self.assertIn(S.InstallChannel.PIP_LOCAL_WHEEL, result)
            self.assertNotIn(S.InstallChannel.NPM_LOCAL_TGZ, result)
            whl_path = Path(
                result[S.InstallChannel.PIP_LOCAL_WHEEL]["path"]
            )
            self.assertTrue(whl_path.is_file())
            self.assertEqual(
                whl_path.parent, (harness_run / "artifacts").resolve()
            )

    def test_only_tgz_invokes_only_tgz_builder(self) -> None:
        plan = _mk_plan(["npm-local-tgz"])
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "h"
            harness_run.mkdir()
            track: dict[str, int] = {}
            result = PR.build_artifacts(
                harness_run, plan,
                builder=_make_builder(track),
            )
            self.assertEqual(track, {"tgz": 1})
            self.assertIn(S.InstallChannel.NPM_LOCAL_TGZ, result)
            self.assertNotIn(S.InstallChannel.PIP_LOCAL_WHEEL,
                              result)

    def test_both_channels_invokes_both_builders(self) -> None:
        plan = _mk_plan(["pip-local-wheel", "npm-local-tgz",
                          "pip-local-wheel"])
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "h"
            harness_run.mkdir()
            track: dict[str, int] = {}
            result = PR.build_artifacts(
                harness_run, plan,
                builder=_make_builder(track),
            )
            # ONE wheel build (not per pip-local-wheel run);
            # ONE tgz build.
            self.assertEqual(track, {"wheel": 1, "tgz": 1})
            self.assertEqual(set(result.keys()), {
                S.InstallChannel.PIP_LOCAL_WHEEL,
                S.InstallChannel.NPM_LOCAL_TGZ,
            })

    def test_manifest_json_carries_provenance(self) -> None:
        plan = _mk_plan(["pip-local-wheel"])
        wheel_bytes = b"DETERMINISTIC WHEEL"
        expected_sha = hashlib.sha256(wheel_bytes).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "h"
            harness_run.mkdir()
            result = PR.build_artifacts(
                harness_run, plan,
                builder=_make_builder({},
                                         wheel_content=wheel_bytes),
            )
            manifest_path = (
                harness_run / "artifacts" / "manifest.json"
            )
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            self.assertIn("pip-local-wheel", manifest)
            self.assertEqual(
                manifest["pip-local-wheel"]["sha256"], expected_sha,
            )
            self.assertEqual(
                result[S.InstallChannel.PIP_LOCAL_WHEEL]["sha256"],
                expected_sha,
            )


# ---------------------------------------------------------------------------
# Task A.3 — build failure aborts cleanly
# ---------------------------------------------------------------------------


class BuildFailureAbortsTests(unittest.TestCase):

    def test_failing_wheel_build_raises_build_error(self) -> None:
        def _bad_wheel(artifacts_dir: Path) -> Path:
            raise RuntimeError("pip-build crashed (simulated)")
        builder = PR.BuilderHooks(build_wheel=_bad_wheel)
        plan = _mk_plan(["pip-local-wheel"])
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "h"
            harness_run.mkdir()
            with self.assertRaises(PR.BuildError) as ctx:
                PR.build_artifacts(
                    harness_run, plan, builder=builder,
                )
            self.assertIn("wheel build failed", str(ctx.exception))
            self.assertIn("pip-build crashed", str(ctx.exception))

    def test_default_builder_failure_with_subprocess_patched(
            self) -> None:
        """v1.5.7 102 retired the 'default raises
        NotImplementedError' assertion: the default builder is
        now live (shells out). With ``subprocess.run`` patched
        to return non-zero, the default-builder code path still
        raises a BuildError that carries the captured stderr.
        The deeper coverage (correct argv / cwd / one-build-per-
        artifact) lives in ``test_default_builder_wired_102.py``.
        """
        import subprocess as _sub
        import unittest.mock as _mock

        def _fake_run(cmd, **kwargs):
            return _sub.CompletedProcess(
                args=cmd, returncode=1,
                stdout="", stderr="simulated build failure",
            )
        plan = _mk_plan(["pip-local-wheel"])
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "h"
            harness_run.mkdir()
            with _mock.patch("bin.harness.plan_runner.subprocess.run",
                             side_effect=_fake_run):
                with self.assertRaises(PR.BuildError) as ctx:
                    PR.build_artifacts(harness_run, plan)
            self.assertIn("wheel build failed",
                            str(ctx.exception))
            self.assertIn("simulated build failure",
                            str(ctx.exception))

    def test_run_plan_aborts_no_runs_no_summary(self) -> None:
        """A BuildError from `build_artifacts` propagates through
        `run_plan` — no per-run dirs and no SUMMARY.md should be
        written."""
        def _bad_wheel(artifacts_dir: Path) -> Path:
            raise RuntimeError("simulated failure")
        builder = PR.BuilderHooks(build_wheel=_bad_wheel)
        plan = _mk_plan(["pip-local-wheel"])
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            with self.assertRaises(PR.BuildError):
                PR.run_plan(
                    plan, runs_root,
                    hooks=PR.PlanRunnerHooks(fake_run=_fake_run),
                    builder=builder,
                )
            # The harness-run dir was created (forensic trail),
            # but no run-NN dirs and no SUMMARY.md.
            dirs = [d for d in runs_root.iterdir() if d.is_dir()]
            self.assertEqual(len(dirs), 1)
            harness_run = dirs[0]
            self.assertFalse((harness_run / "SUMMARY.md").exists())
            self.assertEqual(
                list(harness_run.glob("run-*")), [],
                "no per-run dirs should exist after build failure",
            )


# ---------------------------------------------------------------------------
# Task B — per-run artifact_used.json provenance
# ---------------------------------------------------------------------------


class PerRunArtifactProvenanceTests(unittest.TestCase):

    def test_pip_local_wheel_run_gets_artifact_used_receipt(
            self) -> None:
        plan = _mk_plan(["pip-local-wheel", "clone"])
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            outcomes = PR.run_plan(
                plan, runs_root,
                hooks=PR.PlanRunnerHooks(fake_run=_fake_run),
                builder=_make_builder({}),
            )
            self.assertEqual(len(outcomes), 2)
            harness_run = next(
                d for d in runs_root.iterdir() if d.is_dir()
            )
            # Run 0 (pip-local-wheel): artifact_used.json exists.
            run0 = harness_run / "run-00"
            self.assertTrue(
                (run0 / "artifact_used.json").is_file(),
                "pip-local-wheel run must record provenance",
            )
            inv = json.loads(
                (run0 / "artifact_used.json").read_text(
                    encoding="utf-8")
            )
            self.assertEqual(inv["channel"], "pip-local-wheel")
            self.assertEqual(inv["filename"], "qpb-1.5.7.whl")
            self.assertEqual(
                inv["sha256"],
                hashlib.sha256(b"FAKE WHEEL CONTENT").hexdigest(),
            )
            self.assertTrue(Path(inv["path"]).is_file())

            # Run 1 (clone): no artifact_used.json.
            run1 = harness_run / "run-01"
            self.assertFalse(
                (run1 / "artifact_used.json").exists(),
                "clone run must NOT carry artifact provenance "
                "(no local artifact used)",
            )

    def test_npm_local_tgz_run_gets_artifact_used_receipt(
            self) -> None:
        plan = _mk_plan(["npm-local-tgz"])
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            PR.run_plan(
                plan, runs_root,
                hooks=PR.PlanRunnerHooks(fake_run=_fake_run),
                builder=_make_builder({}),
            )
            harness_run = next(
                d for d in runs_root.iterdir() if d.is_dir()
            )
            inv = json.loads(
                (harness_run / "run-00" /
                  "artifact_used.json").read_text(encoding="utf-8")
            )
            self.assertEqual(inv["channel"], "npm-local-tgz")
            self.assertEqual(inv["filename"], "qpb-1.5.7.tgz")
            self.assertEqual(
                inv["sha256"],
                hashlib.sha256(b"FAKE TGZ CONTENT").hexdigest(),
            )


# ---------------------------------------------------------------------------
# Task C — `--wheel` / `--tgz` overrides skip the build
# ---------------------------------------------------------------------------


class WheelOverrideTests(unittest.TestCase):

    def test_wheel_override_skips_build_and_copies_into_folder(
            self) -> None:
        plan = _mk_plan(["pip-local-wheel"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            override = tmp_p / "prebuilt.whl"
            override.write_bytes(b"PREBUILT WHEEL")
            harness_run = tmp_p / "h"
            harness_run.mkdir()
            track: dict[str, int] = {}
            result = PR.build_artifacts(
                harness_run, plan,
                builder=_make_builder(track),
                wheel_override=override,
            )
            # Build NOT invoked.
            self.assertEqual(track, {})
            # File copied into the artifacts dir.
            placed = Path(
                result[S.InstallChannel.PIP_LOCAL_WHEEL]["path"]
            )
            self.assertEqual(placed.name, "prebuilt.whl")
            self.assertEqual(placed.parent.name, "artifacts")
            self.assertEqual(
                placed.read_bytes(), b"PREBUILT WHEEL",
            )
            # sha256 reflects the override content, not any
            # build.
            self.assertEqual(
                result[S.InstallChannel.PIP_LOCAL_WHEEL]["sha256"],
                hashlib.sha256(b"PREBUILT WHEEL").hexdigest(),
            )

    def test_wheel_override_missing_path_raises_build_error(
            self) -> None:
        plan = _mk_plan(["pip-local-wheel"])
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp) / "h"
            harness_run.mkdir()
            with self.assertRaises(PR.BuildError) as ctx:
                PR.build_artifacts(
                    harness_run, plan,
                    wheel_override=Path(tmp) / "does-not-exist.whl",
                )
            self.assertIn("wheel override not found",
                            str(ctx.exception))


class TgzOverrideTests(unittest.TestCase):

    def test_tgz_override_skips_build_and_copies_into_folder(
            self) -> None:
        plan = _mk_plan(["npm-local-tgz"])
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            override = tmp_p / "prebuilt.tgz"
            override.write_bytes(b"PREBUILT TGZ")
            harness_run = tmp_p / "h"
            harness_run.mkdir()
            track: dict[str, int] = {}
            result = PR.build_artifacts(
                harness_run, plan,
                builder=_make_builder(track),
                tgz_override=override,
            )
            self.assertEqual(track, {})
            placed = Path(
                result[S.InstallChannel.NPM_LOCAL_TGZ]["path"]
            )
            self.assertEqual(placed.name, "prebuilt.tgz")
            self.assertEqual(placed.parent.name, "artifacts")


# ---------------------------------------------------------------------------
# Pre-101 baseline preserved: clone-only plans need no build
# ---------------------------------------------------------------------------


class CloneOnlyPlanNoBuildTests(unittest.TestCase):

    def test_clone_only_plan_runs_without_invoking_builder(
            self) -> None:
        """The 099/100 baseline: a plan whose runs are all
        ``clone`` channel should never trigger a build. The
        default builder (which raises NotImplementedError) must
        not be hit."""
        plan = _mk_plan(["clone", "clone"])
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            # No builder, no override — the default would raise
            # if invoked.
            outcomes = PR.run_plan(
                plan, runs_root,
                hooks=PR.PlanRunnerHooks(fake_run=_fake_run),
            )
            self.assertEqual(len(outcomes), 2)
            harness_run = next(
                d for d in runs_root.iterdir() if d.is_dir()
            )
            self.assertFalse(
                (harness_run / "artifacts").exists(),
                "clone-only plans must not create an artifacts/ "
                "dir",
            )
            # SUMMARY.md still landed.
            self.assertTrue(
                (harness_run / "SUMMARY.md").is_file(),
            )


if __name__ == "__main__":
    unittest.main()
