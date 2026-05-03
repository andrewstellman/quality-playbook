"""progress_monitor.py — background monitor that surfaces run progress to stdout.

v1.5.1 Item 2.2. Closes the observability gap the virtio-1.4.6 rerun
(2026-04-19) surfaced: the orchestrator updated quality/PROGRESS.md only
at phase boundaries, the live per-phase transcript carried the real-time
signal, and operators had to tail a second file by hand from another
terminal to see any mid-phase progress.

Design (docs/design/QPB_v1.5.1_Design.md Item 4):

  - Default: a polling thread watches quality/PROGRESS.md. When the file
    mtime changes, re-read and surface any new top-level (#) or
    second-level (##) headers via logboth(). Deeper headers (### and
    below) are intentionally ignored — they add noise without adding
    phase-level information.

  - --verbose: add a second watcher that tails the current phase's
    transcript (the per-phase output file written by
    bin.run_playbook.run_prompt). All new lines are surfaced, not just
    headers. The transcript path changes on phase rollover; the
    orchestrator calls set_transcript_path() on each phase boundary.

  - --quiet: suppress both watchers. Phase-boundary announcements still
    reach stdout via direct logboth() calls from the orchestrator.

Threading hygiene:

  - daemon=True so an interpreter exit never blocks on the monitor.
  - threading.Event-based shutdown so wait() can be interrupted
    immediately; no time.sleep() polling that can't be aborted.
  - Context-manager interface (__enter__/__exit__) so every start is
    paired with a stop+join in a try/finally-equivalent pattern.
  - Shared current_transcript_path is protected by a lock; the main
    thread writes it, the monitor thread reads it.

Stdlib-only.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Callable, List, Optional


# "#" or "##" followed by a space. "###" and deeper are skipped.
_HEADER_RE = re.compile(r"^##?\s")


class ProgressMonitor:
    """Poll quality/PROGRESS.md (and optionally the live phase transcript)
    and surface new content through a caller-supplied emit() function.

    Production usage passes emit=lib.logboth-wrapped-in-a-closure so
    output lands in both stdout (subject to --no-stdout-echo) and the
    run log file. Tests inject a lambda that appends to a list.
    """

    # Public attributes read by tests; treat as read-only.
    progress_path: Path
    interval: float
    verbose: bool
    quiet: bool

    def __init__(
        self,
        progress_path: Path,
        log_file: Path,
        emit: Callable[[Path, str], None],
        *,
        interval: float = 2.0,
        verbose: bool = False,
        quiet: bool = False,
    ) -> None:
        self.progress_path = Path(progress_path)
        self._log_file = Path(log_file)
        self._emit = emit
        self.interval = float(interval)
        self.verbose = bool(verbose)
        self.quiet = bool(quiet)

        self._shutdown = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # State tracked across poll cycles.
        self._last_progress_mtime: float = 0.0
        self._printed_headers: set[str] = set()

        # Shared transcript-path state: main thread writes on phase
        # rollover, monitor thread reads. Guarded by a lock so the main
        # thread's swap is atomic from the monitor's point of view.
        self._transcript_lock = threading.Lock()
        self._transcript_path: Optional[Path] = None
        self._transcript_offset: int = 0

        # v1.5.1 Item 3.2: idle heartbeat during --pace-seconds waits.
        # The orchestrator calls set_pacing(seconds) before sleeping and
        # clear_pacing() after. The monitor thread emits a single line
        # per pacing interval so operators don't think the run hung.
        self._pacing_seconds: int = 0
        self._pacing_announced: bool = False

    # --- context-manager + lifecycle ---------------------------------

    def __enter__(self) -> "ProgressMonitor":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run_loop,
            name="qpb-progress-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal shutdown and join. Idempotent."""
        self._shutdown.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

    # --- transcript path (phase rollover) ----------------------------

    def set_transcript_path(self, path: Optional[Path]) -> None:
        """Swap the transcript this monitor tails. Called on phase
        rollover. Resets the read offset so the new phase's content
        is streamed from the top."""
        with self._transcript_lock:
            self._transcript_path = Path(path) if path is not None else None
            self._transcript_offset = 0

    # --- pacing heartbeat (Phase 3 Item 3.2) -------------------------

    def set_pacing(self, seconds: int) -> None:
        """Arm the idle heartbeat for a pacing wait of ``seconds``.

        v1.5.1 Item 3.2. The orchestrator calls this before entering
        time.sleep(pace_seconds). The monitor thread emits a single
        ``Pacing: Ns before next prompt…`` line on its next poll and
        then stays quiet until the orchestrator calls clear_pacing().

        ``seconds <= 0`` is a no-op — zero pacing means nothing to
        announce.
        """
        with self._transcript_lock:
            if seconds > 0:
                self._pacing_seconds = int(seconds)
                self._pacing_announced = False
            else:
                self._pacing_seconds = 0
                self._pacing_announced = False

    def clear_pacing(self) -> None:
        """Disarm the pacing heartbeat. Idempotent."""
        with self._transcript_lock:
            self._pacing_seconds = 0
            self._pacing_announced = False

    # --- main loop ---------------------------------------------------

    def _run_loop(self) -> None:
        # self._shutdown.wait(interval) returns True when set, False on
        # timeout. We poll first (so a short interval still gives an
        # initial read) and then wait the interval before the next poll.
        while True:
            try:
                self._poll_once()
            except Exception as exc:  # noqa: BLE001 — monitor must not crash the run
                self._safe_emit(f"WARN: progress monitor exception: {exc}")
            if self._shutdown.wait(self.interval):
                return

    def _poll_once(self) -> None:
        # v1.5.1 Item 3.2: emit the pacing heartbeat before either
        # content watcher runs so a quiet/non-verbose run still sees
        # the heartbeat during a pacing wait. --quiet still suppresses
        # it — operators who asked for no stdout output get none.
        if not self.quiet:
            self._emit_pacing_heartbeat()
        if self.quiet:
            return
        self._poll_progress()
        if self.verbose:
            self._poll_transcript()

    def _emit_pacing_heartbeat(self) -> None:
        with self._transcript_lock:
            pacing = self._pacing_seconds
            already = self._pacing_announced
            if pacing > 0 and not already:
                self._pacing_announced = True
                announce = pacing
            else:
                announce = 0
        if announce:
            self._safe_emit(f"Pacing: {announce}s before next prompt…")

    def _poll_progress(self) -> None:
        path = self.progress_path
        if not path.is_file():
            return
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if mtime == self._last_progress_mtime:
            return
        self._last_progress_mtime = mtime
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        new_headers = self._extract_new_headers(content)
        for header in new_headers:
            self._safe_emit(header)

    def _extract_new_headers(self, content: str) -> List[str]:
        headers: List[str] = []
        for line in content.splitlines():
            stripped = line.rstrip()
            if not stripped:
                continue
            if not _HEADER_RE.match(stripped):
                continue
            if stripped in self._printed_headers:
                continue
            self._printed_headers.add(stripped)
            headers.append(stripped)
        return headers

    def _poll_transcript(self) -> None:
        with self._transcript_lock:
            path = self._transcript_path
            offset = self._transcript_offset
        if path is None or not path.is_file():
            return
        try:
            size = path.stat().st_size
        except OSError:
            return
        if size <= offset:
            # File shrank (shouldn't happen on phase files) or no new
            # content. Reset offset on shrink so we pick up the next write.
            if size < offset:
                with self._transcript_lock:
                    # Only reset if the path hasn't changed since we read it.
                    if self._transcript_path == path:
                        self._transcript_offset = 0
            return
        try:
            # Binary mode keeps every offset on this path in bytes:
            # stat().st_size is bytes, but text-mode seek() expects char
            # positions, which desync on UTF-8 multi-byte content (em-dash,
            # ✓, emoji, accented chars) and cause skipped/repeated lines.
            with path.open("rb") as handle:
                handle.seek(offset)
                raw = handle.read()
        except OSError:
            return
        chunk = raw.decode("utf-8", errors="replace")
        new_offset = offset + len(raw)
        with self._transcript_lock:
            # Only commit the offset if the path is still the one we read.
            if self._transcript_path == path:
                self._transcript_offset = new_offset
        for line in chunk.splitlines():
            if line.strip():
                self._safe_emit(line.rstrip())

    def _safe_emit(self, message: str) -> None:
        try:
            self._emit(self._log_file, message)
        except Exception:  # noqa: BLE001 — never crash the monitor thread
            pass
