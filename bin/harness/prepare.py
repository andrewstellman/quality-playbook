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
``ABORTED_PREP`` is the design §6 terminal state set when
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

    def __init__(self, reason: str, *,
                 leakage_terms: "list[str] | None" = None,
                 install_log_path: "str | None" = None,
                 install_log_tail: "list[str] | None" = None):
        super().__init__(reason)
        self.reason = reason
        # Populated when the leakage-gate fires; carries the
        # specific terms that leaked so the operator can fix the
        # case or extend the scrub list.
        self.leakage_terms = leakage_terms or []
        # v1.5.7 146: install-observability. On an install
        # failure/timeout, carry the path to the teed install.log
        # and its last-N lines so the caller can surface them in
        # the ABORTED_PREP message + grading.json without re-reading
        # the file.
        self.install_log_path = install_log_path
        self.install_log_tail = install_log_tail or []


# ---------------------------------------------------------------------------
# Worktree / clone helpers
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: "Path | None" = None,
         check: bool = True) -> subprocess.CompletedProcess:
    """Thin wrapper for git subprocess calls. Captures stdout +
    stderr so prep failures carry context in the PrepError reason
    string.

    v1.5.7 180-followup-10 FINDING-21: prepends
    ``-c core.longpaths=true`` to every git invocation so the
    working-tree materialization (clone, checkout, switch)
    handles Windows MAX_PATH (260-char limit) defensively.
    Webpack's asset-modules test fixtures exceed 260 chars
    when checked out under ``harness_runs/<ts>/run-NN/target/``
    and crash the clone with ``unable to create file ...:
    Filename too long``. The ``-c`` form is per-invocation
    (no persistent config change to the operator's git).
    Also routes through ``_platform.resolve_executable`` for
    the FINDING-5 PATHEXT fix on Windows.
    """
    from bin.harness import _platform as _platform_mod
    return subprocess.run(
        [_platform_mod.resolve_executable("git"),
         "-c", "core.longpaths=true",
         *args],
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
    # v1.5.7 105: skip the switch when the clone already landed
    # on the requested ref (the common case where the plan names
    # the repo's default branch — chi/express/keto/master,
    # gson/main, etc.) and prefer `git switch` over the legacy
    # `git checkout`. The two-step (plain switch, then `--detach`
    # fallback) handles branch names AND SHAs/tags cleanly:
    # branch names switch + auto-track origin; SHAs/tags fall
    # through to the detached path (gson pins a full SHA, so
    # this matters). Bad refs still raise PrepError →
    # ABORTED_PREP.
    if target_ref:
        current = _git("rev-parse", "--abbrev-ref", "HEAD",
                        cwd=dest).stdout.strip()
        if target_ref != current:
            res = _git("switch", "--quiet", target_ref,
                        cwd=dest, check=False)
            if res.returncode != 0:
                res = _git("switch", "--quiet", "--detach",
                            target_ref, cwd=dest, check=False)
            if res.returncode != 0:
                raise PrepError(
                    f"switch {target_ref!r} failed: "
                    f"{res.stderr.strip() or res.stdout.strip()}"
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

    Per design §B / design §1: this is the SECURITY prep step.
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
    list to set ``ABORTED_PREP`` (design §6).

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
    """design §3 ``clone`` channel: invoke
    ``python3 -m bin.install_skill --into <target> --ai-tool <tool>``
    from the QPB clone root.

    This is the dev/Phase 1 path. Other channels are templated
    by ``build_install_command``; their live execution lands
    post-publish (for registry) / after channel-build prereqs
    are present locally (for *-local-*).
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
# v1.5.7 096 Phase 6 — install-command templating per channel + version
# ---------------------------------------------------------------------------


def build_install_command(channel: "InstallChannel",
                           target_dir: Path, *,
                           ai_tool: str = "claude",
                           install_version: "str | None" = None,
                           local_artifact: "Path | None" = None,
                           force: bool = False,
                           ) -> "list[str]":
    """v1.5.7 096 Phase 6: build the install command for any of
    the design §3 channels. The returned argv list is exactly
    what the harness shells out to install the skill into
    ``target_dir`` for the given channel.

    Channel forms (verified against
    ``bin.qpb_validate._RUN_INSTALLER_*``):

    * ``clone`` →
      ``python3 -m bin.install_skill --into <target> --ai-tool <tool>``
      run from the QPB clone root.
    * ``pip-registry@<version|latest>`` →
      ``uvx quality-playbook@<version> install --into <target>
      --ai-tool <tool>``. ``install_version="latest"`` (or None)
      installs the current PyPI head.
    * ``npm-registry@<version|latest>`` →
      ``npx quality-playbook@<version> init --ai-tool=<tool>``.
      (npm syntax uses ``=`` for ai-tool, matching the
      ``_RUN_INSTALLER_NPM`` template + the README's published
      npx incantation.) v1.5.7 156: the harness MUST run this
      subprocess with ``cwd=<target_dir>`` — the npm shim
      auto-injects ``--into <cwd>`` (intended for end-user "install
      into here" UX), so leaving cwd inherited from the harness
      installs into QPB's own source tree.
    * ``pip-local-wheel`` → ``uvx --from <wheel-path>
      quality-playbook install --into <target> --ai-tool <tool>``.
      ``local_artifact`` is the path to the freshly-built wheel
      (``dist/quality_playbook-<version>-py3-none-any.whl``).
    * ``npm-local-tgz`` → ``npx --package <tgz-path>
      quality-playbook init --ai-tool=<tool>``.
      ``local_artifact`` is the path to ``npm pack`` output. As
      with npm-registry, ``install_skill_channel`` must invoke
      with ``cwd=<target_dir>`` (156).

    ``force=True`` appends ``--force`` to overwrite an existing
    target install (matches the ``_RUN_INSTALLER_*_FORCE``
    variants).

    Raises PrepError for missing local_artifact on a local
    channel, or unsupported channel.

    NOTE: this is pure templating — no subprocess runs here. The
    `install_skill_channel` wrapper below shells it out. Tests
    exercise the templater directly so they're hermetic (no live
    registry / no built wheel required).
    """
    if channel == InstallChannel.CLONE:
        qpb = _qpb_clone_root()
        cmd = [
            sys.executable, "-m", "bin.install_skill",
            "--into", str(target_dir),
            "--ai-tool", ai_tool,
        ]
        if force:
            cmd.append("--force")
        # The clone command runs from qpb_root cwd, but the
        # caller of `subprocess.run` is what sets cwd; the argv
        # itself doesn't carry that — flagged via the returned
        # list. The wrapper sets cwd=qpb_root for clone.
        return cmd

    if channel == InstallChannel.PIP_REGISTRY:
        version = install_version or "latest"
        cmd = [
            "uvx", f"quality-playbook@{version}",
            "install",
            "--into", str(target_dir),
            "--ai-tool", ai_tool,
        ]
        if force:
            cmd.append("--force")
        return cmd

    if channel == InstallChannel.NPM_REGISTRY:
        version = install_version or "latest"
        # v1.5.7 180-followup-4 FINDING-5: resolve npx via
        # _platform.resolve_executable (Windows: npx.cmd).
        from bin.harness import _platform as _platform_mod
        cmd = [
            _platform_mod.resolve_executable("npx"),
            f"quality-playbook@{version}",
            "init",
            f"--ai-tool={ai_tool}",
        ]
        if force:
            cmd.append("--force")
        return cmd

    if channel == InstallChannel.PIP_LOCAL_WHEEL:
        if local_artifact is None:
            raise PrepError(
                "pip-local-wheel channel requires local_artifact "
                "(path to the freshly-built wheel under dist/)"
            )
        cmd = [
            "uvx", "--from", str(local_artifact),
            "quality-playbook", "install",
            "--into", str(target_dir),
            "--ai-tool", ai_tool,
        ]
        if force:
            cmd.append("--force")
        return cmd

    if channel == InstallChannel.NPM_LOCAL_TGZ:
        if local_artifact is None:
            raise PrepError(
                "npm-local-tgz channel requires local_artifact "
                "(path to the `npm pack` output)"
            )
        # v1.5.7 142 + 150: --yes auto-confirms npx's "Need to
        # install the following packages — Ok to proceed? (y)"
        # prompt, which would otherwise block on stdin forever (the
        # subprocess has no TTY) and fire the prep timeout. This was
        # the REAL cause of the 138-symptom timeout — observed
        # verbatim in 146's install.log on the first post-146 chi
        # codex run (`Ok to proceed? (y)`). --prefer-offline (the 142
        # wisdom) stays as an honest optimization on top: npx still
        # does a quick registry-metadata check before installing, and
        # --prefer-offline uses the local cache when present. QPB's
        # npm package has ZERO runtime dependencies (verified against
        # the in-tarball package.json) and the shim does no network
        # work (verbatim subprocess.spawn to `python3 -m
        # quality_playbook_cli install`), so once --yes unblocks the
        # prompt the install finishes in seconds. Flag ordering
        # --yes → --prefer-offline → --package is conventional
        # (general, then registry-policy, then spec) and verified
        # accepted by npx 11.x.
        # v1.5.7 180-followup-4 FINDING-5: resolve npx via
        # _platform.resolve_executable (Windows: npx.cmd).
        from bin.harness import _platform as _platform_mod
        cmd = [
            _platform_mod.resolve_executable("npx"),
            "--yes", "--prefer-offline",
            "--package", str(local_artifact),
            "quality-playbook", "init",
            f"--ai-tool={ai_tool}",
        ]
        if force:
            cmd.append("--force")
        return cmd

    raise PrepError(f"unknown install channel: {channel!r}")


def _write_install_log(install_log_path: "Path | None",
                        stdout: "str | None",
                        stderr: "str | None") -> "list[str]":
    """v1.5.7 146: tee captured install stdout/stderr to
    ``install.log`` and return the last 30 lines (the tail used in
    ABORTED_PREP messages). ``capture_output`` keeps the two
    streams separate, so they're written stdout-then-stderr with a
    divider rather than truly interleaved. Best-effort — never
    raises (an install-log I/O error must not mask the real install
    result). Returns ``[]`` when ``install_log_path`` is None."""
    if install_log_path is None:
        return []
    parts: "list[str]" = []
    if stdout:
        parts.append(stdout.rstrip("\n"))
    if stderr:
        parts.append("--- stderr ---\n" + stderr.rstrip("\n"))
    combined = "\n".join(parts)
    try:
        install_log_path.parent.mkdir(parents=True, exist_ok=True)
        install_log_path.write_text(combined, encoding="utf-8")
    except OSError:
        pass
    lines = combined.splitlines()
    return lines[-30:]


def install_skill_channel(channel: "InstallChannel",
                            target_dir: Path, *,
                            ai_tool: str = "claude",
                            install_version: "str | None" = None,
                            local_artifact: "Path | None" = None,
                            force: bool = False,
                            timeout_s: float = 300.0,
                            install_log_path: "Path | None" = None) -> None:
    """v1.5.7 096 Phase 6: dispatch install per channel.

    Wraps ``build_install_command`` + ``subprocess.run`` with
    the per-channel cwd convention:

    * ``clone``: cwd = QPB clone root (so ``-m bin.install_skill``
      resolves).
    * registry / local channels: cwd is the OS default (the
      uvx/npx tooling locates its own working dir).

    Live registry runs only work POST-PUBLISH (PyPI/npm carry
    the artifact). Pre-publish, the local channels use the
    freshly-built local wheel/tgz.
    """
    cmd = build_install_command(
        channel, target_dir, ai_tool=ai_tool,
        install_version=install_version,
        local_artifact=local_artifact, force=force,
    )
    # v1.5.7 156: per-channel cwd convention.
    # * CLONE: ``_qpb_clone_root()`` (the harness's QPB clone provides
    #   the source tree that ``install_skill.py`` reads from).
    # * NPM channels: ``str(target_dir)``. The npm shim
    #   (``bin/quality-playbook.js::translateArgv``) auto-injects
    #   ``--into <cwd>`` for the install verb, so pointing cwd at the
    #   target IS how the install gets to the right place. Without
    #   this, cwd defaulted to None ⇒ subprocess inherited the
    #   harness's working directory (QPB's source tree, which already
    #   contains skill marker dirs) ⇒ shim injected
    #   ``--into <QPB-source-tree>`` ⇒ every file copy reported
    #   ``status=skipped`` and the run target got nothing. This was
    #   the 2026-05-29 ship-readiness retest's chi/gson codex Mode B
    #   failure mode (`harness_runs/20260529T235425Z/run-03` →
    #   `verdict=None`, `facts_error=installed quality_gate.py not
    #   found under .../target`).
    # * PIP / PIP_REGISTRY: ``None``. The pip channels pass
    #   ``--into <target>`` explicitly in build_install_command, so
    #   cwd doesn't matter.
    if channel == InstallChannel.CLONE:
        cwd = str(_qpb_clone_root())
    elif channel in (InstallChannel.NPM_LOCAL_TGZ,
                     InstallChannel.NPM_REGISTRY):
        cwd = str(target_dir)
    else:
        cwd = None
    _logp = str(install_log_path) if install_log_path else None
    try:
        result = subprocess.run(
            cmd, cwd=cwd, check=True,
            capture_output=True, text=True,
            timeout=timeout_s,
        )
    except subprocess.CalledProcessError as exc:
        tail = _write_install_log(
            install_log_path, exc.stdout, exc.stderr)
        raise PrepError(
            f"install_skill ({channel.value}) failed: "
            f"{(exc.stderr or exc.stdout or '').strip()[-500:]}",
            install_log_path=_logp, install_log_tail=tail,
        )
    except subprocess.TimeoutExpired as exc:
        # v1.5.7 146: ``exc.stdout``/``exc.stderr`` carry whatever
        # was captured before the kill (str under text=True; may be
        # None). Tee it so the timeout isn't a black box.
        _so = exc.stdout.decode("utf-8", "ignore") if isinstance(
            exc.stdout, bytes) else exc.stdout
        _se = exc.stderr.decode("utf-8", "ignore") if isinstance(
            exc.stderr, bytes) else exc.stderr
        tail = _write_install_log(install_log_path, _so, _se)
        raise PrepError(
            f"install_skill ({channel.value}) timed out after "
            f"{timeout_s}s — registry channels can be slow on a "
            f"cold cache, raise --timeout if needed.",
            install_log_path=_logp, install_log_tail=tail,
        )
    except FileNotFoundError as exc:
        # uvx / npx not on PATH — operator-actionable.
        raise PrepError(
            f"install_skill ({channel.value}) tooling missing: "
            f"{exc}. Install the required runtime (uvx for pip "
            f"channels; npx for npm channels)."
        )
    # v1.5.7 146: success — tee the install output too (so a clean
    # install.log is available for confirming e.g. whether
    # --prefer-offline actually hit the cache).
    _write_install_log(install_log_path, result.stdout, result.stderr)


# ---------------------------------------------------------------------------
# Reference-docs population (acceptance)
# ---------------------------------------------------------------------------


def _resolve_docs_source(reference_docs_source: str,
                          repo: str,
                          runs_root: "Optional[Path]" = None) -> str:
    """v1.5.7 144 (Option 2 ruling): resolve the effective ``docs``
    value before ``populate_reference_docs`` runs.

    Explicit paths pass through unchanged — operator opt-in always
    wins. For the ``"gather"`` default, auto-pick up gathered docs
    at the DOCUMENTED convention
    ``<runs_root|./repos>/docs_gathered/<repo>/`` when it exists and
    is non-empty; otherwise return ``"gather"`` (the pre-144 no-op
    fallback — same experience when nothing's gathered).

    Only ``docs_gathered/<repo>/`` is consulted — it's the
    source-of-truth the doc-gathering protocol + ``setup_repos.sh``
    use. The versioned ``<repo>-<version>/reference_docs/`` dirs are
    per-run MIRRORS (and ambiguous across versions / ``.bak``), so
    they're deliberately NOT candidates (the 144 halt surfaced a
    gson case where the mirror diverged from the gathered source).

    Pure / read-only: ``is_dir()`` + a non-empty probe; no network,
    no writes. An existing-but-empty ``docs_gathered/<repo>/`` is
    treated as "not present" (falls through to ``"gather"``) so an
    empty dir can't starve Phase 1 of the Tier-3 source fallback.

    ``repo`` → ``<repo_name>``: last URL path segment, ``.git``
    suffix stripped, lowercased
    (``https://github.com/google/gson`` → ``gson``;
    ``git@github.com:foo/bar.git`` → ``bar``).
    """
    if reference_docs_source != "gather":
        return reference_docs_source
    repo_name = repo.rstrip("/").rsplit("/", 1)[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    repo_name = repo_name.lower()
    if not repo_name:
        return "gather"
    candidates: "list[Path]" = []
    if runs_root is not None:
        candidates.append(
            Path(runs_root) / "docs_gathered" / repo_name)
    candidates.append(Path("repos") / "docs_gathered" / repo_name)
    for cand in candidates:
        cand = cand.expanduser()
        try:
            if cand.is_dir() and any(cand.iterdir()):
                return str(cand)
        except OSError:
            continue
    return "gather"


def populate_reference_docs(target_dir: Path,
                              reference_docs_source: str) -> None:
    """Acceptance prep: ensure ``reference_docs/`` is present in
    the target before the install step.

    Two source shapes per design §1:
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


def _run_install_for_axes(
    target_dir: Path,
    *,
    axes: "RunAxes | None" = None,
    ai_tool: str = "claude",
    local_artifact: "Path | None" = None,
    prep_timeout_s: "float | None" = None,
    install_log_path: "Path | None" = None,
) -> None:
    """v1.5.7 096 Phase 6: route the install step by axes.install_
    channel. When ``axes`` is None (no axes provided — Phase 1
    smoke entry pre-096), defaults to the clone channel for
    backward compatibility.

    v1.5.7 138: ``prep_timeout_s`` overrides ``install_skill_channel``'s
    default install timeout for THIS run when set (codex's
    npm-local-tgz on a cold cache exceeds the 300s default). None ⇒
    the channel default.

    v1.5.7 146: ``install_log_path`` tees the install stdout/stderr
    to that file (and carries the tail on a timeout/failure). None ⇒
    no install log (pre-146 behavior).
    """
    if axes is None:
        install_skill_clone_channel(target_dir, ai_tool=ai_tool)
        return
    install_skill_channel(
        axes.install_channel,
        target_dir,
        ai_tool=ai_tool,
        install_version=axes.install_version,
        local_artifact=local_artifact,
        install_log_path=install_log_path,
        **({"timeout_s": prep_timeout_s}
           if prep_timeout_s is not None else {}),
    )


def prepare_acceptance(case: Case, worktree_dest: Path, *,
                        ai_tool: str = "claude",
                        axes: "RunAxes | None" = None,
                        local_artifact: "Path | None" = None,
                        prep_timeout_s: "float | None" = None,
                        install_log_path: "Path | None" = None,
                        ) -> PrepResult:
    """design §1 acceptance prep: worktree → docs present →
    Phase-0 install. No scrub, no leakage gate.

    v1.5.7 096 Phase 6: accepts an optional ``axes`` so the
    install step routes by ``install_channel``
    (clone / pip-registry@<v> / npm-registry@<v> /
    pip-local-wheel / npm-local-tgz). ``axes=None`` keeps the
    Phase 1 clone-default contract for backward compatibility.
    """
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
    _run_install_for_axes(
        worktree_dest, axes=axes, ai_tool=ai_tool,
        local_artifact=local_artifact,
        prep_timeout_s=prep_timeout_s,
        install_log_path=install_log_path,
    )
    return PrepResult(
        target_dir=worktree_dest,
        target_sha=sha,
        scrubbed_docs_manifest=None,
        leakage_gate=None,
    )


def prepare_security(case: Case, worktree_dest: Path, *,
                      ai_tool: str = "claude",
                      axes: "RunAxes | None" = None,
                      local_artifact: "Path | None" = None,
                      prep_timeout_s: "float | None" = None,
                      install_log_path: "Path | None" = None,
                      ) -> PrepResult:
    """design §1 / design §B security prep: worktree → scrub
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
    _run_install_for_axes(
        worktree_dest, axes=axes, ai_tool=ai_tool,
        local_artifact=local_artifact,
        prep_timeout_s=prep_timeout_s,
        install_log_path=install_log_path,
    )
    return PrepResult(
        target_dir=worktree_dest,
        target_sha=sha,
        scrubbed_docs_manifest=manifest.to_json(),
        leakage_gate="clean",
    )


def prepare(case: Case, worktree_dest: Path, *,
             ai_tool: str = "claude",
             axes: "RunAxes | None" = None,
             local_artifact: "Path | None" = None,
             prep_timeout_s: "float | None" = None,
             install_log_path: "Path | None" = None,
             ) -> PrepResult:
    """Top-level dispatch: routes by ``case.inputs.prep``. The
    case's prep policy MUST match its type (the loader pins this
    in ``schema.parse_case``).

    v1.5.7 096 Phase 6: ``axes`` routes the install step through
    ``build_install_command`` by channel + version (clone /
    pip-registry@<v> / npm-registry@<v> / pip-local-wheel /
    npm-local-tgz). ``axes=None`` keeps the Phase 1 clone default.
    """
    if case.inputs.prep == PrepPolicy.ACCEPTANCE:
        return prepare_acceptance(
            case, worktree_dest, ai_tool=ai_tool,
            axes=axes, local_artifact=local_artifact,
            prep_timeout_s=prep_timeout_s,
            install_log_path=install_log_path,
        )
    elif case.inputs.prep == PrepPolicy.SECURITY:
        return prepare_security(
            case, worktree_dest, ai_tool=ai_tool,
            axes=axes, local_artifact=local_artifact,
            prep_timeout_s=prep_timeout_s,
            install_log_path=install_log_path,
        )
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
    "build_install_command",
    "install_skill_channel",
    "populate_reference_docs",
    "prepare",
    "prepare_acceptance",
    "prepare_security",
]
