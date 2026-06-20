"""quality_playbook_cli: thin entry-point shim for the pip
distribution channel.

`quality-playbook` (the console script) routes through
`quality_playbook_cli.main()`, which locates the bundled QPB
source-layout data under `_bundle/`, sets ``QPB_CHANNEL=pip``,
loads the bundled ``install_skill.py`` / ``qpb_validate.py`` via
importlib (NOT via a top-level ``import bin``), and delegates to
the same entry points the clone workflow uses.

**Hard packaging constraint**: the full ``bin/`` tooling closure
ships as **package data**, NOT as an importable top-level ``bin``
package. After ``pip install quality-playbook``, ``python -c
"import bin"`` MUST FAIL — only ``import quality_playbook_cli``
resolves.

Public CLI surface:

    quality-playbook install <target-repo> --ai-tool <tool>
    quality-playbook install --into <repo> --ai-tool <tool> --force
    quality-playbook install --help            # install_skill help
    quality-playbook validate <target-repo>    # runs qpb_validate
    quality-playbook validate --help           # qpb_validate help
    quality-playbook --help                    # alias for `install --help`
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


__all__ = ["main"]


def _detect_version() -> str:
    """Read the skill version from SKILL.md frontmatter — THE single
    canonical source (v1.5.10 instruction 057). ``__version__`` is no
    longer a hand-maintained literal; it derives at import time.

    Candidate SKILL.md locations, in order:
      1. ``<this_file>/_bundle/SKILL.md`` — the staged bundle shipped
         inside the installed pip wheel / npm tarball.
      2. ``<this_file>/../SKILL.md`` — the repo-root SKILL.md when
         running from a source clone (quality_playbook_cli/ sits one
         level under the root).
    Returns ``"0.0.0+unknown"`` only if neither is readable — never
    raises, so importing the shim can't fail on a malformed tree."""
    candidates = [
        Path(__file__).resolve().parent / "_bundle" / "SKILL.md",
        Path(__file__).resolve().parent.parent / "SKILL.md",
    ]
    for cand in candidates:
        try:
            text = cand.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue
        # Bounded to frontmatter when present; SKILL.md only carries a
        # `version:` line in frontmatter, never in the body.
        block = text
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                block = text[:end]
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("version:"):
                val = stripped.split(":", 1)[1].strip()
                if val:
                    return val
    return "0.0.0+unknown"  # pragma: no cover - defensive


# Public version — derived from SKILL.md frontmatter (single source,
# instruction 057), not a hand-maintained literal.
__version__ = _detect_version()


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
    # Register in sys.modules BEFORE exec_module so dataclass /
    # typing machinery in path-loaded modules can resolve
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
    # none is given (back-compat with the initial release that
    # only supported install) — but we now also recognize
    # ``validate``, which routes to qpb_validate.py from the
    # bundle so the remediation string
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
