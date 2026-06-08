"""bin/submit_awesome_copilot.py — generate + (optionally) automate the
submission to the github/awesome-copilot registry.

The awesome-copilot registry (https://github.com/github/awesome-copilot)
accepts community-contributed skills as PRs that add a folder under
``skills/<skill-name>/`` containing a ``SKILL.md`` with required
frontmatter plus optional bundled assets. The repo's own tooling
(``npm run skill:create`` / ``npm run skill:validate`` / ``npm start``)
is intended to run inside a clone of awesome-copilot, not inside QPB.

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
     ``npm start``, and opening the PR.

3. In ``--submit`` mode: automates steps 1-6 of MANUAL_STEPS.md
   (fork+clone, upstream remote+fetch, branch, copy SKILL.md, run
   ``npm start``, commit+push, open PR) with explicit confirmation
   gates before every destructive action. Only step 7 (wait for
   maintainer review) is external.

Pre-flight check: version-string parity (same check pip + npm publish
scripts use). If parity fails the script halts; the submitted SKILL.md
must match the published pip/npm version.

Cross-platform: pathlib + utf-8 read/write + list-form subprocess args
+ no ``shell=True``.

Usage::

    python3 bin/submit_awesome_copilot.py                # show intro
    python3 bin/submit_awesome_copilot.py --dry-run      # generate packet only
    python3 bin/submit_awesome_copilot.py --submit       # packet + fork + push + PR
    python3 bin/submit_awesome_copilot.py --help         # full flag reference

``--dry-run`` and ``--submit`` are mutually exclusive; one must be
passed to run the workflow. ``--submit`` automates all 6 mechanical
steps of MANUAL_STEPS.md with confirmation prompts before any
destructive action (push to fork, opening the PR). Only step 7 — wait
for maintainer review — is external.

Exit codes:

- 0   success
- 64  EX_USAGE — bad invocation
- 65  EX_DATAERR — pre-flight check failed
- 70  EX_SOFTWARE — subprocess failure during automated submission
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple


EX_OK = 0
EX_USAGE = 64
EX_DATAERR = 65
EX_SOFTWARE = 70

PACKAGE_NAME = "quality-playbook"
SKILL_NAME = "quality-playbook"
QPB_REPO_URL = "https://github.com/andrewstellman/quality-playbook"
AWESOME_COPILOT_REPO = "github/awesome-copilot"
AWESOME_COPILOT_HTTPS = "https://github.com/github/awesome-copilot.git"
DEFAULT_FORK_PATH = Path.home() / "Documents" / "awesome-copilot-fork"

_VERSION_RE_TOML = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
_VERSION_RE_JSON = re.compile(r'"version"\s*:\s*"([^"]+)"')
_VERSION_RE_PY = re.compile(r'__version__\s*=\s*"([^"]+)"')


# ---------------------------------------------------------------------------
# Version + frontmatter helpers (unchanged from pre-206).
# ---------------------------------------------------------------------------


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
        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
            val = val[1:-1]
        out[key] = val
    return out


# ---------------------------------------------------------------------------
# Packet generation (unchanged structure; MANUAL_STEPS gains a header note).
# ---------------------------------------------------------------------------


def generate_trimmed_skill_md(
    version: str,
    frontmatter: dict,
) -> str:
    """Render a SKILL.md suitable for the awesome-copilot ``skills/``
    directory."""
    name = frontmatter.get("name", SKILL_NAME)
    description = frontmatter.get("description", "")
    description_safe = description.replace('"', '\\"')

    body = f"""---
