#!/usr/bin/env python3
"""bin/qpb_validate.py — Phase 0 Install Validator (v1.5.7 instruction 077).

Implements the deterministic Phase 0 install check designed in the
v1.5.7 Phase 0 + Windows Portability Addendum r3 (canonical design;
workspace path: ``QPB_v1.5.7_Phase0_Windows_Addendum.md``). This script
is the single source of truth for "is the Quality Playbook correctly
installed in this project."

Architectural framing (addendum §1.2, honest): this validator is
**A-19-class strength, not A-13-class**. Mode A has no runner harness
in which to spawn an auditor sub-agent for Phase 0 — the same agent
that would skip the install would also report the validator result.
What the validator provides instead of context separation:

* a deterministic install-closure check that beats diffuse prose
  checks across ~5 doc surfaces, and
* an anti-fabrication forcing function via a run-nonce contract
  (§3.4): a UUID nonce is written to disk under ``<target>/quality/``
  and stamped on every emitted ``event=`` line; the agent must paste
  the entire structured block verbatim into chat; an adopter (or a
  post-hoc check) cross-references the chat nonce against the disk
  file. Stale/fabricated pastes are detectable but not runtime-
  prevented. The residual risk is named honestly (addendum §12 row 7).

Behaviors (addendum §3.1): generate run-nonce + disk witness; detect
invocation context (clone vs installed); detect target + AI tool;
detect platform (``platform_kind()`` + Windows shell heuristic);
detect package managers; check the install closure / scaffolding /
environment against the embedded manifest (§3.2); emit
``event=remediation_suggestion`` lines with platform-aware commands
from the §3.3.2 finding catalog; exit 0 (ok) / 1 (remediable) /
2 (blocked).

Stdlib-only by design (matches QPB ``bin/`` conventions; no install
of the validator's own deps must be required to *check* the install).
"""

from __future__ import annotations

import sys
from pathlib import Path

# v1.5.7 instruction 077 (addendum §5.2 W3 entry-point audit): put the
# QPB clone root on sys.path so the validator works as a loose script
# (`python <clone>/bin/qpb_validate.py <target>`) from any cwd — the
# launch-prompt invocation form. No-op under `python -m
# bin.qpb_validate` (root already on sys.path). The validator imports
# no sibling bin.* module today, so this is also a defensive no-op
# that keeps script-form robust if one is added later.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import importlib.util
import os
import py_compile
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

__all__ = [
    "INSTALL_CLOSURE",
    "INSTALL_SCAFFOLDING",
    "INSTALL_ENVIRONMENT",
    "FINDING_CATALOG",
    "KIND_TO_FINDING_CODES",
    "platform_kind",
    "windows_shell_kind",
    "detect_package_managers",
    "command_for_platform",
    "main",
]

# ---------------------------------------------------------------------------
# §3.2 Install manifest contract
#
# INSTALL_CLOSURE is machine-derived from live
# bin/install_skill.py:_bundle_files() at HEAD a8cb3a5 and is pinned
# byte-for-byte against the installer by
# bin/tests/test_install_manifest_no_drift.py (acceptance #11). DO NOT
# hand-edit this list — if the installer's bundle set changes,
# regenerate from _bundle_files() (the drift test will fail loudly
# otherwise; that failure is the design working, not a flake).
# ---------------------------------------------------------------------------

# AI-tool marker -> canonical install path (relative to target),
# mirroring bin/install_skill.py:KNOWN_ENVIRONMENTS / AI_TOOL_MAP. Kept
# here (not imported) so the validator stays import-light and works
# from an installed location where install_skill.py is absent.
MARKER_TO_INSTALL_REL = {
    ".claude": ".claude/skills/quality-playbook",
    ".github": ".github/skills/quality-playbook",
    ".cursor": ".cursor/skills/quality-playbook",
    ".continue": ".continue/skills/quality-playbook",
    ".codex": ".codex/skills/quality-playbook",
    ".windsurf": ".windsurf/skills/quality-playbook",
    ".cline": ".cline/skills/quality-playbook",
    ".aider": ".aider/skills/quality-playbook",
}
AI_TOOL_TO_MARKER = {
    "claude": ".claude",
    "copilot": ".github",
    "github": ".github",
    "cursor": ".cursor",
    "continue": ".continue",
    "codex": ".codex",
    "windsurf": ".windsurf",
    "cline": ".cline",
    "aider": ".aider",
}
# Marker -> the CLI binary the runner shells out to (for cli_on_path).
# Only the four with first-class remediation (§3.3.2) have a binary;
# others fall back to informational.
MARKER_TO_CLI = {
    ".claude": "claude",
    ".github": "gh",
    ".cursor": "cursor",
    ".codex": "codex",
}

