"""Quality Playbook benchmark runner package.

v1.5.8 instructions 208 + 209: the plugin-native repo restructure
moved the BUNDLED scripts (the ones that ship inside
``quality_playbook_cli/_bundle/bin/`` and adopter installs at
``<install>/bin/``) from ``bin/<name>.py`` to
``plugins/quality-playbook/skills/quality-playbook/scripts/<name>.py``
(post-209, standard self-hosted marketplace layout). 208 had them
at ``skills/quality-playbook/scripts/<name>.py``; that path is
retained as a fallback for transitional clones. Repo-level
``bin/*.py`` (run_playbook, build_channel_package, publish_pip,
publish_npm, submit_awesome_copilot, etc.) reference them via
``from bin import <name>`` / ``from bin.<name> import …``.

This ``__init__.py`` extends the package's ``__path__`` so those
imports keep resolving — Python's package-finder walks ``__path__``
when resolving ``bin.<name>``, so the moved scripts are still
discoverable as ``bin.<name>``. No per-file shim is required.

The bin/install_skill.py shim is a separate, explicit file because
it's also a CLI entry point invoked from build_channel_package +
publish_pip + publish_npm as a subprocess (``python3 -m
bin.install_skill``), and the explicit shim keeps the file-by-file
``importlib.util.spec_from_file_location`` invocation pattern that
``_bundle_files()`` ships at adopter side."""

from pathlib import Path as _Path

# v1.5.8 instruction 209: extend the package search path to include
# the canonical skill-scripts directory so ``from bin import X``
# and ``from bin.X import Y`` continue resolving for bundled
# modules that now live at
# plugins/quality-playbook/skills/quality-playbook/scripts/.
# 208-era skills/quality-playbook/scripts/ is also appended for
# transitional clones — first hit wins via Python's package finder.
_REPO_ROOT = _Path(__file__).resolve().parent.parent
_CANONICAL_SCRIPTS_DIR = (
    _REPO_ROOT / "plugins" / "quality-playbook"
    / "skills" / "quality-playbook" / "scripts"
)
_LEGACY_208_SCRIPTS_DIR = (
    _REPO_ROOT / "skills" / "quality-playbook" / "scripts"
)
if _CANONICAL_SCRIPTS_DIR.is_dir():
    # Append (not prepend) so legacy bin/<name>.py at the repo root
    # still wins if any non-bundled module happens to share a name
    # with a bundled one (no current overlap, but defensive).
    __path__.append(str(_CANONICAL_SCRIPTS_DIR))
if _LEGACY_208_SCRIPTS_DIR.is_dir():
    __path__.append(str(_LEGACY_208_SCRIPTS_DIR))

__all__ = [
    "archive_lib",
    "benchmark_lib",
    "citation_verifier",
    "council_config",
    "council_semantic_check",
    "reference_docs_ingest",
    "migrate_v1_5_0_layout",
    "quality_playbook",
    "run_playbook",
]