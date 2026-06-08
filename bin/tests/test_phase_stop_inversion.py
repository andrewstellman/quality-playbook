"""v1.5.7 instruction 089b F11 regression: the 5 per-phase
boundary instructions must DEFAULT-CONTINUE (the A-28 full-pipeline
default from 087), not unconditionally STOP. Round 1 live-test:
virtio (Claude Code sonnet) stopped after Phase 2 because the
per-phase reference STOP prose contradicted AGENTS.md's
full-pipeline default — local prose won.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
# The 3 files carrying the 5 per-phase boundary instructions
# (phase1_exploration_guide → P2, phase2_generation_guide → P3,
# SKILL.md → P4/P5/P6).
# v1.5.8 instruction 208: references/ + SKILL.md moved into the plugin skill folder.
_SKILL_DIR = _QPB_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
_LOCI = (
    _SKILL_DIR / "references" / "phase1_exploration_guide.md",
    _SKILL_DIR / "references" / "phase2_generation_guide.md",
    _SKILL_DIR / "SKILL.md",
)
# The old unconditional-STOP phrasing (the F11 defect): "STOP. Do
# not proceed to Phase N unless the user explicitly asks".
_OLD_STOP = re.compile(
    r"STOP\. Do not proceed to Phase [1-6] unless the user "
    r"explicitly asks")
# The inverted default-continue phrasing (the F11 fix).
_NEW_CONTINUE = re.compile(
    r"continue automatically to Phase [1-6] unless the operator "
    r"invoked you for the current phase only")


class PhaseStopInversionTests(unittest.TestCase):
    """Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED
    during instruction-089b development:
      Mutation: revert SKILL.md's after-Phase-5 boundary line back
        to `**After printing this message, STOP. Do not proceed to
        Phase 6 unless the user explicitly asks.**`.
      Observed failure (purged __pycache__ first):
        FAIL: test_no_unconditional_stop_phrasing_remains
        AssertionError: unconditional-STOP phrasing reverted in
          SKILL.md (089b F11 regression): ['STOP. Do not proceed to
          Phase 6 unless the user explicitly asks']
      Mutation reverted; test passes.
    """

    def test_no_unconditional_stop_phrasing_remains(self) -> None:
        for p in _LOCI:
            txt = p.read_text(encoding="utf-8")
            hits = _OLD_STOP.findall(txt)
            self.assertEqual(
                hits, [],
                f"unconditional-STOP phrasing reverted in {p.name} "
                f"(089b F11 regression): {hits}. Per-phase boundary "
                f"instructions must DEFAULT-CONTINUE (A-28 "
                f"full-pipeline default); STOP only for single-phase "
                f"operator invocations.")

    def test_inverted_default_continue_present_at_all_five_loci(self) -> None:
        total = 0
        for p in _LOCI:
            txt = p.read_text(encoding="utf-8")
            n = len(_NEW_CONTINUE.findall(txt))
            total += n
            if p.name == "SKILL.md":
                self.assertGreaterEqual(
                    n, 3, f"SKILL.md should carry 3 inverted "
                    f"default-continue boundary instructions "
                    f"(after Phase 3/4/5), found {n}.")
            else:
                self.assertGreaterEqual(
                    n, 1, f"{p.name} should carry 1 inverted "
                    f"default-continue boundary instruction, found {n}.")
        self.assertGreaterEqual(
            total, 5,
            f"expected >=5 inverted default-continue boundary "
            f"instructions across the 3 loci, found {total} — the "
            f"F11 inversion is incomplete.")

    def test_single_phase_invocation_semantic_preserved(self) -> None:
        # The inversion MUST preserve the per-phase incremental path:
        # the inverted prose explicitly carves out "invoked you for
        # the current phase only" so `Run quality playbook phase N.`
        # still stops after Phase N.
        for p in _LOCI:
            txt = p.read_text(encoding="utf-8")
            for m in _NEW_CONTINUE.finditer(txt):
                # The carve-out clause must accompany every inverted
                # instruction (it's in the regex), and the
                # single-phase example must be present in-context.
                window = txt[m.start():m.start() + 400]
                self.assertIn(
                    "Run quality playbook phase", window,
                    f"{p.name}: an inverted boundary instruction is "
                    f"missing the single-phase-invocation carve-out "
                    f"example — per-phase incremental runs would break.")


if __name__ == "__main__":
    unittest.main()
