"""bin/publish_npm.py — publish-time script for the npm distribution channel.

Drives the v1.5.8 publish sequence for ``quality-playbook`` on
npmjs.com. Stages the bundle via ``bin/build_channel_package.py``,
verifies ``npm pack --dry-run`` reports a clean file list, prompts the
operator, then ``npm publish --access public``, then verifies via
``npm view quality-playbook version``.

This script intentionally does NOT modify ``pyproject.toml``,
``package.json``, or ``quality_playbook_cli/__init__.py``. Version
bumps are operator-side.

Cross-platform: pathlib + list-form subprocess args. ``npm`` is invoked
via ``shutil.which("npm")`` so the script halts cleanly when npm is not
on PATH instead of letting subprocess pick up an unexpected binary.

Usage::

    python3 bin/publish_npm.py                          # show intro
    python3 bin/publish_npm.py --dry-run                # preflights + pack, no publish
    python3 bin/publish_npm.py --publish                # preflights + pack + publish (LIVE)
    python3 bin/publish_npm.py --publish --otp 123456   # publish with pre-generated OTP
    python3 bin/publish_npm.py --help

``--dry-run`` and ``--publish`` are mutually exclusive; one must be
passed to run the workflow. ``--skip-stage`` modifies behavior
orthogonally and requires either ``--dry-run`` or ``--publish``
to take effect.

2FA-enabled npm accounts (recommended) require a per-publish OTP
code. If ``--otp`` isn't passed on the command line, the script
prompts interactively (``getpass.getpass``, no terminal echo)
immediately after the y/N confirmation. The OTP value is redacted
in the publish log so leaked logs can't expose it. Operators with
token-delete-after-use policies should rely on interactive OTP
rather than long-lived granular access tokens with bypass-2FA.

Exit codes:

- 0   success (or successful dry-run)
- 64  EX_USAGE — bad invocation
- 65  EX_DATAERR — pre-flight check failed
- 70  EX_SOFTWARE — subprocess failure during stage/pack/publish/verify

Pre-flight checks (executed in order, halt on first failure):

1. Clean working tree.
2. Version-string parity (pyproject.toml + package.json + __init__.py).
3. Tag ``v<version>`` exists.
4. ``npm whoami`` succeeds (npm CLI is logged in).
5. ``bin/build_channel_package.py --stage`` succeeds.
6. No forbidden bundle contents (``.git/``, ``__pycache__/``,
   ``*.pyc``, ``quality/``, ``previous_runs/``, ``harness_runs/``,
   ``metrics/``, ``node_modules/``, ``.env``).
7. ``npm pack --dry-run`` succeeds.

Publish:

1. Confirmation prompt with the file list from ``npm pack --dry-run``.
2. ``npm publish --access public``.
3. Post-publish verification via ``npm view quality-playbook version``.

Logging: ``~/.qpb/publish_logs/npm_<version>_<UTC-ISO8601>.log``.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Tuple


EX_OK = 0
EX_USAGE = 64
EX_DATAERR = 65
EX_SOFTWARE = 70

PACKAGE_NAME = "quality-playbook"

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
)
FORBIDDEN_BASENAMES: Tuple[str, ...] = (
    ".env",
)


# Reuse the version regexes from publish_pip's discipline.
_VERSION_RE_TOML = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
_VERSION_RE_JSON = re.compile(r'"version"\s*:\s*"([^"]+)"')
_VERSION_RE_PY = re.compile(r'__version__\s*=\s*"([^"]+)"')


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _log_dir() -> Path:
    return Path.home() / ".qpb" / "publish_logs"


def _open_log(version: str):
    d = _log_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"npm_{version}_{_utc_stamp()}.log"
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
    check: bool = False,
    capture: bool = True,
) -> subprocess.CompletedProcess:
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


def _resolve_npm() -> Optional[str]:
    """Look up npm on PATH. Returns the absolute path or None."""
    return shutil.which("npm")


def _read_version(path: Path, regex: re.Pattern) -> Optional[str]:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    m = regex.search(text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Pre-flight checks.
# ---------------------------------------------------------------------------


def check_clean_tree(repo_root: Path) -> Tuple[bool, str]:
    """Check 1: ``git status --porcelain`` empty.

    The bundle directory ``quality_playbook_cli/_bundle/`` is gitignored
    (``.gitignore:99``), so `git status --porcelain` correctly excludes it
    even when it exists on disk. The bundle is rebuilt deterministically by
    check 5 (``build_channel_package.py --stage``); any stale state is
    overwritten before ``npm publish`` sees it.
    """
    r = _run(["git", "status", "--porcelain"], cwd=repo_root)
    if r.returncode != 0:
        return False, f"git status failed: {r.stderr.strip()}"
    if r.stdout.strip():
        return False, (
            "Working tree not clean. `git status --porcelain` reports:\n"
            + r.stdout
            + "\nCommit or stash before publishing."
        )
    return True, "Working tree clean."


def check_version_parity(repo_root: Path) -> Tuple[bool, str]:
    py = _read_version(repo_root / "pyproject.toml", _VERSION_RE_TOML)
    pkg = _read_version(repo_root / "package.json", _VERSION_RE_JSON)
    init = _read_version(
        repo_root / "quality_playbook_cli" / "__init__.py",
        _VERSION_RE_PY,
    )
    if init is None:
        # quality_playbook_cli/__init__.py derives __version__ from SKILL.md
        # (single source, v1.5.10 instruction 057) and no longer carries a
        # literal; fall back to the canonical SKILL.md frontmatter version.
        _skill = repo_root / "SKILL.md"
        if _skill.is_file():
            for _line in _skill.read_text(encoding="utf-8").splitlines():
                _st = _line.strip()
                if _st.startswith("version:"):
                    init = _st.split(":", 1)[1].strip() or None
                    break
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
    tag = f"v{version}"
    r = _run(["git", "tag", "--list", tag], cwd=repo_root)
    if r.returncode != 0:
        return False, f"git tag --list failed: {r.stderr.strip()}"
    if r.stdout.strip() != tag:
        return False, (
            f"Tag {tag} does NOT exist. Create it before publishing."
        )
    return True, f"Tag {tag} exists."


def check_npm_whoami(npm: Optional[str]) -> Tuple[bool, str]:
    if npm is None:
        return False, "npm is not on PATH — install Node.js or fix PATH."
    r = _run([npm, "whoami"])
    if r.returncode != 0:
        return False, (
            "npm whoami failed — not logged in. Run `npm login` first.\n"
            f"  stderr: {(r.stderr or '').strip()}"
        )
    return True, f"npm logged in as: {r.stdout.strip()}"


def check_stage_bundle(
    repo_root: Path,
    log_fh,
    *,
    skip: bool = False,
) -> Tuple[bool, str]:
    if skip:
        return True, "Stage step skipped (--skip-stage)."
    r = _run(
        [
            sys.executable,
            str(repo_root / "bin" / "build_channel_package.py"),
            "--stage",
        ],
        cwd=repo_root,
    )
    log_fh.write("--- build_channel_package stdout ---\n")
    log_fh.write(r.stdout or "")
    log_fh.write("--- build_channel_package stderr ---\n")
    log_fh.write(r.stderr or "")
    if r.returncode != 0:
        return False, (
            f"build_channel_package.py --stage failed (exit {r.returncode}). "
            f"Tail of stderr:\n{(r.stderr or '')[-2000:]}"
        )
    return True, "Bundle staged for npm pack."


def _scan_for_forbidden(paths: Iterable[str]) -> list[str]:
    hits = []
    for p in paths:
        norm = p.replace("\\", "/")
        for frag in FORBIDDEN_FRAGMENTS:
            if frag in norm:
                hits.append(p)
                break
        else:
            for suf in FORBIDDEN_SUFFIXES:
                if norm.endswith(suf):
                    hits.append(p)
                    break
            else:
                base = norm.rsplit("/", 1)[-1]
                if base in FORBIDDEN_BASENAMES:
                    hits.append(p)
    return hits


def check_no_forbidden_in_bundle(repo_root: Path) -> Tuple[bool, str]:
    """Scan the staged bundle directory for forbidden contents.

    This is a pre-``npm pack`` check; if the bundle was staged with
    cruft, halt before packaging.
    """
    bundle = repo_root / "quality_playbook_cli" / "_bundle"
    if not bundle.is_dir():
        return False, (
            f"Staged bundle not found at {bundle}. Run --stage first."
        )
    members: list[str] = []
    for p in bundle.rglob("*"):
        if p.is_file():
            members.append(str(p.relative_to(bundle)).replace("\\", "/"))
    hits = _scan_for_forbidden(members)
    if hits:
        head = "\n    ".join(hits[:25])
        more = ("" if len(hits) <= 25
                else f"\n    ... and {len(hits) - 25} more")
        return False, f"Forbidden contents in staged bundle:\n    {head}{more}"
    return True, f"No forbidden contents in {len(members)} staged files."


def npm_pack_dry_run(
    repo_root: Path,
    npm: str,
    log_fh,
) -> Tuple[bool, str, list[str]]:
    """Run ``npm pack --dry-run --json`` and return the file list."""
    r = _run(
        [npm, "pack", "--dry-run", "--json"],
        cwd=repo_root,
    )
    log_fh.write("--- npm pack --dry-run --json stdout ---\n")
    log_fh.write(r.stdout or "")
    log_fh.write("--- npm pack --dry-run --json stderr ---\n")
    log_fh.write(r.stderr or "")
    if r.returncode != 0:
        return False, f"npm pack --dry-run failed (exit {r.returncode}).", []
    # npm prepack may emit progress text to stdout before npm's JSON
    # output. Find the JSON array (or object) start and parse from
    # there. Belt + suspenders with build_channel_package's stderr
    # discipline (instruction 203). Full unmodified stdout is still
    # captured to the publish log above for post-mortem.
    stdout = r.stdout or ""
    json_start = stdout.find("[")
    if json_start < 0:
        return (
            False,
            "npm pack JSON parse failed: no '[' in stdout (stdout="
            + repr(stdout[:200])
            + ")",
            [],
        )
    json_payload = stdout[json_start:]
    try:
        data = json.loads(json_payload)
    except json.JSONDecodeError as e:
        return False, f"npm pack JSON parse failed: {e}", []
    if not data:
        return False, "npm pack returned no entries.", []
    files = []
    for entry in data:
        for f in entry.get("files") or []:
            path = f.get("path")
            if path:
                files.append(path)
    # Also scan the file list for forbidden contents (defense in depth).
    hits = _scan_for_forbidden(files)
    if hits:
        head = "\n    ".join(hits[:25])
        more = ("" if len(hits) <= 25
                else f"\n    ... and {len(hits) - 25} more")
        return (
            False,
            f"npm pack file list contains forbidden contents:\n    {head}{more}",
            files,
        )
    return True, f"npm pack --dry-run OK ({len(files)} files).", files


# ---------------------------------------------------------------------------
# Publish actions.
# ---------------------------------------------------------------------------


def run_npm_publish(
    repo_root: Path,
    npm: str,
    otp: Optional[str],
    log_fh,
) -> Tuple[bool, str]:
    """Run ``npm publish --access public`` with optional 2FA OTP.

    v1.5.8 instruction 205: npm rejects publish from 2FA-enabled
    accounts with E403 unless ``--otp <code>`` is passed. ``otp`` is
    an empty string or None for accounts without 2FA. The OTP value
    is redacted (``<REDACTED>``) in the publish log so leaked logs
    can't expose it.
    """
    cmd = [npm, "publish", "--access", "public"]
    if otp:
        cmd.extend(["--otp", otp])
    # Log-discipline: write the command line with the OTP value
    # redacted before invoking the subprocess.
    redacted_cmd = list(cmd)
    for i, tok in enumerate(redacted_cmd):
        if tok == "--otp" and i + 1 < len(redacted_cmd):
            redacted_cmd[i + 1] = "<REDACTED>"
    _log(log_fh, f"npm publish cmd: {redacted_cmd}")
    r = _run(cmd, cwd=repo_root, capture=False)
    if r.returncode != 0:
        return False, f"npm publish failed (exit {r.returncode})."
    return True, "Published to npm."


# Backwards-compat shim for the dry-run path. Pre-205 callers passed
# ``dry_run=True`` to get a "would run" message without invoking
# subprocess. main() now handles the dry-run branch directly before
# calling run_npm_publish, but keep the legacy wrapper for callers
# that import npm_publish by name.
def npm_publish(
    repo_root: Path,
    npm: str,
    log_fh,
    *,
    dry_run: bool,
    otp: Optional[str] = None,
) -> Tuple[bool, str]:
    if dry_run:
        return True, "[dry-run] Would run: npm publish --access public"
    return run_npm_publish(repo_root, npm, otp, log_fh)


def verify_npm_version(
    npm: str,
    version: str,
    *,
    dry_run: bool,
) -> Tuple[bool, str]:
    if dry_run:
        return True, f"[dry-run] Would verify {PACKAGE_NAME}@{version} on npm."
    r = _run([npm, "view", PACKAGE_NAME, "version"])
    if r.returncode != 0:
        return False, (
            f"npm view failed (exit {r.returncode}): {(r.stderr or '').strip()}"
        )
    found = (r.stdout or "").strip()
    if found != version:
        return False, (
            f"npm view reports version={found!r}, expected {version!r}. "
            "Publish may not have propagated yet — wait 30s and retry."
        )
    return True, f"npm view confirms {PACKAGE_NAME}@{version}."


# ---------------------------------------------------------------------------
# Driver.
# ---------------------------------------------------------------------------


def _confirm_publish(version: str, files: list[str]) -> bool:
    print(f"\nAbout to publish {PACKAGE_NAME}@{version} to npm.")
    print("Files to be shipped (from npm pack --dry-run):")
    for f in files[:60]:
        print(f"  {f}")
    if len(files) > 60:
        print(f"  ... and {len(files) - 60} more")
    try:
        ans = input("\nContinue with `npm publish --access public`? [y/N] ")
    except EOFError:
        return False
    return ans.strip().lower() == "y"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="publish_npm",
        description=(
            "Publish the current 1.5.x state of quality-playbook to npm. "
            "Runs 7 pre-flight checks before npm publish."
        ),
        epilog="Logs to ~/.qpb/publish_logs/npm_<version>_<timestamp>.log.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all pre-flight checks + npm pack, but DON'T call npm publish. "
             "Mutually exclusive with --publish.",
    )
    p.add_argument(
        "--publish",
        action="store_true",
        help="Run all pre-flight checks + npm pack + `npm publish --access "
             "public` (LIVE). Mutually exclusive with --dry-run.",
    )
    p.add_argument(
        "--skip-stage",
        action="store_true",
        help="Skip the build_channel_package stage step (assume bundle is fresh).",
    )
    p.add_argument(
        "--otp",
        type=str,
        default=None,
        metavar="CODE",
        help="6-digit npm 2FA OTP code. Required if your npm account "
             "has 2FA enabled. If not provided on the command line "
             "and --publish is set, the script prompts for it "
             "interactively (via getpass, no echo) immediately before "
             "calling `npm publish`.",
    )
    return p.parse_args(argv)


def _print_intro() -> None:
    """v1.5.7 089x — self-describing no-args output. Same shape as
    publish_pip's intro; pinned by
    ``test_scripts_self_describing_089x.py``."""
    try:
        from bin._purpose import print_command_intro as _print_command_intro
    except ImportError:
        from _purpose import print_command_intro as _print_command_intro  # type: ignore[no-redef]
    _print_command_intro(
        name="publish_npm",
        summary=(
            "Publish-time script for the npm distribution channel. "
            "Seven pre-flight checks (clean tree, version parity, tag, "
            "npm whoami, stage bundle, forbidden contents, npm pack "
            "dry-run) then operator-confirmed `npm publish --access "
            "public` + npm view verification."
        ),
        role=(
            "Run by the operator at v1.5.x ship time, AFTER the version "
            "bumps and v<ver> tag are committed AND AFTER publish_pip "
            "succeeded. Logs every run to "
            "~/.qpb/publish_logs/npm_<version>_<timestamp>.log."
        ),
        usage_hint=(
            "python3 bin/publish_npm.py --dry-run\n"
            "  or: python3 bin/publish_npm.py --publish "
            "[--otp <code>]"
        ),
    )


def main(argv: Optional[list[str]] = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list:
        _print_intro()
        return 0
    args = parse_args(argv_list)

    # v1.5.8 instruction 204: require explicit --dry-run XOR --publish
    # affirmation. Pre-204, any flag (e.g. --skip-stage alone) would
    # fall through to the live publish path because args.dry_run was
    # False — same bug shape as publish_pip.py.
    if args.dry_run and args.publish:
        print(
            "ERROR: --dry-run and --publish are mutually exclusive. "
            "Pick one.",
            file=sys.stderr,
        )
        return EX_USAGE
    if not args.dry_run and not args.publish:
        print(
            "ERROR: must pass --dry-run or --publish.\n"
            "  --dry-run runs preflights + npm pack without publishing.\n"
            "  --publish runs preflights + npm pack + npm publish "
            "--access public.",
            file=sys.stderr,
        )
        return EX_USAGE
    repo_root = Path(__file__).resolve().parent.parent

    py_version = _read_version(repo_root / "pyproject.toml", _VERSION_RE_TOML)
    version_for_log = py_version or "unknown"

    log_path, log_fh = _open_log(version_for_log)
    try:
        _log(log_fh, f"publish_npm starting. dry_run={args.dry_run} "
                     f"version={version_for_log} log={log_path}")
        _log(log_fh, f"repo_root={repo_root}")

        # 1. Clean tree.
        _log(log_fh, "Pre-flight 1/7: clean working tree...")
        ok, msg = check_clean_tree(repo_root)
        _log(log_fh, msg)
        if not ok:
            return EX_DATAERR

        # 2. Version parity.
        _log(log_fh, "Pre-flight 2/7: version-string parity...")
        ok, msg = check_version_parity(repo_root)
        _log(log_fh, msg)
        if not ok:
            return EX_DATAERR
        version = py_version

        # 3. Tag exists.
        _log(log_fh, "Pre-flight 3/7: tag exists...")
        ok, msg = check_tag_exists(repo_root, version)
        _log(log_fh, msg)
        if not ok:
            return EX_DATAERR

        # 4. npm whoami. Skip in dry-run when npm is missing — the
        # operator should be able to validate the rest of the flow on
        # a fresh machine without logging in.
        npm = _resolve_npm()
        _log(log_fh, "Pre-flight 4/7: npm whoami...")
        ok, msg = check_npm_whoami(npm)
        _log(log_fh, msg)
        if not ok:
            if args.dry_run and npm is None:
                _log(log_fh, "(npm missing — continuing because --dry-run)")
            else:
                return EX_DATAERR

        # 5. Stage bundle.
        _log(log_fh, "Pre-flight 5/7: stage bundle...")
        ok, msg = check_stage_bundle(repo_root, log_fh, skip=args.skip_stage)
        _log(log_fh, msg)
        if not ok:
            return EX_SOFTWARE

        # 6. No forbidden in staged bundle.
        _log(log_fh, "Pre-flight 6/7: no forbidden contents in staged bundle...")
        ok, msg = check_no_forbidden_in_bundle(repo_root)
        _log(log_fh, msg)
        if not ok:
            return EX_DATAERR

        # 7. npm pack --dry-run.
        _log(log_fh, "Pre-flight 7/7: npm pack --dry-run...")
        if npm is None:
            if args.dry_run:
                _log(log_fh, "[dry-run] Skipping npm pack (npm not on PATH).")
                files: list[str] = []
            else:
                _log(log_fh, "npm is not on PATH — cannot run npm pack.")
                return EX_DATAERR
        else:
            ok, msg, files = npm_pack_dry_run(repo_root, npm, log_fh)
            _log(log_fh, msg)
            if not ok:
                return EX_SOFTWARE

        _log(log_fh, "Pre-flight checks PASSED.")
        if args.dry_run:
            _log(log_fh, "[dry-run] Skipping confirmation + npm publish.")
            return EX_OK

        if not _confirm_publish(version, files):
            _log(log_fh, "Operator declined npm publish. Halting.")
            return EX_OK

        # v1.5.8 instruction 205: resolve OTP for 2FA-enabled accounts.
        # Prompt happens AFTER the y/N confirmation and immediately
        # before `npm publish` to minimize the OTP-expiry window
        # (~30s). getpass.getpass suppresses terminal echo so the
        # operator's typed OTP doesn't end up in shell scrollback.
        otp = args.otp
        if otp is None:
            try:
                otp = getpass.getpass(
                    "Enter npm 2FA OTP code (6 digits; leave empty "
                    "if no 2FA on account): "
                ).strip()
            except EOFError:
                otp = ""

        _log(log_fh, "Publishing to npm...")
        ok, msg = run_npm_publish(repo_root, npm, otp or None, log_fh)
        _log(log_fh, msg)
        if not ok:
            _log(log_fh, "Publish state may be partial — check the "
                         "npm dashboard before retrying.")
            return EX_SOFTWARE

        _log(log_fh, "Verifying npm version...")
        ok, msg = verify_npm_version(npm, version, dry_run=args.dry_run)
        _log(log_fh, msg)
        if not ok:
            return EX_SOFTWARE

        _log(log_fh, "publish_npm DONE.")
        return EX_OK
    finally:
        log_fh.close()


if __name__ == "__main__":
    sys.exit(main())
