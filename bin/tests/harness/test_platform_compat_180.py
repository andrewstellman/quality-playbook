"""v1.5.7 180: Windows compatibility tests for the harness's
Unix-isms. Surfaced on Andrew's Windows 11 box when
`qpb_harness.py:383` tried to open `/tmp/qpb-harness-<TS>.log`
(non-existent path on Windows). 180 introduces
`bin/harness/_platform.py` as the cross-platform abstraction
seam; this test file verifies the abstractions behave correctly
on the running platform (Linux/Mac in CI; Windows for Andrew's
acceptance test).
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest


_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from bin.harness import _platform as P  # noqa: E402


class TmpDirTests(unittest.TestCase):

    def test_180_get_tmp_dir_returns_real_directory(self) -> None:
        d = P.get_tmp_dir()
        self.assertIsInstance(d, pathlib.Path)
        self.assertTrue(
            d.is_dir(),
            f"get_tmp_dir() must return existing dir; got {d}",
        )

    def test_180_orchestrator_log_path_uses_tmp_dir(self) -> None:
        log_path = P.get_orchestrator_log_path(
            "20260601T135234Z")
        self.assertEqual(
            log_path.parent, P.get_tmp_dir(),
            f"orchestrator log path must live under "
            f"get_tmp_dir(); got parent {log_path.parent}",
        )
        self.assertIn("qpb-harness", log_path.name)


class SpawnDetachedTests(unittest.TestCase):

    def test_180_spawn_detached_returns_pid(self) -> None:
        log_path = (
            P.get_tmp_dir() / "_test_180_spawn.log")
        try:
            # Spawn a no-op detached process that exits cleanly.
            pid = P.spawn_detached(
                [sys.executable, "-c",
                 "import sys; sys.exit(0)"],
                log_path=log_path,
            )
            # v1.5.7 180 FIX (FINDING-1): on POSIX, spawn_detached
            # calls os.fork() and returns 0 in the forked child.
            # The child must NOT continue running pytest/unittest
            # assertions — it would re-enter the test framework's
            # session state, polluting output (pytest: 11 spurious
            # errors) and producing false failures
            # (assertGreater(0, 0) fails in the child). Exit
            # immediately via os._exit so atexit handlers and
            # framework teardown DO NOT run in the child.
            if not P.IS_WINDOWS and pid == 0:
                import os as _os
                _os._exit(0)
            # Parent (POSIX) or only caller (Windows).
            self.assertIsInstance(pid, int)
            self.assertGreater(pid, 0)
        finally:
            try:
                log_path.unlink()
            except OSError:
                pass


class FileLockTests(unittest.TestCase):

    def test_180_file_lock_blocking_acquires_and_releases(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = pathlib.Path(tmp) / "test.lock"
            lock_path.touch()
            with open(lock_path, "w", encoding="utf-8") as fp:
                ok = P.acquire_file_lock(fp, blocking=True)
                self.assertTrue(ok)
                P.release_file_lock(fp)

    def test_180_file_lock_nb_returns_false_when_held(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = pathlib.Path(tmp) / "test.lock"
            lock_path.touch()
            fp_a = open(lock_path, "w", encoding="utf-8")
            fp_b = open(lock_path, "w", encoding="utf-8")
            try:
                self.assertTrue(
                    P.acquire_file_lock(fp_a, blocking=True))
                ok = P.acquire_file_lock(fp_b, blocking=False)
                self.assertFalse(
                    ok,
                    "Second NB acquire on held lock must "
                    "return False",
                )
            finally:
                P.release_file_lock(fp_a)
                fp_a.close()
                fp_b.close()


class ModuleSurfaceTests(unittest.TestCase):
    """The bare import of _platform must succeed on every
    platform (no top-level fcntl import that breaks Windows,
    no top-level msvcrt import that breaks POSIX). 180's
    abstraction must use lazy / conditional imports."""

    def test_180_platform_module_imports_cleanly(self) -> None:
        # Already imported above; if it failed the whole file
        # would have errored. Explicit assertions for clarity:
        self.assertTrue(hasattr(P, "IS_WINDOWS"))
        self.assertTrue(hasattr(P, "get_tmp_dir"))
        self.assertTrue(hasattr(P, "spawn_detached"))
        self.assertTrue(hasattr(P, "acquire_file_lock"))
        self.assertTrue(hasattr(P, "release_file_lock"))
        self.assertTrue(hasattr(P, "popen_kwargs_detached"))
        self.assertTrue(hasattr(P, "get_orchestrator_log_path"))


class ChildArgsReinvocationTests(unittest.TestCase):
    """v1.5.7 180 FIX (FINDING-2): qpb_harness.py's Windows
    spawn path must construct child_args as
    ``[sys.executable, "-m", "bin.qpb_harness"] + sys.argv[1:]``,
    NOT ``list(sys.argv)``. Pre-fix the latter caused
    ``WinError 193 ("%1 is not a valid Win32 application")``
    because sys.argv[0] is the .py path which Windows
    CreateProcess can't execute directly."""

    def test_180_child_args_uses_explicit_module_invocation(
            self) -> None:
        src = (
            _REPO / "bin" / "qpb_harness.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "child_args = list(sys.argv)", src,
            "qpb_harness.py: child_args must NOT be "
            "`list(sys.argv)` — Windows CreateProcess can't "
            "execute the .py path. Use "
            "`[sys.executable, '-m', 'bin.qpb_harness']`.",
        )
        # Positively assert the correct form appears in the
        # spawn block.
        self.assertIn("sys.executable", src)
        self.assertIn('"-m"', src)
        self.assertIn('"bin.qpb_harness"', src)


