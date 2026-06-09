"""bin/qpb_heartbeat.py — v1.5.9 instruction 210 thin shim.

The canonical qpb_heartbeat.py lives at
``plugins/quality-playbook/skills/quality-playbook/scripts/qpb_heartbeat.py``
per the standard self-hosted marketplace layout (post-209). This
thin shim preserves the ``python3 -m bin.qpb_heartbeat`` invocation
the QPB worker SKILL.md "Heartbeat emission contract" section and
the per-phase heartbeat call-outs reference.

Implementation mirrors ``bin/install_skill.py`` post-209: load the
canonical script by file path (NOT a
``from plugins.quality_playbook... import qpb_heartbeat`` import —
the hyphen in ``quality-playbook`` makes the directory name invalid
as a Python module identifier). Re-export ``main`` so the
historical entry point keeps working.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CANONICAL = (
    _REPO_ROOT / "plugins" / "quality-playbook"
    / "skills" / "quality-playbook" / "scripts" / "qpb_heartbeat.py"
)

if not _CANONICAL.is_file():
    raise RuntimeError(
        f"bin/qpb_heartbeat.py shim: canonical script missing at "
        f"{_CANONICAL} (post-209 standard self-hosted marketplace "
        f"layout). The clone appears partial."
    )

_spec = importlib.util.spec_from_file_location(
    "_qpb_heartbeat_canonical", _CANONICAL
)
if _spec is None or _spec.loader is None:
    raise RuntimeError(
        f"bin/qpb_heartbeat.py shim: could not build importlib spec "
        f"for {_CANONICAL}."
    )
_impl = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _impl
_spec.loader.exec_module(_impl)

main = _impl.main
# Re-export every public name so callers that do
# ``from bin import qpb_heartbeat`` + ``qpb_heartbeat.<helper>`` keep
# working. Skip dunders (module machinery).
for _name in dir(_impl):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_impl, _name)

if __name__ == "__main__":
    sys.exit(_impl.main())
