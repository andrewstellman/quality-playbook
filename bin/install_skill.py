"""bin/install_skill.py — turnkey AI-agent-driven Quality Playbook installer.

Copies the skill files (SKILL.md, quality_gate.py, references/,
phase_prompts/, agents/, and bin/citation_verifier.py) from a QPB
checkout into a target AI-tool skills directory. Auto-detects known
tool environments (.claude, .github, .cursor, .continue) in the
working directory, or scans a target repo via --into <target-repo>;
falls back to --target <path> for arbitrary install locations.
Cross-platform (macOS / Linux / Windows) via pathlib + explicit utf-8
encoding + explicit newline handling.

Default invocation mode is by an AI coding agent (Claude Code, Cursor, the
GitHub Copilot CLI, etc.) acting on behalf of an adopter. The default
output format is one event per line, key=value pairs, so the calling
agent can parse results without natural-language interpretation. Pass
--verbose for human-friendly prose alongside the structured output.

Usage:

    python3 -m bin.install_skill                            # auto-detect from cwd
    python3 -m bin.install_skill --into /path/to/target    # scan target repo
    python3 -m bin.install_skill --target /path/to/skill   # explicit target
    python3 -m bin.install_skill --source /qpb-clone       # explicit source root
    python3 -m bin.install_skill --no-smoke                # skip smoke check
    python3 -m bin.install_skill --force                   # overwrite without backup
    python3 -m bin.install_skill --verbose                 # human prose alongside

Exit codes: 0 on success; 64 (EX_USAGE) on bad invocation or refusal;
65 (EX_DATAERR) on smoke-check failure or downgrade refusal.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


# Detection table — first matching environment in the target's working
# directory wins. Adding a new tool is a one-line config change here.
KNOWN_ENVIRONMENTS: list[tuple[str, str]] = [
    (".claude", ".claude/skills/quality-playbook"),
    (".github", ".github/skills/quality-playbook"),
    (".cursor", ".cursor/skills/quality-playbook"),
    (".continue", ".continue/skills/quality-playbook"),
    # v1.5.7 instruction 046 (A-3) — expansion to the 10-layout
    # fallback (was 6). New marker dirs auto-detected by
    # detect_environment in the same order as SKILL_FALLBACK_GUIDE.
    (".codex", ".codex/skills/quality-playbook"),
    (".windsurf", ".windsurf/skills/quality-playbook"),
    (".cline", ".cline/skills/quality-playbook"),
    (".aider", ".aider/skills/quality-playbook"),
]


# v1.5.6 instruction 064: explicit AI-tool selection map. Used by
# --ai-tool <name>; bypasses marker-directory auto-detection so the
# installer works even when the AI tool hasn't created its config
# folder yet (notably Cursor and GitHub Copilot on first project open).
# 'github' is an alias for 'copilot' — both map to .github/skills/.
AI_TOOL_MAP: dict[str, tuple[str, str]] = {
    "cursor": (".cursor", ".cursor/skills/quality-playbook"),
    "claude": (".claude", ".claude/skills/quality-playbook"),
    "copilot": (".github", ".github/skills/quality-playbook"),
    "github": (".github", ".github/skills/quality-playbook"),
    "continue": (".continue", ".continue/skills/quality-playbook"),
    # v1.5.7 instruction 046 (A-3) — expansion to 10-layout fallback
    # (was 6). 'github' remains an alias for 'copilot'. aider does NOT
    # auto-discover from .aider/skills/ — see the aider footnote in
    # ai_context/TOOLKIT.md (surfaced for Cowork-direct application).
    "codex": (".codex", ".codex/skills/quality-playbook"),
    "windsurf": (".windsurf", ".windsurf/skills/quality-playbook"),
    "cline": (".cline", ".cline/skills/quality-playbook"),
    "aider": (".aider", ".aider/skills/quality-playbook"),
}
AI_TOOL_CHOICES: tuple[str, ...] = tuple(AI_TOOL_MAP.keys())


# Bundle source paths, relative to the QPB clone root. Each tuple is
# (source-relative-to-clone, dest-relative-to-target).
def _bundle_files(source_root: Path) -> list[tuple[Path, Path]]:
    """Enumerate every file the install bundle copies, with each file's
    destination path relative to the install target."""
    files: list[tuple[Path, Path]] = [
        (source_root / "SKILL.md", Path("SKILL.md")),
        # quality_gate.py canonical location is
        # .github/skills/quality_gate/quality_gate.py within the QPB
        # clone — the file at .github/skills/quality_gate.py is a
        # 28-byte stub pointing here. (Tracked in v1.5.6 follow-ups
        # alongside the Council Round 1 P1.2 install-path fix.) The
        # install bundle copies the real script to the target's
        # quality_gate.py at the install root, not nested.
        (source_root / ".github" / "skills" / "quality_gate" / "quality_gate.py",
         Path("quality_gate.py")),
    ]
    refs_src = source_root / "references"
    if refs_src.is_dir():
        for f in sorted(refs_src.glob("*.md")):
            files.append((f, Path("references") / f.name))
    # v1.5.6 BUG-001: phase_prompts/ are loaded at runtime by both Mode A
    # walkthroughs (per SKILL.md Mode A description, around line 62) and
    # Mode B's `bin/run_playbook.py::_load_phase_prompt`. The installer
    # MUST bundle them — installs that omit phase_prompts/ produce a
    # bundle that looks complete but breaks Mode A on the first phase
    # boundary because phase{N}.md cannot be resolved.
    phase_prompts_src = source_root / "phase_prompts"
    if phase_prompts_src.is_dir():
        for f in sorted(phase_prompts_src.glob("*.md")):
            files.append((f, Path("phase_prompts") / f.name))
    # v1.5.6 cluster A (issue #1 concern 4): bundle agents/ alongside
    # references/ and phase_prompts/ so README Step 4's
    # `claude --agent agents/quality-playbook.agent.md` invocation
    # resolves at the install destination, not just inside the QPB
    # clone. Pre-fix the relative path only worked from the QPB
    # source tree — adopters running the documented invocation from
    # their own target repo got "agent file not found" because the
    # installer never copied the agents/ directory.
    agents_src = source_root / "agents"
    if agents_src.is_dir():
        for f in sorted(agents_src.glob("*.md")):
            files.append((f, Path("agents") / f.name))
    # v1.5.6 BUG-005: bundle bin/citation_verifier.py so quality_gate.py's
    # soft-import path resolves at the install destination instead of
    # silently falling back to the WARN path. Pre-fix the v1.5.1 byte-
    # equality citation check was effectively disabled in every
    # installed copy because the only working import path was the QPB
    # source clone itself. quality_gate.py's _VERIFIER_SEARCH_ROOTS
    # picks up bin/citation_verifier.py from the install root.
    citation_verifier_src = source_root / "bin" / "citation_verifier.py"
    if citation_verifier_src.is_file():
        files.append((citation_verifier_src, Path("bin") / "citation_verifier.py"))
    # v1.5.7 fix F-1: bundle bin/reference_docs_ingest.py so Phase 1's
    # `python -m bin.reference_docs_ingest` invocation resolves at the
    # install destination. Pre-fix, every benchmark target hard-stopped
    # at Phase 1 with ModuleNotFoundError because the script lived only
    # in the QPB clone, not at the install root. The module imports
    # `from bin import benchmark_lib`, so benchmark_lib.py must also be
    # bundled (next entry).
    reference_docs_ingest_src = source_root / "bin" / "reference_docs_ingest.py"
    if reference_docs_ingest_src.is_file():
        files.append((reference_docs_ingest_src, Path("bin") / "reference_docs_ingest.py"))
    # v1.5.7 fix F-1 (transitive): bundle bin/benchmark_lib.py because
    # reference_docs_ingest.py imports it at module load. benchmark_lib
    # has no internal bin/ dependencies (stdlib-only) so the bundle
    # closure terminates here.
    benchmark_lib_src = source_root / "bin" / "benchmark_lib.py"
    if benchmark_lib_src.is_file():
        files.append((benchmark_lib_src, Path("bin") / "benchmark_lib.py"))
    # v1.5.7 instruction 050 A-6.2: bundle the quality_playbook
    # closure so adopter Mode-A runs hitting Phase 4's
    # `python3 -m bin.quality_playbook semantic-check plan|assemble .`
    # invocation (per phase_prompts/phase4.md:26,43) resolve at the
    # install destination. Self-bootstrap masked this (cwd is the QPB
    # clone); an adopter Mode-A run against a non-Spec-Gap target with
    # Tier 1/2 REQs would hit ModuleNotFoundError at Phase 4.
    #
    # Closure traced (AST) from quality_playbook.py's imports + each
    # module's transitive `from .` imports:
    #   quality_playbook -> archive_lib, council_semantic_check,
    #                       migrate_v1_5_0_layout
    #   archive_lib      -> role_map
    #   council_semantic_check -> archive_lib, benchmark_lib,
    #                             council_config
    #   migrate_v1_5_0_layout  -> archive_lib
    #   role_map / council_config -> (no internal bin. imports)
    # benchmark_lib was bundled in 049 (A-6.1); the remaining 6 land
    # here. __init__.py is required for the `from .` package syntax
    # to resolve at the install root.
    qpb_init_src = source_root / "bin" / "__init__.py"
    if qpb_init_src.is_file():
        files.append((qpb_init_src, Path("bin") / "__init__.py"))
    for _mod_name in (
        "quality_playbook.py",
        "archive_lib.py",
        "council_semantic_check.py",
        "migrate_v1_5_0_layout.py",
        "role_map.py",
        "council_config.py",
    ):
        _mod_src = source_root / "bin" / _mod_name
        if _mod_src.is_file():
            files.append((_mod_src, Path("bin") / _mod_name))
    # v1.5.7 instruction 086 (A-26): bundle the three remaining
    # adopter-facing bin/*.py modules SKILL.md / phase_prompts hard-
    # reference but the install bundle previously omitted. Surfaced
    # 2026-05-18 by the Copilot CLI Mode B on httpx (then the
    # `gh copilot` extension; superseded by the standalone `copilot`
    # CLI per 089f): agent honestly ran Phase 1, tried `python3 -m
    # bin.validate_phase_artifacts . --phase 1` per
    # phase_prompts/phase1.md:79-81, hit ModuleNotFoundError,
    # correctly diagnosed the bundle gap. The Mode A runs that
    # succeeded (cobra Claude Code, click codex CLI, gson Claude Code)
    # only worked because Claude Code / codex CLI have lax filesystem
    # sandboxes that silently fell back to running modules from the
    # QPB source clone; sandboxed agents (Copilot CLI, codex desktop
    # subprocess) hit hard ImportError. Bundling these three closes
    # the adopter-path bundle gap.
    #
    # Why these three specifically (and no others): grep SKILL.md +
    # phase_prompts/*.md for `bin\.[a-z_]+` → the union of referenced
    # module names, minus the modules already bundled above, minus the
    # two QPB-operator-side entry points adopters do NOT run from
    # install_root (bin.run_playbook is the Mode-B harness invoked
    # from the QPB clone; bin.qpb_validate is the Phase 0 entry-point
    # also invoked from the QPB clone per SKILL.md:681 / README
    # Step 4). What remains: run_state_lib, validate_phase_artifacts,
    # qpb_config.
    #
    # Import closure: run_state_lib.py + qpb_config.py are stdlib-only
    # (no `from bin` / `import bin` at module level);
    # validate_phase_artifacts.py's only internal import is
    # `from bin import role_map` (with an `import role_map` fallback)
    # and role_map.py is already bundled by the 050 A-6.2 loop above.
    # Closure terminates after these three additions.
    for _mod_name in (
        "run_state_lib.py",
        "validate_phase_artifacts.py",
        "qpb_config.py",
    ):
        _mod_src = source_root / "bin" / _mod_name
        if _mod_src.is_file():
            files.append((_mod_src, Path("bin") / _mod_name))
    return files


# Frontmatter keys required for the smoke check.
_REQUIRED_FRONTMATTER_KEYS = ("version", "name", "description")
# Pattern 7 anchor used by the exploration-patterns smoke check.
_PATTERN_7_ANCHOR_RE = re.compile(r"^##+\s+Pattern\s+7\b", re.MULTILINE)


# ---------------------------------------------------------------------------
# Output emission
# ---------------------------------------------------------------------------


# v1.5.7 instruction 089j — attribution banner printed to stderr at
# install start (BEFORE the first ``event=`` emission). stderr keeps
# stdout's machine-parseable ``event=key=value`` stream pure for
# calling agents; the banner is for the human running the install.
# Adopters see project name + author + URL + tagline + license at
# the moment they pull the skill in. The five elements (name,
# author, URL, tagline, license) are the required deliverable;
# box-drawing is presentational.
_BANNER_NAME = "Quality Playbook"
_BANNER_AUTHOR = "Andrew Stellman"
_BANNER_URL = "https://github.com/andrewstellman/quality-playbook"
_BANNER_TAGLINE = "Quality engineering that finds the bugs review misses."
_BANNER_LICENSE = "Apache License, Version 2.0"

_BANNER_TEXT = (
    "============================================================\n"
    f"  {_BANNER_NAME} — by {_BANNER_AUTHOR}\n"
    f"  {_BANNER_URL}\n"
    "\n"
    f"  {_BANNER_TAGLINE}\n"
    "\n"
    f"  Licensed under the {_BANNER_LICENSE}\n"
    "============================================================\n"
)


def _print_banner(stream=None) -> None:
    """Write the install-time attribution banner to ``stream``
    (default ``sys.stderr``). Always called BEFORE the first
    ``event=`` emission so the stdout event stream stays parse-
    clean for calling agents. Idempotent on stream errors — the
    banner is informational; a broken stderr must not break the
    install.
    """
    target = stream if stream is not None else sys.stderr
    try:
        target.write(_BANNER_TEXT)
        target.flush()
    except (OSError, ValueError):
        pass


class Emitter:
    """Structured key=value output for AI-agent consumption, plus optional
    human-prose lines under --verbose. Both go to stdout; smoke-failure
    diagnostics go to stderr separately."""

    def __init__(self, verbose: bool = False, stream=None) -> None:
        self.verbose = verbose
        self.stream = stream if stream is not None else sys.stdout

    def emit(self, event: str, prose: str = "", **fields: object) -> None:
        parts = [f"event={event}"]
        for key, value in fields.items():
            parts.append(f"{key}={_escape_value(value)}")
        line = " ".join(parts)
        print(line, file=self.stream)
        if self.verbose and prose:
            print(f"  {prose}", file=self.stream)


def _escape_value(value: object) -> str:
    s = str(value)
    if " " in s or "=" in s:
        return f'"{s}"'
    return s


# ---------------------------------------------------------------------------
# Detection + source-root discovery
# ---------------------------------------------------------------------------


def detect_environment(cwd: Path) -> Optional[tuple[str, Path]]:
    """Scan ``cwd`` for a known tool environment marker. Returns
    (env_name, target_install_path) on the first match, or None if no
    known environment is present."""
    for marker, dest_rel in KNOWN_ENVIRONMENTS:
        if (cwd / marker).is_dir():
            return (marker, cwd / dest_rel)
    return None


def find_source_root(script_path: Path) -> Path:
    """Resolve the QPB clone root from the install script's location.
    The script lives at <clone>/bin/install_skill.py."""
    return script_path.resolve().parent.parent


# ---------------------------------------------------------------------------
# File copy with backup
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# v1.5.7 instruction 087 (A-24): install-time sentinel-file creation.
# The gitignore template the Phase 0 validator emits for
# scaffolding_missing_gitignore contains `!informal_docs/README.md`
# and `!quality/RUN_INDEX.md` negation rules; without the files
# themselves, run_playbook.py's pre-flight aborts with "Required
# sentinel files missing". Adopter had to create them by hand on
# first run. Surfaced 2026-05-18 (httpx Terminal A; codex desktop
# express).
_SENTINEL_FILES: list[tuple[str, str]] = [
    (
        "informal_docs/README.md",
        "# Informal Docs\n\n"
        "Place non-citable plaintext project context here for "
        "Quality Playbook runs.\n",
    ),
    (
        "quality/RUN_INDEX.md",
        "# Run Index\n\n"
        "This directory holds Quality Playbook run artifacts. "
        "See <https://github.com/andrewstellman/quality-playbook> "
        "for details.\n",
    ),
]


def _ensure_sentinel_files(repo_root: Path, emitter: Emitter) -> None:
    """Create the two sentinel files the gitignore template's negation
    rules require, if they don't already exist (or are empty).
    Preserves operator content — a no-op when the file already has
    content (A-24; instruction-087 Things-to-NOT-do)."""
    for rel_path, default_content in _SENTINEL_FILES:
        dst = repo_root / rel_path
        if dst.exists() and dst.stat().st_size > 0:
            emitter.emit("sentinel_check", path=rel_path,
                         status="already_present")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(default_content, encoding="utf-8")
        emitter.emit("sentinel_create", path=rel_path, status="created",
                     bytes=len(default_content))


def _migrate_flat_legacy_install(target: Path, emitter: Emitter) -> None:
    """A-23: when installing the v1.5.7 NESTED layout
    (`<marker>/skills/quality-playbook/`) and a v1.5.6-era FLAT
    SKILL.md coexists at `<marker>/skills/SKILL.md`, a marker-based
    resolver can load the older flat one (surfaced 2026-05-18 codex
    desktop misdirected express run). Rename the flat SKILL.md (and a
    flat quality_gate.py if present) to `<name>.legacy-<UTC-ts>` so it
    can no longer be resolved as canonical, while preserving it for
    inspection.

    Fires ONLY for the canonical nested layout — `target` is
    `<marker>/skills/quality-playbook` (target.parent.name == "skills"
    and target.name != "skills"). v1.5.7 install() always computes a
    nested target via AI_TOOL_MAP, so this never touches an
    intentional flat-only install (instruction-087 halt-condition)."""
    if target.parent.name != "skills" or target.name == "skills":
        return  # not the canonical nested layout — do not migrate
    flat_dir = target.parent  # <marker>/skills
    for fname in ("SKILL.md", "quality_gate.py"):
        flat = flat_dir / fname
        if not flat.is_file():
            continue
        base_new = flat_dir / f"{fname}.legacy-{_utc_timestamp()}"
        new_path = base_new
        n = 1
        while new_path.exists():  # idempotent: bump on collision
            new_path = flat_dir / f"{base_new.name}.{n}"
            n += 1
        flat.rename(new_path)
        emitter.emit("legacy_migrate", from_path=fname,
                     to_path=new_path.name, status="renamed")


def copy_with_backup(
    src: Path,
    dst: Path,
    *,
    force: bool,
    emitter: Emitter,
) -> str:
    """Copy ``src`` to ``dst``. Returns one of:
        "copied"       — destination did not exist or content matched (handled).
        "skipped"      — destination existed with byte-identical content.
        "backed_up"    — destination existed with different content; old version
                         preserved as ``<dst>.operator-backup-<UTC-ts>`` and new
                         version copied. (Only when ``force`` is False.)
        "overwritten"  — destination existed; new version copied without backup
                         (--force).
        "error"        — read or write failure (logged via emitter).
    """
    rel_dst = str(dst)
    try:
        if not src.is_file():
            emitter.emit(
                "copy", file=rel_dst, status="error",
                detail=f"missing-source-{src}",
                prose=f"source file missing: {src}",
            )
            return "error"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            src_bytes = src.read_bytes()
            dst_bytes = dst.read_bytes()
            if src_bytes == dst_bytes:
                emitter.emit(
                    "copy", file=rel_dst, status="skipped",
                    prose=f"already up-to-date: {rel_dst}",
                )
                return "skipped"
            if force:
                _atomic_write_bytes(dst, src_bytes)
                emitter.emit(
                    "copy", file=rel_dst, status="overwritten",
                    prose=f"overwritten (--force): {rel_dst}",
                )
                return "overwritten"
            backup = dst.with_name(
                f"{dst.name}.operator-backup-{_utc_timestamp()}"
            )
            shutil.copy2(dst, backup)
            _atomic_write_bytes(dst, src_bytes)
            emitter.emit(
                "copy", file=rel_dst, status="backed_up",
                backup_path=str(backup),
                prose=f"operator edits preserved → {backup.name}; new version copied",
            )
            return "backed_up"
        _atomic_write_bytes(dst, src.read_bytes())
        emitter.emit(
            "copy", file=rel_dst, status="copied",
            prose=f"copied: {rel_dst}",
        )
        return "copied"
    except OSError as exc:
        emitter.emit(
            "copy", file=rel_dst, status="error",
            detail=type(exc).__name__,
            prose=f"copy failed: {exc}",
        )
        return "error"


def _atomic_write_bytes(dst: Path, data: bytes) -> None:
    """Write ``data`` to ``dst`` via a same-directory temp file rename so
    a crash mid-write doesn't leave a partial destination."""
    tmp = dst.with_suffix(dst.suffix + ".install-tmp")
    tmp.write_bytes(data)
    tmp.replace(dst)


