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

WHY THIS SUBPROCESS TEST ACTUALLY TRAVERSES THE BYPASS (instruction
053 / 051 Option B — making the traversal self-evident to a static
reviewer): `parse_args` defaults `args.parallel = True` for every
non-`--worker` invocation — see `parse_args`'s worker-branch
(`if args.worker: args.parallel = False`) in `bin/run_playbook.py`.
This subprocess test invokes the real CLI WITHOUT `--worker`, so
`args.parallel` is True → the parent enters the `if args.parallel:`
worker-spawn branch in `execute_run` and calls `build_worker_command`
— and `build_worker_command` is the ONLY call site of the A-8
bypass. (Stable function-name references used here, not line numbers:
cumulative run_playbook.py edits in 053/054/055 drifted the original
:732 / :5081 / :5088 citations — instruction-053b F3.) Therefore deleting the `--logs-flat`
propagation block inside `build_worker_command` MUST flip this test
from PASS to FAIL. A static reviewer does not need to know the
`parse_args` default to see this: `test_logs_flat_writes_legacy_paths_only`
now passes `--parallel` explicitly (redundant with the default, but
it pins traversal unmistakably and defends against a future change to
the parallel default), and `test_logs_flat_spans_parse_args_through_
worker_to_disk` asserts the full chain
(parse_args → build_worker_command-contains-`--logs-flat` → spawned
worker → on-disk legacy layout) in one reviewer-checkable place.

Mutation-test evidence (in-tree per
ai_context/DEVELOPMENT_PROCESS.md:152-160): delete the instruction-051
A-8 `if getattr(args, "logs_flat", False): command.append(
"--logs-flat")` propagation block from
bin/run_playbook.py:build_worker_command. Expected failure:
test_logs_flat_writes_legacy_paths_only fails at
`assertFalse(centralized_run_id_dirs(...))` because the worker
subprocess, parsed without --logs-flat, writes the CENTRALIZED
quality/logs/<run-id>/ tree (the original bug); AND
test_logs_flat_spans_parse_args_through_worker_to_disk fails even
earlier — at its in-process `assertIn("--logs-flat",
build_worker_command(args, "."))` assertion, before any subprocess
runs (the deterministic, no-subprocess proof that traversal is real).
Restore the block → both pass. Bite verified during instruction 051
development (subprocess test) and instruction 053 development
(spanning test). (The env twin test was NOT broken pre-fix — env vars
inherit into the subprocess so QPB_LOGS_LEGACY=1 always propagated;
it pins the flag/env equivalence and guards future regressions.)
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import run_playbook

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
    # v1.5.7 084b: this is a REAL drive invocation of the runner (no
    # --help/--worker/--operator-invoked), so under an ambient agent
    # env (dev/CI running pytest from inside a Claude Code / Codex /
    # Copilot terminal) the v1.5.7 A-22 guard would refuse it. These
    # tests exercise logs-LAYOUT behavior, not agent-context behavior;
    # strip the agent-context signals so the child runs as if from a
    # bare operator shell (consistent with this helper's existing
    # test-hygiene env isolation above).
    for _agent_var in run_playbook._AGENT_CONTEXT_SIGNALS:
        env.pop(_agent_var, None)
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
        # `--parallel` is redundant with the parse_args default
        # (args.parallel=True for non-`--worker` runs) but is passed
        # explicitly here (instruction 053 / 051 Option B) to pin the
        # worker-spawn traversal unmistakably and defend against a
        # future change to the parallel default.
        with TemporaryDirectory() as tmp:
            wd = Path(tmp)
            out = _run_until_layout(
                wd, extra_args=["--logs-flat", "--parallel"]
            )
            self._assert_legacy_layout(wd, out)

    def test_qpb_logs_legacy_env_writes_legacy_paths_only(self) -> None:
        """Task 5: same assertions, env-driven (QPB_LOGS_LEGACY=1, no
        --logs-flat flag). Pins the flag/env equivalence in
        `bin/run_playbook.py`'s `_logs_legacy_mode`. This path
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

    def test_logs_flat_spans_parse_args_through_worker_to_disk(self) -> None:
        """Instruction 053 / 051 Option B: ONE reviewer-checkable
        artifact spanning the entire A-8 chain — real CLI args →
        parsed namespace → worker-argv reconstruction → spawned worker
        → on-disk legacy layout. This is the single test codex's
        instruction-051 Q4 was asking for; a static reviewer can
        follow steps 1→2 without running anything to see the bypass is
        traversed.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160): delete the
        instruction-051 A-8 propagation block
        (`if getattr(args, "logs_flat", False):
        command.append("--logs-flat")`) from
        bin/run_playbook.py:build_worker_command. Expected failure:
        THIS test fails at step 2's
        `self.assertIn("--logs-flat", cmd)` — BEFORE any subprocess is
        spawned (deterministic, fast, no-subprocess proof that the
        worker-argv reconstruction is the bypass and that this test
        traverses it). Restore the block → passes. Bite executed
        during instruction 053 development; PASS→FAIL on mutation,
        FAIL→PASS on restore, confirmed.
        """
        with TemporaryDirectory() as tmp:
            wd = Path(tmp)
            # Step 1: real CLI args → parsed namespace. No `--worker`,
            # so parse_args defaults args.parallel=True (the property
            # that makes the parent re-spawn a worker via
            # build_worker_command — the only A-8 bypass site).
            args = run_playbook.parse_args([
                str(wd), "--model", "sonnet", "--logs-flat", "--phase", "1",
            ])
            self.assertIs(args.parallel, True)
            self.assertIs(args.logs_flat, True)

            # Step 2: worker-argv reconstruction propagates --logs-flat
            # (the A-8 fix). Fails here, pre-subprocess, if the
            # propagation block is reverted.
            cmd = run_playbook.build_worker_command(args, str(wd))
            self.assertIn("--logs-flat", cmd)

            # Step 3: the real CLI subprocess writes the legacy layout
            # only — no centralized quality/logs/<run-id>/.
            out = _run_until_layout(
                wd, extra_args=["--logs-flat", "--parallel"]
            )
            self._assert_legacy_layout(wd, out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
