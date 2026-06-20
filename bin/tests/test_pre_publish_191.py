"""v1.5.7 191 — pre-publish 1.5.8 fixes (codex audit findings).

FINDING-48: `__init__.py:__version__` must match `pyproject.toml`
version. The v1.5.7 → 1.5.8 bump missed `__init__.py`.

FINDING-49: `package.json:description` must not leak internal
instruction codes. The pre-191 description carried "v1.5.7 089v
block C." as a parenthetical.

FINDING-51: file headers in `pyproject.toml`, `__init__.py`, and
`bin/quality-playbook.js` must not carry internal instruction
codes (`089u`, `090c F:`, `089v`-style references) or dated
release-engineering provenance. These files ship — the codes are
meaningless to anyone outside the project.
"""
from __future__ import annotations

import pathlib
import re
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]


_INTERNAL_CODE_PATTERNS = [
    # 089u, 089v, 090c, 091x — 3-digit + lowercase letter form
    re.compile(r"\b\d{3}[a-z]\b"),
    # 089u decision, 2026-05-22 — dated decision markers
    re.compile(r"\d{3}[a-z]\s+decision"),
    # FINDING-NN — internal finding codes
    re.compile(r"\bFINDING-\d+\b"),
    # v1.5.7 prefix on internal instruction references
    re.compile(r"v1\.5\.[0-9]\s+\d{3}"),
]


def _read_pyproject_version() -> str:
    text = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if m is None:
        raise AssertionError("pyproject.toml has no version line")
    return m.group(1)


def _read_init_version() -> str:
    # v1.5.10 instruction 057: __version__ is no longer a hand-written
    # literal — it DERIVES from SKILL.md frontmatter at import time. Read
    # the runtime value (import the module) instead of regex-scanning for
    # a literal that no longer exists.
    import importlib
    import sys
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    qpc = importlib.import_module("quality_playbook_cli")
    return qpc.__version__


def _read_package_json_description() -> str:
    import json
    pkg = json.loads(
        (_REPO / "package.json").read_text(encoding="utf-8"))
    return pkg.get("description", "")


def _read_pyproject_description() -> str:
    text = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(
        r'^description\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if m is None:
        raise AssertionError("pyproject.toml has no description")
    return m.group(1)


class PrePublishVersionTests(unittest.TestCase):
    """FINDING-48 — version-stamp parity across publishing
    surfaces."""

    def test_quality_playbook_cli_version_matches_pyproject(
            self) -> None:
        """The runtime `quality_playbook_cli.__version__` an
        installed user sees MUST equal `pyproject.toml` version.
        A mismatch is a publish-time bug invisible until an
        adopter introspects."""
        pyp = _read_pyproject_version()
        init = _read_init_version()
        self.assertEqual(
            init, pyp,
            f"version mismatch: pyproject.toml={pyp!r} but "
            f"quality_playbook_cli/__init__.py:__version__"
            f"={init!r}. Update __init__.py to match.")


class PrePublishDescriptionTests(unittest.TestCase):
    """FINDING-49 — `package.json:description` must not leak
    internal codes (it renders on npmjs.com)."""

    def test_package_json_description_matches_pyproject(
            self) -> None:
        """The npm and pip descriptions should match verbatim
        — one published voice across both channels."""
        npm = _read_package_json_description()
        pip = _read_pyproject_description()
        self.assertEqual(
            npm, pip,
            f"description mismatch: package.json={npm!r} "
            f"vs pyproject.toml={pip!r}.")

    def test_package_json_description_has_no_internal_codes(
            self) -> None:
        """Even if the descriptions diverge in the future, the
        npm description MUST NOT carry internal instruction
        codes (089-style references)."""
        desc = _read_package_json_description()
        for pat in _INTERNAL_CODE_PATTERNS:
            m = pat.search(desc)
            self.assertIsNone(
                m, f"package.json description carries internal "
                   f"code matching {pat.pattern!r}: "
                   f"{m.group(0) if m else ''!r} in {desc!r}")


class PrePublishHeaderTests(unittest.TestCase):
    """FINDING-51 — file headers ship to PyPI / npm. Must not
    carry internal codes (089u, 090c F:, etc.) or dated release-
    engineering provenance."""

    def _assert_no_codes_in_first_lines(
            self, relpath: str, n_lines: int) -> None:
        text = (_REPO / relpath).read_text(encoding="utf-8")
        head = "\n".join(text.splitlines()[:n_lines])
        for pat in _INTERNAL_CODE_PATTERNS:
            m = pat.search(head)
            self.assertIsNone(
                m, f"{relpath} first {n_lines} lines carry "
                   f"internal code: matched {pat.pattern!r} "
                   f"-> {m.group(0) if m else ''!r}")

    def test_no_internal_codes_in_pyproject_header(self) -> None:
        """pyproject.toml top 30 lines (header + project table
        intro) — no internal codes."""
        self._assert_no_codes_in_first_lines("pyproject.toml", 30)

    def test_no_internal_codes_in_quality_playbook_cli_init(
            self) -> None:
        """quality_playbook_cli/__init__.py header docstring —
        no internal codes."""
        self._assert_no_codes_in_first_lines(
            "quality_playbook_cli/__init__.py", 40)

    def test_no_internal_codes_in_quality_playbook_js(
            self) -> None:
        """bin/quality-playbook.js header — no internal codes."""
        self._assert_no_codes_in_first_lines(
            "bin/quality-playbook.js", 60)


if __name__ == "__main__":
    unittest.main()
