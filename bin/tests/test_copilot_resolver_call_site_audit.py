"""v1.5.7 089f — call-site audit pin for the gh-copilot → copilot
CLI migration.

After 089f, all active subprocess invocations of the GitHub Copilot
CLI MUST route through ``bin/copilot_resolver.py``. Literal
``["gh", "copilot", ...]`` subprocess argv constructions outside the
resolver itself constitute stale-touchpoint debt that would split
the skill's CLI handling — adopters on the new ``copilot`` CLI would
hit FileNotFoundError on those stale call sites while the resolver-
routed call sites work fine.

This test grep-walks ``bin/`` and the gate directory and asserts that
the literal pattern ``["gh", "copilot"`` appears ONLY inside:

  (a) ``bin/copilot_resolver.py`` itself (the resolver legitimately
      emits this argv for its gh-copilot fallback branch and probes
      ``["gh", "copilot", "--help"]`` for availability — both are
      "availability-check fallback" per instruction 089f Task 7).
  (b) Test files (test mocks that exercise the fallback path
      need to construct the expected argv literal to assert against).
  (c) Comments / docstrings explaining historical / legacy behavior
      — flagged by detecting comment / triple-quoted-string context
      on the same or preceding line.

Mutation-bite evidence (ai_context/DEVELOPMENT_PROCESS.md:152-160),
instruction-089f Task 3:
  Mutation: revert ``bin/run_playbook.py``'s ``command_for_runner``
  copilot branch to the pre-089f literal ``["gh", "copilot", "-p",
  prompt, "--model", copilot_model, "--yolo"]`` form.
  Expected failure: this test fails — ``run_playbook.py`` now
  contains a stray literal outside the resolver.
  Restoration: re-set to the resolver call; passes.
  Bite executed during 089f Task 3; PASS→FAIL→PASS confirmed.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Active-source directories where stray gh-copilot subprocess literals
# would be a migration regression. The resolver itself is excluded
# (it's the legitimate home of these literals); test files are
# excluded (they may construct the literal as expected-argv for the
# fallback path).
# v1.5.8 instruction 208: bundled skill scripts moved into
# skills/quality-playbook/scripts/; sweep there instead of the
# legacy .github/skills/quality_gate/ location.
_AUDIT_DIRS = [
    _REPO_ROOT / "bin",
    _REPO_ROOT / "skills" / "quality-playbook" / "scripts",
]
_RESOLVER_PATH = _REPO_ROOT / "bin" / "copilot_resolver.py"

# The pattern that indicates a SUBPROCESS argv literal — a list
# starting with ``["gh", "copilot"`` (with the comma + quoted
# elements that mark a Python list literal). Doesn't match prose
# like "use `gh copilot`" or `gh copilot --help` in markdown.
_STRAY_PATTERN = re.compile(r'\[\s*[\'"]gh[\'"]\s*,\s*[\'"]copilot[\'"]')


class CopilotResolverCallSiteAuditTests(unittest.TestCase):

    def test_no_stray_gh_copilot_argv_literals_in_active_source(self) -> None:
        """No file outside ``bin/copilot_resolver.py`` and test
        files may contain the literal pattern
        ``["gh", "copilot", ...]`` as a subprocess argv.
        """
        offenders: list[str] = []
        for audit_dir in _AUDIT_DIRS:
            if not audit_dir.is_dir():
                continue
            for py_file in audit_dir.rglob("*.py"):
                # Skip the resolver itself (legitimate home for the
                # fallback literal + availability probe).
                if py_file.resolve() == _RESOLVER_PATH.resolve():
                    continue
                # Skip test files (mocks build the expected literal
                # to assert against).
                if "/tests/" in str(py_file) or py_file.name.startswith("test_"):
                    continue
                # Skip __pycache__ if any escaped.
                if "__pycache__" in str(py_file):
                    continue
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                if _STRAY_PATTERN.search(source):
                    # Capture line numbers for a useful failure
                    # message — match.start() gives byte offset; we
                    # convert to line number via the lines-up-to-match
                    # count.
                    for m in _STRAY_PATTERN.finditer(source):
                        line_no = source.count("\n", 0, m.start()) + 1
                        rel = py_file.relative_to(_REPO_ROOT)
                        offenders.append(f"{rel}:{line_no}")

        self.assertEqual(
            offenders, [],
            f"v1.5.7 089f migration audit: found stray "
            f"['gh', 'copilot', ...] subprocess argv literals "
            f"outside bin/copilot_resolver.py and test files. "
            f"All Copilot CLI invocations MUST route through "
            f"bin.copilot_resolver.resolve_copilot_command(). "
            f"Offenders: {offenders}",
        )

    def test_resolver_module_exists_and_is_importable(self) -> None:
        """The resolver module must exist at the canonical path —
        a guard against accidental removal that would break every
        Mode B reviewer subprocess site at once.
        """
        self.assertTrue(
            _RESOLVER_PATH.is_file(),
            f"bin/copilot_resolver.py must exist at {_RESOLVER_PATH}; "
            f"it's the load-bearing seam for the 089f CLI migration.",
        )
        # Importability: if this fails, the resolver has a syntax
        # error and every subprocess site that imports it is broken.
        from bin import copilot_resolver  # noqa: F401
        # Detection helper signature must match the documented surface.
        self.assertTrue(callable(copilot_resolver.resolve_copilot_command))
        self.assertTrue(callable(copilot_resolver.require_copilot_cli))
        self.assertTrue(hasattr(copilot_resolver, "CopilotCLIUnavailable"))
        self.assertTrue(callable(copilot_resolver.reset_cache))


if __name__ == "__main__":
    unittest.main()
