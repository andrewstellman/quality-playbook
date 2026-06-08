"""Quality Playbook benchmark runner package.

v1.5.8 instruction 208: the plugin-native repo restructure moved the
BUNDLED scripts (the ones that ship inside ``quality_playbook_cli/
_bundle/bin/`` and adopter installs at ``<install>/bin/``) from
``bin/<name>.py`` to ``skills/quality-playbook/scripts/<name>.py``.
Repo-level ``bin/*.py`` (run_playbook, build_channel_package,
publish_pip, publish_npm, submit_awesome_copilot, etc.) reference
them via ``from bin import <name>`` / ``from bin.<name> import …``.

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

# v1.5.8 instruction 208: extend the package search path to include
# the canonical skill-scripts directory so ``from bin import X``
# and ``from bin.X import Y`` continue resolving for bundled
# modules that moved to skills/quality-playbook/scripts/.
_CANONICAL_SCRIPTS_DIR = (
    _Path(__file__).resolve().parent.parent
    / "skills" / "quality-playbook" / "scripts"
)
if _CANONICAL_SCRIPTS_DIR.is_dir():
    # Append (not prepend) so legacy bin/<name>.py at the repo root
    # still wins if any non-bundled module happens to share a name
    # with a bundled one (no current overlap, but defensive).
    __path__.append(str(_CANONICAL_SCRIPTS_DIR))

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