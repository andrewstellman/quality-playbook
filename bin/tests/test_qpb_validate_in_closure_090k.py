"""v1.5.7 instruction 090k — qpb_validate.py must ship in the install closure.

Surfaced 2026-05-24 by the openfga-run3 npm-channel Mode-A dogfood
(Claude Code Opus 4.7): the agent followed the canonical Mode-A
entry sequence (per AGENTS.md / SKILL.md:68) and ran

    python3 <install>/.claude/skills/quality-playbook/bin/qpb_validate.py <target>

— and hit ``[Errno 2] No such file or directory``, because
``bin/install_skill.py::_bundle_files()`` EXCLUDED ``qpb_validate.py``
from the closure on a now-wrong rationale ("the Phase 0 entry-point
is invoked from the QPB clone"). The npm tarball did ship
``quality_playbook_cli/_bundle/bin/qpb_validate.py`` (~70.5 kB), but
the closure ``install_skill`` copied to ``<install>/.../bin/`` omitted
it. Mode-A agents read SKILL.md / README / AGENTS.md, all of which
point at the installed-skill bin path — so the file MUST be present
there for Phase 0 to pass.

Tests:

* ``test_qpb_validate_is_in_bundle_files`` — closure membership pin.
  Mutation bite (executable): delete the
  ``_require_bundle_file(... / "qpb_validate.py")`` line from
  ``_bundle_files()`` → this test FAILs.

* ``test_install_creates_qpb_validate_in_closure_bin`` — install
  into a temp target, assert the closure ``bin/`` contains
  ``qpb_validate.py``. Reproduces the openfga-run3 ``Errno 2``
  failure mode (file absent) → fails. Restore the closure entry
  → file present → passes.

* ``test_installed_qpb_validate_runs_from_closure_with_no_qpb_on_pythonpath``
  — the END-to-END regression: install the skill into a fresh
  temp target, invoke
  ``python3 <install>/.../bin/qpb_validate.py <target>`` as a
  SUBPROCESS with ``PYTHONPATH`` SCRUBBED of the QPB clone, and
  assert it emits ``event=validation_complete``. This is the
  load-bearing test the instruction Task C requires — it proves
  the validator's import closure self-resolves at the install
  root WITHOUT the QPB clone on path (the openfga-run3 failure
  mode would have been caught by this).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bin import install_skill


_REPO_ROOT = Path(__file__).resolve().parents[2]


class QpbValidateInClosure090kTests(unittest.TestCase):

    def test_qpb_validate_is_in_bundle_files(self) -> None:
        """_bundle_files() must include bin/qpb_validate.py."""
        bundle = install_skill._bundle_files(_REPO_ROOT)
        bin_dests = [str(dst) for _src, dst in bundle]
        self.assertIn(
            "bin/qpb_validate.py", bin_dests,
            "v1.5.7 090k: install_skill._bundle_files() must include "
            "bin/qpb_validate.py in the install closure. The 2026-05-24 "
            "openfga-run3 Mode-A dogfood reproduced 'Errno 2' because "
            "this file was missing from <install>/.../bin/.",
        )

    def test_install_skill_itself_still_excluded(self) -> None:
        """install_skill.py itself must NEVER be in the closure — the
        installer cannot install itself (the install_root has no use
        for the installer module). Pin this so a future overcorrection
        doesn't bundle the installer along with qpb_validate.py."""
        bundle = install_skill._bundle_files(_REPO_ROOT)
        bin_dests = [str(dst) for _src, dst in bundle]
        self.assertNotIn(
            "bin/install_skill.py", bin_dests,
            "install_skill.py must NOT be in the install closure — "
            "the installer cannot install itself.",
        )

    def test_install_creates_qpb_validate_in_closure_bin(self) -> None:
        """A real install must produce a closure ``bin/`` directory
        containing qpb_validate.py at the expected path."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            installed_validator = (
                target / ".github" / "skills" / "quality-playbook"
                / "bin" / "qpb_validate.py"
            )
            self.assertTrue(
                installed_validator.is_file(),
                f"v1.5.7 090k: install closure must place qpb_validate.py "
                f"at {installed_validator}; the openfga-run3 dogfood "
                f"reproduced Errno 2 here. Got missing.",
            )
            # Sanity check the file is the real validator, not a stub.
            head = installed_validator.read_text(
                encoding="utf-8", errors="ignore"
            )[:2000]
            self.assertIn("qpb_validate", head)

    def test_installed_qpb_validate_runs_from_closure_with_no_qpb_on_pythonpath(
            self) -> None:
        """The load-bearing 090k e2e: install the skill, then run
        ``python3 <install>/.../bin/qpb_validate.py <target>`` as a
        SUBPROCESS with PYTHONPATH scrubbed of the QPB clone. The
        validator MUST self-resolve its import closure from the
        install root (per 090k's Halt condition: ``qpb_validate.py``'s
        import closure must run self-contained — its module-level
        imports are stdlib-only, and the lazy ``from bin._purpose
        import …`` finds ``_purpose.py`` in the same install closure).

        Mutation bite: drop ``_purpose.py`` from the closure (or drop
        ``qpb_validate.py`` itself) → the subprocess crashes with
        ImportError / Errno 2 → this test FAILs."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            installed_validator = (
                target / ".github" / "skills" / "quality-playbook"
                / "bin" / "qpb_validate.py"
            )
            self.assertTrue(installed_validator.is_file())

            # Scrub the QPB clone from PYTHONPATH for the subprocess.
            env = {k: v for k, v in os.environ.items()
                   if k != "PYTHONPATH"}
            env["PYTHONPATH"] = ""  # explicitly empty
            # Tell qpb_validate.py to validate the temp target dir.
            result = subprocess.run(
                [sys.executable, str(installed_validator), str(target)],
                env=env, cwd=str(target),
                capture_output=True, text=True, timeout=60,
            )
            full_output = result.stdout + result.stderr
            # The validator emits structured event= lines. We don't
            # require status=ok (the temp target isn't a fully scaffolded
            # QPB-aware repo); we require that it RAN to completion —
            # i.e. emitted validation_complete with some terminal
            # status. The pre-090k failure mode was ``Errno 2: No such
            # file`` (the file didn't exist) OR ImportError (couldn't
            # find _purpose). Either is a hard pre-validator crash;
            # the test asserts the validator at least RAN.
            self.assertIn(
                "event=validation_complete",
                full_output,
                f"v1.5.7 090k: installed qpb_validate.py must run from "
                f"the install closure with no QPB clone on PYTHONPATH "
                f"and emit event=validation_complete. Got:\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n"
                f"returncode: {result.returncode}",
            )


