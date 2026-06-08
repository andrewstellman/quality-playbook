"""v1.5.7 instruction 077 (addendum r3 §5.2 W3 entry-point audit) —
the five audited entry points carry the sys.path bootstrap (or import
no sibling bin.* module at all).

Pins the W3 audit outcome so a future edit cannot silently drop a
bootstrap and reintroduce the 073/074-class cwd-dependence.

Note on the "first N lines" wording: instruction-077 Task 4 #7
illustratively says "first 10 lines", but two correctly-bootstrapped
scripts place the standard pattern later in the *import preamble*
(reference_docs_ingest.py wraps it in the canonical
try/except-ImportError form ~line 49; validate_phase_artifacts.py
~line 76, after its long module docstring). The addendum §5.2 is
canonical and its intent is "script-form works from any cwd / apply
the standard pattern if missing". This test therefore asserts the
robust invariant the addendum actually requires — the bootstrap
appears anywhere in the module import preamble (before the first
top-level def/class), OR the script imports no sibling bin.* module
so the bootstrap would be a no-op — rather than a brittle literal
line-10 window that would wrongly fail those two. (Empirically, all
five exit 0 in script form from a foreign cwd — see
test_install_skill_script_form.py.)
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
# v1.5.8 instruction 208: bundled scripts moved to
# skills/quality-playbook/scripts/. The audit list includes both
# bundled and unbundled scripts, so resolve each by trying the
# nested location first then the legacy bin/ location.
_NESTED_BIN = _QPB_ROOT / "skills" / "quality-playbook" / "scripts"
_LEGACY_BIN = _QPB_ROOT / "bin"


def _resolve_audited_script(script: str) -> Path:
    nested = _NESTED_BIN / script
    if nested.is_file():
        return nested
    return _LEGACY_BIN / script


# Backward-compat: tests may reference ``_BIN / <script>`` as if
# all audited scripts live in one folder. Expose ``_BIN`` as a
# helper-object whose ``/`` operator delegates to
# ``_resolve_audited_script`` while a path-shaped repr still works.
class _BinResolver:
    def __truediv__(self, script: str) -> Path:
        return _resolve_audited_script(script)

    def __repr__(self) -> str:
        return f"<BinResolver nested={_NESTED_BIN} legacy={_LEGACY_BIN}>"


_BIN = _BinResolver()

_AUDITED = (
    "validate_phase_artifacts.py",
    "reference_docs_ingest.py",
    "quality_playbook.py",
    "classify_project.py",
    "qpb_config.py",
)

_BOOTSTRAP = "sys.path.insert(0, str(Path(__file__).resolve().parent.parent))"
_FIRST_DEF_RE = re.compile(r"^(def |class )", re.MULTILINE)
_SIBLING_IMPORT_RE = re.compile(
    r"^\s*(from\s+bin(\.\w+)?\s+import\b"
    r"|import\s+bin\b"
    r"|from\s+\.\s+import\b"
    r"|from\s+\.\w+\s+import\b)")


def _preamble(src: str) -> str:
    m = _FIRST_DEF_RE.search(src)
    return src[:m.start()] if m else src


def _imports_sibling_bin_module(src: str) -> bool:
    for line in src.splitlines():
        if line.lstrip().startswith("#"):
            continue
        if _SIBLING_IMPORT_RE.match(line):
            return True
    return False


class EntryPointBootstrapAuditTests(unittest.TestCase):

    def test_audited_scripts_have_bootstrap_or_no_sibling_import(self) -> None:
        """Each §5.2 audited script has the standard sys.path
        bootstrap in its import preamble, or imports no sibling bin.*
        module (bootstrap would be a no-op).

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-077 —
        BITE EXECUTED during instruction-077 development:
          Mutation: delete the §5.2 bootstrap line from
          bin/quality_playbook.py (which DOES import siblings via
          `from . import archive_lib`).
          Observed failure (purged __pycache__ first):
            FAIL: test_audited_scripts_have_bootstrap_or_no_sibling_import
            (script='quality_playbook.py')
            AssertionError: False is not true : quality_playbook.py:
            no sys.path bootstrap in import preamble AND it imports a
            sibling bin.* module — script form will break from a
            foreign cwd
          Restoration: bootstrap restored; test PASS again.
        """
        for script in _AUDITED:
            with self.subTest(script=script):
                src = (_BIN / script).read_text(encoding="utf-8")
                preamble = _preamble(src)
                has_bootstrap = _BOOTSTRAP in preamble
                imports_sibling = _imports_sibling_bin_module(src)
                self.assertTrue(
                    has_bootstrap or not imports_sibling,
                    f"{script}: no sys.path bootstrap in import "
                    f"preamble AND it imports a sibling bin.* module "
                    f"— script form will break from a foreign cwd")

    def test_scripts_that_import_siblings_actually_have_bootstrap(self) -> None:
        """Stronger: any audited script that imports a sibling bin.*
        module MUST carry the bootstrap (the no-op alternative only
        excuses pure-stdlib scripts)."""
        for script in _AUDITED:
            with self.subTest(script=script):
                src = (_BIN / script).read_text(encoding="utf-8")
                if _imports_sibling_bin_module(src):
                    self.assertIn(
                        _BOOTSTRAP, _preamble(src),
                        f"{script} imports a sibling bin.* module but "
                        f"lacks the §5.2 bootstrap in its preamble")

    def test_validator_has_bootstrap(self) -> None:
        """The Phase 0 validator (launch-prompt invoked in script
        form) carries the bootstrap too."""
        src = (_BIN / "qpb_validate.py").read_text(encoding="utf-8")
        self.assertIn(_BOOTSTRAP, _preamble(src))


if __name__ == "__main__":
    unittest.main()
