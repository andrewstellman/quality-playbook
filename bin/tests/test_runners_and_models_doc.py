"""v1.5.7 Phase 6e: structural tests for references/runners_and_models.md.

Validates:
- File exists at the canonical path.
- Sections cover each of the four runners (claude-cli, gh copilot,
  codex-cli, cursor-cli).
- Does NOT contain a model-availability matrix (intentional anti-goal
  per Design: runtime model knowledge is the orchestrating LLM's
  job, not this document's).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


DOC_PATH = Path(__file__).resolve().parent.parent.parent / "references" / "runners_and_models.md"


class RunnersAndModelsDocTests(unittest.TestCase):
    def test_doc_exists(self) -> None:
        self.assertTrue(DOC_PATH.is_file(),
                        f"Missing required adopter doc at {DOC_PATH}")

    def test_doc_covers_all_four_runners(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8").lower()
        for runner in ("claude-cli", "gh copilot", "codex-cli", "cursor-cli"):
            self.assertIn(
                runner, text,
                f"Doc must include a section / mention for runner {runner!r}",
            )

    def test_doc_covers_council_of_three_rationale(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8").lower()
        # The doc must explain WHY the Council exists (the "why three"
        # + "why diversity" rationale per the brief).
        self.assertIn("council of three", text)
        self.assertIn("model-family diversity", text)
        self.assertIn("2-of-2 degradation", text)

    def test_doc_covers_override_mechanisms(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        # Must cross-reference the three override layers (CLI, config,
        # built-in default). v1.5.7 Phase 6c follow-on: config file
        # format is JSON (stdlib-only), not YAML — per orchestrator's
        # Path γ disposition.
        self.assertIn("--council-roster", text)
        self.assertIn("~/.qpb/config.json", text)
        self.assertIn("DEFAULT_COUNCIL_MEMBERS", text)

    def test_doc_does_not_contain_model_availability_matrix(self) -> None:
        # The brief's explicit anti-goal: "NO model-availability
        # matrix (decay-prone). NO claims about which models are
        # reachable through which runners as of which date."
        #
        # Detect by looking for a table whose header row contains
        # both "runner" or "model" AND specific model identifier
        # patterns (e.g., a row that lists model names per runner).
        text = DOC_PATH.read_text(encoding="utf-8")
        # Look for a markdown table that names multiple specific
        # model identifiers in cells (the matrix signature).
        # Heuristic: a markdown table row containing 2+ model-like
        # identifiers (matching a pattern like "claude-X" or "gpt-X")
        # separated by pipe characters.
        model_id_pattern = re.compile(
            r"\|.*?(claude-\d|gpt-\d|gemini-\d).*?\|.*?(claude-\d|gpt-\d|gemini-\d).*?\|"
        )
        matches = model_id_pattern.findall(text)
        self.assertEqual(
            matches, [],
            f"Doc must NOT contain a model-availability matrix; "
            f"found table row(s) with multiple model identifiers: {matches}",
        )

    def test_doc_points_at_canonical_council_config(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        # Adopters need to know where the canonical roster source is.
        self.assertIn("bin/council_config.py", text)


if __name__ == "__main__":
    unittest.main()
