"""Acceptance criterion #3 (addendum §10): the 4 README launch prompts
(Claude Code, Copilot, Cursor, Windsurf) use distribution-agnostic
phrasing with no `python3` literals.

This test was added in instruction 079b after 079 Council cycle 1
caught the launch prompts silently violating acceptance #3 (the suite
pinned the structural collapse but not the literal phrasing rule)."""

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
README = REPO_ROOT / "README.md"

# v1.5.7 089: conscious re-pin (the 079b Task-3 designed trigger) —
# F1/F5/F10 expanded README Step 3 (3 cp recipes → 13 modules + the
# 087 sentinel block) + added the F10 Known-limitations section,
# shifting the 4 §3.5 IDE launch prompts down (272/278/286/288 →
# 344/350/358/360). The prompts themselves are unchanged.
LAUNCH_PROMPT_LINES = (344, 350, 358, 360)  # the 4 IDE prompts per §3.5


class ReadmeLaunchPromptsNoPython3LiteralTest(unittest.TestCase):
    def test_no_python3_literal_in_four_launch_prompts(self):
        """Acceptance #3: no `python3` literal in the 4 launch-prompt
        lines.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-079b —
        BITE EXECUTED during instruction-079b development:
          Mutation: in README.md:272 re-insert a `python3` literal
          (revert the validator invocation to `python3
          <path-to-your-QPB-clone>/bin/qpb_validate.py …`).
          Observed failure (purged __pycache__ first):
            FAIL: test_no_python3_literal_in_four_launch_prompts
            AssertionError: 'python3' unexpectedly found in
            '**Claude Code:** Open Claude Code in your project
            directory and say: *"Run the QPB install validator
            against this project (the `qpb_validate.py` entry point
            inside your QPB installation). For …' : README.md:272
            contains `python3` literal — acceptance criterion #3
            (addendum §10) forbids `python3` literals in launch
            prompts. … Line content: '…'
          Restoration: README.md byte-restored from pristine
          snapshot; all 3 tests PASS again. (PASS→FAIL→PASS,
          __pycache__ purged between mutate and restore per
          feedback_mutation_bite_pycache; python-driven
          shutil.copy2 restore, no cp -i alias.)
        """
        lines = README.read_text(encoding="utf-8").splitlines()
        for lineno in LAUNCH_PROMPT_LINES:
            line = lines[lineno - 1]
            self.assertNotIn(
                "python3",
                line,
                f"README.md:{lineno} contains `python3` literal — "
                f"acceptance criterion #3 (addendum §10) forbids "
                f"`python3` literals in launch prompts. Use `python` "
                f"(platform-portable; works on macOS via python3 symlink "
                f"convention OR explicit alias, on Windows as py / python). "
                f"Line content: {line!r}",
            )

    def test_no_hardcoded_clone_path_in_four_launch_prompts(self):
        """Same prompts must use <path-to-your-QPB-clone> placeholder,
        not a hardcoded maintainer path like ~/Documents/QPB."""
        lines = README.read_text(encoding="utf-8").splitlines()
        for lineno in LAUNCH_PROMPT_LINES:
            line = lines[lineno - 1]
            # ~/Documents/ is the most likely maintainer-specific hardcode;
            # also forbid absolute /Users/ and /home/ in prompts.
            for forbidden in ("~/Documents/", "/Users/", "/home/"):
                self.assertNotIn(
                    forbidden,
                    line,
                    f"README.md:{lineno} contains hardcoded path "
                    f"`{forbidden}` — acceptance criterion #3 (addendum "
                    f"§10) + §3.5 prescribes the `<path-to-your-QPB-clone>` "
                    f"placeholder. Line content: {line!r}",
                )

    def test_launch_prompt_lines_are_the_four_ide_prompts(self):
        """Guard the line-number pins: if a future README reflow
        shifts the prompts, this fails immediately and forces a
        conscious re-pin (instruction-079b Task 3 note)."""
        lines = README.read_text(encoding="utf-8").splitlines()
        markers = {
            344: "**Claude Code:**",
            350: "**GitHub Copilot:**",
            358: "**Cursor:**",
            360: "**Windsurf:**",
        }
        for lineno, marker in markers.items():
            self.assertTrue(
                lines[lineno - 1].startswith(marker),
                f"README.md:{lineno} no longer starts with {marker!r} "
                f"(launch-prompt reflow — re-pin LAUNCH_PROMPT_LINES). "
                f"Line content: {lines[lineno - 1]!r}",
            )


if __name__ == "__main__":
    unittest.main()
