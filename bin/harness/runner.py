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


# Runners supported by the current adapter implementation. Each
# entry has a per-CLI command builder (`_<runner>_command`)
# below; adding a runner is a 091-style adapter addition.
#
# v1.5.7 104: install_channel guard removed. The launch command
# is channel-independent — `prepare` already installed the skill
# into the target before launch_run runs; the runner just spawns
# the AI-CLI against the installed target. The stale Phase-1
# `_SUPPORTED_CHANNELS = {clone}` guard wrongly blocked
# local-wheel / local-tgz / registry channels on the first live
# run (it survived 091-103 only because every test before 104
# used the clone channel).
_SUPPORTED_RUNNERS = {Runner.CLAUDE, Runner.CODEX,
                      Runner.COPILOT, Runner.CURSOR}


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


@dataclass
class SpawnResult:
    """v1.5.7 108: returned from ``launch_run_async`` — the
    spawn-only half of the split. Carries the detached child's
    PID + the bookkeeping the eventual ``collect_one_process``
    (or in-process reaper) needs to write a terminal
    ``status.json`` and produce a ``LaunchResult``.

    The detached child's stdout/stderr have already been
    redirected to ``stream_path``; the spawning process
    closes its own end of the pipe so a later collector in a
    different process tree never needs the file handle."""
    pid: int
    started_at: str
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


def _mode_b_agent_marker_vars() -> "frozenset[str]":
    """v1.5.7 115: return the canonical set of agent-marker
    env-var names that ``run_playbook._detect_agent_context``
    checks. Imported lazily from ``bin.run_playbook`` so the
    list stays in sync as new agents are added — hardcoding
    a divergent copy would silently break when the canonical
    list grows.

    The lazy import avoids paying run_playbook's full
    module-load cost on harness import (run_playbook pulls
    benchmark_lib, archive_lib, copilot_resolver, … on
    module load). We pay it once on the first Mode B
    launch.
    """
    from bin.run_playbook import _AGENT_CONTEXT_SIGNALS
    return frozenset(_AGENT_CONTEXT_SIGNALS.keys())


def _sanitize_mode_b_env(
        env: "dict[str, str]") -> "dict[str, str]":
    """v1.5.7 115: build the Mode B subprocess env so that
    ``run_playbook``'s ``_detect_agent_context`` guard (the
    "don't let an agent delegate to me" A-22 structural
    defense) does NOT refuse the harness's invocation.

    The harness IS a legitimate operator (Mode B per
    design §G — "run_playbook.py IS the Mode B harness"). It
    captures run_playbook's full stdout to stream.ndjson;
    run_playbook spawns FRESH per-phase CLIs (which set their
    OWN agent markers) — exactly the pattern the guard is
    meant to ALLOW, not the interactive-agent-delegation it
    blocks. But the harness inherits the operator's shell env,
    which may include ``CLAUDECODE=1`` (Claude Code session)
    or any of the other agent markers, and ``_vendor_env_for``
    actively SETS one of those markers (e.g. ``CLAUDECODE=1``
    for ``Runner.CLAUDE`` so the gate's runner-detector finds
    it). So without sanitization the guard trips and Mode B
    refuses with the agent-session ERROR before ever reaching
    phase work — exactly what the AUP-experiment's 1272-byte
    Mode B streams showed after 114 fixed the import gap.

    The fix:

    1. **Strip the agent-marker vars** (the canonical list
       lives in ``run_playbook._AGENT_CONTEXT_SIGNALS``; see
       ``_mode_b_agent_marker_vars``). Stripping them
       satisfies ``_detect_agent_context`` (it returns
       ``None``) and the guard exits silently.

    2. **Set ``QPB_OPERATOR_NON_TTY_OVERRIDE=1``** — the
       documented CI escape hatch (085 / docs/CI_INTEGRATION.md).
       It's a no-op when ``--operator-invoked`` isn't on the
       argv (current harness shape), but adding it now means
       future invocations that pass ``--operator-invoked``
       work without env-thrashing.

    Mode-B-only: do NOT call this for Mode A.
    ``_vendor_env_for`` SETS the agent marker on purpose for
    Mode A (the gate uses it to detect which runner produced
    the gate-report); stripping it would break gate provenance.

    Safe: run_playbook spawns its own fresh per-phase CLI
    subprocesses (claude / codex / copilot / cursor), each of
    which sets its OWN agent marker. Stripping these from
    run_playbook's own env doesn't affect the per-phase
    subprocess envs.
    """
    sanitized = dict(env)
    for var in _mode_b_agent_marker_vars():
        sanitized.pop(var, None)
    sanitized["QPB_OPERATOR_NON_TTY_OVERRIDE"] = "1"
    return sanitized


