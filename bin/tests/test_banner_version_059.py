"""v1.5.10 instruction 059 — the attribution banner carries the
running skill version.

When the skill runs, the full attribution banner must show the
version (e.g. ``Quality Playbook v1.5.10``) so an operator can
confirm at a glance which version is running — catching the
stale-install class of bug (a pre-056 copy installed in a target
silently running old behavior; the 2026-06-21 vaelii gotcha).

The version is RUNTIME-DERIVED from ``_purpose.get_version()`` (THE
canonical SKILL.md-frontmatter reader, 057), so:
  - the expected banner is computed dynamically from get_version()
    here, NOT a hardcoded string — a future version bump never
    breaks these pins (057 single-source principle); and
  - a stale install renders ITS OWN version (the tripwire works).

MUTATION (per ai_context/DEVELOPMENT_PROCESS.md): drop the
``v{version}`` from ``_purpose.attribution_banner_text()`` (e.g.
revert the title line to ``{BANNER_NAME} -- by {BANNER_AUTHOR}``)
and ``test_banner_contains_version`` FAILs ⇒ bite.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr

from bin import _purpose


class BannerVersion059Tests(unittest.TestCase):
    def test_banner_contains_version(self) -> None:
        """attribution_banner_text() carries f"v{get_version()}" —
        the load-bearing assertion. Mutation bite: drop the version
        from the title line ⇒ this FAILs."""
        version = _purpose.get_version()
        self.assertNotEqual(
            version, "unknown",
            "get_version() must resolve from SKILL.md frontmatter for "
            "this repo checkout",
        )
        banner = _purpose.attribution_banner_text()
        self.assertIn(
            f"v{version}", banner,
            "attribution banner must render the running version "
            f"v{version} (059).",
        )

    def test_pin_is_dynamic_not_static(self) -> None:
        """The expected banner is DERIVED from get_version(), not a
        frozen literal — so a version bump never breaks the pin (057
        single-source). We assert the rendered title line equals the
        dynamically-composed expectation."""
        version = _purpose.get_version()
        expected_title = (
            f"  {_purpose.BANNER_NAME} v{version} "
            f"-- by {_purpose.BANNER_AUTHOR}"
        )
        self.assertIn(
            expected_title, _purpose.attribution_banner_text(),
            "title line must be the dynamically-composed "
            "name+version+author line",
        )

    def test_print_attribution_banner_emits_version_on_stderr(
            self) -> None:
        """The actual printed banner (default stream = stderr, the
        089k clean-stdout rule) carries the version."""
        version = _purpose.get_version()
        buf = io.StringIO()
        with redirect_stderr(buf):
            _purpose.print_attribution_banner()
        out = buf.getvalue()
        self.assertIn(f"v{version}", out)
        # still the full 80-wide banner (not condensed)
        self.assertIn("=" * 80, out)
        self.assertIn("Licensed under the Apache License", out)

    def test_skeleton_banner_text_stays_versionless(self) -> None:
        """BANNER_TEXT remains the versionless canonical skeleton (the
        byte-for-byte single source for the SKILL.md / AGENTS.md
        banner blocks). The version is layered on only at render time
        — so the skeleton pins (089j / 090k) never need a version
        literal and can't drift."""
        version = _purpose.get_version()
        self.assertNotIn(f"v{version}", _purpose.BANNER_TEXT)
        self.assertIn(
            f"{_purpose.BANNER_NAME} -- by {_purpose.BANNER_AUTHOR}",
            _purpose.BANNER_TEXT,
        )


if __name__ == "__main__":
    unittest.main()
