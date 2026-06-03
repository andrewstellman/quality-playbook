"""v1.5.7 148 — install-banner observability via the install.log
artifact fallback (parallel to 145's phase-0 witness fallback).

The 2026-05-29T15:14 retest's keto run came back NOT-MET solely on
`banner_rendered=False` — despite a PASSED gate (install necessarily
succeeded, banner included). Root cause is the 143-class gap:
copilot's boxed-TUI stream doesn't capture the install subprocess's
output, so `parse_transcript`'s `_RE_BANNER_RULE` (the ═×80 rule)
never matches. 146 already tees install stdout/stderr to
`<run-NN>/install.log` (the attribution banner is emitted on stderr
at end-of-successful-install). 148 makes `parse_transcript` fall
back to that log for the banner when the stream lacks it.

Stream match always wins; target_dir=None preserves pre-148.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bin.harness.facts import parse_transcript

BANNER = "═" * 80  # _RE_BANNER_RULE = re.compile(r"═{80}")


def _run_target(tmp: str, *, install_log: "str | None") -> Path:
    """A <run-NN>/target dir; optionally with <run-NN>/install.log."""
    run_dir = Path(tmp) / "run-00"
    target = run_dir / "target"
    target.mkdir(parents=True, exist_ok=True)
    if install_log is not None:
        (run_dir / "install.log").write_text(
            install_log, encoding="utf-8")
    return target


def _banner(target: Path) -> bool:
    _ph, install, _b, _s = parse_transcript("", target_dir=target)
    return install.banner_rendered


class BannerArtifactFallbackTests(unittest.TestCase):

    def test_stream_banner_still_wins_over_artifact(self) -> None:
        """Stream has the banner → True via stream; install.log not
        needed. Mutation-bite: if the artifact path overrode the
        stream, this still passes, but the precedence is pinned by
        the no-target-dir + the stream-only nature here."""
        with tempfile.TemporaryDirectory() as tmp:
            target = _run_target(tmp, install_log="no banner here")
            ph, install, _b, _s = parse_transcript(
                f"agent output...\n{BANNER}\nQuality Playbook\n",
                target_dir=target)
            self.assertTrue(install.banner_rendered)

    def test_artifact_fallback_fires_when_stream_has_no_banner(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _run_target(
                tmp,
                install_log=f"npm install...\n{BANNER}\n"
                            f"Quality Playbook — by Andrew Stellman\n")
            self.assertTrue(_banner(target))

    def test_no_fire_when_install_log_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _run_target(tmp, install_log=None)
            self.assertFalse(_banner(target))

    def test_no_fire_when_install_log_has_no_banner(self) -> None:
        # Install failed before the banner emission → log present but
        # bannerless → banner_rendered stays False (correct: the
        # banner was NOT actually rendered).
        with tempfile.TemporaryDirectory() as tmp:
            target = _run_target(
                tmp, install_log="npm ERR! install failed\n")
            self.assertFalse(_banner(target))

    def test_target_dir_none_preserves_pre148(self) -> None:
        # No target_dir → install.log fallback never consulted.
        _ph, install, _b, _s = parse_transcript("no banner in stream")
        self.assertFalse(install.banner_rendered)

    def test_install_log_oserror_falls_through_gracefully(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _run_target(tmp, install_log=BANNER)
            # install.log exists (is_file True) but read_text raises.
            with mock.patch.object(Path, "read_text",
                                   side_effect=OSError("boom")):
                self.assertFalse(_banner(target))  # no crash, False

    def test_partial_banner_symmetric_with_stream(self) -> None:
        """A short rule (< 80 ═) doesn't match in EITHER path — the
        artifact path uses the SAME _RE_BANNER_RULE as the stream."""
        short = "═" * 40
        with tempfile.TemporaryDirectory() as tmp:
            target = _run_target(tmp, install_log=f"x\n{short}\n")
            self.assertFalse(_banner(target))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
