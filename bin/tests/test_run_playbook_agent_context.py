"""v1.5.7 instruction 084 (A-22 structural defense) regression tests.

Split into its own sibling file because bin/tests/test_run_playbook.py
is ~4.8k lines (well over a reasonable size to extend).
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from bin import run_playbook as rp

# QPB clone root: bin/tests/<this> -> parents[2]. Used as subprocess
# cwd so `-m bin.run_playbook` resolves regardless of where the test
# runner was launched from.
_REPO_ROOT = Path(__file__).resolve().parents[2]


class AgentContextRefusalTests(unittest.TestCase):
    """v1.5.7 instruction 084 (A-22 structural defense): the runner
    refuses to start when invoked from inside an AI-agent session
    unless the caller passes --operator-invoked, --next-iteration, or
    the internal --worker self-spawn flag.

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    instruction-084 development:
      Mutation: comment out the call to
        _check_agent_context_or_refuse(_effective_argv) in main().
      Observed failure (purged __pycache__ first):
        FAIL: test_codex_context_refused_without_operator_invoked
        AssertionError: 0 != 2 : expected exit 2, got 0
          [with the refusal removed, argparse processes --help and
           exits 0; the agent-context guard never fires]
      Mutation reverted; tests pass.

    Note on the guard placement: the refusal runs at the very TOP of
    main() BEFORE parse_args, operating on the raw effective argv
    (token membership), NOT on a parsed Namespace. argparse processes
    `--help` *during* parse_args and exits 0, so a post-parse refusal
    could never fire for a `--help` invocation — yet the contract is
    "refuse before any other work so the agent sees only the error"
    (instruction-084 codex contract #2). Raw-argv carve-out detection
    is the correct resolution; an agent reaching for the runner does
    not pass --worker / --next-iteration / --operator-invoked.
    """

    def test_detect_agent_context_codex(self) -> None:
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "abc"}, clear=False):
            self.assertEqual(rp._detect_agent_context(), "Codex CLI")

    def test_detect_agent_context_copilot(self) -> None:
        with mock.patch.dict(os.environ,
                             {"COPILOT_AGENT_SESSION_ID": "abc"}, clear=False):
            self.assertEqual(rp._detect_agent_context(), "GitHub Copilot CLI")

    def test_detect_agent_context_claude_code(self) -> None:
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=False):
            self.assertEqual(rp._detect_agent_context(), "Claude Code")

    def test_detect_agent_context_none(self) -> None:
        # Strip all known agent vars from env for this test.
        env_strip = {k: "" for k in rp._AGENT_CONTEXT_SIGNALS}
        with mock.patch.dict(os.environ, env_strip, clear=False):
            for k in rp._AGENT_CONTEXT_SIGNALS:
                os.environ.pop(k, None)
            self.assertIsNone(rp._detect_agent_context())

    def test_codex_context_refused_without_operator_invoked(self) -> None:
        # Run bin/run_playbook.py as subprocess with CODEX_THREAD_ID
        # set, expect exit 2 + stderr mentioning the agent + Mode A.
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook", "--help"],
            env=env, capture_output=True, text=True, cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 2,
                         f"expected exit 2, got {result.returncode}\n"
                         f"stdout: {result.stdout}\nstderr: {result.stderr}")
        self.assertIn("agent", result.stderr.lower())
        self.assertIn("Mode A", result.stderr)

    def test_operator_invoked_bypasses_refusal(self) -> None:
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--operator-invoked", "--help"],
            env=env, capture_output=True, text=True, cwd=str(_REPO_ROOT),
        )
        # --help prints usage and exits 0; the refusal must not fire.
        self.assertEqual(result.returncode, 0,
                         f"expected exit 0 (help), got {result.returncode}\n"
                         f"stderr: {result.stderr}")

    def test_next_iteration_bypasses_refusal(self) -> None:
        env = dict(os.environ)
        env["COPILOT_AGENT_SESSION_ID"] = "test-session-uuid"
        # --next-iteration is the legitimate handoff carve-out.
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--next-iteration", "--help"],
            env=env, capture_output=True, text=True, cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0)

    def test_worker_self_spawn_bypasses_refusal(self) -> None:
        # halt-condition #4: the internal --worker self-spawn inherits
        # the parent's env (Popen passes no env=). Without the --worker
        # carve-out, parallel mode would refuse its own workers under
        # any agent terminal. --help => exit 0 proves the carve-out.
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--worker", "--help"],
            env=env, capture_output=True, text=True, cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0,
                         f"expected exit 0 (worker carve-out + help), got "
                         f"{result.returncode}\nstderr: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
