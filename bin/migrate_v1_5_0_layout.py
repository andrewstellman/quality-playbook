"""migrate_v1_5_0_layout.py — idempotent one-shot for the v1.5.0 layout move.

Brings a pre-v1.5.0 repo into compliance with the consolidated `quality/`
layout expected by the orchestrator, gate, and SKILL.md prose after Phase 5a.

Pre-v1.5.0 layout (the source shape this script migrates):

    <repo>/
      control_prompts/             # per-phase prompt captures at repo root
      previous_runs/<ts>/quality/  # archived prior runs, nested one level
      quality/                     # current run artifacts

v1.5.0 target layout:

    <repo>/
      quality/
        control_prompts/           # moved from <repo>/control_prompts/
        runs/<ts>/quality/         # renamed from <repo>/previous_runs/<ts>/quality/
        ... current run artifacts  # unchanged
        RUN_INDEX.md               # generated here, append-only across future runs

For each subfolder that lands under `quality/runs/<ts>/`, a best-effort
`INDEX.md` is backfilled from git log (for timestamp bounds) and surviving
artifacts (BUGS.md / REQUIREMENTS.md / PROGRESS.md) for the tier / severity /
disposition counts. Fields that cannot be recovered from the archived
content are stored as the string `"unknown"`.

Idempotent semantics: running the script twice is identical to running it
once. Already-migrated state is detected by looking at repo-root
`control_prompts/` and `previous_runs/` — absent = already done, present =
execute the move(s). Half-migrated state (one missing, one present)
completes the remaining half rather than erroring.

Dry-run mode (`--dry-run`) prints the planned moves and writes without
touching the filesystem.

Usage:

    python -m bin.migrate_v1_5_0_layout <repo-path>        # execute
    python -m bin.migrate_v1_5_0_layout <repo-path> --dry-run

`<repo-path>` defaults to the current working directory.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# v1.5.7 090c: foreign-bin-proof import — try the package form
# first, fall back to a path-load of archive_lib.py from this
# file's directory so the import is anchored on __file__ and
# never resolves to a sibling repo's bin/.
try:
    from bin import archive_lib
except ImportError:
    import importlib.util as _ilu
    _al_path = Path(__file__).resolve().parent / "archive_lib.py"
    _al_spec = _ilu.spec_from_file_location(
        "_qpb_archive_lib_via_migrate", _al_path,
    )
    if _al_spec is None or _al_spec.loader is None:
        raise ImportError(
            f"migrate_v1_5_0_layout: cannot resolve archive_lib — "
            f"path-load fallback target {_al_path} is missing."
        )
    archive_lib = _ilu.module_from_spec(_al_spec)
    # v1.5.7 090c: register in sys.modules BEFORE exec_module so
    # any dataclass/typing machinery in archive_lib that consults
    # `sys.modules[__module__]` resolves.
    sys.modules[_al_spec.name] = archive_lib
    _al_spec.loader.exec_module(archive_lib)


class MigrationError(Exception):
    """Raised on unrecoverable migration failures."""


# ---------------------------------------------------------------------------
# Plan / state detection
# ---------------------------------------------------------------------------


def _legacy_previous_runs(repo: Path) -> Path:
    return repo / "previous_runs"


def _legacy_control_prompts(repo: Path) -> Path:
    return repo / "control_prompts"


def _quality_runs(repo: Path) -> Path:
    return repo / "quality" / "runs"


def _quality_control_prompts(repo: Path) -> Path:
    return repo / "quality" / "control_prompts"


def already_migrated(repo: Path) -> bool:
    """Return True iff every legacy location is absent and at least one v1.5.0 location exists.

    A repo that never had the legacy folders is also considered migrated (nothing to do).
    """
    legacy_absent = (
        not _legacy_previous_runs(repo).exists()
        and not _legacy_control_prompts(repo).exists()
    )
    return legacy_absent


# ---------------------------------------------------------------------------
# Delegations to archive_lib for payload extraction and rendering.
# ---------------------------------------------------------------------------


def build_index_payload(repo: Path, run_folder: Path) -> Dict[str, object]:
    """Back-compat wrapper retained for tests; pins legacy target_repo_git_sha=unknown."""
    return archive_lib.build_index_payload(
        repo,
        run_folder,
        target_repo_git_sha="unknown",
    )


def render_index_markdown(run_id: str, payload: Dict[str, object]) -> str:
    return archive_lib.render_index_markdown(
        run_id,
        payload,
        provenance=(
            "backfilled by `bin/migrate_v1_5_0_layout.py` from git log and\n"
            "the surviving artifacts"
        ),
    )


render_run_index_row = archive_lib.render_run_index_row
render_run_index_header = archive_lib.render_run_index_header


# ---------------------------------------------------------------------------
# Plan + execute
# ---------------------------------------------------------------------------


class Planner:
    """Collect planned moves and writes; execute or print them."""

    def __init__(self, repo: Path, *, dry_run: bool = False) -> None:
        self.repo = repo
        self.dry_run = dry_run
        self.actions: List[str] = []

    def _log(self, msg: str) -> None:
        self.actions.append(msg)
        prefix = "[dry-run]" if self.dry_run else "[migrate]"
        print(f"{prefix} {msg}")

    def move_tree(self, src: Path, dst: Path) -> None:
        self._log(f"move {src.relative_to(self.repo)} -> {dst.relative_to(self.repo)}")
        if self.dry_run:
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise MigrationError(
                f"cannot move {src} -> {dst}: destination already exists. Manual "
                "cleanup required."
            )
        shutil.move(str(src), str(dst))

    def write_text(self, path: Path, content: str) -> None:
        self._log(f"write {path.relative_to(self.repo)} ({len(content)} bytes)")
        if self.dry_run:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def migrate(repo: Path, *, dry_run: bool = False) -> Planner:
    repo = repo.resolve()
    if not repo.is_dir():
        raise MigrationError(f"{repo} is not a directory")
    planner = Planner(repo, dry_run=dry_run)
    legacy_prev = _legacy_previous_runs(repo)
    legacy_cp = _legacy_control_prompts(repo)

    if not legacy_prev.exists() and not legacy_cp.exists():
        planner._log("no legacy directories present — nothing to move")
    else:
        if legacy_prev.exists():
            planner.move_tree(legacy_prev, _quality_runs(repo))
        if legacy_cp.exists():
            planner.move_tree(legacy_cp, _quality_control_prompts(repo))

    runs_dir = _quality_runs(repo)
    run_payloads: List[Tuple[str, Dict[str, object]]] = []
    if runs_dir.is_dir():
        for run_folder in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
            index_path = run_folder / "INDEX.md"
            if index_path.exists():
                planner._log(f"keep existing {index_path.relative_to(repo)}")
                continue
            # For dry-run, build the payload only when the real filesystem state
            # lets us — folders that haven't been moved yet won't be under
            # quality/runs/ in dry-run mode.
            try:
                payload = build_index_payload(repo, run_folder)
            except Exception as exc:  # noqa: BLE001 — best-effort backfill
                planner._log(f"skip INDEX.md for {run_folder.name}: {exc}")
                continue
            planner.write_text(index_path, render_index_markdown(run_folder.name, payload))
            run_payloads.append((run_folder.name, payload))
    elif legacy_prev.exists() and dry_run:
        # Dry-run: enumerate the legacy entries that would produce run folders.
        for run_folder in sorted(p for p in legacy_prev.iterdir() if p.is_dir()):
            planner._log(f"dry-run would backfill INDEX.md for quality/runs/{run_folder.name}/")

    # v1.5.4 Phase 3.6.2 (B-19): the migration script is a one-time
    # rescue tool for v1.5.0 → v1.5.1 layouts; it lands archives at
    # the LEGACY ``quality/runs/`` path. The render call passes
    # ``archive_dir=LEGACY_ARCHIVE_DIRNAME`` so RUN_INDEX rows point
    # at the actual on-disk location rather than the new
    # ``previous_runs/`` default.
    legacy_dir = archive_lib.LEGACY_ARCHIVE_DIRNAME
    if run_payloads:
        rows = [
            archive_lib.render_run_index_row(run_id, payload, archive_dir=legacy_dir)
            for run_id, payload in run_payloads
        ]
        existing_path = repo / "quality" / "RUN_INDEX.md"
        existing = existing_path.read_text(encoding="utf-8") if existing_path.is_file() else ""
        if existing and "| Run |" in existing:
            content = existing.rstrip() + "\n" + "\n".join(rows) + "\n"
        else:
            content = archive_lib.render_run_index_header() + "\n".join(rows) + "\n"
        planner.write_text(existing_path, content)
    elif runs_dir.is_dir() and not (repo / "quality" / "RUN_INDEX.md").exists():
        # Runs directory exists but no new INDEX.md was backfilled this
        # invocation (re-run on an already-migrated repo) — still ensure the
        # top-level index exists by rebuilding from existing INDEX.md files.
        rebuilt_rows: List[str] = []
        for run_folder in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
            payload = archive_lib.load_index_payload(run_folder / "INDEX.md")
            if payload is not None:
                rebuilt_rows.append(
                    archive_lib.render_run_index_row(
                        run_folder.name, payload, archive_dir=legacy_dir,
                    )
                )
        if rebuilt_rows:
            planner.write_text(
                repo / "quality" / "RUN_INDEX.md",
                archive_lib.render_run_index_header() + "\n".join(rebuilt_rows) + "\n",
            )

    return planner


_load_existing_index_payload = archive_lib.load_index_payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    # v1.5.7 089x: no-args is purpose-banner-safe.
    _argv_list_089x = list(sys.argv[1:] if argv is None else argv)
    try:
        from bin._purpose import print_command_intro as _print_command_intro
        from bin._purpose import print_help_banner as _print_help_banner
    except ImportError:
        from _purpose import print_command_intro as _print_command_intro  # type: ignore[no-redef]
        from _purpose import print_help_banner as _print_help_banner  # type: ignore[no-redef]
    if not _argv_list_089x:
        _print_command_intro(
            name='migrate_v1_5_0_layout',
            summary=(
            "One-shot v1.5.0 → v1.5.x layout migrator — upgrades a "
            "target from the pre-v1.5.0 flat layout to the current "
            "`quality/` + `informal_docs/` shape. "
            ),
            role=(
            "Operator-side migration — NOT called during a playbook "
            "run. Run once per target repo when upgrading from a "
            "pre-v1.5.0 install. "
            ),
            usage_hint='python3 -m bin.migrate_v1_5_0_layout <target>',
        )
        return 0

    # v1.5.7 090a: full attribution banner at top of --help.
    _print_help_banner(_argv_list_089x)

    parser = argparse.ArgumentParser(
        description=(
            "Idempotently migrate a pre-v1.5.0 QPB target repo to the consolidated "
            "quality/ layout. Moves control_prompts/ and previous_runs/ under "
            "quality/ and backfills per-run INDEX.md + top-level RUN_INDEX.md."
        ),
    )
    parser.add_argument(
        "repo",
        nargs="?",
        default=".",
        help="Target repository to migrate (default: current working directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned moves and writes without touching the filesystem.",
    )
    args = parser.parse_args(argv)

    try:
        migrate(Path(args.repo), dry_run=args.dry_run)
    except MigrationError as exc:
        print(f"migrate: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
