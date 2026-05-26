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


# v1.5.7 090d: use the centralized skip-clean helper.
# Previously the `import build` shape returned True even when
# `build/__main__.py` was missing, so `python -m build` crashed
# and the test reported FAIL instead of skipped.
from bin.tests._channel_test_helpers import (  # noqa: E402
    pip_channel_prereqs_ok as _pip_channel_prereqs_ok,
    node_npm_available as _node_npm_available,
)

_BUILD_OK = _pip_channel_prereqs_ok()
_NPM_OK = _node_npm_available()


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
                "bin/qpb_phase.py",  # v1.5.7 109
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
                "_bundle/bin/qpb_phase.py",  # v1.5.7 109
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
        # v1.5.7 090e T4: deterministic JSON extraction. `npm pack
        # --json` prints non-JSON `prepack` script output BEFORE
        # the JSON array (e.g. the 090c auto-stage emits
        # `build_channel_package: staged 54 files...` first). The
        # pre-090e parser used `stdout.find("[")` which is brittle
        # — if `prepack` output ever contains a `[` character
        # (e.g. a bracketed log prefix), the slice starts at the
        # wrong byte. The robust form: find the first LINE that
        # starts with `[` (the JSON array opener at column 0).
        # That can never collide with prepack chatter (which
        # never starts a line with bare `[`).
        json_lines = r.stdout.splitlines(keepends=True)
        json_start_idx = None
        for i, line in enumerate(json_lines):
            if line.lstrip().startswith("["):
                json_start_idx = i
                break
        self.assertIsNotNone(
            json_start_idx,
            f"090e: npm pack output has no line starting with "
            f"`[` (JSON array). stdout:\n{r.stdout}",
        )
        data = json.loads("".join(json_lines[json_start_idx:]))
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
            "quality_playbook_cli/_bundle/bin/qpb_phase.py",
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


# ---------------------------------------------------------------------------
# Test class 4 (090e T5): backend version stamping
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    _BUILD_OK,
    "`build` package + working `python -m venv` required — "
    "skipping the backend version-stamping test.",
)
class BackendStampsSkillMdVersion090eTests(unittest.TestCase):
    """v1.5.7 090e T5: `_qpb_build_backend` must stamp the
    SKILL.md version into pyproject.toml + package.json BEFORE
    setuptools builds the wheel, so a cold `python -m build`
    after a SKILL.md version bump produces a correctly-
    versioned artifact (no need to run the stamper CLI
    separately).

    Pre-090e the backend only staged the bundle; the version
    stamper lived in the CLI. A bare `python -m build` after a
    SKILL.md bump (the blessed release path post-090c) would
    therefore ship a stale version.

    Mutation candidate: revert the `_stamp_version()` call in
    `_qpb_build_backend.build_wheel` / `build_sdist`. Expected
    failure: this test fires because the wheel's METADATA
    Version field shows the stale pyproject value instead of
    the (simulated) SKILL.md value."""

    def test_cold_build_stamps_skill_md_version(self) -> None:
        """Temporarily set SKILL.md frontmatter to a different
        version, run cold `python -m build --wheel`, unzip the
        wheel and confirm METADATA shows the SKILL.md version,
        not the pre-stamp pyproject value. Restores SKILL.md
        + pyproject.toml + package.json on teardown.
        """
        skill_md = REPO_ROOT / "SKILL.md"
        pyproject = REPO_ROOT / "pyproject.toml"
        package_json = REPO_ROOT / "package.json"
        skill_backup = skill_md.read_text(encoding="utf-8")
        pyproject_backup = pyproject.read_text(encoding="utf-8")
        package_json_backup = package_json.read_text(encoding="utf-8")
        # Also back up the staged bundle dir state so a clean
        # _bundle (which the cold-build will produce) doesn't
        # corrupt the working tree post-test.
        bundle = REPO_ROOT / "quality_playbook_cli" / "_bundle"
        try:
            # Rewrite SKILL.md frontmatter's version line to a
            # synthetic value that wouldn't match by accident.
            # PEP440-valid synthetic version (no hyphens; the
            # build backend's pyproject.toml validator
            # enforces PEP440). 9999 is implausible as a real
            # release version, so the test's pin doesn't
            # accidentally match a future bump.
            synthetic_version = "9999.0.0"
            # SKILL.md's version: line is INDENTED under
            # `metadata:` ("  version: 1.5.7"); the regex must
            # allow leading whitespace to match it.
            new_skill = re.sub(
                r"^(\s*version:\s*).*$",
                rf"\g<1>{synthetic_version}",
                skill_backup, count=1, flags=re.MULTILINE,
            )
            self.assertNotEqual(
                new_skill, skill_backup,
                "Could not find a `version:` frontmatter line "
                "in SKILL.md to rewrite for the test fixture.",
            )
            skill_md.write_text(new_skill, encoding="utf-8")

            # Clear _bundle to exercise the cold path.
            if bundle.is_dir():
                shutil.rmtree(bundle)

            with tempfile.TemporaryDirectory(
                prefix="qpb_090e_stamp_",
            ) as tmp:
                tmp_path = Path(tmp)
                r = subprocess.run(
                    [sys.executable, "-m", "build", "--wheel",
                     "--outdir", str(tmp_path), str(REPO_ROOT)],
                    capture_output=True, text=True, timeout=300,
                )
                self.assertEqual(
                    r.returncode, 0,
                    f"090e: cold `python -m build` (synthetic "
                    f"SKILL.md version) must succeed. rc="
                    f"{r.returncode}\nstdout:\n{r.stdout}\n"
                    f"stderr:\n{r.stderr}",
                )
                wheels = list(
                    tmp_path.glob(
                        f"quality_playbook-{synthetic_version}*.whl"
                    )
                )
                self.assertTrue(
                    wheels,
                    f"090e: expected wheel named "
                    f"quality_playbook-{synthetic_version}-*.whl "
                    f"(SKILL.md version stamped into "
                    f"pyproject.toml). Got: "
                    f"{[p.name for p in tmp_path.iterdir()]}",
                )
                wheel = wheels[0]
                with zipfile.ZipFile(wheel) as zf:
                    metadata_names = [
                        n for n in zf.namelist()
                        if n.endswith(".dist-info/METADATA")
                    ]
                    self.assertEqual(len(metadata_names), 1)
                    metadata = zf.read(metadata_names[0]).decode(
                        "utf-8")
                self.assertIn(
                    f"Version: {synthetic_version}", metadata,
                    f"090e: wheel METADATA must carry the "
                    f"SKILL.md-stamped version ({synthetic_version}), "
                    f"not the pre-stamp pyproject value. "
                    f"METADATA excerpt:\n{metadata[:500]}",
                )
        finally:
            skill_md.write_text(skill_backup, encoding="utf-8")
            pyproject.write_text(pyproject_backup, encoding="utf-8")
            package_json.write_text(
                package_json_backup, encoding="utf-8")
            # Re-stage the _bundle so the next test that needs
            # it has a fresh copy.
            from bin import build_channel_package as bcp
            bcp.stage(REPO_ROOT, bundle, clean=True)


