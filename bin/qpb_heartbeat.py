"""bin/qpb_heartbeat.py — v1.5.9 Phase 1B thin shim.

The canonical qpb_heartbeat.py lives at
``plugins/quality-playbook/skills/quality-playbook/scripts/qpb_heartbeat.py``
(the standard self-hosted marketplace layout). This thin shim preserves
the ``python3 -m bin.qpb_heartbeat`` / ``python3 <clone>/bin/qpb_heartbeat.py``
invocation the QPB worker SKILL.md "Heartbeat emission" section references,
without churning callers. Mirrors the bin/install_skill.py shim: load the
canonical script by file path (a ``from plugins...import`` is impossible —
the hyphen in ``quality-playbook`` is not a valid Python identifier) and
re-export its public names.

In an adopter install the BUNDLED copy ships at
``<install>/bin/qpb_heartbeat.py`` (the canonical script itself, copied by
install_skill._bundle_files) — this repo-root shim is only the QPB-clone
dev entry point.
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
        f"{_CANONICAL}. The clone appears partial.")

_spec = importlib.util.spec_from_file_location(
    "_qpb_heartbeat_canonical", _CANONICAL)
if _spec is None or _spec.loader is None:
    raise RuntimeError(
        f"bin/qpb_heartbeat.py shim: could not build importlib spec for "
        f"{_CANONICAL}.")
_impl = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _impl
_spec.loader.exec_module(_impl)

main = _impl.main
for _name in dir(_impl):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_impl, _name)

if __name__ == "__main__":
    sys.exit(_impl.main())