class SignalGuardTests(unittest.TestCase):
    """v1.5.7 180-followup-3 FINDING-3: any reference to a
    POSIX-only signal attribute in bin/ must be guarded for
    Windows (either an AttributeError-catching except clause
    or a hasattr(signal, "SIG…") pre-check)."""

    def test_180_signal_sighup_guarded_with_attribute_error(
            self) -> None:
        src = (
            _REPO / "bin" / "harness" / "plan_runner.py"
        ).read_text(encoding="utf-8")
        if "signal.SIGHUP" in src:
            sighup_idx = src.find("signal.SIGHUP")
            snippet = src[sighup_idx:sighup_idx + 800]
            self.assertTrue(
                "AttributeError" in snippet
                or "hasattr(signal" in snippet,
                "signal.SIGHUP handler must catch "
                "AttributeError (Windows) or use "
                "hasattr(signal, 'SIGHUP') guard. "
                "Snippet: " + snippet[:200],
            )

    # v1.5.7 180-followup-6 FINDING-9: the enumerated-list sweep
    # that lived here was REPLACED by
    # ``ComprehensiveSweepTests::test_180_no_unguarded_posix_signals_anywhere``
    # which uses inverse-membership against the Windows-available
    # frozenset. The enumerated list missed SIGKILL — Andrew's
    # 5th Windows fire. See [[methodology_lesson_16]].


class SpawnVerifyTests(unittest.TestCase):
    """v1.5.7 180-followup-3 FINDING-4: after spawn_detached
    returns a child pid, the parent MUST verify the child is
    alive before declaring success. Source-pin check."""

    def test_180_spawn_detached_followed_by_liveness_check(
            self) -> None:
        src = (
            _REPO / "bin" / "qpb_harness.py"
        ).read_text(encoding="utf-8")
        self.assertTrue(
            "pid_alive" in src
            or "_verify_child_started" in src
            or "child_alive" in src,
            "qpb_harness.py must verify spawned child is alive "
            "before declaring success. See 180 FINDING-4.",
        )


class PidAliveTests(unittest.TestCase):
    """v1.5.7 180-followup-3: P.pid_alive contract on the
    running platform."""

    def test_180_pid_alive_self_is_alive(self) -> None:
        import os as _os
        self.assertTrue(P.pid_alive(_os.getpid()))

    def test_180_pid_alive_zero_is_dead(self) -> None:
        self.assertFalse(P.pid_alive(0))

    def test_180_pid_alive_unlikely_pid_is_dead(self) -> None:
        # 999_999_999 is well above the practical max pid range
        # on Linux/Mac/Windows. May very rarely be alive on a
        # truly long-running machine — skip if so.
        if P.pid_alive(999_999_999):
            self.skipTest("999_999_999 happened to be live")
        self.assertFalse(P.pid_alive(999_999_999))


class ResolveExecutableTests(unittest.TestCase):
    """v1.5.7 180-followup-4 FINDING-5: resolve_executable wraps
    shutil.which so subprocess.Popen gets a full path with the
    correct extension on Windows."""

    def test_180_resolve_executable_finds_python(self) -> None:
        resolved = None
        for name in ("python3", "python"):
            try:
                resolved = P.resolve_executable(name)
                break
            except FileNotFoundError:
                continue
        self.assertIsNotNone(
            resolved,
            "neither python3 nor python on PATH — "
            "test prerequisite failed",
        )
        self.assertTrue(pathlib.Path(resolved).is_file())

    def test_180_resolve_executable_raises_on_missing(
            self) -> None:
        with self.assertRaises(FileNotFoundError):
            P.resolve_executable(
                "nonexistent_executable_xyz_12345")


