"""v1.5.7 instruction 089p (#329 follow-up) — drift guard tying the
`references/what_just_happened.md` recap's TDD-not-executed
detection strings to the actual strings `quality_gate.py` emits.

The 089p cross-cutting augmentation in `what_just_happened.md`
tells the agent to grep `quality/results/quality-gate.log` for a
fixed set of literal strings — the gate messages 089m's NOT_RUN
WARN and 089o's overclaim / phase5_env FAILs emit. If a future
instruction rewords one of those gate messages WITHOUT updating
the recap doc, the recap's detection silently rots: the agent
greps for a string the gate no longer prints, the TDD-not-
executed callout never fires, and the buried signal stays buried
— exactly the failure 089p exists to fix. State S (Rule 6) and
State CN (Rule 7) carry the same class of risk; this test is the
089p analogue of the guard they implicitly rely on.

Each string in `_DETECTION_STRINGS` must appear verbatim in BOTH
`.github/skills/quality_gate/quality_gate.py` (the emitter) AND
`references/what_just_happened.md` (the recap that greps for it).

**Mutation-bite evidence** (per ai_context/DEVELOPMENT_PROCESS.md):
reword any one emitted string in `quality_gate.py` — e.g. change
``"TDD red/green cycle not executed for"`` to ``"TDD cycle was
not run for"`` — WITHOUT updating `what_just_happened.md`. Expected
failure: `test_detection_strings_present_in_quality_gate` fails
because the old string is no longer in `quality_gate.py`. Restore
→ passes. Bite executed PASS → FAIL → PASS during 089p
development.
"""

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# v1.5.8 instruction 208: quality_gate.py + references/ moved into
# skills/quality-playbook/.
_SKILL_DIR = REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
QUALITY_GATE = _SKILL_DIR / "scripts" / "quality_gate.py"
WHAT_JUST_HAPPENED = _SKILL_DIR / "references" / "what_just_happened.md"


# The literal gate-log substrings the 089p recap augmentation
# greps for. Each is a stable fragment of a message emitted by
# quality_gate.py's check_tdd_logs — 089m's NOT_RUN WARN and
# 089o's overclaim / phase5_env FAILs. These are SUBSTRINGS, not
# whole lines (the full messages interpolate counts / bug ids),
# chosen to be the invariant part a reword would most likely
# disturb.
_DETECTION_STRINGS = (
    # 089m NOT_RUN WARN.
    "TDD red/green cycle not executed for",
    # 089o overclaim FAIL — per-receipt.
    "but body admits non-execution",
    # 089o overclaim FAIL — rolled-up count.
    "TDD receipt(s) overclaim",
    # 089o phase5_env.log missing FAIL.
    "phase5_env.log is missing",
    # 089o NOT_RUN-but-runner-available FAIL.
    "phase5_env.log shows the test runner IS available",
)


class RecapTddSignalDrift089pTests(unittest.TestCase):
    """Pin the 089p recap detection strings to both their emitter
    (quality_gate.py) and their consumer (what_just_happened.md)."""

    def test_quality_gate_source_present(self) -> None:
        self.assertTrue(
            QUALITY_GATE.is_file(),
            f"quality_gate.py must exist at {QUALITY_GATE}",
        )

    def test_what_just_happened_source_present(self) -> None:
        self.assertTrue(
            WHAT_JUST_HAPPENED.is_file(),
            f"what_just_happened.md must exist at {WHAT_JUST_HAPPENED}",
        )

    def test_detection_strings_present_in_quality_gate(self) -> None:
        """Every recap detection string must appear verbatim in
        quality_gate.py — i.e. the gate actually emits it. If this
        fails, a gate message was reworded; update both
        quality_gate.py's message AND the matching string in
        what_just_happened.md + this test's _DETECTION_STRINGS."""
        gate_src = QUALITY_GATE.read_text(encoding="utf-8")
        for needle in _DETECTION_STRINGS:
            self.assertIn(
                needle, gate_src,
                f"089p drift guard: the recap-detection string "
                f"{needle!r} is no longer emitted by "
                f"quality_gate.py. A gate message was reworded "
                f"without updating the recap. The "
                f"what_just_happened.md TDD-not-executed "
                f"augmentation will silently stop firing — "
                f"re-sync the string in quality_gate.py, "
                f"what_just_happened.md, and _DETECTION_STRINGS.",
            )

    def test_detection_strings_present_in_what_just_happened(self) -> None:
        """Every detection string must also appear verbatim in
        what_just_happened.md — i.e. the recap actually tells the
        agent to grep for it. Catches a recap doc that drifts away
        from the gate (the opposite direction)."""
        recap_src = WHAT_JUST_HAPPENED.read_text(encoding="utf-8")
        for needle in _DETECTION_STRINGS:
            self.assertIn(
                needle, recap_src,
                f"089p drift guard: the gate-log string {needle!r} "
                f"is not referenced in what_just_happened.md's "
                f"TDD-execution augmentation. The recap must tell "
                f"the agent to grep for every signal the gate "
                f"emits, or that signal stays buried.",
            )

    def test_augmentation_section_exists(self) -> None:
        """what_just_happened.md must carry the cross-cutting
        augmentation section header (the 089p deliverable)."""
        recap_src = WHAT_JUST_HAPPENED.read_text(encoding="utf-8")
        self.assertIn(
            "Cross-cutting augmentation — TDD execution status",
            recap_src,
            "089p: what_just_happened.md must contain the "
            "cross-cutting TDD-execution augmentation section.",
        )
        # It must NOT be wired into the first-match-wins classifier
        # table (it is a modifier, not a state — halt condition).
        self.assertNotIn(
            "TDD execution status |", recap_src,
            "089p: the TDD-execution augmentation must NOT be a "
            "row in the first-match-wins classifier table — it is "
            "a cross-cutting modifier that composes with B/CN/I/F, "
            "never a state that shadows them.",
        )


if __name__ == "__main__":
    unittest.main()
