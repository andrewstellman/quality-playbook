#!/usr/bin/env python3
"""bin/bootstrap_self_audit_docs.py — mirror docs_gathered/ → reference_docs/.

The QPB self-audit (running the playbook against the QPB repo root)
expects to find curated documentation at ``reference_docs/`` so Phase 1
can ingest it. The QPB-local ``docs_gathered/`` directory holds the
pre-curation source; ``reference_docs/`` is gitignored by policy
(per .gitignore: "Tier 4 context and citable material — Not tracked
in the skill's own repo so QPB's reference_docs/ stays a clean
scaffold folder").

Run once after a fresh clone (or any time the curated set changes):

    python3 -m bin.bootstrap_self_audit_docs

Idempotent: existing reference_docs/ files are overwritten with the
docs_gathered/ source. The reference_docs/cite/.gitkeep scaffolding
is preserved.

v1.5.6 BUG-007: pre-fix, the QPB direct-root reference_docs/ was empty
while the harness-installed bootstrap had the curated docs set. Phase 1
against the QPB repo root fell into code-only mode unnecessarily.
This helper closes the gap deterministically without changing the
no-track gitignore policy on reference_docs/.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "docs_gathered"
DEST_DIR = REPO_ROOT / "reference_docs"
PLAINTEXT_EXTENSIONS = {".md", ".txt"}
EXCLUDED_NAMES = {"README.md"}


def main() -> int:
    if not SOURCE_DIR.is_dir():
        print(f"ERROR: source directory missing: {SOURCE_DIR}", file=sys.stderr)
        print(
            "The QPB-local docs_gathered/ directory holds pre-curation "
            "documentation for the bootstrap self-audit. It is gitignored "
            "by policy and must be populated by the operator before this "
            "helper can mirror it.",
            file=sys.stderr,
        )
        return 1
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    dest_cite = DEST_DIR / "cite"
    dest_cite.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in sorted(SOURCE_DIR.iterdir()):
        if not src.is_file():
            continue
        if src.suffix.lower() not in PLAINTEXT_EXTENSIONS:
            continue
        if src.name in EXCLUDED_NAMES:
            continue
        shutil.copyfile(src, DEST_DIR / src.name)
        copied += 1

    source_cite = SOURCE_DIR / "cite"
    if source_cite.is_dir():
        for src in sorted(source_cite.iterdir()):
            if not src.is_file():
                continue
            if src.suffix.lower() not in PLAINTEXT_EXTENSIONS:
                continue
            if src.name in EXCLUDED_NAMES:
                continue
            shutil.copyfile(src, dest_cite / src.name)
            copied += 1

    print(f"event=mirror_complete source={SOURCE_DIR} dest={DEST_DIR} files_copied={copied}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