class NoBareNpmOrNpxTests(unittest.TestCase):
    """v1.5.7 180-followup-4 FINDING-5: source-pin check that
    no bin/*.py file passes a bare 'npm' or 'npx' as the first
    list element to subprocess.run / Popen / call / etc. Pre-
    fix this caused WinError 2 on Windows because subprocess
    doesn't extension-walk PATHEXT for ``npm.cmd`` /
    ``npx.cmd``."""

    def test_180_no_bare_npm_or_npx_in_subprocess_calls(
            self) -> None:
        import re
        npm_pattern = re.compile(
            r"subprocess\.(run|Popen|call|check_call"
            r"|check_output)\s*\([^)]*\[\s*[\"']npm[\"']")
        npx_pattern = re.compile(
            r"subprocess\.(run|Popen|call|check_call"
            r"|check_output)\s*\([^)]*\[\s*[\"']npx[\"']")
        for f in (_REPO / "bin").rglob("*.py"):
            if "test" in f.name:
                continue
            src = f.read_text(encoding="utf-8")
            for m in npm_pattern.finditer(src):
                self.fail(
                    f"{f} contains bare 'npm' in subprocess "
                    f"call: {m.group(0)}")
            for m in npx_pattern.finditer(src):
                self.fail(
                    f"{f} contains bare 'npx' in subprocess "
                    f"call: {m.group(0)}")


class FailFastScopeTests(unittest.TestCase):
    """v1.5.7 180-followup-4 FINDING-6: qpb_harness.py spawn
    verify must wait for ``manifest.json`` (post-launch marker)
    rather than just ``predicted_hrd.is_dir()`` (a pre-launch
    setup marker that exists during artifact build)."""

    def test_180_fail_fast_waits_for_manifest_json(
            self) -> None:
        src = (
            _REPO / "bin" / "qpb_harness.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "manifest.json", src,
            "qpb_harness.py must wait for manifest.json as "
            "the post-launch marker per FINDING-6. The "
            "run-dir-existence check alone is insufficient — "
            "it passes during artifact build, before any "
            "runs launch.",
        )


class ManifestRunningStateTests(unittest.TestCase):
    """v1.5.7 180-followup-6 FINDING-10: a manifest with all-
    FAILED entries doesn't mean the launch succeeded. The post-
    launch verify now requires at least one state=RUNNING (or
    PENDING) entry; on deadline-exceeded with all-terminal,
    the per-run terminal_reason is surfaced to stderr."""

    def test_180_at_least_one_running_helper_exists(
            self) -> None:
        from bin import qpb_harness
        self.assertTrue(
            hasattr(qpb_harness, "_at_least_one_running"))

    def test_180_at_least_one_running_returns_false_on_all_failed(
            self) -> None:
        import tempfile, json as _json
        from bin import qpb_harness
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False) as f:
            _json.dump({"runs": [
                {"index": 0, "state": "DONE",
                 "terminal_state": "FAILED"},
                {"index": 1, "state": "DONE",
                 "terminal_state": "FAILED"},
            ]}, f)
            path = pathlib.Path(f.name)
        try:
            self.assertFalse(
                qpb_harness._at_least_one_running(path))
        finally:
            path.unlink()

    def test_180_at_least_one_running_returns_true_on_mixed(
            self) -> None:
        import tempfile, json as _json
        from bin import qpb_harness
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False) as f:
            _json.dump({"runs": [
                {"index": 0, "state": "DONE",
                 "terminal_state": "FAILED"},
                {"index": 1, "state": "RUNNING"},
            ]}, f)
            path = pathlib.Path(f.name)
        try:
            self.assertTrue(
                qpb_harness._at_least_one_running(path))
        finally:
            path.unlink()

    def test_180_at_least_one_running_returns_true_on_pending(
            self) -> None:
        # PENDING is acceptable — runs may be mid-spawn but not
        # yet RUNNING; the launch has not failed.
        import tempfile, json as _json
        from bin import qpb_harness
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False) as f:
            _json.dump({"runs": [
                {"index": 0, "state": "PENDING"},
            ]}, f)
            path = pathlib.Path(f.name)
        try:
            self.assertTrue(
                qpb_harness._at_least_one_running(path))
        finally:
            path.unlink()

    def test_180_at_least_one_running_handles_missing_or_garbage(
            self) -> None:
        from bin import qpb_harness
        self.assertFalse(
            qpb_harness._at_least_one_running(
                pathlib.Path("/nonexistent/qpb-test")))

    def test_180_surface_all_failed_helper_exists(self) -> None:
        from bin import qpb_harness
        self.assertTrue(
            hasattr(qpb_harness,
                    "_surface_all_failed_at_launch"))

    def test_180_qpb_harness_uses_running_state_check_not_just_exists(
            self) -> None:
        # Source-pin: qpb_harness.py's _cmd_run_plan must CALL
        # the stronger check (_at_least_one_running) inside the
        # post-launch verify loop, not just check is_file().
        # The function definition is `def _at_least_one_running`
        # — the call is `_at_least_one_running(<expr>)`. We need
        # at least one CALL beyond the def. Counting occurrences
        # of `_at_least_one_running(` requires ≥2: one for def,
        # at least one for call.
        src = (_REPO / "bin" / "qpb_harness.py").read_text(
            encoding="utf-8")
        occurrences = src.count("_at_least_one_running(")
        self.assertGreaterEqual(
            occurrences, 2,
            f"qpb_harness.py must CALL _at_least_one_running in "
            f"the post-launch verify loop (FINDING-10). Found "
            f"{occurrences} occurrence(s) of "
            f"`_at_least_one_running(` — expected ≥2 (one for "
            f"def, ≥1 for call). Pre-fix the manifest-existence "
            f"check passed when all 4 runs failed at launch.")