# ---------------------------------------------------------------------------
# Smoke checks
# ---------------------------------------------------------------------------


def smoke_check_quality_gate(target: Path, emitter: Emitter) -> bool:
    """Confirm quality_gate.py is loadable Python without running it.

    The instruction asked for "python <target>/quality_gate.py --help (or
    equivalent help-only call)". The current quality_gate.py does NOT
    recognize --help (its argparse-free CLI treats --help as a repo
    name and exits 1). We use the equivalent: compile the source text
    in a subprocess. This keeps the smoke check side-effect free;
    py_compile would leave __pycache__/ behind in the install tree.
    """
    gate = target / "quality_gate.py"
    if not gate.is_file():
        emitter.emit(
            "smoke_check", check="quality_gate_help", status="failed",
            detail="missing-quality_gate.py",
            prose="quality_gate.py not present at target",
        )
        return False
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; import sys; "
                    "source = Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace'); "
                    "compile(source, sys.argv[1], 'exec')"
                ),
                str(gate),
            ],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode != 0:
            emitter.emit(
                "smoke_check", check="quality_gate_help", status="failed",
                detail=f"compile-exit-{result.returncode}",
                prose=f"quality_gate.py syntax check failed: {result.stderr.strip()}",
            )
            return False
    except (subprocess.TimeoutExpired, OSError) as exc:
        emitter.emit(
            "smoke_check", check="quality_gate_help", status="failed",
            detail=type(exc).__name__,
            prose=f"quality_gate.py syntax check failed: {exc}",
        )
        return False
    emitter.emit(
        "smoke_check", check="quality_gate_help", status="passed",
        prose="quality_gate.py loads as valid Python (compile OK)",
    )
    return True