name: {name}
description: "{description_safe}"
license: Apache-2.0
compatibility: "Cross-platform. Requires Python 3.10+ and git. Install via `pip install {PACKAGE_NAME}` or `npx {PACKAGE_NAME} install --into <repo> --ai-tool <tool>`."
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
npx {PACKAGE_NAME} install --into <repo> --ai-tool <tool>
```

After installation, run:

```bash
quality-playbook install --into /path/to/your/repo --ai-tool <tool>
```

`<tool>` is one of: `claude`, `cursor`, `copilot`, `continue`, `codex`,
`windsurf`, `cline`, `aider`. The installer copies the skill files
(`SKILL.md`, `quality_gate.py`, `references/`, `phase_prompts/`,
`agents/`, `bin/citation_verifier.py`) into the right place for your
AI coding agent (Claude Code, Cursor, GitHub Copilot CLI, etc.) —
auto-detecting `.claude/`, `.github/`, `.cursor/`, `.continue/`,
`.codex/`, `.windsurf/`, `.cline/`, or `.aider/`.

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
5. **Phase 5 (Reconcile)** — Combined bug report with TDD-verified
   patches.
6. **Phase 6 (Verify)** — Final ship-readiness verdict + AGENTS.md
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
`npx {PACKAGE_NAME} install --into <repo> --ai-tool <tool>`) plus
the canonical `quality-playbook install --into <repo> --ai-tool <tool>`
command, which copies the skill files into the adopter's AI-tool
skills directory (auto-detecting `.claude/`, `.github/`, `.cursor/`,
`.continue/`, `.codex/`, `.windsurf/`, `.cline/`, `.aider/`).

The skill ships five support directories (`references/`,
`phase_prompts/`, `agents/`, `bin/`, `ai_context/`) plus `SKILL.md`
and `quality_gate.py`. The full bundle is ~64 files (132KB SKILL.md
alone) which exceeds the typical in-repo-skill footprint. So the
`SKILL.md` in this PR links back to {QPB_REPO_URL} as the canonical
source instead of inlining the assets.

## Verification

The maintainer can verify the skill by running:

```bash
pip install {PACKAGE_NAME}=={version}
quality-playbook install --into ./test-target-repo --ai-tool claude
ls ./test-target-repo/.claude/skills/quality-playbook/   # or similar
```

Then in the target repo's AI agent, say "run the quality playbook"
and the skill activates.

## Checklist (per `github/awesome-copilot` CONTRIBUTING.md)

- [x] I have read `CONTRIBUTING.md` and followed the submission
      guidelines.
- [x] This PR targets the `staged` branch (not `main`).
- [x] Contribution type: **new skill** (adds `skills/{SKILL_NAME}/`).
- [x] `SKILL.md` frontmatter has `name`, `description`, and `license`.
- [x] `name` matches the folder name (`{SKILL_NAME}`).
- [x] `description` is clear and non-empty.
- [x] `npm start` run locally — `skill:validate` passes and
      top-level `README.md` regenerated; both staged in this PR.
- [x] Canonical repo + license linked.

## License note for maintainers

The Quality Playbook toolkit ships under **Apache 2.0** (see
`LICENSE.txt` in the canonical repo). The frontmatter `license:` field
in this PR's `SKILL.md` is set to `Apache-2.0`. If the registry
requires `license: MIT` for all skill entries, please flag and we will
re-evaluate licensing options with the QPB maintainers.

## Canonical source

Maintained at {QPB_REPO_URL}.
"""


def generate_manual_steps(version: str) -> str:
    return f"""# Manual steps to submit `{SKILL_NAME}` v{version} to awesome-copilot

> **Or run `python3 bin/submit_awesome_copilot.py --submit` to automate
> steps 1-6 below (the script prompts for confirmation before every
> destructive action — push, PR-create — and halts cleanly on any
> failure). Only step 7 (wait for maintainer review) is external.**

This script (`bin/submit_awesome_copilot.py`) generates the submission
packet but does NOT push or open a PR by default. The awesome-copilot
registry's validators (`npm start`) need to run inside a clone of
{AWESOME_COPILOT_REPO}, not inside QPB. So the final fork-and-PR is
operator-side unless you pass `--submit`.

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

2. **Pull `staged` and create a branch** (the registry's CONTRIBUTING.md
   warns that PRs targeting `main` "may be outright rejected" — branch
   from and target `staged`):

   ```bash
   cd /path/to/your/awesome-copilot-fork
   git fetch upstream staged
   git checkout -b add-{SKILL_NAME}-{version} upstream/staged
   ```

3. **Copy the generated skill folder in**:

   ```bash
   mkdir -p skills/{SKILL_NAME}
   cp <packet>/skills/{SKILL_NAME}/SKILL.md skills/{SKILL_NAME}/SKILL.md
   ```

   (`<packet>` is wherever this script wrote the submission — by
   default `dist/awesome_copilot_submission/` in the QPB repo.)

4. **Run the registry's pre-submit command**:

   ```bash
   npm start
   ```

   This is the canonical command in CONTRIBUTING.md — it runs
   `skill:validate` + regenerates the top-level `README.md`.
   If validation complains, edit `skills/{SKILL_NAME}/SKILL.md` and
   re-run. Do NOT edit the generated `README.md` table by hand;
   `npm start` updates it. The npm-run targets `npm run skill:validate`
   and `npm run build` are wrapped by `npm start`.

5. **Commit + push to your fork** (note: top-level `README.md` is what
   `npm start` regenerates — not `docs/README.skills.md`):

   ```bash
   git add skills/{SKILL_NAME}/ README.md
   git commit -m "Add {SKILL_NAME} skill v{version}"
   git push -u origin add-{SKILL_NAME}-{version}
   ```

6. **Open the PR using the generated body** (target `staged`, not
   `main`):

   ```bash
   gh pr create \\
     --repo {AWESOME_COPILOT_REPO} \\
     --base staged \\
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


