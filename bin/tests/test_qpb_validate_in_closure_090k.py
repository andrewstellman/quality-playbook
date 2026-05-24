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
    """v1.5.7 090k Task A — the Mode-A run-start sequence must instruct
    the agent to print the attribution banner ONCE at the start of its
    first response, before Phase 0.

    Two surfaces are checked:

    1. ``AGENTS.md`` carries the directive in the "Mode A entry
       sequence" section (canonical for QPB-clone-based agents).
    2. ``phase_prompts/phase1.md`` carries a parallel directive at
       the top (for channel-installed Mode A agents who don't have
       AGENTS.md in their install bundle — AGENTS.md is NOT in
       _bundle_files()).

    Mutation bite: drop either directive → the test FAILs.
    """

    def test_agents_md_carries_run_start_banner_step(self) -> None:
        text = (_REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(
            "0. **Print the attribution banner ONCE at run start",
            text,
            "AGENTS.md must instruct Mode A agents to print the "
            "attribution banner once at run start before Phase 0 "
            "(v1.5.7 090k Task A).",
        )
        # The directive must reference the canonical _purpose.py source
        # so wording stays in sync.
        self.assertIn("bin/_purpose.print_attribution_banner()", text)
        # The directive must include the actual banner BOX (the
        # 80-equal-sign rule) so the agent has the literal text in
        # context.
        self.assertIn("=" * 80, text)
        # Once-per-run rule — must explicitly forbid reprinting.
        self.assertIn("exactly once", text)

    def test_phase1_md_carries_run_start_banner_directive(self) -> None:
        text = (_REPO_ROOT / "phase_prompts" / "phase1.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "Run-start attribution banner (v1.5.7 090k",
            text,
            "phase_prompts/phase1.md must carry the run-start banner "
            "directive for channel-installed Mode A agents (AGENTS.md "
            "is not in the install bundle).",
        )
        self.assertIn("=" * 80, text)
        self.assertIn("DO NOT reprint", text)


if __name__ == "__main__":
    unittest.main()
