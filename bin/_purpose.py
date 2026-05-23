"""v1.5.7 089x — shared helper: ``get_version()`` + purpose banners
+ full attribution banner.

This module is the single source of truth for THREE concerns that
were duplicated/scattered across the ``bin/`` tree:

1. **Version reading from SKILL.md** (``get_version()``). Pre-089x
   there were two readers: ``install_skill._read_skill_version``
   and ``benchmark_lib.detect_skill_version`` (plus
   ``benchmark_lib.skill_version``). 089x consolidates them — the
   two existing readers now delegate here.

2. **Per-script PURPOSE banner** (``print_purpose()``). Lightweight,
   human-readable banner printed on every bin script's no-args
   path (and ``--help``). Format:

       Quality Playbook v<VERSION> · <script-name>[ (library — not a command)]
       <one-line summary of what this script is>

       Role in a playbook run: <where/when it's used>

       <CLI:> This is a command — run with --help for options[, or: <example>]
       <lib:> Nothing to run here directly — the playbook calls this module.
              For commands: python3 -m bin.run_playbook --help

       Quality Playbook · by Andrew Stellman · <URL>

   Streams to **stdout** by default (preserves the 089k clean-
   stdout-event= rule: the purpose banner is the script's
   primary output when invoked bare, not a side-channel
   informational write).

3. **Full attribution banner** (``print_attribution_banner()``).
   The ceremonial 80-wide box originally defined in
   ``install_skill.py:262-280``. 089x lifts the constants +
   render here so install_skill (existing) + run_playbook (089x
   T6 addition) can share ONE source. Streams to **stderr** by
   default (089k clean-stdout-event= rule preserved).

**Load-bearing back-compat**: ``install_skill.py`` re-exports the
``_BANNER_*`` constants from this module (via a defensive
lazy-load that works in both clone and shim contexts — the 089u
pip shim and 089v npm shim load install_skill via importlib
without ``bin/`` on sys.path). The 089l drift-guard test
``test_install_skill_banner_089j.py`` reads
``install_skill._BANNER_NAME`` etc.; those reads continue to
work because install_skill rebinds them from this module. Any
banner-text edit lands here once and propagates through the
re-export.

Stdlib-only — runs cleanly in every Python ≥3.10 context the
bundle ships in (clone, wheel, npm tarball, adopter install).
No import-time side effects.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional, TextIO


# ---------------------------------------------------------------------------
# Attribution banner constants (canonical — install_skill re-exports these)
#
# 089l: 80-wide box rule + two-line tagline. The drift-guard test
# (test_install_skill_banner_089j.py) pins these byte-identical to the
# banner block AGENTS.md embeds, so an edit here must be matched in
# AGENTS.md or the test fires.
# ---------------------------------------------------------------------------

BANNER_NAME: str = "Quality Playbook"
BANNER_AUTHOR: str = "Andrew Stellman"
BANNER_URL: str = "https://github.com/andrewstellman/quality-playbook"
BANNER_TAGLINE: tuple[str, str] = (
    "AI code review is good. Quality engineering is better.",
    "Because code that looks right can still do the wrong thing.",
)
BANNER_LICENSE: str = "Apache License, Version 2.0"
BANNER_BOX_WIDTH: int = 80
BANNER_BOX_RULE: str = "=" * BANNER_BOX_WIDTH

BANNER_TEXT: str = (
    f"{BANNER_BOX_RULE}\n"
    f"  {BANNER_NAME} — by {BANNER_AUTHOR}\n"
    f"  {BANNER_URL}\n"
    "\n"
    f"  {BANNER_TAGLINE[0]}\n"
    f"  {BANNER_TAGLINE[1]}\n"
    "\n"
    f"  Licensed under the {BANNER_LICENSE}\n"
    f"{BANNER_BOX_RULE}\n"
)


# ---------------------------------------------------------------------------
# Version reader — single source (consolidates 089x T4)
# ---------------------------------------------------------------------------

# Frontmatter version line: `version: 1.5.7` (with optional surrounding
# quotes; trailing whitespace tolerated). Matches the regex
# install_skill._parse_yaml_frontmatter would yield for the version key.
_VERSION_LINE_RE = re.compile(
    r'^\s*version\s*:\s*"?([^"\s]+)"?\s*$', re.MULTILINE
)


def _skill_md_candidates() -> list[Path]:
    """Return ordered SKILL.md candidate paths to try.

    The resolution order:
      1. ``<this_file>/../SKILL.md`` — the natural location in EVERY
         context this module ships in: clone (``<repo>/SKILL.md``),
         pip wheel bundle (``<...>/quality_playbook_cli/_bundle/
         SKILL.md``), npm tarball bundle (same path), adopter install
         (``<target>/.claude/skills/quality-playbook/SKILL.md``).
      2. ``Path.cwd() / 'SKILL.md'`` — fallback if a script is invoked
         from a SKILL.md root that's distinct from the module's
         directory (rare but cheap to support).
    """
    here = Path(__file__).resolve()
    cands: list[Path] = []
    primary = here.parent.parent / "SKILL.md"
    if primary.is_file():
        cands.append(primary)
    cwd_cand = Path.cwd() / "SKILL.md"
    if cwd_cand.is_file() and cwd_cand.resolve() not in [
        c.resolve() for c in cands
    ]:
        cands.append(cwd_cand)
    return cands


def _read_version_from(path: Path) -> Optional[str]:
    """Parse SKILL.md frontmatter and return the ``version:`` value,
    or None on any failure (missing file, unreadable, no version
    key in frontmatter)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None
    # Limit to the frontmatter block if present (between two `---`
    # fences at the file start). Falling through to a whole-file
    # regex is fine — SKILL.md only has a `version:` line in
    # frontmatter, never in the body — but we keep the search bounded
    # for clarity.
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            text = text[: end + 4]
    m = _VERSION_LINE_RE.search(text)
    if m:
        return m.group(1).strip()
    return None