# ---------------------------------------------------------------------------
# Logging helpers (mirrors publish_pip/publish_npm conventions).
# ---------------------------------------------------------------------------


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _log_dir() -> Path:
    return Path.home() / ".qpb" / "submit_logs"


def _open_log(version: str):
    d = _log_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"awesome_copilot_{version}_{_utc_stamp()}.log"
    return p, p.open("w", encoding="utf-8")


def _log(log_fh, msg: str) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"[{ts}] {msg}"
    print(line)
    log_fh.write(line + "\n")
    log_fh.flush()


def _run(
    args: list,
    *,
    cwd: Optional[Path] = None,
    check: bool = False,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """List-form subprocess, utf-8 decoded, no shell. cross-platform."""
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        encoding="utf-8",
        errors="replace",
    )


def _log_subprocess(log_fh, label: str, r: subprocess.CompletedProcess) -> None:
    log_fh.write(f"--- {label} (rc={r.returncode}) stdout ---\n")
    log_fh.write(r.stdout or "")
    log_fh.write(f"--- {label} stderr ---\n")
    log_fh.write(r.stderr or "")
    log_fh.write("--- end ---\n")
    log_fh.flush()


def _confirm(prompt: str) -> bool:
    """y/N confirmation prompt. EOF/empty/anything-not-y returns False."""
    try:
        ans = input(prompt).strip().lower()
    except EOFError:
        return False
    return ans == "y"


