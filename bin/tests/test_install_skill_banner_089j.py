"""v1.5.7 instruction 089j — install-time attribution banner.

Asserts the three contract obligations:

1. **Banner appears on stderr.** Running the installer emits a banner
   carrying the project name ("Quality Playbook"), author ("Andrew
   Stellman"), GitHub URL, tagline, and Apache-2.0 license to
   stderr at install start, unconditionally (both default and
   ``--verbose``).

2. **stdout stays parse-clean** — the LOAD-BEARING obligation. The
   banner text MUST NOT appear on stdout. The existing
   ``event=intro`` / ``event=install_complete`` contract and
   ordering are intact (``event=intro`` is the FIRST stdout line in
   non-verbose mode). In non-verbose mode every stdout line is a
   well-formed ``event=`` record; in verbose mode the prose
   continuation lines (which begin with two spaces and are NOT
   banner content) are an existing v1.5.6+ feature and unaffected
   by 089j.

3. **Smoke checks still pass** — the installer's existing smoke-
   check sequence (`event=smoke_check ... status=passed`) is
   unaffected by the banner addition.

**Mutation-bite evidence** (per ai_context/DEVELOPMENT_PROCESS.md):
Move the banner write from ``sys.stderr`` to ``sys.stdout`` (i.e.
flip the default of ``_print_banner``'s target). Expected failure:
``test_banner_does_not_appear_on_stdout`` fails — the banner
substring NOW appears in stdout. Restore by reverting the default.
Mutation executed PASS → FAIL → PASS during 089j development.
"""

from __future__ import annotations

import io
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import install_skill


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _capture_install(verbose: bool = False) -> tuple[int, str, str]:
    """Run a complete install against a fresh TemporaryDirectory and
    return (exit_code, stdout_text, stderr_text). Both streams are
    captured via injected ``io.StringIO`` buffers to avoid touching
    the real stdout/stderr."""
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with TemporaryDirectory() as tmp:
        target_repo = Path(tmp)
        rc = install_skill.install(
            into=target_repo,
            ai_tool="claude",
            source_root=REPO_ROOT,
            verbose=verbose,
            stream=out_buf,
            banner_stream=err_buf,
        )
    return rc, out_buf.getvalue(), err_buf.getvalue()


class BannerOnStderrTests(unittest.TestCase):
    """Obligation 1: banner appears on stderr, unconditionally."""

    def test_banner_appears_on_stderr_default_mode(self) -> None:
        """In default (non-verbose) mode, the banner's five required
        elements (name, author, URL, tagline, license) all appear
        on stderr."""
        rc, _stdout, stderr = _capture_install(verbose=False)
        self.assertEqual(rc, 0, "default install must succeed")
        # Five required elements.
        self.assertIn("Quality Playbook", stderr,
                      "banner must include project name")
        self.assertIn("Andrew Stellman", stderr,
                      "banner must include author")
        self.assertIn(
            "https://github.com/andrewstellman/quality-playbook", stderr,
            "banner must include GitHub URL",
        )
        self.assertIn(
            "Quality engineering that finds the bugs review misses.",
            stderr,
            "banner must include the canonical tagline",
        )
        self.assertIn(
            "Apache License, Version 2.0", stderr,
            "banner must include the Apache-2.0 license line",
        )

    def test_banner_appears_on_stderr_verbose_mode(self) -> None:
        """The banner is unconditional — ``--verbose`` is required to
        produce it, but also doesn't suppress it. Same five-element
        check on stderr."""
        rc, _stdout, stderr = _capture_install(verbose=True)
        self.assertEqual(rc, 0, "verbose install must succeed")
        self.assertIn("Quality Playbook", stderr)
        self.assertIn("Andrew Stellman", stderr)
        self.assertIn(
            "https://github.com/andrewstellman/quality-playbook", stderr,
        )
        self.assertIn(
            "Quality engineering that finds the bugs review misses.",
            stderr,
        )
        self.assertIn("Apache License, Version 2.0", stderr)

    def test_banner_module_constants_drive_text(self) -> None:
        """The banner content lives in module-level constants — any
        future rename of the project, author, URL, tagline, or
        license MUST update both the constant and any human-facing
        copy in lockstep. Pin the constants here so a silent edit
        to one of them flips this test."""
        self.assertEqual(install_skill._BANNER_NAME, "Quality Playbook")
        self.assertEqual(install_skill._BANNER_AUTHOR, "Andrew Stellman")
        self.assertEqual(
            install_skill._BANNER_URL,
            "https://github.com/andrewstellman/quality-playbook",
        )
        self.assertEqual(
            install_skill._BANNER_TAGLINE,
            "Quality engineering that finds the bugs review misses.",
        )
        self.assertEqual(
            install_skill._BANNER_LICENSE,
            "Apache License, Version 2.0",
        )


