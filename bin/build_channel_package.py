"""v1.5.7 089u — publish-time build script for the pip distribution
channel.

Stages the QPB clone's source layout under
``quality_playbook_cli/_bundle/`` by reading
``bin.install_skill._bundle_files()`` as the **single source of
truth** for what the package ships. No hand-maintained file list —
this guarantees the pip wheel's data dir mirrors what
``install_skill.py`` expects to find at its ``--source`` root.

Usage (run from QPB clone root, before ``python -m build``):

    python3 bin/build_channel_package.py             # stage
    python3 -m build                                 # build wheel + sdist

Or call ``stage()`` programmatically from tests:

    from bin.build_channel_package import enumerate_bundle, stage
    items = enumerate_bundle(repo_root)              # for parity checks
    stage(repo_root, dest_dir)                       # for end-to-end tests

The shim ``quality_playbook_cli`` (loaded at ``pip install`` time)
finds this staged data dir at ``Path(__file__).parent / "_bundle"``
and runs ``install_skill.main()`` against it with ``--source``
defaulting to the packaged bundle root.

**Bundle parity discipline.** The set of file paths this script
stages MUST equal ``_bundle_files(repo_root)``'s source set. The
parity test
``bin/tests/test_pip_channel_package_parity_089u.py``
asserts this — drop a member from this script's enumeration and
the parity test fails.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent


def _import_install_skill():
    """Load ``bin/install_skill.py`` for its ``_bundle_files()``
    function — used at build time only, not at adopter ``pip
    install`` time. The shim loads install_skill from the staged
    package data, not from this clone path."""
    # The clone has ``bin/`` as a top-level package, so a plain
    # ``from bin import install_skill`` works when this script is
    # run from the clone root.
    sys.path.insert(0, str(REPO_ROOT))
    from bin import install_skill  # noqa: E402

    return install_skill


def skill_bundle_paths(repo_root: Path) -> list[Path]:
    """Return the SKILL-BUNDLE source paths — exactly the set
    ``install_skill._bundle_files(repo_root)`` enumerates.

    These are the files that get copied into an adopter's target
    repo at install time. The parity test pins this set to
    ``_bundle_files()`` member-for-member."""
    install_skill = _import_install_skill()
    return [src for src, _dest_rel in install_skill._bundle_files(repo_root)]


def executor_paths(repo_root: Path) -> list[Path]:
    """Return the EXECUTOR source paths — the QPB scripts the
    ``quality_playbook_cli`` shim loads at adopter ``pip install``
    time, with their import closures.

    The shim has two verbs:
      - ``install``  →  ``bin/install_skill.py``
      - ``validate`` →  ``bin/qpb_validate.py`` (089u-cycle2: wired
        so the pip-channel remediation string
        ``uvx quality-playbook validate <target>`` actually
        resolves to a runnable command)

    Neither of these is in ``_bundle_files()`` (adopters don't get
    the executor scripts at their target — they get the skill
    closure those scripts WRITE to the target). But the pip-channel
    package data must ship both, so the shim can load and run them.

    Closure check (089u pre-flight): ``bin/install_skill.py`` is
    stdlib-only with zero ``from bin import …`` imports.
    ``bin/qpb_validate.py`` is also stdlib-only at the module
    level. Both load cleanly via ``importlib.util`` without any
    sibling-package resolution. If a future edit adds an internal
    import to either, extend this function."""
    return [
        repo_root / "bin" / "install_skill.py",
        repo_root / "bin" / "qpb_validate.py",
    ]


def enumerate_bundle(repo_root: Path) -> list[Path]:
    """Return the full set of absolute source paths the pip channel
    package data must contain — the skill bundle plus the
    executor. Order: skill bundle (in ``_bundle_files()`` order)
    then executor."""
    return skill_bundle_paths(repo_root) + executor_paths(repo_root)


def npm_extra_paths(repo_root: Path) -> list[Path]:
    """Return the **npm-tarball-only extras** — files the npm
    package needs in addition to the staged ``quality_playbook_cli/
    _bundle/`` tree the wheel also uses.

    These live at the clone root (not inside ``_bundle/``) and are
    picked up by ``npm pack`` via ``package.json``'s ``files``
    glob. The wheel does NOT include them — the wheel uses the
    Python console-script declared in ``pyproject.toml`` instead,
    and never needs the Node shim.

    Order: stable for parity-test diffs.

    089v additions:
      - ``bin/quality-playbook.js`` — the Node shim that the npm
        consumer's ``npx`` invocation hits first (it then spawns
        ``python3 -m quality_playbook_cli`` against the staged
        bundle).
      - ``package.json`` — npm package metadata declaring the
        ``quality-playbook`` bin entry, the npm tarball's
        ``files`` manifest, and the Node engines floor.
    """
    return [
        repo_root / "bin" / "quality-playbook.js",
        repo_root / "package.json",
    ]


def enumerate_npm_tarball(repo_root: Path) -> list[Path]:
    """Return the full set of absolute source paths the **npm
    tarball** must contain. This is the parity contract for the
    fourth distribution surface:

      1. ``_bundle_files()`` — skill bundle (51 files, shared with
         the wheel via the staged ``quality_playbook_cli/_bundle/``).
      2. ``executor_paths()`` — ``install_skill.py`` +
         ``qpb_validate.py`` (also shared, via the staged bundle).
      3. ``quality_playbook_cli/__init__.py`` — the Python shim the
         npm-shipped Node shim spawns as ``python -m
         quality_playbook_cli`` (delivered via ``package.json``'s
         ``files`` glob, NOT via ``_bundle_files()``).
      4. ``quality_playbook_cli/__main__.py`` — the ``python -m``
         entry the npm shim invokes. Without it
         ``python -m quality_playbook_cli`` fails with
         "package and cannot be directly executed"; the wheel's
         console-script path bypasses ``-m`` entirely so the wheel
         did not need this file, but the npm channel does.
      5. ``npm_extra_paths()`` — the Node shim + ``package.json``.

    Mutation bite (the 4-surface lockstep invariant): drop a member
    from ``_bundle_files()`` and the npm-parity test fires (along
    with the wheel-parity and AGENTS.md cp-block guards). Drop a
    member from ``npm_extra_paths()`` and only the npm test
    fires."""
    return (
        skill_bundle_paths(repo_root)
        + executor_paths(repo_root)
        + [
            repo_root / "quality_playbook_cli" / "__init__.py",
            repo_root / "quality_playbook_cli" / "__main__.py",
        ]
        + npm_extra_paths(repo_root)
    )


def stage(repo_root: Path, dest_dir: Path,
          *, clean: bool = True) -> list[Path]:
    """Copy every file enumerated by ``enumerate_bundle(repo_root)``
    into ``dest_dir``, preserving the clone-relative path layout.

    Returns the list of staged file paths (under ``dest_dir``).
    With ``clean=True`` (default), removes any prior ``dest_dir``
    contents first.
    """
    repo_root = repo_root.resolve()
    dest_dir = dest_dir.resolve()
    if clean and dest_dir.is_dir():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    staged: list[Path] = []
    for src in enumerate_bundle(repo_root):
        try:
            rel = src.resolve().relative_to(repo_root)
        except ValueError:
            # The path isn't under repo_root — refuse to stage
            # something from outside the clone (defense against
            # an unexpected _bundle_files() entry pointing
            # elsewhere).
            raise RuntimeError(
                f"build_channel_package: refusing to stage source "
                f"path {src} which is not under repo_root "
                f"{repo_root}. _bundle_files() returned an "
                f"unexpected entry — investigate before publishing."
            )
        target = dest_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            shutil.copy2(src, target)
            staged.append(target)
        else:
            # _bundle_files() should only yield files; surface a
            # build error rather than silently dropping a dir.
            raise RuntimeError(
                f"build_channel_package: source path {src} is not "
                f"a regular file. _bundle_files() yielded a non-"
                f"file entry — investigate."
            )
    return staged


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_channel_package",
        description=(
            "Stage the QPB clone's source layout under "
            "quality_playbook_cli/_bundle/ for the pip channel. "
            "Run before `python -m build`."
        ),
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=REPO_ROOT / "quality_playbook_cli" / "_bundle",
        help=(
            "Destination directory (default: "
            "<repo>/quality_playbook_cli/_bundle)"
        ),
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help=(
            "Do not clean the destination directory before "
            "staging. Use only for incremental dev runs."
        ),
    )
    args = parser.parse_args(argv)

    staged = stage(REPO_ROOT, args.dest, clean=not args.no_clean)
    print(
        f"build_channel_package: staged {len(staged)} files into "
        f"{args.dest}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