# ---------------------------------------------------------------------------
# Automated submission steps (only invoked under --submit).
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def step1_verify_or_create_fork(
    fork_path: Path,
    log_fh,
) -> Tuple[bool, str]:
    """Step 1: ensure fork-path is a usable awesome-copilot clone.

    Idempotent: if the path already exists + contains ``.git/`` and a
    ``package.json``, we skip the fork action.
    """
    if fork_path.is_dir() and (fork_path / ".git").exists():
        _log(log_fh, f"Step 1: fork path exists at {fork_path} with .git/ — skipping gh fork.")
        if not (fork_path / "package.json").is_file():
            return False, (
                f"Step 1: {fork_path} has .git/ but no package.json — "
                "doesn't look like awesome-copilot. Halt for operator inspection."
            )
        node_modules = fork_path / "node_modules"
        if not node_modules.is_dir():
            _log(log_fh, "Step 1: node_modules missing — running `npm install`...")
            r = _run(["npm", "install"], cwd=fork_path)
            _log_subprocess(log_fh, "npm install", r)
            if r.returncode != 0:
                return False, (
                    f"Step 1: `npm install` failed (exit {r.returncode}). "
                    f"Tail of stderr:\n{(r.stderr or '')[-1500:]}"
                )
        return True, f"Step 1: fork ready at {fork_path}."

    # Fork-path absent (or no .git): need to create the fork.
    _log(log_fh, "Step 1: checking gh auth status...")
    auth = _run(["gh", "auth", "status"])
    _log_subprocess(log_fh, "gh auth status", auth)
    if auth.returncode != 0:
        return False, (
            "Step 1: `gh auth status` reports not authenticated. "
            "Run `gh auth login` first and re-run --submit."
        )

    parent = fork_path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)

    _log(
        log_fh,
        f"Step 1: cloning fork to {fork_path} via "
        f"`gh repo fork {AWESOME_COPILOT_REPO} --clone=true --remote-name origin`...",
    )
    r = _run(
        [
            "gh", "repo", "fork", AWESOME_COPILOT_REPO,
            "--clone=true",
            "--remote-name", "origin",
            "--", str(fork_path),
        ],
        cwd=parent,
    )
    _log_subprocess(log_fh, "gh repo fork", r)
    if r.returncode != 0:
        return False, (
            f"Step 1: `gh repo fork` failed (exit {r.returncode}). "
            f"Tail of stderr:\n{(r.stderr or '')[-1500:]}"
        )
    if not (fork_path / ".git").exists() or not (fork_path / "package.json").is_file():
        return False, (
            f"Step 1: post-clone verification failed — {fork_path} missing "
            ".git/ or package.json."
        )
    _log(log_fh, "Step 1: running `npm install` in fresh fork...")
    r2 = _run(["npm", "install"], cwd=fork_path)
    _log_subprocess(log_fh, "npm install", r2)
    if r2.returncode != 0:
        return False, (
            f"Step 1: `npm install` failed (exit {r2.returncode}). "
            f"Tail of stderr:\n{(r2.stderr or '')[-1500:]}"
        )
    return True, f"Step 1: fork created and ready at {fork_path}."


def step2_setup_upstream_and_fetch(
    fork_path: Path,
    log_fh,
) -> Tuple[bool, str]:
    """Step 2: ensure upstream remote points at github/awesome-copilot,
    then ``git fetch upstream staged``."""
    r = _run(["git", "remote", "get-url", "upstream"], cwd=fork_path)
    _log_subprocess(log_fh, "git remote get-url upstream", r)
    if r.returncode == 0:
        current = (r.stdout or "").strip()
        if "github/awesome-copilot" not in current and "github.com/github/awesome-copilot" not in current:
            ok = _confirm(
                f"upstream points at {current!r}, not "
                f"github/awesome-copilot. Reset upstream to "
                f"{AWESOME_COPILOT_HTTPS}? [y/N] "
            )
            if not ok:
                return False, (
                    f"Step 2: upstream points elsewhere ({current!r}) "
                    "and operator declined to reset. Halt."
                )
            r2 = _run(
                ["git", "remote", "set-url", "upstream", AWESOME_COPILOT_HTTPS],
                cwd=fork_path,
            )
            _log_subprocess(log_fh, "git remote set-url upstream", r2)
            if r2.returncode != 0:
                return False, (
                    f"Step 2: `git remote set-url upstream` failed "
                    f"(exit {r2.returncode})."
                )
    else:
        _log(log_fh, "Step 2: upstream remote missing — adding...")
        r3 = _run(
            ["git", "remote", "add", "upstream", AWESOME_COPILOT_HTTPS],
            cwd=fork_path,
        )
        _log_subprocess(log_fh, "git remote add upstream", r3)
        if r3.returncode != 0:
            return False, (
                f"Step 2: `git remote add upstream` failed "
                f"(exit {r3.returncode}). stderr:\n{(r3.stderr or '')[-1500:]}"
            )

    _log(log_fh, "Step 2: `git fetch upstream staged`...")
    rf = _run(["git", "fetch", "upstream", "staged"], cwd=fork_path)
    _log_subprocess(log_fh, "git fetch upstream staged", rf)
    if rf.returncode != 0:
        return False, (
            f"Step 2: `git fetch upstream staged` failed "
            f"(exit {rf.returncode}). stderr:\n{(rf.stderr or '')[-1500:]}"
        )
    return True, "Step 2: upstream configured and staged fetched."