def get_version() -> str:
    """Return the v1.5.7 skill version from SKILL.md frontmatter.

    THE canonical version reader (089x T4). Graceful fallback to
    ``"unknown"`` on any failure — the purpose banner must never
    crash on a missing or malformed SKILL.md, since that would
    defeat the no-args-safety guarantee.
    """
    for cand in _skill_md_candidates():
        v = _read_version_from(cand)
        if v:
            return v
    return "unknown"


# ---------------------------------------------------------------------------
# Lightweight attribution footer (one-liner; on every purpose banner)
# ---------------------------------------------------------------------------


def attribution_footer() -> str:
    """The lightweight attribution footer — one line, name + author +
    URL. Goes on every purpose banner and every ``--help`` epilog.
    The FULL 80-wide box is reserved for install-success +
    playbook run start/end."""
    return f"{BANNER_NAME} · by {BANNER_AUTHOR} · {BANNER_URL}"


# ---------------------------------------------------------------------------
# Per-script purpose banner
# ---------------------------------------------------------------------------


PURPOSE_ROLE_LABEL: str = "Role in a playbook run:"


def print_purpose(
    name: str,
    summary: str,
    role: str,
    *,
    kind: str = "command",
    usage_hint: Optional[str] = None,
    stream: Optional[TextIO] = None,
    footer: bool = True,
) -> None:
    """Print the per-script PURPOSE banner.

    Parameters
    ----------
    name
        The script's display name (without ``bin/`` prefix, no ``.py``).
        Example: ``"install_skill"``, ``"benchmark_lib"``.
    summary
        One-line summary of what the script is / does. No trailing period
        is added — write the sentence as you want it to appear.
    role
        One- or two-line description of where/when the script is used in
        a playbook run. The literal label ``"Role in a playbook run:"``
        prefixes this in the output (pinned by
        ``test_scripts_self_describing_089x.py``).
    kind
        ``"command"`` (default) — the script is a user-invocable CLI.
        ``"library"`` — the module is imported by other code and not
        meant to be run directly. Affects the closing hint.
    usage_hint
        Optional one-line example invocation shown alongside the
        "run with --help" hint (commands only).
    stream
        Output stream. Defaults to ``sys.stdout`` — the purpose banner
        IS the script's output on a bare invocation; it must reach the
        same descriptor any other CLI output would.
    footer
        Whether to append the lightweight attribution footer (one-line
        name + author + URL) at the bottom of the banner. Default
        ``True``. 090a sets it ``False`` from
        ``print_command_intro()``, where the FULL attribution banner
        has already supplied the name + URL — printing the lightweight
        footer too would double-attribute. The 089x meta-test only
        requires that the GitHub URL + "by Andrew Stellman" string
        appear *somewhere* in stdout, so caller-side dropping of the
        footer is safe when the full banner is also emitted.
    """
    if stream is None:
        stream = sys.stdout
    version = get_version()
    kind_marker = "  (library — not a command)" if kind == "library" else ""

    lines: list[str] = [
        f"Quality Playbook v{version} · {name}{kind_marker}",
        summary,
        "",
        f"{PURPOSE_ROLE_LABEL} {role}",
        "",
    ]
    if kind == "library":
        lines.append(
            "Nothing to run here directly — the playbook calls this "
            "module. For commands: python3 -m bin.run_playbook --help"
        )
    else:
        if usage_hint:
            lines.append(
                "This is a command — run with --help for options, "
                f"or: {usage_hint}"
            )
        else:
            lines.append("This is a command — run with --help for options")
    if footer:
        lines.append("")
        lines.append(attribution_footer())

    try:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
    except (OSError, ValueError):
        # Purpose banner is informational; a broken stream must not
        # break the script. Mirror install_skill._print_banner's
        # graceful-stream-error pattern.
        pass


