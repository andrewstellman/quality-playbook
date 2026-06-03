"""v1.5.7 140 — smart auto-pause follow-tail for the TUI output
screen.

Andrew hit two UX bugs monitoring the 2026-05-29 retest: (1) arrow
keys didn't scroll the output view; (2) mouse-wheel scroll-up
snapped back to the bottom after ~0.5s. Root causes: the RichLog
wasn't focused (so arrows never reached it), and the 2s refresh did
clear()+rewrite then scroll_end (clobbering the operator's scroll
position).

140 fixes both: the output render focuses the log (built-in arrow /
page / home scrolling) and uses the pure `_should_pause_follow` to
auto-pause follow when the operator scrolls up (preserving their
viewport across refreshes) and auto-resume when they return to the
bottom — the 'less +F' idiom. `f` is the explicit override.

The textual `QPBHarnessApp` is closure-local (the 119 no-textual
import invariant) and its scroll/focus integration needs a TTY, so
it's operator-confirmable; `_should_pause_follow` is the
unit-testable seam and carries the load-bearing mutation-bite.
"""
from __future__ import annotations

import unittest

from bin.harness.tui import _should_pause_follow


def _pause(scroll_y, max_scroll_y, *, manual=False, paused=False, f=False):
    return _should_pause_follow(
        scroll_y, max_scroll_y,
        manual_scroll_event=manual, currently_paused=paused,
        user_pressed_f=f)


class ShouldPauseFollowTests(unittest.TestCase):

    def test_following_at_bottom_no_event_stays_following(self) -> None:
        # not paused, at bottom, nothing happened → keep following.
        self.assertFalse(_pause(10, 10))

    def test_following_manual_scroll_up_pauses(self) -> None:
        # not paused + manual scroll up (scroll_y < max) → pause.
        self.assertTrue(_pause(3, 10, manual=True))

    def test_paused_scroll_to_bottom_resumes(self) -> None:
        # LOAD-BEARING: paused + back at the bottom → resume follow.
        # Mutation-bite: inverting the at-max condition flips this.
        self.assertFalse(_pause(10, 10, paused=True))

    def test_paused_f_press_resumes(self) -> None:
        # f is the explicit toggle: paused → following.
        self.assertFalse(_pause(3, 10, paused=True, f=True))

    def test_following_f_press_pauses(self) -> None:
        # f toggles the other way too: following → paused.
        self.assertTrue(_pause(10, 10, paused=False, f=True))

    def test_paused_manual_scroll_up_stays_paused(self) -> None:
        # already paused + more scroll-up → no flicker, stays paused.
        self.assertTrue(_pause(3, 10, manual=True, paused=True))

    def test_paused_scroll_down_not_yet_bottom_stays_paused(
            self) -> None:
        # scrolled down but not at the bottom yet → still paused.
        self.assertTrue(_pause(7, 10, manual=True, paused=True))

    def test_following_wheel_down_at_bottom_stays_following(
            self) -> None:
        # at the bottom already, a downward event → stays following.
        self.assertFalse(_pause(10, 10, manual=True, paused=False))

    def test_f_toggle_ignores_scroll_position(self) -> None:
        # f overrides regardless of where the viewport is.
        self.assertTrue(_pause(10, 10, paused=False, f=True))
        self.assertFalse(_pause(0, 10, paused=True, f=True))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
