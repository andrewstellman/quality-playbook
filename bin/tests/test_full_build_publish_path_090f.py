"""v1.5.7 090f — the standard publish build (`python -m build`,
NO `--wheel`) must produce a working wheel via the sdist→wheel
path.

The 2026-05-23 cold-clone publish smoke on macOS revealed:
running the standard publish invocation `python -m build`
(which builds the sdist, then builds the wheel FROM the
unpacked sdist) failed with::

    pyproject_hooks._impl.BackendUnavailable:
    Cannot find module '_qpb_build_backend' in [...]

Root cause: 090e's PEP517 backend (`_qpb_build_backend.py`,
declared via `backend-path = ["."]` in pyproject.toml) was
NOT included in the sdist, so when `build` unpacked the
sdist and tried to build the wheel, PEP517 couldn't load the
backend → no wheel was produced.

This was masked because all prior verification used
`python -m build --wheel`, which builds the wheel DIRECTLY
from the source tree (where the backend module IS at the
repo root). The standard sdist→wheel path was never
exercised.

090f closes the gap with TWO changes:

1. ``MANIFEST.in`` includes ``_qpb_build_backend.py`` (so the
   sdist ships the backend).
2. The backend is context-aware: source-tree builds run
   stage+stamp (preserves 090c cold-build safety); sdist-
   unpack builds (no root ``SKILL.md`` / ``bin/build_channel_
   package.py``) skip stage+stamp and delegate straight to
   setuptools (the unpacked tree already has a complete
   stamped bundle).

This test pins both fixes by running the EXACT
``python -m build`` (no flags) from the live clone, asserting
both artifacts are produced, AND pip-installing the wheel
into a fresh venv to confirm install + validate succeed.

**Mutation bites** (per ai_context/DEVELOPMENT_PROCESS.md):

- Drop ``MANIFEST.in`` (or remove its ``include
  _qpb_build_backend.py`` line) → the sdist no longer ships
  the backend → ``python -m build`` fails at the wheel step
  with BackendUnavailable → this test fires.
- Revert the ``_is_source_tree_build()`` guard in
  ``_qpb_build_backend.build_wheel`` (always run stage+stamp)
  → wheel-from-sdist crashes when ``_stage_bundle()`` /
  ``_stamp_version()`` can't find the dev machinery in the
  unpacked sdist → this test fires.

Both bites produce a clean FAIL at the build step — no
silent partial pass.
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


from bin.tests._channel_test_helpers import (  # noqa: E402
    pip_channel_prereqs_ok as _pip_channel_prereqs_ok,
)

_BUILD_OK = _pip_channel_prereqs_ok()


@unittest.skipUnless(
    _BUILD_OK,
    "`build` package + `python -m venv` required — skipping "
    "the full python -m build (sdist→wheel) publish-path test.",
)
class FullPythonMBuildProducesWorkingWheel090fTests(unittest.TestCase):
    """**The 090f regression pin.** Exercises the REAL publish
    invocation (``python -m build``, no flags) which builds
    sdist → unpacks → builds wheel from unpacked tree. This
    is the path ``twine upload`` / pipx / uvx all hit; using
    ``--wheel`` masks the entire wheel-from-sdist code path
    and is what let the 090f bug ship.

    Heavy test (~30-60s): builds sdist + wheel + creates a
    venv + pip-installs + runs the console scripts. Skips
    cleanly without the build / venv prerequisites."""

    @classmethod
    def setUpClass(cls) -> None:
        """Build both artifacts via the FULL `python -m build`
        once at class setup, pip-install the wheel into a
        venv, and reuse for all tests in this class."""
        cls._setup_error: str | None = None
        try:
            cls._build_dir = Path(tempfile.mkdtemp(prefix="qpb-090f-build-"))
            cls._venv_dir = Path(tempfile.mkdtemp(prefix="qpb-090f-venv-"))

            # Clear the live _bundle/ so we exercise the cold
            # source-tree path (the sdist's auto-stage step
            # populates _bundle/ inside the unpacked sdist,
            # not in the live clone, but clearing first
            # ensures we're not accidentally testing a stale
            # _bundle/).
            bundle = REPO_ROOT / "quality_playbook_cli" / "_bundle"
            if bundle.is_dir():
                shutil.rmtree(bundle)

            # THE LOAD-BEARING INVOCATION: `python -m build`
            # with NO `--wheel`. This forces the sdist → wheel
            # path that 090f fixes.
            r = subprocess.run(
                [sys.executable, "-m", "build",
                 "--outdir", str(cls._build_dir),
                 str(REPO_ROOT)],
                capture_output=True, text=True, timeout=600,
            )
            if r.returncode != 0:
                cls._setup_error = (
                    f"090f: full `python -m build` (sdist→wheel) "
                    f"failed (rc={r.returncode}). This is the "
                    f"regression class 090f closes; if this test "
                    f"is failing here, MANIFEST.in or the "
                    f"_qpb_build_backend context-awareness has "
                    f"been broken.\nstdout:\n{r.stdout}\nstderr:"
                    f"\n{r.stderr}"
                )
                return

            sdists = list(cls._build_dir.glob("*.tar.gz"))
            wheels = list(cls._build_dir.glob("*.whl"))
            cls._sdist = sdists[0] if sdists else None
            cls._wheel = wheels[0] if wheels else None
            if not cls._sdist or not cls._wheel:
                cls._setup_error = (
                    f"090f: `python -m build` succeeded but did "
                    f"not produce both .tar.gz AND .whl. dist "
                    f"contents: "
                    f"{sorted(p.name for p in cls._build_dir.iterdir())}"
                )
                return

            # Create the venv + install the wheel.
            r = subprocess.run(
                [sys.executable, "-m", "venv", str(cls._venv_dir)],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                cls._setup_error = (
                    f"venv create failed: rc={r.returncode}\n"
                    f"{r.stderr}"
                )
                return
            cls._venv_python = cls._venv_dir / "bin" / "python"
            cls._venv_qp = cls._venv_dir / "bin" / "quality-playbook"
            r = subprocess.run(
                [str(cls._venv_python), "-m", "pip", "install",
                 "--quiet", "--disable-pip-version-check",
                 str(cls._wheel)],
                capture_output=True, text=True, timeout=180,
            )
            if r.returncode != 0:
                cls._setup_error = (
                    f"pip install failed (rc={r.returncode}):\n"
                    f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
                )
                return
        except (OSError, subprocess.TimeoutExpired) as exc:
            cls._setup_error = f"setUpClass exception: {exc!r}"

    @classmethod
    def tearDownClass(cls) -> None:
        for d in (getattr(cls, "_venv_dir", None),
                  getattr(cls, "_build_dir", None)):
            if d is not None and d.is_dir():
                shutil.rmtree(d, ignore_errors=True)

    def _require_setup(self) -> None:
        if self._setup_error is not None:
            self.fail(self._setup_error)

    def test_both_sdist_and_wheel_are_produced(self) -> None:
        """The most direct regression pin: `python -m build`
        (no flags) MUST produce both artifacts. Pre-090f the
        wheel step crashed with BackendUnavailable so only
        the .tar.gz was in the outdir."""
        self._require_setup()
        self.assertIsNotNone(self._sdist, "no .tar.gz produced")
        self.assertIsNotNone(self._wheel, "no .whl produced")

    def test_wheel_contains_full_bundle(self) -> None:
        """The wheel built via the sdist→wheel path must
        contain the FULL `_bundle/` (the unpacked sdist had a
        complete, stamped bundle; the wheel step packaged
        it)."""
        self._require_setup()
        import zipfile
        with zipfile.ZipFile(self._wheel) as zf:
            names = zf.namelist()
        bundle = [n for n in names
                  if "quality_playbook_cli/_bundle/" in n]
        self.assertGreaterEqual(
            len(bundle), 50,
            f"090f: wheel from sdist→wheel path ships too few "
            f"_bundle/ files (got {len(bundle)} — expected "
            f"~54). The context-aware backend skipped stamp/"
            f"stage but the sdist's pre-staged bundle must "
            f"still be packaged.",
        )
        self.assertTrue(
            any("_bundle/bin/_purpose.py" in n for n in names),
            "090f: wheel from sdist→wheel path missing "
            "_purpose.py. The same ship-blocker class as 090b.",
        )

    def test_sdist_contains_backend_module(self) -> None:
        """`MANIFEST.in` must ship `_qpb_build_backend.py` in
        the sdist so PEP517 can load the backend when
        building the wheel from the unpacked sdist."""
        self._require_setup()
        import tarfile
        with tarfile.open(self._sdist) as tf:
            names = tf.getnames()
        self.assertTrue(
            any(n.endswith("/_qpb_build_backend.py") for n in names),
            f"090f: sdist must ship _qpb_build_backend.py for "
            f"PEP517 to load the backend when building the "
            f"wheel from the unpacked sdist. sdist contents: "
            f"{sorted(names)[:20]}",
        )

    def test_wheel_installs_and_validate_succeeds(self) -> None:
        """Install the produced wheel into a fresh venv, run
        `quality-playbook install` + `validate` from the
        installed console script, and assert both succeed.
        This is the full publish-path smoke."""
        self._require_setup()
        with tempfile.TemporaryDirectory(prefix="qpb-090f-target-") as t:
            target = Path(t)
            # Scaffold the target so validate has the canonical
            # layout.
            (target / ".gitignore").write_text(
                "# QPB scaffold\nquality/\n", encoding="utf-8",
            )
            (target / "reference_docs").mkdir(exist_ok=True)
            (target / "reference_docs" / "cite").mkdir(exist_ok=True)

            r_install = subprocess.run(
                [str(self._venv_qp), "install",
                 "--into", str(target),
                 "--ai-tool", "claude",
                 "--no-smoke"],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(
                r_install.returncode, 0,
                f"090f: `quality-playbook install` from the "
                f"wheel built via the sdist→wheel path must "
                f"exit 0. rc={r_install.returncode}\n"
                f"stdout:\n{r_install.stdout}\nstderr:\n"
                f"{r_install.stderr}",
            )
            self.assertIn(
                "event=install_complete", r_install.stdout,
                f"install must emit event=install_complete. "
                f"stdout:\n{r_install.stdout}",
            )
            self.assertIn(
                "status=success", r_install.stdout,
                f"install_complete must carry status=success. "
                f"stdout:\n{r_install.stdout}",
            )

            r_validate = subprocess.run(
                [str(self._venv_qp), "validate", str(target)],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(
                r_validate.returncode, 0,
                f"090f: `quality-playbook validate` from the "
                f"sdist→wheel-built wheel must exit 0. "
                f"rc={r_validate.returncode}\nstdout:\n"
                f"{r_validate.stdout}\nstderr:\n"
                f"{r_validate.stderr}",
            )
            self.assertIn(
                "status=ok", r_validate.stdout,
                f"validate must emit status=ok. stdout:\n"
                f"{r_validate.stdout}",
            )


if __name__ == "__main__":
    unittest.main()
