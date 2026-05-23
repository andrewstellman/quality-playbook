"""v1.5.7 089v — ``python -m quality_playbook_cli`` entry.

The 089u pip channel only needed the ``quality-playbook`` console
script (wired by setuptools through ``[project.scripts]`` in
``pyproject.toml``). The 089v npm channel spawns the same Python
entry as ``python -m quality_playbook_cli`` (via the Node shim
``bin/quality-playbook.js``) — and ``python -m <pkg>`` requires a
``__main__.py`` adjacent to ``__init__.py``. This file is that
bridge.

It is intentionally trivial: forward sys.argv[1:] to
``quality_playbook_cli.main()`` and propagate the return code as
the process exit status. No verb parsing, no argv mutation — the
single routing brain in ``__init__.main()`` stays the canonical
dispatcher.
"""

import sys

from . import main


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
