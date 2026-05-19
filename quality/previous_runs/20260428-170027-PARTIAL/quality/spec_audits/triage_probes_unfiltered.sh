#!/bin/bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path
source = Path("bin/run_playbook.py").read_text(encoding="utf-8")
assert "docs_gathered/ is missing or empty" in source
assert "proceeding with code-only analysis" not in source
assert "Read the quality playbook skill at .github/skills/SKILL.md" in source
assert "exit_code = run_prompt" not in source
gate = Path(".github/skills/quality_gate/quality_gate.py").read_text(encoding="utf-8")
assert '"repos"' not in gate.split("excluded =", 1)[1].split("}", 1)[0]
PY