class KillProcessTreeTests(unittest.TestCase):
    """v1.5.7 180-followup-6 FINDING-9: ``_platform.kill_process_tree``
    abstracts the SIGKILL/TerminateProcess primitive. Andrew's
    5th Windows fire saw all 4 runs FAIL with
    ``AttributeError("module 'signal' has no attribute 'SIGKILL'")``
    — the prior code path evaluated ``signal.SIGKILL`` at
    runner.py module-load time via a default arg
    (``def kill_run(... sig=signal.SIGKILL ...)``)."""

    def test_180_kill_process_tree_helper_exists(self) -> None:
        from bin.harness import _platform as _pmod
        self.assertTrue(hasattr(_pmod, "kill_process_tree"))

    def test_180_kill_process_tree_no_op_on_invalid_pid(
            self) -> None:
        from bin.harness import _platform as _pmod
        _pmod.kill_process_tree(0, force=True)
        _pmod.kill_process_tree(-1, force=True)

    def test_180_runner_kill_run_no_load_time_sigkill_default(
            self) -> None:
        src = (_REPO / "bin" / "harness" / "runner.py").read_text(
            encoding="utf-8")
        import re
        m = re.search(
            r"def kill_run\([^)]*sig[^)]*\)", src, re.DOTALL)
        self.assertIsNotNone(
            m, "runner.py must define kill_run with a sig param")
        sig_param = m.group(0)
        self.assertNotIn(
            "signal.SIGKILL", sig_param,
            "kill_run's sig default MUST NOT be signal.SIGKILL "
            "(crashes Windows module-load — see "
            "180-followup-6 FINDING-9). Use None sentinel + "
            "lazy resolution inside _platform.kill_process_tree.")

    def test_180_no_sigkill_in_default_args(self) -> None:
        import re
        for f in (_REPO / "bin").rglob("*.py"):
            if "test" in f.name:
                continue
            src = f.read_text(encoding="utf-8")
            for m in re.finditer(
                    r"^def\s+\w+\([^)]*\)\s*(->\s*[^:]+)?\s*:",
                    src, re.MULTILINE | re.DOTALL):
                sig_text = m.group(0)
                if "signal.SIGKILL" in sig_text:
                    self.fail(
                        f"{f}: function signature contains "
                        f"signal.SIGKILL as default arg — "
                        f"crashes Windows module-load. "
                        f"Match: {sig_text[:200]}")


