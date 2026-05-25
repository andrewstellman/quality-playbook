"""QPB Test Harness — prep policies (acceptance + security).

Two sibling prep policies for the same engine (per
``QPB_Test_Harness_1.5.7_Design.md`` §B).

  * ``acceptance``: worktree → docs present → Phase-0 install.
    No scrub; the agent gets the full target.
  * ``security``: worktree → scrub ``reference_docs/`` of any
    leakage terms → **leakage-gate** (abort if the bug is still
    named in the scrubbed tree) → install.

The leakage-gate is the load-bearing security invariant: it
prevents the harness itself from accidentally feeding the answer
key into the run (e.g. a CVE number left in a scrubbed doc).
``ABORTED_PREP`` is the SCHEMA.md §6 terminal state set when
this fires; the run never starts.

Phase 1 supports ``install_channel=clone`` only (Phase 2 wires
local-wheel/local-tgz; Phase 6 wires registry). The clone install
path shells out to ``bin/install_skill.py``.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from bin.harness.schema import (
    Case,
    CaseType,
    InstallChannel,
    PrepPolicy,
    RunAxes,
    SchemaError,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PrepError(RuntimeError):
    """Prep failed — caller maps to ``ABORTED_PREP``. The reason
    string is human-readable and ends up in ``status.json``."""

    def __init__(self, reason: str, *, leakage_terms: "list[str] | None" = None):
        super().__init__(reason)
        self.reason = reason
        # Populated when the leakage-gate fires; carries the
        # specific terms that leaked so the operator can fix the
        # case or extend the scrub list.
        self.leakage_terms = leakage_terms or []


# ---------------------------------------------------------------------------
# Worktree / clone helpers
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: "Path | None" = None,
         check: bool = True) -> subprocess.CompletedProcess:
    """Thin wrapper for git subprocess calls. Captures stdout +
    stderr so prep failures carry context in the PrepError reason
    string."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True, text=True, check=check,
    )


