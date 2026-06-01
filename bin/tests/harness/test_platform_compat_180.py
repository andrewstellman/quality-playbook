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

    def test_180_no_unguarded_posix_signal_attributes(
            self) -> None:
        import re
        posix_signals = [
            "SIGHUP", "SIGUSR1", "SIGUSR2", "SIGCHLD",
            "SIGPIPE", "SIGTTIN", "SIGTTOU", "SIGTSTP",
        ]
        pattern = re.compile(
            r"signal\.(" + "|".join(posix_signals) + r")\b")
        for f in (_REPO / "bin").rglob("*.py"):
            if "test" in f.name:
                continue
            src = f.read_text(encoding="utf-8")
            for m in pattern.finditer(src):
                start = max(0, m.start() - 600)
                end = min(len(src), m.end() + 600)
                window = src[start:end]
                self.assertTrue(
                    "AttributeError" in window
                    or "hasattr(signal" in window,
                    f"{f}:{m.group(0)} is unguarded for "
                    f"Windows. Surrounding window: "
                    f"{window[:400]}",
                )


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

    def test_180_no_unguarded_posix_signals_anywhere(
            self) -> None:
        import re
        posix_signals = [
            "SIGHUP", "SIGUSR1", "SIGUSR2", "SIGCHLD",
            "SIGPIPE", "SIGTTIN", "SIGTTOU", "SIGTSTP",
            "SIGWINCH", "SIGPROF", "SIGTRAP", "SIGBUS",
            "SIGSYS",
        ]
        pattern = re.compile(
            r"signal\.(" + "|".join(posix_signals) + r")\b")
        guards = ["AttributeError", "hasattr(signal",
                  "# Windows-OK"]
        for f in self._iter_non_test_bin_py():
            src = f.read_text(encoding="utf-8")
            for m in pattern.finditer(src):
                if not self._windowed_guards_present(
                        src, m.start(), m.end(), guards):
                    self.fail(
                        f"{f}:{m.group(0)} unguarded for "
                        f"Windows (need AttributeError catch "
                        f"or hasattr(signal,...) guard within "
                        f"±800 chars)")

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