def smoke_check_skill_md_frontmatter(target: Path, emitter: Emitter) -> bool:
    skill = target / "SKILL.md"
    if not skill.is_file():
        emitter.emit(
            "smoke_check", check="skill_md_frontmatter", status="failed",
            detail="missing-SKILL.md",
            prose="SKILL.md not present at target",
        )
        return False
    text = skill.read_text(encoding="utf-8", errors="replace")
    fm = _parse_yaml_frontmatter(text)
    if fm is None:
        emitter.emit(
            "smoke_check", check="skill_md_frontmatter", status="failed",
            detail="parse-failed",
            prose="SKILL.md frontmatter could not be parsed",
        )
        return False
    missing = [k for k in _REQUIRED_FRONTMATTER_KEYS if k not in fm]
    if missing:
        emitter.emit(
            "smoke_check", check="skill_md_frontmatter", status="failed",
            detail=f"missing-keys-{','.join(missing)}",
            prose=f"SKILL.md frontmatter missing keys: {missing}",
        )
        return False
    emitter.emit(
        "smoke_check", check="skill_md_frontmatter", status="passed",
        version=fm.get("version", "<unknown>"),
        prose=f"SKILL.md frontmatter OK (version={fm.get('version')})",
    )
    return True


def smoke_check_exploration_patterns(target: Path, emitter: Emitter) -> bool:
    path = target / "references" / "exploration_patterns.md"
    if not path.is_file():
        emitter.emit(
            "smoke_check", check="exploration_patterns_loaded",
            status="failed", detail="missing-exploration_patterns.md",
            prose="references/exploration_patterns.md not present at target",
        )
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if not _PATTERN_7_ANCHOR_RE.search(text):
        emitter.emit(
            "smoke_check", check="exploration_patterns_loaded",
            status="failed", detail="missing-pattern-7-anchor",
            prose="exploration_patterns.md missing the Pattern 7 structural anchor",
        )
        return False
    emitter.emit(
        "smoke_check", check="exploration_patterns_loaded", status="passed",
        prose="references/exploration_patterns.md loaded; Pattern 7 anchor found",
    )
    return True


