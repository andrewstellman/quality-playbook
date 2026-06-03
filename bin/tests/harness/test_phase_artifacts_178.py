"""v1.5.7 178 — Phase 0 setup detection for early-Phase-1 Mode A
runs. Surfaced on harness_runs/20260531T234613Z where Mode A
runs showed phase=— for 5-10 minutes while doing real work,
because PHASE_ARTIFACTS only keyed on Phase-1-DONE artifact
(EXPLORATION.md) — earlier markers (PROGRESS.md, RUN_INDEX.md,
formal_docs_manifest.json from the doc-gathering step) were
ignored.

178 adds a Phase 0 entry as belt-and-suspenders for the SKILL.md
mandate-strengthening (Fix A) — even if an agent misbehaves and
doesn't emit ``qpb_phase 1 start`` as its first tool call, Tier 3
artifact fallback now catches the early indicators.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from bin.harness.phase_artifacts import (  # noqa: E402
    PHASE_ARTIFACTS, infer_phase_from_artifacts,
)


class PhaseZeroEntryTests(unittest.TestCase):

    def test_178_phase_artifacts_has_phase_0_entry(self) -> None:
        """PHASE_ARTIFACTS must include Phase 0 with at least one
        early-setup indicator."""
        self.assertIn(
            0, PHASE_ARTIFACTS,
            "PHASE_ARTIFACTS must have a Phase 0 entry for "
            "early-run detection",
        )
        p0 = PHASE_ARTIFACTS[0]
        self.assertTrue(
            any(name in p0
                for name in ("PROGRESS.md", "RUN_INDEX.md",
                              "formal_docs_manifest.json")),
            f"Phase 0 entry must include at least one early-"
            f"setup artifact (PROGRESS.md / RUN_INDEX.md / "
            f"formal_docs_manifest.json); got {p0!r}",
        )


class InferPhaseZeroTests(unittest.TestCase):

    def test_178_infer_phase_reports_zero_on_early_artifacts_only(
            self) -> None:
        """When only Phase 0 artifacts are present (no
        EXPLORATION.md yet), infer_phase_from_artifacts returns 0
        — not None. Pre-178: None ⇒ status shows phase=—; post-
        178: 0 ⇒ status shows P0/setup."""
        with tempfile.TemporaryDirectory() as tmp:
            quality_dir = Path(tmp) / "quality"
            quality_dir.mkdir()
            (quality_dir / "PROGRESS.md").write_text(
                "setup", encoding="utf-8")
            result = infer_phase_from_artifacts(quality_dir)
            self.assertEqual(
                result, 0,
                f"Expected infer_phase_from_artifacts to return "
                f"0 when only Phase 0 artifacts present; got "
                f"{result!r}",
            )

    def test_178_higher_phase_still_wins_over_phase_zero(
            self) -> None:
        """Phase 0 fires only when nothing higher is detected.
        With Phase 1's EXPLORATION.md present, infer must still
        return 1 (highest-wins semantic preserved per 168)."""
        with tempfile.TemporaryDirectory() as tmp:
            quality_dir = Path(tmp) / "quality"
            quality_dir.mkdir()
            # Both Phase 0 (PROGRESS.md) and Phase 1
            # (EXPLORATION.md) present.
            (quality_dir / "PROGRESS.md").write_text(
                "setup", encoding="utf-8")
            (quality_dir / "EXPLORATION.md").write_text(
                "x", encoding="utf-8")
            result = infer_phase_from_artifacts(quality_dir)
            self.assertEqual(
                result, 1,
                "highest-phase-wins must hold: Phase 1 takes "
                "precedence over Phase 0 when both are present",
            )

    def test_178_no_artifacts_still_returns_none(self) -> None:
        """An empty quality dir still returns None (not 0).
        Phase 0 fires only when at least one P0 artifact is
        present."""
        with tempfile.TemporaryDirectory() as tmp:
            quality_dir = Path(tmp) / "quality"
            quality_dir.mkdir()
            result = infer_phase_from_artifacts(quality_dir)
            self.assertIsNone(result)


class StatusDisplayPhaseZeroTests(unittest.TestCase):
    """status.py renders Phase 0 with name="prep" + state=
    "running" (NOT "done" — Phase 0 in the new model is implicit
    setup, never "done" as a discrete phase)."""

    def test_178_status_renders_phase_zero_as_prep_running(
            self) -> None:
        import tempfile
        from bin.harness import status as ST  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            quality_dir = target / "quality"
            quality_dir.mkdir()
            (quality_dir / "PROGRESS.md").write_text(
                "setup", encoding="utf-8")
            inferred = ST._infer_phase_from_artifacts(target)
            self.assertIsNotNone(inferred)
            self.assertEqual(inferred["phase"], 0)
            self.assertIn(inferred["name"], ("prep", "setup"))
            self.assertEqual(inferred["state"], "running")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
