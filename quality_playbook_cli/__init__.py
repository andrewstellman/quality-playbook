"""v1.5.7 089u — quality_playbook_cli: thin entry-point shim for the
pip distribution channel.

`quality-playbook` (the console script) routes through
`quality_playbook_cli.main()`, which:

  1. Locates the package's bundled QPB source-layout data (staged at
     publish time from `bin.install_skill._bundle_files()` by
     `bin/build_channel_package.py`).
  2. Sets ``QPB_CHANNEL=pip`` in the environment so
     ``bin/qpb_validate.py``'s remediation emits the
     ``uvx quality-playbook …`` / ``pipx run quality-playbook …``
     form rather than the clone form (back-compat default).
  3. Loads the bundled ``bin/install_skill.py`` via importlib (NOT
     via a top-level ``import bin``) — that file is stdlib-only and
     self-contained, so it runs cleanly without any sibling
     ``from bin import`` resolution.
  4. Defaults ``--source`` to the packaged bundle root and invokes
     the same ``install_skill.main()`` the clone workflow uses, so
     the install behavior is byte-identical to ``python3 -m
     bin.install_skill`` from a clone.

**Hard packaging constraint** (089u decision, 2026-05-22): the full
``bin/`` tooling closure ships as **package data**, NOT as an
importable top-level ``bin`` package. After ``pip install
quality-playbook``, ``python -c "import bin"`` MUST FAIL — only
``import quality_playbook_cli`` resolves. The shim never adds the
bundle's ``bin/`` to top-level ``sys.path``; it loads
``install_skill.py`` by file path via ``importlib.util``.

Public CLI surface (thin aliases over the bundled scripts):

    quality-playbook install <target-repo> --ai-tool <tool>
    quality-playbook install --into <repo> --ai-tool <tool> --force
    quality-playbook install --help            # install_skill help
    quality-playbook validate <target-repo>    # runs qpb_validate
    quality-playbook validate --help           # qpb_validate help
    quality-playbook --help                    # alias for `install --help`

Two subcommand verbs are wired at v1.5.7: ``install`` (routes to
``bin/install_skill.py``) and ``validate`` (routes to
``bin/qpb_validate.py``). The latter exists so the pip-channel
remediation strings ``qpb_validate.py`` emits — e.g. *"verify with:
`uvx quality-playbook validate <target>`"* — actually resolve to a
runnable command at the adopter end. Both verbs follow the same
load pattern: the bundled script is loaded via
``importlib.util.spec_from_file_location`` (NOT via a top-level
``import bin``), called with the remaining argv. ``install`` also
defaults ``--source`` to the packaged bundle root before
delegating to ``install_skill.main()``.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


__all__ = ["main"]

# Public version (mirrors the pyproject.toml + the live clone).
__version__ = "1.5.7"


def _bundle_root() -> Path:
    """Return the absolute path to the packaged QPB source-layout
    data dir. Built at publish time by
    ``bin/build_channel_package.py``; absent in the source tree."""
    return Path(__file__).resolve().parent / "_bundle"


def _load_bundled_script(bundle: Path, script_rel: str,
                          private_name: str):
    """Load a script from the package bundle via importlib (NOT via
    a top-level ``import bin``). ``script_rel`` is a path relative
    to ``bundle`` (e.g. ``"bin/install_skill.py"`` or
    ``"bin/qpb_validate.py"``); ``private_name`` is the namespaced
    module name used by the importlib spec so the loaded module
    can never collide with a user's ``bin`` import.

    Used by both the ``install`` and ``validate`` verbs."""
    script = bundle / script_rel
    if not script.is_file():
        raise RuntimeError(
            f"quality-playbook: packaged bundle missing "
            f"{script_rel} at {script}. The wheel was built "
            f"incorrectly (run `python bin/build_channel_package.py` "
            f"before `python -m build`)."
        )
    spec = importlib.util.spec_from_file_location(private_name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"quality-playbook: could not load {script_rel} from "
            f"{script} (importlib spec resolution failed)."
        )
    module = importlib.util.module_from_spec(spec)
    # v1.5.7 090c: register in sys.modules BEFORE exec_module so
    # dataclass/typing machinery in path-loaded modules can resolve
    # `sys.modules[cls.__module__]`. Without this, dataclasses
    # raises AttributeError on `cls.__module__.__dict__` because
    # the private namespaced name isn't in sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_install_skill(bundle: Path):
    """Back-compat alias for the install-verb load path."""
    return _load_bundled_script(
        bundle, "bin/install_skill.py", "_qpb_install_skill_pip"
    )


def _load_qpb_validate(bundle: Path):
    """Load ``bin/qpb_validate.py`` from the package bundle. Used
    by the ``validate`` verb."""
    return _load_bundled_script(
        bundle, "bin/qpb_validate.py", "_qpb_validate_pip"
    )


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point.

    Parses argv minimally — recognizes ``install`` and ``validate``
    as subcommand verbs (the rest of argv passes through verbatim).
    Sets ``QPB_CHANNEL=pip`` if not already set so bundled scripts
    emit pip-channel remediation. Loads the bundled script via
    ``importlib.util`` (NOT via a top-level ``import bin``).
    """
    if argv is None:
        argv = list(sys.argv[1:])
    else:
        argv = list(argv)

    bundle = _bundle_root()
    if not bundle.is_dir():
        sys.stderr.write(
            f"quality-playbook: packaged data dir missing at {bundle}.\n"
            f"The wheel was built incorrectly (the build script\n"
            f"`bin/build_channel_package.py` was not run before\n"
            f"`python -m build`). Reinstall after rebuilding.\n"
        )
        return 65  # EX_DATAERR — closure incomplete.

    # Mark this invocation as pip-channel so any bundled script
    # that reads QPB_CHANNEL emits uvx/pipx remediation rather
    # than the clone form.
    os.environ.setdefault("QPB_CHANNEL", "pip")

    # Subcommand dispatch. ``install`` is the default verb when
    # none is given (back-compat with the v1.5.7 089u initial
    # release that only supported install) — but we now also
    # recognize ``validate``, which routes to qpb_validate.py from
    # the bundle so the remediation string
    # ``uvx quality-playbook validate <target>`` actually resolves.
    verb = "install"
    if argv and argv[0] in ("install", "validate"):
        verb = argv[0]
        argv = argv[1:]

    if verb == "validate":
        qpb_validate = _load_qpb_validate(bundle)
        return qpb_validate.main(argv)

    # install (default).
    # Default --source to the packaged bundle root so install_skill
    # reads from package data, not from a non-existent clone.
    if "--source" not in argv:
        argv = ["--source", str(bundle)] + argv
    install_skill = _load_install_skill(bundle)
    return install_skill.main(argv)
