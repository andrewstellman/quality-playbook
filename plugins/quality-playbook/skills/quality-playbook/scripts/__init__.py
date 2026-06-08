"""Quality Playbook bundled-scripts package.

This is the SOURCE for the adopter-side ``bin/__init__.py`` shipped in
every install bundle. Both the pip wheel (`quality_playbook_cli/_bundle/
bin/__init__.py`) and the npm tarball stage from this file. v1.5.8
instruction 208 renamed the source location from ``bin/__init__.py``
to ``skills/quality-playbook/scripts/__init__.py`` as part of the
plugin-native repo layout; the dev-time ``bin/__init__.py`` at the
repo root is a SEPARATE file that lets the repo-level ``bin/``
directory keep working as a Python package for non-bundled scripts
(run_playbook, build_channel_package, publish_pip, etc.).
"""

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
