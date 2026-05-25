"""QPB Test Harness — runner adapter (claude only for Phase 1).

Per the instruction: Phase 1 supports the CLAUDE adapter only.
Other CLIs (codex / copilot / cursor) and Mode B (via
``bin/run_playbook.py`` reuse) are explicitly Phase 5.

Contract:
  * Detached subprocess via ``start_new_session=True`` so closing
    a client never kills a run (design §H / lifecycle).
  * PID + heartbeat capture written to a status file.
  * Raw NDJSON stream capture to ``stream.ndjson`` (always
    retained, gitignored by ``repos/security-test-cases/.gitignore``
    — never committed).
  * Per-run **max-duration timeout** — kill the process tree on
    expiry; terminal state ``TIMED_OUT``.
  * Support ``install_channel=CLONE`` only for Phase 1 (Phase 2's
    local-wheel/local-tgz adds the channel command-builders).
"""
from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bin.harness.schema import (
    InstallChannel,
    RunAxes,
    Runner,
    TerminalState,
)


class RunnerError(RuntimeError):
    """A runner adapter call failed for a non-timeout reason
    (e.g. claude CLI is not on PATH, or the channel is not yet
    supported in Phase 1)."""


# Phase 1: only the CLAUDE adapter is wired. The others are
# rejected at runtime with a clear "Phase 5" message; the schema
# enum has them so cases can be authored in advance.
_PHASE1_RUNNERS = {Runner.CLAUDE}
_PHASE1_CHANNELS = {InstallChannel.CLONE}


def _utc_now_iso() -> str:
    """UTC ISO-8601 timestamp matching the QPB run-id convention
    (without microseconds, with the Zulu suffix)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class LaunchSpec:
    """Caller-supplied launch parameters. Phase 1 is intentionally
    minimal — Phase 4's manager builds richer specs from queue
    entries."""
    target_dir: Path
    run_dir: Path
    axes: RunAxes
    case_id: str
    run_id: str
    max_duration_s: float
    prompt: str
    # Passed verbatim into the subprocess env (after env_snapshot
    # capture). Used to set the vendor env var for the run (e.g.
    # ``CLAUDECODE=1``) — this is what makes the gate's runner
    # detection correct when we later re-run the gate for
    # gate-derived facts.
    extra_env: "dict[str, str]" = None  # type: ignore[assignment]


@dataclass
class LaunchResult:
    """Returned after the run terminates (or is timed out / killed).
    The harness writes this into ``status.json`` + uses
    ``terminal_state`` / ``exit_code`` to drive grading."""
    pid: int
    started_at: str
    ended_at: str
    exit_code: int
    terminal_state: TerminalState
    cli_command: str
    cwd: str
    env_snapshot: dict
    stream_path: Path


def _vendor_env_for(runner: Runner) -> "dict[str, str]":
    """Return the env var the gate's ``_RUNNER_ENV_MARKERS`` looks
    for (see ``quality_gate.py``). For Phase 1 ``CLAUDE`` →
    ``CLAUDECODE=1``."""
    if runner == Runner.CLAUDE:
        return {"CLAUDECODE": "1"}
    if runner == Runner.CODEX:
        return {"CODEX_THREAD_ID": "harness"}
    if runner == Runner.COPILOT:
        return {"COPILOT_AGENT_SESSION_ID": "harness"}
    return {}


def _claude_command(model: str, prompt: str,
                     thinking: "str | None" = None) -> "list[str]":
    """Build the claude CLI invocation for a Mode A run.

    Uses the same flags QPB's existing ``run_playbook.py`` uses
    (``--print``, ``--dangerously-skip-permissions``,
    ``--model``). Stream is captured via ``--output-format
    stream-json --verbose``, matching the design §G note that
    "claude has clean stream-json --verbose".

    NOTE: ``thinking`` is reserved for axes parity but not yet
    wired into the claude CLI invocation here (Phase 1 stays
    minimal; Phase 5 broadens this when codex/copilot adapters
    land and the thinking parameter shapes per-CLI).
    """
    return [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--model", model,
        "--output-format", "stream-json",
        "--verbose",
        prompt,
    ]


def _command_for_axes(axes: RunAxes, prompt: str) -> "list[str]":
    """Phase 1: only claude+clone is supported. Anything else
    raises a clear RunnerError so a case-author trying to author
    a multi-runner case in advance gets a helpful message rather
    than a cryptic subprocess failure.
    """
    if axes.runner not in _PHASE1_RUNNERS:
        raise RunnerError(
            f"runner {axes.runner.value!r} is not supported in "
            f"Phase 1 (claude only); the {axes.runner.value} "
            f"adapter lands in Phase 5."
        )
    if axes.install_channel not in _PHASE1_CHANNELS:
        raise RunnerError(
            f"install_channel {axes.install_channel.value!r} is "
            f"not supported in Phase 1 (clone only); local-wheel/"
            f"local-tgz land in Phase 2, registry in Phase 6."
        )
    return _claude_command(axes.model, prompt, axes.thinking)


def _write_status(run_dir: Path, status: dict) -> None:
    """Atomic write of status.json (tmp + rename), so a reader
    never sees a partial file."""
    target = run_dir / "status.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, indent=2) + "\n",
                    encoding="utf-8")
    os.replace(tmp, target)


def _kill_process_tree(pid: int) -> None:
    """SIGTERM the process group started by ``start_new_session``.
    Falls through to SIGKILL after a short grace period. Phase 4's
    manager will own this; Phase 1 just needs it for the timeout
    path here.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGTERM)
    time.sleep(2.0)
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGKILL)


