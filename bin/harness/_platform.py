"""v1.5.7 180: cross-platform abstractions for the harness.

Closes the Windows compatibility gap deferred earlier in
v1.5.7. The POSIX code paths are preserved exactly; Windows
paths use the platform-equivalent primitives:

| Concept                  | POSIX                          | Windows                                          |
| ------------------------ | ------------------------------ | ------------------------------------------------ |
| Temp dir                 | ``/tmp``                       | ``%TEMP%`` via ``tempfile.gettempdir()``         |
| Detached spawn           | ``os.fork()`` + ``setsid()``   | ``subprocess.Popen(creationflags=...)``          |
| New session for child    | ``start_new_session=True``     | ``CREATE_NEW_PROCESS_GROUP``                     |
| Exclusive file lock      | ``fcntl.flock(LOCK_EX)``       | ``msvcrt.locking(LK_LOCK)``                      |
| Non-blocking lock probe  | ``fcntl.flock(LOCK_EX|LOCK_NB)`` | ``msvcrt.locking(LK_NBLCK)``                   |
| Release lock             | ``fcntl.flock(LOCK_UN)``       | ``msvcrt.locking(LK_UNLCK)``                     |

All POSIX-only / Windows-only module imports are deferred to
the helper bodies (NOT module-level) so a bare ``from
bin.harness import _platform`` succeeds on either platform.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence


IS_WINDOWS: bool = sys.platform == "win32"


def get_tmp_dir() -> Path:
    """Return a Path to the OS temp directory. POSIX: usually
    ``/tmp``. Windows: ``%TEMP%``. Existence guaranteed by
    stdlib."""
    return Path(tempfile.gettempdir())


def get_orchestrator_log_path(run_id: str) -> Path:
    """Path for the orchestrator's auto-detach log:
    ``<tmpdir>/qpb-harness-<run_id>.log``."""
    return get_tmp_dir() / f"qpb-harness-{run_id}.log"


def popen_kwargs_detached() -> dict:
    """Popen kwargs that detach the child from the parent's
    session/console. POSIX: ``{"start_new_session": True}``.
    Windows: ``{"creationflags": DETACHED_PROCESS |
    CREATE_NEW_PROCESS_GROUP}``.

    Used by ``_spawn_collector`` and ``_spawn_watchdog`` to
    spread into their ``subprocess.Popen`` call:

        subprocess.Popen(args, **popen_kwargs_detached(), ...)
    """
    if IS_WINDOWS:
        # subprocess.DETACHED_PROCESS / CREATE_NEW_PROCESS_GROUP
        # only exist on Windows builds of Python's subprocess
        # module. Lazy access via getattr in case of CI quirks.
        flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess,
                       "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )
        return {"creationflags": flags}
    return {"start_new_session": True}


def spawn_detached(
        args: "Sequence[str]",
        log_path: "Optional[Path]" = None,
        env: "Optional[dict]" = None) -> int:
    """Spawn a fully-detached subprocess and return a pid.

    POSIX: forks. In the PARENT, returns the child's pid. In the
    CHILD, returns 0 — and BEFORE returning 0 the helper has
    already called ``setsid()``, dup2'd stdio to ``log_path``
    (when provided), and exported the environment overrides.
    Caller uses the classic Unix pattern::

        pid = spawn_detached(...)
        if pid != 0:
            # parent — banner + return
            return 0
        # child — continue inline

    Windows: launches ``subprocess.Popen(args, ...)`` with
    ``creationflags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP``,
    stdout/stderr redirected to ``log_path`` (when provided),
    and ``env`` if specified. Returns the child's pid; the
    parent never sees a 0 return. The "child code" must be
    reachable by the child's command line — typically the child
    re-runs the same ``qpb_harness run-plan ...`` invocation
    with a marker env var (``QPB_HARNESS_DETACHED=1``) so the
    spawn block is skipped on re-entry.

    The behavioral contract is the same on both platforms:
      * The returned pid identifies a live, detached process.
      * The parent process is free to exit; the child
        continues.
      * ``log_path`` receives the child's stdout/stderr.
    """
    if IS_WINDOWS:
        # On Windows we cannot fork — the only path is Popen.
        # The child runs `args` from scratch with `env` (which
        # the caller should populate with QPB_HARNESS_DETACHED
        # so the child's re-entry skips the spawn block).
        log_fp = None
        try:
            if log_path is not None:
                log_fp = open(log_path, "ab")
                stdout = log_fp
                stderr = subprocess.STDOUT
            else:
                stdout = subprocess.DEVNULL
                stderr = subprocess.DEVNULL
            proc = subprocess.Popen(
                list(args),
                stdout=stdout,
                stderr=stderr,
                stdin=subprocess.DEVNULL,
                env=env,
                **popen_kwargs_detached(),
            )
            return int(proc.pid)
        finally:
            if log_fp is not None:
                try:
                    log_fp.close()
                except OSError:
                    pass
    # POSIX path: fork + setsid + dup2.
    log_fp = None
    if log_path is not None:
        log_fp = open(log_path, "ab")
    try:
        pid = os.fork()
    except OSError:
        if log_fp is not None:
            log_fp.close()
        raise
    if pid != 0:
        # Parent.
        if log_fp is not None:
            log_fp.close()
        return pid
    # Child.
    try:
        os.setsid()
    except OSError:
        pass  # already session leader
    if log_fp is not None:
        try:
            os.dup2(log_fp.fileno(), sys.stdout.fileno())
            os.dup2(log_fp.fileno(), sys.stderr.fileno())
        finally:
            log_fp.close()
    if env:
        for k, v in env.items():
            os.environ[k] = str(v)
    return 0


# ---------------------------------------------------------------------------
# File locks
# ---------------------------------------------------------------------------


def acquire_file_lock(fp, blocking: bool = True) -> bool:
    """Acquire an exclusive lock on the file represented by
    ``fp``. POSIX: ``fcntl.flock(fp.fileno(), LOCK_EX [| LOCK_NB
    if not blocking])``. Windows: ``msvcrt.locking(fp.fileno(),
    LK_LOCK if blocking else LK_NBLCK, N)``.

    Returns True if lock acquired; False if ``blocking=False``
    and the lock is held by another OFD. Raises OSError on real
    failure (e.g., bad fd)."""
    if IS_WINDOWS:
        import msvcrt
        mode = (msvcrt.LK_LOCK if blocking
                else msvcrt.LK_NBLCK)
        # msvcrt.locking requires a non-zero byte count and
        # locks bytes starting from the current file position.
        # Seek to 0 + lock 1 byte gives the same coordination
        # semantic as fcntl.flock (file-level exclusive).
        try:
            fp.seek(0)
        except OSError:
            pass
        try:
            msvcrt.locking(fp.fileno(), mode, 1)
            return True
        except OSError:
            if not blocking:
                return False
            raise
    import fcntl
    op = fcntl.LOCK_EX
    if not blocking:
        op = op | fcntl.LOCK_NB
    try:
        fcntl.flock(fp.fileno(), op)
        return True
    except BlockingIOError:
        if not blocking:
            return False
        raise


def pid_alive(pid: int) -> bool:
    """v1.5.7 180-followup-3 FINDING-4: cross-platform pid
    liveness check. Used by the orchestrator's spawn-then-verify
    pattern — after ``spawn_detached`` returns a child pid, the
    parent confirms the child is still alive before declaring
    "this shell can close safely."

    POSIX: ``os.kill(pid, 0)`` — raises ``ProcessLookupError``
    if dead, ``PermissionError`` if alive but we lack signal
    rights (treated as alive). Other ``OSError`` → False.

    Windows: ``OpenProcess`` + ``GetExitCodeProcess`` via
    ctypes. A process whose exit code is ``STILL_ACTIVE`` (259)
    is alive; any other exit code means it terminated. A
    ``NULL`` handle from ``OpenProcess`` means dead-or-
    inaccessible — treated as dead (operator surfaces error).
    """
    if pid is None or pid <= 0:
        return False
    if IS_WINDOWS:
        import ctypes
        STILL_ACTIVE = 259
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        h = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        try:
            exit_code = ctypes.c_ulong(0)
            ok = kernel32.GetExitCodeProcess(
                h, ctypes.byref(exit_code))
            if not ok:
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(h)
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def release_file_lock(fp) -> None:
    """Release the lock held on ``fp``. POSIX:
    ``fcntl.flock(LOCK_UN)``. Windows:
    ``msvcrt.locking(LK_UNLCK, N)``. Idempotent; safe to call
    on an unlocked fp (swallows OSError)."""
    if IS_WINDOWS:
        import msvcrt
        try:
            fp.seek(0)
        except OSError:
            pass
        try:
            msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        return
    import fcntl
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
