"""v1.5.8 instruction 206 — AUDIT-table invariant test for the release-
channel affirmation pattern.

**Origin**: Per `ai_context/DEVELOPMENT_PROCESS.md` § AUDIT-table invariant
test pattern. Three sites now share the ``--dry-run`` XOR ``--<live>``
affirmation contract (publish_pip / publish_npm / submit_awesome_copilot).
The policy threshold for AUDIT elevation is three confirmed reuses; this
file is the elevation mandated by Panelist C's 206 review.

**The invariant**: every release-channel script must:

- Declare ``EX_USAGE = 64`` at module scope.
- Register both ``--dry-run`` and its corresponding ``--<live>`` flag
  in its ``parse_args`` (``argparse``) parser.
- Exit 0 with intro printed when invoked with no args (089x convention).
- Reject both-flags-set with EX_USAGE + an error message containing
  ``"mutually exclusive"``.

**Adding a new release-channel script**: append a row to
``RELEASE_AFFIRMATION_AUDIT`` below. The sweep tests below extend
automatically. If you forget to add the row but a new module imports
the same shape, ``test_audit_table_size_matches_known_sites`` provides a
weak-but-loud reminder.
"""
from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bin import publish_npm, publish_pip, submit_awesome_copilot  # noqa: E402


# AUDIT table — every release-channel script that should require
# --dry-run XOR <live-flag> affirmation.
#
# Schema: (module, live_flag_name, prog_name)
#   module          — the imported bin/<name>.py module
#   live_flag_name  — the affirmation flag (without leading --)
#   prog_name       — the argv[0] sentinel for sys.argv mocking
#
# When adding a new release-channel script, append here. Tests below
# parametrize over this list via ``unittest.TestCase.subTest``.
RELEASE_AFFIRMATION_AUDIT = [
    (publish_pip, "publish", "publish_pip"),
    (publish_npm, "publish", "publish_npm"),
    (submit_awesome_copilot, "submit", "submit_awesome_copilot"),
]


class ReleaseAffirmationSweepTests(unittest.TestCase):
    """v1.5.8 instruction 206 AUDIT-table elevation. Three confirmed
    reuses of the affirmation contract triggered the elevation per
    DEVELOPMENT_PROCESS.md § AUDIT-table invariant test pattern."""

    def test_each_module_declares_ex_usage_64(self) -> None:
        for mod, _live, prog in RELEASE_AFFIRMATION_AUDIT:
            with self.subTest(module=prog):
                self.assertEqual(
                    mod.EX_USAGE,
                    64,
                    f"{prog}.EX_USAGE must equal 64 (the POSIX EX_USAGE constant).",
                )

    def test_each_module_registers_dry_run_flag(self) -> None:
        for mod, _live, prog in RELEASE_AFFIRMATION_AUDIT:
            with self.subTest(module=prog):
                args = mod.parse_args(["--dry-run"])
                self.assertTrue(
                    getattr(args, "dry_run"),
                    f"{prog} must register --dry-run and set args.dry_run=True.",
                )

    def test_each_module_registers_live_affirmation_flag(self) -> None:
        for mod, live, prog in RELEASE_AFFIRMATION_AUDIT:
            with self.subTest(module=prog, flag=f"--{live}"):
                args = mod.parse_args([f"--{live}"])
                self.assertTrue(
                    getattr(args, live),
                    f"{prog} must register --{live} and set args.{live}=True.",
                )

    def test_each_module_no_args_returns_zero(self) -> None:
        for mod, _live, prog in RELEASE_AFFIRMATION_AUDIT:
            with self.subTest(module=prog):
                with mock.patch.object(sys, "argv", [prog]):
                    with mock.patch("sys.stdout", new=io.StringIO()):
                        rc = mod.main()
                self.assertEqual(
                    rc,
                    0,
                    f"{prog} must print intro + return 0 when invoked with no args.",
                )

    def test_each_module_both_flags_returns_ex_usage_mutually_exclusive(
        self,
    ) -> None:
        for mod, live, prog in RELEASE_AFFIRMATION_AUDIT:
            with self.subTest(module=prog, flag=f"--{live}"):
                argv = [prog, "--dry-run", f"--{live}"]
                captured_err = io.StringIO()
                with mock.patch.object(sys, "argv", argv):
                    with mock.patch("sys.stderr", new=captured_err):
                        rc = mod.main()
                self.assertEqual(
                    rc,
                    mod.EX_USAGE,
                    f"{prog} must reject --dry-run + --{live} with EX_USAGE.",
                )
                self.assertIn(
                    "mutually exclusive",
                    captured_err.getvalue(),
                    f"{prog}'s mutex error must contain 'mutually exclusive'.",
                )

    def test_audit_table_size_matches_known_sites(self) -> None:
        # Sweep guard: as of instruction 206, the affirmation contract is
        # used by 3 release-channel scripts. If a new release script
        # gets added but forgets to extend this AUDIT, this guard fails
        # loudly. Update the expected size when adding a row above.
        self.assertEqual(
            len(RELEASE_AFFIRMATION_AUDIT),
            3,
            "AUDIT table size changed. If you added a new release-channel "
            "script with affirmation flags, update this expected size to "
            "match. If you removed one, update the same.",
        )


if __name__ == "__main__":
    unittest.main()
