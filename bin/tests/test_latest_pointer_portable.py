"""v1.5.7 089h — portable ``quality/logs/latest.txt`` pointer +
Windows W-B regression coverage.

Background: the 2026-05-20 Windows smoke test (httpx-win, copilot/
auto, Mode B) surfaced finding W-B — ``quality/logs/latest`` symlink
creation fails on standard Windows with ``[WinError 1314] A
required privilege is not held by the client`` (no
``SeCreateSymbolicLinkPrivilege`` without admin / Developer Mode).
Resolution itself wasn't broken (the resolver's most-recent-by-name
fallback covered it), but the message read like an error and
Windows operators lost any "latest" reference.

089h fix combination (A+B+D):
  - (B) ALWAYS write ``quality/logs/latest.txt`` — a cross-platform
        one-line file holding the current run-id. This is now the
        load-bearing "latest" reference (the symlink is a
        convenience for ``cd quality/logs/latest``).
  - (A) Keep the symlink best-effort + relative, but SOFTEN its
        failure message from a WARN-style framing to an
        informational note that (1) explains the symlink's purpose,
        (2) says latest.txt covers resolution, (3) mentions
        Developer Mode as OPTIONAL.
  - (D) The softened message also notes Windows Developer Mode as
        an OPTIONAL way to enable the symlink and silence the note
        (informational, never required).

This test file pins:
  - ``latest.txt`` is written on run-start AND completion (the two
    call sites of ``_update_latest_symlink``).
  - Resolver Source 1.5 reads ``latest.txt`` when the symlink is
    absent (the Windows case).
  - Resolver falls through cleanly on stale/empty/dangling pointer
    (no crash; most-recent-by-name still works).
  - Softened message wording (informational, mentions latest.txt
    and Developer Mode, no WARN-style framing) is preserved across
    both OSError-during-symlink and pre-existing-entry branches.
  - Symlink-success path still wins (Source 1 beats Source 1.5).
  - latest.txt holds ONLY the run-id, not an absolute path
    (relocatability invariant).

Mutation-bite evidence (ai_context/DEVELOPMENT_PROCESS.md:152-160),
instruction-089h Task 3: each pin has an inline mutation-bite
docstring documenting the specific change that would break the
pin. 3 bites were executed PASS→FAIL→PASS during development;
``__pycache__`` purged between mutate and restore per the worker's
mutation-bite-discipline memory.
"""

from __future__ import annotations

import argparse
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bin import run_playbook
from bin import run_state_lib