def step3_create_or_reuse_branch(
    fork_path: Path,
    branch: str,
    log_fh,
) -> Tuple[bool, str]:
    """Step 3: create ``add-quality-playbook-<version>`` branch from
    upstream/staged, or reuse an existing matching branch."""
    r_exist = _run(
        ["git", "rev-parse", "--verify", f"refs/heads/{branch}"],
        cwd=fork_path,
    )
    branch_exists = r_exist.returncode == 0

    r_upstream = _run(
        ["git", "rev-parse", "upstream/staged"],
        cwd=fork_path,
    )
    if r_upstream.returncode != 0:
        return False, (
            f"Step 3: could not rev-parse upstream/staged "
            f"(exit {r_upstream.returncode})."
        )
    upstream_sha = (r_upstream.stdout or "").strip()

    if branch_exists:
        r_br = _run(["git", "rev-parse", branch], cwd=fork_path)
        branch_sha = (r_br.stdout or "").strip()
        if branch_sha == upstream_sha:
            _log(log_fh, f"Step 3: branch {branch} already at upstream/staged HEAD — reusing.")
            r_co = _run(["git", "checkout", branch], cwd=fork_path)
            _log_subprocess(log_fh, "git checkout branch", r_co)
            if r_co.returncode != 0:
                return False, f"Step 3: `git checkout {branch}` failed."
            return True, f"Step 3: reusing branch {branch}."
        ok = _confirm(
            f"Branch `{branch}` exists and diverges from upstream/staged. "
            f"Reset to upstream/staged? [y/N] "
        )
        if not ok:
            return False, (
                f"Step 3: branch {branch} diverges and operator declined "
                "reset. Operator must resolve manually."
            )
        r_co = _run(["git", "checkout", branch], cwd=fork_path)
        _log_subprocess(log_fh, "git checkout branch (reset path)", r_co)
        if r_co.returncode != 0:
            return False, f"Step 3: `git checkout {branch}` failed."
        r_reset = _run(
            ["git", "reset", "--hard", "upstream/staged"],
            cwd=fork_path,
        )
        _log_subprocess(log_fh, "git reset --hard upstream/staged", r_reset)
        if r_reset.returncode != 0:
            return False, (
                f"Step 3: `git reset --hard upstream/staged` failed "
                f"(exit {r_reset.returncode})."
            )
        return True, f"Step 3: branch {branch} reset to upstream/staged."

    _log(log_fh, f"Step 3: creating branch {branch} from upstream/staged...")
    r_new = _run(
        ["git", "checkout", "-b", branch, "upstream/staged"],
        cwd=fork_path,
    )
    _log_subprocess(log_fh, "git checkout -b branch", r_new)
    if r_new.returncode != 0:
        return False, (
            f"Step 3: `git checkout -b {branch} upstream/staged` "
            f"failed (exit {r_new.returncode}). "
            f"stderr:\n{(r_new.stderr or '')[-1500:]}"
        )
    return True, f"Step 3: branch {branch} created."


