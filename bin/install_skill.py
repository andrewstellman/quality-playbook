"""bin/install_skill.py — v1.5.8 instruction 208 thin shim.

The canonical install_skill.py lives at
``skills/quality-playbook/scripts/install_skill.py`` after the
plugin-native restructure (208). This thin shim preserves the
historical ``python3 -m bin.install_skill`` invocation for the QPB
clone-based install path so README docs / test commands /
``bin/run_playbook.py`` / ``bin/publish_pip.py`` /
``bin/publish_npm.py`` keep working without churn.

Implementation: load the canonical script by file path (NOT a
``from skills.quality_playbook.scripts import install_skill``
``import`` — the hyphen in ``quality-playbook`` makes the directory
name invalid as a Python module identifier). Re-export ``main``
and ``install`` so the historical entry points keep working.

The shipped pip wheel + npm tarball still get ``install_skill.py``
at ``_bundle/bin/install_skill.py`` (the flat bundle layout) via
``bin/build_channel_package.py``; the shim is only used at the
dev-time ``python3 -m bin.install_skill`` invocation against the
QPB clone.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = (
    Path(__file__).resolve().parent.parent
    / "skills" / "quality-playbook" / "scripts" / "install_skill.py"
)

if not _CANONICAL.is_file():
    raise RuntimeError(
        f"bin/install_skill.py shim: canonical script missing at "
        f"{_CANONICAL}. The plugin-native repo restructure "
        f"(v1.5.8 instruction 208) expects the install script at "
        f"this location; the clone appears partial."
    )

_spec = importlib.util.spec_from_file_location(
    "_qpb_install_skill_canonical", _CANONICAL
)
if _spec is None or _spec.loader is None:
    raise RuntimeError(
        f"bin/install_skill.py shim: could not build importlib "
        f"spec for {_CANONICAL}."
    )
_impl = importlib.util.module_from_spec(_spec)
# Register in sys.modules so any internal dataclass/typing
# machinery in the canonical script resolves against itself.
sys.modules[_spec.name] = _impl
_spec.loader.exec_module(_impl)

# Re-export the public entry points so callers that do
# ``from bin.install_skill import main`` or ``... import install``
# keep working post-208.
main = _impl.main
install = _impl.install
# Re-export EVERY name from the canonical module so callers that
# did ``from bin import install_skill`` + ``install_skill.<any>``
# keep working — including the underscore-prefixed banner
# constants the 089j drift-guard test reads
# (``_BANNER_NAME`` / ``_BANNER_URL`` / etc.) and the private
# helpers build_channel_package + tests reach into
# (``_bundle_files``, ``_bundle_files_soft``,
# ``_resolve_bundle_source_root``, ``_scripts_dirname``).
# Skip dunder-style names (``__builtins__`` etc.) which are
# module-machinery, not data the shim should masquerade as.
for _name in dir(_impl):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_impl, _name)

if __name__ == "__main__":
    sys.exit(_impl.main())
