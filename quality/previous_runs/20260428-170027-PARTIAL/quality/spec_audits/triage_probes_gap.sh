#!/bin/bash
set -euo pipefail

grep -q '`SKILL.md`' agents/quality-playbook.agent.md || {
  echo "BUG-017 probe: repo-root SKILL.md absent from general orchestrator"
}

grep -q 'Run Phase 1 in the current session.' agents/quality-playbook.agent.md && \
grep -q 'You do NOT execute phase logic yourself.' agents/quality-playbook.agent.md && {
  echo "BUG-018 probe: general orchestrator contains both contradictory ownership statements"
}

python3 - <<'PY'
from pathlib import Path
source = Path("pytest/__main__.py").read_text(encoding="utf-8")
assert "TextTestRunner" in source
assert "--collect-only" not in source
assert "::" not in source
print("BUG-019 probe: shim lacks explicit collect-only and node-id handling")
PY
