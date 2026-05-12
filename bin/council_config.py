"""council_config.py — stable reviewer identifiers for the Council of Three.

The Council-of-Three is three independent AI reviewers. Their identifier
strings flow into two places:

  1. The semantic-check prompts (Phase 6) — each reviewer sees their own
     prompt with their identifier embedded.
  2. The `reviewer` field in each `citation_semantic_check.json` review
     entry (schemas.md §9.2) — the gate's majority-overreaches rule
     groups reviews by this field (§10 invariant #17). A typo silently
     becomes a fourth reviewer and breaks the 2-of-3 vote.

This module is the single source of truth. Callers MUST import the
canonical tuple instead of hardcoding the strings at call sites.
Introducing a new reviewer is a one-line change here.
"""

from __future__ import annotations

# Phase 6 launch roster. Stable across the Council's review entries in one
# run and across runs. If a reviewer is swapped (different model version,
# different provider), assign the new identifier here rather than mutating
# an existing one — historical archives reference these strings verbatim.
#
# v1.5.7 Phase 6a: swap to current roster. Prior roster (claude-opus-4.7,
# gpt-5.4, gemini-2.5-pro) preserved verbatim in archived Council
# responses and historical synthesis docs; only the active launch
# identifiers change here. Swap rationale:
#   - claude-opus-4.7: retained (no change).
#   - gpt-5.4 → gpt-5.5: vendor's current production model identifier.
#   - gemini-2.5-pro → claude-sonnet-4.6: Council resilience — gh copilot
#     silently dropped gemini-2.5-pro support during the v1.5.6 sweep
#     (see QPB_v1.5.7_Design.md "Council resilience gap"); claude-
#     sonnet-4.6 is reliably available across the same runner set.
DEFAULT_COUNCIL_MEMBERS: tuple[str, ...] = (
    "claude-opus-4.7",
    "gpt-5.5",
    "claude-sonnet-4.6",
)


def council_members() -> tuple[str, ...]:
    """Return the active Council roster.

    Indirection layer in case callers want to inject a test roster without
    monkey-patching the module-level constant.
    """
    return DEFAULT_COUNCIL_MEMBERS
