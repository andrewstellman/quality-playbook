"""bin/qpb_config.py — per-operator config persistence (v1.5.7 Phase 6c).

Stdlib-only (no PyYAML / TOML write dependency). The config file is
JSON for hand-edit clarity; atomic writes via temp-file + os.replace.

File location resolution order:
  1. $XDG_CONFIG_HOME/qpb/config.json
  2. ~/.qpb/config.json

Schema:
  {
    "runner": "copilot",
    "council_members": ["claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6"]
  }

Both fields are optional; missing fields fall through to runner-side
defaults (DEFAULT_COUNCIL_MEMBERS for the roster; "copilot" for the
runner).

Public API:
  load_config() -> Optional[dict]   — returns parsed dict or None if missing/malformed
  save_config(updates: dict) -> None — atomic merge-and-write; preserves unknown keys
  unset_key(key: str) -> None       — remove a key (defaults take over)
  config_path() -> Path             — the active config file path (first existing, or write target)
  default_config_path() -> Path     — the write-target path (XDG-respecting)
  validate_roster(members) -> list[str]  — return list of warnings for unknown identifiers

CLI entry point: `python3 -m bin.qpb_config <show|set-runner|set-roster|unset> [...]`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional


CONFIG_BASENAME = "config.json"
CONFIG_SUBDIR = "qpb"
DEFAULT_HOME_DIR = ".qpb"


# v1.5.7 Phase 6c: known model identifiers for roster validation. Union of
# v1.5.6 + v1.5.7 rosters + curated alternatives. Unknown identifiers
# (typos, novel models the runner doesn't recognize yet) emit a non-fatal
# startup warning; the actual probe happens at Council launch time.
KNOWN_MODEL_IDENTIFIERS: frozenset[str] = frozenset({
    # v1.5.7 active roster
    "claude-opus-4.7",
    "gpt-5.5",
    "claude-sonnet-4.6",
    # v1.5.6 prior roster (preserved so historical configs don't warn)
    "gpt-5.4",
    "gemini-2.5-pro",
    # gpt-5.3-codex was used in v1.5.6 / v1.5.7 reviews
    "gpt-5.3-codex",
    # Curated alternatives adopters may select
    "claude-opus-4.6",
    "claude-sonnet-4.5",
    "claude-haiku-4.5",
    "gpt-4.1",
    "gpt-5-codex",
})


def default_config_path() -> Path:
    """Return the canonical write-target path for the config file.

    Prefers $XDG_CONFIG_HOME/qpb/config.json when XDG_CONFIG_HOME is
    set and non-empty; otherwise falls back to ~/.qpb/config.json.
    This is the path save_config() writes to. load_config() reads from
    a fallback chain (xdg path → home path).
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / CONFIG_SUBDIR / CONFIG_BASENAME
    return Path.home() / DEFAULT_HOME_DIR / CONFIG_BASENAME


