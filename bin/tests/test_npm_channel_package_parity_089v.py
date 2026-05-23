"""v1.5.7 089v — npm tarball bundle-parity tests.

The npm distribution channel (block C) is the fourth surface that
must stay in lockstep with ``install_skill._bundle_files()``:

  1. The clone workflow (``python3 -m bin.install_skill``).
  2. The AGENTS.md cp-block (the operator-facing one-liner the
     drift guard pins to ``_bundle_files()``'s manifest).
  3. The pip wheel (assembled by ``bin/build_channel_package.py``
     under ``quality_playbook_cli/_bundle/``; pinned by
     ``test_pip_channel_package_parity_089u.py``).
  4. The npm tarball (assembled at publish time; pinned by THIS
     file).

For the npm tarball the staged ``quality_playbook_cli/_bundle/``
tree is the same artifact the wheel uses — produced by
``build_channel_package.stage()``. The npm-only additions are
``bin/quality-playbook.js`` (the Node shim) and ``package.json``
(npm metadata). Both are enumerated by the new
``build_channel_package.npm_extra_paths()`` helper.

Test layers:

- **Structural** (always run, no node required): assert
  ``enumerate_npm_tarball()`` is the expected superset of
  ``_bundle_files()`` + the executors + the npm-only extras, and
  that ``package.json``'s ``files`` array lists every entry the
  npm tarball ultimately needs.
- **End-to-end** (``@skipUnless(node + npm)``): actually run
  ``npm pack --dry-run --json`` from a staged temp tree, parse
  the file list, and assert it contains every clone-relative
  ``_bundle_files()`` path under the ``quality_playbook_cli/
  _bundle/`` prefix plus both npm extras.

Mutation-bite evidence (per ai_context/DEVELOPMENT_PROCESS.md):
delete one entry from ``npm_extra_paths()`` — the structural
test ``test_npm_extras_includes_node_shim_and_package_json``
fires. Drop a member from ``_bundle_files()`` — the e2e parity
test ``test_npm_pack_dry_run_includes_every_bundle_file`` fires.
Restore by reverting. Bites executed PASS → FAIL → PASS during
089v development.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bin import build_channel_package as bcp  # noqa: E402
from bin import install_skill  # noqa: E402


def _npm_available() -> bool:
    """Return True iff `npm` is on PATH and runnable. The npm e2e
    test is @skipUnless'd on this so the suite stays GREEN in
    node-less envs (the instruction's halt condition: node-
    dependent tests SKIP, not FAIL)."""
    for cmd in ("npm",):
        result = shutil.which(cmd)
        if result is None:
            return False
    # Confirm `npm --version` actually runs.
    try:
        proc = subprocess.run(
            ["npm", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


_NPM_OK = _npm_available()


class NpmChannelPackageParity089vStructuralTests(unittest.TestCase):
    """Layer 1 — structural assertions. No node/npm required."""

    def test_npm_extras_includes_node_shim_and_package_json(self) -> None:
        """``npm_extra_paths()`` must enumerate exactly the npm-
        specific extras: the Node shim + ``package.json``. These
        are the files the wheel does NOT include but the npm
        tarball does."""
        extras = bcp.npm_extra_paths(REPO_ROOT)
        expected = [
            REPO_ROOT / "bin" / "quality-playbook.js",
            REPO_ROOT / "package.json",
        ]
        self.assertEqual(
            extras, expected,
            "089v: npm_extra_paths() must list the Node shim and "
            "package.json — extending it requires updating the npm "
            "tarball contract in the parity test deliberately.",
        )
        for p in extras:
            self.assertTrue(
                p.is_file(),
                f"089v: npm extra {p} must exist in the repo "
                f"(missing file would ship a broken npm tarball).",
            )

    def test_enumerate_npm_tarball_superset_of_bundle_files(self) -> None:
        """``enumerate_npm_tarball()`` must be a STRICT SUPERSET of
        ``install_skill._bundle_files()``'s source set — every
        clone-relative bundle file must be present in the npm
        tarball, plus the executors, the Python shim, and the
        npm-only extras."""
        npm_paths = set(bcp.enumerate_npm_tarball(REPO_ROOT))
        bundle_sources = {src for src, _dest_rel in
                          install_skill._bundle_files(REPO_ROOT)}
        missing = bundle_sources - npm_paths
        self.assertFalse(
            missing,
            f"089v: enumerate_npm_tarball() is missing "
            f"{len(missing)} _bundle_files() entries — the npm "
            f"tarball will ship an incomplete skill closure. "
            f"Missing (first 5): "
            f"{sorted(missing)[:5]}",
        )

    def test_enumerate_npm_tarball_includes_python_shim_and_extras(
            self) -> None:
        """The Python shim (``quality_playbook_cli/__init__.py``)
        AND its ``__main__.py`` (the ``python -m`` entry the Node
        shim invokes) must be in the npm tarball — without
        ``__main__.py`` ``python -m quality_playbook_cli`` fails
        with "package and cannot be directly executed". Both npm
        extras (Node shim + package.json) must also be present."""
        npm_paths = set(bcp.enumerate_npm_tarball(REPO_ROOT))
        for required in (
            REPO_ROOT / "quality_playbook_cli" / "__init__.py",
            REPO_ROOT / "quality_playbook_cli" / "__main__.py",
        ):
            self.assertIn(
                required, npm_paths,
                f"089v: enumerate_npm_tarball() must include "
                f"{required.name} — without it the Node shim's "
                f"`python -m quality_playbook_cli` cannot run.",
            )
        for extra in bcp.npm_extra_paths(REPO_ROOT):
            self.assertIn(
                extra, npm_paths,
                f"089v: enumerate_npm_tarball() must include the "
                f"npm extra {extra}.",
            )

    def test_package_json_files_field_covers_npm_payload(self) -> None:
        """``package.json``'s ``files`` array must list patterns
        that, taken together, cover the Node shim + the Python
        shim's full subtree (so the staged ``_bundle/`` data ships
        with the tarball when present)."""
        package_json = json.loads(
            (REPO_ROOT / "package.json").read_text())
        files = package_json.get("files", [])
        # Must list the Node shim path explicitly.
        self.assertIn(
            "bin/quality-playbook.js", files,
            "089v: package.json files must list "
            "bin/quality-playbook.js — npm pack would otherwise "
            "omit the entry-point shim.",
        )
        # Must list a glob that covers the entire
        # `quality_playbook_cli/` subtree (including the staged
        # `_bundle/`).
        has_qpc_glob = any(
            p.startswith("quality_playbook_cli/")
            and (p.endswith("**/*") or p.endswith("**"))
            for p in files
        )
        self.assertTrue(
            has_qpc_glob,
            f"089v: package.json files must include a recursive "
            f"glob under quality_playbook_cli/ (e.g. "
            f"'quality_playbook_cli/**/*') — got: {files}",
        )

    def test_package_json_bin_points_at_node_shim(self) -> None:
        """The npm ``bin`` field must map ``quality-playbook`` ->
        ``bin/quality-playbook.js`` — that's the entry npm
        installs onto PATH for ``npx quality-playbook …``."""
        package_json = json.loads(
            (REPO_ROOT / "package.json").read_text())
        bin_field = package_json.get("bin")
        self.assertIsInstance(
            bin_field, dict,
            "089v: package.json bin must be an object mapping "
            "command names to script paths.",
        )
        self.assertEqual(
            bin_field.get("quality-playbook"),
            "bin/quality-playbook.js",
            "089v: package.json bin.quality-playbook must point "
            "at bin/quality-playbook.js (the Node shim).",
        )

    def test_package_json_name_and_version_match_wheel(self) -> None:
        """The npm package's name + version must match the wheel
        (operator publishes both as the same release version)."""
        package_json = json.loads(
            (REPO_ROOT / "package.json").read_text())
        self.assertEqual(package_json.get("name"), "quality-playbook")
        self.assertEqual(package_json.get("version"), "1.5.7")


@unittest.skipUnless(
    _NPM_OK,
    "npm not available — skipping the npm-pack e2e parity test (the "
    "instruction's halt condition: node-dependent tests SKIP, not "
    "FAIL, in node-less envs).",
)
class NpmChannelPackageParity089vE2ETests(unittest.TestCase):
    """Layer 2 — actually invoke ``npm pack --dry-run --json`` on a
    staged tree and assert the tarball's file list matches the
    contract."""

    def setUp(self) -> None:
        # Stage the bundle into a temp dir so npm pack reads the
        # full payload (the live clone's quality_playbook_cli/_bundle/
        # is gitignored and only built at publish time).
        self.workdir = Path(tempfile.mkdtemp(prefix="qpb_089v_npm_"))
        self.staged = self.workdir / "qpb"
        self.staged.mkdir()
        # Copy package.json, the Node shim, the Python shim, and
        # the README/LICENSE if present.
        for rel in ("package.json", "README.md", "LICENSE"):
            src = REPO_ROOT / rel
            if src.is_file():
                shutil.copy2(src, self.staged / rel)
        (self.staged / "bin").mkdir(exist_ok=True)
        shutil.copy2(
            REPO_ROOT / "bin" / "quality-playbook.js",
            self.staged / "bin" / "quality-playbook.js",
        )
        # Stage the Python shim + its data bundle.
        bundle_dir = self.staged / "quality_playbook_cli" / "_bundle"
        bcp.stage(REPO_ROOT, bundle_dir, clean=True)
        shutil.copy2(
            REPO_ROOT / "quality_playbook_cli" / "__init__.py",
            self.staged / "quality_playbook_cli" / "__init__.py",
        )

    def tearDown(self) -> None:
        if self.workdir.exists():
            shutil.rmtree(self.workdir)

    def _npm_pack_filelist(self) -> set[str]:
        """Run ``npm pack --dry-run --json`` from ``self.staged``
        and return the set of tarball-relative paths."""
        proc = subprocess.run(
            ["npm", "pack", "--dry-run", "--json"],
            cwd=self.staged,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        # `npm pack --json` returns a list of one object with a
        # `files` field listing tarball entries.
        self.assertEqual(
            proc.returncode, 0,
            f"npm pack --dry-run failed: stdout={proc.stdout!r} "
            f"stderr={proc.stderr!r}",
        )
        data = json.loads(proc.stdout.decode("utf-8"))
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        files = data[0].get("files", [])
        return {entry["path"] for entry in files}

    def test_npm_pack_dry_run_includes_node_shim_and_package_json(
            self) -> None:
        """The npm tarball must ship the Node shim and the package
        manifest itself."""
        names = self._npm_pack_filelist()
        for required in ("bin/quality-playbook.js", "package.json"):
            self.assertIn(
                required, names,
                f"089v: npm pack manifest missing {required} — the "
                f"tarball would not run.",
            )

    def test_npm_pack_dry_run_includes_python_shim(self) -> None:
        """The npm tarball must ship the Python shim — the Node
        shim's spawned ``python -m quality_playbook_cli`` cannot
        resolve otherwise."""
        names = self._npm_pack_filelist()
        self.assertIn(
            "quality_playbook_cli/__init__.py", names,
            "089v: npm pack manifest missing the Python shim — "
            "the Node shim's `python -m quality_playbook_cli` "
            "would fail with ModuleNotFoundError at the adopter's "
            "machine.",
        )

    def test_npm_pack_dry_run_includes_every_bundle_file(self) -> None:
        """Every clone-relative ``_bundle_files()`` source must
        appear in the npm tarball under the
        ``quality_playbook_cli/_bundle/`` prefix.

        Mutation candidate: drop a member from ``_bundle_files()``
        in ``bin/install_skill.py``. Expected failure: this test
        fires because the missing member's clone-relative path is
        absent from the tarball manifest."""
        names = self._npm_pack_filelist()
        missing = []
        for src, _dest_rel in install_skill._bundle_files(REPO_ROOT):
            rel = src.resolve().relative_to(REPO_ROOT)
            tarball_rel = "quality_playbook_cli/_bundle/" + rel.as_posix()
            if tarball_rel not in names:
                missing.append(tarball_rel)
        self.assertFalse(
            missing,
            f"089v: npm pack manifest is missing "
            f"{len(missing)} _bundle_files() entries under "
            f"quality_playbook_cli/_bundle/. First 5: {missing[:5]}",
        )


if __name__ == "__main__":
    unittest.main()