def step4_copy_skill_md(
    packet_dir: Path,
    fork_path: Path,
    log_fh,
) -> Tuple[bool, str]:
    """Step 4: copy SKILL.md from packet to fork; verify SHA256 parity."""
    src = packet_dir / "skills" / SKILL_NAME / "SKILL.md"
    if not src.is_file():
        return False, f"Step 4: packet missing SKILL.md at {src}."
    dst_dir = fork_path / "skills" / SKILL_NAME
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "SKILL.md"
    shutil.copy2(src, dst)
    src_hash = _sha256(src)
    dst_hash = _sha256(dst)
    if src_hash != dst_hash:
        return False, (
            f"Step 4: SHA256 mismatch after copy.\n"
            f"  src={src} {src_hash}\n  dst={dst} {dst_hash}"
        )
    _log(log_fh, f"Step 4: copied SKILL.md to {dst} (sha256={src_hash[:12]}...).")
    return True, "Step 4: SKILL.md copied + verified."


def step5_run_npm_start(
    fork_path: Path,
    log_fh,
) -> Tuple[bool, str]:
    """Step 5: run ``npm start`` in fork; halt on non-zero; confirm
    README.md was modified."""
    _log(log_fh, "Step 5: running `npm start` in fork...")
    r = _run(["npm", "start"], cwd=fork_path)
    _log_subprocess(log_fh, "npm start", r)
    if r.returncode != 0:
        return False, (
            f"Step 5: `npm start` failed (exit {r.returncode}). "
            f"Read the log and fix SKILL.md issues, then re-run --submit. "
            f"Tail of stderr:\n{(r.stderr or '')[-1500:]}"
        )
    r_st = _run(["git", "status", "--porcelain", "README.md"], cwd=fork_path)
    if r_st.returncode != 0:
        return False, f"Step 5: `git status --porcelain README.md` failed."
    if not (r_st.stdout or "").strip():
        _log(
            log_fh,
            "Step 5 WARNING: README.md not reported as modified by git "
            "(may already match upstream). Continuing.",
        )
    return True, "Step 5: `npm start` succeeded."


def step6_commit_and_push(
    fork_path: Path,
    branch: str,
    version: str,
    log_fh,
) -> Tuple[bool, str]:
    """Step 6: stage, show diff --stat --cached, prompt y/N, commit + push.

    v1.5.8 instruction 206 + Panelist B's CONCERN: stage BEFORE preview so
    the diff includes the just-copied (and previously untracked) SKILL.md.
    Pre-fix, `git diff --stat` (no ref) showed only modifications to
    tracked files; the headline file was invisible at the gate.
    """
    # Stage first so the preview reflects what will actually be committed.
    # `git add` is idempotent on already-staged paths; if there's nothing
    # to stage (idempotent re-run), `git commit` below handles it.
    r_add = _run(
        ["git", "add", f"skills/{SKILL_NAME}/", "README.md"],
        cwd=fork_path,
    )
    _log_subprocess(log_fh, "git add", r_add)
    if r_add.returncode != 0:
        return False, f"Step 6: `git add` failed (exit {r_add.returncode})."

    r_diff = _run(["git", "diff", "--stat", "--cached"], cwd=fork_path)
    diff_text = r_diff.stdout or ""
    print("\n--- git diff --stat --cached in fork ---")
    print(diff_text)
    print("--- end diff ---\n")
    log_fh.write("--- git diff --stat --cached ---\n")
    log_fh.write(diff_text)
    log_fh.write("--- end ---\n")
    ok = _confirm("Commit and push this submission to your fork? [y/N] ")
    if not ok:
        return False, (
            "Step 6: operator declined commit+push. SKILL.md was copied "
            "and `npm start` ran AND changes are now staged in the fork; "
            "no commit was made. Re-run --submit to retry, or "
            "`git reset HEAD` in the fork to un-stage and inspect."
        )
    r_commit = _run(
        ["git", "commit", "-m", f"Add {SKILL_NAME} skill v{version}"],
        cwd=fork_path,
    )
    _log_subprocess(log_fh, "git commit", r_commit)
    if r_commit.returncode != 0:
        combined = (r_commit.stdout or "") + (r_commit.stderr or "")
        if "nothing to commit" in combined.lower():
            _log(log_fh, "Step 6: nothing to commit (idempotent re-run).")
        else:
            return False, (
                f"Step 6: `git commit` failed (exit {r_commit.returncode}). "
                f"Tail of stderr:\n{(r_commit.stderr or '')[-1500:]}"
            )
    r_push = _run(
        ["git", "push", "-u", "origin", branch],
        cwd=fork_path,
    )
    _log_subprocess(log_fh, "git push", r_push)
    if r_push.returncode != 0:
        return False, (
            f"Step 6: `git push -u origin {branch}` failed "
            f"(exit {r_push.returncode}). "
            f"stderr:\n{(r_push.stderr or '')[-1500:]}"
        )
    return True, f"Step 6: pushed to origin/{branch}."


