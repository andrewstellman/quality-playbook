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
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable

# v1.5.7 089x: `_purpose` import that works in BOTH invocation forms —
# `python -m bin.build_channel_package` (bin/ is a package; cwd is the
# repo root) AND `python3 bin/build_channel_package.py` (sys.path[0] is
# bin/, so the package import fails but the direct one works).
try:
    from bin import _purpose
except ImportError:
    import _purpose  # type: ignore[no-redef]


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


def _purge_compiled_artifacts(dest_dir: Path) -> None:
    """v1.5.7 089y T-B: remove ``__pycache__`` dirs + ``.pyc``/
    ``.pyo`` files from a staged tree.

    Why this exists: the staged ``quality_playbook_cli/_bundle/``
    tree is a Python source bundle, but if anything imports the
    staged modules at test/dev time (the 089u + 089v e2e tests
    do this when they spawn ``python -m quality_playbook_cli``),
    Python writes ``__pycache__/*.pyc`` siblings to the
    ``.py`` files. Those compiled artifacts are
    platform/version-specific and have no place in either the pip
    wheel or the npm tarball — both channels should ship .py
    source only.

    Called at the END of ``stage()`` so the staged tree is
    artifact-free regardless of whether ``clean=True`` wiped a
    previous staging (in which case there'd be nothing to purge)
    or ``clean=False`` left a dirty incremental tree.
    """
    if not dest_dir.is_dir():
        return
    for pycache in dest_dir.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache, ignore_errors=True)
    for suffix in (".pyc", ".pyo"):
        for f in dest_dir.rglob(f"*{suffix}"):
            try:
                f.unlink()
            except OSError:
                pass


