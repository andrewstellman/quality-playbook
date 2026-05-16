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

import sys

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

    Resolution (v1.5.7 D6 6c, instruction 052 / ship-blocker A-9):
      1. The ``council_members`` key in the per-operator config file
         (``$XDG_CONFIG_HOME/qpb/config.json`` then ``~/.qpb/config.json``,
         resolved by ``qpb_config.load_config()``) — when present and a
         non-empty list of non-empty strings, validate via
         ``qpb_config.validate_roster()`` (unknown identifiers emit a
         non-fatal stderr warning per that function's existing contract)
         and use it as the roster.
      2. ``DEFAULT_COUNCIL_MEMBERS`` — the canonical hardcoded fallback.

    Every caller that asks "who is on the Council right now?" routes
    through here (the Phase 6 dispatch in ``council_semantic_check.py``
    and the Phase 4 banner in ``run_playbook.py``), so this is the single
    seam where the adopter override takes effect. ``qpb_config.load_config()``
    stays a pure persistence read; the default/validation resolution is a
    consumer concern and lives here (matches QPB_v1.5.7_Design.md:409 — the
    banner reads this function "dynamically").

    Failure modes fall through to (2) WITHOUT crashing the runner:
      - ``qpb_config`` is unavailable (minimal install / isolated fixture).
      - No config file exists, or it lacks the ``council_members`` key.
      - ``council_members`` is malformed (not a list, empty list, or
        contains a non-string / blank entry): emit a one-line stderr
        warning and fall back to ``DEFAULT_COUNCIL_MEMBERS``. An adopter
        who wants to clear the override should ``qpb config unset
        council_members`` rather than write an empty list.
    """
    # Soft-import keeps council_config import-time-safe for callers that
    # don't ship qpb_config (mirrors the dual-import convention used for
    # council_config itself in council_semantic_check.py).
    try:
        from . import qpb_config
    except ImportError:
        try:
            import qpb_config  # type: ignore[no-redef]
        except ImportError:
            return DEFAULT_COUNCIL_MEMBERS

    cfg = qpb_config.load_config()
    if not cfg:
        return DEFAULT_COUNCIL_MEMBERS
    raw = cfg.get("council_members")
    if raw is None:
        return DEFAULT_COUNCIL_MEMBERS
    if (
        not isinstance(raw, list)
        or not raw
        or not all(isinstance(m, str) and m.strip() for m in raw)
    ):
        print(
            "WARN: ~/.qpb/config.json council_members is malformed (must "
            "be a non-empty list of non-empty strings); falling back to "
            f"defaults {DEFAULT_COUNCIL_MEMBERS}.",
            file=sys.stderr,
        )
        return DEFAULT_COUNCIL_MEMBERS

    members = tuple(m.strip() for m in raw)
    for warning in qpb_config.validate_roster(members):
        print(f"WARN: {warning}", file=sys.stderr)
    return members
