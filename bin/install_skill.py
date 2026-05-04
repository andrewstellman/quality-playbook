"""bin/install_skill.py — turnkey AI-agent-driven Quality Playbook installer.

Copies SKILL.md, quality_gate.py, and the references/ subtree from a QPB
checkout into a target AI-tool skills directory. Auto-detects known tool
environments (.claude, .github, .cursor, .continue) in the working
directory, or scans a target repo via --into <target-repo>; falls back
to --target <path> for arbitrary install locations.
Cross-platform (macOS / Linux / Windows) via pathlib + explicit utf-8
encoding + explicit newline handling.

Default invocation mode is by an AI coding agent (Claude Code, Cursor, the
GitHub Copilot CLI, etc.) acting on behalf of an adopter. The default
output format is one event per line, key=value pairs, so the calling
agent can parse results without natural-language interpretation. Pass
--verbose for human-friendly prose alongside the structured output.

Usage:

    python -m bin.install_skill                            # auto-detect from cwd
    python -m bin.install_skill --into /path/to/target    # scan target repo
    python -m bin.install_skill --target /path/to/skill   # explicit target
    python -m bin.install_skill --source /qpb-clone       # explicit source root
    python -m bin.install_skill --no-smoke                # skip smoke check
    python -m bin.install_skill --force                   # overwrite without backup
    python -m bin.install_skill --verbose                 # human prose alongside

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
]


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
    return files


# Frontmatter keys required for the smoke check.
_REQUIRED_FRONTMATTER_KEYS = ("version", "name", "description")
# Pattern 7 anchor used by the exploration-patterns smoke check.
_PATTERN_7_ANCHOR_RE = re.compile(r"^##+\s+Pattern\s+7\b", re.MULTILINE)


# ---------------------------------------------------------------------------
# Output emission
# ---------------------------------------------------------------------------


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
    name and exits 1). We use the equivalent: py_compile, which proves
    the file is syntactically valid Python and importable, without
    executing any top-level code.
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
            [sys.executable, "-m", "py_compile", str(gate)],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode != 0:
            emitter.emit(
                "smoke_check", check="quality_gate_help", status="failed",
                detail=f"py_compile-exit-{result.returncode}",
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
        prose="quality_gate.py loads as valid Python (py_compile OK)",
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
    source_root: Optional[Path] = None,
    cwd: Optional[Path] = None,
    force: bool = False,
    no_smoke: bool = False,
    verbose: bool = False,
    stream=None,
) -> int:
    """Run the install. Returns the exit code (0 success; 64 usage refusal;
    65 smoke-check failure or downgrade refusal)."""
    emitter = Emitter(verbose=verbose, stream=stream)
    cwd = cwd or Path.cwd()
    source_root = (
        source_root.resolve() if source_root is not None
        else find_source_root(Path(__file__))
    )
    if target is not None and into is not None:
        emitter.emit(
            "refuse",
            reason="target-and-into-mutually-exclusive",
            target=str(target),
            into=str(into),
            prose="--target and --into cannot be used together",
        )
        return 64
    if into is not None:
        into = into.resolve()
        detected = detect_environment(into)
        if detected is None:
            envs = ", ".join(name for name, _ in KNOWN_ENVIRONMENTS)
            emitter.emit(
                "refuse",
                reason="no-environment-detected-in-target",
                target=str(into),
                known_envs=envs,
                prose=(
                    f"No known AI-tool environment found inside target repo {into}. "
                    f"Known environments: {envs}. "
                    f"Pass --target <path> to install to a custom location."
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
                "refuse", reason="no-environment-detected",
                known_envs=envs,
                prose=(
                    f"No known AI-tool environment found in {cwd}. "
                    f"Known environments: {envs}. "
                    f"Run from the target repo root, or pass --into <target-repo> "
                    f"or --target <path>."
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

    bundle = _bundle_files(source_root)
    statuses: list[str] = []
    for src, dst_rel in bundle:
        dst = target / dst_rel
        statuses.append(copy_with_backup(src, dst, force=force, emitter=emitter))

    smoke_failed = 0
    if not no_smoke:
        if not smoke_check_quality_gate(target, emitter):
            smoke_failed += 1
        if not smoke_check_skill_md_frontmatter(target, emitter):
            smoke_failed += 1
        if not smoke_check_exploration_patterns(target, emitter):
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
        source_root=args.source,
        force=args.force,
        no_smoke=args.no_smoke,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