def stage(repo_root: Path, dest_dir: Path,
          *, clean: bool = True) -> list[Path]:
    """Copy every file enumerated by ``enumerate_bundle(repo_root)``
    into ``dest_dir``, preserving the clone-relative path layout.

    Returns the list of staged file paths (under ``dest_dir``).
    With ``clean=True`` (default), removes any prior ``dest_dir``
    contents first.

    v1.5.7 089y T-B: also purges any ``__pycache__`` / ``.pyc`` /
    ``.pyo`` that may have appeared under ``dest_dir`` (e.g. from
    test imports of the staged modules) — neither channel ships
    compiled artifacts.
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
    # v1.5.7 089y T-B: purge compiled-Python cruft from the staged
    # tree (only effective for the --no-clean incremental case; a
    # clean stage starts from an empty dir so there's nothing to
    # purge).
    _purge_compiled_artifacts(dest_dir)
    # v1.5.7 090b T-B: belt-and-suspenders fail-loud guard. The
    # 090b Task-A change made `_bundle_files()` raise-on-missing
    # for each mandatory member, so a missing source file fails
    # the build cleanly. This guard catches the OTHER failure
    # mode: a staging step that completes "successfully" but
    # produces a partial tree (e.g. an interrupted copy, an OS
    # race, the still-unexplained machine-specific stage that
    # produced 53 files instead of 54). The wheel / npm tarball
    # must never ship without these — install_skill +
    # qpb_validate (the channel executors) import _purpose at
    # module load.
    _assert_mandatory_staged_members(dest_dir)
    return staged


# v1.5.7 090b: load-time hard dependencies that MUST be present in
# the staged tree before a wheel/tarball can be produced. install_
# skill.py + qpb_validate.py are the channel executors; _purpose.py
# is the shared helper both import at module load.
_MANDATORY_STAGED_REL_PATHS: tuple[Path, ...] = (
    Path("bin") / "install_skill.py",
    Path("bin") / "qpb_validate.py",
    Path("bin") / "_purpose.py",
)


def _assert_mandatory_staged_members(dest_dir: Path) -> None:
    """v1.5.7 090b T-B: refuse to declare staging complete if any
    of the LOAD-TIME hard-dependency members are absent from
    ``dest_dir``. Pre-090b a partial stage would silently produce
    a wheel/tarball that crashed at install with FileNotFoundError
    on first import of the channel executors (the 2026-05-23
    pip/npx smoke crash). This guard makes the failure mode loud
    at build time instead of silent at adopter install time."""
    missing: list[Path] = []
    for rel in _MANDATORY_STAGED_REL_PATHS:
        p = dest_dir / rel
        if not p.is_file():
            missing.append(rel)
    if missing:
        names = ", ".join(str(m) for m in missing)
        raise RuntimeError(
            f"build_channel_package: staged bundle at {dest_dir} "
            f"is missing mandatory members: {names}. The channel "
            f"executors (install_skill.py + qpb_validate.py) import "
            f"`_purpose.py` at module load; a wheel / npm tarball "
            f"built from this staged tree would crash with "
            f"FileNotFoundError on first install. Refusing to "
            f"declare staging complete — investigate the staging "
            f"step before retrying."
        )


_PYPROJECT_VERSION_RE = re.compile(
    r'^(version\s*=\s*)"([^"]+)"\s*$', re.MULTILINE
)
_PACKAGE_JSON_VERSION_RE = re.compile(
    r'^(\s*"version"\s*:\s*)"([^"]+)"', re.MULTILINE
)


def stamp_channel_manifest_versions(repo_root: Path) -> list[tuple[Path, str, str]]:
    """v1.5.7 089x T4: rewrite the channel manifests' ``version``
    fields from SKILL.md so the pip wheel + npm tarball can't ship
    a version that drifts from the skill.

    Reads ``_purpose.get_version()`` (THE canonical reader) and
    updates:
      - ``pyproject.toml`` — the ``[project]`` table's ``version =
        "..."`` line.
      - ``package.json`` — the top-level ``"version": "..."`` field.

    Idempotent: re-running with no SKILL.md change writes the same
    text. Returns a list of ``(path, before, after)`` tuples for
    every file actually modified (empty list if both files were
    already in sync — useful for tests / logging).

    Run by ``main()`` automatically before ``stage()``. Adopters
    invoking ``python -m build`` / ``npm pack`` directly should
    run this first.
    """
    # _purpose is imported at module top with try/except for both
    # `python -m bin.build_channel_package` and `python3
    # bin/build_channel_package.py` invocations.
    skill_version = _purpose.get_version()
    if skill_version == "unknown":
        raise RuntimeError(
            f"build_channel_package: could not resolve SKILL.md "
            f"version from {repo_root}; refusing to stamp channel "
            f"manifests with a placeholder."
        )

    changed: list[tuple[Path, str, str]] = []
    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
        new_text, n = _PYPROJECT_VERSION_RE.subn(
            lambda m: f'{m.group(1)}"{skill_version}"',
            text, count=1,
        )
        if n == 0:
            raise RuntimeError(
                f"build_channel_package: pyproject.toml has no "
                f"matchable `version = \"...\"` line — manifest "
                f"shape changed; update the regex deliberately."
            )
        if new_text != text:
            pyproject.write_text(new_text, encoding="utf-8")
            old = _PYPROJECT_VERSION_RE.search(text).group(2)
            changed.append((pyproject, old, skill_version))

    package_json = repo_root / "package.json"
    if package_json.is_file():
        text = package_json.read_text(encoding="utf-8")
        new_text, n = _PACKAGE_JSON_VERSION_RE.subn(
            lambda m: f'{m.group(1)}"{skill_version}"',
            text, count=1,
        )
        if n == 0:
            raise RuntimeError(
                f"build_channel_package: package.json has no "
                f"matchable `\"version\": \"...\"` line — manifest "
                f"shape changed; update the regex deliberately."
            )
        if new_text != text:
            package_json.write_text(new_text, encoding="utf-8")
            old = _PACKAGE_JSON_VERSION_RE.search(text).group(2)
            changed.append((package_json, old, skill_version))
    return changed


def main(argv: Iterable[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    else:
        argv = list(argv)

    # v1.5.7 089x T2 + T3 invariant: no-args is purpose-banner-safe.
    # Bare invocation does NOT stage or modify anything — that
    # behavior was a 089u footgun ("run the build script just to
    # peek at what it does, get a half-staged tree"). The explicit
    # form (`--stage` or any other arg) is required to do work.
    if not argv:
        # v1.5.7 090a: full attribution banner + purpose banner.
        _purpose.print_command_intro(
            name="build_channel_package",
            summary=(
                "Stage the QPB clone source layout into "
                "quality_playbook_cli/_bundle/ + stamp the pip + "
                "npm channel manifests' version from SKILL.md."
            ),
            role=(
                "Run by the OPERATOR before `python -m build` "
                "(pip wheel) or `npm pack` (npm tarball). NOT "
                "called during a playbook run."
            ),
            usage_hint=(
                "python3 bin/build_channel_package.py --stage"
            ),
        )
        return 0

    # v1.5.7 090a: full attribution banner at top of --help.
    _purpose.print_help_banner(argv)

    parser = argparse.ArgumentParser(
        prog="build_channel_package",
        description=(
            "Stage the QPB clone's source layout under "
            "quality_playbook_cli/_bundle/ for the pip channel + "
            "stamp the pip+npm manifests' version from SKILL.md. "
            "Run before `python -m build` (pip wheel) or `npm "
            "pack` (npm tarball)."
        ),
        epilog=(
            "Examples:\n"
            "  # Default: stage + stamp manifests\n"
            "  python3 bin/build_channel_package.py --stage\n\n"
            "  # Stamp only (no staging):\n"
            "  python3 bin/build_channel_package.py "
            "--stamp-only\n\n"
            + ATTRIBUTION_FOOTER_FOR_HELP
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    parser.add_argument(
        "--stage", action="store_true",
        help="Stage the bundle (default action when args given).",
    )
    parser.add_argument(
        "--stamp-only", action="store_true",
        help=(
            "Stamp the pip+npm channel manifests' version from "
            "SKILL.md but do NOT stage the bundle."
        ),
    )
    parser.add_argument(
        "--version", action="store_true",
        help="Print the SKILL.md version and exit.",
    )
    args = parser.parse_args(argv)

    if args.version:
        print(_purpose.get_version())
        return 0

    # Stamp the channel manifests from SKILL.md (089x T4 — single
    # source of truth: pip wheel + npm tarball versions match SKILL).
    changed = stamp_channel_manifest_versions(REPO_ROOT)
    for path, before, after in changed:
        print(
            f"build_channel_package: stamped "
            f"{path.relative_to(REPO_ROOT)}: {before} -> {after}"
        )

    if args.stamp_only:
        return 0

    staged = stage(REPO_ROOT, args.dest, clean=not args.no_clean)
    print(
        f"build_channel_package: staged {len(staged)} files into "
        f"{args.dest}"
    )
    return 0


# v1.5.7 089x T2: stitched into argparse's epilog so `--help` carries
# the lightweight attribution footer (the FULL 80-wide banner is
# install-success + run_playbook only).
ATTRIBUTION_FOOTER_FOR_HELP = (
    "Quality Playbook · by Andrew Stellman · "
    "https://github.com/andrewstellman/quality-playbook"
)


if __name__ == "__main__":
    sys.exit(main())