def config_path() -> Path:
    """Return the active config file path (the first existing one,
    or the default write-target if neither exists).

    Resolution order:
      1. $XDG_CONFIG_HOME/qpb/config.json
      2. ~/.qpb/config.json
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        xdg_path = Path(xdg) / CONFIG_SUBDIR / CONFIG_BASENAME
        if xdg_path.is_file():
            return xdg_path
    home_path = Path.home() / DEFAULT_HOME_DIR / CONFIG_BASENAME
    if home_path.is_file():
        return home_path
    # Neither exists: return the default write-target so callers know
    # where save_config() would write.
    return default_config_path()


def load_config() -> Optional[dict]:
    """Return the parsed config dict, or None if no config file exists.

    Resolution order: $XDG_CONFIG_HOME/qpb/config.json → ~/.qpb/config.json.
    Malformed JSON: emit warning to stderr, return None (treat as
    missing config rather than crashing the runner).
    """
    path = config_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(
            f"WARN: qpb_config: malformed JSON in {path}: {exc}. "
            f"Treating as missing config.",
            file=sys.stderr,
        )
        return None
    except (OSError, UnicodeError) as exc:
        print(
            f"WARN: qpb_config: could not read {path}: {exc}. "
            f"Treating as missing config.",
            file=sys.stderr,
        )
        return None


def save_config(updates: dict) -> None:
    """Atomic merge-and-write of the config file. Preserves unknown
    keys (forward-compat).

    Writes to a temp file in the same directory + os.replace into
    place so the operation is atomic on POSIX filesystems. A
    mid-write crash leaves the original file unchanged.
    """
    target = default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    # Merge with existing config (if any) to preserve unknown keys.
    existing = load_config() or {}
    merged = {**existing, **updates}

    # Atomic write via temp-file + os.replace
    fd, tmp_name = tempfile.mkstemp(
        prefix=".config-",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(merged, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, target)
    except Exception:
        # Clean up the temp file if the rename failed.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def unset_key(key: str) -> None:
    """Remove a key from the config file. Defaults take over on next
    load. No-op if the key isn't present.
    """
    existing = load_config()
    if not existing or key not in existing:
        return
    del existing[key]
    target = default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".config-",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(existing, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def validate_roster(members) -> list[str]:
    """Return a list of warning strings for unknown identifiers in
    the roster. Empty list means all members are recognized.

    The validation is non-fatal: the warnings are printed at startup
    when applicable; the actual model probe happens at Council launch.
    """
    warnings = []
    for i, member in enumerate(members):
        if member not in KNOWN_MODEL_IDENTIFIERS:
            warnings.append(
                f"council_members[{i}] is {member!r} — unrecognized "
                f"model identifier; will probe at Council launch."
            )
    return warnings


def _split_roster(roster_arg: str) -> list[str]:
    """Parse a comma-separated roster string into a list of stripped
    member strings. Empty entries are dropped."""
    members = [m.strip() for m in roster_arg.split(",")]
    members = [m for m in members if m]
    return members


def _cmd_show() -> int:
    """`qpb config show` — print the current effective config."""
    cfg = load_config() or {}
    print(json.dumps(cfg, indent=2, sort_keys=True))
    # Also report the active config path so operators can find it.
    path = config_path()
    if path.is_file():
        print(f"# config file: {path}", file=sys.stderr)
    else:
        print(f"# no config file found; would write to: {default_config_path()}",
              file=sys.stderr)
    return 0


def _cmd_set_runner(name: str) -> int:
    """`qpb config set-runner <name>` — write the runner key."""
    save_config({"runner": name})
    print(f"runner set to: {name}")
    return 0


def _cmd_set_roster(roster_arg: str) -> int:
    """`qpb config set-roster <m1,m2,m3>` — write the council_members key."""
    members = _split_roster(roster_arg)
    if not members:
        print(
            "ERROR: empty roster; pass comma-separated member identifiers.",
            file=sys.stderr,
        )
        return 2
    warnings = validate_roster(members)
    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)
    save_config({"council_members": members})
    print(f"council_members set to: {members}")
    return 0


def _cmd_unset(key: str) -> int:
    """`qpb config unset <key>` — remove a key from the config."""
    unset_key(key)
    print(f"unset: {key}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for `python3 -m bin.qpb_config <subcommand> [...]`."""
    parser = argparse.ArgumentParser(
        prog="qpb config",
        description="QPB per-operator config persistence (v1.5.7+).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="Print the current effective config.")
    p_runner = sub.add_parser("set-runner", help="Write the runner key.")
    p_runner.add_argument("name", help="Runner name (claude / copilot / codex / cursor).")
    p_roster = sub.add_parser("set-roster", help="Write the council_members key.")
    p_roster.add_argument("members", help="Comma-separated member identifiers.")
    p_unset = sub.add_parser("unset", help="Remove a key from the config.")
    p_unset.add_argument("key", help="Key to remove.")

    args = parser.parse_args(argv)
    if args.cmd == "show":
        return _cmd_show()
    if args.cmd == "set-runner":
        return _cmd_set_runner(args.name)
    if args.cmd == "set-roster":
        return _cmd_set_roster(args.members)
    if args.cmd == "unset":
        return _cmd_unset(args.key)
    parser.error(f"unknown sub-command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
