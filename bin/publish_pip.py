"""bin/publish_pip.py — publish-time script for the pip distribution channel.

Drives the v1.5.8 publish sequence for ``quality-playbook`` on PyPI.
Calls ``bin/build_channel_package.py`` to stage the bundle, builds the
sdist + wheel via ``python -m build``, runs the 089u parity test, scans
the built artifacts for forbidden contents, then publishes to test PyPI
first, prompts the operator, then publishes to prod PyPI.

This script intentionally does NOT modify ``pyproject.toml`` or
``quality_playbook_cli/__init__.py``. Version bumps are operator-side
and are read by this script for parity verification — never written.

Cross-platform: pathlib + list-form subprocess args + utf-8 explicit.

Usage::

    python3 bin/publish_pip.py                # full publish flow
    python3 bin/publish_pip.py --dry-run      # everything except twine upload
    python3 bin/publish_pip.py --skip-tests   # skip the 089u parity test
    python3 bin/publish_pip.py --help         # show all flags

Exit codes:

- 0   success (or successful dry-run)
- 64  EX_USAGE — bad invocation
- 65  EX_DATAERR — pre-flight check failed (version mismatch, dirty
      tree, missing tag, forbidden bundle contents, twine not
      configured)
- 70  EX_SOFTWARE — subprocess failure during build/upload/verify

Pre-flight checks (executed in order, halt on first failure):

1. Clean working tree (``git status --porcelain`` empty + no untracked
   files under ``quality_playbook_cli/_bundle/``).
2. Version-string parity across ``pyproject.toml``, ``package.json``,
   and ``quality_playbook_cli/__init__.py:__version__``.
3. Tag ``v<version>`` exists.
4. Tag is an ancestor of HEAD (or operator explicitly confirms it is
   intentionally stale).
5. Build cleanly: ``python3 bin/build_channel_package.py`` then
   ``python3 -m build``.
6. Parity test passes: ``bin/tests/test_pip_channel_package_parity_089u.py``.
7. No forbidden contents in the built sdist/wheel (``.git/``,
   ``__pycache__/``, ``*.pyc``, ``quality/``, ``previous_runs/``,
   ``harness_runs/``, ``metrics/``, ``node_modules/``, ``.env``).
8. Twine auth configured (``~/.pypirc`` exists OR
   ``TWINE_USERNAME``/``TWINE_PASSWORD``/``TWINE_REPOSITORY_URL``
   env vars set).

Two-phase publish:

1. ``twine upload --repository testpypi dist/*``.
2. Operator confirmation prompt (``y/N``) — verify in clean venv first.
3. ``twine upload dist/*`` (prod PyPI).
4. Post-publish verification via ``pip index versions quality-playbook``
   (or curl fallback to ``https://pypi.org/pypi/quality-playbook/json``).

Logging: every run writes a structured log to
``~/.qpb/publish_logs/pip_<version>_<UTC-ISO8601>.log``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Tuple


EX_OK = 0
EX_USAGE = 64
EX_DATAERR = 65
EX_SOFTWARE = 70

PACKAGE_NAME = "quality-playbook"

# Forbidden path fragments inside the sdist/wheel. A match anywhere
# in the archive member path is a halt.
FORBIDDEN_FRAGMENTS: Tuple[str, ...] = (
    ".git/",
    "__pycache__/",
    "quality/",
    "previous_runs/",
    "harness_runs/",
    "metrics/",
    "node_modules/",
)
FORBIDDEN_SUFFIXES: Tuple[str, ...] = (
    ".pyc",
    ".env",
)
FORBIDDEN_BASENAMES: Tuple[str, ...] = (
    ".env",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _log_dir() -> Path:
    return Path.home() / ".qpb" / "publish_logs"


def _open_log(version: str) -> Tuple[Path, "open"]:
    d = _log_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"pip_{version}_{_utc_stamp()}.log"
    return p, p.open("w", encoding="utf-8")


def _log(log_fh, msg: str) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"[{ts}] {msg}"
    print(line)
    log_fh.write(line + "\n")
    log_fh.flush()


def _run(
    args: list[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """List-form subprocess with utf-8 decoded output, no shell."""
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------
# Pre-flight checks. Each returns (ok: bool, message: str). On ``ok=False``
# the caller halts with EX_DATAERR.
# ---------------------------------------------------------------------------


def check_clean_tree(repo_root: Path) -> Tuple[bool, str]:
    """Check 1: ``git status --porcelain`` empty + bundle dir not littered.

    The bundle directory ``quality_playbook_cli/_bundle/`` is staged by
    ``build_channel_package.stage()`` and cleaned automatically by
    ``--no-clean`` being absent. Untracked files there mean a previous
    interrupted build left state.
    """
    r = _run(["git", "status", "--porcelain"], cwd=repo_root, check=False)
    if r.returncode != 0:
        return False, f"git status failed: {r.stderr.strip()}"
    if r.stdout.strip():
        return False, (
            "Working tree is not clean. `git status --porcelain` reports:\n"
            + r.stdout
            + "\nCommit or stash before publishing."
        )
    # Specifically scan the bundle dir for stray untracked files.
    bundle = repo_root / "quality_playbook_cli" / "_bundle"
    if bundle.exists():
        r2 = _run(
            ["git", "status", "--porcelain", "--ignored", str(bundle)],
            cwd=repo_root,
            check=False,
        )
        if r2.returncode == 0 and r2.stdout.strip():
            return False, (
                "build_channel_package may have left state under "
                f"{bundle.relative_to(repo_root)} — clean it before "
                "publishing:\n" + r2.stdout
            )
    return True, "Working tree clean."


_VERSION_RE_TOML = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
_VERSION_RE_JSON = re.compile(r'"version"\s*:\s*"([^"]+)"')
_VERSION_RE_PY = re.compile(r'__version__\s*=\s*"([^"]+)"')


def _read_version(path: Path, regex: re.Pattern) -> Optional[str]:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    m = regex.search(text)
    return m.group(1) if m else None


def check_version_parity(repo_root: Path) -> Tuple[bool, str]:
    """Check 2: pyproject + package.json + __init__.py all agree."""
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
        return False, "Missing version string in one of the manifests:\n" + report
    if py == pkg == init:
        return True, f"Version parity OK at {py}.\n" + report
    return False, "Version-string MISMATCH:\n" + report


def check_tag_exists(repo_root: Path, version: str) -> Tuple[bool, str]:
    """Check 3: ``git tag --list v<version>`` returns the tag."""
    tag = f"v{version}"
    r = _run(["git", "tag", "--list", tag], cwd=repo_root, check=False)
    if r.returncode != 0:
        return False, f"git tag --list failed: {r.stderr.strip()}"
    if r.stdout.strip() != tag:
        return False, (
            f"Tag {tag} does NOT exist. Create it before publishing:\n"
            f"  git tag -a {tag} -m \"Quality Playbook {version}\""
        )
    r2 = _run(["git", "rev-parse", tag], cwd=repo_root, check=False)
    if r2.returncode != 0:
        return False, f"Tag {tag} exists but rev-parse failed: {r2.stderr.strip()}"
    return True, f"Tag {tag} exists at {r2.stdout.strip()}."


def check_tag_ancestor_of_head(
    repo_root: Path,
    version: str,
    *,
    confirm: Optional[bool] = None,
) -> Tuple[bool, str]:
    """Check 4: ``git merge-base --is-ancestor v<version> HEAD``.

    When the tag is NOT an ancestor of HEAD, prompt the operator unless
    ``confirm`` is set explicitly (True = yes, False = no, None = ask).
    """
    tag = f"v{version}"
    r = _run(
        ["git", "merge-base", "--is-ancestor", tag, "HEAD"],
        cwd=repo_root,
        check=False,
    )
    if r.returncode == 0:
        return True, f"Tag {tag} is an ancestor of HEAD."
    msg = (
        f"WARNING: Tag {tag} is NOT an ancestor of HEAD. Your tag "
        "might be stale, or you intentionally cherry-picked a fix."
    )
    if confirm is True:
        return True, msg + " (operator confirmed --yes-stale-tag)."
    if confirm is False:
        return False, msg + " (operator declined --yes-stale-tag)."
    try:
        ans = input(msg + " Continue? [y/N] ").strip().lower()
    except EOFError:
        ans = ""
    if ans == "y":
        return True, msg + " Operator confirmed at prompt."
    return False, msg + " Operator declined at prompt."


def check_build_clean(
    repo_root: Path,
    log_fh,
    *,
    skip: bool = False,
) -> Tuple[bool, str]:
    """Check 5: stage + ``python -m build`` succeed without error."""
    if skip:
        return True, "Build step skipped (--skip-build)."
    py = sys.executable
    # Stage the bundle.
    r1 = _run(
        [py, str(repo_root / "bin" / "build_channel_package.py"), "--stage"],
        cwd=repo_root,
        check=False,
    )
    log_fh.write("--- build_channel_package stdout ---\n")
    log_fh.write(r1.stdout or "")
    log_fh.write("--- build_channel_package stderr ---\n")
    log_fh.write(r1.stderr or "")
    if r1.returncode != 0:
        return False, (
            f"build_channel_package.py --stage failed (exit {r1.returncode}). "
            f"Tail of stderr:\n{(r1.stderr or '')[-2000:]}"
        )
    # Clean dist/ first to ensure we only scan fresh artifacts.
    dist = repo_root / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    # Build wheel + sdist.
    r2 = _run([py, "-m", "build"], cwd=repo_root, check=False)
    log_fh.write("--- python -m build stdout ---\n")
    log_fh.write(r2.stdout or "")
    log_fh.write("--- python -m build stderr ---\n")
    log_fh.write(r2.stderr or "")
    if r2.returncode != 0:
        return False, (
            f"python -m build failed (exit {r2.returncode}). "
            f"Tail of stderr:\n{(r2.stderr or '')[-2000:]}"
        )
    return True, "Build OK (staged + built wheel + sdist)."


def check_parity_test(repo_root: Path, *, skip: bool = False) -> Tuple[bool, str]:
    """Check 6: 089u parity test passes."""
    if skip:
        return True, "Parity test skipped (--skip-tests)."
    test_path = (
        repo_root
        / "bin"
        / "tests"
        / "test_pip_channel_package_parity_089u.py"
    )
    if not test_path.is_file():
        return False, f"Parity test not found at {test_path}."
    r = _run(
        [sys.executable, "-m", "pytest", "-v", str(test_path)],
        cwd=repo_root,
        check=False,
    )
    if r.returncode != 0:
        return False, (
            f"Parity test FAILED (exit {r.returncode}).\n"
            f"Tail of stdout:\n{(r.stdout or '')[-2000:]}"
        )
    return True, "Parity test passes."


def _scan_archive_for_forbidden(members: Iterable[str]) -> list[str]:
    hits = []
    for m in members:
        norm = m.replace("\\", "/")
        for frag in FORBIDDEN_FRAGMENTS:
            if frag in norm:
                hits.append(m)
                break
        else:
            for suf in FORBIDDEN_SUFFIXES:
                if norm.endswith(suf):
                    hits.append(m)
                    break
            else:
                base = norm.rsplit("/", 1)[-1]
                if base in FORBIDDEN_BASENAMES:
                    hits.append(m)
    return hits


def check_no_forbidden_contents(repo_root: Path) -> Tuple[bool, str]:
    """Check 7: scan sdist + wheel for forbidden paths."""
    dist = repo_root / "dist"
    if not dist.is_dir():
        return False, f"No dist/ directory at {dist} — run build step first."
    artifacts = sorted(list(dist.glob("*.whl")) + list(dist.glob("*.tar.gz")))
    if not artifacts:
        return False, f"No wheel or sdist found under {dist}."
    all_hits: list[str] = []
    for art in artifacts:
        try:
            if art.suffix == ".whl":
                with zipfile.ZipFile(art) as zf:
                    hits = _scan_archive_for_forbidden(zf.namelist())
            else:
                import tarfile
                with tarfile.open(art, "r:gz") as tf:
                    hits = _scan_archive_for_forbidden(tf.getnames())
        except (zipfile.BadZipFile, OSError) as e:
            return False, f"Could not read {art}: {e}"
        if hits:
            all_hits.append(f"{art.name}:")
            for h in hits[:25]:
                all_hits.append(f"    {h}")
            if len(hits) > 25:
                all_hits.append(f"    ... and {len(hits) - 25} more")
    if all_hits:
        return False, "Forbidden contents in build artifacts:\n" + "\n".join(all_hits)
    return True, f"No forbidden contents in {len(artifacts)} artifact(s)."


def check_twine_auth() -> Tuple[bool, str]:
    """Check 8: twine is importable AND credentials are reachable."""
    try:
        # Import directly; don't reach into private upload internals.
        import twine  # noqa: F401
        from twine.commands import upload as _twine_upload  # noqa: F401
    except ImportError as e:
        return False, (
            f"twine is not importable: {e}\n"
            "Install with: pip install twine"
        )
    pypirc = Path.home() / ".pypirc"
    env_user = os.environ.get("TWINE_USERNAME")
    env_pw = os.environ.get("TWINE_PASSWORD")
    env_url = os.environ.get("TWINE_REPOSITORY_URL")
    if pypirc.is_file():
        return True, f"twine auth: ~/.pypirc found at {pypirc}."
    if env_user and env_pw:
        return True, "twine auth: TWINE_USERNAME + TWINE_PASSWORD set."
    if env_url and env_pw:
        return True, "twine auth: TWINE_REPOSITORY_URL + TWINE_PASSWORD set."
    return False, (
        "No twine credentials found. Either create ~/.pypirc or set "
        "TWINE_USERNAME/TWINE_PASSWORD environment variables."
    )


# ---------------------------------------------------------------------------
# Publish actions.
# ---------------------------------------------------------------------------


def upload_testpypi(repo_root: Path, log_fh, *, dry_run: bool) -> Tuple[bool, str]:
    dist = repo_root / "dist"
    if dry_run:
        artifacts = sorted(list(dist.glob("*")))
        return True, (
            f"[dry-run] Would upload to test PyPI: "
            f"{[a.name for a in artifacts]}"
        )
    r = _run(
        [
            sys.executable, "-m", "twine", "upload",
            "--repository", "testpypi",
            str(dist / "*"),
        ],
        cwd=repo_root,
        check=False,
        capture=False,
    )
    if r.returncode != 0:
        return False, f"twine upload to testpypi failed (exit {r.returncode})."
    return True, "Uploaded to test PyPI."


def upload_prod(repo_root: Path, log_fh, *, dry_run: bool) -> Tuple[bool, str]:
    dist = repo_root / "dist"
    if dry_run:
        artifacts = sorted(list(dist.glob("*")))
        return True, (
            f"[dry-run] Would upload to PROD PyPI: "
            f"{[a.name for a in artifacts]}"
        )
    r = _run(
        [
            sys.executable, "-m", "twine", "upload",
            str(dist / "*"),
        ],
        cwd=repo_root,
        check=False,
        capture=False,
    )
    if r.returncode != 0:
        return False, f"twine upload to PyPI failed (exit {r.returncode})."
    return True, "Uploaded to PROD PyPI."


def verify_pypi_version(version: str, *, dry_run: bool) -> Tuple[bool, str]:
    """Confirm prod PyPI reports the new version.

    Try ``pip index versions`` first; fall back to the JSON API via urllib.
    """
    if dry_run:
        return True, f"[dry-run] Would verify {PACKAGE_NAME}=={version} on PyPI."
    r = _run(
        [sys.executable, "-m", "pip", "index", "versions", PACKAGE_NAME],
        check=False,
    )
    if r.returncode == 0 and version in (r.stdout or ""):
        return True, (
            f"pip index versions confirms {PACKAGE_NAME} {version} on PyPI."
        )
    # Fallback to JSON API.
    try:
        import urllib.request
        url = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latest = data.get("info", {}).get("version")
        releases = list((data.get("releases") or {}).keys())
        if latest == version or version in releases:
            return True, (
                f"PyPI JSON API confirms {PACKAGE_NAME} {version} "
                f"(latest={latest})."
            )
        return False, (
            f"PyPI does NOT report {version}. latest={latest}, "
            f"releases tail={releases[-5:]}"
        )
    except Exception as e:  # noqa: BLE001
        return False, f"PyPI verification failed: {e}"


# ---------------------------------------------------------------------------
# Driver.
# ---------------------------------------------------------------------------


def _confirm_prod() -> bool:
    """Operator confirmation prompt before prod PyPI upload."""
    try:
        ans = input(
            "\nRun the test-PyPI install command in a clean venv, "
            "verify `qpb --version` prints the right version, then "
            "come back.\nContinue with prod PyPI publish? [y/N] "
        ).strip().lower()
    except EOFError:
        return False
    return ans == "y"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="publish_pip",
        description=(
            "Publish the current 1.5.x state of quality-playbook to "
            "test PyPI then prod PyPI. Runs 8 pre-flight checks before "
            "the first upload."
        ),
        epilog=(
            "Logs to ~/.qpb/publish_logs/pip_<version>_<timestamp>.log. "
            "Re-running after a failure: clean dist/ and re-run."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all pre-flight checks + build, but DON'T call twine upload.",
    )
    p.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the 089u parity test (NOT for production).",
    )
    p.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the build step (assume dist/ is already populated).",
    )
    p.add_argument(
        "--yes-stale-tag",
        action="store_true",
        help="Acknowledge non-ancestor tag without prompting.",
    )
    p.add_argument(
        "--no-stale-tag",
        action="store_true",
        help="Halt without prompting if tag is not an ancestor of HEAD.",
    )
    return p.parse_args(argv)


def _print_intro() -> None:
    """v1.5.7 089x — self-describing no-args output. Routed via
    ``_purpose.print_command_intro`` so the script carries the
    ``Quality Playbook v<ver>`` line + ``Role in a playbook run:``
    label + ``by Andrew Stellman`` attribution footer the 089x
    meta-test pins for every shipped bin script. NO files are
    created — the publish-log handle is opened only when the
    operator passes a real argv (a flag like ``--dry-run`` or the
    no-arg-but-confirmed publish flow)."""
    try:
        from bin._purpose import print_command_intro as _print_command_intro
    except ImportError:
        from _purpose import print_command_intro as _print_command_intro  # type: ignore[no-redef]
    _print_command_intro(
        name="publish_pip",
        summary=(
            "Publish-time script for the pip distribution channel. "
            "Eight pre-flight checks (clean tree, version parity, tag, "
            "build, parity test, forbidden contents, twine auth) then "
            "two-phase publish: test PyPI -> operator-confirmed prod "
            "PyPI -> verification."
        ),
        role=(
            "Run by the operator at v1.5.x ship time, AFTER the version "
            "bumps and v<ver> tag are committed. Called from the "
            "operator's local checkout. Logs every run to "
            "~/.qpb/publish_logs/pip_<version>_<timestamp>.log."
        ),
        usage_hint="python3 bin/publish_pip.py --dry-run",
    )


def main(argv: Optional[list[str]] = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list:
        _print_intro()
        return 0
    args = parse_args(argv_list)
    repo_root = Path(__file__).resolve().parent.parent

    # Read version first so the log filename is right even if other
    # checks fail.
    py_version = _read_version(repo_root / "pyproject.toml", _VERSION_RE_TOML)
    version_for_log = py_version or "unknown"

    log_path, log_fh = _open_log(version_for_log)
    try:
        _log(log_fh, f"publish_pip starting. dry_run={args.dry_run} "
                     f"version={version_for_log} log={log_path}")
        _log(log_fh, f"repo_root={repo_root}")

        # 1. Clean tree.
        _log(log_fh, "Pre-flight 1/8: clean working tree...")
        ok, msg = check_clean_tree(repo_root)
        _log(log_fh, msg)
        if not ok:
            return EX_DATAERR

        # 2. Version parity.
        _log(log_fh, "Pre-flight 2/8: version-string parity...")
        ok, msg = check_version_parity(repo_root)
        _log(log_fh, msg)
        if not ok:
            return EX_DATAERR
        version = py_version  # parity confirmed; all three match

        # 3. Tag exists.
        _log(log_fh, "Pre-flight 3/8: tag exists...")
        ok, msg = check_tag_exists(repo_root, version)
        _log(log_fh, msg)
        if not ok:
            return EX_DATAERR

        # 4. Tag ancestor of HEAD.
        _log(log_fh, "Pre-flight 4/8: tag is ancestor of HEAD...")
        confirm: Optional[bool] = None
        if args.yes_stale_tag:
            confirm = True
        elif args.no_stale_tag:
            confirm = False
        ok, msg = check_tag_ancestor_of_head(repo_root, version, confirm=confirm)
        _log(log_fh, msg)
        if not ok:
            return EX_DATAERR

        # 5. Build cleanly.
        _log(log_fh, "Pre-flight 5/8: build cleanly...")
        ok, msg = check_build_clean(repo_root, log_fh, skip=args.skip_build)
        _log(log_fh, msg)
        if not ok:
            return EX_SOFTWARE

        # 6. Parity test.
        _log(log_fh, "Pre-flight 6/8: parity test...")
        ok, msg = check_parity_test(repo_root, skip=args.skip_tests)
        _log(log_fh, msg)
        if not ok:
            return EX_SOFTWARE

        # 7. No forbidden bundle contents.
        _log(log_fh, "Pre-flight 7/8: no forbidden contents in dist...")
        ok, msg = check_no_forbidden_contents(repo_root)
        _log(log_fh, msg)
        if not ok:
            return EX_DATAERR

        # 8. Twine auth.
        _log(log_fh, "Pre-flight 8/8: twine auth configured...")
        ok, msg = check_twine_auth()
        _log(log_fh, msg)
        if not ok:
            # Dry-run doesn't strictly need auth, but the published flow
            # would halt here, so report consistently in both modes.
            if not args.dry_run:
                return EX_DATAERR
            _log(log_fh, "(twine auth missing — continuing because --dry-run)")

        # Two-phase publish.
        _log(log_fh, "Pre-flight checks PASSED. Uploading to test PyPI...")
        ok, msg = upload_testpypi(repo_root, log_fh, dry_run=args.dry_run)
        _log(log_fh, msg)
        if not ok:
            _log(log_fh, "Publish state may be partial — check the "
                         "PyPI dashboard before retrying.")
            return EX_SOFTWARE

        install_cmd = (
            "pip install -i https://test.pypi.org/simple/ "
            "--extra-index-url https://pypi.org/simple/ "
            f"{PACKAGE_NAME}=={version}"
        )
        _log(log_fh, "Test PyPI install command for operator verification:")
        _log(log_fh, "  " + install_cmd)

        if args.dry_run:
            _log(log_fh, "[dry-run] Skipping prod PyPI prompt + upload.")
            return EX_OK

        if not _confirm_prod():
            _log(log_fh, "Operator declined prod PyPI upload. Halting.")
            return EX_OK

        _log(log_fh, "Uploading to prod PyPI...")
        ok, msg = upload_prod(repo_root, log_fh, dry_run=args.dry_run)
        _log(log_fh, msg)
        if not ok:
            _log(log_fh, "Publish state may be partial — check the "
                         "PyPI dashboard before retrying.")
            return EX_SOFTWARE

        _log(log_fh, "Verifying prod PyPI version...")
        ok, msg = verify_pypi_version(version, dry_run=args.dry_run)
        _log(log_fh, msg)
        if not ok:
            return EX_SOFTWARE

        _log(log_fh, "publish_pip DONE.")
        return EX_OK
    finally:
        log_fh.close()


if __name__ == "__main__":
    sys.exit(main())