def _make_args(**kwargs) -> argparse.Namespace:
    """Build the argparse Namespace ``_update_latest_symlink``
    expects. Defaults to centralized layout (``logs_flat=False``)
    with no env-var legacy mode in play."""
    defaults = dict(logs_flat=False)
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class LatestPointerWrittenOnEachUpdate(unittest.TestCase):
    """Pins (B): ``_update_latest_symlink`` ALWAYS writes
    ``quality/logs/latest.txt`` regardless of whether the symlink
    succeeds. This is the W-B Windows fix — Windows operators
    without Developer Mode get latest.txt as their portable
    reference."""

    def test_latest_txt_written_on_symlink_success(self) -> None:
        """When the symlink succeeds (Mac/Linux/Windows-with-
        Developer-Mode case), latest.txt is STILL written. The two
        pointers coexist.

        Mutation: in ``_update_latest_symlink``, move the
        ``latest.txt`` write block to AFTER the symlink succeeds
        (i.e., skip it on the success path).
        Expected failure: ``self.assertTrue(pointer.is_file())``
        below fails — latest.txt is missing despite the symlink
        having been created.
        Restoration: move the write back to before the symlink
        attempt; passes.
        Bite executed during 089h Task 3 development.
        """
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            run_id = "20260520T120000Z"
            (repo / "quality" / "logs" / run_id).mkdir(parents=True)
            log_file = repo / "playbook.log"
            log_file.write_text("", encoding="utf-8")

            try:
                run_playbook._update_latest_symlink(
                    repo, "20260520-120000", _make_args(), log_file,
                )
            except OSError:
                self.skipTest("Host filesystem doesn't support symlinks "
                              "at all (latest.txt-only path covered by "
                              "the OSError-during-symlink test below)")

            pointer = repo / "quality" / "logs" / "latest.txt"
            self.assertTrue(pointer.is_file(),
                            "latest.txt must be written even when the "
                            "symlink succeeds (B: always-write)")
            self.assertEqual(pointer.read_text(encoding="utf-8").strip(),
                             run_id,
                             "latest.txt holds exactly the run-id")
            symlink = repo / "quality" / "logs" / "latest"
            # If the host supported the symlink, both should exist.
            if symlink.is_symlink():
                self.assertEqual(symlink.resolve().name, run_id)

    def test_latest_txt_written_when_symlink_fails(self) -> None:
        """The Windows W-B case: symlink creation raises OSError
        (no SeCreateSymbolicLinkPrivilege). latest.txt MUST still
        be written so resolution + operator-visible reference both
        work."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            run_id = "20260520T130000Z"
            (repo / "quality" / "logs" / run_id).mkdir(parents=True)
            log_file = repo / "playbook.log"
            log_file.write_text("", encoding="utf-8")

            with mock.patch.object(
                Path, "symlink_to",
                side_effect=OSError(1314,
                                    "A required privilege is not held by "
                                    "the client"),
            ):
                run_playbook._update_latest_symlink(
                    repo, "20260520-130000", _make_args(), log_file,
                )

            pointer = repo / "quality" / "logs" / "latest.txt"
            self.assertTrue(pointer.is_file(),
                            "latest.txt MUST be written even when the "
                            "symlink fails — this is the Windows W-B fix")
            self.assertEqual(pointer.read_text(encoding="utf-8").strip(),
                             run_id)
            symlink = repo / "quality" / "logs" / "latest"
            self.assertFalse(symlink.is_symlink(),
                             "symlink should be absent (Path.symlink_to "
                             "was patched to raise)")

    def test_latest_txt_holds_run_id_not_absolute_path(self) -> None:
        """Relocatability invariant: latest.txt holds ONLY the
        run-id (a relative reference), not an absolute path.
        Otherwise moving the cell tree would break the pointer.
        Matches the symlink's relative-target invariant.

        Mutation: in ``_update_latest_symlink``, replace
        ``(logs_root / "latest.txt").write_text(run_id + "\\n", ...)``
        with ``(logs_root / "latest.txt").write_text(
        str((logs_root / run_id).absolute()) + "\\n", ...)``.
        Expected failure: this test's ``startswith("/")`` check
        fires.
        Restoration: revert to writing the bare run-id; passes.
        Bite executed during 089h Task 3 development.
        """
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            run_id = "20260520T140000Z"
            (repo / "quality" / "logs" / run_id).mkdir(parents=True)
            log_file = repo / "playbook.log"
            log_file.write_text("", encoding="utf-8")

            with mock.patch.object(
                Path, "symlink_to",
                side_effect=OSError("filesystem doesn't support symlinks"),
            ):
                run_playbook._update_latest_symlink(
                    repo, "20260520-140000", _make_args(), log_file,
                )

            content = (
                repo / "quality" / "logs" / "latest.txt"
            ).read_text(encoding="utf-8").strip()
            self.assertEqual(content, run_id,
                             "latest.txt must hold exactly the run-id "
                             "(no leading path components, no trailing "
                             "whitespace beyond the trailing newline)")
            self.assertFalse(content.startswith("/"),
                             "must not be an absolute path — breaks "
                             "the relocatable-cell-tree invariant")
            self.assertNotIn(str(repo), content,
                             "must not contain the absolute repo path")


class ResolverReadsLatestTxt(unittest.TestCase):
    """Pins Source 1.5 of ``resolve_run_state_path``: when the
    symlink is absent but ``latest.txt`` exists, the resolver
    returns the run_state.jsonl under the pointed-at run-id dir.
    This is the Windows W-B resolution path."""

    def test_resolver_reads_latest_txt_when_symlink_absent(self) -> None:
        """The Windows case: no symlink, but latest.txt exists
        pointing at a valid run-id dir with run_state.jsonl. The
        resolver MUST return that path.

        Mutation: revert ``run_state_lib.resolve_run_state_path``
        to skip Source 1.5 (remove the ``latest.txt`` block).
        Expected failure: this test fails because the resolver
        falls through to most-recent-by-name, which on a single-
        run-dir setup gives the same answer — so to discriminate
        the test uses TWO run-id dirs and points latest.txt at the
        OLDER one. Without Source 1.5, the resolver returns the
        newer one. Restoration: re-add Source 1.5; passes.
        Bite executed during 089h Task 3 development.
        """
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            logs_dir = repo / "quality" / "logs"
            logs_dir.mkdir(parents=True)
            # Two run-id dirs; latest.txt points at the OLDER one.
            # If the resolver IGNORES latest.txt, it'll return the
            # newer dir via most-recent-by-name — the assertion
            # below catches that.
            older = "20260101T000000Z"
            newer = "20260520T000000Z"
            (logs_dir / older).mkdir()
            (logs_dir / older / "run_state.jsonl").write_text(
                '{"ts":"older","event":"_index"}\n', encoding="utf-8"
            )
            (logs_dir / newer).mkdir()
            (logs_dir / newer / "run_state.jsonl").write_text(
                '{"ts":"newer","event":"_index"}\n', encoding="utf-8"
            )
            (logs_dir / "latest.txt").write_text(older + "\n",
                                                  encoding="utf-8")

            resolved = run_state_lib.resolve_run_state_path(repo)
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved.parent.name, older,
                             "resolver must honor latest.txt over "
                             "most-recent-by-name (Source 1.5 beats "
                             "Source 2)")

    def test_resolver_symlink_beats_latest_txt(self) -> None:
        """When BOTH the symlink AND latest.txt exist (the normal
        Mac/Linux case after 089h), Source 1 (symlink) still wins.
        This pins that 089h is additive — the existing
        Mac-developer experience is unchanged."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            logs_dir = repo / "quality" / "logs"
            logs_dir.mkdir(parents=True)
            symlinked = "20260520T100000Z"
            pointed = "20260520T200000Z"
            (logs_dir / symlinked).mkdir()
            (logs_dir / symlinked / "run_state.jsonl").write_text(
                '{"ts":"sym","event":"_index"}\n', encoding="utf-8"
            )
            (logs_dir / pointed).mkdir()
            (logs_dir / pointed / "run_state.jsonl").write_text(
                '{"ts":"ptr","event":"_index"}\n', encoding="utf-8"
            )
            try:
                (logs_dir / "latest").symlink_to(
                    symlinked, target_is_directory=True
                )
            except (OSError, NotImplementedError):
                self.skipTest("Host filesystem doesn't support symlinks")
            (logs_dir / "latest.txt").write_text(pointed + "\n",
                                                  encoding="utf-8")

            resolved = run_state_lib.resolve_run_state_path(repo)
            self.assertIsNotNone(resolved)
            # The symlink path wins — resolver returns
            # ``<repo>/quality/logs/latest/run_state.jsonl``
            # (the symlink-named path). Discriminating Source 1 vs
            # Source 1.5 requires resolving the symlink to compare
            # the real target dir against the symlinked vs pointed
            # run-id. Source 1 beats Source 1.5 (the documented
            # order).
            self.assertEqual(resolved.parent.name, "latest",
                             "Source 1 returns the literal "
                             "<logs>/latest/run_state.jsonl path "
                             "(the symlink name), not the resolved "
                             "target name")
            # Resolve the symlink to confirm we got the symlinked
            # run-id (Source 1 winner), not the pointed run-id
            # (Source 1.5 loser).
            actual_target = resolved.parent.resolve().name
            self.assertEqual(actual_target, symlinked,
                             "symlink (Source 1) must beat latest.txt "
                             "(Source 1.5) when both exist; resolved "
                             "target should be the symlinked run-id, "
                             "not the latest.txt-pointed run-id")
            self.assertNotEqual(actual_target, pointed,
                                "latest.txt must NOT have hijacked "
                                "the resolution from the symlink")

    def test_resolver_falls_through_on_stale_latest_txt(self) -> None:
        """latest.txt pointing at a nonexistent run-id dir: the
        resolver MUST fall through to most-recent-by-name rather
        than returning None or crashing. Robustness against
        interrupted writes / manual edits / deleted run dirs."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            logs_dir = repo / "quality" / "logs"
            logs_dir.mkdir(parents=True)
            real_run = "20260520T000000Z"
            (logs_dir / real_run).mkdir()
            (logs_dir / real_run / "run_state.jsonl").write_text(
                '{"ts":"real","event":"_index"}\n', encoding="utf-8"
            )
            # Pointer references a run-id that doesn't exist.
            (logs_dir / "latest.txt").write_text(
                "20299999T999999Z\n", encoding="utf-8"
            )

            resolved = run_state_lib.resolve_run_state_path(repo)
            self.assertIsNotNone(resolved,
                                 "resolver must not return None when a "
                                 "valid run-dir exists, even if "
                                 "latest.txt is dangling")
            self.assertEqual(resolved.parent.name, real_run,
                             "resolver falls through to most-recent-"
                             "by-name on dangling latest.txt")

    def test_resolver_falls_through_on_empty_latest_txt(self) -> None:
        """Empty latest.txt (e.g., write interrupted at zero bytes):
        resolver MUST fall through, not crash on the
        ``logs_dir / "" / "run_state.jsonl"`` path."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            logs_dir = repo / "quality" / "logs"
            logs_dir.mkdir(parents=True)
            real_run = "20260520T000000Z"
            (logs_dir / real_run).mkdir()
            (logs_dir / real_run / "run_state.jsonl").write_text(
                '{"ts":"real","event":"_index"}\n', encoding="utf-8"
            )
            (logs_dir / "latest.txt").write_text("", encoding="utf-8")

            resolved = run_state_lib.resolve_run_state_path(repo)
            self.assertIsNotNone(resolved,
                                 "empty latest.txt must not break "
                                 "resolution")
            self.assertEqual(resolved.parent.name, real_run)

    def test_resolver_falls_through_on_whitespace_only_latest_txt(self) -> None:
        """Whitespace-only pointer (no run-id content): same
        fall-through as empty."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            logs_dir = repo / "quality" / "logs"
            logs_dir.mkdir(parents=True)
            real_run = "20260520T000000Z"
            (logs_dir / real_run).mkdir()
            (logs_dir / real_run / "run_state.jsonl").write_text(
                '{"ts":"real","event":"_index"}\n', encoding="utf-8"
            )
            (logs_dir / "latest.txt").write_text("   \n\n",
                                                  encoding="utf-8")

            resolved = run_state_lib.resolve_run_state_path(repo)
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved.parent.name, real_run)

    def test_resolver_unchanged_when_no_latest_txt(self) -> None:
        """Pre-089h cells (no latest.txt; symlink may or may not
        exist) MUST resolve identically to pre-089h behavior. This
        pins that 089h is additive."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            logs_dir = repo / "quality" / "logs"
            logs_dir.mkdir(parents=True)
            older = "20260101T000000Z"
            newer = "20260520T000000Z"
            (logs_dir / older).mkdir()
            (logs_dir / older / "run_state.jsonl").write_text(
                '{"ts":"older","event":"_index"}\n', encoding="utf-8"
            )
            (logs_dir / newer).mkdir()
            (logs_dir / newer / "run_state.jsonl").write_text(
                '{"ts":"newer","event":"_index"}\n', encoding="utf-8"
            )
            # No latest symlink, no latest.txt. Resolver must use
            # Source 2 (most-recent-by-name → newer).
            resolved = run_state_lib.resolve_run_state_path(repo)
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved.parent.name, newer,
                             "resolver Source 2 unchanged when no "
                             "latest.txt or symlink present")