def step7_open_pr(
    fork_path: Path,
    packet_dir: Path,
    version: str,
    log_fh,
) -> Tuple[bool, str]:
    """Step 7: show PR title + first 20 lines of PR_BODY.md, prompt
    y/N, then ``gh pr create``."""
    pr_body_path = packet_dir / "PR_BODY.md"
    if not pr_body_path.is_file():
        return False, f"Step 7: PR body missing at {pr_body_path}."
    title = f"Add {SKILL_NAME} skill v{version}"
    body_lines = pr_body_path.read_text(encoding="utf-8").splitlines()
    preview = "\n".join(body_lines[:20])
    print("\n--- PR preview ---")
    print(f"PR title: {title}")
    print(f"PR base:  {AWESOME_COPILOT_REPO} staged")
    print("PR body (first 20 lines):")
    print(preview)
    print(f"... (full body at {pr_body_path})")
    print("--- end PR preview ---\n")
    log_fh.write(f"--- PR preview ---\nTitle: {title}\nBase: staged\n")
    log_fh.write(preview + "\n--- end ---\n")
    ok = _confirm(
        f"Open this PR against {AWESOME_COPILOT_REPO} staged? [y/N] "
    )
    if not ok:
        return False, (
            "Step 7: operator declined PR-create. The branch was pushed "
            "to your fork but no PR was opened. You can open it later "
            f"with `gh pr create --repo {AWESOME_COPILOT_REPO} --base "
            f"staged --title {title!r} --body-file {pr_body_path}`."
        )
    r = _run(
        [
            "gh", "pr", "create",
            "--repo", AWESOME_COPILOT_REPO,
            "--base", "staged",
            "--title", title,
            "--body-file", str(pr_body_path),
        ],
        cwd=fork_path,
    )
    _log_subprocess(log_fh, "gh pr create", r)
    if r.returncode != 0:
        return False, (
            f"Step 7: `gh pr create` failed (exit {r.returncode}). "
            f"stderr:\n{(r.stderr or '')[-1500:]}"
        )
    pr_url = (r.stdout or "").strip()
    _log(log_fh, f"Step 7: PR opened — {pr_url}")
    return True, f"Step 7: PR opened at {pr_url}"


def run_submission(
    repo_root: Path,
    packet_dir: Path,
    version: str,
    fork_path: Path,
    log_fh,
) -> int:
    """Drive steps 1-7 of the awesome-copilot submission. Each step
    halts on failure with EX_SOFTWARE; the operator inspects the log
    and re-runs (idempotent where possible)."""
    branch = f"add-{SKILL_NAME}-{version}"
    _log(log_fh, f"Beginning automated submission. fork_path={fork_path} branch={branch}")

    steps = [
        ("1", lambda: step1_verify_or_create_fork(fork_path, log_fh)),
        ("2", lambda: step2_setup_upstream_and_fetch(fork_path, log_fh)),
        ("3", lambda: step3_create_or_reuse_branch(fork_path, branch, log_fh)),
        ("4", lambda: step4_copy_skill_md(packet_dir, fork_path, log_fh)),
        ("5", lambda: step5_run_npm_start(fork_path, log_fh)),
        ("6", lambda: step6_commit_and_push(fork_path, branch, version, log_fh)),
        ("7", lambda: step7_open_pr(fork_path, packet_dir, version, log_fh)),
    ]
    for label, fn in steps:
        _log(log_fh, f"Step {label}: starting...")
        ok, msg = fn()
        _log(log_fh, msg)
        if not ok:
            _log(log_fh, f"Step {label}: HALT.")
            return EX_SOFTWARE
    _log(log_fh, "Automated submission DONE.")
    return EX_OK


