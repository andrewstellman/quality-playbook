"""v1.5.7: pin SKILL.md size below an OWNER-CHOSEN ARBITRARY SOFT
TRIPWIRE.

**This ceiling is an arbitrary, owner-chosen soft tripwire — NOT a
hard technical limit.** It exists to catch unintended SKILL.md
bloat, and is bumped DELIBERATELY when a change is worth the
tokens. Per the v1.5.7 090m owner note: *"If an extra 2k tokens
make a difference we're probably dealing with a far too limited AI
to do this work anyway"* — i.e. the bound is operational hygiene,
not a model-capability constraint.

History:
- Acceptance criterion from instruction 025: SKILL.md BPE token
  count below 30K. Phase 7 trim achieved 26,162 BPE (cl100k_base).
- Instruction 058 (A-11) added the layout-aware
  `PYTHONPATH=<install_root>` Phase 1 invocation guidance to
  SKILL.md, re-growing it to ~27,943 BPE.
- Instruction 062 widened the ceiling 28,000 → 29,000 BPE (the
  prior 28,000 pin left only ~57 BPE of live headroom — the
  instruction-061 Council Lens-1 fragility finding).
- Instruction 089b F11 widened it 29,000 → 29,500 (3
  STOP→default-continue inversions, ~29,156 BPE).
- Instruction 089d F21 widened it 29,500 → 30,000 (the design-
  target hard ceiling): the F21 fix documents 3 by-design Mode A
  vs Mode B asymmetries, growing SKILL.md to ~29,823 BPE.
- **Instruction 090m** widened it 30,000 → 32,000 because the
  MANDATORY FIRST ACTION banner went from a condensed 2-line
  blockquote (which the agent was producing literally at skill-
  load, defeating the install-time attribution) to the full
  canonical 8-line block matching `bin/_purpose.BANNER_TEXT`
  (+~170 BPE). The owner's accompanying decision: this ceiling
  is arbitrary, not a design target; bump it whenever a change
  is worth the tokens. The 32,000 bound leaves ~1,900 BPE of
  headroom over the live ~30,113 BPE; future edits widen the
  ceiling DELIBERATELY (with a one-line rationale appended here),
  the same way prior widenings were documented.

If a future SKILL.md edit legitimately grows the file past
32,000, update the pin to match, add a one-line rationale here
explaining why the change was worth the tokens, and re-check
references/*.md for further trim opportunities — but understand
that "we breached the ceiling" is NOT a forcing function on its
own; the question is always "is this change worth the tokens?"
The bump is the answer when the answer is yes.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILL_MD = Path(__file__).resolve().parents[2] / "SKILL.md"
REFERENCES_DIR = Path(__file__).resolve().parents[2] / "references"


class SkillMdSizeTests(unittest.TestCase):
    def test_skill_md_bpe_token_count_under_threshold(self) -> None:
        """SKILL.md stays under the 32,000 BPE (cl100k_base) ceiling
        — an arbitrary, owner-chosen soft tripwire (v1.5.7 090m).

        See the module docstring for the full ceiling-history prose
        and the rationale for treating this bound as a soft
        tripwire (not a hard technical limit).

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md):
          Mutation: drop the ceiling below the live SKILL.md size —
          set the `assertLess` bound to `30000` (live SKILL.md is
          ~30,113 BPE post-090m; the 32,000 bound provides ~1,887
          BPE headroom).
          Expected failure: THIS test fails with
            AssertionError: SKILL.md is 30113 BPE tokens — exceeds
            the v1.5.7 size ceiling (30000 — an arbitrary, owner-
            chosen soft tripwire …).
          (Returning to 31,000 would also fail by the same logic;
          a useful bite is any value below the live size. A bite
          that uses a value strictly above the live size — e.g.
          33,000 — is NOT useful because the test would still
          pass under either the original 32,000 bound or the
          mutated one.)
          Restoration: re-set the ceiling to 32,000; test passes
          (30,113 < 32,000).
          Mutation strategy unchanged from prior bumps — any future
          widening adds a one-line history bullet to the module
          docstring and keeps this mutation-evidence form.
        """
        try:
            import tiktoken
        except ImportError:
            self.skipTest("tiktoken not installed")
        enc = tiktoken.get_encoding("cl100k_base")
        text = SKILL_MD.read_text(encoding="utf-8")
        token_count = len(enc.encode(text))
        # Ceiling history (see module docstring for full prose):
        # 28,000 → 29,000 (062 Lens-1 fragility), → 29,500 (089b
        # F11), → 30,000 (089d F21). v1.5.7 090m widened it
        # 30,000 → 32,000 because the MANDATORY FIRST ACTION
        # banner went from a condensed 2-line blockquote to the
        # full 8-line canonical banner block matching
        # `bin/_purpose.BANNER_TEXT` byte-for-byte. The owner's
        # accompanying decision: **this ceiling is an arbitrary,
        # owner-chosen soft tripwire — not a hard technical
        # limit.** It catches unintended bloat; bump it
        # deliberately when a change is worth the tokens. (Per
        # the 090m owner note: "if an extra 2k tokens make a
        # difference we're probably dealing with a far too
        # limited AI to do this work anyway.")
        self.assertLess(
            token_count, 32000,
            f"SKILL.md is {token_count} BPE tokens — exceeds the "
            f"v1.5.7 size ceiling (32000 — an arbitrary, owner-"
            f"chosen soft tripwire, not a hard technical limit). "
            f"If the SKILL.md growth is intentional and worth the "
            f"tokens, bump the ceiling here with a one-line "
            f"rationale appended to the module docstring (see "
            f"history of prior bumps for the canonical form). "
            f"Otherwise trim references/*.md or SKILL.md content."
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
