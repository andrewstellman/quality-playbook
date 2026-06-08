"""Regression tests for the v1.5.7 Deliverable 2 role-map query cookbook.

Pins three contracts:

1. ``references/role_map_queries.md`` exists and contains the four
   anti-pattern strings + the four canonical-query anchors documented
   in ``docs/design/QPB_v1.5.7_Design.md`` Deliverable 2.
2. The Phase 2 prompt template that the runner actually loads at
   Phase 2 cites the cookbook by relative path.
3. The Phase 2 prompt's cookbook-reference paragraph stays under a
   300-token budget so it doesn't bloat the prompt context.

Test-module placement choice: a new dedicated module rather than
extending an existing role-map or phase-prompt test file. The
cookbook is a v1.5.7 feature with three small contracts that are
naturally discoverable as a unit; co-locating them makes the surface
greppable. If a future test needs to interact with both this cookbook
and the role-map validator, it can import from both modules.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# v1.5.8 instruction 208: references/ + phase_prompts/ moved into the plugin skill folder.
_SKILL_DIR = REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
COOKBOOK_PATH = _SKILL_DIR / "references" / "role_map_queries.md"
PHASE2_PROMPT_PATH = _SKILL_DIR / "phase_prompts" / "phase2.md"

# Canonical query anchors (substrings that distinguish each canonical
# query — taken from ``docs/design/QPB_v1.5.7_Design.md`` Deliverable 2).
_REQUIRED_CANONICAL_ANCHORS = (
    'select(.role == "code")',
    'select(.role == "test")',
    'select(.role == "skill-tool")',
    "group_by(.role)",
)

# Anti-pattern strings — the four wrong-guess paths an agent might
# construct from intuition. The cookbook MUST list each with a
# "DO NOT use" annotation.
_REQUIRED_ANTI_PATTERNS = (
    ".roles.source[]",
    ".roles.code[]",
    ".files.code[]",
    'select(.role == "source")',
)

# Phase 2 prompt's cookbook-reference paragraph — anchor strings used
# to locate the inserted block for the token-budget test. The paragraph
# header line is unique to the cookbook addition (other Phase 2 prompt
# paragraphs use different bolded headers).
_COOKBOOK_PARAGRAPH_ANCHOR = "Role-map query cookbook"


class CookbookContentTests(unittest.TestCase):
    """Work-item C test 1: cookbook file exists and contains the
    required canonical queries + anti-patterns.

    Cookbook reads happen per-test (lazy ``self._cookbook_text()``)
    rather than in ``setUpClass``. Pre-fix-up the class used
    ``setUpClass`` which raised ``FileNotFoundError`` if the cookbook
    was missing, errored every test in the class during setup, and
    obscured the ``test_cookbook_file_exists`` failure mode. With
    the lazy read, deleting the cookbook fails ``test_cookbook_file_exists``
    with a clean "file must exist" message and only the other three
    tests error on read — better diagnostic surface for operators.
    """

    @property
    def text(self) -> str:
        """Read the cookbook on demand. Cached per-instance so the
        three content-check tests don't pay multiple I/O passes."""
        if not hasattr(self, "_cookbook_text"):
            self._cookbook_text = COOKBOOK_PATH.read_text(encoding="utf-8")
        return self._cookbook_text

    def test_cookbook_file_exists(self) -> None:
        self.assertTrue(
            COOKBOOK_PATH.is_file(),
            f"references/role_map_queries.md must exist (got: "
            f"{COOKBOOK_PATH})",
        )

    def test_cookbook_contains_all_canonical_query_anchors(self) -> None:
        for anchor in _REQUIRED_CANONICAL_ANCHORS:
            with self.subTest(anchor=anchor):
                self.assertIn(
                    anchor, self.text,
                    f"cookbook missing canonical query anchor "
                    f"{anchor!r} (one of the four required patterns "
                    f"per Design Deliverable 2)",
                )

    def test_cookbook_contains_all_anti_patterns(self) -> None:
        for pattern in _REQUIRED_ANTI_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIn(
                    pattern, self.text,
                    f"cookbook missing anti-pattern {pattern!r} from "
                    f"the DO NOT use list (per Design Deliverable 2)",
                )

    def test_cookbook_does_not_enumerate_role_taxonomy(self) -> None:
        """Deliberate non-content per the brief: the cookbook must NOT
        enumerate role taxonomy values inline, to avoid drift if
        ``bin/role_map.py::ROLE_DESCRIPTIONS`` evolves.

        Two sub-assertions:

        (a) The cookbook points at ``ROLE_DESCRIPTIONS`` as the canonical
            source (positive citation check).

        (b) The cookbook's PROSE (text outside fenced code blocks and
            outside lines that contain canonical jq query fragments)
            contains fewer than 2 quoted role-identifier strings. The
            <2 threshold allows a single contextual mention (e.g.,
            "the implementation-code role is ``code``") but rejects an
            inline taxonomy list. Counting outside code blocks AND
            outside ``select(.role ==`` lines is the load-bearing
            scoping decision: legitimate uses of role strings (canonical
            queries, anti-pattern jq fragments) live in code/query
            context and don't count toward the inline-enumeration
            threshold.

        Strengthened in v1.5.7 Phase 2 fix-up (5 of 7 Council
        perspectives flagged that the pre-fix-up version only checked
        sub-assertion (a) and would not bite if someone added an
        inline role list alongside the citation).
        """
        from bin.role_map import ROLE_DESCRIPTIONS

        # Sub-assertion (a): positive citation check (preserved from
        # the pre-fix-up test).
        self.assertIn(
            "ROLE_DESCRIPTIONS", self.text,
            "cookbook must cite bin/role_map.py::ROLE_DESCRIPTIONS as "
            "the canonical role-taxonomy source instead of enumerating "
            "roles inline",
        )

        # Sub-assertion (b): inline-enumeration check.
        # Strip fenced code blocks (```...```), then strip remaining
        # lines that look like jq fragments (start with `jq `, are
        # ≥4-space indented, or contain `select(.role ==`).
        in_fence = False
        prose_lines: list[str] = []
        for raw in self.text.splitlines():
            stripped = raw.lstrip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if stripped.startswith("jq "):
                continue
            # 4-space-indented lines are conventionally code blocks
            # in Markdown; skip those too even when not fenced.
            if raw.startswith("    "):
                continue
            if "select(.role ==" in raw:
                continue
            prose_lines.append(raw)
        prose = "\n".join(prose_lines)

        # Count quoted-string occurrences of each role identifier in
        # the remaining prose. Match `"<role>"` exactly — single-quoted
        # or backtick forms would have to use the role value directly
        # and aren't the brief's concern; the failure mode is an
        # inline list like '"code", "test", "docs", "fixture", ...'.
        offenders: list[tuple[str, int]] = []
        for role in sorted(ROLE_DESCRIPTIONS.keys()):
            count = len(re.findall(rf'"{re.escape(role)}"', prose))
            if count > 0:
                offenders.append((role, count))
        total = sum(c for _, c in offenders)
        self.assertLess(
            total, 2,
            f"cookbook prose appears to enumerate role taxonomy "
            f"values inline. Found {total} quoted role-identifier "
            f"occurrences in non-code prose: {offenders!r}. The "
            f"cookbook should cite "
            f"bin/role_map.py::ROLE_DESCRIPTIONS as the canonical "
            f"source instead of listing role values inline (they "
            f"would drift if the taxonomy evolves). Legitimate uses "
            f"of role strings (canonical queries, anti-pattern jq "
            f"fragments) belong inside code blocks or `select(.role "
            f"==` lines and don't count here.",
        )


