"""v1.6.0 Feature D — supersession of the review/refinement walkthrough.

The validation interview (`references/requirements_interview.md`) replaces the
v1.5.7 review/refinement walkthrough entirely: `REVIEW_REQUIREMENTS.md`,
`REFINE_REQUIREMENTS.md`, and `REFINEMENT_HINTS.md` are no longer generated.

Instruction 003 acceptance: **a sweep test proving no remaining generator of
the superseded walkthrough files.** This is that test.

A "generator" here is a shipped reference doc or phase prompt that instructs
the agent to *emit* one of those files (the two old templates were exactly
that — "This is the template for `quality/REVIEW_REQUIREMENTS.md`"). Prose that
*names* the old files to say they are superseded is not a generator, and is
allowed — the point is that nothing tells the agent to produce them again.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES = REPO_ROOT / "references"
PHASE_PROMPTS = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
    / "phase_prompts"
)

SUPERSEDED_FILES = (
    "REVIEW_REQUIREMENTS.md",
    "REFINE_REQUIREMENTS.md",
    "REFINEMENT_HINTS.md",
)

# The two reference docs that WERE the generators (templates the agent read
# and emitted as quality/*.md). They must be gone.
SUPERSEDED_TEMPLATES = (
    REFERENCES / "requirements_review.md",
    REFERENCES / "requirements_refinement.md",
)

# Generation-verb patterns that, paired with a superseded filename, mean
# "produce this file". A doc may still mention the filename to mark it
# superseded; it may not instruct the agent to generate it.
_GENERATE_VERBS = re.compile(
    r"\b(generate|generates|write|writes|produce|produces|create|creates|"
    r"template for|emit|emits)\b",
    re.IGNORECASE,
)


class SupersededTemplatesRemovedTests(unittest.TestCase):
    def test_old_template_reference_docs_are_deleted(self):
        for path in SUPERSEDED_TEMPLATES:
            with self.subTest(template=path.name):
                self.assertFalse(
                    path.exists(),
                    f"{path.name} still exists — the validation interview "
                    "supersedes it; it must be deleted, not left as a "
                    "second review system.",
                )

    def test_interview_protocol_exists(self):
        self.assertTrue(
            (REFERENCES / "requirements_interview.md").is_file(),
            "references/requirements_interview.md is the replacement and "
            "must exist.",
        )


class NoRemainingGeneratorTests(unittest.TestCase):
    """No shipped doc instructs generation of a superseded file."""

    def _swept_files(self):
        files = sorted(REFERENCES.glob("*.md"))
        files += sorted(PHASE_PROMPTS.glob("*.md"))
        files.append(REPO_ROOT / "SKILL.md")
        return [f for f in files if f.is_file()]

    def test_no_generation_instruction_for_superseded_files(self):
        offenders = []
        for path in self._swept_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if not any(name in line for name in SUPERSEDED_FILES):
                    continue
                # The interview doc's supersession section legitimately names
                # the old files. A line that pairs a filename with a
                # generation verb is the thing we forbid — unless it is
                # explicitly negated ("no longer generated", "superseded").
                if _GENERATE_VERBS.search(line):
                    low = line.lower()
                    negated = (
                        "no longer" in low
                        or "superseded" in low
                        or "supersede" in low
                        or "replaced" in low
                        or "replaces" in low
                        or "old " in low
                    )
                    if not negated:
                        offenders.append(
                            f"{path.relative_to(REPO_ROOT)}:{lineno}: "
                            f"{line.strip()[:120]}"
                        )
        self.assertEqual(
            offenders, [],
            "Found instruction(s) to generate a superseded walkthrough file. "
            "The validation interview replaces them; nothing may still tell "
            "the agent to produce them:\n  " + "\n  ".join(offenders),
        )

    def test_no_gate_check_references_superseded_files(self):
        """There was no gate check to orphan; assert it stays that way."""
        gate = (
            REPO_ROOT / "plugins" / "quality-playbook" / "skills"
            / "quality-playbook" / "scripts" / "quality_gate.py"
        ).read_text(encoding="utf-8", errors="replace")
        for name in SUPERSEDED_FILES:
            with self.subTest(file=name):
                self.assertNotIn(
                    name, gate,
                    f"quality_gate.py references {name}; the superseded "
                    "walkthrough had no gate check and must not gain one.",
                )


if __name__ == "__main__":
    unittest.main()
