"""v1.5.7 Phase 6a follow-on: dedicated test file for the Council roster pin.

The canonical roster lives at `bin/council_config.DEFAULT_COUNCIL_MEMBERS`.
This test asserts the exact tuple value so a future edit that accidentally
drifts the roster (typo, reorder, missing entry) fails the test suite
during release prep instead of after tag.

The historical home of this pin was `test_council_semantic_check.py::
CouncilConfigTests`, which is preserved there as a roster-shape assertion
(length + member presence). This dedicated file adds the stricter
value-pin per the Phase 6 Council Lens-1 fixup request.
"""

from __future__ import annotations

import unittest

from bin.council_config import DEFAULT_COUNCIL_MEMBERS, council_members


class CouncilRosterPinTests(unittest.TestCase):
    """Pin the canonical roster's exact tuple value."""

    def test_default_council_members_exact_value(self) -> None:
        """v1.5.7 Phase 6a swap: the active roster is
        (claude-opus-4.7, gpt-5.5, claude-sonnet-4.6).

        If this test fails, either (a) a roster swap landed without
        updating this pin (update the pin AND ensure the prior roster
        identifiers are preserved verbatim in any archived Council
        responses / historical synthesis docs), or (b) someone
        accidentally drifted the tuple (revert).
        """
        self.assertEqual(
            DEFAULT_COUNCIL_MEMBERS,
            ("claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6"),
        )

    def test_council_members_returns_default(self) -> None:
        """The indirection layer `council_members()` returns the
        canonical tuple. Future test-injection callers can monkeypatch
        the function rather than the module-level constant."""
        self.assertEqual(council_members(), DEFAULT_COUNCIL_MEMBERS)

    def test_roster_has_three_distinct_members(self) -> None:
        """Phase 6 Council audit requires three reviewers (per
        invariant #17). Duplicate members would silently collapse the
        2-of-3 vote and break the audit."""
        self.assertEqual(len(DEFAULT_COUNCIL_MEMBERS), 3)
        self.assertEqual(len(set(DEFAULT_COUNCIL_MEMBERS)), 3,
                         f"Roster must have 3 DISTINCT members; "
                         f"got duplicates in {DEFAULT_COUNCIL_MEMBERS}")


if __name__ == "__main__":
    unittest.main()