# ---------------------------------------------------------------------------
# CLI surface.
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="submit_awesome_copilot",
        description=(
            "Generate the submission packet for the github/awesome-copilot "
            "registry. Reads QPB's SKILL.md frontmatter + version-string "
            "manifests, writes a packet under "
            "dist/awesome_copilot_submission/. With --submit also automates "
            "fork+branch+copy+validate+push+PR (with confirmation gates). "
            "See ai_context/DEVELOPMENT_PROCESS.md (awesome-copilot "
            "submission workflow) for the operator-side details."
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
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Generate the submission packet only. No fork, no push, no "
            "PR. Mutually exclusive with --submit."
        ),
    )
    p.add_argument(
        "--submit",
        action="store_true",
        help=(
            "Generate the packet AND automate steps 1-6 of MANUAL_STEPS.md "
            "(fork+clone, upstream remote+fetch, branch, copy SKILL.md, "
            "run `npm start`, commit+push, open PR) with confirmation "
            "prompts before every destructive action. Mutually exclusive "
            "with --dry-run."
        ),
    )
    p.add_argument(
        "--fork-path",
        type=Path,
        default=DEFAULT_FORK_PATH,
        metavar="DIR",
        help=(
            "Local clone of the operator's awesome-copilot fork. "
            "If the directory doesn't exist and --submit is used, "
            "the script offers to fork+clone via `gh repo fork`. "
            "Default: ~/Documents/awesome-copilot-fork."
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
            "dist/awesome_copilot_submission/. With --submit also "
            "automates fork+branch+copy+npm-start+push+PR."
        ),
        role=(
            "Run by the operator at v1.5.x ship time AFTER publish_pip "
            "+ publish_npm succeed. --dry-run generates the packet only; "
            "--submit automates steps 1-6 of MANUAL_STEPS.md with "
            "confirmation gates before every destructive action."
        ),
        usage_hint=(
            "python3 bin/submit_awesome_copilot.py --dry-run\n"
            "  or: python3 bin/submit_awesome_copilot.py --submit"
        ),
    )


def main(argv: Optional[list] = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list:
        _print_intro()
        return 0
    args = parse_args(argv_list)

    # v1.5.8 instruction 206: require explicit --dry-run XOR --submit
    # affirmation. Mirrors the publish_pip/publish_npm pattern from 204.
    if args.dry_run and args.submit:
        print(
            "ERROR: --dry-run and --submit are mutually exclusive. "
            "Pick one.",
            file=sys.stderr,
        )
        return EX_USAGE
    if not args.dry_run and not args.submit:
        print(
            "ERROR: must pass --dry-run or --submit.\n"
            "  --dry-run generates the submission packet only.\n"
            "  --submit generates the packet AND automates fork/branch/"
            "copy/validate/push/PR.",
            file=sys.stderr,
        )
        return EX_USAGE

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

    if args.dry_run:
        print(
            f"\nNext: follow MANUAL_STEPS.md to fork {AWESOME_COPILOT_REPO}, "
            "copy the skill folder in, run `npm start`, and "
            "open the PR. (Or re-run with --submit to automate steps 1-6.)"
        )
        return EX_OK

    # --submit path: drive the 7-step automation.
    log_path, log_fh = _open_log(version)
    try:
        _log(log_fh, f"submit_awesome_copilot --submit starting. version={version} log={log_path}")
        _log(log_fh, f"repo_root={repo_root} packet={dest} fork_path={args.fork_path}")
        rc = run_submission(repo_root, dest, version, args.fork_path, log_fh)
        return rc
    finally:
        log_fh.close()


if __name__ == "__main__":
    sys.exit(main())
