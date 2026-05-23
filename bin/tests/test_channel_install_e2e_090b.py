"""v1.5.7 090b — channel install end-to-end test (ship-blocker).

The 2026-05-23 pip/npx smoke crash on macOS revealed a gap: the
existing bundle-parity test (`test_pip_channel_package_parity_
089u.py`) asserts that ``stage()``'s output set equals
``install_skill._bundle_files()`` — which AGREES even when
``_bundle_files()`` is wrong. The hygiene test
(`test_channel_artifact_hygiene_089y.py`) only checks no-`.pyc`
ships. Neither actually RUNS the built artifact. The crash was
``FileNotFoundError: .../quality_playbook_cli/_bundle/bin/
_purpose.py`` at install — the wheel built fine, ``pip install``
landed fine, but the first import of the bundled
``install_skill.py`` blew up because the staged bundle was
missing ``_purpose.py``.

This file closes that gap. It actually builds the wheel,
``pip install``s it into a throwaway venv, runs
``quality-playbook install --into <tmp> --ai-tool claude``, and
asserts the structured output contains ``install_complete
status=success``. Then it runs ``quality-playbook validate
<tmp>`` and asserts ``status=ok``. The same flow for npm via
``npm pack`` + ``npx --package=<tgz>``.

**Mutation bite** (per ai_context/DEVELOPMENT_PROCESS.md):
removing ``bin/_purpose.py`` from ``_bundle_files()`` (or
deleting it from the staged tree pre-build) would, pre-090b,
have produced a wheel that crashed at install — exactly the
ship-blocker bug 090b fixes. Post-090b, the same mutation
fires ``_bundle_files()``'s raise-on-missing helper at STAGE
time before the wheel can be built, so the test wouldn't even
reach the install step — it would fail at the stage call.
Either way, this test catches the regression class. Bite
executed PASS → FAIL (at stage) → PASS during 090b
development.

**Cost** — this is a HEAVY test (~30-60s per pip path, ~10-20s
per npm path; total ~60-90s on the dev host). It skips cleanly
when ``build`` / ``pip`` / ``node`` / ``npm`` aren't available,
same discipline as the other channel tests.

**Hermetic** — temp dirs only; no writes to the repo tree.
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


def _node_npm_available() -> bool:
    if shutil.which("node") is None or shutil.which("npm") is None:
        return False
    try:
        r1 = subprocess.run(["node", "--version"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=20)
        r2 = subprocess.run(["npm", "--version"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=20)
        return r1.returncode == 0 and r2.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


_PIP_OK = _build_available() and _venv_works()
_NPM_OK = _node_npm_available()


def _scaffold_target(target: Path) -> None:
    """Scaffold the minimum a target needs to validate cleanly: the
    `.gitignore` sentinel with the QPB block + `reference_docs/cite/`.
    Mirrors the existing 089u e2e test's target-prep pattern.

    The scaffolding is what install_skill normally writes itself
    (via its INSTALL_SCAFFOLDING list), but we pre-scaffold so the
    validate step has a clean baseline to assert on. The skill
    closure itself comes from `install` (the unit under test).
    """
    (target / ".gitignore").write_text(
        "# QPB scaffold\nquality/\n", encoding="utf-8",
    )
    (target / "reference_docs").mkdir(exist_ok=True)
    (target / "reference_docs" / "cite").mkdir(exist_ok=True)


@unittest.skipUnless(
    _PIP_OK,
    "`build` package + working `python -m venv` required — "
    "skipping the pip channel e2e install test.",
)
class PipChannelInstallE2E090bTests(unittest.TestCase):
    """The load-bearing test: build the wheel, pip-install it, run
    the console script against a temp target, assert install +
    validate report success. This is the test the 2026-05-23
    crash didn't have."""

    @classmethod
    def setUpClass(cls) -> None:
        """One-time fixture: stage the bundle + build the wheel +
        create the venv + pip install. All errors go to
        ``_setup_error`` so individual tests can fail cleanly with
        the diagnostic instead of aborting class setup."""
        cls._setup_error: str | None = None
        try:
            cls._build_dir = Path(tempfile.mkdtemp(prefix="qpb-090b-build-"))
            cls._venv_dir = Path(tempfile.mkdtemp(prefix="qpb-090b-venv-"))

            # 1. Stage the bundle (this is the unit under test —
            # the 090b T-A + T-B changes make staging fail loudly
            # if a mandatory member is missing).
            from bin import build_channel_package
            bundle_dest = REPO_ROOT / "quality_playbook_cli" / "_bundle"
            build_channel_package.stage(REPO_ROOT, bundle_dest, clean=True)

            # 2. Build the wheel.
            dist_dir = cls._build_dir / "dist"
            r = subprocess.run(
                [sys.executable, "-m", "build", "--wheel",
                 "--outdir", str(dist_dir), str(REPO_ROOT)],
                capture_output=True, text=True, timeout=180,
            )
            if r.returncode != 0:
                cls._setup_error = (
                    f"`python -m build --wheel` failed "
                    f"(rc={r.returncode}):\n"
                    f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
                )
                return
            wheels = list(dist_dir.glob("quality_playbook-*.whl"))
            if not wheels:
                cls._setup_error = (
                    f"build succeeded but no wheel found in "
                    f"{dist_dir}; contents: "
                    f"{sorted(p.name for p in dist_dir.iterdir())}"
                )
                return
            cls._wheel = wheels[0]

            # 3. Create venv.
            r = subprocess.run(
                [sys.executable, "-m", "venv", str(cls._venv_dir)],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                cls._setup_error = (
                    f"`python -m venv` failed (rc={r.returncode}):\n"
                    f"{r.stderr}"
                )
                return
            cls._venv_python = cls._venv_dir / "bin" / "python"
            cls._venv_qp = cls._venv_dir / "bin" / "quality-playbook"
            if not cls._venv_python.is_file():
                cls._setup_error = (
                    f"venv created but no python at {cls._venv_python}"
                )
                return

            # 4. pip install the wheel.
            r = subprocess.run(
                [str(cls._venv_python), "-m", "pip", "install",
                 "--quiet", "--disable-pip-version-check",
                 str(cls._wheel)],
                capture_output=True, text=True, timeout=180,
            )
            if r.returncode != 0:
                cls._setup_error = (
                    f"`pip install <wheel>` failed "
                    f"(rc={r.returncode}):\n"
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

    def test_install_reports_status_success(self) -> None:
        """**The load-bearing assertion**: ``quality-playbook
        install --into <tmp> --ai-tool claude`` runs end-to-end
        from the installed wheel and reports
        ``install_complete status=success``. Pre-090b this would
        have crashed with ``FileNotFoundError: .../_bundle/bin/
        _purpose.py`` before reaching the install logic.

        Mutation candidate: remove ``bin/_purpose.py`` from
        ``_bundle_files()``. Pre-090b that produced a wheel that
        crashed here; post-090b the staging step raises before the
        wheel can even be built — so the mutation bites at
        ``setUpClass`` time."""
        self._require_setup()
        with tempfile.TemporaryDirectory(prefix="qpb-090b-target-") as t:
            target = Path(t)
            r = subprocess.run(
                [str(self._venv_qp), "install",
                 "--into", str(target),
                 "--ai-tool", "claude",
                 "--no-smoke"],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(
                r.returncode, 0,
                f"090b: `quality-playbook install` (from built "
                f"wheel) must exit 0. rc={r.returncode}\n"
                f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}",
            )
            self.assertIn(
                "event=install_complete", r.stdout,
                f"090b: install must emit "
                f"event=install_complete. stdout:\n{r.stdout}",
            )
            self.assertIn(
                "status=success", r.stdout,
                f"090b: install_complete must carry "
                f"status=success. stdout:\n{r.stdout}",
            )
            # Sanity: the skill closure landed at the canonical
            # claude path.
            install_root = (
                target / ".claude" / "skills" / "quality-playbook"
            )
            self.assertTrue(
                install_root.is_dir(),
                f"090b: install closure missing at "
                f"{install_root}; install reported success but "
                f"the closure isn't on disk.",
            )

    def test_validate_reports_status_ok_after_install(self) -> None:
        """After ``install``, ``quality-playbook validate <target>``
        reports ``status=ok``. This is the second half of the
        2026-05-23 smoke validation."""
        self._require_setup()
        with tempfile.TemporaryDirectory(prefix="qpb-090b-vtarget-") as t:
            target = Path(t)
            _scaffold_target(target)
            r_install = subprocess.run(
                [str(self._venv_qp), "install",
                 "--into", str(target),
                 "--ai-tool", "claude",
                 "--no-smoke"],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(
                r_install.returncode, 0,
                f"install precondition failed: rc="
                f"{r_install.returncode}; stderr:\n"
                f"{r_install.stderr}",
            )
            r_validate = subprocess.run(
                [str(self._venv_qp), "validate", str(target)],
                capture_output=True, text=True, timeout=120,
            )
            # qpb_validate returns 0 on status=ok, 1 on
            # remediable, 2 on blocked. The contract here is
            # status=ok (and rc=0) — anything else is a failure
            # the 090b ship-readiness gate must catch.
            self.assertEqual(
                r_validate.returncode, 0,
                f"090b: validate must exit 0 on a scaffolded "
                f"freshly-installed target. rc="
                f"{r_validate.returncode}\nstdout:\n"
                f"{r_validate.stdout}\nstderr:\n"
                f"{r_validate.stderr}",
            )
            self.assertIn(
                "status=ok", r_validate.stdout,
                f"090b: validate must emit status=ok on a "
                f"scaffolded freshly-installed target. "
                f"stdout:\n{r_validate.stdout}",
            )


@unittest.skipUnless(
    _NPM_OK,
    "node/npm not available — skipping the npm channel e2e "
    "install test.",
)
class NpmChannelInstallE2E090bTests(unittest.TestCase):
    """The npm side of the 090b ship-readiness gate. Builds the
    npm tarball, ``npx --package=<tgz>`` invokes it, and asserts
    the install closure landed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._setup_error: str | None = None
        try:
            cls._build_dir = Path(tempfile.mkdtemp(prefix="qpb-090b-npm-"))

            # Stage the bundle (same as the pip class).
            from bin import build_channel_package
            bundle_dest = REPO_ROOT / "quality_playbook_cli" / "_bundle"
            build_channel_package.stage(REPO_ROOT, bundle_dest, clean=True)

            # Stage a tarball-shaped tree under build_dir.
            staged = cls._build_dir / "qpb-npm-stage"
            staged.mkdir()
            for rel in ("package.json", "README.md", "LICENSE",
                        ".npmignore"):
                src = REPO_ROOT / rel
                if src.is_file():
                    shutil.copy2(src, staged / rel)
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
            build_channel_package.stage(
                REPO_ROOT,
                staged / "quality_playbook_cli" / "_bundle",
                clean=True,
            )
            cls._npm_staged = staged

            # npm pack — produces the tarball in the cwd.
            r = subprocess.run(
                # --ignore-scripts skips the 090c prepack hook
                # (fixture pre-stages manually).
                ["npm", "pack", "--silent", "--ignore-scripts"],
                cwd=str(staged),
                capture_output=True, text=True, timeout=180,
            )
            if r.returncode != 0:
                cls._setup_error = (
                    f"`npm pack` failed (rc={r.returncode}):\n"
                    f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
                )
                return
            tarballs = list(staged.glob("quality-playbook-*.tgz"))
            if not tarballs:
                cls._setup_error = (
                    f"npm pack succeeded but no tarball at {staged}"
                )
                return
            cls._tarball = tarballs[0]
        except (OSError, subprocess.TimeoutExpired) as exc:
            cls._setup_error = f"setUpClass exception: {exc!r}"

    @classmethod
    def tearDownClass(cls) -> None:
        d = getattr(cls, "_build_dir", None)
        if d is not None and d.is_dir():
            shutil.rmtree(d, ignore_errors=True)

    def _require_setup(self) -> None:
        if self._setup_error is not None:
            self.fail(self._setup_error)

    def test_npx_install_lands_closure(self) -> None:
        """``npx --package=<tgz> quality-playbook init
        --ai-tool=claude`` in a temp cwd lands the skill closure
        at ``.claude/skills/quality-playbook/``."""
        self._require_setup()
        with tempfile.TemporaryDirectory(prefix="qpb-090b-npx-") as t:
            target = Path(t)
            r = subprocess.run(
                ["npx", "--yes",
                 f"--package={self._tarball}",
                 "quality-playbook", "init",
                 "--ai-tool=claude", "--no-smoke"],
                cwd=str(target),
                capture_output=True, text=True, timeout=180,
                env=os.environ.copy(),
            )
            self.assertEqual(
                r.returncode, 0,
                f"090b npx install must exit 0. rc={r.returncode}\n"
                f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}",
            )
            install_root = (
                target / ".claude" / "skills" / "quality-playbook"
            )
            self.assertTrue(
                install_root.is_dir(),
                f"090b: npx install closure missing at "
                f"{install_root}; install reported success but "
                f"the closure isn't on disk.",
            )
            for required in ("SKILL.md", "quality_gate.py"):
                self.assertTrue(
                    (install_root / required).is_file(),
                    f"090b: installed closure missing "
                    f"{required} at {install_root}",
                )


if __name__ == "__main__":
    unittest.main()
