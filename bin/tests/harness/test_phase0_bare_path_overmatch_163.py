"""v1.5.7 163 — diagnose haiku's `phase0_first_probe=False`.

Investigation finding (per the review-request): the witnesses at
``harness_runs/20260530T134322Z/run-00/target/quality/`` show a
CLEAN remediation sequence (blocked → remediable → ok), exactly
what 141's prefix-scoped first_probe_ok=True logic should accept.
Code stream parsing also recovers the same 3-probe sequence. The
bug was in ``_RE_PHASE0_BARE_PATH_FAIL``: its second alternative
``\\[Errno 2\\] No such file or directory.*qpb_validate``
over-matched on ABSOLUTE paths whose tail happened to contain
``qpb_validate`` (the empirical case: agent fumbled the install
target dir and tried
``…/run-00/.claude/skills/quality-playbook/bin/qpb_validate.py``
instead of ``…/target/.claude/…``). The over-match wrongly set
``bare_path_fail=True``, which suppressed ``first_probe_ok``.

The fix tightens the second alternative to require a
RELATIVE/BARE ``bin/qpb_validate.py`` reference (not preceded by
a path separator) — matching only the canonical bare-path bug
pattern, not a coincidental substring inside a full path.

Path 1 from the instruction (probe-detection bug). Worker
recommends keeping the assertion as-is (no plan-side relaxation
needed for haiku); fix the detection.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from bin.harness import facts as F


# ---------------------------------------------------------------------------
# Bare-path-fail regex semantics
# ---------------------------------------------------------------------------


class BarePathFailRegexTests(unittest.TestCase):

    def test_canonical_bare_path_fail_still_matches(self) -> None:
        # 138/141 canonical pattern — preserved. Real streams
        # encode the traceback inline (the regex requires the
        # python3 line and FileNotFoundError on the same logical
        # line because `.` doesn't match newlines).
        text = (
            "python3 bin/qpb_validate.py . — Traceback: "
            "FileNotFoundError: bin/qpb_validate.py")
        self.assertTrue(
            F._RE_PHASE0_BARE_PATH_FAIL.search(text))

    def test_bare_errno_pattern_still_matches(self) -> None:
        # The Errno 2 variant ALSO needs to keep firing when the
        # path is bare/relative.
        text = ("$ python3 bin/qpb_validate.py .\n"
                "[Errno 2] No such file or directory: "
                "'bin/qpb_validate.py'\n")
        self.assertTrue(
            F._RE_PHASE0_BARE_PATH_FAIL.search(text))

    def test_absolute_path_with_qpb_validate_substring_does_NOT_match(
            self) -> None:
        # The bug (163): pre-163 this matched because the regex
        # was `[Errno 2].*qpb_validate` and the greedy `.*` swept
        # across to the qpb_validate substring inside the absolute
        # path. Post-163: require the bin/qpb_validate.py reference
        # to NOT be preceded by a path separator. Mutation-bite:
        # reverting to the broad `.*qpb_validate` regex makes this
        # test fail.
        text = (
            "Error: Exit code 2 — Python: can't open file "
            "'/Users/x/harness_runs/20260530T134322Z/run-00/"
            ".claude/skills/quality-playbook/bin/qpb_validate.py': "
            "[Errno 2] No such file or directory"
        )
        # This is a TARGET-RESOLUTION bug (agent looked under
        # run-00/.claude/... instead of run-00/target/.claude/...),
        # NOT a bare-path-fail. The phase-0 detection should leave
        # bare_path_fail=False so the witnesses can drive the
        # first_probe_ok computation.
        self.assertFalse(
            F._RE_PHASE0_BARE_PATH_FAIL.search(text),
            "absolute path with qpb_validate substring should NOT "
            "trip bare_path_fail")

    def test_absolute_path_in_error_message_before_bin_does_not_match(
            self) -> None:
        # Variant of the absolute-path case — even more emphasis
        # that the slash directly before bin/ disqualifies the
        # match (the bare-path-fail signature has bin/qpb_validate
        # at the start of a word/token).
        text = ("FileNotFoundError: [Errno 2] No such file or "
                "directory: '/path/to/skills/bin/qpb_validate.py'")
        self.assertFalse(
            F._RE_PHASE0_BARE_PATH_FAIL.search(text))


# ---------------------------------------------------------------------------
# Real-world empirical regression — the 13:43:22Z run-00 case
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parents[3]


class RealWorldRun00HaikuRegressionTests(unittest.TestCase):
    """The empirical proof: the 2026-05-30 13:43:22Z run-00 (gson
    claude/haiku) had a clean (blocked → remediable → ok) witness
    sequence; pre-163 code computed first_probe_ok=False because
    the bare-path-fail regex over-matched on the agent's mis-located
    absolute-path error. Post-163: first_probe_ok=True."""

    def _target(self):
        p = (_REPO_ROOT
             / "harness_runs/20260530T134322Z/run-00/target")
        return p if p.is_dir() else None

    def test_run_00_haiku_classifies_first_probe_ok_true(
            self) -> None:
        target = self._target()
        if target is None:
            self.skipTest(
                "harness_runs/20260530T134322Z/run-00/target not on "
                "disk (pruned)")
        stream = (target.parent / "stream.ndjson")
        if not stream.is_file():
            self.skipTest(
                "stream.ndjson not on disk; can't reproduce")
        transcript = stream.read_text(errors="ignore")
        phase0, *_ = F.parse_transcript(
            transcript, target_dir=target)
        self.assertEqual(phase0.status, "ok")
        self.assertEqual(phase0.probe_attempts, 3)
        # LOAD-BEARING: pre-163 this was False because the
        # bare_path_fail over-match suppressed the first_probe_ok
        # computation.
        self.assertTrue(phase0.first_probe_ok)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
