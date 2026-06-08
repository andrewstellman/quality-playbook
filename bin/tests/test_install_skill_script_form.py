"""v1.5.7 instruction 077 (addendum r3 §5.2 / acceptance #4) —
entry-point scripts must work in script-path form from any cwd.

The launch prompts + validator remediation suggestions use
script-path form (`python <root>/bin/<script>.py …`), never the
`-m bin.<script>` module form (cwd-dependent, the root cause of the
073/074 install-path failures). This test subprocess-invokes each
adopter-facing entry point's `--help` from a foreign temp cwd and
asserts exit 0 — the cwd-independence guarantee §5.2 promises.

`bin/quality_playbook.py` is the load-bearing case: before the §5.2
bootstrap it exited 1 from a foreign cwd with
`ModuleNotFoundError: No module named 'bin'` raised in the
transitively-imported migrate_v1_5_0_layout.py.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_QPB_ROOT = Path(__file__).resolve().parents[2]
# v1.5.8 instruction 208: bundled scripts moved to
# skills/quality-playbook/scripts/. classify_project.py stays at the
# legacy bin/ location (it's not bundled with the skill).
_BIN_NESTED = _QPB_ROOT / "skills" / "quality-playbook" / "scripts"
_BIN_LEGACY = _QPB_ROOT / "bin"


def _resolve_script(script: str) -> Path:
    nested = _BIN_NESTED / script
    if nested.is_file():
        return nested
    return _BIN_LEGACY / script


class _BinResolver:
    def __truediv__(self, script: str) -> Path:
        return _resolve_script(script)


_BIN = _BinResolver()

# install_skill (the installer itself, launch-prompt invoked) + the
# five §5.2 "Audit and apply if missing" entry points.
_SCRIPTS = (
    "install_skill.py",
    "validate_phase_artifacts.py",
    "reference_docs_ingest.py",
    "quality_playbook.py",
    "classify_project.py",
    "qpb_config.py",
)


class ScriptFormInvocationTests(unittest.TestCase):

    def test_all_entry_points_help_exit0_from_foreign_cwd(self) -> None:
        """`python <clone>/bin/<script>.py --help` exits 0 from a
        directory that is NOT the QPB clone.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-077 —
        BITE EXECUTED during instruction-077 development:
          Mutation: delete the
          `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
          §5.2 bootstrap line from bin/quality_playbook.py.
          Observed failure (purged __pycache__ first):
            FAIL: test_all_entry_points_help_exit0_from_foreign_cwd
            (script='quality_playbook.py')
            AssertionError: 1 != 0 : quality_playbook.py --help from
            foreign cwd exited 1 ; stderr contained
            'File ".../bin/migrate_v1_5_0_layout.py", line 53, in
            <module> from bin import archive_lib' ->
            ModuleNotFoundError: No module named 'bin'
          Restoration: bootstrap line restored; exit 0; test PASS.
        """
        with TemporaryDirectory() as td:
            for script in _SCRIPTS:
                with self.subTest(script=script):
                    proc = subprocess.run(
                        [sys.executable, str(_BIN / script), "--help"],
                        cwd=td, capture_output=True, text=True)
                    self.assertEqual(
                        proc.returncode, 0,
                        f"{script} --help from foreign cwd exited "
                        f"{proc.returncode}\nstdout:{proc.stdout}\n"
                        f"stderr:{proc.stderr}")
                    self.assertTrue(
                        proc.stdout.strip(),
                        f"{script} --help produced no stdout")

    def test_validator_help_exit0_from_foreign_cwd(self) -> None:
        """The Phase 0 validator itself is launch-prompt invoked in
        script-path form; it too must work from any cwd."""
        with TemporaryDirectory() as td:
            proc = subprocess.run(
                [sys.executable, str(_BIN / "qpb_validate.py"), "--help"],
                cwd=td, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0,
                             proc.stdout + proc.stderr)
            self.assertIn("qpb_validate", proc.stdout)


if __name__ == "__main__":
    unittest.main()