def print_command_intro(
    name: str,
    summary: str,
    role: str,
    *,
    usage_hint: Optional[str] = None,
    stream: Optional[TextIO] = None,
) -> None:
    """v1.5.7 090a — combined CLI intro: FULL attribution banner +
    purpose banner (no lightweight footer), both to stdout by
    default.

    Used by every user-facing CLI's bare-no-args path. Pre-090a
    the no-args path printed only the lightweight purpose banner +
    one-line footer; 090a revises 089x's banner split to show the
    full 80-wide attribution banner on the no-args invocation
    (and at the top of ``--help`` via ``print_help_banner``).

    The full banner appears FIRST as a ceremonial header; the
    purpose banner follows with the script-specific role + usage
    hint. The purpose banner's lightweight footer is suppressed
    here because the full banner already supplied the name + URL
    — printing both would double-attribute.

    Libraries (``kind="library"``) are explicitly out of scope —
    they keep the lightweight purpose banner + footer (090a's
    CLI-vs-library line is deliberate; the full banner on every
    internal library's bare-run is repetitive noise).
    """
    if stream is None:
        stream = sys.stdout
    print_attribution_banner(stream=stream)
    print_purpose(
        name=name,
        summary=summary,
        role=role,
        kind="command",
        usage_hint=usage_hint,
        stream=stream,
        footer=False,
    )


def print_help_banner(
    argv: list[str],
    *,
    stream: Optional[TextIO] = None,
) -> bool:
    """v1.5.7 090a — emit the full attribution banner to stdout if
    ``argv`` contains ``-h`` or ``--help``. Used by CLIs to put
    the banner at the top of ``--help`` output, above argparse's
    usage / description / epilog.

    Returns ``True`` iff the banner was emitted (so a caller can
    branch on it if needed). The default stream is stdout — the
    full banner on the no-args + ``--help`` paths is stdout (the
    089k clean-``event=`` rule applies to *runs*, not to
    informational discovery actions).
    """
    if stream is None:
        stream = sys.stdout
    if "-h" in argv or "--help" in argv:
        print_attribution_banner(stream=stream)
        return True
    return False


# ---------------------------------------------------------------------------
# Full attribution banner (install-success + run_playbook start/end only)
# ---------------------------------------------------------------------------


def print_attribution_banner(stream: Optional[TextIO] = None) -> None:
    """Print the full 80-wide attribution banner.

    Default stream is **stderr** (preserves the 089k clean-stdout-
    ``event=`` rule). Called by:
      - ``install_skill._print_banner`` at the END of a successful
        install (existing behavior; re-export below).
      - ``run_playbook`` at the START and END of a Mode-B playbook
        run (089x T6, new).

    NOT called by ``--help`` or any library no-args path — those use
    ``print_purpose`` + the lightweight footer.
    """
    if stream is None:
        stream = sys.stderr
    try:
        stream.write(BANNER_TEXT)
        stream.flush()
    except (OSError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Module __main__ — purpose banner on no-args (089x T3 invariant: every
# bin/*.py is safe + self-describing).
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    print_purpose(
        name="_purpose",
        summary=(
            "Shared helper for the bin/ tree: version reader + "
            "purpose-banner renderer + full-attribution-banner "
            "renderer. Used by every other bin script's no-args "
            "path."
        ),
        role=(
            "Imported by every bin/ module. Not run during a "
            "playbook execution — the modules that import it "
            "(install_skill, run_playbook, qpb_validate, …) are "
            "the user-facing entry points."
        ),
        kind="library",
    )
    sys.exit(0)