class PsutilMigrationTests(unittest.TestCase):
    """v1.5.7 182: psutil-backed process management."""

    def test_pid_alive_uses_psutil(self) -> None:
        # Source-pin: _platform.py imports psutil (lazily
        # inside pid_alive) and the body references
        # psutil.Process. Catches a revert.
        src = (_REPO / "bin" / "harness" / "_platform.py"
               ).read_text(encoding="utf-8")
        self.assertIn("import psutil", src)
        self.assertIn("psutil.Process", src)
        # The pre-182 hand-rolled Windows implementations must
        # be gone — match the actual function CALLS (``(``
        # suffix), not bare names (which can legitimately
        # appear in docstrings describing the pre-182 history).
        self.assertNotIn(
            "OpenProcess(", src,
            "ctypes OpenProcess( call remains in _platform.py; "
            "should have migrated to psutil "
            "(182 commit 3/5).")
        self.assertNotIn("GetExitCodeProcess(", src)
        self.assertNotIn("TerminateProcess(", src)

    def test_kill_process_tree_walks_descendants(self) -> None:
        # Functional: spawn a parent that spawns a child; kill
        # the parent via kill_process_tree(force=True); verify
        # both pids are dead. This is the empirical evidence
        # that the Windows leader-only bug is fixed (POSIX has
        # always tree-killed via os.killpg, but the test
        # validates the new psutil shape on this platform too).
        import subprocess
        import sys
        import time
        from bin.harness import _platform
        # Parent spawns a child via Python that just sleeps.
        parent_code = (
            "import subprocess, sys, time; "
            "p = subprocess.Popen([sys.executable, '-c', "
            "'import time; time.sleep(60)']); "
            "print(p.pid, flush=True); "
            "time.sleep(60)")
        parent = subprocess.Popen(
            [sys.executable, "-c", parent_code],
            stdout=subprocess.PIPE)
        try:
            child_pid_line = parent.stdout.readline().strip()
            child_pid = int(child_pid_line)
            # Let psutil settle.
            time.sleep(0.2)
            self.assertTrue(
                _platform.pid_alive(parent.pid),
                f"parent {parent.pid} should be alive")
            self.assertTrue(
                _platform.pid_alive(child_pid),
                f"child {child_pid} should be alive")
            # Now tree-kill from the parent.
            _platform.kill_process_tree(parent.pid, force=True)
            # Reap the parent so its pid no longer appears as a
            # zombie (POSIX-only; on Windows TerminateProcess
            # cleanly removes the entry). psutil.is_running()
            # returns True for zombies; the kill is real but
            # the OS hasn't yet been told to drop the entry.
            try:
                parent.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            # Now both should be dead. Allow brief settle for
            # the orphaned child whose parent (now reaped) is
            # init / launchd.
            for _ in range(30):
                if (not _platform.pid_alive(parent.pid)
                        and not _platform.pid_alive(child_pid)):
                    break
                time.sleep(0.1)
            self.assertFalse(
                _platform.pid_alive(parent.pid),
                f"parent {parent.pid} should be dead after "
                f"tree-kill + wait")
            self.assertFalse(
                _platform.pid_alive(child_pid),
                f"child {child_pid} should be dead after "
                f"tree-kill (pre-182 the Windows leg killed "
                f"only the leader; the child would survive).")
        finally:
            # Defensive cleanup.
            try:
                parent.kill()
            except Exception:
                pass
            try:
                parent.wait(timeout=2)
            except Exception:
                pass


class SkillBundleHarnessOnlyDepTests(unittest.TestCase):
    """v1.5.7 182: psutil is a harness-ONLY dependency. The
    QPB skill bundle MUST NOT depend on it because skill
    bundles install into arbitrary target repos and extra
    deps pollute the target's install. This test fails the
    build at commit time if `import psutil` or `from psutil
    import ...` slips into any skill-bundled artifact.

    Lands BEFORE the actual psutil imports (commit 3/5 of
    182) so the isolation guard is in place before the deps
    arrive — defense-in-depth against accidental leak."""

    SKILL_FILES = [
        "bin/run_playbook.py",          # skill entry point
        "bin/install_skill.py",         # bundler — MUST NOT
                                        # bundle psutil INTO the
                                        # skill
        ".github/skills/quality-playbook/SKILL.md",
        ".github/skills/quality-playbook/quality_gate.py",
    ]

    def _check_no_psutil_import(self, path) -> None:
        if not path.is_file():
            self.skipTest(f"{path} not present in this layout")
        src = path.read_text(encoding="utf-8")
        # Allow comment / docstring mentions; disallow actual
        # imports.
        import re
        # Look for ``import psutil`` or ``from psutil ...`` at
        # the START of any line (after optional whitespace) —
        # but NOT inside a comment.
        for lineno, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.match(r"^(import psutil|from psutil)\b",
                        stripped):
                self.fail(
                    f"{path}:{lineno} imports psutil — that's "
                    f"a skill-bundle dep leak. psutil is "
                    f"harness-only (instruction 182). Move the "
                    f"call into bin/harness/_platform.py or use "
                    f"a stdlib alternative.")

    def test_182_psutil_does_not_leak_into_skill_bundle(
            self) -> None:
        for rel in self.SKILL_FILES:
            self._check_no_psutil_import(_REPO / rel)

    def test_182_psutil_not_in_references_dir(self) -> None:
        # references/ holds skill reference docs (markdown
        # mostly, but some .py); if any python file there
        # imports psutil, the skill could pick it up at
        # runtime via reference_docs_ingest paths.
        refs = _REPO / "references"
        if not refs.is_dir():
            self.skipTest("references/ not present")
        for f in refs.rglob("*.py"):
            self._check_no_psutil_import(f)

    def test_182_psutil_not_in_skill_bundle_install_dir(
            self) -> None:
        # The skill bundle when installed lives under
        # .github/skills/quality-playbook/. Sweep every .py
        # under it.
        skill_dir = (
            _REPO / ".github" / "skills" / "quality-playbook"
        )
        if not skill_dir.is_dir():
            self.skipTest("skill bundle dir not present")
        for f in skill_dir.rglob("*.py"):
            self._check_no_psutil_import(f)


