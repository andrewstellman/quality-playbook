"""v1.5.7 instruction 084 (A-22 structural defense) + 084b
(F1 guard-narrowing / F2 test env-isolation) regression tests.

Split into its own sibling file because bin/tests/test_run_playbook.py
is ~4.8k lines (well over a reasonable size to extend).

084b context: the 084 guard refused even informational/management
probes (--help, --kill) under an ambient agent env, breaking ~11
pre-existing tests' subprocess invocations and 2 detection tests that
used mock.patch.dict(clear=False) without stripping ambient vars
(codex F1 + F2). 084b adds an informational-token bypass (consulted
FIRST in _check_agent_context_or_refuse) and env-isolates every test
in this file via _AgentEnvIsolationMixin so they pass under BOTH
`env -i` clean AND ambient CODEX_THREAD_ID / COPILOT_AGENT_SESSION_ID
/ CLAUDECODE.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bin import run_playbook as rp

# QPB clone root: bin/tests/<this> -> parents[2]. Used as subprocess
# cwd so `-m bin.run_playbook` resolves regardless of where the test
# runner was launched from.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# A path that does not exist — used as a non-informational target so
# the guard (which fires at the very top of main(), BEFORE parse_args
# and BEFORE any target resolution) is exercised on a real "drive"
# shape without ever running the playbook. When the guard does NOT
# fire (carve-out / no agent env), target resolution then fails fast
# with a non-2 exit, which is exactly what the carve-out tests assert.
_NONEXISTENT_TARGET = "/tmp/nonexistent-qpb-target-084b-xyz"


class _AgentEnvIsolationMixin:
    """084b F2 fix. Strip ALL agent-context env vars in setUp (saving
    them) and restore in tearDown, so every test runs in an env known
    to be free of ambient CODEX_THREAD_ID / COPILOT_AGENT_SESSION_ID /
    CLAUDECODE leaking in from the test runner's parent terminal. The
    prior `mock.patch.dict(..., clear=False)` pattern left ambient
    vars in place, so in a real Codex session CODEX_THREAD_ID won
    first and the precedence tests failed (codex 084 F2)."""

    def setUp(self) -> None:
        super().setUp()
        self._saved_agent_env = {
            k: os.environ.pop(k, None) for k in rp._AGENT_CONTEXT_SIGNALS
        }

    def tearDown(self) -> None:
        for k, v in self._saved_agent_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        super().tearDown()


class AgentContextRefusalTests(_AgentEnvIsolationMixin, unittest.TestCase):
    """v1.5.7 instruction 084 (A-22) + 084b: the runner refuses a real
    "drive Phases 1-6" invocation from inside an AI-agent session
    unless --worker / --next-iteration / --operator-invoked; and (084b)
    informational/management probes (--help, --kill) are NEVER refused.

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    instruction-084b development:
      Mutation: comment out the call to
        _check_agent_context_or_refuse(_effective_argv) in main().
      Observed failure (purged __pycache__ first):
        FAIL: test_codex_context_refused_without_operator_invoked
        AssertionError: 1 != 2 : expected exit 2 (guard refusal), got 1
          [with the refusal removed, a non-informational target
           invocation proceeds to target resolution and exits 1 on the
           nonexistent path instead of the guard's exit 2]
      Mutation reverted; tests pass.

    Guard placement (084): the refusal runs at the very TOP of main()
    BEFORE parse_args, on the raw effective argv (token membership).
    084b adds the informational-token bypass as the FIRST carve-out so
    --help/--kill are not refused; the real-drive refusal below proves
    the A-22 protection is intact post-narrowing.
    """

    def test_detect_agent_context_codex(self) -> None:
        # Mixin stripped ambient agent vars; set only the one under
        # test so precedence is deterministic under any host terminal.
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "abc"},
                             clear=False):
            self.assertEqual(rp._detect_agent_context(), "Codex CLI")

    def test_detect_agent_context_copilot(self) -> None:
        with mock.patch.dict(os.environ,
                             {"COPILOT_AGENT_SESSION_ID": "abc"},
                             clear=False):
            self.assertEqual(rp._detect_agent_context(),
                             "GitHub Copilot CLI")

    def test_detect_agent_context_claude_code(self) -> None:
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"},
                             clear=False):
            self.assertEqual(rp._detect_agent_context(), "Claude Code")

    def test_detect_agent_context_none(self) -> None:
        # Mixin already stripped every agent var in setUp; detection
        # must report no agent context.
        self.assertIsNone(rp._detect_agent_context())

    def test_codex_context_refused_without_operator_invoked(self) -> None:
        # 084b: a REAL drive invocation (target arg, no informational
        # token, no carve-out) under CODEX_THREAD_ID must still refuse
        # with exit 2 + Mode-A-directing stderr. (084 used --help here;
        # post-084b --help is an informational bypass, so the refusal
        # must be proven with a non-informational invocation.)
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook", _NONEXISTENT_TARGET],
            env=env, capture_output=True, text=True, cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 2,
                         f"expected exit 2 (guard refusal), got "
                         f"{result.returncode}\nstdout: {result.stdout}\n"
                         f"stderr: {result.stderr}")
        self.assertIn("agent", result.stderr.lower())
        self.assertIn("Mode A", result.stderr)

    def test_operator_invoked_bypasses_refusal(self) -> None:
        # --operator-invoked + a non-informational target: the guard
        # must NOT fire (carve-out); target resolution then fails on
        # the nonexistent path with a non-2 exit. Asserting "not 2"
        # keeps this load-bearing for the carve-out specifically
        # (remove the carve-out -> guard exit 2 -> this fails).
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--operator-invoked", _NONEXISTENT_TARGET],
            env=env, capture_output=True, text=True, cwd=str(_REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 2,
                            f"--operator-invoked must bypass the guard "
                            f"(not exit 2), got {result.returncode}\n"
                            f"stderr: {result.stderr}")

    def test_next_iteration_bypasses_refusal(self) -> None:
        env = dict(os.environ)
        env["COPILOT_AGENT_SESSION_ID"] = "test-session-uuid"
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--next-iteration", _NONEXISTENT_TARGET],
            env=env, capture_output=True, text=True, cwd=str(_REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 2,
                            f"--next-iteration must bypass the guard "
                            f"(not exit 2), got {result.returncode}\n"
                            f"stderr: {result.stderr}")

    def test_worker_self_spawn_bypasses_refusal(self) -> None:
        # halt-condition #4: the internal --worker self-spawn inherits
        # the parent's env (Popen passes no env=). Without the --worker
        # carve-out, parallel mode would refuse its own workers under
        # any agent terminal.
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--worker", _NONEXISTENT_TARGET],
            env=env, capture_output=True, text=True, cwd=str(_REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 2,
                            f"--worker must bypass the guard (not exit "
                            f"2), got {result.returncode}\n"
                            f"stderr: {result.stderr}")


class AgentContextInformationalBypassTests(
        _AgentEnvIsolationMixin, unittest.TestCase):
    """v1.5.7 instruction 084b (F1 regression): the agent-context
    guard bypasses --help, --version, --kill, and similar
    informational / management tokens. The prior 084 implementation
    refused these under ambient agent env, breaking the test suite for
    any developer running pytest from inside a Claude Code / Codex /
    Copilot terminal (codex F1: 9 failures + 2 errors).

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    instruction-084b development:
      Mutation: comment out the
        `if _is_informational_or_management_invocation(argv): return`
      line in _check_agent_context_or_refuse.
      Observed failure (purged __pycache__ first; child env had
      CODEX_THREAD_ID=test-thread-uuid set):
        FAIL: test_help_bypasses_guard_under_ambient_codex_env
        AssertionError: 2 != 0 : --help should bypass guard, got exit 2
      Mutation reverted; tests pass.
    """

    def test_help_bypasses_guard_under_ambient_codex_env(self) -> None:
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook", "--help"],
            env=env, capture_output=True, text=True, cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0,
                         f"--help should bypass guard, got exit "
                         f"{result.returncode}\nstderr: {result.stderr}")

    def test_kill_bypasses_guard_under_ambient_copilot_env(self) -> None:
        env = dict(os.environ)
        env["COPILOT_AGENT_SESSION_ID"] = "test-session-uuid"
        # --kill on a fresh dir with no PIDs exits 0 (nothing to do)
        # or 1 (no pid file) — both acceptable; the contract is
        # "not exit 2 from the guard refusal." tempdir cwd so --kill
        # has somewhere to look without touching real run state.
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run(
                [sys.executable, "-m", "bin.run_playbook", "--kill"],
                env=env, capture_output=True, text=True, cwd=td,
            )
        self.assertNotEqual(result.returncode, 2,
                            f"--kill should bypass guard (not exit 2), "
                            f"got {result.returncode}\n"
                            f"stderr: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