def smoke_check_bundle_presence(
    target: Path, source_root: Path, emitter: Emitter,
) -> bool:
    """v1.5.7 BUG-003: assert every bundle member landed at the install
    destination.

    Pre-fix the smoke check covered only three specific files
    (quality_gate.py, SKILL.md frontmatter, exploration_patterns.md
    Pattern 7 anchor). A missing or corrupted bundle member elsewhere
    (e.g., agents/quality-playbook.agent.md, phase_prompts/phase5.md,
    bin/reference_docs_ingest.py, etc.) would slip through.

    Uses `_bundle_files(source_root)` as the single source of truth for
    "what should be installed" — the same list the installer's copy
    loop uses. No duplication; bundle additions in `_bundle_files`
    automatically expand this smoke check's surface.

    Each destination file must be present AND non-empty (zero-byte
    files indicate a truncated or failed copy). Python module bundle
    members are not parsed beyond size-check here; the runtime import
    in their first use will surface syntax errors.
    """
    missing: list[str] = []
    empty: list[str] = []
    for _src, dst_rel in _bundle_files(source_root):
        dst = target / dst_rel
        if not dst.is_file():
            missing.append(str(dst_rel))
            continue
        try:
            size = dst.stat().st_size
        except OSError:
            missing.append(str(dst_rel))
            continue
        if size == 0:
            empty.append(str(dst_rel))
    if missing or empty:
        emitter.emit(
            "smoke_check", check="bundle_presence", status="failed",
            detail=f"missing={missing};empty={empty}",
            prose=(
                f"bundle smoke check found "
                f"{len(missing)} missing + {len(empty)} empty file(s); "
                f"missing={missing!r}, empty={empty!r}"
            ),
        )
        return False
    emitter.emit(
        "smoke_check", check="bundle_presence", status="passed",
        prose=f"all {len(list(_bundle_files(source_root)))} bundle file(s) present and non-empty",
    )
    return True


