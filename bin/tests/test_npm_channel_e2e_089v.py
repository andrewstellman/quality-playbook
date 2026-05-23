"""v1.5.7 089v — end-to-end npm-channel install tests.

These tests stage the npm-tarball-shaped tree directly (no actual
``npm publish`` / ``npm install`` needed) and run the Node shim
against it, then assert:

1. **End-to-end install** — ``node <shim> init --loop=claude
   --no-smoke`` writes the skill bundle into a tempdir's
   ``.claude/skills/quality-playbook/`` and exits 0; the installed
   closure has the expected load-bearing files (SKILL.md +
   quality_gate.py).

2. **Validate after install** — ``node <shim> validate <target>``
   routes through ``quality_playbook_cli`` → bundled
   ``qpb_validate.py`` and emits ``event=`` lines on stdout. This
   pins the npx remediation string ``npx quality-playbook
   validate <target>`` is a real runnable command at the
   adopter's machine.

The staged tree layout mirrors what ``npm pack`` produces:

    <staged-root>/
      bin/quality-playbook.js
      package.json
      quality_playbook_cli/
        __init__.py
        __main__.py
        _bundle/                  (← from build_channel_package.stage())
          SKILL.md
          .github/skills/quality_gate/quality_gate.py
          bin/install_skill.py
          bin/qpb_validate.py
          …

That's the same shape ``npm pack --dry-run`` enumerates (pinned
by ``test_npm_channel_package_parity_089v.py``). Skipping the
actual ``npm install`` step saves ~20-60s per test without
sacrificing coverage of the v1.5.7 single-routing-brain
contract — the Node shim, Python shim, and Python entries are
all exercised end-to-end.

All tests ``@skipUnless(node)``. The pip-channel wheel build
(089u) and these npm staging tests share the bundle-staging step
(``build_channel_package.stage()``); when both run in the same
test session the staging is idempotent (clean=True wipes any
prior staged copy).

**Mutation-bite evidence**:
- Replace ``stdio: 'inherit'`` in the shim with ``stdio: 'pipe'``
  (drop forwarding) -> the validate test's ``event=`` line
  assertion fails (captured stdout is empty). Restore.
- Delete the ``--into <cwd>`` injection in ``translateArgv`` ->
  the install test fails because install_skill aborts on no
  target. Restore.

Bites executed PASS -> FAIL -> PASS during 089v development.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SHIM_PATH = REPO_ROOT / "bin" / "quality-playbook.js"

_NODE = shutil.which("node")


def _node_available() -> bool:
    if _NODE is None:
        return False
    try:
        proc = subprocess.run(
            [_NODE, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


_NODE_OK = _node_available()


@unittest.skipUnless(
    _NODE_OK,
    "node not available — skipping npm-channel e2e (instruction "
    "halt condition: node-dependent tests SKIP, not FAIL).",
)
class NpmChannelE2E089vTests(unittest.TestCase):
    """Stage the npm tarball tree once + run the shim against a
    tempdir target."""

    _staged: Path | None = None
    _setup_error: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        """Stage the npm-shaped tree in a temp dir. Errors are
        captured into ``_setup_error`` so individual tests fail
        cleanly with the diagnostic."""
        try:
            cls._staged = Path(tempfile.mkdtemp(prefix="qpb-089v-npm-e2e-"))
            staged = cls._staged
            # Mirror the npm tarball layout: package.json + bin/ +
            # quality_playbook_cli/{__init__,__main__}.py +
            # quality_playbook_cli/_bundle/…
            shutil.copy2(
                REPO_ROOT / "package.json", staged / "package.json",
            )
            (staged / "bin").mkdir()
            shutil.copy2(
                REPO_ROOT / "bin" / "quality-playbook.js",
                staged / "bin" / "quality-playbook.js",
            )
            (staged / "quality_playbook_cli").mkdir()
            for name in ("__init__.py", "__main__.py"):
                shutil.copy2(
                    REPO_ROOT / "quality_playbook_cli" / name,
                    staged / "quality_playbook_cli" / name,
                )
            from bin import build_channel_package
            build_channel_package.stage(
                REPO_ROOT,
                staged / "quality_playbook_cli" / "_bundle",
                clean=True,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            cls._setup_error = f"setUpClass exception: {exc!r}"

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._staged is not None and cls._staged.is_dir():
            shutil.rmtree(cls._staged, ignore_errors=True)

    def _require_setup(self) -> None:
        if self._setup_error is not None:
            self.fail(self._setup_error)

    def _shim_argv(self):
        return [_NODE, str(self._staged / "bin" / "quality-playbook.js")]

    def test_npx_install_into_tempdir(self) -> None:
        """``node <shim> init --loop=claude --no-smoke`` against a
        cwd of <tempdir> produces a .claude/skills/quality-
        playbook/ install closure inside that tempdir."""
        self._require_setup()
        with tempfile.TemporaryDirectory(prefix="qpb-089v-target-") as target:
            target_path = Path(target)
            # Run the shim with cwd = target_path so the
            # translated --into resolves to the tempdir.
            proc = subprocess.run(
                self._shim_argv() + [
                    "init", "--loop=claude", "--no-smoke",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(target_path),
                env=os.environ.copy(),
                timeout=120,
            )
            self.assertEqual(
                proc.returncode, 0,
                f"089v e2e: shim install must succeed against "
                f"target {target_path}. rc={proc.returncode}; "
                f"stdout:\n{proc.stdout.decode('utf-8', 'replace')}\n"
                f"stderr:\n{proc.stderr.decode('utf-8', 'replace')}",
            )
            install_root = target_path / ".claude" / "skills" / "quality-playbook"
            self.assertTrue(
                install_root.is_dir(),
                f"089v e2e: install root {install_root} does not "
                f"exist after `node shim init --loop=claude`.",
            )
            # Sanity-check load-bearing files.
            for required in ("SKILL.md", "quality_gate.py"):
                self.assertTrue(
                    (install_root / required).is_file(),
                    f"089v e2e: installed closure missing "
                    f"{required} at {install_root}",
                )

    def test_npx_validate_after_install_emits_events(self) -> None:
        """``node <shim> validate <target>`` (after an install)
        routes through quality_playbook_cli -> qpb_validate.py and
        emits ``event=`` lines on stdout. This pins the npx
        remediation string is a real runnable command."""
        self._require_setup()
        with tempfile.TemporaryDirectory(prefix="qpb-089v-vtarget-") as target:
            target_path = Path(target)
            # Install first.
            r_install = subprocess.run(
                self._shim_argv() + [
                    "init", "--loop=claude", "--no-smoke",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(target_path),
                env=os.environ.copy(),
                timeout=120,
            )
            self.assertEqual(
                r_install.returncode, 0,
                f"089v e2e: install must succeed before validate. "
                f"rc={r_install.returncode}; stderr:\n"
                f"{r_install.stderr.decode('utf-8', 'replace')}",
            )
            # Now validate against the same target.
            r_validate = subprocess.run(
                self._shim_argv() + ["validate", str(target_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(),
                timeout=120,
            )
            stdout = r_validate.stdout.decode("utf-8", "replace")
            self.assertIn(
                "event=", stdout,
                f"089v e2e: `node <shim> validate` must route to "
                f"qpb_validate.py and emit event= lines on stdout. "
                f"rc={r_validate.returncode}; stdout:\n{stdout}\n"
                f"stderr:\n"
                f"{r_validate.stderr.decode('utf-8', 'replace')}",
            )


if __name__ == "__main__":
    unittest.main()
