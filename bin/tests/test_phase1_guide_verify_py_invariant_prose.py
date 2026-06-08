"""v1.5.7 instruction 080 (W4 — addendum r3 §6): the Phase 1
generation guide now mandates `verify.py` (a subprocess-the-shell-
pipeline orchestrator) and names the v1.3.23 invariant explicitly,
and no longer references `verify.sh` in its active instruction text.

Pins the W4 prose contract so a future edit cannot silently revert
the Phase-1 mechanical-verification artifact to the bash form (or
drop the named invariant)."""

from __future__ import annotations

import unittest
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
# v1.5.8 instruction 208: references/ moved into the plugin skill folder.
_GUIDE = _QPB_ROOT / "skills" / "quality-playbook" / "references" / "phase1_exploration_guide.md"


class Phase1GuideVerifyPyInvariantProseTests(unittest.TestCase):

    def test_guide_mandates_verify_py_subprocess_invariant(self) -> None:
        """The guide names verify.py + the subprocess.run orchestrator
        pattern + the v1.3.23 invariant + the Python-reimplementation
        prohibition.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080 —
        BITE EXECUTED during instruction-080 development:
          Mutation: in references/phase1_exploration_guide.md revert
          the "**Reimplementing the extraction in Python … is
          FORBIDDEN**" sentence (delete the FORBIDDEN clause).
          Observed failure (purged __pycache__ first):
            FAIL: test_guide_mandates_verify_py_subprocess_invariant
            AssertionError: 'FORBIDDEN' not found in '<!-- D5
            (v1.5.7): moved from SKILL.md … [full phase1 guide
            text] …' : 'FORBIDDEN' not found in the phase1 guide :
            the W4 guide must forbid Python reimplementation of the
            extraction (v1.3.23 invariant)
          Restoration: guide byte-restored from pristine snapshot;
          test PASS again. (python-driven shutil.copy2 restore,
          __pycache__ purged between mutate and restore per
          feedback_mutation_bite_pycache.)
        """
        text = _GUIDE.read_text(encoding="utf-8")
        for needle, why in (
            ("verify.py", "the W4 mechanical artifact filename"),
            ("subprocess.run",
             "the orchestrator pattern (subprocess the shell pipeline)"),
            ("v1.3.23", "the named load-bearing invariant"),
            ("FORBIDDEN",
             "the W4 guide must forbid Python reimplementation of "
             "the extraction (v1.3.23 invariant)"),
        ):
            self.assertIn(needle, text,
                          f"{needle!r} not found in the phase1 guide : "
                          f"{why}")

    def test_guide_active_text_no_longer_references_verify_sh(self) -> None:
        """The active generation-instruction text must not reference
        `verify.sh` (W4 replaced it with verify.py). A forensic
        change-history mention would be acceptable, but the guide
        currently carries none — so a zero-occurrence assertion is
        the tight pin."""
        text = _GUIDE.read_text(encoding="utf-8")
        self.assertNotIn(
            "verify.sh", text,
            "references/phase1_exploration_guide.md still references "
            "`verify.sh` — W4 (instruction 080) replaced the Phase-1 "
            "mechanical artifact with `verify.py`. If a forensic "
            "change-history mention is later added intentionally, "
            "scope this assertion to the active instruction section.")


if __name__ == "__main__":
    unittest.main()
