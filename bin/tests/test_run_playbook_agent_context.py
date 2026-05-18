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
import pty
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
        # 085 HARDENING: --operator-invoked ALONE no longer bypasses
        # (agents read --help and fabricate the flag — 2026-05-18 codex
        # desktop did). It now requires an unfabricatable operator
        # signal too: interactive TTY stdin, OR the out-of-band CI
        # env var. subprocess tests have piped (non-TTY) stdin, so the
        # deterministic operator path here is the env override; this
        # test keeps proving "--operator-invoked + a valid operator
        # signal bypasses under agent env" under the post-085 contract.
        # (The full TTY/no-TTY/override matrix is in
        # OperatorInvokedTtyRequirementTests below.)
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        env["QPB_OPERATOR_NON_TTY_OVERRIDE"] = "1"
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--operator-invoked", _NONEXISTENT_TARGET],
            env=env, capture_output=True, text=True,
            stdin=subprocess.PIPE, cwd=str(_REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 2,
                            f"--operator-invoked + operator signal must "
                            f"bypass the guard (not exit 2), got "
                            f"{result.returncode}\nstderr: {result.stderr}")

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


@unittest.skipUnless(sys.platform != "win32",
                     "pty.openpty() is POSIX-only; the TTY-positive "
                     "case cannot be constructed on Windows")
class OperatorInvokedTtyRequirementTests(
        _AgentEnvIsolationMixin, unittest.TestCase):
    """v1.5.7 instruction 085: --operator-invoked alone is no longer
    sufficient to bypass the agent-context guard. It must be paired
    with stdin-is-TTY OR the QPB_OPERATOR_NON_TTY_OVERRIDE env var.
    --worker / --next-iteration (mechanically set, not agent-bypass
    surface) keep their unconditional carve-out.

    All invocations use a NONEXISTENT target (not --help): post-084b
    --help is itself an informational bypass and would mask the TTY /
    carve-out path under test, making the assertions non-load-bearing.
    A nonexistent target makes the guard fire on a real "drive" shape;
    when the guard does NOT fire the run exits 1 at target resolution
    (deterministic, runner-independent), so "not 2" precisely isolates
    "the guard let it through".

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    instruction-085 development:
      Mutation: in _check_agent_context_or_refuse, replace the
        `if "--operator-invoked" in tokens:` isatty/env-var block
        with the prior `if "--operator-invoked" in tokens: return`
        (restores the 084b "--operator-invoked alone bypasses"
        semantics).
      Observed failure (purged __pycache__ first):
        FAIL: test_operator_invoked_without_tty_still_refused
        AssertionError: 1 != 2 : --operator-invoked without TTY
        should refuse under agent env, got exit 1
          [with the TTY/env gate removed, --operator-invoked alone
           bypasses; the nonexistent target then exits 1 at target
           resolution instead of the guard's exit 2]
      Mutation reverted; tests pass.
    """

    def test_operator_invoked_without_tty_still_refused(self) -> None:
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        env.pop("QPB_OPERATOR_NON_TTY_OVERRIDE", None)
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--operator-invoked", _NONEXISTENT_TARGET],
            env=env, capture_output=True, text=True,
            stdin=subprocess.PIPE, cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 2,
                         f"--operator-invoked without TTY should refuse "
                         f"under agent env, got exit {result.returncode}\n"
                         f"stderr: {result.stderr}")
        self.assertIn("TTY", result.stderr)
        self.assertIn("interactive terminal", result.stderr.lower())
        # The CI escape-hatch env var must NOT leak into the refusal.
        self.assertNotIn("QPB_OPERATOR_NON_TTY_OVERRIDE", result.stderr)

    def test_operator_invoked_with_env_override_bypasses(self) -> None:
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        env["QPB_OPERATOR_NON_TTY_OVERRIDE"] = "1"
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--operator-invoked", _NONEXISTENT_TARGET],
            env=env, capture_output=True, text=True,
            stdin=subprocess.PIPE, cwd=str(_REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 2,
                            f"--operator-invoked + env override should "
                            f"bypass (not exit 2), got "
                            f"{result.returncode}\nstderr: {result.stderr}")

    def test_operator_invoked_with_tty_bypasses(self) -> None:
        # Real TTY stdin via pty.openpty() — the human-operator case.
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        env.pop("QPB_OPERATOR_NON_TTY_OVERRIDE", None)
        master, slave = pty.openpty()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "bin.run_playbook",
                 "--operator-invoked", _NONEXISTENT_TARGET],
                env=env, capture_output=True, text=True,
                stdin=slave, cwd=str(_REPO_ROOT),
            )
        finally:
            os.close(slave)
            os.close(master)
        self.assertNotEqual(result.returncode, 2,
                            f"--operator-invoked with TTY stdin should "
                            f"bypass (not exit 2), got "
                            f"{result.returncode}\nstderr: {result.stderr}")

    def test_worker_carveout_unchanged(self) -> None:
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "test-thread-uuid"
        env.pop("QPB_OPERATOR_NON_TTY_OVERRIDE", None)
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--worker", _NONEXISTENT_TARGET],
            env=env, capture_output=True, text=True,
            stdin=subprocess.PIPE, cwd=str(_REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 2,
                            "--worker carve-out should still bypass "
                            "without TTY (mechanical self-spawn)")

    def test_next_iteration_carveout_unchanged(self) -> None:
        env = dict(os.environ)
        env["COPILOT_AGENT_SESSION_ID"] = "test-session-uuid"
        env.pop("QPB_OPERATOR_NON_TTY_OVERRIDE", None)
        result = subprocess.run(
            [sys.executable, "-m", "bin.run_playbook",
             "--next-iteration", _NONEXISTENT_TARGET],
            env=env, capture_output=True, text=True,
            stdin=subprocess.PIPE, cwd=str(_REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 2,
                            "--next-iteration carve-out should still "
                            "bypass without TTY")


if __name__ == "__main__":
    unittest.main()
