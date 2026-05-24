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


class BannerDirectivePresence090mTests(unittest.TestCase):
    """v1.5.7 090m — the Mode-A skill-load attribution banner lives
    in **SKILL.md's MANDATORY FIRST ACTION** (the file actually read
    at skill-load), NOT in phase1.md / AGENTS.md.

    Root-cause correction for 090k + 090l: those instructions
    placed the directive on the wrong surface (the agent reads
    SKILL.md at skill-load, so the phase1.md / AGENTS.md
    directives never overrode SKILL.md's then-condensed 2-line
    blockquote). 090m moves the directive to SKILL.md and removes
    the redundant phase1.md / AGENTS.md banner blocks.

    Tests:

      * ``test_skill_md_mandatory_first_action_carries_full_banner``
        — SKILL.md's MANDATORY FIRST ACTION reproduces the FULL
        canonical block (both taglines + license + 80-wide === rules),
        with NO ``v1.5.7``/version token inside the fenced banner,
        and the surrounding directive explicitly forbids condensation.
      * ``test_skill_md_banner_matches_purpose_byte_for_byte`` — the
        embedded banner block matches ``bin/_purpose.BANNER_TEXT``
        byte-for-byte (modulo Markdown fence/indent whitespace).
        Mutation bite: condense the SKILL.md banner → this test FAILs.
      * ``test_phase1_md_and_agents_md_carry_no_competing_banner_directive``
        — phase1.md no longer carries a "Skill-load attribution
        banner" block; AGENTS.md no longer carries a "Step 0" banner.
        Mutation bite: re-add a banner block to either surface →
        this test FAILs (the 090m single-source-of-truth pin).
    """

    # Lines of the canonical _purpose banner that MUST appear verbatim
    # in SKILL.md's MANDATORY FIRST ACTION fenced block.
    _CANONICAL_BANNER_LINES = (
        "  Quality Playbook — by Andrew Stellman",
        "  https://github.com/andrewstellman/quality-playbook",
        "  AI code review is good. Quality engineering is better.",
        "  Because code that looks right can still do the wrong thing.",
        "  Licensed under the Apache License, Version 2.0",
    )

    def _extract_first_banner_block(self, text: str) -> str:
        """Find the FIRST fenced ```…``` block whose body contains
        the canonical banner (80-wide === rule + the canonical
        author line + the license line) and return the inner
        block. The fence opener can be indented (Markdown list
        inside) — tolerate leading whitespace per line."""
        import re
        fence_pat = re.compile(
            r"^[ \t]*```[^\n]*\n([\s\S]*?)^[ \t]*```",
            re.MULTILINE,
        )
        for m in fence_pat.finditer(text):
            body = m.group(1)
            normalized_body = "\n".join(ln.lstrip()
                                        for ln in body.splitlines())
            if (
                "=" * 80 in normalized_body
                and "Quality Playbook — by Andrew Stellman"
                    in normalized_body
                and "Apache License" in normalized_body
            ):
                return body
        self.fail(
            "could not extract banner fence — must contain the "
            "80-wide === rule, the canonical author line, and the "
            "license line.",
        )

    def test_skill_md_mandatory_first_action_carries_full_banner(
            self) -> None:
        text = (_REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        # The MANDATORY FIRST ACTION must explicitly instruct against
        # condensation (090m mutation guard — the live openfga-run3
        # Mode-A runs emitted a 2-line condensed banner against the
        # pre-090m SKILL.md blockquote).
        self.assertIn("MANDATORY FIRST ACTION", text)
        self.assertIn(
            "do NOT condense, abbreviate, summarize, reformat, or add a version number",
            text,
        )
        # Reference the single source of truth so wording stays
        # in sync.
        self.assertIn("bin/_purpose.print_attribution_banner()", text)
        # Full canonical block must be present.
        self.assertIn("=" * 80, text,
                      "SKILL.md: missing 80-wide === rule")
        for line in self._CANONICAL_BANNER_LINES:
            self.assertIn(
                line, text,
                f"SKILL.md: missing canonical banner line {line!r} "
                f"— 090m forbids condensing the banner block.",
            )
        # NO version token inside the FIRST fenced banner block
        # (surrounding prose may carry "v1.5.7" / "090m" tracking
        # tags, but the fenced block itself must match _purpose
        # exactly, which has no version number).
        directive_banner = self._extract_first_banner_block(text)
        self.assertNotIn(
            "v1.5.7", directive_banner,
            "SKILL.md banner block contains a version token — "
            "090m requires the block to match _purpose.BANNER_TEXT "
            "byte-for-byte, and BANNER_TEXT has no version number.",
        )

    def test_skill_md_banner_matches_purpose_byte_for_byte(
            self) -> None:
        """090m single-source-of-truth check — the SKILL.md banner
        block must match ``bin/_purpose.BANNER_TEXT`` byte-for-byte
        modulo Markdown fence/indent whitespace.

        Mutation bite: shorten a tagline, drop the license line,
        add a version number, or change the 80-wide === rule → this
        test FAILs. Forces the SKILL.md banner and the
        ``_purpose.BANNER_*`` constants to evolve together.
        """
        from bin import _purpose
        canonical = _purpose.BANNER_TEXT
        # Sanity-check the canonical.
        self.assertIn("=" * 80, canonical)
        for line in self._CANONICAL_BANNER_LINES:
            self.assertIn(line, canonical,
                          f"_purpose.BANNER_TEXT missing {line!r}")
        text = (_REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        directive_banner = self._extract_first_banner_block(text)

        def _normalize(block: str) -> str:
            return "\n".join(ln.rstrip().lstrip()
                             for ln in block.splitlines())
        self.assertEqual(
            _normalize(directive_banner),
            _normalize(canonical),
            "SKILL.md: embedded banner block does NOT match "
            "bin/_purpose.print_attribution_banner() output after "
            "whitespace normalization. 090m requires byte-for-byte "
            "match modulo Markdown fence/indent whitespace. Update "
            "the SKILL.md banner block to match _purpose.BANNER_TEXT "
            "(the single source of truth).",
        )

    def test_phase1_md_and_agents_md_carry_no_competing_banner_directive(
            self) -> None:
        """090m single-source-of-truth pin: phase1.md and AGENTS.md
        must NOT carry their own banner-printing directives. Removing
        them is what makes SKILL.md the unambiguous skill-load surface.

        Mutation bite: re-add a "Skill-load attribution banner" block
        to phase1.md (or a "Step 0" Print-the-banner block to
        AGENTS.md) → this test FAILs.
        """
        phase1_text = (
            _REPO_ROOT / "phase_prompts" / "phase1.md"
        ).read_text(encoding="utf-8")
        # The 090k/090l directive carried this distinctive heading;
        # 090m removed it.
        self.assertNotIn(
            "Skill-load attribution banner",
            phase1_text,
            "phase_prompts/phase1.md still carries a 'Skill-load "
            "attribution banner' directive — 090m removed it; "
            "SKILL.md is now the single source.",
        )
        # phase1.md must not contain the canonical 80-wide === rule
        # (that's banner-block evidence) — its body is phase-1
        # exploration prose, never the attribution banner.
        self.assertNotIn(
            "=" * 80, phase1_text,
            "phase_prompts/phase1.md contains the 80-wide === rule "
            "— this is banner-block evidence; 090m removed the "
            "banner directive from this file.",
        )

        agents_text = (_REPO_ROOT / "AGENTS.md").read_text(
            encoding="utf-8",
        )
        # AGENTS.md Step 0 was the 090k/090l banner step; 090m
        # collapsed it to a pointer-only note.
        self.assertNotIn(
            "0. **Print the FULL attribution banner",
            agents_text,
            "AGENTS.md still carries a 'Step 0: Print the FULL "
            "attribution banner' directive — 090m removed it; "
            "SKILL.md is now the single source.",
        )
        # The 090m pointer-only AGENTS.md note must reference
        # SKILL.md as the source of truth so a future reader knows
        # where the banner actually lives.
        self.assertIn(
            "the SKILL.md MANDATORY FIRST ACTION",
            agents_text,
            "AGENTS.md must include a pointer telling readers that "
            "the Mode-A skill-load banner lives in SKILL.md (090m).",
        )


if __name__ == "__main__":
    unittest.main()
