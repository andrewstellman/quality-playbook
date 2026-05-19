"""v1.5.7 Phase 7: pin SKILL.md size below the <30K design target.

Acceptance criteria from instruction 025: SKILL.md BPE token count
below 30K. Phase 7 trim achieved 26,162 BPE (cl100k_base). Instruction
058 (A-11) then added the layout-aware `PYTHONPATH=<install_root>`
Phase 1 invocation guidance to SKILL.md, re-growing it to **27,943
BPE** post-trim. Instruction 062 widened the ceiling 28,000 → 29,000
BPE: the prior 28,000 pin left only ~57 BPE of live headroom (any
incremental SKILL.md prose edit would have reddened the suite — the
instruction-061 Council Lens-1 fragility finding); 29,000 restores
~1,057 BPE of headroom while still hard-blocking any change that
would breach the <30K design target.

If a future SKILL.md edit legitimately grows the file past 29,000
(new orchestration content), update the pin AND the no-orphaned-
pointer test below to match — and re-check references/*.md for
further trim opportunities rather than only widening the ceiling.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILL_MD = Path(__file__).resolve().parents[2] / "SKILL.md"
REFERENCES_DIR = Path(__file__).resolve().parents[2] / "references"


class SkillMdSizeTests(unittest.TestCase):
    def test_skill_md_bpe_token_count_under_threshold(self) -> None:
        """SKILL.md stays under the 29,000 BPE (cl100k_base) ceiling
        — well below the <30K design target.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-062
        (closing the instruction-061 Council Lens-1 test-fragility
        finding):
          Mutation: drop the ceiling below the live SKILL.md size —
          set the `assertLess` bound to `27500` (live SKILL.md is
          27,943 BPE post-A-11).
          Expected failure: THIS test fails with
            AssertionError: SKILL.md is 27943 BPE tokens — exceeds
            the v1.5.7 size ceiling (27500). ...
          (dropping back to 28,000 is NOT a useful bite — 27,943 <
          28,000 so it would still pass; the bite must use a bound
          below the live size to actually flip the test).
          Restoration: re-set the ceiling to 29,000; test passes
          (27,943 < 29,000, ~1,057 BPE headroom).
          Bite executed during instruction-062 development;
          PASS→FAIL→PASS confirmed (__pycache__ purged between
          mutate and restore).
        """
        try:
            import tiktoken
        except ImportError:
            self.skipTest("tiktoken not installed")
        enc = tiktoken.get_encoding("cl100k_base")
        text = SKILL_MD.read_text(encoding="utf-8")
        token_count = len(enc.encode(text))
        # Phase 7 trim achieved 26,162 BPE; instruction 058 (A-11)
        # re-grew SKILL.md to 27,943 BPE post-trim (layout-aware
        # Phase 1 invocation guidance). Instruction 062 widened this
        # ceiling 28,000 → 29,000 (Council-061 Lens-1 fragility
        # finding; ~1,057 BPE headroom). v1.5.7 instruction 089b F11
        # widened it 29,000 → 29,500: the F11 fix inverts 3 SKILL.md
        # per-phase STOP boundary instructions to longer
        # default-continue prose (the A-28 full-pipeline alignment),
        # growing SKILL.md to ~29,156 BPE. Instruction-089b
        # explicitly relaxed the size budget for F11 ("byte count may
        # change; this is not a constraint — prefer correctness over
        # arbitrary size targets"); 29,500 accommodates the
        # instruction-mandated growth with ~344 BPE headroom while
        # still hard-blocking the <30K design target. A references/
        # *.md trim pass to reclaim headroom is deferred (orchestrator
        # / v1.6.x — out of 089b's finding-scoped remit).
        self.assertLess(
            token_count, 29500,
            f"SKILL.md is {token_count} BPE tokens — exceeds the "
            f"v1.5.7 size ceiling (29500; <30K design target). If "
            f"this growth is intentional, update this test's pin AND "
            f"re-check the references/*.md tree for further trim "
            f"opportunities rather than only widening the ceiling."
        )


class SkillMdPointerTests(unittest.TestCase):
    """For each `See \\`references/<name>.md\\`` pointer in SKILL.md,
    assert the target file exists. Test bites if a future edit removes
    a referenced file without updating SKILL.md."""

    def test_all_skill_md_pointers_resolve(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        # Match `See `references/X.md`` patterns (the v1.5.7 Phase 7
        # canonical pointer phrasing).
        pattern = re.compile(r"See `(references/[^`]+\.md)`")
        matches = pattern.findall(text)
        self.assertGreater(
            len(matches), 0,
            "SKILL.md should contain at least one `See references/X.md` "
            "pointer (v1.5.7 Phase 7 added Phase 1, 2, 6 pointers).",
        )
        repo_root = SKILL_MD.parent
        missing = [m for m in matches if not (repo_root / m).is_file()]
        self.assertEqual(
            missing, [],
            f"SKILL.md references files that don't exist: {missing}",
        )


class PhasePromptReferenceLoadTests(unittest.TestCase):
    """For each `phase_prompts/<N>.md` reference load (any references/
    file mentioned in the prompt body), assert the file exists."""

    def test_phase_prompts_reference_files_all_exist(self) -> None:
        # Match references/X.md only when it's the direct object of a
        # "read", "consult", or "see" directive — these are real
        # directive references the agent should be able to find. Bare
        # mentions in code-block examples or inline narrative (e.g.,
        # "references/forms.md:section-3" as an illustrative path) are
        # excluded.
        prompts_dir = SKILL_MD.parent / "phase_prompts"
        directive_pattern = re.compile(
            r"(?:read|consult|see|load)\s+`?(references/[\w_.-]+\.md)",
            re.IGNORECASE,
        )
        missing = []
        for prompt in sorted(prompts_dir.glob("phase*.md")):
            text = prompt.read_text(encoding="utf-8")
            for ref in directive_pattern.findall(text):
                target = SKILL_MD.parent / ref
                if not target.is_file():
                    missing.append(f"{prompt.name}: {ref}")
        self.assertEqual(
            missing, [],
            f"phase_prompts/*.md directive references that don't exist: "
            f"{missing}",
        )


if __name__ == "__main__":
    unittest.main()