class PidIsAliveConsolidationTests(unittest.TestCase):
    """v1.5.7 180-followup-10 FINDING-20: plan_runner._pid_is_alive
    is consolidated to delegate to _platform.pid_alive. The
    pre-fix body used os.kill(pid, 0) which on Windows returns
    False for every pid because CPython's os.kill only accepts
    SIGTERM / CTRL_C_EVENT / CTRL_BREAK_EVENT — anything else
    raises OSError(ERROR_INVALID_PARAMETER) which the bare
    `except OSError: return False` swallowed. Andrew's 6th
    Windows fire saw 4/4 runs marked DONE+FAILED within
    seconds because of this."""

    def test_plan_runner_pid_is_alive_is_platform_pid_alive(
            self) -> None:
        from bin.harness import plan_runner
        from bin.harness import _platform
        self.assertIs(
            plan_runner._pid_is_alive,
            _platform.pid_alive,
            "plan_runner._pid_is_alive must be the "
            "_platform.pid_alive function (FINDING-20 "
            "consolidation). Pre-fix the local body used "
            "os.kill(pid, 0) which is broken on Windows.")

    def test_no_residual_os_kill_zero_in_plan_runner(
            self) -> None:
        # The OLD POSIX-only liveness pattern. Post-fix the
        # body is gone; the literal `os.kill(pid, 0)` MUST
        # NOT reappear in plan_runner.py.
        src = (_REPO / "bin" / "harness" / "plan_runner.py"
               ).read_text(encoding="utf-8")
        self.assertNotIn(
            "os.kill(pid, 0)", src,
            "plan_runner.py contains POSIX-only "
            "os.kill(pid, 0); use _platform.pid_alive "
            "instead (FINDING-20). CPython's os.kill on "
            "Windows raises OSError for any sig that isn't "
            "SIGTERM / CTRL_C_EVENT / CTRL_BREAK_EVENT.")

    def test_no_def_pid_is_alive_in_plan_runner(self) -> None:
        # The function body should be GONE — only the alias
        # import remains. Catches a regression where someone
        # re-introduces the POSIX-only helper.
        src = (_REPO / "bin" / "harness" / "plan_runner.py"
               ).read_text(encoding="utf-8")
        self.assertNotIn(
            "def _pid_is_alive(", src,
            "plan_runner.py still defines _pid_is_alive "
            "locally; should be an aliased import from "
            "_platform (FINDING-20).")


class GitLongPathsTests(unittest.TestCase):
    """v1.5.7 180-followup-10 FINDING-21: git clone invocations
    pass ``-c core.longpaths=true`` to handle Windows MAX_PATH
    (260-char limit) fixtures. Webpack's asset-modules test
    fixtures exceed 260 chars when checked out under
    ``harness_runs/<ts>/run-NN/target/`` and crash the clone
    with ``unable to create file ...: Filename too long``."""

    def test_prepare_clone_passes_core_longpaths_true(
            self) -> None:
        src = (_REPO / "bin" / "harness" / "prepare.py"
               ).read_text(encoding="utf-8")
        self.assertIn(
            "core.longpaths=true", src,
            "prepare.py must pass core.longpaths=true to git "
            "invocations for Windows MAX_PATH defensive "
            "coverage (FINDING-21).")

    def test_prepare_git_helper_uses_minus_c_form(
            self) -> None:
        # The ``-c <key>=<value>`` form is per-invocation
        # (no persistent operator-config change). Source-pin
        # that the flag appears with the ``-c`` form, not as
        # a `git config core.longpaths true` mutation.
        src = (_REPO / "bin" / "harness" / "prepare.py"
               ).read_text(encoding="utf-8")
        self.assertIn(
            '"-c", "core.longpaths=true"', src,
            "FINDING-21 flag MUST be passed via the per-"
            "invocation `-c <key>=<value>` form, not as a "
            "persistent config mutation.")


