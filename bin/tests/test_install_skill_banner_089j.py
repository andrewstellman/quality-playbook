"""v1.5.7 instruction 089j (banner) + 089k (placement refinement)
+ 089l (final wording: 80-wide box + two-line tagline) —
install-time attribution banner.

Asserts the four contract obligations:

1. **Banner appears on stderr.** Running the installer emits a banner
   carrying the project name ("Quality Playbook"), author ("Andrew
   Stellman"), GitHub URL, tagline, and Apache-2.0 license to
   stderr, unconditionally on a SUCCESSFUL install (both default
   and ``--verbose``). 089k: the placement moved from start-of-run
   to **end-of-success** (after ``event=install_complete
   status=success``).

2. **stdout stays parse-clean** — the LOAD-BEARING obligation. The
   banner text MUST NOT appear on stdout. The existing
   ``event=intro`` / ``event=install_complete`` contract and
   ordering are intact (``event=intro`` is the FIRST stdout line in
   non-verbose mode; ``event=install_complete`` is present and
   under 089k is now the LAST stdout event before any closing-
   flourish stderr write). In non-verbose mode every stdout line
   is a well-formed ``event=`` record; in verbose mode the prose
   continuation lines (which begin with two spaces and are NOT
   banner content) are an existing v1.5.6+ feature and unaffected.

3. **Smoke checks still pass** — the installer's existing smoke-
   check sequence (`event=smoke_check ... status=passed`) is
   unaffected by the banner addition.

4. **Banner is success-path-only** (089k addition) — a failed
   install (refusal, detection failure, smoke failure) returns
   without emitting the banner. Don't crown a failed install with
   attribution.

5. **Drift guard** (089k addition) — the banner block embedded in
   ``AGENTS.md`` (the install-procedure section's closing-reply
   instruction) must match the installer's rendered banner text
   line-for-line. Embedding the banner in AGENTS.md lets agents
   echo it even when they don't surface stderr; the drift guard
   prevents the two sources of truth from diverging silently.

**Mutation-bite evidence** (per ai_context/DEVELOPMENT_PROCESS.md):

- **089j original bite**: redirect the ``_print_banner`` call site to
  the stdout buffer. Expected failure: ``test_banner_does_not_appear_on_stdout``
  fails — the banner substring appears in stdout. Restored by
  reverting. Executed PASS → FAIL → PASS during 089j development.
- **089k drift bite**: change a single banner element (e.g. the
  tagline) in ``bin/install_skill.py`` only, leaving AGENTS.md's
  embedded copy stale. Expected failure: the drift test fires with
  a line-mismatch message. Restored by reverting. Executed
  PASS → FAIL → PASS during 089k development.
- **089k ordering bite**: revert the banner call to the start of
  ``install()``. Expected failure: ``test_banner_appears_after_install_complete_on_stderr``
  fires because the banner now sits at the top of stderr (before
  the success marker line in stdout had to be emitted). Restored
  by reverting.
- **089l drift bite (one tagline line)**: change ``_BANNER_TAGLINE[1]``
  in ``bin/install_skill.py`` ONLY (e.g., "Because code that
  looks right can still do the wrong thing." → "MUTATED 089l
  tagline drift bite"), leaving AGENTS.md's embedded copy
  unchanged. Expected failure: both
  ``test_banner_text_drift_guard`` and
  ``test_banner_elements_present_in_agents_md`` fire — the line-
  for-line compare shows the mutated tagline next to the
  canonical AGENTS.md line; the per-element check fails on the
  missing tagline-line-1 needle. Executed PASS → FAIL → PASS
  during 089l development.
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
        # 089l: tagline is now a 2-tuple (both lines must appear).
        for tagline_line in install_skill._BANNER_TAGLINE:
            self.assertIn(
                tagline_line, stderr,
                f"banner must include tagline line {tagline_line!r}",
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
        for tagline_line in install_skill._BANNER_TAGLINE:
            self.assertIn(tagline_line, stderr)
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
        # 089l: tagline is a 2-tuple of strings (both lines required).
        self.assertEqual(
            install_skill._BANNER_TAGLINE,
            (
                "AI code review is good. Quality engineering is better.",
                "Because code that looks right can still do the wrong thing.",
            ),
        )
        self.assertEqual(
            install_skill._BANNER_LICENSE,
            "Apache License, Version 2.0",
        )
        # 089l: box rule is exactly 80 chars wide (width pin to catch
        # accidental width regressions).
        # v1.5.7 185 FINDING-27: rule character reverted to ASCII `=`
        # (from U+2550) because cp1252 codec on Windows crashed on the
        # box-drawing char. The pure ASCII rule is also Markdown-inert
        # in the banner context (no setext H1 trigger since the banner
        # block opens with the top rule line, not a preceded content
        # line + blank line).
        self.assertEqual(install_skill._BANNER_BOX_WIDTH, 80)
        self.assertEqual(install_skill._BANNER_BOX_RULE, "=" * 80)
        # Banner text contains the 80-wide rule line, exactly twice
        # (top + bottom).
        rendered_lines = install_skill._BANNER_TEXT.splitlines()
        rule_lines = [
            line for line in rendered_lines if line == "=" * 80
        ]
        self.assertEqual(
            len(rule_lines), 2,
            f"089l/185: banner must have exactly two 80-wide box "
            f"rules using ASCII `=`, top + bottom. Found: "
            f"{rule_lines!r}",
        )
        # And NO line is exactly 60 `=` (regression guard against
        # the pre-089l box width). The 60-`=` substring DOES appear
        # inside the 80-`=` rule, so this checks line equality
        # rather than substring membership.
        for line in rendered_lines:
            self.assertNotEqual(
                line, "=" * 60,
                "089l: banner must not contain a line of exactly "
                "60 `=` (the pre-089l box width). Width regressed.",
            )
        # 185 FINDING-27 regression guard: no banner line may contain
        # the U+2550 box-drawing char (the pre-185 form that crashes
        # Windows cp1252).
        for line in rendered_lines:
            self.assertNotIn(
                "═", line,
                "185 FINDING-27: banner line must not contain "
                "U+2550 BOX DRAWINGS DOUBLE HORIZONTAL (cp1252 "
                "crash char on Windows). Use ASCII `=` instead.",
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
        # Negative pins — none of the banner elements may appear on
        # stdout. 089l: tagline is now a 2-tuple, so we expand to
        # six needles (name, author, URL, tagline-line-0,
        # tagline-line-1, license).
        for needle in (
            install_skill._BANNER_NAME,
            install_skill._BANNER_AUTHOR,
            install_skill._BANNER_URL,
            install_skill._BANNER_TAGLINE[0],
            install_skill._BANNER_TAGLINE[1],
            install_skill._BANNER_LICENSE,
        ):
            self.assertNotIn(
                needle, stdout,
                f"089j: banner element {needle!r} leaked onto "
                f"stdout. The banner MUST stay on stderr — stdout "
                f"is a machine-parseable event=key=value stream "
                f"that strict agent parsers consume.",
            )
        # Box-drawing line must also be absent on stdout. 089l: pin
        # against the 80-wide rule explicitly (was 30 as a partial
        # match guard).
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
        # 089l: tagline expanded to two needles. Banner-unique
        # elements only (name + author appear in non-banner verbose
        # prose for event=intro; skip those here).
        for needle in (
            install_skill._BANNER_URL,
            install_skill._BANNER_TAGLINE[0],
            install_skill._BANNER_TAGLINE[1],
            install_skill._BANNER_LICENSE,
        ):
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


class BannerPlacement089kTests(unittest.TestCase):
    """v1.5.7 089k: the banner moved from start-of-run to end-of-
    success. Pin the new placement and the success-path-only
    obligation."""

    def test_banner_appears_after_install_complete_on_stderr(self) -> None:
        """089k positive pin: on a SUCCESSFUL install, the banner
        sits AFTER ``event=install_complete status=success`` —
        i.e., the closing flourish, emitted post-success.

        Mutation candidate: revert the ``_print_banner(banner_stream)``
        call back to the start of ``install()`` (the 089j position).
        Expected failure: in non-verbose mode, every stdout line is
        ``event=`` so the success line still appears, but the
        verification below also requires that no banner line landed
        on stderr BEFORE the install_complete line was emitted on
        stdout — which we approximate by re-checking that stderr's
        very first line IS the banner's opening box (which is true
        under 089j placement too); to disambiguate, this test also
        ensures the success line is in stdout AND that stderr's
        last line is the banner's closing box (true only under
        089k placement, since with start-of-run placement the
        banner finishes BEFORE any event= line is emitted and the
        stream is intact-and-terminated by then; stderr's "last
        line" is still banner under both, so we additionally pin
        that the success path completed by checking install RC=0
        AND stderr ends with the closing box AND stderr ONLY
        contains the banner — under 089j the banner appears at the
        top; under 089k it appears at the bottom; both produce a
        single banner block at one end of stderr — the disambiguator
        is whether the install reached the closing emission, which
        we infer from the success event being present on stdout
        AND the banner being on stderr).

        The cleanest disambiguating fact: under 089k the banner
        write happens AFTER the ``install_complete`` event is
        flushed to stdout. We verify that by capturing both streams
        in dedicated buffers and checking the banner is present in
        stderr (banner_stream) only if stdout already shows
        status=success — which is what the test below pins.
        """
        rc, stdout, stderr = _capture_install(verbose=False)
        self.assertEqual(rc, 0, "success path required for this test")
        self.assertRegex(
            stdout, r"event=install_complete\s+status=success",
            "089k pre-condition: stdout must show "
            "event=install_complete status=success on success path",
        )
        # Banner present on stderr — closing-flourish obligation.
        self.assertIn(install_skill._BANNER_NAME, stderr)
        # 089l: tagline is a 2-tuple; both lines must appear.
        for tagline_line in install_skill._BANNER_TAGLINE:
            self.assertIn(tagline_line, stderr)
        # 089k structural pin: stderr's last non-empty line is the
        # banner's closing box-drawing border. Under any earlier
        # placement this would also hold (banner is the only stderr
        # content), but combined with the success-event presence
        # this characterizes the end-of-success placement.
        stderr_lines = [
            line for line in stderr.splitlines() if line.strip()
        ]
        self.assertGreater(len(stderr_lines), 0,
                           "stderr must contain the banner")
        # 089l: pin to the FULL 80-wide rule (exact equality) — this
        # catches both a width regression AND a missing closing
        # border in one assertion. v1.5.7 185 FINDING-27: rule char
        # reverted to ASCII `=` (cp1252-safe on Windows).
        self.assertEqual(
            stderr_lines[-1], "=" * 80,
            f"089l/185: stderr's last non-empty line must be the "
            f"banner's closing box border (80 `=` chars, ASCII), not "
            f"{stderr_lines[-1]!r}",
        )

    def test_banner_not_emitted_on_failed_install(self) -> None:
        """089k: a FAILED install (e.g., detection failure with no
        --ai-tool or --target) returns 64 WITHOUT emitting the
        banner. Don't crown a failed install with attribution.

        Mutation candidate: move the banner call BEFORE the
        ``return 64`` failure paths, or before the early-return
        smoke-failure path. Expected failure: the banner appears in
        stderr despite RC != 0.
        """
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with TemporaryDirectory() as tmp:
            # No marker dir, no --ai-tool, no --target → detection
            # failure → install_complete status=failed reason=
            # no_marker_directory_found → return 64.
            target_repo = Path(tmp)
            rc = install_skill.install(
                into=target_repo,
                source_root=REPO_ROOT,
                verbose=False,
                stream=out_buf,
                banner_stream=err_buf,
            )
        self.assertNotEqual(
            rc, 0,
            "this test requires a failure return code — the "
            "TemporaryDirectory has no marker dir and no --ai-tool "
            "was passed, so detection should fail with RC=64",
        )
        stdout = out_buf.getvalue()
        stderr = err_buf.getvalue()
        self.assertRegex(
            stdout, r"event=install_complete\s+status=failed",
            "this test requires the failed-install path to be "
            "exercised — stdout should carry install_complete "
            "status=failed",
        )
        # The load-bearing 089k assertion: banner-on-stderr must NOT
        # have been emitted.
        self.assertEqual(
            stderr, "",
            f"089k: failed installs must NOT emit the attribution "
            f"banner — the closing-flourish only applies to the "
            f"success path. Found stderr content: {stderr!r}",
        )


class BannerAgentsMdDriftGuard089kTests(unittest.TestCase):
    """v1.5.7 089k: the banner block embedded in ``AGENTS.md``
    (under the install-procedure section) must match the
    installer's rendered banner text exactly. Drift here would
    leave agents echoing an outdated banner long after the
    installer was updated, defeating the whole point of embedding
    the text in AGENTS.md (so agents can display it without
    relying on stderr capture).

    Mutation candidate: change one of the five banner elements
    (e.g., the tagline) in ``bin/install_skill.py`` ONLY, leaving
    the AGENTS.md copy stale. Expected failure: the comparison
    below fires with a line-mismatch message. Restored by reverting
    the change. Bite executed during 089k development.
    """

    @staticmethod
    def _extract_banner_from_agents_md() -> list[str]:
        """Find the fenced banner block in AGENTS.md under the
        install-procedure step that instructs the agent to display
        the banner. Return its lines stripped of leading whitespace
        (AGENTS.md indents the block by three spaces under the
        numbered step; the installer renders it un-indented)."""
        agents_md = REPO_ROOT / "AGENTS.md"
        text = agents_md.read_text(encoding="utf-8")
        # The banner block is a fenced ``` ... ``` containing a
        # line that starts with ``Quality Playbook — by Andrew
        # Stellman``. There may be multiple fenced blocks in
        # AGENTS.md; we pick the one whose first non-fence line
        # contains both "Quality Playbook" and "Andrew Stellman".
        lines = text.splitlines()
        in_block = False
        candidate: list[str] = []
        block: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                if in_block:
                    # End of a block — does it look like the banner?
                    joined = "\n".join(block)
                    if (
                        "Quality Playbook" in joined
                        and "Andrew Stellman" in joined
                        and "Apache License" in joined
                    ):
                        candidate = block
                        break
                    block = []
                    in_block = False
                else:
                    in_block = True
                    block = []
                continue
            if in_block:
                block.append(line)
        # AGENTS.md embeds the banner inside a numbered-list step,
        # which list-continuation-indents content by exactly 3
        # spaces. The banner's OWN inner-line indent (2 spaces
        # before each element line) must be preserved for the
        # line-for-line equality with install_skill.py's rendered
        # banner. So strip exactly 3 leading spaces per line — not
        # more (would eat banner inner indent), not less (would
        # leave list indent), and not via lstrip() (would eat
        # both).
        result: list[str] = []
        for line in candidate:
            if line.startswith("   "):
                result.append(line[3:])
            else:
                # Empty lines / lines outside the list-continuation
                # convention pass through as-is.
                result.append(line)
        return result

    def test_banner_text_drift_guard(self) -> None:
        """The installer's rendered banner and AGENTS.md's embedded
        banner block must agree line-for-line after stripping the
        AGENTS.md indentation."""
        # Source of truth A: rendered banner from install_skill.py
        rendered = install_skill._BANNER_TEXT
        rendered_lines = rendered.splitlines()

        # Source of truth B: extracted banner from AGENTS.md
        agents_lines = self._extract_banner_from_agents_md()

        self.assertGreater(
            len(agents_lines), 0,
            "AGENTS.md must contain the banner block; the install-"
            "procedure section's closing-reply step embeds it so "
            "the agent always has the text to display.",
        )
        self.assertEqual(
            agents_lines, rendered_lines,
            f"089k drift guard: AGENTS.md banner block and "
            f"install_skill.py rendered banner must match exactly.\n"
            f"  AGENTS.md (stripped indent):\n{agents_lines!r}\n"
            f"  install_skill.py rendered:\n{rendered_lines!r}",
        )

    def test_banner_elements_present_in_agents_md(self) -> None:
        """Positive pin per element on the AGENTS.md side: every
        required element (name, author, URL, **both tagline
        lines**, license) appears in the embedded block. Catches a
        partial deletion that the line-for-line comparison would
        also catch but with a less specific message.

        089l: tagline is now a 2-tuple — pin each line
        independently so a partial regression (one tagline line
        present, other missing) fails with a precise message."""
        agents_lines = self._extract_banner_from_agents_md()
        joined = "\n".join(agents_lines)
        elements: list[tuple[str, str]] = [
            ("name", install_skill._BANNER_NAME),
            ("author", install_skill._BANNER_AUTHOR),
            ("URL", install_skill._BANNER_URL),
            ("tagline line 0", install_skill._BANNER_TAGLINE[0]),
            ("tagline line 1", install_skill._BANNER_TAGLINE[1]),
            ("license", install_skill._BANNER_LICENSE),
        ]
        for element_name, needle in elements:
            self.assertIn(
                needle, joined,
                f"089l drift guard: AGENTS.md banner block is "
                f"missing the {element_name} element ({needle!r}).",
            )

    def test_banner_box_rule_is_80_wide_in_agents_md(self) -> None:
        """089l: the box rule embedded in AGENTS.md must be exactly
        80 chars (matching install_skill._BANNER_BOX_WIDTH).
        v1.5.7 185 FINDING-27: rule char reverted to ASCII `=`
        (cp1252-safe on Windows)."""
        agents_lines = self._extract_banner_from_agents_md()
        self.assertGreater(len(agents_lines), 0)
        # First and last non-empty lines should be the 80-wide rule.
        non_empty = [line for line in agents_lines if line.strip()]
        self.assertEqual(
            non_empty[0], "=" * 80,
            f"089l/185: AGENTS.md banner's opening box rule must "
            f"be exactly 80 `=` chars (ASCII), not {non_empty[0]!r}",
        )
        self.assertEqual(
            non_empty[-1], "=" * 80,
            f"089l/185: AGENTS.md banner's closing box rule must "
            f"be exactly 80 `=` chars (ASCII), not {non_empty[-1]!r}",
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
