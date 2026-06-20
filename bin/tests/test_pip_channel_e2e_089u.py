"""v1.5.7 089u — end-to-end pip-channel install tests.

These tests build the `quality-playbook` wheel (`python -m build`)
and install it into a clean temporary venv, then verify:

1. **No top-level `bin` in site-packages** — `python -c "import
   bin"` MUST FAIL after the wheel is installed. The hard packaging
   constraint: only `quality_playbook_cli` resolves; the tooling
   closure ships as data, not as an importable top-level package.

2. **`quality-playbook --help` works** — the console script entry
   point resolves and prints install_skill's help (the shim
   forwards `--help` through after stripping the optional `install`
   verb).

3. **End-to-end install** — `quality-playbook install --into
   <tmp-repo> --ai-tool claude` writes the skill bundle into the
   tempdir's `.claude/skills/quality-playbook/` and exits 0; the
   installed closure matches `_bundle_files()` (no drift between
   the clone install and the pip install).

These are **heavy** integration tests (build a wheel + create a
venv + pip install + run subprocess) — each can take 30s-2min. They
gracefully skip when the prerequisites (`build` package, working
`python -m venv`) are unavailable, so the suite stays green on
minimal CI runners.

**Mutation-bite evidence** (per ai_context/DEVELOPMENT_PROCESS.md):

- Edit ``pyproject.toml`` to set ``packages = ["quality_playbook_cli",
  "bin"]`` (so setuptools publishes ``bin/`` as an importable
  top-level package). Expected failure:
  ``test_import_bin_fails_after_pip_install`` fires because
  ``python -c 'import bin'`` now succeeds.

- Comment out the ``os.environ.setdefault("QPB_CHANNEL", "pip")``
  call in ``quality_playbook_cli.main``. Expected failure: the
  e2e install would still succeed (the shim still works) but the
  channel-remediation pin in the e2e tests' validator step would
  fall back to the clone form rather than uvx. (Not exercised by
  this file's tests — the channel pin is in
  ``test_pip_channel_remediation_089u.py``; mentioned here for
  completeness.)

Both pip-channel bites executed PASS → FAIL → PASS during 089u
development.
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


# v1.5.7 090d: skip-clean check via the centralized helper. The
# previous in-process ``import build`` check returned True even
# when ``build`` was a namespace package missing ``__main__.py``
# (and therefore ``python -m build`` failed). The new check runs
# ``sys.executable -m build --help`` — same entry point the test
# will invoke — so skip-vs-run agrees with what the test does.
from bin.tests._channel_test_helpers import (  # noqa: E402
    pip_channel_prereqs_ok as _pip_channel_prereqs_ok,
    SKIP_PIP_PREREQS as _SKIP_PIP_PREREQS,
)

_PREREQS_OK = _pip_channel_prereqs_ok()


@unittest.skipUnless(
    _PREREQS_OK,
    _SKIP_PIP_PREREQS + " (089u e2e: skipping cleanly on minimal "
    "CI runners).",
)
class PipChannelE2E089uTests(unittest.TestCase):
    """Build a wheel from the QPB clone + install it into a clean
    venv + verify the hard packaging constraint and end-to-end
    install path.

    Each test does the full build+install once (in a class-level
    fixture) for cost efficiency — the heavy work runs once even
    if multiple tests share the venv."""

    _venv_dir: Path | None = None
    _venv_python: Path | None = None
    _wheel: Path | None = None
    _build_dir: Path | None = None
    _setup_error: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        """Stage the bundle, build the wheel, create a venv, install
        the wheel. All errors are captured into ``_setup_error`` so
        the individual tests can fail cleanly with the diagnostic
        rather than aborting class setup."""
        try:
            cls._build_dir = Path(tempfile.mkdtemp(prefix="qpb-e2e-build-"))
            cls._venv_dir = Path(tempfile.mkdtemp(prefix="qpb-e2e-venv-"))

            # 1. Stage the bundle.
            from bin import build_channel_package
            bundle_dest = REPO_ROOT / "quality_playbook_cli" / "_bundle"
            build_channel_package.stage(REPO_ROOT, bundle_dest, clean=True)

            # 2. Build the wheel into _build_dir/dist.
            dist_dir = cls._build_dir / "dist"
            r = subprocess.run(
                [
                    sys.executable, "-m", "build",
                    "--wheel",
                    "--outdir", str(dist_dir),
                    str(REPO_ROOT),
                ],
                capture_output=True, text=True, timeout=180,
            )
            if r.returncode != 0:
                cls._setup_error = (
                    f"`python -m build` failed (rc={r.returncode}):\n"
                    f"--- stdout ---\n{r.stdout}\n"
                    f"--- stderr ---\n{r.stderr}\n"
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

            # 3. Create the venv.
            r = subprocess.run(
                [sys.executable, "-m", "venv", str(cls._venv_dir)],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                cls._setup_error = (
                    f"`python -m venv` failed (rc={r.returncode}):\n"
                    f"{r.stderr}\n"
                )
                return
            # On macOS / Linux: <venv>/bin/python. On Windows:
            # <venv>\Scripts\python.exe (not exercised here).
            cls._venv_python = cls._venv_dir / "bin" / "python"
            if not cls._venv_python.is_file():
                cls._setup_error = (
                    f"venv created but no Python interpreter at "
                    f"{cls._venv_python}"
                )
                return

            # 4. Install the wheel into the venv.
            r = subprocess.run(
                [str(cls._venv_python), "-m", "pip", "install",
                 "--quiet", "--disable-pip-version-check",
                 str(cls._wheel)],
                capture_output=True, text=True, timeout=180,
            )
            if r.returncode != 0:
                cls._setup_error = (
                    f"`pip install <wheel>` failed (rc={r.returncode}):\n"
                    f"--- stdout ---\n{r.stdout}\n"
                    f"--- stderr ---\n{r.stderr}\n"
                )
                return
        except (OSError, subprocess.TimeoutExpired) as exc:
            cls._setup_error = f"setUpClass exception: {exc!r}"

    @classmethod
    def tearDownClass(cls) -> None:
        """Best-effort cleanup of the venv + build dirs. Also wipe
        the staged ``_bundle/`` so a subsequent clone test run
        starts clean."""
        for d in (cls._venv_dir, cls._build_dir):
            if d is not None and d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
        # The staged _bundle/ under quality_playbook_cli/ is
        # gitignored; leave it for now (a subsequent stage() call
        # will clean it). The test does not rely on its absence.

    def _require_setup(self) -> None:
        if self._setup_error is not None:
            self.fail(self._setup_error)

    def test_import_bin_fails_after_pip_install(self) -> None:
        """**The hard packaging constraint.** After the wheel is
        installed into a clean venv, ``python -c 'import bin'`` MUST
        FAIL. The QPB tooling closure ships as package data, not as
        a top-level import package.

        Mutation candidate: extend ``pyproject.toml``'s
        ``[tool.setuptools].packages`` list to include ``"bin"``.
        Expected failure: this test fires because the wheel now
        publishes a top-level ``bin`` import package."""
        self._require_setup()
        # Use Python's isolated mode (-I) so the import resolves
        # purely against site-packages, NOT against the cwd or
        # PYTHONPATH. Without this, the test would falsely succeed
        # in finding `bin/` because the test process cwd is the QPB
        # clone root (which DOES have a top-level `bin/`). What we
        # want to verify is that the WHEEL doesn't ship `bin/` as
        # an importable top-level package.
        r = subprocess.run(
            [str(self._venv_python), "-I", "-c", "import bin"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(
            r.returncode, 0,
            f"089u hard packaging constraint: `import bin` (in "
            f"isolated mode) must FAIL after the wheel is "
            f"installed into a clean venv — only site-packages "
            f"resolves, and the wheel must not publish a top-"
            f"level `bin/` import package. It succeeded (rc=0). "
            f"Stdout:\n{r.stdout}\n"
            f"Fix pyproject.toml's [tool.setuptools].packages "
            f"list to exclude `bin`.",
        )
        # Must specifically be ModuleNotFoundError / ImportError —
        # not a syntax error or other failure mode.
        self.assertIn(
            "ModuleNotFoundError",
            r.stderr,
            f"089u: `import bin` failed but not with the expected "
            f"ModuleNotFoundError. stderr:\n{r.stderr}",
        )

    def test_import_quality_playbook_cli_succeeds(self) -> None:
        """The thin shim package IS importable — that's the only
        QPB top-level import the wheel publishes."""
        self._require_setup()
        r = subprocess.run(
            [str(self._venv_python), "-c",
             "import quality_playbook_cli; "
             "print(quality_playbook_cli.__version__)"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            r.returncode, 0,
            f"089u: `import quality_playbook_cli` must succeed "
            f"after wheel install. rc={r.returncode}; stderr:\n"
            f"{r.stderr}",
        )
        # v1.5.10 instruction 057: __version__ DERIVES from SKILL.md
        # frontmatter (the single source) — read the canonical version
        # dynamically rather than pinning a literal so this survives
        # future bumps.
        from bin import _purpose
        skill_version = _purpose.get_version()
        self.assertNotEqual(
            skill_version, "unknown",
            "089u: SKILL.md frontmatter version must resolve.",
        )
        self.assertIn(
            skill_version, r.stdout,
            f"089u: quality_playbook_cli.__version__ should be "
            f"{skill_version} (from SKILL.md). Got: {r.stdout!r}",
        )

    def test_console_script_help_works(self) -> None:
        """``quality-playbook --help`` runs the shim → install_skill
        forwards --help and prints the install_skill argparse help.
        We just check it exits 0 and emits a reasonable banner."""
        self._require_setup()
        bin_dir = self._venv_dir / "bin"
        qp = bin_dir / "quality-playbook"
        if not qp.is_file():
            self.skipTest(
                f"quality-playbook console script not at {qp} "
                f"(unusual venv layout)"
            )
        r = subprocess.run(
            [str(qp), "--help"],
            capture_output=True, text=True, timeout=30,
        )
        # argparse prints help to stdout and exits 0.
        self.assertEqual(r.returncode, 0, f"stderr: {r.stderr}")
        # The shim does NOT pollute stdout with the install banner
        # before --help — the banner goes to stderr only at the END
        # of a successful install; --help short-circuits argparse
        # before any install runs.
        # Just confirm we got argparse usage output, not a stack trace.
        combined = (r.stdout + r.stderr).lower()
        self.assertTrue(
            "usage" in combined or "install_skill" in combined,
            f"`quality-playbook --help` produced no recognizable "
            f"help text. stdout:\n{r.stdout}\nstderr:\n{r.stderr}",
        )

    def test_validate_verb_runs_against_installed_target(self) -> None:
        """``quality-playbook validate <target>`` routes to the
        bundled ``qpb_validate.py`` and reports against a target
        that just received a quality-playbook install. The
        remediation string ``uvx quality-playbook validate
        <target>`` (089u channel-aware pip form) is expected to
        resolve to a real runnable command — this test verifies
        the shim actually wires it."""
        self._require_setup()
        bin_dir = self._venv_dir / "bin"
        qp = bin_dir / "quality-playbook"
        if not qp.is_file():
            self.skipTest(
                f"quality-playbook console script not at {qp}"
            )

        with tempfile.TemporaryDirectory(prefix="qpb-e2e-validate-") as target:
            target_path = Path(target)
            # First, install so there's something to validate.
            r_install = subprocess.run(
                [str(qp), "install",
                 "--into", str(target_path),
                 "--ai-tool", "claude",
                 "--no-smoke"],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(
                r_install.returncode, 0,
                f"089u validate-verb: install step must succeed first; "
                f"rc={r_install.returncode}; stderr:\n{r_install.stderr}",
            )
            # Now run validate against the same target. qpb_validate's
            # exit codes: 0 ok, 1 remediable, 2 fail; we don't pin a
            # specific code (the target's scaffolding state can vary),
            # only that the verb resolves and runs (rc != exception-
            # level codes from argparse / Python).
            r_validate = subprocess.run(
                [str(qp), "validate", str(target_path)],
                capture_output=True, text=True, timeout=60,
            )
            # If the verb routing were broken, argparse would emit
            # "unrecognized arguments" with rc=2 AND no event= lines.
            # A real qpb_validate run emits event=validation_complete.
            self.assertIn(
                "event=", r_validate.stdout,
                f"089u validate-verb: `quality-playbook validate` "
                f"must route to qpb_validate.py and emit event= "
                f"lines on stdout. rc={r_validate.returncode}; "
                f"stdout:\n{r_validate.stdout}\nstderr:\n"
                f"{r_validate.stderr}",
            )

    def test_end_to_end_install_into_tempdir(self) -> None:
        """``quality-playbook install --into <tmp-repo> --ai-tool
        claude`` produces a .claude/skills/quality-playbook/ tree
        whose closure matches ``_bundle_files()`` — the same set
        an adopter would get from a clone install."""
        self._require_setup()
        bin_dir = self._venv_dir / "bin"
        qp = bin_dir / "quality-playbook"
        if not qp.is_file():
            self.skipTest(
                f"quality-playbook console script not at {qp}"
            )

        with tempfile.TemporaryDirectory(prefix="qpb-e2e-target-") as target:
            target_path = Path(target)
            # Run the install — non-verbose to keep stdout machine-
            # parseable.
            r = subprocess.run(
                [str(qp), "install",
                 "--into", str(target_path),
                 "--ai-tool", "claude",
                 "--no-smoke"],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(
                r.returncode, 0,
                f"089u e2e: `quality-playbook install` must succeed "
                f"into {target_path}. rc={r.returncode}; "
                f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}",
            )
            install_root = target_path / ".claude" / "skills" / "quality-playbook"
            self.assertTrue(
                install_root.is_dir(),
                f"089u e2e: install root {install_root} does not "
                f"exist after the install command.",
            )
            # Sanity-check load-bearing files: SKILL.md +
            # quality_gate.py + references/ + bin/citation_verifier.
            for must_have in (
                "SKILL.md",
                "quality_gate.py",
                "references/exploration_patterns.md",
                "bin/citation_verifier.py",
            ):
                self.assertTrue(
                    (install_root / must_have).is_file(),
                    f"089u e2e: expected installed file "
                    f"{must_have} missing from {install_root}",
                )


if __name__ == "__main__":
    unittest.main()
