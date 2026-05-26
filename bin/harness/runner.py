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
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bin.harness.schema import (
    InstallChannel,
    Mode,
    RunAxes,
    Runner,
    TerminalState,
)


class RunnerError(RuntimeError):
    """A runner adapter call failed for a non-timeout reason
    (e.g. claude CLI is not on PATH, or the channel is not yet
    supported)."""


# Phases supported by the current runner implementation:
#   * Phase 1 (091): claude adapter, clone channel.
#   * Phase 5 (095): codex / copilot / cursor adapters + Mode B
#     reuse of ``bin.run_playbook`` for each.
# Channel coverage is still Phase 1's ``clone`` only — Phase 2
# wires local-wheel/local-tgz; Phase 6 wires registry.
_SUPPORTED_RUNNERS = {Runner.CLAUDE, Runner.CODEX,
                      Runner.COPILOT, Runner.CURSOR}
_SUPPORTED_CHANNELS = {InstallChannel.CLONE}


def _utc_now_iso() -> str:
    """UTC ISO-8601 timestamp matching the QPB run-id convention
    (without microseconds, with the Zulu suffix)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class LaunchSpec:
    """Caller-supplied launch parameters. The Phase 4 manager
    builds richer specs from queue entries."""
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
    # v1.5.7 100: extra argv tokens spliced into the runner CLI at
    # the runner-appropriate position (the harness does NOT
    # interpret them). Example for codex low thinking:
    # ``["-c", "model_reasoning_effort=\"low\""]`` → spliced
    # between ``codex`` and ``exec``. Default empty list.
    parameters: "list[str]" = None  # type: ignore[assignment]


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
                     thinking: "str | None" = None,
                     parameters: "list[str] | None" = None,
                     ) -> "list[str]":
    """Build the claude CLI invocation for a Mode A run.

    Uses the same flags QPB's existing ``run_playbook.py``
    ``command_for_runner`` uses (``-p``, ``--dangerously-skip-
    permissions``, ``--model``). Stream is captured via
    ``--output-format stream-json --verbose``, matching the
    design §G note that "claude has clean stream-json --verbose".

    NOTE: ``thinking`` is reserved for axes parity but not yet
    wired into the claude CLI invocation — the production
    `run_playbook.command_for_runner` doesn't pass it either;
    when claude grows a stable thinking-effort flag, both this
    helper and the production builder gain it together.

    v1.5.7 100: ``parameters`` (when non-empty) is spliced
    verbatim into the flags region — between the standard flags
    and the trailing positional prompt — so claude reads them as
    additional CLI flags without disturbing prompt routing.
    """
    return [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--model", model,
        "--output-format", "stream-json",
        "--verbose",
        *(parameters or []),
        prompt,
    ]


def _codex_command(model: str,
                    parameters: "list[str] | None" = None,
                    ) -> "list[str]":
    """v1.5.7 095 Phase 5: codex adapter. Mirrors
    ``bin.run_playbook.command_for_runner`` for ``runner=codex``:
    ``codex exec --full-auto`` reads the prompt from stdin when
    no positional prompt is provided (codex-cli 0.125+). The
    trailing ``"-"`` is the explicit stdin sentinel.

    Caller must set ``stdin_input=prompt`` on the LaunchSpec so
    the prompt reaches the subprocess on stdin (argv would hit
    shell command-line length limits on long phase prompts).

    v1.5.7 100: ``parameters`` (when non-empty) is spliced
    verbatim between ``codex`` and ``exec`` — codex reads
    ``-c <key=value>`` (and similar global config overrides) only
    when they precede the subcommand. The stdin sentinel ``-``
    stays at the end so prompt routing is unchanged.
    """
    command = ["codex", *(parameters or []), "exec", "--full-auto"]
    if model:
        command.extend(["-m", model])
    command.append("-")
    return command


def _copilot_command(model: str, prompt: str,
                      parameters: "list[str] | None" = None,
                      ) -> "list[str]":
    """v1.5.7 095 Phase 5: copilot adapter. Mirrors the
    ``copilot_resolver`` pattern from ``bin.run_playbook``: the
    standalone ``copilot`` CLI is preferred when on PATH; the
    deprecated ``gh copilot`` extension is the grace-period
    fallback (089f).

    The harness-side build is a soft-resolve: try the standalone
    ``copilot``-with-``-p``-prompt form first, fall through to
    ``gh copilot suggest`` only at launch time if the operator
    explicitly opts in (the harness defaults to the canonical
    standalone form per 089f).

    v1.5.7 100: ``parameters`` (when non-empty) is spliced
    verbatim into the flags region — after the standard flags and
    before the ``-p <prompt>`` pair — so copilot reads them as
    additional flags without disturbing the argv prompt route.
    """
    command = ["copilot", "--model", model, "--allow-all-tools",
                *(parameters or []), "-p", prompt]
    return command


def _cursor_command(model: str,
                     parameters: "list[str] | None" = None,
                     ) -> "list[str]":
    """v1.5.7 095 Phase 5: cursor adapter. Mirrors
    ``bin.run_playbook.command_for_runner`` for ``runner=cursor``:
    ``cursor agent --print --force`` reads the prompt from stdin
    (cursor-cli 3.1+; do NOT pass ``-`` as a positional — cursor
    treats it as the literal prompt content, unlike codex).
    ``--force`` (alias ``--yolo``) skips confirmation prompts
    for unattended runs.

    Caller must set ``stdin_input=prompt`` on the LaunchSpec.

    v1.5.7 100: ``parameters`` (when non-empty) is appended
    verbatim — cursor takes the prompt on stdin, so extra flags
    can safely live at the end of the flag region without
    disturbing prompt routing.
    """
    command = ["cursor", "agent", "--print", "--force"]
    if model:
        command.extend(["--model", model])
    if parameters:
        command.extend(parameters)
    return command


def _mode_b_command(runner: Runner, target_dir: Path,
                     model: str) -> "list[str]":
    """v1.5.7 095 Phase 5: Mode B reuses ``bin.run_playbook`` as
    the canonical harness (per design §G — "run_playbook.py IS
    the Mode B harness"). The shell-out invocation is:

        python3 -m bin.run_playbook --<runner> --model <model> \
            <target_dir>

    The runner flag matches the run_playbook arg parser
    (``--claude``/``--copilot``/``--codex``/``--cursor``);
    ``--model`` is the per-runner model override. The harness
    captures stream output the same way as Mode A; the difference
    is just *who drives the phases* — Mode A is the CLI agent,
    Mode B is the run_playbook harness.
    """
    flag = {
        Runner.CLAUDE: "--claude",
        Runner.CODEX: "--codex",
        Runner.COPILOT: "--copilot",
        Runner.CURSOR: "--cursor",
    }[runner]
    return [
        sys.executable, "-m", "bin.run_playbook",
        flag, "--model", model, str(target_dir),
    ]


def _needs_stdin_prompt(runner: Runner) -> bool:
    """codex + cursor read the prompt on stdin (codex via the
    ``-`` sentinel; cursor implicitly when no positional arg).
    claude + copilot take the prompt on argv.

    Mode B is the run_playbook harness — it consumes the prompt
    internally and doesn't need a stdin pipe from the harness.
    """
    return runner in (Runner.CODEX, Runner.CURSOR)


def _command_for_axes(axes: RunAxes, prompt: str,
                       target_dir: "Path | None" = None,
                       parameters: "list[str] | None" = None,
                       ) -> "list[str]":
    """v1.5.7 095 Phase 5: dispatch to the right adapter.

    Mode A: per-runner CLI invocation (claude/codex/copilot/
    cursor) with the prompt passed on argv (claude/copilot) or
    stdin (codex/cursor — caller routes via
    ``_needs_stdin_prompt``).

    Mode B: ``python3 -m bin.run_playbook --<runner> --model
    <model> <target_dir>`` — the run_playbook harness drives the
    phases.

    v1.5.7 100: ``parameters`` (when non-empty) is forwarded to
    the per-runner Mode A builder which splices the tokens at
    the runner-appropriate position. Mode B ignores parameters —
    run_playbook owns the CLI for whichever runner it's driving;
    operator-specific overrides land via run_playbook's own
    flags.
    """
    if axes.runner not in _SUPPORTED_RUNNERS:
        raise RunnerError(
            f"runner {axes.runner.value!r} is not in the supported "
            f"set {sorted(r.value for r in _SUPPORTED_RUNNERS)}"
        )
    if axes.install_channel not in _SUPPORTED_CHANNELS:
        raise RunnerError(
            f"install_channel {axes.install_channel.value!r} is "
            f"not yet supported (clone only; local-wheel/local-tgz "
            f"land in Phase 2, registry in Phase 6)."
        )
    if axes.mode == Mode.B:
        if target_dir is None:
            raise RunnerError(
                "Mode B requires target_dir (run_playbook drives "
                "the phases against the target tree)"
            )
        return _mode_b_command(axes.runner, target_dir, axes.model)
    # Mode A — per-runner Mode A invocation.
    if axes.runner == Runner.CLAUDE:
        return _claude_command(axes.model, prompt, axes.thinking,
                                parameters=parameters)
    if axes.runner == Runner.CODEX:
        return _codex_command(axes.model, parameters=parameters)
    if axes.runner == Runner.COPILOT:
        return _copilot_command(axes.model, prompt,
                                 parameters=parameters)
    if axes.runner == Runner.CURSOR:
        return _cursor_command(axes.model, parameters=parameters)
    # Unreachable given the _SUPPORTED_RUNNERS guard above.
    raise RunnerError(f"runner {axes.runner!r} fell through dispatch")


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
    cmd = _command_for_axes(spec.axes, spec.prompt,
                              target_dir=spec.target_dir,
                              parameters=spec.parameters)
    cli_command = " ".join(cmd)
    # v1.5.7 095 Phase 5: codex and cursor read the prompt on
    # stdin (codex: via the ``-`` sentinel; cursor: implicitly
    # when no positional arg). claude+copilot take it on argv.
    # Mode B (run_playbook) handles its own prompt internally.
    needs_stdin = (
        spec.axes.mode != Mode.B
        and _needs_stdin_prompt(spec.axes.runner)
    )

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
            stdin=(subprocess.PIPE if needs_stdin
                    else subprocess.DEVNULL),
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
        # codex/cursor: write the prompt to stdin then close it.
        if needs_stdin and proc.stdin is not None:
            try:
                proc.stdin.write(spec.prompt.encode("utf-8"))
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                # Subprocess died before we wrote the prompt —
                # the wait() below will surface the exit code +
                # FAILED terminal state.
                pass

        terminal_state: TerminalState
        exit_code: int
        try:
            exit_code = proc.wait(timeout=spec.max_duration_s)
            # Per design §6 / lifecycle: COMPLETED requires exit-0 AND a
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
    # Exposed for tests + downstream reuse:
    "_claude_command",
    "_codex_command",
    "_copilot_command",
    "_cursor_command",
    "_mode_b_command",
    "_command_for_axes",
    "_needs_stdin_prompt",
    "_vendor_env_for",
    "_kill_process_tree",
]
