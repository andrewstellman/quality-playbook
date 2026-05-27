"""v1.5.7 116 — TUI selection cursor must clamp to the
selectable range.

Operator-reported (live ``qpb_harness tui``): pressing ↓ past
the last row makes the highlight disappear; you then have to
press ↑ several extra times before the bottom row re-
highlights. Cause (pre-116, ``bin/harness/tui.py:572-573``):

    if ch == curses.KEY_DOWN:
        selected_idx += 1     # unclamped!

KEY_UP only guards ``> 0``, so the over-incremented index
takes multiple ↑ presses to return into range.

Additional class of the same bug (refresh-induced): when the
list shrinks between auto-refresh ticks (a run dir disappears,
or a view-switch reduces the row count), an index valid for the
OLD row count points past the NEW last row. Same fix: re-clamp
after each row-rebuild.

116 fix: introduce ``_clamp_cursor(idx, n_rows) -> int`` pure
helper; call it on KEY_UP / KEY_DOWN AND at the top of each
event-loop iteration after the per-view row count is computed.

Coverage:
  * ``_clamp_cursor`` pure helper — boundary behavior at the
    last row (KEY_DOWN at idx=n-1+1 ⇒ stays at n-1, the
    operator-reported case), at row 0 (KEY_UP under-run ⇒
    stays at 0), under refresh-shrink (idx=5 in a 3-row list
    ⇒ 2), empty list (n=0 ⇒ 0), single-row list (any idx
    ⇒ 0), round-trip at the boundary (↓ then ↑ takes ONE
    press each).
  * The clamp helper is exported in ``tui.__all__`` so it's
    callable from tests without curses initialization.
  * Module-import-safe (111 invariant): importing
    ``bin.harness.tui`` does NOT start curses.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from bin.harness import tui as TUI


_REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Task A — _clamp_cursor pure helper
# ---------------------------------------------------------------------------


class ClampCursorBoundaryTests(unittest.TestCase):
    """**THE 116 MUTATION-BITE**: the unclamped pre-116
    ``selected_idx += 1`` would let the cursor drift past
    ``n_rows-1``. The clamp pins the last row as the upper
    bound; reverting to ``selected_idx + 1`` (no clamp)
    makes ``test_down_at_last_row_stays_put`` FAIL."""

    def test_down_at_last_row_stays_put(self) -> None:
        """**The operator-reported failure mode**: ↓ at the
        last row stays on the last row (highlight remains
        visible). Pre-116 the cursor incremented past n_rows-1
        and the highlight disappeared. Revert to the unclamped
        ``idx + 1`` ⇒ this assertion FAILS (returns n_rows
        instead of n_rows-1)."""
        # 5-row list, cursor at last row (idx=4). KEY_DOWN
        # should attempt idx=5; clamp pins it to 4.
        self.assertEqual(TUI._clamp_cursor(5, 5), 4)
        # 1-row list, cursor at row 0. ↓ should stay at 0.
        self.assertEqual(TUI._clamp_cursor(1, 1), 0)

    def test_up_at_row_zero_stays_put(self) -> None:
        """KEY_UP at row 0 stays on row 0 (the pre-116
        ``> 0`` guard already handled this case; 116
        preserves it via the same clamp)."""
        # 5-row list, cursor at row 0. KEY_UP attempts idx=-1;
        # clamp pins to 0.
        self.assertEqual(TUI._clamp_cursor(-1, 5), 0)
        # In-range cursor unchanged.
        self.assertEqual(TUI._clamp_cursor(0, 5), 0)
        self.assertEqual(TUI._clamp_cursor(2, 5), 2)

    def test_round_trip_at_boundary_takes_one_press(
            self) -> None:
        """Acceptance criterion: ↓/↑ round-trip by ONE press
        at the boundaries. Pre-116 the cursor over-incremented,
        so ↑ took 1+(idx-overshoot) presses to return; 116
        clamps so a single ↓-then-↑ at the last row returns
        the cursor exactly where it started."""
        n_rows = 5
        idx = 4  # at last row
        # ↓ press attempts idx+1=5, clamped to 4 (stays).
        idx_after_down = TUI._clamp_cursor(idx + 1, n_rows)
        self.assertEqual(idx_after_down, 4)
        # ↑ press from clamped idx=4 ⇒ idx-1=3, no further
        # clamp needed. Round-trip from clamped state takes
        # ONE press.
        idx_after_up = TUI._clamp_cursor(idx_after_down - 1,
                                            n_rows)
        self.assertEqual(idx_after_up, 3)
        # Symmetric round-trip from idx=0:
        idx = 0
        idx_after_up = TUI._clamp_cursor(idx - 1, n_rows)
        self.assertEqual(idx_after_up, 0)
        idx_after_down = TUI._clamp_cursor(idx_after_up + 1,
                                              n_rows)
        self.assertEqual(idx_after_down, 1)


class ClampCursorEmptyAndSingleRowTests(unittest.TestCase):
    """Acceptance criterion: empty / single-row views handled
    cleanly. ↑/↓ on a 0-row list is a no-op (cursor stays at
    0); on a 1-row list, ↓/↑ are also no-ops (cursor stays at
    0 — the only valid row)."""

    def test_empty_list_returns_zero(self) -> None:
        """``n_rows == 0`` ⇒ cursor pinned to 0 regardless of
        the requested idx. The render layer's
        ``i == selectable_first_row + selected_idx`` check
        won't highlight anything when n_data_rows is 0, so 0
        is a safe no-selection sentinel."""
        self.assertEqual(TUI._clamp_cursor(0, 0), 0)
        self.assertEqual(TUI._clamp_cursor(5, 0), 0)
        self.assertEqual(TUI._clamp_cursor(-3, 0), 0)

    def test_single_row_list_returns_zero(self) -> None:
        """1-row list: any cursor movement clamps back to 0
        (the only selectable index)."""
        # Already at row 0.
        self.assertEqual(TUI._clamp_cursor(0, 1), 0)
        # ↓ attempts idx=1 ⇒ clamped to 0 (1-row list has
        # max idx = 0).
        self.assertEqual(TUI._clamp_cursor(1, 1), 0)
        # ↑ attempts idx=-1 ⇒ clamped to 0.
        self.assertEqual(TUI._clamp_cursor(-1, 1), 0)


class ClampCursorRefreshShrinkTests(unittest.TestCase):
    """Acceptance criterion: re-clamp after auto-refresh so a
    previously-valid index can't point past a now-shorter
    list. ``_clamp_cursor`` is called at the top of each
    event-loop iteration AFTER the per-view row count is
    recomputed, so a list that shrinks between 2s ticks (a
    run dir disappears; a view transition reduces the row
    count) doesn't leave the cursor pointing at thin air."""

    def test_index_clamped_when_list_shrinks(self) -> None:
        """Was valid for a 10-row list (idx=7); the list
        shrinks to 3 rows ⇒ clamp pins idx to 2 (the new
        last row)."""
        self.assertEqual(TUI._clamp_cursor(7, 3), 2)

    def test_index_unchanged_when_list_grows(self) -> None:
        """Was valid for a 3-row list (idx=2); the list
        grows to 10 rows ⇒ cursor stays at 2 (still
        in-range; no movement)."""
        self.assertEqual(TUI._clamp_cursor(2, 10), 2)

    def test_index_clamped_when_list_empties(self) -> None:
        """Was valid for a 5-row list (idx=4); the list
        empties (e.g. all run dirs deleted in test cleanup)
        ⇒ clamp pins idx to 0 (no-selection sentinel)."""
        self.assertEqual(TUI._clamp_cursor(4, 0), 0)


# ---------------------------------------------------------------------------
# 111 invariant — module import is side-effect-free (no curses)
# ---------------------------------------------------------------------------


class ImportSafetyTests(unittest.TestCase):
    """111 pinned this; 116 must preserve it. The clamp helper
    is a pure function defined at module scope — importing
    ``bin.harness.tui`` must NOT start curses (curses-less CI
    / sandbox / test runner must succeed)."""

    def test_import_does_not_start_curses(self) -> None:
        """Spawn a fresh subprocess and import tui — exit 0
        (no curses init, no terminal access)."""
        proc = subprocess.run(
            [sys.executable, "-c",
              "from bin.harness import tui; "
              "assert callable(tui._clamp_cursor)"],
            cwd=str(_REPO_ROOT),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            proc.returncode, 0,
            f"importing bin.harness.tui must NOT init curses "
            f"(stderr={proc.stderr[:400]!r})",
        )


# ---------------------------------------------------------------------------
# Bundle-safety: 116 lives under bin/harness/ (excluded)
# ---------------------------------------------------------------------------


class BundleSafety116Tests(unittest.TestCase):

    def test_tui_changes_stay_under_harness(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"116 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