def smoke_check_bundled_modules(target: Path, emitter: Emitter) -> bool:
    """v1.5.7 instruction 086 (A-26): the three adopter-facing modules
    bundled by 086 (run_state_lib, validate_phase_artifacts,
    qpb_config) must IMPORT cleanly as `bin.<module>` from the install
    root — not merely be present + non-empty
    (smoke_check_bundle_presence already covers presence/size). This
    reproduces the EXACT adopter path that 2026-05-18 gh-copilot-on-
    httpx hit ImportError on (`PYTHONPATH=<install_root> python3 -m
    bin.validate_phase_artifacts`), so it also exercises the real
    `from bin import role_map` closure resolving against the bundled
    role_map at the install root — not just a syntax check.

    Run in a subprocess with `-B` (no __pycache__ written into the
    install tree), mirroring smoke_check_quality_gate's side-effect-
    free pattern. (The in-process spec_from_file_location/exec_module
    approach is unreliable for dotted `bin.<name>` modules — no parent
    package in sys.modules → AttributeError.) Additive: does not
    change any existing smoke check.
    """
    try:
        result = subprocess.run(
            [
                sys.executable, "-B", "-c",
                (
                    "import sys; sys.path.insert(0, sys.argv[1]); "
                    "import bin.run_state_lib, "
                    "bin.validate_phase_artifacts, bin.qpb_config"
                ),
                str(target),
            ],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        emitter.emit(
            "smoke_check", check="bundled_modules", status="failed",
            detail=type(exc).__name__,
            prose=f"bundled-module import smoke check failed: {exc}",
        )
        return False
    if result.returncode != 0:
        emitter.emit(
            "smoke_check", check="bundled_modules", status="failed",
            detail=f"import-exit-{result.returncode}",
            prose=(f"bundled-module import failed at install root: "
                   f"{result.stderr.strip()[:500]}"),
        )
        return False
    emitter.emit(
        "smoke_check", check="bundled_modules", status="passed",
        prose="run_state_lib + validate_phase_artifacts + qpb_config "
              "import cleanly as bin.* from the install root",
    )
    return True


def _parse_yaml_frontmatter(text: str) -> Optional[dict[str, str]]:
    """Lightweight YAML-frontmatter parser sufficient for the smoke check.
    Recognizes ``key: value`` pairs between leading ``---`` fences,
    including pairs nested one level under a parent key (e.g.
    ``version`` under ``metadata:`` in QPB's SKILL.md). Nested keys are
    flattened into the same dict so both ``metadata.version`` and a
    bare top-level ``version:`` map to the ``version`` key. Returns
    None if no frontmatter block is present or if the block is
    malformed (no closing fence)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None
    fields: dict[str, str] = {}
    for raw in lines[1:end]:
        # Strip leading whitespace so nested keys (one level deep) are
        # captured. We don't model arbitrary nesting — adopters' SKILL.md
        # files put `version`, `name`, `description` either at top level
        # or under `metadata:`, both of which this flattening handles.
        stripped = raw.strip()
        if ":" not in stripped or stripped.startswith("#"):
            continue
        key, _, value = stripped.partition(":")
        value = value.strip().strip('"').strip("'")
        if not value:
            # Parent of a nested block — skip; the children will land
            # via their own iterations.
            continue
        # Last write wins; this is fine because the same key at top
        # level and inside metadata: would carry the same intended
        # value.
        fields[key.strip()] = value
    return fields


# ---------------------------------------------------------------------------
# Downgrade detection
# ---------------------------------------------------------------------------


def _read_skill_version(skill_path: Path) -> Optional[str]:
    if not skill_path.is_file():
        return None
    try:
        text = skill_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fm = _parse_yaml_frontmatter(text)
    if fm is None:
        return None
    return fm.get("version")


def _is_downgrade(installed: str, incoming: str) -> bool:
    """Compare semver-ish version strings. Returns True iff incoming <
    installed by lexical-tuple comparison of dotted integer parts."""
    def parts(v: str) -> tuple[int, ...]:
        out: list[int] = []
        for p in v.split("."):
            digits = re.match(r"\d+", p)
            out.append(int(digits.group(0)) if digits else 0)
        return tuple(out)
    try:
        return parts(incoming) < parts(installed)
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def install(
    *,
    target: Optional[Path] = None,
    into: Optional[Path] = None,
    ai_tool: Optional[str] = None,
    source_root: Optional[Path] = None,
    cwd: Optional[Path] = None,
    force: bool = False,
    no_smoke: bool = False,
    verbose: bool = False,
    stream=None,
    banner_stream=None,
) -> int:
    """Run the install. Returns the exit code (0 success; 64 usage refusal;
    65 smoke-check failure or downgrade refusal).

    Location resolution precedence:
      1. ``target`` (literal install path) — if set, used directly.
      2. ``ai_tool`` (canonical subdirectory) — if set, computes
         ``<into or cwd>/<marker>/skills/quality-playbook`` and creates
         the marker directory if missing.
      3. ``into`` (target repo root) — auto-detect AI-tool marker dir.
      4. cwd-based auto-detect — fallback for bare invocations.

    ``target`` is mutually exclusive with ``into`` and with ``ai_tool``.

    ``banner_stream`` (default ``sys.stderr``) is where the v1.5.7 089j
    attribution banner is written. Tests inject a buffer here to assert
    the banner-on-stderr / stdout-parse-clean contract. Production
    callers (``__main__``) get stderr.
    """
    # v1.5.7 089j: attribution banner FIRST, to stderr (or injected
    # banner_stream). MUST precede the first event= line so stdout
    # remains a clean machine-parseable stream for calling agents.
    _print_banner(banner_stream)

    emitter = Emitter(verbose=verbose, stream=stream)
    cwd = cwd or Path.cwd()
    source_root = (
        source_root.resolve() if source_root is not None
        else find_source_root(Path(__file__))
    )

    # v1.5.6 instruction 064: install explainer message at run start.
    # Brief explanation of what's happening + how to override detection.
    # v1.5.7 089d (F23): derive the marker list from the canonical
    # KNOWN_ENVIRONMENTS (8 markers post-046/A-3) instead of
    # hard-coding 4 of 8 (.cursor/.claude/.github/.continue). Pinned
    # by bin/tests/test_install_layouts_pinned.py.
    _intro_markers = "/, ".join(marker for marker, _ in KNOWN_ENVIRONMENTS) + "/"
    intro_short = (
        f"skill bundle installs into a tool-specific subdirectory; "
        f"auto-detection scans for the marker ({_intro_markers}); "
        f"pass --ai-tool <cursor|claude|copilot|continue|codex|windsurf|cline|aider> "
        f"to bypass detection"
    )
    intro_verbose = (
        "Installing the Quality Playbook skill. The skill files (SKILL.md, "
        "quality_gate.py, references/, phase_prompts/, agents/, "
        "bin/citation_verifier.py) install into a subdirectory specific "
        "to your AI coding tool — for example .cursor/skills/quality-playbook/ "
        "for Cursor, .claude/skills/quality-playbook/ for Claude Code. The "
        "installer detects which tool by looking for the marker directory in "
        "your target. If detection fails, pass "
        "--ai-tool <cursor|claude|copilot|continue|codex|windsurf|cline|aider> to specify explicitly."
    )
    emitter.emit("intro", prose=intro_verbose if verbose else intro_short)

    if target is not None and into is not None:
        emitter.emit(
            "refuse",
            reason="target-and-into-mutually-exclusive",
            target=str(target),
            into=str(into),
            prose="--target and --into cannot be used together",
        )
        return 64
    if target is not None and ai_tool is not None:
        emitter.emit(
            "refuse",
            reason="target-and-ai-tool-mutually-exclusive",
            target=str(target),
            ai_tool=ai_tool,
            prose=(
                "--target and --ai-tool cannot be used together: --target "
                "specifies a literal install path, --ai-tool specifies the "
                "canonical subdirectory for a named tool. Pick one."
            ),
        )
        return 64

    # v1.5.6 instruction 064: explicit AI-tool selection (bypasses
    # marker-directory auto-detection; creates the marker if missing).
    if ai_tool is not None:
        marker, dest_rel = AI_TOOL_MAP[ai_tool]
        base = into.resolve() if into is not None else cwd
        target = (base / dest_rel).resolve()
        marker_dir = (base / marker).resolve()
        marker_created = not marker_dir.exists()
        marker_dir.mkdir(parents=True, exist_ok=True)
        target.mkdir(parents=True, exist_ok=True)
        emitter.emit(
            "ai_tool_explicit",
            ai_tool=ai_tool,
            target=str(base),
            marker=marker,
            install_path=str(target),
            marker_created="yes" if marker_created else "no",
            prose=(
                f"--ai-tool {ai_tool} → install path {target} "
                f"(marker {marker} {'created' if marker_created else 'already present'})"
            ),
        )
    elif into is not None:
        into = into.resolve()
        detected = detect_environment(into)
        if detected is None:
            envs = ", ".join(name for name, _ in KNOWN_ENVIRONMENTS)
            emitter.emit(
                "detection_failed",
                target=str(into),
                markers_searched=envs,
                prose=(
                    f"no AI-tool marker directory found in {into}; "
                    f"searched: {envs}"
                ),
            )
            emitter.emit(
                "install_complete",
                status="failed",
                reason="no_marker_directory_found",
                prose=(
                    f"No AI tool marker directory found in {into}. The "
                    f"installer can't guess which AI tool you're using. To "
                    f"proceed:\n"
                    f"  (a) Pass --ai-tool <cursor|claude|copilot|continue|codex|windsurf|cline|aider> "
                    f"to specify explicitly:\n"
                    f"      python3 -m bin.install_skill --into {into} --ai-tool cursor\n"
                    f"  (b) Pass --target <absolute-path> to install to a "
                    f"specific path:\n"
                    f"      python3 -m bin.install_skill --target {into}/.cursor/skills/quality-playbook\n"
                    f"  (c) Open the target project in your AI tool first "
                    f"(which creates the marker directory), then re-run "
                    f"auto-detection."
                ),
            )
            return 64
        env_name, target = detected
        emitter.emit(
            "detected_env_inside_target",
            target=str(into),
            env=env_name,
            install_path=str(target),
            prose=f"detected {env_name}/ inside target repo; install path {target}",
        )
    elif target is None:
        detected = detect_environment(cwd)
        if detected is None:
            envs = ", ".join(name for name, _ in KNOWN_ENVIRONMENTS)
            emitter.emit(
                "detection_failed",
                target=str(cwd),
                markers_searched=envs,
                prose=(
                    f"no AI-tool marker directory found in {cwd}; "
                    f"searched: {envs}"
                ),
            )
            emitter.emit(
                "install_complete",
                status="failed",
                reason="no_marker_directory_found",
                prose=(
                    f"No AI tool marker directory found in {cwd}. The "
                    f"installer can't guess which AI tool you're using. To "
                    f"proceed:\n"
                    f"  (a) Pass --ai-tool <cursor|claude|copilot|continue|codex|windsurf|cline|aider> "
                    f"to specify explicitly:\n"
                    f"      python3 -m bin.install_skill --ai-tool cursor\n"
                    f"  (b) Pass --target <absolute-path> to install to a "
                    f"specific path:\n"
                    f"      python3 -m bin.install_skill --target {cwd}/.cursor/skills/quality-playbook\n"
                    f"  (c) Open the target project in your AI tool first "
                    f"(which creates the marker directory), then re-run "
                    f"auto-detection."
                ),
            )
            return 64
        env_name, target = detected
        emitter.emit(
            "detected_env", env=env_name, target=str(target),
            prose=f"detected {env_name}/, proposing target {target}",
        )
    else:
        target = target.resolve()
        emitter.emit(
            "target_explicit", target=str(target),
            prose=f"target specified explicitly: {target}",
        )

    # Downgrade refusal: if SKILL.md exists at target and its version is
    # higher than the source bundle's, refuse.
    incoming_version = _read_skill_version(source_root / "SKILL.md")
    installed_version = _read_skill_version(target / "SKILL.md")
    if (
        incoming_version is not None
        and installed_version is not None
        and _is_downgrade(installed_version, incoming_version)
    ):
        emitter.emit(
            "refuse", reason="downgrade",
            installed_version=installed_version,
            incoming_version=incoming_version,
            prose=(
                f"refusing downgrade: target SKILL.md is v{installed_version}; "
                f"bundle is v{incoming_version}"
            ),
        )
        return 65

    # v1.5.7 087 (A-23): rename any coexisting v1.5.6-era flat
    # SKILL.md BEFORE the nested bundle lands, so the nested install
    # is the only marker-resolvable canonical SKILL.md.
    _migrate_flat_legacy_install(target, emitter)

    bundle = _bundle_files(source_root)
    statuses: list[str] = []
    for src, dst_rel in bundle:
        dst = target / dst_rel
        statuses.append(copy_with_backup(src, dst, force=force, emitter=emitter))

    # v1.5.7 087 (A-24): create the gitignore-negation sentinel files
    # at the adopter repo root so run_playbook.py's pre-flight does
    # not abort with "Required sentinel files missing". The canonical
    # nested layout is <repo_root>/<marker>/skills/quality-playbook,
    # so repo_root == target.parents[2]. For an exotic explicit
    # --target that is not the nested layout, skip (operator-managed).
    if target.parent.name == "skills" and target.name != "skills":
        _ensure_sentinel_files(target.parents[2], emitter)
    else:
        emitter.emit("sentinel_check", path="(skipped)",
                     status="non_nested_target")

    smoke_failed = 0
    if not no_smoke:
        if not smoke_check_quality_gate(target, emitter):
            smoke_failed += 1
        if not smoke_check_skill_md_frontmatter(target, emitter):
            smoke_failed += 1
        if not smoke_check_exploration_patterns(target, emitter):
            smoke_failed += 1
        if not smoke_check_bundle_presence(target, source_root, emitter):
            smoke_failed += 1
        if not smoke_check_bundled_modules(target, emitter):
            smoke_failed += 1

    error_count = sum(1 for s in statuses if s == "error")
    if error_count > 0 or smoke_failed > 0:
        status = "failed" if (error_count > 0) else "partial"
        emitter.emit(
            "install_complete", status=status,
            errors=error_count, smoke_failed=smoke_failed,
            prose=(
                f"install completed with {error_count} copy error(s) and "
                f"{smoke_failed} smoke-check failure(s)"
            ),
        )
        return 65 if smoke_failed > 0 else 64
    # v1.5.7 instruction 058 A-11.2: teach the layout-aware Phase 1
    # ingest invocation. `bin/reference_docs_ingest.py` does
    # `from bin import benchmark_lib` at import, so `-m
    # bin.reference_docs_ingest` resolves only when `bin/` is a
    # reachable top-level package. For an install_skill.py-layout
    # adopter the bundled bin/ lives at <install_root>/bin/, NOT at
    # the target repo root — so the canonical bare invocation fails
    # with ModuleNotFoundError unless PYTHONPATH points at the
    # install root. Emitting the exact command here means an agent
    # (or human) reading the install output learns the correct form
    # even if SKILL.md is read inconsistently. The ABSOLUTE
    # install-root path is used (unambiguous + cwd-independent +
    # branch-independent — `target` is in scope on every success
    # path).
    # The full command (spaces) goes in `prose` (verbose-only),
    # NOT a structured field — the structured-output contract
    # (test_install_skill.StructuredOutputTests) requires
    # whitespace-free `key=value` fields in non-verbose mode.
    # `installed_at` is a single-token path (same convention as
    # ai_tool_explicit's install_path=).
    emitter.emit(
        "phase1_ingest_invocation_hint",
        installed_at=str(target),
        prose=(
            "Phase 1 invocation — from your target repo root, run:\n"
            f"  PYTHONPATH={target} python3 -m bin.reference_docs_ingest .\n"
            "(the bundled bin/ closure lives under the install root, "
            "not at the target repo root; the PYTHONPATH= prefix makes "
            "`-m bin.reference_docs_ingest` resolve)"
        ),
    )
    emitter.emit(
        "install_complete", status="success",
        errors=0, smoke_failed=0,
        files_copied=sum(1 for s in statuses if s != "skipped"),
        prose=f"install OK; target={target}",
    )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="install_skill",
        description=__doc__,
    )
    location_group = parser.add_mutually_exclusive_group()
    location_group.add_argument(
        "--target", type=Path, default=None,
        help="Explicit install path; overrides auto-detection.",
    )
    location_group.add_argument(
        "--into", type=Path, default=None,
        help=(
            "Target repo root to scan for AI-tool markers; installs into the "
            "matching skill path inside that repo."
        ),
    )
    parser.add_argument(
        "--ai-tool",
        choices=list(AI_TOOL_CHOICES),
        metavar="<name>",
        default=None,
        help=(
            "Explicitly select the target AI tool. Use when auto-detection "
            "can't find a marker directory (e.g., the AI tool hasn't created "
            "its config folder yet — common with Cursor and Copilot on first "
            "project open). Mutually exclusive with --target. 'github' is an "
            "alias for 'copilot'. Maps each tool to its canonical skill "
            "subdirectory: cursor -> .cursor/skills/quality-playbook/; "
            "claude -> .claude/skills/quality-playbook/; "
            "copilot -> .github/skills/quality-playbook/; "
            "continue -> .continue/skills/quality-playbook/; "
            "codex -> .codex/skills/quality-playbook/; "
            "windsurf -> .windsurf/skills/quality-playbook/; "
            "cline -> .cline/skills/quality-playbook/; "
            "aider -> .aider/skills/quality-playbook/ (aider does not "
            "auto-discover — tell aider to read SKILL.md explicitly)."
        ),
    )
    parser.add_argument(
        "--source", type=Path, default=None,
        help="QPB clone root to copy from (defaults to the parent of bin/install_skill.py).",
    )
    parser.add_argument(
        "--no-smoke", action="store_true",
        help="Skip the post-install smoke check.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing files without preserving as backup.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Emit human-prose lines alongside structured output.",
    )
    args = parser.parse_args(argv)
    return install(
        target=args.target,
        into=args.into,
        ai_tool=args.ai_tool,
        source_root=args.source,
        force=args.force,
        no_smoke=args.no_smoke,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
