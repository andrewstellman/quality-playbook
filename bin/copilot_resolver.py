"""v1.5.7 089f — CLI resolver for GitHub Copilot subprocess invocations.

GitHub deprecated the ``gh copilot`` extension on 2025-10-25; the
replacement is the standalone ``copilot`` CLI
(https://github.com/github/copilot-cli, installed via
``curl -fsSL https://gh.io/copilot-install | bash``, brew, winget, or
``npm install -g @github/copilot``). The two CLIs share enough flag
surface that we can shim transparently:

  +--------------------------+------------------------------+--------------------+
  | Concept                  | ``gh copilot`` (deprecated)  | ``copilot`` (new)  |
  +--------------------------+------------------------------+--------------------+
  | One-shot prompt          | ``-p`` / ``--prompt``        | ``-p`` / ``--prompt`` |
  | Auto-approve all tools   | ``--yolo``                   | ``--allow-all``    |
  |                          |                              | (``--yolo`` alias) |
  | Model selection          | ``--model <name>``           | ``--model <name>`` |
  | Help / availability      | ``gh copilot --help``        | ``copilot --help`` |
  +--------------------------+------------------------------+--------------------+

During the deprecation grace period some adopters have only
``gh copilot`` (their existing setup), some have only ``copilot``
(fresh installs after 2025-10), and some have both. The skill MUST
work for all three setups, so this resolver picks at runtime.

Detection rule (canonical order):

  1. If ``copilot`` is on PATH → use ``copilot`` (the new standalone CLI).
  2. Else if ``gh copilot --help`` returns 0 → use ``gh copilot``.
  3. Else → raise :class:`CopilotCLIUnavailable` with a remediation
     message that explains both install routes.

The detection result is cached for the lifetime of the process; tests
that need to exercise a specific path call :func:`reset_cache` and
mock :func:`shutil.which` plus the internal ``_probe_gh_copilot``
helper.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Tuple


# Cached detection state. Key "which" -> "copilot" | "gh-copilot" | "".
# Cleared by :func:`reset_cache` (tests only). A dict (not a module-
# level variable) so tests can monkeypatch the cache without rebinding
# names — see test_copilot_resolver.py for the pattern.
_CACHE: dict = {}


class CopilotCLIUnavailable(RuntimeError):
    """Raised by :func:`resolve_copilot_command` when neither
    ``copilot`` nor ``gh copilot`` is available on the host. The
    exception message is the canonical remediation message — surface
    it verbatim to the operator (it lists both install routes)."""


_REMEDIATION_MESSAGE = (
    "Neither `copilot` nor `gh copilot` is available on PATH.\n"
    "\n"
    "Install the standalone GitHub Copilot CLI (preferred; the new "
    "canonical form per https://github.com/github/copilot-cli):\n"
    "  - macOS:   brew install copilot-cli\n"
    "  - Windows: winget install GitHub.Copilot\n"
    "  - Linux:   curl -fsSL https://gh.io/copilot-install | bash\n"
    "  - npm:     npm install -g @github/copilot\n"
    "\n"
    "Or install the legacy `gh copilot` extension (deprecated "
    "2025-10-25; still works during the grace period):\n"
    "  gh extension install github/gh-copilot"
)


def reset_cache() -> None:
    """Clear the detection cache. Tests only.

    Production callers should never need this — detection is meant
    to be a once-per-process operation. The cache exists because
    repeated ``shutil.which`` plus subprocess probes are wasteful
    and would slow down every Mode B reviewer subprocess site.
    """
    _CACHE.clear()


def _probe_gh_copilot() -> bool:
    """Return True iff ``gh copilot --help`` exits 0.

    Returns False on ``FileNotFoundError`` (``gh`` not installed) or
    on any non-zero exit. This is the same probe shape that
    :func:`bin.benchmark_lib.require_copilot` used pre-089f; the
    behavior is preserved so that adopters who already pass the
    benchmark availability check don't see a regression.
    """
    try:
        result = subprocess.run(
            ["gh", "copilot", "--help"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def _detect_copilot_cli() -> str:
    """Detect which Copilot CLI is available (cached).

    Returns one of ``"copilot"``, ``"gh-copilot"``, or ``""`` (none).
    Order matters: ``copilot`` (the new standalone CLI) wins over
    ``gh copilot`` when both are available, because ``gh copilot`` is
    deprecated and adopters with both installed are mid-migration.
    """
    if "which" not in _CACHE:
        if shutil.which("copilot") is not None:
            _CACHE["which"] = "copilot"
        elif _probe_gh_copilot():
            _CACHE["which"] = "gh-copilot"
        else:
            _CACHE["which"] = ""
    return _CACHE["which"]


def require_copilot_cli() -> Tuple[bool, str]:
    """Return ``(available, which_cli)`` for the host's Copilot CLI.

    ``which_cli`` is one of ``"copilot"``, ``"gh-copilot"``, or
    ``""`` (none available). ``available`` is the boolean equivalent
    (``True`` when ``which_cli != ""``). The pair shape lets
    :func:`bin.benchmark_lib.require_copilot` keep its existing
    boolean-return signature while diagnostic-printing callers
    (``run_playbook.py``'s Mode B preview, ``qpb_validate.py``'s
    Phase 0 remediation) know which install route to recommend.
    """
    which = _detect_copilot_cli()
    return (which != "", which)


def resolve_copilot_command(
    prompt: str,
    model: str,
    *,
    allow_all: bool = False,
) -> list:
    """Return the subprocess command list for the available copilot CLI.

    Prefers the standalone ``copilot`` CLI (the new canonical form;
    GitHub deprecated ``gh copilot`` on 2025-10-25). Falls back to
    ``gh copilot`` when ``copilot`` is not on PATH. Raises
    :class:`CopilotCLIUnavailable` when neither is available; the
    exception message is the canonical remediation message
    (:data:`_REMEDIATION_MESSAGE`).

    Args:
      prompt:    Prompt text passed as the ``-p`` argument value.
      model:     Model identifier passed as ``--model`` argument
                 value (e.g., ``"claude-sonnet-4.6"``,
                 ``"gpt-5.5"``).
      allow_all: When True, append the auto-approve-all-tools flag
                 (``--allow-all`` for the new CLI, ``--yolo`` for
                 the legacy extension; the new CLI accepts ``--yolo``
                 as an alias but ``--allow-all`` is canonical per
                 ``copilot --help`` on 0.x).

    Returns:
      A subprocess argv list. Callers may wrap with
      :func:`bin.run_playbook._resolve_runner_command` for Windows
      ``.cmd``/``.bat`` shim resolution; the resolver itself returns
      bare-name argv (``["copilot", ...]`` or
      ``["gh", "copilot", ...]``).
    """
    which = _detect_copilot_cli()
    if which == "copilot":
        cmd = ["copilot", "-p", prompt, "--model", model]
        if allow_all:
            cmd.append("--allow-all")
        return cmd
    if which == "gh-copilot":
        cmd = ["gh", "copilot", "-p", prompt, "--model", model]
        if allow_all:
            cmd.append("--yolo")
        return cmd
    raise CopilotCLIUnavailable(_REMEDIATION_MESSAGE)


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='copilot_resolver',
        summary=(
            "Single-source resolver for the GitHub Copilot CLI surface — "
            "picks between the deprecated `gh copilot` extension and the "
            "newer standalone `copilot` CLI based on PATH availability. "
        ),
        role=(
            "Called by every code path that spawns a copilot reviewer "
            "(Council-of-Three runs in Phase 6, the autonomous reviewer "
            "loop, the workspace-addendum confirmation reviewer). "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
