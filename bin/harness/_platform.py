"""v1.5.7 180: cross-platform abstractions for the harness.

Closes the Windows compatibility gap deferred earlier in
v1.5.7. The POSIX code paths are preserved exactly; Windows
paths use the platform-equivalent primitives. The symbol
mentions inside the table below are documentation only — the
actual call sites are inside ``IS_WINDOWS``-branched helpers
below (``# Windows-OK``):

| Concept                  | POSIX                          | Windows                                          |
| ------------------------ | ------------------------------ | ------------------------------------------------ |
| Temp dir                 | ``/tmp``                       | ``%TEMP%`` via ``tempfile.gettempdir()``         |
| Detached spawn           | ``os.fork()`` + ``setsid()``   | ``subprocess.Popen(creationflags=...)``          |
| New session for child    | ``start_new_session`` flag     | ``CREATE_NEW_PROCESS_GROUP``                     |
| Exclusive file lock      | ``fcntl.flock(LOCK_EX)``       | ``msvcrt.locking(LK_LOCK)``                      |
| Non-blocking lock probe  | ``fcntl.flock(LOCK_EX|LOCK_NB)`` | ``msvcrt.locking(LK_NBLCK)``                   |
| Release lock             | ``fcntl.flock(LOCK_UN)``       | ``msvcrt.locking(LK_UNLCK)``                     |

All POSIX-only / Windows-only module imports are deferred to
the helper bodies (NOT module-level) so a bare ``from
bin.harness import _platform`` succeeds on either platform.
The POSIX symbols mentioned in this docstring's table
(``os.fork``, ``os.setsid``, ``/tmp``, ``fcntl``,
``start_new_session``, ``SIGHUP``) are documentation, not
calls. The actual call sites are inside ``IS_WINDOWS``
branches below (Windows-OK by exclusion).
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
    # POSIX path: fork + setsid + dup2. The IS_WINDOWS branch
    # above returned early; this code only runs when not
    # IS_WINDOWS (Windows-OK by exclusion).
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
    """v1.5.7 180-followup-3 FINDING-4 / 182: cross-platform
    pid liveness check via psutil. Pre-182 implementations:

    - POSIX used ``os.kill(pid, 0)`` (the signal-0 idiom).
    - Windows used ctypes ``OpenProcess`` +
      ``GetExitCodeProcess``.

    psutil internally uses the same OS-native APIs but handles
    edge cases (zombie states, permission boundaries, pid 0
    sentinel) and exposes a cleaner contract. The 21-finding
    180 chain surfaced 4 process-management bugs (FINDING-9
    signal-default load-time bomb, FINDING-20 broken Windows
    os.kill, latent kill-tree-only-leader on Windows, latent
    hardcoded exit_code=-1 for orphans) — per methodology
    lesson #31, that's the bug count threshold at which
    library adoption is the right strategic answer.

    Returns True iff a process with this pid currently exists.
    Note: this does NOT defend against pid recycling — use
    ``pid_alive_with_identity`` for that (added by 182 commit
    4/5).
    """
    if pid is None or int(pid) <= 0:
        return False
    import psutil
    try:
        return psutil.Process(int(pid)).is_running()
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        # Process exists but we lack rights — treat as alive
        # (matches the pre-182 PermissionError → True behavior
        # for POSIX and the OpenProcess NULL-handle path
        # divergence on Windows).
        return True


def resolve_executable(name: str) -> str:
    """v1.5.7 180-followup-4 FINDING-5: cross-platform executable
    resolution. ``shutil.which`` returns the full path with
    extension on Windows (handles ``PATHEXT`` for ``.cmd`` /
    ``.bat`` / ``.exe``), which ``subprocess.Popen`` requires
    when ``shell=False`` — bare ``Popen(["npm", ...])`` raises
    ``WinError 2: The system cannot find the file specified``
    on Windows because ``CreateProcess`` does NOT extension-
    walk.

    Use for any subprocess invocation of an external CLI tool
    (npm / npx / git / claude / copilot / codex / cursor / node)
    that isn't already a full path. ``sys.executable`` is
    already a full path; ``shutil.which("python")`` etc. are
    fine too.

    Raises ``FileNotFoundError`` if the executable isn't on
    PATH; callers usually want to surface this immediately so
    the operator sees a clear "not installed" message.
    """
    import shutil
    resolved = shutil.which(name)
    if resolved is None:
        raise FileNotFoundError(
            f"executable {name!r} not found on PATH. "
            f"Check installation and PATH configuration."
        )
    return resolved


def kill_process_tree(pid: int, *, force: bool = True) -> None:
    """v1.5.7 180-followup-6 FINDING-9 / 182: cross-platform
    process-tree termination via psutil.

    Pre-182 the Windows leg used ``TerminateProcess`` on the
    leader pid only — descendants stayed alive. Andrew
    OBSERVED this in run 20260601T201924Z: command windows
    continued popping up well after the "failure" because
    node.exe / MCP / sub-shells were orphaned. The pre-182
    docstring's "acceptable for leader-driven runs"
    assumption was wrong — Windows AI CLIs spawn descendants
    that DO outlive the leader.

    psutil's ``children(recursive=True)`` walks the process
    tree via OS-native APIs (procfs on Linux, ``kqueue`` on
    macOS, ``Process32First/Next`` on Windows). The
    Windows leg now actually kills the tree.

    ``force=True`` (default) → ``proc.kill()`` (POSIX
    ``SIGKILL`` / Windows ``TerminateProcess``).
    ``force=False`` → ``proc.terminate()`` (POSIX
    ``SIGTERM`` / Windows still ``TerminateProcess`` — no
    signal distinction on Windows; preserved for API
    parity).

    Best-effort: any ``psutil.NoSuchProcess`` or
    ``psutil.AccessDenied`` is swallowed (the process may
    have exited between the liveness check and the kill
    call; tree-kill is operationally diagnostic — a missed
    descendant still leaves the leader dead, which is the
    main correctness contract).
    """
    if pid is None or int(pid) <= 0:
        return
    import psutil
    try:
        parent = psutil.Process(int(pid))
    except psutil.NoSuchProcess:
        return
    try:
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    for child in children:
        try:
            if force:
                child.kill()
            else:
                child.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    try:
        if force:
            parent.kill()
        else:
            parent.terminate()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


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
