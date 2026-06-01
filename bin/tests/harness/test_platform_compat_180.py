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
