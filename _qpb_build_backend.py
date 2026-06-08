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


def _is_source_tree_build() -> bool:
    """v1.5.7 090f: distinguish a SOURCE-TREE build (where
    ``stage()`` + ``stamp()`` need to run because the staged
    bundle / stamped versions might be stale) from an
    SDIST-UNPACK build (where the sdist already contains a
    complete, stamped bundle and the dev machinery isn't
    present).

    The standard publish path is ``python -m build`` (no
    ``--wheel``), which builds the sdist first and then builds
    the wheel FROM THE UNPACKED SDIST in a temp dir. The
    unpacked sdist contains the backend module (per 090f's
    MANIFEST.in addition) + the pyproject.toml + the already-
    staged ``quality_playbook_cli/_bundle/`` — but NOT the root
    ``bin/build_channel_package.py`` / ``bin/install_skill.py``
    / ``SKILL.md`` etc. Trying to ``stage()`` or ``stamp()``
    from the sdist would crash because the build machinery
    isn't reachable.

    The discriminator: presence of plugin-skill ``SKILL.md`` AND
    ``bin/build_channel_package.py``. Both exist in a real QPB
    clone (source-tree); neither is in the sdist. A single
    AND-check is enough because the sdist ships only the
    runtime artifact + the backend module, not the dev
    machinery (per 090f's halt-condition: don't ship dev
    machinery in the sdist as the "fix").

    v1.5.8 instruction 209: SKILL.md lives under the standard
    self-hosted marketplace plugin layout
    (``plugins/quality-playbook/skills/quality-playbook/SKILL.md``).
    208 placed it at ``skills/quality-playbook/SKILL.md``; both are
    accepted with the pre-208 root-SKILL.md form as a final safety
    net for in-progress restructures."""
    skill_md_locations = (
        _REPO_ROOT / "plugins" / "quality-playbook"
        / "skills" / "quality-playbook" / "SKILL.md",
        _REPO_ROOT / "skills" / "quality-playbook" / "SKILL.md",
        _REPO_ROOT / "SKILL.md",
    )
    return (
        any(p.is_file() for p in skill_md_locations)
        and (_REPO_ROOT / "bin" / "build_channel_package.py").is_file()
    )


def _load_build_channel_package():
    """Path-load ``bin/build_channel_package.py`` from the QPB
    clone (anchored on `_REPO_ROOT`, never via sys.path). Used by
    both `_stage_bundle` and `_stamp_version` so the build can
    never resolve to a foreign sibling repo's `bin/`."""
    script = _REPO_ROOT / "bin" / "build_channel_package.py"
    if not script.is_file():
        raise RuntimeError(
            f"_qpb_build_backend: cannot path-load — build script "
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
    sys.modules[spec.name] = bcp
    spec.loader.exec_module(bcp)
    return bcp


def _stamp_version() -> None:
    """v1.5.7 090e T5: stamp ``SKILL.md`` version into
    ``pyproject.toml`` + ``package.json`` BEFORE the build runs.

    Pre-090e, version stamping happened only in
    `bin/build_channel_package.py`'s CLI `main()`. Since 090c
    made cold ``python -m build`` (which goes through this
    backend) the blessed release path, a bare ``python -m
    build`` after a SKILL.md version bump — without
    separately running the stamper CLI — could ship a stale
    version. 090e wires the stamp into the backend's build
    path so any ``python -m build`` produces a correctly-
    versioned artifact.

    The stamper reads SKILL.md frontmatter (`_purpose.
    get_version()`) and rewrites the ``version =`` field in
    pyproject.toml + the ``"version"`` field in
    package.json. Idempotent — re-running with SKILL.md
    unchanged is a no-op."""
    bcp = _load_build_channel_package()
    # `stamp_channel_manifest_versions` is the same function
    # the CLI calls; calling it here ensures the cold-build
    # path agrees with the explicit-stamper path.
    bcp.stamp_channel_manifest_versions(_REPO_ROOT)


def _stage_bundle() -> None:
    """Stage ``quality_playbook_cli/_bundle/`` from the QPB clone's
    source layout via ``bin/build_channel_package.stage()``. Run
    automatically before every wheel/sdist build so cold-build
    artifacts always contain the complete bundle."""
    bcp = _load_build_channel_package()
    # Stage into the canonical dest. bcp.stage() runs 090b's
    # _assert_mandatory_staged_members at the end and raises if
    # any load-time hard-dep member is missing — that guard is
    # the load-bearing "no empty bundles" pin.
    dest = _REPO_ROOT / "quality_playbook_cli" / "_bundle"
    bcp.stage(_REPO_ROOT, dest, clean=True)


def build_wheel(wheel_directory, config_settings=None,
                metadata_directory=None):  # type: ignore[no-redef]
    # v1.5.7 090e T5: stamp SKILL.md version BEFORE staging.
    # Order matters: the stamper rewrites pyproject.toml +
    # package.json on disk; setuptools reads pyproject.toml
    # when computing the wheel metadata. Stamp first, then
    # stage, then delegate to setuptools (which now sees the
    # stamped version).
    #
    # v1.5.7 090f: context-aware. Source-tree builds need
    # stamp+stage (the bundle might be stale). Sdist-unpack
    # builds (standard `python -m build` sdist→wheel) already
    # have a complete + stamped tree — and the dev machinery
    # isn't present — so skip stamp/stage and delegate
    # straight to setuptools.
    if _is_source_tree_build():
        _stamp_version()
        _stage_bundle()
    return _setuptools_backend.build_wheel(
        wheel_directory, config_settings, metadata_directory,
    )


def build_sdist(sdist_directory, config_settings=None):  # type: ignore[no-redef]
    # v1.5.7 090e T5: stamp before staging (see build_wheel
    # comment for ordering rationale).
    # v1.5.7 090f: same context-awareness — sdist-of-sdist is
    # nonsensical so this almost always runs from a source
    # tree, but the guard makes the backend uniform.
    if _is_source_tree_build():
        _stamp_version()
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
        # v1.5.7 090e T5: stamp before staging — editable
        # installs also produce metadata that pyproject.toml
        # drives.
        # v1.5.7 090f: context-aware (editable installs almost
        # always run from a source tree, but the guard makes
        # the backend uniform).
        if _is_source_tree_build():
            _stamp_version()
            _stage_bundle()
        return _setuptools_editable(
            wheel_directory, config_settings, metadata_directory,
        )
