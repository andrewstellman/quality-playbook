"""v1.5.7 115 — Mode B must launch run_playbook with a clean
OPERATOR env so the anti-agent guard doesn't refuse.

After 114 fixed the import, the live AUP experiment showed Mode
B runs failing with a 1272-byte stream:

    ERROR: bin/run_playbook.py detected it is being invoked from
    inside an AI-agent session (Claude Code).

``run_playbook._detect_agent_context`` (the B-15/A-17 structural
defense from instruction 084) refuses to run when ANY of the
agent-marker env vars is set — ``CLAUDECODE`` / ``CODEX_THREAD_ID``
/ ``COPILOT_AGENT_SESSION_ID`` / ``CURSOR_AGENT`` / etc. The
harness inherited ``CLAUDECODE`` from the operator's shell and
``_vendor_env_for(Runner.CLAUDE)`` actively SETS ``CLAUDECODE=1``
(so the gate's runner-detector can find it for Mode A). For Mode
B those markers trip the guard.

114's test passed because it used ``run_playbook --help``, which
short-circuits BEFORE the guard (info-token carve-out). The real
Mode B launch has no such carve-out, so the guard fires.

115 fix: launch run_playbook with a sanitized operator env (Mode
B only — Mode A's CLAUDECODE marker must persist for gate
provenance).

Coverage:
  * ``runner._mode_b_agent_marker_vars()`` returns the canonical
    list from ``bin.run_playbook._AGENT_CONTEXT_SIGNALS`` (so it
    stays in sync — if run_playbook adds a new agent marker, the
    harness strip-list grows automatically).
  * ``runner._sanitize_mode_b_env`` strips those markers + sets
    ``QPB_OPERATOR_NON_TTY_OVERRIDE=1``.
  * ``launch_run_async`` applies the sanitization for Mode B
    only — Mode A keeps the marker.
  * **THE 115 MUTATION-BITE / GUARD-REACHING REAL LAUNCH**:
    invoke the full Mode B command with ``CLAUDECODE=1`` in the
    parent env. With sanitization: the guard passes and argparse
    runs (rejecting a bad ``--phase abc`` arg, exit 2). Without
    sanitization: the guard refuses with the "detected it is
    being invoked from inside an AI-agent session" message.
    Mutation-bite proves the sanitization is load-bearing.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bin.harness import runner as R
from bin.harness import schema as S


_REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Task A — _sanitize_mode_b_env + _mode_b_agent_marker_vars unit tests
# ---------------------------------------------------------------------------


class SanitizeModeBEnvTests(unittest.TestCase):
    """The pure env-transform: strip agent markers + set the
    non-TTY override. Mode A's vendor env (CLAUDECODE=1 for
    runner detection) is NOT this function's concern — the
    sanitizer is invoked only on the Mode B path."""

    def test_strips_claudecode(self) -> None:
        e = R._sanitize_mode_b_env(
            {"CLAUDECODE": "1", "OTHER": "x"})
        self.assertNotIn("CLAUDECODE", e)
        self.assertEqual(e["OTHER"], "x")

    def test_strips_codex_marker(self) -> None:
        e = R._sanitize_mode_b_env(
            {"CODEX_THREAD_ID": "session-abc"})
        self.assertNotIn("CODEX_THREAD_ID", e)

    def test_strips_copilot_marker(self) -> None:
        e = R._sanitize_mode_b_env(
            {"COPILOT_AGENT_SESSION_ID": "s"})
        self.assertNotIn("COPILOT_AGENT_SESSION_ID", e)

    def test_strips_cursor_marker(self) -> None:
        e = R._sanitize_mode_b_env({"CURSOR_AGENT": "c"})
        self.assertNotIn("CURSOR_AGENT", e)

    def test_strips_every_canonical_marker(self) -> None:
        """All 8 agent markers (incl. forward-compat placeholders)
        stripped. The canonical list is
        ``run_playbook._AGENT_CONTEXT_SIGNALS``."""
        from bin.run_playbook import _AGENT_CONTEXT_SIGNALS
        all_set = {var: "x" for var in _AGENT_CONTEXT_SIGNALS}
        e = R._sanitize_mode_b_env(all_set)
        for var in _AGENT_CONTEXT_SIGNALS:
            self.assertNotIn(
                var, e,
                f"115: _sanitize_mode_b_env must strip {var} "
                f"(it's in run_playbook._AGENT_CONTEXT_SIGNALS)",
            )

    def test_sets_qpb_operator_non_tty_override(self) -> None:
        """The 085 CI escape hatch — set on Mode B's env so
        the documented operator-with-no-TTY path works without
        env-thrashing."""
        e = R._sanitize_mode_b_env({})
        self.assertEqual(
            e["QPB_OPERATOR_NON_TTY_OVERRIDE"], "1",
        )

    def test_does_not_mutate_input(self) -> None:
        """The helper returns a new dict; the caller's env is
        unchanged."""
        original = {"CLAUDECODE": "1", "PATH": "/usr/bin"}
        snapshot = dict(original)
        R._sanitize_mode_b_env(original)
        self.assertEqual(original, snapshot)

    def test_preserves_unrelated_env(self) -> None:
        """Non-agent vars (PATH, HOME, custom vars) flow through
        untouched."""
        e = R._sanitize_mode_b_env({
            "PATH": "/usr/bin",
            "HOME": "/home/u",
            "MY_VAR": "x",
            "CLAUDECODE": "1",
        })
        self.assertEqual(e["PATH"], "/usr/bin")
        self.assertEqual(e["HOME"], "/home/u")
        self.assertEqual(e["MY_VAR"], "x")


class AgentMarkerVarsListStaysInSyncTests(unittest.TestCase):
    """The instruction explicitly says "consider
    importing/centralizing the list rather than hardcoding a
    divergent copy". 115 reads the canonical list from
    ``bin.run_playbook._AGENT_CONTEXT_SIGNALS`` so if
    run_playbook adds a new agent marker, the harness's strip
    list grows automatically."""

    def test_marker_vars_match_run_playbook(self) -> None:
        from bin.run_playbook import _AGENT_CONTEXT_SIGNALS
        self.assertEqual(
            R._mode_b_agent_marker_vars(),
            frozenset(_AGENT_CONTEXT_SIGNALS.keys()),
            "115: the harness's _mode_b_agent_marker_vars() "
            "MUST equal run_playbook._AGENT_CONTEXT_SIGNALS' "
            "keys. If this fails, run_playbook added an agent "
            "marker and the harness needs to know to strip it. "
            "The 115 design centralizes the list via lazy "
            "import precisely to avoid this kind of drift.",
        )

    def test_returns_frozenset(self) -> None:
        """Immutable return so a caller can't accidentally
        mutate the shared set."""
        self.assertIsInstance(
            R._mode_b_agent_marker_vars(), frozenset)


# ---------------------------------------------------------------------------
# Task A — launch_run_async integration: Mode B sanitizes, Mode A doesn't
# ---------------------------------------------------------------------------


def _mk_axes(runner: S.Runner = S.Runner.CLAUDE, *,
             mode: S.Mode = S.Mode.A,
             channel: S.InstallChannel = S.InstallChannel.CLONE,
             model: str = "opus") -> S.RunAxes:
    return S.RunAxes(
        runner=runner, mode=mode,
        install_channel=channel, model=model,
    )


class LaunchRunAsyncEnvSelectionTests(unittest.TestCase):
    """The Mode B sanitization fires in ``launch_run_async``;
    Mode A keeps the agent marker (the gate's
    runner-detection depends on it for gate-report
    provenance). Verify both via the ``env_snapshot`` recorded
    on the SpawnResult."""

    def _make_spec(self, target_dir: Path, run_dir: Path, *,
                    mode: S.Mode,
                    runner: S.Runner = S.Runner.CLAUDE
                    ) -> R.LaunchSpec:
        return R.LaunchSpec(
            target_dir=target_dir, run_dir=run_dir,
            axes=_mk_axes(runner, mode=mode),
            case_id="c", run_id="r",
            max_duration_s=5.0, prompt="(unused)",
        )

    def test_mode_b_env_snapshot_strips_claudecode(
            self) -> None:
        """**THE 115 LAUNCH-INTEGRATION ASSERTION**:
        ``launch_run_async`` for Mode B must produce an env
        with the agent markers stripped — even though
        ``_vendor_env_for(CLAUDE)`` sets CLAUDECODE=1 and the
        parent env (this test process) likely has it too. The
        sanitizer is the last step before subprocess spawn."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            spec = self._make_spec(target, run_dir,
                                     mode=S.Mode.B)
            # Patch the agent env into this process so the
            # env build path sees it (mirror the operator's
            # CLAUDECODE=1 shell).
            old_env = os.environ.get("CLAUDECODE")
            os.environ["CLAUDECODE"] = "1"
            try:
                # Use Popen patching to capture env without
                # actually spawning run_playbook (we just
                # want the env_snapshot from SpawnResult; the
                # subprocess never runs).
                captured = {}
                import subprocess as _sp
                real_popen = _sp.Popen

                class _FakePopen:
                    def __init__(self_pipe, cmd, **kwargs):
                        captured["cmd"] = cmd
                        captured["env"] = kwargs.get("env")
                        self_pipe.pid = 99999
                        self_pipe.stdin = None
                    def wait(self_p, *a, **k):
                        return 0
                _sp.Popen = _FakePopen  # type: ignore[assignment]
                try:
                    spawn = R.launch_run_async(spec)
                finally:
                    _sp.Popen = real_popen
            finally:
                if old_env is None:
                    os.environ.pop("CLAUDECODE", None)
                else:
                    os.environ["CLAUDECODE"] = old_env
            # The subprocess env (the captured one) has
            # CLAUDECODE stripped AND has the override set.
            env_passed = captured["env"]
            self.assertNotIn(
                "CLAUDECODE", env_passed,
                "115: Mode B subprocess env MUST NOT carry "
                "CLAUDECODE — it would trip the anti-agent "
                "guard.",
            )
            self.assertEqual(
                env_passed.get("QPB_OPERATOR_NON_TTY_OVERRIDE"),
                "1",
                "115: Mode B subprocess env MUST set the "
                "non-TTY override so the documented CI "
                "escape hatch can fire if --operator-invoked "
                "is ever added to the argv.",
            )
            # The env_snapshot recorded on the SpawnResult
            # mirrors that — operators reading status.json
            # see the sanitized state.
            self.assertNotIn("CLAUDECODE", spawn.env_snapshot)
            self.assertEqual(
                spawn.env_snapshot.get(
                    "QPB_OPERATOR_NON_TTY_OVERRIDE"),
                "1",
            )

    def test_mode_a_env_snapshot_keeps_claudecode(
            self) -> None:
        """**Regression pin — DO NOT BREAK MODE A**:
        ``_vendor_env_for(CLAUDE)`` sets CLAUDECODE=1
        deliberately so the gate's runner-detector finds the
        marker and stamps gate-report-latest.json with
        ``runner=claude``. Stripping it for Mode A would
        break gate provenance. 115's sanitization is Mode-B-
        ONLY; this test catches a regression that accidentally
        widens the strip to Mode A."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            spec = self._make_spec(target, run_dir,
                                     mode=S.Mode.A)
            captured = {}
            import subprocess as _sp
            real_popen = _sp.Popen

            class _FakePopen:
                def __init__(self_pipe, cmd, **kwargs):
                    captured["env"] = kwargs.get("env")
                    self_pipe.pid = 99998
                    self_pipe.stdin = None
                def wait(self_p, *a, **k):
                    return 0
            _sp.Popen = _FakePopen  # type: ignore[assignment]
            try:
                spawn = R.launch_run_async(spec)
            finally:
                _sp.Popen = real_popen
            env_passed = captured["env"]
            self.assertEqual(
                env_passed.get("CLAUDECODE"), "1",
                "115 regression guard: Mode A env MUST keep "
                "CLAUDECODE=1 (set by _vendor_env_for for "
                "gate-report runner detection). 115's "
                "sanitization is Mode B-only; if this fails, "
                "the strip widened to Mode A and gate "
                "provenance is broken.",
            )
            # And the override is NOT set for Mode A (it's a
            # Mode-B-specific concession).
            self.assertNotIn(
                "QPB_OPERATOR_NON_TTY_OVERRIDE", env_passed,
            )


# ---------------------------------------------------------------------------
# Task B — REAL launch that REACHES THE GUARD (not --help)
# ---------------------------------------------------------------------------


class ModeBGuardReachingRealLaunchTests(unittest.TestCase):
    """**THE 115 MUTATION-BITE / REAL LAUNCH**: actually run
    the Mode B subprocess with the operator's CLAUDECODE=1
    env, drive it past argparse's info-token carve-out (use
    ``--phase abc`` so argparse rejects AFTER the guard
    runs), and assert the guard didn't refuse.

    114's test used ``--help`` which short-circuited the
    guard via the info-token carve-out (the very gap that
    let the bug ship). 115's test uses a non-info argv to
    force the guard into its env-checking branch."""

    def _build_target(self, tmp: str) -> Path:
        target = Path(tmp) / "target"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _build_cmd(self, target: Path) -> "list[str]":
        # Real Mode B argv (via the production builder). Add
        # `--phase abc` so argparse rejects it AFTER the
        # guard runs — that gives us a fast, clean exit
        # whose output we can assert on.
        return R._mode_b_command(
            S.Runner.CLAUDE, target, model="opus",
            parameters=["--phase", "abc"],
        )

    def test_guard_passes_with_sanitized_env(self) -> None:
        """**THE 115 LOAD-BEARING TEST**: with sanitization
        (the 115 fix), Mode B's run_playbook gets PAST the
        guard even with CLAUDECODE=1 in the parent env.
        Argparse's ``--phase abc`` rejection fires
        afterwards — proof the guard didn't short-circuit."""
        with tempfile.TemporaryDirectory() as tmp:
            target = self._build_target(tmp)
            # Simulate the operator's CLAUDECODE=1 shell as
            # the parent env, then apply the 115 sanitizer.
            parent_env = {
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
                "CLAUDECODE": "1",  # operator's shell marker
            }
            sanitized = R._sanitize_mode_b_env(parent_env)
            cmd = self._build_cmd(target)
            proc = subprocess.run(
                cmd, env=sanitized, cwd=str(target),
                capture_output=True, text=True, timeout=15,
            )
            output = proc.stdout + proc.stderr
            # **THE 115 MUTATION-BITE**: the guard MUST NOT
            # refuse. The "detected it is being invoked from"
            # phrase is run_playbook's guard-refusal stderr.
            self.assertNotIn(
                "detected it is being invoked from", output,
                "115: with sanitization, run_playbook's "
                "_detect_agent_context guard must NOT refuse. "
                "If this assertion fires, the sanitization "
                "isn't stripping a marker the parent env "
                "carried.",
            )
            # And argparse rejected the bad `--phase`
            # value — which means we got PAST the guard into
            # arg parsing. The exact message is
            # ``Invalid phase 'abc'. Must be 1-6 or 'all'.``
            # (run_playbook's custom phase-validator that wraps
            # ``--phase`` — not the plain argparse int error).
            self.assertIn(
                "Invalid phase 'abc'", output,
                f"115: subprocess must reach argparse (past "
                f"the guard) and reject `--phase abc`. "
                f"Output didn't contain the expected argparse "
                f"error: {output[:400]!r}",
            )
            # Argparse-on-bad-int exits 2.
            self.assertEqual(proc.returncode, 2)

    def test_mutation_bite_unsanitized_env_triggers_guard(
            self) -> None:
        """**Pre-115 baseline** (proves the test setup
        works): pass the parent env UNCHANGED with
        CLAUDECODE=1 — the guard MUST fire and refuse.

        If this test fails, the test scaffolding is broken —
        e.g. run_playbook stopped enforcing the guard, or
        we're not reaching it for some other reason. The
        mutation-bite asymmetry is: this test asserts the
        guard fires under the UN-sanitized parent env, while
        ``test_guard_passes_with_sanitized_env`` asserts it
        doesn't fire under the sanitized env. Both must hold
        for the 115 fix to be load-bearing."""
        with tempfile.TemporaryDirectory() as tmp:
            target = self._build_target(tmp)
            unsanitized_env = {
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
                "CLAUDECODE": "1",
            }
            cmd = self._build_cmd(target)
            proc = subprocess.run(
                cmd, env=unsanitized_env, cwd=str(target),
                capture_output=True, text=True, timeout=15,
            )
            output = proc.stdout + proc.stderr
            self.assertIn(
                "detected it is being invoked from", output,
                "115 baseline: with CLAUDECODE=1 and NO "
                "sanitization, run_playbook's guard MUST "
                "refuse. If this assertion fails, either the "
                "guard regressed or the test isn't actually "
                "passing the CLAUDECODE marker through.",
            )

    def test_other_marker_vars_also_caught(self) -> None:
        """Forward-compatibility: the sanitization must work
        for the full canonical agent-marker set, not just
        CLAUDECODE. Use CODEX_THREAD_ID + COPILOT_AGENT_SESSION_ID
        in the parent env and verify guard still passes after
        sanitization."""
        with tempfile.TemporaryDirectory() as tmp:
            target = self._build_target(tmp)
            parent_env = {
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
                "CODEX_THREAD_ID": "session-codex",
                "COPILOT_AGENT_SESSION_ID": "session-copilot",
                "CURSOR_AGENT": "cursor",
            }
            sanitized = R._sanitize_mode_b_env(parent_env)
            cmd = self._build_cmd(target)
            proc = subprocess.run(
                cmd, env=sanitized, cwd=str(target),
                capture_output=True, text=True, timeout=15,
            )
            output = proc.stdout + proc.stderr
            self.assertNotIn(
                "detected it is being invoked from", output,
                "115: sanitization must strip ALL canonical "
                "agent markers, not just CLAUDECODE.",
            )


# ---------------------------------------------------------------------------
# Bundle-safety: 115 lives under bin/harness/ (excluded)
# ---------------------------------------------------------------------------


class BundleSafety115Tests(unittest.TestCase):

    def test_runner_changes_stay_under_harness(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"115 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