class Phase2PromptCookbookReferenceTests(unittest.TestCase):
    """Work-item C test 2: Phase 2 prompt template (the file the
    runner actually loads at Phase 2) cites the cookbook by relative
    path."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PHASE2_PROMPT_PATH.read_text(encoding="utf-8")

    def test_runner_loads_phase2_from_phase_prompts_dir(self) -> None:
        """Sanity check: confirm the runner does in fact load the
        Phase 2 prompt from ``phase_prompts/phase2.md``. If this
        assertion fires, the Phase 2 prompt template path has moved
        and this test module's PHASE2_PROMPT_PATH constant is stale."""
        run_playbook = REPO_ROOT / "bin" / "run_playbook.py"
        rp_text = run_playbook.read_text(encoding="utf-8")
        # v1.5.8 instruction 208: PHASE_PROMPTS_DIR construction now
        # nests through ``skills/quality-playbook/`` to match the
        # plugin-native layout.
        self.assertIn(
            '"skills" / "quality-playbook" / "phase_prompts"',
            rp_text,
            "runner's PHASE_PROMPTS_DIR construction has moved; update "
            "PHASE2_PROMPT_PATH in this test to match",
        )
        self.assertIn(
            '_load_phase_prompt("phase2"',
            rp_text,
            "runner's Phase 2 prompt loader has moved; update this "
            "test to match the new loader signature",
        )

    def test_phase2_prompt_cites_cookbook_by_relative_path(self) -> None:
        self.assertIn(
            "references/role_map_queries.md",
            self.text,
            "Phase 2 prompt template must cite the cookbook by the "
            "relative path 'references/role_map_queries.md' so the "
            "runner-installed and source-tree paths both resolve",
        )

    def test_phase2_prompt_contains_cookbook_reference_paragraph(self) -> None:
        self.assertIn(
            _COOKBOOK_PARAGRAPH_ANCHOR, self.text,
            f"Phase 2 prompt template must contain the "
            f"{_COOKBOOK_PARAGRAPH_ANCHOR!r} paragraph header (added "
            f"in v1.5.7 Deliverable 2)",
        )