class StdoutStaysParseCleanTests(unittest.TestCase):
    """Obligation 2 — LOAD-BEARING. The banner must NOT appear on
    stdout; the existing ``event=`` contract is intact."""

    def test_banner_does_not_appear_on_stdout(self) -> None:
        """The whole point of writing the banner to stderr: stdout
        stays a clean machine-parseable stream for calling agents.

        Mutation candidate: redirect the banner write to stdout.
        Expected failure: this test fails — the banner substring
        appears in stdout.
        Restoration: revert ``_print_banner``'s default target to
        ``sys.stderr``; passes.
        Bite executed during 089j development.
        """
        rc, stdout, _stderr = _capture_install(verbose=False)
        self.assertEqual(rc, 0)
        # Five negative pins — none of the five banner elements
        # may appear on stdout.
        for needle in (
            install_skill._BANNER_NAME,
            install_skill._BANNER_AUTHOR,
            install_skill._BANNER_URL,
            install_skill._BANNER_TAGLINE,
            install_skill._BANNER_LICENSE,
        ):
            self.assertNotIn(
                needle, stdout,
                f"089j: banner element {needle!r} leaked onto "
                f"stdout. The banner MUST stay on stderr — stdout "
                f"is a machine-parseable event=key=value stream "
                f"that strict agent parsers consume.",
            )
        # Box-drawing line must also be absent on stdout.
        self.assertNotIn(
            "=" * 30, stdout,
            "089j: banner box-drawing leaked onto stdout",
        )

    def test_banner_does_not_appear_on_stdout_in_verbose_mode(self) -> None:
        """Same negative pin in verbose mode (where stdout legitimately
        contains existing two-space prose continuation lines; the
        banner still must not appear)."""
        rc, stdout, _stderr = _capture_install(verbose=True)
        self.assertEqual(rc, 0)
        for needle in (
            install_skill._BANNER_NAME,
            install_skill._BANNER_AUTHOR,
            install_skill._BANNER_URL,
            install_skill._BANNER_TAGLINE,
            install_skill._BANNER_LICENSE,
        ):
            # NB: install_skill prose mentions "Quality Playbook" in
            # the verbose prose continuation for event=intro
            # ("Installing the Quality Playbook skill..."). That is
            # NOT the banner — it pre-existed 089j. Pin the URL +
            # license instead, which are banner-unique.
            if needle == install_skill._BANNER_NAME:
                continue
            if needle == install_skill._BANNER_AUTHOR:
                # Andrew Stellman is similarly potentially in prose;
                # only check the banner-unique elements.
                continue
            self.assertNotIn(
                needle, stdout,
                f"089j: banner element {needle!r} leaked onto "
                f"stdout in verbose mode.",
            )
        # Box-drawing line is banner-unique on stdout.
        self.assertNotIn("=" * 30, stdout,
                         "089j: banner box-drawing leaked onto stdout")

    def test_stdout_first_line_is_event_intro(self) -> None:
        """The ``event=intro`` line is and remains the FIRST stdout
        line. 089j must not push it down by inserting anything
        above (the banner goes to stderr, not stdout)."""
        rc, stdout, _stderr = _capture_install(verbose=False)
        self.assertEqual(rc, 0)
        lines = stdout.splitlines()
        self.assertGreater(len(lines), 0, "stdout must not be empty")
        self.assertTrue(
            lines[0].startswith("event=intro"),
            f"089j: stdout's first line must remain 'event=intro' "
            f"(found: {lines[0]!r}). The banner goes to stderr; "
            f"stdout's event= contract and ordering are untouched.",
        )

    def test_stdout_non_verbose_is_pure_event_stream(self) -> None:
        """In non-verbose mode, EVERY stdout line is a well-formed
        ``event=key`` record (or ``event=key key=value ...``).
        Verbose mode's two-space prose continuations are exempted
        from this rule (they pre-exist 089j)."""
        rc, stdout, _stderr = _capture_install(verbose=False)
        self.assertEqual(rc, 0)
        for i, line in enumerate(stdout.splitlines()):
            self.assertTrue(
                line.startswith("event="),
                f"089j: non-verbose stdout line {i} does not start "
                f"with 'event=': {line!r}. The banner must NOT have "
                f"leaked onto stdout; pre-existing event= contract "
                f"must hold.",
            )

    def test_event_install_complete_still_emitted(self) -> None:
        """The terminal ``event=install_complete`` event remains on
        stdout (the contract's tail anchor)."""
        rc, stdout, _stderr = _capture_install(verbose=False)
        self.assertEqual(rc, 0)
        self.assertRegex(
            stdout, r"event=install_complete\b",
            "089j: install_complete event must remain on stdout",
        )


class SmokeChecksStillPassTests(unittest.TestCase):
    """Obligation 3: the installer's existing smoke-check sequence
    runs and reports ``status=passed`` — the banner addition must
    not perturb the smoke pipeline."""

    def test_smoke_check_status_passed_on_stdout(self) -> None:
        """A complete install emits at least one
        ``event=smoke_check ... status=passed`` line on stdout."""
        rc, stdout, _stderr = _capture_install(verbose=False)
        self.assertEqual(rc, 0)
        self.assertRegex(
            stdout, r"event=smoke_check[^\n]*status=passed",
            "089j: smoke-check sequence must still report "
            "status=passed; the banner addition must not perturb "
            "the smoke pipeline.",
        )


if __name__ == "__main__":
    unittest.main()
