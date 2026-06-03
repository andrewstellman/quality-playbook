"""v1.5.7 089y — channel artifact-hygiene tests.

Both the pip wheel + sdist AND the npm tarball must ship ONLY
Python source files (``*.py``) for the bundled tree; never the
platform/version-specific compiled artifacts (``__pycache__``,
``*.pyc``, ``*.pyo``) that Python writes when those modules are
imported at test/dev time. Pre-089y both channels were leaking
compiled cruft into published artifacts (no ``.npmignore``; the
``files`` allowlist swept in ``__pycache__``).

This file exercises both channels end-to-end:

- **Test 1: npm tarball (``@skipUnless(npm)``)** — stage the
  npm-tarball-shaped tree, intentionally inject a
  ``__pycache__/something.pyc`` into the staged
  ``_bundle/``, run ``npm pack --dry-run --json``, and assert
  the manifest contains NO entries matching ``__pycache__`` or
  ``*.pyc``.

- **Test 2: pip wheel (``@skipUnless(build + venv)``)** — run
  ``bin/build_channel_package.py`` (its
  ``stamp_channel_manifest_versions`` step is fine to fire);
  inject a ``__pycache__/something.pyc`` into the staged
  ``_bundle/``; build the wheel via ``python -m build``; unzip
  the wheel; assert no ``__pycache__``/``*.pyc`` inside.

- **Test 3: stage() purge** — call
  ``build_channel_package.stage()`` against a temp dest;
  inject ``__pycache__/x.pyc`` siblings; re-run
  ``stage(..., clean=False)``; assert the purge step removed
  the cruft. This is the structural test (always runs;
  no node/build deps).

**Mutation bite** (per ai_context/DEVELOPMENT_PROCESS.md):
- Remove the ``_purge_compiled_artifacts`` call from
  ``stage()`` → Test 3 fails (the injected ``.pyc`` survives).
- Delete ``.npmignore`` → Test 1 fails (``npm pack`` ships the
  injected ``__pycache__``).
- Delete ``[tool.setuptools.exclude-package-data]`` from
  pyproject.toml → Test 2 fails (the wheel ships the injected
  ``.pyc``).
Bites executed PASS → FAIL → PASS during 089y development.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bin import build_channel_package as bcp  # noqa: E402


def _npm_available() -> bool:
    if shutil.which("npm") is None:
        return False
    try:
        r = subprocess.run(["npm", "--version"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=20)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# v1.5.7 090d: centralized skip-clean checks. The in-process
# ``import build`` shape was insufficient — it returned True
# even when ``build`` was a namespace package missing
# ``__main__.py``, so ``python -m build`` failed and the test
# crashed instead of skipping. The new helper invokes
# ``sys.executable -m build --help`` to match what the test
# actually does.
from bin.tests._channel_test_helpers import (  # noqa: E402
    pip_channel_prereqs_ok as _pip_channel_prereqs_ok,
)

_NPM_OK = _npm_available()
_PIP_PREREQS_OK = _pip_channel_prereqs_ok()


class ChannelArtifactHygiene089yStructuralTests(unittest.TestCase):
    """Structural test for ``stage()``'s purge step. No external
    deps required."""

    def test_stage_purges_pycache_and_pyc(self) -> None:
        """Inject ``__pycache__`` + ``.pyc`` cruft into a staged
        bundle, re-run ``stage(..., clean=False)``, and assert
        they're purged. The clean=True path doesn't exercise the
        purge because rmtree wipes everything first; this test
        explicitly takes the incremental path."""
        with tempfile.TemporaryDirectory(prefix="qpb_089y_stage_") as tmp:
            dest = Path(tmp) / "_bundle"
            bcp.stage(REPO_ROOT, dest, clean=True)

            # Inject the cruft: a __pycache__ dir with a .pyc file +
            # a top-level .pyc.
            pycache = dest / "bin" / "__pycache__"
            pycache.mkdir(parents=True, exist_ok=True)
            (pycache / "install_skill.cpython-313.pyc").write_bytes(
                b"\x42\x42\xff\xff"  # nonsense bytes; just a marker
            )
            top_pyc = dest / "stray.pyc"
            top_pyc.write_bytes(b"\x42\x42\xff\xff")
            top_pyo = dest / "stray.pyo"
            top_pyo.write_bytes(b"\x42\x42\xff\xff")
            self.assertTrue(pycache.is_dir())
            self.assertTrue(top_pyc.is_file())
            self.assertTrue(top_pyo.is_file())

            # Re-run stage WITHOUT clean — the purge step at the end
            # should still wipe the cruft.
            bcp.stage(REPO_ROOT, dest, clean=False)

            self.assertFalse(
                pycache.exists(),
                f"089y: stage() must purge __pycache__/ from staged "
                f"tree; found at {pycache}",
            )
            self.assertFalse(
                top_pyc.exists(),
                f"089y: stage() must purge *.pyc; found {top_pyc}",
            )
            self.assertFalse(
                top_pyo.exists(),
                f"089y: stage() must purge *.pyo; found {top_pyo}",
            )

    def test_purge_helper_handles_missing_dest_gracefully(self) -> None:
        """``_purge_compiled_artifacts`` should be a no-op on a
        missing dest_dir (so the build doesn't crash before staging
        runs)."""
        nonexistent = Path("/tmp/qpb_089y_definitely_not_here_x9z")
        # Should not raise.
        bcp._purge_compiled_artifacts(nonexistent)


@unittest.skipUnless(
    _NPM_OK,
    "npm not available — skipping the npm tarball hygiene test (the "
    "node-dependent test SKIPs cleanly).",
)
class NpmTarballArtifactHygiene089yTests(unittest.TestCase):
    """npm tarball must not ship ``__pycache__`` or ``.pyc``."""

    def _stage_npm_tree(self, tmp_root: Path) -> None:
        """Stage the npm-tarball-shaped tree under ``tmp_root``."""
        for rel in ("package.json", "README.md", "LICENSE",
                    ".npmignore"):
            src = REPO_ROOT / rel
            if src.is_file():
                shutil.copy2(src, tmp_root / rel)
        (tmp_root / "bin").mkdir()
        shutil.copy2(
            REPO_ROOT / "bin" / "quality-playbook.js",
            tmp_root / "bin" / "quality-playbook.js",
        )
        (tmp_root / "quality_playbook_cli").mkdir()
        for name in ("__init__.py", "__main__.py"):
            shutil.copy2(
                REPO_ROOT / "quality_playbook_cli" / name,
                tmp_root / "quality_playbook_cli" / name,
            )
        bcp.stage(
            REPO_ROOT,
            tmp_root / "quality_playbook_cli" / "_bundle",
            clean=True,
        )

    def test_npm_pack_ships_no_pycache_or_pyc(self) -> None:
        """Inject ``__pycache__/foo.pyc`` into the staged tree,
        run ``npm pack --dry-run --json``, and assert the manifest
        contains NO entries matching ``__pycache__`` or ``.pyc``."""
        with tempfile.TemporaryDirectory(prefix="qpb_089y_npm_") as tmp:
            tmp_root = Path(tmp)
            self._stage_npm_tree(tmp_root)

            # Inject cruft so the .npmignore has something to filter.
            injected_pycache = (
                tmp_root / "quality_playbook_cli" / "_bundle" / "bin"
                / "__pycache__"
            )
            injected_pycache.mkdir(parents=True, exist_ok=True)
            (injected_pycache / "install_skill.cpython-313.pyc").write_bytes(
                b"\x42\x42"
            )
            stray = tmp_root / "quality_playbook_cli" / "stray.pyc"
            stray.write_bytes(b"\x42\x42")

            proc = subprocess.run(
                # --ignore-scripts skips the 090c prepack hook
            # (fixture pre-stages manually + injects cruft).
            ["npm", "pack", "--dry-run", "--json",
             "--ignore-scripts"],
                cwd=str(tmp_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
            self.assertEqual(
                proc.returncode, 0,
                f"npm pack --dry-run failed: stdout={proc.stdout!r} "
                f"stderr={proc.stderr!r}",
            )
            data = json.loads(proc.stdout.decode("utf-8"))
            files = data[0].get("files", [])
            names = {entry["path"] for entry in files}
            offenders = [n for n in names
                         if "__pycache__" in n
                         or n.endswith(".pyc")
                         or n.endswith(".pyo")]
            self.assertEqual(
                offenders, [],
                f"089y: npm pack manifest ships compiled-Python "
                f"cruft: {offenders!r}. .npmignore must exclude "
                f"__pycache__/*.pyc/*.pyo.",
            )


@unittest.skipUnless(
    _PIP_PREREQS_OK,
    "`build` package + working `python -m venv` required — skipping "
    "the pip wheel hygiene test.",
)
class PipWheelArtifactHygiene089yTests(unittest.TestCase):
    """pip wheel must not ship ``__pycache__`` or ``.pyc``."""

    def test_wheel_ships_no_pycache_or_pyc(self) -> None:
        """Stage the bundle, inject ``__pycache__/foo.pyc``,
        build the wheel, unzip, and assert no compiled cruft."""
        with tempfile.TemporaryDirectory(prefix="qpb_089y_wheel_") as tmp:
            tmp_path = Path(tmp)
            # Stage the bundle (this purges, but we'll re-inject
            # AFTER stage to test that the WHEEL excludes them).
            bundle_dest = REPO_ROOT / "quality_playbook_cli" / "_bundle"
            bcp.stage(REPO_ROOT, bundle_dest, clean=True)
            injected_pycache = bundle_dest / "bin" / "__pycache__"
            injected_pycache.mkdir(parents=True, exist_ok=True)
            (injected_pycache / "install_skill.cpython-313.pyc").write_bytes(
                b"\x42\x42"
            )
            try:
                # Build the wheel.
                dist_dir = tmp_path / "dist"
                r = subprocess.run(
                    [sys.executable, "-m", "build", "--wheel",
                     "--outdir", str(dist_dir), str(REPO_ROOT)],
                    capture_output=True, text=True, timeout=180,
                )
                self.assertEqual(
                    r.returncode, 0,
                    f"`python -m build` failed:\n{r.stdout}\n{r.stderr}",
                )
                wheels = list(dist_dir.glob("quality_playbook-*.whl"))
                self.assertGreater(
                    len(wheels), 0,
                    f"no wheel found in {dist_dir}",
                )
                wheel = wheels[0]
                # Inspect the wheel contents.
                with zipfile.ZipFile(wheel) as zf:
                    names = zf.namelist()
                offenders = [n for n in names
                             if "__pycache__" in n
                             or n.endswith(".pyc")
                             or n.endswith(".pyo")]
                self.assertEqual(
                    offenders, [],
                    f"089y: wheel {wheel.name} ships compiled-Python "
                    f"cruft: {offenders!r}. pyproject.toml's "
                    f"[tool.setuptools.exclude-package-data] must "
                    f"exclude these and "
                    f"`build_channel_package.stage()` must purge "
                    f"them at the source.",
                )
            finally:
                # Clean up the staged injection so subsequent test
                # runs (or 089u/089v e2e tests) start fresh.
                if injected_pycache.exists():
                    shutil.rmtree(injected_pycache, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
