"""runners.py — LLM runner abstraction for skill_derivation passes.

Four concrete runners ship: ClaudeRunner (subprocess `claude --print
--model sonnet`), CopilotRunner (subprocess `copilot -p --model
<name>` via :mod:`bin.copilot_resolver`, with deprecated
``gh copilot --prompt`` as grace-period fallback per 089f),
CodexRunner (subprocess `codex exec --full-auto [-m <model>]`,
codex-cli 0.125+), and CursorRunner (subprocess `cursor agent
--print --force [--model <model>]`, cursor-cli 3.1+). Tests use
MockRunner from test_skill_derivation_pass_a.py.

Default to claude-print for Phase 3 self-audit runs because Phase 3
fires 60-100+ LLM calls per run and the Copilot CLI's weekly quota
has been under pressure -- defaulting to claude routes Phase 3 cost
to Anthropic's quota.

The CLI flag (`--runner claude|copilot|codex|cursor`) follows the
existing bin/run_playbook.py convention; do not introduce a parallel
env-var scheme.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol

from bin import copilot_resolver


def _resolve_runner_command(argv: "list[str]") -> "list[str]":
    """Resolve a bare-name AI CLI invocation to its full path (W2,
    addendum r3 §4.2).

    Deliberate copy of bin/run_playbook.py:_resolve_runner_command
    (instruction-078 Task 3 explicitly sanctions a local copy over a
    cross-module import: importing the large run_playbook module from
    this lightweight runners module is awkward and import-order
    fragile). Keep the two byte-identical in body; both are pinned by
    bin/tests/test_runner_command_shim_resolution.py.

    On Windows, AI CLIs are typically `.cmd`/`.bat` shims;
    `subprocess.run` without `shell=True` raises FileNotFoundError
    because CreateProcess only auto-resolves `.exe`. `shutil.which`
    walks PATHEXT, so it returns the shim's full path. On Unix this is
    effectively a no-op. Unresolvable -> bare argv (preserves the
    existing FileNotFoundError surface). Resolution-only — does NOT
    address stdin-through-`.cmd` (addendum §4.3 / §8 smoke test).
    """
    if not argv:
        return argv
    resolved = shutil.which(argv[0])
    if resolved is None:
        return argv
    return [resolved] + list(argv[1:])


@dataclass
class RunnerResult:
    stdout: str
    stderr: str
    elapsed_ms: int
    returncode: int


class LLMRunner(Protocol):
    """Minimal contract: turn a prompt into a stdout response.

    Implementations are responsible for measuring elapsed time and
    capturing stderr for debugging.
    """

    def run(self, prompt: str) -> RunnerResult:
        ...


@dataclass
class ClaudeRunner:
    """Subprocess wrapper for `claude --print --model <model>`.

    Sends the prompt on stdin to avoid command-line length limits on
    long section bodies + recovery preamble + output schema.
    """

    model: str = "sonnet"
    timeout_seconds: int = 600  # 10 minutes per call; long enough for substantive sections

    def run(self, prompt: str) -> RunnerResult:
        import time
        start = time.monotonic()
        try:
            result = subprocess.run(
                _resolve_runner_command(
                    ["claude", "--print", "--model", self.model]),
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return RunnerResult(
                stdout=result.stdout,
                stderr=result.stderr,
                elapsed_ms=elapsed_ms,
                returncode=result.returncode,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return RunnerResult(
                stdout="",
                stderr=f"timeout after {self.timeout_seconds}s",
                elapsed_ms=elapsed_ms,
                returncode=124,
            )


@dataclass
class CopilotRunner:
    """Subprocess wrapper for the GitHub Copilot CLI.

    Resolves to ``copilot -p <text> --model <model>`` (the new
    standalone CLI) when on PATH, falling back to
    ``gh copilot -p <text> --model <model>`` (the deprecated
    extension) during the grace period (v1.5.7 089f; GitHub
    deprecated ``gh copilot`` on 2025-10-25). Resolution lives in
    :mod:`bin.copilot_resolver`.

    Burns Copilot CLI weekly quota; opt in explicitly via --runner
    copilot. Default Phase 3 runs use ClaudeRunner.

    History note (BUG-001, pre-089f): the prior implementation used
    a bare ``--prompt`` flag (no positional value) and piped the
    prompt body on stdin via ``input=prompt`` — relying on
    ``gh copilot``'s tolerance of ``--prompt`` without a value to
    avoid ARG_MAX truncation on long section bodies. The new
    ``copilot`` CLI requires ``-p <text>`` (per
    ``copilot --help``), so this runner now passes the prompt on
    argv — the same shape the Mode B reviewer hot path
    (``bin/run_playbook.py:command_for_runner``) has always used.
    Modern ARG_MAX (>1 MB on macOS and Linux, ~32 KB on Windows)
    accommodates skill-derivation prompts. ``input=prompt`` is
    retained as a defensive harmless redundancy: the CLI takes
    argv; the stdin pipe is ignored.
    """

    model: str = "claude-sonnet-4.6"
    timeout_seconds: int = 600

    def run(self, prompt: str) -> RunnerResult:
        import time
        start = time.monotonic()
        try:
            # v1.5.7 089f: resolver picks the available CLI and
            # builds the argv (prompt on argv per the new CLI's
            # required `-p <text>` shape; see docstring for the
            # BUG-001 history). input=prompt below is the harmless-
            # redundancy retention noted in the docstring.
            argv = copilot_resolver.resolve_copilot_command(
                prompt, self.model)
            result = subprocess.run(
                _resolve_runner_command(argv),
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return RunnerResult(
                stdout=result.stdout,
                stderr=result.stderr,
                elapsed_ms=elapsed_ms,
                returncode=result.returncode,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return RunnerResult(
                stdout="",
                stderr=f"timeout after {self.timeout_seconds}s",
                elapsed_ms=elapsed_ms,
                returncode=124,
            )


@dataclass
class CodexRunner:
    """Subprocess wrapper for `codex exec --full-auto [-m <model>]`.

    Codex CLI's non-interactive mode reads instructions from stdin
    when no positional prompt is given (per `codex exec --help` on
    codex-cli 0.125+). `--full-auto` is the low-friction sandboxed
    automatic-execution mode (the codex equivalent of the Copilot
    CLI's `--allow-all` / `--yolo`). We do NOT enable
    `--dangerously-bypass-approvals-and-sandbox` by default; only
    enable that if a future caller needs full sandbox bypass.

    The default model is empty (the empty string) — codex picks
    its own default from `~/.codex/config.toml`. An explicit value
    overrides via `-m <model>`.
    """

    model: str = ""
    timeout_seconds: int = 600

    def run(self, prompt: str) -> RunnerResult:
        import time
        argv = _resolve_runner_command(["codex", "exec", "--full-auto"])
        if self.model:
            argv.extend(["-m", self.model])
        start = time.monotonic()
        try:
            result = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return RunnerResult(
                stdout=result.stdout,
                stderr=result.stderr,
                elapsed_ms=elapsed_ms,
                returncode=result.returncode,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return RunnerResult(
                stdout="",
                stderr=f"timeout after {self.timeout_seconds}s",
                elapsed_ms=elapsed_ms,
                returncode=124,
            )


@dataclass
class CursorRunner:
    """Subprocess wrapper for `cursor agent --print --force [--model <model>]`.

    v1.5.4 F-1 (Bootstrap_Findings 2026-04-30): Cursor CLI is the
    fourth sibling alongside claude/copilot/codex. The `cursor agent`
    subcommand runs the Cursor agent in a terminal; `--print` makes
    it non-interactive (script-friendly) and gives it access to all
    tools including write+shell. `--force` (alias `--yolo`) skips
    confirmation prompts so the run is fully unattended — required
    for batch automation.

    Cursor reads the prompt on stdin ONLY when no positional arg is
    given. Unlike codex 0.125+, cursor 3.1.10 does NOT honor `-` as
    a stdin sentinel — it treats `-` as the literal prompt content.
    We therefore pass NO positional arg and pipe the prompt via
    `subprocess.run(input=prompt)`. (Verified post-bootstrap smoke
    test: `cursor agent --print --force -` aborts with "your last
    message was only a hyphen, so there isn't a clear task yet";
    `echo PROMPT | cursor agent --print --force` works correctly.)

    The default model is empty (the empty string) — cursor picks its
    own default per its account/config. An explicit value overrides
    via `--model <model>`.
    """

    model: str = ""
    timeout_seconds: int = 600

    def run(self, prompt: str) -> RunnerResult:
        import time
        argv = _resolve_runner_command(
            ["cursor", "agent", "--print", "--force"])
        if self.model:
            argv.extend(["--model", self.model])
        start = time.monotonic()
        try:
            result = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return RunnerResult(
                stdout=result.stdout,
                stderr=result.stderr,
                elapsed_ms=elapsed_ms,
                returncode=result.returncode,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return RunnerResult(
                stdout="",
                stderr=f"timeout after {self.timeout_seconds}s",
                elapsed_ms=elapsed_ms,
                returncode=124,
            )


def make_runner(name: str, *, model: str | None = None) -> LLMRunner:
    """Factory. CLI flag value -> runner instance.

    Phase 5 Stage 0 (DQ-5-1): the optional `model` keyword overrides
    the runner's default model. None preserves the runner's built-in
    default; an explicit string ('sonnet', 'opus', etc.) routes to
    the corresponding subprocess invocation.
    """
    if name == "claude":
        return ClaudeRunner(model=model) if model else ClaudeRunner()
    if name == "copilot":
        return CopilotRunner(model=model) if model else CopilotRunner()
    if name == "codex":
        return CodexRunner(model=model) if model else CodexRunner()
    if name == "cursor":
        return CursorRunner(model=model) if model else CursorRunner()
    raise ValueError(
        f"unknown runner {name!r}; valid values: claude, copilot, codex, cursor"
    )
