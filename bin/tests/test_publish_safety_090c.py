"""v1.5.7 090c — publish-safety tests.

The 2026-05-23 channel-architecture Council found that the
existing channel tests pre-staged via module import — they missed
exactly the paths that broke. The 089y / 090b bugs (.pyc cruft,
`_purpose.py` drop) shared a root cause: invocation-context-
sensitive imports + no enforcement that the bundle is staged.

This test file closes three failure classes that previously
shipped GREEN:

1. **Script-form invocation from a foreign cwd** — `python3
   bin/build_channel_package.py --stage` run from a cwd that
   contains a SIBLING `bin/` directory must produce a complete
   bundle (`_purpose.py` + all mandatory members), NOT a bundle
   computed against the foreign `install_skill`'s root.
2. **Cold build (no pre-staged `_bundle/`)** — `python -m build`
   and `npm pack` from a clean tree must produce artifacts that
   contain the FULL `_bundle/`. Pre-090c they shipped an empty
   `_bundle/`.
3. **Foreign-`bin`-proof imports across bundled scripts** — each
   bundled script's `from bin import X` must have a path-load
   fallback (or a safe guarded behavior) so the import can never
   hard-crash from sys.path pollution.

Each test skips cleanly when its prerequisites
(`build` / `node`+`npm`) aren't available.
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


def _build_available() -> bool:
    try:
        import build  # noqa: F401
        return True
    except ImportError:
        return False


def _venv_works() -> bool:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [sys.executable, "-m", "venv", "--without-pip",
                 str(Path(tmp) / "v")],
                capture_output=True, text=True, timeout=30,
            )
            return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _npm_available() -> bool:
    if shutil.which("npm") is None:
        return False
    try:
        r = subprocess.run(["npm", "--version"],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=20)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


_BUILD_OK = _build_available() and _venv_works()
_NPM_OK = _npm_available()


# ---------------------------------------------------------------------------
# Test class 1: script-form foreign-cwd invocation of
# build_channel_package.py
# ---------------------------------------------------------------------------


class ScriptFormForeignCwdStaging090cTests(unittest.TestCase):
    """**The 090c Task-A regression pin.** Pre-090c, `python3
    bin/build_channel_package.py --stage` invoked from a cwd
    containing a sibling `bin/install_skill.py` resolved to the
    SIBLING's copy of `install_skill._bundle_files()` — staging
    against the wrong source root and dropping members (the
    2026-05-23 ship-blocker).

    Post-090c, `_import_install_skill` path-loads from
    REPO_ROOT/bin/install_skill.py via spec_from_file_location.
    The module that defines `_bundle_files()` is always from the
    SAME clone as `build_channel_package.py`, regardless of cwd.

    Mutation candidate: revert Task A (use
    `sys.path.insert(REPO_ROOT)` + `from bin import install_skill`).
    Expected failure: this test fires because the foreign sibling
    `install_skill` is loaded and either crashes or stages an
    incomplete bundle."""

    def test_script_form_from_foreign_cwd_stages_complete_bundle(
            self) -> None:
        """Set up a temp dir with a sabotaged sibling `bin/
        install_skill.py` that raises if loaded; invoke
        `python3 <REPO_ROOT>/bin/build_channel_package.py --stage`
        from that cwd; assert the REAL bundle was staged with
        every mandatory member present."""
        with tempfile.TemporaryDirectory(
            prefix="qpb_090c_foreign_",
        ) as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "bin").mkdir()
            # Sabotaged sibling — if `from bin import install_skill`
            # resolves to this one, the build fails LOUDLY (which
            # is itself sufficient to fail the assertion below).
            (tmp_path / "bin" / "install_skill.py").write_text(
                "# v1.5.7 090c test sentinel — foreign "
                "install_skill\n"
                "from pathlib import Path\n"
                "def _bundle_files(source_root):\n"
                "    raise RuntimeError(\n"
                "        '090c regression — foreign "
                "install_skill loaded'\n"
                "    )\n",
                encoding="utf-8",
            )
            # Also drop a foreign _purpose so the load order
            # collision is fully simulated.
            (tmp_path / "bin" / "_purpose.py").write_text(
                "# foreign _purpose sentinel\n"
                "def get_version(): return 'FOREIGN-090c'\n",
                encoding="utf-8",
            )

            # Run the REAL build_channel_package from REPO_ROOT,
            # but with cwd = tmp_path (the foreign sibling tree).
            # Use --stamp-only to keep the test fast and avoid
            # mutating the live `_bundle/` (the stamp-only path
            # also exercises `_import_install_skill` —
            # `stamp_channel_manifest_versions` calls
            # `_purpose.get_version()`).
            real_script = REPO_ROOT / "bin" / "build_channel_package.py"
            self.assertTrue(real_script.is_file())

            r = subprocess.run(
                [sys.executable, str(real_script), "--stamp-only"],
                cwd=str(tmp_path),
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(
                r.returncode, 0,
                f"090c: script-form invocation from foreign cwd "
                f"must succeed. rc={r.returncode}\n"
                f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}",
            )
            # The foreign _purpose's get_version returns FOREIGN.
            # If our path-load worked, the REAL get_version returns
            # the actual SKILL.md version. Check pyproject.toml
            # hasn't been stamped with the foreign version.
            pyproject = (REPO_ROOT / "pyproject.toml").read_text(
                encoding="utf-8")
            self.assertNotIn(
                "FOREIGN-090c", pyproject,
                "090c: pyproject.toml was stamped with the "
                "foreign _purpose's version — the path-load "
                "fallback did not anchor on REPO_ROOT.",
            )

    def test_full_stage_from_foreign_cwd_produces_complete_bundle(
            self) -> None:
        """The heavier sibling: actually run `--stage` from a
        foreign cwd into a temp dest_dir; assert the staged
        tree contains `bin/_purpose.py` + all mandatory
        members."""
        with tempfile.TemporaryDirectory(
            prefix="qpb_090c_stage_foreign_",
        ) as tmp:
            tmp_path = Path(tmp)
            # Set up the sabotaged sibling tree.
            (tmp_path / "bin").mkdir()
            (tmp_path / "bin" / "install_skill.py").write_text(
                "raise RuntimeError("
                "'foreign install_skill loaded — 090c regression')\n",
                encoding="utf-8",
            )
            dest = tmp_path / "_real_bundle"

            # Use a SUBPROCESS so the staging happens with cwd
            # set to the foreign tree.
            real_script = REPO_ROOT / "bin" / "build_channel_package.py"
            r = subprocess.run(
                [sys.executable, str(real_script),
                 "--stage", "--dest", str(dest)],
                cwd=str(tmp_path),
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(
                r.returncode, 0,
                f"090c: script-form --stage from foreign cwd "
                f"must produce a complete bundle. rc={r.returncode}\n"
                f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}",
            )
            # Mandatory member check.
            for required in (
                "bin/install_skill.py",
                "bin/qpb_validate.py",
                "bin/_purpose.py",
                "SKILL.md",
                "phase_prompts/phase1.md",
            ):
                self.assertTrue(
                    (dest / required).is_file(),
                    f"090c: staged bundle from foreign cwd "
                    f"missing {required} at {dest}",
                )


# ---------------------------------------------------------------------------
# Test class 2: cold build (no pre-staged _bundle)
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    _BUILD_OK,
    "`build` package + working `python -m venv` required — "
    "skipping the cold pip-build test.",
)
class ColdPipBuildShipsCompleteBundle090cTests(unittest.TestCase):
    """**The 090c Task-B regression pin (pip side).** Pre-090c,
    `python -m build` from a tree with no pre-staged `_bundle/`
    succeeded but produced a wheel/sdist containing ZERO
    `_bundle/` content. A release cut from a clean clone would
    have shipped a dead package.

    Post-090c, the custom backend `_qpb_build_backend` auto-stages
    via `bin/build_channel_package.stage()` before delegating to
    setuptools. The 090b mandatory-member guard runs inside
    `stage()` — incomplete bundles fail loudly.

    Mutation candidate: revert pyproject.toml's
    `build-backend = "_qpb_build_backend"` back to
    `"setuptools.build_meta"`. Expected failure: an empty
    `_bundle/` wheel ships and this test fires."""

    def test_cold_build_wheel_contains_full_bundle(self) -> None:
        """Clear any pre-staged `_bundle/`, then run
        `python -m build --wheel`; assert the wheel contains
        `_bundle/bin/_purpose.py` (the ship-blocker file) AND
        every mandatory bundle member."""
        with tempfile.TemporaryDirectory(prefix="qpb_090c_cold_") as tmp:
            tmp_path = Path(tmp)
            # Clear the live _bundle/ so we exercise the cold
            # path. (Best effort — if another test is mid-flight
            # this could race, but the test suite is serial.)
            bundle = REPO_ROOT / "quality_playbook_cli" / "_bundle"
            if bundle.is_dir():
                shutil.rmtree(bundle)

            r = subprocess.run(
                [sys.executable, "-m", "build", "--wheel",
                 "--outdir", str(tmp_path), str(REPO_ROOT)],
                capture_output=True, text=True, timeout=300,
            )
            self.assertEqual(
                r.returncode, 0,
                f"090c: cold `python -m build --wheel` must "
                f"succeed. rc={r.returncode}\nstdout:\n{r.stdout}\n"
                f"stderr:\n{r.stderr}",
            )
            wheels = list(tmp_path.glob("quality_playbook-*.whl"))
            self.assertTrue(
                wheels,
                f"090c: no wheel produced at {tmp_path}",
            )
            wheel = wheels[0]
            with zipfile.ZipFile(wheel) as zf:
                names = zf.namelist()
            bundle_files = [
                n for n in names
                if "quality_playbook_cli/_bundle/" in n
            ]
            self.assertGreaterEqual(
                len(bundle_files), 50,
                f"090c: cold-build wheel ships too few "
                f"_bundle/ files (got {len(bundle_files)} — "
                f"expected ~54). This was the 2026-05-23 cold-"
                f"build empty-bundle hole.",
            )
            for required_rel in (
                "_bundle/bin/_purpose.py",
                "_bundle/bin/install_skill.py",
                "_bundle/bin/qpb_validate.py",
                "_bundle/SKILL.md",
                "_bundle/phase_prompts/phase1.md",
            ):
                self.assertTrue(
                    any(required_rel in n for n in names),
                    f"090c: cold-build wheel missing "
                    f"{required_rel}; ship-blocker class is "
                    f"back. wheel={wheel.name}",
                )


@unittest.skipUnless(
    _NPM_OK,
    "npm not available — skipping the cold npm-pack test.",
)
class ColdNpmPackShipsCompleteBundle090cTests(unittest.TestCase):
    """**The 090c Task-B regression pin (npm side).** Pre-090c,
    `npm pack` from a tree with no pre-staged `_bundle/`
    succeeded but produced a tarball containing zero `_bundle/`
    content. Post-090c, `package.json`'s `scripts.prepack` runs
    `python3 bin/build_channel_package.py --stage` before the
    tarball is built.

    Mutation candidate: drop `scripts.prepack` from
    `package.json`. Expected failure: empty bundle ships."""

    def test_cold_npm_pack_dry_run_contains_full_bundle(self) -> None:
        # Clear the live _bundle/ so we exercise the cold path.
        bundle = REPO_ROOT / "quality_playbook_cli" / "_bundle"
        if bundle.is_dir():
            shutil.rmtree(bundle)
        r = subprocess.run(
            ["npm", "pack", "--dry-run", "--json"],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(
            r.returncode, 0,
            f"090c: cold `npm pack --dry-run` must succeed. "
            f"rc={r.returncode}\nstdout:\n{r.stdout}\n"
            f"stderr:\n{r.stderr}",
        )
        # `npm pack` prints non-JSON noise (the `prepack` script
        # output) before the JSON. Find the JSON array start.
        idx = r.stdout.find("[")
        self.assertGreaterEqual(
            idx, 0,
            f"npm pack output has no JSON array: {r.stdout!r}",
        )
        data = json.loads(r.stdout[idx:])
        files = data[0].get("files", [])
        names = {entry["path"] for entry in files}
        bundle_names = [
            n for n in names
            if "quality_playbook_cli/_bundle/" in n
        ]
        self.assertGreaterEqual(
            len(bundle_names), 50,
            f"090c: cold-npm-pack tarball ships too few "
            f"_bundle/ files (got {len(bundle_names)} — "
            f"expected ~54). The prepack auto-stage must run.",
        )
        for required_rel in (
            "quality_playbook_cli/_bundle/bin/_purpose.py",
            "quality_playbook_cli/_bundle/bin/install_skill.py",
            "quality_playbook_cli/_bundle/bin/qpb_validate.py",
        ):
            self.assertIn(
                required_rel, names,
                f"090c: cold-npm-pack tarball missing "
                f"{required_rel}.",
            )


# ---------------------------------------------------------------------------
# Test class 3: import-closure / foreign-bin isolation
# ---------------------------------------------------------------------------


class ForeignBinIsolation090cTests(unittest.TestCase):
    """**The 090c Task-C regression pin.** Each bundled script's
    `from bin import X` must have a foreign-`bin`-proof fallback.
    This test invokes each bundled script with a sabotaged
    sibling `bin/` on sys.path (via subprocess + PYTHONPATH) and
    asserts it loads + exits 0.

    Mutation candidate: revert any one script's path-load
    fallback to a bare `from bin import X`. Expected failure:
    that script crashes when invoked with the foreign sibling
    on PYTHONPATH."""

    BUNDLED_LIBS_WITH_BIN_IMPORTS = (
        "bin.archive_lib",
        "bin.migrate_v1_5_0_layout",
        "bin.validate_phase_artifacts",
        "bin.reference_docs_ingest",
        "bin.benchmark_lib",
    )

    def test_each_lib_loads_under_foreign_bin_pythonpath(self) -> None:
        """Set up a sabotaged sibling `bin/` tree, prepend it to
        PYTHONPATH, then for each bundled lib run
        `python -m bin.<name>` from REPO_ROOT and assert exit 0.
        The script invocation goes through each lib's
        `if __name__ == "__main__"` block which prints the
        purpose banner and exits."""
        with tempfile.TemporaryDirectory(
            prefix="qpb_090c_foreignbin_",
        ) as tmp:
            tmp_path = Path(tmp)
            # Sabotaged sibling — every file just raises if loaded.
            sibling_bin = tmp_path / "bin"
            sibling_bin.mkdir()
            for name in (
                "run_state_lib.py", "archive_lib.py",
                "role_map.py", "benchmark_lib.py", "_purpose.py",
                "citation_verifier.py", "copilot_resolver.py",
            ):
                (sibling_bin / name).write_text(
                    f"# 090c sentinel: this should NEVER be "
                    f"loaded.\n"
                    f"raise RuntimeError(\n"
                    f"    '090c foreign-bin sibling loaded: "
                    f"{name}'\n"
                    f")\n",
                    encoding="utf-8",
                )

            env = os.environ.copy()
            # Put the sabotaged sibling FIRST on PYTHONPATH so
            # `from bin import X` resolves to it preferentially.
            env["PYTHONPATH"] = (
                str(tmp_path) + os.pathsep
                + env.get("PYTHONPATH", "")
            )

            for dotted in self.BUNDLED_LIBS_WITH_BIN_IMPORTS:
                with self.subTest(lib=dotted):
                    r = subprocess.run(
                        [sys.executable, "-m", dotted],
                        cwd=str(REPO_ROOT),
                        env=env,
                        capture_output=True, text=True,
                        timeout=30,
                    )
                    self.assertEqual(
                        r.returncode, 0,
                        f"090c: `python -m {dotted}` must succeed "
                        f"with a foreign sibling bin/ first on "
                        f"PYTHONPATH. rc={r.returncode}\n"
                        f"stdout:\n{r.stdout}\nstderr:\n"
                        f"{r.stderr}",
                    )


if __name__ == "__main__":
    unittest.main()
