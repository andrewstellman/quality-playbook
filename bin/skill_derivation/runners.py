"""runners.py — LLM runner abstraction for skill_derivation passes.

Four concrete runners ship: ClaudeRunner (subprocess `claude --print
--model sonnet`), CopilotRunner (subprocess `gh copilot --prompt
--model claude-sonnet-4.6`), CodexRunner (subprocess `codex exec
--full-auto [-m <model>]`, codex-cli 0.125+), and CursorRunner
(subprocess `cursor agent --print --force [--model <model>]`,
cursor-cli 3.1+). Tests use MockRunner from
test_skill_derivation_pass_a.py.

Default to claude-print for Phase 3 self-audit runs because Phase 3
fires 60-100+ LLM calls per run and gh-copilot's weekly quota has
been under pressure -- defaulting to claude routes Phase 3 cost to
Anthropic's quota.

The CLI flag (`--runner claude|copilot|codex|cursor`) follows the
existing bin/run_playbook.py convention; do not introduce a parallel
env-var scheme.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Protocol


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
                ["claude", "--print", "--model", self.model],
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
    """Subprocess wrapper for `gh copilot --prompt --model <model>`.

    Burns gh-copilot weekly quota; opt in explicitly via --runner
    copilot. Default Phase 3 runs use ClaudeRunner.
    """

    model: str = "claude-sonnet-4.6"
    timeout_seconds: int = 600

    def run(self, prompt: str) -> RunnerResult:
        import time
        start = time.monotonic()
        try:
            result = subprocess.run(
                ["gh", "copilot", "--prompt", "--model", self.model],
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
    automatic-execution mode (the codex equivalent of
    `gh copilot --yolo`). We do NOT enable
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
        argv = ["codex", "exec", "--full-auto"]
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
        argv = ["cursor", "agent", "--print", "--force"]
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
