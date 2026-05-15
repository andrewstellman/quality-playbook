"""Regression tests for the A-1 preservation invariant (v1.5.7
ship-blocker, instruction 042).

The defect: ``bin/run_playbook.archive_previous_run`` ran
``_clear_live_quality()`` unconditionally — even when
``archive_lib.archive_run()`` raised. On any archive failure
(timestamp collision, staging error, disk full, ...) the live
adopter artifact tree was destroyed without having been preserved.

The invariant pinned here: **``_clear_live_quality()`` runs ONLY when
the archive succeeded.** Any exception out of ``archive_run()`` —
``ArchiveError`` or otherwise — must leave the live ``quality/`` tree
intact and surface a warning.

Each test is mutation-verified (see the module-level note in the
instruction-042 output report for the exact bite procedure + results).
"""

from __future__ import annotations

import io
import os
import subprocess
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bin import archive_lib
from bin import run_playbook


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_git(repo: Path) -> None:
    subprocess.run(
        ["git", "init"], cwd=repo, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)


def _commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", message, "--allow-empty"],
        cwd=repo, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


# The full canonical artifact set the auto-archive must preserve.
# Relative to <repo>/quality/. Mirrors the Test C symptom inventory
# (BUGS.md / EXPLORATION.md / REQUIREMENTS.md / PROGRESS.md / role map
# / writeups / patches / code_reviews / spec_audits / mechanical /
# test files / centralized logs).
_SOURCE_TREE = {
    "BUGS.md": "# Bugs\n\n<!-- Quality Playbook v1.5.7 -->\n\n### BUG-001\n\n**Severity**: HIGH\n",
    "EXPLORATION.md": "# Exploration\n\nArea A\nArea B\nArea C\nArea D\n",
    "REQUIREMENTS.md": "# Requirements\n\n### REQ-001\n\n**Tier**: 1\nBody.\n",
    "PROGRESS.md": "## Phase completion\n\n- [x] Phase 1: Exploration\n- [x] Phase 2: Generation\n- [x] Phase 3\n",
    "CONTRACTS.md": "# Contracts\n\nC1\nC2\n",
    "COVERAGE_MATRIX.md": "# Coverage\n\n| REQ | test |\n|-----|------|\n",
    "QUALITY.md": "# Quality\n\nQ1\nQ2\n",
    "exploration_role_map.json": '{"version": 1, "breakdown": {}, "roles": {}}\n',
    "results/recheck-results.json": '{"ok": true}\n',
    "writeups/BUG-001.md": "# BUG-001 writeup\n\nDetail.\n",
    "patches/BUG-001-fix.patch": "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n",
    "code_reviews/pass1.md": "# Code review pass 1\n\nNotes.\n",
    "spec_audits/audit1.md": "# Spec audit 1\n\nNotes.\n",
    "mechanical/verify.sh": "#!/bin/sh\necho ok\n",
    "test_functional_test.go": "package q\n// functional stub\n",
    "test_regression_test.go": "package q\n// regression stub\n",
    "logs/20260515T110000Z/run_state.jsonl": '{"event": "run_start"}\n',
    "logs/20260515T110000Z/runner.log": "runner log line\n",
}

# Canonical INDEX.md whose run_timestamp_end pins the archive folder
# name deterministically (prior_ts -> 20260515T110000Z). Valid §11 JSON.
_INDEX_WITH_END = (
    "# Run Index\n\n```json\n"
    '{"qpb_version": "1.5.7",'
    ' "run_timestamp_start": "2026-05-15T10:30:00Z",'
    ' "run_timestamp_end": "2026-05-15T11:00:00Z",'
    ' "summary": {"bugs": {"HIGH": 1}, "gate_verdict": "partial"}}\n'
    "```\n"
)

# Legacy-stub INDEX.md: only run_timestamp_start. _prior_run_id_from_live_index
# returns None (it requires _end), so the early-return branch at
# run_playbook.py:2480 is skipped and the archive_run() try/except path
# (the one carrying the bug) is exercised.
_INDEX_START_ONLY = (
    "# Run Index\n\n```json\n"
    '{"qpb_version": "1.5.7",'
    ' "run_timestamp_start": "2026-05-15T10:30:00Z",'
    ' "summary": {"bugs": {"HIGH": 1}, "gate_verdict": "partial"}}\n'
    "```\n"
)

_LIVE_ARTIFACT_NAMES = (
    "BUGS.md", "EXPLORATION.md", "REQUIREMENTS.md", "PROGRESS.md",
    "CONTRACTS.md", "QUALITY.md", "exploration_role_map.json",
)


def _seed_source_tree(repo: Path, index_md: str) -> None:
    for rel, content in _SOURCE_TREE.items():
        _write(repo / "quality" / rel, content)
    _write(repo / "quality" / "INDEX.md", index_md)


