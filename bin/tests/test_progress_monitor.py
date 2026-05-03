"""Tests for bin/progress_monitor.py (v1.5.1 Item 2.2)."""

from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import progress_monitor


def _touch(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append(path: Path, content: str) -> None:
    # Bump mtime monotonically — some filesystems have 1s mtime
    # resolution, which would make "mtime changed" unreliable in a
    # sub-second test window.
    with path.open("a", encoding="utf-8") as handle:
        handle.write(content)
    now = time.time()
    import os as _os
    _os.utime(path, (now, now + 0.001))


class HeaderExtractionTests(unittest.TestCase):
    """Unit-test the header regex in isolation — no thread, no I/O."""

    def test_matches_top_and_second_level(self) -> None:
        monitor = _no_run_monitor()
        first = monitor._extract_new_headers(
            "# Run Start\n## Phase 1\n### Subsection\nregular line\n"
        )
        self.assertEqual(first, ["# Run Start", "## Phase 1"])

    def test_second_pass_returns_only_new_headers(self) -> None:
        monitor = _no_run_monitor()
        monitor._extract_new_headers("# One\n## Two\n")
        new = monitor._extract_new_headers("# One\n## Two\n## Three\n")
        self.assertEqual(new, ["## Three"])

    def test_ignores_deeper_and_non_header_lines(self) -> None:
        monitor = _no_run_monitor()
        out = monitor._extract_new_headers(
            "#not a header\n##also-no-space\n### Three-hash\nbullet\n# Real\n"
        )
        self.assertEqual(out, ["# Real"])


def _no_run_monitor() -> progress_monitor.ProgressMonitor:
    """Build a monitor without starting its thread."""
    with TemporaryDirectory() as tmp:
        return progress_monitor.ProgressMonitor(
            progress_path=Path(tmp) / "PROGRESS.md",
            log_file=Path(tmp) / "log.txt",
            emit=lambda _lf, _msg: None,
        )


class ProgressMonitorTests(unittest.TestCase):
    """Threaded tests with short poll intervals. Each test is bounded by
    an overall wait deadline so a broken thread can't hang the suite."""

    POLL_INTERVAL = 0.05
    DEADLINE_SECONDS = 3.0

    def _new_monitor(
        self, tmp: Path, *, verbose: bool = False, quiet: bool = False
    ) -> tuple[progress_monitor.ProgressMonitor, list[str], Path, Path]:
        progress = tmp / "PROGRESS.md"
        log_file = tmp / "log.txt"
        emitted: list[str] = []
        lock = threading.Lock()

        def emit(_log_file: Path, message: str) -> None:
            with lock:
                emitted.append(message)

        monitor = progress_monitor.ProgressMonitor(
            progress_path=progress,
            log_file=log_file,
            emit=emit,
            interval=self.POLL_INTERVAL,
            verbose=verbose,
            quiet=quiet,
        )
        return monitor, emitted, progress, log_file

    def _await(self, predicate) -> None:
        deadline = time.time() + self.DEADLINE_SECONDS
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        raise AssertionError("predicate never became true within deadline")

    def test_new_header_surfaces_within_one_poll(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted, progress, _log = self._new_monitor(Path(tmp))
            with monitor:
                _touch(progress, "# First Header\n")
                self._await(lambda: "# First Header" in emitted)

    def test_second_level_header_surfaces(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted, progress, _log = self._new_monitor(Path(tmp))
            with monitor:
                _touch(progress, "# First\n## Phase 1\n")
                self._await(lambda: "## Phase 1" in emitted)

    def test_third_level_header_ignored(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted, progress, _log = self._new_monitor(Path(tmp))
            with monitor:
                _touch(progress, "### Sub\nplain line\n")
                # Wait a few cycles then verify nothing surfaced.
                time.sleep(self.POLL_INTERVAL * 4)
            self.assertEqual(emitted, [])

    def test_does_not_reprint_existing_headers(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted, progress, _log = self._new_monitor(Path(tmp))
            with monitor:
                _touch(progress, "# One\n## Two\n")
                self._await(lambda: "## Two" in emitted)
                # A subsequent mtime bump without new headers must not
                # re-emit.
                before = list(emitted)
                _append(progress, "regular text\n")
                time.sleep(self.POLL_INTERVAL * 4)
            self.assertEqual(emitted, before)

    def test_rapid_successive_writes_do_not_drop_headers(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted, progress, _log = self._new_monitor(Path(tmp))
            with monitor:
                # Start with the initial header, then pile more on fast.
                _touch(progress, "# One\n")
                _append(progress, "## Two\n")
                _append(progress, "## Three\n")
                self._await(
                    lambda: {"# One", "## Two", "## Three"}.issubset(set(emitted))
                )

    def test_missing_progress_file_is_patient(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted, progress, _log = self._new_monitor(Path(tmp))
            with monitor:
                # Progress file doesn't exist yet; monitor must not raise.
                time.sleep(self.POLL_INTERVAL * 3)
                _touch(progress, "# Late Start\n")
                self._await(lambda: "# Late Start" in emitted)

    def test_quiet_suppresses_both_progress_and_transcript(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted, progress, _log = self._new_monitor(
                Path(tmp), quiet=True
            )
            transcript = Path(tmp) / "phase1.output.txt"
            with monitor:
                monitor.set_transcript_path(transcript)
                _touch(progress, "# One\n")
                _touch(transcript, "transcript line\n")
                time.sleep(self.POLL_INTERVAL * 6)
            self.assertEqual(emitted, [])

    def test_verbose_streams_new_transcript_lines(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted, _progress, _log = self._new_monitor(
                Path(tmp), verbose=True
            )
            transcript = Path(tmp) / "phase1.output.txt"
            with monitor:
                monitor.set_transcript_path(transcript)
                _touch(transcript, "line one\nline two\n")
                self._await(lambda: "line one" in emitted and "line two" in emitted)

    def test_verbose_picks_up_phase_rollover(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted, _progress, _log = self._new_monitor(
                Path(tmp), verbose=True
            )
            phase1 = Path(tmp) / "phase1.output.txt"
            phase2 = Path(tmp) / "phase2.output.txt"
            with monitor:
                monitor.set_transcript_path(phase1)
                _touch(phase1, "phase1 body\n")
                self._await(lambda: "phase1 body" in emitted)
                # Roll over to phase 2; monitor must switch streams.
                monitor.set_transcript_path(phase2)
                _touch(phase2, "phase2 body\n")
                self._await(lambda: "phase2 body" in emitted)

    def test_stop_joins_cleanly(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, _emitted, progress, _log = self._new_monitor(Path(tmp))
            _touch(progress, "# Starting\n")
            monitor.start()
            # Mimic the Ctrl-C path: set the event from outside and
            # verify the thread exits quickly.
            deadline = time.time() + self.DEADLINE_SECONDS
            monitor.stop(timeout=1.0)
            self.assertLess(time.time(), deadline)
            # Idempotent stop.
            monitor.stop(timeout=0.1)

    def test_context_manager_start_and_stop(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, _emitted, _progress, _log = self._new_monitor(Path(tmp))
            with monitor:
                self.assertIsNotNone(monitor._thread)
                self.assertTrue(monitor._thread.is_alive())
            self.assertIsNone(monitor._thread)

    def test_emit_exception_does_not_crash_thread(self) -> None:
        with TemporaryDirectory() as tmp:
            calls = {"count": 0}

            def boom(_lf: Path, _msg: str) -> None:
                calls["count"] += 1
                raise RuntimeError("simulated caller failure")

            monitor = progress_monitor.ProgressMonitor(
                progress_path=Path(tmp) / "PROGRESS.md",
                log_file=Path(tmp) / "log.txt",
                emit=boom,
                interval=self.POLL_INTERVAL,
            )
            with monitor:
                _touch(Path(tmp) / "PROGRESS.md", "# One\n## Two\n")
                self._await(lambda: calls["count"] >= 2)
                # Thread still alive — the exception did not kill it.
                self.assertTrue(monitor._thread.is_alive())


class ProgressMonitorHeartbeatTests(unittest.TestCase):
    """v1.5.1 Item 3.2: set_pacing / clear_pacing API + heartbeat emission.

    Uses direct _poll_once() invocation on a non-started monitor so the
    tests are deterministic and don't depend on thread timing."""

    def _monitor(self, tmp: Path, *, quiet: bool = False):
        emitted: list[str] = []
        monitor = progress_monitor.ProgressMonitor(
            progress_path=tmp / "PROGRESS.md",
            log_file=tmp / "log.txt",
            emit=lambda _lf, msg: emitted.append(msg),
            interval=0.05,
            quiet=quiet,
        )
        return monitor, emitted

    def test_set_pacing_nonzero_emits_heartbeat_once(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted = self._monitor(Path(tmp))
            monitor.set_pacing(60)
            monitor._poll_once()
            monitor._poll_once()  # subsequent polls must not re-emit
            heartbeats = [m for m in emitted if m.startswith("Pacing:")]
            self.assertEqual(len(heartbeats), 1)
            self.assertEqual(heartbeats[0], "Pacing: 60s before next prompt…")

    def test_set_pacing_zero_is_noop(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted = self._monitor(Path(tmp))
            monitor.set_pacing(0)
            monitor._poll_once()
            self.assertEqual([m for m in emitted if m.startswith("Pacing:")], [])

    def test_clear_pacing_stops_heartbeat(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted = self._monitor(Path(tmp))
            monitor.set_pacing(10)
            monitor._poll_once()
            monitor.clear_pacing()
            # Re-arm for a new pace interval; must emit again.
            monitor.set_pacing(20)
            monitor._poll_once()
            heartbeats = [m for m in emitted if m.startswith("Pacing:")]
            self.assertEqual(len(heartbeats), 2)
            self.assertEqual(heartbeats[0], "Pacing: 10s before next prompt…")
            self.assertEqual(heartbeats[1], "Pacing: 20s before next prompt…")

    def test_quiet_suppresses_heartbeat(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, emitted = self._monitor(Path(tmp), quiet=True)
            monitor.set_pacing(30)
            monitor._poll_once()
            self.assertEqual([m for m in emitted if m.startswith("Pacing:")], [])

    def test_idempotent_clear(self) -> None:
        with TemporaryDirectory() as tmp:
            monitor, _emitted = self._monitor(Path(tmp))
            monitor.clear_pacing()
            monitor.clear_pacing()  # no exception

    def test_heartbeat_format_matches_briefing(self) -> None:
        """Ensure the literal format from the briefing is unchanged
        ('Pacing: Ns before next prompt…' with ellipsis U+2026)."""
        with TemporaryDirectory() as tmp:
            monitor, emitted = self._monitor(Path(tmp))
            monitor.set_pacing(42)
            monitor._poll_once()
            self.assertIn("Pacing: 42s before next prompt…", emitted)


class TranscriptByteOffsetTests(unittest.TestCase):
    """v1.5.5 BUG-002: _poll_transcript must keep byte offsets consistent.

    The previous implementation opened the transcript in text mode, seeked
    by a byte offset (from path.stat().st_size), read characters, then
    re-encoded with len(chunk.encode("utf-8")) to advance the offset. On
    any non-ASCII content the text-mode decode-with-errors='replace' and
    the byte-vs-char seek interpretation drift apart, skipping or
    repeating lines on subsequent polls. The fix opens in binary mode and
    keeps every offset on this path as bytes throughout.
    """

    def _no_thread_monitor(self, tmp: Path):
        emitted: list[str] = []
        monitor = progress_monitor.ProgressMonitor(
            progress_path=tmp / "PROGRESS.md",
            log_file=tmp / "log.txt",
            emit=lambda _lf, msg: emitted.append(msg),
            interval=0.05,
        )
        return monitor, emitted

    def test_tailing_handles_utf8_multibyte_content(self) -> None:
        """A UTF-8 multi-byte character split across two writes must not
        desync the offset, and complete lines on either side must be
        emitted intact. Reproduces BUG-002."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            transcript = tmp / "phase.output.txt"
            # First write ends in the middle of a 3-byte em-dash
            # (U+2014 = e2 80 94 — only the first two bytes flushed).
            first_chunk = (
                "line1 ✓ checkmark\nline2 partial ".encode("utf-8") + b"\xe2\x80"
            )
            transcript.write_bytes(first_chunk)

            monitor, emitted = self._no_thread_monitor(tmp)
            monitor.set_transcript_path(transcript)
            monitor._poll_transcript()

            # First complete line must surface intact.
            self.assertIn("line1 ✓ checkmark", emitted)
            # Offset MUST equal actual byte size — no drift from the
            # trailing partial multi-byte. Old code produced a replacement
            # char from the 2 orphan bytes and re-encoded it as 3 bytes,
            # drifting +1 per partial.
            self.assertEqual(
                monitor._transcript_offset,
                len(first_chunk),
                f"byte offset desynced from file size: monitor at "
                f"{monitor._transcript_offset}, file at {len(first_chunk)} "
                f"bytes (BUG-002 — text-mode read with errors='replace' "
                f"re-encodes orphan bytes as full 3-byte replacement chars)",
            )

            # Complete the em-dash and append a clean third line.
            rest = b"\x94 finished\nline3 done\n"
            with transcript.open("ab") as handle:
                handle.write(rest)

            emitted.clear()
            monitor._poll_transcript()

            # Third line must surface — proves no bytes were skipped.
            self.assertIn("line3 done", emitted)
            # Offset still pinned to actual file size.
            self.assertEqual(
                monitor._transcript_offset,
                len(first_chunk) + len(rest),
                "second-poll byte offset diverged from file size",
            )

    def test_offset_increment_is_byte_count(self) -> None:
        """Static guard: a future edit must not change the increment to a
        character count. The fix keeps offsets in bytes everywhere on the
        transcript-tailing path."""
        import inspect
        import re

        source = inspect.getsource(progress_monitor.ProgressMonitor._poll_transcript)

        # Forbid `new_offset = offset + len(chunk)` where chunk is a str:
        # that would count characters, not bytes.
        forbidden = re.compile(r"new_offset\s*=\s*offset\s*\+\s*len\(\s*chunk\s*\)")
        self.assertIsNone(
            forbidden.search(source),
            "_poll_transcript must NOT increment offset by len(chunk) — "
            "chunk is a decoded str and len(chunk) counts characters, not "
            "bytes (BUG-002 regression).",
        )

        # And require some byte-aware increment to exist (fix uses len(raw)
        # on the bytes object; alternative would be chunk.encode('utf-8')).
        self.assertTrue(
            "len(raw)" in source or 'encode("utf-8"' in source or "encode('utf-8'" in source,
            "_poll_transcript must increment offset using a byte-length "
            "source (len(raw) on bytes, or chunk.encode('utf-8')).",
        )

        # And the file must be opened in binary mode on this path.
        self.assertIn(
            '"rb"',
            source,
            "_poll_transcript must open the transcript in binary mode "
            "(\"rb\") so seek() uses byte offsets (BUG-002 fix).",
        )


if __name__ == "__main__":
    unittest.main()