import re  # noqa: E402 — late import used only by the 090e test


# ---------------------------------------------------------------------------
# v1.5.7 091 — harness bundle-safety tests
# ---------------------------------------------------------------------------
#
# These two tests RUN IN THE RELEASE GATE (NOT segregated like the
# harness functionality suite under ``bin/tests/harness/``). Per
# ``QPB_Test_Harness_1.5.7_Implementation_Plan.md`` §1+§4: their
# whole job is to catch a harness change leaking into the shipped
# adopter closure — exactly the kind of leak the segregated
# functionality suite by definition cannot catch.
#
# Two invariants:
#   1. No path under ``bin/harness/`` or the top-level
#      ``bin/qpb_harness.py`` appears in
#      ``install_skill._bundle_files()``'s manifest. The function is
#      an enumerated allowlist (~lines 213–229), so a new
#      subpackage is excluded BY DEFAULT — but the pin prevents a
#      future maintainer from "helpfully" adding it.
#   2. NO bundled module — and ``bin/__init__.py`` in particular —
#      transitively imports ``bin.harness``. The ``__init__.py``
#      path is the real leak vector the allowlist alone doesn't
#      catch: every ``import bin.X`` runs ``bin/__init__.py``, and
#      if it imported the harness, the harness would land in every
#      adopter install.