INSTALL_CLOSURE = [
    # ---- Top-level skill files (2) ----
    {"path": "SKILL.md", "kind": "skill_doc", "min_version": "1.5.7", "expected_sha256": None, "source_glob": None},
    {"path": "quality_gate.py", "kind": "gate_script", "min_version": None, "expected_sha256": None, "source_glob": None},

    # ---- agents/ (3 — sorted glob "*.md", NOT "*.agent.md") ----
    {"path": "agents/calibration_orchestrator.md", "kind": "agent_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "agents/quality-playbook-claude.agent.md", "kind": "agent_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "agents/quality-playbook.agent.md", "kind": "agent_file", "min_version": None, "expected_sha256": None, "source_glob": None},

    # ---- bin/ (13 — fixed enumeration from install_skill.py;
    #      v1.5.7 086 A-26 added qpb_config / run_state_lib /
    #      validate_phase_artifacts) ----
    {"path": "bin/__init__.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/archive_lib.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/benchmark_lib.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/citation_verifier.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/council_config.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/council_semantic_check.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/migrate_v1_5_0_layout.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/qpb_config.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/quality_playbook.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/reference_docs_ingest.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/role_map.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/run_state_lib.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "bin/validate_phase_artifacts.py", "kind": "bundled_module", "min_version": None, "expected_sha256": None, "source_glob": None},

    # ---- phase_prompts/ (10 — sorted glob "*.md"; phase0.md does NOT
    #      exist; README.md/iteration.md/single_pass.md ARE bundled) ----
    {"path": "phase_prompts/README.md", "kind": "phase_prompt_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "phase_prompts/iteration.md", "kind": "phase_prompt_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "phase_prompts/phase1.md", "kind": "phase_prompt_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "phase_prompts/phase2.md", "kind": "phase_prompt_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "phase_prompts/phase3.md", "kind": "phase_prompt_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "phase_prompts/phase4.md", "kind": "phase_prompt_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "phase_prompts/phase5.md", "kind": "phase_prompt_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "phase_prompts/phase6.md", "kind": "phase_prompt_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "phase_prompts/phase6_auditor.md", "kind": "phase_prompt_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "phase_prompts/single_pass.md", "kind": "phase_prompt_file", "min_version": None, "expected_sha256": None, "source_glob": None},

    # ---- references/ (23 — sorted glob "*.md"; v1.5.7 089 F8 added
    #      qpb_validate_event_schema.md) ----
    {"path": "references/challenge_gate.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/code-only-mode.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/constitution.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/defensive_patterns.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/exploration_patterns.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/functional_tests.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/iteration.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/orchestrator_protocol.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/phase1_exploration_guide.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/phase2_generation_guide.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/phase6_verify_guide.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/qpb_validate_event_schema.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/requirements_pipeline.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/requirements_refinement.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/requirements_review.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/review_protocols.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/role_map_queries.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/run_state_schema.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/runners_and_models.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/schema_mapping.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/spec_audit.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/verification.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
    {"path": "references/what_just_happened.md", "kind": "reference_file", "min_version": None, "expected_sha256": None, "source_glob": None},
]
# Total: 2 + 3 + 13 + 10 + 23 = 51 entries (v1.5.7 086 A-26: bin/
# grew 10 → 13 — qpb_config / run_state_lib / validate_phase_artifacts;
# v1.5.7 089 F8: references/ grew 22 → 23 — qpb_validate_event_schema.md
# added, auto-bundled by _bundle_files()'s references/* glob.
# INSTALL_CLOSURE is the machine-derived mirror of _bundle_files(),
# kept in lockstep per the drift test).
# Acceptance #11: set(e["path"]) == set(str(dst) for _, dst in _bundle_files()).

INSTALL_SCAFFOLDING = [
    {"path": ".gitignore", "kind": "gitignore_scaffold"},
    {"path": "reference_docs", "kind": "directory_scaffold"},
    {"path": "reference_docs/cite", "kind": "directory_scaffold"},
]

INSTALL_ENVIRONMENT = [
    {"kind": "python_version", "min_version": "3.10"},
    {"kind": "python_pkg", "pkg": "tiktoken"},
    {"kind": "python_pkg", "pkg": "yaml"},
    {"kind": "cli_on_path", "tool": "<detected-ai-tool>"},
    {"kind": "bash_available", "required_when": "project triggers mechanical verification"},
]

# Python packages QPB requires importable, mapped from import name
# (the name used in `importlib.util.find_spec`) to PyPI distribution
# name (the name `pip install` actually accepts). For `yaml` the
# import name and dist name diverge — `pip install yaml` is
# unrunnable; the correct distribution is `PyYAML`. Keep this map as
# the single source of truth so check_environment and the
# remediation_suggestion emission agree.
PYTHON_PKG_IMPORT_TO_DIST = {
    "tiktoken": "tiktoken",
    "yaml": "PyYAML",
}

# Sentinel substring used to recognise the QPB block appended to a
# target's .gitignore by the AGENTS.md install `cp` step. Matched as a
# substring (the template may evolve; this anchor stays stable).
_GITIGNORE_SENTINEL = "quality/"

# ---------------------------------------------------------------------------
# §3.3.3 Platform detection contract
# ---------------------------------------------------------------------------


def platform_kind() -> str:
    """Return one of: 'macos', 'linux', 'windows', 'unknown'.

    Verbatim from addendum §3.3.3.
    """
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "win32" or os.name == "nt":
        return "windows"
    return "unknown"


def windows_shell_kind(env: "dict[str, str] | None" = None) -> str:
    """Best-effort guess of which shell the agent is running in on
    Windows, from env vars (addendum §3.3.3).

    Returns 'powershell', 'cmd', 'git_bash', or 'ambiguous'.

    Precedence: an MSYSTEM value (MINGW64/MSYS) is the strongest
    signal (Git Bash); else PSModulePath present without MSYSTEM ->
    PowerShell (the modern default, preferred when otherwise
    ambiguous); else COMSPEC present without PSModulePath/MSYSTEM ->
    cmd.exe; else ambiguous.
    """
    e = os.environ if env is None else env
    if e.get("MSYSTEM"):
        return "git_bash"
    if e.get("PSModulePath"):
        return "powershell"
    if e.get("COMSPEC"):
        return "cmd"
    return "ambiguous"


def detect_package_managers() -> "dict[str, bool]":
    """Detect available OS package managers (used by remediation
    suggestions that depend on package-manager presence — §3.3.3).
    Cached by the caller for the run.
    """
    return {pm: shutil.which(pm) is not None
            for pm in ("brew", "apt", "dnf", "winget", "choco")}


# ---------------------------------------------------------------------------
# §3.3.2 Finding catalog (13 codes). Each entry: tool, severity,
# per-platform command templates, rationale, verify_with. Platform keys
# are macos / linux / windows_powershell / windows_cmd. command_for_
# platform() resolves <placeholder> substitutions and always returns a
# non-empty string for every (code, platform) pair (acceptance #12/#14).
#
# Unix command strings keep balanced quoting so shlex.split() never
# raises (acceptance #14). Windows strings never contain the bare token
# `python3`, windows_cmd strings never contain `&&`, and path
# separators are backslashes (acceptance #14).
# ---------------------------------------------------------------------------

_RUN_INSTALLER_MAC = "python3 <clone>/bin/install_skill.py --into <target> --ai-tool <tool>"
_RUN_INSTALLER_WIN = "python <clone>\\bin\\install_skill.py --into <target> --ai-tool <tool>"
_RUN_INSTALLER_MAC_FORCE = _RUN_INSTALLER_MAC + " --force"
_RUN_INSTALLER_WIN_FORCE = _RUN_INSTALLER_WIN + " --force"
_REVALIDATE = "python <root>/bin/qpb_validate.py <target>"

FINDING_CATALOG = {
    "install_absent": {
        "tool": "run_installer",
        "severity": "remediable",
        "commands": {
            "macos": _RUN_INSTALLER_MAC,
            "linux": _RUN_INSTALLER_MAC,
            "windows_powershell": _RUN_INSTALLER_WIN,
            "windows_cmd": _RUN_INSTALLER_WIN,
        },
        "rationale": "No QPB install at the canonical AI-tool path; run the installer.",
        "verify_with": _REVALIDATE,
    },
    "install_partial": {
        "tool": "repair_partial",
        "severity": "remediable",
        "commands": {
            "macos": _RUN_INSTALLER_MAC_FORCE,
            "linux": _RUN_INSTALLER_MAC_FORCE,
            "windows_powershell": _RUN_INSTALLER_WIN_FORCE,
            "windows_cmd": _RUN_INSTALLER_WIN_FORCE,
        },
        "rationale": "Install path exists but INSTALL_CLOSURE has missing/unreadable entries; re-run with --force (operator-edited files become <file>.operator-backup-<TIMESTAMP>).",
        "verify_with": _REVALIDATE,
    },
    "install_wrong_ai_tool": {
        "tool": "reinstall_for_correct_tool",
        "severity": "remediable",
        "commands": {
            "macos": _RUN_INSTALLER_MAC,
            "linux": _RUN_INSTALLER_MAC,
            "windows_powershell": _RUN_INSTALLER_WIN,
            "windows_cmd": _RUN_INSTALLER_WIN,
        },
        "rationale": "Install detected at one marker but a different --ai-tool was requested; re-install for the requested tool.",
        "verify_with": _REVALIDATE,
    },
    "install_version_skew": {
        "tool": "upgrade_install",
        "severity": "remediable",
        "commands": {
            "macos": _RUN_INSTALLER_MAC_FORCE,
            "linux": _RUN_INSTALLER_MAC_FORCE,
            "windows_powershell": _RUN_INSTALLER_WIN_FORCE,
            "windows_cmd": _RUN_INSTALLER_WIN_FORCE,
        },
        "rationale": "Installed SKILL.md version older than the clone. Re-install is closure-only; your <target>/quality/ directory is preserved untouched. Operator-edited files become <file>.operator-backup-<TIMESTAMP>.",
        "verify_with": _REVALIDATE,
    },
    "scaffolding_missing_gitignore": {
        "tool": "apply_gitignore_template",
        "severity": "remediable",
        "commands": {
            "macos": "cat <clone>/skill-template.gitignore >> <target>/.gitignore",
            "linux": "cat <clone>/skill-template.gitignore >> <target>/.gitignore",
            "windows_powershell": "Get-Content <clone>\\skill-template.gitignore | Add-Content <target>\\.gitignore",
            "windows_cmd": "type <clone>\\skill-template.gitignore >> <target>\\.gitignore",
        },
        "rationale": "Target .gitignore absent or lacks the QPB sentinel block.",
        "verify_with": _REVALIDATE,
    },
    "scaffolding_missing_reference_docs": {
        "tool": "create_reference_docs",
        "severity": "remediable",
        "commands": {
            "macos": "mkdir -p <target>/reference_docs/cite",
            "linux": "mkdir -p <target>/reference_docs/cite",
            "windows_powershell": "New-Item -ItemType Directory -Force -Path <target>\\reference_docs\\cite",
            "windows_cmd": "mkdir <target>\\reference_docs\\cite",
        },
        "rationale": "<target>/reference_docs/ or <target>/reference_docs/cite/ does not exist.",
        "verify_with": _REVALIDATE,
    },
    "python_version_too_old": {
        "tool": "install_newer_python",
        "severity": "remediable",
        "commands": {
            "macos": "brew install python@3.12",
            "linux": "sudo apt install python3.12",
            "windows_powershell": "Download and run the Windows installer from https://www.python.org/downloads/windows/ (adds python and py -3 to PATH)",
            "windows_cmd": "Download and run the Windows installer from https://www.python.org/downloads/windows/ (adds python and py -3 to PATH)",
        },
        "rationale": "sys.version_info < (3, 10); QPB requires Python 3.10+.",
        "verify_with": "python --version",
    },
    "python_pkg_missing": {
        "tool": "install_python_pkg",
        "severity": "remediable",
        "commands": {
            "macos": "python3 -m pip install --user <pkg>",
            "linux": "python3 -m pip install --user <pkg>",
            "windows_powershell": "py -3 -m pip install --user <pkg>",
            "windows_cmd": "py -3 -m pip install --user <pkg>",
        },
        "rationale": "importlib.util.find_spec(<pkg>) returned None; install the missing package.",
        "verify_with": _REVALIDATE,
    },
    "ai_cli_not_on_path": {
        "tool": "install_ai_cli",
        "severity": "blocked",
        "commands": {
            "macos": "Install the <tool> CLI: claude -> https://docs.claude.com/en/docs/claude-code/quickstart ; cursor -> https://cursor.com/install ; codex -> npm install -g @openai/codex ; gh -> brew install gh then gh extension install github/gh-copilot",
            "linux": "Install the <tool> CLI: claude -> https://docs.claude.com/en/docs/claude-code/quickstart ; cursor -> https://cursor.com/install ; codex -> npm install -g @openai/codex ; gh -> apt install gh then gh extension install github/gh-copilot",
            "windows_powershell": "Install the <tool> CLI: claude -> https://docs.claude.com/en/docs/claude-code/quickstart ; cursor -> https://cursor.com/install ; codex -> npm install -g @openai/codex ; gh -> winget install GitHub.cli ; then gh extension install github/gh-copilot",
            "windows_cmd": "Install the <tool> CLI: claude -> https://docs.claude.com/en/docs/claude-code/quickstart ; cursor -> https://cursor.com/install ; codex -> npm install -g @openai/codex ; gh -> winget install GitHub.cli ; then gh extension install github/gh-copilot",
        },
        "rationale": "shutil.which(<tool>) returned None for the detected AI tool; the runner cannot invoke it. Phase 0 blocks rather than discovering this in Phase 1.",
        "verify_with": _REVALIDATE,
    },
    "bash_unavailable_mechanical_required": {
        "tool": "install_bash_environment",
        "severity": "blocked",
        "commands": {
            "macos": "bash is the system default on macOS; this finding should not emit here",
            "linux": "bash is the system default on Linux; this finding should not emit here",
            "windows_powershell": "Install Git Bash from https://gitforwindows.org or WSL2 via wsl --install -d Ubuntu",
            "windows_cmd": "Install Git Bash from https://gitforwindows.org or WSL2 via wsl --install -d Ubuntu",
        },
        "rationale": "Target project type triggers mechanical verification but bash is unavailable. (Phase 0 cannot classify the project; this code is emitted later by the mechanical-verification path, not by the Phase 0 validator.)",
        "verify_with": _REVALIDATE,
    },
    "bash_unavailable_mechanical_not_required": {
        "tool": "none",
        "severity": "remediable",
        "commands": {
            "macos": "No remediation needed; mechanical verification will be recorded NOT APPLICABLE.",
            "linux": "No remediation needed; mechanical verification will be recorded NOT APPLICABLE.",
            "windows_powershell": "No remediation needed; mechanical verification will be recorded NOT APPLICABLE.",
            "windows_cmd": "No remediation needed; mechanical verification will be recorded NOT APPLICABLE.",
        },
        "rationale": "bash unavailable but the project type does not require mechanical verification; proceeding (auto-passable).",
        "verify_with": "none",
    },
    "validator_invoked_from_clone": {
        "tool": "clarify_target",
        "severity": "blocked",
        "commands": {
            "macos": "Re-invoke with an explicit target argument: python <clone>/bin/qpb_validate.py <absolute-path-to-target>",
            "linux": "Re-invoke with an explicit target argument: python <clone>/bin/qpb_validate.py <absolute-path-to-target>",
            "windows_powershell": "Re-invoke with an explicit target argument: python <clone>\\bin\\qpb_validate.py <absolute-path-to-target>",
            "windows_cmd": "Re-invoke with an explicit target argument: python <clone>\\bin\\qpb_validate.py <absolute-path-to-target>",
        },
        "rationale": "Validator cwd appears to be the QPB clone, not a target project. Default cwd-as-target would risk installing the skill into your QPB clone.",
        "verify_with": "python <clone>/bin/qpb_validate.py <target>",
    },
    "multiple_ai_tool_markers": {
        "tool": "select_ai_tool",
        "severity": "blocked",
        "commands": {
            "macos": "Pass --ai-tool <claude|cursor|copilot|continue|codex|windsurf|cline|aider> explicitly; priority order: operator-told > self-identified > ASK",
            "linux": "Pass --ai-tool <claude|cursor|copilot|continue|codex|windsurf|cline|aider> explicitly; priority order: operator-told > self-identified > ASK",
            "windows_powershell": "Pass --ai-tool <claude|cursor|copilot|continue|codex|windsurf|cline|aider> explicitly; priority order: operator-told > self-identified > ASK",
            "windows_cmd": "Pass --ai-tool <claude|cursor|copilot|continue|codex|windsurf|cline|aider> explicitly; priority order: operator-told > self-identified > ASK",
        },
        "rationale": "Target has 2+ AI-tool markers; the install path is ambiguous without an explicit --ai-tool.",
        "verify_with": "python <clone>/bin/qpb_validate.py <target> --ai-tool <tool>",
    },
    "stale_quality_dir": {
        "tool": "resolve_stale_quality",
        "severity": "blocked",
        "commands": {
            "macos": (
                "Resolve stale <target>/quality/ explicitly. Choose one:\n"
                "  (a) Fresh start (recommended for new runs):\n"
                "      git -C <target> restore quality && git -C <target> clean -fd quality\n"
                "  (b) Continue a previous run (only if you intend resume):\n"
                "      pass --resume to bin/run_playbook (Mode B) or read "
                "      quality/PROGRESS.md to identify the last completed phase "
                "      (Mode A walk-from-checkpoint)."
            ),
            "linux": (
                "Resolve stale <target>/quality/ explicitly. Choose one:\n"
                "  (a) Fresh start (recommended for new runs):\n"
                "      git -C <target> restore quality && git -C <target> clean -fd quality\n"
                "  (b) Continue a previous run (only if you intend resume):\n"
                "      pass --resume to bin/run_playbook (Mode B) or read "
                "      quality/PROGRESS.md to identify the last completed phase "
                "      (Mode A walk-from-checkpoint)."
            ),
            "windows_powershell": (
                "Resolve stale <target>\\quality\\ explicitly. Choose one:\n"
                "  (a) Fresh start (recommended for new runs):\n"
                "      git -C <target> restore quality; git -C <target> clean -fd quality\n"
                "  (b) Continue a previous run (only if you intend resume):\n"
                "      pass --resume to bin/run_playbook (Mode B) or read "
                "      quality\\PROGRESS.md to identify the last completed phase "
                "      (Mode A walk-from-checkpoint)."
            ),
            "windows_cmd": (
                "Resolve stale <target>\\quality\\ explicitly. Choose one:\n"
                "  (a) Fresh start (recommended for new runs):\n"
                # cmd.exe sequencing is `&` (single); `&&` is forbidden
                # in windows-cmd catalog forms — see
                # test_qpb_validate_remediation_commands::
                # test_no_double_ampersand_in_cmd_forms. (macos/linux
                # bash keep `&&`; windows_powershell uses `;`.)
                "      git -C <target> restore quality & git -C <target> clean -fd quality\n"
                "  (b) Continue a previous run (only if you intend resume):\n"
                "      pass --resume to bin/run_playbook (Mode B) or read "
                "      quality\\PROGRESS.md to identify the last completed phase "
                "      (Mode A walk-from-checkpoint)."
            ),
        },
        "rationale": (
            "<target>/quality/ contains files but no active-run marker. "
            "Agents have been observed (codex Mode A on click 2026-05-18) "
            "treating this state as a resumable run and skipping the "
            "Phase 0 install/validate sequence. Resolve explicitly: "
            "either clean and restart, or resume deliberately."
        ),
        "verify_with": _REVALIDATE,
    },
}

# §3.2 kind -> §3.3.2 finding code(s). Acceptance #12 asserts every
# kind used in the three manifests maps to >=1 catalog code, and the
# kinds with no install-closure remediation (cli/python/bash) have
# their own dedicated codes.
KIND_TO_FINDING_CODES = {
    # INSTALL_CLOSURE kinds — a missing/old/unreadable closure file is
    # remediated by (re-)running the installer.
    "skill_doc": ["install_partial", "install_version_skew", "install_absent"],
    "gate_script": ["install_partial", "install_absent"],
    "bundled_module": ["install_partial", "install_absent"],
    "reference_file": ["install_partial", "install_absent"],
    "phase_prompt_file": ["install_partial", "install_absent"],
    "agent_file": ["install_partial", "install_absent"],
    # INSTALL_SCAFFOLDING kinds.
    "gitignore_scaffold": ["scaffolding_missing_gitignore"],
    "directory_scaffold": ["scaffolding_missing_reference_docs"],
    # INSTALL_ENVIRONMENT kinds.
    "cli_on_path": ["ai_cli_not_on_path"],
    "python_pkg": ["python_pkg_missing"],
    "python_version": ["python_version_too_old"],
    "bash_available": [
        "bash_unavailable_mechanical_required",
        "bash_unavailable_mechanical_not_required",
    ],
    # v1.5.7 A-20 reframed (instruction 084). Not a manifest kind — a
    # synthetic hygiene kind for the stale-quality-dir block; carries
    # its own dedicated catalog code.
    "install_hygiene": ["stale_quality_dir"],
}


# F2 fix (instruction 077b): the two finding codes addendum r3
# §3.3.3 names as package-manager-presence-dependent. For these,
# command_for_platform() consults the detected managers and "prefers
# commands that match what's actually installed" (§3.3.3 verbatim)
# instead of the OS-only hardcode (Linux->apt, Windows->winget) codex
# flagged. The static FINDING_CATALOG templates are retained as the
# no-pkg_mgrs fallback so callers that pass no managers (acceptance
# #12/#14, which iterate command_for_platform(code, plat)) keep
# getting a non-empty string for every (code, platform) pair.
_PKG_MGR_AWARE = {"python_version_too_old", "ai_cli_not_on_path"}


def command_for_platform(finding_code: str, platform: "str | None" = None,
                          pkg_mgrs: "dict[str, bool] | None" = None,
                          **subs: str) -> str:
    """Return the platform-correct command string for a finding code,
    with <placeholder> tokens substituted.

    ``platform`` accepts: 'macos', 'linux', 'windows',
    'windows-powershell', 'windows-cmd' (hyphen or underscore). When
    None, the host platform_kind() is used (Windows -> powershell, the
    modern default per §3.3.3). Always returns a non-empty string for
    every catalog (code, platform) pair.

    ``pkg_mgrs`` (F2): the detect_package_managers() result
    ({name: present-bool}). When provided AND the finding code is
    package-manager-dependent (§3.3.3), the command is chosen from the
    detected managers (dnf>apt on Linux, choco>winget on Windows, brew
    on macOS). When omitted, the static catalog template is used.
    """
    entry = FINDING_CATALOG[finding_code]
    key = _platform_key(platform)
    if pkg_mgrs is not None and finding_code in _PKG_MGR_AWARE:
        template = _pkg_mgr_aware_command(finding_code, key, pkg_mgrs, subs)
    else:
        template = entry["commands"][key]
    for placeholder, value in subs.items():
        template = template.replace(f"<{placeholder}>", str(value))
    return template


def _pkg_mgr_aware_command(finding_code: str, key: str,
                           pkg_mgrs: "dict[str, bool]",
                           subs: "dict[str, str]") -> str:
    """Build the package-manager-preferred command (§3.3.3). Windows
    forms never contain a bare `python3` token and never use `&&`
    (acceptance #14); Unix forms stay shlex-parseable."""
    def has(pm: str) -> bool:
        return bool(pkg_mgrs.get(pm))

    if finding_code == "python_version_too_old":
        if key == "macos":
            return ("brew install python@3.12" if has("brew")
                    else "Download and run the macOS installer from "
                         "https://www.python.org/downloads/macos/")
        if key == "linux":
            if has("dnf"):
                return "sudo dnf install python3.12"
            if has("apt"):
                return "sudo apt install python3.12"
            return ("Install Python 3.10+ via your distribution "
                    "package manager (apt/dnf) or from "
                    "https://www.python.org/downloads/source/")
        # windows_powershell / windows_cmd
        if has("choco"):
            return "choco install python --version=3.12.0"
        if has("winget"):
            return "winget install Python.Python.3.12"
        return ("Download and run the Windows installer from "
                "https://www.python.org/downloads/windows/ "
                "(adds python and py -3 to PATH)")

    # ai_cli_not_on_path — tool-aware (§3.3.2 per-tool) + pkg-mgr-aware
    # for gh (Copilot). claude/cursor/codex have no distro package; use
    # their canonical install routes.
    tool = (subs.get("tool") or "").lower()
    if tool == "claude":
        return ("Install Claude Code: "
                "https://docs.claude.com/en/docs/claude-code/quickstart")
    if tool == "cursor":
        return ("Install Cursor (its CLI ships with the desktop app): "
                "https://cursor.com/install")
    if tool == "codex":
        return "npm install -g @openai/codex"
    if tool in ("gh", "copilot", "github"):
        if key == "macos":
            return ("brew install gh" if has("brew")
                    else "Install gh from https://cli.github.com ; then "
                         "gh extension install github/gh-copilot")
        if key == "linux":
            if has("apt"):
                return "sudo apt install gh"
            if has("dnf"):
                return "sudo dnf install gh"
            return ("Install gh from https://cli.github.com ; then "
                    "gh extension install github/gh-copilot")
        # windows
        if has("winget"):
            return "winget install GitHub.cli"
        if has("choco"):
            return "choco install gh"
        return ("Install gh from https://cli.github.com ; then "
                "gh extension install github/gh-copilot")
    # Unknown / placeholder tool -> the static multi-tool directive.
    return FINDING_CATALOG[finding_code]["commands"][key]


def _platform_key(platform: "str | None") -> str:
    if platform is None:
        pk = platform_kind()
        if pk == "windows":
            return "windows_powershell"
        if pk in ("macos", "linux"):
            return pk
        return "linux"  # 'unknown' -> Unix form (most portable default)
    p = platform.replace("-", "_").lower()
    if p in ("macos", "linux", "windows_powershell", "windows_cmd"):
        return p
    if p == "windows":
        return "windows_powershell"
    raise ValueError(f"unknown platform: {platform!r}")


# ---------------------------------------------------------------------------
# Structured emitter (every line carries the run-nonce — §3.4)
# ---------------------------------------------------------------------------


def _escape_value(value: object) -> str:
    s = str(value)
    if " " in s or "=" in s:
        return '"' + s.replace('"', "'") + '"'
    return s


class Emitter:
    """event=<name> nonce=<NONCE> k=v ... lines to stdout. Same shape
    as bin/install_skill.py:Emitter so the witness contract reuses the
    adopter's existing mental model."""

    def __init__(self, nonce: str, stream=None) -> None:
        self.nonce = nonce
        self.stream = stream if stream is not None else sys.stdout

    def emit(self, event: str, **fields: object) -> None:
        parts = [f"event={event}", f"nonce={self.nonce}"]
        for key, value in fields.items():
            parts.append(f"{key}={_escape_value(value)}")
        print(" ".join(parts), file=self.stream)


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

# Clone-only markers: top-level paths present in a QPB clone (and in
# a download-zip extract of the repo, for the tracked ones) but NEVER
# produced by install_skill.py:_bundle_files() (which copies only
# SKILL.md, quality_gate.py, references/*, phase_prompts/*, agents/*,
# bin/*). The pre-077b _CLONE_MARKERS set
# (bin/SKILL.md/phase_prompts/references) was the F1 defect — all four
# ARE bundled, so they could never discriminate clone-vs-installed and
# every installed tree fell through to "ambiguous". `setup_repos.sh`
# was named primary by 077b but is absent from the current clone;
# `.git/` covers git clones, and `docs/design/` + `ai_context/` are
# tracked clone-only paths (so they also survive a download-zip
# extract). The OR-set stays robust if any single one drifts (worker
# design call per 077b Task 1; HALT_077-named candidate set).
_CLONE_ONLY_MARKERS = ("setup_repos.sh", ".git", "docs/design", "ai_context")

# An installed validator lives at
# <target>/<marker>/skills/quality-playbook/bin/qpb_validate.py.
_INSTALL_MARKERS = tuple(MARKER_TO_INSTALL_REL)


def detect_invocation_context(script_path: Path) -> "tuple[str, Path]":
    """Return ('clone'|'installed'|'ambiguous', resolved_root).

    F1 fix (instruction 077b). The pre-077b heuristic used
    bin/SKILL.md/phase_prompts/references as clone markers, but
    install_skill.py:_bundle_files() bundles all four into the
    installed tree, so "installed" was unreachable and every installed
    tree fell through to "ambiguous" (addendum r3 §3.1 behavior #2
    missed end-to-end; codex-confirmed in HALT_077). New algorithm, in
    priority order:

    1. INSTALLED first, via the unambiguous path-ancestor signature
       ``<marker>/skills/quality-playbook/bin/<script>``. Structural —
       cannot be spoofed by the closure-file overlap that broke F1.
    2. else CLONE, via a marker ``_bundle_files()`` never produces
       (setup_repos.sh / .git / docs/design / ai_context — any one).
    3. else AMBIGUOUS — a true fallback now, not the always-fired
       branch (the agent branches on the ambiguity, e.g. asks).
    """
    resolved = script_path.resolve()
    # (1) installed: <marker>/skills/quality-playbook/bin/<script>
    for anc in resolved.parents:
        if (anc.name == "quality-playbook"
                and anc.parent.name == "skills"
                and anc.parent.parent.name in _INSTALL_MARKERS):
            return "installed", anc
    root = resolved.parent.parent
    # (2) clone: any bundle-absent marker at the clone root
    if any((root / m).exists() for m in _CLONE_ONLY_MARKERS):
        return "clone", root
    # (3) ambiguous (true fallback)
    return "ambiguous", root


def _markers_in(dir_path: Path) -> "list[str]":
    return sorted(m for m in MARKER_TO_INSTALL_REL
                  if (dir_path / m).is_dir())


def detect_target(argv_target: "str | None",
                   cwd: Path) -> "tuple[Path, list[str]]":
    """Resolve (target_abs, markers_found_in_target).

    If an explicit target argument is given, use it (markers are then
    scanned inside it). Otherwise walk up from cwd to the first
    directory containing >=1 AI-tool marker and use that.
    """
    if argv_target:
        t = Path(argv_target).expanduser().resolve()
        return t, _markers_in(t)
    cur = cwd.resolve()
    for d in [cur, *cur.parents]:
        found = _markers_in(d)
        if found:
            return d, found
    return cur, []


def detect_ai_tool(markers: "list[str]",
                    cli_arg: "str | None") -> "tuple[str | None, str | None]":
    """Return (marker, normalized_tool_name) using the AGENTS.md
    priority order: operator-told (--ai-tool) > self-identified
    (single marker) > ASK (None on ambiguity)."""
    if cli_arg:
        marker = AI_TOOL_TO_MARKER.get(cli_arg.lower())
        return marker, cli_arg.lower()
    if len(markers) == 1:
        m = markers[0]
        rev = {v: k for k, v in AI_TOOL_TO_MARKER.items() if v == m}
        return m, next(iter(rev.values())) if rev else None
    return None, None


# ---------------------------------------------------------------------------
# Closure / scaffolding / environment checks
# ---------------------------------------------------------------------------


def _readable_file(p: Path) -> bool:
    try:
        with p.open("rb") as fh:
            fh.read(1)
        return True
    except OSError:
        return False


def _static_parse_ok(p: Path) -> "tuple[bool, str | None]":
    """Static parse via py_compile (NOT import — addendum §3.2: a
    target-root import could execute top-level code or collide with a
    target's own module).

    Returns (ok, detail). detail is None on success. On failure it
    distinguishes a real SOURCE parse failure (py_compile.
    PyCompileError / SyntaxError) from a FILESYSTEM/sandbox failure
    (OSError — permissions, sandbox, missing fd) so Phase 0 closure
    diagnostics never misreport a permissions/sandbox error as
    syntactic corruption of the file (v1.5.7 089 F4 / bootstrap
    BUG-001 / REQ-001 — closure diagnostics must distinguish syntax
    from filesystem failures)."""
    try:
        py_compile.compile(str(p), doraise=True)
        return True, None
    except (py_compile.PyCompileError, SyntaxError) as exc:
        return False, f"py_compile parse failed: {exc}"
    except OSError as exc:
        return False, (f"py_compile filesystem error: "
                       f"{type(exc).__name__}: {exc}")


def _skill_version(skill_md: Path) -> "str | None":
    """Read meta.version from SKILL.md frontmatter (best-effort, no
    YAML dependency — the validator must run before deps are checked).
    """
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("version:"):
            return s.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def _version_tuple(v: str) -> "tuple[int, ...]":
    out = []
    for part in v.split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out)


def check_closure(install_root: Path) -> "list[dict]":
    """Apply each INSTALL_CLOSURE entry's kind-specific check. Returns
    a list of finding dicts: {code, kind, path, detail}."""
    findings: "list[dict]" = []
    if not install_root.exists():
        findings.append({
            "code": "install_absent", "kind": "skill_doc",
            "path": str(install_root),
            "detail": "canonical install path does not exist",
        })
        return findings
    for entry in INSTALL_CLOSURE:
        p = install_root / entry["path"]
        kind = entry["kind"]
        if not p.is_file():
            findings.append({"code": "install_partial", "kind": kind,
                             "path": entry["path"], "detail": "missing"})
            continue
        if not _readable_file(p):
            findings.append({"code": "install_partial", "kind": kind,
                             "path": entry["path"], "detail": "unreadable"})
            continue
        if kind in ("gate_script", "bundled_module"):
            ok, parse_detail = _static_parse_ok(p)
            if not ok:
                findings.append({"code": "install_partial", "kind": kind,
                                 "path": entry["path"],
                                 "detail": parse_detail})
                continue
        if kind == "skill_doc" and entry.get("min_version"):
            got = _skill_version(p)
            if got and _version_tuple(got) < _version_tuple(entry["min_version"]):
                findings.append({"code": "install_version_skew",
                                 "kind": kind, "path": entry["path"],
                                 "detail": f"installed {got} < {entry['min_version']}"})
        if kind == "phase_prompt_file" and entry.get("expected_sha256"):
            import hashlib
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            if digest != entry["expected_sha256"]:
                findings.append({"code": "install_partial", "kind": kind,
                                 "path": entry["path"],
                                 "detail": "sha256 mismatch"})
    return findings


def check_scaffolding(target: Path) -> "list[dict]":
    findings: "list[dict]" = []
    for entry in INSTALL_SCAFFOLDING:
        kind = entry["kind"]
        p = target / entry["path"]
        if kind == "gitignore_scaffold":
            ok = p.is_file()
            if ok:
                try:
                    ok = _GITIGNORE_SENTINEL in p.read_text(
                        encoding="utf-8", errors="replace")
                except OSError:
                    ok = False
            if not ok:
                findings.append({"code": "scaffolding_missing_gitignore",
                                 "kind": kind, "path": entry["path"],
                                 "detail": "absent or missing QPB sentinel"})
        elif kind == "directory_scaffold":
            if not p.is_dir():
                findings.append({"code": "scaffolding_missing_reference_docs",
                                 "kind": kind, "path": entry["path"],
                                 "detail": "directory absent"})
    return findings


def check_environment(cli_tool: "str | None") -> "tuple[list[dict], list[dict]]":
    """Return (findings, infos). Findings are blocking/remediable;
    infos are non-finding ``event=info`` lines (e.g. bash absent on a
    not-yet-classified project — addendum §6.5)."""
    findings: "list[dict]" = []
    infos: "list[dict]" = []
    if sys.version_info < (3, 10):
        findings.append({
            "code": "python_version_too_old", "kind": "python_version",
            "path": "<runtime>",
            "detail": f"{sys.version_info.major}.{sys.version_info.minor} < 3.10",
        })
    for import_name, dist_name in PYTHON_PKG_IMPORT_TO_DIST.items():
        if importlib.util.find_spec(import_name) is None:
            findings.append({"code": "python_pkg_missing",
                             "kind": "python_pkg",
                             "path": import_name,
                             "dist": dist_name,
                             "detail": f"{import_name} not importable"})
    if cli_tool:
        if shutil.which(cli_tool) is None:
            findings.append({"code": "ai_cli_not_on_path",
                             "kind": "cli_on_path", "path": cli_tool,
                             "detail": f"{cli_tool} not on PATH"})
    if shutil.which("bash") is None:
        # Phase 0 cannot classify the target's project type, so the
        # *blocked* mechanical-required variant is out of scope here;
        # emit the auto-passable info per addendum §6.5.
        infos.append({"event": "info", "bash": "unavailable",
                       "mechanical_verification": "not_applicable"})
    return findings, infos


# ---------------------------------------------------------------------------
# Run-nonce + disk witness
# ---------------------------------------------------------------------------


def _write_witness(target: Path, nonce: str, iso_ts: str,
                    ctx: str, root: Path, argv: "list[str]") -> Path:
    """Create <target>/quality/ if needed and write the immutable
    nonce witness file. Filename uses a Windows-safe compact timestamp
    (isoformat contains ':' which is invalid in Windows filenames);
    the full ISO timestamp is in the file body and emitted lines."""
    qdir = target / "quality"
    qdir.mkdir(parents=True, exist_ok=True)
    fts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    witness = qdir / f".qpb_validation_{fts}_{nonce}.txt"
    body = (
        f"nonce={nonce}\n"
        f"timestamp={iso_ts}\n"
        f"cwd={Path.cwd()}\n"
        f"argv={argv}\n"
        f"platform={platform_kind()}\n"
        f"invocation_context={ctx}\n"
        f"validator_root={root}\n"
        f"target={target}\n"
    )
    witness.write_text(body, encoding="utf-8")
    return witness


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="qpb_validate",
        description="QPB Phase 0 install validator (addendum r3 §3.1).",
    )
    p.add_argument("target", nargs="?", default=None,
                   help="absolute path to the target project (auto-"
                        "detected from cwd markers if omitted)")
    p.add_argument("--ai-tool", default=None,
                   help="explicit AI tool "
                        "(claude|cursor|copilot|continue|codex|windsurf|cline|aider)")
    return p


def _is_recent_run_start(line: str, *, now: "datetime | None" = None,
                         window_hours: int = 24) -> bool:
    """True iff `line` carries a `ts` value within `window_hours` of
    now. Dependency-free parse (no json/re — qpb_validate intentionally
    keeps a minimal stdlib import surface): the timestamp is the first
    quoted value following the ``"ts"`` key. Any parse/format failure
    is treated as "not recent" — the conservative direction, since a
    stale-but-unparseable marker should still block (A-20)."""
    i = line.find('"ts"')
    if i == -1:
        return False
    rest = line[i + 4:]
    colon = rest.find(":")
    if colon == -1:
        return False
    rest = rest[colon + 1:]
    q1 = rest.find('"')
    if q1 == -1:
        return False
    q2 = rest.find('"', q1 + 1)
    if q2 == -1:
        return False
    try:
        ts = datetime.fromisoformat(rest[q1 + 1:q2].strip())
    except ValueError:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    cur = now or datetime.now(timezone.utc)
    return (cur - ts) <= timedelta(hours=window_hours)


def check_stale_quality_dir(target: Path) -> "list[dict]":
    """Return findings if <target>/quality/ contains files but no
    active-run marker. An active-run marker is presence of
    quality/run_state.jsonl with at least one event=run_start line
    whose ts is within the last 24 hours (a heuristic for "active or
    very recent" — older state is treated as stale).

    Why 24h: arbitrary but generous; longer than any plausible
    in-flight run, shorter than a "definitely stale" gap.
    """
    findings: "list[dict]" = []
    qdir = target / "quality"
    if not qdir.is_dir():
        return findings
    # Non-empty check: any file (skip dotfiles like .qpb_validation_*
    # which the validator itself writes — those are witness artifacts,
    # not playbook state, and would create a chicken-and-egg loop).
    # v1.5.7 087 (A-24 reconciliation): quality/RUN_INDEX.md is the
    # install-time sentinel install_skill.py creates so the gitignore
    # template's `!quality/RUN_INDEX.md` negation rule + run_playbook
    # pre-flight are satisfied. It is an install sentinel, NOT a
    # prior-run artifact — excluding it (same rationale as the
    # validator-witness dotfiles) keeps a freshly-installed quality/
    # from being mis-flagged as a stale run that blocks every adopter
    # at Phase 0.
    _STALE_EXCLUDED_NAMES = {"RUN_INDEX.md"}
    visible = [
        p for p in qdir.rglob("*")
        if p.is_file() and not p.name.startswith(".")
        and p.name not in _STALE_EXCLUDED_NAMES
    ]
    if not visible:
        return findings
    # Active-run marker check.
    run_state = qdir / "run_state.jsonl"
    if run_state.is_file():
        try:
            for line in run_state.read_text(encoding="utf-8").splitlines():
                if ('"event": "run_start"' in line
                        or "event=run_start" in line):
                    if _is_recent_run_start(line):
                        return findings
        except OSError:
            pass
    findings.append({
        "code": "stale_quality_dir",
        "kind": "install_hygiene",
        "path": "quality/",
        "detail": (
            f"{len(visible)} file(s) under quality/ without an active-run marker"
        ),
    })
    return findings


def main(argv: "list[str] | None" = None) -> int:
    args = _build_parser().parse_args(argv)
    argv_list = list(sys.argv[1:] if argv is None else argv)

    script_path = Path(__file__)
    ctx, root = detect_invocation_context(script_path)
    cwd = Path.cwd()

    target, markers = detect_target(args.target, cwd)

    # §3.6 edge: validator run from inside the clone with no explicit
    # target -> blocked (don't silently treat the clone as the target).
    # The signal is "the auto-detected target resolved to the clone
    # root itself" — robust even though the QPB clone carries its own
    # .claude/ + .github/ marker dirs (which would otherwise look like
    # an ambiguous multi-marker target).
    if (args.target is None and ctx == "clone"
            and target.resolve() == root.resolve()):
        nonce = uuid.uuid4().hex
        iso_ts = datetime.now(timezone.utc).isoformat()
        em = Emitter(nonce)
        em.emit("invocation_context", location=ctx, root=root)
        plat = platform_kind()
        em.emit("remediation_suggestion", tool="clarify_target",
                finding="validator_invoked_from_clone", severity="blocked",
                command=command_for_platform(
                    "validator_invoked_from_clone", clone=str(root)),
                rationale=FINDING_CATALOG["validator_invoked_from_clone"]["rationale"],
                verify_with=FINDING_CATALOG["validator_invoked_from_clone"]["verify_with"])
        em.emit("validation_complete", status="blocked", findings=1,
                ts=iso_ts)
        return 2

    nonce = uuid.uuid4().hex
    iso_ts = datetime.now(timezone.utc).isoformat()
    witness = _write_witness(target, nonce, iso_ts, ctx, root, argv_list)
    em = Emitter(nonce)
    em.emit("invocation_context", location=ctx, root=root,
            witness=witness.name)

    plat = platform_kind()
    shell = windows_shell_kind() if plat == "windows" else "n/a"
    em.emit("platform_detected", kind=plat, shell=shell)

    # §3.6 edge: multiple AI-tool markers + no explicit --ai-tool.
    if len(markers) > 1 and not args.ai_tool:
        em.emit("target_resolved", target=target, markers=",".join(markers))
        em.emit("remediation_suggestion", tool="select_ai_tool",
                finding="multiple_ai_tool_markers", severity="blocked",
                command=command_for_platform("multiple_ai_tool_markers"),
                rationale=FINDING_CATALOG["multiple_ai_tool_markers"]["rationale"],
                verify_with=FINDING_CATALOG["multiple_ai_tool_markers"]["verify_with"])
        em.emit("validation_complete", status="blocked", findings=1,
                ts=iso_ts)
        return 2

    marker, tool = detect_ai_tool(markers, args.ai_tool)
    em.emit("target_resolved", target=target,
            marker=marker or "none", ai_tool=tool or "unknown")

    pkg_mgrs = detect_package_managers()
    em.emit("package_managers",
            **{k: ("yes" if v else "no") for k, v in pkg_mgrs.items()})

    findings: "list[dict]" = []

    # v1.5.7 A-20 reframed (instruction 084): run the stale-quality
    # hygiene check FIRST so an agent that found a stale quality/ tree
    # from a prior aborted run sees a blocked finding before it can
    # mis-read the artifacts as a resumable run and skip Phase 0.
    stale_findings = check_stale_quality_dir(target)
    for f in stale_findings:
        em.emit("install_hygiene_check", path=f["path"], kind=f["kind"],
                status="fail", detail=f["detail"])
    findings.extend(stale_findings)

    # install_wrong_ai_tool: requested tool's path absent while a
    # different marker's install is present.
    if args.ai_tool and marker and len(markers) >= 1 and marker not in markers:
        present = [m for m in markers if (target / MARKER_TO_INSTALL_REL[m]).exists()]
        if present:
            findings.append({
                "code": "install_wrong_ai_tool", "kind": "skill_doc",
                "path": MARKER_TO_INSTALL_REL.get(marker, "?"),
                "detail": f"requested {args.ai_tool} but install present at {present}",
            })

    if marker:
        install_root = target / MARKER_TO_INSTALL_REL[marker]
    else:
        install_root = target / ".claude" / "skills" / "quality-playbook"
    closure_findings = check_closure(install_root)
    for f in closure_findings:
        em.emit("closure_check", path=f["path"], kind=f["kind"],
                status="fail", detail=f["detail"])
    findings.extend(closure_findings)

    scaffold_findings = check_scaffolding(target)
    for f in scaffold_findings:
        em.emit("scaffolding_check", path=f["path"], kind=f["kind"],
                status="fail", detail=f["detail"])
    findings.extend(scaffold_findings)

    cli_tool = MARKER_TO_CLI.get(marker) if marker else None
    env_findings, infos = check_environment(cli_tool)
    for f in env_findings:
        em.emit("environment_check", path=f["path"], kind=f["kind"],
                status="fail", detail=f["detail"])
    for info in infos:
        em.emit(info.pop("event"), **info)
    findings.extend(env_findings)

    # Emit one remediation_suggestion per finding (§3.1 step 12).
    subs = {
        "clone": str(root) if ctx == "clone" else "<path-to-your-QPB-clone>",
        "root": str(root),
        "target": str(target),
        "tool": tool or "<tool>",
    }
    for f in findings:
        code = f["code"]
        cat = FINDING_CATALOG[code]
        local_subs = dict(subs)
        if code == "python_pkg_missing":
            local_subs["pkg"] = f.get("dist", f["path"])
        em.emit("remediation_suggestion", tool=cat["tool"], finding=code,
                severity=cat["severity"],
                command=command_for_platform(code, pkg_mgrs=pkg_mgrs,
                                              **local_subs),
                rationale=cat["rationale"], verify_with=cat["verify_with"])

    n = len(findings)
    if n == 0:
        em.emit("validation_complete", status="ok", findings=0, ts=iso_ts)
        return 0
    if any(FINDING_CATALOG[f["code"]]["severity"] == "blocked"
           for f in findings):
        em.emit("validation_complete", status="blocked", findings=n,
                ts=iso_ts)
        return 2
    em.emit("validation_complete", status="remediable", findings=n,
            ts=iso_ts)
    return 1


if __name__ == "__main__":
    sys.exit(main())