def launch_run(spec: LaunchSpec) -> LaunchResult:
    """Launch one run end-to-end. Detached subprocess, stream
    capture, max-duration timeout, status file written.

    Phase 1 contract: returns ``LaunchResult`` once the run
    terminates (or is killed by the timeout). Phase 4's manager
    will own the parallel orchestration of many concurrent
    LaunchSpecs; this function stays a single-run primitive.
    """
    spec.run_dir.mkdir(parents=True, exist_ok=True)
    cmd = _command_for_axes(spec.axes, spec.prompt)
    cli_command = " ".join(cmd)

    # Snapshot env at launch time — recorded in invocation.json so
    # the run is reproducible. Includes the vendor env var we set
    # below so the run + the later gate re-run agree.
    env = os.environ.copy()
    env.update(_vendor_env_for(spec.axes.runner))
    if spec.extra_env:
        env.update(spec.extra_env)
    env_snapshot = {
        k: v for k, v in env.items()
        # Keep the snapshot tight: only the vendor markers + the
        # explicit extras. Full os.environ is noisy and may carry
        # secrets the operator wouldn't want in receipts.
        if (k in ("CLAUDECODE", "CODEX_THREAD_ID",
                   "COPILOT_AGENT_SESSION_ID", "CURSOR")
             or (spec.extra_env and k in spec.extra_env))
    }

    stream_path = spec.run_dir / "stream.ndjson"
    started_at = _utc_now_iso()
    # Pre-write the QUEUED→RUNNING status so an observer (Phase 4
    # TUI / external watcher) can see the run is live before it
    # produces stream output.
    _write_status(spec.run_dir, {
        "state": "RUNNING",
        "pid": None,  # filled in once we have it
        "started_at": started_at,
        "heartbeat": started_at,
        "exit_code": None,
        "terminal_state": None,
    })

    with open(stream_path, "wb") as stream_fp:
        proc = subprocess.Popen(
            cmd,
            cwd=str(spec.target_dir),
            stdout=stream_fp,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        _write_status(spec.run_dir, {
            "state": "RUNNING",
            "pid": proc.pid,
            "started_at": started_at,
            "heartbeat": started_at,
            "exit_code": None,
            "terminal_state": None,
        })

        terminal_state: TerminalState
        exit_code: int
        try:
            exit_code = proc.wait(timeout=spec.max_duration_s)
            # Per SCHEMA.md §6: COMPLETED requires exit-0 AND a
            # gate verdict in the produced artifacts. Phase 1
            # routes by exit code only — Phase 2's grader will
            # re-classify ``COMPLETED`` vs ``FAILED`` based on
            # whether the gate produced a verdict.
            terminal_state = (TerminalState.COMPLETED if exit_code == 0
                                else TerminalState.FAILED)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc.pid)
            # After kill, reap the now-defunct process so PID
            # tracking is honest.
            with contextlib.suppress(subprocess.TimeoutExpired):
                exit_code = proc.wait(timeout=5.0)
            else_exit = proc.returncode
            exit_code = else_exit if else_exit is not None else -1
            terminal_state = TerminalState.TIMED_OUT

    ended_at = _utc_now_iso()
    _write_status(spec.run_dir, {
        "state": "DONE",
        "pid": proc.pid,
        "started_at": started_at,
        "heartbeat": ended_at,
        "ended_at": ended_at,
        "exit_code": exit_code,
        "terminal_state": terminal_state.value,
    })

    return LaunchResult(
        pid=proc.pid,
        started_at=started_at,
        ended_at=ended_at,
        exit_code=exit_code,
        terminal_state=terminal_state,
        cli_command=cli_command,
        cwd=str(spec.target_dir),
        env_snapshot=env_snapshot,
        stream_path=stream_path,
    )


__all__ = [
    "RunnerError",
    "LaunchSpec",
    "LaunchResult",
    "launch_run",
    # Exposed for tests + Phase 5 to reuse:
    "_claude_command",
    "_command_for_axes",
    "_vendor_env_for",
    "_kill_process_tree",
]