class HarnessBundleExclusion091Tests(unittest.TestCase):
    """v1.5.7 091 invariant 1: ``bin.install_skill._bundle_files()``
    never lists a path under ``bin/harness/`` or
    ``bin/qpb_harness.py``."""

    def test_no_harness_path_in_bundle_files(self) -> None:
        """Pin the closure manifest against ``bin/harness/`` and
        ``bin/qpb_harness.py``.

        Mutation bite: add a line like
        ``(_require_bundle_file(source_root / "bin" / "harness" /
        "schema.py"), Path("bin/harness/schema.py"))`` to
        ``_bundle_files()`` → this test FAILs.
        """
        from bin.install_skill import _bundle_files
        bundle = _bundle_files(REPO_ROOT)
        dest_paths = [str(dst) for _src, dst in bundle]
        for p in dest_paths:
            self.assertFalse(
                p.startswith("bin/harness/")
                or p == "bin/harness"
                or p == "bin/qpb_harness.py",
                f"v1.5.7 091: bin/harness/* and bin/qpb_harness.py "
                f"MUST be excluded from the install closure. "
                f"Found leaked path: {p!r}. The harness is release "
                f"tooling, not adopter-shipped code.",
            )

    def test_no_harness_subdir_in_staged_bundle(self) -> None:
        """End-to-end pin: after a stage, no ``bin/harness/``
        subdir appears under ``quality_playbook_cli/_bundle/``.

        Skipped if the stage hasn't been built (test runner has no
        wheel-build prereqs); the in-memory ``_bundle_files()``
        check above stays load-bearing regardless.
        """
        bundle_dir = REPO_ROOT / "quality_playbook_cli" / "_bundle"
        if not bundle_dir.is_dir():
            self.skipTest("staged _bundle/ not present")
        leaks = []
        for root, dirs, files in os.walk(bundle_dir):
            rel_root = Path(root).relative_to(bundle_dir).as_posix()
            if "harness" in rel_root.split("/"):
                leaks.append(rel_root)
            for name in files:
                if name == "qpb_harness.py":
                    leaks.append(str(Path(rel_root) / name))
        self.assertEqual(
            leaks, [],
            f"v1.5.7 091: harness files leaked into staged bundle: "
            f"{leaks}. The harness is release tooling and MUST NOT "
            f"reach adopter installs.",
        )


class HarnessImportIsolation091Tests(unittest.TestCase):
    """v1.5.7 091 invariant 2: importing the bundled closure does
    NOT transitively load ``bin.harness``.

    The mechanically real risk: every ``import bin.X`` runs
    ``bin/__init__.py``. If that file (or any module it imports)
    were to ``import bin.harness``, every adopter install would
    transitively load the harness on first use of ANY bundled
    bin/ module. The test launches a FRESH Python subprocess (so
    ``sys.modules`` is clean) and asserts ``bin.harness`` is
    absent after a representative sample of bundled-module
    imports.
    """

    # Representative sample of the bundled bin/ modules. We don't
    # exhaustively iterate _bundle_files() here because that would
    # re-prove the manifest pin above; we exercise the
    # ``bin/__init__.py`` path (which is the real load-bearing
    # surface) + a few high-leverage modules to be safe.
    _CHECK_MODULES = (
        "bin",  # the __init__.py itself
        "bin._purpose",
        "bin.install_skill",
        "bin.quality_playbook",
        "bin.run_state_lib",
    )

    def test_init_py_does_not_import_harness(self) -> None:
        """``bin/__init__.py`` itself doesn't grow a
        ``from .harness import ...`` line. Source-level pin —
        catches the leak even if the harness module isn't yet
        importable (e.g. mid-WIP).

        Mutation bite: add ``from . import harness`` to
        ``bin/__init__.py`` → this test FAILs.
        """
        init_py = REPO_ROOT / "bin" / "__init__.py"
        text = init_py.read_text(encoding="utf-8")
        self.assertNotIn(
            "harness", text,
            f"v1.5.7 091: bin/__init__.py MUST NOT reference "
            f"'harness'. It runs on every `import bin.*`; an "
            f"import here would leak the harness into every "
            f"adopter install. Found 'harness' in:\n{text}",
        )

    def test_importing_bundled_modules_does_not_load_harness(
            self) -> None:
        """Fresh-subprocess pin: import a representative sample of
        bundled modules and assert ``bin.harness`` is absent from
        ``sys.modules``.

        Mutation bite: have any bundled module (e.g.
        ``bin.run_state_lib``) ``import bin.harness.schema`` at
        module-load time → this test FAILs because ``bin.harness``
        appears in the fresh subprocess's ``sys.modules``.
        """
        script = (
            "import sys, json\n"
            "modules = " + repr(self._CHECK_MODULES) + "\n"
            "for m in modules:\n"
            "    __import__(m)\n"
            "leaked = sorted(\n"
            "    k for k in sys.modules\n"
            "    if k == 'bin.harness' or k.startswith('bin.harness.')\n"
            ")\n"
            "print(json.dumps({'leaked': leaked,\n"
            "                  'checked': list(modules)}))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(
            result.returncode, 0,
            f"v1.5.7 091: subprocess crashed during bundled-module "
            f"import sweep. stdout:\n{result.stdout}\nstderr:\n"
            f"{result.stderr}",
        )
        report = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(
            report["leaked"], [],
            f"v1.5.7 091: importing the bundled closure "
            f"({report['checked']}) transitively loaded "
            f"{report['leaked']}. The harness MUST NOT be reachable "
            f"from any bundled module — that path leaks it into "
            f"every adopter install.",
        )


if __name__ == "__main__":
    unittest.main()
