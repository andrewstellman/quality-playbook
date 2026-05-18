"""v1.5.7 instruction 086 (A-26) regression defense.

Sibling file, consistent with the existing test_install_* split
(test_install_manifest_no_drift / test_install_skill_script_form /
test_install_skill).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from bin import install_skill


class BundleCompletenessTests(unittest.TestCase):
    """v1.5.7 instruction 086 (A-26) regression defense: every
    bin.<module> reference in SKILL.md or phase_prompts/*.md must be
    either bundled by install_skill.py OR explicitly listed in the
    operator-side allowlist (modules adopters run from the QPB clone,
    NOT from install_root).

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    086 development:
      Mutation: remove run_state_lib.py from the 086 bundle additions
        in install_skill.py._bundle_files().
      Observed failure (purged __pycache__ first):
        FAIL: test_every_bin_module_referenced_in_skill_or_phase_prompts_is_bundled_or_allowlisted
        AssertionError: bin.run_state_lib referenced in
        SKILL.md/phase_prompts/*.md but neither bundled nor allowlisted.
      Mutation reverted; tests pass.
    """

    # Adopters do NOT run these from install_root — they're QPB-side
    # operator-driven entry points. SKILL.md / phase_prompts may
    # reference them as `<clone>/bin/<name>.py` style invocations.
    _OPERATOR_SIDE_BIN_MODULES = frozenset({
        "bin.run_playbook",   # Mode B runner — operator-side
        "bin.qpb_validate",   # Phase 0 entry — operator runs from QPB clone
    })

    def test_every_bin_module_referenced_in_skill_or_phase_prompts_is_bundled_or_allowlisted(self) -> None:
        """For each `bin.<module>` reference in SKILL.md or
        phase_prompts/*.md, verify the corresponding file is either
        bundled by install_skill.py::_bundle_files() OR in the
        operator-side allowlist."""
        qpb_root = Path(__file__).resolve().parent.parent.parent
        text_sources = [qpb_root / "SKILL.md"]
        phase_prompts = qpb_root / "phase_prompts"
        if phase_prompts.is_dir():
            text_sources.extend(sorted(phase_prompts.glob("*.md")))

        referenced: set[str] = set()
        pattern = re.compile(r"\bbin\.([a-z_][a-z0-9_]+)\b")
        for src in text_sources:
            if src.is_file():
                for match in pattern.finditer(
                        src.read_text(encoding="utf-8")):
                    referenced.add(f"bin.{match.group(1)}")

        bundled = {
            f"bin.{src.name[:-3]}"  # strip .py
            for src, _dst in install_skill._bundle_files(qpb_root)
            if src.suffix == ".py" and src.parent.name == "bin"
        }

        for ref in sorted(referenced):
            if ref in self._OPERATOR_SIDE_BIN_MODULES:
                continue
            self.assertIn(
                ref, bundled,
                f"{ref} referenced in SKILL.md/phase_prompts/*.md "
                f"but neither bundled by install_skill.py nor in the "
                f"operator-side allowlist "
                f"({sorted(self._OPERATOR_SIDE_BIN_MODULES)}). Either "
                f"add it to _bundle_files() or, if it's an "
                f"operator-side entry point adopters don't invoke from "
                f"install_root, add it to the _OPERATOR_SIDE_BIN_MODULES "
                f"allowlist.")


if __name__ == "__main__":
    unittest.main()