class TuiCursesFallbackTests(unittest.TestCase):
    """v1.5.7 180-followup-5 FINDING-7: ``import curses`` is not
    available on Windows Python; tui.py must detect the failure
    and degrade to the ``--dump runs`` non-interactive renderer
    with a clear install hint."""

    def test_180_tui_curses_import_guarded_with_dump_fallback(
            self) -> None:
        src = (
            _REPO / "bin" / "harness" / "tui.py"
        ).read_text(encoding="utf-8")
        # The `import curses` inside launch_status_tui must be in
        # a try/except that handles the Windows path. Source-pin:
        # within 1500 chars of the first `import curses`, expect
        # both ``IS_WINDOWS`` and ``format_runs_list_as_text``
        # (the fallback renderer).
        idx = src.find("import curses")
        self.assertGreater(idx, 0)
        window = src[max(0, idx - 200):idx + 1500]
        self.assertIn(
            "IS_WINDOWS", window,
            "tui.py launch_status_tui must guard `import "
            "curses` with an IS_WINDOWS branch + dump fallback")
        self.assertIn(
            "format_runs_list_as_text", window,
            "tui.py Windows fallback must use "
            "format_runs_list_as_text",
        )

    def test_180_tui_smoke_imports_cleanly(self) -> None:
        # Import smoke test: bin.harness.tui must import without
        # error on every platform (the top-level module doesn't
        # touch curses; the curses import is inside
        # launch_status_tui).
        import importlib
        m = importlib.import_module("bin.harness.tui")
        self.assertTrue(hasattr(m, "launch_status_tui"))


