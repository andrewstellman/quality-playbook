#!/usr/bin/env python3
"""Quality Playbook gate script entry point — QPB-clone shadow.

The canonical gate script lives at
``.github/skills/quality_gate/quality_gate.py`` inside the
``quality_gate/`` Python package so its 232-test unit-test suite under
``.github/skills/quality_gate/tests/`` can be discovered as a regular
package. Adopters do NOT see this layout — ``bin/install_skill.py``
copies the canonical script directly to ``<install_root>/quality_gate.py``
(parallel to ``SKILL.md``) at install time.

In the QPB clone itself, this shim provides the parallel
``.github/skills/quality_gate.py`` entry point that adopter-facing
documentation refers to (SKILL.md Phase 5/6 prose, the
``python3 .github/skills/quality_gate.py .`` invocation example in
README and TOOLKIT, and self-bootstrap Phase 6 runs against the QPB
clone). Without this shim the ``.github/skills/quality_gate.py`` path
exists as a 28-byte text stub (the previous symlink that never
materialized on filesystems with ``core.symlinks=false``) and
self-bootstrap Phase 6 fails trying to execute it as Python.

The shim adds the package's directory to ``sys.path`` so
``import quality_gate`` resolves to the module at
``.github/skills/quality_gate/quality_gate.py`` (NOT a circular
self-import — the package directory contains a ``quality_gate.py``
module, and ``sys.path[0] = .../quality_gate/`` makes that module
importable as a top-level name without going through the package's
``__init__.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PACKAGE_DIR = _HERE / "quality_gate"

if not _PACKAGE_DIR.is_dir():
    print(
        f"ERROR: cannot locate quality_gate package directory at {_PACKAGE_DIR}. "
        f"This shim expects to live at .github/skills/quality_gate.py inside "
        f"the QPB clone, with the canonical script at "
        f".github/skills/quality_gate/quality_gate.py. If you are running an "
        f"adopter-installed copy of quality_gate.py, this shim should not be "
        f"present — bin/install_skill.py installs the real script directly, "
        f"not this shim.",
        file=sys.stderr,
    )
    sys.exit(2)

sys.path.insert(0, str(_PACKAGE_DIR))

import quality_gate  # noqa: E402

if __name__ == "__main__":
    sys.exit(quality_gate.main())
