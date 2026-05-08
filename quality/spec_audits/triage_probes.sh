#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path
import re

skill = Path("SKILL.md").read_text(encoding="utf-8")
runtime = Path("bin/run_playbook.py").read_text(encoding="utf-8")
helper = Path("bin/benchmark_lib.py").read_text(encoding="utf-8")

section_match = re.search(
    r"### Locating reference files\n\n(.*?)(?:\n## |\Z)",
    skill,
    re.S,
)
assert section_match, "Root SKILL.md must contain the 'Locating reference files' section"
section = section_match.group(1)

section_items = re.findall(r"^\d+\.\s+`([^`]+)`", section, re.M)
assert section_items == [
    "references/",
    ".claude/skills/quality-playbook/references/",
    ".github/skills/references/",
    ".github/skills/quality-playbook/references/",
], f"Unexpected root SKILL.md fallback list: {section_items!r}"

assert ".cursor/skills/quality-playbook/SKILL.md" in runtime
assert ".continue/skills/quality-playbook/SKILL.md" in runtime
assert ".cursor/skills/quality-playbook/SKILL.md" in helper
assert ".continue/skills/quality-playbook/SKILL.md" in helper

assert ".cursor/skills/quality-playbook/references/" not in section
assert ".continue/skills/quality-playbook/references/" not in section

print("Claim: root SKILL.md documents only four reference fallback locations.")
print(f"Actual section entries: {section_items}")
print("Result: CLAIM IS TRUE")
print("Claim: runtime/helper surfaces already support Cursor and Continue installs.")
print("Actual runtime support: .cursor and .continue paths are present in bin/run_playbook.py and bin/benchmark_lib.py")
print("Result: CLAIM IS TRUE")
PY