def clone_worktree(repo_url: str, target_ref: "str | None",
                    dest: Path) -> str:
    """Clone ``repo_url`` into ``dest`` and check out ``target_ref``
    (a SHA or tag). Returns the resolved target SHA so the harness
    can record it in ``invocation.json.target_sha``.

    Phase 1 uses a straight ``git clone`` (Phase 4's manager will
    add the local-mirror cache; Phase 3's scheduler is what makes
    that worth the complexity). Best-effort for now.
    """
    if dest.exists():
        raise PrepError(
            f"clone_worktree: destination {dest} already exists"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        _git("clone", "--quiet", repo_url, str(dest))
    except subprocess.CalledProcessError as exc:
        raise PrepError(
            f"clone failed: {exc.stderr.strip() or exc}"
        )
    if target_ref:
        try:
            _git("checkout", "--quiet", target_ref, cwd=dest)
        except subprocess.CalledProcessError as exc:
            raise PrepError(
                f"checkout {target_ref!r} failed: "
                f"{exc.stderr.strip() or exc}"
            )
    try:
        sha = _git("rev-parse", "HEAD", cwd=dest).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise PrepError(
            f"could not resolve target SHA: "
            f"{exc.stderr.strip() or exc}"
        )
    return sha


# ---------------------------------------------------------------------------
# Reference-docs scrub (security only)
# ---------------------------------------------------------------------------


@dataclass
class ScrubManifest:
    """Records the files that were scrubbed + their pre-scrub
    hashes. Goes into ``invocation.json.scrubbed_docs_manifest``
    on security runs (acceptance runs leave this as ``None``).
    The hashes make the scrub auditable: a future run can re-scrub
    and compare to detect drift in either the source docs or the
    scrub terms."""
    files: "list[dict]"

    def to_json(self) -> dict:
        return {"files": self.files}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def scrub_reference_docs(reference_docs_dir: Path,
                          scrub_terms: "list[str]") -> ScrubManifest:
    """Scan ``reference_docs/`` recursively and delete files whose
    contents reference any of the ``scrub_terms`` (case-insensitive
    substring match). Records each removed file + its pre-scrub
    SHA-256 in the returned manifest.

    Per design §B / SCHEMA.md §1: this is the SECURITY prep step.
    Acceptance runs skip it entirely.
    """
    manifest_entries: list[dict] = []
    if not reference_docs_dir.is_dir():
        # No reference_docs/ to scrub — return empty manifest;
        # the leakage-gate below will still run against whatever
        # text content exists in the worktree to catch leakage in
        # other files (READMEs, etc.).
        return ScrubManifest(files=[])
    normalized_terms = [t.lower() for t in scrub_terms]
    for root, _dirs, names in os.walk(reference_docs_dir):
        for name in names:
            p = Path(root) / name
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            lower = text.lower()
            hit_terms = [t for t in normalized_terms if t in lower]
            if hit_terms:
                sha = _sha256_file(p)
                manifest_entries.append({
                    "path": str(p.relative_to(reference_docs_dir.parent)),
                    "sha256": sha,
                    "matched_terms": hit_terms,
                })
                p.unlink()
    return ScrubManifest(files=manifest_entries)


def leakage_gate(target_dir: Path, scrub_terms: "list[str]",
                 *, exclude_subdirs: "tuple[str, ...]" = (
                     ".git", "node_modules", "__pycache__",
                 )) -> "list[str]":
    """Re-scan the worktree post-scrub for any remaining occurrence
    of a scrub term. If any term still appears, returns the list of
    terms that leaked; the caller raises ``PrepError`` with the
    list to set ``ABORTED_PREP`` (SCHEMA.md §6).

    Conservative scan: text files only (binary content is skipped
    by the ``errors='ignore'`` decode + the case-insensitive
    substring match — false-positive cost is a halted run, never a
    leaked answer key).

    Excludes ``.git`` etc. by default so VCS metadata containing a
    SHA doesn't false-positive every security case.
    """
    normalized_terms = [t.lower() for t in scrub_terms]
    if not normalized_terms:
        return []
    leaked: set[str] = set()
    for root, dirs, names in os.walk(target_dir):
        # Mutate dirs in place to skip excluded subdirs.
        dirs[:] = [d for d in dirs if d not in exclude_subdirs]
        for name in names:
            p = Path(root) / name
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            lower = text.lower()
            for t in normalized_terms:
                if t in lower:
                    leaked.add(t)
            if len(leaked) == len(normalized_terms):
                # All terms already hit — short-circuit the walk.
                return sorted(leaked)
    return sorted(leaked)


# ---------------------------------------------------------------------------
# Phase-0 install
# ---------------------------------------------------------------------------


def _qpb_clone_root() -> Path:
    """Resolve the QPB clone root from this module's location.
    ``bin/harness/prepare.py`` → ``<qpb_root>``."""
    return Path(__file__).resolve().parents[2]


def install_skill_clone_channel(target_dir: Path, *,
                                  ai_tool: str = "claude",
                                  no_smoke: bool = True) -> None:
    """SCHEMA.md §3 ``clone`` channel: invoke
    ``python3 -m bin.install_skill --into <target> --ai-tool <tool>``
    from the QPB clone root.

    Phase 1 supports ``clone`` only. Phase 2 will fan this out to
    ``pip-local-wheel`` / ``npm-local-tgz`` via the channel-build
    harness.
    """
    qpb = _qpb_clone_root()
    cmd = [
        sys.executable, "-m", "bin.install_skill",
        "--into", str(target_dir),
        "--ai-tool", ai_tool,
    ]
    if no_smoke:
        cmd.append("--no-smoke")
    try:
        subprocess.run(
            cmd, cwd=str(qpb), check=True,
            capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise PrepError(
            f"install_skill (clone channel) failed: "
            f"{(exc.stderr or exc.stdout or '').strip()[-500:]}"
        )


# ---------------------------------------------------------------------------
# Reference-docs population (acceptance)
# ---------------------------------------------------------------------------


def populate_reference_docs(target_dir: Path,
                              reference_docs_source: str) -> None:
    """Acceptance prep: ensure ``reference_docs/`` is present in
    the target before the install step.

    Two source shapes per SCHEMA.md §1:
      * a path → copy the directory's contents into
        ``<target>/reference_docs/``;
      * the literal ``"gather"`` → no-op (the run is expected to
        gather docs itself; the harness leaves the dir alone for
        the agent to populate via Phase 1's
        ``reference_docs_ingest`` step).

    Phase 1 keeps this minimal — the broader doc-gathering harness
    is design's open question (E1 expansion).
    """
    if reference_docs_source == "gather":
        # Agent-driven gather — leave the dir absent / empty so
        # Phase-0 install creates it as part of scaffolding (see
        # 090h: reference_docs/ is the single adopter-doc location).
        return
    src = Path(reference_docs_source).expanduser()
    if not src.is_dir():
        raise PrepError(
            f"reference_docs_source {src} does not exist or is "
            f"not a directory"
        )
    dest = target_dir / "reference_docs"
    dest.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.is_file():
            shutil.copy2(entry, dest / entry.name)
        elif entry.is_dir():
            shutil.copytree(entry, dest / entry.name,
                            dirs_exist_ok=True)


# ---------------------------------------------------------------------------
# The top-level prep entry points
# ---------------------------------------------------------------------------


@dataclass
class PrepResult:
    """Returned by both prep policies on success. Captures the
    artifacts the harness will record in ``invocation.json``
    (target_sha, scrubbed_docs_manifest, leakage_gate)."""
    target_dir: Path
    target_sha: str
    scrubbed_docs_manifest: "dict | None" = None
    leakage_gate: "str | None" = None  # "clean" | None for acceptance


def prepare_acceptance(case: Case, worktree_dest: Path, *,
                        ai_tool: str = "claude") -> PrepResult:
    """SCHEMA.md §1 acceptance prep: worktree → docs present →
    Phase-0 install. No scrub, no leakage gate."""
    if case.type != CaseType.ACCEPTANCE:
        raise PrepError(
            f"prepare_acceptance called on non-acceptance case "
            f"{case.id} (type={case.type.value})"
        )
    sha = clone_worktree(case.inputs.repo_url, case.inputs.target_ref,
                          worktree_dest)
    if case.inputs.reference_docs_source is not None:
        populate_reference_docs(worktree_dest,
                                  case.inputs.reference_docs_source)
    install_skill_clone_channel(worktree_dest, ai_tool=ai_tool)
    return PrepResult(
        target_dir=worktree_dest,
        target_sha=sha,
        scrubbed_docs_manifest=None,
        leakage_gate=None,
    )


def prepare_security(case: Case, worktree_dest: Path, *,
                      ai_tool: str = "claude") -> PrepResult:
    """SCHEMA.md §1 / design §B security prep: worktree → scrub
    reference_docs of leakage terms → leakage-gate → install.

    The leakage-gate is load-bearing: if ANY scrub term remains in
    the worktree after the scrub, this raises ``PrepError`` with
    the leaked terms attached. The caller maps to
    ``terminal_state=ABORTED_PREP`` and writes
    ``leakage_gate="ABORTED"`` to invocation.json — the run never
    starts.
    """
    if case.type != CaseType.SECURITY_EVAL:
        raise PrepError(
            f"prepare_security called on non-security_eval case "
            f"{case.id} (type={case.type.value})"
        )
    if case.answer_key is None:
        raise PrepError(
            f"security case {case.id} has no answer_key"
        )
    sha = clone_worktree(case.inputs.repo_url, case.inputs.target_ref
                          or case.answer_key.vulnerable_parent,
                          worktree_dest)
    scrub_terms = case.inputs.scrub_terms or []
    manifest = scrub_reference_docs(worktree_dest / "reference_docs",
                                      scrub_terms)
    leaked = leakage_gate(worktree_dest, scrub_terms)
    if leaked:
        raise PrepError(
            f"leakage-gate ABORTED: terms still present in worktree "
            f"after scrub: {leaked}",
            leakage_terms=leaked,
        )
    install_skill_clone_channel(worktree_dest, ai_tool=ai_tool)
    return PrepResult(
        target_dir=worktree_dest,
        target_sha=sha,
        scrubbed_docs_manifest=manifest.to_json(),
        leakage_gate="clean",
    )


def prepare(case: Case, worktree_dest: Path, *,
             ai_tool: str = "claude") -> PrepResult:
    """Top-level dispatch: routes by ``case.inputs.prep``. The
    case's prep policy MUST match its type (the loader pins this
    in ``schema.parse_case``)."""
    if case.inputs.prep == PrepPolicy.ACCEPTANCE:
        return prepare_acceptance(case, worktree_dest, ai_tool=ai_tool)
    elif case.inputs.prep == PrepPolicy.SECURITY:
        return prepare_security(case, worktree_dest, ai_tool=ai_tool)
    else:
        raise PrepError(
            f"unknown prep policy {case.inputs.prep!r}"
        )


__all__ = [
    "PrepError",
    "PrepResult",
    "ScrubManifest",
    "clone_worktree",
    "scrub_reference_docs",
    "leakage_gate",
    "install_skill_clone_channel",
    "populate_reference_docs",
    "prepare",
    "prepare_acceptance",
    "prepare_security",
]
