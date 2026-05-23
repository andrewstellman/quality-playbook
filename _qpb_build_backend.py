"""v1.5.7 090c — auto-stage build backend for the pip channel.

Wraps ``setuptools.build_meta`` so that ``python -m build`` (and
any other PEP 517 frontend) automatically stages the
``quality_playbook_cli/_bundle/`` tree before delegating to
setuptools. This closes the **cold-build empty-bundle hole** the
2026-05-23 Council found: pre-090c, ``pyproject.toml`` shipped
package-data globs that included whatever was in ``_bundle/``
"if present", which meant a fresh checkout (no prior ``stage()``
run) would produce a wheel + sdist containing ZERO ``_bundle/``
content. A release cut from a clean clone would push a dead
package.

Post-090c, the build sequence is:

  python -m build
    → frontend imports `_qpb_build_backend.build_wheel` (per
      ``[build-system].build-backend`` in pyproject.toml +
      ``backend-path = ["."]``)
    → this module calls ``bin/build_channel_package.stage(...)``
      first (which runs the 090b mandatory-member guard)
    → then delegates to ``setuptools.build_meta.build_wheel``

The build can never silently produce an incomplete artifact:
``build_channel_package.stage()``'s 090b
``_assert_mandatory_staged_members`` raises a clear error if any
load-time hard-dependency member is missing from the staged
tree.

**Important — backend self-isolation:** PEP 517 frontends like
``python -m build`` invoke the backend inside an isolated build
environment (``--no-isolation`` is the explicit opt-out). The
build env contains only what ``[build-system].requires``
declares. We delegate to ``setuptools.build_meta`` for the
actual wheel construction; the staging step calls
``bin/build_channel_package.py`` directly via Python's
file-path importlib. The build script is stdlib-only (no
third-party imports), so it runs cleanly in the isolated env.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from setuptools import build_meta as _setuptools_backend  # type: ignore[import-untyped]


# PEP 517 mandatory backend hooks — defaults reused from setuptools.
build_wheel = None  # overridden below
build_sdist = None  # overridden below
get_requires_for_build_wheel = _setuptools_backend.get_requires_for_build_wheel
get_requires_for_build_sdist = _setuptools_backend.get_requires_for_build_sdist
prepare_metadata_for_build_wheel = (
    _setuptools_backend.prepare_metadata_for_build_wheel
)
# Optional editable hook (setuptools>=64). Re-export when available.
build_editable = getattr(_setuptools_backend, "build_editable", None)
get_requires_for_build_editable = getattr(
    _setuptools_backend, "get_requires_for_build_editable", None,
)
prepare_metadata_for_build_editable = getattr(
    _setuptools_backend, "prepare_metadata_for_build_editable", None,
)


_REPO_ROOT = Path(__file__).resolve().parent


def _stage_bundle() -> None:
    """Stage ``quality_playbook_cli/_bundle/`` from the QPB clone's
    source layout via ``bin/build_channel_package.stage()``. Run
    automatically before every wheel/sdist build so cold-build
    artifacts always contain the complete bundle.

    Path-loads ``build_channel_package`` from the clone (NOT from
    sys.path) so the build can never resolve to a foreign sibling
    repo's ``bin/build_channel_package.py`` (the 090c root-cause
    pattern)."""
    script = _REPO_ROOT / "bin" / "build_channel_package.py"
    if not script.is_file():
        raise RuntimeError(
            f"_qpb_build_backend: cannot stage — build script "
            f"missing at {script}. The pyproject.toml backend "
            f"path is anchored on this file's location; this "
            f"error means the clone is incomplete or the "
            f"backend was invoked outside the QPB repo root."
        )
    spec = importlib.util.spec_from_file_location(
        "_qpb_build_channel_package_for_backend", script,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"_qpb_build_backend: importlib spec resolution "
            f"failed for {script}"
        )
    bcp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bcp)
    # Stage into the canonical dest. bcp.stage() runs 090b's
    # _assert_mandatory_staged_members at the end and raises if
    # any load-time hard-dep member is missing — that guard is
    # the load-bearing "no empty bundles" pin.
    dest = _REPO_ROOT / "quality_playbook_cli" / "_bundle"
    bcp.stage(_REPO_ROOT, dest, clean=True)


def build_wheel(wheel_directory, config_settings=None,
                metadata_directory=None):  # type: ignore[no-redef]
    _stage_bundle()
    return _setuptools_backend.build_wheel(
        wheel_directory, config_settings, metadata_directory,
    )


def build_sdist(sdist_directory, config_settings=None):  # type: ignore[no-redef]
    _stage_bundle()
    return _setuptools_backend.build_sdist(
        sdist_directory, config_settings,
    )


# Editable installs (pip install -e .): also stage, then delegate.
if build_editable is not None:  # setuptools >= 64
    _setuptools_editable = _setuptools_backend.build_editable  # type: ignore[attr-defined]

    def build_editable(  # type: ignore[no-redef]
        wheel_directory, config_settings=None, metadata_directory=None,
    ):
        _stage_bundle()
        return _setuptools_editable(
            wheel_directory, config_settings, metadata_directory,
        )
