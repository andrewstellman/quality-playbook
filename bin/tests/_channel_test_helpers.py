"""v1.5.7 090d — shared skip-clean helpers for channel build tests.

The 2026-05-23 publish-safety cycle (090c) closed FIX-REQUIRED
with all tests green, but the tests' own skip-clean guards were
themselves env-dependent: an `import build` check returned True
even when the `build` package was a namespace lacking
``__main__.py`` (so ``python -m build`` failed with
``No module named build.__main__``). 090c's reviewer didn't
catch this because the reviewer's env had `build` properly
installed — the same "env-dependent green" blind spot behind
the whole channel saga.

090d closes the gap by:
1. Checking `python -m build --help` (the actual entry point
   the test will invoke), NOT `import build` (which can succeed
   on a partial install).
2. Using the SAME interpreter the test will use for the
   subprocess call (`sys.executable`).
3. Centralizing the check in this module so the three affected
   test files stay in lockstep.

Adopters / contributors without `build` installed now see
`skipped`, not `FAILED`. The build/pack tests still run-and-pass
in dev envs where the tools ARE available (i.e. the skip is
conditional, not unconditional).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def python_build_module_works() -> bool:
    """Return True iff ``sys.executable -m build --help`` exits 0.

    Pre-090d the channel build tests used ``import build`` to
    decide skip-vs-run. That check can succeed (the `build`
    package is importable as a namespace) even when
    ``python -m build`` fails because ``build/__main__.py`` is
    missing. The robust check invokes the actual entry point.

    Uses ``sys.executable`` because that's the SAME interpreter
    the tests invoke for the real subprocess call (`[sys.
    executable, "-m", "build", "--wheel", ...]`). If a future
    test changes to use a different interpreter, the check
    here must be updated to match.
    """
    try:
        r = subprocess.run(
            [sys.executable, "-m", "build", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def python_venv_works() -> bool:
    """Return True iff ``sys.executable -m venv`` can create a
    usable venv. (Stripped-down distros sometimes ship Python
    without the ensurepip / venv module.)"""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [sys.executable, "-m", "venv", "--without-pip",
                 str(Path(tmp) / "v")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def pip_channel_prereqs_ok() -> bool:
    """Combined check for the pip-channel build path:
    ``python -m build`` must be runnable AND ``python -m venv``
    must produce a working venv.

    Use as the skipUnless guard for any test that does
    ``python -m build --wheel/--sdist`` and ``pip install`` into
    a throwaway venv.
    """
    return python_build_module_works() and python_venv_works()


def node_npm_available() -> bool:
    """Return True iff both ``node --version`` and ``npm --version``
    are runnable. Use as the skipUnless guard for npm-channel
    tests that invoke ``npm pack`` / ``npx`` via subprocess."""
    if shutil.which("node") is None or shutil.which("npm") is None:
        return False
    try:
        r1 = subprocess.run(
            ["node", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
        r2 = subprocess.run(
            ["npm", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
        return r1.returncode == 0 and r2.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# Skip-message strings used by the @skipUnless decorators in the
# channel test files. Kept here so the three files emit
# IDENTICAL skip messages — easier for a CI log scrape to count
# them as one class of skip.
SKIP_PIP_PREREQS = (
    "pip channel build prereqs missing — `python -m build` and "
    "`python -m venv` must both be runnable against `sys.executable`. "
    "Install the `build` package (`pip install build`) to exercise "
    "this test path."
)

SKIP_NPM_PREREQS = (
    "npm channel prereqs missing — `node` + `npm` must both be on "
    "PATH and runnable. Install Node.js to exercise this test path."
)
