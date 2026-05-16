"""End-to-end layout tests for the v1.5.7 A-8 fix (instruction 051):
`--logs-flat` (and its env twin `QPB_LOGS_LEGACY=1`) must flip the
runner-owned log + run_state layout to the v1.5.6 legacy paths.

WHY THESE ARE SUBPROCESS / FULL-ENTRY-POINT TESTS, NOT DIRECT-HELPER
TESTS: the A-8 bug lived in the parent → worker argv reconstruction
(`build_worker_command` omitted `--logs-flat`), NOT in the
path-computing helpers (`_run_log_dir` / `log_file_for` /
`_run_state_jsonl_path`). Those helpers' own unit tests always passed
because they exercise the predicate in isolation — which is exactly
why the bug went undetected for the whole flag path. The only way to
catch it is to run the actual CLI entry point so the parent dispatch
re-spawns a worker and the real file writes happen. (A fast,
deterministic complement that pins the precise bypass-site fix lives
in test_run_playbook.py::*build_worker_command*logs_flat* — these
on-disk tests are the integration backstop.)

Mutation-test evidence (in-tree per
ai_context/DEVELOPMENT_PROCESS.md:152-160): delete the instruction-051
A-8 `if getattr(args, "logs_flat", False): command.append(
"--logs-flat")` propagation block from
bin/run_playbook.py:build_worker_command. Expected failure:
test_logs_flat_writes_legacy_paths_only fails at
`assertFalse(centralized_run_id_dirs(...))` because the worker
subprocess, parsed without --logs-flat, writes the CENTRALIZED
quality/logs/<run-id>/ tree (the original bug). Restore the block →
passes. Bite verified during instruction 051 development. (The env
twin test was NOT broken pre-fix — env vars inherit into the
subprocess so QPB_LOGS_LEGACY=1 always propagated; it pins the
flag/env equivalence and guards future regressions.)
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUN_PLAYBOOK = REPO_ROOT / "bin" / "run_playbook.py"
# The runner sets up the log/run_state layout BEFORE the (doomed,
# no-backend) model invocation; this cap is generous enough for the
# layout to land and short enough to keep the suite snappy.
_LAYOUT_SETTLE_SECONDS = 45


def _run_until_layout(workdir: Path, *, extra_args, env_extra=None):
    """Invoke the real runner CLI against `workdir` until the
    layout has been written, then hard-kill the whole process group
    (the runner re-spawns worker subprocesses; killing only the
    parent leaks them). Returns the combined stdout/stderr text."""
    env = os.environ.copy()
    # Isolate from a stray real ~/.qpb/config.json (orchestrator D6
    # test pollution) and from an inherited QPB_LOGS_LEGACY.
    env.pop("QPB_LOGS_LEGACY", None)
    if env_extra:
        env.update(env_extra)
    cmd = [
        sys.executable, str(RUN_PLAYBOOK), ".",
        "--model", "sonnet", "--phase", "1", *extra_args,
    ]
    proc = subprocess.Popen(
        cmd, cwd=str(workdir), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=_LAYOUT_SETTLE_SECONDS)
    except subprocess.TimeoutExpired:
        # Kill the whole process group (parent + re-spawned workers).
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out = ""
    return out or ""


def _centralized_run_id_dirs(workdir: Path):
    """Run-id subdirectories under quality/logs/ (excluding the
    `latest` symlink). Their presence == centralized layout == the
    A-8 bug when --logs-flat / QPB_LOGS_LEGACY=1 is in effect."""
    logs = workdir / "quality" / "logs"
    if not logs.is_dir():
        return []
    return [
        p for p in logs.iterdir()
        if p.is_dir() and p.name != "latest" and not p.is_symlink()
    ]


class LogsFlatEndToEndTests(unittest.TestCase):
    def _assert_legacy_layout(self, workdir: Path, out: str) -> None:
        centralized = _centralized_run_id_dirs(workdir)
        self.assertEqual(
            centralized, [],
            f"CENTRALIZED layout leaked under legacy mode (A-8 "
            f"regression): quality/logs/<run-id>/ dirs exist "
            f"{[p.name for p in centralized]}. runner output:\n"
            f"{out[:1500]}",
        )
        # Decisive legacy signals (instruction 051 Task 4 allows
        # relaxing the parent-dir *-playbook-*.log check — it lands as
        # a sibling of the target dir; the in-target signals below are
        # unambiguous).
        self.assertTrue(
            (workdir / "quality" / "run_state.jsonl").is_file(),
            f"legacy quality/run_state.jsonl missing — layout did not "
            f"flip. runner output:\n{out[:1500]}",
        )
        self.assertTrue(
            (workdir / "quality" / "control_prompts").is_dir(),
            f"legacy quality/control_prompts/ missing — layout did "
            f"not flip. runner output:\n{out[:1500]}",
        )

    def test_logs_flat_writes_legacy_paths_only(self) -> None:
        with TemporaryDirectory() as tmp:
            wd = Path(tmp)
            out = _run_until_layout(wd, extra_args=["--logs-flat"])
            self._assert_legacy_layout(wd, out)

    def test_qpb_logs_legacy_env_writes_legacy_paths_only(self) -> None:
        """Task 5: same assertions, env-driven (QPB_LOGS_LEGACY=1, no
        --logs-flat flag). Pins the flag/env equivalence in
        _logs_legacy_mode (bin/run_playbook.py:1405-1407). This path
        was NOT broken by the A-8 bug (env vars inherit into the
        re-spawned worker subprocess) — the test guards against a
        future regression and pins that both knobs reach the same
        legacy layout."""
        with TemporaryDirectory() as tmp:
            wd = Path(tmp)
            out = _run_until_layout(
                wd, extra_args=[], env_extra={"QPB_LOGS_LEGACY": "1"}
            )
            self._assert_legacy_layout(wd, out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