class Phase2PromptCookbookTokenBudgetTests(unittest.TestCase):
    """Work-item C test 3: the cookbook-reference paragraph added to
    the Phase 2 prompt stays under 300 BPE tokens.

    Token-counting strategy: try ``tiktoken`` if available; fall back
    to ``len(text) / 4`` chars-per-token approximation otherwise.
    Pass if EITHER method produces <300 (the chars-per-token estimate
    overstates BPE token count for English prose, so it's a strict
    upper bound)."""

    BUDGET = 300

    def _extract_cookbook_paragraph(self) -> str:
        """Return the cookbook-reference paragraph from the Phase 2
        prompt by matching the bolded header through the next blank
        line."""
        text = PHASE2_PROMPT_PATH.read_text(encoding="utf-8")
        pattern = re.compile(
            r"\*\*Role-map query cookbook[^*]*\*\*[^\n]*",
            re.MULTILINE,
        )
        match = pattern.search(text)
        if not match:
            self.fail(
                "could not locate the Role-map query cookbook "
                "paragraph in the Phase 2 prompt template; check "
                "that the v1.5.7 Deliverable 2 paragraph is present"
            )
        start = match.start()
        rest = text[start:]
        end = rest.find("\n\n")
        if end == -1:
            return rest
        return rest[:end]

    def test_cookbook_paragraph_under_300_tokens(self) -> None:
        paragraph = self._extract_cookbook_paragraph()
        tiktoken_tokens = None
        try:
            import tiktoken  # type: ignore[import-not-found]
            enc = tiktoken.get_encoding("cl100k_base")
            tiktoken_tokens = len(enc.encode(paragraph))
        except ImportError:
            tiktoken_tokens = None

        chars_estimate = len(paragraph) / 4.0

        # Pass if EITHER method produces <BUDGET. The chars-per-token
        # estimate overstates BPE token count for English prose, so
        # it's a strict upper bound.
        passing_method = []
        if tiktoken_tokens is not None and tiktoken_tokens < self.BUDGET:
            passing_method.append(
                f"tiktoken={tiktoken_tokens} < {self.BUDGET}"
            )
        if chars_estimate < self.BUDGET:
            passing_method.append(
                f"chars/4={chars_estimate:.0f} < {self.BUDGET}"
            )
        self.assertTrue(
            passing_method,
            f"cookbook paragraph exceeds {self.BUDGET}-token budget: "
            f"tiktoken={tiktoken_tokens}, chars/4={chars_estimate:.0f}, "
            f"paragraph length={len(paragraph)} chars. "
            f"Trim the paragraph or split into multiple references.",
        )


if __name__ == "__main__":
    unittest.main()
