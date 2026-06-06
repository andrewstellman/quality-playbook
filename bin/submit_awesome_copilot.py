"""bin/submit_awesome_copilot.py — generate the submission packet for the
github/awesome-copilot registry.

The awesome-copilot registry (https://github.com/github/awesome-copilot)
accepts community-contributed skills as PRs that add a folder under
``skills/<skill-name>/`` containing a ``SKILL.md`` with required
frontmatter plus optional bundled assets. The repo's own tooling
(``npm run skill:create`` / ``npm run skill:validate`` /
``npm run build``) is intended to run inside a clone of awesome-copilot,
not inside QPB.

For QPB we have a single Skill (``quality-playbook``) but it ships seven
support directories (``bin/``, ``references/``, ``phase_prompts/``,
``agents/``, ``quality_gate.py``, ``ai_context/`` slice, and so on) that
cannot be sensibly carried as in-repo assets without exceeding the
registry's typical-skill footprint. So this script:

1. Reads QPB's authoritative metadata from ``SKILL.md`` frontmatter +
   ``pyproject.toml``.
2. Generates a **submission packet** under
   ``dist/awesome_copilot_submission/`` containing:

   - ``skills/quality-playbook/SKILL.md`` — a TRIMMED variant suitable
     for the awesome-copilot collection (links back to the canonical
     QPB repo for the full toolkit instead of inlining 5MB+ of assets).
   - ``PR_BODY.md`` — markdown body the operator pastes into the PR.
   - ``MANUAL_STEPS.md`` — the operator's checklist for forking
     awesome-copilot, copying the skill folder in, running
     ``npm run skill:validate``, and opening the PR.

3. Does NOT call ``gh pr create`` or push to any remote. The operator
   reviews the generated packet and runs the manual fork-and-PR steps
   themselves. See ``ai_context/DEVELOPMENT_PROCESS.md`` ("awesome-copilot
   submission workflow") for the full operator-side workflow.

Pre-flight check: version-string parity (same check pip + npm publish
scripts use). If parity fails the script halts; the submitted SKILL.md
must match the published pip/npm version.

Cross-platform: pathlib + utf-8 read/write + no shell.

Usage::

    python3 bin/submit_awesome_copilot.py
    python3 bin/submit_awesome_copilot.py --dest /tmp/foo
    python3 bin/submit_awesome_copilot.py --help

Exit codes:

- 0   success
- 64  EX_USAGE — bad invocation
- 65  EX_DATAERR — pre-flight check failed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple


EX_OK = 0
EX_USAGE = 64
EX_DATAERR = 65

PACKAGE_NAME = "quality-playbook"
SKILL_NAME = "quality-playbook"
QPB_REPO_URL = "https://github.com/andrewstellman/quality-playbook"
AWESOME_COPILOT_REPO = "github/awesome-copilot"

_VERSION_RE_TOML = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
_VERSION_RE_JSON = re.compile(r'"version"\s*:\s*"([^"]+)"')
_VERSION_RE_PY = re.compile(r'__version__\s*=\s*"([^"]+)"')


def _read_version(path: Path, regex: re.Pattern) -> Optional[str]:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    m = regex.search(text)
    return m.group(1) if m else None


def check_version_parity(repo_root: Path) -> Tuple[bool, str, Optional[str]]:
    """Same parity check publish_pip + publish_npm use.

    Returns ``(ok, message, version)``.
    """
    py = _read_version(repo_root / "pyproject.toml", _VERSION_RE_TOML)
    pkg = _read_version(repo_root / "package.json", _VERSION_RE_JSON)
    init = _read_version(
        repo_root / "quality_playbook_cli" / "__init__.py",
        _VERSION_RE_PY,
    )
    report = (
        f"  pyproject.toml:                          {py}\n"
        f"  package.json:                            {pkg}\n"
        f"  quality_playbook_cli/__init__.py:        {init}"
    )
    if None in (py, pkg, init):
        return False, "Missing version string in one of the manifests:\n" + report, None
    if py == pkg == init:
        return True, f"Version parity OK at {py}.\n" + report, py
    return False, "Version-string MISMATCH:\n" + report, None


def read_skill_frontmatter(skill_md: Path) -> dict:
    """Parse the YAML-ish frontmatter block from SKILL.md.

    QPB's SKILL.md uses a simple ``---`` / ``---`` delimited block with
    ``key: value`` lines. We don't pull in PyYAML — this is a
    publish-script utility, not a runtime parser. We extract the four
    fields the awesome-copilot registry's skills schema requires
    (``name``, ``description``, ``license``) plus our author block.
    """
    if not skill_md.is_file():
        raise FileNotFoundError(f"SKILL.md not found at {skill_md}")
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("SKILL.md does not start with --- frontmatter delimiter")
    # Find the closing ---.
    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError("SKILL.md frontmatter has no closing ---")
    block = text[4:end]
    out: dict = {}
    for line in block.splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        # Trim matching quotes.
        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
            val = val[1:-1]
        out[key] = val
    return out


def generate_trimmed_skill_md(
    version: str,
    frontmatter: dict,
) -> str:
    """Render a SKILL.md suitable for the awesome-copilot ``skills/``
    directory.

    The trimmed version:

    - Keeps the ``name`` and ``description`` from the canonical
      SKILL.md (the registry's two required fields).
    - Adds ``license: MIT`` per the registry's frontmatter convention
      (QPB ships under Apache 2.0 + LICENSE.txt; we explicitly call
      out the Apache 2.0 license in the body and credit the LICENSE.txt
      in the QPB repo).
    - Adds a ``compatibility`` field per the registry pattern
      (cross-platform Python 3.8+, requires git).
    - Body links to the canonical QPB repo for the full toolkit.
    """
    name = frontmatter.get("name", SKILL_NAME)
    description = frontmatter.get("description", "")
    # Escape any literal double quotes the description may contain.
    description_safe = description.replace('"', '\\"')

    body = f"""---
name: {name}
description: "{description_safe}"
license: Apache-2.0
compatibility: "Cross-platform. Requires Python 3.8+ and git. Install via `pip install {PACKAGE_NAME}` or `npx {PACKAGE_NAME}`."
metadata:
  version: "{version}"
  author: Andrew Stellman
  upstream: {QPB_REPO_URL}
---

# Quality Playbook

Run a complete quality engineering audit on any codebase. Derives behavioral requirements from the code, generates spec-traced functional tests, runs a three-pass code review with regression tests, executes a multi-model spec audit (Council of Three), and produces a consolidated bug report with TDD-verified patches. Finds the 35% of real defects that structural code review alone cannot catch.

## Installation

This skill is distributed as a standalone toolkit because the full bundle
(seven phase-prompt directories, the citation verifier, the Council
runner, the bundled references, and the cross-platform install scripts)
exceeds the typical in-repo skill footprint. The canonical install is
one command:

```bash
pip install {PACKAGE_NAME}
# or
npx {PACKAGE_NAME}
```

After installation, run:

```bash
qpb install --into /path/to/your/repo
```

That copies the skill files (`SKILL.md`, `quality_gate.py`,
`references/`, `phase_prompts/`, `agents/`, `bin/citation_verifier.py`)
into the right place for your AI coding agent (Claude Code, Cursor,
GitHub Copilot CLI, etc.) — auto-detecting `.claude/`, `.github/`,
`.cursor/`, `.continue/`, `.codex/`, `.windsurf/`, `.cline/`, or
`.aider/`.

## What it does

When you (or your AI coding agent) say one of the trigger phrases —
"quality playbook", "spec audit", "Council of Three", "fitness-to-purpose",
or "coverage theater" — this skill drives the following workflow:

1. **Phase 1 (Explore)** — Documentation intake + three-stage codebase
   exploration. Writes `quality/EXPLORATION.md`.
2. **Phase 2 (Generate)** — Produces requirements, constitution,
   functional tests, code-review protocol, integration tests, spec-audit
   protocol, TDD protocol.
3. **Phase 3 (Code Review)** — Three-pass code review against HEAD;
   regression tests for every confirmed bug; patches.
4. **Phase 4 (Spec Audit)** — Three independent AI auditors review the
   code against requirements. Council-of-Three triage with verification
   probes. Layer-2 semantic citation check.
5. **Phase 5 (Consolidate)** — Combined bug report with TDD-verified
   patches.
6. **Phase 6 (Ship)** — Final ship-readiness verdict + AGENTS.md
   regeneration.

The trigger language is intentional: this is an opt-in heavy workflow
(it can take 30-90 minutes on a large codebase), not a always-on hook.

## License

Apache 2.0. Full terms in
[LICENSE.txt]({QPB_REPO_URL}/blob/main/LICENSE.txt) in the canonical
repository.

## Canonical source

This skill is maintained at {QPB_REPO_URL}. File issues and PRs there.
"""
    return body


def generate_pr_body(version: str, frontmatter: dict) -> str:
    description = frontmatter.get("description", "")
    return f"""# Add `{SKILL_NAME}` skill

This PR adds the **Quality Playbook** skill (v{version}) to the
`skills/` directory.

## What it is

{description}

## Distribution

The full Quality Playbook toolkit is published on pip + npm as
`{PACKAGE_NAME}` (v{version}). The `SKILL.md` added here gives users
a one-line install (`pip install {PACKAGE_NAME}` or
`npx {PACKAGE_NAME}`) plus the canonical `qpb install --into <repo>`
command, which copies the skill files into the adopter's AI-tool
skills directory (auto-detecting `.claude/`, `.github/`, `.cursor/`,
`.continue/`, `.codex/`, `.windsurf/`, `.cline/`, `.aider/`).

The skill ships seven support directories (references, phase prompts,
agents, citation verifier, Council runner, quality gate, AI context
slice) that together exceed the typical in-repo-skill footprint. So
the `SKILL.md` in this PR links back to {QPB_REPO_URL} as the canonical
source instead of inlining the assets.

## Verification

The maintainer can verify the skill by running:

```bash
pip install {PACKAGE_NAME}=={version}
qpb install --into ./test-target-repo
ls ./test-target-repo/.claude/skills/quality-playbook/   # or similar
```

Then in the target repo's AI agent, say "run the quality playbook"
and the skill activates.

## Checklist

- [x] `SKILL.md` frontmatter has `name`, `description`, and `license`.
- [x] `name` matches the folder name (`{SKILL_NAME}`).
- [x] `description` is clear and non-empty.
- [x] Canonical repo + license linked.
- [ ] `npm run skill:validate` run by maintainer in awesome-copilot
      clone after copying the folder in.
- [ ] `npm run build` run by maintainer to update generated README
      tables.

## Canonical source

Maintained at {QPB_REPO_URL}.
"""


def generate_manual_steps(version: str) -> str:
    return f"""# Manual steps to submit `{SKILL_NAME}` v{version} to awesome-copilot

This script (`bin/submit_awesome_copilot.py`) generates the submission
packet but does NOT push or open a PR. The awesome-copilot registry's
validators (`npm run skill:validate`, `npm run build`) need to run
inside a clone of {AWESOME_COPILOT_REPO}, not inside QPB. So the final
fork-and-PR is operator-side.

## Prerequisites

- `gh` CLI logged in to GitHub (`gh auth status` shows OK).
- A clone or fork of {AWESOME_COPILOT_REPO} somewhere on disk.
- Node.js + npm installed (for the registry's validators).

## Steps

1. **Fork awesome-copilot** (one-time):

   ```bash
   gh repo fork {AWESOME_COPILOT_REPO} --clone=true
   cd awesome-copilot
   npm install
   ```

2. **Pull main and create a branch**:

   ```bash
   cd /path/to/your/awesome-copilot-fork
   git fetch upstream main
   git checkout -b add-{SKILL_NAME}-{version} upstream/main
   ```

3. **Copy the generated skill folder in**:

   ```bash
   mkdir -p skills/{SKILL_NAME}
   cp <packet>/skills/{SKILL_NAME}/SKILL.md skills/{SKILL_NAME}/SKILL.md
   ```

   (`<packet>` is wherever this script wrote the submission — by
   default `dist/awesome_copilot_submission/` in the QPB repo.)

4. **Run the registry's validators**:

   ```bash
   npm run skill:validate
   npm run build
   ```

   If `skill:validate` complains about anything, edit
   `skills/{SKILL_NAME}/SKILL.md` and re-run. Do NOT edit any of the
   generated README tables by hand; `npm run build` updates them.

5. **Commit + push to your fork**:

   ```bash
   git add skills/{SKILL_NAME}/ docs/README.skills.md
   git commit -m "Add {SKILL_NAME} skill v{version}"
   git push -u origin add-{SKILL_NAME}-{version}
   ```

6. **Open the PR using the generated body**:

   ```bash
   gh pr create \\
     --repo {AWESOME_COPILOT_REPO} \\
     --title "Add {SKILL_NAME} skill v{version}" \\
     --body-file <packet>/PR_BODY.md
   ```

7. **Wait for the awesome-copilot review**. The maintainers may ask
   for changes to the SKILL.md trigger language, description length,
   or the install command. Iterate as needed.

## Re-running this script

Re-running `bin/submit_awesome_copilot.py` regenerates the packet from
the current QPB state. The version string is read live from
`pyproject.toml` + `package.json` + `quality_playbook_cli/__init__.py`
and parity-checked before the packet is generated. If those three
disagree the script halts; the submitted SKILL.md must match the
version published on pip + npm.
"""


def write_packet(
    dest: Path,
    version: str,
    frontmatter: dict,
) -> None:
    skill_dir = dest / "skills" / SKILL_NAME
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        generate_trimmed_skill_md(version, frontmatter),
        encoding="utf-8",
    )
    (dest / "PR_BODY.md").write_text(
        generate_pr_body(version, frontmatter),
        encoding="utf-8",
    )
    (dest / "MANUAL_STEPS.md").write_text(
        generate_manual_steps(version),
        encoding="utf-8",
    )
    # A small machine-readable index for tooling / tests.
    (dest / "submission.json").write_text(
        json.dumps(
            {
                "registry": AWESOME_COPILOT_REPO,
                "skill_name": SKILL_NAME,
                "package_name": PACKAGE_NAME,
                "version": version,
                "upstream": QPB_REPO_URL,
                "generated_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ),
                "files": {
                    "skill_md": f"skills/{SKILL_NAME}/SKILL.md",
                    "pr_body": "PR_BODY.md",
                    "manual_steps": "MANUAL_STEPS.md",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="submit_awesome_copilot",
        description=(
            "Generate the submission packet for the github/awesome-copilot "
            "registry. Reads QPB's SKILL.md frontmatter + version-string "
            "manifests, writes a packet under "
            "dist/awesome_copilot_submission/ that the operator then forks, "
            "validates, and PRs by hand. See ai_context/DEVELOPMENT_PROCESS.md "
            "(awesome-copilot submission workflow) for the operator-side "
            "details."
        ),
    )
    p.add_argument(
        "--dest",
        default=None,
        help=(
            "Destination directory for the packet "
            "(default: <repo>/dist/awesome_copilot_submission)."
        ),
    )
    return p.parse_args(argv)


def _print_intro() -> None:
    """v1.5.7 089x — self-describing no-args output. Pinned by
    ``test_scripts_self_describing_089x.py``. NO files are
    created on the no-args path — packet generation only fires
    when the operator passes a real argv (including the empty
    ``--dest <X>`` form which is still a non-empty argv)."""
    try:
        from bin._purpose import print_command_intro as _print_command_intro
    except ImportError:
        from _purpose import print_command_intro as _print_command_intro  # type: ignore[no-redef]
    _print_command_intro(
        name="submit_awesome_copilot",
        summary=(
            "Generate the awesome-copilot submission packet. Reads "
            "QPB's SKILL.md frontmatter + the three version manifests "
            "(pyproject.toml, package.json, __init__.py), writes a "
            "trimmed skills/quality-playbook/SKILL.md + PR body + "
            "manual fork-and-PR steps under "
            "dist/awesome_copilot_submission/."
        ),
        role=(
            "Run by the operator at v1.5.x ship time AFTER publish_pip "
            "+ publish_npm succeed. The script does NOT push or open a "
            "PR; the operator follows MANUAL_STEPS.md in the generated "
            "packet to fork github/awesome-copilot, copy the skill "
            "folder in, run `npm run skill:validate`, and `gh pr create`."
        ),
        usage_hint="python3 bin/submit_awesome_copilot.py --dest /tmp/foo",
    )


def main(argv: Optional[list[str]] = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list:
        _print_intro()
        return 0
    args = parse_args(argv_list)
    repo_root = Path(__file__).resolve().parent.parent

    print("Pre-flight: version-string parity...")
    ok, msg, version = check_version_parity(repo_root)
    print(msg)
    if not ok:
        return EX_DATAERR

    skill_md = repo_root / "SKILL.md"
    try:
        frontmatter = read_skill_frontmatter(skill_md)
    except (FileNotFoundError, ValueError) as e:
        print(f"Could not read SKILL.md frontmatter: {e}")
        return EX_DATAERR

    if args.dest:
        dest = Path(args.dest).resolve()
    else:
        dest = repo_root / "dist" / "awesome_copilot_submission"
    dest.mkdir(parents=True, exist_ok=True)

    write_packet(dest, version, frontmatter)

    print(f"\nSubmission packet generated at: {dest}")
    print(f"  - skills/{SKILL_NAME}/SKILL.md")
    print("  - PR_BODY.md")
    print("  - MANUAL_STEPS.md")
    print("  - submission.json")
    print(
        f"\nNext: follow MANUAL_STEPS.md to fork {AWESOME_COPILOT_REPO}, "
        "copy the skill folder in, run `npm run skill:validate`, and "
        "open the PR."
    )
    return EX_OK


if __name__ == "__main__":
    sys.exit(main())