class ComprehensiveSweepTests(unittest.TestCase):
    """v1.5.7 180-followup-5 FINDING-8: comprehensive source-
    inspection sweep. Every platform-conditional symbol use in
    non-test ``bin/*.py`` must be guarded for cross-platform
    safety. Fails at commit time if a new unguarded reference
    slips in.

    Guards accepted in the ±800-char window around each match:
    ``IS_WINDOWS``, ``popen_kwargs_detached``,
    ``spawn_detached``, ``acquire_file_lock``,
    ``resolve_executable``, ``get_tmp_dir``,
    ``get_orchestrator_log_path``, ``hasattr(signal``,
    ``AttributeError``, ``# Windows-OK`` annotation."""

    def _windowed_guards_present(
            self, src: str, match_start: int,
            match_end: int, guards: list) -> bool:
        start = max(0, match_start - 800)
        end = min(len(src), match_end + 800)
        window = src[start:end]
        return any(g in window for g in guards)

    def _iter_non_test_bin_py(self):
        for f in (_REPO / "bin").rglob("*.py"):
            if "test" in f.name:
                continue
            yield f

    # v1.5.7 180-followup-6 FINDING-9: inverse-membership check.
    # The prior enumerated-list approach (180-followup-5
    # FINDING-8) missed signal.SIGKILL — Andrew's 5th Windows
    # fire failed all 4 runs at launch. Methodology lesson #16:
    # for cross-platform symbol sweeps, enumerate the SMALLER
    # set (what's available on the constrained platform) and
    # flag anything outside it. The Windows-available signal
    # list is short and well-bounded.
    WINDOWS_AVAILABLE_SIGNALS = frozenset({
        "SIGABRT", "SIGFPE", "SIGILL", "SIGINT", "SIGSEGV",
        "SIGTERM", "SIGBREAK", "NSIG",
    })

    def test_180_no_unguarded_posix_signals_anywhere(
            self) -> None:
        import re
        # Match every signal.SIG* attribute access.
        pattern = re.compile(r"signal\.(SIG[A-Z][A-Z0-9_]*)\b")
        guards = ["AttributeError", "hasattr(signal",
                  "IS_WINDOWS", "# Windows-OK"]
        for f in self._iter_non_test_bin_py():
            src = f.read_text(encoding="utf-8")
            for m in pattern.finditer(src):
                sig_name = m.group(1)
                if sig_name in self.WINDOWS_AVAILABLE_SIGNALS:
                    continue  # Windows-portable; no guard
                if not self._windowed_guards_present(
                        src, m.start(), m.end(), guards):
                    self.fail(
                        f"{f}:signal.{sig_name} unguarded for "
                        f"Windows (POSIX-only — Windows-"
                        f"available set is "
                        f"{sorted(self.WINDOWS_AVAILABLE_SIGNALS)}). "
                        f"Need AttributeError catch / "
                        f"hasattr(signal,...) / IS_WINDOWS "
                        f"branch within ±800 chars.")

    def test_180_no_unguarded_start_new_session_true(
            self) -> None:
        import re
        pattern = re.compile(r"start_new_session\s*=\s*True")
        guards = ["popen_kwargs_detached", "IS_WINDOWS",
                  "# Windows-OK"]
        for f in self._iter_non_test_bin_py():
            src = f.read_text(encoding="utf-8")
            for m in pattern.finditer(src):
                if not self._windowed_guards_present(
                        src, m.start(), m.end(), guards):
                    self.fail(
                        f"{f}: unguarded "
                        f"start_new_session=True (route via "
                        f"_platform.popen_kwargs_detached or "
                        f"add IS_WINDOWS guard)")

    def test_180_no_unguarded_hardcoded_tmp_var_paths(
            self) -> None:
        import re
        pattern = re.compile(
            r'''["']/(tmp|var|proc|dev)/''')
        guards = ["get_tmp_dir", "IS_WINDOWS",
                  "get_orchestrator_log_path",
                  "# Windows-OK"]
        for f in self._iter_non_test_bin_py():
            src = f.read_text(encoding="utf-8")
            for m in pattern.finditer(src):
                if not self._windowed_guards_present(
                        src, m.start(), m.end(), guards):
                    self.fail(
                        f"{f}: hardcoded POSIX path "
                        f"{m.group(0)!r} (use "
                        f"_platform.get_tmp_dir() or annotate "
                        f"# Windows-OK)")

    def test_180_no_unguarded_posix_only_os_calls(
            self) -> None:
        import re
        pattern = re.compile(
            r"os\.(fork|setsid|setpgid|setpgrp|wait3|wait4"
            r"|chroot|chown|ttyname)\b")
        guards = ["spawn_detached", "IS_WINDOWS",
                  "popen_kwargs_detached", "# Windows-OK"]
        for f in self._iter_non_test_bin_py():
            src = f.read_text(encoding="utf-8")
            for m in pattern.finditer(src):
                if not self._windowed_guards_present(
                        src, m.start(), m.end(), guards):
                    self.fail(
                        f"{f}: POSIX-only os call "
                        f"{m.group(0)!r} unguarded "
                        f"(use _platform.spawn_detached or "
                        f"IS_WINDOWS guard)")

    def test_180_no_top_level_posix_only_module_imports(
            self) -> None:
        # ``import fcntl`` / ``from fcntl import ...`` at module
        # scope crashes Windows at import time. Helper modules
        # ARE allowed (we DO import fcntl inside function bodies
        # in _platform.py); the test catches only top-level
        # (start-of-line + no leading whitespace) imports.
        import re
        pattern = re.compile(
            r"^(import|from)\s+(fcntl|pwd|grp|resource|termios"
            r"|tty)\b", re.MULTILINE)
        for f in self._iter_non_test_bin_py():
            src = f.read_text(encoding="utf-8")
            for m in pattern.finditer(src):
                self.fail(
                    f"{f}: top-level POSIX-only import "
                    f"{m.group(0)!r} crashes Windows at "
                    f"import time. Move inside a function "
                    f"body or guard via IS_WINDOWS.")

    def test_180_no_top_level_windows_only_module_imports(
            self) -> None:
        import re
        pattern = re.compile(
            r"^(import|from)\s+(msvcrt|winreg)\b",
            re.MULTILINE)
        for f in self._iter_non_test_bin_py():
            src = f.read_text(encoding="utf-8")
            for m in pattern.finditer(src):
                self.fail(
                    f"{f}: top-level Windows-only import "
                    f"{m.group(0)!r} crashes POSIX at import "
                    f"time. Move inside a function body or "
                    f"guard via IS_WINDOWS.")


class PopenKwargsTests(unittest.TestCase):

    def test_180_popen_kwargs_detached_posix(self) -> None:
        if P.IS_WINDOWS:
            self.skipTest("POSIX-only behavior pin")
        kwargs = P.popen_kwargs_detached()
        self.assertEqual(
            kwargs.get("start_new_session"), True)

    def test_180_popen_kwargs_detached_windows(self) -> None:
        if not P.IS_WINDOWS:
            self.skipTest("Windows-only behavior pin")
        kwargs = P.popen_kwargs_detached()
        self.assertIn("creationflags", kwargs)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