class ArchivePreservationTests(unittest.TestCase):
    """Pins the A-1 invariant: live quality/ is destroyed ONLY after a
    successful archive. Instruction 042 (v1.5.7 ship-blocker)."""

    def test_archive_preserves_full_artifact_tree_happy_path(self) -> None:
        """Happy path: a fully-populated quality/ tree is archived
        completely (every file at the same relative path), the
        archive carries a valid §11 INDEX.md, and only then is the
        live tree cleared."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_git(repo)
            _seed_source_tree(repo, _INDEX_WITH_END)
            _commit(repo, "seed full live run")

            run_playbook.archive_previous_run(
                repo, current_run_timestamp="20260515T120000Z"
            )

            # prior_ts from INDEX.run_timestamp_end -> 20260515T110000Z
            archive = repo / "quality" / "previous_runs" / "20260515T110000Z"
            self.assertTrue(
                archive.is_dir(),
                f"archive folder {archive} must exist after a successful "
                f"archive (previous_runs children: "
                f"{list((repo / 'quality' / 'previous_runs').iterdir())})",
            )

            # EVERY source file present at the same relative path under
            # the archive's inner quality/ dir.
            for rel in _SOURCE_TREE:
                archived = archive / "quality" / rel
                self.assertTrue(
                    archived.is_file(),
                    f"archived tree is missing {rel} — the full artifact "
                    f"tree was NOT preserved (A-1 regression)",
                )

            # Archive's INDEX.md (sibling of the inner quality/ dir) is
            # valid §11 JSON.
            archive_index = archive / "INDEX.md"
            self.assertTrue(archive_index.is_file())
            payload = archive_lib.load_index_payload(archive_index)
            self.assertIsInstance(
                payload, dict,
                "archive INDEX.md must be parseable §11 JSON",
            )

            # Live quality/ cleared per _clear_live_quality: only the
            # archive subtrees + RUN_INDEX.md survive at top level.
            live_children = {
                c.name for c in (repo / "quality").iterdir()
            }
            self.assertEqual(
                live_children & {"BUGS.md", "EXPLORATION.md", "REQUIREMENTS.md"},
                set(),
                "live canonical artifacts should be cleared AFTER a "
                "successful archive",
            )
            self.assertIn("previous_runs", live_children)

    def test_archive_preserves_data_when_archive_target_collision(self) -> None:
        """Hypothesis H2 / the A-1 bug-fix invariant. When
        archive_run() raises ArchiveError because the archive target
        already exists, archive_previous_run must NOT clear the live
        tree. Conservative Option A: detect, warn, return — live data
        survives, the pre-existing collision target is untouched.

        Pre-fix this FAILS (the except path swallows the error then
        unconditionally clears). Post-fix this PASSES.
        """
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_git(repo)
            # _INDEX_START_ONLY -> prior_ts is None -> the early-return
            # branch is skipped and the archive_run() try/except (the
            # buggy path) is exercised.
            _seed_source_tree(repo, _INDEX_START_ONLY)
            _commit(repo, "seed live run for collision test")

            # Force a deterministic compute_archive_timestamp via
            # BUGS.md mtime (INDEX has no run_timestamp_end so the
            # timestamp chain falls to the BUGS.md mtime rung).
            bugs = repo / "quality" / "BUGS.md"
            fixed_epoch = 1747305600  # 2025-05-15T08:00:00Z (deterministic)
            os.utime(bugs, (fixed_epoch, fixed_epoch))
            expected_ts = datetime.fromtimestamp(
                fixed_epoch, tz=timezone.utc
            ).strftime("%Y%m%dT%H%M%SZ")

            # Pre-existing collision target with a stub the archive
            # must NOT overwrite or delete.
            collision = repo / "quality" / "previous_runs" / expected_ts
            collision.mkdir(parents=True)
            sentinel = collision / "DO_NOT_TOUCH.txt"
            sentinel.write_text("prior archive — different run\n", encoding="utf-8")

            buf = io.StringIO()
            with redirect_stderr(buf):
                run_playbook.archive_previous_run(
                    repo, current_run_timestamp="20260515T120000Z"
                )

            # 1. The pre-existing collision target is untouched.
            self.assertTrue(sentinel.is_file())
            self.assertEqual(
                sentinel.read_text(encoding="utf-8"),
                "prior archive — different run\n",
                "the pre-existing collision target must not be "
                "overwritten",
            )
            self.assertEqual(
                {c.name for c in collision.iterdir()},
                {"DO_NOT_TOUCH.txt"},
                "the collision target must not be repopulated with the "
                "live tree",
            )

            # 2. The live quality/ tree is INTACT — _clear_live_quality
            #    did NOT run.
            for name in _LIVE_ARTIFACT_NAMES:
                self.assertTrue(
                    (repo / "quality" / name).is_file(),
                    f"live quality/{name} was destroyed on archive "
                    f"collision — A-1 regression (destructive-on-error)",
                )

            # 3. A warning was surfaced explaining the collision.
            stderr = buf.getvalue()
            self.assertIn(
                "archive_previous_run", stderr,
                "a warning explaining the preserved-on-failure outcome "
                "must be emitted to stderr",
            )

    def test_archive_preserves_data_on_unexpected_exception(self) -> None:
        """Defensive: ANY exception out of archive_run() (not just
        ArchiveError) must leave the live tree intact and return
        gracefully rather than propagating or destroying data.

        Pre-fix this FAILS (RuntimeError propagates out of
        archive_previous_run, so the call raises). Post-fix the broad
        except returns gracefully and the live tree survives.
        """
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_git(repo)
            _seed_source_tree(repo, _INDEX_START_ONLY)
            _commit(repo, "seed live run for unexpected-exception test")

            buf = io.StringIO()
            with mock.patch.object(
                archive_lib, "archive_run",
                side_effect=RuntimeError("simulated archive failure"),
            ):
                with redirect_stderr(buf):
                    # Must NOT raise.
                    run_playbook.archive_previous_run(
                        repo, current_run_timestamp="20260515T120000Z"
                    )

            for name in _LIVE_ARTIFACT_NAMES:
                self.assertTrue(
                    (repo / "quality" / name).is_file(),
                    f"live quality/{name} was destroyed when archive_run "
                    f"raised RuntimeError — A-1 regression",
                )
            self.assertIn("archive_previous_run", buf.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