def _resolve_run_playbook_script(
        target_dir: "Path | None" = None) -> Path:
    """v1.5.7 114: locate ``bin/run_playbook.py`` by its
    absolute path in the QPB clone, then invoke it as a
    direct script. Returns the absolute path to the script.

    **Design note (worth documenting; the 114 instruction's
    wording is incorrect on this point):** the install bundle
    DELIBERATELY excludes ``bin/run_playbook.py`` —
    ``install_skill.py:397-398`` comments: "minus
    `bin.run_playbook` (the Mode-B harness invoked from the
    QPB clone, NOT from install_root)". So we cannot find
    run_playbook.py at ``<target>/.claude/skills/.../bin/``
    (the 114 instruction assumed it lives there; it doesn't,
    by design).

    What we CAN do, and what fixes the AUP-experiment's
    "No module named bin.run_playbook" failure, is invoke
    run_playbook.py by its absolute path inside the QPB
    clone — the same clone the harness runs from. The
    runner.py module file (this file) lives at
    ``<qpb_clone>/bin/harness/runner.py``, so the script is
    reliably at ``<qpb_clone>/bin/run_playbook.py``
    (``__file__.parents[2] / "bin" / "run_playbook.py"``).

    run_playbook.py injects QPB root into ``sys.path`` when
    invoked as a direct script (its module header:
    ``sys.path.insert(0, str(_Path(__file__).resolve().parent
    .parent))``), so its sibling imports (``benchmark_lib``,
    ``archive_lib``, ``copilot_resolver``) resolve regardless
    of the subprocess's cwd. This is the ESSENTIAL invariant
    the 114 instruction calls out: "the subprocess MUST be
    able to import run_playbook's siblings (no `No module
    named …`)."

    Pre-114 the launch hardcoded ``python3 -m bin.run_playbook``,
    which only resolves when ``cwd`` is the QPB clone root.
    ``launch_run_async`` uses ``cwd=target_dir`` (the channel-
    installed target) per the lifecycle contract, so the ``-m``
    form died immediately with ``No module named bin.run_playbook``
    — the 79-byte streams the AUP experiment surfaced on the
    first Mode B run.

    The ``target_dir`` parameter is accepted for forward
    compatibility (callers pass it through 095/106 contracts)
    but ignored: run_playbook is the same script regardless of
    which target it drives.
    """
    del target_dir  # unused; see docstring
    qpb_clone_root = Path(__file__).resolve().parents[2]
    script_path = qpb_clone_root / "bin" / "run_playbook.py"
    if not script_path.is_file():
        raise RunnerError(
            f"114: cannot locate `bin/run_playbook.py` "
            f"relative to runner.py — expected at {script_path}. "
            "The harness must run from a QPB clone (the install "
            "bundle excludes run_playbook.py — see "
            "`install_skill.py:397-398`)."
        )
    return script_path