class BannerDirectivePresence090kTests(unittest.TestCase):
    """v1.5.7 090k Task A + 090l refinement — the Mode-A run-start
    sequence must instruct the agent to print the FULL canonical
    attribution banner ONCE as the first content of its first
    response, anchored to skill-load (NOT vaguer "run start").

    Two surfaces are checked:

    1. ``AGENTS.md`` carries the directive in the "Mode A entry
       sequence" section (canonical for QPB-clone-based agents).
    2. ``phase_prompts/phase1.md`` carries a parallel directive at
       the top (for channel-installed Mode A agents who don't have
       AGENTS.md in their install bundle — AGENTS.md is NOT in
       _bundle_files()).

    090l additions (mutation bites in docstrings):

      * Each surface must include the FULL banner block — both
        taglines + the license line + the two ``===…===`` 80-wide
        rules. A future edit that condenses to a shorter banner
        (e.g. the 2-line "▎ Quality Playbook v1.5.7 — by Andrew
        Stellman / ▎ https://…" the live OpenFGA Mode-A run emitted
        before 090l) → these tests FAIL.
      * The banner block must NOT contain a version token
        (``v1.5.7``, ``v1.6.0``, …) — match ``_purpose`` exactly.
      * The directive must anchor printing to immediately-after-
        skill-load / first-content-of-first-response, not to
        vaguer "run start." Both ``skill`` and ``first response``
        / ``first content`` framing must be present.
      * The directive must explicitly forbid condensing /
        abbreviating / summarizing / reformatting the block.

    090l consistency check (``test_directive_banner_matches_purpose``)
    — the embedded banner block in the directive must match
    ``bin/_purpose.print_attribution_banner()`` output byte-for-byte
    (a single source of truth pin). Mutation bite: edit either
    surface's banner text → this test FAILs.
    """

    # Lines of the canonical _purpose banner that MUST appear verbatim
    # in both AGENTS.md Step 0 and phase_prompts/phase1.md.
    _CANONICAL_BANNER_LINES = (
        "  Quality Playbook — by Andrew Stellman",
        "  https://github.com/andrewstellman/quality-playbook",
        "  AI code review is good. Quality engineering is better.",
        "  Because code that looks right can still do the wrong thing.",
        "  Licensed under the Apache License, Version 2.0",
    )

    def _assert_full_banner_block_present(self, text: str,
                                          surface_name: str) -> None:
        # 80-wide === rule (the banner top + bottom border).
        self.assertIn("=" * 80, text,
                      f"{surface_name}: missing 80-wide === rule")
        for line in self._CANONICAL_BANNER_LINES:
            self.assertIn(
                line, text,
                f"{surface_name}: missing canonical banner line "
                f"{line!r} — 090l forbids condensing the banner block.",
            )

    def _extract_directive_banner_block(self, text: str) -> str:
        """Find a fenced ```…``` block whose body contains the
        canonical banner (80-wide === rule + the canonical
        signature lines) and return the inner block. AGENTS.md
        Step 0's fence is inside a numbered-list item, so each body
        line is indented with 3 spaces; phase1.md's fence is
        un-indented. Match either by tolerating leading whitespace
        per line.

        The block is identified by scanning fenced regions and
        picking the one(s) that contain BOTH the 80-`=` rule AND
        the "Quality Playbook — by Andrew Stellman" canonical
        author line. For surfaces with multiple banner fences
        (AGENTS.md has both a 089j install-banner block and a 090l
        Step 0 block), we accept the LAST match — Step 0 is
        appended after the install-banner-in-step-7 block."""
        import re
        # Match fenced regions: ``` opener, any body, ``` closer.
        # The fence opener can be indented (Markdown list inside).
        fence_pat = re.compile(
            r"^[ \t]*```[^\n]*\n([\s\S]*?)^[ \t]*```",
            re.MULTILINE,
        )
        matches = list(fence_pat.finditer(text))
        candidates: list[str] = []
        for m in matches:
            body = m.group(1)
            # Strip any per-line leading whitespace before matching.
            normalized_body = "\n".join(ln.lstrip()
                                        for ln in body.splitlines())
            if (
                "=" * 80 in normalized_body
                and "Quality Playbook — by Andrew Stellman"
                    in normalized_body
                and "Apache License" in normalized_body
            ):
                candidates.append(body)
        self.assertGreater(
            len(candidates), 0,
            "could not extract banner fence — directive must wrap "
            "the canonical banner block in a triple-backtick fence "
            "containing the 80-wide === rule, the canonical "
            "author line, and the license line.",
        )
        return candidates[-1]

    def test_agents_md_carries_skill_load_anchored_banner_step(
            self) -> None:
        text = (_REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        # 090l skill-load anchor — must reference the skill-load
        # trigger and "first content of your first response," not
        # just vague "run start."
        self.assertIn(
            "0. **Print the FULL attribution banner immediately after the skill loads",
            text,
            "AGENTS.md Step 0 must anchor banner printing to "
            "immediately-after-skill-load (090l), not vaguer 'run "
            "start' (the 090k phrasing).",
        )
        self.assertIn("first content of your first response", text)
        # The directive must reference the canonical _purpose source
        # so wording stays in sync.
        self.assertIn("bin/_purpose.print_attribution_banner()", text)
        # Full canonical block present (090l).
        self._assert_full_banner_block_present(text, "AGENTS.md")
        # Forbid condensation (090l mutation guard).
        self.assertIn("Do NOT condense, abbreviate, summarize", text)
        # NO version token inside the directive's banner FENCE.
        directive_banner = self._extract_directive_banner_block(text)
        # Permit "v1.5.7" outside the fence (in the surrounding
        # paragraph as a tracking tag), but NEVER inside it.
        self.assertNotIn(
            "v1.5.7", directive_banner,
            "AGENTS.md banner block contains a version token — "
            "090l requires the block to match _purpose.BANNER_TEXT "
            "byte-for-byte, and BANNER_TEXT has no version number.",
        )
        # Once-per-run rule — must explicitly forbid reprinting.
        self.assertIn("exactly once", text)
        self.assertIn("Do NOT reprint", text)

    def test_phase1_md_carries_skill_load_anchored_banner_directive(
            self) -> None:
        text = (_REPO_ROOT / "phase_prompts" / "phase1.md").read_text(
            encoding="utf-8"
        )
        # The 090l header tag distinguishes the directive from the
        # surrounding phase1 prose.
        self.assertIn(
            "Skill-load attribution banner (v1.5.7 090k + 090l",
            text,
            "phase_prompts/phase1.md must carry the skill-load "
            "anchored banner directive for channel-installed Mode A "
            "agents (AGENTS.md is not in the install bundle).",
        )
        self.assertIn(
            "immediately after the Quality Playbook skill loaded",
            text,
        )
        self.assertIn("DO NOT reprint", text)
        # Full canonical block present (090l).
        self._assert_full_banner_block_present(text, "phase1.md")
        # NO version token inside the directive's banner FENCE.
        directive_banner = self._extract_directive_banner_block(text)
        self.assertNotIn(
            "v1.5.7", directive_banner,
            "phase1.md banner block contains a version token — "
            "090l requires the block to match _purpose.BANNER_TEXT "
            "byte-for-byte, and BANNER_TEXT has no version number.",
        )
        # Forbid condensation (090l mutation guard).
        self.assertIn(
            "do NOT condense, abbreviate, summarize, or reformat",
            text,
        )

    def test_directive_banner_matches_purpose_byte_for_byte(
            self) -> None:
        """090l consistency check — the embedded banner block in
        each directive surface must match
        ``bin/_purpose.print_attribution_banner()`` output byte-for-
        byte. Single source of truth: ``_purpose.BANNER_TEXT``.

        Mutation bite: edit either surface's banner text (e.g. shorten
        a tagline, drop the license line, add a version number,
        change the 80-wide === rule) → this test FAILs.
        """
        # Import _purpose and obtain its rendered banner.
        from bin import _purpose
        canonical = _purpose.BANNER_TEXT
        # Sanity-check the canonical itself — BANNER_TEXT should
        # carry the 80-wide rule, both taglines, and the license line.
        self.assertIn("=" * 80, canonical)
        for line in self._CANONICAL_BANNER_LINES:
            self.assertIn(line, canonical,
                          f"_purpose.BANNER_TEXT missing {line!r}")

        for surface_path in (
            _REPO_ROOT / "AGENTS.md",
            _REPO_ROOT / "phase_prompts" / "phase1.md",
        ):
            text = surface_path.read_text(encoding="utf-8")
            directive_banner = self._extract_directive_banner_block(
                text,
            )
            # The directive surfaces use a 3-space indent inside
            # AGENTS.md (Step 0 is a numbered-list item) and no
            # indent in phase1.md. Strip a leading 3-space indent
            # from each line for AGENTS.md before comparing — but
            # the canonical _purpose banner has 2-space indents on
            # the inner lines. Normalize by stripping leading
            # whitespace on each line for the comparison.
            def _normalize(block: str) -> str:
                return "\n".join(ln.rstrip().lstrip()
                                 for ln in block.splitlines())
            self.assertEqual(
                _normalize(directive_banner),
                _normalize(canonical),
                f"{surface_path.name}: embedded banner block does NOT "
                f"match bin/_purpose.print_attribution_banner() output "
                f"after whitespace normalization. 090l requires "
                f"byte-for-byte match modulo Markdown-list-indent "
                f"whitespace. Update the surface's banner block to "
                f"match _purpose.BANNER_TEXT (the single source of "
                f"truth).",
            )


if __name__ == "__main__":
    unittest.main()
