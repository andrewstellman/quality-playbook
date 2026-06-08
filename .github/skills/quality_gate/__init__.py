"""Quality Playbook gate script — legacy package entry point.

v1.5.8 instructions 208 + 209 moved quality_gate.py from this
directory to its current canonical location at
``plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py``
(standard self-hosted marketplace layout). The tests/ subtree
stays here for now (fixture/test inventory keeps git history; the
tests' own import paths were updated to find the script at its
new location).

Re-export the script's public names by loading it from the new
canonical location so any callers still doing
``from .github.skills.quality_gate import …`` continue resolving.
"""
from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path

_REPO_ROOT = _Path(__file__).resolve().parents[3]
_CANONICAL_209 = (
    _REPO_ROOT / "plugins" / "quality-playbook"
    / "skills" / "quality-playbook" / "scripts" / "quality_gate.py"
)
_CANONICAL_208 = (
    _REPO_ROOT / "skills" / "quality-playbook" / "scripts" / "quality_gate.py"
)
if _CANONICAL_209.is_file():
    _CANONICAL = _CANONICAL_209
else:
    _CANONICAL = _CANONICAL_208
if _CANONICAL.is_file():
    _spec = _ilu.spec_from_file_location(
        "_qpb_quality_gate_via_legacy_pkg", _CANONICAL
    )
    if _spec is not None and _spec.loader is not None:
        _mod = _ilu.module_from_spec(_spec)
        _sys.modules[_spec.name] = _mod
        _spec.loader.exec_module(_mod)
        # Re-export public names (``*``-style) into this package
        # namespace so legacy callers get the same surface.
        for _name in dir(_mod):
            if not _name.startswith("_"):
                globals()[_name] = getattr(_mod, _name)