def _mode_b_command(runner: Runner, target_dir: Path,
                     model: str,
                     parameters: "list[str] | None" = None,
                     ) -> "list[str]":
    """v1.5.7 095 Phase 5: Mode B reuses ``bin.run_playbook`` as
    the canonical harness (per design §G — "run_playbook.py IS
    the Mode B harness").

    v1.5.7 114: invocation switched from the bare ``-m
    bin.run_playbook`` to the absolute-script-path form:

        python3 <qpb_clone>/bin/run_playbook.py \
            --<runner> --model <model> \
            [<parameters...>] <target_dir>

    Pre-114 used ``python3 -m bin.run_playbook …``, which only
    resolves when the working directory contains ``bin/`` as an
    importable package — i.e. when launched from the QPB clone
    root. ``launch_run_async`` launches with ``cwd=target_dir``
    (the channel-installed target), so the ``-m`` form died
    immediately with ``No module named bin.run_playbook`` on
    the first live Mode B run (AUP experiment, three 79-byte
    streams). The absolute-path script form sidesteps that
    failure mode: run_playbook's own module header injects QPB
    root into ``sys.path`` so its sibling imports
    (``benchmark_lib``, ``archive_lib``, ``copilot_resolver``)
    resolve regardless of cwd. See
    ``_resolve_run_playbook_script`` for why we use the
    QPB-clone path rather than the install path the 114
    instruction text implied (the install bundle deliberately
    excludes run_playbook.py).

    The runner flag matches the run_playbook arg parser
    (``--claude``/``--copilot``/``--codex``/``--cursor``);
    ``--model`` is the per-runner model override. The harness
    captures stream output the same way as Mode A; the
    difference is just *who drives the phases* — Mode A is the
    CLI agent, Mode B is the run_playbook harness.

    v1.5.7 106: ``parameters`` in Mode B is spliced into the
    ``run_playbook`` argv (before the trailing ``<target_dir>``
    positional). This lets a plan select phases in Mode B —
    e.g. ``parameters=["--phase", "3"]``. In Mode A the same
    field routes to the runner CLI (per 100); the contract is
    "``parameters`` routes to whichever subprocess this run
    launches".
    """
    flag = {
        Runner.CLAUDE: "--claude",
        Runner.CODEX: "--codex",
        Runner.COPILOT: "--copilot",
        Runner.CURSOR: "--cursor",
    }[runner]
    script_path = _resolve_run_playbook_script(target_dir)
    return [
        sys.executable, str(script_path),
        flag, "--model", model,
        *(parameters or []),
        str(target_dir),
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
    # v1.5.7 104: install_channel does NOT affect the launch
    # argv (prepare already installed the skill); the old
    # clone-only guard here wrongly blocked local/registry
    # channels on the first live run.
    if axes.mode == Mode.B:
        if target_dir is None:
            raise RunnerError(
                "Mode B requires target_dir (run_playbook drives "
                "the phases against the target tree)"
            )
        # v1.5.7 106: forward `parameters` so plan runs can
        # select phases (e.g. `--phase 3`) in Mode B.
        return _mode_b_command(axes.runner, target_dir, axes.model,
                                parameters=parameters)
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


def launch_run_async(spec: LaunchSpec) -> SpawnResult:
    """v1.5.7 108: spawn the detached AI-CLI child and RETURN
    IMMEDIATELY (no wait). Writes the RUNNING ``status.json``
    so an observer (the 110 status layer / 111 TUI / a later
    collector) can see the run is live before it produces
    stream output.

    Use ``collect_one_process(spec, spawn)`` (same process) or
    the orphan-polling pattern in ``plan_runner.collect_
    harness_run`` (after run_plan returns + the collector runs
    detached) to drive the wait + terminal status. The split
    is the 108 anti-SIGTTIN fix: a long-lived foreground
    parent ``wait()``ing on the AI-CLI is what got suspended
    on the first live full-pipeline run.
    """
    spec.run_dir.mkdir(parents=True, exist_ok=True)
    cmd = _command_for_axes(spec.axes, spec.prompt,
                              target_dir=spec.target_dir,
                              parameters=spec.parameters)
    cli_command = " ".join(cmd)
    needs_stdin = (
        spec.axes.mode != Mode.B
        and _needs_stdin_prompt(spec.axes.runner)
    )
    env = os.environ.copy()
    env.update(_vendor_env_for(spec.axes.runner))
    if spec.extra_env:
        env.update(spec.extra_env)
    # v1.5.7 115: Mode B sanitization — strip agent-marker env
    # vars + set QPB_OPERATOR_NON_TTY_OVERRIDE=1 so
    # run_playbook's _detect_agent_context guard doesn't
    # refuse the harness's launch. See _sanitize_mode_b_env
    # for the full rationale (the harness is a legitimate
    # operator; the guard's A-22 structural defense is meant
    # to block interactive-agent-delegation, not the
    # harness's pipe-captured-stdout / fresh-per-phase-CLI
    # pattern). Mode A keeps the agent marker (the gate uses
    # it to detect which runner produced the gate-report).
    if spec.axes.mode == Mode.B:
        env = _sanitize_mode_b_env(env)
    env_snapshot = {
        k: v for k, v in env.items()
        if (k in ("CLAUDECODE", "CODEX_THREAD_ID",
                   "COPILOT_AGENT_SESSION_ID", "CURSOR",
                   "QPB_OPERATOR_NON_TTY_OVERRIDE")
             or (spec.extra_env and k in spec.extra_env))
    }
    stream_path = spec.run_dir / "stream.ndjson"
    started_at = _utc_now_iso()
    # Pre-write so a watcher sees RUNNING even before the
    # child produces output.
    _write_status(spec.run_dir, {
        "state": "RUNNING",
        "pid": None,
        "started_at": started_at,
        "heartbeat": started_at,
        "exit_code": None,
        "terminal_state": None,
    })
    # Open the stream file, spawn the child with its stdout
    # dup'd to the file fd, then CLOSE the parent's handle so
    # the child keeps writing via the dup'd fd even after the
    # parent process exits (108 anti-SIGTTIN — the parent must
    # not retain a long-lived handle that blocks reaping).
    stream_fp = open(stream_path, "wb")
    try:
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
    finally:
        stream_fp.close()
    _write_status(spec.run_dir, {
        "state": "RUNNING",
        "pid": proc.pid,
        "started_at": started_at,
        "heartbeat": started_at,
        "exit_code": None,
        "terminal_state": None,
    })
    if needs_stdin and proc.stdin is not None:
        try:
            proc.stdin.write(spec.prompt.encode("utf-8"))
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
    return SpawnResult(
        pid=proc.pid,
        started_at=started_at,
        cli_command=cli_command,
        cwd=str(spec.target_dir),
        env_snapshot=env_snapshot,
        stream_path=stream_path,
    )


def _classify_stream_terminal(
        stream_path: Path,
) -> "tuple[TerminalState | None, str]":
    """v1.5.7 113: classify a run's terminal state from the
    LAST ``result`` event in ``stream.ndjson``.

    Returns ``(terminal_state, reason)``:
      * ``(TerminalState.BLOCKED, reason)`` when the last
        ``result`` event has ``is_error: true`` (AUP / API
        error). ``reason`` is the result body text — the
        operator-facing receipt of WHY the run was blocked.
      * ``(TerminalState.COMPLETED, "")`` when the last
        ``result`` event has ``is_error: false``. A clean
        Claude ``result`` event is the authoritative "the
        run finished its turn" signal — pre-113, the 108
        orphan-collector REQUIRED ``gate-report-latest.json``
        for COMPLETED, but the AUP experiment showed that
        two clean Mode A gson runs produced full ``quality/``
        trees (all 6 phases) WITHOUT that file (the
        report-writer step ran inconsistently), and the
        artifact-only inference mislabeled them FAILED.
      * ``(None, "")`` when the stream has no parseable
        ``result`` event — inconclusive. Callers fall back to
        the artifact-based heuristic. Notably, Mode B
        (``run_playbook``) streams do NOT emit Claude's
        ``result`` envelope, so the classifier is a no-op
        there and the artifact heuristic still drives the
        decision.

    Robust to: missing file, malformed JSON lines (skipped),
    multiple ``result`` events (LAST wins — a recovered run
    that ended cleanly is NOT misclassified as BLOCKED).
    """
    if not stream_path.is_file():
        return (None, "")
    try:
        text = stream_path.read_text(
            encoding="utf-8", errors="ignore"
        )
    except OSError:
        return (None, "")
    last_result: "dict | None" = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("type") == "result":
            last_result = obj
    if last_result is None:
        return (None, "")
    if last_result.get("is_error"):
        reason = last_result.get("result", "")
        if not isinstance(reason, str):
            reason = json.dumps(reason)
        return (TerminalState.BLOCKED, reason)
    return (TerminalState.COMPLETED, "")


def _stream_ended_in_api_error(
        stream_path: Path) -> "tuple[bool, str]":
    """v1.5.7 112: detect an AUP / API-error termination by
    reading the LAST ``result`` event from ``stream.ndjson``.

    Claude Code's AUP refusal looks like:
      ``{"type":"result", "subtype":"success",
         "is_error":true,
         "result":"API Error: Claude Code is unable to respond
                   to this request, which appears to violate
                   our Usage Policy (…/aup) …"}``

    The robust key is ``is_error:true`` — NOT ``subtype``
    (AUP refusals report ``subtype:"success"`` with
    ``is_error:true``). The process also exits 0, so the
    pre-112 ``COMPLETED if exit_code == 0`` logic mis-marked
    AUP-blocked runs COMPLETED, which then graded the
    partial ``quality/`` tree as substantive failures (first
    live run showed "18 substantive fails" from this).

    Returns ``(blocked, reason)``.

    v1.5.7 113: thin wrapper over ``_classify_stream_terminal``
    that preserves the (bool, reason) shape callers of the 112
    API depend on. New code should use
    ``_classify_stream_terminal`` directly to also get the
    COMPLETED signal (a clean ``is_error:false`` result event).
    """
    state, reason = _classify_stream_terminal(stream_path)
    return (state == TerminalState.BLOCKED, reason)


def collect_one_process(spec: LaunchSpec,
                         spawn: SpawnResult) -> LaunchResult:
    """v1.5.7 108: in-process collector — waits for a child
    spawned in THIS process via the equivalent of
    ``subprocess.Popen``. Used by the backward-compatible
    ``launch_run`` (which does spawn + wait inline) and by
    tests that stub the spawn.

    Cross-process collection (the new ``run_plan`` detached
    flow) uses the orphan-polling helper in ``plan_runner``
    instead — that helper can't ``waitpid`` (orphans), so it
    polls ``os.kill(pid, 0)`` for liveness and infers the
    terminal state from produced artifacts.

    This function expects the caller to still hold the Popen
    handle; we don't — so we use ``os.waitpid`` to reap our
    own child by PID, then write the terminal status.

    Honors ``spec.max_duration_s``: if the process is still
    alive past the budget, kill the process group and record
    ``TIMED_OUT``.
    """
    # waitpid with WNOHANG poll until budget exhausted.
    started = _utc_now_iso()
    deadline = time.monotonic() + max(0.0, spec.max_duration_s)
    exit_code = -1
    terminal_state = TerminalState.FAILED
    timed_out = False
    while True:
        try:
            wpid, status = os.waitpid(spawn.pid, os.WNOHANG)
        except ChildProcessError:
            # Not our child (or already reaped). Best-effort.
            wpid, status = (spawn.pid, 0)
        if wpid != 0:
            # Process exited.
            if os.WIFEXITED(status):
                exit_code = os.WEXITSTATUS(status)
            elif os.WIFSIGNALED(status):
                exit_code = -os.WTERMSIG(status)
            else:
                exit_code = -1
            terminal_state = (TerminalState.COMPLETED
                               if exit_code == 0
                               else TerminalState.FAILED)
            break
        if time.monotonic() >= deadline:
            timed_out = True
            _kill_process_tree(spawn.pid)
            # Reap the now-defunct process.
            try:
                _wpid, status = os.waitpid(spawn.pid, 0)
                if os.WIFEXITED(status):
                    exit_code = os.WEXITSTATUS(status)
                elif os.WIFSIGNALED(status):
                    exit_code = -os.WTERMSIG(status)
            except ChildProcessError:
                pass
            terminal_state = TerminalState.TIMED_OUT
            break
        time.sleep(0.05)
    # v1.5.7 112: AUP / API-error refusal overrides exit-code
    # logic — Claude Code's AUP refusal exits 0 with a
    # `result` event carrying `is_error:true`, so the
    # exit-code-only logic above mis-marked it COMPLETED
    # (which then graded the partial quality/ tree as
    # substantive failures). TIMED_OUT still wins (a kill is
    # a kill, regardless of stream content); otherwise an
    # API-error stream ⇒ BLOCKED.
    terminal_reason = ""
    if terminal_state != TerminalState.TIMED_OUT:
        blocked, reason = _stream_ended_in_api_error(
            spawn.stream_path
        )
        if blocked:
            terminal_state = TerminalState.BLOCKED
            terminal_reason = reason
    ended_at = _utc_now_iso()
    _write_status(spec.run_dir, {
        "state": "DONE",
        "pid": spawn.pid,
        "started_at": spawn.started_at,
        "heartbeat": ended_at,
        "ended_at": ended_at,
        "exit_code": exit_code,
        "terminal_state": terminal_state.value,
        # v1.5.7 112: record the AUP / API-error body when
        # we hit the BLOCKED path so the operator can see
        # WHY a run was marked N/A. Empty for non-BLOCKED.
        "terminal_reason": terminal_reason,
    })
    return LaunchResult(
        pid=spawn.pid,
        started_at=spawn.started_at,
        ended_at=ended_at,
        exit_code=exit_code,
        terminal_state=terminal_state,
        cli_command=spawn.cli_command,
        cwd=spawn.cwd,
        env_snapshot=spawn.env_snapshot,
        stream_path=spawn.stream_path,
    )


def launch_run(spec: LaunchSpec) -> LaunchResult:
    """Launch one run end-to-end. Detached subprocess, stream
    capture, max-duration timeout, status file written.

    v1.5.7 108: now a thin wrapper composing ``launch_run_async``
    + ``collect_one_process``. Existing callers (the
    `bin.qpb_harness run` single-run entry, tests that patch
    `launch_run`) keep the synchronous semantics; the new
    `run_plan` detached flow uses `launch_run_async` directly
    and a different collector (orphan polling) per 108.
    """
    spawn = launch_run_async(spec)
    return collect_one_process(spec, spawn)


__all__ = [
    "RunnerError",
    "LaunchSpec",
    "LaunchResult",
    "SpawnResult",
    "launch_run",
    "launch_run_async",
    "collect_one_process",
    "_stream_ended_in_api_error",
    "_classify_stream_terminal",
    # Exposed for tests + downstream reuse:
    "_claude_command",
    "_codex_command",
    "_copilot_command",
    "_cursor_command",
    "_mode_b_command",
    "_resolve_run_playbook_script",
    "_sanitize_mode_b_env",
    "_mode_b_agent_marker_vars",
    "_command_for_axes",
    "_needs_stdin_prompt",
    "_vendor_env_for",
    "_kill_process_tree",
]