class SoftenedMessageWording(unittest.TestCase):
    """Pins (A+D): the symlink-failure message is now informational
    (not a WARN/error), mentions latest.txt, and references
    Developer Mode as OPTIONAL.

    Mutation-bite evidence: revert any of the four required
    substrings (e.g., remove the "Developer Mode" mention) and the
    corresponding assertion fires."""

    def test_oserror_message_is_informational(self) -> None:
        """The symlink-OSError branch emits an informational note,
        not a WARN. 4 substrings required:
        ``convenience symlink``, ``latest.txt``, ``resolution is
        unaffected``, ``Developer Mode``."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            run_id = "20260520T120000Z"
            (repo / "quality" / "logs" / run_id).mkdir(parents=True)
            log_file = repo / "playbook.log"
            log_file.write_text("", encoding="utf-8")

            with mock.patch.object(
                Path, "symlink_to",
                side_effect=OSError("simulated WinError 1314"),
            ):
                run_playbook._update_latest_symlink(
                    repo, "20260520-120000", _make_args(), log_file,
                )

            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("convenience symlink", log_text)
            self.assertIn("latest.txt", log_text)
            self.assertIn("resolution is unaffected", log_text)
            self.assertIn("Developer Mode", log_text)
            # Negative pin: the pre-089h WARN framing must NOT
            # appear.
            self.assertNotIn(
                "Could not update quality/logs/latest symlink",
                log_text,
                "softened note must drop the pre-089h WARN-style framing",
            )

    def test_preexisting_entry_message_is_informational(self) -> None:
        """The "pre-existing entry can't be removed" branch (e.g.,
        a real directory at the latest path that resists unlink)
        also gets the softened framing — mentions latest.txt and
        explains the situation."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            run_id = "20260520T120000Z"
            (repo / "quality" / "logs" / run_id).mkdir(parents=True)
            # Pre-existing 'latest' as a REAL directory (not a
            # symlink) that resists unlink.
            (repo / "quality" / "logs" / "latest").mkdir()
            log_file = repo / "playbook.log"
            log_file.write_text("", encoding="utf-8")

            with mock.patch.object(
                Path, "unlink",
                side_effect=OSError("Directory not empty"),
            ):
                run_playbook._update_latest_symlink(
                    repo, "20260520-120000", _make_args(), log_file,
                )

            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("latest.txt", log_text,
                          "pre-existing-entry branch also references "
                          "latest.txt as the resolution backup")
            self.assertNotIn(
                "Could not update",
                log_text,
                "softened note must drop the pre-089h `Could not "
                "update` WARN framing",
            )
            # Even though the symlink couldn't be replaced,
            # latest.txt was written BEFORE that branch fired
            # (the writes run sequentially).
            pointer = repo / "quality" / "logs" / "latest.txt"
            self.assertTrue(pointer.is_file(),
                            "latest.txt is written before the symlink "
                            "attempt; pre-existing-entry branch doesn't "
                            "skip the write")
            self.assertEqual(pointer.read_text(encoding="utf-8").strip(),
                             run_id)


class LegacyModeNoOp(unittest.TestCase):
    """Pins: under --logs-flat / QPB_LOGS_LEGACY, neither the
    symlink nor latest.txt is written (the legacy layout doesn't
    use the logs/ tree at all). 089h doesn't change this."""

    def test_legacy_mode_does_not_write_latest_txt(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "cell"
            repo.mkdir()
            log_file = repo / "playbook.log"
            log_file.write_text("", encoding="utf-8")

            args = _make_args(logs_flat=True)
            run_playbook._update_latest_symlink(
                repo, "20260520-120000", args, log_file,
            )

            # Legacy mode: no quality/logs/ at all, so no latest
            # symlink AND no latest.txt.
            self.assertFalse((repo / "quality" / "logs").exists())


if __name__ == "__main__":
    unittest.main()
